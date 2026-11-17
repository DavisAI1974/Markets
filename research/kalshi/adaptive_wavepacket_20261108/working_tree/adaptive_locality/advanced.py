"""Bounded adaptive neighborhoods, reversible geometric packing, and stability tests.

Research-only. Distances and center membership are not proof of scientific equivalence.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from .core import Observation, MetricContract, LocalityError, gaussian_kernel

@dataclass(frozen=True)
class AdaptivePolicy:
    k:int=8
    min_bandwidth:float=0.01
    max_bandwidth:float=10.0
    min_support:int=2
    hysteresis:float=0.15
    def __post_init__(self):
        if self.k<1 or self.min_support<1 or self.min_support>self.k:
            raise LocalityError("invalid support policy")
        if not 0<self.min_bandwidth<=self.max_bandwidth or not math.isfinite(self.max_bandwidth):
            raise LocalityError("invalid bandwidth bounds")
        if not 0<=self.hysteresis<1:
            raise LocalityError("invalid hysteresis")

@dataclass(frozen=True)
class Neighborhood:
    center_id:str
    neighbors:tuple[tuple[str,float],...]
    bandwidth:float|None
    status:str

def adaptive_neighborhood(center:Observation,history:list[Observation],
                          metric:MetricContract,policy:AdaptivePolicy,
                          previous_bandwidth:float|None=None)->Neighborhood:
    """Historical-only, same-family k-nearest selection, exact deterministic distances."""
    distances=sorted(((o.event_id,metric.distance(center,o)) for o in history
                      if o.event_id!=center.event_id and o.family==center.family
                      and o.event_clock<=center.event_clock),key=lambda p:(p[1],p[0]))
    chosen=tuple(distances[:policy.k])
    if len(chosen)<policy.min_support:
        return Neighborhood(center.event_id,chosen,None,"ABSTAIN_LOW_SUPPORT")
    candidate=max(policy.min_bandwidth,min(policy.max_bandwidth,chosen[-1][1]))
    if previous_bandwidth is not None:
        if not math.isfinite(previous_bandwidth) or previous_bandwidth<=0:
            raise LocalityError("invalid previous bandwidth")
        if abs(candidate-previous_bandwidth)/previous_bandwidth<=policy.hysteresis:
            candidate=previous_bandwidth
    return Neighborhood(center.event_id,chosen,candidate,"READY")

@dataclass(frozen=True)
class PackingDecision:
    action:str
    event_id:str
    center_id:str|None
    distance:float|None
    reason:str

class PackingIndex:
    """Stable immutable representatives; splits/retirements leave audit tombstones."""
    def __init__(self,metric:MetricContract,separation:float):
        if not math.isfinite(separation) or separation<=0: raise LocalityError("invalid separation")
        self.metric=metric
        self.separation=separation
        self.centers:dict[str,Observation]={}
        self.retired:dict[str,str]={}
    def propose(self,observation:Observation)->PackingDecision:
        if observation.event_id in self.retired:
            return PackingDecision("ABSTAIN",observation.event_id,None,None,"retired identity")
        if observation.event_id in self.centers:
            if self.centers[observation.event_id].identity()!=observation.identity():
                raise LocalityError("conflicting center")
            return PackingDecision("EXISTS",observation.event_id,observation.event_id,0.0,"same center")
        self.metric.vector(observation)
        candidates=sorted(((self.metric.distance(observation,c),key) for key,c in self.centers.items()
                           if c.family==observation.family),key=lambda x:(x[0],x[1]))
        if candidates and candidates[0][0]<self.separation:
            return PackingDecision("ASSIGN_CANDIDATE",observation.event_id,candidates[0][1],
                                   candidates[0][0],"within exclusion radius; no job elimination")
        return PackingDecision("INSERT_CENTER",observation.event_id,observation.event_id,None,"separated")
    def admit_center(self,observation:Observation,decision:PackingDecision)->None:
        if decision!=self.propose(observation) or decision.action!="INSERT_CENTER":
            raise LocalityError("stale or ineligible packing decision")
        self.centers[observation.event_id]=observation
    def retire(self,center_id:str,reason:str)->None:
        if center_id not in self.centers or not reason: raise LocalityError("invalid retirement")
        self.retired[center_id]=reason
        del self.centers[center_id]
    def restore(self,observation:Observation)->None:
        if observation.event_id not in self.retired or observation.event_id in self.centers:
            raise LocalityError("not a retired center")
        del self.retired[observation.event_id]
        decision=self.propose(observation)
        if decision.action!="INSERT_CENTER":
            self.retired[observation.event_id]="restore blocked by separation"
            raise LocalityError("restoration violates separation")
        self.admit_center(observation,decision)

def window_drift(series:list[Observation],metric:MetricContract,
                 window:int,tolerance:float)->dict:
    """Finite consecutive-window drift; never infinite convergence proof."""
    if window<2 or len(series)<2*window or not math.isfinite(tolerance) or tolerance<0:
        raise LocalityError("insufficient data or invalid drift tolerance")
    first=series[-2*window:-window]
    last=series[-window:]
    def max_pair(values):
        return max(metric.distance(a,b) for a in values for b in values)
    internal=max(max_pair(first),max_pair(last))
    cross=max(metric.distance(a,b) for a in first for b in last)
    return {"stable_within_windows":internal<=tolerance,
            "stable_across_windows":cross<=tolerance,
            "max_internal":internal,"max_cross":cross,
            "claim":"FINITE_DIAGNOSTIC_ONLY"}

def localized_weights(observation:Observation,centers:list[Observation],
                      metric:MetricContract,bandwidth:float,
                      allow_cross_family:bool=False)->dict:
    """Normalized weights with explicit underflow abstention."""
    if not centers: return {"status":"ABSTAIN_EMPTY","weights":{}}
    candidates=sorted((c for c in centers if allow_cross_family or c.family==observation.family),
                      key=lambda c:c.event_id)
    if not candidates: return {"status":"ABSTAIN_FAMILY","weights":{}}
    if not math.isfinite(bandwidth) or bandwidth<=0:
        raise LocalityError("invalid bandwidth")
    logw=[]
    for c in candidates:
        ratio=metric.distance(observation,c)/bandwidth
        logw.append(-math.inf if not math.isfinite(ratio) or ratio>1e154 else -0.5*ratio*ratio)
    peak=max(logw)
    if peak == -math.inf:
        return {"status":"ABSTAIN_NUMERIC","weights":{}}
    weights=[math.exp(x-peak) for x in logw]
    denominator=sum(weights)
    if not math.isfinite(denominator) or denominator<=0:
        return {"status":"ABSTAIN_NUMERIC","weights":{}}
    return {"status":"READY","weights":{c.event_id:w/denominator for c,w in zip(candidates,weights)}}
