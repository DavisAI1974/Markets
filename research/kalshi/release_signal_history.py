"""
release_signal_history.py — test the S80 release-triggered signal on HISTORICAL Kalshi trade flow.

Consumes kalshi_history.py output (per-event trade JSONL with signed `taker_side`) and runs the merged
architecture on REAL signed order flow around PAST scheduled releases — no waiting for live accrual:

  * DIRECTION = net taker-flow imbalance SIGN over a strictly pre-decision window
                (info_dipole.divergence's imb_level, computed on the REAL buy/sell volume the taker_side
                gives us — the ORIGINAL dipole input, cleaner than the live book-depth proxy).
  * FADE      = info_dipole EXHAUSTION (the flow dipole collapsing toward 0.5 early->late half).
  * CATALYST  = the scheduled release. WTI Kalshi contracts settle on the WTI price, which the EIA crude
                inventory (Wed 14:30 UTC / 10:30 ET) moves intraday. So for a WTI series:
                  - Wednesday events   = RELEASE days (decision = release + spike-pause).
                  - non-Wed events     = natural PLACEBO days (same machinery, no release) — the honest
                                         baseline the direction/fade read must beat.

Discipline: leakage-gated (the (price, buy_vol, sell_vol) triple maps straight onto
odcore.leakage.assert_no_leakage), per-contract, placebo-baselined, provisional-until-live. Zero
synthetic data — every trade is a real Kalshi fill.

Usage:
    python research/kalshi/release_signal_history.py --series KXWTI          # all pulled events
    python research/kalshi/release_signal_history.py --series KXWTI --release-utc 14:30 --out out.json
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
from odcore.info_dipole import divergence            # noqa: E402
from odcore.leakage import assert_no_leakage          # noqa: E402

STORE = "data/kalshi_hist_trades"
_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}

# Daily SETTLE time (UTC HH:MM) per series — the contract converges to 0/100 into this, a MECHANICAL
# move that flow can't predict, so every decision whose forward horizon reaches the settle window is
# excluded ("daily settle numbers won't help us with individual trade" — Greg). EDT assumed (May-Jul).
#   WTI   = ICE daily settlement ~2:30 PM ET.
#   natgas/Brent = 1-min candle close 5:00 PM EDT (per rules_primary).
SETTLE_UTC = {"KXWTI": (18, 30), "KXNATGASD": (21, 0), "KXBRENTD": (21, 0)}


# ---- parse + bin ---------------------------------------------------------------------------
def event_date(event_ticker: str) -> datetime | None:
    """KXWTI-26JUL0114 -> 2026-07-01 (UTC midnight). Format: <SERIES>-<YY><MMM><DD>[<HH>]."""
    try:
        tail = event_ticker.split("-", 1)[1]              # 26JUL0114
        yy = int(tail[:2]); mon = _MONTHS[tail[2:5]]; dd = int(tail[5:7])
        return datetime(2000 + yy, mon, dd, tzinfo=timezone.utc)
    except (ValueError, KeyError, IndexError):
        return None


def _parse_ts(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def load_event_trades(series: str, event: str) -> dict[str, list[dict]]:
    """-> {ticker: [ {ts, yes_price, count, side} sorted ]} from the stored trade JSONL."""
    path = os.path.join(STORE, series, f"{event}_trades.jsonl")
    by_tk: dict[str, list[dict]] = defaultdict(list)
    if not os.path.exists(path):
        return {}
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("yes_price") is None or not r.get("ts"):
            continue
        by_tk[r["ticker"]].append({"ts": _parse_ts(r["ts"]), "price": float(r["yes_price"]),
                                   "count": float(r.get("count") or 0.0), "side": r.get("taker_side")})
    for tk in by_tk:
        by_tk[tk].sort(key=lambda x: x["ts"])
    return by_tk


def bin_flow(trades: list[dict], bin_s: float, t0: float, t1: float):
    """Time-bin trades in [t0,t1] -> (ts, price, buy_vol, sell_vol) aligned arrays (last price ffill)."""
    if not trades:
        return None
    nb = int((t1 - t0) / bin_s) + 1
    price = np.full(nb, np.nan); buy = np.zeros(nb); sell = np.zeros(nb)
    for tr in trades:
        if tr["ts"] < t0 or tr["ts"] > t1:
            continue
        b = int((tr["ts"] - t0) / bin_s)
        if b >= nb:
            continue
        price[b] = tr["price"]
        if tr["side"] == "yes":
            buy[b] += tr["count"]
        elif tr["side"] == "no":
            sell[b] += tr["count"]
    # forward-fill price; drop leading NaNs
    last = np.nan
    for i in range(nb):
        if np.isnan(price[i]):
            price[i] = last
        else:
            last = price[i]
    ts = t0 + bin_s * (np.arange(nb) + 1)
    valid = ~np.isnan(price)
    if valid.sum() < 12:
        return None
    return ts[valid], price[valid], buy[valid], sell[valid]


# ---- signal --------------------------------------------------------------------------------
def signal_at(i, ts, p, bv, sv, window: int = 20):
    """Signed scalar 'as of bin i' from the pre-decision flow window — the leakage-gated closure.
    Direction = flow imbalance sign; magnitude discounted when the dipole is exhausting (fade)."""
    lo = max(0, i - window + 1)
    if i - lo + 1 < 6:
        return None
    drift = float(p[i] - p[lo])
    d = divergence(bv[lo:i + 1], sv[lo:i + 1], price_drift=drift if drift != 0 else 1e-9)
    if d is None:
        return None
    lvl = d["imb_level"]
    direction = 1 if lvl > 0 else (-1 if lvl < 0 else 0)
    strength = abs(lvl) * (0.5 if d["exhausting"] else 1.0)
    return round(direction * strength * (1.0 + d["reversal_conviction"]), 9)


def read(ts, p, bv, sv, i, window, horizon_bins, move_thresh=1.0):
    """A directional call is only scorable when price actually MOVES over the horizon (>= move_thresh
    cents); flat-forward windows leave `hit=None` (excluded from the hit rate, not counted a miss)."""
    lo = max(0, i - window + 1)
    if i - lo + 1 < 6 or i + horizon_bins >= len(p):
        return None
    drift = float(p[i] - p[lo])
    d = divergence(bv[lo:i + 1], sv[lo:i + 1], price_drift=drift if drift != 0 else 1e-9)
    if d is None:
        return None
    direction = 1 if d["imb_level"] > 0 else (-1 if d["imb_level"] < 0 else 0)
    fwd = float(p[i + horizon_bins] - p[i])
    moved = abs(fwd) >= move_thresh and direction != 0
    hit = int(np.sign(fwd) == direction) if moved else None
    return {"direction": direction, "conv": round(abs(d["imb_level"]), 4),
            "exhausting": bool(d["exhausting"]), "expect": d["expect"],
            "fwd": round(fwd, 3), "moved": moved, "hit": hit}


# ---- per-event evaluation ------------------------------------------------------------------
def eval_event(series, event, cfg) -> dict | None:
    ed = event_date(event)
    if ed is None:
        return None
    is_release = ed.weekday() == cfg["release_weekday"]      # Wed for EIA crude
    hh, mm = cfg["release_hh"], cfg["release_mm"]
    release_ts = ed.replace(hour=hh, minute=mm).timestamp()
    shh, smm = cfg["settle_hh"], cfg["settle_mm"]
    settle_ts = ed.replace(hour=shh, minute=smm).timestamp()
    # the LAST tradeable instant whose forward horizon still completes before the settle guard
    cutoff_ts = settle_ts - cfg["settle_guard_s"] - cfg["horizon_bins"] * cfg["bin_s"]
    by_tk = load_event_trades(series, event)
    if not by_tk:
        return None
    bin_s, W, hz = cfg["bin_s"], cfg["window"], cfg["horizon_bins"]
    ev_recs, pl_recs = [], []
    for tk, trades in by_tk.items():
        if len(trades) < cfg["min_trades"]:
            continue
        span0, span1 = trades[0]["ts"], trades[-1]["ts"]
        binned = bin_flow(trades, bin_s, span0, span1)
        if binned is None:
            continue
        ts, p, bv, sv = binned
        if is_release and span0 <= release_ts <= span1:
            di = int(np.searchsorted(ts, release_ts + cfg["spike_pause_s"], side="left"))
            if di < len(ts) and ts[di] <= cutoff_ts:         # release read must clear the settle window
                r = read(ts, p, bv, sv, di, W, hz, cfg["move_thresh"])
                if r:
                    r["ticker"] = tk; ev_recs.append(r)
        # placebo: non-release, >=1h from the release, AND clear of the settlement convergence window
        rng = np.random.default_rng(abs(hash(tk)) % (2 ** 32))
        cand = [j for j in range(W, len(p) - hz)
                if abs(ts[j] - release_ts) > 3600 and ts[j] <= cutoff_ts]
        rng.shuffle(cand)
        for j in cand[:cfg["placebo_per_contract"]]:
            r = read(ts, p, bv, sv, j, W, hz, cfg["move_thresh"])
            if r:
                pl_recs.append(r)
    return {"event": event, "date": ed.date().isoformat(), "is_release": is_release,
            "n_contracts": len(by_tk), "event_recs": ev_recs, "placebo_recs": pl_recs}


def _rate(recs):
    scored = [r for r in recs if r.get("hit") is not None]
    return (round(sum(r["hit"] for r in scored) / len(scored), 3), len(scored)) if scored else (None, 0)


def run(series, cfg) -> dict:
    events = sorted({os.path.basename(p).replace("_trades.jsonl", "")
                     for p in glob.glob(os.path.join(STORE, series, "*_trades.jsonl"))})
    if not events:
        return {"series": series, "status": "NO_DATA",
                "msg": f"no pulled trades in {os.path.join(STORE, series)} — run kalshi_history.py --all first"}
    ev_all, pl_all, per_event = [], [], []
    for e in events:
        res = eval_event(series, e, cfg)
        if res is None:
            continue
        ev_all += res["event_recs"]; pl_all += res["placebo_recs"]
        ehr, en = _rate(res["event_recs"])
        per_event.append({"event": e, "date": res["date"], "is_release": res["is_release"],
                          "event_hit": ehr, "event_n": en})
    # leakage gate on one real binned contract
    leak = _leakage_check(series, events, cfg)
    ev_hr, ev_n = _rate(ev_all)
    pl_hr, pl_n = _rate(pl_all)
    return {"series": series, "status": "OK", "n_events": len(per_event),
            "leakage_pass": leak,
            "release_events": sum(1 for pe in per_event if pe["is_release"]),
            "event": {"hit_rate": ev_hr, "n": ev_n},
            "placebo": {"hit_rate": pl_hr, "n": pl_n},
            "edge_vs_placebo": (None if (ev_hr is None or pl_hr is None) else round(ev_hr - pl_hr, 3)),
            "exhaustion_fade": _fade_report(ev_all + pl_all),
            "per_event": per_event}


def _fade_report(recs):
    """Does exhaustion call the fade? Split hit-rate by exhausting vs not (fade = lower continuation)."""
    ex = [r for r in recs if r["exhausting"]]; nx = [r for r in recs if not r["exhausting"]]
    return {"exhausting": {"continuation_hit": _rate(ex)[0], "n": len(ex)},
            "not_exhausting": {"continuation_hit": _rate(nx)[0], "n": len(nx)}}


def _leakage_check(series, events, cfg) -> bool:
    for e in events:
        by_tk = load_event_trades(series, e)
        for tk, trades in by_tk.items():
            if len(trades) < cfg["min_trades"]:
                continue
            binned = bin_flow(trades, cfg["bin_s"], trades[0]["ts"], trades[-1]["ts"])
            if binned is None:
                continue
            ts, p, bv, sv = binned
            idxs = list(range(cfg["window"], len(p) - 1, max(1, (len(p) - cfg["window"]) // 12 or 1)))[:12]
            if len(idxs) < 3:
                continue
            passed, _ = assert_no_leakage(
                lambda i, ts_, p_, bv_, sv_: signal_at(i, ts_, p_, bv_, sv_, cfg["window"]),
                ts, p, bv, sv, idxs, reps=3, seed=0)
            return bool(passed)
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Test the release-triggered signal on historical Kalshi flow")
    ap.add_argument("--series", default="KXWTI")
    ap.add_argument("--bin-s", type=float, default=60.0, help="trade-bin seconds")
    ap.add_argument("--window", type=int, default=20, help="pre-decision flow window (bins)")
    ap.add_argument("--horizon-bins", type=int, default=20, help="forward move horizon (bins)")
    ap.add_argument("--spike-pause-s", type=float, default=120.0, help="pause through the release spike")
    ap.add_argument("--release-utc", default="14:30", help="release time UTC HH:MM (EIA crude 14:30)")
    ap.add_argument("--release-weekday", type=int, default=2, help="0=Mon..6=Sun (EIA crude Wed=2)")
    ap.add_argument("--min-trades", type=int, default=100)
    ap.add_argument("--placebo-per-contract", type=int, default=6)
    ap.add_argument("--move-thresh", type=float, default=1.0, help="min |fwd move| (cents) to score a call")
    ap.add_argument("--settle-utc", default=None, help="daily settle HH:MM UTC (default: per-series SETTLE_UTC)")
    ap.add_argument("--settle-guard-s", type=float, default=1800.0,
                    help="exclude decisions whose forward horizon lands within this of the daily settle")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    hh, mm = (int(x) for x in args.release_utc.split(":"))
    if args.settle_utc:
        shh, smm = (int(x) for x in args.settle_utc.split(":"))
    else:
        shh, smm = SETTLE_UTC.get(args.series, (21, 0))
    cfg = {"bin_s": args.bin_s, "window": args.window, "horizon_bins": args.horizon_bins,
           "spike_pause_s": args.spike_pause_s, "release_hh": hh, "release_mm": mm,
           "release_weekday": args.release_weekday, "min_trades": args.min_trades,
           "placebo_per_contract": args.placebo_per_contract, "move_thresh": args.move_thresh,
           "settle_hh": shh, "settle_mm": smm, "settle_guard_s": args.settle_guard_s}
    res = run(args.series, cfg)
    if args.out:
        json.dump(res, open(args.out, "w"), indent=2)
    if res["status"] != "OK":
        print(f"[{res['series']}] {res['status']}: {res.get('msg')}")
        return
    print(f"[{res['series']}] events={res['n_events']} (release={res['release_events']}) "
          f"leakage_pass={res['leakage_pass']}")
    print(f"  RELEASE  hit={res['event']['hit_rate']} (n={res['event']['n']})")
    print(f"  PLACEBO  hit={res['placebo']['hit_rate']} (n={res['placebo']['n']})")
    print(f"  EDGE vs placebo = {res['edge_vs_placebo']}")
    f = res["exhaustion_fade"]
    print(f"  FADE: exhausting continuation={f['exhausting']['continuation_hit']} (n={f['exhausting']['n']}) "
          f"vs not-exhausting={f['not_exhausting']['continuation_hit']} (n={f['not_exhausting']['n']})")
    print("  provisional — per-contract, placebo-baselined; never size off one window.")


if __name__ == "__main__":
    main()
