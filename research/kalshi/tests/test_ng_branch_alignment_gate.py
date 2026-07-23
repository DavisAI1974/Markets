from __future__ import annotations

import copy
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any, Sequence

import ng_branch_alignment_gate as gate


class FakeGit:
    def __init__(
        self,
        *,
        branch: str | None = gate.DEFAULT_BRANCH,
        head: str = "1" * 40,
        remote_url: str | None = "git@github.com:DavisAI1974/Markets.git",
        remote_sha: str | None = "1" * 40,
        ahead: int = 0,
        behind: int = 0,
        status: str = "",
        top_level: str = "/work/Markets",
    ) -> None:
        self.branch = branch
        self.head = head
        self.remote_url = remote_url
        self.remote_sha = remote_sha
        self.ahead = ahead
        self.behind = behind
        self.status = status
        self.top_level = top_level
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, command: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        command = list(command)
        self.calls.append((command, kwargs))
        args = tuple(command[3:])
        if args == ("rev-parse", "--show-toplevel"):
            return subprocess.CompletedProcess(command, 0, self.top_level + "\n", "")
        if args == ("symbolic-ref", "--quiet", "--short", "HEAD"):
            if self.branch is None:
                return subprocess.CompletedProcess(command, 1, "", "")
            return subprocess.CompletedProcess(command, 0, self.branch + "\n", "")
        if args == ("rev-parse", "HEAD"):
            return subprocess.CompletedProcess(command, 0, self.head + "\n", "")
        if args == ("remote", "get-url", gate.DEFAULT_REMOTE):
            if self.remote_url is None:
                return subprocess.CompletedProcess(command, 2, "", "missing remote")
            return subprocess.CompletedProcess(command, 0, self.remote_url + "\n", "")
        if args == ("status", "--porcelain=v1", "--untracked-files=all"):
            return subprocess.CompletedProcess(command, 0, self.status, "")
        remote_ref = f"refs/remotes/{gate.DEFAULT_REMOTE}/{gate.DEFAULT_BRANCH}"
        if args == ("rev-parse", "--verify", remote_ref):
            if self.remote_sha is None:
                return subprocess.CompletedProcess(command, 1, "", "missing ref")
            return subprocess.CompletedProcess(command, 0, self.remote_sha + "\n", "")
        if args == ("rev-list", "--left-right", "--count", f"HEAD...{remote_ref}"):
            return subprocess.CompletedProcess(command, 0, f"{self.ahead}\t{self.behind}\n", "")
        return subprocess.CompletedProcess(command, 99, "", f"unexpected command: {args!r}")


