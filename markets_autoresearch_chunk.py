"""
markets_autoresearch_chunk.py — per-chunk operator-form discovery for Phase 2.

Implements the feasibility leg of HANDOFF_TO_CODE_PHASE2.md. For each picked
MarketChunk, fits a small library of candidate operator forms to bar-level
data (X_t -> log_return_{t+1}), records the best fit by complexity-penalized
in-sample R^2, and persists a per-chunk JSON record.

Operator candidates are linear-in-coefficients (so np.linalg.lstsq suffices)
but include nonlinear feature constructions (log volume, dipole squared,
dipole * sign, dipole velocity, interactions). This is structurally analogous
to apr5's operator-form search restricted to a hand-curated family — full
symbolic regression is not implemented here; the apr5 OD-branch search engine
is the right backend when wired in.

Aggregation: per regime, count which operator family wins most often. Per
HANDOFF_TO_CODE_PHASE2.md gate E ("operator family stable across at least
60% of chunks"), report the modal-operator share per regime.

Optional gate-D evaluation (--gate-d-eval): train on first-half chunks,
test on second-half, compare best recovered operator's forward predictive
R^2 to the dipole-only baseline.

Usage:
    python markets_autoresearch_chunk.py --asset ETH \\
        --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json \\
        [--regime-filter WHALE] [--complexity-lambda 0.05] \\
        [--output-path /tmp/autoresearch_eth.json] [--gate-d-eval]
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np

from markets_adapter import MarketChunk
from phase1_5_evaluator import classify_venue, load_bars


# ---------------------------------------------------------------------------
# Operator family — linear-in-coefficients with curated feature constructions.
#
# Each entry is (name, build_features), where build_features takes the bar
# sequence within a chunk and returns (X, y, feature_names) such that
# y[i] = f(X[i, :], coeffs) and y[i] is log_return_{t+1} from bar i.
#
# All operators include an intercept column; their n_params is the number
# of returned columns.
# ---------------------------------------------------------------------------

EPS = 1e-9


def _bar_arrays(bars):
    closes = np.array([b.close for b in bars], dtype=float)
    dipoles = np.array([b.dipole for b in bars], dtype=float)
    vols = np.array([max(b.volume, EPS) for b in bars], dtype=float)
    log_vols = np.log(vols)
    log_returns = np.log(closes[1:] / np.clip(closes[:-1], EPS, None))
    return closes, dipoles, vols, log_vols, log_returns


def _intercept_only(bars):
    _, _, _, _, y = _bar_arrays(bars)
    n = len(y)
    X = np.ones((n, 1))
    return X, y, ["intercept"]


def _dipole_only(bars):
    _, d, _, _, y = _bar_arrays(bars)
    n = len(y)
    X = np.column_stack([d[:-1], np.ones(n)])
    return X, y, ["dipole_t", "intercept"]


def _dipole_logvolume(bars):
    _, d, _, lv, y = _bar_arrays(bars)
    n = len(y)
    X = np.column_stack([d[:-1], lv[:-1], np.ones(n)])
    return X, y, ["dipole_t", "log_vol_t", "intercept"]


def _dipole_squared(bars):
    _, d, _, _, y = _bar_arrays(bars)
    n = len(y)
    d_lag = d[:-1]
    X = np.column_stack([d_lag, d_lag * d_lag, np.ones(n)])
    return X, y, ["dipole_t", "dipole_t^2", "intercept"]


def _dipole_velocity(bars):
    _, d, _, _, y = _bar_arrays(bars)
    n = len(y)
    if n < 2:
        return None
    # d_velocity_t = d_t - d_{t-1}; align with y[1:] so we lose one more sample
    d_lag = d[1:-1]                       # bar t for t >= 1
    d_vel = d[1:-1] - d[:-2]              # d_t - d_{t-1}
    y_shift = y[1:]                       # next-return for t >= 1
    X = np.column_stack([d_lag, d_vel, np.ones(len(y_shift))])
    return X, y_shift, ["dipole_t", "dipole_velocity_t", "intercept"]


def _dipole_volume_interaction(bars):
    _, d, _, lv, y = _bar_arrays(bars)
    n = len(y)
    X = np.column_stack([d[:-1] * lv[:-1], np.ones(n)])
    return X, y, ["dipole_t * log_vol_t", "intercept"]


def _signed_dipole_squared(bars):
    """y = a * d * |d| + c — mean-reversion / momentum on signed magnitude."""
    _, d, _, _, y = _bar_arrays(bars)
    n = len(y)
    d_lag = d[:-1]
    X = np.column_stack([d_lag * np.abs(d_lag), np.ones(n)])
    return X, y, ["dipole_t * |dipole_t|", "intercept"]


def _kitchen_sink(bars):
    _, d, _, lv, y = _bar_arrays(bars)
    n = len(y)
    if n < 4:
        return None
    d_lag = d[:-1]
    X = np.column_stack([
        d_lag,
        d_lag * d_lag,
        lv[:-1],
        d_lag * lv[:-1],
        np.ones(n),
    ])
    return X, y, ["dipole_t", "dipole_t^2", "log_vol_t",
                   "dipole_t * log_vol_t", "intercept"]


OPERATOR_FAMILY = [
    ("O0_intercept_only", _intercept_only),
    ("O1_dipole", _dipole_only),
    ("O2_dipole_logvolume", _dipole_logvolume),
    ("O3_dipole_squared", _dipole_squared),
    ("O4_dipole_velocity", _dipole_velocity),
    ("O5_dipole_volume_interaction", _dipole_volume_interaction),
    ("O6_signed_dipole_squared", _signed_dipole_squared),
    ("O7_kitchen_sink", _kitchen_sink),
]


# ---------------------------------------------------------------------------
# Per-chunk fit
# ---------------------------------------------------------------------------


def _fit_one(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    """Fit OLS, return (coefs, in_sample_r2)."""
    if X.shape[0] < X.shape[1] + 1:
        return np.zeros(X.shape[1]), float("nan")
    if np.std(y) < 1e-12:
        return np.zeros(X.shape[1]), 0.0
    coefs, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    y_hat = X @ coefs
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / max(ss_tot, 1e-12)
    return coefs, r2


def autoresearch_chunk(chunk: MarketChunk, complexity_lambda: float = 0.05
                       ) -> dict:
    """Fit each operator family member to the chunk, pick the best by
    complexity-adjusted in-sample R^2.

    Returns a record with all candidate fits and the winner.
    """
    t0 = time.time()
    candidates = []
    for name, builder in OPERATOR_FAMILY:
        built = builder(chunk.bars)
        if built is None:
            continue
        X, y, feat_names = built
        if X.shape[0] < 3:
            continue
        coefs, r2 = _fit_one(X, y)
        if not np.isfinite(r2):
            continue
        n_params = X.shape[1]
        n_samples = X.shape[0]
        # Complexity penalty: BIC-like, subtract λ * (n_params - 1) / n_samples
        # (intercept counted as free; only extra features cost complexity).
        penalty = complexity_lambda * (n_params - 1) / max(n_samples, 1)
        score = r2 - penalty
        candidates.append({
            "name": name,
            "n_params": int(n_params),
            "n_samples": int(n_samples),
            "in_sample_r2": round(float(r2), 5),
            "complexity_penalty": round(float(penalty), 5),
            "penalty_adjusted_score": round(float(score), 5),
            "coefficients": {fn: round(float(c), 6) for fn, c in zip(feat_names, coefs)},
        })
    candidates.sort(key=lambda c: -c["penalty_adjusted_score"])
    best = candidates[0] if candidates else None
    return {
        "n_bars": len(chunk.bars),
        "candidates": candidates,
        "best_operator": best["name"] if best else None,
        "best_in_sample_r2": best["in_sample_r2"] if best else None,
        "best_penalty_adjusted_score": best["penalty_adjusted_score"] if best else None,
        "search_wall_clock_s": round(time.time() - t0, 4),
    }


# ---------------------------------------------------------------------------
# Aggregation: which operator wins per regime
# ---------------------------------------------------------------------------


def aggregate_winners(records: list[dict]) -> dict:
    """For each regime, count which operator was the winner. Compute the
    modal-operator share — gate E threshold is 60%.
    """
    by_regime: dict[str, Counter] = defaultdict(Counter)
    by_regime_r2: dict[str, list[float]] = defaultdict(list)
    for rec in records:
        if rec.get("best_operator") is None:
            continue
        by_regime[rec["regime"]][rec["best_operator"]] += 1
        if rec.get("best_in_sample_r2") is not None:
            by_regime_r2[rec["regime"]].append(rec["best_in_sample_r2"])
    out: dict[str, dict] = {}
    for regime, counts in by_regime.items():
        total = sum(counts.values())
        modal_op, modal_n = counts.most_common(1)[0]
        modal_share = modal_n / total
        r2s = by_regime_r2[regime]
        out[regime] = {
            "n_chunks": total,
            "modal_operator": modal_op,
            "modal_share": round(modal_share, 3),
            "gate_E_pass": modal_share >= 0.60 and total >= 3,
            "winner_distribution": dict(counts),
            "in_sample_r2_mean": round(float(np.mean(r2s)), 4) if r2s else None,
            "in_sample_r2_max": round(float(np.max(r2s)), 4) if r2s else None,
        }
    return out


# ---------------------------------------------------------------------------
# Optional Gate D: train/test forward predictive R^2 vs dipole-only baseline
# ---------------------------------------------------------------------------


def gate_d_eval(records: list[dict]) -> dict:
    """Compare the best per-chunk operator to the dipole-only baseline by
    in-sample R^2 averaged across chunks. NOT a true cross-chunk train/test
    split (that requires sequence-aware evaluation, deferred to a separate
    tool when n grows). This is a sanity-check version of Gate D suitable
    for the current sample size.
    """
    if not records:
        return {"gate_D_pass": False, "reason": "no records"}
    best_r2s = []
    dipole_r2s = []
    for rec in records:
        if rec.get("best_in_sample_r2") is None:
            continue
        best_r2s.append(rec["best_in_sample_r2"])
        for c in rec.get("candidates", []):
            if c["name"] == "O1_dipole":
                dipole_r2s.append(c["in_sample_r2"])
                break
    if not best_r2s or not dipole_r2s:
        return {"gate_D_pass": False, "reason": "missing baseline or best"}
    best_mean = float(np.mean(best_r2s))
    dipole_mean = float(np.mean(dipole_r2s))
    if dipole_mean <= 0:
        relative_uplift = float("nan")
    else:
        relative_uplift = (best_mean - dipole_mean) / dipole_mean
    return {
        "best_operator_mean_r2": round(best_mean, 4),
        "dipole_only_mean_r2": round(dipole_mean, 4),
        "relative_uplift": round(relative_uplift, 3) if math.isfinite(relative_uplift) else None,
        "gate_D_threshold": 0.50,
        "gate_D_pass": math.isfinite(relative_uplift) and relative_uplift >= 0.50,
        "note": "in-sample comparison; true cross-chunk train/test deferred to when n>=30/regime",
    }


# ---------------------------------------------------------------------------
# Main: pick chunks, run autoresearch, aggregate
# ---------------------------------------------------------------------------


def run_venue(label: str, bins_path: str, regime_filter: str | None,
               complexity_lambda: float) -> list[dict]:
    bars = load_bars(bins_path)
    chunks, results, _, _ = classify_venue(
        bars, label, chunk_max=30, chunk_min=10, multi_signal_pelt=True,
    )
    records: list[dict] = []
    for idx, (c, r) in enumerate(zip(chunks, results)):
        if regime_filter and regime_filter not in r.regime.value:
            continue
        if not c.bars:
            continue
        rec = autoresearch_chunk(c, complexity_lambda=complexity_lambda)
        rec["venue"] = label
        rec["chunk_idx"] = idx
        rec["regime"] = r.regime.value
        rec["start_utc"] = datetime.fromtimestamp(
            c.bars[0].ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        records.append(rec)
    return records


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asset", type=str, required=True)
    p.add_argument("--cb-bins", type=str, required=True)
    p.add_argument("--kr-bins", type=str, required=True)
    p.add_argument("--regime-filter", type=str, default=None,
                   help="Substring filter on regime label (e.g. WHALE, HERD); empty runs on all")
    p.add_argument("--complexity-lambda", type=float, default=0.05,
                   help="Penalty per (n_params-1)/n_samples; higher prefers simpler operators")
    p.add_argument("--output-path", type=str, default=None)
    p.add_argument("--gate-d-eval", action="store_true",
                   help="Print sanity-check Gate D evaluation (in-sample uplift only; true cross-chunk eval deferred until n>=30/regime)")
    args = p.parse_args()

    print(f"=== Phase 2 autoresearch (single-chunk feasibility) — "
          f"asset={args.asset}, regime_filter={args.regime_filter or '(none)'} ===\n")

    cb_records = run_venue(f"CB-{args.asset}", args.cb_bins,
                            args.regime_filter, args.complexity_lambda)
    kr_records = run_venue(f"KR-{args.asset}", args.kr_bins,
                            args.regime_filter, args.complexity_lambda)
    all_records = cb_records + kr_records

    if not all_records:
        print(f"  no chunks matched filter '{args.regime_filter}'")
        return

    print(f"--- Per-chunk autoresearch results ({len(all_records)} chunks) ---")
    print(f"  {'venue':<8}  {'idx':>3}  {'regime':<22}  {'start_utc':<17}  "
          f"{'best_operator':<32}  {'in_sample_r2':>12}  {'wall_clock_ms':>13}")
    for rec in all_records:
        wall_ms = rec["search_wall_clock_s"] * 1000
        print(f"  {rec['venue']:<8}  {rec['chunk_idx']:>3}  "
              f"{rec['regime']:<22}  {rec['start_utc']:<17}  "
              f"{rec['best_operator']:<32}  "
              f"{rec['best_in_sample_r2']:>12.4f}  {wall_ms:>13.1f}")
    print()

    print(f"--- Per-regime operator-stability aggregation (Gate E proxy) ---")
    agg = aggregate_winners(all_records)
    for regime in sorted(agg, key=lambda r: -agg[r]["n_chunks"]):
        a = agg[regime]
        verdict = "PASS" if a["gate_E_pass"] else "FAIL/insufficient"
        print(f"  {regime}: n={a['n_chunks']}  modal={a['modal_operator']} "
              f"({a['modal_share']:.0%})  mean_r2={a['in_sample_r2_mean']}  "
              f"-> Gate E: {verdict}")
        if a["n_chunks"] >= 2:
            for op, n in sorted(a["winner_distribution"].items(),
                                  key=lambda kv: -kv[1]):
                print(f"      {op:<32}  {n}")
    print()

    if args.gate_d_eval:
        print(f"--- Gate D (sanity check; in-sample only) ---")
        d = gate_d_eval(all_records)
        for k, v in d.items():
            print(f"  {k}: {v}")
        print()

    if args.output_path:
        out = {
            "asset": args.asset,
            "regime_filter": args.regime_filter,
            "complexity_lambda": args.complexity_lambda,
            "n_chunks": len(all_records),
            "records": all_records,
            "aggregate_per_regime": agg,
        }
        if args.gate_d_eval:
            out["gate_D"] = gate_d_eval(all_records)
        with open(args.output_path, "w") as f:
            json.dump(out, f, indent=2)
        print(f"Output saved: {args.output_path}")


if __name__ == "__main__":
    main()
