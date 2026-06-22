"""_info_dipole_harness.py — the falsification scoreboard: OD dipole filter vs a classical champion.

Architect's test D (S36b): score turn-detectors on FROZEN fine-resolution data, OUT-OF-SAMPLE, by
bps-to-turn (timing) + FN-rate at matched FP (filtering) + net of the per-leg fee floor. Do NOT run
"quantum vs classical" (the unification thesis predicts a null). Run the OD-recovered operator vs a STRONG
CLASSICAL CHAMPION (order-flow imbalance + tuned reversal filter), BOTH classical.

Surgical design: both detectors share the SAME timing trigger (price reverses R bps off the running
extreme = a candidate turn); they differ ONLY in the FILTER that decides which candidates are real:
  - CHAMPION  filter = raw order-flow IMBALANCE threshold over a window (the classical baseline).
  - CHALLENGER filter = the OD dipole `divergence()` (exhaustion + divergence, the S36 read).
Same timing → the comparison isolates FILTERING, which is exactly where the Architect predicts OD wins.

Ground truth = ZigZag pivots at a tradeable swing size (theta, swings that clear the fee floor). A call
(i,dir) is a TRUE POSITIVE if it's the first matching-direction call on the leg a true pivot opens; missed
pivots = FN; unmatched calls = FP. Net trades the calls (flip at each), per-leg fee (slippage is already in
the realized entry/exit prices, which are R bps off the turn). Tune each detector on the in-sample 60%,
score the out-of-sample 40%. Discipline: a challenger only enters the harness AFTER it passes a pre-entry
leakage check — `divergence()` uses only the strictly-prior window, so it qualifies.

Run: python _info_dipole_harness.py
"""
from __future__ import annotations

import json

import numpy as np

from odcore.info_dipole import divergence
from _info_dipole_swing_backtest import load_series, zigzag, trailing_imbalance

FEE_RT = 10.0          # taker round-trip per leg (bps); slippage already in realized prices
FEE_MAKER = 4.0        # maker/maker round-trip per leg (rest at the turn) — the fee-floor lever
SWING_THETA = 0.0020   # tradeable swing size (20 bps) defining the true turns
IS_FRAC = 0.60         # in-sample fraction (tune); rest is out-of-sample (score)


def candidates(p, R):
    """Timing trigger: every R-bps price reversal off the running extreme -> (confirm_idx, dir, extreme_idx)."""
    out = []
    n = len(p); mode = 0; ext_i = 0; ext = p[0]
    for i in range(1, n):
        if mode == 0:
            if p[i] >= p[0] * (1 + R): mode = 1; ext = p[i]; ext_i = i
            elif p[i] <= p[0] * (1 - R): mode = -1; ext = p[i]; ext_i = i
        elif mode == 1:
            if p[i] > ext: ext = p[i]; ext_i = i
            elif p[i] <= ext * (1 - R): out.append((i, -1, ext_i)); mode = -1; ext = p[i]; ext_i = i
        else:
            if p[i] < ext: ext = p[i]; ext_i = i
            elif p[i] >= ext * (1 + R): out.append((i, 1, ext_i)); mode = 1; ext = p[i]; ext_i = i
    return out


def filt_champion(cand, ts, p, bv, sv, W, T):
    """Classical: keep a candidate turn only if order-flow imbalance over W confirms the reversal dir."""
    imb = trailing_imbalance(ts, bv, sv, W)
    return [(i, d) for (i, d, ei) in cand
            if (d < 0 and imb[i] <= -T) or (d > 0 and imb[i] >= T)]


def filt_dipole(cand, ts, p, bv, sv, W, C):
    """OD: keep a candidate only if the dipole expects a reversal AND reversal_conviction >= C.
    C is the selectivity knob (the dipole analogue of the champion's imbalance threshold T)."""
    C = C or 0.0
    keep = []
    for (i, d, ei) in cand:
        lo = int(np.searchsorted(ts, ts[i] - W))
        if i - lo < 6:
            continue
        drift = p[ei] - p[lo]                       # the move INTO the extreme (the leg that's ending)
        dv = divergence(bv[lo:i + 1], sv[lo:i + 1], drift)
        if dv is not None and dv["expect"] == "reversal" and dv["reversal_conviction"] >= C:
            keep.append((i, d))
    return keep


def run_calls(p, calls, fee):
    """Trade the calls: flip to each call's dir; per-leg fee. Returns (net_bps_total, entries[list (i,dir)])."""
    pos = 0; entry_i = 0; net = 0.0; entries = []
    for i, d in calls:
        if d != 0 and d != pos:
            if pos != 0:
                net += pos * (p[i] / p[entry_i] - 1.0) * 1e4 - fee
            pos = d; entry_i = i; entries.append((i, d))
    if pos != 0:
        net += pos * (p[-1] / p[entry_i] - 1.0) * 1e4 - fee
    return round(net, 1), entries


def score(entries, pivots, p):
    """Confusion + timing vs the true turns. entries/pivots sorted by index."""
    if not entries:
        return dict(n_calls=0, TP=0, FP=0, FN=len(pivots), recall=0.0, precision=None,
                    bps_to_turn=None, net=None)
    ci = np.array([e[0] for e in entries]); cd = np.array([e[1] for e in entries])
    used = np.zeros(len(entries), bool)
    TP = 0; FN = 0; offs = []
    for k, (j, t) in enumerate(pivots):
        jn = pivots[k + 1][0] if k + 1 < len(pivots) else len(p)
        want = 1 if t == "L" else -1
        m = np.where((ci > j) & (ci <= jn) & (cd == want) & (~used))[0]
        if m.size:
            used[m[0]] = True; TP += 1; offs.append(abs(p[ci[m[0]]] / p[j] - 1.0) * 1e4)
        else:
            FN += 1
    FP = int((~used).sum())
    return dict(n_calls=len(entries), TP=TP, FP=FP, FN=FN, n_turns=len(pivots),
                recall=round(TP / max(1, len(pivots)), 3),
                precision=round(TP / max(1, len(entries)), 3),
                bps_to_turn=round(float(np.median(offs)), 1) if offs else None)


