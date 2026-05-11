"""
calibrate_hawkes_eta.py — derive per-(asset, venue) Hawkes branching-ratio
thresholds for the F10 hawkes confidence multiplier.

Pass-7 finding: η varies systematically with regime (WHALE/HERD/NASCENT
have higher η than EQUILIBRIUM). Computing venue-wide p25/p75 across all
chunks would just relabel directional cells as "high η" and EQUILIBRIUM as
"low η" — no information gain. Calibration restricts to *directional*
regimes (WHALE_*, HERD_*, NASCENT_*) and reports p25/p75 within that
subset, so the multiplier discriminates clustered-cascade flow from
scattered-Poisson directional flow within the same regime class.

Output schema (matches vpin_calibration.json structure for symmetry):

    {
      "ETH/Coinbase": {
        "n_directional": 46,
        "p25": 0.20, "p50": 0.35, "p75": 0.45,
        "elevated": 0.45,   // alias for p75 — multiplier reads this
        "diffuse":  0.20    // alias for p25 — multiplier reads this
      },
      ...
    }

Usage:
    python calibrate_hawkes_eta.py \\
        --bins ETH:Coinbase=eth_coinbase_bins.json \\
        --bins ETH:Kraken=eth_kraken_bins.json \\
        --bins BTC:Coinbase=btc_coinbase_bins.json \\
        --bins BTC:Kraken=btc_kraken_bins.json \\
        --out hawkes_eta_calibration.json
"""

from __future__ import annotations

import argparse
import json
from typing import Iterable

import numpy as np

from markets_adapter import (
    MarketChunker, MarketChunkEncoder, _vpin_bucket_volume_from_corpus,
)
from phase1_5_evaluator import load_bars
from regime_classifier import classify_regime, baselines_from_corpus


DIRECTIONAL_PREFIXES = ("WHALE_", "HERD_")  # NASCENT_ also starts with WHALE_

MIN_DIRECTIONAL_CHUNKS = 20  # below this, write a fallback entry


def _is_directional(regime_value: str) -> bool:
    return regime_value.startswith(DIRECTIONAL_PREFIXES)


def _process_one(asset: str, venue: str, bins_path: str,
                   chunk_max: int, chunk_min: int) -> dict | None:
    bars = load_bars(bins_path)
    if not bars:
        return None
    chunker = MarketChunker(max_window_size=chunk_max,
                              stride=chunk_max // 2,
                              min_segment=chunk_min, mode="hybrid")
    encoder = MarketChunkEncoder(d_enc=64)
    chunks = chunker.chunk(f"{venue}-{asset}", bars)
    if not chunks:
        return None
    bv = _vpin_bucket_volume_from_corpus(chunks)
    feats = [encoder._extract(c, vpin_bucket_volume=bv) for c in chunks]
    base = baselines_from_corpus(feats)
    results = [classify_regime(f, base) for f in feats]

    etas = [float(f.hawkes_eta) for f, r in zip(feats, results)
             if _is_directional(r.regime.value) and float(f.hawkes_eta) > 0.0]

    if len(etas) < MIN_DIRECTIONAL_CHUNKS:
        # Not enough directional chunks for a defensible threshold.
        return {
            "n_directional": len(etas),
            "p25": None, "p50": None, "p75": None,
            "elevated": None, "diffuse": None,
            "note": f"too few directional chunks (<{MIN_DIRECTIONAL_CHUNKS}); "
                     "consumer falls back to literature defaults.",
        }

    p25 = round(float(np.percentile(etas, 25)), 4)
    p50 = round(float(np.percentile(etas, 50)), 4)
    p75 = round(float(np.percentile(etas, 75)), 4)
    return {
        "n_directional": len(etas),
        "p25": p25, "p50": p50, "p75": p75,
        "elevated": p75,
        "diffuse": p25,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bins", action="append", required=True,
                   help='Asset:Venue=path entries. Repeatable. '
                        'Example: ETH:Coinbase=eth_coinbase_bins.json')
    p.add_argument("--out", default="hawkes_eta_calibration.json")
    p.add_argument("--chunk-max-size", type=int, default=30)
    p.add_argument("--chunk-min-segment", type=int, default=10)
    args = p.parse_args()

    out: dict = {}
    for entry in args.bins:
        if "=" not in entry or ":" not in entry.split("=")[0]:
            print(f"[skip] malformed --bins entry: {entry}")
            continue
        asset_venue, path = entry.split("=", 1)
        asset, venue = asset_venue.split(":", 1)
        result = _process_one(asset, venue, path,
                                args.chunk_max_size, args.chunk_min_segment)
        if result is None:
            print(f"[{asset}/{venue}] no data at {path}; skipping")
            continue
        out[f"{asset}/{venue}"] = result
        if result.get("p75") is None:
            print(f"[{asset}/{venue}] {result['note']}")
        else:
            print(f"[{asset}/{venue}] n_dir={result['n_directional']} "
                  f"p25={result['p25']} p50={result['p50']} p75={result['p75']}")

    from datetime import datetime, timezone
    payload = {
        "version": 1,
        "computed_utc": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "directional_prefixes": list(DIRECTIONAL_PREFIXES),
        "calibration": out,
    }
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nWrote {args.out}: {len(out)} (asset, venue) entries")


if __name__ == "__main__":
    main()
