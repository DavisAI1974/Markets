"""
backfill_bybit.py

Backfills Bybit USDT linear-perp bins by downloading daily trade dumps
from public.bybit.com (the Bybit public trading archive, no auth, no API
key). History goes back to each symbol's listing date (BTC/ETH/DOGE/XRP
reach 2021; SOL perp listed later -> use Binance Vision for SOL's deep
history).

Output schema matches bybit_perp_collector.py exactly so RT bins and
backfill bins are interchangeable. Mid price for backfill is the last
trade price within each 1-second bin (the historical dump carries trades
only, not the bid/ask; use the RT collector for true mid-quote).

Dump CSV columns (with header row):
    timestamp,symbol,side,size,price,tickDirection,trdMatchID,...
  - timestamp : epoch SECONDS, float (sub-second precision)
  - side      : TAKER side ("Buy"|"Sell") -- same convention as the RT
                publicTrade 'S' field, so no flip is needed
  - size      : base-asset quantity
  - price     : trade price

Merge semantics: existing RT bins always win. Backfill only fills gaps.

Usage:
    python backfill_bybit.py --symbol BTCUSDT --days 30 \\
        --bins-path btc_bybit_perp_bins.json
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone


DUMP_BASE = "https://public.bybit.com/trading/{symbol}/{symbol}{date}.csv.gz"
SECOND_BIN_S = 1.0


def _load_existing_bins(path: str) -> dict[float, dict]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            raw = json.load(f)
        return {float(k): v for k, v in raw.items()}
    except Exception as e:  # noqa: BLE001
        print(f"[backfill-by] could not load existing bins: {e}", flush=True)
        return {}


def _save_bins(bins: dict, path: str) -> None:
    serializable = {str(k): v for k, v in bins.items()}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(serializable, f)
    os.replace(tmp, path)


def _download_day(symbol: str, date_str: str) -> bytes | None:
    url = DUMP_BASE.format(symbol=symbol, date=date_str)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "markets-watch-backfill/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"[backfill-by] {date_str}: not published (404 -- before listing or not yet up)",
                  flush=True)
            return None
        print(f"[backfill-by] {date_str}: HTTP {e.code}", flush=True)
        return None
    except Exception as e:  # noqa: BLE001
        print(f"[backfill-by] {date_str}: {type(e).__name__}: {e}", flush=True)
        return None


def _parse_gz_into_bins(gz_bytes: bytes, bins: dict) -> int:
    """Parse one daily dump (gzip csv), accumulate into bins (in place).
    Returns number of trades parsed.
    """
    n_trades = 0
    with gzip.open(io.BytesIO(gz_bytes), "rt", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            # 0:timestamp 1:symbol 2:side 3:size 4:price 5:tickDirection ...
            if len(row) < 5:
                continue
            # Skip header row ("timestamp" is not a number)
            try:
                t_s = float(row[0])
            except ValueError:
                continue
            try:
                qty = float(row[3])
                price = float(row[4])
            except (ValueError, IndexError):
                continue
            side = str(row[2]).strip().lower()  # taker side: "buy" | "sell"
            ts = int(t_s / SECOND_BIN_S) * SECOND_BIN_S
            b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": price,
                                      "high": 0.0, "low": 0.0, "n_trades": 0})
            if side == "buy":
                b["buy"] += qty
            elif side == "sell":
                b["sell"] += qty
            if b["high"] == 0.0 or price > b["high"]:
                b["high"] = price
            if b["low"] == 0.0 or price < b["low"]:
                b["low"] = price
            # Mid = last trade price seen in bin (proxy; true mid-quote would
            # require the RT collector's bid/ask, absent from the dump).
            b["mid"] = price
            b["n_trades"] += 1
            n_trades += 1
    return n_trades


def main():
    p = argparse.ArgumentParser(description="Bybit linear-perp daily-dump backfill")
    p.add_argument("--symbol", type=str, required=True,
                   help="e.g. BTCUSDT, ETHUSDT, SOLUSDT, DOGEUSDT, XRPUSDT")
    p.add_argument("--days", type=int, default=30, help="how many days back to backfill")
    p.add_argument("--bins-path", type=str, required=True,
                   help="output bins file (existing RT bins are preserved)")
    args = p.parse_args()

    symbol = args.symbol.upper()

    existing = _load_existing_bins(args.bins_path)
    print(f"[backfill-by] {symbol}: loaded {len(existing)} existing bins", flush=True)

    backfill_bins: dict[float, dict] = {}
    today_utc = datetime.now(tz=timezone.utc).date()
    days_processed = 0
    days_missing = 0
    total_trades = 0

    # Walk backwards so newest data lands first; skip today (not yet published).
    for d in range(1, args.days + 1):
        date = today_utc - timedelta(days=d)
        date_str = date.isoformat()
        gz_bytes = _download_day(symbol, date_str)
        if gz_bytes is None:
            days_missing += 1
            continue
        n = _parse_gz_into_bins(gz_bytes, backfill_bins)
        total_trades += n
        days_processed += 1
        print(f"[backfill-by] {date_str}: {n:,} trades  (running bins={len(backfill_bins):,})",
              flush=True)

    print(f"[backfill-by] {symbol}: {days_processed} days processed, "
          f"{days_missing} missing, {total_trades:,} trades, "
          f"{len(backfill_bins):,} backfill bins", flush=True)

    # Merge: existing RT bins always win, backfill fills gaps only.
    merged = dict(existing)
    n_filled = 0
    for ts, b in backfill_bins.items():
        if ts not in merged:
            merged[ts] = b
            n_filled += 1
    print(f"[backfill-by] merged: {len(merged)} total bins ({n_filled} filled by backfill)",
          flush=True)

    _save_bins(merged, args.bins_path)
    print(f"[backfill-by] saved {args.bins_path}", flush=True)


if __name__ == "__main__":
    main()
