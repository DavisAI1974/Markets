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
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.neighbors import KNeighborsClassifier

TICK = 0.001
HGRID = tuple([1, 2, 3, 4, 5, 10, 15] + list(range(20, 3601, 5)))
MODELS = ("logistic", "extra_trees", "knn")
GRIDS = {"logistic": (0.01, 0.1, 1.0, 10.0), "extra_trees": (10, 40, 100), "knn": (20, 80, 160)}
SEED = 20260819
FOLD_BLOCK = {"era1": "discovery_fit", "era2": "discovery_fit", "era3": "discovery_tune", "era4": "validation", "era5": "validation", "untouched_confirmation": "confirmation", "held_insert_era4": "held"}
EXPECTED_EXACT = {0: 135860, 1: 18837, 2: 1592, 3: 124, 4: 8, 5: 1}
MIN_COUNTS = {1: {"validation_pos": 200, "validation_neg": 1000, "confirmation_pos": 100, "confirmation_neg": 500}, 2: {"validation_pos": 30, "validation_neg": 300, "confirmation_pos": 15, "confirmation_neg": 200}, 3: {"validation_pos": 10, "validation_neg": 50, "confirmation_pos": 5, "confirmation_neg": 50}}


def load_events(*paths):
    by = defaultdict(dict)
    for p in paths:
        with gzip.open(p, "rt") as f:
            for line in f:
                r = json.loads(line)
                by[r["week_sunday"]][int(r["sequence_index"])] = {"event_id": r["event_id"], "week_sunday": r["week_sunday"], "sequence_index": int(r["sequence_index"]), "t0_idx": int(r["t0_idx"]), "polarity": int(r["polarity"]), "confirm_idx": (r.get("dynamic_endpoint") or {}).get("causal_confirmation_idx")}
    return by


def load_lineage(*paths):
    out = []
    for p in paths:
        with gzip.open(p, "rt") as f:
            for line in f:
                r = json.loads(line); block = FOLD_BLOCK.get(str(r.get("fold")))
                if block is None: continue
                out.append({"week": r["week_sunday"], "origin_event_id": r["origin_event_id"], "origin_sequence_index": int(r["origin_sequence_index"]), "depth": int(r.get("all_model_consecutive_positive_depth", 0)), "block": block})
    return out


def day_from_name(p):
    m = re.search(r"(20\d{6})", Path(p).name)
    if not m: raise SystemExit(f"cannot parse raw day from {p}")
    return m.group(1)


def load_week_prices(raw_dir, week):
    sun = datetime.strptime(week, "%Y%m%d"); pts = []
    for p in sorted(Path(raw_dir).glob("NG_*.jsonl.gz")):
        d = day_from_name(p); di = (datetime.strptime(d, "%Y%m%d") - sun).days
        if di < 0 or di > 5: continue
        with gzip.open(p, "rt") as f:
            for line in f:
                r = json.loads(line)
                if r.get("action") != "T": continue
                try: px = float(r.get("price", 0) or 0); ts = float(r.get("ts_event", r.get("ts")))
                except Exception: continue
                if px > 0: pts.append((di * 86400.0 + (ts % 86400.0), px))
    pts.sort(key=lambda z: z[0])
    if not pts: return np.empty(0), np.empty(0)
    return np.asarray([x[0] for x in pts], float), np.asarray([x[1] for x in pts], float)


def event_confirm(e):
    v = e.get("confirm_idx"); return None if v is None else int(v)


def snapshot(times, prices, e, h):
    c = event_confirm(e)
    if c is None or h <= 0: return None
    j = int(np.searchsorted(times, float(c), side="left")); k = int(np.searchsorted(times, float(c + h), side="right")) - 1
    if j >= len(times) or k < j: return None
    p0 = float(prices[j]); p1 = float(prices[k]); seg = prices[j:k + 1]; pol = float(e["polarity"])
    signed = pol * (p1 - p0) / TICK
    if pol > 0: mfe = (float(np.max(seg)) - p0) / TICK; mae = (float(np.min(seg)) - p0) / TICK
    else: mfe = (p0 - float(np.min(seg))) / TICK; mae = (p0 - float(np.max(seg))) / TICK
    return np.asarray([pol, math.asinh(signed), math.asinh(mfe), math.asinh(mae), math.asinh(mfe - mae)], float)


