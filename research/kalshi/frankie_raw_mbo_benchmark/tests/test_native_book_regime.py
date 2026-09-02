"""Section 4.2, which did not run at all on the delivered artifact.

D-4: a full-text walk of run 33605852433 for `4.2`, `book_regime`, `daily_book`,
`first_book`, `last_book` and `spread` returned four hits and none was a 4.2 output. Its
absence left `book_full` - 10.13 GB, 93.47% of the exact member ledger - with no consumer.
"""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_book_regime import (
    DAY_COMPANION_FAMILY,
    BookRegimeCalculator,
    BookRegimeError,
)

CTX = dict(
    source_day="20211003",
    source_role="A_CLEAN",
    continuity_segment=0,
    session_phase="RTH",
)


def book(**overrides):
    base = dict(
        best_bid=3_500_000_000,
        best_ask=3_500_010_000,
        bid_depth_full=40,
        ask_depth_full=60,
        bid_order_count_full=4,
        ask_order_count_full=6,
        bid_price_level_count_full=3,
        ask_price_level_count_full=5,
    )
    base.update(overrides)
    return base


class SnapshotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = BookRegimeCalculator()

    def _rows(self):
        return {r["measure"]: r for r in self.calc.companion_rows()}

    def test_the_book_already_on_the_row_produces_every_contracted_measure(self) -> None:
        self.calc.observe_snapshot(book(), recv_ns=1_000, **CTX)
        rows = self._rows()
        self.assertEqual(rows["book_spread_raw"]["value"]["maximum"], 10_000.0)
        self.assertEqual(rows["book_total_depth"]["value"]["maximum"], 100.0)
        self.assertEqual(rows["book_order_count"]["value"]["maximum"], 10.0)
        self.assertEqual(rows["book_level_count"]["value"]["maximum"], 8.0)
        self.assertAlmostEqual(rows["relative_imbalance"]["value"]["maximum"], -0.2)

    def test_a_one_sided_book_has_no_spread_rather_than_a_zero_one(self) -> None:
        """Recording zero would say the two sides met, which is what an absent side denies."""
        self.calc.observe_snapshot(book(best_ask=None), recv_ns=1_000, **CTX)
        row = self._rows()["book_spread_raw"]
        self.assertEqual(row["value"]["n"], 0)
        self.assertEqual(row["excluded_missing_members"], 1)
        self.assertEqual(self.calc.summary()["snapshots_without_a_spread"], 1)

    def test_an_empty_book_has_no_imbalance_but_does_have_a_depth_of_zero(self) -> None:
        """Zero depth IS a measurement; zero imbalance would be a reading of balance."""
        self.calc.observe_snapshot(
            book(bid_depth_full=0, ask_depth_full=0), recv_ns=1_000, **CTX)
        rows = self._rows()
        self.assertEqual(rows["book_total_depth"]["value"]["n"], 1)
        self.assertEqual(rows["book_total_depth"]["value"]["maximum"], 0.0)
        self.assertEqual(rows["relative_imbalance"]["value"]["n"], 0)
        self.assertEqual(rows["relative_imbalance"]["excluded_missing_members"], 1)

    def test_the_extracted_quantities_are_returned_for_the_member_row(self) -> None:
        """A summary with no exact member beneath it is not evidence - gate eight's rule."""
        extracted = self.calc.observe_snapshot(book(), recv_ns=1_234, **CTX)
        self.assertEqual(extracted["recv_ns"], 1_234)
        self.assertEqual(extracted["total_depth"], 100)
        self.assertEqual(extracted["spread_raw"], 10_000)

    def test_a_non_mapping_snapshot_is_refused(self) -> None:
        with self.assertRaises(BookRegimeError):
            self.calc.observe_snapshot([], recv_ns=1, **CTX)


class FirstLastPairTest(unittest.TestCase):
    """The contract names first and last by hand, and neither existed in the artifact."""

    def setUp(self) -> None:
        self.calc = BookRegimeCalculator()

    def test_the_pair_is_the_exact_first_and_last_not_a_statistic(self) -> None:
        self.calc.observe_snapshot(book(bid_depth_full=10), recv_ns=1_000, **CTX)
        self.calc.observe_snapshot(book(bid_depth_full=99), recv_ns=2_000, **CTX)
        self.calc.observe_snapshot(book(bid_depth_full=20), recv_ns=3_000, **CTX)
        pair = self.calc.first_last_pairs()[0]
        self.assertEqual(pair["first_book"]["bid_depth"], 10)
        self.assertEqual(pair["last_book"]["bid_depth"], 20,
                         "last is the last seen, not the largest")

    def test_each_segment_and_phase_keeps_its_own_pair(self) -> None:
        self.calc.observe_snapshot(book(), recv_ns=1_000, **CTX)
        other = {**CTX, "continuity_segment": 1}
        self.calc.observe_snapshot(book(bid_depth_full=7), recv_ns=2_000, **other)
        pairs = self.calc.first_last_pairs()
        self.assertEqual(len(pairs), 2)
        self.assertEqual({p["continuity_segment"] for p in pairs}, {0, 1})


class GroupCompanionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = BookRegimeCalculator()

    def test_group_count_and_the_largest_group_are_both_reported(self) -> None:
        for count in (3, 11, 5):
            self.calc.observe_group_size(count, **CTX)
        summary = self.calc.summary()
        self.assertEqual(summary["groups_observed"], 3)
        self.assertEqual(summary["max_actions_in_a_group"], 11)

    def test_an_empty_group_is_refused(self) -> None:
        with self.assertRaises(BookRegimeError):
            self.calc.observe_group_size(0, **CTX)


class StratumTest(unittest.TestCase):
    def test_the_day_companion_names_its_own_pooling(self) -> None:
        """A blank family on a legitimately cross-family row reads like a lost one - D-14."""
        calc = BookRegimeCalculator()
        calc.observe_snapshot(book(), recv_ns=1, **CTX)
        row = calc.companion_rows()[0]
        self.assertEqual(row["stratum"]["family_id"], DAY_COMPANION_FAMILY)
        self.assertTrue(row["stratum"]["cluster_version"])


if __name__ == "__main__":
    unittest.main()
