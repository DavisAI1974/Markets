#!/usr/bin/env python3
"""Bind lock-first G15 scoring through exact publication.

This outer publication gate requires the six-factor pre-outcome lock, the guarded
score receipt proving the lock and forecast hashes were checked before actuals were
opened, and the existing exact render/publication completion to agree exactly.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from ng_g15_counterfactual_attribution import FACTORS
from ng_g15_counterfactual_score_gate import validate_receipt
from ng_g15_counterfactual_scoring_wall import validate_lock
from ng_g15_exact_publication_gate import validate_completion as validate_exact_publication

SCHEMA = "ng_g15_counterfactual_scored_publication_completion.v1"
READY = "EXACT_G15_COUNTERFACTUAL_SCORED_PUBLICATION_COMPLETE"
READY_SD = "EXACT_G15_COUNTERFACTUAL_SCORED_PUBLICATION_COMPLETE_WITH_STAND_DOWNS"


class CounterfactualScoredPublicationError(ValueError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _verify(value: Mapping[str, Any], field: str, label: str) -> dict[str, Any]:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    if not observed or observed != _fp(payload):
        raise CounterfactualScoredPublicationError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def build_completion(
    *,
    lock: Mapping[str, Any],
    score_receipt: Mapping[str, Any],
    exact_publication: Mapping[str, Any],
) -> dict[str, Any]:
    originals = copy.deepcopy((lock, score_receipt, exact_publication))
    try:
        validate_lock(lock)
        validate_receipt(score_receipt, lock=lock)
        validate_exact_publication(dict(exact_publication))
    except ValueError as error:
        raise CounterfactualScoredPublicationError(
            f"upstream G15 publication chain failed: {error}"
        ) from error
    locked = _verify(lock, "lock_fingerprint", "counterfactual scoring lock")
    scored = _verify(score_receipt, "fingerprint", "counterfactual score receipt")
    published = _verify(
        exact_publication, "completion_fingerprint", "exact G15 publication"
    )

    lock_links = {
        "counterfactual_scoring_lock_fingerprint": "lock_fingerprint",
        "counterfactual_attribution_fingerprint": "counterfactual_attribution_fingerprint",
        "exact_refinement_authorization_fingerprint": "exact_refinement_authorization_fingerprint",
        "exact_replay_completion_fingerprint": "exact_replay_completion_fingerprint",
        "blind_forecast_sha256": "blind_forecast_sha256",
        "refined_forecast_sha256": "refined_forecast_sha256",
        "refined_curve_fingerprint": "refined_curve_fingerprint",
    }
    for score_field, lock_field in lock_links.items():
        if scored.get(score_field) != locked.get(lock_field):
            raise CounterfactualScoredPublicationError(
                f"score receipt changed locked {lock_field}"
            )

    publication_links = {
        "exact_refinement_authorization_fingerprint": "exact_refinement_authorization_fingerprint",
        "exact_replay_completion_fingerprint": "exact_replay_completion_fingerprint",
        "blind_forecast_sha256": "blind_forecast_sha256",
        "refined_forecast_sha256": "refined_forecast_sha256",
        "refined_curve_fingerprint": "refined_curve_fingerprint",
        "actual_artifact_fingerprint": "actual_artifact_fingerprint",
        "blind_score_fingerprint": "blind_score_fingerprint",
        "refined_score_fingerprint": "refined_score_fingerprint",
        "comparison_fingerprint": "comparison_fingerprint",
    }
    for score_field, publication_field in publication_links.items():
        if scored.get(score_field) != published.get(publication_field):
            raise CounterfactualScoredPublicationError(
                f"publication changed scored {publication_field}"
            )
    if published.get("actual_outcomes_used") is not True:
        raise CounterfactualScoredPublicationError("G15 outcome use was not disclosed")
    if published.get("outcome_scoring_complete") is not True:
        raise CounterfactualScoredPublicationError("G15 scoring is incomplete")
    if published.get("continuous_rt_renders_complete") is not True:
        raise CounterfactualScoredPublicationError("canonical G15 renders are incomplete")

    stand_down_days = sorted(
        set(locked.get("stand_down_days") or [])
        | set(scored.get("stand_down_days") or [])
        | set(published.get("stand_down_days") or [])
    )
    result = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 15,
        "status": READY_SD if stand_down_days else READY,
        "authority": "G15_COUNTERFACTUAL_SCORED_PUBLICATION_AUDIT_ONLY",
        "counterfactual_scoring_lock_fingerprint": locked["lock_fingerprint"],
        "counterfactual_score_gate_fingerprint": scored["fingerprint"],
        "counterfactual_attribution_fingerprint": locked[
            "counterfactual_attribution_fingerprint"
        ],
        "exact_publication_completion_fingerprint": published[
            "completion_fingerprint"
        ],
        "exact_refinement_authorization_fingerprint": published[
            "exact_refinement_authorization_fingerprint"
        ],
        "exact_replay_completion_fingerprint": published[
            "exact_replay_completion_fingerprint"
        ],
        "blind_forecast_sha256": published["blind_forecast_sha256"],
        "refined_forecast_sha256": published["refined_forecast_sha256"],
        "refined_curve_fingerprint": published["refined_curve_fingerprint"],
        "actual_artifact_fingerprint": published["actual_artifact_fingerprint"],
        "blind_score_fingerprint": published["blind_score_fingerprint"],
        "refined_score_fingerprint": published["refined_score_fingerprint"],
        "comparison_fingerprint": published["comparison_fingerprint"],
        "lesson_adjudication_fingerprint": published[
            "lesson_adjudication_fingerprint"
        ],
        "counterfactual_factors": list(FACTORS),
        "lesson_candidate_ids_fixed_before_scoring": list(
            locked.get("lesson_candidate_ids_fixed_before_scoring") or []
        ),
        "stand_down_days": stand_down_days,
        "counterfactual_attribution_locked_before_actual_open": True,
        "locked_forecast_hashes_checked_before_actual_open": True,
        "blind_and_refined_scores_separate": True,
        "canonical_renders_complete": True,
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecast_immutable": True,
        "may_change_blind_prior": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_select_lesson_support_from_scores": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "G15_COUNTERFACTUAL_LESSON_ADJUDICATION_AND_G16_PRE_CUTOFF_LINEAGE",
    }
    result["completion_fingerprint"] = _fp(result)
    if (lock, score_receipt, exact_publication) != originals:
        raise CounterfactualScoredPublicationError(
            "publication gate mutated an input artifact"
        )
    validate_completion(result)
    return result


def validate_completion(completion: Mapping[str, Any]) -> None:
    value = _verify(
        completion,
        "completion_fingerprint",
        "counterfactual scored publication completion",
    )
    if value.get("schema") != SCHEMA or value.get("status") not in {READY, READY_SD}:
        raise CounterfactualScoredPublicationError("unexpected scored publication")
    if value.get("authority") != "G15_COUNTERFACTUAL_SCORED_PUBLICATION_AUDIT_ONLY":
        raise CounterfactualScoredPublicationError("publication authority mismatch")
    for field in (
        "counterfactual_attribution_locked_before_actual_open",
        "locked_forecast_hashes_checked_before_actual_open",
        "blind_and_refined_scores_separate",
        "canonical_renders_complete",
        "actual_g15_outcomes_used",
        "one_signal_authority_preserved",
        "blind_forecast_immutable",
    ):
        if value.get(field) is not True:
            raise CounterfactualScoredPublicationError(f"{field} must remain true")
    for field in (
        "actual_g16_outcomes_used",
        "random_shuffle_used",
        "may_change_blind_prior",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_select_lesson_support_from_scores",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise CounterfactualScoredPublicationError(f"{field} must remain false")
    if value.get("counterfactual_factors") != list(FACTORS):
        raise CounterfactualScoredPublicationError("six-factor coverage was lost")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CounterfactualScoredPublicationError("CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CounterfactualScoredPublicationError("brokerage must remain tastytrade")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bind counterfactual lock-first G15 scores through publication"
    )
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--score-receipt", type=Path, required=True)
    parser.add_argument("--exact-publication", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build_completion(
        lock=load(args.lock),
        score_receipt=load(args.score_receipt),
        exact_publication=load(args.exact_publication),
    )
    _atomic(args.out, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "completion_fingerprint": result["completion_fingerprint"],
                "blind_score_fingerprint": result["blind_score_fingerprint"],
                "refined_score_fingerprint": result["refined_score_fingerprint"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
