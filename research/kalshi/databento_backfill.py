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
    """S115: resolve through creds.py, the one resolver - this read the process env DIRECTLY, so it
    failed on a fresh container even with the key sitting in ~/.config/markets/env or retrievable
    from SSM. Same family as the nuclear_outages and databento_live_smoke fixes: a feed consumer
    that knows about exactly one credential home is a feed that stops working when the home moves.
    creds.get walks MARKETS_ env vars -> ~/.config/markets/env -> legacy -> SSM SecureString."""
    import databento as db
    import creds
    key = creds.get("DATABENTO_API_KEY", required=False)
    if not key:
        raise SystemExit("[databento] DATABENTO_API_KEY not resolvable - check `python creds.py`. "
                         "Homes: MARKETS_DATABENTO_API_KEY, ~/.config/markets/env, or SSM "
                         "/markets/DATABENTO_API_KEY (needs the AWS pair to read SSM).")
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


L1_DIR = "data/ng_l1"          # the L1 quote/book tape flow_read consumes (bid/ask px + sz)


def _write_mbp1_df(df, symbol: str, out_dir: str = None) -> int:
    """S114: mbp-1 -> the ng_l1 row format flow_read actually reads.

    THE GAP THIS CLOSES. `data/ng_l1/NG_<day>.jsonl.gz` is a declared input (stage_group pulls it,
    firehose_present.l1_book flags it, flow_read serves quote imbalance and spread off it) and
    NOTHING IN THIS MODULE COULD WRITE IT. A `--schema mbp-1` pull fell through to `_write_df`,
    which emits the TRADES format into OUT_DIR and DISCARDS every book field - so the pull
    "succeeded", reported its row count, and produced no L1 file anywhere. Measured on g24: the L1
    book is absent from S3 for 8 of 10 prior sessions and the blind ran without quote imbalance or
    spread on those days.

    Written gzipped, one file per UTC day, matching the existing store byte-for-byte in shape:
      {"ts","action","instrument_id","price","size","side","bid_px","ask_px","bid_sz","ask_sz"}
    """
    import gzip as _gz
    odir = out_dir or L1_DIR
    os.makedirs(odir, exist_ok=True)
    handles: dict[str, object] = {}
    n = 0

    def _num(row, *names):
        for nm in names:
            if nm in row:
                v = row[nm]
                try:
                    if v is None or (isinstance(v, float) and v != v):
                        return None
                except Exception:
                    pass
                return v
        return None

    for ts, row in df.iterrows():
        sec = ts.timestamp() if hasattr(ts, "timestamp") else float(ts) / 1e9
        day = datetime.fromtimestamp(sec, timezone.utc).strftime("%Y%m%d")
        fh = handles.get(day)
        if fh is None:
            fh = _gz.open(os.path.join(odir, f"{symbol}_{day}.jsonl.gz"), "at")
            handles[day] = fh
        rec = {
            "ts": sec,
            "action": row.get("action"),
            "instrument_id": _json_safe(_num(row, "instrument_id")),
            "price": _json_safe(_num(row, "price")),
            "size": _json_safe(_num(row, "size")),
            "side": row.get("side"),
            # DBN mbp-1 exposes level 0 as bid_px_00/ask_px_00; older to_df builds use bid_px/ask_px.
            # Try both rather than assuming - a silently missing book column would reproduce exactly
            # the defect this function exists to fix.
            "bid_px": _json_safe(_num(row, "bid_px_00", "bid_px")),
            "ask_px": _json_safe(_num(row, "ask_px_00", "ask_px")),
            "bid_sz": _json_safe(_num(row, "bid_sz_00", "bid_sz")),
            "ask_sz": _json_safe(_num(row, "ask_sz_00", "ask_sz")),
        }
        fh.write(json.dumps(rec) + "\n")
        n += 1
    for fh in handles.values():
        fh.close()
    return n


def _json_safe(v):
    """Make a DBN cell JSON-serializable without losing info: Timestamp -> epoch seconds, numpy scalar ->
    python scalar, NaN/NaT -> None. No rounding, no dropping."""
    if v is None:
        return None
    if hasattr(v, "timestamp"):                       # pandas/py Timestamp
        try:
            return v.timestamp()
        except Exception:
            return str(v)
    if hasattr(v, "item"):                            # numpy scalar -> python scalar
        try:
            v = v.item()
        except Exception:
            return str(v)
    if isinstance(v, float) and v != v:               # NaN
        return None
    return v


