from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_corpus_executor_plan_compiler_v31 as compiler_v31
import ng_v38_execution_command_lineage_gate as gate


def _manifest(tmp_path: Path):
    commands = gate.compiler._selftest_commands(tmp_path)
    paths = gate._canonical_paths(tmp_path)
    for target_key, sources in gate._required_sources().items():
        for index, source_key in enumerate(sources):
            commands[target_key].extend([f"--source-{index}", paths[source_key]])
    commands["g16_counterfactual_publication"].extend(
        ["--actual", str((tmp_path / "g16_actual_fixed.json").resolve(strict=False))]
    )
    return gate.compiler.build_extension_manifest(artifact_dir=tmp_path, commands=commands)


def _refingerprint(value):
    value.pop("fingerprint", None)
    value["fingerprint"] = gate._fp(value)
    return value


def test_ready_gate_binds_every_readiness_link(tmp_path: Path):
    manifest = _manifest(tmp_path)
    result = gate.build_gate(manifest, artifact_dir=tmp_path)
    checked = gate.validate_gate(result, extension_manifest=manifest, artifact_dir=tmp_path)
    assert checked["status"] == gate.READY
    assert checked["blockers"] == []
    assert checked["g16_actual_exposed_only_at_counterfactual_publication"] is True
    assert checked["g16_actual_path"].endswith("g16_actual_fixed.json")
    assert all(
        row["bound_exactly_once"]
        for rows in checked["command_source_bindings"].values()
        for row in rows
    )


def test_missing_source_artifact_is_visible_stand_down(tmp_path: Path):
    manifest = _manifest(tmp_path)
    ready = gate.build_gate(manifest, artifact_dir=tmp_path)
    target = next(key for key, rows in ready["command_source_bindings"].items() if rows)
    source_path = ready["command_source_bindings"][target][0]["source_artifact"]
    manifest["commands"][target].remove(source_path)
    _refingerprint(manifest)
    blocked = gate.build_gate(manifest, artifact_dir=tmp_path)
    assert blocked["status"] == gate.BLOCKED
    assert any("MISSING_SOURCE_ARTIFACT_BINDING" in item for item in blocked["blockers"])
    with pytest.raises(gate.V38ExecutionCommandLineageError):
        gate.validate_gate(blocked, extension_manifest=manifest, artifact_dir=tmp_path)


def test_duplicate_source_artifact_is_rejected(tmp_path: Path):
    manifest = _manifest(tmp_path)
    ready = gate.build_gate(manifest, artifact_dir=tmp_path)
    target = next(key for key, rows in ready["command_source_bindings"].items() if rows)
    source_path = ready["command_source_bindings"][target][0]["source_artifact"]
    manifest["commands"][target].append(source_path)
    _refingerprint(manifest)
    blocked = gate.build_gate(manifest, artifact_dir=tmp_path)
    assert any("AMBIGUOUS_SOURCE_ARTIFACT_BINDING" in item for item in blocked["blockers"])


def test_raw_actual_is_forbidden_before_g16_scoring(tmp_path: Path):
    manifest = _manifest(tmp_path)
    target = "g16_attribution_bound_curve_lock"
    manifest["commands"][target].extend(["--actual", str(tmp_path / "leaked.json")])
    _refingerprint(manifest)
    blocked = gate.build_gate(manifest, artifact_dir=tmp_path)
    assert f"{target}:RAW_ACTUAL_PATH_FORBIDDEN_BEFORE_SCORING" in blocked["blockers"]


def test_g16_publication_requires_exactly_one_actual(tmp_path: Path):
    manifest = _manifest(tmp_path)
    argv = manifest["commands"]["g16_counterfactual_publication"]
    index = argv.index("--actual")
    del argv[index : index + 2]
    _refingerprint(manifest)
    blocked = gate.build_gate(manifest, artifact_dir=tmp_path)
    assert "g16_counterfactual_publication:EXACT_G16_ACTUAL_BINDING_REQUIRED" in blocked["blockers"]


