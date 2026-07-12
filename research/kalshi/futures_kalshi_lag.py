"""
futures_kalshi_lag.py — measure the LAG between the futures market (the price-discovery venue) and
Kalshi's contract books (the venue we trade), per contract.

The question (Greg, S80): Kalshi's energy binaries are re-quoted off NYMEX/ICE by a handful of
makers. Is there a measurable delay between a futures move and the Kalshi re-price — and how big?
If futures LEAD by N bars, we can read the present faster than the venue re-prices it (entry-quality
edge; the reprice alone can pay the spread+fee toll).

Method: for each Kalshi contract (strike x day) with enough trades, build a 1-min last-trade
probability series on the same minute grid as the futures 1-min closes; DIFF both (changes, not
levels — levels correlate spuriously through shared trend); run odcore.leadlag.detect_leadlag
(raw cross-correlation over lags + time-slide null z — the S19/INFO-066 operator). Convention:
a = futures returns, b = Kalshi prob changes -> peak lag > 0 means FUTURES LEAD by that many bars.

Discipline: per-contract reads, never pooled into one average lag; the summary is the DISTRIBUTION
of per-contract peak lags (each contract keeps its own row). The daily-settlement convergence window
is excluded (mechanical snap to 0/100, not re-pricing). Zero synthetic data.

RESULT (first run, 2026-07-12; KXWTI Jul 6-10 x CL=F Yahoo 1m): 41 contracts measured, 15 significant
at z>=3 vs the time-slide null. Peak-lag histogram (significant): {0: 6, +1min: 8, +5: 1}. EVERY
significant contract has lag >= 0 — futures lead or synchronous, Kalshi NEVER leads (the one-way
causality confirmed in data). ~half re-price a full MINUTE late (incl. busy strikes, 400+ updates/day);
the lag-0 half may still lag sub-minute (invisible at 1m bars — finer futures data, e.g. Pyth, to pin).

Usage:
    python research/kalshi/futures_kalshi_lag.py --series KXWTI --fetch CL=F --out lag_report.json
    python research/kalshi/futures_kalshi_lag.py --series KXWTI \
        --futures-json <path to [{ts, close}, ...] 1-min bars> --out lag_report.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, _ROOT)
from odcore.leadlag import detect_leadlag                  # noqa: E402
from release_signal_history import (load_event_trades, event_date, SETTLE_UTC)  # noqa: E402

STORE = "data/kalshi_hist_trades"


def fetch_yahoo_1m(symbol: str, out_path: str) -> str:
    """Fetch ~7d of 1-min bars for a futures symbol (CL=F, NG=F, BZ=F) -> [{ts, close}] JSON."""
    import urllib.parse
    import urllib.request
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(symbol)}?interval=1m&range=7d")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    d = json.loads(urllib.request.urlopen(req, timeout=30).read())
    res = d["chart"]["result"][0]
    rows = [{"ts": t, "close": c} for t, c in
            zip(res["timestamp"], res["indicators"]["quote"][0]["close"]) if c is not None]
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    json.dump(rows, open(out_path, "w"))
    return out_path


def minute_grid_prob(trades: list[dict], t0: int, t1: int):
    """Last-trade Kalshi probability per minute on [t0, t1) (ffill); returns (minutes, prob, fresh)
    where fresh[i]=True if a real trade landed in minute i (vs carried forward)."""
    nb = (t1 - t0) // 60
    prob = np.full(nb, np.nan)
    fresh = np.zeros(nb, bool)
    for tr in trades:
        b = int((tr["ts"] - t0) // 60)
        if 0 <= b < nb:
            prob[b] = tr["price"]
            fresh[b] = True
    last = np.nan
    for i in range(nb):
        if np.isnan(prob[i]):
            prob[i] = last
        else:
            last = prob[i]
    minutes = t0 + 60 * np.arange(nb)
    return minutes, prob, fresh


def run(series: str, futures_json: str, min_trades: int, max_lag: int) -> dict:
    fut = json.load(open(futures_json))
    fmap = {int(r["ts"]) // 60 * 60: float(r["close"]) for r in fut}
    f_lo, f_hi = min(fmap), max(fmap)
    shh, smm = SETTLE_UTC.get(series, (21, 0))

    rows = []
    for path in sorted(glob.glob(os.path.join(STORE, series, "*_trades.jsonl"))):
        event = os.path.basename(path).replace("_trades.jsonl", "")
        ed = event_date(event)
        if ed is None:
            continue
        settle_ts = int(ed.replace(hour=shh, minute=smm).timestamp())
        cutoff = settle_ts - 1800                      # exclude the mechanical settle convergence
        by_tk = load_event_trades(series, event)
        for tk, trades in by_tk.items():
            if len(trades) < min_trades:
                continue
            t0 = max(int(trades[0]["ts"] // 60 * 60), f_lo)
            t1 = min(int(trades[-1]["ts"] // 60 * 60), f_hi, cutoff)
            if t1 - t0 < 120 * 60:                     # need >= 2h of overlap
                continue
            minutes, prob, fresh = minute_grid_prob(trades, t0, t1)
            fut_px = np.array([fmap.get(int(m), np.nan) for m in minutes])
            # keep minutes where both series exist
            ok = ~np.isnan(prob) & ~np.isnan(fut_px)
            if ok.sum() < 90:
                continue
            p = prob[ok]; f = fut_px[ok]
            dp = np.diff(p); df = np.diff(f)
            if np.count_nonzero(dp) < 12:              # Kalshi must actually re-price sometimes
                continue
            r = detect_leadlag(df, dp, max_lag=max_lag, n_null=200, seed=0)
            rows.append({"event": event, "ticker": tk, "date": ed.date().isoformat(),
                         "n_min": int(ok.sum()), "n_kalshi_updates": int(np.count_nonzero(dp)),
                         "n_trades": len(trades),
                         "peak_lag_min": r.lag, "cc": round(r.cc, 3), "z": round(r.z, 2),
                         "leader": {"a": "futures", "b": "kalshi"}.get(r.leader, r.leader)})
    # distribution of per-contract peak lags (each contract keeps its own row; no averaging)
    sig = [r for r in rows if r["z"] >= 3.0]
    lag_hist = defaultdict(int)
    for r in sig:
        lag_hist[r["peak_lag_min"]] += 1
    return {"series": series, "n_contracts": len(rows), "n_significant_z3": len(sig),
            "lag_histogram_significant": dict(sorted(lag_hist.items())),
            "contracts": rows}


def main() -> None:
    ap = argparse.ArgumentParser(description="Futures->Kalshi lag measurement (per contract)")
    ap.add_argument("--series", default="KXWTI")
    ap.add_argument("--futures-json", default=None, help='[{"ts":epoch,"close":px}, ...] 1-min bars')
    ap.add_argument("--fetch", default=None, help="Yahoo symbol to fetch 7d 1m bars (e.g. CL=F, NG=F)")
    ap.add_argument("--min-trades", type=int, default=150)
    ap.add_argument("--max-lag", type=int, default=30, help="minutes")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    fj = args.futures_json
    if args.fetch:
        fj = fetch_yahoo_1m(args.fetch, os.path.join("data", "kalshi_hist_trades",
                                                     f"_fut_{args.fetch.replace('=','')}_1m.json"))
        print(f"[fetch] {args.fetch} 1m -> {fj}")
    if not fj:
        ap.error("pass --futures-json or --fetch SYMBOL")
    res = run(args.series, fj, args.min_trades, args.max_lag)
    if args.out:
        json.dump(res, open(args.out, "w"), indent=2)
    print(f"[{res['series']}] contracts measured: {res['n_contracts']}  significant (z>=3): {res['n_significant_z3']}")
    print(f"  peak-lag histogram (significant only; +N = FUTURES LEAD by N min): "
          f"{res['lag_histogram_significant']}")
    for r in sorted(res["contracts"], key=lambda x: -x["z"])[:20]:
        print(f"    {r['ticker']:<26} {r['date']} lag={r['peak_lag_min']:+3d}m cc={r['cc']:+.3f} "
              f"z={r['z']:>5.1f} updates={r['n_kalshi_updates']:<4} trades={r['n_trades']}")


if __name__ == "__main__":
    main()