def birth_cases(events, lineage, stage):
    out, censored = [], []
    for lr in lineage:
        q = lr["depth"]
        if q < stage - 1: continue
        w = lr["week"]; i = lr["origin_sequence_index"]; rs = events.get(w, {})
        preds = [rs.get(i + j) for j in range(stage)]; target = rs.get(i + stage)
        if any(e is None for e in preds) or target is None:
            censored.append({"week": w, "origin_event_id": lr["origin_event_id"], "depth": q, "reason": "FROZEN_WEEK_END_OR_CANONICAL_TARGET_UNAVAILABLE"}); continue
        out.append({"id": f"{w}|{lr['origin_event_id']}|BIRTH_D{stage}", "week": w, "block": lr["block"], "final_depth": q, "y": 1 if q >= stage else 0, "preds": preds, "target": target, "next_after_target": rs.get(i + stage + 1)})
    return out, censored


def cache_snapshot(cache, week, e, h):
    key = (week, e["sequence_index"], int(h))
    if key not in cache["snap"]: cache["snap"][key] = snapshot(cache["times"][week], cache["prices"][week], e, h)
    return cache["snap"][key]


def feature_pair(case, stage, mode, h, cache):
    preds = case["preds"]; target = case["target"]; w = case["week"]
    if mode == "prior":
        tt = int(target["t0_idx"]); parts = []
        for e in preds:
            c = event_confirm(e)
            if c is None or c + h > tt: return None
            s = cache_snapshot(cache, w, e, h)
            if s is None: return None
            parts.append(s)
        long = np.concatenate(parts); short = np.concatenate(parts[1:]) if stage > 1 else np.empty(0)
        lead = int(tt - max(event_confirm(e) + h for e in preds)); return long, short, lead
    tc = event_confirm(target)
    if tc is None: return None
    if mode == "detect":
        parts = [np.asarray([float(e["polarity"])]) for e in preds]; tpart = np.asarray([float(target["polarity"])])
        return np.concatenate(parts + [tpart]), np.concatenate((parts[1:] if stage > 1 else []) + [tpart]), 0
    if mode == "post":
        nxt = case.get("next_after_target")
        if nxt is None or tc + h >= int(nxt["t0_idx"]): return None
        tpart = cache_snapshot(cache, w, target, h)
        if tpart is None: return None
        parts = []
        for e in preds:
            s = cache_snapshot(cache, w, e, h)
            if s is None: return None
            parts.append(s)
        return np.concatenate(parts + [tpart]), np.concatenate((parts[1:] if stage > 1 else []) + [tpart]), 0
    raise ValueError(mode)


def dataset(cases, stage, mode, h, cache, which):
    xs, ys, ids, weeks, leads = [], [], [], [], []
    for c in cases:
        fp = feature_pair(c, stage, mode, h, cache)
        if fp is None: continue
        xs.append(fp[0] if which == "long" else fp[1]); ys.append(c["y"]); ids.append(c["id"]); weeks.append(c["week"]); leads.append(fp[2])
    if not ys: return np.empty((0, 0)), np.empty(0, int), [], [], []
    X = np.vstack(xs) if xs[0].size else np.empty((len(xs), 0)); return X, np.asarray(ys, int), ids, weeks, leads


def split_cases(cases, blocks): return [c for c in cases if c["block"] in blocks]


def scale(Xtr, Xte):
    if Xtr.shape[1] == 0: return Xtr, Xte
    xm = Xtr.mean(0); xs = Xtr.std(0); xs[xs < 1e-9] = 1.0
    return (Xtr - xm) / xs, (Xte - xm) / xs


def fit_model(name, param, X, y):
    if X.shape[1] == 0: return None
    if name == "logistic": m = LogisticRegression(C=float(param), max_iter=1000, random_state=SEED)
    elif name == "extra_trees": m = ExtraTreesClassifier(n_estimators=120, min_samples_leaf=int(param), max_features=1.0, random_state=SEED, n_jobs=-1)
    else: m = KNeighborsClassifier(n_neighbors=min(int(param), len(X)), weights="distance", n_jobs=-1)
    m.fit(X, y); return m


