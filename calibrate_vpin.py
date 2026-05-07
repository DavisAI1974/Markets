"""
calibrate_vpin.py — compute per-(asset, venue) VPIN distributions from
the bins corpus and write vpin_calibration.json so the regime
classifier picks empirical thresholds rather than literature defaults
that are likely off for crypto.

Output schema:
{
  "version": 1,
  "computed_utc": "2026-05-07T...Z",
  "calibration": {
    "BTC/Coinbase": {
      "n_chunks": 1234,
      "corpus_mean_chunk_volume": 1.234,
      "bucket_volume": 0.123,        # mean / 10
      "vpin_p10": 0.04,
      "vpin_p25": 0.08,
      "vpin_p50": 0.18,
      "vpin_p75": 0.32,
      "vpin_p90": 0.51,
      "elevated": 0.32,              # alias of p75
      "diffuse": 0.08,               # alias of p25
      "per_regime_mean": {            # diagnostic; multiplier rules
        "HERD_UP": 0.41,              # may later use these
        "WHALE_UP": 0.35,
        "EQUILIBRIUM_TWO_SIDED": 0.12,
        ...
      }
    },
    ...
  }
}

regime_classifier reads this at module load; falls back to hardcoded
defaults if the file is missing or the entry is missing for a given
(asset, venue).

Run:
  python calibrate_vpin.py \\
    --asset BTC --cb-bins phase1_bins.json --kr-bins kraken_bins.json \\
    --output-path vpin_calibration.json

Or use --all-from-data-sources to run over the standard set.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections import defaultdict
from typing import Optional

# Lazy imports inside main; module-level imports of numpy break smoke
# testing the calibration logic independently.


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


def _calibrate_one(label: str, bins_path: str) -> Optional[dict]:
    if not os.path.exists(bins_path):
        print(f"[calibrate] {label}: bins file missing ({bins_path}); skip",
              flush=True)
        return None

    # Local imports so the file is parseable in environments without
    # numpy (this script is not invoked there anyway).
    from phase1_5_evaluator import classify_venue, load_bars
    from markets_adapter import (
        MarketChunkEncoder, _compute_vpin, _vpin_bucket_volume_from_corpus,
    )

    bars = load_bars(bins_path)
    if not bars:
        print(f"[calibrate] {label}: no bars; skip", flush=True)
        return None

    chunks, results, _, _ = classify_venue(bars, label)
    if not chunks:
        print(f"[calibrate] {label}: chunker produced no chunks; skip",
              flush=True)
        return None

    bucket_volume = _vpin_bucket_volume_from_corpus(chunks)
    if bucket_volume <= 0:
        print(f"[calibrate] {label}: zero bucket_volume; skip", flush=True)
        return None

    # Recompute VPIN per chunk using the corpus-derived bucket size,
    # NOT whatever the encoder used during classify_venue (which
    # would have used the per-chunk fallback).
    vpins: list[float] = []
    per_regime: dict[str, list[float]] = defaultdict(list)
    for chunk, r in zip(chunks, results):
        vpin, n_full = _compute_vpin(chunk.bars, bucket_volume)
        if n_full < 3:
            continue
        vpins.append(vpin)
        per_regime[r.regime.value].append(vpin)

    if len(vpins) < 30:
        print(f"[calibrate] {label}: only {len(vpins)} chunks with VPIN; "
              f"need >=30 for stable percentiles. Skipping.", flush=True)
        return None

    vpins.sort()
    out = {
        "n_chunks": len(vpins),
        "corpus_mean_chunk_volume": bucket_volume * 10.0,
        "bucket_volume": bucket_volume,
        "vpin_p10": _percentile(vpins, 10),
        "vpin_p25": _percentile(vpins, 25),
        "vpin_p50": _percentile(vpins, 50),
        "vpin_p75": _percentile(vpins, 75),
        "vpin_p90": _percentile(vpins, 90),
    }
    out["elevated"] = out["vpin_p75"]
    out["diffuse"] = out["vpin_p25"]
    out["per_regime_mean"] = {
        regime: float(sum(xs) / len(xs))
        for regime, xs in per_regime.items() if xs
    }
    out["per_regime_n"] = {regime: len(xs) for regime, xs in per_regime.items()}
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cb-bins-eth", default="eth_coinbase_bins.json")
    p.add_argument("--kr-bins-eth", default="eth_kraken_bins.json")
    p.add_argument("--cb-bins-btc", default="phase1_bins.json")
    p.add_argument("--kr-bins-btc", default="kraken_bins.json")
    p.add_argument("--output-path", default="vpin_calibration.json")
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
        print(f"[calibrate] {label}: n={result['n_chunks']} "
              f"p25={result['vpin_p25']:.3f} p50={result['vpin_p50']:.3f} "
              f"p75={result['vpin_p75']:.3f} p90={result['vpin_p90']:.3f}",
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
    print(f"[calibrate] wrote {args.output_path}: "
          f"{len(calibration)} (asset, venue) entries", flush=True)


if __name__ == "__main__":
    main()
