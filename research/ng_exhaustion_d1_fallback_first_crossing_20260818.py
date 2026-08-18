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

import ng_exhaustion_d1_plus0_profitability_20260818 as plus0
from ng_dipole_runway_audit import TICK

SEED = 20260818
COSTS = (0.0, 0.5, 1.0, 2.0)
VALIDATION_BLOCKS = ("D1_VALIDATION", "D1_CONFIRMATION")


def finite(x):
    return plus0.finite(x)


def iter_gz(path):
    return plus0.iter_gz(path)


def write_gz(path, rows):
    return plus0.write_gz(path, rows)


def load_events(*paths):
    return plus0.load_events(*paths)


def safe_log1p(x):
    return plus0.safe_log1p(x)


def causal_checkpoint_features(origin, events, cp, prior_rows):
    base, base_names = plus0.causal_plus0_features(origin, events)
    ep = origin.get("dynamic_endpoint") or {}
    ft = origin.get("feature") or {}
    conf_off = float(ep["causal_confirmation_offset_s"])
    offset = int(cp["checkpoint_offset_seconds"])
    current_rel = conf_off + offset
    current_idx = int(cp["checkpoint_idx"])

    x = list(base)
    names = list(base_names)

    def add(name, value):
        names.append(name)
        x.append(float(value))

    add("fallback_checkpoint_offset_log1p", safe_log1p(offset))
    add("fallback_checkpoint_offset_seconds", float(offset))
    add("survived_to_checkpoint", 1.0)
    add("current_rel_from_t0_log1p", safe_log1p(current_rel))

    for key in ("exh_t50_s", "exh_t25_s", "exh_t10_s", "exh_zero_onset_within60_s"):
        vals = plus0.landmark_features(ft.get(key), current_rel)
        add("checkpoint_" + key + "_occurred", vals[0])
        add("checkpoint_" + key + "_observed_or_censored_log1p", vals[1])

    known = []
    for p in prior_rows:
        if int(p.get("checkpoint_offset_seconds", 10**9)) >= offset:
            continue
        if not p.get("execution_fill_available"):
            continue
        if not finite(p.get("entry_price")) or not finite(p.get("actual_fill_idx")):
            continue
        if int(p["actual_fill_idx"]) <= current_idx:
            known.append(p)
    known.sort(key=lambda r: (int(r["actual_fill_idx"]), int(r["checkpoint_offset_seconds"])))
    pol = float(origin["polarity"])
    add("known_prior_fill_count_log1p", safe_log1p(len(known)))
    add("known_prior_fill_exists", 1.0 if known else 0.0)
    if not known:
        for name in (
            "prior_price_signed_change_ticks",
            "prior_price_last_step_signed_ticks",
            "prior_price_range_ticks",
            "prior_price_path_efficiency",
            "seconds_since_last_known_fill_log1p",
        ):
            add(name, 0.0)
    else:
        prices = [float(r["entry_price"]) for r in known]
        fills = [int(r["actual_fill_idx"]) for r in known]
        signed_change = pol * (prices[-1] - prices[0]) / TICK if len(prices) >= 2 else 0.0
        signed_last = pol * (prices[-1] - prices[-2]) / TICK if len(prices) >= 2 else 0.0
        rng = (max(prices) - min(prices)) / TICK if len(prices) >= 2 else 0.0
        total = sum(abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))) / TICK
        eff = abs(signed_change) / total if total > 0 else 0.0
        add("prior_price_signed_change_ticks", signed_change)
        add("prior_price_last_step_signed_ticks", signed_last)
        add("prior_price_range_ticks", rng)
        add("prior_price_path_efficiency", eff)
        add("seconds_since_last_known_fill_log1p", safe_log1p(current_idx - fills[-1]))

    return np.asarray(x, dtype=float), names


