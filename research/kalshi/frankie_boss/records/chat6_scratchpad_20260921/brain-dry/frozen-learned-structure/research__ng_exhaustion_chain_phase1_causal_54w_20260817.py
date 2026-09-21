#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.neighbors import KNeighborsRegressor

import ng_exhaustion_chain_phase1_causal_20260817 as pilot

HORIZONS = pilot.HORIZONS
DEPTHS = pilot.DEPTHS
MODELS = ("ridge", "extra_trees", "knn")
SEED = 20260817
FOLDS = (
    (tuple(range(0, 18)), tuple(range(18, 24)), "era1"),
    (tuple(range(0, 24)), tuple(range(24, 30)), "era2"),
    (tuple(range(0, 30)), tuple(range(30, 36)), "era3"),
    (tuple(range(0, 36)), tuple(range(36, 42)), "era4"),
    (tuple(range(0, 42)), tuple(range(42, 48)), "era5"),
    (tuple(range(0, 48)), tuple(range(48, 54)), "untouched_confirmation"),
)


def combine(weeks, byweek, hmax, max_depth, history_len):
    xs, ys, meta = [], [], []
    for w in weeks:
        X, Y, idx = pilot.matrices(byweek[w], hmax, max_depth, history_len)
        if len(Y):
            xs.append(X); ys.append(Y)
            meta.extend((w, int(t), byweek[w][int(t)]["event_id"]) for t in idx)
    if not ys:
        return np.empty((0,0)), np.empty((0,22)), []
    X = np.vstack(xs) if history_len else np.empty((sum(len(y) for y in ys), 0), float)
    return X, np.vstack(ys), meta


def sample(X, Y, meta, limit):
    if limit is None or len(Y) <= limit:
        return X, Y, meta
    ix = np.linspace(0, len(Y)-1, int(limit), dtype=int)
    return X[ix], Y[ix], [meta[i] for i in ix]


def scale(Xtr, Ytr, Xte, Yte, history_len):
    ym = Ytr.mean(axis=0); ys = Ytr.std(axis=0); ys[ys < 1e-12] = 1.0
    Ytr = (Ytr-ym)/ys; Yte = (Yte-ym)/ys
    if history_len:
        xm = Xtr.mean(axis=0); xs = Xtr.std(axis=0); xs[xs < 1e-12] = 1.0
        Xtr = (Xtr-xm)/xs; Xte = (Xte-xm)/xs
    return Xtr, Ytr, Xte, Yte


def limits(model, inner):
    if model == "ridge": return None, None
    if model == "extra_trees": return (70000 if inner else 110000), None
    return (18000 if inner else 30000), (3000 if inner else 5500)


def grid(model):
    return pilot.RIDGE_GRID if model == "ridge" else (pilot.TREE_GRID if model == "extra_trees" else pilot.KNN_GRID)


def fit_predict(model, param, Xtr, Ytr, Xte, inner=False):
    if Xtr.shape[1] == 0:
        return np.zeros((len(Xte), Ytr.shape[1]), float)
    if model == "ridge": m = Ridge(alpha=float(param))
    elif model == "extra_trees":
        m = ExtraTreesRegressor(n_estimators=30 if inner else 80, min_samples_leaf=int(param), max_features=1.0, random_state=SEED, n_jobs=-1)
    else:
        m = KNeighborsRegressor(n_neighbors=min(int(param), len(Xtr)), weights="distance", n_jobs=-1)
    m.fit(Xtr, Ytr)
    return m.predict(Xte)


def score(model, param, train_weeks, test_weeks, byweek, hmax, max_depth, history_len, inner=False):
    Xtr, Ytr, _ = combine(train_weeks, byweek, hmax, max_depth, history_len)
    Xte, Yte, meta = combine(test_weeks, byweek, hmax, max_depth, history_len)
    if not len(Ytr) or not len(Yte): return None
    trl, tel = limits(model, inner)
    Xtr, Ytr, _ = sample(Xtr, Ytr, [("",0,"")]*len(Ytr), trl)
    Xte, Yte, meta = sample(Xte, Yte, meta, tel)
    Xtr, Ytr, Xte, Yte = scale(Xtr, Ytr, Xte, Yte, history_len)
    pred = fit_predict(model, param, Xtr, Ytr, Xte, inner=inner)
    loss = np.mean((Yte-pred)**2, axis=1)
    return {"loss": loss, "meta": meta, "mse": float(loss.mean()), "n": int(len(loss))}


