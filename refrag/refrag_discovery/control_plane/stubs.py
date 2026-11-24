from __future__ import annotations

from typing import Any


CONTROL_PLANE_STUBS: dict[str, str] = {}


def get_control_plane_stub(operator_id: str) -> dict[str, Any]:
    message = CONTROL_PLANE_STUBS.get(operator_id)
    if message is None:
        raise KeyError(operator_id)
    return {
        "operator_id": operator_id,
        "status": "stubbed",
        "message": message,
    }
