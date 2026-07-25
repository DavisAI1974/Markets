from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_historical_refinement_executor_v18 as executor_v18
import ng_historical_refinement_executor_v19 as executor
import ng_historical_refinement_readiness_v23 as readiness


def test_executor_uses_paginated_readiness_and_entrypoint() -> None:
    assert readiness.SCHEMA == "ng_historical_refinement_readiness.v23"
    assert executor.SUGGESTED_ENTRYPOINTS["corpus_s3_latest_version_resolution"] == (
        "python",
        "ng_corpus_s3_paginated_latest_version_resolution.py",
        "resolve",
    )


def test_build_plan_binds_paginated_output_and_authority(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    first = plan["stages"][0]
    assert first["key"] == "corpus_s3_latest_version_resolution"
    assert first["expected_output"] == (
        "ng_corpus_s3_paginated_latest_version_resolution_attestation.json"
    )
    assert first["suggested_entrypoint"] == [
        "python",
        "ng_corpus_s3_paginated_latest_version_resolution.py",
        "resolve",
    ]
    assert first["requires_fixed_outcomes"] is False
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


def test_v22_plan_is_rejected_by_executor_v19(tmp_path: Path) -> None:
    legacy_plan = executor_v18.build_plan(tmp_path / "artifacts", tmp_path)
    with pytest.raises(executor.HistoricalRefinementExecutionError):
        executor.validate_plan(legacy_plan)


def test_refingerprinted_legacy_output_is_rejected(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    tampered["stages"][0]["expected_output"] = (
        "ng_corpus_s3_latest_version_resolution_attestation.json"
    )
    tampered.pop("fingerprint", None)
    tampered["fingerprint"] = executor.legacy_executor._fingerprint(tampered)
    with pytest.raises(executor.HistoricalRefinementExecutionError):
        executor.validate_plan(tampered)


def test_refingerprinted_legacy_entrypoint_is_rejected(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    tampered = copy.deepcopy(plan)
    tampered["stages"][0]["suggested_entrypoint"] = [
        "python",
        "ng_corpus_s3_latest_version_resolution.py",
        "resolve",
    ]
    tampered.pop("fingerprint", None)
    tampered["fingerprint"] = executor.legacy_executor._fingerprint(tampered)
    with pytest.raises(executor.HistoricalRefinementExecutionError):
        executor.validate_plan(tampered)


def test_configure_stage_preserves_v23_contract(tmp_path: Path) -> None:
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    configured = executor.configure_stage(
        plan,
        "corpus_s3_latest_version_resolution",
        [
            "python",
            "ng_corpus_s3_paginated_latest_version_resolution.py",
            "resolve",
        ],
    )
    executor.validate_plan(configured)
    assert configured["stages"][0]["enabled"] is True
    assert not any("option" in row["key"].lower() for row in configured["stages"])
