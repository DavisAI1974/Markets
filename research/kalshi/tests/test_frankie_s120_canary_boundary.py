from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_s118_redo as s120  # noqa: E402


CLOCK = [20, 22, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20]


def payload(*, disposition: str = "CALL", guess: float = 100, gap: float = 0,
            confidence: str = "med", curve_values: list[float] | None = None) -> dict:
    if curve_values is None:
        # Deliberately non-linear but ends at guess-gap.
        curve_values = [0, -8, -2, 12, 9, 25, 42, 58, 54, 72, 88, 96, guess - gap]
    return {
        "specialist": "B",
        "group": "g18",
        "date": "20260427",
        "guessed_net_usd": guess,
        "overnight_gap_usd": gap,
        "path_p50_curve": [[h, v] for h, v in zip(CLOCK, curve_values)],
        "reasoning": "synthetic structural regression",
        "plays_fired": [],
        "plays_stood_down": [],
        "confidence": confidence,
        "state_defects_and_gaps_reported": [],
        "disposition": disposition,
    }


class S120CanaryBoundaryTests(unittest.TestCase):
    def validate(self, row: dict) -> None:
        s120.validate_day(row, "g18", "20260427", "B")

    def test_explicit_zero_net_low_confidence_abstain_passes(self):
        row = payload(
            disposition="ABSTAIN", guess=0, gap=0, confidence="low",
            curve_values=[0] * len(CLOCK),
        )
        self.validate(row)

    def test_zero_curve_without_explicit_abstain_fails(self):
        row = payload(
            disposition="CALL", guess=0, gap=0, confidence="low",
            curve_values=[0] * len(CLOCK),
        )
        with self.assertRaisesRegex(s120.ForecastStop, "A-86 decorative straight-line"):
            self.validate(row)

    def test_abstain_with_nonzero_net_fails(self):
        row = payload(
            disposition="ABSTAIN", guess=50, gap=0, confidence="low",
            curve_values=[0] * (len(CLOCK) - 1) + [50],
        )
        with self.assertRaisesRegex(s120.ForecastStop, "ABSTAIN requires zero guessed net"):
            self.validate(row)

    def test_nonzero_decorative_straight_line_fails_a86(self):
        values = [100 * i / (len(CLOCK) - 1) for i in range(len(CLOCK))]
        row = payload(disposition="CALL", guess=100, gap=0, curve_values=values)
        with self.assertRaisesRegex(s120.ForecastStop, "A-86 decorative straight-line"):
            self.validate(row)

    def test_nonzero_genuinely_shaped_path_passes(self):
        self.validate(payload())

    def test_every_adapter_required_field_is_enforced(self):
        complete = payload()
        for field in s120.CANARY_ADAPTER_FIELDS:
            row = copy.deepcopy(complete)
            row.pop(field)
            with self.subTest(field=field):
                with self.assertRaisesRegex(s120.ForecastStop, "S120 day-output contract missing fields"):
                    self.validate(row)

    def test_full_brain_keeps_all_play_bodies_and_index(self):
        plays = {f"p{i}": {"id": f"p{i}", "call": f"call {i}"} for i in range(90)}
        index = [
            {"play": f"p{i}", "evaluability": "ARMED" if i < 33 else "INPUT_ABSENT"}
            for i in range(90)
        ]
        view = {"doctrine": {"x": 1}, "play_index": index, "plays": plays}
        served = s120.full_brain(view)
        self.assertEqual(len(served["plays"]), 90)
        self.assertEqual(len(served["play_index"]), 90)
        self.assertEqual(served["_frankie_serving"]["canonical_plays_total"], 90)
        self.assertEqual(served["_frankie_serving"]["full_plays_served"], 90)
        self.assertEqual(served["_frankie_serving"]["index_suggested_count"], 33)
        self.assertTrue(served["_frankie_serving"]["s120_full_availability"])

    def test_a82_rejects_own_day_outcome_but_allows_prior_dated_evidence(self):
        s120.assert_no_outcome_leak(
            'historical 20260424 actual_day_move_usd was recorded', "g18", "20260427"
        )
        with self.assertRaisesRegex(s120.ForecastStop, "own/future"):
            s120.assert_no_outcome_leak(
                'target 20260427 actual_day_move_usd was recorded', "g18", "20260427"
            )

    def test_contract_authority_is_current_bld1_eleven_plus_disposition(self):
        self.assertEqual(len(s120.CANONICAL_BLD1_DAY_FIELDS), 11)
        self.assertEqual(len(s120.CANARY_ADAPTER_FIELDS), 12)
        self.assertEqual(s120.CANARY_ADAPTER_FIELDS[-1], "disposition")


if __name__ == "__main__":
    unittest.main()
