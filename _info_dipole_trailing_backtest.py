"""_info_dipole_trailing_backtest.py — HORIZON-FREE flow strategy: ride until price reverses, then flip or flatten.

Greg (S36): "ditch the horizon times, period. The only thing that ends a trade is price moving against you.
Then the question is go short, go long, or just flatten." So there is NO clock. A leg rides until an
ADVERSE price move (a trailing backslide off the peak favorable excursion). At that reversal the order-flow
dipole decides the next action:
  - dipole shows STRENGTH in the reversal direction -> FLIP (open the opposite leg, ride it the same way);
  - dipole does NOT confirm -> FLATTEN (the trade is over).

Everything is look-ahead free: every bar decision uses only data up to that bar.

EXIT (the only ender — price, never a clock):
  peak = running max of the open leg's favorable excursion (bps).
  giveback = peak - pnl.  EXIT the leg when giveback >= trigger, where
     trigger = BACKSLIDE_FRAC * peak     once peak >= TRAIL_ACTIVATE   (lock most of a real run:
                                                                        "+50 peak, 10% -> sell +45")
     trigger = FLOOR_BPS                 otherwise                     (a small adverse move ends a
                                                                        not-yet-profitable / losing leg).
FLIP vs FLATTEN at every leg exit: dipole = order-flow imbalance over the trailing WIN_S window ending at
the exit bar; FLIP iff it leans the reversal way by >= FLIP_THRESH; else FLATTEN. Cost charged PER LEG
(enter+exit = round-trip). Entry direction = the FLOW policy (follow when flow confirms, fade when opposes).

CAVEATS (load-bearing): (1) with no horizon, one onset's managed trade can ride a long way, so per-onset
trades on the same venue OVERLAP and are correlated — effective independent N is well below the row count
(read this as per-signal expectancy, not a single-book equity curve). (2) Exit params are tunable and the
test_bars are thin (1-min, ~2 days, ONE trend regime); this shows the MECHANISM and must be tuned/validated
on the local 1-sec multi-regime history. (3) Onsets near the series end get a forced flatten at the last
bar (not price-driven) — a small late-sample artifact.

Run: python _info_dipole_trailing_backtest.py
"""
from __future__ import annotations

import bisect
import glob
import json

import numpy as np

from odcore.info_dipole import divergence

WIN_S = 1800                 # pre-entry gate window AND trailing window for the flip-confirm dipole
COST_PER_SIDE_BPS = 5.0

# exit-management defaults (swept in main)
BACKSLIDE_FRAC = 0.10        # once in a real run, give back this fraction of peak then exit (Greg's 10%)
TRAIL_ACTIVATE = 30.0        # peak (bps) above which we switch from the absolute floor to the % trail
FLOOR_BPS = 15.0            # absolute adverse move (bps off peak) that ends a not-yet-profitable leg
FLIP_THRESH = 0.05           # order-flow imbalance magnitude needed to confirm a flip (else flatten)
MAX_LEGS = 4                 # cap legs per onset


def load_bars():
    bars = {}
    for fp in glob.glob("fingerprint_dataset/test_bars/*.json"):
        d = json.load(open(fp)); a, v = d["asset"].lower(), d["venue"].lower()
        B = sorted(d["bars"], key=lambda b: b["ts"])
        bars[(a, v)] = (np.array([b["ts"] for b in B]),
                        np.array([b.get("buy_vol", 0.) for b in B]),
                        np.array([b.get("sell_vol", 0.) for b in B]),
                        np.array([b["close"] for b in B]))
    return bars


def imbalance(bv, sv):
    b = float(np.sum(bv)); s = float(np.sum(sv)); t = b + s
    return (b - s) / t if t > 0 else 0.0


