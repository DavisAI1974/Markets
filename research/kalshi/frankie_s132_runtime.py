#!/usr/bin/env python3
"""Canonical S132 runtime install seam.

S120 remains immutable history.  Its canary addendum encoded the old fixed-clock/flat-ABSTAIN
contract, so S132 must remove that instruction before a specialist packet is rendered.  This shim is
the only S132 runtime install path: it preserves S120's full-brain/leak-wall packet construction,
removes the obsolete output adapter metadata, adds the S132 event-driven adapter, and installs the
S132 validator.

No brain, specialist role, spawn.py, state, or data source is modified here.
"""
from __future__ import annotations

import json
from typing import Any

import frankie_s118_redo as s120
import frankie_s132_dynamic_curve as s132

base = s120.base
ForecastStop = s132.ForecastStop


def _remove_old_canary_instruction(text: str) -> str:
    old = getattr(s120, "_CANARY_OUTPUT_ADDENDUM", "")
    if not old:
        return text
    # Remove either a normal double-newline append or a bare occurrence.  Do not alter any other
    # model instruction text.
    text = text.replace("\n\n" + old, "")
    text = text.replace(old, "")
    return text.rstrip()


def packet(template: str, gid: str, day: str, spec: str, namespace: str,
           *, bridge_deviation: bool = False) -> tuple[str, dict[str, Any]]:
    """Reuse S120 causal/full-brain packet construction but replace only its output-contract metadata."""
    prompt, payload = s120.packet(
        template, gid, day, spec, namespace, bridge_deviation=bridge_deviation
    )
    payload.pop("canary_output_adapter", None)
    payload["s132_output_adapter"] = {
        "required_fields": list(s132.S132_REQUIRED_FIELDS),
        "curve_nodes_authoritative": True,
        "path_p50_curve_rule": "exact projection of curve_nodes P50; never a second authored curve",
        "fixed_clock": False,
        "fixed_point_count": False,
        "decimal_et_hours_allowed": True,
        "node_rule": "Frankie chooses a node only for an expected market-state transition",
        "uncertainty_rule": "every node carries P25/P50/P75 cumulative-from-open envelope",
        "abstain_rule": "withhold directional trading authority; still emit best full curve/range forecast",
    }
    payload["redo_guards"] = list(payload.get("redo_guards") or []) + [
        "S132-event-driven-curve",
        "S132-no-fixed-clock",
        "S132-abstain-not-flat",
    ]
    return prompt, payload


def install() -> None:
    """Install the clean S132 runtime boundary in-process."""
    # First retain every useful S120 guard (full-brain availability + outcome wall).
    s120.install()

    # Then remove only the obsolete S120 output-contract prose before any S132 packet is emitted.
    base.MODEL_INSTRUCTIONS = _remove_old_canary_instruction(base.MODEL_INSTRUCTIONS)
    if s132.S132_OUTPUT_ADDENDUM not in base.MODEL_INSTRUCTIONS:
        base.MODEL_INSTRUCTIONS = base.MODEL_INSTRUCTIONS.rstrip() + "\n\n" + s132.S132_OUTPUT_ADDENDUM

    base._packet = packet
    base._validate_day = s132.validate_day


def _selftest() -> None:
    install()
    old = getattr(s120, "_CANARY_OUTPUT_ADDENDUM", "")
    assert not old or old not in base.MODEL_INSTRUCTIONS
    assert "all-zero canonical curve" not in base.MODEL_INSTRUCTIONS
    assert s132.S132_OUTPUT_ADDENDUM in base.MODEL_INSTRUCTIONS
    assert base._validate_day is s132.validate_day
    assert base._packet is packet

    # Exercise metadata replacement without needing a real group packet/state tree.
    original = s120.packet
    try:
        def fake_packet(*args, **kwargs):
            return "PROMPT", {
                "canary_output_adapter": {"abstain_rule": "old flat rule"},
                "redo_guards": ["A-80", "A-82"],
            }
        s120.packet = fake_packet
        prompt, payload = packet("BLD-1", "gx", "20250102", "C", "ns")
        assert prompt == "PROMPT"
        assert "canary_output_adapter" not in payload
        a = payload["s132_output_adapter"]
        assert a["fixed_clock"] is False
        assert a["fixed_point_count"] is False
        assert a["abstain_rule"].startswith("withhold directional trading authority")
    finally:
        s120.packet = original


if __name__ == "__main__":
    _selftest()
    print(json.dumps({
        "status": "READY",
        "runtime": "S132_EVENT_DRIVEN",
        "s120_full_brain_and_leak_guards_retained": True,
        "old_flat_abstain_instruction_present": False,
        "fixed_clock": False,
        "fixed_point_count": False,
    }, indent=2, sort_keys=True))
