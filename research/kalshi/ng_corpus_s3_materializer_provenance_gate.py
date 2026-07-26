#!/usr/bin/env python3
"""Bind exact S3 materialization to its complete runtime-observed inventory evidence.

The exact materializer receipt records the runtime-inventory fingerprint used during
materialization, but its standalone receipt does not embed the full paginated runtime
capture. This gate closes that provenance seam by recursively validating and embedding
both artifacts, then proving that the downloaded/reused bytes, exact S3 versions,
materialization specification, and downstream inspection plan all descend from the same
runtime-observed inventory capture.

The gate is historical-only and outcome-blind. It cannot mutate blind forecasts,
posterior state, ``knowledge/ng_brain.json``, CME SHADOW mode, brokerage, or options.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_corpus_s3_exact_materializer as exact_materializer
import ng_corpus_s3_runtime_observed_inventory_capture as runtime_capture

SCHEMA = "ng_corpus_s3_materializer_provenance_gate.v1"
READY_STATUS = "S3_RUNTIME_INVENTORY_AND_EXACT_MATERIALIZATION_PROVENANCE_BOUND"
BLOCKED_STATUS = "S3_RUNTIME_INVENTORY_AND_EXACT_MATERIALIZATION_PROVENANCE_BLOCKED"


class CorpusS3MaterializerProvenanceError(ValueError):
    """Raised when runtime-inventory/materialization lineage is unsafe."""


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
        raise CorpusS3MaterializerProvenanceError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise CorpusS3MaterializerProvenanceError(
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
            raise CorpusS3MaterializerProvenanceError(
                f"{label}: {field} must remain {expected!r}"
            )


def build_gate(
    runtime_receipt: Mapping[str, Any],
    exact_receipt: Mapping[str, Any],
    *,
    runtime_validator: Callable[[Mapping[str, Any]], Mapping[str, Any]] = runtime_capture.validate_receipt,
    materializer_validator: Callable[[Mapping[str, Any]], Mapping[str, Any]] = exact_materializer.validate_receipt,
) -> dict[str, Any]:
    """Recursively validate and bind runtime inventory to exact materialization."""

    try:
        runtime_value = copy.deepcopy(dict(runtime_validator(runtime_receipt)))
    except Exception as error:
        raise CorpusS3MaterializerProvenanceError(
            f"runtime-observed inventory receipt is invalid: {error}"
        ) from error
    try:
        exact_value = copy.deepcopy(dict(materializer_validator(exact_receipt)))
    except Exception as error:
        raise CorpusS3MaterializerProvenanceError(
            f"exact materializer receipt is invalid: {error}"
        ) from error

    _authority(runtime_value, label="runtime-observed inventory receipt")
    _authority(exact_value, label="exact materializer receipt")

    runtime_fp = str(runtime_value.get("receipt_fingerprint") or "")
    exact_fp = str(exact_value.get("receipt_fingerprint") or "")
    runtime_materialization_spec = runtime_value.get("materialization_spec")
    exact_source_spec = exact_value.get("source_spec")
    if not isinstance(runtime_materialization_spec, Mapping):
        raise CorpusS3MaterializerProvenanceError(
            "runtime-observed inventory lacks embedded materialization specification"
        )
    if not isinstance(exact_source_spec, Mapping):
        raise CorpusS3MaterializerProvenanceError(
            "exact materializer lacks embedded source specification"
        )

    runtime_spec_fp = str(
        runtime_value.get("materialization_spec_fingerprint") or ""
    )
    exact_spec_fp = str(exact_value.get("source_spec_fingerprint") or "")
    blockers: list[str] = []
    if runtime_value.get("status") != runtime_capture.READY_STATUS:
        blockers.append("RUNTIME_OBSERVED_INVENTORY_NOT_READY")
    if exact_value.get("status") != exact_materializer.READY_STATUS:
        blockers.append("EXACT_MATERIALIZATION_NOT_READY")
    if list(runtime_value.get("blockers") or []):
        blockers.append("RUNTIME_OBSERVED_INVENTORY_HAS_BLOCKERS")
    if list(exact_value.get("blockers") or []):
        blockers.append("EXACT_MATERIALIZATION_HAS_BLOCKERS")
    if exact_value.get("runtime_inventory_capture_fingerprint") != runtime_fp:
        blockers.append("EXACT_MATERIALIZER_RUNTIME_CAPTURE_FINGERPRINT_MISMATCH")
    if exact_source_spec != dict(runtime_materialization_spec):
        blockers.append("MATERIALIZATION_SPEC_CONTENT_MISMATCH")
    if runtime_spec_fp != _fp(dict(runtime_materialization_spec)):
        blockers.append("RUNTIME_MATERIALIZATION_SPEC_FINGERPRINT_MISMATCH")
    if exact_spec_fp != _fp(dict(exact_source_spec)):
        blockers.append("EXACT_MATERIALIZATION_SPEC_FINGERPRINT_MISMATCH")
    if exact_spec_fp != runtime_spec_fp:
        blockers.append("RUNTIME_TO_EXACT_MATERIALIZATION_SPEC_LINEAGE_MISMATCH")
    if exact_value.get("identity_from_s3_keys_inferred") is not False:
        blockers.append("IDENTITY_INFERRED_FROM_S3_KEYS")
    if exact_value.get("exact_version_get_object_required") is not True:
        blockers.append("EXACT_VERSION_GET_OBJECT_NOT_REQUIRED")
    if exact_value.get("checksum_mode_enabled") is not True:
        blockers.append("CHECKSUM_MODE_NOT_ENABLED")
    if exact_value.get("atomic_local_replacement_required") is not True:
        blockers.append("ATOMIC_LOCAL_REPLACEMENT_NOT_REQUIRED")
    if not exact_value.get("source_materializations_fingerprint"):
        blockers.append("SOURCE_MATERIALIZATION_EVIDENCE_MISSING")
    if not isinstance(exact_value.get("source_count"), int) or int(
        exact_value.get("source_count") or 0
    ) <= 0:
        blockers.append("MATERIALIZED_SOURCE_COUNT_NOT_POSITIVE")
    for field, blocker in (
        (
            "downstream_materialization_receipt_fingerprint",
            "DOWNSTREAM_MATERIALIZATION_ATTESTATION_MISSING",
        ),
        (
            "canonical_inventory_spec_fingerprint",
            "CANONICAL_INVENTORY_SPEC_FINGERPRINT_MISSING",
        ),
        (
            "materialization_evidence_fingerprint",
            "MATERIALIZATION_EVIDENCE_FINGERPRINT_MISSING",
        ),
        ("plan_fingerprint", "DOWNSTREAM_INSPECTION_PLAN_FINGERPRINT_MISSING"),
        (
            "inventory_compiler_receipt_fingerprint",
            "INVENTORY_COMPILER_RECEIPT_FINGERPRINT_MISSING",
        ),
    ):
        if not exact_value.get(field):
            blockers.append(blocker)

    blockers = sorted(set(blockers))
    lineage = {
        "runtime_capture_receipt_fingerprint": runtime_fp,
        "runtime_materialization_spec_fingerprint": runtime_spec_fp,
        "exact_materializer_receipt_fingerprint": exact_fp,
        "exact_materializer_runtime_capture_fingerprint": exact_value.get(
            "runtime_inventory_capture_fingerprint"
        ),
        "exact_materialization_spec_fingerprint": exact_spec_fp,
        "source_materializations_fingerprint": exact_value.get(
            "source_materializations_fingerprint"
        ),
        "source_count": exact_value.get("source_count"),
        "downstream_materialization_receipt_fingerprint": exact_value.get(
            "downstream_materialization_receipt_fingerprint"
        ),
        "canonical_inventory_spec_fingerprint": exact_value.get(
            "canonical_inventory_spec_fingerprint"
        ),
        "materialization_evidence_fingerprint": exact_value.get(
            "materialization_evidence_fingerprint"
        ),
        "plan_fingerprint": exact_value.get("plan_fingerprint"),
        "inventory_compiler_receipt_fingerprint": exact_value.get(
            "inventory_compiler_receipt_fingerprint"
        ),
    }
    status = READY_STATUS if not blockers else BLOCKED_STATUS
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "runtime_capture_receipt": runtime_value,
        "runtime_capture_receipt_fingerprint": runtime_fp,
        "exact_materializer_receipt": exact_value,
        "exact_materializer_receipt_fingerprint": exact_fp,
        "runtime_materialization_spec_fingerprint": runtime_spec_fp,
        "exact_materialization_spec_fingerprint": exact_spec_fp,
        "exact_materializer_runtime_inventory_capture_fingerprint": exact_value.get(
            "runtime_inventory_capture_fingerprint"
        ),
        "source_materializations_fingerprint": exact_value.get(
            "source_materializations_fingerprint"
        ),
        "source_count": exact_value.get("source_count"),
        "downstream_materialization_receipt_fingerprint": exact_value.get(
            "downstream_materialization_receipt_fingerprint"
        ),
        "canonical_inventory_spec_fingerprint": exact_value.get(
            "canonical_inventory_spec_fingerprint"
        ),
        "materialization_evidence_fingerprint": exact_value.get(
            "materialization_evidence_fingerprint"
        ),
        "plan_fingerprint": exact_value.get("plan_fingerprint"),
        "inventory_compiler_receipt_fingerprint": exact_value.get(
            "inventory_compiler_receipt_fingerprint"
        ),
        "provenance_lineage": lineage,
        "provenance_lineage_fingerprint": _fp(lineage),
        "runtime_capture_recursively_validated": True,
        "exact_materializer_recursively_validated": True,
        "complete_runtime_inventory_embedded": True,
        "exact_materialized_bytes_bound_to_runtime_inventory": status == READY_STATUS,
        "identity_from_s3_keys_inferred": False,
        "blockers": blockers,
        "next_action": (
            "RUN_BYTE_LEVEL_CORPUS_INSPECTION"
            if status == READY_STATUS
            else "REPAIR_RUNTIME_INVENTORY_MATERIALIZATION_PROVENANCE_BLOCKERS"
        ),
        **_authority_fields(),
    }
    receipt["fingerprint"] = _fp(receipt)
    return receipt


def validate_gate(
    value: Mapping[str, Any],
    *,
    runtime_validator: Callable[[Mapping[str, Any]], Mapping[str, Any]] = runtime_capture.validate_receipt,
    materializer_validator: Callable[[Mapping[str, Any]], Mapping[str, Any]] = exact_materializer.validate_receipt,
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise CorpusS3MaterializerProvenanceError(
            "materializer provenance gate schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="materializer provenance gate")
    runtime_receipt = checked.get("runtime_capture_receipt")
    exact_receipt = checked.get("exact_materializer_receipt")
    if not isinstance(runtime_receipt, Mapping) or not isinstance(exact_receipt, Mapping):
        raise CorpusS3MaterializerProvenanceError(
            "materializer provenance gate lacks embedded upstream receipts"
        )
    expected = build_gate(
        runtime_receipt,
        exact_receipt,
        runtime_validator=runtime_validator,
        materializer_validator=materializer_validator,
    )
    if checked != expected:
        raise CorpusS3MaterializerProvenanceError(
            "materializer provenance gate does not reconstruct deterministically"
        )
    return copy.deepcopy(dict(value))


def build_from_paths(
    *, runtime_capture_path: Path, exact_materializer_path: Path, out: Path
) -> dict[str, Any]:
    receipt = build_gate(_load(runtime_capture_path), _load(exact_materializer_path))
    _write(out, receipt)
    validate_gate(receipt)
    return receipt


def _selftest() -> int:
    authority = _authority_fields()
    spec = {"schema": "selftest.materialization", "corpora": [], **authority}
    runtime = {
        "status": runtime_capture.READY_STATUS,
        "receipt_fingerprint": "r" * 64,
        "materialization_spec": spec,
        "materialization_spec_fingerprint": _fp(spec),
        "blockers": [],
        **authority,
    }
    exact = {
        "status": exact_materializer.READY_STATUS,
        "receipt_fingerprint": "e" * 64,
        "runtime_inventory_capture_fingerprint": runtime["receipt_fingerprint"],
        "source_spec": spec,
        "source_spec_fingerprint": _fp(spec),
        "source_materializations_fingerprint": "s" * 64,
        "source_count": 2,
        "downstream_materialization_receipt_fingerprint": "d" * 64,
        "canonical_inventory_spec_fingerprint": "c" * 64,
        "materialization_evidence_fingerprint": "m" * 64,
        "plan_fingerprint": "p" * 64,
        "inventory_compiler_receipt_fingerprint": "i" * 64,
        "identity_from_s3_keys_inferred": False,
        "exact_version_get_object_required": True,
        "checksum_mode_enabled": True,
        "atomic_local_replacement_required": True,
        "blockers": [],
        **authority,
    }
    passthrough = lambda item: copy.deepcopy(dict(item))
    ready = build_gate(
        runtime,
        exact,
        runtime_validator=passthrough,
        materializer_validator=passthrough,
    )
    assert ready["status"] == READY_STATUS
    validate_gate(
        ready,
        runtime_validator=passthrough,
        materializer_validator=passthrough,
    )

    mismatched = copy.deepcopy(exact)
    mismatched["runtime_inventory_capture_fingerprint"] = "x" * 64
    blocked = build_gate(
        runtime,
        mismatched,
        runtime_validator=passthrough,
        materializer_validator=passthrough,
    )
    assert blocked["status"] == BLOCKED_STATUS
    assert "EXACT_MATERIALIZER_RUNTIME_CAPTURE_FINGERPRINT_MISMATCH" in blocked[
        "blockers"
    ]
    print("[ng_corpus_s3_materializer_provenance_gate] selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--runtime-capture", type=Path, required=True)
    build_parser.add_argument("--exact-materializer", type=Path, required=True)
    build_parser.add_argument("--out", type=Path, required=True)
    subparsers.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.command == "selftest":
        return _selftest()
    receipt = build_from_paths(
        runtime_capture_path=args.runtime_capture,
        exact_materializer_path=args.exact_materializer,
        out=args.out,
    )
    print(json.dumps({"out": str(args.out), "status": receipt["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
