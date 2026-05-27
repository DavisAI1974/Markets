"""Chunk-level dissection of top winners vs top losers.

Picks the TOP_N biggest winners (by net_bps) and TOP_N biggest losers (by |net_bps|)
from per_trade.csv, slices each trade's bar path from the venue bin files,
runs MarketChunker + MarketChunkEncoder on each path, and aggregates features
per cohort.

Goal: surface "hidden signals" — chunk-level features that distinguish winners
from losers but are not visible in the trade-level aggregates we currently use.

Output:
  Per encoder feature, mean / std / median for winners vs losers + separability
  (Cohen's d). Features with |d| >= 0.5 are flagged as candidate signals.
  Top discriminators get suggested-signal entries to consider for in_flight_promote
  v1.1 (or refrag's embedding feature set).

Runtime: ~3-5 min on a warm filesystem (heavy bin-file load + PELT chunking
per trade). Re-run after every phase ships.
"""

from __future__ import annotations

import bisect
import csv
import math
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

import numpy as np

from markets_adapter import MarketBar, MarketChunker, MarketChunkEncoder
from phase1_5_evaluator import load_bars


CSV_PATH = Path(r"E:\Markets\_analysis_historical_rt_trade_shapes_20260523\per_trade.csv")
ROOT = Path(__file__).resolve().parent

BIN_FILES = {
    ("BTC", "Coinbase"): ROOT / "btc_coinbase_bins.json",
    ("BTC", "Kraken"): ROOT / "btc_kraken_bins.json",
    ("BTC", "Bybit"): ROOT / "btc_bybit_perp_bins.json",
    ("ETH", "Coinbase"): ROOT / "eth_coinbase_bins.json",
    ("ETH", "Kraken"): ROOT / "eth_kraken_bins.json",
    ("ETH", "Bybit"): ROOT / "eth_bybit_perp_bins.json",
}

TOP_N = 100
MIN_BARS = 16        # PELT min_segment; need at least this many bars for chunking
SEPARABILITY_THRESHOLD = 0.5   # |Cohen's d| >= 0.5 = "candidate hidden signal"


def _parse_float(v):
    if v is None or v == "" or v == "None":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _features_to_dict(features) -> dict[str, float]:
    """Convert MarketFeatures dataclass to a flat dict, drop list-valued fields
    (like spectral coefficients) and keep only scalar features for cohort
    comparison."""
    d = asdict(features)
    scalar = {}
    for k, v in d.items():
        if isinstance(v, (int, float)):
            scalar[k] = float(v)
    return scalar


def _cohens_d(a: list[float], b: list[float]) -> float:
    """Cohen's d effect size. >= 0.2 = small, >= 0.5 = medium, >= 0.8 = large."""
    if len(a) < 2 or len(b) < 2:
        return 0.0
    mean_a = statistics.mean(a)
    mean_b = statistics.mean(b)
    var_a = statistics.variance(a) if len(a) > 1 else 0.0
    var_b = statistics.variance(b) if len(b) > 1 else 0.0
    n_a, n_b = len(a), len(b)
    pooled_sd = math.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2))
    if pooled_sd == 0:
        return 0.0
    return (mean_a - mean_b) / pooled_sd


def _quartiles(xs: list[float]) -> tuple[float, float, float]:
    if not xs:
        return 0.0, 0.0, 0.0
    s = sorted(xs)
    q25 = s[int(0.25 * (len(s) - 1))]
    q50 = s[int(0.50 * (len(s) - 1))]
    q75 = s[int(0.75 * (len(s) - 1))]
    return q25, q50, q75


