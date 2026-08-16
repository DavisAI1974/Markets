"""Whole-curve, P&L-blind duration audit.

Tests Greg's actual hypothesis from the S74/S75 graphs:
    the ENTIRE pre-onset dipole mean-flow curve, not scalar summaries, contains
    information about the eventual directional-run duration.

Rules:
- no winner/loser labels
- no fees, gross P&L, or net P&L in target/features
- feature is the full birth->onset signed dipole mean-flow curve resampled to 100 points
- chronological train/test only
- fixed, untuned methods designed to preserve curve geometry
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from leg_imbalance import extract

COINS=("sol","btc","eth","xrp")
KNN_K=25
EPS=1e-12


def rankdata(a):
    a=np.asarray(a,float); order=np.argsort(a,kind="mergesort"); r=np.empty(len(a),float)
    i=0
    while i<len(a):
        j=i+1
        while j<len(a) and a[order[j]]==a[order[i]]: j+=1
        r[order[i:j]]=(i+j-1)/2; i=j
    return r


def corr(x,y):
    x=np.asarray(x,float); y=np.asarray(y,float); m=np.isfinite(x)&np.isfinite(y); x=x[m]; y=y[m]
    if len(x)<3 or np.std(x)<EPS or np.std(y)<EPS: return float("nan")
    return float(np.corrcoef(x,y)[0,1])


def spear(x,y): return corr(rankdata(x),rankdata(y))


def norm_shape(A):
    """Pure shape: each curve starts at 0 and its own birth->onset range is 1."""
    B=A-A[:,[0]]
    rng=np.ptp(B,axis=1)
    rng[rng<EPS]=1.0
    return B/rng[:,None]


def zcurve(A, mu=None, sd=None):
    """Pointwise standardization learned on TRAIN only."""
    if mu is None: mu=A.mean(0)
    if sd is None: sd=A.std(0); sd[sd<EPS]=1.0
    return (A-mu)/sd,mu,sd


def knn_predict(trainA,trainy,testA,k=KNN_K):
    k=min(k,len(trainA))
    out=np.empty(len(testA),float)
    for i,a in enumerate(testA):
        d=np.mean((trainA-a)**2,axis=1)
        ix=np.argpartition(d,k-1)[:k]
        # Median is deliberately robust and has no fitted coefficients.
        out[i]=float(np.median(trainy[ix]))
    return out


def train_quintile_archetypes(A,y):
    order=np.argsort(y,kind="mergesort"); g=np.empty(len(y),int)
    for rank,idx in enumerate(order): g[idx]=min(4,int(rank*5/len(y)))
    means=[]; ranges=[]
    for q in range(5):
        m=g==q
        means.append(A[m].mean(0))
        ranges.append({"q":q+1,"n":int(m.sum()),"duration_median_s":float(np.median(y[m])),"duration_min_s":float(np.min(y[m])),"duration_max_s":float(np.max(y[m]))})
    return np.stack(means),ranges


def nearest_archetype(A,means):
    D=np.mean((A[:,None,:]-means[None,:,:])**2,axis=2)
    return np.argmin(D,axis=1)


def archetype_test_summary(predq,y):
    out={}
    for q in range(5):
        m=predq==q
        out[f"Q{q+1}"]={
            "n":int(m.sum()),
            "actual_duration_median_s":float(np.median(y[m])) if m.sum() else None,
            "actual_duration_mean_s":float(np.mean(y[m])) if m.sum() else None,
        }
    return out


def eval_pred(pred,y,base):
    mae=float(np.mean(np.abs(pred-y))); bmae=float(np.mean(np.abs(base-y)))
    return {"spearman":spear(pred,y),"pearson_log_duration":corr(np.log1p(pred),np.log1p(y)),"mae_s":mae,"baseline_mae_s":bmae,"mae_improvement_pct":float(100*(bmae-mae)/bmae) if bmae else float("nan")}


def coin(coin):
    rows,hours=extract(coin)
    y=np.asarray([float(r["dur"]) for r in rows],float)
    raw=np.stack([np.asarray(r["t_pre_arc"],float) for r in rows])
    preclock=np.asarray([float(r["pre_ext"]) for r in rows],float)
    n=len(y); cut=max(50,int(.70*n)); tr=np.arange(n)<cut; te=~tr
    base=float(np.median(y[tr]))

    # Representation 1: actual signed dipole mean-flow curve [-1,+1], pointwise standardized on train.
    Z,mu,sd=zcurve(raw[tr]); Zte=(raw[te]-mu)/sd
    pred_raw=knn_predict(Z,y[tr],Zte)

    # Representation 2: pure geometry after removing each curve's absolute birth/peak scale.
    shape=norm_shape(raw)
    Zs,smu,ssd=zcurve(shape[tr]); Zste=(shape[te]-smu)/ssd
    pred_shape=knn_predict(Zs,y[tr],Zste)

    # Representation 3: whole raw curve + known pre-onset wall-clock duration as one extra dimension.
    pc_mu=float(preclock[tr].mean()); pc_sd=float(preclock[tr].std() or 1.0)
    Zclock=np.column_stack([Z,(preclock[tr]-pc_mu)/pc_sd])
    Zteclock=np.column_stack([Zte,(preclock[te]-pc_mu)/pc_sd])
    pred_clock=knn_predict(Zclock,y[tr],Zteclock)

    # Direct graph test: construct duration-quintile archetype curves on TRAIN only; assign TEST curves by nearest whole-curve shape.
    arche_raw,ranges=train_quintile_archetypes(Z,y[tr])
    pq_raw=nearest_archetype(Zte,arche_raw)
    arche_shape,_=train_quintile_archetypes(Zs,y[tr])
    pq_shape=nearest_archetype(Zste,arche_shape)

    # How well does predicted archetype ORDER track actual duration? Q index is an ordinal duration forecast.
    arch_order_raw=spear(pq_raw+1,y[te]); arch_order_shape=spear(pq_shape+1,y[te])

    # Mean raw curves by actual duration quintile across ALL runs are characterization only, not used in OOS prediction.
    order=np.argsort(y,kind="mergesort"); g=np.empty(n,int)
    for rank,idx in enumerate(order): g[idx]=min(4,int(rank*5/n))
    means={f"Q{q+1}":raw[g==q].mean(0).tolist() for q in range(5)}
    endpoints={f"Q{q+1}":{"n":int((g==q).sum()),"duration_median_s":float(np.median(y[g==q])),"birth_mean":float(raw[g==q,0].mean()),"onset_peak_mean":float(raw[g==q,-1].mean()),"preclock_mean_s":float(preclock[g==q].mean())} for q in range(5)}

    return {
        "n_runs":n,"hours":float(hours),"train_n":int(tr.sum()),"test_n":int(te.sum()),
        "target":"onset->close duration seconds only",
        "pnl_used":False,
        "fixed_knn_k":KNN_K,
        "oos_whole_curve_knn":{
            "raw_dipole_curve":eval_pred(pred_raw,y[te],base),
            "pure_shape_normalized":eval_pred(pred_shape,y[te],base),
            "raw_curve_plus_preonset_clock":eval_pred(pred_clock,y[te],base),
        },
        "oos_nearest_duration_archetype":{
            "train_quintile_duration_ranges":ranges,
            "raw_curve":{"ordinal_spearman":arch_order_raw,"test_actual_duration_by_predicted_archetype":archetype_test_summary(pq_raw,y[te])},
            "pure_shape":{"ordinal_spearman":arch_order_shape,"test_actual_duration_by_predicted_archetype":archetype_test_summary(pq_shape,y[te])},
        },
        "characterization_actual_duration_quintiles":endpoints,
        "mean_raw_dipole_curve_by_actual_duration_quintile":means,
    }


def main():
    out={"analysis":"whole pre-onset dipole mean-flow curve -> future run duration","winner_loser_labels_used":False,"fees_or_pnl_used":False,"coins":{}}
    for c in COINS:
        print("===",c.upper(),"===",flush=True)
        out["coins"][c]=coin(c)
        r=out["coins"][c]
        print("knn",r["oos_whole_curve_knn"],flush=True)
        print("archetype raw rho",r["oos_nearest_duration_archetype"]["raw_curve"]["ordinal_spearman"],"shape rho",r["oos_nearest_duration_archetype"]["pure_shape"]["ordinal_spearman"],flush=True)
    p=Path("whole_curve_duration_audit_results.json"); p.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print("RESULT_FILE="+str(p),flush=True)

if __name__=="__main__": main()
