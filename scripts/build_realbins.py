"""
scripts/build_realbins.py — merge the daily collector JSONL into the merged per-source
realbins/<source>_bins.json that odcore.io.load_bins and markets_adapter.load_minute_bars
consume UNCHANGED.

Why: the git data/* branches stalled on 2026-05-17, but the collectors kept writing locally
to live_data_history/<YYYY-MM-DD>/<source>_bins.jsonl through ~today. This rebuilds realbins/
from that full local history so every OD script (od_real_run, the dipole runner, backtests)
runs on weeks of data instead of the stale ~10-day git snapshot.

Only the fields the two loaders read are kept (slim): buy, sell, mid, bid, ask, n_trades.

Usage:
    python scripts/build_realbins.py --days 30
    python scripts/build_realbins.py --start 2026-05-10 --end 2026-06-08 \
        --sources btc_coinbase eth_coinbase
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, timedelta

DEFAULT_HISTORY = "E:/Markets/live_data_history"
OUT = os.path.join(os.path.dirname(__file__), "..", "realbins")
KEEP = ("buy", "sell", "mid", "bid", "ask", "n_trades")
DEFAULT_SOURCES = ["btc_coinbase", "btc_kraken", "btc_bybit_perp",
                   "eth_coinbase", "eth_kraken", "eth_bybit_perp"]


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--history-dir", default=DEFAULT_HISTORY)
    ap.add_argument("--sources", nargs="+", default=DEFAULT_SOURCES)
    ap.add_argument("--days", type=int, default=30, help="window length ending at --end")
    ap.add_argument("--start", default=None, help="YYYY-MM-DD (overrides --days)")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD (default: latest dated folder)")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    avail = sorted(d for d in os.listdir(args.history_dir)
                   if len(d) == 10 and d[4] == "-" and d[7] == "-")
    if not avail:
        print(f"no dated folders in {args.history_dir}")
        return
    end = date.fromisoformat(args.end) if args.end else date.fromisoformat(avail[-1])
    start = date.fromisoformat(args.start) if args.start else end - timedelta(days=args.days - 1)
    os.makedirs(args.out, exist_ok=True)
    print(f"window {start}..{end}  ({(end - start).days + 1} days)  "
          f"available {avail[0]}..{avail[-1]}  sources={args.sources}")

    for src in args.sources:
        merged: dict[str, dict] = {}
        days_used = 0
        for d in daterange(start, end):
            path = os.path.join(args.history_dir, d.isoformat(), f"{src}_bins.jsonl")
            if not os.path.exists(path):
                continue
            days_used += 1
            with open(path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        b = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = b.get("ts")
                    if ts is None or b.get("mid") is None:
                        continue
                    merged[str(ts)] = {k: b.get(k) for k in KEEP}
        if not merged:
            print(f"  {src:18} NO DATA in window")
            continue
        outp = os.path.join(args.out, f"{src}_bins.json")
        with open(outp, "w") as fh:
            json.dump(merged, fh)
        ks = sorted(int(float(k)) for k in merged)
        span = (ks[-1] - ks[0]) / 86400
        mb = os.path.getsize(outp) / 1e6
        print(f"  {src:18} days={days_used:>2}  bins={len(merged):>8}  "
              f"span={span:4.1f}d  fill={len(merged)/(ks[-1]-ks[0]+1):4.0%}  "
              f"{mb:6.1f}MB", flush=True)


if __name__ == "__main__":
    main()
