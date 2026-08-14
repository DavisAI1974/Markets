#!/usr/bin/env python3
"""S131 corrected mechanical re-blind input exporter for September 2025 G3.

Why this exists
---------------
The S129 state artifact was built with BOTH ``group=None`` and ``mask_after=None``.  That disabled
G3 scored-leg context and the one-shot Sep-05 anchor price mask.  S131 repairs only that harness
boundary and exports a new, isolated set of BLIND inputs for ChatGPT-operated Frankie.

This is deliberately NOT a pristine holdout: September outcomes are already known outside the
packet.  The model-facing packet nevertheless contains no target outcomes and no score/reveal phase.

Standing constraints enforced here:
- current S128 decision-state/contract repairs are retained;
- no historical hydration/backfill experiment is invoked;
- no new datapoint family is added;
- canonical group_config.py is NOT edited (G3 is injected in-process only);
- brain/schema, A-E specialist roles, spawn.py, G24, and S129 frozen artifacts are untouched;
- price-derived state is one-shot frozen at the real Sep-05 anchor close boundary;
- causal day slices contain no future day blocks;
- this exporter has no scoring or realized-outcome reader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import brain_view  # noqa: E402
import build_causal_slices as causal  # noqa: E402
import frankie_group_forecast_s118 as base  # noqa: E402
import frankie_s118_redo as s120  # noqa: E402
import frankie_s128_contract_repairs as s128  # noqa: E402
import frankie_specialist_parity_s126 as s126  # noqa: E402
import group_config as gc  # noqa: E402
from frankie_core import verify_original_spawn  # noqa: E402
from frankie_packet_compact_s120 import assert_frankie_invariants, compact_packet_json  # noqa: E402

GID = "g3"
DAYS = [
    "20250908", "20250909", "20250910", "20250911", "20250912",
    "20250915", "20250916", "20250917", "20250918", "20250919",
]
ANCHOR_DATE = "20250905"
ANCHOR_PRICE = 3.026
ANCHOR_LASTHR_DIR = -1
SCORED_LEG = "ngv25"
SCORED_STORE = f"ng_mbo_{SCORED_LEG}"
DEFAULT_NAMESPACE = "frankie_g3_s131_corrected_reblind"

# This is a local harness contract, not a canonical group_config edit.
_G3_CONTEXT = {
    "window": "Sun 2025-09-07 -> Fri 2025-09-19",
    "days": DAYS,
    "anchor": ANCHOR_PRICE,
    "anchor_date": ANCHOR_DATE,
    "anchor_lasthr_dir": ANCHOR_LASTHR_DIR,
    "mask_after": ANCHOR_DATE,
    "seam": None,
    "legs": {"all": SCORED_LEG},
    "eia_thursdays": ["20250911", "20250918"],
    "basis": "Oct/NGV25 clean for Sep 08-19; next known scored-leg seam is Sep 25, outside window",
}

# Avoid accidentally importing the rejected S130 experiment while still making the check explicit.
_REJECTED_HYDRATION_MODULE = "frankie_historical_" + "hydrate_s130"


class S131Stop(RuntimeError):
    pass


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def install_g3_context() -> None:
    """Install G3 only in this Python process; fail if a conflicting canonical entry appears later."""
    existing = gc.GROUPS.get(GID)
    if existing is not None:
        probe = {
            "days": existing.get("days"),
            "anchor_date": existing.get("anchor_date"),
            "mask_after": existing.get("mask_after"),
            "seam": existing.get("seam"),
            "legs": existing.get("legs"),
        }
        want = {k: _G3_CONTEXT[k] for k in probe}
        if probe != want:
            raise S131Stop(f"canonical {GID} now exists with different contract; refuse shadowing: {probe}")
        return
    gc.GROUPS[GID] = dict(_G3_CONTEXT)


def _assert_no_rejected_hydration() -> None:
    if _REJECTED_HYDRATION_MODULE in sys.modules:
        raise S131Stop("rejected S130 hydration module entered the S131 process")


def _owners() -> dict[str, str]:
    owners = gc.owner_map(GID)
    expected = {
        "20250908": "B", "20250909": "C", "20250910": "C", "20250911": "D",
        "20250912": "E", "20250915": "B", "20250916": "C", "20250917": "C",
        "20250918": "D", "20250919": "E",
    }
    if owners != expected:
        raise S131Stop(f"unexpected G3 owner map: {owners}")
    return owners


def build_state() -> dict[str, Any]:
    """Normal current decision-state path, with the two S129 omissions repaired."""
    _assert_no_rejected_hydration()
    state = s128.decision_state(DAYS, mask_after=ANCHOR_DATE, group=GID)
    build = state.get("_state_build") or {}
    if build.get("group") != GID:
        raise S131Stop(f"state group context missing: {build}")
    if build.get("mask_after") != ANCHOR_DATE:
        raise S131Stop(f"Sep-05 one-shot price mask missing: {build}")

    for day in DAYS:
        row = state.get(day)
        if not isinstance(row, dict):
            raise S131Stop(f"state missing day {day}")
        scored = row.get("scored_leg")
        if not isinstance(scored, dict) or scored.get("leg") != SCORED_STORE:
            raise S131Stop(f"{day}: scored-leg context is not {SCORED_STORE}: {scored!r}")

        # The one-shot price mask must be machine-readable even when an underlying historical
        # price-derived source is absent.  Exogenous channels are intentionally NOT frozen.
        for block in ("contract_structure", "vol_regime", "cash_basis", "options_surface", "squeeze_watch"):
            value = row.get(block)
            if not isinstance(value, dict) or value.get("masked_one_shot") is not True:
                raise S131Stop(f"{day}: price-derived block {block} is not Sep-05 one-shot masked: {value!r}")
            if value.get("vintage_asof") != ANCHOR_DATE:
                raise S131Stop(f"{day}: {block} mask vintage is not {ANCHOR_DATE}: {value!r}")

    state["_s131_reblind_contract"] = {
        "phase": "corrected_mechanical_reblind_inputs",
        "not_pristine_holdout": True,
        "window": "2025-09-08..2025-09-19",
        "starter_anchor": {
            "date": ANCHOR_DATE,
            "close": ANCHOR_PRICE,
            "last_hour_dir": "down",
            "last_hour_dir_numeric": ANCHOR_LASTHR_DIR,
        },
        "group_context": GID,
        "scored_leg": "NGV25",
        "scored_store": SCORED_STORE,
        "seam_inside_window": False,
        "next_known_seam_date": "20250925",
        "price_mask_after": ANCHOR_DATE,
        "hydration": "REJECTED_NOT_USED",
        "actuals_read": False,
        "score_or_reveal_phase_present": False,
        "rule": "current normal decision-state path only; missing historical feeds remain unavailable/null",
    }
    _assert_no_rejected_hydration()
    return state


def _brain_for_day(state: dict[str, Any], day: str) -> dict[str, Any]:
    """Current specialist working view with in-window outcome redaction + S128 availability annotation."""
    brain = brain_view.load()
    view, _served, _withheld = brain_view.build(
        brain, "specialist", phase="working", window_days=DAYS
    )
    view = brain_view.annotate_evaluability(view, state[day])
    return s128.full_brain(view)


def _packet(
    state: dict[str, Any], *, day: str, specialist: str, template: str,
    namespace: str, decision_day: str | None = None, starter_anchor_bridge: bool = False,
) -> dict[str, Any]:
    decision_day = decision_day or day
    prompt = base._emit_prompt(
        template, GID, day=day, spec=specialist, namespace=namespace,
        allow_bridge_deviation=(template == "BLD-2"),
    )

    if starter_anchor_bridge:
        # The first weekend bridge starts from an explicit REAL starter anchor, not from a hidden
        # target outcome and not from Monday state.  No Sep-08 information is allowed to travel
        # backward into the Sep-05 bridge decision.
        causal_slice = {
            "_information_clock": state.get("_information_clock"),
            "_play_input_availability": state.get("_play_input_availability"),
            "_s131_reblind_contract": state.get("_s131_reblind_contract"),
            "_starter_anchor_exit": {
                "date": ANCHOR_DATE,
                "close": ANCHOR_PRICE,
                "last_hour_dir": "down",
                "weekend_cycle_evidence": None,
                "rule": "explicit starter anchor only; no Sep-08-or-later state in this bridge packet",
            },
        }
        # Evaluate the brain against only the fields actually served to the starter bridge.
        brain = brain_view.load()
        view, _served, _withheld = brain_view.build(
            brain, "specialist", phase="working", window_days=DAYS
        )
        view = brain_view.annotate_evaluability(view, causal_slice.get("_starter_anchor_exit"))
        brain_served = s128.full_brain(view)
    else:
        causal_slice = causal.slice_state(state, decision_day)
        bad = causal.audit(causal_slice, decision_day)
        if bad:
            raise S131Stop(f"causal slice violation at {decision_day}: {bad}")
        brain_served = _brain_for_day(state, decision_day)

    payload = {
        "packet_version": "s131.corrected-mechanical-reblind.1",
        "phase": "BLIND",
        "group": GID,
        "day": day,
        "decision_day": decision_day,
        "specialist": specialist,
        "template": template,
        "not_pristine_holdout": True,
        "corrected_mechanical_reblind": True,
        "realized_target_outcome_in_packet": False,
        "actuals_read": False,
        "canonical_prompt": prompt,
        "canonical_role_files": {
            "shared": base.ROLE_SHARED.read_text(encoding="utf-8"),
            "specialist": base.ROLE_SPEC[specialist].read_text(encoding="utf-8"),
        },
        "causal_slice": causal_slice,
        "brain_view_served": brain_served,
        "s131_boundary_repairs": [
            "g3_group_context_restored_in_process",
            "sep05_one_shot_price_mask_restored",
            "s128_contract_repairs_retained",
            "rejected_s130_hydration_not_used",
        ],
        "operator_transport": "chatgpt-session-manual; no model API invoked by exporter",
    }
    payload = s126.attach_specialist_access(payload, specialist=specialist, phase="BLIND")
    s120.assert_no_outcome_leak(json.dumps(payload, sort_keys=True), GID, decision_day)
    return payload


def export(out_dir: Path, namespace: str) -> dict[str, Any]:
    verify_original_spawn()
    install_g3_context()
    _assert_no_rejected_hydration()
    owners = _owners()
    state = build_state()

    out_dir.mkdir(parents=True, exist_ok=True)
    state_path = out_dir / "g3_s131_corrected_state.json"
    state_text = json.dumps(state, indent=2, sort_keys=True) + "\n"
    state_path.write_text(state_text, encoding="utf-8")

    exported: list[dict[str, Any]] = []

    # Explicit starter bridge: Sep-05 real anchor -> Sep-08 Monday.
    starter = _packet(
        state, day="20250908", decision_day=ANCHOR_DATE, specialist="A", template="BLD-2",
        namespace=namespace, starter_anchor_bridge=True,
    )
    compact = compact_packet_json(starter)
    inv = assert_frankie_invariants(starter, compact)
    p = out_dir / "g3_BLD-2_A_20250905_to_20250908.json"
    p.write_text(compact + "\n", encoding="utf-8")
    exported.append({
        "template": "BLD-2", "specialist": "A", "decision_day": ANCHOR_DATE,
        "target_day": "20250908", "path": p.name, "sha256": _sha256(compact),
        "bytes": len(compact.encode("utf-8")), "invariants": inv,
    })

    for day in DAYS:
        # The second Monday gets its normal in-block Friday bridge.
        if day == "20250915":
            bridge = _packet(
                state, day=day, decision_day="20250912", specialist="A", template="BLD-2",
                namespace=namespace,
            )
            compact = compact_packet_json(bridge)
            inv = assert_frankie_invariants(bridge, compact)
            p = out_dir / "g3_BLD-2_A_20250912_to_20250915.json"
            p.write_text(compact + "\n", encoding="utf-8")
            exported.append({
                "template": "BLD-2", "specialist": "A", "decision_day": "20250912",
                "target_day": day, "path": p.name, "sha256": _sha256(compact),
                "bytes": len(compact.encode("utf-8")), "invariants": inv,
            })

        spec = owners[day]
        packet = _packet(
            state, day=day, specialist=spec, template="BLD-1", namespace=namespace,
        )
        compact = compact_packet_json(packet)
        inv = assert_frankie_invariants(packet, compact)
        p = out_dir / f"g3_BLD-1_{spec}_{day}.json"
        p.write_text(compact + "\n", encoding="utf-8")
        exported.append({
            "template": "BLD-1", "specialist": spec, "decision_day": day,
            "target_day": day, "path": p.name, "sha256": _sha256(compact),
            "bytes": len(compact.encode("utf-8")), "invariants": inv,
        })

    manifest = {
        "group": GID,
        "window": "2025-09-08..2025-09-19",
        "namespace": namespace,
        "operator": "ChatGPT session",
        "phase": "corrected_mechanical_reblind_inputs_only",
        "not_pristine_holdout": True,
        "state_builder": "frankie_s128_contract_repairs.decision_state",
        "g3_context_injected_in_process_only": True,
        "group_config_file_modified": False,
        "mask_after": ANCHOR_DATE,
        "starter_anchor": {"date": ANCHOR_DATE, "close": ANCHOR_PRICE, "last_hour_dir": "down"},
        "scored_leg": "NGV25",
        "scored_store": SCORED_STORE,
        "hydration": "REJECTED_NOT_USED",
        "model_api_invoked": False,
        "actuals_read": False,
        "score_or_reveal_phase_present": False,
        "state_path": state_path.name,
        "state_sha256": _sha256(state_text.rstrip("\n")),
        "packet_count": len(exported),
        "packets": exported,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _assert_no_rejected_hydration()
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    args = ap.parse_args()
    try:
        result = export(args.out, args.namespace)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"STOP - {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
