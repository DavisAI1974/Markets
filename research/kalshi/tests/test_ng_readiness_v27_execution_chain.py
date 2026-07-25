from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_corpus_executor_pipeline_arm_v22 as arm
import ng_corpus_executor_plan_compiler_v22 as compiler
import ng_historical_refinement_executor_v23 as executor
import ng_historical_refinement_preflight_v23 as preflight
import ng_historical_refinement_readiness_v27 as readiness


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


def _runtime_receipt() -> dict:
    return {
        "status": compiler.runtime_capture.READY_STATUS,
        "blockers": [],
        "actual_runtime_capture_bound_to_product_lags": True,
        "declared_observations_bound_to_runtime_interval": True,
        "complete_pagination_attested": True,
        "checksum_enabled_heads_attested": True,
        "source_spec": {"capture": True},
        "finalization_contract": {"final": True},
        "materialization_spec": {"materialize": True},
        "paginated_inventory_receipt": {"page": True},
        "receipt_fingerprint": "r" * 64,
        "paginated_inventory_receipt_fingerprint": "p" * 64,
        "capture_started_at_utc": "2026-07-25T20:00:00Z",
        "capture_completed_at_utc": "2026-07-25T20:00:02Z",
        "runtime_finalization_checks_fingerprint": "f" * 64,
        "declared_observation_checks_fingerprint": "d" * 64,
    }


def test_stage_prefix_uses_runtime_observed_capture() -> None:
    assert compiler.CONFIGURED_STAGES[:5] == (
        "corpus_expected_day_contract",
        "corpus_inventory_finalization_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
    )
    assert readiness.STAGES[3].filename == (
        "ng_corpus_s3_runtime_observed_inventory_capture_attestation.json"
    )
    assert readiness.STAGES[3].pre_outcome is True


def test_runtime_capture_command_binds_finalization_and_materialization(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        compiler.v21,
        "_commands",
        lambda **kwargs: {
            key: ["python", f"{key}.py"] for key in compiler.CONFIGURED_STAGES
        },
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
        materialization_receipt_path=tmp_path / "materialization-receipt.json",
        inventory_receipt_path=tmp_path / "inventory-receipt.json",
        broad_plan_path=tmp_path / "broad-plan.json",
        slice_bundle_path=tmp_path / "slice.json",
        target_plan_path=tmp_path / "target.json",
    )
    argv = commands["corpus_s3_inventory_capture"]
    assert argv[:3] == [
        "python",
        "ng_corpus_s3_runtime_observed_inventory_capture.py",
        "capture",
    ]
    assert argv[argv.index("--finalization") + 1].endswith("finalization.json")
    assert argv[argv.index("--materialization-spec-out") + 1].endswith(
        "materialization.json"
    )
    assert argv[argv.index("--receipt-out") + 1].endswith("runtime-receipt.json")


def test_runtime_capture_validation_accepts_exact_evidence(monkeypatch) -> None:
    receipt = _runtime_receipt()
    monkeypatch.setattr(
        compiler.runtime_capture,
        "validate_receipt",
        lambda value: copy.deepcopy(receipt),
    )
    checked = compiler._validate_runtime_capture(
        capture_spec={"capture": True},
        finalization_receipt={"final": True},
        capture_receipt=receipt,
        materialization_spec={"materialize": True},
    )
    assert checked["receipt_fingerprint"] == "r" * 64


def test_runtime_capture_validation_rejects_blockers(monkeypatch) -> None:
    receipt = _runtime_receipt()
    receipt["blockers"] = ["RUNTIME_CAPTURE_BEFORE_FINALIZATION_DEADLINE"]
    monkeypatch.setattr(
        compiler.runtime_capture,
        "validate_receipt",
        lambda value: copy.deepcopy(receipt),
    )
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV22Error):
        compiler._validate_runtime_capture(
            capture_spec={"capture": True},
            finalization_receipt={"final": True},
            capture_receipt=receipt,
            materialization_spec={"materialize": True},
        )


def test_runtime_capture_validation_rejects_finalization_substitution(monkeypatch) -> None:
    receipt = _runtime_receipt()
    monkeypatch.setattr(
        compiler.runtime_capture,
        "validate_receipt",
        lambda value: copy.deepcopy(receipt),
    )
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV22Error):
        compiler._validate_runtime_capture(
            capture_spec={"capture": True},
            finalization_receipt={"different": True},
            capture_receipt=receipt,
            materialization_spec={"materialize": True},
        )


def test_compiled_plan_enables_only_expected_day_contract(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    monkeypatch.setattr(compiler.executor, "validate_plan", lambda value: None)
    rows = compiler._validate_plan(plan, commands, compiled=True)
    assert rows["corpus_expected_day_contract"]["enabled"] is True
    assert rows["corpus_s3_inventory_capture"]["enabled"] is False
    assert rows["corpus_s3_materialization"]["enabled"] is False


def test_plan_rejects_legacy_paginated_inventory_artifact(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    plan["stages"][3]["expected_output"] = (
        "ng_corpus_s3_paginated_inventory_capture_attestation.json"
    )
    monkeypatch.setattr(compiler.executor, "validate_plan", lambda value: None)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV22Error):
        compiler._validate_plan(plan, commands, compiled=True)


def test_plan_rejects_materialization_before_runtime_capture(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    plan["stages"][3], plan["stages"][4] = plan["stages"][4], plan["stages"][3]
    monkeypatch.setattr(compiler.executor, "validate_plan", lambda value: None)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV22Error):
        compiler._validate_plan(plan, commands, compiled=True)


def test_arm_stage_set_matches_runtime_observed_prefix() -> None:
    assert arm.ARMED_STAGES == compiler.CONFIGURED_STAGES
    assert "corpus_s3_inventory_capture" in arm.ARMED_STAGES
    assert "g15_exact_replay" not in arm.ARMED_STAGES


def test_preflight_accepts_runtime_observed_order(monkeypatch) -> None:
    plan, _ = _rows(enabled_first=True)
    plan["fingerprint"] = "plan"
    monkeypatch.setattr(preflight.executor, "validate_plan", lambda value: None)
    preflight._check_plan(plan)


def test_preflight_rejects_removed_runtime_capture(monkeypatch) -> None:
    plan, _ = _rows(enabled_first=True)
    plan["stages"] = [
        row for row in plan["stages"] if row["key"] != "corpus_s3_inventory_capture"
    ]
    monkeypatch.setattr(preflight.executor, "validate_plan", lambda value: None)
    with pytest.raises(preflight.HistoricalRefinementPreflightV23Error):
        preflight._check_plan(plan)


def test_executor_uses_readiness_v27_runtime_entrypoint() -> None:
    assert readiness.SCHEMA == "ng_historical_refinement_readiness.v27"
    assert executor.SUGGESTED_ENTRYPOINTS["corpus_s3_inventory_capture"] == (
        "python",
        "ng_corpus_s3_runtime_observed_inventory_capture.py",
        "capture",
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
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV22Error):
        compiler._authority(tampered, label="test")
    assert not any("option" in key.lower() for key in compiler.CONFIGURED_STAGES)
    by_key = {spec.key: spec for spec in readiness.STAGES}
    assert all(by_key[key].pre_outcome for key in compiler.CONFIGURED_STAGES)
