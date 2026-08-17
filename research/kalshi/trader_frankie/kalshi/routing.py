"""Deterministic best-execution routing across direct Kalshi and tastytrade routes."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from ..common.hashing import parse_timestamp
from ..common.models import IdentityStatus, TradeDecision
from .models import ContractResolution, KalshiTradeIntent, OutcomeExposure


@dataclass(frozen=True)
class RouterConfig:
    max_quote_age_seconds: int
    spread_weight: float
    fill_probability_penalty: float


@dataclass(frozen=True)
class RouteQuote:
    route: str
    ticker: str
    contract_identity_hash: str
    captured_at: str
    yes_bid: float | None
    yes_ask: float | None
    no_bid: float | None
    no_ask: float | None
    fee_per_contract: float
    fill_probability: float
    available: bool


@dataclass(frozen=True)
class RouteSelection:
    route: str
    executable_price: float
    spread: float
    fee_per_contract: float
    fill_probability: float
    score: float
    reasons: tuple[str, ...]


class NoExecutableRoute(RuntimeError):
    pass


class KalshiRouteRouter:
    def __init__(self, config: RouterConfig) -> None:
        self.config = config

    def choose(
        self,
        *,
        intent: KalshiTradeIntent,
        resolution: ContractResolution,
        quotes: tuple[RouteQuote, ...],
        now: dt.datetime,
    ) -> RouteSelection:
        if intent.decision is not TradeDecision.TRADE or intent.entry is None or intent.outcome_exposure is None:
            raise NoExecutableRoute("STAND_DOWN intent is not routable")
        if resolution.status is not IdentityStatus.EXACT or resolution.mapping is None:
            raise NoExecutableRoute("contract identity is not EXACT")
        candidates: list[RouteSelection] = []
        for quote in quotes:
            captured = parse_timestamp(quote.captured_at)
            if (
                not quote.available
                or quote.route not in resolution.mapping.enabled_routes
                or quote.ticker != intent.ticker
                or quote.contract_identity_hash != resolution.identity_hash
                or captured is None
                or (now.astimezone(dt.timezone.utc) - captured).total_seconds() > self.config.max_quote_age_seconds
                or not 0 <= quote.fill_probability <= 1
            ):
                continue
            if intent.outcome_exposure is OutcomeExposure.YES:
                executable, bid, ask = quote.yes_ask, quote.yes_bid, quote.yes_ask
            else:
                executable, bid, ask = quote.no_ask, quote.no_bid, quote.no_ask
            if executable is None or bid is None or ask is None or executable > intent.entry.max_price:
                continue
            spread = max(0.0, ask - bid)
            score = (
                executable
                + self.config.spread_weight * spread
                + quote.fee_per_contract
                + self.config.fill_probability_penalty * (1.0 - quote.fill_probability)
            )
            candidates.append(RouteSelection(
                route=quote.route, executable_price=executable, spread=spread,
                fee_per_contract=quote.fee_per_contract, fill_probability=quote.fill_probability,
                score=score, reasons=("PRICE_SPREAD_FEE_FILL_SCORE",),
            ))
        if not candidates:
            raise NoExecutableRoute("no fresh exact route satisfies the intent price")
        return min(candidates, key=lambda candidate: (candidate.score, candidate.route))
