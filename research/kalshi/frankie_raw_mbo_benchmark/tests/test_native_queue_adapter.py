"""Tests for the section-4.6 queue adapter (D53: the F_LAST group is the unit).

These pin the CONSTRUCTION choices, not just that the code runs. Every one of them is a
choice the module could have made differently, and a silent change to any would re-cut a
stratum or re-classify an exit without failing anything - the defect shape this tree keeps
finding (S108 off-instrument, S109 `session_b_share`, the 2026-08-29 `_family_id` split).

The load-bearing three, because they are the ones a reader should check first:

* `NoLookaheadTests` - an add reads the queue that stood when IT rested, even when the
  order ahead of it is cancelled later in the same group. The negative case is RUN beside
  it: the same group read at F_LAST reports nothing ahead, which is present, typed, in
  range and wrong.
* `FifoIdentityTests` - a fill ahead is credited when the BOOK removes the filled order, not
  when the `F` row arrives, so `initial_ahead - current_ahead == fills_ahead + cancels_ahead`
  holds throughout and a recorded violation still means a non-FIFO event.
* `TerminalAttributionTests` - `F` mutates nothing in this feed, so FILLED and CANCELLED are
  told apart by pending fill quantity at removal and never by the removing row's action.
"""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark import native_queue_adapter as qa
from research.kalshi.frankie_raw_mbo_benchmark.native_group_adapters import GroupContext
from research.kalshi.frankie_raw_mbo_benchmark.native_queue import (
    CANCELLED,
    FILLED,
    OPEN_AT_SEGMENT_END,
    QueueSurvivalCalculator,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_rt_book import ReplayBook, RtBookError

F_SNAPSHOT = 32
F_TOB = 64


def ctx(**over):
    base = dict(
        group_index=0,
        source_day="20211004",
        source_role="SCORED_FINDINGS_DAY",
        continuity_segment=18904,
        session_phase="RTH",
        family_id="ow-abc",
        side_orientation="B",
        event_ns=90,
        recv_ns=1_000,
        instrument_id=42,
    )
    base.update(over)
    return GroupContext(**base)


def row(action, side, order_id, price, size, recv, **over):
    out = {
        "action": action,
        "side": side,
        "order_id": order_id,
        "price_raw": price,
        "size": size,
        "ts_recv_ns": recv,
        "ts_event_ns": recv - 10,
        "sequence": recv,
        "flags": 0,
        "instrument_id": 42,
    }
    out.update(over)
    return out


class Harness:
    """One calculator, one adapter, one book advanced across every group - as the driver is."""

    def __init__(self):
        self.calc = QueueSurvivalCalculator()
        self.adapter = qa.QueueGroupAdapter()
        self.book = ReplayBook()

    def feed(self, actions, **over):
        return self.adapter.feed_group(self.calc, actions, ctx(**over), book=self.book)

    def lifecycles(self, recv_ns=9_000):
        """Close everything still open and index every exact row by order id."""
        return {r["order_id"]: r for r in self.close(recv_ns=recv_ns)}

    def close(self, recv_ns=9_000):
        """Finalize the PAIR, in order: the calculator censors, the adapter releases.

        Found by the seeded walk below rather than by reading the code: finalizing the
        calculator alone leaves the adapter still tracking every order the calculator has
        just censored, and the next thing it says about one of them lands in
        `unknown_order_events` - a defect counter turned into noise. The two are one
        operation and the tests spell it as one.
        """
        rows = self.calc.finalize(recv_ns=recv_ns)
        self.adapter.finalize()
        return rows


class GuardTests(unittest.TestCase):
    def test_an_empty_group_is_refused(self):
        h = Harness()
        with self.assertRaises(qa.QueueAdapterError):
            h.feed([])

    def test_a_negative_size_on_a_fill_row_raises_rather_than_clamping(self):
        # `ReplayBook.apply` returns before validating anything on F/T/N, so the fill size is
        # validated where it is READ. max(0, size) would make a malformed row a silent zero.
        h = Harness()
        h.feed([row("A", "B", 1, 1000, 5, 100)])
        with self.assertRaises(qa.QueueAdapterError):
            h.feed([row("F", "B", 1, 1000, -3, 110)], group_index=1)

    def test_a_negative_size_on_a_book_row_is_refused_by_the_book(self):
        h = Harness()
        with self.assertRaises(RtBookError):
            h.feed([row("A", "B", 1, 1000, -1, 100)])

    def test_a_second_book_for_one_instrument_is_refused(self):
        # A book rebuilt between groups reports every resting order as front-of-queue, which
        # is a number rather than a failure.
        h = Harness()
        h.feed([row("A", "B", 1, 1000, 5, 100)])
        with self.assertRaises(qa.QueueAdapterError):
            h.adapter.feed_group(h.calc, [row("A", "B", 2, 1000, 5, 110)], ctx(), book=ReplayBook())

    def test_a_row_naming_another_instrument_is_refused(self):
        h = Harness()
        with self.assertRaises(qa.QueueAdapterError):
            h.feed([row("A", "B", 1, 1000, 5, 100, instrument_id=43)])

    def test_a_segment_change_with_tracking_still_held_is_refused(self):
        """A missing boundary call must fail, not read as a queue that never moved."""
        h = Harness()
        h.feed([row("A", "B", 1, 1000, 5, 100)])
        with self.assertRaises(qa.QueueAdapterError):
            h.feed([row("A", "B", 2, 1000, 5, 200)], group_index=1, continuity_segment=18905)
        h.adapter.close_continuity_segment(segment=18904)
        out = h.feed([row("A", "B", 2, 1000, 5, 200)], group_index=1, continuity_segment=18905)
        self.assertEqual(out["births"], 1)

    def test_finalizing_the_calculator_alone_leaves_the_adapter_tracking(self):
        """The pairing, asserted as a requirement rather than assumed by a caller.

        `QueueSurvivalCalculator.finalize` censors every open lifecycle. The adapter cannot
        see that happen, so it must be released too - and until it is, it still holds the
        orders. Written as a test so a wirer meets the requirement instead of the symptom.
        """
        h = Harness()
        h.feed([row("A", "B", 1, 1000, 5, 100)])
        h.calc.finalize(recv_ns=9_000)
        self.assertEqual(h.calc.open_order_count, 0)
        self.assertEqual(h.adapter.open_tracked_orders, 1, "the adapter is not finalized yet")
        receipt = h.adapter.finalize()
        self.assertEqual(receipt["tracking_released"], 1)
        self.assertEqual(h.adapter.open_tracked_orders, 0)

    def test_the_adapter_never_censors_on_the_calculators_behalf(self):
        # Two owners for one censoring would double-count; the traversal owns the boundary
        # because it owns the boundary's receive time.
        h = Harness()
        h.feed([row("A", "B", 1, 1000, 5, 100)])
        receipt = h.adapter.close_continuity_segment(segment=18904)
        self.assertEqual(receipt["tracking_released"], 1)
        self.assertEqual(h.calc.censored_count, 0)
        self.assertEqual(h.calc.open_order_count, 1)


class NoLookaheadTests(unittest.TestCase):
    """The whole reason `ReplayBook` exists, asserted rather than described.

    NC-3, S113: a test that never produces the guard's output has not tested the guard. The
    first version of this class stacked three adds at one level and asserted 0/1/2 ahead -
    and a book advanced over the WHOLE group first returns 0/1/2 as well, because nothing
    later in that group moved anybody. It proved FIFO ordering and nothing about lookahead.
    The discriminating shape is a departure LATER in the same group: only a book advanced
    action by action still reports the order that stood ahead when the add rested.
    """

    LOOKAHEAD_PROBE = [
        row("A", "B", 10, 1000, 5, 100),
        row("A", "B", 11, 1000, 7, 110),   # rests behind 10: 1 order, 5 lots ahead
        row("C", "B", 10, 1000, 5, 120),   # 10 leaves LATER IN THE SAME GROUP
        row("A", "B", 12, 1000, 3, 130),   # rests behind 11: 1 order, 7 lots ahead
    ]

    def test_an_add_reads_the_queue_that_stood_when_it_rested(self):
        h = Harness()
        h.feed(self.LOOKAHEAD_PROBE)
        rows = h.lifecycles()
        self.assertEqual(rows[11]["episodes"][0]["initial_orders_ahead"], 1)
        self.assertEqual(rows[11]["episodes"][0]["initial_volume_ahead"], 5)
        self.assertEqual(rows[12]["episodes"][0]["initial_orders_ahead"], 1)
        self.assertEqual(rows[12]["episodes"][0]["initial_volume_ahead"], 7)

    def test_the_same_group_read_at_F_LAST_gives_a_different_answer(self):
        """The negative case, run rather than asserted in prose.

        This is what an adapter reading `InstrumentBook` at group close would have recorded:
        order 11 reports NOTHING ahead of it, because by F_LAST the order that was ahead had
        already been cancelled. Present, typed, in range and wrong - and 0 rather than 1 is
        the difference between an order that queued and an order that was at the touch.
        """
        book = ReplayBook()
        for action in self.LOOKAHEAD_PROBE:
            book.apply(action)
        self.assertEqual(book.view("B", 1000, 11), (0, 0))
        self.assertEqual(book.view("B", 1000, 12), (1, 7))

    def test_fifo_admits_every_new_order_at_the_back(self):
        h = Harness()
        h.feed([
            row("A", "B", 10, 1000, 5, 100),
            row("A", "B", 11, 1000, 7, 110),
            row("A", "B", 12, 1000, 3, 120),
        ])
        rows = h.lifecycles()
        ahead = [rows[o]["episodes"][0]["initial_orders_ahead"] for o in (10, 11, 12)]
        volume = [rows[o]["episodes"][0]["initial_volume_ahead"] for o in (10, 11, 12)]
        self.assertEqual(ahead, [0, 1, 2])
        self.assertEqual(volume, [0, 5, 12])

    def test_birth_time_is_the_rows_own_receive_clock_not_the_groups(self):
        # A lifetime measured on the group clock is zero for every order born and killed
        # inside one group, which is a large share of them.
        h = Harness()
        h.feed([row("A", "B", 10, 1000, 5, 100), row("C", "B", 10, 1000, 5, 400)])
        rows = h.lifecycles()
        self.assertEqual(rows, {})  # nothing left open
        self.assertEqual(h.calc.resolved_lifetime.rows()[0]["value"]["maximum"], 300.0)


class TerminalAttributionTests(unittest.TestCase):
    def _terminal(self, h):
        return h.adapter  # convenience for readability in the tests below

    def test_a_removal_that_books_a_pending_fill_is_filled(self):
        h = Harness()
        out = h.feed([
            row("A", "B", 10, 1000, 5, 100),
            row("F", "B", 10, 1000, 5, 110),
            row("C", "B", 10, 1000, 5, 120),
        ])
        self.assertEqual(len(out["terminals"]), 1)
        terminal = out["terminals"][0]
        self.assertEqual(terminal["terminal_status"], FILLED)
        self.assertEqual(terminal["terminal_basis"], qa.TERMINAL_BASIS_FILL)
        self.assertEqual(terminal["own_fill_size"], 5)
        self.assertTrue(terminal["resolved"])

    def test_a_removal_with_no_pending_fill_is_cancelled(self):
        # The removing row is a `C` in BOTH cases. Only the pending fill tells them apart.
        h = Harness()
        out = h.feed([row("A", "B", 10, 1000, 5, 100), row("C", "B", 10, 1000, 5, 120)])
        terminal = out["terminals"][0]
        self.assertEqual(terminal["terminal_status"], CANCELLED)
        self.assertEqual(terminal["terminal_basis"], qa.TERMINAL_BASIS_CANCEL)

    def test_a_partial_fill_then_a_pull_of_the_remainder_resolves_as_cancelled(self):
        """The pending quantity was already booked by the earlier reduction."""
        h = Harness()
        out = h.feed([
            row("A", "B", 10, 1000, 5, 100),
            row("F", "B", 10, 1000, 2, 110),
            row("C", "B", 10, 1000, 2, 120),   # books the fill, order survives at size 3
            row("C", "B", 10, 1000, 3, 130),   # a genuine pull of what is left
        ])
        terminal = out["terminals"][0]
        self.assertEqual(terminal["terminal_status"], CANCELLED)
        self.assertEqual(terminal["own_fill_size"], 2)

    def test_every_terminal_row_carries_its_basis_and_its_scope(self):
        # S114: a caveat that lives only in a docstring is a caveat that expires.
        h = Harness()
        out = h.feed([row("A", "B", 10, 1000, 5, 100), row("C", "B", 10, 1000, 5, 120)])
        terminal = out["terminals"][0]
        self.assertEqual(terminal["queue_scope"], qa.QUEUE_SCOPE)
        self.assertIn("terminal_basis", terminal)
        self.assertEqual(terminal["birth_group_index"], 0)
        self.assertEqual(terminal["terminal_group_index"], 0)

    def test_resolved_and_censored_orders_never_collapse_into_one_population(self):
        h = Harness()
        h.feed([
            row("A", "B", 10, 1000, 5, 100),
            row("A", "B", 11, 1000, 5, 110),
            row("C", "B", 10, 1000, 5, 200),
        ])
        h.calc.finalize(recv_ns=5_000)
        self.assertEqual(h.calc.resolved_count, 1)
        self.assertEqual(h.calc.censored_count, 1)
        survival = h.calc.time_to_exit.rows()[0]["value"]
        self.assertEqual(survival["total_observations"], 2)
        self.assertEqual(survival["observed_events"], 1)
        self.assertEqual(survival["censored_observations"], 1)


class FifoIdentityTests(unittest.TestCase):
    """A fill ahead is credited at the DEPARTURE, so the calculator's identity stays exact."""

    def test_a_fill_ahead_is_booked_when_the_book_removes_the_filled_order(self):
        h = Harness()
        h.feed([
            row("A", "B", 10, 1000, 5, 100),
            row("A", "B", 11, 1000, 7, 110),
            row("F", "B", 10, 1000, 5, 120),
            row("C", "B", 10, 1000, 5, 130),
        ])
        rows = h.lifecycles()
        episode = rows[11]["episodes"][0]
        self.assertEqual(episode["initial_orders_ahead"], 1)
        self.assertEqual(episode["final_orders_ahead"], 0)
        self.assertEqual(episode["fills_ahead"], 1)
        self.assertEqual(episode["cancels_ahead"], 0)
        self.assertEqual(episode["queue_movement"], 1)
        self.assertEqual(h.calc.identity_violations, 0)

    def test_crediting_at_the_fill_row_would_have_broken_the_identity(self):
        """The negative case, stated as the reason the credit point is what it is.

        At the `F` row the book has not moved - `F` mutates nothing in this feed - so a
        credit there raises `fills_ahead` while `current_orders_ahead` is unchanged and the
        residual goes negative. This asserts the residual never does.
        """
        h = Harness()
        h.feed([
            row("A", "B", 10, 1000, 5, 100),
            row("A", "B", 11, 1000, 7, 110),
            row("F", "B", 10, 1000, 5, 120),
        ])
        rows = h.lifecycles()
        episode = rows[11]["episodes"][0]
        self.assertEqual(episode["fills_ahead"], 0, "not credited until the order is removed")
        self.assertEqual(episode["residual_negative_violations"], 0)
        self.assertEqual(h.calc.identity_violations, 0)

    def test_a_cancel_ahead_shows_up_as_a_cancel_not_a_fill(self):
        h = Harness()
        h.feed([
            row("A", "B", 10, 1000, 5, 100),
            row("A", "B", 11, 1000, 7, 110),
            row("C", "B", 10, 1000, 5, 130),
        ])
        rows = h.lifecycles()
        episode = rows[11]["episodes"][0]
        self.assertEqual(episode["fills_ahead"], 0)
        self.assertEqual(episode["cancels_ahead"], 1)
        self.assertEqual(h.calc.identity_violations, 0)

    def test_a_partial_cancel_ahead_moves_volume_without_moving_position(self):
        h = Harness()
        h.feed([
            row("A", "B", 10, 1000, 5, 100),
            row("A", "B", 11, 1000, 7, 110),
            row("C", "B", 10, 1000, 2, 130),
        ])
        rows = h.lifecycles()
        episode = rows[11]["episodes"][0]
        self.assertEqual(episode["initial_volume_ahead"], 5)
        self.assertEqual(episode["final_volume_ahead"], 3)
        self.assertEqual(episode["final_orders_ahead"], 1)
        self.assertEqual(episode["queue_movement"], 0)


class PriorityTests(unittest.TestCase):
    def test_a_reprice_opens_a_new_episode_at_the_back_of_the_new_level(self):
        h = Harness()
        h.feed([
            row("A", "B", 10, 1000, 5, 100),
            row("A", "B", 11, 999, 4, 105),
            row("M", "B", 10, 999, 5, 120),
        ])
        rows = h.lifecycles()
        self.assertEqual(rows[10]["priority_loss_count"], 1)
        self.assertEqual(rows[10]["episode_count"], 2)
        first, second = rows[10]["episodes"]
        self.assertEqual(first["price_raw"], 1000)
        self.assertEqual(second["price_raw"], 999)
        self.assertEqual(second["initial_orders_ahead"], 1)

    def test_a_size_decrease_at_the_same_price_keeps_priority(self):
        h = Harness()
        h.feed([
            row("A", "B", 10, 1000, 5, 100),
            row("A", "B", 11, 1000, 7, 110),
            row("M", "B", 11, 1000, 3, 120),
        ])
        rows = h.lifecycles()
        self.assertEqual(rows[11]["episode_count"], 1)
        self.assertEqual(rows[11]["modify_count"], 1)
        self.assertEqual(rows[11]["priority_loss_count"], 0)

    def test_a_size_increase_loses_priority_even_where_the_position_cannot_show_it(self):
        """The rule can fire where the observation cannot see it, and that is counted.

        Order 11 is already last at its level, so re-appending it to the back leaves
        `orders_ahead` unchanged. The observed position can FALSIFY the rule but never
        confirm it, which is why the rule is the primary and the gap is a counter.
        """
        h = Harness()
        h.feed([
            row("A", "B", 10, 1000, 5, 100),
            row("A", "B", 11, 1000, 7, 110),
            row("M", "B", 11, 1000, 9, 120),
        ])
        rows = h.lifecycles()
        self.assertEqual(rows[11]["priority_loss_count"], 1)
        self.assertEqual(rows[11]["episode_count"], 2)
        self.assertEqual(h.adapter.counters["priority_loss_not_visible_in_position"], 1)
        self.assertEqual(h.adapter.counters["priority_rule_disagreement"], 0)

    def test_a_departure_by_reprice_is_declared_rather_than_hidden_in_the_residual(self):
        """`cancels_ahead` is a residual, so a re-price ahead is booked as a cancel ahead.

        The adapter does not fight the calculator's declared basis; it counts how often the
        residual is carrying a move rather than a pull.
        """
        h = Harness()
        h.feed([
            row("A", "B", 10, 1000, 5, 100),
            row("A", "B", 11, 1000, 7, 110),
            row("M", "B", 10, 999, 5, 120),
        ])
        rows = h.lifecycles()
        self.assertEqual(rows[11]["episodes"][0]["cancels_ahead"], 1)
        self.assertEqual(h.adapter.counters["reprice_departures_ahead"], 1)

    def test_a_requeue_at_the_same_price_still_moves_everyone_behind(self):
        """The case a price comparison alone would miss.

        A size increase keeps the price, so `moved` is false, and yet `_modify` detaches the
        order and re-appends it: everything behind it moves up on a departure that is neither
        a fill nor a cancel. Detected from the position AFTER the row rather than from the
        price, and counted like any other re-queue.
        """
        h = Harness()
        h.feed([
            row("A", "B", 10, 1000, 5, 100),
            row("A", "B", 11, 1000, 7, 110),
            row("A", "B", 12, 1000, 3, 120),
            row("M", "B", 10, 1000, 8, 130),   # same price, larger size: back of the queue
        ])
        rows = h.lifecycles()
        self.assertEqual(rows[10]["priority_loss_count"], 1)
        self.assertEqual(rows[11]["episodes"][0]["final_orders_ahead"], 0)
        self.assertEqual(rows[11]["episodes"][0]["cancels_ahead"], 1)
        self.assertEqual(rows[12]["episodes"][0]["final_orders_ahead"], 1)
        self.assertEqual(h.adapter.counters["reprice_departures_ahead"], 2)
        self.assertEqual(h.calc.identity_violations, 0)

    def test_a_duplicate_add_requeues_one_lifecycle_instead_of_forking_it(self):
        # `_add_order` REPLACES on a duplicate id, and `on_add` refuses a second birth for
        # one order, so the only lawful reading is priority loss.
        h = Harness()
        h.feed([row("A", "B", 10, 1000, 5, 100), row("A", "B", 10, 1000, 6, 110)])
        rows = h.lifecycles()
        self.assertEqual(rows[10]["episode_count"], 2)
        self.assertEqual(h.adapter.counters["duplicate_add_requeued"], 1)

    def test_a_modify_for_an_order_that_never_rested_is_a_birth(self):
        # Databento's reference LOB treats a missing modify as an add and the book mirrors it.
        h = Harness()
        out = h.feed([row("M", "B", 10, 1000, 5, 100)])
        self.assertEqual(out["births"], 1)
        self.assertEqual(h.adapter.counters["modify_missing_treated_as_add"], 1)


class RetainedNotDroppedTests(unittest.TestCase):
    """Everything observed is either measured or COUNTED. Nothing is passed over (D60)."""

    def test_an_anonymous_order_rests_in_the_book_but_opens_no_lifecycle(self):
        # order_id 0 is a missing identity, not an identity: one key would fuse unrelated
        # orders. The book still rests it, so the level depth behind it stays right.
        h = Harness()
        h.feed([row("A", "B", 0, 1000, 4, 100), row("A", "B", 7, 1000, 2, 110)])
        rows = h.lifecycles()
        self.assertEqual(set(rows), {7})
        self.assertEqual(rows[7]["episodes"][0]["initial_orders_ahead"], 1)
        self.assertEqual(rows[7]["episodes"][0]["initial_volume_ahead"], 4)
        self.assertEqual(h.adapter.counters["anonymous_adds_not_tracked"], 1)

    def test_a_snapshot_add_restates_a_book_and_is_not_a_birth(self):
        h = Harness()
        h.feed([
            row("A", "B", 5, 1000, 8, 100, flags=F_SNAPSHOT),
            row("A", "B", 6, 1000, 2, 110),
        ])
        rows = h.lifecycles()
        self.assertEqual(set(rows), {6})
        self.assertEqual(rows[6]["episodes"][0]["initial_volume_ahead"], 8)
        self.assertEqual(h.adapter.counters["snapshot_adds_not_born"], 1)

    def test_a_cancel_for_an_order_that_rested_before_the_window_is_counted(self):
        h = Harness()
        h.feed([row("C", "B", 99, 1000, 5, 100)])
        self.assertEqual(h.adapter.counters["cancel_for_untracked_order"], 1)
        self.assertEqual(h.calc.unknown_order_events, 0, "never routed into the defect counter")

    def test_a_fill_the_book_cannot_locate_is_counted_and_not_levelled(self):
        # An aggressor's own fill names no resting order, so its side is the row's claim
        # rather than a book fact. Levelling it would fabricate the missing fact.
        h = Harness()
        h.feed([row("F", "A", 77, 1000, 5, 100)])
        self.assertEqual(h.adapter.counters["fill_for_unlocated_order"], 1)

    def test_trades_and_none_rows_leave_a_trace(self):
        h = Harness()
        out = h.feed([row("T", "A", 0, 1000, 3, 100), row("N", "N", 0, 1000, 0, 110)])
        self.assertEqual(out["rows_applied"], 2)
        self.assertEqual(h.adapter.counters["non_mutating_T"], 1)
        self.assertEqual(h.adapter.counters["non_mutating_N"], 1)


class AdministrativeRemovalTests(unittest.TestCase):
    """A reset and a top-of-book wipe end an order without a fill or a cancel."""

    def test_a_reset_leaves_the_lifecycle_open_so_it_is_censored_not_resolved(self):
        h = Harness()
        h.feed([row("A", "B", 10, 1000, 5, 100), row("R", "N", 0, 0, 0, 200)])
        self.assertEqual(h.adapter.counters["orphaned_by_reset"], 1)
        self.assertEqual(h.calc.open_order_count, 1, "not resolved by an administrative removal")
        censored = h.calc.close_continuity_segment(segment=18904, recv_ns=9_000)
        self.assertEqual(censored[0]["terminal_status"], OPEN_AT_SEGMENT_END)
        self.assertTrue(censored[0]["censored"])
        self.assertEqual(h.calc.resolved_count, 0)

    def test_a_top_of_book_wipe_orphans_only_its_own_side(self):
        h = Harness()
        h.feed([
            row("A", "B", 10, 1000, 5, 100),
            row("A", "A", 20, 1010, 5, 110),
            row("A", "B", 0, qa.PRICE_SENTINEL_ABS, 0, 120, flags=F_TOB),
        ])
        self.assertEqual(h.adapter.counters["orphaned_by_tob_wipe"], 1)
        self.assertIsNone(h.book.resting_at(10))
        self.assertIsNotNone(h.book.resting_at(20))

    def test_a_cancel_row_for_an_orphaned_order_does_not_resolve_it(self):
        h = Harness()
        h.feed([row("A", "B", 10, 1000, 5, 100), row("R", "N", 0, 0, 0, 200)])
        h.feed([row("C", "B", 10, 1000, 5, 300)], group_index=1)
        self.assertEqual(h.adapter.counters["terminal_row_for_orphaned_order"], 1)
        self.assertEqual(h.calc.resolved_count, 0)
        self.assertEqual(h.calc.open_order_count, 1)


class DeclaredScopeTests(unittest.TestCase):
    """D53's cost is stated ON the value and counted, never described and forgotten."""

    def test_the_scope_constant_is_declared_not_only_in_prose(self):
        self.assertEqual(qa.QUEUE_SCOPE, "BIRTH_GROUP_STRATUM")

    def test_the_report_names_every_distortion_and_the_counters_that_size_it(self):
        report = qa.QueueGroupAdapter().report()
        self.assertEqual(report["section"], "4.6")
        self.assertEqual(report["queue_scope"], qa.QUEUE_SCOPE)
        self.assertEqual(report["fills_ahead_credit_point"], "BOOK_REMOVAL_OF_THE_FILLED_ORDER")
        names = {d["name"] for d in report["declared_distortions"]}
        self.assertIn("BIRTH_GROUP_STRATUM", names)
        self.assertIn("RESET_ORPHAN_CENSORED_AT_THE_BOUNDARY", names)
        for declared in report["declared_distortions"]:
            self.assertTrue(declared["statement"])
            self.assertTrue(declared["counters"])

    def test_every_counter_a_distortion_promises_is_one_the_module_writes(self):
        """A declaration pointing at a counter nobody increments has quietly expired.

        `DECLARED_DISTORTIONS` is the value-borne form of D53's cost, and its whole job is to
        say how big each distortion is. Rename a counter and the statement survives while the
        number it points at stops existing - a caveat that reads live on dead evidence, which
        is the S114 schema correction in miniature. So the names are checked against the
        module that writes them.
        """
        import inspect

        source = inspect.getsource(qa)
        for declared in qa.DECLARED_DISTORTIONS:
            for name in (n.strip() for n in declared["counters"].split(",")):
                with self.subTest(distortion=declared["name"], counter=name):
                    self.assertIn(f'"{name}"', source)

    def test_an_order_outliving_its_birth_group_is_counted(self):
        """The stratum is stamped at birth and never restamped, so the count sizes the fiction."""
        h = Harness()
        h.feed([row("A", "B", 10, 1000, 5, 100)])
        h.feed([row("C", "B", 10, 1000, 5, 300)], group_index=1)
        self.assertEqual(h.adapter.counters["lifecycles_outliving_birth_group"], 1)

    def test_the_birth_phase_is_kept_and_a_later_phase_is_counted_not_restamped(self):
        h = Harness()
        h.feed([row("A", "B", 10, 1000, 5, 100)])
        out = h.feed(
            [row("C", "B", 10, 1000, 5, 300)], group_index=1, session_phase="POST_SETTLEMENT"
        )
        terminal = out["terminals"][0]
        self.assertEqual(terminal["session_phase"], "RTH", "the stratum keeps the birth phase")
        self.assertEqual(terminal["birth_session_phase"], "RTH")
        self.assertEqual(h.adapter.counters["lifecycles_observed_in_another_phase"], 1)

    def test_a_sentinel_priced_rest_is_kept_and_counted_never_dropped(self):
        # The book rests it and reports it as the touch, so it is real to everything else at
        # that level. Dropping it here would leave the level one order short.
        h = Harness()
        h.feed([row("A", "B", 10, qa.PRICE_SENTINEL_ABS, 5, 100)])
        self.assertEqual(h.adapter.counters["sentinel_price_births"], 1)
        self.assertEqual(h.adapter.open_tracked_orders, 1)


class RealCalculatorTests(unittest.TestCase):
    """The end-to-end assertion: a plausible cascade lands in the REAL 4.6 calculator."""

    CASCADE = [
        row("A", "B", 10, 3000, 5, 100),
        row("A", "B", 11, 3000, 7, 110),
        row("A", "A", 20, 3010, 4, 120),
        row("T", "A", 0, 3000, 5, 130),
        row("F", "B", 10, 3000, 5, 140),
        row("C", "B", 10, 3000, 5, 150),
        row("C", "A", 20, 3010, 4, 160),
    ]

    def test_the_cascade_feeds_every_ingest_point(self):
        h = Harness()
        out = h.feed(self.CASCADE)
        self.assertEqual(out["births"], 3)
        self.assertEqual(out["own_fills"], 1)
        self.assertEqual(out["level_fills"], 1)
        self.assertEqual(len(out["terminals"]), 2)
        statuses = {t["order_id"]: t["terminal_status"] for t in out["terminals"]}
        self.assertEqual(statuses, {10: FILLED, 20: CANCELLED})

    def test_the_summary_splits_resolved_from_censored_and_counts_no_violations(self):
        h = Harness()
        h.feed(self.CASCADE)
        h.calc.finalize(recv_ns=9_000)
        summary = h.calc.summary()
        self.assertEqual(summary["section"], "4.6")
        self.assertEqual(summary["resolved"], 2)
        self.assertEqual(summary["censored"], 1)
        self.assertEqual(summary["still_open"], 0)
        self.assertEqual(summary["fifo_identity_violations"], 0)
        self.assertEqual(summary["events_for_unknown_orders"], 0)

    def test_the_two_sides_land_in_different_strata(self):
        # Section 3 forbids pooling across sides, and the side comes off the BOOK rather than
        # off the row, so a stratum cannot be cut by an unverified claim.
        h = Harness()
        h.feed(self.CASCADE)
        sides = {r["stratum"]["side_orientation"] for r in h.calc.resolved_lifetime.rows()}
        self.assertEqual(sides, {"B", "A"})

    def test_nothing_the_adapter_feeds_lands_in_the_unknown_order_counter(self):
        """`unknown_order_events` is a defect counter; routing normal tape into it kills it."""
        h = Harness()
        h.feed(self.CASCADE)
        h.calc.finalize(recv_ns=9_000)
        self.assertEqual(h.calc.unknown_order_events, 0)


class SeededTapeTests(unittest.TestCase):
    """Random well-formed tape, one advancing book, and the invariants that must survive it.

    The hand-built cases above each pin ONE construction choice. This drives the adapter over
    thousands of interleaved adds, fills, partial and full cancels, re-prices and size changes
    and asserts the properties that no single case can: that the FIFO identity never breaks,
    that nothing the adapter feeds lands in the calculator's defect counter, and that every
    order it opened is closed exactly once. A regression in the refresh scope, the fill credit
    point or the level index shows up here as a violation count rather than as an exception.
    """

    BIDS = (2_990_000_000, 2_995_000_000, 3_000_000_000, 3_005_000_000)
    ASKS = (3_020_000_000, 3_025_000_000, 3_030_000_000, 3_035_000_000)

    def _walk(self, seed, groups=400):
        import random

        rng = random.Random(seed)
        h = Harness()
        live: list[int] = []
        order_id = 1_000
        recv = 1_000_000
        births = 0
        for group_index in range(groups):
            actions = []
            for _ in range(rng.randint(1, 5)):
                recv += rng.randint(1, 50)
                live = [o for o in live if h.book.is_resting(o)]
                resting_is_deep = len(live) >= 40
                if rng.random() < (0.15 if resting_is_deep else 0.55) or not live:
                    order_id += 1
                    side = rng.choice("BA")
                    price = rng.choice(self.BIDS if side == "B" else self.ASKS)
                    live.append(order_id)
                    actions.append(row("A", side, order_id, price, rng.randint(1, 9), recv))
                    continue
                target = rng.choice(live)
                side, price, size = h.book.resting_at(target)
                draw = rng.random()
                if draw < 0.28:
                    actions.append(row("F", side, target, price, rng.randint(1, size), recv))
                elif draw < 0.70:
                    pull = rng.choice([size, max(1, size // 2)])
                    actions.append(row("C", side, target, price, pull, recv))
                elif draw < 0.95:
                    moved = rng.choice(self.BIDS if side == "B" else self.ASKS)
                    actions.append(
                        row("M", side, target, moved, max(1, size + rng.randint(-3, 3)), recv)
                    )
                else:
                    actions.append(row("T", side, 0, price, rng.randint(1, 4), recv))
            births += h.feed(actions, group_index=group_index, recv_ns=recv)["births"]
        h.close(recv_ns=recv + 10_000)
        return births, h

    def test_the_fifo_identity_survives_random_tape(self):
        for seed in range(6):
            with self.subTest(seed=seed):
                births, h = self._walk(seed)
                summary = h.calc.summary()
                self.assertGreater(births, 50, "the walk must actually exercise births")
                self.assertEqual(summary["fifo_identity_violations"], 0)

    def test_nothing_the_adapter_feeds_reaches_the_defect_counter(self):
        for seed in range(6):
            with self.subTest(seed=seed):
                _, h = self._walk(seed)
                self.assertEqual(h.calc.unknown_order_events, 0)

    def test_every_order_opened_is_closed_exactly_once(self):
        for seed in range(6):
            with self.subTest(seed=seed):
                births, h = self._walk(seed)
                summary = h.calc.summary()
                self.assertEqual(summary["completed_lifecycles"], births)
                self.assertEqual(summary["resolved"] + summary["censored"], births)
                self.assertEqual(summary["still_open"], 0)
                self.assertEqual(h.adapter.open_tracked_orders, 0)


if __name__ == "__main__":
    unittest.main()
