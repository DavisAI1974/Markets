#!/usr/bin/env python3
"""Revalidate source-spec-derived S3 capabilities before readiness-v38 execution.

The AWS execution-context gate proves the active principal and region. This gate proves that
that exact principal can reach every declared corpus bucket and prefix, that bucket versioning
is enabled, and that checksum-enabled metadata can be read for a deterministic declared source
in each corpus. It performs control-plane and HEAD requests only; it never downloads corpus
bytes and never claims corpus completeness.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_corpus_coverage_audit as coverage
import ng_corpus_s3_inventory_capture as capture
import ng_corpus_s3_latest_version_resolution as resolution
import ng_corpus_executor_plan_compiler_v31 as compiler
import ng_v38_aws_execution_context_revalidation_gate as aws_gate

SCHEMA = "ng_v38_s3_source_capability_revalidation_gate.v1"
READY = "V38_S3_SOURCE_CAPABILITIES_REVALIDATED_READY"
BLOCKED = "V38_S3_SOURCE_CAPABILITIES_REVALIDATION_BLOCKED"
_ERROR_TOKEN = re.compile(r"[^A-Z0-9_]+")


class V38S3SourceCapabilityRevalidationError(ValueError):
    """Raised when S3 capability evidence is malformed, unsafe, or stale."""


def _fp(value: Any) -> str:
    return compiler._fp(value)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V38S3SourceCapabilityRevalidationError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise V38S3SourceCapabilityRevalidationError(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any]) -> None:
    expected = {
        "paid_live_data_assumed": False,
        "corpus_files_opened": False,
        "outcome_files_opened": False,
        "actual_outcomes_used": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_g16_blind_prior": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }
    for field, expected_value in expected.items():
        if value.get(field) != expected_value:
            raise V38S3SourceCapabilityRevalidationError(
                f"S3 source-capability revalidation must keep {field}={expected_value!r}"
            )


def _default_command_runner(
    argv: Sequence[str], timeout_seconds: float
) -> Mapping[str, Any]:
    return aws_gate._default_command_runner(argv, timeout_seconds)


def _error_code(stderr: Any) -> str:
    text = str(stderr or "").upper()
    for token in (
        "ACCESSDENIED",
        "NOSUCHBUCKET",
        "NOSUCHKEY",
        "INVALIDACCESSKEYID",
        "SIGNATUREDOESNOTMATCH",
        "EXPIREDTOKEN",
        "AUTHORIZATIONHEADERMALFORMED",
        "KMSACCESSDENIED",
    ):
        if token in text.replace(" ", ""):
            return token
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"AWS_CLI_ERROR_{digest}"


def _probe_json(
    argv: Sequence[str],
    *,
    command_runner: Callable[[Sequence[str], float], Mapping[str, Any]],
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        result = dict(command_runner(tuple(argv), timeout_seconds))
    except Exception as error:
        return {
            "ok": False,
            "returncode": None,
            "error_code": f"RUNNER_EXCEPTION_{type(error).__name__.upper()}",
            "response": None,
        }
    returncode = int(result.get("returncode", 1))
    if returncode != 0:
        return {
            "ok": False,
            "returncode": returncode,
            "error_code": _error_code(result.get("stderr")),
            "response": None,
        }
    try:
        response = json.loads(str(result.get("stdout") or ""))
    except json.JSONDecodeError:
        return {
            "ok": False,
            "returncode": returncode,
            "error_code": "INVALID_JSON_RESPONSE",
            "response": None,
        }
    if not isinstance(response, dict):
        return {
            "ok": False,
            "returncode": returncode,
            "error_code": "NON_OBJECT_JSON_RESPONSE",
            "response": None,
        }
    return {"ok": True, "returncode": returncode, "error_code": None, "response": response}


def _profile_args(profile: str | None) -> list[str]:
    return ["--profile", profile] if profile else []


def _global_args(aws_path: Path, profile: str | None, region: str) -> list[str]:
    return [str(aws_path), *_profile_args(profile), "--region", region, "--no-cli-pager"]


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise V38S3SourceCapabilityRevalidationError(f"{label} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise V38S3SourceCapabilityRevalidationError(
            f"{label} must be a positive integer"
        ) from error
    if number <= 0:
        raise V38S3SourceCapabilityRevalidationError(f"{label} must be a positive integer")
    return number


def _normalize_scope(
    source_spec: Mapping[str, Any],
    *,
    selected_profile: str | None,
    effective_region: str,
    expected_account_id: str,
) -> dict[str, Any]:
    spec = copy.deepcopy(dict(source_spec))
    if spec.get("schema") != resolution.SPEC_SCHEMA:
        raise V38S3SourceCapabilityRevalidationError(
            f"source spec schema must be {resolution.SPEC_SCHEMA}"
        )
    try:
        resolution._authority(spec, label="S3 capability source spec")
    except Exception as error:
        raise V38S3SourceCapabilityRevalidationError(str(error)) from error
    spec_profile = str(spec.get("aws_profile") or "").strip() or None
    spec_region = str(spec.get("aws_region") or "").strip() or None
    if spec_profile is not None and spec_profile != selected_profile:
        raise V38S3SourceCapabilityRevalidationError(
            "source spec AWS profile differs from the validated execution profile"
        )
    if spec_region is not None and spec_region != effective_region:
        raise V38S3SourceCapabilityRevalidationError(
            "source spec AWS region differs from the validated execution region"
        )
    corpora = list(spec.get("corpora") or [])
    if len(corpora) != len(coverage.EXPECTED_WINDOWS):
        raise V38S3SourceCapabilityRevalidationError(
            "source spec must contain both canonical corpora"
        )
    normalized: list[dict[str, Any]] = []
    seen_corpora: set[str] = set()
    seen_sources: set[str] = set()
    seen_keys: set[tuple[str, str]] = set()
    for raw_corpus in corpora:
        if not isinstance(raw_corpus, Mapping):
            raise V38S3SourceCapabilityRevalidationError("source corpus is not an object")
        corpus = copy.deepcopy(dict(raw_corpus))
        corpus_id = str(corpus.get("corpus_id") or "")
        expected = coverage.EXPECTED_WINDOWS.get(corpus_id)
        if expected is None or corpus_id in seen_corpora:
            raise V38S3SourceCapabilityRevalidationError(
                f"unexpected or duplicate corpus_id {corpus_id!r}"
            )
        seen_corpora.add(corpus_id)
        lane = str(corpus.get("lane") or "")
        if lane != expected["lane"]:
            raise V38S3SourceCapabilityRevalidationError(f"{corpus_id}: lane mismatch")
        bucket = str(corpus.get("bucket") or "").strip()
        prefix = str(corpus.get("prefix") or "")
        if not bucket or "://" in bucket or bucket.startswith("/"):
            raise V38S3SourceCapabilityRevalidationError(f"{corpus_id}: invalid bucket")
        if not prefix or prefix.startswith("/"):
            raise V38S3SourceCapabilityRevalidationError(
                f"{corpus_id}: a non-empty dedicated prefix is required"
            )
        owner_account_id = str(
            corpus.get("bucket_owner_account_id") or expected_account_id
        ).strip()
        if not re.fullmatch(r"[0-9]{12}", owner_account_id):
            raise V38S3SourceCapabilityRevalidationError(
                f"{corpus_id}: bucket_owner_account_id must be 12 digits"
            )
        expected_count = _positive_int(
            corpus.get("expected_object_count"),
            label=f"{corpus_id}:expected_object_count",
        )
        sources = list(corpus.get("sources") or [])
        if len(sources) != expected_count:
            raise V38S3SourceCapabilityRevalidationError(
                f"{corpus_id}: declared source count differs from expected_object_count"
            )
        normalized_sources: list[dict[str, str]] = []
        for raw_source in sources:
            if not isinstance(raw_source, Mapping):
                raise V38S3SourceCapabilityRevalidationError(
                    f"{corpus_id}: source is not an object"
                )
            source_id = str(raw_source.get("source_id") or "")
            key = str(raw_source.get("key") or "")
            day = str(raw_source.get("day") or "")
            source_lane = str(raw_source.get("lane") or "")
            if not source_id or source_id in seen_sources:
                raise V38S3SourceCapabilityRevalidationError(
                    f"duplicate or missing source_id {source_id!r}"
                )
            if not day or source_lane != lane:
                raise V38S3SourceCapabilityRevalidationError(
                    f"{source_id}: explicit day/lane is missing or inconsistent"
                )
            if not key or not key.startswith(prefix):
                raise V38S3SourceCapabilityRevalidationError(
                    f"{source_id}: exact key under the declared prefix is required"
                )
            pair = (bucket, key)
            if pair in seen_keys:
                raise V38S3SourceCapabilityRevalidationError(
                    f"{source_id}: duplicate bucket/key declaration"
                )
            seen_sources.add(source_id)
            seen_keys.add(pair)
            normalized_sources.append(
                {"source_id": source_id, "day": day, "lane": lane, "key": key}
            )
        normalized_sources.sort(key=lambda row: row["source_id"])
        normalized.append(
            {
                "corpus_id": corpus_id,
                "lane": lane,
                "bucket": bucket,
                "prefix": prefix,
                "bucket_owner_account_id": owner_account_id,
                "expected_object_count": expected_count,
                "source_count": len(normalized_sources),
                "sources": normalized_sources,
                "checksum_probe_source": normalized_sources[0],
            }
        )
    if seen_corpora != set(coverage.EXPECTED_WINDOWS):
        raise V38S3SourceCapabilityRevalidationError(
            "source spec is missing a canonical corpus"
        )
    normalized.sort(key=lambda row: row["corpus_id"])
    return {
        "aws_profile": selected_profile,
        "aws_region": effective_region,
        "corpora": normalized,
    }


def _collect_probe_evidence(
    scope: Mapping[str, Any],
    *,
    aws_path: Path,
    command_runner: Callable[[Sequence[str], float], Mapping[str, Any]],
    timeout_seconds: float,
) -> dict[str, Any]:
    profile = scope.get("aws_profile")
    region = str(scope.get("aws_region") or "")
    global_args = _global_args(aws_path, str(profile) if profile else None, region)
    bucket_requests: dict[tuple[str, str], dict[str, Any]] = {}
    for corpus in scope.get("corpora") or []:
        bucket_requests[(corpus["bucket"], corpus["bucket_owner_account_id"])] = corpus
    buckets: dict[str, Any] = {}
    for (bucket, owner), _ in sorted(bucket_requests.items()):
        request_id = f"{owner}:{bucket}"
        buckets[request_id] = {
            "bucket": bucket,
            "bucket_owner_account_id": owner,
            "location": _probe_json(
                [
                    *global_args,
                    "s3api",
                    "get-bucket-location",
                    "--bucket",
                    bucket,
                    "--expected-bucket-owner",
                    owner,
                    "--output",
                    "json",
                ],
                command_runner=command_runner,
                timeout_seconds=timeout_seconds,
            ),
            "versioning": _probe_json(
                [
                    *global_args,
                    "s3api",
                    "get-bucket-versioning",
                    "--bucket",
                    bucket,
                    "--expected-bucket-owner",
                    owner,
                    "--output",
                    "json",
                ],
                command_runner=command_runner,
                timeout_seconds=timeout_seconds,
            ),
        }
    corpora: dict[str, Any] = {}
    for corpus in scope.get("corpora") or []:
        sample = corpus["checksum_probe_source"]
        owner = corpus["bucket_owner_account_id"]
        bucket = corpus["bucket"]
        corpora[corpus["corpus_id"]] = {
            "corpus_id": corpus["corpus_id"],
            "bucket": bucket,
            "prefix": corpus["prefix"],
            "bucket_owner_account_id": owner,
            "checksum_probe_source_id": sample["source_id"],
            "checksum_probe_key": sample["key"],
            "prefix_list_object_versions": _probe_json(
                [
                    *global_args,
                    "s3api",
                    "list-object-versions",
                    "--bucket",
                    bucket,
                    "--prefix",
                    corpus["prefix"],
                    "--max-keys",
                    "1",
                    "--expected-bucket-owner",
                    owner,
                    "--output",
                    "json",
                ],
                command_runner=command_runner,
                timeout_seconds=timeout_seconds,
            ),
            "checksum_head_object": _probe_json(
                [
                    *global_args,
                    "s3api",
                    "head-object",
                    "--bucket",
                    bucket,
                    "--key",
                    sample["key"],
                    "--checksum-mode",
                    "ENABLED",
                    "--expected-bucket-owner",
                    owner,
                    "--output",
                    "json",
                ],
                command_runner=command_runner,
                timeout_seconds=timeout_seconds,
            ),
        }
    return {"buckets": buckets, "corpora": corpora}


def _bucket_region(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "us-east-1"
    if text == "EU":
        return "eu-west-1"
    return text


def _build_from_evidence(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    checked_aws: Mapping[str, Any],
    source_spec: Mapping[str, Any],
    repository_root: Path,
    probe_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    root = repository_root.expanduser().resolve(strict=False)
    profile = checked_aws.get("selected_profile")
    region = str(checked_aws.get("effective_region") or "")
    account = str(checked_aws.get("expected_account_id") or "")
    scope = _normalize_scope(
        source_spec,
        selected_profile=str(profile) if profile else None,
        effective_region=region,
        expected_account_id=account,
    )
    evidence = copy.deepcopy(dict(probe_evidence))
    raw_buckets = evidence.get("buckets")
    raw_corpora = evidence.get("corpora")
    if not isinstance(raw_buckets, Mapping) or not isinstance(raw_corpora, Mapping):
        raise V38S3SourceCapabilityRevalidationError(
            "S3 probe evidence must contain bucket and corpus maps"
        )
    blockers: list[str] = []
    bucket_summaries: list[dict[str, Any]] = []
    expected_bucket_ids = {
        f"{row['bucket_owner_account_id']}:{row['bucket']}" for row in scope["corpora"]
    }
    if set(raw_buckets) != expected_bucket_ids:
        raise V38S3SourceCapabilityRevalidationError(
            "S3 bucket probe evidence set differs from the source spec"
        )
    for request_id in sorted(expected_bucket_ids):
        raw = raw_buckets[request_id]
        if not isinstance(raw, Mapping):
            raise V38S3SourceCapabilityRevalidationError(
                f"bucket evidence is not an object: {request_id}"
            )
        location = raw.get("location")
        versioning = raw.get("versioning")
        if not isinstance(location, Mapping) or not isinstance(versioning, Mapping):
            raise V38S3SourceCapabilityRevalidationError(
                f"bucket evidence is incomplete: {request_id}"
            )
        observed_region = None
        if location.get("ok") is not True:
            blockers.append(f"{request_id}:BUCKET_LOCATION_{location.get('error_code')}")
        else:
            response = location.get("response")
            if not isinstance(response, Mapping):
                raise V38S3SourceCapabilityRevalidationError(
                    f"bucket location response is malformed: {request_id}"
                )
            observed_region = _bucket_region(response.get("LocationConstraint"))
            if observed_region != region:
                blockers.append(f"{request_id}:BUCKET_REGION_MISMATCH")
        versioning_status = None
        if versioning.get("ok") is not True:
            blockers.append(f"{request_id}:BUCKET_VERSIONING_{versioning.get('error_code')}")
        else:
            response = versioning.get("response")
            if not isinstance(response, Mapping):
                raise V38S3SourceCapabilityRevalidationError(
                    f"bucket versioning response is malformed: {request_id}"
                )
            versioning_status = str(response.get("Status") or "") or None
            if versioning_status != "Enabled":
                blockers.append(f"{request_id}:BUCKET_VERSIONING_NOT_ENABLED")
        bucket_summaries.append(
            {
                "request_id": request_id,
                "bucket": raw.get("bucket"),
                "bucket_owner_account_id": raw.get("bucket_owner_account_id"),
                "observed_region": observed_region,
                "expected_region": region,
                "versioning_status": versioning_status,
                "bucket_location_accessible": location.get("ok") is True,
                "bucket_versioning_accessible": versioning.get("ok") is True,
                "bucket_versioning_enabled": versioning_status == "Enabled",
            }
        )
    expected_corpus_ids = {row["corpus_id"] for row in scope["corpora"]}
    if set(raw_corpora) != expected_corpus_ids:
        raise V38S3SourceCapabilityRevalidationError(
            "S3 corpus probe evidence set differs from the source spec"
        )
    corpus_by_id = {row["corpus_id"]: row for row in scope["corpora"]}
    corpus_summaries: list[dict[str, Any]] = []
    for corpus_id in sorted(expected_corpus_ids):
        corpus = corpus_by_id[corpus_id]
        raw = raw_corpora[corpus_id]
        if not isinstance(raw, Mapping):
            raise V38S3SourceCapabilityRevalidationError(
                f"corpus evidence is not an object: {corpus_id}"
            )
        if (
            raw.get("bucket") != corpus["bucket"]
            or raw.get("prefix") != corpus["prefix"]
            or raw.get("bucket_owner_account_id") != corpus["bucket_owner_account_id"]
            or raw.get("checksum_probe_source_id")
            != corpus["checksum_probe_source"]["source_id"]
            or raw.get("checksum_probe_key") != corpus["checksum_probe_source"]["key"]
        ):
            raise V38S3SourceCapabilityRevalidationError(
                f"corpus probe request differs from source spec: {corpus_id}"
            )
        list_probe = raw.get("prefix_list_object_versions")
        head_probe = raw.get("checksum_head_object")
        if not isinstance(list_probe, Mapping) or not isinstance(head_probe, Mapping):
            raise V38S3SourceCapabilityRevalidationError(
                f"corpus probe evidence is incomplete: {corpus_id}"
            )
        prefix_accessible = list_probe.get("ok") is True
        if not prefix_accessible:
            blockers.append(
                f"{corpus_id}:LIST_OBJECT_VERSIONS_{list_probe.get('error_code')}"
            )
        else:
            list_response = list_probe.get("response")
            if not isinstance(list_response, Mapping):
                raise V38S3SourceCapabilityRevalidationError(
                    f"list-object-versions response is malformed: {corpus_id}"
                )
            if list_response.get("Name") not in (None, corpus["bucket"]):
                blockers.append(f"{corpus_id}:LIST_RESPONSE_BUCKET_MISMATCH")
            if list_response.get("Prefix") not in (None, corpus["prefix"]):
                blockers.append(f"{corpus_id}:LIST_RESPONSE_PREFIX_MISMATCH")
        checksum_accessible = head_probe.get("ok") is True
        normalized_head: dict[str, Any] | None = None
        if not checksum_accessible:
            blockers.append(f"{corpus_id}:HEAD_OBJECT_{head_probe.get('error_code')}")
        else:
            head_response = head_probe.get("response")
            if not isinstance(head_response, Mapping):
                raise V38S3SourceCapabilityRevalidationError(
                    f"head-object response is malformed: {corpus_id}"
                )
            try:
                normalized_head = capture._normalize_head_response(
                    head_response,
                    source_id=corpus["checksum_probe_source"]["source_id"],
                )
            except Exception as error:
                blockers.append(f"{corpus_id}:HEAD_OBJECT_METADATA_INVALID")
                normalized_head = {"normalization_error": type(error).__name__}
            if normalized_head is not None and "normalization_error" not in normalized_head:
                for blocker in normalized_head.get("blockers") or []:
                    blockers.append(str(blocker))
                if normalized_head.get("delete_marker") is True:
                    blockers.append(f"{corpus_id}:CHECKSUM_PROBE_IS_DELETE_MARKER")
                version_id = str(normalized_head.get("version_id") or "")
                if not version_id or version_id == "null":
                    blockers.append(f"{corpus_id}:CHECKSUM_PROBE_VERSION_ID_MISSING")
        corpus_summaries.append(
            {
                "corpus_id": corpus_id,
                "lane": corpus["lane"],
                "bucket": corpus["bucket"],
                "prefix": corpus["prefix"],
                "bucket_owner_account_id": corpus["bucket_owner_account_id"],
                "declared_source_count": corpus["source_count"],
                "checksum_probe_source_id": corpus["checksum_probe_source"]["source_id"],
                "checksum_probe_key": corpus["checksum_probe_source"]["key"],
                "required_prefix_list_object_versions_accessible": prefix_accessible,
                "checksum_enabled_head_object_accessible": checksum_accessible,
                "checksum_probe_head": normalized_head,
                "identity_from_s3_keys_inferred": False,
            }
        )
    blockers = sorted(set(blockers))
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": READY if not blockers else BLOCKED,
        "repository_root": str(root),
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "pipeline_arm_receipt_fingerprint": arm_receipt.get("fingerprint"),
        "aws_execution_context_revalidation_receipt": copy.deepcopy(dict(checked_aws)),
        "aws_execution_context_revalidation_fingerprint": checked_aws.get("fingerprint"),
        "source_spec": copy.deepcopy(dict(source_spec)),
        "source_spec_fingerprint": _fp(source_spec),
        "normalized_source_scope": scope,
        "normalized_source_scope_fingerprint": _fp(scope),
        "probe_evidence": evidence,
        "probe_evidence_fingerprint": _fp(evidence),
        "bucket_capability_summaries": bucket_summaries,
        "bucket_capability_summaries_fingerprint": _fp(bucket_summaries),
        "corpus_capability_summaries": corpus_summaries,
        "corpus_capability_summaries_fingerprint": _fp(corpus_summaries),
        "blockers": blockers,
        "source_spec_derived_only": True,
        "control_plane_and_checksum_metadata_only": True,
        "required_bucket_locations_verified": not any(
            "BUCKET_LOCATION" in blocker or "BUCKET_REGION" in blocker for blocker in blockers
        ),
        "required_bucket_versioning_enabled_verified": not any(
            "BUCKET_VERSIONING" in blocker for blocker in blockers
        ),
        "required_prefix_list_object_versions_access_verified": not any(
            "LIST_OBJECT_VERSIONS" in blocker or "LIST_RESPONSE" in blocker
            for blocker in blockers
        ),
        "checksum_enabled_head_object_access_verified": not any(
            "HEAD_OBJECT" in blocker
            or "S3_SHA256" in blocker
            or "S3_CHECKSUM" in blocker
            or "CHECKSUM_PROBE" in blocker
            for blocker in blockers
        ),
        "all_declared_objects_verified": False,
        "corpus_completeness_claimed": False,
        "identity_from_s3_keys_inferred": False,
        "configuration_and_metadata_only": True,
        "corpus_files_opened": False,
        "outcome_files_opened": False,
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_g16_blind_prior": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": (
            "RUN_BRANCH_GUARDED_FIRST_BLOCKING_STAGE"
            if not blockers
            else "REPAIR_S3_SOURCE_CAPABILITY_BLOCKERS_AND_STAND_DOWN"
        ),
    }
    result["fingerprint"] = _fp(result)
    return result


def build_gate(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    aws_execution_context_receipt: Mapping[str, Any],
    source_spec: Mapping[str, Any],
    repository_root: Path,
    *,
    expected_account_id: str,
    expected_region: str,
    environment: Mapping[str, str] | None = None,
    command_runner: Callable[[Sequence[str], float], Mapping[str, Any]] = _default_command_runner,
    allow_custom_endpoint_urls: bool = False,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    root = repository_root.expanduser().resolve(strict=False)
    try:
        checked_aws = aws_gate.validate_gate(
            aws_execution_context_receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            repository_root=root,
            expected_account_id=expected_account_id,
            expected_region=expected_region,
            environment=environment,
            command_runner=command_runner,
            allow_custom_endpoint_urls=allow_custom_endpoint_urls,
            verify_runtime=True,
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        raise V38S3SourceCapabilityRevalidationError(
            f"AWS execution-context receipt is invalid: {error}"
        ) from error
    external = checked_aws.get("external_runtime_revalidation_receipt")
    if not isinstance(external, Mapping):
        raise V38S3SourceCapabilityRevalidationError(
            "AWS execution-context receipt lacks external-runtime evidence"
        )
    aws_path = aws_gate._aws_path(external)
    scope = _normalize_scope(
        source_spec,
        selected_profile=(
            str(checked_aws.get("selected_profile"))
            if checked_aws.get("selected_profile")
            else None
        ),
        effective_region=str(checked_aws.get("effective_region") or ""),
        expected_account_id=str(checked_aws.get("expected_account_id") or ""),
    )
    evidence = _collect_probe_evidence(
        scope,
        aws_path=aws_path,
        command_runner=command_runner,
        timeout_seconds=timeout_seconds,
    )
    result = _build_from_evidence(
        plan,
        arm_receipt,
        checked_aws,
        source_spec,
        root,
        evidence,
    )
    validate_gate(
        result,
        plan=plan,
        arm_receipt=arm_receipt,
        source_spec=source_spec,
        repository_root=root,
        expected_account_id=expected_account_id,
        expected_region=expected_region,
        environment=environment,
        command_runner=command_runner,
        allow_custom_endpoint_urls=allow_custom_endpoint_urls,
        require_ready=False,
        verify_runtime=False,
        timeout_seconds=timeout_seconds,
    )
    return result


def validate_gate(
    value: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    source_spec: Mapping[str, Any],
    repository_root: Path | None = None,
    expected_account_id: str | None = None,
    expected_region: str | None = None,
    environment: Mapping[str, str] | None = None,
    command_runner: Callable[[Sequence[str], float], Mapping[str, Any]] = _default_command_runner,
    allow_custom_endpoint_urls: bool = False,
    require_ready: bool = True,
    verify_runtime: bool = True,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise V38S3SourceCapabilityRevalidationError(
            "S3 source-capability receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked)
    root = (
        repository_root.expanduser().resolve(strict=False)
        if repository_root is not None
        else Path(str(checked.get("repository_root") or "")).expanduser().resolve(strict=False)
    )
    if str(root) != checked.get("repository_root"):
        raise V38S3SourceCapabilityRevalidationError("repository root mismatch")
    embedded_aws = checked.get("aws_execution_context_revalidation_receipt")
    if not isinstance(embedded_aws, Mapping):
        raise V38S3SourceCapabilityRevalidationError(
            "embedded AWS execution-context receipt is missing"
        )
    account = str(
        expected_account_id or embedded_aws.get("expected_account_id") or ""
    )
    region = str(expected_region or embedded_aws.get("expected_region") or "")
    try:
        validated_aws = aws_gate.validate_gate(
            embedded_aws,
            plan=plan,
            arm_receipt=arm_receipt,
            repository_root=root,
            expected_account_id=account,
            expected_region=region,
            environment=environment,
            command_runner=command_runner,
            allow_custom_endpoint_urls=allow_custom_endpoint_urls,
            verify_runtime=verify_runtime,
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        raise V38S3SourceCapabilityRevalidationError(
            f"embedded AWS execution-context receipt is invalid: {error}"
        ) from error
    expected_pairs = {
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "pipeline_arm_receipt_fingerprint": arm_receipt.get("fingerprint"),
        "aws_execution_context_revalidation_fingerprint": validated_aws.get("fingerprint"),
        "source_spec_fingerprint": _fp(source_spec),
    }
    for field, expected_value in expected_pairs.items():
        if checked.get(field) != expected_value:
            raise V38S3SourceCapabilityRevalidationError(f"field mismatch: {field}")
    if checked.get("source_spec") != dict(source_spec):
        raise V38S3SourceCapabilityRevalidationError("embedded source spec mismatch")
    for field, fingerprint_field in (
        ("normalized_source_scope", "normalized_source_scope_fingerprint"),
        ("probe_evidence", "probe_evidence_fingerprint"),
        ("bucket_capability_summaries", "bucket_capability_summaries_fingerprint"),
        ("corpus_capability_summaries", "corpus_capability_summaries_fingerprint"),
    ):
        if checked.get(fingerprint_field) != _fp(checked.get(field)):
            raise V38S3SourceCapabilityRevalidationError(
                f"evidence fingerprint mismatch: {field}"
            )
    rebuilt = _build_from_evidence(
        plan,
        arm_receipt,
        validated_aws,
        source_spec,
        root,
        checked.get("probe_evidence") or {},
    )
    if rebuilt != dict(value):
        raise V38S3SourceCapabilityRevalidationError(
            "S3 source-capability receipt differs from deterministic evidence rebuild"
        )
    if require_ready and checked.get("status") != READY:
        raise V38S3SourceCapabilityRevalidationError(
            "S3 source-capability revalidation is blocked"
        )
    if verify_runtime:
        runtime = build_gate(
            plan,
            arm_receipt,
            embedded_aws,
            source_spec,
            root,
            expected_account_id=account,
            expected_region=region,
            environment=environment,
            command_runner=command_runner,
            allow_custom_endpoint_urls=allow_custom_endpoint_urls,
            timeout_seconds=timeout_seconds,
        )
        if runtime != dict(value):
            raise V38S3SourceCapabilityRevalidationError(
                "S3 source-capability receipt differs from current deterministic reconstruction"
            )
    return copy.deepcopy(dict(value))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--arm-receipt", type=Path, required=True)
    parser.add_argument("--aws-execution-context-revalidation", type=Path, required=True)
    parser.add_argument("--source-spec", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--expected-account-id", required=True)
    parser.add_argument("--expected-region", required=True)
    parser.add_argument("--allow-custom-endpoint-url", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    args = parser.parse_args(argv)
    receipt = build_gate(
        _load(args.plan),
        _load(args.arm_receipt),
        _load(args.aws_execution_context_revalidation),
        _load(args.source_spec),
        args.repository_root,
        expected_account_id=args.expected_account_id,
        expected_region=args.expected_region,
        allow_custom_endpoint_urls=args.allow_custom_endpoint_url,
        timeout_seconds=args.timeout_seconds,
    )
    _write(args.out, receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "blockers": receipt["blockers"],
                "fingerprint": receipt["fingerprint"],
            },
            sort_keys=True,
        )
    )
    return 0 if receipt["status"] == READY else 2


if __name__ == "__main__":
    raise SystemExit(main())
