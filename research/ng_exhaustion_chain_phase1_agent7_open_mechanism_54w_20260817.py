#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge

import ng_exhaustion_chain_phase1_discovery_20260817 as pilot

SEED = 20260817
MAX_DEPTH = 12
ALPHAS = (1.0, 10.0, 100.0, 1000.0)
FOLDS = (
    (tuple(range(0, 18)), tuple(range(18, 24)), "era1"),
    (tuple(range(0, 24)), tuple(range(24, 30)), "era2"),
    (tuple(range(0, 30)), tuple(range(30, 36)), "era3"),
    (tuple(range(0, 36)), tuple(range(36, 42)), "era4"),
    (tuple(range(0, 42)), tuple(range(42, 48)), "era5"),
    (tuple(range(0, 48)), tuple(range(48, 54)), "untouched_confirmation"),
)


def finite(x):
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def feature_names(depth: int, dim: int):
    names = []
    for lag in range(depth, 0, -1):
        for j in range(dim):
            names.append(f"L{lag}.x{j}")
            names.append(f"L{lag}.abs_x{j}")
            names.append(f"L{lag}.sq_x{j}")
            names.append(f"L{lag}.signed_sqrt_x{j}")
            names.append(f"L{lag}.tanh_x{j}")
    for lag in range(depth, 1, -1):
        newer = lag - 1
        for j in range(dim):
            names.append(f"L{lag}xL{newer}.x{j}_product")
            names.append(f"L{lag}-L{newer}.x{j}_difference")
        names.extend([
            f"L{lag}xL{newer}.norm_product",
            f"L{lag}/L{newer}.norm_ratio",
            f"L{lag}xL{newer}.cosine",
        ])
    return names


def nonlinear_history(hist: np.ndarray) -> np.ndarray:
    # hist oldest -> newest; each row is the frozen transformed behavior vector.
    chunks = []
    for x in hist:
        chunks.extend([
            x,
            np.abs(x),
            x * x,
            np.sign(x) * np.sqrt(np.abs(x)),
            np.tanh(x),
        ])
    for a, b in zip(hist[:-1], hist[1:]):
        na = float(np.linalg.norm(a)); nb = float(np.linalg.norm(b))
        denom = max(1e-9, na * nb)
        chunks.extend([
            a * b,
            a - b,
            np.asarray([na * nb, na / max(1e-9, nb), float(np.dot(a, b)) / denom], dtype=np.float32),
        ])
    return np.concatenate(chunks).astype(np.float32, copy=False)


def paired_week_matrices(weeks, byweek, arrays, valid, depth):
    short_x, long_x, ys, meta = [], [], [], []
    dim = next(iter(arrays.values())).shape[1]
    for w in weeks:
        arr = arrays[w]
        ok = valid[w]
        rows = byweek[w]
        for t in range(depth, len(arr)):
            if not ok[t] or not ok[t-depth:t].all():
                continue
            long_hist = arr[t-depth:t]
            long_x.append(nonlinear_history(long_hist))
            if depth == 1:
                short_x.append(np.empty(0, dtype=np.float32))
            else:
                short_x.append(nonlinear_history(long_hist[1:]))
            ys.append(arr[t].astype(np.float32, copy=False))
            meta.append((w, int(t), rows[t]["event_id"]))
    Y = np.asarray(ys, dtype=np.float32) if ys else np.empty((0, dim), dtype=np.float32)
    XL = np.asarray(long_x, dtype=np.float32) if long_x else np.empty((0, 0), dtype=np.float32)
    if depth == 1:
        XS = np.empty((len(Y), 0), dtype=np.float32)
    else:
        XS = np.asarray(short_x, dtype=np.float32) if short_x else np.empty((0, 0), dtype=np.float32)
    return XS, XL, Y, meta


def deterministic_sample(XS, XL, Y, meta, limit):
    if limit is None or len(Y) <= limit:
        return XS, XL, Y, meta
    ix = np.linspace(0, len(Y) - 1, int(limit), dtype=int)
    return XS[ix], XL[ix], Y[ix], [meta[i] for i in ix]


def standardize_train_test(Xtr, Xte):
    if Xtr.shape[1] == 0:
        return Xtr, Xte, None, None
    mu = Xtr.mean(axis=0, dtype=np.float64).astype(np.float32)
    sd = Xtr.std(axis=0, dtype=np.float64).astype(np.float32)
    sd[sd < 1e-6] = 1.0
    return (Xtr - mu) / sd, (Xte - mu) / sd, mu, sd


