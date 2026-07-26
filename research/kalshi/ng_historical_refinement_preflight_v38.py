#!/usr/bin/env python3
"""Run readiness-v38 only with an exact locked AWS subprocess environment."""
from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v35 as executor
import ng_historical_refinement_preflight_v37 as prior
import ng_historical_refinement_readiness as legacy_readiness
import ng_v38_aws_subprocess_environment_lock as environment_lock
import ng_v38_s3_source_capability_revalidation_gate as s3_gate

SCHEMA = "ng_historical_refinement_preflight.v38"
EXECUTOR_CONTRACT = prior.EXECUTOR_CONTRACT
READINESS_CONTRACT = prior.READINESS_CONTRACT
STAGE_CONTRACT = prior.STAGE_CONTRACT
STAGE_CONTRACT_FINGERPRINT = prior.STAGE_CONTRACT_FINGERPRINT
_NEW_FIELDS = (
    "prior_preflight_fingerprint",
    "aws_subprocess_environment_lock_receipt",
    "aws_subprocess_environment_lock_fingerprint",
    "exact_validated_profile_and_region_forced",
    "direct_credential_environment_preserved_when_present",
    "credential_provider_environment_preserved_when_present",
    "custom_endpoint_overrides_rejected_at_subprocess_launch",
    "secret_values_recorded",
    "runtime_aws_subprocess_environment_rebuilt_at_executor_delegation",
)


class HistoricalRefinementPreflightV38Error(RuntimeError):
    pass


def _validated_environment_lock(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    aws_receipt: Mapping[str, Any],
    s3_receipt: Mapping[str, Any],
    environment_receipt: Mapping[str, Any],
    source_spec: Mapping[str, Any],
    repository_root: Path,
    *,
    environment: Mapping[str, str] | None,
) -> dict[str, Any]:
    try:
        return environment_lock.validate_gate(
            environment_receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            aws_execution_context_receipt=aws_receipt,
            s3_source_capability_receipt=s3_receipt,
            source_spec=source_spec,
            repository_root=repository_root,
            environment=environment,
        )
    except Exception as error:
        raise HistoricalRefinementPreflightV38Error(
            f"AWS subprocess environment lock is invalid: {error}"
        ) from error


def _base_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    prior_fingerprint = base.pop("prior_preflight_fingerprint", None)
    for field in _NEW_FIELDS[1:]:
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = prior.SCHEMA
    base["fingerprint"] = prior_fingerprint
    return base


