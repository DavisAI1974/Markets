#!/usr/bin/env python3
"""Bind branch-guarded execution to the complete readiness-v38 G16-blind arm.

This preflight recursively validates the v29 compiler and arm receipts, requires the
exact readiness-v38 stage order, exposes only explicitly bound G15 outcomes, and keeps
both fixed-G16 publication stages disabled. It then delegates one first-blocking-stage
run to the existing live branch-alignment wrapper and fingerprints the exact plan used.
"""
from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_corpus_executor_pipeline_arm_v29 as arm
import ng_historical_refinement_executor_v34 as executor
import ng_historical_refinement_preflight as legacy
import ng_historical_refinement_readiness_v38 as readiness

SCHEMA = "ng_historical_refinement_preflight.v30"
EXECUTOR_CONTRACT = "ng_historical_refinement_executor_v34"
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
_WRAPPER_FIELDS = (
    "legacy_preflight_fingerprint",
    "executor_contract",
    "readiness_contract",
    "readiness_stage_contract",
    "readiness_stage_contract_fingerprint",
    "execution_plan_snapshot",
    "execution_plan_v38_validated",
    "pipeline_arm_receipt",
    "pipeline_arm_receipt_fingerprint",
    "compiler_provenance_recursively_validated",
    "fixed_g15_outcomes_explicitly_bound",
    "g16_outcomes_forbidden",
    "g16_blind_chain_terminal_stage",
    "g16_counterfactual_publication_disabled",
    "g16_attribution_bound_publication_disabled",
    "g16_curve_locked_before_scoring",
    "first_blocking_stage_only",
    "blind_and_brain_paths_protected",
)


class HistoricalRefinementPreflightV30Error(RuntimeError):
    pass


