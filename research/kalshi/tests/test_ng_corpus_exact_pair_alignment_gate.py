from __future__ import annotations

import copy
from datetime import datetime, timezone

import pytest

import ng_corpus_exact_pair_alignment_gate as alignment


def _ts(day: str, hour: int) -> float:
    return datetime.strptime(day + f" {hour:02d}:00", "%Y%m%d %H:%M").replace(tzinfo=timezone.utc).timestamp()


def _definition(day: str, symbol: str, instrument: int, *, publisher: int = 1, start=None, end=None):
    return {
        "dataset": "GLBX.MDP3",
        "publisher_id": publisher,
        "instrument_id": instrument,
        "raw_symbol": symbol,
        "definition_start_s": _ts("20260101", 0) if start is None else start,
        "definition_end_s": _ts("20260630", 23) if end is None else end,
        "definition_fingerprint": f"def-{symbol}-{instrument}-{publisher}-{start}-{end}",
    }


def _evidence(object_id, day, lane, definition, *, start=None, end=None):
    event_start = _ts(day, 1) if start is None else start
    event_end = _ts(day, 22) if end is None else end
    core = {
        "status": "UNIQUE_DEFINITION_MATCH",
        "record_count": 10,
        "event_start_s": event_start,
        "event_end_s": event_end,
        "datasets": ["GLBX.MDP3"],
        "publisher_ids": [definition["publisher_id"]],
        "instrument_ids": [definition["instrument_id"]],
        "decoded_raw_symbols": [definition["raw_symbol"]],
        "source_schemas": ["MBO" if lane == "mbo" else "TRADES"],
        "transport_metadata": {"dataset": "GLBX.MDP3", "source_schema": lane},
        "event_types": ["mbo" if lane == "mbo" else "trade"],
        "proposed_lane": lane,
        "matching_definition_fingerprints": [definition["definition_fingerprint"]],
        "unique_definition": definition,
        "identity_inferred_from_object_name": False,
    }
    row = {
        "object_id": object_id,
        "location": f"s3://bucket/{object_id}.dbn",
        "quarantine_object_fingerprint": f"q-{object_id}",
        "source_sha256_before": "a" * 64,
        "source_sha256_after": "a" * 64,
        **core,
    }
    row["evidence_fingerprint"] = alignment._fp(core)
    row["probe_object_fingerprint"] = alignment._fp(row)
    return row


def _binding(object_id, day, lane, definition, evidence):
    return {
        "object_id": object_id,
        "location": evidence["location"],
        "review_status": "APPROVED",
        "source_id": f"src-{object_id}",
        "corpus_id": "l1_dense_one_year" if lane == "l1_trades" else "mbo_spring_summer",
        "lane": lane,
        "day": day,
        "definition": copy.deepcopy(definition),
        "probe_evidence_fingerprint": evidence["evidence_fingerprint"],
    }


def _bundle(mutator=None):
    bindings = []
    evidence_rows = []
    for group, (days, contract_map) in alignment.coverage.TARGETS.items():
        for day in days:
            expected = contract_map[day]
            for lane in alignment.coverage.LANES:
                object_id = f"g{group}-{day}-{lane}"
                definition = _definition(day, expected["raw_symbol"], expected["instrument_id"])
                evidence = _evidence(object_id, day, lane, definition)
                binding = _binding(object_id, day, lane, definition, evidence)
                bindings.append(binding)
                evidence_rows.append(evidence)
    if mutator is not None:
        mutator(bindings, evidence_rows)
    manifest = {"bindings": bindings, "corpora": []}
    manifest["binding_manifest_fingerprint"] = alignment._fp(manifest)
    probe = {
        "schema": "ng_corpus_identity_probe.v1",
        "status": "REVIEW_REQUIRED",
        "snapshot_fingerprint": "snapshot",
        "quarantine_fingerprint": "quarantine",
        "definition_fingerprints": sorted({
            row["unique_definition"]["definition_fingerprint"] for row in evidence_rows
        }),
        "probed_object_count": len(evidence_rows),
        "objects": evidence_rows,
        "proposed_binding_manifest_fingerprint": "proposal",
        "automatic_approval_permitted": False,
        "session_day_inferred_from_object_name": False,
        **alignment._authority(),
    }
    probe["probe_fingerprint"] = alignment._fp(probe)
    review_gate = {
        "schema": alignment.review.GATE_SCHEMA,
        "status": "REVIEW_COMPLETE_EXACT_TARGETS_READY_BROAD_UNVERIFIED",
        "reviewed_binding_manifest_fingerprint": manifest["binding_manifest_fingerprint"],
        **alignment._authority(),
    }
    review_gate["review_gate_fingerprint"] = alignment._fp(review_gate)
    snapshot = {"snapshot_fingerprint": "snapshot"}
    return review_gate, manifest, probe, snapshot


