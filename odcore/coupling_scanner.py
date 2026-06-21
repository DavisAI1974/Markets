"""
odcore/coupling_scanner.py — rank channel pairs by structured coupling; emit decoupling events.

RECONSTRUCTED-FROM-CLAUDE.md. Cites:
  - Coupling discriminator + INFO-041 control (structured vs mere correlation): null_extract.
  - Tautology-killing circular-shift null (INFO-066 l.913): a coupling claim is only real if
    its excess survives circular-shifting one channel (kills the instantaneous pairing while
    preserving smoothness + shared factors). Used here for both the lead-lag coupling and the
    operator-structure excess.
  - Lead-lag (raw cross-cov over lag): leadlag.py (the S19 right tool).
  - Decoupling -> first-class signal: a previously-coupled pair whose coupling collapses is a
    tradeable dislocation (analogous to operator_drift_alarm's snapshot diff).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

from .operators import windowed_operator_matrix, COL
from .null_extract import analyze_coupling
from .dipole_predictor import fit_algebraic_dipole
from .leadlag import detect_leadlag, cross_correlation


@dataclass
class PairScore:
    name: str
    pair_kind: str
    n_windows: int
    structured: bool
    mi_frac: float
    chem_frac: float
    dipole_a: float
    dipole_b: float
    dipole_c: float
    dipole_r2: float
    leadlag: int
    leadlag_cc: float
    coupling_z: float       # lead-lag peak vs circular-shift null (tautology-killing)
    structure_excess: float  # operator-structure metric: real minus circular-shift null mean
    structure_z: float
    rank_score: float


def _structure_metric(M: np.ndarray) -> float:
    """Scalar 'how much structured coupling' from an operator matrix: the larger of the
    MI-in-null fraction (gated by a real MI~H_a slope fit) and the chem residual fraction."""
    v = analyze_coupling(M)
    mi_term = v.mi_frac if v.mi_slope_r2 >= 0.3 else 0.0
    return max(mi_term, v.chem_residual_frac)


def tautology_structure_null(a: np.ndarray, b: np.ndarray, window: int, stride: int,
                             n_null: int = 20, seed: int = 0) -> tuple[float, float, float]:
    """Circular-shift null on the operator-structure metric (INFO-066).

    Returns (excess, z, real_metric): excess = real - null_mean. A genuine structured
    coupling has excess > 0 at high z; a tautology has excess ~ 0.
    """
    M = windowed_operator_matrix(a, b, window=window, stride=stride)
    if M.shape[0] < 30:
        return 0.0, 0.0, 0.0
    real = _structure_metric(M)
    rng = np.random.default_rng(seed)
    n = min(a.size, b.size)
    nulls = np.empty(n_null)
    for i in range(n_null):
        shift = int(rng.integers(window, n - window))
        Mn = windowed_operator_matrix(a[:n], np.roll(b[:n], shift), window=window, stride=stride)
        nulls[i] = _structure_metric(Mn) if Mn.shape[0] >= 30 else 0.0
    mu, sd = float(nulls.mean()), float(nulls.std())
    z = (real - mu) / sd if sd > 1e-12 else 0.0
    return real - mu, z, real


def score_pair(a: np.ndarray, b: np.ndarray, name: str, pair_kind: str,
               window: int = 40, stride: int = 10, max_lag: int = 15,
               struct_null: bool = True, seed: int = 0) -> PairScore | None:
    M = windowed_operator_matrix(a, b, window=window, stride=stride)
    if M.shape[0] < 30:
        return None
    v = analyze_coupling(M)
    fit = fit_algebraic_dipole(M)
    ll = detect_leadlag(a, b, max_lag=max_lag, n_null=100, seed=seed)
    if struct_null:
        excess, sz, _ = tautology_structure_null(a, b, window, stride, n_null=20, seed=seed)
    else:
        excess, sz = 0.0, 0.0
    # rank: structured coupling that survives the tautology null, weighted by lead-lag
    # significance and the dipole's quadratic (chem) content
    rank = (max(v.mi_frac if v.mi_slope_r2 >= 0.3 else 0.0, v.chem_residual_frac)
            * max(0.0, sz) * (1.0 + abs(fit.c)))
    return PairScore(
        name=name, pair_kind=pair_kind, n_windows=int(M.shape[0]),
        structured=bool(v.structured), mi_frac=v.mi_frac, chem_frac=v.chem_residual_frac,
        dipole_a=fit.a, dipole_b=fit.b, dipole_c=fit.c, dipole_r2=fit.r2,
        leadlag=ll.lag, leadlag_cc=ll.cc, coupling_z=ll.z,
        structure_excess=excess, structure_z=sz, rank_score=rank)


# ---------------------------------------------------------------------------
# Decoupling detector — rolling lag-0 coupling, flag collapses
# ---------------------------------------------------------------------------

@dataclass
class DecouplingEvent:
    index: int        # window index where the collapse fired
    cc: float         # coupling at the event
    baseline: float   # rolling baseline coupling before the event
    severity: str     # info | warning | critical


def rolling_coupling(a: np.ndarray, b: np.ndarray, win: int = 600, step: int = 60) -> np.ndarray:
    """Lag-0 |cross-correlation| in a sliding window -> a coupling time series."""
    a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float)
    n = min(a.size, b.size)
    out = []
    for s in range(0, n - win + 1, step):
        _, cc = cross_correlation(a[s:s + win], b[s:s + win], max_lag=0)
        out.append(abs(float(cc[0])))
    return np.asarray(out)


def detect_decoupling(cc_series: np.ndarray, lookback: int = 20,
                      drop_k: float = 2.5) -> list[DecouplingEvent]:
    """Flag windows where coupling collapses below its rolling baseline by drop_k sigma."""
    events: list[DecouplingEvent] = []
    for i in range(lookback, len(cc_series)):
        past = cc_series[i - lookback:i]
        mu, sd = float(past.mean()), float(past.std())
        if sd < 1e-9:
            continue
        drop = (mu - cc_series[i]) / sd
        if drop >= drop_k:
            sev = "critical" if drop >= 4 else ("warning" if drop >= 3 else "info")
            events.append(DecouplingEvent(index=i, cc=float(cc_series[i]),
                                          baseline=mu, severity=sev))
    return events
