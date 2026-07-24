#!/usr/bin/env python3
"""Bind verified G16 replay bytes/windows into counterfactual causal authority.

This outcome-blind wrapper joins two independent proofs before any G16 refined
curve may be built: (1) every replay lane and state cutoff is bound to the
verified broad L1/MBO corpus partition and exact common event window; and (2)
the causal posterior uses only the locked G15 counterfactual lesson lineage.
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
    NEXT_STAGE as COUNTERFACTUAL_NEXT_STAGE,
    SCHEMA as COUNTERFACTUAL_SCHEMA,
    STATUS_READY as COUNTERFACTUAL_READY,
    STATUS_STAND_DOWNS as COUNTERFACTUAL_STAND_DOWNS,
    _fp as counterfactual_fingerprint,
)
from ng_g16_exact_partition_replay_authorization import (
    G16ExactPartitionReplayAuthorizationError,
    READY as EXACT_READY,
    READY_WITH_STAND_DOWNS as EXACT_STAND_DOWNS,
    SCHEMA as EXACT_SCHEMA,
    validate_authorization as validate_exact_authorization,
)

SCHEMA = "ng_g16_exact_counterfactual_causal_authorization.v1"
AUTHORITY = "EXACT_G16_CORPUS_BYTES_WINDOWS_AND_G15_COUNTERFACTUAL_CAUSAL_ONLY"
STATUS_READY = "G16_EXACT_COUNTERFACTUAL_CAUSAL_AUTHORIZED"
STATUS_STAND_DOWNS = "G16_EXACT_COUNTERFACTUAL_CAUSAL_AUTHORIZED_WITH_STAND_DOWNS"
NEXT_STAGE = "OUTCOME_BLIND_G16_CURVE_ADAPTER_WITH_EXACT_CORPUS_AND_COUNTERFACTUAL_LINEAGE"
EXPECTED_REPLAY_SOURCE_COUNT = 22


class G16ExactCounterfactualCausalAuthorizationError(ValueError):
    """Raised when exact replay provenance and causal lesson lineage diverge."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise G16ExactCounterfactualCausalAuthorizationError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise G16ExactCounterfactualCausalAuthorizationError(
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
            raise G16ExactCounterfactualCausalAuthorizationError(
                f"{field} must remain false"
            )
    if value.get("actual_g15_outcomes_used") is not True:
        raise G16ExactCounterfactualCausalAuthorizationError(
            "G15 outcome use must be disclosed"
        )
    if value.get("one_signal_authority_preserved") is not True:
        raise G16ExactCounterfactualCausalAuthorizationError(
            "one signal authority must be preserved"
        )
    if value.get("blind_forecasts_immutable") is not True:
        raise G16ExactCounterfactualCausalAuthorizationError(
            "blind forecasts must remain immutable"
        )
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise G16ExactCounterfactualCausalAuthorizationError(
            "CME event contracts must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16ExactCounterfactualCausalAuthorizationError(
            "brokerage contract must remain tastytrade, not IBKR"
        )


def _validate_upstream(
    exact_authorization: Mapping[str, Any],
    counterfactual_authorization: Mapping[str, Any],
) -> None:
    try:
        validate_exact_authorization(exact_authorization)
    except G16ExactPartitionReplayAuthorizationError as error:
        raise G16ExactCounterfactualCausalAuthorizationError(
            f"exact partition/replay authorization invalid: {error}"
        ) from error

    counterfactual_payload = copy.deepcopy(dict(counterfactual_authorization))
    observed = counterfactual_payload.pop("fingerprint", None)
    if observed != counterfactual_fingerprint(counterfactual_payload):
        raise G16ExactCounterfactualCausalAuthorizationError(
            "counterfactual causal authorization fingerprint mismatch"
        )
    if exact_authorization.get("schema") != EXACT_SCHEMA or exact_authorization.get(
        "status"
    ) not in {EXACT_READY, EXACT_STAND_DOWNS}:
        raise G16ExactCounterfactualCausalAuthorizationError(
            "exact partition/replay authorization is not ready"
        )
    if counterfactual_authorization.get(
        "schema"
    ) != COUNTERFACTUAL_SCHEMA or counterfactual_authorization.get("status") not in {
        COUNTERFACTUAL_READY,
        COUNTERFACTUAL_STAND_DOWNS,
    }:
        raise G16ExactCounterfactualCausalAuthorizationError(
            "counterfactual causal authorization is not ready"
        )
    if counterfactual_authorization.get("next_permitted_stage") != COUNTERFACTUAL_NEXT_STAGE:
        raise G16ExactCounterfactualCausalAuthorizationError(
            "counterfactual causal authorization has an unexpected next stage"
        )
    _authority(counterfactual_authorization)


