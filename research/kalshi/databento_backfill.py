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
Symbology: continuous front-month via stype_in="continuous". Default roll = VOLUME ("CL.v.0"/"NG.v.0")
so we track the liquid front Kalshi reprices off, not the nearest-expiry calendar contract (--roll c/n/v).

Output: data/pyth_ticks/{symbol}_{YYYYMMDD}.jsonl, records {"ts","price","size","symbol","src"} — the
same shape the live collector + pyth_backfill write, so the lag/baseline code consumes all three feeds
identically. Zero synthetic.

MBP-10 (S86): with --schema mbp-10 the pull carries the 10-level book. The writer (`_write_mbp10_df`)
keeps only TRADE events with their concurrent book (top-of-book + per-side 10-level depth totals) ->
data/nymex_mbp10/{symbol}_{YYYYMMDD}.jsonl (its OWN dir, never mixed with the trades tape). This is the
depth/imbalance/exhaustion read for event_move_baseline --depth.

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
import time
from datetime import datetime, timedelta, timezone

DATASET = "GLBX.MDP3"                         # CME Globex: NYMEX (CL crude, NG Henry Hub gas), COMEX
ROOTS = {"CL", "NG"}                          # bare roots we resolve to continuous front-month. Brent = ICE.
# Continuous roll rule for the front-month (index .0): v=volume, n=open-interest, c=calendar/nearest-expiry.
# DEFAULT v (volume) — the canary must be the LIQUID front Kalshi reprices off; calendar (.c) keeps reading
# the nearest-expiry contract even after volume has migrated to the next month a week+ before it expires.
ROLL = "v"
OUT_DIR = "data/pyth_ticks"
MBP10_DIR = "data/nymex_mbp10"                # depth tape lives in its OWN dir (never mixed with trades)


def _retry(fn, tries=5, base=2.0):
    """Call fn(), retrying on TRANSIENT network errors (reset/timeout/aborted) with exp backoff.
    Non-network errors (bad symbol, over-cost, auth) re-raise immediately. The proxy occasionally
    resets long streaming pulls (ConnectionResetError 104) — a retry clears it."""
    transient = ("connection", "reset", "aborted", "timed out", "timeout", "temporarily",
                 "protocolerror", "remotedisconnected", "broken pipe")
    for i in range(tries):
        try:
            return fn()
        except SystemExit:
            raise
        except Exception as e:                        # noqa: BLE001 - classify by message
            msg = f"{type(e).__name__} {e}".lower()
            if i == tries - 1 or not any(k in msg for k in transient):
                raise
            wait = base ** i
            print(f"[databento] transient error ({type(e).__name__}), retry {i + 1}/{tries - 1} in {wait:.0f}s")
            time.sleep(wait)


def _client():
    import databento as db
    key = os.environ.get("DATABENTO_API_KEY")
    if not key:
        raise SystemExit("[databento] set DATABENTO_API_KEY (a secret) in the env first")
    return db.Historical(key)


def _sym(symbol: str) -> tuple[str, str]:
    """(databento symbol, stype_in). Continuous front-month (roll rule ROLL) if a bare root, else raw."""
    if symbol.upper() in ROOTS:
        return f"{symbol.upper()}.{ROLL}.0", "continuous"
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


