from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_corpus_executor_pipeline_arm_v23 as arm
import ng_corpus_executor_plan_compiler_v23 as compiler
import ng_historical_refinement_executor_v24 as executor
import ng_historical_refinement_preflight_v24 as preflight
import ng_historical_refinement_readiness_v28 as readiness


def _rows(*, enabled_first: bool = True) -> tuple[dict, dict[str, list[str]]]:
    commands = {key: ["python", f"{key}.py"] for key in compiler.CONFIGURED_STAGES}
    commands["corpus_expected_day_contract"] = [
        "python",
        "ng_corpus_expected_day_contract.py",
        "build",
    ]
    commands["corpus_inventory_finalization_contract"] = [
        "python",
        "ng_corpus_inventory_finalization_contract.py",
        "build",
    ]
    commands["corpus_s3_inventory_capture"] = [
        "python",
        "ng_corpus_s3_runtime_observed_inventory_capture.py",
        "capture",
    ]
    commands["corpus_s3_materialization"] = [
        "python",
        "ng_corpus_s3_exact_materializer.py",
        "materialize",
    ]
    stages = []
    for index, spec in enumerate(readiness.STAGES):
        stages.append(
            {
                "key": spec.key,
                "argv": commands.get(spec.key, []),
                "enabled": enabled_first and index == 0,
                "requires_fixed_outcomes": not spec.pre_outcome,
                "expected_output": spec.filename,
                "suggested_entrypoint": list(executor.SUGGESTED_ENTRYPOINTS.get(spec.key, ())),
            }
        )
    return {"stages": stages, "outcome_paths": []}, commands


def _runtime_receipt() -> dict:
    return {"receipt_fingerprint": "r" * 64}


def _exact_receipt() -> dict:
    return {
        "status": compiler.exact_materializer.READY_STATUS,
        "blockers": [],
        "exact_version_get_object_required": True,
        "checksum_mode_enabled": True,
        "atomic_local_replacement_required": True,
        "identity_from_s3_keys_inferred": False,
        "runtime_inventory_capture_fingerprint": "r" * 64,
        "source_spec": {"materialize": True},
        "source_spec_fingerprint": compiler.exact_materializer._fp({"materialize": True}),
        "source_materializations_fingerprint": "s" * 64,
        "source_count": 2,
        "downstream_materialization_receipt": {"nested": True},
        "downstream_materialization_receipt_fingerprint": "m" * 64,
        "receipt_fingerprint": "e" * 64,
    }


def test_stage_prefix_uses_exact_materialization() -> None:
    assert compiler.CONFIGURED_STAGES[:6] == (
        "corpus_expected_day_contract",
        "corpus_inventory_finalization_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
        "corpus_coverage",
    )
    assert readiness.STAGES[4].filename == "ng_corpus_s3_exact_materializer_receipt.json"
    assert readiness.STAGES[4].pre_outcome is True


def test_exact_materialization_command_binds_runtime_and_all_outputs(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        compiler.v22,
        "_commands",
        lambda **kwargs: {key: ["python", f"{key}.py"] for key in compiler.CONFIGURED_STAGES},
    )
    commands = compiler._commands(
        artifact_dir=tmp_path,
        resolution_spec_path=tmp_path / "resolution.json",
        expected_day_receipt_path=tmp_path / "expected-day.json",
        finalization_receipt_path=tmp_path / "finalization.json",
        resolution_receipt_path=tmp_path / "resolution-receipt.json",
        capture_spec_path=tmp_path / "capture.json",
        capture_receipt_path=tmp_path / "runtime-receipt.json",
        materialization_spec_path=tmp_path / "materialization.json",
        materialization_receipt_path=tmp_path / "exact-receipt.json",
        inventory_receipt_path=tmp_path / "inventory-receipt.json",
        broad_plan_path=tmp_path / "broad-plan.json",
        slice_bundle_path=tmp_path / "slice.json",
        target_plan_path=tmp_path / "target.json",
    )
    argv = commands["corpus_s3_materialization"]
    assert argv[:3] == ["python", "ng_corpus_s3_exact_materializer.py", "materialize"]
    assert argv[argv.index("--runtime-capture") + 1].endswith("runtime-receipt.json")
    assert argv[argv.index("--receipt-out") + 1].endswith("exact-receipt.json")
    assert argv[argv.index("--plan-out") + 1].endswith("broad-plan.json")
    assert argv[argv.index("--inventory-receipt-out") + 1].endswith("inventory-receipt.json")


