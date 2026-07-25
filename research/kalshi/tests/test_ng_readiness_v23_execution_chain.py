from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_corpus_executor_pipeline_arm_v18 as arm
import ng_corpus_executor_plan_compiler_v18 as compiler
import ng_historical_refinement_executor_v19 as executor
import ng_historical_refinement_preflight_v19 as preflight
import ng_historical_refinement_readiness_v23 as readiness


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
                "expected_output": spec.filename,
                "suggested_entrypoint": list(
                    executor.SUGGESTED_ENTRYPOINTS.get(spec.key, ())
                ),
            }
        )
    return {"stages": stages, "outcome_paths": []}, commands


def test_stage_prefix_starts_with_paginated_resolution() -> None:
    assert compiler.CONFIGURED_STAGES[:4] == (
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
        "corpus_coverage",
    )
    assert readiness.STAGES[0].filename == (
        "ng_corpus_s3_paginated_latest_version_resolution_attestation.json"
    )
    assert readiness.STAGES[0].pre_outcome is True


def test_paginated_resolution_command_emits_exact_capture_spec(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        compiler.v17,
        "_commands",
        lambda **kwargs: {
            key: ["python", f"{key}.py"]
            for key in compiler.v17.CONFIGURED_STAGES
        },
    )
    commands = compiler._commands(
        artifact_dir=tmp_path,
        resolution_spec_path=tmp_path / "resolution.json",
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
    argv = commands["corpus_s3_latest_version_resolution"]
    assert argv[:3] == [
        "python",
        "ng_corpus_s3_paginated_latest_version_resolution.py",
        "resolve",
    ]
    assert argv[argv.index("--capture-spec-out") + 1].endswith("capture.json")


def test_validate_inputs_binds_paginated_evidence_to_capture(monkeypatch) -> None:
    source = {"schema": "resolution"}
    capture_spec = {"schema": "capture"}
    legacy = {"receipt_fingerprint": "legacy"}
    resolved = {
        "status": compiler.resolution.READY_STATUS,
        "blockers": [],
        "complete_pagination_attested": True,
        "source_spec": source,
        "source_spec_fingerprint": compiler.resolution._fp(source),
        "capture_spec": capture_spec,
        "capture_spec_fingerprint": compiler.resolution._fp(capture_spec),
        "legacy_resolution_receipt": legacy,
    }
    captured = {
        "source_spec_fingerprint": compiler.resolution._fp(capture_spec),
    }
    monkeypatch.setattr(
        compiler.resolution, "validate_receipt", lambda value: copy.deepcopy(resolved)
    )
    monkeypatch.setattr(
        compiler.v17,
        "validate_inputs",
        lambda **kwargs: (
            copy.deepcopy(legacy),
            captured,
            {"a": 1},
            {"b": 2},
            {"c": 3},
            {"d": 4},
            {"e": 5},
        ),
    )
    result = compiler.validate_inputs(
        resolution_spec=source,
        resolution_receipt=resolved,
        capture_spec=capture_spec,
        capture_receipt={},
        materialization_spec={},
        materialization_receipt={},
        inventory_receipt={},
        broad_plan={},
        slice_bundle={},
        target_plan={},
    )
    assert result[0] == resolved
    assert result[1] == captured


def test_validate_inputs_rejects_substituted_capture_spec(monkeypatch) -> None:
    source = {"schema": "resolution"}
    expected = {"schema": "capture", "id": 1}
    supplied = {"schema": "capture", "id": 2}
    resolved = {
        "status": compiler.resolution.READY_STATUS,
        "blockers": [],
        "complete_pagination_attested": True,
        "source_spec": source,
        "source_spec_fingerprint": compiler.resolution._fp(source),
        "capture_spec": expected,
        "capture_spec_fingerprint": compiler.resolution._fp(expected),
        "legacy_resolution_receipt": {"receipt_fingerprint": "legacy"},
    }
    monkeypatch.setattr(compiler.resolution, "validate_receipt", lambda value: resolved)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV18Error):
        compiler.validate_inputs(
            resolution_spec=source,
            resolution_receipt=resolved,
            capture_spec=supplied,
            capture_receipt={},
            materialization_spec={},
            materialization_receipt={},
            inventory_receipt={},
            broad_plan={},
            slice_bundle={},
            target_plan={},
        )


