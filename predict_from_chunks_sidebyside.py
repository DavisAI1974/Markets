"""Side-by-side in-flight prediction: chunk-only vs chunk+stack.

For each trade in a stratified random sample, walks chunk-by-chunk and asks at
each chunk boundary k: "given the chunks observed so far (and the stack
features), is this trade going to win?" — then compares predictions to truth.

Two predictors run side-by-side:
  CHUNK-ONLY    cumulative mean of 4 separating features → sign-aligned z-score sum
  CHUNK+STACK   same + funding rate at entry + OI z-score at entry + news flag
                  (within ±60 min of entry)

Why two: shows exactly where chunk LACKS — trades where chunk says one thing
and stack says another, and we can see which was right.

Sampling:
  - Dedupe trades by (asset, venue, entry_ts, exit_ts) to fix the duplicate
    bar-slice issue (multiple family variants share the same chunks).
  - Stratified random sample: SAMPLE_HALF winners (net_bps > +5) + SAMPLE_HALF
    losers (net_bps < -5) from the deduped set.
  - Chronological split: first 50% by entry_ts = train (derives feature
    means/stds for z-scoring); last 50% = test (held-out evaluation).

Output:
  _predict_sidebyside_report.txt   per-trade chunk-by-chunk predictions
  _predict_sidebyside.csv          long-format CSV (one row per (trade, k))
  _predict_sidebyside_summary.txt  accuracy curves + disagreement analysis

Constants for z-scoring come from the TRAIN split, never from the test split.
No backtest-window-fitting: thresholds are derived from the train half only,
applied frozen to the test half.
"""

from __future__ import annotations

import bisect
import csv
import json
import math
import random
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from markets_adapter import MarketBar, MarketChunker, MarketChunkEncoder
from phase1_5_evaluator import load_bars


CSV_PATH = Path(r"E:\Markets\_analysis_historical_rt_trade_shapes_20260523\per_trade.csv")
ROOT = Path(__file__).resolve().parent
FUNDING_PATH = ROOT / "backend_funding_history.jsonl"
OI_PATH = ROOT / "backend_oi_history.jsonl"
NEWS_PATH = ROOT / "news_events.jsonl"

OUT_TXT = ROOT / "_predict_sidebyside_report.txt"
OUT_CSV = ROOT / "_predict_sidebyside.csv"
OUT_SUM = ROOT / "_predict_sidebyside_summary.txt"

BIN_FILES = {
    ("BTC", "Coinbase"): ROOT / "btc_coinbase_bins.json",
    ("BTC", "Kraken"): ROOT / "btc_kraken_bins.json",
    ("BTC", "Bybit"): ROOT / "btc_bybit_perp_bins.json",
    ("ETH", "Coinbase"): ROOT / "eth_coinbase_bins.json",
    ("ETH", "Kraken"): ROOT / "eth_kraken_bins.json",
    ("ETH", "Bybit"): ROOT / "eth_bybit_perp_bins.json",
}

SAMPLE_HALF = 500          # 500 winners + 500 losers = 1000 total
WIN_THRESHOLD_BPS = 5.0    # net_bps > this  → winner label
LOSE_THRESHOLD_BPS = -5.0  # net_bps < this  → loser label
MIN_BARS = 16
SEED = 42
NEWS_WINDOW_SEC = 3600     # ±60 min of entry → news flag fires

# Features chunk-only uses (5 separating + ret_std redundant with realized_vol)
CHUNK_FEATS = ("spectral_entropy", "range_atr", "realized_vol", "spectral_energy")
# Stack features (non-chunk-derived)
STACK_FEATS = ("funding_rate", "oi_zscore", "news_flag")


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


def _features_to_scalar_dict(features):
    d = asdict(features)
    return {k: float(v) for k, v in d.items() if isinstance(v, (int, float))}


# -------- Stack feature loaders --------