def _patch(monkeypatch):
    monkeypatch.setattr(alignment.materialization, "validate_snapshot", lambda value: value)
    monkeypatch.setattr(alignment.materialization, "validate_bindings", lambda value, **kwargs: value)


def test_exact_g15_g16_pairs_are_ready(monkeypatch):
    _patch(monkeypatch)
    review_gate, manifest, probe, snapshot = _bundle()
    result = alignment.build_alignment_gate(
        review_gate=review_gate, reviewed_bindings=manifest, probe=probe, snapshot=snapshot
    )
    assert result["status"] == "G15_G16_EXACT_PAIR_ALIGNMENT_READY"
    assert all(group["status"] == "MATCHED_L1_MBO_READY" for group in result["groups"])


def test_publisher_mismatch_blocks_pair(monkeypatch):
    _patch(monkeypatch)
    def mutate(bindings, evidence):
        binding = next(row for row in bindings if row["day"] == "20260315" and row["lane"] == "mbo")
        event = next(row for row in evidence if row["object_id"] == binding["object_id"])
        binding["definition"]["publisher_id"] = 2
        event["unique_definition"]["publisher_id"] = 2
        event["publisher_ids"] = [2]
        core = {key: event[key] for key in (
            "status", "record_count", "event_start_s", "event_end_s", "datasets", "publisher_ids",
            "instrument_ids", "decoded_raw_symbols", "source_schemas", "transport_metadata",
            "event_types", "proposed_lane", "matching_definition_fingerprints", "unique_definition",
            "identity_inferred_from_object_name",
        )}
        event["evidence_fingerprint"] = alignment._fp(core)
        event.pop("probe_object_fingerprint")
        event["probe_object_fingerprint"] = alignment._fp(event)
        binding["probe_evidence_fingerprint"] = event["evidence_fingerprint"]
    review_gate, manifest, probe, snapshot = _bundle(mutate)
    result = alignment.build_alignment_gate(
        review_gate=review_gate, reviewed_bindings=manifest, probe=probe, snapshot=snapshot
    )
    day = result["groups"][0]["days"][0]
    assert day["pair_blockers"] == ["PUBLISHER_MISMATCH"]
    assert result["status"] == "BLOCKED"


def test_definition_period_mismatch_blocks_pair(monkeypatch):
    _patch(monkeypatch)
    def mutate(bindings, evidence):
        binding = next(row for row in bindings if row["day"] == "20260315" and row["lane"] == "mbo")
        binding["definition"]["definition_start_s"] += 1
        event = next(row for row in evidence if row["object_id"] == binding["object_id"])
        event["unique_definition"]["definition_start_s"] += 1
        core = {key: event[key] for key in (
            "status", "record_count", "event_start_s", "event_end_s", "datasets", "publisher_ids",
            "instrument_ids", "decoded_raw_symbols", "source_schemas", "transport_metadata",
            "event_types", "proposed_lane", "matching_definition_fingerprints", "unique_definition",
            "identity_inferred_from_object_name",
        )}
        event["evidence_fingerprint"] = alignment._fp(core)
        event.pop("probe_object_fingerprint")
        event["probe_object_fingerprint"] = alignment._fp(event)
        binding["probe_evidence_fingerprint"] = event["evidence_fingerprint"]
    review_gate, manifest, probe, snapshot = _bundle(mutate)
    result = alignment.build_alignment_gate(
        review_gate=review_gate, reviewed_bindings=manifest, probe=probe, snapshot=snapshot
    )
    assert "DEFINITION_PERIOD_MISMATCH" in result["groups"][0]["days"][0]["pair_blockers"]


