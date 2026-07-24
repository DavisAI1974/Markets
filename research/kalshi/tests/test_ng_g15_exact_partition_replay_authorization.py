from __future__ import annotations

import copy

import pytest

import ng_g15_exact_partition_replay_authorization as gate
from ng_historical_manifest import G15_DATES, SOURCE_KINDS


def _sources():
    bridge_entries = []
    partition_days = []
    completion_days = []
    for index, day in enumerate(G15_DATES):
        symbol = "NGJ26" if day <= "20260319" else "NGK26"
        instrument_id = 1008 if symbol == "NGJ26" else 996
        identity = {
            "dataset": "GLBX.MDP3",
            "publisher_id": 1,
            "instrument_id": instrument_id,
            "raw_symbol": symbol,
            "definition_date": "2026-03-01" if symbol == "NGJ26" else "2026-03-20",
            "definition_start_s": 1.0,
            "definition_end_s": 2_000_000_000.0,
        }
        lanes = {}
        for lane_index, source_kind in enumerate(SOURCE_KINDS):
            start = 1000.0 + index * 100.0 + lane_index
            end = start + 50.0
            source_id = f"{day}:{source_kind}"
            source = {
                "source_id": source_id,
                "location": f"/fixture/{source_id}.jsonl",
                "sha256": f"{index * 2 + lane_index + 1:064x}",
                "size_bytes": 100 + index + lane_index,
                "record_count": 10 + index + lane_index,
                "event_start_s": start,
                "event_end_s": end,
            }
            lane = {
                "status": "READY",
                "ordered_sources": [copy.deepcopy(source)],
                "source_partition_fingerprint": f"partition-{source_id}",
            }
            lanes["l1_partition" if source_kind == "l1_trades" else "mbo_partition"] = lane
            bridge_entries.append(
                {
                    "day": day,
                    "source_kind": source_kind,
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
                "selected_identity": identity,
                **lanes,
            }
        )
        completion_days.append(
            {
                "date": day,
                "completed_states": 2,
                "first_event_s": 1000.0 + index * 100.0 + 2.0,
                "last_event_s": 1000.0 + index * 100.0 + 40.0,
                "stand_down_reasons": {},
            }
        )

    partition = {
        "schema": "ng_broad_corpus_exact_partition_gate.v1",
        "status": gate.partition_gate.READY_STATUS,
        "fingerprint": "partition-gate-fingerprint",
        "exact_overlap_gate_fingerprint": "overlap-fingerprint",
        "day_reports": partition_days,
    }
    bridge = {
        "schema": "ng_g15_replay_manifest_bridge.v1",
        "status": "READY",
        "fingerprint": "bridge-fingerprint",
        "manifest": {"entries": bridge_entries},
    }
    completion = {
        "schema": "ng_g15_exact_replay_completion.v1",
        "status": gate.replay_completion.READY,
        "completion_fingerprint": "completion-fingerprint",
        "bridge_fingerprint": bridge["fingerprint"],
        "manifest_fingerprint": "manifest-fingerprint",
        "replay_fingerprint": "replay-fingerprint",
        "prepared_corpus_fingerprint": "prepared-fingerprint",
        "days": completion_days,
    }
    return partition, completion, bridge


@pytest.fixture(autouse=True)
def _stub_dependencies(monkeypatch):
    monkeypatch.setattr(gate.partition_gate, "validate_gate", lambda value: value)
    monkeypatch.setattr(gate.replay_bridge, "validate_bridge_output", lambda value: None)
    monkeypatch.setattr(
        gate.replay_completion,
        "validate_completion",
        lambda value, **kwargs: None,
    )


def test_build_binds_all_24_replay_lanes():
    partition, completion, bridge = _sources()
    result = gate.build_authorization(partition, completion, bridge)
    assert result["status"] == gate.READY
    assert result["bound_replay_source_count"] == 24
    assert result["all_g15_replay_sources_bound_to_exact_partition"] is True
    assert [row["day"] for row in result["day_bindings"]] == list(G15_DATES)


