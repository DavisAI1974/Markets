"""_canary_incremental.py — prove RollingFlow (O(1)/tick) == the batch window operator, and time the win.

Run: python _canary_incremental.py
"""
import bisect
import time

import numpy as np

from odcore.incremental import RollingFlow
from _info_dipole_swing_backtest import load_series

W = 300.0


def batch_imb(ts, bv, sv, i):
    lo = bisect.bisect_left(ts, ts[i] - W)
    B = bv[lo:i + 1].sum(); S = sv[lo:i + 1].sum()
    return (B - S) / (B + S) if B + S > 0 else 0.0


def batch_exhaust(ts, bv, sv, i):
    lo = bisect.bisect_left(ts, ts[i] - W)
    hb = bisect.bisect_left(ts, ts[i] - W / 2)
    e = (bv[lo:hb].sum() - sv[lo:hb].sum()); et = bv[lo:hb].sum() + sv[lo:hb].sum()
    l = (bv[hb:i + 1].sum() - sv[hb:i + 1].sum()); lt = bv[hb:i + 1].sum() + sv[hb:i + 1].sum()
    ie = e / et if et > 0 else 0.0; il = l / lt if lt > 0 else 0.0
    return abs(il) < abs(ie)


def main():
    series = load_series("realbins")
    ts, p, bv, sv = series["btc_kraken"]
    rf = RollingFlow(W)
    max_err = 0.0; exh_mismatch = 0; checks = 0
    t0 = time.perf_counter()
    for i in range(len(ts)):
        rf.update(ts[i], bv[i], sv[i])
        if i > 50 and i % 3000 == 0:
            max_err = max(max_err, abs(rf.imbalance() - batch_imb(ts, bv, sv, i)))
            if rf.exhausting() != batch_exhaust(ts, bv, sv, i):
                exh_mismatch += 1
            checks += 1
    t_inc = time.perf_counter() - t0
    print(f"incremental RollingFlow vs batch window operator (btc_kraken, {len(ts)} ticks, W={W:.0f}s):")
    print(f"  imbalance max abs err = {max_err:.2e}   (checks={checks})")
    print(f"  exhausting mismatches = {exh_mismatch}/{checks}")
    print(f"  full incremental pass over {len(ts)} ticks: {t_inc*1e3:.0f} ms "
          f"({t_inc/len(ts)*1e6:.2f} us/tick, O(1) amortized)")
    assert max_err < 1e-9 and exh_mismatch == 0, "incremental operator diverges from batch!"
    print("  CANARY PASS — incremental operator is bit-faithful to the batch math.")


if __name__ == "__main__":
    main()
