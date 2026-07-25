#!/usr/bin/env python3
"""Bind explicit S3 inventory evidence to materialized NG corpus bytes.

This is the fail-closed bridge between a versioned/checksummed AWS/S3 object
inventory and ``ng_corpus_inventory_plan_compiler.py``. It never downloads
objects, infers identity from S3 keys, or assumes a paid live feed. Every
source must declare its day, lane, exact remote object identity, SHA-256,
materialized local path, and observed definition record.

The output is an ordinary canonical corpus-inspection plan plus a deterministic
attestation that the local bytes exactly match the declared remote object and
the definition observation. It cannot alter blind forecasts, posterior state,
``knowledge/ng_brain.json``, execution authority, CME SHADOW mode, brokerage,
or the options lane.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote

import ng_corpus_coverage_audit as coverage
import ng_corpus_inspection as inspection
import ng_corpus_inventory_plan_compiler as compiler

SPEC_SCHEMA = "ng_corpus_s3_materialization_spec.v1"
RECEIPT_SCHEMA = "ng_corpus_s3_materialization_attestation.v1"
READY_STATUS = "S3_MATERIALIZATION_ATTESTED_READY_FOR_BYTE_INSPECTION"
BLOCKED_STATUS = "S3_MATERIALIZATION_ATTESTED_WITH_INVENTORY_BLOCKERS"


class CorpusS3MaterializationError(ValueError):
    """Raised when remote-object or local-byte evidence is unsafe."""


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


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusS3MaterializationError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusS3MaterializationError(
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
    expected = _authority_fields()
    for field, required in expected.items():
        if value.get(field) != required:
            raise CorpusS3MaterializationError(
                f"{label}: {field} must remain {required!r}"
            )


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise CorpusS3MaterializationError(
            f"{label} must be a positive integer"
        )
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CorpusS3MaterializationError(
            f"{label} must be a positive integer"
        ) from error
    if number <= 0:
        raise CorpusS3MaterializationError(
            f"{label} must be a positive integer"
        )
    return number


def _hex_sha256(value: Any, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise CorpusS3MaterializationError(
            f"{label} must be a 64-character hexadecimal SHA-256"
        )
    return text


def _resolve_path(base: Path, value: Any, *, label: str) -> Path:
    text = str(value or "")
    if not text:
        raise CorpusS3MaterializationError(f"{label} is required")
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _inside_allowed(
    path: Path, allowed_roots: Sequence[Path], *, label: str
) -> None:
    for root in allowed_roots:
        if path == root or root in path.parents:
            return
    raise CorpusS3MaterializationError(
        f"{label} escapes every allowed_root"
    )


def _definition(
    source: Mapping[str, Any], *, source_id: str, spec_dir: Path
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    inline = source.get("definition")
    reference = source.get("definition_path")
    if inline not in (None, "") and reference not in (None, ""):
        raise CorpusS3MaterializationError(
            f"{source_id}: provide exactly one of definition or definition_path"
        )
    if inline not in (None, ""):
        if not isinstance(inline, Mapping):
            raise CorpusS3MaterializationError(
                f"{source_id}: definition must be an object"
            )
        return inspection.validate_definition(inline), None
    if reference in (None, ""):
        raise CorpusS3MaterializationError(
            f"{source_id}: observed definition is required"
        )
    relative = Path(str(reference))
    if relative.is_absolute():
        raise CorpusS3MaterializationError(
            f"{source_id}: definition_path must be relative"
        )
    root = spec_dir.resolve()
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise CorpusS3MaterializationError(
            f"{source_id}: definition_path escapes the spec directory"
        )
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise CorpusS3MaterializationError(
            f"{source_id}: cannot read definition document {path}: {error}"
        ) from error
    observed_sha = hashlib.sha256(raw).hexdigest()
    expected_sha = source.get("definition_sha256")
    if expected_sha not in (None, "") and _hex_sha256(
        expected_sha, label=f"{source_id}:definition_sha256"
    ) != observed_sha:
        raise CorpusS3MaterializationError(
            f"{source_id}: definition_sha256 mismatch"
        )
    try:
        raw_text = raw.decode("utf-8")
        parsed = json.loads(raw_text)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CorpusS3MaterializationError(
            f"{source_id}: definition document is invalid JSON"
        ) from error
    if not isinstance(parsed, dict):
        raise CorpusS3MaterializationError(
            f"{source_id}: definition document must contain an object"
        )
    document = {
        "source_id": source_id,
        "reference": str(reference),
        "sha256": observed_sha,
        "size_bytes": len(raw),
        "raw_text": raw_text,
    }
    return inspection.validate_definition(parsed), document


def _remote_object(
    source: Mapping[str, Any], *, source_id: str
) -> dict[str, Any]:
    raw = source.get("s3_object")
    if not isinstance(raw, Mapping):
        raise CorpusS3MaterializationError(
            f"{source_id}: s3_object must be an object"
        )
    bucket = str(raw.get("bucket") or "").strip()
    key = str(raw.get("key") or "")
    if not bucket or not key:
        raise CorpusS3MaterializationError(
            f"{source_id}: s3 bucket and key are required"
        )
    if "://" in bucket or bucket.startswith("/") or key.startswith("/"):
        raise CorpusS3MaterializationError(
            f"{source_id}: invalid exact S3 bucket/key identity"
        )
    version_id = str(raw.get("version_id") or "")
    etag = str(raw.get("etag") or "").strip().strip('"')
    last_modified = str(raw.get("last_modified") or "")
    if not last_modified:
        raise CorpusS3MaterializationError(
            f"{source_id}: s3 last_modified is required"
        )
    size_bytes = _positive_int(
        raw.get("size_bytes"), label=f"{source_id}:s3 size_bytes"
    )
    checksum_sha256 = _hex_sha256(
        raw.get("checksum_sha256"),
        label=f"{source_id}:s3 checksum_sha256",
    )
    normalized = {
        "bucket": bucket,
        "key": key,
        "version_id": version_id or None,
        "etag": etag or None,
        "last_modified": last_modified,
        "size_bytes": size_bytes,
        "checksum_sha256": checksum_sha256,
        "checksum_source": str(raw.get("checksum_source") or "").strip(),
    }
    if not normalized["checksum_source"]:
        raise CorpusS3MaterializationError(
            f"{source_id}: s3 checksum_source is required"
        )
    return normalized


def _s3_location(remote: Mapping[str, Any]) -> str:
    location = (
        f"s3://{remote['bucket']}/"
        f"{quote(str(remote['key']), safe='/-_.~')}"
    )
    if remote.get("version_id"):
        location += "?versionId=" + quote(
            str(remote["version_id"]), safe="-_.~"
        )
    return location


def _build_core(
    source_spec: Mapping[str, Any], *, spec_dir: Path
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    spec = copy.deepcopy(dict(source_spec))
    if spec.get("schema") != SPEC_SCHEMA:
        raise CorpusS3MaterializationError(
            f"materialization spec schema must be {SPEC_SCHEMA}"
        )
    _authority(spec, label="materialization spec")
    observed_at = str(spec.get("inventory_observed_at") or "")
    if not observed_at:
        raise CorpusS3MaterializationError(
            "inventory_observed_at is required"
        )
    raw_roots = list(spec.get("allowed_roots") or [])
    if not raw_roots:
        raise CorpusS3MaterializationError(
            "materialization spec requires at least one allowed_root"
        )
    roots = [
        _resolve_path(spec_dir, root, label="allowed_root")
        for root in raw_roots
    ]
    corpora = list(spec.get("corpora") or [])
    if len(corpora) != len(coverage.EXPECTED_WINDOWS):
        raise CorpusS3MaterializationError(
            "materialization spec must contain both canonical corpora"
        )

    seen_corpora: set[str] = set()
    seen_sources: set[str] = set()
    seen_remote_objects: set[tuple[str, str, str | None]] = set()
    canonical_corpora: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    definition_documents: list[dict[str, Any]] = []

    for raw_corpus in corpora:
        if not isinstance(raw_corpus, Mapping):
            raise CorpusS3MaterializationError(
                "materialization corpus is not an object"
            )
        corpus = copy.deepcopy(dict(raw_corpus))
        corpus_id = str(corpus.get("corpus_id") or "")
        expected = coverage.EXPECTED_WINDOWS.get(corpus_id)
        if expected is None or corpus_id in seen_corpora:
            raise CorpusS3MaterializationError(
                f"unexpected or duplicate corpus_id {corpus_id!r}"
            )
        seen_corpora.add(corpus_id)
        lane = str(corpus.get("lane") or expected["lane"])
        if lane != expected["lane"]:
            raise CorpusS3MaterializationError(
                f"{corpus_id}: lane mismatch"
            )
        publisher_id = _positive_int(
            corpus.get("publisher_id"), label=f"{corpus_id}:publisher_id"
        )
        canonical_sources: list[dict[str, Any]] = []
        for raw_source in corpus.get("sources") or []:
            if not isinstance(raw_source, Mapping):
                raise CorpusS3MaterializationError(
                    f"{corpus_id}: source is not an object"
                )
            source = copy.deepcopy(dict(raw_source))
            source_id = str(source.get("source_id") or "")
            if not source_id or source_id in seen_sources:
                raise CorpusS3MaterializationError(
                    f"duplicate or missing source_id {source_id!r}"
                )
            seen_sources.add(source_id)
            if source.get("lane") != lane:
                raise CorpusS3MaterializationError(
                    f"{source_id}: explicit lane must be {lane}"
                )
            day = str(source.get("day") or "")
            if not day:
                raise CorpusS3MaterializationError(
                    f"{source_id}: explicit day is required"
                )
            remote = _remote_object(source, source_id=source_id)
            remote_key = (
                str(remote["bucket"]),
                str(remote["key"]),
                remote.get("version_id"),
            )
            if remote_key in seen_remote_objects:
                raise CorpusS3MaterializationError(
                    f"{source_id}: duplicate exact S3 object identity"
                )
            seen_remote_objects.add(remote_key)
            local = _resolve_path(
                spec_dir,
                source.get("materialized_path"),
                label=f"{source_id}:materialized_path",
            )
            _inside_allowed(
                local, roots, label=f"{source_id}:materialized_path"
            )
            if not local.is_file():
                raise CorpusS3MaterializationError(
                    f"{source_id}: materialized_path is not a regular file"
                )
            local_size = local.stat().st_size
            local_sha = _sha256(local)
            if local_size != int(remote["size_bytes"]):
                raise CorpusS3MaterializationError(
                    f"{source_id}: materialized size does not match S3 object"
                )
            if local_sha != remote["checksum_sha256"]:
                raise CorpusS3MaterializationError(
                    f"{source_id}: materialized SHA-256 does not match S3 object"
                )
            definition, document = _definition(
                source, source_id=source_id, spec_dir=spec_dir
            )
            if definition["source_sha256"] != local_sha:
                raise CorpusS3MaterializationError(
                    f"{source_id}: definition source_sha256 does not match "
                    "materialized bytes"
                )
            if int(definition["source_size_bytes"]) != local_size:
                raise CorpusS3MaterializationError(
                    f"{source_id}: definition source_size_bytes does not "
                    "match materialized bytes"
                )
            if int(definition["publisher_id"]) != publisher_id:
                raise CorpusS3MaterializationError(
                    f"{source_id}: definition publisher mismatch"
                )
            if definition["dataset"] != coverage.DATASET:
                raise CorpusS3MaterializationError(
                    f"{source_id}: definition dataset mismatch"
                )
            location = _s3_location(remote)
            canonical_sources.append(
                {
                    "source_id": source_id,
                    "day": day,
                    "lane": lane,
                    "location": location,
                    "materialized_path": str(local),
                    "definition": definition,
                    "skip_nonmatching": source.get("skip_nonmatching") is True,
                    "inventory_observed_at": str(
                        source.get("inventory_observed_at") or observed_at
                    ),
                }
            )
            evidence.append(
                {
                    "source_id": source_id,
                    "corpus_id": corpus_id,
                    "lane": lane,
                    "day": day,
                    "remote_object": remote,
                    "remote_identity_fingerprint": _fp(remote),
                    "location": location,
                    "materialized_path": str(local),
                    "materialized_size_bytes": local_size,
                    "materialized_sha256": local_sha,
                    "definition_fingerprint": definition[
                        "definition_fingerprint"
                    ],
                    "remote_bytes_match_materialized": True,
                    "definition_bytes_match_materialized": True,
                    "identity_inferred_from_s3_key": False,
                }
            )
            if document is not None:
                definition_documents.append(document)
        canonical_corpora.append(
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
                "sources": canonical_sources,
            }
        )

    if seen_corpora != set(coverage.EXPECTED_WINDOWS):
        raise CorpusS3MaterializationError(
            "materialization spec is missing a canonical corpus"
        )
    inventory_spec = {
        "schema": compiler.SPEC_SCHEMA,
        "allowed_roots": [str(root) for root in roots],
        "inventory_observed_at": observed_at,
        "corpora": canonical_corpora,
        **_authority_fields(),
    }
    plan, compiler_receipt = compiler.build_compiled_plan(
        inventory_spec, spec_dir=spec_dir
    )
    return (
        inventory_spec,
        plan,
        sorted(evidence, key=lambda row: str(row["source_id"])),
        sorted(
            definition_documents, key=lambda row: str(row["source_id"])
        ),
        compiler_receipt,
    )


def build_attested_plan(
    source_spec: Mapping[str, Any], *, spec_dir: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    (
        inventory_spec,
        plan,
        evidence,
        definition_documents,
        compiler_receipt,
    ) = _build_core(source_spec, spec_dir=spec_dir.resolve())
    blockers = list(compiler_receipt.get("blockers") or [])
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": READY_STATUS if not blockers else BLOCKED_STATUS,
        "spec_directory": str(spec_dir.resolve()),
        "source_spec": copy.deepcopy(dict(source_spec)),
        "source_spec_fingerprint": _fp(source_spec),
        "canonical_inventory_spec": inventory_spec,
        "canonical_inventory_spec_fingerprint": _fp(inventory_spec),
        "definition_documents": definition_documents,
        "materialization_evidence": evidence,
        "materialization_evidence_fingerprint": _fp(evidence),
        "compiled_plan": plan,
        "plan_fingerprint": plan["plan_fingerprint"],
        "inventory_compiler_receipt": compiler_receipt,
        "inventory_compiler_receipt_fingerprint": compiler_receipt[
            "receipt_fingerprint"
        ],
        "blockers": blockers,
        "next_action": (
            "RUN_BYTE_LEVEL_CORPUS_INSPECTION"
            if not blockers
            else "RESOLVE_INVENTORY_SCOPE_BLOCKERS_BEFORE_BYTE_INSPECTION"
        ),
        **_authority_fields(),
    }
    receipt["receipt_fingerprint"] = _fp(receipt)
    validate_receipt(receipt)
    return inventory_spec, plan, receipt


def validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("receipt_fingerprint", None)
    if checked.get("schema") != RECEIPT_SCHEMA or observed != _fp(checked):
        raise CorpusS3MaterializationError(
            "materialization receipt schema or fingerprint mismatch"
        )
    checked["receipt_fingerprint"] = observed
    _authority(checked, label="materialization receipt")
    source_spec = copy.deepcopy(dict(checked.get("source_spec") or {}))
    if checked.get("source_spec_fingerprint") != _fp(source_spec):
        raise CorpusS3MaterializationError(
            "materialization source spec fingerprint mismatch"
        )
    spec_dir = Path(str(checked.get("spec_directory") or ""))
    if not spec_dir.is_absolute():
        raise CorpusS3MaterializationError(
            "materialization spec_directory must be absolute"
        )
    (
        inventory_spec,
        plan,
        evidence,
        definition_documents,
        compiler_receipt,
    ) = _build_core(source_spec, spec_dir=spec_dir)
    if (
        inventory_spec != checked.get("canonical_inventory_spec")
        or checked.get("canonical_inventory_spec_fingerprint")
        != _fp(inventory_spec)
    ):
        raise CorpusS3MaterializationError(
            "canonical inventory spec mismatch"
        )
    if (
        evidence != list(checked.get("materialization_evidence") or [])
        or checked.get("materialization_evidence_fingerprint")
        != _fp(evidence)
    ):
        raise CorpusS3MaterializationError(
            "materialization evidence mismatch"
        )
    if definition_documents != list(
        checked.get("definition_documents") or []
    ):
        raise CorpusS3MaterializationError(
            "definition document evidence mismatch"
        )
    if (
        plan != checked.get("compiled_plan")
        or checked.get("plan_fingerprint") != plan["plan_fingerprint"]
    ):
        raise CorpusS3MaterializationError(
            "compiled inspection plan mismatch"
        )
    if (
        compiler_receipt != checked.get("inventory_compiler_receipt")
        or checked.get("inventory_compiler_receipt_fingerprint")
        != compiler_receipt["receipt_fingerprint"]
    ):
        raise CorpusS3MaterializationError(
            "nested inventory compiler receipt mismatch"
        )
    compiler.validate_receipt(compiler_receipt)
    blockers = list(compiler_receipt.get("blockers") or [])
    expected_status = READY_STATUS if not blockers else BLOCKED_STATUS
    expected_action = (
        "RUN_BYTE_LEVEL_CORPUS_INSPECTION"
        if not blockers
        else "RESOLVE_INVENTORY_SCOPE_BLOCKERS_BEFORE_BYTE_INSPECTION"
    )
    if (
        checked.get("blockers") != blockers
        or checked.get("status") != expected_status
        or checked.get("next_action") != expected_action
    ):
        raise CorpusS3MaterializationError(
            "materialization status, blockers, or next action mismatch"
        )
    return checked


def _self_test() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        data = root / "data"
        data.mkdir()
        sources: dict[str, dict[str, Any]] = {}
        for source_id, lane in (("l1", "l1_trades"), ("mbo", "mbo")):
            path = data / f"{source_id}.jsonl"
            path.write_text("{}\n", encoding="utf-8")
            raw_sha = _sha256(path)
            definition = inspection.definition_observation(
                dataset=coverage.DATASET,
                publisher_id=1,
                instrument_id=1008,
                raw_symbol="NGJ26",
                definition_date="20260315",
                definition_start_s=0.0,
                definition_end_s=2.0,
                observed_from=f"s3-selftest:{source_id}",
                observed_at="2026-07-24T00:00:00Z",
                source_sha256=raw_sha,
                source_size_bytes=path.stat().st_size,
            )
            sources[source_id] = {
                "source_id": source_id,
                "day": "20260315",
                "lane": lane,
                "materialized_path": str(path),
                "s3_object": {
                    "bucket": "selftest-bucket",
                    "key": f"ng/{source_id}.jsonl",
                    "version_id": "v1",
                    "etag": source_id,
                    "last_modified": "2026-07-24T00:00:00Z",
                    "size_bytes": path.stat().st_size,
                    "checksum_sha256": raw_sha,
                    "checksum_source": "upload-manifest",
                },
                "definition": definition,
            }
        spec = {
            "schema": SPEC_SCHEMA,
            "allowed_roots": [str(data)],
            "inventory_observed_at": "2026-07-24T00:00:00Z",
            "corpora": [
                {
                    "corpus_id": coverage.L1_CORPUS_ID,
                    "lane": "l1_trades",
                    "publisher_id": 1,
                    "expected_days": ["20260315"],
                    "expected_object_count": 1,
                    "inventory_scope_verified": True,
                    "inventory_complete_asserted": True,
                    "sources": [sources["l1"]],
                },
                {
                    "corpus_id": coverage.MBO_CORPUS_ID,
                    "lane": "mbo",
                    "publisher_id": 1,
                    "expected_days": ["20260315"],
                    "expected_object_count": 1,
                    "inventory_scope_verified": True,
                    "inventory_complete_asserted": True,
                    "sources": [sources["mbo"]],
                },
            ],
            **_authority_fields(),
        }
        _, _, receipt = build_attested_plan(spec, spec_dir=root)
        assert receipt["status"] == READY_STATUS
        validate_receipt(receipt)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("--spec", type=Path, required=True)
    compile_parser.add_argument(
        "--inventory-spec-out", type=Path, required=True
    )
    compile_parser.add_argument("--plan-out", type=Path, required=True)
    compile_parser.add_argument("--receipt-out", type=Path, required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--receipt", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.self_test:
        _self_test()
        return 0
    if args.command == "compile":
        source_spec = _load_json(args.spec)
        inventory_spec, plan, receipt = build_attested_plan(
            source_spec, spec_dir=args.spec.parent
        )
        _write(args.inventory_spec_out, inventory_spec)
        _write(args.plan_out, plan)
        _write(args.receipt_out, receipt)
        return 0
    if args.command == "validate":
        validate_receipt(_load_json(args.receipt))
        return 0
    raise CorpusS3MaterializationError(
        "choose compile, validate, or --self-test"
    )


if __name__ == "__main__":
    raise SystemExit(main())