def _write_mbp10_df(df, symbol: str, out_dir: str = None) -> int:
    """RAW MBP-10 ingestion — keep EVERYTHING the dataset carries (Greg S88: we paid for the full dataset,
    we keep all the info; the agent sifts it for correlations; gates live ONLY on the trade-signal side,
    never on the historical data). EVERY message (trades AND book updates A/C/M/etc.) and EVERY column
    Databento provides (all 10 price levels + sizes + counts per side, action, side, depth, flags,
    sequence, ts_event, ts_recv, ...). Zero filtering, zero reduction, zero derived fields. Split per UTC
    day -> {symbol}_{day}.jsonl. Written to MBP10_DIR unless out_dir overrides (the continuous tape)."""
    out = out_dir or MBP10_DIR
    os.makedirs(out, exist_ok=True)
    if df is None or len(df) == 0:
        return 0
    # STREAM row-by-row via itertuples -- do NOT materialize the whole day as a list of dicts
    # (to_dict(orient="records") on a 2M-message day builds gigabytes on top of the frame and gets
    # the process OOM-killed). itertuples yields one lightweight tuple at a time -> bounded memory.
    df2 = df.reset_index()                              # ts_recv index + all columns become columns
    cols = list(df2.columns)
    handles: dict[str, object] = {}
    n = 0
    for row in df2.itertuples(index=False, name=None):
        r = dict(zip(cols, row))
        # ZERO FILTERING (Greg): every decoded record is written, no row is ever dropped. The timestamp
        # is used only to bucket into a per-UTC-day file; if it cannot be parsed the row still goes to
        # an _undated file so nothing is lost. All original columns are kept verbatim regardless.
        sec = None
        for cand in (r.get("ts_event"), r.get("ts_recv")):
            if cand is None:
                continue
            try:
                sec = cand.timestamp() if hasattr(cand, "timestamp") else float(cand) / 1e9
                break
            except Exception:
                continue
        day = (datetime.fromtimestamp(sec, timezone.utc).strftime("%Y%m%d")
               if sec is not None else "undated")
        rec = {"ts": sec, "symbol": symbol, "src": "databento_mbp10"}
        for k, v in r.items():                          # keep ALL original columns verbatim
            rec[str(k)] = _json_safe(v)
        fh = handles.get(day)
        if fh is None:
            fh = open(os.path.join(out, f"{symbol}_{day}.jsonl"), "a", buffering=1)
            handles[day] = fh
        fh.write(json.dumps(rec) + "\n")
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


def range_pull(client, symbol: str, start: str, end: str, schema: str, max_cost: float, out_dir: str = None):
    """SYNCHRONOUS continuous date-range pull -- canary-sized only (a few days; to_df loads to memory).
    Use `batch` for a month+. Writes the continuous intraday tape to out_dir, kept SEPARATE from the
    S86 release-window slices in MBP10_DIR so those baselines are never contaminated."""
    sym, stype = _sym(symbol)
    if estimate_cost(client, sym, stype, start, end, schema) > max_cost:
        raise SystemExit(f"[databento] over --max-cost ${max_cost}; aborting")
    store = _retry(lambda: client.timeseries.get_range(dataset=DATASET, symbols=[sym], stype_in=stype,
                                                        schema=schema, start=start, end=end))
    df = store.to_df()
    if len(df) and schema.startswith("mbp-10"):
        got = _write_mbp10_df(df, symbol, out_dir)
        print(f"[databento] range {symbol} {start}..{end}: {got} trade+book rows -> {out_dir or MBP10_DIR}")
    elif len(df) and schema.startswith("mbp-1"):
        got = _write_mbp1_df(df, symbol, out_dir)
        print(f"[databento] range {symbol} {start}..{end}: {got} L1 rows -> {out_dir or L1_DIR}")
    else:
        got = _write_df(df, symbol) if len(df) else 0
        print(f"[databento] range {symbol} {start}..{end}: {got} trades -> {OUT_DIR}")


