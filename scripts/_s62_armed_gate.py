"""_s62_armed_gate.py — S62 Greg's REFINED armed flip: arm at -X (sweep), coeff WIN/LOSS gate.

Design (Greg, night-2): arm when a leg goes -X underwater (sweep X = 20/25/30/35/40); at the arm,
use the WIN-LONG/WIN-SHORT coeff as a second test on the FLIP direction (= opposite of our side):
  coeff says flip-direction WINS  -> FIRE the flip (reverse, ride the trend)
  coeff says flip-direction LOSS  -> FLATTEN (cut at the arm; don't flip blind into chop)
Legs that never reach -X -> HOLD. Direction coeff = the win-long/win-short mirror axis (perfect
-1.0 in the residual); built PER-WEEK OOS (centroids from other weeks' winning-long/short legs) so
it is leakage-clean. Grades net $/hr @ $5k vs baseline, per-week, and prints how many of the 10
biggest losers actually flip (Greg's success test) vs collateral on the dip-recovery winners.

fee=0 (Greg handles fees); flip = 22bp taker cross; flatten = exit at the arm depth.
Usage:  python scripts/_s62_armed_gate.py [--gate 0.0]   (gate = min |dir_score| to act; 0 = sign only)
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
from odcore.dipole_predictor import build_centroids                    # noqa: E402

CAP = 5000.0; FC = 22.0; WK = 7 * 24 * 3600
BINS = "/tmp/backfill"; CACHE = "/tmp/s62cache"
CELLS = [("sol", "SOLUSDT", 100.0), ("eth", "ETHUSDT", 80.0), ("btc", "BTCUSDT", 80.0),
         ("xrp", "XRPUSDT", 80.0), ("doge", "DOGEUSDT", 100.0)]


def coeff_cache(coin, sym, th):
    """load or compute the strictly-pre-entry 128-dim coeff per leg (aligned by entry cell)."""
    p = f"{CACHE}/{coin}_coefs.npz"
    if os.path.exists(p):
        z = np.load(p); return {int(c): z["coefs"][i] for i, c in enumerate(z["ecell"])}
    from _run_alt_coeffs import coef_for_window
    m, *_r, hrs = load_bins(f"{BINS}/{sym}_30d_bins.json"); m = np.asarray(m, float); lm = np.log(m)
    fl = armed_midband_flips(m, th, 0.5); out = {}; C = []; ecs = []; gr = []; sd = []
    for k in range(len(fl) - 1):
        ci, _p, side = fl[k]; xi = fl[k + 1][0]; ci = int(ci); xi = int(xi)
        if xi <= ci or ci < 1802:
            continue
        r = coef_for_window(list(np.diff(lm[ci - 1800:ci])))
        c = np.asarray(r[0], float) if r is not None else np.zeros(128)
        out[ci] = c; C.append(c); ecs.append(ci); gr.append(int(side) * (lm[xi] - lm[ci]) * 1e4); sd.append(int(side))
    np.savez_compressed(p, coefs=np.array(C), ecell=np.array(ecs), gross=np.array(gr),
                        side=np.array(sd), ok=np.ones(len(C), bool))
    return out


def run(coin, sym, th, xarm, gate):
    m, *_r, hrs = load_bins(f"{BINS}/{sym}_30d_bins.json"); m = np.asarray(m, float); lm = np.log(m)
    cmap = coeff_cache(coin, sym, th)
    fl = armed_midband_flips(m, th, 0.5)
    ci_a, xi_a, side_a, gross, r_arm, coefs, ec = [], [], [], [], [], [], []
    for k in range(len(fl) - 1):
        ci, _p, side = fl[k]; xi = fl[k + 1][0]; ci = int(ci); xi = int(xi); side = int(side)
        if xi <= ci or ci < 1802 or ci not in cmap:
            continue
        r = side * (lm[ci:xi + 1] - lm[ci]) * 1e4; und = np.where(r <= -xarm)[0]
        ci_a.append(ci); xi_a.append(xi); side_a.append(side); gross.append(float(r[-1]))
        r_arm.append(float(r[int(und[0])]) if len(und) else None); coefs.append(cmap[ci]); ec.append(ci)
    gross = np.array(gross); side_a = np.array(side_a); coefs = np.array(coefs); ec = np.array(ec)
    week = (ec // WK).astype(int); win = gross > 0; big = gross <= -40
    # PER-WEEK OOS direction score: centroids from other weeks' winning-long vs winning-short
    dscore = np.full(len(gross), np.nan)
    for w in sorted(set(week)):
        tr = (week != w); wl = coefs[tr & win & (side_a > 0)]; ws = coefs[tr & win & (side_a < 0)]
        if len(wl) < 10 or len(ws) < 10:
            continue
        cwl, cws = wl.mean(0), ws.mean(0); cm = (cwl + cws) / 2
        axis = (cwl - cws) / (np.linalg.norm(cwl - cws) + 1e-9)
        te = week == w; dscore[te] = (coefs[te] - cm) @ axis         # >0 = coeff says LONG wins
    # action per leg
    base = np.sum(CAP * gross / 1e4) / hrs
    pnl = gross.copy(); nflip = nflat = 0
    fired_big = fired_win = 0
    for i in range(len(gross)):
        if r_arm[i] is None or np.isnan(dscore[i]):
            continue                                                  # never armed / no score -> HOLD
        pred_win_dir = 1 if dscore[i] > 0 else -1
        flip_is_win = (pred_win_dir == -side_a[i]) and (abs(dscore[i]) >= gate)
        if flip_is_win:
            pnl[i] = -(gross[i] - r_arm[i]) - FC; nflip += 1
            fired_big += big[i]; fired_win += win[i]
        else:
            pnl[i] = r_arm[i]; nflat += 1                            # FLATTEN at the arm depth
    tot = np.sum(CAP * pnl / 1e4) / hrs
    pw = []
    for w in sorted(set(week)):
        mk = week == w; hh = (np.ptp(ec[mk]) + 1) / 3600.0 if mk.sum() else 1
        pw.append((np.sum(CAP * pnl[mk] / 1e4) - np.sum(CAP * gross[mk] / 1e4)) / hh)
    # Greg's success test: of the 10 biggest losers, how many flipped?
    order = np.argsort(gross)[:10]; big10_flip = sum(1 for i in order if pnl[i] != gross[i] and r_arm[i] is not None and (1 if dscore[i] > 0 else -1) == -side_a[i])
    return dict(base=base, tot=tot, pw=pw, nflip=nflip, nflat=nflat, fb=fired_big, fw=fired_win, big10=big10_flip)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--gate", type=float, default=0.0)
    args = ap.parse_args()
    for coin, sym, th in CELLS:
        print(f"\n[{coin}] (coeff WIN/LOSS gate on flip direction, per-week OOS; gate|score|>={args.gate})")
        print(f"   {'arm':>4}{'base':>8}{'gated':>8}{'Δ':>7}{'flip':>6}{'flat':>6}  big10-flip  fire(big/win)  per-week Δ")
        for x in (10, 15, 20):        # coeff gives the direction early -> keep the arm at 10/15 (Greg)
            r = run(coin, sym, th, float(x), args.gate)
            print(f"   -{x:<3}{r['base']:>+8.2f}{r['tot']:>+8.2f}{r['tot']-r['base']:>+7.2f}"
                  f"{r['nflip']:>6}{r['nflat']:>6}     {r['big10']:>2}/10      {r['fb']:>3}/{r['fw']:<3}     "
                  + " ".join(f"{v:+.1f}" for v in r['pw']))


if __name__ == "__main__":
    main()
