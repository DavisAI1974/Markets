#!/usr/bin/env python3
"""Run the guarded historical executor against attribution-bound readiness v33."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v28 as v28
import ng_historical_refinement_readiness_v33 as readiness

SUGGESTED_ENTRYPOINTS: dict[str, tuple[str, ...]] = {
    **v28.SUGGESTED_ENTRYPOINTS,
    "g15_attribution_bound_publication": (
        "python",
        "ng_g15_attribution_bound_publication_gate.py",
    ),
}


def _check_v33_plan_contract(plan: Mapping[str, Any]) -> None:
    stages = list(plan.get("stages") or [])
    if len(stages) != len(readiness.STAGES):
        raise legacy_executor.HistoricalRefinementExecutionError(
            "readiness-v33 execution plan stage count mismatch"
        )
    for spec, step in zip(readiness.STAGES, stages):
        if step.get("key") != spec.key:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v33 stage order mismatch"
            )
        if step.get("expected_output") != spec.filename:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v33 expected output mismatch"
            )
        expected_entrypoint = list(SUGGESTED_ENTRYPOINTS.get(spec.key, ()))
        if step.get("suggested_entrypoint") != expected_entrypoint:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v33 suggested entrypoint mismatch"
            )

    keys = [str(step.get("key")) for step in stages]
    publication_index = keys.index("g15_publication")
    if keys[publication_index : publication_index + 3] != [
        "g15_publication",
        "g15_attribution_bound_publication",
        "g15_counterfactual_lesson_gate",
    ]:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "attribution-bound publication must remain between publication and lessons"
        )

    publication = stages[publication_index]
    if publication.get("requires_fixed_outcomes") is not True:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "G15 publication must remain behind the fixed-outcome boundary"
        )

    bound = stages[publication_index + 1]
    if bound.get("expected_output") != "g15_attribution_bound_publication_gate.json":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "attribution-bound publication artifact was substituted"
        )
    if bound.get("suggested_entrypoint") != [
        "python",
        "ng_g15_attribution_bound_publication_gate.py",
    ]:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "attribution-bound publication entrypoint mismatch"
        )
    if bound.get("requires_fixed_outcomes") is not True:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "attribution-bound publication must remain post-outcome"
        )

    lesson = stages[publication_index + 2]
    if lesson.get("requires_fixed_outcomes") is not True:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "G15 scored lesson adjudication must remain post-outcome"
        )


@contextmanager
def _v33_context() -> Iterator[None]:
    old_readiness = legacy_executor.readiness
    old_entrypoints = legacy_executor.SUGGESTED_ENTRYPOINTS
    old_validate = legacy_executor.validate_plan

    def guarded_validate(plan: Mapping[str, Any]) -> None:
        old_validate(plan)
        _check_v33_plan_contract(plan)

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
    with _v33_context():
        return legacy_executor.build_plan(*args, **kwargs)


def validate_plan(plan: Mapping[str, Any]) -> None:
    with _v33_context():
        legacy_executor.validate_plan(plan)


def configure_stage(
    plan: Mapping[str, Any],
    stage_key: str,
    argv: Sequence[str],
    **kwargs: Any,
) -> dict[str, Any]:
    with _v33_context():
        return legacy_executor.configure_stage(plan, stage_key, argv, **kwargs)


def run_next(*args: Any, **kwargs: Any) -> dict[str, Any]:
    with _v33_context():
        return legacy_executor.run_next(*args, **kwargs)


def validate_ledger(ledger: Mapping[str, Any]) -> None:
    with _v33_context():
        legacy_executor.validate_ledger(ledger)


def main() -> int:
    with _v33_context():
        return legacy_executor.main()


PLAN_SCHEMA = legacy_executor.PLAN_SCHEMA
LEDGER_SCHEMA = legacy_executor.LEDGER_SCHEMA
HistoricalRefinementExecutionError = legacy_executor.HistoricalRefinementExecutionError


if __name__ == "__main__":
    raise SystemExit(main())
