from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_historical_refinement_executor_v16 as executor_v16
import ng_historical_refinement_executor_v17 as executor
import ng_historical_refinement_readiness_v21 as readiness


def test_inventory_capture_is_first_readiness_stage() -> None:
    keys = [spec.key for spec in readiness.STAGES]
    assert keys[0:3] == [
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
        "corpus_coverage",
    ]
    stage = readiness.STAGES[0]
    assert stage.schema == "ng_corpus_s3_inventory_capture_attestation.v1"
    assert stage.pre_outcome is True
    assert stage.filename == "ng_corpus_s3_inventory_capture_attestation.json"


def test_capture_materialization_spec_is_fingerprint_bound() -> None:
    assert (
        "corpus_s3_inventory_capture",
        "materialization_spec_fingerprint",
        "corpus_s3_materialization",
        "source_spec_fingerprint",
    ) in readiness.LINK_RULES


def test_readiness_selftest_covers_missing_and_complete_capture() -> None:
    assert readiness.selftest() == 0


def test_executor_uses_v21_and_live_capture_entrypoint() -> None:
    plan = executor.build_plan(Path("renders/ng_refine_s95"), Path("."))
    assert [row["key"] for row in plan["stages"]] == [
        spec.key for spec in readiness.STAGES
    ]
    assert executor.SUGGESTED_ENTRYPOINTS["corpus_s3_inventory_capture"] == (
        "python",
        "ng_corpus_s3_inventory_capture.py",
        "capture",
    )
    assert plan["random_shuffle_used"] is False
    assert plan["blind_forecasts_immutable"] is True
    assert plan["may_update_ng_brain"] is False
    assert plan["cme_event_contracts_mode"] == "SHADOW"
    assert plan["brokerage_contract"] == "tastytrade_not_ibkr"
    assert plan["options_lane_started"] is False


def test_executor_rejects_v20_plan_without_capture_stage() -> None:
    legacy_plan = executor_v16.build_plan(Path("renders/ng_refine_s95"), Path("."))
    with pytest.raises(Exception):
        executor.validate_plan(legacy_plan)


def test_executor_rejects_removed_capture_stage_after_refingerprinting() -> None:
    plan = executor.build_plan(Path("renders/ng_refine_s95"), Path("."))
    tampered = copy.deepcopy(plan)
    tampered["stages"] = [
        row
        for row in tampered["stages"]
        if row["key"] != "corpus_s3_inventory_capture"
    ]
    with pytest.raises(Exception):
        executor.validate_plan(tampered)


def test_all_corpus_front_door_stages_remain_pre_outcome() -> None:
    stages = {spec.key: spec for spec in readiness.STAGES}
    for key in (
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
        "corpus_coverage",
        "corpus_definition_byte_binding",
        "target_slice_coverage",
        "target_slice_broad_lineage",
        "target_slice_derivation",
        "basis_inventory_regeneration",
    ):
        assert stages[key].pre_outcome is True


def test_permanent_authority_wall_remains_closed() -> None:
    plan = executor.build_plan(Path("renders/ng_refine_s95"), Path("."))
    assert plan.get("outcome_paths", plan.get("actual_outcome_paths")) == []
    assert plan["paid_live_data_assumed"] is False
    assert plan["random_shuffle_used"] is False
    assert plan["one_signal_authority_preserved"] is True
    assert plan["blind_forecasts_immutable"] is True
    assert plan["may_update_ng_brain"] is False
    assert plan["execution_authority"] is False
    assert plan["cme_event_contracts_mode"] == "SHADOW"
    assert plan["brokerage_contract"] == "tastytrade_not_ibkr"
    assert plan["options_lane_started"] is False
