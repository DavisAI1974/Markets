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
EVENT_CLOCK = "ts_event_ns"

LIFECYCLE_AVAILABILITY_STAMP = "emitted_at_recv_ns"
"""F-20 under D83: the receive-clock instant the traversal stood at when it retained a
lifecycle row - the row's own feature-availability clock, stamped uniformly by
`native_replay_driver._retain_lifecycle` and read FIRST by
`native_causal_stream.lifecycle_availability`. Declared here, once, because the producer and
the consumer must agree on the name and neither imports the other. The design is the
Step-1 two-day module's (`research/ng_exhaustion_mbo_2day_full_mbo_step1_20260825.py`):
`event_known_by_ts_recv_ns` is the receive time of the record that made the event knowable,
never a time chosen; only that definition is reused, no Step-1 value.

MEASURED ON THE REAL SUNDAY LEDGERS BEFORE THE STAMP (F-feed-7, run 33630348943, record
`FRANKIE_FEED_RECORD_SUNDAY_33630348943_20260903.md`): 109,532 of 377,454 lifecycle rows
(29.0%) could not ride inside any group - withheld_no_own_clock 43,569 (every `mirror`
GROUP_CLOSE row names no receive clock), withheld_close_occasion 65,960 (mirror|STREAM_END
43,569; lineage|STREAM_END 21,651; queue|STREAM_END 597; response|STREAM_END 91;
replenishment|STREAM_END 51; exhaustion|STREAM_END 1), withheld_beyond_last_cutoff 3, late
arrivals 1,713; in-stream mirror 0 of 87,138, lineage 0 of 21,651. Those are the numbers this
stamp drives to zero on a fresh run: every one of those rows now carries the receive instant
it was retained at, and `native_causal_stream` places it there."""


class ClockError(ValueError):
    """A group could not be measured on the declared clocks."""


# S121 item one (D83): the registry's `causal_clocks` group, produced BY NAME on every member
# row. The delivery receipt named all seven layer ids as delivered with the member line's hash
# as each one's evidence, while no field on the row was keyed by any of them. Delivered-by-hash
# and findable-by-name are different facts; these are the names, in the registry's own order,
# and `test_the_seven_ids_are_exactly_the_registrys_causal_clocks_group` reads them back from
# the JSON so a drift between the two fails.
CLOCK_EVENT_TIME = "clock_event_time"
CLOCK_RECEIVE_TIME = "clock_receive_time"
CLOCK_EVENT_KNOWN_BY = "clock_event_known_by"
CLOCK_FEATURE_AVAILABILITY = "clock_feature_availability"
CLOCK_PROSPECTIVE_DISCOVERY_CONFIRMATION = "clock_prospective_discovery_confirmation"
CLOCK_MODEL_EVALUATION = "clock_model_evaluation"
CLOCK_LOCK_TIME = "clock_lock_time"
CAUSAL_CLOCK_LAYER_IDS: tuple[str, ...] = (
    CLOCK_EVENT_TIME,
    CLOCK_RECEIVE_TIME,
    CLOCK_EVENT_KNOWN_BY,
    CLOCK_FEATURE_AVAILABILITY,
    CLOCK_PROSPECTIVE_DISCOVERY_CONFIRMATION,
    CLOCK_MODEL_EVALUATION,
    CLOCK_LOCK_TIME,
)
CAUSAL_CLOCKS_CARRIER = "member_row.causal_clocks"

