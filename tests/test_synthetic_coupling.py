"""
Phase-0 acceptance tests: the operator core reproduces the research-log controls.

  (1) symmetric independent channels -> null aligns with the equal-entropy attractor
      (-1,-1,+2)/sqrt6 in the quadratic subspace (INFO-012); MI not structured.
  (2) native structured coupling -> MI enters the null (mi_frac high), slope > 0, and
      the slope RISES monotonically with the coupling knob g (INFO-040).
  (3) diffusive correlation -> high correlation but MI stays OUT of the null
      (not structured) (the INFO-041 control).
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from odcore.null_extract import analyze_coupling, extract_null, EQ_QUAD
from odcore import synthetic as syn


def _quad_cos(null0: np.ndarray) -> float:
    """|cos| between null0's (H_a^2,H_b^2,H_a*H_b) part and the (-1,-1,+2)/sqrt6 attractor."""
    sub = null0[[2, 3, 4]]
    n = np.linalg.norm(sub)
    if n == 0:
        return 0.0
    sub = sub / n
    ref = EQ_QUAD[[2, 3, 4]]
    ref = ref / np.linalg.norm(ref)
    return abs(float(sub @ ref))


def test_equal_entropy_attractor():
    M = syn.ensemble_independent(n_windows=120, win=40, seed=1)
    null = extract_null(M)
    assert _quad_cos(null.null0) >= 0.97, _quad_cos(null.null0)
    v = analyze_coupling(M)
    assert not v.structured, v.reason  # independence is NOT structured coupling


def test_native_coupling_detected():
    M = syn.ensemble_native_coupled(n_windows=120, win=40, g=1.5, seed=2)
    v = analyze_coupling(M)
    assert v.structured, v.reason
    assert v.mi_frac >= 0.4, v.mi_frac


def test_diffusive_correlation_not_structured():
    M = syn.ensemble_diffusive(n_windows=120, win=40, seed=3)
    v = analyze_coupling(M)
    assert not v.structured, f"diffusive flagged structured: {v}"


def test_strength_slope_monotone_in_g():
    slopes = []
    for g in (0.25, 0.75, 1.5):
        M = syn.ensemble_native_coupled(n_windows=120, win=40, g=g, seed=7)
        slopes.append(analyze_coupling(M).mi_slope)
    assert slopes[0] < slopes[1] < slopes[2], slopes


if __name__ == "__main__":
    print("== equal-entropy attractor (independent symmetric) ==")
    M = syn.ensemble_independent(120, 40, seed=1)
    null = extract_null(M)
    v = analyze_coupling(M)
    print(f"  quad |cos| to (-1,-1,2)/sqrt6: {_quad_cos(null.null0):.4f}")
    print(f"  verdict: structured={v.structured} mi_frac={v.mi_frac:.3f} "
          f"eq={v.eq_entropy_frac:.3f} mi_var={v.mi_var:.2e} :: {v.reason}")

    print("== native structured coupling (g=1.5) ==")
    M = syn.ensemble_native_coupled(120, 40, g=1.5, seed=2)
    v = analyze_coupling(M)
    print(f"  verdict: structured={v.structured} mi_frac={v.mi_frac:.3f} "
          f"slope={v.mi_slope:.3f} r2={v.mi_slope_r2:.3f} :: {v.reason}")

    print("== diffusive correlation ==")
    M = syn.ensemble_diffusive(120, 40, seed=3)
    v = analyze_coupling(M)
    print(f"  verdict: structured={v.structured} mi_frac={v.mi_frac:.3f} "
          f"slope={v.mi_slope:.3f} r2={v.mi_slope_r2:.3f} mi_var={v.mi_var:.2e} :: {v.reason}")

    print("== slope monotone in g ==")
    for g in (0.25, 0.75, 1.5):
        M = syn.ensemble_native_coupled(120, 40, g=g, seed=7)
        vv = analyze_coupling(M)
        print(f"  g={g}: slope={vv.mi_slope:.3f} mi_frac={vv.mi_frac:.3f}")