def _write_mbp10_df(df, symbol: str) -> int:
    """MBP-10 DBNStore.to_df() -> per-day depth JSONL. We keep only TRADE events (action=='T') carrying
    their CONCURRENT 10-level book snapshot — same lean density as the `trades` tape (so the S85 price
    path reproduces byte-for-byte off the T prints), plus the book at each trade for the imbalance /
    thinning (exhaustion) read. Book updates between trades (A/C/M) are dropped to keep the tape lean and
    branch-storable; the raw MBP-10 is re-downloadable free within 30d if the full book is ever needed.

    Record: {ts (ts_event), price, size, symbol, src, bid_px, ask_px, bid_sz, ask_sz, bid_dep, ask_dep}
      bid_px/ask_px/bid_sz/ask_sz = top of book (level 00); bid_dep/ask_dep = sum of the 10 resting sizes
      per side (the depth whose thinning = liquidity being consumed = the leader exhausting resistance).
    Written to MBP10_DIR (NOT OUT_DIR) so load_tape() never mixes it with the trades tape."""
    os.makedirs(MBP10_DIR, exist_ok=True)
    bid_sz_cols = [f"bid_sz_0{i}" for i in range(10) if f"bid_sz_0{i}" in df.columns]
    ask_sz_cols = [f"ask_sz_0{i}" for i in range(10) if f"ask_sz_0{i}" in df.columns]
    handles: dict[str, object] = {}
    n = 0
    has_te = "ts_event" in df.columns
    for idx, row in df.iterrows():
        if str(row.get("action")) != "T":            # trades only (the price path + book-at-trade)
            continue
        te = row["ts_event"] if has_te else idx        # exchange event time (fall back to index=ts_recv)
        sec = te.timestamp() if hasattr(te, "timestamp") else float(te) / 1e9
        px = row.get("price")
        if px is None or (isinstance(px, float) and px != px):   # skip NaN-priced (shouldn't happen for T)
            continue
        def _f(col):
            v = row.get(col)
            return float(v) if v is not None and v == v else 0.0
        bid_dep = sum(_f(c) for c in bid_sz_cols)
        ask_dep = sum(_f(c) for c in ask_sz_cols)
        day = datetime.fromtimestamp(sec, timezone.utc).strftime("%Y%m%d")
        fh = handles.get(day)
        if fh is None:
            fh = open(os.path.join(MBP10_DIR, f"{symbol}_{day}.jsonl"), "a", buffering=1)
            handles[day] = fh
        fh.write(json.dumps({
            "ts": sec, "price": float(px), "size": int(row.get("size", 0) or 0),
            "symbol": symbol, "src": "databento_mbp10",
            "bid_px": _f("bid_px_00"), "ask_px": _f("ask_px_00"),
            "bid_sz": _f("bid_sz_00"), "ask_sz": _f("ask_sz_00"),
            "bid_dep": round(bid_dep, 1), "ask_dep": round(ask_dep, 1),
        }) + "\n")
        n += 1
    for fh in handles.values():
        fh.close()
    return n


def _root(symbol: str) -> str:
    """CL.c.0/CLQ6 -> CL, NG.c.0/NGDQ6 -> NG (the definitions store is keyed by ROOT)."""
    s = symbol.upper()
    if s.startswith("NG"):
        return "NG"
    if s.startswith(("CL", "WTI")):
        return "CL"
    if s.startswith(("BRENT", "BZ")):
        return "BRENT"
    return s.split(".")[0]


def _write_defs_df(df, root: str) -> int:
    """definition-schema DBNStore.to_df() -> {root}_definitions.jsonl, point-in-time tick spec.

    Captures tick_size = min_price_increment and unit_qty = unit_of_measure_qty (tick_value = the
    product) at each effective ts, deduping runs where the spec is unchanged so the store stays sparse.
    FIRST-RUN CHECK (do once when the key lands): CL and NG should both land at tick_value == $10
    (CL 0.01x1000, NG 0.001x10000) — if unit_qty comes back fixed-point-scaled (e.g. ~1e12), divide by
    1e9 here; event_move_baseline reads tick_value and tags any reference fallback, so a wrong scale
    shows up immediately against REFERENCE_TICKS. Do NOT hardcode — this store IS the point-in-time truth."""
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{root}_definitions.jsonl")
    n = 0
    last = None
    with open(path, "a", buffering=1) as fh:
        for ts, row in df.iterrows():
            sec = ts.timestamp() if hasattr(ts, "timestamp") else float(ts) / 1e9
            tsz = row.get("min_price_increment")
            uq = row.get("unit_of_measure_qty")
            if tsz is None:
                continue
            tsz = float(tsz)
            uq = float(uq) if uq is not None else None
            key = (round(tsz, 12), None if uq is None else round(uq, 6))
            if key == last:                          # unchanged spec -> skip (keep store sparse)
                continue
            last = key
            rec = {"ts": sec, "symbol": root, "raw_symbol": row.get("raw_symbol"),
                   "tick_size": tsz, "unit_qty": uq,
                   "tick_value": (tsz * uq) if uq is not None else None}
            fh.write(json.dumps(rec) + "\n")
            n += 1
    return n


