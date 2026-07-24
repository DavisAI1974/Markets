from __future__ import annotations

import copy

import pytest

import ng_g16_exact_partition_replay_authorization as gate
from ng_g16_historical_replay import CANONICAL_DATES, SOURCE_KINDS


def _sources():
    identity = {
        "dataset": "GLBX.MDP3",
        "publisher_id": 1,
        "instrument_id": 996,
        "raw_symbol": "NGK26",
        "definition_date": "2026-03-20",
        "definition_start_s": 1.0,
        "definition_end_s": 2_000_000_000.0,
    }
    partition_days = []
    manifest_entries = []
    replay_states = []
    for day_index, day in enumerate(CANONICAL_DATES):
        lanes = {}
        starts = {}
        ends = {}
        for lane_index, source_kind in enumerate(SOURCE_KINDS):
            start = 1000.0 + day_index * 100.0 + lane_index
            end = start + 60.0
            starts[source_kind] = start
            ends[source_kind] = end
            source_id = f"{day}:{source_kind}"
            source = {
                "source_id": source_id,
                "location": f"/fixture/{source_id}.dbn",
                "sha256": f"{day_index * 2 + lane_index + 1:064x}",
                "size_bytes": 100 + day_index + lane_index,
                "record_count": 10 + day_index + lane_index,
                "event_start_s": start,
                "event_end_s": end,
            }
            lanes[
                "l1_partition" if source_kind == "l1_trades" else "mbo_partition"
            ] = {
                "status": "READY",
                "ordered_sources": [copy.deepcopy(source)],
                "source_partition_fingerprint": f"partition-{source_id}",
            }
            manifest_entries.append(
                {
                    "day": day,
                    "source_kind": source_kind,
                    "status": "PRESENT",
                    "location": source["location"],
                    "sha256": source["sha256"],
                    "size_bytes": source["size_bytes"],
                    "record_count": source["record_count"],
                    "event_start_s": source["event_start_s"],
                    "event_end_s": source["event_end_s"],
                    **identity,
                }
            )
        partition_days.append(
            {
                "day": day,
                "status": "READY",
                "selected_identity": copy.deepcopy(identity),
                **lanes,
            }
        )
        common_start = max(starts.values())
        common_end = min(ends.values())
        replay_states.extend(
            [
                {
                    "session_day": day,
                    "sequence": 1,
                    "decision_cutoff_s": common_start + 1.0,
                    "availability": {"stand_down_reasons": []},
                },
                {
                    "session_day": day,
                    "sequence": 2,
                    "decision_cutoff_s": common_end - 1.0,
                    "availability": {"stand_down_reasons": []},
                },
            ]
        )

    partition = {
        "schema": gate.partition_gate.SCHEMA,
        "status": gate.partition_gate.READY_STATUS,
        "fingerprint": "partition-fingerprint",
        "day_reports": partition_days,
    }
    manifest = {
        "schema": gate.replay_module.MANIFEST_SCHEMA,
        "status": "READY",
        "fingerprint": "manifest-fingerprint",
        "entries": manifest_entries,
    }
    prepared_index = {
        "schema": gate.replay_module.PREPARED_SCHEMA,
        "status": "READY",
        "prepared_corpus_fingerprint": "prepared-fingerprint",
    }
    replay = {
        "schema": gate.replay_module.REPLAY_SCHEMA,
        "status": "READY",
        "fingerprint": "replay-fingerprint",
        "stand_down_days": [],
        "streams": [{"states": replay_states}],
    }
    blind_prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
    prepared_replay = {
        "schema": gate.prepared_gate.SCHEMA,
        "status": gate.prepared_gate.STATUS_READY,
        "fingerprint": "prepared-gate-fingerprint",
        "manifest_fingerprint": manifest["fingerprint"],
        "prepared_corpus_fingerprint": prepared_index[
            "prepared_corpus_fingerprint"
        ],
        "replay_fingerprint": replay["fingerprint"],
        "blind_prior_fingerprint": "blind-prior-fingerprint",
    }
    return partition, prepared_index, manifest, replay, blind_prior, prepared_replay


@pytest.fixture(autouse=True)
def _stub_dependencies(monkeypatch):
    monkeypatch.setattr(gate.partition_gate, "validate_gate", lambda value: value)
    monkeypatch.setattr(
        gate.replay_module,
        "validate_prepared_index",
        lambda value, **kwargs: None,
    )
    monkeypatch.setattr(gate.replay_module, "validate_manifest", lambda value: None)
    monkeypatch.setattr(
        gate.replay_module,
        "validate_replay_output",
        lambda value: None,
    )
    monkeypatch.setattr(
        gate.prepared_gate,
        "validate_gate_artifact",
        lambda value, **kwargs: None,
    )


def _build(values):
    return gate.build_authorization(*values)


