"""Tests for section 4.7's observation half.

These pin the CONSTRUCTION choices, not just that the code runs. Every one of them could have
been made differently, and a silent change to any would re-cut a 4.7 stratum or re-scale a
restoration without failing anything - the defect shape this tree keeps meeting (S108
off-instrument, S109 `session_b_share`, the 2026-08-29 `_family_id` split).

The three that carry the most weight, because the contract does not decide them:

* the tick neighbourhood is ONE tick, derived from two already-committed sources and carried on
  every emitted value;
* a refill may never restore the removal made by its own row;
* new-ID adds and same-ID modifies are classified on observed residency and never merged.
"""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark import native_group_adapters as ga
from research.kalshi.frankie_raw_mbo_benchmark import native_replenishment_adapter as ra
from research.kalshi.frankie_raw_mbo_benchmark import native_rt_book as rt
from research.kalshi.frankie_raw_mbo_benchmark.native_replenishment import (
    CENSORED_STREAM_END,
    NEIGHBORING_PRICE,
    NEVER_RESTORED,
    NEW_LIQUIDITY,
    RESHAPED_RESIDUAL,
    RESTORED,
    SAME_PRICE,
    ReplenishmentCalculator,
)
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import F_TOB, PRICE_SCALE

TICK = ra.TICK_RAW_NG
P0 = 3_000_000_000          # 3.000, a real NG price on the raw scale
P_DOWN1 = P0 - TICK         # one tick below: the neighbour
P_DOWN2 = P0 - 2 * TICK     # two ticks below: NOT a neighbour
HORIZON = 1_000_000_000     # one second, in ns


def ctx(**over):
    base = dict(
        group_index=0,
        source_day="20211004",
        source_role="SCORED_FINDINGS_DAY",
        continuity_segment=18901,
        session_phase="RTH",
        family_id="ow-abc",
        side_orientation="B",
        event_ns=90,
        recv_ns=1_000,
        instrument_id=42,
    )
    base.update(over)
    return ga.GroupContext(**base)


def row(action, side, order_id, price, size, recv, **extra):
    out = {
        "action": action,
        "side": side,
        "order_id": order_id,
        "price_raw": price,
        "size": size,
        "ts_recv_ns": recv,
        "ts_event_ns": recv - 10,
    }
    out.update(extra)
    return out


def calc(**over):
    kwargs = {"horizon_ns": HORIZON}
    kwargs.update(over)
    return ReplenishmentCalculator(**kwargs)


def observe(observer, groups, calculator):
    """Feed several groups in tape order, returning every row the observer handed back."""
    rows = []
    for index, actions in enumerate(groups):
        rows.extend(
            observer.observe_group(
                actions,
                ctx(group_index=index, recv_ns=actions[-1]["ts_recv_ns"]),
                calculator=calculator,
            )
        )
    return rows


# The book this module measures against: two bid levels, the touch at P0.
SEEDED = [
    row("A", "B", 1, P0, 5, 100),
    row("A", "B", 2, P_DOWN1, 4, 110),
]


class GuardTests(unittest.TestCase):
    def test_an_empty_group_is_refused(self):
        with self.assertRaises(ra.ReplenishmentAdapterError):
            ra.level_observations([], ctx(), replay=ra.InstrumentReplay())

    def test_a_nonpositive_tick_is_refused_at_both_entry_points(self):
        with self.assertRaises(ra.ReplenishmentAdapterError):
            ra.ReplenishmentObserver(tick_raw=0)
        with self.assertRaises(ra.ReplenishmentAdapterError):
            ra.level_observations(SEEDED, ctx(), replay=ra.InstrumentReplay(), tick_raw=-1)

    def test_a_negative_neighbourhood_is_refused(self):
        with self.assertRaises(ra.ReplenishmentAdapterError):
            ra.ReplenishmentObserver(neighbourhood_ticks=-1)

    def test_a_negative_size_is_refused_loudly_and_never_clamped(self):
        # max(0, size) would turn a malformed row into a silent zero - present, typed, in range
        # and wrong. `ReplayBook` refuses, and this module does not soften it into a
        # ReplenishmentAdapterError, because re-labelling hides which layer said no.
        with self.assertRaises(rt.RtBookError):
            ra.level_observations(
                [row("A", "B", 1, P0, -1, 100)], ctx(), replay=ra.InstrumentReplay()
            )

    def test_a_malformed_price_is_refused_rather_than_defaulted_into_a_level(self):
        # Never defaulted into the sentinel, which would silently move the row to "no price".
        with self.assertRaises(ra.ReplenishmentAdapterError):
            ra.level_observations(
                [row("A", "B", 1, "three thousand", 5, 100)],
                ctx(),
                replay=ra.InstrumentReplay(),
            )


