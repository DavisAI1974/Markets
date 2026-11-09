"""Optional graph finite-volume flux operator on an explicitly supplied domain.

A graph residual is a discrete approximation; this module makes no continuum
Neumann claim without an independently validated geometric discretization.
"""
from dataclasses import dataclass
import math
from .core import LocalityError

@dataclass(frozen=True)
class Edge:
    a:str
    b:str
    conductance:float
    def __post_init__(self):
        if self.a==self.b or not self.a or not self.b:
            raise LocalityError("distinct graph endpoints required")
        if not math.isfinite(self.conductance) or self.conductance<=0:
            raise LocalityError("positive finite conductance required")

@dataclass(frozen=True)
class FluxDomain:
    volumes:dict[str,float]
    edges:tuple[Edge,...]
    boundary:tuple[str,...]
    def __post_init__(self):
        if not self.volumes or any(not math.isfinite(v) or v<=0 for v in self.volumes.values()):
            raise LocalityError("finite positive cell volumes required")
        if len(set(self.boundary))!=len(self.boundary) or not set(self.boundary)<=set(self.volumes):
            raise LocalityError("invalid boundary set")
        seen=set()
        for e in self.edges:
            if e.a not in self.volumes or e.b not in self.volumes:
                raise LocalityError("edge outside domain")
            key=tuple(sorted((e.a,e.b)))
            if key in seen: raise LocalityError("duplicate edge")
            seen.add(key)

def divergence(domain:FluxDomain,field:dict[str,float])->dict[str,float]:
    if set(field)!=set(domain.volumes) or any(not math.isfinite(v) for v in field.values()):
        raise LocalityError("incomplete finite field")
    result={k:0.0 for k in domain.volumes}
    for e in domain.edges:
        flux=e.conductance*(field[e.b]-field[e.a])
        result[e.a]+=flux/domain.volumes[e.a]
        result[e.b]-=flux/domain.volumes[e.b]
    return result

def conservative_step(domain:FluxDomain,field:dict[str,float],dt:float,
                      outward_flux:dict[str,float]|None=None)->dict[str,float]:
    """Explicit Euler step with prescribed outward boundary flux per cell.

    Caller must independently establish a stable dt for the domain.
    """
    if not math.isfinite(dt) or dt<=0: raise LocalityError("invalid time step")
    outward_flux=outward_flux or {}
    if not set(outward_flux)<=set(domain.boundary):
        raise LocalityError("flux specified at non-boundary cell")
    if any(not math.isfinite(v) for v in outward_flux.values()):
        raise LocalityError("invalid boundary flux")
    derivative=divergence(domain,field)
    return {k:field[k]+dt*(derivative[k]-outward_flux.get(k,0.0)/domain.volumes[k])
            for k in field}

def total_mass(domain:FluxDomain,field:dict[str,float])->float:
    if set(field)!=set(domain.volumes): raise LocalityError("incomplete field")
    return sum(domain.volumes[k]*field[k] for k in domain.volumes)

def stable_explicit_dt(domain:FluxDomain)->float:
    rates={k:0.0 for k in domain.volumes}
    for edge in domain.edges:
        rates[edge.a]+=edge.conductance/domain.volumes[edge.a]
        rates[edge.b]+=edge.conductance/domain.volumes[edge.b]
    maximum=max(rates.values())
    return 1/maximum if maximum else math.inf
