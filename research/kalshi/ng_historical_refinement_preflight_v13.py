#!/usr/bin/env python3
"""Bind branch-guarded execution to dual-inspection readiness v16."""
from __future__ import annotations

import copy
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

import ng_historical_refinement_executor_v13 as executor
import ng_historical_refinement_preflight as legacy
import ng_historical_refinement_preflight_v12 as v12
import ng_historical_refinement_readiness_v16 as readiness

SCHEMA = "ng_historical_refinement_preflight.v13"
EXECUTOR_CONTRACT = "ng_historical_refinement_executor_v13"
READINESS_CONTRACT = readiness.SCHEMA
STAGE_CONTRACT = [
    {
        "key": spec.key,
        "filename": spec.filename,
        "schema": spec.schema,
        "pre_outcome": bool(spec.pre_outcome),
    }
    for spec in readiness.STAGES
]
STAGE_ORDER = [row["key"] for row in STAGE_CONTRACT]
STAGE_CONTRACT_FINGERPRINT = legacy._fingerprint(STAGE_CONTRACT)


class HistoricalRefinementPreflightV13Error(RuntimeError):
    pass


@contextmanager
def _v16_context() -> Iterator[None]:
    saved = (
        v12.executor,
        v12.readiness,
        v12.EXECUTOR_CONTRACT,
        v12.READINESS_CONTRACT,
        v12.STAGE_CONTRACT,
        v12.STAGE_ORDER,
        v12.STAGE_CONTRACT_FINGERPRINT,
    )
    v12.executor = executor
    v12.readiness = readiness
    v12.EXECUTOR_CONTRACT = EXECUTOR_CONTRACT
    v12.READINESS_CONTRACT = READINESS_CONTRACT
    v12.STAGE_CONTRACT = STAGE_CONTRACT
    v12.STAGE_ORDER = STAGE_ORDER
    v12.STAGE_CONTRACT_FINGERPRINT = STAGE_CONTRACT_FINGERPRINT
    try:
        yield
    finally:
        (
            v12.executor,
            v12.readiness,
            v12.EXECUTOR_CONTRACT,
            v12.READINESS_CONTRACT,
            v12.STAGE_CONTRACT,
            v12.STAGE_ORDER,
            v12.STAGE_CONTRACT_FINGERPRINT,
        ) = saved


