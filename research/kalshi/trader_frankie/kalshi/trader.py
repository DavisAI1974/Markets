"""Intelligent proposal layer for Trader Frankie K; never submits orders."""
from __future__ import annotations

from typing import Any, Mapping

from ..common.hashing import hash_payload, new_id
from ..common.ledger import ImmutableTradingLedger
from ..common.models import ForecastEnvelope, IdentityStatus, TradeDecision
from ..common.reasoning import DecisionBackend, StandDownBackend
from .models import (
    ContractResolution, KalshiEntry, KalshiMarketSnapshot, KalshiOrderStyle,
    KalshiTradeIntent, OutcomeExposure,
)
from .prompts import TRADER_FRANKIE_K_INSTRUCTIONS


class TraderDecisionError(RuntimeError):
    pass


class TraderFrankieK:
    agent_id = "TRADER_FRANKIE_K"
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
        resolution: ContractResolution,
        snapshot: KalshiMarketSnapshot,
        correlation_id: str,
    ) -> KalshiTradeIntent:
        forced_reason: str | None = None
        if resolution.status is not IdentityStatus.EXACT:
            forced_reason = f"CONTRACT_IDENTITY_{resolution.status.value}"
        elif resolution.mapping is None:
            forced_reason = "CONTRACT_MAPPING_MISSING"
        elif snapshot.contract_identity_hash != resolution.identity_hash:
            forced_reason = "SNAPSHOT_IDENTITY_HASH_MISMATCH"
        elif snapshot.ticker != resolution.mapping.ticker:
            forced_reason = "SNAPSHOT_TICKER_MISMATCH"

        if forced_reason:
            raw: Mapping[str, Any] = {"decision": "STAND_DOWN", "reason": forced_reason}
        else:
            raw = self.backend.generate(
                agent_id=self.agent_id,
                instructions=TRADER_FRANKIE_K_INSTRUCTIONS,
                payload={
                    "forecast_envelope": forecast.as_dict(),
                    "contract_resolution": resolution.as_dict(),
                    "market_snapshot": snapshot.as_dict(),
                },
            )
        intent = self._parse(raw, forecast=forecast, snapshot=snapshot)
        if self.ledger is not None:
            self.ledger.append(
                "trade_intents", intent.as_dict(), correlation_id=correlation_id,
                source_id=intent.trade_intent_id, venue="KALSHI",
            )
            if intent.decision is TradeDecision.STAND_DOWN:
                self.ledger.append(
                    "stand_downs", intent.as_dict(), correlation_id=correlation_id,
                    source_id=intent.trade_intent_id, venue="KALSHI",
                )
        return intent

    def _parse(
        self,
        raw: Mapping[str, Any],
        *,
        forecast: ForecastEnvelope,
        snapshot: KalshiMarketSnapshot,
    ) -> KalshiTradeIntent:
        if not isinstance(raw, Mapping):
            raise TraderDecisionError("Trader Frankie K backend output must be an object")
        try:
            decision = TradeDecision(str(raw.get("decision") or "STAND_DOWN").upper())
        except ValueError as exc:
            raise TraderDecisionError("decision must be TRADE or STAND_DOWN") from exc
        reasoning_hash = hash_payload(dict(raw))
        expires_at = str(raw.get("expires_at") or snapshot.close_time)
        if decision is TradeDecision.STAND_DOWN:
            return KalshiTradeIntent(
                trade_intent_id=new_id("kalshi-intent"), forecast_id=forecast.forecast_id,
                snapshot_id=snapshot.snapshot_id, ticker=snapshot.ticker, decision=decision,
                outcome_exposure=None, entry=None, expected_edge=None,
                confidence=forecast.forecast.confidence,
                expected_lifespan=forecast.chain_state.expected_lifespan,
                invalidation=forecast.chain_state.invalidation, exit_thesis=(),
                expires_at=expires_at, trader_reasoning_hash=reasoning_hash,
                stand_down_reason=str(raw.get("reason") or "NO_EXECUTABLE_EDGE"),
            )
        entry = raw.get("entry")
        if not isinstance(entry, Mapping):
            raise TraderDecisionError("TRADE requires an entry object")
        try:
            exposure = OutcomeExposure(str(raw["outcome_exposure"]).upper())
            order_style = KalshiOrderStyle(str(entry["order_style"]).upper())
            max_price = float(entry["max_price"])
            requested_count = float(entry["requested_count"])
            expected_edge = float(raw["expected_edge"])
            confidence = float(raw["confidence"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TraderDecisionError(f"invalid TRADE output: {exc}") from exc
        if not 0 < max_price < 1 or requested_count <= 0:
            raise TraderDecisionError("Kalshi price must be between 0 and 1 and count must be positive")
        return KalshiTradeIntent(
            trade_intent_id=new_id("kalshi-intent"), forecast_id=forecast.forecast_id,
            snapshot_id=snapshot.snapshot_id, ticker=snapshot.ticker, decision=decision,
            outcome_exposure=exposure,
            entry=KalshiEntry(max_price=max_price, requested_count=requested_count, order_style=order_style),
            expected_edge=expected_edge, confidence=confidence,
            expected_lifespan=str(raw.get("expected_lifespan")) if raw.get("expected_lifespan") else None,
            invalidation=tuple(str(v) for v in raw.get("invalidation") or ()),
            exit_thesis=tuple(str(v) for v in raw.get("exit_thesis") or ()),
            expires_at=expires_at, trader_reasoning_hash=reasoning_hash,
            stand_down_reason=None,
        )
