#!/usr/bin/env python3
"""Fail-closed Git branch and worktree alignment gate for NG historical refinement.

The gate never fetches, rebases, merges, resets, or modifies the repository. It only
records the locally observed Git state and refuses to authorize historical-refinement
execution when the checkout is detached, on the wrong branch, dirty outside explicitly
allowed artifact paths, behind/diverged from the configured remote ref, or bound to the
wrong GitHub repository.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

SCHEMA = "ng_branch_alignment_gate.v1"
DEFAULT_BRANCH = "chatgpt/ng-forecaster-s103-audit"
DEFAULT_REPOSITORY = "DavisAI1974/Markets"
DEFAULT_REMOTE = "origin"


class BranchAlignmentError(RuntimeError):
    """Raised when the Git checkout cannot satisfy the alignment contract."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _run_git(
    repo_root: Path,
    args: Sequence[str],
    *,
    runner: Callable[..., Any] = subprocess.run,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(repo_root), *args]
    result = runner(
        command,
        capture_output=True,
        text=True,
        shell=False,
        check=False,
    )
    returncode = int(getattr(result, "returncode", 1))
    if returncode != 0 and not allow_failure:
        stderr = str(getattr(result, "stderr", "") or "").strip()
        raise BranchAlignmentError(f"git {' '.join(args)} failed ({returncode}): {stderr}")
    return result


def _stdout(result: Any) -> str:
    return str(getattr(result, "stdout", "") or "").strip()


def _stdout_preserve_leading(result: Any) -> str:
    return str(getattr(result, "stdout", "") or "").rstrip("\r\n")


