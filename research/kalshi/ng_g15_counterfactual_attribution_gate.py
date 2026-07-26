#!/usr/bin/env python3
"""Recursively authorize exact G15 six-factor counterfactual attribution.

The gate binds the exact replay completion, deterministic G15 refinement pipeline,
refinement authorization, and outcome-blind six-factor attribution report. It
reconstructs both upstream authorizations from their causal inputs, verifies every
state carries all six requested factor effects, and preserves lesson proposals as
non-writing candidates only.

It never reads outcomes, changes the blind forecast or posterior stream, updates
``ng_brain.json``, grants execution authority, authorizes G16, or starts options.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from ng_g15_counterfactual_attribution import (
    FACTORS,
    build_report as build_attribution_report,
    validate_report as validate_attribution_report,
)
from ng_g15_exact_refinement_gate import (
    build_authorization as build_refinement_authorization,
    validate_authorization as validate_refinement_authorization,
)

SCHEMA = "ng_g15_counterfactual_attribution_authorization.v1"
ATTRIBUTION_SCHEMA = "ng_g15_counterfactual_attribution.v1"
COMPLETION_SCHEMA = "ng_g15_exact_replay_completion.v1"
PIPELINE_SCHEMA = "ng_g15_pipeline.v1"
REFINEMENT_SCHEMA = "ng_g15_exact_refinement_authorization.v1"
READY = "G15_COUNTERFACTUAL_ATTRIBUTION_AUTHORIZED"
READY_WITH_STAND_DOWNS = "G15_COUNTERFACTUAL_ATTRIBUTION_AUTHORIZED_WITH_STAND_DOWNS"
ATTRIBUTION_READY = {"READY", "READY_WITH_STAND_DOWNS"}
REFINEMENT_READY = {"EXACT_G15_REFINEMENT_READY", "EXACT_G15_REFINEMENT_READY_WITH_STAND_DOWNS"}
G15_DATES = (
    "20260315", "20260316", "20260317", "20260318", "20260319", "20260320",
    "20260322", "20260323", "20260324", "20260325", "20260326", "20260327",
)


class CounterfactualAttributionAuthorizationError(ValueError):
    """Raised when six-factor attribution is not exact-replay reproducible."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CounterfactualAttributionAuthorizationError(
            f"artifact must be a JSON object: {path}"
        )
    return value


def _dependency_call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except (TypeError, ValueError) as error:
        raise CounterfactualAttributionAuthorizationError(str(error)) from error


def _verify_embedded_fingerprint(
    value: Mapping[str, Any], field: str, *, label: str
) -> None:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    if not observed or observed != _fingerprint(payload):
        raise CounterfactualAttributionAuthorizationError(
            f"{label} fingerprint mismatch"
        )


def _validate_controls(value: Mapping[str, Any], *, label: str) -> None:
    false_fields = (
        "actual_outcomes_used",
        "random_shuffle_used",
        "may_change_blind_forecast",
        "may_change_blind_prior",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "g16_authorized",
        "options_lane_started",
    )
    for field in false_fields:
        if field in value and value.get(field) is not False:
            raise CounterfactualAttributionAuthorizationError(
                f"{label} must keep {field}=false"
            )
    if value.get("cme_event_contracts_mode", "SHADOW") != "SHADOW":
        raise CounterfactualAttributionAuthorizationError(
            f"{label} must keep CME event contracts SHADOW"
        )
    if value.get("brokerage_contract", "tastytrade_not_ibkr") != "tastytrade_not_ibkr":
        raise CounterfactualAttributionAuthorizationError(
            f"{label} must preserve tastytrade rather than IBKR"
        )


