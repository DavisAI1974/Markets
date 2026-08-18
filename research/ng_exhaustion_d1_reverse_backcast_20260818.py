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
import ng_exhaustion_chain_phase1_structural_54w_20260817 as structural

MODELS = ("ridge", "extra_trees", "knn")
SEED = 20260817
SOURCE_TAG = "REVERSE_BACKCAST_NOT_FORWARD_OOT"

# Fixed before observing this reverse-labeler's validation/confirmation metrics.
GATE = {
    "validation": {
        "min_mcc": 0.20,
        "min_balanced_accuracy": 0.60,
        "min_precision_lift": 1.20,
        "min_true_positive_coverage": 0.80,
        "prevalence_ratio_low": 0.50,
        "prevalence_ratio_high": 2.00,
    },
    "confirmation": {
        "min_mcc": 0.15,
        "min_balanced_accuracy": 0.575,
        "min_precision_lift": 1.15,
        "min_true_positive_coverage": 0.75,
        "prevalence_ratio_low": 0.50,
        "prevalence_ratio_high": 2.00,
    },
    "held": {
        "min_mcc": 0.05,
        "min_balanced_accuracy": 0.525,
        "min_precision_lift": 1.00,
        "min_true_positive_coverage": 0.70,
        "prevalence_ratio_low": 0.35,
        "prevalence_ratio_high": 2.50,
    },
}


def load_jsonl_gz(path):
    with gzip.open(path, "rt") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def load_frozen_labels(path):
    out = {}
    by_week = defaultdict(lambda: {"rows": 0, "exact_d1": 0})
    for r in load_jsonl_gz(path):
        w = r["week_sunday"]
        i = int(r["origin_sequence_index"])
        y = int(r.get("all_model_consecutive_positive_depth", 0)) == 1
        out[(w, i)] = y
        by_week[w]["rows"] += 1
        by_week[w]["exact_d1"] += int(y)
    return out, dict(by_week)


def sample_train(X, Y, model):
    tr_lim, _ = structural.model_limits(model, inner=False)
    if tr_lim is None or len(Y) <= tr_lim:
        return X, Y
    ix = np.linspace(0, len(Y) - 1, int(tr_lim), dtype=int)
    return X[ix], Y[ix]


def make_estimator(model, param, ntrain):
    if model == "ridge":
        return Ridge(alpha=float(param), fit_intercept=True)
    if model == "extra_trees":
        return ExtraTreesRegressor(
            n_estimators=100,
            min_samples_leaf=int(param),
            max_features=1.0,
            random_state=SEED,
            n_jobs=-1,
        )
    if model == "knn":
        return KNeighborsRegressor(
            n_neighbors=min(int(param), int(ntrain)),
            weights="distance",
            p=2,
            n_jobs=-1,
        )
    raise ValueError(model)


class HistoryPredictor:
    def __init__(self, model, depth, history_len, param, byweek, arrays, valid, train_weeks):
        self.model_name = model
        self.depth = int(depth)
        self.history_len = int(history_len)
        self.param = param
        X, Y, _ = structural.matrices(train_weeks, byweek, arrays, valid, depth, history_len)
        if not len(Y):
            raise RuntimeError(f"empty training matrix model={model} depth={depth} h={history_len}")
        X, Y = sample_train(X, Y, model)
        self.ntrain = int(len(Y))
        self.mu = Y.mean(axis=0)
        self.sd = Y.std(axis=0)
        self.sd[self.sd < 1e-12] = 1.0
        self.estimator = None
        if history_len:
            xm = np.tile(self.mu, history_len)
            xs = np.tile(self.sd, history_len)
            Xz = (X - xm) / xs
            Yz = (Y - self.mu) / self.sd
            self.estimator = make_estimator(model, param, len(Y))
            self.estimator.fit(Xz, Yz)

    def losses_for_week(self, week, byweek, arrays, valid):
        X, Y, meta = structural.matrices([week], byweek, arrays, valid, self.depth, self.history_len)
        if not len(Y):
            return {}, 0
        Yz = (Y - self.mu) / self.sd
        if self.history_len:
            xm = np.tile(self.mu, self.history_len)
            xs = np.tile(self.sd, self.history_len)
            Xz = (X - xm) / xs
            pred = self.estimator.predict(Xz)
        else:
            pred = np.zeros_like(Yz)
        loss = np.mean((Yz - pred) ** 2, axis=1)
        return {(w, int(seq)): float(v) for v, (w, seq, _) in zip(loss, meta)}, int(len(loss))


