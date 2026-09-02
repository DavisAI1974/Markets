"""Section 4.5: formation, serialization, and observation clocks.

Computed as a forward-only streaming pass over F_LAST-closed groups. The calculator sees
one member at a time and never holds a forward window, so a clock derived here cannot be
contaminated by a later group: causal lawfulness is a property of the traversal rather than
a rule applied to the output afterwards.

Section 2 fixes the pivot: "the first lawful knowledge time for a completed group is its
F_LAST receive time". Every derived feature of a member therefore becomes available at that
instant and not before, which is what `first_lawful_availability_ns` records.

Section 4.5 also requires that "economic interpretation remains separate from a
serialization/feed explanation", so every measure here is stamped SERIALIZATION_FEED. These
numbers describe how the tape reached us, not what the market did.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_stratum import (
    Declaration,
    StratifiedMeasure,
    StratumError,
    StratumKey,
)

INTERPRETATION_DOMAIN = "SERIALIZATION_FEED"
CAUSAL_CLOCK = "ts_recv_ns"
PRIOR = "PRIOR"
T0 = "T0"
HORIZON = "H+N"
VALID_RECOGNITION = frozenset({PRIOR, T0, HORIZON})

F_LAST_FLAG = 128


class ClockError(ValueError):
    """A group could not be measured on the declared clocks."""


def clock_subfamily(channel_id: int, component_count: int) -> str:
    """Section 4.5 strata include channel and component count.

    Carried in `StratumKey.subfamily_id` rather than as new StratumKey fields: declaration 4
    already names "family, subfamily, and cluster version", and channel-by-component-count is
    genuinely a subfamily for clock purposes. Keeping StratumKey stable avoids growing a
    shared identity type for one section's needs.
    """
    return f"channel={int(channel_id)}|components={int(component_count)}"


@dataclass(frozen=True)
class RecognitionLabel:
    """Section 2's PRIOR / T0 / H+N, with the lead time and the clock it was measured on.

    A later, better-looking horizon may not replace an earlier valid call, so `supersedes`
    is deliberately absent: a recognition is a fact about when something was first knowable,
    not a slot to be overwritten.
    """

    label: str
    clock: str
    reference_ns: int
    observed_ns: int

    def __post_init__(self) -> None:
        if self.label not in VALID_RECOGNITION:
            raise ClockError(f"recognition label must be one of {sorted(VALID_RECOGNITION)}")
        if self.clock != CAUSAL_CLOCK:
            raise ClockError(f"recognition must be measured on {CAUSAL_CLOCK}")
        if self.label == PRIOR and self.observed_ns >= self.reference_ns:
            raise ClockError("a PRIOR recognition must precede its reference")
        if self.label == T0 and self.observed_ns != self.reference_ns:
            raise ClockError("a T0 recognition must coincide with its reference")
        if self.label == HORIZON and self.observed_ns <= self.reference_ns:
            raise ClockError("an H+N recognition must follow its reference")

    @property
    def lead_ns(self) -> int:
        """Negative after the reference, positive before it. PRIOR lead is positive."""
        return self.reference_ns - self.observed_ns

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "clock": self.clock,
            "reference_ns": self.reference_ns,
            "observed_ns": self.observed_ns,
            "lead_ns": self.lead_ns,
        }


def _components(group: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    actions = group.get("raw_actions")
    if not isinstance(actions, list) or not actions:
        raise ClockError("group carries no raw_actions")
    return actions


# D-1. THE DECISION CLOCK WAS EMPTY ON EVERY ONE OF 43,569 MEMBERS, and it is the clock that
# makes the other three actionable - without it nothing separates LAWFULLY KNOWABLE from
# ACTED UPON. The cause was not a bug in the measure: no caller ever passed a decision time,
# so the parameter defaulted to None, and 43,569 members were excluded by a rule that reads
# "members with no decision time are excluded and counted". The measure ran perfectly and
# reported an absence.
#
# In a replay there IS no trading decision to observe, so the honest reading is that the
# decision is taken at the first instant the group is lawfully knowable - F_LAST. That yields
# a delay of zero, which is a MEASUREMENT, and it must never be confusable with a zero that
# means "unknown". So the basis travels ON the record: a reader can always tell whether the
# zero was observed, adopted by replay convention, or absent. A caveat that lives only in
# prose expires (S115); this one is a field.
DECISION_BASIS_OBSERVED = "OBSERVED_DECISION_TIME"
DECISION_BASIS_REPLAY_EARLIEST = "REPLAY_EARLIEST_LAWFUL_AVAILABILITY"
DECISION_BASIS_ABSENT = "NO_DECISION_TIME"
DECISION_BASES = (
    DECISION_BASIS_OBSERVED,
    DECISION_BASIS_REPLAY_EARLIEST,
    DECISION_BASIS_ABSENT,
)


def _is_f_last(component: Mapping[str, Any]) -> bool:
    flagged = component.get("is_last")
    if isinstance(flagged, bool):
        return flagged
    return bool(int(component.get("flags", 0)) & F_LAST_FLAG)


def member_clock_row(
    group: Mapping[str, Any],
    *,
    group_index: int,
    source_day: str,
    source_role: str,
    continuity_segment: int,
    family_id: str,
    side_orientation: str,
    session_phase: str,
    decision_ts_recv_ns: int | None = None,
    decision_basis: str = DECISION_BASIS_REPLAY_EARLIEST,
) -> dict[str, Any]:
    """The exact per-member clock record. Section 3 requires this before any average.

    Raises rather than degrading when the group is not F_LAST-closed: an unclosed group has
    no lawful availability time, so every clock derived from it would be unanchored.
    """
    components = _components(group)
    if not _is_f_last(components[-1]):
        raise ClockError(f"group {group_index} is not F_LAST-closed on its final component")

    recv = [int(c["ts_recv_ns"]) for c in components]
    event = [int(c["ts_event_ns"]) for c in components]
    if any(b < a for a, b in zip(recv, recv[1:])):
        raise ClockError(f"group {group_index} receive times are not monotonic")

    f_last_recv = recv[-1]
    first_recv = recv[0]

    event_to_receive = [r - e for r, e in zip(recv, event)]
    within_group_gaps = [b - a for a, b in zip(recv, recv[1:])]
    sequences = [int(c["sequence"]) for c in components]
    channels = sorted({int(c["channel_id"]) for c in components})

    if decision_basis not in DECISION_BASES:
        raise ClockError(
            f"unknown decision basis {decision_basis!r}; one of {DECISION_BASES} is required "
            "so that a zero delay can never be read as an absent one"
        )
    if decision_ts_recv_ns is not None:
        # An observed time overrides any convention. Passing one alongside a replay basis
        # would silently discard it, which is the drop this programme keeps finding.
        decision_basis = DECISION_BASIS_OBSERVED
    elif decision_basis == DECISION_BASIS_REPLAY_EARLIEST:
        decision_ts_recv_ns = f_last_recv

    f_last_to_decision = None
    if decision_ts_recv_ns is not None:
        if decision_ts_recv_ns < f_last_recv:
            raise ClockError(
                f"group {group_index} decision time precedes its F_LAST availability; "
                "a decision cannot be taken before the group is knowable"
            )
        f_last_to_decision = int(decision_ts_recv_ns) - f_last_recv

    return {
        "group_index": group_index,
        "source_day": source_day,
        "source_role": source_role,
        "continuity_segment": continuity_segment,
        "family_id": family_id,
        "side_orientation": side_orientation,
        "session_phase": session_phase,
        "interpretation_domain": INTERPRETATION_DOMAIN,
        "component_count": len(components),
        "channels": channels,
        "clocks": {
            "first_component_ts_event_ns": event[0],
            "first_component_ts_recv_ns": first_recv,
            "f_last_ts_recv_ns": f_last_recv,
            "first_lawful_availability_ns": f_last_recv,
            "decision_ts_recv_ns": decision_ts_recv_ns,
        },
        "decision_basis": decision_basis,
        "event_to_receive_latency_ns": event_to_receive,
        "formation_latency_ns": f_last_recv - first_recv,
        "within_group_receive_gaps_ns": within_group_gaps,
        "max_within_group_receive_gap_ns": max(within_group_gaps) if within_group_gaps else 0,
        "f_last_to_decision_delay_ns": f_last_to_decision,
        "sequence_first": sequences[0],
        "sequence_last": sequences[-1],
        "sequence_span": sequences[-1] - sequences[0],
        "sequence_contiguous": sequences == list(range(sequences[0], sequences[0] + len(sequences))),
        "channel_count": len(channels),
        "single_channel_group": len(channels) == 1,
    }


class ClockCalculator:
    """Streaming section 4.5 accumulator: exact rows out, stratified companions retained.

    Holds no forward window and no cross-group state beyond the stratified accumulators, so
    memory is bounded by stratum count rather than by group count.
    """

    def __init__(self, *, exact_cap: int | None = None, seed: int = 0) -> None:
        kwargs: dict[str, Any] = {"seed": seed}
        if exact_cap is not None:
            kwargs["exact_cap"] = exact_cap

        def measure(name: str, numerator: str, missingness: str) -> StratifiedMeasure:
            return StratifiedMeasure(
                name=name,
                declaration=Declaration(
                    numerator_formula=numerator,
                    population="F_LAST-closed native event groups within the stratum",
                    causal_cutoff="F_LAST receive time (ts_recv_ns) of the group",
                    status="RESOLVED",
                    missingness_rule=missingness,
                ),
                **kwargs,
            )

        self.event_to_receive = measure(
            "event_to_receive_latency_ns",
            "ts_recv_ns - ts_event_ns, one observation per component",
            "components lacking either timestamp are excluded and counted per stratum",
        )
        self.formation_latency = measure(
            "formation_latency_ns",
            "f_last.ts_recv_ns - first_component.ts_recv_ns, one observation per member",
            "groups that are not F_LAST-closed are refused, never excluded silently",
        )
        self.within_group_gap = measure(
            "within_group_receive_gap_ns",
            "consecutive ts_recv_ns differences inside one group",
            "single-component groups contribute no gap and are counted as excluded",
        )
        self.f_last_to_decision = measure(
            "f_last_to_decision_delay_ns",
            "decision.ts_recv_ns - f_last.ts_recv_ns, one observation per member",
            "members whose decision basis is NO_DECISION_TIME are excluded and counted per "
            "stratum; a replay adopts F_LAST as the decision instant and observes zero",
        )
        self.sequence_span = measure(
            "sequence_span",
            "last component sequence - first component sequence",
            "no exclusions; every closed group has a sequence span",
        )
        self.members_seen = 0
        self.noncontiguous_sequence_members = 0
        self.multi_channel_members = 0

    @property
    def measures(self) -> tuple[StratifiedMeasure, ...]:
        return (
            self.event_to_receive,
            self.formation_latency,
            self.within_group_gap,
            self.f_last_to_decision,
            self.sequence_span,
        )

    def _key(self, row: Mapping[str, Any], channel_id: int) -> StratumKey:
        return StratumKey(
            source_day=row["source_day"],
            source_role=row["source_role"],
            continuity_segment=int(row["continuity_segment"]),
            family_id=row["family_id"],
            side_orientation=row["side_orientation"],
            session_phase=row["session_phase"],
            clock=CAUSAL_CLOCK,
            subfamily_id=clock_subfamily(channel_id, int(row["component_count"])),
        )

    def observe(self, row: Mapping[str, Any]) -> None:
        """Fold one exact member row into the stratified companions."""
        if row.get("interpretation_domain") != INTERPRETATION_DOMAIN:
            raise ClockError("clock measures accept serialization/feed rows only")
        self.members_seen += 1
        if not row["sequence_contiguous"]:
            self.noncontiguous_sequence_members += 1
        if not row["single_channel_group"]:
            self.multi_channel_members += 1

        # A multi-channel group has no single channel stratum, so it is attributed to each
        # channel it actually spans rather than to a synthetic combined one.
        for channel_id in row["channels"]:
            key = self._key(row, channel_id)
            for latency in row["event_to_receive_latency_ns"]:
                self.event_to_receive.observe(key, float(latency))
            self.formation_latency.observe(key, float(row["formation_latency_ns"]))
            self.sequence_span.observe(key, float(row["sequence_span"]))

            gaps = row["within_group_receive_gaps_ns"]
            if gaps:
                for gap in gaps:
                    self.within_group_gap.observe(key, float(gap))
            else:
                self.within_group_gap.exclude_missing(key)

            delay = row["f_last_to_decision_delay_ns"]
            if delay is None:
                self.f_last_to_decision.exclude_missing(key)
            else:
                self.f_last_to_decision.observe(key, float(delay))

    def companion_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for measure in self.measures:
            rows.extend(measure.rows())
        return rows

    def summary(self) -> dict[str, Any]:
        return {
            "section": "4.5",
            "interpretation_domain": INTERPRETATION_DOMAIN,
            "interpretation_note": (
                "these are serialization and feed timings; an economic reading of them is a "
                "separate claim and is not licensed by these numbers"
            ),
            "causal_clock": CAUSAL_CLOCK,
            "members_seen": self.members_seen,
            "noncontiguous_sequence_members": self.noncontiguous_sequence_members,
            "multi_channel_members": self.multi_channel_members,
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
        }