def test_nested_refingerprinted_tampering_is_rejected(tmp_path: Path):
    manifest = _manifest(tmp_path)
    result = gate.build_gate(manifest, artifact_dir=tmp_path)
    result["g16_actual_path"] = str(tmp_path / "substituted.json")
    _refingerprint(result)
    with pytest.raises(gate.V38ExecutionCommandLineageError):
        gate.validate_gate(result, extension_manifest=manifest, artifact_dir=tmp_path)


def test_gate_input_is_not_mutated(tmp_path: Path):
    manifest = _manifest(tmp_path)
    original = copy.deepcopy(manifest)
    gate.build_gate(manifest, artifact_dir=tmp_path)
    assert manifest == original


def test_v31_compiler_requires_cli_and_lineage_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    manifest = _manifest(tmp_path)
    lineage_receipt = gate.build_gate(manifest, artifact_dir=tmp_path)
    plan = {
        "artifact_dir": str(tmp_path),
        "fingerprint": "p" * 64,
        "stages": [
            {"key": key, "argv": list(argv)}
            for key, argv in manifest["commands"].items()
        ],
    }
    v30_receipt = {"fingerprint": "v" * 64, "command_contract_fingerprint": "c" * 64}
    monkeypatch.setattr(
        compiler_v31.v30,
        "build_compiled_plan",
        lambda **kwargs: (copy.deepcopy(plan), copy.deepcopy(v30_receipt)),
    )
    monkeypatch.setattr(compiler_v31.v30, "validate_receipt", lambda *args, **kwargs: None)
    compiled, receipt = compiler_v31.build_compiled_plan(
        artifact_dir=tmp_path,
        working_directory=tmp_path,
        upstream_plan={"fingerprint": "u" * 64},
        upstream_receipt={"fingerprint": "r" * 64},
        extension_manifest=manifest,
        command_contract={"fingerprint": "c" * 64},
        command_lineage=lineage_receipt,
        verify_files=False,
    )
    assert compiled == plan
    assert receipt["status"] == compiler_v31.STATUS
    assert receipt["all_required_cli_options_verified"] is True
    assert receipt["exact_command_source_bindings_verified"] is True
    assert receipt["g16_actual_path"].endswith("g16_actual_fixed.json")
    assert receipt["options_lane_started"] is False


def test_v31_compiler_rejects_blocked_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    manifest = _manifest(tmp_path)
    ready = gate.build_gate(manifest, artifact_dir=tmp_path)
    target = next(key for key, rows in ready["command_source_bindings"].items() if rows)
    source_path = ready["command_source_bindings"][target][0]["source_artifact"]
    manifest["commands"][target].remove(source_path)
    _refingerprint(manifest)
    blocked = gate.build_gate(manifest, artifact_dir=tmp_path)
    monkeypatch.setattr(compiler_v31.v30, "build_compiled_plan", lambda **kwargs: pytest.fail("must not compile"))
    with pytest.raises(compiler_v31.CorpusExecutorPlanCompilerV31Error):
        compiler_v31.build_compiled_plan(
            artifact_dir=tmp_path,
            working_directory=tmp_path,
            upstream_plan={},
            upstream_receipt={},
            extension_manifest=manifest,
            command_contract={"fingerprint": "c" * 64},
            command_lineage=blocked,
            verify_files=False,
        )


def test_permanent_authority_wall(tmp_path: Path):
    result = gate.build_gate(_manifest(tmp_path), artifact_dir=tmp_path)
    assert result["random_shuffle_used"] is False
    assert result["one_signal_authority_preserved"] is True
    assert result["blind_forecasts_immutable"] is True
    assert result["may_update_ng_brain"] is False
    assert result["execution_authority"] is False
    assert result["cme_event_contracts_mode"] == "SHADOW"
    assert result["brokerage_contract"] == "tastytrade_not_ibkr"
    assert result["options_lane_started"] is False