def predict_probability(name, param, Xtr, ytr, Xte):
    base = float(np.mean(ytr)) if len(ytr) else 0.0
    if Xtr.shape[1] == 0: return np.full(len(Xte), base, float)
    A, C = scale(Xtr, Xte); m = fit_model(name, param, A, ytr)
    return np.clip(m.predict_proba(C)[:, 1], 1e-6, 1 - 1e-6)


def tune_param(name, fitset, tuneset, stage, mode, h, cache, which):
    Xf, yf, _, _, _ = dataset(fitset, stage, mode, h, cache, which); Xt, yt, _, _, _ = dataset(tuneset, stage, mode, h, cache, which)
    if len(np.unique(yf)) < 2 or len(np.unique(yt)) < 2: return None
    best = None
    for p in GRIDS[name]:
        pred = predict_probability(name, p, Xf, yf, Xt); loss = float(log_loss(yt, pred, labels=[0, 1])); z = (loss, float(p), p)
        if best is None or z[:2] < best[:2]: best = z
    return None if best is None else best[2]


def metrics(y, p, null_p, weeks):
    if not len(y): return {"n": 0}
    p = np.clip(p, 1e-6, 1 - 1e-6); np0 = np.clip(np.full(len(y), null_p, float), 1e-6, 1 - 1e-6)
    out = {"n": int(len(y)), "positive_n": int(np.sum(y == 1)), "negative_n": int(np.sum(y == 0)), "positive_rate": float(np.mean(y)), "log_loss": float(log_loss(y, p, labels=[0, 1])), "null_log_loss": float(log_loss(y, np0, labels=[0, 1])), "brier": float(brier_score_loss(y, p)), "null_brier": float(brier_score_loss(y, np0))}
    out["log_loss_gain_vs_null"] = out["null_log_loss"] - out["log_loss"]; out["brier_gain_vs_null"] = out["null_brier"] - out["brier"]
    if len(np.unique(y)) == 2: out["roc_auc"] = float(roc_auc_score(y, p)); out["average_precision"] = float(average_precision_score(y, p))
    else: out["roc_auc"] = None; out["average_precision"] = None
    pw = defaultdict(list)
    for yy, pp, w in zip(y, p, weeks): pw[w].append((int(yy), float(pp)))
    gains = {}
    for w, vals in pw.items():
        yy = np.asarray([z[0] for z in vals], int); pp = np.asarray([z[1] for z in vals], float); base = np.full(len(yy), null_p, float)
        gains[w] = float(brier_score_loss(yy, base) - brier_score_loss(yy, pp))
    out["positive_week_fraction_brier"] = float(np.mean([v > 0 for v in gains.values()])) if gains else None; out["per_week_brier_gain"] = dict(sorted(gains.items()))
    order = np.argsort(-p); k = max(1, int(math.ceil(0.10 * len(y)))); top = y[order[:k]]
    out["top_decile_positive_rate"] = float(np.mean(top)); out["top_decile_lift_vs_block_base"] = float(np.mean(top) / np.mean(y)) if np.mean(y) > 0 else None
    return out


def score_block(name, param, trainset, testset, stage, mode, h, cache, which):
    Xtr, ytr, _, _, _ = dataset(trainset, stage, mode, h, cache, which); Xte, yte, ids, weeks, leads = dataset(testset, stage, mode, h, cache, which)
    if len(np.unique(ytr)) < 2 or not len(yte): return None
    pred = predict_probability(name, param, Xtr, ytr, Xte); null_p = float(np.mean(ytr))
    return {"ids": ids, "weeks": weeks, "leads": leads, "prob": pred, "y": yte, "metrics": metrics(yte, pred, null_p, weeks)}


