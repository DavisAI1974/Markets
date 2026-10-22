"""Section 4.13: chain families and D-depth lineages.

`D0` is a root with no qualifying successor; `D1` and deeper are successive stages, and
"no maximum depth is imposed". So depth here is an unbounded integer computed from the
graph, never a bucket - a chain fifteen deep is recorded as fifteen rather than clipped
into a top label, because clipping is how a corpus stops being able to show you the deep
chains it contains.

Section 4.13 then forbids two things that look like ordinary reporting. Depth labels are
never averaged: a mean depth of 1.7 describes no chain that exists, so depth is reported
as a distribution over exact integers with counts. And roots, descendants, terminated,
censored and still-open chains never mix, so lineage status is part of the stratum
identity rather than a column you could forget to filter on.

The censoring clock is an INPUT here, not something the graph can find for itself. A stage's
exit time is written by its own successor - `add` stamps the parent the moment a child enters -
so a censored stage, which by definition never got a qualifying successor, has no exit and
therefore no `stage_duration_ns`. Deriving the censored age from that field made "censored" and
"has a duration" mutually exclusive by construction: on the 2021-10-03 Sunday run
`censored_stage_age_ns` reported n=0 with all 21,651 nodes excluded while 21,603 of them were
censored - the measure's declared population was exactly the population it could never observe.
Section 4.6 has no such hole because its caller hands it the boundary time at the moment it
censors (`_close(status=OPEN_AT_SEGMENT_END, recv_ns=...)`), so the age is censoring time minus
birth and never a field the subject was supposed to fill in for itself. 4.13 takes the same
input as `censoring_recv_ns`; when it is not supplied the age is ABSENT and counted, never a
zero, because a zero would be a measurement.

Two root counts live in this summary and they are different populations. `roots_total` is every
node with no parent, which is also the D0 row of the depth distribution; `d0_roots` is section
4.13's D0 class, a root with NO qualifying successor. On the Sunday run they read 21,344 and
21,296, and the 48 that separates them is the number of roots that acquired a successor. That
48 also equalled `status_counts[TERMINATED]`, but only because observed max depth was 1 so every
parent happened to be a root - a coincidence of that day, not an identity. Both counts are
carried, each with a declared definition, and the identity that links them is checked here
rather than left for a reader to guess at.
"""
from __future__ import annotations

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

ROOT = "ROOT"
DESCENDANT = "DESCENDANT"

TERMINATED = "TERMINATED"
CENSORED_SEGMENT_END = "CENSORED_SEGMENT_END"
CENSORED_STREAM_END = "CENSORED_STREAM_END"
OPEN = "OPEN"
LINEAGE_STATUSES = frozenset({TERMINATED, CENSORED_SEGMENT_END, CENSORED_STREAM_END, OPEN})
CENSORED_STATUSES = frozenset({CENSORED_SEGMENT_END, CENSORED_STREAM_END})


class LineageError(ValueError):
    """A lineage could not be constructed consistently."""


@dataclass
class LineageNode:
    """One stage in a chain. Depth is computed, never assigned."""

    node_id: str
    parent_id: str | None
    depth: int
    transition_type: str
    side_orientation: str
    entered_recv_ns: int
    exited_recv_ns: int | None = None
    status: str = OPEN

    @property
    def role(self) -> str:
        return ROOT if self.parent_id is None else DESCENDANT

    @property
    def depth_label(self) -> str:
        """`D<n>` with no ceiling. A label for reading, never a bucket for averaging."""
        return f"D{self.depth}"

    @property
    def stage_duration_ns(self) -> int | None:
        if self.exited_recv_ns is None:
            return None
        return self.exited_recv_ns - self.entered_recv_ns

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "depth_label": self.depth_label,
            "role": self.role,
            "transition_type": self.transition_type,
            "side_orientation": self.side_orientation,
            "entered_recv_ns": self.entered_recv_ns,
            "exited_recv_ns": self.exited_recv_ns,
            "stage_duration_ns": self.stage_duration_ns,
            "status": self.status,
            "clock": CAUSAL_CLOCK,
        }


