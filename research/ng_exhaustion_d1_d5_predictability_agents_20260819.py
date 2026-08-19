#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.neighbors import KNeighborsRegressor

TICK = 0.001
HGRID = tuple([1, 2, 3, 4, 5, 10, 15] + list(range(20, 3601, 5)))
TARGET_H = (5, 10, 20, 30, 60, 120, 300)
MODELS = ("ridge", "extra_trees", "knn")
GRIDS = {
    "ridge": (1.0, 10.0, 100.0),
    "extra_trees": (10, 40),
    "knn": (20, 80),
}
SEED = 20260819
FOLD_BLOCK = {
    "era1": "discovery_fit",
    "era2": "discovery_fit",
    "era3": "discovery_tune",
    "era4": "validation",
    "era5": "validation",
    "untouched_confirmation": "confirmation",
    "held_insert_era4": "held",
}
MIN_SUPPORT = {
    1: {"validation": 100, "confirmation": 50, "held": 50},
    2: {"validation": 30, "confirmation": 15, "held": 10},
    3: {"validation": 10, "confirmation": 5, "held": 5},
}


def finite(x):
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def load_events(*paths):
    by = defaultdict(dict)
    for p in paths:
        with gzip.open(p, "rt") as f:
            for line in f:
                r = json.loads(line)
                by[r["week_sunday"]][int(r["sequence_index"])] = r
    return by


def load_lineage(*paths):
    out = []
    for p in paths:
        with gzip.open(p, "rt") as f:
            for line in f:
                out.append(json.loads(line))
    return out


def day_from_name(p):
    m = re.search(r"(20\d{6})", Path(p).name)
    if not m:
        raise SystemExit(f"cannot parse raw day from {p}")
    return m.group(1)


def load_week_prices(raw_dir, week):
    sun = datetime.strptime(week, "%Y%m%d")
    pts = []
    for p in sorted(Path(raw_dir).glob("NG_*.jsonl.gz")):
        d = day_from_name(p)
        di = (datetime.strptime(d, "%Y%m%d") - sun).days
        if di < 0 or di > 5:
            continue
        with gzip.open(p, "rt") as f:
            for line in f:
                r = json.loads(line)
                if r.get("action") != "T":
                    continue
                try:
                    px = float(r.get("price", 0) or 0)
                    ts = float(r.get("ts_event", r.get("ts")))
                except Exception:
                    continue
                if px <= 0:
                    continue
                pts.append((di * 86400.0 + (ts % 86400.0), px))
    pts.sort(key=lambda z: z[0])
    if not pts:
        return np.empty(0), np.empty(0)
    return np.asarray([x[0] for x in pts], float), np.asarray([x[1] for x in pts], float)


def static_features(e):
    fam = str(e.get("family") or "")
    lag = (e.get("dynamic_endpoint") or {}).get("causal_confirmation_offset_s")
    lag = 0.0 if lag is None else float(lag)
    return np.asarray([
        float(e.get("polarity", 0)),
        lag,
        float(fam == "A"),
        float(fam == "B"),
        float(fam == "C"),
        float(fam not in ("A", "B", "C")),
    ], float)


def event_confirm(e):
    v = (e.get("dynamic_endpoint") or {}).get("causal_confirmation_idx")
    return None if v is None else int(v)


def event_t0(e):
    return int(e["t0_idx"])


def snapshot(times, prices, e, h):
    c = event_confirm(e)
    if c is None:
        return None
    end = float(c + h)
    j = int(np.searchsorted(times, float(c), side="left"))
    k = int(np.searchsorted(times, end, side="right")) - 1
    if j >= len(times) or k < j:
        return None
    p0 = float(prices[j])
    p1 = float(prices[k])
    seg = prices[j:k + 1]
    pol = float(e.get("polarity", 0) or 0)
    if pol == 0:
        return None
    signed = pol * (p1 - p0) / TICK
    if pol > 0:
        mfe = (float(np.max(seg)) - p0) / TICK
        mae = (float(np.min(seg)) - p0) / TICK
    else:
        mfe = (p0 - float(np.min(seg))) / TICK
        mae = (p0 - float(np.max(seg))) / TICK
    return np.asarray([
        math.asinh(signed),
        math.asinh(mfe),
        math.asinh(mae),
        math.asinh(mfe - mae),
    ], float)


def target_vector(e):
    ns = (e.get("link") or {}).get("next_same_polarity")
    if ns is None:
        return None
    out = [1.0 if int(ns) == 1 else -1.0]
    post = (e.get("outcome") or {}).get("post_endpoint_price")
    if not post:
        return None
    for metric in ("signed_displacement_ticks", "mfe_ticks", "mae_ticks"):
        for h in TARGET_H:
            z = (post.get("horizons") or {}).get(str(h), {})
            if z.get("censored", False) or not finite(z.get(metric)):
                return None
            out.append(math.asinh(float(z[metric])))
    return np.asarray(out, float)


