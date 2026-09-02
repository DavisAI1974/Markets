"""Section 4.8: absorption, withdrawal, and delivered pressure.

A causal runway is scored on what the book did with the pressure applied to it: pressure
absorbed without price movement, delivered through price, or accompanied by withdrawal.
Those three are distinct mechanisms with the same surface appearance - depth falls - and
section 4.8 requires them kept apart rather than merged into a single depletion number.

The separation that does the work here is between *traded* and *withdrawn* depletion. Both
remove displayed size; only one involves a counterparty. A runway whose depth collapsed
because makers pulled is not evidence of demand, and pooling it with a runway whose depth
was consumed by aggressors would manufacture exactly that reading.

Section 4.8 also requires the mean of member-level ratios and the ratio of aggregate sums
to be reported as coequal, so every ratio here is a RatioPair. They answer different
questions - typical runway behaviour versus overall balance - and either alone can invert
the other's sign when runway sizes are uneven.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research.kalshi.frankie_raw_mbo_benchmark.native_stratum import (
    RESOLVED,
    Declaration,
    StratifiedMeasure,
    StratumKey,
)

CAUSAL_CLOCK = "ts_recv_ns"

ABSORBED_WITHOUT_PRICE_MOVE = "ABSORBED_WITHOUT_PRICE_MOVE"
DELIVERED_THROUGH_PRICE = "DELIVERED_THROUGH_PRICE"
ACCOMPANIED_BY_WITHDRAWAL = "ACCOMPANIED_BY_WITHDRAWAL"
INDETERMINATE = "INDETERMINATE"
SPARSE = "SPARSE"
DISCOVERED_PREFIX = "OW_DISPOSITION"
VALID_DISPOSITIONS = frozenset(
    {
        ABSORBED_WITHOUT_PRICE_MOVE,
        DELIVERED_THROUGH_PRICE,
        ACCOMPANIED_BY_WITHDRAWAL,
        INDETERMINATE,
        SPARSE,
    }
)


DEFAULT_REPLACEMENT_HORIZON_NS = 60 * 1_000_000_000
"""How long after a runway closes a same-side re-add still counts as replacing what it lost.

