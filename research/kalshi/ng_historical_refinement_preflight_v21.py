#!/usr/bin/env python3
"""Bind branch-guarded execution to expected-day historical readiness v25."""
from __future__ import annotations

import argparse
import copy
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor_v21 as executor
import ng_historical_refinement_preflight as legacy
import ng_historical_refinement_preflight_v20 as v20
import ng_historical_refinement_readiness_v25 as readiness

SCHEMA = "ng_historical_refinement_preflight.v21"
EXECUTOR_CONTRACT = "ng_historical_refinement_executor_v21"
READINESS_CONTRACT = readiness.SCHEMA
STAGE_CONTRACT = [
    {
        "key": spec.key,
        "filename": spec.filename,
        "schema": spec.schema,
        "pre_outcome": bool(spec.pre_outcome),
    }
    for spec in readiness.STAGES
]
STAGE_ORDER = [row["key"] for row in STAGE_CONTRACT]
STAGE_CONTRACT_FINGERPRINT = legacy._fingerprint(STAGE_CONTRACT)


class HistoricalRefinementPreflightV21Error(RuntimeError):
    pass


@contextmanager
def _v25_context() -> Iterator[None]:
    saved = (
        v20.executor,
        v20.readiness,
        v20.EXECUTOR_CONTRACT,
        v20.READINESS_CONTRACT,
        v20.STAGE_CONTRACT,
        v20.STAGE_ORDER,
        v20.STAGE_CONTRACT_FINGERPRINT,
    )
    v20.executor = executor
    v20.readiness = readiness
    v20.EXECUTOR_CONTRACT = EXECUTOR_CONTRACT
    v20.READINESS_CONTRACT = READINESS_CONTRACT
    v20.STAGE_CONTRACT = STAGE_CONTRACT
    v20.STAGE_ORDER = STAGE_ORDER
    v20.STAGE_CONTRACT_FINGERPRINT = STAGE_CONTRACT_FINGERPRINT
    try:
        yield
    finally:
        (
            v20.executor,
            v20.readiness,
            v20.EXECUTOR_CONTRACT,
            v20.READINESS_CONTRACT,
            v20.STAGE_CONTRACT,
            v20.STAGE_ORDER,
            v20.STAGE_CONTRACT_FINGERPRINT,
        ) = saved