def batch(client, symbol: str, start: str, end: str, schema: str, max_cost: float):
    sym, stype = _sym(symbol)
    if estimate_cost(client, sym, stype, start, end, schema) > max_cost:
        raise SystemExit(f"[databento] over --max-cost ${max_cost}; aborting")
    job = client.batch.submit_job(dataset=DATASET, symbols=[sym], stype_in=stype, schema=schema,
                                  start=start, end=end, encoding="dbn", compression="zstd")
    print(f"[databento] batch job submitted: id={job.get('id')} state={job.get('state')}")
    print("  poll: client.batch.list_jobs(); download: client.batch.download(job_id, out_dir) "
          "(free re-download within 30d), then feed the .dbn.zst through _write_df.")


def batch_pull(client, symbol: str, start: str, end: str, schema: str, max_cost: float,
               out_dir: str = None, poll_s: float = 20.0, timeout_s: float = 5400.0,
               flush_dir: str = None) -> int:
    """FULL batch pipeline for a (canary-to-month) range: cost-gate -> submit (split by DAY) -> poll to
    done -> download the .dbn.zst files to a temp dir -> decode EACH FILE streaming (one day in memory at
    a time -> bounded) -> write JSONL to out_dir -> delete the temp files. Returns rows written.

    Batch (vs sync range) is the right tool for large/continuous pulls: files land on disk not memory,
    decode is per-file, and Databento re-serves the job free for 30 days. Loop this per month for a year,
    gzip each month to the data branch, delete local -> the year accrues on the branch, disk stays bounded.

    flush_dir: if set, immediately gzip each freshly-decoded per-day JSONL into flush_dir/{name}.gz and
    delete the raw JSONL, so local never holds more than ONE day of raw at a time even while pulling a
    whole month's batch job (raw MBP-10 keeps every message -> a month of raw JSONL would overrun the
    runner disk; this bounds it to a day without reducing any data)."""
    import tempfile
    import shutil
    import glob
    import gzip as _gz
    import databento as db
    sym, stype = _sym(symbol)
    if estimate_cost(client, sym, stype, start, end, schema) > max_cost:
        raise SystemExit(f"[databento] over --max-cost ${max_cost}; aborting")
    job = _retry(lambda: client.batch.submit_job(dataset=DATASET, symbols=[sym], stype_in=stype,
                 schema=schema, start=start, end=end, encoding="dbn", compression="zstd",
                 split_duration="day"))
    jid = job.get("id")
    print(f"[databento] batch {symbol} {start}..{end} job={jid} state={job.get('state')}", flush=True)
    waited, st = 0.0, job.get("state")
    while waited < timeout_s:
        det = _retry(lambda: client.batch.get_job_details(jid))
        st = det.get("state")
        if st == "done":
            break
        if st in ("expired", "failed"):
            raise SystemExit(f"[databento] batch job {jid} {st}")
        time.sleep(poll_s); waited += poll_s
    if st != "done":
        raise SystemExit(f"[databento] batch job {jid} not done after {int(timeout_s)}s (state {st})")
    total = _download_decode_flush(client, jid, symbol, schema, out_dir, flush_dir)
    print(f"[databento] batch {symbol} {start}..{end}: {total} rows -> {flush_dir or out_dir or MBP10_DIR}",
          flush=True)
    return total


