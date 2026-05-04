"""
Phase 1: 4-hour Coinbase BTC-USD coefficient-trajectory run.

Per HANDOFF_TO_CODE.md (Architect -> Code):
  - WS collect 4 hours of BTC-USD trades + ticker from Coinbase
  - Bin to 1-min bars (240 bars over 4 hours)
  - PELT chunk the bar series (expect ~8-15 regime chunks)
  - Per chunk: SignalDecoder.prefill -> coefficient vector
  - 1000-permutation within-chunk shuffle control per chunk
  - Within-chunk H_a/H_b correlation -> contamination flag (>0.7 = paired-trade)
  - Output per-chunk JSON record
  - Plot coefficient trajectory with PELT boundaries marked, contaminated chunks shaded

Stop gates (Phase 1):
  A. >=1 coefficient dimension shows discontinuity at >=1 PELT boundary larger
     than max(perm_spread[k], perm_spread[k+1])
  B. >=60% of chunks pass contamination gate (corr <= 0.7)
  C. Held-out second 4-hour window shows similar discontinuity pattern

A+B alone -> signal candidate, run second window. A+B+C -> proceed to Kraken.

DURATION_S is configurable so this script can be smoke-tested with a short run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
from collections import defaultdict

import numpy as np
import websockets

from markets_adapter import (
    MarketBar,
    MarketChunker,
    MarketChunkEncoder,
    FeatureScaler,
    SignalDecoder,
)


PRODUCT = "BTC-USD"
WS_URI = "wss://ws-feed.exchange.coinbase.com"

DEFAULT_DURATION_S = 4 * 3600       # 4 hours
SECOND_BIN_S = 1.0
MINUTE_BIN_S = 60.0
N_PERMUTATIONS = 1000
CONTAMINATION_THRESHOLD = 0.7       # within-chunk H_a/H_b correlation


# ---------------------------------------------------------------------------
# Collection: 1-second bins from Coinbase WS
# ---------------------------------------------------------------------------

async def collect(duration_s: float, save_path: str) -> dict[float, dict]:
    """Stream Coinbase WS for duration_s seconds, accumulating 1-sec bins.

    Saves bins to disk every 30 seconds so a mid-run crash doesn't lose data.
    """
    sub = {
        "type": "subscribe",
        "product_ids": [PRODUCT],
        "channels": ["matches", "ticker"],
    }
    bins: dict[float, dict] = {}
    last_mid: float | None = None
    t0 = time.time()
    last_save = t0

    print(f"[collect] starting {duration_s:.0f}s collection on {PRODUCT}", flush=True)
    async with websockets.connect(WS_URI, ping_interval=20) as ws:
        await ws.send(json.dumps(sub))
        while time.time() - t0 < duration_s:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
            except asyncio.TimeoutError:
                print(f"[collect] WS recv timeout at t={time.time()-t0:.0f}s", flush=True)
                continue
            msg = json.loads(raw)
            mtype = msg.get("type", "")
            ts = int(time.time() / SECOND_BIN_S) * SECOND_BIN_S

            if mtype in ("match", "last_match"):
                qty = float(msg["size"])
                maker_side = msg["side"]
                b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": last_mid,
                                          "high": 0.0, "low": 0.0, "n_trades": 0})
                if maker_side == "sell":
                    b["buy"] += qty
                elif maker_side == "buy":
                    b["sell"] += qty
                price = float(msg.get("price", last_mid or 0.0))
                if b["high"] == 0.0 or price > b["high"]:
                    b["high"] = price
                if b["low"] == 0.0 or price < b["low"]:
                    b["low"] = price
                b["n_trades"] += 1

            elif mtype == "ticker":
                bid_s = msg.get("best_bid")
                ask_s = msg.get("best_ask")
                if bid_s is None or ask_s is None:
                    continue
                last_mid = 0.5 * (float(bid_s) + float(ask_s))
                b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": last_mid,
                                          "high": 0.0, "low": 0.0, "n_trades": 0})
                b["mid"] = last_mid

            now = time.time()
            if now - last_save >= 30.0:
                _save_bins(bins, save_path)
                last_save = now
                print(f"[collect] t={now-t0:.0f}s bins={len(bins)}", flush=True)

    _save_bins(bins, save_path)
    print(f"[collect] done. final bins={len(bins)}", flush=True)
    return bins


def _save_bins(bins: dict, path: str) -> None:
    serializable = {str(k): v for k, v in bins.items()}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(serializable, f)
    os.replace(tmp, path)


def _load_bins(path: str) -> dict[float, dict]:
    with open(path) as f:
        raw = json.load(f)
    return {float(k): v for k, v in raw.items()}


# ---------------------------------------------------------------------------
# Aggregate 1-sec bins -> 1-min bars
# ---------------------------------------------------------------------------

def aggregate_to_minute_bars(sec_bins: dict[float, dict]) -> list[MarketBar]:
    """Group 1-sec bins into 1-min OHLCV+flow bars."""
    minute_groups: dict[float, list[tuple[float, dict]]] = defaultdict(list)
    for ts, b in sec_bins.items():
        if b.get("mid") is None:
            continue
        m_ts = int(ts / MINUTE_BIN_S) * MINUTE_BIN_S
        minute_groups[m_ts].append((ts, b))

    bars: list[MarketBar] = []
    for m_ts in sorted(minute_groups):
        members = sorted(minute_groups[m_ts], key=lambda x: x[0])
        mids = [b["mid"] for _, b in members if b["mid"] is not None]
        if not mids:
            continue
        open_p = float(mids[0])
        close_p = float(mids[-1])
        # high/low: from per-second highs/lows where available, else from mids
        highs = [b["high"] for _, b in members if b.get("high", 0.0) > 0.0]
        lows = [b["low"] for _, b in members if b.get("low", 0.0) > 0.0]
        high_p = float(max(highs + mids))
        low_p = float(min(lows + mids))
        buy_v = float(sum(b["buy"] for _, b in members))
        sell_v = float(sum(b["sell"] for _, b in members))
        bars.append(MarketBar(
            ts=float(m_ts),
            close=close_p,
            open_=open_p,
            high=high_p,
            low=low_p,
            volume=buy_v + sell_v,
            buy_vol=buy_v,
            sell_vol=sell_v,
        ))
    return bars


# ---------------------------------------------------------------------------
# Per-chunk analysis: contamination, decoder, perm control
# ---------------------------------------------------------------------------

def chunk_contamination(chunk_bars: list[MarketBar]) -> float:
    """Within-chunk Pearson correlation between H_a and H_b.

    High correlation = paired trade pattern -> wash/cooperative manipulation.
    Per HANDOFF_TO_CODE: chunks with corr > CONTAMINATION_THRESHOLD are flagged
    and excluded from training and from trajectory analysis.
    """
    H_a = np.array([b.buy_vol for b in chunk_bars], dtype=float)
    H_b = np.array([b.sell_vol for b in chunk_bars], dtype=float)
    if np.std(H_a) < 1e-12 or np.std(H_b) < 1e-12:
        return 0.0
    return float(np.corrcoef(H_a, H_b)[0, 1])


def perm_spread_for_chunk(
    chunk_bars: list[MarketBar],
    encoder: MarketChunkEncoder,
    decoder: SignalDecoder,
    n_perm: int = N_PERMUTATIONS,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Within-chunk permutation noise floor.

    Shuffle bars within the chunk n_perm times, re-encode + decode each
    shuffled chunk, then compute per-coefficient-dimension spread (95th
    percentile of |perm_coef - median_perm_coef|).

    Returns: array of shape (d_enc,) with per-dim noise floor.
    """
    if rng is None:
        rng = np.random.default_rng(0)
    n_bars = len(chunk_bars)
    if n_bars < 4:
        return np.zeros(encoder.d_enc)

    bar_indices = np.arange(n_bars)
    perm_coefs = np.zeros((n_perm, encoder.d_enc))
    from markets_adapter import MarketChunk
    for i in range(n_perm):
        perm_idx = rng.permutation(bar_indices)
        shuffled = [chunk_bars[j] for j in perm_idx]
        # Wrap shuffled bars in a MarketChunk stub for encode()
        stub = MarketChunk(
            chunk_id="perm",
            source_id="perm",
            window_start=0,
            window_end=n_bars,
            bars=shuffled,
        )
        emb = encoder.encode([stub])[0]
        coefs, _ = decoder.prefill([emb], [1])
        perm_coefs[i] = np.asarray(coefs)

    median = np.median(perm_coefs, axis=0)
    abs_dev = np.abs(perm_coefs - median)
    spread_95 = np.percentile(abs_dev, 95, axis=0)
    return spread_95


