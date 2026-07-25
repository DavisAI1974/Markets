from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_corpus_executor_pipeline_arm_v20 as arm
import ng_corpus_executor_plan_compiler_v20 as compiler
import ng_historical_refinement_executor_v21 as executor
import ng_historical_refinement_preflight_v21 as preflight
import ng_historical_refinement_readiness_v25 as readiness


def _rows(*, enabled_first: bool = True) -> tuple[dict, dict[str, list[str]]]:
    commands = {key: ["python", f"{key}.py"] for key in compiler.CONFIGURED_STAGES}
    commands["corpus_expected_day_contract"] = [
        "python",
        "ng_corpus_expected_day_contract.py",
        "build",
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
                "suggested_entrypoint": list(
                    executor.SUGGESTED_ENTRYPOINTS.get(spec.key, ())
                ),
            }
        )
    return {"stages": stages, "outcome_paths": []}, commands


def test_stage_prefix_begins_with_expected_day_contract() -> None:
    assert compiler.CONFIGURED_STAGES[:4] == (
        "corpus_expected_day_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
    )
    assert readiness.STAGES[0].filename == (
        "ng_corpus_expected_day_contract_attestation.json"
    )
    assert readiness.STAGES[0].pre_outcome is True


def test_expected_day_command_uses_resolution_spec(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        compiler.v19,
        "_commands",
        lambda **kwargs: {
            key: ["python", f"{key}.py"]
            for key in compiler.v19.CONFIGURED_STAGES
        },
    )
    commands = compiler._commands(
        artifact_dir=tmp_path,
        resolution_spec_path=tmp_path / "resolution.json",
        expected_day_receipt_path=tmp_path / "expected-day.json",
        resolution_receipt_path=tmp_path / "resolution-receipt.json",
        capture_spec_path=tmp_path / "capture.json",
        capture_receipt_path=tmp_path / "capture-receipt.json",
        materialization_spec_path=tmp_path / "materialization.json",
        materialization_receipt_path=tmp_path / "materialization-receipt.json",
        inventory_receipt_path=tmp_path / "inventory-receipt.json",
        broad_plan_path=tmp_path / "broad-plan.json",
        slice_bundle_path=tmp_path / "slice.json",
        target_plan_path=tmp_path / "target.json",
    )
    argv = commands["corpus_expected_day_contract"]
    assert argv[:3] == ["python", "ng_corpus_expected_day_contract.py", "build"]
    assert argv[argv.index("--spec") + 1].endswith("resolution.json")
    assert argv[argv.index("--out") + 1].endswith("expected-day.json")


def test_validate_inputs_binds_expected_day_to_resolution(monkeypatch) -> None:
    source = {"schema": "resolution"}
    contracted = {
        "status": compiler.expected_day.READY_STATUS,
        "blockers": [],
        "complete_calendar_partition_attested": True,
        "source_spec": source,
        "source_spec_fingerprint": compiler.expected_day._fp(source),
        "receipt_fingerprint": "expected-day",
    }
    resolved = {
        "source_spec_fingerprint": compiler.expected_day._fp(source),
        "receipt_fingerprint": "resolution",
    }
    monkeypatch.setattr(
        compiler.expected_day,
        "validate_receipt",
        lambda value: copy.deepcopy(contracted),
    )
    monkeypatch.setattr(
        compiler.v19,
        "validate_inputs",
        lambda **kwargs: (
            copy.deepcopy(resolved),
            {"a": 1},
            {"b": 2},
            {"c": 3},
            {"d": 4},
            {"e": 5},
            {"f": 6},
        ),
    )
    result = compiler.validate_inputs(
        resolution_spec=source,
        expected_day_receipt=contracted,
        resolution_receipt={},
        capture_spec={},
        capture_receipt={},
        materialization_spec={},
        materialization_receipt={},
        inventory_receipt={},
        broad_plan={},
        slice_bundle={},
        target_plan={},
    )
    assert result[0] == contracted
    assert result[1] == resolved


