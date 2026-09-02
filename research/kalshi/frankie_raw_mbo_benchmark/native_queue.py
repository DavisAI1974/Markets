"""Section 4.6: queue position, priority, and order survival.

Streaming and forward-only. Order lifecycles are linked across groups but never across a
continuity boundary: section 2 says resets, snapshots, gaps and session boundaries start a
new segment and "no calculation crosses them". Here that is enforced by closing every open
lifecycle as censored when a segment ends, so a linked lifetime cannot silently span a gap
whose duration we never observed.

Two exact identities make the queue arithmetic self-checking rather than assumed:

  * At a fixed side and price, FIFO admits new orders only behind resting ones, so
    `orders_ahead` can never increase within one queue episode.
  * Every departure from ahead of us is either a fill or a cancel, giving
    `initial_orders_ahead - current_orders_ahead == fills_ahead + cancels_ahead`.

`cancels_ahead` is computed as that residual and the identity is asserted, so a
non-FIFO event shows up as a recorded violation instead of a plausible number.

Section 4.6 forbids an arithmetic mean for time-to-exit under censoring, so resolved
lifetimes feed a distribution and *all* exits - resolved and censored alike - feed a
Kaplan-Meier accumulator with at-risk counts at every time.

**D-13. Two units live here, and every measure now names the one it counts.** The section
measured orders and episodes under a single declared population, "resting orders within the
stratum and continuity segment". On run 33605852433 that read as one number twice:
`initial_volume_ahead` n = 20,005, `queue_movement` n = 24,645, same declared population.
They are different populations. A lifecycle is one order id inside one continuity segment;
a queue episode is one stretch of retained priority, and an order that loses priority twice
contributes one lifecycle and three episodes. So `initial_volume_ahead` counts BIRTHS,
`queue_movement` counts CLOSED EPISODES, and the lifetime measures count LIFECYCLES - each
said in its own declaration, because a population that is false is worse than one that is
missing: it invites exactly the pooling section 3 exists to forbid.

The 24,645 - 20,005 = 4,640 difference is the re-queue count, and it was reconcilable only
by differencing against a counter in another block entirely - the adapter's
`queue_observation`, where `modify_reprice` reads 4,625 - which left FIFTEEN observations
unattributed: fourteen reconcile to `priority_loss_not_visible_in_position` and the fifteenth
to nothing that was emitted anywhere. Two things close
that here. Every re-queued episode records WHY its level changed (`opened_basis`), counted
in `episode_accounting` by the transition the book itself shows - price, side, or neither -
so the residual class is reported rather than differenced out. And the opening queue
position of a re-queue, which was computed on every priority loss and entered no average at
all, is its own measure now (`requeue_initial_volume_ahead`), so the three n values
reconcile inside one section: births + re-queues - still-open = closed episodes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from research.kalshi.frankie_raw_mbo_benchmark.native_stratum import (
    CENSORED,
    RESOLVED,
    Declaration,
    StratifiedMeasure,
    StratumKey,
)

OPENED_AT_BIRTH = "BIRTH"
REOPENED_PRICE_CHANGED = "REQUEUE_PRICE_CHANGED"
REOPENED_SIDE_CHANGED = "REQUEUE_SIDE_CHANGED"
REOPENED_SAME_LEVEL = "REQUEUE_SAME_LEVEL"
# D-13. The three ways a priority loss can present in the book, kept apart because the
# fifteen unattributed observations on run 33605852433 sit in exactly this distinction. The
# arithmetic there: 4,625 `modify_reprice` + 14 `priority_loss_not_visible_in_position` =
# 4,639 of 4,640 re-queues, so fourteen are priority losses the book position never showed -
# a size increase re-queues at the order's own side and price - and the fifteenth is not
# attributable at all, because those two are the only cause counters the adapter's
# `queue_observation` block reported. A same-level re-queue is not a re-price, and having no
# place inside 4.6 to count one apart from the other is how the fifteen went missing.
REOPEN_BASES = (REOPENED_PRICE_CHANGED, REOPENED_SIDE_CHANGED, REOPENED_SAME_LEVEL)

# D-13. The two units, written once and used by the declarations that count in each. A
# lifecycle is one order id inside one continuity segment; an episode is one stretch of
# retained priority within it, so the two n values differ by construction and neither is
# the other's denominator.
LIFECYCLE_POPULATION = "tracked order lifecycles within the stratum and continuity segment"
EPISODE_POPULATION = "queue episodes within the stratum and continuity segment"

UNIT_LIFECYCLE = "ORDER_LIFECYCLE"
UNIT_BIRTH_EPISODE = "BIRTH_QUEUE_EPISODE"
UNIT_REQUEUE_EPISODE = "REQUEUED_QUEUE_EPISODE"
UNIT_CLOSED_EPISODE = "CLOSED_QUEUE_EPISODE"

FILLED = "FILLED"
CANCELLED = "CANCELLED"
OPEN_AT_SEGMENT_END = "OPEN_AT_SEGMENT_END"
OPEN_AT_STREAM_END = "OPEN_AT_STREAM_END"
TERMINAL_RESOLVED = frozenset({FILLED, CANCELLED})
TERMINAL_CENSORED = frozenset({OPEN_AT_SEGMENT_END, OPEN_AT_STREAM_END})

CAUSAL_CLOCK = "ts_recv_ns"

# Given (side, price_raw, order_id) -> (orders_ahead, volume_ahead).
BookView = Callable[[str, int, int], "tuple[int, int]"]


class QueueError(ValueError):
    """A queue lifecycle could not be tracked consistently."""


def _reopen_basis(closed: "QueueEpisode", *, side: str, price_raw: int) -> str:
    """Which move the book shows between the episode that closed and the one that opens.

    Side first, because a side change is the stronger statement and a re-priced order that
    also crossed sides would otherwise be filed as a plain re-price. Neither changing is a
    real and separate case - a size increase re-queues an order at its own side and price -
    and it is the case that went uncounted: fourteen of the fifteen unattributed observations
    on run 33605852433 reconcile to the adapter's `priority_loss_not_visible_in_position`,
    which is exactly this class, and the fifteenth is unattributable from what was emitted.
    """
    if side != closed.side:
        return REOPENED_SIDE_CHANGED
    if price_raw != closed.price_raw:
        return REOPENED_PRICE_CHANGED
    return REOPENED_SAME_LEVEL


@dataclass
class QueueEpisode:
    """One order resting at one side/price with priority retained throughout.

    A re-price or a size increase costs priority, which ends the episode and starts a new
    one. Keeping episodes separate is what makes `orders_ahead` monotone and the
    fills/cancels identity checkable; a single per-order record spanning a re-price would
    silently mix two different queues.
    """

    side: str
    price_raw: int
    opened_recv_ns: int
    initial_orders_ahead: int
    initial_volume_ahead: int
    current_orders_ahead: int
    current_volume_ahead: int
    # D-13. Why this episode exists, carried ON the episode rather than in prose. A birth and
    # a re-queue are different populations, and on the Sunday run the only record of which
    # was which lived in an adapter counter block that no measure of 4.6 could see.
    opened_basis: str = OPENED_AT_BIRTH
    fills_ahead: int = 0
    closed_recv_ns: int | None = None
    identity_violations: int = 0
    ahead_increase_violations: int = 0
    residual_negative_violations: int = 0

    @property
    def cancels_ahead(self) -> int:
        """Residual of the FIFO identity, floored at zero and counted when it breaks."""
        residual = (self.initial_orders_ahead - self.current_orders_ahead) - self.fills_ahead
        return max(residual, 0)

    @property
    def queue_movement(self) -> int:
        """Positions gained. Non-negative within an episode by the FIFO argument."""
        return self.initial_orders_ahead - self.current_orders_ahead

    def observe(self, *, orders_ahead: int, volume_ahead: int, fills_ahead_delta: int = 0) -> None:
        """Record one observation. A breach counts once, however many invariants it trips.

        The two checks are not independent - an increase in `orders_ahead` also drives the
        residual negative - so incrementing per failed check would report one bad
        observation as two violations and inflate every downstream rate.
        """
        ahead_increased = orders_ahead > self.current_orders_ahead
        self.current_orders_ahead = orders_ahead
        self.current_volume_ahead = volume_ahead
        self.fills_ahead += fills_ahead_delta
        residual_negative = (self.initial_orders_ahead - self.current_orders_ahead) - self.fills_ahead < 0

        # Recorded, never repaired: the reading stands and the breach is counted beside it.
        if ahead_increased:
            self.ahead_increase_violations += 1
        if residual_negative:
            self.residual_negative_violations += 1
        if ahead_increased or residual_negative:
            self.identity_violations += 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "side": self.side,
            "price_raw": self.price_raw,
            "opened_recv_ns": self.opened_recv_ns,
            "opened_basis": self.opened_basis,
            "closed_recv_ns": self.closed_recv_ns,
            "initial_orders_ahead": self.initial_orders_ahead,
            "initial_volume_ahead": self.initial_volume_ahead,
            "final_orders_ahead": self.current_orders_ahead,
            "final_volume_ahead": self.current_volume_ahead,
            "fills_ahead": self.fills_ahead,
            "cancels_ahead": self.cancels_ahead,
            "cancels_ahead_basis": "residual of initial_ahead - current_ahead - fills_ahead",
            "queue_movement": self.queue_movement,
            "identity_violations": self.identity_violations,
            "ahead_increase_violations": self.ahead_increase_violations,
            "residual_negative_violations": self.residual_negative_violations,
        }


@dataclass
class OrderLifecycle:
    """One order id inside one continuity segment, across its queue episodes."""

    order_id: int
    instrument_id: int
    continuity_segment: int
    birth_recv_ns: int
    birth_sequence: int
    side: str
    family_id: str
    session_phase: str
    source_day: str
    source_role: str
    episodes: list[QueueEpisode] = field(default_factory=list)
    own_fill_count: int = 0
    own_fill_size: int = 0
    modify_count: int = 0
    priority_loss_count: int = 0
    terminal_status: str | None = None
    terminal_recv_ns: int | None = None
    # F-17 (Frankie's F-17, S119). 97.3% of lifecycles outlive the group that gave rise to
    # them, so a stratum stamped at BIRTH describes an instant the order left long ago. The
    # exit-time family and phase are stamped at the terminal and the stratum is keyed on
    # them; the birth values stay on the row. None until the order dies - a censored order
    # has no exit group, and inventing one would be a key collision dressed as a label.
    exit_family_id: str | None = None
    exit_session_phase: str | None = None

    @property
    def exit_stratum_available(self) -> bool:
        """Whether the order died inside a group whose family and phase are known.

        Segment-end censoring has no exit group, so this is False there - and a censored
        order is therefore EXCLUDED from the exit-keyed view and counted, never filed under
        an invented exit.
        """
        return self.exit_family_id is not None and self.exit_session_phase is not None

    @property
    def current_episode(self) -> QueueEpisode:
        if not self.episodes:
            raise QueueError(f"order {self.order_id} has no open queue episode")
        return self.episodes[-1]

    @property
    def resolved(self) -> bool:
        return self.terminal_status in TERMINAL_RESOLVED

    @property
    def lifetime_ns(self) -> int | None:
        if self.terminal_recv_ns is None:
            return None
        return self.terminal_recv_ns - self.birth_recv_ns

    def age_ns(self, now_recv_ns: int) -> int:
        return now_recv_ns - self.birth_recv_ns

    def as_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "instrument_id": self.instrument_id,
            "continuity_segment": self.continuity_segment,
            "source_day": self.source_day,
            "source_role": self.source_role,
            # F-17. The PRIMARY stratum stays keyed on BIRTH - S119 decided that and a
            # committed test pins it, and moving it would break comparability with run
            # 33605852433. The EXIT context is carried beside it and feeds a second, separately
            # labelled survival view, so Frankie's F-17 population exists without the birth
            # one being overwritten. Which is primary is Greg's to pick (D60); both are here.
            "family_id": self.family_id,
            "side": self.side,
            "session_phase": self.session_phase,
            "stratum_basis": "BIRTH_STAMPED",
            "birth_family_id": self.family_id,
            "birth_session_phase": self.session_phase,
            "exit_family_id": self.exit_family_id,
            "exit_session_phase": self.exit_session_phase,
            "exit_stratum_available": self.exit_stratum_available,
            "birth_recv_ns": self.birth_recv_ns,
            "birth_sequence": self.birth_sequence,
            "terminal_status": self.terminal_status,
            "terminal_recv_ns": self.terminal_recv_ns,
            "lifetime_ns": self.lifetime_ns,
            "resolved": self.resolved,
            "censored": self.terminal_status in TERMINAL_CENSORED,
            "own_fill_count": self.own_fill_count,
            "own_fill_size": self.own_fill_size,
            "modify_count": self.modify_count,
            "priority_loss_count": self.priority_loss_count,
            "episode_count": len(self.episodes),
            "episodes": [e.as_dict() for e in self.episodes],
            "clock": CAUSAL_CLOCK,
        }


class QueueSurvivalCalculator:
    """Streaming section 4.6 accumulator.

    Open state is bounded by the number of simultaneously resting orders - the book itself -
    rather than by the number of groups processed, so a 4.26M-group stream does not grow
    memory without bound.
    """

    def __init__(self, *, exact_cap: int | None = None, seed: int = 0) -> None:
        kwargs: dict[str, Any] = {"seed": seed}
        if exact_cap is not None:
            kwargs["exact_cap"] = exact_cap

        # D-13. `population` is a PARAMETER now. It was one string shared by five measures -
        # "resting orders within the stratum and continuity segment" - and two of those
        # measures do not count orders at all. One declaration covering two units is how
        # 20,005 and 24,645 came to be reported as the same population, and a false
        # population invites the pooling this whole section exists to refuse.
        def measure(
            name: str,
            numerator: str,
            population: str,
            status: str,
            missingness: str,
            kind: str = "DISTRIBUTION",
        ):
            return StratifiedMeasure(
                name=name,
                declaration=Declaration(
                    numerator_formula=numerator,
                    population=population,
                    causal_cutoff="F_LAST receive time of the group carrying the action",
                    status=status,
                    missingness_rule=missingness,
                ),
                kind=kind,
                **kwargs,
            )

        self.resolved_lifetime = measure(
            "resolved_lifetime_ns",
            "terminal.ts_recv_ns - birth.ts_recv_ns, resolved exits only",
            LIFECYCLE_POPULATION + ", resolved exits only; one observation per order id",
            RESOLVED,
            "censored and still-open orders are excluded here and carried in time_to_exit",
        )
        self.censored_age = measure(
            "censored_age_ns",
            "segment_or_stream_end.ts_recv_ns - birth.ts_recv_ns, censored orders only",
            # The unit is stated; the arithmetic, the exclusion predicate and the n are
            # untouched. This measure reported 597 against 597 declared censorings on run
            # 33605852433 and is the reference for the same channel in 4.13, so nothing here
            # changes what it counts - only what it says it counts.
            LIFECYCLE_POPULATION + ", censored exits only; one observation per order id",
            CENSORED,
            "resolved orders are excluded here; they appear in resolved_lifetime",
        )
        self.initial_volume_ahead = measure(
            "initial_volume_ahead",
            "sum of resting sizes ahead at the opening of an order's BIRTH episode",
            "tracked order BIRTHS within the stratum and continuity segment; one observation "
            "per order id, taken at its first queue episode only",
            RESOLVED,
            # D-13. The 4,640 re-queue opens are not missing from this measure, they are not
            # members of it: the queue an order rejoins after losing priority is a different
            # population from the queue it was born into. They are measured, in
            # requeue_initial_volume_ahead, and retained per episode on every lifecycle row.
            "orders whose level could not be read are excluded and counted; re-queue episode "
            "opens are NOT members here and are measured by requeue_initial_volume_ahead",
        )
        self.requeue_initial_volume_ahead = measure(
            "requeue_initial_volume_ahead",
            "sum of resting sizes ahead at the opening of a RE-QUEUED episode",
            EPISODE_POPULATION + ", re-queued episodes only; one observation per priority loss",
            RESOLVED,
            # D60: this number was computed on every priority loss, written to the episode row
            # and then entered no average at all - 4,640 readings of where an order lands when
            # it loses priority, retained and never used. It is also the half of the episode
            # population that makes the section's three n values reconcile without reaching
            # for an adapter counter.
            "priority losses whose new level could not be read are excluded and counted",
        )
        self.queue_movement = measure(
            "queue_movement",
            "initial_orders_ahead - final_orders_ahead within one episode",
            EPISODE_POPULATION + "; one observation per episode CLOSED, birth episodes and "
            "re-queued episodes alike, so an order that lost priority twice contributes three",
            RESOLVED,
            # The old rule claimed an exclusion that does not exist and never did: an episode
            # with no observation after open reports a movement of 0, and that 0 is a
            # measurement - no order ahead departed, which the book states directly - not an
            # absence dressed as a number.
            "no episode is excluded; an episode never re-observed after open contributes a "
            "measured 0, since nothing ahead of it departed",
        )
        self.time_to_exit = measure(
            "time_to_exit_ns",
            "Kaplan-Meier over exit times; censored orders lower the at-risk set without an event",
            LIFECYCLE_POPULATION + "; one observation per order id, as an event or a censoring",
            CENSORED,
            "every order contributes exactly once, as an event or as a censoring",
            kind="SURVIVAL",
        )
        # F-17 (Frankie's F-17, S119) - the PARALLEL view. Same lifetimes, keyed on the group
        # the order DIED in rather than the one it was born in. 97.3% of lifecycles outlive
        # their birth group, so for almost every order these two strata name different
        # families and phases - that difference is the finding. Birth stays PRIMARY (S119's
        # decision, pinned by a committed test, and the comparability of run 33605852433
        # depends on it); this is filed beside it, never instead of it. Which is primary is
        # Greg's pick under D60.
        self.time_to_exit_by_exit_stratum = measure(
            "time_to_exit_by_exit_stratum_ns",
            "Kaplan-Meier over exit times, keyed on the EXIT group's family and phase (F-17); "
            "the birth-keyed time_to_exit_ns is the primary view and this is its complement",
            LIFECYCLE_POPULATION + "; one observation per RESOLVED-or-censored order that died "
            "inside a known group - segment-end censoring has no exit group",
            CENSORED,
            "an order censored at segment end is EXCLUDED here and counted "
            "(exit_view_excluded_no_exit_group); it remains in time_to_exit_ns, so the two "
            "populations differ by exactly that count: COMPLEMENTARY_SCOPE_DIFFERENCE",
            kind="SURVIVAL",
        )
        self.exit_view_filed = 0
        self.exit_view_excluded_no_exit_group = 0

        self._open: dict[tuple[int, int], OrderLifecycle] = {}
        self._level_fill_counts: dict[tuple[int, str, int], int] = {}
        self.completed = 0
        self.resolved_count = 0
        self.censored_count = 0
        self.identity_violations = 0
        self.unknown_order_events = 0
        # D-13. The episode census, kept at the point of observation rather than derived
        # afterwards. Each of these is incremented in the same statement block that feeds a
        # measure, so `episode_accounting` reconciles the measures' own observation calls and
        # not a second, independent count of the same events that could agree with nothing.
        self.birth_episodes = 0
        self.episodes_measured = 0
        self.episode_reopens: dict[str, int] = {basis: 0 for basis in REOPEN_BASES}

    @property
    def measures(self) -> tuple[StratifiedMeasure, ...]:
        return (
            self.resolved_lifetime,
            self.censored_age,
            self.initial_volume_ahead,
            self.requeue_initial_volume_ahead,
            self.queue_movement,
            self.time_to_exit,
            # F-17. In the tuple, or the D-13 unit gate, companion_rows and stratum_counts all
            # miss it - a measure that exists and is enumerated nowhere is the dark-section
            # shape one attribute down.
            self.time_to_exit_by_exit_stratum,
        )

    @property
    def episode_reopen_count(self) -> int:
        return sum(self.episode_reopens.values())

    @property
    def open_order_count(self) -> int:
        return len(self._open)

    def _key(self, lifecycle: OrderLifecycle) -> StratumKey:
        """The BIRTH stratum - the primary key, unchanged since S119 decided it."""
        return StratumKey(
            source_day=lifecycle.source_day,
            source_role=lifecycle.source_role,
            continuity_segment=lifecycle.continuity_segment,
            family_id=lifecycle.family_id,
            side_orientation=lifecycle.side,
            session_phase=lifecycle.session_phase,
            clock=CAUSAL_CLOCK,
        )

    def _exit_key(self, lifecycle: OrderLifecycle) -> StratumKey:
        """The EXIT stratum (F-17): the group the order actually died in.

        Only meaningful when `exit_stratum_available`; callers check first. 97.3% of
        lifecycles outlive their birth group, so for almost the whole population this names a
        different family and phase from `_key`, and that difference is the finding, not an
        error - which is why both views are kept and labelled rather than one replacing the
        other.
        """
        return StratumKey(
            source_day=lifecycle.source_day,
            source_role=lifecycle.source_role,
            continuity_segment=lifecycle.continuity_segment,
            family_id=lifecycle.exit_family_id,  # type: ignore[arg-type]
            side_orientation=lifecycle.side,
            session_phase=lifecycle.exit_session_phase,  # type: ignore[arg-type]
            clock=CAUSAL_CLOCK,
        )

    def on_add(
        self,
        *,
        instrument_id: int,
        order_id: int,
        side: str,
        price_raw: int,
        recv_ns: int,
        sequence: int,
        continuity_segment: int,
        source_day: str,
        source_role: str,
        family_id: str,
        session_phase: str,
        book_view: BookView,
    ) -> OrderLifecycle:
        handle = (instrument_id, order_id)
        if handle in self._open:
            raise QueueError(f"order {order_id} is already resting; a duplicate add would fork its lifecycle")
        orders_ahead, volume_ahead = book_view(side, price_raw, order_id)
        lifecycle = OrderLifecycle(
            order_id=order_id,
            instrument_id=instrument_id,
            continuity_segment=continuity_segment,
            birth_recv_ns=recv_ns,
            birth_sequence=sequence,
            side=side,
            family_id=family_id,
            session_phase=session_phase,
            source_day=source_day,
            source_role=source_role,
        )
        lifecycle.episodes.append(
            QueueEpisode(
                side=side,
                price_raw=price_raw,
                opened_recv_ns=recv_ns,
                initial_orders_ahead=orders_ahead,
                initial_volume_ahead=volume_ahead,
                current_orders_ahead=orders_ahead,
                current_volume_ahead=volume_ahead,
            )
        )
        self._open[handle] = lifecycle
        self.initial_volume_ahead.observe(self._key(lifecycle), float(volume_ahead))
        self.birth_episodes += 1
        return lifecycle

    def observe_level(
        self,
        *,
        instrument_id: int,
        order_id: int,
        orders_ahead: int,
        volume_ahead: int,
        fills_ahead_delta: int = 0,
    ) -> None:
        """Refresh one resting order's queue state at a relevant action."""
        lifecycle = self._open.get((instrument_id, order_id))
        if lifecycle is None:
            self.unknown_order_events += 1
            return
        episode = lifecycle.current_episode
        before = episode.identity_violations
        episode.observe(
            orders_ahead=orders_ahead,
            volume_ahead=volume_ahead,
            fills_ahead_delta=fills_ahead_delta,
        )
        self.identity_violations += episode.identity_violations - before

    def on_priority_loss(
        self,
        *,
        instrument_id: int,
        order_id: int,
        side: str,
        price_raw: int,
        recv_ns: int,
        book_view: BookView,
    ) -> None:
        """Close the current queue episode and open a new one at the back of its queue."""
        lifecycle = self._open.get((instrument_id, order_id))
        if lifecycle is None:
            self.unknown_order_events += 1
            return
        episode = lifecycle.current_episode
        key = self._key(lifecycle)
        self._close_episode(lifecycle, episode, recv_ns=recv_ns)
        lifecycle.priority_loss_count += 1
        # D-13. Classified from what the BOOK shows, before and after, because that is the
        # only account of the re-queue this section holds: the cause the adapter knows -
        # re-price, size increase, duplicate add, a re-add of an order a reset took - is
        # counted in its own `queue_observation` block and in none of 4.6's measures or its
        # summary. Reconciling 4,640 re-queues by differencing them against that block's 4,625
        # `modify_reprice` events is what left fifteen observations homeless.
        basis = _reopen_basis(episode, side=side, price_raw=price_raw)
        self.episode_reopens[basis] += 1
        orders_ahead, volume_ahead = book_view(side, price_raw, order_id)
        lifecycle.episodes.append(
            QueueEpisode(
                side=side,
                price_raw=price_raw,
                opened_recv_ns=recv_ns,
                opened_basis=basis,
                initial_orders_ahead=orders_ahead,
                initial_volume_ahead=volume_ahead,
                current_orders_ahead=orders_ahead,
                current_volume_ahead=volume_ahead,
            )
        )
        self.requeue_initial_volume_ahead.observe(key, float(volume_ahead))

    def on_modify_retaining_priority(self, *, instrument_id: int, order_id: int) -> None:
        lifecycle = self._open.get((instrument_id, order_id))
        if lifecycle is None:
            self.unknown_order_events += 1
            return
        lifecycle.modify_count += 1

    def on_own_fill(self, *, instrument_id: int, order_id: int, size: int) -> None:
        lifecycle = self._open.get((instrument_id, order_id))
        if lifecycle is None:
            self.unknown_order_events += 1
            return
        lifecycle.own_fill_count += 1
        lifecycle.own_fill_size += int(size)

    def note_level_fill(self, *, instrument_id: int, side: str, price_raw: int, count: int = 1) -> int:
        """Count a fill at a level. In FIFO a fill is always ahead of anything still resting."""
        handle = (instrument_id, side, price_raw)
        self._level_fill_counts[handle] = self._level_fill_counts.get(handle, 0) + count
        return self._level_fill_counts[handle]

    def _close_episode(self, lifecycle: OrderLifecycle, episode: QueueEpisode, *, recv_ns: int) -> None:
        """The one place an episode is measured, so the census cannot drift from the measure.

        Both closers - a priority loss and a lifecycle terminal - come through here, which is
        what makes `episodes_measured` equal to `queue_movement`'s total n by construction
        rather than by a second count that happens to agree.
        """
        if episode.closed_recv_ns is None:
            episode.closed_recv_ns = recv_ns
        self.queue_movement.observe(self._key(lifecycle), float(episode.queue_movement))
        self.episodes_measured += 1

    def _close(
        self,
        lifecycle: OrderLifecycle,
        *,
        status: str,
        recv_ns: int,
        exit_family_id: str | None = None,
        exit_session_phase: str | None = None,
    ) -> dict[str, Any]:
        lifecycle.terminal_status = status
        lifecycle.terminal_recv_ns = recv_ns
        # F-17. Stamped BEFORE the key is built, so every terminal observation below files
        # under the exit stratum. Segment-end censoring passes neither and stays BIRTH_STAMPED,
        # which the row then says in words.
        lifecycle.exit_family_id = exit_family_id
        lifecycle.exit_session_phase = exit_session_phase
        episode = lifecycle.current_episode
        key = self._key(lifecycle)
        lifetime = lifecycle.lifetime_ns or 0
        self._close_episode(lifecycle, episode, recv_ns=recv_ns)
        if status in TERMINAL_RESOLVED:
            self.resolved_lifetime.observe(key, float(lifetime))
            self.time_to_exit.observe(key, float(lifetime), event_observed=True)
            self.resolved_count += 1
        else:
            self.censored_age.observe(key, float(lifetime))
            self.time_to_exit.observe(key, float(lifetime), event_observed=False)
            self.censored_count += 1
        # F-17, the parallel view. The same lifetime filed under the group the order DIED in.
        # Censored orders have no exit group and are excluded HERE and counted - they are still
        # in the birth-keyed view above, so nothing is lost, and the two views' populations
        # differ by exactly the censored count, which the declaration states.
        if lifecycle.exit_stratum_available:
            self.time_to_exit_by_exit_stratum.observe(
                self._exit_key(lifecycle), float(lifetime),
                event_observed=status in TERMINAL_RESOLVED,
            )
            self.exit_view_filed += 1
        else:
            self.time_to_exit_by_exit_stratum.exclude_missing(key)
            self.exit_view_excluded_no_exit_group += 1
        self.completed += 1
        self._open.pop((lifecycle.instrument_id, lifecycle.order_id), None)
        return lifecycle.as_dict()

    def on_terminal(
        self,
        *,
        instrument_id: int,
        order_id: int,
        status: str,
        recv_ns: int,
        exit_family_id: str | None = None,
        exit_session_phase: str | None = None,
    ) -> dict[str, Any] | None:
        if status not in TERMINAL_RESOLVED:
            raise QueueError(f"on_terminal accepts {sorted(TERMINAL_RESOLVED)}; censoring is not an event")
        lifecycle = self._open.get((instrument_id, order_id))
        if lifecycle is None:
            self.unknown_order_events += 1
            return None
        return self._close(
            lifecycle, status=status, recv_ns=recv_ns,
            exit_family_id=exit_family_id, exit_session_phase=exit_session_phase,
        )

    def close_continuity_segment(self, *, segment: int, recv_ns: int) -> list[dict[str, Any]]:
        """Censor every order still resting when a segment ends.

        Section 2 forbids a calculation crossing a reset, snapshot, gap or session boundary.
        Carrying an open lifecycle past one would produce a lifetime measured across an
        interval we never observed, so those orders exit as censored instead.
        """
        stranded = [lc for lc in self._open.values() if lc.continuity_segment == segment]
        return [self._close(lc, status=OPEN_AT_SEGMENT_END, recv_ns=recv_ns) for lc in stranded]

    def finalize(self, *, recv_ns: int) -> list[dict[str, Any]]:
        return [
            self._close(lc, status=OPEN_AT_STREAM_END, recv_ns=recv_ns)
            for lc in list(self._open.values())
        ]

    def companion_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for measure in self.measures:
            rows.extend(measure.rows())
        return rows

    def episode_accounting(self) -> dict[str, Any]:
        """D-13. The census that turns the 20,005-vs-24,645 difference into an identity.

        `episodes_opened - episodes_measured == episodes_still_open` holds exactly, because
        an open lifecycle holds exactly one unclosed episode and every close goes through
        `_close_episode`. It is REPORTED, not asserted: a breach here means an episode was
        opened or closed somewhere this class does not know about, and the number is the
        evidence for that, so raising would destroy it.

        `reopens_without_a_price_change` is the named residual. On run 33605852433 the
        section's re-queue count (4,640) could only be read against a counter in another
        block (the adapter's `queue_observation`, `modify_reprice` 4,625), and the 15 that did not
        match had
        nowhere to be counted: 14 reconcile to `priority_loss_not_visible_in_position` and
        the fifteenth is unattributable from the committed evidence, since no other cause
        counter was emitted. That class is counted here every run now, so the number is
        reported rather than differenced out of two artifacts and rediscovered.
        """
        opened = self.birth_episodes + self.episode_reopen_count
        without_price_change = (
            self.episode_reopens[REOPENED_SAME_LEVEL] + self.episode_reopens[REOPENED_SIDE_CHANGED]
        )
        return {
            "birth_episodes": self.birth_episodes,
            "reopened_episodes": self.episode_reopen_count,
            "reopened_by_level_transition": dict(self.episode_reopens),
            "reopens_without_a_price_change": without_price_change,
            "reopens_without_a_price_change_basis": (
                "REQUEUE_SAME_LEVEL + REQUEUE_SIDE_CHANGED; a re-queue at the order's own "
                "side and price is a priority loss the book position does not show, and is "
                "not a re-price"
            ),
            "episodes_opened": opened,
            "episodes_measured": self.episodes_measured,
            "episodes_still_open": self.open_order_count,
            "accounting_balances": opened - self.episodes_measured == self.open_order_count,
            "identity": (
                "birth_episodes + reopened_episodes - episodes_still_open == "
                "episodes_measured == queue_movement total n"
            ),
        }

    def summary(self) -> dict[str, Any]:
        return {
            "section": "4.6",
            "causal_clock": CAUSAL_CLOCK,
            "completed_lifecycles": self.completed,
            "resolved": self.resolved_count,
            "censored": self.censored_count,
            "still_open": self.open_order_count,
            "fifo_identity_violations": self.identity_violations,
            "events_for_unknown_orders": self.unknown_order_events,
            "censoring_note": (
                "resolved and censored lifetimes are never pooled into one mean; section 4.6 "
                "requires a survival estimator with at-risk counts for time-to-exit"
            ),
            # D-13. The unit each measure counts, in the summary as well as on every averaged
            # row, because the two were read side by side as one population and nothing in
            # the artifact said they were not.
            "measure_units": {
                self.resolved_lifetime.name: UNIT_LIFECYCLE,
                self.censored_age.name: UNIT_LIFECYCLE,
                self.time_to_exit.name: UNIT_LIFECYCLE,
                self.time_to_exit_by_exit_stratum.name: UNIT_LIFECYCLE,
                self.initial_volume_ahead.name: UNIT_BIRTH_EPISODE,
                self.requeue_initial_volume_ahead.name: UNIT_REQUEUE_EPISODE,
                self.queue_movement.name: UNIT_CLOSED_EPISODE,
            },
            "episode_accounting": self.episode_accounting(),
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
            # F-17. Both views' populations, so the scope difference is on the record.
            "exit_view": {
                "measure": self.time_to_exit_by_exit_stratum.name,
                "filed": self.exit_view_filed,
                "excluded_no_exit_group": self.exit_view_excluded_no_exit_group,
                "primary_view": self.time_to_exit.name,
                "basis": (
                    "birth-keyed survival is PRIMARY (S119); the exit-keyed view is filed "
                    "beside it; which is primary is a D60 decision, not the runner's"
                ),
            },
        }
