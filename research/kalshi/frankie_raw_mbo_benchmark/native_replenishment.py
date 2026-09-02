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

## D-3: the ratio was named for something it does not measure

The measure this module previously called `restoration_ratio` is an ARRIVAL DENSITY. The
observation layer credits each refill to EVERY pending episode in the neighbourhood - that
rule is deliberate and is argued at length in `native_replenishment_adapter` - so in run
33605852433 **441,404 attributions landed across 24,283 episodes, 18.18 per episode**, and
the aggregate 748,271 over 52,541 gave **14.24** against a median removed quantity of 1 to 2
lots. Read under the old name that says nine to forty lots come back for every lot removed.
What it actually says is how much liquidity arrives within one tick and 60 s of a removal.

**The name was the defect, so the name is what changed.** The arithmetic, the attribution and
the emission are untouched: every number this module produces is bit-identical to the
delivered run, so the two remain directly comparable and the AT_TOUCH / BEHIND_TOUCH contrast
Frankie found (a factor of 379 to 405 on time-to-restoration) is unaffected. Changing the
attribution here would have silently invalidated that comparison, which is why it was
prescribed as a relabel and left as one.

Two things travel with the value from now on. The formula rides on the episode row rather
than living in this docstring, because a caveat that only prose carries expires the first
time a row is read alone - that is the whole of D-3. And the multiplicity is EMITTED:
`refill_attributions` per episode, a `refill_attributions_per_episode` distribution per
stratum, and `attributions_per_episode` in the summary, so nobody has to divide 441,404 by
24,283 to discover what kind of quantity they are holding.

The numerator was relabelled in S120 (F-17). `replaced_quantity` carried the same implication
of replacement the ratio did - "replaced" reads as replacement of what left - and it is the
same arrival-credited quantity: liquidity that arrived NEAR the removal, credited to every
pending episode in the neighbourhood. It is now `neighborhood_arrival_quantity`. Value
unchanged, key renamed, the old name refuses loudly and names its successor, exactly as the
ratio did under D-3, so the comparison with run 33605852433 survives through the legend of
one rename rather than a silent drift in meaning.
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

ARRIVAL_ATTRIBUTION_RULE = "EVERY_PENDING_EPISODE_IN_NEIGHBORHOOD"
"""How an arrival is credited, stated as a value so it cannot be read off a name instead.

Not one-to-one. Two episodes pending at one level both receive the same arrival in full, so
summing `neighborhood_arrival_quantity` across overlapping episodes exceeds the quantity that arrived.
The episode is the unit 4.7 measures; the sum is not a quantity of liquidity.
"""

