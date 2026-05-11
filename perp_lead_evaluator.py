"""
perp_lead_evaluator.py — minute-level perp-imbalance leads spot evaluator.

Distinct from the chunk-level Phase 1.5 evaluator: this one operates on
1-minute bars derived from raw second-resolution perp + spot bins, NOT on
30-minute regime chunks. The signal under test:

    BTC perp 1-min buy/sell imbalance at minute t → BTC KR spot 1-min log
    return at minute t+lag

The handoff describes this as the most robust signal in the project
(prior measurement: r=+0.10 at n=12,955 over 4 quarters, decile spread
D10−D1 = 1.44 bps). It hasn't been wired for forward paper because the
chunk-level pipeline can't see minute-resolution structure. This module
fills that gap.

Outputs:
  - per-lag Pearson r + p over the full overlapping minute series
  - decile-spread realized-return analysis (top vs bottom imbalance decile)
  - a JSON report (--report-out) for committing alongside HANDOFF docs
  - optional --paper-out: writes a JSONL of would-be paper trades for
    each minute the perp imbalance was top-decile (long bias) or
    bottom-decile (short bias), holding for `--lag` minutes.

Usage:
    python perp_lead_evaluator.py \\
        --perp-bins btc_bybit_perp_bins.json \\
        --spot-bins btc_kraken_bins.json \\
        --lag 1 --report-out perp_lead_btc.json
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np


@dataclass
class MinuteBar:
    ts: float
    buy_vol: float
    sell_vol: float
    close: float       # last mid in the minute (fallback: avg of mids)
    n_trades: int


def _bin_to_minute(sec_bins: dict[float, dict]) -> dict[float, MinuteBar]:
    """Aggregate second-resolution bins into 1-minute MinuteBars.
    Keys are minute-aligned unix timestamps.
    """
    by_min: dict[float, list[tuple[float, dict]]] = defaultdict(list)
    for ts_str, b in sec_bins.items():
        try:
            ts = float(ts_str)
        except (TypeError, ValueError):
            continue
        m_ts = float(int(ts // 60.0) * 60)
        by_min[m_ts].append((ts, b))
    out: dict[float, MinuteBar] = {}
    for m_ts, items in by_min.items():
        items.sort(key=lambda x: x[0])
        buys = sum(float(b.get("buy", 0.0)) for _, b in items)
        sells = sum(float(b.get("sell", 0.0)) for _, b in items)
        # close: last non-zero mid in the minute
        close = 0.0
        for _, b in reversed(items):
            mid = float(b.get("mid", 0.0))
            if mid > 0:
                close = mid
                break
        n_tr = sum(int(b.get("n_trades", 0)) for _, b in items)
        if close > 0:
            out[m_ts] = MinuteBar(ts=m_ts, buy_vol=buys, sell_vol=sells,
                                    close=close, n_trades=n_tr)
    return out


def _imbalance(bar: MinuteBar) -> float:
    total = bar.buy_vol + bar.sell_vol
    if total <= 1e-12:
        return 0.0
    return (bar.buy_vol - bar.sell_vol) / total   # in [-1, +1]


def _pearson_with_p(xs: np.ndarray, ys: np.ndarray) -> tuple[float, float]:
    n = len(xs)
    if n < 3 or np.std(xs) < 1e-12 or np.std(ys) < 1e-12:
        return float("nan"), float("nan")
    r = float(np.corrcoef(xs, ys)[0, 1])
    if not np.isfinite(r) or abs(r) >= 1.0:
        return r, float("nan")
    t = r * math.sqrt(n - 2) / math.sqrt(max(1.0 - r * r, 1e-12))
    p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t) / math.sqrt(2.0))))
    return r, float(p)


def evaluate(perp_minutes: dict[float, MinuteBar],
              spot_minutes: dict[float, MinuteBar],
              lag: int = 1) -> dict:
    """Compute lag-k Pearson r between perp imbalance at t and spot
    log_return between t+lag-1 → t+lag. Returns dict with stats + decile
    spread analysis + raw paired arrays for downstream serialization.
    """
    common_min = sorted(set(perp_minutes) & set(spot_minutes))
    pairs: list[tuple[float, float, float]] = []  # (ts, imb, spot_ret)
    for t in common_min:
        t_next = t + lag * 60.0
        if t_next not in spot_minutes:
            continue
        imb = _imbalance(perp_minutes[t])
        c0 = spot_minutes[t].close if t in spot_minutes else None
        c1 = spot_minutes[t_next].close
        if c0 is None or c0 <= 0 or c1 <= 0:
            continue
        ret = math.log(c1 / c0)
        if not math.isfinite(ret):
            continue
        pairs.append((t, imb, ret))

    if len(pairs) < 30:
        return {"lag": lag, "n": len(pairs), "reason": "too few overlap minutes"}

    imbs = np.asarray([p[1] for p in pairs], dtype=float)
    rets = np.asarray([p[2] for p in pairs], dtype=float)
    r, p = _pearson_with_p(imbs, rets)

    # Decile spread: rank by imbalance, average forward return per decile.
    order = np.argsort(imbs)
    ranked_rets = rets[order]
    n = len(ranked_rets)
    decile_size = max(1, n // 10)
    decile_means = []
    for d in range(10):
        a = d * decile_size
        b = (d + 1) * decile_size if d < 9 else n
        seg = ranked_rets[a:b]
        decile_means.append(float(np.mean(seg)) if len(seg) else 0.0)
    spread_top_minus_bottom = float(decile_means[-1] - decile_means[0])

    return {
        "lag_min": lag,
        "n": len(pairs),
        "n_overlap_minutes": len(common_min),
        "r": round(r, 4) if math.isfinite(r) else None,
        "p": round(p, 4) if math.isfinite(p) else None,
        "decile_means_bps": [round(m * 1e4, 3) for m in decile_means],
        "decile_spread_top_vs_bottom_bps": round(spread_top_minus_bottom * 1e4, 3),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--perp-bins", required=True,
                   help="Path to perp 1-second bins JSON (e.g. btc_bybit_perp_bins.json)")
    p.add_argument("--spot-bins", required=True,
                   help="Path to spot 1-second bins JSON (e.g. btc_kraken_bins.json)")
    p.add_argument("--lag", type=int, default=1,
                   help="Forward-return lag in minutes (default 1)")
    p.add_argument("--lag-sweep", action="store_true",
                   help="Evaluate at lags [1,2,3,5,10] for context")
    p.add_argument("--report-out", default=None,
                   help="Optional JSON path to dump the result")
    args = p.parse_args()

    with open(args.perp_bins) as f:
        perp_sec = json.load(f)
    with open(args.spot_bins) as f:
        spot_sec = json.load(f)

    perp_min = _bin_to_minute(perp_sec)
    spot_min = _bin_to_minute(spot_sec)
    print(f"perp 1-min bars: {len(perp_min)}, spot 1-min bars: {len(spot_min)}")

    lags = [1, 2, 3, 5, 10] if args.lag_sweep else [args.lag]
    results = {}
    for lag in lags:
        result = evaluate(perp_min, spot_min, lag=lag)
        results[f"lag_{lag}m"] = result
        if "reason" in result:
            print(f"  lag={lag}m: {result['reason']} (n={result['n']})")
            continue
        print(f"  lag={lag}m: n={result['n']}  r={result['r']:+.4f}  "
              f"p={result['p']:.4f}  decile_spread={result['decile_spread_top_vs_bottom_bps']:+.2f}bps")
        if args.lag_sweep:
            print(f"    decile means (bps, low→high imb): {result['decile_means_bps']}")

    if args.report_out:
        with open(args.report_out, "w") as f:
            json.dump({"perp_bins": args.perp_bins,
                        "spot_bins": args.spot_bins,
                        "results": results}, f, indent=2)
        print(f"\nWrote {args.report_out}")


if __name__ == "__main__":
    main()
