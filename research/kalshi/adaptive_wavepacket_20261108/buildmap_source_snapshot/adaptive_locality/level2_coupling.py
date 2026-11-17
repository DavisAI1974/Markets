"""Level 2: unsmoothed dipole-balance pair interactions, independently tested.

Each B_(i,j)(t) from a retained Level 1 BalanceWindow remains a DISTINCT,
directional channel. No six-node topology, B_net, mean-field, raw averaging,
silently discarded window or calculation suppression. A missing, rank-deficient,
outlier, or unstable window is a RESEARCH_HOLD with full original lineage.
The positive result is only a predictive ASSOCIATION, not causal coupling.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from itertools import permutations
import math
from typing import Sequence
from .core import LocalityError, _digest
from .coupling import BalanceWindow, _qr_fit, _predict_sse

LEVEL2_BASE=("const","Bk","Bk2")
LEVEL2_FULL=LEVEL2_BASE+("Bj","Bj2","BkBj")


@dataclass(frozen=True)
class Level2Link:
    target_balance: tuple[str,str]
    donor_balance: tuple[str,str]
    status: str
    reason: str
    base_holdout_sse: float | None
    full_holdout_sse: float | None
    past_shift_null_sse: float | None
    predictive_gain: float | None
    null_gain: float | None
    opposing_operator_signs: bool | None
    fitted_coefficients: tuple[tuple[str,float], ...]
    train_intervals: int
    test_intervals: int
    evidence_identity: str
    scientific_jobs_eliminated: int=0


def _research_link(target,donor,reason,evidence_identity,train=0,test=0):
    return Level2Link(target,donor,"RESEARCH_HOLD",reason,None,None,None,None,
                      None,None,(),train,test,evidence_identity)


def _fit_link(target,donor,clock,series,*, min_gain,null_margin,evidence_identity):
    count=len(clock)
    lag=max(3,count//5)
    split=int((count-1)*0.65)
    train_idx=range(lag,max(lag,split-1))
    test_idx=range(split,count-1)
    if len(train_idx)<2*len(LEVEL2_FULL) or len(test_idx)<len(LEVEL2_FULL):
        return _research_link(target,donor,"INSUFFICIENT_INDEPENDENT_CHRONOLOGICAL_SUPPORT",
                              evidence_identity,len(train_idx),len(test_idx))
    bk=series[target]
    bj=series[donor]
    def row(i,j):
        x,y=bk[i],bj[j]
        values=(1.,x,x*x,y,y*y,x*y)
        if not all(math.isfinite(z) for z in values):
            raise LocalityError("nonfinite unsmoothed balance operator")
        return values
    try:
        def target_rate(i):
            dt=clock[i+1]-clock[i]
            if dt<=0:
                raise LocalityError("nonmonotone balance clocks")
            value=(bk[i+1]-bk[i])/dt
            if not math.isfinite(value):
                raise LocalityError("nonfinite balance derivative")
            return value
        base_train=[row(i,i)[:len(LEVEL2_BASE)] for i in train_idx]
        full_train=[row(i,i) for i in train_idx]
        null_train=[row(i,i-lag) for i in train_idx]
        ytrain=[target_rate(i) for i in train_idx]
        base_fit=_qr_fit(base_train,ytrain,LEVEL2_BASE)
        full_fit=_qr_fit(full_train,ytrain,LEVEL2_FULL)
        null_fit=_qr_fit(null_train,ytrain,LEVEL2_FULL)
        ytest=[target_rate(i) for i in test_idx]
        base_error=_predict_sse(base_fit,[row(i,i)[:len(LEVEL2_BASE)] for i in test_idx],ytest)
        full_error=_predict_sse(full_fit,[row(i,i) for i in test_idx],ytest)
        null_error=_predict_sse(null_fit,[row(i,i-lag) for i in test_idx],ytest)
        if not all(math.isfinite(v) for v in (base_error,full_error,null_error)):
            raise LocalityError("nonfinite held-out residual")
        if base_error<=1e-14:
            return _research_link(target,donor,"SELF_BASELINE_ALREADY_EXPLAINS_HOLDOUT",
                                  evidence_identity,len(train_idx),len(test_idx))
        gain=(base_error-full_error)/base_error
        null_gain=(base_error-null_error)/base_error
        fit=dict(full_fit.coefficients)
        opposing=fit["Bk2"]*fit["BkBj"]<0
        status=("CANDIDATE_ASSOCIATION_REVIEW_ONLY"
                if gain>=min_gain and gain>=null_gain+null_margin
                else "NO_SUPPORTED_ASSOCIATION")
        return Level2Link(target,donor,status,
                          "Unsmoothed, direction-specific predictive comparison; not a causal or equivalent-calculation claim",
                          base_error,full_error,null_error,gain,null_gain,
                          opposing,full_fit.coefficients,len(train_idx),len(test_idx),
                          evidence_identity)
    except (LocalityError,OverflowError,ZeroDivisionError) as exc:
        return _research_link(target,donor,
                              "RANK_NUMERIC_OR_DERIVATIVE_REVIEW:"+str(exc),
                              evidence_identity,len(train_idx),len(test_idx))


def discover_level2_balance_links(windows: Sequence[BalanceWindow], *,
                                  source_identity:str, calibration_identity:str,
                                  min_gain:float=0.15, null_margin:float=0.08,
                                  max_channels:int=36, max_windows:int=12000) -> dict:
    """Return ALL original windows, ALL proposed directed links, ALL review holds.

    Source/calibration are mandatory external identities; the Level 1 balance
    channels must agree on exact source frames at each matching clock.
    Invalid channels are set aside from fitting, never from the returned data.
    """
    if not source_identity or not calibration_identity:
        raise LocalityError("missing Level 2 source/calibration identity")
    if not (0<min_gain<1 and 0<null_margin<1):
        raise LocalityError("invalid candidate thresholds")
    windows=tuple(windows)
    if not windows:
        raise LocalityError("no Level 1 balance windows supplied")
    if len(windows)>max_windows:
        raise LocalityError("bounded offline budget exceeded; partition only with explicit evidence manifest")
    if any(not isinstance(w,BalanceWindow) or w.scientific_jobs_eliminated!=0 for w in windows):
        raise LocalityError("invalid or destructive Level 1 windows")
    identity=_digest({"source":source_identity,"calibration":calibration_identity,
                      "windows":[asdict(w) for w in windows]})
    groups:dict[tuple[str,str],dict[int,BalanceWindow]]={}
    issues=[]
    for index,w in enumerate(windows):
        channel=(w.target,w.donor)
        if not all(channel) or channel[0]==channel[1] or not w.source_frames:
            issues.append({"index":index,"channel":channel,"clock":w.end_clock,
                           "reason":"INVALID_WINDOW_OR_EMPTY_PROVENANCE"})
        lane=groups.setdefault(channel,{})
        if w.end_clock in lane:
            issues.append({"index":index,"channel":channel,"clock":w.end_clock,
                           "reason":"DUPLICATE_WINDOW_CLOCK_NOT_DROPPED"})
        else:
            lane[w.end_clock]=w
        if w.status!="READY_RESEARCH_ONLY" or w.balance is None or not math.isfinite(w.balance):
            issues.append({"index":index,"channel":channel,"clock":w.end_clock,
                           "reason":"LEVEL1_FIT_RESEARCH_HOLD:"+w.status})
    channels=tuple(sorted(groups))
    if not 2<=len(channels)<=max_channels:
        raise LocalityError("bounded Level 2 needs 2..max_channels pair series")
    clocks=tuple(sorted({clock for lane in groups.values() for clock in lane}))
    for channel, lane in groups.items():
        if tuple(sorted(lane))!=clocks:
            issues.append({"index":None,"channel":channel,"clock":None,
                           "reason":"MISSING_WINDOWS_IN_CHANNEL"})
    for clock in clocks:
        windows_at=[lane[clock] for lane in groups.values() if clock in lane]
        if len(windows_at)!=len(groups) or any(w.source_frames!=windows_at[0].source_frames
                                               for w in windows_at):
            issues.append({"index":None,"channel":None,"clock":clock,
                           "reason":"CROSS_CHANNEL_SOURCE_WINDOW_MISMATCH"})
    invalid={tuple(i["channel"]) for i in issues if i["channel"] is not None}
    global_problem=any(i["channel"] is None for i in issues)
    if len(clocks)<35:
        global_problem=True
        issues.append({"index":None,"channel":None,"clock":None,
                       "reason":"INSUFFICIENT_LEVEL2_SUPPORT"})
    series={channel:tuple(groups[channel][clock].balance for clock in clocks)
            for channel in channels if not global_problem and channel not in invalid}
    links=[]
    for a,b in permutations(channels,2):
        if global_problem or a in invalid or b in invalid:
            link=_research_link(a,b,"INPUT_WINDOWS_REQUIRE_INDEPENDENT_INVESTIGATION",identity)
        else:
            link=_fit_link(a,b,clocks,series,min_gain=min_gain,
                           null_margin=null_margin,evidence_identity=identity)
            if link.status=="RESEARCH_HOLD":
                issues.append({"index":None,"channel":a,"donor_channel":b,
                               "clock":None,"reason":link.reason})
        links.append(link)
    return {
        "schema":1,"kind":"OFFLINE_LEVEL2_UNSMOOTHED_BALANCE_LINKS",
        "trust":"UNSIGNED_RESEARCH_ONLY_NOT_CAUSAL_OR_SCIENTIFIC_EQUIVALENCE",
        "source_identity":source_identity,"calibration_identity":calibration_identity,
        "evidence_identity":identity,"channels":channels,"clocks":clocks,
        "original_window_count":len(windows),"retained_original_windows":windows,
        "unresolved_research_items":tuple(issues),
        "unresolved_count":len(issues),
        "links":tuple(links),"tested_link_count":len(links),
        "candidate_count":sum(link.status=="CANDIDATE_ASSOCIATION_REVIEW_ONLY" for link in links),
        "held_link_count":sum(link.status=="RESEARCH_HOLD" for link in links),
        "scientific_jobs_eliminated":0,"raw_values_averaged":False,
        "input_windows_dropped":0,"rank_deficiencies_dropped":0,
        "limitations":(
            "All original Level 1 windows, including rank-deficient and outlying cases, retained for research.",
            "Overlapping windows are dependent: predictive nulls do not imply independent confirmation.",
            "Self-only and past-lag controls are diagnostic, not a causal identification theorem.",
            "No hardcoded network edges, domain grouping, neighbor means, or science job elimination.",
            "No continuum geometry or Neumann boundary conditions are implied.",
        ),
    }
