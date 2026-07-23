#!/usr/bin/env python3
"""Bind exact G15 counterfactual factors to scored lesson adjudication.

This gate converts the six outcome-blind factor proposals from
``ng_g15_counterfactual_attribution`` into the canonical unscored proposal contract,
then invokes the existing G15 outcome-scored adjudicator. The proposal set is derived
only from deterministic full-minus-neutral counterfactual rows; it cannot be selected or
edited after seeing G15 scores.

The resulting G16 registry remains pre-cutoff SHADOW-only. It cannot change either blind
forecast, the posterior stream, execution authority, or ``knowledge/ng_brain.json``.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from ng_g15_counterfactual_attribution import (
    FACTORS,
    validate_report as validate_counterfactual_report,
)
from ng_g15_lesson_adjudication import (
    build_adjudication,
    validate_adjudication,
    validate_daily_audit,
    validate_unscored_proposals,
)
from ng_g15_path_score import validate_comparison
from ng_historical_manifest import G15_DATES

SCHEMA = "ng_g15_counterfactual_lesson_gate.v1"
PROPOSAL_SCHEMA = "ng_g15_lesson_proposals.v1"
AUTHORITY = "G15_COUNTERFACTUAL_LESSON_ADJUDICATION_ONLY"


class CounterfactualLessonGateError(ValueError):
    """Raised when counterfactual lesson evidence is incomplete or inconsistent."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _expected_support_days(
    attribution: Mapping[str, Any], factor: str
) -> list[str]:
    days = {
        str(row.get("session_day") or "")
        for row in attribution.get("rows") or []
        for item in row.get("factors") or []
        if str(item.get("factor") or "") == factor
        and bool(item.get("changed_posterior"))
    }
    unknown = sorted(days - set(G15_DATES))
    if unknown:
        raise CounterfactualLessonGateError(
            f"attribution:{factor}: non-canonical support days {', '.join(unknown)}"
        )
    return sorted(days)


def _validate_counterfactual_proposals(attribution: Mapping[str, Any]) -> None:
    factors = [str(value) for value in attribution.get("factors") or []]
    if factors != list(FACTORS):
        raise CounterfactualLessonGateError(
            "attribution factor order differs from the six canonical factors"
        )
    proposals = [dict(row) for row in attribution.get("lesson_proposals") or []]
    seen: set[str] = set()
    for proposal in proposals:
        factor = str(proposal.get("factor") or "")
        identifier = str(proposal.get("id") or "")
        if factor not in FACTORS:
            raise CounterfactualLessonGateError(
                f"attribution proposal has unsupported factor {factor!r}"
            )
        if identifier != f"g15_counterfactual.{factor}":
            raise CounterfactualLessonGateError(
                f"attribution:{factor}: non-canonical proposal id"
            )
        if identifier in seen:
            raise CounterfactualLessonGateError(
                f"attribution:{factor}: duplicate proposal"
            )
        seen.add(identifier)
        if proposal.get("status") != "UNSCORED_CANDIDATE":
            raise CounterfactualLessonGateError(
                f"attribution:{factor}: proposal must remain unscored"
            )
        if proposal.get("authority") != "LESSON_PROPOSAL_ONLY":
            raise CounterfactualLessonGateError(
                f"attribution:{factor}: proposal authority mismatch"
            )
        if proposal.get("may_update_ng_brain") is not False:
            raise CounterfactualLessonGateError(
                f"attribution:{factor}: brain mutation must remain false"
            )
        expected_days = _expected_support_days(attribution, factor)
        observed_days = sorted(
            str(day) for day in proposal.get("supporting_g15_days") or []
        )
        if observed_days != expected_days:
            raise CounterfactualLessonGateError(
                f"attribution:{factor}: support days differ from counterfactual rows"
            )
        overall = dict((attribution.get("overall") or {}).get(factor) or {})
        if int(proposal.get("changed_states") or 0) != int(
            overall.get("changed_states") or 0
        ):
            raise CounterfactualLessonGateError(
                f"attribution:{factor}: changed-state count mismatch"
            )
    expected_ids = {
        f"g15_counterfactual.{factor}"
        for factor in FACTORS
        if _expected_support_days(attribution, factor)
    }
    if seen != expected_ids:
        raise CounterfactualLessonGateError(
            "attribution proposal set differs from factors that changed the posterior"
        )