def _cross_checks(
    exact_authorization: Mapping[str, Any],
    counterfactual_authorization: Mapping[str, Any],
) -> None:
    for field in (
        "prepared_replay_gate_fingerprint",
        "manifest_fingerprint",
        "prepared_corpus_fingerprint",
        "replay_fingerprint",
        "blind_prior_fingerprint",
    ):
        if exact_authorization.get(field) != counterfactual_authorization.get(field):
            raise G16ExactCounterfactualCausalAuthorizationError(
                f"counterfactual causal authorization uses a different {field}"
            )
    if exact_authorization.get("bound_replay_source_count") != EXPECTED_REPLAY_SOURCE_COUNT:
        raise G16ExactCounterfactualCausalAuthorizationError(
            "exactly 22 G16 replay lanes must be bound"
        )
    for field in (
        "all_g16_replay_sources_bound_to_exact_partition",
        "all_g16_state_spans_inside_exact_common_windows",
    ):
        if exact_authorization.get(field) is not True:
            raise G16ExactCounterfactualCausalAuthorizationError(
                f"exact replay authorization must keep {field}=true"
            )
    candidate_ids = list(counterfactual_authorization.get("candidate_ids") or [])
    if not candidate_ids or candidate_ids != sorted(set(candidate_ids)):
        raise G16ExactCounterfactualCausalAuthorizationError(
            "counterfactual candidate ids must be non-empty, unique, and sorted"
        )
    evidence = dict(
        counterfactual_authorization.get("candidate_evidence_fingerprints") or {}
    )
    if sorted(evidence) != candidate_ids or any(not value for value in evidence.values()):
        raise G16ExactCounterfactualCausalAuthorizationError(
            "counterfactual candidate evidence map is incomplete"
        )


def _build_unchecked(
    exact_authorization: Mapping[str, Any],
    counterfactual_authorization: Mapping[str, Any],
) -> dict[str, Any]:
    exact = copy.deepcopy(dict(exact_authorization))
    causal = copy.deepcopy(dict(counterfactual_authorization))
    originals = copy.deepcopy((exact, causal))
    _validate_upstream(exact, causal)
    _cross_checks(exact, causal)

    exact_stand_downs = sorted({str(day) for day in exact.get("stand_down_days") or []})
    causal_stand_downs = sorted(
        {str(day) for day in causal.get("all_stand_down_days") or []}
    )
    all_stand_downs = sorted(set(exact_stand_downs) | set(causal_stand_downs))
    candidate_ids = list(causal.get("candidate_ids") or [])

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "status": STATUS_STAND_DOWNS if all_stand_downs else STATUS_READY,
        "authority": AUTHORITY,
        "exact_partition_replay_authorization_fingerprint": exact.get("fingerprint"),
        "counterfactual_causal_authorization_fingerprint": causal.get("fingerprint"),
        "exact_partition_gate_fingerprint": exact.get("exact_partition_gate_fingerprint"),
        "prepared_replay_gate_fingerprint": exact.get("prepared_replay_gate_fingerprint"),
        "manifest_fingerprint": exact.get("manifest_fingerprint"),
        "prepared_corpus_fingerprint": exact.get("prepared_corpus_fingerprint"),
        "replay_fingerprint": exact.get("replay_fingerprint"),
        "blind_prior_fingerprint": exact.get("blind_prior_fingerprint"),
        "source_binding_fingerprint": exact.get("source_binding_fingerprint"),
        "window_contract_fingerprint": exact.get("window_contract_fingerprint"),
        "bound_replay_source_count": exact.get("bound_replay_source_count"),
        "all_g16_replay_sources_bound_to_exact_partition": True,
        "all_g16_state_spans_inside_exact_common_windows": True,
        "counterfactual_lineage_gate_fingerprint": causal.get(
            "counterfactual_lineage_gate_fingerprint"
        ),
        "prepared_causal_authorization_fingerprint": causal.get(
            "prepared_causal_authorization_fingerprint"
        ),
        "g16_plan_fingerprint": causal.get("g16_plan_fingerprint"),
        "authorization_stream_fingerprint": causal.get(
            "authorization_stream_fingerprint"
        ),
        "posterior_stream_fingerprint": causal.get("posterior_stream_fingerprint"),
        "g16_blind_forecast_fingerprint": causal.get(
            "g16_blind_forecast_fingerprint"
        ),
        "g16_blind_safe_state_fingerprint": causal.get(
            "g16_blind_safe_state_fingerprint"
        ),
        "candidate_count": len(candidate_ids),
        "candidate_ids": candidate_ids,
        "candidate_evidence_fingerprints": copy.deepcopy(
            dict(causal.get("candidate_evidence_fingerprints") or {})
        ),
        "candidate_ids_observed_in_posterior_attribution": list(
            causal.get("candidate_ids_observed_in_posterior_attribution") or []
        ),
        "exact_partition_stand_down_days": exact_stand_downs,
        "counterfactual_causal_stand_down_days": causal_stand_downs,
        "all_stand_down_days": all_stand_downs,
        "source_exact_partition_replay_authorization": exact,
        "source_counterfactual_causal_authorization": causal,
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
            "The G16 pre-cutoff posterior is authorized only when replay bytes and "
            "state windows match the verified broad corpus and attribution uses the "
            "locked G15 counterfactual lesson lineage."
        ),
    }
    result["fingerprint"] = _fp(result)
    if (exact, causal) != originals:
        raise G16ExactCounterfactualCausalAuthorizationError(
            "authorization mutated an upstream artifact"
        )
    return result