class TickNeighbourhoodTests(unittest.TestCase):
    """THE declared choice. It is derived, it is one tick, and it travels on the value."""

    def test_the_tick_is_derived_from_the_two_committed_sources_not_invented(self):
        # research/ng_dipole_runway_audit.py commits TICK = 0.001; the v4 state adapter commits
        # PRICE_SCALE = 1_000_000_000 as the scale price_raw is expressed in.
        self.assertEqual(ra.TICK_DECIMAL_NG, 0.001)
        self.assertEqual(ra.TICK_RAW_NG, round(ra.TICK_DECIMAL_NG * PRICE_SCALE))
        self.assertEqual(ra.TICK_RAW_NG, 1_000_000)

    def test_the_neighbourhood_is_exactly_one_adjacent_level(self):
        # Any wider number is a bar sited at a value. One tick is the smallest price
        # distinction the venue permits, so it is the only width nobody has to choose.
        self.assertEqual(ra.NEIGHBOURHOOD_TICKS, 1)

    def test_the_choice_travels_on_every_emitted_observation(self):
        # S114: a caveat that lives only in a docstring is a caveat that expires.
        group = ra.level_observations(SEEDED, ctx(), replay=ra.InstrumentReplay())
        self.assertTrue(group.observations)
        for observation in group.observations:
            emitted = observation.as_dict()
            self.assertEqual(emitted["tick_raw"], TICK)
            self.assertEqual(emitted["neighbourhood_ticks"], 1)
            self.assertEqual(
                emitted["price_relation_basis"],
                "ADJACENT_LEVEL|tick_raw=1000000|neighbourhood_ticks=1",
            )

    def test_the_basis_string_cannot_drift_from_the_values_it_names(self):
        wide = ra.ReplenishmentObserver(tick_raw=25, neighbourhood_ticks=3)
        self.assertEqual(
            wide.summary()["price_relation_basis"],
            "ADJACENT_LEVEL|tick_raw=25|neighbourhood_ticks=3",
        )

    def test_same_price_and_one_tick_away_are_the_only_two_relations(self):
        group = ra.level_observations(SEEDED, ctx(), replay=ra.InstrumentReplay())
        add_at_p0 = next(o for o in group.observations if o.price_raw == P0)
        self.assertEqual(add_at_p0.price_relation_to(P0), (SAME_PRICE, 0))
        self.assertEqual(add_at_p0.price_relation_to(P_DOWN1), (NEIGHBORING_PRICE, -1))
        self.assertEqual(add_at_p0.price_relation_to(P0 + TICK), (NEIGHBORING_PRICE, 1))
        self.assertIsNone(add_at_p0.price_relation_to(P_DOWN2))

    def test_a_refill_beyond_the_neighbourhood_is_counted_not_folded_in(self):
        # An add two ticks away is a true fact about a DIFFERENT level. Calling it
        # replenishment of this one would be an invention; ignoring it would be a silent drop.
        observer = ra.ReplenishmentObserver()
        c = calc()
        rows = observe(
            observer,
            [SEEDED, [row("C", "B", 1, P0, 5, 200)], [row("A", "B", 9, P_DOWN2, 7, 300)]],
            c,
        )
        far = next(r for r in rows if r["observation"] == ra.REFILL and r["recv_ns"] == 300)
        self.assertEqual(far["attributed_to_episode_ids"], [])
        self.assertEqual(far["quantity"], 7)
        self.assertEqual(
            far["unattributed_reason"], ra.NO_PENDING_EPISODE_IN_NEIGHBOURHOOD
        )
        emitted = c.advance(200 + HORIZON)[0]
        self.assertEqual(emitted["outcome"], NEVER_RESTORED)
        self.assertEqual(emitted["replaced_quantity"], 0)

    def test_an_ordinary_unprompted_add_is_not_filed_as_an_anomaly(self):
        # `refill_quantity_unattributed` is reserved for the two DEFECT shapes - an undefined
        # price and an out-of-order timestamp. If ordinary adds landed there it would tally the
        # whole tape and stop being a signal.
        observer = ra.ReplenishmentObserver()
        observe(observer, [SEEDED], calc())
        self.assertEqual(observer.integrity["refill_with_no_pending_episode"], 2)
        self.assertEqual(observer.integrity["refill_quantity_no_pending_episode"], 9)
        self.assertNotIn("refill_quantity_unattributed", observer.integrity)

    def test_a_refill_one_tick_away_is_neighbouring_and_carries_a_signed_offset(self):
        observer = ra.ReplenishmentObserver()
        c = calc()
        rows = observe(
            observer,
            [SEEDED, [row("C", "B", 1, P0, 5, 200)], [row("A", "B", 9, P_DOWN1, 7, 300)]],
            c,
        )
        refill = next(r for r in rows if r["observation"] == ra.REFILL and r["recv_ns"] == 300)
        self.assertEqual(refill["price_relations"], [NEIGHBORING_PRICE])
        self.assertEqual(refill["neighbour_offset_ticks"], [1])
        emitted = c.advance(200 + HORIZON)[0]
        self.assertEqual(emitted["neighboring_price_refill_quantity"], 7)
        self.assertEqual(emitted["same_price_refill_quantity"], 0)


