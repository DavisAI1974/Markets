"""
lag_join.py — the FUTURES->KALSHI lag join (realized-EV of the echo, net-of-fee), two modes.

Thesis (Greg, S84/S87): NYMEX is the CANARY, Kalshi the DELAYED follower. The front-month future moves
first; the Kalshi daily-settle market (KXWTI / KXNATGASD, "will the close be above $X") reprices seconds-
to-minutes later. We WATCH the future, and the moment it makes a real move we lift the STALE Kalshi ATM
strike in that direction and ride the catch-up. NYMEX moving IS the trade; we stand aside otherwise.

Two modes, ONE trade engine (`simulate_trade`):
  * RELEASE  (default): anchor at the 14:30 EIA release, the one scheduled catalyst -> the S87 per-cell
    study (contract x surprise x coiled), over the mapped release events.
  * INTRADAY (--intraday): scan a whole day's CONTINUOUS tape (data/nymex_cont/) for EVERY sustained move
    -- the storage print is one catalyst; a headline / inventory leak / risk move all move NYMEX and
    Kalshi lags each one (Greg S87). Trade them all day.

Trade model (Greg S87, both modes):
  * ENTRY = TAKER, the moment the canary has moved trigger_usd DOLLARS and HELD for confirm_s (sustained,
    not a transient poke). All movement in $/c, never bps; trigger tuned PER CONTRACT.
  * STAND-BACK if Kalshi already moved with NYMEX before entry (caught up on its own -> no stale edge).
  * HOLD via a NYMEX DOLLAR TRAILING STOP (reverse_usd): ride through consistent movement / Kalshi whipsaw,
    exit only when the canary retraces reverse_usd from its favorable extreme (a real trend reversal). A
    fraction-of-run stop churns the fee on a trending day; the $-trailing stop rides the trend.
  * EXIT = MAKER "best number" (sell at the trend top into the still-buying herd, ~0 fee; fills only if the
    echo made a wave) vs the pure-TAKER floor (cross the spread). Report both, net-of-fee.

Discipline (kalshi-backtest): leakage-safe by construction (entry = canary direction + stale Kalshi mark,
both strictly <= entry; the trailing-stop exit is the forward outcome); settle-window bound; per-cell
never pooled; DISTRIBUTIONS not means; net-of-fee at taker AND (optimistic) maker. Zero synthetic.

Fee: fee_cents(P) = ceil(7*P*(1-P)), P=yes/100 (== round_up(0.07*C*P*(1-P)) per taker leg).

Usage:
    python research/kalshi/lag_join.py --selftest
    python research/kalshi/lag_join.py [--trig-sweep]                       # release-anchored per-cell study
    python research/kalshi/lag_join.py --intraday --day 20260617 --event KXWTI-26JUN1714 --root CL [-v]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import datetime as dt
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import event_move_baseline as emb                         # noqa: E402  (futures machinery, reused)
from odcore.leakage import assert_no_leakage              # noqa: E402

KALSHI_STORE = "data/kalshi_hist_trades"
CONT_DIR = "data/nymex_cont"
SURPRISE_FILE = "data/eia_surprise.json"
BIG_SURPRISE = {"KXNATGASD": 15.0, "KXWTI": 4.0}          # NG Bcf / CL Mbbl (S86 seasonal-proxy split)

# release day (YYYYMMDD) -> mapped settled Kalshi event (S87 survey). R = 14:30 UTC. 16 of 24 windows have
# a live Kalshi market: CL 10/12 (WTI daily launched early May), NG 6/12 (KXNATGASD launched ~Jun 3).
EVENTS = {
    "KXWTI": [
        ("20260506", "KXWTI-26MAY06"), ("20260513", "KXWTI-26MAY13"), ("20260520", "KXWTI-26MAY2014"),
        ("20260527", "KXWTI-26MAY2714"), ("20260603", "KXWTI-26JUN0314"), ("20260610", "KXWTI-26JUN1014"),
        ("20260617", "KXWTI-26JUN1714"), ("20260624", "KXWTI-26JUN2414"), ("20260701", "KXWTI-26JUL0114"),
        ("20260708", "KXWTI-26JUL0814"),
    ],
    "KXNATGASD": [
        ("20260604", "KXNATGASD-26JUN0417"), ("20260611", "KXNATGASD-26JUN1117"),
        ("20260618", "KXNATGASD-26JUN1817"), ("20260625", "KXNATGASD-26JUN2517"),
        ("20260702", "KXNATGASD-26JUL0217"), ("20260709", "KXNATGASD-26JUL0917"),
    ],
}
SERIES_ROOT = {"KXWTI": "CL", "KXNATGASD": "NG"}
ROOT_SERIES = {v: k for k, v in SERIES_ROOT.items()}
SETTLE_UTC = {"KXWTI": (18, 30), "KXNATGASD": (21, 0)}    # daily settle (UTC); hold bounded before this


def _iso_to_ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def fee_cents(price_cents: float) -> int:
    """Kalshi taker fee per contract in CENTS: ceil(7*P*(1-P)), P=price/100. Max ~2c at the 50c ATM."""
    P = max(0.0, min(1.0, price_cents / 100.0))
    return math.ceil(7.0 * P * (1.0 - P) - 1e-9)


def price_at(ts: np.ndarray, yes: np.ndarray, t: float):
    """Last trade price at/just before t (the observable mark). None if no trade yet."""
    i = int(np.searchsorted(ts, t, side="right")) - 1
    return None if i < 0 else float(yes[i])


# ---- kalshi echo tape (release-window or full-day slice) -------------------------------------------
def load_echo(series: str, event: str, suffix: str = "release"):
    """Grouped per-strike arrays from data/kalshi_hist_trades/<series>/<event>_<suffix>.jsonl.
    suffix='release' (14:30 window) or 'fullday' (whole session). -> {ticker:{ts,yes,floor}}."""
    path = os.path.join(KALSHI_STORE, series, f"{event}_{suffix}.jsonl")
    if not os.path.exists(path):
        return {}
    by = defaultdict(list)
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("ts") is None or r.get("yes_price") is None:
            continue
        by[r["ticker"]].append((_iso_to_ts(r["ts"]), float(r["yes_price"]), r.get("floor")))
    out = {}
    for tk, rows in by.items():
        rows.sort(key=lambda x: x[0])
        out[tk] = {"ts": np.array([r[0] for r in rows], float),
                   "yes": np.array([r[1] for r in rows], float), "floor": rows[0][2]}
    return out


def load_nymex_cont(root: str, day: str):
    """Continuous intraday NYMEX tape for one day -> (ts, price) arrays."""
    path = os.path.join(CONT_DIR, f"{root}_{day}.jsonl")
    rows = [json.loads(l) for l in open(path) if l.strip()]
    rows.sort(key=lambda r: r["ts"])
    return np.array([r["ts"] for r in rows], float), np.array([r["price"] for r in rows], float)


def pick_atm(echo: dict, t: float, lo_win: float = 300.0, hi_win: float = 300.0):
    """The liquid ATM strike near t: the strike with the most trades in [t-lo_win, t+hi_win], tie-broken
    to the one nearest 50c (max sensitivity to the underlying). hi_win=0 keeps it strictly pre-t."""
    best, best_key = None, None
    for tk, d in echo.items():
        m = (d["ts"] >= t - lo_win) & (d["ts"] <= t + hi_win)
        n = int(m.sum())
        if n == 0:
            continue
        near50 = -abs(float(np.median(d["yes"][m])) - 50.0)
        key = (n, near50)
        if best_key is None or key > best_key:
            best_key, best = key, tk
    return best


# ---- sustained-move detector (the NYMEX-driven entry trigger) --------------------------------------
def find_sustained_move(fts, fp, from_idx, until_t, trig_usd, confirm_s, base=None):
    """First SUSTAINED move at/after from_idx and <= until_t: |price-base| >= trig_usd (same dir) HELD for
    confirm_s (a transient poke that falls back inside resets). base defaults to fp[from_idx] (rolling
    anchor); pass the release baseline for release mode. Returns (ei, sign) or (None, None)."""
    b = base if base is not None else float(fp[from_idx])
    cross_sgn, cross_t0 = 0, None
    j = from_idx
    n = len(fp)
    while j < n and fts[j] <= until_t:
        d = float(fp[j]) - b
        if abs(d) >= trig_usd:
            sgn = 1 if d > 0 else -1
            if sgn != cross_sgn:
                cross_sgn, cross_t0 = sgn, float(fts[j])
            if float(fts[j]) - cross_t0 >= confirm_s:
                return j, float(sgn)
        else:
            cross_sgn, cross_t0 = 0, None
        j += 1
    return None, None


def scan_moves(fts, fp, trig_usd, confirm_s, cooldown_s, max_events=1000):
    """All sustained moves across the session (rolling anchor + cooldown so one swing isn't re-entered)."""
    out, i, n = [], 1, len(fp)
    while i < n and len(out) < max_events:
        ei, s = find_sustained_move(fts, fp, i, fts[i] + 600, trig_usd, confirm_s, base=float(fp[i]))
        if ei is None:
            i += 1
            continue
        out.append((ei, s))
        k = ei
        while k < n and fts[k] < fts[ei] + cooldown_s:
            k += 1
        i = k
    return out


# ---- the shared trade engine -----------------------------------------------------------------------
def simulate_trade(root, fts, fp, kts, kyes, ei, s, cfg, settle_bound):
    """One echo trade: taker entry at the stale Kalshi mark, stand-back guard, NYMEX $-trailing-stop hold,
    maker-best-number / taker-floor exit, net-of-fee. Returns the trade core dict or None."""
    t_entry = float(fts[ei])
    entry_mark = price_at(kts, kyes, t_entry)
    if entry_mark is None or entry_mark < 3 or entry_mark > 97:      # need a live, tradeable ATM
        return None
    slip, maker_off, min_wave = cfg["slip"], cfg["maker_off"], cfg["min_wave"]
    rev = cfg["reverse_usd"][root]
    # STAND-BACK: skip if Kalshi already moved in the NYMEX direction before entry (caught up on its own).
    kref = price_at(kts, kyes, t_entry - cfg["look_back"])
    if kref is not None and s * (entry_mark - kref) >= cfg["stale_cap"]:
        return None
    entry_px = entry_mark + s * slip                                # taker entry, adverse
    entry_fee = fee_cents(entry_px)

    # NYMEX DOLLAR TRAILING-STOP hold: ride the trend; exit on a reverse_usd retrace from the extreme.
    n = len(fp)
    ext_f = float(fp[ei])
    end_t = min(t_entry + cfg["max_hold"], settle_bound)
    t_dec = None
    j = ei + 1
    while j < n and fts[j] <= end_t:
        if s * (float(fp[j]) - ext_f) > 0:
            ext_f = float(fp[j])                                    # trend extending -> keep holding
        if s * (ext_f - float(fp[j])) >= rev:                       # retraced reverse_usd -> trend broke
            t_dec = float(fts[j]); break
        j += 1
    if t_dec is None:
        t_dec = end_t

    kfwd = (kts > t_entry) & (kts <= t_dec)
    ext = entry_mark
    if kfwd.any():
        e = float((np.max if s > 0 else np.min)(kyes[kfwd]))
        ext = e if s * (e - entry_mark) > 0 else entry_mark
    exit_mark = price_at(kts, kyes, t_dec)
    if exit_mark is None:
        return None
    wave = s * (ext - entry_mark)                                   # favorable Kalshi carry (c)
    taker_exit = exit_mark - s * slip
    pnl_taker = s * (taker_exit - entry_px) - entry_fee - fee_cents(taker_exit)
    if wave >= min_wave:
        maker_filled = 1
        pnl_maker = s * ((ext - s * maker_off) - entry_px) - entry_fee - 0
    else:
        maker_filled = 0
        pnl_maker = pnl_taker
    return {"t_entry": t_entry, "dir": "up" if s > 0 else "dn", "entry_px": round(entry_px, 2),
            "ext": round(ext, 2), "wave": round(float(wave), 2), "maker_filled": maker_filled,
            "pnl_taker": round(float(pnl_taker), 3), "pnl_maker": round(float(pnl_maker), 3),
            "hold_used": round(t_dec - t_entry, 1)}


# ---- RELEASE mode ----------------------------------------------------------------------------------
def simulate_event(series, day, event, fut, cfg):
    """One release-anchored echo trade (the 14:30 catalyst)."""
    root = SERIES_ROOT[series]
    y, m, d = int(day[:4]), int(day[4:6]), int(day[6:8])
    R = dt.datetime(y, m, d, 14, 30, tzinfo=dt.timezone.utc).timestamp()
    sh, sm = SETTLE_UTC[series]
    settle = dt.datetime(y, m, d, sh, sm, tzinfo=dt.timezone.utc).timestamp()
    fts, fp, fsz = fut
    ri = int(np.searchsorted(fts, R, side="right")) - 1
    if ri < 1:
        return None
    base = float(fp[ri])
    ei, s = find_sustained_move(fts, fp, ri, R + cfg["max_wait"], cfg["trigger_usd"][root],
                                cfg["confirm_s"], base=base)
    if ei is None:
        return None
    echo = load_echo(series, event, "release")
    atm = pick_atm(echo, R) if echo else None
    if atm is None:
        return None
    kts, kyes = echo[atm]["ts"], echo[atm]["yes"]
    tr = simulate_trade(root, fts, fp, kts, kyes, ei, s, cfg, settle - cfg["settle_buffer"])
    if tr is None:
        return None
    tr.update({"series": series, "root": root, "day": day, "event": event, "atm": atm,
               "fmove": round(float(fp[ei]) - base, 4), "trigger_lag": round(tr["t_entry"] - R, 1)})
    return tr


def coiled_flag(root, fut, R, pre_s=120.0):
    fts, fp, fsz = fut
    ri = int(np.searchsorted(fts, R, side="right")) - 1
    if ri < 1:
        return "coiled=unknown"
    pv = emb.pre_release_volume(ri, fts, fsz, pre_s)
    return "coiled" if pv["coiled_ratio"] < 1.0 else "active"


def cell_of(series, day, surprise_map):
    pr = surprise_map.get(f"{day[:4]}-{day[4:6]}-{day[6:8]}")
    surp = pr.get("surprise") if pr else None
    return emb.surprise_cell(series, surp, BIG_SURPRISE[series]), int(day[4:6])


def run_release(cfg):
    surprise_map_all = emb.load_surprise_file(SURPRISE_FILE)
    rows, fut_cache = [], {}
    for series, evs in EVENTS.items():
        root = SERIES_ROOT[series]
        fut = fut_cache.setdefault(root, emb.load_tape(root))
        smap = surprise_map_all.get(series, {})
        for day, event in evs:
            row = simulate_event(series, day, event, fut, cfg)
            if row is None:
                continue
            y, m, d = int(day[:4]), int(day[4:6]), int(day[6:8])
            R = dt.datetime(y, m, d, 14, 30, tzinfo=dt.timezone.utc).timestamp()
            row["scell"], row["month"] = cell_of(series, day, smap)
            row["coiled"] = coiled_flag(root, fut, R)
            rows.append(row)
    return rows


# ---- INTRADAY mode ---------------------------------------------------------------------------------
def run_intraday(day, event, root, cfg):
    """Scan a day's continuous tape for every sustained move and trade each Kalshi echo."""
    series = ROOT_SERIES[root]
    fts, fp = load_nymex_cont(root, day)
    echo = load_echo(series, event, "fullday")
    sh, sm = SETTLE_UTC[series]
    y, m, d = int(day[:4]), int(day[4:6]), int(day[6:8])
    settle = dt.datetime(y, m, d, sh, sm, tzinfo=dt.timezone.utc).timestamp()
    moves = scan_moves(fts, fp, cfg["trigger_usd"][root], cfg["confirm_s"], cfg["cooldown_s"])
    trades = []
    for ei, s in moves:
        atm = pick_atm(echo, float(fts[ei]), lo_win=600.0, hi_win=0.0)   # strictly pre-entry ATM
        if atm is None:
            continue
        tr = simulate_trade(root, fts, fp, echo[atm]["ts"], echo[atm]["yes"], ei, s, cfg,
                            settle - cfg["settle_buffer"])
        if tr:
            tr["atm"] = atm
            trades.append(tr)
    return fts, len(moves), trades


# ---- reporting -------------------------------------------------------------------------------------
def _q(a, ps):
    return [round(float(np.percentile(a, p)), 2) for p in ps] if len(a) else [None] * len(ps)


def report(rows, group_keys, title):
    print(f"\n=== {title} ===")
    print(f"{'cell':<30} {'n':>3} {'taker: pos% med [p25,p75]':<28} {'maker: pos% med [p25,p75] fill%':<34}")
    groups = defaultdict(list)
    for r in rows:
        groups[tuple(r[k] for k in group_keys)].append(r)
    for key, rs in sorted(groups.items()):
        tk = np.array([r["pnl_taker"] for r in rs], float)
        mk = np.array([r["pnl_maker"] for r in rs], float)
        fill = 100.0 * np.mean([r["maker_filled"] for r in rs])
        tq, mq = _q(tk, [25, 50, 75]), _q(mk, [25, 50, 75])
        label = "|".join(str(k) for k in key)
        print(f"{label:<30} {len(rs):>3} "
              f"{100*np.mean(tk>0):>4.0f}% {tq[1]:>5}c [{tq[0]},{tq[2]}]".ljust(28) + "  "
              f"{100*np.mean(mk>0):>4.0f}% {mq[1]:>5}c [{mq[0]},{mq[2]}] {fill:>3.0f}%")


def _cfg_from_args(args):
    return {"trigger_usd": {"CL": args.trigger_cl, "NG": args.trigger_ng},
            "reverse_usd": {"CL": args.reverse_cl, "NG": args.reverse_ng},
            "max_wait": args.max_wait, "confirm_s": args.confirm_s, "cooldown_s": args.cooldown_s,
            "stale_cap": args.stale_cap, "look_back": args.look_back, "slip": args.slip,
            "maker_off": args.maker_off, "min_wave": args.min_wave, "max_hold": args.max_hold,
            "settle_buffer": args.settle_buffer}


# ---- selftest (leakage closure + fee math; tiny constructed arrays, no synthetic trades) -----------
def selftest():
    ok = True
    assert fee_cents(50) == 2 and fee_cents(90) == 1 and fee_cents(100) == 0 and fee_cents(0) == 0
    print("  ok  fee_cents: 50c->2c, 90c->1c, edges->0")
    ts = np.arange(20, dtype=float)
    p = 100.0 + np.cumsum(np.ones(20))
    z = np.zeros(20)
    base_i = 3

    def dir_at(i, ts_, p_, bv_, sv_):
        return None if i <= base_i else round(float(np.sign(p_[i] - p_[base_i])), 3)
    dp, dfl = assert_no_leakage(dir_at, ts, p, z, z, idxs=[8, 12], reps=3, seed=0)
    print("  ok  future-direction closure invariant to post-entry ticks" if dp else f"  FAIL dir leak {dfl}")

    def mark_at(i, ts_, p_, bv_, sv_):
        return round(float(p_[i]), 3)
    mp, mfl = assert_no_leakage(mark_at, ts, p, z, z, idxs=[8, 12], reps=3, seed=1)
    print("  ok  kalshi entry-mark closure invariant to post-entry ticks" if mp else f"  FAIL mark leak {mfl}")

    # sustained-move detector: a 1-tick poke must NOT trigger; a held move MUST.
    fts2 = np.arange(10, dtype=float)
    poke = np.array([50, 50, 60, 50, 50, 50, 50, 50, 50, 50], float)      # spikes 1 tick then reverts
    ei_p, _ = find_sustained_move(fts2, poke, 0, 9, 5, confirm_s=2)
    held = np.array([50, 50, 60, 61, 62, 63, 64, 65, 66, 67], float)      # crosses and holds
    ei_h, _ = find_sustained_move(fts2, held, 0, 9, 5, confirm_s=2)
    okm = (ei_p is None) and (ei_h is not None)
    print("  ok  sustained-move detector rejects poke / accepts held move" if okm else "  FAIL detector")
    ok = dp and mp and okm
    print("SELFTEST", "PASS" if ok else "FAIL")
    return ok


def main():
    ap = argparse.ArgumentParser(description="Futures->Kalshi lag join (release + intraday modes)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--intraday", action="store_true", help="scan a day's continuous tape (needs --day/--event/--root)")
    ap.add_argument("--day"); ap.add_argument("--event"); ap.add_argument("--root", choices=["CL", "NG"])
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--trigger-cl", type=float, default=0.20, help="WTI entry trigger ($ NYMEX move)")
    ap.add_argument("--trigger-ng", type=float, default=0.03, help="NatGas entry trigger ($ NYMEX move)")
    ap.add_argument("--reverse-cl", type=float, default=0.30, help="WTI trailing-stop retrace ($) to exit")
    ap.add_argument("--reverse-ng", type=float, default=0.04, help="NatGas trailing-stop retrace ($) to exit")
    ap.add_argument("--max-wait", type=float, default=300.0, help="release: give up if NYMEX quiet by then (s)")
    ap.add_argument("--confirm-s", type=float, default=5.0, help="canary must HOLD beyond trigger this many s")
    ap.add_argument("--cooldown-s", type=float, default=180.0, help="intraday: min gap between entries (s)")
    ap.add_argument("--stale-cap", type=float, default=12.0, help="stand back if Kalshi already moved this many c")
    ap.add_argument("--look-back", type=float, default=180.0, help="stand-back reference lookback (s)")
    ap.add_argument("--slip", type=float, default=1.0, help="adverse taker slippage per fill (c)")
    ap.add_argument("--maker-off", type=float, default=1.0, help="maker haircut off the exact extreme (c)")
    ap.add_argument("--min-wave", type=float, default=1.0, help="min favorable echo (c) for a maker fill")
    ap.add_argument("--max-hold", type=float, default=3600.0, help="max hold (s), bounded before settle")
    ap.add_argument("--settle-buffer", type=float, default=1800.0, help="stop this many s before settle")
    ap.add_argument("--trig-sweep", action="store_true", help="release: EV-vs-trigger curve, per contract")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)
    cfg = _cfg_from_args(args)

    if args.intraday:
        if not (args.day and args.event and args.root):
            ap.error("--intraday needs --day, --event and --root")
        fts, n_moves, trades = run_intraday(args.day, args.event, args.root, cfg)
        s0, s1 = (dt.datetime.fromtimestamp(fts[0], dt.timezone.utc),
                  dt.datetime.fromtimestamp(fts[-1], dt.timezone.utc))
        print(f"\nINTRADAY LAG JOIN — {args.root} {args.day} ({args.event}), session "
              f"{s0:%H:%M}-{s1:%H:%M} UTC, {len(fts)} NYMEX ticks")
        print(f"trigger ${cfg['trigger_usd'][args.root]:.2f} confirm {args.confirm_s:.0f}s "
              f"cooldown {args.cooldown_s:.0f}s reverse-stop ${cfg['reverse_usd'][args.root]:.2f} (hold the trend)")
        print(f"{n_moves} sustained NYMEX moves -> {len(trades)} tradeable echoes (rest: no live ATM / stood back)")
        if trades:
            tk = np.array([t["pnl_taker"] for t in trades]); mk = np.array([t["pnl_maker"] for t in trades])
            fill = 100 * np.mean([t["maker_filled"] for t in trades])
            for nm, a, extra in [("taker", tk, ""), ("maker", mk, f" fill {fill:.0f}%")]:
                print(f"  {nm:6} n={len(a):>2}  pos {100*np.mean(a>0):>3.0f}%  med {np.median(a):+5.1f}c  "
                      f"mean {np.mean(a):+5.1f}c  sum {np.sum(a):+6.0f}c  "
                      f"[p25 {np.percentile(a,25):+.0f}, p75 {np.percentile(a,75):+.0f}]{extra}")
            if args.verbose:
                print(f"\n{'t_entry':>8} {'dir':>3} {'atm':>22} {'entry':>5} {'ext':>5} {'wave':>5} "
                      f"{'pnlT':>5} {'pnlM':>5} {'hold':>5}")
                for t in trades:
                    hh = dt.datetime.fromtimestamp(t["t_entry"], dt.timezone.utc).strftime("%H:%M:%S")
                    print(f"{hh:>8} {t['dir']:>3} {t['atm']:>22} {t['entry_px']:>5} {t['ext']:>5} "
                          f"{t['wave']:>5} {t['pnl_taker']:>5} {t['pnl_maker']:>5} {t['hold_used']:>5.0f}")
        return

    # RELEASE mode (default)
    rows = run_release(cfg)
    print(f"\nLAG JOIN (release) — {len(rows)} echo trades  (trigger CL=${args.trigger_cl:.2f} "
          f"NG=${args.trigger_ng:.3f}, reverse-stop CL=${args.reverse_cl:.2f} NG=${args.reverse_ng:.3f}; "
          f"ENTRY+HOLD+EXIT all NYMEX-driven, $/c)")
    print("net-of-fee CENTS/contract; ENTRY taker; EXIT maker-best-number-w-taker-fallback vs pure-taker floor")
    report(rows, ["root"], "per contract")
    report(rows, ["root", "scell"], "per contract x surprise cell")
    report(rows, ["root", "coiled"], "per contract x coiled/primed gate")
    tk = np.array([r["pnl_taker"] for r in rows], float); mk = np.array([r["pnl_maker"] for r in rows], float)
    print(f"\n[pooled footnote] taker med {np.median(tk):+.2f}c pos {100*np.mean(tk>0):.0f}% | "
          f"maker med {np.median(mk):+.2f}c pos {100*np.mean(mk>0):.0f}% "
          f"fill {100*np.mean([r['maker_filled'] for r in rows]):.0f}%")

    if args.trig_sweep:
        print("\n[trigger sweep — EV-vs-threshold, tuned PER CONTRACT in $ (Greg S87)]")
        grids = {"CL": (0.05, 0.10, 0.15, 0.20, 0.30, 0.50), "NG": (0.005, 0.01, 0.02, 0.03, 0.05, 0.08)}
        for root in ("CL", "NG"):
            print(f"  {root} (trigger in $ of {'crude' if root == 'CL' else 'gas'}):")
            for trig in grids[root]:
                rr = [r for r in run_release(dict(cfg, trigger_usd={**cfg["trigger_usd"], root: trig}))
                      if r["root"] == root]
                if rr:
                    tk = np.array([r["pnl_taker"] for r in rr]); mk = np.array([r["pnl_maker"] for r in rr])
                    print(f"    trig>=${trig:>5.3f}  n={len(rr):>2}  "
                          f"taker {np.median(tk):+5.1f}c/{100*np.mean(tk>0):>3.0f}%  "
                          f"maker {np.median(mk):+5.1f}c/{100*np.mean(mk>0):>3.0f}%  "
                          f"fill {100*np.mean([r['maker_filled'] for r in rr]):>3.0f}%")


if __name__ == "__main__":
    main()
