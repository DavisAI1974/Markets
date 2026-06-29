"""
backfill_binance_vision.py

Backfills Binance USDT-M futures bins by downloading daily aggTrades zip
files from data.binance.vision (the Binance Vision public S3 bucket, no
auth, no API key).

Output schema matches binance_*_perp_collector.py exactly so RT bins and
backfill bins are interchangeable. Mid price for backfill is the last
trade price within each 1-second bin (true mid-quote isn't available
historically without separately downloading bookTicker zips, which
doubles bandwidth for marginal accuracy gain).

Merge semantics: existing RT bins always win. Backfill only fills gaps.

Usage:
    python backfill_binance_vision.py \\
        --symbol BTCUSDT --days 30 --bins-path btc_binance_perp_bins.json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import time
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone


VISION_BASE = (
    "https://data.binance.vision/data/futures/um/daily/aggTrades/"
    "{symbol}/{symbol}-aggTrades-{date}.zip"
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
        print(f"[backfill-bn] could not load existing bins: {e}", flush=True)
        return {}


def _save_bins(bins: dict, path: str) -> None:
    serializable = {str(k): v for k, v in bins.items()}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(serializable, f)
    os.replace(tmp, path)


def _download_day(symbol: str, date_str: str) -> bytes | None:
    url = VISION_BASE.format(symbol=symbol, date=date_str)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "markets-watch-backfill/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"[backfill-bn] {date_str}: not yet published (404)", flush=True)
            return None
        print(f"[backfill-bn] {date_str}: HTTP {e.code}", flush=True)
        return None
    except Exception as e:
        print(f"[backfill-bn] {date_str}: {type(e).__name__}: {e}", flush=True)
        return None


def _parse_zip_into_bins(zip_bytes: bytes, bins: dict) -> int:
    """Parse one daily aggTrades zip, accumulate into bins (in place).
    Returns number of trades parsed.
    """
    n_trades = 0
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        if not names:
            return 0
        with zf.open(names[0]) as f:
            reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8"))
            for row in reader:
                # Futures aggTrades schema:
                # 0:agg_id  1:price  2:qty  3:first_id  4:last_id
                # 5:transact_time(ms)  6:is_buyer_maker
                if len(row) < 7:
                    continue
                # Skip header row if present (sometimes Vision includes it)
                if not row[0].lstrip("-").isdigit():
                    continue
                try:
                    price = float(row[1])
                    qty = float(row[2])
                    first_id = int(row[3])
                    last_id = int(row[4])
                    t_ms = int(row[5])
                    is_buyer_maker = row[6].strip().lower() in ("true", "1", "t")
                except (ValueError, IndexError):
                    continue
                ts = int((t_ms / 1000.0) / SECOND_BIN_S) * SECOND_BIN_S
                n_raw = max(1, last_id - first_id + 1)
                b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": price,
                                          "high": 0.0, "low": 0.0, "n_trades": 0})
                if is_buyer_maker:
                    b["sell"] += qty
                else:
                    b["buy"] += qty
                if b["high"] == 0.0 or price > b["high"]:
                    b["high"] = price
                if b["low"] == 0.0 or price < b["low"]:
                    b["low"] = price
                # Mid = last trade price seen in bin (proxy; true mid-quote
                # would require separately downloading bookTicker zips)
                b["mid"] = price
                b["n_trades"] += n_raw
                n_trades += n_raw
    return n_trades


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", type=str, required=True, help="e.g. BTCUSDT or ETHUSDT")
    p.add_argument("--days", type=int, default=30, help="how many days back to backfill")
    p.add_argument("--bins-path", type=str, required=True,
                   help="output bins file (existing RT bins are preserved)")
    args = p.parse_args()

    symbol = args.symbol.upper()

    existing = _load_existing_bins(args.bins_path)
    print(f"[backfill-bn] {symbol}: loaded {len(existing)} existing bins", flush=True)

    backfill_bins: dict[float, dict] = {}
    today_utc = datetime.now(tz=timezone.utc).date()
    days_processed = 0
    days_missing = 0
    total_trades = 0

    # Walk backwards so newest data lands first; if a day fails we still
    # have older days. Skip today (not yet published).
    for d in range(1, args.days + 1):
        date = today_utc - timedelta(days=d)
        date_str = date.isoformat()
        zip_bytes = _download_day(symbol, date_str)
        if zip_bytes is None:
            days_missing += 1
            continue
        n = _parse_zip_into_bins(zip_bytes, backfill_bins)
        total_trades += n
        days_processed += 1
        print(f"[backfill-bn] {date_str}: {n:,} trades  (running bins={len(backfill_bins)})",
              flush=True)

    print(f"[backfill-bn] {symbol}: {days_processed} days processed, "
          f"{days_missing} missing, {total_trades:,} trades, "
          f"{len(backfill_bins):,} backfill bins", flush=True)

    # Merge: existing RT bins always win, backfill fills gaps only.
    merged = dict(existing)
    n_filled = 0
    for ts, b in backfill_bins.items():
        if ts not in merged:
            merged[ts] = b
            n_filled += 1
    print(f"[backfill-bn] merged: {len(merged)} total bins ({n_filled} filled by backfill)",
          flush=True)

    _save_bins(merged, args.bins_path)
    print(f"[backfill-bn] saved {args.bins_path}", flush=True)


if __name__ == "__main__":
    main()