def test_event_time_nonoverlap_blocks_pair(monkeypatch):
    _patch(monkeypatch)
    def mutate(bindings, evidence):
        l1 = next(row for row in evidence if row["object_id"] == "g15-20260315-l1_trades")
        mbo = next(row for row in evidence if row["object_id"] == "g15-20260315-mbo")
        l1["event_end_s"] = _ts("20260315", 5)
        mbo["event_start_s"] = _ts("20260315", 6)
        for event in (l1, mbo):
            core = {key: event[key] for key in (
                "status", "record_count", "event_start_s", "event_end_s", "datasets", "publisher_ids",
                "instrument_ids", "decoded_raw_symbols", "source_schemas", "transport_metadata",
                "event_types", "proposed_lane", "matching_definition_fingerprints", "unique_definition",
                "identity_inferred_from_object_name",
            )}
            event["evidence_fingerprint"] = alignment._fp(core)
            event.pop("probe_object_fingerprint")
            event["probe_object_fingerprint"] = alignment._fp(event)
            binding = next(row for row in bindings if row["object_id"] == event["object_id"])
            binding["probe_evidence_fingerprint"] = event["evidence_fingerprint"]
    review_gate, manifest, probe, snapshot = _bundle(mutate)
    result = alignment.build_alignment_gate(
        review_gate=review_gate, reviewed_bindings=manifest, probe=probe, snapshot=snapshot
    )
    day = result["groups"][0]["days"][0]
    assert day["pair_blockers"] == ["EVENT_TIME_NONOVERLAP"]
    assert day["event_time_overlap"] is None


def test_wrong_basis_is_not_relabelled(monkeypatch):
    _patch(monkeypatch)
    def mutate(bindings, evidence):
        binding = next(row for row in bindings if row["day"] == "20260315" and row["lane"] == "l1_trades")
        binding["definition"]["raw_symbol"] = "NGK26"
        binding["definition"]["instrument_id"] = 996
    review_gate, manifest, probe, snapshot = _bundle(mutate)
    result = alignment.build_alignment_gate(
        review_gate=review_gate, reviewed_bindings=manifest, probe=probe, snapshot=snapshot
    )
    assert result["groups"][0]["days"][0]["lanes"]["l1_trades"]["status"] == "WRONG_BASIS"


def test_duplicate_exact_source_blocks(monkeypatch):
    _patch(monkeypatch)
    def mutate(bindings, evidence):
        original = next(row for row in bindings if row["object_id"] == "g15-20260315-l1_trades")
        original_evidence = next(row for row in evidence if row["object_id"] == original["object_id"])
        duplicate = copy.deepcopy(original)
        duplicate["object_id"] = "duplicate"
        duplicate["source_id"] = "src-duplicate"
        duplicate_evidence = copy.deepcopy(original_evidence)
        duplicate_evidence["object_id"] = "duplicate"
        duplicate_evidence["location"] = "s3://bucket/duplicate.dbn"
        duplicate_evidence.pop("probe_object_fingerprint")
        duplicate_evidence["probe_object_fingerprint"] = alignment._fp(duplicate_evidence)
        duplicate["location"] = duplicate_evidence["location"]
        bindings.append(duplicate)
        evidence.append(duplicate_evidence)
    review_gate, manifest, probe, snapshot = _bundle(mutate)
    result = alignment.build_alignment_gate(
        review_gate=review_gate, reviewed_bindings=manifest, probe=probe, snapshot=snapshot
    )
    assert result["groups"][0]["days"][0]["lanes"]["l1_trades"]["status"] == "DUPLICATE_EXACT_BASIS"


