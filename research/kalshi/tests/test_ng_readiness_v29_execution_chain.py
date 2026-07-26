from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_corpus_executor_pipeline_arm_v24 as arm
import ng_corpus_executor_plan_compiler_v24 as compiler
import ng_historical_refinement_executor_v25 as executor
import ng_historical_refinement_preflight_v25 as preflight
import ng_historical_refinement_readiness_v29 as readiness


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
    commands["corpus_s3_materialization_provenance"] = [
        "python",
        "ng_corpus_s3_materializer_provenance_gate.py",
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
                "suggested_entrypoint": list(executor.SUGGESTED_ENTRYPOINTS.get(spec.key, ())),
            }
        )
    return {"stages": stages, "outcome_paths": []}, commands


def _authority() -> dict:
    return {
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


def _provenance_receipt() -> tuple[dict, dict, dict]:
    runtime = {"receipt_fingerprint": "r" * 64}
    exact = {"receipt_fingerprint": "e" * 64}
    receipt = {
        "status": compiler.provenance_gate.READY_STATUS,
        "blockers": [],
        "runtime_capture_recursively_validated": True,
        "exact_materializer_recursively_validated": True,
        "complete_runtime_inventory_embedded": True,
        "exact_materialized_bytes_bound_to_runtime_inventory": True,
        "identity_from_s3_keys_inferred": False,
        "runtime_capture_receipt": runtime,
        "exact_materializer_receipt": exact,
        "runtime_capture_receipt_fingerprint": runtime["receipt_fingerprint"],
        "exact_materializer_receipt_fingerprint": exact["receipt_fingerprint"],
        "exact_materializer_runtime_inventory_capture_fingerprint": runtime[
            "receipt_fingerprint"
        ],
        "source_materializations_fingerprint": "s" * 64,
        "source_count": 2,
        "downstream_materialization_receipt_fingerprint": "d" * 64,
        "canonical_inventory_spec_fingerprint": "c" * 64,
        "materialization_evidence_fingerprint": "m" * 64,
        "plan_fingerprint": "p" * 64,
        "inventory_compiler_receipt_fingerprint": "i" * 64,
        "provenance_lineage_fingerprint": "l" * 64,
        "fingerprint": "g" * 64,
        **_authority(),
    }
    return runtime, exact, receipt


def test_stage_prefix_inserts_recursive_provenance() -> None:
    assert compiler.CONFIGURED_STAGES[:7] == (
        "corpus_expected_day_contract",
        "corpus_inventory_finalization_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
        "corpus_s3_materialization_provenance",
        "corpus_coverage",
    )
    assert readiness.STAGES[5].filename == "ng_corpus_s3_materializer_provenance_gate.json"
    assert readiness.STAGES[5].pre_outcome is True


def test_provenance_command_binds_both_upstream_receipts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        compiler.v23,
        "_commands",
        lambda **kwargs: {key: ["python", f"{key}.py"] for key in compiler.v23.CONFIGURED_STAGES},
    )
    commands = compiler._commands(
        artifact_dir=tmp_path,
        resolution_spec_path=tmp_path / "resolution.json",
        expected_day_receipt_path=tmp_path / "expected.json",
        finalization_receipt_path=tmp_path / "finalization.json",
        resolution_receipt_path=tmp_path / "resolution-receipt.json",
        capture_spec_path=tmp_path / "capture-spec.json",
        capture_receipt_path=tmp_path / "runtime.json",
        materialization_spec_path=tmp_path / "materialization-spec.json",
        materialization_receipt_path=tmp_path / "exact.json",
        materialization_provenance_path=tmp_path / "provenance.json",
        inventory_receipt_path=tmp_path / "inventory.json",
        broad_plan_path=tmp_path / "broad-plan.json",
        slice_bundle_path=tmp_path / "slice.json",
        target_plan_path=tmp_path / "target.json",
    )
    argv = commands["corpus_s3_materialization_provenance"]
    assert argv[:3] == [
        "python",
        "ng_corpus_s3_materializer_provenance_gate.py",
        "build",
    ]
    assert argv[argv.index("--runtime-capture") + 1].endswith("runtime.json")
    assert argv[argv.index("--exact-materializer") + 1].endswith("exact.json")
    assert argv[argv.index("--out") + 1].endswith("provenance.json")


