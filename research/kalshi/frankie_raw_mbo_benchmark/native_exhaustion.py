"""Section 4.10: exhaustion state, birth, persistence, and completion.

A candidate's runway is a sequence of segments between recorded LANDMARKS, and section
4.10 draws two hard lines around it. "Never average across phases of the same event" - so
the landmark is part of the stratum identity, and folding two segments of one runway into
one figure is a key collision that cannot happen rather than a mistake to avoid. And
"never use completed duration at an earlier causal cutoff" - so a runway's completed
duration is simply not readable until it has completed; asking for it early raises instead
of returning the value that will eventually be true.

The landmarks are `T0`, `ENDPOINT_ONSET` and `ENDPOINT_CONFIRMATION`, recovered from the
prior exhaustion program rather than named here. A runway that never marks `T0` is a
lawful runway with no birth - which is how the negative class is carried, rather than
being unrepresentable.

`P/O/S/X` are seed annotations, never an allowlist. Anything that does not match a seed
receives a deterministic open-world ID derived from its own observed shape, so a novel
state is preserved with an identity rather than forced into the nearest known label.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_stratum import (
    CENSORED,
    RESOLVED,
    STILL_OPEN,
    Declaration,
    StratifiedMeasure,
    StratumKey,
)

CAUSAL_CLOCK = "ts_recv_ns"

# Ordered: a runway may skip landmarks but never revisit an earlier one.
#
# These three names are RECOVERED, not chosen. The prior exhaustion program defines a
# runway as `t0 -> dynamic endpoint`, and it records the endpoint with TWO timestamps
# rather than one: `structural_onset_idx` is the first second of the qualifying run - when
# the thing began - and `causal_confirmation_idx` is the third, the earliest instant at
# which the run may lawfully be asserted
# (`ng_exhaustion_chain_canonical_table_20260817.py:220-267`, `PERSIST = 3`). Confirmation
# is usable as a CLOCK and never as evidence.
#
# The eleven-name ladder that stood here (SEARCHED, PRECURSOR, PREBIRTH, FIRST_DEVIATION,
# BIRTH, TRANSITION, INFLECTION, PERSISTENCE, EXTENSION, COMPLETION, REVERSAL) was a
# 2026-08-28 invention whose whole provenance was one prose line. Not one of the eleven names is
# a phase in the built corpus, and four were reused for a DIFFERENT referent, which is
# worse than absence because it reads as continuity: BIRTH is an instant, TRANSITION is a
# chain edge BETWEEN events, EXTENSION is the chain reaching depth D+1, and REVERSAL is a
# price-outcome class computed after the endpoint. `FIRST_DEVIATION` and `INFLECTION` occur
# nowhere. PREBIRTH in particular is a timing REGION and explicitly "never a phase".
T0 = "T0"
ENDPOINT_ONSET = "ENDPOINT_ONSET"
ENDPOINT_CONFIRMATION = "ENDPOINT_CONFIRMATION"
LANDMARK_ORDER = (
    T0,
    ENDPOINT_ONSET,
    ENDPOINT_CONFIRMATION,
)
# Not a landmark: the stratum-key placeholder for a runway that closed before anything was
# marked on it. It names the absence so such a runway still lands in a key rather than
# borrowing the first rung of the ladder and reading as a birth that never happened.
UNMARKED = "UNMARKED"
# Positions are floats so a discovered landmark can be inserted between two carried ones
# without renumbering. The carried names are a starting vocabulary in exactly the sense
# SEED_STATES is: a crosswalk, never an allowlist, and never the set of landmarks a runway
# is allowed to have.
LANDMARK_INDEX: dict[str, float] = {n: float(i) for i, n in enumerate(LANDMARK_ORDER)}
DISCOVERED_LANDMARKS: dict[str, dict[str, Any]] = {}
TERMINAL_LANDMARKS = frozenset({ENDPOINT_CONFIRMATION})


def register_discovered_landmark(name: str, *, after: str, before: str | None = None) -> float:
    """Admit a landmark the carried vocabulary does not contain.

    A discovered landmark declares where it sits relative to landmarks already known, so
    ordering stays checkable, and it is recorded as discovered so it is never mistaken for
    a carried one. Registering the same landmark twice at the same position is idempotent;
    re-registering it somewhere else is refused, because a landmark that moves is a
    different landmark.
    """
    if not name or not isinstance(name, str):
        raise ExhaustionError("a discovered landmark needs a non-empty name")
    if after not in LANDMARK_INDEX:
        raise ExhaustionError(f"unknown anchor landmark: {after}")
    upper = LANDMARK_INDEX[before] if before is not None else None
    if before is not None and before not in LANDMARK_INDEX:
        raise ExhaustionError(f"unknown anchor landmark: {before}")
    lower = LANDMARK_INDEX[after]
    if upper is None:
        candidates = sorted(v for v in LANDMARK_INDEX.values() if v > lower)
        upper = candidates[0] if candidates else lower + 2.0
    if upper <= lower:
        raise ExhaustionError("a discovered landmark must sit strictly between its anchors")
    position = (lower + upper) / 2.0
    if name in LANDMARK_INDEX:
        if abs(LANDMARK_INDEX[name] - position) > 1e-12:
            raise ExhaustionError(f"landmark {name} is already registered at a different position")
        return LANDMARK_INDEX[name]
    LANDMARK_INDEX[name] = position
    DISCOVERED_LANDMARKS[name] = {"after": after, "before": before, "position": position}
    return position

SEED_STATES = {
    "P": "persistent_exhaustion",
    "O": "collapsed_opposite_flow_reversal",
    "S": "collapsed_same_flow_reload",
    "X": "collapsed_sparse_indeterminate",
}
OPEN_WORLD_PREFIX = "OW"

COMPLETED = "COMPLETED"
CENSORED_SEGMENT_END = "CENSORED_SEGMENT_END"
CENSORED_STREAM_END = "CENSORED_STREAM_END"
OPEN = "OPEN"


class ExhaustionError(ValueError):
    """A runway could not be constructed consistently."""


def open_world_state_id(shape: Sequence[str]) -> str:
    """Deterministic identity for a state that matches no seed.

    Content-derived so the same observed shape always yields the same ID across runs and
    across arms, which is what makes an unmatched state comparable rather than merely
    unlabelled.
    """
    if not shape:
        raise ExhaustionError("an open-world state needs an observed shape")
    digest = hashlib.sha256("|".join(shape).encode("utf-8")).hexdigest()[:16]
    return f"{OPEN_WORLD_PREFIX}_{digest}"


DISCOVERED_NAMED_STATES: dict[str, str] = {}
DISCOVERED_PREFIX = "DS"


def register_discovered_state(name: str, shape: Sequence[str]) -> str:
    """Give a discovered structure a durable name instead of only a hash.

    An open-world hash is stable and comparable but says nothing. When a structure recurs
    often enough to be worth naming, this records the name against the shape that earned it,
    so it can be referred to without being mistaken for one of the four carried seeds.
    """
    if not name or not isinstance(name, str):
        raise ExhaustionError("a discovered state needs a non-empty name")
    if name in SEED_STATES:
        raise ExhaustionError(f"{name} is a carried seed; discovered names must be distinct")
    identity = open_world_state_id(shape)
    existing = DISCOVERED_NAMED_STATES.get(name)
    if existing is not None and existing != identity:
        raise ExhaustionError(f"discovered state {name} is already bound to a different shape")
    DISCOVERED_NAMED_STATES[name] = identity
    return f"{DISCOVERED_PREFIX}_{name}"


def resolve_state_id(seed: str | None, shape: Sequence[str]) -> str:
    """Seeds are a crosswalk, never an allowlist, and never the set of states that exist.

    Three lawful outcomes: a carried seed passes through; `None` yields a content-derived
    open-world identity; and a registered discovered name yields its own durable identity.
    An unregistered name is refused so a typo cannot silently become a new state.
    """
    if seed is None:
        return open_world_state_id(shape)
    if seed in SEED_STATES:
        return seed
    if seed.startswith(f"{DISCOVERED_PREFIX}_"):
        bare = seed[len(DISCOVERED_PREFIX) + 1 :]
        if bare in DISCOVERED_NAMED_STATES:
            return seed
        raise ExhaustionError(f"{seed} is not a registered discovered state")
    if seed in DISCOVERED_NAMED_STATES:
        return f"{DISCOVERED_PREFIX}_{seed}"
    raise ExhaustionError(
        f"{seed} is neither a carried seed nor a registered discovered state; pass seed=None "
        "for an open-world identity, or register it with register_discovered_state"
    )


@dataclass
class RunwaySegment:
    """The interval a runway spends at one landmark, from that mark to the next."""

    landmark: str
    entered_recv_ns: int
    exited_recv_ns: int | None = None
    depletion: int = 0
    refill: int = 0
    absorption: int = 0

    @property
    def duration_ns(self) -> int | None:
        if self.exited_recv_ns is None:
            return None
        return self.exited_recv_ns - self.entered_recv_ns

    def as_dict(self) -> dict[str, Any]:
        return {
            "landmark": self.landmark,
            "entered_recv_ns": self.entered_recv_ns,
            "exited_recv_ns": self.exited_recv_ns,
            "duration_ns": self.duration_ns,
            "depletion": self.depletion,
            "refill": self.refill,
            "absorption": self.absorption,
        }


@dataclass
class ExhaustionRunway:
    """One candidate's complete causal runway."""

    candidate_id: str
    instrument_id: int
    side: str
    source_day: str
    source_role: str
    continuity_segment: int
    family_id: str
    session_phase: str
    state_id: str
    searched_coverage_ns: int
    opened_recv_ns: int
    segments: list[RunwaySegment] = field(default_factory=list)
    falsifiers: list[str] = field(default_factory=list)
    alternative_hypotheses: list[str] = field(default_factory=list)
    recurrences: int = 0
    status: str = OPEN
    closed_recv_ns: int | None = None

    @property
    def current_segment(self) -> RunwaySegment | None:
        return self.segments[-1] if self.segments else None

    @property
    def birth_recv_ns(self) -> int | None:
        """The ONSET, never the confirmation, and `None` when no birth was marked.

        The prior program separates a target's own birth second (`t0_idx`) from the
        confirmation an observer may act on, and those differ by `PERSIST - 1`. A single
        landmark populated from a confirmation shifts every downstream class boundary
        later, turning births into priors. So this is the onset. A runway that never
        marked `T0` returns `None` rather than a substitute: that is the negative case -
        a boundary with no birth - and it has to be representable to be counted.
        """
        for segment in self.segments:
            if segment.landmark == T0:
                return segment.entered_recv_ns
        return None

    @property
    def completed(self) -> bool:
        return self.status == COMPLETED

    @property
    def completed_duration_ns(self) -> int:
        """Readable only after completion.

        Section 4.10 forbids using a completed duration at an earlier causal cutoff. Raising
        here means the rule is enforced at the point of access, not left to a caller who may
        reasonably assume a duration is always available.
        """
        if not self.completed or self.closed_recv_ns is None:
            raise ExhaustionError(
                f"runway {self.candidate_id} has not completed; its duration is not lawful yet"
            )
        return self.closed_recv_ns - self.opened_recv_ns

    def causal_age_ns(self, now_recv_ns: int) -> int:
        """Always lawful: elapsed time so far, which a live consumer would also have."""
        return now_recv_ns - self.opened_recv_ns

    def mark_landmark(self, landmark: str, recv_ns: int) -> RunwaySegment:
        if landmark not in LANDMARK_INDEX:
            raise ExhaustionError(
                f"unknown runway landmark: {landmark}; register it with "
                "register_discovered_landmark rather than forcing it into a carried one"
            )
        current = self.current_segment
        if current is not None:
            if LANDMARK_INDEX[landmark] <= LANDMARK_INDEX[current.landmark]:
                raise ExhaustionError(
                    f"runway {self.candidate_id} cannot move from {current.landmark} "
                    f"back to {landmark}"
                )
            if recv_ns < current.entered_recv_ns:
                raise ExhaustionError("a landmark cannot precede the one it follows")
            current.exited_recv_ns = recv_ns
        entry = RunwaySegment(landmark=landmark, entered_recv_ns=recv_ns)
        self.segments.append(entry)
        return entry

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "instrument_id": self.instrument_id,
            "source_day": self.source_day,
            "source_role": self.source_role,
            "continuity_segment": self.continuity_segment,
            "family_id": self.family_id,
            "side": self.side,
            "session_phase": self.session_phase,
            "state_id": self.state_id,
            "state_is_open_world": self.state_id.startswith(f"{OPEN_WORLD_PREFIX}_"),
            "searched_coverage_ns": self.searched_coverage_ns,
            "opened_recv_ns": self.opened_recv_ns,
            "closed_recv_ns": self.closed_recv_ns,
            "birth_recv_ns": self.birth_recv_ns,
            "status": self.status,
            "completed": self.completed,
            "censored": self.status in (CENSORED_SEGMENT_END, CENSORED_STREAM_END),
            "recurrences": self.recurrences,
            "birth_marked": self.birth_recv_ns is not None,
            "segment_count": len(self.segments),
            "segments": [seg.as_dict() for seg in self.segments],
            "falsifiers": list(self.falsifiers),
            "alternative_hypotheses": list(self.alternative_hypotheses),
            "clock": CAUSAL_CLOCK,
        }