# ---------------------------------------------------------------------------
# Main analysis pipeline
# ---------------------------------------------------------------------------

def analyze(
    bars: list[MarketBar],
    n_perm: int = N_PERMUTATIONS,
    chunk_max_size: int = 30,
    chunk_min_segment: int = 10,
) -> dict:
    """End-to-end Phase-1 analysis on collected 1-min bars."""
    chunker = MarketChunker(
        max_window_size=chunk_max_size,
        stride=chunk_max_size // 2,
        min_segment=chunk_min_segment,
        mode="hybrid",
    )
    encoder = MarketChunkEncoder(d_enc=64)
    decoder = SignalDecoder()

    chunks = chunker.chunk(PRODUCT, bars)
    if len(chunks) == 0:
        return {"error": f"no chunks produced", "n_bars": len(bars)}

    print(f"[analyze] {len(bars)} bars -> {len(chunks)} chunks", flush=True)

    # Per-chunk: encode + decode + contamination + perm spread
    chunk_records: list[dict] = []
    coef_matrix = np.zeros((len(chunks), encoder.d_enc))
    perm_matrix = np.zeros((len(chunks), encoder.d_enc))
    contam_pass = 0
    rng = np.random.default_rng(42)

    for i, chunk in enumerate(chunks):
        emb = encoder.encode([chunk])[0]
        coefs, posterior = decoder.prefill([emb], [1])
        coef_matrix[i] = np.asarray(coefs)

        contam_corr = chunk_contamination(chunk.bars)
        contam_flag = abs(contam_corr) > CONTAMINATION_THRESHOLD
        if not contam_flag:
            contam_pass += 1

        perm_spread = perm_spread_for_chunk(chunk.bars, encoder, decoder, n_perm=n_perm, rng=rng)
        perm_matrix[i] = perm_spread

        rec = {
            "chunk_idx": i,
            "window_start": int(chunk.window_start),
            "window_end": int(chunk.window_end),
            "n_bars": int(chunk.window_end - chunk.window_start),
            "realized_vol": float(chunk.realized_vol),
            "contamination_corr": float(contam_corr),
            "contamination_flag": bool(contam_flag),
            "underdetermined": bool(posterior["underdetermined"]),
            "coef_first_8": [float(x) for x in coefs[:8]],
            "perm_spread_first_8": [float(x) for x in perm_spread[:8]],
        }
        chunk_records.append(rec)
        print(f"[analyze] chunk[{i}] [{chunk.window_start}:{chunk.window_end}] "
              f"rv={chunk.realized_vol:.5f} contam={contam_corr:+.3f} "
              f"flag={contam_flag} perm_spread_mean={float(np.mean(perm_spread)):.4f}",
              flush=True)

    # Discontinuity check at PELT boundaries (only meaningful with >=2 chunks).
    # Fix #1: filter out permutation-invariant dims (true perm_spread ~ 0). Those
    # dims have no meaningful within-chunk noise floor, so any non-zero diff
    # gets clamped against the floor of 1e-6 and trivially passes. Examples:
    # mean_dipole, mean_ofi, range_atr (means are invariant under bar shuffle).
    # Only evaluate dims with perm_spread >= PERM_SPREAD_VALID_THRESHOLD.
    PERM_SPREAD_VALID_THRESHOLD = 0.001
    boundaries: list[dict] = []
    n_passed = 0
    for k in range(len(chunks) - 1):
        diff = np.abs(coef_matrix[k + 1] - coef_matrix[k])
        perm_combined = np.maximum(perm_matrix[k], perm_matrix[k + 1])
        valid_mask = perm_combined >= PERM_SPREAD_VALID_THRESHOLD
        n_valid = int(np.sum(valid_mask))
        if n_valid == 0:
            boundaries.append({
                "between": (k, k + 1),
                "n_valid_dims": 0,
                "n_dims_exceeding_perm95": 0,
                "max_ratio": 0.0,
                "max_ratio_dim": -1,
                "passes": False,
                "skipped_reason": "no_dims_with_meaningful_perm_spread",
            })
            continue
        diff_valid = diff[valid_mask]
        floor_valid = perm_combined[valid_mask]
        ratio = diff_valid / floor_valid
        n_dims_passing = int(np.sum(ratio > 1.0))
        max_ratio = float(np.max(ratio))
        valid_idx = np.where(valid_mask)[0]
        max_dim = int(valid_idx[int(np.argmax(ratio))])
        passed = n_dims_passing >= 1
        if passed:
            n_passed += 1
        boundaries.append({
            "between": (k, k + 1),
            "n_valid_dims": n_valid,
            "n_dims_exceeding_perm95": n_dims_passing,
            "max_ratio": max_ratio,
            "max_ratio_dim": max_dim,
            "passes": passed,
        })

    n_chunks = len(chunks)
    contam_rate = contam_pass / n_chunks if n_chunks > 0 else 0.0
    # gate_A is unevaluable with only 1 chunk (no boundaries) - report None
    gate_A = (n_passed >= 1) if n_chunks >= 2 else None
    gate_B = contam_rate >= 0.6

    return {
        "n_bars": len(bars),
        "n_chunks": n_chunks,
        "n_perm": n_perm,
        "chunks": chunk_records,
        "boundaries": boundaries,
        "n_boundaries_passing": n_passed,
        "contamination_pass_rate": contam_rate,
        "gate_A_discontinuity": gate_A,
        "gate_B_contamination": gate_B,
        "ALL_GATES_AB": bool(gate_A) and bool(gate_B) if gate_A is not None else None,
        "coef_matrix": coef_matrix.tolist(),
        "perm_matrix": perm_matrix.tolist(),
    }


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

