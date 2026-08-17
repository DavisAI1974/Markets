#!/usr/bin/env python3
"""Price-blind NG exhaustion-family quantification, geometry-balanced v2.

WHY V2
------
The raw roll-20 event population contains many exact saturated/plateau left-side
curves. Ordinary event-weighted K-means can let that repeated geometry dominate
the objective and collapse minority morphologies. Family discovery is a shape-
vocabulary question, so this audit fits candidate prototypes on UNIQUE/rounded
pre-flip geometries, then assigns every event back to its nearest prototype.
Frequency is reported afterward; duplicate shapes do not get extra votes while
prototypes are being discovered.

Hard rules:
- t<=0 dipole geometry only for all family discovery, K diagnostics, and labels.
- no price, price leg, duration, displacement, pivot, or post-flip field is used.
- post-flip dipole exhaustion is used only after labels are frozen as an
  exhaustion-domain validation.
- K=2..8 are all reported descriptively; no K is chosen from price outcomes.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.preprocessing import RobustScaler

from ng_dipole_runway_audit import load_day
from ng_dipole_native_shape_audit import event_rows

ROLL = 20
KS = tuple(range(2, 9))
SEED = 20260816
ROUND_DECIMALS = 5


def quantile(xs, p):
    a = sorted(float(x) for x in xs if math.isfinite(float(x)))
    if not a:
        return None
    if len(a) == 1:
        return a[0]
    z = p * (len(a) - 1)
    i = int(math.floor(z)); j = min(i + 1, len(a) - 1); w = z - i
    return a[i] * (1 - w) + a[j] * w


def slope(y, lo, hi):
    yy = np.asarray(y[lo:hi], dtype=float)
    if len(yy) < 2 or float(np.ptp(yy)) < 1e-15:
        return 0.0
    xx = np.arange(len(yy), dtype=float)
    return float(np.polyfit(xx, yy, 1)[0])


def first_ge(y, level):
    for i, v in enumerate(y):
        if float(v) >= level:
            return i
    return len(y) - 1


def geom_scalar(r):
    b = np.asarray(r["pre_build"], dtype=float)
    c10 = first_ge(b, .10); c25 = first_ge(b, .25); c50 = first_ge(b, .50)
    c75 = first_ge(b, .75); c90 = first_ge(b, .90)
    return {
        "base10": float(r["pre_base10"]),
        "excursion": float(r["pre_excursion"]),
        "prominence": float(r["pre_prominence"]),
        "rise10_s_before_t0": 60 - c10,
        "rise25_s_before_t0": 60 - c25,
        "rise50_s_before_t0": 60 - c50,
        "rise75_s_before_t0": 60 - c75,
        "rise90_s_before_t0": 60 - c90,
        "build10_to_90_s": max(0, c90 - c10),
        "slope_early": slope(b, 0, 21),
        "slope_mid": slope(b, 20, 41),
        "slope_late": slope(b, 40, 61),
        "late_minus_mid": slope(b, 40, 61) - slope(b, 20, 41),
        "mid_minus_early": slope(b, 20, 41) - slope(b, 0, 21),
        "roughness": float(np.mean(np.abs(np.diff(b)))) if len(b) > 1 else 0.0,
    }


def feature(r):
    raw = np.asarray(r["pre_raw"], dtype=float)
    peak = float(raw[-1])
    rel = raw / peak if abs(peak) > 1e-12 else np.zeros_like(raw)
    b = np.asarray(r["pre_build"], dtype=float)
    g = geom_scalar(r)
    scalar = np.asarray([
        g["base10"], math.log1p(abs(g["excursion"])), math.log1p(abs(g["prominence"])),
        g["rise10_s_before_t0"] / 60.0, g["rise25_s_before_t0"] / 60.0,
        g["rise50_s_before_t0"] / 60.0, g["rise75_s_before_t0"] / 60.0,
        g["rise90_s_before_t0"] / 60.0, g["build10_to_90_s"] / 60.0,
        g["slope_early"], g["slope_mid"], g["slope_late"],
        g["late_minus_mid"], g["mid_minus_early"], g["roughness"],
        float(np.std(b)),
    ], dtype=float)
    # Dense enough to keep morphology, sparse enough to avoid overweighting 61 adjacent seconds.
    return np.concatenate([b[::2], rel[::2], scalar])


def unique_geometry(X):
    rounded = np.round(X, ROUND_DECIMALS)
    _, idx = np.unique(rounded, axis=0, return_index=True)
    idx = np.sort(idx)
    return X[idx], idx


def fit_balanced(X, k):
    U, idx = unique_geometry(X)
    if len(U) < k:
        raise RuntimeError(f"only {len(U)} unique pre-flip geometries for K={k}")
    km = KMeans(n_clusters=k, random_state=SEED, n_init=50, max_iter=1000)
    ulab = km.fit_predict(U)
    if len(set(int(x) for x in ulab)) != k:
        raise RuntimeError(f"K={k} collapsed on {len(U)} unique geometries")
    centers = np.asarray(km.cluster_centers_, dtype=float)
    full = np.argmin(cdist(X, centers), axis=1).astype(int)
    return centers, full, U, ulab


def deterministic_order(rows, labels, centers):
    keys = []
    for c in range(len(centers)):
        rr = [r for r, z in zip(rows, labels) if int(z) == c]
        gs = [geom_scalar(r) for r in rr]
        key = (
            quantile([g["rise50_s_before_t0"] for g in gs], .5) or 0.0,
            quantile([g["slope_late"] for g in gs], .5) or 0.0,
            quantile([abs(g["excursion"]) for g in gs], .5) or 0.0,
        )
        keys.append((key, c))
    order = [c for _, c in sorted(keys)]
    remap = {old: new for new, old in enumerate(order)}
    new_labels = np.asarray([remap[int(z)] for z in labels], dtype=int)
    new_centers = np.vstack([centers[old] for old in order])
    return new_labels, new_centers, remap


def family_summary(rows, labels, k):
    days = sorted({r["day"] for r in rows})
    out = {}
    for c in range(k):
        rr = [r for r, z in zip(rows, labels) if int(z) == c]
        gs = [geom_scalar(r) for r in rr]
        keys = list(gs[0])
        out[f"F{c+1}"] = {
            "n": len(rr),
            "fraction": len(rr) / len(rows),
            "by_day": {d: sum(1 for r in rr if r["day"] == d) for d in days},
            "pre_median": {key: quantile([g[key] for g in gs], .5) for key in keys},
            "pre_iqr": {key: [quantile([g[key] for g in gs], .25), quantile([g[key] for g in gs], .75)] for key in keys},
            "exact_flat_pre_fraction": sum(1 for r in rr if np.std(np.asarray(r["pre_raw"], dtype=float)) < 1e-12) / len(rr),
        }
    return out


def loo_stability(X, rows, global_labels, global_centers, k):
    folds = {}; agreements = []; centroid_shift = []
    for day in sorted({r["day"] for r in rows}):
        tr = np.asarray([i for i, r in enumerate(rows) if r["day"] != day], dtype=int)
        te = np.asarray([i for i, r in enumerate(rows) if r["day"] == day], dtype=int)
        centers, _, _, _ = fit_balanced(X[tr], k)
        rr, cc = linear_sum_assignment(cdist(centers, global_centers))
        mapping = {int(local): int(global_) for local, global_ in zip(rr, cc)}
        local_pred = np.argmin(cdist(X[te], centers), axis=1)
        pred = np.asarray([mapping[int(z)] for z in local_pred], dtype=int)
        agreement = float(np.mean(pred == global_labels[te]))
        shift = float(np.mean([np.linalg.norm(centers[a] - global_centers[b]) for a, b in zip(rr, cc)]))
        agreements.append(agreement); centroid_shift.append(shift)
        folds[day] = {"n_heldout": int(len(te)), "assignment_agreement": agreement, "matched_centroid_shift": shift}
    return {
        "mean_assignment_agreement": float(np.mean(agreements)),
        "min_assignment_agreement": float(np.min(agreements)),
        "mean_matched_centroid_shift": float(np.mean(centroid_shift)),
        "folds": folds,
    }


def post_validation(rows, labels, k):
    medians = []; within = []; fam = {}
    for c in range(k):
        rr = [r for r, z in zip(rows, labels) if int(z) == c]
        A = []
        for r in rr:
            peak = float(r["pre_raw"][-1])
            A.append(np.asarray(r["post_raw"], dtype=float) / peak)
        A = np.vstack(A)
        med = np.median(A, axis=0); medians.append(med)
        rms = np.sqrt(np.mean((A - med) ** 2, axis=1)); within.extend(rms.tolist())
        t25 = [61 if r["exh_t25_s"] is None else r["exh_t25_s"] for r in rr]
        z0 = [61 if r["exh_zero_s"] is None else r["exh_zero_s"] for r in rr]
        fam[f"F{c+1}"] = {
            "post_rms_to_family_median": quantile(rms, .5),
            "exh_t25_median_s": quantile(t25, .5),
            "exh_t25_iqr_s": [quantile(t25, .25), quantile(t25, .75)],
            "exh_zero_median_s": quantile(z0, .5),
        }
    between = [float(np.sqrt(np.mean((medians[i] - medians[j]) ** 2))) for i in range(k) for j in range(i+1, k)]
    w = quantile(within, .5); b = quantile(between, .5)
    return {"within_post_rms_median": w, "between_post_centroid_rms_median": b,
            "within_to_between_ratio": None if not b else w / b, "families": fam}


def metrics_for_k(X, rows, k):
    centers, labels, U, ulab = fit_balanced(X, k)
    labels, centers, remap = deterministic_order(rows, labels, centers)
    # Re-label unique geometries against reordered centers so diagnostics use the same family IDs.
    ulab_ordered = np.argmin(cdist(U, centers), axis=1)
    event_sample = min(2400, len(X))
    event_sil = silhouette_score(X, labels, sample_size=event_sample, random_state=SEED)
    return {
        "k": k,
        "geometry_balanced_unique_n": len(U),
        "geometry_silhouette": float(silhouette_score(U, ulab_ordered)),
        "event_silhouette_after_assignment": float(event_sil),
        "geometry_davies_bouldin": float(davies_bouldin_score(U, ulab_ordered)),
        "geometry_calinski_harabasz": float(calinski_harabasz_score(U, ulab_ordered)),
        "min_family_fraction": float(np.min(np.bincount(labels, minlength=k)) / len(labels)),
        "max_family_fraction": float(np.max(np.bincount(labels, minlength=k)) / len(labels)),
        "loo_cross_day": loo_stability(X, rows, labels, centers, k),
        "post_exhaustion_validation": post_validation(rows, labels, k),
        "families": family_summary(rows, labels, k),
    }, labels, centers


def render_families(rows, labels, k, path):
    fig, axs = plt.subplots(k, 1, figsize=(12, 3.1*k), sharex=True)
    if k == 1: axs = [axs]
    x = np.arange(-60, 61)
    rng = np.random.default_rng(SEED)
    for c, ax in enumerate(axs):
        rr = [r for r, z in zip(rows, labels) if int(z) == c]
        idx = rng.choice(len(rr), size=min(90, len(rr)), replace=False)
        curves = []
        for r in rr:
            peak = float(r["pre_raw"][-1])
            curves.append(np.asarray(r["pre_raw"] + r["post_raw"][1:], dtype=float) / peak)
        A = np.vstack(curves)
        for i in idx:
            ax.plot(x, A[int(i)], linewidth=.65, alpha=.055)
        med = np.median(A, axis=0); lo = np.quantile(A,.25,axis=0); hi=np.quantile(A,.75,axis=0)
        ax.fill_between(x, lo, hi, alpha=.16)
        ax.plot(x, med, linewidth=2.0, label=f"F{c+1} median; n={len(rr)}")
        ax.axvline(0, linestyle="--", linewidth=1); ax.axhline(0, linewidth=.7)
        ax.legend(loc="best"); ax.set_ylabel("dipole / t0 peak")
    axs[-1].set_xlabel("seconds from dipole t0")
    fig.suptitle(f"NG roll20 price-blind families K={k}\nLeft side defines family; right side shown only for exhaustion validation")
    fig.tight_layout(rect=[0,0,1,.97]); fig.savefig(path,dpi=165); plt.close(fig)


def render_metrics(ms, path):
    ks=[m["k"] for m in ms]
    fig, ax=plt.subplots(figsize=(10,6))
    ax.plot(ks,[m["geometry_silhouette"] for m in ms],marker="o",label="geometry-balanced silhouette")
    ax.plot(ks,[m["loo_cross_day"]["mean_assignment_agreement"] for m in ms],marker="o",label="leave-one-day-out assignment agreement")
    ax.plot(ks,[m["post_exhaustion_validation"]["within_to_between_ratio"] for m in ms],marker="o",label="post within/between RMS (lower better)")
    ax.set_xticks(ks); ax.set_xlabel("candidate K"); ax.grid(alpha=.2); ax.legend();
    ax.set_title("NG exhaustion family-count diagnostics — no price used")
    fig.tight_layout(); fig.savefig(path,dpi=165); plt.close(fig)


def main(paths):
    rows=[]; by_day={}
    for p in paths:
        d=load_day(p); rr=event_rows(d,ROLL); rows.extend(rr); by_day[d.day]=len(rr)
    rawF=np.vstack([feature(r) for r in rows])
    scaler=RobustScaler(quantile_range=(20,80)).fit(rawF); X=scaler.transform(rawF)
    U,_=unique_geometry(X)
    flat=sum(1 for r in rows if np.std(np.asarray(r["pre_raw"],dtype=float))<1e-12)
    zero_exc=sum(1 for r in rows if abs(float(r["pre_excursion"]))<1e-12)
    diagnostics={
        "n_events":len(rows), "by_day":by_day, "unique_pre_geometry_n":len(U),
        "unique_pre_geometry_fraction":len(U)/len(rows),
        "exact_flat_pre_n":flat, "exact_flat_pre_fraction":flat/len(rows),
        "zero_excursion_n":zero_exc, "zero_excursion_fraction":zero_exc/len(rows),
        "geometry_balance_rule":f"unique rounded scaled pre-only feature vectors at {ROUND_DECIMALS} decimals",
    }
    ms=[]; labels_by_k={}
    for k in KS:
        m,lab,_=metrics_for_k(X,rows,k); ms.append(m); labels_by_k[k]=lab
        if k in (3,4,5): render_families(rows,lab,k,f"ng_exhaustion_families_v2_k{k}.png")
    render_metrics(ms,"ng_exhaustion_family_count_metrics_v2.png")
    out={
        "analysis":"NG roll20 geometry-balanced exhaustion-family quantification v2",
        "family_discovery_uses_price":False,
        "family_discovery_uses_post_flip":False,
        "post_validation_domain":"dipole exhaustion only",
        "diagnostics":diagnostics,
        "candidate_metrics":ms,
        "renders":["ng_exhaustion_family_count_metrics_v2.png","ng_exhaustion_families_v2_k3.png","ng_exhaustion_families_v2_k4.png","ng_exhaustion_families_v2_k5.png"],
    }
    Path("ng_exhaustion_family_quantification_v2.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps({"diagnostics":diagnostics,"candidate_summary":[{
        "k":m["k"],"geo_sil":m["geometry_silhouette"],"event_sil":m["event_silhouette_after_assignment"],
        "loo":m["loo_cross_day"]["mean_assignment_agreement"],"post_ratio":m["post_exhaustion_validation"]["within_to_between_ratio"],
        "min_frac":m["min_family_fraction"]} for m in ms]},indent=2))

if __name__=="__main__":
    if len(sys.argv)<2: raise SystemExit("usage: script DAY.jsonl.gz ...")
    main(sys.argv[1:])
