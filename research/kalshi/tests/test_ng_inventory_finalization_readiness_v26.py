from __future__ import annotations

import sys
from pathlib import Path

import pytest

KALSHI = Path(__file__).resolve().parents[1]
if str(KALSHI) not in sys.path:
    sys.path.insert(0, str(KALSHI))

import ng_historical_refinement_executor_v22 as executor
import ng_historical_refinement_readiness as legacy
import ng_historical_refinement_readiness_v26 as readiness


def test_finalization_stage_is_between_expected_days_and_s3_resolution() -> None:
    keys = [spec.key for spec in readiness.STAGES]
    assert keys[:4] == [
        "corpus_expected_day_contract",
        "corpus_inventory_finalization_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
    ]
    assert readiness.STAGES[1].pre_outcome is True
    assert readiness.STAGES[1].filename == "ng_corpus_inventory_finalization_contract.json"


def test_link_rules_bind_one_source_spec_through_front_door() -> None:
    assert readiness.LINK_RULES[:2] == (
        (
            "corpus_expected_day_contract",
            "source_spec_fingerprint",
            "corpus_inventory_finalization_contract",
            "source_spec_fingerprint",
        ),
        (
            "corpus_inventory_finalization_contract",
            "source_spec_fingerprint",
            "corpus_s3_latest_version_resolution",
            "source_spec_fingerprint",
        ),
    )


def test_executor_exposes_operational_finalization_entrypoint() -> None:
    assert executor.SUGGESTED_ENTRYPOINTS["corpus_inventory_finalization_contract"] == (
        "python",
        "ng_corpus_inventory_finalization_contract.py",
        "build",
    )


def test_complete_fixture_chain_reaches_v26_completion(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V26"
    assert report["product_specific_finalization_lags_attested"] is True
    readiness.validate_readiness_report(report)


def test_missing_finalization_blocks_before_resolution(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        if spec.key != "corpus_inventory_finalization_contract":
            readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    assert report["first_blocking_stage"] == "corpus_inventory_finalization_contract"
    resolution_row = next(row for row in report["stages"] if row["key"] == "corpus_s3_latest_version_resolution")
    assert resolution_row["effective_status"] == "BLOCKED_BY_UPSTREAM"


def test_substituted_source_spec_fingerprint_blocks_finalization(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    finalization = values["corpus_inventory_finalization_contract"]
    finalization["source_spec_fingerprint"] = "substituted"
    finalization.pop("receipt_fingerprint")
    finalization["receipt_fingerprint"] = legacy._fingerprint(finalization)
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    row = next(row for row in report["stages"] if row["key"] == "corpus_inventory_finalization_contract")
    assert row["effective_status"] == "INVALID"


def test_refingerprinted_readiness_summary_tampering_rejected(tmp_path: Path) -> None:
    values = readiness._linked_fixture_chain()
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(tmp_path, validator_overrides=overrides)
    report["product_specific_finalization_lags_attested"] = False
    report.pop("fingerprint")
    report["fingerprint"] = legacy._fingerprint(report)
    with pytest.raises(legacy.HistoricalRefinementReadinessError):
        readiness.validate_readiness_report(report)


def test_executor_rejects_removed_finalization_stage(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path, tmp_path)
    plan["stages"] = [
        step for step in plan["stages"]
        if step["key"] != "corpus_inventory_finalization_contract"
    ]
    plan.pop("fingerprint")
    plan["fingerprint"] = legacy._fingerprint(plan)
    with pytest.raises(executor.HistoricalRefinementExecutionError):
        executor.validate_plan(plan)


def test_permanent_authority_wall() -> None:
    plan = executor.build_plan(Path("renders/ng_refine_s95"), Path("."))
    assert plan["random_shuffle_used"] is False
    assert plan["blind_forecasts_immutable"] is True
    assert plan["may_update_ng_brain"] is False
    assert plan["execution_authority"] is False
    assert plan["cme_event_contracts_mode"] == "SHADOW"
    assert plan["brokerage_contract"] == "tastytrade_not_ibkr"
    assert plan["options_lane_started"] is False
    assert not any("option" in step["key"].lower() for step in plan["stages"])
