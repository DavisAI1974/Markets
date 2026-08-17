"""Local immutable-ledger paper engine for Kalshi event contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ...common.approval import ApprovedOrder, require_approved_order
from ...common.hashing import hash_payload, new_id, utc_now
from ...common.ledger import ImmutableTradingLedger
from ...common.models import OrderState
from ...common.state_machine import OrderLifecycle
from ..models import KalshiMarketSnapshot
from .base import BrokerOrderResult


@dataclass(frozen=True)
class PaperFillConfig:
    immediate_fill_fraction: float
    fee_per_contract: float


class PaperLedgerBroker:
    """Simulates resting, partial/full fills, cancellation, positions, and settlement."""

    def __init__(
        self,
        *,
        ledger: ImmutableTradingLedger,
        fill_config: PaperFillConfig,
        route_name: str = "paper_ledger",
    ) -> None:
        if not 0 <= fill_config.immediate_fill_fraction <= 1:
            raise ValueError("immediate_fill_fraction must be between 0 and 1")
        self.ledger = ledger
        self.fill_config = fill_config
        self.route_name = route_name
        self._snapshots: dict[str, KalshiMarketSnapshot] = {}
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
            if row["venue"] != "KALSHI_PAPER":
                continue
            order = dict(row["payload"])
            self._orders[str(order["order_id"])] = order
        last_state: dict[str, str] = {}
        for row in self.ledger.read("order_events"):
            if row["venue"] == "KALSHI_PAPER":
                payload = row["payload"]
                last_state[str(payload["order_id"])] = str(payload["order_state"])
        for row in self.ledger.read("fills"):
            if row["venue"] != "KALSHI_PAPER":
                continue
            fill = dict(row["payload"])
            self._fills.append(fill)
            order = self._orders.get(str(fill["order_id"]))
            if order is None:
                continue
            quantity = float(fill["count"])
            price = float(fill["price"])
            prior_value = (order.get("average_fill_price") or 0.0) * float(order.get("filled_count", 0.0))
            order["filled_count"] = float(order.get("filled_count", 0.0)) + quantity
            order["remaining_count"] = max(0.0, float(order["count"]) - order["filled_count"])
            order["average_fill_price"] = (prior_value + price * quantity) / order["filled_count"]
            sign = 1.0 if fill["outcome_exposure"] == "YES" else -1.0
            position = self._positions.setdefault(str(fill["ticker"]), {
                "yes_equivalent_count": 0.0, "cost": 0.0, "fees": 0.0, "realized_pnl": 0.0,
            })
            position["yes_equivalent_count"] += sign * quantity
            position["cost"] += price * quantity
            position["fees"] += float(fill["fee"])
        for row in self.ledger.read("settlements"):
            if row["venue"] != "KALSHI_PAPER":
                continue
            settlement = row["payload"]
            position = self._positions.get(str(settlement["ticker"]))
            if position is not None:
                position["yes_equivalent_count"] = 0.0
                position["realized_pnl"] += float(settlement["realized_pnl"])
        for order_id, order in self._orders.items():
            order["state"] = last_state.get(order_id, str(order.get("state") or OrderState.ERROR_SAFE.value))
            lifecycle = OrderLifecycle(order_id)
            lifecycle.state = OrderState(order["state"])
            self._lifecycles[order_id] = lifecycle

    def ingest_snapshot(self, snapshot: KalshiMarketSnapshot) -> None:
        self._snapshots[snapshot.ticker] = snapshot

    def get_market(self, ticker: str) -> Mapping[str, Any]:
        snapshot = self._snapshots.get(ticker)
        return snapshot.as_dict() if snapshot else {}

    def get_orderbook(self, ticker: str) -> Mapping[str, Any]:
        snapshot = self._snapshots.get(ticker)
        if snapshot is None:
            return {}
        return {
            "ticker": ticker,
            "yes_bid": snapshot.yes_bid,
            "yes_ask": snapshot.yes_ask,
            "no_bid": snapshot.no_bid,
            "no_ask": snapshot.no_ask,
            "book_hash": snapshot.book_hash,
        }

    def get_balance(self) -> Mapping[str, Any]:
        realized = sum(position.get("realized_pnl", 0.0) for position in self._positions.values())
        return {"mode": "paper", "realized_pnl": realized}

    def get_positions(self) -> Mapping[str, Any]:
        return {"market_positions": [dict(value, ticker=ticker) for ticker, value in self._positions.items()]}

    def get_orders(self) -> Mapping[str, Any]:
        return {"orders": [dict(order) for order in self._orders.values()]}

    def submit_order(self, order: ApprovedOrder) -> BrokerOrderResult:
        require_approved_order(order, venue="KALSHI_EVENT")
        if order.route != self.route_name:
            raise RuntimeError(f"approval route {order.route!r} does not match {self.route_name!r}")
        if any(item["client_order_id"] == order.client_order_id for item in self._orders.values()):
            raise RuntimeError("duplicate client_order_id")
        payload = dict(order.payload)
        ticker = str(payload["ticker"])
        snapshot = self._snapshots.get(ticker)
        if snapshot is None or snapshot.status.lower() != "open":
            raise RuntimeError("paper submission requires a current open snapshot")
        order_id = new_id("paper-kalshi-order")
        count = float(payload["count"])
        economic_limit = float(payload["economic_max_price"])
        outcome = str(payload["outcome_exposure"])
        record = {
            "order_id": order_id,
            "approval_id": order.approval_id,
            "client_order_id": order.client_order_id,
            "ticker": ticker,
            "outcome_exposure": outcome,
            "limit_price": economic_limit,
            "time_in_force": str(payload["time_in_force"]),
            "count": count,
            "filled_count": 0.0,
            "remaining_count": count,
            "average_fill_price": None,
            "state": OrderState.SUBMITTED.value,
            "correlation_id": order.intent_id,
        }
        self._orders[order_id] = record
        lifecycle = OrderLifecycle(order_id)
        self._lifecycles[order_id] = lifecycle
        self._record_event(lifecycle.transition(OrderState.INTENT_CREATED, reason="approved intent"), record)
        self._record_event(lifecycle.transition(OrderState.RISK_PENDING, reason="risk decision recorded"), record)
        self._record_event(lifecycle.transition(OrderState.RISK_APPROVED, reason=order.risk_decision_id), record)
        self._record_event(lifecycle.transition(OrderState.SUBMIT_PENDING, reason="paper submit"), record)
        self._record_event(lifecycle.transition(OrderState.SUBMITTED, reason="paper order accepted"), record)
        self.ledger.append(
            "orders", record, correlation_id=order.intent_id, source_id=order_id, venue="KALSHI_PAPER",
        )
        self._try_fill(order_id, snapshot, self.fill_config.immediate_fill_fraction)
        current = self._orders[order_id]
        if current["remaining_count"] > 0 and current["time_in_force"] != "good_till_canceled":
            current["state"] = OrderState.CANCELLED.value
            self._record_event(
                lifecycle.transition(OrderState.CANCELLED, reason="paper time-in-force remainder cancelled"),
                current,
            )
        elif current["filled_count"] == 0:
            current["state"] = OrderState.RESTING.value
            self._record_event(lifecycle.transition(OrderState.RESTING, reason="limit not marketable"), current)
        return self._result(current)

    def process_snapshot(self, snapshot: KalshiMarketSnapshot, *, fill_fraction: float = 1.0) -> None:
        if not 0 <= fill_fraction <= 1:
            raise ValueError("fill_fraction must be between 0 and 1")
        self.ingest_snapshot(snapshot)
        for order_id, order in tuple(self._orders.items()):
            if order["ticker"] == snapshot.ticker and order["state"] in {
                OrderState.RESTING.value, OrderState.PARTIAL.value,
            }:
                self._try_fill(order_id, snapshot, fill_fraction)

    def _try_fill(self, order_id: str, snapshot: KalshiMarketSnapshot, fraction: float) -> None:
        order = self._orders[order_id]
        ask = snapshot.yes_ask if order["outcome_exposure"] == "YES" else snapshot.no_ask
        if ask is None or ask > order["limit_price"] or fraction <= 0 or order["remaining_count"] <= 0:
            return
        if order["time_in_force"] == "fill_or_kill" and fraction < 1.0:
            return
        quantity = min(order["remaining_count"], order["count"] * fraction)
        if quantity <= 0:
            return
        previous_value = (order["average_fill_price"] or 0.0) * order["filled_count"]
        order["filled_count"] += quantity
        order["remaining_count"] -= quantity
        order["average_fill_price"] = (previous_value + ask * quantity) / order["filled_count"]
        fee = self.fill_config.fee_per_contract * quantity
        fill = {
            "fill_id": new_id("paper-kalshi-fill"),
            "order_id": order_id,
            "ticker": order["ticker"],
            "outcome_exposure": order["outcome_exposure"],
            "count": quantity,
            "price": ask,
            "fee": fee,
            "created_at": utc_now().isoformat().replace("+00:00", "Z"),
        }
        self._fills.append(fill)
        sign = 1.0 if order["outcome_exposure"] == "YES" else -1.0
        position = self._positions.setdefault(order["ticker"], {
            "yes_equivalent_count": 0.0, "cost": 0.0, "fees": 0.0, "realized_pnl": 0.0,
        })
        position["yes_equivalent_count"] += sign * quantity
        position["cost"] += ask * quantity
        position["fees"] += fee
        self.ledger.append(
            "fills", fill, correlation_id=order["correlation_id"], source_id=fill["fill_id"],
            venue="KALSHI_PAPER",
        )
        lifecycle = self._lifecycles[order_id]
        if order["remaining_count"] > 1e-12:
            order["state"] = OrderState.PARTIAL.value
            self._record_event(lifecycle.transition(OrderState.PARTIAL, reason="paper partial fill"), order)
        else:
            order["state"] = OrderState.FILLED.value
            self._record_event(lifecycle.transition(OrderState.FILLED, reason="paper fill complete"), order)
            order["state"] = OrderState.POSITION_OPEN.value
            self._record_event(lifecycle.transition(OrderState.POSITION_OPEN, reason="paper position opened"), order)
            self.ledger.append(
                "positions", dict(position, ticker=order["ticker"]),
                correlation_id=order["correlation_id"], source_id=fill["fill_id"], venue="KALSHI_PAPER",
            )

    def cancel_order(self, order_id: str) -> Mapping[str, Any]:
        order = self._orders[order_id]
        if order["state"] not in {OrderState.RESTING.value, OrderState.PARTIAL.value}:
            raise RuntimeError("only resting or partial paper orders can be cancelled")
        order["state"] = OrderState.CANCELLED.value
        self._record_event(
            self._lifecycles[order_id].transition(OrderState.CANCELLED, reason="paper cancellation"), order
        )
        return {"order_id": order_id, "reduced_by": order["remaining_count"], "state": order["state"]}

    def get_order(self, order_id: str) -> Mapping[str, Any]:
        return dict(self._orders[order_id])

    def get_fills(self, order_id: str | None = None) -> Mapping[str, Any]:
        fills = self._fills if order_id is None else [fill for fill in self._fills if fill["order_id"] == order_id]
        return {"fills": [dict(fill) for fill in fills]}

    def settle(self, ticker: str, *, winning_outcome: str, correlation_id: str) -> Mapping[str, Any]:
        if winning_outcome not in {"YES", "NO"}:
            raise ValueError("winning_outcome must be YES or NO")
        position = self._positions.get(ticker)
        if position is None:
            raise RuntimeError("no paper position to settle")
        net_yes = position["yes_equivalent_count"]
        yes_count = max(0.0, net_yes)
        no_count = max(0.0, -net_yes)
        payout = yes_count if winning_outcome == "YES" else no_count
        pnl = payout - position["cost"] - position["fees"]
        position["realized_pnl"] += pnl
        position["yes_equivalent_count"] = 0.0
        settlement = {
            "settlement_id": new_id("paper-kalshi-settlement"),
            "ticker": ticker,
            "winning_outcome": winning_outcome,
            "payout": payout,
            "cost": position["cost"],
            "fees": position["fees"],
            "realized_pnl": pnl,
        }
        self.ledger.append(
            "settlements", settlement, correlation_id=correlation_id,
            source_id=settlement["settlement_id"], venue="KALSHI_PAPER",
        )
        self.ledger.append(
            "pnl_snapshots", settlement, correlation_id=correlation_id,
            source_id=settlement["settlement_id"], venue="KALSHI_PAPER",
        )
        for order_id, order in self._orders.items():
            if order["ticker"] == ticker and order["state"] == OrderState.POSITION_OPEN.value:
                order["state"] = OrderState.SETTLED.value
                self._record_event(
                    self._lifecycles[order_id].transition(OrderState.SETTLED, reason="paper settlement"), order
                )
        return settlement

    def _record_event(self, event: Any, order: Mapping[str, Any]) -> None:
        self.ledger.append(
            "order_events", {
                "event": event,
                "order_state": order["state"],
                "order_id": order["order_id"],
            }, correlation_id=order["correlation_id"], source_id=event.event_id,
            venue="KALSHI_PAPER",
        )

    @staticmethod
    def _result(order: Mapping[str, Any]) -> BrokerOrderResult:
        return BrokerOrderResult(
            order_id=str(order["order_id"]),
            client_order_id=str(order["client_order_id"]),
            state=str(order["state"]),
            filled_count=float(order["filled_count"]),
            remaining_count=float(order["remaining_count"]),
            average_fill_price=order["average_fill_price"],
            raw_source_hash=hash_payload(order),
        )
