"""Section 4.10: exhaustion state, birth, persistence, and completion.

A candidate's runway is a sequence of phases, and section 4.10 draws two hard lines around
it. "Never average across phases of the same event" - so the phase is part of the stratum
identity, and folding two phases of one runway into one figure is a key collision that
cannot happen rather than a mistake to avoid. And "never use completed duration at an
earlier causal cutoff" - so a runway's completed duration is simply not readable until it
has completed; asking for it early raises instead of returning the value that will
eventually be true.

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

# Ordered: a runway may skip phases but never revisit an earlier one.
SEARCHED = "SEARCHED"
PRECURSOR = "PRECURSOR"
PREBIRTH = "PREBIRTH"
FIRST_DEVIATION = "FIRST_DEVIATION"
BIRTH = "BIRTH"
TRANSITION = "TRANSITION"
INFLECTION = "INFLECTION"
PERSISTENCE = "PERSISTENCE"
EXTENSION = "EXTENSION"
COMPLETION = "COMPLETION"
REVERSAL = "REVERSAL"
PHASE_ORDER = (
    SEARCHED,
    PRECURSOR,
    PREBIRTH,
    FIRST_DEVIATION,
    BIRTH,
    TRANSITION,
    INFLECTION,
    PERSISTENCE,
    EXTENSION,
    COMPLETION,
    REVERSAL,
)
PHASE_INDEX = {name: index for index, name in enumerate(PHASE_ORDER)}
TERMINAL_PHASES = frozenset({COMPLETION, REVERSAL})

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


def resolve_state_id(seed: str | None, shape: Sequence[str]) -> str:
    """Seeds are a crosswalk, never an allowlist."""
    if seed is None:
        return open_world_state_id(shape)
    if seed not in SEED_STATES:
        raise ExhaustionError(f"{seed} is not a seed annotation; pass seed=None for open-world")
    return seed


@dataclass
class RunwayPhase:
    phase: str
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
            "phase": self.phase,
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
    phases: list[RunwayPhase] = field(default_factory=list)
    falsifiers: list[str] = field(default_factory=list)
    alternative_hypotheses: list[str] = field(default_factory=list)
    recurrences: int = 0
    status: str = OPEN
    closed_recv_ns: int | None = None

    @property
    def current_phase(self) -> RunwayPhase | None:
        return self.phases[-1] if self.phases else None

    @property
    def birth_recv_ns(self) -> int | None:
        for phase in self.phases:
            if phase.phase == BIRTH:
                return phase.entered_recv_ns
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

    def enter_phase(self, phase: str, recv_ns: int) -> RunwayPhase:
        if phase not in PHASE_INDEX:
            raise ExhaustionError(f"unknown runway phase: {phase}")
        current = self.current_phase
        if current is not None:
            if PHASE_INDEX[phase] <= PHASE_INDEX[current.phase]:
                raise ExhaustionError(
                    f"runway {self.candidate_id} cannot move from {current.phase} back to {phase}"
                )
            if recv_ns < current.entered_recv_ns:
                raise ExhaustionError("a phase cannot begin before the one it follows")
            current.exited_recv_ns = recv_ns
        entry = RunwayPhase(phase=phase, entered_recv_ns=recv_ns)
        self.phases.append(entry)
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
            "phase_count": len(self.phases),
            "phases": [p.as_dict() for p in self.phases],
            "falsifiers": list(self.falsifiers),
            "alternative_hypotheses": list(self.alternative_hypotheses),
            "clock": CAUSAL_CLOCK,
        }


class ExhaustionCalculator:
    """Streaming section 4.10 accumulator. Phase is part of the stratum, not a column."""

    def __init__(self, *, exact_cap: int | None = None, seed: int = 0) -> None:
        kwargs: dict[str, Any] = {"seed": seed}
        if exact_cap is not None:
            kwargs["exact_cap"] = exact_cap

        def measure(name: str, numerator: str, status: str, missingness: str):
            return StratifiedMeasure(
                name=name,
                declaration=Declaration(
                    numerator_formula=numerator,
                    population="exhaustion runways within the stratum, state and phase",
                    causal_cutoff="phase exit receive time on ts_recv_ns",
                    status=status,
                    missingness_rule=missingness,
                ),
                **kwargs,
            )

        self.phase_duration = measure(
            "phase_duration_ns",
            "phase exit - phase entry, one observation per completed phase",
            RESOLVED,
            "phases still open contribute nothing and are counted as excluded",
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
        self.phase_depletion = measure(
            "phase_depletion", "displayed depletion within one phase", RESOLVED, "no exclusions"
        )
        self.phase_refill = measure(
            "phase_refill", "replaced quantity within one phase", RESOLVED, "no exclusions"
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
            self.phase_duration,
            self.completed_duration,
            self.censored_age,
            self.phase_depletion,
            self.phase_refill,
            self.recurrences,
        )

    @property
    def open_runway_count(self) -> int:
        return len(self._open)

    @staticmethod
    def _key(runway: ExhaustionRunway, phase: str) -> StratumKey:
        """Phase is in the key: section 4.10 forbids averaging across phases of one event."""
        return StratumKey(
            source_day=runway.source_day,
            source_role=runway.source_role,
            continuity_segment=runway.continuity_segment,
            family_id=runway.family_id,
            side_orientation=runway.side,
            session_phase=runway.session_phase,
            clock=CAUSAL_CLOCK,
            subfamily_id=f"state={runway.state_id}|phase={phase}",
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

    def enter_phase(self, candidate_id: str, phase: str, recv_ns: int) -> RunwayPhase:
        runway = self._require(candidate_id)
        previous = runway.current_phase
        entry = runway.enter_phase(phase, recv_ns)
        if previous is not None and previous.duration_ns is not None:
            key = self._key(runway, previous.phase)
            self.phase_duration.observe(key, float(previous.duration_ns))
            self.phase_depletion.observe(key, float(previous.depletion))
            self.phase_refill.observe(key, float(previous.refill))
        return entry

    def _require(self, candidate_id: str) -> ExhaustionRunway:
        runway = self._open.get(candidate_id)
        if runway is None:
            raise ExhaustionError(f"runway {candidate_id} is not open")
        return runway

    def note_recurrence(self, candidate_id: str) -> None:
        self._require(candidate_id).recurrences += 1

    def _close(self, runway: ExhaustionRunway, *, status: str, recv_ns: int) -> dict[str, Any]:
        current = runway.current_phase
        if current is not None and current.exited_recv_ns is None:
            current.exited_recv_ns = recv_ns
            key = self._key(runway, current.phase)
            if current.duration_ns is not None:
                self.phase_duration.observe(key, float(current.duration_ns))
                self.phase_depletion.observe(key, float(current.depletion))
                self.phase_refill.observe(key, float(current.refill))
        runway.status = status
        runway.closed_recv_ns = recv_ns
        terminal_phase = current.phase if current is not None else SEARCHED
        key = self._key(runway, terminal_phase)
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

    def complete(self, candidate_id: str, *, recv_ns: int, terminal_phase: str = COMPLETION) -> dict[str, Any]:
        if terminal_phase not in TERMINAL_PHASES:
            raise ExhaustionError(f"terminal phase must be one of {sorted(TERMINAL_PHASES)}")
        runway = self._require(candidate_id)
        current = runway.current_phase
        if current is None or current.phase != terminal_phase:
            runway.enter_phase(terminal_phase, recv_ns)
            previous_index = len(runway.phases) - 2
            if previous_index >= 0:
                previous = runway.phases[previous_index]
                if previous.duration_ns is not None:
                    key = self._key(runway, previous.phase)
                    self.phase_duration.observe(key, float(previous.duration_ns))
                    self.phase_depletion.observe(key, float(previous.depletion))
                    self.phase_refill.observe(key, float(previous.refill))
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
            "seed_states_are_a_crosswalk_not_an_allowlist": True,
            "phase_stratum_note": (
                "phase is part of the stratum key, so averaging across phases of the same "
                "event is a key collision that cannot occur rather than a rule to remember"
            ),
            "completed_duration_note": (
                "completed duration raises before completion; it is never readable at an "
                "earlier causal cutoff"
            ),
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
        }
