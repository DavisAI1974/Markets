#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

TICK = 0.001
P = "persistent_exhaustion"
O = "collapsed_opposite_flow_reversal"
X = "collapsed_sparse_indeterminate"
EXPECTED_POX = 3429
EXPECTED_FLIP = 1444
EXPECTED_SAME = 1985
HGRID = (0, 1, 2, 3, 4, 5, 10, 15, 20, 30, 45, 60)
HOLDS = (5, 10, 20, 30, 60)
COSTS = (0.5, 1.0, 2.0)


def finite(v):
    try:
        return math.isfinite(float(v))
    except Exception:
        return False


def mean(xs):
    return float(np.mean(xs)) if xs else None


def median(xs):
    return float(np.median(xs)) if xs else None


def q(xs, p):
    return float(np.quantile(xs, p)) if xs else None


def block_for(week, base_weeks):
    if week == "20260329":
        return "held"
    i = base_weeks.index(week)
    if i < 12:
        return "fit"
    if i < 18:
        return "tune"
    if i < 36:
        return "era13"
    if i < 48:
        return "era45"
    return "conf"


def load_events(base_path, held_path):
    by = defaultdict(list)
    for path in (base_path, held_path):
        with gzip.open(path, "rt") as f:
            for line in f:
                r = json.loads(line)
                ep = r.get("dynamic_endpoint") or {}
                hs = ((r.get("outcome") or {}).get("post_endpoint_price") or {}).get("horizons", {})
                H = {}
                for h in (5, 10, 20, 30, 60, 120, 300):
                    z = hs.get(str(h), {})
                    v = z.get("signed_displacement_ticks")
                    H[h] = None if z.get("censored", False) or not finite(v) else float(v)
                by[str(r["week_sunday"])].append({
                    "event_id": str(r["event_id"]),
                    "week": str(r["week_sunday"]),
                    "seq": int(r["sequence_index"]),
                    "t0": int(r["t0_idx"]),
                    "state": str(r["seed_state"]),
                    "pol": int(r["polarity"]),
                    "confirm": None if ep.get("causal_confirmation_idx") is None else int(ep["causal_confirmation_idx"]),
                    "onset": None if ep.get("structural_onset_idx") is None else int(ep["structural_onset_idx"]),
                    "H": H,
                })
    for w in by:
        by[w].sort(key=lambda e: e["seq"])
    base_weeks = sorted(w for w in by if w != "20260329")
    if len(base_weeks) != 54:
        raise RuntimeError(f"expected 54 base weeks, got {len(base_weeks)}")
    return dict(by), base_weeks


def state_available(e):
    if e["confirm"] is None:
        return None
    # Frozen Phase-2 predecessor-state availability wall.
    return int(e["confirm"]) + 60


def day_from_name(p):
    s = Path(p).name
    for token in s.split("_"):
        if len(token) == 8 and token.isdigit():
            return token
    raise RuntimeError(f"cannot parse raw day: {p}")


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
                if px > 0:
                    pts.append((di * 86400.0 + (ts % 86400.0), px))
    pts.sort(key=lambda z: z[0])
    if not pts:
        return np.empty(0), np.empty(0)
    return np.asarray([z[0] for z in pts], float), np.asarray([z[1] for z in pts], float)


def px_before(times, prices, t):
    j = int(np.searchsorted(times, float(t), side="right")) - 1
    if j < 0:
        return None
    return float(prices[j])


def px_at_after(times, prices, t):
    j = int(np.searchsorted(times, float(t), side="left"))
    if j >= len(times):
        return None, None, None
    return float(times[j]), float(prices[j]), j


def raw_context(times, prices, signal, orient):
    p0 = px_before(times, prices, signal)
    if p0 is None:
        return None
    vals = []
    for lag in (1, 2, 5, 10, 20, 30, 60):
        p = px_before(times, prices, signal - lag)
        if p is None:
            return None
        vals.append(math.asinh(float(orient) * (p0 - p) / TICK))
    j0 = int(np.searchsorted(times, float(signal - 30), side="left"))
    j1 = int(np.searchsorted(times, float(signal), side="right"))
    seg = prices[j0:j1]
    if len(seg) < 2:
        vals += [0.0, 0.0]
    else:
        dif = np.diff(seg) / TICK
        vals += [math.asinh(float(np.std(dif))), math.asinh(float(np.max(seg) - np.min(seg)) / TICK)]
    return vals


