#!/usr/bin/env python3
"""Materialize exact versioned/checksummed S3 corpus objects before byte inspection.

The runtime-observed inventory stage proves which exact S3 versions exist and emits the
canonical materialization specification. This stage makes that specification operational:
it downloads missing or mismatched objects with ``s3api get-object --version-id`` into a
temporary file, verifies byte size and SHA-256 before atomic replacement, reuses already
verified local bytes, and then runs the existing materialization/inspection-plan compiler.

No trading identity is inferred from object keys. The stage is historical-only,
outcome-blind, non-executing, and cannot mutate blind forecasts, posterior state,
``knowledge/ng_brain.json``, CME SHADOW mode, brokerage, or the options lane.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_corpus_s3_materialization_attestation as materialization
import ng_corpus_s3_materialization_stage as materialization_stage
import ng_corpus_s3_runtime_observed_inventory_capture as runtime_capture

SCHEMA = "ng_corpus_s3_exact_materializer_receipt.v1"
READY_STATUS = "S3_EXACT_VERSION_MATERIALIZATION_READY_FOR_BYTE_INSPECTION"
BLOCKED_STATUS = "S3_EXACT_VERSION_MATERIALIZATION_BLOCKED"


class CorpusS3ExactMaterializerError(ValueError):
    """Raised when exact object materialization evidence is unsafe."""


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusS3ExactMaterializerError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusS3ExactMaterializerError(f"JSON artifact must be an object: {path}")
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
            raise CorpusS3ExactMaterializerError(
                f"{label}: {field} must remain {expected!r}"
            )


def _timestamp_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _hex_sha256(value: Any, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise CorpusS3ExactMaterializerError(
            f"{label} must be a 64-character hexadecimal SHA-256"
        )
    return text


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise CorpusS3ExactMaterializerError(f"{label} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CorpusS3ExactMaterializerError(f"{label} must be a positive integer") from error
    if number <= 0:
        raise CorpusS3ExactMaterializerError(f"{label} must be a positive integer")
    return number


def _resolve_path(base: Path, value: Any, *, label: str) -> Path:
    text = str(value or "")
    if not text:
        raise CorpusS3ExactMaterializerError(f"{label} is required")
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _inside_allowed(path: Path, roots: Sequence[Path], *, label: str) -> None:
    for root in roots:
        if path == root or root in path.parents:
            return
    raise CorpusS3ExactMaterializerError(f"{label} escapes every allowed_root")


def _decode_s3_checksum(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        raw = base64.b64decode(text, validate=True)
    except Exception as error:
        raise CorpusS3ExactMaterializerError("S3 ChecksumSHA256 is not valid base64") from error
    if len(raw) != 32:
        raise CorpusS3ExactMaterializerError("S3 ChecksumSHA256 must decode to 32 bytes")
    return raw.hex()


def _run_get_object(argv: Sequence[str]) -> dict[str, Any]:
    process = subprocess.run(
        list(argv),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process.returncode != 0:
        raise CorpusS3ExactMaterializerError(
            f"AWS CLI command failed ({process.returncode}): {' '.join(argv[:-1])}: "
            f"{process.stderr.strip()}"
        )
    try:
        value = json.loads(process.stdout or "{}")
    except json.JSONDecodeError as error:
        raise CorpusS3ExactMaterializerError("AWS get-object returned invalid JSON") from error
    if not isinstance(value, dict):
        raise CorpusS3ExactMaterializerError("AWS get-object response must be an object")
    return value


def _global_aws_args(runtime_receipt: Mapping[str, Any], aws_executable: str) -> list[str]:
    source_spec = runtime_receipt.get("source_spec")
    if not isinstance(source_spec, Mapping):
        raise CorpusS3ExactMaterializerError(
            "runtime capture receipt is missing embedded source specification"
        )
    result = [aws_executable]
    profile = str(source_spec.get("aws_profile") or "")
    region = str(source_spec.get("aws_region") or "")
    if profile:
        result.extend(["--profile", profile])
    if region:
        result.extend(["--region", region])
    return result


def _source_rows(spec: Mapping[str, Any]) -> list[tuple[str, str, Mapping[str, Any]]]:
    rows: list[tuple[str, str, Mapping[str, Any]]] = []
    seen: set[str] = set()
    for raw_corpus in spec.get("corpora") or []:
        if not isinstance(raw_corpus, Mapping):
            raise CorpusS3ExactMaterializerError("materialization corpus is not an object")
        corpus_id = str(raw_corpus.get("corpus_id") or "")
        if not corpus_id:
            raise CorpusS3ExactMaterializerError("materialization corpus_id is required")
        for raw_source in raw_corpus.get("sources") or []:
            if not isinstance(raw_source, Mapping):
                raise CorpusS3ExactMaterializerError(
                    f"{corpus_id}: materialization source is not an object"
                )
            source_id = str(raw_source.get("source_id") or "")
            if not source_id or source_id in seen:
                raise CorpusS3ExactMaterializerError(
                    f"duplicate or missing source_id {source_id!r}"
                )
            seen.add(source_id)
            rows.append((corpus_id, source_id, raw_source))
    return sorted(rows, key=lambda row: row[1])


def materialize_source_bytes(
    spec: Mapping[str, Any],
    *,
    spec_dir: Path,
    runtime_receipt: Mapping[str, Any],
    aws_executable: str = "aws",
    runner: Callable[[Sequence[str]], Mapping[str, Any]] = _run_get_object,
    force_download: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Materialize every exact object and return evidence plus visible blockers."""

    materialization_spec = copy.deepcopy(dict(spec))
    if materialization_spec.get("schema") != materialization.SPEC_SCHEMA:
        raise CorpusS3ExactMaterializerError(
            f"materialization spec schema must be {materialization.SPEC_SCHEMA}"
        )
    _authority(materialization_spec, label="exact materialization specification")
    raw_roots = list(materialization_spec.get("allowed_roots") or [])
    if not raw_roots:
        raise CorpusS3ExactMaterializerError(
            "exact materialization specification requires allowed_roots"
        )
    roots = [
        _resolve_path(spec_dir, root, label="allowed_root") for root in raw_roots
    ]
    aws_prefix = _global_aws_args(runtime_receipt, aws_executable)
    evidence: list[dict[str, Any]] = []
    blockers: list[str] = []

    for index, (corpus_id, source_id, source) in enumerate(_source_rows(materialization_spec)):
        remote = source.get("s3_object")
        if not isinstance(remote, Mapping):
            raise CorpusS3ExactMaterializerError(f"{source_id}: s3_object is required")
        bucket = str(remote.get("bucket") or "").strip()
        key = str(remote.get("key") or "")
        version_id = str(remote.get("version_id") or "")
        if not bucket or not key or not version_id:
            raise CorpusS3ExactMaterializerError(
                f"{source_id}: exact bucket, key, and version_id are required"
            )
        expected_size = _positive_int(
            remote.get("size_bytes"), label=f"{source_id}:size_bytes"
        )
        expected_sha = _hex_sha256(
            remote.get("checksum_sha256"), label=f"{source_id}:checksum_sha256"
        )
        target = _resolve_path(
            spec_dir,
            source.get("materialized_path"),
            label=f"{source_id}:materialized_path",
        )
        _inside_allowed(target, roots, label=f"{source_id}:materialized_path")
        target.parent.mkdir(parents=True, exist_ok=True)

        existing_size = target.stat().st_size if target.is_file() else None
        existing_sha = _sha256(target) if target.is_file() else None
        existing_verified = existing_size == expected_size and existing_sha == expected_sha
        action = "REUSED_VERIFIED_LOCAL_BYTES"
        response: dict[str, Any] = {}
        atomic_replace = False
        source_blockers: list[str] = []

        if force_download or not existing_verified:
            action = "DOWNLOADED_EXACT_S3_VERSION"
            temporary = target.parent / (
                f".{target.name}.partial-{os.getpid()}-{index}"
            )
            try:
                temporary.unlink(missing_ok=True)
                command = [
                    *aws_prefix,
                    "s3api",
                    "get-object",
                    "--bucket",
                    bucket,
                    "--key",
                    key,
                    "--version-id",
                    version_id,
                    "--checksum-mode",
                    "ENABLED",
                    str(temporary),
                ]
                response = copy.deepcopy(dict(runner(command)))
                if not temporary.is_file():
                    source_blockers.append("DOWNLOAD_OUTPUT_MISSING")
                else:
                    observed_size = temporary.stat().st_size
                    observed_sha = _sha256(temporary)
                    if observed_size != expected_size:
                        source_blockers.append("DOWNLOADED_SIZE_MISMATCH")
                    if observed_sha != expected_sha:
                        source_blockers.append("DOWNLOADED_SHA256_MISMATCH")
                    response_version = str(response.get("VersionId") or "")
                    if response_version and response_version != version_id:
                        source_blockers.append("GET_OBJECT_VERSION_ID_MISMATCH")
                    response_length = response.get("ContentLength")
                    if response_length not in (None, "") and int(response_length) != expected_size:
                        source_blockers.append("GET_OBJECT_CONTENT_LENGTH_MISMATCH")
                    response_checksum = _decode_s3_checksum(response.get("ChecksumSHA256"))
                    if response_checksum is not None and response_checksum != expected_sha:
                        source_blockers.append("GET_OBJECT_CHECKSUM_SHA256_MISMATCH")
                    if not source_blockers:
                        os.replace(temporary, target)
                        atomic_replace = True
            except Exception as error:
                source_blockers.append(f"DOWNLOAD_FAILED:{type(error).__name__}")
            finally:
                temporary.unlink(missing_ok=True)

        observed_size = target.stat().st_size if target.is_file() else None
        observed_sha = _sha256(target) if target.is_file() else None
        if observed_size != expected_size:
            source_blockers.append("FINAL_LOCAL_SIZE_MISMATCH")
        if observed_sha != expected_sha:
            source_blockers.append("FINAL_LOCAL_SHA256_MISMATCH")
        source_blockers = sorted(set(source_blockers))
        blockers.extend(f"{source_id}:{item}" for item in source_blockers)
        evidence.append(
            {
                "corpus_id": corpus_id,
                "source_id": source_id,
                "bucket": bucket,
                "key": key,
                "version_id": version_id,
                "materialized_path": str(target),
                "expected_size_bytes": expected_size,
                "expected_sha256": expected_sha,
                "preexisting_size_bytes": existing_size,
                "preexisting_sha256": existing_sha,
                "preexisting_bytes_verified": existing_verified,
                "action": action,
                "atomic_replace_performed": atomic_replace,
                "get_object_response": response,
                "final_size_bytes": observed_size,
                "final_sha256": observed_sha,
                "exact_version_and_checksum_verified": not source_blockers,
                "identity_inferred_from_s3_key": False,
                "blockers": source_blockers,
            }
        )

    return evidence, sorted(set(blockers))


