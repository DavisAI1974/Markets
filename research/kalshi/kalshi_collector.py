"""
kalshi_collector.py — public-API snapshot collector for Kalshi prediction markets.

S78 Kalshi pivot, Step 1 (KALSHI_BUILD_SCOPE.md). The crypto book-swing edge was a
fee-floor microstructure signal; Kalshi fits the stack better (direct news->outcome
coupling, wide books, Greg's energy/macro/weather domain edge). This collector is the
shared prerequisite for BOTH downstream threads:

  * news->contract COUPLING   (news_coupling_research.py reads the mid-probability series)
  * book-imbalance MICRO      (research/shape_s71/early_signal.book_imbalance reads bids/asks)
  * WEATHER via OD            (the full strike-ladder implied distribution to score an OD
                              forecast against; the crown-jewel edge — see KICKOFF_S78_KALSHI.md)

Public market data needs NO auth. We poll the v2 REST API and append one JSONL line per
(market, snapshot) into data/kalshi/<SERIES>_bins.jsonl — ONE FILE PER SERIES (not per
strike/day ticker) so the whole ladder's evolution for e.g. NYC daily-high lives together,
which is exactly what the weather-vs-implied-distribution test needs. Gzip on push (S37
lesson: >100MB files break git).

PRICES: Kalshi quotes in dollars (0.00-1.00). We store everything in CENTS (0-100) = the
implied probability, so `mid` is a probability-in-cents series directly.

BOOK TRANSFORM (binary market -> unified YES book): the /orderbook endpoint returns YES
bids (`yes`) and NO bids (`no`). A NO bid at price q is equivalent to a YES ask at (1-q).
So:  YES bids = yes-side;  YES asks = [(1-q, size) for NO bids].  This yields a standard
[[price_cents, size], ...] best-first book that early_signal.book_imbalance() consumes
unchanged.

Modes:
  --discover           enumerate open markets under the watchlist (ranked by liquidity) and
                       exit. The CHEAP GATE — confirm real depth before collecting for hours.
  (default) collect    poll every --interval s for --duration s; append JSONL per series.

Examples:
  python kalshi_collector.py --discover
  python kalshi_collector.py --duration 14400 --interval 5
  python kalshi_collector.py --series KXHIGHNY,KXHIGHLAX,KXCPIYOY --depth --duration 7200
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any, Optional

API_BASE = "https://api.elections.kalshi.com/trade-api/v2"

# --- Watchlist: where Greg has edge. Grouped by thesis. -----------------------------------
# Weather daily-HIGH-temp cities — the OD-weather settlement targets (settle on the exact
# NWS-reported daily high at a specific station -> an OD forecast keys on that same variable).
WEATHER_HIGH = [
    "KXHIGHNY",    # NYC (Central Park)
    "KXHIGHLAX",   # Los Angeles
    "KXHIGHCHI",   # Chicago
    "KXHIGHAUS",   # Austin
    "KXHIGHDEN",   # Denver
    "KXHIGHTHOU",  # Houston
    "KXHIGHTDAL",  # Dallas
    "KXHIGHTPHX",  # Phoenix
    "KXHIGHTATL",  # Atlanta
    "KXHIGHTBOS",  # Boston
    "KXHIGHTSFO",  # San Francisco
    "KXHIGHTSATX", # San Antonio
]
# Scheduled macro prints — clean news->outcome causal events (a release IS the contract input).
ECON = [
    "KXUSNFP",     # US nonfarm payrolls
    "KXCPIYOY",    # CPI YoY (inflation)
    "KXCPICOREA",  # Core CPI annual
    "PCECORE",     # Core PCE
    "KXFEDHIKE",   # Next Fed rate hike
    "RATECUTS",    # Number of rate cuts
    "KXEFFR",      # Fed funds (EFFR) over/under
]
DEFAULT_WATCHLIST = WEATHER_HIGH + ECON


# --- HTTP -----------------------------------------------------------------------------------
class RateLimitedClient:
    """Minimal urllib client with polite pacing + retry/backoff on 429/5xx."""

    def __init__(self, min_interval_s: float = 0.12, timeout_s: float = 25.0):
        self.min_interval_s = min_interval_s
        self.timeout_s = timeout_s
        self._last = 0.0

    def get(self, path: str, params: Optional[dict] = None, retries: int = 4) -> Optional[dict]:
        url = API_BASE + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        for attempt in range(retries + 1):
            wait = self.min_interval_s - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    self._last = time.time()
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                self._last = time.time()
                if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                    time.sleep(2.0 ** attempt)
                    continue
                if e.code == 404:
                    return None
                print(f"[kalshi] HTTP {e.code} on {path}: {e.reason}", flush=True)
                return None
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                if attempt < retries:
                    time.sleep(2.0 ** attempt)
                    continue
                print(f"[kalshi] net error on {path}: {e}", flush=True)
                return None
        return None


# --- parsing helpers ------------------------------------------------------------------------
def _f(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _cents(dollars: Any) -> Optional[float]:
    v = _f(dollars)
    return None if v is None else round(v * 100.0, 2)


def _levels_to_cents(levels: Any) -> list[list[float]]:
    """[[price_dollars, size], ...] -> [[price_cents, size], ...] (drops zero/invalid)."""
    out: list[list[float]] = []
    for lv in levels or []:
        if not isinstance(lv, (list, tuple)) or len(lv) < 2:
            continue
        p, s = _f(lv[0]), _f(lv[1])
        if p is None or s is None or s <= 0:
            continue
        out.append([round(p * 100.0, 2), s])
    return out


def unified_yes_book(ob: dict) -> tuple[list[list[float]], list[list[float]]]:
    """Kalshi binary orderbook -> unified YES book (bids, asks) in cents, best-first.

    YES bids  = yes-side bids.                       (best = highest price)
    YES asks  = NO bids reflected: (100 - q, size).  (best = lowest ask)
    """
    inner = ob.get("orderbook_fp") or ob.get("orderbook") or ob
    yes_raw = inner.get("yes_dollars") or inner.get("yes") or []
    no_raw = inner.get("no_dollars") or inner.get("no") or []

    yes_bids = _levels_to_cents(yes_raw)
    no_bids = _levels_to_cents(no_raw)
    yes_asks = [[round(100.0 - p, 2), s] for p, s in no_bids]

    yes_bids.sort(key=lambda x: x[0], reverse=True)  # best (highest) first
    yes_asks.sort(key=lambda x: x[0])                # best (lowest) first
    return yes_bids, yes_asks


def snapshot_from_market(m: dict) -> dict:
    """Metadata snapshot from a /markets ladder item. NOTE: for weather/econ ladders the
    item's top-of-book (yes_bid/ask) and liquidity_dollars are frequently NULL — the real
    live price only comes from /orderbook (see enrich_with_orderbook)."""
    last = _cents(m.get("last_price_dollars"))
    return {
        "ticker": m.get("ticker"),
        "event": m.get("event_ticker"),
        "status": m.get("status"),
        "strike_type": m.get("strike_type"),
        "floor_strike": m.get("floor_strike"),
        "subtitle": m.get("yes_sub_title") or m.get("subtitle"),
        "close_time": m.get("close_time"),
        "mid": None,
        "yes_bid": _cents(m.get("yes_bid_dollars")),
        "yes_ask": _cents(m.get("yes_ask_dollars")),
        "spread": None,
        "last": last,
        "volume_24h_fp": m.get("volume_24h_fp"),
        "volume_fp": m.get("volume_fp"),
        "open_interest_fp": m.get("open_interest_fp"),
        "liquidity_dollars": _f(m.get("liquidity_dollars")),
    }


def enrich_with_orderbook(client: "RateLimitedClient", snap: dict, keep_levels: int = 10) -> dict:
    """Pull /orderbook and set the LIVE mid/spread/book from it (the reliable price source).
    Stores the unified YES book (best-first, cents) that early_signal.book_imbalance() reads.
    Sets book_ok=True only when a 2-sided top-of-book exists."""
    snap["book_ok"] = False
    ob = client.get(f"/markets/{snap['ticker']}/orderbook", {"depth": keep_levels})
    if not ob:
        return snap
    bids, asks = unified_yes_book(ob)
    snap["bids"] = bids[:keep_levels]
    snap["asks"] = asks[:keep_levels]
    yb = bids[0][0] if bids else None
    ya = asks[0][0] if asks else None
    snap["yes_bid"] = yb
    snap["yes_ask"] = ya
    if yb is not None and ya is not None and ya >= yb:
        snap["mid"] = round(0.5 * (yb + ya), 2)
        snap["spread"] = round(ya - yb, 2)
        snap["book_ok"] = True
    elif ya is not None:              # one-sided (far-OTM strike): mark near the offered side
        snap["mid"] = ya
    elif yb is not None:
        snap["mid"] = yb
    elif snap.get("last") is not None:
        snap["mid"] = snap["last"]
    return snap


def select_active_markets(ms: list[dict], max_markets: int) -> list[dict]:
    """Pick the FRONT ladder(s): markets with the soonest close_time. Filters out far-dated
    clutter (e.g. KXCPIYOY has 100+ markets across many months; we want the next print)."""
    dated = [m for m in ms if m.get("close_time")]
    dated.sort(key=lambda m: m["close_time"])
    return (dated or ms)[:max_markets]


# --- I/O ------------------------------------------------------------------------------------
def append_jsonl(out_dir: str, series: str, rows: list[dict]) -> None:
    if not rows:
        return
    path = os.path.join(out_dir, f"{series}_bins.jsonl")
    with open(path, "a") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")


def gzip_file(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    gz = path + ".gz"
    with open(path, "rb") as fin, gzip.open(gz, "wb") as fout:
        fout.writelines(fin)
    return gz


# --- core -----------------------------------------------------------------------------------
def list_open_markets(client: RateLimitedClient, series: str, limit: int = 200) -> list[dict]:
    """All open markets under a series (the strike ladder), paginating."""
    markets: list[dict] = []
    cursor = None
    while True:
        params = {"series_ticker": series, "status": "open", "limit": min(limit, 200)}
        if cursor:
            params["cursor"] = cursor
        d = client.get("/markets", params)
        if not d:
            break
        markets.extend(d.get("markets", []))
        cursor = d.get("cursor")
        if not cursor or len(markets) >= limit:
            break
    return markets[:limit]


def discover(client: RateLimitedClient, watchlist: list[str], max_markets: int = 14) -> None:
    """Cheap gate: for each series, pull the FRONT ladder's live orderbooks and show the
    implied distribution (2-sided depth). Real depth is confirmed by book_ok, not the
    (often-null) liquidity_dollars field."""
    print(f"[discover] {len(watchlist)} series (live orderbook depth)\n" + "=" * 72, flush=True)
    grand = grand_2sided = 0
    for series in watchlist:
        ms = list_open_markets(client, series)
        active = select_active_markets(ms, max_markets)
        grand += len(ms)
        snaps = [enrich_with_orderbook(client, snapshot_from_market(m)) for m in active]
        two_sided = [s for s in snaps if s.get("book_ok")]
        grand_2sided += len(two_sided)
        print(f"\n{series}: {len(ms)} open | {len(active)} front | {len(two_sided)} two-sided", flush=True)
        for s in sorted(snaps, key=lambda x: x.get("close_time") or "")[:8]:
            flag = "OK " if s.get("book_ok") else "1sd"
            print(f"    [{flag}] {s['ticker']:<26} {str(s['subtitle'])[:16]:<16} "
                  f"mid={s['mid']} bid/ask={s['yes_bid']}/{s['yes_ask']} "
                  f"depth={len(s.get('bids', []))}/{len(s.get('asks', []))} close={s['close_time']}",
                  flush=True)
    print("\n" + "=" * 72
          + f"\n[discover] {grand} open markets; {grand_2sided} two-sided front-ladder books", flush=True)


def collect(client: RateLimitedClient, watchlist: list[str], duration_s: float,
            interval_s: float, out_dir: str, max_markets: int, keep_levels: int) -> None:
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    cycle = 0
    total_rows = total_ok = 0
    print(f"[collect] {len(watchlist)} series, interval={interval_s}s, duration={duration_s:.0f}s, "
          f"max_markets/series={max_markets} -> {out_dir}", flush=True)
    while time.time() - t0 < duration_s:
        cycle += 1
        ts = round(time.time(), 2)
        for series in watchlist:
            ms = list_open_markets(client, series)
            if not ms:
                continue
            active = select_active_markets(ms, max_markets)
            rows = []
            for m in active:
                snap = snapshot_from_market(m)
                snap["ts"] = ts
                snap["series"] = series
                snap["cycle"] = cycle
                enrich_with_orderbook(client, snap, keep_levels)   # live mid + unified YES book
                rows.append(snap)
                if snap.get("book_ok"):
                    total_ok += 1
            append_jsonl(out_dir, series, rows)
            total_rows += len(rows)
        el = time.time() - t0
        print(f"[collect] cycle={cycle} t={el:.0f}s rows={total_rows} two_sided={total_ok}", flush=True)
        sleep = interval_s - ((time.time() - t0) % interval_s)
        if time.time() - t0 + sleep < duration_s:
            time.sleep(max(0.0, sleep))
        else:
            break
    print(f"[collect] done: {cycle} cycles, {total_rows} rows ({total_ok} two-sided) -> {out_dir}",
          flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description="Kalshi public-API snapshot collector (S78 Step 1)")
    p.add_argument("--series", default="", help="comma-separated series tickers (default: built-in watchlist)")
    p.add_argument("--discover", action="store_true", help="list open markets per series + liquidity, then exit")
    p.add_argument("--duration", type=float, default=14400.0, help="collect seconds (default 4h)")
    p.add_argument("--interval", type=float, default=30.0, help="poll interval seconds (Kalshi books move slowly)")
    p.add_argument("--max-markets", type=int, default=20, help="front-ladder markets per series (soonest close)")
    p.add_argument("--keep-levels", type=int, default=10, help="book levels to store per side")
    p.add_argument("--out-dir", default="data/kalshi", help="output dir for <SERIES>_bins.jsonl")
    p.add_argument("--min-interval", type=float, default=0.12, help="min seconds between HTTP requests")
    args = p.parse_args()

    watchlist = [s.strip() for s in args.series.split(",") if s.strip()] or DEFAULT_WATCHLIST
    client = RateLimitedClient(min_interval_s=args.min_interval)

    if args.discover:
        discover(client, watchlist)
        return
    collect(client, watchlist, args.duration, args.interval, args.out_dir,
            args.max_markets, args.keep_levels)


if __name__ == "__main__":
    main()
