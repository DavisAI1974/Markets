#!/usr/bin/env python3
"""Bind exact G16 corpus provenance directly into curve authorization.

This outcome-blind gate joins the exact causal authorization (verified replay
bytes, common L1/MBO event windows, and locked G15 lesson lineage) with the
deterministic G16 counterfactual curve authorization. The resulting curve
authority is the only artifact permitted to proceed to the pre-scoring lock.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from ng_g16_exact_counterfactual_causal_authorization import (
    AUTHORITY as EXACT_CAUSAL_AUTHORITY,
    G16ExactCounterfactualCausalAuthorizationError,
    NEXT_STAGE as EXACT_CAUSAL_NEXT_STAGE,
    SCHEMA as EXACT_CAUSAL_SCHEMA,
    STATUS_READY as EXACT_CAUSAL_READY,
    STATUS_STAND_DOWNS as EXACT_CAUSAL_STAND_DOWNS,
    validate_authorization as validate_exact_causal_authorization,
)
from ng_g16_counterfactual_curve_authorization import (
    AUTHORITY as CURVE_AUTHORITY,
    G16CounterfactualCurveAuthorizationError,
    NEXT_STAGE as CURVE_NEXT_STAGE,
    SCHEMA as CURVE_SCHEMA,
    STATUS_READY as CURVE_READY,
    STATUS_STAND_DOWNS as CURVE_STAND_DOWNS,
    validate_authorization as validate_counterfactual_curve_authorization,
)

SCHEMA = "ng_g16_exact_counterfactual_curve_authorization.v1"
AUTHORITY = "EXACT_G16_CORPUS_BYTES_WINDOWS_AND_G15_COUNTERFACTUAL_CURVE_ONLY"
STATUS_READY = "G16_EXACT_COUNTERFACTUAL_CURVE_AUTHORIZED"
STATUS_STAND_DOWNS = "G16_EXACT_COUNTERFACTUAL_CURVE_AUTHORIZED_WITH_STAND_DOWNS"
NEXT_STAGE = (
    "LOCK_G16_REFINED_CURVE_WITH_EXACT_CORPUS_AND_COUNTERFACTUAL_LINEAGE_BEFORE_SCORING"
)
EXPECTED_REPLAY_SOURCE_COUNT = 22


class G16ExactCounterfactualCurveAuthorizationError(ValueError):
    """Raised when exact causal provenance and the G16 curve authority diverge."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise G16ExactCounterfactualCurveAuthorizationError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise G16ExactCounterfactualCurveAuthorizationError(
            f"JSON artifact must be an object: {path}"
        )
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any]) -> None:
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
        if value.get(field) is not False:
            raise G16ExactCounterfactualCurveAuthorizationError(
                f"{field} must remain false"
            )
    if value.get("actual_g15_outcomes_used") is not True:
        raise G16ExactCounterfactualCurveAuthorizationError(
            "G15 outcome use must be disclosed"
        )
    for field in (
        "one_signal_authority_preserved",
        "blind_forecasts_immutable",
        "all_g16_replay_sources_bound_to_exact_partition",
        "all_g16_state_spans_inside_exact_common_windows",
    ):
        if value.get(field) is not True:
            raise G16ExactCounterfactualCurveAuthorizationError(
                f"{field} must remain true"
            )
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise G16ExactCounterfactualCurveAuthorizationError(
            "CME event contracts must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16ExactCounterfactualCurveAuthorizationError(
            "brokerage contract must remain tastytrade, not IBKR"
        )


