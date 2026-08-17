#!/usr/bin/env python3
"""Price-blind NG exhaustion-family quantification for the 2026-08-16 scratch study.

Family discovery and K selection diagnostics use t<=0 dipole geometry ONLY.
Post-flip dipole behavior is used only as exhaustion-domain validation.
No price field, price leg, displacement, duration, or outcome participates in clustering.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.preprocessing import RobustScaler

from ng_dipole_runway_audit import load_day
from ng_dipole_native_shape_audit import event_rows

ROLL = 20
KS = tuple(range(2, 9))
SEED = 20260816
PRE = 60
POST = 60


def q(xs, p):
    a = sorted(float(x) for x in xs if math.isfinite(float(x)))
    if not a:
        return None
    if len(a) == 1:
        return a[0]
    z = p * (len(a) - 1)
    i = int(math.floor(z)); j = min(i + 1, len(a) - 1); w = z - i
    return a[i] * (1 - w) + a[j] * w


def safe_mean(xs):
    a = [float(x) for x in xs if math.isfinite(float(x))]
    return sum(a) / len(a) if a else float("nan")


def slope(y, lo, hi):
    yy = np.asarray(y[lo:hi], dtype=float)
    if len(yy) < 2:
        return 0.0
    xx = np.arange(len(yy), dtype=float)
    return float(np.polyfit(xx, yy, 1)[0])


def first_cross(y, level):
    for i, v in enumerate(y):
        if float(v) >= level:
            return i
    return len(y) - 1


def row_geometry(r):
    b = np.asarray(r["pre_build"], dtype=float)
    raw = np.asarray(r["pre_raw"], dtype=float)
    peak = float(raw[-1])
    rel = raw / peak if abs(peak) > 1e-12 else np.zeros_like(raw)
    c10 = first_cross(b, 0.10)
    c25 = first_cross(b, 0.25)
    c50 = first_cross(b, 0.50)
    c75 = first_cross(b, 0.75)
    c90 = first_cross(b, 0.90)
    scalars = np.asarray([
        float(r["pre_base10"]),
        math.log1p(abs(float(r["pre_excursion"]))),
        math.log1p(abs(float(r["pre_prominence"]))),
        float(r["peak_abs"]),
        c10 / 60.0, c25 / 60.0, c50 / 60.0, c75 / 60.0, c90 / 60.0,
        max(0, c90 - c10) / 60.0,
        slope(b, 0, 21), slope(b, 20, 41), slope(b, 40, 61),
        slope(b, 40, 61) - slope(b, 20, 41),
        slope(b, 20, 41) - slope(b, 0, 21),
        float(np.std(b)),
        float(np.mean(np.abs(np.diff(b)))) if len(b) > 1 else 0.0,
    ], dtype=float)
    # Whole-curve geometry: normalized baseline-to-spike build plus peak-relative shape.
    curve = np.concatenate([b[::2], rel[::3]])
    return np.concatenate([curve, scalars])


def geom_summary(r):
    b = r["pre_build"]
    c10 = first_cross(b, .10); c50 = first_cross(b, .50); c90 = first_cross(b, .90)
    return {
        "base10": float(r["pre_base10"]),
        "excursion": float(r["pre_excursion"]),
        "prominence": float(r["pre_prominence"]),
        "rise10_s_before_t0": 60 - c10,
        "rise50_s_before_t0": 60 - c50,
        "rise90_s_before_t0": 60 - c90,
        "build_10_to_90_s": max(0, c90 - c10),
        "slope_early": slope(b, 0, 21),
        "slope_mid": slope(b, 20, 41),
        "slope_late": slope(b, 40, 61),
        "late_minus_mid": slope(b, 40, 61) - slope(b, 20, 41),
    }


def fit_k(X, k):
    km = KMeans(n_clusters=k, random_state=SEED, n_init=30, max_iter=500)
    labels = km.fit_predict(X)
    return km, labels


def stable_label_order(labels, rows, k):
    """Give arbitrary KMeans clusters deterministic pre-only labels.

    Primary key is median 50% rise time (seconds before t0), then late slope and excursion.
    No post-flip or price information is consulted.
    """
    keys = []
    for c in range(k):
        rr = [r for r, z in zip(rows, labels) if int(z) == c]
        gs = [geom_summary(r) for r in rr]
        key = (
            q([g["rise50_s_before_t0"] for g in gs], .5) or 0.0,
            q([g["slope_late"] for g in gs], .5) or 0.0,
            q([abs(g["excursion"]) for g in gs], .5) or 0.0,
        )
        keys.append((key, c))
    order = [c for _, c in sorted(keys)]
    remap = {old: i for i, old in enumerate(order)}
    return np.asarray([remap[int(z)] for z in labels], dtype=int), remap


def family_geometry(rows, labels, k):
    out = {}
    days = sorted({r["day"] for r in rows})
    for c in range(k):
        rr = [r for r, z in zip(rows, labels) if int(z) == c]
        gs = [geom_summary(r) for r in rr]
        out[f"F{c+1}"] = {
            "n": len(rr),
            "fraction": len(rr) / len(rows),
            "by_day": {d: sum(1 for r in rr if r["day"] == d) for d in days},
            "pre_geometry_median": {
                key: q([g[key] for g in gs], .5)
                for key in gs[0]
            },
            "pre_geometry_iqr": {
                key: [q([g[key] for g in gs], .25), q([g[key] for g in gs], .75)]
                for key in gs[0]
            },
        }
    return out


def loo_stability(X, rows, global_km, global_labels, k):
    days = sorted({r["day"] for r in rows})
    agreements = []
    centroid_distances = []
    margins = []
    folds = {}
    for day in days:
        tr = np.asarray([i for i, r in enumerate(rows) if r["day"] != day], dtype=int)
        te = np.asarray([i for i, r in enumerate(rows) if r["day"] == day], dtype=int)
        km, _ = fit_k(X[tr], k)
        cost = cdist(km.cluster_centers_, global_km.cluster_centers_)
        rr, cc = linear_sum_assignment(cost)
        mapping = {int(a): int(b) for a, b in zip(rr, cc)}
        pred_raw = km.predict(X[te])
        pred = np.asarray([mapping[int(z)] for z in pred_raw], dtype=int)
        agree = float(np.mean(pred == global_labels[te]))
        agreements.append(agree)
        cd = float(np.mean([cost[a, b] for a, b in zip(rr, cc)]))
        centroid_distances.append(cd)
        d = cdist(X[te], km.cluster_centers_)
        if d.shape[1] >= 2:
            ss = np.sort(d, axis=1)
            margins.extend((ss[:, 1] - ss[:, 0]).tolist())
        folds[day] = {
            "n_heldout": int(len(te)),
            "assignment_agreement_vs_global_preonly": agree,
            "matched_centroid_mean_distance": cd,
        }
    return {
        "mean_assignment_agreement": float(np.mean(agreements)),
        "min_assignment_agreement": float(np.min(agreements)),
        "mean_matched_centroid_distance": float(np.mean(centroid_distances)),
        "heldout_centroid_margin_median": q(margins, .5),
        "folds": folds,
    }


def post_validation(rows, labels, k):
    """Validate with dipole exhaustion ONLY; still no price use."""
    cents = []
    within = []
    fam = {}
    for c in range(k):
        rr = [r for r, z in zip(rows, labels) if int(z) == c]
        curves = []
        for r in rr:
            peak = float(r["pre_raw"][-1])
            if abs(peak) < 1e-12:
                continue
            curves.append(np.asarray(r["post_raw"], dtype=float) / peak)
        A = np.vstack(curves)
        cent = np.median(A, axis=0)
        cents.append(cent)
        rms = np.sqrt(np.mean((A - cent) ** 2, axis=1))
        within.extend(rms.tolist())
        fam[f"F{c+1}"] = {
            "n": len(rr),
            "post_curve_rms_to_family_median": float(np.median(rms)),
            "exh_t25_median_s": q([61 if r["exh_t25_s"] is None else r["exh_t25_s"] for r in rr], .5),
            "exh_t25_iqr_s": [
                q([61 if r["exh_t25_s"] is None else r["exh_t25_s"] for r in rr], .25),
                q([61 if r["exh_t25_s"] is None else r["exh_t25_s"] for r in rr], .75),
            ],
            "exh_zero_median_s": q([61 if r["exh_zero_s"] is None else r["exh_zero_s"] for r in rr], .5),
        }
    between = []
    for i in range(k):
        for j in range(i + 1, k):
            between.append(float(np.sqrt(np.mean((cents[i] - cents[j]) ** 2))))
    return {
        "within_family_post_rms_median": q(within, .5),
        "between_family_post_centroid_rms_median": q(between, .5),
        "within_to_between_ratio": None if not between else (q(within, .5) / q(between, .5)),
        "families": fam,
    }


def candidate_metrics(X, rows, k):
    km, raw_labels = fit_k(X, k)
    labels, remap = stable_label_order(raw_labels, rows, k)
    # Reorder global centroid array to the deterministic family numbering.
    inv = {new: old for old, new in remap.items()}
    ordered_centers = np.vstack([km.cluster_centers_[inv[i]] for i in range(k)])
    global_km = KMeans(n_clusters=k, random_state=SEED, n_init=1)
    global_km.cluster_centers_ = ordered_centers
    global_km.n_features_in_ = X.shape[1]
    counts = np.bincount(labels, minlength=k)
    sil = float(silhouette_score(X, labels, sample_size=min(2400, len(X)), random_state=SEED))
    db = float(davies_bouldin_score(X, labels))
    ch = float(calinski_harabasz_score(X, labels))
    stab = loo_stability(X, rows, global_km, labels, k)
    post = post_validation(rows, labels, k)
    return {
        "k": k,
        "silhouette": sil,
        "davies_bouldin": db,
        "calinski_harabasz": ch,
        "min_family_fraction": float(np.min(counts) / len(labels)),
        "max_family_fraction": float(np.max(counts) / len(labels)),
        "loo_stability": stab,
        "post_exhaustion_validation": post,
        "family_geometry": family_geometry(rows, labels, k),
    }, labels


def render_families(rows, labels, k, path):
    fig, axs = plt.subplots(k, 1, figsize=(12, 3.3 * k), sharex=True)
    if k == 1:
        axs = [axs]
    x = np.arange(-60, 61)
    rng = np.random.default_rng(SEED)
    for c, ax in enumerate(axs):
        rr = [r for r, z in zip(rows, labels) if int(z) == c]
        take = rng.choice(len(rr), size=min(70, len(rr)), replace=False)
        normalized = []
        for i in take:
            r = rr[int(i)]
            peak = float(r["pre_raw"][-1])
            curve = np.asarray(r["pre_raw"] + r["post_raw"][1:], dtype=float) / peak
            normalized.append(curve)
            ax.plot(x, curve, alpha=.08, linewidth=.7)
        allc = []
        for r in rr:
            peak = float(r["pre_raw"][-1])
            allc.append(np.asarray(r["pre_raw"] + r["post_raw"][1:], dtype=float) / peak)
        A = np.vstack(allc)
        med = np.median(A, axis=0)
        lo = np.quantile(A, .25, axis=0); hi = np.quantile(A, .75, axis=0)
        ax.fill_between(x, lo, hi, alpha=.18)
        ax.plot(x, med, linewidth=2.0, label=f"F{c+1} median; n={len(rr)}")
        ax.axvline(0, linestyle="--", linewidth=1)
        ax.axhline(0, linewidth=.7)
        ax.legend(loc="best")
        ax.set_ylabel("oriented dipole / t0 peak")
    axs[-1].set_xlabel("seconds from dipole t0")
    fig.suptitle(f"NG roll20 price-blind exhaustion families, K={k}\nFamilies use t<=0 only; right side is held-out exhaustion-domain validation")
    fig.tight_layout(rect=[0, 0, 1, .97])
    fig.savefig(path, dpi=165)
    plt.close(fig)


def render_k_metrics(metrics, path):
    ks = [m["k"] for m in metrics]
    sil = [m["silhouette"] for m in metrics]
    stab = [m["loo_stability"]["mean_assignment_agreement"] for m in metrics]
    ratio = [m["post_exhaustion_validation"]["within_to_between_ratio"] for m in metrics]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(ks, sil, marker="o", label="pre-only silhouette")
    ax.plot(ks, stab, marker="o", label="leave-one-day-out assignment stability")
    ax.plot(ks, ratio, marker="o", label="post within/between dispersion (lower better)")
    ax.set_xlabel("candidate family count K")
    ax.set_xticks(ks)
    ax.grid(alpha=.2)
    ax.legend()
    ax.set_title("NG exhaustion family-count diagnostics (no price used)")
    fig.tight_layout()
    fig.savefig(path, dpi=165)
    plt.close(fig)


def main(paths):
    days = [load_day(p) for p in paths]
    rows = []
    by_day = {}
    for d in days:
        rr = event_rows(d, ROLL)
        rows.extend(rr)
        by_day[d.day] = len(rr)
    feats = np.vstack([row_geometry(r) for r in rows])
    scaler = RobustScaler(quantile_range=(20, 80)).fit(feats)
    X = scaler.transform(feats)

    metrics = []
    labels_by_k = {}
    for k in KS:
        m, labels = candidate_metrics(X, rows, k)
        metrics.append(m)
        labels_by_k[k] = labels
        if k in (3, 4, 5):
            render_families(rows, labels, k, f"ng_exhaustion_families_k{k}.png")
    render_k_metrics(metrics, "ng_exhaustion_family_count_metrics.png")

    out = {
        "analysis": "NG roll20 exhaustion-family quantification; clustering t<=0 only",
        "price_used_for_family_discovery": False,
        "post_validation_domain": "dipole exhaustion only",
        "roll_s": ROLL,
        "n_events": len(rows),
        "by_day": by_day,
        "feature_contract": {
            "curve": "pre_build every 2s + pre_raw/t0_peak every 3s, t=-60..0 only",
            "geometry": "baseline, excursion, prominence, rise times, early/mid/late slopes, curvature, roughness",
            "scaler": "RobustScaler 20-80 percentile",
            "candidate_k": list(KS),
        },
        "candidate_metrics": metrics,
        "renders": [
            "ng_exhaustion_family_count_metrics.png",
            "ng_exhaustion_families_k3.png",
            "ng_exhaustion_families_k4.png",
            "ng_exhaustion_families_k5.png",
        ],
    }
    Path("ng_exhaustion_family_quantification.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({"n": len(rows), "by_day": by_day, "metrics": [
        {"k": m["k"], "sil": m["silhouette"], "stab": m["loo_stability"]["mean_assignment_agreement"],
         "post_ratio": m["post_exhaustion_validation"]["within_to_between_ratio"],
         "min_frac": m["min_family_fraction"]}
        for m in metrics
    ]}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: ng_exhaustion_family_quantify_20260816.py DAY.jsonl.gz ...")
    main(sys.argv[1:])
