"""Immutable Kalshi venue contracts."""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any

from ..common.approval import ApprovedOrder
from ..common.hashing import hash_payload, to_primitive
from ..common.models import IdentityStatus, TradeDecision


class OutcomeExposure(str, enum.Enum):
    YES = "YES"
    NO = "NO"


class KalshiOrderStyle(str, enum.Enum):
    LIMIT_GTC = "LIMIT_GTC"
    IMMEDIATE_OR_CANCEL = "IMMEDIATE_OR_CANCEL"
    FILL_OR_KILL = "FILL_OR_KILL"


@dataclass(frozen=True)
class ContractMapping:
    mapping_id: str
    ticker: str
    event_ticker: str
    series_ticker: str
    yes_meaning: str
    no_meaning: str
    settlement_condition: str
    settlement_source: str
    settlement_field: str
    settlement_time: str
    close_time: str
    expiration_time: str
    underlying: str
    compatible_horizons: tuple[str, ...]
    enabled_routes: tuple[str, ...]
    version: str

    def as_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True)
class ObservedContract:
    ticker: str | None
    event_ticker: str | None
    series_ticker: str | None
    yes_meaning: str | None
    no_meaning: str | None
    settlement_condition: str | None
    settlement_source: str | None
    settlement_field: str | None
    settlement_time: str | None
    close_time: str | None
    expiration_time: str | None
    raw_source_hash: str


@dataclass(frozen=True)
class ContractResolution:
    status: IdentityStatus
    mapping: ContractMapping | None
    reasons: tuple[str, ...]
    identity_hash: str

    def as_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True)
class KalshiMarketSnapshot:
    snapshot_id: str
    captured_at: str
    ticker: str
    status: str
    yes_bid: float | None
    yes_ask: float | None
    no_bid: float | None
    no_ask: float | None
    book_hash: str
    volume: float | None
    open_interest: float | None
    close_time: str
    expiration_time: str
    contract_identity_hash: str
    raw_source_hash: str
    source: str = "KALSHI"

    def as_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True)
class KalshiEntry:
    max_price: float
    requested_count: float
    order_style: KalshiOrderStyle


@dataclass(frozen=True)
class KalshiTradeIntent:
    trade_intent_id: str
    forecast_id: str | None
    snapshot_id: str
    ticker: str
    decision: TradeDecision
    outcome_exposure: OutcomeExposure | None
    entry: KalshiEntry | None
    expected_edge: float | None
    confidence: float | None
    expected_lifespan: str | None
    invalidation: tuple[str, ...]
    exit_thesis: tuple[str, ...]
    expires_at: str
    trader_reasoning_hash: str
    stand_down_reason: str | None
    execution_authority: bool = False

    def as_dict(self) -> dict[str, Any]:
        return to_primitive(self)

    @property
    def intent_hash(self) -> str:
        return hash_payload(self.as_dict())


@dataclass(frozen=True)
class KalshiRiskDecision:
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
