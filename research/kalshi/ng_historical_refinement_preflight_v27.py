#!/usr/bin/env python3
"""Bind branch-guarded execution to prepared-normalized-identity readiness v31."""
from __future__ import annotations

import argparse
import copy
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor_v27 as executor
import ng_historical_refinement_preflight as legacy
import ng_historical_refinement_readiness_v31 as readiness

SCHEMA = "ng_historical_refinement_preflight.v27"
EXECUTOR_CONTRACT = "ng_historical_refinement_executor_v27"
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


class HistoricalRefinementPreflightV27Error(RuntimeError):
    pass


def _check_plan(plan: Mapping[str, Any]) -> None:
    executor.validate_plan(plan)
    rows = [row for row in plan.get("stages") or [] if isinstance(row, Mapping)]
    keys = [str(row.get("key")) for row in rows]
    if keys != STAGE_ORDER:
        raise HistoricalRefinementPreflightV27Error(
            "embedded plan does not use readiness-v31 stage order"
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
    )
    try:
        positions = {key: keys.index(key) for key in required}
    except ValueError as error:
        raise HistoricalRefinementPreflightV27Error(
            "required prepared-identity historical stage is missing"
        ) from error
    if [positions[key] for key in required] != sorted(positions[key] for key in required):
        raise HistoricalRefinementPreflightV27Error(
            "prepared normalized identity is not ordered before G15 replay"
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
        "corpus_s3_latest_version_resolution": (
            "ng_corpus_s3_paginated_latest_version_resolution_attestation.json",
            None,
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
    }
    for key, (output, entrypoint) in expected_contracts.items():
        row = by_key[key]
        if row.get("expected_output") != output:
            raise HistoricalRefinementPreflightV27Error(
                f"{key}: canonical artifact was substituted"
            )
        if entrypoint is not None and row.get("suggested_entrypoint") != entrypoint:
            raise HistoricalRefinementPreflightV27Error(
                f"{key}: suggested entrypoint was substituted"
            )
    guard = by_key["g15_prepared_normalized_identity"]
    argv = guard.get("argv", [])
    if argv[:3] != [
        "python",
        "ng_g15_prepared_normalized_identity_guard.py",
        "build",
    ]:
        raise HistoricalRefinementPreflightV27Error(
            "prepared normalized identity command was substituted"
        )
    for flag in ("--bridge", "--prepared-index", "--out"):
        if flag not in argv:
            raise HistoricalRefinementPreflightV27Error(
                f"prepared normalized identity command lacks {flag}"
            )
    if not (
        positions["replay_catalog_export"]
        < positions["broad_corpus_scope"]
        < positions["broad_corpus_exact_overlap"]
        < positions["broad_corpus_exact_partition"]
        < positions["g15_prepared_normalized_identity"]
        < positions["g15_exact_replay"]
    ):
        raise HistoricalRefinementPreflightV27Error(
            "prepared normalized identity must follow exact broad alignment and precede G15 replay"
        )
    if positions["g15_prepared_normalized_identity"] + 1 != positions["g15_exact_replay"]:
        raise HistoricalRefinementPreflightV27Error(
            "prepared normalized identity must remain directly before G15 replay"
        )
    for key in required[:-1]:
        if by_key[key].get("requires_fixed_outcomes") is not False:
            raise HistoricalRefinementPreflightV27Error(f"{key} must remain pre-outcome")


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
        "execution_plan_v31_validated",
        "prepared_normalized_identity_required",
        "prepared_normalized_identity_pre_outcome",
        "prepared_identity_follows_exact_broad_alignment",
        "prepared_identity_precedes_g15_replay",
        "prepared_identity_directly_precedes_g15_replay",
        "prepared_identity_command_bound_to_bridge_index_and_output",
        "prepared_publishers_explicit_and_positive_required_v31",
        "prepared_rows_exact_manifest_identity_required_v31",
        "prepared_event_time_bounds_and_chronology_required_v31",
        "prepared_definitions_before_trade_and_mbo_required_v31",
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
    result["schema"] = SCHEMA
    result["legacy_preflight_fingerprint"] = base["fingerprint"]
    result["executor_contract"] = EXECUTOR_CONTRACT
    result["readiness_contract"] = READINESS_CONTRACT
    result["readiness_stage_contract"] = copy.deepcopy(STAGE_CONTRACT)
    result["readiness_stage_contract_fingerprint"] = STAGE_CONTRACT_FINGERPRINT
    result["execution_plan_snapshot"] = copy.deepcopy(dict(plan))
    result["execution_plan_v31_validated"] = True
    result["prepared_normalized_identity_required"] = True
    result["prepared_normalized_identity_pre_outcome"] = True
    result["prepared_identity_follows_exact_broad_alignment"] = True
    result["prepared_identity_precedes_g15_replay"] = True
    result["prepared_identity_directly_precedes_g15_replay"] = True
    result["prepared_identity_command_bound_to_bridge_index_and_output"] = True
    result["prepared_publishers_explicit_and_positive_required_v31"] = True
    result["prepared_rows_exact_manifest_identity_required_v31"] = True
    result["prepared_event_time_bounds_and_chronology_required_v31"] = True
    result["prepared_definitions_before_trade_and_mbo_required_v31"] = True
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
        raise HistoricalRefinementPreflightV27Error(
            "preflight v27 schema or fingerprint mismatch"
        )
    if value.get("executor_contract") != EXECUTOR_CONTRACT:
        raise HistoricalRefinementPreflightV27Error("executor contract mismatch")
    if value.get("readiness_contract") != READINESS_CONTRACT:
        raise HistoricalRefinementPreflightV27Error("readiness contract mismatch")
    if value.get("readiness_stage_contract") != STAGE_CONTRACT:
        raise HistoricalRefinementPreflightV27Error("stage contract mismatch")
    if value.get("readiness_stage_contract_fingerprint") != STAGE_CONTRACT_FINGERPRINT:
        raise HistoricalRefinementPreflightV27Error("stage fingerprint mismatch")
    for field in (
        "execution_plan_v31_validated",
        "prepared_normalized_identity_required",
        "prepared_normalized_identity_pre_outcome",
        "prepared_identity_follows_exact_broad_alignment",
        "prepared_identity_precedes_g15_replay",
        "prepared_identity_directly_precedes_g15_replay",
        "prepared_identity_command_bound_to_bridge_index_and_output",
        "prepared_publishers_explicit_and_positive_required_v31",
        "prepared_rows_exact_manifest_identity_required_v31",
        "prepared_event_time_bounds_and_chronology_required_v31",
        "prepared_definitions_before_trade_and_mbo_required_v31",
    ):
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV27Error(
                f"mandatory field mismatch: {field}"
            )
    plan = value.get("execution_plan_snapshot")
    if not isinstance(plan, Mapping):
        raise HistoricalRefinementPreflightV27Error("exact plan snapshot is required")
    _check_plan(plan)
    if value.get("plan_fingerprint") != plan.get("fingerprint"):
        raise HistoricalRefinementPreflightV27Error("plan fingerprint mismatch")
    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("legacy_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV27Error(
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
