"""Shared deterministic risk inputs and gates. Threshold values are always explicit config."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable

from .hashing import parse_timestamp
from .models import HealthSnapshot, PortfolioSnapshot


@dataclass(frozen=True)
class CommonRiskConfig:
    max_forecast_age_seconds: int
    max_snapshot_age_seconds: int
    max_position: float
    max_market_exposure: float
    max_portfolio_exposure: float
    max_daily_loss: float
    max_open_orders: int
    max_concurrent_markets: int
    min_seconds_to_close: int
    min_quantity: float
    max_quantity: float
    global_kill_switch: bool


@dataclass(frozen=True)
class RiskContext:
    now: dt.datetime
    portfolio: PortfolioSnapshot
    health: HealthSnapshot
    duplicate_intent: bool
    duplicate_client_order_id: bool
    seconds_to_close: float | None


def common_gate_reasons(
    *,
    config: CommonRiskConfig,
    context: RiskContext,
    forecast_generated_at: str | None,
    snapshot_captured_at: str,
    intent_expires_at: str,
    market_open: bool,
    quantity: float,
    projected_position: float,
    projected_market_exposure: float,
    projected_portfolio_exposure: float,
) -> tuple[str, ...]:
    reasons: list[str] = []
    now = context.now.astimezone(dt.timezone.utc)
    if config.global_kill_switch:
        reasons.append("GLOBAL_KILL_SWITCH")
    if not context.health.data_feed_ok:
        reasons.append("DATA_FEED_UNHEALTHY")
    if not context.health.broker_api_ok:
        reasons.append("BROKER_API_UNHEALTHY")
    if not market_open:
        reasons.append("MARKET_NOT_OPEN")
    generated = parse_timestamp(forecast_generated_at)
    if generated is None:
        reasons.append("FORECAST_TIME_UNKNOWN")
    else:
        forecast_age = (now - generated).total_seconds()
        if forecast_age < 0:
            reasons.append("FORECAST_FROM_FUTURE")
        elif forecast_age > config.max_forecast_age_seconds:
            reasons.append("FORECAST_STALE")
    captured = parse_timestamp(snapshot_captured_at)
    if captured is None:
        reasons.append("MARKET_SNAPSHOT_STALE")
    else:
        snapshot_age = (now - captured).total_seconds()
        if snapshot_age < 0:
            reasons.append("MARKET_SNAPSHOT_FROM_FUTURE")
        elif snapshot_age > config.max_snapshot_age_seconds:
            reasons.append("MARKET_SNAPSHOT_STALE")
    expires = parse_timestamp(intent_expires_at)
    if expires is None or now >= expires:
        reasons.append("INTENT_EXPIRED")
    if context.duplicate_intent:
        reasons.append("DUPLICATE_INTENT")
    if context.duplicate_client_order_id:
        reasons.append("DUPLICATE_CLIENT_ORDER_ID")
    if not config.min_quantity <= quantity <= config.max_quantity:
        reasons.append("QUANTITY_OUT_OF_RANGE")
    if abs(projected_position) > config.max_position:
        reasons.append("POSITION_LIMIT")
    if abs(projected_market_exposure) > config.max_market_exposure:
        reasons.append("MARKET_EXPOSURE_LIMIT")
    if abs(projected_portfolio_exposure) > config.max_portfolio_exposure:
        reasons.append("PORTFOLIO_EXPOSURE_LIMIT")
    if context.portfolio.daily_realized_pnl <= -abs(config.max_daily_loss):
        reasons.append("DAILY_LOSS_LIMIT")
    if context.portfolio.open_order_count >= config.max_open_orders:
        reasons.append("OPEN_ORDER_LIMIT")
    if context.portfolio.concurrent_market_count >= config.max_concurrent_markets:
        reasons.append("CONCURRENT_MARKET_LIMIT")
    if context.seconds_to_close is None or context.seconds_to_close < config.min_seconds_to_close:
        reasons.append("TOO_CLOSE_TO_CLOSE_OR_SETTLEMENT")
    return tuple(reasons)


def require_config_keys(raw: dict, keys: Iterable[str], *, label: str) -> None:
    missing = sorted(key for key in keys if key not in raw or raw[key] is None)
    if missing:
        raise ValueError(f"{label} requires explicit thresholds: {', '.join(missing)}")
