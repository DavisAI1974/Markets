#!/usr/bin/env python3
"""S135 canonical CURRENT-FRANKIE runtime seam.

Purpose
-------
Prior group runs could accidentally install only one of Frankie's additive runtime layers. S135 makes
one composition point the required entry for every new group run.

S135 composes, in order:
- S120 full-current-brain availability + existing outcome wall;
- S132 event-driven full-curve contract (no fixed clock, no flat-ABSTAIN rule);
- S133 reasoning-authority contract + explicit sequential/live/refine prior-session carry;
- S126 A-E specialist parity over the complete already-served data/brain universe;
- S128 current decision-state contract repairs through the exported decision_state() proxy;
- S135 specialist authority contracts for C/D/E and the A weekend bridge.

It does NOT edit the brain, A-E role files, spawn.py, group_config.py, or add a datapoint family.
Hydration is not part of this runtime. Frankie remains coordinator. Day owners are not averaged.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import brain_view
import frankie_s118_redo as s120
import frankie_s128_contract_repairs as s128
import frankie_s132_dynamic_curve as s132
import frankie_s133_reasoning_runtime as s133
import frankie_s135_specialist_authority as authority
import frankie_specialist_parity_s126 as s126
from frankie_core import verify_original_spawn

base = s133.base
ForecastStop = s133.ForecastStop
SPECIALISTS = tuple("ABCDE")
STACK_VERSION = "s135.current-frankie.2"


def decision_state(days, mask_after=None, group=None):
    """The only S135 decision-state entry: current S128 repairs + explicit group/mask parameters."""
    if group is None:
        raise ForecastStop("S135 refuses decision_state without explicit group context")
    return s128.decision_state(days, mask_after=mask_after, group=group)


def _attach(payload: dict[str, Any], *, specialist: str, phase: str,
            task: str = "day_forecast", information_state: str = "open") -> dict[str, Any]:
    out = s126.attach_specialist_access(payload, specialist=specialist, phase=phase)
    out = authority.attach(
        out, specialist=specialist, phase=phase, task=task, information_state=information_state
    )
    out["s135_current_frankie_stack"] = {
        "version": STACK_VERSION,
        "s120_full_current_brain": True,
        "s126_specialist_parity": True,
        "s128_decision_state_repairs": True,
        "s132_event_driven_curve": True,
        "s133_reasoning_authority": True,
        "s135_specialist_authority": True,
        "fixed_curve_clock": False,
        "fixed_curve_point_count": False,
        "abstain_means_flat_market": False,
        "raw_d1_flow_without_price_direction_owner": False,
        "coordinator": "Frankie",
        "owner_selection": "configured specialist owner verbatim; never average specialists",
        "hydration": "REJECTED_NOT_USED",
        "new_datapoint_family": False,
    }
    return out


def packet(template: str, gid: str, day: str, spec: str, namespace: str,
           *, bridge_deviation: bool = False) -> tuple[str, dict[str, Any]]:
    """One-shot/current packet with every current Frankie runtime layer installed."""
    prompt, payload = s133.packet(
        template, gid, day, spec, namespace, bridge_deviation=bridge_deviation
    )
    phase = str(payload.get("phase") or "BLIND").upper()
    task = "weekend_bridge" if spec == "A" and template == "BLD-2" else "day_forecast"
    return prompt, _attach(payload, specialist=spec, phase=phase, task=task)


def packet_sequential(template: str, gid: str, day: str, spec: str, namespace: str,
                      *, prior_session: Mapping[str, Any],
                      bridge_deviation: bool = False,
                      provenance: str = "completed prior-session MBO evidence") -> tuple[str, dict[str, Any]]:
    """Sequential/live/refine packet with completed strictly-prior session state + full S135 stack."""
    prompt, payload = s133.packet_sequential(
        template, gid, day, spec, namespace,
        prior_session=prior_session,
        bridge_deviation=bridge_deviation,
        provenance=provenance,
    )
    phase = str(payload.get("phase") or "BLIND").upper()
    task = "weekend_bridge" if spec == "A" and template == "BLD-2" else "day_forecast"
    return prompt, _attach(payload, specialist=spec, phase=phase, task=task)


def packet_live_rederive(open_packet: Mapping[str, Any], *, legal_event_evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Canonical D post-catalyst re-derive entry. Triggered by evidence availability, never a fixed clock."""
    return authority.live_rederive_packet(open_packet, legal_event_evidence=legal_event_evidence)


def validate_owner_output(output: Mapping[str, Any], specialist: str, *, task: str = "day_forecast") -> None:
    authority.validate_owner_output(output, specialist, task=task)


