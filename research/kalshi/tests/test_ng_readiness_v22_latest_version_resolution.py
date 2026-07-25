from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_historical_refinement_executor_v18 as executor
import ng_historical_refinement_readiness_v22 as readiness


def test_readiness_begins_with_latest_version_resolution() -> None:
    assert [spec.key for spec in readiness.STAGES][:3] == [
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
    ]
    assert readiness.STAGES[0].pre_outcome is True


def test_resolution_fingerprint_is_bound_to_capture_spec() -> None:
    assert readiness.LINK_RULES[0] == (
        "corpus_s3_latest_version_resolution",
        "capture_spec_fingerprint",
        "corpus_s3_inventory_capture",
        "source_spec_fingerprint",
    )


def test_missing_artifacts_block_at_resolution(tmp_path: Path) -> None:
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=overrides
    )
    assert report["first_blocking_stage"] == "corpus_s3_latest_version_resolution"
    assert report["status"] == "S3_LATEST_VERSION_RESOLUTION_INCOMPLETE"
    assert report["s3_latest_versions_resolved"] is False


def test_complete_fixture_chain_reaches_v22_completion(tmp_path: Path) -> None:
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    values = readiness._linked_fixture_chain()
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=overrides
    )
    assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V22"
    assert report["s3_latest_versions_resolved"] is True
    assert report["inventory_capture_bound_to_resolved_versions"] is True


def test_substituted_capture_spec_blocks_capture(tmp_path: Path) -> None:
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    values = readiness._linked_fixture_chain()
    capture = copy.deepcopy(values["corpus_s3_inventory_capture"])
    capture["source_spec_fingerprint"] = "substituted"
    capture.pop("receipt_fingerprint", None)
    capture["receipt_fingerprint"] = readiness._fingerprint(capture)
    values["corpus_s3_inventory_capture"] = capture
    for spec in readiness.STAGES:
        readiness._atomic_json(tmp_path / spec.filename, values[spec.key])
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=overrides
    )
    assert "corpus_s3_inventory_capture" not in report["ready_stages"]
    assert report["first_blocking_stage"] == "corpus_s3_inventory_capture"


def test_executor_uses_v22_resolution_entrypoint() -> None:
    assert readiness.SCHEMA == "ng_historical_refinement_readiness.v22"
    assert executor.SUGGESTED_ENTRYPOINTS[
        "corpus_s3_latest_version_resolution"
    ] == (
        "python",
        "ng_corpus_s3_latest_version_resolution.py",
        "resolve",
    )


def test_executor_plan_is_historical_first(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path, tmp_path)
    assert plan["stages"][0]["key"] == "corpus_s3_latest_version_resolution"
    assert plan["outcome_paths"] == []
    assert plan["paid_live_data_assumed"] is False
    assert plan["random_shuffle_used"] is False
    assert plan["one_signal_authority_preserved"] is True
    assert plan["blind_forecasts_immutable"] is True
    assert plan["may_update_ng_brain"] is False
    assert plan["execution_authority"] is False
    assert plan["cme_event_contracts_mode"] == "SHADOW"
    assert plan["brokerage_contract"] == "tastytrade_not_ibkr"
    assert plan["options_lane_started"] is False


def test_refingerprinted_summary_bypass_is_rejected(tmp_path: Path) -> None:
    overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}
    report = readiness.build_readiness_report(
        tmp_path, validator_overrides=overrides
    )
    tampered = copy.deepcopy(report)
    tampered["inventory_capture_bound_to_resolved_versions"] = True
    tampered["fingerprint"] = readiness._fingerprint(
        {key: value for key, value in tampered.items() if key != "fingerprint"}
    )
    with pytest.raises(readiness.HistoricalRefinementReadinessError):
        readiness.validate_readiness_report(tampered)
