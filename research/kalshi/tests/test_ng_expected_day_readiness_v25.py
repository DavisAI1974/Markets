from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import ng_corpus_expected_day_contract as gate
import ng_historical_refinement_executor_v21 as executor
import ng_historical_refinement_readiness_v25 as readiness


def _find_corpus(spec: dict, corpus_id: str) -> dict:
    return next(row for row in spec["corpora"] if row["corpus_id"] == corpus_id)


def _drop_expected_day(corpus: dict, day: str) -> None:
    corpus["expected_days"] = [value for value in corpus["expected_days"] if value != day]
    corpus["sources"] = [value for value in corpus["sources"] if value["day"] != day]
    corpus["expected_object_count"] = len(corpus["sources"])


def test_complete_calendar_contract_is_ready() -> None:
    receipt = gate.build_contract(gate._selftest_spec())
    assert receipt["status"] == gate.READY_STATUS
    assert receipt["blockers"] == []
    assert receipt["complete_calendar_partition_attested"] is True
    gate.validate_receipt(receipt)


def test_shortened_expected_day_list_is_visible() -> None:
    spec = gate._selftest_spec()
    corpus = _find_corpus(spec, "l1_dense_one_year")
    _drop_expected_day(corpus, "20250702")
    receipt = gate.build_contract(spec)
    assert receipt["status"] == gate.BLOCKED_STATUS
    assert "l1_dense_one_year:20250702:CALENDAR_DAY_UNCLASSIFIED" in receipt["blockers"]


def test_evidenced_non_saturday_exchange_closure_is_allowed() -> None:
    spec = gate._selftest_spec()
    corpus = _find_corpus(spec, "l1_dense_one_year")
    _drop_expected_day(corpus, "20250704")
    corpus["excluded_days"].append(
        {
            "day": "20250704",
            "reason_code": "EXCHANGE_HOLIDAY_NO_SESSION",
            "evidence_source": "calendar/CME-2025.json",
            "evidence_observed_at": "2026-07-25T00:00:00Z",
            "evidence_sha256": "a" * 64,
        }
    )
    receipt = gate.build_contract(spec)
    assert receipt["status"] == gate.READY_STATUS


def test_non_saturday_exclusion_without_evidence_blocks() -> None:
    spec = gate._selftest_spec()
    corpus = _find_corpus(spec, "l1_dense_one_year")
    _drop_expected_day(corpus, "20250704")
    corpus["excluded_days"].append(
        {"day": "20250704", "reason_code": "EXCHANGE_HOLIDAY_NO_SESSION"}
    )
    receipt = gate.build_contract(spec)
    assert any("EXCLUSION_EVIDENCE" in blocker for blocker in receipt["blockers"])


def test_g15_target_day_cannot_be_excluded() -> None:
    spec = gate._selftest_spec()
    for corpus in spec["corpora"]:
        _drop_expected_day(corpus, "20260316")
        corpus["excluded_days"].append(
            {
                "day": "20260316",
                "reason_code": "EXCHANGE_CLOSURE_NO_SESSION",
                "evidence_source": "calendar/fake.json",
                "evidence_observed_at": "2026-07-25T00:00:00Z",
                "evidence_sha256": "b" * 64,
            }
        )
    receipt = gate.build_contract(spec)
    assert any("TARGET_REPLAY_DAY_EXCLUDED" in blocker for blocker in receipt["blockers"])


def test_source_on_excluded_day_blocks() -> None:
    spec = gate._selftest_spec()
    corpus = _find_corpus(spec, "l1_dense_one_year")
    corpus["expected_days"].remove("20250704")
    corpus["excluded_days"].append(
        {
            "day": "20250704",
            "reason_code": "EXCHANGE_HOLIDAY_NO_SESSION",
            "evidence_source": "calendar/CME-2025.json",
            "evidence_observed_at": "2026-07-25T00:00:00Z",
            "evidence_sha256": "c" * 64,
        }
    )
    receipt = gate.build_contract(spec)
    assert "l1_dense_one_year:20250704:DECLARED_SOURCE_ON_NONEXPECTED_DAY" in receipt["blockers"]


def test_nested_refingerprinted_tampering_is_rejected() -> None:
    receipt = gate.build_contract(gate._selftest_spec())
    tampered = copy.deepcopy(receipt)
    tampered["source_spec"]["corpora"][0]["expected_days"].pop()
    tampered["source_spec_fingerprint"] = gate._fp(tampered["source_spec"])
    payload = copy.deepcopy(tampered)
    payload.pop("receipt_fingerprint", None)
    tampered["receipt_fingerprint"] = gate._fp(payload)
    with pytest.raises(gate.CorpusExpectedDayContractError):
        gate.validate_receipt(tampered)


def test_authority_escalation_is_rejected() -> None:
    receipt = gate.build_contract(gate._selftest_spec())
    tampered = copy.deepcopy(receipt)
    tampered["options_lane_started"] = True
    payload = copy.deepcopy(tampered)
    payload.pop("receipt_fingerprint", None)
    tampered["receipt_fingerprint"] = gate._fp(payload)
    with pytest.raises(gate.CorpusExpectedDayContractError):
        gate.validate_receipt(tampered)


def test_contract_is_deterministic_and_inputs_immutable() -> None:
    spec = gate._selftest_spec()
    before = copy.deepcopy(spec)
    first = gate.build_contract(spec)
    second = gate.build_contract(spec)
    assert first == second
    assert spec == before


def test_readiness_v25_places_contract_first() -> None:
    assert readiness.STAGES[0].key == "corpus_expected_day_contract"
    assert readiness.STAGES[1].key == "corpus_s3_latest_version_resolution"
    assert readiness.LINK_RULES[0] == (
        "corpus_expected_day_contract",
        "source_spec_fingerprint",
        "corpus_s3_latest_version_resolution",
        "source_spec_fingerprint",
    )


def test_missing_contract_blocks_all_downstream_stages(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES[1:]:
        (tmp_path / spec.filename).write_text(
            json.dumps(values[spec.key], sort_keys=True), encoding="utf-8"
        )
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["first_blocking_stage"] == "corpus_expected_day_contract"
    assert report["ready_stages"] == []


def test_executor_v21_exposes_expected_day_entrypoint(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path, tmp_path)
    first = plan["stages"][0]
    assert first["key"] == "corpus_expected_day_contract"
    assert first["suggested_entrypoint"] == [
        "python",
        "ng_corpus_expected_day_contract.py",
        "build",
    ]
    executor.validate_plan(plan)


def test_permanent_authority_wall() -> None:
    receipt = gate.build_contract(gate._selftest_spec())
    assert receipt["actual_outcomes_used"] is False
    assert receipt["paid_live_data_assumed"] is False
    assert receipt["random_shuffle_used"] is False
    assert receipt["blind_forecasts_immutable"] is True
    assert receipt["may_update_ng_brain"] is False
    assert receipt["execution_authority"] is False
    assert receipt["cme_event_contracts_mode"] == "SHADOW"
    assert receipt["brokerage_contract"] == "tastytrade_not_ibkr"
    assert receipt["options_lane_started"] is False