def tune(model, train_weeks, byweek, hmax, max_depth, history_len):
    if history_len == 0: return None
    nval = max(3, len(train_weeks)//6)
    fitw, valw = train_weeks[:-nval], train_weeks[-nval:]
    cand = []
    for p in grid(model):
        z = score(model, p, fitw, valw, byweek, hmax, max_depth, history_len, inner=True)
        if z is not None: cand.append((z["mse"], p))
    if not cand: return None
    cand.sort(key=lambda x:(x[0], float(x[1])))
    return cand[0][1]


def paired(model, train_weeks, test_weeks, byweek, hmax, depth):
    short = depth-1
    ps = tune(model, train_weeks, byweek, hmax, depth, short) if short else None
    pl = tune(model, train_weeks, byweek, hmax, depth, depth)
    if pl is None: return None
    a = score(model, ps, train_weeks, test_weeks, byweek, hmax, depth, short)
    b = score(model, pl, train_weeks, test_weeks, byweek, hmax, depth, depth)
    if a is None or b is None: return None
    if a["meta"] != b["meta"]: raise SystemExit(f"causal paired-sample drift h={hmax} d={depth} model={model}")
    g = a["loss"]-b["loss"]
    pw = defaultdict(list)
    for x,(w,_,_) in zip(g,a["meta"]): pw[w].append(float(x))
    return {
        "n": int(len(g)), "short_param": ps, "long_param": pl,
        "short_mse": a["mse"], "long_mse": b["mse"],
        "gain_mean": float(g.mean()), "gain_median": float(np.median(g)), "gain_positive_rate": float(np.mean(g>0)),
        "per_week_gain_mean": {w:float(np.mean(v)) for w,v in sorted(pw.items())},
    }


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("event_table"); ap.add_argument("--base-freeze",default="research/NG_EXHAUSTION_CHAIN_PHASE1_54W_BASE_FREEZE_20260817.json"); ap.add_argument("--out",default="NG_EXHAUSTION_CHAIN_PHASE1_CAUSAL_54W_20260817.json"); a=ap.parse_args()
    freeze=json.load(open(a.base_freeze)); byweek=pilot.load_rows(a.event_table)
    if sorted(byweek)!=freeze["base_weeks"] or len(byweek)!=54: raise SystemExit("54-week base drift")
    weeks=sorted(byweek); out={}
    for h in HORIZONS:
        hz={}
        for train_ix,test_ix,name in FOLDS:
            tr=[weeks[i] for i in train_ix]; te=[weeks[i] for i in test_ix]
            f={"train_weeks":tr,"test_weeks":te,"depth":{}}
            for d in DEPTHS:
                f["depth"][str(d)]={}
                for model in MODELS:
                    z=paired(model,tr,te,byweek,h,d)
                    f["depth"][str(d)][model]={"n":0,"gain_mean":None} if z is None else z
            hz[name]=f
        out[str(h)]=hz
    result={
        "status":"PHASE1_CAUSAL_EXECUTABLE_54W_PROVISIONAL_COMPLETE",
        "source_engine":"research/ng_exhaustion_chain_phase1_causal_20260817.py",
        "week_count":54,"weeks":weeks,"temporarily_excluded_week":"20260329",
        "characteristics_accessed":False,"timing_accessed_only_for_causal_availability":True,
        "by_information_horizon_seconds":out,
        "historical_phase1_complete":False,"phase2_allowed":False,"runway_clock_mutated":False,"permanent_frankie_mutated":False,
    }
    Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result["status"],"horizons":list(out)},indent=2))

if __name__=="__main__": main()
