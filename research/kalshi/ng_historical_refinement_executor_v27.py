#!/usr/bin/env python3
"""Run the guarded historical executor against prepared-identity readiness v31."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v26 as v26
import ng_historical_refinement_readiness_v31 as readiness

SUGGESTED_ENTRYPOINTS: dict[str, tuple[str, ...]] = {
    **v26.SUGGESTED_ENTRYPOINTS,
    "g15_prepared_normalized_identity": (
        "python",
        "ng_g15_prepared_normalized_identity_guard.py",
        "build",
    ),
}


def _check_v31_plan_contract(plan: Mapping[str, Any]) -> None:
    stages = list(plan.get("stages") or [])
    if len(stages) != len(readiness.STAGES):
        raise legacy_executor.HistoricalRefinementExecutionError(
            "readiness-v31 execution plan stage count mismatch"
        )
    for spec, step in zip(readiness.STAGES, stages):
        if step.get("key") != spec.key:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v31 stage order mismatch"
            )
        if step.get("expected_output") != spec.filename:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v31 expected output mismatch"
            )
        expected_entrypoint = list(SUGGESTED_ENTRYPOINTS.get(spec.key, ()))
        if step.get("suggested_entrypoint") != expected_entrypoint:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v31 suggested entrypoint mismatch"
            )

    keys = [step.get("key") for step in stages]
    catalog_index = keys.index("replay_catalog_export")
    if keys[catalog_index : catalog_index + 3] != [
        "replay_catalog_export",
        "g15_prepared_normalized_identity",
        "g15_exact_replay",
    ]:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "prepared normalized identity must remain between replay-catalog export and G15 replay"
        )
    guard = stages[catalog_index + 1]
    if guard.get("expected_output") != "g15_prepared_normalized_identity_guard.json":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "prepared normalized identity artifact was substituted"
        )
    if guard.get("suggested_entrypoint") != [
        "python",
        "ng_g15_prepared_normalized_identity_guard.py",
        "build",
    ]:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "prepared normalized identity entrypoint mismatch"
        )
    if guard.get("requires_fixed_outcomes") is not False:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "prepared normalized identity attestation must remain pre-outcome"
        )


@contextmanager
def _v31_context() -> Iterator[None]:
    old_readiness = legacy_executor.readiness
    old_entrypoints = legacy_executor.SUGGESTED_ENTRYPOINTS
    old_validate = legacy_executor.validate_plan

    def guarded_validate(plan: Mapping[str, Any]) -> None:
        old_validate(plan)
        _check_v31_plan_contract(plan)

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
    with _v31_context():
        return legacy_executor.build_plan(*args, **kwargs)


def validate_plan(plan: Mapping[str, Any]) -> None:
    with _v31_context():
        legacy_executor.validate_plan(plan)


def configure_stage(
    plan: Mapping[str, Any],
    stage_key: str,
    argv: Sequence[str],
    **kwargs: Any,
) -> dict[str, Any]:
    with _v31_context():
        return legacy_executor.configure_stage(plan, stage_key, argv, **kwargs)


def run_next(*args: Any, **kwargs: Any) -> dict[str, Any]:
    with _v31_context():
        return legacy_executor.run_next(*args, **kwargs)


def validate_ledger(ledger: Mapping[str, Any]) -> None:
    with _v31_context():
        legacy_executor.validate_ledger(ledger)


def main() -> int:
    with _v31_context():
        return legacy_executor.main()


PLAN_SCHEMA = legacy_executor.PLAN_SCHEMA
LEDGER_SCHEMA = legacy_executor.LEDGER_SCHEMA
HistoricalRefinementExecutionError = legacy_executor.HistoricalRefinementExecutionError


if __name__ == "__main__":
    raise SystemExit(main())
