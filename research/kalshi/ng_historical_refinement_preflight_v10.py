#!/usr/bin/env python3
"""Run readiness-v13 historical refinement behind live pre/post Git alignment.

Version 10 binds branch-guarded execution to the exact G16 curve authorization,
pre-outcome lock, and scored publication artifacts. The older generic lock and
publication route cannot satisfy the embedded readiness contract.
"""
from __future__ import annotations

import argparse
import copy
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor_v10 as executor
import ng_historical_refinement_preflight as legacy
import ng_historical_refinement_preflight_v9 as v9
import ng_historical_refinement_readiness_v13 as readiness

SCHEMA = "ng_historical_refinement_preflight.v10"
EXECUTOR_CONTRACT = "ng_historical_refinement_executor_v10"
READINESS_CONTRACT = readiness.SCHEMA
V9_SCHEMA = v9.SCHEMA


class HistoricalRefinementPreflightV10Error(RuntimeError):
    """Raised when branch-guarded execution is not bound to readiness v13."""


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
def _v13_context() -> Iterator[None]:
    saved = (
        v9.executor,
        v9.readiness,
        v9.EXECUTOR_CONTRACT,
        v9.READINESS_CONTRACT,
        v9.STAGE_CONTRACT,
        v9.STAGE_ORDER,
        v9.STAGE_CONTRACT_FINGERPRINT,
    )
    v9.executor = executor
    v9.readiness = readiness
    v9.EXECUTOR_CONTRACT = EXECUTOR_CONTRACT
    v9.READINESS_CONTRACT = READINESS_CONTRACT
    v9.STAGE_CONTRACT = STAGE_CONTRACT
    v9.STAGE_ORDER = STAGE_ORDER
    v9.STAGE_CONTRACT_FINGERPRINT = STAGE_CONTRACT_FINGERPRINT
    try:
        yield
    finally:
        (
            v9.executor,
            v9.readiness,
            v9.EXECUTOR_CONTRACT,
            v9.READINESS_CONTRACT,
            v9.STAGE_CONTRACT,
            v9.STAGE_ORDER,
            v9.STAGE_CONTRACT_FINGERPRINT,
        ) = saved


