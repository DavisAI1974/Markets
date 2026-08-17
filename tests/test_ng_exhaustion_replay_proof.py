import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "research"))

import ng_exhaustion_replay_proof as proof
from ng_exhaustion_runway_clock import A_FAST_COLLAPSE, A_PERSISTENT, ReplayValidationError

FREEZE_MANIFEST = (
    ROOT
    / "research"
    / "blind_freeze"
    / "ng_exhaustion_20260816"
    / "FRANKIE_NG_EXHAUSTION_BLIND_PREDICTION_FREEZE_MANIFEST_20260816.json"
)


class ExhaustionReplayProofTests(unittest.TestCase):
    def test_blind_freeze_proves_counts_and_no_future_access(self):
        report = proof.validate_blind_freeze_manifest(FREEZE_MANIFEST)
        self.assertEqual(
            report["heldout_a_counts"],
            {A_FAST_COLLAPSE: 831, A_PERSISTENT: 785},
        )
        self.assertEqual(report["prediction_n"], 1711)
        self.assertEqual(report["shard_records"], 1711)
        self.assertTrue(report["freeze_pre_reveal"])
        self.assertFalse(report["future_price_served_to_model"])
        self.assertFalse(report["outcome_accessed_before_freeze"])
        self.assertFalse(report["blind_experiment_rerun"])

    def test_blind_freeze_tamper_fails_closed(self):
        manifest = json.loads(FREEZE_MANIFEST.read_text(encoding="utf-8"))
        manifest["future_price_served_to_model"] = True
        with self.assertRaises(ReplayValidationError):
            proof.validate_blind_freeze_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
