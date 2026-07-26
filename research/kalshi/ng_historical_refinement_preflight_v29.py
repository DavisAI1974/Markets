#!/usr/bin/env python3
"""Bind branch-guarded execution to the durable readiness-v33 plan contract."""
from __future__ import annotations

import argparse
import copy
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor_v29 as executor
import ng_historical_refinement_preflight as legacy
import ng_historical_refinement_readiness_v33 as readiness

SCHEMA = "ng_historical_refinement_preflight.v29"
EXECUTOR_CONTRACT = "ng_historical_refinement_executor_v29"
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


class HistoricalRefinementPreflightV29Error(RuntimeError):
    pass


def _check_flags(argv: Any, flags: Sequence[str], *, stage: str) -> None:
    if not isinstance(argv, list) or not all(isinstance(part, str) for part in argv):
        raise HistoricalRefinementPreflightV29Error(f"{stage}: command vector is invalid")
    for flag in flags:
        if flag not in argv:
            raise HistoricalRefinementPreflightV29Error(
                f"{stage}: command lacks required binding {flag}"
            )


def _check_plan(plan: Mapping[str, Any]) -> None:
    executor.validate_plan(plan)
    rows = [row for row in plan.get("stages") or [] if isinstance(row, Mapping)]
    keys = [str(row.get("key")) for row in rows]
    if keys != STAGE_ORDER:
        raise HistoricalRefinementPreflightV29Error(
            "embedded plan does not use readiness-v33 stage order"
        )
    by_key = {str(row.get("key")): row for row in rows}
    tail = [
        "g15_counterfactual_attribution",
        "g15_counterfactual_attribution_authorization",
        "g15_publication",
        "g15_attribution_bound_publication",
        "g15_counterfactual_lesson_gate",
    ]
    start = keys.index(tail[0])
    if keys[start : start + len(tail)] != tail:
        raise HistoricalRefinementPreflightV29Error(
            "G15 attribution authorization, publication binding, and lessons are reordered"
        )

    expected_contracts = {
        "g15_counterfactual_attribution_authorization": (
            "g15_counterfactual_attribution_authorization.json",
            ["python", "ng_g15_counterfactual_attribution_gate.py"],
        ),
        "g15_publication": (
            "g15_exact_publication_completion.json",
            ["python", "ng_g15_exact_publication_gate.py"],
        ),
        "g15_attribution_bound_publication": (
            "g15_attribution_bound_publication_gate.json",
            ["python", "ng_g15_attribution_bound_publication_gate.py"],
        ),
        "g15_counterfactual_lesson_gate": (
            "g15_counterfactual_lesson_gate.json",
            None,
        ),
    }
    for key, (output, entrypoint) in expected_contracts.items():
        row = by_key[key]
        if row.get("expected_output") != output:
            raise HistoricalRefinementPreflightV29Error(
                f"{key}: canonical artifact was substituted"
            )
        if entrypoint is not None and row.get("suggested_entrypoint") != entrypoint:
            raise HistoricalRefinementPreflightV29Error(
                f"{key}: suggested entrypoint was substituted"
            )

    _check_flags(
        by_key["g15_counterfactual_attribution_authorization"].get("argv"),
        ("--completion", "--pipeline", "--refinement-authorization", "--attribution", "--out"),
        stage="g15_counterfactual_attribution_authorization",
    )
    _check_flags(
        by_key["g15_publication"].get("argv"),
        (
            "--authorization",
            "--blind",
            "--refined",
            "--actual",
            "--blind-score",
            "--refined-score",
            "--comparison",
            "--adjudication",
            "--blind-render-rt",
            "--refined-render-rt",
            "--blind-render-png",
            "--refined-render-png",
            "--out",
        ),
        stage="g15_publication",
    )
    _check_flags(
        by_key["g15_attribution_bound_publication"].get("argv"),
        (
            "--attribution-authorization",
            "--publication",
            "--blind-score",
            "--refined-score",
            "--comparison",
            "--out",
        ),
        stage="g15_attribution_bound_publication",
    )
    _check_flags(
        by_key["g15_counterfactual_lesson_gate"].get("argv"),
        (
            "--replay",
            "--anchor",
            "--refine-stream",
            "--attribution",
            "--audit",
            "--comparison",
            "--proposals-out",
            "--adjudication-out",
            "--out",
        ),
        stage="g15_counterfactual_lesson_gate",
    )

    if by_key["g15_counterfactual_attribution_authorization"].get(
        "requires_fixed_outcomes"
    ) is not False:
        raise HistoricalRefinementPreflightV29Error(
            "G15 attribution authorization must remain outcome-blind"
        )
    for key in (
        "g15_publication",
        "g15_attribution_bound_publication",
        "g15_counterfactual_lesson_gate",
    ):
        if by_key[key].get("requires_fixed_outcomes") is not True:
            raise HistoricalRefinementPreflightV29Error(
                f"{key}: must remain behind the fixed-outcome boundary"
            )
    if by_key["g15_counterfactual_lesson_gate"].get("enabled") and not by_key[
        "g15_attribution_bound_publication"
    ].get("enabled"):
        raise HistoricalRefinementPreflightV29Error(
            "scored lessons may not be enabled before attribution-bound publication"
        )
    if by_key["g15_attribution_bound_publication"].get("enabled") and not by_key[
        "g15_publication"
    ].get("enabled"):
        raise HistoricalRefinementPreflightV29Error(
            "publication binding may not be enabled before G15 publication"
        )
    if plan.get("random_shuffle_used") is not False:
        raise HistoricalRefinementPreflightV29Error("random shuffle must remain forbidden")
    if plan.get("blind_forecasts_immutable") is not True:
        raise HistoricalRefinementPreflightV29Error("blind forecasts must remain immutable")
    if plan.get("may_update_ng_brain") is not False:
        raise HistoricalRefinementPreflightV29Error("ng_brain.json writes remain forbidden")
    if plan.get("cme_event_contracts_mode") != "SHADOW":
        raise HistoricalRefinementPreflightV29Error("CME event contracts must remain SHADOW")
    if plan.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise HistoricalRefinementPreflightV29Error("tastytrade brokerage contract changed")
    if plan.get("options_lane_started") is not False:
        raise HistoricalRefinementPreflightV29Error("options lane started without authorization")


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
        "execution_plan_v33_validated",
        "attribution_authorization_pre_outcome",
        "publication_fixed_outcome",
        "attribution_bound_publication_fixed_outcome",
        "counterfactual_lessons_fixed_outcome",
        "separate_blind_refined_score_commands_required",
        "lesson_support_locked_before_scoring",
        "lesson_brain_write_forbidden",
        "g16_outcome_access_forbidden",
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
    result["execution_plan_v33_validated"] = True
    result["attribution_authorization_pre_outcome"] = True
    result["publication_fixed_outcome"] = True
    result["attribution_bound_publication_fixed_outcome"] = True
    result["counterfactual_lessons_fixed_outcome"] = True
    result["separate_blind_refined_score_commands_required"] = True
    result["lesson_support_locked_before_scoring"] = True
    result["lesson_brain_write_forbidden"] = True
    result["g16_outcome_access_forbidden"] = True
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
        raise HistoricalRefinementPreflightV29Error(
            "preflight v29 schema or fingerprint mismatch"
        )
    if value.get("executor_contract") != EXECUTOR_CONTRACT:
        raise HistoricalRefinementPreflightV29Error("executor contract mismatch")
    if value.get("readiness_contract") != READINESS_CONTRACT:
        raise HistoricalRefinementPreflightV29Error("readiness contract mismatch")
    if value.get("readiness_stage_contract") != STAGE_CONTRACT:
        raise HistoricalRefinementPreflightV29Error("stage contract mismatch")
    if value.get("readiness_stage_contract_fingerprint") != STAGE_CONTRACT_FINGERPRINT:
        raise HistoricalRefinementPreflightV29Error("stage fingerprint mismatch")
    for field in (
        "execution_plan_v33_validated",
        "attribution_authorization_pre_outcome",
        "publication_fixed_outcome",
        "attribution_bound_publication_fixed_outcome",
        "counterfactual_lessons_fixed_outcome",
        "separate_blind_refined_score_commands_required",
        "lesson_support_locked_before_scoring",
        "lesson_brain_write_forbidden",
        "g16_outcome_access_forbidden",
    ):
        if value.get(field) is not True:
            raise HistoricalRefinementPreflightV29Error(
                f"mandatory field mismatch: {field}"
            )
    plan = value.get("execution_plan_snapshot")
    if not isinstance(plan, Mapping):
        raise HistoricalRefinementPreflightV29Error("exact plan snapshot is required")
    _check_plan(plan)
    if value.get("plan_fingerprint") != plan.get("fingerprint"):
        raise HistoricalRefinementPreflightV29Error("plan fingerprint mismatch")
    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("legacy_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV29Error(
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
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
