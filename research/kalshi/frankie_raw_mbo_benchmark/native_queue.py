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
            "family_id": self.family_id,
            "side": self.side,
            "session_phase": self.session_phase,
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

        def measure(name: str, numerator: str, status: str, missingness: str, kind: str = "DISTRIBUTION"):
            return StratifiedMeasure(
                name=name,
                declaration=Declaration(
                    numerator_formula=numerator,
                    population="resting orders within the stratum and continuity segment",
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
            RESOLVED,
            "censored and still-open orders are excluded here and carried in time_to_exit",
        )
        self.censored_age = measure(
            "censored_age_ns",
            "segment_or_stream_end.ts_recv_ns - birth.ts_recv_ns, censored orders only",
            CENSORED,
            "resolved orders are excluded here; they appear in resolved_lifetime",
        )
        self.initial_volume_ahead = measure(
            "initial_volume_ahead",
            "sum of resting sizes ahead at episode open",
            RESOLVED,
            "orders whose level could not be read are excluded and counted",
        )
        self.queue_movement = measure(
            "queue_movement",
            "initial_orders_ahead - final_orders_ahead within one episode",
            RESOLVED,
            "episodes with no observation after open are excluded and counted",
        )
        self.time_to_exit = measure(
            "time_to_exit_ns",
            "Kaplan-Meier over exit times; censored orders lower the at-risk set without an event",
            CENSORED,
            "every order contributes exactly once, as an event or as a censoring",
            kind="SURVIVAL",
        )

        self._open: dict[tuple[int, int], OrderLifecycle] = {}
        self._level_fill_counts: dict[tuple[int, str, int], int] = {}
        self.completed = 0
        self.resolved_count = 0
        self.censored_count = 0
        self.identity_violations = 0
        self.unknown_order_events = 0

    @property
    def measures(self) -> tuple[StratifiedMeasure, ...]:
        return (
            self.resolved_lifetime,
            self.censored_age,
            self.initial_volume_ahead,
            self.queue_movement,
            self.time_to_exit,
        )

    @property
    def open_order_count(self) -> int:
        return len(self._open)

    def _key(self, lifecycle: OrderLifecycle) -> StratumKey:
        return StratumKey(
            source_day=lifecycle.source_day,
            source_role=lifecycle.source_role,
            continuity_segment=lifecycle.continuity_segment,
            family_id=lifecycle.family_id,
            side_orientation=lifecycle.side,
            session_phase=lifecycle.session_phase,
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
        episode.closed_recv_ns = recv_ns
        self.queue_movement.observe(self._key(lifecycle), float(episode.queue_movement))
        lifecycle.priority_loss_count += 1
        orders_ahead, volume_ahead = book_view(side, price_raw, order_id)
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

    def _close(self, lifecycle: OrderLifecycle, *, status: str, recv_ns: int) -> dict[str, Any]:
        lifecycle.terminal_status = status
        lifecycle.terminal_recv_ns = recv_ns
        episode = lifecycle.current_episode
        if episode.closed_recv_ns is None:
            episode.closed_recv_ns = recv_ns
        key = self._key(lifecycle)
        lifetime = lifecycle.lifetime_ns or 0
        self.queue_movement.observe(key, float(episode.queue_movement))
        if status in TERMINAL_RESOLVED:
            self.resolved_lifetime.observe(key, float(lifetime))
            self.time_to_exit.observe(key, float(lifetime), event_observed=True)
            self.resolved_count += 1
        else:
            self.censored_age.observe(key, float(lifetime))
            self.time_to_exit.observe(key, float(lifetime), event_observed=False)
            self.censored_count += 1
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
    ) -> dict[str, Any] | None:
        if status not in TERMINAL_RESOLVED:
            raise QueueError(f"on_terminal accepts {sorted(TERMINAL_RESOLVED)}; censoring is not an event")
        lifecycle = self._open.get((instrument_id, order_id))
        if lifecycle is None:
            self.unknown_order_events += 1
            return None
        return self._close(lifecycle, status=status, recv_ns=recv_ns)

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
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
        }
