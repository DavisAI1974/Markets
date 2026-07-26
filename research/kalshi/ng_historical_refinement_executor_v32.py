#!/usr/bin/env python3
"""Run the guarded historical executor against attribution-bound G16 curve readiness v36."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v31 as v31
import ng_historical_refinement_readiness_v36 as readiness

SUGGESTED_ENTRYPOINTS: dict[str, tuple[str, ...]] = {
    **v31.SUGGESTED_ENTRYPOINTS,
    "g16_attribution_bound_curve_authorization": (
        "python",
        "ng_g16_attribution_bound_curve_authorization_gate.py",
    ),
}


def _check_v36_plan_contract(plan: Mapping[str, Any]) -> None:
    stages = list(plan.get("stages") or [])
    if len(stages) != len(readiness.STAGES):
        raise legacy_executor.HistoricalRefinementExecutionError(
            "readiness-v36 execution plan stage count mismatch"
        )
    for spec, step in zip(readiness.STAGES, stages):
        if step.get("key") != spec.key:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v36 stage order mismatch"
            )
        if step.get("expected_output") != spec.filename:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v36 expected output mismatch"
            )
        expected_entrypoint = list(SUGGESTED_ENTRYPOINTS.get(spec.key, ()))
        if step.get("suggested_entrypoint") != expected_entrypoint:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v36 suggested entrypoint mismatch"
            )

    keys = [str(step.get("key")) for step in stages]
    curve_index = keys.index("g16_counterfactual_curve_authorization")
    if keys[curve_index : curve_index + 3] != [
        "g16_counterfactual_curve_authorization",
        "g16_attribution_bound_curve_authorization",
        "g16_counterfactual_curve_lock",
    ]:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "attribution-bound G16 curve authorization must remain between legacy curve and lock"
        )

    legacy_curve = stages[curve_index]
    if legacy_curve.get("requires_fixed_outcomes") is not True:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "legacy G16 counterfactual curve must disclose fixed G15 outcome use"
        )

    bound = stages[curve_index + 1]
    if bound.get("expected_output") != "g16_attribution_bound_curve_authorization.json":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "attribution-bound G16 curve artifact was substituted"
        )
    if bound.get("suggested_entrypoint") != [
        "python",
        "ng_g16_attribution_bound_curve_authorization_gate.py",
    ]:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "attribution-bound G16 curve entrypoint mismatch"
        )
    if bound.get("requires_fixed_outcomes") is not True:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "attribution-bound G16 curve authorization must remain fixed-G15-outcome"
        )

    lock = stages[curve_index + 2]
    if lock.get("requires_fixed_outcomes") is not True:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "G16 curve lock must disclose fixed G15 outcome lineage while remaining G16-outcome-blind"
        )


@contextmanager
def _v36_context() -> Iterator[None]:
    old_readiness = legacy_executor.readiness
    old_entrypoints = legacy_executor.SUGGESTED_ENTRYPOINTS
    old_validate = legacy_executor.validate_plan

    def guarded_validate(plan: Mapping[str, Any]) -> None:
        old_validate(plan)
        _check_v36_plan_contract(plan)

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
    with _v36_context():
        return legacy_executor.build_plan(*args, **kwargs)


def validate_plan(plan: Mapping[str, Any]) -> None:
    with _v36_context():
        legacy_executor.validate_plan(plan)


def configure_stage(
    plan: Mapping[str, Any],
    stage_key: str,
    argv: Sequence[str],
    **kwargs: Any,
) -> dict[str, Any]:
    with _v36_context():
        return legacy_executor.configure_stage(plan, stage_key, argv, **kwargs)


def run_next(*args: Any, **kwargs: Any) -> dict[str, Any]:
    with _v36_context():
        return legacy_executor.run_next(*args, **kwargs)


def validate_ledger(ledger: Mapping[str, Any]) -> None:
    with _v36_context():
        legacy_executor.validate_ledger(ledger)


def main() -> int:
    with _v36_context():
        return legacy_executor.main()


PLAN_SCHEMA = legacy_executor.PLAN_SCHEMA
LEDGER_SCHEMA = legacy_executor.LEDGER_SCHEMA
HistoricalRefinementExecutionError = legacy_executor.HistoricalRefinementExecutionError


if __name__ == "__main__":
    raise SystemExit(main())
