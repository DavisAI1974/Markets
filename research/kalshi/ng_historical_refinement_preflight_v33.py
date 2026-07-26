#!/usr/bin/env python3
"""Run readiness-v38 preflight only after every configured stage script is rehashed.

Preflight v32 revalidates the v31 command contract and G16 extension scripts. This wrapper
adds the historical-corpus and G15 prefix scripts and revalidates the complete code map at
the exact executor delegation point. Only the first blocking stage can run; fixed G16
scoring/publication remains disabled by the armed plan.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v34 as executor
import ng_historical_refinement_preflight_v32 as prior
import ng_historical_refinement_readiness as legacy_readiness
import ng_v38_all_stage_runtime_revalidation_gate as all_stage_gate

SCHEMA = "ng_historical_refinement_preflight.v33"
EXECUTOR_CONTRACT = prior.EXECUTOR_CONTRACT
READINESS_CONTRACT = prior.READINESS_CONTRACT
STAGE_CONTRACT = prior.STAGE_CONTRACT
STAGE_CONTRACT_FINGERPRINT = prior.STAGE_CONTRACT_FINGERPRINT
_NEW_FIELDS = (
    "prior_preflight_fingerprint",
    "all_stage_runtime_revalidation_receipt",
    "all_stage_runtime_revalidation_fingerprint",
    "all_configured_stage_scripts_rehashed",
    "historical_and_g15_prefix_scripts_rehashed",
    "runtime_revalidation_at_executor_delegation",
)


class HistoricalRefinementPreflightV33Error(RuntimeError):
    pass


def _validated_all_stage_gate(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    verify_runtime: bool,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        return all_stage_gate.validate_gate(
            receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            verify_runtime=verify_runtime,
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        raise HistoricalRefinementPreflightV33Error(
            f"all-stage runtime revalidation is invalid: {error}"
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
    gate_receipt: Mapping[str, Any],
    base: Mapping[str, Any],
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    checked_gate = _validated_all_stage_gate(
        plan,
        arm_receipt,
        gate_receipt,
        verify_runtime=False,
        timeout_seconds=timeout_seconds,
    )
    prior.validate_receipt(base, verify_runtime=False, timeout_seconds=timeout_seconds)
    result = copy.deepcopy(dict(base))
    result.update(
        {
            "schema": SCHEMA,
            "prior_preflight_fingerprint": base["fingerprint"],
            "all_stage_runtime_revalidation_receipt": copy.deepcopy(checked_gate),
            "all_stage_runtime_revalidation_fingerprint": checked_gate["fingerprint"],
            "all_configured_stage_scripts_rehashed": True,
            "historical_and_g15_prefix_scripts_rehashed": True,
            "runtime_revalidation_at_executor_delegation": True,
        }
    )
    result.pop("fingerprint", None)
    result["fingerprint"] = legacy_readiness._fingerprint(result)
    validate_receipt(result, verify_runtime=False, timeout_seconds=timeout_seconds)
    return result


def execute_preflight(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    all_stage_runtime_revalidation: Mapping[str, Any],
    ledger_path: Path,
    *,
    executor_runner: Callable[..., Mapping[str, Any]] | None = None,
    timeout_seconds: float = 10.0,
    **kwargs: Any,
) -> dict[str, Any]:
    checked_gate = _validated_all_stage_gate(
        plan,
        arm_receipt,
        all_stage_runtime_revalidation,
        verify_runtime=True,
        timeout_seconds=timeout_seconds,
    )
    embedded_prior = checked_gate.get("prior_runtime_revalidation_receipt")
    if not isinstance(embedded_prior, Mapping):
        raise HistoricalRefinementPreflightV33Error(
            "all-stage runtime receipt lacks the v32-compatible prior receipt"
        )
    base_runner = executor.execute_next if executor_runner is None else executor_runner

    def guarded_runner(*args: Any, **runner_kwargs: Any) -> Mapping[str, Any]:
        _validated_all_stage_gate(
            plan,
            arm_receipt,
            all_stage_runtime_revalidation,
            verify_runtime=True,
            timeout_seconds=timeout_seconds,
        )
        return base_runner(*args, **runner_kwargs)

    base = prior.execute_preflight(
        plan,
        arm_receipt,
        embedded_prior,
        ledger_path,
        executor_runner=guarded_runner,
        timeout_seconds=timeout_seconds,
        **kwargs,
    )
    return _finalize(
        plan,
        arm_receipt,
        checked_gate,
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
    if value.get("schema") != SCHEMA or observed != legacy_readiness._fingerprint(value):
        raise HistoricalRefinementPreflightV33Error(
            "preflight v33 schema or fingerprint mismatch"
        )
    for field in (
        "all_configured_stage_scripts_rehashed",
        "historical_and_g15_prefix_scripts_rehashed",
        "runtime_revalidation_at_executor_delegation",
    ):
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV33Error(f"mandatory field mismatch: {field}")
    plan = value.get("execution_plan_snapshot")
    arm_receipt = value.get("pipeline_arm_receipt")
    gate_receipt = value.get("all_stage_runtime_revalidation_receipt")
    if not all(isinstance(item, Mapping) for item in (plan, arm_receipt, gate_receipt)):
        raise HistoricalRefinementPreflightV33Error(
            "preflight v33 requires plan, arm, and all-stage runtime snapshots"
        )
    checked_gate = _validated_all_stage_gate(
        plan,
        arm_receipt,
        gate_receipt,
        verify_runtime=verify_runtime,
        timeout_seconds=timeout_seconds,
    )
    if value.get("all_stage_runtime_revalidation_fingerprint") != checked_gate.get(
        "fingerprint"
    ):
        raise HistoricalRefinementPreflightV33Error(
            "all-stage runtime revalidation fingerprint mismatch"
        )
    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("prior_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV33Error(
            "embedded preflight-v32 fingerprint mismatch"
        )
    prior.validate_receipt(base, verify_runtime=False, timeout_seconds=timeout_seconds)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--arm-receipt", required=True)
    parser.add_argument("--all-stage-runtime-revalidation", required=True)
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
    gate_receipt = legacy_executor._load_json(Path(args.all_stage_runtime_revalidation))
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
    legacy_executor._atomic_json(Path(args.out), receipt)
    print(
        f"[ng_historical_refinement_preflight_v33] {receipt['status']} "
        f"executor_called={receipt['executor_called']} all_stage_runtime_revalidated=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
