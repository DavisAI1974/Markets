"""Tests for the real-time replay book (Greg: "We should see it like it would be seen in rt").

Databento's `InstrumentBook` mutates on EVERY record, but the group frame carrying
`raw_actions` is only emitted at F_LAST. So by the time a closed group reaches an adapter,
the book already reflects that group's OWN later actions, and reading a level there reports
it as it stood AFTER the add that level is meant to describe. That is an intra-group
lookahead which is present, typed and wrong - the S108 off-instrument / S109
`session_b_share` / 2026-08-29 `_family_id` shape, where nothing fails and the values are
simply not the quantity they claim to be. `ReplayBook` exists to make every read the view a
live feed would have had at that action's own instant.

These tests pin CONSTRUCTION choices, not just that the code runs. The governing rule is
that `ReplayBook` must agree with `InstrumentBook`
(`research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`) about every book mutation: if the
two books disagree about one fact, nothing raises, the numbers just differ, and that is the
defect this module is guarding against rather than a new one to introduce. Each mutation test
below therefore names the `InstrumentBook` method it is copied from. The ONE deliberate
divergence is malformed input (see `ErrorTests.test_negative_size_raises_rather_than_clamping`).
"""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark import native_group_adapters as ga
from research.kalshi.frankie_raw_mbo_benchmark import native_rt_book as rt


def row(action, side, order_id, price, size, recv):
    return {
        "action": action,
        "side": side,
        "order_id": order_id,
        "price_raw": price,
        "size": size,
        "ts_recv_ns": recv,
        "ts_event_ns": recv - 10,
    }


def feed(book, rows):
    for r in rows:
        book.apply(r)
    return book


# One group's worth of raw actions, mixing both sides and every mutating action. Used by the
# no-lookahead property below; every row here is legal, so nothing in it should raise.
STREAM = [
    row("A", "B", 1, 3000, 5, 100),
    row("A", "A", 2, 3010, 4, 110),
    row("A", "B", 3, 3000, 7, 120),
    row("T", "A", 0, 3010, 2, 130),   # non-mutating in this feed
    row("F", "A", 2, 3010, 2, 140),   # non-mutating in this feed
    row("A", "B", 4, 3001, 6, 150),
    row("C", "B", 1, 3000, 5, 160),   # full cancel: order 3 moves up
    row("M", "B", 3, 3000, 9, 170),   # size increase: priority lost, back of the level
    row("A", "B", 5, 3000, 2, 180),
    row("C", "A", 2, 3010, 4, 190),   # the ask side empties
]


def reading(book):
    """Everything ReplayBook can be asked, as one comparable tuple."""
    return (
        book.level("B", 3000),
        book.level("B", 3001),
        book.level("A", 3010),
        book.touch_price("B"),
        book.touch_price("A"),
        book.view("B", 3000, 3),
        book.view("B", 3000, 5),
        book.is_resting(1),
        book.resting_at(3),
    )


