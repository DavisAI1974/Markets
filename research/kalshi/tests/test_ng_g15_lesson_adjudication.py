import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

import ng_g15_lesson_adjudication as adjudication  # noqa: E402
from ng_historical_manifest import G15_DATES  # noqa: E402


class G15LessonAdjudicationTests(unittest.TestCase):
    def setUp(self):
        self.audit, self.proposals, self.comparison = adjudication._fixture()

    @staticmethod
    def _refresh(artifact, field):
        artifact[field] = adjudication._fingerprint(
            {k: v for k, v in artifact.items() if k != field}
        )

    def test_supported_candidate_enters_g16_shadow_registry(self):
        result = adjudication.build_adjudication(self.audit, self.proposals, self.comparison)
        row = result["adjudications"][0]
        self.assertEqual(row["status"], "G15_SUPPORTED_SHADOW_CANDIDATE")
        self.assertTrue(row["g16_shadow_test"]["eligible"])
        self.assertEqual(result["g16_shadow_registry"]["candidate_count"], 1)
        self.assertFalse(result["g16_shadow_registry"]["actual_g16_outcomes_used"])

    def test_counterexample_is_recorded_and_blocks_g16(self):
        self.comparison["days"][1]["path_mae_improvement_usd"] = -50
        self._refresh(self.comparison, "artifact_fingerprint")
        result = adjudication.build_adjudication(self.audit, self.proposals, self.comparison)
        row = result["adjudications"][0]
        self.assertIn("20260316", row["scored_counterexample_days"])
        self.assertFalse(row["g16_shadow_test"]["eligible"])
        self.assertEqual(result["g16_shadow_registry"]["candidate_count"], 0)

    def test_insufficient_single_day_does_not_enter_g16(self):
        self.proposals["proposals"][0]["supporting_g15_days"] = [G15_DATES[0]]
        self._refresh(self.proposals, "proposal_fingerprint")
        result = adjudication.build_adjudication(self.audit, self.proposals, self.comparison)
        self.assertEqual(result["adjudications"][0]["status"], "INSUFFICIENT_G15")
        self.assertEqual(result["g16_shadow_registry"]["candidate_count"], 0)

    def test_direction_harm_blocks_otherwise_positive_candidate(self):
        day = self.comparison["days"][0]
        day["blind_net_direction_ok"] = True
        day["refined_net_direction_ok"] = False
        self._refresh(self.comparison, "artifact_fingerprint")
        result = adjudication.build_adjudication(self.audit, self.proposals, self.comparison)
        row = result["adjudications"][0]
        self.assertFalse(row["g16_shadow_test"]["eligible"])
        self.assertEqual(row["metrics"]["direction_harm_count"], 1)

    def test_input_artifacts_remain_immutable(self):
        audit_before = copy.deepcopy(self.audit)
        proposals_before = copy.deepcopy(self.proposals)
        comparison_before = copy.deepcopy(self.comparison)
        adjudication.build_adjudication(self.audit, self.proposals, self.comparison)
        self.assertEqual(self.audit, audit_before)
        self.assertEqual(self.proposals, proposals_before)
        self.assertEqual(self.comparison, comparison_before)

    def test_proposal_audit_fingerprint_mismatch_is_rejected(self):
        self.proposals["source_audit_fingerprint"] = "wrong"
        self._refresh(self.proposals, "proposal_fingerprint")
        with self.assertRaises(adjudication.LessonAdjudicationError):
            adjudication.build_adjudication(self.audit, self.proposals, self.comparison)

    def test_non_g15_supporting_day_is_rejected(self):
        self.proposals["proposals"][0]["supporting_g15_days"].append("20260401")
        self._refresh(self.proposals, "proposal_fingerprint")
        with self.assertRaises(adjudication.LessonAdjudicationError):
            adjudication.build_adjudication(self.audit, self.proposals, self.comparison)

    def test_tampered_comparison_is_rejected(self):
        self.comparison["days"][0]["path_mae_improvement_usd"] = 999
        with self.assertRaises(adjudication.LessonAdjudicationError):
            adjudication.build_adjudication(self.audit, self.proposals, self.comparison)

    def test_tampered_output_is_rejected(self):
        result = adjudication.build_adjudication(self.audit, self.proposals, self.comparison)
        result["adjudications"][0]["status"] = "ADOPTED"
        with self.assertRaises(adjudication.LessonAdjudicationError):
            adjudication.validate_adjudication(result)

    def test_registry_candidates_exactly_match_eligible_rows(self):
        result = adjudication.build_adjudication(self.audit, self.proposals, self.comparison)
        result["g16_shadow_registry"]["candidates"] = []
        result["g16_shadow_registry"]["candidate_count"] = 0
        registry = result["g16_shadow_registry"]
        self._refresh(registry, "registry_fingerprint")
        self._refresh(result, "artifact_fingerprint")
        with self.assertRaises(adjudication.LessonAdjudicationError):
            adjudication.validate_adjudication(result)

    def test_no_artifact_can_update_brain_or_execution(self):
        result = adjudication.build_adjudication(self.audit, self.proposals, self.comparison)
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(result["execution_authority"])
        for row in result["adjudications"]:
            self.assertFalse(row["may_update_ng_brain"])
            self.assertFalse(row["execution_authority"])
        registry = result["g16_shadow_registry"]
        self.assertFalse(registry["may_update_ng_brain"])
        self.assertFalse(registry["execution_authority"])
        self.assertFalse(registry["may_change_g16_blind_prior"])

    def test_deterministic_artifact_fingerprint(self):
        first = adjudication.build_adjudication(self.audit, self.proposals, self.comparison)
        second = adjudication.build_adjudication(self.audit, self.proposals, self.comparison)
        self.assertEqual(first["artifact_fingerprint"], second["artifact_fingerprint"])


if __name__ == "__main__":
    unittest.main()