# The bases. Short, because they ride on every row; the prose behind each lives ONCE in
# `CAUSAL_CLOCK_DECLARATIONS` and is rendered into the 4.5 summary, never repeated per row.
BASIS_OBSERVED_ON_THE_RECORD = "OBSERVED_ON_THE_RECORD"
BASIS_F_LAST_RECEIVE_OF_THE_GROUP = "F_LAST_RECEIVE_OF_THE_GROUP"
FEATURE_BASIS_REPLAY_EARLIEST = "REPLAY_EARLIEST_LAWFUL_AVAILABILITY"
FEATURE_BASIS_OBSERVED = "OBSERVED_COMPUTATION_INSTANT"
FEATURE_SCOPE_MEMBER_ROW = "MEMBER_ROW_DERIVED_BLOCKS"
DISCOVERY_BASIS_NONE = "NO_RECOGNITION_EMITTED_AT_THIS_CUTOFF"
DISCOVERY_BASIS_EMITTED = "RECOGNITIONS_EMITTED_AT_THIS_CUTOFF"
EVALUATION_BASIS_NONE = "NO_INVOCATION_AT_THIS_CUTOFF"
EVALUATION_BASIS_STAGED = "PRINCIPAL_INVOCATION_STAGED_AT_THIS_CUTOFF"
LOCK_BASIS_PRINCIPAL = "STAMPED_BY_THE_PRINCIPAL_FIRST_LOCK"
EVALUATION_BASIS_LEGACY_DECISION_TS = "DERIVED_FROM_LEGACY_DECISION_TS_RECV_NS"
"""F-feed-5 (S122, measured on the real Sunday ledgers): a pre-S121 row carries
`clocks.decision_ts_recv_ns` under `decision_basis`, and the legacy derivation had declared
the model-evaluation clock NOT_ON_THIS_ROW anyway. It derives from that instant now, and the
entry carries the row's own `decision_basis` so a convention-adopted instant
(REPLAY_EARLIEST_LAWFUL_AVAILABILITY) is never read as an observed staging."""
DECISION_BASIS_UNDECLARED_ON_ROW = "DECISION_BASIS_UNDECLARED_ON_ROW"
NOT_ON_THIS_ROW = "NOT_ON_THIS_ROW"
"""A ledger written before this build carries the five-field `clocks` object and nothing
keyed by a registry id. What that object can support is derived; what it cannot is said."""

CAUSAL_CLOCK_DECLARATIONS: dict[str, str] = {
    CLOCK_EVENT_TIME: (
        "ts_event of every DBN record as received; the group carries its first and F_LAST "
        "component event times. Nothing is computed."
    ),
    CLOCK_RECEIVE_TIME: (
        "ts_recv of every record; the package's causal clock, on which the stream is ordered. "
        "The group carries its first and F_LAST component receive times."
    ),
    CLOCK_EVENT_KNOWN_BY: (
        "the receive time of the record carrying F_LAST: the first instant a completed group is "
        "lawfully knowable (contract section 2). Equal to clocks.first_lawful_availability_ns."
    ),
    CLOCK_FEATURE_AVAILABILITY: (
        "the instant the row's derived blocks were computed on the causal prefix ending at "
        "this F_LAST. A replay has no such instant to observe, so the earliest lawful one is "
        "adopted and the basis says so; max_contributing_ts_recv_ns names the latest input "
        "consumed and may never exceed feature_cutoff_ts_recv_ns."
    ),
    CLOCK_PROSPECTIVE_DISCOVERY_CONFIRMATION: (
        "the F_LAST cutoff at which 4.11 actually emitted each PRIOR / T0 / H+N call, beside "
        "the instant at which the call was knowable (recognized_recv_ns, on the candidate "
        "lane's clock). Two instants the code used to collapse into one."
    ),
    CLOCK_MODEL_EVALUATION: (
        "the receive-clock cutoff of the group at which the principal is staged to be invoked; "
        "stamped by the driver when the cadence fires and carried into the spawn request's "
        "cutoff as clock_model_evaluation_ns. Null with a declared basis otherwise."
    ),
    CLOCK_LOCK_TIME: (
        "the cutoff at which the principal writes FIRST_LOCK. His act, not the tape's: the "
        "traversal carries the declared null and his first-lock ledger stamps the value."
    ),
}


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
    feature_computed_at_ns: int | None = None,
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
        # S121 item one: the seven registry clocks BY NAME, beside the five-field object the
        # stream and the registry validator read. Beside, never inside.
        "causal_clocks": causal_clock_layers(
            event_ns=event, recv_ns=recv, feature_computed_at_ns=feature_computed_at_ns
        ),
    }


