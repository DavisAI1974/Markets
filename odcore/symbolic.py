"""
odcore/symbolic.py — PySR (Julia backend) symbolic regression: DISCOVER the
dipole / coupling / MI-vs-H equation from raw crypto operator data.

RECONSTRUCTED-FROM-CLAUDE.md (the per-session research workflow; would-be port of
s12_consolidate_per_domain.py). Cites:
  - PySR (Brunton/Cao/Liu/Tegmark/Cranmer family) with the extended operator set
    {+,-,*,/,square,cube,exp,log,sqrt} on per-domain ensemble-H data; families land
    at complexity 5-6 (INFO-025 l.615). PySR 1.5.10 (l.2044).
  - "same PySR-from-raw-data machinery" applied to markets (l.472/567): re-derive the
    governing equation WITHOUT assuming it (Piece 1).
  - Acceptance discipline: a discovered form is a CANDIDATE, promoted only on >=3-seed
    <5% coefficient reproduction + walk-forward + tautology null (Result Discipline l.143).
  - Fallback: when Julia/PySR is unavailable (l.2057), callers fall back to the
    reconstructed numpy forms (dipole_predictor.fit_algebraic_dipole).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .operators import COL

EXTENDED_UNARY = ["square", "cube", "exp", "log", "sqrt"]
EXTENDED_BINARY = ["+", "-", "*", "/"]


def pysr_available() -> bool:
    try:
        import pysr  # noqa: F401
        return True
    except Exception:
        return False


@dataclass
class DiscoveredEquation:
    target: str
    features: list[str]
    best_equation: str
    best_complexity: int
    best_loss: float
    best_score: float
    pareto: list[dict]


def _regressor(niterations: int, maxsize: int, seed: int):
    from pysr import PySRRegressor
    return PySRRegressor(
        niterations=niterations,
        maxsize=maxsize,
        binary_operators=list(EXTENDED_BINARY),
        unary_operators=list(EXTENDED_UNARY),
        elementwise_loss="loss(p, t) = (p - t)^2",
        model_selection="best",
        populations=15,
        progress=False,
        verbosity=0,
        random_state=seed,
        deterministic=True,
        parallelism="serial",
        temp_equation_file=True,
    )


def discover(M: np.ndarray, target: str, features: list[str],
             niterations: int = 40, maxsize: int = 12, seed: int = 0) -> DiscoveredEquation:
    """Run PySR to discover target ~ f(features) over the windowed operator ensemble."""
    M = np.asarray(M, dtype=float)
    y = M[:, COL[target]]
    X = np.column_stack([M[:, COL[f]] for f in features])
    model = _regressor(niterations, maxsize, seed)
    model.fit(X, y, variable_names=[f.replace("*", "x").replace("^", "p") for f in features])
    eqs = model.equations_
    best_idx = int(eqs["score"].idxmax())
    pareto = [
        {"complexity": int(r.complexity), "loss": float(r.loss),
         "score": float(r.score), "equation": str(r.equation)}
        for r in eqs.itertuples()
    ]
    return DiscoveredEquation(
        target=target, features=features,
        best_equation=str(eqs.loc[best_idx, "equation"]),
        best_complexity=int(eqs.loc[best_idx, "complexity"]),
        best_loss=float(eqs.loc[best_idx, "loss"]),
        best_score=float(eqs.loc[best_idx, "score"]),
        pareto=pareto,
    )
