"""Independent recalculation of the S40 dipole-rate vs price-rate result.

This script preserves the original S40 event construction exactly, then reports
several non-pooled views so a single flattened Pearson cannot hide heterogeneity.
It does not modify any Frankie code, brain, schema, role, play, or datapoint.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from odcore.io import load_bins

LB = 1800
H = 60
W = 60
CAP = 500
LAGS = tuple(range(-8, 9, 2))
SOURCE_COMMIT = "c1c9a2d7f63e36911eb05bb608430f8e96bcc085"
SOURCE_SCRIPT_BLOB = "1261f0de64ae3cf7f1cf87e0769ccb73af0e2362"


def corr1(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    if x.size < 3 or y.size != x.size:
        return float("nan")
    if np.std(x) == 0.0 or np.std(y) == 0.0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def lag_curve(x: np.ndarray, y: np.ndarray) -> dict[str, object]:
    """S40 lag convention: k>0 means x (dipole rate) leads y (price rate)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    vals: dict[str, float] = {}
    best_k = None
    best_cc = -np.inf
    for k in LAGS:
        if x.ndim == 1:
            if k >= 0:
                a = x[: x.shape[0] - k] if k else x
                b = y[k:] if k else y
            else:
                a = x[-k:]
                b = y[: y.shape[0] + k]
        else:
            if k >= 0:
                a = x[:, : x.shape[1] - k] if k else x
                b = y[:, k:] if k else y
            else:
                a = x[:, -k:]
                b = y[:, : y.shape[1] + k]
        cc = corr1(a, b)
        vals[str(k)] = cc
        if np.isfinite(cc) and cc > best_cc:
            best_cc = cc
            best_k = k
    return {"values": vals, "peak_lag_s": best_k, "peak_corr": float(best_cc)}


def collect() -> tuple[np.ndarray, np.ndarray, list[dict[str, object]], np.ndarray]:
    offs = np.arange(-H, H + 1, dtype=int)
    le: list[np.ndarray] = []
    pr: list[np.ndarray] = []
    meta: list[dict[str, object]] = []

    for cv in ("btc_bybit_perp", "eth_bybit_perp"):
        bins_path = Path(f"realbins/{cv}_bins.json")
        if not bins_path.exists():
            continue
        bs = load_bins(str(bins_path))
        ts, mid, bvol, svol = bs.ts, bs.mid, bs.buy, bs.sell
        cb = np.concatenate([[0.0], np.cumsum(bvol)])
        cs = np.concatenate([[0.0], np.cumsum(svol)])
        t0, t1 = ts[0], ts[-1]

        for side in ("buy", "sell"):
            label_path = Path(f"_alt_labels/{cv}_{side}_winner_onsets.json")
            if not label_path.exists():
                continue
            sgn = 1.0 if side == "buy" else -1.0
            cnt = 0
            for r in json.load(open(label_path)):
                if cnt >= CAP:
                    break
                dts = float(r["decision_ts_utc"])
                if not (t0 + LB <= dts <= t1):
                    continue
                i = int(np.searchsorted(ts, dts, "right")) - 1
                w = mid[i - LB : i + 1]
                if (w <= 0).any():
                    continue
                e = i - LB + (int(np.argmin(w)) if side == "buy" else int(np.argmax(w)))
                if (i - e) < H or (e - H - W) < 0 or (e + H + 1) > len(ts):
                    continue

                lean = np.empty(len(offs), dtype=float)
                price = np.empty(len(offs), dtype=float)
                for j, o in enumerate(offs):
                    end = int(e + o)
                    buy = cb[end + 1] - cb[end - W + 1]
                    sell = cs[end + 1] - cs[end - W + 1]
                    total = buy + sell
                    lean[j] = sgn * (buy - sell) / total if total > 0 else 0.0
                    price[j] = sgn * np.log(mid[end] / mid[e]) * 1e4

                le.append(lean)
                pr.append(price)
                meta.append(
                    {
                        "cell": cv,
                        "side": side,
                        "decision_ts_utc": dts,
                        "turn_ts": int(ts[e]),
                    }
                )
                cnt += 1

    return np.asarray(le), np.asarray(pr), meta, offs


