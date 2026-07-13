"""
lag_join_intraday.py — the INTRADAY framework (Greg S87): trade EVERY significant NYMEX move all day,
not just the weekly storage print. Same scaffold as lag_join.py (sustained-move NYMEX entry -> NYMEX-
driven hold through Kalshi whipsaw -> maker-into-herd / taker exit, net-of-fee) but scanning the whole
CONTINUOUS session instead of anchoring at the 14:30 release.

The storage release is ONE catalyst; a geopolitical headline, an inventory leak, an equity-risk move all
move NYMEX the same way and Kalshi lags every one. This scans the continuous tape (data/nymex_cont/) for
each sustained move and joins the full-day Kalshi echo (data/kalshi_hist_trades/.../<ev>_fullday.jsonl).

Discipline: leakage-safe by construction (entry = NYMEX move direction + stale Kalshi price, both strictly
<= entry time; the NYMEX-driven exit is the forward outcome). Per-move distributions, net-of-fee at maker
AND taker. Zero synthetic. Provisional -- one day (06-17, the Hormuz high-vol day) is a PROOF, not a
validated edge; the full-month/year batch is what settles it.

Usage:
    python research/kalshi/lag_join_intraday.py --day 20260617 --event KXWTI-26JUN1714 --root CL
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lag_join import fee_cents, price_at                  # noqa: E402  (reuse the fee + mark helpers)

CONT_DIR = "data/nymex_cont"
KALSHI_STORE = "data/kalshi_hist_trades"


def _iso_ts(s):
    import datetime as dt
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def load_nymex_cont(root, day):
    """Continuous NYMEX tape for one day -> (ts, price) arrays (time-sorted)."""
    path = os.path.join(CONT_DIR, f"{root}_{day}.jsonl")
    rows = [json.loads(l) for l in open(path) if l.strip()]
    rows.sort(key=lambda r: r["ts"])
    return np.array([r["ts"] for r in rows], float), np.array([r["price"] for r in rows], float)


def load_kalshi_fullday(series, event):
    """Full-day Kalshi tape -> {ticker: {ts, yes, floor}} per strike, time-sorted."""
    path = os.path.join(KALSHI_STORE, series, f"{event}_fullday.jsonl")
    by = defaultdict(list)
    for line in open(path):
        r = json.loads(line)
        if r.get("ts") is None or r.get("yes_price") is None:
            continue
        by[r["ticker"]].append((_iso_ts(r["ts"]), float(r["yes_price"]), r.get("floor")))
    out = {}
    for tk, rr in by.items():
        rr.sort(key=lambda x: x[0])
        out[tk] = {"ts": np.array([x[0] for x in rr], float),
                   "yes": np.array([x[1] for x in rr], float), "floor": rr[0][2]}
    return out


def scan_moves(fts, fp, trig_usd, confirm_s, cooldown_s, max_events=500):
    """Yield (entry_idx, sign) for each SUSTAINED move: the canary crosses trig_usd (same dir) and HOLDS
    for confirm_s. After a move we cool down `cooldown_s` so one swing is not re-entered. (Same sustained-
    move logic as lag_join, swept across the whole session.)"""
    out = []
    i = 1
    n = len(fp)
    while i < n and len(out) < max_events:
        base = fp[i]
        cross_sgn, cross_t0, ei = 0, None, None
        j = i
        while j < n and fts[j] - fts[i] <= 600:            # look up to 10 min for a sustained breakout
            d = fp[j] - base
            if abs(d) >= trig_usd:
                sgn = 1 if d > 0 else -1
                if sgn != cross_sgn:
                    cross_sgn, cross_t0 = sgn, fts[j]
                if fts[j] - cross_t0 >= confirm_s:
                    ei = j; break
            else:
                cross_sgn, cross_t0 = 0, None
            j += 1
        if ei is not None:
            out.append((ei, 1.0 if fp[ei] > base else -1.0, base))
            # cooldown from the entry
            k = ei
            while k < n and fts[k] < fts[ei] + cooldown_s:
                k += 1
            i = k
        else:
            i += 1
    return out


def pick_atm(kalshi, t, win=600.0):
    """The ATM strike AT time t = the strike with a recent trade in [t-win, t] whose last price is nearest
    50c (max sensitivity to the NYMEX move). The ATM drifts through the day as the underlying moves."""
    best, best_key = None, None
    for tk, d in kalshi.items():
        m = (d["ts"] >= t - win) & (d["ts"] <= t)
        if not m.any():
            continue
        last = float(d["yes"][m][-1])
        key = -abs(last - 50.0)
        if best_key is None or key > best_key:
            best_key, best = key, tk
    return best


def simulate(fts, fp, kalshi, ei, s, base, cfg):
    """One intraday echo trade (mirrors lag_join.simulate_event's entry/exit, sans release anchor)."""
    t_entry = fts[ei]
    atm = pick_atm(kalshi, t_entry)
    if atm is None:
        return None
    kts, kyes = kalshi[atm]["ts"], kalshi[atm]["yes"]
    entry_mark = price_at(kts, kyes, t_entry)
    if entry_mark is None or entry_mark < 3 or entry_mark > 97:     # need a live, tradeable ATM
        return None
    slip, maker_off, min_wave = cfg["slip"], cfg["maker_off"], cfg["min_wave"]
    # stand-back: skip if Kalshi already moved with NYMEX (caught up on its own)
    kR = price_at(kts, kyes, base if False else t_entry - cfg["look_back"])
    if kR is not None and s * (entry_mark - kR) >= cfg["stale_cap"]:
        return None
    entry_px = entry_mark + s * slip
    entry_fee = fee_cents(entry_px)

    # NYMEX TRAILING-STOP exit (Greg S87): HOLD through consistent directional movement; exit only when
    # the canary RETRACES reverse_usd DOLLARS from its favorable extreme -- a real trend reversal, not
    # every minor pullback. A fraction-of-local-run stop churns fees on a trending day (enter, stop out on
    # noise, re-enter); a fixed-$ trailing stop rides the whole trend and pays one round-trip, not ten.
    rev = cfg["reverse_usd"]
    n = len(fp)
    ext_f = fp[ei]                                          # favorable NYMEX extreme (the trend high/low)
    t_dec = fts[-1]
    end_t = t_entry + cfg["max_hold"]
    j = ei + 1
    while j < n and fts[j] <= end_t:
        if s * (fp[j] - ext_f) > 0:
            ext_f = fp[j]                                   # trend still extending -> keep holding
        if s * (ext_f - fp[j]) >= rev:                      # retraced reverse_usd from the peak -> trend broke
            t_dec = fts[j]; break
        j += 1
    else:
        t_dec = min(fts[min(j, n-1)], end_t)

    kfwd = (kts > t_entry) & (kts <= t_dec)
    ext = entry_mark
    if kfwd.any():
        ext = (max if s > 0 else min)(entry_mark, float((np.max if s > 0 else np.min)(kyes[kfwd])))
    exit_mark = price_at(kts, kyes, t_dec)
    if exit_mark is None:
        return None
    wave = s * (ext - entry_mark)
    taker_exit = exit_mark - s * slip
    pnl_taker = s * (taker_exit - entry_px) - entry_fee - fee_cents(taker_exit)
    if wave >= min_wave:
        maker_filled = 1
        pnl_maker = s * ((ext - s * maker_off) - entry_px) - entry_fee - 0
    else:
        maker_filled = 0
        pnl_maker = pnl_taker
    return {"t_entry": t_entry, "atm": atm, "dir": "up" if s > 0 else "dn",
            "entry_px": round(entry_px, 1), "ext": round(ext, 1), "wave": round(float(wave), 1),
            "pnl_taker": round(float(pnl_taker), 2), "pnl_maker": round(float(pnl_maker), 2),
            "maker_filled": maker_filled, "hold_s": round(t_dec - t_entry, 0)}


def main():
    ap = argparse.ArgumentParser(description="Intraday lag join — trade every NYMEX move all session")
    ap.add_argument("--day", required=True)
    ap.add_argument("--event", required=True)
    ap.add_argument("--root", required=True, choices=["CL", "NG"])
    ap.add_argument("--series", default=None)
    ap.add_argument("--trigger", type=float, default=0.20, help="$ NYMEX move to fire (per contract)")
    ap.add_argument("--confirm-s", type=float, default=5.0)
    ap.add_argument("--cooldown-s", type=float, default=180.0, help="min gap between entries (s)")
    ap.add_argument("--reverse-usd", type=float, default=0.25, help="$ NYMEX retrace from the favorable "
                    "extreme that ends the hold (trend reversal). Bigger = ride trends longer, churn less")
    ap.add_argument("--max-hold", type=float, default=3600.0)
    ap.add_argument("--stale-cap", type=float, default=12.0)
    ap.add_argument("--look-back", type=float, default=180.0, help="stand-back reference lookback (s)")
    ap.add_argument("--slip", type=float, default=1.0)
    ap.add_argument("--maker-off", type=float, default=1.0)
    ap.add_argument("--min-wave", type=float, default=1.0)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    series = args.series or ("KXWTI" if args.root == "CL" else "KXNATGASD")
    cfg = {k: getattr(args, k) for k in ["reverse_usd", "max_hold", "stale_cap", "look_back",
                                         "slip", "maker_off", "min_wave"]}

    fts, fp = load_nymex_cont(args.root, args.day)
    kalshi = load_kalshi_fullday(series, args.event)
    moves = scan_moves(fts, fp, args.trigger, args.confirm_s, args.cooldown_s)
    trades = []
    for ei, s, base in moves:
        r = simulate(fts, fp, kalshi, ei, s, base, cfg)
        if r:
            trades.append(r)

    import datetime as dt
    print(f"\nINTRADAY LAG JOIN — {args.root} {args.day} ({args.event})")
    print(f"session {dt.datetime.fromtimestamp(fts[0],dt.timezone.utc):%H:%M}-"
          f"{dt.datetime.fromtimestamp(fts[-1],dt.timezone.utc):%H:%M} UTC, {len(fp)} NYMEX ticks")
    print(f"trigger ${args.trigger:.2f} confirm {args.confirm_s:.0f}s cooldown {args.cooldown_s:.0f}s "
          f"reverse-stop ${args.reverse_usd:.2f} (hold through the trend)")
    print(f"{len(moves)} sustained NYMEX moves -> {len(trades)} tradeable Kalshi echoes "
          f"(rest had no live ATM / stood back)")
    if not trades:
        return
    tk = np.array([t["pnl_taker"] for t in trades])
    mk = np.array([t["pnl_maker"] for t in trades])
    fill = 100 * np.mean([t["maker_filled"] for t in trades])

    def line(name, a):
        return (f"  {name:6} n={len(a):>2}  pos {100*np.mean(a>0):>3.0f}%  "
                f"med {np.median(a):+5.1f}c  mean {np.mean(a):+5.1f}c  "
                f"sum {np.sum(a):+6.0f}c  [p25 {np.percentile(a,25):+.0f}, p75 {np.percentile(a,75):+.0f}]")
    print("net-of-fee cents/contract, per intraday trade (distribution, not led by the mean):")
    print(line("taker", tk))
    print(line("maker", mk), f" fill {fill:.0f}%")
    if args.verbose:
        print(f"\n{'t_entry':>8} {'dir':>3} {'atm':>22} {'entry':>5} {'ext':>5} {'wave':>5} "
              f"{'pnlT':>5} {'pnlM':>5} {'hold':>5}")
        for t in trades:
            hh = dt.datetime.fromtimestamp(t["t_entry"], dt.timezone.utc).strftime("%H:%M:%S")
            print(f"{hh:>8} {t['dir']:>3} {t['atm']:>22} {t['entry_px']:>5} {t['ext']:>5} "
                  f"{t['wave']:>5} {t['pnl_taker']:>5} {t['pnl_maker']:>5} {t['hold_s']:>5.0f}")


if __name__ == "__main__":
    main()
