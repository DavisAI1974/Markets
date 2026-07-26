#!/usr/bin/env python3
"""Run the guarded historical executor against recursive-provenance readiness v29."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v24 as v24
import ng_historical_refinement_readiness_v29 as readiness

SUGGESTED_ENTRYPOINTS: dict[str, tuple[str, ...]] = {
    **v24.SUGGESTED_ENTRYPOINTS,
    "corpus_s3_materialization_provenance": (
        "python",
        "ng_corpus_s3_materializer_provenance_gate.py",
        "build",
    ),
}


def _check_v29_plan_contract(plan: Mapping[str, Any]) -> None:
    stages = list(plan.get("stages") or [])
    if len(stages) != len(readiness.STAGES):
        raise legacy_executor.HistoricalRefinementExecutionError(
            "readiness-v29 execution plan stage count mismatch"
        )
    for spec, step in zip(readiness.STAGES, stages):
        if step.get("key") != spec.key:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v29 stage order mismatch"
            )
        if step.get("expected_output") != spec.filename:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v29 expected output mismatch"
            )
        expected_entrypoint = list(SUGGESTED_ENTRYPOINTS.get(spec.key, ()))
        if step.get("suggested_entrypoint") != expected_entrypoint:
            raise legacy_executor.HistoricalRefinementExecutionError(
                f"{spec.key}: readiness-v29 suggested entrypoint mismatch"
            )

    first, second, third, fourth, fifth, sixth, seventh = stages[:7]
    if first.get("key") != "corpus_expected_day_contract":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "expected-day contract must remain first in readiness v29"
        )
    if second.get("key") != "corpus_inventory_finalization_contract":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "inventory finalization must remain before S3 requests"
        )
    if third.get("key") != "corpus_s3_latest_version_resolution":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "paginated S3 version resolution must follow finalization"
        )
    if fourth.get("key") != "corpus_s3_inventory_capture":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "runtime-observed inventory must precede exact materialization"
        )
    if fifth.get("key") != "corpus_s3_materialization":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "exact version materialization must precede provenance binding"
        )
    if fifth.get("expected_output") != "ng_corpus_s3_exact_materializer_receipt.json":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "exact materializer receipt was substituted"
        )
    if sixth.get("key") != "corpus_s3_materialization_provenance":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "recursive materializer provenance must follow exact materialization"
        )
    if sixth.get("expected_output") != "ng_corpus_s3_materializer_provenance_gate.json":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "materializer provenance artifact was substituted"
        )
    if sixth.get("suggested_entrypoint") != [
        "python",
        "ng_corpus_s3_materializer_provenance_gate.py",
        "build",
    ]:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "materializer provenance entrypoint mismatch"
        )
    if sixth.get("requires_fixed_outcomes") is not False:
        raise legacy_executor.HistoricalRefinementExecutionError(
            "materializer provenance must remain pre-outcome"
        )
    if seventh.get("key") != "corpus_coverage":
        raise legacy_executor.HistoricalRefinementExecutionError(
            "broad byte inspection must follow recursive materializer provenance"
        )


@contextmanager
def _v29_context() -> Iterator[None]:
    old_readiness = legacy_executor.readiness
    old_entrypoints = legacy_executor.SUGGESTED_ENTRYPOINTS
    old_validate = legacy_executor.validate_plan

    def guarded_validate(plan: Mapping[str, Any]) -> None:
        old_validate(plan)
        _check_v29_plan_contract(plan)

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
    with _v29_context():
        return legacy_executor.build_plan(*args, **kwargs)


def validate_plan(plan: Mapping[str, Any]) -> None:
    with _v29_context():
        legacy_executor.validate_plan(plan)


def configure_stage(
    plan: Mapping[str, Any],
    stage_key: str,
    argv: Sequence[str],
    **kwargs: Any,
) -> dict[str, Any]:
    with _v29_context():
        return legacy_executor.configure_stage(plan, stage_key, argv, **kwargs)


def run_next(*args: Any, **kwargs: Any) -> dict[str, Any]:
    with _v29_context():
        return legacy_executor.run_next(*args, **kwargs)


def validate_ledger(ledger: Mapping[str, Any]) -> None:
    with _v29_context():
        legacy_executor.validate_ledger(ledger)


def main() -> int:
    with _v29_context():
        return legacy_executor.main()


PLAN_SCHEMA = legacy_executor.PLAN_SCHEMA
LEDGER_SCHEMA = legacy_executor.LEDGER_SCHEMA
HistoricalRefinementExecutionError = legacy_executor.HistoricalRefinementExecutionError


if __name__ == "__main__":
    raise SystemExit(main())
