#!/usr/bin/env python3
"""Outcome-scored adjudication for G15 microstructure lesson proposals.

This module is downstream of the immutable blind forecast, causal replay, refined
curve, and outcome scorer. It does not create a forecast and cannot update
``knowledge/ng_brain.json``. It associates each pre-existing replay proposal with
the scored G15 days on which that mechanism was materially attributed, records
support and counterexamples, and produces a conservative registry of candidates
eligible only for chronological G16 SHADOW testing.

A positive day-level result means the full causal refined path reduced path MAE
relative to the immutable blind path. It is not proof that one mechanism caused
the improvement; the artifact keeps that limitation explicit.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

from ng_historical_manifest import G15_DATES
from ng_g15_path_score import validate_comparison

SCHEMA = "ng_g15_lesson_adjudication.v1"
AUTHORITY = "LESSON_ADJUDICATION_ONLY"
G16_REGISTRY_SCHEMA = "ng_g16_shadow_lesson_registry.v1"
EPS = 1e-9


class LessonAdjudicationError(ValueError):
    """Raised when lesson evidence is incomplete, contradictory, or tampered."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _validate_fingerprint(artifact: Mapping[str, Any], field_name: str, *, label: str) -> None:
    payload = copy.deepcopy(dict(artifact))
    observed = payload.pop(field_name, None)
    if not isinstance(observed, str) or observed != _fingerprint(payload):
        raise LessonAdjudicationError(f"{label}: {field_name} mismatch")


def validate_daily_audit(audit: Mapping[str, Any]) -> None:
    if audit.get("schema") != "ng_g15_daily_refine_audit.v1":
        raise LessonAdjudicationError("audit: schema mismatch")
    if audit.get("authority") != "REFINE_AUDIT_ONLY":
        raise LessonAdjudicationError("audit: authority mismatch")
    if audit.get("execution_authority") is not False:
        raise LessonAdjudicationError("audit: execution authority must remain false")
    if int(audit.get("group") or 0) != 15:
        raise LessonAdjudicationError("audit: group must be 15")
    if int(audit.get("n_days") or 0) != len(G15_DATES):
        raise LessonAdjudicationError("audit: n_days must equal canonical G15 count")
    days = [str(day.get("date") or "") for day in audit.get("days") or []]
    if days != list(G15_DATES):
        raise LessonAdjudicationError("audit: canonical G15 days are incomplete or out of order")
    if any(day.get("outcome_scored") is not False for day in audit.get("days") or []):
        raise LessonAdjudicationError("audit: causal audit must remain outcome-blind")
    _validate_fingerprint(audit, "audit_fingerprint", label="audit")


def validate_unscored_proposals(proposals: Mapping[str, Any], *, audit_fingerprint: str) -> None:
    if proposals.get("schema") != "ng_g15_lesson_proposals.v1":
        raise LessonAdjudicationError("proposals: schema mismatch")
    if proposals.get("authority") != "LESSON_PROPOSAL_ONLY":
        raise LessonAdjudicationError("proposals: authority mismatch")
    if proposals.get("execution_authority") is not False:
        raise LessonAdjudicationError("proposals: execution authority must remain false")
    if proposals.get("may_update_ng_brain") is not False:
        raise LessonAdjudicationError("proposals: may_update_ng_brain must remain false")
    if int(proposals.get("group") or 0) != 15:
        raise LessonAdjudicationError("proposals: group must be 15")
    if proposals.get("source_audit_fingerprint") != audit_fingerprint:
        raise LessonAdjudicationError("proposals: source audit fingerprint mismatch")
    identifiers: set[str] = set()
    for proposal in proposals.get("proposals") or []:
        identifier = str(proposal.get("id") or "")
        if not identifier:
            raise LessonAdjudicationError("proposals: proposal id is required")
        if identifier in identifiers:
            raise LessonAdjudicationError(f"proposals: duplicate id {identifier}")
        identifiers.add(identifier)
        if proposal.get("may_update_ng_brain") is not False:
            raise LessonAdjudicationError(f"proposals:{identifier}: brain mutation must remain false")
        dates = [str(day) for day in proposal.get("supporting_g15_days") or []]
        unknown = sorted(set(dates) - set(G15_DATES))
        if unknown:
            raise LessonAdjudicationError(
                f"proposals:{identifier}: non-G15 supporting days {', '.join(unknown)}"
            )
    _validate_fingerprint(proposals, "proposal_fingerprint", label="proposals")


