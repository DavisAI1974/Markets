"""Deterministic Kalshi Risk Governor. No model output can waive these gates."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Mapping

from ..common.approval import _issue_approved_order
from ..common.hashing import hash_payload, new_id, parse_timestamp, utc_now
from ..common.ledger import ImmutableTradingLedger
from ..common.models import ForecastEnvelope, IdentityStatus, TradeDecision
from ..common.risk import (
    CommonRiskConfig, RiskContext, common_gate_reasons, require_config_keys,
)
from .models import (
    ContractResolution, KalshiMarketSnapshot, KalshiOrderStyle, KalshiRiskDecision,
    KalshiTradeIntent, OutcomeExposure,
)


@dataclass(frozen=True)
class KalshiRiskConfig:
    common: CommonRiskConfig
    min_contract_price: float
    max_contract_price: float
    max_order_notional: float
    allowed_routes: tuple[str, ...]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "KalshiRiskConfig":
        common_keys = tuple(CommonRiskConfig.__dataclass_fields__)
        common_raw = raw.get("common")
        if not isinstance(common_raw, dict):
            raise ValueError("Kalshi risk config requires a common object")
        require_config_keys(common_raw, common_keys, label="Kalshi common risk config")
        venue_keys = ("min_contract_price", "max_contract_price", "max_order_notional", "allowed_routes")
        require_config_keys(dict(raw), venue_keys, label="Kalshi risk config")
        return cls(
            common=CommonRiskConfig(**{key: common_raw[key] for key in common_keys}),
            min_contract_price=float(raw["min_contract_price"]),
            max_contract_price=float(raw["max_contract_price"]),
            max_order_notional=float(raw["max_order_notional"]),
            allowed_routes=tuple(str(route) for route in raw["allowed_routes"]),
        )


class KalshiRiskGovernor:
    def __init__(
        self,
        config: KalshiRiskConfig,
        *,
        ledger: ImmutableTradingLedger | None = None,
    ) -> None:
        self.config = config
        self.config_hash = hash_payload(config)
        self.ledger = ledger

    def evaluate(
        self,
        *,
        intent: KalshiTradeIntent,
        forecast: ForecastEnvelope,
        snapshot: KalshiMarketSnapshot,
        resolution: ContractResolution,
        context: RiskContext,
        route: str,
        correlation_id: str,
    ) -> KalshiRiskDecision:
        decision_id = new_id("kalshi-risk")
        reasons: list[str] = []
        if self.ledger is not None and self.ledger.contains_source("risk_decisions", intent.trade_intent_id):
            reasons.append("DUPLICATE_INTENT")
        entry = intent.entry
        if intent.decision is not TradeDecision.TRADE:
            reasons.append("INTENT_IS_STAND_DOWN")
        if intent.execution_authority:
            reasons.append("INTENT_ILLEGALLY_CLAIMS_EXECUTION_AUTHORITY")
        if resolution.status is not IdentityStatus.EXACT or resolution.mapping is None:
            reasons.append("CONTRACT_IDENTITY_NOT_EXACT")
        if snapshot.contract_identity_hash != resolution.identity_hash:
            reasons.append("SNAPSHOT_CONTRACT_IDENTITY_CHANGED")
        if intent.forecast_id is None or intent.forecast_id != forecast.forecast_id:
            reasons.append("FORECAST_ID_MISSING_OR_MISMATCH")
        if intent.snapshot_id != snapshot.snapshot_id:
            reasons.append("SNAPSHOT_ID_MISMATCH")
        if intent.ticker != snapshot.ticker:
            reasons.append("TICKER_MISMATCH")
        if not snapshot.raw_source_hash or not snapshot.book_hash:
            reasons.append("SNAPSHOT_PROVENANCE_MISSING")
        if route not in self.config.allowed_routes:
            reasons.append("ROUTE_NOT_RISK_APPROVED")
        if resolution.mapping is not None and route not in resolution.mapping.enabled_routes:
            reasons.append("ROUTE_NOT_ENABLED_FOR_CONTRACT")
        if entry is None or intent.outcome_exposure is None:
            reasons.append("TRADE_FIELDS_MISSING")
            price = 0.0
            quantity = 0.0
        else:
            price = entry.max_price
            quantity = entry.requested_count
            if not self.config.min_contract_price <= price <= self.config.max_contract_price:
                reasons.append("PRICE_SANITY")
            if price * quantity > self.config.max_order_notional:
                reasons.append("ORDER_NOTIONAL_LIMIT")
        direction = 1.0 if intent.outcome_exposure is OutcomeExposure.YES else -1.0
        projected_position = context.portfolio.current_position + direction * quantity
        projected_market_exposure = context.portfolio.market_exposure + price * quantity
        projected_portfolio_exposure = context.portfolio.portfolio_exposure + price * quantity
        reasons.extend(common_gate_reasons(
            config=self.config.common,
            context=context,
            forecast_generated_at=forecast.generated_at,
            snapshot_captured_at=snapshot.captured_at,
            intent_expires_at=intent.expires_at,
            market_open=snapshot.status.lower() == "open",
            quantity=quantity,
            projected_position=projected_position,
            projected_market_exposure=projected_market_exposure,
            projected_portfolio_exposure=projected_portfolio_exposure,
        ))
        unique_reasons = tuple(dict.fromkeys(reasons))
        approved = None
        if not unique_reasons and entry is not None and intent.outcome_exposure is not None:
            client_order_id = f"tfk-{intent.trade_intent_id[-28:]}"
            api_price = entry.max_price if intent.outcome_exposure is OutcomeExposure.YES else 1.0 - entry.max_price
            time_in_force = {
                KalshiOrderStyle.LIMIT_GTC: "good_till_canceled",
                KalshiOrderStyle.IMMEDIATE_OR_CANCEL: "immediate_or_cancel",
                KalshiOrderStyle.FILL_OR_KILL: "fill_or_kill",
            }[entry.order_style]
            expires = parse_timestamp(intent.expires_at)
            payload = {
                "ticker": intent.ticker,
                "client_order_id": client_order_id,
                "side": "bid" if intent.outcome_exposure is OutcomeExposure.YES else "ask",
                "count": f"{entry.requested_count:.2f}",
                "price": f"{api_price:.4f}",
                "time_in_force": time_in_force,
                "self_trade_prevention_type": "taker_at_cross",
                "cancel_order_on_pause": True,
                "post_only": False,
                "reduce_only": False,
                "exchange_index": 0,
                "outcome_exposure": intent.outcome_exposure.value,
                "economic_max_price": f"{entry.max_price:.4f}",
            }
            if time_in_force == "good_till_canceled" and expires is not None:
                payload["expiration_time"] = int(expires.timestamp())
            approved = _issue_approved_order(
                risk_decision_id=decision_id,
                venue="KALSHI_EVENT",
                route=route,
                client_order_id=client_order_id,
                intent_id=intent.trade_intent_id,
                intent_hash=intent.intent_hash,
                payload=payload,
            )
        result = KalshiRiskDecision(
            risk_decision_id=decision_id,
            intent_id=intent.trade_intent_id,
            decision="APPROVE" if approved else "REJECT",
            reasons=unique_reasons,
            config_hash=self.config_hash,
            created_at=utc_now().isoformat().replace("+00:00", "Z"),
            approved_order=approved,
        )
        if self.ledger is not None:
            self.ledger.append(
                "risk_decisions", result.as_dict(), correlation_id=correlation_id,
                source_id=intent.trade_intent_id, venue="KALSHI",
            )
        return result