def _slice_bars_by_ts(bars: list[MarketBar], ts_start: float, ts_end: float) -> list[MarketBar]:
    """Binary-search bar slice by timestamp (bars are sorted by ts)."""
    if not bars:
        return []
    ts_list = [b.ts for b in bars]
    i_start = bisect.bisect_left(ts_list, ts_start)
    i_end = bisect.bisect_right(ts_list, ts_end)
    return bars[i_start:i_end]


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
                "tte_20bps_min": _parse_float(r.get("tte_20bps_min")),
            })

    print(f"  loaded {len(trades)} usable rows", flush=True)
    if len(trades) < 200:
        print("  not enough trades for 100+100 analysis", flush=True)
        sys.exit(1)

    # Top N winners and top N losers.
    sorted_by_net = sorted(trades, key=lambda t: t["net_bps"])
    losers = sorted_by_net[:TOP_N]
    winners = list(reversed(sorted_by_net[-TOP_N:]))

    print(f"  top {TOP_N} winners: net_bps {winners[0]['net_bps']:.1f} (best) "
          f"to {winners[-1]['net_bps']:.1f} (median of top)", flush=True)
    print(f"  top {TOP_N} losers:  net_bps {losers[0]['net_bps']:.1f} (worst) "
          f"to {losers[-1]['net_bps']:.1f} (median of top)", flush=True)

    # Group trades by (asset, venue) so we load each bin file once.
    by_av = defaultdict(list)
    for t in winners:
        by_av[(t["asset"], t["venue"])].append(("WIN", t))
    for t in losers:
        by_av[(t["asset"], t["venue"])].append(("LOSE", t))

    chunker = MarketChunker(max_window_size=256, stride=128, min_segment=MIN_BARS, mode="hybrid")
    encoder = MarketChunkEncoder(d_enc=64, compute_hawkes=False, compute_hurst=False)

    # cohort -> feature_name -> list[float]
    cohort_features: dict[str, dict[str, list[float]]] = {
        "WIN": defaultdict(list),
        "LOSE": defaultdict(list),
    }
    # Per-trade aggregate (one record per trade with mean of its chunk features)
    cohort_per_trade: dict[str, list[dict]] = {"WIN": [], "LOSE": []}
    skipped_too_short = 0

    print("\nProcessing per (asset, venue) ...", flush=True)
    t_start = time.time()
    for (asset, venue), trade_list in by_av.items():
        bin_path = BIN_FILES.get((asset, venue))
        if bin_path is None or not bin_path.exists():
            print(f"  SKIP {asset}/{venue}: no bin file", flush=True)
            continue
        print(f"  Loading {asset}/{venue} bars from {bin_path.name} ...", flush=True)
        t0 = time.time()
        bars = load_bars(str(bin_path))
        print(f"    {len(bars)} bars loaded in {time.time()-t0:.1f}s", flush=True)

        for cohort, trade in trade_list:
            sliced = _slice_bars_by_ts(bars, trade["entry_ts"], trade["exit_ts"])
            if len(sliced) < MIN_BARS:
                skipped_too_short += 1
                continue
            source_id = f"{asset}_{venue}_{trade['id']}"
            try:
                chunks = chunker.chunk(source_id, sliced, multi_signal=True)
            except Exception as e:
                print(f"    chunk error {source_id}: {e}", flush=True)
                continue
            if not chunks:
                skipped_too_short += 1
                continue
            chunk_feats_for_trade = []
            for chunk in chunks:
                try:
                    feats = encoder._extract(chunk, vpin_bucket_volume=0.0)
                except Exception:
                    continue
                feat_dict = _features_to_dict(feats)
                # accumulate per chunk
                for k, v in feat_dict.items():
                    cohort_features[cohort][k].append(v)
                chunk_feats_for_trade.append(feat_dict)

            if chunk_feats_for_trade:
                # Trade-level summary: mean of chunk features for this trade
                trade_record = {
                    "id": trade["id"], "asset": asset, "venue": venue,
                    "side": trade["side"], "strategy_id": trade["strategy_id"],
                    "net_bps": trade["net_bps"], "hold_min": trade["hold_min"],
                    "tte_20bps_min": trade["tte_20bps_min"],
                    "n_chunks": len(chunk_feats_for_trade),
                }
                # Mean of each scalar feature across the trade's chunks
                all_keys = set()
                for cf in chunk_feats_for_trade:
                    all_keys.update(cf.keys())
                for k in all_keys:
                    vals = [cf[k] for cf in chunk_feats_for_trade if k in cf]
                    trade_record[f"mean_{k}"] = statistics.mean(vals) if vals else 0.0
                cohort_per_trade[cohort].append(trade_record)

    print(f"\nProcessing complete in {time.time()-t_start:.1f}s", flush=True)
    print(f"  WIN chunks={sum(len(v) for v in cohort_features['WIN'].values()) // max(1, len(cohort_features['WIN']))}",
          flush=True)
    print(f"  LOSE chunks={sum(len(v) for v in cohort_features['LOSE'].values()) // max(1, len(cohort_features['LOSE']))}",
          flush=True)
    print(f"  skipped (too short for chunking): {skipped_too_short}", flush=True)
    print(f"  WIN per-trade records: {len(cohort_per_trade['WIN'])}", flush=True)
    print(f"  LOSE per-trade records: {len(cohort_per_trade['LOSE'])}", flush=True)

    # ---- Chunk-level feature separability ----
    print("\n" + "=" * 100, flush=True)
    print("CHUNK-LEVEL FEATURE SEPARABILITY (Cohen's d, winners - losers)", flush=True)
    print("=" * 100, flush=True)

    all_features = set(cohort_features["WIN"].keys()) | set(cohort_features["LOSE"].keys())
    rows = []
    for fname in sorted(all_features):
        win_vals = cohort_features["WIN"].get(fname, [])
        lose_vals = cohort_features["LOSE"].get(fname, [])
        if len(win_vals) < 10 or len(lose_vals) < 10:
            continue
        d = _cohens_d(win_vals, lose_vals)
        win_q25, win_q50, win_q75 = _quartiles(win_vals)
        lose_q25, lose_q50, lose_q75 = _quartiles(lose_vals)
        rows.append({
            "feature": fname,
            "cohens_d": d,
            "win_med": win_q50, "lose_med": lose_q50,
            "win_q25": win_q25, "win_q75": win_q75,
            "lose_q25": lose_q25, "lose_q75": lose_q75,
            "n_win": len(win_vals), "n_lose": len(lose_vals),
        })

    rows.sort(key=lambda r: -abs(r["cohens_d"]))
    print(f"\n  {'feature':<28s}  {'cohens_d':>9s}  {'win_med':>10s}  {'lose_med':>10s}  "
          f"{'win_q25-q75':>16s}  {'lose_q25-q75':>16s}", flush=True)
    print("  " + "-" * 96, flush=True)
    for r in rows:
        marker = " ***" if abs(r["cohens_d"]) >= 0.8 else (" *" if abs(r["cohens_d"]) >= SEPARABILITY_THRESHOLD else "  ")
        print(f"  {r['feature'][:28]:<28s}  {r['cohens_d']:>+9.3f}  "
              f"{r['win_med']:>+10.4f}  {r['lose_med']:>+10.4f}  "
              f"{r['win_q25']:>+7.4f}/{r['win_q75']:>+7.4f}  "
              f"{r['lose_q25']:>+7.4f}/{r['lose_q75']:>+7.4f}{marker}", flush=True)

    candidate_signals = [r for r in rows if abs(r["cohens_d"]) >= SEPARABILITY_THRESHOLD]

    print(f"\n--- CANDIDATE HIDDEN SIGNALS (|d| >= {SEPARABILITY_THRESHOLD}) ---", flush=True)
    if not candidate_signals:
        print("  none found above threshold — features overlap heavily.", flush=True)
    else:
        for r in candidate_signals:
            direction = ("HIGHER in winners" if r["cohens_d"] > 0
                         else "LOWER in winners")
            magnitude = ("LARGE" if abs(r["cohens_d"]) >= 0.8
                         else "MEDIUM")
            print(f"  [{magnitude:>6s}] {r['feature']:<28s}  d={r['cohens_d']:+.3f}  "
                  f"{direction}  median_win={r['win_med']:+.4f}  "
                  f"median_lose={r['lose_med']:+.4f}", flush=True)

    # ---- Per-trade aggregate comparison ----
    print("\n" + "=" * 100, flush=True)
    print("PER-TRADE FEATURE COMPARISON (trade-mean of chunk features)", flush=True)
    print("=" * 100, flush=True)

    win_records = cohort_per_trade["WIN"]
    lose_records = cohort_per_trade["LOSE"]
    if win_records and lose_records:
        all_trade_keys = set()
        for r in win_records + lose_records:
            for k in r.keys():
                if k.startswith("mean_"):
                    all_trade_keys.add(k)
        trade_rows = []
        for k in sorted(all_trade_keys):
            wvals = [r[k] for r in win_records if k in r]
            lvals = [r[k] for r in lose_records if k in r]
            if len(wvals) < 10 or len(lvals) < 10:
                continue
            d = _cohens_d(wvals, lvals)
            trade_rows.append({
                "feature": k, "cohens_d": d,
                "win_mean": statistics.mean(wvals),
                "lose_mean": statistics.mean(lvals),
                "n_win": len(wvals), "n_lose": len(lvals),
            })
        trade_rows.sort(key=lambda r: -abs(r["cohens_d"]))
        print(f"\n  {'feature':<33s}  {'cohens_d':>9s}  {'win_mean':>12s}  {'lose_mean':>12s}",
              flush=True)
        print("  " + "-" * 70, flush=True)
        for r in trade_rows[:25]:
            marker = " ***" if abs(r["cohens_d"]) >= 0.8 else (" *" if abs(r["cohens_d"]) >= SEPARABILITY_THRESHOLD else "  ")
            print(f"  {r['feature'][:33]:<33s}  {r['cohens_d']:>+9.3f}  "
                  f"{r['win_mean']:>+12.4f}  {r['lose_mean']:>+12.4f}{marker}", flush=True)

    # ---- Fix suggestions based on top discriminators ----
    print("\n" + "=" * 100, flush=True)
    print("FIX SUGGESTIONS FROM HIDDEN SIGNALS", flush=True)
    print("=" * 100, flush=True)
    if not candidate_signals:
        print("  No features cross the separability threshold. Either:", flush=True)
        print("    - winners and losers are genuinely indistinguishable at chunk level", flush=True)
        print("      (the signal lives in finer microstructure or operator-form)", flush=True)
        print("    - the cohort sizes (n=100) are too small to detect medium effects", flush=True)
        print("    - the encoder doesn't capture the right features yet (refrag opportunity)", flush=True)
    else:
        print(f"\n  Top discriminating features identified — candidates for new in-flight",
              flush=True)
        print(f"  signals or as features in the refrag embedding:", flush=True)
        for r in candidate_signals[:10]:
            print(f"\n    Feature: {r['feature']}", flush=True)
            print(f"      Cohen's d = {r['cohens_d']:+.3f} ({'winners higher' if r['cohens_d']>0 else 'winners lower'})",
                  flush=True)
            print(f"      Winners median: {r['win_med']:+.4f}  (q25={r['win_q25']:+.4f}, q75={r['win_q75']:+.4f})",
                  flush=True)
            print(f"      Losers  median: {r['lose_med']:+.4f}  (q25={r['lose_q25']:+.4f}, q75={r['lose_q75']:+.4f})",
                  flush=True)
            # Suggested gate based on winners' q25 (if d > 0) or q75 (if d < 0)
            if r["cohens_d"] > 0:
                suggested_threshold = r["win_q25"]
                print(f"      Suggested gate: promote when {r['feature']} >= {suggested_threshold:+.4f}",
                      flush=True)
            else:
                suggested_threshold = r["win_q75"]
                print(f"      Suggested gate: promote when {r['feature']} <= {suggested_threshold:+.4f}",
                      flush=True)
            print(f"      Note: requires live computation of this feature on the in-flight",
                  flush=True)
            print(f"            bar window. Promote markets_in_flight_promote.py to compute",
                  flush=True)
            print(f"            chunk features per-tick if this feature lands in refrag's",
                  flush=True)
            print(f"            embedding output.",
                  flush=True)

    print("\n" + "=" * 100, flush=True)


if __name__ == "__main__":
    main()
