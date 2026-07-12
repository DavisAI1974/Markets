"""
level_hit_dataset.py — the PER-TRADE LEVEL-HIT dataset (S82; the continuation predictor).

The S80 reframe (Greg): the prediction unit is a LEVEL-HIT event, not a bar. When price hits a new
level L travelling in a direction, the question is whether the move CONTINUES to the next level
(L+dir) before it REVERSES (back through L-dir). Each event carries its own context; we never average
across them — we build the DISTRIBUTION of outcomes per cell and read the WINNER FINGERPRINT (which
context precedes continuation). `each-trade-individually-never-average`.

One row per level-hit event on the real WTI trade tape (kalshi_history.py output, signed `taker_side`):

  CONTEXT (strictly PRE-hit — leakage-gated closure over trades [i-W .. i], never reads the future):
    moneyness   : yes_price band at the hit (the market-implied probability = direct moneyness).
    side        : direction of travel (up/down) + the aggressor taker_side of the hitting trade.
    tod         : UTC hour bucket.
    release     : within +/- window of the series' scheduled release (WTI = EIA crude Wed 14:30 UTC).
    velocity    : signed pre-hit price slope (cents/sec) over the window.
    herd/whale  : SCORED not assumed — clip count (breadth), total volume, max-clip concentration.
                  whale = one clip dominates (finite inventory, scalp-only); herd = many small clips
                  (fuel keeps arriving -> continuation). `herd-over-whale-for-continuation`.
    exhaustion  : info_dipole divergence -> exhausting flag + expect state.

  OUTCOME (forward from the hit, trailing exit = score_hold philosophy, bounded by the settle guard):
    continued   : reached L+dir before L-dir?  (the level-continuation label)
    run_length  : furthest level count reached in dir before the first one-level pullback.
    net_cents   : trailing-exit P&L net of that strike's REAL Kalshi fee + entry slippage.
    resolution  : 'target' | 'reversal' | 'censored' (walk hit the settle/horizon cap unresolved).

Discipline: leakage gate BEFORE any distribution (odcore.leakage.assert_no_leakage on the context
closure); per-cell (moneyness x side x release x tod), distributions not means; the settle window is
excluded; zero synthetic — every row is a real fill. Provisional-until-live.

Usage:
    python research/kalshi/level_hit_dataset.py --series KXWTI --out data/level_hits_KXWTI.json
    python research/kalshi/level_hit_dataset.py --series KXWTI --min-cell 30 --top-fingerprints 8
"""
from __future__ import annotations

import argparse
import glob
import json
import math
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

# Daily SETTLE (UTC HH:MM) — the mechanical 0/100 convergence flow can't predict; every event whose
# forward walk reaches it is capped there (censored) not scored through it. (Matches release_signal_history.)
SETTLE_UTC = {"KXWTI": (18, 30), "KXNATGASD": (21, 0), "KXBRENTD": (21, 0)}
# Scheduled release (UTC HH:MM, weekday 0=Mon..6=Sun) — the catalyst flag.
RELEASE = {"KXWTI": (14, 30, 2), "KXNATGASD": (14, 30, 3), "KXBRENTD": (14, 30, 2)}


# ---- parse -------------------------------------------------------------------------------------
def event_date(event_ticker: str):
    """KXWTI-26JUL0114 -> 2026-07-01 UTC midnight. <SERIES>-<YY><MMM><DD>[<HH>]."""
    try:
        tail = event_ticker.split("-", 1)[1]
        yy = int(tail[:2]); mon = _MONTHS[tail[2:5]]; dd = int(tail[5:7])
        return datetime(2000 + yy, mon, dd, tzinfo=timezone.utc)
    except (ValueError, KeyError, IndexError):
        return None


