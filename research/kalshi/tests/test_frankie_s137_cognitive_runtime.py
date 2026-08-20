from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_s137_cognitive_runtime as s137  # noqa: E402


class FrankieS137CognitiveRuntimeTests(unittest.TestCase):
    @staticmethod
    def base_packet(*args, **kwargs):
        del args, kwargs
        return "CURRENT PROMPT", {
            "phase": "BLIND",
            "specialist": "C",
            "causal_slice": {"20260820": {"dow": "Thu"}},
            "brain_view_served": {"plays": {"p": {"id": "p"}}},
        }

    @staticmethod
    def output(candidate_id, *, retrieve=True, unknown_ref=False):
        first_action = "RETRIEVE" if retrieve else "OBSERVE"
        first_ref = "packet:missing" if unknown_ref else "packet:causal_slice"
        return {
            "disposition": "ABSTAIN",
            "reasoning": "DIRECTION OWNER: unavailable",
            "cognitive_evaluation": {
                "candidate_id": candidate_id,
                "reasoning_steps": [
                    {
                        "step_id": "S1",
                        "action": first_action,
                        "claim": "inspect the causal slice",
                        "evidence_refs": [first_ref],
                        "depends_on": [],
                        "status": "SUPPORTED",
                    },
                    {
                        "step_id": "S2",
                        "action": "REASON",
                        "claim": "withhold unsupported directional authority",
                        "evidence_refs": ["packet:brain_view_served"],
                        "depends_on": ["S1"],
                        "status": "SUPPORTED",
                    },
                ],
                "uncertainty": {
                    "level": "HIGH",
                    "drivers": ["synthetic wrapper test"],
                    "calibrated_probability": None,
                },
            },
        }

    def test_wrapper_attaches_exactly_one_shadow_candidate(self):
        runtime = s137.runtime_for("COG01_COALA_ARCHITECTURE_MAP")
        with mock.patch.object(s137.s135, "packet", side_effect=self.base_packet):
            prompt, packet = runtime.packet("BLD-1", "g-test", "20260820", "C", "unit")
        contract = packet["s137_cognitive_candidate"]
        self.assertIn("S137 COGNITIVE SHADOW CANDIDATE", prompt)
        self.assertEqual(contract["candidate_id"], "COG01_COALA_ARCHITECTURE_MAP")
        self.assertEqual(contract["authority"], "SHADOW_ONLY")
        self.assertFalse(contract["execution_enabled"])
        self.assertFalse(contract["automatic_apply"])

    def test_wrapper_validates_evidence_bound_output_then_consumes_pending_contract(self):
        candidate_id = "COG02_REACT_EVIDENCE_LOOP"
        runtime = s137.runtime_for(candidate_id)
        with mock.patch.object(s137.s135, "packet", side_effect=self.base_packet):
            runtime.packet("BLD-1", "g-test", "20260820", "C", "unit")
        with mock.patch.object(s137.s135, "validate_owner_output", return_value=None):
            runtime.validate_owner_output(self.output(candidate_id), "C")
            with self.assertRaises(s137.CognitiveRuntimeError):
                runtime.validate_owner_output(self.output(candidate_id), "C")

    def test_wrapper_rejects_unknown_evidence_ref(self):
        candidate_id = "COG04_STRUCTGPT_TYPED_READS"
        runtime = s137.runtime_for(candidate_id)
        with mock.patch.object(s137.s135, "packet", side_effect=self.base_packet):
            runtime.packet("BLD-1", "g-test", "20260820", "C", "unit")
        with mock.patch.object(s137.s135, "validate_owner_output", return_value=None):
            with self.assertRaises(s137.CognitiveRuntimeError):
                runtime.validate_owner_output(self.output(candidate_id, unknown_ref=True), "C")

    def test_react_candidate_rejects_retrieval_not_used_by_reasoning(self):
        candidate_id = "COG02_REACT_EVIDENCE_LOOP"
        runtime = s137.runtime_for(candidate_id)
        with mock.patch.object(s137.s135, "packet", side_effect=self.base_packet):
            runtime.packet("BLD-1", "g-test", "20260820", "C", "unit")
        output = self.output(candidate_id)
        output["cognitive_evaluation"]["reasoning_steps"][1]["depends_on"] = []
        with mock.patch.object(s137.s135, "validate_owner_output", return_value=None):
            with self.assertRaises(s137.CognitiveRuntimeError):
                runtime.validate_owner_output(output, "C")

    def test_faithful_candidate_requires_supported_deterministic_check(self):
        candidate_id = "COG05_FAITHFUL_EXECUTABLE_REASONING"
        runtime = s137.runtime_for(candidate_id)
        with mock.patch.object(s137.s135, "packet", side_effect=self.base_packet):
            runtime.packet("BLD-1", "g-test", "20260820", "C", "unit")
        output = self.output(candidate_id)
        output["cognitive_evaluation"]["deterministic_checks"] = [
            {
                "check_id": "identity",
                "check_type": "EXACT_EQUAL",
                "evidence_refs": ["packet:causal_slice"],
                "inputs": {"left": "EXACT", "right": "EXACT"},
            }
        ]
        with mock.patch.object(s137.s135, "validate_owner_output", return_value=None):
            runtime.validate_owner_output(output, "C")

    def test_wrapper_refuses_to_replace_unvalidated_packet_contract(self):
        runtime = s137.runtime_for("COG09_HIAGENT_WORKING_MEMORY")
        with mock.patch.object(s137.s135, "packet", side_effect=self.base_packet):
            runtime.packet("BLD-1", "g-test", "20260820", "C", "unit")
            with self.assertRaises(s137.CognitiveRuntimeError):
                runtime.packet("BLD-1", "g-test", "20260821", "C", "unit")


if __name__ == "__main__":
    unittest.main()
