"""Section 4.0: the per-second flow and quote substrate, which fed everything and reported to nothing.

**Why this exists.** The principal proposed it after run 33605852433 (the assessment's "Is
there a calculation not in the contract that should be?", item (a)). That run already
computed `traversal.legacy_per_second_roll20`: 22,380 legacy observable rows, 2,028 trades,
474 buy / 488 sell seconds classified by midpoint with the tape's side field never consulted,
8 excluded at mid, 1 with no quote. It is the substrate on which the candidate detector and
all of 4.12 run, and it was not one of the sixteen sections - no averaged companion, no
declaration block, no stratum, no acceptance gate. That is why the 51.6% NO_DIRECTION share
in 4.12 had to be explained from traversal counters rather than from a section, and why
nobody could check whether the classification rule was right. It is 4.0 because it is
upstream of everything.

**What it measures.** One exact row per COMPLETED second on the traversal's declared binning
clock. A second is complete once the stream has moved past it, so its bins are final - the
same rule the candidate lane judges by, and the reason a second is never classified while
its own trades are still arriving. Each row carries the second's own classified buy and sell
volume, its trade dispositions, the quote the last classifiable trade was judged against, and
the trailing-window quantities downstream consumed AT that second: the roll20 value the
detector saw, and the window signed flow and polarity 4.12's stages were built from.

**The classification rule is not restated here.** The declaration cites
`native_roll20.CALCULATION` verbatim, and the per-trade dispositions come from a
`SecondBinner` of the same class the traversal feeds - read back as counter deltas, so the
rule lives in exactly one place and a paraphrase cannot drift from it. At completion the
section's per-second volumes are RECONCILED against the traversal's own binner and a
disagreement REFUSES rather than reports: two computations of one number that are never
compared are two numbers (the `rolling_value` lesson, applied one layer up).

**Nothing is dropped (D60).** Every completed second receives exactly one class, and a second
that cannot be classified is a CLASS, never a gap: NO_DIRECTION (no trades, or balanced
classified volume), EXCLUDED_AT_MID (trades, every one priced exactly at the mid), NO_QUOTE
(trades, none with a usable touch to form a mid from), UNUSABLE_PRICE_OR_SIZE (trade rows the
substrate could not use at all). A second still open when a continuity segment or the stream
ends is INCOMPLETE - retained as an exact row with its partial tallies, counted, and kept
OUTSIDE the census denominator, because judging a partial bin as a finished one is precisely
what completion exists to prevent.

**On the stratum.** Seconds are not F_LAST groups and have no family, so the family slot
carries a name that says so rather than a blank (the D-14 shape: an empty slot is the absence
of a statement, not a statement of absence). Side is the OUTCOME being counted, so it cannot
also be a stratum key. The session phase is the phase of the second's OWN instant, never the
phase of the group that happened to close after it - D75 was exactly a stage filed under a
neighbouring second's phase, and a per-second section that inherited a group's phase would
rebuild that defect one phase ahead instead of one behind.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark import native_roll20
from research.kalshi.frankie_raw_mbo_benchmark.native_stratum import (
    RESOLVED,
    Declaration,
    StratifiedMeasure,
    StratumKey,
)

SECTION = "4.0"
CAUSAL_CLOCK = "ts_recv_ns"

SUBSTRATE_FAMILY = "PER_SECOND_SUBSTRATE_NO_FAMILY"
"""The family slot for a per-second row. Seconds have no candidate family; the slot says so."""

SIDE_IS_THE_OUTCOME = "BOTH"
"""The side slot. A census OF sides cannot be stratified BY side, so both are in every row."""

# --- the own-second classification: exactly one per completed second ---------------------
BUY = "BUY"
SELL = "SELL"
NO_DIRECTION = "NO_DIRECTION"
EXCLUDED_AT_MID = "EXCLUDED_AT_MID"
NO_QUOTE = "NO_QUOTE"
UNUSABLE_PRICE_OR_SIZE = "UNUSABLE_PRICE_OR_SIZE"
CLASSIFICATIONS = (BUY, SELL, NO_DIRECTION, EXCLUDED_AT_MID, NO_QUOTE, UNUSABLE_PRICE_OR_SIZE)

# --- why a second is NO_DIRECTION, kept apart because they are different facts -----------
NO_TRADES = "NO_TRADES"
BALANCED = "BALANCED"
NOT_APPLICABLE = "NOT_APPLICABLE"

# --- the trailing-window direction 4.12 consumed at that second ---------------------------
# 4.12's own vocabulary (`native_dipole.LONG / SHORT / NO_DIRECTION`), restated by value so
# this module does not import a downstream section: a zero window flow is NO_DIRECTION,
# never a default. This is the census Frankie reconstructed from counters.
WINDOW_LONG = "LONG"
WINDOW_SHORT = "SHORT"
WINDOW_NO_DIRECTION = "NO_DIRECTION"
WINDOW_DIRECTIONS = (WINDOW_LONG, WINDOW_SHORT, WINDOW_NO_DIRECTION)

# --- a second the traversal never judged --------------------------------------------------
INCOMPLETE_SEGMENT_END = "INCOMPLETE_SEGMENT_END"
INCOMPLETE_STREAM_END = "INCOMPLETE_STREAM_END"

QUOTE_ROW = "QUOTE_ROW"
"""A legacy row that is not a trade. Counted on the second so `rows` reconciles with the binner."""


class FlowSubstrateError(ValueError):
    """The per-second substrate could not be accounted for consistently."""


def _finite(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return out if math.isfinite(out) else float("nan")


@dataclass
class SecondTally:
    """Everything the substrate produced for one second, before it is judged complete."""

    second: int
    source_day: str
    rows: int = 0
    trades: int = 0
    """Trade rows the binner could use: `price > 0 and size > 0`. Its own `trades_seen`."""
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    buy_trades: int = 0
    sell_trades: int = 0
    at_mid_trades: int = 0
    no_quote_trades: int = 0
    unusable_trades: int = 0
    last_quote: dict[str, float] | None = None
    """The touch the LAST classifiable trade in the second was judged against, verbatim."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "trades": self.trades,
            "buy_volume": self.buy_volume,
            "sell_volume": self.sell_volume,
            "net_volume": self.buy_volume - self.sell_volume,
            "buy_trades": self.buy_trades,
            "sell_trades": self.sell_trades,
            "at_mid_trades": self.at_mid_trades,
            "no_quote_trades": self.no_quote_trades,
            "unusable_trades": self.unusable_trades,
            "last_quote": dict(self.last_quote) if self.last_quote else None,
        }


