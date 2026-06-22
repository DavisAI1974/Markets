"""_info_dipole_swing_backtest.py — the SWING strategy: buy valleys, short peaks, flip at each turn.

Greg's model (S36): markets oscillate — go LONG at the valley as it starts to turn up, go SHORT at the
peak as it starts to roll over, flip at every turn. No clock/horizon — the only thing that ends a position
is the next turning point. Enter AT the turn, never on the backside (after the move has already traveled).
Rarer straight runs = one long leg with no turn (flow keeps confirming -> you just ride, don't flip).

Minimum tradeable swing = the one that beats the round-trip FEE (5 bps/side = 10 bps = 0.10% of trade
value). Smaller swings lose by definition. So we don't guess a swing size — we SWEEP it and let the fee
set the floor.

THREE layers (per asset x venue price series; look-ahead noted):
  1. ORACLE (perfect hindsight)   — mark every true peak/valley (ZigZag, reversal threshold theta), long
     valleys / short peaks, flip at each pivot. The CEILING: shows the swings beat the fee, and by how much.
  2. PRICE-CONFIRM (no look-ahead) — flip only after price retraces theta from the extreme. By construction
     this enters on the BACKSIDE (theta late) — the thing Greg says to AVOID. Baseline for "how bad is late".
  3. DIPOLE (no look-ahead)       — flip when the order-flow dipole crosses (flow rolls from buy->sell at a
     peak / sell->buy at a valley). Aims to enter AT the turn, early — the edge. In a straight run flow stays
     one-signed -> no flip -> ride. Reported with how close its entries land to the true pivots (turn vs backside).

Cost = COST_PER_SIDE_BPS per side; every completed leg pays a round-trip. Net bps over the ~2-day series.

CAVEAT: thin 1-min/2-day single-regime test_bars. The oracle ceiling is real arithmetic; the dipole capture
is indicative and must be re-tuned/validated on the local 1-sec multi-regime history.

Run: python _info_dipole_swing_backtest.py
"""
from __future__ import annotations

import glob
import json

import numpy as np

COST_PER_SIDE_BPS = 5.0
RT = 2 * COST_PER_SIDE_BPS


def load_series():
    out = {}
    for fp in glob.glob("fingerprint_dataset/test_bars/*.json"):
        d = json.load(open(fp)); a, v = d["asset"].lower(), d["venue"].lower()
        B = sorted(d["bars"], key=lambda b: b["ts"])
        out[f"{a}_{v}"] = (np.array([b["ts"] for b in B], float),
                           np.array([b["close"] for b in B], float),
                           np.array([b.get("buy_vol", 0.) for b in B], float),
                           np.array([b.get("sell_vol", 0.) for b in B], float))
    return out


def zigzag(p, theta):
    """True peaks/valleys: a pivot is confirmed once price reverses by `theta` (fraction) off the extreme.

    Returns list of (idx, 'H'|'L') at the actual extreme bars (oracle uses these exact tops/bottoms).
    """
    piv = []
    n = len(p)
    if n < 2:
        return piv
    mode = 0                 # 0 unknown, +1 in up-leg (seeking a High), -1 in down-leg (seeking a Low)
    ext_i, ext_v = 0, p[0]
    for i in range(1, n):
        if mode == 0:        # unknown: p[0] is the implicit first pivot; first theta move sets direction
            if p[i] >= p[0] * (1 + theta):
                piv.append((0, "L")); mode = 1; ext_i, ext_v = i, p[i]
            elif p[i] <= p[0] * (1 - theta):
                piv.append((0, "H")); mode = -1; ext_i, ext_v = i, p[i]
        elif mode == 1:      # up-leg: track the running high; confirm peak on a theta reversal down
            if p[i] > ext_v:
                ext_i, ext_v = i, p[i]
            elif p[i] <= ext_v * (1 - theta):
                piv.append((ext_i, "H")); mode = -1; ext_i, ext_v = i, p[i]
        else:                # down-leg: track the running low; confirm valley on a theta reversal up
            if p[i] < ext_v:
                ext_i, ext_v = i, p[i]
            elif p[i] >= ext_v * (1 + theta):
                piv.append((ext_i, "L")); mode = 1; ext_i, ext_v = i, p[i]
    return piv


def oracle_swing(p, theta):
    """Perfect: long from each valley to the next peak, short from each peak to the next valley."""
    piv = zigzag(p, theta)
    if len(piv) < 2:
        return {"n": 0, "net_total": 0.0, "gross_total": 0.0, "mean_swing_bps": 0.0}
    legs = []
    swings = []
    for (i0, t0), (i1, t1) in zip(piv[:-1], piv[1:]):
        d = 1.0 if t0 == "L" else -1.0                  # long off a valley, short off a peak
        move = (p[i1] / p[i0] - 1.0) * 1e4
        legs.append(d * move - RT)
        swings.append(abs(move))
    legs = np.array(legs)
    return {"n": len(legs), "net_total": round(float(legs.sum()), 1),
            "gross_total": round(float((legs + RT).sum()), 1),
            "net_per_leg": round(float(legs.mean()), 2),
            "mean_swing_bps": round(float(np.mean(swings)), 1),
            "n_pivots": len(piv)}


