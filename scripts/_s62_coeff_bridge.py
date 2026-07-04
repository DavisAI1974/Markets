"""_s62_coeff_bridge.py — S62 do-2 BRIDGE: git loser-signature -> CURRENT legs (same-period).

The honest test the S34 date-confound demands. The git 128-dim coeffs separate win/lose at
AUC 0.78-0.93 IN-SAMPLE, but on the S35 fine-scale archives (win/lose from disjoint windows).
Here: compute each CURRENT mid-band leg's OWN strictly-pre-entry 128-dim coeff (the deterministic
in-container pipeline, identical recipe to _run_alt_coeffs), project it onto the git win/lose
CENTROIDS (side-matched cell), and ask whether CURRENT big-losers (labeled by their own outcome,
same period -> no date confound) score loser-aligned. If yes, the signature is real + portable
-> flip driver deployable. If not, the old separation was confound/scale-local -> needs per-mid-band
coeff re-derivation (the named precondition).

loser_score = H_b - H_a  where  H_a=<c,c_win>/||c_win||, H_b=<c,c_lose>/||c_lose||  (dipole_predictor).

Usage:  python scripts/_s62_coeff_bridge.py --coin btc --theta 80 --bigloss 40
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins, COINS                       # noqa: E402
from odcore.entry_coinbase import armed_midband_flips                  # noqa: E402
from odcore.dipole_predictor import build_centroids, project           # noqa: E402
from _run_alt_coeffs import coef_for_window                            # noqa: E402

CAP = 5000.0
FC = 22.0
BINS_DIR = os.environ.get("S62_BINS_DIR", "/tmp/backfill")
SYM = dict(COINS)
PRE = 1800                     # strictly-pre-entry window (cells) = 30 min on 1s bins (cs100_v2)
COEFF_IDX = "fingerprint_dataset/coeffs/coeff_index.json.gz"


def load_centroids(coin):
    """git win/lose centroids per side-cell, cs2000_clean lineage (same-lineage clean)."""
    d = json.load(gzip.open(COEFF_IDX))["by_source_id"]
    out = {}
    for side_name in ("buy", "sell"):
        cell = f"{coin}_coinbase_{side_name}"
        win = [r["coef"] for r in d.values()
               if r["cell"] == cell and r["lineage"] == "cs2000_clean" and r["label"] == "win"]
        lose = [r["coef"] for r in d.values()
                if r["cell"] == cell and r["lineage"] == "cs2000_clean" and r["label"] == "lose"]
        C = np.array(win + lose, float)
        y = np.r_[np.ones(len(win)), np.zeros(len(lose))]
        c_win, c_lose = build_centroids(C, y)
        out[side_name] = (c_win, c_lose, len(win), len(lose))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coin", default="btc")
    ap.add_argument("--theta", type=float, default=80.0)
    ap.add_argument("--bigloss", type=float, default=40.0)
    ap.add_argument("--limit", type=int, default=0, help="cap legs for a quick smoke run")
    ap.add_argument("--save", default="", help="npz path to cache coefs/gross/ecell/side for the stack")
    args = ap.parse_args()

    cents = load_centroids(args.coin)
    print(f"[{args.coin}] centroids: "
          + "  ".join(f"{s}(win{cents[s][2]}/lose{cents[s][3]})" for s in cents))

    sym = SYM[args.coin]
    mid, *_r, hrs = load_bins(os.path.join(BINS_DIR, f"{sym}_30d_bins.json"))
    mid = np.asarray(mid, float)
    logmid = np.log(mid)
    flips = armed_midband_flips(mid, args.theta)
    legs = []
    for k in range(len(flips) - 1):
        ci, _p, side = flips[k]; xi = flips[k + 1][0]
        ci = int(ci); xi = int(xi)
        if xi > ci and ci >= PRE + 2:
            legs.append((ci, xi, int(side)))
    if args.limit:
        legs = legs[:args.limit]

    gross, score, ok, coefs = [], [], [], []
    for ci, xi, side in legs:
        g = side * (logmid[xi] - logmid[ci]) * 1e4
        lr = list(np.diff(logmid[ci - PRE:ci]))       # strictly pre-entry log-returns
        res = coef_for_window(lr)
        gross.append(g)
        if res is None:
            score.append(np.nan); ok.append(False); coefs.append(np.zeros(128)); continue
        c = np.asarray(res[0], float)
        coefs.append(c)
        side_name = "buy" if side > 0 else "sell"
        c_win, c_lose, nw, nl = cents[side_name]
        Ha, Hb = project(c, c_win, c_lose)
        score.append(Hb - Ha)                          # higher = more loser-aligned
        ok.append(True)
    gross = np.array(gross); score = np.array(score); ok = np.array(ok); coefs = np.array(coefs)
    if args.save:
        np.savez_compressed(args.save, coefs=coefs, gross=gross, ok=ok,
                            ecell=np.array([ci for ci, _, _ in legs]),
                            side=np.array([s for _, _, s in legs]))
        print(f"  [cached {coefs.shape} coeffs -> {args.save}]")
    winner = gross > 0; bigloss = gross <= -args.bigloss
    m = ok & (winner | bigloss)
    from sklearn.metrics import roc_auc_score
    sides = np.array([s for _, _, s in legs])
    ecells = np.array([ci for ci, _, _ in legs])
    week = (ecells // (7 * 24 * 3600)).astype(int)

    def _auc(mask):
        mm = m & mask
        return (roc_auc_score(bigloss[mm], score[mm])
                if len(np.unique(bigloss[mm])) > 1 and mm.sum() > 10 else float("nan"))

    auc = _auc(np.ones(len(m), bool))
    print(f"  legs scored={int(ok.sum())}/{len(legs)}  winners={int(winner.sum())}  "
          f"big-losers={int(bigloss.sum())}")
    print(f"  SAME-PERIOD bridge AUC (big-loser vs winner) = {auc:.3f}   "
          f"(cheap floor ~0.55; git in-sample 0.93/0.80; 0.50 = chance)")
    print("  CONSISTENCY — per side:  "
          + "  ".join(f"{sn}={_auc(sides == sv):.3f}(n{int((m&(sides==sv)).sum())})"
                      for sn, sv in (("buy", 1), ("sell", -1))))
    print("  CONSISTENCY — per week:  "
          + "  ".join(f"w{w}={_auc(week == w):.3f}" for w in sorted(set(week))))

    # PER-MID-BAND RE-DERIVATION: build centroids from CURRENT legs (per-week OOS), not the
    # old S35 archives — does the coeff carry ANY same-period signal at its own scale?
    train = m & (winner | bigloss)
    y = bigloss.astype(int)
    rd = np.full(len(gross), np.nan)
    for w in sorted(set(week)):
        tr = train & (week != w); te = ok & (week == w)
        if tr.sum() < 20 or len(np.unique(y[tr])) < 2:
            continue
        cw, cl = build_centroids(coefs[tr], y[tr])
        for i in np.where(te)[0]:
            Ha, Hb = project(coefs[i], cw, cl)
            rd[i] = Hb - Ha
    mm = m & ~np.isnan(rd)
    rd_auc = (roc_auc_score(bigloss[mm], rd[mm])
              if len(np.unique(bigloss[mm])) > 1 else float("nan"))
    print(f"  RE-DERIVED (current-leg centroids, per-week OOS) AUC = {rd_auc:.3f}   "
          f"<- centroid projection (common-mode collapsed — README says don't grade this way)")

    # MULTIVARIATE — the RIGHT tool (Greg): a full classifier on all 128 coeff dims, per-week
    # OOS, captures the residual the centroid collapses. Does the coeff DIFFER from winners
    # consistently (per week)?
    from sklearn.linear_model import LogisticRegression
    mv = np.full(len(gross), np.nan)
    for w in sorted(set(week)):
        tr = train & (week != w); te = ok & (week == w)
        if tr.sum() < 30 or len(np.unique(y[tr])) < 2:
            continue
        mu = coefs[tr].mean(0); sd = coefs[tr].std(0) + 1e-9
        clf = LogisticRegression(max_iter=3000, C=0.3, class_weight="balanced")
        clf.fit((coefs[tr] - mu) / sd, y[tr])
        mv[te] = clf.predict_proba((coefs[te] - mu) / sd)[:, 1]
    mv_m = m & ~np.isnan(mv)
    mv_auc = (roc_auc_score(bigloss[mv_m], mv[mv_m])
              if len(np.unique(bigloss[mv_m])) > 1 else float("nan"))
    per_wk = "  ".join(
        f"w{w}={roc_auc_score(bigloss[mv_m & (week == w)], mv[mv_m & (week == w)]):.2f}"
        if (mv_m & (week == w)).sum() > 10 and len(np.unique(bigloss[mv_m & (week == w)])) > 1
        else f"w{w}=--" for w in sorted(set(week)))
    print(f"  MULTIVARIATE (128-dim logistic, per-week OOS) AUC = {mv_auc:.3f}   [{per_wk}]")

    # DIAGNOSTIC (Greg: "consistently there + differs from winner = signal"). (1) coeffs distinct,
    # not degenerate? (2) how many of 128 dims differ big-loser vs winner (Welch p<0.05) vs the
    # ~6.4 expected by chance — and does it REPRODUCE across the two halves of the window (consistency)?
    from scipy import stats
    Cb = coefs[m & bigloss]; Cw = coefs[m & winner]
    # distinctiveness: mean pairwise cosine among a sample (1.0 = all identical/degenerate)
    samp = coefs[m][np.random.default_rng(0).choice(int(m.sum()), min(200, int(m.sum())), replace=False)]
    sn = samp / (np.linalg.norm(samp, axis=1, keepdims=True) + 1e-12)
    cos = sn @ sn.T; iu = np.triu_indices(len(sn), 1)
    print(f"  coeff distinctiveness: mean pairwise cosine {cos[iu].mean():.3f} "
          f"(1.0=degenerate; lower=distinct)")
    p = np.array([stats.ttest_ind(Cb[:, j], Cw[:, j], equal_var=False).pvalue for j in range(128)])
    ndiff = int((p < 0.05).sum())
    # consistency across window halves (first vs second half of the 30d, per dim sign agreement)
    ec = np.array([ci for ci, _, _ in legs]); half = ec > np.median(ec)
    b1 = coefs[m & bigloss & half].mean(0) - coefs[m & winner & half].mean(0)
    b0 = coefs[m & bigloss & ~half].mean(0) - coefs[m & winner & ~half].mean(0)
    sig = p < 0.05
    consist = int((np.sign(b1[sig]) == np.sign(b0[sig])).sum()) if sig.sum() else 0
    print(f"  per-dim big-loser vs winner: {ndiff}/128 dims differ p<0.05 (chance ~6); of those, "
          f"{consist}/{ndiff} keep the SAME sign in both window-halves (consistency)")

    # flip driver on the loser_score
    base = float(np.sum(CAP * gross / 1e4)) / hrs
    orc = float(np.sum(CAP * np.where(bigloss, -gross - FC, gross) / 1e4)) / hrs
    print(f"  BASELINE {base:+.2f}  ENTRY-FLIP ORACLE {orc:+.2f} $/hr")
    print(f"    {'pctl':>5} {'nflip':>5} {'trueBL':>6} {'winFlip':>7} {'$/hr':>8} {'vsbase':>8}")
    for pctl in (95, 90, 85, 80, 70):
        thr = np.nanpercentile(score[ok], pctl)
        fl = ok & (score >= thr)
        d = float(np.sum(CAP * np.where(fl, -gross - FC, gross) / 1e4)) / hrs
        print(f"    {pctl:>5} {int(fl.sum()):>5} {int((fl & bigloss).sum()):>6} "
              f"{int((fl & winner).sum()):>7} {d:>+8.2f} {d - base:>+8.2f}")


if __name__ == "__main__":
    main()
