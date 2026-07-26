#!/usr/bin/env python3
"""Execute readiness-v38 with the exact validated AWS subprocess environment."""
from __future__ import annotations

import argparse
import copy
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v34 as prior
import ng_v38_aws_subprocess_environment_lock as environment_lock


@contextmanager
def _locked_environment_context(launch_environment: Mapping[str, str]) -> Iterator[None]:
    old_environment_builder = legacy_executor._command_environment

    def locked_builder() -> dict[str, str]:
        return {str(key): str(value) for key, value in launch_environment.items()}

    legacy_executor._command_environment = locked_builder
    try:
        yield
    finally:
        legacy_executor._command_environment = old_environment_builder


def execute_next(
    plan: Mapping[str, Any],
    ledger_path: Path,
    *,
    arm_receipt: Mapping[str, Any],
    aws_execution_context_revalidation: Mapping[str, Any],
    s3_source_capability_revalidation: Mapping[str, Any],
    source_spec: Mapping[str, Any],
    repository_root: Path,
    environment: Mapping[str, str] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run one stage after rebuilding its minimal AWS environment from validated lineage."""
    receipt, launch_environment = environment_lock.build_locked_environment(
        plan,
        arm_receipt,
        aws_execution_context_revalidation,
        s3_source_capability_revalidation,
        source_spec,
        repository_root,
        environment=dict(os.environ if environment is None else environment),
    )
    with _locked_environment_context(launch_environment):
        raw_result = prior.execute_next(plan, ledger_path, **kwargs)
    result = copy.deepcopy(dict(raw_result))
    result.update(
        {
            "aws_subprocess_environment_lock_fingerprint": receipt["fingerprint"],
            "aws_subprocess_environment_locked": True,
            "aws_selected_profile": receipt.get("selected_profile"),
            "aws_expected_region": receipt.get("expected_region"),
            "custom_endpoint_overrides_rejected": True,
            "secret_values_recorded": False,
        }
    )
    return result


def run_next(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Compatibility alias for versioned preflight wrappers."""
    return execute_next(*args, **kwargs)


def build_plan(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return prior.build_plan(*args, **kwargs)


def validate_plan(plan: Mapping[str, Any]) -> None:
    prior.validate_plan(plan)


def configure_stage(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return prior.configure_stage(*args, **kwargs)


def validate_ledger(ledger: Mapping[str, Any], plan: Mapping[str, Any]) -> None:
    prior.validate_ledger(ledger, plan)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--arm-receipt", type=Path, required=True)
    parser.add_argument("--aws-execution-context-revalidation", type=Path, required=True)
    parser.add_argument("--s3-source-capability-revalidation", type=Path, required=True)
    parser.add_argument("--source-spec", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--allow-fixed-outcomes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--readiness-out", type=Path)
    args = parser.parse_args()
    result = execute_next(
        legacy_executor._load_json(args.plan),
        args.ledger,
        arm_receipt=legacy_executor._load_json(args.arm_receipt),
        aws_execution_context_revalidation=legacy_executor._load_json(
            args.aws_execution_context_revalidation
        ),
        s3_source_capability_revalidation=legacy_executor._load_json(
            args.s3_source_capability_revalidation
        ),
        source_spec=legacy_executor._load_json(args.source_spec),
        repository_root=args.repository_root,
        allow_fixed_outcomes=args.allow_fixed_outcomes,
        dry_run=args.dry_run,
        readiness_out=args.readiness_out,
    )
    print(
        f"[ng_historical_refinement_executor_v35] {result['status']} "
        f"stage={result.get('stage')} aws_environment_locked=true"
    )
    return 0


PLAN_SCHEMA = prior.PLAN_SCHEMA
LEDGER_SCHEMA = prior.LEDGER_SCHEMA
SUGGESTED_ENTRYPOINTS = prior.SUGGESTED_ENTRYPOINTS
HistoricalRefinementExecutionError = prior.HistoricalRefinementExecutionError


if __name__ == "__main__":
    raise SystemExit(main())
