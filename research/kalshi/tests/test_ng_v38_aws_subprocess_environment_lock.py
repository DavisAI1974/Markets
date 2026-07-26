from __future__ import annotations

import copy
from pathlib import Path

import pytest

import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v35 as executor
import ng_historical_refinement_preflight_v38 as preflight
import ng_v38_aws_subprocess_environment_lock as lock


def _inputs(tmp_path: Path):
    plan = {"fingerprint": "plan-fp"}
    arm = {"fingerprint": "arm-fp"}
    aws = {
        "fingerprint": "aws-fp",
        "expected_account_id": "123456789012",
        "selected_profile": "markets-prod",
        "expected_region": "us-east-1",
        "effective_region": "us-east-1",
    }
    s3 = {
        "fingerprint": "s3-fp",
        "aws_execution_context_revalidation_receipt": copy.deepcopy(aws),
    }
    source_spec = {"schema": "test-source-spec"}
    environment = {
        "PATH": "/usr/bin",
        "HOME": str(tmp_path),
        "AWS_PROFILE": "markets-prod",
        "AWS_DEFAULT_PROFILE": "markets-prod",
        "AWS_REGION": "us-east-1",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "not-recorded-access-key",
        "AWS_SECRET_ACCESS_KEY": "not-recorded-secret",
        "AWS_SESSION_TOKEN": "not-recorded-token",
        "AWS_SHARED_CREDENTIALS_FILE": str(tmp_path / "credentials"),
    }
    return plan, arm, aws, s3, source_spec, environment


def _stub_validated_inputs(
    plan,
    arm_receipt,
    aws_receipt,
    s3_receipt,
    source_spec,
    repository_root,
    *,
    environment,
):
    return copy.deepcopy(dict(aws_receipt)), copy.deepcopy(dict(s3_receipt))


def test_locked_environment_preserves_credentials_without_recording_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm, aws, s3, source_spec, environment = _inputs(tmp_path)
    monkeypatch.setattr(lock, "_validated_inputs", _stub_validated_inputs)
    receipt, launch = lock.build_locked_environment(
        plan,
        arm,
        aws,
        s3,
        source_spec,
        tmp_path,
        environment=environment,
    )
    assert receipt["status"] == lock.READY
    assert launch["AWS_ACCESS_KEY_ID"] == environment["AWS_ACCESS_KEY_ID"]
    assert launch["AWS_SECRET_ACCESS_KEY"] == environment["AWS_SECRET_ACCESS_KEY"]
    assert launch["AWS_SESSION_TOKEN"] == environment["AWS_SESSION_TOKEN"]
    assert launch["AWS_PROFILE"] == launch["AWS_DEFAULT_PROFILE"] == "markets-prod"
    assert launch["AWS_REGION"] == launch["AWS_DEFAULT_REGION"] == "us-east-1"
    assert launch["PYTHONHASHSEED"] == "0"
    assert launch["TZ"] == "UTC"
    rendered = repr(receipt)
    assert environment["AWS_ACCESS_KEY_ID"] not in rendered
    assert environment["AWS_SECRET_ACCESS_KEY"] not in rendered
    assert environment["AWS_SESSION_TOKEN"] not in rendered
    assert receipt["secret_values_recorded"] is False


@pytest.mark.parametrize(
    "key",
    ["AWS_ENDPOINT_URL", "AWS_ENDPOINT_URL_S3", "S3_ENDPOINT_URL"],
)
def test_custom_endpoint_overrides_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    plan, arm, aws, s3, source_spec, environment = _inputs(tmp_path)
    environment[key] = "http://127.0.0.1:9000"
    monkeypatch.setattr(lock, "_validated_inputs", _stub_validated_inputs)
    with pytest.raises(
        lock.V38AwsSubprocessEnvironmentLockError,
        match="endpoint overrides are forbidden",
    ):
        lock.build_locked_environment(
            plan,
            arm,
            aws,
            s3,
            source_spec,
            tmp_path,
            environment=environment,
        )


def test_ambient_profile_substitution_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm, aws, s3, source_spec, environment = _inputs(tmp_path)
    environment["AWS_PROFILE"] = "different-profile"
    environment["AWS_DEFAULT_PROFILE"] = "different-profile"
    monkeypatch.setattr(lock, "_validated_inputs", _stub_validated_inputs)
    with pytest.raises(
        lock.V38AwsSubprocessEnvironmentLockError,
        match="profile differs",
    ):
        lock.build_locked_environment(
            plan,
            arm,
            aws,
            s3,
            source_spec,
            tmp_path,
            environment=environment,
        )