def plot_trajectory(report: dict, out_path: str) -> bool:
    """Plot per-coefficient-dim trajectory across chunks. Returns True on success."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[plot] matplotlib not available; skipping plot", flush=True)
        return False

    coefs = np.asarray(report["coef_matrix"])
    perm = np.asarray(report["perm_matrix"])
    n_chunks, d_enc = coefs.shape
    if n_chunks < 2:
        return False

    # Top-12 most-varying dimensions across the trajectory
    cv = coefs.std(axis=0)
    top_dims = list(np.argsort(-cv)[:12])

    fig, ax = plt.subplots(figsize=(14, 7))
    x = np.arange(n_chunks)
    for d in top_dims:
        ax.plot(x, coefs[:, d], label=f"dim {d}", alpha=0.8, linewidth=1.4)
        ax.fill_between(x, coefs[:, d] - perm[:, d], coefs[:, d] + perm[:, d],
                        alpha=0.08)

    # Mark contaminated chunks with shaded background
    for rec in report["chunks"]:
        if rec["contamination_flag"]:
            ax.axvspan(rec["chunk_idx"] - 0.4, rec["chunk_idx"] + 0.4,
                       alpha=0.18, color="red")

    # Mark passing PELT boundaries
    for b in report["boundaries"]:
        if b["passes"]:
            ax.axvline(x=b["between"][0] + 0.5, color="black", linestyle="--",
                       alpha=0.5, linewidth=1)

    ax.set_xlabel("PELT chunk index")
    ax.set_ylabel("recovered coefficient (z-scored embedding)")
    ax.set_title(f"Coefficient trajectory across {n_chunks} PELT chunks "
                 f"(top-12 most-varying dims; dashed = passing boundary; red = contaminated)")
    ax.legend(loc="upper right", fontsize=8, ncol=2)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"[plot] wrote {out_path}", flush=True)
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Phase 1 4-hour Coinbase trajectory run")
    p.add_argument("--duration", type=float, default=DEFAULT_DURATION_S,
                   help="Collection duration in seconds (default: 14400 = 4 hours)")
    p.add_argument("--n-perm", type=int, default=N_PERMUTATIONS,
                   help=f"Permutations per chunk (default: {N_PERMUTATIONS})")
    p.add_argument("--bins-path", type=str, default="phase1_bins.json",
                   help="Where to save 1-sec bins")
    p.add_argument("--report-path", type=str, default="phase1_report.json",
                   help="Where to save final analysis report")
    p.add_argument("--plot-path", type=str, default="phase1_trajectory.png",
                   help="Where to save trajectory plot")
    p.add_argument("--from-bins", action="store_true",
                   help="Skip collection, load bins from --bins-path")
    p.add_argument("--collect-only", action="store_true",
                   help="Collect WS data only (skip analysis); for use with progressive driver")
    p.add_argument("--chunk-max-size", type=int, default=30,
                   help="Max bars per PELT chunk (default 30 = 30 min at 1-min bars)")
    p.add_argument("--chunk-min-segment", type=int, default=10,
                   help="Min bars per PELT segment (default 10 = 10 min)")
    args = p.parse_args()

    if args.from_bins:
        if not os.path.exists(args.bins_path):
            print(f"[main] no bins at {args.bins_path}", file=sys.stderr)
            sys.exit(2)
        sec_bins = _load_bins(args.bins_path)
        print(f"[main] loaded {len(sec_bins)} sec bins from {args.bins_path}", flush=True)
    else:
        sec_bins = asyncio.run(collect(args.duration, args.bins_path))
        if args.collect_only:
            print(f"[main] collect-only mode; bins at {args.bins_path}; exiting", flush=True)
            return

    bars = aggregate_to_minute_bars(sec_bins)
    print(f"[main] {len(sec_bins)} sec bins -> {len(bars)} min bars", flush=True)
    if len(bars) < 5:
        print(f"[main] too few minute bars ({len(bars)}); abort", file=sys.stderr)
        sys.exit(2)

    report = analyze(
        bars,
        n_perm=args.n_perm,
        chunk_max_size=args.chunk_max_size,
        chunk_min_segment=args.chunk_min_segment,
    )

    with open(args.report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"[main] wrote {args.report_path}", flush=True)

    plot_trajectory(report, args.plot_path)

    print("\n[main] === phase 1 verdict ===")
    if "error" in report:
        print(f"  ERROR: {report['error']}")
        sys.exit(1)
    print(f"  n_chunks                       : {report['n_chunks']}")
    if report['n_chunks'] >= 2:
        print(f"  n_boundaries_passing           : {report['n_boundaries_passing']} / {report['n_chunks']-1}")
    else:
        print(f"  n_boundaries_passing           : N/A (only 1 chunk; gate A unevaluable)")
    print(f"  contamination_pass_rate        : {report['contamination_pass_rate']:.2%}")
    print(f"  gate A (>=1 disc passing perm) : {report['gate_A_discontinuity']}")
    print(f"  gate B (>=60% chunks clean)    : {report['gate_B_contamination']}")
    print(f"  ALL_GATES_AB (signal candidate): {report['ALL_GATES_AB']}")
    if report["ALL_GATES_AB"] is True:
        print("  -> next: rerun on a held-out 4-hour window (gate C replication)")
    elif report["ALL_GATES_AB"] is None:
        print("  -> too few chunks to evaluate gate A; wait for more data")
    else:
        print("  -> gates failing; will reassess at next checkpoint")


if __name__ == "__main__":
    main()
