#!/usr/bin/env python3
"""Run readiness-v9 historical refinement behind live pre/post Git alignment.

Version 7 binds branch-guarded execution to the exact partition-to-replay byte
contract. Every plan and receipt must place that pre-outcome authorization after
exact replay and before replay-window authorization and causal refinement.
"""
from __future__ import annotations

import argparse
import copy
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor_v7 as executor
import ng_historical_refinement_preflight as legacy
import ng_historical_refinement_readiness_v9 as readiness

SCHEMA = "ng_historical_refinement_preflight.v7"
EXECUTOR_CONTRACT = "ng_historical_refinement_executor_v7"
READINESS_CONTRACT = readiness.SCHEMA
LEGACY_SCHEMA = legacy.SCHEMA


class HistoricalRefinementPreflightV7Error(RuntimeError):
    """Raised when branch-guarded execution is not bound to readiness v9."""


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
def _v9_context() -> Iterator[None]:
    old_executor = legacy.executor
    legacy.executor = executor
    try:
        yield
    finally:
        legacy.executor = old_executor


def _base_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    legacy_fingerprint = base.pop("legacy_preflight_fingerprint", None)
    for field in (
        "executor_contract",
        "readiness_contract",
        "readiness_stage_contract",
        "readiness_stage_contract_fingerprint",
        "execution_plan_snapshot",
        "execution_plan_v9_validated",
        "broad_corpus_scope_required",
        "broad_corpus_exact_overlap_required",
        "broad_corpus_exact_partition_required",
        "g15_exact_partition_replay_authorization_required",
        "g15_exact_partition_replay_authorization_pre_outcome",
        "g15_replay_window_blocked_until_partition_replay_authorized",
        "g15_exact_replay_window_authorization_required",
        "g15_exact_replay_window_authorization_pre_outcome",
        "g15_refinement_blocked_until_partition_and_window_authorized",
        "lock_first_g15_scoring_required",
        "counterfactual_g16_lineage_required",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = LEGACY_SCHEMA
    base["fingerprint"] = legacy_fingerprint
    return base


def _finalize(plan: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, Any]:
    with _v9_context():
        executor.validate_plan(plan)
        legacy.validate_receipt(base)
    result = copy.deepcopy(dict(base))
    result["schema"] = SCHEMA
    result["legacy_preflight_fingerprint"] = base["fingerprint"]
    result["executor_contract"] = EXECUTOR_CONTRACT
    result["readiness_contract"] = READINESS_CONTRACT
    result["readiness_stage_contract"] = copy.deepcopy(STAGE_CONTRACT)
    result["readiness_stage_contract_fingerprint"] = STAGE_CONTRACT_FINGERPRINT
    result["execution_plan_snapshot"] = copy.deepcopy(dict(plan))
    result["execution_plan_v9_validated"] = True
    result["broad_corpus_scope_required"] = True
    result["broad_corpus_exact_overlap_required"] = True
    result["broad_corpus_exact_partition_required"] = True
    result["g15_exact_partition_replay_authorization_required"] = True
    result["g15_exact_partition_replay_authorization_pre_outcome"] = True
    result["g15_replay_window_blocked_until_partition_replay_authorized"] = True
    result["g15_exact_replay_window_authorization_required"] = True
    result["g15_exact_replay_window_authorization_pre_outcome"] = True
    result["g15_refinement_blocked_until_partition_and_window_authorized"] = True
    result["lock_first_g15_scoring_required"] = True
    result["counterfactual_g16_lineage_required"] = True
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
    """Execute one readiness-v9 stage with branch alignment before and after."""
    executor.validate_plan(plan)
    runner = executor.run_next if executor_runner is None else executor_runner
    with _v9_context():
        base = legacy.execute_preflight(
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
        raise HistoricalRefinementPreflightV7Error("preflight v7 schema or fingerprint mismatch")
    if value.get("executor_contract") != EXECUTOR_CONTRACT:
        raise HistoricalRefinementPreflightV7Error("preflight v7 executor contract mismatch")
    if value.get("readiness_contract") != READINESS_CONTRACT:
        raise HistoricalRefinementPreflightV7Error("preflight v7 readiness contract mismatch")
    if value.get("readiness_stage_contract") != STAGE_CONTRACT:
        raise HistoricalRefinementPreflightV7Error("preflight v7 stage contract mismatch")
    if value.get("readiness_stage_contract_fingerprint") != STAGE_CONTRACT_FINGERPRINT:
        raise HistoricalRefinementPreflightV7Error("preflight v7 stage contract fingerprint mismatch")
    if value.get("execution_plan_v9_validated") is not True:
        raise HistoricalRefinementPreflightV7Error("preflight v7 must record v9 plan validation")
    for field, message in (
        ("broad_corpus_scope_required", "broad corpus scope"),
        ("broad_corpus_exact_overlap_required", "broad corpus exact overlap"),
        ("broad_corpus_exact_partition_required", "broad corpus exact source partition"),
        ("g15_exact_partition_replay_authorization_required", "G15 exact partition-to-replay authorization"),
        ("g15_exact_partition_replay_authorization_pre_outcome", "pre-outcome partition-to-replay authorization"),
        ("g15_replay_window_blocked_until_partition_replay_authorized", "partition-to-window wall"),
        ("g15_exact_replay_window_authorization_required", "G15 exact replay-window authorization"),
        ("g15_exact_replay_window_authorization_pre_outcome", "pre-outcome replay-window authorization"),
        ("g15_refinement_blocked_until_partition_and_window_authorized", "G15 refinement authorization wall"),
        ("lock_first_g15_scoring_required", "G15 lock-first scoring"),
        ("counterfactual_g16_lineage_required", "G16 counterfactual lineage"),
    ):
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV7Error(f"{message} must remain mandatory")

    plan = value.get("execution_plan_snapshot")
    if not isinstance(plan, Mapping):
        raise HistoricalRefinementPreflightV7Error("preflight v7 requires the exact plan snapshot")
    with _v9_context():
        executor.validate_plan(plan)
    if value.get("plan_fingerprint") != plan.get("fingerprint"):
        raise HistoricalRefinementPreflightV7Error(
            "receipt plan fingerprint does not match embedded v9 plan"
        )
    stage_keys = [
        row.get("key")
        for row in plan.get("stages") or []
        if isinstance(row, Mapping)
    ]
    if stage_keys != STAGE_ORDER:
        raise HistoricalRefinementPreflightV7Error(
            "embedded plan does not use readiness-v9 stage order"
        )
    try:
        broad_index = stage_keys.index("broad_corpus_scope")
        overlap_index = stage_keys.index("broad_corpus_exact_overlap")
        partition_index = stage_keys.index("broad_corpus_exact_partition")
        replay_index = stage_keys.index("g15_exact_replay")
        partition_replay_index = stage_keys.index("g15_exact_partition_replay_authorization")
        window_index = stage_keys.index("g15_exact_replay_window_authorization")
        refine_index = stage_keys.index("g15_exact_refinement")
    except ValueError as error:
        raise HistoricalRefinementPreflightV7Error(
            "required broad-corpus, replay, partition-binding, window, or refinement stage is missing"
        ) from error
    if not (
        broad_index
        < overlap_index
        < partition_index
        < replay_index
        < partition_replay_index
        < window_index
        < refine_index
    ):
        raise HistoricalRefinementPreflightV7Error(
            "broad verification, replay, byte binding, window authorization, and refinement are out of order"
        )
    rows = {str(row.get("key")): row for row in plan.get("stages") or []}
    for key in (
        "broad_corpus_scope",
        "broad_corpus_exact_overlap",
        "broad_corpus_exact_partition",
        "g15_exact_replay",
        "g15_exact_partition_replay_authorization",
        "g15_exact_replay_window_authorization",
        "g15_exact_refinement",
    ):
        if rows[key].get("requires_fixed_outcomes") is not False:
            raise HistoricalRefinementPreflightV7Error(f"{key} must remain pre-outcome")

    executor_result = value.get("executor_result")
    if isinstance(executor_result, Mapping):
        selected_stage = executor_result.get("stage")
        if selected_stage is not None and selected_stage not in STAGE_ORDER:
            raise HistoricalRefinementPreflightV7Error(
                "executor selected a stage outside readiness v9"
            )

    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("legacy_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV7Error(
            "embedded legacy preflight fingerprint mismatch"
        )
    with _v9_context():
        legacy.validate_receipt(base)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan")
    parser.add_argument("--ledger")
    parser.add_argument("--out")
    parser.add_argument("--readiness-out")
    parser.add_argument("--expected-branch", default=branch_alignment.DEFAULT_BRANCH)
    parser.add_argument("--expected-repository", default=branch_alignment.DEFAULT_REPOSITORY)
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
    if receipt["status"] not in {"PREFLIGHT_PASSED", "PREFLIGHT_PASSED_WITH_STAND_DOWNS"}:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
