#!/usr/bin/env python3
"""Require G15 counterfactual lesson lineage in the outcome-blind G16 curve gate.

The prepared-curve authorization proves that the refined G16 curve is reproduced
from the exact prepared NGK26 replay, immutable blind forecast, pre-cutoff plan,
and authorized posterior stream.  The counterfactual-causal authorization proves
that the same posterior chain uses the deterministic G15 full-minus-neutral lesson
set that was published and pre-registered before G16 outcome access.

This wrapper requires both contracts together.  It does not read G16 outcomes,
does not alter a blind artifact or posterior, cannot update ``ng_brain.json``,
keeps CME event contracts SHADOW, keeps tastytrade as the brokerage contract, and
leaves the options lane unstarted.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from ng_g16_counterfactual_causal_authorization import (
    AUTHORITY as COUNTERFACTUAL_AUTHORITY,
    G16CounterfactualCausalAuthorizationError,
    NEXT_STAGE as COUNTERFACTUAL_NEXT_STAGE,
    SCHEMA as COUNTERFACTUAL_SCHEMA,
    STATUS_READY as COUNTERFACTUAL_READY,
    STATUS_STAND_DOWNS as COUNTERFACTUAL_STAND_DOWNS,
    validate_authorization_artifact as validate_counterfactual_authorization,
)
from ng_g16_prepared_curve_authorization import (
    AUTHORITY as PREPARED_CURVE_AUTHORITY,
    G16PreparedCurveAuthorizationError,
    NEXT_STAGE as PREPARED_CURVE_NEXT_STAGE,
    SCHEMA as PREPARED_CURVE_SCHEMA,
    STATUS_READY as PREPARED_CURVE_READY,
    STATUS_STAND_DOWNS as PREPARED_CURVE_STAND_DOWNS,
    validate_curve_authorization,
)

SCHEMA = "ng_g16_counterfactual_curve_authorization.v1"
AUTHORITY = "EXACT_G15_COUNTERFACTUAL_LINEAGE_TO_G16_OUTCOME_BLIND_CURVE_ONLY"
STATUS_READY = "G16_COUNTERFACTUAL_CURVE_AUTHORIZED"
STATUS_STAND_DOWNS = "G16_COUNTERFACTUAL_CURVE_AUTHORIZED_WITH_STAND_DOWNS"
NEXT_STAGE = "LOCK_G16_REFINED_CURVE_WITH_COUNTERFACTUAL_LINEAGE_BEFORE_SCORING"


class G16CounterfactualCurveAuthorizationError(ValueError):
    """Raised when G15 counterfactual lineage and the G16 curve chain diverge."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _validate_upstream(
    *,
    counterfactual_authorization: Mapping[str, Any],
    prepared_curve_authorization: Mapping[str, Any],
    counterfactual_kwargs: Mapping[str, Any],
    curve_kwargs: Mapping[str, Any],
) -> None:
    try:
        validate_counterfactual_authorization(
            counterfactual_authorization, **dict(counterfactual_kwargs)
        )
    except G16CounterfactualCausalAuthorizationError as error:
        raise G16CounterfactualCurveAuthorizationError(
            f"counterfactual causal authorization invalid: {error}"
        ) from error
    try:
        validate_curve_authorization(
            prepared_curve_authorization, **dict(curve_kwargs)
        )
    except G16PreparedCurveAuthorizationError as error:
        raise G16CounterfactualCurveAuthorizationError(
            f"prepared curve authorization invalid: {error}"
        ) from error

    if (
        counterfactual_authorization.get("schema") != COUNTERFACTUAL_SCHEMA
        or counterfactual_authorization.get("authority") != COUNTERFACTUAL_AUTHORITY
        or counterfactual_authorization.get("status")
        not in {COUNTERFACTUAL_READY, COUNTERFACTUAL_STAND_DOWNS}
    ):
        raise G16CounterfactualCurveAuthorizationError(
            "counterfactual causal authorization is not ready"
        )
    if counterfactual_authorization.get("next_permitted_stage") != COUNTERFACTUAL_NEXT_STAGE:
        raise G16CounterfactualCurveAuthorizationError(
            "counterfactual causal authorization does not permit the curve adapter"
        )
    if (
        prepared_curve_authorization.get("schema") != PREPARED_CURVE_SCHEMA
        or prepared_curve_authorization.get("authority") != PREPARED_CURVE_AUTHORITY
        or prepared_curve_authorization.get("status")
        not in {PREPARED_CURVE_READY, PREPARED_CURVE_STAND_DOWNS}
    ):
        raise G16CounterfactualCurveAuthorizationError(
            "prepared curve authorization is not ready"
        )
    if prepared_curve_authorization.get("next_permitted_stage") != PREPARED_CURVE_NEXT_STAGE:
        raise G16CounterfactualCurveAuthorizationError(
            "prepared curve authorization has an unexpected next stage"
        )


