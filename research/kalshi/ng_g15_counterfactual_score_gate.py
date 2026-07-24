#!/usr/bin/env python3
"""Score G15 only after the six-factor counterfactual lock validates.

The command path validates the pre-outcome lock and both locked forecast byte hashes
before opening the fixed G15 actual-outcome file. Blind and refined paths are scored
separately through ``ng_g15_path_score`` and remain descriptive SHADOW evidence.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from ng_g15_counterfactual_scoring_wall import validate_lock
from ng_g15_path_score import (
    build_comparison,
    build_scorecard,
    validate_comparison,
    validate_scorecard,
)

SCHEMA = "ng_g15_counterfactual_score_gate.v1"
READY = "EXACT_G15_COUNTERFACTUAL_SCORES_COMPLETE"
READY_SD = "EXACT_G15_COUNTERFACTUAL_SCORES_COMPLETE_WITH_STAND_DOWNS"


class CounterfactualScoreGateError(ValueError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _verify(value: Mapping[str, Any], field: str, label: str) -> dict[str, Any]:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    if not observed or observed != _fp(payload):
        raise CounterfactualScoreGateError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def validate_locked_forecasts(
    lock: Mapping[str, Any], *, blind_bytes: bytes, refined_bytes: bytes
) -> dict[str, Any]:
    try:
        validate_lock(lock)
    except ValueError as error:
        raise CounterfactualScoreGateError(f"pre-outcome lock invalid: {error}") from error
    value = _verify(lock, "lock_fingerprint", "counterfactual scoring lock")
    if value.get("actual_g15_outcomes_used") is not False:
        raise CounterfactualScoreGateError("pre-scoring lock contains G15 outcomes")
    if value.get("g15_fixed_scoring_authorized") is not True:
        raise CounterfactualScoreGateError("fixed G15 scoring is not authorized")
    if value.get("blind_forecast_sha256") != _sha(blind_bytes):
        raise CounterfactualScoreGateError("blind forecast bytes differ from lock")
    if value.get("refined_forecast_sha256") != _sha(refined_bytes):
        raise CounterfactualScoreGateError("refined forecast bytes differ from lock")
    return value


def build_scores(
    *,
    lock: Mapping[str, Any],
    blind: Mapping[str, Any],
    refined: Mapping[str, Any],
    actual: Mapping[str, Any],
    blind_bytes: bytes,
    refined_bytes: bytes,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    originals = copy.deepcopy((lock, blind, refined, actual))
    locked = validate_locked_forecasts(
        lock, blind_bytes=blind_bytes, refined_bytes=refined_bytes
    )
    try:
        blind_score = build_scorecard(
            blind,
            actual,
            forecast_kind="blind",
            forecast_bytes=blind_bytes,
        )
        refined_score = build_scorecard(
            refined,
            actual,
            forecast_kind="refined",
            forecast_bytes=refined_bytes,
            blind_bytes=blind_bytes,
        )
        comparison = build_comparison(blind_score, refined_score)
    except ValueError as error:
        raise CounterfactualScoreGateError(f"G15 path scoring failed: {error}") from error

    if blind_score.get("forecast_sha256") != locked.get("blind_forecast_sha256"):
        raise CounterfactualScoreGateError("blind score references bytes outside lock")
    if refined_score.get("forecast_sha256") != locked.get("refined_forecast_sha256"):
        raise CounterfactualScoreGateError("refined score references bytes outside lock")
    actual_fp = str(blind_score.get("actual_artifact_fingerprint") or "")
    if not actual_fp or refined_score.get("actual_artifact_fingerprint") != actual_fp:
        raise CounterfactualScoreGateError("blind/refined scores use different actual substrate")
    if comparison.get("blind_score_fingerprint") != blind_score.get("artifact_fingerprint"):
        raise CounterfactualScoreGateError("comparison references a different blind score")
    if comparison.get("refined_score_fingerprint") != refined_score.get("artifact_fingerprint"):
        raise CounterfactualScoreGateError("comparison references a different refined score")

    stand_down_days = sorted(set(locked.get("stand_down_days") or []))
    receipt = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 15,
        "status": READY_SD if stand_down_days else READY,
        "authority": "G15_COUNTERFACTUAL_OUTCOME_SCORING_AUDIT_ONLY",
        "counterfactual_scoring_lock_fingerprint": locked["lock_fingerprint"],
        "counterfactual_attribution_fingerprint": locked[
            "counterfactual_attribution_fingerprint"
        ],
        "exact_refinement_authorization_fingerprint": locked[
            "exact_refinement_authorization_fingerprint"
        ],
        "exact_replay_completion_fingerprint": locked[
            "exact_replay_completion_fingerprint"
        ],
        "blind_forecast_sha256": locked["blind_forecast_sha256"],
        "refined_forecast_sha256": locked["refined_forecast_sha256"],
        "refined_curve_fingerprint": locked["refined_curve_fingerprint"],
        "actual_artifact_fingerprint": actual_fp,
        "blind_score_fingerprint": blind_score["artifact_fingerprint"],
        "refined_score_fingerprint": refined_score["artifact_fingerprint"],
        "comparison_fingerprint": comparison["artifact_fingerprint"],
        "lesson_candidate_ids_fixed_before_scoring": list(
            locked.get("lesson_candidate_ids_fixed_before_scoring") or []
        ),
        "stand_down_days": stand_down_days,
        "lock_validated_before_actual_file_open": True,
        "blind_and_refined_scores_separate": True,
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
        "next_permitted_stage": "G15_EXACT_RENDER_AND_PUBLICATION",
    }
    receipt["fingerprint"] = _fp(receipt)
    if (lock, blind, refined, actual) != originals:
        raise CounterfactualScoreGateError("scoring mutated an input artifact")
    validate_receipt(
        receipt,
        lock=lock,
        blind_score=blind_score,
        refined_score=refined_score,
        comparison=comparison,
    )
    return receipt, blind_score, refined_score, comparison


def validate_receipt(
    receipt: Mapping[str, Any],
    *,
    lock: Mapping[str, Any] | None = None,
    blind_score: Mapping[str, Any] | None = None,
    refined_score: Mapping[str, Any] | None = None,
    comparison: Mapping[str, Any] | None = None,
) -> None:
    value = _verify(receipt, "fingerprint", "counterfactual score receipt")
    if value.get("schema") != SCHEMA or value.get("status") not in {READY, READY_SD}:
        raise CounterfactualScoreGateError("unexpected counterfactual score receipt")
    if value.get("authority") != "G15_COUNTERFACTUAL_OUTCOME_SCORING_AUDIT_ONLY":
        raise CounterfactualScoreGateError("score receipt authority mismatch")
    required_true = (
        "lock_validated_before_actual_file_open",
        "blind_and_refined_scores_separate",
        "actual_g15_outcomes_used",
        "one_signal_authority_preserved",
        "blind_forecast_immutable",
    )
    for field in required_true:
        if value.get(field) is not True:
            raise CounterfactualScoreGateError(f"score receipt must keep {field}=true")
    required_false = (
        "actual_g16_outcomes_used",
        "random_shuffle_used",
        "may_change_blind_prior",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_select_lesson_support_from_scores",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    )
    for field in required_false:
        if value.get(field) is not False:
            raise CounterfactualScoreGateError(f"score receipt must keep {field}=false")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CounterfactualScoreGateError("CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CounterfactualScoreGateError("brokerage contract must remain tastytrade")
    if lock is not None:
        validate_lock(lock)
        if value.get("counterfactual_scoring_lock_fingerprint") != lock.get(
            "lock_fingerprint"
        ):
            raise CounterfactualScoreGateError("receipt references a different lock")
    if blind_score is not None:
        validate_scorecard(blind_score)
        if value.get("blind_score_fingerprint") != blind_score.get(
            "artifact_fingerprint"
        ):
            raise CounterfactualScoreGateError("receipt references a different blind score")
    if refined_score is not None:
        validate_scorecard(refined_score)
        if value.get("refined_score_fingerprint") != refined_score.get(
            "artifact_fingerprint"
        ):
            raise CounterfactualScoreGateError("receipt references a different refined score")
    if comparison is not None:
        validate_comparison(comparison)
        if value.get("comparison_fingerprint") != comparison.get(
            "artifact_fingerprint"
        ):
            raise CounterfactualScoreGateError("receipt references a different comparison")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score G15 only after validating the counterfactual lock"
    )
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--blind", type=Path, required=True)
    parser.add_argument("--refined", type=Path, required=True)
    parser.add_argument("--actual", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    parser.add_argument("--blind-score-out", type=Path, required=True)
    parser.add_argument("--refined-score-out", type=Path, required=True)
    parser.add_argument("--comparison-out", type=Path, required=True)
    args = parser.parse_args()

    # Deliberate order: validate lock and forecast bytes before opening actual outcomes.
    lock_value = json.loads(args.lock.read_text(encoding="utf-8"))
    blind_bytes = args.blind.read_bytes()
    refined_bytes = args.refined.read_bytes()
    validate_locked_forecasts(
        lock_value, blind_bytes=blind_bytes, refined_bytes=refined_bytes
    )
    blind = json.loads(blind_bytes.decode("utf-8"))
    refined = json.loads(refined_bytes.decode("utf-8"))
    actual = json.loads(args.actual.read_text(encoding="utf-8"))
    receipt, blind_score, refined_score, comparison = build_scores(
        lock=lock_value,
        blind=blind,
        refined=refined,
        actual=actual,
        blind_bytes=blind_bytes,
        refined_bytes=refined_bytes,
    )
    _atomic(args.blind_score_out, blind_score)
    _atomic(args.refined_score_out, refined_score)
    _atomic(args.comparison_out, comparison)
    _atomic(args.receipt_out, receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "lock_fingerprint": receipt[
                    "counterfactual_scoring_lock_fingerprint"
                ],
                "blind_score_fingerprint": receipt["blind_score_fingerprint"],
                "refined_score_fingerprint": receipt["refined_score_fingerprint"],
                "comparison_fingerprint": receipt["comparison_fingerprint"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
