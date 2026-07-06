"""_s66_canary_capacity.py — prove odcore.capacity reproduces the S50/S51 _capacity_model._leg_caps
BIT-FOR-BIT (v1 flow-bound + v2 queue-honest). MUST pass before wiring capacity into the executor.
"""
import os
import sys
from dataclasses import dataclass

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odcore.capacity import caps_for_legs, FILL_W          # noqa: E402
from _capacity_model import _leg_caps                        # noqa: E402


@dataclass
class L:
    side: int
    open_idx: int
    close_idx: int
    flip_idx: int


def main():
    rng = np.random.default_rng(7)
    n = 5000
    mid = 100.0 + np.cumsum(rng.normal(0, 0.02, n))
    buy = np.abs(rng.normal(3, 2, n))
    sell = np.abs(rng.normal(3, 2, n))
    bb = np.abs(rng.normal(50, 20, n))
    ba = np.abs(rng.normal(50, 20, n))

    # random legs (both sides, varied open/flip/close spacing incl. some c<=o degenerate)
    legs = []
    for _ in range(400):
        ci = int(rng.integers(1, n - 300))
        oi = ci + int(rng.integers(0, 40))
        c = oi + int(rng.integers(-2, 250))    # -2 exercises the c<=o guard
        legs.append(L(int(rng.choice([-1, 1])), oi, min(c, n - 1), ci))

    for window in (FILL_W, None, 3, 50):
        for pe in (True, False):
            v1_ref, v2_ref = _leg_caps(legs, mid, buy, sell, bb, ba,
                                       queue_frac=1.0, window=window, price_eligible=pe)
            v1_new = caps_for_legs(legs, mid, buy, sell, window=window, price_eligible=pe)  # flow-bound
            v2_new = caps_for_legs(legs, mid, buy, sell, window=window, price_eligible=pe,
                                   bb=bb, ba=ba, queue_frac=1.0)                            # queue-honest
            d1 = float(np.max(np.abs(v1_new - v1_ref)))
            d2 = float(np.max(np.abs(v2_new - v2_ref)))
            assert d1 == 0.0, f"v1 mismatch window={window} pe={pe}: max|Δ|={d1}"
            assert d2 == 0.0, f"v2 mismatch window={window} pe={pe}: max|Δ|={d2}"
            print(f"  window={str(window):>4} price_eligible={pe!s:>5}: v1 max|Δ|={d1}  v2 max|Δ|={d2}  OK")

    # queue_frac variation
    for qf in (0.0, 0.5, 2.0):
        _, v2_ref = _leg_caps(legs, mid, buy, sell, bb, ba, queue_frac=qf)
        v2_new = caps_for_legs(legs, mid, buy, sell, bb=bb, ba=ba, queue_frac=qf)
        assert float(np.max(np.abs(v2_new - v2_ref))) == 0.0, f"queue_frac={qf} mismatch"
        print(f"  queue_frac={qf}: OK")

    print("CANARY PASS: odcore.capacity == _capacity_model._leg_caps (v1 flow-bound + v2 queue-honest), all configs")


if __name__ == "__main__":
    main()
