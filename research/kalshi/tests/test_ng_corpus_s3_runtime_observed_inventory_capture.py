from __future__ import annotations

import copy

import pytest

import ng_corpus_inventory_finalization_contract as finalization
import ng_corpus_s3_paginated_inventory_capture as paginated
import ng_corpus_s3_runtime_observed_inventory_capture as gate


def _evidence():
    spec, final_receipt, materialization, receipt = gate._fixture()
    inventory = receipt["paginated_inventory_receipt"]
    return spec, final_receipt, materialization, inventory, receipt


def _rebuild_for_spec(spec):
    _, _, _, inventory, _ = _evidence()
    final_receipt = finalization.build_contract(spec)
    materialization, capture_receipt = paginated.build_from_paginated_evidence(
        spec,
        captured_pages=inventory["captured_pages"],
        head_responses=inventory["captured_head_objects"],
    )
    return final_receipt, materialization, capture_receipt


def test_fixture_is_ready_and_validates():
    *_, receipt = _evidence()
    assert receipt["status"] == gate.READY_STATUS
    assert gate.validate_receipt(receipt) == receipt


def test_runtime_capture_before_finalization_deadline_blocks():
    spec, final_receipt, materialization, inventory, _ = _evidence()
    receipt = gate.build_from_captured_inventory(
        spec,
        finalization_receipt=final_receipt,
        materialization_spec=materialization,
        paginated_inventory_receipt=inventory,
        capture_started_at="2020-01-01T00:00:00Z",
        capture_completed_at="2020-01-01T00:00:01Z",
        max_declared_clock_skew_seconds=999999999,
    )
    assert receipt["status"] == gate.BLOCKED_STATUS
    assert any(
        blocker.endswith("RUNTIME_CAPTURE_BEFORE_FINALIZATION_DEADLINE")
        for blocker in receipt["blockers"]
    )


def test_declared_observation_outside_runtime_skew_blocks():
    spec, _, _, _, _ = _evidence()
    changed = copy.deepcopy(spec)
    changed["inventory_observed_at"] = "2026-07-24T23:00:00Z"
    for corpus in changed["corpora"]:
        corpus["inventory_observed_at"] = changed["inventory_observed_at"]
    final_receipt, materialization, inventory = _rebuild_for_spec(changed)
    receipt = gate.build_from_captured_inventory(
        changed,
        finalization_receipt=final_receipt,
        materialization_spec=materialization,
        paginated_inventory_receipt=inventory,
        capture_started_at="2026-07-25T00:00:00Z",
        capture_completed_at="2026-07-25T00:00:02Z",
        max_declared_clock_skew_seconds=60,
    )
    assert receipt["status"] == gate.BLOCKED_STATUS
    assert any(
        blocker.endswith("DECLARED_OBSERVATION_OUTSIDE_RUNTIME_CAPTURE_SKEW")
        for blocker in receipt["blockers"]
    )


def test_capture_completion_may_not_precede_start():
    spec, final_receipt, materialization, inventory, _ = _evidence()
    with pytest.raises(gate.RuntimeObservedInventoryCaptureError):
        gate.build_from_captured_inventory(
            spec,
            finalization_receipt=final_receipt,
            materialization_spec=materialization,
            paginated_inventory_receipt=inventory,
            capture_started_at="2026-07-25T00:00:02Z",
            capture_completed_at="2026-07-25T00:00:00Z",
        )


def test_finalization_source_substitution_rejected():
    spec, final_receipt, materialization, inventory, _ = _evidence()
    changed = copy.deepcopy(final_receipt)
    changed["source_spec_fingerprint"] = "0" * 64
    changed.pop("receipt_fingerprint")
    changed["receipt_fingerprint"] = gate._fp(changed)
    with pytest.raises(Exception):
        gate.build_from_captured_inventory(
            spec,
            finalization_receipt=changed,
            materialization_spec=materialization,
            paginated_inventory_receipt=inventory,
            capture_started_at="2026-07-25T00:00:00Z",
            capture_completed_at="2026-07-25T00:00:02Z",
        )


def test_paginated_inventory_substitution_rejected():
    spec, final_receipt, materialization, inventory, _ = _evidence()
    changed = copy.deepcopy(inventory)
    changed["source_spec_fingerprint"] = "0" * 64
    changed.pop("receipt_fingerprint")
    changed["receipt_fingerprint"] = gate._fp(changed)
    with pytest.raises(Exception):
        gate.build_from_captured_inventory(
            spec,
            finalization_receipt=final_receipt,
            materialization_spec=materialization,
            paginated_inventory_receipt=changed,
            capture_started_at="2026-07-25T00:00:00Z",
            capture_completed_at="2026-07-25T00:00:02Z",
        )


def test_refingerprinted_nested_tampering_rejected():
    *_, receipt = _evidence()
    changed = copy.deepcopy(receipt)
    changed["runtime_finalization_checks"][0][
        "runtime_capture_after_finalization_deadline"
    ] = False
    changed["runtime_finalization_checks_fingerprint"] = gate._fp(
        changed["runtime_finalization_checks"]
    )
    changed.pop("receipt_fingerprint")
    changed["receipt_fingerprint"] = gate._fp(changed)
    with pytest.raises(gate.RuntimeObservedInventoryCaptureError):
        gate.validate_receipt(changed)


def test_authority_escalation_rejected():
    *_, receipt = _evidence()
    changed = copy.deepcopy(receipt)
    changed["options_lane_started"] = True
    changed.pop("receipt_fingerprint")
    changed["receipt_fingerprint"] = gate._fp(changed)
    with pytest.raises(gate.RuntimeObservedInventoryCaptureError):
        gate.validate_receipt(changed)


def test_deterministic_reconstruction():
    spec, final_receipt, materialization, inventory, receipt = _evidence()
    rebuilt = gate.build_from_captured_inventory(
        spec,
        finalization_receipt=final_receipt,
        materialization_spec=materialization,
        paginated_inventory_receipt=inventory,
        capture_started_at=receipt["capture_started_at_utc"],
        capture_completed_at=receipt["capture_completed_at_utc"],
        max_declared_clock_skew_seconds=receipt[
            "max_declared_clock_skew_seconds"
        ],
    )
    assert rebuilt == receipt


def test_inputs_are_not_mutated():
    spec, final_receipt, materialization, inventory, _ = _evidence()
    originals = copy.deepcopy((spec, final_receipt, materialization, inventory))
    gate.build_from_captured_inventory(
        spec,
        finalization_receipt=final_receipt,
        materialization_spec=materialization,
        paginated_inventory_receipt=inventory,
        capture_started_at="2026-07-25T00:00:00Z",
        capture_completed_at="2026-07-25T00:00:02Z",
    )
    assert (spec, final_receipt, materialization, inventory) == originals


def test_permanent_controls_are_preserved():
    *_, receipt = _evidence()
    assert receipt["actual_outcomes_used"] is False
    assert receipt["paid_live_data_assumed"] is False
    assert receipt["random_shuffle_used"] is False
    assert receipt["one_signal_authority_preserved"] is True
    assert receipt["blind_forecasts_immutable"] is True
    assert receipt["may_update_ng_brain"] is False
    assert receipt["execution_authority"] is False
    assert receipt["cme_event_contracts_mode"] == "SHADOW"
    assert receipt["brokerage_contract"] == "tastytrade_not_ibkr"
    assert receipt["options_lane_started"] is False
