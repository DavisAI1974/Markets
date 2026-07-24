from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import ng_historical_refinement_readiness_v10 as readiness


def _write_chain(root: Path, values):
    for spec in readiness.STAGES:
        path = root / spec.filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(values[spec.key], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _overrides():
    return {spec.key: (lambda value: None) for spec in readiness.STAGES}


def test_stage_order_places_g16_partition_binding_before_causal():
    keys = [spec.key for spec in readiness.STAGES]
    assert keys.index("g16_prepared_replay") < keys.index(
        "g16_exact_partition_replay_authorization"
    )
    assert keys.index("g16_exact_partition_replay_authorization") < keys.index(
        "g16_exact_causal"
    )
    spec = next(
        row
        for row in readiness.STAGES
        if row.key == "g16_exact_partition_replay_authorization"
    )
    assert spec.pre_outcome is True


def test_complete_fixture_chain_reaches_v10_status(tmp_path):
    values = readiness._linked_fixture_chain()
    _write_chain(tmp_path, values)
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=_overrides()
    )
    assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V10"
    assert report["g16_replay_sources_bound_to_exact_partition"] is True
    assert report["g16_replay_state_windows_authorized"] is True


def test_missing_g16_partition_binding_blocks_causal(tmp_path):
    values = readiness._linked_fixture_chain()
    values.pop("g16_exact_partition_replay_authorization")
    for spec in readiness.STAGES:
        if spec.key in values:
            path = tmp_path / spec.filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(values[spec.key], indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=_overrides()
    )
    assert (
        report["first_blocking_stage"]
        == "g16_exact_partition_replay_authorization"
    )
    rows = {row["key"]: row for row in report["stages"]}
    assert rows["g16_exact_causal"]["effective_status"] == "BLOCKED_BY_UPSTREAM"
    assert (
        rows["g16_prepared_causal_authorization"]["effective_status"]
        == "BLOCKED_BY_UPSTREAM"
    )


def test_linked_partition_fingerprint_substitution_is_rejected(tmp_path):
    values = readiness._linked_fixture_chain()
    gate = values["g16_exact_partition_replay_authorization"]
    gate["exact_partition_gate_fingerprint"] = "different"
    gate["fingerprint"] = readiness._fingerprint(
        {key: value for key, value in gate.items() if key != "fingerprint"}
    )
    _write_chain(tmp_path, values)
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=_overrides()
    )
    rows = {row["key"]: row for row in report["stages"]}
    assert (
        report["first_blocking_stage"]
        == "g16_exact_partition_replay_authorization"
    )
    assert (
        rows["g16_exact_partition_replay_authorization"]["effective_status"]
        == "INVALID"
    )
    assert rows["g16_exact_causal"]["effective_status"] == "BLOCKED_BY_UPSTREAM"


def test_linked_prepared_replay_substitution_is_rejected(tmp_path):
    values = readiness._linked_fixture_chain()
    gate = values["g16_exact_partition_replay_authorization"]
    gate["prepared_replay_gate_fingerprint"] = "different"
    gate["fingerprint"] = readiness._fingerprint(
        {key: value for key, value in gate.items() if key != "fingerprint"}
    )
    _write_chain(tmp_path, values)
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=_overrides()
    )
    rows = {row["key"]: row for row in report["stages"]}
    assert (
        report["first_blocking_stage"]
        == "g16_exact_partition_replay_authorization"
    )
    assert (
        rows["g16_exact_partition_replay_authorization"]["effective_status"]
        == "INVALID"
    )
    assert rows["g16_exact_causal"]["effective_status"] == "BLOCKED_BY_UPSTREAM"


def test_linked_replay_fingerprint_substitution_is_rejected(tmp_path):
    values = readiness._linked_fixture_chain()
    gate = values["g16_exact_partition_replay_authorization"]
    gate["replay_fingerprint"] = "different"
    gate["fingerprint"] = readiness._fingerprint(
        {key: value for key, value in gate.items() if key != "fingerprint"}
    )
    _write_chain(tmp_path, values)
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=_overrides()
    )
    rows = {row["key"]: row for row in report["stages"]}
    assert (
        report["first_blocking_stage"]
        == "g16_exact_partition_replay_authorization"
    )
    assert (
        rows["g16_exact_partition_replay_authorization"]["effective_status"]
        == "INVALID"
    )
    assert rows["g16_exact_causal"]["effective_status"] == "BLOCKED_BY_UPSTREAM"


def test_v9_report_is_not_a_v10_report():
    report = {
        "schema": "ng_historical_refinement_readiness.v9",
        "fingerprint": "anything",
    }
    with pytest.raises(readiness.HistoricalRefinementReadinessError):
        readiness.validate_readiness_report(report)


def test_refingerprinted_summary_tampering_is_rejected(tmp_path):
    values = readiness._linked_fixture_chain()
    _write_chain(tmp_path, values)
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=_overrides()
    )
    report["g16_replay_state_windows_authorized"] = False
    payload = copy.deepcopy(report)
    payload.pop("fingerprint")
    report["fingerprint"] = readiness._fingerprint(payload)
    with pytest.raises(readiness.HistoricalRefinementReadinessError):
        readiness.validate_readiness_report(report)


def test_permanent_authority_contract(tmp_path):
    values = readiness._linked_fixture_chain()
    _write_chain(tmp_path, values)
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=_overrides()
    )
    assert report["actual_outcome_paths_loaded"] is False
    assert report["paid_live_data_assumed"] is False
    assert report["random_shuffle_used"] is False
    assert report["blind_forecasts_immutable"] is True
    assert report["may_update_ng_brain"] is False
    assert report["execution_authority"] is False
    assert report["cme_event_contracts_mode"] == "SHADOW"
    assert report["brokerage_contract"] == "tastytrade_not_ibkr"
    assert report["options_lane_started"] is False
