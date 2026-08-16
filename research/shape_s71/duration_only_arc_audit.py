"""Duration-only re-analysis of the S74 whole-leg dipole arcs.

Purpose
-------
Remove the historical P&L winner/loser axis completely.  Treat every executor
leg as a directional run and ask only whether the strictly pre-onset dipole arc
contains information about how long that run continues after onset.

No fee, gross P&L, net P&L, winner, or loser variable enters any statistic,
bin, feature, model, or target below.

The run boundaries are the same historical S74 LIVE executor boundaries so the
analysis is directly comparable to Greg's graphs.  All predictive features use
only the birth->onset limb; the target is future onset->close duration.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from leg_imbalance import extract

COINS = ("sol", "btc", "eth", "xrp")
EPS = 1e-12


def rankdata(a: np.ndarray) -> np.ndarray:
    """Average ranks for ties, 0-based.  Minimal scipy-free implementation."""
    a = np.asarray(a, float)
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), float)
    i = 0
    while i < len(a):
        j = i + 1
        while j < len(a) and a[order[j]] == a[order[i]]:
            j += 1
        ranks[order[i:j]] = (i + j - 1) / 2.0
        i = j
    return ranks


def corr(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if len(x) < 3 or np.std(x) < EPS or np.std(y) < EPS:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if len(x) < 3:
        return float("nan")
    return corr(rankdata(x), rankdata(y))


def first_cross_fraction(a: np.ndarray, level: float) -> float:
    idx = np.where(a >= level)[0]
    return float(idx[0] / (len(a) - 1)) if len(idx) else 1.0


def slope(a: np.ndarray, lo: float, hi: float) -> float:
    n = len(a)
    i0 = int(round(lo * (n - 1)))
    i1 = max(i0 + 2, int(round(hi * (n - 1))) + 1)
    i1 = min(i1, n)
    x = np.linspace(lo, hi, i1 - i0)
    return float(np.polyfit(x, a[i0:i1], 1)[0]) if len(x) >= 3 else 0.0


def onset_features(r: dict) -> dict[str, float]:
    a = np.asarray(r["t_pre_arc"], float)
    valley = float(a[0])
    peak = float(a[-1])
    amp = peak - valley
    if abs(amp) > 1e-9:
        z = (a - valley) / amp
    else:
        z = np.zeros_like(a)

    # Greg's visual hypotheses, stated on the birth->onset limb.
    # Earlier ascent => smaller cross fractions.
    start10 = first_cross_fraction(a, valley + 0.10 * amp) if amp > 0 else 1.0
    rise25 = first_cross_fraction(a, valley + 0.25 * amp) if amp > 0 else 1.0
    rise50 = first_cross_fraction(a, valley + 0.50 * amp) if amp > 0 else 1.0
    rise80 = first_cross_fraction(a, valley + 0.80 * amp) if amp > 0 else 1.0
    zero = first_cross_fraction(a, 0.0)

    x = np.linspace(0.0, 1.0, len(a))
    quad = float(np.polyfit(x, z, 2)[0]) if np.std(z) > EPS else 0.0
    cubic = float(np.polyfit(x, z, 3)[0]) if np.std(z) > EPS else 0.0

    return {
        "birth_to_onset_s": float(r["pre_ext"]),
        "birth_level": valley,
        "onset_peak": peak,
        "rise_amplitude": amp,
        "pre_mean": float(r["t_pre_mean"]),
        "ascent_start10_frac": start10,
        "rise25_frac": rise25,
        "rise50_frac": rise50,
        "rise80_frac": rise80,
        "zero_cross_frac": zero,
        "slope_early": slope(a, 0.00, 0.33),
        "slope_mid": slope(a, 0.33, 0.67),
        "slope_late": slope(a, 0.67, 1.00),
        "curvature_quad_norm": quad,
        "curvature_cubic_norm": cubic,
        "normalized_area": float(np.mean(z)),
        "rising_fraction": float(np.mean(np.diff(a) > 0)),
    }


def quantile_groups(y: np.ndarray, k: int = 5) -> np.ndarray:
    """Equal-count groups by duration. No outcome-fit threshold."""
    order = np.argsort(y, kind="mergesort")
    g = np.empty(len(y), int)
    for rank, idx in enumerate(order):
        g[idx] = min(k - 1, int(rank * k / len(y)))
    return g


def summarize_groups(y: np.ndarray, X: dict[str, np.ndarray], groups: np.ndarray) -> dict:
    out = {}
    for q in range(groups.max() + 1):
        m = groups == q
        out[f"Q{q+1}"] = {
            "n": int(m.sum()),
            "duration_s": {
                "min": float(np.min(y[m])),
                "median": float(np.median(y[m])),
                "mean": float(np.mean(y[m])),
                "max": float(np.max(y[m])),
            },
            "feature_means": {k: float(np.mean(v[m])) for k, v in X.items()},
        }
    return out


def ridge_time_split(X: dict[str, np.ndarray], y: np.ndarray) -> dict:
    """Fixed ridge, chronological 70/30 split. No hyperparameter tuning."""
    names = list(X)
    A = np.column_stack([X[k] for k in names]).astype(float)
    n = len(y)
    cut = max(10, int(n * 0.70))
    tr = np.arange(n) < cut
    te = ~tr
    mu = np.nanmean(A[tr], axis=0)
    sd = np.nanstd(A[tr], axis=0)
    sd[sd < 1e-9] = 1.0
    Z = np.nan_to_num((A - mu) / sd)
    yt = np.log1p(y)
    Z1 = np.column_stack([np.ones(n), Z])
    alpha = 1.0
    eye = np.eye(Z1.shape[1]); eye[0, 0] = 0.0
    beta = np.linalg.solve(Z1[tr].T @ Z1[tr] + alpha * eye, Z1[tr].T @ yt[tr])
    pred = np.expm1(Z1 @ beta)
    base = float(np.median(y[tr]))
    mae = float(np.mean(np.abs(pred[te] - y[te])))
    base_mae = float(np.mean(np.abs(base - y[te])))
    return {
        "train_n": int(tr.sum()),
        "test_n": int(te.sum()),
        "fixed_alpha": alpha,
        "test_spearman": spearman(pred[te], y[te]),
        "test_pearson_log_duration": corr(np.log1p(pred[te]), np.log1p(y[te])),
        "test_mae_s": mae,
        "baseline_train_median_s": base,
        "baseline_mae_s": base_mae,
        "mae_improvement_pct": float(100.0 * (base_mae - mae) / base_mae) if base_mae else float("nan"),
        "coefficients": {name: float(beta[i + 1]) for i, name in enumerate(names)},
    }


def old_pnl_label_sanity(rows: list[dict], y: np.ndarray) -> dict:
    """Diagnostic only: show P&L labels were cross-cutting duration, never use them as target/features."""
    net = np.asarray([float(r["net"]) for r in rows])
    med = float(np.median(y))
    short = y < med
    long = ~short
    return {
        "duration_median_s": med,
        "short_run_count": int(short.sum()),
        "long_run_count": int(long.sum()),
        "old_positive_net_inside_short_runs": int(np.sum(short & (net > 0))),
        "old_nonpositive_net_inside_short_runs": int(np.sum(short & (net <= 0))),
        "old_positive_net_inside_long_runs": int(np.sum(long & (net > 0))),
        "old_nonpositive_net_inside_long_runs": int(np.sum(long & (net <= 0))),
        "note": "These counts are provenance only. net/P&L is excluded from every duration statistic and model.",
    }


def coin_result(coin: str) -> dict:
    rows, hours = extract(coin)
    # extract() preserves chronological executor-leg order.
    y = np.asarray([float(r["dur"]) for r in rows], float)
    feats = [onset_features(r) for r in rows]
    names = list(feats[0])
    X = {k: np.asarray([f[k] for f in feats], float) for k in names}
    groups = quantile_groups(y, 5)
    side = np.asarray([int(r["side"]) for r in rows])

    feature_assoc = {}
    for k, v in X.items():
        feature_assoc[k] = {
            "spearman_all": spearman(v, y),
            "spearman_buy_runs": spearman(v[side > 0], y[side > 0]),
            "spearman_sell_runs": spearman(v[side < 0], y[side < 0]),
        }

    # Curve means by pure duration quintile, P&L-blind.
    arcs = np.stack([np.asarray(r["t_pre_arc"], float) for r in rows])
    arc_means = {f"Q{q+1}": np.mean(arcs[groups == q], axis=0).tolist() for q in range(5)}

    return {
        "coin": coin,
        "hours": float(hours),
        "n_runs": int(len(rows)),
        "duration_s_quantiles": {
            str(p): float(np.quantile(y, p)) for p in (0.10, 0.20, 0.25, 0.50, 0.75, 0.80, 0.90)
        },
        "old_pnl_label_sanity": old_pnl_label_sanity(rows, y),
        "feature_duration_association": feature_assoc,
        "duration_quintiles": summarize_groups(y, X, groups),
        "chronological_70_30_duration_predictor": ridge_time_split(X, y),
        "mean_pre_onset_arcs_by_duration_quintile": arc_means,
    }


def main() -> None:
    result = {
        "analysis": "S74 dipole arcs relabeled by duration only; winner/loser removed",
        "target": "future directional-run duration from onset to close (seconds)",
        "predictors": "strictly birth-to-onset dipole arc only",
        "fees_or_pnl_used": False,
        "coins": {},
    }
    for coin in COINS:
        print(f"=== {coin.upper()} duration-only ===", flush=True)
        result["coins"][coin] = coin_result(coin)
        r = result["coins"][coin]
        top = sorted(
            ((k, abs(v["spearman_all"]), v["spearman_all"]) for k, v in r["feature_duration_association"].items()
             if np.isfinite(v["spearman_all"])),
            key=lambda x: x[1], reverse=True,
        )[:6]
        print("top duration associations:", [(k, round(s, 3)) for k, _, s in top])
        print("time-split:", r["chronological_70_30_duration_predictor"])

    out = Path("duration_only_arc_audit_results.json")
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"RESULT_FILE={out}")


if __name__ == "__main__":
    main()
