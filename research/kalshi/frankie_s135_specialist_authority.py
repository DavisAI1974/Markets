#!/usr/bin/env python3
"""S135 specialist authority/sequencing contracts.

This module does not redefine A-E roles. It adds the narrow operating constraints learned from the
G3 S131-S134 work so the canonical roles cannot silently fall back to stale authority semantics.
No brain rules, datapoint families, fixed curve clocks, or synthetic history are introduced here.
"""
from __future__ import annotations

import copy
import json
from typing import Any, Mapping

VERSION = "S135_SPECIALIST_AUTHORITY_V1"
_SPECIALISTS = set("ABCDE")
_FORBIDDEN_LIVE_OUTCOME_KEYS = {
    "actual_close", "actual_day_move_usd", "realized_close", "realized_day_move_usd",
    "final_session_close", "target_outcome",
}


def _common() -> list[str]:
    return [
        "Preserve the assigned specialist's CALL/ABSTAIN and S132 curve verbatim; coordinator averaging or smoothing is forbidden.",
        "ABSTAIN withholds directional authority; it still requires the best event-driven P25/P50/P75 path/range.",
        "A CALL requires an evaluable S133 direction owner. Raw D-1 signed flow without paired price/shape cannot add next-session sign confidence.",
        "Slow storage/balance/grid/demand state is backdrop/regime/magnitude/risk unless a canonical current-brain play explicitly grants day-sign authority.",
    ]


def specialist_contract(specialist: str, *, task: str = "day_forecast", information_state: str = "open") -> dict[str, Any]:
    spec = str(specialist).upper()
    if spec not in _SPECIALISTS:
        raise ValueError(f"unknown specialist {specialist!r}")
    rules = _common()
    contract: dict[str, Any] = {
        "version": VERSION,
        "specialist": spec,
        "task": task,
        "information_state": information_state,
        "rules": rules,
        "new_brain_rule": False,
        "new_datapoint_family": False,
        "hydration": "REJECTED_NOT_USED",
    }

    if spec == "C":
        rules.extend([
            "Continuation-vs-turn is price-sensitive. If the paired price/shape discriminator is missing, conflicted, or has stood continuation down, do not rebuild that sign from raw D-1 flow plus slow balance.",
            "Use another valid canonical sign owner or lower authority/ABSTAIN; pressure/liquidity context is not a substitute sign gate.",
        ])
        contract["continuation_guard"] = {
            "raw_d1_flow_plus_slow_backdrop_may_recreate_sign": False,
            "paired_price_shape_or_other_canonical_sign_owner_required": True,
        }
    elif spec == "D":
        rules.extend([
            "Open-time and post-catalyst states are different legal information states. Once an EIA print/impulse is legally observed, rebuild the remaining S132 curve from that state rather than defend the opening path.",
            "The re-derive trigger is event availability/evidence, never a hard-coded wall-clock node.",
        ])
        contract["live_rederive"] = {
            "required_after_legal_eia_impulse": True,
            "trigger": "event/evidence availability, not fixed clock",
            "scope": "remaining curve only",
        }
    elif spec == "E":
        rules.extend([
            "Gross Friday roll/program flow is not automatically directional. Interpret it against price response to aggression, failure-to-extend, absorption, exhaustion, and late-session turn/exit state.",
            "Program-day flow may describe participation/liquidity without owning sign.",
        ])
        contract["friday_guard"] = {
            "gross_program_or_roll_flow_alone_may_own_sign": False,
            "price_response_and_turn_evidence_required_for_flow_sign_authority": True,
        }
    elif spec == "A" and task == "weekend_bridge":
        rules.extend([
            "Bridge Friday's legally completed exit/tape/chain state plus genuinely available weekend information into Monday B; A does not own Monday's forecast.",
            "Keep the Sunday gap distinct from Monday's session and never invent weather/stability/gap sign when the historical archive is unavailable.",
        ])
        contract["weekend_bridge"] = {
            "owns_monday_forecast": False,
            "invent_missing_weekend_information": False,
            "friday_completed_state_required_when_available": True,
        }
    return contract


def attach(payload: Mapping[str, Any], *, specialist: str, phase: str,
           task: str = "day_forecast", information_state: str = "open") -> dict[str, Any]:
    out = copy.deepcopy(dict(payload))
    out["s135_specialist_authority"] = specialist_contract(
        specialist, task=task, information_state=information_state
    )
    out["s135_specialist_authority"]["phase"] = str(phase).upper()
    return out


