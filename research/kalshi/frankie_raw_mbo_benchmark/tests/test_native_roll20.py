"""Section 8 of the feed inventory: recreate the legacy per-second roll20 from native.

These tests are DIFFERENTIAL against the frozen implementation wherever one exists. The
risk this module carries is not that it fails - it is that it produces a series that is
present, typed, in range and NOT the quantity the 3,429 frozen events were detected from.
Only exact agreement with the frozen functions rules that out, so the reconciliation is the
deliverable and the series is a by-product of it.

Nothing here reads a Step-1 output. The mission forbids Step-1-derived input and the feed
inventory seals the October Step-1 seconds as the answer; the lawful source is the legacy
control row the V4 adapter PROJECTS from the native MBO stream, which the driver already
retains verbatim under D60.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark import native_roll20

_RESEARCH = Path(__file__).resolve().parents[3]
if str(_RESEARCH) not in sys.path:
    sys.path.insert(0, str(_RESEARCH))
import ng_dipole_native_shape_audit as frozen  # noqa: E402


def legacy_row(**over):
    """A legacy control row in the shape `_legacy_control_row` emits."""
    row = {
        "census_view": "LEGACY_CONTROL",
        "action": "T",
        "side": "B",
        "price": 5.000,
        "size": 3,
        "ts_recv": 1_633_046_400.25,
        "ts_event": 1_633_046_400.10,
        "instrument_id": 42,
    }
    for i in range(10):
        row[f"bid_px_{i:02d}"] = 0.0
        row[f"ask_px_{i:02d}"] = 0.0
        row[f"bid_sz_{i:02d}"] = 0
        row[f"ask_sz_{i:02d}"] = 0
    row["bid_px_00"] = 4.998
    row["ask_px_00"] = 5.002
    row.update(over)
    return row


class MidpointClassificationTest(unittest.TestCase):
    """The frozen rule, character for character: side comes from price vs the mid."""

    def test_a_trade_above_the_mid_is_buy_volume(self) -> None:
        binner = native_roll20.SecondBinner(clock=native_roll20.RECV_CLOCK)
        binner.observe(legacy_row(price=5.001, size=7))
        self.assertEqual(binner.buy_volume_at(1_633_046_400), 7.0)
        self.assertEqual(binner.sell_volume_at(1_633_046_400), 0.0)

    def test_a_trade_below_the_mid_is_sell_volume(self) -> None:
        binner = native_roll20.SecondBinner(clock=native_roll20.RECV_CLOCK)
        binner.observe(legacy_row(price=4.999, size=4))
        self.assertEqual(binner.sell_volume_at(1_633_046_400), 4.0)
        self.assertEqual(binner.buy_volume_at(1_633_046_400), 0.0)

    def test_a_trade_exactly_at_the_mid_counts_on_NEITHER_side(self) -> None:
        """No tick-rule fallback exists in the frozen recipe. It enters neither column."""
        binner = native_roll20.SecondBinner(clock=native_roll20.RECV_CLOCK)
        binner.observe(legacy_row(price=5.000, size=9))
        self.assertEqual(binner.buy_volume_at(1_633_046_400), 0.0)
        self.assertEqual(binner.sell_volume_at(1_633_046_400), 0.0)
        self.assertEqual(binner.excluded_at_mid, 1)

    def test_the_tape_side_field_is_never_consulted(self) -> None:
        """side='B' on a below-mid trade must still classify as sell."""
        binner = native_roll20.SecondBinner(clock=native_roll20.RECV_CLOCK)
        binner.observe(legacy_row(price=4.999, size=2, side="B"))
        self.assertEqual(binner.sell_volume_at(1_633_046_400), 2.0)

    def test_a_trade_with_no_two_sided_book_is_excluded_and_counted(self) -> None:
        binner = native_roll20.SecondBinner(clock=native_roll20.RECV_CLOCK)
        binner.observe(legacy_row(bid_px_00=0.0))
        self.assertEqual(binner.buy_volume_at(1_633_046_400), 0.0)
        self.assertEqual(binner.excluded_no_quote, 1)

    def test_a_crossed_book_is_excluded(self) -> None:
        """The frozen gate is `bid > 0 and ask >= bid`."""
        binner = native_roll20.SecondBinner(clock=native_roll20.RECV_CLOCK)
        binner.observe(legacy_row(bid_px_00=5.010, ask_px_00=5.002))
        self.assertEqual(binner.excluded_no_quote, 1)

    def test_only_trade_rows_contribute(self) -> None:
        binner = native_roll20.SecondBinner(clock=native_roll20.RECV_CLOCK)
        for action in ("A", "C", "M", "F", "N", "R"):
            binner.observe(legacy_row(action=action, price=5.001))
        self.assertEqual(binner.buy_volume_at(1_633_046_400), 0.0)
        self.assertEqual(binner.trades_seen, 0)

    def test_a_nonpositive_size_or_price_does_not_contribute(self) -> None:
        binner = native_roll20.SecondBinner(clock=native_roll20.RECV_CLOCK)
        binner.observe(legacy_row(size=0, price=5.001))
        binner.observe(legacy_row(size=3, price=0.0))
        self.assertEqual(binner.buy_volume_at(1_633_046_400), 0.0)


class ClockIsDeclaredTest(unittest.TestCase):
    """The frozen census binned on EVENT time; the A-arm's causal clock is ts_recv_ns."""

    def test_the_clock_must_be_named_and_cannot_default(self) -> None:
        with self.assertRaises(TypeError):
            native_roll20.SecondBinner()

    def test_an_unknown_clock_is_refused(self) -> None:
        with self.assertRaises(native_roll20.Roll20Error):
            native_roll20.SecondBinner(clock="whenever")

    def test_the_two_clocks_bin_the_same_row_differently_and_both_are_available(self) -> None:
        row = legacy_row(price=5.001, size=1, ts_recv=1_633_046_401.9, ts_event=1_633_046_400.1)
        recv = native_roll20.SecondBinner(clock=native_roll20.RECV_CLOCK)
        event = native_roll20.SecondBinner(clock=native_roll20.EVENT_CLOCK)
        recv.observe(row)
        event.observe(row)
        self.assertEqual(recv.buy_volume_at(1_633_046_401), 1.0)
        self.assertEqual(event.buy_volume_at(1_633_046_400), 1.0)


