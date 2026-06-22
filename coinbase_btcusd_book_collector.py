"""
coinbase_btcusd_book_collector.py

L2 order-book collector for the OD-BOOK experiment (S36b, markets timing line).

Unlike the trade-bin collectors (which keep only {buy, sell, mid, high, low,
n_trades} aggregates), this captures the *resting-size book state* that the
OD-BOOK spec's x(t) needs: top-K depth per side on a regular time grid, plus
spread and signed trade flow. It does NOT replace the trade collectors; it runs
alongside them and writes a separate file.

Channels (Coinbase Exchange WS, all PUBLIC — no API keys):
  - level2_batch : full book snapshot + batched l2update deltas (the
                   unauthenticated variant; `level2` requires auth).
  - matches      : taker trades, for signed trade-flow per grid tick.

We maintain a live local book (price -> size per side), apply l2update deltas,
and every GRID_MS milliseconds emit one snapshot row:

    {"ts": grid_ts,            # float epoch seconds, snapped to the grid
     "mid": mid, "spread": spread,
     "bids": [[px_off, size], ... K],   # px_off = bid_price - mid  (<= 0)
     "asks": [[px_off, size], ... K],   # px_off = ask_price - mid  (>= 0)
     "buy": buy_vol, "sell": sell_vol,  # taker volume since last grid tick
     "n_trades": n}

Rows are appended to a gzipped JSONL file (one JSON object per line), the
established gzip-on-disk pattern (S23). Append-only => resume just continues;
reconnect rebuilds the book from the fresh `snapshot` Coinbase sends on
(re)subscribe, so there is no snapshot-replay double-count problem (the book is
stateful, not accumulated, unlike Kraken trade bins).

Run:
  python coinbase_btcusd_book_collector.py --duration 21000 \
      --out btc_coinbase_book.jsonl.gz --grid-ms 100 --depth 10
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


WS_URI = "wss://ws-feed.exchange.coinbase.com"
PRODUCT = "BTC-USD"


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
        print(f"[cb-book] could not read existing file: {e}", flush=True)
    return n, last_ts


def _top_k(book: dict[float, float], side: str, k: int) -> list[tuple[float, float]]:
    """Top-k (price, size) for a side; bids = highest prices, asks = lowest."""
    if not book:
        return []
    if side == "bid":
        return heapq.nlargest(k, book.items())
    return heapq.nsmallest(k, book.items())


async def collect(duration_s: float, out_path: str, grid_ms: int, depth: int) -> None:
    grid_s = grid_ms / 1000.0
    sub = {
        "type": "subscribe",
        "product_ids": [PRODUCT],
        "channels": ["level2_batch", "matches"],
    }

    n_existing, last_ts = _resume_count(out_path)
    bids: dict[float, float] = {}
    asks: dict[float, float] = {}
    # signed taker flow accumulating within the current grid cell
    cur_buy = 0.0
    cur_sell = 0.0
    cur_ntr = 0
    next_grid: float | None = None

    t0 = time.time()
    reconnect_count = 0
    rows_written = 0
    last_log = t0

    print(f"[cb-book] starting {duration_s:.0f}s on {PRODUCT} grid={grid_ms}ms depth={depth}"
          + (f" (resume: {n_existing} rows, last_ts={last_ts})" if n_existing else ""),
          flush=True)

    # Append mode: gzip 'at' keeps prior rows intact across resumes/reconnects.
    out = gzip.open(out_path, "at")

    def emit(grid_ts: float) -> None:
        nonlocal cur_buy, cur_sell, cur_ntr, rows_written
        tb = _top_k(bids, "bid", depth)
        ta = _top_k(asks, "ask", depth)
        if not tb or not ta:
            # book not yet populated; reset flow and skip (don't fabricate a side)
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

    try:
        while time.time() - t0 < duration_s:
            try:
                # max_size=None: the initial level2 snapshot for a liquid book
                # (~1MB+) exceeds the 1MiB websockets default and would 1009-drop.
                async with websockets.connect(WS_URI, ping_interval=20, close_timeout=5,
                                              max_size=None) as ws:
                    await ws.send(json.dumps(sub))
                    if reconnect_count > 0:
                        print(f"[cb-book] reconnected ({reconnect_count}); awaiting fresh snapshot",
                              flush=True)
                        bids.clear()
                        asks.clear()

                    while time.time() - t0 < duration_s:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
                        except asyncio.TimeoutError:
                            print(f"[cb-book] recv timeout t={time.time()-t0:.0f}s", flush=True)
                            continue

                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        mtype = msg.get("type", "")
                        now = time.time()

                        if mtype == "snapshot":
                            bids.clear()
                            asks.clear()
                            for p, s in msg.get("bids", []):
                                sz = float(s)
                                if sz > 0:
                                    bids[float(p)] = sz
                            for p, s in msg.get("asks", []):
                                sz = float(s)
                                if sz > 0:
                                    asks[float(p)] = sz
                            next_grid = (int(now / grid_s) + 1) * grid_s

                        elif mtype == "l2update":
                            for side, p, s in msg.get("changes", []):
                                price = float(p)
                                sz = float(s)
                                book = bids if side == "buy" else asks
                                if sz == 0.0:
                                    book.pop(price, None)
                                else:
                                    book[price] = sz

                        elif mtype in ("match", "last_match"):
                            qty = float(msg.get("size", 0.0))
                            maker_side = msg.get("side", "")
                            # Coinbase 'side' = the resting (maker) side; taker is the
                            # opposite. maker sell => taker buy, and vice versa.
                            if maker_side == "sell":
                                cur_buy += qty
                            elif maker_side == "buy":
                                cur_sell += qty
                            cur_ntr += 1

                        # Emit any grid cells that have elapsed (handles gaps).
                        if next_grid is not None:
                            while now >= next_grid:
                                emit(next_grid)
                                next_grid += grid_s

                        if now - last_log >= 30.0:
                            out.flush()
                            print(f"[cb-book] t={now-t0:.0f}s rows={rows_written} "
                                  f"book=({len(bids)}b/{len(asks)}a)", flush=True)
                            last_log = now

            except (websockets.exceptions.ConnectionClosed,
                    websockets.exceptions.WebSocketException,
                    ConnectionResetError, OSError) as e:
                reconnect_count += 1
                print(f"[cb-book] WS issue ({type(e).__name__}: {e}); retry 5s "
                      f"(count={reconnect_count})", flush=True)
                out.flush()
                try:
                    await asyncio.sleep(5)
                except asyncio.CancelledError:
                    break
    finally:
        out.flush()
        out.close()

    print(f"[cb-book] done. rows_written={rows_written} reconnects={reconnect_count}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Coinbase BTC-USD L2 book collector (OD-BOOK)")
    ap.add_argument("--duration", type=float, default=21000.0,
                    help="collection seconds (default 21000 = 5h50m)")
    ap.add_argument("--out", type=str, default="btc_coinbase_book.jsonl.gz",
                    help="gzipped JSONL output path")
    ap.add_argument("--grid-ms", type=int, default=100,
                    help="snapshot grid in ms (default 100)")
    ap.add_argument("--depth", type=int, default=10,
                    help="top-K levels per side (default 10)")
    args = ap.parse_args()
    asyncio.run(collect(args.duration, args.out, args.grid_ms, args.depth))


if __name__ == "__main__":
    main()
