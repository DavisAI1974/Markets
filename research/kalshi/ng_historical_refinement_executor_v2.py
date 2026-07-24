#!/usr/bin/env python3
"""Run the guarded historical executor against canonical readiness v4.

The legacy executor remains the battle-tested command runner and mutation guard.  This
adapter replaces only its readiness contract and suggested entrypoints for the duration
of each call, making the G15 pre-outcome lock, guarded separate scoring receipt, and
scored-publication completion mandatory before lessons or G16 can advance.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_readiness_v4 as readiness


SUGGESTED_ENTRYPOINTS: dict[str, tuple[str, ...]] = {
    **legacy_executor.SUGGESTED_ENTRYPOINTS,
    "g15_counterfactual_attribution": (
        "python",
        "ng_g15_counterfactual_attribution.py",
    ),
    "g15_counterfactual_scoring_lock": (
        "python",
        "ng_g15_counterfactual_scoring_wall.py",
        "lock",
    ),
    "g15_counterfactual_score_gate": (
        "python",
        "ng_g15_counterfactual_score_gate.py",
    ),
    "g15_publication": (
        "python",
        "ng_g15_exact_publication_gate.py",
    ),
    "g15_counterfactual_scored_publication": (
        "python",
        "ng_g15_counterfactual_scored_publication_gate.py",
    ),
    "g15_counterfactual_lesson_gate": (
        "python",
        "ng_g15_counterfactual_lesson_gate.py",
    ),
    "g15_g16_counterfactual_lineage": (
        "python",
        "ng_g15_g16_counterfactual_lineage_gate.py",
    ),
    "g16_counterfactual_causal_authorization": (
        "python",
        "ng_g16_counterfactual_causal_authorization.py",
    ),
    "g16_counterfactual_curve_authorization": (
        "python",
        "ng_g16_counterfactual_curve_authorization.py",
    ),
    "g16_counterfactual_curve_lock": (
        "python",
        "ng_g16_counterfactual_publication_gate.py",
        "lock",
    ),
    "g16_counterfactual_publication": (
        "python",
        "ng_g16_counterfactual_publication_gate.py",
        "publish",
    ),
}


@contextmanager
def _v4_context() -> Iterator[None]:
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
    with _v4_context():
        return legacy_executor.build_plan(*args, **kwargs)


def validate_plan(plan: Mapping[str, Any]) -> None:
    with _v4_context():
        legacy_executor.validate_plan(plan)


def configure_stage(
    plan: Mapping[str, Any],
    stage_key: str,
    argv: Sequence[str],
    **kwargs: Any,
) -> dict[str, Any]:
    with _v4_context():
        return legacy_executor.configure_stage(plan, stage_key, argv, **kwargs)


def run_next(*args: Any, **kwargs: Any) -> dict[str, Any]:
    with _v4_context():
        return legacy_executor.run_next(*args, **kwargs)


def validate_ledger(ledger: Mapping[str, Any]) -> None:
    with _v4_context():
        legacy_executor.validate_ledger(ledger)


def main() -> int:
    with _v4_context():
        return legacy_executor.main()


PLAN_SCHEMA = legacy_executor.PLAN_SCHEMA
LEDGER_SCHEMA = legacy_executor.LEDGER_SCHEMA
HistoricalRefinementExecutionError = legacy_executor.HistoricalRefinementExecutionError


if __name__ == "__main__":
    raise SystemExit(main())
