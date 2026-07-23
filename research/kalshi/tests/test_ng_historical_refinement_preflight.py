from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import ng_branch_alignment_gate as branch_alignment
import ng_historical_refinement_executor as executor
import ng_historical_refinement_preflight as preflight


class GateSequence:
    def __init__(self, gates):
        self.gates = [copy.deepcopy(gate) for gate in gates]
        self.calls = []

    def __call__(self, repository_path, **kwargs):
        self.calls.append((Path(repository_path), kwargs))
        if not self.gates:
            raise AssertionError("unexpected gate build")
        return copy.deepcopy(self.gates.pop(0))


class HistoricalRefinementPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "Markets"
        self.work = self.repo / "research" / "kalshi"
        self.artifacts = self.work / "renders" / "ng_refine_s95"
        self.artifacts.mkdir(parents=True)
        for relative in (
            "forecasts/grp15.json",
            "forecasts/grp16.json",
            "knowledge/ng_brain.json",
        ):
            path = self.work / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
        self.plan = executor.build_plan(self.artifacts, self.work)
        self.ledger = self.artifacts / "execution_ledger.json"

    def tearDown(self):
        self.temp.cleanup()

    def gate(
        self,
        *,
        status="ALIGNED",
        head="1" * 40,
        repository_root=None,
        observed_branch=branch_alignment.DEFAULT_BRANCH,
        observed_repository=branch_alignment.DEFAULT_REPOSITORY,
        remote=branch_alignment.DEFAULT_REMOTE,
        remote_url=None,
        expected_branch=branch_alignment.DEFAULT_BRANCH,
        expected_repository=branch_alignment.DEFAULT_REPOSITORY,
        allowed_dirty_prefixes=(),
        require_remote_match=True,
        allow_local_ahead=False,
        stand_downs=(),
        blockers=(),
    ):
        repository_root = repository_root or self.repo
        if status == "BLOCKED" and not blockers:
            blockers = ("DIRTY_OUTSIDE_ALLOWED_PATHS",)
        if status == "ALIGNED_WITH_STAND_DOWNS" and not stand_downs:
            stand_downs = ("ALLOWED_DIRTY_PATHS:1",)
        gate = {
            "schema": branch_alignment.SCHEMA,
            "market": "NG",
            "status": status,
            "observed_at": "2026-07-23T17:00:00Z",
            "repository_root": str(repository_root),
            "expected_repository": expected_repository,
            "observed_remote_repository": observed_repository,
            "remote": remote,
            "remote_url": remote_url or f"git@github.com:{observed_repository}.git",
            "expected_branch": expected_branch,
            "observed_branch": observed_branch,
            "detached_head": False,
            "head_sha": head,
            "remote_ref": f"refs/remotes/{remote}/{expected_branch}",
            "remote_ref_available": True,
            "remote_sha": head,
            "ahead_by": 0,
            "behind_by": 0,
            "require_remote_match": require_remote_match,
            "allow_local_ahead": allow_local_ahead,
            "allowed_dirty_prefixes": sorted(allowed_dirty_prefixes),
            "allowed_dirty_entries": [],
            "blocked_dirty_entries": [] if status != "BLOCKED" else [{"status": " M", "path": "bad.py"}],
            "blockers": list(blockers),
            "stand_downs": list(stand_downs),
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
                "REPAIR_BRANCH_OR_WORKTREE_ALIGNMENT"
                if status == "BLOCKED"
                else "HISTORICAL_REFINEMENT_EXECUTOR_PREFLIGHT"
            ),
        }
        gate["fingerprint"] = branch_alignment._fingerprint(gate)
        branch_alignment.validate_gate(gate)
        return gate

    @staticmethod
    def executor_result(status="CONFIGURATION_REQUIRED"):
        return {"status": status, "stage": "corpus_coverage"}

    def run_with(self, gates, executor_runner=None, **kwargs):
        sequence = GateSequence(gates)
        calls = []

        def runner(*args, **inner_kwargs):
            calls.append((args, inner_kwargs))
            if executor_runner is not None:
                return executor_runner(*args, **inner_kwargs)
            return self.executor_result()

        result = preflight.execute_preflight(
            self.plan,
            self.ledger,
            gate_builder=sequence,
            executor_runner=runner,
            **kwargs,
        )
        return result, sequence, calls

    def test_aligned_pre_and_post_call_executor_once(self):
        result, sequence, calls = self.run_with([self.gate(), self.gate()])
        self.assertEqual(result["status"], "PREFLIGHT_PASSED")
        self.assertEqual(result["executor_result"]["status"], "CONFIGURATION_REQUIRED")
        self.assertEqual(len(sequence.calls), 2)
        self.assertEqual(len(calls), 1)
        preflight.validate_receipt(result)

    def test_blocked_preflight_never_calls_executor(self):
        result, sequence, calls = self.run_with([self.gate(status="BLOCKED")])
        self.assertEqual(result["status"], "BRANCH_ALIGNMENT_BLOCKED")
        self.assertFalse(result["executor_called"])
        self.assertEqual(len(sequence.calls), 1)
        self.assertEqual(calls, [])
        self.assertFalse(self.ledger.exists())

    def test_working_directory_must_be_inside_repository(self):
        outside = self.root / "other-repository"
        outside.mkdir()
        with self.assertRaises(preflight.HistoricalRefinementPreflightError):
            self.run_with([self.gate(repository_root=outside)])

    def test_head_change_is_detected_after_execution(self):
        result, _, _ = self.run_with([self.gate(head="1" * 40), self.gate(head="2" * 40)])
        self.assertEqual(result["status"], "REPOSITORY_HEAD_CHANGED")
        self.assertFalse(result["head_immutable_during_execution"])
        self.assertIn("HEAD_CHANGED", result["blockers"][0])

    def test_repository_identity_change_is_detected(self):
        after = self.gate(remote_url="https://github.com/DavisAI1974/Markets.git")
        result, _, _ = self.run_with([self.gate(), after])
        self.assertEqual(result["status"], "REPOSITORY_ALIGNMENT_CHANGED")
        self.assertFalse(result["alignment_identity_immutable_during_execution"])

    def test_post_execution_block_is_visible(self):
        result, _, _ = self.run_with([self.gate(), self.gate(status="BLOCKED")])
        self.assertEqual(result["status"], "POST_EXECUTION_ALIGNMENT_BLOCKED")
        self.assertTrue(result["executor_called"])
        self.assertIn("DIRTY_OUTSIDE_ALLOWED_PATHS", result["blockers"])

    def test_alignment_stand_downs_are_unionized(self):
        before = self.gate(status="ALIGNED_WITH_STAND_DOWNS", stand_downs=("LOCAL_AHEAD_ALLOWED:1",))
        after = self.gate(status="ALIGNED_WITH_STAND_DOWNS", stand_downs=("ALLOWED_DIRTY_PATHS:2",))
        result, _, _ = self.run_with([before, after])
        self.assertEqual(result["status"], "PREFLIGHT_PASSED_WITH_STAND_DOWNS")
        self.assertEqual(result["stand_downs"], ["ALLOWED_DIRTY_PATHS:2", "LOCAL_AHEAD_ALLOWED:1"])

    def test_fixed_outcome_flag_is_forwarded(self):
        result, _, calls = self.run_with([self.gate(), self.gate()], allow_fixed_outcomes=True)
        self.assertTrue(calls[0][1]["allow_fixed_outcomes"])
        self.assertTrue(result["fixed_outcomes_explicitly_allowed"])

    def test_dry_run_and_command_runner_are_forwarded(self):
        command_runner = object()
        result, _, calls = self.run_with(
            [self.gate(), self.gate()],
            dry_run=True,
            command_runner=command_runner,
        )
        self.assertTrue(calls[0][1]["dry_run"])
        self.assertIs(calls[0][1]["command_runner"], command_runner)
        self.assertTrue(result["dry_run"])

    def test_requested_repository_policy_cannot_be_ignored(self):
        gate = self.gate(expected_repository="Other/Repo", observed_repository="Other/Repo")
        with self.assertRaises(preflight.HistoricalRefinementPreflightError):
            self.run_with([gate])

    def test_requested_dirty_prefix_policy_cannot_be_ignored(self):
        gate = self.gate(allowed_dirty_prefixes=())
        with self.assertRaises(preflight.HistoricalRefinementPreflightError):
            self.run_with([gate], allowed_dirty_prefixes=("research/kalshi/renders",))

    def test_receipt_authority_escalation_is_rejected_after_refingerprint(self):
        result, _, _ = self.run_with([self.gate(), self.gate()])
        result["execution_authority"] = True
        result.pop("fingerprint")
        result["fingerprint"] = preflight._fingerprint(result)
        with self.assertRaises(preflight.HistoricalRefinementPreflightError):
            preflight.validate_receipt(result)

    def test_blocked_receipt_cannot_claim_executor_called(self):
        result, _, _ = self.run_with([self.gate(status="BLOCKED")])
        result["executor_called"] = True
        result["executor_result"] = self.executor_result()
        result.pop("fingerprint")
        result["fingerprint"] = preflight._fingerprint(result)
        with self.assertRaises(preflight.HistoricalRefinementPreflightError):
            preflight.validate_receipt(result)

    def test_passed_receipt_requires_executor_status(self):
        result, _, _ = self.run_with([self.gate(), self.gate()])
        result["executor_result"] = {}
        result.pop("fingerprint")
        result["fingerprint"] = preflight._fingerprint(result)
        with self.assertRaises(preflight.HistoricalRefinementPreflightError):
            preflight.validate_receipt(result)

    def test_nested_gate_tampering_is_rejected(self):
        result, _, _ = self.run_with([self.gate(), self.gate()])
        result["alignment_before"]["options_lane_started"] = True
        result["alignment_before"].pop("fingerprint")
        result["alignment_before"]["fingerprint"] = branch_alignment._fingerprint(result["alignment_before"])
        result.pop("fingerprint")
        result["fingerprint"] = preflight._fingerprint(result)
        with self.assertRaises(branch_alignment.BranchAlignmentError):
            preflight.validate_receipt(result)

    def test_plan_tampering_is_rejected_before_gate_build(self):
        plan = copy.deepcopy(self.plan)
        plan["brokerage_contract"] = "ibkr"
        plan.pop("fingerprint")
        plan["fingerprint"] = executor._fingerprint(plan)
        sequence = GateSequence([self.gate()])
        with self.assertRaises(executor.HistoricalRefinementExecutionError):
            preflight.execute_preflight(plan, self.ledger, gate_builder=sequence)
        self.assertEqual(sequence.calls, [])

    def test_permanent_authority_contract_is_preserved(self):
        result, _, _ = self.run_with([self.gate(), self.gate()])
        self.assertFalse(result["random_shuffle_used"])
        self.assertTrue(result["one_signal_authority_preserved"])
        self.assertTrue(result["blind_forecasts_immutable"])
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(result["execution_authority"])
        self.assertEqual(result["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(result["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(result["options_lane_started"])


if __name__ == "__main__":
    unittest.main()
