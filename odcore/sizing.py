"""
odcore/sizing.py — OD-native position sizing (NOT textbook Kelly).

Per Greg: do not treat textbook Kelly as the gold standard; size from OUR measured pieces.
The size fraction is driven by OD-native confidence — the chemistry RESIDUAL-FRACTION strength
(INFO-044, the Brusselator-B analog of coupling strength), the live algebraic-dipole surface
R^2 (how cleanly the dipole fits now), and the lead-lag stability (how reliable the cross-channel
timing is) — then calibrated to the MEASURED walk-forward edge so size tracks realized OOS edge,
not a theoretical constant. Circuit breakers (elsewhere) are guardrails only.
"""

from __future__ import annotations

from dataclasses import dataclass


def _clip01(x: float) -> float:
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


@dataclass
class SizingInputs:
    residual_fraction: float   # chem strength meter in [0,1] (INFO-044)
    dipole_r2: float           # live algebraic-dipole fit quality in [0,1]
    leadlag_stability: float   # |cc| at the peak lag in [0,1]
    walkforward_edge: float    # measured OOS edge (e.g. net return per trade), >=0 scales up


def od_size_fraction(inp: SizingInputs, w_residual: float = 0.5, w_dipole: float = 0.3,
                     w_leadlag: float = 0.2, edge_scale: float = 50.0) -> float:
    """Confidence in [0,1] from the OD measures, scaled by the measured edge.

    edge_scale maps a per-trade edge (in return units) to a multiplier ~1 at a meaningful
    edge; a non-positive measured edge -> zero size (don't trade a signal with no proven edge).
    """
    confidence = (w_residual * _clip01(inp.residual_fraction)
                  + w_dipole * _clip01(inp.dipole_r2)
                  + w_leadlag * _clip01(inp.leadlag_stability))
    edge_mult = _clip01(inp.walkforward_edge * edge_scale)
    return _clip01(confidence * edge_mult)


def position_notional(equity: float, size_fraction: float, max_position_usd: float,
                      floor_usd: float = 0.0) -> float:
    """Translate the OD size fraction into a capped notional.

    size scales UP when OD confidence + measured edge are high, DOWN as they weaken (so a
    losing streak, which erodes the walk-forward edge, shrinks size automatically)."""
    notional = size_fraction * max_position_usd
    if notional < floor_usd:
        return 0.0
    return min(notional, max_position_usd)


def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Provided for COMPARISON only (not the sizing rule). f* = p/|loss| - (1-p)/win."""
    if avg_win <= 0 or avg_loss >= 0:
        return 0.0
    b = avg_win / abs(avg_loss)
    return max(0.0, (win_rate * (b + 1) - 1) / b)
