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
from research.kalshi.frankie_raw_mbo_benchmark.native_queue_adapter import QueueGroupAdapter
from research.kalshi.frankie_raw_mbo_benchmark.native_rt_book import ReplayBook
from research.kalshi.frankie_raw_mbo_benchmark.native_candidate_adapter import (
    BookState,
    CandidateEpisodeTracker,
    EMPTY_BOOK,
    NO_CLUSTERING,
    ResponseFeed,
    starting_liquidity_regime,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_full_capture_adapter import (
    ACTIVITY_ANCHORS,
    ACTIVITY_SINCE_DECLARATION,
    RETIRED_FIXED_INTERVAL_FRAME_KEYS,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_clocks import (
    LIFECYCLE_AVAILABILITY_STAMP,
    ClockCalculator,
    member_clock_row,
    stamp_discovery_confirmations,
    stamp_model_evaluation,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_group_adapters import ladder_from_full_book
from research.kalshi.frankie_raw_mbo_benchmark.native_mirror import MatchScope
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
    """Decides when the principal model is invoked. Supplied, never inferred here.

    THE CADENCE AUDIT (S122, F-26; Greg: "Don't make cutoff times"). Every argument a policy
    receives is an EVENT or a count of events, never a time interval:

    * `group_index`, `recv_ns`: THIS cutoff - the F_LAST receive of the group that just
      closed. A cutoff's identity is the pair `(group_index, recv_ns)`: on the real Sunday
      ledgers 1,399 of 43,569 groups share an F_LAST receive nanosecond (F-feed-9, run
      33630348943), so `recv_ns` alone does not name a cutoff.
    * `mark`: the session mark of that group (segment, phase - exchange facts).
    * `groups_since_last`: a COUNT of F_LAST-closed groups since the last invocation.
    * `candidate_events`: the candidate events knowable AT this cutoff - the 4.11 calls
      emitted since the previous row (recognitions) and the 4.16 change points observed
      since it - so a policy can fire on them.

    The interval `ns_since_last` that this protocol offered before S122 is REMOVED: a policy
    firing on it would have made a cutoff a time we chose. `CADENCE_AUDIT` in the traversal
    summary records the vocabulary so the audit is a field a reader can check, not prose.
    """

    def should_invoke(
        self,
        *,
        group_index: int,
        recv_ns: int,
        mark: SessionMark,
        groups_since_last: int,
        candidate_events: Mapping[str, Any],
    ) -> bool:
        ...


CADENCE_AUDIT: dict[str, Any] = {
    "rule": "an invocation cutoff is an EVENT - the F_LAST receive of a group, or a candidate event at it - never a time we choose (D83, F-26)",
    "cutoff_identity": ["group_index", "recv_ns"],
    "cutoff_identity_note": "recv_ns alone is not unique: groups can share an F_LAST receive nanosecond (F-feed-9)",
    "policy_inputs": ["group_index", "recv_ns", "mark", "groups_since_last", "candidate_events"],
    "policy_inputs_that_are_time_intervals": [],
    "removed_at_s122": ["ns_since_last"],
    "candidate_event_kinds": ["recognitions_at_this_cutoff", "change_points_at_this_cutoff"],
}


class CandidateEventCadence:
    """Invoke at a cutoff that carries a candidate event, and never on elapsed time.

    A recognition emitted at this cutoff, or a 4.16 change point observed at it, is the
    trigger; a count of F_LAST-closed groups (`every_groups`) is the only other one, and it
    is a count of events. There is no clock in here to schedule on.
    """

    def __init__(self, *, every_groups: int | None = None) -> None:
        if every_groups is not None and every_groups <= 0:
            raise ReplayDriverError("every_groups must be a positive count of groups or None")
        self.every_groups = every_groups

    def should_invoke(
        self,
        *,
        group_index: int,
        groups_since_last: int,
        candidate_events: Mapping[str, Any],
        **_: Any,
    ) -> bool:
        if candidate_events.get("recognitions_at_this_cutoff") or candidate_events.get(
            "change_points_at_this_cutoff"
        ):
            return True
        return (
            self.every_groups is not None
            and group_index > 0
            and groups_since_last >= self.every_groups
        )


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
    flow_seconds_completed: int = 0
    """4.0 seconds judged COMPLETE and handed to the census, one exact row each.

    Zero on a consumed pass means the substrate section is dark - the state in which the
    detector and 4.12 ran on a series nothing declared, stratified or gated.
    """
    replenishment_observations: int = 0
    """4.7 removals and refills actually stated to the calculator, not horizons matured."""
    queue_rows_applied: int = 0
    """4.6 raw actions applied to the queue adapter's own book, one at a time."""
    queue_terminals: int = 0
    """4.6 lifecycles that RESOLVED inside a group. Censored ones come from the calculator."""
    candidates_without_stratum: int = 0
    """Candidates released before any group closed. Counted, never opened on empty strings."""
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
    # D-2. How many (group, open runway) pairs contributed liquidity. Overlapping
    # runways each receive the same group, so this exceeds the group count and the
    # excess IS the attribution multiplicity - stated, per F-29, never inferred.
    runway_liquidity_attributions: int = 0
    # D-11. How many (recurring group, open runway of that family) pairs were
    # notified. Zero here means the structures that recur and the structures
    # runways open on are disjoint, which is itself a finding.
    runway_structure_recurrences: int = 0
    # D-8. (same-side add, pending runway) pairs. Exceeds the add count when
    # runways overlap, and the excess IS the multiplicity - stated, per F-29.
    replacement_attributions: int = 0
    # D-4. How many full-book snapshots reached 4.2. Zero means the section is
    # dark again, which is the state that produced a 10 GB unread artifact.
    book_snapshots_summarised: int = 0
    # D-16. Members handed to 4.4's matcher. Zero means the section is dark
    # again, which is the state that produced 0 pairs and 3,454 exclusions.
    mirror_members_offered: int = 0
    # 4.0b. Seconds whose detector outcome was attributed to a stratum. Zero means the
    # section is dark, which is the state that left 4,371 rejections outside the contract.
    detector_seconds_accounted: int = 0
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


def _row_size(row: Mapping[str, Any]) -> int:
    """A row's size, absent or unreadable reading as zero rather than raising.

    Zero is the right reading here specifically: a row that states no size added no displayed
    quantity, so it contributes nothing to a replacement numerator. That is a different case
    from a row whose size is missing where one is required, which the adapters refuse.
    """
    value = row.get("size")
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


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
        emit_change_points: bool = True,
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
        # 4.16's event-driven half is ON by canonical default under D83/D88: the launcher
        # carries every lawful surface unless a declared comparison explicitly turns one off.
        # Every change point remains retained under D60; the opt-out is therefore visible in
        # the section summary rather than being allowed to masquerade as an observed zero.
        self.emit_change_points = emit_change_points
        self._last_change_point_state: tuple | None = None
        self.session_rule = session_rule
        self.cadence = cadence
        self.run = run
        self.run.response.declare_change_point_feed(enabled=emit_change_points)
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
        # 4.0 shadows this binner with one of the same class and reconciles against it on
        # every completed second, so it must bin on the same clock. The clock is declared
        # ONCE, here, where the binner is built. A first draft demanded the run be
        # constructed with a matching clock as well, and a caller who set one and not the
        # other was refused over a section they had never touched; the section now adopts
        # the driver's clock and refuses only if it has already binned rows on another.
        run.flow_substrate.declare_clock(roll20_clock)
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
        # Built LAZILY from the first mark's real segment. Seeding it with 0 stamped every
        # candidate in the first segment with a segment id that exists nowhere else in the
        # run: `segment_of` returns an absolute trade-date ordinal (18908, 18911...), and
        # 4.10, 4.11, 4.12 and 4.16 all stratify on it, so the candidate lane landed in
        # strata no group row shares and any join by segment returned empty. Wrong on the
        # FIRST segment of every run, not only across a weekend.
        self.detector: native_candidate.CausalPeakDetector | None = None
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
        # D-5. The full price ladder as it stood BEFORE the group now being processed.
        # 4.9's contract is a comparison of two consecutive full-book states, and it was
        # being handed the group's own consumed/left delta instead - which is why its
        # imbalance read exactly +/-1.0 on 152 of 154 observations. None until the first
        # frame carrying a book arrives; a fabricated empty one would read as a book
        # with no liquidity rather than as no book at all.
        self._latest_ladder: dict[str, dict[int, int]] | None = None
        self._episode_context = ("", "", "")
        self._candidate_second = 0
        self._last_signed_flow = 0
        # 4.16 rides the same unit. Its baseline is the book at the candidate's FIRST LAWFUL
        # instant, not at the spike: a response measured from a moment nobody could have
        # acted on is not a response anyone could have captured.
        self.responses = ResponseFeed(run.response.value_names)
        # 4.7's OBSERVATION half. The maturation half was already fed by
        # `replenishment.advance`; nothing ever told the calculator that a removal or a
        # refill had happened, so it matured horizons for episodes that were never opened.
        self.replenishment_observer = ReplenishmentObserver()
        # 4.6's OBSERVATION half. `QueueSurvivalCalculator` was reached only by
        # `close_continuity_segment` and `finalize`, so it censored lifecycles nobody had
        # opened - the same shape 4.7 was in. The adapter advances a book action by action
        # and reports queue position from what the book DID, never from what a row said.
        self.queue_adapter = QueueGroupAdapter()
        # One book per instrument, owned HERE and handed back unchanged at every group: the
        # adapter refuses a second book for an instrument it has already seen, because a book
        # rebuilt between groups reports every resting order as front-of-queue, which is a
        # number rather than a failure. It is deliberately NOT the replenishment observer's
        # book - two consumers calling `apply` on one book would apply every row twice.
        self._queue_books: dict[int, ReplayBook] = {}

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
        self._last_recv_ns: int | None = None
        # F-26: change points observed since the previous member row, offered to the cadence
        # policy as candidate events at this cutoff (a count, reset per row).
        self._change_points_since_row = 0
        # F-20 / D83: the receive-clock instant the driver stands at when it retains a
        # lifecycle row. `_on_group` sets it to the group's F_LAST receive and `finalize` to
        # the finalize instant, so a group-close row carries its group's F_LAST receive, a
        # segment-close row the receive that REVEALED the boundary (the first group of the
        # next segment - that is when the censoring became knowable, not the old segment's
        # last receive), and a stream-end row the instant the stream was closed.
        self._retention_recv_ns: int | None = None
        # S121 item one: the 4.11 calls emitted since the last member row was written. They
        # are stamped onto the row of the group at whose cutoff they were emitted
        # (clock_prospective_discovery_confirmation); calls emitted at stream end, where no
        # further row exists, are carried in the traversal summary instead.
        self._confirmations_pending: list[dict[str, Any]] = []
        self._confirmations_at_stream_end: list[dict[str, Any]] = []

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
        # 4.0b closes AFTER finish(): the releases finish() forces out are the segment's
        # last outcomes, and closing before them would reconcile against a detector still
        # holding peaks in its buffer. Unconditional, so a segment that searched nothing is
        # still a row rather than an omission.
        self._retain_detector_close(segment, recv_ns, occasion="SEGMENT_CLOSE")
        for section in (
            "queue", "replenishment", "exhaustion", "response", "absorption",
            # 4.0 releases the seconds the boundary left unjudged as INCOMPLETE rows. In
            # BOTH loops: S119's own recorded error was a finalize call that landed in the
            # segment-close loop and not the stream-end one, so pending state never closed.
            "flow_substrate",
        ):
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
        # AFTER the calculator censored, never instead of it. This releases the adapter's own
        # tracking; skip it and the adapter goes on naming lifecycles the calculator has
        # already closed, every one landing in `unknown_order_events` - a defect counter
        # turned into noise. The adapter refuses the next group if this call is missed.
        self.queue_adapter.close_continuity_segment(segment=segment)
        self._close_lineage(
            segment=segment, censored_status=CENSORED_SEGMENT_END, occasion="SEGMENT_CLOSE",
            recv_ns=recv_ns,
        )
        self.counters.candidate_summaries.append(self.detector.summary())
        self.counters.episode_summaries.append(self.episodes.summary())
        # The NEXT segment is opened by `_mark_for` from the new mark's own ordinal. It is
        # not `segment + 1`: segments are trade-date ordinals and a weekend skips two.

    def _close_lineage(
        self, *, segment: int, censored_status: str, occasion: str, recv_ns: int
    ) -> None:
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
                # D-9. The censoring CLOCK, which the node cannot supply for itself: a
                # stage's `exited_recv_ns` is stamped only by its own successor, and a
                # censored stage is precisely one that never got a qualifying successor. So
                # censored and "has a duration" were mutually exclusive by construction, and
                # the age channel excluded all 21,651 of them. 4.6 has no such hole because
                # its caller hands it the boundary time at the moment it censors.
                censoring_recv_ns=recv_ns,
            )
            self.counters.lineage_nodes_observed += 1
            self._retain_lifecycle([row], section="lineage", occasion=occasion)
        self.lineage_graph = LineageGraph(lineage_signature=self.lineage_signature)
        self._lineage_node_of = {}
        self._lineage_context = {}

    def _retain_lifecycle(self, rows: Any, *, section: str, occasion: str) -> None:
        """Keep every exact row a section hands back, stamped with where it came from and WHEN.

        F-20 under D83. Every section named its availability clock differently (`recv_ns`,
        `closed_recv_ns`, `terminal_recv_ns`, `exited_recv_ns`, `second`, `available_second`,
        nested `runs[].end_recv_ns`) and two named none (the mirror rows), so the causal
        stream had to place rows by a declared rule and WITHHELD what it could not place -
        60 mirror rows and 362 close-occasion rows on a 60-group fixture. A lifecycle row
        without its own availability instant is a row missing its feature-availability
        clock. `emitted_at_recv_ns` is the driver's own receive-clock instant at the moment
        of retention, stamped on every row uniformly, so availability is a FIELD the stream
        reads first (`native_causal_stream.lifecycle_availability`) and the rules remain
        only for ledgers written before the stamp existed. Design reused from the Step-1
        two-day module's per-event clock set (`event_known_by_ts_recv_ns`: the receive time
        of the record that made the event knowable); no Step-1 value is copied.
        """
        stamp = self._retention_recv_ns
        if stamp is None:
            raise ReplayDriverError(
                f"a {section} row was offered for retention ({occasion}) before the driver "
                "stood at any receive instant; a lifecycle row is not retained without its "
                "availability clock"
            )
        for row in rows or ():
            kept = dict(row)
            kept["emitting_section"] = section
            kept["emitted_on"] = occasion
            kept[LIFECYCLE_AVAILABILITY_STAMP] = stamp
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

    def _account_detector_second(self, second: int) -> None:
        """4.0b: attribute what the detector decided across this second to the live stratum.

        Read AFTER `detector.observe`, so the delta is the outcome of the second just judged
        plus any window that second closed. The section consumes the detector's counters and
        never a flow value - it accounts for the selection and cannot influence it. Phase and
        day are those of the F_LAST group whose close advanced the clock, the same
        granularity the episodes ride on.
        """
        source_day, _family_id, session_phase = self._episode_context
        self.run.detector_coverage.observe_second(
            self.detector,
            second=second,
            source_day=source_day,
            source_role=self.identity_role,
            continuity_segment=self.detector.continuity_segment,
            session_phase=session_phase,
        )
        self.counters.detector_seconds_accounted += 1

    def _retain_detector_close(self, segment: int, recv_ns: int, *, occasion: str) -> None:
        """Close 4.0b's ledger for one detector and KEEP the reconciliation row it returns.

        The close proves the partition identity and the section-versus-detector agreement,
        and raises on either failing: a judged second with no named outcome is refused, not
        binned. The row is the exact evidence beneath the section's summary, and it goes to
        the lifecycle ledger for the reason every other close on this path now does - the
        return used to be dropped.
        """
        source_day, _family_id, session_phase = self._episode_context
        row = self.run.detector_coverage.close_segment(
            self.detector,
            source_day=source_day,
            source_role=self.identity_role,
            continuity_segment=segment,
            session_phase=session_phase,
            recv_ns=recv_ns,
            occasion=occasion,
        )
        self._retain_lifecycle([row], section="detector_coverage", occasion=occasion)

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
            # 4.0 FIRST, upstream of everything that reads this second. The census is over
            # the substrate as consumed, judged at the instant the detector judges it and
            # from the very bins it is about to read.
            self._complete_flow_second(second, value=value, signed=signed, polarity=polarity)
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
            # The OTHER half of 4.16's emission rule, and it had no caller at all - the
            # eighth instance of the shape S119 closed seven of. The contract requires
            # emission "at every available event-driven change point AND at versioned fixed
            # H+N horizons"; run 33605852433 emitted only the horizons. The trigger is the
            # observable state CHANGING, never the clock: firing every second would make
            # change points a fourth fixed cadence, retaining (open tracks x seconds) under
            # D60 to record readings the horizons already carry.
            self._observe_change_points(second * NS_PER_SECOND)
            self._last_signed_flow = signed
            self._retain_candidates(self.detector.observe(second, value))
            # 4.0b, from the detector's own counters, after the second it just judged.
            self._account_detector_second(second)
        self._last_complete_second = current_second - 1

    def _complete_flow_second(
        self, second: int, *, value: float, signed: int, polarity: int
    ) -> None:
        """Hand 4.0 one COMPLETED second, stratified on the second's OWN instant.

        The phase comes from the session rule evaluated AT the second, not from the group
        that closed after it. D75 was a stage filed under a neighbouring second's phase, and
        the per-second episode lane here inherits the closing group's phase, which is that
        defect one phase ahead rather than one behind; a section whose whole job is the
        per-second census cannot carry it. The segment is the candidate LANE's, so a join
        with 4.10-4.12 on the same second lands in the same stratum; the rule's own segment
        rides on the row, and a disagreement is counted by the section rather than hidden or
        made fatal, because a recv-clock second at a trade-date boundary can lawfully differ.

        The binner's bins for the second travel as the WITNESS the section reconciles its own
        tally against. If they disagree the section refuses, and that is the point: the
        census must be over the substrate the detector was handed, not a second derivation.
        """
        source_day = self._episode_context[0]
        second_ns = second * NS_PER_SECOND
        mark = self.session_rule.classify(
            event_ns=second_ns, recv_ns=second_ns, source_day=source_day, previous=None
        )
        row = self.run.flow_substrate.complete_second(
            second,
            roll20_value=value,
            window_signed_flow=signed,
            polarity=polarity,
            buy_volume=self.roll20.buy_volume_at(second),
            sell_volume=self.roll20.sell_volume_at(second),
            source_day=source_day,
            source_role=self.identity_role,
            continuity_segment=self.detector.continuity_segment,
            session_phase=mark.session_phase,
            segment_by_rule=mark.continuity_segment,
        )
        self.counters.flow_seconds_completed += 1
        self._retain_lifecycle([row], section="flow_substrate", occasion="SECOND_COMPLETE")

    def _observe_change_points(self, recv_ns: int) -> None:
        """Emit a 4.16 change point when the observable state has actually moved.

        Enabled by default under D83/D88. An explicit comparison may set
        `emit_change_points=False`; under D60 the section records that disabled state rather
        than reporting a zero that could be mistaken for an observed absence.
        """
        if not self.emit_change_points:
            return
        fingerprint = self.responses.state_fingerprint()
        if fingerprint == self._last_change_point_state:
            return
        self._last_change_point_state = fingerprint
        self._change_points_since_row += self.run.response.observe_change_point(
            recv_ns, values_for=self.responses.change_point_values_for
        )

    def _retain_candidates(self, candidates: Any) -> None:
        """The ONE route a candidate takes into every downstream section.

        This used to write the lifecycle row and stop, while the per-second path separately
        opened the 4.10/4.11/4.12 episode and the 4.16 track. `finish()` releases - the whole
        `window_truncated` class - came through here alone, so `candidate_unit_events` counted
        them and the four sections received nothing: one lost candidate per boundary plus the
        tail of every segment. Two routes into one lane is how they disagree.
        """
        for candidate in candidates or ():
            self.counters.candidates_detected += 1
            self._retain_lifecycle(
                [candidate.as_dict()], section="candidate", occasion="CANDIDATE_LAWFUL"
            )
            self._open_candidate(candidate)

    def _open_candidate(self, candidate: Any) -> None:
        """Open the 4.10/4.11/4.12 episode and the 4.16 track for one candidate."""
        source_day, family_id, session_phase = self._episode_context
        if not source_day:
            # Nothing has closed a group yet, so there is no stratum identity to open on.
            # Counted rather than opened with empty strings, which would be a key collision
            # dressed as a missing label.
            self.counters.candidates_without_stratum += 1
            return
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
            # D-10. WHERE the regime came from, so a reader can see that it is a bare sign
            # comparison of two absolute depths and not a conditioned state. It read
            # DEPTH_SKEW_BID on all 84 at-risk rows because the sign never flipped on this
            # instrument-day - D23 applied to a stratum key: a condition that cannot change
            # state carries no information, whatever it is written in.
            starting_liquidity_regime_basis=(
                f"SIGN_OF_BID_MINUS_ASK_DEPTH@{self._latest_book.depth_scope}"
            ),
        )
        self.responses.open(
            candidate.candidate_id,
            side_orientation="B" if candidate.polarity > 0 else (
                "A" if candidate.polarity < 0 else "N"
            ),
        )
        self.counters.response_tracks_opened += 1
        opened = self.episodes.open(
            candidate,
            source_day=source_day,
            family_id=family_id,
            session_phase=session_phase,
            instrument_id=self.counters.instrument_id,
            book=self._latest_book,
            signed_flow=self._last_signed_flow,
        )
        self._retain_episode_rows([opened])
        # The call 4.11 just made, held for the member row of the cutoff at which it was made.
        self._confirmations_pending.append({
            "candidate_id": opened["candidate_id"],
            "outcome": opened["recognition_outcome"],
            "birth_recv_ns": opened["birth_recv_ns"],
            "recognized_recv_ns": opened.get("recognized_recv_ns"),
            "recognized_recv_ns_basis": opened.get("recognized_recv_ns_basis"),
        })

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
            self._start_candidate_segment(mark.continuity_segment)
        elif self._mark is None:
            self.counters.segments_opened += 1
            self._start_candidate_segment(mark.continuity_segment)
        self._mark = mark
        return mark

    def _start_candidate_segment(self, segment: int) -> None:
        """Open the candidate lane on the REAL segment, never on a counter of our own."""
        self.detector = self._new_detector(segment)
        # 4.0b opens with the detector, so its first reading is the zero every counter
        # starts from and every later delta is attributable. It also checks, here, that the
        # detector exposes no rejection this section cannot name.
        self.run.detector_coverage.open_segment(self.detector)
        self.episodes = CandidateEpisodeTracker(
            exhaustion=self.run.exhaustion,
            recognition=self.run.recognition,
            dipole=self.run.dipole,
            source_role=self.identity_role,
        )
        self._last_complete_second = None

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
        # Every lifecycle row retained from here until the next group - including the
        # segment close `_mark_for` may trigger below - is stamped at this receive.
        self._retention_recv_ns = recv_ns

        event_ns = int(envelope["ts_event_ns"])

        # The legacy rows emitted since the previous group close belong to this group, and
        # the frozen census assigns every row in a group to the group's own second. Binning
        # each row at its own timestamp splits a boundary-straddling group and yields a
        # different, entirely plausible number - see PerRowSecondBinner in the roll20 tests.
        # The clock is a DECLARATION (see native_roll20): the frozen census binned on event
        # time, this package's causal clock is receive time. Receive order is guarded above;
        # EVENT time is not, and real MBO reorders event times against receive order
        # routinely. Under EVENT_CLOCK that produced a backwards second and surfaced hours
        # into a run as a contiguity error raised inside the detector, three files from the
        # cause. It fails here instead, naming the clock.
        stamp = recv_ns if self.roll20.clock == native_roll20.RECV_CLOCK else event_ns
        group_rows = self._legacy_pending
        self._legacy_pending = []
        self.roll20.observe_group(
            group_rows,
            second=stamp // NS_PER_SECOND,
        )
        candidate_second = stamp // NS_PER_SECOND
        if (
            self._last_complete_second is not None
            and candidate_second <= self._last_complete_second
        ):
            raise ReplayDriverError(
                f"the {self.roll20.clock} clock moved backwards to second {candidate_second} "
                f"after {self._last_complete_second}; the candidate lane needs contiguous "
                "seconds, and event time is not monotone in receive order on real MBO"
            )
        self._candidate_second = candidate_second

        source_day = _source_day(source_object)
        mark = self._mark_for(event_ns, recv_ns, source_day)
        # 4.0 sees the SAME rows at the SAME second the binner just did, so its census is
        # over the substrate the detector and 4.12 actually consume. It is fed AFTER the mark
        # and not beside the binner above, deliberately: `_mark_for` closes the previous
        # continuity segment, and that close releases every second still pending in 4.0 as
        # INCOMPLETE. Fed one call earlier, the first group of every new segment would be
        # sitting in that pending buffer when the old segment closed, and would be released
        # as an incomplete second of a segment it never belonged to.
        self.run.flow_substrate.observe_group_rows(
            group_rows, second=candidate_second, source_day=source_day
        )
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
        # `activity_since` (event anchors, D83; `activity_full` until S122), `book_effects`,
        # `integrity_delta` and `capture_observations` -
        # which is precisely what D61 exists to restore, and this loop then discarded every
        # one of them. The wrapper put the data back into the frame and the traversal threw
        # it away one line later.
        #
        # So it no longer enumerates. Every frame key is carried, and anything new an adapter
        # adds arrives automatically instead of being silently dropped until someone notices.
        # Measured: member_clock_row consumes raw_actions for clocks but does not return it.
        for carried, value in frame.items():
            if carried in row:
                continue
            row[carried] = value
            self.counters.frame_keys_carried.add(carried)
        row["instrument_id"] = int(envelope["instrument_id"])
        self.counters.instrument_id = int(envelope["instrument_id"])
        full_book = frame.get("book_full")
        ladder_before = self._latest_ladder
        if isinstance(full_book, Mapping):
            # D-4. 4.2, at last given the book it exists to summarise. Read from the frame
            # that is already in hand - no new capture, no new field, no second pass.
            self.counters.book_snapshots_summarised += 1
            row["book_regime"] = self.run.book_regime.observe_snapshot(
                full_book,
                source_day=source_day,
                source_role=self.identity_role,
                continuity_segment=mark.continuity_segment,
                session_phase=mark.session_phase,
                recv_ns=recv_ns,
            )
        if isinstance(full_book, Mapping):
            self._latest_book = BookState.from_full_book(full_book)
            # D-10. The whole instant, not just its price: flow and both depth channels
            # were already in hand here and had nowhere to go.
            self.responses.note_state(
                self._latest_book,
                signed_flow_lots=self._last_signed_flow,
                ladder=self._latest_ladder,
            )
            ladder_after = ladder_from_full_book(full_book)
            if ladder_after is not None:
                self._latest_ladder = ladder_after
        ladder_after = self._latest_ladder
        self._episode_context = (
            source_day, str(structure["candidate_family_id"]), mark.session_phase
        )
        # AFTER the context exists. An episode opened without its stratum identity would
        # carry empty strings into a stratum key, which is a key collision waiting to happen
        # rather than a missing label.
        self._advance_candidates(self._candidate_second)
        # S121 item one: the two act-clocks, stamped BEFORE the row is written so the row of
        # the cutoff group carries them. Every 4.11 call emitted since the previous row rides
        # this one, at this cutoff; the cadence decision moves up here from below so the
        # invocation cutoff is on the row of the group it fires at, and the same value goes
        # into the cutoff dict as `clock_model_evaluation_ns` (native_staging copies it
        # unchanged). Nothing the decision reads depends on the sections fed below.
        stamp_discovery_confirmations(row, self._confirmations_pending)
        candidate_events = {
            "recognitions_at_this_cutoff": len(self._confirmations_pending),
            "change_points_at_this_cutoff": self._change_points_since_row,
        }
        self._confirmations_pending = []
        self._change_points_since_row = 0
        groups_since = group_index - self._last_invoke_group
        # F-26: no time interval reaches the policy. The cutoff is this group's F_LAST
        # receive; the events at it are offered; a count of groups is the only other input.
        invoke = bool(self.cadence.should_invoke(
            group_index=group_index,
            recv_ns=recv_ns,
            mark=mark,
            groups_since_last=groups_since,
            candidate_events=candidate_events,
        ))
        evaluation = stamp_model_evaluation(row, staged_at_recv_ns=recv_ns if invoke else None)
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
                book_before=ladder_before,
                book_after=ladder_after,
            ),
        )

        # Horizon-bearing sections mature in stream time, never by lookahead.
        self._retain_lifecycle(
            self.run.replenishment.advance(recv_ns),
            section="replenishment",
            occasion="HORIZON_MATURED",
        )

        if invoke:
            cutoff = {
                "group_index": group_index,
                "recv_ns": recv_ns,
                "first_lawful_availability_ns": row["clocks"]["first_lawful_availability_ns"],
                "session_phase": mark.session_phase,
                "continuity_segment": mark.continuity_segment,
                "source_day": source_day,
                # The model-evaluation clock by name. WIRING NOTE for native_staging (owned
                # elsewhere): `stage_spawn_request` copies dict(cutoff) unchanged, so this
                # reaches the spawn request today; adding "clock_model_evaluation_ns" to
                # REQUIRED_CUTOFF_KEYS makes it a required layer of the request.
                "clock_model_evaluation_ns": evaluation["value_ns"],
            }
            self.counters.invocation_cutoffs.append(cutoff)
            self._last_invoke_group = group_index
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
        # D-16. 4.4's matcher, which nothing has ever called - which is the mechanical cause
        # of the delivered run's zero pairs against 3,454 unmatched stages. Every group
        # already carries its own side string; the mirror is the side-swapped one, and the
        # coordinate is this group's receive time, which is lawful at the moment of the offer.
        # Built here from the group's own actions rather than reaching for the structure
        # descriptor, which belongs to a different method - one side string, same definition,
        # `"".join(row["side"])`, exactly as `describe_structure` forms it.
        self.counters.mirror_members_offered += 1
        self._retain_lifecycle(
            [self.run.mirror.offer(
                member_id=ctx.candidate_id,
                sides="".join(str(row.get("side", "?")) for row in actions),
                coordinate=float(ctx.recv_ns),
                scope=MatchScope(
                    source_day=ctx.source_day,
                    source_role=ctx.source_role,
                    continuity_segment=ctx.continuity_segment,
                    family_id=ctx.family_id,
                    session_phase=ctx.session_phase,
                ),
            )],
            section="mirror",
            occasion="GROUP_CLOSE",
        )
        # D-4. The other 4.2 companion the contract names by hand: group count and
        # max-actions-per-group, neither of which existed in the delivered artifact.
        self.run.book_regime.observe_group_size(
            len(actions),
            source_day=ctx.source_day,
            source_role=ctx.source_role,
            continuity_segment=ctx.continuity_segment,
            session_phase=ctx.session_phase,
        )
        # D-11. 4.14 has just said this structure occurred; 4.10 has runways open on it. The
        # calculator's `note_recurrence` existed and nothing ever called it, so
        # `recurrence_count` was min = max = 0.0 in all 28 strata over all 91 candidates.
        self.counters.runway_structure_recurrences += (
            self.episodes.note_structure_recurrence(ctx.family_id)
        )

        # --- 4.9 ladder. D-5: on the reconstructed book this is one transition per SIDE,
        # both of them, whether or not the group touched them; only the group-local fallback
        # is limited to the sides the group acted on.
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
        pressure = runway_pressure_fields(actions, ctx)
        # D-2. 4.10's phase_depletion and phase_refill were fields nothing ever wrote, so both
        # read exactly 0.0 in all 109 strata. The quantities are right here, already computed
        # for 4.8: depletion is traded plus withdrawn, refill is what was added.
        self.counters.runway_liquidity_attributions += self.episodes.note_group_liquidity(
            side=ctx.side_orientation,
            depletion=pressure["traded_quantity"] + pressure["withdrawn_quantity"],
            refill=pressure["surviving_depth"],
        )
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
                        **pressure,
                    )
                )
            ],
            section="absorption",
            occasion="GROUP_CLOSE",
        )
        self.counters.absorption_runways += 1
        # D-8. Same-side replacement necessarily happens in a LATER group - on this tape a
        # group either consumes or adds, never both, which is why the within-group numerator
        # was 0.0 in all 205 strata. The group's own adds are offered to the runways that
        # closed before it and are still inside their horizon.
        for add_side in ("B", "A"):
            added = sum(
                _row_size(row) for row in actions
                if str(row.get("action")) == "A" and str(row.get("side")) == add_side
            )
            self.counters.replacement_attributions += self.run.absorption.note_same_side_add(
                side=add_side, quantity=added, recv_ns=ctx.recv_ns
            )

        # --- 4.7 replenishment, the observation half: removals open episodes, refills are
        # attributed against the ones already pending. The calculator still owns resolution -
        # this can observe a restoration but can never report one before stream time reaches it.
        rows = self.replenishment_observer.observe_group(
            actions, ctx, calculator=self.run.replenishment
        )
        self.counters.replenishment_observations += len(rows)
        self._retain_lifecycle(rows, section="replenishment", occasion="GROUP_CLOSE")

        # --- 4.6 queue survival: the adapter walks this group's actions through its own
        # book one at a time, so a position is what the book held BEFORE the next row - not
        # a reading taken at F_LAST, which reports every order in the group as front-of-queue.
        queue = self.queue_adapter.feed_group(
            self.run.queue,
            actions,
            ctx,
            book=self._queue_books.setdefault(ctx.instrument_id, ReplayBook()),
        )
        self.counters.queue_rows_applied += int(queue["rows_applied"])
        self.counters.queue_terminals += int(queue["terminal_count"])
        # D60: `terminals` is the ONLY emission point for a lifecycle that resolved inside a
        # group. Dropping it keeps the stratified average and loses every member under it.
        self._retain_lifecycle(queue["terminals"], section="queue", occasion="GROUP_CLOSE")

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
        # Stream-end rows are stamped at the finalize instant, explicit or the last receive.
        self._retention_recv_ns = at
        # D60: every one of these RETURNS the rows it censored at stream end, and the return
        # was dropped at all four call sites.
        # Same dependency as at a segment boundary: open runways close before the calculator
        # that holds them does.
        if self.detector is not None and self._last_complete_second is not None:
            self._retain_candidates(self.detector.finish(self._last_complete_second))
            self._retain_episode_rows(self.episodes.close_segment(at))
        # 4.11 calls emitted by the stream-end release have no further member row to ride;
        # they are carried here, at the instant they were emitted, rather than dropped.
        self._confirmations_at_stream_end = [
            {**confirmation, "confirmed_at_cutoff_ns": at, "emitted_on": "STREAM_END"}
            for confirmation in self._confirmations_pending
        ]
        self._confirmations_pending = []
        # 4.0b's stream-end close, in the STREAM-END path and not the segment-close loop -
        # S119's own recorded mistake was a finalize wired into the wrong one. After
        # finish(), for the reason given at the segment boundary.
        if self.detector is not None:
            self._retain_detector_close(
                self.detector.continuity_segment, at, occasion="STREAM_END"
            )
        for section in (
            "queue", "replenishment", "exhaustion", "response", "absorption",
            # 4.0 releases the seconds the boundary left unjudged as INCOMPLETE rows. In
            # BOTH loops: S119's own recorded error was a finalize call that landed in the
            # segment-close loop and not the stream-end one, so pending state never closed.
            "flow_substrate",
        ):
            self._retain_lifecycle(
                getattr(self.run, section).finalize(recv_ns=at),
                section=section,
                occasion="STREAM_END",
            )
        # D-16. 4.4 settles its own pool rather than taking a clock: a member still pooled at
        # stream end had no counterpart arrive, and the pool decides that, not when the stream
        # stopped. `finalize` also refuses unless the population adds up - members seen equals
        # paired plus every reason counted - so a member leaving without a reason fails the
        # run instead of quietly shrinking the denominator.
        self._retain_lifecycle(
            self.run.mirror.finalize(), section="mirror", occasion="STREAM_END",
        )
        # Paired with the calculator's `finalize` above, for the boundary's reason.
        self.queue_adapter.finalize()
        # 4.13 closes here too, in the segment it is still open in. A node with no child at
        # stream end is CENSORED_STREAM_END, which is a different fact from a node whose
        # stage ended - reporting both as OPEN would have erased the distinction 4.13 is for.
        self._close_lineage(
            segment=self._mark.continuity_segment if self._mark is not None else 0,
            censored_status=CENSORED_STREAM_END,
            occasion="STREAM_END",
            recv_ns=at,
        )
        # The detector is built lazily from the first mark's real segment, so a pass that
        # consumed nothing has none. Reporting a summary for a lane that never opened would
        # be an empty stratum dressed as an observation.
        if self.detector is not None:
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
            "discovery_confirmations_at_stream_end": list(self._confirmations_at_stream_end),
            "save_points": self.counters.save_points,
            # What each fed section actually received. A section reporting strata off an
            # empty ingest is indistinguishable from one reporting a real absence, so the
            # ingest count is emitted beside the measures rather than inferred from them.
            "sections_fed": {
                "4.0_flow_seconds_completed": self.counters.flow_seconds_completed,
                "4.8_absorption_runways": self.counters.absorption_runways,
                "4.9_ladder_transitions": self.counters.ladder_transitions_fed,
                "4.13_lineage_nodes_added": self.counters.lineage_nodes_added,
                "4.13_lineage_nodes_observed": self.counters.lineage_nodes_observed,
                "4.14_recurrence_sequences": self.counters.recurrence_sequences,
                "candidate_unit_events": self.counters.candidates_detected,
                "4.10_4.11_4.12_episode_rows": self.counters.episode_rows,
                "4.16_response_tracks": self.counters.response_tracks_opened,
                "4.7_replenishment_observations": self.counters.replenishment_observations,
                "4.6_queue_rows_applied": self.counters.queue_rows_applied,
                "4.6_queue_terminals": self.counters.queue_terminals,
                "candidates_without_stratum": self.counters.candidates_without_stratum,
                "4.0b_detector_seconds_accounted": self.counters.detector_seconds_accounted,
            },
            # D66's second unit, reported per continuity segment. A segment that found NOTHING
            # is still a row here: absence is a result about that segment, not an omission.
            "candidate_detection": list(self.counters.candidate_summaries),
            "candidate_episodes": list(self.counters.episode_summaries),
            "replenishment_observation": self.replenishment_observer.summary(),
            "queue_observation": self.queue_adapter.report(),
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
            # F-20: the field every retained lifecycle row carries as its availability clock.
            "lifecycle_availability_stamp": LIFECYCLE_AVAILABILITY_STAMP,
            # D83, once per run rather than a string on every row: the fixed-seconds blocks
            # that no longer reach the member row, and the event anchors that replaced them.
            "fixed_interval_blocks_removed": list(RETIRED_FIXED_INTERVAL_FRAME_KEYS),
            "activity_anchors": list(ACTIVITY_ANCHORS),
            "activity_since_declaration": dict(ACTIVITY_SINCE_DECLARATION),
            "causal_clock": CAUSAL_CLOCK,
            "forward_only": True,
            "session_rule": type(self.session_rule).__name__,
            "cadence_policy": type(self.cadence).__name__,
            # F-26: the cadence audit as a field, not prose.
            "cadence_audit": dict(CADENCE_AUDIT),
        }
        return result
