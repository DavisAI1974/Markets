#!/usr/bin/env python3
"""Run readiness-v38 only after exact source-spec S3 capabilities are freshly revalidated."""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v34 as executor
import ng_historical_refinement_preflight_v36 as prior
import ng_historical_refinement_readiness as legacy_readiness
import ng_v38_s3_source_capability_revalidation_gate as s3_gate

SCHEMA = "ng_historical_refinement_preflight.v37"
EXECUTOR_CONTRACT = prior.EXECUTOR_CONTRACT
READINESS_CONTRACT = prior.READINESS_CONTRACT
STAGE_CONTRACT = prior.STAGE_CONTRACT
STAGE_CONTRACT_FINGERPRINT = prior.STAGE_CONTRACT_FINGERPRINT
_NEW_FIELDS = (
    "prior_preflight_fingerprint",
    "s3_source_capability_revalidation_receipt",
    "s3_source_capability_revalidation_fingerprint",
    "s3_source_spec_fingerprint",
    "required_bucket_locations_verified",
    "required_bucket_versioning_enabled_verified",
    "required_prefix_list_object_versions_access_verified",
    "checksum_enabled_head_object_access_verified",
    "corpus_completeness_claimed",
    "runtime_s3_source_capability_revalidation_at_executor_delegation",
)


class HistoricalRefinementPreflightV37Error(RuntimeError):
    pass


