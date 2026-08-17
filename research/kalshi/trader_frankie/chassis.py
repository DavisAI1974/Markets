"""Composition root for the dual-venue chassis; provider and credentials remain external."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common.forecast_adapter import ReadOnlyForecastAdapter
from .common.ledger import ImmutableTradingLedger
from .common.models import ForecastEnvelope
from .kalshi.brokers.base import KalshiBroker
from .kalshi.models import ContractResolution, KalshiMarketSnapshot, KalshiRiskDecision
from .origin import assert_descendant_write_path, verify_freeze
from .tasty.brokers.base import TastyBroker
from .tasty.models import InstrumentResolution, TastyMarketSnapshot, TastyRiskDecision

HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class TraderStatePaths:
    kalshi_ledger: Path = HERE / "kalshi" / "evidence" / "trading.sqlite3"
    tasty_ledger: Path = HERE / "tasty" / "evidence" / "trading.sqlite3"

    def verified(self) -> "TraderStatePaths":
        assert_descendant_write_path(self.kalshi_ledger)
        assert_descendant_write_path(self.tasty_ledger)
        if self.kalshi_ledger.resolve() == self.tasty_ledger.resolve():
            raise ValueError("Kalshi and Tasty evidence stores must be isolated")
        return self


class DualVenueTradingChassis:
    def __init__(self, paths: TraderStatePaths | None = None) -> None:
        self.freeze = verify_freeze()
        self.paths = (paths or TraderStatePaths()).verified()
        self.kalshi_ledger = ImmutableTradingLedger(self.paths.kalshi_ledger)
        self.tasty_ledger = ImmutableTradingLedger(self.paths.tasty_ledger)
        self.adapter = ReadOnlyForecastAdapter()

    def ingest_forecast(self, raw: dict[str, Any], *, correlation_id: str) -> ForecastEnvelope:
        envelope = self.adapter.adapt(raw)
        source_id = envelope.forecast_id or envelope.provenance.forecast_hash
        for ledger, venue in ((self.kalshi_ledger, "KALSHI"), (self.tasty_ledger, "TASTY")):
            ledger.append(
                "forecast_envelopes", envelope.as_dict(), correlation_id=correlation_id,
                source_id=source_id, venue=venue,
            )
        return envelope

    def record_kalshi_market_state(
        self,
        *,
        resolution: ContractResolution,
        snapshot: KalshiMarketSnapshot,
        correlation_id: str,
    ) -> None:
        self.kalshi_ledger.append(
            "contract_mappings", resolution.as_dict(), correlation_id=correlation_id,
            source_id=resolution.identity_hash, venue="KALSHI",
        )
        self.kalshi_ledger.append(
            "kalshi_market_snapshots", snapshot.as_dict(), correlation_id=correlation_id,
            source_id=snapshot.snapshot_id, venue="KALSHI",
        )

    def record_tasty_market_state(
        self,
        *,
        resolution: InstrumentResolution,
        snapshot: TastyMarketSnapshot,
        correlation_id: str,
    ) -> None:
        self.tasty_ledger.append(
            "instrument_mappings", resolution.as_dict(), correlation_id=correlation_id,
            source_id=resolution.identity_hash, venue="TASTY",
        )
        self.tasty_ledger.append(
            "tasty_market_snapshots", snapshot.as_dict(), correlation_id=correlation_id,
            source_id=snapshot.snapshot_id, venue="TASTY",
        )

    @staticmethod
    def execute_kalshi(decision: KalshiRiskDecision, broker: KalshiBroker) -> Any:
        if decision.decision != "APPROVE" or decision.approved_order is None:
            raise RuntimeError("Kalshi executor cannot accept an unapproved TradeIntent")
        return broker.submit_order(decision.approved_order)

    @staticmethod
    def execute_tasty(decision: TastyRiskDecision, broker: TastyBroker) -> Any:
        if decision.decision != "APPROVE" or decision.approved_order is None:
            raise RuntimeError("Tasty executor cannot accept an unapproved TastyTradeIntent")
        return broker.submit_order(decision.approved_order)
