from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import ng_historical_refinement_executor as legacy_executor
import ng_historical_refinement_executor_v2 as executor_v2
import ng_historical_refinement_readiness as legacy_readiness
import ng_historical_refinement_readiness_v4 as readiness


class HistoricalRefinementReadinessV4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}

    def _write_chain(self, root: Path, values=None) -> dict:
        values = values or readiness._linked_fixture_chain()
        for spec in readiness.STAGES:
            readiness._atomic_json(root / spec.filename, values[spec.key])
        return values

    def test_stage_order_closes_g15_scoring_bypass(self) -> None:
        keys = [spec.key for spec in readiness.STAGES]
        self.assertLess(keys.index("g15_counterfactual_attribution"), keys.index("g15_counterfactual_scoring_lock"))
        self.assertLess(keys.index("g15_counterfactual_scoring_lock"), keys.index("g15_counterfactual_score_gate"))
        self.assertLess(keys.index("g15_counterfactual_score_gate"), keys.index("g15_publication"))
        self.assertLess(keys.index("g15_publication"), keys.index("g15_counterfactual_scored_publication"))
        self.assertLess(keys.index("g15_counterfactual_scored_publication"), keys.index("g15_counterfactual_lesson_gate"))

    def test_fixed_outcome_boundary_is_lock_then_score(self) -> None:
        specs = {spec.key: spec for spec in readiness.STAGES}
        self.assertTrue(specs["g15_counterfactual_scoring_lock"].pre_outcome)
        self.assertFalse(specs["g15_counterfactual_score_gate"].pre_outcome)
        self.assertFalse(specs["g15_publication"].pre_outcome)
        self.assertFalse(specs["g15_counterfactual_scored_publication"].pre_outcome)

    def test_complete_fixture_chain_is_v4_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self._write_chain(root)
            report = readiness.build_readiness_report(root, validator_overrides=self.overrides)
        self.assertEqual(report["schema"], readiness.SCHEMA)
        self.assertEqual(report["status"], "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V4")
        self.assertTrue(report["g15_counterfactual_scoring_locked_before_actual_open"])
        self.assertTrue(report["g15_blind_and_refined_scores_separate"])
        self.assertTrue(report["g15_counterfactual_scored_publication_complete"])
        readiness.validate_readiness_report(report)

    def test_missing_lock_blocks_score_and_all_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self._write_chain(root)
            (root / "g15_counterfactual_scoring_lock.json").unlink()
            report = readiness.build_readiness_report(root, validator_overrides=self.overrides)
        self.assertEqual(report["first_blocking_stage"], "g15_counterfactual_scoring_lock")
        rows = {row["key"]: row for row in report["stages"]}
        self.assertEqual(rows["g15_counterfactual_score_gate"]["effective_status"], "BLOCKED_BY_UPSTREAM")
        self.assertEqual(rows["g16_counterfactual_publication"]["effective_status"], "BLOCKED_BY_UPSTREAM")

    def test_refingerprinted_score_lock_substitution_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            values = self._write_chain(root)
            score = copy.deepcopy(values["g15_counterfactual_score_gate"])
            score["counterfactual_scoring_lock_fingerprint"] = "replacement-lock"
            score.pop("fingerprint")
            score["fingerprint"] = readiness._fingerprint(score)
            readiness._atomic_json(root / "g15_counterfactual_score_gate.json", score)
            report = readiness.build_readiness_report(root, validator_overrides=self.overrides)
        rows = {row["key"]: row for row in report["stages"]}
        self.assertEqual(rows["g15_counterfactual_score_gate"]["effective_status"], "INVALID")
        self.assertTrue(any("provenance link mismatch" in item for item in rows["g15_counterfactual_score_gate"]["blockers"]))

    def test_scored_publication_must_bind_lesson_adjudication(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            values = self._write_chain(root)
            lesson = copy.deepcopy(values["g15_counterfactual_lesson_gate"])
            lesson["source"]["adjudication_fingerprint"] = "different-adjudication"
            lesson.pop("fingerprint")
            lesson["fingerprint"] = readiness._fingerprint(lesson)
            readiness._atomic_json(root / "g15_counterfactual_lesson_gate.json", lesson)
            report = readiness.build_readiness_report(root, validator_overrides=self.overrides)
        row = next(row for row in report["stages"] if row["key"] == "g15_counterfactual_lesson_gate")
        self.assertEqual(row["effective_status"], "INVALID")

    def test_v3_report_cannot_pass_v4_validator(self) -> None:
        fake = {
            "schema": legacy_readiness.SCHEMA,
            "stage_order": [spec.key for spec in legacy_readiness.STAGES],
            "stages": [],
        }
        fake["fingerprint"] = readiness._fingerprint(fake)
        with self.assertRaises(readiness.HistoricalRefinementReadinessError):
            readiness.validate_readiness_report(fake)

    def test_report_authority_escalation_fails_after_refingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            report = readiness.build_readiness_report(root, validator_overrides=self.overrides)
        tampered = copy.deepcopy(report)
        tampered["options_lane_started"] = True
        tampered.pop("fingerprint")
        tampered["fingerprint"] = readiness._fingerprint(tampered)
        with self.assertRaises(readiness.HistoricalRefinementReadinessError):
            readiness.validate_readiness_report(tampered)

    def test_report_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self._write_chain(root)
            first = readiness.build_readiness_report(root, validator_overrides=self.overrides)
            second = readiness.build_readiness_report(root, validator_overrides=self.overrides)
        self.assertEqual(first, second)


class HistoricalRefinementExecutorV2Tests(unittest.TestCase):
    def test_plan_uses_v4_stage_order(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            plan = executor_v2.build_plan(root / "artifacts", root)
        self.assertEqual(
            [row["key"] for row in plan["stages"]],
            [spec.key for spec in readiness.STAGES],
        )
        executor_v2.validate_plan(plan)

    def test_plan_marks_lock_pre_outcome_and_score_post_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            plan = executor_v2.build_plan(root / "artifacts", root)
        rows = {row["key"]: row for row in plan["stages"]}
        self.assertFalse(rows["g15_counterfactual_scoring_lock"]["requires_fixed_outcomes"])
        self.assertTrue(rows["g15_counterfactual_score_gate"]["requires_fixed_outcomes"])
        self.assertTrue(rows["g15_counterfactual_scored_publication"]["requires_fixed_outcomes"])

    def test_plan_exposes_lock_first_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            plan = executor_v2.build_plan(root / "artifacts", root)
        rows = {row["key"]: row for row in plan["stages"]}
        self.assertIn("ng_g15_counterfactual_scoring_wall.py", rows["g15_counterfactual_scoring_lock"]["suggested_entrypoint"])
        self.assertIn("ng_g15_counterfactual_score_gate.py", rows["g15_counterfactual_score_gate"]["suggested_entrypoint"])
        self.assertIn("ng_g15_counterfactual_scored_publication_gate.py", rows["g15_counterfactual_scored_publication"]["suggested_entrypoint"])

    def test_legacy_plan_order_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            legacy_plan = legacy_executor.build_plan(root / "artifacts", root)
        with self.assertRaises(legacy_executor.HistoricalRefinementExecutionError):
            executor_v2.validate_plan(legacy_plan)

    def test_context_restores_legacy_globals(self) -> None:
        original_readiness = legacy_executor.readiness
        original_entrypoints = legacy_executor.SUGGESTED_ENTRYPOINTS
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            executor_v2.build_plan(root / "artifacts", root)
        self.assertIs(legacy_executor.readiness, original_readiness)
        self.assertIs(legacy_executor.SUGGESTED_ENTRYPOINTS, original_entrypoints)

    def test_options_command_remains_forbidden(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            plan = executor_v2.build_plan(root / "artifacts", root)
        tampered = copy.deepcopy(plan)
        step = next(row for row in tampered["stages"] if row["key"] == "g15_counterfactual_scoring_lock")
        step["enabled"] = True
        step["argv"] = ["python", "worker.py", "--options-implementation"]
        tampered.pop("fingerprint")
        tampered["fingerprint"] = legacy_executor._fingerprint(tampered)
        with self.assertRaises(legacy_executor.HistoricalRefinementExecutionError):
            executor_v2.validate_plan(tampered)

    def test_plan_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            first = executor_v2.build_plan(root / "artifacts", root)
            second = executor_v2.build_plan(root / "artifacts", root)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
