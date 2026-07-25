from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_corpus_executor_pipeline_arm_v14 as arm
import ng_corpus_executor_plan_compiler_v14 as compiler
import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v14 as executor_v14
import ng_historical_refinement_executor_v15 as executor
import ng_historical_refinement_preflight_v15 as preflight
import ng_historical_refinement_readiness_v19 as readiness


def _commands(tmp_path: Path) -> dict[str, list[str]]:
    return compiler._commands(
        artifact_dir=tmp_path / "artifacts",
        inventory_receipt_path=tmp_path / "inventory.json",
        broad_plan_path=tmp_path / "broad.json",
        slice_bundle_path=tmp_path / "slices.json",
        target_plan_path=tmp_path / "target.json",
    )


def _plan(tmp_path: Path, *, compiled: bool = True):
    commands = _commands(tmp_path)
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    for index, key in enumerate(compiler.CONFIGURED_STAGES):
        plan = executor.configure_stage(
            plan,
            key,
            commands[key],
            enabled=(index == 0 if compiled else True),
        )
    return plan, commands


def _refingerprint(plan):
    value = copy.deepcopy(plan)
    value.pop("fingerprint", None)
    value["fingerprint"] = legacy_executor._fingerprint(value)
    return value


def test_executor_adopts_readiness_v19_and_derivation_entrypoint(tmp_path):
    plan = executor.build_plan(tmp_path / "artifacts", tmp_path)
    keys = [row["key"] for row in plan["stages"]]
    assert keys == [spec.key for spec in readiness.STAGES]
    assert executor.SUGGESTED_ENTRYPOINTS["target_slice_derivation"] == (
        "python",
        "ng_target_slice_derivation_gate_v2.py",
        "build",
    )
    row = next(row for row in plan["stages"] if row["key"] == "target_slice_derivation")
    assert row["requires_fixed_outcomes"] is False


def test_compiler_inserts_plan_bound_derivation_before_basis(tmp_path):
    plan, commands = _plan(tmp_path)
    rows = compiler._validate_plan(plan, commands, compiled=True)
    keys = [row["key"] for row in plan["stages"]]
    assert keys.index("target_slice_broad_lineage") < keys.index("target_slice_derivation")
    assert keys.index("target_slice_derivation") < keys.index("basis_inventory_regeneration")
    assert rows["target_slice_derivation"]["enabled"] is False
    assert commands["target_slice_derivation"][0:3] == [
        "python",
        "ng_target_slice_derivation_gate_v2.py",
        "build",
    ]
    assert "--lineage-gate" in commands["target_slice_derivation"]


def test_compiled_plan_enables_only_broad_inspection(tmp_path):
    plan, commands = _plan(tmp_path)
    compiler._validate_plan(plan, commands, compiled=True)
    enabled = [row["key"] for row in plan["stages"] if row["enabled"]]
    assert enabled == ["corpus_coverage"]


def test_arm_enables_only_plan_bound_corpus_prefix(tmp_path):
    plan, commands = _plan(tmp_path)
    armed = arm._arm(plan, commands)
    rows = {row["key"]: row for row in armed["stages"]}
    assert all(rows[key]["enabled"] is True for key in compiler.CONFIGURED_STAGES)
    assert rows["target_slice_derivation"]["requires_fixed_outcomes"] is False
    assert all(
        rows[spec.key]["enabled"] is False
        for spec in readiness.STAGES[len(compiler.CONFIGURED_STAGES) :]
    )


def test_preflight_accepts_exact_v19_order(tmp_path):
    plan, _ = _plan(tmp_path)
    preflight._check_plan(plan)


def test_preflight_rejects_v17_plan_without_derivation(tmp_path):
    old = executor_v14.build_plan(tmp_path / "artifacts", tmp_path)
    with pytest.raises(Exception):
        preflight._check_plan(old)


def test_removed_derivation_stage_fails_after_refingerprinting(tmp_path):
    plan, commands = _plan(tmp_path)
    tampered = copy.deepcopy(plan)
    tampered["stages"] = [
        row for row in tampered["stages"] if row["key"] != "target_slice_derivation"
    ]
    tampered = _refingerprint(tampered)
    with pytest.raises(Exception):
        compiler._validate_plan(tampered, commands, compiled=True)


def test_premature_derivation_activation_fails_compiled_validation(tmp_path):
    plan, commands = _plan(tmp_path)
    tampered = executor.configure_stage(
        plan,
        "target_slice_derivation",
        commands["target_slice_derivation"],
        enabled=True,
    )
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV14Error):
        compiler._validate_plan(tampered, commands, compiled=True)


def test_post_outcome_derivation_tamper_fails_preflight(tmp_path):
    plan, _ = _plan(tmp_path)
    tampered = copy.deepcopy(plan)
    row = next(
        row for row in tampered["stages"] if row["key"] == "target_slice_derivation"
    )
    row["requires_fixed_outcomes"] = True
    tampered = _refingerprint(tampered)
    with pytest.raises(Exception):
        preflight._check_plan(tampered)


def test_authority_escalation_is_rejected():
    receipt = {
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": True,
    }
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV14Error):
        compiler._authority(receipt, label="test")


def test_plan_generation_is_deterministic(tmp_path):
    first, commands_first = _plan(tmp_path)
    second, commands_second = _plan(tmp_path)
    assert first == second
    assert commands_first == commands_second
    assert first["random_shuffle_used"] is False
    assert first["blind_forecasts_immutable"] is True
    assert first["may_update_ng_brain"] is False
    assert first["execution_authority"] is False
    assert first["cme_event_contracts_mode"] == "SHADOW"
    assert first["brokerage_contract"] == "tastytrade_not_ibkr"
    assert first["options_lane_started"] is False