def cases_for_depth(events, lineage, depth):
    rows = []
    for lr in lineage:
        if int(lr.get("all_model_consecutive_positive_depth", 0)) != depth:
            continue
        w = lr["week_sunday"]
        i = int(lr["origin_sequence_index"])
        rs = events.get(w, {})
        preds = [rs.get(i + j) for j in range(depth)]
        target = rs.get(i + depth)
        nxt = rs.get(i + depth + 1)
        if any(x is None for x in preds) or target is None:
            continue
        y = target_vector(target)
        block = FOLD_BLOCK.get(str(lr.get("fold")))
        if y is None or block is None:
            continue
        rows.append({
            "id": f"{w}|{lr['origin_event_id']}|D{depth}",
            "week": w,
            "block": block,
            "preds": preds,
            "target": target,
            "next": nxt,
            "y": y,
        })
    return rows


def feature_pair(case, depth, mode, h, cache):
    preds = case["preds"]
    target = case["target"]
    nxt = case["next"]
    w = case["week"]

    def snap(e, hh):
        key = (w, int(e["sequence_index"]), int(hh))
        if key not in cache["snap"]:
            cache["snap"][key] = snapshot(cache["times"][w], cache["prices"][w], e, hh)
        return cache["snap"][key]

    if mode == "prior":
        tt = event_t0(target)
        parts = []
        for e in preds:
            c = event_confirm(e)
            if c is None or c + h > tt:
                return None
            s = snap(e, h)
            if s is None:
                return None
            parts.append(np.r_[static_features(e), s])
        long = np.concatenate(parts)
        short = np.concatenate(parts[1:]) if depth > 1 else np.empty(0)
        return long, short

    tc = event_confirm(target)
    if tc is None:
        return None
    tstatic = static_features(target)

    if mode == "detect":
        parts = []
        for e in preds:
            c = event_confirm(e)
            if c is None or c > tc:
                return None
            parts.append(static_features(e))
        long = np.concatenate(parts + [tstatic])
        short = np.concatenate((parts[1:] if depth > 1 else []) + [tstatic])
        return long, short

    if mode == "post":
        if nxt is None or tc + h >= event_t0(nxt):
            return None
        ts = snap(target, h)
        if ts is None:
            return None
        parts = []
        for e in preds:
            c = event_confirm(e)
            if c is None:
                return None
            s = snap(e, h)
            if s is None:
                return None
            parts.append(np.r_[static_features(e), s])
        tpart = np.r_[tstatic, ts]
        long = np.concatenate(parts + [tpart])
        short = np.concatenate((parts[1:] if depth > 1 else []) + [tpart])
        return long, short

    raise ValueError(mode)


def dataset(cases, depth, mode, h, cache, which):
    xs, ys, ids, weeks = [], [], [], []
    for c in cases:
        fp = feature_pair(c, depth, mode, h, cache)
        if fp is None:
            continue
        x = fp[0] if which == "long" else fp[1]
        xs.append(x)
        ys.append(c["y"])
        ids.append(c["id"])
        weeks.append(c["week"])
    if not ys:
        return np.empty((0, 0)), np.empty((0, 22)), [], []
    X = np.vstack(xs) if xs[0].size else np.empty((len(xs), 0))
    return X, np.vstack(ys), ids, weeks


def split_cases(cases, blocks):
    return [c for c in cases if c["block"] in blocks]


def standardize(Xtr, Ytr, Xte):
    ym = Ytr.mean(0)
    ys = Ytr.std(0)
    ys[ys < 1e-9] = 1.0
    Yn = (Ytr - ym) / ys
    if Xtr.shape[1]:
        xm = Xtr.mean(0)
        xs = Xtr.std(0)
        xs[xs < 1e-9] = 1.0
        return (Xtr - xm) / xs, Yn, (Xte - xm) / xs, ym, ys
    return Xtr, Yn, Xte, ym, ys


def fit_model(name, param, X, Y):
    if X.shape[1] == 0:
        return None
    if name == "ridge":
        m = Ridge(alpha=float(param))
    elif name == "extra_trees":
        m = ExtraTreesRegressor(
            n_estimators=80,
            min_samples_leaf=int(param),
            max_features=1.0,
            random_state=SEED,
            n_jobs=-1,
        )
    else:
        m = KNeighborsRegressor(
            n_neighbors=min(int(param), len(X)),
            weights="distance",
            n_jobs=-1,
        )
    m.fit(X, Y)
    return m


