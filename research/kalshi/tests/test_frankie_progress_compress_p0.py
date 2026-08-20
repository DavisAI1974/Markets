from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_progress_compress_p0 import (  # noqa: E402
    ProgressCompressP0Error,
    ResourceUsage,
    ShadowCallbackResult,
    build_release_firewall_receipt,
    run_progress_compress_shadow,
)


def sha_json(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def self_hash(core, field):
    return {**core, field: sha_json(core)}


def callback_result(payload, artifacts, **usage):
    return ShadowCallbackResult(
        payload=payload,
        artifacts=artifacts,
        usage=ResourceUsage(**usage),
        isolated=True,
        side_effect_free=True,
        permanent_state_mutated=False,
        release_data_accessed=False,
    )


class Fixture:
    def __init__(self):
        self.protected = {
            "weights": b"permanent-frozen-weights",
            "features": b"permanent-frozen-features",
        }
        self.expected = {key: sha_bytes(value) for key, value in self.protected.items()}
        self.task = {
            "task_id": "regime-2",
            "opened_at": "2026-08-01T00:00:00Z",
            "label_revealed_at": "2026-08-02T00:00:00Z",
            "progress_at": "2026-08-02T00:00:00Z",
            "compress_at": "2026-08-03T00:00:00Z",
            "evaluation_at": "2026-08-04T00:00:00Z",
            "release_at": "2026-09-01T00:00:00Z",
            "training_manifest_sha256": "a" * 64,
            "new_task_evaluation_manifest_sha256": "b" * 64,
            "release_manifest_sha256": "c" * 64,
            "required_parameter_ids": ["p_feature", "p_weight"],
            "ewc_parameters": {
                "p_feature": {"anchor": 0.2, "fisher": 0.5, "source_artifact_id": "features"},
                "p_weight": {"anchor": -0.1, "fisher": 2.0, "source_artifact_id": "weights"},
            },
            "new_task_min_rows": 5,
            "new_task_higher_is_better": True,
            "minimum_new_task_improvement": 0.05,
        }
        self.cohorts = [
            {
                "cohort_id": "old-a",
                "stratum": "normal",
                "case_manifest_sha256": "d" * 64,
                "min_rows": 5,
                "higher_is_better": True,
            },
            {
                "cohort_id": "old-b",
                "stratum": "stress",
                "case_manifest_sha256": "f" * 64,
                "min_rows": 5,
                "higher_is_better": False,
            },
        ]
        budget = {
            "model_calls": 100,
            "input_tokens": 10000,
            "output_tokens": 10000,
            "tool_queries": 100,
            "storage_bytes": 1000000,
            "wall_clock_ms": 100000,
        }
        self.budgets = {
            "FROZEN_BASELINE": dict(budget),
            "PROGRESS_COMPRESS_CANDIDATE": dict(budget),
        }
        self.evaluator_hash = "e" * 64
        evaluator_core = {
            "judge_id": "locked-objective-evaluator",
            "judge_version_hash": self.evaluator_hash,
            "canary_manifest_hash": "1" * 64,
            "case_set_hash": "2" * 64,
            "cases": 100,
            "rates": {
                "order_flip_rate": 0.0,
                "length_control_flip_rate": 0.0,
                "truth_disagreement_rate": 0.0,
            },
            "tolerances": {
                "order_flip_rate": 0.01,
                "length_control_flip_rate": 0.01,
                "truth_disagreement_rate": 0.05,
            },
            "verdict": "JUDGE_AUTHORITY_RETAINED",
            "blockers": [],
            "promotion_authority": "NONE",
        }
        self.evaluator_receipt = self_hash(evaluator_core, "canary_hash")
        contamination_core = {
            "status": "VALIDATOR_OR_EVALUATION_HELPER_NOT_RUNTIME_MODEL",
            "verdict": "PASS",
            "bindings": {
                "precommit_hash": "3" * 64,
                "adaptive_search_manifest_hash": "4" * 64,
                "planted_null_manifest_hash": "5" * 64,
                "locked_evaluator_hash": self.evaluator_hash,
            },
            "row_hash": "6" * 64,
            "policy": {
                "min_trials": 10,
                "max_false_selection_rate": 0.5,
                "confidence_z": 1.96,
            },
            "policy_hash": sha_json(
                {
                    "min_trials": 10,
                    "max_false_selection_rate": 0.5,
                    "confidence_z": 1.96,
                }
            ),
            "trial_count": 10,
            "false_selection_count": 0,
            "false_selection_rate": 0.0,
            "false_selection_wilson_upper": 0.2775,
            "declared_parent_hash_separation": True,
            "blockers": [],
        }
        self.contamination_receipt = self_hash(contamination_core, "receipt_hash")
        self.release_receipt = build_release_firewall_receipt(
            task_release_manifest_sha256={"regime-2": self.task["release_manifest_sha256"]},
            locked_evaluator_hash=self.evaluator_hash,
        )
        self.post_regression = False
        self.omit_post_cell = False
        self.corrupt_rollback = False
        self.mutate_protected = False
        self.leak_release = False
        self.drop_ewc_binding = False

    def progress(self, context):
        if self.mutate_protected:
            self.protected["weights"] = b"illicit-permanent-mutation"
        accesses = [sha_bytes(context["protected_feature_artifacts"]["weights"]), context["training_manifest_sha256"]]
        if self.leak_release:
            accesses.append(self.task["release_manifest_sha256"])
        return callback_result(
            {
                "operation": "PROGRESS",
                "task_id": context["task_id"],
                "observed_at": context["observed_at"],
                "active_column_artifact_ids": ["active-column"],
                "lateral_accesses": [
                    {
                        "artifact_id": "weights",
                        "content_sha256": sha_bytes(context["protected_feature_artifacts"]["weights"]),
                    }
                ],
                "accessed_artifact_hashes": accesses,
            },
            {"active-column": b"disposable-active-column"},
            model_calls=1,
            input_tokens=10,
            output_tokens=10,
            storage_bytes=10,
            wall_clock_ms=1,
        )

    def teacher(self, context):
        target = b"teacher-distillation-targets"
        return callback_result(
            {
                "operation": "TEACHER_TARGETS",
                "task_id": context["task_id"],
                "observed_at": context["observed_at"],
                "teacher_target_artifact_id": "teacher-targets",
                "teacher_target_sha256": sha_bytes(target),
                "accessed_artifact_hashes": [
                    sha_bytes(next(iter(context["active_column"].values()))),
                    sha_bytes(context["protected_knowledge_base"]["weights"]),
                    context["training_manifest_sha256"],
                ],
            },
            {"teacher-targets": target},
            model_calls=1,
            input_tokens=10,
            output_tokens=10,
            storage_bytes=10,
            wall_clock_ms=1,
        )

    def compress(self, context):
        candidate = {
            key: value + b"|compressed:" + context["task_id"].encode("utf-8")
            for key, value in context["current_shadow_knowledge_base"].items()
        }
        parameter_ids = sorted(context["ewc_manifest"]["parameters"])
        if self.drop_ewc_binding:
            parameter_ids.pop()
        return callback_result(
            {
                "operation": "COMPRESS_PROPOSAL",
                "task_id": context["task_id"],
                "observed_at": context["observed_at"],
                "teacher_target_sha256": context["teacher_target_sha256"],
                "ewc_manifest_sha256": context["ewc_manifest_sha256"],
                "protected_parameter_ids": parameter_ids,
                "distillation_applied": True,
                "ewc_anchor_applied": True,
                "candidate_kb_artifact_ids": sorted(candidate),
                "accessed_artifact_hashes": [
                    context["teacher_target_sha256"],
                    context["ewc_manifest_sha256"],
                    sha_bytes(next(iter(context["active_column"].values()))),
                ],
            },
            candidate,
            model_calls=1,
            input_tokens=10,
            output_tokens=10,
            storage_bytes=10,
            wall_clock_ms=1,
        )

    def evaluate(self, context):
        artifacts = {"evaluation-receipt": f"{context['operation']}:{context.get('evaluation_role', context.get('arm'))}".encode()}
        if context["operation"] == "EVALUATE_PROTECTED":
            is_post = context["evaluation_role"] == "POST"
            cells = []
            for index, cohort in enumerate(context["protected_cohorts"]):
                if is_post and self.omit_post_cell and index == 1:
                    continue
                base_metric = 0.90 if cohort["higher_is_better"] else 0.10
                metric = base_metric
                if is_post and self.post_regression and index == 0:
                    metric = 0.89
                cells.append(
                    {
                        "cohort_id": cohort["cohort_id"],
                        "stratum": cohort["stratum"],
                        "case_manifest_sha256": cohort["case_manifest_sha256"],
                        "row_count": 5,
                        "higher_is_better": cohort["higher_is_better"],
                        "metric": metric,
                    }
                )
            payload = {
                "operation": "EVALUATE_PROTECTED",
                "evaluation_role": context["evaluation_role"],
                "task_id": context["task_id"],
                "observed_at": context["observed_at"],
                "cells": cells,
                "accessed_artifact_hashes": [
                    *(sha_bytes(value) for value in context["knowledge_base"].values()),
                    *(cohort["case_manifest_sha256"] for cohort in context["protected_cohorts"]),
                ],
            }
        else:
            payload = {
                "operation": "EVALUATE_NEW_TASK",
                "arm": context["arm"],
                "task_id": context["task_id"],
                "observed_at": context["observed_at"],
                "case_manifest_sha256": context["case_manifest_sha256"],
                "row_count": 5,
                "higher_is_better": True,
                "metric": 0.60 if context["arm"] == "FROZEN_BASELINE" else 0.70,
                "accessed_artifact_hashes": [
                    *(sha_bytes(value) for value in context["knowledge_base"].values()),
                    context["case_manifest_sha256"],
                ],
            }
        return callback_result(
            payload,
            artifacts,
            model_calls=1,
            input_tokens=5,
            output_tokens=5,
            storage_bytes=5,
            wall_clock_ms=1,
        )

    def rollback(self, context):
        artifacts = (
            dict(context["candidate_shadow_knowledge_base"])
            if self.corrupt_rollback
            else {
                "weights": b"permanent-frozen-weights",
                "features": b"permanent-frozen-features",
            }
        )
        return callback_result(
            {
                "operation": "ROLLBACK",
                "task_id": context["task_id"],
                "observed_at": context["observed_at"],
                "byte_exact_requested": True,
                "accessed_artifact_hashes": [
                    *(sha_bytes(value) for value in context["candidate_shadow_knowledge_base"].values()),
                    *context["expected_protected_hashes"].values(),
                ],
            },
            artifacts,
            storage_bytes=5,
            wall_clock_ms=1,
        )

    def run(self, **overrides):
        values = {
            "protected_kb": self.protected,
            "expected_protected_hashes": self.expected,
            "tasks": [self.task],
            "protected_cohorts": self.cohorts,
            "matched_budgets": self.budgets,
            "progress_fn": self.progress,
            "teacher_fn": self.teacher,
            "compress_fn": self.compress,
            "evaluate_fn": self.evaluate,
            "rollback_fn": self.rollback,
            "evaluator_independence_receipt": self.evaluator_receipt,
            "contamination_receipt": self.contamination_receipt,
            "release_firewall_receipt": self.release_receipt,
        }
        values.update(overrides)
        return run_progress_compress_shadow(**values)


class FrankieProgressCompressP0Tests(unittest.TestCase):
    def test_complete_shadow_lifecycle_is_retained_nowhere_and_non_authorizing(self):
        fixture = Fixture()
        result = fixture.run()
        self.assertEqual(result["status"], "COMPLETED_SHADOW_EVIDENCE_ONLY")
        self.assertTrue(result["component_contract_passed"])
        self.assertFalse(result["paper_faithful"])
        self.assertFalse(result["performance_evidence"])
        self.assertTrue(result["rollback_receipt"]["passed"])
        self.assertTrue(result["rollback_receipt"]["nonvacuous_candidate"])
        self.assertTrue(result["rollback_receipt"]["byte_exact_restoration"])
        self.assertFalse(result["rollback_receipt"]["live_external_rollback_evidence"])
        self.assertGreater(result["removal_receipt"]["removed_artifact_count"], 0)
        self.assertFalse(result["candidate_retained"])
        self.assertFalse(result["automatic_consolidation"])
        self.assertFalse(result["execution"])
        self.assertFalse(result["apply"])
        self.assertFalse(result["promotion"])
        self.assertTrue(result["explicit_user_authorization_required"])
        task = result["task_receipts"][0]
        self.assertTrue(task["protected_zero_regression"])
        self.assertTrue(task["new_task"]["passed"])
        self.assertFalse(task["consolidated_into_permanent_kb"])
        self.assertEqual(len(task["retention_rows"]), 2)
        for index, event in enumerate(result["lineage_events"]):
            expected_prior = (
                result["protected_kb_snapshot_sha256"]
                if index == 0
                else result["lineage_events"][index - 1]["event_hash"]
            )
            self.assertEqual(event["prior_event_hash"], expected_prior)

    def test_callback_mutating_permanent_snapshot_aborts_and_cannot_claim_rollback(self):
        fixture = Fixture()
        fixture.mutate_protected = True
        result = fixture.run()
        self.assertEqual(result["status"], "ABORTED_ROLLBACK_FAILED")
        self.assertIn("protected knowledge base mutated", result["abort_receipt"]["reason"])
        self.assertFalse(result["rollback_receipt"]["passed"])
        self.assertFalse(result["removal_receipt"]["permanent_state_integrity_verified"])
        self.assertIsNone(result["removal_receipt"]["permanent_state_changed"])

    def test_multiple_tasks_are_sequential_only_inside_disposable_shadow_lineage(self):
        fixture = Fixture()
        second = copy.deepcopy(fixture.task)
        second.update(
            {
                "task_id": "regime-3",
                "opened_at": "2026-08-05T00:00:00Z",
                "label_revealed_at": "2026-08-06T00:00:00Z",
                "progress_at": "2026-08-06T00:00:00Z",
                "compress_at": "2026-08-07T00:00:00Z",
                "evaluation_at": "2026-08-08T00:00:00Z",
                "release_at": "2026-10-01T00:00:00Z",
                "training_manifest_sha256": "7" * 64,
                "new_task_evaluation_manifest_sha256": "8" * 64,
                "release_manifest_sha256": "9" * 64,
            }
        )
        fixture.release_receipt = build_release_firewall_receipt(
            task_release_manifest_sha256={
                fixture.task["task_id"]: fixture.task["release_manifest_sha256"],
                second["task_id"]: second["release_manifest_sha256"],
            },
            locked_evaluator_hash=fixture.evaluator_hash,
        )
        result = fixture.run(tasks=[fixture.task, second])
        self.assertEqual(result["status"], "COMPLETED_SHADOW_EVIDENCE_ONLY")
        self.assertEqual(len(result["task_receipts"]), 2)
        self.assertEqual(
            result["task_receipts"][1]["input_shadow_kb_snapshot_sha256"],
            result["task_receipts"][0]["candidate_shadow_kb_snapshot_sha256"],
        )
        self.assertTrue(result["rollback_receipt"]["byte_exact_restoration"])
        self.assertFalse(result["candidate_retained"])

    def test_missing_fisher_anchor_coverage_fails_preflight(self):
        fixture = Fixture()
        broken = copy.deepcopy(fixture.task)
        del broken["ewc_parameters"]["p_weight"]
        with self.assertRaisesRegex(ProgressCompressP0Error, "coverage is incomplete"):
            fixture.run(tasks=[broken])

        broken = copy.deepcopy(fixture.task)
        for value in broken["ewc_parameters"].values():
            value["fisher"] = 0.0
        with self.assertRaisesRegex(ProgressCompressP0Error, "Fisher map is vacuous"):
            fixture.run(tasks=[broken])

    def test_incomplete_retention_matrix_aborts_and_removes_candidate(self):
        fixture = Fixture()
        fixture.omit_post_cell = True
        result = fixture.run()
        self.assertEqual(result["status"], "ABORTED_REMOVED")
        self.assertIn("retention matrix", result["abort_receipt"]["reason"])
        self.assertTrue(result["rollback_receipt"]["passed"])
        self.assertFalse(result["candidate_retained"])

    def test_future_release_leakage_and_premature_labels_fail_closed(self):
        fixture = Fixture()
        fixture.leak_release = True
        result = fixture.run()
        self.assertEqual(result["status"], "ABORTED_REMOVED")
        self.assertIn("undeclared artifact", result["abort_receipt"]["reason"])

        fixture = Fixture()
        premature = copy.deepcopy(fixture.task)
        premature["progress_at"] = "2026-08-01T12:00:00Z"
        with self.assertRaisesRegex(ProgressCompressP0Error, "violates opened"):
            fixture.run(tasks=[premature])

    def test_unbound_or_nonindependent_evaluator_is_rejected(self):
        fixture = Fixture()
        broken = dict(fixture.evaluator_receipt)
        broken["judge_version_hash"] = "9" * 64
        with self.assertRaisesRegex(ProgressCompressP0Error, "hash-invalid"):
            fixture.run(evaluator_independence_receipt=broken)

        fixture = Fixture()
        contamination = copy.deepcopy(fixture.contamination_receipt)
        contamination["bindings"]["locked_evaluator_hash"] = "9" * 64
        core = {key: value for key, value in contamination.items() if key != "receipt_hash"}
        contamination["receipt_hash"] = sha_json(core)
        with self.assertRaisesRegex(ProgressCompressP0Error, "unbound or failed"):
            fixture.run(contamination_receipt=contamination)

    def test_failed_byte_rollback_blocks_completion(self):
        fixture = Fixture()
        fixture.corrupt_rollback = True
        result = fixture.run()
        self.assertEqual(result["status"], "ABORTED_ROLLBACK_FAILED")
        self.assertIn("byte-exact shadow rollback failed", result["abort_receipt"]["reason"])
        self.assertFalse(result["rollback_receipt"]["byte_exact_restoration"])
        self.assertFalse(result["component_contract_passed"])

    def test_budget_mismatch_and_runtime_budget_overrun_fail_closed(self):
        fixture = Fixture()
        mismatched = copy.deepcopy(fixture.budgets)
        mismatched["PROGRESS_COMPRESS_CANDIDATE"]["model_calls"] = 99
        with self.assertRaisesRegex(ProgressCompressP0Error, "budgets are not exactly matched"):
            fixture.run(matched_budgets=mismatched)

        fixture = Fixture()
        tiny = copy.deepcopy(fixture.budgets)
        for arm in tiny:
            tiny[arm]["model_calls"] = 0
        result = fixture.run(matched_budgets=tiny)
        self.assertEqual(result["status"], "ABORTED_REMOVED")
        self.assertIn("budget exceeded", result["abort_receipt"]["reason"])

    def test_any_old_cohort_regression_is_catastrophic(self):
        fixture = Fixture()
        fixture.post_regression = True
        result = fixture.run()
        self.assertEqual(result["status"], "ABORTED_REMOVED")
        self.assertIn("catastrophic protected-cohort regression", result["abort_receipt"]["reason"])
        self.assertTrue(result["rollback_receipt"]["passed"])

    def test_missing_compression_ewc_binding_and_fault_receipts_abort(self):
        fixture = Fixture()
        fixture.drop_ewc_binding = True
        result = fixture.run()
        self.assertEqual(result["status"], "ABORTED_REMOVED")
        self.assertIn("Fisher/anchor", result["abort_receipt"]["reason"])

        fixture = Fixture()
        result = fixture.run(faults=["AFTER_PROGRESS"])
        self.assertEqual(result["status"], "ABORTED_REMOVED")
        self.assertTrue(result["abort_receipt"]["fault_injected"])
        self.assertRegex(result["abort_receipt"]["abort_hash"], r"^[0-9a-f]{64}$")
        self.assertRegex(result["removal_receipt"]["removal_hash"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
