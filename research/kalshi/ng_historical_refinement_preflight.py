#!/usr/bin/env python3
"""Run the guarded NG historical-refinement executor behind a live Git preflight.

The wrapper rebuilds the branch-alignment gate immediately before and after the
selected historical stage. It refuses to call the executor when the checkout is
on the wrong branch, bound to the wrong repository, dirty outside explicitly
allowed artifact paths, behind or diverged from the remote ref, or locally ahead
without explicit permission. It also rejects any HEAD movement during the stage.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor as executor

SCHEMA = "ng_historical_refinement_preflight.v1"
PASS_STATUSES = {"ALIGNED", "ALIGNED_WITH_STAND_DOWNS"}
EXECUTOR_OK_STATUSES = {
    "CHAIN_COMPLETE",
    "CONFIGURATION_REQUIRED",
    "DRY_RUN",
    "ADVANCED",
    "ADVANCED_WITH_STAND_DOWNS",
    "STOOD_DOWN",
}


class HistoricalRefinementPreflightError(RuntimeError):
    """Raised when branch state or wrapper provenance violates the contract."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HistoricalRefinementPreflightError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise HistoricalRefinementPreflightError(f"JSON artifact must be an object: {path}")
    return value


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _validate_live_gate(plan: Mapping[str, Any], gate: Mapping[str, Any]) -> None:
    executor.validate_plan(plan)
    branch_alignment.validate_gate(gate)
    repository_root = Path(str(gate.get("repository_root") or "")).resolve(strict=False)
    working_directory = Path(str(plan.get("working_directory") or "")).resolve(strict=False)
    if not _is_within(working_directory, repository_root):
        raise HistoricalRefinementPreflightError(
            f"plan working directory is outside the aligned repository: {working_directory}"
        )
    if gate.get("status") not in PASS_STATUSES:
        return
    if gate.get("next_permitted_stage") != "HISTORICAL_REFINEMENT_EXECUTOR_PREFLIGHT":
        raise HistoricalRefinementPreflightError("aligned gate does not authorize executor preflight")
    if gate.get("blocked_dirty_entries"):
        raise HistoricalRefinementPreflightError("aligned gate contains blocked dirty entries")


def _build_gate(
    plan: Mapping[str, Any],
    *,
    expected_branch: str,
    expected_repository: str,
    remote: str,
    allowed_dirty_prefixes: Sequence[str],
    require_remote_match: bool,
    allow_local_ahead: bool,
    gate_builder: Callable[..., Mapping[str, Any]],
    branch_runner: Callable[..., Any],
) -> dict[str, Any]:
    gate = dict(
        gate_builder(
            Path(str(plan["working_directory"])),
            expected_branch=expected_branch,
            expected_repository=expected_repository,
            remote=remote,
            allowed_dirty_prefixes=tuple(allowed_dirty_prefixes),
            require_remote_match=require_remote_match,
            allow_local_ahead=allow_local_ahead,
            runner=branch_runner,
        )
    )
    _validate_live_gate(plan, gate)
    if gate.get("expected_branch") != expected_branch:
        raise HistoricalRefinementPreflightError("branch gate ignored the requested branch")
    if gate.get("expected_repository") != expected_repository:
        raise HistoricalRefinementPreflightError("branch gate ignored the requested repository")
    if gate.get("remote") != remote:
        raise HistoricalRefinementPreflightError("branch gate ignored the requested remote")
    if gate.get("require_remote_match") is not bool(require_remote_match):
        raise HistoricalRefinementPreflightError("branch gate remote-match policy mismatch")
    if gate.get("allow_local_ahead") is not bool(allow_local_ahead):
        raise HistoricalRefinementPreflightError("branch gate local-ahead policy mismatch")
    requested_prefixes = {
        branch_alignment._normalise_prefix(value)
        for value in allowed_dirty_prefixes
        if branch_alignment._normalise_prefix(value)
    }
    if set(gate.get("allowed_dirty_prefixes") or []) != requested_prefixes:
        raise HistoricalRefinementPreflightError("branch gate dirty-prefix policy mismatch")
    return gate


