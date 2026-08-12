from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_s121_curve_restore as s121  # noqa: E402


def payload(*, disposition="CALL", guess=180, gap=20, curve=None):
    if curve is None:
        curve = [
            [20.0, 0], [20.3, 8], [20.9, -4], [21.15, 12], [21.8, 25], [22.05, 18],
            [22.4, 40], [23.1, 55], [0.2, 48], [0.45, 65], [1.1, 82], [2.35, 70],
            [3.0, 95], [4.8, 88], [5.25, 110], [6.4, 104], [7.05, 130], [7.3, 122],
            [8.15, 150], [8.45, 138], [9.2, 165], [10.05, 154], [10.8, 172], [11.2, 160],
        ]
    return {
        "specialist": "B", "group": "g18", "date": "20260427",
        "guessed_net_usd": guess, "overnight_gap_usd": gap,
        "path_p50_curve": curve,
        "reasoning": "synthetic endogenous path",
        "plays_fired": [], "plays_stood_down": [], "confidence": "med",
        "state_defects_and_gaps_reported": [], "disposition": disposition,
    }


class S121CurveRestoreTests(unittest.TestCase):
    def validate(self, row):
        s121.validate_day(row, "g18", "20260427", "B")

    def test_variable_irregular_dense_timestamps_pass(self):
        self.validate(payload())

    def test_hhmm_strings_and_fractional_hours_are_both_allowed(self):
        row = payload(
            guess=120, gap=0,
            curve=[["20:00", 0], ["20:17", 9], [21.1, -3], ["22:41", 28],
                   [0.4, 16], ["02:13", 45], [4.6, 37], ["06:52", 70],
                   [8.2, 61], ["10:11", 88], [12.7, 105], ["16:43", 120]],
        )
        self.validate(row)

    def test_no_fixed_clock_grid_is_required(self):
        pts = s121.curve_points([[20.0, 0], [20.13, 5], [21.77, -2], [23.42, 9], [1.03, 4]], "g18", "20260427")
        self.assertEqual(len(pts), 5)

    def test_abstain_does_not_flatten_or_zero_the_market_forecast(self):
        row = payload(disposition="ABSTAIN")
        self.validate(row)
        self.assertNotEqual(row["guessed_net_usd"], 0)
        self.assertTrue(any(v != 0 for _, v in row["path_p50_curve"][1:]))

    def test_exact_decorative_interpolation_still_fails_a86(self):
        curve = [[20.0, 0], [21.0, 10], [22.0, 20], [23.0, 30], [0.0, 40], [1.0, 50],
                 [2.0, 60], [3.0, 70], [4.0, 80], [5.0, 90], [6.0, 100]]
        row = payload(guess=100, gap=0, curve=curve)
        with self.assertRaisesRegex(s121.ForecastStop, "A-86 decorative exact endpoint interpolation"):
            self.validate(row)

    def test_chronology_is_enforced_without_cadence(self):
        row = payload(guess=30, gap=0, curve=[[20.0, 0], [21.4, 10], [21.2, 20], [22.0, 30]])
        with self.assertRaisesRegex(s121.ForecastStop, "strictly chronological"):
            self.validate(row)

    def test_endpoint_reconciles_to_net_ex_gap(self):
        row = payload()
        row["path_p50_curve"][-1][1] = 999
        with self.assertRaisesRegex(s121.ForecastStop, "endpoint does not reconcile"):
            self.validate(row)

    def test_adapter_text_explicitly_forbids_fixed_grid_and_flat_abstain_semantics(self):
        text = s121.S121_OUTPUT_ADDENDUM
        self.assertIn("NO required cadence", text)
        self.assertIn("ABSTAIN does NOT erase the market forecast", text)
        self.assertIn("do not average", text.lower())


if __name__ == "__main__":
    unittest.main()
