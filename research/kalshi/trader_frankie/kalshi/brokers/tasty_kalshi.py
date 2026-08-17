"""tastytrade event-contract route behind a documented-gateway boundary."""
from __future__ import annotations

from typing import Any, Mapping, Protocol

from ...common.approval import ApprovedOrder, require_approved_order
from ...common.hashing import hash_payload
from ...common.ledger import ImmutableTradingLedger
from .base import BrokerOrderResult


class TastyEventContractGateway(Protocol):
    """Injected once tastytrade publishes/supports an event-contract API integration."""

    def get_market(self, ticker: str) -> Mapping[str, Any]: ...
    def get_orderbook(self, ticker: str) -> Mapping[str, Any]: ...
    def get_balance(self) -> Mapping[str, Any]: ...
    def get_positions(self) -> Mapping[str, Any]: ...
    def get_orders(self) -> Mapping[str, Any]: ...
    def submit_normalized_event_order(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def cancel_order(self, order_id: str) -> Mapping[str, Any]: ...
    def get_order(self, order_id: str) -> Mapping[str, Any]: ...
    def get_fills(self, order_id: str | None = None) -> Mapping[str, Any]: ...


class TastyKalshiBroker:
    """Second route from day one, but no undocumented URL or request shape is guessed."""

    route_name = "tasty_kalshi"

    def __init__(
        self,
        gateway: TastyEventContractGateway | None,
        *,
        ledger: ImmutableTradingLedger | None = None,
    ) -> None:
        self.gateway = gateway
        self.ledger = ledger

    def _require_gateway(self) -> TastyEventContractGateway:
        if self.gateway is None:
            raise RuntimeError("tastytrade event-contract gateway is unavailable; route fails closed")
        return self.gateway

    def get_market(self, ticker: str) -> Mapping[str, Any]:
        return self._require_gateway().get_market(ticker)

    def get_orderbook(self, ticker: str) -> Mapping[str, Any]:
        return self._require_gateway().get_orderbook(ticker)

    def get_balance(self) -> Mapping[str, Any]:
        return self._require_gateway().get_balance()

    def get_positions(self) -> Mapping[str, Any]:
        return self._require_gateway().get_positions()

    def get_orders(self) -> Mapping[str, Any]:
        return self._require_gateway().get_orders()

    def submit_order(self, order: ApprovedOrder) -> BrokerOrderResult:
        require_approved_order(order, venue="KALSHI_EVENT")
        if order.route != self.route_name:
            raise RuntimeError(f"approval route {order.route!r} does not match tasty Kalshi")
        response = self._require_gateway().submit_normalized_event_order(dict(order.payload))
        result = BrokerOrderResult(
            order_id=str(response["order_id"]),
            client_order_id=str(response.get("client_order_id") or order.client_order_id),
            state=str(response.get("state") or "SUBMITTED").upper(),
            filled_count=float(response.get("filled_count", 0)),
            remaining_count=float(response.get("remaining_count", 0)),
            average_fill_price=(
                float(response["average_fill_price"]) if response.get("average_fill_price") is not None else None
            ),
            raw_source_hash=hash_payload(response),
        )
        if self.ledger is not None:
            self.ledger.append(
                "orders", {"approval": order.as_dict(), "response": dict(response)},
                correlation_id=order.intent_id, source_id=result.order_id, venue="TASTY_KALSHI",
            )
        return result

    def cancel_order(self, order_id: str) -> Mapping[str, Any]:
        return self._require_gateway().cancel_order(order_id)

    def get_order(self, order_id: str) -> Mapping[str, Any]:
        return self._require_gateway().get_order(order_id)

    def get_fills(self, order_id: str | None = None) -> Mapping[str, Any]:
        return self._require_gateway().get_fills(order_id)