def strategy_metrics(candidates, threshold, cost):
    by_id = defaultdict(list)
    for r in candidates:
        if finite(r.get("prediction")):
            by_id[r["d1_id"]].append(r)
    chosen = []
    for did, rows in by_id.items():
        rows.sort(key=lambda r: int(r["checkpoint_offset_seconds"]))
        for r in rows:
            if abs(float(r["prediction"])) >= float(threshold):
                chosen.append(r)
                break
    vals = []
    weeks = defaultdict(list)
    offsets = Counter()
    for r in chosen:
        ori = 1.0 if float(r["prediction"]) >= 0 else -1.0
        net = ori * float(r["target_origin_polarity_ticks"]) - float(cost)
        vals.append(net)
        weeks[r["week_sunday"]].append(net)
        offsets[int(r["checkpoint_offset_seconds"])] += 1
    week_means = {w: float(np.mean(v)) for w, v in weeks.items()}
    loo = []
    if len(week_means) >= 2:
        for w in week_means:
            z = []
            for r in chosen:
                if r["week_sunday"] == w:
                    continue
                ori = 1.0 if float(r["prediction"]) >= 0 else -1.0
                z.append(ori * float(r["target_origin_polarity_ticks"]) - float(cost))
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
        "selected_checkpoint_counts": dict(sorted(offsets.items())),
        "week_means": week_means,
    }


def choose_threshold(tune_candidates):
    mags = np.asarray([abs(float(r["prediction"])) for r in tune_candidates if finite(r.get("prediction"))], dtype=float)
    if len(mags) == 0:
        return None, [], "NO_TUNE_PREDICTIONS"
    thresholds = [0.0]
    for q in (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95):
        thresholds.append(float(np.quantile(mags, q)))
    thresholds = sorted(set(round(v, 12) for v in thresholds))
    audit = []
    for th in thresholds:
        m = strategy_metrics(tune_candidates, th, 1.0)
        passed = bool(
            m["n"] >= 100
            and m["weeks"] >= 4
            and m["mean_ticks"] is not None and m["mean_ticks"] > 0
            and m["positive_trade_rate"] is not None and m["positive_trade_rate"] >= 0.52
            and m["positive_week_fraction"] is not None and m["positive_week_fraction"] >= 0.55
            and m["leave_one_week_out_min_mean_ticks"] is not None and m["leave_one_week_out_min_mean_ticks"] > 0
        )
        audit.append({"threshold_abs_pred_ticks": th, "net_1_tick_first_crossing": m, "gate_passed": passed})
        if passed:
            return th, audit, "TUNE_GATE_PASSED"
    return None, audit, "TUNE_GATE_FAILED"


