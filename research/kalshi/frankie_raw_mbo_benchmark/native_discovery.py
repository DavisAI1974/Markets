"""Section 4.15: open-world cluster and new-structure discovery.

Two things make this section different from the rest of the contract.

First, it is the one place where a leak could enter through a *feature* rather than through
a clock. "Outcomes, Step-1, reveal, scoring, and later causal responses are excluded from
discovery features" - so a feature name matching the forbidden set raises at schema
construction, before any data is seen. A denylist is not a perfect guard against a
creatively named feature, but it closes the path where an outcome column is passed in under
its own obvious name, which is how this actually happens.

Second, the averaging rule inverts. Everywhere else an average is a companion to exact
evidence; here it is illegal until discovery is *frozen*. An average may describe a
discovered cluster, but it "may not erase members, force assignment, determine the allowed
number of clusters, or serve as the sole discovery surface". So `cluster_summary` raises
while the model is still open, and assignment never consults a mean.

Discovery is online leader clustering: each member joins the nearest cluster within the
declared radius, or founds its own. That is genuinely streaming, deterministic given the
schema and the input order, and open-world by construction - singletons and unmatched
members are outcomes of the method rather than exceptions to it. `mode` records whether the
run is the live-lawful `INCREMENTAL` form or the `RETROSPECTIVE` form, because the two
answer different questions and the distinction must travel with the output.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

CAUSAL_CLOCK = "ts_recv_ns"

INCREMENTAL = "INCREMENTAL"
RETROSPECTIVE = "RETROSPECTIVE"
VALID_MODES = frozenset({INCREMENTAL, RETROSPECTIVE})

UNASSIGNED = "UNASSIGNED"

# Feature-name fragments that would carry an answer into discovery.
FORBIDDEN_FEATURE_FRAGMENTS = (
    "outcome",
    "step1",
    "step_1",
    "reveal",
    "score",
    "scoring",
    "label",
    "target",
    "answer",
    "future",
    "response",
    "realized",
    "settle",
    "pnl",
    "profit",
)


class DiscoveryError(ValueError):
    """A discovery schema or assignment violated section 4.15."""


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class FeatureSchema:
    """Hash-bound feature schema, scaling, distance and seed.

    Validated at construction rather than at use: a forbidden feature should be impossible
    to build a schema around, not merely impossible to score with.
    """

    version: str
    feature_names: tuple[str, ...]
    scaling: Mapping[str, tuple[float, float]]
    distance: str
    radius: float
    seed: int
    mode: str

    def __post_init__(self) -> None:
        if not self.feature_names:
            raise DiscoveryError("a discovery schema needs at least one feature")
        if len(set(self.feature_names)) != len(self.feature_names):
            raise DiscoveryError("feature names must be unique")
        if self.mode not in VALID_MODES:
            raise DiscoveryError(f"mode must be one of {sorted(VALID_MODES)}")
        if self.distance != "EUCLIDEAN_ON_SCALED_FEATURES":
            raise DiscoveryError("only EUCLIDEAN_ON_SCALED_FEATURES is implemented")
        if self.radius <= 0:
            raise DiscoveryError("radius must be positive")
        for name in self.feature_names:
            lowered = name.lower()
            for fragment in FORBIDDEN_FEATURE_FRAGMENTS:
                if fragment in lowered:
                    raise DiscoveryError(
                        f"feature '{name}' matches forbidden fragment '{fragment}'; section 4.15 "
                        "excludes outcomes, Step-1, reveal, scoring and later causal responses "
                        "from discovery features"
                    )
            if name not in self.scaling:
                raise DiscoveryError(f"feature '{name}' has no declared scaling")
            centre, scale = self.scaling[name]
            if scale <= 0:
                raise DiscoveryError(f"scaling for '{name}' must have a positive scale")

    @property
    def schema_hash(self) -> str:
        return _canonical_hash(
            {
                "version": self.version,
                "feature_names": list(self.feature_names),
                "scaling": {k: list(v) for k, v in sorted(self.scaling.items())},
                "distance": self.distance,
                "radius": self.radius,
                "seed": self.seed,
                "mode": self.mode,
            }
        )

    def vector(self, features: Mapping[str, float]) -> tuple[float, ...]:
        missing = [name for name in self.feature_names if name not in features]
        if missing:
            raise DiscoveryError(f"member is missing declared features: {missing}")
        extra = set(features) - set(self.feature_names)
        if extra:
            raise DiscoveryError(f"member carries undeclared features: {sorted(extra)}")
        scaled = []
        for name in self.feature_names:
            centre, scale = self.scaling[name]
            scaled.append((float(features[name]) - centre) / scale)
        return tuple(scaled)

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "feature_names": list(self.feature_names),
            "scaling": {k: list(v) for k, v in sorted(self.scaling.items())},
            "distance": self.distance,
            "radius": self.radius,
            "seed": self.seed,
            "mode": self.mode,
            "schema_hash": self.schema_hash,
            "forbidden_fragments": list(FORBIDDEN_FEATURE_FRAGMENTS),
        }


@dataclass
class Cluster:
    """A discovered cluster. Its centroid is a location, not a decision rule."""

    cluster_id: str
    centroid: tuple[float, ...]
    member_ids: list[str] = field(default_factory=list)
    founded_recv_ns: int = 0
    merged_into: str | None = None

    @property
    def support(self) -> int:
        return len(self.member_ids)

    @property
    def is_singleton(self) -> bool:
        return self.support == 1

    def absorb(self, vector: tuple[float, ...], member_id: str) -> None:
        n = self.support
        self.centroid = tuple(
            (existing * n + new) / (n + 1) for existing, new in zip(self.centroid, vector)
        )
        self.member_ids.append(member_id)

    def as_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "centroid": list(self.centroid),
            "support": self.support,
            "is_singleton": self.is_singleton,
            "founded_recv_ns": self.founded_recv_ns,
            "merged_into": self.merged_into,
            "member_ids": list(self.member_ids),
        }


def _euclidean(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


class DiscoveryCalculator:
    """Online open-world clustering with a hard freeze before any average."""

    def __init__(self, schema: FeatureSchema) -> None:
        self.schema = schema
        self.clusters: dict[str, Cluster] = {}
        self.assignments: list[dict[str, Any]] = []
        self.unassigned: list[dict[str, Any]] = []
        self._next_cluster = 0
        self._frozen = False
        self.training_population = 0
        self.splits = 0
        self.merges = 0

    @property
    def frozen(self) -> bool:
        return self._frozen

    @property
    def cluster_count(self) -> int:
        return sum(1 for c in self.clusters.values() if c.merged_into is None)

    @property
    def singleton_count(self) -> int:
        return sum(1 for c in self.clusters.values() if c.merged_into is None and c.is_singleton)

    def _new_cluster_id(self) -> str:
        cluster_id = f"C{self._next_cluster:06d}"
        self._next_cluster += 1
        return cluster_id

    def assign(
        self,
        *,
        member_id: str,
        features: Mapping[str, float],
        recv_ns: int,
    ) -> dict[str, Any]:
        """Assign one member. Nearest cluster within radius, else a new one.

        No average is consulted to decide the number of clusters: the radius and the data
        decide, which is what section 4.15 means by an average never determining the allowed
        number of clusters.
        """
        if self._frozen:
            raise DiscoveryError("discovery is frozen; no further members may be assigned")
        vector = self.schema.vector(features)
        self.training_population += 1

        best_id: str | None = None
        best_distance = float("inf")
        for cluster in self.clusters.values():
            if cluster.merged_into is not None:
                continue
            distance = _euclidean(vector, cluster.centroid)
            if distance < best_distance:
                best_distance, best_id = distance, cluster.cluster_id

        if best_id is None or best_distance > self.schema.radius:
            cluster_id = self._new_cluster_id()
            self.clusters[cluster_id] = Cluster(
                cluster_id=cluster_id,
                centroid=vector,
                member_ids=[member_id],
                founded_recv_ns=recv_ns,
            )
            record = {
                "member_id": member_id,
                "cluster_id": cluster_id,
                "distance": 0.0,
                "support_at_assignment": 1,
                "founded_new_cluster": True,
                "assigned_recv_ns": recv_ns,
                "schema_hash": self.schema.schema_hash,
                "mode": self.schema.mode,
            }
        else:
            cluster = self.clusters[best_id]
            cluster.absorb(vector, member_id)
            record = {
                "member_id": member_id,
                "cluster_id": best_id,
                "distance": best_distance,
                "support_at_assignment": cluster.support,
                "founded_new_cluster": False,
                "assigned_recv_ns": recv_ns,
                "schema_hash": self.schema.schema_hash,
                "mode": self.schema.mode,
            }
        self.assignments.append(record)
        return record

    def record_unassigned(self, *, member_id: str, reason: str, recv_ns: int) -> dict[str, Any]:
        """Preserve a member discovery could not place. Section 4.15 requires it stays."""
        if self._frozen:
            raise DiscoveryError("discovery is frozen")
        record = {
            "member_id": member_id,
            "cluster_id": UNASSIGNED,
            "reason": reason,
            "recv_ns": recv_ns,
            "schema_hash": self.schema.schema_hash,
        }
        self.unassigned.append(record)
        return record

    def note_split(self, *, parent_cluster_id: str) -> None:
        if parent_cluster_id not in self.clusters:
            raise DiscoveryError(f"unknown cluster {parent_cluster_id}")
        self.splits += 1

    def merge(self, *, source_cluster_id: str, target_cluster_id: str) -> None:
        if source_cluster_id not in self.clusters or target_cluster_id not in self.clusters:
            raise DiscoveryError("both clusters must exist to merge")
        if source_cluster_id == target_cluster_id:
            raise DiscoveryError("a cluster cannot merge into itself")
        source = self.clusters[source_cluster_id]
        target = self.clusters[target_cluster_id]
        for member_id in source.member_ids:
            target.member_ids.append(member_id)
        source.merged_into = target_cluster_id
        self.merges += 1

    def freeze(self) -> dict[str, Any]:
        """Fix membership and version. Only after this may a cluster be described."""
        self._frozen = True
        return {
            "frozen": True,
            "schema": self.schema.as_dict(),
            "training_population": self.training_population,
            "cluster_count": self.cluster_count,
            "singleton_count": self.singleton_count,
            "unassigned_count": len(self.unassigned),
            "membership_hash": _canonical_hash(
                {
                    c.cluster_id: sorted(c.member_ids)
                    for c in self.clusters.values()
                    if c.merged_into is None
                }
            ),
        }

    def cluster_summary(self) -> list[dict[str, Any]]:
        """Descriptive centroids and prevalence, legal only once frozen.

        Exemplars and boundary members ride alongside the centroid because section 4.15
        keeps them coequal with it: a centroid that appears without its boundary members
        looks tighter than the cluster actually is.
        """
        if not self._frozen:
            raise DiscoveryError(
                "discovery is not frozen; an average may not describe a cluster whose "
                "membership can still change"
            )
        live = [c for c in self.clusters.values() if c.merged_into is None]
        total = sum(c.support for c in live)
        distance_by_member = {row["member_id"]: row["distance"] for row in self.assignments}
        rows = []
        for cluster in sorted(live, key=lambda c: c.cluster_id):
            members = sorted(cluster.member_ids, key=lambda m: distance_by_member.get(m, 0.0))
            rows.append(
                {
                    "cluster_id": cluster.cluster_id,
                    "schema_hash": self.schema.schema_hash,
                    "schema_version": self.schema.version,
                    "mode": self.schema.mode,
                    "support": cluster.support,
                    "prevalence": (cluster.support / total) if total else None,
                    "prevalence_is_a_rate_not_a_mean": True,
                    "descriptive_centroid": list(cluster.centroid),
                    "is_singleton": cluster.is_singleton,
                    "nearest_exemplar": members[0] if members else None,
                    "boundary_member": members[-1] if members else None,
                    "member_ids": list(cluster.member_ids),
                    "note": (
                        "this centroid describes a frozen membership; it did not determine "
                        "the cluster count, force any assignment, or replace any member"
                    ),
                }
            )
        return rows

    def summary(self) -> dict[str, Any]:
        return {
            "section": "4.15",
            "causal_clock": CAUSAL_CLOCK,
            "mode": self.schema.mode,
            "schema_hash": self.schema.schema_hash,
            "frozen": self._frozen,
            "training_population": self.training_population,
            "cluster_count": self.cluster_count,
            "singleton_count": self.singleton_count,
            "unassigned_count": len(self.unassigned),
            "splits": self.splits,
            "merges": self.merges,
            "leak_guard": (
                "forbidden feature fragments are rejected at schema construction, before any "
                "data is seen"
            ),
            "average_rule": (
                "no cluster may be described until discovery is frozen; an average never "
                "determines the cluster count, forces an assignment, or erases a member"
            ),
        }