def _timing_improvement(blind: Any, refined: Any) -> float | None:
    blind_value = _finite(blind)
    refined_value = _finite(refined)
    if blind_value is None or refined_value is None:
        return None
    return blind_value - refined_value


def _classify_day(path_improvement: float) -> str:
    if path_improvement > EPS:
        return "SUPPORT"
    if path_improvement < -EPS:
        return "COUNTEREXAMPLE"
    return "NEUTRAL"


def _proposal_status(*, sample_size: int, support_count: int, counterexample_count: int,
                     mean_path_improvement: float, direction_gain_count: int,
                     direction_harm_count: int) -> tuple[str, str, bool]:
    """Return (status, confidence, eligible_for_g16_shadow)."""
    if sample_size < 2:
        return "INSUFFICIENT_G15", "LOW", False
    if (support_count >= 2 and counterexample_count == 0 and
            mean_path_improvement > EPS and direction_harm_count == 0):
        confidence = "MODERATE_G15_ONLY" if sample_size >= 3 else "LOW_G15_ONLY"
        return "G15_SUPPORTED_SHADOW_CANDIDATE", confidence, True
    if (counterexample_count > support_count or mean_path_improvement < -EPS or
            direction_harm_count > direction_gain_count):
        return "G15_CONTRADICTED", "LOW", False
    return "G15_MIXED", "LOW", False


def _scored_day_row(date: str, comparison_day: Mapping[str, Any],
                    audit_day: Mapping[str, Any]) -> dict[str, Any]:
    path = _finite(comparison_day.get("path_mae_improvement_usd"))
    endpoint = _finite(comparison_day.get("endpoint_improvement_usd"))
    if path is None or endpoint is None:
        raise LessonAdjudicationError(f"{date}: comparison improvement values are missing")
    blind_direction = bool(comparison_day.get("blind_net_direction_ok"))
    refined_direction = bool(comparison_day.get("refined_net_direction_ok"))
    blind_regime = bool(comparison_day.get("blind_regime_ok"))
    refined_regime = bool(comparison_day.get("refined_regime_ok"))
    major_timing = _timing_improvement(
        comparison_day.get("blind_major_move_timing_error_steps"),
        comparison_day.get("refined_major_move_timing_error_steps"),
    )
    turn_timing = _timing_improvement(
        comparison_day.get("blind_turn_timing_error_steps"),
        comparison_day.get("refined_turn_timing_error_steps"),
    )
    return {
        "date": date,
        "classification": _classify_day(path),
        "path_mae_improvement_usd": round(path, 8),
        "endpoint_improvement_usd": round(endpoint, 8),
        "direction_gain": (not blind_direction) and refined_direction,
        "direction_harm": blind_direction and (not refined_direction),
        "regime_gain": (not blind_regime) and refined_regime,
        "regime_harm": blind_regime and (not refined_regime),
        "major_move_timing_improvement_steps": None if major_timing is None else round(major_timing, 8),
        "dominant_turn_timing_improvement_steps": None if turn_timing is None else round(turn_timing, 8),
        "n_completed_states": int(audit_day.get("n_completed_states") or 0),
        "flow_allowed_states": int(audit_day.get("flow_allowed_states") or 0),
        "queue_allowed_states": int(audit_day.get("queue_allowed_states") or 0),
        "max_abs_direction_posterior_shift": _finite(
            audit_day.get("max_abs_direction_posterior_shift")
        ),
        "stand_down_reasons": copy.deepcopy(dict(audit_day.get("stand_down_reasons") or {})),
        "association_caveat": (
            "The mechanism was materially attributed on this day, but the scored "
            "improvement belongs to the full refined path rather than this mechanism alone."
        ),
    }


