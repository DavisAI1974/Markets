from __future__ import annotations

import copy
import inspect
from pathlib import Path

import pytest

import ng_historical_refinement_preflight_v35 as preflight
import ng_v38_external_runtime_dependency_revalidation_gate as gate


class FakeDistribution:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.metadata = {"Name": "Vendor-Dist"}
        self.version = "1.2.3"
        self.files = [
            "vendor_pkg/__init__.py",
            "Vendor_Dist-1.2.3.dist-info/METADATA",
        ]

    def locate_file(self, value: str) -> Path:
        return self.root / value


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    package = tmp_path / "vendor_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    metadata_dir = tmp_path / "Vendor_Dist-1.2.3.dist-info"
    metadata_dir.mkdir()
    (metadata_dir / "METADATA").write_text(
        "Name: Vendor-Dist\nVersion: 1.2.3\n", encoding="utf-8"
    )
    python_executable = tmp_path / "python"
    python_executable.write_bytes(b"python-runtime")
    aws_executable = tmp_path / "aws"
    aws_executable.write_bytes(b"aws-runtime")
    plan = {"fingerprint": "plan-fp"}
    arm_receipt = {"fingerprint": "arm-fp"}
    dependency_receipt = {
        "fingerprint": "dependency-fp",
        "repository_root": str(tmp_path),
        "external_imports_ignored": ["json", "vendor_pkg.api"],
    }
    monkeypatch.setattr(
        gate.dependency_gate,
        "validate_gate",
        lambda value, **kwargs: copy.deepcopy(dict(value)),
    )
    hooks = {
        "python_executable": python_executable,
        "packages_distributions": lambda: {"vendor_pkg": ["Vendor-Dist"]},
        "distribution_loader": lambda name: FakeDistribution(tmp_path),
        "which": lambda name: str(aws_executable) if name == "aws" else None,
        "version_runner": lambda argv, timeout: {
            "returncode": 0,
            "stdout": "aws-cli/2.17.0 Python/3.11",
            "stderr": "",
        },
    }
    return plan, arm_receipt, dependency_receipt, hooks


def test_gate_hashes_python_distribution_files_and_aws(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm_receipt, dependency_receipt, hooks = _fixture(tmp_path, monkeypatch)
    receipt = gate.build_gate(
        plan,
        arm_receipt,
        dependency_receipt,
        tmp_path,
        **hooks,
    )
    assert receipt["status"] == gate.READY
    assert receipt["third_party_imports"] == ["vendor_pkg"]
    assert receipt["import_to_distributions"] == {"vendor_pkg": ["Vendor-Dist"]}
    assert receipt["installed_distributions"]["Vendor-Dist"]["file_count"] == 2
    assert receipt["python_runtime"]["executable"].endswith("/python")
    assert receipt["runtime_executables"]["aws"]["version_text"].startswith("aws-cli/")
    assert receipt["all_distribution_files_rehashed"] is True
    assert receipt["aws_cli_rehashed_and_version_probed"] is True
    gate.validate_gate(
        receipt,
        plan=plan,
        arm_receipt=arm_receipt,
        repository_root=tmp_path,
        verify_runtime=False,
        **hooks,
    )


def test_gate_detects_installed_distribution_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm_receipt, dependency_receipt, hooks = _fixture(tmp_path, monkeypatch)
    receipt = gate.build_gate(plan, arm_receipt, dependency_receipt, tmp_path, **hooks)
    (tmp_path / "vendor_pkg" / "__init__.py").write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(
        gate.V38ExternalRuntimeDependencyRevalidationError,
        match="deterministic reconstruction",
    ):
        gate.validate_gate(
            receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            repository_root=tmp_path,
            verify_runtime=True,
            **hooks,
        )


def test_gate_rejects_unmapped_external_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm_receipt, dependency_receipt, hooks = _fixture(tmp_path, monkeypatch)
    dependency_receipt["external_imports_ignored"].append("missing_vendor")
    hooks["packages_distributions"] = lambda: {"vendor_pkg": ["Vendor-Dist"]}
    with pytest.raises(
        gate.V38ExternalRuntimeDependencyRevalidationError,
        match="no installed distribution provenance: missing_vendor",
    ):
        gate.build_gate(plan, arm_receipt, dependency_receipt, tmp_path, **hooks)


def test_gate_rejects_missing_aws_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm_receipt, dependency_receipt, hooks = _fixture(tmp_path, monkeypatch)
    hooks["which"] = lambda name: None
    with pytest.raises(
        gate.V38ExternalRuntimeDependencyRevalidationError,
        match="required runtime executable is missing: aws",
    ):
        gate.build_gate(plan, arm_receipt, dependency_receipt, tmp_path, **hooks)


def test_preflight_revalidates_external_runtime_at_executor_delegation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    order: list[str] = []
    plan = {"fingerprint": "plan-fp"}
    arm_receipt = {"fingerprint": "arm-fp"}
    external_receipt = {
        "fingerprint": "external-fp",
        "repository_root": str(tmp_path),
        "dependency_runtime_revalidation_receipt": {"fingerprint": "dependency-fp"},
    }

    def validate_external(*args, **kwargs):
        order.append("external")
        return copy.deepcopy(external_receipt)

    def fake_prior(*args, **kwargs):
        order.append("prior-preflight")
        kwargs["executor_runner"](plan, Path("ledger.json"))
        return {"fingerprint": "prior-preflight-fp"}

    def fake_executor(*args, **kwargs):
        order.append("executor")
        return {"status": "DRY_RUN"}

    monkeypatch.setattr(preflight, "_validated_external_gate", validate_external)
    monkeypatch.setattr(preflight.prior, "execute_preflight", fake_prior)
    monkeypatch.setattr(preflight, "_finalize", lambda *args, **kwargs: {"ok": True})

    result = preflight.execute_preflight(
        plan,
        arm_receipt,
        external_receipt,
        tmp_path,
        Path("ledger.json"),
        executor_runner=fake_executor,
    )
    assert result == {"ok": True}
    assert order == ["external", "prior-preflight", "external", "executor"]


def test_preflight_receipt_requires_external_runtime_boundary_fields() -> None:
    receipt = {"schema": preflight.SCHEMA}
    receipt["fingerprint"] = preflight.legacy_readiness._fingerprint(receipt)
    with pytest.raises(
        preflight.HistoricalRefinementPreflightV35Error,
        match="python_runtime_rehashed",
    ):
        preflight.validate_receipt(receipt, verify_runtime=False)


def test_permanent_authority_wall_is_explicit() -> None:
    text = inspect.getsource(gate) + inspect.getsource(preflight)
    assert '"cme_event_contracts_mode": "SHADOW"' in text
    assert '"brokerage_contract": "tastytrade_not_ibkr"' in text
    assert '"options_lane_started": False' in text
    assert '"may_update_ng_brain": False' in text
    assert '"random_shuffle_used": False' in text
    assert "all_distribution_files_rehashed" in text
    assert "runtime_external_revalidation_at_executor_delegation" in text
