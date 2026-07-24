#!/usr/bin/env python3
"""Run readiness-v10 historical refinement behind live pre/post Git alignment.

Version 8 binds branch-guarded execution to the exact G16 partition-to-replay
byte and event-window authorization. The pre-cutoff G16 causal path cannot run
until every prepared replay lane and emitted feature-state span is authorized
against the verified broad-corpus partition.
"""
from __future__ import annotations

import argparse
import copy
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor_v8 as executor
import ng_historical_refinement_preflight as legacy
import ng_historical_refinement_preflight_v7 as v7
import ng_historical_refinement_readiness_v10 as readiness

SCHEMA = "ng_historical_refinement_preflight.v8"
EXECUTOR_CONTRACT = "ng_historical_refinement_executor_v8"
READINESS_CONTRACT = readiness.SCHEMA
V7_SCHEMA = v7.SCHEMA


class HistoricalRefinementPreflightV8Error(RuntimeError):
    """Raised when branch-guarded execution is not bound to readiness v10."""


def _stage_contract() -> list[dict[str, Any]]:
    return [
        {
            "key": spec.key,
            "filename": spec.filename,
            "schema": spec.schema,
            "pre_outcome": bool(spec.pre_outcome),
        }
        for spec in readiness.STAGES
    ]


STAGE_CONTRACT = _stage_contract()
STAGE_ORDER = [row["key"] for row in STAGE_CONTRACT]
STAGE_CONTRACT_FINGERPRINT = legacy._fingerprint(STAGE_CONTRACT)


@contextmanager
def _v10_context() -> Iterator[None]:
    saved = (
        v7.executor,
        v7.readiness,
        v7.EXECUTOR_CONTRACT,
        v7.READINESS_CONTRACT,
        v7.STAGE_CONTRACT,
        v7.STAGE_ORDER,
        v7.STAGE_CONTRACT_FINGERPRINT,
    )
    v7.executor = executor
    v7.readiness = readiness
    v7.EXECUTOR_CONTRACT = EXECUTOR_CONTRACT
    v7.READINESS_CONTRACT = READINESS_CONTRACT
    v7.STAGE_CONTRACT = STAGE_CONTRACT
    v7.STAGE_ORDER = STAGE_ORDER
    v7.STAGE_CONTRACT_FINGERPRINT = STAGE_CONTRACT_FINGERPRINT
    try:
        yield
    finally:
        (
            v7.executor,
            v7.readiness,
            v7.EXECUTOR_CONTRACT,
            v7.READINESS_CONTRACT,
            v7.STAGE_CONTRACT,
            v7.STAGE_ORDER,
            v7.STAGE_CONTRACT_FINGERPRINT,
        ) = saved