def build_authorization(
    exact_authorization: Mapping[str, Any],
    counterfactual_authorization: Mapping[str, Any],
) -> dict[str, Any]:
    result = _build_unchecked(exact_authorization, counterfactual_authorization)
    validate_authorization(result)
    return result


def validate_authorization(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise G16ExactCounterfactualCausalAuthorizationError(
            "exact counterfactual causal authorization schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    if checked.get("authority") != AUTHORITY:
        raise G16ExactCounterfactualCausalAuthorizationError(
            "authorization authority mismatch"
        )
    if checked.get("status") not in {STATUS_READY, STATUS_STAND_DOWNS}:
        raise G16ExactCounterfactualCausalAuthorizationError(
            "authorization is not ready"
        )
    if checked.get("next_permitted_stage") != NEXT_STAGE:
        raise G16ExactCounterfactualCausalAuthorizationError(
            "authorization has an unexpected next stage"
        )
    _authority(checked)
    expected = _build_unchecked(
        checked.get("source_exact_partition_replay_authorization") or {},
        checked.get("source_counterfactual_causal_authorization") or {},
    )
    if _canonical(expected) != _canonical(checked):
        raise G16ExactCounterfactualCausalAuthorizationError(
            "authorization differs from deterministic reconstruction"
        )
    return copy.deepcopy(dict(value))


def selftest() -> int:
    from unittest import mock

    exact = {
        "schema": EXACT_SCHEMA,
        "status": EXACT_READY,
        "fingerprint": "exact",
        "exact_partition_gate_fingerprint": "partition",
        "prepared_replay_gate_fingerprint": "prepared-replay",
        "manifest_fingerprint": "manifest",
        "prepared_corpus_fingerprint": "corpus",
        "replay_fingerprint": "replay",
        "blind_prior_fingerprint": "blind",
        "source_binding_fingerprint": "source-binding",
        "window_contract_fingerprint": "window",
        "bound_replay_source_count": 22,
        "all_g16_replay_sources_bound_to_exact_partition": True,
        "all_g16_state_spans_inside_exact_common_windows": True,
        "stand_down_days": [],
    }
    causal = {
        "schema": COUNTERFACTUAL_SCHEMA,
        "status": COUNTERFACTUAL_READY,
        "prepared_replay_gate_fingerprint": "prepared-replay",
        "manifest_fingerprint": "manifest",
        "prepared_corpus_fingerprint": "corpus",
        "replay_fingerprint": "replay",
        "blind_prior_fingerprint": "blind",
        "counterfactual_lineage_gate_fingerprint": "lineage",
        "prepared_causal_authorization_fingerprint": "prepared-causal",
        "g16_plan_fingerprint": "plan",
        "authorization_stream_fingerprint": "auth-stream",
        "posterior_stream_fingerprint": "posterior-stream",
        "g16_blind_forecast_fingerprint": "blind-forecast",
        "g16_blind_safe_state_fingerprint": "blind-state",
        "candidate_ids": ["candidate-a"],
        "candidate_evidence_fingerprints": {"candidate-a": "evidence-a"},
        "candidate_ids_observed_in_posterior_attribution": ["candidate-a"],
        "all_stand_down_days": [],
        "next_permitted_stage": COUNTERFACTUAL_NEXT_STAGE,
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
    }
    causal["fingerprint"] = counterfactual_fingerprint(causal)
    with mock.patch(
        __name__ + ".validate_exact_authorization", return_value=exact
    ):
        result = build_authorization(exact, causal)
        assert result["status"] == STATUS_READY
        assert result["bound_replay_source_count"] == 22
        assert result["actual_g16_outcomes_used"] is False
        assert result["options_lane_started"] is False
    print("[ng_g16_exact_counterfactual_causal_authorization] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-partition-replay-authorization", type=Path)
    parser.add_argument("--counterfactual-causal-authorization", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if any(
        value is None
        for value in (
            args.exact_partition_replay_authorization,
            args.counterfactual_causal_authorization,
            args.out,
        )
    ):
        parser.error(
            "--exact-partition-replay-authorization, "
            "--counterfactual-causal-authorization, and --out are required"
        )
    result = build_authorization(
        _load(args.exact_partition_replay_authorization),
        _load(args.counterfactual_causal_authorization),
    )
    _write(args.out, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "bound_replay_sources": result["bound_replay_source_count"],
                "candidate_count": result["candidate_count"],
                "stand_down_days": result["all_stand_down_days"],
                "fingerprint": result["fingerprint"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
