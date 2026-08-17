"""Immutable tastytrade venue contracts."""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any

from ..common.approval import ApprovedOrder
from ..common.hashing import hash_payload, to_primitive
from ..common.models import IdentityStatus, TradeDecision


class InstrumentType(str, enum.Enum):
    FUTURE = "Future"
    FUTURE_OPTION = "Future Option"


class TastySide(str, enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True)
class InstrumentMapping:
    instrument_id: str
    symbol: str
    instrument_type: InstrumentType
    root_symbol: str
    product_code: str
    exchange: str
    underlying: str
    contract_multiplier: float
    tick_size: float
    expiration_time: str
    compatible_horizons: tuple[str, ...]
    enabled_routes: tuple[str, ...]
    version: str

    def as_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True)
class ObservedInstrument:
    symbol: str | None
    instrument_type: str | None
    root_symbol: str | None
    product_code: str | None
    exchange: str | None
    contract_multiplier: float | None
    tick_size: float | None
    expiration_time: str | None
    active: bool | None
    tradeable: bool | None
    raw_source_hash: str


@dataclass(frozen=True)
class InstrumentResolution:
    status: IdentityStatus
    mapping: InstrumentMapping | None
    reasons: tuple[str, ...]
    identity_hash: str

    def as_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True)
class TastyMarketSnapshot:
    snapshot_id: str
    captured_at: str
    instrument_id: str
    symbol: str
    instrument_type: InstrumentType
    session_status: str
    bid: float | None
    ask: float | None
    last: float | None
    required_margin: float | None
    expiration_time: str
    instrument_identity_hash: str
    raw_source_hash: str
    source: str

    def as_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True)
class TastyTradeIntent:
    trade_intent_id: str
    forecast_id: str | None
    snapshot_id: str
    instrument_id: str
    symbol: str
    instrument_type: InstrumentType
    side: TastySide | None
    quantity_requested: float | None
    entry_limit: float | None
    trade_or_stand_down: TradeDecision
    forecast_horizon: str | None
    expected_lifespan: str | None
    invalidation: tuple[str, ...]
    exit_thesis: tuple[str, ...]
    confidence: float | None
    expires_at: str
    reasoning_hash: str
    stand_down_reason: str | None
    execution_authority: bool = False

    def as_dict(self) -> dict[str, Any]:
        return to_primitive(self)

    @property
    def intent_hash(self) -> str:
        return hash_payload(self.as_dict())


@dataclass(frozen=True)
class TastyRiskDecision:
    risk_decision_id: str
    intent_id: str
    decision: str
    reasons: tuple[str, ...]
    config_hash: str
    created_at: str
    approved_order: ApprovedOrder | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "risk_decision_id": self.risk_decision_id,
            "intent_id": self.intent_id,
            "decision": self.decision,
            "reasons": list(self.reasons),
            "config_hash": self.config_hash,
            "created_at": self.created_at,
            "approved_order": self.approved_order.as_dict() if self.approved_order else None,
        }