def tune_and_score(name, filt, grid, seg_is, seg_oos):
    """Grid-search params to MAX in-sample net; score the chosen params out-of-sample."""
    ts_i, p_i, bv_i, sv_i = seg_is
    ts_o, p_o, bv_o, sv_o = seg_oos
    cand_is = {R: candidates(p_i, R) for R in {g[0] for g in grid}}
    best = None
    for (R, W, T) in grid:
        calls = filt(cand_is[R], ts_i, p_i, bv_i, sv_i, W, T)
        net, _ = run_calls(p_i, calls, FEE_RT)
        if best is None or net > best[0]:
            best = (net, R, W, T)
    _, R, W, T = best
    cand_o = candidates(p_o, R)
    calls_o = filt(cand_o, ts_o, p_o, bv_o, sv_o, W, T)
    net_o, entries = run_calls(p_o, calls_o, FEE_RT)
    net_mk, _ = run_calls(p_o, calls_o, FEE_MAKER)
    piv_o = zigzag(p_o, SWING_THETA)
    s = score(entries, piv_o, p_o)
    s.update(net_oos=net_o, net_oos_maker=net_mk, params=dict(R_bps=R * 1e4, W_s=W, T=T))
    return s


def main():
    series = load_series("realbins")
    champ_grid = [(R / 1e4, W, T) for R in (5, 8, 12) for W in (60, 300) for T in (0.05, 0.10, 0.20)]
    chall_grid = [(R / 1e4, W, C) for R in (5, 8, 12) for W in (300, 900, 1800) for C in (0.0, 0.15, 0.30, 0.50)]

    print("FALSIFICATION HARNESS — OD dipole filter vs classical OFI champion (same timing trigger).")
    print(f"Frozen 1-sec realbins, OUT-OF-SAMPLE (tune on first {int(IS_FRAC*100)}%, score last "
          f"{int((1-IS_FRAC)*100)}%). Fee {FEE_RT}bps/leg round-trip. True turns = {SWING_THETA*1e4:.0f}bp swings.")
    print("recall = 1 - FN rate (caught turns); precision = TP/calls (1 - FP rate); bps_to_turn = timing.\n")
    print(f"{'venue':15s} {'detector':10s} {'calls':>6s} {'recall':>7s} {'prec':>6s} "
          f"{'bps2turn':>9s} {'net_oos':>9s}")
    print("-" * 74)
    agg = {"CHAMPION": [], "CHALLENGER": []}
    out = {}
    for s in sorted(series):
        ts, p, bv, sv = series[s]
        cut = int(len(p) * IS_FRAC)
        seg_is = (ts[:cut], p[:cut], bv[:cut], sv[:cut])
        seg_oos = (ts[cut:], p[cut:], bv[cut:], sv[cut:])
        champ = tune_and_score("CHAMPION", filt_champion, champ_grid, seg_is, seg_oos)
        chall = tune_and_score("CHALLENGER", filt_dipole, chall_grid, seg_is, seg_oos)
        out[s] = {"champion": champ, "challenger": chall}
        for tag, r in [("CHAMPION", champ), ("CHALLENGER", chall)]:
            agg[tag].append(r)
            print(f"{s if tag=='CHAMPION' else '':15s} {tag:10s} {r['n_calls']:>6d} "
                  f"{r['recall']:>7.3f} {str(r['precision']):>6s} {str(r['bps_to_turn']):>9s} "
                  f"{r['net_oos']:>+8.0f} {r['net_oos_maker']:>+8.0f}")
        print("-" * 74)

    print("\nPOOLED OOS (mean over venues):")
    for tag in ("CHAMPION", "CHALLENGER"):
        rs = agg[tag]
        mr = np.mean([r["recall"] for r in rs])
        mp = np.mean([r["precision"] for r in rs if r["precision"] is not None])
        mb = np.mean([r["bps_to_turn"] for r in rs if r["bps_to_turn"] is not None])
        nt = np.sum([r["net_oos"] for r in rs])
        ntm = np.sum([r["net_oos_maker"] for r in rs])
        nw = np.sum([1 for r in rs if r["net_oos"] > 0]); nwm = np.sum([1 for r in rs if r["net_oos_maker"] > 0])
        print(f"   {tag:10s} recall={mr:.3f}  precision={mp:.3f}  bps_to_turn={mb:.1f}  "
              f"net@10taker={nt:+.0f} ({nw}/6+)  net@4maker={ntm:+.0f} ({nwm}/6+)")
    print("\nRead: if CHALLENGER beats CHAMPION on recall/precision (FILTERING) at similar bps_to_turn,")
    print("the dipole adds turn-filtering edge (Architect's soft prediction). If only net differs, it's timing.")

    with open("_info_dipole_harness_results.json", "w") as f:
        json.dump({"config": {"fee_rt_bps": FEE_RT, "swing_theta_bps": SWING_THETA * 1e4,
                              "is_frac": IS_FRAC}, "per_venue": out}, f, indent=2)
    print("\nWrote _info_dipole_harness_results.json")


if __name__ == "__main__":
    main()
