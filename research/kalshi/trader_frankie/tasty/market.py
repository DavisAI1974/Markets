"""Point-in-time tastytrade/DXLink snapshot capture with raw response hashing."""
from __future__ import annotations

from typing import Any, Mapping

from ..common.hashing import hash_payload, new_id, utc_now
from ..common.models import IdentityStatus
from .models import InstrumentResolution, TastyMarketSnapshot


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def capture_tasty_snapshot(
    *,
    raw_quote: Mapping[str, Any],
    resolution: InstrumentResolution,
    session_status: str,
    required_margin: float | None,
    source: str,
) -> TastyMarketSnapshot:
    if resolution.status is not IdentityStatus.EXACT or resolution.mapping is None:
        raise ValueError("snapshot capture requires an EXACT approved instrument")
    symbol = str(raw_quote.get("symbol") or "")
    if symbol != resolution.mapping.symbol:
        raise ValueError("quote symbol changed after identity resolution")
    return TastyMarketSnapshot(
        snapshot_id=new_id("tasty-snapshot"),
        captured_at=utc_now().isoformat().replace("+00:00", "Z"),
        instrument_id=resolution.mapping.instrument_id,
        symbol=symbol,
        instrument_type=resolution.mapping.instrument_type,
        session_status=session_status,
        bid=_number(raw_quote.get("bidPrice", raw_quote.get("bid"))),
        ask=_number(raw_quote.get("askPrice", raw_quote.get("ask"))),
        last=_number(raw_quote.get("price", raw_quote.get("last"))),
        required_margin=required_margin,
        expiration_time=resolution.mapping.expiration_time,
        instrument_identity_hash=resolution.identity_hash,
        raw_source_hash=hash_payload(dict(raw_quote)),
        source=source,
    )
