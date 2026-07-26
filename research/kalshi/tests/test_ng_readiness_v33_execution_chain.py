from pathlib import Path

import pytest

import ng_corpus_executor_pipeline_arm_v28 as arm
import ng_corpus_executor_plan_compiler_v28 as compiler
import ng_historical_refinement_executor_v29 as executor
import ng_historical_refinement_preflight_v29 as preflight
import ng_historical_refinement_readiness_v33 as readiness


def _upstream_paths(root: Path) -> dict[str, Path]:
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
        "g15_completion_path": "g15_completion.json",
        "g15_refinement_authorization_path": "g15_refinement_authorization.json",
        "g15_attribution_path": "g15_attribution.json",
        "g15_attribution_authorization_path": "g15_attribution_authorization.json",
    }
    return {key: root / value for key, value in names.items()}


def _fixed_paths(root: Path) -> dict[str, Path]:
    names = {
        "publication_authorization_path": "g15_refinement_authorization.json",
        "blind_forecast_path": "g15_blind_forecast.json",
        "refined_forecast_path": "g15_refined_forecast.json",
        "actual_path": "g15_actual.json",
        "blind_score_path": "g15_blind_score.json",
        "refined_score_path": "g15_refined_score.json",
        "comparison_path": "g15_comparison.json",
        "publication_adjudication_path": "g15_publication_adjudication.json",
        "blind_render_rt_path": "g15_blind_rt.json",
        "refined_render_rt_path": "g15_refined_rt.json",
        "blind_render_png_path": "g15_mbo_blind_continuous.png",
        "refined_render_png_path": "g15_mbo_refined_continuous.png",
        "publication_path": "g15_publication.json",
        "attribution_authorization_path": "g15_attribution_authorization.json",
        "bound_publication_path": "g15_bound_publication.json",
        "replay_path": "g15_replay.json",
        "anchor_path": "g15_anchor.json",
        "refine_stream_path": "g15_refine_stream.json",
        "attribution_path": "g15_attribution.json",
        "daily_audit_path": "g15_daily_audit.json",
        "proposals_out_path": "g15_counterfactual_proposals.json",
        "counterfactual_adjudication_out_path": "g15_counterfactual_adjudication.json",
        "counterfactual_lessons_path": "g15_counterfactual_lessons.json",
    }
    return {key: root / value for key, value in names.items()}


def _commands(root: Path) -> dict[str, list[str]]:
    return compiler._commands(**_fixed_paths(root), **_upstream_paths(root))


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


def test_v33_configures_through_fixed_outcome_lesson_gate():
    order = [spec.key for spec in readiness.STAGES]
    assert list(compiler.CONFIGURED_STAGES) == order[: len(compiler.CONFIGURED_STAGES)]
    assert compiler.CONFIGURED_STAGES[-3:] == (
        "g15_publication",
        "g15_attribution_bound_publication",
        "g15_counterfactual_lesson_gate",
    )
    assert compiler.PRE_OUTCOME_STAGES[-1] == (
        "g15_counterfactual_attribution_authorization"
    )


def test_v33_tail_preserves_outcome_boundary_and_order():
    order = [spec.key for spec in readiness.STAGES]
    start = order.index("g15_counterfactual_attribution")
    assert order[start : start + 5] == [
        "g15_counterfactual_attribution",
        "g15_counterfactual_attribution_authorization",
        "g15_publication",
        "g15_attribution_bound_publication",
        "g15_counterfactual_lesson_gate",
    ]
    by_key = {spec.key: spec for spec in readiness.STAGES}
    assert by_key["g15_counterfactual_attribution_authorization"].pre_outcome is True
    assert by_key["g15_publication"].pre_outcome is False
    assert by_key["g15_attribution_bound_publication"].pre_outcome is False
    assert by_key["g15_counterfactual_lesson_gate"].pre_outcome is False


def test_publication_command_binds_separate_scores_and_canonical_renders(tmp_path):
    paths = _fixed_paths(tmp_path)
    argv = _commands(tmp_path)["g15_publication"]
    assert argv[:2] == ["python", "ng_g15_exact_publication_gate.py"]
    for flag in (
        "--blind-score",
        "--refined-score",
        "--comparison",
        "--blind-render-png",
        "--refined-render-png",
        "--out",
    ):
        assert flag in argv
    assert str(paths["blind_score_path"].resolve()) in argv
    assert str(paths["refined_score_path"].resolve()) in argv
    assert str(paths["blind_render_png_path"].resolve()) in argv
    assert str(paths["refined_render_png_path"].resolve()) in argv


