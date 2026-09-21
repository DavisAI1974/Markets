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
from sklearn.neighbors import KNeighborsRegressor

import ng_exhaustion_chain_phase1_discovery_20260817 as pilot

DEPTHS = tuple(range(1, 13))
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


def finite(x):
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def sample_rows(X, Y, meta, limit):
    if limit is None or len(Y) <= limit:
        return X, Y, meta
    ix = np.linspace(0, len(Y) - 1, int(limit), dtype=int)
    return X[ix], Y[ix], [meta[i] for i in ix]


def matrices(weeks, byweek, arrays, valid, max_depth, history_len):
    xs, ys, meta = [], [], []
    for w in weeks:
        arr = arrays[w]
        ok = valid[w]
        rows = byweek[w]
        for t in range(max_depth, len(arr)):
            if not ok[t] or not ok[t-max_depth:t].all():
                continue
            ys.append(arr[t])
            xs.append(arr[t-history_len:t].reshape(-1) if history_len else np.empty(0, float))
            meta.append((w, t, rows[t]["event_id"]))
    dim = next(iter(arrays.values())).shape[1]
    X = np.asarray(xs, float) if history_len else np.empty((len(ys), 0), float)
    Y = np.asarray(ys, float) if ys else np.empty((0, dim), float)
    return X, Y, meta


def scale_pair(Xtr, Ytr, Xte, Yte, history_len):
    mu = Ytr.mean(axis=0)
    sd = Ytr.std(axis=0)
    sd[sd < 1e-12] = 1.0
    Ytrz = (Ytr - mu) / sd
    Ytez = (Yte - mu) / sd
    if history_len:
        xm = np.tile(mu, history_len)
        xs = np.tile(sd, history_len)
        Xtrz = (Xtr - xm) / xs
        Xtez = (Xte - xm) / xs
    else:
        Xtrz, Xtez = Xtr, Xte
    return Xtrz, Ytrz, Xtez, Ytez


def fit_predict(model, param, Xtr, Ytr, Xte, inner=False):
    if Xtr.shape[1] == 0:
        return np.zeros((len(Xte), Ytr.shape[1]), float)
    if model == "ridge":
        m = Ridge(alpha=float(param), fit_intercept=True)
    elif model == "extra_trees":
        m = ExtraTreesRegressor(
            n_estimators=40 if inner else 100,
            min_samples_leaf=int(param),
            max_features=1.0,
            random_state=SEED,
            n_jobs=-1,
        )
    elif model == "knn":
        m = KNeighborsRegressor(n_neighbors=min(int(param), len(Xtr)), weights="distance", p=2, n_jobs=-1)
    else:
        raise ValueError(model)
    m.fit(Xtr, Ytr)
    return m.predict(Xte)


def grid(model):
    return pilot.RIDGE_GRID if model == "ridge" else (pilot.TREE_LEAF_GRID if model == "extra_trees" else pilot.KNN_GRID)


def model_limits(model, inner):
    if model == "ridge":
        return None, None
    if model == "extra_trees":
        return (70000 if inner else 110000), None
    return (18000 if inner else 30000), (3500 if inner else 6000)


def score_once(model, param, train_weeks, test_weeks, byweek, arrays, valid, max_depth, history_len, inner=False):
    Xtr, Ytr, _ = matrices(train_weeks, byweek, arrays, valid, max_depth, history_len)
    Xte, Yte, meta = matrices(test_weeks, byweek, arrays, valid, max_depth, history_len)
    if not len(Ytr) or not len(Yte):
        return None
    tr_lim, te_lim = model_limits(model, inner)
    Xtr, Ytr, _ = sample_rows(Xtr, Ytr, [("", 0, "")]*len(Ytr), tr_lim)
    Xte, Yte, meta = sample_rows(Xte, Yte, meta, te_lim)
    Xtr, Ytr, Xte, Yte = scale_pair(Xtr, Ytr, Xte, Yte, history_len)
    pred = fit_predict(model, param, Xtr, Ytr, Xte, inner=inner)
    loss = np.mean((Yte - pred) ** 2, axis=1)
    return {"loss": loss, "meta": meta, "n": int(len(loss)), "mse": float(loss.mean())}


