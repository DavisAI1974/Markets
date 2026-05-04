"""
Binance BTCUSDT 2-min orderbook dipole canary — phone-friendly variant.

Identical protocol to binance_btcusdt_canary.py, but no scipy dependency
(only websockets + numpy + Python stdlib). The only scipy call in the
original was stats.pearsonr; this version computes Pearson r via
numpy.corrcoef and the two-tailed p-value via a normal approximation
(at n>=120 the t-distribution is effectively normal, accurate enough
for the canary; gate decisions A/B/C use R^2 and sign, NOT p, so the
gate verdict is bit-identical to the scipy version regardless).

Install on phone:
  Android (Pydroid 3 / Termux): pip install websockets numpy
  iOS (Pyto / a-Shell):         pip install websockets   (numpy bundled)

Geo note: if your phone is on a US IP, swap the host to stream.binance.us
(Binance.US is a separate, US-legal venue with thinner books).

Run: python binance_btcusdt_canary_phone.py
"""

import asyncio
import json
import time
from math import erf, sqrt
import numpy as np
import websockets


SYMBOL = "btcusdt"
DURATION_S = 120
BIN_S = 1.0
WS_HOST = "stream.binance.com:9443"   # use "stream.binance.us:9443" on US IPs


def pearsonr(x, y):
    """Pearson r and two-tailed p-value (normal approximation).

    For n>=30 the normal approximation differs from the exact t-distribution
    p-value by < 1% in the tails relevant here. Gate decisions use R^2 and
    sign only, so the canary verdict is unaffected by this approximation.
    """
    n = len(x)
    if n < 3:
        return float("nan"), float("nan")
    r = float(np.corrcoef(x, y)[0, 1])
    if not np.isfinite(r) or abs(r) >= 1.0:
        return r, float("nan")
    t = r * np.sqrt(n - 2) / np.sqrt(max(1.0 - r * r, 1e-12))
    p = 2.0 * (1.0 - 0.5 * (1.0 + erf(abs(t) / sqrt(2.0))))
    return r, p


async def collect():
    """Stream Binance trades + book ticker for DURATION_S seconds, bin to 1s.

    Both streams binned by local receive time so trade and mid bins share a
    single clock (Binance @bookTicker carries no exchange-time field).
    """
    uri = (
        f"wss://{WS_HOST}/stream"
        f"?streams={SYMBOL}@aggTrade/{SYMBOL}@bookTicker"
    )
    bins = {}
    last_mid = None
    t0 = time.time()

    async with websockets.connect(uri, ping_interval=20) as ws:
        while time.time() - t0 < DURATION_S:
            msg = json.loads(await ws.recv())
            stream = msg.get("stream", "")
            d = msg.get("data", {})
            ts = int(time.time() / BIN_S) * BIN_S

            if "aggTrade" in stream:
                qty = float(d["q"])
                # m=True -> buyer is maker -> taker sold (sell-side aggression)
                is_buyer_maker = d["m"]
                b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": last_mid})
                if is_buyer_maker:
                    b["sell"] += qty
                else:
                    b["buy"] += qty

            elif "bookTicker" in stream:
                bid = float(d["b"]); ask = float(d["a"])
                last_mid = 0.5 * (bid + ask)
                bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": last_mid})
                bins[ts]["mid"] = last_mid

    return bins


def analyze(bins):
    keys = sorted(k for k, v in bins.items() if v["mid"] is not None)
    if len(keys) < 30:
        return {"error": f"too few bins ({len(keys)}); rerun"}

    H_a = np.array([bins[k]["buy"]  for k in keys], dtype=float)
    H_b = np.array([bins[k]["sell"] for k in keys], dtype=float)
    M   = np.array([bins[k]["mid"]  for k in keys], dtype=float)

    eps = 1e-9
    dipole = (H_a - H_b) / (H_a + H_b + eps)
    ratio  = np.log((H_a + eps) / (H_b + eps))

    ret = np.diff(np.log(M))
    n = len(ret)
    dipole = dipole[:n]
    ratio  = ratio[:n]

    r_d, p_d = pearsonr(dipole, ret)
    r_r, p_r = pearsonr(ratio,  ret)

    rng = np.random.default_rng(0)
    r_shuf, _ = pearsonr(rng.permutation(dipole), ret)

    return {
        "n_bins": int(n),
        "mean_buy_vol_per_s":  float(H_a.mean()),
        "mean_sell_vol_per_s": float(H_b.mean()),
        "r_dipole":   float(r_d),  "r2_dipole":   float(r_d**2),  "p_dipole":   float(p_d),
        "r_logratio": float(r_r),  "r2_logratio": float(r_r**2),  "p_logratio": float(p_r),
        "r_shuffled": float(r_shuf), "r2_shuffled": float(r_shuf**2),
    }


def stop_gates(res):
    A = res["r2_dipole"]   > 0.03
    B = res["r2_shuffled"] < 0.01
    C = res["r_dipole"]    > 0
    return {
        "A_signal_above_noise": A,
        "B_shuffled_control_passes": B,
        "C_sign_consistent": C,
        "ALL_PASS": bool(A and B and C),
    }


if __name__ == "__main__":
    print(f"[canary] collecting {DURATION_S}s of {SYMBOL.upper()} from {WS_HOST}...")
    bins = asyncio.run(collect())
    print(f"[canary] collected {len(bins)} second-bins")

    res = analyze(bins)
    print("\n[results]")
    print(json.dumps(res, indent=2))

    if "error" not in res:
        gates = stop_gates(res)
        print("\n[stop gates]")
        for k, v in gates.items():
            print(f"  {k}: {v}")
        if gates["ALL_PASS"]:
            print("\n[next] proceed to 15-min chunk; route bins through OD SR engine.")
        else:
            print("\n[next] NULL on this operator pair via canary. Document and stop.")
