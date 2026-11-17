"""N-1: the original post's boundary mechanism, formalized as a research experiment.

The user-shared post proposed using the DIFFERENCE IN DISTANCE BETWEEN POSITION
NEIGHBORS to enable Neumann boundary conditions on a packed set of centers.
This module gives that sentence one concrete, testable meaning on a PATH of
centers:

* consecutive centers c_k, c_{k+1} at exact metric distance d_k define a
  finite-volume cell for c_k with half-widths d_{k-1}/2 and d_k/2, so the cell
  volume is V_k = (d_{k-1} + d_k) / 2 (end cells: a single half-width);
* the conductance between neighbors is D / d_k;
* where a neighbor is MISSING (the two ends of the path) there is no edge, and
  that absence IS the zero-flux (reflecting, Neumann) condition of the graph
  finite-volume scheme in graph_boundary.py.

What this establishes: a conservative, consistent one-dimensional finite-volume
discretization of u_t = D u_xx with reflecting ends, built only from neighbor
distances (tested against a manufactured solution). What it does NOT establish:
physical normals or facet areas in more than one dimension (Voronoi geometry),
any claim that market-state vectors obey a diffusion law, or any continuum
limit on an arbitrary metric space. Those stay on the physical-neumann-boundary
research gate.
"""
from __future__ import annotations
from typing import Iterable, Sequence
import math

from .core import LocalityError, MetricContract, Observation
from .graph_boundary import Edge, FluxDomain


def flux_domain_from_path(nodes: Sequence[tuple[str, float]], *,
                          diffusivity: float) -> FluxDomain:
    """Build a FluxDomain from an ordered path of (id, coordinate) pairs."""
    path=tuple(nodes)
    if len(path)<2:
        raise LocalityError("a path domain needs at least two centers")
    if not math.isfinite(diffusivity) or diffusivity<=0:
        raise LocalityError("positive finite diffusivity required")
    ids=[name for name,_ in path]
    if len(set(ids))!=len(ids) or any(not name for name in ids):
        raise LocalityError("unique nonempty center ids required")
    xs=[float(x) for _,x in path]
    if any(not math.isfinite(x) for x in xs):
        raise LocalityError("finite path coordinates required")
    gaps=[b-a for a,b in zip(xs,xs[1:])]
    if any(g<=0 for g in gaps):
        raise LocalityError("path coordinates must be strictly increasing; coincident "
                            "centers have no neighbor distance and no cell")
    volumes={}
    for k,name in enumerate(ids):
        left=gaps[k-1]/2 if k>0 else 0.
        right=gaps[k]/2 if k<len(gaps) else 0.
        volumes[name]=left+right
    edges=tuple(Edge(ids[k],ids[k+1],diffusivity/gaps[k]) for k in range(len(gaps)))
    return FluxDomain(volumes,edges,(ids[0],ids[-1]))


def path_from_centers(centers: Iterable[Observation], metric: MetricContract,
                      feature: str) -> tuple[tuple[str, float], ...]:
    """Order centers along one declared feature and place them at cumulative
    EXACT metric distance, so the path geometry reflects the full contract."""
    items=list(centers)
    if feature not in metric.features:
        raise LocalityError("ordering feature must be part of the metric contract")
    index=metric.features.index(feature)
    ordered=sorted(items,key=lambda o:(metric.vector(o)[index],o.event_id))
    path=[]
    position=0.
    for previous,current in zip([None]+ordered,ordered):
        if previous is not None:
            position+=metric.distance(previous,current)
        path.append((current.event_id,position))
    return tuple(path)
