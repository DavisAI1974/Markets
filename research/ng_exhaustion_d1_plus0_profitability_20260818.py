#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

SEED = 20260818
FAMILIES = ("A", "B", "C")
WEEKDAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
BLOCKS = ("D1_DISCOVERY_OOT", "D1_VALIDATION", "D1_CONFIRMATION", "HELD_INSERT_ONLY")
COSTS = (0.0, 0.5, 1.0, 2.0)


def finite(x):
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def fnum(x, default=0.0):
    return float(x) if finite(x) else float(default)


def iter_gz(path):
    with gzip.open(path, "rt") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_gz(path, rows):
    with gzip.open(path, "wt") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")


def load_events(*paths):
    out = {}
    for path in paths:
        with gzip.open(path, "rt") as f:
            for line in f:
                r = json.loads(line)
                out[(r["week_sunday"], r["event_id"])] = r
    return out


def onehot(value, values):
    return [1.0 if value == z else 0.0 for z in values]


def safe_log1p(x):
    return math.log1p(max(0.0, fnum(x)))


def landmark_features(v, confirm_offset):
    conf = max(0.0, fnum(confirm_offset))
    occurred = bool(finite(v) and float(v) <= conf)
    observed_or_censored = float(v) if occurred else conf + 1.0
    return [1.0 if occurred else 0.0, safe_log1p(observed_or_censored)]


def causal_plus0_features(origin, events):
    ep = origin.get("dynamic_endpoint") or {}
    ft = origin.get("feature") or {}
    tc = origin.get("time_context") or {}
    conf_idx = ep.get("causal_confirmation_idx")
    conf_off = ep.get("causal_confirmation_offset_s")
    onset_off = ep.get("structural_onset_offset_s")
    if conf_idx is None or conf_off is None:
        raise ValueError("detector confirmation required for +0 features")

    x = []
    names = []

    def add(name, value):
        names.append(name)
        x.append(float(value))

    add("origin_polarity", fnum(origin.get("polarity")))
    for fam, val in zip(FAMILIES, onehot(origin.get("family"), FAMILIES)):
        add(f"origin_family_{fam}", val)

    distances = list(origin.get("pre_family_distances") or [])
    for i in range(3):
        v = distances[i] if i < len(distances) else None
        add(f"pre_family_distance_{i}", fnum(v))
        add(f"pre_family_distance_{i}_missing", 0.0 if finite(v) else 1.0)

    for key in ("peak_abs", "pre_prominence"):
        v = ft.get(key)
        add(key, fnum(v))
        add(key + "_missing", 0.0 if finite(v) else 1.0)

    add("confirmation_delay_log1p", safe_log1p(conf_off))
    add("onset_delay_log1p", safe_log1p(onset_off))
    add("confirm_minus_onset", max(0.0, fnum(conf_off) - fnum(onset_off)))

    for key in ("exh_t50_s", "exh_t25_s", "exh_t10_s", "exh_zero_onset_within60_s"):
        vals = landmark_features(ft.get(key), conf_off)
        add(key + "_occurred_by_confirm", vals[0])
        add(key + "_observed_or_censored_log1p", vals[1])

    add("local_hour", fnum(tc.get("local_hour")))
    for day, val in zip(WEEKDAYS, onehot(tc.get("local_weekday"), WEEKDAYS)):
        add("weekday_" + day.lower(), val)
    add("hours_since_reopen_log1p", safe_log1p(tc.get("hours_since_reopen_trade")))
    add("week_position_fraction", fnum(tc.get("week_position_fraction")))

    prev_id = (origin.get("link") or {}).get("previous_event_id")
    prev = events.get((origin["week_sunday"], prev_id)) if prev_id else None
    add("previous_event_exists", 1.0 if prev is not None else 0.0)
    if prev is None:
        for fam in FAMILIES:
            add("previous_family_" + fam, 0.0)
        add("previous_same_polarity", 0.0)
        add("previous_t0_gap_log1p", 0.0)
        add("previous_confirmed_by_current_confirm", 0.0)
        add("previous_confirmation_age_log1p", 0.0)
    else:
        for fam, val in zip(FAMILIES, onehot(prev.get("family"), FAMILIES)):
            add("previous_family_" + fam, val)
        add("previous_same_polarity", 1.0 if prev.get("polarity") == origin.get("polarity") else 0.0)
        add("previous_t0_gap_log1p", safe_log1p(int(origin["t0_idx"]) - int(prev["t0_idx"])))
        prev_conf = (prev.get("dynamic_endpoint") or {}).get("causal_confirmation_idx")
        prev_confirmed = prev_conf is not None and int(prev_conf) <= int(conf_idx)
        add("previous_confirmed_by_current_confirm", 1.0 if prev_confirmed else 0.0)
        add("previous_confirmation_age_log1p", safe_log1p(int(conf_idx) - int(prev_conf)) if prev_confirmed else 0.0)

    return np.asarray(x, dtype=float), names


