from __future__ import annotations

import copy
import inspect
from pathlib import Path

import pytest

import ng_historical_refinement_preflight_v32 as preflight
import ng_v38_execution_runtime_revalidation_gate as gate


def _probe_contract() -> dict:
    probes = [
        {
            "stage_key": key,
            "script_sha256": f"{index + 1:064x}",
        }
        for index, key in enumerate(gate.compiler.EXTENSION_STAGES)
    ]
    return {
        "fingerprint": "contract-fp",
        "extension_manifest_fingerprint": "manifest-fp",
        "stage_probes": probes,
    }


def _mock_validated_inputs(monkeypatch: pytest.MonkeyPatch) -> tuple[dict, dict]:
    plan = {"fingerprint": "plan-fp", "artifact_dir": "/tmp/artifacts"}
    arm_receipt = {"fingerprint": "arm-input-fp"}
    checked_arm = {
        "fingerprint": "arm-fp",
        "extension_manifest_fingerprint": "manifest-fp",
    }
    checked_compiler = {
        "fingerprint": "compiler-fp",
        "command_contract_fingerprint": "contract-fp",
        "command_lineage_fingerprint": "lineage-fp",
    }
    contract = _probe_contract()
    lineage = {"fingerprint": "lineage-fp"}

    def fake_validated_inputs(*args, **kwargs):
        return (
            copy.deepcopy(plan),
            copy.deepcopy(checked_arm),
            copy.deepcopy(checked_compiler),
            copy.deepcopy(contract),
            copy.deepcopy(lineage),
        )

    monkeypatch.setattr(gate, "_validated_inputs", fake_validated_inputs)
    return plan, arm_receipt


def test_runtime_gate_records_current_script_hashes(monkeypatch: pytest.MonkeyPatch) -> None:
    plan, arm_receipt = _mock_validated_inputs(monkeypatch)
    receipt = gate.build_gate(plan, arm_receipt)
    assert receipt["status"] == gate.READY
    assert tuple(receipt["runtime_script_sha256"]) == tuple(gate.compiler.EXTENSION_STAGES)
    assert receipt["runtime_help_probes_reexecuted"] is True
    assert receipt["runtime_script_bytes_rehashed"] is True
    assert receipt["runtime_command_lineage_reconstructed"] is True
    gate.validate_gate(
        receipt,
        plan=plan,
        arm_receipt=arm_receipt,
        verify_runtime=False,
    )


def test_runtime_gate_rejects_missing_script_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    plan, arm_receipt = _mock_validated_inputs(monkeypatch)
    original = gate._validated_inputs

    def broken(*args, **kwargs):
        values = list(original(*args, **kwargs))
        values[3]["stage_probes"][0]["script_sha256"] = None
        return tuple(values)

    monkeypatch.setattr(gate, "_validated_inputs", broken)
    with pytest.raises(gate.V38ExecutionRuntimeRevalidationError, match="script SHA-256"):
        gate.build_gate(plan, arm_receipt)


def test_runtime_gate_rejects_refingerprinted_script_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, arm_receipt = _mock_validated_inputs(monkeypatch)
    receipt = gate.build_gate(plan, arm_receipt)
    first = next(iter(receipt["runtime_script_sha256"]))
    receipt["runtime_script_sha256"][first] = "f" * 64
    receipt.pop("fingerprint")
    receipt["fingerprint"] = gate._fp(receipt)
    with pytest.raises(gate.V38ExecutionRuntimeRevalidationError, match="runtime_script_sha256"):
        gate.validate_gate(
            receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            verify_runtime=False,
        )


def test_validated_inputs_forces_fresh_file_and_help_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    manifest = {"fingerprint": "manifest-fp"}
    contract = {
        **_probe_contract(),
        "working_directory": "/tmp/work",
    }
    lineage = {
        "fingerprint": "lineage-fp",
        "extension_manifest_fingerprint": "manifest-fp",
    }
    compiler_receipt = {
        "fingerprint": "compiler-fp",
        "command_contract_fingerprint": "contract-fp",
        "command_lineage_fingerprint": "lineage-fp",
        "v30_compiler_receipt": {"command_contract": contract},
        "command_lineage": lineage,
    }
    checked_arm = {
        "fingerprint": "arm-fp",
        "compiler_receipt": compiler_receipt,
        "extension_manifest": manifest,
    }

    monkeypatch.setattr(
        gate.arm,
        "validate_arm_receipt",
        lambda receipt, armed_plan: copy.deepcopy(checked_arm),
    )

    def validate_compiler(receipt, **kwargs):
        calls["verify_files"] = kwargs["verify_files"]
        calls["verify_runtime_contract"] = kwargs["verify_runtime_contract"]
        return copy.deepcopy(compiler_receipt)

    monkeypatch.setattr(gate.compiler, "validate_receipt", validate_compiler)

    def validate_contract(receipt, **kwargs):
        calls["command_verify_runtime"] = kwargs["verify_runtime"]
        return copy.deepcopy(contract)

    monkeypatch.setattr(gate.command_gate, "validate_gate", validate_contract)
    monkeypatch.setattr(
        gate.lineage_gate,
        "validate_gate",
        lambda receipt, **kwargs: copy.deepcopy(lineage),
    )

    gate._validated_inputs(
        {"artifact_dir": "/tmp/artifacts"},
        {"fingerprint": "input-arm"},
        timeout_seconds=3.0,
        verify_runtime=True,
    )
    assert calls == {
        "verify_files": True,
        "verify_runtime_contract": True,
        "command_verify_runtime": True,
    }


def test_preflight_revalidates_before_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    plan = {"fingerprint": "plan-fp"}
    arm_receipt = {"fingerprint": "arm-fp"}
    runtime_receipt = {"fingerprint": "runtime-fp"}

    def validate_runtime(*args, **kwargs):
        order.append("runtime")
        return runtime_receipt

    def execute_prior(*args, **kwargs):
        order.append("executor")
        return {"fingerprint": "prior-fp"}

    monkeypatch.setattr(preflight, "_validated_runtime_gate", validate_runtime)
    monkeypatch.setattr(preflight.prior, "execute_preflight", execute_prior)
    monkeypatch.setattr(preflight, "_finalize", lambda *args, **kwargs: {"ok": True})

    result = preflight.execute_preflight(
        plan,
        arm_receipt,
        runtime_receipt,
        Path("ledger.json"),
        executor_runner=lambda *args, **kwargs: {},
    )
    assert result == {"ok": True}
    assert order[:2] == ["runtime", "executor"]


def test_preflight_receipt_requires_runtime_boundary_fields() -> None:
    receipt = {"schema": preflight.SCHEMA}
    receipt["fingerprint"] = preflight.prior.prior.legacy._fingerprint(receipt)
    with pytest.raises(
        preflight.HistoricalRefinementPreflightV32Error,
        match="runtime_help_probes_reexecuted",
    ):
        preflight.validate_receipt(receipt, verify_runtime=False)


def test_permanent_authority_wall_is_explicit() -> None:
    text = inspect.getsource(gate) + inspect.getsource(preflight)
    assert '"cme_event_contracts_mode": "SHADOW"' in text
    assert '"brokerage_contract": "tastytrade_not_ibkr"' in text
    assert '"options_lane_started": False' in text
    assert '"may_update_ng_brain": False' in text
    assert '"random_shuffle_used": False' in text
    assert "runtime_revalidation_immediately_before_execution" in text