def build_adjudication(audit: Mapping[str, Any], proposals: Mapping[str, Any],
                       comparison: Mapping[str, Any]) -> dict[str, Any]:
    audit_before = copy.deepcopy(dict(audit))
    proposals_before = copy.deepcopy(dict(proposals))
    comparison_before = copy.deepcopy(dict(comparison))

    validate_daily_audit(audit)
    validate_unscored_proposals(
        proposals, audit_fingerprint=str(audit["audit_fingerprint"])
    )
    try:
        validate_comparison(comparison)
    except Exception as error:
        raise LessonAdjudicationError(f"comparison: {error}") from error
    if comparison.get("lesson_gate", {}).get("may_update_ng_brain") is not False:
        raise LessonAdjudicationError("comparison: lesson gate cannot update ng_brain")

    audit_by_day = {str(day["date"]): dict(day) for day in audit.get("days") or []}
    comparison_by_day = {
        str(day["date"]): dict(day) for day in comparison.get("days") or []
    }
    if set(audit_by_day) != set(G15_DATES) or set(comparison_by_day) != set(G15_DATES):
        raise LessonAdjudicationError(
            "source artifacts do not contain the same canonical G15 days"
        )

    adjudications: list[dict[str, Any]] = []
    registry_candidates: list[dict[str, Any]] = []
    for original in proposals.get("proposals") or []:
        proposal = copy.deepcopy(dict(original))
        identifier = str(proposal["id"])
        attributed_days = sorted(
            set(str(day) for day in proposal.get("supporting_g15_days") or [])
        )
        day_rows = [
            _scored_day_row(date, comparison_by_day[date], audit_by_day[date])
            for date in attributed_days
        ]
        support = [row["date"] for row in day_rows if row["classification"] == "SUPPORT"]
        counterexamples = [
            row["date"] for row in day_rows if row["classification"] == "COUNTEREXAMPLE"
        ]
        neutral = [row["date"] for row in day_rows if row["classification"] == "NEUTRAL"]
        sample_size = len(day_rows)
        path_sum = sum(float(row["path_mae_improvement_usd"]) for row in day_rows)
        endpoint_sum = sum(float(row["endpoint_improvement_usd"]) for row in day_rows)
        mean_path = 0.0 if sample_size == 0 else path_sum / sample_size
        mean_endpoint = 0.0 if sample_size == 0 else endpoint_sum / sample_size
        direction_gain = sum(int(row["direction_gain"]) for row in day_rows)
        direction_harm = sum(int(row["direction_harm"]) for row in day_rows)
        regime_gain = sum(int(row["regime_gain"]) for row in day_rows)
        regime_harm = sum(int(row["regime_harm"]) for row in day_rows)
        status, confidence, eligible = _proposal_status(
            sample_size=sample_size,
            support_count=len(support),
            counterexample_count=len(counterexamples),
            mean_path_improvement=mean_path,
            direction_gain_count=direction_gain,
            direction_harm_count=direction_harm,
        )
        row = {
            "id": identifier,
            "authority": AUTHORITY,
            "status": status,
            "confidence": confidence,
            "mechanism": proposal.get("mechanism"),
            "scope": "G15 outcome-scored association; not isolated mechanism causality",
            "actual_outcomes_used": True,
            "execution_authority": False,
            "may_update_ng_brain": False,
            "original_proposal_status": proposal.get("status"),
            "original_supporting_g15_days": attributed_days,
            "scored_supporting_days": support,
            "scored_counterexample_days": counterexamples,
            "neutral_days": neutral,
            "sample_size_days": sample_size,
            "metrics": {
                "support_count": len(support),
                "counterexample_count": len(counterexamples),
                "neutral_count": len(neutral),
                "path_mae_improvement_sum_usd": round(path_sum, 8),
                "path_mae_improvement_mean_usd": round(mean_path, 8),
                "endpoint_improvement_sum_usd": round(endpoint_sum, 8),
                "endpoint_improvement_mean_usd": round(mean_endpoint, 8),
                "direction_gain_count": direction_gain,
                "direction_harm_count": direction_harm,
                "regime_gain_count": regime_gain,
                "regime_harm_count": regime_harm,
            },
            "days": day_rows,
            "g16_shadow_test": {
                "eligible": eligible,
                "authority": "G16_PRE_CUTOFF_SHADOW_TEST_ONLY",
                "may_update_ng_brain": False,
                "may_change_g16_blind_prior": False,
                "requirements": [
                    "register the mechanism before reading any G16 target-day outcome",
                    "use only G16 evidence available at each decision timestamp",
                    "score chronologically after the forecast/refine artifact is locked",
                    "retain counterexamples and stand-downs",
                ],
            },
            "requirements_before_brain_adoption": [
                "G16 chronological pre-cutoff validation",
                "untouched holdout beyond G16",
                "forward-live SHADOW validation",
                "explicit human review before any ng_brain change",
            ],
        }
        row["evidence_fingerprint"] = _fingerprint(row)
        adjudications.append(row)
        if eligible:
            registry_candidates.append(
                {
                    "proposal_id": identifier,
                    "mechanism": proposal.get("mechanism"),
                    "g15_status": status,
                    "g15_confidence": confidence,
                    "g15_evidence_fingerprint": row["evidence_fingerprint"],
                    "authority": "G16_PRE_CUTOFF_SHADOW_TEST_ONLY",
                    "may_update_ng_brain": False,
                    "may_change_g16_blind_prior": False,
                    "pre_registered_before_g16_outcomes": True,
                }
            )

    registry = {
        "schema": G16_REGISTRY_SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "authority": "G16_PRE_CUTOFF_SHADOW_TEST_ONLY",
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "candidate_count": len(registry_candidates),
        "candidates": registry_candidates,
        "gate": {
            "g16_refinement_authorized": bool(registry_candidates),
            "g16_outcome_access_authorized": False,
            "reason": (
                "Only pre-registered G15-supported candidates may enter G16 SHADOW "
                "refinement; G16 target outcomes remain inaccessible until artifacts lock."
            ),
        },
    }
    registry["registry_fingerprint"] = _fingerprint(registry)

    result = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": AUTHORITY,
        "execution_authority": False,
        "actual_outcomes_used": True,
        "may_update_ng_brain": False,
        "source": {
            "audit_fingerprint": audit["audit_fingerprint"],
            "proposal_fingerprint": proposals["proposal_fingerprint"],
            "comparison_fingerprint": comparison["artifact_fingerprint"],
            "blind_score_fingerprint": comparison.get("blind_score_fingerprint"),
            "refined_score_fingerprint": comparison.get("refined_score_fingerprint"),
        },
        "method": {
            "day_classification": (
                "SUPPORT when the full refined path has positive path-MAE improvement, "
                "COUNTEREXAMPLE when negative, otherwise NEUTRAL."
            ),
            "causal_limitation": (
                "Mechanism attribution is associated with full-path improvement and "
                "does not isolate a mechanism's independent causal effect."
            ),
            "adoption_policy": (
                "No G15 result may directly update ng_brain; only conservative "
                "pre-registration for G16 SHADOW testing is emitted."
            ),
        },
        "adjudications": adjudications,
        "g16_shadow_registry": registry,
        "note": (
            "Outcome-scored evidence only. This artifact cannot alter the blind prior, "
            "the causal refiner, execution authority, or knowledge/ng_brain.json."
        ),
    }
    result["artifact_fingerprint"] = _fingerprint(result)
    validate_adjudication(result)

    if dict(audit) != audit_before:
        raise LessonAdjudicationError("audit mutated during adjudication")
    if dict(proposals) != proposals_before:
        raise LessonAdjudicationError("proposals mutated during adjudication")
    if dict(comparison) != comparison_before:
        raise LessonAdjudicationError("comparison mutated during adjudication")
    return result


