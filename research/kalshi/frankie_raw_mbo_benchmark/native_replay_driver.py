"""The driver: walks the native stream once and feeds every calculation section.

The sixteen sections and the runner were each correct in isolation and driven by nothing.
This is what runs them.

Two things it deliberately does not decide. **Session and continuity boundaries** determine
where lifecycles are censored, where runs restart and where replenishment horizons are cut,
so a rule invented here would quietly change what every downstream section reports.
**Provider cadence** decides at which lawful cutoffs the principal model is asked anything,
which is the shape of the experiment rather than a detail of the traversal. Both are
required constructor arguments with no defaults: a driver built without them raises rather
than picking.

`replay_dbn_files` owns its adapter internally and never exposes it, so checkpointing and
resume are impossible through that entry point. This owns the adapter instead, which is what
makes a run resumable from its last save point rather than restartable only from zero. The
per-group envelope is built here rather than imported, because the full-state replay module
uses bare imports and only loads with `research/` on `sys.path`.

The traversal is forward-only. It holds no forward window, and every section it feeds is
itself forward-only, so a value that could not lawfully exist at a cutoff cannot be computed
at that cutoff - not by policy, but because the data has not been reached.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator, Mapping, Protocol, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.a_memory_member_first_recalculation_20260828 import (
    describe_structure,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_absorption import RunwayPressure
from research.kalshi.frankie_raw_mbo_benchmark.native_group_adapters import (
    GroupContext,
    ladder_transitions,
    lineage_additions,
    occurrences,
    runway_pressure_fields,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_lineage import (
    CENSORED_SEGMENT_END,
    CENSORED_STREAM_END,
    TERMINATED,
    LineageGraph,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_calculation_runner import (
    NativeCalculationRun,
    RunIdentity,
)
from research.kalshi.frankie_raw_mbo_benchmark import native_candidate, native_roll20
from research.kalshi.frankie_raw_mbo_benchmark.native_replenishment_adapter import (
    ReplenishmentObserver,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_candidate_adapter import (
    BookState,
    CandidateEpisodeTracker,
    EMPTY_BOOK,
    NO_CLUSTERING,
    ResponseFeed,
    starting_liquidity_regime,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_clocks import ClockCalculator, member_clock_row
from research.kalshi.frankie_raw_mbo_benchmark.native_session import (
    NS_PER_SECOND,
    phase_within,
    segment_of,
    trade_day,
)
from research.kalshi.frankie_raw_mbo_benchmark.periodic_checkpointer import PeriodicCheckpointer
from research.kalshi.frankie_raw_mbo_benchmark.native_full_capture_adapter import (
    FullCaptureAdapter,
)
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import V4MboAdapter

CAUSAL_CLOCK = "ts_recv_ns"


class ReplayDriverError(ValueError):
    """The traversal could not proceed lawfully."""


@dataclass(frozen=True)
class SessionMark:
    """Where one group sits in session and continuity terms."""

    session_phase: str
    continuity_segment: int
    starts_new_segment: bool = False

    def __post_init__(self) -> None:
        if not self.session_phase:
            raise ReplayDriverError("session_phase must be non-empty")
        if self.continuity_segment < 0:
            raise ReplayDriverError("continuity_segment must be non-negative")


class SessionRule(Protocol):
    """Decides session phase and continuity segment. Supplied, never inferred here.

    Takes BOTH clocks and they are not interchangeable. Session membership is an exchange
    fact about when something happened, so it is decided on `event_ns`; `recv_ns` is the
    causal availability clock and is passed for rules that need it. An earlier draft of this
    protocol offered only `recv_ns`, which would have keyed session membership on the feed's
    serialization rather than on the market.
    """

    def classify(
        self, *, event_ns: int, recv_ns: int, source_day: str, previous: SessionMark | None
    ) -> SessionMark:
        ...


class ExchangeSessionRule:
    """The D6 rule: segment and phase from the CME calendar, keyed on event time.

    Holds no state - `previous` is used only to notice that the segment changed, and the
    segment ordinal itself is absolute, so two runs over overlapping windows agree.
    """

    def classify(
        self, *, event_ns: int, recv_ns: int, source_day: str, previous: SessionMark | None
    ) -> SessionMark:
        day = trade_day(event_ns)
        segment = segment_of(day)
        return SessionMark(
            session_phase=phase_within(event_ns, day),
            continuity_segment=segment,
            starts_new_segment=previous is not None and segment != previous.continuity_segment,
        )


class CadencePolicy(Protocol):
    """Decides when the principal model is invoked. Supplied, never inferred here."""

    def should_invoke(
        self,
        *,
        group_index: int,
        recv_ns: int,
        mark: SessionMark,
        groups_since_last: int,
        ns_since_last: int,
    ) -> bool:
        ...


LINEAGE_SIGNATURE = "ORDER_ID_LINEAGE_V1"
"""What a lineage node IS in this traversal, declared rather than defaulted.

A `lineage_signature` is part of every 4.13 stratum key, so leaving it implicit would make
two runs with different lineage definitions look like one population. Under D53 the unit is
the F_LAST group, and the causal link this traversal can actually observe is between ORDER
IDS: a group's initiating order id parents the ids that group touched for the first time.
That is the whole claim, and the name says it so a later definition cannot quietly replace
it inside the same stratum.
"""

LINEAGE_SEGMENT_SCOPE = "ONE_CONTINUITY_SEGMENT"
"""The lineage graph is rebuilt at every continuity boundary, and the scope travels.