def test_executor_uses_locked_environment_for_the_actual_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm, aws, s3, source_spec, environment = _inputs(tmp_path)
    receipt = {
        "fingerprint": "environment-lock-fp",
        "selected_profile": "markets-prod",
        "expected_region": "us-east-1",
    }
    launch = {
        "PATH": "/usr/bin",
        "AWS_PROFILE": "markets-prod",
        "AWS_DEFAULT_PROFILE": "markets-prod",
        "AWS_REGION": "us-east-1",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "launch-access-key",
    }
    monkeypatch.setattr(
        executor.environment_lock,
        "build_locked_environment",
        lambda *args, **kwargs: (copy.deepcopy(receipt), copy.deepcopy(launch)),
    )
    observed = {}
    original_environment_builder = legacy_executor._command_environment

    def fake_execute_next(*args, **kwargs):
        observed["environment"] = legacy_executor._command_environment()
        return {"status": "DRY_RUN", "stage": "corpus_expected_day_contract"}

    monkeypatch.setattr(executor.prior, "execute_next", fake_execute_next)
    result = executor.execute_next(
        plan,
        tmp_path / "ledger.json",
        arm_receipt=arm,
        aws_execution_context_revalidation=aws,
        s3_source_capability_revalidation=s3,
        source_spec=source_spec,
        repository_root=tmp_path,
        environment=environment,
        dry_run=True,
    )
    assert observed["environment"] == launch
    assert result["aws_subprocess_environment_locked"] is True
    assert result["aws_subprocess_environment_lock_fingerprint"] == "environment-lock-fp"
    assert legacy_executor._command_environment is original_environment_builder


def test_preflight_rebuilds_lock_at_executor_delegation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, arm, aws, s3, source_spec, environment = _inputs(tmp_path)
    environment_receipt = {
        "fingerprint": "environment-lock-fp",
        "selected_profile": "markets-prod",
        "expected_region": "us-east-1",
    }
    monkeypatch.setattr(
        preflight,
        "_validated_environment_lock",
        lambda *args, **kwargs: copy.deepcopy(environment_receipt),
    )
    rebuilds = []

    def fake_build(*args, **kwargs):
        rebuilds.append(True)
        return copy.deepcopy(environment_receipt), {"AWS_REGION": "us-east-1"}

    monkeypatch.setattr(
        preflight.environment_lock,
        "build_locked_environment",
        fake_build,
    )
    delegated = {}

    def fake_executor(*args, **kwargs):
        delegated.update(kwargs)
        return {"status": "DRY_RUN", "stage": "corpus_expected_day_contract"}

    def fake_prior_execute(
        plan_value,
        arm_value,
        aws_value,
        s3_value,
        spec_value,
        root_value,
        ledger_value,
        *,
        executor_runner,
        **kwargs,
    ):
        executor_runner(plan_value, ledger_value, dry_run=True)
        return {
            "schema": preflight.prior.SCHEMA,
            "status": "PREFLIGHT_EXECUTED",
            "fingerprint": "prior-preflight-fp",
            "executor_called": True,
        }

    monkeypatch.setattr(preflight.prior, "execute_preflight", fake_prior_execute)
    monkeypatch.setattr(preflight, "validate_receipt", lambda *args, **kwargs: None)
    receipt = preflight.execute_preflight(
        plan,
        arm,
        aws,
        s3,
        environment_receipt,
        source_spec,
        tmp_path,
        tmp_path / "ledger.json",
        expected_account_id="123456789012",
        expected_region="us-east-1",
        executor_runner=fake_executor,
        environment=environment,
        dry_run=True,
    )
    assert rebuilds == [True]
    assert delegated["arm_receipt"] == arm
    assert delegated["aws_execution_context_revalidation"] == aws
    assert delegated["s3_source_capability_revalidation"] == s3
    assert delegated["source_spec"] == source_spec
    assert delegated["environment"] == environment
    assert receipt[
        "runtime_aws_subprocess_environment_rebuilt_at_executor_delegation"
    ] is True


def test_permanent_authority_wall_is_explicit() -> None:
    source = Path(lock.__file__).read_text(encoding="utf-8")
    assert '"random_shuffle_used": False' in source
    assert '"may_update_ng_brain": False' in source
    assert '"execution_authority": False' in source
    assert '"cme_event_contracts_mode": "SHADOW"' in source
    assert '"brokerage_contract": "tastytrade_not_ibkr"' in source
    assert '"options_lane_started": False' in source
