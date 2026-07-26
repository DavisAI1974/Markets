#!/usr/bin/env python3
"""Run the guarded historical executor against attribution-bound G16 lock readiness v37."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v32 as v32
import ng_historical_refinement_readiness_v37 as readiness

SUGGESTED_ENTRYPOINTS: dict[str, tuple[str, ...]] = {
    **v32.SUGGESTED_ENTRYPOINTS,
    "g16_attribution_bound_curve_lock": (
        "python",
        "ng_g16_attribution_bound_curve_lock_gate.py",
    ),
}


def _check_v37_plan_contract(plan: Mapping[str, Any]) -> None:
    stages = list(plan.get("stages") or [])
    if len(stages) != len(readiness.STAGES):
        raise legacy_executor.HistoricalRefinementExecutionError(
            "readiness-v37 execution plan stage count mismatch"
        )
    for spec, step in zip(readiness.STAGES, stages):
        if step.get("key") != spec.key:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v37 stage order mismatch"
            )
        if step.get("expected_output") != spec.filename:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v37 expected output mismatch"
            )
        expected_entrypoint = list(SUGGESTED_ENTRYPOINTS.get(spec.key, ()))
        if step.get("suggested_entrypoint") != expected_entrypoint:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v37 suggested entrypoint mismatch"
            )

    keys = [str(step.get("key")) for step in stages]
    start = keys.index("g16_attribution_bound_curve_authorization")
    expected = [
        "g16_attribution_bound_curve_authorization",
        "g16_counterfactual_curve_lock",
        "g16_attribution_bound_curve_lock",
        "g16_counterfactual_publication",
    ]
    if keys[start : start + 4] != expected:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "attribution-bound G16 lock must remain between legacy lock and publication"
        )

    bound_lock = stages[start + 2]
    if bound_lock.get("expected_output") != "g16_attribution_bound_curve_lock.json":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "attribution-bound G16 lock artifact was substituted"
        )
    if bound_lock.get("suggested_entrypoint") != [
        "python",
        "ng_g16_attribution_bound_curve_lock_gate.py",
    ]:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "attribution-bound G16 lock entrypoint mismatch"
        )

    for offset, label in (
        (0, "attribution-bound curve authorization"),
        (1, "legacy G16 curve lock"),
        (2, "attribution-bound G16 curve lock"),
        (3, "fixed G16 publication"),
    ):
        if stages[start + offset].get("requires_fixed_outcomes") is not True:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{label} must disclose fixed G15 outcome use"
            )


@contextmanager
def _v37_context() -> Iterator[None]:
    old_readiness = legacy_executor.readiness
    old_entrypoints = legacy_executor.SUGGESTED_ENTRYPOINTS
    old_validate = legacy_executor.validate_plan

    def guarded_validate(plan: Mapping[str, Any]) -> None:
        old_validate(plan)
        _check_v37_plan_contract(plan)

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
    with _v37_context():
        return legacy_executor.build_plan(*args, **kwargs)


def validate_plan(plan: Mapping[str, Any]) -> None:
    with _v37_context():
        legacy_executor.validate_plan(plan)


def configure_stage(
    plan: Mapping[str, Any],
    stage_key: str,
    argv: Sequence[str],
    **kwargs: Any,
) -> dict[str, Any]:
    with _v37_context():
        return legacy_executor.configure_stage(plan, stage_key, argv, **kwargs)


def run_next(*args: Any, **kwargs: Any) -> dict[str, Any]:
    with _v37_context():
        return legacy_executor.run_next(*args, **kwargs)


def validate_ledger(ledger: Mapping[str, Any]) -> None:
    with _v37_context():
        legacy_executor.validate_ledger(ledger)


def main() -> int:
    with _v37_context():
        return legacy_executor.main()


PLAN_SCHEMA = legacy_executor.PLAN_SCHEMA
LEDGER_SCHEMA = legacy_executor.LEDGER_SCHEMA
HistoricalRefinementExecutionError = legacy_executor.HistoricalRefinementExecutionError


if __name__ == "__main__":
    raise SystemExit(main())