def test_exact_materialization_validation_accepts_bound_evidence(monkeypatch) -> None:
    receipt = _exact_receipt()
    monkeypatch.setattr(
        compiler.exact_materializer,
        "validate_receipt",
        lambda value: copy.deepcopy(receipt),
    )
    checked = compiler._validate_exact_materialization(
        runtime_receipt=_runtime_receipt(),
        materialization_spec={"materialize": True},
        materialization_receipt=receipt,
    )
    assert checked["receipt_fingerprint"] == "e" * 64


def test_exact_materialization_validation_rejects_runtime_substitution(monkeypatch) -> None:
    receipt = _exact_receipt()
    monkeypatch.setattr(
        compiler.exact_materializer,
        "validate_receipt",
        lambda value: copy.deepcopy(receipt),
    )
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV23Error):
        compiler._validate_exact_materialization(
            runtime_receipt={"receipt_fingerprint": "x" * 64},
            materialization_spec={"materialize": True},
            materialization_receipt=receipt,
        )


def test_exact_materialization_validation_rejects_blockers(monkeypatch) -> None:
    receipt = _exact_receipt()
    receipt["blockers"] = ["DOWNLOADED_SHA256_MISMATCH"]
    monkeypatch.setattr(
        compiler.exact_materializer,
        "validate_receipt",
        lambda value: copy.deepcopy(receipt),
    )
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV23Error):
        compiler._validate_exact_materialization(
            runtime_receipt=_runtime_receipt(),
            materialization_spec={"materialize": True},
            materialization_receipt=receipt,
        )


def test_compiled_plan_enables_only_expected_day_contract(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    monkeypatch.setattr(
        compiler.v22,
        "_validate_plan",
        lambda value, command_map, compiled: {row["key"]: row for row in value["stages"]},
    )
    rows = compiler._validate_plan(plan, commands, compiled=True)
    assert rows["corpus_expected_day_contract"]["enabled"] is True
    assert rows["corpus_s3_inventory_capture"]["enabled"] is False
    assert rows["corpus_s3_materialization"]["enabled"] is False
    assert rows["corpus_coverage"]["enabled"] is False


def test_plan_rejects_legacy_validation_only_materialization(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    plan["stages"][4]["expected_output"] = "ng_corpus_s3_materialization_attestation.json"
    monkeypatch.setattr(
        compiler.v22,
        "_validate_plan",
        lambda value, command_map, compiled: {row["key"]: row for row in value["stages"]},
    )
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV23Error):
        compiler._validate_plan(plan, commands, compiled=True)


def test_plan_rejects_materializer_entrypoint_substitution(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    plan["stages"][4]["suggested_entrypoint"] = [
        "python",
        "ng_corpus_s3_materialization_stage.py",
    ]
    monkeypatch.setattr(
        compiler.v22,
        "_validate_plan",
        lambda value, command_map, compiled: {row["key"]: row for row in value["stages"]},
    )
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV23Error):
        compiler._validate_plan(plan, commands, compiled=True)


def test_arm_stage_set_matches_exact_materialization_prefix() -> None:
    assert arm.ARMED_STAGES == compiler.CONFIGURED_STAGES
    assert "corpus_s3_materialization" in arm.ARMED_STAGES
    assert "g15_exact_replay" not in arm.ARMED_STAGES


def test_preflight_accepts_exact_materialization_order(monkeypatch) -> None:
    plan, _ = _rows(enabled_first=True)
    plan["fingerprint"] = "plan"
    monkeypatch.setattr(preflight.executor, "validate_plan", lambda value: None)
    preflight._check_plan(plan)


def test_preflight_rejects_removed_exact_materialization(monkeypatch) -> None:
    plan, _ = _rows(enabled_first=True)
    plan["stages"] = [
        row for row in plan["stages"] if row["key"] != "corpus_s3_materialization"
    ]
    monkeypatch.setattr(preflight.executor, "validate_plan", lambda value: None)
    with pytest.raises(preflight.HistoricalRefinementPreflightV24Error):
        preflight._check_plan(plan)


def test_executor_uses_readiness_v28_materializer_entrypoint() -> None:
    assert readiness.SCHEMA == "ng_historical_refinement_readiness.v28"
    assert executor.SUGGESTED_ENTRYPOINTS["corpus_s3_materialization"] == (
        "python",
        "ng_corpus_s3_exact_materializer.py",
        "materialize",
    )


def test_authority_wall_and_no_options_stage() -> None:
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
        "options_lane_started": False,
    }
    compiler._authority(receipt, label="test")
    tampered = copy.deepcopy(receipt)
    tampered["options_lane_started"] = True
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV23Error):
        compiler._authority(tampered, label="test")
    assert not any("option" in key.lower() for key in compiler.CONFIGURED_STAGES)
    by_key = {spec.key: spec for spec in readiness.STAGES}
    assert all(by_key[key].pre_outcome for key in compiler.CONFIGURED_STAGES)
