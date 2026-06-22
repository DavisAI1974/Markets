"""
bybit_perp_collector.py — GENERIC Bybit USDT linear-perp WS collector (any symbol).

Symbol-parameterized version of bybit_{btcusdt,ethusdt}_perp_collector.py. Same
1-sec bin schema as the spot collectors. Bybit V5 public linear WS, no auth:
  - publicTrade.<SYMBOL> -> taker side ('S': "Buy"|"Sell"), qty 'v', price 'p'
  - tickers.<SYMBOL>     -> bid1Price/ask1Price for mid

Run: python bybit_perp_collector.py --symbol SOLUSDT --duration 21000 \\
        --bins-path sol_bybit_perp_bins.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time

import websockets


WS_URI = "wss://stream.bybit.com/v5/public/linear"
SECOND_BIN_S = 1.0


def _load_existing_bins(path: str) -> dict[float, dict]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            raw = json.load(f)
        return {float(k): v for k, v in raw.items()}
    except Exception as e:  # noqa: BLE001
        print(f"[by] could not load existing bins: {e}", flush=True)
        return {}


def _save_bins(bins: dict, path: str) -> None:
    serializable = {str(k): v for k, v in bins.items()}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(serializable, f)
    os.replace(tmp, path)


async def collect(duration_s: float, save_path: str, symbol: str) -> dict[float, dict]:
    tag = f"by-{symbol}"
    sub = {"op": "subscribe", "args": [f"publicTrade.{symbol}", f"tickers.{symbol}"]}
    bins = _load_existing_bins(save_path)
    last_mid: float | None = None
    t0 = time.time()
    last_save = t0
    reconnect_count = 0

    print(f"[{tag}] starting {duration_s:.0f}s on {symbol}"
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

                    topic = msg.get("topic", "")
                    ts = int(time.time() / SECOND_BIN_S) * SECOND_BIN_S

                    if topic.startswith("publicTrade."):
                        for tr in msg.get("data", []):
                            try:
                                qty = float(tr["v"])
                                price = float(tr["p"])
                            except (KeyError, ValueError, TypeError):
                                continue
                            side = str(tr.get("S", "")).lower()   # taker side
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

                    elif topic.startswith("tickers."):
                        d = msg.get("data", {}) or {}
                        bid_s = d.get("bid1Price")
                        ask_s = d.get("ask1Price")
                        if bid_s is None or ask_s is None:
                            continue
                        try:
                            last_mid = 0.5 * (float(bid_s) + float(ask_s))
                        except (TypeError, ValueError):
                            continue
                        b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": last_mid,
                                                  "high": 0.0, "low": 0.0, "n_trades": 0})
                        b["mid"] = last_mid

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
    p = argparse.ArgumentParser(description="Generic Bybit USDT linear-perp collector")
    p.add_argument("--symbol", type=str, required=True, help="e.g. SOLUSDT, DOGEUSDT, XRPUSDT")
    p.add_argument("--duration", type=float, default=21000.0)
    p.add_argument("--bins-path", type=str, required=True)
    args = p.parse_args()
    asyncio.run(collect(args.duration, args.bins_path, args.symbol))


if __name__ == "__main__":
    main()
