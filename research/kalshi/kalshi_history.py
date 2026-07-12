"""
kalshi_history.py — pull HISTORICAL Kalshi trade + candlestick data around past scheduled releases.

The unblock (S80): the release-triggered signal test needs order-flow spanning a real release. Instead
of waiting for live accrual + the next Thursday, Kalshi's PUBLIC API serves history:
  * /markets?status=settled           -> enumerate the exact strike ladder that was live at a past release.
  * /markets/trades  (per ticker)     -> every trade with `taker_side` (yes/no) = SIGNED taker flow —
                                         exactly the info_dipole buy/sell channels, on REAL data.
  * /series/{s}/markets/{t}/candlesticks -> per-interval price + top-of-book (yes_bid/yes_ask) OHLC +
                                         volume + open_interest = the probability series.

Liquidity survey (settled events, total volume): WTI crude ~1.2M/event x46 events; CPI y/y ~0.94M x2;
natgas price ~0.2M x13; Fed ~1.0M; NFP ~0.06M x2. WTI + CPI are the liquid multi-release samples.

Stores per (series,event) to data/kalshi_hist_trades/<series>/<event>_{trades,candles}.jsonl (LOCAL,
gitignored — market data lives local, `markets-data-lives-local-not-git`). No auth (public data). Zero
synthetic data.

Usage:
    # list settled events for a series (with volume), newest first
    python research/kalshi/kalshi_history.py --series KXWTI --list
    # pull ALL strikes of one event's ladder (trades + candles) into the local store
    python research/kalshi/kalshi_history.py --series KXWTI --event KXWTI-26MAY06
    # pull the top-N most-liquid strikes only
    python research/kalshi/kalshi_history.py --series KXNATGASD --event KXNATGASD-26JUN2517 --top 20
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from collections import defaultdict

BASE = "https://api.elections.kalshi.com/trade-api/v2"
STORE = "data/kalshi_hist_trades"
_MIN_INTERVAL = 0.12
_last = [0.0]


def _get(path: str, **params) -> dict:
    dt = time.time() - _last[0]
    if dt < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - dt)
    q = "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}) if params else ""
    for attempt in range(5):
        try:
            req = urllib.request.Request(BASE + path + q, headers={"User-Agent": "Mozilla/5.0"})
            r = json.loads(urllib.request.urlopen(req, timeout=30).read())
            _last[0] = time.time()
            return r
        except Exception:
            if attempt == 4:
                raise
            time.sleep(1.5 * (attempt + 1))
    return {}


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ---- enumeration ---------------------------------------------------------------------------
def list_settled_markets(series: str, cap: int = 2000) -> list[dict]:
    out, cur = [], None
    while len(out) < cap:
        d = _get("/markets", series_ticker=series, status="settled", limit=200, cursor=cur)
        out += d.get("markets", [])
        cur = d.get("cursor")
        if not cur:
            break
    return out


def events_by_volume(series: str) -> list[tuple[str, int, float, str]]:
    """(event_ticker, n_strikes, total_volume, latest_close) sorted by volume desc."""
    ms = list_settled_markets(series)
    ev = defaultdict(lambda: [0, 0.0, ""])
    for m in ms:
        e = m.get("event_ticker", "?")
        ev[e][0] += 1
        ev[e][1] += _num(m.get("volume_fp") or m.get("volume")) or 0.0
        ct = m.get("close_time", "") or ""
        if ct > ev[e][2]:
            ev[e][2] = ct
    rows = [(e, n, v, c) for e, (n, v, c) in ev.items()]
    rows.sort(key=lambda r: -r[2])
    return rows


def event_strikes(series: str, event: str) -> list[dict]:
    return [m for m in list_settled_markets(series) if m.get("event_ticker") == event]


# ---- per-contract history ------------------------------------------------------------------
def fetch_trades(ticker: str, min_ts: int | None = None, max_ts: int | None = None,
                 cap: int = 50000) -> list[dict]:
    """All trades for a ticker (paginated). Row: {ts, yes_price, count, taker_side}. taker_side is the
    aggressor: 'yes' = taker LIFTED the YES offer (buy pressure), 'no' = taker HIT the YES bid (sell)."""
    out, cur = [], None
    while len(out) < cap:
        d = _get("/markets/trades", ticker=ticker, min_ts=min_ts, max_ts=max_ts, limit=1000, cursor=cur)
        for t in d.get("trades", []):
            yp = _num(t.get("yes_price_dollars"))
            out.append({"ts": t.get("created_time"),
                        "yes_price": None if yp is None else round(yp * 100.0, 2),  # cents == prob*100
                        "count": _num(t.get("count_fp")) or 0.0,
                        "taker_side": t.get("taker_side")})
        cur = d.get("cursor")
        if not cur:
            break
    out.sort(key=lambda r: r["ts"] or "")
    return out


def _ohlc(node) -> dict | None:
    if not isinstance(node, dict) or not node:
        return None
    g = lambda k: _num(node.get(k))
    return {"o": g("open_dollars"), "h": g("high_dollars"), "l": g("low_dollars"), "c": g("close_dollars")}


def fetch_candles(series: str, ticker: str, start_ts: int, end_ts: int,
                  period_interval: int = 1) -> list[dict]:
    """Candlesticks (period_interval minutes). Row: {ts, price_ohlc, yes_bid_ohlc, yes_ask_ohlc, vol, oi}.

    The API caps 5000 candlesticks/request, so chunk the range; best-effort (a failed chunk is skipped —
    candles are the secondary series; trades carry the primary signed flow)."""
    span = int(4500 * period_interval * 60)               # <5000-candle safety window per request
    out = []
    lo = start_ts
    while lo < end_ts:
        hi = min(lo + span, end_ts)
        try:
            d = _get(f"/series/{series}/markets/{ticker}/candlesticks",
                     start_ts=lo, end_ts=hi, period_interval=period_interval)
            for c in d.get("candlesticks", []):
                out.append({"ts": c.get("end_period_ts"),
                            "price": _ohlc(c.get("price")),
                            "yes_bid": _ohlc(c.get("yes_bid")), "yes_ask": _ohlc(c.get("yes_ask")),
                            "vol": _num(c.get("volume_fp")) or 0.0,
                            "oi": _num(c.get("open_interest_fp")) or 0.0})
        except Exception:
            pass                                          # skip the chunk; keep going
        lo = hi
    out.sort(key=lambda r: r["ts"] or 0)
    return out


# ---- pull + store --------------------------------------------------------------------------
def _write_jsonl(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")


def pull_event(series: str, event: str, top: int | None, candle_interval: int,
               candle_days: int) -> dict:
    strikes = event_strikes(series, event)
    if not strikes:
        return {"event": event, "status": "NO_STRIKES"}
    strikes.sort(key=lambda m: -(_num(m.get("volume_fp") or m.get("volume")) or 0.0))
    if top:
        strikes = strikes[:top]
    outdir = os.path.join(STORE, series)
    tr_path = os.path.join(outdir, f"{event}_trades.jsonl")
    cd_path = os.path.join(outdir, f"{event}_candles.jsonl")
    all_trades, all_candles = [], []
    now = int(time.time())
    start = now - candle_days * 86400
    summary = []
    for m in strikes:
        tk = m["ticker"]
        tr = fetch_trades(tk)
        cd = fetch_candles(series, tk, start, now, candle_interval)
        for r in tr:
            r["ticker"] = tk
        for r in cd:
            r["ticker"] = tk
        all_trades += tr
        all_candles += cd
        buy = sum(r["count"] for r in tr if r["taker_side"] == "yes")
        sell = sum(r["count"] for r in tr if r["taker_side"] == "no")
        summary.append({"ticker": tk, "n_trades": len(tr), "buy_ct": buy, "sell_ct": sell,
                        "n_candles": len(cd), "close": m.get("close_time")})
    _write_jsonl(tr_path, all_trades)
    _write_jsonl(cd_path, all_candles)
    return {"event": event, "status": "OK", "n_strikes": len(strikes),
            "n_trades": len(all_trades), "n_candles": len(all_candles),
            "trades_path": tr_path, "candles_path": cd_path, "per_strike": summary}


def main() -> None:
    ap = argparse.ArgumentParser(description="Historical Kalshi trades+candlesticks puller (S80)")
    ap.add_argument("--series", required=True)
    ap.add_argument("--list", action="store_true", help="list settled events by volume, then exit")
    ap.add_argument("--event", default=None, help="event_ticker to pull (a release's strike ladder)")
    ap.add_argument("--top", type=int, default=None, help="pull only the N most-liquid strikes")
    ap.add_argument("--candle-interval", type=int, default=1, help="candlestick minutes (1/60/1440)")
    ap.add_argument("--candle-days", type=int, default=30, help="candlestick lookback days")
    args = ap.parse_args()

    if args.list or not args.event:
        rows = events_by_volume(args.series)
        print(f"[{args.series}] {len(rows)} settled events (by total volume):")
        for e, n, v, c in rows[:25]:
            print(f"    {e:<26} strikes={n:<3} vol={v:>11.0f} latest_close={c[:16]}")
        if not args.event:
            return

    res = pull_event(args.series, args.event, args.top, args.candle_interval, args.candle_days)
    print(f"[pull] {res['event']}: {res['status']}", flush=True)
    if res["status"] == "OK":
        print(f"    strikes={res['n_strikes']} trades={res['n_trades']} candles={res['n_candles']}")
        print(f"    -> {res['trades_path']}  +  {res['candles_path']}")
        for s in sorted(res["per_strike"], key=lambda x: -x["n_trades"])[:8]:
            print(f"      {s['ticker']:<26} trades={s['n_trades']:<5} buy={s['buy_ct']:.0f} "
                  f"sell={s['sell_ct']:.0f} candles={s['n_candles']}")


if __name__ == "__main__":
    main()