def classify_second(tally: SecondTally) -> tuple[str, str]:
    """The own-second class and, when it is NO_DIRECTION, the reason.

    Precedence, stated because a second can hold several dispositions at once: any
    classified volume decides the class on its sign; balanced classified volume is
    NO_DIRECTION for the reason BALANCED; with nothing classified, a missing quote outranks
    a trade at the mid, because without a touch there is no mid to be at; then unusable
    rows; then nothing at all. Every branch returns, so every second gets exactly one class.
    """
    if tally.buy_volume > tally.sell_volume:
        return BUY, NOT_APPLICABLE
    if tally.sell_volume > tally.buy_volume:
        return SELL, NOT_APPLICABLE
    if tally.buy_volume > 0.0:
        return NO_DIRECTION, BALANCED
    if tally.no_quote_trades:
        return NO_QUOTE, NOT_APPLICABLE
    if tally.at_mid_trades:
        return EXCLUDED_AT_MID, NOT_APPLICABLE
    if tally.unusable_trades:
        return UNUSABLE_PRICE_OR_SIZE, NOT_APPLICABLE
    return NO_DIRECTION, NO_TRADES


def window_direction(window_signed_flow: int) -> str:
    """4.12's stage rule at this second: sign of the trailing-window flow, zero is none."""
    if window_signed_flow > 0:
        return WINDOW_LONG
    if window_signed_flow < 0:
        return WINDOW_SHORT
    return WINDOW_NO_DIRECTION


