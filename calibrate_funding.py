"""
calibrate_funding.py — pick per-(asset, venue) funding-rate thresholds
empirically from backend_funding_history.jsonl.

The MVP funding_monitor uses ELEVATED=0.0001 (1bp/8h) and
EXTREME=0.0005 (5bp/8h) as hardcoded thresholds based on hand-waved
APR levels. Crypto funding distributions are wider than that prior
implies and shift over time. Once we've collected enough funding
cycles, this script reads the history JSONL and writes per-(asset,
venue) percentile thresholds:

  elevated = p75(|rate|)    # 25% of cycles trip "elevated" by definition
  extreme  = p95(|rate|)    # 5% of cycles trip "extreme"
  clear    = p25(|rate|)

If the asset/venue has fewer than MIN_OBS observations, it's skipped
and funding_monitor uses its hardcoded fallback for that key.

Output schema:
{
  "version": 1,
  "computed_utc": "...",
  "calibration": {
    "BTC/Binance": {
      "n_obs": 87,
      "abs_rate_p25": 0.000012,
      "abs_rate_p50": 0.000056,
      "abs_rate_p75": 0.00012,
      "abs_rate_p95": 0.00038,
      "elevated_threshold": 0.00012,   # alias of p75
      "extreme_threshold": 0.00038,    # alias of p95
      "clear_threshold": 0.000012,     # alias of p25
    },
    ...
  }
}

Run:
  python calibrate_funding.py \\
    --history-path backend_funding_history.jsonl \\
    --output-path funding_calibration.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections import defaultdict


MIN_OBS = 30  # Need ~10 days of 8h cycles before percentiles stabilize.


def _percentile(sorted_vals: list[float], pct: float) -> float:
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


def _calibrate_one(label: str, abs_rates: list[float]) -> dict | None:
    if len(abs_rates) < MIN_OBS:
        print(f"[fund-calib] {label}: only {len(abs_rates)} cycles "
              f"(need >= {MIN_OBS}); skip", flush=True)
        return None
    abs_rates_s = sorted(abs_rates)
    p25 = _percentile(abs_rates_s, 25)
    p50 = _percentile(abs_rates_s, 50)
    p75 = _percentile(abs_rates_s, 75)
    p95 = _percentile(abs_rates_s, 95)
    return {
        "n_obs": len(abs_rates),
        "abs_rate_p25": p25,
        "abs_rate_p50": p50,
        "abs_rate_p75": p75,
        "abs_rate_p95": p95,
        "elevated_threshold": p75,
        "extreme_threshold": p95,
        "clear_threshold": p25,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--history-path", default="backend_funding_history.jsonl")
    p.add_argument("--output-path", default="funding_calibration.json")
    args = p.parse_args()

    if not os.path.exists(args.history_path):
        print(f"[fund-calib] no history at {args.history_path}; "
              f"funding_monitor will use hardcoded defaults", flush=True)
        return

    by_key: dict[str, list[float]] = defaultdict(list)
    with open(args.history_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            asset = row.get("asset")
            venue = row.get("venue")
            rate = row.get("rate")
            if asset and venue and isinstance(rate, (int, float)):
                by_key[f"{asset}/{venue}"].append(abs(float(rate)))

    calibration: dict[str, dict] = {}
    for label, abs_rates in sorted(by_key.items()):
        result = _calibrate_one(label, abs_rates)
        if result is None:
            continue
        calibration[label] = result
        print(f"[fund-calib] {label}: n={result['n_obs']} "
              f"|rate| p25={result['abs_rate_p25']*1e4:+.2f}bps "
              f"p50={result['abs_rate_p50']*1e4:+.2f}bps "
              f"p75={result['abs_rate_p75']*1e4:+.2f}bps "
              f"p95={result['abs_rate_p95']*1e4:+.2f}bps", flush=True)

    out = {
        "version": 1,
        "computed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "calibration": calibration,
    }
    tmp = args.output_path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(out, fh, indent=2)
    os.replace(tmp, args.output_path)
    print(f"[fund-calib] wrote {args.output_path}: "
          f"{len(calibration)} (asset, venue) entries", flush=True)


if __name__ == "__main__":
    main()
