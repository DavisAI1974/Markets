import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g15_path_score import (  # noqa: E402
    ScoreError,
    _fixture,
    _fingerprint,
    _major_move_index,
    _dominant_turn_index,
    _regime,
    build_comparison,
    build_scorecard,
    validate_comparison,
    validate_scorecard,
)


class G15PathScoreTests(unittest.TestCase):
    def setUp(self):
        self.blind, self.refined, self.actual, self.blind_bytes = _fixture()

    def scores(self):
        blind_score = build_scorecard(
            self.blind,
            self.actual,
            forecast_kind="blind",
            forecast_bytes=self.blind_bytes,
        )
        refined_score = build_scorecard(
            self.refined,
            self.actual,
            forecast_kind="refined",
            blind_bytes=self.blind_bytes,
        )
        return blind_score, refined_score

    def test_refined_fixture_reduces_path_error(self):
        blind_score, refined_score = self.scores()
        comparison = build_comparison(blind_score, refined_score)
        self.assertGreater(comparison["block"]["path_absolute_error_improvement_usd"], 0)
        self.assertGreater(comparison["block"]["endpoint_absolute_error_improvement_usd"], 0)

    def test_inputs_remain_immutable(self):
        before_blind = copy.deepcopy(self.blind)
        before_refined = copy.deepcopy(self.refined)
        before_actual = copy.deepcopy(self.actual)
        self.scores()
        self.assertEqual(self.blind, before_blind)
        self.assertEqual(self.refined, before_refined)
        self.assertEqual(self.actual, before_actual)

    def test_roll_offset_is_removed_from_skill_drift(self):
        self.actual["rolls"] = [{"date": "20260320", "offset": -0.037}]
        for day in self.actual["days"]:
            if day["date"] >= "20260320":
                day["cum_from_anchor_close_usd"] -= 370
        score = build_scorecard(self.blind, self.actual, forecast_kind="blind")
        baseline_actual = _fixture()[2]
        baseline = build_scorecard(self.blind, baseline_actual, forecast_kind="blind")
        self.assertEqual(
            score["block"]["final_actual_close_cum_roll_adjusted_usd"],
            baseline["block"]["final_actual_close_cum_roll_adjusted_usd"],
        )

    def test_refined_blind_hash_mismatch_is_rejected(self):
        with self.assertRaises(ScoreError):
            build_scorecard(
                self.refined,
                self.actual,
                forecast_kind="refined",
                blind_bytes=b"different",
            )

    def test_refined_tampering_is_rejected(self):
        self.refined["days"][0]["guessed_net_usd"] += 1
        with self.assertRaises(ScoreError):
            build_scorecard(
                self.refined,
                self.actual,
                forecast_kind="refined",
                blind_bytes=self.blind_bytes,
            )

    def test_incomplete_g15_is_rejected(self):
        self.blind["days"].pop()
        with self.assertRaises(ScoreError):
            build_scorecard(self.blind, self.actual, forecast_kind="blind")

    def test_actual_endpoint_mismatch_is_rejected(self):
        self.actual["days"][0]["net_usd"] += 1
        with self.assertRaises(ScoreError):
            build_scorecard(self.blind, self.actual, forecast_kind="blind")

    def test_probability_scores_are_refined_only(self):
        blind_score, refined_score = self.scores()
        self.assertIsNone(blind_score["days"][0]["probability_score"])
        self.assertIsNotNone(refined_score["days"][0]["probability_score"])
        self.assertGreaterEqual(refined_score["days"][0]["probability_score"]["log_loss"], 0)

    def test_score_and_comparison_authority_are_read_only(self):
        blind_score, refined_score = self.scores()
        comparison = build_comparison(blind_score, refined_score)
        for artifact in (blind_score, refined_score, comparison):
            self.assertFalse(artifact["execution_authority"])
            self.assertFalse(artifact["may_update_ng_brain"])
            self.assertTrue(artifact["actual_outcomes_used"])

    def test_scorecard_tamper_detection(self):
        blind_score, _ = self.scores()
        blind_score["days"][0]["path_mae_usd"] += 1
        with self.assertRaises(ScoreError):
            validate_scorecard(blind_score)

    def test_comparison_tamper_detection(self):
        blind_score, refined_score = self.scores()
        comparison = build_comparison(blind_score, refined_score)
        comparison["block"]["path_absolute_error_improvement_usd"] += 1
        with self.assertRaises(ScoreError):
            validate_comparison(comparison)

    def test_regime_major_move_and_turn_are_deterministic(self):
        values = [0, 10, 20, -30, -40]
        self.assertEqual(_regime(values), _regime(values))
        self.assertEqual(_major_move_index(values), 3)
        self.assertEqual(_dominant_turn_index(values), 2)

    def test_wrong_comparison_roles_are_rejected(self):
        blind_score, refined_score = self.scores()
        blind_score["forecast_kind"] = "refined"
        payload = copy.deepcopy(blind_score)
        payload.pop("artifact_fingerprint", None)
        blind_score["artifact_fingerprint"] = _fingerprint(payload)
        with self.assertRaises(ScoreError):
            build_comparison(blind_score, refined_score)


if __name__ == "__main__":
    unittest.main()