def _base_v9_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    v9_fingerprint = base.pop("v9_preflight_fingerprint", None)
    for field in (
        "execution_plan_v13_validated",
        "g16_exact_counterfactual_curve_authorization_required",
        "g16_exact_counterfactual_curve_authorization_pre_outcome",
        "g16_exact_curve_lock_required",
        "g16_exact_curve_lock_pre_outcome",
        "g16_exact_publication_required",
        "g16_exact_publication_post_outcome",
        "g16_exact_corpus_provenance_preserved_through_lock_and_publication",
        "legacy_g16_lock_publication_route_rejected",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = V9_SCHEMA
    base["fingerprint"] = v9_fingerprint
    return base


def _finalize(plan: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, Any]:
    with _v13_context():
        executor.validate_plan(plan)
        v9.validate_receipt(base)
    result = copy.deepcopy(dict(base))
    result["schema"] = SCHEMA
    result["v9_preflight_fingerprint"] = base["fingerprint"]
    result["executor_contract"] = EXECUTOR_CONTRACT
    result["readiness_contract"] = READINESS_CONTRACT
    result["readiness_stage_contract"] = copy.deepcopy(STAGE_CONTRACT)
    result["readiness_stage_contract_fingerprint"] = STAGE_CONTRACT_FINGERPRINT
    result["execution_plan_snapshot"] = copy.deepcopy(dict(plan))
    result["execution_plan_v13_validated"] = True
    result["g16_exact_counterfactual_curve_authorization_required"] = True
    result["g16_exact_counterfactual_curve_authorization_pre_outcome"] = True
    result["g16_exact_curve_lock_required"] = True
    result["g16_exact_curve_lock_pre_outcome"] = True
    result["g16_exact_publication_required"] = True
    result["g16_exact_publication_post_outcome"] = True
    result["g16_exact_corpus_provenance_preserved_through_lock_and_publication"] = True
    result["legacy_g16_lock_publication_route_rejected"] = True
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
    """Execute one readiness-v13 stage with branch alignment before and after."""
    executor.validate_plan(plan)
    runner = executor.run_next if executor_runner is None else executor_runner
    with _v13_context():
        base = v9.execute_preflight(
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
        raise HistoricalRefinementPreflightV10Error(
            "preflight v10 schema or fingerprint mismatch"
        )
    if value.get("executor_contract") != EXECUTOR_CONTRACT:
        raise HistoricalRefinementPreflightV10Error(
            "preflight v10 executor contract mismatch"
        )
    if value.get("readiness_contract") != READINESS_CONTRACT:
        raise HistoricalRefinementPreflightV10Error(
            "preflight v10 readiness contract mismatch"
        )
    if value.get("readiness_stage_contract") != STAGE_CONTRACT:
        raise HistoricalRefinementPreflightV10Error(
            "preflight v10 stage contract mismatch"
        )
    if value.get("readiness_stage_contract_fingerprint") != STAGE_CONTRACT_FINGERPRINT:
        raise HistoricalRefinementPreflightV10Error(
            "preflight v10 stage contract fingerprint mismatch"
        )
    for field in (
        "execution_plan_v13_validated",
        "g16_exact_counterfactual_curve_authorization_required",
        "g16_exact_counterfactual_curve_authorization_pre_outcome",
        "g16_exact_curve_lock_required",
        "g16_exact_curve_lock_pre_outcome",
        "g16_exact_publication_required",
        "g16_exact_publication_post_outcome",
        "g16_exact_corpus_provenance_preserved_through_lock_and_publication",
        "legacy_g16_lock_publication_route_rejected",
    ):
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV10Error(
                f"preflight v10 mandatory field mismatch: {field}"
            )

    plan = value.get("execution_plan_snapshot")
    if not isinstance(plan, Mapping):
        raise HistoricalRefinementPreflightV10Error(
            "preflight v10 requires the exact plan snapshot"
        )
    executor.validate_plan(plan)
    if value.get("plan_fingerprint") != plan.get("fingerprint"):
        raise HistoricalRefinementPreflightV10Error(
            "receipt plan fingerprint does not match embedded v13 plan"
        )
    stage_keys = [
        row.get("key")
        for row in plan.get("stages") or []
        if isinstance(row, Mapping)
    ]
    if stage_keys != STAGE_ORDER:
        raise HistoricalRefinementPreflightV10Error(
            "embedded plan does not use readiness-v13 stage order"
        )
    try:
        exact_causal = stage_keys.index("g16_exact_counterfactual_causal_authorization")
        prepared_curve = stage_keys.index("g16_prepared_curve_authorization")
        counterfactual_curve = stage_keys.index(
            "g16_counterfactual_curve_authorization"
        )
        exact_curve = stage_keys.index("g16_exact_counterfactual_curve_authorization")
        exact_lock = stage_keys.index("g16_counterfactual_curve_lock")
        exact_publication = stage_keys.index("g16_counterfactual_publication")
    except ValueError as error:
        raise HistoricalRefinementPreflightV10Error(
            "required exact G16 causal, curve, lock, or publication stage is missing"
        ) from error
    if not (
        exact_causal
        < prepared_curve
        < counterfactual_curve
        < exact_curve
        < exact_lock
        < exact_publication
    ):
        raise HistoricalRefinementPreflightV10Error(
            "G16 exact causal, curve, lock, and publication stages are out of order"
        )

    plan_rows = {str(row.get("key")): row for row in plan.get("stages") or []}
    for key in (
        "g16_exact_counterfactual_causal_authorization",
        "g16_prepared_curve_authorization",
        "g16_counterfactual_curve_authorization",
        "g16_exact_counterfactual_curve_authorization",
        "g16_counterfactual_curve_lock",
    ):
        if plan_rows[key].get("requires_fixed_outcomes") is not False:
            raise HistoricalRefinementPreflightV10Error(
                f"{key} must remain pre-outcome"
            )
    if plan_rows["g16_counterfactual_publication"].get(
        "requires_fixed_outcomes"
    ) is not True:
        raise HistoricalRefinementPreflightV10Error(
            "exact G16 publication must remain behind the fixed-outcome boundary"
        )

    contract_rows = {row["key"]: row for row in STAGE_CONTRACT}
    if (
        contract_rows["g16_counterfactual_curve_lock"]["filename"]
        != "g16_exact_counterfactual_curve_lock.json"
        or contract_rows["g16_counterfactual_curve_lock"]["schema"]
        != "ng_g16_exact_counterfactual_curve_lock.v1"
        or contract_rows["g16_counterfactual_publication"]["filename"]
        != "g16_exact_counterfactual_publication_completion.json"
        or contract_rows["g16_counterfactual_publication"]["schema"]
        != "ng_g16_exact_counterfactual_publication_completion.v1"
    ):
        raise HistoricalRefinementPreflightV10Error(
            "legacy G16 lock/publication artifacts may not satisfy readiness v13"
        )

    executor_result = value.get("executor_result")
    if isinstance(executor_result, Mapping):
        selected_stage = executor_result.get("stage")
        if selected_stage is not None and selected_stage not in STAGE_ORDER:
            raise HistoricalRefinementPreflightV10Error(
                "executor selected a stage outside readiness v13"
            )

    base = _base_v9_receipt(receipt)
    if base.get("fingerprint") != value.get("v9_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV10Error(
            "embedded v9 preflight fingerprint mismatch"
        )
    with _v13_context():
        v9.validate_receipt(base)


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
