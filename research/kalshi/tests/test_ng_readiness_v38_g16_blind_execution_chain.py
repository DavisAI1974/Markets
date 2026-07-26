from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_corpus_executor_pipeline_arm_v29 as arm
import ng_corpus_executor_plan_compiler_v29 as compiler
import ng_historical_refinement_preflight_v30 as preflight
import ng_historical_refinement_executor_v34 as executor


def _compiled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(compiler.v28, "validate_receipt", lambda *args, **kwargs: None)
    upstream_plan = {
        "fingerprint": "p" * 64,
        "stages": [
            {"key": key, "argv": ["python", f"{key}.py"]}
            for key in compiler.PREFIX_STAGES
        ],
    }
    upstream_receipt = {"fingerprint": "r" * 64}
    manifest = compiler.build_extension_manifest(
        artifact_dir=tmp_path,
        commands=compiler._selftest_commands(tmp_path),
    )
    return compiler.build_compiled_plan(
        artifact_dir=tmp_path,
        working_directory=tmp_path,
        upstream_plan=upstream_plan,
        upstream_receipt=upstream_receipt,
        extension_manifest=manifest,
        verify_files=False,
    )


def _armed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    plan, receipt = _compiled(tmp_path, monkeypatch)
    return arm.build_armed_plan(
        plan,
        receipt,
        g15_outcome_paths=["renders/ng_refine_s95/g15_actual_fixed.json"],
    )


def _refingerprint(plan):
    value = copy.deepcopy(plan)
    value.pop("fingerprint", None)
    value["fingerprint"] = compiler._fp(value)
    return value


def test_v38_arm_runs_through_attribution_bound_curve_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt = _armed(tmp_path, monkeypatch)
    rows = {row["key"]: row for row in plan["stages"]}
    assert arm.ARMED_STAGES[-1] == "g16_attribution_bound_curve_lock"
    assert all(rows[key]["enabled"] is True for key in arm.ARMED_STAGES)
    assert all(rows[key]["enabled"] is False for key in arm.PUBLICATION_STAGES)
    assert receipt["g16_curve_locked_before_g16_scoring"] is True
    assert receipt["g16_outcomes_forbidden"] is True


def test_arm_binds_only_explicit_g15_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt = _armed(tmp_path, monkeypatch)
    assert plan["outcome_paths"] == ["renders/ng_refine_s95/g15_actual_fixed.json"]
    assert receipt["g15_outcome_paths"] == plan["outcome_paths"]
    assert receipt["fixed_g15_outcomes_explicitly_bound"] is True


def test_arm_rejects_missing_g15_outcome_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt = _compiled(tmp_path, monkeypatch)
    with pytest.raises(arm.CorpusExecutorPipelineArmV29Error):
        arm.build_armed_plan(plan, receipt, g15_outcome_paths=[])


def test_arm_rejects_g16_outcome_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt = _compiled(tmp_path, monkeypatch)
    with pytest.raises(arm.CorpusExecutorPipelineArmV29Error):
        arm.build_armed_plan(
            plan,
            receipt,
            g15_outcome_paths=["renders/ng_refine_s95/g16_actual.json"],
        )


def test_arm_rejects_fixed_g16_publication_enablement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt = _armed(tmp_path, monkeypatch)
    tampered = copy.deepcopy(plan)
    tampered["stages"][-1]["enabled"] = True
    tampered = _refingerprint(tampered)
    with pytest.raises(arm.CorpusExecutorPipelineArmV29Error):
        arm.validate_arm_receipt(receipt, armed_plan=tampered)


def test_arm_rejects_refingerprinted_compiler_provenance_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt = _armed(tmp_path, monkeypatch)
    bad = copy.deepcopy(receipt)
    bad["compiler_receipt"]["fingerprint"] = "0" * 64
    bad.pop("fingerprint")
    bad["fingerprint"] = compiler._fp(bad)
    with pytest.raises(arm.CorpusExecutorPipelineArmV29Error):
        arm.validate_arm_receipt(bad, armed_plan=plan)