def _parse_ts(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def load_event_trades(series: str, event: str):
    """-> {ticker: (ts, price, buy_vol, sell_vol) per-TRADE aligned arrays, time-sorted}.

    Per-trade (not binned): buy_vol[i]=count if the taker lifted YES (buy), sell_vol[i]=count if the
    taker hit the YES bid (sell). This is the exact array shape the leakage gate closure indexes."""
    path = os.path.join(STORE, series, f"{event}_trades.jsonl")
    if not os.path.exists(path):
        return {}
    rows: dict[str, list] = defaultdict(list)
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("yes_price") is None or not r.get("ts"):
            continue
        rows[r["ticker"]].append((_parse_ts(r["ts"]), float(r["yes_price"]),
                                  float(r.get("count") or 0.0), r.get("taker_side")))
    out = {}
    for tk, lst in rows.items():
        lst.sort(key=lambda x: x[0])
        ts = np.array([x[0] for x in lst], float)
        price = np.array([x[1] for x in lst], float)
        buy = np.array([x[2] if x[3] == "yes" else 0.0 for x in lst], float)
        sell = np.array([x[2] if x[3] == "no" else 0.0 for x in lst], float)
        aggr = [x[3] for x in lst]
        out[tk] = (ts, price, buy, sell, aggr)
    return out


# ---- context (strictly pre-hit; the leakage-gated closure) -------------------------------------
def context_at(i, ts, p, bv, sv, window: int):
    """All PRE-hit context 'as of trade i' — reads only [i-W .. i]. Returns None if too thin.

    Everything here must be invariant to trades AFTER i (that is what assert_no_leakage checks)."""
    lo = max(0, i - window + 1)
    if i - lo + 1 < 6:
        return None
    span_s = float(ts[i] - ts[lo])
    drift = float(p[i] - p[lo])
    d = divergence(bv[lo:i + 1], sv[lo:i + 1], price_drift=drift if drift != 0 else 1e-9)
    if d is None:
        return None
    win_buy = float(bv[lo:i + 1].sum()); win_sell = float(sv[lo:i + 1].sum())
    tot = win_buy + win_sell
    clips = np.concatenate([bv[lo:i + 1], sv[lo:i + 1]])
    clips = clips[clips > 0]
    n_clips = int(clips.size)
    max_frac = float(clips.max() / tot) if tot > 0 and n_clips else 0.0
    velocity = round(drift / span_s, 6) if span_s > 0 else 0.0            # cents/sec, signed
    return {
        "price": round(float(p[i]), 2),
        "velocity": velocity,
        "imb_level": round(d["imb_level"], 4),
        "exhausting": bool(d["exhausting"]),
        "expect": d["expect"],
        "aligned_flow": round(d["aligned_flow"], 4),
        "win_vol": round(tot, 2),
        "n_clips": n_clips,
        "max_clip_frac": round(max_frac, 4),
    }


def _leakage_scalar(i, ts, p, bv, sv, window):
    """Collapse context to one scalar for the leakage gate (velocity + imbalance + exhaustion flag)."""
    c = context_at(i, ts, p, bv, sv, window)
    if c is None:
        return None
    return round(c["velocity"] * 1e4 + c["imb_level"] + (0.5 if c["exhausting"] else 0.0), 6)


# ---- feature bucketers -------------------------------------------------------------------------
def moneyness_band(price: float) -> str:
    if price < 10:   return "deep_low"
    if price < 30:   return "low"
    if price < 70:   return "mid"          # near-ATM uncertainty band
    if price < 90:   return "high"
    return "deep_high"


def velocity_band(v: float) -> str:
    a = abs(v)
    if a < 0.002:  return "slow"           # <0.12 c/min
    if a < 0.01:   return "med"            # <0.6  c/min
    return "fast"


def herd_whale(n_clips: int, max_frac: float) -> str:
    """SCORED: whale = one clip dominates; herd = broad clip arrival; else mixed."""
    if max_frac >= 0.5:              return "whale"
    if n_clips >= 8 and max_frac < 0.35:  return "herd"
    return "mixed"


def tod_band(hour: int) -> str:
    if 13 <= hour < 15:  return "release_hrs"   # 09-11 ET, EIA/macro window
    if 14 <= hour < 21:  return "us_session"
    return "off_hours"


# ---- Kalshi fee ------------------------------------------------------------------------------
def kalshi_fee_cents(price_cents: float, contracts: float = 1.0) -> float:
    """Kalshi trading fee = round_up(0.07 * C * P * (1-P)) in dollars -> cents. P in [0,1]."""
    p = min(max(price_cents / 100.0, 0.0), 1.0)
    return math.ceil(0.07 * contracts * p * (1 - p) * 100) / 1.0   # cents (per contract)


# ---- outcome (forward trailing walk) ----------------------------------------------------------
def outcome_from(i, ts, p, dir_, cap_ts, entry_slip: float, max_forward_s: float):
    """Continuation label + trailing-exit P&L from the hit at trade i in direction dir_ (+1 up / -1 down).

    LABEL   continued = price reached L+dir (the next level) BEFORE L-dir (reversal below entry) — Greg's
            level-continuation unit, independent of where the trailing exit lands.
    RUN     run_length = furthest level progress in dir reached (the running extreme).
    P&L     trailing exit one level back off the running extreme; net = captured - slip - fee.
    Bounded by the settle cap and max_forward_s (else 'censored')."""
    L = round(float(p[i]))
    extreme = 0                       # furthest level progress in dir (>=0)
    target_first = False              # reached L+dir before L-dir?
    below_entry = False               # dropped to L-dir (hard reversal below the entry level)
    trail_stop = False                # pulled one level back off the running extreme
    j = i + 1
    horizon = ts[i] + max_forward_s
    while j < len(p):
        if ts[j] > cap_ts or ts[j] > horizon:
            break
        prog = int(round((round(float(p[j])) - L) * dir_))       # signed level progress in dir
        if prog >= 1 and not below_entry:
            target_first = True                                  # target touched before any below-entry
        if prog <= -1:
            below_entry = True
        if prog > extreme:
            extreme = prog
        if extreme >= 1 and prog <= extreme - 1:                 # trailing one-level pullback -> exit
            trail_stop = True
            break
        if below_entry:                                          # hard reversal below entry -> exit
            break
        j += 1
    if trail_stop:
        resolution = "target" if extreme >= 2 else "reversal"    # locked a level in, or round-tripped
        exit_prog = extreme - 1
    elif below_entry:
        resolution = "reversal"; exit_prog = -1
    elif extreme >= 1:
        resolution = "target"; exit_prog = extreme               # ran out of window still in profit
    else:
        resolution = "censored"; exit_prog = 0
    gross = exit_prog * 1.0                                       # cents captured (1 cent / level)
    fee = kalshi_fee_cents(float(p[i]))
    net = round(gross - entry_slip - fee, 3)                      # taker entry (cross the spread)
    net_maker = round(gross - fee, 3)                             # maker entry (rest at the level; S81: toll ~halves)
    return {"continued": int(target_first), "run_length": int(extreme), "resolution": resolution,
            "net_cents": net, "net_maker": net_maker, "fee_cents": round(fee, 3)}


# ---- per-event event extraction ----------------------------------------------------------------
def events_for(series, event, cfg):
    ed = event_date(event)
    if ed is None:
        return []
    rhh, rmm, rwd = cfg["release"]
    is_release_day = ed.weekday() == rwd
    release_ts = ed.replace(hour=rhh, minute=rmm).timestamp()
    shh, smm = cfg["settle"]
    settle_ts = ed.replace(hour=shh, minute=smm).timestamp()
    cap_ts = settle_ts - cfg["settle_guard_s"]                    # walk never scores through the settle
    by_tk = load_event_trades(series, event)
    W = cfg["window"]
    rows = []
    for tk, (ts, p, bv, sv, aggr) in by_tk.items():
        if len(p) < cfg["min_trades"]:
            continue
        last_level = round(float(p[0]))
        for i in range(1, len(p)):
            lvl = round(float(p[i]))
            if lvl == last_level:
                continue
            dir_ = 1 if lvl > last_level else -1
            prev_level = last_level
            last_level = lvl
            if i < W:                                            # need a full pre-window
                continue
            if ts[i] >= cap_ts:                                  # inside the settle exclusion
                continue
            ctx = context_at(i, ts, p, bv, sv, W)
            if ctx is None:
                continue
            out = outcome_from(i, ts, p, dir_, cap_ts, cfg["entry_slip"], cfg["max_forward_s"])
            if out["resolution"] == "censored" and out["run_length"] == 0:
                continue                                         # never resolved, no info
            hour = datetime.fromtimestamp(ts[i], timezone.utc).hour
            in_release = is_release_day and abs(ts[i] - release_ts) <= cfg["release_win_s"]
            rows.append({
                "event": event, "ticker": tk, "trade_i": i,
                "dir": dir_, "aggr": aggr[i], "from_level": prev_level, "level": lvl,
                # cells
                "moneyness": moneyness_band(ctx["price"]),
                "side": "up" if dir_ > 0 else "down",
                "release": bool(in_release), "tod": tod_band(hour),
                # context (pre-hit)
                "velocity_band": velocity_band(ctx["velocity"]),
                "herd_whale": herd_whale(ctx["n_clips"], ctx["max_clip_frac"]),
                "exhausting": ctx["exhausting"], "expect": ctx["expect"],
                "imb_level": ctx["imb_level"], "aligned_flow": ctx["aligned_flow"],
                "velocity": ctx["velocity"], "win_vol": ctx["win_vol"],
                "n_clips": ctx["n_clips"], "max_clip_frac": ctx["max_clip_frac"],
                # outcome
                "continued": out["continued"], "run_length": out["run_length"],
                "resolution": out["resolution"], "net_cents": out["net_cents"],
                "net_maker": out["net_maker"], "fee_cents": out["fee_cents"],
            })
    return rows


# ---- leakage gate ------------------------------------------------------------------------------
def leakage_gate(series, events, cfg) -> tuple[bool, int]:
    """Run assert_no_leakage on the context closure over one real contract with enough depth."""
    W = cfg["window"]
    for e in events:
        by_tk = load_event_trades(series, e)
        for tk, (ts, p, bv, sv, aggr) in by_tk.items():
            if len(p) < max(cfg["min_trades"], W + 20):
                continue
            step = max(1, (len(p) - W) // 12)
            idxs = list(range(W, len(p) - 1, step))[:12]
            if len(idxs) < 3:
                continue
            passed, fails = assert_no_leakage(
                lambda i, ts_, p_, bv_, sv_: _leakage_scalar(i, ts_, p_, bv_, sv_, W),
                ts, p, bv, sv, idxs, reps=3, seed=0)
            return bool(passed), len(fails)
    return True, 0


# ---- per-cell distributions + winner fingerprints ---------------------------------------------
def _dist(rows):
    """Distribution summary of a group's outcomes (NOT a lone mean — full shape)."""
    n = len(rows)
    if n == 0:
        return None
    cont = np.array([r["continued"] for r in rows], float)
    runs = np.array([r["run_length"] for r in rows], float)
    nets = np.array([r["net_cents"] for r in rows], float)
    netm = np.array([r["net_maker"] for r in rows], float)
    res = defaultdict(int)
    for r in rows:
        res[r["resolution"]] += 1
    return {
        "n": n,
        "continue_rate": round(float(cont.mean()), 3),
        "big_run_rate": round(float((runs >= 2).mean()), 3),      # >= 2 levels = the paying tail
        "run_len": {"p25": float(np.percentile(runs, 25)), "med": float(np.median(runs)),
                     "p75": float(np.percentile(runs, 75)), "max": float(runs.max())},
        "net_cents": {"p10": round(float(np.percentile(nets, 10)), 2),
                       "med": round(float(np.median(nets)), 2),
                       "mean": round(float(nets.mean()), 3),
                       "p90": round(float(np.percentile(nets, 90)), 2),
                       "pos_frac": round(float((nets > 0).mean()), 3)},
        "net_maker": {"med": round(float(np.median(netm)), 2),
                       "mean": round(float(netm.mean()), 3),
                       "pos_frac": round(float((netm > 0).mean()), 3)},
        "resolution": dict(res),
    }


def cell_key(r) -> str:
    """Cell = moneyness x side x velocity-regime x release. Velocity is a PRE-hit context, so
    conditioning on it is not leakage — it is the move-regime split S81 showed is load-bearing
    (direction is easy on FAST/big moves, buried when small moves are pooled in)."""
    return f"{r['moneyness']}|{r['side']}|{r['velocity_band']}|{'rel' if r['release'] else 'norel'}"


def winner_fingerprint(rows, big_run: int = 2):
    """What context PRECEDES a BIG continuation (run_length >= big_run — Greg's 'continuation big/small')?

    The money is in the multi-level run, not the 1-level poke (`continued`); a poke that round-trips at the
    trailing stop still loses the toll. So the fingerprint targets the big-run tail: for each context value,
    the lift = its share among big-run winners minus its base share. Distributions, not a model."""
    won = [r for r in rows if r["run_length"] >= big_run]
    lost = [r for r in rows if r["run_length"] < big_run]
    if len(won) < 5 or len(lost) < 5:
        return None
    fp = {}
    for feat in ("herd_whale", "tod", "exhausting", "expect", "aggr"):
        vals = sorted({r[feat] for r in rows}, key=str)
        fp[feat] = {}
        for v in vals:
            w = sum(1 for r in won if r[feat] == v)
            l = sum(1 for r in lost if r[feat] == v)
            base = (w + l) / len(rows)
            in_win = w / len(won)
            fp[feat][str(v)] = {"n": w + l, "win_share": round(in_win, 3),
                                 "base_share": round(base, 3),
                                 "lift": round(in_win - base, 3)}
    return fp


def build(series, cfg):
    events = sorted({os.path.basename(p).replace("_trades.jsonl", "")
                     for p in glob.glob(os.path.join(STORE, series, "*_trades.jsonl"))})
    if not events:
        return {"series": series, "status": "NO_DATA",
                "msg": f"no tape in {os.path.join(STORE, series)} — run kalshi_history.py --all first"}
    leak_pass, leak_fails = leakage_gate(series, events, cfg)
    all_rows = []
    for e in events:
        all_rows += events_for(series, e, cfg)
    if not all_rows:
        return {"series": series, "status": "NO_EVENTS", "leakage_pass": leak_pass}
    # per-cell
    by_cell = defaultdict(list)
    for r in all_rows:
        by_cell[cell_key(r)].append(r)
    cells = {}
    for k, rows in sorted(by_cell.items(), key=lambda kv: -len(kv[1])):
        if len(rows) < cfg["min_cell"]:
            continue
        cells[k] = {"dist": _dist(rows), "fingerprint": winner_fingerprint(rows, cfg["big_run"])}
    # winner cells: highest maker-net pos_frac among reported cells (where continuation actually pays)
    winners = sorted(
        ({"cell": k, "n": c["dist"]["n"], "continue_rate": c["dist"]["continue_rate"],
          "net_taker_pos": c["dist"]["net_cents"]["pos_frac"],
          "net_maker_pos": c["dist"]["net_maker"]["pos_frac"],
          "net_maker_mean": c["dist"]["net_maker"]["mean"]}
         for k, c in cells.items()),
        key=lambda x: -x["net_maker_pos"])[:12]
    return {
        "series": series, "status": "OK",
        "n_events": len(events), "n_level_hits": len(all_rows),
        "leakage_pass": leak_pass, "leakage_fails": leak_fails,
        "overall": _dist(all_rows),
        "n_cells_reported": len(cells),
        "winner_cells": winners,
        "cells": cells,
        "cfg": {k: v for k, v in cfg.items()},
    }


def main():
    ap = argparse.ArgumentParser(description="Per-trade LEVEL-HIT continuation dataset (S82)")
    ap.add_argument("--series", default="KXWTI")
    ap.add_argument("--window", type=int, default=20, help="pre-hit context window (trades)")
    ap.add_argument("--min-trades", type=int, default=100, help="min trades/contract to include")
    ap.add_argument("--min-cell", type=int, default=30, help="min level-hits to report a cell")
    ap.add_argument("--big-run", type=int, default=2, help="run_length threshold for a 'big' continuation")
    ap.add_argument("--entry-slip", type=float, default=1.0, help="entry slippage (cents, cross the spread)")
    ap.add_argument("--max-forward-s", type=float, default=1800.0, help="max forward walk (s)")
    ap.add_argument("--settle-guard-s", type=float, default=1800.0, help="exclusion band before daily settle")
    ap.add_argument("--release-win-s", type=float, default=3600.0, help="+/- release flag window (s)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--top-fingerprints", type=int, default=6, help="how many cell fingerprints to print")
    args = ap.parse_args()
    cfg = {"window": args.window, "min_trades": args.min_trades, "min_cell": args.min_cell,
           "big_run": args.big_run,
           "entry_slip": args.entry_slip, "max_forward_s": args.max_forward_s,
           "settle_guard_s": args.settle_guard_s, "release_win_s": args.release_win_s,
           "settle": SETTLE_UTC.get(args.series, (21, 0)),
           "release": RELEASE.get(args.series, (14, 30, 2))}
    res = build(args.series, cfg)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        json.dump(res, open(args.out, "w"), indent=2)
    if res["status"] != "OK":
        print(f"[{res['series']}] {res['status']}: {res.get('msg', '')}")
        return
    o = res["overall"]
    print(f"[{res['series']}] level_hits={res['n_level_hits']} over {res['n_events']} events  "
          f"leakage_pass={res['leakage_pass']} (fails={res['leakage_fails']})")
    print(f"  OVERALL continue_rate={o['continue_rate']}  run_len med={o['run_len']['med']} "
          f"p75={o['run_len']['p75']}  net_cents med={o['net_cents']['med']} mean={o['net_cents']['mean']} "
          f"pos_frac={o['net_cents']['pos_frac']}")
    print(f"  cells reported (>= {args.min_cell}): {res['n_cells_reported']}")
    print("  WINNER CELLS (by maker-net pos_frac):")
    for w in res["winner_cells"][:8]:
        print(f"    {w['cell']:<34} n={w['n']:<5} cont={w['continue_rate']:.3f} "
              f"taker_pos={w['net_taker_pos']:.3f} maker_pos={w['net_maker_pos']:.3f} "
              f"maker_mean={w['net_maker_mean']:+.2f}")
    shown = 0
    for k, c in res["cells"].items():
        d = c["dist"]
        print(f"\n  CELL {k}  n={d['n']}  cont={d['continue_rate']}  big={d['big_run_rate']}  "
              f"run p75={d['run_len']['p75']}  maker mean={d['net_maker']['mean']} "
              f"pos={d['net_maker']['pos_frac']}")
        if c["fingerprint"] and shown < args.top_fingerprints:
            for feat, vals in c["fingerprint"].items():
                best = sorted(vals.items(), key=lambda kv: -kv[1]["lift"])[0]
                print(f"      {feat}: {best[0]} lift={best[1]['lift']:+.3f} (n={best[1]['n']})")
            shown += 1
    print("\n  provisional — per-cell, distributions not means, leakage-gated; never size off one window.")


if __name__ == "__main__":
    main()