def enumerate_cases(by, base_weeks):
    pox = []
    candidates = []
    for w, rs in sorted(by.items()):
        b = block_for(w, base_weeks)
        for i in range(2, len(rs) - 1):
            a, o, cur, succ = rs[i - 2], rs[i - 1], rs[i], rs[i + 1]
            if a["state"] == P and o["state"] == O:
                candidates.append({"week": w, "block": b, "p": a, "o": o, "cur": cur, "succ": succ, "y": int(cur["state"] == X)})
            if a["state"] == P and o["state"] == O and cur["state"] == X:
                branch = "SAME" if succ["pol"] == cur["pol"] else "FLIP"
                pox.append({"id": f"{w}|{cur['event_id']}", "week": w, "block": b, "p": a, "o": o, "x": cur, "succ": succ, "branch": branch})
    same = sum(r["branch"] == "SAME" for r in pox)
    flip = sum(r["branch"] == "FLIP" for r in pox)
    if (len(pox), flip, same) != (EXPECTED_POX, EXPECTED_FLIP, EXPECTED_SAME):
        raise RuntimeError(f"preserve-all POX invariant failed: observed total/flip/same={(len(pox), flip, same)} expected={(EXPECTED_POX, EXPECTED_FLIP, EXPECTED_SAME)}")
    return pox, candidates


def signal_and_features(case, mode, h, cache):
    p, o, cur, succ = case["p"], case["o"], case["cur"], case["succ"]
    pa, oa = state_available(p), state_available(o)
    if pa is None or oa is None:
        return None
    times, prices = cache[case["week"]]
    if mode == "prior":
        signal = max(pa, oa)
        if signal >= cur["t0"]:
            return None
        ctx = raw_context(times, prices, signal, o["pol"])
        if ctx is None:
            return None
        feats = [
            float(p["pol"]), float(o["pol"]), float(p["pol"] == o["pol"]),
            math.asinh(max(0, o["t0"] - p["t0"])),
            math.asinh(max(0, signal - o["t0"])),
            math.asinh(max(0, oa - o["t0"])),
            math.asinh(max(0, pa - p["t0"])),
        ] + ctx
        return int(signal), np.asarray(feats, float)
    if cur["confirm"] is None:
        return None
    signal = max(pa, oa, int(cur["confirm"]) + int(h))
    if signal >= succ["t0"]:
        return None
    ctx = raw_context(times, prices, signal, cur["pol"])
    if ctx is None:
        return None
    feats = [
        float(p["pol"]), float(o["pol"]), float(cur["pol"]),
        float(p["pol"] == o["pol"]), float(cur["pol"] == o["pol"]),
        math.asinh(max(0, o["t0"] - p["t0"])),
        math.asinh(max(0, cur["t0"] - o["t0"])),
        math.asinh(max(0, int(cur["confirm"]) - cur["t0"])),
        math.asinh(max(0, signal - int(cur["confirm"]))),
    ] + ctx
    return int(signal), np.asarray(feats, float)


def branch_signal_and_features(row, h, cache):
    p, o, cur, succ = row["p"], row["o"], row["x"], row["succ"]
    pa, oa = state_available(p), state_available(o)
    if pa is None or oa is None or cur["confirm"] is None:
        return None
    signal = max(pa, oa, int(cur["confirm"]) + int(h))
    if signal >= succ["t0"]:
        return None
    times, prices = cache[row["week"]]
    ctx = raw_context(times, prices, signal, cur["pol"])
    if ctx is None:
        return None
    feats = [
        float(p["pol"]), float(o["pol"]), float(cur["pol"]),
        float(p["pol"] == o["pol"]), float(cur["pol"] == o["pol"]),
        math.asinh(max(0, o["t0"] - p["t0"])),
        math.asinh(max(0, cur["t0"] - o["t0"])),
        math.asinh(max(0, int(cur["confirm"]) - cur["t0"])),
        math.asinh(max(0, signal - int(cur["confirm"]))),
        math.asinh(max(0, succ["t0"] - signal)),
    ] + ctx
    return int(signal), np.asarray(feats, float)