def install() -> None:
    """Install the single current runtime seam. Do not install S126/S132/S133 separately afterward."""
    verify_original_spawn()
    s133.install()  # includes the clean S132 install, which retains S120 full-brain/outcome guards.
    base._packet = packet
    base._validate_day = s132.validate_day


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stack_manifest() -> dict[str, Any]:
    """Hash the current runtime/brain/roles so every group can record exactly what Frankie used."""
    install()
    brain = brain_view.load()
    view, _served, _withheld = brain_view.build(brain, "specialist", phase="working")
    full = s120.full_brain(view)
    serving = full.get("_frankie_serving") or {}
    plays = full.get("plays") or {}
    canonical = int(serving.get("canonical_plays_total", -1))
    served = int(serving.get("full_plays_served", -1))
    if canonical < 1 or served != canonical or len(plays) != canonical:
        raise ForecastStop(
            f"S135 refuses reduced brain: canonical={canonical} served={served} bodies={len(plays)}"
        )

    module_paths = {
        "s126_specialist_parity": Path(s126.__file__).resolve(),
        "s128_decision_state_repairs": Path(s128.__file__).resolve(),
        "s132_event_driven_curve": Path(s132.__file__).resolve(),
        "s133_reasoning_authority": Path(s133.__file__).resolve(),
        "s135_specialist_authority": Path(authority.__file__).resolve(),
        "s135_current_runtime": Path(__file__).resolve(),
    }
    role_paths = {"shared": Path(base.ROLE_SHARED).resolve()}
    role_paths.update({f"specialist_{k}": Path(v).resolve() for k, v in base.ROLE_SPEC.items()})
    brain_path = Path(brain_view.BRAIN).resolve()

    return {
        "stack_version": STACK_VERSION,
        "coordinator": "Frankie",
        "specialists": list(SPECIALISTS),
        "canonical_plays_total": canonical,
        "full_plays_served": served,
        "brain": {"path": str(brain_path), "sha256": _sha(brain_path)},
        "modules": {k: {"path": str(v), "sha256": _sha(v)} for k, v in module_paths.items()},
        "roles": {k: {"path": str(v), "sha256": _sha(v)} for k, v in role_paths.items()},
        "requirements": {
            "explicit_group_context": True,
            "mask_policy_must_be_explicit": True,
            "full_s3_substrate_before_state": True,
            "state_health_required": True,
            "tape_reconcile_required": True,
            "current_brain_later_learned_evidence": "allowed except target-window outcome wall in historical improvement tests",
            "fixed_curve_clock": False,
            "abstain_flat_curve": False,
            "owner_averaging": False,
            "hydration": "REJECTED_NOT_USED",
            "new_datapoint_family": False,
            "sequential_prior_completed_session": True,
            "specialist_authority_contracts": True,
        },
    }


def _selftest() -> None:
    install()
    assert base._packet is packet
    assert base._validate_day is s132.validate_day
    text = base.MODEL_INSTRUCTIONS
    assert s132.S132_OUTPUT_ADDENDUM in text
    assert s133.S133_REASONING_ADDENDUM in text
    assert "all-zero canonical curve" not in text

    real = s133.packet
    try:
        def fake_packet(*args, **kwargs):
            return "PROMPT", {
                "phase": "BLIND",
                "realized_outcome_in_packet": False,
                "causal_slice": {"20250102": {"dow": "Thu"}},
                "brain_view_served": {
                    "plays": {"p": {"id": "p"}},
                    "_frankie_serving": {"canonical_plays_total": 1, "full_plays_served": 1},
                },
                "redo_guards": ["S133"],
            }
        s133.packet = fake_packet
        prompt, payload = packet("BLD-1", "gx", "20250102", "C", "ns")
        assert prompt == "PROMPT"
        assert payload["specialist_access_contract"]["active_specialist"] == "C"
        assert payload["specialist_access_contract"]["full_plays_served"] == 1
        assert payload["s135_current_frankie_stack"]["s132_event_driven_curve"] is True
        assert payload["s135_current_frankie_stack"]["s133_reasoning_authority"] is True
        assert payload["s135_current_frankie_stack"]["s126_specialist_parity"] is True
        assert payload["s135_current_frankie_stack"]["s135_specialist_authority"] is True
        assert payload["s135_specialist_authority"]["continuation_guard"]["raw_d1_flow_plus_slow_backdrop_may_recreate_sign"] is False
    finally:
        s133.packet = real


if __name__ == "__main__":
    _selftest()
    print(json.dumps(stack_manifest(), indent=2, sort_keys=True))
