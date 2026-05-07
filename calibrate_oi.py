"""
calibrate_oi.py — read backend_oi_history.jsonl and pin per-(asset,
venue) Δoi-z thresholds so the OI monitor uses empirical percentiles
rather than the hardcoded BUILD_Z=2.0 / CLEAR_Z=1.0 fallbacks.

The OI monitor's hardcoded thresholds are inherited from basis_monitor.
Once enough history exists (≥ MIN_OBS_FOR_CALIBRATION observations per
(asset, venue), defaulting to 240 ≈ 2h at 30s poll cadence), this
script swaps them for build_z = p95(|Δoi z|) and clear_z = p50(|Δoi z|)
so the alert fires roughly the top-5%-most-extreme positioning shifts
per (asset, venue) instead of being calibrated to a sigma-count picked
without seeing the distribution.

Output schema:
{
  "version": 1,
  "computed_utc": "...",
  "calibration": {
    "BTC/Binance": {
      "n_obs": 1234,
      "n_deltas": 1222,
      "build_z": 2.18,
      "clear_z": 0.71,
      "delta_oi_pct_p50": 0.00031,
      "delta_oi_pct_p95": 0.00874,
      "abs_z_p50": 0.71,
      "abs_z_p95": 2.18
    },
    ...
  }
}

Run:
  python calibrate_oi.py \\
      --history-path backend_oi_history.jsonl \\
      --output-path  oi_calibration.json
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict


WINDOW_OBS = 12                  # match backend.oi_monitor.WINDOW_OBS
MIN_OBS_FOR_CALIBRATION = 240    # at least this many obs per (asset, venue)
ROLLING_WINDOW_OBS = 240         # match backend.oi_monitor.ROLLING_WINDOW_OBS


def _percentile(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    if len(s) == 1:
        return float(s[0])
    idx = (len(s) - 1) * (p / 100.0)
    lo = int(idx)
    hi = min(lo + 1, len(s) - 1)
    frac = idx - lo
    return float(s[lo] * (1 - frac) + s[hi] * frac)


def _calibrate_one(label: str, obs: list[dict]) -> dict | None:
    """Replay the OI-monitor delta+z computation over the historical
    observations for one (asset, venue). Returns a calibration entry
    or None if there isn't enough data."""
    if len(obs) < MIN_OBS_FOR_CALIBRATION:
        print(f"[oi-calib] {label}: only {len(obs)} obs, need "
              f"{MIN_OBS_FOR_CALIBRATION}; skipping", flush=True)
        return None

    obs.sort(key=lambda d: float(d.get("ts_utc", 0.0)))
    deltas: list[float] = []
    history_window: list[float] = []  # rolling window of past Δoi values
    abs_zs: list[float] = []

    for i in range(WINDOW_OBS, len(obs)):
        anchor = obs[i - WINDOW_OBS]
        cur = obs[i]
        oi_anchor = float(anchor.get("oi", 0.0))
        oi_cur = float(cur.get("oi", 0.0))
        if oi_anchor <= 0 or oi_cur <= 0:
            continue
        d_oi = (oi_cur - oi_anchor) / oi_anchor
        deltas.append(d_oi)
        # Maintain rolling window for z computation matching the
        # backend's running statistics.
        history_window.append(d_oi)
        if len(history_window) > ROLLING_WINDOW_OBS:
            history_window.pop(0)
        if len(history_window) >= 60:  # MIN_OBS_FOR_Z in oi_monitor
            mean = sum(history_window) / len(history_window)
            var = sum((x - mean) ** 2 for x in history_window) / len(history_window)
            std = var ** 0.5
            if std > 1e-12:
                z = (d_oi - mean) / std
                abs_zs.append(abs(z))

    if len(abs_zs) < MIN_OBS_FOR_CALIBRATION:
        print(f"[oi-calib] {label}: only {len(abs_zs)} z-scored obs, "
              f"need {MIN_OBS_FOR_CALIBRATION}; skipping", flush=True)
        return None

    # build_z = p95(|z|) so the "extreme" alert fires on the top ~5% of
    # observed deviations; clear_z = p50(|z|) so a steady-state poll
    # (median |z|) clears any open alert immediately.
    build_z = _percentile(abs_zs, 95.0)
    clear_z = _percentile(abs_zs, 50.0)
    return {
        "n_obs": len(obs),
        "n_deltas": len(deltas),
        "n_zs": len(abs_zs),
        "build_z": float(build_z),
        "clear_z": float(clear_z),
        "delta_oi_pct_p50": _percentile([abs(x) for x in deltas], 50.0),
        "delta_oi_pct_p95": _percentile([abs(x) for x in deltas], 95.0),
        "abs_z_p50": float(clear_z),
        "abs_z_p95": float(build_z),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--history-path", default="backend_oi_history.jsonl")
    p.add_argument("--output-path", default="oi_calibration.json")
    args = p.parse_args()

    if not os.path.exists(args.history_path):
        print(f"[oi-calib] no history at {args.history_path}; oi_monitor "
              f"will use hardcoded defaults", flush=True)
        return

    grouped: dict[str, list[dict]] = defaultdict(list)
    with open(args.history_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            asset = d.get("asset")
            venue = d.get("venue")
            if not asset or not venue:
                continue
            grouped[f"{asset}/{venue}"].append(d)

    calibration = {}
    for label, obs in grouped.items():
        result = _calibrate_one(label, obs)
        if result is None:
            continue
        calibration[label] = result
        print(f"[oi-calib] {label}: n_obs={result['n_obs']} "
              f"build_z={result['build_z']:.2f} clear_z={result['clear_z']:.2f} "
              f"|Δoi|p95={result['delta_oi_pct_p95']*100:.2f}%",
              flush=True)

    if not calibration:
        print(f"[oi-calib] no (asset, venue) had enough history; "
              f"oi_monitor will use hardcoded defaults", flush=True)
        return

    out = {
        "version": 1,
        "computed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "calibration": calibration,
    }
    tmp = args.output_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(out, f, indent=2)
    os.replace(tmp, args.output_path)
    print(f"[oi-calib] wrote {args.output_path}: {len(calibration)} entries",
          flush=True)


if __name__ == "__main__":
    main()
