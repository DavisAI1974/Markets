"""_canary_leakage.py — the leakage check CATCHES a look-ahead signal and CLEARS the dipole.

Run: python _canary_leakage.py
"""
import bisect

import numpy as np

from odcore.info_dipole import divergence
from odcore.leakage import assert_no_leakage
from _info_dipole_swing_backtest import load_series

W = 900.0


def clean_dipole(i, ts, p, bv, sv):
    """The S36 signal: divergence imbalance over the strictly-prior window [i-W, i]. Must be leak-free."""
    lo = bisect.bisect_left(ts, ts[i] - W)
    if i - lo < 6:
        return None
    dv = divergence(bv[lo:i + 1], sv[lo:i + 1], p[i] - p[lo])
    return None if dv is None else round(dv["imb_level"], 10)


def leaky_control(i, ts, p, bv, sv):
    """Deliberate look-ahead (peeks one tick into the future) — the check MUST catch this."""
    if i + 1 >= len(p):
        return None
    return round(float(p[i + 1] - p[i]), 10)


def main():
    ts, p, bv, sv = load_series("realbins")["btc_kraken"]
    idxs = list(range(3000, len(ts) - 5, max(1, (len(ts) - 3000) // 40)))
    ok_clean, _ = assert_no_leakage(clean_dipole, ts, p, bv, sv, idxs)
    ok_leak, fails = assert_no_leakage(leaky_control, ts, p, bv, sv, idxs)
    print(f"pre-entry leakage check on {len(idxs)} sampled indices:")
    print(f"  CLEAN dipole (divergence over [i-W,i]):  {'PASS (leak-free)' if ok_clean else 'FAIL — LEAKS'}")
    print(f"  LEAKY control (uses p[i+1]):             "
          f"{'PASS (BAD — check is blind!)' if ok_leak else f'caught {len(fails)} leaks (GOOD)'}")
    assert ok_clean and not ok_leak, "leakage check is not working as intended"
    print("  CANARY PASS — the check clears the dipole and catches look-ahead. Use it as the harness gate.")


if __name__ == "__main__":
    main()
