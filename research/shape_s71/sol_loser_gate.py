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

    # ---- CELL-SPECIFIC energy anchors from ALL legs (no train/test split; universal SHAPES, SOL's NUMBERS) ----
    def m(mask, arr): return float(arr[mask].mean()) if mask.sum() else 0.0
    sw = win & short; sl = (~win) & short
    lw = win & ~short; ll = (~win) & ~short

    # ---- 4-ANCHOR nearest-energy classification: FIRE the 2 winner energies, SKIP the 2 loser energies,
    #      each anchor with a WIGGLE margin (a trade skips only if CLEARLY nearer a loser energy) ----
    a_sl = m(sl, peak); a_sw = m(sw, peak)                  # short loser / winner energy anchors (ALL legs)
    a_ll = m(ll, peak); a_lw = m(lw, peak)                  # long  loser / winner energy anchors (ALL legs)
    d_lose = np.minimum(np.abs(peak - a_sl), np.abs(peak - a_ll))   # dist to nearest LOSER energy
    d_win  = np.minimum(np.abs(peak - a_sw), np.abs(peak - a_lw))   # dist to nearest WINNER energy
    print(f"  4 ENERGY ANCHORS (all-legs peak): SHORT-LOSE {a_sl:.3f}  SHORT-WIN {a_sw:.3f}  "
          f"LONG-LOSE {a_ll:.3f}  LONG-WIN {a_lw:.3f}\n", flush=True)

    def report(skip, ev, hrs, tag):
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

    print("  --- 4-anchor nearest-energy gate: fire winner energies, skip loser energies (WIGGLE sweep, all legs) ---", flush=True)
    for wig in (0.0, 0.01, 0.02, 0.03, 0.05):
        skip = (d_lose + wig) < d_win                        # skip only if nearer a LOSER energy by margin `wig`
        report(skip, np.arange(n), hours, f"wiggle={wig:.2f}")
    print("\nDONE", flush=True)

if __name__ == "__main__":
    main()