def _download_decode_flush(client, jid: str, symbol: str, schema: str,
                           out_dir: str = None, flush_dir: str = None) -> int:
    """Download an ALREADY-DONE batch job's .dbn.zst files, decode each streaming (one day in memory ->
    bounded), append per-UTC-day JSONL to out_dir, and (if flush_dir) gzip each COMPLETE day + drop raw.

    S90 FIX (load-bearing): a day's JSONL is only complete after the NEXT day-file is processed, because a
    later DBN file writes a few boundary rows (CME trade-date session spans two UTC days; and the ts_event
    vs ts_recv midnight skew puts a straggler into the prior day). The old code gzipped 'wb' each day right
    after the file that first touched it, so the later boundary write truncated the day to a stub -> 80%
    loss (only Fridays / the last day survived). Fix: HOLD the latest 2 UTC-day files unflushed, flush only
    the older now-complete ones; final-flush the rest at the end. Disk stays bounded to ~2-3 days of raw.
    Reused for both fresh pulls (batch_pull) and free RE-DECODE of a done job id (redecode_job)."""
    import tempfile, shutil, glob, gzip as _gz
    import databento as db
    odir = out_dir or MBP10_DIR
    os.makedirs(odir, exist_ok=True)
    if flush_dir:
        os.makedirs(flush_dir, exist_ok=True)

    def _flush(paths):
        # S92 FIX: APPEND ('ab'), never overwrite ('wb'). A day can be flushed once (complete) and then
        # re-touched by a later DBN file's out-of-order boundary straggler, which re-creates a 1-row jsonl;
        # the old 'wb' final-flush CLOBBERED the full .gz with that 1-row residual -> every Monday (the last
        # day of each Tue->Tue week) truncated to a 455-byte stub. Concatenated gzip members decompress as
        # one stream and the reader (load_cont_day) sorts by ts, so appending is loss-free and order-safe.
        for j in paths:
            with open(j, "rb") as src, _gz.open(os.path.join(flush_dir, os.path.basename(j) + ".gz"),
                                                "ab", compresslevel=6) as dst:
                shutil.copyfileobj(src, dst)
            os.remove(j)

    tmp = tempfile.mkdtemp(prefix="dbn_")
    try:
        _retry(lambda: client.batch.download(jid, output_dir=tmp))
        total = 0
        for p in sorted(glob.glob(os.path.join(tmp, "**", "*.dbn.zst"), recursive=True)):
            df = db.DBNStore.from_file(p).to_df()
            if len(df):
                total += (_write_mbp10_df(df, symbol, out_dir) if schema.startswith("mbp-10")
                          else _write_mbp1_df(df, symbol, out_dir) if schema.startswith("mbp-1")
                          else _write_df(df, symbol))
            os.remove(p)
            if flush_dir:
                jsonls = sorted(glob.glob(os.path.join(odir, f"{symbol}_*.jsonl")))
                if len(jsonls) > 2:                                # hold the latest 2 (still open to boundary)
                    _flush(jsonls[:-2])
        if flush_dir:
            _flush(sorted(glob.glob(os.path.join(odir, f"{symbol}_*.jsonl"))))
        return total
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def redecode_job(client, jid: str, symbol: str, schema: str = "mbp-10",
                 out_dir: str = None, flush_dir: str = None) -> int:
    """Re-decode an ALREADY-DONE, ALREADY-PAID batch job by id (free re-serve, ~30d) with the S90 flush fix.
    Recovers a corrupt month without re-charging Databento. symbol = the ROOT used in filenames (CL/NG)."""
    det = _retry(lambda: client.batch.get_job_details(jid))
    if det.get("state") != "done":
        raise SystemExit(f"[databento] job {jid} not done (state {det.get('state')})")
    print(f"[databento] re-decode job {jid} ({symbol} {schema}) with the S90 flush fix", flush=True)
    return _download_decode_flush(client, jid, symbol, schema, out_dir, flush_dir)


def main() -> None:
    global ROLL
    ap = argparse.ArgumentParser(description="Databento true-tick NYMEX backfill (CL/NG)")
    ap.add_argument("mode", choices=["cost", "window", "range", "batch", "pull", "defs"])
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
    ap.add_argument("--out-dir", default=None, help="output dir override (continuous tape kept separate "
                    "from the release-window slices in MBP10_DIR)")
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
    elif args.mode == "range":
        if not (start and end):
            raise SystemExit("[databento] range needs --start and --end")
        range_pull(client, args.symbol, start, end, args.schema, args.max_cost, args.out_dir)
    elif args.mode == "batch":
        if not (start and end):
            raise SystemExit("[databento] batch needs --start and --end")
        batch(client, args.symbol, start, end, args.schema, args.max_cost)
    elif args.mode == "pull":
        if not (start and end):
            raise SystemExit("[databento] pull needs --start and --end")
        batch_pull(client, args.symbol, start, end, args.schema, args.max_cost, args.out_dir)
    elif args.mode == "defs":
        if not (start and end):
            raise SystemExit("[databento] defs needs --start and --end (or --release with --pre/--post)")
        defs(client, args.symbol, start, end, args.max_cost)


if __name__ == "__main__":
    main()
