"""
backfill_kraken_spot.py

Backfills Kraken spot bins via the public Kraken /0/public/Trades REST
endpoint. Walks the trade history forward from --since, paginating via
the response's `last` cursor (nanosecond timestamp).

Kraken's public Trades endpoint returns up to 1000 trades per call and
is rate-limited to ~1 req/sec on the unauthenticated public endpoint.
30 days of XBTUSD or ETHUSD typically fits in 30-90 minutes of paginated
fetching.

Output schema matches kraken_*_collector.py exactly. Mid for backfill
is the last trade price within each 1-second bin.

Merge semantics: existing RT bins always win.

Usage:
    python backfill_kraken_spot.py --pair XBTUSD --days 30 \\
        --bins-path btc_kraken_bins.json
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


KRAKEN_TRADES_URL = "https://api.kraken.com/0/public/Trades"
SECOND_BIN_S = 1.0
INTER_REQUEST_SLEEP_S = 1.05  # respect ~1 req/s public rate limit
MAX_RETRIES = 5


def _load_existing_bins(path: str) -> dict[float, dict]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            raw = json.load(f)
        return {float(k): v for k, v in raw.items()}
    except Exception as e:
        print(f"[backfill-kr] could not load existing bins: {e}", flush=True)
        return {}


def _save_bins(bins: dict, path: str) -> None:
    serializable = {str(k): v for k, v in bins.items()}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(serializable, f)
    os.replace(tmp, path)


def _fetch(pair: str, since_ns: int) -> dict | None:
    qs = urllib.parse.urlencode({"pair": pair, "since": str(since_ns)})
    url = f"{KRAKEN_TRADES_URL}?{qs}"
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "markets-watch-backfill/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            print(f"[backfill-kr] fetch retry {attempt + 1}/{MAX_RETRIES}: {type(e).__name__}: {e}",
                  flush=True)
            time.sleep(2 ** attempt)
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pair", type=str, required=True, help="e.g. XBTUSD or ETHUSD")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--since", type=float, default=None,
                   help="override start time (unix seconds); default = now - days")
    p.add_argument("--max-seconds", type=int, default=18000,
                   help="wallclock budget for fetching (default 5h)")
    p.add_argument("--bins-path", type=str, required=True)
    args = p.parse_args()

    pair = args.pair.upper()

    existing = _load_existing_bins(args.bins_path)
    print(f"[backfill-kr] {pair}: loaded {len(existing)} existing bins", flush=True)

    if args.since is not None:
        since_s = float(args.since)
    else:
        since_s = time.time() - args.days * 86400
    since_ns = int(since_s * 1_000_000_000)
    print(f"[backfill-kr] starting at since={since_ns}  (~{args.days}d ago)", flush=True)

    backfill_bins: dict[float, dict] = {}
    n_calls = 0
    n_trades = 0
    t0 = time.time()
    last_progress_log = t0

    while True:
        if time.time() - t0 > args.max_seconds:
            print(f"[backfill-kr] wallclock budget exhausted ({args.max_seconds}s); stopping", flush=True)
            break

        data = _fetch(pair, since_ns)
        n_calls += 1
        if data is None:
            print(f"[backfill-kr] fetch returned None after retries; stopping", flush=True)
            break
        if data.get("error"):
            print(f"[backfill-kr] kraken error: {data['error']}; stopping", flush=True)
            break

        result = data.get("result", {})
        # Pair key in response uses Kraken's internal name (XXBTZUSD, XETHZUSD)
        pair_key = next((k for k in result.keys() if k != "last"), None)
        if pair_key is None:
            print(f"[backfill-kr] no trade key in response; stopping", flush=True)
            break

        trades = result.get(pair_key, [])
        if not trades:
            print(f"[backfill-kr] empty trade page; reached current edge", flush=True)
            break

        for tr in trades:
            # Schema: [price, volume, time(s), buy/sell, market/limit, misc, trade_id?]
            try:
                price = float(tr[0])
                qty = float(tr[1])
                t_s = float(tr[2])
                side = str(tr[3]).lower()  # 'b' = buy (taker), 's' = sell (taker)
            except (IndexError, ValueError, TypeError):
                continue
            ts = int(t_s / SECOND_BIN_S) * SECOND_BIN_S
            b = backfill_bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": price,
                                                "high": 0.0, "low": 0.0, "n_trades": 0})
            if side == "b":
                b["buy"] += qty
            elif side == "s":
                b["sell"] += qty
            if b["high"] == 0.0 or price > b["high"]:
                b["high"] = price
            if b["low"] == 0.0 or price < b["low"]:
                b["low"] = price
            b["mid"] = price
            b["n_trades"] += 1
            n_trades += 1

        # Advance cursor
        last = result.get("last")
        if not last:
            print(f"[backfill-kr] no 'last' cursor; stopping", flush=True)
            break
        next_since = int(last)
        if next_since <= since_ns:
            print(f"[backfill-kr] cursor not advancing; stopping", flush=True)
            break
        since_ns = next_since

        if time.time() - last_progress_log >= 30.0:
            elapsed = time.time() - t0
            cur_age_d = (time.time() - since_ns / 1e9) / 86400
            print(f"[backfill-kr] elapsed={elapsed:.0f}s calls={n_calls} trades={n_trades:,} "
                  f"bins={len(backfill_bins):,} cursor_age={cur_age_d:.2f}d", flush=True)
            last_progress_log = time.time()

        # Stop when cursor catches up to ~now (within 60s)
        if since_ns / 1e9 >= time.time() - 60:
            print(f"[backfill-kr] cursor caught up to current; stopping", flush=True)
            break

        time.sleep(INTER_REQUEST_SLEEP_S)

    elapsed = time.time() - t0
    print(f"[backfill-kr] {pair}: done. {n_calls} calls, {n_trades:,} trades, "
          f"{len(backfill_bins):,} backfill bins, {elapsed:.0f}s elapsed", flush=True)

    merged = dict(existing)
    n_filled = 0
    for ts, b in backfill_bins.items():
        if ts not in merged:
            merged[ts] = b
            n_filled += 1
    print(f"[backfill-kr] merged: {len(merged)} total bins ({n_filled} filled by backfill)",
          flush=True)
    _save_bins(merged, args.bins_path)
    print(f"[backfill-kr] saved {args.bins_path}", flush=True)


if __name__ == "__main__":
    main()
