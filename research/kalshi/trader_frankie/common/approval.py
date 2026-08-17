"""Risk-issued order capability that brokers require before submission."""
from __future__ import annotations

import json
from types import MappingProxyType
from typing import Any, Mapping

from .hashing import hash_payload, new_id

_ISSUER = object()


class ApprovalError(RuntimeError):
    pass


class ApprovedOrder:
    __slots__ = (
        "approval_id", "risk_decision_id", "venue", "route", "client_order_id",
        "intent_id", "intent_hash", "payload", "approval_hash", "_issuer", "_locked",
    )

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_locked", False):
            raise ApprovalError("ApprovedOrder is immutable")
        object.__setattr__(self, name, value)

    def __init__(
        self,
        *,
        risk_decision_id: str,
        venue: str,
        route: str,
        client_order_id: str,
        intent_id: str,
        intent_hash: str,
        payload: Mapping[str, Any],
        _issuer: object,
    ) -> None:
        if _issuer is not _ISSUER:
            raise ApprovalError("ApprovedOrder may only be issued by a deterministic Risk Governor")
        detached = json.loads(json.dumps(dict(payload), allow_nan=False))
        self.approval_id = new_id("approval")
        self.risk_decision_id = risk_decision_id
        self.venue = venue
        self.route = route
        self.client_order_id = client_order_id
        self.intent_id = intent_id
        self.intent_hash = intent_hash
        self.payload = MappingProxyType(detached)
        self.approval_hash = hash_payload(self.as_dict(include_hash=False))
        self._issuer = _issuer
        self._locked = True

    def as_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        value = {
            "approval_id": self.approval_id,
            "risk_decision_id": self.risk_decision_id,
            "venue": self.venue,
            "route": self.route,
            "client_order_id": self.client_order_id,
            "intent_id": self.intent_id,
            "intent_hash": self.intent_hash,
            "payload": dict(self.payload),
        }
        if include_hash:
            value["approval_hash"] = self.approval_hash
        return value


def _issue_approved_order(**kwargs: Any) -> ApprovedOrder:
    return ApprovedOrder(_issuer=_ISSUER, **kwargs)


def require_approved_order(order: ApprovedOrder, *, venue: str | None = None) -> None:
    if not isinstance(order, ApprovedOrder) or getattr(order, "_issuer", None) is not _ISSUER:
        raise ApprovalError("executor accepts only a Risk Governor ApprovedOrder")
    if venue is not None and order.venue != venue:
        raise ApprovalError(f"approval venue {order.venue!r} does not match broker {venue!r}")
    observed = hash_payload(order.as_dict(include_hash=False))
    if observed != order.approval_hash:
        raise ApprovalError("approved order payload changed after risk approval")
