from pathlib import Path

import pytest

import ng_corpus_executor_pipeline_arm_v26 as arm
import ng_corpus_executor_plan_compiler_v26 as compiler
import ng_g15_prepared_normalized_identity_guard as guard
import ng_historical_refinement_executor_v27 as executor
import ng_historical_refinement_preflight_v27 as preflight
import ng_historical_refinement_readiness_v31 as readiness


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


def test_v31_configured_prefix_ends_with_prepared_identity_before_replay():
    keys = list(compiler.CONFIGURED_STAGES)
    assert keys[-1] == "g15_prepared_normalized_identity"
    order = [spec.key for spec in readiness.STAGES]
    assert keys == order[: len(keys)]
    guard_index = order.index("g15_prepared_normalized_identity")
    assert order[guard_index - 1] == "broad_corpus_exact_partition"
    assert order[guard_index + 1] == "g15_exact_replay"


def test_prepared_identity_command_binds_bridge_index_and_output(tmp_path):
    paths = _paths(tmp_path)
    argv = compiler._commands(**paths)["g15_prepared_normalized_identity"]
    assert argv == [
        "python",
        "ng_g15_prepared_normalized_identity_guard.py",
        "build",
        "--bridge",
        str(paths["g15_bridge_path"].resolve()),
        "--prepared-index",
        str(paths["prepared_index_path"].resolve()),
        "--out",
        str(paths["prepared_identity_path"].resolve()),
    ]


def test_compiled_plan_enables_only_expected_day_contract(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    rows = {row["key"]: row for row in plan["stages"]}
    assert rows["corpus_expected_day_contract"]["enabled"] is True
    for key in compiler.CONFIGURED_STAGES[1:]:
        assert rows[key]["enabled"] is False
    assert rows["g15_exact_replay"]["enabled"] is False


def test_compiled_plan_uses_canonical_prepared_identity_contract(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    row = {item["key"]: item for item in plan["stages"]}[
        "g15_prepared_normalized_identity"
    ]
    assert row["expected_output"] == "g15_prepared_normalized_identity_guard.json"
    assert row["suggested_entrypoint"] == [
        "python",
        "ng_g15_prepared_normalized_identity_guard.py",
        "build",
    ]
    assert row["requires_fixed_outcomes"] is False


def test_command_substitution_is_rejected(tmp_path):
    plan, commands = _compiled_plan(tmp_path)
    bad = dict(commands)
    bad["g15_prepared_normalized_identity"] = ["python", "other.py", "build"]
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV26Error):
        compiler._validate_plan(plan, bad, compiled=True)


def test_prepared_identity_receipt_requires_exact_bridge_and_index(monkeypatch):
    bridge = {"fingerprint": "b" * 64}
    prepared = {"prepared_corpus_fingerprint": "p" * 64}
    receipt = {
        "status": guard.READY,
        "blockers": [],
        "all_publishers_explicit_and_positive": True,
        "all_rows_match_exact_manifest_identity": True,
        "all_events_within_definition_and_lane_periods": True,
        "all_sources_chronological": True,
        "definitions_precede_trade_and_mbo_replay": True,
        "next_action": "RUN_EXACT_G15_CAUSAL_REPLAY",
        "bridge": bridge,
        "prepared_index": prepared,
        "bridge_fingerprint": bridge["fingerprint"],
        "manifest_fingerprint": "m" * 64,
        "prepared_corpus_fingerprint": prepared["prepared_corpus_fingerprint"],
        "source_evidence_fingerprint": "e" * 64,
        "source_count": 26,
        "expected_source_count": 26,
        "fingerprint": "g" * 64,
    }
    monkeypatch.setattr(compiler.prepared_guard, "validate_guard", lambda *args, **kwargs: None)
    monkeypatch.setattr(compiler, "_authority", lambda *args, **kwargs: None)
    checked = compiler._validate_prepared_identity(
        bridge=bridge,
        prepared_index=prepared,
        guard_receipt=receipt,
        verify_files=False,
    )
    assert checked["source_count"] == 26
    bad = dict(receipt)
    bad["bridge_fingerprint"] = "x" * 64
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV26Error):
        compiler._validate_prepared_identity(
            bridge=bridge,
            prepared_index=prepared,
            guard_receipt=bad,
            verify_files=False,
        )


