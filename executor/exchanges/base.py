"""
exchanges/base.py — abstract Exchange interface.

Every exchange adapter implements this. The executor talks only to this
interface; specific exchange API integration lives in the adapter.

Each friend deploying the executor implements (or installs) the adapter for
their specific exchange. We ship a paper-trading adapter (no real orders)
so the system is testable end-to-end without exposing anyone to real money
risk.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class OrderResult:
    success: bool
    exchange_order_id: str = ""
    fill_price: float = 0.0
    fill_size: float = 0.0
    fees_usd: float = 0.0
    error: str = ""
    raw: dict | None = None


@dataclass
class PriceQuote:
    asset: str
    bid: float
    ask: float
    mid: float
    timestamp_utc: float


class Exchange(Protocol):
    """Abstract exchange. All adapters must implement this."""

    name: str

    def get_quote(self, asset: str) -> PriceQuote:
        """Return current best bid/ask for the asset (e.g. 'BTC-USD')."""
        ...

    def market_buy(self, asset: str, notional_usd: float) -> OrderResult:
        """Place a market buy of approximately notional_usd worth of asset."""
        ...

    def market_sell(self, asset: str, size: float) -> OrderResult:
        """Place a market sell of `size` units of asset."""
        ...

    def get_position(self, asset: str) -> float:
        """Current position size in units of asset (0 if flat)."""
        ...