def derive_proposals(
    attribution: Mapping[str, Any], audit: Mapping[str, Any]
) -> dict[str, Any]:
    """Build the canonical unscored proposal artifact from locked factor rows."""
    validate_daily_audit(audit)
    _validate_counterfactual_proposals(attribution)
    rows: list[dict[str, Any]] = []
    source_by_factor = {
        str(row.get("factor") or ""): dict(row)
        for row in attribution.get("lesson_proposals") or []
    }
    for factor in FACTORS:
        source = source_by_factor.get(factor)
        if source is None:
            continue
        overall = dict((attribution.get("overall") or {}).get(factor) or {})
        rows.append(
            {
                "id": f"g15_counterfactual.{factor}",
                "status": "UNSCORED_CANDIDATE",
                "authority": "LESSON_PROPOSAL_ONLY",
                "may_update_ng_brain": False,
                "mechanism": factor,
                "factor": factor,
                "supporting_g15_days": list(source["supporting_g15_days"]),
                "counterfactual_changed_states": int(
                    overall.get("changed_states") or 0
                ),
                "counterfactual_available_states": int(
                    overall.get("available_states") or 0
                ),
                "counterfactual_absolute_direction_effect_sum": overall.get(
                    "absolute_direction_effect_sum"
                ),
                "counterfactual_posterior_l1_effect_sum": overall.get(
                    "posterior_l1_effect_sum"
                ),
                "source_counterfactual_fingerprint": attribution.get("fingerprint"),
                "scope": (
                    "Outcome-blind full-minus-neutral model decomposition; G15 score "
                    "belongs to the complete refined path, not isolated factor causality."
                ),
                "may_select_support_after_scoring": False,
            }
        )
    result = {
        "schema": PROPOSAL_SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": "LESSON_PROPOSAL_ONLY",
        "execution_authority": False,
        "may_update_ng_brain": False,
        "actual_outcomes_used": False,
        "support_selected_before_scoring": True,
        "source_audit_fingerprint": audit.get("audit_fingerprint"),
        "source_counterfactual_fingerprint": attribution.get("fingerprint"),
        "proposal_count": len(rows),
        "proposals": rows,
    }
    result["proposal_fingerprint"] = _fingerprint(result)
    validate_unscored_proposals(
        result, audit_fingerprint=str(audit.get("audit_fingerprint") or "")
    )
    return result


def _bind_counterfactual_lineage(
    adjudication: Mapping[str, Any],
    attribution_fingerprint: Any,
    proposal_fingerprint: Any,
) -> dict[str, Any]:
    bound = copy.deepcopy(dict(adjudication))
    bound.pop("artifact_fingerprint", None)
    bound.setdefault("source", {})[
        "counterfactual_fingerprint"
    ] = attribution_fingerprint
    bound["source"][
        "counterfactual_proposal_fingerprint"
    ] = proposal_fingerprint
    registry = bound.setdefault("g16_shadow_registry", {})
    registry.pop("registry_fingerprint", None)
    registry["source_counterfactual_fingerprint"] = attribution_fingerprint
    registry["source_counterfactual_proposal_fingerprint"] = proposal_fingerprint
    for candidate in registry.get("candidates") or []:
        candidate["source_counterfactual_fingerprint"] = attribution_fingerprint
        candidate[
            "source_counterfactual_proposal_fingerprint"
        ] = proposal_fingerprint
    registry["registry_fingerprint"] = _fingerprint(registry)
    bound["artifact_fingerprint"] = _fingerprint(bound)
    validate_adjudication(bound)
    return bound


