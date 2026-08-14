#!/usr/bin/env python3
"""S126 specialist parity guard for the current Frankie packet.

This is wiring only. It does not rewrite specialist A-E roles, spawn.py, the brain, the
forecast schema, decision settings, or decision-state inputs. The specialist receives the
same already-served causal data universe Frankie receives, after the existing causal/blind
filters have done their work. Frankie remains the coordinator.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import frankie_s118_redo as s120

ForecastStop = s120.ForecastStop
SPECIALISTS = tuple("ABCDE")


def attach_specialist_access(
    payload: dict[str, Any], *, specialist: str, phase: str = "BLIND"
) -> dict[str, Any]:
    """Attach and enforce the shared A-E access contract without filtering data by role."""
    spec = str(specialist).upper()
    if spec not in SPECIALISTS:
        raise ForecastStop(f"specialist parity requires one of {SPECIALISTS}; got {specialist!r}")

    phase_norm = str(phase).upper()
    causal_slice = payload.get("causal_slice")
    if not isinstance(causal_slice, Mapping):
        raise ForecastStop("specialist parity requires the complete served causal_slice mapping")

    brain = payload.get("brain_view_served")
    if not isinstance(brain, Mapping):
        raise ForecastStop("specialist parity requires brain_view_served")
    serving = brain.get("_frankie_serving")
    plays = brain.get("plays")
    if not isinstance(serving, Mapping) or not isinstance(plays, Mapping):
        raise ForecastStop("specialist parity requires full Frankie brain serving telemetry")
    canonical = int(serving.get("canonical_plays_total", -1))
    served = int(serving.get("full_plays_served", -1))
    if canonical < 1 or served != canonical or len(plays) != canonical:
        raise ForecastStop(
            "specialist parity refuses a reduced brain: "
            f"canonical={canonical} served={served} bodies={len(plays)}"
        )

    if phase_norm == "BLIND" and payload.get("realized_outcome_in_packet") is not False:
        raise ForecastStop("blind specialist parity packet attempted to carry realized outcome")

    out = dict(payload)
    out["specialist_access_contract"] = {
        "version": "s126.specialist-parity.1",
        "coordinator": "Frankie",
        "specialists": list(SPECIALISTS),
        "active_specialist": spec,
        "data_universe_key": "causal_slice",
        "data_universe": "complete already-served Frankie causal slice; no role-based field filtering",
        "brain_universe_key": "brain_view_served",
        "canonical_plays": canonical,
        "full_plays_served": served,
        "role_text_rewritten": False,
        "frankie_settings_changed": False,
        "frankie_schema_changed": False,
        "frankie_inputs_changed": False,
        "causal_blind_wall": "preserved; this adapter only consumes the already-filtered served packet",
        "consultation_rule": "availability is complete; each specialist decides relevance inside its existing role",
    }
    return out


def packet(
    template: str,
    gid: str,
    day: str,
    spec: str,
    namespace: str,
    *,
    bridge_deviation: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Current S120 packet plus the shared A-E parity contract; no data replacement."""
    prompt, payload = s120.packet(
        template,
        gid,
        day,
        spec,
        namespace,
        bridge_deviation=bridge_deviation,
    )
    return prompt, attach_specialist_access(payload, specialist=spec, phase="BLIND")


def install() -> None:
    """Install parity after S120 so its full-brain and A-82 guards remain authoritative."""
    s120.install()
    s120.base._packet = packet


if __name__ == "__main__":
    install()
    print("S126 READY: Frankie coordinator; A-E full served-data parity; roles unchanged")