def fit_ensemble(X, y):
    scaler = StandardScaler().fit(X)
    lr = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced", random_state=20260819).fit(scaler.transform(X), y)
    et = ExtraTreesClassifier(n_estimators=240, min_samples_leaf=20, max_features=0.8, class_weight="balanced", random_state=20260819, n_jobs=-1).fit(X, y)
    return scaler, lr, et


def predict_ensemble(model, X):
    scaler, lr, et = model
    return 0.5 * lr.predict_proba(scaler.transform(X))[:, 1] + 0.5 * et.predict_proba(X)[:, 1]


def metric(y, p, train_base):
    if not len(y):
        return {"n": 0}
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    y = np.asarray(y, int)
    base = np.full(len(y), min(max(float(train_base), 1e-6), 1 - 1e-6))
    out = {
        "n": int(len(y)), "positive_n": int(np.sum(y)), "positive_rate": float(np.mean(y)),
        "log_loss": float(log_loss(y, p, labels=[0, 1])), "null_log_loss": float(log_loss(y, base, labels=[0, 1])),
        "brier": float(brier_score_loss(y, p)), "null_brier": float(brier_score_loss(y, base)),
    }
    out["log_loss_gain"] = out["null_log_loss"] - out["log_loss"]
    out["brier_gain"] = out["null_brier"] - out["brier"]
    out["auc"] = float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None
    k = max(1, int(math.ceil(0.20 * len(y))))
    top = y[np.argsort(-p)[:k]]
    out["top20_positive_rate"] = float(np.mean(top))
    out["top20_lift"] = float(np.mean(top) / np.mean(y)) if np.mean(y) > 0 else None
    return out


def datasets(rows, feature_fn):
    d = defaultdict(list)
    for r in rows:
        z = feature_fn(r)
        if z is None:
            continue
        signal, feat = z
        d[r["block"]].append((r, signal, feat))
    return d


def eval_checkpoint(rows, feature_fn, label_fn):
    d = datasets(rows, feature_fn)
    train = d["fit"] + d["tune"]
    if len(train) < 50:
        return {"validated": False, "reason": "LOW_TRAIN_SUPPORT", "availability": {b: len(d[b]) for b in d}}
    Xtr = np.vstack([z[2] for z in train]); ytr = np.asarray([label_fn(z[0]) for z in train], int)
    if len(np.unique(ytr)) < 2:
        return {"validated": False, "reason": "ONE_CLASS_TRAIN"}
    model = fit_ensemble(Xtr, ytr); base = float(np.mean(ytr))
    blocks = {}
    pred_rows = []
    for b in ("fit", "tune", "era13", "era45", "conf", "held"):
        zz = d[b]
        if not zz:
            blocks[b] = {"n": 0}
            continue
        X = np.vstack([z[2] for z in zz]); y = np.asarray([label_fn(z[0]) for z in zz], int); pp = predict_ensemble(model, X)
        blocks[b] = metric(y, pp, base)
        for (r, signal, _), prob in zip(zz, pp):
            pred_rows.append((r, int(signal), float(prob), int(label_fn(r))))
    valid = True
    for b in ("era13", "era45", "conf"):
        m = blocks.get(b, {})
        if m.get("n", 0) < 30 or m.get("log_loss_gain", -1) <= 0 or m.get("brier_gain", -1) <= 0 or (m.get("auc") is not None and m["auc"] < 0.52):
            valid = False
    return {"validated": bool(valid), "train_base_rate": base, "blocks": blocks, "prediction_rows": pred_rows}


def trade_row(case, signal, cache, hold, orient=None, cap_time=None):
    times, prices = cache[case["week"]]
    if orient is None:
        cur = case.get("cur", case.get("x"))
        orient = cur["pol"]
    et, ep, ie = px_at_after(times, prices, signal)
    if et is None:
        return None
    target = float(signal + hold)
    if cap_time is not None:
        target = min(target, float(cap_time))
    xt, xp, ix = px_at_after(times, prices, target)
    if xt is None or ix < ie:
        return None
    seg = prices[ie:ix + 1]
    signed = float(orient) * (seg - ep) / TICK
    gross = float(orient) * (xp - ep) / TICK
    return {"gross": gross, "mfe": float(np.max(signed)), "mae": float(np.min(signed)), "entry_time": et, "exit_time": xt}


