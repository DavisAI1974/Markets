"""
databento_backfill.py — TRUE-TICK historical NYMEX tape from Databento (S84).

The upgrade over pyth_backfill.py: Databento's CME Globex dataset (GLBX.MDP3) carries WTI crude (CL)
AND Henry Hub natural gas (NG) — the feed Pyth simply does not have — at the `trades` schema = EVERY
individual print at nanosecond timestamps. So it fixes both S84 gaps: NG coverage, and the 1-sec
UNDERSAMPLING of the Pyth backfill (this is the actual tape, not a 1/sec sample). NYMEX is the canary
(see NYMEX_CANARY_NOTES_S84.md); this is the high-fidelity historical canary.

Cost: usage-based $/GB, $125 free signup credit; a release-window trades pull is <$0.01. Two modes:
  * window  — sync timeseries.get_range for one release window (fast, tiny).
  * batch   — async batch.submit_job for LARGE ranges (cheaper per GB, re-downloadable free 30d).
Every pull is preceded by metadata.get_cost and gated on --max-cost so we never overspend by surprise.

Auth: needs DATABENTO_API_KEY in the env (a SECRET — env var / GH Actions secret, never hardcode/commit).
Symbology: continuous front-month via stype_in="continuous", symbol "CL.c.0"/"NG.c.0" (auto-roll).

Output: data/pyth_ticks/{symbol}_{YYYYMMDD}.jsonl, records {"ts","price","size","symbol","src"} — the
same shape the live collector + pyth_backfill write, so the lag/baseline code consumes all three feeds
identically. Zero synthetic.

STATUS: written against the databento==0.81 client API (signatures verified); NOT yet run — needs the
API key. Install: pip install databento.

CLI:
  DATABENTO_API_KEY=... python research/kalshi/databento_backfill.py cost   --symbol CL --release 2026-07-08T14:30:00Z
  DATABENTO_API_KEY=... python research/kalshi/databento_backfill.py window --symbol CL --release 2026-07-08T14:30:00Z --pre 120 --post 1800
  DATABENTO_API_KEY=... python research/kalshi/databento_backfill.py batch  --symbol NG --start 2026-01-01 --end 2026-07-12 --max-cost 5.0
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone

DATASET = "GLBX.MDP3"                         # CME Globex: NYMEX (CL crude, NG Henry Hub gas), COMEX
CONT = {"CL": "CL.c.0", "NG": "NG.c.0"}       # continuous front-month (auto-roll). Brent = ICE dataset.
OUT_DIR = "data/pyth_ticks"


def _client():
    import databento as db
    key = os.environ.get("DATABENTO_API_KEY")
    if not key:
        raise SystemExit("[databento] set DATABENTO_API_KEY (a secret) in the env first")
    return db.Historical(key)


def _sym(symbol: str) -> tuple[str, str]:
    """(databento symbol, stype_in). Continuous front-month if a bare root, else raw contract."""
    if symbol in CONT:
        return CONT[symbol], "continuous"
    return symbol, "raw_symbol"


def estimate_cost(client, sym: str, stype: str, start: str, end: str, schema: str) -> float:
    cost = client.metadata.get_cost(dataset=DATASET, symbols=[sym], stype_in=stype,
                                    schema=schema, start=start, end=end)
    print(f"[databento] est. cost {sym} {schema} {start}..{end}: ${cost:.4f}")
    return cost


def _write_df(df, symbol: str) -> int:
    """DBNStore.to_df() -> per-day JSONL in the tick format. Index is ts_event (ns UTC)."""
    os.makedirs(OUT_DIR, exist_ok=True)
    handles: dict[str, object] = {}
    n = 0
    for ts, row in df.iterrows():
        sec = ts.timestamp() if hasattr(ts, "timestamp") else float(ts) / 1e9
        px = float(row["price"])
        size = int(row.get("size", 0) or 0)
        day = datetime.fromtimestamp(sec, timezone.utc).strftime("%Y%m%d")
        fh = handles.get(day)
        if fh is None:
            fh = open(os.path.join(OUT_DIR, f"{symbol}_{day}.jsonl"), "a", buffering=1)
            handles[day] = fh
        fh.write(json.dumps({"ts": sec, "price": px, "size": size,
                             "symbol": symbol, "src": "databento_trades"}) + "\n")
        n += 1
    for fh in handles.values():
        fh.close()
    return n


def window(client, symbol: str, release: str, pre: int, post: int, schema: str, max_cost: float):
    sym, stype = _sym(symbol)
    rt = datetime.fromisoformat(release.replace("Z", "+00:00"))
    start = (rt - timedelta(seconds=pre)).isoformat()
    end = (rt + timedelta(seconds=post)).isoformat()
    if estimate_cost(client, sym, stype, start, end, schema) > max_cost:
        raise SystemExit(f"[databento] over --max-cost ${max_cost}; aborting")
    store = client.timeseries.get_range(dataset=DATASET, symbols=[sym], stype_in=stype,
                                        schema=schema, start=start, end=end)
    df = store.to_df()                          # price scaled to float, ts_event index
    got = _write_df(df, symbol) if len(df) else 0
    print(f"[databento] window {symbol} {release} [-{pre}s,+{post}s]: {got} trades -> {OUT_DIR}")


def batch(client, symbol: str, start: str, end: str, schema: str, max_cost: float):
    sym, stype = _sym(symbol)
    if estimate_cost(client, sym, stype, start, end, schema) > max_cost:
        raise SystemExit(f"[databento] over --max-cost ${max_cost}; aborting")
    job = client.batch.submit_job(dataset=DATASET, symbols=[sym], stype_in=stype, schema=schema,
                                  start=start, end=end, encoding="dbn", compression="zstd")
    print(f"[databento] batch job submitted: id={job.get('id')} state={job.get('state')}")
    print("  poll: client.batch.list_jobs(); download: client.batch.download(job_id, out_dir) "
          "(free re-download within 30d), then feed the .dbn.zst through _write_df.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Databento true-tick NYMEX backfill (CL/NG)")
    ap.add_argument("mode", choices=["cost", "window", "batch"])
    ap.add_argument("--symbol", required=True, help="CL or NG (root -> continuous front) or raw contract")
    ap.add_argument("--release", default=None, help="RFC3339 release time (window/cost mode)")
    ap.add_argument("--pre", type=int, default=120)
    ap.add_argument("--post", type=int, default=1800)
    ap.add_argument("--start", default=None, help="batch/cost start (date or RFC3339)")
    ap.add_argument("--end", default=None, help="batch/cost end")
    ap.add_argument("--schema", default="trades", help="trades (every print) | mbp-1 | tbbo | ohlcv-1s")
    ap.add_argument("--max-cost", type=float, default=1.0, help="abort if est. cost exceeds this ($)")
    args = ap.parse_args()

    client = _client()
    if args.mode in ("window", "cost") and args.release:
        rt = datetime.fromisoformat(args.release.replace("Z", "+00:00"))
        start = (rt - timedelta(seconds=args.pre)).isoformat()
        end = (rt + timedelta(seconds=args.post)).isoformat()
    else:
        start, end = args.start, args.end

    if args.mode == "cost":
        sym, stype = _sym(args.symbol)
        estimate_cost(client, sym, stype, start, end, args.schema)
    elif args.mode == "window":
        window(client, args.symbol, args.release, args.pre, args.post, args.schema, args.max_cost)
    elif args.mode == "batch":
        if not (start and end):
            raise SystemExit("[databento] batch needs --start and --end")
        batch(client, args.symbol, start, end, args.schema, args.max_cost)


if __name__ == "__main__":
    main()
