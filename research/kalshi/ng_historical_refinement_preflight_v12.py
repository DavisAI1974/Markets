#!/usr/bin/env python3
"""Run readiness-v15 historical refinement behind live Git alignment.

Version 12 makes the definition-to-inspected-byte binding gate mandatory between
corpus coverage and basis regeneration. Readiness-v14 plans that only inspect bytes
but do not bind them to observed definition identity are rejected.
"""
from __future__ import annotations

import argparse
import copy
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor_v12 as executor
import ng_historical_refinement_preflight as legacy
import ng_historical_refinement_preflight_v11 as v11
import ng_historical_refinement_readiness_v15 as readiness

SCHEMA = "ng_historical_refinement_preflight.v12"
EXECUTOR_CONTRACT = "ng_historical_refinement_executor_v12"
READINESS_CONTRACT = readiness.SCHEMA
V11_SCHEMA = v11.SCHEMA


class HistoricalRefinementPreflightV12Error(RuntimeError):
    """Raised when branch-guarded execution is not bound to readiness v15."""


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
def _v15_context() -> Iterator[None]:
    saved = (
        v11.executor,
        v11.readiness,
        v11.EXECUTOR_CONTRACT,
        v11.READINESS_CONTRACT,
        v11.STAGE_CONTRACT,
        v11.STAGE_ORDER,
        v11.STAGE_CONTRACT_FINGERPRINT,
    )
    v11.executor = executor
    v11.readiness = readiness
    v11.EXECUTOR_CONTRACT = EXECUTOR_CONTRACT
    v11.READINESS_CONTRACT = READINESS_CONTRACT
    v11.STAGE_CONTRACT = STAGE_CONTRACT
    v11.STAGE_ORDER = STAGE_ORDER
    v11.STAGE_CONTRACT_FINGERPRINT = STAGE_CONTRACT_FINGERPRINT
    try:
        yield
    finally:
        (
            v11.executor,
            v11.readiness,
            v11.EXECUTOR_CONTRACT,
            v11.READINESS_CONTRACT,
            v11.STAGE_CONTRACT,
            v11.STAGE_ORDER,
            v11.STAGE_CONTRACT_FINGERPRINT,
        ) = saved


