from __future__ import annotations

import copy
from datetime import datetime, timezone

import pytest

import ng_corpus_binding_review_gate as review


def _ts(day: str, hour: int) -> float:
    return datetime.strptime(day + f" {hour:02d}:00", "%Y%m%d %H:%M").replace(tzinfo=timezone.utc).timestamp()


def _definition(day: str = "20260315", symbol: str = "NGJ26", instrument: int = 1008):
    return {
        "dataset": "GLBX.MDP3",
        "publisher_id": 1,
        "instrument_id": instrument,
        "raw_symbol": symbol,
        "definition_start_s": _ts("20260101", 0),
        "definition_end_s": _ts("20260630", 23),
        "definition_fingerprint": f"def-{symbol}-{instrument}",
    }


def _bundle(*, day="20260315", lane="l1_trades", status="UNIQUE_DEFINITION_MATCH", definition=None, end_day=None):
    definition = definition or _definition(day)
    object_id = "a" * 64
    corpus_id = "l1_dense_one_year" if lane == "l1_trades" else "mbo_spring_summer"
    evidence = {
        "object_id": object_id,
        "location": "s3://bucket/object.dbn",
        "status": status,
        "event_start_s": _ts(day, 1),
        "event_end_s": _ts(end_day or day, 22),
        "proposed_lane": lane,
        "unique_definition": definition if status == "UNIQUE_DEFINITION_MATCH" else None,
        "evidence_fingerprint": "evidence-1",
    }
    probe = {"probe_fingerprint": "probe-1", "objects": [evidence]}
    binding = {
        "object_id": object_id,
        "location": evidence["location"],
        "review_status": "REVIEW_REQUIRED",
        "source_id": f"probe:{object_id}",
        "corpus_id": corpus_id,
        "lane": lane,
        "day": None,
        "definition": definition if status == "UNIQUE_DEFINITION_MATCH" else None,
        "skip_nonmatching": False,
        "probe_status": status,
        "probe_evidence_fingerprint": evidence["evidence_fingerprint"],
        "identity_inferred_from_object_name": False,
    }
    binding["binding_fingerprint"] = review._fp(binding)
    corpora = [
        {
            "corpus_id": "l1_dense_one_year",
            "lane": "l1_trades",
            "expected_days": [],
            "expected_object_count": None,
            "inventory_scope_verified": False,
            "inventory_complete_asserted": False,
            "inventory_observed_at": "2026-07-23T00:00:00Z",
        },
        {
            "corpus_id": "mbo_spring_summer",
            "lane": "mbo",
            "expected_days": [],
            "expected_object_count": None,
            "inventory_scope_verified": False,
            "inventory_complete_asserted": False,
            "inventory_observed_at": "2026-07-23T00:00:00Z",
        },
    ]
    proposal = {
        "binding_manifest_fingerprint": "bindings-1",
        "bindings": [binding],
        "corpora": corpora,
    }
    snapshot = {"snapshot_fingerprint": "snapshot-1", "scope_complete": False}
    gate = {"gate_fingerprint": "gate-1"}
    quarantine = {"quarantine_fingerprint": "quarantine-1"}
    catalog = {"catalog_fingerprint": "catalog-1"}
    return gate, snapshot, quarantine, catalog, probe, proposal


def _patch(monkeypatch):
    monkeypatch.setattr(review.definition_gate, "validate_gate", lambda gate, **kwargs: gate)
    monkeypatch.setattr(review.identity_probe, "validate_probe", lambda probe, **kwargs: probe)
    monkeypatch.setattr(review.materialization, "validate_snapshot", lambda snapshot: snapshot)
    monkeypatch.setattr(review.materialization, "validate_bindings", lambda value, **kwargs: value)
    monkeypatch.setattr(review.inspection, "validate_definition", lambda value: value)


def _completed_decisions(monkeypatch, **kwargs):
    _patch(monkeypatch)
    gate, snapshot, quarantine, catalog, probe, proposal = _bundle(**kwargs)
    decisions = review.review_template(
        gate=gate,
        snapshot=snapshot,
        quarantine=quarantine,
        definition_catalog=catalog,
        probe=probe,
        proposed_bindings=proposal,
    )
    decisions["status"] = "REVIEW_COMPLETE"
    decisions["reviewed_by"] = "operator"
    decisions["reviewed_at"] = "2026-07-23T04:00:00Z"
    row = decisions["decisions"][0]
    row["decision"] = "APPROVED"
    row.pop("decision_fingerprint")
    row["decision_fingerprint"] = review._fp(row)
    decisions.pop("review_decision_fingerprint")
    decisions["review_decision_fingerprint"] = review._fp(decisions)
    return decisions, gate, snapshot, quarantine, catalog, probe, proposal