class FrozenDifferentialTest(unittest.TestCase):
    """The reconciliation. Exact agreement with the frozen roll20, or this is a new series."""

    @staticmethod
    def _day(buys, sells):
        class Day:
            buy_vol = buys
            sell_vol = sells
        return Day()

    def test_roll20_reproduces_the_frozen_flow_series_exactly(self) -> None:
        import random

        random.seed(11)
        n = 400
        buys = [float(random.randint(0, 9)) for _ in range(n)]
        sells = [float(random.randint(0, 9)) for _ in range(n)]
        expected = frozen.flow_series(self._day(buys, sells), 20)
        actual = native_roll20.roll20(buys, sells, window=20)
        self.assertEqual(len(actual), len(expected))
        for i, (a, e) in enumerate(zip(actual, expected)):
            with self.subTest(second=i):
                if math.isnan(e):
                    self.assertTrue(math.isnan(a))
                else:
                    self.assertEqual(a, e)

    def test_an_all_zero_window_is_nan_not_zero(self) -> None:
        """A second with no trades is UNDEFINED, not balanced. Conflating them is a lie."""
        out = native_roll20.roll20([0.0] * 30, [0.0] * 30, window=20)
        self.assertTrue(all(math.isnan(v) for v in out))

    def test_the_window_is_trailing_and_causal(self) -> None:
        """Value at t may not depend on anything after t."""
        buys = [0.0] * 10 + [5.0] + [0.0] * 10
        sells = [0.0] * 21
        out = native_roll20.roll20(buys, sells, window=20)
        self.assertTrue(math.isnan(out[9]), "the second before the trade cannot see it")
        self.assertEqual(out[10], 1.0)


