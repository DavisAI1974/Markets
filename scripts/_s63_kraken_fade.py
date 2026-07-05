"""_s63_kraken_fade.py — S63 Kraken pivot: the fade-the-trend SIDE rule on KRAKEN's own prices.

Greg's call: park Coinbase, go to Kraken (kr_mk0 = 0bp maker is where the money is — the machine's
gross IS its net there; net-negative at Coinbase taker). This runs the SAME direction test as
`_s63_fade.py` but on KRAKEN'S OWN TAPE (venue law: Kraken prices differ from Binance):
  - BTC / ETH: realbins/*_kraken_bins.json (durable collector, ~26.7d ~June window -> an
    independent cross-venue AND cross-window check vs the Binance last-30d fade result).
  - SOL / DOGE / XRP: /tmp/kraken_backfill/<PAIR>_30d_bins.json (backfill_kraken_trades.py, pulling).
Missing coins are skipped (run again as the REST tape lands).

Side rule: pred_side = -sign(mom over W) (fade the N-hour trend). At kr_mk0 the fee cancels in the
machine-vs-fade comparison (same legs, only the side differs) AND net==gross, so direct $/hr @ $5k
IS the deployable net. Baseline = the machine's own side. per-week + sign-shuffle null.

Coverage honesty: Kraken tape is thin (~16% of seconds have a bin; mid forward-filled). Flagged.

Usage:  python scripts/_s63_kraken_fade.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.entry_coinbase import armed_midband_flips                  # noqa: E402

CAP = 5000.0; WK = 7 * 24 * 3600
REALBINS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "realbins")
KTAPE = "/tmp/kraken_backfill"
# coin -> (bins path, registry theta)  [eth has no registry theta on Kraken -> try 100]
CELLS = [
    ("btc", f"{REALBINS}/btc_kraken_bins.json", 80.0),
    ("eth", f"{REALBINS}/eth_kraken_bins.json", 100.0),
    ("sol", f"{KTAPE}/SOLUSD_30d_bins.json", 100.0),
    ("doge", f"{KTAPE}/XDGUSD_30d_bins.json", 100.0),
    ("xrp", f"{KTAPE}/XRPUSD_30d_bins.json", 80.0),
]
FADE_W = [3600, 7200, 10800, 14400, 21600, 28800]     # 1h 2h 3h 4h 6h 8h
MAXW = 28800
N_SHUF = 500
SEED = 7


def build(path, th):
    mid, buy, sell, cover, hrs = load_bins(path)
    mid = np.asarray(mid, float); lm = np.log(mid); n = len(mid)
    fl = armed_midband_flips(mid, th, 0.5)
    ci_l, d_l, side_l = [], [], []
    for k in range(len(fl) - 1):
        ci, _p, side = fl[k]; xi = fl[k + 1][0]; ci = int(ci); xi = int(xi); side = int(side)
        if xi <= ci or ci < MAXW or ci < 1802 or xi >= n:
            continue
        ci_l.append(ci); d_l.append((lm[xi] - lm[ci]) * 1e4); side_l.append(side)
    return lm, np.array(ci_l), np.array(d_l), np.array(side_l), cover, hrs


def main():
    rng = np.random.default_rng(SEED)
    print("=== S63 KRAKEN pivot: fade-the-trend SIDE rule on Kraken's own prices (kr_mk0, net==gross) ===")
    for coin, path, th in CELLS:
        if not os.path.exists(path):
            print(f"\n[{coin}] bins not present yet: {path}"); continue
        lm, ci, d, mside, cover, hrs = build(path, th)
        if len(d) < 50:
            print(f"\n[{coin}] too few legs ({len(d)}) on {os.path.basename(path)}"); continue
        fwd = np.sign(d); n = len(d)
        span_d = (ci[-1] - ci[0]) / 86400.0 if n else 0.0
        H = max((ci[-1] - ci[0]) / 3600.0, 1.0)     # window hours for $/hr (not fixed 720)
        base = np.sum(CAP * (mside * d) / 1e4) / H
        macc = np.mean(mside == fwd)
        print(f"\n[{coin}]  {os.path.basename(path)}  n={n}  span={span_d:.1f}d  cover={cover*100:.0f}%  "
              f"machine base={base:+.2f} $/hr  machine dir-acc={macc:.3f}")
        print(f"   {'fadeW':>6}{'acc':>6}{'net$/hr':>9}{'Δbase':>7}{'z_null':>8}{'p':>7}{'wk+':>5}"
              f"   per-week Δ")
        week = (ci // WK).astype(int)
        for W in FADE_W:
            mom = np.array([(lm[i] - lm[i - W]) * 1e4 for i in ci])
            pside = -np.sign(mom); pside[pside == 0] = 1
            pnl = pside * d
            tot = np.sum(CAP * pnl / 1e4) / H
            acc = np.mean(pside == fwd)
            pw = []
            for w in sorted(set(week)):
                mk = week == w
                if mk.sum() < 2:
                    continue
                hh = (np.ptp(ci[mk]) + 1) / 3600.0
                pw.append((np.sum(CAP * pnl[mk] / 1e4) - np.sum(CAP * (mside[mk] * d[mk]) / 1e4)) / hh)
            wk_pos = sum(1 for v in pw if v > 0)
            null = np.empty(N_SHUF)
            for j in range(N_SHUF):
                rs = rng.choice((-1, 1), size=n)
                null[j] = np.sum(CAP * (rs * d) / 1e4) / H
            mu = null.mean(); sd = null.std() + 1e-12
            z = (tot - mu) / sd; p = (np.sum(null >= tot) + 1) / (N_SHUF + 1)
            print(f"   {W//3600:>4}h{acc:>6.3f}{tot:>+9.2f}{tot-base:>+7.2f}{z:>+8.2f}{p:>7.3f}"
                  f"{wk_pos:>3}/{len(pw)}   " + " ".join(f"{v:+.1f}" for v in pw))


if __name__ == "__main__":
    main()