def validate_adjudication(result: Mapping[str, Any]) -> None:
    if result.get("schema") != SCHEMA:
        raise LessonAdjudicationError("adjudication: schema mismatch")
    if result.get("authority") != AUTHORITY:
        raise LessonAdjudicationError("adjudication: authority mismatch")
    if result.get("execution_authority") is not False:
        raise LessonAdjudicationError("adjudication: execution authority must remain false")
    if result.get("actual_outcomes_used") is not True:
        raise LessonAdjudicationError("adjudication: outcome use must be disclosed")
    if result.get("may_update_ng_brain") is not False:
        raise LessonAdjudicationError("adjudication: may_update_ng_brain must remain false")
    identifiers: set[str] = set()
    eligible_ids: set[str] = set()
    for row in result.get("adjudications") or []:
        identifier = str(row.get("id") or "")
        if not identifier or identifier in identifiers:
            raise LessonAdjudicationError("adjudication: missing or duplicate proposal id")
        identifiers.add(identifier)
        if row.get("may_update_ng_brain") is not False:
            raise LessonAdjudicationError(
                f"adjudication:{identifier}: brain mutation is forbidden"
            )
        payload = copy.deepcopy(dict(row))
        fingerprint = payload.pop("evidence_fingerprint", None)
        if fingerprint != _fingerprint(payload):
            raise LessonAdjudicationError(
                f"adjudication:{identifier}: evidence fingerprint mismatch"
            )
        if bool((row.get("g16_shadow_test") or {}).get("eligible")):
            eligible_ids.add(identifier)
    registry = dict(result.get("g16_shadow_registry") or {})
    if registry.get("schema") != G16_REGISTRY_SCHEMA:
        raise LessonAdjudicationError("registry: schema mismatch")
    if registry.get("execution_authority") is not False:
        raise LessonAdjudicationError("registry: execution authority must remain false")
    if registry.get("actual_g16_outcomes_used") is not False:
        raise LessonAdjudicationError("registry: G16 outcomes must remain unused")
    if registry.get("may_update_ng_brain") is not False:
        raise LessonAdjudicationError("registry: brain mutation must remain false")
    candidate_ids = {
        str(row.get("proposal_id") or "") for row in registry.get("candidates") or []
    }
    if candidate_ids != eligible_ids:
        raise LessonAdjudicationError(
            "registry: candidates differ from eligible adjudications"
        )
    if int(registry.get("candidate_count") or 0) != len(candidate_ids):
        raise LessonAdjudicationError("registry: candidate_count mismatch")
    registry_payload = copy.deepcopy(registry)
    registry_fingerprint = registry_payload.pop("registry_fingerprint", None)
    if registry_fingerprint != _fingerprint(registry_payload):
        raise LessonAdjudicationError("registry: fingerprint mismatch")
    payload = copy.deepcopy(dict(result))
    fingerprint = payload.pop("artifact_fingerprint", None)
    if fingerprint != _fingerprint(payload):
        raise LessonAdjudicationError("adjudication: artifact fingerprint mismatch")


