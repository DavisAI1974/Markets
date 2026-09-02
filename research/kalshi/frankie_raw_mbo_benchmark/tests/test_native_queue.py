"""Tests for section 4.6 queue position, priority, and order survival."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_queue import (
    CANCELLED,
    FILLED,
    OPEN_AT_SEGMENT_END,
    OPEN_AT_STREAM_END,
    OPENED_AT_BIRTH,
    REOPENED_PRICE_CHANGED,
    REOPENED_SAME_LEVEL,
    REOPENED_SIDE_CHANGED,
    UNIT_BIRTH_EPISODE,
    UNIT_CLOSED_EPISODE,
    UNIT_LIFECYCLE,
    UNIT_REQUEUE_EPISODE,
    OrderLifecycle,
    QueueEpisode,
    QueueError,
    QueueSurvivalCalculator,
)


def total_n(measure) -> int:
    """Observations across every stratum, whichever accumulator the measure uses."""
    total = 0
    for row in measure.rows():
        value = row["value"]
        total += int(value.get("n", value.get("total_observations", 0)) or 0)
    return total


class FakeBook:
    """Minimal FIFO book view: levels[(side, price)] = [(order_id, size), ...]."""

    def __init__(self) -> None:
        self.levels: dict[tuple[str, int], list[tuple[int, int]]] = {}

    def rest(self, side: str, price: int, order_id: int, size: int) -> None:
        self.levels.setdefault((side, price), []).append((order_id, size))

    def remove(self, side: str, price: int, order_id: int) -> None:
        queue = self.levels.get((side, price), [])
        self.levels[(side, price)] = [row for row in queue if row[0] != order_id]

    def view(self, side: str, price: int, order_id: int) -> tuple[int, int]:
        queue = self.levels.get((side, price), [])
        ahead = []
        for oid, size in queue:
            if oid == order_id:
                break
            ahead.append(size)
        return len(ahead), sum(ahead)


def add_kwargs(**overrides):
    base = dict(
        instrument_id=42,
        order_id=1,
        side="B",
        price_raw=1000,
        recv_ns=1_000,
        sequence=1,
        continuity_segment=0,
        source_day="20211004",
        source_role="HELD_OUT_BLIND",
        family_id="AN",
        session_phase="RTH",
    )
    base.update(overrides)
    return base


class QueueEpisodeTest(unittest.TestCase):
    def test_cancels_ahead_is_the_fifo_residual(self) -> None:
        """Five ahead, two filled, one cancelled leaves two ahead."""
        episode = QueueEpisode(
            side="B", price_raw=1000, opened_recv_ns=0,
            initial_orders_ahead=5, initial_volume_ahead=50,
            current_orders_ahead=5, current_volume_ahead=50,
        )
        episode.observe(orders_ahead=2, volume_ahead=20, fills_ahead_delta=2)
        self.assertEqual(episode.fills_ahead, 2)
        self.assertEqual(episode.cancels_ahead, 1)
        self.assertEqual(episode.queue_movement, 3)
        self.assertEqual(episode.identity_violations, 0)

    def test_an_increase_in_orders_ahead_is_recorded_not_repaired(self) -> None:
        """FIFO admits new orders behind, so an increase means the premise broke."""
        episode = QueueEpisode(
            side="B", price_raw=1000, opened_recv_ns=0,
            initial_orders_ahead=2, initial_volume_ahead=20,
            current_orders_ahead=2, current_volume_ahead=20,
        )
        episode.observe(orders_ahead=4, volume_ahead=40)
        self.assertEqual(episode.identity_violations, 1, "one bad observation is one violation")
        self.assertEqual(episode.ahead_increase_violations, 1)
        self.assertEqual(episode.residual_negative_violations, 1)
        self.assertEqual(episode.current_orders_ahead, 4)

    def test_more_fills_than_departures_breaks_the_identity(self) -> None:
        episode = QueueEpisode(
            side="B", price_raw=1000, opened_recv_ns=0,
            initial_orders_ahead=5, initial_volume_ahead=50,
            current_orders_ahead=4, current_volume_ahead=40,
        )
        episode.observe(orders_ahead=4, volume_ahead=40, fills_ahead_delta=3)
        self.assertEqual(episode.identity_violations, 1)
        self.assertEqual(episode.ahead_increase_violations, 0, "orders_ahead did not increase")
        self.assertEqual(episode.residual_negative_violations, 1)
        self.assertEqual(episode.cancels_ahead, 0)


class LifecycleTest(unittest.TestCase):
    def test_resolved_lifetime_and_age(self) -> None:
        lifecycle = OrderLifecycle(
            order_id=1, instrument_id=42, continuity_segment=0,
            birth_recv_ns=1_000, birth_sequence=1, side="B",
            family_id="AN", session_phase="RTH",
            source_day="20211004", source_role="HELD_OUT_BLIND",
        )
        self.assertIsNone(lifecycle.lifetime_ns)
        self.assertEqual(lifecycle.age_ns(3_000), 2_000)
        lifecycle.terminal_recv_ns = 5_000
        lifecycle.terminal_status = FILLED
        self.assertEqual(lifecycle.lifetime_ns, 4_000)
        self.assertTrue(lifecycle.resolved)

    def test_an_order_with_no_episode_is_an_error(self) -> None:
        lifecycle = OrderLifecycle(
            order_id=1, instrument_id=42, continuity_segment=0,
            birth_recv_ns=0, birth_sequence=1, side="B",
            family_id="AN", session_phase="RTH",
            source_day="20211004", source_role="HELD_OUT_BLIND",
        )
        with self.assertRaises(QueueError):
            _ = lifecycle.current_episode


class DeclaredUnitTest(unittest.TestCase):
    """D-13. Two units were reported under one declared population.

    On run 33605852433 `initial_volume_ahead` returned n = 20,005 and `queue_movement`
    n = 24,645, and both declared "resting orders within the stratum and continuity
    segment". One of those numbers counts order births and the other counts closed queue
    episodes, so the shared declaration was false of at least one of them - and a false
    population is worse than an absent one, because it reads as licence to compare the two.
    """

    def setUp(self) -> None:
        self.book = FakeBook()
        self.calc = QueueSurvivalCalculator()

    def populations(self) -> dict[str, str]:
        return {m.name: m.declaration.population for m in self.calc.measures}

    def test_no_two_measures_of_different_units_share_a_population(self) -> None:
        units = self.calc.summary()["measure_units"]
        populations = self.populations()
        self.assertEqual(set(units), set(populations), "every measure declares a unit")
        for left in populations:
            for right in populations:
                if left == right or units[left] == units[right]:
                    continue
                self.assertNotEqual(
                    populations[left],
                    populations[right],
                    f"{left} ({units[left]}) and {right} ({units[right]}) count different "
                    "things and cannot declare the same population",
                )

    def test_the_two_units_are_named_on_the_measures_that_produced_the_mismatch(self) -> None:
        units = self.calc.summary()["measure_units"]
        self.assertEqual(units["initial_volume_ahead"], UNIT_BIRTH_EPISODE)
        self.assertEqual(units["requeue_initial_volume_ahead"], UNIT_REQUEUE_EPISODE)
        self.assertEqual(units["queue_movement"], UNIT_CLOSED_EPISODE)
        for name in ("resolved_lifetime_ns", "censored_age_ns", "time_to_exit_ns"):
            self.assertEqual(units[name], UNIT_LIFECYCLE)

    def test_the_declared_population_matches_the_n_the_measure_produces(self) -> None:
        """One order, two priority losses: one birth, three closed episodes, one lifecycle."""
        self.book.rest("B", 1000, 1, 3)
        self.calc.on_add(**add_kwargs(), book_view=self.book.view)
        self.book.rest("B", 1001, 1, 3)
        self.calc.on_priority_loss(
            instrument_id=42, order_id=1, side="B", price_raw=1001,
            recv_ns=2_000, book_view=self.book.view,
        )
        self.book.rest("B", 1002, 1, 3)
        self.calc.on_priority_loss(
            instrument_id=42, order_id=1, side="B", price_raw=1002,
            recv_ns=3_000, book_view=self.book.view,
        )
        self.calc.on_terminal(instrument_id=42, order_id=1, status=FILLED, recv_ns=4_000)

        self.assertEqual(total_n(self.calc.initial_volume_ahead), 1)
        self.assertEqual(total_n(self.calc.requeue_initial_volume_ahead), 2)
        self.assertEqual(total_n(self.calc.queue_movement), 3)
        self.assertEqual(total_n(self.calc.time_to_exit), 1)

        populations = self.populations()
        self.assertIn("BIRTHS", populations["initial_volume_ahead"])
        self.assertIn("episode", populations["queue_movement"])
        self.assertIn("order id", populations["time_to_exit_ns"])

    def test_queue_movement_no_longer_claims_an_exclusion_it_never_performs(self) -> None:
        """An episode never re-observed contributes a measured 0, and 0 is a measurement.

        The old rule said such episodes "are excluded and counted". Nothing was ever
        excluded and `excluded_missing_members` was 0 on every row, so the declaration
        described a mechanism that does not exist - the same defect as the shared
        population, one field over.
        """
        self.book.rest("B", 1000, 1, 3)
        self.calc.on_add(**add_kwargs(), book_view=self.book.view)
        self.calc.on_terminal(instrument_id=42, order_id=1, status=CANCELLED, recv_ns=2_000)
        row = self.calc.queue_movement.rows()[0]
        self.assertEqual(row["value"]["n"], 1)
        self.assertEqual(row["value"]["maximum"], 0.0)
        self.assertEqual(row["excluded_missing_members"], 0)
        rule = row["declaration"]["missingness_rule"]
        self.assertIn("no episode is excluded", rule)
        self.assertNotIn("are excluded and counted", rule)

    def test_the_censored_channel_is_untouched_by_the_unit_split(self) -> None:
        """4.13 copies this channel, so only what it SAYS it counts changed here."""
        self.book.rest("B", 1000, 1, 3)
        self.calc.on_add(**add_kwargs(), book_view=self.book.view)
        self.calc.finalize(recv_ns=9_000)
        row = self.calc.censored_age.rows()[0]
        self.assertEqual(row["value"]["n"], 1, "one observation per declared censoring")
        self.assertEqual(row["value"]["maximum"], 8_000.0)
        self.assertEqual(row["declaration"]["status"], "CENSORED")
        self.assertEqual(
            row["declaration"]["missingness_rule"],
            "resolved orders are excluded here; they appear in resolved_lifetime",
        )


class EpisodeAccountingTest(unittest.TestCase):
    """D-13's residual. 24,645 - 20,005 = 4,640 re-queues against 4,625 `modify_reprice`
    events left FIFTEEN observations unattributed, and they were unattributable because the
    only account of why an episode reopened lived in an adapter counter that never reached
    this section's artifact. Every reopen is classified here now, from the book itself.
    """

    def setUp(self) -> None:
        self.book = FakeBook()
        self.calc = QueueSurvivalCalculator()
        for order_id in (1, 2, 3):
            self.book.rest("B", 1000, order_id, 3)
            self.calc.on_add(**add_kwargs(order_id=order_id), book_view=self.book.view)

    def reopen(self, order_id: int, side: str, price_raw: int, recv_ns: int) -> None:
        self.book.rest(side, price_raw, order_id, 3)
        self.calc.on_priority_loss(
            instrument_id=42, order_id=order_id, side=side, price_raw=price_raw,
            recv_ns=recv_ns, book_view=self.book.view,
        )

    def test_every_reopen_is_classified_by_the_transition_the_book_shows(self) -> None:
        self.reopen(1, "B", 1001, 2_000)   # re-price, the 4,625
        self.reopen(2, "A", 1005, 2_100)   # side change
        self.calc.on_priority_loss(        # same side, same price: a size increase
            instrument_id=42, order_id=3, side="B", price_raw=1000,
            recv_ns=2_200, book_view=self.book.view,
        )
        accounting = self.calc.summary()["episode_accounting"]
        self.assertEqual(
            accounting["reopened_by_level_transition"],
            {REOPENED_PRICE_CHANGED: 1, REOPENED_SIDE_CHANGED: 1, REOPENED_SAME_LEVEL: 1},
        )
        self.assertEqual(accounting["reopened_episodes"], 3)

    def test_a_same_level_requeue_is_not_a_reprice_and_is_counted_apart(self) -> None:
        """The class the fifteen live in: 14 of them are priority losses the book position
        never showed, which is what a size increase at the order's own side and price is."""
        self.calc.on_priority_loss(
            instrument_id=42, order_id=1, side="B", price_raw=1000,
            recv_ns=2_000, book_view=self.book.view,
        )
        self.reopen(2, "B", 1001, 2_100)
        accounting = self.calc.summary()["episode_accounting"]
        self.assertEqual(accounting["reopened_by_level_transition"][REOPENED_SAME_LEVEL], 1)
        self.assertEqual(accounting["reopened_by_level_transition"][REOPENED_PRICE_CHANGED], 1)
        self.assertEqual(accounting["reopens_without_a_price_change"], 1)

    def test_the_basis_travels_on_the_episode_not_only_in_the_census(self) -> None:
        self.reopen(1, "B", 1001, 2_000)
        row = self.calc.on_terminal(instrument_id=42, order_id=1, status=FILLED, recv_ns=3_000)
        first, second = row["episodes"]
        self.assertEqual(first["opened_basis"], OPENED_AT_BIRTH)
        self.assertEqual(second["opened_basis"], REOPENED_PRICE_CHANGED)

    def test_the_census_reconciles_the_two_units_and_the_measure_it_counts(self) -> None:
        self.reopen(1, "B", 1001, 2_000)
        self.reopen(1, "B", 1002, 2_100)
        self.calc.on_terminal(instrument_id=42, order_id=1, status=FILLED, recv_ns=3_000)
        accounting = self.calc.summary()["episode_accounting"]
        self.assertEqual(accounting["birth_episodes"], 3)
        self.assertEqual(accounting["reopened_episodes"], 2)
        self.assertEqual(accounting["episodes_opened"], 5)
        self.assertEqual(accounting["episodes_measured"], 3, "one terminal, two priority losses")
        self.assertEqual(accounting["episodes_still_open"], 2)
        self.assertTrue(accounting["accounting_balances"])
        self.assertEqual(accounting["episodes_measured"], total_n(self.calc.queue_movement))
        self.assertEqual(accounting["birth_episodes"], total_n(self.calc.initial_volume_ahead))
        self.assertEqual(
            accounting["reopened_episodes"], total_n(self.calc.requeue_initial_volume_ahead)
        )

    def test_the_requeue_queue_position_is_measured_and_not_only_retained(self) -> None:
        """4,640 readings of where an order lands after losing priority entered no average.

        The value is the volume resting ahead at the new level, which is a different
        population from the birth queue and belongs in neither the birth measure nor a
        lifecycle row alone.
        """
        self.book.rest("B", 1001, 70, 9)
        self.book.rest("B", 1001, 71, 4)
        self.reopen(1, "B", 1001, 2_000)
        row = self.calc.requeue_initial_volume_ahead.rows()[0]
        self.assertEqual(row["value"]["n"], 1)
        self.assertEqual(row["value"]["maximum"], 13.0)
        self.assertEqual(total_n(self.calc.initial_volume_ahead), 3, "births are unchanged")

    def test_an_episode_that_leaves_without_being_measured_is_reported_not_raised(self) -> None:
        """An order dropped without a terminal is an episode closed where the census cannot
        see it. The shortfall is the evidence for that, so it is reported rather than raised -
        an exception here would destroy the only record of what went missing."""
        self.reopen(1, "B", 1001, 2_000)
        self.calc._open.pop((42, 1))
        accounting = self.calc.summary()["episode_accounting"]
        self.assertFalse(accounting["accounting_balances"])
        self.assertEqual(accounting["episodes_opened"], 4, "three births and one re-queue")
        self.assertEqual(accounting["episodes_measured"], 1, "only the re-queue closed one")
        self.assertEqual(accounting["episodes_still_open"], 2, "order 1 left without exiting")


class QueueSurvivalCalculatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.book = FakeBook()
        self.calc = QueueSurvivalCalculator()

    def test_birth_records_queue_position_from_the_book(self) -> None:
        self.book.rest("B", 1000, 10, 5)
        self.book.rest("B", 1000, 11, 7)
        self.book.rest("B", 1000, 1, 3)
        lifecycle = self.calc.on_add(**add_kwargs(), book_view=self.book.view)
        episode = lifecycle.current_episode
        self.assertEqual(episode.initial_orders_ahead, 2)
        self.assertEqual(episode.initial_volume_ahead, 12)

    def test_a_duplicate_add_is_refused(self) -> None:
        self.book.rest("B", 1000, 1, 3)
        self.calc.on_add(**add_kwargs(), book_view=self.book.view)
        with self.assertRaises(QueueError):
            self.calc.on_add(**add_kwargs(), book_view=self.book.view)

    def test_fill_resolves_and_feeds_the_survival_estimator_as_an_event(self) -> None:
        self.book.rest("B", 1000, 1, 3)
        self.calc.on_add(**add_kwargs(), book_view=self.book.view)
        row = self.calc.on_terminal(instrument_id=42, order_id=1, status=FILLED, recv_ns=4_000)
        self.assertEqual(row["terminal_status"], FILLED)
        self.assertEqual(row["lifetime_ns"], 3_000)
        self.assertTrue(row["resolved"])
        self.assertFalse(row["censored"])
        survival = self.calc.time_to_exit.rows()[0]["value"]
        self.assertEqual(survival["observed_events"], 1)
        self.assertEqual(survival["censored_observations"], 0)

    def test_cancel_also_resolves(self) -> None:
        self.book.rest("B", 1000, 1, 3)
        self.calc.on_add(**add_kwargs(), book_view=self.book.view)
        row = self.calc.on_terminal(instrument_id=42, order_id=1, status=CANCELLED, recv_ns=2_500)
        self.assertEqual(row["terminal_status"], CANCELLED)
        self.assertTrue(row["resolved"])

    def test_censoring_is_not_accepted_as_a_terminal_event(self) -> None:
        self.book.rest("B", 1000, 1, 3)
        self.calc.on_add(**add_kwargs(), book_view=self.book.view)
        with self.assertRaises(QueueError):
            self.calc.on_terminal(instrument_id=42, order_id=1, status=OPEN_AT_SEGMENT_END, recv_ns=2_000)

    def test_segment_end_censors_open_orders_rather_than_crossing_the_boundary(self) -> None:
        """Section 2: no calculation crosses a continuity boundary."""
        self.book.rest("B", 1000, 1, 3)
        self.calc.on_add(**add_kwargs(), book_view=self.book.view)
        rows = self.calc.close_continuity_segment(segment=0, recv_ns=9_000)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["terminal_status"], OPEN_AT_SEGMENT_END)
        self.assertTrue(rows[0]["censored"])
        self.assertEqual(self.calc.open_order_count, 0)
        survival = self.calc.time_to_exit.rows()[0]["value"]
        self.assertEqual(survival["censored_observations"], 1)
        self.assertEqual(survival["observed_events"], 0)

    def test_segment_end_only_censors_its_own_segment(self) -> None:
        self.book.rest("B", 1000, 1, 3)
        self.book.rest("B", 1000, 2, 3)
        self.calc.on_add(**add_kwargs(order_id=1, continuity_segment=0), book_view=self.book.view)
        self.calc.on_add(**add_kwargs(order_id=2, continuity_segment=1), book_view=self.book.view)
        rows = self.calc.close_continuity_segment(segment=0, recv_ns=9_000)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["order_id"], 1)
        self.assertEqual(self.calc.open_order_count, 1)

    def test_resolved_and_censored_lifetimes_are_never_pooled(self) -> None:
        self.book.rest("B", 1000, 1, 3)
        self.book.rest("B", 1000, 2, 3)
        self.calc.on_add(**add_kwargs(order_id=1), book_view=self.book.view)
        self.calc.on_add(**add_kwargs(order_id=2), book_view=self.book.view)
        self.calc.on_terminal(instrument_id=42, order_id=1, status=FILLED, recv_ns=2_000)
        self.calc.finalize(recv_ns=100_000)
        self.assertEqual(self.calc.resolved_lifetime.rows()[0]["value"]["n"], 1)
        self.assertEqual(self.calc.resolved_lifetime.rows()[0]["value"]["maximum"], 1_000.0)
        self.assertEqual(self.calc.censored_age.rows()[0]["value"]["n"], 1)
        self.assertEqual(self.calc.censored_age.rows()[0]["value"]["maximum"], 99_000.0)

    def test_survival_sees_every_order_exactly_once(self) -> None:
        for order_id in (1, 2, 3):
            self.book.rest("B", 1000, order_id, 3)
            self.calc.on_add(**add_kwargs(order_id=order_id), book_view=self.book.view)
        self.calc.on_terminal(instrument_id=42, order_id=1, status=FILLED, recv_ns=2_000)
        self.calc.on_terminal(instrument_id=42, order_id=2, status=CANCELLED, recv_ns=3_000)
        self.calc.finalize(recv_ns=9_000)
        survival = self.calc.time_to_exit.rows()[0]["value"]
        self.assertEqual(survival["total_observations"], 3)
        self.assertEqual(survival["observed_events"], 2)
        self.assertEqual(survival["censored_observations"], 1)
        self.assertTrue(all("at_risk" in r for r in survival["curve"]))

    def test_priority_loss_opens_a_new_episode_at_the_back(self) -> None:
        self.book.rest("B", 1000, 1, 3)
        self.calc.on_add(**add_kwargs(), book_view=self.book.view)
        self.book.remove("B", 1000, 1)
        self.book.rest("B", 1001, 50, 9)
        self.book.rest("B", 1001, 51, 4)
        self.book.rest("B", 1001, 1, 3)
        self.calc.on_priority_loss(
            instrument_id=42, order_id=1, side="B", price_raw=1001,
            recv_ns=5_000, book_view=self.book.view,
        )
        lifecycle = self.calc._open[(42, 1)]
        self.assertEqual(len(lifecycle.episodes), 2)
        self.assertEqual(lifecycle.priority_loss_count, 1)
        self.assertEqual(lifecycle.episodes[0].closed_recv_ns, 5_000)
        self.assertEqual(lifecycle.current_episode.initial_orders_ahead, 2)
        self.assertEqual(lifecycle.current_episode.price_raw, 1001)

    def test_episodes_keep_queue_arithmetic_separate_across_a_reprice(self) -> None:
        self.book.rest("B", 1000, 90, 5)
        self.book.rest("B", 1000, 1, 3)
        self.calc.on_add(**add_kwargs(), book_view=self.book.view)
        self.calc.observe_level(instrument_id=42, order_id=1, orders_ahead=0, volume_ahead=0, fills_ahead_delta=1)
        self.book.rest("B", 1001, 1, 3)
        self.calc.on_priority_loss(
            instrument_id=42, order_id=1, side="B", price_raw=1001,
            recv_ns=5_000, book_view=self.book.view,
        )
        row = self.calc.on_terminal(instrument_id=42, order_id=1, status=FILLED, recv_ns=6_000)
        first, second = row["episodes"]
        self.assertEqual(first["fills_ahead"], 1)
        self.assertEqual(first["queue_movement"], 1)
        self.assertEqual(second["fills_ahead"], 0)

    def test_own_fills_and_modifies_are_counted(self) -> None:
        self.book.rest("B", 1000, 1, 5)
        self.calc.on_add(**add_kwargs(), book_view=self.book.view)
        self.calc.on_own_fill(instrument_id=42, order_id=1, size=2)
        self.calc.on_own_fill(instrument_id=42, order_id=1, size=1)
        self.calc.on_modify_retaining_priority(instrument_id=42, order_id=1)
        row = self.calc.on_terminal(instrument_id=42, order_id=1, status=FILLED, recv_ns=8_000)
        self.assertEqual(row["own_fill_count"], 2)
        self.assertEqual(row["own_fill_size"], 3)
        self.assertEqual(row["modify_count"], 1)

    def test_events_for_unknown_orders_are_counted_not_raised(self) -> None:
        self.calc.on_own_fill(instrument_id=42, order_id=999, size=1)
        self.calc.observe_level(instrument_id=42, order_id=999, orders_ahead=0, volume_ahead=0)
        self.assertIsNone(self.calc.on_terminal(instrument_id=42, order_id=999, status=FILLED, recv_ns=1))
        self.assertEqual(self.calc.unknown_order_events, 3)

    def test_level_fill_counter_accumulates_per_level(self) -> None:
        self.assertEqual(self.calc.note_level_fill(instrument_id=42, side="B", price_raw=1000), 1)
        self.assertEqual(self.calc.note_level_fill(instrument_id=42, side="B", price_raw=1000), 2)
        self.assertEqual(self.calc.note_level_fill(instrument_id=42, side="A", price_raw=1000), 1)

    def test_identity_violations_surface_in_the_summary(self) -> None:
        self.book.rest("B", 1000, 1, 3)
        self.calc.on_add(**add_kwargs(), book_view=self.book.view)
        self.calc.observe_level(instrument_id=42, order_id=1, orders_ahead=7, volume_ahead=70)
        self.assertEqual(self.calc.summary()["fifo_identity_violations"], 1)

    def test_days_and_sides_do_not_pool(self) -> None:
        for order_id, day, side in ((1, "20211004", "B"), (2, "20211005", "B"), (3, "20211004", "A")):
            self.book.rest(side, 1000, order_id, 3)
            self.calc.on_add(
                **add_kwargs(order_id=order_id, source_day=day, side=side), book_view=self.book.view
            )
            self.calc.on_terminal(instrument_id=42, order_id=order_id, status=FILLED, recv_ns=2_000)
        self.assertEqual(self.calc.resolved_lifetime.stratum_count, 3)

    def test_open_state_is_bounded_by_the_book_not_the_stream(self) -> None:
        for order_id in range(1, 501):
            self.book.rest("B", 1000, order_id, 1)
            self.calc.on_add(**add_kwargs(order_id=order_id), book_view=self.book.view)
            self.calc.on_terminal(instrument_id=42, order_id=order_id, status=FILLED, recv_ns=2_000)
        self.assertEqual(self.calc.open_order_count, 0)
        self.assertEqual(self.calc.completed, 500)

    def test_summary_reports_the_censoring_split(self) -> None:
        self.book.rest("B", 1000, 1, 3)
        self.calc.on_add(**add_kwargs(), book_view=self.book.view)
        self.calc.finalize(recv_ns=9_000)
        summary = self.calc.summary()
        self.assertEqual(summary["section"], "4.6")
        self.assertEqual(summary["censored"], 1)
        self.assertEqual(summary["resolved"], 0)
        self.assertEqual(summary["still_open"], 0)


if __name__ == "__main__":
    unittest.main()