def test_prepared_identity_requires_canonical_source_count(monkeypatch):
    bridge = {"fingerprint": "b" * 64}
    prepared = {"prepared_corpus_fingerprint": "p" * 64}
    receipt = {
        "status": guard.READY,
        "blockers": [],
        "all_publishers_explicit_and_positive": True,
        "all_rows_match_exact_manifest_identity": True,
        "all_events_within_definition_and_lane_periods": True,
        "all_sources_chronological": True,
        "definitions_precede_trade_and_mbo_replay": True,
        "next_action": "RUN_EXACT_G15_CAUSAL_REPLAY",
        "bridge": bridge,
        "prepared_index": prepared,
        "bridge_fingerprint": bridge["fingerprint"],
        "manifest_fingerprint": "m" * 64,
        "prepared_corpus_fingerprint": prepared["prepared_corpus_fingerprint"],
        "source_evidence_fingerprint": "e" * 64,
        "source_count": 25,
        "expected_source_count": 26,
        "fingerprint": "g" * 64,
    }
    monkeypatch.setattr(compiler.prepared_guard, "validate_guard", lambda *args, **kwargs: None)
    monkeypatch.setattr(compiler, "_authority", lambda *args, **kwargs: None)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV26Error):
        compiler._validate_prepared_identity(
            bridge=bridge,
            prepared_index=prepared,
            guard_receipt=receipt,
            verify_files=False,
        )


def test_arm_enables_only_historical_prefix_and_not_replay(tmp_path):
    plan, commands = _compiled_plan(tmp_path)
    armed = arm._arm(plan, commands)
    rows = {row["key"]: row for row in armed["stages"]}
    for key in arm.ARMED_STAGES:
        assert rows[key]["enabled"] is True
        assert rows[key]["requires_fixed_outcomes"] is False
    assert rows["g15_exact_replay"]["enabled"] is False
    for spec in readiness.STAGES[len(arm.ARMED_STAGES) :]:
        assert rows[spec.key]["enabled"] is False


def test_preflight_accepts_canonical_v31_plan(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    preflight._check_plan(plan)


def test_preflight_rejects_removed_prepared_identity_stage(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    plan["stages"] = [
        row for row in plan["stages"] if row["key"] != "g15_prepared_normalized_identity"
    ]
    with pytest.raises(Exception):
        preflight._check_plan(plan)


def test_preflight_rejects_prepared_identity_after_replay(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    rows = list(plan["stages"])
    guard_index = next(i for i, row in enumerate(rows) if row["key"] == "g15_prepared_normalized_identity")
    replay_index = next(i for i, row in enumerate(rows) if row["key"] == "g15_exact_replay")
    rows[guard_index], rows[replay_index] = rows[replay_index], rows[guard_index]
    plan["stages"] = rows
    with pytest.raises(Exception):
        preflight._check_plan(plan)


def test_preflight_contract_binds_executor_and_readiness():
    assert preflight.EXECUTOR_CONTRACT == "ng_historical_refinement_executor_v27"
    assert preflight.READINESS_CONTRACT == readiness.SCHEMA
    assert preflight.STAGE_ORDER == [spec.key for spec in readiness.STAGES]


def test_permanent_authority_wall_remains_closed():
    fixture = readiness._linked_fixture_chain()["g15_prepared_normalized_identity"]
    assert fixture["actual_outcomes_used"] is False
    assert fixture["paid_live_data_assumed"] is False
    assert fixture["random_shuffle_used"] is False
    assert fixture["one_signal_authority_preserved"] is True
    assert fixture["blind_forecasts_immutable"] is True
    assert fixture["may_update_ng_brain"] is False
    assert fixture["execution_authority"] is False
    assert fixture["cme_event_contracts_mode"] == "SHADOW"
    assert fixture["brokerage_contract"] == "tastytrade_not_ibkr"
    assert fixture["options_lane_started"] is False
