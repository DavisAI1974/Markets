#!/usr/bin/env python3
from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

import ng_exhaustion_pox_raw_execution_20260819 as execution
import ng_exhaustion_pox_standalone_analysis_20260819 as analysis


class SyntheticDay:
    def __init__(self, base: float):
        n = 86400
        seconds = np.arange(n, dtype=float)
        self.last_trade = base + seconds * 1e-6
        self.mid = base + 0.0005 + seconds * 1e-6
        self.buy_volume = np.zeros(n, dtype=float)
        self.sell_volume = np.zeros(n, dtype=float)
        self.buy_volume[::3] = 2.0
        self.sell_volume[1::3] = 1.0
        self.buy_volume_cumsum = np.concatenate(([0.0], np.cumsum(self.buy_volume)))
        self.sell_volume_cumsum = np.concatenate(([0.0], np.cumsum(self.sell_volume)))
        self.book_imbalance_mean = np.sin(seconds / 100.0) * 0.25
        self.book_imbalance = self.book_imbalance_mean.copy()
        self.first_observed_second = 0
        self.last_observed_second = n - 1
        self.week_first_trade_elapsed_s = 0


def assert_feature_maps_equal(test: unittest.TestCase, left: dict[str, float], right: dict[str, float]) -> None:
    test.assertEqual(set(left), set(right))
    for key in left:
        a, b = left[key], right[key]
        if math.isnan(a) and math.isnan(b):
            continue
        test.assertEqual(a, b, key)


