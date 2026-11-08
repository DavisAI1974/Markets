"""Locality and finite-convergence diagnostics. No scientific work is suppressed here."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping, Sequence
from types import MappingProxyType
import hashlib
import json
import math

class LocalityError(ValueError):
    pass

def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",",":"), allow_nan=False).encode()).hexdigest()

@dataclass(frozen=True)
class Observation:
    event_id: str
    family: str
    features: Mapping[str, float]
    event_clock: int
    provenance: str
    order_id: str | None = None
    member_id: str | None = None
    direction: str | None = None
    def __post_init__(self):
        if not self.event_id or not self.family or not self.provenance:
            raise LocalityError("event, family and provenance required")
        if not isinstance(self.event_clock, int) or isinstance(self.event_clock, bool):
            raise LocalityError("integer causal clock required")
        if not isinstance(self.features, Mapping):
            raise LocalityError("feature mapping required")
        if any(not isinstance(k, str) or not k for k in self.features):
            raise LocalityError("feature names must be nonempty strings")
        if any(not isinstance(v, (float,int)) or isinstance(v,bool) or not math.isfinite(v)
               for v in self.features.values()):
            raise LocalityError("features must be finite numbers")
        object.__setattr__(self, "features", MappingProxyType(dict(self.features)))
    def identity(self):
        return _digest({"id":self.event_id,"family":self.family,"features":dict(self.features),
                        "clock":self.event_clock,"provenance":self.provenance,
                        "order":self.order_id,"member":self.member_id,"direction":self.direction})

@dataclass(frozen=True)
class MetricContract:
    features: tuple[str,...]
    scales: tuple[float,...]
    weights: tuple[float,...]
    version: str
    def __post_init__(self):
        if not self.version or not self.features or len(set(self.features))!=len(self.features):
            raise LocalityError("version and unique metric features required")
        if len(self.features)!=len(self.scales) or len(self.features)!=len(self.weights):
            raise LocalityError("feature/scales/weights lengths differ")
        if any(not isinstance(k, str) or not k for k in self.features):
            raise LocalityError("invalid metric feature name")
        if any(not isinstance(v, (int,float)) or isinstance(v, bool) for v in (*self.scales,*self.weights)):
            raise LocalityError("numeric scales/weights required")
        object.__setattr__(self,"features",tuple(self.features))
        object.__setattr__(self,"scales",tuple(self.scales))
        object.__setattr__(self,"weights",tuple(self.weights))
        if any(not math.isfinite(x) or x<=0 for x in self.scales):
            raise LocalityError("scales must be positive and finite")
        if any(not math.isfinite(x) or x<0 for x in self.weights) or sum(self.weights)<=0 or not math.isfinite(sum(self.weights)):
            raise LocalityError("nonnegative weights with positive sum required")
        if any(k.lower().endswith(("id","_id","name","descriptor")) for k in self.features):
            raise LocalityError("identifiers and descriptors cannot drive metric")
    def vector(self, obs: Observation) -> tuple[float,...]:
        if any(k not in obs.features for k in self.features):
            raise LocalityError("missing metric feature; abstain, do not impute")
        result = tuple(float(obs.features[k])/s for k,s in zip(self.features,self.scales))
        if any(not math.isfinite(x) for x in result):
            raise LocalityError("normalized feature overflow")
        return result
    def distance(self,a:Observation,b:Observation)->float:
        x,y=self.vector(a),self.vector(b)
        terms = tuple(math.sqrt(w)*(u-v) for w,u,v in zip(self.weights,x,y) if w>0)
        if any(not math.isfinite(t) for t in terms):
            raise LocalityError("metric coordinate overflow")
        distance=math.hypot(*terms)
        if not math.isfinite(distance):
            raise LocalityError("metric distance overflow")
        return distance
    def identity(self)->str:
        return _digest({"features":self.features,"scales":self.scales,"weights":self.weights,"version":self.version})

def gaussian_kernel(distance:float, bandwidth:float)->float:
    if not math.isfinite(distance) or distance<0 or not math.isfinite(bandwidth) or bandwidth<=0:
        raise LocalityError("invalid kernel distance/bandwidth")
    return math.exp(-0.5*(distance/bandwidth)**2)

@dataclass(frozen=True)
class Diagnostic:
    finite_window: bool
    max_distance: float
    tolerance: float
    sample_count: int
    """This diagnostic never claims infinite Cauchy convergence."""

def finite_cauchy(sequence:Sequence[Observation], metric:MetricContract,
                  tolerance:float, window:int)->Diagnostic:
    if window<2 or len(sequence)<window or not math.isfinite(tolerance) or tolerance<0:
        raise LocalityError("insufficient sequence or invalid tolerance")
    sample=sequence[-window:]
    largest=max(metric.distance(sample[i],sample[j]) for i in range(window) for j in range(i+1,window))
    return Diagnostic(largest<=tolerance,largest,tolerance,window)

@dataclass(frozen=True)
class LocalityConfig:
    radius: float
    bandwidth: float
    max_neighbors: int=64
    allow_cross_family: bool=False
    def __post_init__(self):
        if self.radius<=0 or not math.isfinite(self.radius) or self.bandwidth<=0 or not math.isfinite(self.bandwidth):
            raise LocalityError("radius/bandwidth must be finite positive")
        if type(self.max_neighbors) is not int or self.max_neighbors<1:
            raise LocalityError("max_neighbors must be a positive integer")

@dataclass(frozen=True)
class Decision:
    event_id: str
    candidates: tuple[tuple[str,float,float],...]
    proposed_center: str | None
    status: str
    reason: str
    metric_identity: str
    evidence_identity: str

class LocalityEngine:
    """Conservative deterministic candidate selection; never removes jobs or evidence."""
    def __init__(self, metric:MetricContract, config:LocalityConfig):
        self.metric=metric
        self.config=config
        self._observations:dict[str,Observation]={}
        self._centers:dict[str,Observation]={}
    @property
    def centers(self):
        return tuple(sorted(self._centers))
    @property
    def count(self):
        return len(self._observations)
    def propose(self,obs:Observation)->Decision:
        if obs.event_id in self._observations:
            if self._observations[obs.event_id].identity()!=obs.identity():
                raise LocalityError("conflicting event identity")
            return Decision(obs.event_id,(),None,"DUPLICATE","identical event already present",
                            self.metric.identity(),obs.identity())
        self.metric.vector(obs)
        neighbors=[]
        for key,center in self._centers.items():
            if center.family!=obs.family and not self.config.allow_cross_family:
                continue
            distance=self.metric.distance(obs,center)
            if distance<=self.config.radius:
                neighbors.append((key,distance,gaussian_kernel(distance,self.config.bandwidth)))
        neighbors.sort(key=lambda x:(x[1],x[0]))
        neighbors=neighbors[:self.config.max_neighbors]
        if not neighbors:
            return Decision(obs.event_id,(),obs.event_id,"NEW_CENTER","no eligible center",
                            self.metric.identity(),obs.identity())
        total=sum(x[2] for x in neighbors)
        if total<=0:
            return Decision(obs.event_id,(),None,"ABSTAIN","kernel underflow",
                            self.metric.identity(),obs.identity())
        normalized=tuple((key,d,w/total) for key,d,w in neighbors)
        return Decision(obs.event_id,normalized,normalized[0][0],"PROPOSE_ONLY",
                        "candidate similarity is not scientific equivalence",
                        self.metric.identity(),obs.identity())
    def admit(self,obs:Observation,decision:Decision)->None:
        if decision.event_id!=obs.event_id or decision.evidence_identity!=obs.identity() or decision.metric_identity!=self.metric.identity():
            raise LocalityError("stale or incompatible decision")
        if obs.event_id in self._observations:
            if self._observations[obs.event_id].identity()!=obs.identity():
                raise LocalityError("conflicting event identity")
            return
        current=self.propose(obs)
        if current!=decision:
            raise LocalityError("neighborhood changed; recompute decision")
        if decision.status not in ("NEW_CENTER","PROPOSE_ONLY"):
            raise LocalityError("only new evidence may be admitted")
        self._observations[obs.event_id]=obs
        if decision.status=="NEW_CENTER":
            self._centers[obs.event_id]=obs
    def snapshot(self)->dict:
        return {"metric":self.metric.identity(),"events":{k:v.identity() for k,v in sorted(self._observations.items())},
                "centers":list(self.centers)}

def graph_neumann_residual(values:Mapping[str,float],edges:Sequence[tuple[str,str,float]],
                           boundary_nodes:Sequence[str],flux:Mapping[str,float]|None=None)->dict[str,float]:
    """Graph weighted flux residual; NOT a continuum Neumann PDE proof."""
    residual={node:0.0 for node in boundary_nodes}
    for a,b,weight in edges:
        if a not in values or b not in values or not math.isfinite(weight) or weight<0:
            raise LocalityError("invalid graph edge")
        if a in residual: residual[a]+=weight*(values[b]-values[a])
        if b in residual: residual[b]+=weight*(values[a]-values[b])
    flux=flux or {}
    for node in residual:
        if node not in values: raise LocalityError("missing boundary node")
        residual[node]-=flux.get(node,0.0)
    return residual
