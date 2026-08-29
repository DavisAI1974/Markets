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
from research.kalshi.frankie_raw_mbo_benchmark.native_absorption import AbsorptionCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_calculation_runner import (
    NativeCalculationRun,
    RunIdentity,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_clocks import ClockCalculator, member_clock_row
from research.kalshi.frankie_raw_mbo_benchmark.native_session import (
    phase_within,
    segment_of,
    trade_day,
)
from research.kalshi.frankie_raw_mbo_benchmark.periodic_checkpointer import PeriodicCheckpointer
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


@dataclass
class DriverCounters:
    groups_seen: int = 0
    records_seen: int = 0
    segments_opened: int = 0
    invocation_cutoffs: list[dict[str, Any]] = field(default_factory=list)
    save_points: int = 0
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
        self.adapter = adapter if adapter is not None else V4MboAdapter()
        self.checkpointer = checkpointer
        self.materialize_full_state = materialize_full_state
        self.stage_spawn = stage_spawn
        # An OPTIONAL second home for the legacy rows, so a caller can stream them to disk as
        # they are produced. It never replaces retention: the rows are kept either way.
        self.legacy_sink = legacy_sink

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
        for section in ("queue", "replenishment", "exhaustion", "response"):
            self._retain_lifecycle(
                getattr(self.run, section).close_continuity_segment(
                    segment=segment, recv_ns=recv_ns
                ),
                section=section,
                occasion="SEGMENT_CLOSE",
            )

    def _retain_lifecycle(self, rows: Any, *, section: str, occasion: str) -> None:
        """Keep every exact row a section hands back, stamped with where it came from."""
        for row in rows or ():
            kept = dict(row)
            kept["emitting_section"] = section
            kept["emitted_on"] = occasion
            self.counters.lifecycle_rows.append(kept)
            self.run.note_lifecycle_row(row=kept)

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
                self.counters.legacy_rows.append(legacy_row)
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
        for carried in ("book", "activity", "integrity", "sequence", "ts_in_delta_ns",
                        "publisher_id", "channel_id", "raw_symbol", "adapter_revision",
                        "native_priority_id_exposed", "fifo_priority_reconstructed"):
            if carried in frame:
                row[carried] = frame[carried]
        row["instrument_id"] = int(envelope["instrument_id"])
        row["causal_availability_clock"] = envelope["causal_availability_clock"]
        self.counters.member_rows.append(row)
        self.run.clocks.observe(row)
        self.run.note_member_row(row=row)
        self.run.note_session_assignment(
            ts_event_ns=event_ns,
            continuity_segment=mark.continuity_segment,
            session_phase=mark.session_phase,
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
        for section in ("queue", "replenishment", "exhaustion", "response"):
            self._retain_lifecycle(
                getattr(self.run, section).finalize(recv_ns=at),
                section=section,
                occasion="STREAM_END",
            )
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
            "legacy_rows_seen": self.counters.legacy_rows_seen,
            "legacy_rows_retained": len(self.counters.legacy_rows),
            "legacy_rows": list(self.counters.legacy_rows),
            "legacy_rows_streamed": self.legacy_sink is not None,
            "member_rows_retained": len(self.counters.member_rows),
            "lifecycle_rows_retained": len(self.counters.lifecycle_rows),
            "causal_clock": CAUSAL_CLOCK,
            "forward_only": True,
            "session_rule": type(self.session_rule).__name__,
            "cadence_policy": type(self.cadence).__name__,
        }
        return result
