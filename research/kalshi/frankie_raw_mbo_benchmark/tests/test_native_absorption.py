"""Tests for section 4.8 absorption, withdrawal, and delivered pressure."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_absorption import (
    ABSORBED_WITHOUT_PRICE_MOVE,
    ACCOMPANIED_BY_WITHDRAWAL,
    DELIVERED_THROUGH_PRICE,
    INDETERMINATE,
    SPARSE,
    AbsorptionCalculator,
    AbsorptionError,
    RunwayPressure,
)


def runway(**overrides) -> RunwayPressure:
    base = dict(
        runway_id="r1",
        instrument_id=42,
        side="B",
        source_day="20211004",
        source_role="HELD_OUT_BLIND",
        continuity_segment=0,
        family_id="TFCN",
        session_phase="RTH",
        opened_recv_ns=1_000,
        closed_recv_ns=2_000,
        traded_quantity=10,
        withdrawn_quantity=0,
        same_side_replacement_quantity=0,
        opposite_side_retreat_quantity=0,
        depth_at_open=100,
        surviving_depth=90,
        price_at_open_raw=1000,
        price_at_close_raw=1000,
        order_ids_at_open=5,
        order_ids_at_close=4,
        order_ids_persisting=3,
    )
    base.update(overrides)
    return RunwayPressure(**base)


class DispositionTest(unittest.TestCase):
    def test_traded_with_no_price_move_is_absorption(self) -> None:
        self.assertEqual(runway().disposition, ABSORBED_WITHOUT_PRICE_MOVE)

    def test_traded_with_a_price_move_is_delivered(self) -> None:
        self.assertEqual(runway(price_at_close_raw=1004).disposition, DELIVERED_THROUGH_PRICE)

    def test_withdrawal_dominating_trade_is_withdrawal_even_when_price_moved(self) -> None:
        """A runway drained by cancels is not evidence about demand, price move or not."""
        r = runway(traded_quantity=2, withdrawn_quantity=20, price_at_close_raw=1004)
        self.assertEqual(r.disposition, ACCOMPANIED_BY_WITHDRAWAL)

    def test_equal_trade_and_withdrawal_is_not_classified_as_withdrawal(self) -> None:
        r = runway(traded_quantity=10, withdrawn_quantity=10)
        self.assertEqual(r.disposition, ABSORBED_WITHOUT_PRICE_MOVE)

    def test_no_depletion_is_indeterminate_not_absorption(self) -> None:
        r = runway(traded_quantity=0, withdrawn_quantity=0)
        self.assertEqual(r.disposition, INDETERMINATE)

    def test_pure_withdrawal_with_no_trade_is_withdrawal(self) -> None:
        r = runway(traded_quantity=0, withdrawn_quantity=15)
        self.assertEqual(r.disposition, ACCOMPANIED_BY_WITHDRAWAL)

    def test_sparsity_is_checked_before_any_determinate_label(self) -> None:
        r = runway(member_count=1, min_members_for_determinacy=5)
        self.assertEqual(r.disposition, SPARSE)

    def test_price_response_is_signed_toward_the_side_under_pressure(self) -> None:
        self.assertEqual(runway(side="B", price_at_close_raw=1005).price_response_raw, 5)
        self.assertEqual(runway(side="A", price_at_close_raw=1005).price_response_raw, -5)

    def test_derived_quantities(self) -> None:
        r = runway(traded_quantity=6, withdrawn_quantity=4, order_ids_at_open=5, order_ids_persisting=3)
        self.assertEqual(r.displayed_depletion, 10)
        self.assertEqual(r.order_id_turnover, 2)
        self.assertEqual(r.as_dict()["elapsed_ns"], 1_000)

    def test_negative_quantities_are_refused(self) -> None:
        with self.assertRaises(AbsorptionError):
            runway(traded_quantity=-1)
        with self.assertRaises(AbsorptionError):
            runway(surviving_depth=-5)

    def test_a_runway_closing_before_it_opens_is_refused(self) -> None:
        with self.assertRaises(AbsorptionError):
            runway(opened_recv_ns=2_000, closed_recv_ns=1_000)


class AbsorptionCalculatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = AbsorptionCalculator()

    def test_both_ratio_forms_are_retained_and_can_disagree(self) -> None:
        """Uneven runway sizes are exactly when the two forms diverge."""
        self.calc.score(runway(traded_quantity=1, withdrawn_quantity=0))
        self.calc.score(runway(traded_quantity=1, withdrawn_quantity=98))
        rows = [r for r in self.calc.absorption_ratio.rows()]
        totals_num = sum(r["value"]["numerator_total"] for r in rows)
        totals_den = sum(r["value"]["denominator_total"] for r in rows)
        self.assertEqual(totals_num, 2.0)
        self.assertEqual(totals_den, 100.0)
        for row in rows:
            self.assertEqual(row["value"]["difference_label"], "COMPLEMENTARY_SCOPE_DIFFERENCE")
            self.assertTrue(row["value"]["coequal"])

    def test_absorption_and_withdrawal_ratios_are_complementary_on_one_runway(self) -> None:
        self.calc.score(runway(traded_quantity=6, withdrawn_quantity=4))
        absorbed = self.calc.absorption_ratio.rows()[0]["value"]["ratio_of_aggregate_sums"]
        withdrawn = self.calc.withdrawal_ratio.rows()[0]["value"]["ratio_of_aggregate_sums"]
        self.assertAlmostEqual(absorbed, 0.6)
        self.assertAlmostEqual(withdrawn, 0.4)
        self.assertAlmostEqual(absorbed + withdrawn, 1.0)

    def test_indeterminate_runways_stay_explicit_rather_than_silent(self) -> None:
        self.calc.score(runway(traded_quantity=0, withdrawn_quantity=0))
        row = self.calc.absorption_ratio.rows()[0]["value"]
        self.assertEqual(row["indeterminate_members"], 1)
        self.assertEqual(row["member_ratio_distribution"]["n"], 0)
        self.assertEqual(self.calc.summary()["disposition_counts"][INDETERMINATE], 1)

    def test_sparse_runways_stay_explicit(self) -> None:
        self.calc.score(runway(member_count=1, min_members_for_determinacy=10))
        self.assertEqual(self.calc.summary()["disposition_counts"][SPARSE], 1)
        self.assertEqual(self.calc.absorption_ratio.rows()[0]["value"]["indeterminate_members"], 1)

    def test_zero_depth_at_open_is_a_counted_zero_denominator_not_a_drop(self) -> None:
        self.calc.score(runway(depth_at_open=0, surviving_depth=0))
        row = self.calc.survival_ratio.rows()[0]["value"]
        self.assertEqual(row["zero_denominator_members"], 1)

    def test_disposition_separates_strata(self) -> None:
        self.calc.score(runway(price_at_close_raw=1000))
        self.calc.score(runway(price_at_close_raw=1004))
        subfamilies = {r["stratum"]["subfamily_id"] for r in self.calc.price_response.rows()}
        self.assertEqual(
            subfamilies,
            {f"disposition={ABSORBED_WITHOUT_PRICE_MOVE}", f"disposition={DELIVERED_THROUGH_PRICE}"},
        )

    def test_days_and_sides_do_not_pool(self) -> None:
        self.calc.score(runway(source_day="20211004", side="B"))
        self.calc.score(runway(source_day="20211005", side="B"))
        self.calc.score(runway(source_day="20211004", side="A"))
        self.assertEqual(self.calc.price_response.stratum_count, 3)

    def test_price_response_distribution_keeps_the_extreme(self) -> None:
        self.calc.score(runway(price_at_close_raw=1001))
        self.calc.score(runway(price_at_close_raw=1050))
        maxima = [r["value"]["maximum"] for r in self.calc.price_response.rows()]
        self.assertIn(50.0, maxima)

    def test_order_id_turnover_is_recorded(self) -> None:
        self.calc.score(runway(order_ids_at_open=8, order_ids_persisting=2))
        self.assertEqual(self.calc.order_id_turnover.rows()[0]["value"]["maximum"], 6.0)

    def test_summary_counts_every_disposition(self) -> None:
        self.calc.score(runway())
        self.calc.score(runway(price_at_close_raw=1004))
        self.calc.score(runway(traded_quantity=1, withdrawn_quantity=50))
        self.calc.score(runway(traded_quantity=0, withdrawn_quantity=0))
        counts = self.calc.summary()["disposition_counts"]
        self.assertEqual(counts[ABSORBED_WITHOUT_PRICE_MOVE], 1)
        self.assertEqual(counts[DELIVERED_THROUGH_PRICE], 1)
        self.assertEqual(counts[ACCOMPANIED_BY_WITHDRAWAL], 1)
        self.assertEqual(counts[INDETERMINATE], 1)
        self.assertEqual(self.calc.summary()["runways_scored"], 4)

    def test_every_companion_row_carries_its_declaration(self) -> None:
        self.calc.score(runway())
        for row in self.calc.companion_rows():
            for field in ("numerator_formula", "population", "causal_cutoff", "status", "missingness_rule"):
                self.assertTrue(row["declaration"][field])


if __name__ == "__main__":
    unittest.main()