Section 2 forbids a calculation crossing a reset, snapshot, gap or session boundary unless
it models that boundary as its own structure, and `LineageCalculator` is the one section
holding cross-group state that has no `close_continuity_segment` of its own. So the graph is
closed and rebuilt here instead: depth measures lineage WITHIN one CME trade date and never
across the halt that censors every other section. Read as a whole-stream lineage it would
overstate depth by chaining across a boundary the book does not cross - the `ladder_scope`
lesson applied to the one section that could not carry it itself.
"""


@dataclass
class DriverCounters:
    groups_seen: int = 0
    records_seen: int = 0
    segments_opened: int = 0
    invocation_cutoffs: list[dict[str, Any]] = field(default_factory=list)
    save_points: int = 0
    candidates_detected: int = 0
    replenishment_observations: int = 0
    """4.7 removals and refills actually stated to the calculator, not horizons matured."""
    response_tracks_opened: int = 0
    """4.16 tracks. One per candidate, opened at its first lawful instant."""
    episode_rows: int = 0
    """4.10/4.11/4.12 rows: one per episode opened and one per episode ended."""
    instrument_id: int = 0
    frame_keys_carried: set = field(default_factory=set)
    """Every frame key that reached a member row. Named so a new one cannot vanish quietly."""
    """4.10-4.12/4.16's unit: dipole flow events detected causally from the roll20 substrate."""
    candidate_summaries: list[dict[str, Any]] = field(default_factory=list)
    episode_summaries: list[dict[str, Any]] = field(default_factory=list)
    """One per continuity segment, so a segment that found NOTHING is still visible as one."""
    legacy_rows_retained: int = 0
    """Legacy rows RETAINED, counted whether they went to a list or to a sink."""
    member_rows_retained: int = 0
    lifecycle_rows_retained: int = 0
    recurrence_sequences: int = 0
    """4.14 sequences folded in. One per group, so this equals `groups_seen` on a fed pass."""
    ladder_transitions_fed: int = 0
    """4.9 side transitions folded in - zero, one or two per group, never a fixed multiple."""
    absorption_runways: int = 0
    """4.8 runways scored. One per group under D53, where the runway IS the F_LAST group."""
    lineage_nodes_added: int = 0
    """4.13 nodes added to the live graph. Rises only when a group touches a NEW order id."""
    lineage_nodes_observed: int = 0
    """4.13 nodes folded into the calculator with a TERMINAL status, at a boundary or at end.

    Deliberately not equal to `lineage_nodes_added` until the stream ends: a node is observed
    once, when its status is finally known. Observing at creation would have reported every
    node OPEN with no stage duration, because `exited_recv_ns` is set by the arrival of a
    CHILD - so the section that exists to tell termination from censoring would have reported
    neither.
    """
    legacy_rows_seen: int = 0
    """Legacy MBP-10 control rows the adapter emitted. RETAINED IN FULL - see D60.

    They carry the projected ten-level depth (bid/ask price, size and order count at each
    level) at every trade and at group end, and `legacy_observable_crosswalk` is a
    CAUSAL_STREAM_REQUIRED registry group: `legacy_book_imbalance` cannot be computed from
    anything else this traversal keeps.

    The driver used to bind them to `_legacy` and throw them away - a silent drop of a
    required input, which is the exact failure D60 exists to stop. An interim version merely
    COUNTED them, on the reasoning that keeping ~70 fields per row across 4.26M groups was a
    memory decision. Greg overruled that, and the reasoning as well: *"i don't care about
    memory. restore every piece... let him figure out what he uses but he has to see
    everything."* Memory is not a reason to drop anything. Every row is kept.
    """
    legacy_rows: list[dict[str, Any]] = field(default_factory=list)
    """Every legacy row, verbatim, in emission order. Never sampled, capped or summarized."""
    member_rows: list[dict[str, Any]] = field(default_factory=list)
    """Every exact member row, verbatim. D60.

    `member_clock_row` builds a ~20-field exact record per group - five absolute clock
    readings, per-component event-to-receive latencies, within-group receive gaps, the
    sequence span and contiguity, the channel set - hands it to `ClockCalculator.observe`,
    and the row was then dropped. `LAYER_MEMBERS` emitted `exact_member_rows: <int>`, and the
    gate that exists to guarantee exact members beneath every summary was satisfied by that
    counter. A count is not a member.
    """
    lifecycle_rows: list[dict[str, Any]] = field(default_factory=list)
    """Every exact lifecycle and episode row returned at a boundary or at finalize. D60.

    `close_continuity_segment`, `finalize` and `replenishment.advance` each RETURN the exact
    rows they censored or matured, and every call site discarded the return. The stratified
    aggregate survived; the only emission point for a censored episode did not.
    """


def _row_recv_ns(row: Mapping[str, Any], default: int) -> int:
    """A row's receive time, falling back to the group's own. Mirrors the adapter's `_int`."""
    value = row.get("ts_recv_ns")
    return default if value is None else int(value)


def _source_day(source_object: str) -> str:
    import re

    match = re.search(r"(20\d{6})", source_object)
    if not match:
        raise ReplayDriverError(f"cannot derive a source day from {source_object}")
    return match.group(1)


