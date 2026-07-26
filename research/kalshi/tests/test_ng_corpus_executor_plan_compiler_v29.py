from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_corpus_executor_plan_compiler_v29 as compiler


def _ready_manifest(tmp_path: Path):
    return compiler.build_extension_manifest(
        artifact_dir=tmp_path,
        commands=compiler._selftest_commands(tmp_path),
    )


def test_extension_is_exact_v33_to_v38_suffix():
    assert compiler.EXTENSION_STAGES[0] == "g15_g16_counterfactual_lineage"
    assert "g15_g16_attribution_bound_lineage" in compiler.EXTENSION_STAGES
    assert "g16_attribution_bound_causal_authorization" in compiler.EXTENSION_STAGES
    assert "g16_attribution_bound_curve_authorization" in compiler.EXTENSION_STAGES
    assert "g16_attribution_bound_curve_lock" in compiler.EXTENSION_STAGES
    assert compiler.EXTENSION_STAGES[-1] == "g16_attribution_bound_publication"


def test_ready_manifest_binds_every_extension_stage(tmp_path: Path):
    manifest = _ready_manifest(tmp_path)
    checked = compiler.validate_extension_manifest(manifest)
    assert checked["status"] == compiler.MANIFEST_READY
    assert checked["blockers"] == []
    assert set(checked["commands"]) == set(compiler.EXTENSION_STAGES)
    assert checked["all_extension_stages_disabled_at_compile"] is True
    assert checked["outcome_paths_exposed_at_compile"] is False


def test_missing_commands_are_visible_stand_downs(tmp_path: Path):
    manifest = compiler.build_extension_manifest(artifact_dir=tmp_path, commands={})
    assert manifest["status"] == compiler.MANIFEST_BLOCKED
    assert len(manifest["blockers"]) == len(compiler.EXTENSION_STAGES)
    assert manifest["stand_downs"]
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV29Error):
        compiler.validate_extension_manifest(manifest)


def test_entrypoint_substitution_fails_even_when_refingerprinted(tmp_path: Path):
    manifest = _ready_manifest(tmp_path)
    key = compiler.EXTENSION_STAGES[0]
    manifest["commands"][key][1] = "substituted.py"
    manifest.pop("fingerprint")
    manifest["fingerprint"] = compiler._fp(manifest)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV29Error):
        compiler.validate_extension_manifest(manifest)


def test_primary_output_substitution_fails(tmp_path: Path):
    manifest = _ready_manifest(tmp_path)
    key = compiler.EXTENSION_STAGES[-1]
    manifest["primary_output_paths"][key] = str(tmp_path / "wrong.json")
    manifest.pop("fingerprint")
    manifest["fingerprint"] = compiler._fp(manifest)
    with pytest.raises(compiler.CorpusExecutorPlanCompilerV29Error):
        compiler.validate_extension_manifest(manifest)


@pytest.mark.parametrize(
    "forbidden",
    [
        "--broker ibkr",
        "--brain knowledge/ng_brain.json",
        "--random-shuffle",
        "python nymex_options_agent.py",
    ],
)
def test_forbidden_authority_paths_block_manifest(tmp_path: Path, forbidden: str):
    commands = compiler._selftest_commands(tmp_path)
    key = compiler.EXTENSION_STAGES[0]
    commands[key].append(forbidden)
    manifest = compiler.build_extension_manifest(artifact_dir=tmp_path, commands=commands)
    assert manifest["status"] == compiler.MANIFEST_BLOCKED
    assert any(key in blocker for blocker in manifest["blockers"])


def test_outcome_classification_is_derived_from_readiness(tmp_path: Path):
    manifest = _ready_manifest(tmp_path)
    by_key = {spec.key: spec for spec in compiler.readiness.STAGES}
    assert manifest["requires_fixed_outcomes"] == {
        key: (not by_key[key].pre_outcome) for key in compiler.EXTENSION_STAGES
    }


def test_complete_plan_configures_all_stages_but_enables_only_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(compiler.v28, "validate_receipt", lambda *args, **kwargs: None)
    upstream_plan = {
        "fingerprint": "p" * 64,
        "stages": [
            {"key": key, "argv": ["python", f"{key}.py"]}
            for key in compiler.PREFIX_STAGES
        ],
    }
    upstream_receipt = {"fingerprint": "r" * 64}
    plan, receipt = compiler.build_compiled_plan(
        artifact_dir=tmp_path,
        working_directory=tmp_path,
        upstream_plan=upstream_plan,
        upstream_receipt=upstream_receipt,
        extension_manifest=_ready_manifest(tmp_path),
        verify_files=False,
    )
    rows = {row["key"]: row for row in plan["stages"]}
    assert list(rows) == list(compiler.READINESS_STAGES)
    assert rows["corpus_expected_day_contract"]["enabled"] is True
    assert all(
        row["enabled"] is False
        for key, row in rows.items()
        if key != "corpus_expected_day_contract"
    )
    assert plan["outcome_paths"] == []
    assert receipt["status"] == compiler.STATUS
    assert receipt["all_extension_stages_configured_but_disabled"] is True
    assert receipt["options_lane_started"] is False


def test_manifest_input_is_not_mutated(tmp_path: Path):
    manifest = _ready_manifest(tmp_path)
    original = copy.deepcopy(manifest)
    compiler.validate_extension_manifest(manifest)
    assert manifest == original
