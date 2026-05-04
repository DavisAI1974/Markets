"""
Coinbase BTC-USD 2-min orderbook dipole canary.
OD falsification-first protocol — independent-venue replication of the H_a/H_b
dipole test (Binance variant lives in binance_btcusdt_canary.py).

Data source: Coinbase Exchange public WS (no auth, no API key).
  - matches channel -> taker buy/sell volume (via maker-side inversion)
  - ticker  channel -> best bid/ask -> mid

Dependencies: websockets, numpy, scipy

Operators tested:
  H_a = taker buy volume per second  (bid-side aggression)
  H_b = taker sell volume per second (ask-side aggression)
  dipole = (H_a - H_b) / (H_a + H_b)   normalized order-flow imbalance
  ratio  = log(H_a / H_b)               raw form matching the 4-science discovery

Predictand: mid-price log return over the same 1-s bin.

Stop gates (canary, n~120 bins):
  A. R^2(dipole, ret)  > 0.03  -> signal exists above n=120 noise floor
  B. R^2(shuffled, ret) < 0.01 -> permutation control kills it
  C. sign(corr) > 0            -> dipole moves with price (sanity)

Maker-side -> taker-side mapping (Coinbase 'matches.side' is maker's side):
  side="sell" -> maker ask lifted -> taker bought -> H_a
  side="buy"  -> maker bid hit    -> taker sold   -> H_b
"""

import asyncio
import json
import time
import numpy as np
from scipy import stats
import websockets


PRODUCT = "BTC-USD"
DURATION_S = 120
BIN_S = 1.0
WS_URI = "wss://ws-feed.exchange.coinbase.com"


async def collect():
    """Stream Coinbase matches + ticker for DURATION_S seconds, bin to 1s.

    Both streams binned by local receive time so trade and mid bins share a
    single clock (the Coinbase 'time' field is exchange-side and would skew
    if mixed with local-clock bins from late ticker arrivals).
    """
    sub = {
        "type": "subscribe",
        "product_ids": [PRODUCT],
        "channels": ["matches", "ticker"],
    }
    bins = {}        # ts -> {"buy": float, "sell": float, "mid": float|None}
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
                # 'side' is the maker's side; taker is the opposite
                maker_side = msg["side"]
                b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": last_mid})
                if maker_side == "sell":
                    b["buy"] += qty       # taker bought
                elif maker_side == "buy":
                    b["sell"] += qty      # taker sold

            elif mtype == "ticker":
                bid_s = msg.get("best_bid"); ask_s = msg.get("best_ask")
                if bid_s is None or ask_s is None:
                    continue
                last_mid = 0.5 * (float(bid_s) + float(ask_s))
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

    r_d, p_d = stats.pearsonr(dipole, ret)
    r_r, p_r = stats.pearsonr(ratio,  ret)

    rng = np.random.default_rng(0)
    r_shuf = stats.pearsonr(rng.permutation(dipole), ret)[0]

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
    print(f"[canary] collecting {DURATION_S}s of {PRODUCT} from Coinbase public WS...")
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
