"""
bybit_book_collector.py — GENERIC Bybit USDT linear-perp L2 book collector (any symbol).

The Job-3 (S51) venue-book collector: the rebate math only prints if the REBATE VENUE's book has
spread + turn-flow (a rebate on a tight/deep book won't print — the S43 btc lesson), so this
collects Bybit's SOL/ETH perp books for the decisive per-cell re-measurement. Venue analogue of
coinbase_book_collector.py — SAME row schema, so load_book / build_channels / the maker pipeline
consume venue books unchanged:

    {"ts": grid_ts,            # float epoch seconds, snapped to the grid
     "mid": mid, "spread": spread,
     "bids": [[px_off, size], ... K],   # px_off = bid_price - mid  (<= 0)
     "asks": [[px_off, size], ... K],   # px_off = ask_price - mid  (>= 0)
     "buy": buy_vol, "sell": sell_vol,  # taker volume since last grid tick
     "n_trades": n}

Bybit V5 public linear WS (no auth), endpoints/semantics reused from the battle-tested
bybit_perp_collector.py plus the orderbook topic:
  - orderbook.50.<SYMBOL> : snapshot + delta maintenance of the top-50 book (20ms cadence);
                            delta size 0 = remove level; fresh snapshot on (re)subscribe.
  - publicTrade.<SYMBOL>  : taker trades — 'S' is the TAKER side ("Buy"|"Sell"), 'v' qty, 'p' price.
App-level heartbeat {"op":"ping"} every ~20s per Bybit docs (sent inline; the 20ms book cadence
keeps recv hot). Append-only gzip JSONL; reconnect rebuilds the book from the fresh snapshot.

Run:
  python bybit_book_collector.py --symbol SOLUSDT \
      --out sol_bybit_book.jsonl.gz --duration 21000 --grid-ms 100 --depth 10
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import heapq
import json
import os
import time

import websockets


WS_URI = "wss://stream.bybit.com/v5/public/linear"


def _resume_count(path: str) -> tuple[int, float | None]:
    """Return (n_rows, last_ts) for an existing gzipped JSONL file, or (0, None)."""
    if not os.path.exists(path):
        return 0, None
    n = 0
    last_ts: float | None = None
    try:
        with gzip.open(path, "rt") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                n += 1
                try:
                    last_ts = json.loads(line).get("ts", last_ts)
                except json.JSONDecodeError:
                    pass
    except Exception as e:  # noqa: BLE001
        print(f"[by-book] could not read existing file: {e}", flush=True)
    return n, last_ts


def _top_k(book: dict[float, float], side: str, k: int) -> list[tuple[float, float]]:
    """Top-k (price, size) for a side; bids = highest prices, asks = lowest."""
    if not book:
        return []
    if side == "bid":
        return heapq.nlargest(k, book.items())
    return heapq.nsmallest(k, book.items())


async def collect(duration_s: float, out_path: str, grid_ms: int, depth: int,
                  symbol: str) -> None:
    grid_s = grid_ms / 1000.0
    tag = f"by-book-{symbol}"
    sub = {"op": "subscribe", "args": [f"orderbook.50.{symbol}", f"publicTrade.{symbol}"]}

    n_existing, last_ts = _resume_count(out_path)
    bids: dict[float, float] = {}
    asks: dict[float, float] = {}
    cur_buy = 0.0
    cur_sell = 0.0
    cur_ntr = 0
    next_grid: float | None = None

    t0 = time.time()
    reconnect_count = 0
    rows_written = 0
    last_log = t0
    last_ping = t0

    print(f"[{tag}] starting {duration_s:.0f}s on {symbol} grid={grid_ms}ms depth={depth}"
          + (f" (resume: {n_existing} rows, last_ts={last_ts})" if n_existing else ""),
          flush=True)

    out = gzip.open(out_path, "at")

    def emit(grid_ts: float) -> None:
        nonlocal cur_buy, cur_sell, cur_ntr, rows_written
        tb = _top_k(bids, "bid", depth)
        ta = _top_k(asks, "ask", depth)
        if not tb or not ta:
            cur_buy = cur_sell = 0.0
            cur_ntr = 0
            return
        best_bid = tb[0][0]
        best_ask = ta[0][0]
        mid = 0.5 * (best_bid + best_ask)
        spread = best_ask - best_bid
        row = {
            "ts": round(grid_ts, 3),
            "mid": mid,
            "spread": spread,
            "bids": [[round(p - mid, 4), s] for p, s in tb],
            "asks": [[round(p - mid, 4), s] for p, s in ta],
            "buy": cur_buy,
            "sell": cur_sell,
            "n_trades": cur_ntr,
        }
        out.write(json.dumps(row) + "\n")
        rows_written += 1
        cur_buy = cur_sell = 0.0
        cur_ntr = 0

    def apply_levels(side_book: dict[float, float], levels) -> None:
        for p, s in levels:
            price = float(p)
            sz = float(s)
            if sz == 0.0:
                side_book.pop(price, None)
            else:
                side_book[price] = sz

    try:
        while time.time() - t0 < duration_s:
            try:
                async with websockets.connect(WS_URI, ping_interval=20, close_timeout=5,
                                              max_size=None) as ws:
                    await ws.send(json.dumps(sub))
                    if reconnect_count > 0:
                        print(f"[{tag}] reconnected ({reconnect_count}); awaiting fresh snapshot",
                              flush=True)
                        bids.clear()
                        asks.clear()

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

                        now = time.time()
                        # app-level heartbeat every ~20s (Bybit-documented keepalive)
                        if now - last_ping >= 20.0:
                            try:
                                await ws.send(json.dumps({"op": "ping"}))
                            except Exception:  # noqa: BLE001
                                pass
                            last_ping = now

                        topic = msg.get("topic", "")

                        if topic.startswith("orderbook."):
                            data = msg.get("data", {})
                            if msg.get("type") == "snapshot":
                                bids.clear()
                                asks.clear()
                                apply_levels(bids, data.get("b", []))
                                apply_levels(asks, data.get("a", []))
                                if next_grid is None:
                                    next_grid = (int(now / grid_s) + 1) * grid_s
                            else:  # delta
                                apply_levels(bids, data.get("b", []))
                                apply_levels(asks, data.get("a", []))

                        elif topic.startswith("publicTrade."):
                            for tr in msg.get("data", []):
                                qty = float(tr.get("v", 0.0))
                                taker_side = tr.get("S", "")
                                # Bybit 'S' is the TAKER side (proven in bybit_perp_collector.py)
                                if taker_side == "Buy":
                                    cur_buy += qty
                                elif taker_side == "Sell":
                                    cur_sell += qty
                                cur_ntr += 1

                        if next_grid is not None:
                            while now >= next_grid:
                                emit(next_grid)
                                next_grid += grid_s

                        if now - last_log >= 30.0:
                            out.flush()
                            print(f"[{tag}] t={now-t0:.0f}s rows={rows_written} "
                                  f"book=({len(bids)}b/{len(asks)}a)", flush=True)
                            last_log = now

            except (websockets.exceptions.ConnectionClosed,
                    websockets.exceptions.WebSocketException,
                    ConnectionResetError, OSError) as e:
                reconnect_count += 1
                print(f"[{tag}] WS issue ({type(e).__name__}: {e}); retry 5s "
                      f"(count={reconnect_count})", flush=True)
                out.flush()
                try:
                    await asyncio.sleep(5)
                except asyncio.CancelledError:
                    break
    finally:
        out.flush()
        out.close()

    print(f"[{tag}] done. rows_written={rows_written} reconnects={reconnect_count}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generic Bybit linear-perp L2 book collector (S51 Job 3)")
    ap.add_argument("--symbol", type=str, required=True,
                    help="Bybit linear symbol, e.g. SOLUSDT, ETHUSDT")
    ap.add_argument("--duration", type=float, default=21000.0,
                    help="collection seconds (default 21000 = 5h50m)")
    ap.add_argument("--out", type=str, required=True,
                    help="gzipped JSONL output path, e.g. sol_bybit_book.jsonl.gz")
    ap.add_argument("--grid-ms", type=int, default=100,
                    help="snapshot grid in ms (default 100)")
    ap.add_argument("--depth", type=int, default=10,
                    help="top-K levels per side (default 10)")
    args = ap.parse_args()
    asyncio.run(collect(args.duration, args.out, args.grid_ms, args.depth, args.symbol))


if __name__ == "__main__":
    main()
