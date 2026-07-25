#!/usr/bin/env python3
"""Run the guarded historical executor against inventory-finalized readiness v26."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v21 as v21
import ng_historical_refinement_readiness_v26 as readiness

SUGGESTED_ENTRYPOINTS: dict[str, tuple[str, ...]] = {
    **v21.SUGGESTED_ENTRYPOINTS,
    "corpus_inventory_finalization_contract": (
        "python",
        "ng_corpus_inventory_finalization_contract.py",
        "build",
    ),
}


def _check_v26_plan_contract(plan: Mapping[str, Any]) -> None:
    stages = list(plan.get("stages") or [])
    if len(stages) != len(readiness.STAGES):
        raise legacy_executor.HistoricalRefinementExecutionError(
            "readiness-v26 execution plan stage count mismatch"
        )
    for spec, step in zip(readiness.STAGES, stages):
        if step.get("key") != spec.key:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v26 stage order mismatch"
            )
        if step.get("expected_output") != spec.filename:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v26 expected output mismatch"
            )
        expected_entrypoint = list(SUGGESTED_ENTRYPOINTS.get(spec.key, ()))
        if step.get("suggested_entrypoint") != expected_entrypoint:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v26 suggested entrypoint mismatch"
            )
    first, second, third, fourth = stages[:4]
    if first.get("expected_output") != "ng_corpus_expected_day_contract_attestation.json":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "expected-day contract must remain first in readiness v26"
        )
    if second.get("expected_output") != "ng_corpus_inventory_finalization_contract.json":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "inventory finalization must precede every S3 request"
        )
    if third.get("expected_output") != (
        "ng_corpus_s3_paginated_latest_version_resolution_attestation.json"
    ):
        raise legacy_executor.HistoricalRefinementExecutionError(
            "paginated S3 resolution must follow inventory finalization"
        )
    if fourth.get("expected_output") != (
        "ng_corpus_s3_paginated_inventory_capture_attestation.json"
    ):
        raise legacy_executor.HistoricalRefinementExecutionError(
            "paginated S3 inventory must remain after version resolution"
        )


@contextmanager
def _v26_context() -> Iterator[None]:
    old_readiness = legacy_executor.readiness
    old_entrypoints = legacy_executor.SUGGESTED_ENTRYPOINTS
    old_validate = legacy_executor.validate_plan

    def guarded_validate(plan: Mapping[str, Any]) -> None:
        old_validate(plan)
        _check_v26_plan_contract(plan)

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
    with _v26_context():
        return legacy_executor.build_plan(*args, **kwargs)


def validate_plan(plan: Mapping[str, Any]) -> None:
    with _v26_context():
        legacy_executor.validate_plan(plan)


def configure_stage(
    plan: Mapping[str, Any],
    stage_key: str,
    argv: Sequence[str],
    **kwargs: Any,
) -> dict[str, Any]:
    with _v26_context():
        return legacy_executor.configure_stage(plan, stage_key, argv, **kwargs)


def run_next(*args: Any, **kwargs: Any) -> dict[str, Any]:
    with _v26_context():
        return legacy_executor.run_next(*args, **kwargs)


def validate_ledger(ledger: Mapping[str, Any]) -> None:
    with _v26_context():
        legacy_executor.validate_ledger(ledger)


def main() -> int:
    with _v26_context():
        return legacy_executor.main()


PLAN_SCHEMA = legacy_executor.PLAN_SCHEMA
LEDGER_SCHEMA = legacy_executor.LEDGER_SCHEMA
HistoricalRefinementExecutionError = legacy_executor.HistoricalRefinementExecutionError


if __name__ == "__main__":
    raise SystemExit(main())
