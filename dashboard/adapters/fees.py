"""Fill/fee adapter - wraps research/kalshi/kalshi_fill_model.py (read-only import).

MAKER-FIRST framing is doctrine (feed M verdict): maker fee 0 / spread earned, but the
resting-fill probability is a LIVE question with no historical claim - every maker figure
is a BOUND and is labeled as such. Taker numbers are the conservative crossing model."""
from __future__ import annotations

import sys

from . import paths


def _model():
    if paths.KALSHI_RESEARCH not in sys.path:
        sys.path.insert(0, paths.KALSHI_RESEARCH)
    import kalshi_fill_model
    return kalshi_fill_model


def round_trip(p_entry: float, p_exit: float, spread_entry: float, spread_exit: float) -> dict:
    m = _model()
    taker = m.round_trip_taker_cost(p_entry, p_exit, spread_entry, spread_exit)
    return {
        "taker": taker,
        "taker_fee_entry": round(m.taker_fee_per_contract(p_entry), 4),
        "taker_fee_exit": round(m.taker_fee_per_contract(p_exit), 4),
        "maker": {"fees": 0.0, "note": m.maker_bound_note()},
        "framing": "MAKER-FIRST per feed M: taker reserved for the >=4c fast-tail class",
    }
