"""
lag_join.py — the FUTURES->KALSHI lag join (the realized echo move, GROSS), two modes.

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
    fraction-of-run stop churns on a trending day; the $-trailing stop rides the trend.
  * EXIT readouts: at the favorable Kalshi EXTREME (only if the echo made a wave >= min_wave) vs at the
    mark when the trailing stop fires. Report both, gross, in cents per contract.

Discipline (kalshi-backtest): leakage-safe by construction (entry = canary direction + stale Kalshi mark,
both strictly <= entry; the trailing-stop exit is the forward outcome); settle-window bound; per-cell
never pooled; DISTRIBUTIONS not means. Zero synthetic.

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
    exit at the mark or at the favorable extreme, GROSS. Returns the trade core
    dict or None. Reports the stop mark and the qualifying favorable extreme."""
    t_entry = float(fts[ei])
    entry_mark = price_at(kts, kyes, t_entry)
    if entry_mark is None or entry_mark < 3 or entry_mark > 97:      # need a live, tradeable ATM
        return None
    min_wave = cfg["min_wave"]
    rev = cfg["reverse_usd"][root]
    # STAND-BACK: skip if Kalshi already moved in the NYMEX direction before entry (caught up on its own).
    kref = price_at(kts, kyes, t_entry - cfg["look_back"])
    if kref is not None and s * (entry_mark - kref) >= cfg["stale_cap"]:
        return None
    entry_px = entry_mark                                           # entry at the stale mark, gross

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
    gross_at_stop_cents = s * (exit_mark - entry_px)                         # gross move to the stop-fire mark
    if wave >= min_wave:
        wave_qualified = 1
        gross_at_extreme_cents = s * (ext - entry_px)                           # gross move to the favorable extreme
    else:
        wave_qualified = 0
        gross_at_extreme_cents = None
    return {"t_entry": t_entry, "dir": "up" if s > 0 else "dn", "entry_px": round(entry_px, 2),
            "ext": round(ext, 2), "wave": round(float(wave), 2), "wave_qualified": wave_qualified,
            "gross_at_stop_cents": round(float(gross_at_stop_cents), 3),
            "gross_at_extreme_cents": (None if gross_at_extreme_cents is None
                                       else round(float(gross_at_extreme_cents), 3)),
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
def report(rows, group_keys, title):
    print(f"\n=== {title} ===")
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in group_keys)].append(row)
    for key, records in sorted(groups.items()):
        label = "|".join(str(value) for value in key)
        stop = [row["gross_at_stop_cents"] for row in records]
        extreme = [row["gross_at_extreme_cents"] for row in records]
        print(f"{label} n={len(records)} stop_cents={stop} extreme_cents={extreme}")


def _cfg_from_args(args):
    return {"trigger_usd": {"CL": args.trigger_cl, "NG": args.trigger_ng},
            "reverse_usd": {"CL": args.reverse_cl, "NG": args.reverse_ng},
            "max_wait": args.max_wait, "confirm_s": args.confirm_s, "cooldown_s": args.cooldown_s,
            "stale_cap": args.stale_cap, "look_back": args.look_back, "min_wave": args.min_wave, "max_hold": args.max_hold,
            "settle_buffer": args.settle_buffer}


# ---- selftest (leakage closure; tiny constructed arrays, no synthetic trades) ----------------------
def selftest():
    ok = True
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
    ap.add_argument("--min-wave", type=float, default=1.0, help="min favorable echo (c) to qualify the extreme")
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
        report(trades, ["dir"], "observed moves by direction")
        if args.verbose:
            for trade in trades:
                print(trade)
        return

    # RELEASE mode (default)
    rows = run_release(cfg)
    print(f"\nLAG JOIN (release) — {len(rows)} echo trades  (trigger CL=${args.trigger_cl:.2f} "
          f"NG=${args.trigger_ng:.3f}, reverse-stop CL=${args.reverse_cl:.2f} NG=${args.reverse_ng:.3f}; "
          f"ENTRY+HOLD+EXIT all NYMEX-driven, $/c)")
    print("GROSS CENTS/contract; gross_at_stop_cents = exit at stop-fire mark; gross_at_extreme_cents = exit at favorable extreme when wave >= min_wave")
    report(rows, ["root"], "per contract")
    report(rows, ["root", "scell"], "per contract x surprise cell")
    report(rows, ["root", "coiled"], "per contract x coiled/primed gate")
    if args.trig_sweep:
        print("\n[trigger sweep — EV-vs-threshold, tuned PER CONTRACT in $ (Greg S87)]")
        grids = {"CL": (0.05, 0.10, 0.15, 0.20, 0.30, 0.50), "NG": (0.005, 0.01, 0.02, 0.03, 0.05, 0.08)}
        for root in ("CL", "NG"):
            print(f"  {root} (trigger in $ of {'crude' if root == 'CL' else 'gas'}):")
            for trig in grids[root]:
                rr = [r for r in run_release(dict(cfg, trigger_usd={**cfg["trigger_usd"], root: trig}))
                      if r["root"] == root]
                if rr:
                    report(rr, ["dir"], f"trigger >= ${trig:.3f}")


if __name__ == "__main__":
    main()