def _receipt_base(
    plan: Mapping[str, Any],
    before: Mapping[str, Any],
    *,
    allow_fixed_outcomes: bool,
    dry_run: bool,
    allowed_dirty_prefixes: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "market": "NG",
        "plan_fingerprint": plan["fingerprint"],
        "working_directory": str(Path(str(plan["working_directory"])).resolve(strict=False)),
        "alignment_before": copy.deepcopy(dict(before)),
        "alignment_after": None,
        "executor_called": False,
        "executor_result": None,
        "fixed_outcomes_explicitly_allowed": bool(allow_fixed_outcomes),
        "dry_run": bool(dry_run),
        "allowed_dirty_prefixes": sorted(set(allowed_dirty_prefixes)),
        "head_immutable_during_execution": None,
        "alignment_identity_immutable_during_execution": None,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }


def _finalize_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(receipt))
    result.pop("fingerprint", None)
    result["fingerprint"] = _fingerprint(result)
    validate_receipt(result)
    return result


def _alignment_identity(gate: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        gate.get("repository_root"),
        gate.get("expected_repository"),
        gate.get("observed_remote_repository"),
        gate.get("remote_url"),
        gate.get("remote"),
        gate.get("remote_ref"),
        gate.get("expected_branch"),
        gate.get("observed_branch"),
    )


def execute_preflight(
    plan: Mapping[str, Any],
    ledger_path: Path,
    *,
    expected_branch: str = branch_alignment.DEFAULT_BRANCH,
    expected_repository: str = branch_alignment.DEFAULT_REPOSITORY,
    remote: str = branch_alignment.DEFAULT_REMOTE,
    allowed_dirty_prefixes: Sequence[str] = (),
    require_remote_match: bool = True,
    allow_local_ahead: bool = False,
    allow_fixed_outcomes: bool = False,
    dry_run: bool = False,
    readiness_out: Path | None = None,
    validator_overrides: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
    command_runner: Callable[..., Any] = subprocess.run,
    branch_runner: Callable[..., Any] = subprocess.run,
    gate_builder: Callable[..., Mapping[str, Any]] = branch_alignment.build_gate,
    executor_runner: Callable[..., Mapping[str, Any]] = executor.execute_next,
) -> dict[str, Any]:
    """Run one executor stage only when live pre/post branch alignment remains valid."""

    executor.validate_plan(plan)
    before = _build_gate(
        plan,
        expected_branch=expected_branch,
        expected_repository=expected_repository,
        remote=remote,
        allowed_dirty_prefixes=allowed_dirty_prefixes,
        require_remote_match=require_remote_match,
        allow_local_ahead=allow_local_ahead,
        gate_builder=gate_builder,
        branch_runner=branch_runner,
    )
    receipt = _receipt_base(
        plan,
        before,
        allow_fixed_outcomes=allow_fixed_outcomes,
        dry_run=dry_run,
        allowed_dirty_prefixes=allowed_dirty_prefixes,
    )
    if before["status"] not in PASS_STATUSES:
        receipt["status"] = "BRANCH_ALIGNMENT_BLOCKED"
        receipt["blockers"] = list(before.get("blockers") or [])
        receipt["stand_downs"] = list(before.get("stand_downs") or [])
        return _finalize_receipt(receipt)

    executor_result = dict(
        executor_runner(
            plan,
            ledger_path,
            allow_fixed_outcomes=allow_fixed_outcomes,
            dry_run=dry_run,
            readiness_out=readiness_out,
            validator_overrides=validator_overrides,
            command_runner=command_runner,
        )
    )
    receipt["executor_called"] = True
    receipt["executor_result"] = executor_result

    after = _build_gate(
        plan,
        expected_branch=expected_branch,
        expected_repository=expected_repository,
        remote=remote,
        allowed_dirty_prefixes=allowed_dirty_prefixes,
        require_remote_match=require_remote_match,
        allow_local_ahead=allow_local_ahead,
        gate_builder=gate_builder,
        branch_runner=branch_runner,
    )
    receipt["alignment_after"] = after
    same_head = before.get("head_sha") == after.get("head_sha")
    same_identity = _alignment_identity(before) == _alignment_identity(after)
    receipt["head_immutable_during_execution"] = same_head
    receipt["alignment_identity_immutable_during_execution"] = same_identity

    combined_stand_downs = sorted(
        set(before.get("stand_downs") or []) | set(after.get("stand_downs") or [])
    )
    receipt["stand_downs"] = combined_stand_downs
    receipt["blockers"] = list(after.get("blockers") or [])

    if after["status"] not in PASS_STATUSES:
        receipt["status"] = "POST_EXECUTION_ALIGNMENT_BLOCKED"
    elif not same_identity:
        receipt["status"] = "REPOSITORY_ALIGNMENT_CHANGED"
        receipt["blockers"] = ["REPOSITORY_ALIGNMENT_IDENTITY_CHANGED"]
    elif not same_head:
        receipt["status"] = "REPOSITORY_HEAD_CHANGED"
        receipt["blockers"] = [
            f"HEAD_CHANGED:{before.get('head_sha')}->{after.get('head_sha')}"
        ]
    elif combined_stand_downs:
        receipt["status"] = "PREFLIGHT_PASSED_WITH_STAND_DOWNS"
    else:
        receipt["status"] = "PREFLIGHT_PASSED"
    return _finalize_receipt(receipt)


