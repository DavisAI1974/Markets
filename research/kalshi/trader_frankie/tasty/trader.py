"""Intelligent proposal layer for Trader Frankie T; never submits orders."""
from __future__ import annotations

from typing import Any, Mapping

from ..common.hashing import hash_payload, new_id
from ..common.ledger import ImmutableTradingLedger
from ..common.models import ForecastEnvelope, IdentityStatus, TradeDecision
from ..common.reasoning import DecisionBackend, StandDownBackend
from .models import InstrumentResolution, TastyMarketSnapshot, TastySide, TastyTradeIntent
from .prompts import TRADER_FRANKIE_T_INSTRUCTIONS


class TastyTraderDecisionError(RuntimeError):
    pass


class TraderFrankieT:
    agent_id = "TRADER_FRANKIE_T"
    execution_authority = False

    def __init__(
        self,
        backend: DecisionBackend | None = None,
        *,
        ledger: ImmutableTradingLedger | None = None,
    ) -> None:
        self.backend = backend or StandDownBackend()
        self.ledger = ledger

    def decide(
        self,
        *,
        forecast: ForecastEnvelope,
        resolution: InstrumentResolution,
        snapshot: TastyMarketSnapshot,
        correlation_id: str,
    ) -> TastyTradeIntent:
        forced_reason: str | None = None
        if resolution.status is not IdentityStatus.EXACT:
            forced_reason = f"INSTRUMENT_IDENTITY_{resolution.status.value}"
        elif resolution.mapping is None:
            forced_reason = "INSTRUMENT_MAPPING_MISSING"
        elif snapshot.instrument_identity_hash != resolution.identity_hash:
            forced_reason = "SNAPSHOT_IDENTITY_HASH_MISMATCH"
        elif snapshot.instrument_id != resolution.mapping.instrument_id:
            forced_reason = "SNAPSHOT_INSTRUMENT_MISMATCH"
        if forced_reason:
            raw: Mapping[str, Any] = {"decision": "STAND_DOWN", "reason": forced_reason}
        else:
            raw = self.backend.generate(
                agent_id=self.agent_id,
                instructions=TRADER_FRANKIE_T_INSTRUCTIONS,
                payload={
                    "forecast_envelope": forecast.as_dict(),
                    "instrument_resolution": resolution.as_dict(),
                    "market_snapshot": snapshot.as_dict(),
                },
            )
        intent = self._parse(raw, forecast=forecast, snapshot=snapshot)
        if self.ledger is not None:
            self.ledger.append(
                "trade_intents", intent.as_dict(), correlation_id=correlation_id,
                source_id=intent.trade_intent_id, venue="TASTY",
            )
            if intent.trade_or_stand_down is TradeDecision.STAND_DOWN:
                self.ledger.append(
                    "stand_downs", intent.as_dict(), correlation_id=correlation_id,
                    source_id=intent.trade_intent_id, venue="TASTY",
                )
        return intent

    @staticmethod
    def _parse(
        raw: Mapping[str, Any], *, forecast: ForecastEnvelope, snapshot: TastyMarketSnapshot
    ) -> TastyTradeIntent:
        if not isinstance(raw, Mapping):
            raise TastyTraderDecisionError("Trader Frankie T backend output must be an object")
        try:
            decision = TradeDecision(str(raw.get("decision") or "STAND_DOWN").upper())
        except ValueError as exc:
            raise TastyTraderDecisionError("decision must be TRADE or STAND_DOWN") from exc
        reasoning_hash = hash_payload(dict(raw))
        expires_at = str(raw.get("expires_at") or snapshot.expiration_time)
        common = {
            "trade_intent_id": new_id("tasty-intent"),
            "forecast_id": forecast.forecast_id,
            "snapshot_id": snapshot.snapshot_id,
            "instrument_id": snapshot.instrument_id,
            "symbol": snapshot.symbol,
            "instrument_type": snapshot.instrument_type,
            "trade_or_stand_down": decision,
            "forecast_horizon": forecast.forecast.horizon,
            "expires_at": expires_at,
            "reasoning_hash": reasoning_hash,
        }
        if decision is TradeDecision.STAND_DOWN:
            return TastyTradeIntent(
                **common, side=None, quantity_requested=None, entry_limit=None,
                expected_lifespan=forecast.chain_state.expected_lifespan,
                invalidation=forecast.chain_state.invalidation, exit_thesis=(),
                confidence=forecast.forecast.confidence,
                stand_down_reason=str(raw.get("reason") or "NO_EXECUTABLE_EDGE"),
            )
        try:
            side = TastySide(str(raw["side"]).upper())
            quantity = float(raw["quantity_requested"])
            entry_limit = float(raw["entry_limit"])
            confidence = float(raw["confidence"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TastyTraderDecisionError(f"invalid TRADE output: {exc}") from exc
        if quantity <= 0 or entry_limit <= 0:
            raise TastyTraderDecisionError("quantity and entry_limit must be positive")
        return TastyTradeIntent(
            **common, side=side, quantity_requested=quantity, entry_limit=entry_limit,
            expected_lifespan=str(raw.get("expected_lifespan")) if raw.get("expected_lifespan") else None,
            invalidation=tuple(str(v) for v in raw.get("invalidation") or ()),
            exit_thesis=tuple(str(v) for v in raw.get("exit_thesis") or ()),
            confidence=confidence, stand_down_reason=None,
        )
