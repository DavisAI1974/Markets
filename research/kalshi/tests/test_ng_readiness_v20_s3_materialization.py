from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_corpus_executor_pipeline_arm_v15 as arm
import ng_corpus_executor_plan_compiler_v15 as compiler
import ng_historical_refinement_executor_v16 as executor
import ng_historical_refinement_preflight_v16 as preflight
import ng_historical_refinement_readiness_v20 as readiness


def test_materialization_is_first_readiness_stage() -> None:
    keys = [spec.key for spec in readiness.STAGES]
    assert keys[0] == "corpus_s3_materialization"
    assert keys.index("corpus_s3_materialization") < keys.index("corpus_coverage")
    assert keys.index("corpus_coverage") < keys.index("corpus_definition_byte_binding")
    stage = readiness.STAGES[0]
    assert stage.schema == "ng_corpus_s3_materialization_attestation.v1"
    assert stage.pre_outcome is True


def test_materialization_links_plan_and_inventory_receipt_into_byte_binding() -> None:
    assert (
        "corpus_s3_materialization",
        "plan_fingerprint",
        "corpus_definition_byte_binding",
        "plan_fingerprint",
    ) in readiness.LINK_RULES
    assert (
        "corpus_s3_materialization",
        "inventory_compiler_receipt_fingerprint",
        "corpus_definition_byte_binding",
        "inventory_compiler_receipt_fingerprint",
    ) in readiness.LINK_RULES


def test_readiness_selftest_covers_missing_and_complete_materialization() -> None:
    assert readiness.selftest() == 0


def test_executor_uses_v20_and_operational_materialization_wrapper() -> None:
    plan = executor.build_plan(Path("renders/ng_refine_s95"), Path("."))
    assert [row["key"] for row in plan["stages"]] == [spec.key for spec in readiness.STAGES]
    assert executor.SUGGESTED_ENTRYPOINTS["corpus_s3_materialization"] == (
        "python",
        "ng_corpus_s3_materialization_stage.py",
    )
    assert plan["random_shuffle_used"] is False
    assert plan["blind_forecasts_immutable"] is True
    assert plan["may_update_ng_brain"] is False
    assert plan["cme_event_contracts_mode"] == "SHADOW"
    assert plan["brokerage_contract"] == "tastytrade_not_ibkr"
    assert plan["options_lane_started"] is False


def test_compiler_prefix_starts_with_materialization() -> None:
    assert compiler.CONFIGURED_STAGES[0:4] == (
        "corpus_s3_materialization",
        "corpus_coverage",
        "corpus_definition_byte_binding",
        "target_slice_coverage",
    )
    assert arm.ARMED_STAGES == compiler.CONFIGURED_STAGES


def test_materialization_command_writes_standalone_inventory_receipt(tmp_path: Path) -> None:
    commands = compiler._commands(
        artifact_dir=tmp_path / "artifacts",
        materialization_spec_path=tmp_path / "s3_spec.json",
        materialization_receipt_path=tmp_path / "materialization.json",
        inventory_receipt_path=tmp_path / "inventory_receipt.json",
        broad_plan_path=tmp_path / "broad_plan.json",
        slice_bundle_path=tmp_path / "slices.json",
        target_plan_path=tmp_path / "target_plan.json",
    )
    argv = commands["corpus_s3_materialization"]
    assert argv[:2] == ["python", "ng_corpus_s3_materialization_stage.py"]
    assert "--inventory-receipt-out" in argv
    assert argv.index("--inventory-receipt-out") < argv.index("--receipt-out")


def test_preflight_contract_requires_materialization_before_inspection() -> None:
    assert preflight.READINESS_CONTRACT == "ng_historical_refinement_readiness.v20"
    assert preflight.EXECUTOR_CONTRACT == "ng_historical_refinement_executor_v16"
    plan = executor.build_plan(Path("renders/ng_refine_s95"), Path("."))
    preflight._check_plan(plan)


def test_preflight_rejects_removed_materialization_stage() -> None:
    plan = executor.build_plan(Path("renders/ng_refine_s95"), Path("."))
    tampered = copy.deepcopy(plan)
    tampered["stages"] = [
        row for row in tampered["stages"] if row["key"] != "corpus_s3_materialization"
    ]
    with pytest.raises(Exception):
        preflight._check_plan(tampered)


def test_compiler_rejects_post_outcome_materialization() -> None:
    plan = executor.build_plan(Path("renders/ng_refine_s95"), Path("."))
    commands = {key: ["python", f"{key}.py"] for key in compiler.CONFIGURED_STAGES}
    configured = plan
    for index, key in enumerate(compiler.CONFIGURED_STAGES):
        configured = executor.configure_stage(
            configured, key, commands[key], enabled=index == 0
        )
    rows = configured["stages"]
    target = next(row for row in rows if row["key"] == "corpus_s3_materialization")
    target["requires_fixed_outcomes"] = True
    with pytest.raises(Exception):
        compiler._validate_plan(configured, commands, compiled=True)


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
