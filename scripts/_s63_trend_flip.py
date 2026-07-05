"""_s63_trend_flip.py — S63 JOB 1: the 1-HOUR TREND-FADE flip (Greg's S62-close lead).

The reframe (S62): the big losers are a DIRECTION mistake — the machine (a 600s mean-reverter,
its own edge) SHORTS into clean 1-HOUR UPTRENDS (and longs into downtrends). At the 600s scale
direction is ~chance (the market mean-reverts there). But at the RIGHT horizon — 1 HOUR — the
trend predicts the forward direction: among the big losers the 1h momentum reads direction at
0.58-0.67. "Know the trend, short or long."

The signal is CAUSAL and PARAMETER-FREE (no fit): at entry,
    fade = -side * mom1h ,   mom1h = log(mid[ci] / mid[ci - W])   (signed 1h log-return, bp)
fade > 0  <=>  the machine took the side OPPOSITE the W-horizon trend (it is FADING the trend).
fade large <=> it is fading a STRONG trend. Those are the mislabeled-direction big losers.

POLICY (entry flip): flip the legs with the strongest fade (fade in the top `cutpct` percentile),
reverse the whole leg and pay the taker cross; HOLD everything else.
    flip pnl = -gross - FC          (entry reversal, 22bp taker cross)
    hold pnl =  gross               (the machine's own leg)

GRADING (Greg's scoreboard + README Phase-0 discipline):
  - net $/hr @ $5k CAP, vs the machine baseline (HOLD-all).
  - per-week lift (robustness; the signal is parameter-free so per-week is honest OOS).
  - SHUFFLE-NULL floor (authoritative): permute WHICH legs are flipped (same count) N times;
    the real lift must beat its own shuffled shadow (z, p). A knife-edge that only clears at
    one (W, cutpct) is an overfit; a real edge holds across a BAND.
  - big10-flip: of the 10 biggest losers, how many does the policy flip? (Greg's success test.)

Fee frame = Coinbase; tests fee=0; the FLIP is the 22bp taker cross (FC). Same leg population as
the S62 rig (armed_midband_flips, naive k0) on the 30d Binance-spot bins.

Usage:  python scripts/_s63_trend_flip.py            # full sweep, all 5 coins
        python scripts/_s63_trend_flip.py --coin sol # one coin
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.entry_coinbase import armed_midband_flips                  # noqa: E402

CAP = 5000.0            # capital clip ($) — S62 convention
FC = 22.0               # flip = 22bp taker cross (locked S62)
WK = 7 * 24 * 3600      # week in seconds, for per-week splits
BINS = os.environ.get("S62_BINS_DIR", "/tmp/backfill")
CELLS = [("sol", "SOLUSDT", 100.0), ("eth", "ETHUSDT", 80.0), ("btc", "BTCUSDT", 80.0),
         ("xrp", "XRPUSDT", 80.0), ("doge", "DOGEUSDT", 100.0)]
WINDOWS = [3600, 7200, 14400]        # 1h / 2h / 4h trend horizon
CUTPCTS = [80.0, 85.0, 90.0]         # flip top 20% / 15% / 10% of fades
N_SHUF = 500
SEED = 12345


def build_legs(sym, th, W):
    """Legs (ci, xi, side, gross, fade, week) for one coin at trend-window W.

    fade = -side * mom(W) at entry; only legs with ci >= W (1h history available) kept.
    """
    m, b, s, cov, hrs = load_bins(f"{BINS}/{sym}_30d_bins.json")
    m = np.asarray(m, float); lm = np.log(m); n = len(m)
    fl = armed_midband_flips(m, th, 0.5)
    ci_l, xi_l, side_l, gross_l, fade_l = [], [], [], [], []
    for k in range(len(fl) - 1):
        ci, _p, side = fl[k]; xi = fl[k + 1][0]
        ci = int(ci); xi = int(xi); side = int(side)
        if xi <= ci or ci < W or ci < 1802 or xi >= n:
            continue
        gross = side * (lm[xi] - lm[ci]) * 1e4
        mom = (lm[ci] - lm[ci - W]) * 1e4          # signed W-horizon log-return, bp
        fade = -side * mom                          # >0 = fading the trend
        ci_l.append(ci); xi_l.append(xi); side_l.append(side)
        gross_l.append(gross); fade_l.append(fade)
    ci = np.array(ci_l); xi = np.array(xi_l); side = np.array(side_l)
    gross = np.array(gross_l); fade = np.array(fade_l)
    week = (ci // WK).astype(int)
    return dict(ci=ci, xi=xi, side=side, gross=gross, fade=fade, week=week, hrs=hrs)


def dph(pnl):
    """net $/hr @ $5k over a 30d (720h) window — matches the E300 rig's /720 convention."""
    return float(np.sum(CAP * pnl / 1e4) / 720.0)