class CrosswalkTest(unittest.TestCase):
    """Inventory section 8: every legacy field needs an explicit crosswalk."""

    def test_the_crosswalk_names_its_native_source_fields(self) -> None:
        cw = native_roll20.crosswalk(clock=native_roll20.RECV_CLOCK)
        self.assertEqual(
            cw["legacy_per_second_roll20"]["v4_native_source_fields"],
            ["action", "price", "size", "bid_px_00", "ask_px_00", "ts_recv"],
        )

    def test_the_crosswalk_states_the_calculation_and_the_availability_time(self) -> None:
        cw = native_roll20.crosswalk(clock=native_roll20.RECV_CLOCK)
        entry = cw["legacy_per_second_roll20"]
        self.assertIn("mid", entry["calculation"])
        self.assertEqual(entry["availability_time"], "ts_recv")

    def test_the_crosswalk_carries_a_state_hash_that_tracks_the_definition(self) -> None:
        a = native_roll20.crosswalk(clock=native_roll20.RECV_CLOCK)["state_hash"]
        b = native_roll20.crosswalk(clock=native_roll20.EVENT_CLOCK)["state_hash"]
        self.assertEqual(len(a), 64)
        self.assertNotEqual(a, b, "a different clock is a different quantity")

    def test_the_crosswalk_contains_no_october_target_identity(self) -> None:
        """Inventory section 8: 'must not contain October target identities'."""
        import json

        text = json.dumps(native_roll20.crosswalk(clock=native_roll20.RECV_CLOCK))
        for forbidden in ("20211001", "20211003", "20211004", "20211005", "Step-1", "step1"):
            self.assertNotIn(forbidden, text)