def causal_clock_layers(
    *,
    event_ns: Sequence[int],
    recv_ns: Sequence[int],
    feature_computed_at_ns: int | None = None,
) -> dict[str, dict[str, Any]]:
    """The seven registry clocks for one F_LAST-closed group, from its component instants.

    Five are the stream's and are filled here. The other two are acts - of the spawn
    (`stamp_model_evaluation`) and of the principal (his first lock) - and are declared null
    with a basis until the act happens; a null with a basis is a different fact from a zero.
    """
    if not recv_ns or len(recv_ns) != len(event_ns):
        raise ClockError("a group needs one event and one receive instant per component")
    recv = [int(value) for value in recv_ns]
    event = [int(value) for value in event_ns]
    known_by = recv[-1]
    # The Step-1 idea (`max_contributing_ts_recv_ns` / `feature_cutoff_ts_recv_ns`), not its
    # code: the derived blocks consumed these components and nothing later, so the latest
    # input consumed can never exceed the cutoff the features were computed at.
    max_contributing = max(recv)
    if feature_computed_at_ns is None:
        feature_ns, feature_basis = known_by, FEATURE_BASIS_REPLAY_EARLIEST
    else:
        feature_ns, feature_basis = int(feature_computed_at_ns), FEATURE_BASIS_OBSERVED
        if feature_ns < known_by:
            raise ClockError(
                f"{CLOCK_FEATURE_AVAILABILITY} {feature_ns} precedes {CLOCK_EVENT_KNOWN_BY} "
                f"{known_by}; a feature cannot be available before the group is knowable"
            )
    if max_contributing > feature_ns:
        raise ClockError(
            f"max_contributing_ts_recv_ns {max_contributing} exceeds the feature cutoff "
            f"{feature_ns}; a derived block consumed an input after it was computed"
        )
    return {
        CLOCK_EVENT_TIME: {
            "clock": EVENT_CLOCK,
            "first_component_ns": event[0],
            "f_last_ns": event[-1],
            "basis": BASIS_OBSERVED_ON_THE_RECORD,
        },
        CLOCK_RECEIVE_TIME: {
            "clock": CAUSAL_CLOCK,
            "first_component_ns": recv[0],
            "f_last_ns": known_by,
            "basis": BASIS_OBSERVED_ON_THE_RECORD,
        },
        CLOCK_EVENT_KNOWN_BY: {
            "clock": CAUSAL_CLOCK,
            "value_ns": known_by,
            "basis": BASIS_F_LAST_RECEIVE_OF_THE_GROUP,
        },
        CLOCK_FEATURE_AVAILABILITY: {
            "clock": CAUSAL_CLOCK,
            "value_ns": feature_ns,
            "max_contributing_ts_recv_ns": max_contributing,
            "feature_cutoff_ts_recv_ns": feature_ns,
            "basis": feature_basis,
            "scope": FEATURE_SCOPE_MEMBER_ROW,
        },
        CLOCK_PROSPECTIVE_DISCOVERY_CONFIRMATION: {
            "clock": CAUSAL_CLOCK,
            "basis": DISCOVERY_BASIS_NONE,
            "confirmed_at_this_cutoff": [],
        },
        CLOCK_MODEL_EVALUATION: {
            "clock": CAUSAL_CLOCK,
            "value_ns": None,
            "basis": EVALUATION_BASIS_NONE,
        },
        CLOCK_LOCK_TIME: {
            "clock": CAUSAL_CLOCK,
            "value_ns": None,
            "basis": LOCK_BASIS_PRINCIPAL,
        },
    }