def load_funding():
    """Return dict[(asset, venue)] -> sorted list[(ts, rate)]."""
    by_av: dict = defaultdict(list)
    if not FUNDING_PATH.exists():
        return by_av
    with FUNDING_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = _parse_float(row.get("ts_utc"))
            rate = _parse_float(row.get("rate"))
            asset = row.get("asset") or ""
            venue = row.get("venue") or ""
            if ts is None or rate is None or not asset or not venue:
                continue
            by_av[(asset, venue)].append((ts, rate))
    for k in by_av:
        by_av[k].sort(key=lambda r: r[0])
    return by_av


def funding_at(funding_by_av, ts, asset, venue):
    """Most recent funding rate before ts. Falls back across venues if needed."""
    for v in (venue, "Bybit"):  # Bybit is the only one with funding data
        ts_list = funding_by_av.get((asset, v), [])
        if not ts_list:
            continue
        keys = [r[0] for r in ts_list]
        i = bisect.bisect_right(keys, ts) - 1
        if i >= 0:
            return ts_list[i][1]
    return 0.0


def load_oi():
    """Return dict[(asset, venue)] -> sorted list[(ts, oi)]."""
    by_av: dict = defaultdict(list)
    if not OI_PATH.exists():
        return by_av
    with OI_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = _parse_float(row.get("ts_utc"))
            oi = _parse_float(row.get("oi"))
            asset = row.get("asset") or ""
            venue = row.get("venue") or ""
            if ts is None or oi is None or not asset or not venue:
                continue
            by_av[(asset, venue)].append((ts, oi))
    for k in by_av:
        by_av[k].sort(key=lambda r: r[0])
    return by_av


def oi_zscore_at(oi_by_av, ts, asset, venue, lookback_sec=86400 * 3):
    """OI z-score: (oi_now - mean_lookback) / std_lookback, lookback 3 days."""
    for v in (venue, "Bybit"):
        ts_list = oi_by_av.get((asset, v), [])
        if not ts_list:
            continue
        keys = [r[0] for r in ts_list]
        i_now = bisect.bisect_right(keys, ts) - 1
        if i_now < 0:
            continue
        oi_now = ts_list[i_now][1]
        # lookback window
        ts_start = ts - lookback_sec
        i_start = bisect.bisect_left(keys, ts_start)
        window = [r[1] for r in ts_list[i_start:i_now + 1]]
        if len(window) < 5:
            return 0.0
        m = statistics.mean(window)
        sd = statistics.pstdev(window)
        return ((oi_now - m) / sd) if sd > 0 else 0.0
    return 0.0


def load_news():
    """Return list[(ts, assets_set)] sorted by ts."""
    items: list = []
    if not NEWS_PATH.exists():
        return items
    with NEWS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            iso = row.get("published_at") or ""
            if not iso:
                continue
            # Parse ISO timestamp (handle both with and without trailing Z)
            try:
                import datetime as _dt
                iso_norm = iso.replace("Z", "+00:00")
                dt = _dt.datetime.fromisoformat(iso_norm)
                ts = dt.timestamp()
            except (ValueError, TypeError):
                continue
            assets = frozenset(row.get("assets") or [])
            items.append((ts, assets))
    items.sort(key=lambda r: r[0])
    return items


def news_flag_at(news_items, ts, asset, window_sec=NEWS_WINDOW_SEC):
    """1.0 if a news event mentioning `asset` is within ±window_sec of ts."""
    if not news_items:
        return 0.0
    keys = [r[0] for r in news_items]
    i_lo = bisect.bisect_left(keys, ts - window_sec)
    i_hi = bisect.bisect_right(keys, ts + window_sec)
    for j in range(i_lo, i_hi):
        if asset in news_items[j][1]:
            return 1.0
    return 0.0


# -------- Sampling + chunking --------

def load_trades():
    if not CSV_PATH.exists():
        sys.exit(f"MISSING: {CSV_PATH}")
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
    return trades


