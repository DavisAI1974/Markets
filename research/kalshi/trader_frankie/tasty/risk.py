"""Deterministic tastytrade Risk Governor for futures and futures-option intents."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..common.approval import _issue_approved_order
from ..common.hashing import hash_payload, new_id, utc_now
from ..common.ledger import ImmutableTradingLedger
from ..common.models import ForecastEnvelope, IdentityStatus, TradeDecision
from ..common.risk import CommonRiskConfig, RiskContext, common_gate_reasons, require_config_keys
from .models import (
    InstrumentResolution, InstrumentType, TastyMarketSnapshot, TastyRiskDecision,
    TastySide, TastyTradeIntent,
)


@dataclass(frozen=True)
class TastyRiskConfig:
    common: CommonRiskConfig
    min_entry_price: float
    max_entry_price: float
    max_order_notional: float
    max_margin_per_order: float
    allowed_instrument_types: tuple[str, ...]
    allowed_market_data_sources: tuple[str, ...]
    allowed_routes: tuple[str, ...]
    require_sandbox_dry_run: bool

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "TastyRiskConfig":
        common_keys = tuple(CommonRiskConfig.__dataclass_fields__)
        common_raw = raw.get("common")
        if not isinstance(common_raw, dict):
            raise ValueError("Tasty risk config requires a common object")
        require_config_keys(common_raw, common_keys, label="Tasty common risk config")
        venue_keys = (
            "min_entry_price", "max_entry_price", "max_order_notional", "max_margin_per_order",
            "allowed_instrument_types", "allowed_market_data_sources", "allowed_routes",
            "require_sandbox_dry_run",
        )
        require_config_keys(dict(raw), venue_keys, label="Tasty risk config")
        return cls(
            common=CommonRiskConfig(**{key: common_raw[key] for key in common_keys}),
            min_entry_price=float(raw["min_entry_price"]),
            max_entry_price=float(raw["max_entry_price"]),
            max_order_notional=float(raw["max_order_notional"]),
            max_margin_per_order=float(raw["max_margin_per_order"]),
            allowed_instrument_types=tuple(str(v) for v in raw["allowed_instrument_types"]),
            allowed_market_data_sources=tuple(str(v) for v in raw["allowed_market_data_sources"]),
            allowed_routes=tuple(str(v) for v in raw["allowed_routes"]),
            require_sandbox_dry_run=bool(raw["require_sandbox_dry_run"]),
        )


class TastyRiskGovernor:
    def __init__(
        self,
        config: TastyRiskConfig,
        *,
        ledger: ImmutableTradingLedger | None = None,
    ) -> None:
        self.config = config
        self.config_hash = hash_payload(config)
        self.ledger = ledger

    def evaluate(
        self,
        *,
        intent: TastyTradeIntent,
        forecast: ForecastEnvelope,
        snapshot: TastyMarketSnapshot,
        resolution: InstrumentResolution,
        context: RiskContext,
        route: str,
        correlation_id: str,
    ) -> TastyRiskDecision:
        decision_id = new_id("tasty-risk")
        reasons: list[str] = []
        if self.ledger is not None and self.ledger.contains_source("risk_decisions", intent.trade_intent_id):
            reasons.append("DUPLICATE_INTENT")
        if intent.trade_or_stand_down is not TradeDecision.TRADE:
            reasons.append("INTENT_IS_STAND_DOWN")
        if intent.execution_authority:
            reasons.append("INTENT_ILLEGALLY_CLAIMS_EXECUTION_AUTHORITY")
        if resolution.status is not IdentityStatus.EXACT or resolution.mapping is None:
            reasons.append("INSTRUMENT_IDENTITY_NOT_EXACT")
        if snapshot.instrument_identity_hash != resolution.identity_hash:
            reasons.append("SNAPSHOT_INSTRUMENT_IDENTITY_CHANGED")
        if intent.forecast_id is None or intent.forecast_id != forecast.forecast_id:
            reasons.append("FORECAST_ID_MISSING_OR_MISMATCH")
        if intent.snapshot_id != snapshot.snapshot_id:
            reasons.append("SNAPSHOT_ID_MISMATCH")
        if intent.instrument_id != snapshot.instrument_id or intent.symbol != snapshot.symbol:
            reasons.append("INSTRUMENT_MISMATCH")
        if not snapshot.raw_source_hash:
            reasons.append("SNAPSHOT_PROVENANCE_MISSING")
        if not context.portfolio.account_eligible:
            reasons.append("ACCOUNT_NOT_TRADING_ELIGIBLE")
        if route not in self.config.allowed_routes:
            reasons.append("ROUTE_NOT_RISK_APPROVED")
        if resolution.mapping is not None and route not in resolution.mapping.enabled_routes:
            reasons.append("ROUTE_NOT_ENABLED_FOR_INSTRUMENT")
        if intent.instrument_type.value not in self.config.allowed_instrument_types:
            reasons.append("INSTRUMENT_TYPE_NOT_ALLOWED")
        if snapshot.source not in self.config.allowed_market_data_sources:
            reasons.append("MARKET_DATA_SOURCE_NOT_ALLOWED")
        if intent.side is None or intent.quantity_requested is None or intent.entry_limit is None:
            reasons.append("TRADE_FIELDS_MISSING")
            quantity = 0.0
            price = 0.0
        else:
            quantity = intent.quantity_requested
            price = intent.entry_limit
            if not self.config.min_entry_price <= price <= self.config.max_entry_price:
                reasons.append("PRICE_SANITY")
            executable_quote = snapshot.ask if intent.side is TastySide.LONG else snapshot.bid
            if executable_quote is None:
                reasons.append("EXECUTABLE_QUOTE_MISSING")
        multiplier = resolution.mapping.contract_multiplier if resolution.mapping else 0.0
        notional = price * quantity * multiplier
        if notional > self.config.max_order_notional:
            reasons.append("ORDER_NOTIONAL_LIMIT")
        required_margin = snapshot.required_margin
        if required_margin is None:
            reasons.append("MARGIN_REQUIREMENT_UNKNOWN")
        else:
            total_margin = required_margin * quantity
            if total_margin > self.config.max_margin_per_order:
                reasons.append("ORDER_MARGIN_LIMIT")
            if context.portfolio.available_margin is None or total_margin > context.portfolio.available_margin:
                reasons.append("INSUFFICIENT_AVAILABLE_MARGIN")
        signed_quantity = quantity if intent.side is TastySide.LONG else -quantity
        reasons.extend(common_gate_reasons(
            config=self.config.common,
            context=context,
            forecast_generated_at=forecast.generated_at,
            snapshot_captured_at=snapshot.captured_at,
            intent_expires_at=intent.expires_at,
            market_open=snapshot.session_status.lower() == "open",
            quantity=quantity,
            projected_position=context.portfolio.current_position + signed_quantity,
            projected_market_exposure=context.portfolio.market_exposure + notional,
            projected_portfolio_exposure=context.portfolio.portfolio_exposure + notional,
        ))
        unique_reasons = tuple(dict.fromkeys(reasons))
        approved = None
        if not unique_reasons and intent.side is not None and resolution.mapping is not None:
            client_order_id = f"tft-{intent.trade_intent_id[-28:]}"
            action = "Buy to Open" if intent.side is TastySide.LONG else "Sell to Open"
            price_effect = "Debit" if intent.side is TastySide.LONG else "Credit"
            payload = {
                "client_order_id": client_order_id,
                "time-in-force": "Day",
                "order-type": "Limit",
                "price": f"{intent.entry_limit:.8f}".rstrip("0").rstrip("."),
                "price-effect": price_effect,
                "legs": [{
                    "instrument-type": intent.instrument_type.value,
                    "symbol": intent.symbol,
                    "quantity": f"{intent.quantity_requested:.8f}".rstrip("0").rstrip("."),
                    "action": action,
                }],
                "instrument_id": intent.instrument_id,
                "side": intent.side.value,
                "contract_multiplier": resolution.mapping.contract_multiplier,
                "require_dry_run": self.config.require_sandbox_dry_run,
            }
            approved = _issue_approved_order(
                risk_decision_id=decision_id,
                venue="TASTY_FUTURES",
                route=route,
                client_order_id=client_order_id,
                intent_id=intent.trade_intent_id,
                intent_hash=intent.intent_hash,
                payload=payload,
            )
        result = TastyRiskDecision(
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
                source_id=intent.trade_intent_id, venue="TASTY",
            )
        return result
