"""
kraken_book_collector.py — GENERIC Kraken L2 order-book collector (any product).

The KRAKEN sibling of coinbase_book_collector.py (S59; venue goes in the file title —
platforms stay separate). Built to gate the kr_mk0 thread: Kraken Pro US spot has a
VERIFIED 0.00% maker tier at $10M/30d (S58), which flips every surviving mid-band entry
config positive on paper — but venue law says nothing validated on Binance/Coinbase ports
to Kraken books. This collector accrues the Kraken book truth those cells (and the
research-reopened fine band) validate against: fill/queue depth at the touch is the thing
trade bins cannot tell us (Kraken live volume = 35-42% of Coinbase on our pairs).

Row schema is IDENTICAL to coinbase_book_collector.py (loaders reuse unchanged):

    {"ts": grid_ts,            # float epoch seconds, snapped to the grid
     "mid": mid, "spread": spread,
     "bids": [[px_off, size], ... K],   # px_off = bid_price - mid  (<= 0)
     "asks": [[px_off, size], ... K],   # px_off = ask_price - mid  (>= 0)
     "buy": buy_vol, "sell": sell_vol,  # TAKER volume since last grid tick
     "n_trades": n}

Kraken WS v2 (wss://ws.kraken.com/v2, public, no keys) specifics vs Coinbase:
  - channel "book" depth=K: one full `snapshot` per (re)subscribe, then `update` deltas
    (qty 0.0 removes a level). After each update the local side is TRUNCATED to the
    subscribed depth — Kraken maintains a top-K view, and levels pushed out of the top-K
    are not re-sent, so an untruncated map would go stale below the top.
  - channel "trade": `side` is the TAKER side (same as the S37 bins collector). Kraken
    replays a recent-trades `snapshot` on every (re)subscribe — those are IGNORED (only
    `update` counts) or reconnects would double-ingest flow, the known bins-collector bug.
  - symbols are v2 friendly names: BTC/USD, ETH/USD, SOL/USD, XRP/USD and **DOGE/USD**
    (verified live S37 — the legacy XDG is REST-only and returns nothing on v2).

Run:
  python kraken_book_collector.py --product SOL/USD \
      --out sol_kraken_book.jsonl.gz --duration 21000 --grid-ms 100 --depth 10
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


WS_URI = "wss://ws.kraken.com/v2"


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
        print(f"[kr-book] could not read existing file: {e}", flush=True)
    return n, last_ts


def _top_k(book: dict[float, float], side: str, k: int) -> list[tuple[float, float]]:
    """Top-k (price, size) for a side; bids = highest prices, asks = lowest."""
    if not book:
        return []
    if side == "bid":
        return heapq.nlargest(k, book.items())
    return heapq.nsmallest(k, book.items())


def _truncate(book: dict[float, float], side: str, k: int) -> None:
    """Drop levels beyond the top-k (Kraken only maintains the subscribed depth)."""
    if len(book) <= k:
        return
    keep = {p for p, _ in _top_k(book, side, k)}
    for p in [p for p in book if p not in keep]:
        del book[p]


async def collect(duration_s: float, out_path: str, grid_ms: int, depth: int,
                  product: str) -> None:
    grid_s = grid_ms / 1000.0
    tag = f"kr-book-{product}"
    sub_book = {"method": "subscribe",
                "params": {"channel": "book", "symbol": [product], "depth": depth}}
    sub_trade = {"method": "subscribe",
                 "params": {"channel": "trade", "symbol": [product]}}

    n_existing, last_ts = _resume_count(out_path)
    bids: dict[float, float] = {}
    asks: dict[float, float] = {}
    have_snapshot = False
    cur_buy = 0.0
    cur_sell = 0.0
    cur_ntr = 0
    next_grid: float | None = None

    t0 = time.time()
    reconnect_count = 0
    rows_written = 0
    last_log = t0

    print(f"[{tag}] starting {duration_s:.0f}s on {product} grid={grid_ms}ms depth={depth}"
          + (f" (resume: {n_existing} rows, last_ts={last_ts})" if n_existing else ""),
          flush=True)

    out = gzip.open(out_path, "at")   # append: prior rows intact across resumes/reconnects

    def emit(grid_ts: float) -> None:
        nonlocal cur_buy, cur_sell, cur_ntr, rows_written
        tb = _top_k(bids, "bid", depth)
        ta = _top_k(asks, "ask", depth)
        if not tb or not ta or not have_snapshot:
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
            "bids": [[round(p - mid, 6), s] for p, s in tb],
            "asks": [[round(p - mid, 6), s] for p, s in ta],
            "buy": cur_buy,
            "sell": cur_sell,
            "n_trades": cur_ntr,
        }
        out.write(json.dumps(row) + "\n")
        rows_written += 1
        cur_buy = cur_sell = 0.0
        cur_ntr = 0

    def apply_book(data: list, is_snapshot: bool) -> None:
        nonlocal have_snapshot, next_grid
        for d in data:
            if is_snapshot:
                bids.clear()
                asks.clear()
            for lvl in d.get("bids", []):
                px, qty = float(lvl["price"]), float(lvl["qty"])
                if qty == 0.0:
                    bids.pop(px, None)
                else:
                    bids[px] = qty
            for lvl in d.get("asks", []):
                px, qty = float(lvl["price"]), float(lvl["qty"])
                if qty == 0.0:
                    asks.pop(px, None)
                else:
                    asks[px] = qty
            _truncate(bids, "bid", depth)
            _truncate(asks, "ask", depth)
        if is_snapshot and not have_snapshot:
            have_snapshot = True
            next_grid = (int(time.time() / grid_s) + 1) * grid_s

    try:
        while time.time() - t0 < duration_s:
            try:
                async with websockets.connect(WS_URI, ping_interval=20, close_timeout=5,
                                              max_size=None) as ws:
                    await ws.send(json.dumps(sub_book))
                    await ws.send(json.dumps(sub_trade))
                    if reconnect_count > 0:
                        print(f"[{tag}] reconnected ({reconnect_count}); awaiting fresh snapshot",
                              flush=True)
                        bids.clear()
                        asks.clear()
                        have_snapshot = False

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

                        chan = msg.get("channel", "")
                        mtype = msg.get("type", "")
                        now = time.time()

                        if chan == "book" and mtype in ("snapshot", "update"):
                            apply_book(msg.get("data", []), mtype == "snapshot")

                        elif chan == "trade" and mtype == "update":
                            # `update` ONLY — Kraken replays a recent-trades snapshot on
                            # every (re)subscribe; counting those double-ingests flow.
                            for tr in msg.get("data", []):
                                qty = float(tr.get("qty", 0.0))
                                if tr.get("side") == "buy":     # taker side
                                    cur_buy += qty
                                elif tr.get("side") == "sell":
                                    cur_sell += qty
                                cur_ntr += 1

                        # channels "status"/"heartbeat"/method acks: fall through

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
        print(f"[{tag}] done: {rows_written} rows written "
              f"({reconnect_count} reconnects)", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True, help="Kraken v2 pair, e.g. SOL/USD (DOGE/USD not XDG)")
    ap.add_argument("--out", required=True, help="output gzipped JSONL path")
    ap.add_argument("--duration", type=float, default=21000.0)
    ap.add_argument("--grid-ms", type=int, default=100)
    ap.add_argument("--depth", type=int, default=10)
    a = ap.parse_args()
    asyncio.run(collect(a.duration, a.out, a.grid_ms, a.depth, a.product))


if __name__ == "__main__":
    main()