def _validate_upstream(
    exact_causal_authorization: Mapping[str, Any],
    counterfactual_curve_authorization: Mapping[str, Any],
    curve_kwargs: Mapping[str, Any],
) -> None:
    try:
        validate_exact_causal_authorization(exact_causal_authorization)
    except G16ExactCounterfactualCausalAuthorizationError as error:
        raise G16ExactCounterfactualCurveAuthorizationError(
            f"exact counterfactual causal authorization invalid: {error}"
        ) from error
    try:
        validate_counterfactual_curve_authorization(
            counterfactual_curve_authorization, **dict(curve_kwargs)
        )
    except G16CounterfactualCurveAuthorizationError as error:
        raise G16ExactCounterfactualCurveAuthorizationError(
            f"counterfactual curve authorization invalid: {error}"
        ) from error

    if (
        exact_causal_authorization.get("schema") != EXACT_CAUSAL_SCHEMA
        or exact_causal_authorization.get("authority") != EXACT_CAUSAL_AUTHORITY
        or exact_causal_authorization.get("status")
        not in {EXACT_CAUSAL_READY, EXACT_CAUSAL_STAND_DOWNS}
    ):
        raise G16ExactCounterfactualCurveAuthorizationError(
            "exact counterfactual causal authorization is not ready"
        )
    if exact_causal_authorization.get("next_permitted_stage") != EXACT_CAUSAL_NEXT_STAGE:
        raise G16ExactCounterfactualCurveAuthorizationError(
            "exact causal authorization does not permit outcome-blind curve construction"
        )
    if (
        counterfactual_curve_authorization.get("schema") != CURVE_SCHEMA
        or counterfactual_curve_authorization.get("authority") != CURVE_AUTHORITY
        or counterfactual_curve_authorization.get("status")
        not in {CURVE_READY, CURVE_STAND_DOWNS}
    ):
        raise G16ExactCounterfactualCurveAuthorizationError(
            "counterfactual curve authorization is not ready"
        )
    if counterfactual_curve_authorization.get("next_permitted_stage") != CURVE_NEXT_STAGE:
        raise G16ExactCounterfactualCurveAuthorizationError(
            "counterfactual curve authorization has an unexpected next stage"
        )


def _cross_checks(
    exact_causal_authorization: Mapping[str, Any],
    counterfactual_curve_authorization: Mapping[str, Any],
) -> tuple[list[str], dict[str, str], list[str], list[str]]:
    link_fields = {
        "counterfactual_causal_authorization_fingerprint":
            "counterfactual_causal_authorization_fingerprint",
        "prepared_causal_authorization_fingerprint":
            "prepared_causal_authorization_fingerprint",
        "prepared_replay_gate_fingerprint": "prepared_replay_gate_fingerprint",
        "replay_fingerprint": "replay_fingerprint",
        "manifest_fingerprint": "manifest_fingerprint",
        "prepared_corpus_fingerprint": "prepared_corpus_fingerprint",
        "blind_prior_fingerprint": "blind_prior_fingerprint",
        "g16_plan_fingerprint": "g16_plan_fingerprint",
        "authorization_stream_fingerprint": "authorization_stream_fingerprint",
        "posterior_stream_fingerprint": "posterior_stream_fingerprint",
        "g16_blind_forecast_fingerprint": "g16_blind_forecast_fingerprint",
    }
    for exact_field, curve_field in link_fields.items():
        if exact_causal_authorization.get(exact_field) != (
            counterfactual_curve_authorization.get(curve_field)
        ):
            raise G16ExactCounterfactualCurveAuthorizationError(
                f"counterfactual curve {curve_field} bypasses exact causal provenance"
            )

    if exact_causal_authorization.get("bound_replay_source_count") != (
        EXPECTED_REPLAY_SOURCE_COUNT
    ):
        raise G16ExactCounterfactualCurveAuthorizationError(
            "exactly 22 G16 replay lanes must remain bound at curve authorization"
        )
    for field in (
        "all_g16_replay_sources_bound_to_exact_partition",
        "all_g16_state_spans_inside_exact_common_windows",
    ):
        if exact_causal_authorization.get(field) is not True:
            raise G16ExactCounterfactualCurveAuthorizationError(
                f"exact causal authorization must keep {field}=true"
            )

    candidate_ids = [
        str(value) for value in exact_causal_authorization.get("candidate_ids") or []
    ]
    if not candidate_ids or candidate_ids != sorted(candidate_ids):
        raise G16ExactCounterfactualCurveAuthorizationError(
            "exact causal candidate ids must be non-empty and sorted"
        )
    if len(candidate_ids) != len(set(candidate_ids)):
        raise G16ExactCounterfactualCurveAuthorizationError(
            "exact causal candidate ids must be unique"
        )
    curve_candidates = [
        str(value)
        for value in counterfactual_curve_authorization.get("candidate_ids") or []
    ]
    if curve_candidates != candidate_ids:
        raise G16ExactCounterfactualCurveAuthorizationError(
            "counterfactual curve candidates differ from exact causal lineage"
        )

    evidence = {
        str(key): str(value)
        for key, value in dict(
            exact_causal_authorization.get("candidate_evidence_fingerprints") or {}
        ).items()
    }
    curve_evidence = {
        str(key): str(value)
        for key, value in dict(
            counterfactual_curve_authorization.get(
                "candidate_evidence_fingerprints"
            )
            or {}
        ).items()
    }
    if sorted(evidence) != candidate_ids or any(not value for value in evidence.values()):
        raise G16ExactCounterfactualCurveAuthorizationError(
            "exact causal candidate evidence map is incomplete"
        )
    if curve_evidence != evidence:
        raise G16ExactCounterfactualCurveAuthorizationError(
            "counterfactual curve evidence differs from exact causal lineage"
        )

    posterior_used = {
        str(value)
        for value in exact_causal_authorization.get(
            "candidate_ids_observed_in_posterior_attribution"
        )
        or []
    }
    if not posterior_used.issubset(set(candidate_ids)):
        raise G16ExactCounterfactualCurveAuthorizationError(
            "exact causal posterior attribution contains an unregistered candidate"
        )
    curve_used = {
        str(value)
        for value in counterfactual_curve_authorization.get(
            "candidate_ids_used_by_curve"
        )
        or []
    }
    if not curve_used.issubset(posterior_used):
        raise G16ExactCounterfactualCurveAuthorizationError(
            "curve used a candidate not present in exact authorized posterior attribution"
        )

    exact_stand_downs = sorted(
        {str(day) for day in exact_causal_authorization.get("all_stand_down_days") or []}
    )
    curve_stand_downs = sorted(
        {str(day) for day in counterfactual_curve_authorization.get("stand_down_days") or []}
    )
    return candidate_ids, evidence, sorted(curve_used), sorted(
        set(exact_stand_downs) | set(curve_stand_downs)
    )


