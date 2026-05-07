"""
calibrate_liq.py — pick liq_monitor thresholds empirically.

The MVP detector in backend/liq_monitor.py uses three hardcoded
thresholds (VOLUME_Z=4, ONE_SIDED=0.6, GAP=0.3%). Whether those produce
real liquidation alerts vs silence vs spam depends on the actual
distribution of those metrics in our perp bins corpus, which differs
per asset.

This script walks the perp bins for each asset, aggregates to 1-min
bars, computes the three metrics for every bar, and writes
liq_calibration.json with per-asset percentile-based thresholds.

Strategy:
  - vol_z, |dipole|, |gap| each get a per-asset p99 cut.
  - Reports the JOINT pass rate (what fraction of bars trip ALL THREE
    at the chosen percentiles). Aim for ~1-3 events per asset per day
    (~0.1-0.2% of bars). If the joint rate is too high, the user can
    bump the cut to p99.5 or p99.9 in the JSON.

Output schema:
{
  "version": 1,
  "computed_utc": "...",
  "calibration": {
    "BTC": {
      "n_bars": 12345,
      "vol_z_p99": 4.2,
      "dipole_abs_p99": 0.78,
      "gap_abs_p99": 0.0035,
      "joint_pass_rate": 0.0011,         # fraction of bars
      "joint_alerts_per_day_est": 1.6,   # = pass_rate * 1440 (mins/day)
      "vol_z_threshold": 4.2,            # alias of *_p99
      "one_sided_threshold": 0.78,
      "price_move_threshold": 0.0035,
    },
    ...
  }
}

Thresholds default to *_p99 but the file is hand-editable: bump the
threshold fields to make alerts rarer, lower them to make alerts more
common. liq_monitor reads only the threshold fields.

Run:
  python calibrate_liq.py --output-path liq_calibration.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import defaultdict


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _percentile(sorted_vals: list[float], pct: float) -> float:
    """Linear-interp percentile (numpy-style) on a pre-sorted list."""
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    idx = (pct / 100.0) * (n - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return float(sorted_vals[lo])
    frac = idx - lo
    return float(sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo]))


def _calibrate_one(asset: str, perp_bins_path: str,
                    rolling_window: int = 60,
                    pct: float = 99.0) -> dict | None:
    """Compute distribution-percentile thresholds for one asset's perp bins."""
    if not os.path.exists(perp_bins_path):
        print(f"[liq-calib] {asset}: no perp bins at {perp_bins_path}; skip",
              flush=True)
        return None

    # Local imports so the script is parseable without numpy/etc.
    from backend.liq_monitor import _aggregate_to_minute_bars, _load_bins

    bins = _load_bins(perp_bins_path)
    if not bins:
        print(f"[liq-calib] {asset}: empty bins; skip", flush=True)
        return None
    bars = _aggregate_to_minute_bars(bins)
    if len(bars) < rolling_window + 2:
        print(f"[liq-calib] {asset}: only {len(bars)} bars; "
              f"need >= {rolling_window+2}; skip", flush=True)
        return None

    vol_zs: list[float] = []
    dipole_abs: list[float] = []
    gap_abs: list[float] = []

    # For each bar starting at index rolling_window, compute the same
    # three metrics liq_monitor uses at runtime, against a trailing
    # rolling_window of prior bars.
    for i in range(rolling_window, len(bars)):
        bar = bars[i]
        window = bars[i - rolling_window: i]
        if len(window) < rolling_window:
            continue
        mean_v = sum(b["volume"] for b in window) / len(window)
        var_v = sum((b["volume"] - mean_v) ** 2 for b in window) / len(window)
        std_v = var_v ** 0.5
        if std_v < 1e-9:
            continue
        vz = (bar["volume"] - mean_v) / std_v
        total = max(bar["volume"], 1e-9)
        dip = abs((bar["buy_vol"] - bar["sell_vol"]) / total)
        prior_close = window[-1]["close"]
        if prior_close <= 0:
            continue
        gap = abs((bar["close"] - prior_close) / prior_close)
        vol_zs.append(vz)
        dipole_abs.append(dip)
        gap_abs.append(gap)

    if len(vol_zs) < 100:
        print(f"[liq-calib] {asset}: only {len(vol_zs)} testable bars; skip",
              flush=True)
        return None

    vol_zs_s = sorted(vol_zs)
    dipole_s = sorted(dipole_abs)
    gap_s = sorted(gap_abs)

    vol_thr = _percentile(vol_zs_s, pct)
    dip_thr = _percentile(dipole_s, pct)
    gap_thr = _percentile(gap_s, pct)

    # Joint pass rate (how often ALL THREE thresholds are simultaneously met).
    n_pass = sum(
        1 for z, d, g in zip(vol_zs, dipole_abs, gap_abs)
        if z >= vol_thr and d >= dip_thr and g >= gap_thr
    )
    joint_rate = n_pass / len(vol_zs)
    alerts_per_day = joint_rate * 1440.0

    return {
        "n_bars": len(vol_zs),
        "rolling_window": rolling_window,
        "percentile_used": pct,
        "vol_z_p99": vol_thr,
        "dipole_abs_p99": dip_thr,
        "gap_abs_p99": gap_thr,
        "joint_pass_rate": joint_rate,
        "joint_alerts_per_day_est": alerts_per_day,
        # Threshold fields liq_monitor reads:
        "vol_z_threshold": vol_thr,
        "one_sided_threshold": dip_thr,
        "price_move_threshold": gap_thr,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--btc-perp-bins", default="btc_binance_perp_bins.json")
    p.add_argument("--eth-perp-bins", default="eth_binance_perp_bins.json")
    p.add_argument("--rolling-window", type=int, default=60)
    p.add_argument("--percentile", type=float, default=99.0,
                   help="Per-metric percentile cut (default 99). Bump to "
                        "99.5 or 99.9 to make alerts rarer.")
    p.add_argument("--output-path", default="liq_calibration.json")
    args = p.parse_args()

    targets = [("BTC", args.btc_perp_bins), ("ETH", args.eth_perp_bins)]
    calibration: dict[str, dict] = {}
    for asset, path in targets:
        result = _calibrate_one(
            asset, path,
            rolling_window=args.rolling_window,
            pct=args.percentile)
        if result is None:
            continue
        calibration[asset] = result
        print(f"[liq-calib] {asset}: n={result['n_bars']} "
              f"vol_z>={result['vol_z_threshold']:.2f} "
              f"|dip|>={result['one_sided_threshold']:.2f} "
              f"|gap|>={result['price_move_threshold']*100:.3f}% "
              f"=> ~{result['joint_alerts_per_day_est']:.1f} alerts/day "
              f"(joint rate {result['joint_pass_rate']*100:.3f}%)",
              flush=True)

    out = {
        "version": 1,
        "computed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "calibration": calibration,
    }
    tmp = args.output_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(out, f, indent=2)
    os.replace(tmp, args.output_path)
    print(f"[liq-calib] wrote {args.output_path}: {len(calibration)} assets",
          flush=True)


if __name__ == "__main__":
    main()