class FlowSubstrateCalculator:
    """Streaming section 4.0 accumulator over the per-second roll20 substrate.

    Fed twice by the traversal, at two different moments, because the two facts become
    known at two different times: the rows of a group are handed over at group close, at
    the group's own second (`observe_group_rows`); the second is JUDGED only once the stream
    has moved past it (`complete_second`), which is when the traversal's own binner holds the
    final bins this section reconciles against.
    """

    def __init__(
        self,
        *,
        clock: str = native_roll20.RECV_CLOCK,
        exact_cap: int | None = None,
        seed: int = 0,
    ) -> None:
        # The clock is a DECLARATION, exactly as it is for the binner it shadows: the same
        # rows binned on event time are a different series. The constructor refuses an
        # unknown clock through the binner's own check rather than repeating it.
        self._binner = native_roll20.SecondBinner(clock=clock)
        self.clock = clock
        kwargs: dict[str, Any] = {"seed": seed}
        if exact_cap is not None:
            kwargs["exact_cap"] = exact_cap

        population = (
            "every COMPLETED second on the traversal's declared binning clock within the "
            "day, role, continuity segment and session phase of the second's own instant; a "
            "completed second is one the stream has moved past, so its bins are final; a "
            "second with no rows at all is a member; seconds still open at a continuity or "
            "stream boundary are INCOMPLETE and are outside this population"
        )
        cutoff = (
            "the completed second; judged only once the stream has advanced beyond it, so "
            "nothing after the second is consumed"
        )
        no_missing = (
            "none: every completed second receives exactly one class, so no member is ever "
            "excluded and `excluded_missing_members` is zero by construction; a second that "
            "cannot be classified is a CLASS, never a gap"
        )

        def share(name: str, numerator: str) -> StratifiedMeasure:
            return StratifiedMeasure(
                name=name,
                declaration=Declaration(
                    numerator_formula=numerator,
                    population=population,
                    causal_cutoff=cutoff,
                    status=RESOLVED,
                    missingness_rule=no_missing,
                ),
                **kwargs,
            )

        # The averaged view is a CENSUS and nothing else: one indicator per class, whose
        # stratum mean is the class share and whose n is the completed-second denominator
        # the share is over. The exact rows already carry every volume and count; a mean of
        # those would answer no question the rows do not.
        self.class_share: dict[str, StratifiedMeasure] = {
            klass: share(
                f"second_class_share_{klass}",
                f"1.0 if the completed second's own classified volume puts it in class "
                f"{klass}, else 0.0; classification rule: {native_roll20.CALCULATION} "
                "Class precedence: sign of (buy_volume - sell_volume) when either is "
                "positive; BALANCED equal positive volume is NO_DIRECTION; otherwise "
                "NO_QUOTE outranks EXCLUDED_AT_MID outranks UNUSABLE_PRICE_OR_SIZE; a second "
                "with no trade rows is NO_DIRECTION for the reason NO_TRADES",
            )
            for klass in CLASSIFICATIONS
        }
        self.window_share: dict[str, StratifiedMeasure] = {
            direction: share(
                f"window_direction_share_{direction}",
                f"1.0 if the sign of the trailing {native_roll20.DEFAULT_WINDOW}-second "
                f"signed flow at the completed second is {direction} under 4.12's stage "
                "rule (positive LONG, negative SHORT, zero NO_DIRECTION, never a default), "
                "else 0.0",
            )
            for direction in WINDOW_DIRECTIONS
        }

        self._pending: dict[int, SecondTally] = {}
        self._last_completed: int | None = None
        self._max_binned: int | None = None
        self.rows_observed = 0
        self.seconds_completed = 0
        self.seconds_incomplete = 0
        self.empty_seconds_never_completed = 0
        self.volume_reconciliations = 0
        self.boundary_skew_seconds = 0
        self.census: dict[str, int] = {klass: 0 for klass in CLASSIFICATIONS}
        self.no_direction_reasons: dict[str, int] = {NO_TRADES: 0, BALANCED: 0}
        self.window_census: dict[str, int] = {d: 0 for d in WINDOW_DIRECTIONS}
        self.incomplete_by_reason: dict[str, int] = {
            INCOMPLETE_SEGMENT_END: 0,
            INCOMPLETE_STREAM_END: 0,
        }
        self.trade_dispositions: dict[str, int] = {
            "buy": 0, "sell": 0, "at_mid": 0, "no_quote": 0, "unusable": 0, "quote_rows": 0,
        }

    @property
    def measures(self) -> tuple[StratifiedMeasure, ...]:
        return tuple(self.class_share.values()) + tuple(self.window_share.values())

    def declare_clock(self, clock: str) -> None:
        """Adopt the traversal's binning clock. ONE declaration point, and it is the driver's.

        A first draft required the run and the driver to be constructed with matching clocks
        and refused at construction when they were not - so a caller who set the driver's
        clock and not the run's was refused over a section they had never touched. The
        driver owns the binner, so the driver owns the declaration; the section adopts it,
        and refuses only if rows have already been binned on another clock, because THAT
        would be two series under one name.
        """
        if clock == self.clock:
            return
        if self.rows_observed or self.seconds_completed or self._pending:
            raise FlowSubstrateError(
                f"section 4.0 has already binned rows on {self.clock} and cannot be moved to "
                f"{clock}; a series binned on another clock is another series"
            )
        self._binner = native_roll20.SecondBinner(clock=clock)
        self.clock = clock

    # --- ingest: rows at the group's second ----------------------------------------------

    def observe_group_rows(
        self,
        rows: Sequence[Mapping[str, Any]],
        *,
        second: int,
        source_day: str,
    ) -> SecondTally:
        """Fold one F_LAST group's legacy rows in at the group's own second.

        The same assignment the traversal's binner makes - every row of a group at the
        group's second - because the census must be over the substrate that was actually
        consumed, not over a second re-derivation that splits a boundary-straddling group.
        """
        if isinstance(second, bool) or not isinstance(second, int):
            raise FlowSubstrateError("a second is an int on the declared clock")
        if not source_day:
            raise FlowSubstrateError("a group's rows carry their source day; none was given")
        if self._last_completed is not None and second <= self._last_completed:
            raise FlowSubstrateError(
                f"rows arrived for second {second} after it was completed at "
                f"{self._last_completed}; a completed second's bins are final by definition"
            )
        tally = self._pending.get(second)
        if tally is None:
            tally = SecondTally(second=second, source_day=source_day)
            self._pending[second] = tally
        elif tally.source_day != source_day:
            raise FlowSubstrateError(
                f"second {second} received rows from two source days "
                f"({tally.source_day}, {source_day}); a second belongs to one"
            )
        for row in rows:
            self._observe_row(row, second, tally)
        if self._max_binned is None or second > self._max_binned:
            self._max_binned = second
        return tally

    def _observe_row(self, row: Mapping[str, Any], second: int, tally: SecondTally) -> str:
        """One row's disposition, read as the binner's counter deltas.

        The binner is the ONLY implementation of the midpoint rule. Reading its counters
        before and after one row tells this section what the rule did to that row without a
        second copy of the rule existing anywhere - which is the only arrangement under which
        "the classification rule is right" can be checked in one place.
        """
        b = self._binner
        before = (
            b.trades_seen, b.excluded_unusable_price_or_size, b.excluded_no_quote,
            b.excluded_at_mid, b.buy.get(second, 0.0), b.sell.get(second, 0.0),
        )
        b.observe_group((row,), second=second)
        after = (
            b.trades_seen, b.excluded_unusable_price_or_size, b.excluded_no_quote,
            b.excluded_at_mid, b.buy.get(second, 0.0), b.sell.get(second, 0.0),
        )
        self.rows_observed += 1
        tally.rows += 1

        if after[1] > before[1]:
            tally.unusable_trades += 1
            self.trade_dispositions["unusable"] += 1
            return UNUSABLE_PRICE_OR_SIZE
        if after[0] == before[0]:
            self.trade_dispositions["quote_rows"] += 1
            return QUOTE_ROW
        tally.trades += 1
        if after[2] > before[2]:
            tally.no_quote_trades += 1
            self.trade_dispositions["no_quote"] += 1
            return NO_QUOTE
        # From here the row had a usable touch, so the quote it was judged against is a
        # fact about the row worth retaining verbatim - the "quote state used to classify".
        bid = _finite(row.get(native_roll20.BID_TOUCH_FIELD))
        ask = _finite(row.get(native_roll20.ASK_TOUCH_FIELD))
        tally.last_quote = {"bid": bid, "ask": ask, "mid": 0.5 * (bid + ask)}
        if after[3] > before[3]:
            tally.at_mid_trades += 1
            self.trade_dispositions["at_mid"] += 1
            return EXCLUDED_AT_MID
        if after[4] > before[4]:
            tally.buy_trades += 1
            tally.buy_volume = after[4]
            self.trade_dispositions["buy"] += 1
            return BUY
        if after[5] > before[5]:
            tally.sell_trades += 1
            tally.sell_volume = after[5]
            self.trade_dispositions["sell"] += 1
            return SELL
        # A usable trade that moved no counter and no bin is a rule this module does not
        # know. Refusing is the only honest answer: counting it anywhere would be inventing
        # a disposition, and dropping it is what D60 forbids.
        raise FlowSubstrateError(
            f"a trade row at second {second} was accepted by the binner and left no trace "
            "in any counter or bin; the midpoint rule has a branch this section does not "
            "account for"
        )

    # --- judgement: one completed second ---------------------------------------------

    @staticmethod
    def _key(
        *,
        source_day: str,
        source_role: str,
        continuity_segment: int,
        session_phase: str,
    ) -> StratumKey:
        return StratumKey(
            source_day=source_day,
            source_role=source_role,
            continuity_segment=continuity_segment,
            family_id=SUBSTRATE_FAMILY,
            side_orientation=SIDE_IS_THE_OUTCOME,
            session_phase=session_phase,
            clock=CAUSAL_CLOCK,
        )

    def complete_second(
        self,
        second: int,
        *,
        roll20_value: float,
        window_signed_flow: int,
        polarity: int,
        buy_volume: float,
        sell_volume: float,
        source_day: str,
        source_role: str,
        continuity_segment: int,
        session_phase: str,
        segment_by_rule: int | None = None,
    ) -> dict[str, Any]:
        """Judge one COMPLETED second and return its exact row.

        `source_day` is the completing group's, used only for a second that carried no rows.

        `buy_volume` and `sell_volume` are the TRAVERSAL's binner's bins for this second.
        They are not used as the measurement - the section's own tally is - they are the
        witness the tally must agree with. Both were produced by the same rule from the same
        rows in the same order, so the floats are bit-identical when the feed is right and
        any difference means the traversal handed this section a different substrate from
        the one it handed the detector.
        """
        if isinstance(second, bool) or not isinstance(second, int):
            raise FlowSubstrateError("a second is an int on the declared clock")
        if self._last_completed is not None and second <= self._last_completed:
            raise FlowSubstrateError(
                f"second {second} completed at or before the last completed second "
                f"{self._last_completed}; a second is judged once, forward only"
            )
        tally = self._pending.pop(second, None)
        if tally is None:
            tally = SecondTally(second=second, source_day=source_day)
        # A second WITH rows is filed under the source object its rows came from; the
        # caller's `source_day` serves the seconds that carried nothing, which have no source
        # of their own and take the lane's - the group that completed them, as 4.10-4.12 do.
        # Within one continuity segment the two differ only across a FILE seam (the Sunday
        # file and the Monday file share Monday's trade date), and refusing there would kill
        # a roster run at every seam over a difference that is not a defect.
        source_day = tally.source_day
        if tally.buy_volume != float(buy_volume) or tally.sell_volume != float(sell_volume):
            raise FlowSubstrateError(
                f"second {second}: the section tallied buy {tally.buy_volume} / sell "
                f"{tally.sell_volume} but the traversal's binner holds buy {buy_volume} / "
                f"sell {sell_volume}; the census would be over a different substrate from "
                "the one the detector and 4.12 consumed"
            )
        self.volume_reconciliations += 1
        self._last_completed = second

        klass, reason = classify_second(tally)
        direction = window_direction(int(window_signed_flow))
        key = self._key(
            source_day=source_day,
            source_role=source_role,
            continuity_segment=continuity_segment,
            session_phase=session_phase,
        )
        for candidate, measure in self.class_share.items():
            measure.observe(key, 1.0 if candidate == klass else 0.0)
        for candidate, measure in self.window_share.items():
            measure.observe(key, 1.0 if candidate == direction else 0.0)

        self.seconds_completed += 1
        self.census[klass] += 1
        if klass == NO_DIRECTION:
            self.no_direction_reasons[reason] += 1
        self.window_census[direction] += 1
        # A recv-clock second at a trade-date boundary can belong, by event time, to the
        # next trade date while the candidate lane it was judged in is still the previous
        # one. It is filed under the LANE's segment so a join with 4.10-4.12 on the same
        # second lands in the same stratum, and the disagreement is stamped on the row and
        # counted here rather than either hidden or made fatal.
        if segment_by_rule is not None and segment_by_rule != continuity_segment:
            self.boundary_skew_seconds += 1

        defined = roll20_value == roll20_value
        return {
            "second": second,
            "binning_clock": self.clock,
            "clock": CAUSAL_CLOCK,
            "source_day": source_day,
            "source_role": source_role,
            "continuity_segment": continuity_segment,
            "segment_by_rule": segment_by_rule,
            "session_phase": session_phase,
            "classification": klass,
            "no_direction_reason": reason,
            **tally.as_dict(),
            "window_seconds": native_roll20.DEFAULT_WINDOW,
            "window_signed_flow": int(window_signed_flow),
            "window_direction": direction,
            "polarity": int(polarity),
            "roll20_defined": defined,
            "roll20_value": float(roll20_value) if defined else None,
            "status": RESOLVED,
        }

    # --- boundaries: what the traversal never judged --------------------------------

    def _release_pending(
        self, *, reason: str, segment: int | None, recv_ns: int
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for second in sorted(self._pending):
            tally = self._pending.pop(second)
            self.seconds_incomplete += 1
            self.incomplete_by_reason[reason] += 1
            rows.append({
                "second": second,
                "binning_clock": self.clock,
                "clock": CAUSAL_CLOCK,
                "source_day": tally.source_day,
                "continuity_segment": segment,
                "classification": None,
                "status": reason,
                "released_recv_ns": int(recv_ns),
                # No phase and no class: the second was never judged, and stamping either
                # would present a partial bin as a finished reading.
                "incomplete_note": (
                    "rows were binned at this second and the stream ended before it was "
                    "complete; tallies are partial, and the second is outside the census "
                    "denominator"
                ),
                **tally.as_dict(),
            })
        # Seconds in the unjudged tail that carried no rows at all. They are not members
        # of anything and produce no row, but they are how many seconds the tail was, so a
        # reader can see the population boundary rather than infer it.
        if self._last_completed is not None and self._max_binned is not None:
            tail = self._max_binned - self._last_completed
            self.empty_seconds_never_completed += max(0, tail - len(rows))
        self._max_binned = None
        return rows

    def close_continuity_segment(self, *, segment: int, recv_ns: int) -> list[dict[str, Any]]:
        """Release the seconds a continuity boundary left unjudged, as INCOMPLETE rows."""
        return self._release_pending(
            reason=INCOMPLETE_SEGMENT_END, segment=segment, recv_ns=recv_ns
        )

    def finalize(self, *, recv_ns: int) -> list[dict[str, Any]]:
        """Release the seconds the stream's end left unjudged, as INCOMPLETE rows."""
        return self._release_pending(reason=INCOMPLETE_STREAM_END, segment=None, recv_ns=recv_ns)

    # --- outputs -----------------------------------------------------------------------

    def companion_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for measure in self.measures:
            rows.extend(measure.rows())
        return rows

    @staticmethod
    def _shares(counts: Mapping[str, int], denominator: int) -> dict[str, float | None]:
        return {
            name: (count / denominator) if denominator else None
            for name, count in counts.items()
        }

    def summary(self) -> dict[str, Any]:
        return {
            "section": SECTION,
            "causal_clock": CAUSAL_CLOCK,
            "binning_clock": self.clock,
            "window_seconds": native_roll20.DEFAULT_WINDOW,
            "classification_rule": native_roll20.CALCULATION,
            "tape_side_field_consulted": False,
            "rows_observed": self.rows_observed,
            "trade_dispositions": dict(self.trade_dispositions),
            "seconds_completed": self.seconds_completed,
            "census_denominator": self.seconds_completed,
            "census": dict(self.census),
            "census_shares": self._shares(self.census, self.seconds_completed),
            "no_direction_reasons": dict(self.no_direction_reasons),
            "window_census": dict(self.window_census),
            "window_census_shares": self._shares(self.window_census, self.seconds_completed),
            "seconds_incomplete": self.seconds_incomplete,
            "incomplete_by_reason": dict(self.incomplete_by_reason),
            "empty_seconds_never_completed": self.empty_seconds_never_completed,
            "seconds_still_pending": len(self._pending),
            "volume_reconciliations": self.volume_reconciliations,
            "boundary_skew_seconds": self.boundary_skew_seconds,
            "population_note": (
                "the census denominator is COMPLETED seconds only; INCOMPLETE seconds are "
                "retained as exact rows with partial tallies and are not in any share"
            ),
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
        }
