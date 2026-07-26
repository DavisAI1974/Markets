from __future__ import annotations

import copy
import hashlib
import inspect
from pathlib import Path

import pytest

import ng_historical_refinement_preflight_v34 as preflight
import ng_v38_transitive_dependency_runtime_revalidation_gate as gate


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[dict, dict, dict]:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "nested.py").write_text("FLAG = True\n", encoding="utf-8")
    (tmp_path / "helper.py").write_text(
        "import json\nfrom pkg import nested\n\ndef value():\n    return json.dumps(nested.FLAG)\n",
        encoding="utf-8",
    )
    stage = tmp_path / "stage.py"
    stage.write_text("import helper\nprint(helper.value())\n", encoding="utf-8")
    plan = {
        "fingerprint": "plan-fp",
        "working_directory": str(tmp_path),
        "stages": [
            {"key": "corpus_prefix", "argv": ["python", "stage.py"], "cwd": "."},
        ],
    }
    arm_receipt = {"fingerprint": "arm-fp"}
    all_stage_receipt = {
        "fingerprint": "all-stage-fp",
        "all_stage_script_sha256": {"corpus_prefix": _sha(stage)},
    }
    monkeypatch.setattr(gate.executor, "validate_plan", lambda value: None)
    monkeypatch.setattr(
        gate.prior,
        "validate_gate",
        lambda value, **kwargs: copy.deepcopy(dict(value)),
    )
    return plan, arm_receipt, all_stage_receipt


def test_gate_hashes_transitive_local_import_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm_receipt, all_stage_receipt = _fixture(tmp_path, monkeypatch)
    receipt = gate.build_gate(plan, arm_receipt, all_stage_receipt, tmp_path)
    assert receipt["status"] == gate.READY
    assert receipt["stage_local_python_dependency_paths"]["corpus_prefix"] == [
        "helper.py",
        "pkg/__init__.py",
        "pkg/nested.py",
        "stage.py",
    ]
    assert set(receipt["local_python_dependency_sha256"]) == {
        "helper.py",
        "pkg/__init__.py",
        "pkg/nested.py",
        "stage.py",
    }
    assert "json" in receipt["external_imports_ignored"]
    assert receipt["all_entrypoints_in_dependency_closure"] is True
    assert receipt["transitive_local_python_dependencies_rehashed"] is True
    gate.validate_gate(
        receipt,
        plan=plan,
        arm_receipt=arm_receipt,
        repository_root=tmp_path,
        verify_runtime=False,
    )


def test_gate_detects_imported_dependency_change_after_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm_receipt, all_stage_receipt = _fixture(tmp_path, monkeypatch)
    receipt = gate.build_gate(plan, arm_receipt, all_stage_receipt, tmp_path)
    (tmp_path / "helper.py").write_text("VALUE = 'changed'\n", encoding="utf-8")
    with pytest.raises(
        gate.V38TransitiveDependencyRuntimeRevalidationError,
        match="deterministic reconstruction",
    ):
        gate.validate_gate(
            receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            repository_root=tmp_path,
            verify_runtime=True,
        )


def test_gate_fails_closed_on_nonliteral_dynamic_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm_receipt, all_stage_receipt = _fixture(tmp_path, monkeypatch)
    stage = tmp_path / "stage.py"
    stage.write_text(
        "import importlib\nname = 'helper'\nimportlib.import_module(name)\n",
        encoding="utf-8",
    )
    all_stage_receipt["all_stage_script_sha256"]["corpus_prefix"] = _sha(stage)
    with pytest.raises(
        gate.V38TransitiveDependencyRuntimeRevalidationError,
        match="non-literal dynamic import",
    ):
        gate.build_gate(plan, arm_receipt, all_stage_receipt, tmp_path)


def test_gate_fails_closed_on_unresolved_relative_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm_receipt, all_stage_receipt = _fixture(tmp_path, monkeypatch)
    stage = tmp_path / "stage.py"
    stage.write_text("from .missing import value\n", encoding="utf-8")
    all_stage_receipt["all_stage_script_sha256"]["corpus_prefix"] = _sha(stage)
    with pytest.raises(
        gate.V38TransitiveDependencyRuntimeRevalidationError,
        match="unresolved relative import",
    ):
        gate.build_gate(plan, arm_receipt, all_stage_receipt, tmp_path)


def test_gate_rejects_entrypoint_hash_disagreement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm_receipt, all_stage_receipt = _fixture(tmp_path, monkeypatch)
    all_stage_receipt["all_stage_script_sha256"]["corpus_prefix"] = "f" * 64
    with pytest.raises(
        gate.V38TransitiveDependencyRuntimeRevalidationError,
        match="validated entrypoint hash",
    ):
        gate.build_gate(plan, arm_receipt, all_stage_receipt, tmp_path)


def test_preflight_revalidates_dependencies_at_executor_delegation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    order: list[str] = []
    plan = {"fingerprint": "plan-fp"}
    arm_receipt = {"fingerprint": "arm-fp"}
    dependency_receipt = {
        "fingerprint": "dependency-fp",
        "repository_root": str(tmp_path),
        "all_stage_runtime_revalidation_receipt": {"fingerprint": "all-stage-fp"},
    }

    def validate_dependency(*args, **kwargs):
        order.append("dependency")
        return copy.deepcopy(dependency_receipt)

    def fake_prior(*args, **kwargs):
        order.append("prior-preflight")
        kwargs["executor_runner"](plan, Path("ledger.json"))
        return {"fingerprint": "prior-preflight-fp"}

    def fake_executor(*args, **kwargs):
        order.append("executor")
        return {"status": "DRY_RUN"}

    monkeypatch.setattr(preflight, "_validated_dependency_gate", validate_dependency)
    monkeypatch.setattr(preflight.prior, "execute_preflight", fake_prior)
    monkeypatch.setattr(preflight, "_finalize", lambda *args, **kwargs: {"ok": True})

    result = preflight.execute_preflight(
        plan,
        arm_receipt,
        dependency_receipt,
        tmp_path,
        Path("ledger.json"),
        executor_runner=fake_executor,
    )
    assert result == {"ok": True}
    assert order == ["dependency", "prior-preflight", "dependency", "executor"]


def test_preflight_receipt_requires_dependency_boundary_fields() -> None:
    receipt = {"schema": preflight.SCHEMA}
    receipt["fingerprint"] = preflight.legacy_readiness._fingerprint(receipt)
    with pytest.raises(
        preflight.HistoricalRefinementPreflightV34Error,
        match="transitive_local_python_dependencies_rehashed",
    ):
        preflight.validate_receipt(receipt, verify_runtime=False)


def test_permanent_authority_wall_is_explicit() -> None:
    text = inspect.getsource(gate) + inspect.getsource(preflight)
    assert '"cme_event_contracts_mode": "SHADOW"' in text
    assert '"brokerage_contract": "tastytrade_not_ibkr"' in text
    assert '"options_lane_started": False' in text
    assert '"may_update_ng_brain": False' in text
    assert '"random_shuffle_used": False' in text
    assert "transitive_local_python_dependencies_rehashed" in text
    assert "runtime_dependency_revalidation_at_executor_delegation" in text