def standardize_y(Ytr, Yte):
    mu = Ytr.mean(axis=0, dtype=np.float64).astype(np.float32)
    sd = Ytr.std(axis=0, dtype=np.float64).astype(np.float32)
    sd[sd < 1e-6] = 1.0
    return (Ytr - mu) / sd, (Yte - mu) / sd


def ridge_loss(alpha, Xtr, Ytr, Xte, Yte):
    if Xtr.shape[1] == 0:
        pred = np.zeros_like(Yte)
        model = None
    else:
        model = Ridge(alpha=float(alpha), fit_intercept=True, solver="lsqr")
        model.fit(Xtr, Ytr)
        pred = model.predict(Xte)
    loss = np.mean((Yte - pred) ** 2, axis=1)
    return loss, model


def tune_alpha(Xfit, Yfit, Xval, Yval):
    best = None
    for a in ALPHAS:
        loss, _ = ridge_loss(a, Xfit, Yfit, Xval, Yval)
        rec = (float(loss.mean()), float(a))
        if best is None or rec < best:
            best = rec
    return best[1]


def fit_pair(train_weeks, test_weeks, byweek, arrays, valid, depth, train_limit=24000, test_limit=9000):
    XS_tr, XL_tr, Ytr, _ = paired_week_matrices(train_weeks, byweek, arrays, valid, depth)
    XS_te, XL_te, Yte, meta = paired_week_matrices(test_weeks, byweek, arrays, valid, depth)
    if not len(Ytr) or not len(Yte):
        return None
    XS_tr, XL_tr, Ytr, _ = deterministic_sample(XS_tr, XL_tr, Ytr, [("", 0, "")]*len(Ytr), train_limit)
    XS_te, XL_te, Yte, meta = deterministic_sample(XS_te, XL_te, Yte, meta, test_limit)

    nval = max(3, len(train_weeks)//6)
    fit_weeks, val_weeks = train_weeks[:-nval], train_weeks[-nval:]
    XSi, XLi, Yi, _ = paired_week_matrices(fit_weeks, byweek, arrays, valid, depth)
    XSv, XLv, Yv, _ = paired_week_matrices(val_weeks, byweek, arrays, valid, depth)
    XSi, XLi, Yi, _ = deterministic_sample(XSi, XLi, Yi, [("",0,"")]*len(Yi), min(train_limit, 18000))
    XSv, XLv, Yv, _ = deterministic_sample(XSv, XLv, Yv, [("",0,"")]*len(Yv), 6000)

    Yi, Yv = standardize_y(Yi, Yv)
    XSi, XSv, _, _ = standardize_train_test(XSi, XSv)
    XLi, XLv, _, _ = standardize_train_test(XLi, XLv)
    a_short = None if depth == 1 else tune_alpha(XSi, Yi, XSv, Yv)
    a_long = tune_alpha(XLi, Yi, XLv, Yv)
    inner_short = float(np.mean(Yv**2)) if depth == 1 else float(ridge_loss(a_short, XSi, Yi, XSv, Yv)[0].mean())
    inner_long = float(ridge_loss(a_long, XLi, Yi, XLv, Yv)[0].mean())
    inner_gain = inner_short - inner_long

    Ytrz, Ytez = standardize_y(Ytr, Yte)
    XS_trz, XS_tez, _, _ = standardize_train_test(XS_tr, XS_te)
    XL_trz, XL_tez, _, _ = standardize_train_test(XL_tr, XL_te)
    ls, _ = ridge_loss(a_short, XS_trz, Ytrz, XS_tez, Ytez) if depth > 1 else (np.mean(Ytez**2, axis=1), None)
    ll, long_model = ridge_loss(a_long, XL_trz, Ytrz, XL_tez, Ytez)
    gain = ls - ll
    by_week = defaultdict(list)
    for g, (w, _, _) in zip(gain, meta):
        by_week[w].append(float(g))

    top_terms = []
    if long_model is not None:
        names = feature_names(depth, Ytr.shape[1])
        coef = np.asarray(long_model.coef_)
        flat = np.abs(coef).ravel()
        if flat.size:
            top = np.argpartition(flat, -min(30, flat.size))[-min(30, flat.size):]
            top = top[np.argsort(flat[top])[::-1]]
            for ix in top:
                target = int(ix // coef.shape[1]); feat = int(ix % coef.shape[1])
                top_terms.append({"target_dimension": target, "feature": names[feat], "coefficient_standardized": float(coef[target, feat])})

    return {
        "depth": depth,
        "inner_validation_gain": float(inner_gain),
        "selected_in_training": bool(inner_gain > 0),
        "short_alpha": a_short,
        "long_alpha": a_long,
        "n": int(len(gain)),
        "gain_mean": float(gain.mean()),
        "gain_median": float(np.median(gain)),
        "gain_positive_rate": float(np.mean(gain > 0)),
        "per_week_gain_mean": {w: float(np.mean(v)) for w, v in sorted(by_week.items())},
        "top_explicit_equation_terms": top_terms,
    }


def extra_trees_crosscheck(train_weeks, test_weeks, byweek, arrays, valid, depth):
    XS_tr, XL_tr, Ytr, _ = paired_week_matrices(train_weeks, byweek, arrays, valid, depth)
    XS_te, XL_te, Yte, _ = paired_week_matrices(test_weeks, byweek, arrays, valid, depth)
    if not len(Ytr) or not len(Yte):
        return None
    XS_tr, XL_tr, Ytr, _ = deterministic_sample(XS_tr, XL_tr, Ytr, [("",0,"")]*len(Ytr), 18000)
    XS_te, XL_te, Yte, _ = deterministic_sample(XS_te, XL_te, Yte, [("",0,"")]*len(Yte), 5000)
    Ytrz, Ytez = standardize_y(Ytr, Yte)
    def pred(Xtr, Xte):
        if Xtr.shape[1] == 0:
            return np.zeros_like(Ytez)
        m = ExtraTreesRegressor(n_estimators=60, min_samples_leaf=40, max_features=0.7, random_state=SEED, n_jobs=-1)
        m.fit(Xtr, Ytrz)
        return m.predict(Xte)
    ps = pred(XS_tr, XS_te)
    pl = pred(XL_tr, XL_te)
    ls = np.mean((Ytez-ps)**2, axis=1); ll = np.mean((Ytez-pl)**2, axis=1)
    g = ls-ll
    return {"n": int(len(g)), "gain_mean": float(g.mean()), "gain_positive_rate": float(np.mean(g>0))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("event_table")
    ap.add_argument("--base-freeze", default="research/NG_EXHAUSTION_CHAIN_PHASE1_54W_BASE_FREEZE_20260817.json")
    ap.add_argument("--protocol", default="research/NG_EXHAUSTION_CHAIN_PHASE1_AGENT7_OPEN_MECHANISM_20260817.json")
    ap.add_argument("--out", default="NG_EXHAUSTION_CHAIN_PHASE1_AGENT7_OPEN_MECHANISM_54W_20260817.json")
    a = ap.parse_args()

    protocol = json.load(open(a.protocol)); freeze = json.load(open(a.base_freeze))
    assert protocol["status"] == "FROZEN_BEFORE_AGENT7_54W_RESULTS"
    byweek = pilot.load_rows(a.event_table)
    if sorted(byweek) != freeze["base_weeks"] or len(byweek) != 54:
        raise SystemExit("Agent 7 54-week base drift")
    arrays, valid = pilot.make_view(byweek, "full")
    weeks = sorted(byweek)
    folds = {}
    for train_ix, test_ix, name in FOLDS:
        train_weeks = [weeks[i] for i in train_ix]; test_weeks = [weeks[i] for i in test_ix]
        rec = {"train_weeks": train_weeks, "test_weeks": test_weeks, "depth": {}}
        for d in range(1, MAX_DEPTH+1):
            z = fit_pair(train_weeks, test_weeks, byweek, arrays, valid, d)
            if z is None:
                rec["depth"][str(d)] = {"n": 0, "selected_in_training": False}
                continue
            if z["selected_in_training"]:
                z["extra_trees_crosscheck"] = extra_trees_crosscheck(train_weeks, test_weeks, byweek, arrays, valid, d)
            else:
                z["outer_test_interpretation"] = "not eligible for promotion from this fold because the depth was not selected inside training"
            rec["depth"][str(d)] = z
        folds[name] = rec

    result = {
        "status": "PHASE1_AGENT7_OPEN_HIGHER_ORDER_54W_PROVISIONAL_COMPLETE",
        "protocol": a.protocol,
        "week_count": 54,
        "weeks": weeks,
        "temporarily_excluded_week": "20260329",
        "source_behavior_vector": "same frozen 22-dimensional full-path vector used by the prior Phase-1 engine",
        "independent_higher_order_discovery": True,
        "folds": folds,
        "right_censor_rule": "If the deepest tested depth survives, chain depth is right-censored at D=12 and must be extended rather than declared to stop there.",
        "historical_phase1_complete": False,
        "phase2_allowed": False,
        "runway_clock_mutated": False,
        "permanent_frankie_mutated": False,
    }
    Path(a.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "week_count": 54, "max_depth": MAX_DEPTH}, indent=2))


if __name__ == "__main__":
    main()