def simulate(ts, bv, sv, cl, hi, direction, *, backslide, activate, floor_bps,
             allow_flip, flip_thresh, max_legs, exit_mode="price", dipole_exit=0.05):
    """Ride from the onset bar to the END of the series; legs end ONLY on an adverse signal.

    exit_mode:
      "price"  — leg ends on an adverse PRICE move (trailing backslide / floor). Greg's literal ask.
      "dipole" — leg ends when the order-flow DIPOLE flips against the position (flow stops supporting
                 the move), protected by a wide floor stop. Flow-native exit (rides through price noise).
    Returns (gross_bps_total, n_legs, last_bar_index). Look-ahead free (bar i uses only data <= i).
    """
    n = len(cl)
    legs = 0
    gross = 0.0
    pos = direction
    leg_entry = hi - 1
    peak = 0.0
    i = hi - 1
    while i < n:
        pnl = pos * (cl[i] / cl[leg_entry] - 1.0) * 1e4
        if pnl > peak:
            peak = pnl
        end_of_data = (i == n - 1)
        if exit_mode == "price":
            trigger = backslide * peak if peak >= activate else floor_bps
            do_exit = (peak - pnl) >= trigger
        else:  # "dipole": exit when flow turns against the position; floor_bps as a hard protective stop
            lo2 = bisect.bisect_left(ts, ts[i] - WIN_S)
            imb = imbalance(bv[lo2:i + 1], sv[lo2:i + 1])
            flow_against = (pos > 0 and imb <= -dipole_exit) or (pos < 0 and imb >= dipole_exit)
            do_exit = flow_against or (peak - pnl) >= floor_bps
        if do_exit or end_of_data:
            gross += pnl
            legs += 1
            if allow_flip and not end_of_data and legs < max_legs:
                lo2 = bisect.bisect_left(ts, ts[i] - WIN_S)
                imb = imbalance(bv[lo2:i + 1], sv[lo2:i + 1])
                new_dir = -pos
                confirmed = (new_dir > 0 and imb >= flip_thresh) or (new_dir < 0 and imb <= -flip_thresh)
                if confirmed:
                    pos = new_dir; leg_entry = i; peak = 0.0
                    i += 1
                    continue
            break
        i += 1
    return gross, legs, i


def build(bars, onsets, **kw):
    rt = 2 * COST_PER_SIDE_BPS
    out = []
    for w in onsets:
        a, v = w["asset"].lower(), w["venue"].lower()
        if (a, v) not in bars:
            continue
        ts, bv, sv, cl = bars[(a, v)]
        ot = w["true_onset_ts_utc"]
        lo = bisect.bisect_left(ts, ot - WIN_S); hi = bisect.bisect_right(ts, ot)
        if hi == 0 or hi - lo < 6 or hi >= len(ts):
            continue
        pre = cl[hi - 1] - cl[lo]
        if pre == 0 or cl[hi - 1] <= 0:
            continue
        dv = divergence(bv[lo:hi], sv[lo:hi], pre)
        if dv is None:
            continue
        pre_sign = 1.0 if pre > 0 else -1.0
        direction = pre_sign if dv["confirms"] else -pre_sign      # FLOW policy entry
        gross, legs, last_i = simulate(ts, bv, sv, cl, hi, direction, **kw)
        out.append({"cell": w["cell"], "ts": ot, "net": gross - legs * rt,
                    "legs": legs, "bars_held": int(last_i - (hi - 1))})
    return out


def summ(recs):
    if not recs:
        return None
    n = np.array([r["net"] for r in recs])
    return {"n": len(n), "net_bps": round(float(n.mean()), 2),
            "win_rate": round(100 * float((n > 0).mean()), 1),
            "se": round(float(n.std(ddof=1) / np.sqrt(len(n))) if len(n) > 1 else 0.0, 2),
            "avg_legs": round(float(np.mean([r["legs"] for r in recs])), 2),
            "avg_bars_held": round(float(np.mean([r["bars_held"] for r in recs])), 1),
            "total": round(float(n.sum()), 1)}


def fmt(label, s):
    if s is None:
        return f"{label:22s}  (no trades)"
    t = s["net_bps"] / s["se"] if s["se"] > 0 else 0.0
    star = "  <-- CLEARS" if s["net_bps"] > 0 else ""
    return (f"{label:22s} n={s['n']:>4d}  net={s['net_bps']:>+8.2f} (+-{s['se']:>5.2f}, t={t:>+4.1f})  "
            f"win%={s['win_rate']:>4.1f}  legs={s['avg_legs']:.2f}  held~{s['avg_bars_held']:.0f}m  "
            f"total={s['total']:>+9.1f}{star}")


