"""One deterministic broker interface for every Kalshi execution route."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from ...common.approval import ApprovedOrder


@dataclass(frozen=True)
class BrokerOrderResult:
    order_id: str
    client_order_id: str
    state: str
    filled_count: float
    remaining_count: float
    average_fill_price: float | None
    raw_source_hash: str


class KalshiBroker(Protocol):
    route_name: str

    def get_market(self, ticker: str) -> Mapping[str, Any]: ...
    def get_orderbook(self, ticker: str) -> Mapping[str, Any]: ...
    def get_balance(self) -> Mapping[str, Any]: ...
    def get_positions(self) -> Mapping[str, Any]: ...
    def get_orders(self) -> Mapping[str, Any]: ...
    def submit_order(self, order: ApprovedOrder) -> BrokerOrderResult: ...
    def cancel_order(self, order_id: str) -> Mapping[str, Any]: ...
    def get_order(self, order_id: str) -> Mapping[str, Any]: ...
    def get_fills(self, order_id: str | None = None) -> Mapping[str, Any]: ...
