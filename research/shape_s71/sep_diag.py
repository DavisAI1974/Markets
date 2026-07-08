"""S74 SEPARATION DIAGNOSTIC — the decisive test of Greg's intuition: does ANY pre-onset shape/equation
feature give per-trade WINNER vs LOSER distributions that DON'T overlap (so it can replace energy)?

Reuses the LIVE decision path (run_kraken_cell). Adds:
  - cumulative / integrated arc features (Greg: try the integrated form),
  - ignition-timing features (last zero-crossing = when the arc leaves the hole),
  - a TAIL-DECILE separation report: skip the k% most loser-like by a feature, print the win-rate in the
    skipped set. If win-rate stays ~base -> NO separation. If it drops far below base -> a usable skip zone.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from arc_gate import (load_raw, rolling_imb, build_channels, median_spread_bps,
                      run_kraken_cell, KRAKEN, PRE, CPS)
SMOOTH_SEC = 20
COINS = ["btc", "eth", "sol", "xrp"]

def features(pre):
    t = (np.arange(len(pre)) - PRE) * 0.1
    peak = float(pre[-1]); start = float(pre[0]); mn = float(pre.min())
    below0 = float((pre < 0).mean())
    # ---- cumulative / integrated (Greg) ----
    cs = np.cumsum(pre) * 0.1                     # integrated flow (units: arc*sec)
    cum_final = float(cs[-1])                     # net area under the whole limb
    area_pos = float(pre[pre > 0].sum()*0.1); area_neg = float(pre[pre < 0].sum()*0.1)
    net_area_ratio = float((area_pos + area_neg)/(abs(area_pos)+abs(area_neg)+1e-9))  # -1..1
    # time-weighted integral (emphasize the late/ignition part): weight rises 0->1 toward onset
    w = np.linspace(0, 1, len(pre)); late_integral = float((pre*w).sum()*0.1)
    # ---- ignition timing: last time the arc is below zero (leaves the hole) ----
    neg = np.where(pre < 0)[0]
    t_last_neg = float((neg[-1]-PRE)*0.1) if len(neg) else -45.0   # near 0 = ignites LATE (loser tell)
    frac_late_neg = float((pre[-15*CPS:] < 0).mean())             # below-zero in last 15s
    # ---- shape ----
    chord = start + (peak-start)*(t - t[0])/(t[-1]-t[0]+1e-12)
    convexity = float(-(pre-chord).mean())
    asc = pre[-25*CPS:]; below_asc = float((asc < 0).mean()); min_asc = float(asc.min())
    b_blade = float(np.polyfit(t[-15*CPS:], pre[-15*CPS:], 1)[0])
    imin = int(np.argmin(pre)); ipk = int(np.argmax(pre))
    climb = float((pre[ipk]-pre[imin])/((ipk-imin)*0.1)) if ipk > imin else 0.0
    return dict(peak=peak, start=start, mn=mn, below0=below0, below_asc=below_asc, min_asc=min_asc,
                cum_final=cum_final, late_integral=late_integral, net_area_ratio=net_area_ratio,
                t_last_neg=t_last_neg, frac_late_neg=frac_late_neg, convexity=convexity,
                b_blade=b_blade, climb=climb, area_neg=area_neg)

FEATS = ["peak","cum_final","late_integral","net_area_ratio","t_last_neg","frac_late_neg","below0",
         "below_asc","min_asc","convexity","b_blade","climb","area_neg","start"]

def extract_full(coin):
    path = f"/tmp/kbook/{coin}_book.jsonl"; cfg = [c for c in KRAKEN if c.coin == coin][0]
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw)/2.0; N = len(mid); hours = N*0.1/3600.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)
    imb = rolling_imb(buy, sell, SMOOTH_SEC)
    rows, net, dur = [], [], []
    for l in res.legs:
        o = int(l.open_idx); c = int(l.close_idx)
        if o - PRE < 0 or c <= o:
            continue
        pre = imb[o-PRE:o+1] * int(l.side)
        rows.append(features(pre)); net.append(float(l.net_bps)); dur.append((c-o)*0.1)
    return rows, np.array(net), np.array(dur), hours

def tail_report(coin, rows, net, dur):
    F = {k: np.array([r[k] for r in rows]) for k in FEATS}
    win = net > 0; med = np.median(dur); short = dur < med
    base = win.mean()
    print(f"\n===== {coin.upper()}  n={len(rows)} base win%={base*100:.1f} med={med:.0f}s =====")
    for cat, cmask in [("SHORT", short), ("LONG", ~short)]:
        w = cmask & win; l = cmask & ~win; c = cmask
        cw = w.sum()/(w.sum()+l.sum())
        print(f"  --- {cat}  cat-win%={cw*100:.1f}  (win {w.sum()}, lose {l.sum()}) ---")
        print(f"    {'feat':14}{'gap(L-W)':>9}  win%@skip[loser-tail 10/20/30%]   (base {cw*100:.0f}%)")
        for k in FEATS:
            fw, fl = F[k][w], F[k][l]; gap = fl.mean()-fw.mean()
            direction = 1 if gap > 0 else -1
            fc = F[k][c]; yc = win[c]
            order = np.argsort(-fc if direction > 0 else fc)   # most loser-like first
            wr = []
            for frac in (0.10, 0.20, 0.30):
                k_n = max(1, int(frac*len(fc)))
                wr.append(yc[order[:k_n]].mean()*100)
            flag = "  <== SEPARATES" if wr[0] < cw*100 - 12 else ""
            print(f"    {k:14}{gap:>+9.4f}   {wr[0]:5.1f} {wr[1]:5.1f} {wr[2]:5.1f}{flag}")
    return F, win, short, med

if __name__ == "__main__":
    coins = sys.argv[1:] or COINS
    for coin in coins:
        print(f"\n... loading+running {coin} (live executor) ...", flush=True)
        rows, net, dur, hours = extract_full(coin)
        tail_report(coin, rows, net, dur)
        np.savez(f"/tmp/kbook/{coin}_feats2.npz",
                 **{k: np.array([r[k] for r in rows]) for k in FEATS}, net=net, dur=dur, hours=hours)
    print("\nDONE", flush=True)
