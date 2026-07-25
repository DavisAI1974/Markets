#!/usr/bin/env python3
"""Bind branch-guarded execution to paginated historical readiness v23."""
from __future__ import annotations

import argparse
import copy
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor_v19 as executor
import ng_historical_refinement_preflight as legacy
import ng_historical_refinement_preflight_v18 as v18
import ng_historical_refinement_readiness_v23 as readiness

SCHEMA = "ng_historical_refinement_preflight.v19"
EXECUTOR_CONTRACT = "ng_historical_refinement_executor_v19"
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


class HistoricalRefinementPreflightV19Error(RuntimeError):
    pass


@contextmanager
def _v23_context() -> Iterator[None]:
    saved = (
        v18.executor,
        v18.readiness,
        v18.EXECUTOR_CONTRACT,
        v18.READINESS_CONTRACT,
        v18.STAGE_CONTRACT,
        v18.STAGE_ORDER,
        v18.STAGE_CONTRACT_FINGERPRINT,
    )
    v18.executor = executor
    v18.readiness = readiness
    v18.EXECUTOR_CONTRACT = EXECUTOR_CONTRACT
    v18.READINESS_CONTRACT = READINESS_CONTRACT
    v18.STAGE_CONTRACT = STAGE_CONTRACT
    v18.STAGE_ORDER = STAGE_ORDER
    v18.STAGE_CONTRACT_FINGERPRINT = STAGE_CONTRACT_FINGERPRINT
    try:
        yield
    finally:
        (
            v18.executor,
            v18.readiness,
            v18.EXECUTOR_CONTRACT,
            v18.READINESS_CONTRACT,
            v18.STAGE_CONTRACT,
            v18.STAGE_ORDER,
            v18.STAGE_CONTRACT_FINGERPRINT,
        ) = saved


def _base_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    prior = base.pop("v18_preflight_fingerprint", None)
    for field in (
        "execution_plan_v23_validated",
        "complete_s3_service_pagination_required",
        "paginated_resolution_pre_outcome",
        "paginated_resolution_precedes_inventory_capture",
        "service_page_request_response_evidence_bound",
        "pagination_marker_progression_required",
        "pagination_cycles_rejected",
        "truncated_final_page_rejected",
        "resolved_capture_spec_bound_to_inventory_capture_v23",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = v18.SCHEMA
    base["fingerprint"] = prior
    return base


def _check_plan(plan: Mapping[str, Any]) -> None:
    executor.validate_plan(plan)
    rows = [row for row in plan.get("stages") or [] if isinstance(row, Mapping)]
    keys = [str(row.get("key")) for row in rows]
    if keys != STAGE_ORDER:
        raise HistoricalRefinementPreflightV19Error(
            "embedded plan does not use readiness-v23 stage order"
        )
    required = (
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
        raise HistoricalRefinementPreflightV19Error(
            "required paginated corpus stage is missing"
        ) from error
    if not (
        positions["corpus_s3_latest_version_resolution"]
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
        raise HistoricalRefinementPreflightV19Error(
            "complete S3 pagination is not ordered before capture, materialization, and G15 replay"
        )
    by_key = {str(row.get("key")): row for row in rows}
    first = by_key["corpus_s3_latest_version_resolution"]
    if first.get("expected_output") != (
        "ng_corpus_s3_paginated_latest_version_resolution_attestation.json"
    ):
        raise HistoricalRefinementPreflightV19Error(
            "legacy non-paginated S3 resolution artifact may not enter preflight v19"
        )
    if first.get("suggested_entrypoint") != [
        "python",
        "ng_corpus_s3_paginated_latest_version_resolution.py",
        "resolve",
    ]:
        raise HistoricalRefinementPreflightV19Error(
            "paginated S3 resolver entrypoint was substituted"
        )
    for key in required[:-1]:
        if by_key[key].get("requires_fixed_outcomes") is not False:
            raise HistoricalRefinementPreflightV19Error(
                f"{key} must remain pre-outcome"
            )


def _finalize(plan: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, Any]:
    _check_plan(plan)
    with _v23_context():
        v18.validate_receipt(base)
    result = copy.deepcopy(dict(base))
    result["schema"] = SCHEMA
    result["v18_preflight_fingerprint"] = base["fingerprint"]
    result["executor_contract"] = EXECUTOR_CONTRACT
    result["readiness_contract"] = READINESS_CONTRACT
    result["readiness_stage_contract"] = copy.deepcopy(STAGE_CONTRACT)
    result["readiness_stage_contract_fingerprint"] = STAGE_CONTRACT_FINGERPRINT
    result["execution_plan_snapshot"] = copy.deepcopy(dict(plan))
    result["execution_plan_v23_validated"] = True
    result["complete_s3_service_pagination_required"] = True
    result["paginated_resolution_pre_outcome"] = True
    result["paginated_resolution_precedes_inventory_capture"] = True
    result["service_page_request_response_evidence_bound"] = True
    result["pagination_marker_progression_required"] = True
    result["pagination_cycles_rejected"] = True
    result["truncated_final_page_rejected"] = True
    result["resolved_capture_spec_bound_to_inventory_capture_v23"] = True
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
    with _v23_context():
        base = v18.execute_preflight(
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
        raise HistoricalRefinementPreflightV19Error(
            "preflight v19 schema or fingerprint mismatch"
        )
    if value.get("executor_contract") != EXECUTOR_CONTRACT:
        raise HistoricalRefinementPreflightV19Error("executor contract mismatch")
    if value.get("readiness_contract") != READINESS_CONTRACT:
        raise HistoricalRefinementPreflightV19Error("readiness contract mismatch")
    if value.get("readiness_stage_contract") != STAGE_CONTRACT:
        raise HistoricalRefinementPreflightV19Error("stage contract mismatch")
    if value.get("readiness_stage_contract_fingerprint") != STAGE_CONTRACT_FINGERPRINT:
        raise HistoricalRefinementPreflightV19Error("stage fingerprint mismatch")
    for field in (
        "execution_plan_v23_validated",
        "complete_s3_service_pagination_required",
        "paginated_resolution_pre_outcome",
        "paginated_resolution_precedes_inventory_capture",
        "service_page_request_response_evidence_bound",
        "pagination_marker_progression_required",
        "pagination_cycles_rejected",
        "truncated_final_page_rejected",
        "resolved_capture_spec_bound_to_inventory_capture_v23",
    ):
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV19Error(
                f"mandatory field mismatch: {field}"
            )
    plan = value.get("execution_plan_snapshot")
    if not isinstance(plan, Mapping):
        raise HistoricalRefinementPreflightV19Error("exact plan snapshot is required")
    _check_plan(plan)
    if value.get("plan_fingerprint") != plan.get("fingerprint"):
        raise HistoricalRefinementPreflightV19Error("plan fingerprint mismatch")
    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("v18_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV19Error(
            "embedded v18 preflight fingerprint mismatch"
        )
    with _v23_context():
        v18.validate_receipt(base)


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