class ExhaustionCalculator:
    """Streaming section 4.10 accumulator. Landmark is part of the stratum, not a column."""

    def __init__(self, *, exact_cap: int | None = None, seed: int = 0) -> None:
        kwargs: dict[str, Any] = {"seed": seed}
        if exact_cap is not None:
            kwargs["exact_cap"] = exact_cap

        def measure(name: str, numerator: str, status: str, missingness: str):
            return StratifiedMeasure(
                name=name,
                declaration=Declaration(
                    numerator_formula=numerator,
                    population="exhaustion runways within the stratum, state and landmark",
                    causal_cutoff="segment exit receive time on ts_recv_ns",
                    status=status,
                    missingness_rule=missingness,
                ),
                **kwargs,
            )

        self.segment_duration = measure(
            "segment_duration_ns",
            "segment exit - segment entry, one observation per closed segment",
            RESOLVED,
            "segments still open contribute nothing and are counted as excluded",
        )
        self.completed_duration = measure(
            "completed_runway_duration_ns",
            "runway close - runway open, completed runways only",
            RESOLVED,
            "censored and open runways are excluded; their durations are not lawful",
        )
        self.censored_age = measure(
            "censored_runway_age_ns",
            "censoring time - runway open, censored runways only",
            CENSORED,
            "completed runways are excluded and reported under completed_runway_duration_ns",
        )
        self.segment_depletion = measure(
            "segment_depletion", "displayed depletion within one segment", RESOLVED, "no exclusions"
        )
        self.segment_refill = measure(
            "segment_refill", "replaced quantity within one segment", RESOLVED, "no exclusions"
        )
        self.recurrences = measure(
            "recurrence_count", "recurrences observed on the runway", RESOLVED, "no exclusions"
        )

        self._open: dict[str, ExhaustionRunway] = {}
        self.opened = 0
        self.completed_count = 0
        self.censored_count = 0
        self.open_world_states: set[str] = set()

    @property
    def measures(self) -> tuple[StratifiedMeasure, ...]:
        return (
            self.segment_duration,
            self.completed_duration,
            self.censored_age,
            self.segment_depletion,
            self.segment_refill,
            self.recurrences,
        )

    @property
    def open_runway_count(self) -> int:
        return len(self._open)

    @staticmethod
    def _key(runway: ExhaustionRunway, landmark: str) -> StratumKey:
        """The landmark is in the key: 4.10 forbids averaging across phases of one event."""
        return StratumKey(
            source_day=runway.source_day,
            source_role=runway.source_role,
            continuity_segment=runway.continuity_segment,
            family_id=runway.family_id,
            side_orientation=runway.side,
            session_phase=runway.session_phase,
            clock=CAUSAL_CLOCK,
            subfamily_id=f"state={runway.state_id}|landmark={landmark}",
        )

    def open_runway(
        self,
        *,
        candidate_id: str,
        instrument_id: int,
        side: str,
        source_day: str,
        source_role: str,
        continuity_segment: int,
        family_id: str,
        session_phase: str,
        searched_coverage_ns: int,
        opened_recv_ns: int,
        seed_state: str | None = None,
        observed_shape: Sequence[str] = (),
    ) -> ExhaustionRunway:
        if candidate_id in self._open:
            raise ExhaustionError(f"runway {candidate_id} is already open")
        state_id = resolve_state_id(seed_state, observed_shape)
        if state_id.startswith(f"{OPEN_WORLD_PREFIX}_"):
            self.open_world_states.add(state_id)
        runway = ExhaustionRunway(
            candidate_id=candidate_id,
            instrument_id=instrument_id,
            side=side,
            source_day=source_day,
            source_role=source_role,
            continuity_segment=continuity_segment,
            family_id=family_id,
            session_phase=session_phase,
            state_id=state_id,
            searched_coverage_ns=searched_coverage_ns,
            opened_recv_ns=opened_recv_ns,
        )
        self._open[candidate_id] = runway
        self.opened += 1
        return runway

    def mark_landmark(self, candidate_id: str, landmark: str, recv_ns: int) -> RunwaySegment:
        runway = self._require(candidate_id)
        previous = runway.current_segment
        entry = runway.mark_landmark(landmark, recv_ns)
        if previous is not None and previous.duration_ns is not None:
            self._observe_segment(runway, previous)
        return entry

    def _observe_segment(self, runway: ExhaustionRunway, segment: RunwaySegment) -> None:
        key = self._key(runway, segment.landmark)
        self.segment_duration.observe(key, float(segment.duration_ns))
        self.segment_depletion.observe(key, float(segment.depletion))
        self.segment_refill.observe(key, float(segment.refill))

    def _require(self, candidate_id: str) -> ExhaustionRunway:
        runway = self._open.get(candidate_id)
        if runway is None:
            raise ExhaustionError(f"runway {candidate_id} is not open")
        return runway

    def note_recurrence(self, candidate_id: str) -> None:
        self._require(candidate_id).recurrences += 1

    def _close(self, runway: ExhaustionRunway, *, status: str, recv_ns: int) -> dict[str, Any]:
        current = runway.current_segment
        if current is not None and current.exited_recv_ns is None:
            current.exited_recv_ns = recv_ns
            if current.duration_ns is not None:
                self._observe_segment(runway, current)
        runway.status = status
        runway.closed_recv_ns = recv_ns
        # UNMARKED, not the first rung: a runway closed before anything was marked has no
        # birth, and borrowing T0 here would manufacture one.
        terminal_landmark = current.landmark if current is not None else UNMARKED
        key = self._key(runway, terminal_landmark)
        self.recurrences.observe(key, float(runway.recurrences))
        if status == COMPLETED:
            self.completed_duration.observe(key, float(runway.completed_duration_ns))
            self.censored_age.exclude_missing(key)
            self.completed_count += 1
        else:
            self.censored_age.observe(key, float(recv_ns - runway.opened_recv_ns))
            self.completed_duration.exclude_missing(key)
            self.censored_count += 1
        self._open.pop(runway.candidate_id, None)
        return runway.as_dict()

    def complete(
        self,
        candidate_id: str,
        *,
        recv_ns: int,
        terminal_landmark: str = ENDPOINT_CONFIRMATION,
    ) -> dict[str, Any]:
        """Completion is asserted at the CONFIRMATION, which is the earliest lawful instant.

        The onset of the terminating run sits `PERSIST - 1` earlier and is marked
        separately; it is the structural answer to "when did it begin", and confirmation is
        the causal answer to "when could that be said". Both are kept.
        """
        if terminal_landmark not in TERMINAL_LANDMARKS:
            raise ExhaustionError(
                f"terminal landmark must be one of {sorted(TERMINAL_LANDMARKS)}"
            )
        runway = self._require(candidate_id)
        current = runway.current_segment
        if current is None or current.landmark != terminal_landmark:
            runway.mark_landmark(terminal_landmark, recv_ns)
            previous_index = len(runway.segments) - 2
            if previous_index >= 0:
                previous = runway.segments[previous_index]
                if previous.duration_ns is not None:
                    self._observe_segment(runway, previous)
        return self._close(runway, status=COMPLETED, recv_ns=recv_ns)

    def close_continuity_segment(self, *, segment: int, recv_ns: int) -> list[dict[str, Any]]:
        stranded = [r for r in self._open.values() if r.continuity_segment == segment]
        return [self._close(r, status=CENSORED_SEGMENT_END, recv_ns=recv_ns) for r in stranded]

    def finalize(self, *, recv_ns: int) -> list[dict[str, Any]]:
        return [
            self._close(r, status=CENSORED_STREAM_END, recv_ns=recv_ns)
            for r in list(self._open.values())
        ]

    def companion_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for measure in self.measures:
            rows.extend(measure.rows())
        return rows

    def summary(self) -> dict[str, Any]:
        return {
            "section": "4.10",
            "causal_clock": CAUSAL_CLOCK,
            "runways_opened": self.opened,
            "completed": self.completed_count,
            "censored": self.censored_count,
            "still_open": self.open_runway_count,
            "open_world_state_count": len(self.open_world_states),
            "discovered_named_states": sorted(DISCOVERED_NAMED_STATES),
            "discovered_landmarks": {
                k: v["position"] for k, v in sorted(DISCOVERED_LANDMARKS.items())
            },
            "carried_seed_count": len(SEED_STATES),
            "carried_landmark_count": len(LANDMARK_ORDER),
            "seed_states_are_a_crosswalk_not_an_allowlist": True,
            "vocabulary_is_a_starting_point": (
                "carried seeds, landmarks and depths are where discovery begins, not what "
                "it is validated against; richer data is expected to add states, landmarks "
                "and depths"
            ),
            "landmark_stratum_note": (
                "the landmark is part of the stratum key, so averaging across phases of the "
                "same event is a key collision that cannot occur rather than a rule to remember"
            ),
            "landmark_provenance": (
                "T0, ENDPOINT_ONSET and ENDPOINT_CONFIRMATION are recovered from the prior "
                "exhaustion program, which records a terminating run's structural onset and "
                "its causal confirmation separately; confirmation is a clock, never evidence"
            ),
            "completed_duration_note": (
                "completed duration raises before completion; it is never readable at an "
                "earlier causal cutoff"
            ),
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
        }
