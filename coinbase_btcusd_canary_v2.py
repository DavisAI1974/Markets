"""
Coinbase BTC-USD canary v2 - same data, two analyses.

Collects the same 2-min Coinbase WS sample as canary v1, then runs two
analyses on it and prints them side by side:

  v1 (bin-level):   per-1s-bin dipole vs per-bin log return.
                    The original canary's brittle protocol.
  v2 (chunk-level): bars -> markets_adapter MarketChunker (PELT) ->
                    MarketChunkEncoder + FeatureScaler -> R^2 on
                    per-chunk mean_dipole vs per-chunk log return.

The point: see whether regime-aware chunking changes the verdict
(per the spectral_chunker.v2 hypothesis - operator signatures get
fragmented by fixed bins).

Pure stdlib + websockets + numpy. No scipy.
"""

from __future__ import annotations

import asyncio
import json
import math
import time
from math import erf, sqrt

import numpy as np
import websockets

from markets_adapter import (
    MarketBar,
    MarketChunker,
    MarketChunkEncoder,
    FeatureScaler,
)


PRODUCT = "BTC-USD"
DURATION_S = 120
BIN_S = 1.0
WS_URI = "wss://ws-feed.exchange.coinbase.com"


def pearsonr(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    n = len(x)
    if n < 3:
        return float("nan"), float("nan")
    r = float(np.corrcoef(x, y)[0, 1])
    if not np.isfinite(r) or abs(r) >= 1.0:
        return r, float("nan")
    t = r * np.sqrt(n - 2) / np.sqrt(max(1.0 - r * r, 1e-12))
    p = 2.0 * (1.0 - 0.5 * (1.0 + erf(abs(t) / sqrt(2.0))))
    return r, p


# ---------------------------------------------------------------------------
# Collection (1-second bins from Coinbase WS, identical to canary v1)
# ---------------------------------------------------------------------------

async def collect() -> dict[float, dict]:
    sub = {
        "type": "subscribe",
        "product_ids": [PRODUCT],
        "channels": ["matches", "ticker"],
    }
    bins: dict[float, dict] = {}
    last_mid = None
    t0 = time.time()

    async with websockets.connect(WS_URI, ping_interval=20) as ws:
        await ws.send(json.dumps(sub))
        while time.time() - t0 < DURATION_S:
            msg = json.loads(await ws.recv())
            mtype = msg.get("type", "")
            ts = int(time.time() / BIN_S) * BIN_S

            if mtype in ("match", "last_match"):
                qty = float(msg["size"])
                maker_side = msg["side"]
                b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": last_mid})
                if maker_side == "sell":
                    b["buy"] += qty       # taker bought
                elif maker_side == "buy":
                    b["sell"] += qty      # taker sold

            elif mtype == "ticker":
                bid_s = msg.get("best_bid")
                ask_s = msg.get("best_ask")
                if bid_s is None or ask_s is None:
                    continue
                last_mid = 0.5 * (float(bid_s) + float(ask_s))
                bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": last_mid})
                bins[ts]["mid"] = last_mid

    return bins


def bins_to_bars(bins: dict[float, dict]) -> list[MarketBar]:
    keys = sorted(k for k, v in bins.items() if v["mid"] is not None)
    return [
        MarketBar(
            ts=float(k),
            close=float(bins[k]["mid"]),
            open_=float(bins[k]["mid"]),
            high=float(bins[k]["mid"]),
            low=float(bins[k]["mid"]),
            volume=float(bins[k]["buy"] + bins[k]["sell"]),
            buy_vol=float(bins[k]["buy"]),
            sell_vol=float(bins[k]["sell"]),
        )
        for k in keys
    ]


# ---------------------------------------------------------------------------
# v1 analysis: per-1s-bin dipole vs per-bin log return
# ---------------------------------------------------------------------------

def analyze_v1(bars: list[MarketBar]) -> dict:
    if len(bars) < 30:
        return {"error": f"too few bars ({len(bars)}); rerun"}
    H_a = np.array([b.buy_vol for b in bars], dtype=float)
    H_b = np.array([b.sell_vol for b in bars], dtype=float)
    M = np.array([b.close for b in bars], dtype=float)
    eps = 1e-9
    dipole = (H_a - H_b) / (H_a + H_b + eps)
    ret = np.diff(np.log(np.maximum(M, 1e-12)))
    n = len(ret)
    dipole = dipole[:n]
    r_d, p_d = pearsonr(dipole, ret)
    rng = np.random.default_rng(0)
    r_shuf, _ = pearsonr(rng.permutation(dipole), ret)
    return {
        "method": "v1_bin_level",
        "n": int(n),
        "mean_buy_vol_per_s": float(H_a.mean()),
        "mean_sell_vol_per_s": float(H_b.mean()),
        "r_dipole": r_d,
        "r2_dipole": r_d * r_d,
        "p_dipole": p_d,
        "r_shuffled": r_shuf,
        "r2_shuffled": r_shuf * r_shuf,
    }


# ---------------------------------------------------------------------------
# v2 analysis: PELT chunks via markets_adapter, R^2 on chunk-level features
# ---------------------------------------------------------------------------

def analyze_v2(bars: list[MarketBar]) -> dict:
    chunker = MarketChunker(max_window_size=60, stride=30, min_segment=10, mode="hybrid")
    encoder = MarketChunkEncoder(d_enc=64)
    chunks = chunker.chunk(PRODUCT, bars)
    if len(chunks) < 4:
        return {"method": "v2_chunk_level", "error": f"too few chunks ({len(chunks)})", "n_chunks": len(chunks)}

    # Per-chunk dipole (mean within window) and per-chunk log return (close[end]/close[start])
    mean_dipoles = np.array([
        float(np.mean([b.dipole for b in c.bars])) for c in chunks
    ], dtype=float)
    chunk_log_returns = np.array([
        math.log(max(c.bars[-1].close, 1e-12) / max(c.bars[0].close, 1e-12))
        for c in chunks
    ], dtype=float)

    # Contemporaneous (lag 0) and lead (lag +1)
    r0, p0 = pearsonr(mean_dipoles, chunk_log_returns)
    r1, p1 = (float("nan"), float("nan"))
    if len(chunks) >= 5:
        r1, p1 = pearsonr(mean_dipoles[:-1], chunk_log_returns[1:])

    rng = np.random.default_rng(0)
    r_shuf, _ = pearsonr(rng.permutation(mean_dipoles), chunk_log_returns)

    # Encoder pipeline (the part that wires into deepnova downstream)
    embeds = encoder.encode(chunks)
    scaler = FeatureScaler().fit(embeds)
    embeds_z = scaler.transform_batch(embeds)

    return {
        "method": "v2_chunk_level",
        "n_chunks": int(len(chunks)),
        "chunk_window_lengths": [int(c.window_end - c.window_start) for c in chunks],
        "chunk_realized_vols": [float(c.realized_vol) for c in chunks],
        "r_dipole_lag0": r0,
        "r2_dipole_lag0": r0 * r0,
        "p_dipole_lag0": p0,
        "r_dipole_lag1": r1,
        "r2_dipole_lag1": r1 * r1,
        "p_dipole_lag1": p1,
        "r_shuffled": r_shuf,
        "r2_shuffled": r_shuf * r_shuf,
        "embed_dim": int(len(embeds_z[0])) if embeds_z else 0,
    }


def stop_gates(r2_dipole: float, r2_shuf: float, r_dipole: float) -> dict:
    A = r2_dipole > 0.03
    B = r2_shuf < 0.01
    C = r_dipole > 0
    return {
        "A_signal_above_noise": A,
        "B_shuffled_control_passes": B,
        "C_sign_consistent": C,
        "ALL_PASS": bool(A and B and C),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"[canary v2] collecting {DURATION_S}s of {PRODUCT} from Coinbase public WS...")
    bins = asyncio.run(collect())
    bars = bins_to_bars(bins)
    print(f"[canary v2] collected {len(bins)} second-bins -> {len(bars)} usable bars")

    print("\n[v1: bin-level analysis]")
    res_v1 = analyze_v1(bars)
    print(json.dumps(res_v1, indent=2))
    if "error" not in res_v1:
        gates_v1 = stop_gates(res_v1["r2_dipole"], res_v1["r2_shuffled"], res_v1["r_dipole"])
        print("[v1 gates]")
        for k, v in gates_v1.items():
            print(f"  {k}: {v}")

    print("\n[v2: PELT-chunk-level analysis via markets_adapter]")
    res_v2 = analyze_v2(bars)
    print(json.dumps(res_v2, indent=2))
    if "error" not in res_v2:
        gates_v2_lag0 = stop_gates(res_v2["r2_dipole_lag0"], res_v2["r2_shuffled"], res_v2["r_dipole_lag0"])
        print("[v2 gates - lag 0 contemporaneous]")
        for k, v in gates_v2_lag0.items():
            print(f"  {k}: {v}")
        if math.isfinite(res_v2["r_dipole_lag1"]):
            gates_v2_lag1 = stop_gates(res_v2["r2_dipole_lag1"], res_v2["r2_shuffled"], res_v2["r_dipole_lag1"])
            print("[v2 gates - lag +1 predictive]")
            for k, v in gates_v2_lag1.items():
                print(f"  {k}: {v}")

    print("\n[comparison]")
    if "error" not in res_v1 and "error" not in res_v2:
        print(f"  v1 R^2 (bin lag 0):   {res_v1['r2_dipole']:.5f}  on n={res_v1['n']} bins")
        print(f"  v2 R^2 (chunk lag 0): {res_v2['r2_dipole_lag0']:.5f}  on n={res_v2['n_chunks']} chunks")
        if math.isfinite(res_v2["r_dipole_lag1"]):
            print(f"  v2 R^2 (chunk lag+1): {res_v2['r2_dipole_lag1']:.5f}  on n={res_v2['n_chunks']-1} chunks (lead)")
