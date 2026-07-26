from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path

import pytest

import ng_historical_refinement_preflight_v36 as preflight
import ng_v38_aws_execution_context_revalidation_gate as gate


ACCOUNT = "123456789012"
REGION = "us-east-1"
ARN = f"arn:aws:sts::{ACCOUNT}:assumed-role/MarketsCorpus/session"


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    aws_path = tmp_path / "aws"
    aws_path.write_bytes(b"aws-cli")
    plan = {"fingerprint": "plan-fp"}
    arm = {"fingerprint": "arm-fp"}
    external = {
        "fingerprint": "external-fp",
        "repository_root": str(tmp_path),
        "runtime_executables": {
            "aws": {
                "path": str(aws_path),
                "sha256": "aws-sha",
                "version_text": "aws-cli/2.17.0",
            }
        },
    }
    monkeypatch.setattr(
        gate.external_gate,
        "validate_gate",
        lambda value, **kwargs: copy.deepcopy(dict(value)),
    )
    environment = {
        "AWS_PROFILE": "markets-corpus",
        "AWS_REGION": REGION,
        "AWS_EC2_METADATA_DISABLED": "true",
    }
    state = {"account": ACCOUNT, "arn": ARN, "region": REGION}

    def runner(argv, timeout):
        parts = list(argv)
        if "configure" in parts:
            return {"returncode": 0, "stdout": state["region"] + "\n", "stderr": ""}
        if "get-caller-identity" in parts:
            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "Account": state["account"],
                        "Arn": state["arn"],
                        "UserId": "AROATEST:session",
                    }
                ),
                "stderr": "",
            }
        raise AssertionError(parts)

    return plan, arm, external, environment, runner, state


def test_gate_binds_sts_account_region_profile_and_no_custom_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm, external, environment, runner, _ = _fixture(tmp_path, monkeypatch)
    receipt = gate.build_gate(
        plan,
        arm,
        external,
        tmp_path,
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        environment=environment,
        command_runner=runner,
    )
    assert receipt["status"] == gate.READY
    assert receipt["caller_identity"]["account_id"] == ACCOUNT
    assert receipt["caller_identity"]["arn"] == ARN
    assert receipt["selected_profile"] == "markets-corpus"
    assert receipt["effective_region"] == REGION
    assert receipt["aws_environment"]["custom_endpoint_urls_present"] is False
    assert receipt["aws_environment"]["credential_values_recorded"] is False
    gate.validate_gate(
        receipt,
        plan=plan,
        arm_receipt=arm,
        repository_root=tmp_path,
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        environment=environment,
        command_runner=runner,
        verify_runtime=False,
    )


def test_gate_rejects_wrong_aws_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm, external, environment, runner, state = _fixture(tmp_path, monkeypatch)
    state["account"] = "999999999999"
    state["arn"] = "arn:aws:sts::999999999999:assumed-role/Other/session"
    with pytest.raises(
        gate.V38AwsExecutionContextRevalidationError,
        match="AWS account mismatch",
    ):
        gate.build_gate(
            plan,
            arm,
            external,
            tmp_path,
            expected_account_id=ACCOUNT,
            expected_region=REGION,
            environment=environment,
            command_runner=runner,
        )


def test_gate_rejects_custom_s3_endpoint_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm, external, environment, runner, _ = _fixture(tmp_path, monkeypatch)
    environment["AWS_ENDPOINT_URL_S3"] = "https://example.invalid"
    with pytest.raises(
        gate.V38AwsExecutionContextRevalidationError,
        match="custom AWS endpoint configuration is forbidden",
    ):
        gate.build_gate(
            plan,
            arm,
            external,
            tmp_path,
            expected_account_id=ACCOUNT,
            expected_region=REGION,
            environment=environment,
            command_runner=runner,
        )