def tuned_param(name, fitset, tuneset, depth, mode, h, cache, which):
    Xf, Yf, _, _ = dataset(fitset, depth, mode, h, cache, which)
    Xt, Yt, _, _ = dataset(tuneset, depth, mode, h, cache, which)
    if not len(Yf) or not len(Yt):
        return None
    best = None
    for p in GRIDS[name]:
        A, B, C, ym, ys = standardize(Xf, Yf, Xt)
        if A.shape[1] == 0:
            pred = np.zeros((len(C), B.shape[1]))
        else:
            pred = fit_model(name, p, A, B).predict(C)
        loss = float(np.mean(((Yt - ym) / ys - pred) ** 2))
        z = (loss, float(p), p)
        if best is None or z[:2] < best[:2]:
            best = z
    return None if best is None else best[2]


def score_block(name, param, trainset, testset, depth, mode, h, cache, which):
    Xtr, Ytr, _, _ = dataset(trainset, depth, mode, h, cache, which)
    Xte, Yte, ids, weeks = dataset(testset, depth, mode, h, cache, which)
    if not len(Ytr) or not len(Yte):
        return None
    A, B, C, ym, ys = standardize(Xtr, Ytr, Xte)
    if A.shape[1] == 0:
        pred = np.zeros((len(C), B.shape[1]))
    else:
        pred = fit_model(name, param, A, B).predict(C)
    loss = np.mean((((Yte - ym) / ys) - pred) ** 2, axis=1)
    return {"loss": loss, "ids": ids, "weeks": weeks, "mse": float(loss.mean()), "n": len(loss)}


def paired_eval(name, cases, depth, mode, h, cache):
    fitset = split_cases(cases, ("discovery_fit",))
    tuneset = split_cases(cases, ("discovery_tune",))
    disc = fitset + tuneset
    pl = tuned_param(name, fitset, tuneset, depth, mode, h, cache, "long")
    ps = tuned_param(name, fitset, tuneset, depth, mode, h, cache, "short")
    out = {"params": {"long": pl, "short": ps}, "blocks": {}}
    if pl is None or ps is None:
        return out
    for b in ("validation", "confirmation", "held"):
        te = split_cases(cases, (b,))
        L = score_block(name, pl, disc, te, depth, mode, h, cache, "long")
        S = score_block(name, ps, disc, te, depth, mode, h, cache, "short")
        if L is None or S is None or L["ids"] != S["ids"]:
            out["blocks"][b] = {"n": 0, "gain_mean": None}
            continue
        g = S["loss"] - L["loss"]
        pw = defaultdict(list)
        for x, w in zip(g, L["weeks"]):
            pw[w].append(float(x))
        out["blocks"][b] = {
            "n": int(len(g)),
            "gain_mean": float(g.mean()),
            "gain_median": float(np.median(g)),
            "gain_positive_rate": float(np.mean(g > 0)),
            "positive_week_fraction": (
                float(np.mean([np.mean(v) > 0 for v in pw.values()])) if pw else None
            ),
            "per_week_gain_mean": {w: float(np.mean(v)) for w, v in sorted(pw.items())},
        }
    return out


def model_pass(z, depth):
    for b in ("validation", "confirmation"):
        q = z["blocks"].get(b, {})
        if q.get("n", 0) < MIN_SUPPORT[depth][b]:
            return False
        if not (q.get("gain_mean") is not None and q["gain_mean"] > 0):
            return False
        if q.get("positive_week_fraction") is not None and q["positive_week_fraction"] < 0.5:
            return False
    h = z["blocks"].get("held", {})
    if h.get("n", 0) >= MIN_SUPPORT[depth]["held"]:
        if not (h.get("gain_mean") is not None and h["gain_mean"] >= 0):
            return False
    return True


def evaluate_point(cases, depth, mode, h, cache):
    rec = {"mode": mode, "H_seconds": h, "models": {}}
    passes = 0
    for m in MODELS:
        z = paired_eval(m, cases, depth, mode, h, cache)
        ok = model_pass(z, depth)
        z["passes_gate"] = ok
        rec["models"][m] = z
        passes += int(ok)
    rec["models_passing"] = passes
    rec["validated"] = passes >= 2
    return rec


