from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_corpus_executor_pipeline_arm_v31 as arm
import ng_corpus_executor_plan_compiler_v29 as base_compiler
import ng_historical_refinement_preflight_v31 as preflight


G15_ACTUAL = "renders/ng_refine_s95/g15_actual_fixed.json"


def _compiled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(base_compiler.v28, "validate_receipt", lambda *args, **kwargs: None)
    upstream_plan = {
        "fingerprint": "p" * 64,
        "stages": [
            {"key": key, "argv": ["python", f"{key}.py"]}
            for key in base_compiler.PREFIX_STAGES
        ],
    }
    upstream_receipt = {"fingerprint": "r" * 64}
    manifest = base_compiler.build_extension_manifest(
        artifact_dir=tmp_path,
        commands=base_compiler._selftest_commands(tmp_path),
    )
    plan, _ = base_compiler.build_compiled_plan(
        artifact_dir=tmp_path,
        working_directory=tmp_path,
        upstream_plan=upstream_plan,
        upstream_receipt=upstream_receipt,
        extension_manifest=manifest,
        verify_files=False,
    )
    compiler_receipt = {
        "schema": arm.compiler.SCHEMA,
        "fingerprint": "c" * 64,
        "extension_manifest_fingerprint": manifest["fingerprint"],
        "command_contract_fingerprint": "d" * 64,
        "command_lineage_fingerprint": "e" * 64,
        "all_required_cli_options_verified": True,
        "exact_command_source_bindings_verified": True,
        "g16_actual_exposed_only_at_counterfactual_publication": True,
    }

    def validate_receipt(value, **kwargs):
        if value != compiler_receipt:
            raise ValueError("compiler-v31 receipt substitution")
        if kwargs.get("extension_manifest") != manifest:
            raise ValueError("extension manifest substitution")
        return copy.deepcopy(compiler_receipt)

    monkeypatch.setattr(arm.compiler, "validate_receipt", validate_receipt)
    return plan, compiler_receipt, manifest


def _armed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    plan, receipt, manifest = _compiled(tmp_path, monkeypatch)
    armed, arm_receipt = arm.build_armed_plan(
        plan,
        receipt,
        manifest,
        g15_outcome_paths=[G15_ACTUAL],
    )
    return armed, arm_receipt, manifest


def _refingerprint(value):
    result = copy.deepcopy(value)
    result.pop("fingerprint", None)
    result["fingerprint"] = arm.compiler._fp(result)
    return result


def test_v31_arm_runs_through_attribution_bound_curve_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt, _ = _armed(tmp_path, monkeypatch)
    rows = {row["key"]: row for row in plan["stages"]}
    assert arm.ARMED_STAGES[-1] == "g16_attribution_bound_curve_lock"
    assert all(rows[key]["enabled"] is True for key in arm.ARMED_STAGES)
    assert all(rows[key]["enabled"] is False for key in arm.PUBLICATION_STAGES)
    assert receipt["g16_curve_locked_before_g16_scoring"] is True


def test_v31_arm_carries_cli_and_lineage_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _, receipt, manifest = _armed(tmp_path, monkeypatch)
    assert receipt["extension_manifest_fingerprint"] == manifest["fingerprint"]
    assert receipt["command_contract_fingerprint"] == "d" * 64
    assert receipt["command_lineage_fingerprint"] == "e" * 64
    assert receipt["all_required_cli_options_verified"] is True
    assert receipt["exact_command_source_bindings_verified"] is True
    assert receipt["g16_actual_exposed_only_at_counterfactual_publication"] is True


def test_v31_arm_rejects_extension_manifest_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt, manifest = _compiled(tmp_path, monkeypatch)
    bad_manifest = copy.deepcopy(manifest)
    bad_manifest["fingerprint"] = "0" * 64
    with pytest.raises(arm.CorpusExecutorPipelineArmV31Error):
        arm.build_armed_plan(
            plan,
            receipt,
            bad_manifest,
            g15_outcome_paths=[G15_ACTUAL],
        )