def validation_gate(block_metrics, threshold):
    if threshold is None:
        return False, ["no fallback threshold passed discovery tune"]
    failures = []
    for b in VALIDATION_BLOCKS:
        m = block_metrics[b]["1.0"]
        if m["n"] < 100:
            failures.append(f"{b}: n {m['n']} < 100")
        if m["weeks"] < 4:
            failures.append(f"{b}: weeks {m['weeks']} < 4")
        if m["mean_ticks"] is None or m["mean_ticks"] <= 0:
            failures.append(f"{b}: net1 mean not positive")
        if m["positive_trade_rate"] is None or m["positive_trade_rate"] <= 0.50:
            failures.append(f"{b}: positive trade rate <= 0.50")
        if m["positive_week_fraction"] is None or m["positive_week_fraction"] < 0.50:
            failures.append(f"{b}: positive week fraction < 0.50")
    return len(failures) == 0, failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--held", required=True)
    ap.add_argument("--lane2-checkpoints", required=True)
    ap.add_argument("--lane3-summary", required=True)
    ap.add_argument("--lane3-rows", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()

    events = load_events(a.base, a.held)
    lane3_summary = json.load(open(a.lane3_summary))
    lane3_rows = {r["d1_id"]: r for r in iter_gz(a.lane3_rows)}
    if len(lane3_rows) != 18837:
        raise SystemExit(f"lane3 preserve-all rows expected=18837 actual={len(lane3_rows)}")

    cp_by_id = defaultdict(list)
    for r in iter_gz(a.lane2_checkpoints):
        cp_by_id[r["d1_id"]].append(r)
    for rows in cp_by_id.values():
        rows.sort(key=lambda r: int(r["checkpoint_offset_seconds"]))

    fallback_ids = {
        did for did, r in lane3_rows.items()
        if r["plus0_status"] != "EARLY_PLUS0_ACTIONABLE_CANDIDATE"
        and r["plus0_status"] != "NO_PLUS0_STRUCTURAL_WINDOW"
    }
    early_ids = {did for did, r in lane3_rows.items() if r["plus0_status"] == "EARLY_PLUS0_ACTIONABLE_CANDIDATE"}

    candidates = []
    feature_names = None
    for did in sorted(fallback_ids):
        l3 = lane3_rows[did]
        week = l3["week_sunday"]
        origin = events.get((week, l3["origin_event_id"]))
        if origin is None:
            raise SystemExit(f"missing canonical origin {did}")
        rows = cp_by_id.get(did, [])
        for cp in rows:
            off = int(cp.get("checkpoint_offset_seconds", 0))
            if off <= 0:
                continue
            if not cp.get("execution_fill_available") or not finite(cp.get("signed_endpoint_ticks")):
                continue
            x, names = causal_checkpoint_features(origin, events, cp, rows)
            if feature_names is None:
                feature_names = names
            elif feature_names != names:
                raise SystemExit("fallback feature schema drift")
            candidates.append({
                "d1_id": did,
                "week_sunday": week,
                "chronological_block": l3["chronological_block"],
                "checkpoint_offset_seconds": off,
                "checkpoint_idx": cp["checkpoint_idx"],
                "remaining_structural_seconds": cp.get("structural_remaining_seconds_from_checkpoint"),
                "target_origin_polarity_ticks": float(cp["signed_endpoint_ticks"]),
                "x": x,
                "prediction": None,
            })

    fit_weeks = set(lane3_summary["chronology"]["fit_weeks"])
    tune_weeks = set(lane3_summary["chronology"]["tune_weeks"])
    fit = [r for r in candidates if r["week_sunday"] in fit_weeks]
    tune = [r for r in candidates if r["week_sunday"] in tune_weeks]
    if not fit or not tune:
        raise SystemExit(f"fallback training data missing fit={len(fit)} tune={len(tune)}")

    fit_counts = Counter(r["d1_id"] for r in fit)
    X = np.vstack([r["x"] for r in fit])
    y = np.asarray([r["target_origin_polarity_ticks"] for r in fit], dtype=float)
    weights = np.asarray([1.0 / fit_counts[r["d1_id"]] for r in fit], dtype=float)
    model = HistGradientBoostingRegressor(
        learning_rate=0.04,
        max_iter=300,
        max_leaf_nodes=20,
        min_samples_leaf=80,
        l2_regularization=1.5,
        random_state=SEED,
    )
    model.fit(X, y, sample_weight=weights)
    for r in candidates:
        r["prediction"] = float(model.predict(r["x"].reshape(1, -1))[0])
        del r["x"]

    tune_candidates = [r for r in candidates if r["week_sunday"] in tune_weeks]
    threshold, threshold_audit, tune_status = choose_threshold(tune_candidates)
    effective = float(threshold) if threshold is not None else float("inf")

    block_metrics = {}
    blocks = ("D1_DISCOVERY_OOT", "D1_VALIDATION", "D1_CONFIRMATION", "HELD_INSERT_ONLY")
    for b in blocks:
        R = [r for r in candidates if r["chronological_block"] == b]
        block_metrics[b] = {str(c): strategy_metrics(R, effective, c) for c in COSTS}
    block_metrics["D1_DISCOVERY_FIT_18_29"] = {str(c): strategy_metrics([r for r in candidates if r["week_sunday"] in fit_weeks], effective, c) for c in COSTS}
    block_metrics["D1_DISCOVERY_TUNE_30_35"] = {str(c): strategy_metrics(tune_candidates, effective, c) for c in COSTS}

    fallback_validated, failures = validation_gate(block_metrics, threshold)

    pred_by_id = defaultdict(list)
    for r in candidates:
        pred_by_id[r["d1_id"]].append(r)
    for rows in pred_by_id.values():
        rows.sort(key=lambda r: int(r["checkpoint_offset_seconds"]))

    output = []
    status_counts = Counter()
    selected_offsets = Counter()
    selected_shapes = Counter()
    for did, l3 in lane3_rows.items():
        rec = {
            "d1_id": did,
            "week_sunday": l3["week_sunday"],
            "chronological_block": l3["chronological_block"],
            "origin_event_id": l3["origin_event_id"],
            "plus0_status": l3["plus0_status"],
            "path_shape_group_outcome_only": l3.get("path_shape_group_outcome_only"),
            "fallback_status": None,
            "selected_checkpoint_offset_seconds": None,
            "selected_prediction": None,
            "selected_orientation": None,
            "selected_target_origin_polarity_ticks": None,
            "selected_remaining_structural_seconds": None,
            "preserved": True,
        }
        if did in early_ids:
            rec["fallback_status"] = "NOT_ELIGIBLE_ALREADY_ACTIONABLE_PLUS0"
        elif l3["plus0_status"] == "NO_PLUS0_STRUCTURAL_WINDOW":
            rec["fallback_status"] = "NO_FALLBACK_STRUCTURAL_WINDOW"
        elif not fallback_validated:
            rec["fallback_status"] = "FALLBACK_MODEL_NOT_VALIDATED"
        else:
            pick = None
            for r in pred_by_id.get(did, []):
                if abs(float(r["prediction"])) >= effective:
                    pick = r
                    break
            if pick is None:
                rec["fallback_status"] = "NO_VALIDATED_FALLBACK_CONFIDENCE_CROSSING"
            else:
                rec["fallback_status"] = "FALLBACK_FIRST_CROSSING_ACTIONABLE_CANDIDATE"
                rec["selected_checkpoint_offset_seconds"] = int(pick["checkpoint_offset_seconds"])
                rec["selected_prediction"] = float(pick["prediction"])
                rec["selected_orientation"] = "WITH_ORIGIN_POLARITY" if pick["prediction"] >= 0 else "AGAINST_ORIGIN_POLARITY"
                rec["selected_target_origin_polarity_ticks"] = float(pick["target_origin_polarity_ticks"])
                rec["selected_remaining_structural_seconds"] = pick.get("remaining_structural_seconds")
                selected_offsets[int(pick["checkpoint_offset_seconds"])] += 1
                selected_shapes[rec.get("path_shape_group_outcome_only")] += 1
        status_counts[rec["fallback_status"]] += 1
        output.append(rec)

    if len(output) != 18837:
        raise SystemExit("fallback preserve-all output count drift")

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / "NG_EXHAUSTION_D1_FALLBACK_FIRST_CROSSING_ROWS_20260818.jsonl.gz"
    write_gz(rows_path, output)
    summary = {
        "status": "D1_DENSE_FALLBACK_FIRST_CROSSING_COMPLETE",
        "population": {
            "forward_exact_d1_n": 18837,
            "already_plus0_actionable_n": len(early_ids),
            "fallback_candidate_d1_n": len(fallback_ids),
            "fallback_checkpoint_training_rows": len(candidates),
            "output_rows": len(output),
        },
        "model": {
            "type": "HistGradientBoostingRegressor",
            "fixed_params": {
                "learning_rate": 0.04,
                "max_iter": 300,
                "max_leaf_nodes": 20,
                "min_samples_leaf": 80,
                "l2_regularization": 1.5,
                "random_state": SEED,
            },
            "sample_weight": "1 / number of eligible fallback checkpoints for each D1 in fit weeks, so long-lived structures do not dominate",
            "feature_names": feature_names,
            "causal_feature_contract": [
                "Base features are the detector-confirmation +0 causal surface.",
                "Checkpoint survival/age and exhaustion landmarks are censored at the current checkpoint.",
                "Only prices from earlier checkpoint fills whose actual fill time is <= current checkpoint may enter price-history features.",
                "The current checkpoint fill price, future MFE/MAE, future checkpoint prices, final duration and descendant identity/state are not inputs.",
                "Current full-state/post-state labels remain excluded from this fallback model.",
            ],
        },
        "threshold_selection": {
            "status": tune_status,
            "selected_abs_prediction_threshold_ticks": threshold,
            "policy": "lowest threshold passing discovery-tune under the chronological first-crossing strategy",
            "audit": threshold_audit,
        },
        "validation": {
            "passed": bool(fallback_validated),
            "failures": failures,
            "gate": "unchanged first-crossing rule must have positive 1-tick net mean, >50% positive trades, >=50% positive weeks, >=100 trades and >=4 weeks in both validation and confirmation",
        },
        "blocks": block_metrics,
        "selected_checkpoint_counts": dict(sorted(selected_offsets.items())),
        "status_counts": dict(status_counts),
        "posthoc_path_shape_of_selected": {
            "counts": dict(selected_shapes),
            "guard": "realized path shape is outcome-only and never a fallback model input",
        },
        "checkpoint_grid": [1,2,3,4,5,10,15,20] + list(range(25,3601,5)),
        "entry_policy": "EARLIEST_CAUSAL_CONFIDENCE_CROSSING_WINS; NO_HINDSIGHT_BEST_CHECKPOINT_SELECTION",
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
    summary_path = out_dir / "NG_EXHAUSTION_D1_FALLBACK_FIRST_CROSSING_SUMMARY_20260818.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": summary["status"],
        "validated": fallback_validated,
        "threshold": threshold,
        "selected_checkpoint_counts": summary["selected_checkpoint_counts"],
        "status_counts": summary["status_counts"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