class BranchAlignmentGateTests(unittest.TestCase):
    def build(self, fake: FakeGit | None = None, **kwargs: Any) -> dict[str, Any]:
        return gate.build_gate(
            Path("/work/Markets"),
            observed_at="2026-07-23T16:49:00Z",
            runner=fake or FakeGit(),
            **kwargs,
        )

    def test_clean_expected_branch_is_aligned(self):
        fake = FakeGit()
        result = self.build(fake)
        gate.validate_gate(result)
        self.assertEqual(result["status"], "ALIGNED")
        self.assertEqual(result["head_sha"], "1" * 40)
        self.assertEqual(result["remote_sha"], "1" * 40)
        self.assertEqual(result["ahead_by"], 0)
        self.assertEqual(result["behind_by"], 0)
        self.assertTrue(all(call[1]["shell"] is False for call in fake.calls))

    def test_wrong_branch_is_blocked(self):
        result = self.build(FakeGit(branch="main"))
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("WRONG_BRANCH:main", result["blockers"])

    def test_detached_head_is_blocked(self):
        result = self.build(FakeGit(branch=None))
        self.assertIn("DETACHED_HEAD", result["blockers"])
        self.assertTrue(result["detached_head"])

    def test_dirty_source_file_is_blocked(self):
        result = self.build(FakeGit(status=" M research/kalshi/ng_live_operator.py\n"))
        self.assertIn("DIRTY_OUTSIDE_ALLOWED_PATHS", result["blockers"])
        self.assertEqual(result["blocked_dirty_entries"][0]["status"], " M")

    def test_explicit_artifact_dirty_prefix_is_visible_stand_down(self):
        result = self.build(
            FakeGit(status="?? research/kalshi/renders/ng_refine_s95/new.json\n"),
            allowed_dirty_prefixes=["research/kalshi/renders/ng_refine_s95"],
        )
        self.assertEqual(result["status"], "ALIGNED_WITH_STAND_DOWNS")
        self.assertEqual(result["allowed_dirty_entries"][0]["status"], "??")
        self.assertIn("ALLOWED_DIRTY_PATHS:1", result["stand_downs"])

    def test_rename_requires_both_paths_to_be_allowed(self):
        result = self.build(
            FakeGit(status="R  research/kalshi/renders/ng_refine_s95/a.json -> research/kalshi/code.py\n"),
            allowed_dirty_prefixes=["research/kalshi/renders/ng_refine_s95"],
        )
        self.assertEqual(result["status"], "BLOCKED")

    def test_behind_remote_is_blocked(self):
        result = self.build(FakeGit(remote_sha="2" * 40, behind=3))
        self.assertIn("BEHIND_REMOTE:3", result["blockers"])

    def test_diverged_remote_is_blocked(self):
        result = self.build(FakeGit(remote_sha="2" * 40, ahead=2, behind=1))
        self.assertIn("DIVERGED_FROM_REMOTE:ahead=2:behind=1", result["blockers"])

    def test_local_ahead_is_blocked_by_default(self):
        result = self.build(FakeGit(head="3" * 40, ahead=2))
        self.assertIn("LOCAL_AHEAD_UNPUSHED:2", result["blockers"])

    def test_local_ahead_can_be_explicitly_allowed_but_is_visible(self):
        result = self.build(FakeGit(head="3" * 40, ahead=2), allow_local_ahead=True)
        self.assertEqual(result["status"], "ALIGNED_WITH_STAND_DOWNS")
        self.assertIn("LOCAL_AHEAD_ALLOWED:2", result["stand_downs"])

    def test_missing_remote_ref_fails_closed_by_default(self):
        result = self.build(FakeGit(remote_sha=None))
        self.assertIn(
            f"REMOTE_REF_UNAVAILABLE:refs/remotes/{gate.DEFAULT_REMOTE}/{gate.DEFAULT_BRANCH}",
            result["blockers"],
        )

    def test_missing_remote_ref_can_be_explicitly_tolerated(self):
        result = self.build(FakeGit(remote_sha=None), require_remote_match=False)
        self.assertEqual(result["status"], "ALIGNED")
        self.assertIsNone(result["ahead_by"])
        self.assertFalse(result["remote_ref_available"])

    def test_wrong_remote_repository_is_blocked(self):
        result = self.build(FakeGit(remote_url="https://github.com/Other/Markets.git"))
        self.assertIn("REMOTE_REPOSITORY_MISMATCH:Other/Markets", result["blockers"])

    def test_malformed_status_is_rejected(self):
        with self.assertRaises(gate.BranchAlignmentError):
            self.build(FakeGit(status="bad\n"))

    def test_refingerprinted_authority_escalation_is_rejected(self):
        result = self.build()
        tampered = copy.deepcopy(result)
        tampered["options_lane_started"] = True
        tampered.pop("fingerprint")
        tampered["fingerprint"] = gate._fingerprint(tampered)
        with self.assertRaises(gate.BranchAlignmentError):
            gate.validate_gate(tampered)

    def test_deterministic_with_fixed_observation_time(self):
        first = self.build(FakeGit())
        second = self.build(FakeGit())
        self.assertEqual(first, second)

    def test_cli_style_atomic_output_round_trip(self):
        result = self.build()
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "gate.json"
            gate._atomic_json(path, result)
            loaded = gate.json.loads(path.read_text(encoding="utf-8"))
            gate.validate_gate(loaded)
            self.assertEqual(loaded["fingerprint"], result["fingerprint"])


if __name__ == "__main__":
    unittest.main()