def grade(D, W, cutpct, rng):
    """Grade the fade-flip policy at (W, cutpct). Returns metrics + shuffle-null z/p."""
    gross = D["gross"]; fade = D["fade"]; week = D["week"]; ci = D["ci"]
    ngl = len(gross)
    if ngl == 0:
        return None
    # policy: flip strongest fades (top cutpct) that are actually fading (fade>0)
    thr = np.percentile(fade, cutpct)
    flip = (fade >= thr) & (fade > 0)
    flip_pnl = -gross - FC
    pnl = np.where(flip, flip_pnl, gross)
    base = dph(gross); tot = dph(pnl); lift = tot - base

    # per-week lift
    pw = []
    for w in sorted(set(week)):
        mk = week == w
        hh = (np.ptp(ci[mk]) + 1) / 3600.0 if mk.sum() > 1 else 1.0
        pw.append(float((np.sum(CAP * pnl[mk] / 1e4) - np.sum(CAP * gross[mk] / 1e4)) / hh))
    wk_pos = sum(1 for v in pw if v > 0)

    # big10: of the 10 most-negative gross legs, how many are flipped
    order = np.argsort(gross)[:10]
    big10 = int(np.sum(flip[order]))

    # SHUFFLE-NULL floor: permute WHICH legs are flipped (same count), recompute lift
    nflip = int(flip.sum())
    null = np.empty(N_SHUF)
    idx = np.arange(ngl)
    for j in range(N_SHUF):
        sh = rng.permutation(idx)[:nflip]
        m = np.zeros(ngl, bool); m[sh] = True
        null[j] = dph(np.where(m, flip_pnl, gross)) - base
    mu = float(null.mean()); sd = float(null.std() + 1e-12)
    z = (lift - mu) / sd
    p = float((np.sum(null >= lift) + 1) / (N_SHUF + 1))
    return dict(base=base, tot=tot, lift=lift, pw=pw, wk_pos=wk_pos, nwk=len(pw),
                nflip=nflip, ntot=ngl, big10=big10, znull=z, pnull=p, mu=mu, sd=sd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coin", default=None)
    args = ap.parse_args()
    cells = [c for c in CELLS if args.coin is None or c[0] == args.coin]
    rng = np.random.default_rng(SEED)

    for coin, sym, th in cells:
        path = f"{BINS}/{sym}_30d_bins.json"
        if not os.path.exists(path):
            print(f"[{coin}] bins missing at {path}"); continue
        print(f"\n[{coin}]  1h-trend-fade flip (entry reversal, flip=22bp taker; per-week + shuffle-null)")
        print(f"   {'W':>6}{'cut':>5}{'legs':>6}{'flip':>5}{'base':>8}{'flip$':>8}{'Δ$/hr':>8}"
              f"{'z_null':>8}{'p':>7}{'wk+':>5} big10   per-week Δ")
        for W in WINDOWS:
            D = build_legs(sym, th, W)
            for cut in CUTPCTS:
                r = grade(D, W, cut, rng)
                if r is None:
                    continue
                hh = "1h" if W == 3600 else ("2h" if W == 7200 else "4h")
                print(f"   {hh:>6}{cut:>5.0f}{r['ntot']:>6}{r['nflip']:>5}{r['base']:>+8.2f}"
                      f"{r['tot']:>+8.2f}{r['lift']:>+8.2f}{r['znull']:>+8.2f}{r['pnull']:>7.3f}"
                      f"{r['wk_pos']:>3}/{r['nwk']} {r['big10']:>2}/10  "
                      + " ".join(f"{v:+.1f}" for v in r['pw']))


if __name__ == "__main__":
    main()
