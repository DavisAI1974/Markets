#!/usr/bin/env python3
"""Repair the one missing Sunday-reopen MBP-10 file in the NG historical corpus.

This is a corpus repair only. It pulls exactly the UTC date 2025-06-29 from the
same volume-continuous NG.v.0 series used by nymex_cont, writes every MBP-10
message/column through the existing raw writer, and refuses to proceed above a
hard cost ceiling.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
from pathlib import Path

import databento as db

from research.kalshi.databento_backfill import _write_mbp10_df

DATASET = "GLBX.MDP3"
SYMBOL = "NG.v.0"
STYPE = "continuous"
SCHEMA = "mbp-10"
START = "2025-06-29T00:00:00Z"
END = "2025-06-30T00:00:00Z"
DAY = "20250629"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="/tmp/ng_repair_20250629")
    ap.add_argument("--max-cost", type=float, default=0.01)
    args = ap.parse_args()

    key = os.environ.get("DATABENTO_API_KEY")
    if not key:
        raise SystemExit("DATABENTO_API_KEY missing")
    client = db.Historical(key)
    cost = float(client.metadata.get_cost(
        dataset=DATASET,
        symbols=[SYMBOL],
        stype_in=STYPE,
        schema=SCHEMA,
        start=START,
        end=END,
    ))
    if cost > args.max_cost:
        raise SystemExit(f"repair cost ${cost:.6f} exceeds hard ceiling ${args.max_cost:.6f}")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    store = client.timeseries.get_range(
        dataset=DATASET,
        symbols=[SYMBOL],
        stype_in=STYPE,
        schema=SCHEMA,
        start=START,
        end=END,
    )
    df = store.to_df()
    if df is None or len(df) == 0:
        raise SystemExit("Databento returned no MBP-10 rows for 2025-06-29")

    rows = int(_write_mbp10_df(df, "NG", out_dir=str(out)))
    raw = out / f"NG_{DAY}.jsonl"
    if rows <= 0 or not raw.exists() or raw.stat().st_size <= 0:
        raise SystemExit("raw writer did not produce the expected Sunday file")

    gz = out / f"NG_{DAY}_sun.jsonl.gz"
    with raw.open("rb") as src, gzip.open(gz, "wb", compresslevel=6) as dst:
        shutil.copyfileobj(src, dst)
    raw.unlink()
    if gz.stat().st_size < 5000:
        raise SystemExit(f"repaired Sunday gzip unexpectedly tiny: {gz.stat().st_size} bytes")

    trade_rows = 0
    first_trade = None
    last_trade = None
    with gzip.open(gz, "rt") as f:
        for line in f:
            r = json.loads(line)
            if r.get("action") == "T":
                trade_rows += 1
                ts = r.get("ts_event", r.get("ts"))
                try:
                    t = float(ts.timestamp()) if hasattr(ts, "timestamp") else float(ts)
                except Exception:
                    t = None
                if t is not None:
                    first_trade = t if first_trade is None else min(first_trade, t)
                    last_trade = t if last_trade is None else max(last_trade, t)
    if trade_rows <= 0:
        raise SystemExit("repaired Sunday file contains no trades")

    report = {
        "status": "REPAIR_READY_FOR_UPLOAD",
        "series": SYMBOL,
        "schema": SCHEMA,
        "start": START,
        "end": END,
        "estimated_cost_usd": cost,
        "hard_cost_ceiling_usd": args.max_cost,
        "rows": rows,
        "trade_rows": trade_rows,
        "gzip_path": str(gz),
        "gzip_bytes": gz.stat().st_size,
        "gzip_sha256": sha256(gz),
        "first_trade_epoch": first_trade,
        "last_trade_epoch": last_trade,
    }
    Path("NG_EXHAUSTION_REPAIR_20250629_REPORT.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