def test_provenance_validation_accepts_recursive_binding(monkeypatch) -> None:
    runtime, exact, receipt = _provenance_receipt()
    monkeypatch.setattr(
        compiler.provenance_gate,
        "validate_gate",
        lambda value: copy.deepcopy(receipt),
    )
    checked = compiler._validate_materializer_provenance(
        runtime_receipt=runtime,
        exact_receipt=exact,
        provenance_receipt=receipt,
    )
    assert checked["fingerprint"] == "g" * 64


def test_provenance_validation_rejects_runtime_substitution(monkeypatch) -> None:
    runtime, exact, receipt = _provenance_receipt()
    monkeypatch.setattr(
        compiler.provenance_gate,
        "validate_gate",
        lambda value: copy.deepcopy(receipt),
    )
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV24Error):
        compiler._validate_materializer_provenance(
            runtime_receipt={"receipt_fingerprint": "x" * 64},
            exact_receipt=exact,
            provenance_receipt=receipt,
        )


def test_provenance_validation_rejects_blockers(monkeypatch) -> None:
    runtime, exact, receipt = _provenance_receipt()
    receipt["blockers"] = ["MATERIALIZATION_SPEC_CONTENT_MISMATCH"]
    monkeypatch.setattr(
        compiler.provenance_gate,
        "validate_gate",
        lambda value: copy.deepcopy(receipt),
    )
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV24Error):
        compiler._validate_materializer_provenance(
            runtime_receipt=runtime,
            exact_receipt=exact,
            provenance_receipt=receipt,
        )


def test_compiled_plan_enables_only_expected_day_contract(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    monkeypatch.setattr(compiler.executor, "validate_plan", lambda value: None)
    rows = compiler._validate_plan(plan, commands, compiled=True)
    assert rows["corpus_expected_day_contract"]["enabled"] is True
    assert rows["corpus_s3_materialization"]["enabled"] is False
    assert rows["corpus_s3_materialization_provenance"]["enabled"] is False
    assert rows["corpus_coverage"]["enabled"] is False


def test_plan_rejects_provenance_artifact_substitution(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    plan["stages"][5]["expected_output"] = "detached-provenance.json"
    monkeypatch.setattr(compiler.executor, "validate_plan", lambda value: None)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV24Error):
        compiler._validate_plan(plan, commands, compiled=True)


def test_plan_rejects_provenance_entrypoint_substitution(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    plan["stages"][5]["suggested_entrypoint"] = ["python", "legacy.py"]
    monkeypatch.setattr(compiler.executor, "validate_plan", lambda value: None)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV24Error):
        compiler._validate_plan(plan, commands, compiled=True)


def test_arm_stage_set_includes_provenance_but_not_g15() -> None:
    assert arm.ARMED_STAGES == compiler.CONFIGURED_STAGES
    assert "corpus_s3_materialization_provenance" in arm.ARMED_STAGES
    assert "g15_exact_replay" not in arm.ARMED_STAGES


def test_preflight_accepts_recursive_provenance_order(monkeypatch) -> None:
    plan, _ = _rows(enabled_first=True)
    plan["fingerprint"] = "plan"
    monkeypatch.setattr(preflight.executor, "validate_plan", lambda value: None)
    preflight._check_plan(plan)


def test_preflight_rejects_removed_provenance(monkeypatch) -> None:
    plan, _ = _rows(enabled_first=True)
    plan["stages"] = [
        row
        for row in plan["stages"]
        if row["key"] != "corpus_s3_materialization_provenance"
    ]
    monkeypatch.setattr(preflight.executor, "validate_plan", lambda value: None)
    with pytest.raises(preflight.HistoricalRefinementPreflightV25Error):
        preflight._check_plan(plan)


def test_executor_uses_readiness_v29_provenance_entrypoint() -> None:
    assert readiness.SCHEMA == "ng_historical_refinement_readiness.v29"
    assert executor.SUGGESTED_ENTRYPOINTS[
        "corpus_s3_materialization_provenance"
    ] == (
        "python",
        "ng_corpus_s3_materializer_provenance_gate.py",
        "build",
    )


def test_authority_wall_and_no_options_stage() -> None:
    receipt = _authority()
    compiler._authority(receipt, label="test")
    tampered = copy.deepcopy(receipt)
    tampered["options_lane_started"] = True
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV24Error):
        compiler._authority(tampered, label="test")
    assert not any("option" in key.lower() for key in compiler.CONFIGURED_STAGES)
    by_key = {spec.key: spec for spec in readiness.STAGES}
    assert all(by_key[key].pre_outcome for key in compiler.CONFIGURED_STAGES)