def _fixture() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    audit_days = []
    comparison_days = []
    for index, date in enumerate(G15_DATES):
        audit_days.append(
            {
                "date": date,
                "n_completed_states": 5,
                "flow_allowed_states": 5,
                "queue_allowed_states": 4,
                "stand_down_reasons": {},
                "max_abs_direction_posterior_shift": 0.1,
                "strongest_attribution": [
                    {
                        "name": "signed_flow" if index < 3 else "other",
                        "used_count": 2,
                        "absolute_contribution_sum": 0.2,
                    }
                ],
                "outcome_scored": False,
            }
        )
        improvement = 20.0 if index < 3 else 0.0
        comparison_days.append(
            {
                "date": date,
                "path_mae_improvement_usd": improvement,
                "endpoint_improvement_usd": improvement,
                "blind_net_direction_ok": False if index < 3 else True,
                "refined_net_direction_ok": True,
                "blind_regime_ok": False if index < 3 else True,
                "refined_regime_ok": True,
                "blind_major_move_timing_error_steps": 2,
                "refined_major_move_timing_error_steps": 1,
                "blind_turn_timing_error_steps": 2,
                "refined_turn_timing_error_steps": 1,
            }
        )
    audit = {
        "schema": "ng_g15_daily_refine_audit.v1",
        "market": "NG",
        "group": 15,
        "authority": "REFINE_AUDIT_ONLY",
        "execution_authority": False,
        "n_days": len(G15_DATES),
        "days": audit_days,
    }
    audit["audit_fingerprint"] = _fingerprint(audit)
    proposals = {
        "schema": "ng_g15_lesson_proposals.v1",
        "market": "NG",
        "group": 15,
        "authority": "LESSON_PROPOSAL_ONLY",
        "execution_authority": False,
        "may_update_ng_brain": False,
        "source_audit_fingerprint": audit["audit_fingerprint"],
        "proposals": [
            {
                "id": "g15_mbo.signed_flow",
                "status": "UNSCORED_CANDIDATE",
                "authority": "LESSON_PROPOSAL_ONLY",
                "may_update_ng_brain": False,
                "mechanism": "signed flow after onset",
                "supporting_g15_days": list(G15_DATES[:3]),
            }
        ],
    }
    proposals["proposal_fingerprint"] = _fingerprint(proposals)
    comparison = {
        "schema": "ng_g15_path_comparison.v1",
        "market": "NG",
        "group": 15,
        "authority": "OUTCOME_SCORING_ONLY",
        "execution_authority": False,
        "actual_outcomes_used": True,
        "may_update_ng_brain": False,
        "blind_score_fingerprint": "blind",
        "refined_score_fingerprint": "refined",
        "days": comparison_days,
        "block": {},
        "lesson_gate": {
            "may_update_ng_brain": False,
            "status": "SCORED_EVIDENCE_ONLY",
            "requirements_before_adoption": [],
        },
    }
    comparison["artifact_fingerprint"] = _fingerprint(comparison)
    return audit, proposals, comparison