class SealedSourceTest(unittest.TestCase):
    def test_the_module_reads_no_file_at_all(self) -> None:
        """Structural guard: it cannot reach the sealed Step-1 seconds if it opens nothing."""
        source = Path(native_roll20.__file__).read_text()
        for forbidden in ("open(", "Path(", "json.load", "gzip", "SECONDS", "step1", "Step-1"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()


_CENSUS = None


def _census():
    global _CENSUS
    if _CENSUS is None:
        import ng_exhaustion_mbo_5y_step1_census_20260822 as c
        _CENSUS = c
    return _CENSUS


def _envelope(second: int, rows):
    """The envelope shape `SecondAggregator.consume` reads."""
    return {
        "compact_event_frame": {
            "ts_event_ns": second * 1_000_000_000,
            "ts_recv_ns": second * 1_000_000_000,
            "raw_symbol": "NGX1",
            "instrument_id": 42,
            "raw_actions": [],
            "book": {},
            "integrity": {},
            "activity": {},
        }
    }


def _drive_frozen(groups):
    collected = []
    agg = _census().SecondAggregator(emit=collected.append)
    for second, rows in groups:
        agg.consume(_envelope(second, rows), list(rows))
    agg.finish()
    return {r["epoch_second"]: r for r in collected}


def _mismatches(groups, binner_cls=None):
    """Every per-second disagreement between the frozen census and this module.

    Returns a list rather than asserting, so the same helper can prove agreement in one
    test and prove the harness CAN disagree in another. A comparator that cannot fail
    proves nothing.
    """
    binner_cls = binner_cls or native_roll20.SecondBinner
    ours = binner_cls(clock=native_roll20.EVENT_CLOCK)
    for second, rows in groups:
        ours.observe_group(rows, second=second)
    out = []
    frozen_rows = _drive_frozen(groups)
    if not frozen_rows:
        raise AssertionError("the frozen aggregator emitted nothing to compare against")
    for second, row in sorted(frozen_rows.items()):
        pairs = (
            ("buy", ours.buy_volume_at(second), row["legacy_buy_qty"]),
            ("sell", ours.sell_volume_at(second), row["legacy_sell_qty"]),
        )
        for side, mine, theirs in pairs:
            if mine != theirs:
                out.append((second, side, mine, theirs))
    return out


class FrozenClassifierDifferentialTest(unittest.TestCase):
    """THE reconciliation: the midpoint rule, driven through the frozen census itself.

    The roll20 arithmetic differential above is partly circular - it mirrors the frozen
    formulation on purpose. This one is not: it drives the frozen `SecondAggregator` and
    this module's binner with identical legacy rows and requires the per-second aggressor
    volumes to agree exactly. This is the half that decides whether the series is the
    frozen quantity or a new one wearing its name.
    """

    def test_agrees_on_a_plain_mix_of_buys_and_sells(self) -> None:
        self.assertEqual(_mismatches([(1_000, [
            legacy_row(price=5.001, size=3),
            legacy_row(price=4.999, size=5),
            legacy_row(price=5.001, size=2),
        ])]), [])

    def test_agrees_that_a_mid_priced_trade_enters_neither_column(self) -> None:
        self.assertEqual(_mismatches([(1_000, [legacy_row(price=5.000, size=8)])]), [])

    def test_agrees_when_the_book_is_one_sided(self) -> None:
        self.assertEqual(
            _mismatches([(1_000, [legacy_row(price=5.001, size=4, bid_px_00=0.0)])]), [])

    def test_agrees_when_the_book_is_crossed(self) -> None:
        self.assertEqual(
            _mismatches([(1_000, [legacy_row(price=5.001, size=4, bid_px_00=5.010)])]), [])

    def test_agrees_that_non_trade_rows_contribute_nothing(self) -> None:
        self.assertEqual(_mismatches([(1_000, [
            legacy_row(action="A", price=5.001, size=9),
            legacy_row(action="C", price=4.999, size=9),
            legacy_row(price=5.001, size=1),
        ])]), [])

    def test_agrees_across_a_randomised_multi_second_stream(self) -> None:
        import random

        random.seed(29)
        groups = []
        for i in range(60):
            rows = []
            for _ in range(random.randint(0, 4)):
                rows.append(legacy_row(
                    action=random.choice(["T", "T", "T", "A", "C", "M"]),
                    price=round(random.uniform(4.995, 5.005), 3),
                    size=random.randint(0, 6),
                    bid_px_00=round(random.choice([0.0, 4.998, 4.999, 5.001]), 3),
                    ask_px_00=5.002,
                ))
            groups.append((1_000 + i, rows))
        self.assertEqual(_mismatches(groups), [])


class TapeSideBinner(native_roll20.SecondBinner):
    """The wrong rule: trust the tape's `side` field instead of the midpoint."""

    def _bin(self, row, second):
        if row.get("action") != native_roll20.TRADE_ACTION:
            return
        size = float(row.get("size") or 0)
        if size <= 0:
            return
        second = self._second(row) if second is None else second
        if row.get("side") == "B":
            self.buy[second] = self.buy.get(second, 0.0) + size
        elif row.get("side") == "A":
            self.sell[second] = self.sell.get(second, 0.0) + size


class MidInclusiveBinner(native_roll20.SecondBinner):
    """The wrong rule: give a mid-priced trade to the buy side instead of neither."""

    def _bin(self, row, second):
        if row.get("action") != native_roll20.TRADE_ACTION:
            return
        price = float(row.get("price") or 0)
        size = float(row.get("size") or 0)
        bid = float(row.get(native_roll20.BID_TOUCH_FIELD) or 0)
        ask = float(row.get(native_roll20.ASK_TOUCH_FIELD) or 0)
        if price <= 0 or size <= 0 or bid <= 0 or ask < bid:
            return
        second = self._second(row) if second is None else second
        if price >= 0.5 * (bid + ask):
            self.buy[second] = self.buy.get(second, 0.0) + size
        else:
            self.sell[second] = self.sell.get(second, 0.0) + size


class PerRowSecondBinner(native_roll20.SecondBinner):
    """The wrong rule: bin each row at its own second instead of the group's."""

    def observe_group(self, rows, *, second):
        for row in rows:
            self._bin(row, None)


class DifferentialHarnessCatchesDivergenceTest(unittest.TestCase):
    """A differential that cannot fail proves nothing. This proves it can.

    `native_rt_book`'s differential suite mutation-tests its own comparator for the same
    reason. Each case injects the specific wrong rule this module exists to avoid, and
    requires the reconciliation to report a disagreement.
    """

    def test_the_harness_rejects_the_tape_side_field_rule(self) -> None:
        groups = [(1_000, [legacy_row(price=4.999, size=5, side="B")])]
        self.assertEqual(_mismatches(groups), [], "sanity: the real rule agrees")
        self.assertEqual(
            _mismatches(groups, TapeSideBinner), [(1_000, "buy", 5.0, 0.0),
                                                  (1_000, "sell", 0.0, 5.0)])

    def test_the_harness_rejects_giving_a_mid_priced_trade_to_a_side(self) -> None:
        groups = [(1_000, [legacy_row(price=5.000, size=6)])]
        self.assertEqual(_mismatches(groups), [], "sanity: the real rule agrees")
        self.assertEqual(_mismatches(groups, MidInclusiveBinner), [(1_000, "buy", 6.0, 0.0)])

    def test_the_harness_rejects_per_row_binning_across_a_second_boundary(self) -> None:
        """The exact defect the group entry point exists to prevent."""
        groups = [(1_000, [legacy_row(price=5.001, size=3, ts_event=1_001.4)])]
        self.assertEqual(_mismatches(groups), [], "sanity: the real rule agrees")
        self.assertEqual(
            _mismatches(groups, PerRowSecondBinner), [(1_000, "buy", 0.0, 3.0)])


if __name__ == "__main__":
    unittest.main()
