from __future__ import annotations

from pathlib import Path
from typing import Any

from refrag_discovery.control_plane.storage import load_json, operator_state_path, save_json, utc_now_iso
from refrag_discovery.registry import build_default_operator_query


VALID_STATES = {"experimental", "candidate", "stable", "deprecated", "promoted"}
STATE_ORDER = {
    "deprecated": -1,
    "experimental": 0,
    "candidate": 1,
    "stable": 2,
    "promoted": 3,
}


def _normalize_state(value: str | None) -> str:
    normalized = str(value or "experimental").strip().lower()
    if normalized == "beta":
        normalized = "candidate"
    if normalized not in VALID_STATES:
        raise ValueError(f"Unsupported lifecycle state: {value}")
    return normalized


def _initial_state(operator_id: str) -> str:
    manifest = build_default_operator_query().get_manifest(operator_id)
    return _normalize_state(str(manifest.get("maturity", "experimental")))


def _drift_status(current_state: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    recent = history[-5:]
    negative_transitions = 0
    drift_reasons: list[str] = []
    for item in recent:
        previous = _normalize_state(item.get("from_state"))
        current = _normalize_state(item.get("to_state"))
        if STATE_ORDER[current] < STATE_ORDER[previous]:
            negative_transitions += 1
        reason = str(item.get("reason", "")).lower()
        if "drift" in reason:
            drift_reasons.append(reason)

    drift_detected = negative_transitions > 0 or current_state == "deprecated" or bool(drift_reasons)
    signal = "stable"
    if drift_detected:
        signal = "negative"
    elif recent:
        signal = "positive"

    return {
        "drift_detected": drift_detected,
        "signal": signal,
        "adwin_proxy_window": len(history),
        "negative_transitions_in_window": negative_transitions,
    }


def _survival_estimate(current_state: str, drift_status: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    base_days = {
        "experimental": 21.0,
        "candidate": 45.0,
        "stable": 120.0,
        "promoted": 180.0,
        "deprecated": 0.0,
    }[current_state]
    hazard_rate = {
        "experimental": 0.09,
        "candidate": 0.05,
        "stable": 0.02,
        "promoted": 0.01,
        "deprecated": 1.0,
    }[current_state]
    hazard_rate += 0.03 * drift_status.get("negative_transitions_in_window", 0)
    if drift_status.get("drift_detected"):
        hazard_rate += 0.05

    decay = 1.0 + (len(history) / 20.0)
    median_remaining_days = round(max(0.0, base_days / decay), 2)
    confidence_interval_days = [
        round(max(0.0, median_remaining_days * 0.75), 2),
        round(median_remaining_days * 1.25, 2),
    ]

    return {
        "median_remaining_days": median_remaining_days,
        "hazard_rate": round(hazard_rate, 4),
        "confidence_interval_days": confidence_interval_days,
    }


def track_operator_lifecycle(
    *,
    operator_id: str,
    transition_to: str | None = None,
    reason: str | None = None,
    evidence: list[str] | None = None,
    approved_by: str | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    path = operator_state_path("lifecycle", operator_id, artifacts_dir)
    state = load_json(
        path,
        {
            "operator_id": operator_id,
            "current_state": _initial_state(operator_id),
            "history": [],
        },
    )

    current_state = _normalize_state(state.get("current_state"))
    history = list(state.get("history", []))
    transition_recorded = False

    if transition_to is not None:
        next_state = _normalize_state(transition_to)
        history.append(
            {
                "from_state": current_state,
                "to_state": next_state,
                "reason": str(reason or ""),
                "evidence": list(evidence or []),
                "approved_by": str(approved_by or ""),
                "recorded_at": utc_now_iso(),
            }
        )
        current_state = next_state
        transition_recorded = True

    save_json(
        path,
        {
            "operator_id": operator_id,
            "current_state": current_state,
            "history": history,
        },
    )

    drift_status = _drift_status(current_state, history)
    survival_estimate = _survival_estimate(current_state, drift_status, history)
    return {
        "transition_recorded": transition_recorded,
        "current_state": current_state,
        "transition_history": history,
        "drift_status": drift_status,
        "survival_estimate": survival_estimate,
    }
