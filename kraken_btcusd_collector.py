"""
kraken_btcusd_collector.py

Standalone Kraken BTC/USD WS collector. Produces the same 1-sec bin schema
as coinbase_btcusd_4hr_trajectory.py so both venues feed into markets_adapter
identically downstream.

Important: Kraken v2 'side' is the TAKER side. Coinbase Exchange's 'side' is
the MAKER side. We add to buy_vol when side=='buy' and sell_vol when side=='sell'
on Kraken, no inversion.

Saves bins to disk every 30s. Mid-run crash loses at most 30s of data.

Usage:
    python kraken_btcusd_collector.py --duration 14400 --bins-path kraken_bins.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time

import websockets


KRAKEN_WS_URI = "wss://ws.kraken.com/v2"
PRODUCT = "BTC/USD"
SECOND_BIN_S = 1.0


async def collect(duration_s: float, save_path: str) -> dict[float, dict]:
    """Stream Kraken WS for duration_s, accumulating 1-sec bins."""
    sub_trade = {
        "method": "subscribe",
        "params": {"channel": "trade", "symbol": [PRODUCT]},
    }
    sub_ticker = {
        "method": "subscribe",
        "params": {"channel": "ticker", "symbol": [PRODUCT]},
    }

    bins: dict[float, dict] = {}
    last_mid: float | None = None
    t0 = time.time()
    last_save = t0

    print(f"[kraken] starting {duration_s:.0f}s collection on {PRODUCT}", flush=True)
    async with websockets.connect(KRAKEN_WS_URI, ping_interval=20) as ws:
        await ws.send(json.dumps(sub_trade))
        await ws.send(json.dumps(sub_ticker))

        while time.time() - t0 < duration_s:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
            except asyncio.TimeoutError:
                print(f"[kraken] WS recv timeout at t={time.time()-t0:.0f}s", flush=True)
                continue

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            channel = msg.get("channel", "")
            mtype = msg.get("type", "")

            if channel == "trade" and mtype in ("update", "snapshot"):
                for trade in msg.get("data", []):
                    ts = int(time.time() / SECOND_BIN_S) * SECOND_BIN_S
                    side = str(trade.get("side", ""))
                    qty = float(trade.get("qty", 0.0))
                    price = float(trade.get("price", last_mid or 0.0))
                    b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": last_mid,
                                              "high": 0.0, "low": 0.0, "n_trades": 0})
                    # Kraken v2: 'side' is the taker side
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
                print(f"[kraken] t={now-t0:.0f}s bins={len(bins)} trades_total={n_trades}",
                      flush=True)

    _save_bins(bins, save_path)
    print(f"[kraken] done. final bins={len(bins)}", flush=True)
    return bins


def _save_bins(bins: dict, path: str) -> None:
    serializable = {str(k): v for k, v in bins.items()}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(serializable, f)
    os.replace(tmp, path)


def main():
    p = argparse.ArgumentParser(description="Kraken BTC/USD WS collector")
    p.add_argument("--duration", type=float, default=14400.0,
                   help="Collection duration in seconds (default 14400 = 4 hours)")
    p.add_argument("--bins-path", type=str, default="kraken_bins.json",
                   help="Where to save 1-sec bins")
    args = p.parse_args()
    asyncio.run(collect(args.duration, args.bins_path))


if __name__ == "__main__":
    main()