def stratified_sample(trades):
    """Dedupe by (asset, venue, entry_ts, exit_ts), then sample SAMPLE_HALF
    winners and SAMPLE_HALF losers."""
    by_slice: dict = defaultdict(list)
    for t in trades:
        key = (t["asset"], t["venue"], t["entry_ts"], t["exit_ts"])
        by_slice[key].append(t)
    # Take first representative per slice (stable: by family alpha order)
    reps = []
    for k, group in by_slice.items():
        group.sort(key=lambda x: x["strategy_id"])
        reps.append(group[0])

    winners = [t for t in reps if t["net_bps"] > WIN_THRESHOLD_BPS]
    losers = [t for t in reps if t["net_bps"] < LOSE_THRESHOLD_BPS]
    print(f"  deduped: {len(reps)} unique bar-slices "
          f"({len(winners)} winners > +{WIN_THRESHOLD_BPS}bps, "
          f"{len(losers)} losers < {LOSE_THRESHOLD_BPS}bps)", flush=True)

    rng = random.Random(SEED)
    rng.shuffle(winners)
    rng.shuffle(losers)
    sample_w = winners[:SAMPLE_HALF]
    sample_l = losers[:SAMPLE_HALF]
    return sample_w + sample_l


def chunk_trade(trade, bars_by_av, chunker, encoder):
    """Return list of chunk feature dicts (one per chunk). [] if too short."""
    bars = bars_by_av.get((trade["asset"], trade["venue"]))
    if bars is None:
        return []
    sliced = _slice_bars_by_ts(bars, trade["entry_ts"], trade["exit_ts"])
    if len(sliced) < MIN_BARS:
        return []
    source_id = f"{trade['asset']}_{trade['venue']}_{trade['id']}"
    try:
        chunks = chunker.chunk(source_id, sliced, multi_signal=True)
    except Exception:
        return []
    out = []
    for chunk in chunks:
        try:
            feats = encoder._extract(chunk, vpin_bucket_volume=0.0)
        except Exception:
            continue
        fd = _features_to_scalar_dict(feats)
        out.append({k: fd.get(k, 0.0) for k in CHUNK_FEATS})
    return out


# -------- Predictor --------

class FeatureNormalizer:
    """Z-score normalizer derived from TRAIN split only.
    For each feature, store mean and std on the train winner+loser pooled set.
    """
    def __init__(self):
        self.params: dict = {}

    def fit(self, samples):
        """samples is list of dict-like with all feature keys present."""
        all_keys = set()
        for s in samples:
            all_keys.update(s.keys())
        for k in all_keys:
            vals = [s[k] for s in samples if k in s and math.isfinite(s[k])]
            if not vals:
                continue
            m = statistics.mean(vals)
            sd = statistics.pstdev(vals) if len(vals) > 1 else 1.0
            sd = sd if sd > 1e-12 else 1.0
            self.params[k] = (m, sd)

    def z(self, feat, val):
        m, sd = self.params.get(feat, (0.0, 1.0))
        return (val - m) / sd


# Sign of each feature aligned with "winner direction" (positive = points toward winner).
# Based on the chunk analyzer Cohen's d output:
#   spectral_entropy HIGHER in winners → +
#   range_atr LOWER in winners → -
#   realized_vol LOWER in winners → -
#   spectral_energy LOWER in winners → -
#   funding_rate HIGHER = crowded = more losers → -
#   oi_zscore HIGHER = stress-loaded = more losers → -
#   news_flag = volatility spike → typically more losers → -
WINNER_SIGN = {
    "spectral_entropy": +1.0,
    "range_atr": -1.0,
    "realized_vol": -1.0,
    "spectral_energy": -1.0,
    "funding_rate": -1.0,
    "oi_zscore": -1.0,
    "news_flag": -1.0,
}


