"""Section 4.0, the per-second flow and quote substrate.

Frankie's item (a) after run 33605852433: the substrate the detector and 4.12 run on was
`traversal.legacy_per_second_roll20`, a counters block with no section beneath it - no
declaration, no stratum, no denominator, no gate - which is why the 51.6% NO_DIRECTION
share had to be reconstructed from counters and why the classification rule could not be
checked anywhere. These are the CALCULATOR's tests; the driver-level proof that it is fed
lives in `test_native_replay_driver.py`, because a calculator's own tests passing while the
driver never calls it is S119's recorded mistake.
"""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark import native_roll20
from research.kalshi.frankie_raw_mbo_benchmark.native_flow_substrate import (
    BALANCED,
    BUY,
    CLASSIFICATIONS,
    EXCLUDED_AT_MID,
    INCOMPLETE_SEGMENT_END,
    INCOMPLETE_STREAM_END,
    NO_DIRECTION,
    NO_QUOTE,
    NO_TRADES,
    SELL,
    SUBSTRATE_FAMILY,
    UNUSABLE_PRICE_OR_SIZE,
    WINDOW_LONG,
    WINDOW_NO_DIRECTION,
    WINDOW_SHORT,
    FlowSubstrateCalculator,
    FlowSubstrateError,
)

CTX = dict(
    source_day="20211004",
    source_role="A_CLEAN",
    continuity_segment=18904,
    session_phase="PRE_SETTLEMENT",
)
SECOND = 1_633_046_400


def legacy_row(**over):
    """A legacy control row in the shape the V4 adapter projects; a trade above the mid."""
    row = {
        "census_view": "LEGACY_CONTROL",
        "action": "T",
        "side": "B",
        "price": 5.001,
        "size": 3,
        "ts_recv": float(SECOND) + 0.25,
        "ts_event": float(SECOND) + 0.10,
        "instrument_id": 42,
        "bid_px_00": 4.998,
        "ask_px_00": 5.002,
    }
    row.update(over)
    return row


def complete(calc, second, *, buy=0.0, sell=0.0, window_flow=0, roll20=float("nan"),
             polarity=0, **ctx_over):
    """Judge one second with the traversal's binner witness matching the section's tally."""
    ctx = {**CTX, **ctx_over}
    return calc.complete_second(
        second, roll20_value=roll20, window_signed_flow=window_flow, polarity=polarity,
        buy_volume=buy, sell_volume=sell, **ctx,
    )


class ClassificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = FlowSubstrateCalculator()

    def test_a_trade_above_the_mid_makes_a_buy_second(self) -> None:
        self.calc.observe_group_rows([legacy_row()], second=SECOND, source_day="20211004")
        row = complete(self.calc, SECOND, buy=3.0)
        self.assertEqual(row["classification"], BUY)
        self.assertEqual(row["buy_volume"], 3.0)
        self.assertEqual(row["buy_trades"], 1)
        self.assertEqual(row["last_quote"], {"bid": 4.998, "ask": 5.002, "mid": 5.0})

    def test_a_trade_below_the_mid_makes_a_sell_second(self) -> None:
        self.calc.observe_group_rows([legacy_row(price=4.999)], second=SECOND,
                                     source_day="20211004")
        row = complete(self.calc, SECOND, sell=3.0)
        self.assertEqual(row["classification"], SELL)
        self.assertEqual(row["net_volume"], -3.0)

    def test_the_tape_side_field_is_never_consulted(self) -> None:
        """The rule is price against the mid. Flipping the tape's own side changes nothing."""
        a = FlowSubstrateCalculator()
        b = FlowSubstrateCalculator()
        a.observe_group_rows([legacy_row(side="B")], second=SECOND, source_day="20211004")
        b.observe_group_rows([legacy_row(side="A")], second=SECOND, source_day="20211004")
        self.assertEqual(complete(a, SECOND, buy=3.0), complete(b, SECOND, buy=3.0))

    def test_balanced_volume_is_no_direction_for_the_reason_balanced(self) -> None:
        self.calc.observe_group_rows(
            [legacy_row(price=5.001), legacy_row(price=4.999)],
            second=SECOND, source_day="20211004",
        )
        row = complete(self.calc, SECOND, buy=3.0, sell=3.0)
        self.assertEqual(row["classification"], NO_DIRECTION)
        self.assertEqual(row["no_direction_reason"], BALANCED)

    def test_a_second_with_no_rows_is_no_direction_for_no_trades(self) -> None:
        row = complete(self.calc, SECOND)
        self.assertEqual(row["classification"], NO_DIRECTION)
        self.assertEqual(row["no_direction_reason"], NO_TRADES)
        self.assertEqual(row["rows"], 0)

    def test_trades_all_at_the_mid_are_a_class_not_a_gap(self) -> None:
        self.calc.observe_group_rows([legacy_row(price=5.0)], second=SECOND,
                                     source_day="20211004")
        row = complete(self.calc, SECOND)
        self.assertEqual(row["classification"], EXCLUDED_AT_MID)
        self.assertEqual(row["at_mid_trades"], 1)
        self.assertEqual(row["trades"], 1)

    def test_trades_without_a_usable_quote_are_a_class(self) -> None:
        self.calc.observe_group_rows([legacy_row(bid_px_00=0.0, ask_px_00=0.0)],
                                     second=SECOND, source_day="20211004")
        row = complete(self.calc, SECOND)
        self.assertEqual(row["classification"], NO_QUOTE)
        self.assertEqual(row["no_quote_trades"], 1)
        self.assertIsNone(row["last_quote"], "no touch was usable, so none is stated")

    def test_no_quote_outranks_at_mid_when_nothing_classified(self) -> None:
        """Without a touch there is no mid to be at, so the missing quote is the reason."""
        self.calc.observe_group_rows(
            [legacy_row(price=5.0), legacy_row(bid_px_00=0.0, ask_px_00=0.0)],
            second=SECOND, source_day="20211004",
        )
        self.assertEqual(complete(self.calc, SECOND)["classification"], NO_QUOTE)

    def test_unusable_trade_rows_are_counted_as_their_own_class(self) -> None:
        self.calc.observe_group_rows([legacy_row(size=0)], second=SECOND,
                                     source_day="20211004")
        row = complete(self.calc, SECOND)
        self.assertEqual(row["classification"], UNUSABLE_PRICE_OR_SIZE)
        self.assertEqual(row["unusable_trades"], 1)
        self.assertEqual(row["trades"], 0, "the binner does not count it as a trade either")

    def test_classified_volume_decides_over_every_exclusion_in_the_same_second(self) -> None:
        self.calc.observe_group_rows(
            [legacy_row(price=5.0), legacy_row(bid_px_00=0.0, ask_px_00=0.0),
             legacy_row(price=5.001, size=2)],
            second=SECOND, source_day="20211004",
        )
        row = complete(self.calc, SECOND, buy=2.0)
        self.assertEqual(row["classification"], BUY)
        self.assertEqual((row["at_mid_trades"], row["no_quote_trades"]), (1, 1))

    def test_non_trade_rows_are_counted_on_the_second(self) -> None:
        self.calc.observe_group_rows([legacy_row(action="A"), legacy_row(action="C")],
                                     second=SECOND, source_day="20211004")
        row = complete(self.calc, SECOND)
        self.assertEqual(row["rows"], 2)
        self.assertEqual(row["trades"], 0)
        self.assertEqual(self.calc.summary()["trade_dispositions"]["quote_rows"], 2)

    def test_every_completed_second_receives_exactly_one_class(self) -> None:
        self.calc.observe_group_rows([legacy_row()], second=SECOND, source_day="20211004")
        self.calc.observe_group_rows([legacy_row(price=5.0)], second=SECOND + 1,
                                     source_day="20211004")
        complete(self.calc, SECOND, buy=3.0)
        complete(self.calc, SECOND + 1)
        complete(self.calc, SECOND + 2)
        summary = self.calc.summary()
        self.assertEqual(summary["seconds_completed"], 3)
        self.assertEqual(sum(summary["census"].values()), 3)
        self.assertEqual(set(summary["census"]), set(CLASSIFICATIONS))
        self.assertAlmostEqual(sum(summary["census_shares"].values()), 1.0)


