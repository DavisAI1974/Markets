"""Source-bound information observables without replacing original evidence.

H: discrete histogram Shannon entropy (nats).
MI: discrete pairwise mutual information on exactly aligned ensemble members.
FI: explicitly a fixed-bin, location-roughness Fisher-LIKE proxy, not
    parameter Fisher information; no physical Fisher claim is made.

Fixed, independently supplied bins prevent silently fitting bin ranges on
future test frames. Any missing/extra member, out-of-bin value or non-finite
source value requires review. No clipping, interpolation, imputation or loss.
"""
from __future__ import annotations
from bisect import bisect_right
from dataclasses import dataclass, asdict
from itertools import combinations
import math

from .core import LocalityError, _digest


@dataclass(frozen=True)
class RawMember:
    evidence_id: str
    member_id: str
    node: str
    value: float
    provenance: str
    order_id: str | None = None
    direction: str | None = None

    def __post_init__(self):
        if not all((self.evidence_id, self.member_id, self.node, self.provenance)):
            raise LocalityError("raw scientific identity fields required")
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)) or not math.isfinite(self.value):
            raise LocalityError("raw measurement must be finite; preserve bad source separately for review")


@dataclass(frozen=True)
class RawFrame:
    clock: int
    source_identity: str
    samples: tuple[RawMember, ...]

    def __post_init__(self):
        if type(self.clock) is not int or not self.source_identity or not self.samples:
            raise LocalityError("invalid raw frame source or clock")
        object.__setattr__(self, "samples", tuple(self.samples))
        if any(not isinstance(s, RawMember) for s in self.samples):
            raise LocalityError("RawMember records required")
        if len({s.evidence_id for s in self.samples}) != len(self.samples):
            raise LocalityError("conflicting or duplicate raw event ID")

    def identity(self) -> str:
        # Preserve source ordering, every value, IDs, direction and provenance.
        return _digest({"clock":self.clock,"source":self.source_identity,
                        "samples":[asdict(s) for s in self.samples]})


@dataclass(frozen=True)
class FixedBins:
    source_identity: str
    version: str
    edges: tuple[tuple[str, tuple[float, ...]], ...]

    def __post_init__(self):
        if not self.source_identity or not self.version or not self.edges:
            raise LocalityError("fixed calibration identity and bins required")
        frozen=tuple((node,tuple(v)) for node,v in self.edges)
        if any(not node or len(v)<4 for node,v in frozen) or len({k for k,_ in frozen})!=len(frozen):
            raise LocalityError("unique nodes with >=3 histogram bins required")
        for node,edges in frozen:
            if any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) for x in edges):
                raise LocalityError("fixed bin edges must be finite")
            widths=[b-a for a,b in zip(edges,edges[1:])]
            if min(widths)<=0 or not all(math.isclose(w,widths[0],rel_tol=1e-10,abs_tol=1e-12)
                                         for w in widths):
                raise LocalityError("Fisher-like proxy requires equally spaced frozen bins")
        object.__setattr__(self,"edges",tuple(sorted(frozen)))

    def identity(self) -> str:
        return _digest({"source":self.source_identity,"version":self.version,
                        "edges":self.edges})


@dataclass(frozen=True)
class InfoFrame:
    clock: int
    source_identity: str
    calibration_identity: str
    raw_identity: str
    raw_evidence_ids: tuple[str, ...]
    raw_count: int
    entropy: tuple[tuple[str,float], ...]
    fisher_proxy: tuple[tuple[str,float], ...]
    mi: tuple[tuple[str,str,float], ...]
    status: str
    review_reasons: tuple[str, ...]

    def identity(self):
        return _digest(asdict(self))


def _bin(value: float, edges: tuple[float, ...]) -> int | None:
    if value < edges[0] or value > edges[-1]:
        return None
    return min(len(edges)-2,bisect_right(edges,value)-1)