def tune(model, train_weeks, byweek, arrays, valid, max_depth, history_len):
    if history_len == 0:
        return None
    nval = max(3, len(train_weeks) // 6)
    fitw = train_weeks[:-nval]
    valw = train_weeks[-nval:]
    cand = []
    for p in grid(model):
        z = score_once(model, p, fitw, valw, byweek, arrays, valid, max_depth, history_len, inner=True)
        if z is not None:
            cand.append((z["mse"], p))
    if not cand:
        return None
    cand.sort(key=lambda x: (x[0], float(x[1])))
    return cand[0][1]


def paired_depth(model, train_weeks, test_weeks, byweek, arrays, valid, depth):
    short = depth - 1
    ps = tune(model, train_weeks, byweek, arrays, valid, depth, short) if short else None
    pl = tune(model, train_weeks, byweek, arrays, valid, depth, depth)
    if pl is None:
        return None
    zs = score_once(model, ps, train_weeks, test_weeks, byweek, arrays, valid, depth, short, inner=False)
    zl = score_once(model, pl, train_weeks, test_weeks, byweek, arrays, valid, depth, depth, inner=False)
    if zs is None or zl is None:
        return None
    if zs["meta"] != zl["meta"]:
        raise SystemExit(f"paired-sample invariant failed model={model} depth={depth}")
    gain = zs["loss"] - zl["loss"]
    perweek = defaultdict(list)
    for g, (w, _, _) in zip(gain, zs["meta"]):
        perweek[w].append(float(g))
    return {
        "short_param": ps,
        "long_param": pl,
        "n": int(len(gain)),
        "gain_mean": float(gain.mean()),
        "gain_median": float(np.median(gain)),
        "gain_positive_rate": float(np.mean(gain > 0)),
        "short_mse": zs["mse"],
        "long_mse": zl["mse"],
        "per_week_gain_mean": {w: float(np.mean(v)) for w, v in sorted(perweek.items())},
        "meta": zs["meta"],
        "gain": gain,
    }


def run_view(byweek, view, write_gains=None):
    arrays, valid = pilot.make_view(byweek, view)
    weeks = sorted(byweek)
    out = {}
    gain_f = gzip.open(write_gains, "wt") if write_gains else None
    try:
        for train_ix, test_ix, fold_name in FOLDS:
            train_weeks = [weeks[i] for i in train_ix]
            test_weeks = [weeks[i] for i in test_ix]
            f = {"train_weeks": train_weeks, "test_weeks": test_weeks, "depth": {}}
            max_depth = 12 if view == "full" else 6
            for depth in range(1, max_depth + 1):
                f["depth"][str(depth)] = {}
                for model in MODELS:
                    z = paired_depth(model, train_weeks, test_weeks, byweek, arrays, valid, depth)
                    if z is None:
                        f["depth"][str(depth)][model] = {"n": 0, "gain_mean": None}
                        continue
                    f["depth"][str(depth)][model] = {k: v for k, v in z.items() if k not in ("meta", "gain")}
                    if gain_f is not None:
                        for g, (w, seq, eid) in zip(z["gain"], z["meta"]):
                            gain_f.write(json.dumps({
                                "fold": fold_name, "week_sunday": w, "sequence_index": int(seq), "target_event_id": eid,
                                "model": model, "depth": depth, "incremental_gain": float(g), "view": view,
                            }, sort_keys=True, separators=(",", ":")) + "\n")
            out[fold_name] = f
    finally:
        if gain_f is not None:
            gain_f.close()
    return {
        "dimension": int(next(iter(arrays.values())).shape[1]),
        "valid_events_by_week": {w: int(valid[w].sum()) for w in weeks},
        "folds": out,
    }


def aggregate(primary):
    out = {}
    discovery = [k for k in primary["folds"] if k != "untouched_confirmation"]
    for depth in DEPTHS:
        d = {}
        for model in MODELS:
            era = []
            weeks = []
            for f in discovery:
                z = primary["folds"][f]["depth"].get(str(depth), {}).get(model, {})
                if finite(z.get("gain_mean")):
                    era.append(float(z["gain_mean"]))
                    weeks.extend(float(x) for x in z.get("per_week_gain_mean", {}).values())
            confirm = primary["folds"]["untouched_confirmation"]["depth"].get(str(depth), {}).get(model, {})
            d[model] = {
                "discovery_era_gains": era,
                "discovery_eras_positive": int(sum(x > 0 for x in era)),
                "discovery_era_count": len(era),
                "discovery_week_positive_rate": None if not weeks else float(np.mean(np.asarray(weeks) > 0)),
                "confirmation_gain_mean": confirm.get("gain_mean"),
                "confirmation_per_week_gain_mean": confirm.get("per_week_gain_mean", {}),
            }
        out[str(depth)] = d
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("event_table")
    ap.add_argument("--base-freeze", default="research/NG_EXHAUSTION_CHAIN_PHASE1_54W_BASE_FREEZE_20260817.json")
    ap.add_argument("--out-prefix", default="NG_EXHAUSTION_CHAIN_PHASE1_STRUCTURAL_54W_20260817")
    a = ap.parse_args()
    freeze = json.load(open(a.base_freeze))
    byweek = pilot.load_rows(a.event_table)
    if sorted(byweek) != freeze["base_weeks"] or len(byweek) != 54:
        raise SystemExit("54-week base drift")
    gains_path = a.out_prefix + "_OOT_GAINS.jsonl.gz"
    primary = run_view(byweek, "full", gains_path)
    sparse = run_view(byweek, "sparse")
    result = {
        "status": "PHASE1_STRUCTURAL_54W_PROVISIONAL_COMPLETE",
        "source_engine": "research/ng_exhaustion_chain_phase1_discovery_20260817.py",
        "week_count": 54,
        "weeks": sorted(byweek),
        "temporarily_excluded_week": "20260329",
        "characteristics_accessed": False,
        "primary_full_path": primary,
        "sparse_sensitivity": sparse,
        "aggregate": aggregate(primary),
        "out_of_time_gain_table": gains_path,
        "historical_phase1_complete": False,
        "phase2_allowed": False,
        "runway_clock_mutated": False,
        "permanent_frankie_mutated": False,
    }
    Path(a.out_prefix + "_SUMMARY.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "week_count": 54, "depths": list(result["aggregate"])}, indent=2))


if __name__ == "__main__":
    main()