def mask_for(meta: list[dict[str, object]], cell: str | None = None, side: str | None = None) -> np.ndarray:
    return np.asarray(
        [
            (cell is None or m["cell"] == cell) and (side is None or m["side"] == side)
            for m in meta
        ],
        dtype=bool,
    )


def mean_curve_summary(lr: np.ndarray, rr: np.ndarray) -> dict[str, object]:
    x = lr.mean(axis=0)
    y = rr.mean(axis=0)
    return {"corr": corr1(x, y), "lead_lag": lag_curve(x, y)}


def pooled_summary(lr: np.ndarray, rr: np.ndarray) -> dict[str, object]:
    return {"corr": corr1(lr, rr), "lead_lag": lag_curve(lr, rr)}


def cluster_bootstrap_ci(x: np.ndarray, y: np.ndarray, b: int = 1000, seed: int = 40) -> dict[str, float]:
    """Resample whole events, preserving within-event serial dependence."""
    if x.shape != y.shape or x.ndim != 2:
        raise ValueError("cluster bootstrap expects same-shaped event x time arrays")
    n_events, n_t = x.shape
    stats = np.column_stack(
        [
            np.full(n_events, n_t, dtype=float),
            x.sum(axis=1),
            y.sum(axis=1),
            np.square(x).sum(axis=1),
            np.square(y).sum(axis=1),
            (x * y).sum(axis=1),
        ]
    )

    def from_stats(s: np.ndarray) -> float:
        n, sx, sy, sxx, syy, sxy = s
        vx = sxx - sx * sx / n
        vy = syy - sy * sy / n
        cov = sxy - sx * sy / n
        if vx <= 0 or vy <= 0:
            return float("nan")
        return float(cov / np.sqrt(vx * vy))

    rng = np.random.default_rng(seed)
    vals = np.empty(b, dtype=float)
    for i in range(b):
        idx = rng.integers(0, n_events, size=n_events)
        vals[i] = from_stats(stats[idx].sum(axis=0))
    vals = vals[np.isfinite(vals)]
    return {
        "estimate": corr1(x, y),
        "lo_95": float(np.quantile(vals, 0.025)),
        "hi_95": float(np.quantile(vals, 0.975)),
        "bootstrap_events": int(n_events),
        "bootstrap_reps": int(b),
    }


def event_corrs(lr: np.ndarray, rr: np.ndarray) -> np.ndarray:
    return np.asarray([corr1(lr[i], rr[i]) for i in range(lr.shape[0])], dtype=float)


def event_peak_lags(lr: np.ndarray, rr: np.ndarray) -> np.ndarray:
    out = []
    for i in range(lr.shape[0]):
        out.append(lag_curve(lr[i], rr[i])["peak_lag_s"])
    return np.asarray(out, dtype=float)


def finite_distribution(v: np.ndarray) -> dict[str, float]:
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    return {
        "n": int(v.size),
        "mean": float(np.mean(v)),
        "median": float(np.median(v)),
        "q25": float(np.quantile(v, 0.25)),
        "q75": float(np.quantile(v, 0.75)),
        "fraction_positive": float(np.mean(v > 0)),
    }


def assign_local_depth_quartiles(depth: np.ndarray, meta: list[dict[str, object]]) -> np.ndarray:
    """Rank depth within each cell x side so one population cannot set all cut points."""
    q = np.full(depth.shape[0], -1, dtype=int)
    for cell in ("btc_bybit_perp", "eth_bybit_perp"):
        for side in ("buy", "sell"):
            idx = np.where(mask_for(meta, cell, side))[0]
            if not idx.size:
                continue
            order = np.argsort(depth[idx], kind="mergesort")
            local_q = np.floor(np.arange(idx.size) * 4.0 / idx.size).astype(int)
            local_q = np.clip(local_q, 0, 3)
            q[idx[order]] = local_q
    return q