def derive_information(raw: RawFrame, bins: FixedBins) -> InfoFrame:
    if raw.source_identity!=bins.source_identity:
        raise LocalityError("information calibration source mismatch")
    edge_map=dict(bins.edges)
    grouped={n:{} for n in edge_map}
    issues=[]
    for sample in raw.samples:
        if sample.node not in grouped:
            issues.append("UNRECOGNIZED_NODE:"+sample.evidence_id)
            continue
        if sample.member_id in grouped[sample.node]:
            issues.append("DUPLICATE_MEMBER:"+sample.evidence_id)
            continue
        position=_bin(sample.value,edge_map[sample.node])
        if position is None:
            issues.append("OUT_OF_FROZEN_RANGE:"+sample.evidence_id)
        grouped[sample.node][sample.member_id]=position
    members=[set(g) for g in grouped.values()]
    if not all(m==members[0] for m in members) or not members[0]:
        issues.append("UNALIGNED_ENSEMBLE_MEMBERS")
    ids=tuple(s.evidence_id for s in raw.samples)
    if issues:
        return InfoFrame(raw.clock,raw.source_identity,bins.identity(),raw.identity(),ids,
                         len(ids),(),(),(),"REVIEW_REQUIRED",tuple(issues))
    entropies={}
    fishers={}
    counts={}
    for node,edges in bins.edges:
        values=[0]* (len(edges)-1)
        for position in grouped[node].values():
            values[position]+=1
        total=len(grouped[node])
        p=[count/total for count in values]
        entropies[node]=-math.fsum(q*math.log(q) for q in p if q>0)
        step=edges[1]-edges[0]
        fishers[node]=4*math.fsum((math.sqrt(p[i+1])-math.sqrt(p[i]))**2
                                for i in range(len(p)-1))/(step*step)
        counts[node]=p
    mutual=[]
    for a,b in combinations(sorted(edge_map),2):
        m=len(edge_map[a])-1
        n=len(edge_map[b])-1
        joint=[[0]*n for _ in range(m)]
        for member in grouped[a]:
            joint[grouped[a][member]][grouped[b][member]]+=1
        total=len(grouped[a])
        mutual.append((a,b,math.fsum(
            (v/total)*math.log((v/total)/(counts[a][i]*counts[b][j]))
            for i,row in enumerate(joint) for j,v in enumerate(row) if v>0)))
    return InfoFrame(raw.clock,raw.source_identity,bins.identity(),raw.identity(),ids,len(ids),
                     tuple(sorted(entropies.items())),tuple(sorted(fishers.items())),
                     tuple(mutual),"READY",())


def validate_series(frames: tuple[InfoFrame,...], *, min_frames: int=2) -> tuple[str,...]:
    if len(frames)<min_frames:
        raise LocalityError("insufficient chronological observables")
    first=frames[0]
    clocks=[]
    raw_ids=set()
    for frame in frames:
        if frame.source_identity!=first.source_identity or frame.calibration_identity!=first.calibration_identity:
            raise LocalityError("incompatible information source/calibration")
        if frame.status!="READY":
            raise LocalityError("review-required frame cannot silently enter coupling fit")
        if set(dict(frame.entropy))!=set(dict(first.entropy)):
            raise LocalityError("node schema changed across frames")
        if set((a,b) for a,b,_ in frame.mi)!=set((a,b) for a,b,_ in first.mi):
            raise LocalityError("pair schema changed")
        if frame.raw_count!=len(frame.raw_evidence_ids):
            raise LocalityError("raw evidence count mismatch")
        if any(x in raw_ids for x in frame.raw_evidence_ids):
            raise LocalityError("duplicate source evidence across frames")
        raw_ids.update(frame.raw_evidence_ids)
        clocks.append(frame.clock)
    if clocks!=sorted(set(clocks)):
        raise LocalityError("non-monotone event clocks; no implicit ordering")
    return tuple(sorted(dict(first.entropy)))
