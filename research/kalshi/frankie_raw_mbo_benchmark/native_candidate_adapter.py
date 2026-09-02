"""Sections 4.10, 4.11 and 4.12 on the D66 candidate unit, as ONE vocabulary.

**Why these three are one module.** They share a definition and splitting them across files
would let it fork. 4.10's runway is opened by a candidate's birth; 4.11 measures recognition
AGAINST that birth; 4.12's stages are the runway's stages and its orientation is polarity
against the latest predecessor candidate. Three modules would each need "what is a birth" and
would each answer it, which is the `_family_id` defect of 2026-08-29 - two vocabularies for
one quantity, where nothing fails and the values simply disagree.

**The unit is a causally detected dipole flow event** (`native_candidate`), not an F_LAST
group. D66: groups stay the MEMBER unit for the group-shaped sections; these three need an
event with a before and an after, and a per-group `candidate_id` would make every runway
exactly one group long so phases could never advance.

**THE STRUCTURAL FACT THIS MODULE MAKES VISIBLE, and it is not a defect to be fixed here.**
4.11 asks for the earliest lawful call as PRIOR, T0 or H+N. A candidate whose birth IS its own
detection can never be recognised before it: the spike at `t` is not knowable until
`t + local_radius`, so every recognition against that birth is `H+N` with `N` equal to the
detection lag. **PRIOR is structurally unreachable for a candidate defined by its own
detection**, and reporting anything else would be backdating. Prebirth prediction needs a
DIFFERENT signal that precedes the spike - a precursor - and this module takes one as an
optional callback rather than inventing it. Until such a signal exists, every candidate is
honestly `H+N` and `precursor_recv_ns` stays None. That is a result about the current
evidence surface, and 4.11 keeps missed and censored members in the population precisely so
it can be read as one.

**The endpoint is entered when it HAPPENS, never looked up.** The frozen `endpoint()` walks
forward from t0 until signed flow has held the opposite polarity for `PERSIST` consecutive
seconds. Walking forward is retrospective; entering `REVERSAL` at the second the third
consecutive opposite reading arrives is the same fact observed causally, and the two agree on
where the episode ended while disagreeing about when that was knowable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_candidate import Candidate
from research.kalshi.frankie_raw_mbo_benchmark.native_dipole import (
    FLIP,
    SAME,
    DipolePath,
    DipoleStage,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_exhaustion import (
    BIRTH,
    PERSISTENCE,
    REVERSAL,
    SEARCHED,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_recognition import CandidateRecognition

NS_PER_SECOND = 1_000_000_000
PERSIST_SECONDS = 3
"""The frozen `PERSIST`: opposite polarity must hold three consecutive seconds to end it."""

DEPTH_LEVELS = 10
NO_PREDECESSOR = "NO_PREDECESSOR"
"""A segment's first candidate has nothing to be SAME or FLIP against. Declared, not defaulted.

