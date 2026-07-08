"""Richer (arm_hi x window x exit_lo) grid for the balance exit, load once. Fairness check for SOL
before the verdict: is there ANY config that beats baseline $/hr?"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from arc_gate import load_raw, rolling_imb, build_channels, median_spread_bps, CPS
from odcore.platform import run_kraken_cell, KRAKEN
from odcore.flip_detector import lean_series

CAP = 5000.0
coin = sys.argv[1] if len(sys.argv) > 1 else "sol"
path = f"/tmp/kbook/{coin}_book.jsonl"
cfg = [c for c in KRAKEN if c.coin == coin][0]
raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
hs = median_spread_bps(path, raw=raw) / 2.0; N = len(mid); hours = N * 0.1 / 3600.0
dph = CAP / 1e4 / hours

base, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)
bnet = np.array([l.net_bps for l in base.legs])
print(f"{coin}: legs={len(base.legs)} {hours:.1f}h  BASELINE $/hr={bnet.sum()*dph:+.2f} win%={100*(bnet>0).mean():.1f}", flush=True)
print(f"  {'arm':>5}{'win':>5}{'exit_lo':>8}{'$/hr':>9}{'dVS':>8}{'win%':>6}{'nBal':>6}{'win$/hr':>9}{'los$/hr':>9}", flush=True)
for arm in (0.20, 0.30, 0.40):
    for W in (200, 400, 600):
        for thr in (0.05, -0.05, -0.15):
            res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs, balance_exit=(arm, thr), bal_lean_w=W)
            net = np.array([l.net_bps for l in res.legs])
            nbal = sum(1 for l in res.legs if getattr(l, "bal_exit", False))
            win = net > 0; los = net < 0
            print(f"  {arm:>5.2f}{W//CPS:>5}{thr:>+8.2f}{net.sum()*dph:>+9.2f}{(net.sum()-bnet.sum())*dph:>+8.2f}"
                  f"{100*win.mean():>6.1f}{nbal:>6}{net[win].sum()*dph:>+9.2f}{net[los].sum()*dph:>+9.2f}", flush=True)
print("DONE", flush=True)