def _cross_checks(
    counterfactual_authorization: Mapping[str, Any],
    prepared_curve_authorization: Mapping[str, Any],
) -> tuple[list[str], dict[str, str], list[str], list[str]]:
    link_fields = {
        "prepared_causal_authorization_fingerprint": "prepared_causal_authorization_fingerprint",
        "prepared_replay_gate_fingerprint": "prepared_replay_gate_fingerprint",
        "replay_fingerprint": "replay_fingerprint",
        "manifest_fingerprint": "manifest_fingerprint",
        "prepared_corpus_fingerprint": "prepared_corpus_fingerprint",
        "blind_prior_fingerprint": "blind_prior_fingerprint",
        "g16_plan_fingerprint": "plan_fingerprint",
        "authorization_stream_fingerprint": "authorization_stream_fingerprint",
        "posterior_stream_fingerprint": "posterior_stream_fingerprint",
        "g16_blind_forecast_fingerprint": "blind_forecast_fingerprint",
    }
    for counterfactual_field, curve_field in link_fields.items():
        if counterfactual_authorization.get(counterfactual_field) != prepared_curve_authorization.get(
            curve_field
        ):
            raise G16CounterfactualCurveAuthorizationError(
                f"prepared curve {curve_field} bypasses counterfactual causal lineage"
            )

    candidate_ids = [str(value) for value in counterfactual_authorization.get("candidate_ids") or []]
    if not candidate_ids or candidate_ids != sorted(candidate_ids):
        raise G16CounterfactualCurveAuthorizationError(
            "counterfactual candidate ids must be non-empty and sorted"
        )
    if len(candidate_ids) != len(set(candidate_ids)):
        raise G16CounterfactualCurveAuthorizationError(
            "counterfactual candidate ids must be unique"
        )
    registered = [
        str(value) for value in prepared_curve_authorization.get("registered_candidate_ids") or []
    ]
    if registered != candidate_ids:
        raise G16CounterfactualCurveAuthorizationError(
            "prepared curve registered candidates differ from counterfactual lineage"
        )

    evidence = {
        str(key): str(value)
        for key, value in dict(
            counterfactual_authorization.get("candidate_evidence_fingerprints") or {}
        ).items()
    }
    if sorted(evidence) != candidate_ids or any(not value for value in evidence.values()):
        raise G16CounterfactualCurveAuthorizationError(
            "counterfactual candidate evidence map is incomplete"
        )

    posterior_used = {
        str(value)
        for value in counterfactual_authorization.get(
            "candidate_ids_observed_in_posterior_attribution"
        )
        or []
    }
    if not posterior_used.issubset(set(candidate_ids)):
        raise G16CounterfactualCurveAuthorizationError(
            "posterior attribution contains a candidate outside counterfactual lineage"
        )
    curve_used = {
        str(value) for value in prepared_curve_authorization.get("used_candidate_ids") or []
    }
    if not curve_used.issubset(posterior_used):
        raise G16CounterfactualCurveAuthorizationError(
            "curve used a candidate not observed in the authorized posterior attribution"
        )

    lineage_stand_downs = sorted(
        {str(day) for day in counterfactual_authorization.get("all_stand_down_days") or []}
    )
    curve_stand_downs = sorted(
        {str(day) for day in prepared_curve_authorization.get("all_stand_down_days") or []}
    )
    return candidate_ids, evidence, sorted(curve_used), sorted(
        set(lineage_stand_downs) | set(curve_stand_downs)
    )