class WindowDirectionTest(unittest.TestCase):
    """The census 4.12 consumed: sign of the trailing-window flow, zero is NO_DIRECTION."""

    def test_the_window_direction_is_the_stage_rule(self) -> None:
        calc = FlowSubstrateCalculator()
        self.assertEqual(complete(calc, SECOND, window_flow=4)["window_direction"],
                         WINDOW_LONG)
        self.assertEqual(complete(calc, SECOND + 1, window_flow=-1)["window_direction"],
                         WINDOW_SHORT)
        self.assertEqual(complete(calc, SECOND + 2, window_flow=0)["window_direction"],
                         WINDOW_NO_DIRECTION)
        summary = calc.summary()
        self.assertEqual(summary["window_census"], {"LONG": 1, "SHORT": 1, "NO_DIRECTION": 1})
        self.assertAlmostEqual(summary["window_census_shares"]["NO_DIRECTION"], 1 / 3)

    def test_an_undefined_roll20_is_stated_as_undefined_not_zero(self) -> None:
        row = complete(FlowSubstrateCalculator(), SECOND)
        self.assertFalse(row["roll20_defined"])
        self.assertIsNone(row["roll20_value"])
        defined = complete(FlowSubstrateCalculator(), SECOND, roll20=0.5, window_flow=2,
                           polarity=1)
        self.assertTrue(defined["roll20_defined"])
        self.assertEqual(defined["roll20_value"], 0.5)


class ReconciliationTest(unittest.TestCase):
    def test_a_disagreement_with_the_traversal_binner_is_refused(self) -> None:
        """The census must be over the substrate the detector consumed, or it is a second one."""
        calc = FlowSubstrateCalculator()
        calc.observe_group_rows([legacy_row()], second=SECOND, source_day="20211004")
        with self.assertRaises(FlowSubstrateError):
            complete(calc, SECOND, buy=4.0)

    def test_rows_for_a_completed_second_are_refused(self) -> None:
        calc = FlowSubstrateCalculator()
        complete(calc, SECOND)
        with self.assertRaises(FlowSubstrateError):
            calc.observe_group_rows([legacy_row()], second=SECOND, source_day="20211004")

    def test_a_second_is_judged_once_forward_only(self) -> None:
        calc = FlowSubstrateCalculator()
        complete(calc, SECOND + 1)
        with self.assertRaises(FlowSubstrateError):
            complete(calc, SECOND + 1)
        with self.assertRaises(FlowSubstrateError):
            complete(calc, SECOND)

    def test_a_second_with_rows_is_filed_under_its_rows_source_day(self) -> None:
        """Across a file seam the completing group's day differs; the rows' own day wins."""
        calc = FlowSubstrateCalculator()
        calc.observe_group_rows([legacy_row()], second=SECOND, source_day="20211003")
        row = complete(calc, SECOND, buy=3.0, source_day="20211004")
        self.assertEqual(row["source_day"], "20211003")
        empty = complete(calc, SECOND + 1, source_day="20211004")
        self.assertEqual(empty["source_day"], "20211004")

    def test_a_boundary_skew_second_is_counted_and_stamped_not_hidden(self) -> None:
        calc = FlowSubstrateCalculator()
        row = calc.complete_second(
            SECOND, roll20_value=float("nan"), window_signed_flow=0, polarity=0,
            buy_volume=0.0, sell_volume=0.0, segment_by_rule=18905, **CTX,
        )
        self.assertEqual(row["continuity_segment"], 18904)
        self.assertEqual(row["segment_by_rule"], 18905)
        self.assertEqual(calc.summary()["boundary_skew_seconds"], 1)

    def test_the_clock_is_a_declaration(self) -> None:
        with self.assertRaises(native_roll20.Roll20Error):
            FlowSubstrateCalculator(clock="wall_clock")
        calc = FlowSubstrateCalculator()
        calc.declare_clock(native_roll20.EVENT_CLOCK)
        self.assertEqual(calc.clock, native_roll20.EVENT_CLOCK)
        calc.observe_group_rows([legacy_row()], second=SECOND, source_day="20211004")
        with self.assertRaises(FlowSubstrateError):
            calc.declare_clock(native_roll20.RECV_CLOCK)


