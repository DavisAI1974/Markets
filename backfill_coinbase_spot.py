"""
backfill_coinbase_spot.py

Backfills Coinbase Exchange spot bins via the public /products/{id}/trades
REST endpoint. Walks history backward from the latest trade using the
`before` cursor (which is a trade-id sequence number in the response's
`CB-BEFORE` header).

Coinbase's free public history is deeper than 24h despite docs being
fuzzy on the limit; in practice you can usually walk back ~30 days but
peak BTC trade rates push API call counts to ~7 hours of fetching for a
full 30 days. The wallclock budget arg lets us cap and accept whatever
depth we got.

Output schema matches coinbase_*_collector.py exactly. Mid for backfill
is the last trade price within each 1-second bin (Coinbase historical
trades don't carry the bid/ask; use the RT collector for true mid).

Merge semantics: existing RT bins always win. Backfill fills gaps only.

Usage:
    python backfill_coinbase_spot.py --product BTC-USD --days 30 \\
        --bins-path btc_coinbase_bins.json
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request


CB_BASE = "https://api.exchange.coinbase.com"
SECOND_BIN_S = 1.0
INTER_REQUEST_SLEEP_S = 0.12  # ~8 req/s, well under 10 req/s public limit
MAX_RETRIES = 5


def _load_existing_bins(path: str) -> dict[float, dict]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            raw = json.load(f)
        return {float(k): v for k, v in raw.items()}
    except Exception as e:
        print(f"[backfill-cb] could not load existing bins: {e}", flush=True)
        return {}


def _save_bins(bins: dict, path: str) -> None:
    serializable = {str(k): v for k, v in bins.items()}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(serializable, f)
    os.replace(tmp, path)


def _cursor_path_for(bins_path: str) -> str:
    if bins_path.endswith(".json"):
        return bins_path[:-5] + ".cursor.json"
    return bins_path + ".cursor.json"


def _load_cursor(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"[backfill-cb] could not load cursor {path}: {e}", flush=True)
        return None


def _save_cursor(path: str, oldest_before: int | None, oldest_ts: float | None) -> None:
    if oldest_before is None:
        return
    payload = {
        "oldest_before": int(oldest_before),
        "oldest_ts": float(oldest_ts) if oldest_ts is not None else None,
        "saved_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f)
    os.replace(tmp, path)


def _fetch_page(product: str, before: int | None) -> tuple[list, int | None] | None:
    """Returns (trades_list, next_before_cursor) or None on hard failure.
    If before is None, fetches the most recent page.
    """
    url = f"{CB_BASE}/products/{product}/trades?limit=1000"
    if before is not None:
        url += f"&before={before}"

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "markets-watch-backfill/1.0", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
                trades = json.loads(body)
                # Pagination cursor in headers
                cb_before = resp.headers.get("CB-BEFORE")
                next_before = int(cb_before) if cb_before else None
                return trades, next_before
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 2 ** attempt
                print(f"[backfill-cb] 429 rate-limited; sleeping {wait}s", flush=True)
                time.sleep(wait)
                continue
            print(f"[backfill-cb] HTTP {e.code} on attempt {attempt+1}: {e.reason}", flush=True)
            time.sleep(2 ** attempt)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            print(f"[backfill-cb] {type(e).__name__} on attempt {attempt+1}: {e}", flush=True)
            time.sleep(2 ** attempt)
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--product", type=str, required=True, help="e.g. BTC-USD or ETH-USD")
    p.add_argument("--days", type=int, default=30,
                   help="how many days back to attempt (may stop earlier if budget exhausted)")
    p.add_argument("--max-seconds", type=int, default=18000,
                   help="wallclock budget for fetching (default 5h)")
    p.add_argument("--bins-path", type=str, required=True)
    p.add_argument("--cursor-path", type=str, default=None,
                   help="sidecar JSON storing oldest pagination cursor; lets a subsequent "
                        "run resume where this one left off. Default: <bins>.cursor.json")
    p.add_argument("--no-resume", action="store_true",
                   help="ignore any existing cursor file and walk back from now")
    args = p.parse_args()

    product = args.product.upper()
    cursor_path = args.cursor_path or _cursor_path_for(args.bins_path)

    existing = _load_existing_bins(args.bins_path)
    print(f"[backfill-cb] {product}: loaded {len(existing)} existing bins", flush=True)

    cutoff_ts = time.time() - args.days * 86400
    print(f"[backfill-cb] target: {args.days}d back  (cutoff_ts={cutoff_ts:.0f})", flush=True)

    backfill_bins: dict[float, dict] = {}
    n_calls = 0
    n_trades = 0
    t0 = time.time()
    last_progress_log = t0
    before_cursor: int | None = None
    oldest_seen_ts: float | None = None

    if not args.no_resume:
        prev = _load_cursor(cursor_path)
        if prev and isinstance(prev.get("oldest_before"), int):
            before_cursor = prev["oldest_before"]
            prev_ts = prev.get("oldest_ts")
            if isinstance(prev_ts, (int, float)):
                oldest_seen_ts = float(prev_ts)
            print(f"[backfill-cb] resuming from cursor before={before_cursor} "
                  f"(prev oldest_ts={prev_ts})", flush=True)
            if oldest_seen_ts is not None and oldest_seen_ts < cutoff_ts:
                print(f"[backfill-cb] cursor already past cutoff "
                      f"({oldest_seen_ts:.0f} < {cutoff_ts:.0f}); nothing to do",
                      flush=True)
                _save_cursor(cursor_path, before_cursor, oldest_seen_ts)
                return

    while True:
        if time.time() - t0 > args.max_seconds:
            print(f"[backfill-cb] wallclock budget exhausted ({args.max_seconds}s); stopping",
                  flush=True)
            break

        page = _fetch_page(product, before_cursor)
        n_calls += 1
        if page is None:
            print(f"[backfill-cb] hard fetch failure; stopping", flush=True)
            break
        trades, next_before = page
        if not trades:
            print(f"[backfill-cb] empty page; reached end of history", flush=True)
            break

        for tr in trades:
            try:
                price = float(tr["price"])
                qty = float(tr["size"])
                # Coinbase 'side' is the MAKER side. Flip for taker direction.
                maker_side = str(tr.get("side", "")).lower()
                # Time is ISO8601
                t_iso = tr["time"]
                # Quick parse: strip 'Z' or '+00:00' for fromisoformat (Py3.11 ok with Z)
                if t_iso.endswith("Z"):
                    t_iso = t_iso[:-1] + "+00:00"
                t_s = time.mktime(time.strptime(t_iso[:19], "%Y-%m-%dT%H:%M:%S"))
                # Apply UTC offset since strptime returns localtime-based mktime
                t_s -= time.timezone
                # Add fractional seconds if present
                if "." in t_iso:
                    frac = t_iso.split(".", 1)[1].split("+", 1)[0].rstrip("Z")
                    try:
                        t_s += float("0." + frac)
                    except ValueError:
                        pass
            except (KeyError, ValueError, TypeError) as e:
                continue

            ts = int(t_s / SECOND_BIN_S) * SECOND_BIN_S
            if oldest_seen_ts is None or ts < oldest_seen_ts:
                oldest_seen_ts = ts

            b = backfill_bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": price,
                                                "high": 0.0, "low": 0.0, "n_trades": 0})
            # Coinbase 'side' = maker side. taker_buy = maker_sold = side='sell'
            if maker_side == "sell":
                b["buy"] += qty
            elif maker_side == "buy":
                b["sell"] += qty
            if b["high"] == 0.0 or price > b["high"]:
                b["high"] = price
            if b["low"] == 0.0 or price < b["low"]:
                b["low"] = price
            b["mid"] = price
            b["n_trades"] += 1
            n_trades += 1

        if oldest_seen_ts is not None and oldest_seen_ts < cutoff_ts:
            print(f"[backfill-cb] reached cutoff (oldest={oldest_seen_ts:.0f} < {cutoff_ts:.0f})",
                  flush=True)
            break

        if next_before is None or (before_cursor is not None and next_before >= before_cursor):
            print(f"[backfill-cb] cursor not advancing; stopping", flush=True)
            break
        before_cursor = next_before

        if time.time() - last_progress_log >= 30.0:
            elapsed = time.time() - t0
            depth_d = (time.time() - (oldest_seen_ts or time.time())) / 86400
            print(f"[backfill-cb] elapsed={elapsed:.0f}s calls={n_calls} trades={n_trades:,} "
                  f"bins={len(backfill_bins):,} depth={depth_d:.2f}d", flush=True)
            last_progress_log = time.time()

        time.sleep(INTER_REQUEST_SLEEP_S)

    elapsed = time.time() - t0
    actual_d = (time.time() - (oldest_seen_ts or time.time())) / 86400
    print(f"[backfill-cb] {product}: done. {n_calls} calls, {n_trades:,} trades, "
          f"{len(backfill_bins):,} backfill bins, depth={actual_d:.2f}d, "
          f"{elapsed:.0f}s elapsed", flush=True)

    merged = dict(existing)
    n_filled = 0
    for ts, b in backfill_bins.items():
        if ts not in merged:
            merged[ts] = b
            n_filled += 1
    print(f"[backfill-cb] merged: {len(merged)} total bins ({n_filled} filled by backfill)",
          flush=True)
    _save_bins(merged, args.bins_path)
    print(f"[backfill-cb] saved {args.bins_path}", flush=True)

    _save_cursor(cursor_path, before_cursor, oldest_seen_ts)
    if before_cursor is not None:
        print(f"[backfill-cb] cursor saved to {cursor_path} "
              f"(oldest_before={before_cursor}, oldest_ts={oldest_seen_ts})",
              flush=True)


if __name__ == "__main__":
    main()