def _base_v11_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    v11_fingerprint = base.pop("v11_preflight_fingerprint", None)
    for field in (
        "execution_plan_v15_validated",
        "corpus_definition_byte_binding_required",
        "corpus_definition_byte_binding_pre_outcome",
        "corpus_definition_byte_binding_before_basis_regeneration",
        "corpus_definition_byte_binding_before_broad_alignment",
        "inspection_only_route_rejected",
        "readiness_v14_without_definition_byte_binding_rejected",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = V11_SCHEMA
    base["fingerprint"] = v11_fingerprint
    return base


def _finalize(plan: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, Any]:
    with _v15_context():
        executor.validate_plan(plan)
        v11.validate_receipt(base)
    result = copy.deepcopy(dict(base))
    result["schema"] = SCHEMA
    result["v11_preflight_fingerprint"] = base["fingerprint"]
    result["executor_contract"] = EXECUTOR_CONTRACT
    result["readiness_contract"] = READINESS_CONTRACT
    result["readiness_stage_contract"] = copy.deepcopy(STAGE_CONTRACT)
    result["readiness_stage_contract_fingerprint"] = STAGE_CONTRACT_FINGERPRINT
    result["execution_plan_snapshot"] = copy.deepcopy(dict(plan))
    result["execution_plan_v15_validated"] = True
    result["corpus_definition_byte_binding_required"] = True
    result["corpus_definition_byte_binding_pre_outcome"] = True
    result["corpus_definition_byte_binding_before_basis_regeneration"] = True
    result["corpus_definition_byte_binding_before_broad_alignment"] = True
    result["inspection_only_route_rejected"] = True
    result["readiness_v14_without_definition_byte_binding_rejected"] = True
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
    """Execute one readiness-v15 stage with branch alignment before and after."""
    executor.validate_plan(plan)
    runner = executor.run_next if executor_runner is None else executor_runner
    with _v15_context():
        base = v11.execute_preflight(
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
        raise HistoricalRefinementPreflightV12Error(
            "preflight v12 schema or fingerprint mismatch"
        )
    if value.get("executor_contract") != EXECUTOR_CONTRACT:
        raise HistoricalRefinementPreflightV12Error(
            "preflight v12 executor contract mismatch"
        )
    if value.get("readiness_contract") != READINESS_CONTRACT:
        raise HistoricalRefinementPreflightV12Error(
            "preflight v12 readiness contract mismatch"
        )
    if value.get("readiness_stage_contract") != STAGE_CONTRACT:
        raise HistoricalRefinementPreflightV12Error(
            "preflight v12 stage contract mismatch"
        )
    if value.get("readiness_stage_contract_fingerprint") != STAGE_CONTRACT_FINGERPRINT:
        raise HistoricalRefinementPreflightV12Error(
            "preflight v12 stage contract fingerprint mismatch"
        )
    for field in (
        "execution_plan_v15_validated",
        "corpus_definition_byte_binding_required",
        "corpus_definition_byte_binding_pre_outcome",
        "corpus_definition_byte_binding_before_basis_regeneration",
        "corpus_definition_byte_binding_before_broad_alignment",
        "inspection_only_route_rejected",
        "readiness_v14_without_definition_byte_binding_rejected",
    ):
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV12Error(
                f"preflight v12 mandatory field mismatch: {field}"
            )

    plan = value.get("execution_plan_snapshot")
    if not isinstance(plan, Mapping):
        raise HistoricalRefinementPreflightV12Error(
            "preflight v12 requires the exact plan snapshot"
        )
    executor.validate_plan(plan)
    if value.get("plan_fingerprint") != plan.get("fingerprint"):
        raise HistoricalRefinementPreflightV12Error(
            "receipt plan fingerprint does not match embedded v15 plan"
        )
    stage_keys = [
        row.get("key")
        for row in plan.get("stages") or []
        if isinstance(row, Mapping)
    ]
    if stage_keys != STAGE_ORDER:
        raise HistoricalRefinementPreflightV12Error(
            "embedded plan does not use readiness-v15 stage order"
        )
    try:
        coverage = stage_keys.index("corpus_coverage")
        byte_binding = stage_keys.index("corpus_definition_byte_binding")
        basis = stage_keys.index("basis_inventory_regeneration")
        broad_scope = stage_keys.index("broad_corpus_scope")
        g15_replay = stage_keys.index("g15_exact_replay")
    except ValueError as error:
        raise HistoricalRefinementPreflightV12Error(
            "required corpus definition-byte or downstream stage is missing"
        ) from error
    if not (coverage < byte_binding < basis < broad_scope < g15_replay):
        raise HistoricalRefinementPreflightV12Error(
            "definition-byte binding is not between coverage and downstream corpus work"
        )

    plan_rows = {str(row.get("key")): row for row in plan.get("stages") or []}
    if plan_rows["corpus_definition_byte_binding"].get(
        "requires_fixed_outcomes"
    ) is not False:
        raise HistoricalRefinementPreflightV12Error(
            "corpus definition-byte binding must remain pre-outcome"
        )
    contract_rows = {row["key"]: row for row in STAGE_CONTRACT}
    byte_contract = contract_rows["corpus_definition_byte_binding"]
    if (
        byte_contract["filename"]
        != "ng_corpus_definition_byte_binding_gate.json"
        or byte_contract["schema"]
        != "ng_corpus_definition_byte_binding_gate.v1"
        or byte_contract["pre_outcome"] is not True
    ):
        raise HistoricalRefinementPreflightV12Error(
            "readiness v15 must require the canonical definition-byte gate"
        )

    executor_result = value.get("executor_result")
    if isinstance(executor_result, Mapping):
        selected_stage = executor_result.get("stage")
        if selected_stage is not None and selected_stage not in STAGE_ORDER:
            raise HistoricalRefinementPreflightV12Error(
                "executor selected a stage outside readiness v15"
            )

    base = _base_v11_receipt(receipt)
    if base.get("fingerprint") != value.get("v11_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV12Error(
            "embedded v11 preflight fingerprint mismatch"
        )
    with _v15_context():
        v11.validate_receipt(base)


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
