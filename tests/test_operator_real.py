"""Operator-core acceptance tests on REAL bins (zero synthetic).

  (1) equal-entropy attractor (-1,-1,+2)/sqrt6 recovers on real near-symmetric channels.
  (2) lead-lag recovers a KNOWN lag injected into a REAL return series.
  (3) tautology-killing circular-shift null: a real coupled cross-venue pair has high
      coupling-z; circular-shifting one channel collapses it (kills the pairing).
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from tests.realdata import have, path
from odcore.io import load_bins, align
from odcore.operators import windowed_operator_matrix
from odcore.null_extract import extract_null, EQ_QUAD
from odcore.leadlag import detect_leadlag

pytestmark = pytest.mark.skipif(not have("btc_coinbase"),
                                reason="real bins (realbins/) not materialized")


def _quad_cos(null0):
    sub = null0[[2, 3, 4]]
    n = np.linalg.norm(sub)
    if n == 0:
        return 0.0
    sub = sub / n
    ref = EQ_QUAD[[2, 3, 4]] / np.linalg.norm(EQ_QUAD[[2, 3, 4]])
    return abs(float(sub @ ref))


def test_equal_entropy_attractor_real():
    s = load_bins(path("btc_coinbase")).resample(60)
    M = windowed_operator_matrix(s.buy, s.sell, window=40, stride=10)
    null = extract_null(M)
    # near-symmetric real channels sit on the equal-entropy substrate
    assert _quad_cos(null.null0) >= 0.90, _quad_cos(null.null0)


def test_leadlag_recovers_injected_lag_real():
    s = load_bins(path("btc_coinbase"))
    r = s.log_return()[:200000]
    lag = 7
    a = r[lag:]
    b = r[:-lag]               # b is a delayed by `lag` bars => a leads b by lag
    res = detect_leadlag(a, b, max_lag=20, n_null=100)
    assert res.lag == lag, res.lag
    assert res.leader == "a", res.leader
    assert res.z > 5, res.z


def test_tautology_null_kills_shifted_coupling_real():
    if not have("btc_bybit_perp"):
        pytest.skip("need bybit perp")
    cb, by = align(load_bins(path("btc_coinbase")), load_bins(path("btc_bybit_perp")))
    a, b = cb.log_return()[:300000], by.log_return()[:300000]
    real = detect_leadlag(a, b, max_lag=15, n_null=100)
    shift = 12345
    shifted = detect_leadlag(a, np.roll(b, shift), max_lag=15, n_null=100)
    assert real.z > 20, real.z                 # genuine cross-venue coupling
    assert real.z > 5 * max(shifted.z, 1.0), (real.z, shifted.z)  # tautology killed by shift


if __name__ == "__main__":
    test_equal_entropy_attractor_real()
    test_leadlag_recovers_injected_lag_real()
    test_tautology_null_kills_shifted_coupling_real()
    print("real-data operator tests passed")