def _check_plan(plan: Mapping[str, Any]) -> None:
    executor.validate_plan(plan)
    rows = [row for row in plan.get("stages") or [] if isinstance(row, Mapping)]
    keys = [str(row.get("key")) for row in rows]
    if keys != STAGE_ORDER:
        raise HistoricalRefinementPreflightV30Error(
            "embedded plan does not use readiness-v38 stage order"
        )
    by_key = {str(row.get("key")): row for row in rows}
    if keys[-4:] != [
        "g16_counterfactual_curve_lock",
        "g16_attribution_bound_curve_lock",
        "g16_counterfactual_publication",
        "g16_attribution_bound_publication",
    ]:
        raise HistoricalRefinementPreflightV30Error(
            "G16 lock/publication chronology changed"
        )
    if by_key[arm.TERMINAL_STAGE].get("enabled") is not True:
        raise HistoricalRefinementPreflightV30Error(
            "attribution-bound G16 curve lock must be armed"
        )
    for key in arm.ARMED_STAGES:
        if by_key[key].get("enabled") is not True:
            raise HistoricalRefinementPreflightV30Error(
                f"{key}: complete G16-blind chain is not armed"
            )
    for key in arm.PUBLICATION_STAGES:
        if by_key[key].get("enabled") is not False:
            raise HistoricalRefinementPreflightV30Error(
                f"{key}: fixed G16 publication must remain disabled"
            )
    outcomes = plan.get("outcome_paths")
    if not isinstance(outcomes, list) or not outcomes:
        raise HistoricalRefinementPreflightV30Error(
            "the armed plan requires explicit fixed-G15 outcome paths"
        )
    normalized = arm._normalize_g15_outcomes(outcomes)
    if normalized != outcomes:
        raise HistoricalRefinementPreflightV30Error(
            "fixed-G15 outcome paths are not canonical"
        )
    outcome_tokens = set(outcomes)
    for spec in readiness.STAGES:
        row = by_key[spec.key]
        expected_entrypoint = list(executor.SUGGESTED_ENTRYPOINTS.get(spec.key, ()))
        if row.get("suggested_entrypoint") != expected_entrypoint:
            raise HistoricalRefinementPreflightV30Error(
                f"{spec.key}: suggested entrypoint was substituted"
            )
        argv = row.get("argv")
        if not isinstance(argv, list) or argv[: len(expected_entrypoint)] != expected_entrypoint:
            raise HistoricalRefinementPreflightV30Error(
                f"{spec.key}: operational command was substituted"
            )
        if row.get("expected_output") != spec.filename:
            raise HistoricalRefinementPreflightV30Error(
                f"{spec.key}: canonical output artifact was substituted"
            )
        if spec.pre_outcome and outcome_tokens.intersection(argv):
            raise HistoricalRefinementPreflightV30Error(
                f"{spec.key}: outcome-blind command references fixed G15 outcomes"
            )
    protected = {
        str(row.get("role")): str(row.get("path"))
        for row in plan.get("protected_paths") or []
        if isinstance(row, Mapping)
    }
    for role in ("g15_blind_forecast", "g16_blind_forecast", "ng_brain"):
        if not protected.get(role):
            raise HistoricalRefinementPreflightV30Error(
                f"protected path is missing: {role}"
            )
    for field in (
        "remote_presence_inferred",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if plan.get(field) is not False:
            raise HistoricalRefinementPreflightV30Error(
                f"execution plan must keep {field}=false"
            )
    if plan.get("one_signal_authority_preserved") is not True:
        raise HistoricalRefinementPreflightV30Error(
            "execution plan must preserve one signal authority"
        )
    if plan.get("blind_forecasts_immutable") is not True:
        raise HistoricalRefinementPreflightV30Error(
            "execution plan must preserve blind forecasts"
        )
    if plan.get("cme_event_contracts_mode") != "SHADOW":
        raise HistoricalRefinementPreflightV30Error(
            "CME event contracts must remain SHADOW"
        )
    if plan.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise HistoricalRefinementPreflightV30Error(
            "brokerage contract must remain tastytrade, not IBKR"
        )


def _validated_arm(
    plan: Mapping[str, Any], receipt: Mapping[str, Any]
) -> dict[str, Any]:
    _check_plan(plan)
    try:
        return arm.validate_arm_receipt(receipt, armed_plan=plan)
    except Exception as error:
        raise HistoricalRefinementPreflightV30Error(
            f"readiness-v38 pipeline arm provenance is invalid: {error}"
        ) from error


@contextmanager
def _executor_context() -> Iterator[None]:
    old_executor = legacy.executor
    legacy.executor = executor
    try:
        yield
    finally:
        legacy.executor = old_executor


def _base_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    prior = base.pop("legacy_preflight_fingerprint", None)
    for field in _WRAPPER_FIELDS[1:]:
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = legacy.SCHEMA
    base["fingerprint"] = prior
    return base


def _finalize(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    base: Mapping[str, Any],
) -> dict[str, Any]:
    validated_arm = _validated_arm(plan, arm_receipt)
    with _executor_context():
        legacy.validate_receipt(base)
    result = copy.deepcopy(dict(base))
    result.update(
        {
            "schema": SCHEMA,
            "legacy_preflight_fingerprint": base["fingerprint"],
            "executor_contract": EXECUTOR_CONTRACT,
            "readiness_contract": READINESS_CONTRACT,
            "readiness_stage_contract": copy.deepcopy(STAGE_CONTRACT),
            "readiness_stage_contract_fingerprint": STAGE_CONTRACT_FINGERPRINT,
            "execution_plan_snapshot": copy.deepcopy(dict(plan)),
            "execution_plan_v38_validated": True,
            "pipeline_arm_receipt": copy.deepcopy(validated_arm),
            "pipeline_arm_receipt_fingerprint": validated_arm["fingerprint"],
            "compiler_provenance_recursively_validated": True,
            "fixed_g15_outcomes_explicitly_bound": True,
            "g16_outcomes_forbidden": True,
            "g16_blind_chain_terminal_stage": arm.TERMINAL_STAGE,
            "g16_counterfactual_publication_disabled": True,
            "g16_attribution_bound_publication_disabled": True,
            "g16_curve_locked_before_scoring": True,
            "first_blocking_stage_only": True,
            "blind_and_brain_paths_protected": True,
        }
    )
    result.pop("fingerprint", None)
    result["fingerprint"] = legacy._fingerprint(result)
    validate_receipt(result)
    return result


def execute_preflight(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    ledger_path: Path,
    *,
    executor_runner: Callable[..., Mapping[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    _validated_arm(plan, arm_receipt)
    runner = executor.execute_next if executor_runner is None else executor_runner
    with _executor_context():
        base = legacy.execute_preflight(
            plan,
            ledger_path,
            executor_runner=runner,
            **kwargs,
        )
    return _finalize(plan, arm_receipt, base)


def validate_receipt(receipt: Mapping[str, Any]) -> None:
    value = copy.deepcopy(dict(receipt))
    observed = value.pop("fingerprint", None)
    if value.get("schema") != SCHEMA or observed != legacy._fingerprint(value):
        raise HistoricalRefinementPreflightV30Error(
            "preflight v30 schema or fingerprint mismatch"
        )
    if value.get("executor_contract") != EXECUTOR_CONTRACT:
        raise HistoricalRefinementPreflightV30Error("executor contract mismatch")
    if value.get("readiness_contract") != READINESS_CONTRACT:
        raise HistoricalRefinementPreflightV30Error("readiness contract mismatch")
    if value.get("readiness_stage_contract") != STAGE_CONTRACT:
        raise HistoricalRefinementPreflightV30Error("stage contract mismatch")
    if value.get("readiness_stage_contract_fingerprint") != STAGE_CONTRACT_FINGERPRINT:
        raise HistoricalRefinementPreflightV30Error("stage fingerprint mismatch")
    mandatory = (
        "execution_plan_v38_validated",
        "compiler_provenance_recursively_validated",
        "fixed_g15_outcomes_explicitly_bound",
        "g16_outcomes_forbidden",
        "g16_counterfactual_publication_disabled",
        "g16_attribution_bound_publication_disabled",
        "g16_curve_locked_before_scoring",
        "first_blocking_stage_only",
        "blind_and_brain_paths_protected",
    )
    for field in mandatory:
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV30Error(
                f"mandatory field mismatch: {field}"
            )
    if value.get("g16_blind_chain_terminal_stage") != arm.TERMINAL_STAGE:
        raise HistoricalRefinementPreflightV30Error("G16-blind terminal stage mismatch")
    plan = value.get("execution_plan_snapshot")
    arm_receipt = value.get("pipeline_arm_receipt")
    if not isinstance(plan, Mapping) or not isinstance(arm_receipt, Mapping):
        raise HistoricalRefinementPreflightV30Error(
            "exact plan and pipeline-arm snapshots are required"
        )
    _validated_arm(plan, arm_receipt)
    if value.get("pipeline_arm_receipt_fingerprint") != arm_receipt.get("fingerprint"):
        raise HistoricalRefinementPreflightV30Error(
            "pipeline arm receipt fingerprint mismatch"
        )
    if value.get("plan_fingerprint") != plan.get("fingerprint"):
        raise HistoricalRefinementPreflightV30Error("plan fingerprint mismatch")
    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("legacy_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV30Error(
            "embedded legacy preflight fingerprint mismatch"
        )
    with _executor_context():
        legacy.validate_receipt(base)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--arm-receipt", required=True)
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
    args = parser.parse_args(argv)
    plan = legacy._load_json(Path(args.plan))
    arm_receipt = legacy._load_json(Path(args.arm_receipt))
    receipt = execute_preflight(
        plan,
        arm_receipt,
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
    )
    legacy._atomic_json(Path(args.out), receipt)
    print(
        f"[ng_historical_refinement_preflight_v30] {receipt['status']} "
        f"executor_called={receipt['executor_called']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
