import copy
import unittest
from unittest.mock import patch

import ng_g15_counterfactual_scored_publication_gate as gate
import ng_g15_counterfactual_scoring_wall as wall


class TestCounterfactualScoredPublicationGate(unittest.TestCase):
    def setUp(self):
        self.lock = wall._selftest_lock()
        self.lock.update(
            {
                "counterfactual_attribution_fingerprint": "attribution-fp",
                "lesson_candidate_ids_fixed_before_scoring": [
                    "g15_counterfactual.signed_flow"
                ],
                "blind_forecast_sha256": "blind-hash",
                "refined_forecast_sha256": "refined-hash",
                "refined_curve_fingerprint": "curve-fp",
            }
        )
        self._refingerprint(self.lock, "lock_fingerprint")
        self.score = {
            "schema": "ng_g15_counterfactual_score_gate.v1",
            "status": "EXACT_G15_COUNTERFACTUAL_SCORES_COMPLETE",
            "authority": "G15_COUNTERFACTUAL_OUTCOME_SCORING_AUDIT_ONLY",
            "counterfactual_scoring_lock_fingerprint": self.lock[
                "lock_fingerprint"
            ],
            "counterfactual_attribution_fingerprint": "attribution-fp",
            "exact_refinement_authorization_fingerprint": self.lock[
                "exact_refinement_authorization_fingerprint"
            ],
            "exact_replay_completion_fingerprint": self.lock[
                "exact_replay_completion_fingerprint"
            ],
            "blind_forecast_sha256": "blind-hash",
            "refined_forecast_sha256": "refined-hash",
            "refined_curve_fingerprint": "curve-fp",
            "actual_artifact_fingerprint": "actual-fp",
            "blind_score_fingerprint": "blind-score",
            "refined_score_fingerprint": "refined-score",
            "comparison_fingerprint": "comparison",
            "lesson_candidate_ids_fixed_before_scoring": [
                "g15_counterfactual.signed_flow"
            ],
            "stand_down_days": [],
            "lock_validated_before_actual_file_open": True,
            "blind_and_refined_scores_separate": True,
            "actual_g15_outcomes_used": True,
            "actual_g16_outcomes_used": False,
            "random_shuffle_used": False,
            "one_signal_authority_preserved": True,
            "blind_forecast_immutable": True,
            "may_change_blind_prior": False,
            "may_change_blind_forecast": False,
            "may_change_posterior": False,
            "may_select_lesson_support_from_scores": False,
            "may_update_ng_brain": False,
            "execution_authority": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
            "options_lane_started": False,
            "next_permitted_stage": "G15_EXACT_RENDER_AND_PUBLICATION",
        }
        self._refingerprint(self.score, "fingerprint")
        self.publication = {
            "actual_outcomes_used": True,
            "outcome_scoring_complete": True,
            "continuous_rt_renders_complete": True,
            "exact_refinement_authorization_fingerprint": self.lock[
                "exact_refinement_authorization_fingerprint"
            ],
            "exact_replay_completion_fingerprint": self.lock[
                "exact_replay_completion_fingerprint"
            ],
            "blind_forecast_sha256": "blind-hash",
            "refined_forecast_sha256": "refined-hash",
            "refined_curve_fingerprint": "curve-fp",
            "actual_artifact_fingerprint": "actual-fp",
            "blind_score_fingerprint": "blind-score",
            "refined_score_fingerprint": "refined-score",
            "comparison_fingerprint": "comparison",
            "lesson_adjudication_fingerprint": "adjudication",
            "stand_down_days": [],
        }
        self._refingerprint(self.publication, "completion_fingerprint")

    def build(self):
        with patch.object(gate, "validate_receipt"), patch.object(
            gate, "validate_exact_publication"
        ):
            return gate.build_completion(
                lock=self.lock,
                score_receipt=self.score,
                exact_publication=self.publication,
            )

    def test_builds_complete_publication(self):
        result = self.build()
        self.assertEqual(result["status"], gate.READY)
        self.assertTrue(result["counterfactual_attribution_locked_before_actual_open"])
        self.assertTrue(result["locked_forecast_hashes_checked_before_actual_open"])
        self.assertTrue(result["blind_and_refined_scores_separate"])

    def test_binds_score_gate_and_lock(self):
        result = self.build()
        self.assertEqual(
            result["counterfactual_scoring_lock_fingerprint"],
            self.lock["lock_fingerprint"],
        )
        self.assertEqual(
            result["counterfactual_score_gate_fingerprint"],
            self.score["fingerprint"],
        )

    def test_rejects_score_lock_substitution(self):
        self.score["counterfactual_scoring_lock_fingerprint"] = "other"
        self._refingerprint(self.score, "fingerprint")
        with self.assertRaises(gate.CounterfactualScoredPublicationError):
            self.build()

    def test_rejects_score_attribution_substitution(self):
        self.score["counterfactual_attribution_fingerprint"] = "other"
        self._refingerprint(self.score, "fingerprint")
        with self.assertRaises(gate.CounterfactualScoredPublicationError):
            self.build()

    def test_rejects_publication_score_substitution(self):
        self.publication["refined_score_fingerprint"] = "other"
        self._refingerprint(self.publication, "completion_fingerprint")
        with self.assertRaises(gate.CounterfactualScoredPublicationError):
            self.build()

    def test_rejects_actual_substrate_substitution(self):
        self.publication["actual_artifact_fingerprint"] = "other"
        self._refingerprint(self.publication, "completion_fingerprint")
        with self.assertRaises(gate.CounterfactualScoredPublicationError):
            self.build()

    def test_requires_renders(self):
        self.publication["continuous_rt_renders_complete"] = False
        self._refingerprint(self.publication, "completion_fingerprint")
        with self.assertRaises(gate.CounterfactualScoredPublicationError):
            self.build()

    def test_unions_stand_downs(self):
        self.lock["status"] = wall.LOCK_READY_SD
        self.lock["stand_down_days"] = ["20260315"]
        self._refingerprint(self.lock, "lock_fingerprint")
        self.score["status"] = "EXACT_G15_COUNTERFACTUAL_SCORES_COMPLETE_WITH_STAND_DOWNS"
        self.score["counterfactual_scoring_lock_fingerprint"] = self.lock[
            "lock_fingerprint"
        ]
        self.score["stand_down_days"] = ["20260316"]
        self._refingerprint(self.score, "fingerprint")
        self.publication["stand_down_days"] = ["20260317"]
        self._refingerprint(self.publication, "completion_fingerprint")
        self.assertEqual(
            self.build()["stand_down_days"],
            ["20260315", "20260316", "20260317"],
        )

    def test_rejects_refingerprinted_g16_outcome_escalation(self):
        result = self.build()
        result["actual_g16_outcomes_used"] = True
        self._refingerprint(result, "completion_fingerprint")
        with self.assertRaises(gate.CounterfactualScoredPublicationError):
            gate.validate_completion(result)

    def test_rejects_lesson_support_selection_from_scores(self):
        result = self.build()
        result["may_select_lesson_support_from_scores"] = True
        self._refingerprint(result, "completion_fingerprint")
        with self.assertRaises(gate.CounterfactualScoredPublicationError):
            gate.validate_completion(result)

    def test_inputs_are_immutable(self):
        before = copy.deepcopy((self.lock, self.score, self.publication))
        self.build()
        self.assertEqual(before, (self.lock, self.score, self.publication))

    def test_deterministic_output(self):
        self.assertEqual(self.build(), self.build())

    def test_authority_contract(self):
        result = self.build()
        self.assertFalse(result["random_shuffle_used"])
        self.assertTrue(result["blind_forecast_immutable"])
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(result["execution_authority"])
        self.assertEqual(result["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(result["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(result["options_lane_started"])

    @staticmethod
    def _refingerprint(value, field):
        value[field] = gate._fp({key: item for key, item in value.items() if key != field})


if __name__ == "__main__":
    unittest.main()