def _validate_attribution_shape(
    attribution: Mapping[str, Any], *, posterior_outputs: int
) -> dict[str, Any]:
    value = copy.deepcopy(dict(attribution))
    _verify_embedded_fingerprint(value, "fingerprint", label="attribution")
    if value.get("schema") != ATTRIBUTION_SCHEMA:
        raise CounterfactualAttributionAuthorizationError(
            "unexpected attribution schema"
        )
    if value.get("status") not in ATTRIBUTION_READY:
        raise CounterfactualAttributionAuthorizationError(
            "counterfactual attribution is not ready"
        )
    if value.get("authority") != "OUTCOME_BLIND_COUNTERFACTUAL_ATTRIBUTION_ONLY":
        raise CounterfactualAttributionAuthorizationError(
            "counterfactual attribution authority is invalid"
        )
    _validate_controls(value, label="attribution")
    if value.get("one_signal_authority_preserved") is not True:
        raise CounterfactualAttributionAuthorizationError(
            "attribution must preserve one signal authority"
        )
    if value.get("blind_forecast_immutable") is not True:
        raise CounterfactualAttributionAuthorizationError(
            "attribution must keep the blind forecast immutable"
        )
    if tuple(value.get("factors") or ()) != tuple(FACTORS):
        raise CounterfactualAttributionAuthorizationError(
            "attribution must contain the canonical six factors"
        )
    rows = [copy.deepcopy(dict(row)) for row in value.get("rows") or []]
    if int(value.get("n_states") or 0) != len(rows) or len(rows) != posterior_outputs:
        raise CounterfactualAttributionAuthorizationError(
            "attribution state count differs from exact posterior outputs"
        )
    if int(value.get("n_days") or 0) != len(G15_DATES):
        raise CounterfactualAttributionAuthorizationError(
            "attribution must cover all canonical G15 days"
        )
    observed_days = {str(row.get("session_day") or "") for row in rows}
    if observed_days != set(G15_DATES):
        raise CounterfactualAttributionAuthorizationError(
            "attribution rows lost canonical G15 coverage"
        )
    for row in rows:
        factors = [str(item.get("factor") or "") for item in row.get("factors") or []]
        if factors != list(FACTORS):
            raise CounterfactualAttributionAuthorizationError(
                "every causal state must quantify all six factors in canonical order"
            )
    overall = dict(value.get("overall") or {})
    per_day = dict(value.get("per_day") or {})
    if set(overall) != set(FACTORS) or set(per_day) != set(G15_DATES):
        raise CounterfactualAttributionAuthorizationError(
            "attribution summaries are incomplete"
        )
    for proposal in value.get("lesson_proposals") or []:
        if proposal.get("status") != "UNSCORED_CANDIDATE":
            raise CounterfactualAttributionAuthorizationError(
                "pre-score lesson proposals must remain UNSCORED_CANDIDATE"
            )
        if proposal.get("authority") != "LESSON_PROPOSAL_ONLY":
            raise CounterfactualAttributionAuthorizationError(
                "lesson proposal authority is invalid"
            )
        if proposal.get("may_update_ng_brain") is not False:
            raise CounterfactualAttributionAuthorizationError(
                "lesson proposals cannot update ng_brain.json"
            )
    return value


