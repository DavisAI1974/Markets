from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_corpus_executor_plan_compiler_v30 as compiler


def _base(tmp_path: Path):
    manifest = {"fingerprint": "m" * 64, "commands": {"x": ["python", "x.py", "--out", "x.json"]}}
    contract = {
        "fingerprint": "c" * 64,
        "extension_manifest_fingerprint": manifest["fingerprint"],
        "working_directory": str(tmp_path.resolve()),
        "help_only_probe": True,
        "corpus_files_opened": False,
        "outcome_files_opened": False,
    }
    plan = {
        "fingerprint": "p" * 64,
        "stages": [{"key": "x", "argv": ["python", "x.py", "--out", "x.json"]}],
    }
    v29_receipt = {"fingerprint": "r" * 64, "extension_manifest": manifest}
    return manifest, contract, plan, v29_receipt


def _patch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    manifest, contract, plan, v29_receipt = _base(tmp_path)
    monkeypatch.setattr(compiler, "READINESS_STAGES", ("x",))
    monkeypatch.setattr(compiler.v29, "validate_extension_manifest", lambda value, require_ready=True: copy.deepcopy(dict(value)))
    monkeypatch.setattr(compiler.command_gate, "validate_gate", lambda value, **kwargs: copy.deepcopy(dict(value)))
    monkeypatch.setattr(compiler.v29, "build_compiled_plan", lambda **kwargs: (copy.deepcopy(plan), copy.deepcopy(v29_receipt)))
    monkeypatch.setattr(compiler.v29, "validate_receipt", lambda *args, **kwargs: copy.deepcopy(v29_receipt))
    monkeypatch.setattr(compiler, "_validate_plan", lambda *args, **kwargs: None)
    monkeypatch.setattr(compiler.v29, "_commands_from_plan", lambda value, keys: {"x": ["python", "x.py", "--out", "x.json"]})
    return manifest, contract, plan, v29_receipt


def test_compiler_requires_ready_command_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manifest, contract, plan, _ = _patch(monkeypatch, tmp_path)
    built_plan, receipt = compiler.build_compiled_plan(
        artifact_dir=tmp_path,
        working_directory=tmp_path,
        upstream_plan={"fingerprint": "u" * 64},
        upstream_receipt={"fingerprint": "q" * 64},
        extension_manifest=manifest,
        command_contract=contract,
        verify_files=False,
        verify_runtime_contract=False,
    )
    assert built_plan == plan
    assert receipt["status"] == compiler.STATUS
    assert receipt["command_contract_fingerprint"] == contract["fingerprint"]
    assert receipt["all_required_cli_options_verified"] is True
    assert receipt["may_change_blind_forecast"] is False
    assert "max_change_blind_forecast" not in receipt
    assert receipt["options_lane_started"] is False


def test_manifest_fingerprint_mismatch_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manifest, contract, _, _ = _patch(monkeypatch, tmp_path)
    contract["extension_manifest_fingerprint"] = "z" * 64
    with pytest.raises(ValueError):
        compiler.build_compiled_plan(
            artifact_dir=tmp_path,
            working_directory=tmp_path,
            upstream_plan={},
            upstream_receipt={},
            extension_manifest=manifest,
            command_contract=contract,
            verify_files=False,
            verify_runtime_contract=False,
        )


def test_working_directory_mismatch_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manifest, contract, _, _ = _patch(monkeypatch, tmp_path)
    contract["working_directory"] = str(tmp_path / "other")
    with pytest.raises(ValueError):
        compiler.build_compiled_plan(
            artifact_dir=tmp_path,
            working_directory=tmp_path,
            upstream_plan={},
            upstream_receipt={},
            extension_manifest=manifest,
            command_contract=contract,
            verify_files=False,
            verify_runtime_contract=False,
        )


def test_contract_that_opened_outcomes_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manifest, contract, _, _ = _patch(monkeypatch, tmp_path)
    contract["outcome_files_opened"] = True
    with pytest.raises(ValueError):
        compiler.build_compiled_plan(
            artifact_dir=tmp_path,
            working_directory=tmp_path,
            upstream_plan={},
            upstream_receipt={},
            extension_manifest=manifest,
            command_contract=contract,
            verify_files=False,
            verify_runtime_contract=False,
        )


def test_refingerprinted_receipt_tampering_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manifest, contract, plan, _ = _patch(monkeypatch, tmp_path)
    _, receipt = compiler.build_compiled_plan(
        artifact_dir=tmp_path,
        working_directory=tmp_path,
        upstream_plan={},
        upstream_receipt={},
        extension_manifest=manifest,
        command_contract=contract,
        verify_files=False,
        verify_runtime_contract=False,
    )
    receipt["all_required_cli_options_verified"] = False
    receipt.pop("fingerprint")
    receipt["fingerprint"] = compiler._fp(receipt)
    with pytest.raises(ValueError):
        compiler.validate_receipt(
            receipt,
            plan=plan,
            verify_files=False,
            verify_runtime_contract=False,
        )


def test_inputs_are_not_mutated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manifest, contract, _, _ = _patch(monkeypatch, tmp_path)
    before_manifest = copy.deepcopy(manifest)
    before_contract = copy.deepcopy(contract)
    compiler.build_compiled_plan(
        artifact_dir=tmp_path,
        working_directory=tmp_path,
        upstream_plan={},
        upstream_receipt={},
        extension_manifest=manifest,
        command_contract=contract,
        verify_files=False,
        verify_runtime_contract=False,
    )
    assert manifest == before_manifest
    assert contract == before_contract
