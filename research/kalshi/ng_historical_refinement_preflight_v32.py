#!/usr/bin/env python3
"""Run branch preflight only after fresh readiness-v38 runtime revalidation.

This wrapper upgrades preflight v31 with a fail-closed time-of-check/time-of-use gate.
Immediately before the guarded executor can run one first-blocking stage, it replays the
help-only CLI probes, rehashes every extension-stage script, and reconstructs the exact
command-artifact lineage. Fixed G16 scoring/publication remains disabled.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor_v34 as executor
import ng_historical_refinement_preflight_v31 as prior
import ng_v38_execution_runtime_revalidation_gate as runtime_gate

SCHEMA = "ng_historical_refinement_preflight.v32"
EXECUTOR_CONTRACT = prior.EXECUTOR_CONTRACT
READINESS_CONTRACT = prior.READINESS_CONTRACT
STAGE_CONTRACT = prior.STAGE_CONTRACT
STAGE_CONTRACT_FINGERPRINT = prior.STAGE_CONTRACT_FINGERPRINT
_RUNTIME_FIELDS = (
    "prior_preflight_fingerprint",
    "runtime_revalidation_receipt",
    "runtime_revalidation_fingerprint",
    "runtime_help_probes_reexecuted",
    "runtime_script_bytes_rehashed",
    "runtime_command_lineage_reconstructed",
    "runtime_revalidation_immediately_before_execution",
)


class HistoricalRefinementPreflightV32Error(RuntimeError):
    pass


def _validated_runtime_gate(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    verify_runtime: bool,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        return runtime_gate.validate_gate(
            receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            verify_runtime=verify_runtime,
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        raise HistoricalRefinementPreflightV32Error(
            f"readiness-v38 runtime revalidation is invalid: {error}"
        ) from error


def _base_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    prior_fingerprint = base.pop("prior_preflight_fingerprint", None)
    for field in _RUNTIME_FIELDS[1:]:
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = prior.SCHEMA
    base["fingerprint"] = prior_fingerprint
    return base


def _finalize(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    gate_receipt: Mapping[str, Any],
    base: Mapping[str, Any],
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    checked_gate = _validated_runtime_gate(
        plan,
        arm_receipt,
        gate_receipt,
        verify_runtime=True,
        timeout_seconds=timeout_seconds,
    )
    prior.validate_receipt(base)
    result = copy.deepcopy(dict(base))
    result.update(
        {
            "schema": SCHEMA,
            "prior_preflight_fingerprint": base["fingerprint"],
            "runtime_revalidation_receipt": copy.deepcopy(checked_gate),
            "runtime_revalidation_fingerprint": checked_gate["fingerprint"],
            "runtime_help_probes_reexecuted": True,
            "runtime_script_bytes_rehashed": True,
            "runtime_command_lineage_reconstructed": True,
            "runtime_revalidation_immediately_before_execution": True,
        }
    )
    result.pop("fingerprint", None)
    result["fingerprint"] = prior.prior.legacy._fingerprint(result)
    validate_receipt(
        result,
        verify_runtime=False,
        timeout_seconds=timeout_seconds,
    )
    return result


def execute_preflight(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    runtime_revalidation: Mapping[str, Any],
    ledger_path: Path,
    *,
    executor_runner: Callable[..., Mapping[str, Any]] | None = None,
    timeout_seconds: float = 10.0,
    **kwargs: Any,
) -> dict[str, Any]:
    _validated_runtime_gate(
        plan,
        arm_receipt,
        runtime_revalidation,
        verify_runtime=True,
        timeout_seconds=timeout_seconds,
    )
    runner = executor.execute_next if executor_runner is None else executor_runner
    base = prior.execute_preflight(
        plan,
        arm_receipt,
        ledger_path,
        executor_runner=runner,
        **kwargs,
    )
    return _finalize(
        plan,
        arm_receipt,
        runtime_revalidation,
        base,
        timeout_seconds=timeout_seconds,
    )


def validate_receipt(
    receipt: Mapping[str, Any],
    *,
    verify_runtime: bool = True,
    timeout_seconds: float = 10.0,
) -> None:
    value = copy.deepcopy(dict(receipt))
    observed = value.pop("fingerprint", None)
    if value.get("schema") != SCHEMA or observed != prior.prior.legacy._fingerprint(value):
        raise HistoricalRefinementPreflightV32Error(
            "preflight v32 schema or fingerprint mismatch"
        )
    mandatory = (
        "runtime_help_probes_reexecuted",
        "runtime_script_bytes_rehashed",
        "runtime_command_lineage_reconstructed",
        "runtime_revalidation_immediately_before_execution",
    )
    for field in mandatory:
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV32Error(
                f"mandatory runtime field mismatch: {field}"
            )
    plan = value.get("execution_plan_snapshot")
    arm_receipt = value.get("pipeline_arm_receipt")
    gate_receipt = value.get("runtime_revalidation_receipt")
    if not all(isinstance(item, Mapping) for item in (plan, arm_receipt, gate_receipt)):
        raise HistoricalRefinementPreflightV32Error(
            "preflight v32 requires plan, arm, and runtime-revalidation snapshots"
        )
    checked_gate = _validated_runtime_gate(
        plan,
        arm_receipt,
        gate_receipt,
        verify_runtime=verify_runtime,
        timeout_seconds=timeout_seconds,
    )
    if value.get("runtime_revalidation_fingerprint") != checked_gate.get("fingerprint"):
        raise HistoricalRefinementPreflightV32Error(
            "runtime revalidation fingerprint mismatch"
        )
    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("prior_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV32Error(
            "embedded preflight-v31 fingerprint mismatch"
        )
    prior.validate_receipt(base)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--arm-receipt", required=True)
    parser.add_argument("--runtime-revalidation", required=True)
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
    plan = prior.prior.legacy._load_json(Path(args.plan))
    arm_receipt = prior.prior.legacy._load_json(Path(args.arm_receipt))
    gate_receipt = prior.prior.legacy._load_json(Path(args.runtime_revalidation))
    receipt = execute_preflight(
        plan,
        arm_receipt,
        gate_receipt,
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
    prior.prior.legacy._atomic_json(Path(args.out), receipt)
    print(
        f"[ng_historical_refinement_preflight_v32] {receipt['status']} "
        f"executor_called={receipt['executor_called']} runtime_revalidated=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