class RemovalObservationTests(unittest.TestCase):
    def test_a_cancel_is_a_removal_carrying_the_depth_it_ate_into(self):
        replay = ra.InstrumentReplay()
        ra.level_observations(SEEDED, ctx(), replay=replay)
        group = ra.level_observations([row("C", "B", 1, P0, 5, 200)], ctx(), replay=replay)
        (removal,) = group.observations
        self.assertEqual(removal.kind, ra.REMOVAL)
        self.assertEqual(removal.quantity, 5)
        self.assertEqual(removal.depth_before, 5)
        self.assertEqual(removal.depth_after, 0)
        self.assertEqual(removal.order_count_delta, -1)
        self.assertEqual(removal.touch_state, ra.AT_TOUCH)

    def test_a_partial_cancel_removes_quantity_but_no_order(self):
        replay = ra.InstrumentReplay()
        ra.level_observations(SEEDED, ctx(), replay=replay)
        group = ra.level_observations([row("C", "B", 1, P0, 2, 200)], ctx(), replay=replay)
        (removal,) = group.observations
        self.assertEqual(removal.quantity, 2)
        self.assertEqual(removal.order_count_delta, 0, "a survivor never leaves the level")

    def test_a_removal_uses_the_book_side_never_the_group_orientation(self):
        # ctx.side_orientation is "MIXED" for any group touching both sides. Keying an episode
        # on it would pool a bid level and an ask level into one stratum at construction time,
        # where no later check could see it.
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(
            observer,
            [
                [row("A", "B", 1, P0, 5, 100), row("A", "A", 2, P0 + 5 * TICK, 4, 110)],
                [row("C", "B", 1, P0, 5, 200), row("C", "A", 2, P0 + 5 * TICK, 4, 210)],
            ],
            c,
        )
        sides = {e.side for e in c.pending_at(42, "B", P0)} | {
            e.side for e in c.pending_at(42, "A", P0 + 5 * TICK)
        }
        self.assertEqual(sides, {"B", "A"})

    def test_the_deeper_level_is_behind_the_touch_and_strata_stay_apart(self):
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(observer, [SEEDED, [row("C", "B", 2, P_DOWN1, 4, 200)], ], c)
        (episode,) = c.pending_at(42, "B", P_DOWN1)
        self.assertEqual(episode.touch_state_at_open, ra.BEHIND_TOUCH)
        c.advance(200 + HORIZON)
        subfamilies = {r["stratum"]["subfamily_id"] for r in c.removed_quantity.rows()}
        self.assertEqual(subfamilies, {"touch=BEHIND_TOUCH"})

    def test_a_removal_while_an_episode_is_still_pending_is_recorded_as_persistence(self):
        # 4.7 names persistence. The calculator has no ingest for a second removal inside an
        # open episode, so the fact is carried on the observation row rather than lost.
        observer = ra.ReplenishmentObserver()
        c = calc()
        rows = observe(
            observer,
            [
                [row("A", "B", 1, P0, 5, 100), row("A", "B", 3, P0, 6, 110)],
                [row("C", "B", 1, P0, 5, 200)],
                [row("C", "B", 3, P0, 6, 300)],
            ],
            c,
        )
        second = [r for r in rows if r.get("removal_during_pending_episode")]
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0]["recv_ns"], 300)
        self.assertEqual(observer.integrity["removal_during_pending_episode"], 1)