def main() -> None:
    le, pr, meta, offs = collect()
    if not len(le):
        raise RuntimeError("no S40 events were reconstructed")

    lr = np.gradient(le, axis=1)
    rr = np.gradient(pr, axis=1)
    zero = int(np.where(offs == 0)[0][0])

    result: dict[str, object] = {
        "provenance": {
            "s40_source_commit": SOURCE_COMMIT,
            "s40_overlay_blob": SOURCE_SCRIPT_BLOB,
            "construction": "exact S40 LB/H/W/CAP, frozen S40 labels, sign-aligned BTC/ETH Bybit winners",
            "note": "July data branches are cumulative supersets; frozen S40 label timestamps define the historical event population.",
        },
        "n_events": int(len(le)),
        "exact_s40_reproduction": pooled_summary(lr, rr),
        "what_the_picture_literally_plotted": mean_curve_summary(lr, rr),
    }

    counts: dict[str, int] = {}
    groups: dict[str, object] = {}
    for cell in ("btc_bybit_perp", "eth_bybit_perp"):
        for side in ("buy", "sell"):
            m = mask_for(meta, cell, side)
            key = f"{cell}:{side}"
            counts[key] = int(m.sum())
            if m.sum():
                groups[key] = {
                    "n": int(m.sum()),
                    "pooled": pooled_summary(lr[m], rr[m]),
                    "mean_curve": mean_curve_summary(lr[m], rr[m]),
                    "event_corr": finite_distribution(event_corrs(lr[m], rr[m])),
                }
    for cell in ("btc_bybit_perp", "eth_bybit_perp"):
        m = mask_for(meta, cell=cell)
        groups[f"{cell}:ALL_SIDES"] = {
            "n": int(m.sum()),
            "pooled": pooled_summary(lr[m], rr[m]),
            "mean_curve": mean_curve_summary(lr[m], rr[m]),
        }
    for side in ("buy", "sell"):
        m = mask_for(meta, side=side)
        groups[f"ALL_CELLS:{side}"] = {
            "n": int(m.sum()),
            "pooled": pooled_summary(lr[m], rr[m]),
            "mean_curve": mean_curve_summary(lr[m], rr[m]),
        }
    result["counts"] = counts
    result["group_breakdown"] = groups

    windows = {
        "far_pre_-60_-11": (offs >= -60) & (offs <= -11),
        "turn_-10_+10": (offs >= -10) & (offs <= 10),
        "turn_-5_+5": (offs >= -5) & (offs <= 5),
        "post_+11_+60": (offs >= 11) & (offs <= 60),
    }
    phase: dict[str, object] = {}
    for name, cols in windows.items():
        phase[name] = {
            "pooled_corr": corr1(lr[:, cols], rr[:, cols]),
            "mean_curve_corr": corr1(lr[:, cols].mean(axis=0), rr[:, cols].mean(axis=0)),
            "event_corr": finite_distribution(event_corrs(lr[:, cols], rr[:, cols])),
        }
    result["phase_breakdown"] = phase

    evc = event_corrs(lr, rr)
    evlags = event_peak_lags(lr, rr)
    result["event_level"] = {
        "corr_distribution": finite_distribution(evc),
        "peak_lag_distribution_s": finite_distribution(evlags),
        "peak_lag_fraction_zero": float(np.mean(evlags == 0)),
        "peak_lag_fraction_dipole_leads": float(np.mean(evlags > 0)),
        "peak_lag_fraction_price_leads": float(np.mean(evlags < 0)),
    }

    depth = -le[:, zero]
    depth_q = assign_local_depth_quartiles(depth, meta)
    dq: dict[str, object] = {}
    for q in range(4):
        m = depth_q == q
        dq[f"Q{q + 1}"] = {
            "n": int(m.sum()),
            "depth_mean": float(depth[m].mean()),
            "pooled_corr": corr1(lr[m], rr[m]),
            "mean_curve_corr": corr1(lr[m].mean(axis=0), rr[m].mean(axis=0)),
            "event_corr": finite_distribution(event_corrs(lr[m], rr[m])),
        }
    result["dipole_depth_quartiles_within_cell_side"] = dq

    turn_cols = windows["turn_-10_+10"]
    result["cluster_bootstrap_95ci"] = {
        "full_window": cluster_bootstrap_ci(lr, rr),
        "turn_-10_+10": cluster_bootstrap_ci(lr[:, turn_cols], rr[:, turn_cols]),
    }

    out = Path("s40_independent_recalc_results.json")
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    print(f"RESULT_FILE={out}")


if __name__ == "__main__":
    main()