def materialize_exact_versions(
    *,
    runtime_capture_path: Path,
    materialization_spec_path: Path,
    inventory_spec_out: Path,
    plan_out: Path,
    inventory_receipt_out: Path,
    materialization_receipt_out: Path,
    receipt_out: Path,
    aws_executable: str = "aws",
    runner: Callable[[Sequence[str]], Mapping[str, Any]] = _run_get_object,
    force_download: bool = False,
    now: Callable[[], datetime] | None = None,
    runtime_validator: Callable[[Mapping[str, Any]], Mapping[str, Any]] = runtime_capture.validate_receipt,
) -> dict[str, Any]:
    runtime_value = runtime_validator(_load(runtime_capture_path))
    if runtime_value.get("status") != runtime_capture.READY_STATUS:
        raise CorpusS3ExactMaterializerError(
            "runtime-observed inventory capture must be ready before materialization"
        )
    spec = _load(materialization_spec_path)
    _authority(spec, label="materialization specification")
    if runtime_value.get("materialization_spec_fingerprint") != _fp(spec):
        raise CorpusS3ExactMaterializerError(
            "runtime capture and materialization specification fingerprint mismatch"
        )

    clock = now or (lambda: datetime.now(timezone.utc))
    started = clock()
    evidence, blockers = materialize_source_bytes(
        spec,
        spec_dir=materialization_spec_path.parent.resolve(),
        runtime_receipt=runtime_value,
        aws_executable=aws_executable,
        runner=runner,
        force_download=force_download,
    )
    completed = clock()
    nested_receipt: dict[str, Any] | None = None
    if not blockers:
        materialization_stage.compile_stage(
            spec_path=materialization_spec_path,
            inventory_spec_out=inventory_spec_out,
            plan_out=plan_out,
            inventory_receipt_out=inventory_receipt_out,
            receipt_out=materialization_receipt_out,
        )
        nested_receipt = _load(materialization_receipt_out)
        materialization.validate_receipt(nested_receipt)
        if nested_receipt.get("status") != materialization.READY_STATUS:
            blockers.append("DOWNSTREAM_MATERIALIZATION_ATTESTATION_BLOCKED")

    status = READY_STATUS if not blockers and nested_receipt is not None else BLOCKED_STATUS
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "runtime_inventory_capture_fingerprint": runtime_value.get("receipt_fingerprint"),
        "source_spec": spec,
        "source_spec_fingerprint": _fp(spec),
        "materialization_started_at_utc": _timestamp_text(started),
        "materialization_completed_at_utc": _timestamp_text(completed),
        "source_materializations": evidence,
        "source_materializations_fingerprint": _fp(evidence),
        "source_count": len(evidence),
        "exact_version_get_object_required": True,
        "checksum_mode_enabled": True,
        "atomic_local_replacement_required": True,
        "identity_from_s3_keys_inferred": False,
        "downstream_materialization_receipt": nested_receipt,
        "downstream_materialization_receipt_fingerprint": (
            nested_receipt.get("receipt_fingerprint") if nested_receipt else None
        ),
        "canonical_inventory_spec_fingerprint": (
            nested_receipt.get("canonical_inventory_spec_fingerprint") if nested_receipt else None
        ),
        "materialization_evidence_fingerprint": (
            nested_receipt.get("materialization_evidence_fingerprint") if nested_receipt else None
        ),
        "plan_fingerprint": nested_receipt.get("plan_fingerprint") if nested_receipt else None,
        "inventory_compiler_receipt_fingerprint": (
            nested_receipt.get("inventory_compiler_receipt_fingerprint")
            if nested_receipt
            else None
        ),
        "blockers": sorted(set(blockers)),
        "next_action": (
            "RUN_BYTE_LEVEL_CORPUS_INSPECTION"
            if status == READY_STATUS
            else "REPAIR_EXACT_S3_MATERIALIZATION_BLOCKERS"
        ),
        **_authority_fields(),
    }
    receipt["receipt_fingerprint"] = _fp(receipt)
    _write(receipt_out, receipt)
    validate_receipt(receipt)
    return receipt


def validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("receipt_fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise CorpusS3ExactMaterializerError(
            "exact materializer receipt schema or fingerprint mismatch"
        )
    checked["receipt_fingerprint"] = observed
    _authority(checked, label="exact materializer receipt")
    if checked.get("identity_from_s3_keys_inferred") is not False:
        raise CorpusS3ExactMaterializerError(
            "trading identity may not be inferred from S3 keys"
        )
    if checked.get("exact_version_get_object_required") is not True:
        raise CorpusS3ExactMaterializerError("exact version get-object must remain required")
    if checked.get("checksum_mode_enabled") is not True:
        raise CorpusS3ExactMaterializerError("checksum mode must remain enabled")
    if checked.get("atomic_local_replacement_required") is not True:
        raise CorpusS3ExactMaterializerError("atomic local replacement must remain required")

    spec = checked.get("source_spec")
    evidence = checked.get("source_materializations")
    if not isinstance(spec, Mapping) or not isinstance(evidence, list):
        raise CorpusS3ExactMaterializerError(
            "exact materializer receipt lacks source specification or evidence"
        )
    if checked.get("source_spec_fingerprint") != _fp(spec):
        raise CorpusS3ExactMaterializerError(
            "exact materializer source-spec fingerprint mismatch"
        )
    if checked.get("source_materializations_fingerprint") != _fp(evidence):
        raise CorpusS3ExactMaterializerError(
            "exact materializer source-evidence fingerprint mismatch"
        )
    if checked.get("source_count") != len(evidence):
        raise CorpusS3ExactMaterializerError("exact materializer source count mismatch")

    blockers: list[str] = []
    for row in evidence:
        if not isinstance(row, Mapping):
            raise CorpusS3ExactMaterializerError(
                "exact materializer evidence row is not an object"
            )
        source_id = str(row.get("source_id") or "")
        path = Path(str(row.get("materialized_path") or ""))
        expected_size = _positive_int(
            row.get("expected_size_bytes"), label=f"{source_id}:expected_size_bytes"
        )
        expected_sha = _hex_sha256(
            row.get("expected_sha256"), label=f"{source_id}:expected_sha256"
        )
        if not path.is_file():
            blockers.append(f"{source_id}:FINAL_LOCAL_FILE_MISSING")
            continue
        if path.stat().st_size != expected_size:
            blockers.append(f"{source_id}:FINAL_LOCAL_SIZE_MISMATCH")
        if _sha256(path) != expected_sha:
            blockers.append(f"{source_id}:FINAL_LOCAL_SHA256_MISMATCH")
        if row.get("identity_inferred_from_s3_key") is not False:
            raise CorpusS3ExactMaterializerError(
                f"{source_id}: identity may not be inferred from S3 key"
            )

    nested = checked.get("downstream_materialization_receipt")
    receipt_blockers = list(checked.get("blockers") or [])
    expected_status = READY_STATUS if not receipt_blockers else BLOCKED_STATUS
    if checked.get("status") != expected_status:
        raise CorpusS3ExactMaterializerError(
            "exact materializer status does not match blockers"
        )
    if blockers and checked.get("status") == READY_STATUS:
        raise CorpusS3ExactMaterializerError(
            "current local bytes no longer match exact materialization evidence"
        )

    if checked.get("status") == READY_STATUS:
        if not isinstance(nested, Mapping):
            raise CorpusS3ExactMaterializerError(
                "ready exact materializer receipt lacks downstream attestation"
            )
        nested_value = materialization.validate_receipt(nested)
        if nested_value.get("status") != materialization.READY_STATUS:
            raise CorpusS3ExactMaterializerError(
                "downstream materialization attestation is not ready"
            )
        links = {
            "downstream_materialization_receipt_fingerprint": nested_value.get(
                "receipt_fingerprint"
            ),
            "canonical_inventory_spec_fingerprint": nested_value.get(
                "canonical_inventory_spec_fingerprint"
            ),
            "materialization_evidence_fingerprint": nested_value.get(
                "materialization_evidence_fingerprint"
            ),
            "plan_fingerprint": nested_value.get("plan_fingerprint"),
            "inventory_compiler_receipt_fingerprint": nested_value.get(
                "inventory_compiler_receipt_fingerprint"
            ),
        }
        for field, expected in links.items():
            if checked.get(field) != expected:
                raise CorpusS3ExactMaterializerError(
                    f"exact materializer {field} link mismatch"
                )
        if nested_value.get("source_spec_fingerprint") != checked.get(
            "source_spec_fingerprint"
        ):
            raise CorpusS3ExactMaterializerError(
                "downstream materialization source-spec fingerprint mismatch"
            )
        if checked.get("next_action") != "RUN_BYTE_LEVEL_CORPUS_INSPECTION":
            raise CorpusS3ExactMaterializerError(
                "ready exact materializer next action mismatch"
            )
    elif checked.get("next_action") != "REPAIR_EXACT_S3_MATERIALIZATION_BLOCKERS":
        raise CorpusS3ExactMaterializerError(
            "blocked exact materializer next action mismatch"
        )
    return copy.deepcopy(dict(value))