class NewIdVersusSameIdTests(unittest.TestCase):
    """New liquidity and reshaped residual are DIFFERENT FACTS and are never merged."""

    def _refill(self, tail, seed=SEEDED):
        replay = ra.InstrumentReplay()
        ra.level_observations(seed, ctx(), replay=replay)
        group = ra.level_observations(tail, ctx(), replay=replay)
        return [o for o in group.observations if o.kind == ra.REFILL]

    def test_an_unseen_order_id_adding_is_new_liquidity(self):
        (refill,) = self._refill([row("A", "B", 9, P0, 3, 200)])
        self.assertEqual(refill.liquidity_kind, NEW_LIQUIDITY)
        self.assertEqual(refill.liquidity_kind_basis, ra.NOT_RESIDENT)

    def test_a_resting_order_growing_is_a_reshaped_residual(self):
        (refill,) = self._refill([row("M", "B", 1, P0, 9, 200)])
        self.assertEqual(refill.liquidity_kind, RESHAPED_RESIDUAL)
        self.assertEqual(refill.liquidity_kind_basis, ra.RESIDENT)

    def test_a_modify_for_an_order_this_book_never_had_declares_its_ambiguity(self):
        # `InstrumentBook` treats it as an add and a window opening mid-stream sees these
        # constantly. There is no residual to reshape, so it is new liquidity - but the basis
        # says how that was decided rather than presenting it as a clean observation.
        (refill,) = self._refill([row("M", "B", 77, P0, 3, 200)])
        self.assertEqual(refill.liquidity_kind, NEW_LIQUIDITY)
        self.assertEqual(refill.liquidity_kind_basis, ra.MODIFY_MISSING)

    def test_an_order_id_of_zero_is_still_measured_but_flagged_as_unidentified(self):
        # `normalize` coerces a missing id to 0 and both books rest it as a real order, so every
        # anonymous order shares one key. The QUANTITY is kept - dropping it would under-count
        # replenishment - and the classification is marked not load-bearing.
        (refill,) = self._refill([row("A", "B", 0, P0, 3, 200)])
        self.assertEqual(refill.liquidity_kind_basis, ra.UNIDENTIFIED)
        self.assertEqual(refill.quantity, 3)

    def test_the_calculator_keeps_the_two_in_separate_fields(self):
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(
            observer,
            [
                SEEDED,
                [row("C", "B", 1, P0, 5, 200)],
                [row("A", "B", 9, P0, 4, 300)],       # new liquidity
                [row("M", "B", 9, P0, 7, 400)],       # the same order reshaped: +3
            ],
            c,
        )
        emitted = c.advance(200 + HORIZON)[0]
        self.assertEqual(emitted["new_id_add_quantity"], 4)
        self.assertEqual(emitted["same_id_modify_quantity"], 3)
        self.assertEqual(emitted["new_id_add_count"], 1)
        self.assertEqual(emitted["same_id_modify_count"], 1)
        self.assertEqual(emitted["replaced_quantity"], 7)


class SelfRestorationTests(unittest.TestCase):
    """A row may never restore the removal it just made."""

    def test_a_modify_walking_one_tick_does_not_answer_its_own_removal(self):
        # The order RETREATED from P0 to P_DOWN1. Attributing the arrival at P_DOWN1 to the
        # episode the same row opened at P0 would report the level instantly restored - the
        # most plausible-looking wrong number this module could produce.
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(observer, [SEEDED, [row("M", "B", 1, P_DOWN1, 5, 200)]], c)
        (episode,) = c.pending_at(42, "B", P0)
        self.assertEqual(episode.replaced_quantity, 0)
        self.assertIsNone(episode.first_restoration_recv_ns)
        emitted = c.advance(200 + HORIZON)
        outcomes = {e["price_raw"]: e["outcome"] for e in emitted}
        self.assertEqual(outcomes[P0], NEVER_RESTORED)

    def test_the_next_row_of_the_same_group_does_answer_it(self):
        # The rule is about one ROW, not about one group: replenishment inside a group is real.
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(
            observer,
            [SEEDED, [row("C", "B", 1, P0, 5, 200), row("A", "B", 9, P0, 5, 210)]],
            c,
        )
        emitted = c.advance(200 + HORIZON)[0]
        self.assertEqual(emitted["outcome"], RESTORED)
        self.assertEqual(emitted["time_to_restoration_ns"], 10)

    def test_the_policy_is_declared_on_the_value(self):
        observer = ra.ReplenishmentObserver()
        self.assertEqual(observer.summary()["self_restoration_policy"], "REFUSED_WITHIN_THE_SAME_ROW")


class SharedAttributionTests(unittest.TestCase):
    def test_two_pending_episodes_at_one_level_share_a_refill_and_say_so(self):
        # The alternative was a FIFO allocation, rejected because it makes an episode's answer
        # depend on episodes it has nothing to do with AND makes overshoot unobservable. The
        # cost is declared rather than hidden: the SUM across overlapping episodes exceeds what
        # arrived, so the episode is the unit, not the sum.
        observer = ra.ReplenishmentObserver()
        c = calc()
        rows = observe(
            observer,
            [
                [row("A", "B", 1, P0, 5, 100), row("A", "B", 2, P0, 6, 110)],
                [row("C", "B", 1, P0, 5, 200)],
                [row("C", "B", 2, P0, 6, 300)],
                [row("A", "B", 9, P0, 4, 400)],
            ],
            c,
        )
        refill = next(r for r in rows if r["observation"] == ra.REFILL and r["recv_ns"] == 400)
        self.assertEqual(len(refill["attributed_to_episode_ids"]), 2)
        self.assertEqual(refill["shared_with_episode_count"], 1)
        self.assertEqual(refill["refill_attribution"], "EVERY_PENDING_EPISODE_IN_NEIGHBOURHOOD")
        for episode in list(c.pending_at(42, "B", P0)):
            self.assertEqual(episode.replaced_quantity, 4)