def test_missing_lane_blocks(monkeypatch):
    _patch(monkeypatch)
    def mutate(bindings, evidence):
        bindings[:] = [row for row in bindings if row["object_id"] != "g16-20260410-mbo"]
        evidence[:] = [row for row in evidence if row["object_id"] != "g16-20260410-mbo"]
    review_gate, manifest, probe, snapshot = _bundle(mutate)
    result = alignment.build_alignment_gate(
        review_gate=review_gate, reviewed_bindings=manifest, probe=probe, snapshot=snapshot
    )
    assert result["groups"][1]["days"][-1]["lanes"]["mbo"]["status"] == "MISSING"


def test_binding_probe_provenance_mismatch_is_rejected(monkeypatch):
    _patch(monkeypatch)
    review_gate, manifest, probe, snapshot = _bundle()
    manifest["bindings"][0]["probe_evidence_fingerprint"] = "wrong"
    manifest["binding_manifest_fingerprint"] = alignment._fp({k: v for k, v in manifest.items() if k != "binding_manifest_fingerprint"})
    review_gate["reviewed_binding_manifest_fingerprint"] = manifest["binding_manifest_fingerprint"]
    review_gate.pop("review_gate_fingerprint")
    review_gate["review_gate_fingerprint"] = alignment._fp(review_gate)
    with pytest.raises(alignment.CorpusQuarantineError, match="probe provenance"):
        alignment.build_alignment_gate(
            review_gate=review_gate, reviewed_bindings=manifest, probe=probe, snapshot=snapshot
        )


def test_probe_tampering_is_rejected(monkeypatch):
    _patch(monkeypatch)
    review_gate, manifest, probe, snapshot = _bundle()
    probe["objects"][0]["event_end_s"] += 1
    with pytest.raises(alignment.CorpusQuarantineError, match="probe_fingerprint"):
        alignment.build_alignment_gate(
            review_gate=review_gate, reviewed_bindings=manifest, probe=probe, snapshot=snapshot
        )


def test_refingerprinted_alignment_tampering_is_recomputed(monkeypatch):
    _patch(monkeypatch)
    review_gate, manifest, probe, snapshot = _bundle()
    result = alignment.build_alignment_gate(
        review_gate=review_gate, reviewed_bindings=manifest, probe=probe, snapshot=snapshot
    )
    changed = copy.deepcopy(result)
    changed["groups"][0]["days"][0]["publisher_id"] = 999
    changed.pop("alignment_gate_fingerprint")
    changed["alignment_gate_fingerprint"] = alignment._fp(changed)
    with pytest.raises(alignment.CorpusQuarantineError, match="not reproduced"):
        alignment.validate_alignment_gate(
            changed, review_gate=review_gate, reviewed_bindings=manifest,
            probe=probe, snapshot=snapshot,
        )


def test_authority_and_chronology_controls_remain_disabled(monkeypatch):
    _patch(monkeypatch)
    review_gate, manifest, probe, snapshot = _bundle()
    result = alignment.build_alignment_gate(
        review_gate=review_gate, reviewed_bindings=manifest, probe=probe, snapshot=snapshot
    )
    assert result["random_shuffle_used"] is False
    assert result["actual_outcomes_used"] is False
    assert result["may_update_ng_brain"] is False
    assert result["execution_authority"] is False
    assert result["cme_event_contracts_mode"] == "SHADOW"
    assert result["brokerage_contract"] == "tastytrade_not_ibkr"
    assert result["options_lane_started"] is False