def _selftest() -> int:
    import ng_corpus_coverage_audit as coverage
    import ng_corpus_inspection as inspection

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        data = root / "data"
        data.mkdir()
        contents = {"l1": b'{"lane":"l1"}\n', "mbo": b'{"lane":"mbo"}\n'}
        corpora = []
        for source_id, lane, corpus_id in (
            ("l1", "l1_trades", coverage.L1_CORPUS_ID),
            ("mbo", "mbo", coverage.MBO_CORPUS_ID),
        ):
            payload = contents[source_id]
            digest = hashlib.sha256(payload).hexdigest()
            definition = inspection.definition_observation(
                dataset=coverage.DATASET,
                publisher_id=1,
                instrument_id=1008,
                raw_symbol="NGJ26",
                definition_date="20260315",
                definition_start_s=0.0,
                definition_end_s=2.0,
                observed_from=f"exact-materializer-selftest:{source_id}",
                observed_at="2026-07-25T00:00:00Z",
                source_sha256=digest,
                source_size_bytes=len(payload),
            )
            corpora.append(
                {
                    "corpus_id": corpus_id,
                    "lane": lane,
                    "publisher_id": 1,
                    "expected_days": ["20260315"],
                    "expected_object_count": 1,
                    "inventory_scope_verified": True,
                    "inventory_complete_asserted": True,
                    "sources": [
                        {
                            "source_id": source_id,
                            "day": "20260315",
                            "lane": lane,
                            "materialized_path": str(data / f"{source_id}.jsonl"),
                            "s3_object": {
                                "bucket": "selftest-bucket",
                                "key": f"ng/{source_id}.jsonl",
                                "version_id": f"version-{source_id}",
                                "etag": source_id,
                                "last_modified": "2026-07-25T00:00:00Z",
                                "size_bytes": len(payload),
                                "checksum_sha256": digest,
                                "checksum_source": "ChecksumSHA256",
                            },
                            "definition": definition,
                        }
                    ],
                }
            )
        spec = {
            "schema": materialization.SPEC_SCHEMA,
            "allowed_roots": [str(data)],
            "inventory_observed_at": "2026-07-25T00:00:00Z",
            "corpora": corpora,
            **_authority_fields(),
        }
        spec_path = root / "materialization.json"
        _write(spec_path, spec)
        runtime_receipt = {
            "status": runtime_capture.READY_STATUS,
            "receipt_fingerprint": "r" * 64,
            "materialization_spec_fingerprint": _fp(spec),
            "source_spec": {**_authority_fields()},
        }
        runtime_path = root / "runtime.json"
        _write(runtime_path, runtime_receipt)

        def runner(argv: Sequence[str]) -> Mapping[str, Any]:
            destination = Path(argv[-1])
            key = argv[argv.index("--key") + 1]
            source_id = "l1" if key.endswith("l1.jsonl") else "mbo"
            payload = contents[source_id]
            destination.write_bytes(payload)
            return {
                "VersionId": f"version-{source_id}",
                "ContentLength": len(payload),
                "ChecksumSHA256": base64.b64encode(
                    hashlib.sha256(payload).digest()
                ).decode("ascii"),
            }

        receipt = materialize_exact_versions(
            runtime_capture_path=runtime_path,
            materialization_spec_path=spec_path,
            inventory_spec_out=root / "inventory.json",
            plan_out=root / "plan.json",
            inventory_receipt_out=root / "inventory-receipt.json",
            materialization_receipt_out=root / "materialization-receipt.json",
            receipt_out=root / "exact-receipt.json",
            runner=runner,
            runtime_validator=lambda value: copy.deepcopy(dict(value)),
        )
        assert receipt["status"] == READY_STATUS
        assert all(
            row["exact_version_and_checksum_verified"]
            for row in receipt["source_materializations"]
        )
        validate_receipt(receipt)

    print("[ng_corpus_s3_exact_materializer] selftest PASS")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")
    materialize_parser = subparsers.add_parser("materialize")
    materialize_parser.add_argument("--runtime-capture", type=Path, required=True)
    materialize_parser.add_argument("--materialization-spec", type=Path, required=True)
    materialize_parser.add_argument("--inventory-spec-out", type=Path, required=True)
    materialize_parser.add_argument("--plan-out", type=Path, required=True)
    materialize_parser.add_argument("--inventory-receipt-out", type=Path, required=True)
    materialize_parser.add_argument("--materialization-receipt-out", type=Path, required=True)
    materialize_parser.add_argument("--receipt-out", type=Path, required=True)
    materialize_parser.add_argument("--aws-executable", default="aws")
    materialize_parser.add_argument("--force-download", action="store_true")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--receipt", type=Path, required=True)
    subparsers.add_parser("selftest")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "selftest":
        return _selftest()
    if args.command == "validate":
        validate_receipt(_load(args.receipt))
        print(json.dumps({"receipt": str(args.receipt), "valid": True}, sort_keys=True))
        return 0
    if args.command == "materialize":
        receipt = materialize_exact_versions(
            runtime_capture_path=args.runtime_capture,
            materialization_spec_path=args.materialization_spec,
            inventory_spec_out=args.inventory_spec_out,
            plan_out=args.plan_out,
            inventory_receipt_out=args.inventory_receipt_out,
            materialization_receipt_out=args.materialization_receipt_out,
            receipt_out=args.receipt_out,
            aws_executable=args.aws_executable,
            force_download=args.force_download,
        )
        print(
            json.dumps(
                {
                    "receipt": str(args.receipt_out),
                    "status": receipt["status"],
                    "source_count": receipt["source_count"],
                },
                sort_keys=True,
            )
        )
        return 0
    parser.error("choose materialize, validate, or selftest")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
