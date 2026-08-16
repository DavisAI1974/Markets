"""P&L-blind live-tail runway audit for the old S74 dipole curves.

Winner/loser labels are not used.  Each executor leg is treated only as a
directional run.  At fixed wall-clock landmarks after onset, use only dipole
mean-flow observations available up to that instant to estimate remaining run
life / survival.  This matches the intended live use of the whole-leg graphs.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from leg_imbalance import (
    CPS,
    KRAKEN,
    SMOOTH_SEC,
    build_channels,
    load_raw,
    median_spread_bps,
    rolling_imb,
    run_kraken_cell,
)

COINS = ("sol", "btc", "eth", "xrp")
LANDMARKS_S = (5, 10, 20, 30, 45, 60)
SURVIVE_AHEAD_S = (10, 20, 30)
EPS = 1e-12


def corr(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y); x = x[m]; y = y[m]
    if len(x) < 3 or np.std(x) < EPS or np.std(y) < EPS:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def rankdata(a):
    a = np.asarray(a, float); order = np.argsort(a, kind="mergesort"); r = np.empty(len(a), float)
    i = 0
    while i < len(a):
        j = i + 1
        while j < len(a) and a[order[j]] == a[order[i]]: j += 1
        r[order[i:j]] = (i + j - 1) / 2.0; i = j
    return r


def spearman(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y); x=x[m]; y=y[m]
    return corr(rankdata(x), rankdata(y)) if len(x) >= 3 else float("nan")


def auc(y, s):
    """Tie-safe rank AUC; y=1 is survives horizon."""
    y = np.asarray(y, int); s = np.asarray(s, float)
    m = np.isfinite(s); y=y[m]; s=s[m]
    pos = y == 1; neg = ~pos
    if pos.sum() == 0 or neg.sum() == 0: return float("nan")
    r = rankdata(s)
    return float((r[pos].sum() - pos.sum() * (pos.sum()-1)/2.0) / (pos.sum()*neg.sum()))


def slope(v, seconds):
    n = min(len(v), max(3, int(seconds*CPS)))
    z = np.asarray(v[-n:], float)
    x = np.arange(n, dtype=float) / CPS
    return float(np.polyfit(x, z, 1)[0]) if n >= 3 else 0.0


def tail_features(v):
    """v is signed-to-run-side dipole mean flow from onset through NOW."""
    v = np.asarray(v, float)
    n5 = max(1, int(5*CPS)); n10=max(1,int(10*CPS))
    last5 = v[-n5:]; last10=v[-n10:]
    peak_so_far = float(np.max(v))
    now = float(v[-1])
    return {
        "flow_now": now,
        "last5_mean": float(np.mean(last5)),
        "last10_mean": float(np.mean(last10)),
        "slope5": slope(v, 5),
        "slope10": slope(v, 10),
        "peak_so_far": peak_so_far,
        "drop_from_peak": float(peak_so_far - now),
        "mean_since_onset": float(np.mean(v)),
        "min_since_onset": float(np.min(v)),
        "negative_fraction": float(np.mean(v < 0)),
        "negative_last5_fraction": float(np.mean(last5 < 0)),
        "crossed_below_zero": float(np.any(v < 0)),
        "flow_change_from_onset": float(now - v[0]),
    }


def build_runs(coin):
    path = f"/tmp/kbook/{coin}_book.jsonl"
    cfg = [c for c in KRAKEN if c.coin == coin][0]
    raw = load_raw(path)
    ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid=np.asarray(g["mid"],float); buy=np.asarray(g["buy"],float); sell=np.asarray(g["sell"],float)
    bb=np.asarray(g["bidK"][1],float); ba=np.asarray(g["askK"][1],float)
    hs=median_spread_bps(path, raw=raw)/2.0
    res,_ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)
    timb = rolling_imb(buy, sell, SMOOTH_SEC)
    runs=[]
    for l in sorted(res.legs, key=lambda z:int(z.open_idx)):
        o=int(l.open_idx); c=int(l.close_idx); side=int(l.side)
        if c <= o: continue
        arr=timb[o:c+1]*side
        runs.append({
            "open_idx":o,
            "duration_s":float((c-o)/CPS),
            "side":side,
            "flow":arr,
        })
    return runs


def feature_bins(x, y_survive, remaining):
    """Equal-count quintiles of one feature; descriptive monotonicity without threshold fitting."""
    x=np.asarray(x,float); y_survive=np.asarray(y_survive,int); remaining=np.asarray(remaining,float)
    order=np.argsort(x, kind="mergesort"); q=np.empty(len(x),int)
    for rank, idx in enumerate(order): q[idx]=min(4,int(rank*5/len(x)))
    out={}
    for k in range(5):
        m=q==k
        out[f"Q{k+1}"]={
            "n":int(m.sum()),
            "feature_mean":float(np.mean(x[m])),
            "survival_rate":float(np.mean(y_survive[m])),
            "remaining_median_s":float(np.median(remaining[m])),
            "remaining_mean_s":float(np.mean(remaining[m])),
        }
    return out


def chrono_logistic(X, y):
    n=len(y); cut=max(20,int(n*0.70)); tr=np.arange(n)<cut; te=~tr
    if y[tr].min()==y[tr].max() or y[te].min()==y[te].max():
        return {"train_n":int(tr.sum()),"test_n":int(te.sum()),"test_auc":float("nan")}
    sc=StandardScaler().fit(X[tr]); Z=sc.transform(X)
    model=LogisticRegression(C=1.0, max_iter=2000).fit(Z[tr],y[tr])
    p=model.predict_proba(Z[te])[:,1]
    return {
        "train_n":int(tr.sum()),"test_n":int(te.sum()),
        "test_auc":auc(y[te],p),
        "test_base_rate":float(np.mean(y[te])),
        "coefficients":model.coef_[0].tolist(),
    }


def analyze_coin(coin):
    runs=build_runs(coin)
    result={"n_runs":len(runs),"landmarks":{}}
    for L in LANDMARKS_S:
        alive=[r for r in runs if r["duration_s"] >= L]
        if len(alive)<50: continue
        feats=[]; rem=[]; sides=[]
        nidx=int(round(L*CPS))
        for r in alive:
            v=r["flow"][:min(len(r["flow"]),nidx+1)]
            feats.append(tail_features(v)); rem.append(r["duration_s"]-L); sides.append(r["side"])
        names=list(feats[0]); X={k:np.asarray([f[k] for f in feats],float) for k in names}
        rem=np.asarray(rem,float); sides=np.asarray(sides,int)
        lr={"n_alive":len(alive),"remaining_duration_s":{"median":float(np.median(rem)),"mean":float(np.mean(rem))},"features":{},"survival":{}}
        for k,x in X.items():
            lr["features"][k]={
                "spearman_remaining_all":spearman(x,rem),
                "spearman_remaining_buy":spearman(x[sides>0],rem[sides>0]),
                "spearman_remaining_sell":spearman(x[sides<0],rem[sides<0]),
            }
        A=np.column_stack([X[k] for k in names])
        for H in SURVIVE_AHEAD_S:
            y=(rem>=H).astype(int)
            if y.min()==y.max(): continue
            sr={
                "n":len(y),"base_rate":float(np.mean(y)),
                "feature_auc":{k:auc(y,x) for k,x in X.items()},
                "chronological_fixed_logistic":chrono_logistic(A,y),
            }
            # Show the two most interpretable flow-state monotonicity tables.
            sr["flow_now_quintiles"]=feature_bins(X["flow_now"],y,rem)
            sr["last5_mean_quintiles"]=feature_bins(X["last5_mean"],y,rem)
            sr["drop_from_peak_quintiles"]=feature_bins(X["drop_from_peak"],y,rem)
            lr["survival"][f"plus_{H}s"]=sr
        result["landmarks"][f"t{L}s"]=lr
    return result


def main():
    out={
        "analysis":"P&L-blind live dipole mean-flow runway audit",
        "target":"remaining directional-run duration / survival from fixed elapsed landmarks",
        "dipole_axis":"signed-to-run-side rolling trade-flow imbalance, bounded [-1,+1]",
        "fees_or_pnl_used":False,
        "coins":{},
    }
    for coin in COINS:
        print(f"=== {coin.upper()} ===",flush=True)
        out["coins"][coin]=analyze_coin(coin)
        # compact console: best per landmark for +20s
        for L,lr in out["coins"][coin]["landmarks"].items():
            s=lr["survival"].get("plus_20s")
            if not s: continue
            best=sorted(s["feature_auc"].items(),key=lambda kv:abs(kv[1]-0.5),reverse=True)[:4]
            print(L,"n",lr["n_alive"],"+20 base",round(s["base_rate"],3),"best",[(k,round(v,3)) for k,v in best],"oos",round(s["chronological_fixed_logistic"]["test_auc"],3),flush=True)
    p=Path("duration_live_tail_audit_results.json"); p.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print("RESULT_FILE="+str(p),flush=True)

if __name__=="__main__": main()