def paired_eval(name, cases, stage, mode, h, cache):
    fitset = split_cases(cases, ("discovery_fit",)); tuneset = split_cases(cases, ("discovery_tune",)); trainset = fitset + tuneset
    pl = tune_param(name, fitset, tuneset, stage, mode, h, cache, "long"); ps = tune_param(name, fitset, tuneset, stage, mode, h, cache, "short") if stage > 1 else None
    out = {"params": {"long": pl, "short": ps}, "blocks": {}}
    if pl is None: return out
    for b in ("validation", "confirmation", "held"):
        te = split_cases(cases, (b,)); L = score_block(name, pl, trainset, te, stage, mode, h, cache, "long")
        if L is None: out["blocks"][b] = {"n": 0}; continue
        rec = dict(L["metrics"]); rec["lead_seconds"] = {"min": int(min(L["leads"])) if L["leads"] else None, "median": float(np.median(L["leads"])) if L["leads"] else None, "p90": float(np.quantile(L["leads"], 0.90)) if L["leads"] else None, "max": int(max(L["leads"])) if L["leads"] else None}
        if stage == 1:
            rec["incremental_log_loss_gain_D_vs_Dminus1"] = rec["log_loss_gain_vs_null"]; rec["incremental_brier_gain_D_vs_Dminus1"] = rec["brier_gain_vs_null"]
        elif ps is not None:
            S = score_block(name, ps, trainset, te, stage, mode, h, cache, "short")
            if S is not None and S["ids"] == L["ids"]:
                rec["incremental_log_loss_gain_D_vs_Dminus1"] = float(log_loss(S["y"], S["prob"], labels=[0, 1])) - rec["log_loss"]; rec["incremental_brier_gain_D_vs_Dminus1"] = float(brier_score_loss(S["y"], S["prob"])) - rec["brier"]
            else: rec["incremental_log_loss_gain_D_vs_Dminus1"] = None; rec["incremental_brier_gain_D_vs_Dminus1"] = None
        out["blocks"][b] = rec
    return out


def model_pass(z, stage):
    req = MIN_COUNTS[stage]
    for b in ("validation", "confirmation"):
        q = z["blocks"].get(b, {})
        if q.get("positive_n", 0) < req[f"{b}_pos"] or q.get("negative_n", 0) < req[f"{b}_neg"]: return False
        if not (q.get("log_loss_gain_vs_null", -1) > 0 and q.get("brier_gain_vs_null", -1) > 0): return False
        if q.get("roc_auc") is None or q["roc_auc"] <= 0.5: return False
        if q.get("positive_week_fraction_brier") is not None and q["positive_week_fraction_brier"] < 0.5: return False
    held = z["blocks"].get("held", {})
    if held.get("positive_n", 0) >= 5 and held.get("negative_n", 0) >= 20 and held.get("brier_gain_vs_null", -1) < 0: return False
    return True


def evaluate_point(cases, stage, mode, h, cache):
    rec = {"mode": mode, "H_seconds": h, "models": {}}; passed = 0
    for m in MODELS:
        z = paired_eval(m, cases, stage, mode, h, cache); ok = model_pass(z, stage); z["passes_gate"] = ok; rec["models"][m] = z; passed += int(ok)
    rec["models_passing"] = passed; rec["validated"] = passed >= 2; return rec


def sparse_report(cases, stage):
    rows = []
    for c in cases:
        prior = []; tt = int(c["target"]["t0_idx"])
        for h in HGRID:
            cs = [event_confirm(e) for e in c["preds"]]
            if all(x is not None for x in cs) and max(int(x) + h for x in cs) <= tt: prior.append({"H": h, "lead_seconds": int(tt - max(int(x) + h for x in cs))})
        rows.append({"id": c["id"], "week": c["week"], "block": c["block"], "birth_label": c["y"], "final_depth_annotation_only": c["final_depth"], "prior_eligible": prior, "target_t0_idx": tt, "target_detector_confirm_idx": event_confirm(c["target"])})
    return rows