def _base_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    prior = base.pop("v12_preflight_fingerprint", None)
    for field in (
        "execution_plan_v16_validated",
        "dual_inspection_lanes_required",
        "broad_definition_byte_binding_required",
        "target_slice_inspection_required_before_basis",
        "target_slice_receipt_cannot_satisfy_broad_scope",
        "broad_receipt_cannot_satisfy_basis_regeneration",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = v12.SCHEMA
    base["fingerprint"] = prior
    return base


def _check_plan(plan: Mapping[str, Any]) -> None:
    executor.validate_plan(plan)
    rows = [row for row in plan.get("stages") or [] if isinstance(row, Mapping)]
    keys = [str(row.get("key")) for row in rows]
    if keys != STAGE_ORDER:
        raise HistoricalRefinementPreflightV13Error(
            "embedded plan does not use readiness-v16 stage order"
        )
    positions = {key: keys.index(key) for key in (
        "corpus_coverage",
        "corpus_definition_byte_binding",
        "target_slice_coverage",
        "basis_inventory_regeneration",
        "broad_corpus_scope",
        "g15_exact_replay",
    )}
    if not (
        positions["corpus_coverage"]
        < positions["corpus_definition_byte_binding"]
        < positions["target_slice_coverage"]
        < positions["basis_inventory_regeneration"]
        < positions["broad_corpus_scope"]
        < positions["g15_exact_replay"]
    ):
        raise HistoricalRefinementPreflightV13Error(
            "dual inspection lanes are not ordered before basis and G15 replay"
        )
    by_key = {str(row.get("key")): row for row in rows}
    for key in ("corpus_definition_byte_binding", "target_slice_coverage"):
        if by_key[key].get("requires_fixed_outcomes") is not False:
            raise HistoricalRefinementPreflightV13Error(
                f"{key} must remain pre-outcome"
            )


def _finalize(plan: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, Any]:
    _check_plan(plan)
    with _v16_context():
        v12.validate_receipt(base)
    result = copy.deepcopy(dict(base))
    result["schema"] = SCHEMA
    result["v12_preflight_fingerprint"] = base["fingerprint"]
    result["executor_contract"] = EXECUTOR_CONTRACT
    result["readiness_contract"] = READINESS_CONTRACT
    result["readiness_stage_contract"] = copy.deepcopy(STAGE_CONTRACT)
    result["readiness_stage_contract_fingerprint"] = STAGE_CONTRACT_FINGERPRINT
    result["execution_plan_snapshot"] = copy.deepcopy(dict(plan))
    result["execution_plan_v16_validated"] = True
    result["dual_inspection_lanes_required"] = True
    result["broad_definition_byte_binding_required"] = True
    result["target_slice_inspection_required_before_basis"] = True
    result["target_slice_receipt_cannot_satisfy_broad_scope"] = True
    result["broad_receipt_cannot_satisfy_basis_regeneration"] = True
    result.pop("fingerprint", None)
    result["fingerprint"] = legacy._fingerprint(result)
    validate_receipt(result)
    return result


def execute_preflight(
    plan: Mapping[str, Any],
    ledger_path: Path,
    *,
    executor_runner: Callable[..., Mapping[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    _check_plan(plan)
    runner = executor.run_next if executor_runner is None else executor_runner
    with _v16_context():
        base = v12.execute_preflight(
            plan,
            ledger_path,
            executor_runner=runner,
            **kwargs,
        )
    return _finalize(plan, base)


def validate_receipt(receipt: Mapping[str, Any]) -> None:
    value = copy.deepcopy(dict(receipt))
    observed = value.pop("fingerprint", None)
    if value.get("schema") != SCHEMA or observed != legacy._fingerprint(value):
        raise HistoricalRefinementPreflightV13Error(
            "preflight v13 schema or fingerprint mismatch"
        )
    if value.get("executor_contract") != EXECUTOR_CONTRACT:
        raise HistoricalRefinementPreflightV13Error("executor contract mismatch")
    if value.get("readiness_contract") != READINESS_CONTRACT:
        raise HistoricalRefinementPreflightV13Error("readiness contract mismatch")
    if value.get("readiness_stage_contract") != STAGE_CONTRACT:
        raise HistoricalRefinementPreflightV13Error("stage contract mismatch")
    if value.get("readiness_stage_contract_fingerprint") != STAGE_CONTRACT_FINGERPRINT:
        raise HistoricalRefinementPreflightV13Error("stage fingerprint mismatch")
    for field in (
        "execution_plan_v16_validated",
        "dual_inspection_lanes_required",
        "broad_definition_byte_binding_required",
        "target_slice_inspection_required_before_basis",
        "target_slice_receipt_cannot_satisfy_broad_scope",
        "broad_receipt_cannot_satisfy_basis_regeneration",
    ):
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV13Error(
                f"mandatory field mismatch: {field}"
            )
    plan = value.get("execution_plan_snapshot")
    if not isinstance(plan, Mapping):
        raise HistoricalRefinementPreflightV13Error("exact plan snapshot is required")
    _check_plan(plan)
    if value.get("plan_fingerprint") != plan.get("fingerprint"):
        raise HistoricalRefinementPreflightV13Error("plan fingerprint mismatch")
    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("v12_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV13Error(
            "embedded v12 preflight fingerprint mismatch"
        )
    with _v16_context():
        v12.validate_receipt(base)


main = v12.main


if __name__ == "__main__":
    with _v16_context():
        raise SystemExit(main())