Sixty seconds, matching 4.7's replenishment horizon. It is the same physical question asked
of the same tape - how long before liquidity that comes back stops being a response to the
liquidity that left - so answering it with two different windows in one artifact would make
the two sections incomparable for no reason anyone could state.
"""


@dataclass
class _PendingReplacement:
    """One closed runway still collecting its replacement numerator.

    Held rather than resolved, because at the moment a runway closes the numerator lies in
    the future. Resolving it immediately is exactly what produced 0.0 in all 205 strata: the
    quantity was correct for the instant it was read, and the instant was the wrong one.
    """

    key: StratumKey
    denominator: float
    side: str
    closed_recv_ns: int
    matures_recv_ns: int
    numerator: float = 0.0
    attributions: int = 0


class AbsorptionError(ValueError):
    """A runway could not be scored for absorption or withdrawal."""


@dataclass(frozen=True)
class RunwayPressure:
    """One causal runway's pressure accounting.

    `withdrawn_quantity` is displayed size removed by cancels and downward modifies;
    `traded_quantity` is size removed by fills. They are separate inputs rather than a
    single depletion figure because the whole disposition rests on telling them apart.
    """

    runway_id: str
    instrument_id: int
    side: str
    source_day: str
    source_role: str
    continuity_segment: int
    family_id: str
    session_phase: str
    opened_recv_ns: int
    closed_recv_ns: int

    traded_quantity: int
    withdrawn_quantity: int
    same_side_replacement_quantity: int
    opposite_side_retreat_quantity: int
    depth_at_open: int
    surviving_depth: int
    price_at_open_raw: int
    price_at_close_raw: int
    order_ids_at_open: int
    order_ids_at_close: int
    order_ids_persisting: int
    min_members_for_determinacy: int = 1
    member_count: int = 1
    # A mechanism the three carried dispositions do not describe. Supplied rather than
    # computed, because the point is to record something the classifier cannot express:
    # forcing a novel mechanism into absorbed/delivered/withdrawn is how it disappears.
    discovered_disposition: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "traded_quantity",
            "withdrawn_quantity",
            "same_side_replacement_quantity",
            "opposite_side_retreat_quantity",
            "depth_at_open",
            "surviving_depth",
        ):
            if getattr(self, name) < 0:
                raise AbsorptionError(f"{name} must be non-negative")
        if self.closed_recv_ns < self.opened_recv_ns:
            raise AbsorptionError("a runway cannot close before it opens")

    @property
    def displayed_depletion(self) -> int:
        return self.traded_quantity + self.withdrawn_quantity

    @property
    def price_response_raw(self) -> int:
        """Signed in the direction of the book side under pressure."""
        delta = self.price_at_close_raw - self.price_at_open_raw
        return delta if self.side == "B" else -delta

    @property
    def price_moved(self) -> bool:
        return self.price_at_close_raw != self.price_at_open_raw

    @property
    def order_id_turnover(self) -> int:
        return max(self.order_ids_at_open - self.order_ids_persisting, 0)

    @property
    def is_discovered_disposition(self) -> bool:
        return self.discovered_disposition is not None

    @property
    def disposition(self) -> str:
        """Which mechanism this runway exhibits.

        Order matters. A supplied discovered disposition wins outright: the carried three are
        a starting vocabulary, and a runway whose mechanism they cannot describe must be
        recordable as itself rather than rounded to the nearest carried label. Then sparsity,
        because a determinate-looking label on one or two members is the kind of finding that
        gets quoted; then withdrawal, because a runway drained by cancels is not evidence
        about demand even if price also moved.
        """
        if self.discovered_disposition is not None:
            return f"{DISCOVERED_PREFIX}_{self.discovered_disposition}"
        if self.member_count < self.min_members_for_determinacy:
            return SPARSE
        if self.displayed_depletion == 0:
            return INDETERMINATE
        if self.withdrawn_quantity > self.traded_quantity:
            return ACCOMPANIED_BY_WITHDRAWAL
        if self.traded_quantity == 0:
            return INDETERMINATE
        return DELIVERED_THROUGH_PRICE if self.price_moved else ABSORBED_WITHOUT_PRICE_MOVE

    def as_dict(self) -> dict[str, Any]:
        return {
            "runway_id": self.runway_id,
            "instrument_id": self.instrument_id,
            "source_day": self.source_day,
            "source_role": self.source_role,
            "continuity_segment": self.continuity_segment,
            "family_id": self.family_id,
            "side": self.side,
            "session_phase": self.session_phase,
            "opened_recv_ns": self.opened_recv_ns,
            "closed_recv_ns": self.closed_recv_ns,
            "elapsed_ns": self.closed_recv_ns - self.opened_recv_ns,
            "traded_quantity": self.traded_quantity,
            "withdrawn_quantity": self.withdrawn_quantity,
            "displayed_depletion": self.displayed_depletion,
            "same_side_replacement_quantity": self.same_side_replacement_quantity,
            "opposite_side_retreat_quantity": self.opposite_side_retreat_quantity,
            "depth_at_open": self.depth_at_open,
            "surviving_depth": self.surviving_depth,
            "price_at_open_raw": self.price_at_open_raw,
            "price_at_close_raw": self.price_at_close_raw,
            "price_response_raw": self.price_response_raw,
            "price_moved": self.price_moved,
            "order_ids_at_open": self.order_ids_at_open,
            "order_ids_at_close": self.order_ids_at_close,
            "order_ids_persisting": self.order_ids_persisting,
            "order_id_turnover": self.order_id_turnover,
            "member_count": self.member_count,
            "disposition": self.disposition,
            "clock": CAUSAL_CLOCK,
        }


class AbsorptionCalculator:
    """Streaming section 4.8 accumulator. Every ratio keeps both coequal forms."""

    def __init__(
        self,
        *,
        exact_cap: int | None = None,
        seed: int = 0,
        replacement_horizon_ns: int = DEFAULT_REPLACEMENT_HORIZON_NS,
    ) -> None:
        if replacement_horizon_ns <= 0:
            raise AbsorptionError("the replacement horizon must be a positive duration")
        self.replacement_horizon_ns = int(replacement_horizon_ns)
        kwargs: dict[str, Any] = {"seed": seed}
        if exact_cap is not None:
            kwargs["exact_cap"] = exact_cap

        def measure(name: str, numerator: str, missingness: str, kind: str):
            return StratifiedMeasure(
                name=name,
                declaration=Declaration(
                    numerator_formula=numerator,
                    population="causal runways within the stratum and continuity segment",
                    causal_cutoff="runway close receive time on ts_recv_ns",
                    status=RESOLVED,
                    missingness_rule=missingness,
                ),
                kind=kind,
                **kwargs,
            )

        self.absorption_ratio = measure(
            "absorption_ratio",
            "traded quantity over displayed depletion",
            "runways with zero depletion are counted as zero-denominator, never dropped",
            "RATIO_PAIR",
        )
        self.withdrawal_ratio = measure(
            "withdrawal_ratio",
            # D-7. Stated in the formula itself, because it was not stated anywhere and the
            # section read as though this were independent evidence. It is not:
            # displayed_depletion IS traded + withdrawn, so in all 192 nonempty strata
            # absorption_numerator + withdrawal_numerator equalled the denominator exactly
            # (6,546 + 38,164 = 44,710) and the two mean_of_member_ratios summed to exactly
            # 1.0. One degree of freedom, reported as two.
            "withdrawn quantity over displayed depletion; EXACTLY 1 - absorption_ratio, since "
            "displayed depletion is traded + withdrawn - retained as the complementary view, "
            "never as a second measurement",
            "runways with zero depletion are counted as zero-denominator, never dropped",
            "RATIO_PAIR",
        )
        # D-7's other half: the measure that IS independent of absorption_ratio.
        # `opposite_side_retreat_quantity` was computed per group, carried on every
        # RunwayPressure, and used in no ratio at all - so the section had a genuinely free
        # second dimension available and spent 410 averaged rows on an identity instead.
        # Traded volume against the far side stepping away separates a maker being run over
        # from a book that simply widened ahead of the trade.
        self.retreat_ratio = measure(
            "traded_over_opposite_retreat_ratio",
            "traded quantity over opposite-side retreat quantity",
            "runways where the opposite side did not retreat are counted as zero-denominator, "
            "never dropped",
            "RATIO_PAIR",
        )
        self.survival_ratio = measure(
            "depth_survival_ratio",
            "surviving depth over depth at open",
            "runways opening with zero depth are counted as zero-denominator",
            "RATIO_PAIR",
        )
        self.replacement_ratio = measure(
            "same_side_replacement_ratio",
            "same-side replacement quantity over displayed depletion",
            "runways with zero depletion are counted as zero-denominator",
            "RATIO_PAIR",
        )
        self.price_response = measure(
            "price_response_raw",
            "close price - open price, signed toward the side under pressure",
            "no exclusions; every scored runway has a price response",
            "DISTRIBUTION",
        )
        self.order_id_turnover = measure(
            "order_id_turnover",
            "order IDs present at open that did not persist to close",
            "no exclusions",
            "DISTRIBUTION",
        )

        self.scored = 0
        self.disposition_counts: dict[str, int] = {name: 0 for name in sorted(VALID_DISPOSITIONS)}
        self.discovered_dispositions: dict[str, int] = {}
        # D-8. Runways whose replacement horizon has not yet elapsed. A list, not a dict:
        # two runways on one stratum at one instant are two runways, and keying them would
        # silently keep the second one only.
        self._pending: list[_PendingReplacement] = []
        self.replacement_resolved = 0
        self.replacement_censored = 0
        self.replacement_attributions = 0
        self._now_ns: int | None = None

    @property
    def measures(self) -> tuple[StratifiedMeasure, ...]:
        return (
            self.absorption_ratio,
            self.withdrawal_ratio,
            self.retreat_ratio,
            self.survival_ratio,
            self.replacement_ratio,
            self.price_response,
            self.order_id_turnover,
        )

    def _key(self, runway: RunwayPressure) -> StratumKey:
        return StratumKey(
            source_day=runway.source_day,
            source_role=runway.source_role,
            continuity_segment=runway.continuity_segment,
            family_id=runway.family_id,
            side_orientation=runway.side,
            session_phase=runway.session_phase,
            clock=CAUSAL_CLOCK,
            subfamily_id=f"disposition={runway.disposition}",
        )

    def score(self, runway: RunwayPressure) -> dict[str, Any]:
        """Fold one runway in. Indeterminate and sparse runways stay visible, not silent."""
        key = self._key(runway)
        disposition = runway.disposition
        self.scored += 1
        if runway.is_discovered_disposition:
            self.discovered_dispositions[disposition] = (
                self.discovered_dispositions.get(disposition, 0) + 1
            )
        else:
            self.disposition_counts[disposition] += 1

        if disposition in (INDETERMINATE, SPARSE):
            # Section 4.8: zero-denominator, sparse and indeterminate members remain explicit.
            self.absorption_ratio.observe_indeterminate(key)
            self.withdrawal_ratio.observe_indeterminate(key)
            self.replacement_ratio.observe_indeterminate(key)
        else:
            depletion = float(runway.displayed_depletion)
            self.absorption_ratio.observe(key, float(runway.traded_quantity), depletion)
            self.withdrawal_ratio.observe(key, float(runway.withdrawn_quantity), depletion)
            # D-8. The replacement numerator is NOT resolved here. It opens instead, seeded
            # with whatever this group itself re-added on the side - which on this tape is
            # always zero, since a group either consumes or adds - and collects same-side
            # adds from following groups until the horizon elapses.
            self._pending.append(_PendingReplacement(
                key=key,
                denominator=depletion,
                side=runway.side,
                closed_recv_ns=runway.closed_recv_ns,
                matures_recv_ns=runway.closed_recv_ns + self.replacement_horizon_ns,
                numerator=float(runway.same_side_replacement_quantity),
            ))

        # Observed for EVERY runway, including the indeterminate and sparse ones, because
        # its denominator is the opposite side's retreat and has nothing to do with whether
        # this side's depletion was zero. Gating it on `disposition` would have made it
        # absent on exactly the runways where the far side moved and this one did not.
        self.retreat_ratio.observe(
            key, float(runway.traded_quantity), float(runway.opposite_side_retreat_quantity)
        )
        self.survival_ratio.observe(key, float(runway.surviving_depth), float(runway.depth_at_open))
        self.price_response.observe(key, float(runway.price_response_raw))
        self.order_id_turnover.observe(key, float(runway.order_id_turnover))
        return runway.as_dict()

    def note_same_side_add(self, *, side: str, quantity: int, recv_ns: int) -> int:
        """Liquidity re-added on one side, offered to every runway still inside its horizon.

        Returns how many pending runways took it. Overlap is real and is COUNTED rather than
        hidden: F-29 caught 4.7 attributing each refill to every pending episode, 18.18 times
        over, with the multiplicity invisible in the ratio's name. The same arithmetic applies
        here, so the same number is published.
        """
        self.advance(recv_ns)
        if side not in ("B", "A") or quantity <= 0:
            return 0
        attributed = 0
        for pending in self._pending:
            if pending.side != side or recv_ns < pending.closed_recv_ns:
                continue
            pending.numerator += float(quantity)
            pending.attributions += 1
            attributed += 1
        self.replacement_attributions += attributed
        return attributed

    def advance(self, recv_ns: int) -> None:
        """Resolve every pending runway whose horizon stream time has now passed.

        Never reads forward: a runway resolves only once the clock has moved beyond its
        maturity, so its numerator is complete at the moment it is read.
        """
        if self._now_ns is not None and recv_ns < self._now_ns:
            raise AbsorptionError("the receive clock cannot run backwards")
        self._now_ns = recv_ns
        still_pending = []
        for pending in self._pending:
            if recv_ns < pending.matures_recv_ns:
                still_pending.append(pending)
                continue
            self.replacement_ratio.observe(pending.key, pending.numerator, pending.denominator)
            self.replacement_resolved += 1
        self._pending = still_pending

    def close_continuity_segment(self, *, segment: int, recv_ns: int) -> list[dict[str, Any]]:
        """A continuity break censors every unmatured runway on the segment being closed.

        An add arriving in the NEXT segment is on the far side of a break in the stream, so
        it cannot be attributed to a runway that closed before it: the interval between them
        was never observed. This is the same treatment 4.6 and 4.10 give at a boundary, and
        the same reason 4.14 refuses a gap that spans one.
        """
        self.advance(recv_ns)
        still_pending = []
        for pending in self._pending:
            if pending.key.continuity_segment != segment:
                still_pending.append(pending)
                continue
            self.replacement_ratio.exclude_missing(pending.key)
            self.replacement_censored += 1
        self._pending = still_pending
        return []

    def finalize(self, *, recv_ns: int) -> list[dict[str, Any]]:
        """Close the section. Unmatured runways are CENSORED, never resolved short.

        A runway whose horizon had not elapsed has an incomplete numerator, and reporting the
        quantity it happened to have reached would be a measurement of the stream's end
        rather than of the market. It is excluded and counted, which is the same treatment
        4.6 gives a resting order that outlives the tape.
        """
        self.advance(recv_ns)
        for pending in self._pending:
            self.replacement_ratio.exclude_missing(pending.key)
            self.replacement_censored += 1
        self._pending = []
        return []

    def companion_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for measure in self.measures:
            rows.extend(measure.rows())
        return rows

    def summary(self) -> dict[str, Any]:
        return {
            "section": "4.8",
            "causal_clock": CAUSAL_CLOCK,
            "runways_scored": self.scored,
            "disposition_counts": dict(self.disposition_counts),
            "discovered_disposition_counts": dict(self.discovered_dispositions),
            "carried_dispositions_are_a_starting_vocabulary": (
                "a runway whose mechanism the carried three cannot describe is recorded under "
                "its own discovered identity rather than rounded to the nearest carried label"
            ),
            "separation_note": (
                "traded and withdrawn depletion are separate inputs: both remove displayed "
                "size but only one involves a counterparty, and pooling them would read a "
                "maker retreat as evidence of demand"
            ),
            "ratio_note": (
                "every ratio keeps mean-of-member-ratios and ratio-of-aggregate-sums as "
                "coequal views; either alone can invert the other when runway sizes are uneven"
            ),
            # D-7. The correction, in the artifact rather than in a commit message.
            "complementarity_note": (
                "absorption_ratio and withdrawal_ratio are COMPLEMENTARY, not independent: "
                "displayed depletion is traded + withdrawn, so their numerators sum to the "
                "denominator and their member ratios sum to 1.0 in every stratum. They carry "
                "one degree of freedom. traded_over_opposite_retreat_ratio is the "
                "independent second dimension and is not derivable from either"
            ),
            # D-8. What the replacement ratio actually rests on, stated rather than left
            # to be derived: how many runways resolved, how many the stream end cut
            # short, and how many (add, pending runway) pairs fed the numerators.
            "replacement_horizon_ns": self.replacement_horizon_ns,
            "replacement_resolved": self.replacement_resolved,
            "replacement_censored": self.replacement_censored,
            "replacement_attributions": self.replacement_attributions,
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
        }