def build_authorization(
    *,
    completion: Mapping[str, Any],
    pipeline: Mapping[str, Any],
    refinement_authorization: Mapping[str, Any],
    attribution: Mapping[str, Any],
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (completion, pipeline, refinement_authorization, attribution)
    )
    completion_value = copy.deepcopy(dict(completion))
    pipeline_value = copy.deepcopy(dict(pipeline))
    refinement_value = copy.deepcopy(dict(refinement_authorization))

    if completion_value.get("schema") != COMPLETION_SCHEMA:
        raise CounterfactualAttributionAuthorizationError(
            "unexpected exact replay completion schema"
        )
    if pipeline_value.get("schema") != PIPELINE_SCHEMA:
        raise CounterfactualAttributionAuthorizationError(
            "unexpected G15 pipeline schema"
        )
    if refinement_value.get("schema") != REFINEMENT_SCHEMA:
        raise CounterfactualAttributionAuthorizationError(
            "unexpected exact refinement authorization schema"
        )
    if refinement_value.get("status") not in REFINEMENT_READY:
        raise CounterfactualAttributionAuthorizationError(
            "exact refinement authorization is not ready"
        )

    rebuilt_refinement = _dependency_call(
        build_refinement_authorization,
        completion=completion_value,
        pipeline=pipeline_value,
        blind_forecast_bytes=None,
    )
    _dependency_call(
        validate_refinement_authorization,
        refinement_value,
        completion=completion_value,
        pipeline=pipeline_value,
    )
    if refinement_value != rebuilt_refinement:
        raise CounterfactualAttributionAuthorizationError(
            "refinement authorization differs from deterministic reconstruction"
        )

    attribution_value = _validate_attribution_shape(
        attribution,
        posterior_outputs=int(refinement_value.get("posterior_outputs") or 0),
    )
    replay = copy.deepcopy(dict(pipeline_value.get("replay") or {}))
    anchor = copy.deepcopy(dict(pipeline_value.get("anchor") or {}))
    refine_stream = copy.deepcopy(dict(pipeline_value.get("refine_stream") or {}))
    _dependency_call(
        validate_attribution_report,
        attribution_value,
        replay=replay,
        anchor=anchor,
        refine_stream=refine_stream,
    )
    rebuilt_attribution = _dependency_call(
        build_attribution_report,
        replay,
        anchor,
        refine_stream,
    )
    if attribution_value != rebuilt_attribution:
        raise CounterfactualAttributionAuthorizationError(
            "counterfactual attribution differs from deterministic reconstruction"
        )

    _validate_controls(refinement_value, label="refinement authorization")
    stand_downs = bool(attribution_value.get("stand_down_days"))
    result = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 15,
        "status": READY_WITH_STAND_DOWNS if stand_downs else READY,
        "authority": "G15_COUNTERFACTUAL_ATTRIBUTION_AUTHORIZATION_ONLY",
        "exact_replay_completion_fingerprint": completion_value.get(
            "completion_fingerprint"
        ),
        "pipeline_fingerprint": pipeline_value.get("pipeline_fingerprint"),
        "refinement_authorization_fingerprint": refinement_value.get(
            "authorization_fingerprint"
        ),
        "attribution_fingerprint": attribution_value.get("fingerprint"),
        "replay_fingerprint": refinement_value.get("replay_fingerprint"),
        "anchor_fingerprint": refinement_value.get("anchor_fingerprint"),
        "refine_stream_fingerprint": refinement_value.get(
            "refine_stream_fingerprint"
        ),
        "n_states": attribution_value.get("n_states"),
        "n_days": attribution_value.get("n_days"),
        "factors": list(FACTORS),
        "factor_summary_fingerprint": _fingerprint(
            attribution_value.get("overall") or {}
        ),
        "per_day_fingerprint": _fingerprint(
            attribution_value.get("per_day") or {}
        ),
        "rows_fingerprint": _fingerprint(attribution_value.get("rows") or []),
        "lesson_proposals_fingerprint": _fingerprint(
            attribution_value.get("lesson_proposals") or []
        ),
        "lesson_proposal_count": len(
            attribution_value.get("lesson_proposals") or []
        ),
        "stand_down_days": list(attribution_value.get("stand_down_days") or []),
        "all_six_factors_quantified": True,
        "lesson_proposals_brain_write_forbidden": True,
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_blind_prior": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "g16_authorized": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": (
            "LOCK_G15_REFINED_FORECAST_AND_SCORE_BLIND_REFINED_SEPARATELY"
        ),
        "note": (
            "All six requested G15 evidence families were reproduced from the exact "
            "causal replay and quantified outcome-blind. Lesson proposals remain "
            "non-writing candidates until separate locked scoring and adjudication."
        ),
    }
    result["authorization_fingerprint"] = _fingerprint(result)
    if (
        completion,
        pipeline,
        refinement_authorization,
        attribution,
    ) != originals:
        raise CounterfactualAttributionAuthorizationError(
            "attribution authorization mutated an input artifact"
        )
    validate_authorization(result)
    return result


def validate_authorization(
    authorization: Mapping[str, Any],
    *,
    completion: Mapping[str, Any] | None = None,
    pipeline: Mapping[str, Any] | None = None,
    refinement_authorization: Mapping[str, Any] | None = None,
    attribution: Mapping[str, Any] | None = None,
) -> None:
    value = copy.deepcopy(dict(authorization))
    _verify_embedded_fingerprint(
        value, "authorization_fingerprint", label="attribution authorization"
    )
    if value.get("schema") != SCHEMA or value.get("status") not in {
        READY,
        READY_WITH_STAND_DOWNS,
    }:
        raise CounterfactualAttributionAuthorizationError(
            "unexpected or non-ready attribution authorization"
        )
    if value.get("authority") != "G15_COUNTERFACTUAL_ATTRIBUTION_AUTHORIZATION_ONLY":
        raise CounterfactualAttributionAuthorizationError(
            "attribution authorization authority is invalid"
        )
    _validate_controls(value, label="attribution authorization")
    if (
        value.get("one_signal_authority_preserved") is not True
        or value.get("blind_forecasts_immutable") is not True
        or value.get("all_six_factors_quantified") is not True
        or value.get("lesson_proposals_brain_write_forbidden") is not True
    ):
        raise CounterfactualAttributionAuthorizationError(
            "attribution authorization lost a permanent control"
        )
    if tuple(value.get("factors") or ()) != tuple(FACTORS):
        raise CounterfactualAttributionAuthorizationError(
            "attribution authorization lost the canonical factor set"
        )
    if int(value.get("n_days") or 0) != len(G15_DATES):
        raise CounterfactualAttributionAuthorizationError(
            "attribution authorization lost canonical G15 coverage"
        )
    supplied = (
        completion,
        pipeline,
        refinement_authorization,
        attribution,
    )
    if any(item is not None for item in supplied):
        if any(item is None for item in supplied):
            raise CounterfactualAttributionAuthorizationError(
                "all four upstream artifacts are required for recursive validation"
            )
        rebuilt = build_authorization(
            completion=completion,
            pipeline=pipeline,
            refinement_authorization=refinement_authorization,
            attribution=attribution,
        )
        if value != rebuilt:
            raise CounterfactualAttributionAuthorizationError(
                "attribution authorization differs from recursive reconstruction"
            )


