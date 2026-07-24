#!/usr/bin/env python3
"""Run the guarded historical executor against replay-window-first readiness v8."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v5 as v5
import ng_historical_refinement_readiness_v8 as readiness

SUGGESTED_ENTRYPOINTS: dict[str, tuple[str, ...]] = {
    **v5.SUGGESTED_ENTRYPOINTS,
    "g15_exact_replay_window_authorization": (
        "python",
        "ng_g15_exact_replay_window_authorization.py",
    ),
}


@contextmanager
def _v8_context() -> Iterator[None]:
    old_readiness = legacy_executor.readiness
    old_entrypoints = legacy_executor.SUGGESTED_ENTRYPOINTS
    legacy_executor.readiness = readiness
    legacy_executor.SUGGESTED_ENTRYPOINTS = SUGGESTED_ENTRYPOINTS
    try:
        yield
    finally:
        legacy_executor.readiness = old_readiness
        legacy_executor.SUGGESTED_ENTRYPOINTS = old_entrypoints


def build_plan(*args: Any, **kwargs: Any) -> dict[str, Any]:
    with _v8_context():
        return legacy_executor.build_plan(*args, **kwargs)


def validate_plan(plan: Mapping[str, Any]) -> None:
    with _v8_context():
        legacy_executor.validate_plan(plan)


def configure_stage(
    plan: Mapping[str, Any],
    stage_key: str,
    argv: Sequence[str],
    **kwargs: Any,
) -> dict[str, Any]:
    with _v8_context():
        return legacy_executor.configure_stage(plan, stage_key, argv, **kwargs)


def run_next(*args: Any, **kwargs: Any) -> dict[str, Any]:
    with _v8_context():
        return legacy_executor.run_next(*args, **kwargs)


def validate_ledger(ledger: Mapping[str, Any]) -> None:
    with _v8_context():
        legacy_executor.validate_ledger(ledger)


def main() -> int:
    with _v8_context():
        return legacy_executor.main()


PLAN_SCHEMA = legacy_executor.PLAN_SCHEMA
LEDGER_SCHEMA = legacy_executor.LEDGER_SCHEMA
HistoricalRefinementExecutionError = legacy_executor.HistoricalRefinementExecutionError


if __name__ == "__main__":
    raise SystemExit(main())