def _validated_s3_gate(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    receipt: Mapping[str, Any],
    source_spec: Mapping[str, Any],
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
        return s3_gate.validate_gate(
            receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            source_spec=source_spec,
            repository_root=repository_root,
            expected_account_id=expected_account_id,
            expected_region=expected_region,
            environment=environment,
            command_runner=command_runner,
            allow_custom_endpoint_urls=allow_custom_endpoint_urls,
            require_ready=True,
            verify_runtime=verify_runtime,
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        raise HistoricalRefinementPreflightV37Error(
            f"S3 source-capability revalidation is invalid: {error}"
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
    s3_receipt: Mapping[str, Any],
    source_spec: Mapping[str, Any],
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
    checked_s3 = _validated_s3_gate(
        plan,
        arm_receipt,
        s3_receipt,
        source_spec,
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
    result = copy.deepcopy(dict(base))
    result.update(
        {
            "schema": SCHEMA,
            "prior_preflight_fingerprint": base["fingerprint"],
            "s3_source_capability_revalidation_receipt": copy.deepcopy(checked_s3),
            "s3_source_capability_revalidation_fingerprint": checked_s3["fingerprint"],
            "s3_source_spec_fingerprint": checked_s3["source_spec_fingerprint"],
            "required_bucket_locations_verified": True,
            "required_bucket_versioning_enabled_verified": True,
            "required_prefix_list_object_versions_access_verified": True,
            "checksum_enabled_head_object_access_verified": True,
            "corpus_completeness_claimed": False,
            "runtime_s3_source_capability_revalidation_at_executor_delegation": True,
        }
    )
    result.pop("fingerprint", None)
    result["fingerprint"] = legacy_readiness._fingerprint(result)
    validate_receipt(
        result,
        repository_root=repository_root,
        source_spec=source_spec,
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
    s3_source_capability_revalidation: Mapping[str, Any],
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
    root = repository_root.expanduser().resolve(strict=False)
    checked_s3 = _validated_s3_gate(
        plan,
        arm_receipt,
        s3_source_capability_revalidation,
        source_spec,
        root,
        expected_account_id=expected_account_id,
        expected_region=expected_region,
        verify_runtime=True,
        environment=environment,
        command_runner=command_runner,
        allow_custom_endpoint_urls=allow_custom_endpoint_urls,
        timeout_seconds=timeout_seconds,
    )
    embedded_aws = checked_s3.get("aws_execution_context_revalidation_receipt")
    if not isinstance(embedded_aws, Mapping):
        raise HistoricalRefinementPreflightV37Error(
            "S3 capability receipt lacks the AWS execution-context receipt"
        )
    if embedded_aws.get("fingerprint") != aws_execution_context_revalidation.get("fingerprint"):
        raise HistoricalRefinementPreflightV37Error(
            "supplied AWS execution-context receipt differs from S3 capability lineage"
        )
    base_runner = executor.execute_next if executor_runner is None else executor_runner

    def guarded_runner(*args: Any, **runner_kwargs: Any) -> Mapping[str, Any]:
        _validated_s3_gate(
            plan,
            arm_receipt,
            s3_source_capability_revalidation,
            source_spec,
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
        aws_execution_context_revalidation,
        root,
        ledger_path,
        expected_account_id=expected_account_id,
        expected_region=expected_region,
        executor_runner=guarded_runner,
        environment=environment,
        command_runner=command_runner,
        allow_custom_endpoint_urls=allow_custom_endpoint_urls,
        timeout_seconds=timeout_seconds,
        **kwargs,
    )
    return _finalize(
        plan,
        arm_receipt,
        checked_s3,
        source_spec,
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
    source_spec: Mapping[str, Any] | None = None,
    verify_runtime: bool = True,
    environment: Mapping[str, str] | None = None,
    command_runner: Callable[[Sequence[str], float], Mapping[str, Any]] = s3_gate._default_command_runner,
    allow_custom_endpoint_urls: bool = False,
    timeout_seconds: float = 15.0,
) -> None:
    value = copy.deepcopy(dict(receipt))
    observed = value.pop("fingerprint", None)
    if value.get("schema") != SCHEMA or observed != legacy_readiness._fingerprint(value):
        raise HistoricalRefinementPreflightV37Error(
            "preflight v37 schema or fingerprint mismatch"
        )
    for field in (
        "required_bucket_locations_verified",
        "required_bucket_versioning_enabled_verified",
        "required_prefix_list_object_versions_access_verified",
        "checksum_enabled_head_object_access_verified",
        "runtime_s3_source_capability_revalidation_at_executor_delegation",
    ):
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV37Error(
                f"mandatory field mismatch: {field}"
            )
    if value.get("corpus_completeness_claimed") is not False:
        raise HistoricalRefinementPreflightV37Error(
            "capability preflight may not claim corpus completeness"
        )
    plan = value.get("execution_plan_snapshot")
    arm_receipt = value.get("pipeline_arm_receipt")
    s3_receipt = value.get("s3_source_capability_revalidation_receipt")
    if not all(isinstance(item, Mapping) for item in (plan, arm_receipt, s3_receipt)):
        raise HistoricalRefinementPreflightV37Error(
            "preflight v37 requires plan, arm, and S3 capability snapshots"
        )
    embedded_spec = s3_receipt.get("source_spec")
    effective_spec = source_spec if source_spec is not None else embedded_spec
    if not isinstance(effective_spec, Mapping):
        raise HistoricalRefinementPreflightV37Error("S3 source spec is missing")
    root = (
        repository_root.expanduser().resolve(strict=False)
        if repository_root is not None
        else Path(str(s3_receipt.get("repository_root") or "")).expanduser().resolve(strict=False)
    )
    embedded_aws = s3_receipt.get("aws_execution_context_revalidation_receipt")
    if not isinstance(embedded_aws, Mapping):
        raise HistoricalRefinementPreflightV37Error(
            "S3 capability receipt lacks AWS execution context"
        )
    checked_s3 = _validated_s3_gate(
        plan,
        arm_receipt,
        s3_receipt,
        effective_spec,
        root,
        expected_account_id=str(embedded_aws.get("expected_account_id") or ""),
        expected_region=str(embedded_aws.get("expected_region") or ""),
        verify_runtime=verify_runtime,
        environment=environment,
        command_runner=command_runner,
        allow_custom_endpoint_urls=allow_custom_endpoint_urls,
        timeout_seconds=timeout_seconds,
    )
    if value.get("s3_source_capability_revalidation_fingerprint") != checked_s3.get(
        "fingerprint"
    ):
        raise HistoricalRefinementPreflightV37Error(
            "S3 source-capability revalidation fingerprint mismatch"
        )
    if value.get("s3_source_spec_fingerprint") != checked_s3.get(
        "source_spec_fingerprint"
    ):
        raise HistoricalRefinementPreflightV37Error("S3 source-spec fingerprint mismatch")
    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("prior_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV37Error(
            "embedded preflight-v36 fingerprint mismatch"
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
    parser.add_argument("--s3-source-capability-revalidation", required=True)
    parser.add_argument("--source-spec", required=True)
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
    receipt = execute_preflight(
        legacy_executor._load_json(Path(args.plan)),
        legacy_executor._load_json(Path(args.arm_receipt)),
        legacy_executor._load_json(Path(args.aws_execution_context_revalidation)),
        legacy_executor._load_json(Path(args.s3_source_capability_revalidation)),
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
        allow_custom_endpoint_urls=args.allow_custom_endpoint_url,
        timeout_seconds=args.timeout_seconds,
    )
    legacy_executor._atomic_json(Path(args.out), receipt)
    print(
        f"[ng_historical_refinement_preflight_v37] {receipt['status']} "
        f"executor_called={receipt['executor_called']} s3_capabilities_revalidated=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
