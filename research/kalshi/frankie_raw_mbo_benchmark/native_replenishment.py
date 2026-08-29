"""Section 4.7: replenishment and liquidity resilience.

This is the first section whose measure looks forward, and it is where the streaming
design earns its keep. An episode opens at a removal or contact and can only resolve
later, so instead of scanning ahead, an episode is held pending and emitted when its
outcome has actually arrived in stream time. Nothing is computed from data the calculator
has not yet reached.

That distinction matters beyond tidiness. A batch pass would compute complete restoration
outcomes for removals near the end of the data - outcomes a live system could never have
had - and quietly report them alongside the rest. Here a removal whose horizon has not
elapsed by end of stream is censored, and never-restored is kept distinct from
not-yet-observed, exactly as section 4.7 requires ("resolved, censored, and never-restored
paths are separate").

Section 4.7 also requires distinguishing new liquidity from reshaped residual orders, so a
refill by a previously unseen order ID and a resize of an order that was already resting
are counted separately and never summed into one "replenishment" number.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from research.kalshi.frankie_raw_mbo_benchmark.native_stratum import (
    CENSORED,
    RESOLVED,
    Declaration,
    StratifiedMeasure,
    StratumKey,
)

CAUSAL_CLOCK = "ts_recv_ns"

RESTORED = "RESTORED"
NEVER_RESTORED = "NEVER_RESTORED"
CENSORED_HORIZON = "CENSORED_HORIZON"
CENSORED_SEGMENT_END = "CENSORED_SEGMENT_END"
CENSORED_STREAM_END = "CENSORED_STREAM_END"
RESOLVED_OUTCOMES = frozenset({RESTORED, NEVER_RESTORED})
CENSORED_OUTCOMES = frozenset({CENSORED_HORIZON, CENSORED_SEGMENT_END, CENSORED_STREAM_END})

SAME_PRICE = "SAME_PRICE"
NEIGHBORING_PRICE = "NEIGHBORING_PRICE"

NEW_LIQUIDITY = "NEW_ID_ADD"
RESHAPED_RESIDUAL = "SAME_ID_MODIFY"


class ReplenishmentError(ValueError):
    """A replenishment episode could not be tracked consistently."""


@dataclass
class ReplenishmentEpisode:
    """One removal or contact, and what the book did about it afterwards."""

    episode_id: int
    instrument_id: int
    side: str
    price_raw: int
    opened_recv_ns: int
    horizon_ns: int
    continuity_segment: int
    source_day: str
    source_role: str
    family_id: str
    session_phase: str
    touch_state_at_open: str
    removed_quantity: int
    removed_order_count: int
    depth_at_open: int
    touch_price_at_open: int | None

    new_id_add_quantity: int = 0
    new_id_add_count: int = 0
    same_id_modify_quantity: int = 0
    same_id_modify_count: int = 0
    same_price_refill_quantity: int = 0
    neighboring_price_refill_quantity: int = 0
    touch_restored_recv_ns: int | None = None
    first_restoration_recv_ns: int | None = None
    peak_restored_quantity: int = 0
    outcome: str | None = None
    closed_recv_ns: int | None = None

    @property
    def replaced_quantity(self) -> int:
        """New liquidity plus reshaped residual, kept addable but never conflated above."""
        return self.new_id_add_quantity + self.same_id_modify_quantity

    @property
    def restoration_ratio(self) -> float | None:
        """Replaced over removed. None when nothing was removed - not zero."""
        if self.removed_quantity == 0:
            return None
        return self.replaced_quantity / self.removed_quantity

    @property
    def overshoot_quantity(self) -> int:
        return max(self.peak_restored_quantity - self.removed_quantity, 0)

    @property
    def time_to_restoration_ns(self) -> int | None:
        if self.first_restoration_recv_ns is None:
            return None
        return self.first_restoration_recv_ns - self.opened_recv_ns

    @property
    def touch_restoration_ns(self) -> int | None:
        if self.touch_restored_recv_ns is None:
            return None
        return self.touch_restored_recv_ns - self.opened_recv_ns

    @property
    def resolved(self) -> bool:
        return self.outcome in RESOLVED_OUTCOMES

    def add_refill(
        self,
        *,
        quantity: int,
        liquidity_kind: str,
        price_relation: str,
        recv_ns: int,
    ) -> None:
        if liquidity_kind not in (NEW_LIQUIDITY, RESHAPED_RESIDUAL):
            raise ReplenishmentError(f"unknown liquidity kind: {liquidity_kind}")
        if price_relation not in (SAME_PRICE, NEIGHBORING_PRICE):
            raise ReplenishmentError(f"unknown price relation: {price_relation}")
        if recv_ns < self.opened_recv_ns:
            raise ReplenishmentError("a refill cannot precede the removal that opened the episode")
        if liquidity_kind == NEW_LIQUIDITY:
            self.new_id_add_quantity += quantity
            self.new_id_add_count += 1
        else:
            self.same_id_modify_quantity += quantity
            self.same_id_modify_count += 1
        if price_relation == SAME_PRICE:
            self.same_price_refill_quantity += quantity
        else:
            self.neighboring_price_refill_quantity += quantity
        self.peak_restored_quantity = max(self.peak_restored_quantity, self.replaced_quantity)
        if self.first_restoration_recv_ns is None:
            self.first_restoration_recv_ns = recv_ns

    def restore_touch(self, recv_ns: int) -> None:
        if self.touch_restored_recv_ns is None:
            self.touch_restored_recv_ns = recv_ns

    def as_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "instrument_id": self.instrument_id,
            "source_day": self.source_day,
            "source_role": self.source_role,
            "continuity_segment": self.continuity_segment,
            "family_id": self.family_id,
            "side": self.side,
            "session_phase": self.session_phase,
            "price_raw": self.price_raw,
            "touch_state_at_open": self.touch_state_at_open,
            "opened_recv_ns": self.opened_recv_ns,
            "closed_recv_ns": self.closed_recv_ns,
            "horizon_ns": self.horizon_ns,
            "removed_quantity": self.removed_quantity,
            "removed_order_count": self.removed_order_count,
            "depth_at_open": self.depth_at_open,
            "touch_price_at_open": self.touch_price_at_open,
            "new_id_add_quantity": self.new_id_add_quantity,
            "new_id_add_count": self.new_id_add_count,
            "same_id_modify_quantity": self.same_id_modify_quantity,
            "same_id_modify_count": self.same_id_modify_count,
            "same_price_refill_quantity": self.same_price_refill_quantity,
            "neighboring_price_refill_quantity": self.neighboring_price_refill_quantity,
            "replaced_quantity": self.replaced_quantity,
            "restoration_ratio": self.restoration_ratio,
            "overshoot_quantity": self.overshoot_quantity,
            "peak_restored_quantity": self.peak_restored_quantity,
            "time_to_restoration_ns": self.time_to_restoration_ns,
            "touch_restoration_ns": self.touch_restoration_ns,
            "outcome": self.outcome,
            "resolved": self.resolved,
            "censored": self.outcome in CENSORED_OUTCOMES,
            "clock": CAUSAL_CLOCK,
        }


class ReplenishmentCalculator:
    """Streaming section 4.7 accumulator with deferred emission.

    Pending episodes are bounded by the horizon rather than by stream length: advancing
    stream time expires anything past its horizon, so the pending set holds only episodes
    whose outcome is still genuinely undetermined.
    """

    def __init__(
        self,
        *,
        horizon_ns: int,
        exact_cap: int | None = None,
        seed: int = 0,
    ) -> None:
        if horizon_ns <= 0:
            raise ReplenishmentError("horizon_ns must be positive")
        self.horizon_ns = horizon_ns
        kwargs: dict[str, Any] = {"seed": seed}
        if exact_cap is not None:
            kwargs["exact_cap"] = exact_cap

        def measure(name: str, numerator: str, status: str, missingness: str, kind: str = "DISTRIBUTION"):
            return StratifiedMeasure(
                name=name,
                declaration=Declaration(
                    numerator_formula=numerator,
                    population="replenishment episodes within the stratum and continuity segment",
                    causal_cutoff=f"episode open + {horizon_ns} ns on {CAUSAL_CLOCK}",
                    status=status,
                    missingness_rule=missingness,
                ),
                kind=kind,
                **kwargs,
            )

        self.removed_quantity = measure(
            "removed_quantity",
            "displayed quantity removed by the initiating event",
            RESOLVED,
            "episodes with zero removal are refused at open, never counted as zero",
        )
        self.replaced_quantity = measure(
            "replaced_quantity",
            "new-ID add quantity + same-ID modify quantity within the horizon",
            RESOLVED,
            "censored episodes are excluded here and reported under their own outcome",
        )
        self.restoration_ratio = measure(
            "restoration_ratio",
            "replaced quantity over removed quantity, member and aggregate forms retained",
            RESOLVED,
            "zero-denominator episodes are counted, not dropped",
            kind="RATIO_PAIR",
        )
        self.time_to_restoration = measure(
            "time_to_restoration_ns",
            "Kaplan-Meier over first restoration; never-restored and horizon-censored differ",
            CENSORED,
            "every episode contributes once, as a restoration event or as a censoring",
            kind="SURVIVAL",
        )
        self.overshoot = measure(
            "overshoot_quantity",
            "peak replaced quantity in excess of removed quantity",
            RESOLVED,
            "episodes that never overshoot contribute zero, which is an observation",
        )

        self._pending: dict[int, ReplenishmentEpisode] = {}
        self._next_id = 0
        self.opened = 0
        self.resolved_count = 0
        self.censored_count = 0
        self.never_restored_count = 0

    @property
    def measures(self) -> tuple[StratifiedMeasure, ...]:
        return (
            self.removed_quantity,
            self.replaced_quantity,
            self.restoration_ratio,
            self.time_to_restoration,
            self.overshoot,
        )

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def _key(self, episode: ReplenishmentEpisode) -> StratumKey:
        return StratumKey(
            source_day=episode.source_day,
            source_role=episode.source_role,
            continuity_segment=episode.continuity_segment,
            family_id=episode.family_id,
            side_orientation=episode.side,
            session_phase=episode.session_phase,
            clock=CAUSAL_CLOCK,
            subfamily_id=f"touch={episode.touch_state_at_open}",
        )

    def open_episode(
        self,
        *,
        instrument_id: int,
        side: str,
        price_raw: int,
        recv_ns: int,
        continuity_segment: int,
        source_day: str,
        source_role: str,
        family_id: str,
        session_phase: str,
        touch_state_at_open: str,
        removed_quantity: int,
        removed_order_count: int,
        depth_at_open: int,
        touch_price_at_open: int | None = None,
    ) -> ReplenishmentEpisode:
        if removed_quantity <= 0:
            raise ReplenishmentError("an episode requires a positive removal; zero is not a contact")
        episode = ReplenishmentEpisode(
            episode_id=self._next_id,
            instrument_id=instrument_id,
            side=side,
            price_raw=price_raw,
            opened_recv_ns=recv_ns,
            horizon_ns=self.horizon_ns,
            continuity_segment=continuity_segment,
            source_day=source_day,
            source_role=source_role,
            family_id=family_id,
            session_phase=session_phase,
            touch_state_at_open=touch_state_at_open,
            removed_quantity=removed_quantity,
            removed_order_count=removed_order_count,
            depth_at_open=depth_at_open,
            touch_price_at_open=touch_price_at_open,
        )
        self._pending[self._next_id] = episode
        self._next_id += 1
        self.opened += 1
        self.removed_quantity.observe(self._key(episode), float(removed_quantity))
        return episode

    def pending_at(self, instrument_id: int, side: str, price_raw: int) -> list[ReplenishmentEpisode]:
        return [
            e
            for e in self._pending.values()
            if e.instrument_id == instrument_id and e.side == side and e.price_raw == price_raw
        ]

    def _emit(self, episode: ReplenishmentEpisode, *, outcome: str, recv_ns: int) -> dict[str, Any]:
        episode.outcome = outcome
        episode.closed_recv_ns = recv_ns
        key = self._key(episode)
        elapsed = recv_ns - episode.opened_recv_ns

        if outcome in RESOLVED_OUTCOMES:
            self.replaced_quantity.observe(key, float(episode.replaced_quantity))
            self.overshoot.observe(key, float(episode.overshoot_quantity))
            self.restoration_ratio.observe(
                key, float(episode.replaced_quantity), float(episode.removed_quantity)
            )
            self.resolved_count += 1
            if outcome == NEVER_RESTORED:
                self.never_restored_count += 1
        else:
            self.replaced_quantity.exclude_missing(key)
            self.overshoot.exclude_missing(key)
            self.censored_count += 1

        restored = episode.time_to_restoration_ns
        if restored is not None:
            self.time_to_restoration.observe(key, float(restored), event_observed=True)
        else:
            self.time_to_restoration.observe(key, float(elapsed), event_observed=False)

        self._pending.pop(episode.episode_id, None)
        return episode.as_dict()

    def advance(self, recv_ns: int) -> list[dict[str, Any]]:
        """Emit every episode whose horizon has elapsed in stream time.

        This is the deferred-emission step. An episode resolves only once the calculator has
        actually reached the point where its outcome is known, so no result here depends on
        data a live consumer would not have had.
        """
        matured = [e for e in self._pending.values() if recv_ns - e.opened_recv_ns >= e.horizon_ns]
        emitted = []
        for episode in sorted(matured, key=lambda e: e.episode_id):
            outcome = RESTORED if episode.first_restoration_recv_ns is not None else NEVER_RESTORED
            emitted.append(self._emit(episode, outcome=outcome, recv_ns=episode.opened_recv_ns + episode.horizon_ns))
        return emitted

    def close_continuity_segment(self, *, segment: int, recv_ns: int) -> list[dict[str, Any]]:
        """Censor episodes whose horizon would otherwise span a boundary."""
        stranded = [e for e in self._pending.values() if e.continuity_segment == segment]
        return [
            self._emit(e, outcome=CENSORED_SEGMENT_END, recv_ns=recv_ns)
            for e in sorted(stranded, key=lambda e: e.episode_id)
        ]

    def finalize(self, *, recv_ns: int) -> list[dict[str, Any]]:
        """Censor whatever is still pending. Never-restored and not-yet-observed differ."""
        return [
            self._emit(e, outcome=CENSORED_STREAM_END, recv_ns=recv_ns)
            for e in sorted(self._pending.values(), key=lambda e: e.episode_id)
        ]

    def companion_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for measure in self.measures:
            rows.extend(measure.rows())
        return rows

    def summary(self) -> dict[str, Any]:
        return {
            "section": "4.7",
            "causal_clock": CAUSAL_CLOCK,
            "horizon_ns": self.horizon_ns,
            "episodes_opened": self.opened,
            "resolved": self.resolved_count,
            "never_restored": self.never_restored_count,
            "censored": self.censored_count,
            "pending": self.pending_count,
            "emission": "DEFERRED_UNTIL_HORIZON_ELAPSED_IN_STREAM_TIME",
            "separation_note": (
                "new-ID adds and same-ID modifies are never summed into one replenishment "
                "figure, and never-restored is distinct from not-yet-observed"
            ),
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
        }