class OvershootTests(unittest.TestCase):
    def test_more_coming_back_than_left_is_an_overshoot(self):
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(
            observer,
            [SEEDED, [row("C", "B", 1, P0, 5, 200)], [row("A", "B", 9, P0, 8, 300)]],
            c,
        )
        emitted = c.advance(200 + HORIZON)[0]
        self.assertEqual(emitted["removed_quantity"], 5)
        self.assertEqual(emitted["overshoot_quantity"], 3)

    def test_no_overshoot_reports_zero_which_is_an_observation(self):
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(
            observer,
            [SEEDED, [row("C", "B", 1, P0, 5, 200)], [row("A", "B", 9, P0, 2, 300)]],
            c,
        )
        emitted = c.advance(200 + HORIZON)[0]
        self.assertEqual(emitted["overshoot_quantity"], 0)


class TouchRestorationTests(unittest.TestCase):
    def test_a_removal_that_empties_the_touch_arms_a_watch_and_a_refill_restores_it(self):
        observer = ra.ReplenishmentObserver()
        c = calc()
        rows = observe(
            observer,
            [SEEDED, [row("C", "B", 1, P0, 5, 200)], [row("A", "B", 9, P0, 5, 300)]],
            c,
        )
        removal = next(r for r in rows if r["observation"] == ra.REMOVAL)
        self.assertEqual(removal["touch_disposition"], ra.TOUCH_DISPLACED)
        emitted = c.advance(200 + HORIZON)[0]
        self.assertEqual(emitted["touch_restoration_ns"], 100)
        self.assertEqual(observer.touch_restorations, 1)

    def test_a_deep_removal_never_displaced_the_touch_and_no_restoration_is_fabricated(self):
        # The conflation this guards: `touch_restoration_ns = None` means BOTH "displaced and
        # never came back" and "never left". Calling restore_touch on the next add would report
        # a restoration that had no displacement, which reads as a fast, healthy book.
        observer = ra.ReplenishmentObserver()
        c = calc()
        rows = observe(
            observer,
            [SEEDED, [row("C", "B", 2, P_DOWN1, 4, 200)], [row("A", "B", 9, P_DOWN1, 4, 300)]],
            c,
        )
        removal = next(r for r in rows if r["observation"] == ra.REMOVAL)
        self.assertEqual(removal["touch_disposition"], ra.TOUCH_NEVER_DISPLACED)
        emitted = c.advance(200 + HORIZON)[0]
        self.assertIsNone(emitted["touch_restoration_ns"])
        self.assertEqual(emitted["outcome"], RESTORED, "the QUANTITY came back; the touch never left")

    def test_the_disposition_and_the_calculator_row_join_on_episode_id(self):
        # The residual conflation cannot be fixed from outside the calculator, so it is closed
        # by a join key that both sides already emit.
        observer = ra.ReplenishmentObserver()
        c = calc()
        rows = observe(observer, [SEEDED, [row("C", "B", 1, P0, 5, 200)]], c)
        removal = next(r for r in rows if r["observation"] == ra.REMOVAL)
        emitted = c.advance(200 + HORIZON)[0]
        self.assertEqual(removal["episode_id"], emitted["episode_id"])
        self.assertIn("touch_disposition", removal)

    def test_a_touch_restoration_is_the_first_one_never_the_latest(self):
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(
            observer,
            [
                SEEDED,
                [row("C", "B", 1, P0, 5, 200)],
                [row("A", "B", 9, P0, 1, 300)],
                [row("A", "B", 10, P0, 4, 400)],
            ],
            c,
        )
        emitted = c.advance(200 + HORIZON)[0]
        self.assertEqual(emitted["touch_restoration_ns"], 100)


