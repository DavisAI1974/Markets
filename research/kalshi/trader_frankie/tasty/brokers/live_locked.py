"""Mechanically unavailable tastytrade production adapter."""
from __future__ import annotations

from typing import Any, Mapping

from ...common.approval import ApprovedOrder


class TastyLiveExecutionLocked(RuntimeError):
    pass


class TastyLiveBrokerLocked:
    route_name = "tasty_live_locked"

    @staticmethod
    def _locked() -> None:
        raise TastyLiveExecutionLocked(
            "tastytrade live execution is mechanically unavailable in v1; no runtime flag can unlock it"
        )

    def get_instrument(self, symbol: str, instrument_type: str) -> Mapping[str, Any]:
        del symbol, instrument_type
        self._locked(); return {}

    def get_balance(self) -> Mapping[str, Any]:
        self._locked(); return {}

    def get_positions(self) -> Mapping[str, Any]:
        self._locked(); return {}

    def get_orders(self) -> Mapping[str, Any]:
        self._locked(); return {}

    def get_margin_requirements(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        del payload
        self._locked(); return {}

    def dry_run_order(self, order: ApprovedOrder) -> Mapping[str, Any]:
        del order
        self._locked(); return {}

    def submit_order(self, order: ApprovedOrder) -> Any:
        del order
        self._locked()

    def cancel_order(self, order_id: str) -> Mapping[str, Any]:
        del order_id
        self._locked(); return {}

    def replace_order(self, order_id: str, order: ApprovedOrder) -> Mapping[str, Any]:
        del order_id, order
        self._locked(); return {}

    def get_order(self, order_id: str) -> Mapping[str, Any]:
        del order_id
        self._locked(); return {}


class TastyLiveBroker(TastyLiveBrokerLocked):
    """Name exists for imports only; behavior remains locked."""
