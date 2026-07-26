from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_v38_execution_command_contract_gate as gate


def _script(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def _manifest(commands):
    return {"fingerprint": "m" * 64, "commands": commands}


def _patch_manifest(monkeypatch: pytest.MonkeyPatch, stages):
    monkeypatch.setattr(gate, "EXTENSION_STAGES", tuple(stages))
    monkeypatch.setattr(
        gate.compiler,
        "validate_extension_manifest",
        lambda value, require_ready=True: copy.deepcopy(dict(value)),
    )


def test_required_option_contract_ignores_optional_and_supports_any_of():
    required, groups = gate.required_option_contract(
        "usage: stage [-h] --input INPUT [--quiet] (--left LEFT | --right RIGHT) --out OUT"
    )
    assert required == ["--input", "--out"]
    assert groups == [["--left", "--right"]]


def test_probe_blocks_missing_required_option(tmp_path: Path):
    _script(
        tmp_path / "stage.py",
        "import argparse\np=argparse.ArgumentParser()\np.add_argument('--input', required=True)\np.add_argument('--out', required=True)\np.parse_args()\n",
    )
    result = gate.probe_command(
        "stage", ["python", "stage.py", "--out", "x.json"], working_directory=tmp_path
    )
    assert result["ready"] is False
    assert "MISSING_REQUIRED_OPTION:--input" in result["blockers"]
    assert result["script_sha256"]


def test_probe_accepts_complete_subcommand_contract(tmp_path: Path):
    _script(
        tmp_path / "stage.py",
        "import argparse\np=argparse.ArgumentParser()\ns=p.add_subparsers(dest='cmd', required=True)\nb=s.add_parser('build')\nb.add_argument('--input', required=True)\nb.add_argument('--out', required=True)\np.parse_args()\n",
    )
    result = gate.probe_command(
        "stage",
        ["python", "stage.py", "build", "--input", "i.json", "--out", "o.json"],
        working_directory=tmp_path,
    )
    assert result["ready"] is True
    assert result["required_options"] == ["--input", "--out"]
    assert result["help_command"][-2:] == ["build", "--help"]


def test_probe_rejects_placeholder_and_path_escape(tmp_path: Path):
    outside = tmp_path.parent / "outside_stage.py"
    _script(outside, "import argparse\nargparse.ArgumentParser().parse_args()\n")
    result = gate.probe_command(
        "stage",
        ["python", str(outside), "--out", "<replace-me>"],
        working_directory=tmp_path,
    )
    assert "SCRIPT_PATH_ESCAPES_WORKING_DIRECTORY" in result["blockers"]
    assert "PLACEHOLDER_ARGUMENTS_FORBIDDEN" in result["blockers"]


def test_gate_exposes_stage_specific_stand_downs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _patch_manifest(monkeypatch, ("alpha", "beta"))
    for name in ("alpha.py", "beta.py"):
        _script(
            tmp_path / name,
            "import argparse\np=argparse.ArgumentParser()\np.add_argument('--input', required=True)\np.add_argument('--out', required=True)\np.parse_args()\n",
        )
    manifest = _manifest(
        {
            "alpha": ["python", "alpha.py", "--out", "alpha.json"],
            "beta": ["python", "beta.py", "--input", "i", "--out", "beta.json"],
        }
    )
    result = gate.build_gate(manifest, working_directory=tmp_path)
    assert result["status"] == gate.BLOCKED
    assert result["blockers"] == ["alpha:MISSING_REQUIRED_OPTION:--input"]
    assert result["stand_downs"][0]["action"] == "REPAIR_COMMAND_ARGUMENT_CONTRACT_AND_STAND_DOWN"


def test_ready_gate_validates_without_opening_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _patch_manifest(monkeypatch, ("alpha",))
    _script(
        tmp_path / "alpha.py",
        "import argparse\np=argparse.ArgumentParser()\np.add_argument('--input', required=True)\np.add_argument('--out', required=True)\np.parse_args()\n",
    )
    manifest = _manifest(
        {"alpha": ["python", "alpha.py", "--input", "i", "--out", "alpha.json"]}
    )
    result = gate.build_gate(manifest, working_directory=tmp_path)
    checked = gate.validate_gate(result, verify_runtime=True)
    assert checked["status"] == gate.READY
    assert checked["help_only_probe"] is True
    assert checked["corpus_files_opened"] is False
    assert checked["outcome_files_opened"] is False
    assert checked["options_lane_started"] is False


def test_refingerprinted_probe_tampering_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _patch_manifest(monkeypatch, ("alpha",))
    _script(tmp_path / "alpha.py", "import argparse\nargparse.ArgumentParser().parse_args()\n")
    result = gate.build_gate(
        _manifest({"alpha": ["python", "alpha.py"]}), working_directory=tmp_path
    )
    result["stage_probes"][0]["script_sha256"] = "0" * 64
    result.pop("fingerprint")
    result["fingerprint"] = gate._fp(result)
    with pytest.raises(gate.V38ExecutionCommandContractError):
        gate.validate_gate(result, verify_runtime=False)


def test_gate_does_not_mutate_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _patch_manifest(monkeypatch, ("alpha",))
    _script(tmp_path / "alpha.py", "import argparse\nargparse.ArgumentParser().parse_args()\n")
    manifest = _manifest({"alpha": ["python", "alpha.py"]})
    original = copy.deepcopy(manifest)
    gate.build_gate(manifest, working_directory=tmp_path)
    assert manifest == original
