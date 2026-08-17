"""Point-in-time Kalshi snapshot capture with raw response hashing."""
from __future__ import annotations

from typing import Any, Mapping

from ..common.hashing import hash_payload, new_id, utc_now
from ..common.models import IdentityStatus
from .models import ContractResolution, KalshiMarketSnapshot


def _number(*values: Any) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def capture_kalshi_snapshot(
    *,
    raw_market: Mapping[str, Any],
    raw_orderbook: Mapping[str, Any],
    resolution: ContractResolution,
) -> KalshiMarketSnapshot:
    if resolution.status is not IdentityStatus.EXACT or resolution.mapping is None:
        raise ValueError("snapshot capture requires an EXACT approved contract")
    market = raw_market.get("market") if isinstance(raw_market.get("market"), Mapping) else raw_market
    if not isinstance(market, Mapping):
        raise TypeError("Kalshi market response must contain an object")
    ticker = str(market.get("ticker") or "")
    if ticker != resolution.mapping.ticker:
        raise ValueError("market ticker changed after identity resolution")
    raw_hash = hash_payload({"market": dict(raw_market), "orderbook": dict(raw_orderbook)})
    return KalshiMarketSnapshot(
        snapshot_id=new_id("kalshi-snapshot"),
        captured_at=utc_now().isoformat().replace("+00:00", "Z"),
        ticker=ticker,
        status=str(market.get("status") or "unknown"),
        yes_bid=_number(market.get("yes_bid_dollars"), market.get("yes_bid")),
        yes_ask=_number(market.get("yes_ask_dollars"), market.get("yes_ask")),
        no_bid=_number(market.get("no_bid_dollars"), market.get("no_bid")),
        no_ask=_number(market.get("no_ask_dollars"), market.get("no_ask")),
        book_hash=hash_payload(dict(raw_orderbook)),
        volume=_number(market.get("volume_fp"), market.get("volume")),
        open_interest=_number(market.get("open_interest_fp"), market.get("open_interest")),
        close_time=str(market.get("close_time") or resolution.mapping.close_time),
        expiration_time=str(
            market.get("expiration_time") or market.get("latest_expiration_time")
            or resolution.mapping.expiration_time
        ),
        contract_identity_hash=resolution.identity_hash,
        raw_source_hash=raw_hash,
    )