def tune_and_fit(model, depth, history_len, train_weeks, byweek, arrays, valid):
    if history_len == 0:
        param = None
    else:
        param = structural.tune(model, train_weeks, byweek, arrays, valid, depth, history_len)
        if param is None:
            raise RuntimeError(f"tuning failed model={model} depth={depth} h={history_len}")
    return HistoryPredictor(model, depth, history_len, param, byweek, arrays, valid, train_weeks)


def build_gain_models(train_weeks, byweek, arrays, valid):
    fitted = {}
    tuning = {}
    for model in MODELS:
        d1_short = tune_and_fit(model, 1, 0, train_weeks, byweek, arrays, valid)
        d1_long = tune_and_fit(model, 1, 1, train_weeks, byweek, arrays, valid)
        d2_short = tune_and_fit(model, 2, 1, train_weeks, byweek, arrays, valid)
        d2_long = tune_and_fit(model, 2, 2, train_weeks, byweek, arrays, valid)
        fitted[model] = {
            1: (d1_short, d1_long),
            2: (d2_short, d2_long),
        }
        tuning[model] = {
            "d1_short_history": 0,
            "d1_long_param": d1_long.param,
            "d2_short_param": d2_short.param,
            "d2_long_param": d2_long.param,
            "d1_train_n": d1_long.ntrain,
            "d2_train_n": d2_long.ntrain,
        }
    return fitted, tuning


def gains_for_weeks(weeks, fitted, byweek, arrays, valid):
    out = {1: {m: {} for m in MODELS}, 2: {m: {} for m in MODELS}}
    rows = {1: defaultdict(int), 2: defaultdict(int)}
    for w in weeks:
        for model in MODELS:
            for depth in (1, 2):
                short, long = fitted[model][depth]
                ls, ns = short.losses_for_week(w, byweek, arrays, valid)
                ll, nl = long.losses_for_week(w, byweek, arrays, valid)
                if set(ls) != set(ll):
                    raise RuntimeError(f"paired target mismatch week={w} model={model} depth={depth}")
                if ns != nl:
                    raise RuntimeError(f"paired target count mismatch week={w} model={model} depth={depth}")
                out[depth][model].update({k: ls[k] - ll[k] for k in ls})
                rows[depth][w] = max(rows[depth][w], ns)
    return out, {str(d): dict(v) for d, v in rows.items()}


def reverse_label_rows(weeks, byweek, gains):
    rows = []
    unresolved = defaultdict(int)
    for w in weeks:
        n = len(byweek[w])
        event_by_seq = {int(r["sequence_index"]): r["event_id"] for r in byweek[w]}
        for i in range(n):
            g1 = {}
            g2 = {}
            ok = True
            for model in MODELS:
                v1 = gains[1][model].get((w, i + 1))
                v2 = gains[2][model].get((w, i + 2))
                if v1 is None or v2 is None:
                    ok = False
                    break
                g1[model] = float(v1)
                g2[model] = float(v2)
            if not ok:
                unresolved[w] += 1
                continue
            d1_all = all(v > 0 for v in g1.values())
            d2_all = all(v > 0 for v in g2.values())
            exact = bool(d1_all and not d2_all)
            rows.append({
                "week_sunday": w,
                "origin_sequence_index": int(i),
                "origin_event_id": event_by_seq.get(i),
                "reverse_exact_d1": exact,
                "reverse_consensus_d1_positive": bool(d1_all),
                "reverse_consensus_d2_positive": bool(d2_all),
                "reverse_incremental_gain_d1": g1,
                "reverse_incremental_gain_d2": g2,
                "reverse_d1_min_gain": float(min(g1.values())),
                "reverse_d2_min_gain": float(min(g2.values())),
            })
    return rows, dict(unresolved)


def confusion_metrics(rows, frozen):
    tp = fp = tn = fn = 0
    frozen_positive_total = sum(int(y) for y in frozen.values())
    frozen_positive_eligible = 0
    for r in rows:
        key = (r["week_sunday"], int(r["origin_sequence_index"]))
        if key not in frozen:
            continue
        y = bool(frozen[key])
        p = bool(r["reverse_exact_d1"])
        frozen_positive_eligible += int(y)
        if p and y:
            tp += 1
        elif p and not y:
            fp += 1
        elif not p and y:
            fn += 1
        else:
            tn += 1
    n = tp + fp + tn + fn
    if not n:
        return {"n": 0}
    prevalence = (tp + fn) / n
    pred_rate = (tp + fp) / n
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    bal = 0.5 * (recall + specificity)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = ((tp * tn - fp * fn) / denom) if denom else 0.0
    precision_lift = precision / prevalence if prevalence > 0 else None
    prevalence_ratio = pred_rate / prevalence if prevalence > 0 else None
    pos_coverage = frozen_positive_eligible / frozen_positive_total if frozen_positive_total else None
    return {
        "n": int(n),
        "tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn),
        "true_prevalence": float(prevalence),
        "predicted_prevalence": float(pred_rate),
        "prevalence_ratio": None if prevalence_ratio is None else float(prevalence_ratio),
        "precision": float(precision),
        "recall": float(recall),
        "specificity": float(specificity),
        "balanced_accuracy": float(bal),
        "f1": float(f1),
        "mcc": float(mcc),
        "precision_lift_vs_prevalence": None if precision_lift is None else float(precision_lift),
        "frozen_positive_total": int(frozen_positive_total),
        "frozen_positive_eligible": int(frozen_positive_eligible),
        "true_positive_coverage": None if pos_coverage is None else float(pos_coverage),
    }


