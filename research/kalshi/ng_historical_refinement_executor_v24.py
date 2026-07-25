#!/usr/bin/env python3
"""Run the guarded historical executor against exact-materialization readiness v28."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v23 as v23
import ng_historical_refinement_readiness_v28 as readiness

SUGGESTED_ENTRYPOINTS: dict[str, tuple[str, ...]] = {
    **v23.SUGGESTED_ENTRYPOINTS,
    "corpus_s3_materialization": (
        "python",
        "ng_corpus_s3_exact_materializer.py",
        "materialize",
    ),
}


def _check_v28_plan_contract(plan: Mapping[str, Any]) -> None:
    stages = list(plan.get("stages") or [])
    if len(stages) != len(readiness.STAGES):
        raise legacy_executor.HistoricalRefinementExecutionError(
            "readiness-v28 execution plan stage count mismatch"
        )
    for spec, step in zip(readiness.STAGES, stages):
        if step.get("key") != spec.key:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v28 stage order mismatch"
            )
        if step.get("expected_output") != spec.filename:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v28 expected output mismatch"
            )
        expected_entrypoint = list(SUGGESTED_ENTRYPOINTS.get(spec.key, ()))
        if step.get("suggested_entrypoint") != expected_entrypoint:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v28 suggested entrypoint mismatch"
            )

    first, second, third, fourth, fifth, sixth = stages[:6]
    if first.get("key") != "corpus_expected_day_contract":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "expected-day contract must remain first in readiness v28"
        )
    if second.get("key") != "corpus_inventory_finalization_contract":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "inventory finalization must remain before S3 requests"
        )
    if third.get("key") != "corpus_s3_latest_version_resolution":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "paginated S3 version resolution must follow finalization"
        )
    if fourth.get("expected_output") != (
        "ng_corpus_s3_runtime_observed_inventory_capture_attestation.json"
    ):
        raise legacy_executor.HistoricalRefinementExecutionError(
            "runtime-observed inventory must precede exact materialization"
        )
    if fifth.get("expected_output") != "ng_corpus_s3_exact_materializer_receipt.json":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "exact version materialization receipt must replace legacy materialization"
        )
    if fifth.get("suggested_entrypoint") != [
        "python",
        "ng_corpus_s3_exact_materializer.py",
        "materialize",
    ]:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "exact materializer entrypoint mismatch"
        )
    if sixth.get("key") != "corpus_coverage":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "broad byte inspection must follow exact materialization"
        )


@contextmanager
def _v28_context() -> Iterator[None]:
    old_readiness = legacy_executor.readiness
    old_entrypoints = legacy_executor.SUGGESTED_ENTRYPOINTS
    old_validate = legacy_executor.validate_plan

    def guarded_validate(plan: Mapping[str, Any]) -> None:
        old_validate(plan)
        _check_v28_plan_contract(plan)

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
    with _v28_context():
        return legacy_executor.build_plan(*args, **kwargs)


def validate_plan(plan: Mapping[str, Any]) -> None:
    with _v28_context():
        legacy_executor.validate_plan(plan)


def configure_stage(
    plan: Mapping[str, Any],
    stage_key: str,
    argv: Sequence[str],
    **kwargs: Any,
) -> dict[str, Any]:
    with _v28_context():
        return legacy_executor.configure_stage(plan, stage_key, argv, **kwargs)


def run_next(*args: Any, **kwargs: Any) -> dict[str, Any]:
    with _v28_context():
        return legacy_executor.run_next(*args, **kwargs)


def validate_ledger(ledger: Mapping[str, Any]) -> None:
    with _v28_context():
        legacy_executor.validate_ledger(ledger)


def main() -> int:
    with _v28_context():
        return legacy_executor.main()


PLAN_SCHEMA = legacy_executor.PLAN_SCHEMA
LEDGER_SCHEMA = legacy_executor.LEDGER_SCHEMA
HistoricalRefinementExecutionError = legacy_executor.HistoricalRefinementExecutionError


if __name__ == "__main__":
    raise SystemExit(main())
