"""backfill_binance_spot.py — Binance SPOT daily aggTrades dumps -> 1-sec bins (S54).

Spot sibling of backfill_binance_vision.py (which pulls USDT-M futures). Purpose: an independent
bulk-history SPOT venue for the big-line multi-window gate — Coinbase (our deploy books) has no
bulk dumps, and the S54 Bybit-perp 30d sweep failed the gate; spot-vs-perp decides whether that
was venue microstructure or window luck.

Same output schema as the other backfills (interchangeable with realbins). Spot aggTrades CSV:
0:agg_id 1:price 2:qty 3:first_id 4:last_id 5:transact_time 6:is_buyer_maker 7:is_best_match.
transact_time is ms in files before 2025-01-01 and MICROSECONDS after (Binance Vision spot
format change) — detected per row by magnitude.

Usage:
    python backfill_binance_spot.py --symbol SOLUSDT --days 30 --bins-path sol_binance_spot_bins.json
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone

VISION_BASE = ("https://data.binance.vision/data/spot/daily/aggTrades/"
               "{symbol}/{symbol}-aggTrades-{date}.zip")
SECOND_BIN_S = 1.0


def _download_day(symbol: str, date_str: str) -> bytes | None:
    url = VISION_BASE.format(symbol=symbol, date=date_str)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "markets-watch-backfill/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        print(f"[backfill-bns] {date_str}: HTTP {e.code}", flush=True)
        return None
    except Exception as e:
        print(f"[backfill-bns] {date_str}: {type(e).__name__}: {e}", flush=True)
        return None


def _parse_zip_into_bins(zip_bytes: bytes, bins: dict) -> int:
    n_trades = 0
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        if not names:
            return 0
        with zf.open(names[0]) as f:
            reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8"))
            for row in reader:
                if len(row) < 7 or not row[0].lstrip("-").isdigit():
                    continue
                try:
                    price = float(row[1])
                    qty = float(row[2])
                    first_id = int(row[3])
                    last_id = int(row[4])
                    t_raw = int(row[5])
                    is_buyer_maker = row[6].strip().lower() in ("true", "1", "t")
                except (ValueError, IndexError):
                    continue
                t_s = t_raw / 1e6 if t_raw > 1e14 else t_raw / 1e3   # us (2025+) vs ms
                ts = int(t_s / SECOND_BIN_S) * SECOND_BIN_S
                n_raw = max(1, last_id - first_id + 1)
                b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": price,
                                         "high": 0.0, "low": 0.0, "n_trades": 0})
                if is_buyer_maker:          # buyer is maker -> taker SOLD
                    b["sell"] += qty
                else:
                    b["buy"] += qty
                if b["high"] == 0.0 or price > b["high"]:
                    b["high"] = price
                if b["low"] == 0.0 or price < b["low"]:
                    b["low"] = price
                b["mid"] = price
                b["n_trades"] += n_raw
                n_trades += n_raw
    return n_trades


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", type=str, required=True)
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--bins-path", type=str, required=True)
    args = p.parse_args()

    bins: dict = {}
    if os.path.exists(args.bins_path):
        with open(args.bins_path) as f:
            bins = {float(k): v for k, v in json.load(f).items()}
    print(f"[backfill-bns] {args.symbol}: loaded {len(bins)} existing bins", flush=True)

    today = datetime.now(timezone.utc).date()
    total = 0
    for d in range(1, args.days + 1):
        date_str = (today - timedelta(days=d)).strftime("%Y-%m-%d")
        blob = _download_day(args.symbol, date_str)
        if blob is None:
            continue
        n = _parse_zip_into_bins(blob, bins)
        total += n
        print(f"[backfill-bns] {date_str}: {n:,} trades  (running bins={len(bins):,})", flush=True)

    with open(args.bins_path, "w") as f:
        json.dump({str(k): v for k, v in sorted(bins.items())}, f)
    print(f"[backfill-bns] saved {args.bins_path} ({len(bins):,} bins, {total:,} trades)",
          flush=True)


if __name__ == "__main__":
    main()
