#!/usr/bin/env python3
"""Bind G15 publication and the G16 pre-cutoff plan to exact counterfactual lessons.

The legacy G15 publication and G16 SHADOW plan contracts validate their own local
provenance, but they predate ``ng_g15_counterfactual_lesson_gate``. This wrapper
makes the counterfactual gate's exact fingerprint and bound adjudication mandatory
for both artifacts. It prevents an older, manually curated adjudication or registry
from being substituted between scored G15 publication and pre-cutoff G16 planning.

The wrapper is audit-only. It does not rebuild forecasts, read G16 outcomes, mutate
``knowledge/ng_brain.json``, or grant execution authority.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from ng_g15_counterfactual_lesson_gate import validate_gate as validate_counterfactual_gate
from ng_g15_exact_publication_gate import validate_completion as validate_g15_publication
from ng_g16_shadow_gate import validate_shadow_plan

SCHEMA = "ng_g15_g16_counterfactual_lineage_gate.v1"
AUTHORITY = "G15_PUBLICATION_G16_PLAN_COUNTERFACTUAL_LINEAGE_ONLY"
READY = "G15_PUBLICATION_G16_PLAN_COUNTERFACTUAL_LINEAGE_BOUND"
READY_WITH_STAND_DOWNS = (
    "G15_PUBLICATION_G16_PLAN_COUNTERFACTUAL_LINEAGE_BOUND_WITH_STAND_DOWNS"
)
COUNTERFACTUAL_SCHEMA = "ng_g15_counterfactual_lesson_gate.v1"
PUBLICATION_SCHEMA = "ng_g15_exact_publication_completion.v1"
PLAN_SCHEMA = "ng_g16_shadow_refinement_plan.v1"


class CounterfactualLineageError(ValueError):
    """Raised when G15 publication or G16 planning bypasses exact lesson lineage."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _verify_fingerprint(
    value: Mapping[str, Any], field: str, *, label: str
) -> dict[str, Any]:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    if not isinstance(observed, str) or observed != _fingerprint(payload):
        raise CounterfactualLineageError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _candidate_ids(registry: Mapping[str, Any]) -> list[str]:
    identifiers = sorted(
        str(row.get("proposal_id") or "") for row in registry.get("candidates") or []
    )
    if any(not identifier for identifier in identifiers):
        raise CounterfactualLineageError("counterfactual registry has an empty candidate id")
    if len(identifiers) != len(set(identifiers)):
        raise CounterfactualLineageError("counterfactual registry has duplicate candidate ids")
    if int(registry.get("candidate_count") or 0) != len(identifiers):
        raise CounterfactualLineageError("counterfactual registry candidate_count mismatch")
    return identifiers


