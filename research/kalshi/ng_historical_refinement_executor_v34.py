#!/usr/bin/env python3
"""Run the guarded historical executor against attribution-bound G16 publication v38."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v33 as v33
import ng_historical_refinement_readiness_v38 as readiness

SUGGESTED_ENTRYPOINTS: dict[str, tuple[str, ...]] = {
    **v33.SUGGESTED_ENTRYPOINTS,
    "g16_attribution_bound_publication": (
        "python",
        "ng_g16_attribution_bound_publication_gate.py",
    ),
}


def _check_v38_plan_contract(plan: Mapping[str, Any]) -> None:
    stages = list(plan.get("stages") or [])
    if len(stages) != len(readiness.STAGES):
        raise legacy_executor.HistoricalRefinementExecutionError(
            "readiness-v38 execution plan stage count mismatch"
        )
    for spec, step in zip(readiness.STAGES, stages):
        if step.get("key") != spec.key:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v38 stage order mismatch"
            )
        if step.get("expected_output") != spec.filename:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v38 expected output mismatch"
            )
        expected_entrypoint = list(SUGGESTED_ENTRYPOINTS.get(spec.key, ()))
        if step.get("suggested_entrypoint") != expected_entrypoint:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v38 suggested entrypoint mismatch"
            )

    keys = [str(step.get("key")) for step in stages]
    expected_tail = [
        "g16_counterfactual_curve_lock",
        "g16_attribution_bound_curve_lock",
        "g16_counterfactual_publication",
        "g16_attribution_bound_publication",
    ]
    if keys[-4:] != expected_tail:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "G16 lock/publication attribution binding chronology changed"
        )
    gate = stages[-1]
    if gate.get("expected_output") != "g16_attribution_bound_publication_gate.json":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "attribution-bound G16 publication artifact was substituted"
        )
    if gate.get("suggested_entrypoint") != [
        "python",
        "ng_g16_attribution_bound_publication_gate.py",
    ]:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "attribution-bound G16 publication entrypoint mismatch"
        )
    for offset, label in (
        (-3, "legacy G16 curve lock"),
        (-2, "attribution-bound G16 curve lock"),
        (-1, "fixed G16 publication"),
        (0, "attribution-bound fixed G16 publication"),
    ):
        row = stages[len(stages) - 1 + offset]
        if row.get("requires_fixed_outcomes") is not True:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{label} must remain behind the fixed G15 outcome boundary"
            )


@contextmanager
def _v38_context() -> Iterator[None]:
    old_readiness = legacy_executor.readiness
    old_entrypoints = legacy_executor.SUGGESTED_ENTRYPOINTS
    old_validate = legacy_executor.validate_plan

    def guarded_validate(plan: Mapping[str, Any]) -> None:
        old_validate(plan)
        _check_v38_plan_contract(plan)

    legacy_executor.readiness = readiness
    legacy_executor.SUGGESTED_ENTRYPOINTS = SUGGESTED_ENTRYPOINTS
    legacy_executor.validate_plan = guarded_validate
    try:
        yield
    finally:
        legacy_executor.readiness = old_readiness
        legacy_executor.SUGGESTED_ENTRYPOINTS = old_entrypoints
        legacy_executor.validate_plan = old_validate


def build_plan(*args: Any, **kwargs: Any) -> dict[str, Any]:
    with _v38_context():
        return legacy_executor.build_plan(*args, **kwargs)


def validate_plan(plan: Mapping[str, Any]) -> None:
    with _v38_context():
        legacy_executor.validate_plan(plan)


def configure_stage(
    plan: Mapping[str, Any],
    stage_key: str,
    argv: Sequence[str],
    **kwargs: Any,
) -> dict[str, Any]:
    with _v38_context():
        return legacy_executor.configure_stage(plan, stage_key, argv, **kwargs)


def execute_next(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Execute one v38 stage using the real base executor entrypoint."""
    with _v38_context():
        return legacy_executor.execute_next(*args, **kwargs)


def run_next(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Compatibility alias retained for existing versioned preflight wrappers."""
    return execute_next(*args, **kwargs)


def validate_ledger(ledger: Mapping[str, Any], plan: Mapping[str, Any]) -> None:
    with _v38_context():
        legacy_executor.validate_ledger(ledger, plan)


def main() -> int:
    with _v38_context():
        return legacy_executor.main()


PLAN_SCHEMA = legacy_executor.PLAN_SCHEMA
LEDGER_SCHEMA = legacy_executor.LEDGER_SCHEMA
HistoricalRefinementExecutionError = legacy_executor.HistoricalRefinementExecutionError


if __name__ == "__main__":
    raise SystemExit(main())