def gate_block(name, metrics):
    g = GATE[name]
    if not metrics.get("n"):
        return False, ["no comparable rows"]
    failures = []
    checks = (
        (metrics["mcc"] >= g["min_mcc"], f"mcc {metrics['mcc']:.6f} < {g['min_mcc']}"),
        (metrics["balanced_accuracy"] >= g["min_balanced_accuracy"], f"balanced_accuracy {metrics['balanced_accuracy']:.6f} < {g['min_balanced_accuracy']}"),
        (metrics["precision_lift_vs_prevalence"] is not None and metrics["precision_lift_vs_prevalence"] >= g["min_precision_lift"], f"precision_lift {metrics['precision_lift_vs_prevalence']} < {g['min_precision_lift']}"),
        (metrics["true_positive_coverage"] is not None and metrics["true_positive_coverage"] >= g["min_true_positive_coverage"], f"true_positive_coverage {metrics['true_positive_coverage']} < {g['min_true_positive_coverage']}"),
        (metrics["prevalence_ratio"] is not None and metrics["prevalence_ratio"] >= g["prevalence_ratio_low"], f"prevalence_ratio {metrics['prevalence_ratio']} < {g['prevalence_ratio_low']}"),
        (metrics["prevalence_ratio"] is not None and metrics["prevalence_ratio"] <= g["prevalence_ratio_high"], f"prevalence_ratio {metrics['prevalence_ratio']} > {g['prevalence_ratio_high']}"),
    )
    for ok, msg in checks:
        if not ok:
            failures.append(msg)
    return not failures, failures


def subset_frozen(frozen, weeks):
    wset = set(weeks)
    return {k: v for k, v in frozen.items() if k[0] in wset}


