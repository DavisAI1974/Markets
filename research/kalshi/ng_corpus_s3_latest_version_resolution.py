#!/usr/bin/env python3
"""Resolve exact latest S3 version IDs for explicitly identified NG corpus objects.

This stage removes the circular requirement that an operator already know every S3
version ID before capturing the inventory. Trading identity is still never inferred
from object keys: day, lane, publisher, materialization path, and observed definition
must be supplied explicitly. Only the latest non-delete version ID for each declared
key is resolved from a complete ``list-object-versions`` response.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_corpus_coverage_audit as coverage
import ng_corpus_s3_inventory_capture as capture

SPEC_SCHEMA = "ng_corpus_s3_latest_version_resolution_spec.v1"
RECEIPT_SCHEMA = "ng_corpus_s3_latest_version_resolution_attestation.v1"
READY_STATUS = "S3_LATEST_VERSIONS_RESOLVED_READY_FOR_CAPTURE"
BLOCKED_STATUS = "S3_LATEST_VERSION_RESOLUTION_BLOCKED"


class CorpusS3LatestVersionResolutionError(ValueError):
    """Raised when latest-version evidence is malformed, ambiguous, or unsafe."""


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusS3LatestVersionResolutionError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusS3LatestVersionResolutionError(
            f"JSON artifact must be an object: {path}"
        )
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _authority_fields() -> dict[str, Any]:
    return {
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    for field, expected in _authority_fields().items():
        if value.get(field) != expected:
            raise CorpusS3LatestVersionResolutionError(
                f"{label}: {field} must remain {expected!r}"
            )


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise CorpusS3LatestVersionResolutionError(
            f"{label} must be a positive integer"
        )
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CorpusS3LatestVersionResolutionError(
            f"{label} must be a positive integer"
        ) from error
    if number <= 0:
        raise CorpusS3LatestVersionResolutionError(
            f"{label} must be a positive integer"
        )
    return number


def _normalize_list_response(
    value: Mapping[str, Any], *, corpus_id: str
) -> dict[str, Any]:
    try:
        return capture._normalize_list_response(value, corpus_id=corpus_id)
    except Exception as error:
        raise CorpusS3LatestVersionResolutionError(
            f"{corpus_id}: invalid list-object-versions response: {error}"
        ) from error


def _build_from_evidence(
    source_spec: Mapping[str, Any],
    *,
    list_responses: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = copy.deepcopy(dict(source_spec))
    if spec.get("schema") != SPEC_SCHEMA:
        raise CorpusS3LatestVersionResolutionError(
            f"resolution spec schema must be {SPEC_SCHEMA}"
        )
    _authority(spec, label="resolution spec")
    observed_at = str(spec.get("inventory_observed_at") or "")
    if not observed_at:
        raise CorpusS3LatestVersionResolutionError(
            "inventory_observed_at is required"
        )
    allowed_roots = list(spec.get("allowed_roots") or [])
    if not allowed_roots:
        raise CorpusS3LatestVersionResolutionError(
            "resolution spec requires allowed_roots"
        )
    corpora = list(spec.get("corpora") or [])
    if len(corpora) != len(coverage.EXPECTED_WINDOWS):
        raise CorpusS3LatestVersionResolutionError(
            "resolution spec must contain both canonical corpora"
        )

    blockers: list[str] = []
    normalized_lists: dict[str, dict[str, Any]] = {}
    resolved_corpora: list[dict[str, Any]] = []
    resolutions: list[dict[str, Any]] = []
    seen_corpora: set[str] = set()
    seen_sources: set[str] = set()

    for raw_corpus in corpora:
        if not isinstance(raw_corpus, Mapping):
            raise CorpusS3LatestVersionResolutionError(
                "resolution corpus is not an object"
            )
        corpus = copy.deepcopy(dict(raw_corpus))
        corpus_id = str(corpus.get("corpus_id") or "")
        expected = coverage.EXPECTED_WINDOWS.get(corpus_id)
        if expected is None or corpus_id in seen_corpora:
            raise CorpusS3LatestVersionResolutionError(
                f"unexpected or duplicate corpus_id {corpus_id!r}"
            )
        seen_corpora.add(corpus_id)
        lane = str(corpus.get("lane") or "")
        if lane != expected["lane"]:
            raise CorpusS3LatestVersionResolutionError(
                f"{corpus_id}: lane mismatch"
            )
        bucket = str(corpus.get("bucket") or "").strip()
        prefix = str(corpus.get("prefix") or "")
        if (
            not bucket
            or "://" in bucket
            or bucket.startswith("/")
            or prefix.startswith("/")
        ):
            raise CorpusS3LatestVersionResolutionError(
                f"{corpus_id}: invalid bucket or prefix"
            )
        publisher_id = _positive_int(
            corpus.get("publisher_id"), label=f"{corpus_id}:publisher_id"
        )
        list_raw = list_responses.get(corpus_id)
        if not isinstance(list_raw, Mapping):
            raise CorpusS3LatestVersionResolutionError(
                f"{corpus_id}: list-object-versions evidence missing"
            )
        listed = _normalize_list_response(list_raw, corpus_id=corpus_id)
        normalized_lists[corpus_id] = listed
        if listed["is_truncated"]:
            blockers.append(f"{corpus_id}:S3_VERSION_LIST_TRUNCATED")

        latest_deletes = {
            row["key"] for row in listed["delete_markers"] if row["is_latest"]
        }
        latest_by_key: dict[str, list[dict[str, Any]]] = {}
        for row in listed["versions"]:
            if row["is_latest"]:
                latest_by_key.setdefault(row["key"], []).append(row)

        sources = list(corpus.get("sources") or [])
        declared_keys: set[str] = set()
        resolved_sources: list[dict[str, Any]] = []
        for raw_source in sources:
            if not isinstance(raw_source, Mapping):
                raise CorpusS3LatestVersionResolutionError(
                    f"{corpus_id}: source is not an object"
                )
            source = copy.deepcopy(dict(raw_source))
            source_id = str(source.get("source_id") or "")
            if not source_id or source_id in seen_sources:
                raise CorpusS3LatestVersionResolutionError(
                    f"duplicate or missing source_id {source_id!r}"
                )
            seen_sources.add(source_id)
            if source.get("lane") != lane:
                raise CorpusS3LatestVersionResolutionError(
                    f"{source_id}: explicit lane mismatch"
                )
            day = str(source.get("day") or "")
            if not day:
                raise CorpusS3LatestVersionResolutionError(
                    f"{source_id}: explicit day is required"
                )
            key = str(source.get("key") or "")
            if not key or not key.startswith(prefix):
                raise CorpusS3LatestVersionResolutionError(
                    f"{source_id}: exact key under corpus prefix is required"
                )
            if source.get("version_id") not in (None, ""):
                raise CorpusS3LatestVersionResolutionError(
                    f"{source_id}: version_id must be absent before resolution"
                )
            if key in declared_keys:
                raise CorpusS3LatestVersionResolutionError(
                    f"{source_id}: duplicate declared key {key!r}"
                )
            declared_keys.add(key)

            candidates = latest_by_key.get(key, [])
            delete_marker = key in latest_deletes
            source_blockers: list[str] = []
            if delete_marker:
                source_blockers.append("LATEST_OBJECT_IS_DELETE_MARKER")
            if len(candidates) == 0:
                source_blockers.append("LATEST_VERSION_NOT_FOUND")
            elif len(candidates) > 1:
                source_blockers.append("LATEST_VERSION_AMBIGUOUS")

            resolved = copy.deepcopy(source)
            version_id: str | None = None
            if len(candidates) == 1 and not delete_marker:
                version_id = candidates[0]["version_id"]
                resolved["version_id"] = version_id
            else:
                resolved["version_id"] = None
            for blocker in source_blockers:
                blockers.append(f"{source_id}:{blocker}")
            resolutions.append(
                {
                    "source_id": source_id,
                    "corpus_id": corpus_id,
                    "day": day,
                    "lane": lane,
                    "bucket": bucket,
                    "key": key,
                    "resolved_version_id": version_id,
                    "candidate_latest_version_ids": sorted(
                        row["version_id"] for row in candidates
                    ),
                    "latest_delete_marker": delete_marker,
                    "blockers": sorted(source_blockers),
                    "identity_from_key_inferred": False,
                }
            )
            resolved_sources.append(resolved)

        for key in sorted(set(latest_by_key) - declared_keys):
            for row in latest_by_key[key]:
                blockers.append(
                    f"{corpus_id}:UNDECLARED_LATEST_OBJECT:{key}:{row['version_id']}"
                )
        for key in sorted(latest_deletes - declared_keys):
            blockers.append(f"{corpus_id}:UNDECLARED_LATEST_DELETE_MARKER:{key}")

        resolved_corpora.append(
            {
                "corpus_id": corpus_id,
                "lane": lane,
                "publisher_id": publisher_id,
                "bucket": bucket,
                "prefix": prefix,
                "expected_days": copy.deepcopy(
                    list(corpus.get("expected_days") or [])
                ),
                "expected_object_count": corpus.get("expected_object_count"),
                "inventory_scope_verified": (
                    corpus.get("inventory_scope_verified") is True
                ),
                "inventory_complete_asserted": (
                    corpus.get("inventory_complete_asserted") is True
                ),
                "inventory_observed_at": str(
                    corpus.get("inventory_observed_at") or observed_at
                ),
                "sources": sorted(
                    resolved_sources, key=lambda row: str(row.get("source_id") or "")
                ),
            }
        )

    if seen_corpora != set(coverage.EXPECTED_WINDOWS):
        raise CorpusS3LatestVersionResolutionError(
            "resolution spec is missing a canonical corpus"
        )

    blockers = sorted(set(blockers))
    capture_spec = {
        "schema": capture.SPEC_SCHEMA,
        "allowed_roots": copy.deepcopy(allowed_roots),
        "inventory_observed_at": observed_at,
        "corpora": sorted(resolved_corpora, key=lambda row: row["corpus_id"]),
        **_authority_fields(),
    }
    for optional in ("aws_profile", "aws_region"):
        if spec.get(optional) not in (None, ""):
            capture_spec[optional] = spec[optional]

    evidence = {"list_object_versions": copy.deepcopy(dict(list_responses))}
    normalized = {"list_object_versions": normalized_lists}
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "status": READY_STATUS if not blockers else BLOCKED_STATUS,
        "source_spec": spec,
        "source_spec_fingerprint": _fp(spec),
        "captured_list_evidence": evidence,
        "captured_list_evidence_fingerprint": _fp(evidence),
        "normalized_list_evidence": normalized,
        "normalized_list_evidence_fingerprint": _fp(normalized),
        "resolutions": sorted(resolutions, key=lambda row: row["source_id"]),
        "resolutions_fingerprint": _fp(
            sorted(resolutions, key=lambda row: row["source_id"])
        ),
        "capture_spec": capture_spec,
        "capture_spec_fingerprint": _fp(capture_spec),
        "blockers": blockers,
        "identity_from_s3_keys_inferred": False,
        "next_action": (
            "RUN_EXACT_S3_INVENTORY_CAPTURE"
            if not blockers
            else "RESOLVE_S3_LATEST_VERSION_BLOCKERS"
        ),
        **_authority_fields(),
    }
    receipt["receipt_fingerprint"] = _fp(receipt)
    return capture_spec, receipt


def validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("receipt_fingerprint", None)
    if checked.get("schema") != RECEIPT_SCHEMA or observed != _fp(checked):
        raise CorpusS3LatestVersionResolutionError(
            "resolution receipt schema or fingerprint mismatch"
        )
    checked["receipt_fingerprint"] = observed
    _authority(checked, label="resolution receipt")
    if checked.get("identity_from_s3_keys_inferred") is not False:
        raise CorpusS3LatestVersionResolutionError(
            "trading identity may not be inferred from S3 keys"
        )
    spec = checked.get("source_spec")
    evidence = checked.get("captured_list_evidence")
    if not isinstance(spec, Mapping) or not isinstance(evidence, Mapping):
        raise CorpusS3LatestVersionResolutionError(
            "resolution receipt is missing embedded evidence"
        )
    if checked.get("source_spec_fingerprint") != _fp(spec):
        raise CorpusS3LatestVersionResolutionError(
            "resolution source spec fingerprint mismatch"
        )
    if checked.get("captured_list_evidence_fingerprint") != _fp(evidence):
        raise CorpusS3LatestVersionResolutionError(
            "resolution list evidence fingerprint mismatch"
        )
    normalized = checked.get("normalized_list_evidence")
    if (
        not isinstance(normalized, Mapping)
        or checked.get("normalized_list_evidence_fingerprint") != _fp(normalized)
    ):
        raise CorpusS3LatestVersionResolutionError(
            "normalized resolution evidence fingerprint mismatch"
        )
    capture_spec, rebuilt = _build_from_evidence(
        spec,
        list_responses=evidence.get("list_object_versions") or {},
    )
    if capture_spec != checked.get("capture_spec"):
        raise CorpusS3LatestVersionResolutionError(
            "capture spec differs from deterministic rebuild"
        )
    if checked.get("capture_spec_fingerprint") != _fp(capture_spec):
        raise CorpusS3LatestVersionResolutionError(
            "capture spec fingerprint mismatch"
        )
    resolutions = checked.get("resolutions")
    if not isinstance(resolutions, list) or checked.get(
        "resolutions_fingerprint"
    ) != _fp(resolutions):
        raise CorpusS3LatestVersionResolutionError(
            "latest-version resolution fingerprint mismatch"
        )
    if rebuilt != dict(value):
        raise CorpusS3LatestVersionResolutionError(
            "resolution receipt differs from deterministic rebuild"
        )
    return copy.deepcopy(dict(value))


def _run_json(argv: Sequence[str]) -> dict[str, Any]:
    process = subprocess.run(
        list(argv),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process.returncode != 0:
        raise CorpusS3LatestVersionResolutionError(
            f"AWS CLI command failed ({process.returncode}): {' '.join(argv)}: "
            f"{process.stderr.strip()}"
        )
    try:
        value = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise CorpusS3LatestVersionResolutionError(
            f"AWS CLI returned invalid JSON: {' '.join(argv)}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusS3LatestVersionResolutionError(
            "AWS CLI response must be a JSON object"
        )
    return value


def resolve_live(
    source_spec: Mapping[str, Any],
    *,
    aws_executable: str = "aws",
    runner: Callable[[Sequence[str]], dict[str, Any]] = _run_json,
) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = copy.deepcopy(dict(source_spec))
    global_args: list[str] = [aws_executable]
    profile = str(spec.get("aws_profile") or "")
    region = str(spec.get("aws_region") or "")
    if profile:
        global_args.extend(["--profile", profile])
    if region:
        global_args.extend(["--region", region])
    list_responses: dict[str, Mapping[str, Any]] = {}
    for corpus in spec.get("corpora") or []:
        corpus_id = str(corpus.get("corpus_id") or "")
        list_responses[corpus_id] = runner(
            [
                *global_args,
                "s3api",
                "list-object-versions",
                "--bucket",
                str(corpus.get("bucket") or ""),
                "--prefix",
                str(corpus.get("prefix") or ""),
                "--output",
                "json",
            ]
        )
    return _build_from_evidence(spec, list_responses=list_responses)


def selftest() -> int:
    spec = {
        "schema": SPEC_SCHEMA,
        "allowed_roots": ["data"],
        "inventory_observed_at": "2026-07-25T00:00:00Z",
        "corpora": [],
        **_authority_fields(),
    }
    responses: dict[str, Mapping[str, Any]] = {}
    for corpus_id, expected in coverage.EXPECTED_WINDOWS.items():
        source_id = f"{corpus_id}-source"
        key = f"ng/{corpus_id}/source.dbn"
        spec["corpora"].append(
            {
                "corpus_id": corpus_id,
                "lane": expected["lane"],
                "publisher_id": 1,
                "bucket": "selftest-bucket",
                "prefix": f"ng/{corpus_id}/",
                "expected_days": ["20260315"],
                "expected_object_count": 1,
                "inventory_scope_verified": True,
                "inventory_complete_asserted": True,
                "sources": [
                    {
                        "source_id": source_id,
                        "day": "20260315",
                        "lane": expected["lane"],
                        "key": key,
                        "materialized_path": f"data/{source_id}.dbn",
                        "definition": {"placeholder": True},
                    }
                ],
            }
        )
        responses[corpus_id] = {
            "Versions": [
                {
                    "Key": key,
                    "VersionId": "v1",
                    "IsLatest": True,
                    "LastModified": "2026-07-25T00:00:00Z",
                    "Size": 8,
                    "ETag": source_id,
                }
            ]
        }
    capture_spec, receipt = _build_from_evidence(spec, list_responses=responses)
    assert receipt["status"] == READY_STATUS
    assert all(
        source["version_id"] == "v1"
        for corpus in capture_spec["corpora"]
        for source in corpus["sources"]
    )
    validate_receipt(receipt)
    tampered = copy.deepcopy(receipt)
    tampered["options_lane_started"] = True
    tampered["receipt_fingerprint"] = _fp(
        {key: item for key, item in tampered.items() if key != "receipt_fingerprint"}
    )
    try:
        validate_receipt(tampered)
    except CorpusS3LatestVersionResolutionError:
        print("[ng_corpus_s3_latest_version_resolution] selftest PASS")
        return 0
    raise AssertionError("authority escalation was accepted")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    resolve_parser = subparsers.add_parser("resolve")
    resolve_parser.add_argument("--spec", type=Path, required=True)
    resolve_parser.add_argument("--capture-spec-out", type=Path, required=True)
    resolve_parser.add_argument("--receipt-out", type=Path, required=True)
    resolve_parser.add_argument("--aws-executable", default="aws")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--receipt", type=Path, required=True)
    subparsers.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.command == "selftest":
        return selftest()
    if args.command == "validate":
        receipt = validate_receipt(_load(args.receipt))
        print(json.dumps({"status": receipt["status"]}, sort_keys=True))
        return 0
    capture_spec, receipt = resolve_live(
        _load(args.spec), aws_executable=args.aws_executable
    )
    _write(args.receipt_out, receipt)
    if receipt["status"] != READY_STATUS:
        print(
            json.dumps(
                {"status": receipt["status"], "blockers": receipt["blockers"]},
                sort_keys=True,
            )
        )
        return 2
    _write(args.capture_spec_out, capture_spec)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "capture_spec": str(args.capture_spec_out),
                "receipt": str(args.receipt_out),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
