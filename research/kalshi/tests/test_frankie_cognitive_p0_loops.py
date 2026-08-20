import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frankie_cognition import COGNITIVE_CONTRACT_VERSION, sha256_json  # noqa: E402
from frankie_cognitive_p0_loops import (  # noqa: E402
    BudgetVector,
    CallbackResult,
    P0LoopError,
    execute_faithful_ir,
    run_bounded_react,
    run_chronological_memory_benchmark,
    run_critic_revision,
    run_iterative_structured_reads,
    run_state_aware_working_memory,
)


def budget(**overrides):
    values = {
        "model_calls": 100,
        "input_tokens": 10000,
        "output_tokens": 10000,
        "tool_queries": 100,
        "storage_bytes": 1000000,
        "wall_clock_ms": 100000,
    }
    values.update(overrides)
    return values


def callback(payload, **usage):
    return CallbackResult(payload, BudgetVector(**usage), side_effect_free=True)


class CognitiveP0LoopTests(unittest.TestCase):
    def test_bounded_react_executes_observe_replan_stop(self):
        source_hash = sha256_json({"id": "x"})
        decisions = iter([
            {"kind": "TOOL", "reason": "need evidence", "tool_name": "lookup", "tool_input": {"id": "x"}},
            {"kind": "STOP", "reason": "evidence resolves it", "final": "yes", "source_hashes": [source_hash]},
        ])

        result = run_bounded_react(
            {"question": "q"},
            decide_fn=lambda _: callback(next(decisions), model_calls=1),
            tool_fn=lambda request: callback(
                {
                    "observation": {"value": 1},
                    "read_only": True,
                    "source_hashes": [source_hash],
                },
                tool_queries=1,
            ),
            allowed_tools=["lookup"],
            baseline_budget=budget(),
        )
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["result"]["tool_observations"], 1)
        self.assertEqual(result["result"]["replans"], 1)
        self.assertFalse(result["paper_faithful"])
        self.assertFalse(result["performance_evidence"])
        self.assertFalse(result["removal"]["canonical_state_changed"])

    def test_react_fault_injection_stops_before_tool(self):
        called = []
        result = run_bounded_react(
            {},
            decide_fn=lambda _: callback({
                "kind": "TOOL", "reason": "r", "tool_name": "lookup", "tool_input": {}
            }),
            tool_fn=lambda request: called.append(request),
            allowed_tools=["lookup"],
            baseline_budget=budget(),
            faults=["react.tool:1"],
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(called, [])
        self.assertIn("fault injected", result["reason"])

    def test_structured_reads_are_iterative_and_citation_bound(self):
        catalog = [{
            "ref_id": "r1",
            "source": "unit",
            "value": 7,
            "content_hash": sha256_json(7),
            "immutable": True,
            "status": "ACTIVE",
        }]
        context = {
            "contract_version": COGNITIVE_CONTRACT_VERSION,
            "evidence_catalog": catalog,
            "evidence_catalog_hash": sha256_json(catalog),
        }
        decisions = iter([
            {"kind": "READ", "ref_ids": ["r1"]},
            {"kind": "ANSWER", "answer": 7, "citations": ["r1"]},
        ])
        result = run_iterative_structured_reads(
            context,
            {"question": "value"},
            decide_fn=lambda _: callback(next(decisions), model_calls=1),
            baseline_budget=budget(),
        )
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["result"]["answer"], 7)
        self.assertEqual(len(result["result"]["read_history"]), 1)
        self.assertEqual(result["matched_budget"]["candidate"]["tool_queries"], 1)

    def test_critic_preserves_initial_and_rechecks_revision(self):
        checks = iter([
            {"check_id": "c1", "check_type": "EXACT_EQUAL", "evidence_refs": ["r1"], "inputs": {"left": 1, "right": 2}},
            {"check_id": "c2", "check_type": "EXACT_EQUAL", "evidence_refs": ["r1"], "inputs": {"left": 2, "right": 2}},
        ])
        result = run_critic_revision(
            {"question": "q"},
            initial_fn=lambda _: callback({"answer": 1, "evidence_refs": ["r1"]}, model_calls=1),
            check_fn=lambda _: callback({"checks": [next(checks)]}, tool_queries=1),
            critique_fn=lambda _: callback({"critique": "wrong value", "evidence_refs": ["r1"]}, model_calls=1),
            revise_fn=lambda _: callback({"answer": 2, "evidence_refs": ["r1"]}, model_calls=1),
            allowed_evidence_refs={"r1"},
            baseline_budget=budget(),
        )
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["result"]["final_answer"], 2)
        self.assertEqual(result["result"]["revisions"], 1)
        self.assertNotEqual(
            result["result"]["initial_answer_artifact_hash"],
            result["result"]["final_answer_artifact_hash"],
        )
        self.assertEqual(
            result["result"]["restore_target_hash"],
            result["result"]["initial_answer_artifact_hash"],
        )

    def test_hiagent_state_hides_completed_detail_but_can_retrieve(self):
        commands = [
            {"kind": "START", "subgoal_id": "s1", "objective": "inspect"},
            {"kind": "EVENT", "subgoal_id": "s1", "event_kind": "ACTION", "content": "read", "evidence_refs": ["r1"]},
            {"kind": "EVENT", "subgoal_id": "s1", "event_kind": "OBSERVATION", "content": "value", "evidence_refs": ["r1"]},
            {"kind": "COMPLETE", "subgoal_id": "s1"},
            {"kind": "RETRIEVE", "subgoal_id": "s1", "reason": "verify"},
            {"kind": "STOP"},
        ]

        def summarize(request):
            return callback({
                "summary": "inspected value",
                "covered_event_hashes": [event["event_hash"] for event in request["trajectory"]],
                "evidence_refs": ["r1"],
            }, model_calls=1)

        result = run_state_aware_working_memory(
            commands,
            summarize_fn=summarize,
            allowed_evidence_refs={"r1"},
            baseline_budget=budget(),
        )
        self.assertEqual(result["status"], "COMPLETED")
        visible = result["result"]["visible_context"]
        self.assertIsNone(visible["active_subgoal_id"])
        self.assertTrue(visible["chunks"][0]["details_hidden"])
        self.assertNotIn("trajectory", visible["chunks"][0])
        self.assertTrue(any(item["stage"] == "hiagent.retrieve" for item in result["artifacts"]))

    def test_hiagent_rejects_start_while_active(self):
        result = run_state_aware_working_memory(
            [
                {"kind": "START", "subgoal_id": "s1", "objective": "one"},
                {"kind": "START", "subgoal_id": "s2", "objective": "two"},
            ],
            summarize_fn=lambda _: callback({}),
            allowed_evidence_refs=set(),
            baseline_budget=budget(),
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("another subgoal is active", result["reason"])

    def test_faithful_ir_derives_final_from_source_hashed_premise(self):
        payload = {"price": 12, "limit": 10}
        result = execute_faithful_ir(
            sources={"s": {"payload": payload, "source_hash": sha256_json(payload)}},
            premises=[
                {"premise_id": "price", "source_id": "s", "path": ["price"]},
                {"premise_id": "limit", "source_id": "s", "path": ["limit"]},
            ],
            program=[
                {"op": "LOAD", "out": "p", "premise_id": "price"},
                {"op": "LOAD", "out": "l", "premise_id": "limit"},
                {"op": "GT", "out": "answer", "left": "p", "right": "l"},
            ],
            final_register="answer",
            baseline_budget=budget(),
        )
        self.assertEqual(result["status"], "COMPLETED")
        self.assertIs(result["result"]["final_answer"], True)
        self.assertEqual(result["result"]["premise_dependencies"], ["limit", "price"])
        self.assertTrue(result["result"]["proof"]["proof_hash"])

    def test_faithful_ir_rejects_source_hash_mismatch(self):
        with self.assertRaises(P0LoopError):
            execute_faithful_ir(
                sources={"s": {"payload": {"x": 1}, "source_hash": "0" * 64}},
                premises=[{"premise_id": "x", "source_id": "s", "path": ["x"]}],
                program=[{"op": "LOAD", "out": "x", "premise_id": "x"}],
                final_register="x",
                baseline_budget=budget(),
            )

    def test_chronological_memory_benchmark_scores_all_axes(self):
        axes = [
            "ACCURATE_RETRIEVAL",
            "TEST_TIME_LEARNING",
            "LONG_RANGE_UNDERSTANDING",
            "SELECTIVE_FORGETTING",
        ]
        cases = []
        for index, axis in enumerate(axes):
            old_payload = {"value": "old"}
            new_payload = {"value": axis}
            cases.append({
                "case_id": f"c{index}",
                "competency": axis,
                "chunks": [
                    {"source_id": "old", "observed_at": "2026-01-01T00:00:00Z", "payload": old_payload, "source_hash": sha256_json(old_payload)},
                    {"source_id": "new", "observed_at": "2026-01-02T00:00:00Z", "payload": new_payload, "source_hash": sha256_json(new_payload)},
                ],
                "query_at": "2026-01-03T00:00:00Z",
                "query": {"field": "value"},
                "expected_answer": axis,
                "expected_source_ids": ["new"],
                "forbidden_source_ids": ["old"] if axis == "SELECTIVE_FORGETTING" else [],
            })

        def factory(_case_id):
            state = []

            def adapter(request):
                if request["operation"] == "INGEST":
                    state.append(request["chunk"])
                    return callback({"accepted": True}, storage_bytes=1)
                return callback({
                    "answer": state[-1]["payload"]["value"],
                    "source_ids": [state[-1]["source_id"]],
                    "abstained": False,
                }, tool_queries=1)

            return adapter

        result = run_chronological_memory_benchmark(
            cases,
            adapter_factory=factory,
            baseline_budget=budget(),
        )
        self.assertEqual(result["status"], "COMPLETED")
        self.assertTrue(all(rate == 1.0 for rate in result["result"]["rates"].values()))
        self.assertTrue(result["result"]["benchmark_only"])
        self.assertEqual(result["result"]["memory_architecture"], "NONE")

    def test_callback_must_attest_side_effect_free(self):
        with self.assertRaises(P0LoopError):
            CallbackResult({}, BudgetVector())


if __name__ == "__main__":
    unittest.main()