class DynamicClockTests(unittest.TestCase):
    def test_data_derived_grids_have_no_fixed_h_cap(self) -> None:
        self.assertEqual(analysis.h_checkpoint_grid(4), [0, 1, 2, 3, 4])
        self.assertEqual(analysis.h_checkpoint_grid(62)[-1], 60)
        self.assertEqual(analysis.h_checkpoint_grid(607)[-1], 605)
        prior = analysis.prior_checkpoint_grid([-77, -12, None])
        self.assertIn(-77, prior)
        self.assertIn(-75, prior)
        self.assertIn(-1, prior)
        self.assertFalse(analysis.on_prior_checkpoint_grid(-77, -76))
        self.assertTrue(analysis.on_prior_checkpoint_grid(-77, -75))

    def test_predecessor_state_is_strictly_causal(self) -> None:
        case = {
            "predecessor_causal_context": {
                "confirmation_offset_s": -17,
                "polarity": -1,
                "family": "B",
            }
        }
        before = analysis.predecessor_features(case, -18)
        at = analysis.predecessor_features(case, -17)
        self.assertEqual(before["predecessor_confirmed_by_checkpoint"], 0.0)
        self.assertTrue(math.isnan(before["predecessor_polarity"]))
        self.assertEqual(at["predecessor_confirmed_by_checkpoint"], 1.0)
        self.assertEqual(at["predecessor_polarity"], -1.0)
        self.assertEqual(at["predecessor_family_B"], 1.0)

    def test_target_specific_membership_state_waits_for_confirmation(self) -> None:
        candidate = {
            "clock": {"day": "20250930", "second_utc": 100},
            "polarity": 1,
            "causal_family": "A",
            "endpoint_posthoc": {
                "censored": False,
                "causal_confirmation_offset_s": 10,
                "structural_onset_offset_s": 4,
            },
            "pre_roll20_oriented_t_minus60_to_t0": [0.25] * 61,
            "predecessor_causal_context": None,
        }
        with patch.object(analysis, "raw_market_features", side_effect=lambda *args: {}):
            at_birth = analysis.membership_features(candidate, 0, {})
            at_confirmation = analysis.membership_features(candidate, 10, {})
        self.assertTrue(math.isnan(at_birth["origin_polarity"]))
        self.assertTrue(math.isnan(at_birth["causal_pre_t0_family_A"]))
        self.assertTrue(math.isnan(at_birth["candidate_pre_roll20_oriented__at_+0"]))
        self.assertEqual(at_confirmation["origin_polarity"], 1.0)
        self.assertEqual(at_confirmation["causal_pre_t0_family_A"], 1.0)
        self.assertEqual(at_confirmation["candidate_pre_roll20_oriented__at_+0"], 0.25)

    def test_branch_h0_is_eligible_before_origin_confirmation(self) -> None:
        cases = []
        for day_index, day in enumerate(("20250929", "20250930", "20251001")):
            for label_index, label in enumerate(("SAME", "FLIP")):
                cases.append(
                    {
                        "case_id": f"{day}-{label}",
                        "clock": {"day": day},
                        "branch_label": label,
                        "origin_confirmation_offset_s": 10,
                        "branch_causally_known_offset_s": 21,
                        "branch_h_end_offset_s": 20,
                    }
                )

        def tiny_matrix(rows, checkpoint_s, raw_days, feature_names=None):
            values = np.asarray(
                [[float(row["branch_label"] == "FLIP"), float(checkpoint_s)] for row in rows],
                dtype=float,
            )
            return values, feature_names or ["label_proxy_for_eligibility_test", "checkpoint"]

        with patch.object(analysis, "matrix", side_effect=tiny_matrix):
            result, _ = analysis.stage2(cases, {}, [0], pass_name="TEST_H0")
        self.assertEqual(result["checkpoints"][0]["eligible_prediction_window_n"], len(cases))

    def test_prebirth_clock_is_decision_time_not_future_birth_time(self) -> None:
        case = {
            "clock": {"day": "20250930", "second_utc": 100, "market_clock": "00:01:40"},
            "causal_record": {},
            "predecessor_causal_context": None,
            "origin_confirmation_offset_s": 10,
            "polarity": 1,
            "frozen_target_family": "A",
            "roster_causal_fields": {"endpoint_posthoc": {}},
        }
        with patch.object(analysis, "raw_market_features", side_effect=lambda *args: {}):
            features = analysis.causal_features(case, -5, {})
        expected = math.sin(2.0 * math.pi * 95.0 / 86400.0)
        future_birth = math.sin(2.0 * math.pi * 100.0 / 86400.0)
        self.assertAlmostEqual(features["clock_utc_sin"], expected)
        self.assertNotEqual(features["clock_utc_sin"], future_birth)
        self.assertTrue(math.isnan(features["origin_polarity"]))

    def test_oriented_target_paths_and_milestones_wait_for_confirmation(self) -> None:
        case = {
            "clock": {"day": "20250930", "second_utc": 100, "market_clock": "00:01:40"},
            "causal_record": {
                "dipole_roll20_oriented_t_minus60_to_plus60": [0.5] * 121,
                "post_exhaustion": {"t50_s": 0},
            },
            "predecessor_causal_context": None,
            "origin_confirmation_offset_s": 10,
            "polarity": 1,
            "frozen_target_family": "A",
            "roster_causal_fields": {"endpoint_posthoc": {}},
        }
        with patch.object(analysis, "raw_market_features", side_effect=lambda *args: {}):
            before = analysis.causal_features(case, 5, {})
            confirmed = analysis.causal_features(case, 10, {})
        self.assertTrue(math.isnan(before["dipole_roll20_oriented__checkpoint_lag0"]))
        self.assertEqual(before["causal_milestone_t50_s_observed_by_h"], 0.0)
        self.assertEqual(confirmed["dipole_roll20_oriented__checkpoint_lag0"], 0.5)
        self.assertEqual(confirmed["causal_milestone_t50_s_observed_by_h"], 1.0)

    def test_oriented_raw_price_waits_for_confirmation(self) -> None:
        case = {
            "clock": {"day": "20250930", "second_utc": 100},
            "polarity": 1,
            "origin_confirmation_offset_s": 10,
            "prior_start_offset_s": -20,
        }
        days = {"20250930": SimpleNamespace(level_fields={})}

        def state_value(raw_days, day, second, field, **kwargs):
            return 3.0 + float(second) * 0.001

        with (
            patch.object(analysis, "raw_state_value", side_effect=state_value),
            patch.object(analysis, "raw_count_value", return_value=0.0),
            patch.object(analysis, "live_market_features", return_value={}),
        ):
            before = analysis.raw_market_features(case, 5, days)
            confirmed = analysis.raw_market_features(case, 10, days)
        self.assertTrue(math.isnan(before["raw_mid_oriented_ticks_from_t0__checkpoint"]))
        self.assertTrue(math.isfinite(confirmed["raw_mid_oriented_ticks_from_t0__checkpoint"]))