def _synthetic_fixture() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    completion = {
        "schema": COMPLETION_SCHEMA,
        "completion_fingerprint": "c" * 64,
    }
    pipeline = {
        "schema": PIPELINE_SCHEMA,
        "pipeline_fingerprint": "p" * 64,
        "replay": {},
        "anchor": {},
        "refine_stream": {},
    }
    refinement = {
        "schema": REFINEMENT_SCHEMA,
        "status": "EXACT_G15_REFINEMENT_READY",
        "authorization_fingerprint": "r" * 64,
        "replay_fingerprint": "e" * 64,
        "anchor_fingerprint": "a" * 64,
        "refine_stream_fingerprint": "s" * 64,
        "posterior_outputs": len(G15_DATES),
        "actual_outcomes_used": False,
        "may_change_blind_prior": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "g16_authorized": False,
    }
    rows = [
        {
            "session_day": day,
            "factors": [{"factor": factor} for factor in FACTORS],
        }
        for day in G15_DATES
    ]
    attribution = {
        "schema": ATTRIBUTION_SCHEMA,
        "status": "READY",
        "authority": "OUTCOME_BLIND_COUNTERFACTUAL_ATTRIBUTION_ONLY",
        "n_states": len(rows),
        "n_days": len(G15_DATES),
        "factors": list(FACTORS),
        "rows": rows,
        "per_day": {day: {} for day in G15_DATES},
        "overall": {factor: {} for factor in FACTORS},
        "stand_down_days": [],
        "lesson_proposals": [
            {
                "id": "g15_counterfactual.signed_flow",
                "status": "UNSCORED_CANDIDATE",
                "authority": "LESSON_PROPOSAL_ONLY",
                "may_update_ng_brain": False,
            }
        ],
        "actual_outcomes_used": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecast_immutable": True,
        "may_change_blind_prior": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }
    attribution["fingerprint"] = _fingerprint(attribution)
    return completion, pipeline, refinement, attribution


def selftest() -> int:
    global build_refinement_authorization
    global validate_refinement_authorization
    global build_attribution_report
    global validate_attribution_report

    completion, pipeline, refinement, attribution = _synthetic_fixture()
    saved = (
        build_refinement_authorization,
        validate_refinement_authorization,
        build_attribution_report,
        validate_attribution_report,
    )
    build_refinement_authorization = lambda **kwargs: copy.deepcopy(refinement)
    validate_refinement_authorization = lambda *args, **kwargs: None
    build_attribution_report = lambda *args, **kwargs: copy.deepcopy(attribution)
    validate_attribution_report = lambda *args, **kwargs: None
    try:
        result = build_authorization(
            completion=completion,
            pipeline=pipeline,
            refinement_authorization=refinement,
            attribution=attribution,
        )
        assert result["status"] == READY
        assert result["all_six_factors_quantified"] is True
        assert result["lesson_proposals_brain_write_forbidden"] is True
        validate_authorization(result)
        tampered = copy.deepcopy(result)
        tampered["may_update_ng_brain"] = True
        tampered.pop("authorization_fingerprint", None)
        tampered["authorization_fingerprint"] = _fingerprint(tampered)
        try:
            validate_authorization(tampered)
        except CounterfactualAttributionAuthorizationError:
            pass
        else:
            raise AssertionError("brain-write escalation was not rejected")
    finally:
        (
            build_refinement_authorization,
            validate_refinement_authorization,
            build_attribution_report,
            validate_attribution_report,
        ) = saved
    print("[ng_g15_counterfactual_attribution_gate] selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--completion", type=Path)
    parser.add_argument("--pipeline", type=Path)
    parser.add_argument("--refinement-authorization", type=Path)
    parser.add_argument("--attribution", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    required = (
        args.completion,
        args.pipeline,
        args.refinement_authorization,
        args.attribution,
        args.out,
    )
    if any(value is None for value in required):
        parser.error(
            "--completion, --pipeline, --refinement-authorization, --attribution, and --out are required"
        )
    result = build_authorization(
        completion=_load(args.completion),
        pipeline=_load(args.pipeline),
        refinement_authorization=_load(args.refinement_authorization),
        attribution=_load(args.attribution),
    )
    _atomic_json(args.out, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "states": result["n_states"],
                "factors": result["factors"],
                "lesson_proposals": result["lesson_proposal_count"],
                "fingerprint": result["authorization_fingerprint"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