def test_validate_inputs_rejects_incomplete_pagination(monkeypatch) -> None:
    source = {"schema": "resolution"}
    resolved = {
        "status": compiler.resolution.READY_STATUS,
        "blockers": [],
        "complete_pagination_attested": False,
    }
    monkeypatch.setattr(compiler.resolution, "validate_receipt", lambda value: resolved)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV18Error):
        compiler.validate_inputs(
            resolution_spec=source,
            resolution_receipt=resolved,
            capture_spec={},
            capture_receipt={},
            materialization_spec={},
            materialization_receipt={},
            inventory_receipt={},
            broad_plan={},
            slice_bundle={},
            target_plan={},
        )


def test_compiled_plan_enables_only_paginated_resolution(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    monkeypatch.setattr(compiler.executor, "validate_plan", lambda value: None)
    rows = compiler._validate_plan(plan, commands, compiled=True)
    assert rows["corpus_s3_latest_version_resolution"]["enabled"] is True
    assert rows["corpus_s3_inventory_capture"]["enabled"] is False


def test_plan_rejects_legacy_resolution_artifact(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    plan["stages"][0]["expected_output"] = (
        "ng_corpus_s3_latest_version_resolution_attestation.json"
    )
    monkeypatch.setattr(compiler.executor, "validate_plan", lambda value: None)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV18Error):
        compiler._validate_plan(plan, commands, compiled=True)


def test_plan_rejects_capture_before_paginated_resolution(monkeypatch) -> None:
    plan, commands = _rows(enabled_first=True)
    plan["stages"][0], plan["stages"][1] = plan["stages"][1], plan["stages"][0]
    monkeypatch.setattr(compiler.executor, "validate_plan", lambda value: None)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV18Error):
        compiler._validate_plan(plan, commands, compiled=True)


def test_arm_stage_set_matches_compiler_prefix() -> None:
    assert arm.ARMED_STAGES == compiler.CONFIGURED_STAGES
    assert arm.ARMED_STAGES[0] == "corpus_s3_latest_version_resolution"


def test_preflight_requires_paginated_resolution_before_capture(monkeypatch) -> None:
    plan, _ = _rows(enabled_first=True)
    plan["fingerprint"] = "plan"
    monkeypatch.setattr(preflight.executor, "validate_plan", lambda value: None)
    preflight._check_plan(plan)


def test_preflight_rejects_substituted_paginated_entrypoint(monkeypatch) -> None:
    plan, _ = _rows(enabled_first=True)
    plan["stages"][0]["suggested_entrypoint"] = [
        "python",
        "ng_corpus_s3_latest_version_resolution.py",
        "resolve",
    ]
    monkeypatch.setattr(preflight.executor, "validate_plan", lambda value: None)
    with pytest.raises(preflight.HistoricalRefinementPreflightV19Error):
        preflight._check_plan(plan)


def test_preflight_rejects_removed_resolution(monkeypatch) -> None:
    plan, _ = _rows(enabled_first=True)
    plan["stages"] = plan["stages"][1:]
    monkeypatch.setattr(preflight.executor, "validate_plan", lambda value: None)
    with pytest.raises(preflight.HistoricalRefinementPreflightV19Error):
        preflight._check_plan(plan)


def test_executor_uses_readiness_v23_and_paginated_entrypoint() -> None:
    assert readiness.SCHEMA == "ng_historical_refinement_readiness.v23"
    assert executor.SUGGESTED_ENTRYPOINTS["corpus_s3_latest_version_resolution"] == (
        "python",
        "ng_corpus_s3_paginated_latest_version_resolution.py",
        "resolve",
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
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV18Error):
        compiler._authority(tampered, label="test")
    assert not any("option" in key.lower() for key in compiler.CONFIGURED_STAGES)
    by_key = {spec.key: spec for spec in readiness.STAGES}
    assert all(by_key[key].pre_outcome for key in compiler.CONFIGURED_STAGES)
