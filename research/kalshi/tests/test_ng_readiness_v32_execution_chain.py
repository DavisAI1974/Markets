import copy
import hashlib
from pathlib import Path

import pytest

import ng_corpus_executor_pipeline_arm_v27 as arm
import ng_corpus_executor_plan_compiler_v27 as compiler
import ng_g15_counterfactual_attribution as attribution_module
import ng_historical_refinement_executor_v28 as executor
import ng_historical_refinement_preflight_v28 as preflight
import ng_historical_refinement_readiness_v32 as readiness


def _paths(root: Path) -> dict[str, Path]:
    names = {
        "artifact_dir": "artifacts",
        "resolution_spec_path": "resolution_spec.json",
        "expected_day_receipt_path": "expected_days.json",
        "finalization_receipt_path": "finalization.json",
        "resolution_receipt_path": "resolution.json",
        "capture_spec_path": "capture_spec.json",
        "capture_receipt_path": "capture.json",
        "materialization_spec_path": "materialization_spec.json",
        "materialization_receipt_path": "materialization.json",
        "materialization_provenance_path": "provenance.json",
        "source_identity_path": "source_identity.json",
        "inventory_receipt_path": "inventory.json",
        "broad_plan_path": "broad_plan.json",
        "slice_bundle_path": "slices.json",
        "target_plan_path": "target_plan.json",
        "g15_bridge_path": "g15_bridge.json",
        "prepared_index_path": "prepared_index.json",
        "prepared_identity_path": "prepared_identity.json",
        "g15_replay_path": "g15_replay.json",
        "g15_anchor_path": "g15_anchor.json",
        "g15_blind_prior_path": "g15_blind_prior.json",
        "g15_blind_forecast_path": "g15_blind_forecast.json",
        "g15_pipeline_path": "g15_pipeline.json",
        "g15_refine_stream_path": "g15_refine_stream.json",
        "g15_completion_path": "g15_exact_replay_completion.json",
        "g15_refinement_authorization_path": "g15_exact_refinement_authorization.json",
        "g15_attribution_path": "g15_counterfactual_attribution.json",
        "g15_attribution_authorization_path": "g15_counterfactual_attribution_authorization.json",
    }
    return {key: root / value for key, value in names.items()}


def _commands(root: Path) -> dict[str, list[str]]:
    return compiler._commands(**_paths(root))


def _compiled_plan(root: Path):
    commands = _commands(root)
    plan = executor.build_plan(root / "artifacts", root / "work")
    for key in compiler.CONFIGURED_STAGES:
        plan = executor.configure_stage(
            plan,
            key,
            commands[key],
            enabled=key == "corpus_expected_day_contract",
        )
    compiler._validate_plan(plan, commands, compiled=True)
    return plan, commands


def _synthetic_chain():
    replay = {"streams": []}
    anchor = {"anchor_fingerprint": "h" * 64}
    refine_stream = {"outputs": []}
    blind = b"blind-forecast\n"
    completion = {"completion_fingerprint": "c" * 64}
    pipeline = {
        "pipeline_fingerprint": "p" * 64,
        "replay": copy.deepcopy(replay),
        "anchor": copy.deepcopy(anchor),
        "refine_stream": copy.deepcopy(refine_stream),
    }
    refinement = {
        "authorization_fingerprint": "r" * 64,
        "blind_forecast_sha256": hashlib.sha256(blind).hexdigest(),
    }
    attribution = {"fingerprint": "a" * 64}
    authorization = {
        "authorization_fingerprint": "u" * 64,
        "replay_fingerprint": "e" * 64,
        "anchor_fingerprint": anchor["anchor_fingerprint"],
        "refine_stream_fingerprint": "s" * 64,
        "factor_summary_fingerprint": "f" * 64,
        "per_day_fingerprint": "d" * 64,
        "rows_fingerprint": "w" * 64,
        "lesson_proposals_fingerprint": "l" * 64,
        "n_states": 12,
        "n_days": 12,
        "factors": list(attribution_module.FACTORS),
        "all_six_factors_quantified": True,
        "lesson_proposals_brain_write_forbidden": True,
        "actual_outcomes_used": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_blind_prior": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "g16_authorized": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "LOCK_G15_REFINED_FORECAST_AND_SCORE_BLIND_REFINED_SEPARATELY",
    }
    return {
        "bridge": {},
        "prepared_index": {},
        "replay": replay,
        "anchor": anchor,
        "blind_prior": {},
        "blind_forecast_bytes": blind,
        "completion": completion,
        "pipeline": pipeline,
        "refinement_authorization": refinement,
        "refine_stream": refine_stream,
        "attribution": attribution,
        "attribution_authorization": authorization,
    }


def _stub_chain_validators(monkeypatch):
    monkeypatch.setattr(compiler.replay_completion, "validate_completion", lambda *a, **k: None)
    monkeypatch.setattr(compiler.refinement_gate, "validate_authorization", lambda *a, **k: None)
    monkeypatch.setattr(compiler.attribution_module, "validate_report", lambda *a, **k: None)
    monkeypatch.setattr(compiler.attribution_gate, "validate_authorization", lambda *a, **k: None)
    monkeypatch.setattr(compiler, "_authority", lambda *a, **k: None)


