import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "research"))

import ng_exhaustion_runway_clock as clock

CLASSIFIER = ROOT / "research" / "FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json"
METRICS = ROOT / "research" / "blind_reveal" / "ng_exhaustion_20260816" / "FRANKIE_NG_EXHAUSTION_POSTREVEAL_METRICS_20260816.json"


class ExhaustionRunwayClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classifier = clock.FrozenAClassifier.load(CLASSIFIER)
        cls.engine = clock.ExhaustionRunwayClock(cls.classifier)
        cls.fast = list(cls.classifier.centroids[0])
        cls.persistent = list(cls.classifier.centroids[1])

    def update(self, **kwargs):
        params = {
            "event_id": "evt-1",
            "session_id": "sess-1",
            "t0": "2026-08-16T10:00:00Z",
            "family": "A",
            "elapsed_s": 60.0,
            "a_t0_to_plus60": self.fast,
            "microstructure": "mixed",
        }
        params.update(kwargs)
        return self.engine.update(**params)

    def test_classifier_sha_is_exact(self):
        self.assertEqual(self.classifier.artifact_sha256, clock.EXPECTED_CLASSIFIER_SHA256)

    def test_classifier_sha_drift_fails_closed(self):
        raw = bytearray(CLASSIFIER.read_bytes())
        raw[-2:-1] = b" "
        with tempfile.NamedTemporaryFile(suffix=".json") as handle:
            handle.write(raw)
            handle.flush()
            with self.assertRaises(clock.ClassifierIntegrityError):
                clock.FrozenAClassifier.load(handle.name)

    def test_exact_61d_normalization_and_distance(self):
        fast = self.classifier.classify_t0_to_plus60(self.fast)
        persistent = self.classifier.classify_t0_to_plus60(self.persistent)
        self.assertEqual(fast.post_state, clock.A_FAST_COLLAPSE)
        self.assertEqual(persistent.post_state, clock.A_PERSISTENT)
        self.assertAlmostEqual(fast.distances[0], 0.0, places=12)
        self.assertAlmostEqual(persistent.distances[1], 0.0, places=12)
        self.assertEqual(len(fast.normalized_curve), 61)
        self.assertEqual(fast.normalized_curve[0], 1.0)

    def test_full_121_field_uses_frozen_slice_60(self):
        result = self.classifier.classify_full_minus60_to_plus60([999.0] * 60 + self.persistent)
        self.assertEqual(result.post_state, clock.A_PERSISTENT)

    def test_pre60_never_classifies_A(self):
        out = self.update(elapsed_s=59.999, a_t0_to_plus60=self.fast)
        self.assertEqual(out["post_state"], clock.A_STATE_PENDING)
        self.assertFalse(out["state_confirmed"])
        self.assertIsNone(out["confirmed_at_s"])
        for scale in clock.SCALES:
            self.assertIsNone(out["runways"][scale]["baseline_total_s"])
            self.assertIsNone(out["runways"][scale]["remaining_s"])
        self.assertFalse(out["future_price_accessed"])

    def test_at60_uses_frozen_fast_baselines(self):
        out = self.update(elapsed_s=60.0, a_t0_to_plus60=self.fast)
        self.assertEqual(out["post_state"], clock.A_FAST_COLLAPSE)
        self.assertEqual(out["confirmed_at_s"], 60.0)
        self.assertEqual(out["runways"]["3t"]["baseline_total_s"], 358.0)
        self.assertEqual(out["runways"]["3t"]["remaining_s"], 298.0)
        self.assertEqual(out["runways"]["13t"]["remaining_s"], 4326.0)

    def test_persistent_uses_longer_frozen_reveal_baselines(self):
        out = self.update(a_t0_to_plus60=self.persistent)
        self.assertEqual(out["post_state"], clock.A_PERSISTENT)
        self.assertEqual(
            [out["runways"][scale]["baseline_total_s"] for scale in clock.SCALES],
            [700.0, 1802.0, 3455.0, 6836.0],
        )

    def test_countdown_monotonic_and_never_negative(self):
        early = self.update(elapsed_s=60.0)
        later = self.update(elapsed_s=400.0)
        very_late = self.update(elapsed_s=10000.0)
        for scale in clock.SCALES:
            self.assertLessEqual(later["runways"][scale]["remaining_s"], early["runways"][scale]["remaining_s"])
            self.assertEqual(very_late["runways"][scale]["remaining_s"], 0.0)

    def test_microstructure_changes_confidence_not_seconds_or_identity(self):
        same = self.update(microstructure="same_side")
        mixed = self.update(microstructure="mixed")
        opposite = self.update(microstructure="opposite")
        self.assertEqual(same["post_state"], mixed["post_state"])
        self.assertEqual(opposite["post_state"], mixed["post_state"])
        for scale in clock.SCALES:
            self.assertEqual(same["runways"][scale]["remaining_s"], mixed["runways"][scale]["remaining_s"])
            self.assertEqual(opposite["runways"][scale]["remaining_s"], mixed["runways"][scale]["remaining_s"])
            self.assertEqual(same["runways"][scale]["confidence"]["modifier"], "stronger")
            self.assertEqual(mixed["runways"][scale]["confidence"]["modifier"], "neutral")
            self.assertEqual(opposite["runways"][scale]["confidence"]["modifier"], "weaker")

    def test_missing_A_window_after60_degrades_closed(self):
        out = self.update(a_t0_to_plus60=None, elapsed_s=120.0)
        self.assertEqual(out["post_state"], clock.A_STATE_UNAVAILABLE)
        self.assertIn("a_classifier_window", out["data_gap_status"])
        self.assertEqual(out["runways"]["8t"]["confidence"]["base"], "unavailable")
        self.assertIsNone(out["runways"]["8t"]["remaining_s"])

    def test_B_remains_unresolved_low_confidence(self):
        out = self.update(family="B", a_t0_to_plus60=None, elapsed_s=100.0)
        self.assertEqual(out["post_state"], clock.B_UNRESOLVED)
        self.assertEqual(out["runways"]["3t"]["baseline_total_s"], 353.0)
        self.assertEqual(out["runways"]["3t"]["confidence"]["base"], "low")

    def test_C_is_provisional_fallback(self):
        out = self.update(family="C", a_t0_to_plus60=None, elapsed_s=100.0)
        self.assertEqual(out["post_state"], clock.C_SCALE_TRANSITION_PROVISIONAL)
        self.assertEqual(out["runways"]["13t"]["baseline_total_s"], 4320.0)

    def test_data_flags_fail_closed_or_degrade_confidence(self):
        no_micro = self.update(
            microstructure="same_side",
            data_flags={"microstructure": False, "a_classifier_window": True, "event_clock": True},
        )
        self.assertEqual(no_micro["microstructure_confirmation"], "unavailable")
        self.assertIn("microstructure", no_micro["data_gap_status"])
        self.assertEqual(no_micro["runways"]["8t"]["confidence"]["modifier"], "degraded_unavailable")

        no_classifier = self.update(
            a_t0_to_plus60=self.fast,
            data_flags={"a_classifier_window": False, "event_clock": True},
        )
        self.assertEqual(no_classifier["post_state"], clock.A_STATE_UNAVAILABLE)
        self.assertIsNone(no_classifier["runways"]["8t"]["remaining_s"])

        with self.assertRaises(clock.RunwayClockError):
            self.update(data_flags={"event_clock": False})

    def test_update_is_deterministic(self):
        first = self.update(a_t0_to_plus60=self.persistent, microstructure="same_side", elapsed_s=321.0)
        second = self.update(a_t0_to_plus60=self.persistent, microstructure="same_side", elapsed_s=321.0)
        self.assertEqual(first, second)

    def test_replay_validation_matches_committed_facts(self):
        report = clock.validate_committed_replay_metrics(METRICS)
        self.assertEqual(report["heldout_a_counts"], {clock.A_FAST_COLLAPSE: 831, clock.A_PERSISTENT: 785})
        self.assertEqual(report["heldout_a_total"], 1616)
        self.assertTrue(report["persistent_gt_fast_all_scales_all_days"])
        self.assertTrue(report["frozen_reveal_baselines_preserved"])
        self.assertFalse(report["blind_experiment_rerun"])

    def test_replay_validation_fails_on_count_drift(self):
        metrics = json.loads(METRICS.read_text())
        metrics["by_group"][clock.A_FAST_COLLAPSE]["n"] = 830
        with self.assertRaises(clock.ReplayValidationError):
            clock.validate_committed_replay_metrics(metrics)


if __name__ == "__main__":
    unittest.main()
