#!/usr/bin/env python3
"""Fail-closed runtime receipt for every governing H module and I record.

This preflight does not pretend catalog presence is integration.  Each H module
is imported in the launch process and its required public API is checked callable;
the focused verification test identity is recorded.  Each JSON authority record
is parsed and every embedded file SHA-256 is reverified against current bytes.
"""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "FRANKIE_V4_AUTHORITY_RUNTIME_VALIDATION_V1_20260824"

H_RUNTIME_MODULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ng_exhaustion_v4_causal_clock", ("make_receipt", "validate_availability_chain")),
    ("ng_exhaustion_v4_causal_entry_adapter", ("authorize_v4_evaluation",)),
    ("ng_exhaustion_v4_state_assembler", ("CausalStateAssembler",)),
    ("ng_exhaustion_v4_mechanics", ("make_state_row", "validate_state_movie", "recompute_first_lock")),
    ("ng_exhaustion_v4_detector_intensity", ("resolve_detector_intensity",)),
    ("ng_exhaustion_v4_detector_intensity_semantics", ("prove_native_stream", "explicit_proxy")),
    ("ng_exhaustion_v4_history_support", ("validate_native_manifest", "make_session_coverage")),
    ("ng_exhaustion_v4_lock_outcome", ("recompute_lock_outcome",)),
    ("ng_exhaustion_v4_adapter_integration", ("IntegratedV4Adapter",)),
    ("ng_exhaustion_v4_end_to_end_adapter", ("run_isolated_adapter", "reconcile_isolated_adapter")),
    ("ng_exhaustion_v4_unified_runtime", ("UnifiedV4Engine", "UnifiedV4Orchestrator", "UnifiedV4Reconciler")),
    ("ng_exhaustion_v4_exact_candidate_freeze", ("freeze_exact_candidate",)),
    ("ng_exhaustion_v4_gate_verifier", ("verify_prelaunch_gates",)),
    ("ng_exhaustion_v4_pilot_chunk_guard", ("authorize_dispatch", "reconcile_chunk")),
    ("ng_exhaustion_v4_pilot_chunk_guardrail", ("make_manifest", "reconcile_children")),
)

I_AUTHORITY_RECORDS: tuple[str, ...] = (
    "research/kalshi/NG_EXHAUSTION_V4_MECHANICAL_CONTRACT_RECEIPT_20260820.json",
    "research/kalshi/NG_EXHAUSTION_V4_STATE_ASSEMBLER_RECEIPT_20260820.json",
    "research/kalshi/NG_EXHAUSTION_V4_UNIFIED_RUNTIME_RECEIPT_20260820.json",
    "research/kalshi/NG_EXHAUSTION_V4_PROTECTED_BASELINE_20260821.json",
    "research/NG_EXHAUSTION_V4_CURRENT_STATE_DECISION_20260822.md",
    "research/kalshi/FRANKIE_V4_CURRENT_STATE_AUDIT_20260822.md",
    "research/kalshi/FRANKIE_V4_UNIFIED_FRAMEWORK_AUDIT_20260820.md",
)


class V4AuthorityValidationError(ValueError):
    """A governing module, API, test identity, record, or declared hash drifted."""


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _focused_test(root: Path, module_name: str) -> Path:
    exact = root / f"research/kalshi/tests/test_{module_name}.py"
    if exact.is_file():
        return exact
    raise V4AuthorityValidationError(f"focused H verification test is missing: {module_name}")


def _validate_declared_hashes(root: Path, payload: Mapping[str, Any], record: str) -> int:
    declared = payload.get("files", payload.get("files_sha256", {}))
    if not isinstance(declared, Mapping):
        raise V4AuthorityValidationError(f"I record declared hash map is invalid: {record}")
    verified = 0
    for relative, expected in declared.items():
        path = root / str(relative)
        if not path.is_file() or _file_sha(path) != str(expected).lower():
            raise V4AuthorityValidationError(f"I record embedded file identity drift: {relative}")
        verified += 1
    return verified


def validate_v4_authority_runtime(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    h_rows: list[dict[str, Any]] = []
    for module_name, symbols in H_RUNTIME_MODULES:
        source = root / f"research/kalshi/{module_name}.py"
        if not source.is_file():
            raise V4AuthorityValidationError(f"H runtime module is missing: {module_name}")
        module = importlib.import_module(f"research.kalshi.{module_name}")
        missing = [name for name in symbols if not callable(getattr(module, name, None))]
        if missing:
            raise V4AuthorityValidationError(f"H runtime API drift in {module_name}: {missing}")
        test = _focused_test(root, module_name)
        h_rows.append(
            {
                "path": str(source.relative_to(root)),
                "source_sha256": _file_sha(source),
                "required_callable_symbols": list(symbols),
                "focused_test_path": str(test.relative_to(root)),
                "focused_test_sha256": _file_sha(test),
                "disposition": "PREFLIGHT_API_SURFACE_ONLY_NOT_OPERATIONAL_PROOF",
            }
        )

    i_rows: list[dict[str, Any]] = []
    embedded_hashes = 0
    for relative in I_AUTHORITY_RECORDS:
        path = root / relative
        if not path.is_file() or path.stat().st_size <= 0:
            raise V4AuthorityValidationError(f"I authority record is missing or empty: {relative}")
        verified = 0
        if path.suffix == ".json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, TypeError, ValueError) as exc:
                raise V4AuthorityValidationError(f"I receipt JSON is invalid: {relative}") from exc
            if not isinstance(payload, Mapping) or not str(payload.get("schema") or "").strip():
                raise V4AuthorityValidationError(f"I receipt schema is absent: {relative}")
            verified = _validate_declared_hashes(root, payload, relative)
        embedded_hashes += verified
        i_rows.append(
            {
                "path": relative,
                "sha256": _file_sha(path),
                "embedded_file_hashes_verified": verified,
                "status": "CURRENT_BYTES_VALIDATED",
            }
        )
    core = {
        "schema": SCHEMA,
        "h_module_count": len(h_rows),
        "i_record_count": len(i_rows),
        "embedded_file_hashes_verified": embedded_hashes,
        "all_required_api_symbols_callable": True,
        "all_declared_receipt_hashes_current": True,
        "operational_execution_required_per_prefix": True,
        "h_modules": h_rows,
        "i_records": i_rows,
    }
    return {**core, "receipt_hash": _hash(core)}


__all__ = [
    "H_RUNTIME_MODULES",
    "I_AUTHORITY_RECORDS",
    "V4AuthorityValidationError",
    "validate_v4_authority_runtime",
]