def test_v32_configured_prefix_ends_at_authorization_before_publication():
    order = [spec.key for spec in readiness.STAGES]
    keys = list(compiler.CONFIGURED_STAGES)
    assert keys == order[: len(keys)]
    assert keys[-4:] == [
        "g15_exact_replay",
        "g15_exact_refinement",
        "g15_counterfactual_attribution",
        "g15_counterfactual_attribution_authorization",
    ]
    assert order[len(keys)] == "g15_publication"


def test_executor_exposes_canonical_attribution_entrypoint():
    assert executor.SUGGESTED_ENTRYPOINTS["g15_counterfactual_attribution"] == (
        "python",
        "ng_g15_counterfactual_attribution.py",
    )


def test_g15_commands_bind_all_causal_inputs_and_outputs(tmp_path):
    paths = _paths(tmp_path)
    commands = compiler._commands(**paths)
    assert commands["g15_exact_replay"][:2] == [
        "python",
        "ng_g15_exact_replay_completion.py",
    ]
    for flag in ("--bridge", "--prepared-index", "--replay", "--anchor", "--blind-prior", "--out"):
        assert flag in commands["g15_exact_replay"]
    for flag in ("--completion", "--pipeline", "--blind-forecast", "--out"):
        assert flag in commands["g15_exact_refinement"]
    for flag in ("--replay", "--anchor", "--refine-stream", "--out"):
        assert flag in commands["g15_counterfactual_attribution"]
    for flag in ("--completion", "--pipeline", "--refinement-authorization", "--attribution", "--out"):
        assert flag in commands["g15_counterfactual_attribution_authorization"]


def test_compiled_plan_enables_only_expected_day_contract(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    rows = {row["key"]: row for row in plan["stages"]}
    assert rows["corpus_expected_day_contract"]["enabled"] is True
    for key in compiler.CONFIGURED_STAGES[1:]:
        assert rows[key]["enabled"] is False
    assert rows["g15_publication"]["enabled"] is False


def test_compiled_plan_uses_canonical_g15_contracts(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    rows = {row["key"]: row for row in plan["stages"]}
    assert rows["g15_counterfactual_attribution"]["suggested_entrypoint"] == [
        "python",
        "ng_g15_counterfactual_attribution.py",
    ]
    assert rows["g15_counterfactual_attribution_authorization"]["expected_output"] == (
        "g15_counterfactual_attribution_authorization.json"
    )
    assert rows["g15_counterfactual_attribution_authorization"]["requires_fixed_outcomes"] is False
    assert rows["g15_publication"]["requires_fixed_outcomes"] is True


def test_g15_command_substitution_is_rejected(tmp_path):
    plan, commands = _compiled_plan(tmp_path)
    bad = copy.deepcopy(commands)
    bad["g15_counterfactual_attribution"] = ["python", "other.py"]
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV27Error):
        compiler._validate_plan(plan, bad, compiled=True)


def test_g15_chain_validation_requires_all_six_factors(monkeypatch):
    _stub_chain_validators(monkeypatch)
    values = _synthetic_chain()
    result = compiler._validate_g15_chain(**values)
    assert result["n_days"] == 12
    assert result["factors"] == list(attribution_module.FACTORS)


def test_g15_chain_rejects_brain_write_escalation(monkeypatch):
    _stub_chain_validators(monkeypatch)
    values = _synthetic_chain()
    values["attribution_authorization"]["may_update_ng_brain"] = True
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV27Error):
        compiler._validate_g15_chain(**values)


def test_arm_enables_pre_outcome_g15_chain_but_not_publication(tmp_path):
    plan, commands = _compiled_plan(tmp_path)
    armed = arm._arm(plan, commands)
    rows = {row["key"]: row for row in armed["stages"]}
    for key in arm.ARMED_STAGES:
        assert rows[key]["enabled"] is True
        assert rows[key]["requires_fixed_outcomes"] is False
    assert rows["g15_publication"]["enabled"] is False
    for spec in readiness.STAGES[len(arm.ARMED_STAGES) :]:
        assert rows[spec.key]["enabled"] is False


def test_preflight_accepts_canonical_v32_plan(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    preflight._check_plan(plan)


def test_preflight_rejects_removed_attribution_authorization(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    plan["stages"] = [
        row
        for row in plan["stages"]
        if row["key"] != "g15_counterfactual_attribution_authorization"
    ]
    with pytest.raises(Exception):
        preflight._check_plan(plan)


def test_preflight_rejects_authorization_after_publication(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    rows = list(plan["stages"])
    auth_index = next(
        i for i, row in enumerate(rows)
        if row["key"] == "g15_counterfactual_attribution_authorization"
    )
    publication_index = next(i for i, row in enumerate(rows) if row["key"] == "g15_publication")
    rows[auth_index], rows[publication_index] = rows[publication_index], rows[auth_index]
    plan["stages"] = rows
    with pytest.raises(Exception):
        preflight._check_plan(plan)


def test_permanent_authority_wall_remains_closed():
    fixture = readiness._linked_fixture_chain()[
        "g15_counterfactual_attribution_authorization"
    ]
    assert fixture["actual_outcomes_used"] is False
    assert fixture["random_shuffle_used"] is False
    assert fixture["one_signal_authority_preserved"] is True
    assert fixture["blind_forecasts_immutable"] is True
    assert fixture["may_update_ng_brain"] is False
    assert fixture["execution_authority"] is False
    assert fixture["g16_authorized"] is False
    assert fixture["cme_event_contracts_mode"] == "SHADOW"
    assert fixture["brokerage_contract"] == "tastytrade_not_ibkr"
    assert fixture["options_lane_started"] is False