def defs(client, symbol: str, start: str, end: str, max_cost: float):
    """Pull the definition schema over a date range and write the point-in-time tick store."""
    sym, stype = _sym(symbol)
    if estimate_cost(client, sym, stype, start, end, "definition") > max_cost:
        raise SystemExit(f"[databento] over --max-cost ${max_cost}; aborting")
    store = _retry(lambda: client.timeseries.get_range(dataset=DATASET, symbols=[sym], stype_in=stype,
                                                       schema="definition", start=start, end=end))
    df = store.to_df()
    got = _write_defs_df(df, _root(symbol)) if len(df) else 0
    print(f"[databento] defs {symbol} {start}..{end}: {got} definition rows -> "
          f"{OUT_DIR}/{_root(symbol)}_definitions.jsonl  (verify tick_value==$10 for CL/NG on first pull)")


def window(client, symbol: str, release: str, pre: int, post: int, schema: str, max_cost: float):
    if schema == "definition":
        rt = datetime.fromisoformat(release.replace("Z", "+00:00"))
        return defs(client, symbol, (rt - timedelta(seconds=pre)).isoformat(),
                    (rt + timedelta(seconds=post)).isoformat(), max_cost)
    sym, stype = _sym(symbol)
    rt = datetime.fromisoformat(release.replace("Z", "+00:00"))
    start = (rt - timedelta(seconds=pre)).isoformat()
    end = (rt + timedelta(seconds=post)).isoformat()
    if estimate_cost(client, sym, stype, start, end, schema) > max_cost:
        raise SystemExit(f"[databento] over --max-cost ${max_cost}; aborting")
    store = _retry(lambda: client.timeseries.get_range(dataset=DATASET, symbols=[sym], stype_in=stype,
                                                        schema=schema, start=start, end=end))
    df = store.to_df()                          # price scaled to float, ts_event index
    if len(df) and schema.startswith("mbp-10"):
        got = _write_mbp10_df(df, symbol)
        print(f"[databento] window {symbol} {release} [-{pre}s,+{post}s]: {got} trade+book rows -> {MBP10_DIR}")
        return
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
    global ROLL
    ap = argparse.ArgumentParser(description="Databento true-tick NYMEX backfill (CL/NG)")
    ap.add_argument("mode", choices=["cost", "window", "batch", "defs"])
    ap.add_argument("--symbol", required=True, help="CL or NG (root -> continuous front) or raw contract")
    ap.add_argument("--release", default=None, help="RFC3339 release time (window/cost mode)")
    ap.add_argument("--pre", type=int, default=120)
    ap.add_argument("--post", type=int, default=1800)
    ap.add_argument("--start", default=None, help="batch/cost start (date or RFC3339)")
    ap.add_argument("--end", default=None, help="batch/cost end")
    ap.add_argument("--schema", default="trades", help="trades (every print) | mbp-1 | tbbo | ohlcv-1s | definition")
    ap.add_argument("--roll", choices=["v", "n", "c"], default=ROLL,
                    help="continuous roll rule for a bare root: v=volume (default), n=open-interest, c=calendar")
    ap.add_argument("--max-cost", type=float, default=1.0, help="abort if est. cost exceeds this ($)")
    args = ap.parse_args()

    ROLL = args.roll
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
    elif args.mode == "defs":
        if not (start and end):
            raise SystemExit("[databento] defs needs --start and --end (or --release with --pre/--post)")
        defs(client, args.symbol, start, end, args.max_cost)


if __name__ == "__main__":
    main()
