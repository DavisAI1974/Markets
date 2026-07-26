#!/usr/bin/env python3
"""Bind validated G15 scoring and lessons to the pre-cutoff G16 lineage.

The legacy G15->G16 lineage gate proves that scored G15 lessons and the G16 SHADOW
plan use one registry. It predates the recursive attribution-bound publication gate,
so it does not itself prove that those lessons descend from the exact six-factor
authorization and the separately scored blind/refined paths. This audit-only wrapper
closes that cross-stage seam before any G16 corpus or causal work may start.

The gate never reads G16 outcomes, changes either blind prior, mutates the posterior or
``knowledge/ng_brain.json``, grants execution authority, or starts the options lane.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

SCHEMA = "ng_g15_g16_attribution_bound_lineage_gate.v1"
AUTHORITY = "G15_ATTRIBUTION_BOUND_LESSONS_TO_G16_PRE_CUTOFF_LINEAGE_ONLY"
READY = "G15_ATTRIBUTION_BOUND_LESSONS_G16_LINEAGE_AUTHORIZED"
READY_WITH_STAND_DOWNS = (
    "G15_ATTRIBUTION_BOUND_LESSONS_G16_LINEAGE_AUTHORIZED_WITH_STAND_DOWNS"
)
BOUND_SCHEMA = "ng_g15_attribution_bound_publication_gate.v1"
LESSON_SCHEMA = "ng_g15_counterfactual_lesson_gate.v1"
LINEAGE_SCHEMA = "ng_g15_g16_counterfactual_lineage_gate.v1"


class AttributionBoundLineageError(ValueError):
    """Raised when G16 lineage is detached from attribution-bound G15 scoring."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AttributionBoundLineageError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise AttributionBoundLineageError(f"artifact must be a JSON object: {path}")
    return value


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _verify_fingerprint(value: Mapping[str, Any], field: str, *, label: str) -> dict[str, Any]:
    candidate = copy.deepcopy(dict(value))
    observed = candidate.pop(field, None)
    if not isinstance(observed, str) or observed != _fingerprint(candidate):
        raise AttributionBoundLineageError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _default_validate_bound(value: Mapping[str, Any]) -> None:
    from ng_g15_attribution_bound_publication_gate import validate_gate

    validate_gate(value)


