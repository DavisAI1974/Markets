from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

import ng_historical_refinement_executor_v19 as executor_v19
import ng_historical_refinement_executor_v20 as executor
import ng_historical_refinement_readiness_v24 as readiness


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _overrides() -> dict[str, Any]:
    return {spec.key: (lambda value: None) for spec in readiness.STAGES}


def _materialize(root: Path) -> dict[str, dict[str, Any]]:
    values = readiness._linked_fixture_chain()
    for spec in readiness.STAGES:
        _write(root / spec.filename, values[spec.key])
    return values


def test_paginated_inventory_replaces_legacy_second_stage() -> None:
    stage = readiness.STAGES[1]
    assert stage.key == "corpus_s3_inventory_capture"
    assert stage.filename == "ng_corpus_s3_paginated_inventory_capture_attestation.json"
    assert stage.schema == "ng_corpus_s3_paginated_inventory_capture_attestation.v1"
    assert stage.ready_statuses == frozenset(
        {"S3_PAGINATED_INVENTORY_CAPTURED_READY_FOR_MATERIALIZATION"}
    )
    assert stage.pre_outcome is True


def test_complete_fixture_chain_reaches_v24(tmp_path: Path) -> None:
    _materialize(tmp_path)
    report = readiness.build_readiness_report(tmp_path, validator_overrides=_overrides())
    assert report["status"] == "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V24"
    assert report["inventory_service_pagination_attested"] is True
    assert report["checksum_enabled_head_inventory_bound"] is True
    assert report["legacy_single_page_inventory_capture_rejected"] is True
    readiness.validate_readiness_report(report)


def test_missing_paginated_inventory_blocks_materialization(tmp_path: Path) -> None:
    _materialize(tmp_path)
    (tmp_path / readiness.STAGES[1].filename).unlink()
    report = readiness.build_readiness_report(tmp_path, validator_overrides=_overrides())
    assert report["first_blocking_stage"] == "corpus_s3_inventory_capture"
    assert report["inventory_service_pagination_attested"] is False
    assert "corpus_s3_materialization" not in report["ready_stages"]


def test_legacy_inventory_artifact_name_cannot_satisfy_v24(tmp_path: Path) -> None:
    values = _materialize(tmp_path)
    paginated_path = tmp_path / readiness.STAGES[1].filename
    paginated_path.unlink()
    _write(
        tmp_path / "ng_corpus_s3_inventory_capture_attestation.json",
        values["corpus_s3_inventory_capture"],
    )
    report = readiness.build_readiness_report(tmp_path, validator_overrides=_overrides())
    assert report["first_blocking_stage"] == "corpus_s3_inventory_capture"


def test_materialization_link_substitution_blocks_downstream(tmp_path: Path) -> None:
    values = _materialize(tmp_path)
    capture = copy.deepcopy(values["corpus_s3_inventory_capture"])
    capture["materialization_spec_fingerprint"] = "substituted"
    capture.pop("receipt_fingerprint", None)
    capture["receipt_fingerprint"] = readiness._fingerprint(capture)
    _write(tmp_path / readiness.STAGES[1].filename, capture)
    report = readiness.build_readiness_report(tmp_path, validator_overrides=_overrides())
    assert report["first_blocking_stage"] == "corpus_s3_materialization"
    assert "corpus_s3_inventory_capture" in report["ready_stages"]
    assert "corpus_s3_materialization" not in report["ready_stages"]


def test_summary_tampering_fails_after_refingerprint(tmp_path: Path) -> None:
    _materialize(tmp_path)
    report = readiness.build_readiness_report(tmp_path, validator_overrides=_overrides())
    tampered = copy.deepcopy(report)
    tampered["legacy_single_page_inventory_capture_rejected"] = False
    tampered.pop("fingerprint", None)
    tampered["fingerprint"] = readiness._fingerprint(tampered)
    with pytest.raises(readiness.HistoricalRefinementReadinessError):
        readiness.validate_readiness_report(tampered)


def test_executor_uses_v24_inventory_entrypoint() -> None:
    assert readiness.SCHEMA == "ng_historical_refinement_readiness.v24"
    assert executor.SUGGESTED_ENTRYPOINTS["corpus_s3_inventory_capture"] == (
        "python",
        "ng_corpus_s3_paginated_inventory_capture.py",
        "capture",
    )


def test_build_plan_binds_paginated_inventory_output_and_authority(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    first, second = plan["stages"][:2]
    assert first["expected_output"] == (
        "ng_corpus_s3_paginated_latest_version_resolution_attestation.json"
    )
    assert second["expected_output"] == (
        "ng_corpus_s3_paginated_inventory_capture_attestation.json"
    )
    assert second["suggested_entrypoint"] == [
        "python",
        "ng_corpus_s3_paginated_inventory_capture.py",
        "capture",
    ]
    assert first["requires_fixed_outcomes"] is False
    assert second["requires_fixed_outcomes"] is False
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


def test_v23_plan_is_rejected_by_executor_v20(tmp_path: Path) -> None:
    legacy_plan = executor_v19.build_plan(tmp_path / "artifacts", tmp_path)
    with pytest.raises(executor.HistoricalRefinementExecutionError):
        executor.validate_plan(legacy_plan)


def test_refingerprinted_legacy_inventory_output_is_rejected(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    tampered["stages"][1]["expected_output"] = (
        "ng_corpus_s3_inventory_capture_attestation.json"
    )
    tampered.pop("fingerprint", None)
    tampered["fingerprint"] = executor.legacy_executor._fingerprint(tampered)
    with pytest.raises(executor.HistoricalRefinementExecutionError):
        executor.validate_plan(tampered)


def test_permanent_authority_wall_is_preserved(tmp_path: Path) -> None:
    _materialize(tmp_path)
    report = readiness.build_readiness_report(tmp_path, validator_overrides=_overrides())
    assert report["paid_live_data_assumed"] is False
    assert report["random_shuffle_used"] is False
    assert report["one_signal_authority_preserved"] is True
    assert report["blind_forecasts_immutable"] is True
    assert report["may_update_ng_brain"] is False
    assert report["execution_authority"] is False
    assert report["cme_event_contracts_mode"] == "SHADOW"
    assert report["brokerage_contract"] == "tastytrade_not_ibkr"
    assert report["options_lane_started"] is False
