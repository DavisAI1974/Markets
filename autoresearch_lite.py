"""
autoresearch_lite.py — Phase 2 minimal autoresearcher.

Tests whether the hand-specified H_a/H_b dipole is the BEST operator for
predicting next-chunk returns within EQUILIBRIUM chunks, or whether a
different operator form fits better.

Three search modes:
1. Operator bake-off — fixed library of mathematically motivated forms,
   pick by held-out R^2.
2. Linear feature selection — Lasso on encoder features to find best
   linear combination of named features.
3. Polynomial feature interaction — degree-2 PolynomialFeatures + Ridge
   to find composite features (dipole×vol_z, etc).

Output: ranked operators with in-sample and held-out R^2, the winner's
recovered coefficients, comparison to the baseline dipole.

Pools EQUILIBRIUM chunks across all four datasets (CB-BTC, KR-BTC,
CB-ETH, KR-ETH). Train/test split: first 60% in-sample, last 40% OOS.

This is the Phase 2 spec's gate D (forward predictive R² > Phase 1
dipole baseline by 50% relative).
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass, asdict

import numpy as np

from markets_adapter import (
    MarketBar, MarketChunker, MarketChunkEncoder, MarketFeatures,
    load_minute_bars,
)
from regime_classifier import (
    Regime, classify_regime, baselines_from_corpus,
)


# load_bars consolidated into markets_adapter.load_minute_bars (single source of the
# minute-bar loader that had been copy-pasted across the backtest/evaluator scripts).
load_bars = load_minute_bars


FEATURE_NAMES = [
    "ret_mean", "ret_std", "ret_skew", "ret_kurt", "autocorr_lag1",
    "mean_dipole", "mean_ofi", "volume_zscore", "realized_vol",
    "range_atr", "spectral_energy",
    "dipole_acl1", "dipole_pk_freq", "dipole_pk_pow", "kyle_proxy",
    "chunk_volume",
]


def build_dataset(datasets: list[tuple[str, str]],
                   regime_filter: Regime | None = Regime.EQUILIBRIUM_TWO_SIDED
                   ) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Build pooled (X, y) across multiple bins files, optionally filtered to one regime.

    regime_filter=None pools all chunks regardless of regime (useful for per-regime mode).
    """
    all_features = []
    all_targets = []
    for label, path in datasets:
        bars = load_bars(path)
        chunker = MarketChunker(max_window_size=30, stride=15, min_segment=10, mode="hybrid")
        encoder = MarketChunkEncoder(d_enc=64)
        chunks = chunker.chunk(label, bars)
        feats = [encoder._extract(c) for c in chunks]
        base = baselines_from_corpus(feats)
        results = [classify_regime(f, base) for f in feats]

        for t in range(len(chunks) - 1):
            if regime_filter is not None and results[t].regime != regime_filter:
                continue
            f = feats[t]
            row = [
                f.ret_mean, f.ret_std, f.ret_skew, f.ret_kurt, f.autocorr_lag1,
                f.mean_dipole, f.mean_ofi, f.volume_zscore, f.realized_vol,
                f.range_atr, f.spectral_energy,
                f.dipole_autocorr_lag1, f.dipole_peak_freq, f.dipole_peak_power,
                f.kyle_proxy, f.chunk_total_volume,
            ]
            c_next = chunks[t + 1]
            if not c_next.bars or not chunks[t].bars:
                continue
            p0 = chunks[t].bars[-1].close
            p1 = c_next.bars[-1].close
            if p0 <= 0 or p1 <= 0:
                continue
            y = math.log(p1 / p0)
            all_features.append(row)
            all_targets.append(y)

    return np.array(all_features), np.array(all_targets), FEATURE_NAMES


def build_per_regime_datasets(datasets: list[tuple[str, str]]
                                ) -> dict[Regime, tuple[np.ndarray, np.ndarray, list[str]]]:
    """Build separate (X, y) for each regime with sufficient samples (n >= 10)."""
    out: dict[Regime, tuple[np.ndarray, np.ndarray, list[str]]] = {}
    for regime in Regime:
        X, y, names = build_dataset(datasets, regime_filter=regime)
        if len(y) >= 10:
            out[regime] = (X, y, names)
    return out


