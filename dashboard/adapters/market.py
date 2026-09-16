"""Market-data adapter: Kalshi raw stores (S3 kalshi/ -> data/kalshi) and the NYMEX
continuous tape (S3 nymex/nymex_cont -> data/nymex_cont) for the leader/follower chart.

Kalshi candle files carry TWO schema vintages (close vs close_dollars) - both handled,
per DASHBOARD_HANDOFF. KXNATGASD skips Fridays; absent days are shown absent, never
interpolated. NYMEX loading reuses the signal core's own reader (read-only import) so
the dashboard can never drift from the canonical normalization.
"""
from __future__ import annotations

import glob
import gzip
import json
import os
import re
import sys

from . import paths

KALSHI_DIR = os.path.join(paths.DATA, "kalshi")
NYMEX_CONT = os.path.join(paths.DATA, "nymex_cont")
SERIES = "KXNATGASD"


def _emb():
    for p in (paths.REPO, paths.KALSHI_RESEARCH):
        if p not in sys.path:
            sys.path.insert(0, p)
    import event_move_baseline
    return event_move_baseline


def kalshi_available() -> bool:
    return os.path.isdir(os.path.join(KALSHI_DIR, "trades", SERIES)) or \
        os.path.isdir(os.path.join(KALSHI_DIR, "candles", SERIES))


def list_event_days() -> dict:
    """Event tickers with a trades file present locally, newest last."""
    pat = os.path.join(KALSHI_DIR, "trades", SERIES, "*_trades.jsonl.gz")
    tickers = sorted(os.path.basename(p).split("_trades")[0] for p in glob.glob(pat))
    if not tickers:
        return {"available": False,
                "reason": "data/kalshi absent - platform_sync pull --prefix kalshi/ first"}
    return {"available": True, "series": SERIES, "n": len(tickers), "event_tickers": tickers}


_MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
           "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}


def event_day_iso(event_ticker: str) -> str | None:
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})", event_ticker)
    if not m:
        return None
    yy, mon, dd = m.groups()
    return f"20{yy}-{_MONTHS[mon]:02d}-{int(dd):02d}"


def _strike(ticker: str) -> float | None:
    m = re.search(r"-T(\d+(?:\.\d+)?)$", ticker)
    return float(m.group(1)) if m else None


def _candle_close(side: dict) -> float | None:
    """Two store vintages: close (cents on old files? carried raw) vs close_dollars."""
    if not isinstance(side, dict):
        return None
    v = side.get("close", side.get("close_dollars"))
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def kalshi_day_candles(event_ticker: str) -> dict:
    """Per-bracket 1m mid series for one event day: {strike: [[end_ts, mid, bid, ask], ...]}."""
    d = os.path.join(KALSHI_DIR, "candles", SERIES)
    if not os.path.isdir(d):
        return {"available": False, "reason": "data/kalshi/candles absent"}
    out = {}
    for path in sorted(glob.glob(os.path.join(d, f"{event_ticker}*_candles_1m.jsonl.gz"))):
        ticker = os.path.basename(path).split("_candles")[0]
        strike = _strike(ticker)
        if strike is None:
            continue
        series = []
        with gzip.open(path, "rt") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                bid = _candle_close(r.get("yes_bid", {}))
                ask = _candle_close(r.get("yes_ask", {}))
                if bid is None or ask is None:
                    continue
                series.append([int(r["end_period_ts"]), round((bid + ask) / 2, 4), bid, ask])
        if series:
            out[str(strike)] = series
    if not out:
        return {"available": False, "reason": f"no candle files for {event_ticker}"}
    return {"available": True, "event_ticker": event_ticker,
            "day": event_day_iso(event_ticker), "brackets": out}


def nymex_available_days(root: str = "NG") -> list[str]:
    pat = os.path.join(NYMEX_CONT, f"{root}_*.jsonl.gz")
    days = []
    for p in glob.glob(pat):
        m = re.search(rf"{root}_(\d{{8}})", os.path.basename(p))
        if m:
            days.append(m.group(1))
    return sorted(set(days))


_BARS_CACHE: dict[tuple, dict] = {}


def nymex_minute_bars(day8: str, root: str = "NG") -> dict:
    """1-minute last-trade bars from the canonical continuous-day reader (local cache only;
    the dashboard does not pull tape from S3 on-request - that is a deliberate cost gate).
    Parsed once per (root, day) per process - the raw day is ~100k+ ticks."""
    if (root, day8) in _BARS_CACHE:
        return _BARS_CACHE[(root, day8)]
    if day8 not in nymex_available_days(root):
        return {"available": False, "day": day8,
                "reason": f"data/nymex_cont/{root}_{day8}*.jsonl.gz absent locally "
                          "(tape stays on S3; pull deliberately, it is large)"}
    cwd = os.getcwd()
    try:
        os.chdir(paths.REPO)
        emb = _emb()
        arrs = emb.load_cont_day(root, day8, source="local")
    finally:
        os.chdir(cwd)
    ts, px = arrs.get("ts"), arrs.get("price")
    if ts is None or len(ts) == 0:
        return {"available": False, "day": day8, "reason": "empty tape"}
    bars = {}
    for t, p in zip(ts, px):
        bars[int(t // 60 * 60)] = float(p)   # last print in the minute wins
    series = [[k, round(v, 4)] for k, v in sorted(bars.items())]
    out = {"available": True, "day": day8, "root": root,
           "n_ticks": int(len(ts)), "n_minutes": len(series), "bars": series}
    _BARS_CACHE[(root, day8)] = out
    return out
