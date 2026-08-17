"""Local NG futures/futures-option paper broker using immutable market snapshots."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ...common.approval import ApprovedOrder, require_approved_order
from ...common.hashing import hash_payload, new_id, utc_now
from ...common.ledger import ImmutableTradingLedger
from ...common.models import OrderState
from ...common.state_machine import OrderLifecycle
from ..models import TastyMarketSnapshot
from .base import TastyOrderResult


@dataclass(frozen=True)
class TastyPaperFillConfig:
    immediate_fill_fraction: float
    fee_per_contract: float


class TastyPaperBroker:
    route_name = "tasty_paper"

    def __init__(
        self,
        *,
        ledger: ImmutableTradingLedger,
        fill_config: TastyPaperFillConfig,
    ) -> None:
        if not 0 <= fill_config.immediate_fill_fraction <= 1:
            raise ValueError("immediate_fill_fraction must be between 0 and 1")
        self.ledger = ledger
        self.fill_config = fill_config
        self._snapshots: dict[str, TastyMarketSnapshot] = {}
        self._orders: dict[str, dict[str, Any]] = {}
        self._fills: list[dict[str, Any]] = []
        self._positions: dict[str, dict[str, float]] = {}
        self._lifecycles: dict[str, OrderLifecycle] = {}
        self.recover_from_ledger()

    def recover_from_ledger(self) -> None:
        """Reconstruct open orders, fills, and positions from immutable records after restart."""
        self._orders.clear()
        self._fills.clear()
        self._positions.clear()
        self._lifecycles.clear()
        for row in self.ledger.read("orders"):
            if row["venue"] != "TASTY_PAPER":
                continue
            order = dict(row["payload"])
            self._orders[str(order["order_id"])] = order
        last_state: dict[str, str] = {}
        for row in self.ledger.read("order_events"):
            if row["venue"] == "TASTY_PAPER":
                payload = row["payload"]
                last_state[str(payload["order_id"])] = str(payload["order_state"])
        for row in self.ledger.read("fills"):
            if row["venue"] != "TASTY_PAPER":
                continue
            fill = dict(row["payload"])
            self._fills.append(fill)
            order = self._orders.get(str(fill["order_id"]))
            if order is None:
                continue
            quantity = float(fill["quantity"])
            price = float(fill["price"])
            prior_value = (order.get("average_fill_price") or 0.0) * float(order.get("filled_quantity", 0.0))
            order["filled_quantity"] = float(order.get("filled_quantity", 0.0)) + quantity
            order["remaining_quantity"] = max(0.0, float(order["quantity"]) - order["filled_quantity"])
            order["average_fill_price"] = (prior_value + price * quantity) / order["filled_quantity"]
            position = self._positions.setdefault(str(fill["symbol"]), {
                "signed_quantity": 0.0, "average_entry": 0.0,
                "multiplier": float(order["multiplier"]), "fees": 0.0, "realized_pnl": 0.0,
            })
            signed = quantity if fill["side"] == "LONG" else -quantity
            prior_abs = abs(position["signed_quantity"])
            position["average_entry"] = (
                position["average_entry"] * prior_abs + price * quantity
            ) / (prior_abs + quantity)
            position["signed_quantity"] += signed
            position["fees"] += float(fill["fee"])
        for row in self.ledger.read("settlements"):
            if row["venue"] != "TASTY_PAPER":
                continue
            settlement = row["payload"]
            position = self._positions.get(str(settlement["symbol"]))
            if position is not None:
                position["signed_quantity"] = 0.0
                position["realized_pnl"] += float(settlement["realized_pnl"])
        for order_id, order in self._orders.items():
            order["state"] = last_state.get(order_id, str(order.get("state") or OrderState.ERROR_SAFE.value))
            lifecycle = OrderLifecycle(order_id)
            lifecycle.state = OrderState(order["state"])
            self._lifecycles[order_id] = lifecycle

    def ingest_snapshot(self, snapshot: TastyMarketSnapshot) -> None:
        self._snapshots[snapshot.symbol] = snapshot

    def get_instrument(self, symbol: str, instrument_type: str) -> Mapping[str, Any]:
        snapshot = self._snapshots.get(symbol)
        if snapshot is None or snapshot.instrument_type.value != instrument_type:
            return {}
        return snapshot.as_dict()

    def get_balance(self) -> Mapping[str, Any]:
        return {"mode": "paper", "realized_pnl": sum(v["realized_pnl"] for v in self._positions.values())}

    def get_positions(self) -> Mapping[str, Any]:
        return {"positions": [dict(value, symbol=symbol) for symbol, value in self._positions.items()]}

    def get_orders(self) -> Mapping[str, Any]:
        return {"orders": [dict(order) for order in self._orders.values()]}

    def get_margin_requirements(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        legs = payload.get("legs") or []
        if not legs:
            return {"error": "no legs"}
        snapshot = self._snapshots.get(str(legs[0].get("symbol")))
        return {"required_margin": snapshot.required_margin if snapshot else None}

    def dry_run_order(self, order: ApprovedOrder) -> Mapping[str, Any]:
        require_approved_order(order, venue="TASTY_FUTURES")
        return {"accepted": order.route == self.route_name, "approval_hash": order.approval_hash}

    def submit_order(self, order: ApprovedOrder) -> TastyOrderResult:
        require_approved_order(order, venue="TASTY_FUTURES")
        if order.route != self.route_name:
            raise RuntimeError(f"approval route {order.route!r} does not match tasty paper")
        if any(item["client_order_id"] == order.client_order_id for item in self._orders.values()):
            raise RuntimeError("duplicate client_order_id")
        payload = dict(order.payload)
        leg = (payload.get("legs") or [None])[0]
        if not isinstance(leg, Mapping):
            raise RuntimeError("approved Tasty order has no leg")
        symbol = str(leg["symbol"])
        snapshot = self._snapshots.get(symbol)
        if snapshot is None or snapshot.session_status.lower() != "open":
            raise RuntimeError("paper submission requires a current open snapshot")
        quantity = float(leg["quantity"])
        limit = float(payload["price"])
        side = str(payload["side"])
        multiplier = float(payload["contract_multiplier"])
        order_id = new_id("paper-tasty-order")
        record = {
            "order_id": order_id,
            "approval_id": order.approval_id,
            "client_order_id": order.client_order_id,
            "symbol": symbol,
            "side": side,
            "limit_price": limit,
            "quantity": quantity,
            "filled_quantity": 0.0,
            "remaining_quantity": quantity,
            "average_fill_price": None,
            "multiplier": multiplier,
            "state": OrderState.SUBMITTED.value,
            "correlation_id": order.intent_id,
        }
        self._orders[order_id] = record
        lifecycle = OrderLifecycle(order_id)
        self._lifecycles[order_id] = lifecycle
        for state, reason in (
            (OrderState.INTENT_CREATED, "approved intent"),
            (OrderState.RISK_PENDING, "risk decision recorded"),
            (OrderState.RISK_APPROVED, order.risk_decision_id),
            (OrderState.SUBMIT_PENDING, "paper submit"),
            (OrderState.SUBMITTED, "paper order accepted"),
        ):
            self._record_event(lifecycle.transition(state, reason=reason), record)
        self.ledger.append(
            "orders", record, correlation_id=order.intent_id, source_id=order_id, venue="TASTY_PAPER",
        )
        self._try_fill(order_id, snapshot, self.fill_config.immediate_fill_fraction)
        if record["filled_quantity"] == 0:
            record["state"] = OrderState.RESTING.value
            self._record_event(lifecycle.transition(OrderState.RESTING, reason="limit not marketable"), record)
        return self._result(record)

    def process_snapshot(self, snapshot: TastyMarketSnapshot, *, fill_fraction: float = 1.0) -> None:
        self.ingest_snapshot(snapshot)
        for order_id, order in tuple(self._orders.items()):
            if order["symbol"] == snapshot.symbol and order["state"] in {
                OrderState.RESTING.value, OrderState.PARTIAL.value,
            }:
                self._try_fill(order_id, snapshot, fill_fraction)

    def _try_fill(self, order_id: str, snapshot: TastyMarketSnapshot, fraction: float) -> None:
        order = self._orders[order_id]
        price = snapshot.ask if order["side"] == "LONG" else snapshot.bid
        marketable = (
            price is not None and (
                (order["side"] == "LONG" and price <= order["limit_price"])
                or (order["side"] == "SHORT" and price >= order["limit_price"])
            )
        )
        if not marketable or fraction <= 0:
            return
        quantity = min(order["remaining_quantity"], order["quantity"] * fraction)
        if quantity <= 0:
            return
        prior_value = (order["average_fill_price"] or 0.0) * order["filled_quantity"]
        order["filled_quantity"] += quantity
        order["remaining_quantity"] -= quantity
        order["average_fill_price"] = (prior_value + float(price) * quantity) / order["filled_quantity"]
        fee = self.fill_config.fee_per_contract * quantity
        fill = {
            "fill_id": new_id("paper-tasty-fill"), "order_id": order_id, "symbol": order["symbol"],
            "side": order["side"], "quantity": quantity, "price": price, "fee": fee,
            "created_at": utc_now().isoformat().replace("+00:00", "Z"),
        }
        self._fills.append(fill)
        position = self._positions.setdefault(order["symbol"], {
            "signed_quantity": 0.0, "average_entry": 0.0, "multiplier": order["multiplier"],
            "fees": 0.0, "realized_pnl": 0.0,
        })
        signed = quantity if order["side"] == "LONG" else -quantity
        prior_abs = abs(position["signed_quantity"])
        position["average_entry"] = (
            (position["average_entry"] * prior_abs + float(price) * quantity) / (prior_abs + quantity)
            if prior_abs + quantity else 0.0
        )
        position["signed_quantity"] += signed
        position["fees"] += fee
        self.ledger.append(
            "fills", fill, correlation_id=order["correlation_id"], source_id=fill["fill_id"],
            venue="TASTY_PAPER",
        )
        lifecycle = self._lifecycles[order_id]
        if order["remaining_quantity"] > 1e-12:
            order["state"] = OrderState.PARTIAL.value
            self._record_event(lifecycle.transition(OrderState.PARTIAL, reason="paper partial fill"), order)
        else:
            order["state"] = OrderState.FILLED.value
            self._record_event(lifecycle.transition(OrderState.FILLED, reason="paper fill complete"), order)
            order["state"] = OrderState.POSITION_OPEN.value
            self._record_event(lifecycle.transition(OrderState.POSITION_OPEN, reason="paper position opened"), order)
            self.ledger.append(
                "positions", dict(position, symbol=order["symbol"]),
                correlation_id=order["correlation_id"], source_id=fill["fill_id"], venue="TASTY_PAPER",
            )

    def cancel_order(self, order_id: str) -> Mapping[str, Any]:
        order = self._orders[order_id]
        if order["state"] not in {OrderState.RESTING.value, OrderState.PARTIAL.value}:
            raise RuntimeError("only resting or partial paper orders can be cancelled")
        order["state"] = OrderState.CANCELLED.value
        self._record_event(
            self._lifecycles[order_id].transition(OrderState.CANCELLED, reason="paper cancellation"), order
        )
        return {"order_id": order_id, "state": order["state"], "cancelled_quantity": order["remaining_quantity"]}

    def replace_order(self, order_id: str, order: ApprovedOrder) -> Mapping[str, Any]:
        self.cancel_order(order_id)
        return self.submit_order(order).__dict__

    def get_order(self, order_id: str) -> Mapping[str, Any]:
        return dict(self._orders[order_id])

    def get_fills(self, order_id: str | None = None) -> Mapping[str, Any]:
        fills = self._fills if order_id is None else [fill for fill in self._fills if fill["order_id"] == order_id]
        return {"fills": [dict(fill) for fill in fills]}

    def settle_to_price(self, symbol: str, *, settlement_price: float, correlation_id: str) -> Mapping[str, Any]:
        position = self._positions.get(symbol)
        if position is None or position["signed_quantity"] == 0:
            raise RuntimeError("no open paper position")
        pnl = (
            (settlement_price - position["average_entry"])
            * position["signed_quantity"]
            * position["multiplier"]
            - position["fees"]
        )
        settlement = {
            "settlement_id": new_id("paper-tasty-settlement"), "symbol": symbol,
            "settlement_price": settlement_price, "entry_price": position["average_entry"],
            "quantity": position["signed_quantity"], "multiplier": position["multiplier"],
            "fees": position["fees"], "realized_pnl": pnl,
        }
        position["realized_pnl"] += pnl
        position["signed_quantity"] = 0.0
        self.ledger.append(
            "settlements", settlement, correlation_id=correlation_id,
            source_id=settlement["settlement_id"], venue="TASTY_PAPER",
        )
        self.ledger.append(
            "pnl_snapshots", settlement, correlation_id=correlation_id,
            source_id=settlement["settlement_id"], venue="TASTY_PAPER",
        )
        for order_id, order in self._orders.items():
            if order["symbol"] == symbol and order["state"] == OrderState.POSITION_OPEN.value:
                order["state"] = OrderState.SETTLED.value
                self._record_event(
                    self._lifecycles[order_id].transition(OrderState.SETTLED, reason="paper settlement"), order
                )
        return settlement

    def _record_event(self, event: Any, order: Mapping[str, Any]) -> None:
        self.ledger.append(
            "order_events", {"event": event, "order_state": order["state"], "order_id": order["order_id"]},
            correlation_id=order["correlation_id"], source_id=event.event_id, venue="TASTY_PAPER",
        )

    @staticmethod
    def _result(order: Mapping[str, Any]) -> TastyOrderResult:
        return TastyOrderResult(
            order_id=str(order["order_id"]), client_order_id=str(order["client_order_id"]),
            state=str(order["state"]), filled_quantity=float(order["filled_quantity"]),
            remaining_quantity=float(order["remaining_quantity"]),
            average_fill_price=order["average_fill_price"], raw_source_hash=hash_payload(order),
        )
