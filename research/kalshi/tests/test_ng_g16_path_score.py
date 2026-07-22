import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g16_path_score import (  # noqa: E402
    G16ScoreError,
    _canonical,
    _fingerprint,
    _fixture_actual,
    _fixture_blind,
    _fixture_refined,
    build_comparison,
    build_scorecard,
    validate_comparison,
    validate_scorecard,
)


class G16PathScoreTests(unittest.TestCase):
    def setUp(self):
        self.blind = _fixture_blind()
        self.actual = _fixture_actual()
        self.refined = _fixture_refined(self.blind)
        self.blind_bytes = (_canonical(self.blind) + "\n").encode()

    def scores(self):
        blind_score = build_scorecard(self.blind, self.actual, role="blind")
        refined_score = build_scorecard(
            self.refined,
            self.actual,
            role="refined",
            blind_forecast=self.blind,
            blind_bytes=self.blind_bytes,
        )
        return blind_score, refined_score

    def test_refined_curve_improves_all_fixture_days(self):
        blind_score, refined_score = self.scores()
        comparison = build_comparison(blind_score, refined_score)
        self.assertEqual(comparison["aggregate"]["days_path_mae_improved"], 11)
        self.assertEqual(refined_score["aggregate"]["mean_path_mae_usd"], 0.0)
        self.assertGreater(comparison["aggregate"]["mean_path_mae_improvement_usd"], 0)

    def test_inputs_are_immutable(self):
        before = (copy.deepcopy(self.blind), copy.deepcopy(self.refined), copy.deepcopy(self.actual))
        self.scores()
        self.assertEqual((self.blind, self.refined, self.actual), before)

    def test_incomplete_g16_forecast_is_rejected(self):
        broken = copy.deepcopy(self.blind)
        broken["days"].pop()
        with self.assertRaises(G16ScoreError):
            build_scorecard(broken, self.actual, role="blind")

    def test_actual_endpoint_contradiction_is_rejected(self):
        broken = copy.deepcopy(self.actual)
        broken["days"][0]["net_usd"] += 1
        with self.assertRaises(G16ScoreError):
            build_scorecard(self.blind, broken, role="blind")

    def test_actual_roll_or_seam_is_rejected(self):
        for key in ("rolls", "seams"):
            broken = copy.deepcopy(self.actual)
            broken[key] = [{"date": "20260401"}]
            with self.assertRaises(G16ScoreError):
                build_scorecard(self.blind, broken, role="blind")

    def test_refined_artifact_tampering_is_rejected(self):
        broken = copy.deepcopy(self.refined)
        broken["days"][0]["guess_curve"][-1][1] -= 1
        with self.assertRaises(G16ScoreError):
            build_scorecard(
                broken,
                self.actual,
                role="refined",
                blind_forecast=self.blind,
                blind_bytes=self.blind_bytes,
            )

    def test_wrong_blind_file_hash_is_rejected(self):
        with self.assertRaises(G16ScoreError):
            build_scorecard(
                self.refined,
                self.actual,
                role="refined",
                blind_forecast=self.blind,
                blind_bytes=b"different\n",
            )

    def test_probability_metrics_are_refined_only(self):
        blind_score, refined_score = self.scores()
        self.assertEqual(blind_score["aggregate"]["probability_scored_days"], 0)
        self.assertEqual(refined_score["aggregate"]["probability_scored_days"], 11)
        self.assertIsNotNone(refined_score["aggregate"]["mean_brier_multiclass"])

    def test_scorecard_tampering_is_rejected(self):
        blind_score, _ = self.scores()
        broken = copy.deepcopy(blind_score)
        broken["aggregate"]["net_direction_hits"] += 1
        with self.assertRaises(G16ScoreError):
            validate_scorecard(broken)

    def test_comparison_tampering_is_rejected(self):
        blind_score, refined_score = self.scores()
        comparison = build_comparison(blind_score, refined_score)
        broken = copy.deepcopy(comparison)
        broken["days"][0]["path_mae_improvement_usd"] += 1
        with self.assertRaises(G16ScoreError):
            validate_comparison(broken)

    def test_comparison_requires_same_actual_artifact(self):
        blind_score, refined_score = self.scores()
        broken = copy.deepcopy(refined_score)
        broken["actual_sha256"] = "different"
        payload = copy.deepcopy(broken)
        payload.pop("score_fingerprint")
        broken["score_fingerprint"] = _fingerprint(payload)
        with self.assertRaises(G16ScoreError):
            build_comparison(blind_score, broken)

    def test_role_order_is_enforced(self):
        blind_score, refined_score = self.scores()
        with self.assertRaises(G16ScoreError):
            build_comparison(refined_score, blind_score)

    def test_deterministic_outputs(self):
        first_blind, first_refined = self.scores()
        second_blind, second_refined = self.scores()
        self.assertEqual(first_blind, second_blind)
        self.assertEqual(first_refined, second_refined)
        self.assertEqual(
            build_comparison(first_blind, first_refined),
            build_comparison(second_blind, second_refined),
        )

    def test_authority_is_read_only(self):
        blind_score, refined_score = self.scores()
        comparison = build_comparison(blind_score, refined_score)
        for artifact in (blind_score, refined_score, comparison):
            self.assertFalse(artifact["execution_authority"])
            self.assertTrue(artifact["actual_g16_outcomes_used"])
            self.assertFalse(artifact["may_update_ng_brain"])
            self.assertFalse(artifact["may_change_g16_blind_prior"])


if __name__ == "__main__":
    unittest.main()