def test_bound_publication_command_binds_authorization_publication_and_scores(tmp_path):
    paths = _fixed_paths(tmp_path)
    argv = _commands(tmp_path)["g15_attribution_bound_publication"]
    assert argv[:2] == ["python", "ng_g15_attribution_bound_publication_gate.py"]
    for flag in (
        "--attribution-authorization",
        "--publication",
        "--blind-score",
        "--refined-score",
        "--comparison",
        "--out",
    ):
        assert flag in argv
    assert str(paths["attribution_authorization_path"].resolve()) in argv
    assert str(paths["bound_publication_path"].resolve()) in argv


def test_lesson_command_uses_locked_counterfactual_support_and_fixed_comparison(tmp_path):
    paths = _fixed_paths(tmp_path)
    argv = _commands(tmp_path)["g15_counterfactual_lesson_gate"]
    assert argv[:2] == ["python", "ng_g15_counterfactual_lesson_gate.py"]
    for flag in (
        "--replay",
        "--anchor",
        "--refine-stream",
        "--attribution",
        "--audit",
        "--comparison",
        "--proposals-out",
        "--adjudication-out",
        "--out",
    ):
        assert flag in argv
    assert str(paths["daily_audit_path"].resolve()) in argv
    assert str(paths["comparison_path"].resolve()) in argv


def test_compiled_plan_enables_only_expected_day_contract(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    rows = {row["key"]: row for row in plan["stages"]}
    assert rows["corpus_expected_day_contract"]["enabled"] is True
    for key in compiler.CONFIGURED_STAGES[1:]:
        assert rows[key]["enabled"] is False
    for key in (
        "g15_publication",
        "g15_attribution_bound_publication",
        "g15_counterfactual_lesson_gate",
    ):
        assert rows[key]["requires_fixed_outcomes"] is True


def test_arm_enables_only_pre_outcome_prefix(tmp_path):
    plan, commands = _compiled_plan(tmp_path)
    armed = arm._arm(plan, commands)
    rows = {row["key"]: row for row in armed["stages"]}
    for key in arm.ARMED_STAGES:
        assert rows[key]["enabled"] is True
        assert rows[key]["requires_fixed_outcomes"] is False
    for key in (
        "g15_publication",
        "g15_attribution_bound_publication",
        "g15_counterfactual_lesson_gate",
    ):
        assert rows[key]["enabled"] is False
        assert rows[key]["requires_fixed_outcomes"] is True
    for spec in readiness.STAGES[len(compiler.CONFIGURED_STAGES) :]:
        assert rows[spec.key]["enabled"] is False


def test_preflight_accepts_canonical_v33_plan(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    preflight._check_plan(plan)


def test_preflight_rejects_lesson_enabled_before_publication_binding(tmp_path):
    plan, commands = _compiled_plan(tmp_path)
    bad = executor.configure_stage(
        plan,
        "g15_counterfactual_lesson_gate",
        commands["g15_counterfactual_lesson_gate"],
        enabled=True,
    )
    with pytest.raises(Exception):
        preflight._check_plan(bad)


def test_preflight_rejects_removed_attribution_binding_stage(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    plan["stages"] = [
        row
        for row in plan["stages"]
        if row["key"] != "g15_attribution_bound_publication"
    ]
    with pytest.raises(Exception):
        preflight._check_plan(plan)


def test_compiler_rejects_fixed_outcome_entrypoint_substitution(tmp_path):
    plan, commands = _compiled_plan(tmp_path)
    row = next(
        item for item in plan["stages"] if item["key"] == "g15_attribution_bound_publication"
    )
    row["suggested_entrypoint"] = ["python", "other.py"]
    with pytest.raises(Exception):
        compiler._validate_plan(plan, commands, compiled=True)


def test_preflight_contract_binds_executor_and_readiness_v33():
    assert preflight.EXECUTOR_CONTRACT == "ng_historical_refinement_executor_v29"
    assert preflight.READINESS_CONTRACT == readiness.SCHEMA
    assert preflight.STAGE_ORDER == [spec.key for spec in readiness.STAGES]


def test_permanent_authority_wall_remains_closed():
    fixture = readiness._linked_fixture_chain()["g15_attribution_bound_publication"]
    assert fixture["actual_g16_outcomes_used"] is False
    assert fixture["random_shuffle_used"] is False
    assert fixture["one_signal_authority_preserved"] is True
    assert fixture["blind_forecasts_immutable"] is True
    assert fixture["may_update_ng_brain"] is False
    assert fixture["execution_authority"] is False
    assert fixture["g16_outcome_access_authorized"] is False
    assert fixture["cme_event_contracts_mode"] == "SHADOW"
    assert fixture["brokerage_contract"] == "tastytrade_not_ibkr"
    assert fixture["options_lane_started"] is False
