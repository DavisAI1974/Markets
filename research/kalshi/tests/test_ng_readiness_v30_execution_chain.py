from pathlib import Path

import pytest

import ng_corpus_executor_pipeline_arm_v25 as arm
import ng_corpus_executor_plan_compiler_v25 as compiler
import ng_corpus_source_identity_attestation as identity
import ng_historical_refinement_executor_v26 as executor
import ng_historical_refinement_preflight_v26 as preflight
import ng_historical_refinement_readiness_v30 as readiness


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


def test_v30_configured_prefix_inserts_source_identity_before_inspection():
    keys = list(compiler.CONFIGURED_STAGES)
    assert keys.index("corpus_s3_materialization_provenance") < keys.index(
        "corpus_source_identity_attestation"
    ) < keys.index("corpus_coverage")
    assert keys == [spec.key for spec in readiness.STAGES[: len(keys)]]


def test_source_identity_command_binds_provenance_plan_and_output(tmp_path):
    paths = _paths(tmp_path)
    argv = compiler._commands(**paths)["corpus_source_identity_attestation"]
    assert argv[:3] == ["python", "ng_corpus_source_identity_attestation.py", "build"]
    assert argv[3:] == [
        "--provenance",
        str(paths["materialization_provenance_path"].resolve()),
        "--plan",
        str(paths["broad_plan_path"].resolve()),
        "--out",
        str(paths["source_identity_path"].resolve()),
    ]


def test_compiled_plan_enables_only_expected_day_contract(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    rows = {row["key"]: row for row in plan["stages"]}
    assert rows["corpus_expected_day_contract"]["enabled"] is True
    for key in compiler.CONFIGURED_STAGES[1:]:
        assert rows[key]["enabled"] is False


def test_compiled_plan_uses_canonical_identity_contract(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    row = {item["key"]: item for item in plan["stages"]}[
        "corpus_source_identity_attestation"
    ]
    assert row["expected_output"] == "ng_corpus_source_identity_attestation.json"
    assert row["suggested_entrypoint"] == [
        "python",
        "ng_corpus_source_identity_attestation.py",
        "build",
    ]
    assert row["requires_fixed_outcomes"] is False


def test_command_substitution_is_rejected(tmp_path):
    plan, commands = _compiled_plan(tmp_path)
    bad = dict(commands)
    bad["corpus_source_identity_attestation"] = ["python", "other.py", "build"]
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV25Error):
        compiler._validate_plan(plan, bad, compiled=True)


def test_source_identity_receipt_requires_exact_provenance_and_plan(monkeypatch):
    authority = identity._authority_fields()
    provenance = {
        "fingerprint": "p" * 64,
        "source_materializations_fingerprint": "m" * 64,
        "source_count": 2,
        **authority,
    }
    plan = {"plan_fingerprint": "q" * 64}
    receipt = {
        "status": identity.READY_STATUS,
        "blockers": [],
        "all_source_native_identities_attested": True,
        "dataset_publisher_instrument_symbol_and_period_bound_to_source_bytes": True,
        "identity_inferred_from_filename_or_s3_key": False,
        "next_action": "RUN_BYTE_LEVEL_CORPUS_INSPECTION",
        "materializer_provenance_receipt": provenance,
        "materializer_provenance_fingerprint": provenance["fingerprint"],
        "plan": plan,
        "plan_fingerprint": plan["plan_fingerprint"],
        "source_materializations_fingerprint": provenance[
            "source_materializations_fingerprint"
        ],
        "source_identity_evidence_fingerprint": "e" * 64,
        "source_count": 2,
        "fingerprint": "i" * 64,
        **authority,
    }
    monkeypatch.setattr(compiler.identity_gate, "validate_attestation", lambda value: value)
    checked = compiler._validate_source_identity(
        provenance_receipt=provenance,
        broad_plan=plan,
        identity_receipt=receipt,
    )
    assert checked["source_count"] == 2
    bad = dict(receipt)
    bad["materializer_provenance_fingerprint"] = "x" * 64
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV25Error):
        compiler._validate_source_identity(
            provenance_receipt=provenance,
            broad_plan=plan,
            identity_receipt=bad,
        )


def test_arm_enables_only_historical_prefix(tmp_path):
    plan, commands = _compiled_plan(tmp_path)
    armed = arm._arm(plan, commands)
    rows = {row["key"]: row for row in armed["stages"]}
    for key in arm.ARMED_STAGES:
        assert rows[key]["enabled"] is True
        assert rows[key]["requires_fixed_outcomes"] is False
    for spec in readiness.STAGES[len(arm.ARMED_STAGES) :]:
        assert rows[spec.key]["enabled"] is False


def test_preflight_accepts_canonical_v30_plan(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    preflight._check_plan(plan)


def test_preflight_rejects_removed_identity_stage(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    plan["stages"] = [
        row for row in plan["stages"] if row["key"] != "corpus_source_identity_attestation"
    ]
    with pytest.raises(Exception):
        preflight._check_plan(plan)


def test_preflight_contract_binds_executor_and_readiness():
    assert preflight.EXECUTOR_CONTRACT == "ng_historical_refinement_executor_v26"
    assert preflight.READINESS_CONTRACT == readiness.SCHEMA
    assert preflight.STAGE_ORDER == [spec.key for spec in readiness.STAGES]


def test_permanent_authority_wall_remains_closed():
    fields = identity._authority_fields()
    assert fields["actual_outcomes_used"] is False
    assert fields["paid_live_data_assumed"] is False
    assert fields["random_shuffle_used"] is False
    assert fields["one_signal_authority_preserved"] is True
    assert fields["blind_forecasts_immutable"] is True
    assert fields["may_update_ng_brain"] is False
    assert fields["execution_authority"] is False
    assert fields["cme_event_contracts_mode"] == "SHADOW"
    assert fields["brokerage_contract"] == "tastytrade_not_ibkr"
    assert fields["options_lane_started"] is False


def test_g15_and_g16_stages_remain_disabled_in_compiled_plan(tmp_path):
    plan, _ = _compiled_plan(tmp_path)
    rows = {row["key"]: row for row in plan["stages"]}
    for key in (
        "g15_exact_replay",
        "g15_refine",
        "g15_score",
        "g16_pre_cutoff_context",
        "g16_refined_curve",
    ):
        if key in rows:
            assert rows[key]["enabled"] is False
