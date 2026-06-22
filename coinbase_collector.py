"""
coinbase_collector.py — GENERIC Coinbase spot WS collector (any product).

Symbol-parameterized version of coinbase_{btcusd,eth}_collector.py so one script
serves every coin. Same 1-sec bin schema as the BTC/ETH collectors
({buy, sell, mid, high, low, n_trades}) so markets_adapter / load_series ingest it
identically. Public WS, no API key. Reconnect + resume-from-disk.

Run: python coinbase_collector.py --product SOL-USD --duration 21000 \\
        --bins-path sol_coinbase_bins.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time

import websockets


WS_URI = "wss://ws-feed.exchange.coinbase.com"
SECOND_BIN_S = 1.0


def _load_existing_bins(path: str) -> dict[float, dict]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            raw = json.load(f)
        return {float(k): v for k, v in raw.items()}
    except Exception as e:  # noqa: BLE001
        print(f"[cb] could not load existing bins: {e}", flush=True)
        return {}


def _save_bins(bins: dict, path: str) -> None:
    serializable = {str(k): v for k, v in bins.items()}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(serializable, f)
    os.replace(tmp, path)


async def collect(duration_s: float, save_path: str, product: str) -> dict[float, dict]:
    tag = f"cb-{product}"
    sub = {"type": "subscribe", "product_ids": [product], "channels": ["matches", "ticker"]}
    bins = _load_existing_bins(save_path)
    last_mid: float | None = None
    t0 = time.time()
    last_save = t0
    reconnect_count = 0

    print(f"[{tag}] starting {duration_s:.0f}s on {product}"
          + (f" (resume {len(bins)} bins)" if bins else ""), flush=True)

    while time.time() - t0 < duration_s:
        try:
            async with websockets.connect(WS_URI, ping_interval=20, close_timeout=5) as ws:
                await ws.send(json.dumps(sub))
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

                    mtype = msg.get("type", "")
                    ts = int(time.time() / SECOND_BIN_S) * SECOND_BIN_S

                    if mtype in ("match", "last_match"):
                        qty = float(msg["size"])
                        maker_side = msg["side"]
                        b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": last_mid,
                                                  "high": 0.0, "low": 0.0, "n_trades": 0})
                        # Coinbase 'side' = resting (maker) side; taker is opposite.
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
                        print(f"[{tag}] t={now-t0:.0f}s bins={len(bins)}", flush=True)

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
    p = argparse.ArgumentParser(description="Generic Coinbase spot collector")
    p.add_argument("--product", type=str, required=True, help="e.g. SOL-USD, DOGE-USD, XRP-USD")
    p.add_argument("--duration", type=float, default=21000.0)
    p.add_argument("--bins-path", type=str, required=True)
    args = p.parse_args()
    asyncio.run(collect(args.duration, args.bins_path, args.product))


if __name__ == "__main__":
    main()
