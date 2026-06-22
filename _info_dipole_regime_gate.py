"""_info_dipole_regime_gate.py — regime master-gate: stand FLAT in bad regimes (Architect S36b + Greg).

A swing strategy (buy valleys / short peaks) gets killed in two regimes: STRAIGHT RUNS (a strong trend —
fading every wiggle is suicide; Greg's "ride, don't fight") and TOXIC / low-liquidity flow (MM withdrawal,
one-sided dumping). The fix is a MASTER enable/disable that sits ON TOP of the filter+timing stack: when the
regime is bad, suppress ALL calls and stay flat. "A swing strategy that goes flat ahead of a liquidity
crisis beats one that enters beautifully into a gap" (Architect).

Two regime metrics tested as the gate (per call, look-ahead free, over a trailing window W):
  - ER  = efficiency ratio |net move| / |path length| over W. High ER = a STRAIGHT RUN (trending) -> don't
          fade. Directly Greg's oscillate-vs-straight-run picture.
  - C   = dipole ratio H_self/H_cross = 0.5*(H_buy+H_sell)/MI(buy,sell). MI collapsing (buy/sell flow
          decoupling) -> C spikes -> toxic/disorderly regime (the Architect's C-ratio idea).

We score on the falsification harness (frozen 1-sec realbins, OOS): does gating the dipole challenger by
regime lift precision / net over the un-gated challenger and the classical champion? The gate direction +
threshold are tuned on the in-sample 60% (the data picks the sign), applied to the out-of-sample 40%.

Run: python _info_dipole_regime_gate.py
"""
from __future__ import annotations

import json

import numpy as np

from odcore.info_dipole import shannon, mutual_info, EPS, divergence
from _info_dipole_swing_backtest import load_series, zigzag, trailing_imbalance
from _info_dipole_harness import (candidates, filt_champion, filt_dipole, run_calls, score,
                                  FEE_RT, FEE_MAKER, SWING_THETA, IS_FRAC)


def efficiency_ratio(ts, p, W):
    """Per-bar trend efficiency over the trailing W seconds: |net move| / |path length| in [0,1]."""
    absdp = np.abs(np.diff(p, prepend=p[0]))
    cum = np.cumsum(absdp)
    lo = np.searchsorted(ts, ts - W)
    idx = np.arange(len(p))
    path = cum[idx] - cum[lo]
    move = np.abs(p[idx] - p[lo])
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(path > 0, move / np.where(path > 0, path, 1.0), 0.0)


def c_ratio_at(ts, bv, sv, i, W):
    lo = int(np.searchsorted(ts, ts[i] - W))
    A, S = bv[lo:i + 1], sv[lo:i + 1]
    if A.size < 6:
        return None
    Ha, Hb = shannon(A), shannon(S)
    mi = mutual_info(A, S)
    return 0.5 * (Ha + Hb) / (mi + EPS)


def gate_calls(calls, metric_vals, direction, thr):
    """Keep call (i,d) if its regime metric passes. direction +1: keep if metric<=thr; -1: keep if >=thr."""
    out = []
    for (i, d) in calls:
        v = metric_vals.get(i)
        if v is None:
            continue
        if (direction > 0 and v <= thr) or (direction < 0 and v >= thr):
            out.append((i, d))
    return out


def metric_at_calls(kind, calls, ts, p, bv, sv, W, er_arr=None):
    if kind == "ER":
        return {i: float(er_arr[i]) for (i, d) in calls}
    return {i: c_ratio_at(ts, bv, sv, i, W) for (i, d) in calls}


def best_dipole_calls(seg, W_dip, C_conv):
    """The challenger's raw calls (dipole filter) for a fixed (R=8bps, W_dip, conviction)."""
    ts, p, bv, sv = seg
    cand = candidates(p, 8 / 1e4)
    return filt_dipole(cand, ts, p, bv, sv, W_dip, C_conv), (ts, p, bv, sv)


