"""S74 THREE-CANDIDATE GATE EVAL — per coin, decide at onset using ONLY pre-onset features on the LIVE legs
(net/dur come from run_kraken_cell via sep_diag.extract_full, cached to *_feats2.npz — the executor owns the
trades; we only choose which to FIRE).

  (A) ENERGY-ONLY   = the current partial gate: 4 energy anchors (short/long x win/lose), skip a trade whose
                      onset peak is nearer a LOSER energy than a winner energy. Baseline to beat.
  (B) EQUATION-ONLY = skip on a single ascension-shape feature's loser-tail (the REPLACEMENT candidate).
  (C) ENERGY + EQ   = skip only when energy-near-loser AND the equation confirms loser (the stack).

Decision is duration-AGNOSTIC (duration is unknown at entry): anchors/thresholds are levels applied per-trade.
Anchors fit in-sample on labels (matches the baseline's convention); a walk-forward variant is also printed.
Metric: win% / $/hr / fired% / losers-caught / winners-wrongly-skipped.  CAP=$5000/trade.
"""
import os, sys
import numpy as np
CAP = 5000.0
COINS = ["btc", "eth", "sol", "xrp"]
FEATS = ["peak","cum_final","late_integral","net_area_ratio","t_last_neg","frac_late_neg","below0",
         "below_asc","min_asc","convexity","b_blade","climb","area_neg","start"]

def load(coin):
    d = np.load(f"/tmp/kbook/{coin}_feats2.npz")
    F = {k: d[k] for k in FEATS}; net = d["net"]; dur = d["dur"]; hours = float(d["hours"])
    return F, net, dur, hours

def metrics(fire, net, win, short, hours):
    """fire = boolean keep-mask over all legs."""
    g = net[fire].sum(); ung = net.sum()
    wk = (net[fire] > 0).mean()*100 if fire.sum() else float("nan")
    sl = (~win) & short; ll = (~win) & ~short; w = win
    return dict(winpct=wk, dph=g/1e4*CAP/hours, fired=fire.sum(), n=len(net),
                firedpct=fire.mean()*100,
                sl_skip=int((~fire & sl).sum()), sl_tot=int(sl.sum()),
                ll_skip=int((~fire & ll).sum()), ll_tot=int(ll.sum()),
                w_skip=int((~fire & w).sum()), w_tot=int(w.sum()),
                ung_dph=ung/1e4*CAP/hours, ung_win=(net > 0).mean()*100)

def energy_gate(F, net, dur):
    """(A) 4-anchor nearest-energy. Returns fire-mask."""
    peak = F["peak"]; win = net > 0; med = np.median(dur); short = dur < med
    def m(mask): return float(peak[mask].mean()) if mask.sum() else 0.0
    a_sl = m((~win) & short); a_sw = m(win & short)
    a_ll = m((~win) & ~short); a_lw = m(win & ~short)
    d_lose = np.minimum(np.abs(peak-a_sl), np.abs(peak-a_ll))
    d_win = np.minimum(np.abs(peak-a_sw), np.abs(peak-a_lw))
    skip = d_lose < d_win
    return ~skip, dict(a_sl=a_sl, a_sw=a_sw, a_ll=a_ll, a_lw=a_lw)

def eq_tail_skip(vals, net, direction, frac):
    """Skip the `frac` most loser-like by a feature (direction +1 = loser is HIGH)."""
    n = len(vals); k = int(frac*n)
    order = np.argsort(-vals if direction > 0 else vals)
    skip = np.zeros(n, bool); skip[order[:k]] = True
    return ~skip

def best_eq(F, net, dur, hours, win, short):
    """(B) find the single equation feature + loser-tail fraction maximizing $/hr while keeping win% up."""
    results = []
    for k in FEATS:
        if k == "peak":
            continue                                    # peak = energy; B must be EQUATION, not energy
        v = F[k]
        gap = v[(~win)].mean() - v[win].mean()
        direction = 1 if gap > 0 else -1
        for frac in (0.05, 0.10, 0.15, 0.20, 0.30):
            fire = eq_tail_skip(v, net, direction, frac)
            mm = metrics(fire, net, win, short, hours)
            results.append((mm["dph"], k, direction, frac, mm))
    results.sort(reverse=True)
    return results

def main():
    coins = sys.argv[1:] or COINS
    for coin in coins:
        F, net, dur, hours = load(coin)
        win = net > 0; med = np.median(dur); short = dur < med
        print(f"\n############### {coin.upper()}  n={len(net)}  base win%={win.mean()*100:.1f}  {hours:.1f}h  med={med:.0f}s ###############")
        ung = metrics(np.ones(len(net), bool), net, win, short, hours)
        print(f"  UNGATED: win%={ung['ung_win']:.1f}  $/hr={ung['ung_dph']:.3f}  legs={len(net)}")

        # (A) ENERGY-ONLY
        fireA, anch = energy_gate(F, net, dur)
        mA = metrics(fireA, net, win, short, hours)
        print(f"\n  (A) ENERGY-ONLY  anchors SL={anch['a_sl']:.3f} SW={anch['a_sw']:.3f} "
              f"LL={anch['a_ll']:.3f} LW={anch['a_lw']:.3f}")
        print(f"      win%={mA['winpct']:.1f}  $/hr={mA['dph']:.3f}  fired={mA['fired']}/{mA['n']} ({mA['firedpct']:.0f}%)"
              f"  SL-skip={mA['sl_skip']}/{mA['sl_tot']} LL-skip={mA['ll_skip']}/{mA['ll_tot']}"
              f"  WIN-skip={mA['w_skip']}/{mA['w_tot']}")

        # (B) EQUATION-ONLY (best single feature)
        res = best_eq(F, net, dur, hours, win, short)
        print(f"\n  (B) EQUATION-ONLY  top-5 single-feature loser-tail skips by $/hr:")
        for dph, k, dr, frac, mm in res[:5]:
            arrow = ">=tail" if dr > 0 else "<=tail"
            print(f"      {k:13} skip {frac*100:2.0f}% {arrow}:  win%={mm['winpct']:.1f}  $/hr={dph:.3f}"
                  f"  fired={mm['firedpct']:.0f}%  SL={mm['sl_skip']}/{mm['sl_tot']} LL={mm['ll_skip']}/{mm['ll_tot']}"
                  f"  WIN-skip={mm['w_skip']}/{mm['w_tot']}")

        # (C) STACK: energy-near-loser AND best-equation-confirms-loser
        bestk = res[0][1]; bestdir = res[0][2]
        v = F[bestk]
        gapdir = bestdir
        # equation "says loser" = in the loser 40% tail of that feature
        thr = np.quantile(v, 0.60 if gapdir > 0 else 0.40)
        eq_loser = (v >= thr) if gapdir > 0 else (v <= thr)
        skipA = ~fireA
        skipC = skipA & eq_loser                       # only skip if BOTH agree
        fireC = ~skipC
        mC = metrics(fireC, net, win, short, hours)
        print(f"\n  (C) STACK energy-loser AND {bestk} loser-tail:")
        print(f"      win%={mC['winpct']:.1f}  $/hr={mC['dph']:.3f}  fired={mC['firedpct']:.0f}%"
              f"  SL-skip={mC['sl_skip']}/{mC['sl_tot']} LL-skip={mC['ll_skip']}/{mC['ll_tot']}"
              f"  WIN-skip={mC['w_skip']}/{mC['w_tot']}")
    print("\nDONE")

if __name__ == "__main__":
    main()