def _build_authorization(
    *,
    counterfactual_authorization: Mapping[str, Any],
    prepared_curve_authorization: Mapping[str, Any],
    counterfactual_kwargs: Mapping[str, Any],
    curve_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    originals = copy.deepcopy(
        (
            counterfactual_authorization,
            prepared_curve_authorization,
            counterfactual_kwargs,
            curve_kwargs,
        )
    )
    _validate_upstream(
        counterfactual_authorization=counterfactual_authorization,
        prepared_curve_authorization=prepared_curve_authorization,
        counterfactual_kwargs=counterfactual_kwargs,
        curve_kwargs=curve_kwargs,
    )
    candidate_ids, evidence, curve_used, stand_downs = _cross_checks(
        counterfactual_authorization, prepared_curve_authorization
    )
    result = {
        "schema": SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": STATUS_STAND_DOWNS if stand_downs else STATUS_READY,
        "authority": AUTHORITY,
        "counterfactual_causal_authorization_fingerprint": counterfactual_authorization.get(
            "fingerprint"
        ),
        "counterfactual_lineage_gate_fingerprint": counterfactual_authorization.get(
            "counterfactual_lineage_gate_fingerprint"
        ),
        "counterfactual_lesson_gate_fingerprint": counterfactual_authorization.get(
            "counterfactual_lesson_gate_fingerprint"
        ),
        "counterfactual_attribution_fingerprint": counterfactual_authorization.get(
            "counterfactual_attribution_fingerprint"
        ),
        "g15_publication_fingerprint": counterfactual_authorization.get(
            "g15_publication_fingerprint"
        ),
        "g15_adjudication_fingerprint": counterfactual_authorization.get(
            "g15_adjudication_fingerprint"
        ),
        "g16_registry_fingerprint": counterfactual_authorization.get(
            "g16_registry_fingerprint"
        ),
        "prepared_curve_authorization_fingerprint": prepared_curve_authorization.get(
            "fingerprint"
        ),
        "prepared_causal_authorization_fingerprint": prepared_curve_authorization.get(
            "prepared_causal_authorization_fingerprint"
        ),
        "prepared_replay_gate_fingerprint": prepared_curve_authorization.get(
            "prepared_replay_gate_fingerprint"
        ),
        "replay_fingerprint": prepared_curve_authorization.get("replay_fingerprint"),
        "manifest_fingerprint": prepared_curve_authorization.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": prepared_curve_authorization.get(
            "prepared_corpus_fingerprint"
        ),
        "blind_prior_fingerprint": prepared_curve_authorization.get(
            "blind_prior_fingerprint"
        ),
        "g16_blind_forecast_fingerprint": prepared_curve_authorization.get(
            "blind_forecast_fingerprint"
        ),
        "g16_blind_forecast_sha256": prepared_curve_authorization.get(
            "blind_forecast_sha256"
        ),
        "g16_plan_fingerprint": prepared_curve_authorization.get("plan_fingerprint"),
        "authorization_stream_fingerprint": prepared_curve_authorization.get(
            "authorization_stream_fingerprint"
        ),
        "posterior_stream_fingerprint": prepared_curve_authorization.get(
            "posterior_stream_fingerprint"
        ),
        "refined_curve_fingerprint": prepared_curve_authorization.get(
            "refined_curve_fingerprint"
        ),
        "transform_config": copy.deepcopy(
            dict(prepared_curve_authorization.get("transform_config") or {})
        ),
        "candidate_count": len(candidate_ids),
        "candidate_ids": candidate_ids,
        "candidate_evidence_fingerprints": evidence,
        "candidate_ids_used_by_curve": curve_used,
        "n_days": int(prepared_curve_authorization.get("n_days") or 0),
        "n_posterior_outputs": int(
            prepared_curve_authorization.get("n_posterior_outputs") or 0
        ),
        "n_curve_outputs_used": int(
            prepared_curve_authorization.get("n_curve_outputs_used") or 0
        ),
        "stand_down_days": stand_downs,
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": False,
        "g16_scoring_authorized": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_g16_blind_prior": False,
        "may_change_g16_blind_forecast": False,
        "may_change_posterior": False,
        "may_select_lessons_from_g16_outcomes": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": NEXT_STAGE,
        "note": (
            "The deterministic outcome-blind G16 curve is bound to the exact prepared "
            "NGK26 replay and to the same G15 full-minus-neutral lesson evidence that "
            "was published and pre-registered before G16 outcome access."
        ),
    }
    result["fingerprint"] = _fp(result)
    current = (
        counterfactual_authorization,
        prepared_curve_authorization,
        counterfactual_kwargs,
        curve_kwargs,
    )
    if current != originals:
        raise G16CounterfactualCurveAuthorizationError(
            "counterfactual curve authorization mutated a source artifact"
        )
    return result


def build_authorization(**kwargs: Any) -> dict[str, Any]:
    result = _build_authorization(**kwargs)
    validate_authorization(result, **kwargs)
    return result