NEIGHBORHOOD_ARRIVAL_FORMULA = (
    "quantity arriving at this level or a neighboring one within the horizon, credited to "
    "every pending episode in the neighborhood, over this episode's removed quantity; a "
    "liquidity arrival density in a price-and-time neighborhood, NOT the share of the "
    "removed quantity that came back"
)
"""The formula, carried on every episode row.

It costs a constant string per row - about 5 MB across the delivered run's 24,283 episodes,
inside a section that is 0.6% of the run's bytes - against a defect that made the headline
number of section 4.7 unreadable. Paid deliberately.
"""


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
    def neighborhood_arrival_quantity(self) -> int:
        """New liquidity plus reshaped residual, kept addable but never conflated above."""
        return self.new_id_add_quantity + self.same_id_modify_quantity


    @property
    def replaced_quantity(self) -> int:
        """Refused loudly rather than quietly kept working (D60), as `restoration_ratio` is.

        A caller reading this name is asking how much of the removal was replaced. The number
        is the arrival quantity credited to the episode from its neighbourhood, which is not
        that. Returning it would reproduce the defect on a codebase already told about it.
        """
        raise ReplenishmentError(
            "replaced_quantity was renamed to neighborhood_arrival_quantity (F-17, S120): it "
            "is the liquidity that arrived NEAR the removal, credited to every pending episode "
            "in the neighbourhood, not the share of the removal that was replaced"
        )

    @property
    def refill_attributions(self) -> int:
        """How many arrivals were credited to THIS episode.

        The multiplicity, per episode, computed where it is cheapest and emitted rather than
        left to be inferred from a traversal counter. In run 33605852433 this averaged 18.18.
        """
        return self.new_id_add_count + self.same_id_modify_count

    @property
    def neighborhood_arrival_ratio(self) -> float | None:
        """Arrival quantity credited to this episode, over removed. None when nothing was
        removed - not zero.

        D-3. Formerly `restoration_ratio`, which claimed a one-to-one relation between what
        left and what came back. It has never been that: an arrival within the neighbourhood
        is credited to every pending episode there, so the numerator counts liquidity that
        arrived NEAR the removal, not liquidity that replaced it. Value unchanged, claim
        corrected.
        """
        if self.removed_quantity == 0:
            return None
        return self.neighborhood_arrival_quantity / self.removed_quantity

    @property
    def restoration_ratio(self) -> float | None:
        """Refused loudly rather than quietly kept working (D60).

        A caller reading the old name is asking for a replacement ratio, and the number it
        would get is an arrival density. Returning it would reproduce the defect on a
        codebase that has already been told about it, so this raises and names the successor.
        """
        raise ReplenishmentError(
            "restoration_ratio was renamed to neighborhood_arrival_ratio (D-3): each arrival "
            "is credited to every pending episode in the neighbourhood, so this is a "
            "liquidity arrival density, not the share of the removal that came back"
        )

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
        self.peak_restored_quantity = max(self.peak_restored_quantity, self.neighborhood_arrival_quantity)
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
            "neighborhood_arrival_quantity": self.neighborhood_arrival_quantity,
            "neighborhood_arrival_ratio": self.neighborhood_arrival_ratio,
            # The qualifier travels ON the value. D-3 happened because the attribution rule
            # lived in an adapter docstring and a traversal counter while the number went out
            # under a name that contradicted both.
            "neighborhood_arrival_ratio_formula": NEIGHBORHOOD_ARRIVAL_FORMULA,
            "refill_attributions": self.refill_attributions,
            "attribution_rule": ARRIVAL_ATTRIBUTION_RULE,
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
        self.neighborhood_arrival_quantity = measure(
            "neighborhood_arrival_quantity",
            "new-ID add quantity + same-ID modify quantity within the horizon",
            RESOLVED,
            "censored episodes are excluded here and reported under their own outcome",
        )
        self.neighborhood_arrival_ratio = measure(
            "neighborhood_arrival_ratio",
            # D-3. The old formula string said "replaced quantity over removed quantity",
            # which is true of the arithmetic and false about the estimand: the numerator is
            # every arrival in the neighbourhood, each one credited to every episode pending
            # there. The formula now says which of the two it is.
            NEIGHBORHOOD_ARRIVAL_FORMULA + "; member and aggregate forms retained",
            RESOLVED,
            "zero-denominator episodes are counted, not dropped",
            kind="RATIO_PAIR",
        )
        self.refill_attributions_per_episode = measure(
            "refill_attributions_per_episode",
            "count of arrivals credited to the episode; the attribution multiplicity itself",
            RESOLVED,
            "censored episodes are excluded here; their exposure to arrivals was truncated",
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
        # D-3's two traversal numbers, kept here so the summary can state the multiplicity
        # instead of a reader deriving 441,404 / 24,283 from two different documents.
        self.refill_attributions_total = 0
        self.episodes_closed = 0

    @property
    def measures(self) -> tuple[StratifiedMeasure, ...]:
        return (
            self.removed_quantity,
            self.neighborhood_arrival_quantity,
            self.neighborhood_arrival_ratio,
            self.refill_attributions_per_episode,
            self.time_to_restoration,
            self.overshoot,
        )

    @property
    def restoration_ratio(self) -> StratifiedMeasure:
        """Refused loudly, for the same reason as the episode property above (D-3)."""
        raise ReplenishmentError(
            "the restoration_ratio measure was renamed to neighborhood_arrival_ratio (D-3); "
            "it measures liquidity arrival density in a price-and-time neighbourhood of a "
            "removal, not how much came back for what left"
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

        # Counted for every episode that closes, resolved or censored, because an attribution
        # was made whatever the outcome turned out to be.
        self.refill_attributions_total += episode.refill_attributions
        self.episodes_closed += 1

        if outcome in RESOLVED_OUTCOMES:
            self.neighborhood_arrival_quantity.observe(key, float(episode.neighborhood_arrival_quantity))
            self.overshoot.observe(key, float(episode.overshoot_quantity))
            self.neighborhood_arrival_ratio.observe(
                key, float(episode.neighborhood_arrival_quantity), float(episode.removed_quantity)
            )
            self.refill_attributions_per_episode.observe(key, float(episode.refill_attributions))
            self.resolved_count += 1
            if outcome == NEVER_RESTORED:
                self.never_restored_count += 1
        else:
            self.neighborhood_arrival_quantity.exclude_missing(key)
            self.overshoot.exclude_missing(key)
            self.refill_attributions_per_episode.exclude_missing(key)
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
            "attribution_rule": ARRIVAL_ATTRIBUTION_RULE,
            "refill_attributions": self.refill_attributions_total,
            "episodes_closed": self.episodes_closed,
            # None, never 0.0, when nothing has closed: no episode has been exposed to an
            # arrival yet, and a multiplicity of zero would read as "each arrival was credited
            # to no episode", which is a different and false statement.
            "attributions_per_episode": (
                self.refill_attributions_total / self.episodes_closed
                if self.episodes_closed
                else None
            ),
            "renamed_measures": {"restoration_ratio": "neighborhood_arrival_ratio"},
            "rename_reason": (
                "D-3: each arrival is credited to every pending episode in the neighbourhood, "
                "so the ratio is a liquidity arrival density in a price-and-time neighbourhood "
                "of a removal, not the share of the removed quantity that came back; the "
                "arithmetic is unchanged and remains comparable with run 33605852433"
            ),
            "separation_note": (
                "new-ID adds and same-ID modifies are never summed into one replenishment "
                "figure, and never-restored is distinct from not-yet-observed"
            ),
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
        }