def test_utc_day_evidence_is_derived_from_event_time():
    assert review._utc_days_for_range(_ts("20260315", 1), _ts("20260315", 22)) == ["20260315"]


def test_multi_day_evidence_requires_split():
    assert review._utc_days_for_range(_ts("20260315", 23), _ts("20260316", 1)) == ["20260315", "20260316"]


def test_template_remains_review_required(monkeypatch):
    _patch(monkeypatch)
    gate, snapshot, quarantine, catalog, probe, proposal = _bundle()
    value = review.review_template(
        gate=gate, snapshot=snapshot, quarantine=quarantine,
        definition_catalog=catalog, probe=probe, proposed_bindings=proposal,
    )
    row = value["decisions"][0]
    assert value["status"] == "REVIEW_REQUIRED"
    assert row["assigned_day"] == "20260315"
    assert row["decision"] == "REVIEW_REQUIRED"
    assert value["session_day_inferred_from_object_name"] is False


def test_unique_identity_can_be_explicitly_approved(monkeypatch):
    decisions, gate, snapshot, quarantine, catalog, probe, proposal = _completed_decisions(monkeypatch)
    artifact, bindings = review.complete_review(
        decisions=decisions, gate=gate, snapshot=snapshot, quarantine=quarantine,
        definition_catalog=catalog, probe=probe, proposed_bindings=proposal,
    )
    assert bindings["bindings"][0]["review_status"] == "APPROVED"
    assert bindings["bindings"][0]["day"] == "20260315"
    assert artifact["status"] == "REVIEW_COMPLETE_TARGETS_BLOCKED"


def test_incomplete_review_is_rejected(monkeypatch):
    _patch(monkeypatch)
    gate, snapshot, quarantine, catalog, probe, proposal = _bundle()
    decisions = review.review_template(
        gate=gate, snapshot=snapshot, quarantine=quarantine,
        definition_catalog=catalog, probe=probe, proposed_bindings=proposal,
    )
    with pytest.raises(review.CorpusQuarantineError, match="incomplete"):
        review.complete_review(
            decisions=decisions, gate=gate, snapshot=snapshot, quarantine=quarantine,
            definition_catalog=catalog, probe=probe, proposed_bindings=proposal,
        )


def test_nonunique_identity_cannot_be_approved(monkeypatch):
    decisions, gate, snapshot, quarantine, catalog, probe, proposal = _completed_decisions(
        monkeypatch, status="AMBIGUOUS_DEFINITION_MATCH"
    )
    with pytest.raises(review.CorpusQuarantineError, match="unique observed definition"):
        review.complete_review(
            decisions=decisions, gate=gate, snapshot=snapshot, quarantine=quarantine,
            definition_catalog=catalog, probe=probe, proposed_bindings=proposal,
        )


def test_multi_day_object_cannot_be_approved(monkeypatch):
    decisions, gate, snapshot, quarantine, catalog, probe, proposal = _completed_decisions(
        monkeypatch, end_day="20260316"
    )
    row = decisions["decisions"][0]
    row["assigned_day"] = "20260315"
    row["source_id"] = review._canonical_source_id("l1_trades", "20260315", row["object_id"])
    row.pop("decision_fingerprint")
    row["decision_fingerprint"] = review._fp(row)
    decisions.pop("review_decision_fingerprint")
    decisions["review_decision_fingerprint"] = review._fp(decisions)
    with pytest.raises(review.CorpusQuarantineError, match="must be split"):
        review.complete_review(
            decisions=decisions, gate=gate, snapshot=snapshot, quarantine=quarantine,
            definition_catalog=catalog, probe=probe, proposed_bindings=proposal,
        )


def test_assigned_day_must_equal_decoded_day(monkeypatch):
    decisions, gate, snapshot, quarantine, catalog, probe, proposal = _completed_decisions(monkeypatch)
    row = decisions["decisions"][0]
    row["assigned_day"] = "20260316"
    row["source_id"] = review._canonical_source_id("l1_trades", "20260316", row["object_id"])
    row.pop("decision_fingerprint")
    row["decision_fingerprint"] = review._fp(row)
    decisions.pop("review_decision_fingerprint")
    decisions["review_decision_fingerprint"] = review._fp(decisions)
    with pytest.raises(review.CorpusQuarantineError, match="decoded event-time"):
        review.complete_review(
            decisions=decisions, gate=gate, snapshot=snapshot, quarantine=quarantine,
            definition_catalog=catalog, probe=probe, proposed_bindings=proposal,
        )


