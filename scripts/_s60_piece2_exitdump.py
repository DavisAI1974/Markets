"""_s60_piece2_exitdump.py — S60 PIECE 2 (EXIT): per-leg giveback anatomy dump.

Greg's S60 call: the ZIGZAG EXIT (flip-at-next-confirm — the promoted machine's own exit) is
the starting place. This dump is the leg-level record the per-coin exit agents analyze
(playbook rule: agents get DUMPS, not tapes). One row per leg of the PROMOTED entry machine
(odcore.entry_coinbase.armed_midband_flips, naive k0, entry held fixed), both venues.

Per leg (entry confirm -> next confirm = the zigzag exit):
  ANATOMY (outcome fields, labeled — not causal reads):
    gross_bp        zigzag-exit gross (the baseline the exit piece must beat)
    peak_fav_bp     max favorable excursion after entry (the oracle-exit prize)
    t_peak_c        cells from entry to the peak (grid_s converts to seconds)
    giveback_bp     peak_fav - gross (what the zigzag exit hands back — THE target)
    max_adv_bp      max adverse excursion (risk anatomy)
    dur_c           leg length in cells; frac_peak = t_peak/dur (early-peak vs late-peak rides)
  TOP-STATE (state AT the peak cell — outcome-anchored fingerprint of the top, NOT causal):
    clmx60_pk       vm(60)/vm(600) at the peak cell (S40 climax, S58 cell-count convention)
    er600_pk        trend efficiency over the 600 cells into the peak
    slean_pk        with-ride lean at the peak (lean600)
    hod_pk          hour-of-day of the peak (bins exact; books approx)
  R8 CAUSAL TRIGGERS (the lean-collapse walk exactly as swing_maker runs it — with-ride lean
  sl=side*lean600[t] walked from entry; arm at arm_hi, trigger at first collapse to exit_lo;
  machine-faithful cell-count window WFLIP=600 on BOTH grids):
    slmax           max with-ride lean over the leg + t_slmax_c
    r8_<cfg>_trig   1/0 triggered before the zigzag exit
    r8_<cfg>_t_c    trigger cell offset from entry
    r8_<cfg>_gx     mid-fill gross if exited at the trigger (leg-slice read — machines re-earn)
    cfgs: a05x0=(0.05,0.0)  a10x0=(0.10,0.0)  a20x0=(0.20,0.0)  a10xm10=(0.10,-0.10)
  ENTRY-SIDE refs: side, kind (confirm/fallback via retrace>=theta), dive_depth (|lean60@pivot|
  S58 convention), lag_bp, hod_entry, entry_idx, plus lean60-variant slmax on bins (lean-window
  wall-clock check: 600 cells = 10min on bins vs 60s on books).

Causality: triggers use only lean values <= t (verbatim swing_maker walk). The entry stream is
gated by assert_truncation_invariance per tape before dumping (the machine's own leakage gate).
Output: one CSV per coin x venue in S60_LEG_DIR (regenerable, not committed).
Usage: python scripts/_s60_piece2_exitdump.py --venue bins|books
"""
import argparse
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s58_piece1_entry import load_venue                              # noqa: E402
from odcore.entry_coinbase import (armed_midband_flips,               # noqa: E402
                                   assert_truncation_invariance)
from odcore.flip_detector import lean_series                          # noqa: E402

OUT_DIR = os.environ.get(
    "S60_LEG_DIR",
    "/tmp/claude-0/-home-user-Markets/d39da483-99f1-5e95-bee0-9f382094f1ac/scratchpad/s60_legs")

# registry shape per coin (odcore.entry_coinbase.COINBASE_MIDBAND) — dump BOTH thetas for
# agent theta-dependence reads, registry flag marks the deploy shape. ETH stays dropped.
REGISTRY_TH = {"sol": 100.0, "xrp": 80.0, "doge": 100.0, "btc": 80.0}
THETAS = (80.0, 100.0)
C = 0.5
WFLIP = 600            # machine-faithful lean window (cells — platform constant)
R8_CFGS = (("a05x0", 0.05, 0.0), ("a10x0", 0.10, 0.0),
           ("a20x0", 0.20, 0.0), ("a10xm10", 0.10, -0.10))
CB_REAL = 8.0