class LineageGraph:
    """A deterministic parent/child graph with unbounded depth."""

    def __init__(self, *, lineage_signature: str) -> None:
        self.lineage_signature = lineage_signature
        self.nodes: dict[str, LineageNode] = {}
        self._children: dict[str, list[str]] = {}

    def add(
        self,
        *,
        node_id: str,
        parent_id: str | None,
        transition_type: str,
        side_orientation: str,
        entered_recv_ns: int,
    ) -> LineageNode:
        if node_id in self.nodes:
            raise LineageError(f"node {node_id} already exists")
        if parent_id is None:
            depth = 0
        else:
            parent = self.nodes.get(parent_id)
            if parent is None:
                raise LineageError(f"parent {parent_id} is not in the graph")
            if entered_recv_ns < parent.entered_recv_ns:
                raise LineageError("a child cannot begin before its parent")
            depth = parent.depth + 1
            if parent.exited_recv_ns is None:
                parent.exited_recv_ns = entered_recv_ns
        node = LineageNode(
            node_id=node_id,
            parent_id=parent_id,
            depth=depth,
            transition_type=transition_type,
            side_orientation=side_orientation,
            entered_recv_ns=entered_recv_ns,
        )
        self.nodes[node_id] = node
        self._children.setdefault(node_id, [])
        if parent_id is not None:
            self._children[parent_id].append(node_id)
        return node

    def children(self, node_id: str) -> list[str]:
        return list(self._children.get(node_id, []))

    def interstage_delay_ns(self, node_id: str) -> int | None:
        node = self.nodes[node_id]
        if node.parent_id is None:
            return None
        return node.entered_recv_ns - self.nodes[node.parent_id].entered_recv_ns

    @property
    def max_depth(self) -> int:
        return max((n.depth for n in self.nodes.values()), default=0)

    @property
    def roots(self) -> list[LineageNode]:
        return [n for n in self.nodes.values() if n.parent_id is None]

    def is_d0_root(self, node_id: str) -> bool:
        """A D0 root is a root with no qualifying successor, per section 4.13."""
        node = self.nodes[node_id]
        return node.parent_id is None and not self._children.get(node_id)


