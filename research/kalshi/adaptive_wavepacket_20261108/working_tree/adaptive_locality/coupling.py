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
from typing import Sequence

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
    # M-1 conditioning diagnostics (reported, never used to drop anything):
    # singular values of the standardized design divided by sqrt(n), descending;
    # their ratio; per-column variance inflation factors (None for const);
    # coefficient standard errors in ORIGINAL units; full coefficient covariance.
    singular_values: tuple[float, ...] = ()
    condition_number: float | None = None
    variance_inflation: tuple[tuple[str, float | None], ...] = ()
    coefficient_standard_errors: tuple[tuple[str, float], ...] = ()
    coefficient_covariance: tuple[tuple[float, ...], ...] = ()


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
    # PG-2: the cause of an abstention (the exact numeric/rank message) is
    # retained here; a status alone must never replace it.
    reason: str = ""
    # M-1: delta-method standard error of B=|c_Ha2|/|c_HaHb| (with covariance).
    balance_standard_error: float | None = None
    # M-4: the single matched lag is one point of a profile; donor memory is
    # reported so the strength of the past-lag null can be read.
    donor_lag1_autocorrelation: float | None = None
    null_gain_by_lag: tuple[dict, ...] = ()


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
    # PG-2: abstention cause retained per window.
    reason: str = ""
    # M-1: delta-method standard error of the window balance.
    balance_standard_error: float | None = None


def _symmetric_eigenvalues(matrix: list[list[float]], sweeps: int=60) -> list[float]:
    """Jacobi eigenvalues of a small symmetric matrix (p <= ~12), pure Python."""
    a=[list(row) for row in matrix]
    p=len(a)
    for _ in range(sweeps):
        off=math.fsum(a[i][j]*a[i][j] for i in range(p) for j in range(p) if i!=j)
        if off<=1e-30:
            break
        for i in range(p):
            for j in range(i+1,p):
                if abs(a[i][j])<=1e-300:
                    continue
                theta=(a[j][j]-a[i][i])/(2*a[i][j])
                t=(1. if theta>=0 else -1.)/(abs(theta)+math.sqrt(theta*theta+1.))
                c=1./math.sqrt(t*t+1.)
                sn=t*c
                for k in range(p):
                    aik,ajk=a[i][k],a[j][k]
                    a[i][k]=c*aik-sn*ajk
                    a[j][k]=sn*aik+c*ajk
                for k in range(p):
                    aki,akj=a[k][i],a[k][j]
                    a[k][i]=c*aki-sn*akj
                    a[k][j]=sn*aki+c*akj
    return sorted((a[i][i] for i in range(p)),reverse=True)


def _upper_inverse(R: list[list[float]]) -> list[list[float]]:
    p=len(R)
    inv=[[0.]*p for _ in range(p)]
    for col in range(p):
        for row in reversed(range(p)):
            value=1. if row==col else 0.
            value-=math.fsum(R[row][k]*inv[k][col] for k in range(row+1,p))
            inv[row][col]=value/R[row][row]
    return inv


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
    # M-1: full conditioning diagnostics of the standardized design X_std = Q R.
    gram=[[math.fsum(R[k][i]*R[k][j] for k in range(p)) for j in range(p)]
          for i in range(p)]
    eigen=_symmetric_eigenvalues(gram)
    singular=tuple(math.sqrt(max(e,0.))/math.sqrt(n) for e in eigen)
    condition=(singular[0]/singular[-1]) if singular[-1]>0 else None
    r_inv=_upper_inverse(R)
    # (X_std^T X_std)^-1 = R^-1 R^-T
    inv_std=[[math.fsum(r_inv[i][k]*r_inv[j][k] for k in range(p)) for j in range(p)]
             for i in range(p)]
    vif=tuple((labels[j],None if j==0 else n*inv_std[j][j]) for j in range(p))
    # Map to original coefficient units: coeff = T @ normalized.
    T=[[0.]*p for _ in range(p)]
    T[0][0]=1.
    for j in range(1,p):
        T[j][j]=1./scales[j]
        T[0][j]=-means[j]/scales[j]
    sigma2=residual/max(1,n-p)
    cov=[[sigma2*math.fsum(T[i][a]*inv_std[a][b]*T[j][b]
                           for a in range(p) for b in range(p))
          for j in range(p)] for i in range(p)]
    errors=tuple((labels[j],math.sqrt(max(cov[j][j],0.))) for j in range(p))
    if any(not math.isfinite(v) for _,v in errors):
        raise LocalityError("nonfinite coefficient standard error")
    return Fit(tuple(zip(labels,coeff)),residual,p,max(diagonal)/min(diagonal),
               singular,condition,vif,errors,tuple(tuple(row) for row in cov))


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
    """Return (B, opposing_signs, standard_error_of_B) or (None, None, None).

    B=|c_Ha2|/|c_HaHb|. The standard error is the delta method with the full
    coefficient covariance (M-1); it is reported so that a window-to-window
    swing in B can be read against its own uncertainty instead of as dynamics.
    """
    co=dict(fit.coefficients)
    scale=max(1.,*(abs(v) for v in co.values()))
    den=co["HaHb"]
    if abs(den)<=1e-8*scale:
        return None,None,None
    labels=[k for k,_ in fit.coefficients]
    i,j=labels.index("Ha2"),labels.index("HaHb")
    num=co["Ha2"]
    error=None
    if fit.coefficient_covariance:
        cov=fit.coefficient_covariance
        # d(|a|/|b|)/da = sign(a)/|b|, d/db = -|a| sign(b)/b^2
        ga=(1. if num>=0 else -1.)/abs(den)
        gb=-abs(num)*(1. if den>=0 else -1.)/(den*den)
        variance=ga*ga*cov[i][i]+gb*gb*cov[j][j]+2*ga*gb*cov[i][j]
        error=math.sqrt(max(variance,0.)) if math.isfinite(variance) else None
    return abs(num)/abs(den),num*den<0,error