def _build_gate(
    replay: Mapping[str, Any],
    anchor: Mapping[str, Any],
    refine_stream: Mapping[str, Any],
    attribution: Mapping[str, Any],
    audit: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (replay, anchor, refine_stream, attribution, audit, comparison)
    )
    try:
        validate_counterfactual_report(
            attribution,
            replay=replay,
            anchor=anchor,
            refine_stream=refine_stream,
        )
        validate_daily_audit(audit)
        validate_comparison(comparison)
    except Exception as error:
        raise CounterfactualLessonGateError(str(error)) from error
    if attribution.get("actual_outcomes_used") is not False:
        raise CounterfactualLessonGateError(
            "counterfactual attribution must remain outcome-blind"
        )
    if comparison.get("actual_outcomes_used") is not True:
        raise CounterfactualLessonGateError(
            "G15 comparison must disclose fixed outcome use"
        )
    if (comparison.get("lesson_gate") or {}).get("may_update_ng_brain") is not False:
        raise CounterfactualLessonGateError(
            "comparison lesson gate cannot update ng_brain"
        )

    proposals = derive_proposals(attribution, audit)
    try:
        adjudication = build_adjudication(audit, proposals, comparison)
        adjudication = _bind_counterfactual_lineage(
            adjudication,
            attribution.get("fingerprint"),
            proposals.get("proposal_fingerprint"),
        )
    except Exception as error:
        raise CounterfactualLessonGateError(str(error)) from error

    proposal_ids = {str(row["id"]) for row in proposals["proposals"]}
    adjudicated_ids = {
        str(row.get("id") or "") for row in adjudication.get("adjudications") or []
    }
    if adjudicated_ids != proposal_ids:
        raise CounterfactualLessonGateError(
            "adjudication did not cover the exact counterfactual proposal set"
        )
    registry = dict(adjudication.get("g16_shadow_registry") or {})
    candidate_ids = {
        str(row.get("proposal_id") or "") for row in registry.get("candidates") or []
    }
    if not candidate_ids.issubset(proposal_ids):
        raise CounterfactualLessonGateError(
            "G16 registry contains a non-counterfactual candidate"
        )

    stand_down_days = sorted(
        set(str(day) for day in attribution.get("stand_down_days") or [])
        | {
            str(day.get("date") or "")
            for day in audit.get("days") or []
            if day.get("stand_down_reasons")
        }
    )
    result = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 15,
        "status": (
            "G15_COUNTERFACTUAL_LESSONS_ADJUDICATED_WITH_STAND_DOWNS"
            if stand_down_days
            else "G15_COUNTERFACTUAL_LESSONS_ADJUDICATED"
        ),
        "authority": AUTHORITY,
        "source": {
            "replay_fingerprint": attribution.get("replay_fingerprint"),
            "anchor_fingerprint": attribution.get("anchor_fingerprint"),
            "refine_stream_fingerprint": attribution.get(
                "refine_stream_fingerprint"
            ),
            "counterfactual_fingerprint": attribution.get("fingerprint"),
            "audit_fingerprint": audit.get("audit_fingerprint"),
            "comparison_fingerprint": comparison.get("artifact_fingerprint"),
            "blind_score_fingerprint": comparison.get("blind_score_fingerprint"),
            "refined_score_fingerprint": comparison.get(
                "refined_score_fingerprint"
            ),
            "proposal_fingerprint": proposals.get("proposal_fingerprint"),
            "adjudication_fingerprint": adjudication.get("artifact_fingerprint"),
            "registry_fingerprint": registry.get("registry_fingerprint"),
        },
        "factor_count": len(FACTORS),
        "proposal_count": len(proposal_ids),
        "adjudicated_count": len(adjudicated_ids),
        "g16_shadow_candidate_count": len(candidate_ids),
        "stand_down_days": stand_down_days,
        "derived_proposals": proposals,
        "adjudication": adjudication,
        "method": {
            "proposal_selection": (
                "Derived before scoring from deterministic G15 full-minus-neutral "
                "counterfactual rows only."
            ),
            "score_attribution": (
                "G15 outcome scores evaluate the full blind/refined paths. Factor "
                "eligibility remains an association, not isolated causal proof."
            ),
            "g16_registration": (
                "Only G15-supported candidates enter the pre-cutoff G16 SHADOW registry."
            ),
        },
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
        "next_permitted_stage": "G16_PRE_CUTOFF_SHADOW_REGISTRATION",
    }
    result["fingerprint"] = _fingerprint(result)
    if (replay, anchor, refine_stream, attribution, audit, comparison) != originals:
        raise CounterfactualLessonGateError("gate mutated an input artifact")
    return result