def summarize_trades(rows):
    if not rows:
        return {"n": 0}
    byweek = defaultdict(list)
    for r in rows:
        byweek[r["week"]].append(r["gross"] - 1.0)
    return {
        "n": len(rows), "mean_gross_ticks": mean([r["gross"] for r in rows]),
        "positive_rate_gross": float(np.mean([r["gross"] > 0 for r in rows])),
        "mean_mfe_ticks": mean([r["mfe"] for r in rows]), "mean_mae_ticks": mean([r["mae"] for r in rows]),
        "mean_net_0_5_ticks": mean([r["gross"] - 0.5 for r in rows]),
        "mean_net_1_ticks": mean([r["gross"] - 1.0 for r in rows]),
        "mean_net_2_ticks": mean([r["gross"] - 2.0 for r in rows]),
        "positive_week_rate_net1": float(np.mean([np.mean(v) > 0 for v in byweek.values()])), "weeks": len(byweek),
    }


def threshold_from_tune(pred_rows, cache):
    cands = (0.50, 0.60, 0.70, 0.80, 0.90)
    scored = []
    for th in cands:
        trades = []
        for case, signal, prob, _ in pred_rows:
            if case["block"] != "tune" or prob < th:
                continue
            z = trade_row(case, signal, cache, 30)
            if z is not None:
                z.update({"week": case["week"]}); trades.append(z)
        s = summarize_trades(trades)
        scored.append({"threshold": th, "summary": s})
    eligible = [z for z in scored if z["summary"].get("n", 0) >= 25]
    if not eligible:
        return 0.70, scored
    eligible.sort(key=lambda z: (z["summary"].get("mean_net_1_ticks") or -1e9, z["threshold"]), reverse=True)
    return float(eligible[0]["threshold"]), scored


def initial_trade_economics(pred_rows, threshold, cache):
    out = {}
    for hold in HOLDS:
        out[str(hold)] = {}
        for b in ("fit", "tune", "era13", "era45", "conf", "held"):
            tr = []
            for case, signal, prob, actual in pred_rows:
                if case["block"] != b or prob < threshold:
                    continue
                z = trade_row(case, signal, cache, hold)
                if z is None:
                    continue
                z.update({"week": case["week"], "actual_pox": actual, "prob": prob}); tr.append(z)
            s = summarize_trades(tr)
            if tr:
                s["true_pox_fraction"] = float(np.mean([r["actual_pox"] for r in tr]))
            out[str(hold)][b] = s
    return out


def persistence_checks(pox, cache):
    checks = defaultdict(list)
    for r in pox:
        x = r["x"]
        if x["H"].get(60) is not None:
            checks["canonical_onset_to_plus60_oriented_positive"].append(x["H"][60] > 0)
        if x["H"].get(5) is not None and x["H"].get(60) is not None:
            checks["canonical_plus5_to_plus60_oriented_positive"].append((x["H"][60] - x["H"][5]) >= 0)
        if x["confirm"] is not None:
            z = trade_row({"week": r["week"], "x": x}, int(x["confirm"]), cache, 60, orient=x["pol"])
            if z is not None:
                checks["raw_confirm_to_plus60_oriented_nonnegative"].append(z["gross"] >= 0)
    return {k: {"n": len(v), "rate": float(np.mean(v)) if v else None} for k, v in checks.items()}


def branch_known_lags(pox, pox_signal_map):
    vals = defaultdict(list)
    known = 0
    for r in pox:
        sc = r["succ"].get("confirm")
        sig = pox_signal_map.get(r["id"])
        if sc is None or sig is None:
            continue
        known += 1
        vals["signal_to_successor_t0"].append(r["succ"]["t0"] - sig)
        vals["signal_to_successor_confirmation"].append(sc - sig)
        vals["x_plus60_to_successor_confirmation"].append(sc - (r["x"]["onset"] + 60) if r["x"].get("onset") is not None else sc - sig)
    return {"n": known, **{k: {"median": median(v), "p10": q(v, .1), "p90": q(v, .9), "min": min(v) if v else None, "max": max(v) if v else None} for k, v in vals.items()}}