def _build_unchecked(
    exact_causal_authorization: Mapping[str, Any],
    counterfactual_curve_authorization: Mapping[str, Any],
    curve_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    exact = copy.deepcopy(dict(exact_causal_authorization))
    curve = copy.deepcopy(dict(counterfactual_curve_authorization))
    context = copy.deepcopy(dict(curve_kwargs))
    originals = copy.deepcopy((exact, curve, context))
    _validate_upstream(exact, curve, context)
    candidate_ids, evidence, curve_used, stand_downs = _cross_checks(exact, curve)

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": STATUS_STAND_DOWNS if stand_downs else STATUS_READY,
        "authority": AUTHORITY,
        "exact_counterfactual_causal_authorization_fingerprint": exact.get(
            "fingerprint"
        ),
        "counterfactual_curve_authorization_fingerprint": curve.get("fingerprint"),
        "exact_partition_replay_authorization_fingerprint": exact.get(
            "exact_partition_replay_authorization_fingerprint"
        ),
        "counterfactual_causal_authorization_fingerprint": exact.get(
            "counterfactual_causal_authorization_fingerprint"
        ),
        "exact_partition_gate_fingerprint": exact.get(
            "exact_partition_gate_fingerprint"
        ),
        "source_binding_fingerprint": exact.get("source_binding_fingerprint"),
        "window_contract_fingerprint": exact.get("window_contract_fingerprint"),
        "bound_replay_source_count": exact.get("bound_replay_source_count"),
        "all_g16_replay_sources_bound_to_exact_partition": True,
        "all_g16_state_spans_inside_exact_common_windows": True,
        "counterfactual_lineage_gate_fingerprint": exact.get(
            "counterfactual_lineage_gate_fingerprint"
        ),
        "prepared_curve_authorization_fingerprint": curve.get(
            "prepared_curve_authorization_fingerprint"
        ),
        "prepared_causal_authorization_fingerprint": curve.get(
            "prepared_causal_authorization_fingerprint"
        ),
        "prepared_replay_gate_fingerprint": curve.get(
            "prepared_replay_gate_fingerprint"
        ),
        "replay_fingerprint": curve.get("replay_fingerprint"),
        "manifest_fingerprint": curve.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": curve.get("prepared_corpus_fingerprint"),
        "blind_prior_fingerprint": curve.get("blind_prior_fingerprint"),
        "g16_blind_forecast_fingerprint": curve.get(
            "g16_blind_forecast_fingerprint"
        ),
        "g16_blind_forecast_sha256": curve.get("g16_blind_forecast_sha256"),
        "g16_plan_fingerprint": curve.get("g16_plan_fingerprint"),
        "authorization_stream_fingerprint": curve.get(
            "authorization_stream_fingerprint"
        ),
        "posterior_stream_fingerprint": curve.get("posterior_stream_fingerprint"),
        "refined_curve_fingerprint": curve.get("refined_curve_fingerprint"),
        "transform_config": copy.deepcopy(dict(curve.get("transform_config") or {})),
        "candidate_count": len(candidate_ids),
        "candidate_ids": candidate_ids,
        "candidate_evidence_fingerprints": evidence,
        "candidate_ids_used_by_curve": curve_used,
        "n_days": int(curve.get("n_days") or 0),
        "n_posterior_outputs": int(curve.get("n_posterior_outputs") or 0),
        "n_curve_outputs_used": int(curve.get("n_curve_outputs_used") or 0),
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
            "The outcome-blind G16 refined curve is authorized only when its causal "
            "posterior is bound to the verified exact replay bytes, common L1/MBO "
            "event windows, and locked G15 counterfactual lesson lineage."
        ),
    }
    result["fingerprint"] = _fp(result)
    if (exact, curve, context) != originals:
        raise G16ExactCounterfactualCurveAuthorizationError(
            "curve authorization mutated an upstream artifact"
        )
    return result