def _default_validate_lesson(
    value: Mapping[str, Any],
    *,
    replay: Mapping[str, Any],
    anchor: Mapping[str, Any],
    refine_stream: Mapping[str, Any],
    attribution: Mapping[str, Any],
    audit: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> None:
    from ng_g15_counterfactual_lesson_gate import validate_gate

    validate_gate(
        value,
        replay=replay,
        anchor=anchor,
        refine_stream=refine_stream,
        attribution=attribution,
        audit=audit,
        comparison=comparison,
    )


def _default_validate_lineage(
    value: Mapping[str, Any],
    *,
    counterfactual_gate: Mapping[str, Any],
    g15_publication: Mapping[str, Any],
    g16_plan: Mapping[str, Any],
    replay: Mapping[str, Any],
    anchor: Mapping[str, Any],
    refine_stream: Mapping[str, Any],
    attribution: Mapping[str, Any],
    audit: Mapping[str, Any],
    comparison: Mapping[str, Any],
    g16_blind_forecast: Mapping[str, Any],
    g16_blind_safe_state: Mapping[str, Any],
) -> None:
    from ng_g15_g16_counterfactual_lineage_gate import validate_lineage

    validate_lineage(
        value,
        counterfactual_gate=counterfactual_gate,
        g15_publication=g15_publication,
        g16_plan=g16_plan,
        replay=replay,
        anchor=anchor,
        refine_stream=refine_stream,
        attribution=attribution,
        audit=audit,
        comparison=comparison,
        g16_blind_forecast=g16_blind_forecast,
        g16_blind_safe_state=g16_blind_safe_state,
    )


def _controls(value: Mapping[str, Any], *, label: str) -> None:
    false_fields = (
        "actual_g16_outcomes_used",
        "g16_scoring_authorized",
        "random_shuffle_used",
        "may_change_g16_blind_prior",
        "may_change_blind_prior",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_select_lessons_from_g16_outcomes",
        "may_update_ng_brain",
        "execution_authority",
        "g16_outcome_access_authorized",
        "options_lane_started",
    )
    for field in false_fields:
        if field in value and value.get(field) is not False:
            raise AttributionBoundLineageError(f"{label} must keep {field}=false")
    if value.get("actual_g15_outcomes_used") is not True:
        raise AttributionBoundLineageError(f"{label} must disclose fixed G15 outcome use")
    if value.get("blind_forecasts_immutable") is not True:
        raise AttributionBoundLineageError(f"{label} must preserve blind forecast immutability")
    if value.get("one_signal_authority_preserved") is not True:
        raise AttributionBoundLineageError(f"{label} must preserve one signal authority")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise AttributionBoundLineageError(f"{label} must keep CME event contracts SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise AttributionBoundLineageError(f"{label} must preserve tastytrade rather than IBKR")


def _build_gate(
    *,
    attribution_bound_publication: Mapping[str, Any],
    counterfactual_lesson_gate: Mapping[str, Any],
    legacy_lineage: Mapping[str, Any],
    g15_publication: Mapping[str, Any],
    g16_plan: Mapping[str, Any],
    replay: Mapping[str, Any],
    anchor: Mapping[str, Any],
    refine_stream: Mapping[str, Any],
    attribution: Mapping[str, Any],
    audit: Mapping[str, Any],
    comparison: Mapping[str, Any],
    g16_blind_forecast: Mapping[str, Any],
    g16_blind_safe_state: Mapping[str, Any],
    bound_validator: Callable[[Mapping[str, Any]], None] = _default_validate_bound,
    lesson_validator: Callable[..., None] = _default_validate_lesson,
    lineage_validator: Callable[..., None] = _default_validate_lineage,
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (
            attribution_bound_publication,
            counterfactual_lesson_gate,
            legacy_lineage,
            g15_publication,
            g16_plan,
            replay,
            anchor,
            refine_stream,
            attribution,
            audit,
            comparison,
            g16_blind_forecast,
            g16_blind_safe_state,
        )
    )
    try:
        bound_validator(attribution_bound_publication)
        lesson_validator(
            counterfactual_lesson_gate,
            replay=replay,
            anchor=anchor,
            refine_stream=refine_stream,
            attribution=attribution,
            audit=audit,
            comparison=comparison,
        )
        lineage_validator(
            legacy_lineage,
            counterfactual_gate=counterfactual_lesson_gate,
            g15_publication=g15_publication,
            g16_plan=g16_plan,
            replay=replay,
            anchor=anchor,
            refine_stream=refine_stream,
            attribution=attribution,
            audit=audit,
            comparison=comparison,
            g16_blind_forecast=g16_blind_forecast,
            g16_blind_safe_state=g16_blind_safe_state,
        )
    except Exception as error:
        raise AttributionBoundLineageError(str(error)) from error

    bound = _verify_fingerprint(
        attribution_bound_publication, "fingerprint", label="attribution-bound publication"
    )
    lesson = _verify_fingerprint(
        counterfactual_lesson_gate, "fingerprint", label="counterfactual lesson gate"
    )
    lineage = _verify_fingerprint(legacy_lineage, "fingerprint", label="legacy G15-G16 lineage")

    if bound.get("schema") != BOUND_SCHEMA:
        raise AttributionBoundLineageError("attribution-bound publication schema mismatch")
    if lesson.get("schema") != LESSON_SCHEMA:
        raise AttributionBoundLineageError("counterfactual lesson gate schema mismatch")
    if lineage.get("schema") != LINEAGE_SCHEMA:
        raise AttributionBoundLineageError("legacy G15-G16 lineage schema mismatch")
    if bound.get("status") not in {
        "G15_ATTRIBUTION_BOUND_PUBLICATION_VERIFIED",
        "G15_ATTRIBUTION_BOUND_PUBLICATION_VERIFIED_WITH_STAND_DOWNS",
    }:
        raise AttributionBoundLineageError("attribution-bound publication is not ready")
    if lesson.get("status") not in {
        "G15_COUNTERFACTUAL_LESSONS_ADJUDICATED",
        "G15_COUNTERFACTUAL_LESSONS_ADJUDICATED_WITH_STAND_DOWNS",
    }:
        raise AttributionBoundLineageError("counterfactual lesson gate is not ready")
    if lineage.get("status") not in {
        "G15_PUBLICATION_G16_PLAN_COUNTERFACTUAL_LINEAGE_BOUND",
        "G15_PUBLICATION_G16_PLAN_COUNTERFACTUAL_LINEAGE_BOUND_WITH_STAND_DOWNS",
    }:
        raise AttributionBoundLineageError("legacy G15-G16 lineage is not ready")

    publication_fp = str(g15_publication.get("completion_fingerprint") or "")
    plan_fp = str(g16_plan.get("plan_fingerprint") or "")
    lesson_source = dict(lesson.get("source") or {})
    adjudication = dict(lesson.get("adjudication") or {})
    registry = dict(adjudication.get("g16_shadow_registry") or {})

    _controls(bound, label="attribution-bound publication")
    _controls(lesson, label="counterfactual lesson gate")
    _controls(lineage, label="legacy G15-G16 lineage")

    equalities = {
        "publication completion": (
            str(bound.get("publication_completion_fingerprint") or ""),
            publication_fp,
            str(lineage.get("g15_publication_fingerprint") or ""),
        ),
        "counterfactual attribution": (
            str(bound.get("attribution_fingerprint") or ""),
            str(lesson_source.get("counterfactual_fingerprint") or ""),
            str(lineage.get("counterfactual_attribution_fingerprint") or ""),
        ),
        "score comparison": (
            str(bound.get("comparison_fingerprint") or ""),
            str(lesson_source.get("comparison_fingerprint") or ""),
        ),
        "blind score": (
            str(bound.get("blind_score_fingerprint") or ""),
            str(lesson_source.get("blind_score_fingerprint") or ""),
        ),
        "refined score": (
            str(bound.get("refined_score_fingerprint") or ""),
            str(lesson_source.get("refined_score_fingerprint") or ""),
        ),
        "counterfactual lesson gate": (
            str(lesson.get("fingerprint") or ""),
            str(lineage.get("counterfactual_lesson_gate_fingerprint") or ""),
        ),
        "lesson adjudication": (
            str(adjudication.get("artifact_fingerprint") or ""),
            str(lineage.get("g15_adjudication_fingerprint") or ""),
        ),
        "G16 lesson registry": (
            str(registry.get("registry_fingerprint") or ""),
            str(lineage.get("g16_registry_fingerprint") or ""),
        ),
        "G16 plan": (plan_fp, str(lineage.get("g16_plan_fingerprint") or "")),
    }
    for label, values in equalities.items():
        if any(not value for value in values) or len(set(values)) != 1:
            raise AttributionBoundLineageError(f"{label} lineage mismatch")

    if bound.get("lesson_proposals_brain_write_forbidden") is not True:
        raise AttributionBoundLineageError(
            "attribution-bound publication lost the no-brain-write lesson contract"
        )
    if lesson.get("may_update_ng_brain") is not False or lineage.get("may_update_ng_brain") is not False:
        raise AttributionBoundLineageError("G15 lesson lineage may not update ng_brain.json")

    candidate_ids = [str(value) for value in lineage.get("candidate_ids") or []]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise AttributionBoundLineageError("G16 candidate ids are duplicated")
    if int(lineage.get("candidate_count") or 0) != len(candidate_ids):
        raise AttributionBoundLineageError("G16 candidate_count mismatch")

    stand_down_days = sorted(
        set(str(day) for day in bound.get("stand_down_days") or [])
        | set(str(day) for day in lesson.get("stand_down_days") or [])
        | set(str(day) for day in lineage.get("stand_down_days") or [])
    )
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": READY_WITH_STAND_DOWNS if stand_down_days else READY,
        "authority": AUTHORITY,
        "attribution_bound_publication_fingerprint": bound["fingerprint"],
        "attribution_authorization_fingerprint": bound[
            "attribution_authorization_fingerprint"
        ],
        "publication_completion_fingerprint": publication_fp,
        "counterfactual_attribution_fingerprint": bound["attribution_fingerprint"],
        "counterfactual_lesson_gate_fingerprint": lesson["fingerprint"],
        "legacy_lineage_fingerprint": lineage["fingerprint"],
        "blind_score_fingerprint": bound["blind_score_fingerprint"],
        "refined_score_fingerprint": bound["refined_score_fingerprint"],
        "comparison_fingerprint": bound["comparison_fingerprint"],
        "g15_adjudication_fingerprint": adjudication["artifact_fingerprint"],
        "g16_registry_fingerprint": registry["registry_fingerprint"],
        "g16_plan_fingerprint": plan_fp,
        "candidate_count": len(candidate_ids),
        "candidate_ids": candidate_ids,
        "candidate_evidence_fingerprints": copy.deepcopy(
            lineage.get("candidate_evidence_fingerprints") or {}
        ),
        "stand_down_days": stand_down_days,
        "all_six_factors_authorized_before_scoring": True,
        "separate_blind_refined_scores_verified": True,
        "scored_lessons_bound_to_attribution_publication": True,
        "g16_plan_bound_to_validated_g15_lessons": True,
        "lesson_proposals_brain_write_forbidden": True,
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": False,
        "g16_scoring_authorized": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_g16_blind_prior": False,
        "may_change_posterior": False,
        "may_select_lessons_from_g16_outcomes": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "g16_outcome_access_authorized": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "VERIFY_G16_MATCHED_CORPUS_AND_RUN_PRE_CUTOFF_CAUSAL_REPLAY",
        "attribution_bound_publication": copy.deepcopy(bound),
        "counterfactual_lesson_gate": copy.deepcopy(lesson),
        "legacy_lineage": copy.deepcopy(lineage),
        "note": (
            "The G16 SHADOW plan and candidate registry are recursively bound to the exact "
            "six-factor authorization, fixed G15 publication, and separate blind/refined "
            "score lineage. G16 outcomes, execution, options, posterior mutation, and "
            "ng_brain.json writes remain forbidden."
        ),
    }
    result["fingerprint"] = _fingerprint(result)

    if (
        attribution_bound_publication,
        counterfactual_lesson_gate,
        legacy_lineage,
        g15_publication,
        g16_plan,
        replay,
        anchor,
        refine_stream,
        attribution,
        audit,
        comparison,
        g16_blind_forecast,
        g16_blind_safe_state,
    ) != originals:
        raise AttributionBoundLineageError("lineage authorization mutated an input artifact")
    return result


def build_gate(**kwargs: Any) -> dict[str, Any]:
    result = _build_gate(**kwargs)
    validate_gate(result, **kwargs)
    return result


def validate_gate(value: Mapping[str, Any], **kwargs: Any) -> None:
    candidate = copy.deepcopy(dict(value))
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != SCHEMA or observed != _fingerprint(candidate):
        raise AttributionBoundLineageError("gate schema or fingerprint mismatch")
    if candidate.get("status") not in {READY, READY_WITH_STAND_DOWNS}:
        raise AttributionBoundLineageError("gate is not ready")
    if candidate.get("authority") != AUTHORITY:
        raise AttributionBoundLineageError("gate authority mismatch")
    _controls(candidate, label="attribution-bound G15-G16 lineage gate")
    for field in (
        "all_six_factors_authorized_before_scoring",
        "separate_blind_refined_scores_verified",
        "scored_lessons_bound_to_attribution_publication",
        "g16_plan_bound_to_validated_g15_lessons",
        "lesson_proposals_brain_write_forbidden",
    ):
        if candidate.get(field) is not True:
            raise AttributionBoundLineageError(f"mandatory gate field mismatch: {field}")
    embedded = (
        candidate.get("attribution_bound_publication"),
        candidate.get("counterfactual_lesson_gate"),
        candidate.get("legacy_lineage"),
    )
    if not all(isinstance(item, Mapping) for item in embedded):
        raise AttributionBoundLineageError("gate lacks recursively embedded G15/G16 lineage evidence")
    supplied = (
        kwargs.get("attribution_bound_publication"),
        kwargs.get("counterfactual_lesson_gate"),
        kwargs.get("legacy_lineage"),
    )
    if all(isinstance(item, Mapping) for item in supplied) and tuple(
        dict(item) for item in embedded
    ) != tuple(dict(item) for item in supplied):
        raise AttributionBoundLineageError("embedded lineage evidence differs from supplied artifacts")
    rebuilt = _build_gate(**kwargs)
    if dict(value) != rebuilt:
        raise AttributionBoundLineageError(
            "gate differs from deterministic recursive reconstruction"
        )


def _noop(*args: Any, **kwargs: Any) -> None:
    return None


def _synthetic_fixture() -> dict[str, Any]:
    publication_fp = "p" * 64
    attribution_fp = "a" * 64
    comparison_fp = "c" * 64
    blind_score_fp = "b" * 64
    refined_score_fp = "r" * 64
    adjudication_fp = "j" * 64
    registry_fp = "g" * 64
    plan_fp = "q" * 64

    bound: dict[str, Any] = {
        "schema": BOUND_SCHEMA,
        "status": "G15_ATTRIBUTION_BOUND_PUBLICATION_VERIFIED",
        "authority": "G15_ATTRIBUTION_BOUND_PUBLICATION_AUDIT_ONLY",
        "attribution_authorization_fingerprint": "u" * 64,
        "publication_completion_fingerprint": publication_fp,
        "attribution_fingerprint": attribution_fp,
        "comparison_fingerprint": comparison_fp,
        "blind_score_fingerprint": blind_score_fp,
        "refined_score_fingerprint": refined_score_fp,
        "stand_down_days": [],
        "lesson_proposals_brain_write_forbidden": True,
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_prior": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "g16_outcome_access_authorized": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }
    bound["fingerprint"] = _fingerprint(bound)

    lesson: dict[str, Any] = {
        "schema": LESSON_SCHEMA,
        "status": "G15_COUNTERFACTUAL_LESSONS_ADJUDICATED",
        "authority": "G15_COUNTERFACTUAL_LESSON_ADJUDICATION_ONLY",
        "source": {
            "counterfactual_fingerprint": attribution_fp,
            "comparison_fingerprint": comparison_fp,
            "blind_score_fingerprint": blind_score_fp,
            "refined_score_fingerprint": refined_score_fp,
        },
        "adjudication": {
            "artifact_fingerprint": adjudication_fp,
            "g16_shadow_registry": {"registry_fingerprint": registry_fp},
        },
        "stand_down_days": [],
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_prior": False,
        "may_change_posterior": False,
        "may_select_lessons_from_g15_scores": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }
    lesson["fingerprint"] = _fingerprint(lesson)

    lineage: dict[str, Any] = {
        "schema": LINEAGE_SCHEMA,
        "status": "G15_PUBLICATION_G16_PLAN_COUNTERFACTUAL_LINEAGE_BOUND",
        "authority": "G15_PUBLICATION_G16_PLAN_COUNTERFACTUAL_LINEAGE_ONLY",
        "g15_publication_fingerprint": publication_fp,
        "counterfactual_attribution_fingerprint": attribution_fp,
        "counterfactual_lesson_gate_fingerprint": lesson["fingerprint"],
        "g15_adjudication_fingerprint": adjudication_fp,
        "g16_registry_fingerprint": registry_fp,
        "g16_plan_fingerprint": plan_fp,
        "candidate_count": 1,
        "candidate_ids": ["g15_counterfactual.activity"],
        "candidate_evidence_fingerprints": {
            "g15_counterfactual.activity": "e" * 64
        },
        "stand_down_days": [],
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": False,
        "g16_scoring_authorized": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_g16_blind_prior": False,
        "may_change_posterior": False,
        "may_select_lessons_from_g16_outcomes": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }
    lineage["fingerprint"] = _fingerprint(lineage)

    return {
        "attribution_bound_publication": bound,
        "counterfactual_lesson_gate": lesson,
        "legacy_lineage": lineage,
        "g15_publication": {"completion_fingerprint": publication_fp},
        "g16_plan": {"plan_fingerprint": plan_fp},
        "replay": {},
        "anchor": {},
        "refine_stream": {},
        "attribution": {},
        "audit": {},
        "comparison": {},
        "g16_blind_forecast": {},
        "g16_blind_safe_state": {},
        "bound_validator": _noop,
        "lesson_validator": _noop,
        "lineage_validator": _noop,
    }


def selftest() -> int:
    fixture = _synthetic_fixture()
    original = copy.deepcopy(fixture)
    result = build_gate(**fixture)
    assert result["status"] == READY
    assert result["g16_plan_bound_to_validated_g15_lessons"] is True
    assert result["actual_g16_outcomes_used"] is False
    assert result["may_update_ng_brain"] is False
    assert result["blind_score_fingerprint"] != result["refined_score_fingerprint"]
    assert fixture == original

    bad = copy.deepcopy(fixture)
    bad["legacy_lineage"]["g16_plan_fingerprint"] = "x" * 64
    bad["legacy_lineage"].pop("fingerprint", None)
    bad["legacy_lineage"]["fingerprint"] = _fingerprint(bad["legacy_lineage"])
    try:
        build_gate(**bad)
    except AttributionBoundLineageError:
        pass
    else:
        raise AssertionError("G16 plan substitution was not rejected")
    print("[ng_g15_g16_attribution_bound_lineage_gate] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attribution-bound-publication", type=Path)
    parser.add_argument("--counterfactual-lesson-gate", type=Path)
    parser.add_argument("--legacy-lineage", type=Path)
    parser.add_argument("--g15-publication", type=Path)
    parser.add_argument("--g16-plan", type=Path)
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--anchor", type=Path)
    parser.add_argument("--refine-stream", type=Path)
    parser.add_argument("--attribution", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--comparison", type=Path)
    parser.add_argument("--g16-blind", type=Path)
    parser.add_argument("--g16-blind-safe-state", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    required = (
        args.attribution_bound_publication,
        args.counterfactual_lesson_gate,
        args.legacy_lineage,
        args.g15_publication,
        args.g16_plan,
        args.replay,
        args.anchor,
        args.refine_stream,
        args.attribution,
        args.audit,
        args.comparison,
        args.g16_blind,
        args.g16_blind_safe_state,
        args.out,
    )
    if any(value is None for value in required):
        parser.error("all artifact arguments and --out are required")
    result = build_gate(
        attribution_bound_publication=_load(args.attribution_bound_publication),
        counterfactual_lesson_gate=_load(args.counterfactual_lesson_gate),
        legacy_lineage=_load(args.legacy_lineage),
        g15_publication=_load(args.g15_publication),
        g16_plan=_load(args.g16_plan),
        replay=_load(args.replay),
        anchor=_load(args.anchor),
        refine_stream=_load(args.refine_stream),
        attribution=_load(args.attribution),
        audit=_load(args.audit),
        comparison=_load(args.comparison),
        g16_blind_forecast=_load(args.g16_blind),
        g16_blind_safe_state=_load(args.g16_blind_safe_state),
    )
    _atomic_json(args.out, result)
    print(
        "[ng_g15_g16_attribution_bound_lineage_gate] "
        f"{result['status']} candidates={result['candidate_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
