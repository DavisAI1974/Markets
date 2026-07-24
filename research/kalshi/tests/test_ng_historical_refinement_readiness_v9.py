from __future__ import annotations

import copy

import pytest

import ng_historical_refinement_readiness_v9 as readiness


def test_stage_order_binds_partition_to_replay_before_window():
    keys = [spec.key for spec in readiness.STAGES]
    assert (
        keys.index("broad_corpus_exact_partition")
        < keys.index("g15_exact_replay")
        < keys.index("g15_exact_partition_replay_authorization")
        < keys.index("g15_exact_replay_window_authorization")
        < keys.index("g15_exact_refinement")
    )


def test_partition_replay_stage_is_pre_outcome_and_exactly_24_lanes():
    spec = next(
        row
        for row in readiness.STAGES
        if row.key == "g15_exact_partition_replay_authorization"
    )
    assert spec.pre_outcome is True
    assert "bound_replay_source_count" in spec.required_fields
    assert "all_g15_replay_sources_bound_to_exact_partition" in spec.required_fields


def test_link_rules_bind_partition_and_replay_fingerprints():
    rules = set(readiness.LINK_RULES)
    assert (
        "broad_corpus_exact_partition",
        "fingerprint",
        "g15_exact_partition_replay_authorization",
        "exact_partition_gate_fingerprint",
    ) in rules
    assert (
        "g15_exact_replay",
        "completion_fingerprint",
        "g15_exact_partition_replay_authorization",
        "exact_replay_completion_fingerprint",
    ) in rules
    assert (
        "g15_exact_replay",
        "replay_fingerprint",
        "g15_exact_partition_replay_authorization",
        "replay_fingerprint",
    ) in rules


def test_missing_partition_replay_authorization_blocks_window_and_refinement(tmp_path):
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    values = readiness._linked_fixture_chain()
    for spec in readiness.STAGES:
        if spec.key == "g15_exact_partition_replay_authorization":
            continue
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=overrides
    )
    assert report["first_blocking_stage"] == (
        "g15_exact_partition_replay_authorization"
    )
    rows = {row["key"]: row for row in report["stages"]}
    assert rows["g15_exact_replay_window_authorization"]["effective_status"] == (
        "BLOCKED_BY_UPSTREAM"
    )
    assert rows["g15_exact_refinement"]["effective_status"] == "BLOCKED_BY_UPSTREAM"


def test_complete_fixture_chain_reports_v9_completion(tmp_path):
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    values = readiness._linked_fixture_chain()
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=overrides
    )
    assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V9"
    assert report["g15_replay_sources_bound_to_exact_partition"] is True


def test_refingerprinted_summary_tampering_is_rejected(tmp_path):
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=overrides
    )
    report["g15_replay_sources_bound_to_exact_partition"] = True
    payload = copy.deepcopy(report)
    payload.pop("fingerprint")
    report["fingerprint"] = readiness._fingerprint(payload)
    with pytest.raises(readiness.HistoricalRefinementReadinessError):
        readiness.validate_readiness_report(report)


def test_permanent_authority_contract_survives_v9(tmp_path):
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=overrides
    )
    assert report["paid_live_data_assumed"] is False
    assert report["random_shuffle_used"] is False
    assert report["blind_forecasts_immutable"] is True
    assert report["may_update_ng_brain"] is False
    assert report["execution_authority"] is False
    assert report["cme_event_contracts_mode"] == "SHADOW"
    assert report["brokerage_contract"] == "tastytrade_not_ibkr"
    assert report["options_lane_started"] is False