def validate_receipt(receipt: Mapping[str, Any]) -> None:
    value = copy.deepcopy(dict(receipt))
    observed = value.pop("fingerprint", None)
    if value.get("schema") != SCHEMA or observed != _fingerprint(value):
        raise HistoricalRefinementPreflightError("preflight receipt schema or fingerprint mismatch")
    if value.get("market") != "NG":
        raise HistoricalRefinementPreflightError("preflight receipt must be for NG")
    for field in (
        "random_shuffle_used",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise HistoricalRefinementPreflightError(f"preflight receipt must keep {field}=false")
    if value.get("one_signal_authority_preserved") is not True:
        raise HistoricalRefinementPreflightError("preflight must preserve one signal authority")
    if value.get("blind_forecasts_immutable") is not True:
        raise HistoricalRefinementPreflightError("preflight must preserve blind forecasts")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise HistoricalRefinementPreflightError("CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise HistoricalRefinementPreflightError("brokerage contract must remain tastytrade, not IBKR")

    before = value.get("alignment_before")
    after = value.get("alignment_after")
    if not isinstance(before, Mapping):
        raise HistoricalRefinementPreflightError("receipt requires a pre-execution alignment gate")
    branch_alignment.validate_gate(before)
    status = value.get("status")
    executor_called = value.get("executor_called")
    executor_result = value.get("executor_result")

    if status == "BRANCH_ALIGNMENT_BLOCKED":
        if before.get("status") != "BLOCKED" or after is not None or executor_called is not False or executor_result is not None:
            raise HistoricalRefinementPreflightError("blocked preflight receipt is inconsistent")
        if value.get("head_immutable_during_execution") is not None:
            raise HistoricalRefinementPreflightError("blocked preflight cannot claim a post-execution HEAD check")
        if value.get("alignment_identity_immutable_during_execution") is not None:
            raise HistoricalRefinementPreflightError("blocked preflight cannot claim an identity check")
        return

    if before.get("status") not in PASS_STATUSES:
        raise HistoricalRefinementPreflightError("executor was called without an aligned preflight")
    if not isinstance(after, Mapping):
        raise HistoricalRefinementPreflightError("executed preflight requires a post-execution gate")
    branch_alignment.validate_gate(after)
    if executor_called is not True or not isinstance(executor_result, Mapping):
        raise HistoricalRefinementPreflightError("executed preflight requires an executor result")
    if not isinstance(executor_result.get("status"), str) or not executor_result.get("status"):
        raise HistoricalRefinementPreflightError("executor result requires a status")

    if status == "POST_EXECUTION_ALIGNMENT_BLOCKED":
        if after.get("status") != "BLOCKED":
            raise HistoricalRefinementPreflightError("post-execution blocked receipt requires a blocked after gate")
    elif status == "REPOSITORY_ALIGNMENT_CHANGED":
        if after.get("status") not in PASS_STATUSES or _alignment_identity(before) == _alignment_identity(after):
            raise HistoricalRefinementPreflightError("repository-identity change receipt is inconsistent")
        if value.get("alignment_identity_immutable_during_execution") is not False:
            raise HistoricalRefinementPreflightError("identity-change receipt must record immutability failure")
    elif status == "REPOSITORY_HEAD_CHANGED":
        if after.get("status") not in PASS_STATUSES or before.get("head_sha") == after.get("head_sha"):
            raise HistoricalRefinementPreflightError("HEAD-change receipt is inconsistent")
        if value.get("head_immutable_during_execution") is not False:
            raise HistoricalRefinementPreflightError("HEAD-change receipt must record immutability failure")
    elif status in {"PREFLIGHT_PASSED", "PREFLIGHT_PASSED_WITH_STAND_DOWNS"}:
        if after.get("status") not in PASS_STATUSES:
            raise HistoricalRefinementPreflightError("passed preflight requires an aligned after gate")
        if _alignment_identity(before) != _alignment_identity(after) or value.get("alignment_identity_immutable_during_execution") is not True:
            raise HistoricalRefinementPreflightError("passed preflight requires unchanged repository identity")
        if before.get("head_sha") != after.get("head_sha") or value.get("head_immutable_during_execution") is not True:
            raise HistoricalRefinementPreflightError("passed preflight requires an unchanged HEAD")
        stand_downs = value.get("stand_downs")
        if not isinstance(stand_downs, list):
            raise HistoricalRefinementPreflightError("stand_downs must be a list")
        if status == "PREFLIGHT_PASSED" and stand_downs:
            raise HistoricalRefinementPreflightError("fully passed preflight cannot contain stand-downs")
        if status == "PREFLIGHT_PASSED_WITH_STAND_DOWNS" and not stand_downs:
            raise HistoricalRefinementPreflightError("stand-down status requires stand-downs")
    else:
        raise HistoricalRefinementPreflightError(f"unsupported preflight status: {status!r}")


def selftest() -> int:
    class FakeGateBuilder:
        def __init__(self, root: Path) -> None:
            self.root = root

        def __call__(self, repository_path: Path, **kwargs: Any) -> dict[str, Any]:
            gate = {
                "schema": branch_alignment.SCHEMA,
                "market": "NG",
                "status": "ALIGNED",
                "observed_at": "2026-07-23T17:00:00Z",
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

    import tempfile

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
            executor_runner=lambda *args, **kwargs: {"status": "CONFIGURATION_REQUIRED"},
        )
        validate_receipt(result)
        assert result["status"] == "PREFLIGHT_PASSED"
    print("[ng_historical_refinement_preflight] selftest PASS")
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
    plan = _load_json(Path(args.plan))
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
    _atomic_json(Path(args.out), receipt)
    summary = {
        "status": receipt["status"],
        "executor_status": (receipt.get("executor_result") or {}).get("status"),
        "fingerprint": receipt["fingerprint"],
        "blockers": receipt.get("blockers") or [],
        "stand_downs": receipt.get("stand_downs") or [],
    }
    print(json.dumps(summary, sort_keys=True))
    if receipt["status"] not in {"PREFLIGHT_PASSED", "PREFLIGHT_PASSED_WITH_STAND_DOWNS"}:
        return 2
    return 0 if summary["executor_status"] in EXECUTOR_OK_STATUSES else 2


if __name__ == "__main__":
    raise SystemExit(main())
