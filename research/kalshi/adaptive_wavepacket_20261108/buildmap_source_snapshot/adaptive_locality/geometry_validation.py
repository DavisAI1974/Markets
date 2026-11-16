"""Chronological, rank-audited controls for *predictive* geometric terms.

Unlike the static identity Ha² vs HaHb, predict a FUTURE change in Ha.
Compare a self-history baseline with added same-clock Ha*Hb and its square,
and a past-only donor-lag null on exactly matching chronological intervals.
Repeated splits overlap: agreement is sensitivity evidence, NOT independent
replication or causal identification. Never skip or suppress original science.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from .core import LocalityError, _digest
from .information import InfoFrame, validate_series
from .coupling import _qr_fit, _predict_sse

SELF=("const","Ha","Ha2","FIa")
INTERACTION=SELF+("HaHb",)
GEOMETRY=INTERACTION+("HaHb2",)


@dataclass(frozen=True)
class GeometryPredictiveSplit:
    train_cutoff_clock: int
    status: str
    reason: str
    training_intervals: int
    testing_intervals: int
    self_holdout_sse: float | None
    geometry_holdout_sse: float | None
    linear_interaction_holdout_sse: float | None
    quadratic_vs_linear_gain: float | None
    quadratic_additional_support: bool | None
    past_donor_holdout_sse: float | None
    geometry_gain: float | None
    past_donor_gain: float | None
    early_holdout_gain: float | None
    late_holdout_gain: float | None
    coefficient_condition_indicator: float | None
    full_coefficients: tuple[tuple[str,float], ...]
    original_training_frame_identities: tuple[str, ...]
    original_testing_frame_identities: tuple[str, ...]


def _directional_terms(frames: Sequence[InfoFrame], i: int,
                       target: str, donor: str, lag: int=0):
    if lag<0 or i-lag<0:
        raise LocalityError("unavailable or future donor history")
    now=frames[i]
    prev=frames[i-lag]
    ha=dict(now.entropy)[target]
    hb=dict(prev.entropy)[donor]
    fi=dict(now.fisher_proxy)[target]
    x=ha*hb
    values=(1.,ha,ha*ha,fi,x,x*x)
    if any(not math.isfinite(v) for v in values):
        raise LocalityError("nonfinite geometric operator; research hold required")
    return values


def _rate(frames: Sequence[InfoFrame],i:int,target:str):
    dt=frames[i+1].clock-frames[i].clock
    if dt<=0:
        raise LocalityError("nonpositive causal-clock interval")
    a=dict(frames[i].entropy)[target]
    b=dict(frames[i+1].entropy)[target]
    result=(b-a)/dt
    if not math.isfinite(result):
        raise LocalityError("nonfinite target derivative")
    return result


def geometric_predictive_controls(frames: Sequence[InfoFrame],target:str,donor:str,
                                  *, split_fractions=(0.55,0.65,0.75),
                                  past_lag:int | None=None,
                                  min_gain:float=0.10,null_margin:float=0.05,
                                  max_frames:int=12000) -> dict:
    frames=tuple(frames)
    names=validate_series(frames,min_frames=64)
    if (target==donor or target not in names or donor not in names or
        type(max_frames) is not int or len(frames)>max_frames or
        not 0<min_gain<1 or not 0<null_margin<1):
        raise LocalityError("invalid directional predictive geometry budget or channel")
    splits=tuple(split_fractions)
    if (not splits or len(splits)>6 or
        any(type(x) is not float or not 0.45<=x<=0.80 for x in splits) or
        tuple(sorted(set(splits)))!=splits):
        raise LocalityError("predeclared distinct chronological split fractions required")
    lag=max(3,len(frames)//6) if past_lag is None else past_lag
    if type(lag) is not int or lag<1 or lag>=len(frames)//3:
        raise LocalityError("invalid positive strictly historical donor lag")
    identities=tuple(f.raw_identity for f in frames)
    results=[]
    for frac in splits:
        cutoff=int((len(frames)-1)*frac)
        train_idx=tuple(range(lag,cutoff-1))
        test_idx=tuple(range(cutoff,len(frames)-1))
        used_training=tuple(identities[i] for i in range(lag,cutoff))
        used_testing=tuple(identities[i] for i in range(cutoff,len(frames)))
        kwargs=dict(train_cutoff_clock=frames[cutoff].clock,
                    training_intervals=len(train_idx),testing_intervals=len(test_idx),
                    original_training_frame_identities=used_training,
                    original_testing_frame_identities=used_testing)
        def hold(reason):
            return GeometryPredictiveSplit(status="RESEARCH_HOLD",reason=reason,
                self_holdout_sse=None,geometry_holdout_sse=None,
                linear_interaction_holdout_sse=None,
                quadratic_vs_linear_gain=None,quadratic_additional_support=None,
                past_donor_holdout_sse=None,geometry_gain=None,past_donor_gain=None,
                early_holdout_gain=None,late_holdout_gain=None,
                coefficient_condition_indicator=None,full_coefficients=(),**kwargs)
        if len(train_idx)<2*len(GEOMETRY) or len(test_idx)<16:
            results.append(hold("INSUFFICIENT_MATCHED_CHRONOLOGICAL_SUPPORT"))
            continue
        try:
            self_train=[_directional_terms(frames,i,target,donor)[:len(SELF)]
                        for i in train_idx]
            full_train=[_directional_terms(frames,i,target,donor) for i in train_idx]
            lag_train=[_directional_terms(frames,i,target,donor,lag) for i in train_idx]
            ytrain=[_rate(frames,i,target) for i in train_idx]
            self_fit=_qr_fit(self_train,ytrain,SELF)
            interaction_fit=_qr_fit([row[:len(INTERACTION)] for row in full_train],
                                    ytrain,INTERACTION)
            full_fit=_qr_fit(full_train,ytrain,GEOMETRY)
            lag_fit=_qr_fit(lag_train,ytrain,GEOMETRY)
            self_test=[_directional_terms(frames,i,target,donor)[:len(SELF)]
                       for i in test_idx]
            full_test=[_directional_terms(frames,i,target,donor) for i in test_idx]
            lag_test=[_directional_terms(frames,i,target,donor,lag) for i in test_idx]
            ytest=[_rate(frames,i,target) for i in test_idx]
            base=_predict_sse(self_fit,self_test,ytest)
            interaction=_predict_sse(interaction_fit,
                                     [row[:len(INTERACTION)] for row in full_test],
                                     ytest)
            full=_predict_sse(full_fit,full_test,ytest)
            past=_predict_sse(lag_fit,lag_test,ytest)
            if not all(math.isfinite(v) for v in (base,interaction,full,past)):
                raise LocalityError("nonfinite heldout predictive residual")
            if base<=1e-14:
                results.append(hold("SELF_MODEL_ALREADY_EXPLAINS_HOLDOUT"))
                continue
            gain=(base-full)/base
            past_gain=(base-past)/base
            # A simple Ha*Hb term is the appropriate nested comparator.
            # A static quadratic identity does not itself improve prediction.
            quadratic_gain=((interaction-full)/interaction
                            if interaction>1e-14 else None)
            halfway=len(test_idx)//2
            if halfway<8 or len(test_idx)-halfway<8:
                results.append(hold("INSUFFICIENT_REGIME_RESOLUTION"))
                continue
            def segment(start,stop):
                b=_predict_sse(self_fit,self_test[start:stop],ytest[start:stop])
                f=_predict_sse(full_fit,full_test[start:stop],ytest[start:stop])
                return (b-f)/b if b>1e-14 else None
            early=segment(0,halfway)
            late=segment(halfway,len(test_idx))
            stable=(early is not None and late is not None and
                    early>0 and late>0)
            def incremental_segment(start,stop):
                i_error=_predict_sse(interaction_fit,
                    [row[:len(INTERACTION)] for row in full_test[start:stop]],
                    ytest[start:stop])
                f_error=_predict_sse(full_fit,full_test[start:stop],ytest[start:stop])
                return (i_error-f_error)/i_error if i_error>1e-14 else None
            early_extra=incremental_segment(0,halfway)
            late_extra=incremental_segment(halfway,len(test_idx))
            extra=(quadratic_gain is not None and quadratic_gain>=min_gain
                   and early_extra is not None and early_extra>0
                   and late_extra is not None and late_extra>0)
            promising=(gain>=min_gain and gain>=past_gain+null_margin and stable)
            # The normalized-QR diagonal ratio is only a warning proxy, not
            # the exact 2-norm design condition number. A numerically suspect
            # fit remains fully saved for research, including its coefficients.
            worst_condition_indicator=max(self_fit.rank_diagonal_ratio,
                                          interaction_fit.rank_diagonal_ratio,
                                          full_fit.rank_diagonal_ratio,
                                          lag_fit.rank_diagonal_ratio)
            near_singular=worst_condition_indicator>1e6
            results.append(GeometryPredictiveSplit(
                status=("RESEARCH_HOLD" if near_singular else
                        "CANDIDATE_PREDICTIVE_ASSOCIATION_REVIEW_ONLY" if promising
                        else "NO_ROBUST_ADDITIONAL_PREDICTIVE_GEOMETRY"),
                reason=("NEAR_SINGULAR_DESIGN_RETAIN_ALL_PREDICTIONS_FOR_RESEARCH"
                        if near_singular else
                        "Matched historical-null and frozen holdout comparisons; "
                        "overlapping splits not independent evidence of causality"),
                self_holdout_sse=base,geometry_holdout_sse=full,
                linear_interaction_holdout_sse=interaction,
                quadratic_vs_linear_gain=quadratic_gain,
                quadratic_additional_support=extra,
                past_donor_holdout_sse=past,geometry_gain=gain,
                past_donor_gain=past_gain,early_holdout_gain=early,
                late_holdout_gain=late,
                coefficient_condition_indicator=worst_condition_indicator,
                full_coefficients=full_fit.coefficients,**kwargs))
        except (LocalityError,ArithmeticError,OverflowError) as exc:
            results.append(hold("RANK_NUMERICAL_OR_CONTROL_RESEARCH:"+str(exc)))
    all_promising=all(x.status=="CANDIDATE_PREDICTIVE_ASSOCIATION_REVIEW_ONLY"
                      for x in results)
    held=sum(x.status=="RESEARCH_HOLD" for x in results)
    status=("RESEARCH_HOLD" if held else
            "CONSISTENT_MULTISPLIT_ASSOCIATION_REVIEW_ONLY" if all_promising else
            "NO_STABLE_ADDITIONAL_GEOMETRIC_PREDICTION")
    return {"schema":1,"kind":"OFFLINE_GEOMETRY_PREDICTIVE_CONTROLS",
            "status":status,"trust":"NO_CAUSAL_OR_PHYSICAL_GEOMETRY_CLAIM",
            "source_identity":frames[0].source_identity,
            "calibration_identity":frames[0].calibration_identity,
            "evidence_identity":_digest({"frames":[f.identity() for f in frames],
                                         "target":target,"donor":donor}),
            "target":target,"donor":donor,
            "past_lag":lag,"split_fractions":splits,
            "original_frame_count":len(frames),
            "preserved_frame_identities":identities,
            "splits":tuple(results),
            "held_split_count":held,
            "scientific_jobs_eliminated":0,"frames_dropped":0,
            "raw_observations_averaged_or_smoothed":False,
            "physical_boundary_condition_supported":False,
            "limitations":(
                "Same-clock geometry operators are tested against *future* target changes.",
                "Quadratic operators are compared against a nested linear interaction term, not just self-only dynamics.",
                "Independent source/seed replication is not established by overlapping time splits.",
                "Past-only donor lag is a negative control, not proof against common drivers.",
                "The maximum normalized-QR diagonal ratio is a conditioning warning proxy, not an exact spectral condition number.",
                "Near-singular, rank-deficient or unexplained splits require durable raw-evidence research holds.",
                "No equivalence, calculation suppression, physical geometry or causality claim.",
            )}
