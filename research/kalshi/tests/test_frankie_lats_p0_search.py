import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frankie_cognition import sha256_json  # noqa: E402
from frankie_cognitive_p0_loops import BudgetVector, CallbackResult  # noqa: E402
from frankie_lats_p0_search import (  # noqa: E402
    LATSContractError,
    compare_tree_to_one_path_control,
    run_bounded_lats_search,
    verify_lats_replay,
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


def feedback_catalog(include_future=False):
    payload = {"signal": "observed", "strength": 2}
    rows = [{
        "ref_id": "f1",
        "payload": payload,
        "source_hash": sha256_json(payload),
        "observed_at": "2026-01-01T00:00:00Z",
        "reveal_at": "2026-01-01T00:00:00Z",
        "immutable": True,
        "status": "ACTIVE",
    }]
    if include_future:
        future = {"resolved": "future-only"}
        rows.append({
            "ref_id": "future",
            "payload": future,
            "source_hash": sha256_json(future),
            "observed_at": "2026-02-01T00:00:00Z",
            "reveal_at": "2026-02-01T00:00:00Z",
            "immutable": True,
            "status": "ACTIVE",
        })
    return rows


def callbacks(*, reverse=False, changed=False, bad_lineage=False):
    generation = {"count": 0}

    def expand(request):
        generation["count"] += 1
        lineage = request["reflection_lineage"]
        if bad_lineage and generation["count"] == 2:
            lineage = []
        suffix = "changed" if changed else "base"
        candidates = [
            {
                "candidate_id": f"a{generation['count']}",
                "hypothesis": f"alpha-{generation['count']}-{suffix}",
                "action": {"kind": "INSPECT", "side": "alpha"},
                "planned_feedback_refs": ["f1"],
                "used_reflection_hashes": lineage,
            },
            {
                "candidate_id": f"b{generation['count']}",
                "hypothesis": f"beta-{generation['count']}",
                "action": {"kind": "INSPECT", "side": "beta"},
                "planned_feedback_refs": ["f1"],
                "used_reflection_hashes": lineage,
            },
        ]
        if reverse:
            candidates.reverse()
        return callback({"source_parent_id": request["parent"]["node_id"], "candidates": candidates}, model_calls=1)

    def simulate(_request):
        return callback({
            "read_only": True,
            "feedback_refs": ["f1"],
            "simulation_status": "SUPPORTED",
            "terminal": False,
            "uses_unrevealed_outcome": False,
        }, tool_queries=1)

    def value(request):
        score = 0.8 if request["hypothesis"].startswith("alpha") else 0.2
        return callback({"value": score, "reason": "source-bound heuristic", "feedback_refs": ["f1"]}, model_calls=1)

    def reflect(request):
        return callback({
            "source_node_id": request["node_id"],
            "reflection": "retain the supported evidence and localize the next check",
            "feedback_refs": ["f1"],
            "next_constraints": ["cite f1"],
        }, model_calls=1)

    return expand, simulate, value, reflect


def run_search(*, mode="TREE", reverse=False, changed=False, bad_lineage=False, iterations=2, **kwargs):
    expand, simulate, value, reflect = callbacks(
        reverse=reverse,
        changed=changed,
        bad_lineage=bad_lineage,
    )
    return run_bounded_lats_search(
        {"question": "which causal hypothesis survives?"},
        feedback_catalog(),
        cutoff_at="2026-01-02T00:00:00Z",
        expand_fn=expand,
        simulate_fn=simulate,
        value_fn=value,
        reflect_fn=reflect,
        baseline_budget=budget(),
        max_depth=3,
        max_width=2,
        iterations=iterations,
        seed=17,
        mode=mode,
        **kwargs,
    )


class FrankieLATSP0SearchTests(unittest.TestCase):
    def test_tree_runs_all_defining_stages_and_preserves_hypotheses(self):
        result = run_search()
        self.assertEqual(result["status"], "COMPLETED")
        stages = {artifact["stage"] for artifact in result["artifacts"]}
        self.assertTrue({
            "lats.select", "lats.expand", "lats.simulate", "lats.value",
            "lats.reflect", "lats.backprop",
        } <= stages)
        self.assertGreaterEqual(len(result["result"]["live_hypotheses"]), 4)
        self.assertTrue(result["result"]["ancestry_audit"]["ancestry_closed"])
        self.assertEqual(result["result"]["completed_iterations"], 2)
        self.assertFalse(result["paper_faithful"])
        self.assertFalse(result["performance_evidence"])
        self.assertEqual(result["promotion_authority"], "NONE")
        self.assertFalse(result["removal"]["canonical_state_changed"])

        nodes = {row["node_id"]: row for row in result["result"]["nodes"]}
        deep = [row for row in nodes.values() if row["depth"] == 2]
        self.assertTrue(deep)
        for row in deep:
            parent = nodes[row["parent_id"]]
            self.assertEqual(
                row["reflection_lineage"][:-1],
                parent["reflection_lineage"],
            )
            self.assertEqual(len(row["reflection_lineage"]), 2)

    def test_budget_overrun_fails_closed_with_removal_receipt(self):
        expand, simulate, value, reflect = callbacks()
        result = run_bounded_lats_search(
            {"question": "q"}, feedback_catalog(),
            cutoff_at="2026-01-02T00:00:00Z",
            expand_fn=expand, simulate_fn=simulate, value_fn=value, reflect_fn=reflect,
            baseline_budget=budget(model_calls=1),
            max_depth=2, max_width=2, iterations=1,
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("matched budget", result["reason"])
        self.assertTrue(result["removal"]["removal_receipt_hash"])
        self.assertFalse(result["removal"]["canonical_state_changed"])

    def test_callback_order_is_canonical_and_changed_replay_is_detected(self):
        forward = run_search(iterations=1)
        reverse = run_search(iterations=1, reverse=True)
        receipt = verify_lats_replay(forward, reverse)
        self.assertTrue(receipt["deterministic"])
        self.assertFalse(receipt["performance_evidence"])

        changed = run_search(iterations=1, changed=True)
        with self.assertRaisesRegex(LATSContractError, "nondeterministic"):
            verify_lats_replay(forward, changed)

    def test_orphan_parent_is_rejected(self):
        _expand, simulate, value, reflect = callbacks()

        def orphan(_request):
            return callback({
                "source_parent_id": "missing",
                "candidates": [{
                    "candidate_id": "x", "hypothesis": "h", "action": {"kind": "READ"},
                    "planned_feedback_refs": ["f1"], "used_reflection_hashes": [],
                }],
            }, model_calls=1)

        result = run_bounded_lats_search(
            {"question": "q"}, feedback_catalog(), cutoff_at="2026-01-02T00:00:00Z",
            expand_fn=orphan, simulate_fn=simulate, value_fn=value, reflect_fn=reflect,
            baseline_budget=budget(), max_depth=2, max_width=2, iterations=1,
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("orphan", result["reason"])

    def test_width_pruned_candidate_never_becomes_a_live_node(self):
        _expand, simulate, value, reflect = callbacks()

        def expand_three(request):
            rows = [{
                "candidate_id": candidate_id,
                "hypothesis": f"hypothesis-{candidate_id}",
                "action": {"kind": "READ"},
                "planned_feedback_refs": ["f1"],
                "used_reflection_hashes": request["reflection_lineage"],
            } for candidate_id in ("x", "y", "z")]
            return callback({"source_parent_id": request["parent"]["node_id"], "candidates": rows}, model_calls=1)

        result = run_bounded_lats_search(
            {"question": "q"}, feedback_catalog(), cutoff_at="2026-01-02T00:00:00Z",
            expand_fn=expand_three, simulate_fn=simulate, value_fn=value, reflect_fn=reflect,
            baseline_budget=budget(), max_depth=2, max_width=2, iterations=1, seed=9,
        )
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(len(result["result"]["pruned_candidate_hashes"]), 1)
        self.assertEqual(len([n for n in result["result"]["nodes"] if n["depth"] == 1]), 2)
        self.assertTrue(result["result"]["ancestry_audit"]["ancestry_closed"])

    def test_unrevealed_feedback_is_never_materialized(self):
        expand, _simulate, value, reflect = callbacks()

        def leak(_request):
            return callback({
                "read_only": True,
                "feedback_refs": ["future"],
                "simulation_status": "SUPPORTED",
                "terminal": False,
                "uses_unrevealed_outcome": False,
            }, tool_queries=1)

        result = run_bounded_lats_search(
            {"question": "q"}, feedback_catalog(include_future=True),
            cutoff_at="2026-01-02T00:00:00Z",
            expand_fn=expand, simulate_fn=leak, value_fn=value, reflect_fn=reflect,
            baseline_budget=budget(), max_depth=2, max_width=2, iterations=1,
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("forbidden or unrevealed", result["reason"])
        self.assertEqual(result["result"]["feedback_cutoff_receipt"]["withheld_ref_ids"], ["future"])
        serialized = str(result["artifacts"])
        self.assertNotIn("future-only", serialized)

    def test_forbidden_feedback_field_is_rejected(self):
        expand, _simulate, value, reflect = callbacks()

        def leaked_payload(_request):
            return callback({
                "read_only": True, "feedback_refs": ["f1"], "simulation_status": "SUPPORTED",
                "terminal": False, "uses_unrevealed_outcome": False, "ground_truth": "leak",
            }, tool_queries=1)

        result = run_bounded_lats_search(
            {"question": "q"}, feedback_catalog(), cutoff_at="2026-01-02T00:00:00Z",
            expand_fn=expand, simulate_fn=leaked_payload, value_fn=value, reflect_fn=reflect,
            baseline_budget=budget(), max_depth=2, max_width=2, iterations=1,
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("forbidden or unknown", result["reason"])

    def test_callback_input_mutation_and_exception_fail_closed(self):
        _expand, simulate, value, reflect = callbacks()

        def mutating(request):
            request["path_node_ids"].append("tampered")
            return callback({"source_parent_id": request["parent"]["node_id"], "candidates": []}, model_calls=1)

        mutated = run_bounded_lats_search(
            {"question": "q"}, feedback_catalog(), cutoff_at="2026-01-02T00:00:00Z",
            expand_fn=mutating, simulate_fn=simulate, value_fn=value, reflect_fn=reflect,
            baseline_budget=budget(), max_depth=2, max_width=2, iterations=1,
        )
        self.assertEqual(mutated["status"], "REJECTED")
        self.assertIn("mutated its input", mutated["reason"])

        expand, _simulate, value, reflect = callbacks()
        exceptional = run_bounded_lats_search(
            {"question": "q"}, feedback_catalog(), cutoff_at="2026-01-02T00:00:00Z",
            expand_fn=expand,
            simulate_fn=lambda _request: (_ for _ in ()).throw(RuntimeError("boom")),
            value_fn=value, reflect_fn=reflect,
            baseline_budget=budget(), max_depth=2, max_width=2, iterations=1,
        )
        self.assertEqual(exceptional["status"], "REJECTED")
        self.assertIn("callback failed", exceptional["reason"])

    def test_callback_side_effect_attestation_is_rechecked_at_boundary(self):
        _expand, simulate, value, reflect = callbacks()

        def revoked_attestation(request):
            result = callback({
                "source_parent_id": request["parent"]["node_id"],
                "candidates": [{
                    "candidate_id": candidate_id,
                    "hypothesis": candidate_id,
                    "action": {"kind": "READ"},
                    "planned_feedback_refs": ["f1"],
                    "used_reflection_hashes": request["reflection_lineage"],
                } for candidate_id in ("a", "b")],
            }, model_calls=1)
            object.__setattr__(result, "side_effect_free", False)
            return result

        result = run_bounded_lats_search(
            {"question": "q"}, feedback_catalog(), cutoff_at="2026-01-02T00:00:00Z",
            expand_fn=revoked_attestation, simulate_fn=simulate, value_fn=value, reflect_fn=reflect,
            baseline_budget=budget(), max_depth=2, max_width=2, iterations=1,
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("side_effect_free", result["reason"])

    def test_reflection_lineage_must_feed_deeper_generation(self):
        result = run_search(bad_lineage=True)
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("reflection lineage mismatch", result["reason"])

    def test_fault_injection_removes_disposable_partial_tree(self):
        result = run_search(iterations=1, faults=["lats.simulate:1"])
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("fault injected", result["reason"])
        self.assertTrue(any(event["event"] == "FAULT_INJECTED" for event in result["events"]))
        self.assertEqual(result["promotion_authority"], "NONE")
        self.assertFalse(result["removal"]["canonical_state_changed"])

    def test_one_path_control_can_be_six_dimension_budget_matched(self):
        def make(mode):
            calls = {"generation": 0}

            def expand(request):
                calls["generation"] += 1
                rows = [{
                    "candidate_id": candidate_id,
                    "hypothesis": candidate_id,
                    "action": {"kind": "READ"},
                    "planned_feedback_refs": ["f1"],
                    "used_reflection_hashes": request["reflection_lineage"],
                } for candidate_id in ("a", "b")]
                model_calls = 1 if mode == "TREE" else 3
                return callback({"source_parent_id": request["parent"]["node_id"], "candidates": rows}, model_calls=model_calls)

            def simulate(_request):
                queries = 1 if mode == "TREE" else 2
                return callback({
                    "read_only": True, "feedback_refs": ["f1"], "simulation_status": "SUPPORTED",
                    "terminal": False, "uses_unrevealed_outcome": False,
                }, tool_queries=queries)

            def value(request):
                return callback({"value": 0.5, "reason": "heuristic", "feedback_refs": ["f1"]}, model_calls=1)

            def reflect(request):
                return callback({
                    "source_node_id": request["node_id"], "reflection": "r",
                    "feedback_refs": ["f1"], "next_constraints": [],
                }, model_calls=1)

            return run_bounded_lats_search(
                {"question": "q"}, feedback_catalog(), cutoff_at="2026-01-02T00:00:00Z",
                expand_fn=expand, simulate_fn=simulate, value_fn=value, reflect_fn=reflect,
                baseline_budget=budget(), max_depth=2, max_width=2, iterations=1, seed=7, mode=mode,
            )

        tree = make("TREE")
        control = make("ONE_PATH_CONTROL")
        receipt = compare_tree_to_one_path_control(tree, control)
        self.assertTrue(receipt["six_dimensions_matched"])
        self.assertFalse(receipt["performance_evidence"])
        self.assertEqual(control["result"]["effective_width"], 1)


if __name__ == "__main__":
    unittest.main()
