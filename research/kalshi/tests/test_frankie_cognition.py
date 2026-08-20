from __future__ import annotations

import dataclasses
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_cognition import (  # noqa: E402
    CognitiveContractError,
    MemoryInvalidation,
    MemoryRecord,
    build_cognitive_context,
    memory_withdrawal_closure,
    select_active_memories,
    sha256_json,
    validate_reasoning_contract,
    validate_working_memory,
)
from frankie_cognitive_candidates import (  # noqa: E402
    TypedEvidenceStore,
    coala_architecture_map,
    rank_associative_memory,
    run_deterministic_check,
    score_memory_competencies,
    select_bounded_plan_branches,
    validate_react_trace,
)
from frankie_cognitive_experiments import (  # noqa: E402
    BUDGET_DIMENSIONS,
    EXPERIMENTS,
    MIN_EVALUATION_CASES,
    MIN_FAIL_TO_PASS_CASES,
    component_contract_canary,
    evaluate_shadow_candidate,
    experiment_manifest,
)


class FrankieCognitionTests(unittest.TestCase):
    @staticmethod
    def context():
        return build_cognitive_context(
            event={
                "event_id": "cognition-unit",
                "candidate_id": "candidate-a",
                "knowable_at": "2026-08-20T12:00:00Z",
                "observed_at": "2026-08-20T12:00:01Z",
                "source_provenance": [
                    {
                        "source": "unit",
                        "knowable_at": "2026-08-20T12:00:00Z",
                        "content_hash": "source-hash",
                    }
                ],
                "contract_identity": {"status": "EXACT"},
                "market_state": {"state": "unit"},
                "causal_state": {"clock_status": "POINT_IN_TIME", "source_fresh": True},
                "cost_state": {"costs_known": True},
            },
            candidate={"id": "candidate-a", "authority": "SHADOW"},
            qualification={"eligible": True, "state": "QUALIFIED"},
            papers=[{"id": "paper-a", "title": "Unit", "url": "https://example.test/paper"}],
        )

    @staticmethod
    def trace_raw():
        return {
            "reasoning_steps": [
                {
                    "step_id": "S1",
                    "action": "RETRIEVE",
                    "claim": "read the exact contract state",
                    "evidence_refs": ["event:contract_identity"],
                    "depends_on": [],
                    "status": "SUPPORTED",
                },
                {
                    "step_id": "S2",
                    "action": "REASON",
                    "claim": "the deterministic qualification is satisfied",
                    "evidence_refs": ["derived:qualification"],
                    "depends_on": ["S1"],
                    "status": "SUPPORTED",
                },
                {
                    "step_id": "S3",
                    "action": "VERIFY",
                    "claim": "the causal clock is point in time",
                    "evidence_refs": ["event:causal_state"],
                    "depends_on": ["S2"],
                    "status": "SUPPORTED",
                },
            ],
            "uncertainty": {
                "level": "MEDIUM",
                "drivers": ["synthetic evidence"],
                "calibrated_probability": None,
            },
        }

    @staticmethod
    def memory(
        memory_id,
        knowable_at,
        *,
        payload=None,
        authority="IMMUTABLE_EVIDENCE",
        influence_parent_ids=None,
    ):
        payload = payload or {"fact": memory_id}
        return MemoryRecord.from_dict(
            {
                "memory_id": memory_id,
                "memory_class": "EPISODIC",
                "created_at": "2026-08-22T13:00:00Z",
                "knowable_at": knowable_at,
                "content_hash": sha256_json(payload),
                "provenance_refs": ["source:0"],
                "influence_parent_ids": influence_parent_ids or [],
                "payload": payload,
                "write_authority": authority,
            }
        )

    def test_coala_map_has_no_execution_or_apply_authority(self):
        mapping = coala_architecture_map()
        self.assertFalse(mapping["execution_enabled"])
        self.assertFalse(mapping["automatic_apply"])
        self.assertEqual(set(mapping["memory"]), {"WORKING", "EPISODIC", "SEMANTIC", "PROCEDURAL"})

    def test_typed_evidence_store_is_hash_bound_and_read_only(self):
        context = self.context()
        store = TypedEvidenceStore(context)
        result = store.read(["event:contract_identity", "derived:qualification"])
        self.assertEqual(result["write_authority"], "NONE")
        self.assertEqual(len(result["records"]), 2)
        self.assertFalse(hasattr(store, "write"))
        with self.assertRaises(CognitiveContractError):
            store.read(["event:missing"])

    def test_future_evidence_is_rejected_from_cognitive_context(self):
        context = self.context()
        catalog = context["evidence_catalog"]
        self.assertEqual(context["evidence_catalog_hash"], sha256_json(catalog))
        with self.assertRaises(CognitiveContractError):
            build_cognitive_context(
                event={
                    "observed_at": "2026-08-20T12:00:00Z",
                    "knowable_at": "2026-08-20T12:00:00Z",
                    "source_provenance": [
                        {
                            "source": "future",
                            "knowable_at": "2026-08-21T12:00:00Z",
                            "content_hash": "future",
                        }
                    ],
                    "contract_identity": {},
                    "market_state": {},
                    "causal_state": {},
                    "cost_state": {},
                },
                candidate={"id": "candidate-a"},
                qualification={"eligible": False},
                papers=[],
            )

    def test_reasoning_trace_is_evidence_bound_and_react_uses_retrieval(self):
        context = self.context()
        steps, uncertainty, trace_hash = validate_reasoning_contract(
            self.trace_raw(),
            allowed_evidence_refs=set(context["evidence_ref_ids"]),
        )
        self.assertEqual(uncertainty.level, "MEDIUM")
        self.assertTrue(trace_hash)
        self.assertTrue(validate_react_trace(steps)["valid"])
        broken = self.trace_raw()
        broken["reasoning_steps"][1]["depends_on"] = []
        steps, _, _ = validate_reasoning_contract(
            broken,
            allowed_evidence_refs=set(context["evidence_ref_ids"]),
        )
        with self.assertRaises(CognitiveContractError):
            validate_react_trace(steps)

    def test_bounded_plan_search_requires_external_feedback(self):
        rows = [
            {
                "branch_id": "root",
                "parent_id": None,
                "depth": 0,
                "external_score": 0.5,
                "feedback_refs": ["derived:qualification"],
                "status": "SUPPORTED",
            },
            {
                "branch_id": "child",
                "parent_id": "root",
                "depth": 1,
                "external_score": 0.8,
                "feedback_refs": ["event:causal_state"],
                "status": "SUPPORTED",
            },
        ]
        self.assertEqual(
            select_bounded_plan_branches(rows, max_width=2, max_depth=2)["value_owner"],
            "EXTERNAL_FEEDBACK_ONLY",
        )
        rows[1]["self_score"] = 1.0
        with self.assertRaises(CognitiveContractError):
            select_bounded_plan_branches(rows)

    def test_faithful_deterministic_check_never_authorizes_execution(self):
        result = run_deterministic_check(
            {
                "check_id": "clock",
                "check_type": "TIMESTAMP_NOT_AFTER",
                "evidence_refs": ["source:0"],
                "inputs": {"left": "2026-08-20T12:00:00Z", "right": "2026-08-20T12:00:01Z"},
            }
        )
        self.assertEqual(result["status"], "SUPPORTED")
        self.assertEqual(result["execution_authority"], "NONE")

    def test_memory_selection_excludes_future_and_invalidated_without_deleting(self):
        active = self.memory("active", "2026-08-20T12:00:00Z")
        stale = self.memory("stale", "2026-08-20T11:00:00Z")
        future = self.memory("future", "2026-08-21T11:00:00Z")
        invalidation = MemoryInvalidation.from_dict(
            {
                "memory_id": "stale",
                "invalidated_at": "2026-08-20T12:30:00Z",
                "reason": "resolved correction",
                "evidence_refs": ["outcome:1"],
            }
        )
        selection = select_active_memories(
            [active, stale, future],
            invalidations=[invalidation],
            decision_at="2026-08-20T13:00:00Z",
        )
        self.assertEqual([record.memory_id for record in selection.selected], ["active"])
        reasons = {item["memory_id"]: item["reason"] for item in selection.excluded}
        self.assertEqual(reasons["stale"], "INVALIDATED")
        self.assertEqual(reasons["future"], "FUTURE_AT_DECISION")
        self.assertEqual(len([active, stale, future]), 3)

    def test_memory_invalidation_withdraws_all_declared_descendants(self):
        source = self.memory("source", "2026-08-20T10:00:00Z")
        summary = self.memory(
            "summary",
            "2026-08-20T11:00:00Z",
            influence_parent_ids=["source"],
        )
        procedure = self.memory(
            "procedure",
            "2026-08-20T12:00:00Z",
            influence_parent_ids=["summary"],
        )
        unrelated = self.memory("unrelated", "2026-08-20T12:30:00Z")
        invalidation = MemoryInvalidation.from_dict(
            {
                "memory_id": "source",
                "invalidated_at": "2026-08-20T13:00:00Z",
                "reason": "source correction",
                "evidence_refs": ["outcome:correction"],
            }
        )
        direct, withdrawn = memory_withdrawal_closure(
            [source, summary, procedure, unrelated],
            invalidations=[invalidation],
            decision_at="2026-08-20T14:00:00Z",
        )
        self.assertEqual(direct, {"source"})
        self.assertEqual(withdrawn, {"source", "summary", "procedure"})
        selection = select_active_memories(
            [source, summary, procedure, unrelated],
            invalidations=[invalidation],
            decision_at="2026-08-20T14:00:00Z",
        )
        self.assertEqual([record.memory_id for record in selection.selected], ["unrelated"])
        reasons = {item["memory_id"]: item["reason"] for item in selection.excluded}
        self.assertEqual(reasons["source"], "INVALIDATED")
        self.assertEqual(reasons["summary"], "ANCESTOR_INVALIDATED")
        self.assertEqual(reasons["procedure"], "ANCESTOR_INVALIDATED")

    def test_memory_influence_lineage_rejects_unknown_parent_and_cycles(self):
        orphan = self.memory(
            "orphan",
            "2026-08-20T12:00:00Z",
            influence_parent_ids=["missing"],
        )
        with self.assertRaises(CognitiveContractError):
            memory_withdrawal_closure(
                [orphan],
                invalidations=[],
                decision_at="2026-08-20T14:00:00Z",
            )
        a = self.memory(
            "a",
            "2026-08-20T12:00:00Z",
            influence_parent_ids=["b"],
        )
        b = self.memory(
            "b",
            "2026-08-20T12:00:00Z",
            influence_parent_ids=["a"],
        )
        with self.assertRaises(CognitiveContractError):
            memory_withdrawal_closure(
                [a, b],
                invalidations=[],
                decision_at="2026-08-20T14:00:00Z",
            )

    def test_memory_scorecard_keeps_all_four_competencies_separate(self):
        competencies = (
            "ACCURATE_RETRIEVAL",
            "TEST_TIME_LEARNING",
            "LONG_RANGE_UNDERSTANDING",
            "SELECTIVE_FORGETTING",
        )
        rows = [
            {
                "case_id": name.lower(),
                "competency": name,
                "passed": True,
                "provenance_ok": True,
                "obsolete_memory_used": False,
            }
            for name in competencies
        ]
        score = score_memory_competencies(rows)
        self.assertEqual(score["verdict"], "COMPONENT_GATE_PASSED")
        rows[-1]["obsolete_memory_used"] = True
        self.assertEqual(score_memory_competencies(rows)["verdict"], "REJECT")

    def test_associative_retrieval_serves_active_nodes_only_and_claims_no_causality(self):
        result = rank_associative_memory(
            node_ids=["a", "b", "stale"],
            edges=[
                {"source": "a", "target": "b", "weight": 1.0},
                {"source": "b", "target": "stale", "weight": 100.0},
            ],
            seed_ids=["a"],
            active_ids={"a", "b"},
            top_k=2,
        )
        self.assertNotIn("stale", result["ranked_ids"])
        self.assertFalse(result["causal_claim"])

    def test_working_memory_has_at_most_one_active_subgoal(self):
        chunks = [
            {
                "subgoal_id": "collect",
                "status": "ACTIVE",
                "summary": "collect current evidence",
                "evidence_refs": ["source:0"],
                "depends_on": [],
            },
            {
                "subgoal_id": "verify",
                "status": "PENDING",
                "summary": "verify the clock",
                "evidence_refs": ["event:causal_state"],
                "depends_on": ["collect"],
            },
        ]
        validated, chunk_hash = validate_working_memory(
            chunks,
            allowed_evidence_refs=set(self.context()["evidence_ref_ids"]),
        )
        self.assertEqual(len(validated), 2)
        self.assertTrue(chunk_hash)
        chunks[1]["status"] = "ACTIVE"
        with self.assertRaises(CognitiveContractError):
            validate_working_memory(
                chunks,
                allowed_evidence_refs=set(self.context()["evidence_ref_ids"]),
            )

    @staticmethod
    def shadow_rows(experiment):
        baseline_metrics = {rule.name: 0.5 for rule in experiment.metric_rules}
        candidate_metrics = {
            rule.name: (0.6 if rule.direction == "HIGHER" else 0.4)
            for rule in experiment.metric_rules
        }
        budget = {dimension: 100.0 for dimension in BUDGET_DIMENSIONS}
        strata = {
            "task": "unit",
            "regime": "synthetic",
            "safety": "standard",
            "provenance": "complete",
        }
        rows = []
        for index in range(MIN_EVALUATION_CASES):
            correction = index < MIN_FAIL_TO_PASS_CASES
            protected = MIN_FAIL_TO_PASS_CASES <= index < (2 * MIN_FAIL_TO_PASS_CASES)
            rows.append(
                {
                    "case_id": f"case-{index:02d}",
                    "baseline_pass": not correction,
                    "candidate_pass": True,
                    "candidate_catastrophic": False,
                    "protected": protected,
                    "strata": {**strata, "safety": "protected" if protected else "standard"},
                    "baseline_budget": budget,
                    "candidate_budget": budget,
                    "baseline_metrics": baseline_metrics,
                    "candidate_metrics": candidate_metrics,
                }
            )
        return rows

    def test_all_ten_experiments_have_executable_matched_budget_gates(self):
        manifest = experiment_manifest()
        self.assertEqual(len(manifest["candidates"]), 10)
        self.assertFalse(manifest["execution_enabled"])
        self.assertFalse(manifest["automatic_apply"])
        self.assertTrue(all("implementation_audit" in row for row in manifest["candidates"]))
        self.assertEqual(
            next(
                row for row in manifest["candidates"]
                if row["candidate_id"] == "COG10_PROGRESS_COMPRESS_SHADOW_LEARNING"
            )["implementation_audit"]["depth"],
            "RELEASE_GATE_ONLY",
        )
        for experiment in EXPERIMENTS:
            with self.subTest(candidate=experiment.candidate_id):
                result = evaluate_shadow_candidate(
                    experiment.candidate_id,
                    self.shadow_rows(experiment),
                )
                self.assertEqual(result["verdict"], "COMPONENT_GATE_PASSED")
                self.assertEqual(result["next_gate"], "UNTOUCHED_FORWARD_SHADOW")
                self.assertEqual(result["promotion_authority"], "NONE")

    def test_all_ten_component_contract_canary_is_explicitly_not_performance_evidence(self):
        result = component_contract_canary()
        self.assertEqual(result["candidates_exercised"], 10)
        self.assertTrue(result["all_component_contracts_passed"])
        self.assertFalse(result["performance_evidence"])

    def test_shadow_gate_rejects_budget_overrun_and_pass_to_fail(self):
        experiment = EXPERIMENTS[0]
        rows = self.shadow_rows(experiment)
        rows[0]["candidate_budget"] = {
            **rows[0]["candidate_budget"],
            "model_calls": 200.0,
        }
        rows[MIN_FAIL_TO_PASS_CASES]["candidate_pass"] = False
        result = evaluate_shadow_candidate(experiment.candidate_id, rows)
        self.assertEqual(result["verdict"], "REJECT")
        self.assertEqual(result["pass_to_fail"], 1)
        self.assertTrue(result["budget_violations"])

    def test_shadow_gate_rejects_tiny_or_under_supported_evidence(self):
        experiment = EXPERIMENTS[0]
        rows = self.shadow_rows(experiment)[:2]
        result = evaluate_shadow_candidate(experiment.candidate_id, rows)
        self.assertEqual(result["verdict"], "REJECT")
        self.assertTrue(any("insufficient cases" in blocker for blocker in result["blockers"]))


if __name__ == "__main__":
    unittest.main()
