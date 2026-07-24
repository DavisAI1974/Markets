#!/usr/bin/env python3
"""Run readiness-v4 historical refinement behind live pre/post Git alignment.

This adapter closes the remaining branch-preflight bypass: the original preflight
wrapper was still bound to the legacy executor/readiness contract at function-
definition time. Version 2 always validates and executes a full readiness-v4 plan,
embeds that exact plan in the receipt, and preserves the branch/HEAD immutability
checks around the selected stage.
"""
from __future__ import annotations

import argparse
import copy
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor_v2 as executor
import ng_historical_refinement_preflight as legacy
import ng_historical_refinement_readiness_v4 as readiness

SCHEMA = "ng_historical_refinement_preflight.v2"
EXECUTOR_CONTRACT = "ng_historical_refinement_executor_v2"
READINESS_CONTRACT = readiness.SCHEMA
LEGACY_SCHEMA = legacy.SCHEMA


class HistoricalRefinementPreflightV2Error(RuntimeError):
    """Raised when the branch-guarded run is not bound to readiness v4."""


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
def _v4_context() -> Iterator[None]:
    old_executor = legacy.executor
    legacy.executor = executor
    try:
        yield
    finally:
        legacy.executor = old_executor


def _base_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(dict(value))
    legacy_fingerprint = base.pop("legacy_preflight_fingerprint", None)
    for field in (
        "executor_contract",
        "readiness_contract",
        "readiness_stage_contract",
        "readiness_stage_contract_fingerprint",
        "execution_plan_snapshot",
        "execution_plan_v4_validated",
        "lock_first_g15_scoring_required",
        "counterfactual_g16_lineage_required",
    ):
        base.pop(field, None)
    base.pop("fingerprint", None)
    base["schema"] = LEGACY_SCHEMA
    base["fingerprint"] = legacy_fingerprint
    return base


def _finalize(plan: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, Any]:
    with _v4_context():
        executor.validate_plan(plan)
        legacy.validate_receipt(base)
    result = copy.deepcopy(dict(base))
    result["schema"] = SCHEMA
    result["legacy_preflight_fingerprint"] = base["fingerprint"]
    result["executor_contract"] = EXECUTOR_CONTRACT
    result["readiness_contract"] = READINESS_CONTRACT
    result["readiness_stage_contract"] = copy.deepcopy(STAGE_CONTRACT)
    result["readiness_stage_contract_fingerprint"] = STAGE_CONTRACT_FINGERPRINT
    result["execution_plan_snapshot"] = copy.deepcopy(dict(plan))
    result["execution_plan_v4_validated"] = True
    result["lock_first_g15_scoring_required"] = True
    result["counterfactual_g16_lineage_required"] = True
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
    """Execute one readiness-v4 stage with live branch alignment on both sides."""

    executor.validate_plan(plan)
    runner = executor.run_next if executor_runner is None else executor_runner
    with _v4_context():
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
        raise HistoricalRefinementPreflightV2Error("preflight v2 schema or fingerprint mismatch")
    if value.get("executor_contract") != EXECUTOR_CONTRACT:
        raise HistoricalRefinementPreflightV2Error("preflight v2 executor contract mismatch")
    if value.get("readiness_contract") != READINESS_CONTRACT:
        raise HistoricalRefinementPreflightV2Error("preflight v2 readiness contract mismatch")
    if value.get("readiness_stage_contract") != STAGE_CONTRACT:
        raise HistoricalRefinementPreflightV2Error("preflight v2 stage contract mismatch")
    if value.get("readiness_stage_contract_fingerprint") != STAGE_CONTRACT_FINGERPRINT:
        raise HistoricalRefinementPreflightV2Error("preflight v2 stage contract fingerprint mismatch")
    if value.get("execution_plan_v4_validated") is not True:
        raise HistoricalRefinementPreflightV2Error("preflight v2 must record v4 plan validation")
    if value.get("lock_first_g15_scoring_required") is not True:
        raise HistoricalRefinementPreflightV2Error("G15 lock-first scoring must remain mandatory")
    if value.get("counterfactual_g16_lineage_required") is not True:
        raise HistoricalRefinementPreflightV2Error("G16 counterfactual lineage must remain mandatory")

    plan = value.get("execution_plan_snapshot")
    if not isinstance(plan, Mapping):
        raise HistoricalRefinementPreflightV2Error("preflight v2 requires the exact execution plan snapshot")
    with _v4_context():
        executor.validate_plan(plan)
    if value.get("plan_fingerprint") != plan.get("fingerprint"):
        raise HistoricalRefinementPreflightV2Error("receipt plan fingerprint does not match embedded v4 plan")
    stage_keys = [row.get("key") for row in plan.get("stages") or [] if isinstance(row, Mapping)]
    if stage_keys != STAGE_ORDER:
        raise HistoricalRefinementPreflightV2Error("embedded plan does not use the readiness-v4 stage order")

    executor_result = value.get("executor_result")
    if isinstance(executor_result, Mapping):
        selected_stage = executor_result.get("stage")
        if selected_stage is not None and selected_stage not in STAGE_ORDER:
            raise HistoricalRefinementPreflightV2Error("executor selected a stage outside readiness v4")

    base = _base_receipt(receipt)
    if base.get("fingerprint") != value.get("legacy_preflight_fingerprint"):
        raise HistoricalRefinementPreflightV2Error("embedded legacy preflight fingerprint mismatch")
    with _v4_context():
        legacy.validate_receipt(base)


