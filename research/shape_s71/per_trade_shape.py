"""S74 PER-TRADE SHAPE SEPARATION — reuse the LIVE decision path (run_kraken_cell) exactly as
sol_ascent_eq.extract() does; add richer scale-free shape features per leg; then measure, PER CELL
(coin x short/long) whether the WINNER vs LOSER per-trade distributions SEPARATE (not just differ in mean).

NO executor/fill/fee reimplementation — run_kraken_cell owns the trades. We only read each leg's pre-onset
imbalance arc (the same signed normalized [-1,1] object) and compute shape descriptors.

Reports, per coin x {short,long}: winner vs loser distribution of each feature, and the CLEAN-LOSER
operating point (threshold where losers concentrate and few winners land) = the fine-tuning target.
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from arc_gate import (load_raw, rolling_imb, build_channels, median_spread_bps,
                      run_kraken_cell, KRAKEN, PRE, CPS)
SMOOTH_SEC = 20
COINS = ["btc", "eth", "sol", "xrp"]

def features(pre):
    """Scale-free shape descriptors of one leg's pre-onset limb (t=-45..0). pre already signed to side."""
    t = (np.arange(len(pre)) - PRE) * 0.1
    peak = float(pre[-1]); start = float(pre[0]); mn = float(pre.min())
    below0 = float((pre < 0).mean())
    # dip persistence in the ASCENT region (last 25s) — the long-loser tell
    asc = pre[-25*CPS:]
    below_asc = float((asc < 0).mean()); min_asc = float(asc.min())
    # chord (start->peak straight line) convexity: + => curve sits BELOW chord => convex/hockey (late ignition)
    chord = start + (peak - start) * (t - t[0])/(t[-1]-t[0] + 1e-12)
    bow = pre - chord
    convexity = float(-bow.mean())
    # normalized shape [0,1] over own range — LEVEL-INVARIANT convexity (removes the energy/peak scale)
    rng = pre.max() - pre.min() + 1e-9
    prn = (pre - pre.min())/rng
    chordn = prn[0] + (prn[-1]-prn[0])*(t - t[0])/(t[-1]-t[0]+1e-12)
    convexity_n = float(-(prn - chordn).mean())          # scale-free hockey-ness
    # hockey break scan on normalized shape
    best = (-1e9, 0.0, 0.0, 0.0)
    for k in range(8, len(t)-8):
        bh = np.polyfit(t[:k+1], prn[:k+1], 1)[0]
        bl = np.polyfit(t[k+1:], prn[k+1:], 1)[0]
        yh = np.concatenate([prn[:k+1].mean()+bh*(t[:k+1]-t[:k+1].mean()),
                             prn[k+1:].mean()+bl*(t[k+1:]-t[k+1:].mean())])
        rr = 1.0 - ((prn-yh)**2).sum()/(((prn-prn.mean())**2).sum()+1e-12)
        if rr > best[0]:
            best = (rr, float(t[k]), float(bh), float(bl))
    hk_r2, t_break, b_handle, b_blade = best
    # linear-fit R2 on normalized shape (the linearity test done PROPERLY, on the shape not the blade)
    bn, an = np.polyfit(t, prn, 1)
    lin_r2 = 1.0 - ((prn-(an+bn*t))**2).sum()/(((prn-prn.mean())**2).sum()+1e-12)
    # quad curvature on raw
    c2 = float(np.polyfit(t, pre, 2)[0])
    imin = int(np.argmin(pre)); ipk = int(np.argmax(pre))
    climb = float((pre[ipk]-pre[imin])/((ipk-imin)*0.1)) if ipk > imin else 0.0
    return dict(peak=peak, start=start, mn=mn, below0=below0, below_asc=below_asc, min_asc=min_asc,
                convexity=convexity, convexity_n=convexity_n, lin_r2=lin_r2, hk_r2=hk_r2,
                t_break=t_break, b_handle=b_handle, b_blade=b_blade, c2=c2, climb=climb)