def _base_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    prior = base.pop("v20_preflight_fingerprint", None)
    for field in (
        "execution_plan_v25_validated",
        "expected_day_contract_required",
        "complete_calendar_partition_bound",
        "expected_day_contract_pre_outcome",
        "expected_day_contract_precedes_s3_resolution",
        "operator_shortened_expected_days_rejected",
        "non_saturday_exclusions_evidence_bound",
        "target_replay_days_may_not_be_excluded",
        "s3_resolution_bound_to_expected_day_contract_v25",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = v20.SCHEMA
    base["fingerprint"] = prior
    return base


def _check_plan(plan: Mapping[str, Any]) -> None:
    executor.validate_plan(plan)
    rows = [row for row in plan.get("stages") or [] if isinstance(row, Mapping)]
    keys = [str(row.get("key")) for row in rows]
    if keys != STAGE_ORDER:
        raise HistoricalRefinementPreflightV21Error(
            "embedded plan does not use readiness-v25 stage order"
        )
    required = (
        "corpus_expected_day_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
        "corpus_coverage",
        "corpus_definition_byte_binding",
        "target_slice_coverage",
        "target_slice_broad_lineage",
        "target_slice_derivation",
        "basis_inventory_regeneration",
        "broad_corpus_scope",
        "g15_exact_replay",
    )
    try:
        positions = {key: keys.index(key) for key in required}
    except ValueError as error:
        raise HistoricalRefinementPreflightV21Error(
            "required expected-day corpus stage is missing"
        ) from error
    if not (
        positions["corpus_expected_day_contract"]
        < positions["corpus_s3_latest_version_resolution"]
        < positions["corpus_s3_inventory_capture"]
        < positions["corpus_s3_materialization"]
        < positions["corpus_coverage"]
        < positions["corpus_definition_byte_binding"]
        < positions["target_slice_coverage"]
        < positions["target_slice_broad_lineage"]
        < positions["target_slice_derivation"]
        < positions["basis_inventory_regeneration"]
        < positions["broad_corpus_scope"]
        < positions["g15_exact_replay"]
    ):
        raise HistoricalRefinementPreflightV21Error(
            "expected-day contract is not ordered before S3 and G15 replay"
        )
    by_key = {str(row.get("key")): row for row in rows}
    first = by_key["corpus_expected_day_contract"]
    second = by_key["corpus_s3_latest_version_resolution"]
    third = by_key["corpus_s3_inventory_capture"]
    if first.get("expected_output") != "ng_corpus_expected_day_contract_attestation.json":
        raise HistoricalRefinementPreflightV21Error(
            "expected-day artifact may not be substituted"
        )
    if first.get("suggested_entrypoint") != [
        "python",
        "ng_corpus_expected_day_contract.py",
        "build",
    ]:
        raise HistoricalRefinementPreflightV21Error(
            "expected-day entrypoint was substituted"
        )
    if second.get("expected_output") != (
        "ng_corpus_s3_paginated_latest_version_resolution_attestation.json"
    ):
        raise HistoricalRefinementPreflightV21Error(
            "legacy non-paginated S3 resolution artifact may not enter preflight v21"
        )
    if third.get("expected_output") != (
        "ng_corpus_s3_paginated_inventory_capture_attestation.json"
    ):
        raise HistoricalRefinementPreflightV21Error(
            "legacy single-page S3 inventory artifact may not enter preflight v21"
        )
    for key in required[:-1]:
        if by_key[key].get("requires_fixed_outcomes") is not False:
            raise HistoricalRefinementPreflightV21Error(f"{key} must remain pre-outcome")


def _finalize(plan: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, Any]:
    _check_plan(plan)
    with _v25_context():
        v20.validate_receipt(base)
    result = copy.deepcopy(dict(base))
    result["schema"] = SCHEMA
    result["v20_preflight_fingerprint"] = base["fingerprint"]
    result["executor_contract"] = EXECUTOR_CONTRACT
    result["readiness_contract"] = READINESS_CONTRACT
    result["readiness_stage_contract"] = copy.deepcopy(STAGE_CONTRACT)
    result["readiness_stage_contract_fingerprint"] = STAGE_CONTRACT_FINGERPRINT
    result["execution_plan_snapshot"] = copy.deepcopy(dict(plan))
    result["execution_plan_v25_validated"] = True
    result["expected_day_contract_required"] = True
    result["complete_calendar_partition_bound"] = True
    result["expected_day_contract_pre_outcome"] = True
    result["expected_day_contract_precedes_s3_resolution"] = True
    result["operator_shortened_expected_days_rejected"] = True
    result["non_saturday_exclusions_evidence_bound"] = True
    result["target_replay_days_may_not_be_excluded"] = True
    result["s3_resolution_bound_to_expected_day_contract_v25"] = True
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
    _check_plan(plan)
    runner = executor.run_next if executor_runner is None else executor_runner
    with _v25_context():
        base = v20.execute_preflight(
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
        raise HistoricalRefinementPreflightV21Error(
            "preflight v21 schema or fingerprint mismatch"
        )
    if value.get("executor_contract") != EXECUTOR_CONTRACT:
        raise HistoricalRefinementPreflightV21Error("executor contract mismatch")
    if value.get("readiness_contract") != READINESS_CONTRACT:
        raise HistoricalRefinementPreflightV21Error("readiness contract mismatch")
    if value.get("readiness_stage_contract") != STAGE_CONTRACT:
        raise HistoricalRefinementPreflightV21Error("stage contract mismatch")
    if value.get("readiness_stage_contract_fingerprint") != STAGE_CONTRACT_FINGERPRINT:
        raise HistoricalRefinementPreflightV21Error("stage fingerprint mismatch")
    for field in (
        "execution_plan_v25_validated",
        "expected_day_contract_required",
        "complete_calendar_partition_bound",
        "expected_day_contract_pre_outcome",
        "expected_day_contract_precedes_s3_resolution",
        "operator_shortened_expected_days_rejected",
        "non_saturday_exclusions_evidence_bound",
        "target_replay_days_may_not_be_excluded",
        "s3_resolution_bound_to_expected_day_contract_v25",
    ):
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV21Error(
                f"mandatory field mismatch: {field}"
            )
    plan = value.get("execution_plan_snapshot")
    if not isinstance(plan, Mapping):
        raise HistoricalRefinementPreflightV21Error("exact plan snapshot is required")
    _check_plan(plan)
    if value.get("plan_fingerprint") != plan.get("fingerprint"):
        raise HistoricalRefinementPreflightV21Error("plan fingerprint mismatch")
    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("v20_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV21Error(
            "embedded v20 preflight fingerprint mismatch"
        )
    with _v25_context():
        v20.validate_receipt(base)


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
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "executor_status": (receipt.get("executor_result") or {}).get("status"),
                "executor_stage": (receipt.get("executor_result") or {}).get("stage"),
                "readiness_contract": receipt["readiness_contract"],
                "fingerprint": receipt["fingerprint"],
                "blockers": receipt.get("blockers") or [],
                "stand_downs": receipt.get("stand_downs") or [],
            },
            sort_keys=True,
        )
    )
    return 0 if receipt["status"] in {
        "PREFLIGHT_PASSED",
        "PREFLIGHT_PASSED_WITH_STAND_DOWNS",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