@pytest.mark.parametrize(
    ("left", "right", "message"),
    [
        (("AWS_PROFILE", "one"), ("AWS_DEFAULT_PROFILE", "two"), "PROFILE"),
        (("AWS_REGION", "us-east-1"), ("AWS_DEFAULT_REGION", "us-west-2"), "REGION"),
    ],
)
def test_gate_rejects_conflicting_profile_or_region_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    left,
    right,
    message: str,
) -> None:
    plan, arm, external, environment, runner, _ = _fixture(tmp_path, monkeypatch)
    environment[left[0]] = left[1]
    environment[right[0]] = right[1]
    with pytest.raises(
        gate.V38AwsExecutionContextRevalidationError,
        match=message,
    ):
        gate.build_gate(
            plan,
            arm,
            external,
            tmp_path,
            expected_account_id=ACCOUNT,
            expected_region=REGION,
            environment=environment,
            command_runner=runner,
        )


def test_gate_detects_principal_change_after_receipt_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm, external, environment, runner, state = _fixture(tmp_path, monkeypatch)
    receipt = gate.build_gate(
        plan,
        arm,
        external,
        tmp_path,
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        environment=environment,
        command_runner=runner,
    )
    state["arn"] = f"arn:aws:sts::{ACCOUNT}:assumed-role/Changed/session"
    with pytest.raises(
        gate.V38AwsExecutionContextRevalidationError,
        match="deterministic reconstruction",
    ):
        gate.validate_gate(
            receipt,
            plan=plan,
            arm_receipt=arm,
            repository_root=tmp_path,
            expected_account_id=ACCOUNT,
            expected_region=REGION,
            environment=environment,
            command_runner=runner,
            verify_runtime=True,
        )


def test_preflight_revalidates_aws_context_at_executor_delegation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    order: list[str] = []
    plan = {"fingerprint": "plan-fp"}
    arm = {"fingerprint": "arm-fp"}
    aws_receipt = {
        "fingerprint": "aws-fp",
        "external_runtime_revalidation_receipt": {"fingerprint": "external-fp"},
        "caller_identity": {"account_id": ACCOUNT, "arn": ARN},
    }

    def validate_aws(*args, **kwargs):
        order.append("aws")
        return copy.deepcopy(aws_receipt)

    def fake_prior(*args, **kwargs):
        order.append("prior-preflight")
        kwargs["executor_runner"](plan, Path("ledger.json"))
        return {"fingerprint": "prior-preflight-fp"}

    def fake_executor(*args, **kwargs):
        order.append("executor")
        return {"status": "DRY_RUN"}

    monkeypatch.setattr(preflight, "_validated_aws_gate", validate_aws)
    monkeypatch.setattr(preflight.prior, "execute_preflight", fake_prior)
    monkeypatch.setattr(preflight, "_finalize", lambda *args, **kwargs: {"ok": True})

    result = preflight.execute_preflight(
        plan,
        arm,
        aws_receipt,
        tmp_path,
        Path("ledger.json"),
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        executor_runner=fake_executor,
    )
    assert result == {"ok": True}
    assert order == ["aws", "prior-preflight", "aws", "executor"]


def test_preflight_receipt_requires_aws_context_boundary_fields() -> None:
    receipt = {"schema": preflight.SCHEMA}
    receipt["fingerprint"] = preflight.legacy_readiness._fingerprint(receipt)
    with pytest.raises(
        preflight.HistoricalRefinementPreflightV36Error,
        match="sts_caller_identity_revalidated",
    ):
        preflight.validate_receipt(receipt, verify_runtime=False)


def test_permanent_authority_wall_is_explicit() -> None:
    text = inspect.getsource(gate) + inspect.getsource(preflight)
    assert '"cme_event_contracts_mode": "SHADOW"' in text
    assert '"brokerage_contract": "tastytrade_not_ibkr"' in text
    assert '"options_lane_started": False' in text
    assert '"may_update_ng_brain": False' in text
    assert '"random_shuffle_used": False' in text
    assert "sts_caller_identity_revalidated" in text
    assert "runtime_aws_context_revalidation_at_executor_delegation" in text
