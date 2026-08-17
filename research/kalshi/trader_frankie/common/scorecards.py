"""Separate forecast-skill and venue-trading scorecards plus deterministic diagnosis."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .hashing import to_primitive


@dataclass(frozen=True)
class ForecasterScorecardEntry:
    forecast_id: str
    direction_correct: bool | None
    path_score: float | None
    magnitude_error: float | None
    timing_error_seconds: float | None
    chain_correct: bool | None
    lifespan_error_seconds: float | None
    invalidation_correct: bool | None

    def as_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True)
class TraderScorecardEntry:
    trade_intent_id: str
    venue: str
    contract_or_instrument_mapping_correct: bool
    decision_correct: bool | None
    entry_quality: float | None
    exit_quality: float | None
    edge_captured: float | None
    slippage: float | None
    fill_quality: float | None
    realized_pnl: float | None

    def as_dict(self) -> dict[str, Any]:
        return to_primitive(self)


def diagnose(*, frankie_correct: bool, trader_stood_down: bool, trader_profitable: bool | None) -> str:
    if trader_stood_down:
        return "GOOD_TRADING_STAND_DOWN" if not frankie_correct else "CORRECT_NO_VALUE_STAND_DOWN"
    if trader_profitable:
        return "MONETIZED_FORECAST"
    if frankie_correct:
        return "TRADING_OR_EXECUTION_PROBLEM"
    return "FORECAST_PROBLEM"
