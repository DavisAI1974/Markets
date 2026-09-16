"""
kalshi_ng_backfill.py - FEED L (DATA_GATE_S98): Kalshi-side NG market data - inventory / backfill.

WHY THIS EXISTS (S98 two-coach architecture): the Kalshi coach's echo replay (feed M) needs the
Kalshi side of the walked winter - KXNATGASD-family daily NG settle brackets, Nov 1 2025 -
Feb 27 2026. THE STRUCTURAL FINDING THIS BUILD ESTABLISHED (2026-07-20): that market DID NOT
EXIST in the winter. KXNATGASD's first market was created 2026-03-27T23:29:42Z (first settle
2026-03-30); KXNATGASW's first close is 2026-04-03; KXNATGASMON's first close is 2026-04-30. The
only NG-linked Kalshi markets alive in the walked winter were three ANNUAL threshold events
(KXNGASMAX-25DEC29, KXNGASMAX-B-25DEC29, KXNGASMIN-25DEC29). This module therefore backfills:
  (a) the FULL LIFE of the KXNATGASD family (2026-03-30 -> present) - the real substrate feed M
      can measure the NYMEX->Kalshi lag on, and
  (b) the winter annual NG markets - the only recoverable winter Kalshi NG data.
Full detail + per-date coverage: research/kalshi/KALSHI_NG_COVERAGE_S98.md.

API REALITY (verified empirically 2026-07-20, docs.kalshi.com):
  * Two disjoint worlds, split by a moving "historical cutoff" (measured ~2 months back;
    regular /markets?status=settled served close_time >= 2026-05-14 on 2026-07-20):
      RECENT   -> GET /markets, /markets/trades, /series/{s}/markets/{t}/candlesticks
      ARCHIVED -> GET /historical/markets, /historical/trades,
                  /historical/markets/{t}/candlesticks
    Regular endpoints return 0 rows / 404 for archived markets and vice versa. Every fetch here
    routes by which enumeration answered, with cross-side fallback (the cutoff MOVES).
  * All six endpoints are PUBLIC - no auth, no account. Both api.elections.kalshi.com and
    external-api.kalshi.com serve identically (we use the former, matching the collectors).
  * Candlesticks: period_interval in {1,60,1440} minutes, HARD CAP 5000 candles per request
    (HTTP 400 above it) -> chunked at 4500. Sparse markets yield sparse grids (only minutes
    with book/trade activity return rows).
  * Trades rows carry BOTH legacy `taker_side` and current `taker_outcome_side`/`taker_book_side`.
    kalshi_history.py (S80) still parses, but its reduced row shape drops fields - THIS store
    keeps every field the API returns, raw, plus provenance fields prefixed "_".
  * NO historical orderbook endpoint exists. Book depth history is STRUCTURALLY UNOBTAINABLE;
    the only book-adjacent history is the candles' yes_bid/yes_ask OHLC (top-of-book). Full
    depth exists only where a live collector snapshotted it (data/kalshi-bins branch,
    2026-07-12 onward).

STORE (git = CODE, S3 = DATA; data/kalshi_ng/ is gitignored; S3 push is the orchestrator's):
  data/kalshi_ng/markets/<SERIES>_markets.jsonl.gz          full raw market definitions
  data/kalshi_ng/trades/<SERIES>/<EVENT>_trades.jsonl.gz    full raw trades, all strikes of the event
  data/kalshi_ng/candles/<SERIES>/<EVENT>_candles_<N>m.jsonl.gz  raw candles + "ticker" per row
  data/kalshi_ng/meta/pull_log.jsonl                        per-event pull provenance
Missing is explicit: an event with an empty trades file means THE API RETURNED ZERO TRADES
(file written with 0 rows + pull_log entry); an absent file means NOT PULLED.

Zero synthetic data. No interpolation. Builders do not commit.

Usage:
  python research/kalshi/kalshi_ng_backfill.py --enumerate            # defs for the NG family
  python research/kalshi/kalshi_ng_backfill.py --pull KXNATGASD       # trades+1m candles, all settled events
  python research/kalshi/kalshi_ng_backfill.py --pull KXNATGASW --pull KXNATGASMON
  python research/kalshi/kalshi_ng_backfill.py --pull-winter-annuals  # KXNGASMAX/KXNGASMIN winter events
  python research/kalshi/kalshi_ng_backfill.py --coverage             # per-date coverage tables
  python research/kalshi/kalshi_ng_backfill.py --selftest
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import gzip
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.elections.kalshi.com/trade-api/v2"
STORE = os.path.join("data", "kalshi_ng")
FAMILY = ["KXNATGASD", "KXNATGASW", "KXNATGASMON"]
WINTER_ANNUAL_SERIES = ["KXNGASMAX", "KXNGASMIN"]
WIN_LO, WIN_HI = "2025-11-01", "2026-02-27"          # the walked winter (inclusive)
ANNUAL_1M_LO, ANNUAL_1M_HI = "2025-10-01", "2026-02-28"  # 1-min candle window for annuals
CANDLE_CAP = 4500                                     # server hard cap is 5000/request
MIN_INTERVAL = 0.13                                   # ~7.7 req/s, under the 10/s public tier
_last = [0.0]


# ---- HTTP ----------------------------------------------------------------------------------
def _get(path: str, retries: int = 6, **params):
    """Polite GET -> parsed JSON. Honors Retry-After on 429; exponential backoff on 5xx/net.
    Returns None on 404 (endpoint answered: no such resource)."""
    q = "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}) if params else ""
    url = BASE + path + q
    for attempt in range(retries + 1):
        wait = MIN_INTERVAL - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                _last[0] = time.time()
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            _last[0] = time.time()
            if e.code == 404:
                return None
            if e.code == 400:
                raise RuntimeError(f"HTTP 400 on {path}{q}: {e.read().decode()[:200]}")
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                ra = e.headers.get("Retry-After")
                time.sleep(float(ra) if ra and ra.isdigit() else 2.0 ** attempt)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt < retries:
                time.sleep(2.0 ** attempt)
                continue
            raise
    return None


# ---- store helpers -------------------------------------------------------------------------
def _write_gz_jsonl(path: str, rows: list[dict]) -> None:
    """Atomic gzip-jsonl write (tmp + replace). An EMPTY file is a valid statement: the API
    answered and returned zero rows for this event (missing-is-explicit)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    os.replace(tmp, path)