def causal_clock_layers_from_legacy_clocks(
    clocks: Mapping[str, Any], *, ts_event_ns: int, decision_basis: str | None = None
) -> dict[str, dict[str, Any]]:
    """The seven, from a pre-S121 row's five-field `clocks` object. Three derive from the
    receive clocks; the model-evaluation clock derives from `decision_ts_recv_ns` when the
    row carries one (F-feed-5), with the row's `decision_basis` beside it; the rest are
    declared `NOT_ON_THIS_ROW` rather than filled with anything. The delivered Sunday ledger
    is such a row and stays deliverable, findable by name."""
    try:
        first_event = int(clocks["first_component_ts_event_ns"])
        first_recv = int(clocks["first_component_ts_recv_ns"])
        f_last_recv = int(clocks["f_last_ts_recv_ns"])
        known_by = int(clocks["first_lawful_availability_ns"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ClockError(f"legacy clocks object cannot support the three derivable clocks: {exc}") from exc
    absent = lambda: {"clock": CAUSAL_CLOCK, "value_ns": None, "basis": NOT_ON_THIS_ROW}  # noqa: E731
    decision = clocks.get("decision_ts_recv_ns")
    if isinstance(decision, bool) or not isinstance(decision, int):
        evaluation = absent()
    else:
        evaluation = {
            "clock": CAUSAL_CLOCK,
            "value_ns": int(decision),
            "basis": EVALUATION_BASIS_LEGACY_DECISION_TS,
            "decision_basis": (
                decision_basis if isinstance(decision_basis, str) and decision_basis
                else DECISION_BASIS_UNDECLARED_ON_ROW
            ),
        }
    return {
        CLOCK_EVENT_TIME: {
            "clock": EVENT_CLOCK, "first_component_ns": first_event, "f_last_ns": int(ts_event_ns),
            "basis": BASIS_OBSERVED_ON_THE_RECORD,
        },
        CLOCK_RECEIVE_TIME: {
            "clock": CAUSAL_CLOCK, "first_component_ns": first_recv, "f_last_ns": f_last_recv,
            "basis": BASIS_OBSERVED_ON_THE_RECORD,
        },
        CLOCK_EVENT_KNOWN_BY: {
            "clock": CAUSAL_CLOCK, "value_ns": known_by, "basis": BASIS_F_LAST_RECEIVE_OF_THE_GROUP,
        },
        CLOCK_FEATURE_AVAILABILITY: absent(),
        CLOCK_PROSPECTIVE_DISCOVERY_CONFIRMATION: absent(),
        CLOCK_MODEL_EVALUATION: evaluation,
        CLOCK_LOCK_TIME: absent(),
    }


def validate_causal_clock_layers(layers: Any) -> dict[str, dict[str, Any]]:
    """Exactly the seven ids, each naming a clock and a basis. Refused, never patched."""
    if not isinstance(layers, Mapping) or set(layers) != set(CAUSAL_CLOCK_LAYER_IDS):
        have = sorted(layers) if isinstance(layers, Mapping) else type(layers).__name__
        raise ClockError(
            f"causal_clocks must carry exactly {list(CAUSAL_CLOCK_LAYER_IDS)}; got {have}"
        )
    for layer_id, entry in layers.items():
        if not isinstance(entry, Mapping):
            raise ClockError(f"causal_clocks[{layer_id}] is not an object")
        if entry.get("clock") not in (CAUSAL_CLOCK, EVENT_CLOCK):
            raise ClockError(f"causal_clocks[{layer_id}] names no clock")
        basis = entry.get("basis")
        if not isinstance(basis, str) or not basis:
            raise ClockError(f"causal_clocks[{layer_id}] carries no basis")
    return dict(layers)


def check_causal_clock_order(layers: Mapping[str, Any]) -> dict[str, int | None]:
    """event_known_by <= feature_availability <= model_evaluation, on the delivered values.

    The order the V4 universe's `validate_availability_chain` enforces, checked here with
    three comparisons and no import from that universe. A clock declared absent (null) is
    skipped, never invented; the two present ones must still be in order.
    """
    layers = validate_causal_clock_layers(layers)
    known_by = layers[CLOCK_EVENT_KNOWN_BY].get("value_ns")
    if isinstance(known_by, bool) or not isinstance(known_by, int):
        raise ClockError(f"{CLOCK_EVENT_KNOWN_BY} carries no integer value")
    feature = layers[CLOCK_FEATURE_AVAILABILITY].get("value_ns")
    model = layers[CLOCK_MODEL_EVALUATION].get("value_ns")
    if feature is not None and feature < known_by:
        raise ClockError(
            f"{CLOCK_FEATURE_AVAILABILITY} {feature} precedes {CLOCK_EVENT_KNOWN_BY} {known_by}"
        )
    floor = known_by if feature is None else feature
    if model is not None and model < floor:
        raise ClockError(
            f"{CLOCK_MODEL_EVALUATION} {model} precedes {CLOCK_FEATURE_AVAILABILITY} {floor}; "
            "a model cannot be evaluated on features not yet available"
        )
    return {
        "event_known_by_ns": known_by,
        "feature_availability_ns": feature,
        "model_evaluation_ns": model,
    }


def stamp_model_evaluation(row: dict[str, Any], *, staged_at_recv_ns: int | None) -> dict[str, Any]:
    """Put the invocation cutoff on the row of the group at whose cutoff the cadence fired.

    None leaves the declared null: NO_INVOCATION_AT_THIS_CUTOFF is a fact about the cadence,
    not an absence of data.
    """
    layers = validate_causal_clock_layers(row["causal_clocks"])
    entry = layers[CLOCK_MODEL_EVALUATION]
    if staged_at_recv_ns is None:
        entry["value_ns"] = None
        entry["basis"] = EVALUATION_BASIS_NONE
        return entry
    entry["value_ns"] = int(staged_at_recv_ns)
    entry["basis"] = EVALUATION_BASIS_STAGED
    check_causal_clock_order(layers)
    return entry


_CONFIRMATION_KEYS = ("candidate_id", "outcome", "birth_recv_ns", "recognized_recv_ns")


def stamp_discovery_confirmations(
    row: dict[str, Any], confirmations: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    """Record every 4.11 call the traversal emitted at THIS group's cutoff.

    `recognized_recv_ns` is when the call was knowable on the candidate lane's clock;
    `confirmed_at_cutoff_ns` is the F_LAST receive at which it was actually emitted. Both
    travel, and whether the first is at or before the second is written down rather than
    assumed - a window truncated at a boundary can name an availability past the cutoff.
    """
    layers = validate_causal_clock_layers(row["causal_clocks"])
    cutoff = int(layers[CLOCK_EVENT_KNOWN_BY]["value_ns"])
    entry = layers[CLOCK_PROSPECTIVE_DISCOVERY_CONFIRMATION]
    kept: list[dict[str, Any]] = []
    for confirmation in confirmations:
        missing = [key for key in _CONFIRMATION_KEYS if key not in confirmation]
        if missing:
            raise ClockError(f"a discovery confirmation is missing {missing}")
        candidate_id = confirmation["candidate_id"]
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ClockError("a discovery confirmation must name its candidate")
        if confirmation["outcome"] not in VALID_RECOGNITION:
            raise ClockError(f"unknown recognition outcome {confirmation['outcome']!r}")
        recognized = confirmation["recognized_recv_ns"]
        kept.append({
            "candidate_id": candidate_id,
            "outcome": confirmation["outcome"],
            "birth_recv_ns": int(confirmation["birth_recv_ns"]),
            "recognized_recv_ns": None if recognized is None else int(recognized),
            "recognized_recv_ns_basis": confirmation.get("recognized_recv_ns_basis"),
            "confirmed_at_cutoff_ns": cutoff,
            "knowable_at_or_before_cutoff": None if recognized is None else int(recognized) <= cutoff,
        })
    entry["confirmed_at_this_cutoff"] = kept
    entry["basis"] = DISCOVERY_BASIS_EMITTED if kept else DISCOVERY_BASIS_NONE
    return entry


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
            # S121 item one: the producer prose lives HERE, once, and the rows carry bases.
            "causal_clock_layers": {
                "carrier": CAUSAL_CLOCKS_CARRIER,
                "layer_ids": list(CAUSAL_CLOCK_LAYER_IDS),
                "declarations": dict(CAUSAL_CLOCK_DECLARATIONS),
            },
        }