def main():
    bars = load_bars()
    wo = json.load(open("fingerprint_dataset/onsets/winner_onsets.json"))
    base_kw = dict(backslide=BACKSLIDE_FRAC, activate=TRAIL_ACTIVATE, floor_bps=FLOOR_BPS,
                   flip_thresh=FLIP_THRESH, max_legs=MAX_LEGS)
    cells = sorted({r["cell"] for r in build(bars, wo, allow_flip=False, **base_kw)})

    print("HORIZON-FREE flow strategy: ride until price reverses, then dipole says flip / flatten.")
    print(f"Cost {COST_PER_SIDE_BPS} bps/side per LEG. Entry = FLOW policy. "
          f"backslide={BACKSLIDE_FRAC} trail_activate={TRAIL_ACTIVATE}bps floor={FLOOR_BPS}bps "
          f"flip_thresh={FLIP_THRESH}.\n")

    noflip = build(bars, wo, allow_flip=False, exit_mode="price", **base_kw)
    flip = build(bars, wo, allow_flip=True, exit_mode="price", **base_kw)
    dip = build(bars, wo, allow_flip=True, exit_mode="dipole", dipole_exit=0.05, **base_kw)

    print("=" * 104)
    print("POOLED")
    print("=" * 104)
    print(" ", fmt("PRICE-stop (flatten)", summ(noflip)))
    print(" ", fmt("PRICE-stop +flip", summ(flip)))
    print(" ", fmt("DIPOLE-exit +flip", summ(dip)))

    print("\n" + "=" * 104)
    print("PER CELL — PRICE-stop+flip  vs  DIPOLE-exit+flip (net bps per onset-trade)")
    print("=" * 104)
    cleared = []
    per_cell = {}
    print(f"{'cell':20s} {'price-stop':>11s} {'dipole-exit':>12s}   {'n':>4s}")
    for c in cells:
        sp = summ([r for r in flip if r["cell"] == c])
        sd = summ([r for r in dip if r["cell"] == c])
        per_cell[c] = {"price_stop_flip": sp, "dipole_exit_flip": sd}
        if sd and sd["n"] >= 5:
            mark = "  <-- dipole CLEARS" if sd["net_bps"] > 0 else ""
            if sd["net_bps"] > 0:
                cleared.append(c)
            print(f"{c:20s} {sp['net_bps']:>+11.2f} {sd['net_bps']:>+12.2f}   {sd['n']:>4d}{mark}")
    print(f"\n  Cells clearing net-of-cost (DIPOLE-exit+flip, n>=5): {', '.join(cleared) or 'NONE'}")

    print("\n" + "=" * 104)
    print("WALK-FORWARD (DIPOLE-exit+flip; early/late temporal split)")
    print("=" * 104)
    for c in cells:
        cr = sorted([r for r in dip if r["cell"] == c], key=lambda r: r["ts"])
        if len(cr) < 16:
            continue
        h = len(cr) // 2
        se, sl = summ(cr[:h]), summ(cr[h:])
        both = "  BOTH+" if (se["net_bps"] > 0 and sl["net_bps"] > 0) else ""
        print(f"   {c:20s} early net={se['net_bps']:>+9.2f} (n={se['n']:>3d})   "
              f"late net={sl['net_bps']:>+9.2f} (n={sl['n']:>3d}){both}")

    print("\n" + "=" * 104)
    print("PARAM SWEEP (ride+stop+flip): pooled & spotlight cells")
    print("=" * 104)
    print(f"{'backslide':>9s} {'floor':>6s} | {'pooled net':>10s} {'n':>5s} | "
          f"{'eth_bybit_buy':>13s} | {'btc_bybit_sell':>14s} | {'btc_bybit_buy':>13s}")
    for bsf in [0.10, 0.20, 0.33]:
        for fl_bps in [15.0, 30.0]:
            kw = dict(backslide=bsf, activate=TRAIL_ACTIVATE, floor_bps=fl_bps,
                      flip_thresh=FLIP_THRESH, max_legs=MAX_LEGS)
            fl = build(bars, wo, allow_flip=True, **kw)
            ps = summ(fl)
            def cnet(c):
                s = summ([r for r in fl if r["cell"] == c]); return s["net_bps"] if s else float("nan")
            print(f"{bsf:>9.2f} {fl_bps:>6.0f} | {ps['net_bps']:>+10.2f} {ps['n']:>5d} | "
                  f"{cnet('eth_bybit_buy'):>+13.2f} | {cnet('btc_bybit_sell'):>+14.2f} | "
                  f"{cnet('btc_bybit_buy'):>+13.2f}")

    out = {
        "config": dict(cost_per_side_bps=COST_PER_SIDE_BPS, horizon="NONE (price+dipole exits only)",
                       **base_kw),
        "pooled": {"price_stop_flatten": summ(noflip), "price_stop_flip": summ(flip),
                   "dipole_exit_flip": summ(dip)},
        "per_cell": per_cell,
        "cells_clearing": cleared,
        "caveat": "horizon-free; overlapping correlated trades; thin 1-min/2-day single-regime; tunable exits; mechanism demo",
    }
    with open("_info_dipole_trailing_backtest_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nWrote _info_dipole_trailing_backtest_results.json")


if __name__ == "__main__":
    main()