class BoundaryTest(unittest.TestCase):
    def test_a_pending_second_is_incomplete_and_outside_the_denominator(self) -> None:
        calc = FlowSubstrateCalculator()
        calc.observe_group_rows([legacy_row()], second=SECOND, source_day="20211004")
        complete(calc, SECOND, buy=3.0)
        calc.observe_group_rows([legacy_row()], second=SECOND + 4, source_day="20211004")
        released = calc.finalize(recv_ns=(SECOND + 5) * 10**9)
        self.assertEqual(len(released), 1)
        self.assertEqual(released[0]["status"], INCOMPLETE_STREAM_END)
        self.assertIsNone(released[0]["classification"])
        self.assertEqual(released[0]["buy_volume"], 3.0, "partial tallies travel with it")
        summary = calc.summary()
        self.assertEqual(summary["seconds_completed"], 1)
        self.assertEqual(summary["seconds_incomplete"], 1)
        self.assertEqual(summary["incomplete_by_reason"][INCOMPLETE_STREAM_END], 1)
        self.assertEqual(summary["empty_seconds_never_completed"], 3,
                         "seconds 1, 2 and 3 of the unjudged tail carried nothing")
        self.assertEqual(summary["seconds_still_pending"], 0)

    def test_a_segment_close_releases_under_its_own_reason(self) -> None:
        calc = FlowSubstrateCalculator()
        calc.observe_group_rows([legacy_row()], second=SECOND, source_day="20211004")
        released = calc.close_continuity_segment(segment=18904, recv_ns=SECOND * 10**9)
        self.assertEqual(released[0]["status"], INCOMPLETE_SEGMENT_END)
        self.assertEqual(released[0]["continuity_segment"], 18904)
        self.assertEqual(calc.finalize(recv_ns=SECOND * 10**9), [])


class CompanionTest(unittest.TestCase):
    def test_the_census_rows_carry_the_denominator_and_no_exclusions(self) -> None:
        calc = FlowSubstrateCalculator()
        calc.observe_group_rows([legacy_row()], second=SECOND, source_day="20211004")
        complete(calc, SECOND, buy=3.0)
        complete(calc, SECOND + 1)
        rows = {r["measure"]: r for r in calc.companion_rows()}
        buy = rows["second_class_share_BUY"]
        self.assertEqual(buy["value"]["n"], 2)
        self.assertEqual(buy["value"]["sum"], 1.0)
        self.assertAlmostEqual(buy["value"]["arithmetic_mean"], 0.5)
        self.assertEqual(buy["excluded_missing_members"], 0)
        self.assertEqual(rows["second_class_share_NO_DIRECTION"]["value"]["sum"], 1.0)
        self.assertEqual(rows["window_direction_share_NO_DIRECTION"]["value"]["n"], 2)

    def test_the_declaration_cites_the_crosswalk_rule_verbatim(self) -> None:
        calc = FlowSubstrateCalculator()
        complete(calc, SECOND)
        for row in calc.companion_rows():
            declaration = row["declaration"]
            for field in ("numerator_formula", "population", "causal_cutoff", "status",
                          "missingness_rule"):
                self.assertTrue(declaration[field], field)
            if row["measure"].startswith("second_class_share_"):
                self.assertIn(native_roll20.CALCULATION, declaration["numerator_formula"])
            self.assertIn("exactly one class", declaration["missingness_rule"])

    def test_the_stratum_names_its_own_coarseness(self) -> None:
        calc = FlowSubstrateCalculator()
        complete(calc, SECOND)
        stratum = calc.companion_rows()[0]["stratum"]
        self.assertEqual(stratum["family_id"], SUBSTRATE_FAMILY)
        self.assertEqual(stratum["session_phase"], "PRE_SETTLEMENT")
        self.assertEqual(stratum["continuity_segment"], 18904)

    def test_phases_and_days_do_not_pool(self) -> None:
        calc = FlowSubstrateCalculator()
        complete(calc, SECOND, session_phase="PRE_SETTLEMENT")
        complete(calc, SECOND + 1, session_phase="SETTLEMENT")
        complete(calc, SECOND + 2, source_day="20211005", session_phase="SETTLEMENT")
        rows = [r for r in calc.companion_rows() if r["measure"] == "second_class_share_BUY"]
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["value"]["n"] == 1 for r in rows))
        self.assertEqual(calc.summary()["stratum_counts"]["second_class_share_BUY"], 3)


if __name__ == "__main__":
    unittest.main()
