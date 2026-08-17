"""Immutable cross-venue contracts. No object in this module can mutate Frankie 1."""
from __future__ import annotations

import dataclasses
import enum
from dataclasses import dataclass
from typing import Any

from .hashing import to_primitive


class TradeDecision(str, enum.Enum):
    TRADE = "TRADE"
    STAND_DOWN = "STAND_DOWN"


class IdentityStatus(str, enum.Enum):
    EXACT = "EXACT"
    MISMATCH = "MISMATCH"
    UNKNOWN = "UNKNOWN"


class OrderState(str, enum.Enum):
    INTENT_CREATED = "INTENT_CREATED"
    RISK_PENDING = "RISK_PENDING"
    RISK_REJECTED = "RISK_REJECTED"
    RISK_APPROVED = "RISK_APPROVED"
    SUBMIT_PENDING = "SUBMIT_PENDING"
    SUBMITTED = "SUBMITTED"
    RESTING = "RESTING"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    POSITION_OPEN = "POSITION_OPEN"
    EXIT_INTENT = "EXIT_INTENT"
    EXIT_ORDER = "EXIT_ORDER"
    POSITION_CLOSED = "POSITION_CLOSED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    ERROR_SAFE = "ERROR_SAFE"
    SETTLED = "SETTLED"


@dataclass(frozen=True)
class Forecast:
    direction: str | None
    expected_path: tuple[Any, ...]
    expected_terminal_move: float | None
    confidence: float | None
    horizon: str | None


@dataclass(frozen=True)
class ChainState:
    mechanism: str | None
    depth: int | None
    origin_id: str | None
    polarity: str | None
    expected_lifespan: str | None
    invalidation: tuple[str, ...]


@dataclass(frozen=True)
class ForecastProvenance:
    forecast_hash: str
    brain_version: str | None
    source_hashes: tuple[str, ...]


@dataclass(frozen=True)
class ForecastEnvelope:
    forecast_id: str | None
    forecaster: str
    forecaster_version: str | None
    generated_at: str | None
    information_cutoff: str | None
    underlying: str | None
    forecast: Forecast
    chain_state: ChainState
    provenance: ForecastProvenance

    def as_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True)
class HealthSnapshot:
    data_feed_ok: bool
    broker_api_ok: bool
    captured_at: str
    details_hash: str


@dataclass(frozen=True)
class PortfolioSnapshot:
    current_position: float
    market_exposure: float
    portfolio_exposure: float
    daily_realized_pnl: float
    open_order_count: int
    concurrent_market_count: int
    account_eligible: bool = True
    available_margin: float | None = None


def as_dict(value: Any) -> dict[str, Any]:
    if not dataclasses.is_dataclass(value):
        raise TypeError("value must be a dataclass")
    result = to_primitive(value)
    if not isinstance(result, dict):
        raise TypeError("dataclass did not serialize to an object")
    return result