class NoLookaheadTests(unittest.TestCase):
    def test_a_restoration_is_never_known_before_stream_time_reaches_the_horizon(self):
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(observer, [SEEDED, [row("C", "B", 1, P0, 5, 200)]], c)
        self.assertEqual(c.advance(200 + HORIZON - 1), [], "the outcome is not available yet")
        self.assertEqual(c.pending_count, 1)

    def test_never_restored_stays_distinct_from_not_yet_observed(self):
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(observer, [SEEDED, [row("C", "B", 1, P0, 5, 200)]], c)
        resolved = c.advance(200 + HORIZON)
        # A second removal whose horizon has not elapsed when the stream ends.
        observe(
            observer,
            [
                [row("A", "B", 8, P0, 5, 10 * HORIZON)],
                [row("C", "B", 8, P0, 5, 10 * HORIZON + 1)],
            ],
            c,
        )
        censored = c.finalize(recv_ns=10 * HORIZON + 2)
        self.assertEqual(resolved[0]["outcome"], NEVER_RESTORED)
        self.assertTrue(resolved[0]["resolved"])
        self.assertEqual(censored[0]["outcome"], CENSORED_STREAM_END)
        self.assertTrue(censored[0]["censored"])
        self.assertFalse(censored[0]["resolved"])

    def test_maturation_is_the_calculators_job_and_the_traversal_must_keep_calling_advance(self):
        """The one thing this half CANNOT enforce, pinned so a wiring pass sees it.

        `native_replay_driver` calls `run.replenishment.advance(recv_ns)` at every group close,
        which is what bounds the pending set to the horizon. Nothing in the observation half
        can do that - it never decides an outcome - so an episode whose horizon elapsed long
        ago still absorbs a refill if `advance` was never called. That is a property of the
        wiring, not a defect here, and it is the reason the driver's existing call site is
        load-bearing rather than incidental.
        """
        observer = ra.ReplenishmentObserver()
        stale = calc()
        observe(
            observer,
            [SEEDED, [row("C", "B", 1, P0, 5, 200)], [row("A", "B", 9, P0, 5, 50 * HORIZON)]],
            stale,
        )
        self.assertEqual(stale.advance(60 * HORIZON)[0]["outcome"], RESTORED)

        matured = calc()
        observer2 = ra.ReplenishmentObserver()
        observer2.observe_group(SEEDED, ctx(recv_ns=110), calculator=matured)
        observer2.observe_group(
            [row("C", "B", 1, P0, 5, 200)], ctx(recv_ns=200), calculator=matured
        )
        emitted = matured.advance(200 + HORIZON)
        observer2.observe_group(
            [row("A", "B", 9, P0, 5, 50 * HORIZON)],
            ctx(recv_ns=50 * HORIZON),
            calculator=matured,
        )
        self.assertEqual(emitted[0]["outcome"], NEVER_RESTORED)

    def test_the_first_restoration_time_is_the_first_refill_not_a_later_one(self):
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(
            observer,
            [
                SEEDED,
                [row("C", "B", 1, P0, 5, 200)],
                [row("A", "B", 9, P0, 1, 250)],
                [row("A", "B", 10, P0, 4, 700)],
            ],
            c,
        )
        emitted = c.advance(200 + HORIZON)[0]
        self.assertEqual(emitted["time_to_restoration_ns"], 50)

    def test_a_refill_that_precedes_its_episode_is_counted_never_clamped_into_range(self):
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(observer, [SEEDED, [row("C", "B", 1, P0, 5, 500)]], c)
        # An out-of-order feed: this add carries a timestamp BEFORE the removal it would answer.
        observe(observer, [[row("A", "B", 9, P0, 5, 400)]], c)
        (episode,) = c.pending_at(42, "B", P0)
        self.assertEqual(episode.replaced_quantity, 0)
        self.assertEqual(observer.integrity["refill_precedes_episode_open"], 1)
        self.assertEqual(observer.integrity["refill_quantity_unattributed"], 5)
        self.assertEqual(observer.integrity["refill_with_no_pending_episode"], 2, "the two seed adds")