def chronological_partition(frame_count: int) -> tuple[int, list[int], list[int]]:
    """Return (lag, training_intervals, testing_intervals) for a frame series.

    Interval i uses frames i and i+1 (the derivative target). Training stops at
    interval split-2 and testing starts at interval split, so the frame split-1
    is consumed only by the last training TARGET and never by a test FEATURE,
    and frame split is consumed only by test rows. The one skipped interval is
    deliberate (review finding M-5): training-target frames and test-feature
    frames are disjoint. The lag is the single matched past-donor lag used by
    the null; see M-4 for the lag sweep that reports a whole profile.
    """
    if type(frame_count) is not int or frame_count<2:
        raise LocalityError("chronological partition needs at least two frames")
    N=frame_count-1
    lag=max(3,frame_count//5)
    split=int(N*0.65)
    training=list(range(lag,split-1))
    testing=list(range(split,N))
    return lag,training,testing


def lag1_autocorrelation(values: Sequence[float]) -> float | None:
    """Pearson correlation of x_t with x_{t+1}; None when undefined."""
    x=list(values)
    if len(x)<3:
        return None
    a,b=x[:-1],x[1:]
    ma=math.fsum(a)/len(a); mb=math.fsum(b)/len(b)
    sa=math.sqrt(math.fsum((v-ma)**2 for v in a)); sb=math.sqrt(math.fsum((v-mb)**2 for v in b))
    if sa<=0 or sb<=0:
        return None
    r=math.fsum((u-ma)*(v-mb) for u,v in zip(a,b))/(sa*sb)
    return max(-1.,min(1.,r)) if math.isfinite(r) else None


def lag_sweep_candidates(frame_count: int, primary: int, *, limit: int=12) -> tuple[int,...]:
    """Up to `limit` lags from 3 to frame_count//3, always including `primary`."""
    lo,hi=3,max(3,frame_count//3)
    if hi<=lo:
        return (primary,)
    steps=max(1,limit-2)
    raw={lo+round(k*(hi-lo)/steps) for k in range(steps+1)}
    raw.add(primary)
    return tuple(sorted(l for l in raw if lo<=l<=hi or l==primary))[:limit]


def _lag_profile(frames, target, donor, original, y, lag, training, testing):
    """M-4: per-lag matched comparison; every lag is a record, none is selected."""
    profile=[]
    for L in lag_sweep_candidates(len(frames),lag):
        base0=max(lag,L)
        train=[i for i in training if i>=base0]
        entry={"lag":L,"training_intervals":len(train),"testing_intervals":len(testing)}
        if len(train)<2*len(FULL) or any(i<base0 for i in testing):
            profile.append({**entry,"improvement":None,"null_gain":None,
                            "reason":"insufficient matched intervals for this lag"})
            continue
        try:
            shifted,_=_series_rows(frames,target,donor,-L,start_index=lag)
            tr_o=[original[i-lag] for i in train]; tr_s=[shifted[i-base0] for i in train]
            ytr=[y[i-lag] for i in train]
            te_o=[original[i-lag] for i in testing]; te_s=[shifted[i-base0] for i in testing]
            yte=[y[i-lag] for i in testing]
            base=_predict_sse(_qr_fit([r[:len(BASE)] for r in tr_o],ytr,BASE),
                              [r[:len(BASE)] for r in te_o],yte)
            full=_predict_sse(_qr_fit(tr_o,ytr,FULL),te_o,yte)
            null=_predict_sse(_qr_fit(tr_s,ytr,FULL),te_s,yte)
            if base<=1e-14:
                profile.append({**entry,"improvement":None,"null_gain":None,
                                "reason":"self-only model already explains holdout"})
            else:
                profile.append({**entry,"improvement":(base-full)/base,
                                "null_gain":(base-null)/base,"reason":""})
        except (LocalityError,ZeroDivisionError,OverflowError) as exc:
            profile.append({**entry,"improvement":None,"null_gain":None,
                            "reason":f"{type(exc).__name__}: {exc}"})
    return tuple(profile)


def _test_direction(frames: tuple[InfoFrame,...],target: str,donor: str,
                    min_gain:float, null_margin:float) -> CouplingResult:
    N=len(frames)-1
    # A past-lag null never cycles into future data. All three
    # comparisons use exactly the same eligible chronological intervals.
    lag,training,testing=chronological_partition(len(frames))
    split=int(N*0.65)
    evidence=tuple(f.raw_identity for f in frames)
    neutral=lambda status,reason="":CouplingResult(
        target,donor,status,None,None,None,None,None,
        None,None,None,len(training),len(testing),evidence,0,reason)
    if len(training)<2*len(FULL) or len(testing)<max(8,len(FULL)):
        return neutral("ABSTAIN_INSUFFICIENT_CHRONOLOGICAL_SUPPORT",
                       f"training_intervals={len(training)} testing_intervals={len(testing)} "
                       f"required>={2*len(FULL)} and >={max(8,len(FULL))}")
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
            return neutral("ABSTAIN_SELF_MODEL_ALREADY_EXPLAINS_HOLDOUT",
                           f"self-only holdout sse={base_error!r} <= 1e-14")
        improvement=(base_error-full_error)/base_error
        null_gain=(base_error-null_error)/base_error
        ratio,opposing,ratio_error=_ratio(full)
        # These are predictive associations. Shared drivers remain an
        # unresolved confound; this code never declares causal influence.
        candidate=improvement>=min_gain and improvement>=null_gain+null_margin
        status="CANDIDATE_ASSOCIATION_REVIEW_ONLY" if candidate else "NO_SUPPORTED_ASSOCIATION"
        reason="predictive association only; not causal and not an equivalence"
        if ratio is None:
            status="ABSTAIN_UNIDENTIFIABLE_DIPOLE_RATIO"
            reason=("|c_HaHb| below 1e-8 x coefficient scale; ratio not identified "
                    "(no epsilon is injected)")
        profile=_lag_profile(frames,target,donor,original,y,lag,training,testing)
        autocorr=lag1_autocorrelation([dict(f.entropy)[donor] for f in frames])
        return CouplingResult(target,donor,status,base_error,full_error,null_error,
                              improvement,null_gain,opposing,ratio,full,
                              len(training),len(testing),evidence,0,reason,ratio_error,
                              autocorr,profile)
    except (LocalityError,ZeroDivisionError,OverflowError) as exc:
        # PG-2: keep the exact cause with the abstention.
        return neutral("ABSTAIN_RANK_OR_NUMERIC_ARTIFACT",
                       f"{type(exc).__name__}: {exc}")


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
                ratio,opposing,ratio_error=_ratio(fit)
                status="READY_RESEARCH_ONLY" if ratio is not None else "ABSTAIN_RATIO"
                reason=("" if ratio is not None else
                        "|c_HaHb| below 1e-8 x coefficient scale; ratio not identified")
                balance=BalanceWindow(a,b,frames[start].clock,frames[stop].clock,status,
                                      ratio,opposing,ids,fit.coefficients,0,reason,
                                      ratio_error)
            except (LocalityError,OverflowError,ZeroDivisionError) as exc:
                # PG-2: the window is retained WITH its cause.
                balance=BalanceWindow(a,b,frames[start].clock,frames[stop].clock,
                                      "ABSTAIN_RANK_OR_NUMERIC_ARTIFACT",None,None,ids,(),
                                      0,f"{type(exc).__name__}: {exc}")
            output.append(balance)
    return tuple(output)


FOUR_SCIENCE_PRECEDENT=("physics","biology","chemistry","geology")


def cross_domain_motif(reports: dict[str,dict], *,
                       required: tuple[str,...] | None=None) -> dict:
    """Compare independently fitted reports from N named sources.

    The historical Basic_equations precedent used exactly physics, biology,
    chemistry and geology; that remains the default (M-6). Any explicit set of
    at least two distinct names may be supplied instead. Names never establish
    independence: shared source identities or shared raw frame identities are
    refused whatever the labels say.
    """
    names=tuple(FOUR_SCIENCE_PRECEDENT if required is None else required)
    if len(names)<2 or len(set(names))!=len(names) or any(not n for n in names):
        raise LocalityError("at least two distinct named sources required")
    required_set=set(names)
    if set(reports)!=required_set:
        return {"status":"INCOMPLETE_DOMAIN_SET","observed":tuple(sorted(reports)),
                "required":tuple(sorted(required_set)),"promotable":False}
    count=len(names)
    # Reused data with N names is not N independently replicated domains.
    sources=[r.get("source_identity") for r in reports.values()]
    identity_sets=[set(r.get("raw_source_frame_identities",())) for r in reports.values()]
    if (any(not x for x in sources) or len(set(sources))!=count or
        any(not x for x in identity_sets) or
        any(identity_sets[i] & identity_sets[j]
            for i in range(count) for j in range(i+1,count))):
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
    label="FOUR" if required is None else str(count)
    return {"status":f"EXPLORATORY_MOTIF_IN_{label}_DOMAINS" if all(detail.values())
            else f"NO_{label}_DOMAIN_MOTIF",
            "required":tuple(sorted(required_set)),
            "candidate_directed_pairs":detail,"promotable":False,
            "caveat":"Separate fits; no raw-data pooling or proof of universality. Correct for multiple testing and validate real independent domains."}