def _build_lineage(
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
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (
            counterfactual_gate,
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
        validate_counterfactual_gate(
            counterfactual_gate,
            replay=replay,
            anchor=anchor,
            refine_stream=refine_stream,
            attribution=attribution,
            audit=audit,
            comparison=comparison,
        )
        validate_g15_publication(g15_publication)
        validate_shadow_plan(
            g16_plan,
            blind_forecast=g16_blind_forecast,
            blind_safe_state=g16_blind_safe_state,
            registry_source=counterfactual_gate.get("adjudication") or {},
        )
    except Exception as error:
        raise CounterfactualLineageError(str(error)) from error

    counterfactual = _verify_fingerprint(
        counterfactual_gate, "fingerprint", label="counterfactual lesson gate"
    )
    if (
        counterfactual.get("schema") != COUNTERFACTUAL_SCHEMA
        or counterfactual.get("authority")
        != "G15_COUNTERFACTUAL_LESSON_ADJUDICATION_ONLY"
    ):
        raise CounterfactualLineageError("counterfactual lesson gate schema/authority mismatch")
    if counterfactual.get("actual_g15_outcomes_used") is not True:
        raise CounterfactualLineageError("counterfactual gate must disclose G15 outcome use")
    if counterfactual.get("actual_g16_outcomes_used") is not False:
        raise CounterfactualLineageError("counterfactual gate cannot use G16 outcomes")

    publication = copy.deepcopy(dict(g15_publication))
    plan = copy.deepcopy(dict(g16_plan))
    if publication.get("schema") != PUBLICATION_SCHEMA:
        raise CounterfactualLineageError("G15 publication schema mismatch")
    if plan.get("schema") != PLAN_SCHEMA:
        raise CounterfactualLineageError("G16 shadow plan schema mismatch")

    source = dict(counterfactual.get("source") or {})
    adjudication = dict(counterfactual.get("adjudication") or {})
    adjudication_fp = str(adjudication.get("artifact_fingerprint") or "")
    registry = dict(adjudication.get("g16_shadow_registry") or {})
    registry_fp = str(registry.get("registry_fingerprint") or "")
    counterfactual_fp = str(counterfactual.get("fingerprint") or "")
    if not adjudication_fp or adjudication_fp != source.get("adjudication_fingerprint"):
        raise CounterfactualLineageError(
            "counterfactual gate source does not bind its exact adjudication"
        )
    if not registry_fp or registry_fp != source.get("registry_fingerprint"):
        raise CounterfactualLineageError(
            "counterfactual gate source does not bind its exact G16 registry"
        )

    publication_links = {
        "anchor_fingerprint": source.get("anchor_fingerprint"),
        "refine_stream_fingerprint": source.get("refine_stream_fingerprint"),
        "daily_audit_fingerprint": source.get("audit_fingerprint"),
        "lesson_proposal_fingerprint": source.get("proposal_fingerprint"),
        "comparison_fingerprint": source.get("comparison_fingerprint"),
        "blind_score_fingerprint": source.get("blind_score_fingerprint"),
        "refined_score_fingerprint": source.get("refined_score_fingerprint"),
        "lesson_adjudication_fingerprint": adjudication_fp,
    }
    for field, expected in publication_links.items():
        if publication.get(field) != expected:
            raise CounterfactualLineageError(
                f"G15 publication {field} bypasses the counterfactual lesson gate"
            )

    publication_registry = dict(publication.get("g16_shadow_registry") or {})
    if publication_registry.get("registry_fingerprint") != registry_fp:
        raise CounterfactualLineageError(
            "G15 publication references a different G16 lesson registry"
        )
    if publication_registry.get("g16_outcome_access_authorized") is not False:
        raise CounterfactualLineageError("G15 publication cannot authorize G16 outcomes")

    if plan.get("lesson_adjudication_fingerprint") != adjudication_fp:
        raise CounterfactualLineageError(
            "G16 plan references an adjudication outside the counterfactual gate"
        )
    if plan.get("lesson_registry_fingerprint") != registry_fp:
        raise CounterfactualLineageError(
            "G16 plan references a registry outside the counterfactual gate"
        )

    candidate_ids = _candidate_ids(registry)
    if list(plan.get("candidate_ids") or []) != candidate_ids:
        raise CounterfactualLineageError(
            "G16 plan candidate set differs from counterfactual G15 candidates"
        )
    if list(publication_registry.get("candidate_ids") or []) != candidate_ids:
        raise CounterfactualLineageError(
            "G15 publication candidate set differs from counterfactual G15 candidates"
        )
    if int(publication_registry.get("candidate_count") or 0) != len(candidate_ids):
        raise CounterfactualLineageError("G15 publication candidate_count mismatch")

    candidate_evidence = {
        str(row.get("proposal_id") or ""): str(row.get("g15_evidence_fingerprint") or "")
        for row in registry.get("candidates") or []
    }
    if any(not value for value in candidate_evidence.values()):
        raise CounterfactualLineageError(
            "every counterfactual G16 candidate needs a G15 evidence fingerprint"
        )
    for day, row in (plan.get("days") or {}).items():
        if dict(row).get("candidate_evidence_fingerprints") != candidate_evidence:
            raise CounterfactualLineageError(
                f"G16 plan {day} candidate evidence differs from the counterfactual registry"
            )

    stand_down_days = sorted(
        set(str(day) for day in counterfactual.get("stand_down_days") or [])
        | set(str(day) for day in publication.get("stand_down_days") or [])
    )
    result = {
        "schema": SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": READY_WITH_STAND_DOWNS if stand_down_days else READY,
        "authority": AUTHORITY,
        "counterfactual_lesson_gate_fingerprint": counterfactual_fp,
        "counterfactual_attribution_fingerprint": source.get(
            "counterfactual_fingerprint"
        ),
        "counterfactual_proposal_fingerprint": source.get("proposal_fingerprint"),
        "g15_publication_fingerprint": publication.get("completion_fingerprint"),
        "g15_adjudication_fingerprint": adjudication_fp,
        "g16_registry_fingerprint": registry_fp,
        "g16_plan_fingerprint": plan.get("plan_fingerprint"),
        "g16_blind_forecast_fingerprint": plan.get("blind_forecast_fingerprint"),
        "g16_blind_safe_state_fingerprint": plan.get(
            "blind_safe_state_fingerprint"
        ),
        "candidate_count": len(candidate_ids),
        "candidate_ids": candidate_ids,
        "candidate_evidence_fingerprints": candidate_evidence,
        "stand_down_days": stand_down_days,
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
        "next_permitted_stage": (
            "G16_EXACT_PREPARED_REPLAY_AND_PRE_CUTOFF_CAUSAL_AUTHORIZATION"
        ),
        "note": (
            "G15 publication and every G16 pre-cutoff candidate are bound to the "
            "same deterministic full-minus-neutral counterfactual lesson gate. "
            "G16 outcomes, execution, options, and ng_brain mutation remain forbidden."
        ),
    }
    result["fingerprint"] = _fingerprint(result)

    if (
        counterfactual_gate,
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
        raise CounterfactualLineageError("lineage validation mutated a source artifact")
    return result


def build_lineage(
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
) -> dict[str, Any]:
    result = _build_lineage(
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
    validate_lineage(
        result,
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
    return result


def validate_lineage(
    result: Mapping[str, Any],
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
    candidate = _verify_fingerprint(result, "fingerprint", label="lineage gate")
    if candidate.get("schema") != SCHEMA or candidate.get("authority") != AUTHORITY:
        raise CounterfactualLineageError("lineage gate schema/authority mismatch")
    if candidate.get("status") not in {READY, READY_WITH_STAND_DOWNS}:
        raise CounterfactualLineageError("lineage gate is not ready")
    for field in (
        "actual_g16_outcomes_used",
        "g16_scoring_authorized",
        "random_shuffle_used",
        "may_change_g16_blind_prior",
        "may_change_posterior",
        "may_select_lessons_from_g16_outcomes",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if candidate.get(field) is not False:
            raise CounterfactualLineageError(f"lineage gate must keep {field}=false")
    if candidate.get("actual_g15_outcomes_used") is not True:
        raise CounterfactualLineageError("lineage gate must disclose G15 outcome use")
    if (
        candidate.get("one_signal_authority_preserved") is not True
        or candidate.get("blind_forecasts_immutable") is not True
    ):
        raise CounterfactualLineageError(
            "lineage gate must preserve one authority and blind immutability"
        )
    if (
        candidate.get("cme_event_contracts_mode") != "SHADOW"
        or candidate.get("brokerage_contract") != "tastytrade_not_ibkr"
    ):
        raise CounterfactualLineageError("lineage authority contract changed")

    rebuilt = _build_lineage(
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
    rebuilt.pop("fingerprint", None)
    candidate.pop("fingerprint", None)
    if candidate != rebuilt:
        raise CounterfactualLineageError(
            "lineage gate differs from deterministic reconstruction"
        )


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CounterfactualLineageError(f"artifact must be a JSON object: {path}")
    return value


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _fixture() -> dict[str, Any]:
    import tempfile

    import ng_g15_counterfactual_attribution as attribution_module
    import ng_g15_counterfactual_lesson_gate as counterfactual_module
    import ng_g15_exact_publication_gate as publication_module
    import ng_g15_lesson_adjudication as adjudication_module
    import ng_g16_shadow_gate as shadow_module
    from ng_historical_manifest import G15_DATES
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
    counterfactual_gate = counterfactual_module.build_gate(
        replay, anchor, refine_stream, attribution, audit, comparison
    )

    with tempfile.TemporaryDirectory() as directory:
        pub_fixture = publication_module._fixture(Path(directory))
        publication = publication_module.build_completion(
            authorization=pub_fixture["authorization"],
            blind=pub_fixture["blind"],
            refined=pub_fixture["refined"],
            actual=pub_fixture["actual"],
            blind_score=pub_fixture["blind_score"],
            refined_score=pub_fixture["refined_score"],
            comparison=pub_fixture["comparison"],
            adjudication=pub_fixture["adjudication"],
            blind_rt=pub_fixture["blind_rt"],
            refined_rt=pub_fixture["refined_rt"],
            blind_bytes=pub_fixture["blind_bytes"],
            refined_bytes=pub_fixture["refined_bytes"],
            blind_png=pub_fixture["blind_png"],
            refined_png=pub_fixture["refined_png"],
        )
    source = counterfactual_gate["source"]
    registry = counterfactual_gate["adjudication"]["g16_shadow_registry"]
    publication.update(
        {
            "anchor_fingerprint": source["anchor_fingerprint"],
            "refine_stream_fingerprint": source["refine_stream_fingerprint"],
            "daily_audit_fingerprint": source["audit_fingerprint"],
            "lesson_proposal_fingerprint": source["proposal_fingerprint"],
            "comparison_fingerprint": source["comparison_fingerprint"],
            "blind_score_fingerprint": source["blind_score_fingerprint"],
            "refined_score_fingerprint": source["refined_score_fingerprint"],
            "lesson_adjudication_fingerprint": source["adjudication_fingerprint"],
            "g16_shadow_registry": {
                "registry_fingerprint": registry["registry_fingerprint"],
                "candidate_count": registry["candidate_count"],
                "candidate_ids": sorted(
                    row["proposal_id"] for row in registry["candidates"]
                ),
                "pre_cutoff_shadow_refinement_authorized": bool(
                    registry["candidates"]
                ),
                "g16_outcome_access_authorized": False,
                "may_change_g16_blind_prior": False,
                "may_update_ng_brain": False,
            },
        }
    )
    publication.pop("completion_fingerprint", None)
    publication["completion_fingerprint"] = publication_module._fingerprint(publication)
    publication_module.validate_completion(publication)

    g16_blind_forecast = shadow_module._fixture_forecast()
    g16_blind_safe_state = shadow_module._fixture_blind_state()
    g16_plan = shadow_module.build_shadow_plan(
        g16_blind_forecast,
        g16_blind_safe_state,
        counterfactual_gate["adjudication"],
    )
    return locals()


def selftest() -> int:
    fixture = _fixture()
    result = build_lineage(
        counterfactual_gate=fixture["counterfactual_gate"],
        g15_publication=fixture["publication"],
        g16_plan=fixture["g16_plan"],
        replay=fixture["replay"],
        anchor=fixture["anchor"],
        refine_stream=fixture["refine_stream"],
        attribution=fixture["attribution"],
        audit=fixture["audit"],
        comparison=fixture["comparison"],
        g16_blind_forecast=fixture["g16_blind_forecast"],
        g16_blind_safe_state=fixture["g16_blind_safe_state"],
    )
    assert result["candidate_count"] > 0
    assert result["actual_g16_outcomes_used"] is False
    assert result["may_update_ng_brain"] is False
    print("[ng_g15_g16_counterfactual_lineage_gate] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Bind exact G15 publication and the G16 pre-cutoff plan to the same "
            "counterfactual lesson gate"
        )
    )
    parser.add_argument("--counterfactual-gate", type=Path)
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
        args.counterfactual_gate,
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
    result = build_lineage(
        counterfactual_gate=_load(args.counterfactual_gate),
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
        "[ng_g15_g16_counterfactual_lineage_gate] "
        f"{result['status']} candidates={result['candidate_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
