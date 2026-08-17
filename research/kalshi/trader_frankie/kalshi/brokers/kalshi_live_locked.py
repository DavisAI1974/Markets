"""Mechanically unavailable Kalshi live adapter."""
from __future__ import annotations

from typing import Any, Mapping

from ...common.approval import ApprovedOrder


class LiveExecutionLocked(RuntimeError):
    pass


class KalshiLiveBrokerLocked:
    route_name = "kalshi_live_locked"

    @staticmethod
    def _locked() -> None:
        raise LiveExecutionLocked(
            "Kalshi live execution is mechanically unavailable in v1; no runtime flag can unlock it"
        )

    def get_market(self, ticker: str) -> Mapping[str, Any]:
        del ticker
        self._locked()
        return {}

    def get_orderbook(self, ticker: str) -> Mapping[str, Any]:
        del ticker
        self._locked()
        return {}

    def get_balance(self) -> Mapping[str, Any]:
        self._locked(); return {}

    def get_positions(self) -> Mapping[str, Any]:
        self._locked(); return {}

    def get_orders(self) -> Mapping[str, Any]:
        self._locked(); return {}

    def submit_order(self, order: ApprovedOrder) -> Any:
        del order
        self._locked()

    def cancel_order(self, order_id: str) -> Mapping[str, Any]:
        del order_id
        self._locked(); return {}

    def get_order(self, order_id: str) -> Mapping[str, Any]:
        del order_id
        self._locked(); return {}

    def get_fills(self, order_id: str | None = None) -> Mapping[str, Any]:
        del order_id
        self._locked(); return {}


class KalshiLiveBroker(KalshiLiveBrokerLocked):
    """Name exists for imports only; behavior remains locked."""
