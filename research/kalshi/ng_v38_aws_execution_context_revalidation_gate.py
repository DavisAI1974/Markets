#!/usr/bin/env python3
"""Revalidate the exact AWS execution identity and configuration before readiness-v38 execution.

The external-runtime gate proves the Python environment and AWS CLI bytes. It does not prove
which AWS principal, profile, region, or endpoint configuration the CLI will use. This gate
calls STS without opening corpus objects, binds the returned principal to an expected account,
requires an exact region, and rejects custom AWS endpoints unless they are explicitly allowed.

Credential values are never recorded. Only safe configuration values and presence indicators
are included in the deterministic receipt.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_corpus_executor_plan_compiler_v31 as compiler
import ng_v38_external_runtime_dependency_revalidation_gate as external_gate

SCHEMA = "ng_v38_aws_execution_context_revalidation_gate.v1"
READY = "V38_AWS_EXECUTION_CONTEXT_REVALIDATED_READY"
_ACCOUNT_RE = re.compile(r"^[0-9]{12}$")
_REGION_RE = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z]+-[0-9]+$")
_SAFE_ENV_KEYS = (
    "AWS_PROFILE",
    "AWS_DEFAULT_PROFILE",
    "AWS_REGION",
    "AWS_DEFAULT_REGION",
    "AWS_EC2_METADATA_DISABLED",
    "AWS_USE_FIPS_ENDPOINT",
    "AWS_USE_DUALSTACK_ENDPOINT",
    "AWS_SDK_LOAD_CONFIG",
    "AWS_ROLE_ARN",
)
_ENDPOINT_ENV_KEYS = ("AWS_ENDPOINT_URL", "AWS_ENDPOINT_URL_S3")
_SECRET_ENV_KEYS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_SECURITY_TOKEN",
)
_PATH_ENV_KEYS = (
    "AWS_CONFIG_FILE",
    "AWS_SHARED_CREDENTIALS_FILE",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
)
_CREDENTIAL_URI_KEYS = (
    "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    "AWS_CONTAINER_CREDENTIALS_FULL_URI",
)


class V38AwsExecutionContextRevalidationError(ValueError):
    """Raised when AWS execution identity/configuration is incomplete, unsafe, or stale."""


def _fp(value: Any) -> str:
    return compiler._fp(value)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V38AwsExecutionContextRevalidationError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise V38AwsExecutionContextRevalidationError(
            f"JSON artifact must be an object: {path}"
        )
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any]) -> None:
    for field in (
        "paid_live_data_assumed",
        "corpus_files_opened",
        "outcome_files_opened",
        "random_shuffle_used",
        "may_change_blind_forecast",
        "may_change_g16_blind_prior",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise V38AwsExecutionContextRevalidationError(
                f"AWS execution-context revalidation must keep {field}=false"
            )
    if value.get("one_signal_authority_preserved") is not True:
        raise V38AwsExecutionContextRevalidationError("one signal authority must be preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise V38AwsExecutionContextRevalidationError("blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise V38AwsExecutionContextRevalidationError(
            "CME event contracts must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise V38AwsExecutionContextRevalidationError(
            "brokerage contract must remain tastytrade"
        )


def _default_command_runner(
    argv: Sequence[str],
    timeout_seconds: float,
) -> Mapping[str, Any]:
    process = subprocess.run(
        list(argv),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_seconds,
    )
    return {
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def _run(
    argv: Sequence[str],
    *,
    command_runner: Callable[[Sequence[str], float], Mapping[str, Any]],
    timeout_seconds: float,
    label: str,
    allow_empty_stdout: bool = False,
) -> str:
    try:
        result = dict(command_runner(tuple(argv), timeout_seconds))
    except Exception as error:
        raise V38AwsExecutionContextRevalidationError(
            f"{label} probe failed: {error}"
        ) from error
    if int(result.get("returncode", 1)) != 0:
        stderr = str(result.get("stderr") or "").strip()
        raise V38AwsExecutionContextRevalidationError(
            f"{label} probe failed with nonzero exit: {stderr}"
        )
    stdout = str(result.get("stdout") or "").strip()
    if not stdout and not allow_empty_stdout:
        raise V38AwsExecutionContextRevalidationError(
            f"{label} probe returned no output"
        )
    return stdout


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _path_env_evidence(environment: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    for key in _PATH_ENV_KEYS:
        value = _clean(environment.get(key))
        if value is None:
            evidence[key] = {"present": False, "basename": None, "path_fingerprint": None}
            continue
        expanded = str(Path(value).expanduser().resolve(strict=False))
        evidence[key] = {
            "present": True,
            "basename": Path(expanded).name,
            "path_fingerprint": hashlib.sha256(expanded.encode("utf-8")).hexdigest(),
        }
    return evidence


def _environment_evidence(
    environment: Mapping[str, str],
    *,
    allow_custom_endpoint_urls: bool,
) -> dict[str, Any]:
    safe = {key: _clean(environment.get(key)) for key in _SAFE_ENV_KEYS}
    endpoint_values = {key: _clean(environment.get(key)) for key in _ENDPOINT_ENV_KEYS}
    custom_endpoints = {key: value for key, value in endpoint_values.items() if value is not None}
    if custom_endpoints and not allow_custom_endpoint_urls:
        raise V38AwsExecutionContextRevalidationError(
            "custom AWS endpoint configuration is forbidden"
        )
    profile = safe["AWS_PROFILE"]
    default_profile = safe["AWS_DEFAULT_PROFILE"]
    if profile and default_profile and profile != default_profile:
        raise V38AwsExecutionContextRevalidationError(
            "AWS_PROFILE and AWS_DEFAULT_PROFILE disagree"
        )
    region = safe["AWS_REGION"]
    default_region = safe["AWS_DEFAULT_REGION"]
    if region and default_region and region != default_region:
        raise V38AwsExecutionContextRevalidationError(
            "AWS_REGION and AWS_DEFAULT_REGION disagree"
        )
    return {
        "safe_values": safe,
        "endpoint_values": endpoint_values,
        "secret_value_presence": {
            key: _clean(environment.get(key)) is not None for key in _SECRET_ENV_KEYS
        },
        "path_value_evidence": _path_env_evidence(environment),
        "credential_uri_presence": {
            key: _clean(environment.get(key)) is not None for key in _CREDENTIAL_URI_KEYS
        },
        "credential_values_recorded": False,
        "custom_endpoint_urls_allowed": bool(allow_custom_endpoint_urls),
        "custom_endpoint_urls_present": bool(custom_endpoints),
    }


def _effective_profile(environment_evidence: Mapping[str, Any]) -> str | None:
    safe = environment_evidence.get("safe_values")
    if not isinstance(safe, Mapping):
        raise V38AwsExecutionContextRevalidationError(
            "AWS environment evidence lacks safe values"
        )
    return _clean(safe.get("AWS_PROFILE")) or _clean(safe.get("AWS_DEFAULT_PROFILE"))


def _effective_env_region(environment_evidence: Mapping[str, Any]) -> str | None:
    safe = environment_evidence.get("safe_values")
    if not isinstance(safe, Mapping):
        raise V38AwsExecutionContextRevalidationError(
            "AWS environment evidence lacks safe values"
        )
    return _clean(safe.get("AWS_REGION")) or _clean(safe.get("AWS_DEFAULT_REGION"))


def _aws_path(external_receipt: Mapping[str, Any]) -> Path:
    executables = external_receipt.get("runtime_executables")
    if not isinstance(executables, Mapping):
        raise V38AwsExecutionContextRevalidationError(
            "external runtime receipt lacks executable evidence"
        )
    aws = executables.get("aws")
    if not isinstance(aws, Mapping):
        raise V38AwsExecutionContextRevalidationError(
            "external runtime receipt lacks AWS CLI evidence"
        )
    path = Path(str(aws.get("path") or "")).expanduser().resolve(strict=False)
    if not path.is_file():
        raise V38AwsExecutionContextRevalidationError(
            f"validated AWS CLI path is missing: {path}"
        )
    return path


def _profile_args(profile: str | None) -> list[str]:
    return ["--profile", profile] if profile else []


def _configured_region(
    aws_path: Path,
    profile: str | None,
    *,
    command_runner: Callable[[Sequence[str], float], Mapping[str, Any]],
    timeout_seconds: float,
) -> str | None:
    argv = [str(aws_path), *_profile_args(profile), "configure", "get", "region"]
    try:
        result = dict(command_runner(tuple(argv), timeout_seconds))
    except Exception as error:
        raise V38AwsExecutionContextRevalidationError(
            f"AWS configured-region probe failed: {error}"
        ) from error
    returncode = int(result.get("returncode", 1))
    stdout = str(result.get("stdout") or "").strip()
    if returncode == 0:
        return _clean(stdout)
    if returncode == 1 and not stdout:
        return None
    stderr = str(result.get("stderr") or "").strip()
    raise V38AwsExecutionContextRevalidationError(
        f"AWS configured-region probe failed with nonzero exit: {stderr}"
    )


def _caller_identity(
    aws_path: Path,
    profile: str | None,
    region: str,
    *,
    command_runner: Callable[[Sequence[str], float], Mapping[str, Any]],
    timeout_seconds: float,
) -> dict[str, str]:
    argv = [
        str(aws_path),
        *_profile_args(profile),
        "--region",
        region,
        "--no-cli-pager",
        "sts",
        "get-caller-identity",
        "--output",
        "json",
    ]
    text = _run(
        argv,
        command_runner=command_runner,
        timeout_seconds=timeout_seconds,
        label="AWS STS caller-identity",
    )
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        raise V38AwsExecutionContextRevalidationError(
            "AWS STS caller-identity returned invalid JSON"
        ) from error
    if not isinstance(raw, Mapping):
        raise V38AwsExecutionContextRevalidationError(
            "AWS STS caller-identity must be a JSON object"
        )
    account = _clean(raw.get("Account"))
    arn = _clean(raw.get("Arn"))
    user_id = _clean(raw.get("UserId"))
    if account is None or not _ACCOUNT_RE.fullmatch(account):
        raise V38AwsExecutionContextRevalidationError(
            "AWS STS caller-identity Account must be a 12-digit account ID"
        )
    if arn is None or not arn.startswith("arn:") or f"::{account}:" not in arn:
        raise V38AwsExecutionContextRevalidationError(
            "AWS STS caller-identity Arn is missing or inconsistent with Account"
        )
    if user_id is None:
        raise V38AwsExecutionContextRevalidationError(
            "AWS STS caller-identity UserId is missing"
        )
    return {"account_id": account, "arn": arn, "user_id": user_id}


def build_gate(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    external_runtime_receipt: Mapping[str, Any],
    repository_root: Path,
    *,
    expected_account_id: str,
    expected_region: str,
    environment: Mapping[str, str] | None = None,
    command_runner: Callable[[Sequence[str], float], Mapping[str, Any]] = _default_command_runner,
    allow_custom_endpoint_urls: bool = False,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    account = str(expected_account_id or "").strip()
    region = str(expected_region or "").strip()
    if not _ACCOUNT_RE.fullmatch(account):
        raise V38AwsExecutionContextRevalidationError(
            "expected_account_id must be a 12-digit account ID"
        )
    if not _REGION_RE.fullmatch(region):
        raise V38AwsExecutionContextRevalidationError(
            "expected_region must be an explicit AWS region"
        )
    root = repository_root.expanduser().resolve(strict=False)
    try:
        checked_external = external_gate.validate_gate(
            external_runtime_receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            repository_root=root,
            verify_runtime=True,
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        raise V38AwsExecutionContextRevalidationError(
            f"external runtime receipt is invalid: {error}"
        ) from error
    env = dict(os.environ if environment is None else environment)
    env_evidence = _environment_evidence(
        env,
        allow_custom_endpoint_urls=allow_custom_endpoint_urls,
    )
    profile = _effective_profile(env_evidence)
    env_region = _effective_env_region(env_evidence)
    configured_region = _configured_region(
        _aws_path(checked_external),
        profile,
        command_runner=command_runner,
        timeout_seconds=timeout_seconds,
    )
    effective_region = env_region or configured_region
    if effective_region is None:
        raise V38AwsExecutionContextRevalidationError(
            "AWS region is not configured in the environment or selected profile"
        )
    if effective_region != region:
        raise V38AwsExecutionContextRevalidationError(
            f"effective AWS region mismatch: expected {region}, got {effective_region}"
        )
    identity = _caller_identity(
        _aws_path(checked_external),
        profile,
        region,
        command_runner=command_runner,
        timeout_seconds=timeout_seconds,
    )
    if identity["account_id"] != account:
        raise V38AwsExecutionContextRevalidationError(
            f"AWS account mismatch: expected {account}, got {identity['account_id']}"
        )
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": READY,
        "repository_root": str(root),
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "pipeline_arm_receipt_fingerprint": arm_receipt.get("fingerprint"),
        "external_runtime_revalidation_receipt": copy.deepcopy(dict(checked_external)),
        "external_runtime_revalidation_fingerprint": checked_external.get("fingerprint"),
        "expected_account_id": account,
        "expected_region": region,
        "selected_profile": profile,
        "environment_region": env_region,
        "configured_profile_region": configured_region,
        "effective_region": effective_region,
        "aws_environment": env_evidence,
        "aws_environment_fingerprint": _fp(env_evidence),
        "caller_identity": identity,
        "caller_identity_fingerprint": _fp(identity),
        "sts_caller_identity_revalidated": True,
        "aws_account_bound_to_expected_account": True,
        "aws_region_bound_to_expected_region": True,
        "custom_aws_endpoints_rejected_unless_explicitly_allowed": True,
        "credential_values_recorded": False,
        "aws_execution_context_revalidation_immediately_before_executor_delegation": True,
        "configuration_and_identity_only": True,
        "corpus_files_opened": False,
        "outcome_files_opened": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_g16_blind_prior": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "RUN_BRANCH_GUARDED_FIRST_BLOCKING_STAGE",
    }
    result["fingerprint"] = _fp(result)
    validate_gate(
        result,
        plan=plan,
        arm_receipt=arm_receipt,
        repository_root=root,
        expected_account_id=account,
        expected_region=region,
        environment=env,
        command_runner=command_runner,
        allow_custom_endpoint_urls=allow_custom_endpoint_urls,
        verify_runtime=False,
        timeout_seconds=timeout_seconds,
    )
    return result


def validate_gate(
    value: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    repository_root: Path | None = None,
    expected_account_id: str | None = None,
    expected_region: str | None = None,
    environment: Mapping[str, str] | None = None,
    command_runner: Callable[[Sequence[str], float], Mapping[str, Any]] = _default_command_runner,
    allow_custom_endpoint_urls: bool | None = None,
    verify_runtime: bool = True,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise V38AwsExecutionContextRevalidationError(
            "AWS execution-context receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked)
    if checked.get("status") != READY:
        raise V38AwsExecutionContextRevalidationError(
            "AWS execution-context revalidation is not ready"
        )
    for field in (
        "sts_caller_identity_revalidated",
        "aws_account_bound_to_expected_account",
        "aws_region_bound_to_expected_region",
        "custom_aws_endpoints_rejected_unless_explicitly_allowed",
        "aws_execution_context_revalidation_immediately_before_executor_delegation",
        "configuration_and_identity_only",
    ):
        if checked.get(field) is not True:
            raise V38AwsExecutionContextRevalidationError(
                f"mandatory field mismatch: {field}"
            )
    if checked.get("credential_values_recorded") is not False:
        raise V38AwsExecutionContextRevalidationError(
            "credential values must never be recorded"
        )
    root = (
        repository_root.expanduser().resolve(strict=False)
        if repository_root is not None
        else Path(str(checked.get("repository_root") or "")).expanduser().resolve(strict=False)
    )
    if str(root) != checked.get("repository_root"):
        raise V38AwsExecutionContextRevalidationError("repository root mismatch")
    external_receipt = checked.get("external_runtime_revalidation_receipt")
    if not isinstance(external_receipt, Mapping):
        raise V38AwsExecutionContextRevalidationError(
            "embedded external-runtime receipt is missing"
        )
    try:
        validated_external = external_gate.validate_gate(
            external_receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            repository_root=root,
            verify_runtime=verify_runtime,
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        raise V38AwsExecutionContextRevalidationError(
            f"embedded external-runtime receipt is invalid: {error}"
        ) from error
    expected_pairs = {
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "pipeline_arm_receipt_fingerprint": arm_receipt.get("fingerprint"),
        "external_runtime_revalidation_fingerprint": validated_external.get("fingerprint"),
    }
    for field, expected in expected_pairs.items():
        if checked.get(field) != expected:
            raise V38AwsExecutionContextRevalidationError(f"field mismatch: {field}")
    for field, fingerprint_field in (
        ("aws_environment", "aws_environment_fingerprint"),
        ("caller_identity", "caller_identity_fingerprint"),
    ):
        evidence = checked.get(field)
        if checked.get(fingerprint_field) != _fp(evidence):
            raise V38AwsExecutionContextRevalidationError(
                f"evidence fingerprint mismatch: {field}"
            )
    account = str(expected_account_id or checked.get("expected_account_id") or "").strip()
    region = str(expected_region or checked.get("expected_region") or "").strip()
    if checked.get("expected_account_id") != account:
        raise V38AwsExecutionContextRevalidationError("expected AWS account mismatch")
    if checked.get("expected_region") != region:
        raise V38AwsExecutionContextRevalidationError("expected AWS region mismatch")
    allow_custom = (
        bool(allow_custom_endpoint_urls)
        if allow_custom_endpoint_urls is not None
        else bool(
            (checked.get("aws_environment") or {}).get("custom_endpoint_urls_allowed")
        )
    )
    if verify_runtime:
        rebuilt = build_gate(
            plan,
            arm_receipt,
            external_receipt,
            root,
            expected_account_id=account,
            expected_region=region,
            environment=environment,
            command_runner=command_runner,
            allow_custom_endpoint_urls=allow_custom,
            timeout_seconds=timeout_seconds,
        )
        if checked != rebuilt:
            raise V38AwsExecutionContextRevalidationError(
                "AWS execution-context receipt differs from current deterministic reconstruction"
            )
    return copy.deepcopy(dict(value))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--arm-receipt", type=Path, required=True)
    parser.add_argument("--external-runtime-revalidation", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--expected-account-id", required=True)
    parser.add_argument("--expected-region", required=True)
    parser.add_argument("--allow-custom-endpoint-url", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    args = parser.parse_args(argv)
    receipt = build_gate(
        _load(args.plan),
        _load(args.arm_receipt),
        _load(args.external_runtime_revalidation),
        args.repository_root,
        expected_account_id=args.expected_account_id,
        expected_region=args.expected_region,
        allow_custom_endpoint_urls=args.allow_custom_endpoint_url,
        timeout_seconds=args.timeout_seconds,
    )
    _write(args.out, receipt)
    print(json.dumps({"status": receipt["status"], "fingerprint": receipt["fingerprint"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