def summarize(values):
    a = np.asarray([float(v) for v in values if finite(v)], dtype=float)
    if len(a) == 0:
        return {"n": 0, "mean": None, "median": None, "p25": None, "p75": None, "min": None, "max": None}
    return {
        "n": int(len(a)),
        "mean": float(np.mean(a)),
        "median": float(np.median(a)),
        "p25": float(np.quantile(a, 0.25)),
        "p75": float(np.quantile(a, 0.75)),
        "min": float(np.min(a)),
        "max": float(np.max(a)),
    }


def selected_metrics(rows, threshold, cost):
    picked = [r for r in rows if finite(r.get("prediction")) and abs(float(r["prediction"])) >= float(threshold)]
    vals = []
    weeks = defaultdict(list)
    for r in picked:
        y = float(r["target_origin_polarity_ticks"])
        ori = 1.0 if float(r["prediction"]) >= 0 else -1.0
        net = ori * y - float(cost)
        vals.append(net)
        weeks[r["week_sunday"]].append(net)
    week_means = {w: float(np.mean(v)) for w, v in weeks.items()}
    loo = []
    if len(week_means) >= 2:
        for w in week_means:
            z = [v for r, v in zip(picked, vals) if r["week_sunday"] != w]
            if z:
                loo.append(float(np.mean(z)))
    return {
        "n": int(len(vals)),
        "weeks": int(len(week_means)),
        "mean_ticks": float(np.mean(vals)) if vals else None,
        "median_ticks": float(np.median(vals)) if vals else None,
        "positive_trade_rate": float(sum(v > 0 for v in vals) / len(vals)) if vals else None,
        "positive_week_fraction": float(sum(v > 0 for v in week_means.values()) / len(week_means)) if week_means else None,
        "leave_one_week_out_min_mean_ticks": min(loo) if loo else None,
        "week_means": week_means,
    }


def block_report(rows, threshold):
    return {
        "all_predictions": {str(cost): selected_metrics(rows, 0.0, cost) for cost in COSTS},
        "confidence_selected": {str(cost): selected_metrics(rows, threshold, cost) for cost in COSTS},
        "prediction_magnitude": summarize([abs(r["prediction"]) for r in rows if finite(r.get("prediction"))]),
    }


def tune_threshold(rows):
    mags = np.asarray([abs(float(r["prediction"])) for r in rows if finite(r.get("prediction"))], dtype=float)
    if len(mags) == 0:
        return None, [], "NO_TUNE_PREDICTIONS"
    candidates = [0.0]
    for q in (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95):
        candidates.append(float(np.quantile(mags, q)))
    candidates = sorted(set(round(x, 12) for x in candidates))
    audit = []
    for th in candidates:
        m = selected_metrics(rows, th, 1.0)
        passed = bool(
            m["n"] >= 100
            and m["weeks"] >= 4
            and m["mean_ticks"] is not None and m["mean_ticks"] > 0
            and m["positive_trade_rate"] is not None and m["positive_trade_rate"] >= 0.52
            and m["positive_week_fraction"] is not None and m["positive_week_fraction"] >= 0.55
            and m["leave_one_week_out_min_mean_ticks"] is not None and m["leave_one_week_out_min_mean_ticks"] > 0
        )
        audit.append({"threshold_abs_pred_ticks": th, "net_1_tick": m, "gate_passed": passed})
        if passed:
            return th, audit, "TUNE_GATE_PASSED"
    return None, audit, "TUNE_GATE_FAILED"


