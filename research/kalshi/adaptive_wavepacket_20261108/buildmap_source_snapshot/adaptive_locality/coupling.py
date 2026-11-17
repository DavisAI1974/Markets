"""Agnostic, evidence-preserving five-step dipole/coupling research probe.

1. Accept independently calibrated, source-bound H, MI, Fisher-like proxy
   derived from immutable raw samples (see information.py).
2. Build a fixed explicit operator library: 1, Ha, Ha^2, FIa,
   Hb, Hb^2, Ha*Hb, MIab, FIb. Do not search for network topology up front.
3. Fit the directional derivative with rank-audited least squares on PAST
   training frames. No smoothing or averaging of raw observations.
4. Evaluate every directed pair independently on a FUTURE holdout.
5. Compare with self-only and time-shifted-donor null. Preserve each
   calculation and abstention; never infer causality or eliminate jobs.

The original Basic_equations Level 2 approach had hardcoded six-node
coupling, global pair averaging and potentially unstable coefficient ratios.
This is a *different experiment*, not a reproduction or proof of discovery.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import permutations, combinations
import math

from .core import LocalityError, _digest
from .information import InfoFrame, validate_series


BASE = ("const", "Ha", "Ha2", "FIa")
FULL = BASE + ("Hb", "Hb2", "HaHb", "MIab", "FIb")


@dataclass(frozen=True)
class Fit:
    coefficients: tuple[tuple[str,float], ...]
    train_residual: float
    rank: int
    rank_diagonal_ratio: float


@dataclass(frozen=True)
class CouplingResult:
    target: str
    donor: str
    status: str
    holdout_base_sse: float | None
    holdout_full_sse: float | None
    holdout_null_sse: float | None
    improvement: float | None
    shifted_null_improvement: float | None
    opposing_dipole_signs: bool | None
    dipole_balance: float | None
    fit: Fit | None
    training_intervals: int
    test_intervals: int
    source_frames: tuple[str,...]
    scientific_jobs_eliminated: int = 0


@dataclass(frozen=True)
class BalanceWindow:
    target: str
    donor: str
    start_clock: int
    end_clock: int
    status: str
    balance: float | None
    opposing_signs: bool | None
    source_frames: tuple[str,...]
    coefficients: tuple[tuple[str,float], ...]
    scientific_jobs_eliminated: int = 0


def _qr_fit(rows: list[tuple[float,...]], target: list[float],
            labels: tuple[str,...]) -> Fit:
    """Reorthogonalized QR; refuse rank deficiency, do not invent ratios."""
    if not rows or len(rows)!=len(target) or len(rows)<2*len(labels):
        raise LocalityError("insufficient independent training rows")
    n,p=len(rows),len(labels)
    if any(len(r)!=p or not all(math.isfinite(v) for v in r) for r in rows):
        raise LocalityError("invalid operator design")
    if not all(math.isfinite(v) for v in target):
        raise LocalityError("invalid derivative response")
    means=[0.] + [math.fsum(row[j] for row in rows)/n for j in range(1,p)]
    scales=[1.]
    for j in range(1,p):
        s=math.sqrt(math.fsum((row[j]-means[j])**2 for row in rows)/n)
        if not math.isfinite(s) or s<=1e-12:
            raise LocalityError("rank-deficient operator: constant or unidentifiable feature")
        scales.append(s)
    cols=[[1.]*n] + [[(row[j]-means[j])/scales[j] for row in rows]
                         for j in range(1,p)]
    qs=[]
    R=[[0.]*p for _ in range(p)]
    diagonal=[]
    for j,v0 in enumerate(cols):
        v=list(v0)
        # Twice-reorthogonalized modified Gram-Schmidt for small libraries.
        for _ in range(2):
            for k,q in enumerate(qs):
                r=math.fsum(q[i]*v[i] for i in range(n))
                R[k][j]+=r
                v=[v[i]-r*q[i] for i in range(n)]
        norm=math.hypot(*v)
        if not math.isfinite(norm) or norm<=1e-7*math.sqrt(n):
            raise LocalityError("operator library rank defect / numerical artifact")
        R[j][j]=norm
        diagonal.append(norm)
        qs.append([w/norm for w in v])
    rhs=[math.fsum(q[i]*target[i] for i in range(n)) for q in qs]
    normalized=[0.]*p
    for j in reversed(range(p)):
        normalized[j]=(rhs[j]-math.fsum(R[j][k]*normalized[k]
                                        for k in range(j+1,p)))/R[j][j]
    coeff=[0.]*p
    for j in range(1,p):
        coeff[j]=normalized[j]/scales[j]
    coeff[0]=normalized[0]-math.fsum(coeff[j]*means[j] for j in range(1,p))
    if any(not math.isfinite(c) for c in coeff):
        raise LocalityError("operator coefficients nonfinite")
    residual=math.fsum((target[i]-math.fsum(rows[i][j]*coeff[j]
                                   for j in range(p)))**2 for i in range(n))
    if not math.isfinite(residual):
        raise LocalityError("unbounded residual")
    return Fit(tuple(zip(labels,coeff)),residual,p,max(diagonal)/min(diagonal))


def _operator_row(frames: tuple[InfoFrame,...], at: int, a: str,
                  b: str, donor_offset: int=0) -> tuple[float,...]:
    now=frames[at]
    donor_index=at+donor_offset
    if donor_offset>0 or donor_index<0 or donor_index>at:
        raise LocalityError("future donor observation or unavailable history")
    donor_frame=frames[donor_index]
    ent_a=dict(now.entropy)
    ent_b=dict(donor_frame.entropy)
    fi_a=dict(now.fisher_proxy)
    fi_b=dict(donor_frame.fisher_proxy)
    pair=tuple(sorted((a,b)))
    mutual={(x,y):value for x,y,value in donor_frame.mi}
    Ha,Hb=ent_a[a],ent_b[b]
    return (1.,Ha,Ha*Ha,fi_a[a],Hb,Hb*Hb,Ha*Hb,mutual[pair],fi_b[b])


def _series_rows(frames: tuple[InfoFrame,...], a: str, b: str,
                 donor_offset: int=0, *, start_index:int=0):
    if donor_offset>0:
        raise LocalityError("future donor observation not permitted")
    X=[]
    y=[]
    for i in range(max(start_index,-donor_offset),len(frames)-1):
        dt=frames[i+1].clock-frames[i].clock
        Ha=dict(frames[i].entropy)[a]
        Ha_next=dict(frames[i+1].entropy)[a]
        X.append(_operator_row(frames,i,a,b,donor_offset))
        y.append((Ha_next-Ha)/dt)
    return X,y


def _predict_sse(fit: Fit, rows, targets) -> float:
    c=[v for _,v in fit.coefficients]
    return math.fsum((value-math.fsum(x*w for x,w in zip(row,c)))**2
                     for row,value in zip(rows,targets))


def _ratio(fit: Fit):
    co=dict(fit.coefficients)
    scale=max(1.,*(abs(v) for v in co.values()))
    den=co["HaHb"]
    if abs(den)<=1e-8*scale:
        return None,None
    return abs(co["Ha2"])/abs(den),co["Ha2"]*den<0


def _test_direction(frames: tuple[InfoFrame,...],target: str,donor: str,
                    min_gain:float, null_margin:float) -> CouplingResult:
    N=len(frames)-1
    lag=max(3,len(frames)//5)
    split=int(N*0.65)
    # A past-lag null never cycles into future data. All three
    # comparisons use exactly the same eligible chronological intervals.
    training=list(range(lag,split-1))
    testing=list(range(split,N))
    evidence=tuple(f.raw_identity for f in frames)
    neutral=lambda status:CouplingResult(target,donor,status,None,None,None,None,None,
                                         None,None,None,len(training),len(testing),evidence)
    if len(training)<2*len(FULL) or len(testing)<max(8,len(FULL)):
        return neutral("ABSTAIN_INSUFFICIENT_CHRONOLOGICAL_SUPPORT")
    original,y=_series_rows(frames,target,donor,start_index=lag)
    shifted,_=_series_rows(frames,target,donor,-lag,start_index=lag)
    train_rows=[i-lag for i in training]
    test_rows=[i-lag for i in testing]
    try:
        base=_qr_fit([original[i][:len(BASE)] for i in train_rows],
                     [y[i] for i in train_rows],BASE)
        full=_qr_fit([original[i] for i in train_rows],[y[i] for i in train_rows],FULL)
        null=_qr_fit([shifted[i] for i in train_rows],[y[i] for i in train_rows],FULL)
        actual=[y[i] for i in test_rows]
        base_error=_predict_sse(base,[original[i][:len(BASE)] for i in test_rows],actual)
        full_error=_predict_sse(full,[original[i] for i in test_rows],actual)
        null_error=_predict_sse(null,[shifted[i] for i in test_rows],actual)
        if not all(math.isfinite(x) for x in (base_error,full_error,null_error)):
            raise LocalityError("nonfinite predictive error")
        if base_error<=1e-14:
            return neutral("ABSTAIN_SELF_MODEL_ALREADY_EXPLAINS_HOLDOUT")
        improvement=(base_error-full_error)/base_error
        null_gain=(base_error-null_error)/base_error
        ratio,opposing=_ratio(full)
        # These are predictive associations. Shared drivers remain an
        # unresolved confound; this code never declares causal influence.
        candidate=improvement>=min_gain and improvement>=null_gain+null_margin
        status="CANDIDATE_ASSOCIATION_REVIEW_ONLY" if candidate else "NO_SUPPORTED_ASSOCIATION"
        if ratio is None:
            status="ABSTAIN_UNIDENTIFIABLE_DIPOLE_RATIO"
        return CouplingResult(target,donor,status,base_error,full_error,null_error,
                              improvement,null_gain,opposing,ratio,full,
                              len(training),len(testing),evidence)
    except (LocalityError,ZeroDivisionError,OverflowError):
        return neutral("ABSTAIN_RANK_OR_NUMERIC_ARTIFACT")


def discover_coupling(frames: tuple[InfoFrame,...], *, min_gain:float=0.15,
                      null_margin:float=0.08, max_nodes:int=12) -> dict:
    if not (0<min_gain<1 and 0<null_margin<1) or type(max_nodes) is not int or max_nodes<2:
        raise LocalityError("invalid independent coupling selection thresholds")
    frames=tuple(frames)
    names=validate_series(frames,min_frames=50)
    if len(names)>max_nodes:
        raise LocalityError("node count exceeds bounded pairwise CPU budget; batch explicitly")
    results=tuple(_test_direction(frames,a,b,min_gain,null_margin)
                  for a,b in permutations(names,2))
    return {"schema":1,"method":"AGNOSTIC_FIVE_STEP_PROBE",
            "trust":"UNSIGNED_ASSOCIATION_RESEARCH_ONLY_NOT_SCIENTIFIC_EQUIVALENCE",
            "source_identity":frames[0].source_identity,
            "calibration_identity":frames[0].calibration_identity,
            "nodes":names,"frames":len(frames),
            "raw_evidence_count":sum(f.raw_count for f in frames),
            "raw_source_frame_identities":tuple(f.raw_identity for f in frames),
            "evidence_identity":_digest({"frames":[f.identity() for f in frames],
                                         "method":"AGNOSTIC_FIVE_STEP_PROBE"}),
            "operator_library":FULL,
            "result_count":len(results),"results":results,
            "scientific_jobs_eliminated":0,
            "no_averaging_of_raw_observations":True,
            "coupling_topology":"UNKNOWN_DISCOVERED_AS_CANDIDATE_ASSOCIATIONS",
            "limitations":(
                "MI/FI histogram estimators and polynomial operators can create rank artifacts.",
                "Holdout prediction and shifted null do NOT prove causality.",
                "Shared drivers, feedback, estimator selection and multiple testing unresolved.",
                "No six-node chain, adjacency, or averaged network state is assumed.",
                "All source evidence and outliers must be retained for separate research.",
            )}


def dipole_window_probe(frames: tuple[InfoFrame,...], *, window:int=40,
                        stride:int=4, max_nodes:int=12) -> tuple[BalanceWindow,...]:
    frames=tuple(frames)
    names=validate_series(frames,min_frames=window+1)
    if type(window) is not int or type(stride) is not int or window<2*len(FULL)+1 or stride<1:
        raise LocalityError("invalid balance window policy")
    if len(names)>max_nodes:
        raise LocalityError("unbounded node count")
    output=[]
    for a,b in permutations(names,2):
        X,y=_series_rows(frames,a,b)
        for stop in range(window,len(X)+1,stride):
            start=stop-window
            ids=tuple(f.raw_identity for f in frames[start:stop+1])
            try:
                fit=_qr_fit(X[start:stop],y[start:stop],FULL)
                ratio,opposing=_ratio(fit)
                status="READY_RESEARCH_ONLY" if ratio is not None else "ABSTAIN_RATIO"
                balance=BalanceWindow(a,b,frames[start].clock,frames[stop].clock,status,
                                      ratio,opposing,ids,fit.coefficients)
            except (LocalityError,OverflowError):
                balance=BalanceWindow(a,b,frames[start].clock,frames[stop].clock,
                                      "ABSTAIN_RANK_OR_NUMERIC_ARTIFACT",None,None,ids,())
            output.append(balance)
    return tuple(output)


def cross_domain_motif(reports: dict[str,dict]) -> dict:
    required={"physics","biology","chemistry","geology"}
    if set(reports)!=required:
        return {"status":"INCOMPLETE_DOMAIN_SET","observed":tuple(sorted(reports)),
                "required":tuple(sorted(required)),"promotable":False}
    # Reused data with four names is not four independently replicated domains.
    sources=[r.get("source_identity") for r in reports.values()]
    identity_sets=[set(r.get("raw_source_frame_identities",())) for r in reports.values()]
    if (any(not x for x in sources) or len(set(sources))!=4 or
        any(not x for x in identity_sets) or
        any(identity_sets[i] & identity_sets[j]
            for i in range(4) for j in range(i+1,4))):
        return {"status":"NONINDEPENDENT_DOMAIN_EVIDENCE","promotable":False,
                "caveat":"Domain labels cannot establish independent source evidence."}
    detail={}
    for science,report in reports.items():
        if report.get("scientific_jobs_eliminated")!=0:
            raise LocalityError("scientific job elimination is prohibited")
        matches=[(r.target,r.donor) for r in report["results"]
                 if r.status=="CANDIDATE_ASSOCIATION_REVIEW_ONLY"
                 and r.opposing_dipole_signs is True]
        detail[science]=tuple(matches)
    return {"status":"EXPLORATORY_MOTIF_IN_FOUR_DOMAINS" if all(detail.values())
            else "NO_FOUR_DOMAIN_MOTIF",
            "candidate_directed_pairs":detail,"promotable":False,
            "caveat":"Separate fits; no raw-data pooling or proof of universality. Correct for multiple testing and validate real independent domains."}