def chunk_only_score(cumulative_chunk_feats, normalizer):
    """Score from chunk features only. Sign-aligned z-score sum."""
    s = 0.0
    for feat in CHUNK_FEATS:
        if feat not in cumulative_chunk_feats:
            continue
        z = normalizer.z(feat, cumulative_chunk_feats[feat])
        s += WINNER_SIGN.get(feat, 0.0) * z
    return s


def stack_score(cumulative_chunk_feats, stack_feats, normalizer):
    """Score from chunk + stack features."""
    s = chunk_only_score(cumulative_chunk_feats, normalizer)
    for feat in STACK_FEATS:
        if feat not in stack_feats:
            continue
        z = normalizer.z(feat, stack_feats[feat])
        s += WINNER_SIGN.get(feat, 0.0) * z
    return s


# -------- Main --------

def main():
    print(f"Loading {CSV_PATH} ...", flush=True)
    all_trades = load_trades()
    print(f"  loaded {len(all_trades)} usable rows", flush=True)

    sample = stratified_sample(all_trades)
    print(f"  sample size: {len(sample)}", flush=True)

    # Chronological split (by entry_ts) for clean train/test
    sample.sort(key=lambda t: t["entry_ts"])
    split = len(sample) // 2
    train, test = sample[:split], sample[split:]
    print(f"  train n={len(train)}, test n={len(test)}", flush=True)

    # Load stack data
    print("Loading stack feature sources ...", flush=True)
    funding = load_funding()
    oi = load_oi()
    news = load_news()
    print(f"  funding venues: {sorted(funding.keys())}", flush=True)
    print(f"  oi venues: {sorted(oi.keys())}", flush=True)
    print(f"  news events: {len(news)}", flush=True)

    # Load bars once per (asset, venue)
    print("Loading bars per (asset, venue) ...", flush=True)
    bars_by_av: dict = {}
    needed_av = set((t["asset"], t["venue"]) for t in sample)
    t_start = time.time()
    for av in needed_av:
        bin_path = BIN_FILES.get(av)
        if bin_path is None or not bin_path.exists():
            continue
        print(f"  loading {av[0]}/{av[1]} ...", flush=True)
        t0 = time.time()
        bars_by_av[av] = load_bars(str(bin_path))
        print(f"    {len(bars_by_av[av])} bars in {time.time()-t0:.1f}s", flush=True)
    print(f"All bars loaded in {time.time()-t_start:.1f}s", flush=True)

    chunker = MarketChunker(max_window_size=256, stride=128, min_segment=MIN_BARS, mode="hybrid")
    encoder = MarketChunkEncoder(d_enc=64, compute_hawkes=False, compute_hurst=False)

    print("Chunking + stack-feature lookup per trade ...", flush=True)
    t_start = time.time()

    # For each trade, compute chunk sequence AND stack features at entry
    def enrich(trade):
        chunks = chunk_trade(trade, bars_by_av, chunker, encoder)
        if not chunks:
            return None
        trade["chunks"] = chunks
        # Cumulative features at each chunk boundary k (1-indexed)
        trade["cumulative_at_k"] = []
        for k in range(1, len(chunks) + 1):
            chunk_window = chunks[:k]
            cum = {}
            for feat in CHUNK_FEATS:
                vals = [c[feat] for c in chunk_window]
                cum[feat] = statistics.mean(vals)
            trade["cumulative_at_k"].append(cum)
        # Stack features evaluated at ENTRY
        ts = trade["entry_ts"]
        trade["stack_feats"] = {
            "funding_rate": funding_at(funding, ts, trade["asset"], trade["venue"]),
            "oi_zscore": oi_zscore_at(oi, ts, trade["asset"], trade["venue"]),
            "news_flag": news_flag_at(news, ts, trade["asset"]),
        }
        return trade

    train_enriched = [t for t in (enrich(t) for t in train) if t is not None]
    test_enriched = [t for t in (enrich(t) for t in test) if t is not None]
    print(f"  enriched: train n={len(train_enriched)}, test n={len(test_enriched)} "
          f"({time.time()-t_start:.1f}s)", flush=True)

    # Fit normalizer on train set: pool all cumulative-feature snapshots + stack feats
    print("Fitting normalizer on TRAIN split ...", flush=True)
    train_snapshots = []
    for t in train_enriched:
        for cum in t["cumulative_at_k"]:
            snapshot = {**cum, **t["stack_feats"]}
            train_snapshots.append(snapshot)
    normalizer = FeatureNormalizer()
    normalizer.fit(train_snapshots)
    print(f"  fitted {len(normalizer.params)} feature normalizers", flush=True)
    for feat in CHUNK_FEATS + STACK_FEATS:
        m, sd = normalizer.params.get(feat, (None, None))
        print(f"    {feat:<20s}  mean={m}  std={sd}", flush=True)

    # Apply both predictors to TEST set, per chunk boundary
    # Bucket k into relative buckets so all trades comparable: K=1 (early), K=middle, K=final
    print("Applying predictors to TEST set ...", flush=True)
    # Per-trade per-k records
    pred_rows = []
    for trade in test_enriched:
        n_chunks = len(trade["chunks"])
        truth = 1 if trade["net_bps"] > 0 else 0
        for k_idx, cum in enumerate(trade["cumulative_at_k"], start=1):
            chunk_s = chunk_only_score(cum, normalizer)
            stack_s = stack_score(cum, trade["stack_feats"], normalizer)
            chunk_pred = 1 if chunk_s > 0 else 0
            stack_pred = 1 if stack_s > 0 else 0
            pred_rows.append({
                "trade_id": trade["id"], "asset": trade["asset"], "venue": trade["venue"],
                "side": trade["side"], "strategy_id": trade["strategy_id"],
                "net_bps": trade["net_bps"], "hold_min": trade["hold_min"],
                "n_chunks_total": n_chunks,
                "k": k_idx,
                "k_frac": k_idx / n_chunks,
                "chunk_score": chunk_s, "stack_score": stack_s,
                "chunk_pred": chunk_pred, "stack_pred": stack_pred,
                "truth": truth,
                "funding_rate": trade["stack_feats"]["funding_rate"],
                "oi_zscore": trade["stack_feats"]["oi_zscore"],
                "news_flag": trade["stack_feats"]["news_flag"],
            })

    # Write CSV
    print(f"Writing {OUT_CSV.name} ...", flush=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        fields = ["trade_id", "asset", "venue", "side", "strategy_id",
                  "net_bps", "hold_min", "n_chunks_total", "k", "k_frac",
                  "chunk_score", "stack_score", "chunk_pred", "stack_pred", "truth",
                  "funding_rate", "oi_zscore", "news_flag"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(pred_rows)

    # Per-trade side-by-side text report
    print(f"Writing {OUT_TXT.name} ...", flush=True)
    with OUT_TXT.open("w", encoding="utf-8") as f:
        f.write("Side-by-side in-flight prediction: CHUNK-only vs CHUNK+STACK\n")
        f.write(f"Test set: {len(test_enriched)} trades, "
                f"{sum(1 for t in test_enriched if t['net_bps']>0)} winners / "
                f"{sum(1 for t in test_enriched if t['net_bps']<0)} losers\n")
        f.write("Stack features: funding_rate, oi_zscore, news_flag (±60min)\n")
        f.write("Score > 0 → predict WIN; Score ≤ 0 → predict LOSE\n")
        f.write("=" * 100 + "\n")

        for trade in sorted(test_enriched, key=lambda t: -abs(t["net_bps"]))[:200]:
            truth = "WIN" if trade["net_bps"] > 0 else "LOSE"
            stack_feats = trade["stack_feats"]
            f.write(f"\n{trade['asset']}/{trade['venue']}  id={trade['id'][:18]:<18s}  "
                    f"net_bps={trade['net_bps']:+7.1f}  truth={truth}  "
                    f"family={trade['strategy_id']:<24s}  hold={trade['hold_min']:5.1f}min  "
                    f"n_chunks={len(trade['chunks'])}\n")
            f.write(f"  stack: funding={stack_feats['funding_rate']:+.5f}  "
                    f"oi_z={stack_feats['oi_zscore']:+.2f}  news={stack_feats['news_flag']:.0f}\n")
            for k_idx, cum in enumerate(trade["cumulative_at_k"], start=1):
                chunk_s = chunk_only_score(cum, normalizer)
                stack_s = stack_score(cum, stack_feats, normalizer)
                c_pred = "WIN" if chunk_s > 0 else "LOSE"
                s_pred = "WIN" if stack_s > 0 else "LOSE"
                c_right = "✓" if (c_pred == truth) else "✗"
                s_right = "✓" if (s_pred == truth) else "✗"
                agree = "==" if c_pred == s_pred else "!="
                f.write(f"   k={k_idx}/{len(trade['chunks'])}  "
                        f"chunk={chunk_s:+6.2f}→{c_pred} {c_right}  {agree}  "
                        f"stack={stack_s:+6.2f}→{s_pred} {s_right}\n")

    # Summary: accuracy curves + disagreement
    print(f"Writing {OUT_SUM.name} ...", flush=True)
    with OUT_SUM.open("w", encoding="utf-8") as f:
        f.write("Side-by-side prediction summary\n")
        f.write("=" * 100 + "\n\n")
        f.write(f"Test set: {len(test_enriched)} trades\n")
        n_test_w = sum(1 for t in test_enriched if t["net_bps"] > 0)
        n_test_l = sum(1 for t in test_enriched if t["net_bps"] < 0)
        f.write(f"  winners (net_bps > 0): {n_test_w}\n")
        f.write(f"  losers  (net_bps < 0): {n_test_l}\n")
        f.write(f"  base rate (winner prior): {100.0*n_test_w/len(test_enriched):.1f}%\n\n")

        # Accuracy by k_frac bucket (relative position in trade)
        f.write("ACCURACY VS RELATIVE CHUNK POSITION (k_frac = chunks_seen / total_chunks)\n")
        f.write("=" * 100 + "\n")
        buckets = [(0.0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.01)]
        f.write(f"\n  {'k_frac':<14s}  {'n_obs':>6s}  "
                f"{'chunk_acc':>10s}  {'stack_acc':>10s}  "
                f"{'chunk_W_recall':>15s}  {'stack_W_recall':>15s}  {'lift':>6s}\n")
        f.write("  " + "-" * 90 + "\n")
        for lo, hi in buckets:
            in_bucket = [r for r in pred_rows if lo <= r["k_frac"] < hi]
            if not in_bucket:
                continue
            c_correct = sum(1 for r in in_bucket if r["chunk_pred"] == r["truth"])
            s_correct = sum(1 for r in in_bucket if r["stack_pred"] == r["truth"])
            w_obs = [r for r in in_bucket if r["truth"] == 1]
            c_w_recall = (sum(1 for r in w_obs if r["chunk_pred"] == 1) / len(w_obs) if w_obs else 0.0)
            s_w_recall = (sum(1 for r in w_obs if r["stack_pred"] == 1) / len(w_obs) if w_obs else 0.0)
            c_acc = c_correct / len(in_bucket)
            s_acc = s_correct / len(in_bucket)
            lift = s_acc / c_acc if c_acc > 0 else 0.0
            f.write(f"  [{lo:.2f}-{hi:.2f}]    {len(in_bucket):>6d}  "
                    f"{c_acc:>10.3f}  {s_acc:>10.3f}  "
                    f"{c_w_recall:>15.3f}  {s_w_recall:>15.3f}  {lift:>6.3f}\n")

        # By absolute k (chunks 1, 2, 3, 4+)
        f.write("\n\nACCURACY VS ABSOLUTE CHUNK INDEX k\n")
        f.write("=" * 100 + "\n")
        f.write(f"\n  {'k':>3s}  {'n_obs':>6s}  "
                f"{'chunk_acc':>10s}  {'stack_acc':>10s}\n")
        f.write("  " + "-" * 40 + "\n")
        ks = sorted(set(r["k"] for r in pred_rows))
        for k in ks:
            if k > 6:
                continue
            in_k = [r for r in pred_rows if r["k"] == k]
            c_acc = sum(1 for r in in_k if r["chunk_pred"] == r["truth"]) / len(in_k)
            s_acc = sum(1 for r in in_k if r["stack_pred"] == r["truth"]) / len(in_k)
            f.write(f"  {k:>3d}  {len(in_k):>6d}  {c_acc:>10.3f}  {s_acc:>10.3f}\n")

        # Disagreement analysis: where chunk and stack differ, which is right?
        f.write("\n\nDISAGREEMENT ANALYSIS\n")
        f.write("=" * 100 + "\n")
        f.write("(Rows where chunk_pred != stack_pred; resolution: which was correct)\n\n")
        disagreements = [r for r in pred_rows if r["chunk_pred"] != r["stack_pred"]]
        if not disagreements:
            f.write("  No disagreements (predictors are identical on this test set)\n")
        else:
            chunk_correct = sum(1 for r in disagreements if r["chunk_pred"] == r["truth"])
            stack_correct = sum(1 for r in disagreements if r["stack_pred"] == r["truth"])
            f.write(f"  Total disagreements: {len(disagreements)}\n")
            f.write(f"  Chunk was right: {chunk_correct}  ({100.0*chunk_correct/len(disagreements):.1f}%)\n")
            f.write(f"  Stack was right: {stack_correct}  ({100.0*stack_correct/len(disagreements):.1f}%)\n")
            f.write(f"  Net stack advantage: {stack_correct - chunk_correct} predictions\n\n")

            # Disagreement bucketed by k_frac
            f.write(f"\n  Disagreement breakdown by k_frac bucket:\n")
            f.write(f"\n  {'k_frac':<14s}  {'n_disagree':>10s}  {'chunk_right':>12s}  {'stack_right':>12s}\n")
            for lo, hi in buckets:
                in_b = [r for r in disagreements if lo <= r["k_frac"] < hi]
                if not in_b:
                    continue
                c_r = sum(1 for r in in_b if r["chunk_pred"] == r["truth"])
                s_r = sum(1 for r in in_b if r["stack_pred"] == r["truth"])
                f.write(f"  [{lo:.2f}-{hi:.2f}]    {len(in_b):>10d}  "
                        f"{c_r:>12d}  {s_r:>12d}\n")

        # Earliest reliable prediction
        f.write("\n\nEARLIEST RELIABLE PREDICTION\n")
        f.write("=" * 100 + "\n")
        f.write("(First k_frac bucket where accuracy ≥ 0.7 for each predictor)\n\n")
        for label, pred_key in (("CHUNK-only", "chunk_pred"), ("CHUNK+STACK", "stack_pred")):
            earliest = None
            for lo, hi in buckets:
                in_b = [r for r in pred_rows if lo <= r["k_frac"] < hi]
                if not in_b:
                    continue
                acc = sum(1 for r in in_b if r[pred_key] == r["truth"]) / len(in_b)
                if acc >= 0.7:
                    earliest = (lo, hi, acc, len(in_b))
                    break
            if earliest:
                f.write(f"  {label}:    k_frac ∈ [{earliest[0]:.2f}, {earliest[1]:.2f})  "
                        f"acc={earliest[2]:.3f}  (n={earliest[3]})\n")
            else:
                f.write(f"  {label}:    NEVER reaches 0.7 accuracy\n")

    print(f"\nDone.", flush=True)
    print(f"  per-trade report:   {OUT_TXT}", flush=True)
    print(f"  CSV:                {OUT_CSV}", flush=True)
    print(f"  summary:            {OUT_SUM}", flush=True)


if __name__ == "__main__":
    main()
