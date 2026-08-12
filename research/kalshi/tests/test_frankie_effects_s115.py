from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_effects_s115 import retention_falsifier, specialist_prior_falsifier  # noqa: E402


class FrankieEffectTests(unittest.TestCase):
    def test_a68_no_same_lens_event_improvement_declares_inert(self):
        carrying = [
            {"event_id": "e1", "lens": "B", "absolute_error": 4.0},
            {"event_id": "e2", "lens": "B", "absolute_error": 2.0},
        ]
        noncarrying = [
            {"event_id": "e1", "lens": "B", "absolute_error": 4.0},
            {"event_id": "e2", "lens": "B", "absolute_error": 2.0},
        ]
        report = retention_falsifier(carrying=carrying, noncarrying=noncarrying, lens="B")
        self.assertEqual(report["verdict"], "RETENTION_INERT_ONE_SESSION")
        self.assertIsNone(report["pooled_scalar"])
        self.assertIn("no same-lens event improvement", report["report_statement"])

    def test_a62_no_failure_or_emission_change_means_cut(self):
        before = [
            {"event_id": "e1", "lens": "E", "named_failure_present": True, "emitted": False},
            {"event_id": "e2", "lens": "E", "named_failure_present": False, "emitted": True},
        ]
        after = [
            {"event_id": "e1", "lens": "E", "named_failure_present": True, "emitted": False},
            {"event_id": "e2", "lens": "E", "named_failure_present": False, "emitted": True},
        ]
        report = specialist_prior_falsifier(before=before, after=after, lens="E")
        self.assertEqual(report["verdict"], "INERT_CUT")
        self.assertIsNone(report["pooled_scalar"])
        self.assertIn("cut them", report["report_statement"])


if __name__ == "__main__":
    unittest.main()
