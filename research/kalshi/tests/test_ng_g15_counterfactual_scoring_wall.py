import copy
import unittest
from unittest.mock import patch

import ng_g15_counterfactual_scoring_wall as wall


class TestCounterfactualScoringWall(unittest.TestCase):
    def setUp(self):
        self.blind_bytes = b'{"blind":true}\n'
        self.refined_bytes = b'{"refined":true}\n'
        self.replay = {"prepared": "exact"}
        self.anchor = {"anchor_fingerprint": "anchor-fp"}
        self.stream = {"outputs": []}
        self.blind = {"group": 15, "days": [], "actual_outcomes_used": False}
        self.auth = {
            "status": "EXACT_G15_REFINEMENT_READY",
            "authority": "EXACT_G15_REFINEMENT_AUTHORIZATION_ONLY",
            "exact_replay_completion_fingerprint": "replay-completion-fp",
            "replay_fingerprint": wall._fp(self.replay),
            "anchor_fingerprint": "anchor-fp",
            "refine_stream_fingerprint": wall._fp(self.stream),
            "blind_forecast_sha256": wall._sha(self.blind_bytes),
            "stand_down_days": [],
        }
        self.auth["authorization_fingerprint"] = wall._fp(self.auth)
        self.attribution = {
            "factors": list(wall.FACTORS),
            "replay_fingerprint": wall._fp(self.replay),
            "anchor_fingerprint": "anchor-fp",
            "refine_stream_fingerprint": wall._fp(self.stream),
            "lesson_proposals": [
                {"id": "g15_counterfactual.signed_flow"},
                {"id": "g15_counterfactual.activity"},
            ],
            "stand_down_days": [],
            "actual_outcomes_used": False,
        }
        self.attribution["fingerprint"] = wall._fp(self.attribution)
        self.refined = {
            "blind_forecast_sha256": wall._sha(self.blind_bytes),
            "refine_stream_fingerprint": wall._fp(self.stream),
        }
        self.refined["artifact_fingerprint"] = wall._fp(self.refined)

    def _fake_refined(self, refined, refined_bytes, *, blind_hash, refine_stream_fingerprint):
        if refined.get("blind_forecast_sha256") != blind_hash:
            raise ValueError("blind mismatch")
        if refined.get("refine_stream_fingerprint") != refine_stream_fingerprint:
            raise ValueError("stream mismatch")
        return refined["artifact_fingerprint"], wall._sha(refined_bytes)

    def build_lock(self):
        with patch.object(wall, "_validate_blind", return_value=wall._sha(self.blind_bytes)), \
             patch.object(wall, "_validate_authorization", return_value=copy.deepcopy(self.auth)), \
             patch.object(wall, "_validate_refined", side_effect=self._fake_refined), \
             patch.object(wall, "validate_attribution"):
            return wall.build_lock(
                authorization=self.auth,
                replay=self.replay,
                anchor=self.anchor,
                refine_stream=self.stream,
                attribution=self.attribution,
                blind=self.blind,
                refined=self.refined,
                blind_bytes=self.blind_bytes,
                refined_bytes=self.refined_bytes,
            )

    def publication(self, lock):
        result = {
            "actual_outcomes_used": True,
            "outcome_scoring_complete": True,
            "exact_refinement_authorization_fingerprint": lock["exact_refinement_authorization_fingerprint"],
            "exact_replay_completion_fingerprint": lock["exact_replay_completion_fingerprint"],
            "refine_stream_fingerprint": lock["refine_stream_fingerprint"],
            "blind_forecast_sha256": lock["blind_forecast_sha256"],
            "refined_forecast_sha256": lock["refined_forecast_sha256"],
            "refined_curve_fingerprint": lock["refined_curve_fingerprint"],
            "blind_score_fingerprint": "blind-score",
            "refined_score_fingerprint": "refined-score",
            "comparison_fingerprint": "comparison",
            "lesson_adjudication_fingerprint": "adjudication",
            "stand_down_days": [],
        }
        result["completion_fingerprint"] = wall._fp(result)
        return result

    def test_builds_pre_outcome_lock(self):
        lock = self.build_lock()
        self.assertEqual(lock["status"], wall.LOCK_READY)
        self.assertFalse(lock["actual_g15_outcomes_used"])
        self.assertEqual(lock["counterfactual_factors"], list(wall.FACTORS))
        self.assertEqual(lock["lesson_candidate_ids_fixed_before_scoring"], [
            "g15_counterfactual.activity", "g15_counterfactual.signed_flow"
        ])

    def test_builds_completion_after_exact_publication(self):
        lock = self.build_lock()
        with patch.object(wall, "validate_exact_publication"):
            completion = wall.build_completion(lock=lock, publication=self.publication(lock))
        self.assertTrue(completion["counterfactual_attribution_locked_before_scoring"])
        self.assertTrue(completion["blind_and_refined_scores_separate"])
        self.assertFalse(completion["actual_g16_outcomes_used"])

    def test_rejects_outcome_tainted_attribution(self):
        self.attribution["actual_outcomes_used"] = True
        self._refingerprint(self.attribution, "fingerprint")
        with self.assertRaises(wall.CounterfactualScoringWallError):
            self.build_lock()

    def test_rejects_missing_factor(self):
        self.attribution["factors"] = list(wall.FACTORS[:-1])
        self._refingerprint(self.attribution, "fingerprint")
        with self.assertRaises(wall.CounterfactualScoringWallError):
            self.build_lock()

    def test_rejects_replay_substitution(self):
        self.replay["other"] = True
        with self.assertRaises(wall.CounterfactualScoringWallError):
            self.build_lock()

    def test_rejects_refined_stream_substitution(self):
        self.refined["refine_stream_fingerprint"] = "other"
        self._refingerprint(self.refined, "artifact_fingerprint")
        with self.assertRaises(wall.CounterfactualScoringWallError):
            self.build_lock()

    def test_rejects_duplicate_candidate_ids(self):
        self.attribution["lesson_proposals"].append({"id": "g15_counterfactual.activity"})
        self._refingerprint(self.attribution, "fingerprint")
        with self.assertRaises(wall.CounterfactualScoringWallError):
            self.build_lock()

    def test_rejects_refingerprinted_lock_outcome_escalation(self):
        lock = self.build_lock()
        lock["actual_g15_outcomes_used"] = True
        self._refingerprint(lock, "lock_fingerprint")
        with self.assertRaises(wall.CounterfactualScoringWallError):
            wall.validate_lock(lock)

    def test_rejects_score_selected_support(self):
        lock = self.build_lock()
        lock["may_select_lesson_support_from_scores"] = True
        self._refingerprint(lock, "lock_fingerprint")
        with self.assertRaises(wall.CounterfactualScoringWallError):
            wall.validate_lock(lock)

    def test_rejects_publication_provenance_change(self):
        lock = self.build_lock()
        publication = self.publication(lock)
        publication["refined_curve_fingerprint"] = "other"
        self._refingerprint(publication, "completion_fingerprint")
        with patch.object(wall, "validate_exact_publication"):
            with self.assertRaises(wall.CounterfactualScoringWallError):
                wall.build_completion(lock=lock, publication=publication)

    def test_requires_separate_scores(self):
        lock = self.build_lock()
        publication = self.publication(lock)
        publication["refined_score_fingerprint"] = ""
        self._refingerprint(publication, "completion_fingerprint")
        with patch.object(wall, "validate_exact_publication"):
            with self.assertRaises(wall.CounterfactualScoringWallError):
                wall.build_completion(lock=lock, publication=publication)

    def test_rejects_g16_outcome_escalation(self):
        lock = self.build_lock()
        with patch.object(wall, "validate_exact_publication"):
            completion = wall.build_completion(lock=lock, publication=self.publication(lock))
        completion["actual_g16_outcomes_used"] = True
        self._refingerprint(completion, "completion_fingerprint")
        with self.assertRaises(wall.CounterfactualScoringWallError):
            wall.validate_completion(completion)

    def test_unions_stand_downs(self):
        self.auth["stand_down_days"] = ["20260315"]
        self._refingerprint(self.auth, "authorization_fingerprint")
        self.attribution["stand_down_days"] = ["20260316"]
        self._refingerprint(self.attribution, "fingerprint")
        self.assertEqual(self.build_lock()["stand_down_days"], ["20260315", "20260316"])

    def test_inputs_are_immutable(self):
        before = copy.deepcopy((self.auth, self.replay, self.anchor, self.stream, self.attribution, self.blind, self.refined))
        self.build_lock()
        self.assertEqual(before, (self.auth, self.replay, self.anchor, self.stream, self.attribution, self.blind, self.refined))

    def test_deterministic_lock(self):
        self.assertEqual(self.build_lock(), self.build_lock())

    def test_authority_contract(self):
        lock = self.build_lock()
        self.assertEqual(lock["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(lock["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(lock["options_lane_started"])
        self.assertFalse(lock["may_update_ng_brain"])
        self.assertFalse(lock["execution_authority"])

    @staticmethod
    def _refingerprint(value, field):
        value[field] = wall._fp({key: item for key, item in value.items() if key != field})


if __name__ == "__main__":
    unittest.main()