4.12 forbids pooling SAME and FLIP, so inventing one for the first candidate would put a
fabricated orientation into a stratum key that the contract says must never mix.
"""


class CandidateAdapterError(ValueError):
    """A candidate episode could not be constructed lawfully."""


@dataclass(frozen=True)
class BookState:
    """The book at one instant, at FULL depth - not the ten-level projection.

    **MBO is the whole book.** Market-by-order carries every resting order at every price
    level; MBP-10 is a ten-level aggregate of it, and the legacy control row is that
    projection. Reading 4.12's stage depths off the legacy row therefore truncates the book to
    ten levels while the full one sits in the same frame - `FullCaptureAdapter` puts it there
    under D61, whose stated purpose includes restoring "everything below the top ten levels".
    Measured on a fourteen-level fixture: the ten-level view reports depth 30 and ten levels,
    the full view 42 and fourteen. A 29% understatement, present, typed and wrong.

    So this is built from `book_full` and the legacy projection is a declared fallback, not
    the default. `depth_scope` travels on the value: a caveat that lives only in prose expires.
    """

    bid_depth: int
    ask_depth: int
    bid_order_count: int
    ask_order_count: int
    bid_level_count: int
    ask_level_count: int
    price_raw: int
    depth_scope: str = "FULL_BOOK"

    @classmethod
    def from_full_book(cls, book: Mapping[str, Any]) -> "BookState":
        """From `frame["book_full"]` - every level, every order."""
        return cls(
            bid_depth=int(book.get("bid_depth_full") or 0),
            ask_depth=int(book.get("ask_depth_full") or 0),
            bid_order_count=int(book.get("bid_order_count_full") or 0),
            ask_order_count=int(book.get("ask_order_count_full") or 0),
            bid_level_count=int(book.get("bid_price_level_count_full") or 0),
            ask_level_count=int(book.get("ask_price_level_count_full") or 0),
            price_raw=_price_raw(book.get("mid")),
            depth_scope="FULL_BOOK",
        )

    @classmethod
    def from_legacy_row(cls, row: Mapping[str, Any]) -> "BookState":
        """From the MBP-10 projection. TEN LEVELS ONLY, and the value says so.

        Kept for a caller that has only the legacy row, and never used where `book_full` is
        available. `depth_scope` is `TOP_TEN_PROJECTION` so a consumer cannot mistake it for
        the book.
        """
        def total(prefix: str, field: str) -> int:
            return sum(
                int(row.get(f"{prefix}_{field}_{i:02d}") or 0) for i in range(DEPTH_LEVELS)
            )

        def levels(prefix: str) -> int:
            return sum(
                1 for i in range(DEPTH_LEVELS) if float(row.get(f"{prefix}_sz_{i:02d}") or 0) > 0
            )

        touch_bid = _price_raw(row.get("bid_px_00"))
        touch_ask = _price_raw(row.get("ask_px_00"))
        return cls(
            bid_depth=total("bid", "sz"),
            ask_depth=total("ask", "sz"),
            bid_order_count=total("bid", "ct"),
            ask_order_count=total("ask", "ct"),
            bid_level_count=levels("bid"),
            ask_level_count=levels("ask"),
            price_raw=(
                (touch_bid + touch_ask) // 2
                if touch_bid > 0 and touch_ask > 0
                else (touch_bid or touch_ask)
            ),
            depth_scope="TOP_TEN_PROJECTION",
        )


def _price_raw(value: Any) -> int:
    """Prices arrive as FLOAT DOLLARS on these rows; raw integer price is 1e-9 units.

    The first version did `int(value)`, which turned 3.499 into 3 - a price three orders of
    magnitude wrong, silently, on every stage. Found by asking whether MBO is deeper than ten
    levels, which it is, and which led here.
    """
    if value is None:
        return 0
    try:
        return int(round(float(value) * 1_000_000_000))
    except (TypeError, ValueError):
        return 0


EMPTY_BOOK = BookState(0, 0, 0, 0, 0, 0, 0)


@dataclass
class _Episode:
    candidate: Candidate
    stages: list[DipoleStage]
    recognition: CandidateRecognition
    orientation: str
    source_day: str
    family_id: str
    session_phase: str
    current_phase: str
    """The 4.10 phase this episode is in. It is 4.12's `event_phase` for every stage.

    One field, read by both, is the whole reason these sections share a module: a stage
    stratified by a phase 4.10 does not agree it was in is two vocabularies for one fact.
    """
    opposite_run: int = 0
    reached_persistence: bool = False
    closed: bool = False


class CandidateEpisodeTracker:
    """Drives 4.10, 4.11 and 4.12 from the causal candidate stream.

    Holds nothing across a continuity boundary: `close_segment` ends every open episode as
    censored, because section 2 forbids a calculation crossing a boundary and an episode that
    spanned the halt would report a duration the book never had.
    """

    def __init__(
        self,
        *,
        exhaustion: Any,
        recognition: Any,
        dipole: Any,
        source_role: str,
        persist_seconds: int = PERSIST_SECONDS,
        precursor_for: Callable[[Candidate], int | None] | None = None,
    ) -> None:
        if persist_seconds < 1:
            raise CandidateAdapterError("persistence must be a positive number of seconds")
        self.exhaustion = exhaustion
        self.recognition = recognition
        self.dipole = dipole
        self.source_role = source_role
        self.persist_seconds = persist_seconds
        # The only route to a PRIOR outcome. Absent, every recognition is honestly H+N.
        self.precursor_for = precursor_for
        self._open: dict[str, _Episode] = {}
        self._last_polarity: int | None = None
        self.episodes_opened = 0
        self.episodes_reversed = 0
        self.episodes_censored = 0
        self.orientation_counts: dict[str, int] = {SAME: 0, FLIP: 0, NO_PREDECESSOR: 0}
        self.paths_withheld_no_predecessor = 0

    # --- opening ----------------------------------------------------------
    def open(
        self,
        candidate: Candidate,
        *,
        source_day: str,
        family_id: str,
        session_phase: str,
        instrument_id: int,
        book: BookState = EMPTY_BOOK,
        signed_flow: int = 0,
    ) -> dict[str, Any]:
        """Open one episode: a 4.10 runway, a 4.11 record, and the first 4.12 stage."""
        if candidate.candidate_id in self._open:
            raise CandidateAdapterError(f"episode {candidate.candidate_id} is already open")
        birth_ns = candidate.event_second * NS_PER_SECOND
        available_ns = candidate.available_second * NS_PER_SECOND
        side = "B" if candidate.polarity > 0 else ("A" if candidate.polarity < 0 else "N")
        orientation = self._orientation(candidate.polarity)

        self.exhaustion.open_runway(
            candidate_id=candidate.candidate_id,
            instrument_id=instrument_id,
            side=side,
            source_day=source_day,
            source_role=self.source_role,
            continuity_segment=candidate.continuity_segment,
            family_id=family_id,
            session_phase=session_phase,
            # What was searched to find it: the trailing observations behind the bar, which
            # is the interval the detector actually consulted and not a round number.
            # The SPAN, not the observation count. Reading the count as a duration
            # understated the searched interval by 36% on a 40%-quiet tape.
            searched_coverage_ns=candidate.searched_span_seconds * NS_PER_SECOND,
            opened_recv_ns=birth_ns,
            # NO SEED STATE, deliberately. P/O/S/X describe post-fill structural dispositions
            # of an F_LAST group; a causally detected flow spike is none of them, and the
            # mission is explicit that a novel structure forced into the nearest carried label
            # "does not look like a lost discovery; it looks like a confirmation of the
            # label". The shape below is what was actually observed, so the calculator derives
            # a content-addressed open-world identity from it.
            observed_shape=self._observed_shape(candidate),
        )
        # D-11. SEARCHED was entered AND left at `birth_ns`, so its duration was exactly 0.0
        # for all 91 candidates - min = max = 0 - and the phase the contract names first
        # carried no information anywhere in the run. The searched interval is the trailing
        # window the detector actually consulted, it was already computed and passed one line
        # above as `searched_coverage_ns`, and it ENDS at the birth. So it begins that far
        # before it. That is earlier than `opened_recv_ns`, correctly: the runway opens when
        # the candidate is born, while the evidence for the birth was gathered beforehand.
        searched_ns = candidate.searched_span_seconds * NS_PER_SECOND
        self.exhaustion.enter_phase(
            candidate.candidate_id, SEARCHED, birth_ns - searched_ns
        )
        self.exhaustion.enter_phase(candidate.candidate_id, BIRTH, birth_ns)

        record = CandidateRecognition(
            candidate_id=candidate.candidate_id,
            source_day=source_day,
            source_role=self.source_role,
            continuity_segment=candidate.continuity_segment,
            family_id=family_id,
            side=side,
            session_phase=session_phase,
            birth_recv_ns=birth_ns,
        )
        precursor_ns = self.precursor_for(candidate) if self.precursor_for else None
        if precursor_ns is not None:
            record.precursor_recv_ns = precursor_ns
            record.record_call(recv_ns=precursor_ns)
        else:
            # H+N by construction, with N the detection lag. See the module docstring: a
            # candidate whose birth is its own detection cannot be recognised before it.
            record.record_call(recv_ns=available_ns)

        # 4.12 REFUSES an orientation outside {SAME, FLIP}, and it is right to. A segment's
        # first candidate has no predecessor, so it gets NO dipole path at all rather than a
        # fabricated orientation entering a stratum key the contract says must never mix.
        # 4.10's runway and 4.11's recognition are unaffected - only the dipole path is
        # withheld, and the withholding is counted so the absence is visible as a result.
        stage = None if orientation == NO_PREDECESSOR else DipoleStage(
            runway_id=candidate.candidate_id,
            stage_index=0,
            recv_ns=birth_ns,
            orientation=orientation,
            signed_flow=int(signed_flow),
            bid_depth=book.bid_depth,
            ask_depth=book.ask_depth,
            bid_order_count=book.bid_order_count,
            ask_order_count=book.ask_order_count,
            bid_level_count=book.bid_level_count,
            ask_level_count=book.ask_level_count,
            price_raw=book.price_raw,
        )
        episode = _Episode(
            candidate=candidate,
            stages=[stage] if stage is not None else [],
            recognition=record,
            orientation=orientation,
            source_day=source_day,
            family_id=family_id,
            session_phase=session_phase,
            current_phase=BIRTH,
        )
        self._open[candidate.candidate_id] = episode
        if stage is not None:
            self._observe_stage(episode, stage)
        self._last_polarity = candidate.polarity or self._last_polarity
        self.episodes_opened += 1
        self.orientation_counts[orientation] += 1
        return {
            "candidate_id": candidate.candidate_id,
            "orientation": orientation,
            "birth_recv_ns": birth_ns,
            "recognition_outcome": record.outcome,
            "detection_lag_seconds": candidate.detection_lag_seconds,
        }

    def _observe_stage(self, episode: _Episode, stage: DipoleStage) -> None:
        """Fold one stage into 4.12, stratified by the 4.10 phase it actually sat in."""
        self.dipole.observe_stage(
            stage,
            source_day=episode.source_day,
            source_role=self.source_role,
            continuity_segment=episode.candidate.continuity_segment,
            family_id=episode.family_id,
            session_phase=episode.session_phase,
            event_phase=episode.current_phase,
        )

    @staticmethod
    def _observed_shape(candidate: Candidate) -> tuple[str, ...]:
        """What was observed, in the order it was established. Deterministic, no thresholds."""
        polarity = (
            "POLARITY_UP" if candidate.polarity > 0
            else ("POLARITY_DOWN" if candidate.polarity < 0 else "POLARITY_NONE")
        )
        return (
            "DIPOLE_FLOW_SPIKE",
            polarity,
            f"SELECTION_{candidate.selection_rule}",
            f"THRESHOLD_{candidate.threshold_rule}",
        )

    def _orientation(self, polarity: int) -> str:
        """SAME or FLIP against the LATEST PREDECESSOR, which is the frozen definition."""
        if self._last_polarity is None or polarity == 0:
            return NO_PREDECESSOR
        return SAME if polarity == self._last_polarity else FLIP

    # --- the pass ---------------------------------------------------------
    def advance(
        self, second: int, *, signed_flow: int, polarity: int, book: BookState = EMPTY_BOOK
    ) -> list[dict[str, Any]]:
        """One completed second. Extends every open episode and ends the ones that reversed."""
        emitted: list[dict[str, Any]] = []
        recv_ns = second * NS_PER_SECOND
        for episode in list(self._open.values()):
            if episode.orientation != NO_PREDECESSOR:
                episode.stages.append(
                    DipoleStage(
                        runway_id=episode.candidate.candidate_id,
                        stage_index=len(episode.stages),
                        recv_ns=recv_ns,
                        orientation=episode.orientation,
                        signed_flow=int(signed_flow),
                        bid_depth=book.bid_depth,
                        ask_depth=book.ask_depth,
                        bid_order_count=book.bid_order_count,
                        ask_order_count=book.ask_order_count,
                        bid_level_count=book.bid_level_count,
                        ask_level_count=book.ask_level_count,
                        price_raw=book.price_raw,
                    )
                )
            if episode.stages:
                self._observe_stage(episode, episode.stages[-1])
            opposed = polarity != 0 and polarity != episode.candidate.polarity
            episode.opposite_run = episode.opposite_run + 1 if opposed else 0
            if not opposed and not episode.reached_persistence:
                self.exhaustion.enter_phase(
                    episode.candidate.candidate_id, PERSISTENCE, recv_ns
                )
                episode.current_phase = PERSISTENCE
                episode.reached_persistence = True
            if episode.opposite_run >= self.persist_seconds:
                emitted.append(self._close(episode, recv_ns, REVERSAL))
                self.episodes_reversed += 1
        return emitted

    def note_group_liquidity(self, *, side: str, depletion: int, refill: int) -> int:
        """Attribute one group's displayed depletion and refill to the runways it belongs to.

        D-2. Attribution is limited to episodes on the SAME side, because a bid-side runway's
        consumption is not measured by asks being pulled - and an unsided group ("N") is
        attributed to none, on the same reasoning that keeps it out of the ladder: assigning
        it to a side would fabricate one the tape declined to state.

        Returns how many runways received it, so overlap is a number the caller can carry
        rather than a multiplicity hidden inside a total. F-29 is the standing warning here:
        4.7 attributed every refill to every pending episode, 18.18 times over, and the ratio
        it produced named none of it.
        """
        if side not in ("B", "A") or (depletion == 0 and refill == 0):
            return 0
        attributed = 0
        for episode in self._open.values():
            if episode.candidate.polarity == 0:
                continue
            episode_side = "B" if episode.candidate.polarity > 0 else "A"
            if episode_side != side:
                continue
            self.exhaustion.note_liquidity(
                episode.candidate.candidate_id, depletion=depletion, refill=refill
            )
            attributed += 1
        return attributed

    def note_structure_recurrence(self, family_id: str) -> int:
        """A group of family F closed while a runway opened on family F is still running.

        D-11. `recurrence_count` was min = max = 0.0 in all 28 strata over all 91 candidates,
        because `ExhaustionCalculator.note_recurrence` existed and nothing called it. This is
        the call: 4.14's own question - did this structure happen again - answered against the
        runways that are open when it does.

        Returns how many runways were notified, so a family with several concurrent runways
        is a stated multiplicity rather than a hidden one.
        """
        notified = 0
        for episode in self._open.values():
            if episode.family_id != family_id:
                continue
            self.exhaustion.note_recurrence(episode.candidate.candidate_id)
            notified += 1
        return notified

    def _close(self, episode: _Episode, recv_ns: int, phase: str) -> dict[str, Any]:
        self.exhaustion.enter_phase(episode.candidate.candidate_id, phase, recv_ns)
        episode.current_phase = phase
        dipole_row: dict[str, Any] | None = None
        if episode.stages:
            dipole_row = self.dipole.observe_path(
                DipolePath(
                    runway_id=episode.candidate.candidate_id, stages=tuple(episode.stages)
                )
            )
        else:
            self.paths_withheld_no_predecessor += 1
        recognition_row = self.recognition.record(episode.recognition)
        episode.closed = True
        self._open.pop(episode.candidate.candidate_id, None)
        return {
            "candidate_id": episode.candidate.candidate_id,
            "terminal_phase": phase,
            "orientation": episode.orientation,
            "stage_count": len(episode.stages),
            "dipole": dipole_row,
            "dipole_path_withheld": dipole_row is None,
            "recognition": recognition_row,
            "candidate": episode.candidate.as_dict(),
        }

    def close_segment(self, recv_ns: int) -> list[dict[str, Any]]:
        """End every open episode at a boundary. Censored, never completed.

        An episode still open when the book closes did not end - it stopped being observable,
        and 4.10 keeps censored distinct from completed for exactly that reason.
        """
        rows = []
        for episode in list(self._open.values()):
            # Censoring applies to the EPISODE's duration, not to the recognition. A candidate
            # that was recognised and then had its episode cut short at the boundary is still
            # detected; overwriting its outcome with CENSORED would erase a real call and
            # understate detection. Only a candidate never recognised at all is censored here.
            if episode.recognition.outcome is None:
                episode.recognition.mark_censored()
            rows.append(self._close(episode, recv_ns, REVERSAL))
            self.episodes_censored += 1
        self._last_polarity = None
        return rows

    def summary(self) -> dict[str, Any]:
        return {
            "unit": "DIPOLE_FLOW_EVENT",
            "episodes_opened": self.episodes_opened,
            "episodes_reversed": self.episodes_reversed,
            "episodes_censored": self.episodes_censored,
            "episodes_open_at_report": len(self._open),
            "orientation_counts": dict(self.orientation_counts),
            "dipole_paths_withheld_no_predecessor": self.paths_withheld_no_predecessor,
            "persist_seconds": self.persist_seconds,
            "prior_reachable": self.precursor_for is not None,
            "prior_note": (
                "PRIOR requires a precursor signal that precedes the spike; a candidate whose "
                "birth is its own detection can only ever be recognised at H+N, and reporting "
                "otherwise would be backdating"
            ),
            "orientation_note": (
                "SAME and FLIP are polarity against the LATEST PREDECESSOR candidate, the "
                "frozen definition; a segment's first candidate is NO_PREDECESSOR rather than "
                "being given a fabricated orientation that would enter a stratum key"
            ),
        }


NO_CLUSTERING = "NO_CLUSTERING_D5"
"""D5 keeps discovery out of this run, so there is no cluster version to name.

