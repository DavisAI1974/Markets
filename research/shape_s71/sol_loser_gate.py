"""S73 CELL-SPECIFIC SEQUENTIAL LOSER GATE (selection on the agent's ORIGINAL builder; builds no shapes).
Per Greg: NOT a general rule — SOL's OWN loser characteristics, checked ONE AT A TIME; if a forming trade's
shape matches a loser trait (fails a check), SKIP it. Thresholds are CELL-SPECIFIC (derived from SOL's own
short-category graphs) with WIGGLE ROOM. Real-time-comparable: every trait is read off the causal pre-onset
limb. LIVE lean+exit, $5k/trade, one-sided maker, no deep-bail.

SOL SHORT-LOSER traits (from the ascension equation, short category): smaller PEAK@onset, dips further
BELOW ZERO (start), and FLATTER / less hockey-stick. A trade that shows ALL of these short-loser traits is
classified a short-loser and skipped. (Long-loser gets its own cell/category rule later — it's entry-strong.)
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from sol_ascent_eq import extract, keys   # reuse the ascension-equation extractor (agent builder)
CAP = 5000.0

def cat_mean(F, mask, k):
    return float(F[k][mask].mean())

def main():
    print("=== S73 CELL-SPECIFIC SEQUENTIAL SHORT-LOSER GATE — SOL (agent builder) ===", flush=True)
    rows, net, dur, hours = extract()
    n = len(rows)
    F = {k: np.array([r[k] for r in rows]) for k in keys}
    win = net > 0; med = np.median(dur); short = dur < med
    cut = int(n*0.6); tr = np.arange(cut); te = np.arange(cut, n)

    # --- CELL-SPECIFIC thresholds: midpoint of SOL's SHORT winner vs loser means, on TRAIN (with wiggle) ---
    sw = win[tr] & short[tr]; sl = (~win[tr]) & short[tr]
    thr = {}
    for k in ("peak", "rise_energy", "start"):
        w_ = cat_mean(F, tr[sw], k) if sw.sum() else 0.0
        l_ = cat_mean(F, tr[sl], k) if sl.sum() else 0.0
        thr[k] = 0.5*(w_+l_)                                  # skip-trait boundary (below = loser side)
    print(f"  SOL short-category thresholds (train): peak<{thr['peak']:.4f}  "
          f"rise_energy<{thr['rise_energy']:.4f}  start<{thr['start']:.4f}  (below = short-loser trait)\n", flush=True)

    # --- the SEQUENTIAL checks (each True if the trade shows the loser trait). ENERGY (peak/rise), not blade. ---
    trait_lowpeak   = F["peak"] < thr["peak"]                 # smaller peak = less energy at onset
    trait_lowenergy = F["rise_energy"] < thr["rise_energy"]   # smaller rise = less energy going in
    trait_dip       = F["start"] < thr["start"]              # dips further below zero (short-loser tell)

    def report(mask_eval, hrs, tag, skip):
        ev = mask_eval
        fire = ~skip[ev]
        ung = net[ev].sum(); g = net[ev][fire].sum(); nk = int(fire.sum()); ne = int(ev.sum())
        wa = (net[ev] > 0).mean(); wk = (net[ev][fire] > 0).mean() if nk else float("nan")
        # diagnostics: of actual short-losers, how many skipped; of winners, how many wrongly skipped
        sl_ev = (~win[ev]) & short[ev]; w_ev = win[ev]
        sl_skipped = int((skip[ev] & sl_ev).sum()); sl_tot = int(sl_ev.sum())
        w_skipped = int((skip[ev] & w_ev).sum()); w_tot = int(w_ev.sum())
        print(f"    [{tag}] UNGATED win%={wa*100:.1f} $/hr={ung/1e4*CAP/hrs:6.3f}  ->  "
              f"GATED win%={wk*100:.1f} $/hr={g/1e4*CAP/hrs:6.3f}  fired={nk}/{ne} ({fire.mean()*100:.0f}%)",
              flush=True)
        print(f"        short-losers skipped {sl_skipped}/{sl_tot}  |  winners wrongly skipped {w_skipped}/{w_tot}",
              flush=True)

    hte = hours*(n-cut)/n
    # variant A: energy check only (the dominant SOL short-loser tell = low onset peak / low rise)
    skipA = trait_lowpeak
    # variant B: sequential cascade — low energy (peak) AND low rise AND dips below zero = short-loser
    skipB = trait_lowpeak & trait_lowenergy & trait_dip
    print("  --- A: single check (peak/energy too low) ---", flush=True)
    report(np.arange(n), hours, "IN-SAMPLE", skipA); report(te, hte, "OOS-40%", skipA)
    print("\n  --- B: sequential cascade (low peak AND low rise-energy AND dips below zero) ---", flush=True)
    report(np.arange(n), hours, "IN-SAMPLE", skipB); report(te, hte, "OOS-40%", skipB)
    print("\nDONE", flush=True)

if __name__ == "__main__":
    main()