class LiveStateTests(unittest.TestCase):
    def test_v3_live_state_crosses_midnight_and_ignores_future_rows(self) -> None:
        days = {
            "20250930": SyntheticDay(3.0),
            "20251001": SyntheticDay(3.0864),
        }
        case = {
            "clock": {"day": "20251001", "second_utc": 74},
            "source_roster_identity": {"week_sunday": "20250928"},
        }
        checkpoint = -60  # cutoff is 00:00:14; 120-second lag is on prior UTC day.
        before = analysis.live_market_features(case, checkpoint, days)
        self.assertEqual(before["v3_live_trade_direction_lag120_known"], 1.0)
        self.assertEqual(before["v3_live_trade_dense_path_lag60_known"], 1.0)
        self.assertIn("v3_live_dipole_roll20_path_lag0", before)
        self.assertIn("v3_live_book_change_lag60", before)

        # Mutating every row after the completed cutoff must not change a feature.
        current = days["20251001"]
        current.last_trade[15:] += 1000.0
        current.mid[15:] += 1000.0
        current.buy_volume[15:] += 999.0
        current.sell_volume[15:] += 777.0
        current.buy_volume_cumsum = np.concatenate(([0.0], np.cumsum(current.buy_volume)))
        current.sell_volume_cumsum = np.concatenate(([0.0], np.cumsum(current.sell_volume)))
        current.book_imbalance_mean[15:] = -0.99
        current.book_imbalance[15:] = -0.99
        after = analysis.live_market_features(case, checkpoint, days)
        assert_feature_maps_equal(self, before, after)


class CrossMidnightExecutionTests(unittest.TestCase):
    def test_quote_side_path_uses_next_utc_day(self) -> None:
        tapes = {
            "20250930": execution.QuoteTape(
                "20250930",
                [(86399.0, 3.000, 3.001, "M", 0)],
                1,
            ),
            "20251001": execution.QuoteTape(
                "20251001",
                [(0.5, 3.002, 3.003, "M", 0), (1.0, 3.004, 3.005, "M", 1)],
                2,
            ),
        }
        result = execution.execution_path(
            execution.QuoteCorpus(tapes),
            "20250930",
            86399.0,
            86401.0,
            1,
        )
        self.assertEqual(result["status"], "EXECUTED_EXACT_MBP10_QUOTE_SIDE")
        self.assertEqual(result["entry"]["day"], "20250930")
        self.assertEqual(result["exit"]["day"], "20251001")
        self.assertAlmostEqual(result["gross_executable_ticks"], 3.0)

    def test_stage1_executes_each_dynamic_first_call_once(self) -> None:
        quotes = []
        for index, second in enumerate(range(104, 166)):
            bid = 3.0 + (second - 104) * 0.001
            quotes.append((float(second), bid, bid + 0.001, "M", index))
        corpus = execution.QuoteCorpus({"20250930": execution.QuoteTape("20250930", quotes, len(quotes))})
        cases = [
            {
                "case_id": "case-1",
                "clock": {"day": "20250930", "second_utc": 100},
                "source_roster_identity": {"week_sunday": "20250928"},
                "branch_label": "SAME",
                "polarity": 1,
                "successor_polarity": 1,
                "origin_confirmation_offset_s": 3,
                "branch_causally_known_offset_s": 51,
                "computational_prediction_window": {
                    "prior_start_offset_s": -20,
                    "h_end_offset_s": 50,
                },
            }
        ]
        first_calls = [
            {
                "case_id": "case-1",
                "cascade_status": "FIRST_CALL_EMITTED",
                "first_call_stage": "PREBIRTH",
                "first_call_checkpoint_s": -5,
            }
        ]
        result, rows, entries = execution.stage1(cases, corpus, first_calls)
        self.assertEqual(entries, {"case-1": 3})
        self.assertEqual(result["first_call_n"], 1)
        self.assertEqual(len(rows), len(execution.HOLDS_S))
        self.assertTrue(all("checkpoint_s" not in cell for cell in result["cells"]))
        self.assertTrue(all(row["execution_information_end_offset_s"] == 3 for row in rows))
        with tempfile.TemporaryDirectory() as tmp:
            ledger = execution.finalize_rule_ledger(
                Path(tmp),
                result,
                {"cells": [], "parent_exit_comparison": {"status": "TEST_ONLY"}},
                {"cells": []},
            )
        stage1_rules = [row for row in ledger if row["rule_id"].startswith("STAGE1_")]
        self.assertTrue(stage1_rules)
        self.assertTrue(all(row["rule_id"].startswith("STAGE1_DYNAMIC_FIRST_CALL_HOLD") for row in stage1_rules))


if __name__ == "__main__":
    unittest.main()
