#!/usr/bin/env python3
"""Lock G15 six-factor attribution before fixed outcome scoring.

The existing exact publication gate keeps blind and refined scores separate. This
outer wall additionally requires the outcome-blind full-minus-neutral attribution
for onset, signed flow, divergence/exhaustion, queue behavior, price efficiency,
and activity to be persisted before scoring begins.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from ng_g15_counterfactual_attribution import FACTORS, validate_report as validate_attribution
from ng_historical_manifest import G15_DATES
from ng_g15_exact_publication_gate import (
    _validate_authorization,
    _validate_blind,
    _validate_refined,
    validate_completion as validate_exact_publication,
)

LOCK_SCHEMA = "ng_g15_counterfactual_scoring_lock.v1"
COMPLETION_SCHEMA = "ng_g15_counterfactual_publication_completion.v1"
LOCK_READY = "EXACT_G15_COUNTERFACTUAL_SCORING_LOCKED"
LOCK_READY_SD = "EXACT_G15_COUNTERFACTUAL_SCORING_LOCKED_WITH_STAND_DOWNS"
READY = "EXACT_G15_COUNTERFACTUAL_PUBLICATION_COMPLETE"
READY_SD = "EXACT_G15_COUNTERFACTUAL_PUBLICATION_COMPLETE_WITH_STAND_DOWNS"


class CounterfactualScoringWallError(ValueError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _verify(value: Mapping[str, Any], field: str, label: str) -> dict[str, Any]:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    if not observed or observed != _fp(payload):
        raise CounterfactualScoringWallError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _authority(value: Mapping[str, Any], *, pre_outcome: bool) -> None:
    expected_false = [
        "random_shuffle_used",
        "may_change_blind_prior",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_select_lesson_support_from_scores",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ]
    if pre_outcome:
        expected_false.append("actual_g15_outcomes_used")
    else:
        expected_false.append("actual_g16_outcomes_used")
    for field in expected_false:
        if value.get(field) is not False:
            raise CounterfactualScoringWallError(f"{field} must remain false")
    if value.get("one_signal_authority_preserved") is not True:
        raise CounterfactualScoringWallError("one signal authority was not preserved")
    if value.get("blind_forecast_immutable") is not True:
        raise CounterfactualScoringWallError("blind forecast immutability was lost")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CounterfactualScoringWallError("CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CounterfactualScoringWallError("brokerage contract must remain tastytrade")


def build_lock(
    *,
    authorization: Mapping[str, Any],
    replay: Mapping[str, Any],
    anchor: Mapping[str, Any],
    refine_stream: Mapping[str, Any],
    attribution: Mapping[str, Any],
    blind: Mapping[str, Any],
    refined: Mapping[str, Any],
    blind_bytes: bytes,
    refined_bytes: bytes,
) -> dict[str, Any]:
    """Build the pre-outcome lock. No actual-outcome argument exists."""
    originals = copy.deepcopy((authorization, replay, anchor, refine_stream, attribution, blind, refined))
    try:
        blind_hash = _validate_blind(blind, blind_bytes)
        auth = _validate_authorization(authorization, blind_bytes)
        validate_attribution(
            dict(attribution), replay=dict(replay), anchor=dict(anchor),
            refine_stream=dict(refine_stream),
        )
    except ValueError as error:
        raise CounterfactualScoringWallError(
            f"upstream pre-scoring validation failed: {error}"
        ) from error
    attr = _verify(attribution, "fingerprint", "counterfactual attribution")

    replay_fp = _fp(replay)
    stream_fp = _fp(refine_stream)
    if auth.get("replay_fingerprint") != replay_fp:
        raise CounterfactualScoringWallError("authorization references a different replay")
    if auth.get("anchor_fingerprint") != anchor.get("anchor_fingerprint"):
        raise CounterfactualScoringWallError("authorization references a different anchor")
    if auth.get("refine_stream_fingerprint") != stream_fp:
        raise CounterfactualScoringWallError("authorization references a different refine stream")
    if attr.get("anchor_fingerprint") != auth.get("anchor_fingerprint"):
        raise CounterfactualScoringWallError("attribution references a different anchor")
    if attr.get("refine_stream_fingerprint") != stream_fp:
        raise CounterfactualScoringWallError("attribution references a different refine stream")
    if attr.get("replay_fingerprint") != (replay.get("fingerprint") or replay_fp):
        raise CounterfactualScoringWallError("attribution references a different replay")
    if list(attr.get("factors") or []) != list(FACTORS):
        raise CounterfactualScoringWallError("attribution lost six-factor coverage")
    if attr.get("actual_outcomes_used") is not False:
        raise CounterfactualScoringWallError("attribution is not outcome-blind")

    try:
        refined_fp, refined_hash = _validate_refined(
            refined, refined_bytes, blind_hash=blind_hash,
            refine_stream_fingerprint=stream_fp,
        )
    except ValueError as error:
        raise CounterfactualScoringWallError(
            f"refined-curve validation failed: {error}"
        ) from error
    candidate_ids = sorted(str(row.get("id") or "") for row in attr.get("lesson_proposals") or [])
    if any(not item for item in candidate_ids) or len(candidate_ids) != len(set(candidate_ids)):
        raise CounterfactualScoringWallError("lesson candidates are missing or duplicated")
    stand_down_days = sorted(set(auth.get("stand_down_days") or []) | set(attr.get("stand_down_days") or []))
    result = {
        "schema": LOCK_SCHEMA,
        "market": "NG",
        "group": 15,
        "status": LOCK_READY_SD if stand_down_days else LOCK_READY,
        "authority": "G15_COUNTERFACTUAL_PRE_SCORING_LOCK_ONLY",
        "exact_refinement_authorization_fingerprint": auth["authorization_fingerprint"],
        "exact_replay_completion_fingerprint": auth["exact_replay_completion_fingerprint"],
        "replay_fingerprint": replay_fp,
        "anchor_fingerprint": auth["anchor_fingerprint"],
        "refine_stream_fingerprint": stream_fp,
        "counterfactual_attribution_fingerprint": attr["fingerprint"],
        "blind_forecast_sha256": blind_hash,
        "refined_forecast_sha256": refined_hash,
        "refined_curve_fingerprint": refined_fp,
        "counterfactual_factors": list(FACTORS),
        "lesson_candidate_ids_fixed_before_scoring": candidate_ids,
        "stand_down_days": stand_down_days,
        "actual_g15_outcomes_used": False,
        "g15_fixed_scoring_authorized": True,
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
        "next_permitted_stage": "EXACT_G15_BLIND_AND_REFINED_SCORING_AND_PUBLICATION",
    }
    result["lock_fingerprint"] = _fp(result)
    if (authorization, replay, anchor, refine_stream, attribution, blind, refined) != originals:
        raise CounterfactualScoringWallError("lock construction mutated an input")
    validate_lock(result)
    return result


def validate_lock(lock: Mapping[str, Any]) -> None:
    value = _verify(lock, "lock_fingerprint", "counterfactual scoring lock")
    if value.get("schema") != LOCK_SCHEMA or value.get("status") not in {LOCK_READY, LOCK_READY_SD}:
        raise CounterfactualScoringWallError("unexpected counterfactual scoring lock")
    if value.get("authority") != "G15_COUNTERFACTUAL_PRE_SCORING_LOCK_ONLY":
        raise CounterfactualScoringWallError("scoring-lock authority mismatch")
    if value.get("counterfactual_factors") != list(FACTORS):
        raise CounterfactualScoringWallError("scoring lock lost factor coverage")
    if value.get("g15_fixed_scoring_authorized") is not True:
        raise CounterfactualScoringWallError("fixed G15 scoring was not explicitly authorized")
    _authority(value, pre_outcome=True)


def build_completion(*, lock: Mapping[str, Any], publication: Mapping[str, Any]) -> dict[str, Any]:
    originals = copy.deepcopy((lock, publication))
    validate_lock(lock)
    try:
        validate_exact_publication(dict(publication))
    except ValueError as error:
        raise CounterfactualScoringWallError(
            f"exact publication validation failed: {error}"
        ) from error
    locked = _verify(lock, "lock_fingerprint", "counterfactual scoring lock")
    published = _verify(publication, "completion_fingerprint", "exact G15 publication")
    links = {
        "exact_refinement_authorization_fingerprint": "exact_refinement_authorization_fingerprint",
        "exact_replay_completion_fingerprint": "exact_replay_completion_fingerprint",
        "refine_stream_fingerprint": "refine_stream_fingerprint",
        "blind_forecast_sha256": "blind_forecast_sha256",
        "refined_forecast_sha256": "refined_forecast_sha256",
        "refined_curve_fingerprint": "refined_curve_fingerprint",
    }
    for lock_field, publication_field in links.items():
        if locked.get(lock_field) != published.get(publication_field):
            raise CounterfactualScoringWallError(f"publication changed locked {publication_field}")
    if published.get("actual_outcomes_used") is not True or published.get("outcome_scoring_complete") is not True:
        raise CounterfactualScoringWallError("exact G15 outcome scoring is incomplete")
    if not published.get("blind_score_fingerprint") or not published.get("refined_score_fingerprint"):
        raise CounterfactualScoringWallError("blind and refined scores were not kept separate")

    stand_down_days = sorted(set(locked.get("stand_down_days") or []) | set(published.get("stand_down_days") or []))
    result = {
        "schema": COMPLETION_SCHEMA,
        "market": "NG",
        "group": 15,
        "status": READY_SD if stand_down_days else READY,
        "authority": "G15_COUNTERFACTUAL_PUBLICATION_AUDIT_ONLY",
        "counterfactual_scoring_lock_fingerprint": locked["lock_fingerprint"],
        "counterfactual_attribution_fingerprint": locked["counterfactual_attribution_fingerprint"],
        "exact_publication_completion_fingerprint": published["completion_fingerprint"],
        "exact_refinement_authorization_fingerprint": published["exact_refinement_authorization_fingerprint"],
        "exact_replay_completion_fingerprint": published["exact_replay_completion_fingerprint"],
        "replay_fingerprint": locked["replay_fingerprint"],
        "refine_stream_fingerprint": published["refine_stream_fingerprint"],
        "blind_forecast_sha256": published["blind_forecast_sha256"],
        "refined_forecast_sha256": published["refined_forecast_sha256"],
        "refined_curve_fingerprint": published["refined_curve_fingerprint"],
        "blind_score_fingerprint": published["blind_score_fingerprint"],
        "refined_score_fingerprint": published["refined_score_fingerprint"],
        "comparison_fingerprint": published["comparison_fingerprint"],
        "lesson_adjudication_fingerprint": published["lesson_adjudication_fingerprint"],
        "lesson_candidate_ids_fixed_before_scoring": list(locked["lesson_candidate_ids_fixed_before_scoring"]),
        "counterfactual_factors": list(FACTORS),
        "stand_down_days": stand_down_days,
        "counterfactual_attribution_locked_before_scoring": True,
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
        "next_permitted_stage": "G15_COUNTERFACTUAL_LESSON_ADJUDICATION",
    }
    result["completion_fingerprint"] = _fp(result)
    if (lock, publication) != originals:
        raise CounterfactualScoringWallError("completion construction mutated an input")
    validate_completion(result)
    return result


def validate_completion(completion: Mapping[str, Any]) -> None:
    value = _verify(completion, "completion_fingerprint", "counterfactual publication completion")
    if value.get("schema") != COMPLETION_SCHEMA or value.get("status") not in {READY, READY_SD}:
        raise CounterfactualScoringWallError("unexpected counterfactual publication completion")
    if value.get("authority") != "G15_COUNTERFACTUAL_PUBLICATION_AUDIT_ONLY":
        raise CounterfactualScoringWallError("publication authority mismatch")
    if value.get("actual_g15_outcomes_used") is not True:
        raise CounterfactualScoringWallError("G15 outcome use was not disclosed")
    if value.get("counterfactual_attribution_locked_before_scoring") is not True:
        raise CounterfactualScoringWallError("attribution was not locked before scoring")
    if value.get("blind_and_refined_scores_separate") is not True:
        raise CounterfactualScoringWallError("blind/refined scoring was not separate")
    if value.get("counterfactual_factors") != list(FACTORS):
        raise CounterfactualScoringWallError("publication lost factor coverage")
    _authority(value, pre_outcome=False)


def _selftest_lock() -> dict[str, Any]:
    value = {
        "schema": LOCK_SCHEMA,
        "market": "NG",
        "group": 15,
        "status": LOCK_READY,
        "authority": "G15_COUNTERFACTUAL_PRE_SCORING_LOCK_ONLY",
        "exact_refinement_authorization_fingerprint": "a",
        "exact_replay_completion_fingerprint": "b",
        "replay_fingerprint": "c",
        "anchor_fingerprint": "d",
        "refine_stream_fingerprint": "e",
        "counterfactual_attribution_fingerprint": "f",
        "blind_forecast_sha256": "g",
        "refined_forecast_sha256": "h",
        "refined_curve_fingerprint": "i",
        "counterfactual_factors": list(FACTORS),
        "lesson_candidate_ids_fixed_before_scoring": [],
        "stand_down_days": [],
        "actual_g15_outcomes_used": False,
        "g15_fixed_scoring_authorized": True,
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
        "next_permitted_stage": "EXACT_G15_BLIND_AND_REFINED_SCORING_AND_PUBLICATION",
    }
    value["lock_fingerprint"] = _fp(value)
    return value


def selftest() -> int:
    lock = _selftest_lock()
    validate_lock(lock)
    altered = copy.deepcopy(lock)
    altered["actual_g15_outcomes_used"] = True
    altered["lock_fingerprint"] = _fp({k: v for k, v in altered.items() if k != "lock_fingerprint"})
    try:
        validate_lock(altered)
    except CounterfactualScoringWallError:
        pass
    else:
        raise AssertionError("outcome-tainted lock was accepted")
    print("[ng_g15_counterfactual_scoring_wall] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Lock G15 counterfactual attribution before scoring")
    parser.add_argument("--selftest", action="store_true")
    sub = parser.add_subparsers(dest="command")
    lock = sub.add_parser("lock")
    for name in ("authorization", "replay", "anchor", "refine-stream", "attribution", "blind", "refined"):
        lock.add_argument("--" + name, type=Path, required=True)
    lock.add_argument("--out", type=Path, required=True)
    publish = sub.add_parser("publish")
    publish.add_argument("--lock", type=Path, required=True)
    publish.add_argument("--publication", type=Path, required=True)
    publish.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.command == "lock":
        load = lambda path: json.loads(path.read_text(encoding="utf-8"))
        result = build_lock(
            authorization=load(args.authorization), replay=load(args.replay), anchor=load(args.anchor),
            refine_stream=load(args.refine_stream), attribution=load(args.attribution),
            blind=load(args.blind), refined=load(args.refined),
            blind_bytes=args.blind.read_bytes(), refined_bytes=args.refined.read_bytes(),
        )
    elif args.command == "publish":
        result = build_completion(
            lock=json.loads(args.lock.read_text(encoding="utf-8")),
            publication=json.loads(args.publication.read_text(encoding="utf-8")),
        )
    else:
        parser.error("choose lock or publish")
    _atomic(args.out, result)
    print(json.dumps({"status": result["status"], "fingerprint": result.get("lock_fingerprint") or result.get("completion_fingerprint")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