def run_stage(stage, events, lineage, raw_dir):
    cases, censored = birth_cases(events, lineage, stage); pos = sum(c["y"] for c in cases); neg = len(cases) - pos; weeks = sorted({c["week"] for c in cases})
    counts = {b: {"positive": 0, "negative": 0} for b in set(FOLD_BLOCK.values())}
    for c in cases: counts[c["block"]]["positive" if c["y"] else "negative"] += 1
    if stage >= 4:
        return {"status": "CHAIN_BIRTH_AGENT_COMPLETE_LOW_SUPPORT_PRESERVED", "stage": stage, "positive_n": int(pos), "negative_n": int(neg), "censored_n": int(len(censored)), "block_counts": counts, "H_grid": list(HGRID), "sparse_cases": sparse_report(cases, stage), "censored": censored, "promotion_performed": False}
    cache = {"times": {}, "prices": {}, "snap": {}}
    for w in weeks: cache["times"][w], cache["prices"][w] = load_week_prices(raw_dir, w)
    tested = []; winner = None
    for h in HGRID:
        p = evaluate_point(cases, stage, "prior", h, cache); tested.append(p)
        if p["validated"]: winner = {"timing_class": "PRIOR_BIRTH_PREDICTION", "H_seconds": h, "point": p}; break
        vn = max((z["blocks"].get("validation", {}).get("n", 0) for z in p["models"].values()), default=0)
        if vn == 0: break
    if winner is None:
        p = evaluate_point(cases, stage, "detect", 0, cache); tested.append(p)
        if p["validated"]: winner = {"timing_class": "AT_DETECTION_RECOGNITION", "H_seconds": 0, "point": p}
    if winner is None:
        for h in HGRID:
            p = evaluate_point(cases, stage, "post", h, cache); tested.append(p)
            if p["validated"]: winner = {"timing_class": "POST_DETECTION_RECOGNITION", "H_seconds": h, "point": p}; break
            vn = max((z["blocks"].get("validation", {}).get("n", 0) for z in p["models"].values()), default=0)
            if vn == 0: break
    return {"status": "CHAIN_BIRTH_AGENT_COMPLETE", "stage": stage, "positive_n": int(pos), "negative_n": int(neg), "censored_n": int(len(censored)), "block_counts": counts, "H_grid": list(HGRID), "primary_success_definition": "PRIOR_BIRTH_PREDICTION_ONLY", "earliest_validated": winner, "tested_points": tested, "censored": censored, "absolute_birth_skill_and_incremental_depth_gain_reported_separately": True, "characteristics_accessed": False, "timing_used_only_for_causal_availability_and_lead_reporting": True, "prohibited_features": ["family", "frozen_post_state", "flow", "book", "time_of_day", "session_position", "pre_exhaustion_shape", "target_identity_before_birth", "next_same_polarity_before_birth", "realized_final_depth", "realized_final_duration", "future_path_shape", "confirmation_lag_as_feature"], "promotion_performed": False, "protected_mutations": {"detector": False, "canonical_rows": False, "phase1": False, "phase2": False, "runway_clock": False, "permanent_frankie": False, "frankie_1": False, "spawn_py": False, "ssos_play": False}}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--stages", required=True); ap.add_argument("--base", required=True); ap.add_argument("--held", required=True); ap.add_argument("--base-lineage", required=True); ap.add_argument("--held-lineage", required=True); ap.add_argument("--raw-dir", required=True); ap.add_argument("--out", required=True); a = ap.parse_args()
    stages = [int(x) for x in a.stages.split(",")]; events = load_events(a.base, a.held); lineage = load_lineage(a.base_lineage, a.held_lineage)
    exact = defaultdict(int)
    for r in lineage: exact[r["depth"]] += 1
    assert dict(sorted(exact.items())) == EXPECTED_EXACT, (dict(sorted(exact.items())), EXPECTED_EXACT)
    result = {"status": "D1_D5_CHAIN_BIRTH_PREDICTABILITY_AGENT_COMPLETE", "date": "2026-08-19", "agent_stages": stages, "H_grid": list(HGRID), "frozen_exact_depth_counts": dict(sorted(exact.items())), "results": {f"D{s}": run_stage(s, events, lineage, a.raw_dir) for s in stages}, "primary_target": "PREDICT_WHETHER_NEXT_CHAIN_STAGE_BEGINS_BEFORE_FROZEN_TARGET_T0", "secondary_behavior_target_deferred": True, "promotion_performed": False}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "stages": stages, "earliest": {k: None if v.get("earliest_validated") is None else {"timing_class": v["earliest_validated"]["timing_class"], "H_seconds": v["earliest_validated"]["H_seconds"]} for k, v in result["results"].items()}}, indent=2))


if __name__ == "__main__": main()
