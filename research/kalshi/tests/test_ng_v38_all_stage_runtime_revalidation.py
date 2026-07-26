from __future__ import annotations

import copy
import hashlib
import inspect
from pathlib import Path

import pytest

import ng_historical_refinement_preflight_v33 as preflight
import ng_v38_all_stage_runtime_revalidation_gate as gate


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[dict, dict, dict]:
    prefix = tmp_path / "prefix.py"
    extension = tmp_path / "extension.py"
    prefix.write_text("print('prefix')\n", encoding="utf-8")
    extension.write_text("print('extension')\n", encoding="utf-8")
    plan = {
        "fingerprint": "plan-fp",
        "working_directory": str(tmp_path),
        "stages": [
            {"key": "corpus_prefix", "argv": ["python", "prefix.py"], "cwd": "."},
            {"key": "g16_extension", "argv": ["python", "extension.py"], "cwd": "."},
        ],
    }
    arm_receipt = {"fingerprint": "arm-fp"}
    prior_receipt = {
        "fingerprint": "prior-fp",
        "runtime_script_sha256": {"g16_extension": _sha(extension)},
    }
    monkeypatch.setattr(gate.executor, "validate_plan", lambda value: None)
    monkeypatch.setattr(gate.compiler, "EXTENSION_STAGES", ("g16_extension",))
    monkeypatch.setattr(
        gate.prior,
        "validate_gate",
        lambda value, **kwargs: copy.deepcopy(dict(value)),
    )
    return plan, arm_receipt, prior_receipt


def test_gate_hashes_historical_prefix_and_g16_extension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm_receipt, prior_receipt = _fixture(tmp_path, monkeypatch)
    receipt = gate.build_gate(plan, arm_receipt, prior_receipt)
    assert receipt["status"] == gate.READY
    assert list(receipt["all_stage_script_sha256"]) == [
        "corpus_prefix",
        "g16_extension",
    ]
    assert receipt["configured_stage_count"] == 2
    assert receipt["historical_and_g15_prefix_scripts_rehashed"] is True
    assert receipt["all_configured_stage_scripts_rehashed"] is True
    gate.validate_gate(
        receipt,
        plan=plan,
        arm_receipt=arm_receipt,
        verify_runtime=False,
    )


def test_gate_detects_prefix_script_change_after_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm_receipt, prior_receipt = _fixture(tmp_path, monkeypatch)
    receipt = gate.build_gate(plan, arm_receipt, prior_receipt)
    (tmp_path / "prefix.py").write_text("print('changed')\n", encoding="utf-8")
    with pytest.raises(
        gate.V38AllStageRuntimeRevalidationError,
        match="deterministic reconstruction",
    ):
        gate.validate_gate(
            receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            verify_runtime=True,
        )


def test_gate_stands_down_when_prefix_script_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm_receipt, prior_receipt = _fixture(tmp_path, monkeypatch)
    (tmp_path / "prefix.py").unlink()
    with pytest.raises(
        gate.V38AllStageRuntimeRevalidationError,
        match="configured stage script is missing",
    ):
        gate.build_gate(plan, arm_receipt, prior_receipt)


def test_gate_rejects_extension_hash_disagreement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm_receipt, prior_receipt = _fixture(tmp_path, monkeypatch)
    prior_receipt["runtime_script_sha256"]["g16_extension"] = "f" * 64
    with pytest.raises(
        gate.V38AllStageRuntimeRevalidationError,
        match="extension hashes",
    ):
        gate.build_gate(plan, arm_receipt, prior_receipt)


def test_preflight_revalidates_again_at_executor_delegation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []
    plan = {"fingerprint": "plan-fp"}
    arm_receipt = {"fingerprint": "arm-fp"}
    all_stage_receipt = {
        "fingerprint": "all-fp",
        "prior_runtime_revalidation_receipt": {"fingerprint": "prior-fp"},
    }

    def validate_all(*args, **kwargs):
        order.append("all-stage")
        return copy.deepcopy(all_stage_receipt)

    def fake_prior(*args, **kwargs):
        order.append("prior-preflight")
        kwargs["executor_runner"](plan, Path("ledger.json"))
        return {"fingerprint": "prior-preflight-fp"}

    def fake_executor(*args, **kwargs):
        order.append("executor")
        return {"status": "DRY_RUN"}

    monkeypatch.setattr(preflight, "_validated_all_stage_gate", validate_all)
    monkeypatch.setattr(preflight.prior, "execute_preflight", fake_prior)
    monkeypatch.setattr(preflight, "_finalize", lambda *args, **kwargs: {"ok": True})

    result = preflight.execute_preflight(
        plan,
        arm_receipt,
        all_stage_receipt,
        Path("ledger.json"),
        executor_runner=fake_executor,
    )
    assert result == {"ok": True}
    assert order == ["all-stage", "prior-preflight", "all-stage", "executor"]


def test_preflight_receipt_requires_all_stage_boundary_fields() -> None:
    receipt = {"schema": preflight.SCHEMA}
    receipt["fingerprint"] = preflight.legacy_readiness._fingerprint(receipt)
    with pytest.raises(
        preflight.HistoricalRefinementPreflightV33Error,
        match="all_configured_stage_scripts_rehashed",
    ):
        preflight.validate_receipt(receipt, verify_runtime=False)


def test_permanent_authority_wall_is_explicit() -> None:
    text = inspect.getsource(gate) + inspect.getsource(preflight)
    assert '"cme_event_contracts_mode": "SHADOW"' in text
    assert '"brokerage_contract": "tastytrade_not_ibkr"' in text
    assert '"options_lane_started": False' in text
    assert '"may_update_ng_brain": False' in text
    assert '"random_shuffle_used": False' in text
    assert "historical_and_g15_prefix_scripts_rehashed" in text
    assert "runtime_revalidation_at_executor_delegation" in text
