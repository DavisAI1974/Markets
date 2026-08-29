"""Section 4.14: recurrence, bursts, and transition graphs.

Two instructions here are easy to nod at and hard to keep.

"Threshold-free exact gaps are canonical; any burst threshold is a versioned descriptive
view, not a membership gate." A burst threshold decides which events count as a burst, and
once it gates membership every downstream number inherits it invisibly. So the exact
interarrival gaps are the stored evidence, and a burst view is computed on demand from a
named, versioned threshold that travels with its output. Changing the threshold changes a
label, never the population.

"Transition counts and conditional probabilities must be reported as such, with
denominators, rather than mislabeled as averages." A conditional probability is not a mean,
and calling it one hides the denominator that decides whether it means anything. Edges here
carry their own count and their own outgoing denominator, and the field is named a
probability rather than filed among the averages.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_stratum import (
    RESOLVED,
    Declaration,
    StratifiedMeasure,
    StratumKey,
)

CAUSAL_CLOCK = "ts_recv_ns"


class RecurrenceError(ValueError):
    """A recurrence sequence could not be measured."""


@dataclass(frozen=True)
class Occurrence:
    """One dated observation of a node label within a continuity segment."""

    node: str
    recv_ns: int
    continuity_segment: int
    order_id: int | None = None


@dataclass
class RunSegment:
    """A maximal consecutive stretch of one node label."""

    node: str
    start_recv_ns: int
    end_recv_ns: int
    length: int
    continuity_segment: int

    @property
    def duration_ns(self) -> int:
        return self.end_recv_ns - self.start_recv_ns

    def as_dict(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "start_recv_ns": self.start_recv_ns,
            "end_recv_ns": self.end_recv_ns,
            "length": self.length,
            "duration_ns": self.duration_ns,
            "continuity_segment": self.continuity_segment,
        }


def homogeneous_runs(occurrences: Sequence[Occurrence]) -> list[RunSegment]:
    """Maximal consecutive same-label runs, restarting at a continuity boundary.

    A run is not allowed to span a segment change even when the label repeats, because the
    gap across a boundary was never observed and a run that bridges it claims continuity
    the data does not support.
    """
    runs: list[RunSegment] = []
    for occurrence in occurrences:
        if (
            runs
            and runs[-1].node == occurrence.node
            and runs[-1].continuity_segment == occurrence.continuity_segment
        ):
            runs[-1].end_recv_ns = occurrence.recv_ns
            runs[-1].length += 1
        else:
            runs.append(
                RunSegment(
                    node=occurrence.node,
                    start_recv_ns=occurrence.recv_ns,
                    end_recv_ns=occurrence.recv_ns,
                    length=1,
                    continuity_segment=occurrence.continuity_segment,
                )
            )
    return runs


def interarrival_gaps(occurrences: Sequence[Occurrence]) -> list[dict[str, Any]]:
    """Exact gaps between consecutive occurrences, never across a boundary."""
    gaps = []
    for previous, current in zip(occurrences, occurrences[1:]):
        if previous.continuity_segment != current.continuity_segment:
            continue
        gaps.append(
            {
                "from_node": previous.node,
                "to_node": current.node,
                "gap_ns": current.recv_ns - previous.recv_ns,
                "recv_ns": current.recv_ns,
                "continuity_segment": current.continuity_segment,
            }
        )
    return gaps


def burst_view(
    gaps: Sequence[dict[str, Any]],
    *,
    threshold_ns: int,
    version: str,
) -> dict[str, Any]:
    """A descriptive labelling of already-stored exact gaps.

    Deliberately takes gaps rather than occurrences and returns a view rather than a
    filtered population: the threshold labels evidence that exists independently of it, so
    changing the threshold cannot change what was observed.
    """
    if threshold_ns <= 0:
        raise RecurrenceError("burst threshold must be positive")
    labelled = [{**gap, "in_burst": gap["gap_ns"] <= threshold_ns} for gap in gaps]
    in_burst = sum(1 for row in labelled if row["in_burst"])
    return {
        "view": "BURST_DESCRIPTIVE_VIEW",
        "is_membership_gate": False,
        "threshold_ns": threshold_ns,
        "threshold_version": version,
        "gap_count": len(labelled),
        "in_burst_count": in_burst,
        "in_burst_share": (in_burst / len(labelled)) if labelled else None,
        "share_is_a_rate_not_a_mean": True,
        "labelled_gaps": labelled,
        "note": (
            "exact gaps are canonical and stored independently; this threshold labels them "
            "and never decides which occurrences exist"
        ),
    }


class TransitionGraph:
    """Edge counts with explicit outgoing denominators."""

    def __init__(self) -> None:
        self.edges: dict[tuple[str, str], int] = {}
        self.outgoing: dict[str, int] = {}

    def add_edge(self, from_node: str, to_node: str, count: int = 1) -> None:
        self.edges[(from_node, to_node)] = self.edges.get((from_node, to_node), 0) + count
        self.outgoing[from_node] = self.outgoing.get(from_node, 0) + count

    def rows(self) -> list[dict[str, Any]]:
        """Counts and conditional probabilities, labelled as such with denominators."""
        return [
            {
                "from_node": from_node,
                "to_node": to_node,
                "transition_count": count,
                "outgoing_denominator": self.outgoing[from_node],
                "conditional_probability": count / self.outgoing[from_node],
                "statistic_kind": "CONDITIONAL_PROBABILITY",
                "is_arithmetic_mean": False,
            }
            for (from_node, to_node), count in sorted(self.edges.items())
        ]


class RecurrenceCalculator:
    """Streaming section 4.14 accumulator over exact gaps and runs."""

    def __init__(self, *, exact_cap: int | None = None, seed: int = 0) -> None:
        kwargs: dict[str, Any] = {"seed": seed}
        if exact_cap is not None:
            kwargs["exact_cap"] = exact_cap

        def measure(name: str, numerator: str, missingness: str):
            return StratifiedMeasure(
                name=name,
                declaration=Declaration(
                    numerator_formula=numerator,
                    population="occurrences within the stratum, node and continuity segment",
                    causal_cutoff="occurrence receive time on ts_recv_ns",
                    status=RESOLVED,
                    missingness_rule=missingness,
                ),
                **kwargs,
            )

        self.run_length = measure(
            "run_length",
            "consecutive same-node occurrences, one observation per maximal run",
            "runs are never allowed to span a continuity boundary",
        )
        self.run_duration = measure(
            "run_duration_ns",
            "last - first receive time within one maximal run",
            "single-occurrence runs contribute zero duration, which is an observation",
        )
        self.interarrival_gap = measure(
            "interarrival_gap_ns",
            "exact receive-time gap between consecutive occurrences in one segment",
            "gaps spanning a continuity boundary are excluded and counted",
        )

        self.graph = TransitionGraph()
        self.occurrences_seen = 0
        self.boundary_restarts = 0
        self.same_order_paths: dict[int, int] = {}

    @property
    def measures(self) -> tuple[StratifiedMeasure, ...]:
        return (self.run_length, self.run_duration, self.interarrival_gap)

    @staticmethod
    def _key(
        node: str,
        *,
        source_day: str,
        source_role: str,
        continuity_segment: int,
        family_id: str,
        side_orientation: str,
        session_phase: str,
    ) -> StratumKey:
        return StratumKey(
            source_day=source_day,
            source_role=source_role,
            continuity_segment=continuity_segment,
            family_id=family_id,
            side_orientation=side_orientation,
            session_phase=session_phase,
            clock=CAUSAL_CLOCK,
            subfamily_id=f"node={node}",
        )

    def observe_sequence(
        self,
        occurrences: Sequence[Occurrence],
        *,
        source_day: str,
        source_role: str,
        family_id: str,
        side_orientation: str,
        session_phase: str,
    ) -> dict[str, Any]:
        """Fold one ordered occurrence sequence in, exact gaps first."""
        if any(b.recv_ns < a.recv_ns for a, b in zip(occurrences, occurrences[1:])):
            raise RecurrenceError("occurrences must be ordered by receive time")
        self.occurrences_seen += len(occurrences)

        def key_for(node: str, segment: int) -> StratumKey:
            return self._key(
                node,
                source_day=source_day,
                source_role=source_role,
                continuity_segment=segment,
                family_id=family_id,
                side_orientation=side_orientation,
                session_phase=session_phase,
            )

        runs = homogeneous_runs(occurrences)
        for run in runs:
            key = key_for(run.node, run.continuity_segment)
            self.run_length.observe(key, float(run.length))
            self.run_duration.observe(key, float(run.duration_ns))

        gaps = interarrival_gaps(occurrences)
        for gap in gaps:
            self.interarrival_gap.observe(key_for(gap["to_node"], gap["continuity_segment"]), float(gap["gap_ns"]))
            self.graph.add_edge(gap["from_node"], gap["to_node"])

        for previous, current in zip(occurrences, occurrences[1:]):
            if previous.continuity_segment != current.continuity_segment:
                self.boundary_restarts += 1
                self.interarrival_gap.exclude_missing(key_for(current.node, current.continuity_segment))

        for occurrence in occurrences:
            if occurrence.order_id is not None:
                self.same_order_paths[occurrence.order_id] = (
                    self.same_order_paths.get(occurrence.order_id, 0) + 1
                )

        return {
            "runs": [r.as_dict() for r in runs],
            "gaps": gaps,
            "run_count": len(runs),
            "gap_count": len(gaps),
        }

    def companion_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for measure in self.measures:
            rows.extend(measure.rows())
        return rows

    def summary(self) -> dict[str, Any]:
        multi_stage = sum(1 for count in self.same_order_paths.values() if count > 1)
        return {
            "section": "4.14",
            "causal_clock": CAUSAL_CLOCK,
            "occurrences_seen": self.occurrences_seen,
            "boundary_restarts": self.boundary_restarts,
            "same_order_paths": len(self.same_order_paths),
            "multi_occurrence_order_paths": multi_stage,
            "transition_edges": self.graph.rows(),
            "canonical_evidence": "THRESHOLD_FREE_EXACT_GAPS",
            "burst_note": (
                "a burst threshold is a versioned descriptive view over stored exact gaps and "
                "never a membership gate; changing it changes a label, not the population"
            ),
            "probability_note": (
                "transition edges carry their own count and outgoing denominator and are "
                "labelled CONDITIONAL_PROBABILITY, never filed among the averages"
            ),
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
        }
