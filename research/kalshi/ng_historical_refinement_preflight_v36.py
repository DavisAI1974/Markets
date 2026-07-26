#!/usr/bin/env python3
"""Run readiness-v38 only after AWS execution identity/configuration is freshly revalidated.

Preflight v35 proves code, Python, installed distributions, and AWS CLI bytes. This wrapper also
proves the exact STS caller identity, selected profile, effective region, and endpoint policy,
then repeats that AWS-context validation immediately before the guarded executor is delegated.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v34 as executor
import ng_historical_refinement_preflight_v35 as prior
import ng_historical_refinement_readiness as legacy_readiness
import ng_v38_aws_execution_context_revalidation_gate as aws_gate

SCHEMA = "ng_historical_refinement_preflight.v36"
EXECUTOR_CONTRACT = prior.EXECUTOR_CONTRACT
READINESS_CONTRACT = prior.READINESS_CONTRACT
STAGE_CONTRACT = prior.STAGE_CONTRACT
STAGE_CONTRACT_FINGERPRINT = prior.STAGE_CONTRACT_FINGERPRINT
_NEW_FIELDS = (
    "prior_preflight_fingerprint",
    "aws_execution_context_revalidation_receipt",
    "aws_execution_context_revalidation_fingerprint",
    "expected_aws_account_id",
    "expected_aws_region",
    "aws_caller_identity_account_id",
    "aws_caller_identity_arn",
    "sts_caller_identity_revalidated",
    "aws_account_bound_to_expected_account",
    "aws_region_bound_to_expected_region",
    "custom_aws_endpoints_rejected_unless_explicitly_allowed",
    "runtime_aws_context_revalidation_at_executor_delegation",
)


class HistoricalRefinementPreflightV36Error(RuntimeError):
    pass


def _validated_aws_gate(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    receipt: Mapping[str, Any],
    repository_root: Path,
    *,
    expected_account_id: str,
    expected_region: str,
    verify_runtime: bool,
    environment: Mapping[str, str] | None,
    command_runner: Callable[[Sequence[str], float], Mapping[str, Any]],
    allow_custom_endpoint_urls: bool,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        return aws_gate.validate_gate(
            receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            repository_root=repository_root,
            expected_account_id=expected_account_id,
            expected_region=expected_region,
            environment=environment,
            command_runner=command_runner,
            allow_custom_endpoint_urls=allow_custom_endpoint_urls,
            verify_runtime=verify_runtime,
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        raise HistoricalRefinementPreflightV36Error(
            f"AWS execution-context revalidation is invalid: {error}"
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
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    aws_receipt: Mapping[str, Any],
    repository_root: Path,
    base: Mapping[str, Any],
    *,
    expected_account_id: str,
    expected_region: str,
    environment: Mapping[str, str] | None,
    command_runner: Callable[[Sequence[str], float], Mapping[str, Any]],
    allow_custom_endpoint_urls: bool,
    timeout_seconds: float,
) -> dict[str, Any]:
    checked_aws = _validated_aws_gate(
        plan,
        arm_receipt,
        aws_receipt,
        repository_root,
        expected_account_id=expected_account_id,
        expected_region=expected_region,
        verify_runtime=False,
        environment=environment,
        command_runner=command_runner,
        allow_custom_endpoint_urls=allow_custom_endpoint_urls,
        timeout_seconds=timeout_seconds,
    )
    prior.validate_receipt(
        base,
        repository_root=repository_root,
        verify_runtime=False,
        timeout_seconds=timeout_seconds,
    )
    caller = checked_aws.get("caller_identity")
    if not isinstance(caller, Mapping):
        raise HistoricalRefinementPreflightV36Error(
            "AWS execution-context receipt lacks caller identity"
        )
    result = copy.deepcopy(dict(base))
    result.update(
        {
            "schema": SCHEMA,
            "prior_preflight_fingerprint": base["fingerprint"],
            "aws_execution_context_revalidation_receipt": copy.deepcopy(checked_aws),
            "aws_execution_context_revalidation_fingerprint": checked_aws["fingerprint"],
            "expected_aws_account_id": expected_account_id,
            "expected_aws_region": expected_region,
            "aws_caller_identity_account_id": caller.get("account_id"),
            "aws_caller_identity_arn": caller.get("arn"),
            "sts_caller_identity_revalidated": True,
            "aws_account_bound_to_expected_account": True,
            "aws_region_bound_to_expected_region": True,
            "custom_aws_endpoints_rejected_unless_explicitly_allowed": True,
            "runtime_aws_context_revalidation_at_executor_delegation": True,
        }
    )
    result.pop("fingerprint", None)
    result["fingerprint"] = legacy_readiness._fingerprint(result)
    validate_receipt(
        result,
        repository_root=repository_root,
        verify_runtime=False,
        environment=environment,
        command_runner=command_runner,
        allow_custom_endpoint_urls=allow_custom_endpoint_urls,
        timeout_seconds=timeout_seconds,
    )
    return result


def execute_preflight(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    aws_execution_context_revalidation: Mapping[str, Any],
    repository_root: Path,
    ledger_path: Path,
    *,
    expected_account_id: str,
    expected_region: str,
    executor_runner: Callable[..., Mapping[str, Any]] | None = None,
    environment: Mapping[str, str] | None = None,
    command_runner: Callable[[Sequence[str], float], Mapping[str, Any]] = aws_gate._default_command_runner,
    allow_custom_endpoint_urls: bool = False,
    timeout_seconds: float = 15.0,
    **kwargs: Any,
) -> dict[str, Any]:
    root = repository_root.expanduser().resolve(strict=False)
    checked_aws = _validated_aws_gate(
        plan,
        arm_receipt,
        aws_execution_context_revalidation,
        root,
        expected_account_id=expected_account_id,
        expected_region=expected_region,
        verify_runtime=True,
        environment=environment,
        command_runner=command_runner,
        allow_custom_endpoint_urls=allow_custom_endpoint_urls,
        timeout_seconds=timeout_seconds,
    )
    embedded_external = checked_aws.get("external_runtime_revalidation_receipt")
    if not isinstance(embedded_external, Mapping):
        raise HistoricalRefinementPreflightV36Error(
            "AWS execution-context receipt lacks the v35 external-runtime receipt"
        )
    base_runner = executor.execute_next if executor_runner is None else executor_runner

    def guarded_runner(*args: Any, **runner_kwargs: Any) -> Mapping[str, Any]:
        _validated_aws_gate(
            plan,
            arm_receipt,
            aws_execution_context_revalidation,
            root,
            expected_account_id=expected_account_id,
            expected_region=expected_region,
            verify_runtime=True,
            environment=environment,
            command_runner=command_runner,
            allow_custom_endpoint_urls=allow_custom_endpoint_urls,
            timeout_seconds=timeout_seconds,
        )
        return base_runner(*args, **runner_kwargs)

    base = prior.execute_preflight(
        plan,
        arm_receipt,
        embedded_external,
        root,
        ledger_path,
        executor_runner=guarded_runner,
        timeout_seconds=timeout_seconds,
        **kwargs,
    )
    return _finalize(
        plan,
        arm_receipt,
        checked_aws,
        root,
        base,
        expected_account_id=expected_account_id,
        expected_region=expected_region,
        environment=environment,
        command_runner=command_runner,
        allow_custom_endpoint_urls=allow_custom_endpoint_urls,
        timeout_seconds=timeout_seconds,
    )


def validate_receipt(
    receipt: Mapping[str, Any],
    *,
    repository_root: Path | None = None,
    verify_runtime: bool = True,
    environment: Mapping[str, str] | None = None,
    command_runner: Callable[[Sequence[str], float], Mapping[str, Any]] = aws_gate._default_command_runner,
    allow_custom_endpoint_urls: bool = False,
    timeout_seconds: float = 15.0,
) -> None:
    value = copy.deepcopy(dict(receipt))
    observed = value.pop("fingerprint", None)
    if value.get("schema") != SCHEMA or observed != legacy_readiness._fingerprint(value):
        raise HistoricalRefinementPreflightV36Error(
            "preflight v36 schema or fingerprint mismatch"
        )
    for field in (
        "sts_caller_identity_revalidated",
        "aws_account_bound_to_expected_account",
        "aws_region_bound_to_expected_region",
        "custom_aws_endpoints_rejected_unless_explicitly_allowed",
        "runtime_aws_context_revalidation_at_executor_delegation",
    ):
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV36Error(
                f"mandatory field mismatch: {field}"
            )
    plan = value.get("execution_plan_snapshot")
    arm_receipt = value.get("pipeline_arm_receipt")
    aws_receipt = value.get("aws_execution_context_revalidation_receipt")
    if not all(isinstance(item, Mapping) for item in (plan, arm_receipt, aws_receipt)):
        raise HistoricalRefinementPreflightV36Error(
            "preflight v36 requires plan, arm, and AWS-context snapshots"
        )
    root = (
        repository_root.expanduser().resolve(strict=False)
        if repository_root is not None
        else Path(str(aws_receipt.get("repository_root") or ""))
        .expanduser()
        .resolve(strict=False)
    )
    expected_account_id = str(value.get("expected_aws_account_id") or "")
    expected_region = str(value.get("expected_aws_region") or "")
    checked_aws = _validated_aws_gate(
        plan,
        arm_receipt,
        aws_receipt,
        root,
        expected_account_id=expected_account_id,
        expected_region=expected_region,
        verify_runtime=verify_runtime,
        environment=environment,
        command_runner=command_runner,
        allow_custom_endpoint_urls=allow_custom_endpoint_urls,
        timeout_seconds=timeout_seconds,
    )
    if value.get("aws_execution_context_revalidation_fingerprint") != checked_aws.get(
        "fingerprint"
    ):
        raise HistoricalRefinementPreflightV36Error(
            "AWS execution-context revalidation fingerprint mismatch"
        )
    caller = checked_aws.get("caller_identity")
    if not isinstance(caller, Mapping):
        raise HistoricalRefinementPreflightV36Error(
            "AWS caller identity is missing"
        )
    if value.get("aws_caller_identity_account_id") != caller.get("account_id"):
        raise HistoricalRefinementPreflightV36Error(
            "AWS caller account mismatch"
        )
    if value.get("aws_caller_identity_arn") != caller.get("arn"):
        raise HistoricalRefinementPreflightV36Error(
            "AWS caller ARN mismatch"
        )
    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("prior_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV36Error(
            "embedded preflight-v35 fingerprint mismatch"
        )
    prior.validate_receipt(
        base,
        repository_root=root,
        verify_runtime=False,
        timeout_seconds=timeout_seconds,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--arm-receipt", required=True)
    parser.add_argument("--aws-execution-context-revalidation", required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--expected-account-id", required=True)
    parser.add_argument("--expected-region", required=True)
    parser.add_argument("--allow-custom-endpoint-url", action="store_true")
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
    plan = legacy_executor._load_json(Path(args.plan))
    arm_receipt = legacy_executor._load_json(Path(args.arm_receipt))
    aws_receipt = legacy_executor._load_json(Path(args.aws_execution_context_revalidation))
    receipt = execute_preflight(
        plan,
        arm_receipt,
        aws_receipt,
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
        allow_custom_endpoint_urls=args.allow_custom_endpoint_url,
        timeout_seconds=args.timeout_seconds,
    )
    legacy_executor._atomic_json(Path(args.out), receipt)
    print(
        f"[ng_historical_refinement_preflight_v36] {receipt['status']} "
        f"executor_called={receipt['executor_called']} aws_context_revalidated=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