def test_v31_arm_rejects_compiler_receipt_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt, manifest = _compiled(tmp_path, monkeypatch)
    bad_receipt = copy.deepcopy(receipt)
    bad_receipt["command_lineage_fingerprint"] = "0" * 64
    with pytest.raises(arm.CorpusExecutorPipelineArmV31Error):
        arm.build_armed_plan(
            plan,
            bad_receipt,
            manifest,
            g15_outcome_paths=[G15_ACTUAL],
        )


def test_v31_arm_rejects_missing_g15_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt, manifest = _compiled(tmp_path, monkeypatch)
    with pytest.raises(arm.CorpusExecutorPipelineArmV31Error):
        arm.build_armed_plan(plan, receipt, manifest, g15_outcome_paths=[])


def test_v31_arm_rejects_g16_outcome_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt, manifest = _compiled(tmp_path, monkeypatch)
    with pytest.raises(arm.CorpusExecutorPipelineArmV31Error):
        arm.build_armed_plan(
            plan,
            receipt,
            manifest,
            g15_outcome_paths=["renders/ng_refine_s95/g16_actual.json"],
        )


def test_v31_arm_rejects_fixed_g16_publication_enablement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt, _ = _armed(tmp_path, monkeypatch)
    tampered = copy.deepcopy(plan)
    tampered["stages"][-1]["enabled"] = True
    tampered = _refingerprint(tampered)
    with pytest.raises(arm.CorpusExecutorPipelineArmV31Error):
        arm.validate_arm_receipt(receipt, armed_plan=tampered)


def test_preflight_v31_accepts_exact_cli_lineage_arm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt, _ = _armed(tmp_path, monkeypatch)
    preflight._check_plan(plan)
    checked = preflight._validated_arm(plan, receipt)
    assert checked["fingerprint"] == receipt["fingerprint"]
    assert checked["all_required_cli_options_verified"] is True
    assert checked["exact_command_source_bindings_verified"] is True


def test_preflight_v31_rejects_publication_enablement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, _, _ = _armed(tmp_path, monkeypatch)
    tampered = copy.deepcopy(plan)
    tampered["stages"][-2]["enabled"] = True
    tampered = _refingerprint(tampered)
    with pytest.raises(preflight.HistoricalRefinementPreflightV31Error):
        preflight._check_plan(tampered)


def test_preflight_v31_rejects_entrypoint_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, _, _ = _armed(tmp_path, monkeypatch)
    tampered = copy.deepcopy(plan)
    target = next(
        row for row in tampered["stages"]
        if row["key"] == "g16_attribution_bound_curve_lock"
    )
    target["argv"][1] = "substituted.py"
    tampered = _refingerprint(tampered)
    with pytest.raises(preflight.HistoricalRefinementPreflightV31Error):
        preflight._check_plan(tampered)


def test_preflight_v31_requires_blind_and_brain_protection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, _, _ = _armed(tmp_path, monkeypatch)
    tampered = copy.deepcopy(plan)
    tampered["protected_paths"] = [
        row for row in tampered["protected_paths"]
        if row["role"] != "g16_blind_forecast"
    ]
    tampered = _refingerprint(tampered)
    with pytest.raises(preflight.HistoricalRefinementPreflightV31Error):
        preflight._check_plan(tampered)


def test_v31_permanent_authority_wall_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt, _ = _armed(tmp_path, monkeypatch)
    assert plan["random_shuffle_used"] is False
    assert plan["blind_forecasts_immutable"] is True
    assert plan["may_update_ng_brain"] is False
    assert plan["execution_authority"] is False
    assert plan["cme_event_contracts_mode"] == "SHADOW"
    assert plan["brokerage_contract"] == "tastytrade_not_ibkr"
    assert plan["options_lane_started"] is False
    assert receipt["may_change_g16_blind_prior"] is False


def test_v31_arm_inputs_are_immutable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt, manifest = _compiled(tmp_path, monkeypatch)
    originals = copy.deepcopy((plan, receipt, manifest))
    arm.build_armed_plan(
        plan,
        receipt,
        manifest,
        g15_outcome_paths=[G15_ACTUAL],
    )
    assert (plan, receipt, manifest) == originals
