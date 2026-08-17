"""Official tastytrade sandbox adapter; sandbox is execution validation, not strategy truth."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from urllib.parse import quote

from ...common.approval import ApprovedOrder, require_approved_order
from ...common.hashing import hash_payload
from ...common.ledger import ImmutableTradingLedger
from .base import TastyOrderResult

TASTY_SANDBOX_BASE_URL = "https://api.cert.tastyworks.com"
TASTY_PRODUCTION_BASE_URL = "https://api.tastyworks.com"
TASTY_ORDERS_ACCEPT_VERSION = "20260427"


class TastyHttpTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]: ...


class TastyAuthProvider(Protocol):
    def headers(self) -> Mapping[str, str]: ...


@dataclass(frozen=True)
class TastySandboxCredentialRef:
    username_env: str
    password_env: str
    namespace: str = "TASTY_SANDBOX"

    def __post_init__(self) -> None:
        if not self.username_env.startswith("TASTY_SANDBOX_"):
            raise ValueError("sandbox username env name must use TASTY_SANDBOX_ namespace")
        if not self.password_env.startswith("TASTY_SANDBOX_"):
            raise ValueError("sandbox password env name must use TASTY_SANDBOX_ namespace")


class TastySandboxBroker:
    route_name = "tasty_sandbox"

    def __init__(
        self,
        *,
        account_number: str,
        transport: TastyHttpTransport,
        auth: TastyAuthProvider,
        credential_ref: TastySandboxCredentialRef,
        ledger: ImmutableTradingLedger | None = None,
        base_url: str = TASTY_SANDBOX_BASE_URL,
    ) -> None:
        if base_url.rstrip("/") != TASTY_SANDBOX_BASE_URL:
            raise ValueError("TastySandboxBroker v1 is sandbox-only; production URL is forbidden")
        self.account_number = account_number
        self.transport = transport
        self.auth = auth
        self.credential_ref = credential_ref
        self.ledger = ledger
        self.base_url = TASTY_SANDBOX_BASE_URL
        self._submitted_client_ids: set[str] = set()
        if self.ledger is not None:
            for row in self.ledger.read("orders"):
                if row["venue"] == "TASTY_SANDBOX":
                    approval = row["payload"].get("approval") or {}
                    client_id = approval.get("client_order_id")
                    if client_id:
                        self._submitted_client_ids.add(str(client_id))

    def _request(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any] | None = None,
        *,
        order_version: bool = False,
    ) -> Mapping[str, Any]:
        headers = dict(self.auth.headers())
        headers["Content-Type"] = "application/json"
        if order_version:
            headers["Accept-Version"] = TASTY_ORDERS_ACCEPT_VERSION
        return self.transport.request(
            method=method, url=self.base_url + path, headers=headers, json_body=body
        )

    def get_instrument(self, symbol: str, instrument_type: str) -> Mapping[str, Any]:
        collection = "future-options" if instrument_type == "Future Option" else "futures"
        return self._request("GET", f"/instruments/{collection}/{quote(symbol, safe='')}")

    def get_trading_status(self) -> Mapping[str, Any]:
        return self._request("GET", f"/accounts/{quote(self.account_number, safe='')}/trading-status")

    def get_balance(self) -> Mapping[str, Any]:
        return self._request("GET", f"/accounts/{quote(self.account_number, safe='')}/balances")

    def get_positions(self) -> Mapping[str, Any]:
        return self._request("GET", f"/accounts/{quote(self.account_number, safe='')}/positions")

    def get_orders(self) -> Mapping[str, Any]:
        return self._request(
            "GET", f"/accounts/{quote(self.account_number, safe='')}/orders", order_version=True
        )

    def get_margin_requirements(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._request(
            "POST", f"/margin/accounts/{quote(self.account_number, safe='')}/dry-run", payload
        )

    @staticmethod
    def _api_body(order: ApprovedOrder) -> dict[str, Any]:
        body = dict(order.payload)
        # These fields are local risk/identity annotations, not tastytrade order attributes.
        for key in (
            "client_order_id", "instrument_id", "side", "contract_multiplier", "require_dry_run"
        ):
            body.pop(key, None)
        return body

    def dry_run_order(self, order: ApprovedOrder) -> Mapping[str, Any]:
        require_approved_order(order, venue="TASTY_FUTURES")
        if order.route != self.route_name:
            raise RuntimeError("approval route does not match tasty sandbox")
        return self._request(
            "POST",
            f"/accounts/{quote(self.account_number, safe='')}/orders/dry-run",
            self._api_body(order),
            order_version=True,
        )

    def submit_order(self, order: ApprovedOrder) -> TastyOrderResult:
        require_approved_order(order, venue="TASTY_FUTURES")
        if order.route != self.route_name:
            raise RuntimeError("approval route does not match tasty sandbox")
        if order.client_order_id in self._submitted_client_ids:
            raise RuntimeError("duplicate client_order_id blocked locally")
        if bool(order.payload.get("require_dry_run")):
            dry_run = self.dry_run_order(order)
            if self._contains_rejection(dry_run):
                raise RuntimeError("tasty sandbox dry-run rejected order")
        response = self._request(
            "POST",
            f"/accounts/{quote(self.account_number, safe='')}/orders",
            self._api_body(order),
            order_version=True,
        )
        self._submitted_client_ids.add(order.client_order_id)
        parsed = self._order_object(response)
        order_id = str(parsed.get("id") or parsed.get("order-id") or parsed.get("order_id"))
        if not order_id or order_id == "None":
            raise RuntimeError("tasty sandbox response did not contain an order id")
        total = self._quantity(parsed, "quantity")
        remaining = self._quantity(parsed, "remaining-quantity", fallback=total)
        filled = max(0.0, total - remaining)
        average = parsed.get("average-fill-price") or parsed.get("average_fill_price")
        result = TastyOrderResult(
            order_id=order_id,
            client_order_id=order.client_order_id,
            state=str(parsed.get("status") or "SUBMITTED").upper(),
            filled_quantity=filled,
            remaining_quantity=remaining,
            average_fill_price=float(average) if average is not None else None,
            raw_source_hash=hash_payload(response),
        )
        if self.ledger is not None:
            self.ledger.append(
                "orders", {"approval": order.as_dict(), "response": dict(response)},
                correlation_id=order.intent_id, source_id=result.order_id, venue="TASTY_SANDBOX",
            )
        return result

    def cancel_order(self, order_id: str) -> Mapping[str, Any]:
        return self._request(
            "DELETE",
            f"/accounts/{quote(self.account_number, safe='')}/orders/{quote(order_id, safe='')}",
            order_version=True,
        )

    def replace_order(self, order_id: str, order: ApprovedOrder) -> Mapping[str, Any]:
        require_approved_order(order, venue="TASTY_FUTURES")
        if order.route != self.route_name:
            raise RuntimeError("approval route does not match tasty sandbox")
        return self._request(
            "PUT",
            f"/accounts/{quote(self.account_number, safe='')}/orders/{quote(order_id, safe='')}",
            self._api_body(order),
            order_version=True,
        )

    def get_order(self, order_id: str) -> Mapping[str, Any]:
        return self._request(
            "GET",
            f"/accounts/{quote(self.account_number, safe='')}/orders/{quote(order_id, safe='')}",
            order_version=True,
        )

    def reconcile(self) -> Mapping[str, Any]:
        """Fetch authoritative sandbox state after restart or the daily sandbox reset."""
        state = {
            "orders": dict(self.get_orders()),
            "positions": dict(self.get_positions()),
            "balance": dict(self.get_balance()),
            "trading_status": dict(self.get_trading_status()),
        }
        return {"state": state, "state_hash": hash_payload(state)}

    @staticmethod
    def _contains_rejection(response: Mapping[str, Any]) -> bool:
        text = str(response).lower()
        return "rejected" in text or "reject-reason" in text or "error" in text

    @staticmethod
    def _order_object(response: Mapping[str, Any]) -> Mapping[str, Any]:
        data = response.get("data")
        if isinstance(data, Mapping):
            order = data.get("order")
            if isinstance(order, Mapping):
                return order
            return data
        return response

    @staticmethod
    def _quantity(order: Mapping[str, Any], key: str, *, fallback: float = 0.0) -> float:
        value = order.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
        legs = order.get("legs")
        if isinstance(legs, list) and legs and isinstance(legs[0], Mapping):
            try:
                return float(legs[0].get(key, legs[0].get("quantity", fallback)))
            except (TypeError, ValueError):
                pass
        return fallback
