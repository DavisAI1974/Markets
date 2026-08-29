"""Tests for section 4.9 price-ladder topology."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_ladder import (
    COMPRESSION,
    EXPANSION,
    UNCHANGED,
    LadderCalculator,
    LadderError,
    LadderSide,
    LadderTransition,
    relative_imbalance,
)

CTX = dict(
    source_day="20211004",
    source_role="HELD_OUT_BLIND",
    continuity_segment=0,
    family_id="AN",
    session_phase="RTH",
)


class LadderSideTest(unittest.TestCase):
    def test_best_price_differs_by_side(self) -> None:
        depths = {1000: 5, 1001: 7, 1002: 3}
        self.assertEqual(LadderSide(side="B", depth_by_price=depths).best_price, 1002)
        self.assertEqual(LadderSide(side="A", depth_by_price=depths).best_price, 1000)

    def test_zero_depth_prices_are_not_occupied(self) -> None:
        side = LadderSide(side="B", depth_by_price={1000: 5, 1001: 0})
        self.assertEqual(side.occupied_prices, frozenset({1000}))
        self.assertEqual(side.occupied_level_count, 1)
        self.assertEqual(side.total_depth, 5)

    def test_gaps_are_exact_spacings_best_first(self) -> None:
        side = LadderSide(side="B", depth_by_price={1000: 1, 1002: 1, 1007: 1})
        self.assertEqual(side.price_gaps, [5, 2])

    def test_a_single_level_has_no_gaps(self) -> None:
        self.assertEqual(LadderSide(side="B", depth_by_price={1000: 4}).price_gaps, [])

    def test_depth_concentration_is_the_touch_share(self) -> None:
        side = LadderSide(side="B", depth_by_price={1000: 1, 1001: 3})
        self.assertAlmostEqual(side.depth_concentration, 0.75)

    def test_empty_side_reports_none_not_zero(self) -> None:
        side = LadderSide(side="B", depth_by_price={})
        self.assertIsNone(side.best_price)
        self.assertIsNone(side.depth_concentration)
        self.assertEqual(side.total_depth, 0)

    def test_invalid_side_or_negative_depth_is_refused(self) -> None:
        with self.assertRaises(LadderError):
            LadderSide(side="X", depth_by_price={})
        with self.assertRaises(LadderError):
            LadderSide(side="B", depth_by_price={1000: -1})


class LadderTransitionTest(unittest.TestCase):
    def test_births_and_deaths_are_set_differences(self) -> None:
        before = LadderSide(side="B", depth_by_price={1000: 5, 1001: 5})
        after = LadderSide(side="B", depth_by_price={1001: 5, 1002: 5})
        t = LadderTransition(before=before, after=after, recv_ns=1)
        self.assertEqual(t.level_births, frozenset({1002}))
        self.assertEqual(t.level_deaths, frozenset({1000}))

    def test_a_level_whose_size_merely_fell_did_not_die(self) -> None:
        """Inferring deaths from depth changes would invent discontinuities."""
        before = LadderSide(side="B", depth_by_price={1000: 100})
        after = LadderSide(side="B", depth_by_price={1000: 1})
        t = LadderTransition(before=before, after=after, recv_ns=1)
        self.assertEqual(t.level_deaths, frozenset())
        self.assertEqual(t.level_births, frozenset())
        self.assertEqual(t.depth_migration, -99)

    def test_a_level_falling_to_zero_does_die(self) -> None:
        before = LadderSide(side="B", depth_by_price={1000: 100})
        after = LadderSide(side="B", depth_by_price={1000: 0})
        self.assertEqual(LadderTransition(before=before, after=after, recv_ns=1).level_deaths, frozenset({1000}))

    def test_touch_migration_is_signed_toward_the_side_aggression(self) -> None:
        bid_up = LadderTransition(
            before=LadderSide(side="B", depth_by_price={1000: 1}),
            after=LadderSide(side="B", depth_by_price={1002: 1}),
            recv_ns=1,
        )
        self.assertEqual(bid_up.touch_migration_raw, 2)
        self.assertEqual(bid_up.touch_state, EXPANSION)

        ask_down = LadderTransition(
            before=LadderSide(side="A", depth_by_price={1002: 1}),
            after=LadderSide(side="A", depth_by_price={1000: 1}),
            recv_ns=1,
        )
        self.assertEqual(ask_down.touch_migration_raw, 2)
        self.assertEqual(ask_down.touch_state, EXPANSION)

    def test_a_retreating_touch_is_compression(self) -> None:
        t = LadderTransition(
            before=LadderSide(side="B", depth_by_price={1002: 1}),
            after=LadderSide(side="B", depth_by_price={1000: 1}),
            recv_ns=1,
        )
        self.assertEqual(t.touch_migration_raw, -2)
        self.assertEqual(t.touch_state, COMPRESSION)

    def test_an_empty_side_yields_no_migration(self) -> None:
        t = LadderTransition(
            before=LadderSide(side="B", depth_by_price={1000: 1}),
            after=LadderSide(side="B", depth_by_price={}),
            recv_ns=1,
        )
        self.assertIsNone(t.touch_migration_raw)
        self.assertEqual(t.touch_state, UNCHANGED)

    def test_mismatched_sides_are_refused(self) -> None:
        with self.assertRaises(LadderError):
            LadderTransition(
                before=LadderSide(side="B", depth_by_price={}),
                after=LadderSide(side="A", depth_by_price={}),
                recv_ns=1,
            )

    def test_causing_orders_are_preserved(self) -> None:
        t = LadderTransition(
            before=LadderSide(side="B", depth_by_price={1000: 1}),
            after=LadderSide(side="B", depth_by_price={1001: 1}),
            recv_ns=1,
            causing_order_ids=(7, 9),
        )
        self.assertEqual(t.as_dict()["causing_order_ids"], [7, 9])


class RelativeImbalanceTest(unittest.TestCase):
    def test_signed_and_bounded(self) -> None:
        self.assertAlmostEqual(relative_imbalance(75, 25), 0.5)
        self.assertAlmostEqual(relative_imbalance(25, 75), -0.5)
        self.assertAlmostEqual(relative_imbalance(50, 50), 0.0)

    def test_empty_book_is_none_not_zero(self) -> None:
        self.assertIsNone(relative_imbalance(0, 0))

    def test_imbalance_is_independent_of_absolute_depth(self) -> None:
        """The reason section 4.9 keeps them separate."""
        self.assertEqual(relative_imbalance(10, 30), relative_imbalance(100, 300))


class LadderCalculatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = LadderCalculator()

    def transition(self, before: dict, after: dict, side: str = "B") -> LadderTransition:
        return LadderTransition(
            before=LadderSide(side=side, depth_by_price=before),
            after=LadderSide(side=side, depth_by_price=after),
            recv_ns=1_000,
        )

    def test_absolute_depth_and_imbalance_are_separate_measures(self) -> None:
        t = self.transition({1000: 10}, {1000: 30})
        self.calc.observe(t, opposite_side_depth=90, **CTX)
        depth = self.calc.absolute_depth.rows()[0]["value"]["maximum"]
        imbalance = self.calc.relative_imbalance.rows()[0]["value"]["maximum"]
        self.assertEqual(depth, 30.0)
        self.assertAlmostEqual(imbalance, (30 - 90) / 120)

    def test_imbalance_orients_by_side(self) -> None:
        ask = self.transition({1000: 10}, {1000: 30}, side="A")
        self.calc.observe(ask, opposite_side_depth=90, **CTX)
        imbalance = self.calc.relative_imbalance.rows()[0]["value"]["maximum"]
        self.assertAlmostEqual(imbalance, (90 - 30) / 120)

    def test_missing_opposite_depth_is_excluded_and_counted(self) -> None:
        self.calc.observe(self.transition({1000: 10}, {1000: 30}), **CTX)
        row = self.calc.relative_imbalance.rows()[0]
        self.assertEqual(row["value"]["n"], 0)
        self.assertEqual(row["excluded_missing_members"], 1)

    def test_single_level_side_is_excluded_from_gaps_not_counted_as_zero(self) -> None:
        self.calc.observe(self.transition({1000: 1}, {1000: 1}), **CTX)
        row = self.calc.price_gap.rows()[0]
        self.assertEqual(row["value"]["n"], 0)
        self.assertEqual(row["excluded_missing_members"], 1)

    def test_gaps_keep_the_rare_discontinuity(self) -> None:
        self.calc.observe(self.transition({1000: 1}, {1000: 1, 1001: 1, 1099: 1}), **CTX)
        self.assertEqual(self.calc.price_gap.rows()[0]["value"]["maximum"], 98.0)

    def test_touch_state_separates_strata(self) -> None:
        self.calc.observe(self.transition({1000: 1}, {1002: 1}), **CTX)
        self.calc.observe(self.transition({1002: 1}, {1000: 1}), **CTX)
        subfamilies = {r["stratum"]["subfamily_id"] for r in self.calc.occupied_levels.rows()}
        self.assertEqual(subfamilies, {f"touch_state={EXPANSION}", f"touch_state={COMPRESSION}"})

    def test_empty_side_excluded_from_migration_and_concentration(self) -> None:
        self.calc.observe(self.transition({1000: 1}, {}), **CTX)
        self.assertEqual(self.calc.touch_migration.rows()[0]["excluded_missing_members"], 1)
        self.assertEqual(self.calc.depth_concentration.rows()[0]["excluded_missing_members"], 1)

    def test_births_and_deaths_are_accumulated(self) -> None:
        self.calc.observe(self.transition({1000: 1, 1001: 1}, {1001: 1, 1002: 1, 1003: 1}), **CTX)
        self.assertEqual(self.calc.level_births.rows()[0]["value"]["maximum"], 2.0)
        self.assertEqual(self.calc.level_deaths.rows()[0]["value"]["maximum"], 1.0)

    def test_days_do_not_pool(self) -> None:
        self.calc.observe(self.transition({1000: 1}, {1000: 2}), **{**CTX, "source_day": "20211004"})
        self.calc.observe(self.transition({1000: 1}, {1000: 2}), **{**CTX, "source_day": "20211005"})
        self.assertEqual(self.calc.occupied_levels.stratum_count, 2)

    def test_summary_records_the_separation_and_the_counts(self) -> None:
        self.calc.observe(self.transition({1000: 1}, {1002: 1}), **CTX)
        summary = self.calc.summary()
        self.assertEqual(summary["section"], "4.9")
        self.assertEqual(summary["transitions"], 1)
        self.assertEqual(summary["touch_state_counts"][EXPANSION], 1)
        self.assertIn("never combined", self.calc.absolute_depth.declaration.missingness_rule)


if __name__ == "__main__":
    unittest.main()
