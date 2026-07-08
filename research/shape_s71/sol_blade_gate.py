"""S75 SOL LOSER-BLADE gate + TWO BOOK PIECES (Greg's spec, S75).

Greg's read of the SOL pre-fire equations:
  short-lose  y=-0.883+2.372x (x<=0.15), blade +1.208   -.
  long-lose   y=-0.883+2.203x (x<=0.15), blade +1.268    |  BOTH LOSERS = same blade shape:
  short-win   y=-0.875+2.117x (x<=0.32), blade +0.963    |  STEEP rise, SHORT ramp (kink ~0.15), then FLAT.
  long-win    y=-0.834+2.197x-2.292x^2+1.543x^3 (cubic)  -'  Winners differ: short-win ramps LONGER (~0.32);
                                                             long-win is a smooth CUBIC that keeps rising.

=> "the loses have the same blade shape. that should be the FIRST pre-enter gate. if the blades look
    anywhere close to this, skip. but still keep both pieces." (Greg, S75)

FIRST GATE  = LOSER-BLADE match (duration-agnostic; both losers share it): steep-short-ramp blade -> SKIP.
SECOND      = the TWO BOOK PIECES kept separate (with-side depth, against-side depth; NOT the net ratio
              "sum" that can be close while the 2 pieces aren't). Greg: "do the book plus numbers, two
              different numbers."

Shape/RATIO only, no volume/price. LIVE path (run_kraken_cell). SOL only (Greg). doge excluded elsewhere.
Blade shape is measured on the BIRTH->ONSET normalized limb (ignition-anchored), matching the equations'
x in [0,1]. Grades vs UNGATED and vs the ENERGY-only gate. CAP=$5000/trade.
"""
import os, sys, types
# --- shim the unused matplotlib import in arc_gate (we don't plot here; avoids an install) ---
if "matplotlib" not in sys.modules:
    _m = types.ModuleType("matplotlib"); _m.use = lambda *a, **k: None
    _p = types.ModuleType("matplotlib.pyplot")
    for _fn in ("subplots", "plot", "savefig", "close", "figure", "tight_layout", "axvline", "axhline"):
        setattr(_p, _fn, lambda *a, **k: None)
    _m.pyplot = _p; sys.modules["matplotlib"] = _m; sys.modules["matplotlib.pyplot"] = _p
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from arc_gate import (load_raw, rolling_imb, build_channels, median_spread_bps,
                      run_kraken_cell, KRAKEN, PRE, CPS)
from whole_legs import ignition_idx, resample
SMOOTH_SEC = 20
LOOKBACK = 150 * CPS
BASE_SEC = 300
ONSET_SEC = 5
CAP = 5000.0
LEVELS = [1, 5, 10]


def causal_rollmean(x, w):
    c = np.concatenate([[0.0], np.cumsum(x)]); ix = np.arange(len(x)); lo = np.maximum(ix + 1 - w, 0)
    return (c[ix + 1] - c[lo]) / (ix + 1 - lo)


def book_pieces(g):
    wb = int(BASE_SEC * CPS); out = {}
    for K in LEVELS:
        bid = np.asarray(g["bidK"][K], float); ask = np.asarray(g["askK"][K], float)
        base = causal_rollmean(bid + ask, wb) + 1e-12
        out[K] = (bid / base, ask / base)
    return out


def blade_feats(p):
    """Blade-shape features on the birth->onset normalized limb p (signed to side, len NRS).
    Loser template = steep early rise + SHORT ramp (kink low) then flat. Winners = longer ramp / cubic."""
    x = np.linspace(0, 1, len(p)); start = float(p[0]); end = float(p[-1]); rise = end - start
    m15 = x <= 0.15
    blade15 = float(np.polyfit(x[m15], p[m15], 1)[0]) if m15.sum() >= 3 else 0.0   # steep-early slope
    # grid hockey: line on [0,k] + constant on (k,1]; kink where the rise plateaus
    best = (1e18, 0.3, 0.0)
    for k in np.linspace(0.10, 0.60, 26):
        a = x <= k
        if a.sum() < 3 or (~a).sum() < 3:
            continue
        A = np.polyfit(x[a], p[a], 1); r1 = np.polyval(A, x[a]); c = p[~a].mean()
        sse = float(((p[a] - r1) ** 2).sum() + ((p[~a] - c) ** 2).sum())
        if sse < best[0]:
            best = (sse, float(k), float(A[0]))
    kink, hblade = best[1], best[2]
    # front-loadedness: normalized-x where 85% of the rise is reached (loser -> SMALL)
    if rise > 1e-6:
        idx = np.where(p >= start + 0.85 * rise)[0]; treach = float(x[idx[0]]) if len(idx) else 1.0
    else:
        treach = 1.0
    chord = np.linspace(start, end, len(p)); convex = float(-(p - chord).mean())    # cubic-late -> +, front-load -> -
    return dict(blade15=blade15, kink=kink, hblade=hblade, treach=treach, convex=convex,
                peak=end, start=start, rise=rise)