def split_train_test(X: np.ndarray, y: np.ndarray, train_frac: float = 0.6):
    n = len(y)
    cut = max(1, int(n * train_frac))
    return X[:cut], y[:cut], X[cut:], y[cut:]


def r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) == 0:
        return float("nan")
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if ss_tot < 1e-18:
        return 0.0
    return 1.0 - ss_res / ss_tot


@dataclass
class OperatorResult:
    name: str
    in_sample_r2: float
    out_of_sample_r2: float
    n_train: int
    n_test: int
    formula: str = ""
    coefficients: dict | None = None


# ---------------------------------------------------------------------------
# Mode 1: hand-coded operator bake-off
# ---------------------------------------------------------------------------

def operator_bakeoff(X_tr, y_tr, X_te, y_te, names) -> list[OperatorResult]:
    """Test fixed mathematical forms against the data."""
    results = []
    idx = {n: i for i, n in enumerate(names)}

    def add(name, predict_fn, formula):
        # Fit a single scalar β on training data: y = β * predictor
        pred_tr = predict_fn(X_tr)
        pred_te = predict_fn(X_te)
        denom = float(np.sum(pred_tr ** 2)) + 1e-12
        beta = float(np.sum(pred_tr * y_tr) / denom)
        results.append(OperatorResult(
            name=name,
            in_sample_r2=r2(y_tr, beta * pred_tr),
            out_of_sample_r2=r2(y_te, beta * pred_te),
            n_train=len(y_tr), n_test=len(y_te),
            formula=f"y_pred = {beta:+.6f} * {formula}",
            coefficients={"beta": beta},
        ))

    # Baseline: dipole (the hand-specified operator)
    add("baseline_dipole", lambda X: X[:, idx["mean_dipole"]], "mean_dipole")
    # Negative dipole (mean reversion form, since lag-1 r was negative)
    add("neg_dipole", lambda X: -X[:, idx["mean_dipole"]], "-mean_dipole")
    # Log-ratio variant: log((H_a + ε) / (H_b + ε)) - can't reconstruct from chunk-mean,
    # so use signed sqrt of vol z-score-weighted dipole as proxy:
    add("dipole_x_volz",
        lambda X: X[:, idx["mean_dipole"]] * X[:, idx["volume_zscore"]],
        "mean_dipole * volume_zscore")
    # Skewness alone
    add("ret_skew", lambda X: X[:, idx["ret_skew"]], "ret_skew")
    # Autocorrelation
    add("autocorr_only", lambda X: X[:, idx["autocorr_lag1"]], "autocorr_lag1")
    # Negative autocorr (mean-revert)
    add("neg_autocorr", lambda X: -X[:, idx["autocorr_lag1"]], "-autocorr_lag1")
    # OFI
    add("mean_ofi", lambda X: X[:, idx["mean_ofi"]], "mean_ofi")
    # Combination: dipole adjusted by acl1
    add("dipole_dampened_by_acl1",
        lambda X: X[:, idx["mean_dipole"]] * (1 - X[:, idx["dipole_acl1"]]),
        "mean_dipole * (1 - dipole_acl1)")
    # Kyle's lambda inverse (illiquidity-weighted dipole)
    add("dipole_x_kyle",
        lambda X: X[:, idx["mean_dipole"]] / (np.abs(X[:, idx["kyle_proxy"]]) + 1e-9),
        "mean_dipole / (|kyle_proxy| + ε)")

    return results


# ---------------------------------------------------------------------------
# Mode 2: Lasso linear feature selection
# ---------------------------------------------------------------------------