def sparse_report(cases, depth):
    out = []
    for c in cases:
        target = c["target"]
        tc = event_confirm(target)
        prior = []
        post = []
        for h in HGRID:
            if all(
                event_confirm(e) is not None and event_confirm(e) + h <= event_t0(target)
                for e in c["preds"]
            ):
                prior.append(h)
            if c["next"] is not None and tc is not None and tc + h < event_t0(c["next"]):
                post.append(h)
        out.append({
            "id": c["id"],
            "week": c["week"],
            "block": c["block"],
            "prior_eligible_H": prior,
            "target_detector_confirm_idx": tc,
            "post_alive_H": post,
        })
    return {
        "status": "LOW_SUPPORT_PRESERVED_NO_UNIVERSAL_PREDICTABILITY_GATE",
        "depth": depth,
        "n": len(cases),
        "cases": out,
    }


def run_depth(depth, a):
    events = load_events(a.base, a.held)
    lineage = load_lineage(a.base_lineage, a.held_lineage)
    cases = cases_for_depth(events, lineage, depth)
    weeks = sorted({c["week"] for c in cases})
    cache = {"times": {}, "prices": {}, "snap": {}}
    for w in weeks:
        cache["times"][w], cache["prices"][w] = load_week_prices(a.raw_dir, w)
    counts = {b: sum(c["block"] == b for c in cases) for b in set(FOLD_BLOCK.values())}

    if depth >= 4:
        return {
            "status": "AGENT_COMPLETE_LOW_SUPPORT_PRESERVED",
            "depth": depth,
            "population_n": len(cases),
            "block_counts": counts,
            "H_grid": list(HGRID),
            "sparse": sparse_report(cases, depth),
            "promotion_performed": False,
        }

    tested = []
    winner = None

    for h in HGRID:
        p = evaluate_point(cases, depth, "prior", h, cache)
        tested.append(p)
        if p["validated"]:
            winner = {"timing_class": "PRIOR", "H_seconds": h, "point": p}
            break
        ns = [z["blocks"].get("validation", {}).get("n", 0) for z in p["models"].values()]
        if max(ns or [0]) < MIN_SUPPORT[depth]["validation"]:
            break

    if winner is None:
        p = evaluate_point(cases, depth, "detect", 0, cache)
        tested.append(p)
        if p["validated"]:
            winner = {"timing_class": "AT_DETECTION", "H_seconds": 0, "point": p}

    if winner is None:
        for h in HGRID:
            p = evaluate_point(cases, depth, "post", h, cache)
            tested.append(p)
            if p["validated"]:
                winner = {"timing_class": "POST_DETECTION", "H_seconds": h, "point": p}
                break
            ns = [z["blocks"].get("validation", {}).get("n", 0) for z in p["models"].values()]
            if max(ns or [0]) < MIN_SUPPORT[depth]["validation"]:
                break

    return {
        "status": "AGENT_COMPLETE",
        "depth": depth,
        "population_n": len(cases),
        "block_counts": counts,
        "H_grid": list(HGRID),
        "earliest_validated": winner,
        "tested_points": tested,
        "method": "PAIRED_D_VS_D_MINUS_1_SAME_ELIGIBLE_TARGETS; DISCOVERY_ONLY_INNER_TUNING; VALIDATION_CONFIRMATION_HELD_NO_RETUNE",
        "target": "FROZEN_TARGET_FULL_BEHAVIOR_VECTOR_NEXT_SAME_PLUS_5_10_20_30_60_120_300_DISP_MFE_MAE",
        "prior_rule": "all required predecessor detector confirmations + H <= target t0",
        "at_detection_rule": "target detector confirmation is causal +0",
        "post_rule": "target remains alive; use target partial H plus D-history partial H; compare against target-partial plus D-1 history",
        "promotion_performed": False,
        "protected_mutations": {
            "detector": False,
            "canonical_rows": False,
            "phase1": False,
            "phase2": False,
            "runway_clock": False,
            "permanent_frankie": False,
            "frankie_1": False,
            "spawn_py": False,
            "ssos_play": False,
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depths", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--held", required=True)
    ap.add_argument("--base-lineage", required=True)
    ap.add_argument("--held-lineage", required=True)
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    depths = [int(x) for x in a.depths.split(",")]
    result = {
        "status": "D1_D5_PREDICTABILITY_AGENT_COMPLETE",
        "agent_depths": depths,
        "H_grid": list(HGRID),
        "results": {f"D{d}": run_depth(d, a) for d in depths},
        "promotion_performed": False,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": result["status"],
        "depths": depths,
        "earliest": {
            k: (
                None if v.get("earliest_validated") is None else {
                    "timing_class": v["earliest_validated"]["timing_class"],
                    "H_seconds": v["earliest_validated"]["H_seconds"],
                }
            )
            for k, v in result["results"].items()
        },
    }, indent=2))


if __name__ == "__main__":
    main()