def extract():
    coin = "sol"; path = f"/tmp/kbook/{coin}_book.jsonl"; cfg = [c for c in KRAKEN if c.coin == coin][0]
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0; N = len(mid); hours = N * 0.1 / 3600.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)
    imb = rolling_imb(buy, sell, SMOOTH_SEC); bp = book_pieces(g); ow = int(ONSET_SEC * CPS)
    legs = sorted(res.legs, key=lambda z: int(z.open_idx)); prev_close = -1
    rows, net, dur = [], [], []
    for l in legs:
        o = int(l.open_idx); c = int(l.close_idx); s = int(l.side)
        if c <= o:
            continue
        lo = max(0, o - LOOKBACK, prev_close + 1)
        seg = imb[lo:o + 1] * s
        if len(seg) < 30:
            prev_close = c; continue
        birth = lo + ignition_idx(seg); prev_close = c
        limb = imb[birth:o + 1] * s
        if len(limb) < 12:
            continue
        f = blade_feats(resample(limb))
        # climb (min->peak ascent rate over the fixed 45s window, matching sep_diag)
        if o - PRE >= 0:
            pw = imb[o - PRE:o + 1] * s; imn = int(np.argmin(pw)); ipk = int(np.argmax(pw))
            f["climb"] = float((pw[ipk] - pw[imn]) / ((ipk - imn) * 0.1)) if ipk > imn else 0.0
        else:
            f["climb"] = 0.0
        oa = max(0, o - ow)
        for K in LEVELS:
            bid_rel, ask_rel = bp[K]; bwr = bid_rel[oa:o + 1].mean(); awr = ask_rel[oa:o + 1].mean()
            wd = bwr if s > 0 else awr; ad = awr if s > 0 else bwr
            f[f"bwith{K}"] = float(wd); f[f"bagn{K}"] = float(ad)
            f[f"bnet{K}"] = float((wd - ad) / (wd + ad + 1e-12))
        rows.append(f); net.append(float(l.net_bps)); dur.append((c - o) * 0.1)
    return rows, np.array(net), np.array(dur), hours


TELLS = ["blade15", "kink", "hblade", "treach", "convex", "peak", "climb",
         "bwith5", "bagn5", "bnet5", "bwith1", "bagn1", "bwith10", "bagn10"]


def sep_report(rows, net, dur):
    F = {k: np.array([r.get(k, np.nan) for r in rows]) for k in TELLS}
    win = net > 0; med = np.median(dur); short = dur < med
    print(f"\n===== SOL  n={len(rows)}  base win%={win.mean()*100:.1f}  med={med:.0f}s =====", flush=True)
    for cat, cm in [("SHORT", short), ("LONG", ~short)]:
        w = cm & win; l = cm & ~win; cw = w.sum() / max(1, (w.sum() + l.sum()))
        print(f"  --- {cat}  cat-win%={cw*100:.1f}  (win {int(w.sum())}, lose {int(l.sum())}) ---", flush=True)
        print(f"    {'tell':9}{'W-mean':>9}{'L-mean':>9}{'gap(L-W)':>10}   win%@skip[10/20/30%] (base {cw*100:.0f})", flush=True)
        for k in TELLS:
            fw, fl = F[k][w], F[k][l]; gap = np.nanmean(fl) - np.nanmean(fw)
            d = 1 if gap > 0 else -1; fc = F[k][cm]; yc = win[cm]
            order = np.argsort(-fc if d > 0 else fc); wr = []
            for fr in (0.10, 0.20, 0.30):
                kn = max(1, int(fr * len(fc))); wr.append(yc[order[:kn]].mean() * 100)
            flag = "  <== SEPARATES" if wr[0] < cw * 100 - 12 else ""
            print(f"    {k:9}{np.nanmean(fw):>9.3f}{np.nanmean(fl):>9.3f}{gap:>+10.4f}   "
                  f"{wr[0]:5.1f} {wr[1]:5.1f} {wr[2]:5.1f}{flag}", flush=True)
    return F, win, short


