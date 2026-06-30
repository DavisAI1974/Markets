"""_flip_debug.py — instrument the flip filter to find what's wrong with it (S45, Greg: "it's how we code it").

The flip ("both") arm made the maker WORSE, not better, even though the gated cells keep a high next-cell
direction hit. That contradicts S36 (opposing+exhausting = 64% reversal), so something in HOW we select /
sign the flip cells is off. This dissects, on the held-out test slice's GATED cells, each candidate flip
condition and reports for each: count, next-cell direction hit (sign imb vs next move), the FILL adverse
drift (d_wait, post->fill) and post-fill move (d_hold), and the maker gross. That isolates whether the
filter (a) inverts direction, (b) selects worse-fill cells, or (c) just needs the exhaustion factor.

Conditions:
  all_gated      : the floor gate is open (current deploy)
  confirming     : gate AND book CONFIRMS the recent move (aligned = imb*sign(price_drift) > 0)
  opposing       : gate AND book OPPOSES the recent move (aligned < 0)            [what _maker_flip_floor used]
  opp_exhaust    : opposing AND the book lean is COLLAPSING (|late imb| < |early imb|)  [S36 full reversal]
  opp_strong     : opposing AND |aligned| >= 0.20 (strong divergence)

Run:  python _flip_debug.py [coin] [K] [pdwin]
"""
from __future__ import annotations

import sys
import numpy as np

from _liquidity_dive import build_channels, median_spread_bps, fwd_cum_return
from odcore import quiet_floor
from odcore.maker_book import simulate_arm, _first_fill_index

KGATE, FLOW_W, TRAIN_FRAC, FILL_WINDOW, HOLD, QUEUE_FRAC = 1.5, 20, 0.6, 10, 1, 1.0


def main():
    coin = sys.argv[1] if len(sys.argv) > 1 else "sol"
    K = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    pdwin = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"

    ch, g = build_channels(path, K, FLOW_W)
    imb = ch["depth_imb"]; mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    n = len(mid); cut = int(n * TRAIN_FRAC); hs = median_spread_bps(path) / 2.0
    quiet = (buy + sell) <= 0.0
    qf = quiet_floor.fit(imb, quiet, train_frac=TRAIN_FRAC)
    gate = qf.gate(imb, KGATE)
    sgn = np.sign(imb)

    # trailing price drift + the divergence pieces, all causal (past only)
    lm = np.log(np.where(mid > 0, mid, np.nan))
    pd = np.zeros(n); pd[pdwin:] = np.nan_to_num(lm[pdwin:] - lm[:-pdwin])
    aligned = imb * np.sign(pd)
    # exhaustion: |imb over the recent half| < |imb over the prior half| of the trailing pdwin window
    half = pdwin // 2
    rollmean = lambda w: np.convolve(imb, np.ones(w) / w, mode="full")[:n]   # causal running mean
    recent = np.zeros(n); prior = np.zeros(n)
    for t in range(pdwin, n):
        recent[t] = np.mean(imb[t - half:t]); prior[t] = np.mean(imb[t - pdwin:t - half])
    exhausting = np.abs(recent) < np.abs(prior)

    sret = np.nan_to_num(np.concatenate([[0.0], np.diff(lm)]))
    fwd1 = fwd_cum_return(sret, 1)

    # fill decomposition over the WHOLE series (we'll mask per condition), side = sgn
    side = np.where(gate, sgn, 0.0)
    qa = np.where(side > 0, bb, ba) * QUEUE_FRAC
    fa = np.where(side > 0, _first_fill_index(qa, sell, FILL_WINDOW),
                  np.where(side < 0, _first_fill_index(qa, buy, FILL_WINDOW), -1))
    ei = np.clip(fa + HOLD, 0, n - 1)
    hs_price = (hs / 1e4) * mid
    entry = np.where(side > 0, mid - hs_price, mid + hs_price)
    filled = (side != 0) & (fa >= 0) & ((fa + HOLD) <= (n - 1))
    d_wait = np.where(filled, sgn * (mid[fa] - mid) / np.where(mid > 0, mid, 1) * 1e4, np.nan)
    d_hold = np.where(filled, sgn * (mid[ei] - mid[fa]) / np.where(mid > 0, mid, 1) * 1e4, np.nan)
    gross = np.where(filled, sgn * (mid[ei] - entry) / np.where(mid > 0, mid, 1) * 1e4, np.nan)

    te = np.zeros(n, bool); te[cut:] = True
    def hit(mask):
        m = mask & te & (sgn != 0)
        m = m[:n - 1]
        a = sgn[:n - 1][m]; b = fwd1[:n - 1][m]; ok = ~np.isnan(b) & (b != 0)
        return float((np.sign(a) == np.sign(b))[ok].mean()) if ok.any() else float("nan")
    def stat(name, cond):
        mask = gate & cond & te
        fm = mask & filled
        nf = int(fm.sum())
        print(f"{name:<14}{int(mask.sum()):>8}{nf:>8}{100*hit(mask):>8.1f}%"
              f"{np.nanmean(np.where(fm, d_wait, np.nan)):>10.3f}{np.nanmean(np.where(fm, d_hold, np.nan)):>9.3f}"
              f"{np.nanmean(np.where(fm, gross, np.nan)):>9.3f}")

    print(f"\n# FLIP DEBUG {coin}_coinbase K={K} pdwin={pdwin}  (test slice; side=sign(depth_imb); "
          f"half_sp={hs:.4f} bps)")
    print(f"{'condition':<14}{'n_gated':>8}{'n_fill':>8}{'nextHit':>9}{'d_wait':>10}{'d_hold':>9}{'gross':>9}")
    stat("all_gated", np.ones(n, bool))
    stat("confirming", aligned > 0)
    stat("opposing", aligned < 0)
    stat("opp_exhaust", (aligned < 0) & exhausting)
    stat("opp_strong", aligned <= -0.20)
    stat("confirm_exhst", (aligned > 0) & exhausting)
    print("\n# read: if 'opposing' has GOOD nextHit but BAD d_wait -> it selects mid-flush fills (concept),")
    print("#       if 'opposing' nextHit < confirming -> the sign/channel is inverted (coding).")


if __name__ == "__main__":
    main()