def test_validate_inputs_rejects_shortened_source_spec(monkeypatch) -> None:
    expected_source = {"schema": "resolution", "days": [1, 2]}
    supplied_source = {"schema": "resolution", "days": [1]}
    contracted = {
        "status": compiler.expected_day.READY_STATUS,
        "blockers": [],
        "complete_calendar_partition_attested": True,
        "source_spec": expected_source,
        "source_spec_fingerprint": compiler.expected_day._fp(expected_source),
    }
    monkeypatch.setattr(compiler.expected_day, "validate_receipt", lambda value: contracted)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV20Error):
        compiler.validate_inputs(
            resolution_spec=supplied_source,
            expected_day_receipt=contracted,
            resolution_receipt={},
            capture_spec={},
            capture_receipt={},
            materialization_spec={},
            materialization_receipt={},
            inventory_receipt={},
            broad_plan={},
            slice_bundle={},
            target_plan={},
        )


def test_validate_inputs_rejects_blocked_expected_day_contract(monkeypatch) -> None:
    blocked = {
        "status": compiler.expected_day.BLOCKED_STATUS,
        "blockers": ["MISSING_DAY"],
        "complete_calendar_partition_attested": False,
    }
    monkeypatch.setattr(compiler.expected_day, "validate_receipt", lambda value: blocked)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV20Error):
        compiler.validate_inputs(
            resolution_spec={},
            expected_day_receipt=blocked,
            resolution_receipt={},
            capture_spec={},
            capture_receipt={},
            materialization_spec={},
            materialization_receipt={},
            inventory_receipt={},
            broad_plan={},
            slice_bundle={},
            target_plan={},
        )


def test_compiled_plan_enables_only_expected_day_contract(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    monkeypatch.setattr(compiler.executor, "validate_plan", lambda value: None)
    rows = compiler._validate_plan(plan, commands, compiled=True)
    assert rows["corpus_expected_day_contract"]["enabled"] is True
    assert rows["corpus_s3_latest_version_resolution"]["enabled"] is False


def test_plan_rejects_resolution_before_expected_day(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    plan["stages"][0], plan["stages"][1] = plan["stages"][1], plan["stages"][0]
    monkeypatch.setattr(compiler.executor, "validate_plan", lambda value: None)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV20Error):
        compiler._validate_plan(plan, commands, compiled=True)


def test_plan_rejects_substituted_expected_day_entrypoint(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    plan["stages"][0]["suggested_entrypoint"] = [
        "python",
        "fake_expected_days.py",
        "build",
    ]
    monkeypatch.setattr(compiler.executor, "validate_plan", lambda value: None)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV20Error):
        compiler._validate_plan(plan, commands, compiled=True)


def test_arm_stage_set_matches_expected_day_compiler_prefix() -> None:
    assert arm.ARMED_STAGES == compiler.CONFIGURED_STAGES
    assert arm.ARMED_STAGES[0] == "corpus_expected_day_contract"
    assert "g15_exact_replay" not in arm.ARMED_STAGES


def test_preflight_requires_expected_day_before_s3(monkeypatch) -> None:
    plan, _ = _rows(enabled_first=True)
    plan["fingerprint"] = "plan"
    monkeypatch.setattr(preflight.executor, "validate_plan", lambda value: None)
    preflight._check_plan(plan)


def test_preflight_rejects_removed_expected_day_stage(monkeypatch) -> None:
    plan, _ = _rows(enabled_first=True)
    plan["stages"] = plan["stages"][1:]
    monkeypatch.setattr(preflight.executor, "validate_plan", lambda value: None)
    with pytest.raises(preflight.HistoricalRefinementPreflightV21Error):
        preflight._check_plan(plan)


def test_executor_uses_readiness_v25_and_expected_day_entrypoint() -> None:
    assert readiness.SCHEMA == "ng_historical_refinement_readiness.v25"
    assert executor.SUGGESTED_ENTRYPOINTS["corpus_expected_day_contract"] == (
        "python",
        "ng_corpus_expected_day_contract.py",
        "build",
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
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV20Error):
        compiler._authority(tampered, label="test")
    assert not any("option" in key.lower() for key in compiler.CONFIGURED_STAGES)
    by_key = {spec.key: spec for spec in readiness.STAGES}
    assert all(by_key[key].pre_outcome for key in compiler.CONFIGURED_STAGES)
