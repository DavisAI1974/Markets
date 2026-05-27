"""Side-by-side chunk mapping for top-100 winners vs top-100 losers.

Sibling to analyze_chunks_winners_vs_losers.py. Where that script does cohort
aggregate Cohen's d, this one dumps PER-TRADE CHUNK SEQUENCES so the actual
shape of winning vs losing trades can be inspected chunk-by-chunk.

Output:
  _chunk_sidebyside_report.txt  — grouped by (asset, venue), winners then losers,
                                  each trade on its own block with chunk-by-chunk
                                  rows showing the 5 separating features +
                                  a per-chunk archetype-match label.
  _chunk_sidebyside.csv         — same data in long format
                                  (one row per chunk).
  _chunk_archetype_match.txt    — archetype-match summary: how many chunks per
                                  cohort match the "winner shape" / "loser shape" /
                                  "mixed" archetype, per asset/venue.

The 5 separating features were identified in analyze_chunks_winners_vs_losers.py:
  spectral_entropy   d=+1.34   HIGHER in winners
  range_atr          d=-1.19   LOWER  in winners
  realized_vol       d=-1.02   LOWER  in winners
  ret_std            d=-1.02   LOWER  in winners (=realized_vol on minute bars)
  spectral_energy    d=-0.92   LOWER  in winners

Archetype-match thresholds are anchors from the cohort medians on the 67k tape.
These are visualization aids, NOT trading constants — they should be re-derived
per tape and never used directly in admission code (per no_window_fit feedback).
"""

from __future__ import annotations

import bisect
import csv
import math
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from markets_adapter import MarketBar, MarketChunker, MarketChunkEncoder
from phase1_5_evaluator import load_bars


CSV_PATH = Path(r"E:\Markets\_analysis_historical_rt_trade_shapes_20260523\per_trade.csv")
ROOT = Path(__file__).resolve().parent
OUT_TXT = ROOT / "_chunk_sidebyside_report.txt"
OUT_CSV = ROOT / "_chunk_sidebyside.csv"
OUT_ARCH = ROOT / "_chunk_archetype_match.txt"

BIN_FILES = {
    ("BTC", "Coinbase"): ROOT / "btc_coinbase_bins.json",
    ("BTC", "Kraken"): ROOT / "btc_kraken_bins.json",
    ("BTC", "Bybit"): ROOT / "btc_bybit_perp_bins.json",
    ("ETH", "Coinbase"): ROOT / "eth_coinbase_bins.json",
    ("ETH", "Kraken"): ROOT / "eth_kraken_bins.json",
    ("ETH", "Bybit"): ROOT / "eth_bybit_perp_bins.json",
}

TOP_N = 100
MIN_BARS = 16

# Archetype anchors from the 67k-tape cohort medians (midpoint between W and L).
# Used only for visual labeling; not trading constants.
SPEC_ENT_MID = 0.843
RANGE_ATR_MID = 0.00125
REALIZED_VOL_MID = 0.00090
SPEC_ENERGY_MID = 5e-6  # both medians are ~0; use a small finite midpoint

SEP_FEATURES = ("spectral_entropy", "range_atr", "realized_vol", "ret_std", "spectral_energy")

BLOCKS = " ▁▂▃▄▅▆▇█"


def _parse_float(v):
    if v is None or v == "" or v == "None":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _slice_bars_by_ts(bars, ts_start, ts_end):
    if not bars:
        return []
    ts_list = [b.ts for b in bars]
    i_start = bisect.bisect_left(ts_list, ts_start)
    i_end = bisect.bisect_right(ts_list, ts_end)
    return bars[i_start:i_end]


def _block(val, vmin, vmax):
    """Unicode block scaled by val within [vmin, vmax]."""
    if vmax <= vmin or not math.isfinite(val):
        return BLOCKS[1]
    p = max(0.0, min(1.0, (val - vmin) / (vmax - vmin)))
    return BLOCKS[1 + int(round(p * (len(BLOCKS) - 2)))]