class RealTimeViewTests(unittest.TestCase):
    """THE REASON THIS MODULE EXISTS. If only one test in this file survives, it is these two."""

    def test_a_later_add_at_the_same_level_is_invisible_to_the_earlier_adds_view(self) -> None:
        # THE HEADLINE. Order 1 rests alone; order 2 joins the same level afterwards. Read at
        # order 1's own instant, order 1 has nothing ahead of it and the level holds one order.
        # An adapter reading the CLOSED group's book instead sees (2, 12) at that same level -
        # the group's own later add, reported as if it had been there all along. That is the
        # intra-group lookahead, and the numbers below are the two answers side by side.
        book = rt.ReplayBook()
        book.apply(row("A", "B", 1, 3000, 5, 100))
        at_the_instant_of_add_one = (book.view("B", 3000, 1), book.level("B", 3000))
        book.apply(row("A", "B", 2, 3000, 7, 110))
        after_the_group_closed = (book.view("B", 3000, 1), book.level("B", 3000))

        self.assertEqual(at_the_instant_of_add_one, ((0, 0), (1, 5)))
        self.assertEqual(book.view("B", 3000, 2), (1, 5), "order 2 queues behind order 1")
        self.assertEqual(after_the_group_closed, ((0, 0), (2, 12)))
        self.assertNotEqual(
            at_the_instant_of_add_one,
            after_the_group_closed,
            "if these ever match, the fixture stopped exercising the lookahead",
        )

    def test_no_reading_depends_on_a_row_later_in_the_sequence(self) -> None:
        # The RT claim as an executable property: the state after k rows must be a function of
        # rows[:k] and nothing else. Replaying each prefix into a FRESH book must reproduce,
        # exactly, what the single streaming book showed at that same instant.
        streaming = []
        live = rt.ReplayBook()
        for r in STREAM:
            live.apply(r)
            streaming.append(reading(live))

        for k in range(1, len(STREAM) + 1):
            with self.subTest(rows_applied=k):
                self.assertEqual(
                    reading(feed(rt.ReplayBook(), STREAM[:k])),
                    streaming[k - 1],
                    "the reading after this row is not a function of the rows up to it",
                )

        # Non-vacuity: the book genuinely moves across the stream, so the property above is
        # not satisfied by a book that never changes.
        self.assertEqual(streaming[0][0], (1, 5), "level B3000 after the first add")
        self.assertEqual(streaming[-1][0], (2, 11), "level B3000 once the group has closed")


class FifoOrderTests(unittest.TestCase):
    def test_fifo_is_insertion_order_not_price_or_size_order(self) -> None:
        # `InstrumentBook._add_order` appends the order id to `levels[side][price]`, so the
        # queue is arrival order. Sorting by id or size here would silently re-rank every
        # queue position downstream without failing anything.
        book = feed(rt.ReplayBook(), [
            row("A", "B", 30, 3000, 9, 100),
            row("A", "B", 10, 3000, 1, 110),
            row("A", "B", 20, 3000, 4, 120),
        ])
        self.assertEqual(book.view("B", 3000, 30), (0, 0))
        self.assertEqual(book.view("B", 3000, 10), (1, 9))
        self.assertEqual(book.view("B", 3000, 20), (2, 10))
        self.assertEqual(book.level("B", 3000), (3, 14))

    def test_an_order_absent_from_the_level_reports_the_whole_level_as_ahead(self) -> None:
        # Matches `test_native_queue.FakeBook.view`, which walks the queue and never breaks
        # when the id is missing. Pinned deliberately: the conservative answer for an order we
        # cannot locate is that ALL of the level is ahead of it, never that none of it is.
        book = feed(rt.ReplayBook(), [
            row("A", "B", 1, 3000, 5, 100),
            row("A", "B", 2, 3000, 7, 110),
        ])
        self.assertEqual(book.view("B", 3000, 999), (2, 12))
        self.assertEqual(book.view("B", 2999, 1), (0, 0), "an empty level has nothing ahead")
        self.assertEqual(book.view("A", 3000, 1), (0, 0), "the other side is a different level")


class CancelTests(unittest.TestCase):
    def test_cancel_removes_from_the_level_and_the_order_behind_moves_up(self) -> None:
        # `InstrumentBook._cancel`: new_size 0 -> `_remove_from_level` + `orders.pop`.
        book = feed(rt.ReplayBook(), [
            row("A", "B", 1, 3000, 5, 100),
            row("A", "B", 2, 3000, 7, 110),
            row("C", "B", 1, 3000, 5, 120),
        ])
        self.assertFalse(book.is_resting(1))
        self.assertIsNone(book.resting_at(1))
        self.assertEqual(book.level("B", 3000), (1, 7))
        self.assertEqual(book.view("B", 3000, 2), (0, 0), "order 2 moved to the front")

    def test_a_partial_cancel_decrements_size_and_keeps_fifo_position(self) -> None:
        # `_cancel` decrements by the ROW's size and only removes at zero; it never calls
        # `_remove_from_level` on the survivor, so the order does not re-queue.
        book = feed(rt.ReplayBook(), [
            row("A", "B", 1, 3000, 5, 100),
            row("A", "B", 2, 3000, 7, 110),
            row("C", "B", 1, 3000, 2, 120),
        ])
        self.assertTrue(book.is_resting(1))
        self.assertEqual(book.resting_at(1), ("B", 3000, 3))
        self.assertEqual(book.level("B", 3000), (2, 10))
        self.assertEqual(book.view("B", 3000, 2), (1, 3), "order 1 is still ahead, now smaller")