def build_gate(
    replay: Mapping[str, Any],
    anchor: Mapping[str, Any],
    refine_stream: Mapping[str, Any],
    attribution: Mapping[str, Any],
    audit: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> dict[str, Any]:
    result = _build_gate(
        replay, anchor, refine_stream, attribution, audit, comparison
    )
    validate_gate(
        result,
        replay=replay,
        anchor=anchor,
        refine_stream=refine_stream,
        attribution=attribution,
        audit=audit,
        comparison=comparison,
    )
    return result


def validate_gate(
    result: Mapping[str, Any],
    *,
    replay: Mapping[str, Any],
    anchor: Mapping[str, Any],
    refine_stream: Mapping[str, Any],
    attribution: Mapping[str, Any],
    audit: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> None:
    candidate = copy.deepcopy(dict(result))
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != SCHEMA or candidate.get("authority") != AUTHORITY:
        raise CounterfactualLessonGateError("gate schema/authority mismatch")
    if observed != _fingerprint(candidate):
        raise CounterfactualLessonGateError("gate fingerprint mismatch")
    for field in (
        "actual_g16_outcomes_used",
        "random_shuffle_used",
        "may_change_blind_prior",
        "may_change_posterior",
        "may_select_lessons_from_g15_scores",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if candidate.get(field) is not False:
            raise CounterfactualLessonGateError(f"gate must keep {field}=false")
    if candidate.get("actual_g15_outcomes_used") is not True:
        raise CounterfactualLessonGateError("gate must disclose G15 outcome use")
    if (
        candidate.get("one_signal_authority_preserved") is not True
        or candidate.get("blind_forecasts_immutable") is not True
    ):
        raise CounterfactualLessonGateError(
            "gate must preserve one authority and blind immutability"
        )
    if (
        candidate.get("cme_event_contracts_mode") != "SHADOW"
        or candidate.get("brokerage_contract") != "tastytrade_not_ibkr"
    ):
        raise CounterfactualLessonGateError("gate authority contract changed")
    validate_unscored_proposals(
        candidate.get("derived_proposals") or {},
        audit_fingerprint=str(audit.get("audit_fingerprint") or ""),
    )
    validate_adjudication(candidate.get("adjudication") or {})
    rebuilt = _build_gate(
        replay, anchor, refine_stream, attribution, audit, comparison
    )
    rebuilt.pop("fingerprint", None)
    if candidate != rebuilt:
        raise CounterfactualLessonGateError(
            "gate differs from deterministic reconstruction"
        )


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CounterfactualLessonGateError(
            f"artifact must be a JSON object: {path}"
        )
    return value


def selftest() -> int:
    import ng_g15_counterfactual_attribution as attribution_module
    import ng_g15_lesson_adjudication as adjudication_module
    from ng_rt_refiner import refine_feature_state

    anchor = attribution_module._fixture_anchor()
    states = [
        attribution_module._fixture_state(day, index + 1)
        for index, day in enumerate(G15_DATES)
    ]
    refine_stream = {
        "schema": "ng_rt_refine_stream.v1",
        "market": "NG",
        "group": 15,
        "authority": "REFINE_POSTERIOR_STREAM_ONLY",
        "execution_authority": False,
        "anchor_fingerprint": anchor["anchor_fingerprint"],
        "n_outputs": len(states),
        "outputs": [refine_feature_state(state, anchor) for state in states],
    }
    replay = {
        "streams": [{"states": states}],
        "fingerprint": attribution_module._fingerprint(states),
    }
    attribution = attribution_module.build_report(replay, anchor, refine_stream)
    audit, _, comparison = adjudication_module._fixture()
    result = build_gate(
        replay, anchor, refine_stream, attribution, audit, comparison
    )
    assert result["factor_count"] == 6
    assert result["proposal_count"] == 6
    assert result["actual_g16_outcomes_used"] is False
    assert result["may_update_ng_brain"] is False
    print("[ng_g15_counterfactual_lesson_gate] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bind exact G15 counterfactual factors to scored lesson adjudication"
    )
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--anchor", type=Path)
    parser.add_argument("--refine-stream", type=Path)
    parser.add_argument("--attribution", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--comparison", type=Path)
    parser.add_argument("--proposals-out", type=Path)
    parser.add_argument("--adjudication-out", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    required = (
        args.replay,
        args.anchor,
        args.refine_stream,
        args.attribution,
        args.audit,
        args.comparison,
        args.proposals_out,
        args.adjudication_out,
        args.out,
    )
    if any(value is None for value in required):
        parser.error(
            "--replay, --anchor, --refine-stream, --attribution, --audit, "
            "--comparison, --proposals-out, --adjudication-out, and --out are required"
        )
    result = build_gate(
        _load(args.replay),
        _load(args.anchor),
        _load(args.refine_stream),
        _load(args.attribution),
        _load(args.audit),
        _load(args.comparison),
    )
    _atomic_json(args.proposals_out, result["derived_proposals"])
    _atomic_json(args.adjudication_out, result["adjudication"])
    _atomic_json(args.out, result)
    print(
        "[ng_g15_counterfactual_lesson_gate] "
        f"{result['status']} proposals={result['proposal_count']} "
        f"g16_candidates={result['g16_shadow_candidate_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
