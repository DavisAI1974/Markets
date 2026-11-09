"""Exact-verification spatial index for conservative, standalone locality proposals.

Grid acceleration is used only at low dimensionality. High-dimensional queries
fall back to a complete exact scan instead of silently dropping candidates.
No scientific work is deduplicated by this index.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from collections import defaultdict
import math
from .core import Observation, MetricContract, LocalityError, _digest


@dataclass(frozen=True)
class IndexedHit:
    center_id: str
    distance: float
    evidence_identity: str


class ExactGridIndex:
    """Bounded query fanout with exact validation; immutable center identities."""

    def __init__(self, metric: MetricContract, radius: float, *, max_cells: int = 729):
        if not math.isfinite(radius) or radius <= 0 or max_cells < 1:
            raise LocalityError("invalid index policy")
        self.metric = metric
        self.radius = radius
        self.max_cells = max_cells
        self._active: dict[str, Observation] = {}
        self._cells: dict[tuple, set[str]] = defaultdict(set)
        self._retired: dict[str, str] = {}
        self._archive: dict[str, tuple[Observation, str]] = {}
        self._revision = 0
        self._dimensions = tuple(i for i, w in enumerate(metric.weights) if w > 0)
        self._grid_enabled = 3 ** len(self._dimensions) <= max_cells

    def _key(self, obs: Observation) -> tuple:
        vector = self.metric.vector(obs)
        coords = []
        for i in self._dimensions:
            weighted = math.sqrt(self.metric.weights[i]) * vector[i]
            if not math.isfinite(weighted):
                raise LocalityError("weighted coordinate overflow")
            scaled = weighted / self.radius
            if not math.isfinite(scaled):
                raise LocalityError("index cell coordinate overflow")
            coords.append(math.floor(scaled))
        return tuple(coords)

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def count(self) -> int:
        return len(self._active)

    @property
    def indexed(self) -> bool:
        return self._grid_enabled

    def add(self, obs: Observation) -> str:
        if obs.event_id in self._retired:
            raise LocalityError("retired center cannot be silently reused")
        old = self._active.get(obs.event_id)
        if old is not None:
            if old.identity() != obs.identity():
                raise LocalityError("conflicting center identity")
            return "EXISTS"
        key = self._key(obs)
        self._active[obs.event_id] = obs
        self._cells[(obs.family, key)].add(obs.event_id)
        self._revision += 1
        return "ADDED"

    def retire(self, center_id: str, reason: str) -> None:
        if center_id not in self._active or not reason:
            raise LocalityError("unknown center or empty retirement reason")
        obs = self._active.pop(center_id)
        cell = (obs.family, self._key(obs))
        self._cells[cell].remove(center_id)
        if not self._cells[cell]:
            del self._cells[cell]
        self._retired[center_id] = _digest({"identity": obs.identity(), "reason": reason})
        self._archive[center_id] = (obs, reason)
        self._revision += 1

    def restore(self, obs: Observation) -> None:
        archived = self._archive.get(obs.event_id)
        if archived is None or obs.event_id not in self._retired:
            raise LocalityError("no retired center")
        original, reason = archived
        if original.identity() != obs.identity():
            raise LocalityError("restoration evidence mismatch")
        if self._retired[obs.event_id] != _digest({"identity": original.identity(), "reason": reason}):
            raise LocalityError("retirement history mismatch")
        del self._retired[obs.event_id]
        del self._archive[obs.event_id]
        self.add(original)

    def candidates(self, obs: Observation, *, allow_cross_family: bool = False,
                   max_neighbors: int | None = None) -> tuple[IndexedHit, ...]:
        key = self._key(obs)
        if max_neighbors is not None and max_neighbors < 1:
            raise LocalityError("invalid neighbor limit")
        if self._grid_enabled:
            families = sorted({x.family for x in self._active.values()}) if allow_cross_family else [obs.family]
            ids: set[str] = set()
            for family in families:
                for offsets in product((-1, 0, 1), repeat=len(key)):
                    cell = tuple(a + b for a, b in zip(key, offsets))
                    ids.update(self._cells.get((family, cell), ()))
        else:
            ids = {k for k, x in self._active.items() if allow_cross_family or x.family == obs.family}
        result = []
        for center_id in ids:
            center = self._active[center_id]
            distance = self.metric.distance(obs, center)
            if not math.isfinite(distance):
                raise LocalityError("non-finite exact distance")
            if distance <= self.radius:
                result.append(IndexedHit(center_id, distance, center.identity()))
        result.sort(key=lambda h: (h.distance, h.center_id))
        if max_neighbors is not None:
            result = result[:max_neighbors]
        return tuple(result)

    def snapshot(self) -> dict:
        return {"schema": 1, "metric": self.metric.identity(), "radius": self.radius,
                "revision": self._revision, "centers": [
                    {"event_id": k, "evidence_identity": v.identity(), "family": v.family}
                    for k, v in sorted(self._active.items())],
                "retired": dict(sorted(self._retired.items())),
                "no_scientific_jobs_eliminated": True}
