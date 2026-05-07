"""
kraken_btcusd_perp_collector.py

BTC-USD *perpetual futures* (Kraken Futures, USD-margined inverse) WS
collector. Same bin schema as the spot collectors so markets_adapter
ingests it identically.

Data source: Kraken Futures public WS, no auth, no API key.
  futures.kraken.com/ws/v1
    - trade  feed: PI_XBTUSD  -> taker side + qty + price (n_trades)
    - ticker feed: PI_XBTUSD  -> bid/ask for mid

Symbol note: PI_XBTUSD is the inverse-USD perpetual (the longstanding
flagship). Kraken also runs PF_XBTUSD (linear, quote-margined). PI_ is
historically the more liquid contract; switch to PF_ if Kraken's
liquidity migrates.

Run: python kraken_btcusd_perp_collector.py --duration 14400 \\
        --bins-path btc_kraken_perp_bins.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time

import websockets


KRAKEN_FUTURES_WS = "wss://futures.kraken.com/ws/v1"
PRODUCT = "PI_XBTUSD"
SECOND_BIN_S = 1.0


def _load_existing_bins(path: str) -> dict[float, dict]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            raw = json.load(f)
        return {float(k): v for k, v in raw.items()}
    except Exception as e:
        print(f"[kr-btc-perp] could not load existing bins: {e}", flush=True)
        return {}


def _save_bins(bins: dict, path: str) -> None:
    serializable = {str(k): v for k, v in bins.items()}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(serializable, f)
    os.replace(tmp, path)


async def collect(duration_s: float, save_path: str) -> dict[float, dict]:
    sub_trade = {"event": "subscribe", "feed": "trade", "product_ids": [PRODUCT]}
    sub_ticker = {"event": "subscribe", "feed": "ticker", "product_ids": [PRODUCT]}

    bins = _load_existing_bins(save_path)
    last_mid: float | None = None
    t0 = time.time()
    last_save = t0
    reconnect_count = 0

    print(f"[kr-btc-perp] starting {duration_s:.0f}s on {PRODUCT}"
          + (f" (resume {len(bins)} bins)" if bins else ""), flush=True)

    while time.time() - t0 < duration_s:
        try:
            async with websockets.connect(KRAKEN_FUTURES_WS, ping_interval=20, close_timeout=5) as ws:
                await ws.send(json.dumps(sub_trade))
                await ws.send(json.dumps(sub_ticker))
                if reconnect_count > 0:
                    print(f"[kr-btc-perp] reconnected ({reconnect_count})", flush=True)

                while time.time() - t0 < duration_s:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    except asyncio.TimeoutError:
                        print(f"[kr-btc-perp] recv timeout t={time.time()-t0:.0f}s", flush=True)
                        continue

                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    feed = msg.get("feed", "")
                    ts = int(time.time() / SECOND_BIN_S) * SECOND_BIN_S

                    # Trade events: feed=='trade' is per-fill; feed=='trade_snapshot'
                    # carries history at connect, also useful as warm-up data.
                    if feed in ("trade", "trade_snapshot"):
                        # 'trade' messages are per-fill objects; 'trade_snapshot'
                        # has a 'trades' list. Handle both.
                        records = []
                        if feed == "trade":
                            records.append(msg)
                        else:
                            records.extend(msg.get("trades", []))
                        for tr in records:
                            try:
                                qty = float(tr.get("qty", 0.0))
                                price = float(tr.get("price", last_mid or 0.0))
                            except (TypeError, ValueError):
                                continue
                            side = str(tr.get("side", "")).lower()  # taker side
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

                    elif feed in ("ticker", "ticker_lite"):
                        bid = msg.get("bid")
                        ask = msg.get("ask")
                        if bid is None or ask is None:
                            continue
                        try:
                            last_mid = 0.5 * (float(bid) + float(ask))
                        except (TypeError, ValueError):
                            continue
                        b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": last_mid,
                                                  "high": 0.0, "low": 0.0, "n_trades": 0})
                        b["mid"] = last_mid

                    elif feed in ("heartbeat", "subscribed"):
                        continue

                    now = time.time()
                    if now - last_save >= 30.0:
                        _save_bins(bins, save_path)
                        last_save = now
                        n_trades = sum(b.get("n_trades", 0) for b in bins.values())
                        print(f"[kr-btc-perp] t={now-t0:.0f}s bins={len(bins)} trades={n_trades}",
                              flush=True)

        except (websockets.exceptions.ConnectionClosed,
                websockets.exceptions.WebSocketException,
                ConnectionResetError, OSError) as e:
            reconnect_count += 1
            print(f"[kr-btc-perp] WS issue ({type(e).__name__}: {e}); retry 5s (count={reconnect_count})",
                  flush=True)
            _save_bins(bins, save_path)
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break

    _save_bins(bins, save_path)
    print(f"[kr-btc-perp] done. bins={len(bins)} reconnects={reconnect_count}", flush=True)
    return bins


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--duration", type=float, default=14400.0)
    p.add_argument("--bins-path", type=str, default="btc_kraken_perp_bins.json")
    args = p.parse_args()
    asyncio.run(collect(args.duration, args.bins_path))


if __name__ == "__main__":
    main()