class RefusedRowTests(unittest.TestCase):
    """Three classes open no episode. Each is refused for a stated reason and counted."""

    def test_a_removal_at_the_undefined_price_sentinel_opens_no_episode(self):
        # A sentinel is the feed declining to state a price. An episode keyed on it could never
        # be matched by a refill at a real price, so every one would report NEVER_RESTORED - a
        # manufactured result rather than a measurement.
        observer = ra.ReplenishmentObserver()
        c = calc()
        rows = observe(
            observer,
            [
                [row("A", "B", 1, rt.PRICE_SENTINEL_ABS, 5, 100)],
                [row("C", "B", 1, rt.PRICE_SENTINEL_ABS, 5, 200)],
            ],
            c,
        )
        removal = next(r for r in rows if r["observation"] == ra.REMOVAL)
        self.assertIsNone(removal["episode_id"])
        self.assertEqual(removal["refused_reason"], ra.REFUSED_SENTINEL_PRICE)
        self.assertEqual(c.opened, 0)
        self.assertEqual(observer.integrity["removal_at_undefined_price_not_opened"], 1)
        self.assertEqual(observer.integrity["removal_quantity_not_opened"], 5)

    def test_a_top_of_book_side_wipe_reports_the_quantity_it_cleared(self):
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(
            observer,
            [
                SEEDED,
                [row("A", "B", 99, rt.PRICE_SENTINEL_ABS, 0, 200, flags=F_TOB)],
            ],
            c,
        )
        self.assertEqual(observer.integrity["tob_wipe_rows"], 1)
        self.assertEqual(observer.integrity["tob_wipe_quantity_cleared"], 9)
        self.assertEqual(c.opened, 0, "a feed normalization is not a participant removal")

    def test_a_reset_reports_what_it_cleared_on_both_sides(self):
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(
            observer,
            [
                [row("A", "B", 1, P0, 5, 100), row("A", "A", 2, P0 + 5 * TICK, 4, 110)],
                [row("R", "N", 0, P0, 0, 200)],
            ],
            c,
        )
        self.assertEqual(observer.integrity["reset_rows"], 1)
        self.assertEqual(observer.integrity["reset_quantity_cleared"], 9)
        self.assertEqual(c.opened, 0)

    def test_the_cleared_quantity_declares_that_it_is_derived(self):
        # `ReplayBook` exposes no level enumeration, so a whole-side clear cannot be READ out of
        # it. The tally is derived from the deltas this module already measured, and its basis
        # is on the value so it can never be mistaken for a book measurement.
        observer = ra.ReplenishmentObserver()
        self.assertEqual(
            observer.summary()["cleared_quantity_basis"], "DERIVED_FROM_OBSERVED_LEVEL_DELTAS"
        )

    def test_the_derived_tally_agrees_with_the_book_it_was_derived_from(self):
        replay = ra.InstrumentReplay()
        stream = [
            row("A", "B", 1, P0, 5, 100),
            row("A", "B", 2, P_DOWN1, 4, 110),
            row("C", "B", 1, P0, 2, 120),
            row("M", "B", 2, P_DOWN2, 9, 130),
            row("A", "A", 3, P0 + 5 * TICK, 6, 140),
            row("F", "B", 2, P_DOWN2, 3, 150),
        ]
        ra.level_observations(stream, ctx(), replay=replay)
        for side, prices in ((("B"), (P0, P_DOWN1, P_DOWN2)), (("A"), (P0 + 5 * TICK,))):
            actual = sum(replay.book.level(side, price)[1] for price in prices)
            self.assertEqual(replay.displayed_volume[side], actual)


class SegmentBoundaryTests(unittest.TestCase):
    def test_the_book_is_discarded_at_a_boundary_and_says_what_it_was_carrying(self):
        # Section 2 forbids a calculation crossing a reset, snapshot, gap or session boundary,
        # and a book built before a gap describes liquidity nobody can vouch for after it.
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(observer, [SEEDED, [row("C", "B", 1, P0, 5, 200)]], c)
        rows = observer.close_continuity_segment(segment=18901, recv_ns=300)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["displayed_volume_discarded"], {"B": 4, "A": 0})
        self.assertEqual(rows[0]["displayed_volume_basis"], "DERIVED_FROM_OBSERVED_LEVEL_DELTAS")
        self.assertEqual(rows[0]["touch_watches_abandoned"], 1)
        self.assertEqual(observer.summary()["instruments"], 0)

    def test_a_retired_books_integrity_counters_survive_the_boundary(self):
        # Dropping them at a segment close would be the same silent loss D60 was written for,
        # only spread across every boundary in the run.
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(observer, [[row("C", "B", 404, P0, 5, 100)]], c)
        self.assertEqual(observer.summary()["replay_book_integrity"]["cancel_missing_order"], 1)
        observer.close_continuity_segment(segment=18901, recv_ns=200)
        self.assertEqual(observer.summary()["replay_book_integrity"]["cancel_missing_order"], 1)

    def test_instruments_never_share_a_book(self):
        observer = ra.ReplenishmentObserver()
        self.assertIsNot(observer.replay_for(1).book, observer.replay_for(2).book)
        self.assertIs(observer.replay_for(1), observer.replay_for(1))