def _direction_owner_text(output: Mapping[str, Any]) -> str:
    reasoning = output.get("reasoning") if isinstance(output.get("reasoning"), Mapping) else {}
    owner = reasoning.get("direction_owner")
    if isinstance(owner, Mapping):
        owner = json.dumps(dict(owner), sort_keys=True)
    return str(owner or "").lower()


def validate_owner_output(output: Mapping[str, Any], specialist: str, *, task: str = "day_forecast") -> None:
    """Fail closed on the authority regressions S133/S134 identified without changing output values."""
    spec = str(specialist).upper()
    if spec not in _SPECIALISTS:
        raise ValueError(f"unknown specialist {specialist!r}")
    call = str(output.get("call") or output.get("decision") or "").upper()
    if call == "CALL":
        owner = _direction_owner_text(output)
        if not owner:
            raise ValueError(f"Specialist {spec} CALL missing evaluable reasoning.direction_owner")
        if spec == "C":
            forbidden = ("raw d-1", "raw_d1", "d-1 trade tilt", "slow balance", "slow backdrop")
            if any(x in owner for x in forbidden):
                raise ValueError("Specialist C cannot use raw D-1 flow/slow backdrop as replacement direction owner")
        if spec == "E":
            forbidden = ("gross program flow", "program_flow_only", "roll flow only", "gross roll flow")
            if any(x in owner for x in forbidden):
                raise ValueError("Specialist E cannot use gross program/roll flow alone as direction owner")

    if spec == "A" and task == "weekend_bridge":
        forbidden_fields = {"guessed_net_usd", "guess_day_move_usd", "path_p50_curve", "curve_nodes"}
        present = sorted(k for k in forbidden_fields if k in output)
        if present:
            raise ValueError(f"Weekend A bridge attempted to own Monday forecast fields: {present}")


def live_rederive_packet(open_packet: Mapping[str, Any], *, legal_event_evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Create D's post-catalyst information state without hard-coding a time or consuming final outcome data."""
    if str(open_packet.get("specialist") or "").upper() != "D":
        raise ValueError("live re-derive is Specialist D only")
    if not legal_event_evidence:
        raise ValueError("post-catalyst re-derive requires explicit legally available event evidence")
    leaked = sorted(k for k in _FORBIDDEN_LIVE_OUTCOME_KEYS if k in legal_event_evidence)
    if leaked:
        raise ValueError(f"post-catalyst evidence contains forbidden target outcome fields: {leaked}")
    if not (legal_event_evidence.get("available_at") or legal_event_evidence.get("observed_at")):
        raise ValueError("post-catalyst evidence must state when it became legally available")
    if not (legal_event_evidence.get("event") or legal_event_evidence.get("release")):
        raise ValueError("post-catalyst evidence must identify the catalyst/release")

    out = copy.deepcopy(dict(open_packet))
    phase = str(out.get("phase") or "LIVE").upper()
    out = attach(out, specialist="D", phase=phase, task="day_forecast", information_state="post_catalyst")
    out["s135_live_rederive"] = {
        "mode": "REBUILD_REMAINING_CURVE",
        "trigger": "legal event evidence availability",
        "fixed_clock_trigger": False,
        "opening_curve_is_prior_not_authority": True,
        "legal_event_evidence": copy.deepcopy(dict(legal_event_evidence)),
    }
    return out


def _selftest() -> None:
    c = specialist_contract("C")
    assert c["continuation_guard"]["raw_d1_flow_plus_slow_backdrop_may_recreate_sign"] is False
    d = specialist_contract("D")
    assert d["live_rederive"]["trigger"] == "event/evidence availability, not fixed clock"
    e = specialist_contract("E")
    assert e["friday_guard"]["gross_program_or_roll_flow_alone_may_own_sign"] is False
    a = specialist_contract("A", task="weekend_bridge")
    assert a["weekend_bridge"]["owns_monday_forecast"] is False
    try:
        validate_owner_output({"call": "CALL", "reasoning": {"direction_owner": "raw D-1 flow"}}, "C")
    except ValueError:
        pass
    else:
        raise AssertionError("C raw-flow direction-owner guard did not fire")
    live = live_rederive_packet(
        {"specialist": "D", "phase": "LIVE"},
        legal_event_evidence={"event": "EIA storage", "available_at": "event_timestamp", "impulse": "observed"},
    )
    assert live["s135_live_rederive"]["fixed_clock_trigger"] is False


if __name__ == "__main__":
    _selftest()
    print("S135 SPECIALIST AUTHORITY READY")