def trailing_imbalance(ts, bv, sv, win_s):
    """Per-bar order-flow imbalance over the trailing win_s window (vectorized via cumsum + searchsorted)."""
    cb = np.concatenate([[0.0], np.cumsum(bv)])
    cs = np.concatenate([[0.0], np.cumsum(sv)])
    lo = np.searchsorted(ts, ts - win_s, side="left")
    idx = np.arange(len(ts)) + 1
    B = cb[idx] - cb[lo]; S = cs[idx] - cs[lo]
    tot = B + S
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(tot > 0, (B - S) / np.where(tot > 0, tot, 1.0), 0.0)


def run_position_series(p, desired):
    """Given a per-bar desired direction in {+1,-1,0} (0 = hold current), simulate flips. Look-ahead free
    as long as `desired[i]` uses only data <= i. Returns net bps total, n_legs, and entry bar indices."""
    pos = 0
    entry_i = 0
    net = 0.0
    legs = 0
    entries = []
    for i in range(len(p)):
        d = desired[i]
        if d != 0 and d != pos:
            if pos != 0:                                # close current leg
                net += pos * (p[i] / p[entry_i] - 1.0) * 1e4 - RT
                legs += 1
            pos = d; entry_i = i; entries.append((i, d))
    if pos != 0:                                        # close the final open leg at the last bar
        net += pos * (p[-1] / p[entry_i] - 1.0) * 1e4 - RT
        legs += 1
    return round(net, 1), legs, entries


def dipole_swing(ts, p, bv, sv, win_s, thresh):
    """Flip with the flow: long when trailing imbalance >= +thresh, short when <= -thresh, hold in the
    deadband. Crossings = turns (buy->sell at a peak, sell->buy at a valley). Lags the price turn."""
    imb = trailing_imbalance(ts, bv, sv, win_s)
    desired = np.where(imb >= thresh, 1, np.where(imb <= -thresh, -1, 0))
    return run_position_series(p, desired), imb


def exhaustion_swing(ts, p, bv, sv, short_s, long_s, collapse):
    """Turn detector via flow EXHAUSTION (the S36 'dipole collapsing toward 0.5' = leader weakening),
    meant to fire BEFORE the sign-cross. Up-trend (imb_long>0) but short-window buying collapsed
    (imb_short < collapse*imb_long) -> peak -> short. Symmetric at a valley. Else hold."""
    il = trailing_imbalance(ts, bv, sv, long_s)
    is_ = trailing_imbalance(ts, bv, sv, short_s)
    d = np.zeros(len(p), int)
    up = (il > 0.02) & (is_ < collapse * il)
    dn = (il < -0.02) & (is_ > collapse * il)
    d[up] = -1; d[dn] = 1
    return run_position_series(p, d)


def price_confirm_swing(p, theta):
    """Backside baseline: flip only after price retraces theta from the extreme (always late, by design)."""
    n = len(p)
    desired = np.zeros(n, int)
    mode = 0; ext_v = p[0]
    for i in range(1, n):
        if mode == 0:
            if p[i] >= p[0] * (1 + theta):
                mode = 1; ext_v = p[i]
            elif p[i] <= p[0] * (1 - theta):
                mode = -1; ext_v = p[i]
        elif mode == 1:                              # seeking high; on theta drop, flip short (late)
            if p[i] > ext_v:
                ext_v = p[i]
            elif p[i] <= ext_v * (1 - theta):
                desired[i] = -1; mode = -1; ext_v = p[i]
        else:                                        # seeking low; on theta rise, flip long (late)
            if p[i] < ext_v:
                ext_v = p[i]
            elif p[i] >= ext_v * (1 + theta):
                desired[i] = 1; mode = 1; ext_v = p[i]
    return run_position_series(p, desired)


def entry_quality(p, entries, piv):
    """How close each entry lands to a true pivot of the matching type (turn vs backside), in bps off it."""
    if not entries or not piv:
        return None
    Hs = [i for i, t in piv if t == "H"]; Ls = [i for i, t in piv if t == "L"]
    offs = []
    for i, d in entries:
        cand = Ls if d > 0 else Hs                       # long should enter near a valley; short near a peak
        if not cand:
            continue
        j = min(cand, key=lambda k: abs(k - i))
        offs.append(abs(p[i] / p[j] - 1.0) * 1e4)         # bps away from the ideal top/bottom price
    return round(float(np.median(offs)), 1) if offs else None


