"""S73 ASCENSION EQUATION (selection/analysis on the agent's ORIGINAL builder arc_gate.py — builds NO
shapes itself). Fit each trade's pre-onset ignition limb to an ascent equation and read whether its
coefficients differentiate winners from losers IN EACH CATEGORY (short/long x win/lose). Greg: the SLOPE
(rate of ascent) differs — most between longs/shorts, but also winners/losers. No averaging in the decision,
no AUC. LIVE lean+exit via run_kraken_cell, $5k/trade, one-sided maker, no deep-bail.

ASCENT EQUATION per trade, over the strictly-pre-onset limb (leakage-free):
  flow(t) ~= a + b*t + c*t^2   (t in seconds, -45..0)
    b        = rate of ascent (the slope Greg points at)          [full-limb]
    b_blade  = rate of ascent over the last 15s (the hockey-stick blade, steep part into onset)
    c        = curvature (accelerating-in = hockey stick)
    peak     = flow at onset (t=0)   (winner tops HIGH)
    start    = flow at -45s           (loser starts / dips BELOW ZERO)
    dip      = min flow over the limb (the below-zero dip)
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from arc_gate import (load_raw, rolling_imb, build_channels, median_spread_bps,   # the agent's builder
                      run_kraken_cell, KRAKEN, PRE, CPS)
SMOOTH_SEC = 20; CAP = 5000.0
BLADE = 15 * CPS                      # last 15s = the blade window (into onset)
EARLY = 30 * CPS                      # first 30s = the handle (early part of the limb)

def ascent_eq(pre):
    """Fit the ascent equation to one trade's pre-onset limb; return its coefficients + Greg's
    hockey-stick / ascent-timing tells."""
    x = (np.arange(len(pre)) - PRE) * 0.1                 # seconds -45..0
    c, b, a = np.polyfit(x, pre, 2)                       # a + b t + c t^2
    b_blade = np.polyfit(x[-BLADE:], pre[-BLADE:], 1)[0]  # last-15s slope (the blade, late)
    b_early = np.polyfit(x[:EARLY], pre[:EARLY], 1)[0]    # first-30s slope (the handle, early)
    hockey = b_blade - b_early                            # >0 = flat handle then steep blade (winner);
    #                                                       ~0 = uniform LINEAR rise (short-loser)
    rise = np.clip(pre - pre.min(), 0, None)              # ascent above the limb's own floor
    center = float((x * rise).sum() / (rise.sum() + 1e-9))  # time-center of the rise: more NEGATIVE = ascent
    #                                                         STARTS SOONER (short-loser); near 0 = late launch
    asc = pre[-25*CPS:]                                    # the ascent region (last 25s, into onset)
    min_asc = float(asc.min())                            # Greg: SHORT-LOSER dips BELOW ZERO here, winner does NOT
    below_asc = float((asc < 0).mean())                  # fraction of the ascent region spent below zero
    # ACTIVE-CLIMB ascension rate = rise from the limb's dip up to its peak, per second (the rate the GRAPH
    # shows: winner steeper). NOT the full-limb/terminal slope, which saturates and reads backwards.
    i_min = int(np.argmin(pre)); i_peak = int(np.argmax(pre))
    asc_rate = float((pre[i_peak] - pre[i_min]) / ((i_peak - i_min) * 0.1)) if i_peak > i_min else 0.0
    rise_energy = float(pre[-1] - pre[0])                 # ENERGY into the trade (peak - start): winner HIGHER
    #   NOTE: b_blade/hockey (terminal-15s slope) is a MISLEADING energy proxy — a winner reaching a higher
    #   peak saturates near onset so its blade-slope reads LOWER (artifact). Use PEAK / rise_energy instead.
    return dict(b=b, b_blade=b_blade, b_early=b_early, hockey=hockey, c=c, asc_rate=asc_rate,
                peak=float(pre[-1]), start=float(pre[0]), dip=float(pre.min()), center=center,
                min_asc=min_asc, below_asc=below_asc, rise_energy=rise_energy)

def extract():
    path = "/tmp/kbook/sol_book.jsonl"; cfg = [c for c in KRAKEN if c.coin == "sol"][0]
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw)/2.0; N = len(mid); hours = N*0.1/3600.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)          # LIVE decision path
    imb = rolling_imb(buy, sell, SMOOTH_SEC)
    rows, net, dur = [], [], []
    for l in res.legs:
        o = int(l.open_idx); c = int(l.close_idx)
        if o - PRE < 0 or c <= o:
            continue
        pre = imb[o-PRE:o+1] * int(l.side)
        rows.append(ascent_eq(pre)); net.append(float(l.net_bps)); dur.append((c-o)*0.1)
    return rows, np.array(net), np.array(dur), hours

def main():
    print("=== S73 ASCENSION EQUATION — SOL, per-category slope differentiation (agent builder) ===", flush=True)
    rows, net, dur, hours = extract()
    n = len(rows)
    keys = ["peak", "rise_energy", "asc_rate", "start", "min_asc", "below_asc", "center"]  # ENERGY + active-climb RATE
    F = {k: np.array([r[k] for r in rows]) for k in keys}
    win = net > 0; med = np.median(dur); short = dur < med
    print(f"  SOL legs: {n}  ({hours:.1f}h)  base win%={win.mean()*100:.1f}  median dur={med:.0f}s\n", flush=True)

    print("  --- ascent-equation coefficients per CATEGORY (mean; the differentiators) ---", flush=True)
    print(f"    {'category':12}{'n':>5}" + "".join(f"{k:>10}" for k in keys) + f"{'net/leg':>9}", flush=True)
    cats = [("SHORT-WIN", win & short), ("SHORT-LOSE", ~win & short),
            ("LONG-WIN", win & ~short), ("LONG-LOSE", ~win & ~short)]
    for name, m in cats:
        if m.sum() == 0:
            continue
        print(f"    {name:12}{m.sum():>5}" + "".join(f"{F[k][m].mean():>10.4f}" for k in keys) +
              f"{net[m].mean():>9.2f}", flush=True)
    print("", flush=True)
    # the two axes Greg named, isolated:
    def gap(mask_a, mask_b, lab_a, lab_b):
        print(f"  --- {lab_a} vs {lab_b} ---", flush=True)
        for k in keys:
            va, vb = F[k][mask_a].mean(), F[k][mask_b].mean()
            print(f"    {k:8}: {lab_a}={va:+.4f}  {lab_b}={vb:+.4f}  gap={va-vb:+.4f}", flush=True)
        print("", flush=True)
    # CELL-SPECIFIC, CATEGORY-SPECIFIC differentiation (the entry-gate axis, per Greg):
    gap(win & short, ~win & short, "SHORT-WIN", "SHORT-LOSE")
    gap(win & ~short, ~win & ~short, "LONG-WIN", "LONG-LOSE")
    print("DONE", flush=True)

if __name__ == "__main__":
    main()
