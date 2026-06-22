"""
kraken_collector.py — GENERIC Kraken spot WS collector (any product).

Symbol-parameterized version of kraken_{btcusd,eth}_collector.py. Same 1-sec bin
schema as the BTC/ETH collectors. Kraken v2 'side' is the TAKER side. Live trade
"update" only (Kraken replays a recent-trades "snapshot" on every (re)subscribe;
counting those double-ingests on reconnect). Public WS, no API key.

NOTE on symbols: Kraken's v2 WS uses friendly pair names (BTC/USD, not the legacy
XBT/XDG). Dogecoin is **DOGE/USD** here (verified live; the legacy "XDG" is
REST-only and returns nothing on v2). SOL/USD and XRP/USD are normal.

Run: python kraken_collector.py --product SOL/USD --duration 21000 \\
        --bins-path sol_kraken_bins.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time

import websockets


KRAKEN_WS_URI = "wss://ws.kraken.com/v2"
SECOND_BIN_S = 1.0


def _load_existing_bins(path: str) -> dict[float, dict]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            raw = json.load(f)
        return {float(k): v for k, v in raw.items()}
    except Exception as e:  # noqa: BLE001
        print(f"[kr] could not load existing bins: {e}", flush=True)
        return {}


def _save_bins(bins: dict, path: str) -> None:
    serializable = {str(k): v for k, v in bins.items()}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(serializable, f)
    os.replace(tmp, path)


async def collect(duration_s: float, save_path: str, product: str) -> dict[float, dict]:
    tag = f"kr-{product}"
    sub_trade = {"method": "subscribe", "params": {"channel": "trade", "symbol": [product]}}
    sub_ticker = {"method": "subscribe", "params": {"channel": "ticker", "symbol": [product]}}

    bins = _load_existing_bins(save_path)
    last_mid: float | None = None
    t0 = time.time()
    last_save = t0
    reconnect_count = 0

    print(f"[{tag}] starting {duration_s:.0f}s on {product}"
          + (f" (resume {len(bins)} bins)" if bins else ""), flush=True)

    while time.time() - t0 < duration_s:
        try:
            async with websockets.connect(KRAKEN_WS_URI, ping_interval=20, close_timeout=5) as ws:
                await ws.send(json.dumps(sub_trade))
                await ws.send(json.dumps(sub_ticker))
                if reconnect_count > 0:
                    print(f"[{tag}] reconnected ({reconnect_count})", flush=True)

                while time.time() - t0 < duration_s:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    except asyncio.TimeoutError:
                        print(f"[{tag}] recv timeout t={time.time()-t0:.0f}s", flush=True)
                        continue
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    channel = msg.get("channel", "")
                    mtype = msg.get("type", "")

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
                        print(f"[{tag}] t={now-t0:.0f}s bins={len(bins)} trades={n_trades}", flush=True)

        except (websockets.exceptions.ConnectionClosed,
                websockets.exceptions.WebSocketException,
                ConnectionResetError, OSError) as e:
            reconnect_count += 1
            print(f"[{tag}] WS issue ({type(e).__name__}: {e}); retry 5s (count={reconnect_count})",
                  flush=True)
            _save_bins(bins, save_path)
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break

    _save_bins(bins, save_path)
    print(f"[{tag}] done. bins={len(bins)} reconnects={reconnect_count}", flush=True)
    return bins


def main():
    p = argparse.ArgumentParser(description="Generic Kraken spot collector")
    p.add_argument("--product", type=str, required=True, help="e.g. SOL/USD, DOGE/USD, XRP/USD")
    p.add_argument("--duration", type=float, default=21000.0)
    p.add_argument("--bins-path", type=str, required=True)
    args = p.parse_args()
    asyncio.run(collect(args.duration, args.bins_path, args.product))


if __name__ == "__main__":
    main()
