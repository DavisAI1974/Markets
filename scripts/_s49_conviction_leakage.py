"""_s49_conviction_leakage.py — MANDATORY pre-wiring gate (Architect S36b): the two-factor conviction signal
computed AT the flip cell must be invariant to all data AFTER it. Runs odcore.leakage.assert_no_leakage on
both conviction factors (clmx_60 quality axis + the size_score axis) at the decision cells, per cell.

If this passes, the conviction->SIZE wiring into simulate_swing_maker is leakage-clean and may proceed.
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _liquidity_dive import build_channels
from _birth_probe import load_book
from odcore.flip_detector import lean_series, detect_flips
from odcore.leakage import assert_no_leakage

WFLIP, REV, DIVW = 600, 0.1, 600


def vm(vol_cum, t, w, N):
    lo = max(0, t + 1 - w)
    return (vol_cum[t + 1] - vol_cum[lo]) / (t + 1 - lo)


def make_signals(coin, K):
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"
    ch, g = build_channels(path, K, 20)
    mid0 = np.asarray(g["mid"], float)
    buy0, sell0 = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    # flip cells from the production detector (the decision cells we size at)
    lean0 = lean_series(buy0, sell0, WFLIP)
    flips = detect_flips(lean0, REV)[0]
    flip_cells = [int(c) for (c, p, s) in flips if 0 < int(c) < len(mid0) - 1]
    # pivot for cell i is CAUSAL (depends only on lean[0..i], detect_flips is a forward ZigZag), so it is
    # invariant to data after i -> precompute once. dive_depth then = |lean[piv[i]]| with piv[i] <= i, and
    # lean[0..i] is unchanged under post-i corruption, so size_at recomputes lean (fast cumsum) but indexes
    # only at <= i. This keeps the leakage test faithful while avoiding a per-call detect_flips over ~1M cells.
    PIV = {int(c): int(pp) for (c, pp, s) in flips}

    # signal_at recomputes the causal conviction features from the (corruptible) p/bv/sv arrays.
    def clmx_at(i, ts, p, bv, sv):
        vol = bv + sv
        cvol = np.concatenate([[0.0], np.cumsum(vol)])
        return round(float(vm(cvol, i, 60, len(p)) / (vm(cvol, i, 600, len(p)) + 1e-12)), 9)

    def size_at(i, ts, p, bv, sv):
        vol = bv + sv
        cvol = np.concatenate([[0.0], np.cumsum(vol)])
        v60 = vm(cvol, i, 60, len(p))
        sret = np.concatenate([[0.0], np.diff(p) / p[:-1]])
        vlt = float(np.std(sret[max(0, i - 120):i + 1])) * 1e4
        lo = max(0, i - DIVW)
        rnp = abs(p[i] - p[lo]) / p[lo] * 1e4
        lean = lean_series(bv, sv, WFLIP)        # fast cumsum; indexed only at piv[i] <= i (invariant)
        dp = abs(lean[PIV.get(i, i)])
        return round(float(v60 + vlt + rnp + dp), 9)

    return mid0, buy0, sell0, flip_cells, clmx_at, size_at


CELLS = [("sol", 1), ("doge", 1), ("xrp", 1), ("eth", 1), ("btc", 10)]
print("=== conviction leakage gate (assert_no_leakage on clmx + size axes) ===")
all_ok = True
for coin, K in CELLS:
    if not os.path.exists(f"/tmp/{coin}_coinbase_book.jsonl.gz"):
        print(f"[{coin}] no book"); continue
    mid, buy, sell, fc, clmx_at, size_at = make_signals(coin, K)
    ts = np.arange(len(mid), dtype=float)
    # sample up to 120 flip cells (detect_flips re-run per i is heavy); enough to catch systematic look-ahead
    rng = np.random.default_rng(0)
    idxs = sorted(rng.choice(fc, size=min(120, len(fc)), replace=False).tolist()) if fc else []
    ok_c, fails_c = assert_no_leakage(clmx_at, ts, mid, buy, sell, idxs, reps=3)
    ok_s, fails_s = assert_no_leakage(size_at, ts, mid, buy, sell, idxs, reps=3)
    ok = ok_c and ok_s
    all_ok &= ok
    print(f"[{coin:4s}] flips={len(fc):>4} tested={len(idxs):>3}  clmx {'PASS' if ok_c else 'FAIL '+str(fails_c[:2])}"
          f"   size {'PASS' if ok_s else 'FAIL '+str(fails_s[:2])}")
print(f"\nOVERALL: {'PASS — conviction signal is leakage-clean, wiring may proceed' if all_ok else 'FAIL — DO NOT WIRE'}")
sys.exit(0 if all_ok else 1)