def extract_full(coin):
    path = f"/tmp/kbook/{coin}_book.jsonl"; cfg = [c for c in KRAKEN if c.coin == coin][0]
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw)/2.0; N = len(mid); hours = N*0.1/3600.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)     # LIVE decision path
    imb = rolling_imb(buy, sell, SMOOTH_SEC)
    rows, net, dur = [], [], []
    for l in res.legs:
        o = int(l.open_idx); c = int(l.close_idx)
        if o - PRE < 0 or c <= o:
            continue
        pre = imb[o-PRE:o+1] * int(l.side)
        rows.append(features(pre)); net.append(float(l.net_bps)); dur.append((c-o)*0.1)
    return rows, np.array(net), np.array(dur), hours

def clean_zone(f_win, f_los, direction):
    """Scan a threshold on feature f; direction=+1 means 'loser tail is HIGH f' (skip f>=thr),
    -1 means loser tail is LOW f (skip f<=thr). Return best operating point maximizing
    losers_caught while winners_dragged stays low (purity-weighted). Report the frontier."""
    vals = np.concatenate([f_win, f_los])
    qs = np.quantile(vals, np.linspace(0.02, 0.98, 49))
    best = None
    for thr in qs:
        if direction > 0:
            los_c = (f_los >= thr).mean(); win_d = (f_win >= thr).mean()
        else:
            los_c = (f_los <= thr).mean(); win_d = (f_win <= thr).mean()
        n_skip = los_c*len(f_los) + win_d*len(f_win)
        purity = (los_c*len(f_los))/(n_skip+1e-9)          # fraction of skipped that are losers
        score = los_c - 1.6*win_d                          # reward loser-catch, penalize winner-drag
        if best is None or score > best["score"]:
            best = dict(thr=float(thr), los_caught=float(los_c), win_dragged=float(win_d),
                        purity=float(purity), score=float(score))
    return best

FEATS = ["peak","convexity","convexity_n","below0","below_asc","min_asc","lin_r2","hk_r2",
         "t_break","b_blade","c2","climb"]
# direction hypotheses: which tail the LOSER lives in, per category (refined by data)
def analyze(coin, rows, net, dur):
    F = {k: np.array([r[k] for r in rows]) for k in FEATS}
    win = net > 0; med = np.median(dur); short = dur < med
    print(f"\n===== {coin.upper()}  (n={len(rows)}, base win%={win.mean()*100:.1f}, med dur={med:.0f}s) =====")
    for cat, cmask in [("SHORT", short), ("LONG", ~short)]:
        w = cmask & win; l = cmask & ~win
        if w.sum() < 10 or l.sum() < 10:
            print(f"  {cat}: too few"); continue
        print(f"  --- {cat}  (win n={w.sum()}, lose n={l.sum()}, cat win%={w.sum()/(w.sum()+l.sum())*100:.1f}) ---")
        print(f"    {'feat':11}{'WIN mean':>10}{'LOSE mean':>11}{'gap':>9}   clean-loser operating pt")
        for k in FEATS:
            fw, fl = F[k][w], F[k][l]
            gap = fl.mean() - fw.mean()
            direction = 1 if gap > 0 else -1     # loser sits on the higher(+)/lower(-) side
            cz = clean_zone(fw, fl, direction)
            arrow = ">=" if direction > 0 else "<="
            print(f"    {k:11}{fw.mean():>10.4f}{fl.mean():>11.4f}{gap:>+9.4f}   skip {arrow}{cz['thr']:+.4f}"
                  f"  losers_caught={cz['los_caught']*100:4.0f}%  winners_dragged={cz['win_dragged']*100:4.0f}%"
                  f"  purity={cz['purity']*100:3.0f}%")
    return F, win, short

if __name__ == "__main__":
    coins = sys.argv[1:] or COINS
    ALL = {}
    for coin in coins:
        print(f"\n... loading+running {coin} (live executor) ...", flush=True)
        rows, net, dur, hours = extract_full(coin)
        ALL[coin] = analyze(coin, rows, net, dur)
        # cache raw features for the gate script
        np.savez(f"/tmp/kbook/{coin}_feats.npz",
                 **{k: np.array([r[k] for r in rows]) for k in FEATS}, net=net, dur=dur)
    print("\nDONE", flush=True)