def test_preflight_accepts_exact_g16_blind_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt = _armed(tmp_path, monkeypatch)
    preflight._check_plan(plan)
    validated = preflight._validated_arm(plan, receipt)
    assert validated["fingerprint"] == receipt["fingerprint"]


def test_preflight_rejects_publication_before_g16_outcome_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, _ = _armed(tmp_path, monkeypatch)
    tampered = copy.deepcopy(plan)
    tampered["stages"][-2]["enabled"] = True
    tampered = _refingerprint(tampered)
    with pytest.raises(preflight.HistoricalRefinementPreflightV30Error):
        preflight._check_plan(tampered)


def test_preflight_rejects_entrypoint_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, _ = _armed(tmp_path, monkeypatch)
    tampered = copy.deepcopy(plan)
    target = next(
        row for row in tampered["stages"] if row["key"] == "g16_attribution_bound_curve_lock"
    )
    target["argv"][1] = "substituted.py"
    tampered = _refingerprint(tampered)
    with pytest.raises(Exception):
        preflight._check_plan(tampered)


def test_preflight_rejects_removed_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, _ = _armed(tmp_path, monkeypatch)
    tampered = copy.deepcopy(plan)
    tampered["stages"] = [
        row for row in tampered["stages"] if row["key"] != "g16_attribution_bound_curve_lock"
    ]
    tampered = _refingerprint(tampered)
    with pytest.raises(Exception):
        preflight._check_plan(tampered)


def test_preflight_requires_all_protected_blind_and_brain_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, _ = _armed(tmp_path, monkeypatch)
    tampered = copy.deepcopy(plan)
    tampered["protected_paths"] = [
        row for row in tampered["protected_paths"] if row["role"] != "g16_blind_forecast"
    ]
    tampered = _refingerprint(tampered)
    with pytest.raises(preflight.HistoricalRefinementPreflightV30Error):
        preflight._check_plan(tampered)


def test_permanent_authority_wall_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipt = _armed(tmp_path, monkeypatch)
    assert plan["random_shuffle_used"] is False
    assert plan["blind_forecasts_immutable"] is True
    assert plan["may_update_ng_brain"] is False
    assert plan["execution_authority"] is False
    assert plan["cme_event_contracts_mode"] == "SHADOW"
    assert plan["brokerage_contract"] == "tastytrade_not_ibkr"
    assert plan["options_lane_started"] is False
    assert receipt["may_change_g16_blind_prior"] is False


def test_arm_inputs_are_not_mutated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    compiled, compiler_receipt = _compiled(tmp_path, monkeypatch)
    original_plan = copy.deepcopy(compiled)
    original_receipt = copy.deepcopy(compiler_receipt)
    arm.build_armed_plan(
        compiled,
        compiler_receipt,
        g15_outcome_paths=["renders/ng_refine_s95/g15_actual_fixed.json"],
    )
    assert compiled == original_plan
    assert compiler_receipt == original_receipt


def test_executor_v34_calls_real_execute_next(monkeypatch: pytest.MonkeyPatch):
    seen = {}

    def fake_execute_next(*args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return {"status": "DRY_RUN", "stage": "corpus_expected_day_contract"}

    monkeypatch.setattr(executor.legacy_executor, "execute_next", fake_execute_next)
    result = executor.execute_next("plan", "ledger", dry_run=True)
    assert result["status"] == "DRY_RUN"
    assert seen["args"] == ("plan", "ledger")
    assert seen["kwargs"]["dry_run"] is True


def test_executor_v34_run_next_is_compatibility_alias(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        executor,
        "execute_next",
        lambda *args, **kwargs: {"status": "CONFIGURATION_REQUIRED"},
    )
    assert executor.run_next("plan", "ledger")["status"] == "CONFIGURATION_REQUIRED"