def successor_actions(pox, cache):
    actions = {}
    for hold in (30, 60):
        actions[str(hold)] = {}
        for action in ("FOLLOW_SUCCESSOR", "CONTINUE_X", "REVERSE_X"):
            actions[str(hold)][action] = {}
            for b in ("fit", "tune", "era13", "era45", "conf", "held"):
                tr = []
                for r in pox:
                    if r["block"] != b or r["succ"].get("confirm") is None:
                        continue
                    if action == "FOLLOW_SUCCESSOR": orient = r["succ"]["pol"]
                    elif action == "CONTINUE_X": orient = r["x"]["pol"]
                    else: orient = -r["x"]["pol"]
                    z = trade_row({"week": r["week"], "x": r["x"]}, int(r["succ"]["confirm"]), cache, hold, orient=orient)
                    if z is not None:
                        z.update({"week": r["week"], "branch": r["branch"]}); tr.append(z)
                s = summarize_trades(tr)
                if tr:
                    s["same_fraction"] = float(np.mean([r["branch"] == "SAME" for r in tr]))
                actions[str(hold)][action][b] = s
    return actions


def dynamic_exit_compare(pox, signal_map, cache, hold=60):
    out = {}
    for b in ("fit", "tune", "era13", "era45", "conf", "held"):
        diffs = []
        for r in pox:
            if r["block"] != b:
                continue
            sig = signal_map.get(r["id"]); sc = r["succ"].get("confirm")
            if sig is None or sc is None or sc <= sig or sc >= sig + hold:
                continue
            fixed = trade_row({"week": r["week"], "x": r["x"]}, sig, cache, hold, orient=r["x"]["pol"])
            dyn = trade_row({"week": r["week"], "x": r["x"]}, sig, cache, hold, orient=r["x"]["pol"], cap_time=sc)
            if fixed and dyn:
                diffs.append(dyn["gross"] - fixed["gross"])
        out[b] = {"n": len(diffs), "mean_improvement_ticks": mean(diffs), "positive_improvement_rate": float(np.mean([d > 0 for d in diffs])) if diffs else None}
    return out


