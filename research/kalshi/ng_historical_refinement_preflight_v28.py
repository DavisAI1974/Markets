#!/usr/bin/env python3
"""Bind branch-guarded execution to attribution-authorized readiness v32."""
from __future__ import annotations

import argparse
import copy
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor_v28 as executor
import ng_historical_refinement_preflight as legacy
import ng_historical_refinement_readiness_v32 as readiness

SCHEMA = "ng_historical_refinement_preflight.v28"
EXECUTOR_CONTRACT = "ng_historical_refinement_executor_v28"
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


class HistoricalRefinementPreflightV28Error(RuntimeError):
    pass


def _check_flags(argv: Sequence[Any], flags: Sequence[str], *, stage: str) -> None:
    if not isinstance(argv, list) or not all(isinstance(part, str) for part in argv):
        raise HistoricalRefinementPreflightV28Error(f"{stage}: command vector is invalid")
    for flag in flags:
        if flag not in argv:
            raise HistoricalRefinementPreflightV28Error(
                f"{stage}: command lacks required binding {flag}"
            )


def _check_plan(plan: Mapping[str, Any]) -> None:
    executor.validate_plan(plan)
    rows = [row for row in plan.get("stages") or [] if isinstance(row, Mapping)]
    keys = [str(row.get("key")) for row in rows]
    if keys != STAGE_ORDER:
        raise HistoricalRefinementPreflightV28Error(
            "embedded plan does not use readiness-v32 stage order"
        )
    required = (
        "corpus_expected_day_contract",
        "corpus_inventory_finalization_contract",
        "corpus_s3_latest_version_resolution",
        "corpus_s3_inventory_capture",
        "corpus_s3_materialization",
        "corpus_s3_materialization_provenance",
        "corpus_source_identity_attestation",
        "corpus_coverage",
        "corpus_definition_byte_binding",
        "target_slice_coverage",
        "target_slice_broad_lineage",
        "target_slice_derivation",
        "basis_inventory_regeneration",
        "replay_catalog_export",
        "broad_corpus_scope",
        "broad_corpus_exact_overlap",
        "broad_corpus_exact_partition",
        "g15_prepared_normalized_identity",
        "g15_exact_replay",
        "g15_exact_refinement",
        "g15_counterfactual_attribution",
        "g15_counterfactual_attribution_authorization",
        "g15_publication",
    )
    try:
        positions = {key: keys.index(key) for key in required}
    except ValueError as error:
        raise HistoricalRefinementPreflightV28Error(
            "required v32 G15 authorization stage is missing"
        ) from error
    if [positions[key] for key in required] != sorted(positions[key] for key in required):
        raise HistoricalRefinementPreflightV28Error(
            "G15 authorization stages are not chronological"
        )

    by_key = {str(row.get("key")): row for row in rows}
    expected_contracts = {
        "corpus_expected_day_contract": (
            "ng_corpus_expected_day_contract_attestation.json",
            ["python", "ng_corpus_expected_day_contract.py", "build"],
        ),
        "corpus_inventory_finalization_contract": (
            "ng_corpus_inventory_finalization_contract.json",
            ["python", "ng_corpus_inventory_finalization_contract.py", "build"],
        ),
        "corpus_s3_inventory_capture": (
            "ng_corpus_s3_runtime_observed_inventory_capture_attestation.json",
            ["python", "ng_corpus_s3_runtime_observed_inventory_capture.py", "capture"],
        ),
        "corpus_s3_materialization": (
            "ng_corpus_s3_exact_materializer_receipt.json",
            ["python", "ng_corpus_s3_exact_materializer.py", "materialize"],
        ),
        "corpus_s3_materialization_provenance": (
            "ng_corpus_s3_materializer_provenance_gate.json",
            ["python", "ng_corpus_s3_materializer_provenance_gate.py", "build"],
        ),
        "corpus_source_identity_attestation": (
            "ng_corpus_source_identity_attestation.json",
            ["python", "ng_corpus_source_identity_attestation.py", "build"],
        ),
        "g15_prepared_normalized_identity": (
            "g15_prepared_normalized_identity_guard.json",
            ["python", "ng_g15_prepared_normalized_identity_guard.py", "build"],
        ),
        "g15_exact_replay": (
            "g15_exact_replay_completion.json",
            ["python", "ng_g15_exact_replay_completion.py"],
        ),
        "g15_exact_refinement": (
            "g15_exact_refinement_authorization.json",
            ["python", "ng_g15_exact_refinement_gate.py"],
        ),
        "g15_counterfactual_attribution": (
            "g15_counterfactual_attribution.json",
            ["python", "ng_g15_counterfactual_attribution.py"],
        ),
        "g15_counterfactual_attribution_authorization": (
            "g15_counterfactual_attribution_authorization.json",
            ["python", "ng_g15_counterfactual_attribution_gate.py"],
        ),
    }
    for key, (output, entrypoint) in expected_contracts.items():
        row = by_key[key]
        if row.get("expected_output") != output:
            raise HistoricalRefinementPreflightV28Error(
                f"{key}: canonical artifact was substituted"
            )
        if row.get("suggested_entrypoint") != entrypoint:
            raise HistoricalRefinementPreflightV28Error(
                f"{key}: suggested entrypoint was substituted"
            )

    command_contracts = {
        "g15_prepared_normalized_identity": (
            ["python", "ng_g15_prepared_normalized_identity_guard.py", "build"],
            ("--bridge", "--prepared-index", "--out"),
        ),
        "g15_exact_replay": (
            ["python", "ng_g15_exact_replay_completion.py"],
            ("--bridge", "--prepared-index", "--replay", "--anchor", "--blind-prior", "--out"),
        ),
        "g15_exact_refinement": (
            ["python", "ng_g15_exact_refinement_gate.py"],
            ("--completion", "--pipeline", "--blind-forecast", "--out"),
        ),
        "g15_counterfactual_attribution": (
            ["python", "ng_g15_counterfactual_attribution.py"],
            ("--replay", "--anchor", "--refine-stream", "--out"),
        ),
        "g15_counterfactual_attribution_authorization": (
            ["python", "ng_g15_counterfactual_attribution_gate.py"],
            ("--completion", "--pipeline", "--refinement-authorization", "--attribution", "--out"),
        ),
    }
    for key, (prefix, flags) in command_contracts.items():
        argv = by_key[key].get("argv", [])
        if argv[: len(prefix)] != prefix:
            raise HistoricalRefinementPreflightV28Error(
                f"{key}: operational command was substituted"
            )
        _check_flags(argv, flags, stage=key)

    causal_order = (
        "g15_prepared_normalized_identity",
        "g15_exact_replay",
        "g15_exact_refinement",
        "g15_counterfactual_attribution",
        "g15_counterfactual_attribution_authorization",
        "g15_publication",
    )
    causal_positions = [positions[key] for key in causal_order]
    if any(right != left + 1 for left, right in zip(causal_positions, causal_positions[1:])):
        raise HistoricalRefinementPreflightV28Error(
            "G15 identity, replay, refinement, attribution, authorization, and publication must remain contiguous"
        )
    for key in causal_order[:-1]:
        if by_key[key].get("requires_fixed_outcomes") is not False:
            raise HistoricalRefinementPreflightV28Error(f"{key} must remain pre-outcome")
    if by_key["g15_publication"].get("requires_fixed_outcomes") is not True:
        raise HistoricalRefinementPreflightV28Error(
            "G15 publication must remain behind the fixed-outcome boundary"
        )


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
    for field in (
        "executor_contract",
        "readiness_contract",
        "readiness_stage_contract",
        "readiness_stage_contract_fingerprint",
        "execution_plan_snapshot",
        "execution_plan_v32_validated",
        "g15_prepared_identity_replay_refinement_attribution_contiguous",
        "g15_exact_replay_command_fully_bound",
        "g15_exact_refinement_command_fully_bound",
        "g15_six_factor_attribution_command_fully_bound",
        "g15_attribution_authorization_command_fully_bound",
        "g15_attribution_authorization_pre_outcome",
        "g15_publication_blocked_until_attribution_authorized",
        "g15_lesson_proposals_brain_write_forbidden_v32",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = legacy.SCHEMA
    base["fingerprint"] = prior
    return base


def _finalize(plan: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, Any]:
    _check_plan(plan)
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
            "execution_plan_v32_validated": True,
            "g15_prepared_identity_replay_refinement_attribution_contiguous": True,
            "g15_exact_replay_command_fully_bound": True,
            "g15_exact_refinement_command_fully_bound": True,
            "g15_six_factor_attribution_command_fully_bound": True,
            "g15_attribution_authorization_command_fully_bound": True,
            "g15_attribution_authorization_pre_outcome": True,
            "g15_publication_blocked_until_attribution_authorized": True,
            "g15_lesson_proposals_brain_write_forbidden_v32": True,
        }
    )
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
    with _executor_context():
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
        raise HistoricalRefinementPreflightV28Error(
            "preflight v28 schema or fingerprint mismatch"
        )
    if value.get("executor_contract") != EXECUTOR_CONTRACT:
        raise HistoricalRefinementPreflightV28Error("executor contract mismatch")
    if value.get("readiness_contract") != READINESS_CONTRACT:
        raise HistoricalRefinementPreflightV28Error("readiness contract mismatch")
    if value.get("readiness_stage_contract") != STAGE_CONTRACT:
        raise HistoricalRefinementPreflightV28Error("stage contract mismatch")
    if value.get("readiness_stage_contract_fingerprint") != STAGE_CONTRACT_FINGERPRINT:
        raise HistoricalRefinementPreflightV28Error("stage fingerprint mismatch")
    for field in (
        "execution_plan_v32_validated",
        "g15_prepared_identity_replay_refinement_attribution_contiguous",
        "g15_exact_replay_command_fully_bound",
        "g15_exact_refinement_command_fully_bound",
        "g15_six_factor_attribution_command_fully_bound",
        "g15_attribution_authorization_command_fully_bound",
        "g15_attribution_authorization_pre_outcome",
        "g15_publication_blocked_until_attribution_authorized",
        "g15_lesson_proposals_brain_write_forbidden_v32",
    ):
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV28Error(
                f"mandatory field mismatch: {field}"
            )
    plan = value.get("execution_plan_snapshot")
    if not isinstance(plan, Mapping):
        raise HistoricalRefinementPreflightV28Error("exact plan snapshot is required")
    _check_plan(plan)
    if value.get("plan_fingerprint") != plan.get("fingerprint"):
        raise HistoricalRefinementPreflightV28Error("plan fingerprint mismatch")
    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("legacy_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV28Error(
            "embedded legacy preflight fingerprint mismatch"
        )
    with _executor_context():
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
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "executor_status": (receipt.get("executor_result") or {}).get("status"),
                "executor_stage": (receipt.get("executor_result") or {}).get("stage"),
                "out": str(args.out),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