def validation_gate(report, threshold):
    failures = []
    if threshold is None:
        return False, ["no threshold passed the discovery-tune gate"]
    for block in ("D1_VALIDATION", "D1_CONFIRMATION"):
        m = report[block]["confidence_selected"]["1.0"]
        if m["n"] < 100:
            failures.append(f"{block}: selected n {m['n']} < 100")
        if m["weeks"] < 4:
            failures.append(f"{block}: selected weeks {m['weeks']} < 4")
        if m["mean_ticks"] is None or m["mean_ticks"] <= 0:
            failures.append(f"{block}: net1 mean not positive")
        if m["positive_trade_rate"] is None or m["positive_trade_rate"] <= 0.50:
            failures.append(f"{block}: positive trade rate <= 0.50")
        if m["positive_week_fraction"] is None or m["positive_week_fraction"] < 0.50:
            failures.append(f"{block}: positive week fraction < 0.50")
    return len(failures) == 0, failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--held", required=True)
    ap.add_argument("--path-master", required=True)
    ap.add_argument("--checkpoints", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()

    events = load_events(a.base, a.held)
    paths = list(iter_gz(a.path_master))
    if len(paths) != 18837:
        raise SystemExit(f"preserve-all D1 invariant failed expected=18837 actual={len(paths)}")

    cp0 = {}
    for r in iter_gz(a.checkpoints):
        if int(r.get("checkpoint_offset_seconds", -1)) != 0:
            continue
        if r["d1_id"] in cp0:
            raise SystemExit(f"duplicate +0 checkpoint for {r['d1_id']}")
        cp0[r["d1_id"]] = r

    model_rows = []
    feature_names = None
    row_out = []
    for p in paths:
        rec = {
            "d1_id": p["d1_id"],
            "week_sunday": p["week_sunday"],
            "chronological_block": p["chronological_block"],
            "origin_event_id": p["origin_event_id"],
            "path_shape_group_outcome_only": p.get("path_shape_group"),
            "preserved": True,
            "checkpoint_offset_seconds": 0,
            "prediction": None,
            "predicted_orientation": None,
            "target_origin_polarity_ticks": None,
            "plus0_status": None,
        }
        c = cp0.get(p["d1_id"])
        if not p.get("detector_clock_precedes_descendant"):
            rec["plus0_status"] = "NO_PLUS0_STRUCTURAL_WINDOW"
            row_out.append(rec)
            continue
        if c is None:
            rec["plus0_status"] = "NO_PLUS0_CHECKPOINT_ROW"
            row_out.append(rec)
            continue
        if not c.get("execution_fill_available") or not finite(c.get("signed_endpoint_ticks")):
            rec["plus0_status"] = "NO_PLUS0_EXECUTABLE_FILL"
            row_out.append(rec)
            continue
        origin = events.get((p["week_sunday"], p["origin_event_id"]))
        if origin is None:
            raise SystemExit(f"missing canonical origin {p['d1_id']}")
        x, names = causal_plus0_features(origin, events)
        if feature_names is None:
            feature_names = names
        elif feature_names != names:
            raise SystemExit("feature schema drift")
        y = float(c["signed_endpoint_ticks"])
        rec["target_origin_polarity_ticks"] = y
        rec["fill_latency_seconds"] = c.get("fill_latency_seconds")
        rec["remaining_structural_seconds_from_checkpoint"] = c.get("structural_remaining_seconds_from_checkpoint")
        rec["plus0_status"] = "PLUS0_FILLABLE_PENDING_MODEL"
        model_rows.append({"out": rec, "x": x, "y": y})
        row_out.append(rec)

    discovery_weeks = sorted(set(z["out"]["week_sunday"] for z in model_rows if z["out"]["chronological_block"] == "D1_DISCOVERY_OOT"))
    if len(discovery_weeks) != 18:
        raise SystemExit(f"expected 18 D1 discovery weeks, got {len(discovery_weeks)} {discovery_weeks}")
    fit_weeks = set(discovery_weeks[:12])
    tune_weeks = set(discovery_weeks[12:])
    fit = [z for z in model_rows if z["out"]["week_sunday"] in fit_weeks]
    tune = [z for z in model_rows if z["out"]["week_sunday"] in tune_weeks]
    if len(fit) < 1000 or len(tune) < 500:
        raise SystemExit(f"insufficient +0 discovery rows fit={len(fit)} tune={len(tune)}")

    X = np.vstack([z["x"] for z in fit])
    y = np.asarray([z["y"] for z in fit], dtype=float)
    model = HistGradientBoostingRegressor(
        learning_rate=0.05,
        max_iter=250,
        max_leaf_nodes=15,
        min_samples_leaf=50,
        l2_regularization=1.0,
        random_state=SEED,
    )
    model.fit(X, y)

    for z in model_rows:
        pred = float(model.predict(z["x"].reshape(1, -1))[0])
        z["out"]["prediction"] = pred
        z["out"]["predicted_orientation"] = "WITH_ORIGIN_POLARITY" if pred >= 0 else "AGAINST_ORIGIN_POLARITY"

    tune_rows = [z["out"] for z in model_rows if z["out"]["week_sunday"] in tune_weeks]
    threshold, threshold_audit, tune_status = tune_threshold(tune_rows)
    effective_threshold = float(threshold) if threshold is not None else float("inf")

    report = {}
    for block in BLOCKS:
        rows = [z["out"] for z in model_rows if z["out"]["chronological_block"] == block]
        report[block] = block_report(rows, effective_threshold)
    report["D1_DISCOVERY_FIT_18_29"] = block_report([z["out"] for z in model_rows if z["out"]["week_sunday"] in fit_weeks], effective_threshold)
    report["D1_DISCOVERY_TUNE_30_35"] = block_report(tune_rows, effective_threshold)

    early_validated, gate_failures = validation_gate(report, threshold)

    early_n = fallback_n = no_window_n = no_fill_n = 0
    shape_early = Counter()
    for r in row_out:
        if r["plus0_status"] == "NO_PLUS0_STRUCTURAL_WINDOW":
            no_window_n += 1
            continue
        if r["plus0_status"] in ("NO_PLUS0_CHECKPOINT_ROW", "NO_PLUS0_EXECUTABLE_FILL"):
            no_fill_n += 1
            continue
        if not early_validated:
            r["plus0_status"] = "FALLBACK_PLUS0_MODEL_NOT_VALIDATED"
            fallback_n += 1
        elif abs(float(r["prediction"])) >= effective_threshold:
            r["plus0_status"] = "EARLY_PLUS0_ACTIONABLE_CANDIDATE"
            early_n += 1
            shape_early[r.get("path_shape_group_outcome_only")] += 1
        else:
            r["plus0_status"] = "FALLBACK_PLUS0_CONFIDENCE_BELOW_GATE"
            fallback_n += 1

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / "NG_EXHAUSTION_D1_PLUS0_EARLY_ENTRY_ROWS_20260818.jsonl.gz"
    write_gz(rows_path, row_out)
    summary = {
        "status": "D1_PLUS0_EARLY_ENTRY_COMPLETE",
        "population": {
            "forward_exact_d1_n": 18837,
            "model_fillable_plus0_n": int(len(model_rows)),
            "no_plus0_structural_window_n": int(no_window_n),
            "no_plus0_fill_or_checkpoint_n": int(no_fill_n),
            "early_plus0_actionable_n": int(early_n),
            "fallback_after_plus0_n": int(fallback_n),
        },
        "clock": "DETECTOR_CONFIRMATION_IS_PLUS0",
        "model": {
            "type": "HistGradientBoostingRegressor",
            "fixed_params": {
                "learning_rate": 0.05,
                "max_iter": 250,
                "max_leaf_nodes": 15,
                "min_samples_leaf": 50,
                "l2_regularization": 1.0,
                "random_state": SEED,
            },
            "target": "remaining signed endpoint return from first trade at/after detector confirmation, expressed in origin-polarity ticks",
            "direction_rule": "prediction >= 0 => with origin polarity; prediction < 0 => against origin polarity",
            "feature_names": feature_names,
            "feature_contract": [
                "Only information causally observable by detector confirmation is used.",
                "Current post-t0 landmarks are censored at confirmation; future landmark completion times are never exposed.",
                "Current full-state/post-state labels are excluded from the primary +0 model entirely.",
                "Previous-event inputs are limited to pre-family/polarity/timing and whether its detector had already confirmed.",
                "Descendant state/identity, realized duration family, final path shape, MFE/MAE and future checkpoints are excluded from model inputs.",
            ],
        },
        "chronology": {
            "fit_weeks": sorted(fit_weeks),
            "tune_weeks": sorted(tune_weeks),
            "validation_block": "D1_VALIDATION",
            "confirmation_block": "D1_CONFIRMATION",
            "held_block": "HELD_INSERT_ONLY",
        },
        "threshold_selection": {
            "status": tune_status,
            "selected_abs_prediction_threshold_ticks": threshold,
            "gate": {
                "min_n": 100,
                "min_weeks": 4,
                "net_1_tick_mean_gt": 0.0,
                "positive_trade_rate_gte": 0.52,
                "positive_week_fraction_gte": 0.55,
                "leave_one_week_out_min_net1_mean_gt": 0.0,
                "selection_policy": "lowest confidence threshold that passes; no later threshold preferred for extra profit",
            },
            "audit": threshold_audit,
        },
        "early_validation": {
            "passed": bool(early_validated),
            "failures": gate_failures,
            "gate": "unchanged threshold must have positive 1-tick net mean, >50% positive trades, >=50% positive weeks, >=100 trades and >=4 weeks in both validation and confirmation",
        },
        "blocks": report,
        "posthoc_path_shape_of_early_selected": {
            "counts": dict(shape_early),
            "guard": "realized path shape is outcome-only and was not a model input",
        },
        "entry_hierarchy": "PLUS0_FIRST; ONLY NONACTIONABLE/FILL-FAILED/NO-WINDOW ROWS PROCEED TO DENSE FALLBACK",
        "fallback_grid": [1, 2, 3, 4, 5, 10, 15, 20] + list(range(25, 3601, 5)),
        "cost_stress_ticks": list(COSTS),
        "rows_file": str(rows_path),
        "promotion_performed": False,
        "protected_mutations": {
            "detector": False,
            "canonical_rows": False,
            "held_rows": False,
            "phase1_lineage": False,
            "phase2": False,
            "runway_clock": False,
            "permanent_frankie": False,
            "frankie1": False,
            "spawn_py": False,
            "ssos_play": False,
        },
    }
    summary_path = out_dir / "NG_EXHAUSTION_D1_PLUS0_EARLY_ENTRY_SUMMARY_20260818.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": summary["status"],
        "fillable": len(model_rows),
        "threshold": threshold,
        "early_validation_passed": early_validated,
        "early_n": early_n,
        "fallback_n": fallback_n,
        "no_window_n": no_window_n,
        "no_fill_n": no_fill_n,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
