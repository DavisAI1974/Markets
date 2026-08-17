"""Kalshi Demo direct adapter using the current V2 event-order create/cancel shape."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from urllib.parse import quote

from ...common.approval import ApprovedOrder, require_approved_order
from ...common.hashing import hash_payload
from ...common.ledger import ImmutableTradingLedger
from .base import BrokerOrderResult

KALSHI_DEMO_BASE_URL = "https://external-api.demo.kalshi.co/trade-api/v2"
KALSHI_PRODUCTION_BASE_URL = "https://external-api.kalshi.com/trade-api/v2"


class HttpTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]: ...


class KalshiRequestSigner(Protocol):
    def headers(self, *, method: str, signed_path: str) -> Mapping[str, str]: ...


@dataclass(frozen=True)
class KalshiDemoCredentialRef:
    access_key_id_env: str
    private_key_path_env: str
    namespace: str = "KALSHI_DEMO"

    def __post_init__(self) -> None:
        if not self.access_key_id_env.startswith("KALSHI_DEMO_"):
            raise ValueError("demo access-key env name must use KALSHI_DEMO_ namespace")
        if not self.private_key_path_env.startswith("KALSHI_DEMO_"):
            raise ValueError("demo private-key env name must use KALSHI_DEMO_ namespace")


class KalshiDirectBroker:
    """Direct demo route. Private-key material stays inside the injected signer."""

    route_name = "kalshi_direct"

    def __init__(
        self,
        *,
        transport: HttpTransport,
        signer: KalshiRequestSigner,
        credential_ref: KalshiDemoCredentialRef,
        ledger: ImmutableTradingLedger | None = None,
        base_url: str = KALSHI_DEMO_BASE_URL,
    ) -> None:
        if base_url.rstrip("/") != KALSHI_DEMO_BASE_URL:
            raise ValueError("KalshiDirectBroker v1 is demo-only; production URL is forbidden")
        self.transport = transport
        self.signer = signer
        self.credential_ref = credential_ref
        self.ledger = ledger
        self.base_url = KALSHI_DEMO_BASE_URL
        self._submitted_client_ids: set[str] = set()
        if self.ledger is not None:
            for row in self.ledger.read("orders"):
                if row["venue"] == "KALSHI_DEMO":
                    approval = row["payload"].get("approval") or {}
                    client_id = approval.get("client_order_id")
                    if client_id:
                        self._submitted_client_ids.add(str(client_id))

    def _public(self, path: str) -> Mapping[str, Any]:
        return self.transport.request(method="GET", url=self.base_url + path)

    def _private(
        self, method: str, path: str, body: Mapping[str, Any] | None = None
    ) -> Mapping[str, Any]:
        signed_path = "/trade-api/v2" + path.split("?", 1)[0]
        headers = dict(self.signer.headers(method=method, signed_path=signed_path))
        headers["Content-Type"] = "application/json"
        return self.transport.request(
            method=method, url=self.base_url + path, headers=headers, json_body=body
        )

    def get_market(self, ticker: str) -> Mapping[str, Any]:
        return self._public(f"/markets/{quote(ticker, safe='')}")

    def get_orderbook(self, ticker: str) -> Mapping[str, Any]:
        return self._public(f"/markets/{quote(ticker, safe='')}/orderbook")

    def get_balance(self) -> Mapping[str, Any]:
        return self._private("GET", "/portfolio/balance")

    def get_positions(self) -> Mapping[str, Any]:
        return self._private("GET", "/portfolio/positions")

    def get_orders(self) -> Mapping[str, Any]:
        return self._private("GET", "/portfolio/orders")

    def submit_order(self, order: ApprovedOrder) -> BrokerOrderResult:
        require_approved_order(order, venue="KALSHI_EVENT")
        if order.route != self.route_name:
            raise RuntimeError(f"approval route {order.route!r} does not match direct Kalshi")
        if order.client_order_id in self._submitted_client_ids:
            raise RuntimeError("duplicate client_order_id blocked locally")
        body = dict(order.payload)
        # Internal economic annotations never leave the deterministic executor boundary.
        body.pop("outcome_exposure", None)
        body.pop("economic_max_price", None)
        response = self._private("POST", "/portfolio/events/orders", body)
        self._submitted_client_ids.add(order.client_order_id)
        result = BrokerOrderResult(
            order_id=str(response["order_id"]),
            client_order_id=str(response.get("client_order_id") or order.client_order_id),
            state="FILLED" if float(response.get("remaining_count", 0)) == 0 else "SUBMITTED",
            filled_count=float(response.get("fill_count", 0)),
            remaining_count=float(response.get("remaining_count", 0)),
            average_fill_price=(
                float(response["average_fill_price"]) if response.get("average_fill_price") is not None else None
            ),
            raw_source_hash=hash_payload(response),
        )
        if self.ledger is not None:
            self.ledger.append(
                "orders", {"approval": order.as_dict(), "response": dict(response)},
                correlation_id=order.intent_id, source_id=result.order_id, venue="KALSHI_DEMO",
            )
        return result

    def cancel_order(self, order_id: str) -> Mapping[str, Any]:
        return self._private("DELETE", f"/portfolio/events/orders/{quote(order_id, safe='')}")

    def get_order(self, order_id: str) -> Mapping[str, Any]:
        return self._private("GET", f"/portfolio/orders/{quote(order_id, safe='')}")

    def get_fills(self, order_id: str | None = None) -> Mapping[str, Any]:
        path = "/portfolio/fills"
        if order_id:
            path += f"?order_id={quote(order_id, safe='')}"
        return self._private("GET", path)

    def reconcile(self) -> Mapping[str, Any]:
        """Fetch authoritative demo state for restart reconciliation."""
        state = {
            "orders": dict(self.get_orders()),
            "positions": dict(self.get_positions()),
            "fills": dict(self.get_fills()),
            "balance": dict(self.get_balance()),
        }
        return {"state": state, "state_hash": hash_payload(state)}


class KalshiDemoBroker(KalshiDirectBroker):
    """Compatibility name for the direct Kalshi demo route."""
