from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_corpus_executor_pipeline_arm_v16 as arm
import ng_corpus_executor_plan_compiler_v16 as compiler
import ng_historical_refinement_executor_v17 as executor
import ng_historical_refinement_preflight_v17 as preflight
import ng_historical_refinement_readiness_v21 as readiness


def _rows(*, enabled_first: bool = True) -> tuple[dict, dict[str, list[str]]]:
    commands = {key: ["python", f"{key}.py"] for key in compiler.CONFIGURED_STAGES}
    stages = []
    for index, spec in enumerate(readiness.STAGES):
        stages.append(
            {
                "key": spec.key,
                "argv": commands.get(spec.key, []),
                "enabled": enabled_first and index == 0,
                "requires_fixed_outcomes": not spec.pre_outcome,
            }
        )
    return {"stages": stages, "outcome_paths": []}, commands


def test_stage_prefix_starts_with_live_inventory_capture() -> None:
    assert compiler.CONFIGURED_STAGES[:4] == (
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
        "corpus_coverage",
        "corpus_definition_byte_binding",
    )
    assert [spec.key for spec in readiness.STAGES][:4] == list(
        compiler.CONFIGURED_STAGES[:4]
    )


def test_capture_command_emits_exact_materialization_spec(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        compiler.v15,
        "_commands",
        lambda **kwargs: {
            key: ["python", f"{key}.py"] for key in compiler.v15.CONFIGURED_STAGES
        },
    )
    commands = compiler._commands(
        artifact_dir=tmp_path,
        capture_spec_path=tmp_path / "capture.json",
        capture_receipt_path=tmp_path / "capture-receipt.json",
        materialization_spec_path=tmp_path / "materialization.json",
        materialization_receipt_path=tmp_path / "materialization-receipt.json",
        inventory_receipt_path=tmp_path / "inventory-receipt.json",
        broad_plan_path=tmp_path / "broad-plan.json",
        slice_bundle_path=tmp_path / "slice.json",
        target_plan_path=tmp_path / "target.json",
    )
    argv = commands["corpus_s3_inventory_capture"]
    assert argv[:3] == ["python", "ng_corpus_s3_inventory_capture.py", "capture"]
    assert argv[argv.index("--materialization-spec-out") + 1].endswith(
        "materialization.json"
    )


def test_validate_inputs_binds_capture_to_materialization(monkeypatch) -> None:
    source = {"schema": "capture"}
    materialization_spec = {"schema": "materialization"}
    captured = {
        "status": compiler.capture.READY_STATUS,
        "blockers": [],
        "source_spec": source,
        "source_spec_fingerprint": compiler.capture._fp(source),
        "materialization_spec": materialization_spec,
        "materialization_spec_fingerprint": compiler.capture._fp(materialization_spec),
    }
    attested = {
        "source_spec_fingerprint": compiler.capture._fp(materialization_spec),
    }
    monkeypatch.setattr(
        compiler.capture, "validate_receipt", lambda value: copy.deepcopy(captured)
    )
    monkeypatch.setattr(
        compiler.v15,
        "validate_inputs",
        lambda **kwargs: (attested, {"a": 1}, {"b": 2}, {"c": 3}, {"d": 4}),
    )
    result = compiler.validate_inputs(
        capture_spec=source,
        capture_receipt=captured,
        materialization_spec=materialization_spec,
        materialization_receipt={},
        inventory_receipt={},
        broad_plan={},
        slice_bundle={},
        target_plan={},
    )
    assert result[0] == captured
    assert result[1] == attested


def test_validate_inputs_rejects_substituted_materialization(monkeypatch) -> None:
    source = {"schema": "capture"}
    expected = {"schema": "materialization", "id": 1}
    supplied = {"schema": "materialization", "id": 2}
    captured = {
        "status": compiler.capture.READY_STATUS,
        "blockers": [],
        "source_spec": source,
        "source_spec_fingerprint": compiler.capture._fp(source),
        "materialization_spec": expected,
        "materialization_spec_fingerprint": compiler.capture._fp(expected),
    }
    monkeypatch.setattr(compiler.capture, "validate_receipt", lambda value: captured)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV16Error):
        compiler.validate_inputs(
            capture_spec=source,
            capture_receipt=captured,
            materialization_spec=supplied,
            materialization_receipt={},
            inventory_receipt={},
            broad_plan={},
            slice_bundle={},
            target_plan={},
        )


def test_compiled_plan_enables_only_capture(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    monkeypatch.setattr(compiler.executor, "validate_plan", lambda value: None)
    rows = compiler._validate_plan(plan, commands, compiled=True)
    assert rows["corpus_s3_inventory_capture"]["enabled"] is True
    assert rows["corpus_s3_materialization"]["enabled"] is False


def test_plan_rejects_materialization_before_capture(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    plan["stages"][0], plan["stages"][1] = plan["stages"][1], plan["stages"][0]
    monkeypatch.setattr(compiler.executor, "validate_plan", lambda value: None)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV16Error):
        compiler._validate_plan(plan, commands, compiled=True)


def test_arm_stage_set_matches_compiler_prefix() -> None:
    assert arm.ARMED_STAGES == compiler.CONFIGURED_STAGES
    assert arm.ARMED_STAGES[0] == "corpus_s3_inventory_capture"


def test_preflight_requires_capture_before_materialization(monkeypatch) -> None:
    plan, _ = _rows(enabled_first=True)
    plan["fingerprint"] = "plan"
    monkeypatch.setattr(preflight.executor, "validate_plan", lambda value: None)
    preflight._check_plan(plan)


def test_preflight_rejects_removed_capture(monkeypatch) -> None:
    plan, _ = _rows(enabled_first=True)
    plan["stages"] = plan["stages"][1:]
    monkeypatch.setattr(preflight.executor, "validate_plan", lambda value: None)
    with pytest.raises(preflight.HistoricalRefinementPreflightV17Error):
        preflight._check_plan(plan)


def test_executor_uses_readiness_v21_and_capture_entrypoint() -> None:
    assert readiness.SCHEMA == "ng_historical_refinement_readiness.v21"
    assert executor.SUGGESTED_ENTRYPOINTS["corpus_s3_inventory_capture"] == (
        "python",
        "ng_corpus_s3_inventory_capture.py",
        "capture",
    )


def test_authority_wall() -> None:
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
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV16Error):
        compiler._authority(tampered, label="test")


def test_all_configured_corpus_stages_are_pre_outcome() -> None:
    by_key = {spec.key: spec for spec in readiness.STAGES}
    assert all(by_key[key].pre_outcome for key in compiler.CONFIGURED_STAGES)


def test_no_options_stage_is_configured() -> None:
    assert not any("option" in key.lower() for key in compiler.CONFIGURED_STAGES)