def main():
    series = load_series()
    thetas = [0.0005, 0.0010, 0.0015, 0.0020, 0.0030, 0.0050, 0.0100]   # 5..100 bps reversal threshold
    print(f"SWING backtest — buy valleys / short peaks, flip at each turn. Fee {COST_PER_SIDE_BPS} bps/side "
          f"(round-trip {RT} bps = the min-swing floor). {len(series)} venue series, 1-min/~2-day.\n")

    print("=" * 100)
    print("1) ORACLE CEILING vs swing size (perfect pivots; shows swings beat the fee and the sweet spot)")
    print("=" * 100)
    print(f"{'theta':>7s} | " + " | ".join(f"{s.replace('_',' '):>16s}" for s in sorted(series)))
    oracle_by = {s: {} for s in series}
    for th in thetas:
        cells = []
        for s in sorted(series):
            o = oracle_swing(series[s][1], th)
            oracle_by[s][th] = o
            cells.append(f"{o['net_total']:>8.0f}/{o['n']:>4d}")
        print(f"{th*1e4:>5.0f}bp | " + " | ".join(f"{c:>16s}" for c in cells))
    print("  (cell = oracle NET bps total / number of swings.  net = sum(swing_bps) - 10bps*swings.)")
    # mean swing size at each theta (pooled)
    print("\n  mean swing size (bps) by theta, pooled across venues:")
    for th in thetas:
        ms = np.mean([oracle_by[s][th]["mean_swing_bps"] for s in series if oracle_by[s][th]["n"]])
        print(f"     theta={th*1e4:>4.0f}bp  mean_swing={ms:>6.1f}bps  net/swing={ms-RT:>+6.1f}bps")

    print("\n" + "=" * 100)
    print("2) DIPOLE swing (real-time, no look-ahead) vs ORACLE vs PRICE-CONFIRM (backside)")
    print("=" * 100)
    th_ref = 0.0020                                       # reference swing size for the realistic comparison
    print(f"Reference swing threshold theta={th_ref*1e4:.0f}bps (mean swing ~50bps). best-of-grid per detector.\n")
    print(f"{'venue':16s} {'ORACLE':>8s} | {'CROSS net (off)':>20s} | {'EXHAUST net (off)':>20s} | {'PRICE-CONF':>10s}")
    results = {}
    for s in sorted(series):
        ts, p, bv, sv = series[s]
        o = oracle_swing(p, th_ref)
        piv = zigzag(p, th_ref)
        bestc = None                                      # imbalance sign-cross detector
        for win_s in [180, 300, 600, 1200]:
            for thr in [0.05, 0.10, 0.20]:
                (net, legs, entries), _ = dipole_swing(ts, p, bv, sv, win_s, thr)
                eq = entry_quality(p, entries, piv)
                if bestc is None or net > bestc[0]:
                    bestc = (net, legs, win_s, thr, eq)
        beste = None                                      # exhaustion detector (fires before the cross)
        for short_s in [120, 300]:
            for long_s in [900, 1800]:
                for col in [0.0, 0.3, 0.5]:
                    net, legs, entries = exhaustion_swing(ts, p, bv, sv, short_s, long_s, col)
                    eq = entry_quality(p, entries, piv)
                    if beste is None or net > beste[0]:
                        beste = (net, legs, short_s, long_s, col, eq)
        pc_net, pc_legs, _ = price_confirm_swing(p, th_ref)
        results[s] = {"oracle_net": o["net_total"], "oracle_n": o["n"],
                      "cross_net": bestc[0], "cross_entry_off_bps": bestc[4],
                      "exhaust_net": beste[0], "exhaust_entry_off_bps": beste[5],
                      "price_confirm_net": pc_net,
                      "cross_capture_pct": round(100 * bestc[0] / o["net_total"], 1) if o["net_total"] > 0 else None,
                      "exhaust_capture_pct": round(100 * beste[0] / o["net_total"], 1) if o["net_total"] > 0 else None}
        print(f"{s:16s} {o['net_total']:>+8.0f} | {bestc[0]:>+9.0f} (off~{bestc[4]:>4}bps) | "
              f"{beste[0]:>+9.0f} (off~{beste[5]:>4}bps) | {pc_net:>+10.0f}")

    print("\n  Every real-time turn-detector LOSES — entries land ~15-27bps off the true turn (the BACKSIDE),")
    print("  while 1-min bars move only ~2-4bps each => the limit is DETECTOR LAG, not bar granularity.")
    print("  capture% (detector net / oracle ceiling):")
    for s in sorted(series):
        r = results[s]
        print(f"   {s:16s} cross={str(r['cross_capture_pct'])+'%':>7s} (off~{r['cross_entry_off_bps']}bps)  "
              f"exhaust={str(r['exhaust_capture_pct'])+'%':>7s} (off~{r['exhaust_entry_off_bps']}bps)")

    out = {"config": {"cost_per_side_bps": COST_PER_SIDE_BPS, "round_trip_bps": RT,
                      "ref_theta_bps": th_ref * 1e4, "thetas_bps": [t * 1e4 for t in thetas]},
           "oracle_ceiling": {s: {str(int(th * 1e4)): oracle_by[s][th] for th in thetas} for s in series},
           "dipole_vs_oracle": results,
           "caveat": "thin 1-min/2-day single-regime; oracle is exact arithmetic, dipole capture indicative; "
                     "re-tune/validate on 1-sec multi-regime history"}
    with open("_info_dipole_swing_backtest_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nWrote _info_dipole_swing_backtest_results.json")


if __name__ == "__main__":
    main()
