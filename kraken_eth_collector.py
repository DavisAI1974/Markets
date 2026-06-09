"""
kraken_eth_collector.py

Minimal Kraken ETH/USD WS collector. Mirror of kraken_btcusd_collector.py
but for ETH/USD. Note: Kraken v2 'side' is the TAKER side.

Run: python kraken_eth_collector.py --duration 14400 --bins-path eth_kraken_bins.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time

import websockets


KRAKEN_WS_URI = "wss://ws.kraken.com/v2"
PRODUCT = "ETH/USD"
SECOND_BIN_S = 1.0


def _load_existing_bins(path: str) -> dict[float, dict]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            raw = json.load(f)
        return {float(k): v for k, v in raw.items()}
    except Exception as e:
        print(f"[kr-eth] could not load existing bins: {e}", flush=True)
        return {}


def _save_bins(bins: dict, path: str) -> None:
    serializable = {str(k): v for k, v in bins.items()}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(serializable, f)
    os.replace(tmp, path)


async def collect(duration_s: float, save_path: str) -> dict[float, dict]:
    sub_trade = {"method": "subscribe", "params": {"channel": "trade", "symbol": [PRODUCT]}}
    sub_ticker = {"method": "subscribe", "params": {"channel": "ticker", "symbol": [PRODUCT]}}

    bins = _load_existing_bins(save_path)
    last_mid: float | None = None
    t0 = time.time()
    last_save = t0
    reconnect_count = 0

    print(f"[kr-eth] starting {duration_s:.0f}s on {PRODUCT}"
          + (f" (resume {len(bins)} bins)" if bins else ""), flush=True)

    while time.time() - t0 < duration_s:
        try:
            async with websockets.connect(KRAKEN_WS_URI, ping_interval=20, close_timeout=5) as ws:
                await ws.send(json.dumps(sub_trade))
                await ws.send(json.dumps(sub_ticker))
                if reconnect_count > 0:
                    print(f"[kr-eth] reconnected ({reconnect_count})", flush=True)

                while time.time() - t0 < duration_s:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    except asyncio.TimeoutError:
                        print(f"[kr-eth] recv timeout t={time.time()-t0:.0f}s", flush=True)
                        continue

                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    channel = msg.get("channel", "")
                    mtype = msg.get("type", "")

                    # Live trades only. Kraken v2 replays a "snapshot" of recent
                    # trades on every (re)subscribe; counting those re-ingests the
                    # same trades on each reconnect (inflated buy/sell volume,
                    # dumped into the reconnect second). Accumulate "update" only.
                    if channel == "trade" and mtype == "update":
                        for trade in msg.get("data", []):
                            ts = int(time.time() / SECOND_BIN_S) * SECOND_BIN_S
                            side = str(trade.get("side", ""))
                            qty = float(trade.get("qty", 0.0))
                            price = float(trade.get("price", last_mid or 0.0))
                            b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": last_mid,
                                                      "high": 0.0, "low": 0.0, "n_trades": 0})
                            if side == "buy":
                                b["buy"] += qty
                            elif side == "sell":
                                b["sell"] += qty
                            if b["high"] == 0.0 or price > b["high"]:
                                b["high"] = price
                            if b["low"] == 0.0 or price < b["low"]:
                                b["low"] = price
                            b["n_trades"] += 1

                    elif channel == "ticker":
                        for ticker in msg.get("data", []):
                            bid = ticker.get("bid")
                            ask = ticker.get("ask")
                            if bid is None or ask is None:
                                continue
                            last_mid = 0.5 * (float(bid) + float(ask))
                            ts = int(time.time() / SECOND_BIN_S) * SECOND_BIN_S
                            b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": last_mid,
                                                      "high": 0.0, "low": 0.0, "n_trades": 0})
                            b["mid"] = last_mid

                    elif channel == "heartbeat" or mtype == "pong":
                        continue

                    now = time.time()
                    if now - last_save >= 30.0:
                        _save_bins(bins, save_path)
                        last_save = now
                        n_trades = sum(b.get("n_trades", 0) for b in bins.values())
                        print(f"[kr-eth] t={now-t0:.0f}s bins={len(bins)} trades={n_trades}",
                              flush=True)

        except (websockets.exceptions.ConnectionClosed,
                websockets.exceptions.WebSocketException,
                ConnectionResetError, OSError) as e:
            reconnect_count += 1
            print(f"[kr-eth] WS issue ({type(e).__name__}: {e}); retry 5s (count={reconnect_count})",
                  flush=True)
            _save_bins(bins, save_path)
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break

    _save_bins(bins, save_path)
    print(f"[kr-eth] done. bins={len(bins)} reconnects={reconnect_count}", flush=True)
    return bins


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--duration", type=float, default=14400.0)
    p.add_argument("--bins-path", type=str, default="eth_kraken_bins.json")
    args = p.parse_args()
    asyncio.run(collect(args.duration, args.bins_path))


if __name__ == "__main__":
    main()