class AccountingTests(unittest.TestCase):
    """D60: every row is used, retained and counted, or refused loudly. Never ignored."""

    def test_every_row_of_a_group_leaves_a_trace(self):
        observer = ra.ReplenishmentObserver()
        c = calc()
        rows = observe(
            observer,
            [
                [
                    row("A", "B", 1, P0, 5, 100),     # a refill
                    row("T", "A", 0, P0, 2, 110),     # non-mutating in this feed
                    row("F", "B", 1, P0, 2, 120),     # non-mutating in this feed
                    row("C", "B", 404, P0, 1, 130),   # a cancel for an order that never rested
                    row("A", "N", 5, P0, 3, 140),     # the tape declining to state a side
                ]
            ],
            c,
        )
        summary = observer.summary()
        self.assertEqual(len(rows), 1, "only the add moved a level")
        self.assertEqual(summary["replay_book_integrity"]["non_mutating_T"], 1)
        self.assertEqual(summary["replay_book_integrity"]["non_mutating_F"], 1)
        self.assertEqual(summary["replay_book_integrity"]["cancel_missing_order"], 1)
        self.assertEqual(summary["replay_book_integrity"]["add_invalid_side"], 1)
        self.assertEqual(summary["integrity"]["mutating_row_touched_no_level"], 2)

    def test_a_mutation_that_changed_nothing_is_still_counted(self):
        replay = ra.InstrumentReplay()
        ra.level_observations(SEEDED, ctx(), replay=replay)
        group = ra.level_observations([row("M", "B", 1, P0, 5, 200)], ctx(), replay=replay)
        self.assertEqual(group.observations, [])
        self.assertEqual(group.integrity["level_unchanged_by_mutation"], 1)

    def test_a_defaulted_causal_timestamp_is_counted_as_defaulted(self):
        actions = [{"action": "A", "side": "B", "order_id": 1, "price_raw": P0, "size": 5}]
        group = ra.level_observations(actions, ctx(recv_ns=777), replay=ra.InstrumentReplay())
        self.assertEqual(group.observations[0].recv_ns, 777)
        self.assertEqual(group.integrity["row_recv_ns_defaulted_to_group_close"], 1)


class NoAveragingTests(unittest.TestCase):
    def test_the_summary_reports_counts_and_never_a_statistic(self):
        # The no-average rule, at construction time. The calculator owns every stratified
        # measure; this half hands it exact integers and nothing else.
        observer = ra.ReplenishmentObserver()
        summary = observer.summary()
        banned = {"mean", "avg", "average", "ratio", "rate", "share", "pct", "per"}
        for key in summary:
            # Split on the separator rather than substring-matching: "restorations" contains
            # "ratio", and a check that fires on that is a check nobody will keep.
            self.assertFalse(
                banned & set(key.lower().split("_")), f"{key} looks like a statistic"
            )

    def test_every_emitted_quantity_is_an_integer(self):
        group = ra.level_observations(SEEDED, ctx(), replay=ra.InstrumentReplay())
        for observation in group.observations:
            emitted = observation.as_dict()
            for key in ("quantity", "order_count_delta", "depth_before", "depth_after"):
                self.assertIsInstance(emitted[key], int)
                self.assertNotIsInstance(emitted[key], bool)


class ImmutabilityTests(unittest.TestCase):
    def test_an_observation_cannot_be_edited_after_it_is_made(self):
        # The fact an episode and a stratum key are built from. A fact that can be edited after
        # the row it labelled was written is not a fact.
        group = ra.level_observations(SEEDED, ctx(), replay=ra.InstrumentReplay())
        with self.assertRaises(Exception):
            group.observations[0].quantity = 99


class RealCalculatorTests(unittest.TestCase):
    """The end-to-end shape: a real book, a real calculator, and the section's own output."""

    def test_a_removal_and_its_refill_survive_all_the_way_to_a_stratified_row(self):
        observer = ra.ReplenishmentObserver()
        c = calc()
        observe(
            observer,
            [SEEDED, [row("C", "B", 1, P0, 5, 200)], [row("A", "B", 9, P0, 5, 300)]],
            c,
        )
        emitted = c.advance(200 + HORIZON)[0]
        self.assertEqual(emitted["outcome"], RESTORED)
        self.assertEqual(emitted["same_price_refill_quantity"], 5)
        self.assertEqual(c.summary()["episodes_opened"], 1)
        self.assertEqual(c.removed_quantity.rows()[0]["stratum"]["source_day"], "20211004")
        self.assertEqual(observer.summary()["episodes_opened"], 1)

    def test_days_do_not_pool(self):
        observer = ra.ReplenishmentObserver()
        c = calc()
        for day in ("20211004", "20211005"):
            observer.observe_group(SEEDED, ctx(source_day=day), calculator=c)
            observer.observe_group(
                [row("C", "B", 1, P0, 5, 200)], ctx(source_day=day, recv_ns=200), calculator=c
            )
            observer.observe_group(
                [row("A", "B", 1, P0, 5, 210)], ctx(source_day=day, recv_ns=210), calculator=c
            )
        c.advance(200 + HORIZON)
        days = {r["stratum"]["source_day"] for r in c.removed_quantity.rows()}
        self.assertEqual(days, {"20211004", "20211005"})


if __name__ == "__main__":
    unittest.main()