def test_source_id_is_deterministic(monkeypatch):
    decisions, gate, snapshot, quarantine, catalog, probe, proposal = _completed_decisions(monkeypatch)
    row = decisions["decisions"][0]
    row["source_id"] = "operator-picked-id"
    row.pop("decision_fingerprint")
    row["decision_fingerprint"] = review._fp(row)
    decisions.pop("review_decision_fingerprint")
    decisions["review_decision_fingerprint"] = review._fp(decisions)
    with pytest.raises(review.CorpusQuarantineError, match="not canonical"):
        review.complete_review(
            decisions=decisions, gate=gate, snapshot=snapshot, quarantine=quarantine,
            definition_catalog=catalog, probe=probe, proposed_bindings=proposal,
        )


def test_rejected_object_cannot_retain_day(monkeypatch):
    decisions, gate, snapshot, quarantine, catalog, probe, proposal = _completed_decisions(monkeypatch)
    row = decisions["decisions"][0]
    row["decision"] = "REJECTED"
    row.pop("decision_fingerprint")
    row["decision_fingerprint"] = review._fp(row)
    decisions.pop("review_decision_fingerprint")
    decisions["review_decision_fingerprint"] = review._fp(decisions)
    with pytest.raises(review.CorpusQuarantineError, match="may not retain"):
        review.complete_review(
            decisions=decisions, gate=gate, snapshot=snapshot, quarantine=quarantine,
            definition_catalog=catalog, probe=probe, proposed_bindings=proposal,
        )


def _approved(day, lane, symbol, instrument, suffix):
    return {
        "review_status": "APPROVED",
        "source_id": f"src-{suffix}",
        "corpus_id": "l1_dense_one_year" if lane == "l1_trades" else "mbo_spring_summer",
        "lane": lane,
        "day": day,
        "definition": _definition(day, symbol, instrument),
    }


def test_wrong_basis_is_visible_not_relabelled():
    reviewed = {
        "bindings": [
            _approved("20260315", "l1_trades", "NGK26", 996, "wrong"),
            _approved("20260315", "mbo", "NGJ26", 1008, "mbo"),
        ]
    }
    group = review._target_coverage(reviewed)["groups"][0]
    day = next(row for row in group["days"] if row["day"] == "20260315")
    assert day["lanes"]["l1_trades"]["status"] == "WRONG_BASIS"
    assert day["status"] == "BLOCKED"


def test_duplicate_exact_lane_is_visible():
    reviewed = {
        "bindings": [
            _approved("20260315", "l1_trades", "NGJ26", 1008, "a"),
            _approved("20260315", "l1_trades", "NGJ26", 1008, "b"),
            _approved("20260315", "mbo", "NGJ26", 1008, "m"),
        ]
    }
    day = review._target_coverage(reviewed)["groups"][0]["days"][0]
    assert day["lanes"]["l1_trades"]["status"] == "DUPLICATE_EXACT_BASIS"


def test_broad_complete_claim_requires_exact_days_and_count(monkeypatch):
    monkeypatch.setattr(review.materialization, "checked_snapshot_scope", lambda snapshot, control: True)
    reviewed = {
        "bindings": [_approved("20260315", "l1_trades", "NGJ26", 1008, "a")],
        "corpora": [
            {
                "corpus_id": "l1_dense_one_year",
                "expected_days": ["20260315", "20260316"],
                "expected_object_count": 1,
                "inventory_complete_asserted": True,
            }
        ],
    }
    with pytest.raises(review.CorpusQuarantineError, match="approved days"):
        review._broad_coverage(reviewed, {"scope_complete": True})


def test_refingerprinted_gate_tampering_is_recomputed(monkeypatch):
    decisions, gate, snapshot, quarantine, catalog, probe, proposal = _completed_decisions(monkeypatch)
    artifact, bindings = review.complete_review(
        decisions=decisions, gate=gate, snapshot=snapshot, quarantine=quarantine,
        definition_catalog=catalog, probe=probe, proposed_bindings=proposal,
    )
    changed = copy.deepcopy(artifact)
    changed["exact_targets"][0]["status"] = "MATCHED_L1_MBO_READY"
    changed.pop("review_gate_fingerprint")
    changed["review_gate_fingerprint"] = review._fp(changed)
    with pytest.raises(review.CorpusQuarantineError, match="coverage was not reproduced"):
        review.validate_completed_review(
            changed, decisions=decisions, reviewed_bindings=bindings, gate=gate, snapshot=snapshot
        )


def test_authority_is_permanently_disabled():
    authority = review._authority()
    assert authority["actual_outcomes_used"] is False
    assert authority["may_update_ng_brain"] is False
    assert authority["execution_authority"] is False
    assert authority["cme_event_contracts_mode"] == "SHADOW"
    assert authority["brokerage_contract"] == "tastytrade_not_ibkr"
    assert authority["options_lane_started"] is False