def delayed_same_watch(pox, cache):
    out = {}
    for b in ("fit", "tune", "era13", "era45", "conf", "held"):
        rows = []
        for r in pox:
            if r["block"] != b or r["branch"] != "SAME" or r["x"].get("onset") is None:
                continue
            signal = int(r["x"]["onset"]) + 60
            for hold in (60, 240):
                z = trade_row({"week": r["week"], "x": r["x"]}, signal, cache, hold, orient=r["x"]["pol"])
                if z is not None:
                    rows.append({"hold": hold, "week": r["week"], **z})
        out[b] = {str(h): summarize_trades([z for z in rows if z["hold"] == h]) for h in (60, 240)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--held", required=True, type=Path)
    ap.add_argument("--raw-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--ledger", required=True, type=Path)
    args = ap.parse_args()

    by, base_weeks = load_events(args.base, args.held)
    pox, candidates = enumerate_cases(by, base_weeks)
    weeks = sorted(by)
    cache = {}
    for w in weeks:
        cache[w] = load_week_prices(args.raw_dir, w)
        if len(cache[w][0]) == 0:
            raise RuntimeError(f"missing authoritative raw tape for week={w}")

    pox_tests = []
    prior = eval_checkpoint(candidates, lambda r: signal_and_features(r, "prior", 0, cache), lambda r: r["y"])
    pox_tests.append({"timing_class": "PRIOR_PO", "H": None, **{k:v for k,v in prior.items() if k != "prediction_rows"}})
    pox_pred_rows_by_key = {("prior", 0): prior.get("prediction_rows", [])}
    for h in HGRID:
        z = eval_checkpoint(candidates, lambda r, hh=h: signal_and_features(r, "post", hh, cache), lambda r: r["y"])
        pox_tests.append({"timing_class": "X_CONFIRM_PLUS_H", "H": h, **{k:v for k,v in z.items() if k != "prediction_rows"}})
        pox_pred_rows_by_key[("post", h)] = z.get("prediction_rows", [])

    earliest = None
    earliest_rows = []
    if prior.get("validated"):
        earliest = {"timing_class": "PRIOR_PO", "H": None}
        earliest_rows = prior.get("prediction_rows", [])
    else:
        for h in HGRID:
            rec = next(x for x in pox_tests if x["timing_class"] == "X_CONFIRM_PLUS_H" and x["H"] == h)
            if rec.get("validated"):
                earliest = {"timing_class": "X_CONFIRM_PLUS_H", "H": h}
                earliest_rows = pox_pred_rows_by_key[("post", h)]
                break

    threshold = None
    threshold_scan = []
    trade = {"status": "NO_VALIDATED_POX_SIGNAL_NO_TRADE_MANUFACTURED"}
    signal_map = {}
    if earliest is not None:
        threshold, threshold_scan = threshold_from_tune(earliest_rows, cache)
        trade = {
            "status": "POX_INITIAL_CONTINUATION_TRADE_RESEARCH_COMPLETE",
            "discovery_selected_probability_threshold": threshold,
            "threshold_scan_tune_only": threshold_scan,
            "fixed_hold_economics": initial_trade_economics(earliest_rows, threshold, cache),
        }
        for case, signal, prob, actual in earliest_rows:
            if actual == 1:
                cur = case["cur"]
                signal_map[f"{case['week']}|{cur['event_id']}"] = int(signal)

    branch_tests = []
    branch_rows_by_h = {}
    for h in HGRID:
        z = eval_checkpoint(pox, lambda r, hh=h: branch_signal_and_features(r, hh, cache), lambda r: int(r["branch"] == "SAME"))
        branch_tests.append({"H": h, **{k:v for k,v in z.items() if k != "prediction_rows"}})
        branch_rows_by_h[h] = z.get("prediction_rows", [])
    branch_earliest = next(({"H": z["H"]} for z in branch_tests if z.get("validated")), None)

    branch_known = branch_known_lags(pox, signal_map)
    persistence = persistence_checks(pox, cache)
    actions = successor_actions(pox, cache)
    dyn_exit = dynamic_exit_compare(pox, signal_map, cache) if signal_map else {"status": "NO_VALIDATED_INITIAL_SIGNAL"}
    delayed = delayed_same_watch(pox, cache)

    with gzip.open(args.ledger, "wt") as f:
        for r in pox:
            x = r["x"]; succ = r["succ"]
            row = {
                "id": r["id"], "week": r["week"], "block": r["block"], "branch": r["branch"],
                "p_event_id": r["p"]["event_id"], "o_event_id": r["o"]["event_id"], "x_event_id": x["event_id"], "successor_event_id": succ["event_id"],
                "x_polarity": x["pol"], "successor_polarity": succ["pol"], "x_t0": x["t0"], "x_confirm": x["confirm"], "x_onset": x["onset"],
                "successor_t0": succ["t0"], "successor_confirm": succ["confirm"], "earliest_pox_signal": signal_map.get(r["id"]),
                "canonical_x_return_plus5_to_plus60": None if x["H"].get(5) is None or x["H"].get(60) is None else x["H"][60] - x["H"][5],
                "preserved": True,
            }
            f.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    result = {
        "status": "POX_FOCUSED_PREDICT_TRADE_COMPLETE",
        "population": {"total": len(pox), "flip": EXPECTED_FLIP, "same": EXPECTED_SAME, "preserved_all": True, "older_679_is_subset_not_master": True},
        "candidate_universe_after_PO": len(candidates),
        "persistence_checks": persistence,
        "pox_identity_prediction": {"earliest_validated": earliest, "tested": pox_tests},
        "initial_continuation_trade": trade,
        "branch_prediction": {"earliest_validated": branch_earliest, "tested": branch_tests},
        "branch_observational_knowability": {"rule": "SUCCESSOR_FROZEN_DETECTOR_CAUSAL_CONFIRMATION", "lags_from_earliest_pox_signal": branch_known},
        "successor_state_actions": actions,
        "dynamic_exit_at_successor_confirmation_vs_fixed60": dyn_exit,
        "same_branch_delayed_reexpression_watch": delayed,
        "D0_D5_incremental_crosswalk": "DEFERRED_UNTIL_INDEPENDENT_RESULTS_FROZEN_AND_OPENED_AFTER_POX_RULE_FREEZE",
        "failure_policy": "FLAG_AND_DECOMPOSE_NOT_AUTO_KILL",
        "promotion_performed": False,
        "protected_mutations": {"detector": False, "canonical_rows": False, "phase1": False, "phase2": False, "runway_clock": False, "permanent_frankie": False, "frankie_1": False, "spawn_py": False, "ssos_play": False},
    }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "population": result["population"], "earliest_pox": earliest, "earliest_branch": branch_earliest, "persistence": persistence}, indent=2))


if __name__ == "__main__":
    main()
