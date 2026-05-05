"""
build_playbook_registry.py — compute per-(asset, venue, regime) edge
statistics and dump to a registry JSON the runtime playbook generator
reads.

For each (asset, venue) loaded from bins, runs the Phase 1.5 classifier
and computes, per regime that has any chunks:
  - n            : number of chunks of this regime
  - r            : Pearson r of (chunk mean_dipole_t, next-chunk log_return)
  - r2, p        : R² and p-value
  - direction    : "momentum" if r>+0.3 with p<0.20,
                   "mean_revert" if r<-0.3 with p<0.20,
                   else "exploring"
  - last_updated : ISO timestamp

Writes playbook_registry.json keyed by "<ASSET>/<VENUE>/<REGIME>".
playbook_generator.py reads this at signal-emit time so the actionable
text reflects the current data, not a hand-coded theory.

Usage:
    python build_playbook_registry.py \\
        --asset ETH \\
        --cb-bins eth_coinbase_bins.json \\
        --kr-bins eth_kraken_bins.json \\
        --output-path playbook_registry.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone

import numpy as np

from phase1_5_evaluator import classify_venue, load_bars, _pearsonr_with_p


def _per_regime_edge(chunks: list, results: list, k: int = 1) -> dict:
    """Mirror the gate-I computation: per regime, correlation of mean
    dipole_t with next-chunk log return at lag k."""
    if len(chunks) < k + 2:
        return {}
    mean_dipoles = []
    chunk_returns = []
    for c in chunks:
        bar_dips = [b.dipole for b in c.bars]
        mean_dipoles.append(float(np.mean(bar_dips)) if bar_dips else 0.0)
        if len(c.bars) >= 2:
            r_ret = math.log(max(c.bars[-1].close, 1e-12)
                              / max(c.bars[0].close, 1e-12))
        else:
            r_ret = 0.0
        chunk_returns.append(r_ret)
    md = np.array(mean_dipoles)
    cr = np.array(chunk_returns)
    labels = [r.regime.value for r in results]

    out: dict[str, dict] = {}
    for regime in set(labels):
        idx = [i for i in range(len(chunks) - k) if labels[i] == regime]
        n = len(idx)
        if n < 1:
            continue
        if n < 3:
            out[regime] = {"n": n, "r": None, "r2": None, "p": None,
                            "direction": "insufficient",
                            "note": "n<3; sample too small to claim direction"}
            continue
        x = md[idx]
        y = cr[[i + k for i in idx]]
        r, p, npairs = _pearsonr_with_p(x, y)
        if not (np.isfinite(r) and np.isfinite(p)):
            out[regime] = {"n": npairs, "r": None, "r2": None, "p": None,
                            "direction": "insufficient",
                            "note": "degenerate variance"}
            continue
        # Direction call is INTENTIONALLY permissive: we want the playbook
        # to update each pass and force awareness of how the read evolves.
        # Loosely: |r|>0.3 with p<0.20 is enough to tag momentum or
        # mean_revert; anything else is "exploring". Caller surfaces the
        # n + p so the user sees the small-sample caveat in the text.
        if r > 0.3 and p < 0.20:
            direction = "momentum"
        elif r < -0.3 and p < 0.20:
            direction = "mean_revert"
        else:
            direction = "exploring"
        out[regime] = {
            "n": int(npairs),
            "r": round(float(r), 4),
            "r2": round(float(r * r), 5),
            "p": round(float(p), 4),
            "direction": direction,
        }
    return out


def build_registry(asset: str, cb_bins_path: str, kr_bins_path: str,
                    multi_signal_pelt: bool = True) -> dict:
    """Run classify_venue on each venue and compute per-regime edge stats.
    Returns a dict shaped:
      {
        "ETH/CB/WHALE_UP":   {n, r, r2, p, direction, last_updated},
        "ETH/KR/WHALE_UP":   {...},
        "ETH/CB/HERD_DOWN":  {...},
        ...
      }
    """
    out: dict[str, dict] = {}
    now = datetime.now(timezone.utc).isoformat()
    for venue_short, bins_path in (("CB", cb_bins_path), ("KR", kr_bins_path)):
        if not os.path.exists(bins_path):
            print(f"[registry] skipping {venue_short}: {bins_path} missing")
            continue
        bars = load_bars(bins_path)
        if not bars:
            continue
        chunks, results, _, _ = classify_venue(
            bars, f"{venue_short}-{asset}",
            chunk_max=30, chunk_min=10,
            multi_signal_pelt=multi_signal_pelt,
        )
        per_regime = _per_regime_edge(chunks, results, k=1)
        for regime, stats in per_regime.items():
            key = f"{asset}/{venue_short}/{regime}"
            out[key] = {**stats, "last_updated": now,
                          "asset": asset, "venue": venue_short, "regime": regime}
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asset", required=True)
    p.add_argument("--cb-bins", required=True)
    p.add_argument("--kr-bins", required=True)
    p.add_argument("--output-path", default="playbook_registry.json")
    p.add_argument("--no-multi-signal-pelt", dest="multi_signal_pelt",
                   action="store_false")
    p.set_defaults(multi_signal_pelt=True)
    args = p.parse_args()

    new_entries = build_registry(args.asset, args.cb_bins, args.kr_bins,
                                   multi_signal_pelt=args.multi_signal_pelt)

    # Merge with existing registry — different assets may live side by side.
    existing: dict = {}
    if os.path.exists(args.output_path):
        try:
            with open(args.output_path) as f:
                existing = json.load(f)
        except Exception:
            existing = {}
    existing.update(new_entries)

    with open(args.output_path, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"[registry] {len(new_entries)} entries written for asset={args.asset}")
    for k in sorted(new_entries):
        s = new_entries[k]
        n = s.get("n", 0)
        r = s.get("r")
        p_val = s.get("p")
        d = s.get("direction", "?")
        if r is None:
            print(f"  {k:<28} n={n:>3}  ({d})")
        else:
            print(f"  {k:<28} n={n:>3}  r={r:+.3f}  p={p_val:.3f}  -> {d}")
    print(f"  saved to {args.output_path}")


if __name__ == "__main__":
    main()
