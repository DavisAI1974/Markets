#!/usr/bin/env python3
"""Run the guarded historical executor against paginated readiness v23."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v18 as v18
import ng_historical_refinement_readiness_v23 as readiness

SUGGESTED_ENTRYPOINTS: dict[str, tuple[str, ...]] = {
    **v18.SUGGESTED_ENTRYPOINTS,
    "corpus_s3_latest_version_resolution": (
        "python",
        "ng_corpus_s3_paginated_latest_version_resolution.py",
        "resolve",
    ),
}


def _check_v23_plan_contract(plan: Mapping[str, Any]) -> None:
    stages = list(plan.get("stages") or [])
    if len(stages) != len(readiness.STAGES):
        raise legacy_executor.HistoricalRefinementExecutionError(
            "readiness-v23 execution plan stage count mismatch"
        )
    for spec, step in zip(readiness.STAGES, stages):
        if step.get("key") != spec.key:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v23 stage order mismatch"
            )
        if step.get("expected_output") != spec.filename:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v23 expected output mismatch"
            )
        expected_entrypoint = list(SUGGESTED_ENTRYPOINTS.get(spec.key, ()))
        if step.get("suggested_entrypoint") != expected_entrypoint:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v23 suggested entrypoint mismatch"
            )
    first = stages[0]
    if first.get("expected_output") != (
        "ng_corpus_s3_paginated_latest_version_resolution_attestation.json"
    ):
        raise legacy_executor.HistoricalRefinementExecutionError(
            "legacy non-paginated S3 resolution artifact may not enter readiness v23"
        )


@contextmanager
def _v23_context() -> Iterator[None]:
    old_readiness = legacy_executor.readiness
    old_entrypoints = legacy_executor.SUGGESTED_ENTRYPOINTS
    old_validate = legacy_executor.validate_plan

    def guarded_validate(plan: Mapping[str, Any]) -> None:
        old_validate(plan)
        _check_v23_plan_contract(plan)

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
    with _v23_context():
        return legacy_executor.build_plan(*args, **kwargs)


def validate_plan(plan: Mapping[str, Any]) -> None:
    with _v23_context():
        legacy_executor.validate_plan(plan)


def configure_stage(
    plan: Mapping[str, Any],
    stage_key: str,
    argv: Sequence[str],
    **kwargs: Any,
) -> dict[str, Any]:
    with _v23_context():
        return legacy_executor.configure_stage(plan, stage_key, argv, **kwargs)


def run_next(*args: Any, **kwargs: Any) -> dict[str, Any]:
    with _v23_context():
        return legacy_executor.run_next(*args, **kwargs)


def validate_ledger(ledger: Mapping[str, Any]) -> None:
    with _v23_context():
        legacy_executor.validate_ledger(ledger)


def main() -> int:
    with _v23_context():
        return legacy_executor.main()


PLAN_SCHEMA = legacy_executor.PLAN_SCHEMA
LEDGER_SCHEMA = legacy_executor.LEDGER_SCHEMA
HistoricalRefinementExecutionError = legacy_executor.HistoricalRefinementExecutionError


if __name__ == "__main__":
    raise SystemExit(main())