def _repo_full_name_from_url(url: str) -> str | None:
    value = url.strip()
    if not value:
        return None
    value = re.sub(r"\.git/?$", "", value)
    patterns = (
        r"^https?://[^/]+/([^/]+/[^/]+)$",
        r"^ssh://git@[^/]+/([^/]+/[^/]+)$",
        r"^git@[^:]+:([^/]+/[^/]+)$",
        r"^git://[^/]+/([^/]+/[^/]+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, value)
        if match:
            return match.group(1)
    return None


def _normalise_prefix(prefix: str) -> str:
    value = prefix.replace("\\", "/").strip()
    while value.startswith("./"):
        value = value[2:]
    return value.rstrip("/")


def _path_allowed(path: str, prefixes: Sequence[str]) -> bool:
    candidate = path.replace("\\", "/").lstrip("./")
    for raw_prefix in prefixes:
        prefix = _normalise_prefix(raw_prefix)
        if not prefix:
            continue
        if candidate == prefix or candidate.startswith(prefix + "/"):
            return True
    return False


def _parse_status(text: str, allowed_dirty_prefixes: Sequence[str]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    allowed: list[dict[str, str]] = []
    blocked: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        if not raw_line:
            continue
        if len(raw_line) < 4 or raw_line[2] != " ":
            raise BranchAlignmentError(f"malformed git status line: {raw_line!r}")
        code = raw_line[:2]
        path_text = raw_line[3:]
        # Porcelain v1 rename/copy output is "old -> new". Both paths must be allowed.
        paths = [part.strip() for part in path_text.split(" -> ")]
        row = {"status": code, "path": path_text}
        if all(_path_allowed(path, allowed_dirty_prefixes) for path in paths):
            allowed.append(row)
        else:
            blocked.append(row)
    return allowed, blocked


def _parse_ahead_behind(text: str) -> tuple[int, int]:
    parts = text.replace("\t", " ").split()
    if len(parts) != 2:
        raise BranchAlignmentError(f"malformed ahead/behind count: {text!r}")
    try:
        ahead, behind = (int(parts[0]), int(parts[1]))
    except ValueError as error:
        raise BranchAlignmentError(f"malformed ahead/behind count: {text!r}") from error
    if ahead < 0 or behind < 0:
        raise BranchAlignmentError("ahead/behind counts cannot be negative")
    return ahead, behind


def build_gate(
    repository_path: Path,
    *,
    expected_branch: str = DEFAULT_BRANCH,
    expected_repository: str = DEFAULT_REPOSITORY,
    remote: str = DEFAULT_REMOTE,
    allowed_dirty_prefixes: Sequence[str] = (),
    require_remote_match: bool = True,
    allow_local_ahead: bool = False,
    observed_at: str | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    repository_path = repository_path.resolve(strict=False)
    if not expected_branch or not expected_repository or not remote:
        raise BranchAlignmentError("expected branch, repository, and remote are required")

    top_level_result = _run_git(repository_path, ["rev-parse", "--show-toplevel"], runner=runner)
    top_level = Path(_stdout(top_level_result)).resolve(strict=False)
    branch_result = _run_git(
        top_level,
        ["symbolic-ref", "--quiet", "--short", "HEAD"],
        runner=runner,
        allow_failure=True,
    )
    current_branch = _stdout(branch_result) if int(getattr(branch_result, "returncode", 1)) == 0 else None
    detached = current_branch is None

    head_sha = _stdout(_run_git(top_level, ["rev-parse", "HEAD"], runner=runner))
    if not re.fullmatch(r"[0-9a-fA-F]{40}", head_sha):
        raise BranchAlignmentError("HEAD is not a full 40-character commit SHA")

    remote_url_result = _run_git(
        top_level,
        ["remote", "get-url", remote],
        runner=runner,
        allow_failure=True,
    )
    remote_url = _stdout(remote_url_result) if int(getattr(remote_url_result, "returncode", 1)) == 0 else None
    remote_repository = _repo_full_name_from_url(remote_url or "")

    status_text = _stdout_preserve_leading(
        _run_git(
            top_level,
            ["status", "--porcelain=v1", "--untracked-files=all"],
            runner=runner,
        )
    )
    allowed_dirty, blocked_dirty = _parse_status(status_text, allowed_dirty_prefixes)

    remote_ref = f"refs/remotes/{remote}/{expected_branch}"
    remote_sha_result = _run_git(
        top_level,
        ["rev-parse", "--verify", remote_ref],
        runner=runner,
        allow_failure=True,
    )
    remote_ref_available = int(getattr(remote_sha_result, "returncode", 1)) == 0
    remote_sha = _stdout(remote_sha_result) if remote_ref_available else None
    if remote_sha is not None and not re.fullmatch(r"[0-9a-fA-F]{40}", remote_sha):
        raise BranchAlignmentError("remote branch ref is not a full 40-character commit SHA")

    ahead: int | None = None
    behind: int | None = None
    if remote_ref_available:
        count_result = _run_git(
            top_level,
            ["rev-list", "--left-right", "--count", f"HEAD...{remote_ref}"],
            runner=runner,
        )
        ahead, behind = _parse_ahead_behind(_stdout(count_result))

    blockers: list[str] = []
    stand_downs: list[str] = []
    if detached:
        blockers.append("DETACHED_HEAD")
    elif current_branch != expected_branch:
        blockers.append(f"WRONG_BRANCH:{current_branch}")
    if remote_url is None:
        blockers.append(f"REMOTE_UNAVAILABLE:{remote}")
    elif remote_repository != expected_repository:
        blockers.append(f"REMOTE_REPOSITORY_MISMATCH:{remote_repository}")
    if blocked_dirty:
        blockers.append("DIRTY_OUTSIDE_ALLOWED_PATHS")
    if require_remote_match and not remote_ref_available:
        blockers.append(f"REMOTE_REF_UNAVAILABLE:{remote_ref}")
    if remote_ref_available:
        assert ahead is not None and behind is not None
        if ahead > 0 and behind > 0:
            blockers.append(f"DIVERGED_FROM_REMOTE:ahead={ahead}:behind={behind}")
        elif behind > 0:
            blockers.append(f"BEHIND_REMOTE:{behind}")
        elif ahead > 0 and not allow_local_ahead:
            blockers.append(f"LOCAL_AHEAD_UNPUSHED:{ahead}")
        elif ahead > 0:
            stand_downs.append(f"LOCAL_AHEAD_ALLOWED:{ahead}")
    if allowed_dirty:
        stand_downs.append(f"ALLOWED_DIRTY_PATHS:{len(allowed_dirty)}")

    if blockers:
        status = "BLOCKED"
    elif stand_downs:
        status = "ALIGNED_WITH_STAND_DOWNS"
    else:
        status = "ALIGNED"

    gate: dict[str, Any] = {
        "schema": SCHEMA,
        "market": "NG",
        "status": status,
        "observed_at": observed_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "repository_root": str(top_level),
        "expected_repository": expected_repository,
        "observed_remote_repository": remote_repository,
        "remote": remote,
        "remote_url": remote_url,
        "expected_branch": expected_branch,
        "observed_branch": current_branch,
        "detached_head": detached,
        "head_sha": head_sha.lower(),
        "remote_ref": remote_ref,
        "remote_ref_available": remote_ref_available,
        "remote_sha": remote_sha.lower() if remote_sha else None,
        "ahead_by": ahead,
        "behind_by": behind,
        "require_remote_match": bool(require_remote_match),
        "allow_local_ahead": bool(allow_local_ahead),
        "allowed_dirty_prefixes": sorted({_normalise_prefix(value) for value in allowed_dirty_prefixes if _normalise_prefix(value)}),
        "allowed_dirty_entries": allowed_dirty,
        "blocked_dirty_entries": blocked_dirty,
        "blockers": blockers,
        "stand_downs": stand_downs,
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
        "next_permitted_stage": (
            "HISTORICAL_REFINEMENT_EXECUTOR_PREFLIGHT"
            if status in {"ALIGNED", "ALIGNED_WITH_STAND_DOWNS"}
            else "REPAIR_BRANCH_OR_WORKTREE_ALIGNMENT"
        ),
    }
    gate["fingerprint"] = _fingerprint(gate)
    validate_gate(gate)
    return gate


def validate_gate(gate: Mapping[str, Any]) -> None:
    value = copy.deepcopy(dict(gate))
    observed = value.pop("fingerprint", None)
    if value.get("schema") != SCHEMA or observed != _fingerprint(value):
        raise BranchAlignmentError("branch alignment schema or fingerprint mismatch")
    if value.get("market") != "NG":
        raise BranchAlignmentError("branch alignment gate must be for NG")
    for field in (
        "remote_fetch_performed",
        "remote_presence_inferred",
        "random_shuffle_used",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise BranchAlignmentError(f"branch alignment gate must keep {field}=false")
    if value.get("one_signal_authority_preserved") is not True:
        raise BranchAlignmentError("branch alignment must preserve one signal authority")
    if value.get("blind_forecasts_immutable") is not True:
        raise BranchAlignmentError("branch alignment must preserve blind forecasts")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise BranchAlignmentError("CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise BranchAlignmentError("brokerage contract must remain tastytrade, not IBKR")

    status = value.get("status")
    blockers = value.get("blockers")
    stand_downs = value.get("stand_downs")
    if not isinstance(blockers, list) or not all(isinstance(item, str) and item for item in blockers):
        raise BranchAlignmentError("blockers must be a string list")
    if not isinstance(stand_downs, list) or not all(isinstance(item, str) and item for item in stand_downs):
        raise BranchAlignmentError("stand_downs must be a string list")
    if status == "BLOCKED":
        if not blockers or value.get("next_permitted_stage") != "REPAIR_BRANCH_OR_WORKTREE_ALIGNMENT":
            raise BranchAlignmentError("blocked gate requires blockers and repair-only next stage")
    elif status in {"ALIGNED", "ALIGNED_WITH_STAND_DOWNS"}:
        if blockers:
            raise BranchAlignmentError("aligned gate cannot contain blockers")
        if status == "ALIGNED" and stand_downs:
            raise BranchAlignmentError("fully aligned gate cannot contain stand-downs")
        if status == "ALIGNED_WITH_STAND_DOWNS" and not stand_downs:
            raise BranchAlignmentError("stand-down status requires stand-downs")
        if value.get("next_permitted_stage") != "HISTORICAL_REFINEMENT_EXECUTOR_PREFLIGHT":
            raise BranchAlignmentError("aligned gate has invalid next stage")
        if value.get("detached_head") is not False:
            raise BranchAlignmentError("aligned gate cannot be detached")
        if value.get("observed_branch") != value.get("expected_branch"):
            raise BranchAlignmentError("aligned gate must be on the expected branch")
        if value.get("observed_remote_repository") != value.get("expected_repository"):
            raise BranchAlignmentError("aligned gate must match the expected repository")
        if value.get("blocked_dirty_entries"):
            raise BranchAlignmentError("aligned gate cannot contain blocked dirty entries")
        if value.get("require_remote_match") and value.get("remote_ref_available") is not True:
            raise BranchAlignmentError("aligned gate requires the remote ref")
        behind = value.get("behind_by")
        ahead = value.get("ahead_by")
        if value.get("remote_ref_available"):
            if not isinstance(ahead, int) or not isinstance(behind, int):
                raise BranchAlignmentError("aligned gate requires numeric ahead/behind counts")
            if behind != 0:
                raise BranchAlignmentError("aligned gate cannot be behind the remote")
            if ahead and not value.get("allow_local_ahead"):
                raise BranchAlignmentError("aligned gate cannot be locally ahead unless explicitly allowed")
    else:
        raise BranchAlignmentError(f"unsupported branch alignment status: {status!r}")


def selftest() -> int:
    class FakeRunner:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def __call__(self, command: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            self.calls.append(list(command))
            args = list(command)[3:]
            outputs = {
                ("rev-parse", "--show-toplevel"): "/tmp/markets\n",
                ("symbolic-ref", "--quiet", "--short", "HEAD"): DEFAULT_BRANCH + "\n",
                ("rev-parse", "HEAD"): "1" * 40 + "\n",
                ("remote", "get-url", DEFAULT_REMOTE): "git@github.com:DavisAI1974/Markets.git\n",
                ("status", "--porcelain=v1", "--untracked-files=all"): "",
                ("rev-parse", "--verify", f"refs/remotes/{DEFAULT_REMOTE}/{DEFAULT_BRANCH}"): "1" * 40 + "\n",
                ("rev-list", "--left-right", "--count", f"HEAD...refs/remotes/{DEFAULT_REMOTE}/{DEFAULT_BRANCH}"): "0\t0\n",
            }
            key = tuple(args)
            if key not in outputs:
                return subprocess.CompletedProcess(command, 1, "", "unexpected command")
            return subprocess.CompletedProcess(command, 0, outputs[key], "")

    gate = build_gate(Path("/tmp/markets"), observed_at="2026-07-23T16:00:00Z", runner=FakeRunner())
    validate_gate(gate)
    assert gate["status"] == "ALIGNED"
    assert gate["execution_authority"] is False
    print("[ng_branch_alignment_gate] selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--repository-path", default=".")
    parser.add_argument("--expected-branch", default=DEFAULT_BRANCH)
    parser.add_argument("--expected-repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--remote", default=DEFAULT_REMOTE)
    parser.add_argument("--allow-dirty-prefix", action="append", default=[])
    parser.add_argument("--allow-local-ahead", action="store_true")
    parser.add_argument("--allow-missing-remote-ref", action="store_true")
    parser.add_argument("--observed-at")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.out:
        parser.error("--out is required unless --selftest is used")
    gate = build_gate(
        Path(args.repository_path),
        expected_branch=args.expected_branch,
        expected_repository=args.expected_repository,
        remote=args.remote,
        allowed_dirty_prefixes=args.allow_dirty_prefix,
        require_remote_match=not args.allow_missing_remote_ref,
        allow_local_ahead=args.allow_local_ahead,
        observed_at=args.observed_at,
    )
    _atomic_json(Path(args.out), gate)
    print(json.dumps({"status": gate["status"], "fingerprint": gate["fingerprint"]}, sort_keys=True))
    return 0 if gate["status"] in {"ALIGNED", "ALIGNED_WITH_STAND_DOWNS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
