from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_core import GateStop  # noqa: E402
from frankie_evolution import build_candidate, evaluate_release  # noqa: E402


class FrankieEvolutionTests(unittest.TestCase):
    @staticmethod
    def candidate_raw(requested_files=None, surfaces=None):
        return {
            "parent_version": "frankie-s117.1",
            "task_route": "prediction-market",
            "mutable_surfaces": surfaces or ["strategy", "skills", "playbook"],
            "strategy": "preserve point-in-time truth and reject unsupported inference",
            "skills": ["contract identity", "causal clock audit"],
            "playbook": ["qualify", "reason independently", "falsify", "shadow"],
            "evidence_refs": ["evidence-a"],
            "hypothesis": "a route-specific harness will reduce repeated failure without regression",
            "requested_files": requested_files or ["research/kalshi/harnesses/prediction_market.json"],
            "human_steering_note": "review regime-change cases",
            "execution_enabled": False,
            "apply_allowed": False,
        }

    def test_rsea_style_candidate_has_three_layer_state(self):
        candidate = build_candidate(self.candidate_raw(), evidence_hashes={"evidence-a"})
        self.assertTrue(candidate.harness_state.strategy)
        self.assertTrue(candidate.harness_state.skills)
        self.assertTrue(candidate.harness_state.playbook)
        self.assertFalse(candidate.execution_enabled)
        self.assertFalse(candidate.apply_allowed)

    def test_source_affecting_surface_requires_isolated_trial(self):
        candidate = build_candidate(
            self.candidate_raw(surfaces=["research_tool"]),
            evidence_hashes={"evidence-a"},
        )
        self.assertTrue(candidate.source_trial_required)
        evaluation = evaluate_release(
            candidate,
            held_out_split_id="heldout-1",
            split_precommitted=True,
            isolated_trial_worker=False,
            required_tests_passed=True,
            held_out_rows=[
                {"case_id": "a", "baseline_pass": False, "candidate_pass": True},
                {"case_id": "b", "baseline_pass": True, "candidate_pass": True},
            ],
        )
        self.assertEqual(evaluation.verdict, "REJECT")

    def test_keep_better_gate_rejects_any_pass_to_fail(self):
        candidate = build_candidate(self.candidate_raw(), evidence_hashes={"evidence-a"})
        evaluation = evaluate_release(
            candidate,
            held_out_split_id="heldout-2",
            split_precommitted=True,
            isolated_trial_worker=True,
            required_tests_passed=True,
            held_out_rows=[
                {"case_id": "a", "baseline_pass": True, "candidate_pass": False},
                {"case_id": "b", "baseline_pass": False, "candidate_pass": True},
            ],
        )
        self.assertEqual(evaluation.pass_to_fail, 1)
        self.assertEqual(evaluation.verdict, "REJECT")

    def test_keep_better_gate_requires_fail_to_pass(self):
        candidate = build_candidate(self.candidate_raw(), evidence_hashes={"evidence-a"})
        evaluation = evaluate_release(
            candidate,
            held_out_split_id="heldout-3",
            split_precommitted=True,
            isolated_trial_worker=True,
            required_tests_passed=True,
            held_out_rows=[
                {"case_id": "a", "baseline_pass": True, "candidate_pass": True},
                {"case_id": "b", "baseline_pass": False, "candidate_pass": False},
            ],
        )
        self.assertEqual(evaluation.verdict, "REJECT")

    def test_clean_nonregressing_fix_is_sandbox_release_eligible(self):
        candidate = build_candidate(self.candidate_raw(), evidence_hashes={"evidence-a"})
        evaluation = evaluate_release(
            candidate,
            held_out_split_id="heldout-4",
            split_precommitted=True,
            isolated_trial_worker=True,
            required_tests_passed=True,
            held_out_rows=[
                {"case_id": "a", "baseline_pass": True, "candidate_pass": True},
                {"case_id": "b", "baseline_pass": False, "candidate_pass": True},
            ],
        )
        self.assertEqual(evaluation.pass_to_fail, 0)
        self.assertEqual(evaluation.fail_to_pass, 1)
        self.assertEqual(evaluation.verdict, "SANDBOX_RELEASE_ELIGIBLE")
        self.assertFalse(evaluation.apply_allowed)

    def test_safety_kernel_and_deploy_targets_are_forbidden(self):
        for path in (
            "research/kalshi/agent_frankie.py",
            "research/kalshi/frankie_core.py",
            "deploy/aws/markets-frankie.service",
            ".github/workflows/agent_frankie_ci.yml",
        ):
            with self.subTest(path=path):
                with self.assertRaises(GateStop):
                    build_candidate(self.candidate_raw(requested_files=[path]), evidence_hashes={"evidence-a"})


if __name__ == "__main__":
    unittest.main()