def dph(net_sub, hours):
    return net_sub.sum() / 1e4 * CAP / hours


def report(name, fire, net, win, short, hours):
    m = dict(win=(net[fire] > 0).mean() * 100 if fire.sum() else float("nan"),
             dph=dph(net[fire], hours), fired=int(fire.sum()), n=len(net), pct=fire.mean() * 100,
             sl=int((~fire & short & ~win).sum()), slT=int((short & ~win).sum()),
             ll=int((~fire & ~short & ~win).sum()), llT=int((~short & ~win).sum()),
             ws=int((~fire & win).sum()), wT=int(win.sum()))
    print(f"  {name:22} win%={m['win']:.1f}  $/hr={m['dph']:.3f}  fired={m['fired']}/{m['n']} ({m['pct']:.0f}%)"
          f"  SL-skip={m['sl']}/{m['slT']} LL-skip={m['ll']}/{m['llT']} WIN-skip={m['ws']}/{m['wT']}", flush=True)
    return m


def zdist(F, keys, mask_ref, mask_other):
    """z-scored nearest-template: dist of every leg to ref-mean vs other-mean over `keys`."""
    Z = np.stack([(F[k] - np.nanmean(F[k])) / (np.nanstd(F[k]) + 1e-9) for k in keys], 1)
    ref = np.nanmean(Z[mask_ref], 0); oth = np.nanmean(Z[mask_other], 0)
    dref = np.linalg.norm(Z - ref, axis=1); doth = np.linalg.norm(Z - oth, axis=1)
    return dref, doth


CACHE = "/tmp/kbook/sol_blade_feats.npz"


def main():
    if os.path.exists(CACHE) and "--fresh" not in sys.argv:
        d = np.load(CACHE, allow_pickle=True)
        rows = list(d["rows"]); net = d["net"]; dur = d["dur"]; hours = float(d["hours"])
        print(f"(loaded cached feats: {len(rows)} legs)", flush=True)
    else:
        rows, net, dur, hours = extract()
        np.savez(CACHE, rows=np.array(rows, dtype=object), net=net, dur=dur, hours=hours)
    F, win, short = sep_report(rows, net, dur)
    lose = ~win
    print(f"\n  ---- GATES (through the live legs; CAP=${CAP:.0f}/trade, {hours:.1f}h) ----", flush=True)
    report("UNGATED", np.ones(len(net), bool), net, win, short, hours)

    # ENERGY-only (4-anchor nearest peak) — the reference
    peak = F["peak"]
    a = {c: float(peak[m].mean()) for c, m in
         (("sl", short & ~win), ("sw", short & win), ("ll", ~short & ~win), ("lw", ~short & win))}
    dlose = np.minimum(np.abs(peak - a["sl"]), np.abs(peak - a["ll"]))
    dwin = np.minimum(np.abs(peak - a["sw"]), np.abs(peak - a["lw"]))
    report("ENERGY-only", ~(dlose < dwin), net, win, short, hours)

    # ⭐ THE 2-NUMBER BOOK GATE (Greg): the TWO book pieces judged TOGETHER — one pass/fail from BOTH
    # numbers AT THE SAME TIME (joint 2-D nearest-template: loser region vs winner region in the
    # (with-side depth, against-side depth) plane). NOT the net ratio, NOT one-then-the-other.
    print(f"\n  ⭐ 2-NUMBER BOOK GATE — both pieces (with-side depth + against-side depth) judged jointly:", flush=True)
    for K in LEVELS:
        keys = [f"bwith{K}", f"bagn{K}"]
        dref, doth = zdist(F, keys, lose, win)          # joint distance to loser vs winner template
        report(f"BOOK-2 K={K} (with+agn)", ~(dref < doth), net, win, short, hours)
    print("\nDONE", flush=True)


if __name__ == "__main__":
    main()
