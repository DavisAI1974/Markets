from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_s137_cognitive_experiment_runner as paired  # noqa: E402
from frankie_cognitive_experiments import (  # noqa: E402
    EXPERIMENT_BY_ID,
    MIN_EVALUATION_CASES,
    MIN_FAIL_TO_PASS_CASES,
)


class FrankieS137PairedRunnerTests(unittest.TestCase):
    candidate_id = "COG01_COALA_ARCHITECTURE_MAP"

    @staticmethod
    def cases():
        strata = {
            "task": "forecast",
            "regime": "development",
            "safety": "standard",
            "provenance": "complete",
        }
        cases = []
        for index in range(MIN_EVALUATION_CASES):
            protected = MIN_FAIL_TO_PASS_CASES <= index < (2 * MIN_FAIL_TO_PASS_CASES)
            cases.append(
                paired.PairedCaseSpec(
                    f"case-{index:02d}",
                    "C",
                    {**strata, "safety": "protected" if protected else "standard"},
                    protected=protected,
                    arm_order=("candidate", "baseline") if index % 2 == 0 else ("baseline", "candidate"),
                )
            )
        return cases

    @staticmethod
    def packet_fn(case):
        return "CURRENT PROMPT", {
            "phase": "BLIND",
            "case": case.case_id,
            "causal_slice": {"day": {"dow": "Thu"}},
            "brain_view_served": {"plays": {"p": {"id": "p"}}},
        }

    @classmethod
    def candidate_output(cls, case):
        return {
            "disposition": "ABSTAIN",
            "cognitive_evaluation": {
                "candidate_id": cls.candidate_id,
                "reasoning_steps": [
                    {
                        "step_id": "S1",
                        "action": "OBSERVE",
                        "claim": f"inspect {case.case_id}",
                        "evidence_refs": ["packet:causal_slice"],
                        "depends_on": [],
                        "status": "SUPPORTED",
                    }
                ],
                "uncertainty": {
                    "level": "HIGH",
                    "drivers": ["scripted paired test"],
                    "calibrated_probability": None,
                },
            },
        }

    @staticmethod
    def budget(candidate=False):
        return paired.BudgetUsage(
            model_calls=1,
            input_tokens=100 + int(candidate),
            output_tokens=50,
            tool_queries=0,
            storage_bytes=500,
            wall_clock_ms=10,
        )

    def test_suite_freezes_both_arms_before_reveal_and_passes_locked_gate(self):
        events = []

        def invoke(case, arm, prompt, packet):
            events.append((case.case_id, "invoke", arm))
            if arm == "candidate":
                self.assertIn("S137 COGNITIVE SHADOW CANDIDATE", prompt)
                self.assertIn("s137_cognitive_candidate", packet)
                output = self.candidate_output(case)
            else:
                self.assertNotIn("s137_cognitive_candidate", packet)
                output = {"disposition": "ABSTAIN"}
            return paired.InvocationResult(output, self.budget(arm == "candidate"))

        def reveal(case):
            case_events = [event for event in events if event[0] == case.case_id]
            self.assertEqual({event[2] for event in case_events}, {"baseline", "candidate"})
            events.append((case.case_id, "reveal", "target"))
            return {"answer": "known only after both freezes"}

        rules = EXPERIMENT_BY_ID[self.candidate_id].metric_rules

        def grade(case, arm, output, actual):
            del output, actual
            candidate = arm == "candidate"
            index = int(case.case_id.rsplit("-", 1)[1])
            passed = True if index >= MIN_FAIL_TO_PASS_CASES else candidate
            metrics = {
                rule.name: (0.6 if candidate and rule.direction == "HIGHER" else
                            0.4 if candidate else 0.5)
                for rule in rules
            }
            return paired.ArmGrade(passed, metrics)

        with mock.patch.object(paired.s135, "install", return_value=None), mock.patch.object(
            paired.s135, "validate_owner_output", return_value=None
        ):
            result = paired.run_paired_suite(
                self.candidate_id,
                self.cases(),
                packet_fn=self.packet_fn,
                invoke_fn=invoke,
                reveal_fn=reveal,
                grade_fn=grade,
                baseline_validate_fn=lambda output, specialist, task: None,
            )
        self.assertEqual(result["evaluation"]["verdict"], "COMPONENT_GATE_PASSED")
        self.assertEqual(result["evaluation"]["next_gate"], "UNTOUCHED_FORWARD_SHADOW")
        self.assertTrue(result["performance_evidence"])
        self.assertEqual(len(result["case_audits"]), MIN_EVALUATION_CASES)
        self.assertTrue(all(audit["same_information_set"] for audit in result["case_audits"]))
        self.assertTrue(all(audit["freeze_before_reveal"] for audit in result["case_audits"]))

    def test_invalid_candidate_never_reveals_target(self):
        revealed = []

        def invoke(case, arm, prompt, packet):
            del prompt, packet
            output = {"disposition": "ABSTAIN"}
            if arm == "candidate":
                output["cognitive_evaluation"] = {
                    "candidate_id": self.candidate_id,
                    "reasoning_steps": [],
                    "uncertainty": {"level": "HIGH", "drivers": ["bad"]},
                }
            return paired.InvocationResult(output, self.budget())

        with mock.patch.object(paired.s135, "install", return_value=None), mock.patch.object(
            paired.s135, "validate_owner_output", return_value=None
        ):
            with self.assertRaises(Exception):
                paired.run_paired_case(
                    self.candidate_id,
                    self.cases()[0],
                    packet_fn=self.packet_fn,
                    invoke_fn=invoke,
                    reveal_fn=lambda case: revealed.append(case.case_id) or {},
                    grade_fn=lambda *args: paired.ArmGrade(True, {}),
                    baseline_validate_fn=lambda output, specialist, task: None,
                )
        self.assertEqual(revealed, [])

    def test_measured_budget_overrun_is_a_rejection(self):
        rules = EXPERIMENT_BY_ID[self.candidate_id].metric_rules

        def invoke(case, arm, prompt, packet):
            del prompt, packet
            output = self.candidate_output(case) if arm == "candidate" else {"disposition": "ABSTAIN"}
            budget = self.budget()
            if arm == "candidate":
                budget = dataclasses.replace(budget, input_tokens=150)
            return paired.InvocationResult(output, budget)

        def grade(case, arm, output, actual):
            del case, output, actual
            candidate = arm == "candidate"
            return paired.ArmGrade(
                candidate,
                {rule.name: (0.6 if candidate else 0.5) for rule in rules},
            )

        import dataclasses
        with mock.patch.object(paired.s135, "install", return_value=None), mock.patch.object(
            paired.s135, "validate_owner_output", return_value=None
        ):
            result = paired.run_paired_suite(
                self.candidate_id,
                [self.cases()[0]],
                packet_fn=self.packet_fn,
                invoke_fn=invoke,
                reveal_fn=lambda case: {"case": case.case_id},
                grade_fn=grade,
                baseline_validate_fn=lambda output, specialist, task: None,
            )
        self.assertEqual(result["evaluation"]["verdict"], "REJECT")
        self.assertTrue(result["evaluation"]["budget_violations"])

    def test_runner_manifest_is_shadow_only_for_all_ten(self):
        manifest = paired.runner_manifest()
        self.assertEqual(len(manifest["candidate_ids"]), 10)
        self.assertEqual(manifest["promotion_authority"], "NONE")
        self.assertFalse(manifest["execution_enabled"])
        self.assertFalse(manifest["automatic_apply"])


if __name__ == "__main__":
    unittest.main()