def _finalize(
    base: Mapping[str, Any],
    environment_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(dict(base))
    result.update(
        {
            "schema": SCHEMA,
            "prior_preflight_fingerprint": base["fingerprint"],
            "aws_subprocess_environment_lock_receipt": copy.deepcopy(
                dict(environment_receipt)
            ),
            "aws_subprocess_environment_lock_fingerprint": environment_receipt[
                "fingerprint"
            ],
            "exact_validated_profile_and_region_forced": True,
            "direct_credential_environment_preserved_when_present": True,
            "credential_provider_environment_preserved_when_present": True,
            "custom_endpoint_overrides_rejected_at_subprocess_launch": True,
            "secret_values_recorded": False,
            "runtime_aws_subprocess_environment_rebuilt_at_executor_delegation": True,
        }
    )
    result.pop("fingerprint", None)
    result["fingerprint"] = legacy_readiness._fingerprint(result)
    return result


def execute_preflight(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    aws_execution_context_revalidation: Mapping[str, Any],
    s3_source_capability_revalidation: Mapping[str, Any],
    aws_subprocess_environment_lock: Mapping[str, Any],
    source_spec: Mapping[str, Any],
    repository_root: Path,
    ledger_path: Path,
    *,
    expected_account_id: str,
    expected_region: str,
    executor_runner: Callable[..., Mapping[str, Any]] | None = None,
    environment: Mapping[str, str] | None = None,
    command_runner: Callable[[Sequence[str], float], Mapping[str, Any]] = s3_gate._default_command_runner,
    allow_custom_endpoint_urls: bool = False,
    timeout_seconds: float = 15.0,
    **kwargs: Any,
) -> dict[str, Any]:
    if allow_custom_endpoint_urls:
        raise HistoricalRefinementPreflightV38Error(
            "custom endpoint URLs are not permitted at the execution boundary"
        )
    root = repository_root.expanduser().resolve(strict=False)
    env = dict(os.environ if environment is None else environment)
    checked_environment = _validated_environment_lock(
        plan,
        arm_receipt,
        aws_execution_context_revalidation,
        s3_source_capability_revalidation,
        aws_subprocess_environment_lock,
        source_spec,
        root,
        environment=env,
    )
    base_runner = executor.execute_next if executor_runner is None else executor_runner

    def guarded_runner(*args: Any, **runner_kwargs: Any) -> Mapping[str, Any]:
        fresh_receipt, _ = environment_lock.build_locked_environment(
            plan,
            arm_receipt,
            aws_execution_context_revalidation,
            s3_source_capability_revalidation,
            source_spec,
            root,
            environment=env,
        )
        if fresh_receipt != dict(aws_subprocess_environment_lock):
            raise HistoricalRefinementPreflightV38Error(
                "AWS subprocess environment changed before executor delegation"
            )
        return base_runner(
            *args,
            arm_receipt=arm_receipt,
            aws_execution_context_revalidation=aws_execution_context_revalidation,
            s3_source_capability_revalidation=s3_source_capability_revalidation,
            source_spec=source_spec,
            repository_root=root,
            environment=env,
            **runner_kwargs,
        )

    base = prior.execute_preflight(
        plan,
        arm_receipt,
        aws_execution_context_revalidation,
        s3_source_capability_revalidation,
        source_spec,
        root,
        ledger_path,
        expected_account_id=expected_account_id,
        expected_region=expected_region,
        executor_runner=guarded_runner,
        environment=env,
        command_runner=command_runner,
        allow_custom_endpoint_urls=False,
        timeout_seconds=timeout_seconds,
        **kwargs,
    )
    result = _finalize(base, checked_environment)
    validate_receipt(
        result,
        repository_root=root,
        source_spec=source_spec,
        environment=env,
        verify_runtime=False,
    )
    return result


def validate_receipt(
    receipt: Mapping[str, Any],
    *,
    repository_root: Path | None = None,
    source_spec: Mapping[str, Any] | None = None,
    environment: Mapping[str, str] | None = None,
    verify_runtime: bool = True,
) -> None:
    value = copy.deepcopy(dict(receipt))
    observed = value.pop("fingerprint", None)
    if value.get("schema") != SCHEMA or observed != legacy_readiness._fingerprint(value):
        raise HistoricalRefinementPreflightV38Error(
            "preflight v38 schema or fingerprint mismatch"
        )
    for field in (
        "exact_validated_profile_and_region_forced",
        "direct_credential_environment_preserved_when_present",
        "credential_provider_environment_preserved_when_present",
        "custom_endpoint_overrides_rejected_at_subprocess_launch",
        "runtime_aws_subprocess_environment_rebuilt_at_executor_delegation",
    ):
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV38Error(
                f"mandatory field mismatch: {field}"
            )
    if value.get("secret_values_recorded") is not False:
        raise HistoricalRefinementPreflightV38Error(
            "secret values must never be recorded"
        )
    plan = value.get("execution_plan_snapshot")
    arm_receipt = value.get("pipeline_arm_receipt")
    aws_receipt = value.get("aws_execution_context_revalidation_receipt")
    s3_receipt = value.get("s3_source_capability_revalidation_receipt")
    environment_receipt = value.get("aws_subprocess_environment_lock_receipt")
    if not all(
        isinstance(item, Mapping)
        for item in (plan, arm_receipt, aws_receipt, s3_receipt, environment_receipt)
    ):
        raise HistoricalRefinementPreflightV38Error(
            "preflight v38 requires plan, arm, AWS, S3, and environment-lock snapshots"
        )
    embedded_spec = s3_receipt.get("source_spec")
    effective_spec = source_spec if source_spec is not None else embedded_spec
    if not isinstance(effective_spec, Mapping):
        raise HistoricalRefinementPreflightV38Error("S3 source spec is missing")
    root = (
        repository_root.expanduser().resolve(strict=False)
        if repository_root is not None
        else Path(str(environment_receipt.get("repository_root") or "")).expanduser().resolve(
            strict=False
        )
    )
    checked_environment = _validated_environment_lock(
        plan,
        arm_receipt,
        aws_receipt,
        s3_receipt,
        environment_receipt,
        effective_spec,
        root,
        environment=dict(os.environ if environment is None else environment),
    )
    if value.get("aws_subprocess_environment_lock_fingerprint") != checked_environment.get(
        "fingerprint"
    ):
        raise HistoricalRefinementPreflightV38Error(
            "AWS subprocess environment lock fingerprint mismatch"
        )
    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("prior_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV38Error(
            "embedded preflight-v37 fingerprint mismatch"
        )
    prior.validate_receipt(
        base,
        repository_root=root,
        source_spec=effective_spec,
        verify_runtime=verify_runtime,
        environment=environment,
        allow_custom_endpoint_urls=False,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--arm-receipt", required=True)
    parser.add_argument("--aws-execution-context-revalidation", required=True)
    parser.add_argument("--s3-source-capability-revalidation", required=True)
    parser.add_argument("--aws-subprocess-environment-lock", required=True)
    parser.add_argument("--source-spec", required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--expected-account-id", required=True)
    parser.add_argument("--expected-region", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--readiness-out")
    parser.add_argument("--expected-branch", default=branch_alignment.DEFAULT_BRANCH)
    parser.add_argument("--expected-repository", default=branch_alignment.DEFAULT_REPOSITORY)
    parser.add_argument("--remote", default=branch_alignment.DEFAULT_REMOTE)
    parser.add_argument("--allow-dirty-prefix", action="append", default=[])
    parser.add_argument("--allow-local-ahead", action="store_true")
    parser.add_argument("--allow-missing-remote-ref", action="store_true")
    parser.add_argument("--allow-fixed-outcomes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    args = parser.parse_args(argv)
    receipt = execute_preflight(
        legacy_executor._load_json(Path(args.plan)),
        legacy_executor._load_json(Path(args.arm_receipt)),
        legacy_executor._load_json(Path(args.aws_execution_context_revalidation)),
        legacy_executor._load_json(Path(args.s3_source_capability_revalidation)),
        legacy_executor._load_json(Path(args.aws_subprocess_environment_lock)),
        legacy_executor._load_json(Path(args.source_spec)),
        Path(args.repository_root),
        Path(args.ledger),
        expected_account_id=args.expected_account_id,
        expected_region=args.expected_region,
        expected_branch=args.expected_branch,
        expected_repository=args.expected_repository,
        remote=args.remote,
        allowed_dirty_prefixes=tuple(args.allow_dirty_prefix),
        require_remote_match=not args.allow_missing_remote_ref,
        allow_local_ahead=args.allow_local_ahead,
        allow_fixed_outcomes=args.allow_fixed_outcomes,
        dry_run=args.dry_run,
        readiness_out=Path(args.readiness_out) if args.readiness_out else None,
        timeout_seconds=args.timeout_seconds,
    )
    legacy_executor._atomic_json(Path(args.out), receipt)
    print(
        f"[ng_historical_refinement_preflight_v38] {receipt['status']} "
        f"executor_called={receipt['executor_called']} aws_environment_locked=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