def lasso_search(X_tr, y_tr, X_te, y_te, names) -> OperatorResult | None:
    try:
        from sklearn.linear_model import LassoCV
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return None

    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_te_s = scaler.transform(X_te)

    n_train = len(y_tr)
    cv_folds = min(5, max(2, n_train // 4))
    if cv_folds < 2:
        return None
    try:
        model = LassoCV(cv=cv_folds, max_iter=5000, random_state=0).fit(X_tr_s, y_tr)
    except Exception:
        return None
    pred_tr = model.predict(X_tr_s)
    pred_te = model.predict(X_te_s)
    nonzero = {names[i]: float(round(c, 6)) for i, c in enumerate(model.coef_) if abs(c) > 1e-9}
    formula = " + ".join(f"{c:+.4f}*{n}" for n, c in nonzero.items()) or "(no features survived)"
    return OperatorResult(
        name="lasso_linear",
        in_sample_r2=r2(y_tr, pred_tr),
        out_of_sample_r2=r2(y_te, pred_te),
        n_train=len(y_tr), n_test=len(y_te),
        formula=f"y_pred = {model.intercept_:+.6f} + {formula}",
        coefficients={"intercept": float(model.intercept_), "selected": nonzero,
                      "alpha": float(model.alpha_)},
    )


# ---------------------------------------------------------------------------
# Mode 3: Polynomial degree-2 feature interaction with Ridge
# ---------------------------------------------------------------------------

def polynomial_search(X_tr, y_tr, X_te, y_te, names) -> OperatorResult | None:
    try:
        from sklearn.linear_model import RidgeCV
        from sklearn.preprocessing import StandardScaler, PolynomialFeatures
    except ImportError:
        return None
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_te_s = scaler.transform(X_te)
    poly = PolynomialFeatures(degree=2, interaction_only=False, include_bias=False)
    X_tr_p = poly.fit_transform(X_tr_s)
    X_te_p = poly.transform(X_te_s)
    n_train = len(y_tr)
    if n_train < 5:
        return None
    try:
        model = RidgeCV(alphas=[0.01, 0.1, 1.0, 10.0, 100.0]).fit(X_tr_p, y_tr)
    except Exception:
        return None
    pred_tr = model.predict(X_tr_p)
    pred_te = model.predict(X_te_p)
    poly_names = poly.get_feature_names_out(names)
    abs_coef = np.abs(model.coef_)
    top_k = np.argsort(-abs_coef)[:6]
    top_features = {poly_names[i]: float(round(model.coef_[i], 6)) for i in top_k if abs_coef[i] > 1e-9}
    return OperatorResult(
        name="polynomial_ridge",
        in_sample_r2=r2(y_tr, pred_tr),
        out_of_sample_r2=r2(y_te, pred_te),
        n_train=len(y_tr), n_test=len(y_te),
        formula=f"top-6 features (of {len(poly_names)}): {', '.join(f'{n}({c:+.3f})' for n, c in top_features.items())}",
        coefficients={"intercept": float(model.intercept_), "top_features": top_features,
                      "alpha": float(model.alpha_)},
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--datasets", nargs="+", required=True,
                   help="Pairs of label:path (e.g. CB-BTC:phase1_bins.json)")
    p.add_argument("--report-path", default=None)
    p.add_argument("--per-regime", action="store_true",
                   help="Run autoresearch separately within each regime class with n>=10")
    args = p.parse_args()

    pairs = []
    for spec in args.datasets:
        if ":" not in spec:
            print(f"Skipping malformed dataset spec: {spec}")
            continue
        label, path = spec.split(":", 1)
        pairs.append((label, path))

    if args.per_regime:
        print(f"Building per-regime datasets from {len(pairs)} sources...")
        per_regime = build_per_regime_datasets(pairs)
        if not per_regime:
            print("FATAL: no regime has n>=10. Need more data.")
            return
        all_per_regime_results = {}
        for regime, (X, y, names) in per_regime.items():
            print(f"\n{'#' * 70}")
            print(f"# REGIME: {regime.value}  (n_pairs={len(y)})")
            print(f"{'#' * 70}")
            X_tr, y_tr, X_te, y_te = split_train_test(X, y, train_frac=0.6)
            print(f"Train: n={len(y_tr)}, Test: n={len(y_te)}\n")
            results = []
            results.extend(operator_bakeoff(X_tr, y_tr, X_te, y_te, names))
            lr = lasso_search(X_tr, y_tr, X_te, y_te, names)
            if lr: results.append(lr)
            pr = polynomial_search(X_tr, y_tr, X_te, y_te, names)
            if pr: results.append(pr)
            results.sort(key=lambda r: -r.out_of_sample_r2)
            print(f"Top operators (held-out R^2):")
            for r in results[:5]:
                flag = "**" if r.out_of_sample_r2 > 0.05 else "  "
                print(f"  {flag} {r.name:<28} OOS R²={r.out_of_sample_r2:+.4f}  "
                      f"IS={r.in_sample_r2:+.4f}  formula={r.formula[:60]}")
            all_per_regime_results[regime.value] = [asdict(r) for r in results]
        if args.report_path:
            with open(args.report_path, "w") as f:
                json.dump(all_per_regime_results, f, indent=2)
            print(f"\nPer-regime report saved: {args.report_path}")
        return

    print(f"Building EQUILIBRIUM-pooled dataset from {len(pairs)} sources...")
    X, y, names = build_dataset(pairs)
    if len(y) < 10:
        print(f"FATAL: only {len(y)} EQUILIBRIUM samples; need >=10")
        return
    print(f"Pooled dataset: {len(y)} EQUILIBRIUM chunk-pairs, {X.shape[1]} features")

    X_tr, y_tr, X_te, y_te = split_train_test(X, y, train_frac=0.6)
    print(f"Train: n={len(y_tr)}, Test: n={len(y_te)}\n")

    all_results: list[OperatorResult] = []
    print("--- Mode 1: hand-coded operator bake-off ---")
    bo = operator_bakeoff(X_tr, y_tr, X_te, y_te, names)
    all_results.extend(bo)

    print("--- Mode 2: Lasso linear feature selection ---")
    lr = lasso_search(X_tr, y_tr, X_te, y_te, names)
    if lr: all_results.append(lr)

    print("--- Mode 3: Polynomial degree-2 + Ridge ---")
    pr = polynomial_search(X_tr, y_tr, X_te, y_te, names)
    if pr: all_results.append(pr)

    print("\n=== Ranked by held-out R^2 ===")
    print(f"{'name':<30} {'IS_R²':>8} {'OOS_R²':>8} {'formula':<60}")
    all_results.sort(key=lambda r: -r.out_of_sample_r2)
    for r in all_results:
        flag = "**" if r.out_of_sample_r2 > 0.05 else "  "
        print(f"{flag} {r.name:<28} {r.in_sample_r2:>+8.4f} {r.out_of_sample_r2:>+8.4f} {r.formula[:80]}")

    print("\n=== Verdict ===")
    baseline_r2 = next((r.out_of_sample_r2 for r in all_results if r.name == "baseline_dipole"), 0.0)
    best = all_results[0] if all_results else None
    if best:
        improvement = best.out_of_sample_r2 - baseline_r2
        relative = improvement / abs(baseline_r2) if abs(baseline_r2) > 1e-6 else float("inf")
        print(f"Baseline (raw dipole) OOS R² = {baseline_r2:+.4f}")
        print(f"Best operator: {best.name}, OOS R² = {best.out_of_sample_r2:+.4f}")
        print(f"Improvement: {improvement:+.4f} (relative: {relative*100:+.1f}%)")
        if best.name == "baseline_dipole":
            print("=> AUTORESEARCH REDISCOVERED THE DIPOLE — the hand-specified operator IS the best.")
            print("   Strong transfer-confirmation: same operator works in markets as in the 4 sciences.")
        elif best.name in ("neg_dipole",):
            print("=> AUTORESEARCH RECOVERED -DIPOLE — the EQUILIBRIUM regime is mean-reverting,")
            print("   consistent with classic order-flow-imbalance-fades literature.")
        elif best.out_of_sample_r2 > baseline_r2 * 1.5 and best.out_of_sample_r2 > 0.05:
            print(f"=> Autoresearch found a stronger operator: {best.name}")
            print("   Recommend swapping it in; gate D (50% improvement) potentially achieved.")
        else:
            print("=> Best operator marginally beats baseline; sample size limits confidence.")

    if args.report_path:
        with open(args.report_path, "w") as f:
            json.dump([asdict(r) for r in all_results], f, indent=2)
        print(f"\nReport saved: {args.report_path}")


if __name__ == "__main__":
    main()
