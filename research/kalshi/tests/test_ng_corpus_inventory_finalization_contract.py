from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

KALSHI = Path(__file__).resolve().parents[1]
if str(KALSHI) not in sys.path:
    sys.path.insert(0, str(KALSHI))

import ng_corpus_inventory_finalization_contract as gate


def test_ready_contract_binds_product_specific_lags() -> None:
    receipt = gate.build_contract(gate._fixture())
    assert receipt["status"] == gate.READY_STATUS
    assert len(receipt["corpus_finalization_summaries"]) == 2
    assert all(row["inventory_observed_after_product_lag"] for row in receipt["corpus_finalization_summaries"])
    assert receipt["product_specific_lags_required"] is True
    gate.validate_receipt(receipt)


def test_inventory_before_corpus_end_blocks() -> None:
    spec = gate._fixture()
    spec["inventory_observed_at"] = "2026-06-30T23:59:59Z"
    for corpus in spec["corpora"]:
        corpus["inventory_observed_at"] = "2026-06-30T23:59:59Z"
    receipt = gate.build_contract(spec)
    assert receipt["status"] == gate.BLOCKED_STATUS
    assert any("INVENTORY_OBSERVED_BEFORE_CORPUS_END" in blocker for blocker in receipt["blockers"])


def test_inventory_before_product_lag_blocks() -> None:
    spec = gate._fixture()
    spec["inventory_observed_at"] = "2026-07-01T12:00:00Z"
    for corpus in spec["corpora"]:
        corpus["inventory_observed_at"] = "2026-07-01T12:00:00Z"
    receipt = gate.build_contract(spec)
    assert receipt["status"] == gate.BLOCKED_STATUS
    assert any("INVENTORY_OBSERVED_BEFORE_FINALIZATION_LAG" in blocker for blocker in receipt["blockers"])


def test_missing_policy_blocks() -> None:
    spec = gate._fixture()
    spec["corpora"][0].pop("finalization_policy")
    receipt = gate.build_contract(spec)
    assert receipt["status"] == gate.BLOCKED_STATUS
    assert any("FINALIZATION_POLICY_MISSING" in blocker for blocker in receipt["blockers"])


def test_invalid_policy_evidence_sha_blocks() -> None:
    spec = gate._fixture()
    spec["corpora"][1]["finalization_policy"]["evidence_sha256"] = "bad"
    receipt = gate.build_contract(spec)
    assert receipt["status"] == gate.BLOCKED_STATUS
    assert any("FINALIZATION_POLICY_EVIDENCE_SHA256_INVALID" in blocker for blocker in receipt["blockers"])


def test_naive_inventory_timestamp_rejected() -> None:
    spec = gate._fixture()
    spec["inventory_observed_at"] = "2026-07-25T00:00:00"
    with pytest.raises(gate.CorpusInventoryFinalizationError):
        gate.build_contract(spec)


def test_source_observation_before_lag_blocks() -> None:
    spec = gate._fixture()
    spec["corpora"][0]["sources"][0]["inventory_observed_at"] = "2026-07-01T12:00:00Z"
    receipt = gate.build_contract(spec)
    assert receipt["status"] == gate.BLOCKED_STATUS
    assert any("SOURCE_OBSERVED_BEFORE_FINALIZATION_LAG" in blocker for blocker in receipt["blockers"])


def test_source_observation_after_corpus_observation_blocks() -> None:
    spec = gate._fixture()
    spec["corpora"][0]["sources"][0]["inventory_observed_at"] = "2026-07-26T00:00:00Z"
    receipt = gate.build_contract(spec)
    assert receipt["status"] == gate.BLOCKED_STATUS
    assert any("SOURCE_OBSERVATION_AFTER_CORPUS_OBSERVATION" in blocker for blocker in receipt["blockers"])


def test_nested_tampering_rejected_even_when_refingerprinted() -> None:
    receipt = gate.build_contract(gate._fixture())
    receipt["corpus_finalization_summaries"][0]["finalization_lag_seconds"] = 0
    receipt.pop("receipt_fingerprint")
    receipt["receipt_fingerprint"] = gate._fp(receipt)
    with pytest.raises(gate.CorpusInventoryFinalizationError):
        gate.validate_receipt(receipt)


def test_authority_escalation_rejected() -> None:
    spec = gate._fixture()
    spec["may_update_ng_brain"] = True
    with pytest.raises(gate.CorpusInventoryFinalizationError):
        gate.build_contract(spec)


def test_deterministic_and_input_immutable() -> None:
    spec = gate._fixture()
    before = json.dumps(spec, sort_keys=True)
    first = gate.build_contract(spec)
    second = gate.build_contract(spec)
    assert first == second
    assert json.dumps(spec, sort_keys=True) == before
    assert first["blind_forecasts_immutable"] is True
    assert first["cme_event_contracts_mode"] == "SHADOW"
    assert first["brokerage_contract"] == "tastytrade_not_ibkr"
    assert first["options_lane_started"] is False
