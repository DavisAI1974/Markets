"""Provider-neutral structured-reasoning boundary for the two trader agents."""
from __future__ import annotations

from typing import Any, Callable, Mapping, Protocol


class DecisionBackend(Protocol):
    def generate(
        self, *, agent_id: str, instructions: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...


class StandDownBackend:
    """Fail-closed backend used until an approved provider is wired outside the agent."""

    def __init__(self, reason: str = "reasoning backend not configured") -> None:
        self.reason = reason

    def generate(
        self, *, agent_id: str, instructions: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        del agent_id, instructions, payload
        return {"decision": "STAND_DOWN", "reason": self.reason}


class CallableBackend:
    def __init__(self, function: Callable[..., Mapping[str, Any]]) -> None:
        self.function = function

    def generate(
        self, *, agent_id: str, instructions: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        result = self.function(agent_id=agent_id, instructions=instructions, payload=payload)
        if not isinstance(result, Mapping):
            raise TypeError("reasoning backend must return a mapping")
        return result
