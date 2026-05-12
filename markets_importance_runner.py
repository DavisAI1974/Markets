"""
markets_importance_runner.py -- runs F.1 permutation importance from the
cloned operator_importance module against Markets chunk features.

Purpose: when the tier search produces a cluster of correlated features that
all hit the same n, score, and CI on the same regime (a redundancy signature),
this runner uses cross-predictor permutation importance to disentangle them.
Features that drive predictions UNIVERSALLY across multiple regression models
are kept; features that only matter under one specific predictor are flagged
as predictor-specific; features that never matter are dead.

Architecture:
  - Pools chunks across (CB, KR, BB-perp) and optional sibling-asset venues.
  - Computes feature values via the existing FEATURE_EXTRACTORS registry.
  - Forward log-returns are the regression target.
  - Builds 4-5 predictors as our "architectures":
      1. LassoCV         (sparse linear baseline)
      2. PolynomialFeatures(d=2) + RidgeCV  (pairwise interactions)
      3. mean_dipole-only OLS  (Pass-17 anchor feature)
      4. mean_ofi-only OLS     (alternative singleton baseline)
      5. Operator family OLS, complexity-adjusted (small fixed library)
  - Each predictor is trained on the first 60% of pooled chunks.
  - PermutationImportance.compute_single (from the cloned operator_importance.py)
    runs against the held-out 40%, using R^2 as the metric.
  - ConsistencyScorer aggregates across predictors and classifies each feature.

Output: JSON report with per-predictor importance, aggregated mean importance,
cross-predictor consistency, and the universal/predictor_specific/dead label.

Reads OD-cloned PermutationImportance, ConsistencyScorer, ImportanceConfig
from this directory's operator_importance.py (the F.1 clone). Does NOT modify
the clone; just consumes its API.

Usage:
    python markets_importance_runner.py --asset ETH \\
        --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json \\
        --bybit-perp-bins eth_bybit_perp_bins.json \\
        --sibling-cb-bins btc_coinbase_bins.json --sibling-kr-bins btc_kraken_bins.json \\
        [--n-permutations 30] [--train-frac 0.6] [--importance-floor 0.001] \\
        --output-report importance_eth.json
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from dataclasses import asdict
from typing import Callable

import numpy as np

from phase1_5_evaluator import FEATURE_EXTRACTORS
from markets_tier_search import (
    forward_log_returns,
    compute_global_feature_values,
    load_all_venue_contexts,
)
# Cloned F.1 module
from operator_importance import (
    PermutationImportance,
    ConsistencyScorer,
    ImportanceConfig,
)


# ---------------------------------------------------------------------------
# Metric: R^2 for regression
# ---------------------------------------------------------------------------

def r2_metric(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """R^2 metric for PermutationImportance to consume. Higher is better."""
    if len(y_true) == 0:
        return 0.0
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if ss_tot < 1e-18:
        return 0.0
    return 1.0 - ss_res / ss_tot


# ---------------------------------------------------------------------------
# Predictor builders. Each returns (predict_fn, status_msg). predict_fn takes
# X of shape (N, n_features) and returns y_hat of shape (N,). The closure is
# stateless w.r.t. fitting -- permutation only perturbs the input matrix.
# ---------------------------------------------------------------------------

def _build_lasso(X_train, y_train) -> tuple[Callable | None, str]:
    try:
        from sklearn.linear_model import LassoCV
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return None, "sklearn not available"
    if len(y_train) < 10:
        return None, f"too few samples ({len(y_train)})"
    scaler = StandardScaler()
    X_s = scaler.fit_transform(X_train)
    cv_folds = min(5, max(2, len(y_train) // 4))
    try:
        model = LassoCV(cv=cv_folds, max_iter=5000, random_state=0).fit(X_s, y_train)
    except Exception as e:
        return None, f"lasso fit failed: {e}"
    return (lambda X: model.predict(scaler.transform(X))), "ok"


def _build_poly_ridge(X_train, y_train) -> tuple[Callable | None, str]:
    try:
        from sklearn.linear_model import RidgeCV
        from sklearn.preprocessing import StandardScaler, PolynomialFeatures
    except ImportError:
        return None, "sklearn not available"
    if len(y_train) < 10:
        return None, f"too few samples ({len(y_train)})"
    scaler = StandardScaler()
    poly = PolynomialFeatures(degree=2, interaction_only=False, include_bias=False)
    X_s = scaler.fit_transform(X_train)
    X_p = poly.fit_transform(X_s)
    try:
        model = RidgeCV(alphas=[0.01, 0.1, 1.0, 10.0, 100.0]).fit(X_p, y_train)
    except Exception as e:
        return None, f"ridge fit failed: {e}"
    return (lambda X: model.predict(poly.transform(scaler.transform(X)))), "ok"


def _build_single_feature_ols(X_train, y_train, feature_idx: int
                                ) -> tuple[Callable | None, str]:
    """y_pred = beta * x_i. Single-feature OLS (no intercept)."""
    if len(y_train) < 5:
        return None, f"too few samples ({len(y_train)})"
    x = X_train[:, feature_idx]
    denom = float(np.sum(x ** 2)) + 1e-12
    beta = float(np.sum(x * y_train) / denom)
    def predict(X):
        return beta * X[:, feature_idx]
    return predict, "ok"


def _build_operator_family(X_train, y_train, feature_names: list[str],
                             complexity_lambda: float = 0.05
                             ) -> tuple[Callable | None, str]:
    """Try a small library of hand-curated linear-in-coefficients forms; pick
    the best by complexity-adjusted in-sample R^2; return its predict_fn.
    Library forms (each skipped if a required feature is absent):
      O0: intercept-only
      O1: mean_dipole only
      O2: mean_dipole + volume_zscore
      O3: mean_dipole + mean_dipole^2
      O4: mean_dipole * |mean_dipole|
      O5: mean_dipole + mean_ofi
      O6: mean_dipole * volume_zscore interaction
    """
    name_to_idx = {n: i for i, n in enumerate(feature_names)}
    n = len(y_train)
    if n < 5:
        return None, f"too few samples ({n})"
    candidates: list[tuple[str, Callable, int, float]] = []  # (name, predict_fn, n_params, in_sample_r2)

    def _fit_lstsq(cols_or_aux: list, name: str) -> None:
        """cols_or_aux: list of (label, array_train_callable) where the callable
        returns a train-time column built from X_train and feature_names."""
        try:
            train_cols = [fn(X_train) for _, fn in cols_or_aux]
            X_aug = np.column_stack(train_cols + [np.ones(n)])
            coefs, _, _, _ = np.linalg.lstsq(X_aug, y_train, rcond=None)
            y_hat = X_aug @ coefs
            r2 = r2_metric(y_train, y_hat)
            def predict(X, c=coefs, builders=[fn for _, fn in cols_or_aux]):
                cols = [b(X) for b in builders]
                return np.column_stack(cols + [np.ones(X.shape[0])]) @ c
            candidates.append((name, predict, len(coefs), r2))
        except Exception:
            pass

    # O0: intercept-only -> y_pred = mean(y)
    mean_y = float(np.mean(y_train))
    candidates.append(("O0_intercept", lambda X: np.full(X.shape[0], mean_y), 1, 0.0))

    if "mean_dipole" in name_to_idx:
        di = name_to_idx["mean_dipole"]
        _fit_lstsq([("dipole", lambda X, i=di: X[:, i])], "O1_dipole")
        _fit_lstsq([("dipole", lambda X, i=di: X[:, i]),
                     ("dipole_sq", lambda X, i=di: X[:, i] ** 2)],
                    "O3_dipole_squared")
        _fit_lstsq([("signed_dipole_sq",
                     lambda X, i=di: X[:, i] * np.abs(X[:, i]))],
                    "O4_signed_dipole_squared")

    if "mean_dipole" in name_to_idx and "volume_zscore" in name_to_idx:
        di = name_to_idx["mean_dipole"]
        vi = name_to_idx["volume_zscore"]
        _fit_lstsq([("dipole", lambda X, i=di: X[:, i]),
                     ("volz", lambda X, i=vi: X[:, i])],
                    "O2_dipole_volz")
        _fit_lstsq([("dipole_x_volz",
                     lambda X, i1=di, i2=vi: X[:, i1] * X[:, i2])],
                    "O6_dipole_volz_interaction")

    if "mean_dipole" in name_to_idx and "mean_ofi" in name_to_idx:
        di = name_to_idx["mean_dipole"]
        oi = name_to_idx["mean_ofi"]
        _fit_lstsq([("dipole", lambda X, i=di: X[:, i]),
                     ("ofi", lambda X, i=oi: X[:, i])],
                    "O5_dipole_ofi")

    if not candidates:
        return None, "no operator-family candidates fit"

    # Score by complexity-adjusted R^2
    best = None
    best_score = -float("inf")
    best_name = ""
    for cname, pred, n_params, r2 in candidates:
        penalty = complexity_lambda * (n_params - 1) / max(n, 1)
        score = r2 - penalty
        if score > best_score:
            best_score = score
            best = pred
            best_name = cname

    return best, f"selected={best_name} (score={best_score:.4f})"


# ---------------------------------------------------------------------------
# Pool chunks across venues into (X, y)
# ---------------------------------------------------------------------------

def assemble_pooled_dataset(contexts: list, feature_names: list[str]
                              ) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Stack chunk feature vectors + forward returns across all venue contexts.
    Drops feature columns where no venue produced finite values; drops rows
    where any kept feature is NaN or the forward return is NaN. Returns
    (X, y, kept_feature_names)."""
    per_feat_vectors: dict[str, list[np.ndarray]] = {f: [] for f in feature_names}
    y_chunks: list[np.ndarray] = []

    for venue_label, ctx, _results in contexts:
        feat_vals = compute_global_feature_values(ctx, feature_names)
        fwd = forward_log_returns(ctx.chunks, k=1)
        if len(fwd) == 0:
            continue
        for fname in feature_names:
            arr = feat_vals.get(fname)
            if arr is None:
                arr = np.full(len(ctx.chunks), np.nan)
            per_feat_vectors[fname].append(arr)
        y_chunks.append(fwd)

    if not y_chunks:
        return np.zeros((0, 0)), np.zeros(0), []

    y = np.concatenate(y_chunks)
    kept = []
    cols = []
    for fname in feature_names:
        v = np.concatenate(per_feat_vectors[fname])
        if not np.any(np.isfinite(v)):
            continue
        kept.append(fname)
        cols.append(v)
    X = np.column_stack(cols) if cols else np.zeros((len(y), 0))

    mask = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    return X[mask], y[mask], kept


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------

