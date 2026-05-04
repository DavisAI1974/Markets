"""
coinbase_eth_collector.py

Minimal Coinbase ETH-USD WS collector. Same bin schema as
coinbase_btcusd_4hr_trajectory.py and kraken_btcusd_collector.py so
markets_adapter ingests it identically. Reconnect + resume-from-disk
patched in.

Run: python coinbase_eth_collector.py --duration 14400 --bins-path eth_coinbase_bins.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time

import websockets


WS_URI = "wss://ws-feed.exchange.coinbase.com"
PRODUCT = "ETH-USD"
SECOND_BIN_S = 1.0


def _load_existing_bins(path: str) -> dict[float, dict]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            raw = json.load(f)
        return {float(k): v for k, v in raw.items()}
    except Exception as e:
        print(f"[cb-eth] could not load existing bins: {e}", flush=True)
        return {}


def _save_bins(bins: dict, path: str) -> None:
    serializable = {str(k): v for k, v in bins.items()}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(serializable, f)
    os.replace(tmp, path)


async def collect(duration_s: float, save_path: str) -> dict[float, dict]:
    sub = {
        "type": "subscribe",
        "product_ids": [PRODUCT],
        "channels": ["matches", "ticker"],
    }
    bins = _load_existing_bins(save_path)
    last_mid: float | None = None
    t0 = time.time()
    last_save = t0
    reconnect_count = 0

    print(f"[cb-eth] starting {duration_s:.0f}s on {PRODUCT}"
          + (f" (resume {len(bins)} bins)" if bins else ""), flush=True)

    while time.time() - t0 < duration_s:
        try:
            async with websockets.connect(WS_URI, ping_interval=20, close_timeout=5) as ws:
                await ws.send(json.dumps(sub))
                if reconnect_count > 0:
                    print(f"[cb-eth] reconnected ({reconnect_count})", flush=True)

                while time.time() - t0 < duration_s:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    except asyncio.TimeoutError:
                        print(f"[cb-eth] recv timeout t={time.time()-t0:.0f}s", flush=True)
                        continue

                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

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
                        print(f"[cb-eth] t={now-t0:.0f}s bins={len(bins)}", flush=True)

        except (websockets.exceptions.ConnectionClosed,
                websockets.exceptions.WebSocketException,
                ConnectionResetError, OSError) as e:
            reconnect_count += 1
            print(f"[cb-eth] WS issue ({type(e).__name__}: {e}); retry 5s (count={reconnect_count})",
                  flush=True)
            _save_bins(bins, save_path)
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break

    _save_bins(bins, save_path)
    print(f"[cb-eth] done. bins={len(bins)} reconnects={reconnect_count}", flush=True)
    return bins


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--duration", type=float, default=14400.0)
    p.add_argument("--bins-path", type=str, default="eth_coinbase_bins.json")
    args = p.parse_args()
    asyncio.run(collect(args.duration, args.bins_path))


if __name__ == "__main__":
    main()