def validate_authorization(authorization: Mapping[str, Any], **kwargs: Any) -> None:
    candidate = copy.deepcopy(dict(authorization))
    observed = candidate.pop("fingerprint", None)
    if observed != _fp(candidate):
        raise G16CounterfactualCurveAuthorizationError("authorization fingerprint mismatch")
    if candidate.get("schema") != SCHEMA or candidate.get("authority") != AUTHORITY:
        raise G16CounterfactualCurveAuthorizationError(
            "authorization schema/authority mismatch"
        )
    if candidate.get("status") not in {STATUS_READY, STATUS_STAND_DOWNS}:
        raise G16CounterfactualCurveAuthorizationError("authorization is not ready")

    false_fields = (
        "actual_g16_outcomes_used",
        "g16_scoring_authorized",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_g16_blind_prior",
        "may_change_g16_blind_forecast",
        "may_change_posterior",
        "may_select_lessons_from_g16_outcomes",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    )
    for field in false_fields:
        if candidate.get(field) is not False:
            raise G16CounterfactualCurveAuthorizationError(
                f"authorization must keep {field}=false"
            )
    if candidate.get("actual_g15_outcomes_used") is not True:
        raise G16CounterfactualCurveAuthorizationError(
            "authorization must disclose G15 outcome use"
        )
    for field in ("one_signal_authority_preserved", "blind_forecasts_immutable"):
        if candidate.get(field) is not True:
            raise G16CounterfactualCurveAuthorizationError(
                f"authorization must keep {field}=true"
            )
    if candidate.get("cme_event_contracts_mode") != "SHADOW":
        raise G16CounterfactualCurveAuthorizationError(
            "CME event contracts must remain SHADOW"
        )
    if candidate.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16CounterfactualCurveAuthorizationError(
            "brokerage contract must remain tastytrade_not_ibkr"
        )
    if candidate.get("next_permitted_stage") != NEXT_STAGE:
        raise G16CounterfactualCurveAuthorizationError(
            "authorization has an unexpected next stage"
        )

    rebuilt = _build_authorization(**kwargs)
    rebuilt.pop("fingerprint", None)
    candidate.pop("fingerprint", None)
    if candidate != rebuilt:
        raise G16CounterfactualCurveAuthorizationError(
            "authorization differs from deterministic reconstruction"
        )


def _fixture() -> dict[str, Any]:
    from ng_g16_counterfactual_causal_authorization import (
        _fixture as causal_fixture,
        build_authorization as build_counterfactual,
    )
    from ng_g16_curve_adapter import CurveConfig, build_refined_forecast
    from ng_g16_prepared_curve_authorization import build_authorization as build_curve

    source = causal_fixture()
    counterfactual_kwargs = {
        key: value
        for key, value in source.items()
        if not key.startswith("_") and key != "lineage_fixture"
    }
    counterfactual_authorization = build_counterfactual(**counterfactual_kwargs)
    blind_bytes = (
        json.dumps(source["g16_blind_forecast"], indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    shadow_plan = source["causal_artifacts"]["plan"]
    posterior_stream = source["causal_artifacts"]["posterior_stream"]
    refined_curve = build_refined_forecast(
        source["g16_blind_forecast"],
        shadow_plan,
        posterior_stream,
        blind_file_bytes=blind_bytes,
        config=CurveConfig(),
    )
    curve_kwargs = {
        "prepared_causal_authorization": source["prepared_authorization"],
        "prepared_gate": source["prepared_gate"],
        "prepared_index": source["prepared_index"],
        "manifest": source["manifest"],
        "replay": source["g16_replay"],
        "blind_prior": source["blind_prior"],
        "causal_artifacts": source["causal_artifacts"],
        "blind_forecast": source["g16_blind_forecast"],
        "blind_safe_state": source["g16_blind_safe_state"],
        "registry_source": source["counterfactual_gate"]["adjudication"],
        "shadow_plan": shadow_plan,
        "posterior_stream": posterior_stream,
        "refined_curve": refined_curve,
        "blind_file_bytes": blind_bytes,
    }
    prepared_curve_authorization = build_curve(**curve_kwargs)
    return {
        "_temporary": source["_temporary"],
        "counterfactual_authorization": counterfactual_authorization,
        "prepared_curve_authorization": prepared_curve_authorization,
        "counterfactual_kwargs": counterfactual_kwargs,
        "curve_kwargs": curve_kwargs,
    }


def selftest() -> int:
    fixture = _fixture()
    try:
        result = build_authorization(
            **{key: value for key, value in fixture.items() if not key.startswith("_")}
        )
        assert result["candidate_count"] > 0
        assert result["actual_g16_outcomes_used"] is False
        assert result["g16_scoring_authorized"] is False
        assert result["may_update_ng_brain"] is False
        assert result["options_lane_started"] is False
    finally:
        fixture["_temporary"].cleanup()
    print("[ng_g16_counterfactual_curve_authorization] selftest PASS")
    return 0


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G16CounterfactualCurveAuthorizationError(f"expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--counterfactual-authorization", type=Path)
    parser.add_argument("--prepared-curve-authorization", type=Path)
    parser.add_argument("--counterfactual-context", type=Path)
    parser.add_argument("--curve-context", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    required = (
        args.counterfactual_authorization,
        args.prepared_curve_authorization,
        args.counterfactual_context,
        args.curve_context,
        args.out,
    )
    if any(value is None for value in required):
        parser.error(
            "authorization, prepared curve, both context JSON files, and --out are required"
        )
    result = build_authorization(
        counterfactual_authorization=_load(args.counterfactual_authorization),
        prepared_curve_authorization=_load(args.prepared_curve_authorization),
        counterfactual_kwargs=_load(args.counterfactual_context),
        curve_kwargs=_load(args.curve_context),
    )
    _atomic(args.out, result)
    print(json.dumps({"status": result["status"], "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