def selftest() -> int:
    import tempfile

    class FakeGateBuilder:
        def __init__(self, root: Path) -> None:
            self.root = root

        def __call__(self, repository_path: Path, **kwargs: Any) -> dict[str, Any]:
            gate = {
                "schema": branch_alignment.SCHEMA,
                "market": "NG",
                "status": "ALIGNED",
                "observed_at": "2026-07-24T04:00:00Z",
                "repository_root": str(self.root),
                "expected_repository": branch_alignment.DEFAULT_REPOSITORY,
                "observed_remote_repository": branch_alignment.DEFAULT_REPOSITORY,
                "remote": branch_alignment.DEFAULT_REMOTE,
                "remote_url": "git@github.com:DavisAI1974/Markets.git",
                "expected_branch": branch_alignment.DEFAULT_BRANCH,
                "observed_branch": branch_alignment.DEFAULT_BRANCH,
                "detached_head": False,
                "head_sha": "1" * 40,
                "remote_ref": f"refs/remotes/origin/{branch_alignment.DEFAULT_BRANCH}",
                "remote_ref_available": True,
                "remote_sha": "1" * 40,
                "ahead_by": 0,
                "behind_by": 0,
                "require_remote_match": True,
                "allow_local_ahead": False,
                "allowed_dirty_prefixes": [],
                "allowed_dirty_entries": [],
                "blocked_dirty_entries": [],
                "blockers": [],
                "stand_downs": [],
                "remote_fetch_performed": False,
                "remote_presence_inferred": False,
                "random_shuffle_used": False,
                "one_signal_authority_preserved": True,
                "blind_forecasts_immutable": True,
                "may_change_posterior": False,
                "may_update_ng_brain": False,
                "execution_authority": False,
                "cme_event_contracts_mode": "SHADOW",
                "brokerage_contract": "tastytrade_not_ibkr",
                "options_lane_started": False,
                "next_permitted_stage": "HISTORICAL_REFINEMENT_EXECUTOR_PREFLIGHT",
            }
            gate["fingerprint"] = branch_alignment._fingerprint(gate)
            return gate

    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        work = root / "research" / "kalshi"
        artifacts = work / "renders"
        work.mkdir(parents=True)
        artifacts.mkdir()
        for relative in ("forecasts/grp15.json", "forecasts/grp16.json", "knowledge/ng_brain.json"):
            path = work / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
        plan = executor.build_plan(artifacts, work)
        result = execute_preflight(
            plan,
            root / "ledger.json",
            dry_run=True,
            gate_builder=FakeGateBuilder(root),
            executor_runner=lambda *args, **kwargs: {"status": "CONFIGURATION_REQUIRED", "stage": "corpus_coverage"},
        )
        validate_receipt(result)
        assert result["status"] == "PREFLIGHT_PASSED"
        assert result["execution_plan_snapshot"]["stages"][6]["key"] == "g15_counterfactual_scoring_lock"
    print("[ng_historical_refinement_preflight_v2] selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
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
    if args.selftest:
        return selftest()
    if not args.plan or not args.ledger or not args.out:
        parser.error("--plan, --ledger, and --out are required unless --selftest is used")
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
    if receipt["status"] not in {"PREFLIGHT_PASSED", "PREFLIGHT_PASSED_WITH_STAND_DOWNS"}:
        return 2
    return 0 if summary["executor_status"] in legacy.EXECUTOR_OK_STATUSES else 2


if __name__ == "__main__":
    raise SystemExit(main())
