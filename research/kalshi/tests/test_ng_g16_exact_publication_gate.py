import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g16_exact_publication_gate import (  # noqa: E402
    G16ExactPublicationError,
    READY,
    READY_WITH_STAND_DOWNS,
    _fixture,
    _fp,
    build_completion,
    validate_completion,
)


class G16ExactPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.inputs = _fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def build(self):
        return build_completion(**self.inputs)

    def test_complete_exact_publication(self):
        result = self.build()
        self.assertEqual(result["status"], READY)
        self.assertTrue(result["exact_g16_publication_complete"])
        self.assertTrue(result["g16_consumed_as_forward_holdout"])
        self.assertFalse(result["g16_reusable_as_untouched_holdout"])
        self.assertEqual(set(result["renders"]), {"blind", "refined"})

    def test_sources_remain_immutable(self):
        before = copy.deepcopy(self.inputs)
        self.build()
        for key, value in before.items():
            if key not in {"blind_png", "refined_png"}:
                self.assertEqual(self.inputs[key], value)

    def test_causal_completion_outcome_leak_is_rejected(self):
        completion = self.inputs["causal_completion"]
        completion["actual_g16_outcomes_used"] = True
        completion.pop("fingerprint")
        completion["fingerprint"] = _fp(completion)
        with self.assertRaises(G16ExactPublicationError):
            self.build()

    def test_causal_completion_plan_mismatch_is_rejected(self):
        completion = self.inputs["causal_completion"]
        completion["plan_fingerprint"] = "x" * 64
        completion.pop("fingerprint")
        completion["fingerprint"] = _fp(completion)
        with self.assertRaises(G16ExactPublicationError):
            self.build()

    def test_refined_curve_wrong_posterior_is_rejected(self):
        refined = self.inputs["refined"]
        refined["posterior_stream_fingerprint"] = "y" * 64
        refined.pop("artifact_fingerprint")
        refined["artifact_fingerprint"] = _fp(refined)
        self.inputs["refined_bytes"] = (
            json.dumps(refined, indent=2, sort_keys=True) + "\n"
        ).encode()
        with self.assertRaises(G16ExactPublicationError):
            self.build()

    def test_blind_score_wrong_forecast_hash_is_rejected(self):
        score = self.inputs["blind_score"]
        score["forecast_sha256"] = "z" * 64
        score.pop("score_fingerprint")
        score["score_fingerprint"] = _fp(score)
        with self.assertRaises(G16ExactPublicationError):
            self.build()

    def test_scorecards_must_share_actual_bytes(self):
        score = self.inputs["refined_score"]
        score["actual_sha256"] = "a" * 64
        score.pop("score_fingerprint")
        score["score_fingerprint"] = _fp(score)
        comparison = self.inputs["comparison"]
        comparison["refined_score_fingerprint"] = score["score_fingerprint"]
        comparison.pop("comparison_fingerprint")
        comparison["comparison_fingerprint"] = _fp(comparison)
        with self.assertRaises(G16ExactPublicationError):
            self.build()

    def test_comparison_score_provenance_is_rejected(self):
        comparison = self.inputs["comparison"]
        comparison["blind_score_fingerprint"] = "b" * 64
        comparison.pop("comparison_fingerprint")
        comparison["comparison_fingerprint"] = _fp(comparison)
        with self.assertRaises(G16ExactPublicationError):
            self.build()

    def test_chronology_must_reference_exact_chain(self):
        chronology = self.inputs["chronology"]
        chronology["source"]["g16_posterior_stream_fingerprint"] = "c" * 64
        chronology.pop("artifact_fingerprint")
        chronology["artifact_fingerprint"] = _fp(chronology)
        with self.assertRaises(G16ExactPublicationError):
            self.build()

    def test_random_shuffle_is_rejected_even_if_refingerprinted(self):
        chronology = self.inputs["chronology"]
        chronology["random_shuffle_used"] = True
        chronology.pop("artifact_fingerprint")
        chronology["artifact_fingerprint"] = _fp(chronology)
        with self.assertRaises(G16ExactPublicationError):
            self.build()

    def test_render_filename_is_canonical(self):
        wrong = self.root / "wrong.png"
        wrong.write_bytes(self.inputs["blind_png"].read_bytes())
        self.inputs["blind_png"] = wrong
        with self.assertRaises(G16ExactPublicationError):
            self.build()

    def test_placeholder_png_is_rejected(self):
        self.inputs["refined_png"].write_bytes(b"not-a-render")
        with self.assertRaises(G16ExactPublicationError):
            self.build()

    def test_render_actual_substrate_mismatch_is_rejected(self):
        self.inputs["blind_rt"]["days"][0]["curve_2h"][1][1] += 1
        with self.assertRaises(G16ExactPublicationError):
            self.build()

    def test_visible_stand_down_status_propagates(self):
        completion = self.inputs["causal_completion"]
        first = next(iter(completion["days"]))
        completion["stand_down_days"] = [first]
        completion["days"][first]["n_updated"] = 0
        completion["days"][first]["n_stand_down"] = 1
        completion["status"] = "READY_WITH_STAND_DOWNS"
        completion.pop("fingerprint")
        completion["fingerprint"] = _fp(completion)
        result = self.build()
        self.assertEqual(result["status"], READY_WITH_STAND_DOWNS)
        self.assertEqual(result["stand_down_days"], [first])

    def test_completion_tamper_is_detected(self):
        result = self.build()
        result["actual_sha256"] = "d" * 64
        with self.assertRaises(G16ExactPublicationError):
            validate_completion(result)

    def test_post_g16_registry_never_adopts_or_executes(self):
        result = self.build()
        registry = result["post_g16_shadow_registry"]
        self.assertFalse(registry["brain_adoption_authorized"])
        self.assertFalse(registry["execution_authorized"])
        self.assertFalse(registry["may_update_ng_brain"])
        self.assertFalse(registry["may_change_any_blind_prior"])

    def test_options_lane_remains_unstarted(self):
        result = self.build()
        self.assertFalse(result["options_lane_started"])
        self.assertFalse(result["options_implementation_authorized"])


if __name__ == "__main__":
    unittest.main()