def build_authorization(
    exact_causal_authorization: Mapping[str, Any],
    counterfactual_curve_authorization: Mapping[str, Any],
    *,
    curve_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    result = _build_unchecked(
        exact_causal_authorization,
        counterfactual_curve_authorization,
        curve_kwargs,
    )
    validate_authorization(
        result,
        exact_causal_authorization=exact_causal_authorization,
        counterfactual_curve_authorization=counterfactual_curve_authorization,
        curve_kwargs=curve_kwargs,
    )
    return result


def validate_authorization(
    value: Mapping[str, Any],
    *,
    exact_causal_authorization: Mapping[str, Any],
    counterfactual_curve_authorization: Mapping[str, Any],
    curve_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise G16ExactCounterfactualCurveAuthorizationError(
            "exact counterfactual curve authorization schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    if checked.get("authority") != AUTHORITY:
        raise G16ExactCounterfactualCurveAuthorizationError(
            "curve authorization authority mismatch"
        )
    if checked.get("status") not in {STATUS_READY, STATUS_STAND_DOWNS}:
        raise G16ExactCounterfactualCurveAuthorizationError(
            "curve authorization is not ready"
        )
    if checked.get("next_permitted_stage") != NEXT_STAGE:
        raise G16ExactCounterfactualCurveAuthorizationError(
            "curve authorization has an unexpected next stage"
        )
    _authority(checked)
    expected = _build_unchecked(
        exact_causal_authorization,
        counterfactual_curve_authorization,
        curve_kwargs,
    )
    if _canonical(expected) != _canonical(checked):
        raise G16ExactCounterfactualCurveAuthorizationError(
            "curve authorization differs from deterministic reconstruction"
        )
    return copy.deepcopy(dict(value))


def _selftest_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    exact = {
        "schema": EXACT_CAUSAL_SCHEMA,
        "authority": EXACT_CAUSAL_AUTHORITY,
        "status": EXACT_CAUSAL_READY,
        "fingerprint": "exact-causal",
        "exact_partition_replay_authorization_fingerprint": "exact-replay",
        "counterfactual_causal_authorization_fingerprint": "counterfactual-causal",
        "exact_partition_gate_fingerprint": "partition",
        "prepared_replay_gate_fingerprint": "prepared-replay",
        "manifest_fingerprint": "manifest",
        "prepared_corpus_fingerprint": "corpus",
        "replay_fingerprint": "replay",
        "blind_prior_fingerprint": "blind-prior",
        "source_binding_fingerprint": "source-binding",
        "window_contract_fingerprint": "window-contract",
        "bound_replay_source_count": 22,
        "all_g16_replay_sources_bound_to_exact_partition": True,
        "all_g16_state_spans_inside_exact_common_windows": True,
        "counterfactual_lineage_gate_fingerprint": "lineage",
        "prepared_causal_authorization_fingerprint": "prepared-causal",
        "g16_plan_fingerprint": "plan",
        "authorization_stream_fingerprint": "authorization-stream",
        "posterior_stream_fingerprint": "posterior-stream",
        "g16_blind_forecast_fingerprint": "blind-forecast",
        "candidate_ids": ["candidate-a"],
        "candidate_evidence_fingerprints": {"candidate-a": "evidence-a"},
        "candidate_ids_observed_in_posterior_attribution": ["candidate-a"],
        "all_stand_down_days": [],
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
        "next_permitted_stage": EXACT_CAUSAL_NEXT_STAGE,
    }
    curve = {
        "schema": CURVE_SCHEMA,
        "authority": CURVE_AUTHORITY,
        "status": CURVE_READY,
        "fingerprint": "curve",
        "counterfactual_causal_authorization_fingerprint": "counterfactual-causal",
        "prepared_curve_authorization_fingerprint": "prepared-curve",
        "prepared_causal_authorization_fingerprint": "prepared-causal",
        "prepared_replay_gate_fingerprint": "prepared-replay",
        "replay_fingerprint": "replay",
        "manifest_fingerprint": "manifest",
        "prepared_corpus_fingerprint": "corpus",
        "blind_prior_fingerprint": "blind-prior",
        "g16_blind_forecast_fingerprint": "blind-forecast",
        "g16_blind_forecast_sha256": "blind-sha",
        "g16_plan_fingerprint": "plan",
        "authorization_stream_fingerprint": "authorization-stream",
        "posterior_stream_fingerprint": "posterior-stream",
        "refined_curve_fingerprint": "refined-curve",
        "transform_config": {"scale": 1.0},
        "candidate_count": 1,
        "candidate_ids": ["candidate-a"],
        "candidate_evidence_fingerprints": {"candidate-a": "evidence-a"},
        "candidate_ids_used_by_curve": ["candidate-a"],
        "n_days": 11,
        "n_posterior_outputs": 11,
        "n_curve_outputs_used": 11,
        "stand_down_days": [],
        "next_permitted_stage": CURVE_NEXT_STAGE,
    }
    return exact, curve, {}


def selftest() -> int:
    from unittest import mock

    exact, curve, curve_kwargs = _selftest_inputs()
    with mock.patch(
        __name__ + ".validate_exact_causal_authorization", return_value=exact
    ), mock.patch(
        __name__ + ".validate_counterfactual_curve_authorization",
        return_value=None,
    ):
        result = build_authorization(exact, curve, curve_kwargs=curve_kwargs)
        assert result["status"] == STATUS_READY
        assert result["bound_replay_source_count"] == EXPECTED_REPLAY_SOURCE_COUNT
        assert result["actual_g16_outcomes_used"] is False
        assert result["g16_scoring_authorized"] is False
        assert result["options_lane_started"] is False
    print("[ng_g16_exact_counterfactual_curve_authorization] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-causal-authorization", type=Path)
    parser.add_argument("--counterfactual-curve-authorization", type=Path)
    parser.add_argument("--curve-context", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if any(
        value is None
        for value in (
            args.exact_causal_authorization,
            args.counterfactual_curve_authorization,
            args.curve_context,
            args.out,
        )
    ):
        parser.error(
            "--exact-causal-authorization, --counterfactual-curve-authorization, "
            "--curve-context, and --out are required"
        )
    result = build_authorization(
        _load(args.exact_causal_authorization),
        _load(args.counterfactual_curve_authorization),
        curve_kwargs=_load(args.curve_context),
    )
    _write(args.out, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "bound_replay_sources": result["bound_replay_source_count"],
                "candidate_count": result["candidate_count"],
                "stand_down_days": result["stand_down_days"],
                "fingerprint": result["fingerprint"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