class NativeReplayDriver:
    """One forward-only pass over the native stream, feeding every section."""

    def __init__(
        self,
        *,
        identity: RunIdentity,
        session_rule: SessionRule,
        cadence: CadencePolicy,
        run: NativeCalculationRun,
        adapter: V4MboAdapter | None = None,
        checkpointer: PeriodicCheckpointer | None = None,
        materialize_full_state: bool = False,
        stage_spawn: Callable[[Mapping[str, Any]], Any] | None = None,
        legacy_sink: Callable[[Mapping[str, Any]], Any] | None = None,
        roll20_clock: str = native_roll20.RECV_CLOCK,
        lineage_signature: str = LINEAGE_SIGNATURE,
        sinks: Any = None,
        candidate_selection: str = native_candidate.CAUSAL_WINDOWED_PROMINENCE,
        candidate_warmup_seconds: int = 900,
        candidate_min_observations: int = 600,
    ) -> None:
        if session_rule is None:
            raise ReplayDriverError(
                "a session rule is required: session and continuity boundaries decide what is "
                "censored, and a rule invented here would change every section's output"
            )
        if cadence is None:
            raise ReplayDriverError(
                "a cadence policy is required: when the principal model is asked anything is "
                "the shape of the experiment, not a traversal detail"
            )
        self.identity = identity
        self.session_rule = session_rule
        self.cadence = cadence
        self.run = run
        # D60: defaults to the CAPTURING adapter. `V4MboAdapter` discards the per-record
        # book effect, the reconstructed FIFO queue, the book below level ten, the per-side
        # event counts, the touch quantity for T/F/M and every anomaly magnitude. The locked
        # file is untouched - `FullCaptureAdapter` subclasses it - so a caller who needs the
        # byte-identical original can still pass one in.
        self.adapter = adapter if adapter is not None else FullCaptureAdapter()
        self.checkpointer = checkpointer
        self.materialize_full_state = materialize_full_state
        self.stage_spawn = stage_spawn
        # An OPTIONAL second home for the legacy rows, so a caller can stream them to disk as
        # they are produced. It never replaces retention: the rows are kept either way.
        self.legacy_sink = legacy_sink
        # `legacy_per_second_roll20` is a CAUSAL_STREAM_REQUIRED layer, so this is fed on
        # every pass rather than being an option a caller may forget to switch on. The
        # clock is a declaration: the frozen census binned on event time, this traversal's
        # causal clock is receive time, and the crosswalk hash changes with the choice.
        self.roll20 = native_roll20.SecondBinner(clock=roll20_clock)
        # Legacy rows emitted since the last group close. This used to be a CURSOR into the
        # fully retained list, which silently made roll20 depend on retention living in RAM:
        # stream the ledger and the slice would have read an empty tail and the per-second
        # binning would have gone quietly wrong. A pending buffer says what it is.
        self._legacy_pending: list[dict[str, Any]] = []
        # When present, the three exact ledgers are retained ON DISK. Nothing is dropped -
        # see `native_row_sink`. Absent, this class behaves exactly as before.
        self.sinks = sinks
        # D66: the CANDIDATE unit, alongside the F_LAST group MEMBER unit. Detected causally
        # from the roll20 substrate one completed second at a time, so a decision at second s
        # can consume nothing after s. Rebuilt at every continuity boundary, like lineage: a
        # trailing bar carried across the halt would be calibrated on the wrong session.
        self.candidate_selection = candidate_selection
        self.candidate_warmup_seconds = candidate_warmup_seconds
        self.candidate_min_observations = candidate_min_observations
        self.detector = self._new_detector(0)
        self._last_complete_second: int | None = None
        # 4.10 / 4.11 / 4.12 ride the candidate unit as ONE vocabulary - a runway is opened by
        # a candidate's birth, recognition is measured against that birth, and the dipole
        # path's stages are the runway's. Three separate adapters would each have to answer
        # "what is a birth" and would each answer it.
        self.episodes = CandidateEpisodeTracker(
            exhaustion=run.exhaustion,
            recognition=run.recognition,
            dipole=run.dipole,
            source_role=self.identity_role,
        )
        self._latest_book = EMPTY_BOOK
        self._episode_context = ("", "", "")
        self._candidate_second = 0
        # 4.16 rides the same unit. Its baseline is the book at the candidate's FIRST LAWFUL
        # instant, not at the spike: a response measured from a moment nobody could have
        # acted on is not a response anyone could have captured.
        self.responses = ResponseFeed()
        # 4.7's OBSERVATION half. The maturation half was already fed by
        # `replenishment.advance`; nothing ever told the calculator that a removal or a
        # refill had happened, so it matured horizons for episodes that were never opened.
        self.replenishment_observer = ReplenishmentObserver()

        # 4.13 is the one fed section whose state is not held by its calculator:
        # `LineageCalculator.observe_node` takes the graph as an argument, so the traversal
        # owns it. Rebuilt at every continuity boundary - see LINEAGE_SEGMENT_SCOPE.
        self.lineage_signature = lineage_signature
        self.lineage_graph = LineageGraph(lineage_signature=lineage_signature)
        self._lineage_node_of: dict[int, str] = {}
        self._lineage_context: dict[str, tuple[str, str]] = {}

        self.counters = DriverCounters()
        self._mark: SessionMark | None = None
        self._last_invoke_group = 0
        self._last_invoke_ns: int | None = None
        self._last_recv_ns: int | None = None

    @property
    def current_mark(self) -> SessionMark | None:
        return self._mark

    # --- boundary handling ------------------------------------------------

    def _close_segment(self, segment: int, recv_ns: int) -> None:
        """Every section that holds open state is closed at the boundary, not carried across.

        Section 2 forbids a calculation crossing a reset, snapshot, gap or session boundary,
        and each section censors differently, so the boundary is fanned out rather than
        handled in one place.
        """
        # D60: each of these RETURNS the exact rows it censored, and every call site used to
        # drop the return. They are the only emission point for a censored lifecycle.
        # EPISODES FIRST. They hold open 4.10 runways, and the fan-out below closes the
        # exhaustion calculator - an episode closing after it raises "runway is not open".
        # The ordering is a real dependency, not a preference.
        if self._last_complete_second is not None:
            self._retain_candidates(self.detector.finish(self._last_complete_second))
            self._retain_episode_rows(self.episodes.close_segment(recv_ns))
        for section in ("queue", "replenishment", "exhaustion", "response"):
            self._retain_lifecycle(
                getattr(self.run, section).close_continuity_segment(
                    segment=segment, recv_ns=recv_ns
                ),
                section=section,
                occasion="SEGMENT_CLOSE",
            )
        self._retain_lifecycle(
            self.replenishment_observer.close_continuity_segment(
                segment=segment, recv_ns=recv_ns
            ),
            section="replenishment",
            occasion="SEGMENT_CLOSE",
        )
        self._close_lineage(
            segment=segment, censored_status=CENSORED_SEGMENT_END, occasion="SEGMENT_CLOSE"
        )
        self.counters.candidate_summaries.append(self.detector.summary())
        self.counters.episode_summaries.append(self.episodes.summary())
        self.detector = self._new_detector(segment + 1)
        self.episodes = CandidateEpisodeTracker(
            exhaustion=self.run.exhaustion, recognition=self.run.recognition,
            dipole=self.run.dipole, source_role=self.identity_role,
        )
        self._last_complete_second = None

    def _close_lineage(self, *, segment: int, censored_status: str, occasion: str) -> None:
        """Observe every node in the live graph with its TERMINAL status, then rebuild.

        A node whose `exited_recv_ns` is set had a qualifying child, so its stage ended and
        it is TERMINATED. One without never ended inside the window we could observe, which
        is censoring and not a negative - 4.13 requires the two be kept apart, and the graph
        already holds the field that distinguishes them. Deciding it here rather than at
        creation is why `lineage_nodes_observed` lags `lineage_nodes_added` mid-stream.
        """
        for node in list(self.lineage_graph.nodes.values()):
            node.status = TERMINATED if node.exited_recv_ns is not None else censored_status
            source_day, session_phase = self._lineage_context[node.node_id]
            row = self.run.lineage.observe_node(
                node,
                self.lineage_graph,
                source_day=source_day,
                source_role=self.identity_role,
                continuity_segment=segment,
                session_phase=session_phase,
            )
            self.counters.lineage_nodes_observed += 1
            self._retain_lifecycle([row], section="lineage", occasion=occasion)
        self.lineage_graph = LineageGraph(lineage_signature=self.lineage_signature)
        self._lineage_node_of = {}
        self._lineage_context = {}

    def _retain_lifecycle(self, rows: Any, *, section: str, occasion: str) -> None:
        """Keep every exact row a section hands back, stamped with where it came from."""
        for row in rows or ():
            kept = dict(row)
            kept["emitting_section"] = section
            kept["emitted_on"] = occasion
            self.counters.lifecycle_rows_retained += 1
            if self.sinks is None:
                self.counters.lifecycle_rows.append(kept)
            self.run.note_lifecycle_row(row=kept)

    def _new_detector(self, segment: int) -> native_candidate.CausalPeakDetector:
        return native_candidate.CausalPeakDetector(
            continuity_segment=segment,
            selection_rule=self.candidate_selection,
            warmup_seconds=self.candidate_warmup_seconds,
            min_threshold_observations=self.candidate_min_observations,
        )

    def _advance_candidates(self, current_second: int) -> None:
        """Judge every second that is now COMPLETE. Never the current one.

        A second is complete only once the stream has moved past it, because its own trades
        are still arriving until then. Judging `current_second` here would read a partial
        bin as a finished one - present, typed, and smaller than the truth.
        """
        if self._last_complete_second is None:
            self._last_complete_second = current_second - 1
            return
        for second in range(self._last_complete_second + 1, current_second):
            value = self.roll20.rolling_value(second)
            signed, polarity = self._flow_at(second, value)
            # Episodes advance on EVERY completed second, not only on the ones that produced
            # a candidate: a runway's persistence and its reversal are properties of the
            # seconds in between, and skipping them would only ever find instant episodes.
            self._retain_episode_rows(
                self.episodes.advance(
                    second, signed_flow=signed, polarity=polarity, book=self._latest_book
                )
            )
            # 4.16 matures in STREAM time, at the first instant at or after each horizon.
            self._retain_lifecycle(
                self.run.response.advance(
                    second * NS_PER_SECOND, values_for=self.responses.values_for
                ),
                section="response",
                occasion="HORIZON_MATURED",
            )
            for candidate in self.detector.observe(second, value):
                self.counters.candidates_detected += 1
                self._retain_lifecycle(
                    [candidate.as_dict()], section="candidate", occasion="CANDIDATE_LAWFUL"
                )
                source_day, family_id, session_phase = self._episode_context
                available_ns = candidate.available_second * NS_PER_SECOND
                self.run.response.open_track(
                    structure_id=candidate.candidate_id,
                    first_lawful_recv_ns=available_ns,
                    source_day=source_day,
                    source_role=self.identity_role,
                    continuity_segment=candidate.continuity_segment,
                    family_id=family_id,
                    side_orientation="B" if candidate.polarity > 0 else (
                        "A" if candidate.polarity < 0 else "N"
                    ),
                    session_phase=session_phase,
                    cluster_version=NO_CLUSTERING,
                    starting_liquidity_regime=starting_liquidity_regime(self._latest_book),
                )
                self.responses.open(candidate.candidate_id, self._latest_book.price_raw)
                self.counters.response_tracks_opened += 1
                self._retain_episode_rows([
                    self.episodes.open(
                        candidate,
                        source_day=source_day,
                        family_id=family_id,
                        session_phase=session_phase,
                        instrument_id=self.counters.instrument_id,
                        book=self._latest_book,
                        signed_flow=signed,
                    )
                ])
        self._last_complete_second = current_second - 1

    def _retain_candidates(self, candidates: Any) -> None:
        for candidate in candidates or ():
            self.counters.candidates_detected += 1
            self._retain_lifecycle(
                [candidate.as_dict()], section="candidate", occasion="CANDIDATE_LAWFUL"
            )

    def _retain_episode_rows(self, rows: Any) -> None:
        for row in rows or ():
            self.counters.episode_rows += 1
            self._retain_lifecycle([row], section="episode", occasion="CANDIDATE_EPISODE")

    def _flow_at(self, second: int, value: float) -> tuple[int, int]:
        """Absolute signed flow in lots, and polarity from the NORMALISED imbalance.

        4.12 keeps these apart on purpose: normalised imbalance is relative and stays in
        [-1,1], absolute depth is not, and neither may be derived from the other. The lot
        count is the stage's `signed_flow`; the sign of roll20 is the direction.
        """
        window = native_roll20.DEFAULT_WINDOW
        buys = sum(self.roll20.buy_volume_at(s) for s in range(second - window + 1, second + 1))
        sells = sum(self.roll20.sell_volume_at(s) for s in range(second - window + 1, second + 1))
        polarity = 0
        if value == value:                      # NaN is no direction, never BALANCED
            polarity = 1 if value > 0 else (-1 if value < 0 else 0)
        return int(buys - sells), polarity

    def _retain_legacy(self, row: Mapping[str, Any]) -> None:
        """D60: every legacy row is kept. A sink changes where, never whether."""
        self.counters.legacy_rows_retained += 1
        if self.sinks is None:
            self.counters.legacy_rows.append(row)
        else:
            self.sinks.legacy.write(row)

    def _mark_for(self, event_ns: int, recv_ns: int, source_day: str) -> SessionMark:
        mark = self.session_rule.classify(
            event_ns=event_ns, recv_ns=recv_ns, source_day=source_day, previous=self._mark
        )
        if not isinstance(mark, SessionMark):
            raise ReplayDriverError("session rule must return a SessionMark")
        if self._mark is not None and mark.continuity_segment < self._mark.continuity_segment:
            raise ReplayDriverError("continuity segment moved backwards; stream order is causal")
        if mark.starts_new_segment and self._mark is not None:
            self._close_segment(self._mark.continuity_segment, recv_ns)
            self.counters.segments_opened += 1
        elif self._mark is None:
            self.counters.segments_opened += 1
        self._mark = mark
        return mark

    # --- the pass ---------------------------------------------------------

    def consume(self, records: Iterable[Mapping[str, Any]]) -> None:
        """Feed one source's records. Groups are handled as they close."""
        for record in records:
            source_object = record.get("source_dbn_object")
            if not source_object:
                raise ReplayDriverError("every record must name its source object")
            frame, legacy_rows = self.adapter.apply(
                record,
                raw_symbol=record.get("raw_symbol"),
                source_dbn_object=str(source_object),
                source_dbn_sha256=str(record.get("source_dbn_sha256", "")),
            )
            self.counters.records_seen += 1
            # D60: never bind an adapter output to `_`, and never drop one for size. These
            # rows are a required registry layer's only source, so every one is retained
            # verbatim in emission order.
            for legacy_row in legacy_rows:
                self.counters.legacy_rows_seen += 1
                self._legacy_pending.append(legacy_row)
                # NOT the book state - that comes from `book_full` at group close, at full
                # depth. The legacy row is a TEN-LEVEL projection and using it here truncated
                # 4.12's stages by 29% on a fourteen-level fixture. Retained under D60 and
                # consumed by the roll20 crosswalk; the book comes from the frame.
                self._retain_legacy(legacy_row)
                if self.legacy_sink is not None:
                    self.legacy_sink(legacy_row)
            if frame is None:
                continue
            self._on_group(
                {
                    "instrument_id": int(frame["instrument_id"]),
                    "ts_event_ns": int(frame["ts_event_ns"]),
                    "ts_recv_ns": int(frame["ts_recv_ns"]),
                    "causal_availability_clock": CAUSAL_CLOCK,
                    "compact_event_frame": frame,
                },
                str(source_object),
            )

    def _on_group(self, envelope: Mapping[str, Any], source_object: str) -> None:
        frame = envelope["compact_event_frame"]
        actions = frame.get("raw_actions")
        if not actions:
            raise ReplayDriverError("a closed group carries no raw actions")
        recv_ns = int(envelope["ts_recv_ns"])
        if self._last_recv_ns is not None and recv_ns < self._last_recv_ns:
            raise ReplayDriverError("receive time moved backwards; the stream is not causal")
        self._last_recv_ns = recv_ns

        event_ns = int(envelope["ts_event_ns"])

        # The legacy rows emitted since the previous group close belong to this group, and
        # the frozen census assigns every row in a group to the group's own second. Binning
        # each row at its own timestamp splits a boundary-straddling group and yields a
        # different, entirely plausible number - see PerRowSecondBinner in the roll20 tests.
        stamp = recv_ns if self.roll20.clock == native_roll20.RECV_CLOCK else event_ns
        self.roll20.observe_group(
            self._legacy_pending,
            second=stamp // NS_PER_SECOND,
        )
        self._legacy_pending = []
        self._candidate_second = stamp // NS_PER_SECOND

        source_day = _source_day(source_object)
        mark = self._mark_for(event_ns, recv_ns, source_day)
        group_index = self.counters.groups_seen
        self.counters.groups_seen += 1

        # D60: this was hardcoded True, so the gate limb comparing groups_f_last_closed to
        # groups_seen could never fire, while the frame carried the real answer all along.
        self.run.coverage.observe_group(
            group_index=group_index,
            record_count=len(actions),
            f_last_closed=bool(frame.get("event_group_complete_f_last", True)),
            cursor=recv_ns,
        )

        # D60: `describe_structure` computes roughly eighteen fields - action and side
        # strings, per-action and per-side counts, terminal action and side, distinct price
        # and order-id counts, the price span, the fill disposition, the mirror, and
        # `discovery_status`, which is the open-world signal saying whether this group matched
        # a carried family or is novel. The driver called it and kept ONE truncated hash, then
        # made a second pass over the actions to collapse the sides. A 20-hex-char hash cannot
        # be inverted back into `side_counts`, so all of it was unrecoverable.
        structure = describe_structure(actions)
        row = member_clock_row(
            {"raw_actions": list(actions)},
            group_index=group_index,
            source_day=source_day,
            source_role=self.identity_role,
            continuity_segment=mark.continuity_segment,
            family_id=str(structure["candidate_family_id"]),
            side_orientation=self._side(actions),
            session_phase=mark.session_phase,
        )
        row["structure"] = structure
        row["snapshot_bootstrap_only"] = bool(frame.get("snapshot_bootstrap_only", False))
        # D60, AND THE SECOND TIME THIS EXACT SHAPE HAS OCCURRED. This was a hardcoded list
        # of eleven keys, written against the BASE adapter's frame. `FullCaptureAdapter`
        # (D61) adds five more - `book_full` (the whole book, not the top ten levels),
        # `activity_full`, `book_effects`, `integrity_delta` and `capture_observations` -
        # which is precisely what D61 exists to restore, and this loop then discarded every
        # one of them. The wrapper put the data back into the frame and the traversal threw
        # it away one line later.
        #
        # So it no longer enumerates. Every frame key is carried, and anything new an adapter
        # adds arrives automatically instead of being silently dropped until someone notices.
        # `raw_actions` is excluded only because the member row already holds it.
        for carried, value in frame.items():
            if carried == "raw_actions" or carried in row:
                continue
            row[carried] = value
            self.counters.frame_keys_carried.add(carried)
        row["instrument_id"] = int(envelope["instrument_id"])
        self.counters.instrument_id = int(envelope["instrument_id"])
        full_book = frame.get("book_full")
        if isinstance(full_book, Mapping):
            self._latest_book = BookState.from_full_book(full_book)
            self.responses.note_price(self._latest_book.price_raw)
        self._episode_context = (
            source_day, str(structure["candidate_family_id"]), mark.session_phase
        )
        # AFTER the context exists. An episode opened without its stratum identity would
        # carry empty strings into a stratum key, which is a key collision waiting to happen
        # rather than a missing label.
        self._advance_candidates(self._candidate_second)
        row["causal_availability_clock"] = envelope["causal_availability_clock"]
        self.counters.member_rows_retained += 1
        if self.sinks is None:
            self.counters.member_rows.append(row)
        self.run.clocks.observe(row)
        self.run.note_member_row(row=row)
        self.run.note_session_assignment(
            ts_event_ns=event_ns,
            continuity_segment=mark.continuity_segment,
            session_phase=mark.session_phase,
        )

        self._feed_sections(
            actions,
            GroupContext(
                group_index=group_index,
                source_day=source_day,
                source_role=self.identity_role,
                continuity_segment=mark.continuity_segment,
                session_phase=mark.session_phase,
                family_id=str(structure["candidate_family_id"]),
                side_orientation=self._side(actions),
                event_ns=event_ns,
                recv_ns=recv_ns,
                instrument_id=int(envelope["instrument_id"]),
            ),
        )

        # Horizon-bearing sections mature in stream time, never by lookahead.
        self._retain_lifecycle(
            self.run.replenishment.advance(recv_ns),
            section="replenishment",
            occasion="HORIZON_MATURED",
        )

        groups_since = group_index - self._last_invoke_group
        ns_since = 0 if self._last_invoke_ns is None else recv_ns - self._last_invoke_ns
        if self.cadence.should_invoke(
            group_index=group_index,
            recv_ns=recv_ns,
            mark=mark,
            groups_since_last=groups_since,
            ns_since_last=ns_since,
        ):
            cutoff = {
                "group_index": group_index,
                "recv_ns": recv_ns,
                "first_lawful_availability_ns": row["clocks"]["first_lawful_availability_ns"],
                "session_phase": mark.session_phase,
                "continuity_segment": mark.continuity_segment,
                "source_day": source_day,
            }
            self.counters.invocation_cutoffs.append(cutoff)
            self._last_invoke_group = group_index
            self._last_invoke_ns = recv_ns
            if self.stage_spawn is not None:
                # STAGE, never invoke. Sol runs as an agent session over committed files;
                # the traversal's job at a cutoff is to leave a request behind, not to call
                # anything. `on_invoke` was the API-shaped verb this replaced.
                self.stage_spawn(cutoff)

        if self.checkpointer is not None:
            saved = self.checkpointer.maybe_save(
                self.adapter,
                completed_mbo_records=self.counters.records_seen,
                event_group_open=False,
            )
            if saved is not None:
                self.counters.save_points += 1

    def _feed_sections(
        self, actions: Sequence[Mapping[str, Any]], ctx: GroupContext
    ) -> None:
        """Hand this group to 4.14, 4.9, 4.8 and 4.13 as constructed domain objects.

        These four sections were built, tested and closed at their boundaries, and then fed
        by nothing: `native_group_adapters` was imported by its own test alone, so the
        traversal reported on an empty ingest while every gate passed. That is the failure
        shape this tree keeps meeting - present, well formed, attesting nothing - and the
        only cure is a call site.

        The stratum context is built ONCE, from the canonical `candidate_family_id`, and
        passed to all four. Assembling it per section is how two vocabularies for one
        quantity get born, which is the `_family_id` defect of 2026-08-29.

        Every return value is retained. Each of these methods hands back the exact row it
        folded in - the runs and gaps, the transition, the runway, the node - and dropping
        it would keep the stratified average while losing the member beneath it, which
        section 6 rejects and D60 forbids.
        """
        # --- 4.14 recurrence: one ordered occurrence sequence per group.
        self._retain_lifecycle(
            [
                self.run.recurrence.observe_sequence(
                    occurrences(actions, ctx),
                    source_day=ctx.source_day,
                    source_role=ctx.source_role,
                    family_id=ctx.family_id,
                    side_orientation=ctx.side_orientation,
                    session_phase=ctx.session_phase,
                )
            ],
            section="recurrence",
            occasion="GROUP_CLOSE",
        )
        self.counters.recurrence_sequences += 1

        # --- 4.9 ladder: one transition per side the group actually touched.
        transitions = ladder_transitions(actions, ctx)
        # 4.9 requires absolute depth and relative imbalance stay separate, so the opposite
        # side's depth is passed as its own argument rather than folded into one figure.
        # When a group touched one side only there is no opposite depth to state, and the
        # calculator excludes it as missing rather than reading the absence as zero - a zero
        # would be a measurement, and none was taken.
        depth_by_side = {side: t.after.total_depth for side, t in transitions.items()}
        for side, transition in transitions.items():
            opposite = next((d for s, d in depth_by_side.items() if s != side), None)
            self._retain_lifecycle(
                [
                    self.run.ladder.observe(
                        transition,
                        source_day=ctx.source_day,
                        source_role=ctx.source_role,
                        continuity_segment=ctx.continuity_segment,
                        family_id=ctx.family_id,
                        session_phase=ctx.session_phase,
                        opposite_side_depth=opposite,
                    )
                ],
                section="ladder",
                occasion="GROUP_CLOSE",
            )
            self.counters.ladder_transitions_fed += 1

        # --- 4.8 absorption: under D53 the runway IS this F_LAST group.
        opened_recv_ns = min(_row_recv_ns(row, ctx.recv_ns) for row in actions)
        self._retain_lifecycle(
            [
                self.run.absorption.score(
                    RunwayPressure(
                        runway_id=ctx.candidate_id,
                        instrument_id=ctx.instrument_id,
                        side=ctx.side_orientation,
                        source_day=ctx.source_day,
                        source_role=ctx.source_role,
                        continuity_segment=ctx.continuity_segment,
                        family_id=ctx.family_id,
                        session_phase=ctx.session_phase,
                        opened_recv_ns=opened_recv_ns,
                        closed_recv_ns=ctx.recv_ns,
                        **runway_pressure_fields(actions, ctx),
                    )
                )
            ],
            section="absorption",
            occasion="GROUP_CLOSE",
        )
        self.counters.absorption_runways += 1

        # --- 4.7 replenishment, the observation half: removals open episodes, refills are
        # attributed against the ones already pending. The calculator still owns resolution -
        # this can observe a restoration but can never report one before stream time reaches it.
        rows = self.replenishment_observer.observe_group(
            actions, ctx, calculator=self.run.replenishment
        )
        self.counters.replenishment_observations += len(rows)
        self._retain_lifecycle(rows, section="replenishment", occasion="GROUP_CLOSE")

        # --- 4.13 lineage: add to the live graph now, observe at the boundary.
        for addition in lineage_additions(actions, ctx, seen_order_ids=self._lineage_node_of):
            node = self.lineage_graph.add(**addition)
            order_id = int(str(node.node_id).rsplit("-", 1)[-1])
            self._lineage_node_of[order_id] = node.node_id
            self._lineage_context[node.node_id] = (ctx.source_day, ctx.session_phase)
            self.counters.lineage_nodes_added += 1

    @property
    def identity_role(self) -> str:
        return "SCORED_FINDINGS_DAY"

    @staticmethod
    def _family_id(actions: Sequence[Mapping[str, Any]]) -> str:
        """The CANONICAL candidate family id, not a second opinion about family identity.

        This used to be the action string alone. That is a different vocabulary from the one
        `a_memory_member_first_recalculation_20260828` produced when it ran the full roster
        into 4,758 candidate families - it keyed `family_id` on `candidate_family_id`, a
        hash over the full structural descriptor. Two family vocabularies over the same data
        would not have failed anything; strata would simply have been cut differently here
        than in the run this one has to reconcile against.
        """
        return str(describe_structure(actions)["candidate_family_id"])

    @staticmethod
    def _side(actions: Sequence[Mapping[str, Any]]) -> str:
        sides = {str(a.get("side", "N")) for a in actions}
        return sides.pop() if len(sides) == 1 else "MIXED"

    def finalize(self, *, recv_ns: int | None = None) -> dict[str, Any]:
        """Close every open structure, then emit the layered result."""
        at = recv_ns if recv_ns is not None else (self._last_recv_ns or 0)
        # D60: every one of these RETURNS the rows it censored at stream end, and the return
        # was dropped at all four call sites.
        # Same dependency as at a segment boundary: open runways close before the calculator
        # that holds them does.
        if self._last_complete_second is not None:
            self._retain_candidates(self.detector.finish(self._last_complete_second))
            self._retain_episode_rows(self.episodes.close_segment(at))
        for section in ("queue", "replenishment", "exhaustion", "response"):
            self._retain_lifecycle(
                getattr(self.run, section).finalize(recv_ns=at),
                section=section,
                occasion="STREAM_END",
            )
        # 4.13 closes here too, in the segment it is still open in. A node with no child at
        # stream end is CENSORED_STREAM_END, which is a different fact from a node whose
        # stage ended - reporting both as OPEN would have erased the distinction 4.13 is for.
        self._close_lineage(
            segment=self._mark.continuity_segment if self._mark is not None else 0,
            censored_status=CENSORED_STREAM_END,
            occasion="STREAM_END",
        )
        self.counters.candidate_summaries.append(self.detector.summary())
        self.counters.episode_summaries.append(self.episodes.summary())
        result = self.run.finalize()
        result["traversal"] = {
            "groups_seen": self.counters.groups_seen,
            "records_seen": self.counters.records_seen,
            "segments_opened": self.counters.segments_opened,
            # D60: these were emitted as len(). The cutoffs ARE the shape of the experiment -
            # which lawful instants the principal was asked anything at - and the output
            # recorded only how many there were.
            "invocation_cutoff_count": len(self.counters.invocation_cutoffs),
            "invocation_cutoffs": list(self.counters.invocation_cutoffs),
            "save_points": self.counters.save_points,
            # What each fed section actually received. A section reporting strata off an
            # empty ingest is indistinguishable from one reporting a real absence, so the
            # ingest count is emitted beside the measures rather than inferred from them.
            "sections_fed": {
                "4.8_absorption_runways": self.counters.absorption_runways,
                "4.9_ladder_transitions": self.counters.ladder_transitions_fed,
                "4.13_lineage_nodes_added": self.counters.lineage_nodes_added,
                "4.13_lineage_nodes_observed": self.counters.lineage_nodes_observed,
                "4.14_recurrence_sequences": self.counters.recurrence_sequences,
                "candidate_unit_events": self.counters.candidates_detected,
                "4.10_4.11_4.12_episode_rows": self.counters.episode_rows,
                "4.16_response_tracks": self.counters.response_tracks_opened,
                "4.7_replenishment_observations": self.counters.replenishment_observations,
            },
            # D66's second unit, reported per continuity segment. A segment that found NOTHING
            # is still a row here: absence is a result about that segment, not an omission.
            "candidate_detection": list(self.counters.candidate_summaries),
            "candidate_episodes": list(self.counters.episode_summaries),
            "replenishment_observation": self.replenishment_observer.summary(),
            "frame_keys_carried": sorted(self.counters.frame_keys_carried),
            "lineage_signature": self.lineage_signature,
            "lineage_segment_scope": LINEAGE_SEGMENT_SCOPE,
            "legacy_rows_seen": self.counters.legacy_rows_seen,
            "legacy_rows_retained": self.counters.legacy_rows_retained,
            **(
                {"legacy_rows": list(self.counters.legacy_rows),
                 "legacy_rows_retention": "INLINE"}
                if self.sinks is None
                else {"legacy_rows_retention": "STREAMED",
                      "legacy_rows_receipt": self.sinks.legacy.receipt()}
            ),
            "legacy_rows_streamed": self.legacy_sink is not None,
            "legacy_per_second_roll20": {
                **self.roll20.summary(),
                "crosswalk_state_hash": native_roll20.crosswalk(
                    clock=self.roll20.clock
                )["state_hash"],
            },
            "member_rows_retained": self.counters.member_rows_retained,
            "lifecycle_rows_retained": self.counters.lifecycle_rows_retained,
            "causal_clock": CAUSAL_CLOCK,
            "forward_only": True,
            "session_rule": type(self.session_rule).__name__,
            "cadence_policy": type(self.cadence).__name__,
        }
        return result