def _read_gz_jsonl(path: str) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _log(store: str, entry: dict) -> None:
    p = os.path.join(store, "meta", "pull_log.jsonl")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    entry["logged_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")


def _ts(iso: str | None) -> int | None:
    if not iso:
        return None
    return int(dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


# ---- enumeration (both worlds, tagged) -----------------------------------------------------
def enumerate_series(series: str, page_cap: int = 400) -> list[dict]:
    """All markets for a series from BOTH the live DB (statuses settled/closed/open) and the
    historical archive. Each raw record gains _src ('live'|'archived'; live wins on overlap,
    _also_archived marks the overlap) and _fetched_at. Full raw fields preserved."""
    by_ticker: dict[str, dict] = {}
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    def page(path: str, src: str, **extra):
        cur, pages = None, 0
        while pages < page_cap:
            d = _get(path, series_ticker=series, limit=1000, cursor=cur, **extra)
            ms = (d or {}).get("markets", [])
            for m in ms:
                t = m.get("ticker")
                if not t:
                    continue
                if t in by_ticker:
                    if src == "archived" and by_ticker[t]["_src"] == "live":
                        by_ticker[t]["_also_archived"] = True
                    continue
                m["_src"] = src
                m["_fetched_at"] = now
                by_ticker[t] = m
            cur = (d or {}).get("cursor")
            pages += 1
            if not cur or not ms:
                break

    for status in ("settled", "closed", "open"):
        page("/markets", "live", status=status)
    page("/historical/markets", "archived")
    out = sorted(by_ticker.values(), key=lambda m: (m.get("close_time") or "", m.get("ticker") or ""))
    return out


def load_or_enumerate(store: str, series: str, refresh: bool = False) -> list[dict]:
    p = os.path.join(store, "markets", f"{series}_markets.jsonl.gz")
    if not refresh and os.path.exists(p):
        return _read_gz_jsonl(p)
    ms = enumerate_series(series)
    _write_gz_jsonl(p, ms)
    _log(store, {"kind": "markets", "series": series, "n_rows": len(ms)})
    print(f"[markets] {series}: {len(ms)} defs -> {p}", flush=True)
    return ms


# ---- trades --------------------------------------------------------------------------------
def fetch_trades(ticker: str, src: str, cap: int = 500000) -> list[dict]:
    """All trades for one ticker, raw rows. Routes by _src with cross-side fallback (the
    cutoff moves). Sorted by created_time."""
    paths = ["/markets/trades", "/historical/trades"] if src == "live" else \
            ["/historical/trades", "/markets/trades"]
    for path in paths:
        out, cur = [], None
        while len(out) < cap:
            d = _get(path, ticker=ticker, limit=1000, cursor=cur)
            tr = (d or {}).get("trades", [])
            out += tr
            cur = (d or {}).get("cursor")
            if not cur or not tr:
                break
        if out:
            for r in out:
                r["_src"] = "live" if path == "/markets/trades" else "archived"
            out.sort(key=lambda r: r.get("created_time") or "")
            return out
    return []


# ---- candles -------------------------------------------------------------------------------
def fetch_candles(series: str, ticker: str, src: str, start_ts: int, end_ts: int,
                  interval_min: int) -> list[dict]:
    """Candlesticks for one ticker over [start_ts, end_ts], chunked under the 5000/request cap.
    Routes by _src with cross-side fallback on 404/empty-first-chunk. Raw candle dicts + ticker."""
    span = CANDLE_CAP * interval_min * 60
    paths = [f"/series/{series}/markets/{ticker}/candlesticks",
             f"/historical/markets/{ticker}/candlesticks"]
    if src != "live":
        paths.reverse()
    for path in paths:
        out, lo, dead = [], start_ts, False
        while lo < end_ts:
            hi = min(lo + span, end_ts)
            d = _get(path, start_ts=lo, end_ts=hi, period_interval=interval_min)
            if d is None:                      # 404 -> wrong side, try the other endpoint
                dead = True
                break
            for c in d.get("candlesticks", []):
                c["ticker"] = ticker
                c["_src"] = "live" if path.startswith("/series/") else "archived"
                out.append(c)
            lo = hi
        if not dead:
            out.sort(key=lambda c: c.get("end_period_ts") or 0)
            return out
    return []


# ---- per-event pull ------------------------------------------------------------------------
def pull_event(store: str, series: str, event: str, markets: list[dict],
               intervals: list[int], candle_window: tuple[int, int] | None = None,
               force: bool = False) -> dict:
    """Pull trades + candles for every strike of one event. Resume: existing files skipped
    unless force. Candle range = each market's [open_time-60s, close_time+60s], optionally
    clamped to candle_window."""
    strikes = [m for m in markets if m.get("event_ticker") == event]
    res = {"event": event, "n_strikes": len(strikes)}
    t0 = time.time()

    tr_path = os.path.join(store, "trades", series, f"{event}_trades.jsonl.gz")
    if force or not os.path.exists(tr_path):
        all_tr = []
        for m in strikes:
            all_tr += fetch_trades(m["ticker"], m.get("_src", "live"))
        all_tr.sort(key=lambda r: (r.get("created_time") or "", r.get("ticker") or ""))
        _write_gz_jsonl(tr_path, all_tr)
        res["n_trades"] = len(all_tr)
        _log(store, {"kind": "trades", "series": series, "event": event,
                     "n_rows": len(all_tr), "n_markets": len(strikes),
                     "t_sec": round(time.time() - t0, 1)})
    else:
        res["n_trades"] = "cached"

    for iv in intervals:
        t1 = time.time()
        cd_path = os.path.join(store, "candles", series, f"{event}_candles_{iv}m.jsonl.gz")
        if not force and os.path.exists(cd_path):
            res[f"n_candles_{iv}m"] = "cached"
            continue
        all_cd = []
        for m in strikes:
            lo = _ts(m.get("open_time") or m.get("created_time"))
            hi = _ts(m.get("close_time"))
            if lo is None or hi is None:
                continue
            lo, hi = lo - 60, hi + 60
            if candle_window:
                lo, hi = max(lo, candle_window[0]), min(hi, candle_window[1])
                if lo >= hi:
                    continue
            all_cd += fetch_candles(series, m["ticker"], m.get("_src", "live"), lo, hi, iv)
        _write_gz_jsonl(cd_path, all_cd)
        res[f"n_candles_{iv}m"] = len(all_cd)
        _log(store, {"kind": f"candles_{iv}m", "series": series, "event": event,
                     "n_rows": len(all_cd), "n_markets": len(strikes),
                     "t_sec": round(time.time() - t1, 1)})
    return res


def pull_series(store: str, series: str, intervals: list[int], force: bool = False,
                include_open: bool = False) -> None:
    ms = load_or_enumerate(store, series)
    skip_status = {"active", "open"} if not include_open else set()
    events = sorted({m["event_ticker"] for m in ms
                     if m.get("event_ticker") and (m.get("status") or "") not in skip_status})
    open_events = sorted({m["event_ticker"] for m in ms
                          if (m.get("status") or "") in {"active", "open"}})
    if open_events and not include_open:
        print(f"[{series}] SKIPPING open (partial-day) events: {open_events} "
              f"(re-run after settle)", flush=True)
    print(f"[{series}] {len(events)} events to pull, intervals={intervals}", flush=True)
    for i, e in enumerate(events, 1):
        r = pull_event(store, series, e, ms, intervals, force=force)
        print(f"  [{i:>3}/{len(events)}] {e:<28} strikes={r['n_strikes']:<3} "
              f"trades={r['n_trades']} " +
              " ".join(f"c{iv}m={r.get(f'n_candles_{iv}m')}" for iv in intervals), flush=True)


def pull_winter_annuals(store: str, force: bool = False) -> None:
    """The only NG-linked Kalshi markets alive in the walked winter: annual threshold events.
    1-min candles restricted to ANNUAL_1M window; 60m + 1440m over full life."""
    w1 = (int(dt.datetime.fromisoformat(ANNUAL_1M_LO + "T00:00:00+00:00").timestamp()),
          int(dt.datetime.fromisoformat(ANNUAL_1M_HI + "T23:59:59+00:00").timestamp()))
    for series in WINTER_ANNUAL_SERIES:
        ms = load_or_enumerate(store, series)
        events = sorted({m["event_ticker"] for m in ms if m.get("event_ticker")
                         and "25DEC" in m["event_ticker"]})
        print(f"[{series}] winter annual events: {events}", flush=True)
        for e in events:
            r = pull_event(store, series, e, ms, intervals=[60, 1440], force=force)
            r2 = pull_event(store, series, e, ms, intervals=[1], candle_window=w1, force=force)
            print(f"  {e}: strikes={r['n_strikes']} trades={r['n_trades']} "
                  f"c60m={r.get('n_candles_60m')} c1440m={r.get('n_candles_1440m')} "
                  f"c1m(window)={r2.get('n_candles_1m')}", flush=True)


# ---- coverage ------------------------------------------------------------------------------
def _event_date(event: str, close_time: str | None) -> str | None:
    """Trade date of a daily event = its close date (close 21:00/22:00Z same day)."""
    return close_time[:10] if close_time else None


def coverage(store: str) -> None:
    print("=" * 100)
    print("WALKED WINTER Nov 1 2025 - Feb 27 2026: KXNATGASD-family coverage")
    print("=" * 100)
    fam_defs = {}
    for s in FAMILY:
        p = os.path.join(store, "markets", f"{s}_markets.jsonl.gz")
        fam_defs[s] = _read_gz_jsonl(p) if os.path.exists(p) else []
        first = min(((m.get("created_time") or "9") for m in fam_defs[s]), default=None)
        firstc = min(((m.get("close_time") or "9") for m in fam_defs[s]), default=None)
        print(f"  {s:<13} defs={len(fam_defs[s]):<6} first market created {str(first)[:19]} "
              f"first close {str(firstc)[:10]}")
    print(f"  -> every date {WIN_LO}..{WIN_HI} is a NAMED GAP for the family: the series did"
          f" not exist (first creation 2026-03-27). No backfill can exist.")

    print("-" * 100)
    print("Winter NG-linked markets that DID exist (annual thresholds):")
    for s in WINTER_ANNUAL_SERIES:
        p = os.path.join(store, "markets", f"{s}_markets.jsonl.gz")
        for m in (_read_gz_jsonl(p) if os.path.exists(p) else []):
            if "25DEC" not in (m.get("event_ticker") or ""):
                continue
            print(f"  {m['ticker']:<26} open {str(m.get('open_time'))[:10]} close "
                  f"{str(m.get('close_time'))[:10]} vol={m.get('volume_fp')} "
                  f"result={m.get('result')}")

    print("=" * 100)
    print("KXNATGASD series life (per event-day): defs / trades rows / 1m candle rows")
    print("=" * 100)
    ms = fam_defs.get("KXNATGASD", [])
    by_ev: dict[str, list[dict]] = {}
    for m in ms:
        by_ev.setdefault(m.get("event_ticker") or "?", []).append(m)
    rows = []
    for e, mm in by_ev.items():
        d = _event_date(e, max((m.get("close_time") or "") for m in mm))
        tr = os.path.join(store, "trades", "KXNATGASD", f"{e}_trades.jsonl.gz")
        cd = os.path.join(store, "candles", "KXNATGASD", f"{e}_candles_1m.jsonl.gz")
        n_tr = len(_read_gz_jsonl(tr)) if os.path.exists(tr) else None
        n_cd = len(_read_gz_jsonl(cd)) if os.path.exists(cd) else None
        vol = sum(float(m.get("volume_fp") or 0) for m in mm)
        rows.append((d, e, len(mm), n_tr, n_cd, vol, mm[0].get("status")))
    rows.sort()
    # listing gaps: business days inside the life with no event
    have = {r[0] for r in rows}
    if rows:
        d0 = dt.date.fromisoformat(rows[0][0])
        d1 = dt.date.fromisoformat(rows[-1][0])
        gaps = []
        d = d0
        while d <= d1:
            if d.weekday() < 5 and d.isoformat() not in have:
                gaps.append(d.isoformat())
            d += dt.timedelta(days=1)
    for d, e, n_mk, n_tr, n_cd, vol, st in rows:
        print(f"  {d}  {e:<26} strikes={n_mk:<3} trades={'-' if n_tr is None else n_tr:<7} "
              f"candles1m={'-' if n_cd is None else n_cd:<7} vol={vol:>10.0f} {st}")
    if rows and gaps:
        print(f"  LISTING GAPS (weekday, no event listed by Kalshi): {gaps}")
    print("  ('-' = not pulled; 0 = pulled, API returned zero rows)")


# ---- selftest ------------------------------------------------------------------------------
def selftest(store: str) -> int:
    """Store readability + known-date row counts (verified against the live API 2026-07-20):
    KXNATGASD-26MAR3017 is the first settled event-day (archived side); its T2.845 strike
    printed exactly 2 trades in its life. Trades are immutable history - the count is stable."""
    fails = 0

    def check(name, ok, detail=""):
        nonlocal fails
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
        if not ok:
            fails += 1

    files = sorted(glob.glob(os.path.join(store, "**", "*.jsonl.gz"), recursive=True))
    check("store has files", bool(files), f"{len(files)} .jsonl.gz files")
    bad = 0
    for p in files:
        try:
            with gzip.open(p, "rt", encoding="utf-8") as f:
                line = f.readline()
                if line.strip():
                    json.loads(line)
        except Exception as ex:
            bad += 1
            print(f"    unreadable: {p}: {ex}")
    check("every file opens + first line parses", bad == 0, f"{bad} unreadable")

    mp = os.path.join(store, "markets", "KXNATGASD_markets.jsonl.gz")
    if os.path.exists(mp):
        defs = _read_gz_jsonl(mp)
        check("KXNATGASD defs >= 5000", len(defs) >= 5000, f"{len(defs)} defs")
        t = [m for m in defs if m.get("ticker") == "KXNATGASD-26MAR3017-T2.845"]
        check("first-day strike KXNATGASD-26MAR3017-T2.845 present", bool(t))
        first_created = min((m.get("created_time") or "9") for m in defs)
        check("series launch: earliest created_time across defs is 2026-03-27",
              first_created.startswith("2026-03-27"), first_created)
        # NOTE: per-STRIKE created_time is NOT the launch date - strikes are added intraday
        # as price moves (ladder churn); T2.845 itself was created 2026-03-30T18:02Z.
        srcs = {m.get("_src") for m in defs}
        check("both routing sources present in defs", srcs >= {"live", "archived"}, str(srcs))
    else:
        check("KXNATGASD defs file exists", False, mp)

    tp = os.path.join(store, "trades", "KXNATGASD", "KXNATGASD-26MAR3017_trades.jsonl.gz")
    if os.path.exists(tp):
        tr = _read_gz_jsonl(tp)
        n845 = sum(1 for r in tr if r.get("ticker") == "KXNATGASD-26MAR3017-T2.845")
        check("known date 2026-03-30: event trades file non-empty", len(tr) > 0, f"{len(tr)} rows")
        check("known count: T2.845 strike has exactly 2 trades", n845 == 2, f"{n845}")
        check("trades keep raw fields (yes_price_dollars + taker_outcome_side)",
              all(("yes_price_dollars" in r and "taker_outcome_side" in r) for r in tr[:50]))
    else:
        check("known-date trades file exists (pull KXNATGASD first)", False, tp)

    cp = os.path.join(store, "candles", "KXNATGASD", "KXNATGASD-26MAR3017_candles_1m.jsonl.gz")
    if os.path.exists(cp):
        cd = _read_gz_jsonl(cp)
        check("known date 2026-03-30: 1m candles non-empty", len(cd) > 0, f"{len(cd)} rows")
        check("candle rows carry yes_bid/yes_ask + ticker",
              all(("yes_bid" in c and "ticker" in c) for c in cd[:50]))
    else:
        check("known-date candles file exists (pull KXNATGASD first)", False, cp)

    print(f"[selftest] {'PASS' if fails == 0 else f'{fails} FAILURES'}")
    return 1 if fails else 0


# ---- CLI -----------------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Feed L: Kalshi NG family backfill (S98 gate)")
    ap.add_argument("--store", default=STORE)
    ap.add_argument("--enumerate", action="store_true", help="(re)pull market definitions for the family + winter annuals")
    ap.add_argument("--pull", action="append", default=[], help="series to pull trades+candles for (repeatable)")
    ap.add_argument("--pull-winter-annuals", action="store_true")
    ap.add_argument("--intervals", default="1", help="comma candle minutes for --pull (default 1)")
    ap.add_argument("--include-open", action="store_true", help="also pull currently-open (partial) events")
    ap.add_argument("--force", action="store_true", help="re-pull cached event files")
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.enumerate:
        for s in FAMILY + WINTER_ANNUAL_SERIES:
            ms = enumerate_series(s)
            p = os.path.join(args.store, "markets", f"{s}_markets.jsonl.gz")
            _write_gz_jsonl(p, ms)
            _log(args.store, {"kind": "markets", "series": s, "n_rows": len(ms)})
            evs = {m.get("event_ticker") for m in ms}
            cl = [m.get("close_time") or "" for m in ms]
            print(f"[markets] {s}: {len(ms)} defs, {len(evs)} events, close-range "
                  f"{min(cl)[:10] if cl else '-'} -> {max(cl)[:10] if cl else '-'}", flush=True)
    for s in args.pull:
        ivs = [int(x) for x in args.intervals.split(",") if x.strip()]
        pull_series(args.store, s, ivs, force=args.force, include_open=args.include_open)
    if args.pull_winter_annuals:
        pull_winter_annuals(args.store, force=args.force)
    if args.coverage:
        coverage(args.store)
    if args.selftest:
        raise SystemExit(selftest(args.store))


if __name__ == "__main__":
    main()
