"""
binance_ethusdt_perp_collector.py

ETH-USDT *perpetual futures* (USDT-margined) WS collector. Same bin schema
as coinbase_eth_collector.py / kraken_eth_collector.py so markets_adapter
ingests it identically — that lets the existing classifier and evaluator
treat spot vs perp as just another (asset, venue) pair.

Data source: Binance USDT-M futures public WS, no auth, no API key.
  fstream.binance.com:9443/stream
    - ethusdt@aggTrade   -> taker buy/sell volume, n_trades via (l-f+1)
    - ethusdt@bookTicker -> top-of-book mid

Run: python binance_ethusdt_perp_collector.py --duration 14400 \\
        --bins-path eth_binance_perp_bins.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time

import websockets


WS_URI = (
    "wss://fstream.binance.com:9443/stream"
    "?streams=ethusdt@aggTrade/ethusdt@bookTicker"
)
SECOND_BIN_S = 1.0


def _load_existing_bins(path: str) -> dict[float, dict]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            raw = json.load(f)
        return {float(k): v for k, v in raw.items()}
    except Exception as e:
        print(f"[bn-eth-perp] could not load existing bins: {e}", flush=True)
        return {}


def _save_bins(bins: dict, path: str) -> None:
    serializable = {str(k): v for k, v in bins.items()}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(serializable, f)
    os.replace(tmp, path)


async def collect(duration_s: float, save_path: str) -> dict[float, dict]:
    bins = _load_existing_bins(save_path)
    last_mid: float | None = None
    t0 = time.time()
    last_save = t0
    reconnect_count = 0

    print(f"[bn-eth-perp] starting {duration_s:.0f}s on ETHUSDT-PERP"
          + (f" (resume {len(bins)} bins)" if bins else ""), flush=True)

    while time.time() - t0 < duration_s:
        try:
            async with websockets.connect(WS_URI, ping_interval=20, close_timeout=5) as ws:
                if reconnect_count > 0:
                    print(f"[bn-eth-perp] reconnected ({reconnect_count})", flush=True)

                while time.time() - t0 < duration_s:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    except asyncio.TimeoutError:
                        print(f"[bn-eth-perp] recv timeout t={time.time()-t0:.0f}s", flush=True)
                        continue

                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    stream = msg.get("stream", "")
                    d = msg.get("data", {})
                    ts = int(time.time() / SECOND_BIN_S) * SECOND_BIN_S

                    if "aggTrade" in stream:
                        try:
                            qty = float(d["q"])
                            price = float(d["p"])
                        except (KeyError, ValueError, TypeError):
                            continue
                        # m=True -> buyer is maker -> taker sold (sell-side aggression)
                        is_buyer_maker = bool(d.get("m"))
                        # Each aggTrade represents (l - f + 1) raw trades that
                        # filled against the same resting order.
                        n_raw = int(d.get("l", 0)) - int(d.get("f", 0)) + 1
                        if n_raw < 1:
                            n_raw = 1

                        b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": last_mid,
                                                  "high": 0.0, "low": 0.0, "n_trades": 0})
                        if is_buyer_maker:
                            b["sell"] += qty
                        else:
                            b["buy"] += qty
                        if b["high"] == 0.0 or price > b["high"]:
                            b["high"] = price
                        if b["low"] == 0.0 or price < b["low"]:
                            b["low"] = price
                        b["n_trades"] += n_raw

                    elif "bookTicker" in stream:
                        try:
                            bid = float(d["b"])
                            ask = float(d["a"])
                        except (KeyError, ValueError, TypeError):
                            continue
                        last_mid = 0.5 * (bid + ask)
                        b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": last_mid,
                                                  "high": 0.0, "low": 0.0, "n_trades": 0})
                        b["mid"] = last_mid

                    now = time.time()
                    if now - last_save >= 30.0:
                        _save_bins(bins, save_path)
                        last_save = now
                        print(f"[bn-eth-perp] t={now-t0:.0f}s bins={len(bins)}", flush=True)

        except (websockets.exceptions.ConnectionClosed,
                websockets.exceptions.WebSocketException,
                ConnectionResetError, OSError) as e:
            reconnect_count += 1
            print(f"[bn-eth-perp] WS issue ({type(e).__name__}: {e}); retry 5s (count={reconnect_count})",
                  flush=True)
            _save_bins(bins, save_path)
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break

    _save_bins(bins, save_path)
    print(f"[bn-eth-perp] done. bins={len(bins)} reconnects={reconnect_count}", flush=True)
    return bins


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--duration", type=float, default=14400.0)
    p.add_argument("--bins-path", type=str, default="eth_binance_perp_bins.json")
    args = p.parse_args()
    asyncio.run(collect(args.duration, args.bins_path))


if __name__ == "__main__":
    main()