def test_rejects_manifest_bytes_not_in_partition():
    partition, completion, bridge = _sources()
    bridge["manifest"]["entries"][0]["sha256"] = "f" * 64
    with pytest.raises(gate.ExactPartitionReplayAuthorizationError):
        gate.build_authorization(partition, completion, bridge)


def test_rejects_ambiguous_partition_match():
    partition, completion, bridge = _sources()
    lane = partition["day_reports"][0]["l1_partition"]
    duplicate = copy.deepcopy(lane["ordered_sources"][0])
    duplicate["source_id"] = "duplicate-source"
    lane["ordered_sources"].append(duplicate)
    with pytest.raises(gate.ExactPartitionReplayAuthorizationError):
        gate.build_authorization(partition, completion, bridge)


def test_rejects_partition_source_reuse():
    partition, completion, bridge = _sources()
    reused = partition["day_reports"][0]["l1_partition"]["ordered_sources"][0]["source_id"]
    partition["day_reports"][0]["mbo_partition"]["ordered_sources"][0]["source_id"] = reused
    with pytest.raises(gate.ExactPartitionReplayAuthorizationError):
        gate.build_authorization(partition, completion, bridge)


def test_rejects_missing_g15_partition_day():
    partition, completion, bridge = _sources()
    partition["day_reports"] = partition["day_reports"][1:]
    with pytest.raises(gate.ExactPartitionReplayAuthorizationError):
        gate.build_authorization(partition, completion, bridge)


def test_rejects_identity_substitution():
    partition, completion, bridge = _sources()
    partition["day_reports"][0]["selected_identity"]["publisher_id"] = 2
    with pytest.raises(gate.ExactPartitionReplayAuthorizationError):
        gate.build_authorization(partition, completion, bridge)


def test_rejects_different_bridge_lineage():
    partition, completion, bridge = _sources()
    completion["bridge_fingerprint"] = "different"
    with pytest.raises(gate.ExactPartitionReplayAuthorizationError):
        gate.build_authorization(partition, completion, bridge)


def test_visible_replay_stand_downs_are_preserved():
    partition, completion, bridge = _sources()
    completion["days"][3]["stand_down_reasons"] = {"collector_skipped_records": 1}
    result = gate.build_authorization(partition, completion, bridge)
    assert result["status"] == gate.READY_WITH_STAND_DOWNS
    assert result["stand_down_days"] == [G15_DATES[3]]


def test_sources_are_not_mutated_and_output_is_deterministic():
    partition, completion, bridge = _sources()
    originals = copy.deepcopy((partition, completion, bridge))
    first = gate.build_authorization(partition, completion, bridge)
    second = gate.build_authorization(partition, completion, bridge)
    assert first == second
    assert (partition, completion, bridge) == originals


def test_refingerprinted_authority_escalation_is_rejected():
    partition, completion, bridge = _sources()
    result = gate.build_authorization(partition, completion, bridge)
    result["options_lane_started"] = True
    payload = copy.deepcopy(result)
    payload.pop("fingerprint")
    result["fingerprint"] = gate._fp(payload)
    with pytest.raises(gate.ExactPartitionReplayAuthorizationError):
        gate.validate_authorization(result)


def test_permanent_authority_contract():
    partition, completion, bridge = _sources()
    result = gate.build_authorization(partition, completion, bridge)
    assert result["actual_outcomes_used"] is False
    assert result["random_shuffle_used"] is False
    assert result["blind_forecasts_immutable"] is True
    assert result["may_update_ng_brain"] is False
    assert result["execution_authority"] is False
    assert result["cme_event_contracts_mode"] == "SHADOW"
    assert result["brokerage_contract"] == "tastytrade_not_ibkr"
    assert result["options_lane_started"] is False
