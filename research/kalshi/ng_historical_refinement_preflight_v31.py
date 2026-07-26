#!/usr/bin/env python3
"""Bind branch-guarded execution to the compiler-v31 readiness-v38 blind arm.

The preflight recursively validates the exact CLI contract, command-artifact
lineage, extension manifest, compiler-v31 receipt, and pipeline-arm-v31 receipt
before allowing the guarded executor to run one first-blocking stage. The chain
remains armed only through the immutable attribution-bound G16 curve lock;
fixed-G16 scoring/publication stays disabled.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_corpus_executor_pipeline_arm_v31 as arm
import ng_historical_refinement_executor_v34 as executor
import ng_historical_refinement_preflight_v30 as prior
import ng_historical_refinement_readiness_v38 as readiness

SCHEMA = "ng_historical_refinement_preflight.v31"
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
STAGE_CONTRACT_FINGERPRINT = prior.legacy._fingerprint(STAGE_CONTRACT)
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
    "compiler_v31_receipt_fingerprint",
    "extension_manifest_fingerprint",
    "command_contract_fingerprint",
    "command_lineage_fingerprint",
    "compiler_v31_provenance_recursively_validated",
    "all_required_cli_options_verified",
    "exact_command_source_bindings_verified",
    "g16_actual_exposed_only_at_counterfactual_publication",
    "fixed_g15_outcomes_explicitly_bound",
    "g16_outcomes_forbidden",
    "g16_blind_chain_terminal_stage",
    "g16_counterfactual_publication_disabled",
    "g16_attribution_bound_publication_disabled",
    "g16_curve_locked_before_scoring",
    "first_blocking_stage_only",
    "blind_and_brain_paths_protected",
)


class HistoricalRefinementPreflightV31Error(RuntimeError):
    pass


def _check_plan(plan: Mapping[str, Any]) -> None:
    try:
        prior._check_plan(plan)
    except Exception as error:
        raise HistoricalRefinementPreflightV31Error(str(error)) from error
    rows = {str(row.get("key")): row for row in plan.get("stages") or []}
    if list(rows) != STAGE_ORDER:
        raise HistoricalRefinementPreflightV31Error(
            "embedded plan does not use readiness-v38 stage order"
        )
    if rows[arm.TERMINAL_STAGE].get("enabled") is not True:
        raise HistoricalRefinementPreflightV31Error(
            "attribution-bound G16 curve lock must be armed"
        )
    for key in arm.ARMED_STAGES:
        if rows[key].get("enabled") is not True:
            raise HistoricalRefinementPreflightV31Error(
                f"{key}: compiler-v31 G16-blind chain is not armed"
            )
    for key in arm.PUBLICATION_STAGES:
        if rows[key].get("enabled") is not False:
            raise HistoricalRefinementPreflightV31Error(
                f"{key}: fixed G16 publication must remain disabled"
            )


def _validated_arm(
    plan: Mapping[str, Any], receipt: Mapping[str, Any]
) -> dict[str, Any]:
    _check_plan(plan)
    try:
        checked = arm.validate_arm_receipt(receipt, armed_plan=plan)
    except Exception as error:
        raise HistoricalRefinementPreflightV31Error(
            f"readiness-v38 compiler-v31 arm provenance is invalid: {error}"
        ) from error
    for field in (
        "all_required_cli_options_verified",
        "exact_command_source_bindings_verified",
        "g16_actual_exposed_only_at_counterfactual_publication",
    ):
        if checked.get(field) is not True:
            raise HistoricalRefinementPreflightV31Error(
                f"pipeline arm v31 must keep {field}=true"
            )
    return checked


def _base_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    prior_fingerprint = base.pop("legacy_preflight_fingerprint", None)
    for field in _WRAPPER_FIELDS[1:]:
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = prior.legacy.SCHEMA
    base["fingerprint"] = prior_fingerprint
    return base


def _finalize(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    base: Mapping[str, Any],
) -> dict[str, Any]:
    validated_arm = _validated_arm(plan, arm_receipt)
    with prior._executor_context():
        prior.legacy.validate_receipt(base)
    compiler_receipt = validated_arm.get("compiler_receipt")
    if not isinstance(compiler_receipt, Mapping):
        raise HistoricalRefinementPreflightV31Error(
            "pipeline arm v31 lacks embedded compiler-v31 receipt"
        )
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
            "compiler_v31_receipt_fingerprint": compiler_receipt.get("fingerprint"),
            "extension_manifest_fingerprint": validated_arm.get(
                "extension_manifest_fingerprint"
            ),
            "command_contract_fingerprint": validated_arm.get(
                "command_contract_fingerprint"
            ),
            "command_lineage_fingerprint": validated_arm.get(
                "command_lineage_fingerprint"
            ),
            "compiler_v31_provenance_recursively_validated": True,
            "all_required_cli_options_verified": True,
            "exact_command_source_bindings_verified": True,
            "g16_actual_exposed_only_at_counterfactual_publication": True,
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
    result["fingerprint"] = prior.legacy._fingerprint(result)
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
    with prior._executor_context():
        base = prior.legacy.execute_preflight(
            plan,
            ledger_path,
            executor_runner=runner,
            **kwargs,
        )
    return _finalize(plan, arm_receipt, base)


def validate_receipt(receipt: Mapping[str, Any]) -> None:
    value = copy.deepcopy(dict(receipt))
    observed = value.pop("fingerprint", None)
    if value.get("schema") != SCHEMA or observed != prior.legacy._fingerprint(value):
        raise HistoricalRefinementPreflightV31Error(
            "preflight v31 schema or fingerprint mismatch"
        )
    if value.get("executor_contract") != EXECUTOR_CONTRACT:
        raise HistoricalRefinementPreflightV31Error("executor contract mismatch")
    if value.get("readiness_contract") != READINESS_CONTRACT:
        raise HistoricalRefinementPreflightV31Error("readiness contract mismatch")
    if value.get("readiness_stage_contract") != STAGE_CONTRACT:
        raise HistoricalRefinementPreflightV31Error("stage contract mismatch")
    if value.get("readiness_stage_contract_fingerprint") != STAGE_CONTRACT_FINGERPRINT:
        raise HistoricalRefinementPreflightV31Error("stage fingerprint mismatch")
    mandatory = (
        "execution_plan_v38_validated",
        "compiler_v31_provenance_recursively_validated",
        "all_required_cli_options_verified",
        "exact_command_source_bindings_verified",
        "g16_actual_exposed_only_at_counterfactual_publication",
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
            raise HistoricalRefinementPreflightV31Error(
                f"mandatory field mismatch: {field}"
            )
    if value.get("g16_blind_chain_terminal_stage") != arm.TERMINAL_STAGE:
        raise HistoricalRefinementPreflightV31Error(
            "G16-blind terminal stage mismatch"
        )
    plan = value.get("execution_plan_snapshot")
    arm_receipt = value.get("pipeline_arm_receipt")
    if not isinstance(plan, Mapping) or not isinstance(arm_receipt, Mapping):
        raise HistoricalRefinementPreflightV31Error(
            "exact plan and pipeline-arm snapshots are required"
        )
    validated_arm = _validated_arm(plan, arm_receipt)
    if value.get("pipeline_arm_receipt_fingerprint") != validated_arm.get("fingerprint"):
        raise HistoricalRefinementPreflightV31Error(
            "pipeline arm receipt fingerprint mismatch"
        )
    compiler_receipt = validated_arm.get("compiler_receipt")
    if not isinstance(compiler_receipt, Mapping):
        raise HistoricalRefinementPreflightV31Error(
            "pipeline arm lacks compiler-v31 receipt"
        )
    expected_links = {
        "compiler_v31_receipt_fingerprint": compiler_receipt.get("fingerprint"),
        "extension_manifest_fingerprint": validated_arm.get(
            "extension_manifest_fingerprint"
        ),
        "command_contract_fingerprint": validated_arm.get(
            "command_contract_fingerprint"
        ),
        "command_lineage_fingerprint": validated_arm.get(
            "command_lineage_fingerprint"
        ),
    }
    for field, expected in expected_links.items():
        if value.get(field) != expected:
            raise HistoricalRefinementPreflightV31Error(
                f"compiler-v31 provenance link mismatch: {field}"
            )
    if value.get("plan_fingerprint") != plan.get("fingerprint"):
        raise HistoricalRefinementPreflightV31Error("plan fingerprint mismatch")
    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("legacy_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV31Error(
            "embedded legacy preflight fingerprint mismatch"
        )
    with prior._executor_context():
        prior.legacy.validate_receipt(base)


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
    plan = prior.legacy._load_json(Path(args.plan))
    arm_receipt = prior.legacy._load_json(Path(args.arm_receipt))
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
    prior.legacy._atomic_json(Path(args.out), receipt)
    print(
        f"[ng_historical_refinement_preflight_v31] {receipt['status']} "
        f"executor_called={receipt['executor_called']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