Declared rather than left blank: an empty stratum field reads as "not recorded", and this is
"deliberately not in this run", which is a different fact.
"""


def starting_liquidity_regime(book: BookState) -> str:
    """A THRESHOLD-FREE description of the book a response starts from.

    4.16 requires the starting liquidity regime in every stratum key, and it is one of the
    four fields the prelaunch state calls "not plumbing; they are the experiment". So it is
    built the way the open-world identities are built: from the book's own shape, with no bar
    sited at a value. A fitted threshold here would be an absolute bar that cannot change
    state - the D23/D28 defect - and would silently decide which responses are comparable.

    Sign of the depth difference only, plus the structurally distinct one-sided case. A side
    with no depth is not merely more skewed than one with a little; nothing can trade there.
    """
    if book.bid_depth == 0 and book.ask_depth == 0:
        return "EMPTY_BOOK"
    if book.bid_depth == 0 or book.ask_depth == 0:
        return "ONE_SIDED_BID" if book.ask_depth == 0 else "ONE_SIDED_ASK"
    if book.bid_depth > book.ask_depth:
        return "DEPTH_SKEW_BID"
    if book.ask_depth > book.bid_depth:
        return "DEPTH_SKEW_ASK"
    return "DEPTH_EVEN"


class ResponseFeed:
    """Section 4.16's `values_for`, and the per-track baseline it needs.

    The calculator asks only at the instant a horizon is due and never reaches forward
    itself; this supplies the reading. The response is measured against the book AT THE
    TRACK'S FIRST LAWFUL INSTANT - the candidate's `available_second`, not its event second -
    because a response measured from a moment nobody could have acted on is not a response
    anyone could have captured.

    **The reading is taken at the first instant AT OR AFTER the horizon, never before.** A
    horizon that matured between two observed seconds is recorded when the traversal next
    looks, which is late by up to one second and never early. Late is a measurement property;
    early would be lookahead.
    """

    def __init__(self) -> None:
        self._baseline: dict[str, int] = {}
        self._price_raw = 0
        self.readings = 0

    def note_price(self, price_raw: int) -> None:
        self._price_raw = int(price_raw)

    def open(self, structure_id: str, price_raw: int) -> None:
        self._baseline[structure_id] = int(price_raw)

    def forget(self, structure_id: str) -> None:
        self._baseline.pop(structure_id, None)

    def values_for(self, track: Any, horizon: int) -> dict[str, float]:
        baseline = self._baseline.get(track.structure_id)
        if baseline is None:
            # No baseline means no comparable reading. Returning 0.0 would be a measurement
            # of "no move" where none was taken, so the name is omitted and the calculator
            # excludes it as missing.
            return {}
        self.readings += 1
        return {"price_response": float(self._price_raw - baseline)}