class LineageCalculator:
    """Streaming section 4.13 accumulator. Depth is a distribution, never a mean."""

    def __init__(self, *, exact_cap: int | None = None, seed: int = 0) -> None:
        kwargs: dict[str, Any] = {"seed": seed}
        if exact_cap is not None:
            kwargs["exact_cap"] = exact_cap

        def measure(name: str, numerator: str, status: str, missingness: str):
            return StratifiedMeasure(
                name=name,
                declaration=Declaration(
                    numerator_formula=numerator,
                    population="lineage nodes within the stratum, depth, role and status",
                    causal_cutoff="node entry receive time on ts_recv_ns",
                    status=status,
                    missingness_rule=missingness,
                ),
                **kwargs,
            )

        self.interstage_delay = measure(
            "interstage_delay_ns",
            "child entry - parent entry, one observation per descendant",
            RESOLVED,
            "roots have no parent and are excluded and counted",
        )
        self.stage_duration = measure(
            "stage_duration_ns",
            "node exit - node entry, closed stages only",
            RESOLVED,
            "still-open stages are excluded and counted; their duration is not lawful yet",
        )
        self.censored_stage_age = measure(
            "censored_stage_age_ns",
            "segment_or_stream_end.ts_recv_ns - node entry, censored stages only",
            CENSORED,
            "terminated stages are excluded and reported under stage_duration_ns; a censored "
            "stage observed without a censoring clock is excluded and counted in "
            "censored_stage_age_coverage, never entered as a zero",
        )

        self.depth_counts: dict[int, int] = {}
        self.status_counts: dict[str, int] = {name: 0 for name in sorted(LINEAGE_STATUSES)}
        self.role_counts = {ROOT: 0, DESCENDANT: 0}
        # Two root populations, counted separately at the source so the identity between them
        # is a CHECK and not a definition. Deriving one by subtracting the other is what let
        # 21,296 and 21,344 sit in one summary with nothing saying they were different things.
        self.d0_roots = 0
        self.roots_with_successor = 0
        self.nodes_with_successor = 0
        self.nodes_seen = 0
        self.observed_max_depth = 0
        # The censored channel reports its own coverage. n=0 is indistinguishable from "the
        # population was empty" unless the seen/observed/unmeasurable split travels with it.
        self.censored_stages_seen = 0
        self.censored_stage_age_observed = 0
        self.censored_stage_age_no_censoring_clock = 0
        self.open_stages_seen = 0

    @property
    def measures(self) -> tuple[StratifiedMeasure, ...]:
        return (self.interstage_delay, self.stage_duration, self.censored_stage_age)

    @staticmethod
    def _key(
        node: LineageNode,
        *,
        source_day: str,
        source_role: str,
        continuity_segment: int,
        session_phase: str,
        lineage_signature: str,
    ) -> StratumKey:
        """Depth, role and status are all in the key: section 4.13 forbids mixing them."""
        return StratumKey(
            source_day=source_day,
            source_role=source_role,
            continuity_segment=continuity_segment,
            family_id=lineage_signature,
            side_orientation=node.side_orientation,
            session_phase=session_phase,
            clock=CAUSAL_CLOCK,
            subfamily_id=(
                f"depth={node.depth}|role={node.role}"
                f"|transition={node.transition_type}|status={node.status}"
            ),
            chain_signature=lineage_signature,
        )

    def observe_node(
        self,
        node: LineageNode,
        graph: LineageGraph,
        *,
        source_day: str,
        source_role: str,
        continuity_segment: int,
        session_phase: str,
        censoring_recv_ns: int | None = None,
    ) -> dict[str, Any]:
        """Observe one node with its terminal status.

        `censoring_recv_ns` is the boundary time that ended the observation window - the
        segment close or the stream end - and it is the only lawful clock for a censored
        stage, exactly as 4.6's `_close(recv_ns=...)` is for a censored order. It is ignored
        for a stage that terminated, which carries its own exit.
        """
        if node.status not in LINEAGE_STATUSES:
            raise LineageError(f"status must be one of {sorted(LINEAGE_STATUSES)}")
        key = self._key(
            node,
            source_day=source_day,
            source_role=source_role,
            continuity_segment=continuity_segment,
            session_phase=session_phase,
            lineage_signature=graph.lineage_signature,
        )
        self.nodes_seen += 1
        self.depth_counts[node.depth] = self.depth_counts.get(node.depth, 0) + 1
        self.status_counts[node.status] += 1
        self.role_counts[node.role] += 1
        self.observed_max_depth = max(self.observed_max_depth, node.depth)
        has_successor = bool(graph.children(node.node_id))
        if has_successor:
            self.nodes_with_successor += 1
        if node.parent_id is None:
            if has_successor:
                self.roots_with_successor += 1
            else:
                self.d0_roots += 1

        delay = graph.interstage_delay_ns(node.node_id)
        if delay is None:
            self.interstage_delay.exclude_missing(key)
        else:
            self.interstage_delay.observe(key, float(delay))

        duration = node.stage_duration_ns
        if node.status == TERMINATED:
            if duration is None:
                # TERMINATED is decided FROM `exited_recv_ns` upstream, so one without an exit
                # is a caller contradiction, not a missing measurement. Refused rather than
                # excluded: an exclusion here would look like the ordinary open-stage case.
                raise LineageError("a TERMINATED stage must carry exited_recv_ns")
            self.stage_duration.observe(key, float(duration))
            self.censored_stage_age.exclude_missing(key)
        elif node.status in CENSORED_STATUSES:
            if node.exited_recv_ns is not None:
                # A stage with an exit had a qualifying successor, which is what ENDS it, so
                # it is terminated. Calling it censored would put an ended stage in the
                # censored population and read its own stage length as an age at censoring.
                raise LineageError(
                    "a stage with exited_recv_ns ended and is TERMINATED; it cannot be censored"
                )
            self.censored_stages_seen += 1
            self.stage_duration.exclude_missing(key)
            if censoring_recv_ns is None:
                # The one case that produced n=0 across all 17 strata: no clock, so no age.
                # Excluded and counted, never a zero - a zero would say the stage was censored
                # at the instant it entered.
                self.censored_stage_age.exclude_missing(key)
                self.censored_stage_age_no_censoring_clock += 1
            else:
                age = censoring_recv_ns - node.entered_recv_ns
                if age < 0:
                    raise LineageError("a censoring cannot precede the stage it censors")
                self.censored_stage_age.observe(key, float(age))
                self.censored_stage_age_observed += 1
        else:
            self.open_stages_seen += 1
            self.stage_duration.exclude_missing(key)
            self.censored_stage_age.exclude_missing(key)
        return node.as_dict()

    def depth_distribution(self) -> list[dict[str, Any]]:
        """Exact integer depths with counts.

        Reported as a distribution rather than a mean because a mean depth of 1.7 describes
        no chain that exists; section 4.13 forbids averaging depth labels.
        """
        total = sum(self.depth_counts.values())
        return [
            {
                "depth": depth,
                "depth_label": f"D{depth}",
                "count": count,
                # The D0 row is every depth-zero node, roots with a successor included, which
                # is NOT section 4.13's D0 class of "a root with no qualifying successor".
                # The two D0s differed by 48 on the Sunday run, so the population travels here
                # rather than being inferred from the label.
                "counted_population": "every node at this exact depth",
                "share_of_nodes": (count / total) if total else None,
                "share_is_a_rate_not_a_mean": True,
            }
            for depth, count in sorted(self.depth_counts.items())
        ]

    def root_reconciliation(self) -> dict[str, Any]:
        """The two root counts, each named, and the identity that links them, checked.

        `roots_total` (every parentless node, which is also the D0 row of the depth
        distribution) and `d0_roots` (4.13's D0 class: a root with NO qualifying successor)
        are different populations. On the 2021-10-03 Sunday run they read 21,344 and 21,296
        and nothing in the artifact said why, so the 48 between them looked like a defect.
        It is `roots_with_a_qualifying_successor`, counted here in its own right. It also
        equalled `status_counts[TERMINATED]` that day, but only because observed max depth
        was 1 so every parent was a root; `terminated_equals_nodes_with_a_successor` is the
        general statement and it is reported rather than assumed.
        """
        roots_total = self.role_counts[ROOT]
        depth0 = self.depth_counts.get(0, 0)
        return {
            "roots_total": roots_total,
            "roots_total_means": "EVERY_NODE_WITH_NO_PARENT",
            "d0_roots": self.d0_roots,
            "d0_roots_means": "ROOTS_WITH_NO_QUALIFYING_SUCCESSOR",
            "roots_with_a_qualifying_successor": self.roots_with_successor,
            "identity": (
                "roots_total = d0_roots + roots_with_a_qualifying_successor"
            ),
            "identity_holds": roots_total == self.d0_roots + self.roots_with_successor,
            "depth0_node_count": depth0,
            "depth0_equals_roots_total": depth0 == roots_total,
            "nodes_with_a_qualifying_successor": self.nodes_with_successor,
            "terminated_status_count": self.status_counts[TERMINATED],
            "terminated_equals_nodes_with_a_successor": (
                self.status_counts[TERMINATED] == self.nodes_with_successor
            ),
        }

    def censored_stage_age_coverage(self) -> dict[str, Any]:
        """What the censored channel saw, split from what it could measure.

        n=0 on a censored measure is ambiguous between "nothing was censored" and "everything
        censored was unmeasurable", and on the Sunday run it was the second: 21,603 censored
        nodes, none of them measured, because the boundary clock never reached this call.
        The split is reported so the two can never be read as the same number again.
        """
        return {
            "censored_stages_seen": self.censored_stages_seen,
            "censored_stage_age_observed": self.censored_stage_age_observed,
            "censored_stage_age_unmeasurable_no_censoring_clock": (
                self.censored_stage_age_no_censoring_clock
            ),
            "unmeasurable_cause": (
                "observe_node was called without censoring_recv_ns, so the boundary time that "
                "ended the observation window was never supplied; the age is absent and "
                "counted here rather than entered as a zero"
            ),
            "open_stages_seen": self.open_stages_seen,
            "open_stages_note": (
                "a still-open stage is neither terminated nor censored and contributes to "
                "neither duration measure; it is excluded and counted"
            ),
        }

    def companion_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for measure in self.measures:
            rows.extend(measure.rows())
        return rows

    def summary(self) -> dict[str, Any]:
        return {
            "section": "4.13",
            "causal_clock": CAUSAL_CLOCK,
            "nodes_seen": self.nodes_seen,
            "observed_max_depth": self.observed_max_depth,
            "maximum_depth_imposed": None,
            "d0_roots": self.d0_roots,
            "d0_roots_means": "ROOTS_WITH_NO_QUALIFYING_SUCCESSOR",
            "root_reconciliation": self.root_reconciliation(),
            "censored_stage_age_coverage": self.censored_stage_age_coverage(),
            "role_counts": dict(self.role_counts),
            "status_counts": dict(self.status_counts),
            "depth_distribution": self.depth_distribution(),
            "depth_note": (
                "depth is reported as a distribution over exact integers; a mean depth "
                "describes no chain that exists and section 4.13 forbids averaging depth labels"
            ),
            "mixing_note": (
                "role, depth, transition and status are all in the stratum key, so roots, "
                "descendants, terminated, censored and open chains cannot mix"
            ),
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
        }