class FillAndTradeTests(unittest.TestCase):
    def test_fill_and_trade_leave_the_book_completely_unchanged(self) -> None:
        # `InstrumentBook._book_effect`: `if msg.action in ("T", "F", "N")` returns an effect
        # with NO mutation. In this feed a fill is not a book event - the venue's subsequent
        # `C` or `M` is what removes the liquidity. If ReplayBook applied fills and
        # InstrumentBook did not, the two books would disagree about one quantity and nothing
        # would fail: that is the `_family_id` defect of 2026-08-29 exactly, which is the
        # thing this module exists to prevent, not to reintroduce.
        book = feed(rt.ReplayBook(), [
            row("A", "B", 1, 3000, 5, 100),
            row("A", "B", 2, 3000, 7, 110),
        ])
        before = (book.level("B", 3000), book.view("B", 3000, 2), book.resting_at(1))

        book.apply(row("F", "B", 1, 3000, 5, 120))
        book.apply(row("T", "B", 1, 3000, 5, 130))
        book.apply(row("N", "N", 0, 3000, 5, 140))

        self.assertEqual((book.level("B", 3000), book.view("B", 3000, 2), book.resting_at(1)), before)
        self.assertTrue(book.is_resting(1), "a fill does not remove the resting order in this feed")
        self.assertEqual(book.resting_at(1), ("B", 3000, 5), "and it does not reduce its size")


class ModifyTests(unittest.TestCase):
    """`InstrumentBook._modify`: priority_lost = old_price != msg.price_raw or msg.size > old_size."""

    def test_a_price_change_loses_priority_and_goes_to_the_back_of_the_new_level(self) -> None:
        book = feed(rt.ReplayBook(), [
            row("A", "B", 1, 3000, 5, 100),
            row("A", "B", 2, 2999, 7, 110),
            row("M", "B", 1, 2999, 5, 120),
        ])
        self.assertEqual(book.level("B", 3000), (0, 0), "the old level was vacated")
        self.assertEqual(book.level("B", 2999), (2, 12))
        self.assertEqual(book.resting_at(1), ("B", 2999, 5))
        self.assertEqual(book.view("B", 2999, 1), (1, 7), "order 1 is now behind order 2")

    def test_a_size_increase_loses_priority_at_the_same_level(self) -> None:
        book = feed(rt.ReplayBook(), [
            row("A", "B", 1, 3000, 5, 100),
            row("A", "B", 2, 3000, 7, 110),
            row("M", "B", 1, 3000, 9, 120),
        ])
        self.assertEqual(book.view("B", 3000, 2), (0, 0), "order 2 is now first")
        self.assertEqual(book.view("B", 3000, 1), (1, 7))
        self.assertEqual(book.level("B", 3000), (2, 16))

    def test_a_size_decrease_retains_fifo_position(self) -> None:
        book = feed(rt.ReplayBook(), [
            row("A", "B", 1, 3000, 5, 100),
            row("A", "B", 2, 3000, 7, 110),
            row("M", "B", 1, 3000, 3, 120),
        ])
        self.assertEqual(book.view("B", 3000, 1), (0, 0), "order 1 kept the front")
        self.assertEqual(book.view("B", 3000, 2), (1, 3))
        self.assertEqual(book.resting_at(1), ("B", 3000, 3))

    def test_a_modify_to_zero_size_removes_the_order(self) -> None:
        # `_modify`: `if old.size == 0` -> removed from the level and from `orders`.
        book = feed(rt.ReplayBook(), [
            row("A", "B", 1, 3000, 5, 100),
            row("A", "B", 2, 3000, 7, 110),
            row("M", "B", 1, 3000, 0, 120),
        ])
        self.assertFalse(book.is_resting(1))
        self.assertEqual(book.level("B", 3000), (1, 7))

    def test_a_modify_for_an_unknown_order_is_treated_as_an_add(self) -> None:
        # PINNED to the authority, not to intuition: `_modify` with `old is None` counts
        # `modify_missing_treated_as_add` and calls `_add_order`. Databento's reference LOB
        # does the same. A replay window that opens mid-stream will see these constantly, so
        # refusing would make ReplayBook unusable on any window that is not the session's
        # first record; the implementer who disagrees should argue with `_modify`, not here.
        book = feed(rt.ReplayBook(), [
            row("A", "B", 1, 3000, 5, 100),
            row("M", "B", 77, 3000, 4, 110),
        ])
        self.assertTrue(book.is_resting(77))
        self.assertEqual(book.resting_at(77), ("B", 3000, 4))
        self.assertEqual(book.view("B", 3000, 77), (1, 5), "it joins at the back, like an add")

    def test_a_side_change_removes_and_re_adds_on_the_new_side(self) -> None:
        # `_modify` when `old_side != msg.side`: remove, pop, `_add_order` on the new side.
        book = feed(rt.ReplayBook(), [
            row("A", "B", 1, 3000, 5, 100),
            row("M", "A", 1, 3010, 5, 110),
        ])
        self.assertEqual(book.level("B", 3000), (0, 0))
        self.assertEqual(book.level("A", 3010), (1, 5))
        self.assertEqual(book.resting_at(1), ("A", 3010, 5))


