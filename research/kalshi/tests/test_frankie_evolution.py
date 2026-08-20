from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_core import GateStop  # noqa: E402
from frankie_evaluation_controls import HoldoutExposureLedger  # noqa: E402
from frankie_evolution import (  # noqa: E402
    MIN_RELEASE_CASES,
    MIN_RELEASE_FIXES,
    build_candidate,
    evaluate_release,
)


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

    @staticmethod
    def row(case_id, baseline_pass, candidate_pass, *, protected=False, catastrophic=False):
        return {
            "case_id": case_id,
            "baseline_pass": baseline_pass,
            "candidate_pass": candidate_pass,
            "protected": protected,
            "candidate_catastrophic": catastrophic,
            "strata": {
                "task": "unit",
                "regime": "synthetic",
                "safety": "protected" if protected else "standard",
                "provenance": "complete",
            },
        }

    @staticmethod
    def release_controls(split_id="heldout-4"):
        split_hash = "a" * 64
        ledger = HoldoutExposureLedger(split_id, split_hash, "RELEASE").record(
            query_id="final-score",
            consumer="locked-evaluator",
            purpose="FINAL_RELEASE_SCORE",
            output_level="AGGREGATE_ONLY",
        )
        return {
            "evaluator_locked": True,
            "permissions_locked": True,
            "rollback_verified": True,
            "untouched_forward": True,
            "release_split_reuse_count": 0,
            "held_out_split_hash": split_hash,
            "release_exposure_audit": ledger.release_audit(),
        }

    @classmethod
    def clean_release_rows(cls):
        rows = []
        for index in range(MIN_RELEASE_CASES):
            correction = index < MIN_RELEASE_FIXES
            protected = MIN_RELEASE_FIXES <= index < (2 * MIN_RELEASE_FIXES)
            rows.append(
                cls.row(
                    f"release-{index:02d}",
                    not correction,
                    True,
                    protected=protected,
                )
            )
        return rows

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
            **self.release_controls("heldout-1"),
            held_out_rows=[
                self.row("a", False, True),
                self.row("b", True, True, protected=True),
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
            **self.release_controls("heldout-2"),
            held_out_rows=[
                self.row("a", True, False, protected=True),
                self.row("b", False, True),
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
            **self.release_controls("heldout-3"),
            held_out_rows=[
                self.row("a", True, True, protected=True),
                self.row("b", False, False),
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
            **self.release_controls(),
            held_out_rows=self.clean_release_rows(),
        )
        self.assertEqual(evaluation.pass_to_fail, 0)
        self.assertEqual(evaluation.fail_to_pass, MIN_RELEASE_FIXES)
        self.assertEqual(evaluation.verdict, "SANDBOX_RELEASE_ELIGIBLE")
        self.assertFalse(evaluation.apply_allowed)

    def test_release_requires_locked_evaluator_permissions_rollback_and_forward_gate(self):
        candidate = build_candidate(self.candidate_raw(), evidence_hashes={"evidence-a"})
        controls = self.release_controls("heldout-controls")
        for missing in ("evaluator_locked", "permissions_locked", "rollback_verified", "untouched_forward"):
            with self.subTest(control=missing):
                weakened = {**controls, missing: False}
                evaluation = evaluate_release(
                    candidate,
                    held_out_split_id="heldout-controls",
                    split_precommitted=True,
                    isolated_trial_worker=True,
                    required_tests_passed=True,
                    **weakened,
                    held_out_rows=[
                        self.row("a", True, True, protected=True),
                        self.row("b", False, True),
                    ],
                )
                self.assertEqual(evaluation.verdict, "REJECT")

    def test_catastrophic_case_and_release_split_reuse_are_rejected(self):
        candidate = build_candidate(self.candidate_raw(), evidence_hashes={"evidence-a"})
        controls = {**self.release_controls("heldout-reused"), "release_split_reuse_count": 1}
        evaluation = evaluate_release(
            candidate,
            held_out_split_id="heldout-reused",
            split_precommitted=True,
            isolated_trial_worker=True,
            required_tests_passed=True,
            **controls,
            held_out_rows=[
                self.row("a", True, True, protected=True),
                self.row("b", False, True, catastrophic=True),
            ],
        )
        self.assertEqual(evaluation.catastrophic_failures, 1)
        self.assertEqual(evaluation.verdict, "REJECT")

    def test_release_rejects_missing_or_tampered_holdout_exposure_audit(self):
        candidate = build_candidate(self.candidate_raw(), evidence_hashes={"evidence-a"})
        controls = self.release_controls("heldout-firewall")
        for audit in (None, {**controls["release_exposure_audit"], "exposure_count": 2}):
            with self.subTest(audit=audit):
                evaluation = evaluate_release(
                    candidate,
                    held_out_split_id="heldout-firewall",
                    split_precommitted=True,
                    isolated_trial_worker=True,
                    required_tests_passed=True,
                    **{**controls, "release_exposure_audit": audit},
                    held_out_rows=self.clean_release_rows(),
                )
                self.assertFalse(evaluation.holdout_firewall_passed)
                self.assertEqual(evaluation.verdict, "REJECT")

    def test_safety_kernel_and_deploy_targets_are_forbidden(self):
        for path in (
            "research/kalshi/agent_frankie.py",
            "research/kalshi/frankie_core.py",
            "research/kalshi/frankie_cognition.py",
            "research/kalshi/frankie_cognitive_experiments.py",
            "deploy/aws/markets-frankie.service",
            ".github/workflows/agent_frankie_ci.yml",
        ):
            with self.subTest(path=path):
                with self.assertRaises(GateStop):
                    build_candidate(self.candidate_raw(requested_files=[path]), evidence_hashes={"evidence-a"})


if __name__ == "__main__":
    unittest.main()
