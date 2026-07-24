#!/usr/bin/env python3
"""Run readiness-v5 historical refinement behind live pre/post Git alignment.

Version 3 binds the branch-guarded executor to the broad-corpus-first v5 stage contract.
The exact execution plan is validated and embedded in the receipt; Git branch, remote,
HEAD, and worktree alignment are checked on both sides by the established preflight.
No G15 stage can run through this wrapper unless the mandatory broad-corpus gate exists
in the plan before exact replay.
"""
from __future__ import annotations

import argparse
import copy
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor_v3 as executor
import ng_historical_refinement_preflight as legacy
import ng_historical_refinement_readiness_v5 as readiness

SCHEMA = "ng_historical_refinement_preflight.v3"
EXECUTOR_CONTRACT = "ng_historical_refinement_executor_v3"
READINESS_CONTRACT = readiness.SCHEMA
LEGACY_SCHEMA = legacy.SCHEMA


class HistoricalRefinementPreflightV3Error(RuntimeError):
    """Raised when branch-guarded execution is not bound to readiness v5."""


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
def _v5_context() -> Iterator[None]:
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
        "execution_plan_v5_validated",
        "broad_corpus_scope_required",
        "lock_first_g15_scoring_required",
        "counterfactual_g16_lineage_required",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = LEGACY_SCHEMA
    base["fingerprint"] = legacy_fingerprint
    return base


def _finalize(plan: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, Any]:
    with _v5_context():
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
    result["execution_plan_v5_validated"] = True
    result["broad_corpus_scope_required"] = True
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
    """Execute one readiness-v5 stage with branch alignment before and after."""
    executor.validate_plan(plan)
    runner = executor.run_next if executor_runner is None else executor_runner
    with _v5_context():
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
        raise HistoricalRefinementPreflightV3Error("preflight v3 schema or fingerprint mismatch")
    if value.get("executor_contract") != EXECUTOR_CONTRACT:
        raise HistoricalRefinementPreflightV3Error("preflight v3 executor contract mismatch")
    if value.get("readiness_contract") != READINESS_CONTRACT:
        raise HistoricalRefinementPreflightV3Error("preflight v3 readiness contract mismatch")
    if value.get("readiness_stage_contract") != STAGE_CONTRACT:
        raise HistoricalRefinementPreflightV3Error("preflight v3 stage contract mismatch")
    if value.get("readiness_stage_contract_fingerprint") != STAGE_CONTRACT_FINGERPRINT:
        raise HistoricalRefinementPreflightV3Error("preflight v3 stage contract fingerprint mismatch")
    if value.get("execution_plan_v5_validated") is not True:
        raise HistoricalRefinementPreflightV3Error("preflight v3 must record v5 plan validation")
    if value.get("broad_corpus_scope_required") is not True:
        raise HistoricalRefinementPreflightV3Error("broad corpus scope must remain mandatory")
    if value.get("lock_first_g15_scoring_required") is not True:
        raise HistoricalRefinementPreflightV3Error("G15 lock-first scoring must remain mandatory")
    if value.get("counterfactual_g16_lineage_required") is not True:
        raise HistoricalRefinementPreflightV3Error("G16 counterfactual lineage must remain mandatory")

    plan = value.get("execution_plan_snapshot")
    if not isinstance(plan, Mapping):
        raise HistoricalRefinementPreflightV3Error("preflight v3 requires the exact execution plan snapshot")
    with _v5_context():
        executor.validate_plan(plan)
    if value.get("plan_fingerprint") != plan.get("fingerprint"):
        raise HistoricalRefinementPreflightV3Error("receipt plan fingerprint does not match embedded v5 plan")
    stage_keys = [row.get("key") for row in plan.get("stages") or [] if isinstance(row, Mapping)]
    if stage_keys != STAGE_ORDER:
        raise HistoricalRefinementPreflightV3Error("embedded plan does not use readiness-v5 stage order")
    try:
        broad_index = stage_keys.index("broad_corpus_scope")
        replay_index = stage_keys.index("g15_exact_replay")
    except ValueError as error:
        raise HistoricalRefinementPreflightV3Error("broad corpus or G15 replay stage is missing") from error
    if broad_index >= replay_index:
        raise HistoricalRefinementPreflightV3Error("broad corpus scope must precede G15 replay")
    broad_row = next(row for row in plan["stages"] if row.get("key") == "broad_corpus_scope")
    if broad_row.get("requires_fixed_outcomes") is not False:
        raise HistoricalRefinementPreflightV3Error("broad corpus verification must remain pre-outcome")

    executor_result = value.get("executor_result")
    if isinstance(executor_result, Mapping):
        selected_stage = executor_result.get("stage")
        if selected_stage is not None and selected_stage not in STAGE_ORDER:
            raise HistoricalRefinementPreflightV3Error("executor selected a stage outside readiness v5")

    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("legacy_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV3Error("embedded legacy preflight fingerprint mismatch")
    with _v5_context():
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
    return 0 if summary["executor_status"] in legacy.EXECUTOR_OK_STATUSES else 2


if __name__ == "__main__":
    raise SystemExit(main())
