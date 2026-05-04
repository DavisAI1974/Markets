"""
phase2_chunk_picker.py — list classified chunks per venue with bar-index,
wall-clock UTC start, regime label, and per-chunk diagnostics. Intended as
the bridge between phase1_5_evaluator.py and Phase 2 autoresearch
feasibility (HANDOFF_TO_CODE_PHASE2.md): pick a WHALE chunk by index, feed
it to markets_autoresearch_chunk.py.

Usage:
    python phase2_chunk_picker.py --asset ETH \\
        --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json \\
        [--regime-filter WHALE]
"""

from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone

from phase1_5_evaluator import classify_venue, load_bars


def list_chunks(label: str, bins_path: str, regime_filter: str | None,
                 chunk_max: int, chunk_min: int, multi_signal_pelt: bool) -> int:
    bars = load_bars(bins_path)
    chunks, results, base, _ = classify_venue(
        bars, label, chunk_max=chunk_max, chunk_min=chunk_min,
        multi_signal_pelt=multi_signal_pelt,
    )
    print(f"\n=== {label}: {len(chunks)} chunks "
          f"(multi_signal_pelt={multi_signal_pelt}) ===")
    print(f"  baselines: rv={base.rv:.5f}, kyle={base.kyle:.6f}, "
          f"vol={base.chunk_volume:.3f}")
    print()
    print(f"{'idx':>3}  {'regime':<24}  {'start_utc':<20}  {'bars':>5}  "
          f"{'mean_dipole':>11}  {'log_ret':>9}  {'volume':>10}  {'kyle':>10}")
    n_match = 0
    for i, (c, r) in enumerate(zip(chunks, results)):
        if not c.bars:
            continue
        if regime_filter and regime_filter not in r.regime.value:
            continue
        n_match += 1
        mean_d = sum(b.dipole for b in c.bars) / len(c.bars)
        log_ret = math.log(max(c.bars[-1].close, 1e-12)
                            / max(c.bars[0].close, 1e-12))
        vol = sum(b.volume for b in c.bars)
        kyle = abs(log_ret) / max(vol, 1e-9)
        ts0 = datetime.fromtimestamp(c.bars[0].ts, tz=timezone.utc) \
            .strftime("%Y-%m-%d %H:%M")
        print(f"{i:>3}  {r.regime.value:<24}  {ts0:<20}  {len(c.bars):>5}  "
              f"{mean_d:>+11.4f}  {log_ret:>+9.5f}  {vol:>10.3f}  "
              f"{kyle:>10.6f}")
    if regime_filter:
        print(f"\n  matched {n_match} chunk(s) with regime filter '{regime_filter}'")
    return n_match


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asset", type=str, required=True)
    p.add_argument("--cb-bins", type=str, required=True)
    p.add_argument("--kr-bins", type=str, required=True)
    p.add_argument("--regime-filter", type=str, default=None,
                   help="Substring filter on regime label, e.g. WHALE, HERD")
    p.add_argument("--chunk-max-size", type=int, default=30)
    p.add_argument("--chunk-min-segment", type=int, default=10)
    p.add_argument("--multi-signal-pelt", action="store_true", default=True,
                   help="Default ON; use --no-multi-signal-pelt to disable")
    p.add_argument("--no-multi-signal-pelt", dest="multi_signal_pelt",
                   action="store_false")
    args = p.parse_args()

    list_chunks(f"CB-{args.asset}", args.cb_bins, args.regime_filter,
                 args.chunk_max_size, args.chunk_min_segment,
                 args.multi_signal_pelt)
    list_chunks(f"KR-{args.asset}", args.kr_bins, args.regime_filter,
                 args.chunk_max_size, args.chunk_min_segment,
                 args.multi_signal_pelt)


if __name__ == "__main__":
    main()
