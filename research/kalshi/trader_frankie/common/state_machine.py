"""Explicit fail-closed order lifecycle state machine."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .hashing import hash_payload, new_id, utc_now
from .models import OrderState


class InvalidTransition(RuntimeError):
    pass


ALLOWED_TRANSITIONS: dict[OrderState, frozenset[OrderState]] = {
    OrderState.INTENT_CREATED: frozenset({OrderState.RISK_PENDING, OrderState.EXPIRED, OrderState.REJECTED}),
    OrderState.RISK_PENDING: frozenset({OrderState.RISK_APPROVED, OrderState.RISK_REJECTED, OrderState.ERROR_SAFE}),
    OrderState.RISK_APPROVED: frozenset({OrderState.SUBMIT_PENDING, OrderState.EXPIRED, OrderState.ERROR_SAFE}),
    OrderState.SUBMIT_PENDING: frozenset({OrderState.SUBMITTED, OrderState.REJECTED, OrderState.ERROR_SAFE}),
    OrderState.SUBMITTED: frozenset({OrderState.RESTING, OrderState.PARTIAL, OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED, OrderState.ERROR_SAFE}),
    OrderState.RESTING: frozenset({OrderState.PARTIAL, OrderState.FILLED, OrderState.CANCELLED, OrderState.EXPIRED, OrderState.ERROR_SAFE}),
    OrderState.PARTIAL: frozenset({OrderState.PARTIAL, OrderState.FILLED, OrderState.CANCELLED, OrderState.ERROR_SAFE}),
    OrderState.FILLED: frozenset({OrderState.POSITION_OPEN, OrderState.SETTLED, OrderState.ERROR_SAFE}),
    OrderState.POSITION_OPEN: frozenset({OrderState.EXIT_INTENT, OrderState.SETTLED, OrderState.ERROR_SAFE}),
    OrderState.EXIT_INTENT: frozenset({OrderState.EXIT_ORDER, OrderState.EXPIRED, OrderState.REJECTED, OrderState.ERROR_SAFE}),
    OrderState.EXIT_ORDER: frozenset({OrderState.POSITION_CLOSED, OrderState.ERROR_SAFE}),
    OrderState.POSITION_CLOSED: frozenset({OrderState.SETTLED}),
}
TERMINAL_STATES = frozenset({
    OrderState.RISK_REJECTED, OrderState.CANCELLED, OrderState.EXPIRED, OrderState.REJECTED,
    OrderState.ERROR_SAFE, OrderState.SETTLED,
})


@dataclass(frozen=True)
class LifecycleEvent:
    event_id: str
    aggregate_id: str
    from_state: str | None
    to_state: str
    created_at: str
    reason: str
    details_hash: str


class OrderLifecycle:
    def __init__(self, aggregate_id: str) -> None:
        self.aggregate_id = aggregate_id
        self.state: OrderState | None = None

    def transition(
        self, target: OrderState, *, reason: str, details: Mapping[str, Any] | None = None
    ) -> LifecycleEvent:
        if self.state is None:
            if target is not OrderState.INTENT_CREATED:
                raise InvalidTransition("lifecycle must begin at INTENT_CREATED")
        elif self.state in TERMINAL_STATES:
            raise InvalidTransition(f"terminal state {self.state.value} cannot transition")
        elif target not in ALLOWED_TRANSITIONS.get(self.state, frozenset()):
            prior = self.state
            self.state = OrderState.ERROR_SAFE
            raise InvalidTransition(f"unexpected transition {prior.value} -> {target.value}; failed closed")
        prior = self.state
        self.state = target
        return LifecycleEvent(
            event_id=new_id("order-event"),
            aggregate_id=self.aggregate_id,
            from_state=prior.value if prior else None,
            to_state=target.value,
            created_at=utc_now().isoformat().replace("+00:00", "Z"),
            reason=reason,
            details_hash=hash_payload(details or {}),
        )