def selftest() -> int:
    audit, proposals, comparison = _fixture()
    result = build_adjudication(audit, proposals, comparison)
    row = result["adjudications"][0]
    assert row["status"] == "G15_SUPPORTED_SHADOW_CANDIDATE"
    assert row["sample_size_days"] == 3
    assert row["may_update_ng_brain"] is False
    assert result["g16_shadow_registry"]["candidate_count"] == 1
    assert result["g16_shadow_registry"]["actual_g16_outcomes_used"] is False
    print("[ng_g15_lesson_adjudication] selftest PASS")
    return 0


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Adjudicate G15 replay lesson proposals against blind-vs-refined scores"
    )
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--proposals", type=Path)
    parser.add_argument("--comparison", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if any(value is None for value in (args.audit, args.proposals, args.comparison, args.out)):
        parser.error("--audit, --proposals, --comparison, and --out are required")
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    proposals = json.loads(args.proposals.read_text(encoding="utf-8"))
    comparison = json.loads(args.comparison.read_text(encoding="utf-8"))
    result = build_adjudication(audit, proposals, comparison)
    _atomic_json(args.out, result)
    print(
        json.dumps(
            {
                "out": str(args.out),
                "adjudication_count": len(result["adjudications"]),
                "g16_shadow_candidate_count": result["g16_shadow_registry"]["candidate_count"],
                "may_update_ng_brain": False,
                "execution_authority": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
