"""
odcore/null_extract.py — centered-SVD null extraction + coupling decomposition.

RECONSTRUCTED-FROM-CLAUDE.md (would-be port of s12_coupling_decomposition.py /
s13_chemistry_residual.py). Cites (CLAUDE (5).md):
  - Center the 6 columns (NOT z-score: scale is a units choice, MI is the invariant,
    INFO-051 l.1051), SVD, smallest right-singular vector = null[0] (INFO-012 l.597;
    INFO-022 rank-3 null l.609).
  - The (-1,-1,+2)/sqrt(6) equal-entropy attractor in (H_a^2,H_b^2,H_a*H_b) is a GEOMETRIC
    ARTIFACT / baseline to project out, not signal (INFO-012/036/051).
  - Coupling discriminator: decompose null[0] into {equal-entropy, MI, residual} axes.
    MI entering the null => STRUCTURED, law-like coupling (INFO-040 l.289-373). The
    INFO-041 control (l.375-390): generic correlation creates MI but it stays OUT of the
    null -> discriminates structured coupling from mere correlation.
  - Two strength meters: biology = MI-vs-H_a SLOPE (MI ~= 0.28*H_a; INFO-040 l.340);
    chemistry = RESIDUAL-FRACTION of the fixed relation
    0.54*H_a + 0.54*H_b + 0.32*H_a^2 - 0.55*H_b^2 ~ 0 (INFO-040 l.298 / INFO-044 l.1495).
  - singular_gap = null-direction confidence (INFO-024 l.613).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .operators import COL

# ---- Fixed axes in the 6-basis [H_a, H_b, H_a^2, H_b^2, H_a*H_b, MI] ----

def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v

# equal-entropy identity: linear (H_a - H_b) and quadratic (-1,-1,+2)/sqrt6 attractor
EQ_LINEAR = _unit(np.array([1.0, -1.0, 0.0, 0.0, 0.0, 0.0]))
EQ_QUAD = _unit(np.array([0.0, 0.0, -1.0, -1.0, 2.0, 0.0]))
# MI coupling axis
MI_AXIS = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 1.0])
# chemistry residual relation 0.54 H_a + 0.54 H_b + 0.32 H_a^2 - 0.55 H_b^2 ~ 0
CHEM_RESIDUAL = _unit(np.array([0.54, 0.54, 0.32, -0.55, 0.0, 0.0]))


@dataclass
class NullResult:
    null0: np.ndarray            # smallest right-singular vector (6,)
    singular_values: np.ndarray  # all 6, descending
    singular_gap: float          # (s[-2]-s[-1]) / s[0]; larger => better-defined null


def extract_null(M: np.ndarray) -> NullResult:
    """Center columns (no z-score), SVD, return the smallest-singular-value direction."""
    M = np.asarray(M, dtype=float)
    if M.ndim != 2 or M.shape[0] < 2 or M.shape[1] != 6:
        raise ValueError("operator matrix must be (n_windows>=2, 6)")
    Mc = M - M.mean(axis=0, keepdims=True)
    # right-singular vectors are rows of Vt; smallest singular value is last
    _, s, Vt = np.linalg.svd(Mc, full_matrices=False)
    null0 = Vt[-1]
    s = np.asarray(s, dtype=float)
    gap = float((s[-2] - s[-1]) / s[0]) if s[0] > 0 and s.size >= 2 else 0.0
    return NullResult(null0=null0, singular_values=s, singular_gap=gap)


@dataclass
class CouplingDecomp:
    eq_entropy_frac: float   # fraction of null[0] energy on the equal-entropy identity
    mi_frac: float           # fraction on the MI coupling axis  (high => STRUCTURED coupling)
    residual_frac: float     # remainder (chemistry-type coupling lives here)
    chem_residual_frac: float  # fraction specifically along the chemistry residual relation
    structured: bool         # mi_frac high OR chem_residual_frac high, gated by caller thresholds


def decompose_coupling(null0: np.ndarray, mi_threshold: float = 0.5,
                       chem_threshold: float = 0.15) -> CouplingDecomp:
    """Decompose null[0] onto {equal-entropy, MI, residual} axes (INFO-040).

    Fractions are squared projections of the unit null vector. mi_frac high =>
    biology-type structured coupling; chem_residual_frac high => chemistry-type
    (partial, residual) coupling. The INFO-041 control is enforced upstream (generic
    correlation does not raise mi_frac because MI never enters the low-variance null).
    """
    v = _unit(np.asarray(null0, dtype=float).ravel())
    p_lin = float(v @ EQ_LINEAR)
    p_quad = float(v @ EQ_QUAD)
    p_mi = float(v @ MI_AXIS)
    eq_frac = p_lin ** 2 + p_quad ** 2
    mi_frac = p_mi ** 2
    resid_frac = max(0.0, 1.0 - eq_frac - mi_frac)
    chem_frac = float(v @ CHEM_RESIDUAL) ** 2
    structured = (mi_frac >= mi_threshold) or (chem_frac >= chem_threshold)
    return CouplingDecomp(eq_entropy_frac=eq_frac, mi_frac=mi_frac,
                          residual_frac=resid_frac, chem_residual_frac=chem_frac,
                          structured=structured)


@dataclass
class StrengthReadout:
    mi_slope: float    # biology readout: slope of MI ~ slope*H_a
    mi_slope_r2: float
    chem_residual_frac: float  # chemistry readout: residual-fraction (Brusselator-B analog)


def coupling_strength(M: np.ndarray) -> StrengthReadout:
    """Two OD-native strength meters from the windowed operator ensemble.

    biology  = slope of the linear fit MI ~ slope*H_a + b  (INFO-040: MI ~= 0.28*H_a;
               slope rises monotonically with the coupling knob g).
    chemistry = residual-fraction of null[0] along the fixed chemistry relation
               (INFO-044: rises monotonically with the Brusselator-B knob).
    """
    M = np.asarray(M, dtype=float)
    Ha = M[:, COL["H_a"]]
    mi = M[:, COL["MI"]]
    # least-squares slope of MI on H_a
    A = np.column_stack([Ha, np.ones_like(Ha)])
    coef, *_ = np.linalg.lstsq(A, mi, rcond=None)
    slope = float(coef[0])
    pred = A @ coef
    ss_res = float(np.sum((mi - pred) ** 2))
    ss_tot = float(np.sum((mi - mi.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
    chem_frac = decompose_coupling(extract_null(M).null0).chem_residual_frac
    return StrengthReadout(mi_slope=slope, mi_slope_r2=r2, chem_residual_frac=chem_frac)


@dataclass
class CouplingVerdict:
    structured: bool
    mi_frac: float
    chem_residual_frac: float
    eq_entropy_frac: float
    mi_slope: float
    mi_slope_r2: float
    mi_mean: float
    mi_var: float
    singular_gap: float
    reason: str


def analyze_coupling(M: np.ndarray, mi_threshold: float = 0.4,
                     chem_threshold: float = 0.20, slope_r2_floor: float = 0.30,
                     mi_var_floor: float = 1e-4, gap_floor: float = 1e-3) -> CouplingVerdict:
    """Full coupling verdict for a windowed operator ensemble (the INFO-040/041 process).

    Discriminates STRUCTURED coupling from mere correlation AND from the degenerate
    zero-coupling case:
      - native/structured coupling -> MI is a tight function of H_a, so (MI - slope*H_a)
        is a low-variance combination that enters the null => mi_frac high (INFO-040).
      - generic/diffusive correlation -> MI is high-variance and NOT a function of H_a,
        so it cannot sit in the low-variance null => mi_frac low (INFO-041 control).
      - independence -> MI ~ 0 constant; its column collapses and can masquerade as a
        null direction => guard with mi_var_floor (INFO-024 l.613).
    """
    M = np.asarray(M, dtype=float)
    null = extract_null(M)
    decomp = decompose_coupling(null.null0)
    strength = coupling_strength(M)
    mi = M[:, COL["MI"]]
    mi_mean, mi_var = float(mi.mean()), float(mi.var())

    if mi_var < mi_var_floor:
        return CouplingVerdict(False, decomp.mi_frac, decomp.chem_residual_frac,
                               decomp.eq_entropy_frac, strength.mi_slope,
                               strength.mi_slope_r2, mi_mean, mi_var,
                               null.singular_gap,
                               "MI variance collapsed (independence / degenerate; INFO-024)")

    mi_structured = (decomp.mi_frac >= mi_threshold and
                     strength.mi_slope_r2 >= slope_r2_floor)
    chem_structured = (decomp.chem_residual_frac >= chem_threshold and
                       null.singular_gap >= gap_floor)
    structured = mi_structured or chem_structured
    if mi_structured:
        reason = "MI in null + tight MI~H_a fit (biology-type structured coupling)"
    elif chem_structured:
        reason = "residual relation in null (chemistry-type partial coupling)"
    else:
        reason = "high-variance MI stays out of null (mere correlation; INFO-041)"
    return CouplingVerdict(structured, decomp.mi_frac, decomp.chem_residual_frac,
                           decomp.eq_entropy_frac, strength.mi_slope,
                           strength.mi_slope_r2, mi_mean, mi_var,
                           null.singular_gap, reason)