class ResetTests(unittest.TestCase):
    def test_reset_clears_both_sides(self) -> None:
        # `_book_effect` on "R": `orders.clear()` and both level maps rebuilt empty.
        book = feed(rt.ReplayBook(), [
            row("A", "B", 1, 3000, 5, 100),
            row("A", "A", 2, 3010, 4, 110),
            row("R", "N", 0, 0, 0, 120),
        ])
        self.assertEqual(book.level("B", 3000), (0, 0))
        self.assertEqual(book.level("A", 3010), (0, 0))
        self.assertFalse(book.is_resting(1))
        self.assertFalse(book.is_resting(2))
        self.assertIsNone(book.touch_price("B"))
        self.assertIsNone(book.touch_price("A"))


class TouchPriceTests(unittest.TestCase):
    def test_touch_price_is_max_on_the_bid_min_on_the_ask_and_none_when_empty(self) -> None:
        # `InstrumentBook.best_price_raw`: max on "B", min on "A", None on an empty side.
        # Taking the same extreme on both sides would read as a plausible price and be the
        # far touch on one of them.
        book = rt.ReplayBook()
        self.assertIsNone(book.touch_price("B"))
        self.assertIsNone(book.touch_price("A"))
        feed(book, [
            row("A", "B", 1, 3000, 5, 100),
            row("A", "B", 2, 2999, 5, 110),
            row("A", "A", 3, 3010, 5, 120),
            row("A", "A", 4, 3011, 5, 130),
        ])
        self.assertEqual(book.touch_price("B"), 3000)
        self.assertEqual(book.touch_price("A"), 3010)
        book.apply(row("C", "B", 1, 3000, 5, 140))
        self.assertEqual(book.touch_price("B"), 2999, "the touch falls back to the next level")


class AdmissionGuardTests(unittest.TestCase):
    def test_a_sentinel_priced_row_never_enters_the_book(self) -> None:
        book = feed(rt.ReplayBook(), [row("A", "B", 1, rt.PRICE_SENTINEL_ABS, 5, 100)])
        self.assertFalse(book.is_resting(1))
        self.assertIsNone(book.resting_at(1))
        self.assertIsNone(book.touch_price("B"), "an undefined price is not a touch")
        self.assertEqual(book.level("B", rt.PRICE_SENTINEL_ABS), (0, 0))

    def test_an_unsided_row_never_enters_the_book(self) -> None:
        # The `ladder_transitions` precedent: Databento's "N" is the tape DECLINING to state a
        # side, so assigning it to one would fabricate the very fact that is missing.
        book = feed(rt.ReplayBook(), [row("A", "N", 9, 3000, 50, 100)])
        self.assertFalse(book.is_resting(9))
        self.assertEqual(book.level("B", 3000), (0, 0))
        self.assertEqual(book.level("A", 3000), (0, 0))

    def test_the_sentinel_is_one_constant_shared_with_the_group_adapters(self) -> None:
        # Two constants over one fact is the `_family_id` defect: they do not fail, they drift.
        self.assertEqual(rt.PRICE_SENTINEL_ABS, ga.PRICE_SENTINEL_ABS)
        self.assertEqual(rt.PRICE_SENTINEL_ABS, 9_000_000_000_000_000_000)