def vm(cvol, i, w):
    """Mean volume/cell over the trailing w cells at i (cumulative-array convention)."""
    lo = max(0, i - w)
    return (cvol[i + 1] - cvol[lo + 1]) / max(i - lo, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", choices=("bins", "books"), default="bins")
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    grid_s = 1.0 if args.venue == "bins" else 0.1

    for coin, mid, buy, sell, hrs, _b in load_venue(args.venue):
        if coin == "eth":
            continue                                        # dropped (S58 board)
        lean = lean_series(buy, sell, WFLIP)
        lean60 = lean_series(buy, sell, 60)                 # S58 dive convention + wall-clock check
        cvol = np.concatenate([[0.0], np.cumsum(buy + sell)])
        cpath = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(np.log(mid))))])

        path = f"{OUT_DIR}/exit_legs_{coin}_{args.venue}.csv"
        with open(path, "w", newline="") as fh:
            wr = csv.writer(fh)
            hdr = ["theta", "registry", "side", "kind", "grid_s",
                   "gross_bp", "net_real_bp", "peak_fav_bp", "t_peak_c", "giveback_bp",
                   "max_adv_bp", "dur_c", "frac_peak",
                   "clmx60_pk", "er600_pk", "slean_pk", "hod_pk",
                   "slmax", "t_slmax_c", "slmax60"]
            for tag, _a, _x in R8_CFGS:
                hdr += [f"r8_{tag}_trig", f"r8_{tag}_t_c", f"r8_{tag}_gx"]
            hdr += ["dive_depth", "lag_bp", "hod_entry", "entry_idx"]
            wr.writerow(hdr)

            for theta in THETAS:
                assert_truncation_invariance(mid, theta, C)
                flips = armed_midband_flips(mid, theta, C)
                for j in range(len(flips) - 1):
                    ci, pi, sd = flips[j]
                    xi = flips[j + 1][0]
                    ep = mid[ci]
                    seg = mid[ci:xi + 1]
                    fav = sd * (seg - ep) / ep * 1e4         # with-ride excursion, fav[0]=0
                    gross = float(fav[-1])
                    pk = int(np.argmax(fav))
                    peak_fav = float(fav[pk])
                    max_adv = float(-np.min(fav))
                    dur = xi - ci
                    pkidx = ci + pk
                    p0 = max(0, pkidx - 600)
                    plen = cpath[pkidx + 1] - cpath[p0 + 1]
                    er_pk = abs(mid[pkidx] - mid[p0]) / mid[p0] / plen if plen > 0 else 0.0
                    v60, v600 = vm(cvol, pkidx, 60), vm(cvol, pkidx, 600)

                    sl = sd * lean[ci:xi + 1]                # with-ride lean walk (causal)
                    slmax = float(np.max(sl)); t_slmax = int(np.argmax(sl))
                    r8cols = []
                    for _tag, ah, xl in R8_CFGS:
                        armed = False; te = -1
                        for t in range(len(sl)):
                            if not armed:
                                if sl[t] >= ah:
                                    armed = True
                            elif sl[t] <= xl:
                                te = t
                                break
                        if te < 0:
                            r8cols += [0, -1, ""]
                        else:
                            gx = float(fav[te])
                            r8cols += [1, te, round(gx, 2)]

                    retrace = abs(ep - mid[pi]) / mid[pi] * 1e4
                    kind = "fallback" if retrace >= theta * 0.999 else "confirm"
                    hod_e = int((ci * grid_s // 3600) % 24)
                    hod_p = int((pkidx * grid_s // 3600) % 24)
                    wr.writerow([theta, int(theta == REGISTRY_TH[coin]), sd, kind, grid_s,
                                 round(gross, 2), round(gross - 2 * CB_REAL, 2),
                                 round(peak_fav, 2), pk, round(peak_fav - gross, 2),
                                 round(max_adv, 2), dur, round(pk / max(dur, 1), 3),
                                 round(v60 / v600, 3) if v600 > 0 else 0,
                                 round(er_pk, 3), round(float(sd * lean[pkidx]), 4), hod_p,
                                 round(slmax, 4), t_slmax,
                                 round(float(np.max(sd * lean60[ci:xi + 1])), 4),
                                 *r8cols,
                                 round(abs(lean60[pi]), 4), round(retrace, 2), hod_e, ci])
        print(f"[{coin} {args.venue}] wrote {path}  ({hrs:.1f}h tape)")


if __name__ == "__main__":
    main()
