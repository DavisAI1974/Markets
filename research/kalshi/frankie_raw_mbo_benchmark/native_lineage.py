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
            "censoring time - node entry, censored stages only",
            CENSORED,
            "terminated stages are excluded and reported under stage_duration_ns",
        )

        self.depth_counts: dict[int, int] = {}
        self.status_counts: dict[str, int] = {name: 0 for name in sorted(LINEAGE_STATUSES)}
        self.role_counts = {ROOT: 0, DESCENDANT: 0}
        self.d0_roots = 0
        self.nodes_seen = 0
        self.observed_max_depth = 0

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
    ) -> dict[str, Any]:
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
        if graph.is_d0_root(node.node_id):
            self.d0_roots += 1

        delay = graph.interstage_delay_ns(node.node_id)
        if delay is None:
            self.interstage_delay.exclude_missing(key)
        else:
            self.interstage_delay.observe(key, float(delay))

        duration = node.stage_duration_ns
        if node.status == TERMINATED and duration is not None:
            self.stage_duration.observe(key, float(duration))
            self.censored_stage_age.exclude_missing(key)
        elif node.status in (CENSORED_SEGMENT_END, CENSORED_STREAM_END) and duration is not None:
            self.censored_stage_age.observe(key, float(duration))
            self.stage_duration.exclude_missing(key)
        else:
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
                "share_of_nodes": (count / total) if total else None,
                "share_is_a_rate_not_a_mean": True,
            }
            for depth, count in sorted(self.depth_counts.items())
        ]

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
