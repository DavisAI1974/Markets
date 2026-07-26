#!/usr/bin/env python3
"""Lock the exact AWS subprocess environment used by readiness-v38 execution.

The identity and S3 capability gates prove which AWS principal, region, profile, buckets,
prefixes, version history, and checksum metadata are valid. The base historical executor,
however, builds a fresh subprocess environment from ambient process state. That creates a
time-of-check/time-of-use seam: direct credentials may be dropped, a different profile may
be selected, or an unvalidated endpoint override may reach the actual corpus command.

This gate derives one minimal launch environment from the freshly validated AWS and S3
receipts, forces the exact profile and region, preserves only required credential-provider
inputs, rejects every custom endpoint override, and records only redacted environment
evidence. Secret values are used for launch but never written to the receipt.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_corpus_executor_plan_compiler_v31 as compiler
import ng_v38_aws_execution_context_revalidation_gate as aws_gate
import ng_v38_s3_source_capability_revalidation_gate as s3_gate

SCHEMA = "ng_v38_aws_subprocess_environment_lock.v1"
READY = "V38_AWS_SUBPROCESS_ENVIRONMENT_LOCK_READY"

_BASE_ENV_KEYS = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PYTHONPATH",
    "VIRTUAL_ENV",
    "TMPDIR",
    "TEMP",
    "TMP",
)
_DIRECT_CREDENTIAL_KEYS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_SECURITY_TOKEN",
)
_CREDENTIAL_PROVIDER_KEYS = (
    "AWS_CONFIG_FILE",
    "AWS_SHARED_CREDENTIALS_FILE",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
    "AWS_ROLE_ARN",
    "AWS_ROLE_SESSION_NAME",
    "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    "AWS_CONTAINER_CREDENTIALS_FULL_URI",
    "AWS_CONTAINER_AUTHORIZATION_TOKEN",
    "AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE",
    "AWS_EC2_METADATA_DISABLED",
    "AWS_SDK_LOAD_CONFIG",
    "AWS_USE_FIPS_ENDPOINT",
    "AWS_USE_DUALSTACK_ENDPOINT",
    "AWS_CA_BUNDLE",
    "AWS_MAX_ATTEMPTS",
    "AWS_RETRY_MODE",
)
_PATH_VALUE_KEYS = (
    "AWS_CONFIG_FILE",
    "AWS_SHARED_CREDENTIALS_FILE",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
    "AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE",
    "AWS_CA_BUNDLE",
)
_ENDPOINT_OVERRIDE_KEYS = (
    "AWS_ENDPOINT_URL",
    "AWS_ENDPOINT_URL_S3",
    "S3_ENDPOINT_URL",
)
_PROFILE_KEYS = ("AWS_PROFILE", "AWS_DEFAULT_PROFILE")
_REGION_KEYS = ("AWS_REGION", "AWS_DEFAULT_REGION")


class V38AwsSubprocessEnvironmentLockError(ValueError):
    """Raised when the launch environment is incomplete, unsafe, or stale."""


def _fp(value: Any) -> str:
    return compiler._fp(value)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V38AwsSubprocessEnvironmentLockError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise V38AwsSubprocessEnvironmentLockError(
            f"JSON artifact must be an object: {path}"
        )
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _authority(value: Mapping[str, Any]) -> None:
    expected = {
        "paid_live_data_assumed": False,
        "corpus_files_opened": False,
        "outcome_files_opened": False,
        "actual_outcomes_used": False,
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
    }
    for field, expected_value in expected.items():
        if value.get(field) != expected_value:
            raise V38AwsSubprocessEnvironmentLockError(
                f"AWS subprocess environment lock must keep {field}={expected_value!r}"
            )


def _validated_inputs(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    aws_execution_context_receipt: Mapping[str, Any],
    s3_source_capability_receipt: Mapping[str, Any],
    source_spec: Mapping[str, Any],
    repository_root: Path,
    *,
    environment: Mapping[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = repository_root.expanduser().resolve(strict=False)
    account = str(aws_execution_context_receipt.get("expected_account_id") or "")
    region = str(aws_execution_context_receipt.get("expected_region") or "")
    try:
        checked_aws = aws_gate.validate_gate(
            aws_execution_context_receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            repository_root=root,
            expected_account_id=account,
            expected_region=region,
            environment=environment,
            allow_custom_endpoint_urls=False,
            verify_runtime=False,
        )
        checked_s3 = s3_gate.validate_gate(
            s3_source_capability_receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            source_spec=source_spec,
            repository_root=root,
            expected_account_id=account,
            expected_region=region,
            environment=environment,
            allow_custom_endpoint_urls=False,
            require_ready=True,
            verify_runtime=False,
        )
    except Exception as error:
        raise V38AwsSubprocessEnvironmentLockError(
            f"AWS/S3 execution provenance is invalid: {error}"
        ) from error
    embedded_aws = checked_s3.get("aws_execution_context_revalidation_receipt")
    if not isinstance(embedded_aws, Mapping):
        raise V38AwsSubprocessEnvironmentLockError(
            "S3 capability receipt lacks AWS execution-context lineage"
        )
    if embedded_aws.get("fingerprint") != checked_aws.get("fingerprint"):
        raise V38AwsSubprocessEnvironmentLockError(
            "AWS execution-context receipt differs from S3 capability lineage"
        )
    return checked_aws, checked_s3


def _path_evidence(value: str | None) -> dict[str, Any]:
    if value is None:
        return {"present": False, "basename": None, "path_fingerprint": None}
    expanded = str(Path(value).expanduser().resolve(strict=False))
    return {
        "present": True,
        "basename": Path(expanded).name,
        "path_fingerprint": hashlib.sha256(expanded.encode("utf-8")).hexdigest(),
    }


def _build_environment(
    checked_aws: Mapping[str, Any],
    environment: Mapping[str, str],
) -> tuple[dict[str, str], dict[str, Any]]:
    ambient = {str(key): str(value) for key, value in environment.items()}
    endpoint_values = {
        key: _clean(ambient.get(key)) for key in _ENDPOINT_OVERRIDE_KEYS
    }
    present_endpoints = {
        key: value for key, value in endpoint_values.items() if value is not None
    }
    if present_endpoints:
        raise V38AwsSubprocessEnvironmentLockError(
            "custom AWS/S3 endpoint overrides are forbidden at subprocess launch"
        )

    expected_profile = _clean(checked_aws.get("selected_profile"))
    expected_region = _clean(checked_aws.get("expected_region"))
    if expected_region is None:
        raise V38AwsSubprocessEnvironmentLockError(
            "validated AWS receipt lacks an expected region"
        )

    ambient_profile = (
        _clean(ambient.get("AWS_PROFILE"))
        or _clean(ambient.get("AWS_DEFAULT_PROFILE"))
    )
    ambient_region = (
        _clean(ambient.get("AWS_REGION"))
        or _clean(ambient.get("AWS_DEFAULT_REGION"))
    )
    if ambient_profile != expected_profile:
        raise V38AwsSubprocessEnvironmentLockError(
            "ambient AWS profile differs from the validated execution profile"
        )
    if ambient_region not in (None, expected_region):
        raise V38AwsSubprocessEnvironmentLockError(
            "ambient AWS region differs from the validated execution region"
        )

    launch: dict[str, str] = {}
    for key in (*_BASE_ENV_KEYS, *_DIRECT_CREDENTIAL_KEYS, *_CREDENTIAL_PROVIDER_KEYS):
        value = ambient.get(key)
        if value is not None:
            launch[key] = value

    if expected_profile is not None:
        launch["AWS_PROFILE"] = expected_profile
        launch["AWS_DEFAULT_PROFILE"] = expected_profile
    else:
        launch.pop("AWS_PROFILE", None)
        launch.pop("AWS_DEFAULT_PROFILE", None)

    launch["AWS_REGION"] = expected_region
    launch["AWS_DEFAULT_REGION"] = expected_region
    launch["AWS_PAGER"] = ""
    launch["AWS_CLI_AUTO_PROMPT"] = "off"
    launch["PYTHONHASHSEED"] = "0"
    launch["TZ"] = "UTC"

    safe_values = {
        key: launch.get(key)
        for key in (
            *_BASE_ENV_KEYS,
            *_PROFILE_KEYS,
            *_REGION_KEYS,
            "AWS_EC2_METADATA_DISABLED",
            "AWS_SDK_LOAD_CONFIG",
            "AWS_USE_FIPS_ENDPOINT",
            "AWS_USE_DUALSTACK_ENDPOINT",
            "AWS_MAX_ATTEMPTS",
            "AWS_RETRY_MODE",
            "AWS_PAGER",
            "AWS_CLI_AUTO_PROMPT",
            "PYTHONHASHSEED",
            "TZ",
        )
        if key in launch
    }
    path_values = {
        key: _path_evidence(_clean(launch.get(key))) for key in _PATH_VALUE_KEYS
    }
    evidence = {
        "launch_environment_keys": sorted(launch),
        "safe_values": safe_values,
        "direct_credential_presence": {
            key: key in launch for key in _DIRECT_CREDENTIAL_KEYS
        },
        "credential_provider_presence": {
            key: key in launch for key in _CREDENTIAL_PROVIDER_KEYS
        },
        "path_value_evidence": path_values,
        "endpoint_override_presence": {
            key: False for key in _ENDPOINT_OVERRIDE_KEYS
        },
        "secret_values_recorded": False,
        "exact_profile_forced": True,
        "exact_region_forced": True,
        "python_hash_seed_forced": True,
        "timezone_forced_utc": True,
    }
    return launch, evidence


def build_locked_environment(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    aws_execution_context_receipt: Mapping[str, Any],
    s3_source_capability_receipt: Mapping[str, Any],
    source_spec: Mapping[str, Any],
    repository_root: Path,
    *,
    environment: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    env = dict(os.environ if environment is None else environment)
    checked_aws, checked_s3 = _validated_inputs(
        plan,
        arm_receipt,
        aws_execution_context_receipt,
        s3_source_capability_receipt,
        source_spec,
        repository_root,
        environment=env,
    )
    launch_environment, evidence = _build_environment(checked_aws, env)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": READY,
        "repository_root": str(repository_root.expanduser().resolve(strict=False)),
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "pipeline_arm_receipt_fingerprint": arm_receipt.get("fingerprint"),
        "aws_execution_context_revalidation_fingerprint": checked_aws.get("fingerprint"),
        "s3_source_capability_revalidation_fingerprint": checked_s3.get("fingerprint"),
        "source_spec_fingerprint": s3_gate._fp(source_spec),
        "expected_account_id": checked_aws.get("expected_account_id"),
        "selected_profile": checked_aws.get("selected_profile"),
        "expected_region": checked_aws.get("expected_region"),
        "effective_region": checked_aws.get("effective_region"),
        "launch_environment_evidence": evidence,
        "launch_environment_evidence_fingerprint": _fp(evidence),
        "launch_environment_key_count": len(launch_environment),
        "exact_validated_profile_and_region_forced": True,
        "direct_credential_environment_preserved_when_present": True,
        "credential_provider_environment_preserved_when_present": True,
        "custom_endpoint_overrides_rejected": True,
        "secret_values_recorded": False,
        "subprocess_environment_rebuilt_immediately_before_launch": True,
        "configuration_only": True,
        "corpus_files_opened": False,
        "outcome_files_opened": False,
        "actual_outcomes_used": False,
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
        "next_permitted_stage": "RUN_FIRST_BLOCKING_STAGE_WITH_LOCKED_AWS_ENVIRONMENT",
    }
    result["fingerprint"] = _fp(result)
    validate_gate(
        result,
        plan=plan,
        arm_receipt=arm_receipt,
        aws_execution_context_receipt=checked_aws,
        s3_source_capability_receipt=checked_s3,
        source_spec=source_spec,
        repository_root=repository_root,
        environment=env,
    )
    return result, launch_environment


def build_gate(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    aws_execution_context_receipt: Mapping[str, Any],
    s3_source_capability_receipt: Mapping[str, Any],
    source_spec: Mapping[str, Any],
    repository_root: Path,
    *,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    receipt, _ = build_locked_environment(
        plan,
        arm_receipt,
        aws_execution_context_receipt,
        s3_source_capability_receipt,
        source_spec,
        repository_root,
        environment=environment,
    )
    return receipt


def validate_gate(
    value: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    aws_execution_context_receipt: Mapping[str, Any],
    s3_source_capability_receipt: Mapping[str, Any],
    source_spec: Mapping[str, Any],
    repository_root: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise V38AwsSubprocessEnvironmentLockError(
            "AWS subprocess environment lock schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked)
    if checked.get("status") != READY:
        raise V38AwsSubprocessEnvironmentLockError(
            "AWS subprocess environment lock is not ready"
        )
    for field in (
        "exact_validated_profile_and_region_forced",
        "direct_credential_environment_preserved_when_present",
        "credential_provider_environment_preserved_when_present",
        "custom_endpoint_overrides_rejected",
        "subprocess_environment_rebuilt_immediately_before_launch",
        "configuration_only",
    ):
        if checked.get(field) is not True:
            raise V38AwsSubprocessEnvironmentLockError(
                f"mandatory field mismatch: {field}"
            )
    if checked.get("secret_values_recorded") is not False:
        raise V38AwsSubprocessEnvironmentLockError(
            "secret values must never be recorded"
        )
    root = (
        repository_root.expanduser().resolve(strict=False)
        if repository_root is not None
        else Path(str(checked.get("repository_root") or "")).expanduser().resolve(strict=False)
    )
    env = dict(os.environ if environment is None else environment)
    checked_aws, checked_s3 = _validated_inputs(
        plan,
        arm_receipt,
        aws_execution_context_receipt,
        s3_source_capability_receipt,
        source_spec,
        root,
        environment=env,
    )
    launch_environment, evidence = _build_environment(checked_aws, env)
    expected_pairs = {
        "repository_root": str(root),
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "pipeline_arm_receipt_fingerprint": arm_receipt.get("fingerprint"),
        "aws_execution_context_revalidation_fingerprint": checked_aws.get("fingerprint"),
        "s3_source_capability_revalidation_fingerprint": checked_s3.get("fingerprint"),
        "source_spec_fingerprint": s3_gate._fp(source_spec),
        "expected_account_id": checked_aws.get("expected_account_id"),
        "selected_profile": checked_aws.get("selected_profile"),
        "expected_region": checked_aws.get("expected_region"),
        "effective_region": checked_aws.get("effective_region"),
        "launch_environment_evidence_fingerprint": _fp(evidence),
        "launch_environment_key_count": len(launch_environment),
    }
    for field, expected_value in expected_pairs.items():
        if checked.get(field) != expected_value:
            raise V38AwsSubprocessEnvironmentLockError(
                f"field mismatch: {field}"
            )
    if checked.get("launch_environment_evidence") != evidence:
        raise V38AwsSubprocessEnvironmentLockError(
            "launch environment evidence differs from current reconstruction"
        )
    rebuilt = copy.deepcopy(checked)
    rebuilt.pop("fingerprint", None)
    rebuilt["fingerprint"] = _fp(rebuilt)
    if rebuilt != dict(value):
        raise V38AwsSubprocessEnvironmentLockError(
            "AWS subprocess environment lock differs from deterministic reconstruction"
        )
    return copy.deepcopy(dict(value))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--arm-receipt", type=Path, required=True)
    parser.add_argument("--aws-execution-context-revalidation", type=Path, required=True)
    parser.add_argument("--s3-source-capability-revalidation", type=Path, required=True)
    parser.add_argument("--source-spec", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt = build_gate(
        _load(args.plan),
        _load(args.arm_receipt),
        _load(args.aws_execution_context_revalidation),
        _load(args.s3_source_capability_revalidation),
        _load(args.source_spec),
        args.repository_root,
    )
    _write(args.out, receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "selected_profile": receipt["selected_profile"],
                "expected_region": receipt["expected_region"],
                "launch_environment_key_count": receipt["launch_environment_key_count"],
                "fingerprint": receipt["fingerprint"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
