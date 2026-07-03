"""_s59_fingerprint_prep.py — S59 FINGERPRINT WIRE-IN PREP (micros tier, MEASUREMENT ONLY).

The S58 standing item (Greg: predict winners by their DISTINCTIVE fingerprint at entry;
all five coin agents found big winners INVISIBLE to the individual causal flow reads —
separation, if any, lives in bucket/joint structure). This round is the mid-band micros-tier
prep the kickoff names: per-cell winner/loser ONSET buckets from the 30d legs + the
DUAL-PRINT scorer (match-to-winner MINUS match-to-loser), graded OOS.

ONE DEFINED TEST: on the DEPLOY-SHAPE legs (naive k0 armed machine, registry theta per coin),
does a per-cell dual-print score over the causal onset feature vector separate winners from
losers OUT-OF-SAMPLE (train half -> test half, and the reverse)?

Feature vector at the confirm cell (ALL strictly causal — computed from tape <= confirm idx;
the S58 leg-dump descriptor set, continuous form):
  opposing, exhausting (S36 divergence at the pivot), clmx60 (vm60/vm600), er600,
  fade_vel (bp/min into the pivot), dive... (dive omitted: needs fine lean series; the
  mid-band proxies are) runup_norm, dur_arm (bars pivot->confirm), hod_sin, hod_cos, side.

Dual-print score = cos(x, winner_centroid) - cos(x, loser_centroid), centroids + feature
standardization fit on the TRAIN half only (per cell). Graded by: AUC(test), mean net of
top-quartile vs bottom-quartile test legs, both split directions.

WHAT THIS IS NOT: no wiring, no machine config, no threshold picked. The S35 coeff/encoder
tier stays behind its onset canary (S35b precondition; archives on Greg's E: drive). If the
micros-tier dual-print shows OOS separation here, THE candidate 5th member exists at
mid-band and the wire-in graduates to a machine-config round with the full gate battery.

LEAKAGE: features recomputed on a prefix tape must match (asserted per cell on a sample).

Usage: python scripts/_s59_fingerprint_prep.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins, COINS                     # noqa: E402
from odcore.entry_coinbase import armed_midband_flips                # noqa: E402
from odcore.info_dipole import divergence                            # noqa: E402

# registry deploy shapes (five-verdict board; eth dropped)
SHAPES = {"sol": 100.0, "btc": 80.0, "doge": 100.0, "xrp": 80.0}
C = 0.5
DIVW = 600
FEE_RT = 16.0            # cb_real round trip — the WIN label is net-of-deploy-fee positive


def leg_features(mid, buy, sell, cpath, flips, hrs):
    """Per-leg (features, gross_bp, entry_idx). Features strictly causal at the confirm."""
    cb = np.concatenate([[0.0], np.cumsum(buy)])
    cs = np.concatenate([[0.0], np.cumsum(sell)])
    out = []
    for k in range(len(flips) - 1):
        ci, pi, sd = (int(x) for x in flips[k])
        cj = int(flips[k + 1][0])
        gross = sd * (mid[cj] - mid[ci]) / mid[ci] * 1e4
        lo = max(0, pi - DIVW)
        opp = exh = 0.0
        if pi - lo >= 12:
            dv = divergence(buy[lo:pi + 1], sell[lo:pi + 1], float(mid[pi] - mid[lo]))
            if dv is not None:
                opp = float(bool(dv["opposing"])); exh = float(bool(dv["exhausting"]))
        v60 = (cb[pi + 1] + cs[pi + 1] - cb[max(0, pi - 59)] - cs[max(0, pi - 59)]) / 60.0
        v600 = (cb[pi + 1] + cs[pi + 1] - cb[max(0, pi - 599)] - cs[max(0, pi - 599)]) / 600.0
        clmx = v60 / v600 if v600 > 0 else 0.0
        path = cpath[pi] - cpath[lo]
        er = (abs(mid[pi] - mid[lo]) / path) if path > 0 else 0.0
        p0 = max(0, pi - 120)
        fade = -sd * (mid[pi] - mid[p0]) / mid[p0] * 1e4 / 2.0
        runup = abs(mid[pi] - mid[lo]) / mid[lo] * 1e4
        dur = float(ci - pi)
        hod = (ci % 86400) / 86400.0 * 2 * np.pi
        x = np.array([opp, exh, clmx, er, fade, runup, np.log1p(dur),
                      np.sin(hod), np.cos(hod), float(sd)])
        out.append((x, gross, ci))
    return out


def dual_print_eval(legs, split_frac=0.5):
    """Train centroids on one half, score the other; both directions. Returns rows."""
    X = np.array([x for x, g, c in legs])
    G = np.array([g for x, g, c in legs])
    n = len(G)
    cut = int(n * split_frac)
    rows = []
    for tr, te, name in ((slice(0, cut), slice(cut, None), "early->late"),
                         (slice(cut, None), slice(0, cut), "late->early")):
        Xtr, Gtr, Xte, Gte = X[tr], G[tr], X[te], G[te]
        win = Gtr > 0            # winner = fee-free gross>0 on train; deploy-fee variant below
        winf = Gtr > FEE_RT
        for lbl, w in (("gross>0", win), ("net>fee", winf)):
            if w.sum() < 8 or (~w).sum() < 8 or len(Gte) < 20:
                continue
            mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
            Ztr, Zte = (Xtr - mu) / sd, (Xte - mu) / sd
            cw = Ztr[w].mean(0); cl = Ztr[~w].mean(0)
            def cos(A, b):
                nb = np.linalg.norm(b) + 1e-12
                return (A @ b) / ((np.linalg.norm(A, axis=1) + 1e-12) * nb)
            score = cos(Zte, cw) - cos(Zte, cl)
            yw = Gte > (FEE_RT if lbl == "net>fee" else 0.0)
            if yw.sum() == 0 or yw.sum() == len(yw):
                continue
            order = np.argsort(score)
            ranks = np.empty(len(score)); ranks[order] = np.arange(len(score))
            auc = (ranks[yw].mean() - (yw.sum() - 1) / 2) / (~yw).sum()
            q = len(score) // 4
            top, bot = order[-q:], order[:q]
            rows.append((name, lbl, len(Gte), float(auc),
                         float(Gte[top].mean()), float(Gte[bot].mean())))
    return rows


def leakage_spotcheck(mid, buy, sell, cpath, flips, hrs):
    """Features from a 2/3-prefix tape must equal full-tape features for legs inside it."""
    n = len(mid)
    cut = (2 * n) // 3
    fl_pre = [f for f in flips if int(f[0]) < cut and True]
    full = {c: x for x, g, c in leg_features(mid, buy, sell, cpath, flips, hrs)}
    # recompute on the prefix
    pre_flips = [f for f in flips if int(f[0]) < cut]
    pre = leg_features(mid[:cut], buy[:cut], sell[:cut], cpath[:cut], pre_flips, hrs)
    for x, g, c in pre[:-1]:                      # last leg's gross needs the next confirm
        if c in full and not np.allclose(x, full[c]):
            return False
    return True


def main():
    print("S59 fingerprint prep — dual-print micros tier, deploy-shape legs, OOS half-split")
    print(f"{'cell':>10} {'split':>12} {'label':>8} | {'n_te':>5} {'AUC':>6} "
          f"{'topQ gr':>8} {'botQ gr':>8}")
    for coin, sym in COINS:
        if coin not in SHAPES:
            continue
        p = f"/tmp/backfill/{sym}_30d_bins.json"
        if not os.path.exists(p):
            print(f"[{coin}] bins missing"); continue
        mid, buy, sell, cover, hrs = load_bins(p)
        mid = np.asarray(mid, float)
        buy = np.asarray(buy, float); sell = np.asarray(sell, float)
        cpath = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(mid)))])
        theta = SHAPES[coin]
        flips = armed_midband_flips(mid, theta, C)
        legs = leg_features(mid, buy, sell, cpath, flips, hrs)
        ok = leakage_spotcheck(mid, buy, sell, cpath, flips, hrs)
        print(f"[{coin}] th{theta:.0f} k0: {len(legs)} legs | leakage spotcheck "
              f"{'PASS' if ok else 'FAIL'}")
        if not ok:
            continue
        for name, lbl, nte, auc, tq, bq in dual_print_eval(legs):
            print(f"{coin+'_mb'+str(int(theta)):>10} {name:>12} {lbl:>8} | {nte:>5} "
                  f"{auc:>6.3f} {tq:>+8.2f} {bq:>+8.2f}")


if __name__ == "__main__":
    main()
