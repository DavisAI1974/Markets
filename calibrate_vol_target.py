"""
calibrate_vol_target.py — derive per-(asset, venue) VOL_TARGET values
for forward_paper vol-target sizing from the bins corpus, replacing
the hand-picked global default 0.005.

The forward_paper.vol_target_multiplier scales notional by
target / realized_vol clipped to [0.5, 2.0]. The "target" should be
the realized_vol value at which scaling = 1.0; setting it to the
per-(asset, venue) median realized_vol means the median chunk gets
unit notional, the bottom-quartile (quiet) chunks get sized up, and
the top-quartile (loud) chunks get sized down — a clean inverse-vol
weighting.

Output schema:
{
  "version": 1,
  "computed_utc": "...",
  "calibration": {
    "ETH/Coinbase": {
      "n_chunks": 198,
      "p25": 0.00198, "p50": 0.00357, "p75": 0.00582,
      "vol_target": 0.00357     # median = unit-multiplier point
    },
    ...
  }
}

forward_paper reads this once at module load; falls back to the
hardcoded VOL_TARGET when missing.

Run:
  python calibrate_vol_target.py
"""

from __future__ import annotations

import argparse
import json
import os
import time

# Avoid the heavyweight regime classifier import; we only need bars +
# chunks + realized_vol. The chunker mirrors phase1_5_evaluator so
# the calibration matches what forward_paper actually sees.


def _percentile(xs, p):
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


def _calibrate_one(label: str, bins_path: str) -> dict | None:
    if not os.path.exists(bins_path):
        print(f"[vol-target] {label}: missing {bins_path}; skipping",
              flush=True)
        return None
    # Defer the heavy imports so a missing scipy doesn't block the
    # other (asset, venue) targets.
    from phase1_5_evaluator import load_bars
    from markets_adapter import MarketChunker

    bars = load_bars(bins_path)
    if len(bars) < 30:
        print(f"[vol-target] {label}: only {len(bars)} bars; skipping",
              flush=True)
        return None
    chunker = MarketChunker(max_window_size=30, stride=15,
                              min_segment=10, mode="hybrid")
    chunks = chunker.chunk(label, bars)
    rvs = [float(c.realized_vol) for c in chunks
            if c.realized_vol and c.realized_vol > 0]
    if len(rvs) < 30:
        print(f"[vol-target] {label}: only {len(rvs)} chunks with "
              f"realized_vol > 0; skipping", flush=True)
        return None

    p25 = _percentile(rvs, 25)
    p50 = _percentile(rvs, 50)
    p75 = _percentile(rvs, 75)
    return {
        "n_chunks": len(rvs),
        "p25": p25, "p50": p50, "p75": p75,
        # Target = median; quiet chunks size up, loud chunks size down.
        "vol_target": p50,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cb-bins-eth", default="eth_coinbase_bins.json")
    p.add_argument("--kr-bins-eth", default="eth_kraken_bins.json")
    p.add_argument("--cb-bins-btc", default="btc_coinbase_bins.json")
    p.add_argument("--kr-bins-btc", default="btc_kraken_bins.json")
    p.add_argument("--output-path", default="vol_target_calibration.json")
    args = p.parse_args()

    targets = [
        ("ETH/Coinbase", args.cb_bins_eth),
        ("ETH/Kraken", args.kr_bins_eth),
        ("BTC/Coinbase", args.cb_bins_btc),
        ("BTC/Kraken", args.kr_bins_btc),
    ]

    calibration = {}
    for label, path in targets:
        result = _calibrate_one(label, path)
        if result is None:
            continue
        calibration[label] = result
        print(f"[vol-target] {label}: n={result['n_chunks']} "
              f"p25={result['p25']:.5f} p50={result['p50']:.5f} "
              f"p75={result['p75']:.5f} -> target={result['vol_target']:.5f}",
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
    print(f"[vol-target] wrote {args.output_path}: "
          f"{len(calibration)} (asset, venue) entries", flush=True)


if __name__ == "__main__":
    main()
