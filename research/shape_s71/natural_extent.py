"""S74 NATURAL-EXTENT ASCENSION — Greg's refinement: don't clip the ignition limb at a fixed 45s. Detect each
leg's BIRTH (ignition = bottom of the hole before the final rise into onset), measure the per-cell TIME-EXTENT
(short vs long signals live over different spans — a per-cell NUMBER), and fit the ascension SHAPE over
NORMALIZED time [0,1] (scale-free, comparable across legs of different length). Then re-test winner/loser
separation on the normalized shape. Reuses the LIVE decision path (run_kraken_cell); the executor owns trades.

Look-back extended to 90s so long-leg births aren't clipped; we also record how often ignition hits the
90s edge (would need even more look-back). Amplitude is the native normalized-imbalance arc [-1,1]; time is
renormalized per leg. Everything strictly pre-onset (leakage-free)."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from arc_gate import (load_raw, rolling_imb, build_channels, median_spread_bps,
                      run_kraken_cell, KRAKEN, CPS)
SMOOTH_SEC = 20
LOOKBACK = 150 * CPS         # 150s max look-back for the birth (was 45s clip — measure what it hid)
NRS = 100                    # resample points over normalized ascension time
COINS = ["btc", "eth", "sol", "xrp"]

def last_upcross(seg):
    """Last time before onset the signed arc crossed UP through zero (trade-direction flow took over)."""
    neg = seg < 0
    cr = np.where((~neg[1:]) & (neg[:-1]))[0] + 1     # i where seg[i-1]<0<=seg[i]
    return int(cr[-1]) if len(cr) else 0

def ignition_idx(seg):
    """seg = signed arc from -LOOKBACK..0 (onset last). Birth = start of the FINAL rise into onset:
    scan back from onset; the ignition is where the running-min (going back) stops decreasing, i.e. the
    deepest point of the final hole. Robust = argmin of seg restricted to the final monotone-down-going-back
    region. We use the global argmin over the window but clamp to the LAST such min if arc re-dips."""
    # running min from the end backwards; ignition = earliest index whose value == min of seg[i:]
    m = np.minimum.accumulate(seg[::-1])[::-1]     # m[i] = min(seg[i:])
    # the final descent bottom = last index where seg equals the suffix-min AND is a local trough
    cand = np.where(seg <= m + 1e-9)[0]
    ig = cand[0] if len(cand) else 0               # earliest point from which onset is the running max
    # tighten: take the deepest point at/after ig (bottom of the final hole)
    ig = ig + int(np.argmin(seg[ig:]))
    return ig

def norm_shape(limb):
    """limb = signed arc ignition..onset. Return scale-free normalized-time, min-max amplitude shape (NRS pts)
    and its shape descriptors."""
    L = len(limb)
    xs = np.linspace(0, 1, NRS)
    y = np.interp(xs, np.linspace(0, 1, L), limb)     # normalized-time resample
    amp = y.max() - y.min() + 1e-9
    yn = (y - y.min())/amp                              # [0,1] amplitude
    # chord convexity (scale-free hockey-ness): + => below chord => convex/late-blade
    chord = yn[0] + (yn[-1]-yn[0])*xs
    conv_n = float(-(yn - chord).mean())
    area_n = float(yn.mean())                           # 0.5 linear; <0.5 convex/late; >0.5 concave/early
    # normalized-time of steepest slope (where accel peaks): ~1 late blade, ~0.5 linear
    dsl = np.gradient(yn, xs); t_infl = float(xs[int(np.argmax(dsl))])
    # rise concentrated in last third?
    rise_last3 = float((yn[-1] - yn[int(NRS*2/3)]))     # of total 1.0
    # amplitude fingerprint at 25/50/75% of the way in
    q25, q50, q75 = float(yn[NRS//4]), float(yn[NRS//2]), float(yn[3*NRS//4])
    return yn, dict(conv_n=conv_n, area_n=area_n, t_infl=t_infl, rise_last3=rise_last3,
                    q25=q25, q50=q50, q75=q75)

def extract(coin):
    path = f"/tmp/kbook/{coin}_book.jsonl"; cfg = [c for c in KRAKEN if c.coin == coin][0]
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw)/2.0; N = len(mid); hours = N*0.1/3600.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)
    imb = rolling_imb(buy, sell, SMOOTH_SEC)
    rows, rows45, net, dur, shapes, extents, edgehit = [], [], [], [], [], [], []
    ext_cross = []
    legs = sorted(res.legs, key=lambda z: int(z.open_idx))
    prev_close = -1
    for l in legs:
        o = int(l.open_idx); c = int(l.close_idx); s = int(l.side)
        if c <= o:
            continue
        lo = max(0, o - LOOKBACK, prev_close + 1)        # bound by prior leg's close / book start
        prev_close = c
        seg = imb[lo:o+1] * s
        if len(seg) < 30:
            continue
        ig = ignition_idx(seg)
        limb = seg[ig:]                                 # ignition..onset (natural extent)
        if len(limb) < 12:
            limb = seg[-12:]; ig = len(seg)-12
        yn, feat = norm_shape(limb)
        ext_sec = (len(limb)-1)*0.1
        feat["extent"] = ext_sec
        feat["peak"] = float(seg[-1])                   # energy at onset
        feat["below0"] = float((limb < 0).mean())
        feat["dip"] = float(limb.min())
        # 45s-truncated variant of the SAME shape descriptors (for head-clip comparison)
        limb45 = seg[-min(45*CPS, len(seg)):]
        _, feat45 = norm_shape(limb45)
        feat45["extent"] = (len(limb45)-1)*0.1; feat45["peak"] = float(seg[-1])
        feat45["below0"] = float((limb45 < 0).mean()); feat45["dip"] = float(limb45.min())
        # last up-crossing extent (alt birth definition)
        uc = last_upcross(seg); ext_cross.append((len(seg)-1-uc)*0.1)
        rows.append(feat); rows45.append(feat45); net.append(float(l.net_bps)); dur.append((c-o)*0.1)
        shapes.append(yn); extents.append(ext_sec)
        # bound-clip = ignition landed at the window start (birth may be earlier, truncated by lookback/prev-close)
        edgehit.append(1 if (lo > 0 and ig == 0) else 0)
    return (rows, rows45, np.array(net), np.array(dur), np.array(shapes), np.array(extents),
            np.array(ext_cross), np.array(edgehit), hours)

FEATS = ["extent","conv_n","area_n","t_infl","rise_last3","q25","q50","q75","below0","dip","peak"]

def sep_table(F, win, short, tag):
    print(f"    --- {tag} separation (win% in loser-tail 10/20/30%; base=cat win%) ---")
    for cat, cmask in [("SHORT", short), ("LONG", ~short)]:
        w = cmask&win; l = cmask&~win; cw = w.sum()/(w.sum()+l.sum()+1e-9)
        print(f"      [{cat}] cat-win%={cw*100:.1f}")
        for k in FEATS:
            fw, fl = F[k][w], F[k][l]; gap = fl.mean()-fw.mean(); dr = 1 if gap>0 else -1
            fc = F[k][cmask]; yc = win[cmask]
            order = np.argsort(-fc if dr>0 else fc)
            wr = [yc[order[:max(1,int(fr*len(fc)))]].mean()*100 for fr in (0.10,0.20,0.30)]
            flag = "  <== SEP" if wr[0] < cw*100-12 else ""
            print(f"        {k:11}{gap:>+8.3f}  {wr[0]:5.1f} {wr[1]:5.1f} {wr[2]:5.1f}{flag}")

def report(coin, rows, rows45, net, dur, extents, ext_cross, edgehit):
    F = {k: np.array([r[k] for r in rows]) for k in FEATS}
    F45 = {k: np.array([r[k] for r in rows45]) for k in FEATS}
    win = net > 0; med = np.median(dur); short = dur < med; base = win.mean()
    print(f"\n===== {coin.upper()} n={len(rows)} base win%={base*100:.1f} med-dur={med:.0f}s "
          f"birth-bound-clip={edgehit.mean()*100:.1f}% =====")
    cats = [("SHORT-WIN", win&short), ("SHORT-LOSE", ~win&short),
            ("LONG-WIN", win&~short), ("LONG-LOSE", ~win&~short)]
    print(f"  {'cell':12}{'n':>5}" + "".join(f"{k:>9}" for k in FEATS))
    for nm, m in cats:
        if m.sum() < 5: continue
        print(f"  {nm:12}{m.sum():>5}" + "".join(f"{F[k][m].mean():>9.3f}" for k in FEATS))
    # per-cell EXTENT (the time-signature NUMBER) + HEAD-CLIP: fraction born before -45s
    print("  --- ascension TIME-EXTENT (s): argmin-birth [p25 med p75], last-upcross med, frac born <-45s ---")
    for nm, m in cats:
        if m.sum() < 5: continue
        q = np.percentile(F["extent"][m], [25,50,75]); qc = np.median(ext_cross[m])
        f45 = float((F["extent"][m] > 45).mean())*100
        print(f"    {nm:12} argmin[{q[0]:5.1f} {q[1]:5.1f} {q[2]:5.1f}]  upcross-med={qc:5.1f}  born<-45s={f45:4.0f}%")
    # separation: NATURAL vs 45s-TRUNCATED (does capturing the full head help?)
    sep_table(F, win, short, "NATURAL-extent shape")
    sep_table(F45, win, short, "45s-TRUNCATED shape")

if __name__ == "__main__":
    coins = sys.argv[1:] or COINS
    for coin in coins:
        print(f"\n... loading+running {coin} (live executor) ...", flush=True)
        rows, rows45, net, dur, shapes, extents, ext_cross, edgehit, hours = extract(coin)
        report(coin, rows, rows45, net, dur, extents, ext_cross, edgehit)
        np.savez(f"/tmp/kbook/{coin}_nat.npz",
                 **{k: np.array([r[k] for r in rows]) for k in FEATS},
                 net=net, dur=dur, extents=extents, ext_cross=ext_cross, hours=hours, shapes=shapes)
    print("\nDONE", flush=True)