def _base_v7_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    v7_fingerprint = base.pop("v7_preflight_fingerprint", None)
    for field in (
        "execution_plan_v10_validated",
        "g16_exact_partition_replay_authorization_required",
        "g16_exact_partition_replay_authorization_pre_outcome",
        "g16_replay_bytes_bound_to_exact_partition",
        "g16_replay_state_windows_authorized_before_causal",
        "g16_causal_blocked_until_partition_replay_authorized",
        "g16_prepared_causal_authorization_blocked_until_partition_replay_authorized",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = V7_SCHEMA
    base["fingerprint"] = v7_fingerprint
    return base


def _finalize(plan: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, Any]:
    with _v10_context():
        executor.validate_plan(plan)
        v7.validate_receipt(base)
    result = copy.deepcopy(dict(base))
    result["schema"] = SCHEMA
    result["v7_preflight_fingerprint"] = base["fingerprint"]
    result["executor_contract"] = EXECUTOR_CONTRACT
    result["readiness_contract"] = READINESS_CONTRACT
    result["readiness_stage_contract"] = copy.deepcopy(STAGE_CONTRACT)
    result["readiness_stage_contract_fingerprint"] = STAGE_CONTRACT_FINGERPRINT
    result["execution_plan_snapshot"] = copy.deepcopy(dict(plan))
    result["execution_plan_v10_validated"] = True
    result["g16_exact_partition_replay_authorization_required"] = True
    result["g16_exact_partition_replay_authorization_pre_outcome"] = True
    result["g16_replay_bytes_bound_to_exact_partition"] = True
    result["g16_replay_state_windows_authorized_before_causal"] = True
    result["g16_causal_blocked_until_partition_replay_authorized"] = True
    result[
        "g16_prepared_causal_authorization_blocked_until_partition_replay_authorized"
    ] = True
    result.pop("fingerprint", None)
    result["fingerprint"] = legacy._fingerprint(result)
    validate_receipt(result)
    return result


def execute_preflight(
    plan: Mapping[str, Any],
    ledger_path: Path,
    *,
    executor_runner: Callable[..., Mapping[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Execute one readiness-v10 stage with branch alignment before and after."""
    executor.validate_plan(plan)
    runner = executor.run_next if executor_runner is None else executor_runner
    with _v10_context():
        base = v7.execute_preflight(
            plan,
            ledger_path,
            executor_runner=runner,
            **kwargs,
        )
    return _finalize(plan, base)


def validate_receipt(receipt: Mapping[str, Any]) -> None:
    value = copy.deepcopy(dict(receipt))
    observed = value.pop("fingerprint", None)
    if value.get("schema") != SCHEMA or observed != legacy._fingerprint(value):
        raise HistoricalRefinementPreflightV8Error(
            "preflight v8 schema or fingerprint mismatch"
        )
    if value.get("executor_contract") != EXECUTOR_CONTRACT:
        raise HistoricalRefinementPreflightV8Error(
            "preflight v8 executor contract mismatch"
        )
    if value.get("readiness_contract") != READINESS_CONTRACT:
        raise HistoricalRefinementPreflightV8Error(
            "preflight v8 readiness contract mismatch"
        )
    if value.get("readiness_stage_contract") != STAGE_CONTRACT:
        raise HistoricalRefinementPreflightV8Error(
            "preflight v8 stage contract mismatch"
        )
    if (
        value.get("readiness_stage_contract_fingerprint")
        != STAGE_CONTRACT_FINGERPRINT
    ):
        raise HistoricalRefinementPreflightV8Error(
            "preflight v8 stage contract fingerprint mismatch"
        )
    if value.get("execution_plan_v10_validated") is not True:
        raise HistoricalRefinementPreflightV8Error(
            "preflight v8 must record v10 plan validation"
        )
    for field, message in (
        (
            "g16_exact_partition_replay_authorization_required",
            "G16 exact partition/replay-window authorization",
        ),
        (
            "g16_exact_partition_replay_authorization_pre_outcome",
            "pre-outcome G16 partition/replay-window authorization",
        ),
        (
            "g16_replay_bytes_bound_to_exact_partition",
            "G16 replay-byte binding",
        ),
        (
            "g16_replay_state_windows_authorized_before_causal",
            "G16 replay-state window wall",
        ),
        (
            "g16_causal_blocked_until_partition_replay_authorized",
            "G16 causal authorization wall",
        ),
        (
            "g16_prepared_causal_authorization_blocked_until_partition_replay_authorized",
            "G16 prepared-causal authorization wall",
        ),
    ):
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV8Error(
                f"{message} must remain mandatory"
            )

    plan = value.get("execution_plan_snapshot")
    if not isinstance(plan, Mapping):
        raise HistoricalRefinementPreflightV8Error(
            "preflight v8 requires the exact plan snapshot"
        )
    executor.validate_plan(plan)
    if value.get("plan_fingerprint") != plan.get("fingerprint"):
        raise HistoricalRefinementPreflightV8Error(
            "receipt plan fingerprint does not match embedded v10 plan"
        )
    stage_keys = [
        row.get("key")
        for row in plan.get("stages") or []
        if isinstance(row, Mapping)
    ]
    if stage_keys != STAGE_ORDER:
        raise HistoricalRefinementPreflightV8Error(
            "embedded plan does not use readiness-v10 stage order"
        )
    try:
        prepared_index = stage_keys.index("g16_prepared_replay")
        binding_index = stage_keys.index(
            "g16_exact_partition_replay_authorization"
        )
        causal_index = stage_keys.index("g16_exact_causal")
        prepared_causal_index = stage_keys.index(
            "g16_prepared_causal_authorization"
        )
    except ValueError as error:
        raise HistoricalRefinementPreflightV8Error(
            "required G16 prepared replay, partition binding, causal, or prepared-causal stage is missing"
        ) from error
    if not (
        prepared_index
        < binding_index
        < causal_index
        < prepared_causal_index
    ):
        raise HistoricalRefinementPreflightV8Error(
            "G16 prepared replay, exact partition binding, causal, and prepared-causal stages are out of order"
        )
    rows = {str(row.get("key")): row for row in plan.get("stages") or []}
    for key in (
        "g16_prepared_replay",
        "g16_exact_partition_replay_authorization",
        "g16_exact_causal",
        "g16_prepared_causal_authorization",
    ):
        if rows[key].get("requires_fixed_outcomes") is not False:
            raise HistoricalRefinementPreflightV8Error(
                f"{key} must remain pre-outcome"
            )

    executor_result = value.get("executor_result")
    if isinstance(executor_result, Mapping):
        selected_stage = executor_result.get("stage")
        if selected_stage is not None and selected_stage not in STAGE_ORDER:
            raise HistoricalRefinementPreflightV8Error(
                "executor selected a stage outside readiness v10"
            )

    base = _base_v7_receipt(receipt)
    if base.get("fingerprint") != value.get("v7_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV8Error(
            "embedded v7 preflight fingerprint mismatch"
        )
    with _v10_context():
        v7.validate_receipt(base)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan")
    parser.add_argument("--ledger")
    parser.add_argument("--out")
    parser.add_argument("--readiness-out")
    parser.add_argument("--expected-branch", default=branch_alignment.DEFAULT_BRANCH)
    parser.add_argument(
        "--expected-repository", default=branch_alignment.DEFAULT_REPOSITORY
    )
    parser.add_argument("--remote", default=branch_alignment.DEFAULT_REMOTE)
    parser.add_argument("--allow-dirty-prefix", action="append", default=[])
    parser.add_argument("--allow-local-ahead", action="store_true")
    parser.add_argument("--allow-missing-remote-ref", action="store_true")
    parser.add_argument("--allow-fixed-outcomes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.plan or not args.ledger or not args.out:
        parser.error("--plan, --ledger, and --out are required")
    plan = legacy._load_json(Path(args.plan))
    receipt = execute_preflight(
        plan,
        Path(args.ledger),
        expected_branch=args.expected_branch,
        expected_repository=args.expected_repository,
        remote=args.remote,
        allowed_dirty_prefixes=args.allow_dirty_prefix,
        require_remote_match=not args.allow_missing_remote_ref,
        allow_local_ahead=args.allow_local_ahead,
        allow_fixed_outcomes=args.allow_fixed_outcomes,
        dry_run=args.dry_run,
        readiness_out=Path(args.readiness_out) if args.readiness_out else None,
    )
    legacy._atomic_json(Path(args.out), receipt)
    summary = {
        "status": receipt["status"],
        "executor_status": (receipt.get("executor_result") or {}).get("status"),
        "executor_stage": (receipt.get("executor_result") or {}).get("stage"),
        "readiness_contract": receipt["readiness_contract"],
        "fingerprint": receipt["fingerprint"],
        "blockers": receipt.get("blockers") or [],
        "stand_downs": receipt.get("stand_downs") or [],
    }
    print(json.dumps(summary, sort_keys=True))
    if receipt["status"] not in {
        "PREFLIGHT_PASSED",
        "PREFLIGHT_PASSED_WITH_STAND_DOWNS",
    }:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