def _archetype_label(spec_ent, range_atr, realized_vol, spec_energy):
    """Per-chunk archetype label based on how many of the 4 dimensions match
    the winner-shape side of the cohort midpoint.

    Returns:
        "WIN_SHAPE"   if all 4 match winner direction
        "WIN_LEAN"    if 3 of 4
        "MIXED"       if 2 of 4
        "LOSE_LEAN"   if 3 of 4 match loser direction (1 of 4 winner)
        "LOSE_SHAPE"  if all 4 match loser direction
    """
    w_match = 0
    if spec_ent >= SPEC_ENT_MID:
        w_match += 1
    if range_atr <= RANGE_ATR_MID:
        w_match += 1
    if realized_vol <= REALIZED_VOL_MID:
        w_match += 1
    if spec_energy <= SPEC_ENERGY_MID:
        w_match += 1
    return {4: "WIN_SHAPE", 3: "WIN_LEAN", 2: "MIXED", 1: "LOSE_LEAN", 0: "LOSE_SHAPE"}[w_match]


def _features_to_scalar_dict(features):
    d = asdict(features)
    return {k: float(v) for k, v in d.items() if isinstance(v, (int, float))}


def main():
    if not CSV_PATH.exists():
        print(f"MISSING: {CSV_PATH}", flush=True)
        sys.exit(1)

    print(f"Loading {CSV_PATH} ...", flush=True)
    trades = []
    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            net_bps = _parse_float(r.get("net_bps"))
            entry_ts = _parse_float(r.get("entry_ts"))
            exit_ts = _parse_float(r.get("exit_ts"))
            if net_bps is None or entry_ts is None or exit_ts is None:
                continue
            asset = r.get("asset") or ""
            venue = r.get("venue") or ""
            if (asset, venue) not in BIN_FILES:
                continue
            trades.append({
                "id": r.get("id") or "",
                "asset": asset, "venue": venue,
                "side": r.get("side") or "",
                "strategy_id": r.get("strategy_id") or "",
                "entry_ts": entry_ts, "exit_ts": exit_ts,
                "net_bps": net_bps,
                "hold_min": _parse_float(r.get("hold_min")) or 0.0,
            })
    print(f"  loaded {len(trades)} usable rows", flush=True)
    if len(trades) < 200:
        sys.exit("not enough trades")

    sorted_by_net = sorted(trades, key=lambda t: t["net_bps"])
    losers = sorted_by_net[:TOP_N]
    winners = list(reversed(sorted_by_net[-TOP_N:]))
    print(f"  winners {winners[0]['net_bps']:+.1f}…{winners[-1]['net_bps']:+.1f}", flush=True)
    print(f"  losers  {losers[0]['net_bps']:+.1f}…{losers[-1]['net_bps']:+.1f}", flush=True)

    by_av = defaultdict(lambda: {"WIN": [], "LOSE": []})
    for t in winners:
        by_av[(t["asset"], t["venue"])]["WIN"].append(t)
    for t in losers:
        by_av[(t["asset"], t["venue"])]["LOSE"].append(t)

    chunker = MarketChunker(max_window_size=256, stride=128, min_segment=MIN_BARS, mode="hybrid")
    encoder = MarketChunkEncoder(d_enc=64, compute_hawkes=False, compute_hurst=False)

    # Per-trade chunk sequences: (asset, venue) -> cohort -> list[trade dict with "chunks" list]
    output_by_av: dict = defaultdict(lambda: {"WIN": [], "LOSE": []})
    skipped = 0

    print("\nProcessing per (asset, venue) ...", flush=True)
    t_start = time.time()
    for (asset, venue), groups in by_av.items():
        bin_path = BIN_FILES.get((asset, venue))
        if bin_path is None or not bin_path.exists():
            continue
        print(f"  Loading {asset}/{venue} bars from {bin_path.name} ...", flush=True)
        t0 = time.time()
        bars = load_bars(str(bin_path))
        print(f"    {len(bars)} bars loaded in {time.time()-t0:.1f}s", flush=True)

        for cohort in ("WIN", "LOSE"):
            for trade in groups[cohort]:
                sliced = _slice_bars_by_ts(bars, trade["entry_ts"], trade["exit_ts"])
                if len(sliced) < MIN_BARS:
                    skipped += 1
                    continue
                source_id = f"{asset}_{venue}_{trade['id']}"
                try:
                    chunks = chunker.chunk(source_id, sliced, multi_signal=True)
                except Exception as e:
                    print(f"    chunk error {source_id}: {e}", flush=True)
                    continue
                if not chunks:
                    skipped += 1
                    continue
                chunk_records = []
                for ci, chunk in enumerate(chunks):
                    try:
                        feats = encoder._extract(chunk, vpin_bucket_volume=0.0)
                    except Exception:
                        continue
                    fd = _features_to_scalar_dict(feats)
                    rec = {
                        "chunk_idx": ci,
                        "n_bars": getattr(chunk, "n_bars", None) or len(getattr(chunk, "bars", []) or []),
                        "spectral_entropy": fd.get("spectral_entropy", 0.0),
                        "range_atr": fd.get("range_atr", 0.0),
                        "realized_vol": fd.get("realized_vol", 0.0),
                        "ret_std": fd.get("ret_std", 0.0),
                        "spectral_energy": fd.get("spectral_energy", 0.0),
                        "ret_mean": fd.get("ret_mean", 0.0),
                        "mean_dipole": fd.get("mean_dipole", 0.0),
                    }
                    rec["archetype"] = _archetype_label(
                        rec["spectral_entropy"], rec["range_atr"],
                        rec["realized_vol"], rec["spectral_energy"],
                    )
                    chunk_records.append(rec)
                if chunk_records:
                    output_by_av[(asset, venue)][cohort].append({
                        **trade, "chunks": chunk_records, "n_chunks": len(chunk_records),
                    })
    print(f"\nProcessing complete in {time.time()-t_start:.1f}s (skipped {skipped})", flush=True)

    # ---- Write text report ----
    print(f"\nWriting {OUT_TXT.name} ...", flush=True)
    archetype_counts: dict = defaultdict(lambda: defaultdict(int))  # cohort -> archetype -> count

    with OUT_TXT.open("w", encoding="utf-8") as f:
        f.write("Side-by-side chunk mapping: top-100 winners vs top-100 losers\n")
        f.write(f"Source: {CSV_PATH}\n")
        f.write(f"Features tracked: {', '.join(SEP_FEATURES)}\n")
        f.write(f"Archetype anchors (midpoints, 67k tape): "
                f"spec_ent={SPEC_ENT_MID}, range_atr={RANGE_ATR_MID}, "
                f"realized_vol={REALIZED_VOL_MID}, spec_energy={SPEC_ENERGY_MID}\n")
        f.write("=" * 100 + "\n")

        # Determine ranges for unicode block scaling (use 5/95 percentile from each cohort union)
        all_chunks = []
        for av_groups in output_by_av.values():
            for cohort in ("WIN", "LOSE"):
                for tr in av_groups[cohort]:
                    all_chunks.extend(tr["chunks"])
        if not all_chunks:
            f.write("  no chunks to display\n")
            sys.exit(0)

        def _pctile(xs, p):
            s = sorted(xs)
            i = max(0, min(len(s) - 1, int(p * (len(s) - 1))))
            return s[i]

        ranges = {}
        for feat in SEP_FEATURES:
            vals = [c[feat] for c in all_chunks]
            ranges[feat] = (_pctile(vals, 0.05), _pctile(vals, 0.95))

        for (asset, venue), groups in sorted(output_by_av.items()):
            f.write(f"\n\n{'#' * 100}\n")
            f.write(f"# {asset}/{venue}  —  WIN n={len(groups['WIN'])}, LOSE n={len(groups['LOSE'])}\n")
            f.write(f"{'#' * 100}\n")

            for cohort, prefix in (("WIN", "W"), ("LOSE", "L")):
                f.write(f"\n--- {cohort} (n={len(groups[cohort])}) ---\n")
                if cohort == "WIN":
                    sorted_trades = sorted(groups[cohort], key=lambda t: -t["net_bps"])
                else:
                    sorted_trades = sorted(groups[cohort], key=lambda t: t["net_bps"])
                for idx, tr in enumerate(sorted_trades, start=1):
                    f.write(f"\n[{prefix}#{idx:02d}] id={tr['id'][:12]:<12s}  "
                            f"net_bps={tr['net_bps']:+7.1f}  side={tr['side']:<4s}  "
                            f"family={tr['strategy_id']:<25s}  hold={tr['hold_min']:5.1f}min  "
                            f"n_chunks={tr['n_chunks']}\n")
                    for c in tr["chunks"]:
                        blocks = "".join(_block(c[feat], *ranges[feat]) for feat in SEP_FEATURES)
                        f.write(f"   ck{c['chunk_idx']:>2d} [{c['n_bars']:>3d}bar]  "
                                f"se={c['spectral_entropy']:.3f}  "
                                f"rA={c['range_atr']:.5f}  "
                                f"rV={c['realized_vol']:.5f}  "
                                f"rS={c['ret_std']:.5f}  "
                                f"sE={c['spectral_energy']:.2e}  "
                                f"{blocks}  {c['archetype']:<11s}\n")
                        archetype_counts[cohort][c["archetype"]] += 1

    # ---- Write CSV (long format, one row per chunk) ----
    print(f"Writing {OUT_CSV.name} ...", flush=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        fields = ["cohort", "asset", "venue", "trade_id", "side", "strategy_id",
                  "net_bps", "hold_min", "chunk_idx", "n_bars",
                  "spectral_entropy", "range_atr", "realized_vol", "ret_std",
                  "spectral_energy", "ret_mean", "mean_dipole", "archetype"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for (asset, venue), groups in output_by_av.items():
            for cohort in ("WIN", "LOSE"):
                for tr in groups[cohort]:
                    for c in tr["chunks"]:
                        w.writerow({
                            "cohort": cohort, "asset": asset, "venue": venue,
                            "trade_id": tr["id"], "side": tr["side"],
                            "strategy_id": tr["strategy_id"],
                            "net_bps": tr["net_bps"], "hold_min": tr["hold_min"],
                            "chunk_idx": c["chunk_idx"], "n_bars": c["n_bars"],
                            "spectral_entropy": c["spectral_entropy"],
                            "range_atr": c["range_atr"],
                            "realized_vol": c["realized_vol"],
                            "ret_std": c["ret_std"],
                            "spectral_energy": c["spectral_energy"],
                            "ret_mean": c["ret_mean"],
                            "mean_dipole": c["mean_dipole"],
                            "archetype": c["archetype"],
                        })

    # ---- Write archetype-match summary ----
    print(f"Writing {OUT_ARCH.name} ...", flush=True)
    with OUT_ARCH.open("w", encoding="utf-8") as f:
        f.write("Archetype-match summary — count of chunks by archetype per cohort\n")
        f.write("=" * 100 + "\n\n")
        f.write("Archetype labels: WIN_SHAPE (4/4 match winner direction), WIN_LEAN (3/4),\n")
        f.write("                  MIXED (2/4), LOSE_LEAN (1/4), LOSE_SHAPE (0/4)\n")
        f.write("4 dimensions: spectral_entropy↑, range_atr↓, realized_vol↓, spectral_energy↓\n\n")

        # Overall
        archetypes = ["WIN_SHAPE", "WIN_LEAN", "MIXED", "LOSE_LEAN", "LOSE_SHAPE"]
        f.write(f"  {'archetype':<12s}  {'WIN_count':>10s}  {'LOSE_count':>10s}  "
                f"{'WIN_pct':>8s}  {'LOSE_pct':>8s}  {'lift_W/L':>10s}\n")
        f.write("  " + "-" * 70 + "\n")
        total_w = sum(archetype_counts["WIN"].values())
        total_l = sum(archetype_counts["LOSE"].values())
        for arch in archetypes:
            w = archetype_counts["WIN"].get(arch, 0)
            l = archetype_counts["LOSE"].get(arch, 0)
            wp = (100.0 * w / total_w) if total_w else 0.0
            lp = (100.0 * l / total_l) if total_l else 0.0
            lift = (wp / lp) if lp > 0 else float("inf") if wp > 0 else 0.0
            lift_str = f"{lift:>10.2f}" if math.isfinite(lift) else "       inf"
            f.write(f"  {arch:<12s}  {w:>10d}  {l:>10d}  {wp:>7.1f}%  {lp:>7.1f}%  {lift_str}\n")
        f.write(f"\n  Totals: WIN chunks={total_w}, LOSE chunks={total_l}\n")

        # Implication
        win_dom = archetype_counts["WIN"].get("WIN_SHAPE", 0) + archetype_counts["WIN"].get("WIN_LEAN", 0)
        lose_dom = archetype_counts["LOSE"].get("LOSE_SHAPE", 0) + archetype_counts["LOSE"].get("LOSE_LEAN", 0)
        f.write(f"\n  Winners with WIN_SHAPE or WIN_LEAN chunks: {win_dom}/{total_w} = "
                f"{100.0*win_dom/total_w if total_w else 0:.1f}%\n")
        f.write(f"  Losers  with LOSE_SHAPE or LOSE_LEAN chunks: {lose_dom}/{total_l} = "
                f"{100.0*lose_dom/total_l if total_l else 0:.1f}%\n")

    print("\nDone.", flush=True)
    print(f"  text report:        {OUT_TXT}", flush=True)
    print(f"  csv:                {OUT_CSV}", flush=True)
    print(f"  archetype summary:  {OUT_ARCH}", flush=True)


if __name__ == "__main__":
    main()
