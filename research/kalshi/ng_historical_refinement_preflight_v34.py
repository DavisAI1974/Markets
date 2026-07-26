#!/usr/bin/env python3
"""Run readiness-v38 only after every transitive local Python dependency is rehashed.

Preflight v33 revalidates every configured stage entrypoint at the executor boundary. This
wrapper additionally validates the complete local import closure for the historical corpus,
G15, and G16 code paths, then repeats that dependency validation inside the guarded runner
immediately before the first blocking stage is delegated to the executor.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v34 as executor
import ng_historical_refinement_preflight_v33 as prior
import ng_historical_refinement_readiness as legacy_readiness
import ng_v38_transitive_dependency_runtime_revalidation_gate as dependency_gate

SCHEMA = "ng_historical_refinement_preflight.v34"
EXECUTOR_CONTRACT = prior.EXECUTOR_CONTRACT
READINESS_CONTRACT = prior.READINESS_CONTRACT
STAGE_CONTRACT = prior.STAGE_CONTRACT
STAGE_CONTRACT_FINGERPRINT = prior.STAGE_CONTRACT_FINGERPRINT
_NEW_FIELDS = (
    "prior_preflight_fingerprint",
    "dependency_runtime_revalidation_receipt",
    "dependency_runtime_revalidation_fingerprint",
    "transitive_local_python_dependencies_rehashed",
    "all_entrypoints_in_dependency_closure",
    "runtime_dependency_revalidation_at_executor_delegation",
)


class HistoricalRefinementPreflightV34Error(RuntimeError):
    pass


def _validated_dependency_gate(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    receipt: Mapping[str, Any],
    repository_root: Path,
    *,
    verify_runtime: bool,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        return dependency_gate.validate_gate(
            receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            repository_root=repository_root,
            verify_runtime=verify_runtime,
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        raise HistoricalRefinementPreflightV34Error(
            f"transitive dependency runtime revalidation is invalid: {error}"
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
    dependency_receipt: Mapping[str, Any],
    repository_root: Path,
    base: Mapping[str, Any],
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    checked_dependency = _validated_dependency_gate(
        plan,
        arm_receipt,
        dependency_receipt,
        repository_root,
        verify_runtime=False,
        timeout_seconds=timeout_seconds,
    )
    prior.validate_receipt(base, verify_runtime=False, timeout_seconds=timeout_seconds)
    result = copy.deepcopy(dict(base))
    result.update(
        {
            "schema": SCHEMA,
            "prior_preflight_fingerprint": base["fingerprint"],
            "dependency_runtime_revalidation_receipt": copy.deepcopy(checked_dependency),
            "dependency_runtime_revalidation_fingerprint": checked_dependency["fingerprint"],
            "transitive_local_python_dependencies_rehashed": True,
            "all_entrypoints_in_dependency_closure": True,
            "runtime_dependency_revalidation_at_executor_delegation": True,
        }
    )
    result.pop("fingerprint", None)
    result["fingerprint"] = legacy_readiness._fingerprint(result)
    validate_receipt(
        result,
        repository_root=repository_root,
        verify_runtime=False,
        timeout_seconds=timeout_seconds,
    )
    return result


def execute_preflight(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    dependency_runtime_revalidation: Mapping[str, Any],
    repository_root: Path,
    ledger_path: Path,
    *,
    executor_runner: Callable[..., Mapping[str, Any]] | None = None,
    timeout_seconds: float = 10.0,
    **kwargs: Any,
) -> dict[str, Any]:
    root = repository_root.expanduser().resolve(strict=False)
    checked_dependency = _validated_dependency_gate(
        plan,
        arm_receipt,
        dependency_runtime_revalidation,
        root,
        verify_runtime=True,
        timeout_seconds=timeout_seconds,
    )
    embedded_all_stage = checked_dependency.get("all_stage_runtime_revalidation_receipt")
    if not isinstance(embedded_all_stage, Mapping):
        raise HistoricalRefinementPreflightV34Error(
            "dependency runtime receipt lacks the v33-compatible all-stage receipt"
        )
    base_runner = executor.execute_next if executor_runner is None else executor_runner

    def guarded_runner(*args: Any, **runner_kwargs: Any) -> Mapping[str, Any]:
        _validated_dependency_gate(
            plan,
            arm_receipt,
            dependency_runtime_revalidation,
            root,
            verify_runtime=True,
            timeout_seconds=timeout_seconds,
        )
        return base_runner(*args, **runner_kwargs)

    base = prior.execute_preflight(
        plan,
        arm_receipt,
        embedded_all_stage,
        ledger_path,
        executor_runner=guarded_runner,
        timeout_seconds=timeout_seconds,
        **kwargs,
    )
    return _finalize(
        plan,
        arm_receipt,
        checked_dependency,
        root,
        base,
        timeout_seconds=timeout_seconds,
    )


def validate_receipt(
    receipt: Mapping[str, Any],
    *,
    repository_root: Path | None = None,
    verify_runtime: bool = True,
    timeout_seconds: float = 10.0,
) -> None:
    value = copy.deepcopy(dict(receipt))
    observed = value.pop("fingerprint", None)
    if value.get("schema") != SCHEMA or observed != legacy_readiness._fingerprint(value):
        raise HistoricalRefinementPreflightV34Error(
            "preflight v34 schema or fingerprint mismatch"
        )
    for field in (
        "transitive_local_python_dependencies_rehashed",
        "all_entrypoints_in_dependency_closure",
        "runtime_dependency_revalidation_at_executor_delegation",
    ):
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV34Error(f"mandatory field mismatch: {field}")
    plan = value.get("execution_plan_snapshot")
    arm_receipt = value.get("pipeline_arm_receipt")
    dependency_receipt = value.get("dependency_runtime_revalidation_receipt")
    if not all(isinstance(item, Mapping) for item in (plan, arm_receipt, dependency_receipt)):
        raise HistoricalRefinementPreflightV34Error(
            "preflight v34 requires plan, arm, and dependency-runtime snapshots"
        )
    root = (
        repository_root.expanduser().resolve(strict=False)
        if repository_root is not None
        else Path(str(dependency_receipt.get("repository_root") or ""))
        .expanduser()
        .resolve(strict=False)
    )
    checked_dependency = _validated_dependency_gate(
        plan,
        arm_receipt,
        dependency_receipt,
        root,
        verify_runtime=verify_runtime,
        timeout_seconds=timeout_seconds,
    )
    if value.get("dependency_runtime_revalidation_fingerprint") != checked_dependency.get(
        "fingerprint"
    ):
        raise HistoricalRefinementPreflightV34Error(
            "dependency runtime revalidation fingerprint mismatch"
        )
    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("prior_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV34Error(
            "embedded preflight-v33 fingerprint mismatch"
        )
    prior.validate_receipt(base, verify_runtime=False, timeout_seconds=timeout_seconds)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--arm-receipt", required=True)
    parser.add_argument("--dependency-runtime-revalidation", required=True)
    parser.add_argument("--repository-root", required=True)
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
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    args = parser.parse_args(argv)
    plan = legacy_executor._load_json(Path(args.plan))
    arm_receipt = legacy_executor._load_json(Path(args.arm_receipt))
    dependency_receipt = legacy_executor._load_json(Path(args.dependency_runtime_revalidation))
    receipt = execute_preflight(
        plan,
        arm_receipt,
        dependency_receipt,
        Path(args.repository_root),
        Path(args.ledger),
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
        f"[ng_historical_refinement_preflight_v34] {receipt['status']} "
        f"executor_called={receipt['executor_called']} transitive_dependencies_revalidated=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