def run(contexts: list, feature_names: list[str],
         n_permutations: int, train_frac: float,
         importance_floor: float, universal_threshold: float) -> dict:
    X, y, kept = assemble_pooled_dataset(contexts, feature_names)
    n = len(y)
    if n < 20:
        return {"error": f"only {n} (chunk, fwd_return) pairs; need >=20"}

    cut = max(1, int(n * train_frac))
    X_tr, y_tr = X[:cut], y[:cut]
    X_te, y_te = X[cut:], y[cut:]
    print(f"  pooled n={n}  train={len(y_tr)}  test={len(y_te)}  features={len(kept)}")

    name_to_idx = {nm: i for i, nm in enumerate(kept)}

    # Build predictors
    print("\n  fitting predictors...")
    predictors: dict[str, Callable] = {}
    train_r2s: dict[str, float] = {}
    test_r2s: dict[str, float] = {}

    pf, msg = _build_lasso(X_tr, y_tr)
    if pf is not None:
        predictors["lasso_cv"] = pf
        print(f"    lasso_cv: {msg}")
    else:
        print(f"    lasso_cv SKIPPED: {msg}")

    pf, msg = _build_poly_ridge(X_tr, y_tr)
    if pf is not None:
        predictors["poly_ridge"] = pf
        print(f"    poly_ridge: {msg}")
    else:
        print(f"    poly_ridge SKIPPED: {msg}")

    if "mean_dipole" in name_to_idx:
        pf, msg = _build_single_feature_ols(X_tr, y_tr, name_to_idx["mean_dipole"])
        if pf is not None:
            predictors["dipole_only"] = pf
            print(f"    dipole_only: {msg}")

    if "mean_ofi" in name_to_idx:
        pf, msg = _build_single_feature_ols(X_tr, y_tr, name_to_idx["mean_ofi"])
        if pf is not None:
            predictors["ofi_only"] = pf
            print(f"    ofi_only: {msg}")

    pf, msg = _build_operator_family(X_tr, y_tr, kept)
    if pf is not None:
        predictors["operator_family"] = pf
        print(f"    operator_family: {msg}")
    else:
        print(f"    operator_family SKIPPED: {msg}")

    # Per-predictor train/test R^2 for diagnostic
    for name, pfn in predictors.items():
        train_r2s[name] = r2_metric(y_tr, pfn(X_tr))
        test_r2s[name] = r2_metric(y_te, pfn(X_te))
        print(f"    {name:<20} train_r2={train_r2s[name]:+.4f}  test_r2={test_r2s[name]:+.4f}")

    if not predictors:
        return {"error": "no predictors built"}

    # ===== Use cloned F.1 PermutationImportance =====
    # Pass n_features as operator_dim so the clone's assert doesn't trip.
    config = ImportanceConfig(
        operator_dim=len(kept),
        n_permutations=n_permutations,
        importance_floor=importance_floor,
        universal_threshold=universal_threshold,
    )
    pi = PermutationImportance(config)
    scorer = ConsistencyScorer(config)

    print(f"\n  running permutation importance ({n_permutations} perms x {len(predictors)} predictors x {len(kept)} features)...")
    per_predictor: dict[str, np.ndarray] = {}
    for name, pfn in predictors.items():
        t0 = time.time()
        imp = pi.compute_single(X_te, y_te, pfn, metric_fn=r2_metric)
        per_predictor[name] = imp
        elapsed = time.time() - t0
        print(f"    {name:<20} top3={sorted(((float(imp[i]), kept[i]) for i in range(len(kept))), reverse=True)[:3]}  ({elapsed:.1f}s)")

    # Aggregate via the clone's ConsistencyScorer
    per_arch_matrix = np.stack([per_predictor[n] for n in predictors.keys()], axis=0)
    aggregated = np.mean(per_arch_matrix, axis=0)
    consistency = scorer.score(per_arch_matrix)
    classification = scorer.classify(aggregated, consistency)

    # Reframe classification: "universal" + "architecture_specific" -> our labels.
    # Also derive per-feature predictor-specific predictor list.
    feature_classifications = []
    for i, fname in enumerate(kept):
        cls = classification.get(i, "dead")
        # Which predictors had this feature above floor?
        alive_in = [pname for pname, imp in per_predictor.items()
                    if imp[i] > importance_floor]
        feature_classifications.append({
            "feature": fname,
            "classification": cls,  # "universal" | "architecture_specific" | "dead"
            "aggregated_importance": float(aggregated[i]),
            "consistency": float(consistency[i]),
            "alive_in_predictors": alive_in,
            "per_predictor_importance": {
                pname: float(per_predictor[pname][i])
                for pname in predictors.keys()
            },
        })

    universal = [c["feature"] for c in feature_classifications if c["classification"] == "universal"]
    arch_specific = [c["feature"] for c in feature_classifications if c["classification"] == "architecture_specific"]
    dead = [c["feature"] for c in feature_classifications if c["classification"] == "dead"]

    return {
        "n_chunks": int(n),
        "n_train": int(len(y_tr)),
        "n_test": int(len(y_te)),
        "n_permutations": n_permutations,
        "features_searched": kept,
        "predictors": {
            name: {"train_r2": float(train_r2s[name]),
                    "test_r2": float(test_r2s[name])}
            for name in predictors.keys()
        },
        "classifications": feature_classifications,
        "universal_features": universal,
        "architecture_specific_features": arch_specific,
        "dead_features": dead,
        "summary": {
            "n_universal": len(universal),
            "n_architecture_specific": len(arch_specific),
            "n_dead": len(dead),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--asset", required=True, choices=["ETH", "BTC"])
    p.add_argument("--cb-bins", required=True)
    p.add_argument("--kr-bins", required=True)
    p.add_argument("--bybit-perp-bins", default=None)
    p.add_argument("--sibling-cb-bins", default=None)
    p.add_argument("--sibling-kr-bins", default=None)
    p.add_argument("--features", nargs="*", default=None)
    p.add_argument("--n-permutations", type=int, default=30)
    p.add_argument("--train-frac", type=float, default=0.60)
    p.add_argument("--importance-floor", type=float, default=0.001)
    p.add_argument("--universal-threshold", type=float, default=0.70)
    p.add_argument("--chunk-max-size", type=int, default=30)
    p.add_argument("--chunk-min-segment", type=int, default=10)
    p.add_argument("--multi-signal-pelt", action="store_true", default=True)
    p.add_argument("--output-report", default=None)
    args = p.parse_args()

    feature_names = args.features
    if feature_names is None:
        feature_names = [n for n, _g, _r, _fn in FEATURE_EXTRACTORS]

    print(f"=== markets_importance_runner asset={args.asset} perms={args.n_permutations} features={len(feature_names)} ===")

    contexts = load_all_venue_contexts(
        asset=args.asset, cb_bins=args.cb_bins, kr_bins=args.kr_bins,
        perp_bins=args.bybit_perp_bins,
        sibling_cb_bins=args.sibling_cb_bins,
        sibling_kr_bins=args.sibling_kr_bins,
        chunk_max=args.chunk_max_size, chunk_min=args.chunk_min_segment,
        multi_pelt=args.multi_signal_pelt,
    )

    result = run(
        contexts, feature_names,
        n_permutations=args.n_permutations,
        train_frac=args.train_frac,
        importance_floor=args.importance_floor,
        universal_threshold=args.universal_threshold,
    )

    if "error" in result:
        print(f"\nERROR: {result['error']}")
        return

    print()
    print("=== Classifications (sorted by aggregated importance desc) ===")
    sorted_cls = sorted(result["classifications"],
                          key=lambda c: -c["aggregated_importance"])
    print(f"  {'feature':<40} {'classification':<22} {'agg_imp':>9} {'consist':>8}  alive_in")
    for c in sorted_cls:
        alive = ",".join(c["alive_in_predictors"]) if c["alive_in_predictors"] else "(none)"
        print(f"  {c['feature']:<40} {c['classification']:<22} {c['aggregated_importance']:>9.5f} "
              f"{c['consistency']:>8.3f}  {alive}")
    s = result["summary"]
    print(f"\n  totals: universal={s['n_universal']} "
          f"architecture_specific={s['n_architecture_specific']} dead={s['n_dead']}")

    if args.output_report:
        with open(args.output_report, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\n  report saved: {args.output_report}")


if __name__ == "__main__":
    main()
