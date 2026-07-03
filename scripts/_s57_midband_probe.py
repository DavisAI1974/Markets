"""_s57_midband_probe.py — S57: FIRST PASS at the MID BAND (Greg: "we are going to have to
figure out that mid band. there's no other way").

The fee reality (this session, verified tiers): the fine 2-4bp band is negative at EVERY
reachable Coinbase tier (-$124..-$2,380/hr at $5k all-in). The mid band (60-100bp coarse
swings) is the band whose swings can pay real fees. This probe = the machine Greg specced:

  COARSE selection: theta zigzag on mid (theta 60/80/100bp) — the swing structure.
  ENTRY: the zigzag's own barely-late entry — the FIRST deployed fine-flip confirm with the
    coarse direction, at/after the coarse turn's CONFIRM cell (causal: coarse turns are only
    known at confirm; fine flips are the deployed detector, untouched).
  STAGED COMMIT: starter s0 x $5k at entry; ALL-IN (top to $5k — the S57 cap) at the first
    +2bp favorable print after entry (the S57-measured trigger). No add if never confirmed.
  EXIT: the next coarse leg's entry flip (position flips there), else the next coarse confirm.

Priced at the real Coinbase tiers (both sides maker-posted — deployed executor measures
~0-1% taker with cover-grace; the fine-flip exit is postable). Controls: REVERSED (coarse
directions inverted, same mechanics) + oracle capture fraction. ONE WINDOW per cell —
PROVISIONAL by standing rule; the gate (multi-window + shuffle) comes before any adoption.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _birth_probe import load_book                                    # noqa: E402
from _liquidity_dive import build_channels                            # noqa: E402
from odcore.flip_detector import lean_series, detect_flips            # noqa: E402
from odcore.platform import FLOW_W, WFLIP, REV                        # noqa: E402

MID_USD = 5000.0
S0 = 0.4                        # starter fraction (all-in = $5k total)
CONF = 2.0                      # bp — the measured staged trigger
THETAS = (60.0, 80.0, 100.0)
FEE_TIERS = (("cb_entry <10k", 40.0), ("cb_early 100k-1M", 10.0),
             ("cb_real 1-15M", 8.0), ("cb_scale 75-250M", 3.0), ("cb_top ceil", 0.0))
# maker-posted both sides -> fee per side = maker rate; taker exposure noted in docstring


def coarse_zigzag(mid, theta_bp):
    """Theta zigzag: list of (pivot_idx, confirm_idx, new_dir). Causal confirms — a turn
    exists only once price retraces theta from the tracked extreme (separate hi/lo tracking;
    the single-extreme version silently never armed at d=0 — caught by a 0-pivot canary)."""
    out = []
    hi = lo = mid[0]; hi_i = lo_i = 0; d = 0
    for i in range(1, len(mid)):
        p = mid[i]
        if d >= 0:
            if p > hi:
                hi, hi_i = p, i
            if (p - hi) / hi * 1e4 <= -theta_bp:   # top confirmed -> short leg begins
                out.append((hi_i, i, -1)); d = -1; lo, lo_i = p, i
                continue
        if d <= 0:
            if p < lo:
                lo, lo_i = p, i
            if (p - lo) / lo * 1e4 >= theta_bp:    # bottom confirmed -> long leg begins
                out.append((lo_i, i, +1)); d = +1; hi, hi_i = p, i
    return out


def run_cell(coin):
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"
    raw = load_book(path)
    _, g = build_channels(path, 1, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    hrs = (float(raw["ts"][-1]) - float(raw["ts"][0])) / 3600.0
    lean = lean_series(buy, sell, WFLIP)
    fines = detect_flips(lean, REV)[0]          # (confirm, pivot, side) — deployed detector
    fc = np.asarray([int(c) for (c, p, s) in fines])
    fs = np.asarray([int(s) for (c, p, s) in fines])

    for theta in THETAS:
        for tag, sgn in (("fwd", +1), ("REV", -1)):
            piv = coarse_zigzag(mid, theta)
            legs = []
            oracle = 0.0
            for k in range(len(piv) - 1):
                _, cidx, d0 = piv[k]
                npiv, ncidx, _nd = piv[k + 1]
                d = d0 * sgn
                oracle += abs(mid[npiv] - mid[piv[k][0]]) / mid[piv[k][0]] * 1e4 if sgn > 0 else 0
                # barely-late entry: first fine flip with side==d at/after coarse confirm
                j = np.searchsorted(fc, cidx)
                while j < len(fc) and fs[j] != d:
                    j += 1
                if j >= len(fc) or fc[j] >= ncidx:
                    continue
                ei = int(fc[j]); ep = mid[ei]
                # exit: next coarse leg's entry flip (side == -d after next coarse confirm)
                j2 = np.searchsorted(fc, ncidx)
                while j2 < len(fc) and fs[j2] != -d:
                    j2 += 1
                xi = int(fc[j2]) if j2 < len(fc) else ncidx
                xp = mid[xi]
                seg = mid[ei:xi + 1]
                fav = d * (seg - ep) / ep * 1e4
                hit = np.nonzero(fav >= CONF)[0]
                ai = ei + int(hit[0]) if len(hit) else -1
                legs.append((d, ep, xp, ai, mid[ai] if ai >= 0 else 0.0))
            if not legs:
                continue
            n = len(legs)
            d_ = np.asarray([l[0] for l in legs]); ep = np.asarray([l[1] for l in legs])
            xp = np.asarray([l[2] for l in legs]); ai = np.asarray([l[3] for l in legs])
            ap = np.asarray([l[4] for l in legs])
            gross = d_ * (xp - ep) / ep * 1e4
            gadd = np.where(ai >= 0, d_ * (xp - ap) / np.where(ap > 0, ap, 1) * 1e4, 0.0)
            addpct = 100 * np.mean(ai >= 0)
            win = 100 * np.mean(gross > 0)
            if tag == "fwd":
                print(f"\n[{coin} theta={theta:.0f}bp] {n} legs ({n / hrs:.1f}/hr) "
                      f"win {win:.0f}%  mean swing {np.mean(np.abs(gross)):.0f}bp  "
                      f"add fires {addpct:.0f}%")
                hdr = "  " + f"{'tier':>18} | {'all-in $/hr':>11} | {'staged $/hr':>11}"
                print(hdr)
            for label, mk in FEE_TIERS:
                fee = 2 * mk                     # maker both sides
                allin = float(np.sum(MID_USD * (gross - fee) / 1e4)) / hrs
                st = S0 * MID_USD * (gross - fee) / 1e4
                ad = np.where(ai >= 0, (1 - S0) * MID_USD * (gadd - fee) / 1e4, 0.0)
                staged = float(np.sum(st + ad)) / hrs
                if tag == "fwd":
                    print(f"  {label:>18} | {allin:>+11.2f} | {staged:>+11.2f}")
                elif label == "cb_real 1-15M":
                    print(f"  {'REVERSED @cb_real':>18} | {allin:>+11.2f} | {staged:>+11.2f}")


def main():
    for coin in ("sol", "eth"):
        run_cell(coin)


if __name__ == "__main__":
    main()