def test_binds_all_22_g16_replay_lanes_and_windows():
    values = _sources()
    result = _build(values)
    assert result["status"] == gate.READY
    assert result["bound_replay_source_count"] == 22
    assert result["all_g16_replay_sources_bound_to_exact_partition"] is True
    assert result["all_g16_state_spans_inside_exact_common_windows"] is True
    assert [row["day"] for row in result["day_bindings"]] == list(CANONICAL_DATES)


def test_rejects_manifest_bytes_not_in_partition():
    values = list(_sources())
    values[2]["entries"][0]["sha256"] = "f" * 64
    with pytest.raises(gate.G16ExactPartitionReplayAuthorizationError):
        _build(values)


def test_rejects_ambiguous_partition_match():
    values = list(_sources())
    lane = values[0]["day_reports"][0]["l1_partition"]
    duplicate = copy.deepcopy(lane["ordered_sources"][0])
    duplicate["source_id"] = "duplicate-source"
    lane["ordered_sources"].append(duplicate)
    with pytest.raises(gate.G16ExactPartitionReplayAuthorizationError):
        _build(values)


def test_rejects_partition_source_reuse():
    values = list(_sources())
    reused = values[0]["day_reports"][0]["l1_partition"]["ordered_sources"][0][
        "source_id"
    ]
    values[0]["day_reports"][0]["mbo_partition"]["ordered_sources"][0][
        "source_id"
    ] = reused
    with pytest.raises(gate.G16ExactPartitionReplayAuthorizationError):
        _build(values)


def test_rejects_identity_substitution():
    values = list(_sources())
    values[0]["day_reports"][0]["selected_identity"]["publisher_id"] = 2
    with pytest.raises(gate.G16ExactPartitionReplayAuthorizationError):
        _build(values)


def test_rejects_prepared_replay_lineage_substitution():
    values = list(_sources())
    values[5]["replay_fingerprint"] = "different-replay"
    with pytest.raises(gate.G16ExactPartitionReplayAuthorizationError):
        _build(values)


def test_rejects_state_before_exact_common_window():
    values = list(_sources())
    values[3]["streams"][0]["states"][0]["decision_cutoff_s"] = 0.0
    with pytest.raises(gate.G16ExactPartitionReplayAuthorizationError):
        _build(values)


def test_rejects_state_after_exact_common_window():
    values = list(_sources())
    day = CANONICAL_DATES[-1]
    state = next(
        row
        for row in values[3]["streams"][0]["states"]
        if row["session_day"] == day and row["sequence"] == 2
    )
    state["decision_cutoff_s"] = 9_999_999.0
    with pytest.raises(gate.G16ExactPartitionReplayAuthorizationError):
        _build(values)


def test_rejects_missing_canonical_state_day():
    values = list(_sources())
    missing = CANONICAL_DATES[2]
    values[3]["streams"][0]["states"] = [
        row
        for row in values[3]["streams"][0]["states"]
        if row["session_day"] != missing
    ]
    with pytest.raises(gate.G16ExactPartitionReplayAuthorizationError):
        _build(values)


def test_visible_stand_downs_are_preserved():
    values = list(_sources())
    day = CANONICAL_DATES[3]
    state = next(
        row
        for row in values[3]["streams"][0]["states"]
        if row["session_day"] == day
    )
    state["availability"]["stand_down_reasons"] = ["collector_skipped_records"]
    values[3]["stand_down_days"] = [day]
    result = _build(values)
    assert result["status"] == gate.READY_WITH_STAND_DOWNS
    assert result["stand_down_days"] == [day]


def test_sources_are_immutable_and_output_is_deterministic():
    values = _sources()
    originals = copy.deepcopy(values)
    first = _build(values)
    second = _build(values)
    assert first == second
    assert values == originals


def test_refingerprinted_authority_escalation_is_rejected():
    result = _build(_sources())
    result["options_lane_started"] = True
    payload = copy.deepcopy(result)
    payload.pop("fingerprint")
    result["fingerprint"] = gate._fp(payload)
    with pytest.raises(gate.G16ExactPartitionReplayAuthorizationError):
        gate.validate_authorization(result)


def test_permanent_authority_contract():
    result = _build(_sources())
    assert result["actual_g16_outcomes_used"] is False
    assert result["paid_live_data_assumed"] is False
    assert result["random_shuffle_used"] is False
    assert result["blind_forecasts_immutable"] is True
    assert result["may_change_g16_blind_prior"] is False
    assert result["may_change_posterior"] is False
    assert result["may_update_ng_brain"] is False
    assert result["execution_authority"] is False
    assert result["cme_event_contracts_mode"] == "SHADOW"
    assert result["brokerage_contract"] == "tastytrade_not_ibkr"
    assert result["options_lane_started"] is False
