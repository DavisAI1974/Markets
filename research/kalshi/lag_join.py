"""
lag_join.py — P3: the FUTURES->KALSHI lag join (realized-EV of the echo, net-of-fee).

The thesis (Greg, S84/S87): NYMEX is the CANARY, Kalshi the DELAYED follower. On an EIA release the
front-month future moves first; the Kalshi daily-settle market (KXWTI / KXNATGASD, "will the close be
above $X") reprices SECONDS-TO-MINUTES later. Because we get to WATCH the future move for ~a minute
before Kalshi catches up, the entry direction is OBSERVED, not predicted -> we lift the stale Kalshi
strike in the direction the future already went, and ride the catch-up.

This turns the S85/S86 futures-move CEILING into REALIZED-EV: does the echo pay AFTER the Kalshi fee?

Trade model (Greg, S87):
  * ENTRY  = TAKER. At t_entry = R + tau (tau = how long we watch the future), take the future's observed
             direction and LIFT the stale Kalshi ATM strike. Entry is taker because the market is stale
             (we cross to get in before it reprices).
  * RIDE   = a run-length-guided hold (NG front-loaded ~60s, CL slower; from event_move_baseline).
  * EXIT   = MAKER at the best number, SHORT leash, TAKER fallback. Rest the close at/just above the
             current top-of-book (the "best number" -- a momentum buyer lifts it thinking they poached the
             last good fill while we are happy to be out). If the wave does not take it within a short
             patience window, do NOT sit -> fire taker immediately.
  * BASE   = pure TAKER exit at the hold horizon (the realistic floor to compare the maker exit against).

Discipline (kalshi-backtest skill): leakage gate on the ENTRY closure (direction + entry mark must be
invariant to any tape after t_entry); settle-window bound (hold cannot run past the daily settle);
per-cell never pooled (contract x surprise x coiled x season); DISTRIBUTIONS not means; NET-OF-FEE at
taker AND (optimistic) maker. Zero synthetic data. Provisional-until-live.

Kalshi fee: fee_cents(P) = ceil(7 * P * (1-P)), P = yes_price/100 (== round_up(0.07*C*P*(1-P)) per
contract per taker leg). Maker fill modeled ~0 fee (optimistic; flagged with fill-risk).

Data (all local / already pulled):
  * futures canary tape  data/pyth_ticks/{CL,NG}_YYYYMMDD.jsonl   (databento true ticks; via load_tape)
  * kalshi echo tape     data/kalshi_hist_trades/{KXWTI,KXNATGASD}/<event>_release.jsonl  (signed trades)
  * surprise             data/eia_surprise.json                    (seasonal-proxy; eia_surprise.py)

Usage:
    python research/kalshi/lag_join.py --selftest         # leakage-closure + fee math unit check
    python research/kalshi/lag_join.py                    # run the join, per-cell tables
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
SURPRISE_FILE = "data/eia_surprise.json"
BIG_SURPRISE = {"KXNATGASD": 15.0, "KXWTI": 4.0}          # NG Bcf / CL Mbbl (S86 seasonal-proxy split)

# release day (YYYYMMDD) -> mapped settled Kalshi event (from the S87 survey). R = 14:30 UTC that day.
# 16 of 24 windows have a live Kalshi market: CL 10/12 (WTI daily launched early May), NG 6/12
# (KXNATGASD launched ~Jun 3). The gaps are market-existence, not signal.
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
# daily settle (UTC) — hold is bounded strictly before this (settle-window exclusion).
SETTLE_UTC = {"KXWTI": (18, 30), "KXNATGASD": (21, 0)}


def _iso_to_ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def fee_cents(price_cents: float) -> int:
    """Kalshi taker fee per contract, in CENTS: ceil(7 * P * (1-P)), P = price/100.
    == round_up(0.07 * C * P * (1-P)) for C=1 (dollars) expressed in cents. Max ~2c at the 50c ATM."""
    P = max(0.0, min(1.0, price_cents / 100.0))
    return math.ceil(7.0 * P * (1.0 - P) - 1e-9)


# ---- kalshi echo tape ------------------------------------------------------------------------------
def load_echo(series: str, event: str):
    """Load the pulled release-window trades for one event, grouped per strike into time-sorted arrays.
    Returns {ticker: {'ts':arr, 'yes':arr(cents), 'side':list, 'floor':float}}."""
    path = os.path.join(KALSHI_STORE, series, f"{event}_release.jsonl")
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
        by[r["ticker"]].append((_iso_to_ts(r["ts"]), float(r["yes_price"]),
                                r.get("taker_side"), r.get("floor")))
    out = {}
    for tk, rows in by.items():
        rows.sort(key=lambda x: x[0])
        out[tk] = {"ts": np.array([r[0] for r in rows], float),
                   "yes": np.array([r[1] for r in rows], float),
                   "side": [r[2] for r in rows],
                   "floor": rows[0][3]}
    return out


def pick_atm(echo: dict, R: float, win: float = 300.0):
    """The ATM strike at the release = the strike with the most trades in [R-win, R+win] (the liquid
    at-the-money rung the future move will reprice). Ties -> the one whose price is nearest 50c."""
    best, best_key = None, None
    for tk, d in echo.items():
        m = (d["ts"] >= R - win) & (d["ts"] <= R + win)
        n = int(m.sum())
        if n == 0:
            continue
        near50 = -abs(float(np.median(d["yes"][m])) - 50.0)
        key = (n, near50)
        if best_key is None or key > best_key:
            best_key, best = key, tk
    return best


def price_at(ts: np.ndarray, yes: np.ndarray, t: float):
    """Last trade price at/just before t (the observable mark). None if no trade yet."""
    i = int(np.searchsorted(ts, t, side="right")) - 1
    return None if i < 0 else float(yes[i])


# ---- the trade simulation --------------------------------------------------------------------------
def simulate_event(series, day, event, fut, cfg):
    """One echo trade for one event. Returns a row dict or None (no future dir / no echo / no ATM)."""
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
    # ---- NYMEX-DRIVEN ENTRY (Greg S87): watch the canary in real time and enter the MOMENT it has
    # clearly moved by trigger_usd DOLLARS after R -- adaptive timing, not a fixed clock. All movements
    # in $ / c, never bps (Greg), and the trigger is tuned PER CONTRACT (same scaffold, different values:
    # WTI ~$0.10-0.20 of a ~$77 barrel, NG ~$0.02-0.03 of ~$3 gas). NYMEX moving IS the trade; if the
    # canary never moves that much within max_wait, we DON'T trade. This is the purpose of the RT tape.
    trig_usd, max_wait, confirm_s = cfg["trigger_usd"][root], cfg["max_wait"], cfg["confirm_s"]
    scan = np.where((fts > R) & (fts <= R + max_wait))[0]
    # SUSTAINED-move entry (Greg S87): "NYMEX moved" must mean a move that HELD, not a one-tick poke that
    # reverts. Require the canary to stay beyond trig_usd (same direction) for confirm_s before firing --
    # a transient spike that falls back inside resets and does NOT trigger us.
    ei = None; cross_t0, cross_sgn = None, 0
    for idx in scan:
        d = float(fp[idx]) - base
        if abs(d) >= trig_usd:
            sgn = 1 if d > 0 else -1
            if sgn != cross_sgn:                                     # first tick of a breakout this way
                cross_sgn, cross_t0 = sgn, float(fts[idx])
            if float(fts[idx]) - cross_t0 >= confirm_s:              # breakout HELD for confirm_s -> confirmed
                ei = int(idx); break
        else:
            cross_sgn, cross_t0 = 0, None                           # fell back inside -> it was a poke, reset
    if ei is None:
        return None
    t_entry = float(fts[ei])
    fmove = float(fp[ei]) - base                                    # the canary move ($) that TRIGGERED entry
    s = 1.0 if fmove > 0 else -1.0                                  # +1 long yes, -1 short yes
    trigger_lag = round(t_entry - R, 1)                            # how fast the canary moved (front-loaded?)

    echo = load_echo(series, event)
    if not echo:
        return None
    atm_tk = pick_atm(echo, R)
    if atm_tk is None:
        return None
    kts, kyes = echo[atm_tk]["ts"], echo[atm_tk]["yes"]

    entry_mark = price_at(kts, kyes, t_entry)
    if entry_mark is None:
        return None
    slip = cfg["slip"]
    # entry is TAKER, adverse: buying (s>0) pays UP, selling (s<0) sells DOWN
    entry_px = entry_mark + s * slip
    entry_fee = fee_cents(entry_px)

    # ---- STAND-BACK (Greg S87): our edge is entering while Kalshi is STALE vs NYMEX. If Kalshi has
    # ALREADY moved in the NYMEX direction by entry (caught up on its own / a Kalshi-led move), there is
    # no stale edge left -> stand back. NYMEX is the trigger; a Kalshi-led move is not our trade.
    kR = price_at(kts, kyes, R)
    if kR is not None and s * (entry_mark - kR) >= cfg["stale_cap"]:
        return None

    # ---- NYMEX-DRIVEN exit (Greg S87): watch the LEADER the whole time. HOLD through Kalshi's own
    # whipsaw; exit at the END of the NYMEX move -- when the canary gives back (1-retain_frac) of its
    # favorable run from R. We ride on the leader, not the follower's chop.
    sb = settle - cfg["settle_buffer"]                              # settle-window exclusion bound
    fN = np.where((fts > t_entry) & (fts <= sb))[0]
    if fN.size == 0:
        return None
    retain, maker_off, min_wave = cfg["retain_frac"], cfg["maker_off"], cfg["min_wave"]
    peak_fav = max(0.0, s * (float(fp[ei]) - base))                # NYMEX favorable run so far (at entry)
    t_dec = None
    for idx in fN:
        dN = s * (float(fp[idx]) - base)                           # NYMEX favorable displacement from R
        if dN > peak_fav:
            peak_fav = dN                                         # canary still advancing -> keep holding
        if peak_fav > 0 and dN < retain * peak_fav:               # canary gave it back -> the move is over
            t_dec = float(fts[idx]); break
    if t_dec is None:                                             # NYMEX never reverted -> ride to settle bound
        t_dec = float(fts[fN[-1]])

    # Kalshi outcome at the NYMEX-decided exit time: the favorable Kalshi extreme reached while we rode.
    kfwd = np.where((kts > t_entry) & (kts <= t_dec))[0]
    ext = entry_mark
    for idx in kfwd:
        px = float(kyes[idx])
        if s * (px - ext) > 0:
            ext = px
    exit_mark = price_at(kts, kyes, t_dec)
    if exit_mark is None:
        return None
    wave = s * (ext - entry_mark)                                  # how far the echo carried in our favor (c)

    # ---- BASE: pure TAKER exit at the NYMEX-decided time -- the realistic floor (cross the spread). ----
    taker_exit_px = exit_mark - s * slip                           # adverse: sell into bid / buy at ask
    pnl_taker = s * (taker_exit_px - entry_px) - entry_fee - fee_cents(taker_exit_px)

    # ---- PRIMARY: maker "best number" -- rest the close at the TOP and let the still-buying herd lift it
    #      (no exit fee, no adverse cross). Fills only if the echo made a wave to sell into (>= min_wave);
    #      concede a small haircut off the exact tick. Else -> the taker floor. Optimistic; fill-risk. ----
    if wave >= min_wave:
        maker_filled = 1
        maker_exit_px = ext - s * maker_off
        pnl_maker = s * (maker_exit_px - entry_px) - entry_fee - 0
    else:
        maker_filled = 0
        pnl_maker = pnl_taker

    return {
        "series": series, "root": root, "day": day, "event": event, "atm": atm_tk,
        "fmove": round(fmove, 4), "dir": "up" if s > 0 else "dn", "trigger_lag": trigger_lag,
        "entry_px": round(entry_px, 2), "taker_exit_px": round(taker_exit_px, 2),
        "ext": round(ext, 2), "wave": round(float(wave), 2), "maker_filled": maker_filled,
        "pnl_taker": round(float(pnl_taker), 3), "pnl_maker": round(float(pnl_maker), 3),
        "hold_used": round(t_dec - t_entry, 1),
    }


# ---- cells + reporting -----------------------------------------------------------------------------
def coiled_flag(root, fut, R, pre_s=120.0):
    """Coiled/primed detector on the FUTURE tape (Greg S86): coiled_ratio<1 = volume drying up into the
    release. Leakage-safe (strictly pre-R). Returns 'coiled' / 'active'."""
    fts, fp, fsz = fut
    ri = int(np.searchsorted(fts, R, side="right")) - 1
    if ri < 1:
        return "coiled=unknown"
    pv = emb.pre_release_volume(ri, fts, fsz, pre_s)
    return "coiled" if pv["coiled_ratio"] < 1.0 else "active"


def cell_of(series, day, row, surprise_map):
    root = SERIES_ROOT[series]
    iso = f"{day[:4]}-{day[4:6]}-{day[6:8]}"
    pr = surprise_map.get(iso)
    surp = pr.get("surprise") if pr else None
    scell = emb.surprise_cell(series, surp, BIG_SURPRISE[series])
    month = int(day[4:6])
    return scell, month


def _q(a, ps):
    if not len(a):
        return [None] * len(ps)
    return [round(float(np.percentile(a, p)), 2) for p in ps]


def report(rows, group_keys, title):
    print(f"\n=== {title} ===")
    print(f"{'cell':<30} {'n':>3} {'taker: pos% med [p25,p75]':<28} {'maker: pos% med [p25,p75] fill%':<34}")
    groups = defaultdict(list)
    for r in rows:
        groups[tuple(r[k] for k in group_keys)].append(r)
    for key, rs in sorted(groups.items()):
        n = len(rs)
        tk = np.array([r["pnl_taker"] for r in rs], float)
        mk = np.array([r["pnl_maker"] for r in rs], float)
        fill = 100.0 * np.mean([r["maker_filled"] for r in rs])
        tk_pos = 100.0 * np.mean(tk > 0)
        mk_pos = 100.0 * np.mean(mk > 0)
        tq = _q(tk, [25, 50, 75])
        mq = _q(mk, [25, 50, 75])
        label = "|".join(str(k) for k in key)
        print(f"{label:<30} {n:>3} "
              f"{tk_pos:>4.0f}% {tq[1]:>5}c [{tq[0]},{tq[2]}]".ljust(28) + "  "
              f"{mk_pos:>4.0f}% {mq[1]:>5}c [{mq[0]},{mq[2]}] {fill:>3.0f}%")


def run(cfg):
    surprise_map_all = emb.load_surprise_file(SURPRISE_FILE)
    all_rows = []
    fut_cache = {}
    for series, evs in EVENTS.items():
        root = SERIES_ROOT[series]
        if root not in fut_cache:
            fut_cache[root] = emb.load_tape(root)
        fut = fut_cache[root]
        smap = surprise_map_all.get(series, {})
        for day, event in evs:
            row = simulate_event(series, day, event, fut, cfg)
            if row is None:
                continue
            y, m, d = int(day[:4]), int(day[4:6]), int(day[6:8])
            R = dt.datetime(y, m, d, 14, 30, tzinfo=dt.timezone.utc).timestamp()
            scell, month = cell_of(series, day, row, smap)
            row["scell"] = scell
            row["coiled"] = coiled_flag(root, fut, R)
            row["month"] = month
            all_rows.append(row)
    return all_rows


# ---- selftest (leakage closure + fee math; tiny constructed arrays, no synthetic trades) -----------
def selftest():
    ok = True
    # fee math
    assert fee_cents(50) == 2, fee_cents(50)
    assert fee_cents(90) == 1, fee_cents(90)
    assert fee_cents(99) == 1 or fee_cents(99) == 0
    assert fee_cents(100) == 0 and fee_cents(0) == 0
    print("  ok  fee_cents: 50c->2c, 90c->1c, edges->0")

    # leakage: the ENTRY closure (future direction + entry mark) must be invariant to any tape after
    # t_entry. Two closures, each gated on its own tape via assert_no_leakage.
    ts = np.arange(20, dtype=float)                    # 20 evenly-spaced ticks
    p = 100.0 + np.cumsum(np.ones(20))                 # monotone rising price
    z = np.zeros(20)
    # future-direction-at-i = sign(p[i]-p[base]) read only from p[<=i]; base fixed pre-i
    base_i = 3
    def dir_at(i, ts_, p_, bv_, sv_):
        if i <= base_i:
            return None
        return round(float(np.sign(p_[i] - p_[base_i])), 3)
    dp, df = assert_no_leakage(dir_at, ts, p, z, z, idxs=[8, 12], reps=3, seed=0)
    print("  ok  future-direction closure invariant to post-entry ticks" if dp else f"  FAIL dir leak {df}")
    ok = ok and dp
    # kalshi-entry-mark = last price <= t read only from p[<=i]
    def mark_at(i, ts_, p_, bv_, sv_):
        return round(float(p_[i]), 3)
    mp, mf = assert_no_leakage(mark_at, ts, p, z, z, idxs=[8, 12], reps=3, seed=1)
    print("  ok  kalshi entry-mark closure invariant to post-entry ticks" if mp else f"  FAIL mark leak {mf}")
    ok = ok and mp
    print("SELFTEST", "PASS" if ok else "FAIL")
    return ok


def main():
    ap = argparse.ArgumentParser(description="P3 futures->Kalshi lag join (realized-EV of the echo)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--trigger-cl", type=float, default=0.15, help="WTI entry trigger: NYMEX $ move to fire")
    ap.add_argument("--trigger-ng", type=float, default=0.02, help="NatGas entry trigger: NYMEX $ move to fire")
    ap.add_argument("--max-wait", type=float, default=300.0, help="give up if NYMEX hasn't moved by then (s)")
    ap.add_argument("--confirm-s", type=float, default=5.0, help="canary must HOLD beyond trigger this many s "
                    "(sustained move, not a transient poke) before we fire")
    ap.add_argument("--retain-frac", type=float, default=0.5, help="NYMEX-driven exit: exit when the canary "
                    "gives back to this fraction of its favorable run (hold through Kalshi whipsaw)")
    ap.add_argument("--stale-cap", type=float, default=12.0, help="stand back if Kalshi already moved this "
                    "many c in the NYMEX direction by entry (caught up on its own)")
    ap.add_argument("--slip", type=float, default=1.0, help="adverse taker slippage per fill (cents)")
    ap.add_argument("--maker-off", type=float, default=1.0, help="maker haircut off the exact extreme (c)")
    ap.add_argument("--min-wave", type=float, default=1.0, help="min favorable echo (c) for a maker fill")
    ap.add_argument("--settle-buffer", type=float, default=1800.0, help="stop this many s before settle")
    ap.add_argument("--trig-sweep", action="store_true", help="print the EV-vs-trigger curve (the #2 ask)")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)

    cfg = {"trigger_usd": {"CL": args.trigger_cl, "NG": args.trigger_ng}, "max_wait": args.max_wait,
           "confirm_s": args.confirm_s, "retain_frac": args.retain_frac, "stale_cap": args.stale_cap,
           "slip": args.slip, "maker_off": args.maker_off, "min_wave": args.min_wave,
           "settle_buffer": args.settle_buffer}
    rows = run(cfg)
    print(f"\nP3 LAG JOIN — {len(rows)} echo trades "
          f"(trigger CL=${args.trigger_cl:.2f} NG=${args.trigger_ng:.3f} retain={args.retain_frac:.2f} "
          f"stale_cap={args.stale_cap:.0f}c slip={args.slip:.0f}c; ENTRY+HOLD+EXIT all NYMEX-driven, $/c)")
    print("net-of-fee CENTS per contract; ENTRY taker; EXIT maker-best-number-w-taker-fallback vs pure-taker base")
    report(rows, ["root"], "per contract")
    report(rows, ["root", "scell"], "per contract x surprise cell")
    report(rows, ["root", "coiled"], "per contract x coiled/primed gate")
    # pooled footnote (never the headline)
    tk = np.array([r["pnl_taker"] for r in rows], float)
    mk = np.array([r["pnl_maker"] for r in rows], float)
    print(f"\n[pooled footnote] taker med {np.median(tk):+.2f}c pos {100*np.mean(tk>0):.0f}% | "
          f"maker med {np.median(mk):+.2f}c pos {100*np.mean(mk>0):.0f}% "
          f"fill {100*np.mean([r['maker_filled'] for r in rows]):.0f}%")

    if args.trig_sweep:
        print("\n[trigger sweep — the #2 EV-vs-threshold curve, tuned PER CONTRACT in $ (Greg S87)]")
        grids = {"CL": (0.05, 0.10, 0.15, 0.20, 0.30, 0.50), "NG": (0.005, 0.01, 0.02, 0.03, 0.05, 0.08)}
        for root in ("CL", "NG"):
            print(f"  {root} (trigger in $ of {'crude' if root=='CL' else 'gas'}):")
            for trig in grids[root]:
                rr = [r for r in run(dict(cfg, trigger_usd={**cfg["trigger_usd"], root: trig}))
                      if r["root"] == root]
                if rr:
                    tk = np.array([r["pnl_taker"] for r in rr], float)
                    mk = np.array([r["pnl_maker"] for r in rr], float)
                    lag = np.median([r["trigger_lag"] for r in rr])
                    print(f"    trig>=${trig:>5.3f}  n={len(rr):>2}  lag~{lag:>4.0f}s  "
                          f"taker {np.median(tk):+5.1f}c/{100*np.mean(tk>0):>3.0f}%  "
                          f"maker {np.median(mk):+5.1f}c/{100*np.mean(mk>0):>3.0f}%  fill {100*np.mean([r['maker_filled'] for r in rr]):>3.0f}%")


if __name__ == "__main__":
    main()
