#!/usr/bin/env python3
"""FEED M part 1 (S100, DATA_GATE_S98) - the lag's NG-specific EXECUTION SHAPE on the KXNATGASD
life (2026-03-30 -> present). PER-EVENT characterization, never pooled as a conclusion; this is a
fill-tradeoff MAP (which brackets respond when, and how far), NOT a significance test - the lag
itself is ESTABLISHED (gate 0c) and never re-litigated.

Per NYMEX front-month move event: for every bracket with same-day Kalshi activity, the
delay-to-first-Kalshi-trade after the event, and the bracket's candle-mid change at +1m/+5m,
tagged by moneyness band, time-of-day, and move class. 1-sec-or-finer NYMEX readouts are LOWER
BOUNDS on the move (standing rule); Kalshi trade stamps are ms.

Blind/exclusion discipline: NYMEX settle window 14:00-14:30 ET EXCLUDED (standing); events at/after
16:30 ET flagged `near_bracket_settle` (the bracket's own 17:00 EDT settle mechanics - S99
verified). Characterization only - no strategy, no leakage surface (no forecast is being scored).

Event definition (stated, fixed per the MEASURED life regime, not tuned to any outcome): a move
event fires when the front price travels >= MOVE_MIN_C cents from its trailing-WINDOW_S anchor
extreme; t0 = the crossing trade's ts; non-overlapping (cooldown). REGIME NOTE (measured
2026-07-20 before setting these): the life (Apr-Jul 2026) is the spring low-vol regime - the most
active day (Jul 7, 11c session range) shows max 60s travel 1.8c and max 300s travel 3.0c, so the
winter-scale 2c/60s definition fires ZERO events across the life. Definition: 1.5c within 300s;
classes 1.5-2.5c / 2.5-4c / >=4c. The fee wall (~1.75c taker at midprob + spread) sits INSIDE the
smallest class - which is exactly the size-vs-fee reality the map exists to expose.

Store: data/kalshi_echo/lag_map.jsonl (one row per event x bracket) + per-day day rows. NYMEX day
caches are DELETED after each day (disk allowance).
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import event_move_baseline as emb
from kalshi_fill_model import kalshi_dir

ET = ZoneInfo("America/New_York")
MOVE_MIN_C = 1.5                 # cents; regime-derived floor (see docstring)
WINDOW_S = 300.0
COOLDOWN_S = 300.0
SESSION_ET = (8, 16)             # characterize the US session 08:00-16:00 ET (settle excl. below)
SETTLE_EXCL_ET = (14.0, 14.5)    # standing NYMEX settle-window exclusion
NEAR_BRACKET_SETTLE_ET = 16.5
MONEYNESS_BANDS_C = [(0, 3, "ATM"), (3, 8, "NEAR"), (8, 10000, "FAR")]
OUT_DIR_CANDIDATES = [os.path.join(HERE, "..", "..", "data", "kalshi_echo"),
                      os.path.join("data", "kalshi_echo")]


def _out_dir() -> str:
    for p in OUT_DIR_CANDIDATES:
        parent = os.path.dirname(p)
        if os.path.isdir(parent):
            os.makedirs(p, exist_ok=True)
            return p
    os.makedirs(OUT_DIR_CANDIDATES[0], exist_ok=True)
    return OUT_DIR_CANDIDATES[0]


MON = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
       "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}


def event_day_from_ticker(event_ticker: str) -> str:
    """KXNATGASD-26APR2217 -> 2026-04-22 (the trailing '17' is the 17:00 EDT close hour)."""
    tail = event_ticker.split("-")[1]
    yy = int(tail[:2]); mon = MON[tail[2:5]]; dd = int(tail[5:7])
    return f"20{yy:02d}-{mon:02d}-{dd:02d}"


def strike_from_ticker(ticker: str) -> float | None:
    for part in ticker.split("-"):
        if part.startswith("T"):
            try:
                return float(part[1:])
            except ValueError:
                return None
    return None


def _et_hours(ts_utc_s: np.ndarray, day_iso: str) -> np.ndarray:
    """ET decimal hour for an array of UTC epoch seconds (DST-correct via one reference offset per
    day - the walk window never crosses a DST boundary INSIDE a session)."""
    ref = datetime.fromtimestamp(float(ts_utc_s[0]), tz=timezone.utc).astimezone(ET)
    off = ref.utcoffset().total_seconds() / 3600.0
    h = (ts_utc_s % 86400) / 3600.0 + off
    return np.mod(h, 24.0)


def nymex_move_events(day8: str) -> tuple[list[dict], float]:
    """Move events from the S3 continuous NG day. Returns (events, ts_unit_divisor_applied)."""
    d = emb.load_cont_day("NG", day8, source="s3")
    ts = d["ts"]; px = d["price"]
    if ts.size == 0:
        return [], 1.0
    # ts units: normalize to SECONDS (raw is ns if > 1e14)
    div = 1e9 if ts[0] > 1e14 else 1.0
    t = ts / div
    eth = _et_hours(t, day8)
    m = (eth >= SESSION_ET[0]) & (eth < SESSION_ET[1])
    t, px, eth = t[m], px[m], eth[m]
    events = []
    i = 0
    n = len(t)
    while i < n:
        # trailing-60s anchor extremes ending at i
        j0 = np.searchsorted(t, t[i] - WINDOW_S)
        window = px[j0:i + 1]
        if window.size:
            up_move = (px[i] - window.min()) * 100.0
            dn_move = (window.max() - px[i]) * 100.0
            mv = up_move if up_move >= dn_move else -dn_move
            if abs(mv) >= MOVE_MIN_C:
                et_h = float(eth[i])
                if not (SETTLE_EXCL_ET[0] <= et_h < SETTLE_EXCL_ET[1]):
                    size_c = abs(mv)
                    cls = "1.5-2.5c" if size_c < 2.5 else ("2.5-4c" if size_c < 4 else ">=4c")
                    events.append({"t0": float(t[i]), "et_hour": round(et_h, 3),
                                   "dir": int(np.sign(mv)), "size_c": round(size_c, 2),
                                   "cls": cls, "nymex_px": float(px[i]),
                                   "near_bracket_settle": bool(et_h >= NEAR_BRACKET_SETTLE_ET)})
                # skip cooldown either way (excluded-window crossings also reset the anchor)
                i = int(np.searchsorted(t, t[i] + COOLDOWN_S))
                continue
        i += 1
    return events, div


def load_kalshi_day(event_ticker: str) -> tuple[dict, dict]:
    """(trades_by_strike, candles_by_strike) for one event day. trades: sorted [t_s, yes_price];
    candles: {minute_ts: (bid_close, ask_close)}."""
    kd = kalshi_dir()
    tpath = os.path.join(kd, "trades", "KXNATGASD", f"{event_ticker}_trades.jsonl.gz")
    cpath = os.path.join(kd, "candles", "KXNATGASD", f"{event_ticker}_candles_1m.jsonl.gz")
    trades = defaultdict(list)
    with gzip.open(tpath, "rt") as fh:
        for line in fh:
            r = json.loads(line)
            k = strike_from_ticker(r["ticker"])
            if k is None:
                continue
            ts = datetime.fromisoformat(r["created_time"].replace("Z", "+00:00")).timestamp()
            yp = r.get("yes_price_dollars")
            if yp is None and r.get("no_price_dollars") is not None:
                yp = 1.0 - float(r["no_price_dollars"])
            trades[k].append((ts, float(yp) if yp is not None else None))
    candles = defaultdict(dict)
    if os.path.exists(cpath):
        with gzip.open(cpath, "rt") as fh:
            for line in fh:
                r = json.loads(line)
                k = strike_from_ticker(r.get("ticker", "")) if "ticker" in r else None
                try:
                    yb, ya = r["yes_bid"], r["yes_ask"]
                    bid = float(yb.get("close", yb.get("close_dollars")))
                    ask = float(ya.get("close", ya.get("close_dollars")))
                except (KeyError, TypeError, ValueError):
                    continue                                  # two store vintages: close / close_dollars
                candles[k][int(r["end_period_ts"])] = (bid, ask)
    for k in trades:
        trades[k].sort()
    return dict(trades), {k: v for k, v in candles.items()}


def _moneyness_band(dist_c: float) -> str:
    for lo, hi, name in MONEYNESS_BANDS_C:
        if lo <= dist_c < hi:
            return name
    return "FAR"


def characterize_day(event_ticker: str, verbose: bool = False) -> list[dict]:
    day_iso = event_day_from_ticker(event_ticker)
    day8 = day_iso.replace("-", "")
    trades, candles = load_kalshi_day(event_ticker)
    if not trades:
        return []
    events, _ = nymex_move_events(day8)
    rows = []
    for ev in events:
        for strike, tl in trades.items():
            dist_c = abs(strike - ev["nymex_px"]) * 100.0
            band = _moneyness_band(dist_c)
            ts_arr = np.array([x[0] for x in tl])
            # delay to first Kalshi trade in this bracket AFTER the event
            k = int(np.searchsorted(ts_arr, ev["t0"]))
            delay_s = (float(ts_arr[k] - ev["t0"]) if k < len(ts_arr) else None)
            if delay_s is not None and delay_s > 600.0:
                delay_s = None                                   # no response within 10 min
            # candle mid response at +1m / +5m vs the event minute (per-bracket candles)
            cnd = candles.get(strike, {})
            m0 = int(ev["t0"] // 60 * 60) + 60                   # end_period_ts of the event minute
            mid = {}
            for lbl, mts in (("m0", m0), ("m1", m0 + 60), ("m5", m0 + 300)):
                ba = cnd.get(mts)
                mid[lbl] = (None if ba is None else (ba[0] + ba[1]) / 2.0)
            # sign convention: yes(settle>=strike) rises when the futures rise, for EVERY strike -
            # so dmid_*_signed = (mid change) * nymex dir; positive = bracket moved WITH the move
            dmid1 = (None if mid["m0"] is None or mid["m1"] is None
                     else round((mid["m1"] - mid["m0"]) * ev["dir"], 4))
            dmid5 = (None if mid["m0"] is None or mid["m5"] is None
                     else round((mid["m5"] - mid["m0"]) * ev["dir"], 4))
            rows.append({"day": day_iso, "event_ticker": event_ticker, "strike": strike,
                         "t0": ev["t0"], "et_hour": ev["et_hour"], "cls": ev["cls"],
                         "dir": ev["dir"], "size_c": ev["size_c"],
                         "moneyness_c": round(dist_c, 1), "band": band,
                         "delay_s": (round(delay_s, 3) if delay_s is not None else None),
                         "dmid_1m_signed": dmid1, "dmid_5m_signed": dmid5,
                         "near_bracket_settle": ev["near_bracket_settle"]})
    if verbose:
        resp = [r for r in rows if r["delay_s"] is not None]
        med = (sorted(r["delay_s"] for r in resp)[len(resp) // 2] if resp else None)
        print(f"[lag-map] {day_iso}: {len(events)} nymex events x {len(trades)} brackets -> "
              f"{len(rows)} rows, {len(resp)} responded, median delay "
              f"{med if med is None else round(med, 1)}s", flush=True)
    return rows


def run(limit: int | None = None) -> None:
    kd = kalshi_dir()
    days = sorted(os.path.basename(p).split("_trades")[0]
                  for p in glob.glob(os.path.join(kd, "trades", "KXNATGASD", "*_trades.jsonl.gz")))
    if limit:
        days = days[:limit]
    out_path = os.path.join(_out_dir(), "lag_map.jsonl")
    done = set()
    if os.path.exists(out_path):
        with open(out_path) as fh:
            for line in fh:
                try:
                    done.add(json.loads(line)["event_ticker"])
                except Exception:
                    pass
    with open(out_path, "a") as fh:
        for et in days:
            if et in done:
                continue
            try:
                rows = characterize_day(et, verbose=True)
            except FileNotFoundError as e:
                print(f"[lag-map] {et}: NYMEX day missing ({e}) - named gap, skipped", flush=True)
                continue
            for r in rows:
                fh.write(json.dumps(r) + "\n")
            fh.flush()
            # disk discipline: drop the cached NYMEX day
            day8 = event_day_from_ticker(et).replace("-", "")
            for p in glob.glob(os.path.join(HERE, "..", "..", "data", "nymex_cont", f"NG_{day8}*")):
                os.remove(p)
    print(f"[lag-map] store: {out_path}")


def summarize() -> None:
    """Distributions per (band x cls x tod bucket) - DESCRIPTORS of the map, per-cell, never a
    pooled verdict. Printed for the notes doc + the two-coach spec."""
    out_path = os.path.join(_out_dir(), "lag_map.jsonl")
    rows = [json.loads(l) for l in open(out_path)]
    rows = [r for r in rows if not r["near_bracket_settle"]]
    cells = defaultdict(list)
    for r in rows:
        if r["delay_s"] is not None:
            tod = "am" if r["et_hour"] < 12 else "pm"
            cells[(r["band"], r["cls"], tod)].append(r["delay_s"])
    print(f"[lag-map] {len(rows)} rows (settle-adjacent excluded); responded cells:")
    for key in sorted(cells):
        v = sorted(cells[key])
        n = len(v)
        print(f"  {key[0]:4s} {key[1]:6s} {key[2]}: n={n:5d} delay_s min={v[0]:.1f} "
              f"med={v[n // 2]:.1f} p90={v[int(n * .9)]:.1f}")
    # response-rate per band (responded within 10 min / all rows), a fill-reality descriptor
    for band in ("ATM", "NEAR", "FAR"):
        b = [r for r in rows if r["band"] == band]
        resp = [r for r in b if r["delay_s"] is not None]
        print(f"  response-rate {band}: {len(resp)}/{len(b)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("run"); r.add_argument("--limit", type=int, default=None)
    sub.add_parser("summarize")
    o = sub.add_parser("one"); o.add_argument("ticker")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.limit); return 0
    if a.cmd == "summarize":
        summarize(); return 0
    if a.cmd == "one":
        rows = characterize_day(a.ticker, verbose=True)
        for x in rows[:10]:
            print(json.dumps(x))
        return 0
    ap.print_help(); return 0


if __name__ == "__main__":
    sys.exit(main())