class ErrorTests(unittest.TestCase):
    def test_rt_book_error_is_a_value_error(self) -> None:
        self.assertTrue(issubclass(rt.RtBookError, ValueError))

    def test_negative_size_raises_rather_than_clamping(self) -> None:
        # THE ONE DELIBERATE DIVERGENCE FROM InstrumentBook, pinned so it is a choice and not
        # a drift: `_add_order` and `_cancel` both use `max(0, msg.size)`, which turns a
        # malformed row into a silent zero - present, typed, in range and wrong. ReplayBook
        # follows the `_size` precedent in native_group_adapters instead and refuses. It
        # mirrors InstrumentBook on every book MUTATION and is stricter only on malformed
        # INPUT, so the two books can never disagree about a row either of them accepted.
        for action in ("A", "C", "M"):
            with self.subTest(action=action):
                book = feed(rt.ReplayBook(), [row("A", "B", 1, 3000, 5, 100)])
                with self.assertRaises(rt.RtBookError):
                    book.apply(row(action, "B", 1, 3000, -1, 110))

    def test_a_duplicate_add_of_a_resting_order_id_is_refused(self) -> None:
        # PINNED, and the implementer may argue with it. InstrumentBook._add_order tolerates
        # this: it counts `duplicate_add_order_id`, drops the old order from its level and
        # rests the new one. It can afford to, because its job is to survive a whole day's
        # tape. ReplayBook's job is to answer `view(side, price, order_id)` for ONE named
        # order, and after a silent replacement that answer is the queue position of a
        # different order under the same id - present, typed and wrong. The conservative
        # option is to refuse and let the caller count it, so that is what is pinned.
        book = feed(rt.ReplayBook(), [row("A", "B", 1, 3000, 5, 100)])
        with self.assertRaises(rt.RtBookError):
            book.apply(row("A", "B", 1, 3001, 7, 110))

    def test_an_unrecognized_action_is_refused(self) -> None:
        # `InstrumentBook.apply` raises on an action outside VALID_ACTIONS ("ACMRTFN").
        # Skipping it would silently drop a record the feed's own vocabulary does not cover.
        book = rt.ReplayBook()
        with self.assertRaises(rt.RtBookError):
            book.apply(row("X", "B", 1, 3000, 5, 100))

    def test_a_cancel_for_an_unknown_order_is_a_no_op_not_an_error(self) -> None:
        # PINNED to the authority: `_cancel` with `old is None` counts `cancel_missing_order`
        # and mutates nothing. A group is a SLICE of the day, so a cancel of an order that
        # rested before the replay window opened is structural, not malformed - raising would
        # make ReplayBook unusable anywhere but the session's first record.
        book = feed(rt.ReplayBook(), [row("A", "B", 1, 3000, 5, 100)])
        book.apply(row("C", "B", 999, 3000, 5, 110))
        self.assertEqual(book.level("B", 3000), (1, 5), "the level is untouched")
        self.assertFalse(book.is_resting(999), "and no order was invented for it")


class IndependenceTests(unittest.TestCase):
    def test_two_replay_books_share_no_state(self) -> None:
        # A mutable default on the class would pool two instruments into one book, which reads
        # as depth rather than as an error.
        first = feed(rt.ReplayBook(), [row("A", "B", 1, 3000, 5, 100)])
        second = rt.ReplayBook()
        self.assertEqual(second.level("B", 3000), (0, 0))
        self.assertFalse(second.is_resting(1))
        self.assertIsNone(second.touch_price("B"))
        second.apply(row("A", "B", 2, 3000, 7, 110))
        self.assertEqual(first.level("B", 3000), (1, 5))
        self.assertFalse(first.is_resting(2))


if __name__ == "__main__":
    unittest.main()
