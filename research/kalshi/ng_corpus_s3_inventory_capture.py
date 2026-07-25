#!/usr/bin/env python3
"""Capture an exact S3 inventory and compile the materialization specification.

The stage queries S3 directly through the AWS CLI, but never infers trading identity
from object keys. Days, lanes, publisher identity, local materialization paths, and
observed definitions must be supplied explicitly. Dedicated corpus prefixes are
verified against the complete set of latest non-delete objects, and every selected
object must expose an exact SHA-256 through S3 checksum metadata or explicit object
metadata before the downstream materialization attestation may run.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_corpus_coverage_audit as coverage

SPEC_SCHEMA = "ng_corpus_s3_inventory_capture_spec.v1"
MATERIALIZATION_SCHEMA = "ng_corpus_s3_materialization_spec.v1"
RECEIPT_SCHEMA = "ng_corpus_s3_inventory_capture_attestation.v1"
READY_STATUS = "S3_INVENTORY_CAPTURED_READY_FOR_MATERIALIZATION"
BLOCKED_STATUS = "S3_INVENTORY_CAPTURE_BLOCKED"


class CorpusS3InventoryCaptureError(ValueError):
    """Raised when S3 inventory evidence is malformed or unsafe."""


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
        raise CorpusS3InventoryCaptureError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusS3InventoryCaptureError(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
            raise CorpusS3InventoryCaptureError(
                f"{label}: {field} must remain {expected!r}"
            )


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise CorpusS3InventoryCaptureError(f"{label} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CorpusS3InventoryCaptureError(f"{label} must be a positive integer") from error
    if number <= 0:
        raise CorpusS3InventoryCaptureError(f"{label} must be a positive integer")
    return number


def _hex_sha256(value: Any, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise CorpusS3InventoryCaptureError(
            f"{label} must be a 64-character hexadecimal SHA-256"
        )
    return text


def _checksum_from_head(
    head: Mapping[str, Any], *, source_id: str
) -> tuple[str | None, str | None, list[str]]:
    candidates: list[tuple[str, str]] = []
    native = head.get("ChecksumSHA256")
    if native not in (None, ""):
        try:
            raw = base64.b64decode(str(native), validate=True)
        except Exception:
            return None, None, [f"{source_id}:S3_CHECKSUM_SHA256_INVALID_BASE64"]
        if len(raw) != 32:
            return None, None, [f"{source_id}:S3_CHECKSUM_SHA256_INVALID_LENGTH"]
        candidates.append((raw.hex(), "s3.ChecksumSHA256"))
    metadata = head.get("Metadata")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, Mapping):
        return None, None, [f"{source_id}:S3_METADATA_NOT_OBJECT"]
    lowered = {str(key).lower(): value for key, value in metadata.items()}
    for key in ("sha256", "checksum_sha256", "source_sha256"):
        if lowered.get(key) not in (None, ""):
            try:
                checksum = _hex_sha256(
                    lowered[key], label=f"{source_id}:Metadata.{key}"
                )
            except CorpusS3InventoryCaptureError:
                return None, None, [f"{source_id}:S3_METADATA_SHA256_INVALID"]
            candidates.append((checksum, f"s3.Metadata.{key}"))
    if not candidates:
        return None, None, [f"{source_id}:S3_SHA256_MISSING"]
    values = {checksum for checksum, _ in candidates}
    if len(values) != 1:
        return None, None, [f"{source_id}:S3_SHA256_CONFLICT"]
    checksum = candidates[0][0]
    sources = "+".join(sorted(source for _, source in candidates))
    return checksum, sources, []


def _normalize_list_response(
    value: Mapping[str, Any], *, corpus_id: str
) -> dict[str, Any]:
    versions: list[dict[str, Any]] = []
    for raw in value.get("Versions") or []:
        if not isinstance(raw, Mapping):
            raise CorpusS3InventoryCaptureError(
                f"{corpus_id}: Versions entry is not an object"
            )
        key = str(raw.get("Key") or "")
        version_id = str(raw.get("VersionId") or "")
        if not key or not version_id:
            raise CorpusS3InventoryCaptureError(
                f"{corpus_id}: every listed version requires Key and VersionId"
            )
        versions.append(
            {
                "key": key,
                "version_id": version_id,
                "is_latest": raw.get("IsLatest") is True,
                "last_modified": str(raw.get("LastModified") or ""),
                "size_bytes": _positive_int(
                    raw.get("Size"), label=f"{corpus_id}:{key}:Size"
                ),
                "etag": str(raw.get("ETag") or "").strip().strip('"') or None,
            }
        )
    delete_markers: list[dict[str, Any]] = []
    for raw in value.get("DeleteMarkers") or []:
        if not isinstance(raw, Mapping):
            raise CorpusS3InventoryCaptureError(
                f"{corpus_id}: DeleteMarkers entry is not an object"
            )
        delete_markers.append(
            {
                "key": str(raw.get("Key") or ""),
                "version_id": str(raw.get("VersionId") or ""),
                "is_latest": raw.get("IsLatest") is True,
                "last_modified": str(raw.get("LastModified") or ""),
            }
        )
    return {
        "versions": sorted(versions, key=lambda row: (row["key"], row["version_id"])),
        "delete_markers": sorted(
            delete_markers, key=lambda row: (row["key"], row["version_id"])
        ),
        "is_truncated": value.get("IsTruncated") is True,
        "next_key_marker": value.get("NextKeyMarker"),
        "next_version_id_marker": value.get("NextVersionIdMarker"),
    }


def _normalize_head_response(
    value: Mapping[str, Any], *, source_id: str
) -> dict[str, Any]:
    checksum, checksum_source, blockers = _checksum_from_head(
        value, source_id=source_id
    )
    return {
        "content_length": _positive_int(
            value.get("ContentLength"), label=f"{source_id}:ContentLength"
        ),
        "last_modified": str(value.get("LastModified") or ""),
        "version_id": str(value.get("VersionId") or "") or None,
        "etag": str(value.get("ETag") or "").strip().strip('"') or None,
        "checksum_sha256": checksum,
        "checksum_source": checksum_source,
        "delete_marker": value.get("DeleteMarker") is True,
        "blockers": blockers,
    }


def _build_from_evidence(
    source_spec: Mapping[str, Any],
    *,
    list_responses: Mapping[str, Mapping[str, Any]],
    head_responses: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = copy.deepcopy(dict(source_spec))
    if spec.get("schema") != SPEC_SCHEMA:
        raise CorpusS3InventoryCaptureError(
            f"capture spec schema must be {SPEC_SCHEMA}"
        )
    _authority(spec, label="capture spec")
    observed_at = str(spec.get("inventory_observed_at") or "")
    if not observed_at:
        raise CorpusS3InventoryCaptureError("inventory_observed_at is required")
    allowed_roots = list(spec.get("allowed_roots") or [])
    if not allowed_roots:
        raise CorpusS3InventoryCaptureError("capture spec requires allowed_roots")
    corpora = list(spec.get("corpora") or [])
    if len(corpora) != len(coverage.EXPECTED_WINDOWS):
        raise CorpusS3InventoryCaptureError(
            "capture spec must contain both canonical corpora"
        )

    blockers: list[str] = []
    normalized_lists: dict[str, dict[str, Any]] = {}
    normalized_heads: dict[str, dict[str, Any]] = {}
    materialization_corpora: list[dict[str, Any]] = []
    seen_corpora: set[str] = set()
    seen_sources: set[str] = set()

    for raw_corpus in corpora:
        if not isinstance(raw_corpus, Mapping):
            raise CorpusS3InventoryCaptureError("capture corpus is not an object")
        corpus = copy.deepcopy(dict(raw_corpus))
        corpus_id = str(corpus.get("corpus_id") or "")
        expected = coverage.EXPECTED_WINDOWS.get(corpus_id)
        if expected is None or corpus_id in seen_corpora:
            raise CorpusS3InventoryCaptureError(
                f"unexpected or duplicate corpus_id {corpus_id!r}"
            )
        seen_corpora.add(corpus_id)
        lane = str(corpus.get("lane") or "")
        if lane != expected["lane"]:
            raise CorpusS3InventoryCaptureError(f"{corpus_id}: lane mismatch")
        bucket = str(corpus.get("bucket") or "").strip()
        prefix = str(corpus.get("prefix") or "")
        if (
            not bucket
            or "://" in bucket
            or bucket.startswith("/")
            or prefix.startswith("/")
        ):
            raise CorpusS3InventoryCaptureError(
                f"{corpus_id}: invalid bucket or prefix"
            )
        publisher_id = _positive_int(
            corpus.get("publisher_id"), label=f"{corpus_id}:publisher_id"
        )
        list_raw = list_responses.get(corpus_id)
        if not isinstance(list_raw, Mapping):
            raise CorpusS3InventoryCaptureError(
                f"{corpus_id}: list-object-versions evidence missing"
            )
        listed = _normalize_list_response(list_raw, corpus_id=corpus_id)
        normalized_lists[corpus_id] = listed
        if listed["is_truncated"]:
            blockers.append(f"{corpus_id}:S3_VERSION_LIST_TRUNCATED")
        latest_deletes = {
            row["key"] for row in listed["delete_markers"] if row["is_latest"]
        }
        for key in sorted(latest_deletes):
            blockers.append(f"{corpus_id}:LATEST_DELETE_MARKER:{key}")
        latest_versions = {
            (row["key"], row["version_id"]): row
            for row in listed["versions"]
            if row["is_latest"]
        }
        sources = list(corpus.get("sources") or [])
        declared_pairs: set[tuple[str, str]] = set()
        materialization_sources: list[dict[str, Any]] = []
        for raw_source in sources:
            if not isinstance(raw_source, Mapping):
                raise CorpusS3InventoryCaptureError(
                    f"{corpus_id}: source is not an object"
                )
            source = copy.deepcopy(dict(raw_source))
            source_id = str(source.get("source_id") or "")
            if not source_id or source_id in seen_sources:
                raise CorpusS3InventoryCaptureError(
                    f"duplicate or missing source_id {source_id!r}"
                )
            seen_sources.add(source_id)
            if source.get("lane") != lane:
                raise CorpusS3InventoryCaptureError(
                    f"{source_id}: explicit lane mismatch"
                )
            day = str(source.get("day") or "")
            if not day:
                raise CorpusS3InventoryCaptureError(
                    f"{source_id}: explicit day is required"
                )
            key = str(source.get("key") or "")
            version_id = str(source.get("version_id") or "")
            if not key or not version_id or not key.startswith(prefix):
                raise CorpusS3InventoryCaptureError(
                    f"{source_id}: exact key and version_id under corpus prefix are required"
                )
            pair = (key, version_id)
            if pair in declared_pairs:
                raise CorpusS3InventoryCaptureError(
                    f"{source_id}: duplicate exact object identity"
                )
            declared_pairs.add(pair)
            listed_row = latest_versions.get(pair)
            if listed_row is None:
                blockers.append(f"{source_id}:EXACT_LATEST_VERSION_NOT_LISTED")
            head_raw = head_responses.get(source_id)
            if not isinstance(head_raw, Mapping):
                raise CorpusS3InventoryCaptureError(
                    f"{source_id}: head-object evidence missing"
                )
            head = _normalize_head_response(head_raw, source_id=source_id)
            normalized_heads[source_id] = head
            blockers.extend(head["blockers"])
            if head["delete_marker"]:
                blockers.append(f"{source_id}:HEAD_OBJECT_IS_DELETE_MARKER")
            if head["version_id"] != version_id:
                blockers.append(f"{source_id}:HEAD_VERSION_ID_MISMATCH")
            if listed_row is not None:
                if head["content_length"] != listed_row["size_bytes"]:
                    blockers.append(f"{source_id}:LIST_HEAD_SIZE_MISMATCH")
                if (
                    head["etag"]
                    and listed_row["etag"]
                    and head["etag"] != listed_row["etag"]
                ):
                    blockers.append(f"{source_id}:LIST_HEAD_ETAG_MISMATCH")
            expected_sha = source.get("expected_checksum_sha256")
            if expected_sha not in (None, ""):
                expected_hex = _hex_sha256(
                    expected_sha, label=f"{source_id}:expected_checksum_sha256"
                )
                if head["checksum_sha256"] != expected_hex:
                    blockers.append(f"{source_id}:EXPECTED_SHA256_MISMATCH")
            if not head["last_modified"]:
                blockers.append(f"{source_id}:HEAD_LAST_MODIFIED_MISSING")
            s3_object = {
                "bucket": bucket,
                "key": key,
                "version_id": version_id,
                "etag": head["etag"],
                "last_modified": head["last_modified"],
                "size_bytes": head["content_length"],
                "checksum_sha256": head["checksum_sha256"],
                "checksum_source": head["checksum_source"],
            }
            materialization_source = {
                "source_id": source_id,
                "day": day,
                "lane": lane,
                "materialized_path": source.get("materialized_path"),
                "s3_object": s3_object,
                "skip_nonmatching": source.get("skip_nonmatching") is True,
            }
            if source.get("definition") not in (None, ""):
                materialization_source["definition"] = copy.deepcopy(
                    source["definition"]
                )
            if source.get("definition_path") not in (None, ""):
                materialization_source["definition_path"] = source[
                    "definition_path"
                ]
            if source.get("definition_sha256") not in (None, ""):
                materialization_source["definition_sha256"] = source[
                    "definition_sha256"
                ]
            materialization_sources.append(materialization_source)
        undeclared = sorted(set(latest_versions) - declared_pairs)
        for key, version_id in undeclared:
            blockers.append(
                f"{corpus_id}:UNDECLARED_LATEST_OBJECT:{key}:{version_id}"
            )
        materialization_corpora.append(
            {
                "corpus_id": corpus_id,
                "lane": lane,
                "publisher_id": publisher_id,
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
                    materialization_sources, key=lambda row: row["source_id"]
                ),
            }
        )
    if seen_corpora != set(coverage.EXPECTED_WINDOWS):
        raise CorpusS3InventoryCaptureError(
            "capture spec is missing a canonical corpus"
        )
    blockers = sorted(set(blockers))
    materialization_spec = {
        "schema": MATERIALIZATION_SCHEMA,
        "allowed_roots": copy.deepcopy(allowed_roots),
        "inventory_observed_at": observed_at,
        "corpora": sorted(
            materialization_corpora, key=lambda row: row["corpus_id"]
        ),
        **_authority_fields(),
    }
    evidence = {
        "list_object_versions": copy.deepcopy(dict(list_responses)),
        "head_objects": copy.deepcopy(dict(head_responses)),
    }
    normalized_inventory = {
        "list_object_versions": normalized_lists,
        "head_objects": normalized_heads,
    }
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "status": READY_STATUS if not blockers else BLOCKED_STATUS,
        "source_spec": spec,
        "source_spec_fingerprint": _fp(spec),
        "captured_inventory": evidence,
        "captured_inventory_fingerprint": _fp(evidence),
        "normalized_inventory": normalized_inventory,
        "normalized_inventory_fingerprint": _fp(normalized_inventory),
        "materialization_spec": materialization_spec,
        "materialization_spec_fingerprint": _fp(materialization_spec),
        "blockers": blockers,
        "next_action": (
            "RUN_S3_MATERIALIZATION_ATTESTATION"
            if not blockers
            else "RESOLVE_S3_INVENTORY_CAPTURE_BLOCKERS"
        ),
        **_authority_fields(),
    }
    receipt["receipt_fingerprint"] = _fp(receipt)
    return materialization_spec, receipt


def validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("receipt_fingerprint", None)
    if checked.get("schema") != RECEIPT_SCHEMA or observed != _fp(checked):
        raise CorpusS3InventoryCaptureError(
            "capture receipt schema or fingerprint mismatch"
        )
    checked["receipt_fingerprint"] = observed
    _authority(checked, label="capture receipt")
    spec = checked.get("source_spec")
    evidence = checked.get("captured_inventory")
    if not isinstance(spec, Mapping) or not isinstance(evidence, Mapping):
        raise CorpusS3InventoryCaptureError(
            "capture receipt is missing embedded evidence"
        )
    if checked.get("source_spec_fingerprint") != _fp(spec):
        raise CorpusS3InventoryCaptureError(
            "capture source spec fingerprint mismatch"
        )
    if checked.get("captured_inventory_fingerprint") != _fp(evidence):
        raise CorpusS3InventoryCaptureError("capture evidence fingerprint mismatch")
    normalized = checked.get("normalized_inventory")
    if (
        not isinstance(normalized, Mapping)
        or checked.get("normalized_inventory_fingerprint") != _fp(normalized)
    ):
        raise CorpusS3InventoryCaptureError(
            "normalized capture evidence fingerprint mismatch"
        )
    materialization_spec, rebuilt = _build_from_evidence(
        spec,
        list_responses=evidence.get("list_object_versions") or {},
        head_responses=evidence.get("head_objects") or {},
    )
    if materialization_spec != checked.get("materialization_spec"):
        raise CorpusS3InventoryCaptureError(
            "materialization spec differs from deterministic rebuild"
        )
    if checked.get("materialization_spec_fingerprint") != _fp(
        materialization_spec
    ):
        raise CorpusS3InventoryCaptureError(
            "materialization spec fingerprint mismatch"
        )
    if rebuilt != dict(value):
        raise CorpusS3InventoryCaptureError(
            "capture receipt differs from deterministic rebuild"
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
        stderr = process.stderr.strip()
        raise CorpusS3InventoryCaptureError(
            f"AWS CLI command failed ({process.returncode}): {' '.join(argv)}: {stderr}"
        )
    try:
        value = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise CorpusS3InventoryCaptureError(
            f"AWS CLI returned invalid JSON: {' '.join(argv)}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusS3InventoryCaptureError(
            "AWS CLI response must be a JSON object"
        )
    return value


def capture_live(
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
    head_responses: dict[str, Mapping[str, Any]] = {}
    for corpus in spec.get("corpora") or []:
        corpus_id = str(corpus.get("corpus_id") or "")
        bucket = str(corpus.get("bucket") or "")
        prefix = str(corpus.get("prefix") or "")
        list_responses[corpus_id] = runner(
            [
                *global_args,
                "s3api",
                "list-object-versions",
                "--bucket",
                bucket,
                "--prefix",
                prefix,
                "--output",
                "json",
            ]
        )
        for source in corpus.get("sources") or []:
            source_id = str(source.get("source_id") or "")
            argv = [
                *global_args,
                "s3api",
                "head-object",
                "--bucket",
                bucket,
                "--key",
                str(source.get("key") or ""),
                "--version-id",
                str(source.get("version_id") or ""),
                "--checksum-mode",
                "ENABLED",
                "--output",
                "json",
            ]
            head_responses[source_id] = runner(argv)
    return _build_from_evidence(
        spec, list_responses=list_responses, head_responses=head_responses
    )


def selftest() -> int:
    checksum = hashlib.sha256(b"selftest").digest()
    checksum_b64 = base64.b64encode(checksum).decode("ascii")
    spec = {
        "schema": SPEC_SCHEMA,
        "allowed_roots": ["data"],
        "inventory_observed_at": "2026-07-25T00:00:00Z",
        "corpora": [],
        **_authority_fields(),
    }
    list_responses: dict[str, Mapping[str, Any]] = {}
    head_responses: dict[str, Mapping[str, Any]] = {}
    for corpus_id, expected in coverage.EXPECTED_WINDOWS.items():
        lane = expected["lane"]
        source_id = f"{corpus_id}-source"
        key = f"ng/{corpus_id}/source.dbn"
        spec["corpora"].append(
            {
                "corpus_id": corpus_id,
                "lane": lane,
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
                        "lane": lane,
                        "key": key,
                        "version_id": "v1",
                        "materialized_path": f"data/{source_id}.dbn",
                        "definition": {"placeholder": True},
                    }
                ],
            }
        )
        list_responses[corpus_id] = {
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
        head_responses[source_id] = {
            "ContentLength": 8,
            "LastModified": "2026-07-25T00:00:00Z",
            "VersionId": "v1",
            "ETag": source_id,
            "ChecksumSHA256": checksum_b64,
        }
    materialization_spec, receipt = _build_from_evidence(
        spec, list_responses=list_responses, head_responses=head_responses
    )
    assert receipt["status"] == READY_STATUS
    assert materialization_spec["schema"] == MATERIALIZATION_SCHEMA
    validate_receipt(receipt)
    tampered = copy.deepcopy(receipt)
    tampered["options_lane_started"] = True
    tampered["receipt_fingerprint"] = _fp(
        {
            key: value
            for key, value in tampered.items()
            if key != "receipt_fingerprint"
        }
    )
    try:
        validate_receipt(tampered)
    except CorpusS3InventoryCaptureError:
        return 0
    raise AssertionError("authority escalation was accepted")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("--spec", type=Path, required=True)
    capture_parser.add_argument(
        "--materialization-spec-out", type=Path, required=True
    )
    capture_parser.add_argument("--receipt-out", type=Path, required=True)
    capture_parser.add_argument("--aws-executable", default="aws")
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
    materialization_spec, receipt = capture_live(
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
    _write(args.materialization_spec_out, materialization_spec)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "materialization_spec": str(args.materialization_spec_out),
                "receipt": str(args.receipt_out),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
