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

    def test_structgpt_adapter_runtime_replays_citations_through_typed_store(self):
        candidate_id = "COG04_STRUCTGPT_TYPED_READS"
        runtime = s137.runtime_for(candidate_id)
        with mock.patch.object(s137.s135, "packet", side_effect=self.base_packet):
            _prompt, packet = runtime.packet("BLD-1", "g-test", "20260820", "C", "unit")
        catalog = packet["s137_cognitive_candidate"]["evidence_catalog"]
        self.assertTrue(all(row["immutable"] and row["status"] == "ACTIVE" for row in catalog))
        with mock.patch.object(s137.s135, "validate_owner_output", return_value=None), mock.patch.object(
            s137.TypedEvidenceStore,
            "read",
            autospec=True,
            wraps=s137.TypedEvidenceStore.read,
        ) as typed_read:
            runtime.validate_owner_output(self.output(candidate_id), "C")
        self.assertEqual(typed_read.call_count, 1)

    def test_structgpt_pending_catalog_is_not_aliased_to_returned_packet(self):
        candidate_id = "COG04_STRUCTGPT_TYPED_READS"
        runtime = s137.runtime_for(candidate_id)
        with mock.patch.object(s137.s135, "packet", side_effect=self.base_packet):
            _prompt, packet = runtime.packet("BLD-1", "g-test", "20260820", "C", "unit")
        key = ("C", "day_forecast")
        original = runtime._pending_catalogs[key][0]["content_hash"]
        packet["s137_cognitive_candidate"]["evidence_catalog"][0]["content_hash"] = "mutated"
        self.assertEqual(runtime._pending_catalogs[key][0]["content_hash"], original)

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

    def test_runtime_exposes_bounded_faithful_ir_hook_without_authority(self):
        payload = {"value": 7}
        runtime = s137.runtime_for("COG05_FAITHFUL_EXECUTABLE_REASONING")
        result = runtime.run_p0_component(
            sources={"source": {"payload": payload, "source_hash": s137.sha256_json(payload)}},
            premises=[{"premise_id": "p", "source_id": "source", "path": ["value"]}],
            program=[{"op": "LOAD", "out": "answer", "premise_id": "p"}],
            final_register="answer",
            baseline_budget={
                "model_calls": 1,
                "input_tokens": 100,
                "output_tokens": 100,
                "tool_queries": 1,
                "storage_bytes": 1000,
                "wall_clock_ms": 1000,
            },
        )
        self.assertEqual(result["status"], "COMPLETED")
        self.assertFalse(result["performance_evidence"])
        self.assertEqual(result["promotion_authority"], "NONE")

    def test_runtime_rejects_p0_hook_for_non_loop_candidate(self):
        with self.assertRaises(s137.CognitiveRuntimeError):
            s137.runtime_for("COG01_COALA_ARCHITECTURE_MAP").run_p0_component()

    def test_runtime_registers_all_bounded_defining_loop_hooks(self):
        self.assertEqual(
            set(s137.P0_COMPONENT_RUNNERS),
            {
                "COG02_REACT_EVIDENCE_LOOP",
                "COG03_LATS_BOUNDED_PLAN_SEARCH",
                "COG04_STRUCTGPT_TYPED_READS",
                "COG05_FAITHFUL_EXECUTABLE_REASONING",
                "COG06_CRITIC_TOOL_VERIFICATION",
                "COG07_MEMORY_AGENT_BENCH",
                "COG08_HIPPORAG_ASSOCIATIVE_RETRIEVAL",
                "COG09_HIAGENT_WORKING_MEMORY",
                "COG10_PROGRESS_COMPRESS_SHADOW_LEARNING",
            },
        )


if __name__ == "__main__":
    unittest.main()