def evaluate(seg_is, seg_oos):
    res = {}
    # --- baselines: champion + un-gated challenger (fixed sane dipole params) ---
    ts_i, p_i, bv_i, sv_i = seg_is; ts_o, p_o, bv_o, sv_o = seg_oos
    piv_o = zigzag(p_o, SWING_THETA)

    # champion (tuned small grid on IS net)
    champ_best = None
    cand_i8 = candidates(p_i, 8 / 1e4)
    for W in (60, 300):
        for T in (0.05, 0.10, 0.20):
            net, _ = run_calls(p_i, filt_champion(cand_i8, ts_i, p_i, bv_i, sv_i, W, T), FEE_RT)
            if champ_best is None or net > champ_best[0]:
                champ_best = (net, W, T)
    _, Wc, Tc = champ_best
    champ_o = filt_champion(candidates(p_o, 8 / 1e4), ts_o, p_o, bv_o, sv_o, Wc, Tc)
    net_o, ent = run_calls(p_o, champ_o, FEE_MAKER); s = score(ent, piv_o, p_o)
    res["CHAMPION"] = dict(net_maker=net_o, **{k: s[k] for k in ("recall", "precision", "bps_to_turn", "n_calls")})

    # un-gated challenger: fix R=8, tune W_dip + conviction on IS net
    chall_best = None
    for Wd in (300, 900):
        for C in (0.0, 0.15, 0.30):
            calls = filt_dipole(cand_i8, ts_i, p_i, bv_i, sv_i, Wd, C)
            net, _ = run_calls(p_i, calls, FEE_RT)
            if chall_best is None or net > chall_best[0]:
                chall_best = (net, Wd, C)
    _, Wd, Cc = chall_best
    raw_o = filt_dipole(candidates(p_o, 8 / 1e4), ts_o, p_o, bv_o, sv_o, Wd, Cc)
    net_o, ent = run_calls(p_o, raw_o, FEE_MAKER); s = score(ent, piv_o, p_o)
    res["CHALLENGER"] = dict(net_maker=net_o, **{k: s[k] for k in ("recall", "precision", "bps_to_turn", "n_calls")})

    # --- regime-gated challenger: tune (metric, direction, threshold, W) on IS net ---
    raw_i = filt_dipole(cand_i8, ts_i, p_i, bv_i, sv_i, Wd, Cc)
    for kind in ("ER", "C"):
        Wr = 900
        er_i = efficiency_ratio(ts_i, p_i, Wr) if kind == "ER" else None
        er_o = efficiency_ratio(ts_o, p_o, Wr) if kind == "ER" else None
        mi_i = metric_at_calls(kind, raw_i, ts_i, p_i, bv_i, sv_i, Wr, er_i)
        thr_grid = (0.2, 0.35, 0.5, 0.65, 0.8) if kind == "ER" else (2.0, 4.0, 8.0, 16.0)
        gbest = None
        for direction in (+1, -1):
            for thr in thr_grid:
                net, _ = run_calls(p_i, gate_calls(raw_i, mi_i, direction, thr), FEE_RT)
                if gbest is None or net > gbest[0]:
                    gbest = (net, direction, thr)
        _, gd, gt = gbest
        mi_o = metric_at_calls(kind, raw_o, ts_o, p_o, bv_o, sv_o, Wr, er_o)
        gated_o = gate_calls(raw_o, mi_o, gd, gt)
        net_o, ent = run_calls(p_o, gated_o, FEE_MAKER); s = score(ent, piv_o, p_o)
        res[f"CHALL+{kind}gate"] = dict(net_maker=net_o, gate=f"{'<=' if gd>0 else '>='}{gt}",
                                        **{k: s[k] for k in ("recall", "precision", "bps_to_turn", "n_calls")})
    return res


def main():
    series = load_series("realbins")
    print("REGIME MASTER-GATE on the harness — does standing flat in bad regimes lift the dipole? "
          "(net @ MAKER floor, OOS)\n")
    rows = ["CHAMPION", "CHALLENGER", "CHALL+ERgate", "CHALL+Cgate"]
    agg = {r: [] for r in rows}
    out = {}
    print(f"{'venue':15s} {'detector':14s} {'calls':>6s} {'recall':>7s} {'prec':>6s} "
          f"{'bps2turn':>9s} {'net@mk':>8s} {'gate':>8s}")
    print("-" * 82)
    for s in sorted(series):
        ts, p, bv, sv = series[s]
        cut = int(len(p) * IS_FRAC)
        seg_is = (ts[:cut], p[:cut], bv[:cut], sv[:cut])
        seg_oos = (ts[cut:], p[cut:], bv[cut:], sv[cut:])
        r = evaluate(seg_is, seg_oos)
        out[s] = r
        for name in rows:
            d = r[name]; agg[name].append(d)
            print(f"{s if name=='CHAMPION' else '':15s} {name:14s} {d['n_calls']:>6d} "
                  f"{d['recall']:>7.3f} {str(d['precision']):>6s} {str(d['bps_to_turn']):>9s} "
                  f"{d['net_maker']:>+8.0f} {d.get('gate',''):>8s}")
        print("-" * 82)
    print("\nPOOLED OOS @ maker floor (mean recall/prec/timing; SUM net; venues net+):")
    for name in rows:
        ds = agg[name]
        mr = np.mean([d["recall"] for d in ds])
        mp = np.mean([d["precision"] for d in ds if d["precision"] is not None])
        mb = np.mean([d["bps_to_turn"] for d in ds if d["bps_to_turn"] is not None])
        nt = np.sum([d["net_maker"] for d in ds]); nw = np.sum([1 for d in ds if d["net_maker"] > 0])
        print(f"   {name:14s} recall={mr:.3f}  precision={mp:.3f}  bps2turn={mb:.1f}  "
              f"net@mk_total={nt:+.0f}  ({nw}/6 venues+)")
    with open("_info_dipole_regime_gate_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nWrote _info_dipole_regime_gate_results.json")


if __name__ == "__main__":
    main()