def write_gz_rows(path, rows):
    with gzip.open(path, "wt") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--held", required=True)
    ap.add_argument("--base-lineage", required=True)
    ap.add_argument("--held-lineage", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base_byweek = pilot.load_rows(a.base)
    held_byweek = pilot.load_rows(a.held)
    base_weeks = sorted(base_byweek)
    held_weeks = sorted(held_byweek)
    if len(base_weeks) != 54:
        raise SystemExit(f"expected frozen 54-week base, got {len(base_weeks)}")
    if len(held_weeks) != 1:
        raise SystemExit(f"expected one held week, got {held_weeks}")

    discovery = base_weeks[18:36]
    validation = base_weeks[36:48]
    confirmation = base_weeks[48:54]
    backcast = base_weeks[0:18]
    if len(discovery) != 18 or len(validation) != 12 or len(confirmation) != 6 or len(backcast) != 18:
        raise SystemExit("D1 chronology split drift")

    all_byweek = dict(base_byweek)
    all_byweek.update(held_byweek)
    arrays, valid = pilot.make_view(all_byweek, "full")

    base_frozen, base_frozen_counts = load_frozen_labels(a.base_lineage)
    held_frozen, held_frozen_counts = load_frozen_labels(a.held_lineage)

    disc_set, val_set, conf_set = set(discovery), set(validation), set(confirmation)
    disc_frozen_n = sum(int(v) for (w, _), v in base_frozen.items() if w in disc_set)
    val_frozen_n = sum(int(v) for (w, _), v in base_frozen.items() if w in val_set)
    conf_frozen_n = sum(int(v) for (w, _), v in base_frozen.items() if w in conf_set)
    held_frozen_n = sum(int(v) for v in held_frozen.values())
    expected = (8530, 5907, 2991, 1409)
    actual = (disc_frozen_n, val_frozen_n, conf_frozen_n, held_frozen_n)
    if actual != expected:
        raise SystemExit(f"frozen exact-D1 count drift expected={expected} actual={actual}")

    fitted, tuning = build_gain_models(discovery, all_byweek, arrays, valid)

    block_results = {}
    all_blocks = {
        "validation": (validation, subset_frozen(base_frozen, validation)),
        "confirmation": (confirmation, subset_frozen(base_frozen, confirmation)),
        "held": (held_weeks, held_frozen),
    }
    for name, (weeks, frozen) in all_blocks.items():
        gains, gain_rows = gains_for_weeks(weeks, fitted, all_byweek, arrays, valid)
        reverse_rows, unresolved = reverse_label_rows(weeks, all_byweek, gains)
        metrics = confusion_metrics(reverse_rows, frozen)
        passed, failures = gate_block(name, metrics)
        block_results[name] = {
            "weeks": weeks,
            "metrics": metrics,
            "gate_passed": bool(passed),
            "gate_failures": failures,
            "gain_target_rows": gain_rows,
            "unresolved_origins_by_week": unresolved,
        }

    overall_pass = all(block_results[k]["gate_passed"] for k in ("validation", "confirmation", "held"))

    backcast_rows_out = []
    backcast_audit = {
        "applied": False,
        "candidate_exact_d1_n": 0,
        "eligible_origin_n": 0,
        "unresolved_origin_n": 0,
        "weeks": backcast,
    }
    if overall_pass:
        gains, gain_rows = gains_for_weeks(backcast, fitted, all_byweek, arrays, valid)
        reverse_rows, unresolved = reverse_label_rows(backcast, all_byweek, gains)
        positives = []
        for r in reverse_rows:
            if not r["reverse_exact_d1"]:
                continue
            q = dict(r)
            q["label_source"] = SOURCE_TAG
            q["forward_oot_validation_credit"] = False
            q["phase1_lineage_rewritten"] = False
            q["profit_used_for_membership"] = False
            q["realized_duration_used_for_membership"] = False
            positives.append(q)
        backcast_rows_out = positives
        backcast_audit = {
            "applied": True,
            "candidate_exact_d1_n": int(len(positives)),
            "eligible_origin_n": int(len(reverse_rows)),
            "unresolved_origin_n": int(sum(unresolved.values())),
            "unresolved_origins_by_week": unresolved,
            "gain_target_rows": gain_rows,
            "weeks": backcast,
        }

    rows_path = out_dir / "NG_EXHAUSTION_D1_REVERSE_BACKCAST_ROWS_20260818.jsonl.gz"
    write_gz_rows(rows_path, backcast_rows_out)

    result = {
        "status": "D1_REVERSE_BACKCAST_APPLIED" if overall_pass else "D1_REVERSE_BACKCAST_GATE_FAILED_NO_ROWS_APPLIED",
        "method": "STRUCTURALLY_FAITHFUL_REVERSE_INCREMENTAL_GAIN_LABELER",
        "definition": "reverse exact D1 iff all three later-trained models have positive D1 incremental gain and D2 consensus does not remain all-positive",
        "chronology": {
            "prelineage_backcast_weeks": backcast,
            "reverse_labeler_training_weeks": discovery,
            "validation_weeks": validation,
            "untouched_confirmation_weeks": confirmation,
            "held_confirmation_weeks": held_weeks,
        },
        "predeclared_gate": GATE,
        "tuning": tuning,
        "frozen_exact_d1_positive_counts": {
            "discovery": int(disc_frozen_n),
            "validation": int(val_frozen_n),
            "confirmation": int(conf_frozen_n),
            "held": int(held_frozen_n),
        },
        "frozen_lineage_counts_by_week": {
            "base": base_frozen_counts,
            "held": held_frozen_counts,
        },
        "blocks": block_results,
        "overall_gate_passed": bool(overall_pass),
        "backcast": backcast_audit,
        "backcast_rows_path": str(rows_path),
        "backcast_row_tag": SOURCE_TAG,
        "preserve_all_policy": "FAIL_CLOSED_NO_MANUFACTURED_PRELINEAGE_LABELS",
        "membership_target_only": True,
        "profit_used_for_membership": False,
        "realized_duration_used_for_membership": False,
        "promotion_performed": False,
        "protected_mutations": {
            "frozen_detector": False,
            "canonical_54w_base": False,
            "held_rows": False,
            "phase1_lineage": False,
            "phase2": False,
            "runway_clock": False,
            "permanent_frankie": False,
            "frankie1": False,
            "spawn_py": False,
            "ssos_paper_play": False,
        },
    }
    summary_path = out_dir / "NG_EXHAUSTION_D1_REVERSE_BACKCAST_20260818.json"
    summary_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": result["status"],
        "overall_gate_passed": overall_pass,
        "validation": block_results["validation"]["metrics"],
        "confirmation": block_results["confirmation"]["metrics"],
        "held": block_results["held"]["metrics"],
        "backcast_exact_d1_n": backcast_audit["candidate_exact_d1_n"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
