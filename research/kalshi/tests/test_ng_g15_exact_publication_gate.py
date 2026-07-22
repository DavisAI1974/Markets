import copy
import sys
import tempfile
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

import ng_g15_exact_publication_gate as mod  # noqa: E402


class ExactPublicationGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fx = mod._fixture(Path(self.temp.name))

    def build(self, **overrides):
        args = {
            "authorization": self.fx["authorization"],
            "blind": self.fx["blind"],
            "refined": self.fx["refined"],
            "actual": self.fx["actual"],
            "blind_score": self.fx["blind_score"],
            "refined_score": self.fx["refined_score"],
            "comparison": self.fx["comparison"],
            "adjudication": self.fx["adjudication"],
            "blind_rt": self.fx["blind_rt"],
            "refined_rt": self.fx["refined_rt"],
            "blind_bytes": self.fx["blind_bytes"],
            "refined_bytes": self.fx["refined_bytes"],
            "blind_png": self.fx["blind_png"],
            "refined_png": self.fx["refined_png"],
        }
        args.update(overrides)
        return mod.build_completion(**args)

    @staticmethod
    def refingerprint(value, field):
        value.pop(field, None)
        value[field] = mod._fingerprint(value)

    def test_complete_exact_publication(self):
        result = self.build()
        self.assertEqual(result["status"], mod.READY)
        self.assertTrue(result["continuous_rt_renders_complete"])
        self.assertTrue(
            result["g16_shadow_registry"][
                "pre_cutoff_shadow_refinement_authorized"
            ]
        )

    def test_sources_are_immutable(self):
        before = copy.deepcopy(
            (
                self.fx["authorization"], self.fx["blind"], self.fx["refined"],
                self.fx["actual"], self.fx["adjudication"],
            )
        )
        self.build()
        self.assertEqual(
            before,
            (
                self.fx["authorization"], self.fx["blind"], self.fx["refined"],
                self.fx["actual"], self.fx["adjudication"],
            ),
        )

    def test_non_exact_authorization_is_rejected(self):
        auth = copy.deepcopy(self.fx["authorization"])
        auth["status"] = "MBO_ONLY"
        self.refingerprint(auth, "authorization_fingerprint")
        with self.assertRaises(mod.ExactPublicationError):
            self.build(authorization=auth)

    def test_blind_file_hash_mismatch_is_rejected(self):
        with self.assertRaises(mod.ExactPublicationError):
            self.build(blind_bytes=self.fx["blind_bytes"] + b"x")

    def test_refined_stream_provenance_mismatch_is_rejected(self):
        refined = copy.deepcopy(self.fx["refined"])
        refined["refine_stream_fingerprint"] = "other"
        self.refingerprint(refined, "artifact_fingerprint")
        refined_bytes = (mod._canonical(refined) + "\n").encode()
        with self.assertRaises(mod.ExactPublicationError):
            self.build(refined=refined, refined_bytes=refined_bytes)

    def test_refined_artifact_tampering_is_rejected(self):
        refined = copy.deepcopy(self.fx["refined"])
        refined["days"][0]["guessed_net_usd"] += 1
        with self.assertRaises(mod.ExactPublicationError):
            self.build(refined=refined)

    def test_score_must_reference_exact_forecast_bytes(self):
        score = copy.deepcopy(self.fx["refined_score"])
        score["forecast_sha256"] = "other"
        self.refingerprint(score, "artifact_fingerprint")
        with self.assertRaises(mod.ExactPublicationError):
            self.build(refined_score=score)

    def test_scores_must_share_actual_substrate(self):
        score = copy.deepcopy(self.fx["blind_score"])
        score["actual_artifact_fingerprint"] = "other"
        self.refingerprint(score, "artifact_fingerprint")
        with self.assertRaises(mod.ExactPublicationError):
            self.build(blind_score=score)

    def test_comparison_must_reference_exact_scores(self):
        comparison = copy.deepcopy(self.fx["comparison"])
        comparison["blind_score_fingerprint"] = "other"
        self.refingerprint(comparison, "artifact_fingerprint")
        with self.assertRaises(mod.ExactPublicationError):
            self.build(comparison=comparison)

    def test_adjudication_must_reference_exact_pipeline_audit(self):
        adjudication = copy.deepcopy(self.fx["adjudication"])
        adjudication["source"]["audit_fingerprint"] = "other"
        self.refingerprint(adjudication, "artifact_fingerprint")
        with self.assertRaises(mod.ExactPublicationError):
            self.build(adjudication=adjudication)

    def test_registry_tampering_is_rejected(self):
        adjudication = copy.deepcopy(self.fx["adjudication"])
        adjudication["g16_shadow_registry"]["candidate_count"] = 2
        self.refingerprint(adjudication, "artifact_fingerprint")
        with self.assertRaises(mod.ExactPublicationError):
            self.build(adjudication=adjudication)

    def test_wrong_render_filename_is_rejected(self):
        wrong = Path(self.temp.name) / "blind.png"
        wrong.write_bytes(mod._png_fixture())
        with self.assertRaises(mod.ExactPublicationError):
            self.build(blind_png=wrong)

    def test_placeholder_or_non_png_render_is_rejected(self):
        self.fx["blind_png"].write_bytes(b"not a png" * 1000)
        with self.assertRaises(mod.ExactPublicationError):
            self.build()

    def test_render_rt_must_share_scoring_actual_substrate(self):
        rt = copy.deepcopy(self.fx["refined_rt"])
        rt["days"][0]["net_usd"] += 1
        with self.assertRaises(mod.ExactPublicationError):
            self.build(refined_rt=rt)

    def test_stand_down_status_is_visible(self):
        auth = copy.deepcopy(self.fx["authorization"])
        auth["status"] = "EXACT_G15_REFINEMENT_READY_WITH_STAND_DOWNS"
        auth["stand_down_days"] = [mod.G15_DATES[0]]
        self.refingerprint(auth, "authorization_fingerprint")
        result = self.build(authorization=auth)
        self.assertEqual(result["status"], mod.READY_WITH_STAND_DOWNS)
        self.assertEqual(result["stand_down_days"], [mod.G15_DATES[0]])

    def test_completion_tampering_is_rejected(self):
        result = self.build()
        result["g16_shadow_registry"]["g16_outcome_access_authorized"] = True
        with self.assertRaises(mod.ExactPublicationError):
            mod.validate_completion(result)

    def test_g16_outcomes_brain_and_execution_remain_disabled(self):
        result = self.build()
        self.assertFalse(result["execution_authority"])
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(
            result["g16_shadow_registry"]["g16_outcome_access_authorized"]
        )
        self.assertFalse(
            result["g16_shadow_registry"]["may_change_g16_blind_prior"]
        )


if __name__ == "__main__":
    unittest.main()
