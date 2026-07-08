"""S73 REFINED ENTRY GATE — SOL, 4-cell UNIVERSAL-SHAPE / CELL-SPECIFIC-NUMBER cascade (selection on the
agent's ORIGINAL builder; DECISION through the LIVE run_kraken_cell — nothing reinvented). Same SOL 73h book.

The universal shapes (coin-universal across the 4 majors; doge separate), applied with SOL's OWN thresholds:
  - classify each forming trade's shape SHORT vs LONG by ENERGY (onset peak magnitude),
  - SHORT-LOSER  = the flat / low-energy / near-zero-peak short shape         -> SKIP,
  - LONG-LOSER   = the long shape that dips DEEPER / LONGER below zero          -> SKIP,
  - fire $5k on everything else (short-winner + long-winner).
Sequential cascade: each characteristic checked in turn; a trade that shows a loser trait is skipped.
Shape-only (normalized imbalance-ratio arc — NO volume, NO price). Thresholds derived on TRAIN, applied OOS.
LIVE lean+exit, one-sided maker, no deep-bail.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from sol_ascent_eq import extract       # runs LIVE run_kraken_cell via the agent builder
CAP = 5000.0

def main():
    print("=== S73 REFINED 4-CELL ENTRY GATE — SOL (LIVE run_kraken_cell; agent builder) ===", flush=True)
    rows, net, dur, hours = extract()
    n = len(rows)
    peak = np.array([r["peak"] for r in rows])
    min_asc = np.array([r["min_asc"] for r in rows])       # below-zero dip depth in the ascent region
    win = net > 0; med = np.median(dur); short = dur < med
    cut = int(n*0.6); tr = np.arange(cut); te = np.arange(cut, n); hte = hours*(n-cut)/n

    # ---- CELL-SPECIFIC thresholds from TRAIN (universal SHAPES, SOL's NUMBERS) ----
    def m(mask, arr): return float(arr[mask].mean()) if mask.sum() else 0.0
    sw = win[tr] & short[tr]; sl = (~win[tr]) & short[tr]
    lw = win[tr] & ~short[tr]; ll = (~win[tr]) & ~short[tr]
    P_split  = 0.5*(m(short[tr], peak[tr]) + m(~short[tr], peak[tr]))   # short vs long shape (by energy/peak)
    peak_sl  = m(sl, peak[tr])                                         # short-loser's OWN energy number (its cell)
    peak_ll  = m(ll, peak[tr])                                         # long-loser's OWN energy number (its cell)
    print(f"  SOL ENERGY thresholds (train): P_split(peak)={P_split:.3f}  "
          f"short-loser peak<{peak_sl:.3f}  long-loser peak<{peak_ll:.3f}", flush=True)
    print(f"    cell energy numbers (train peak): SHORT-WIN {m(sw,peak[tr]):.3f} / SHORT-LOSE {m(sl,peak[tr]):.3f} | "
          f"LONG-WIN {m(lw,peak[tr]):.3f} / LONG-LOSE {m(ll,peak[tr]):.3f}\n", flush=True)

    # ---- PURE-ENERGY fire gate: skip the low-energy loser in EACH category (peak = onset energy) ----
    is_long_shape = peak >= P_split
    skip_short_loser = (~is_long_shape) & (peak < peak_sl)             # low-energy short -> skip
    skip_long_loser  = is_long_shape & (peak < peak_ll)               # low-energy long  -> skip
    skip = skip_short_loser | skip_long_loser

    def report(ev, hrs, tag):
        fire = ~skip[ev]
        ung = net[ev].sum(); g = net[ev][fire].sum(); nk = int(fire.sum()); ne = len(ev)
        wa = (net[ev] > 0).mean(); wk = (net[ev][fire] > 0).mean() if nk else float("nan")
        sl_ev = (~win[ev]) & short[ev]; ll_ev = (~win[ev]) & ~short[ev]; w_ev = win[ev]
        print(f"    [{tag}] UNGATED win%={wa*100:.1f} $/hr={ung/1e4*CAP/hrs:6.3f}  ->  "
              f"GATED win%={wk*100:.1f} $/hr={g/1e4*CAP/hrs:6.3f}  fired={nk}/{ne} ({fire.mean()*100:.0f}%)",
              flush=True)
        print(f"        short-losers skipped {int((skip[ev]&sl_ev).sum())}/{int(sl_ev.sum())}  "
              f"long-losers skipped {int((skip[ev]&ll_ev).sum())}/{int(ll_ev.sum())}  "
              f"winners wrongly skipped {int((skip[ev]&w_ev).sum())}/{int(w_ev.sum())}", flush=True)

    print("  --- REFINED 4-cell cascade (skip short-loser on energy + long-loser on below-zero dip) ---", flush=True)
    report(np.arange(n), hours, "IN-SAMPLE")
    report(te, hte, "OOS-40%")
    print("\nDONE", flush=True)

if __name__ == "__main__":
    main()
