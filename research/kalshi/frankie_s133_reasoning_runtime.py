#!/usr/bin/env python3
"""S133 reasoning-authority runtime seam.

S131's post-freeze score localized the largest G3 miss to a reasoning/protocol interaction rather
than to a missing Frankie brain rule.  The current brain already carries day-boundary continuation /
exhaustion logic, including the prior-session collapse filter that would stand down continuation when
the old swing is spent.  S131's one-shot price wall made that load-bearing prior-session price/shape
state unavailable.  Specialist C then allowed a slow loose-balance backdrop plus raw D-1 signed flow
to act as directional corroboration even while explicitly acknowledging that delivery-vs-absorption
and chain/cum state could not be evaluated.

S133 adds two general operating disciplines over the S132 event-driven curve runtime:

1. REASONING AUTHORITY.  Every directional call must name the evidence that OWNS sign.  Raw prior-
   session flow without its paired realized price/shape discriminator may describe pressure,
   liquidity, uncertainty, or tail risk, but it may not increase next-session directional confidence
   as "corroboration".  A slow balance/regime backdrop also may not silently substitute for a missing
   continuation-vs-turn discriminator.  If the sign-owning input is unavailable, Frankie must either
   find another canonical sign owner or downgrade/ABSTAIN while still emitting the full S132 curve.

2. SEQUENTIAL/LIVE/REFINE PRIOR-SESSION CARRY.  A caller may explicitly attach completed prior-session
   realized MBO evidence when its session date is strictly earlier than the decision day.  Own-day or
   future realized evidence is rejected.  The default packet() path remains one-shot and injects no
   realized prior-session price, preserving the historical canary protocol.

This module does NOT modify the brain, specialist roles, schema, spawn.py, state builders, data
sources, S131 frozen artifacts, or S132 curve contract.
"""
from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping
from typing import Any

import frankie_s118_redo as s120
import frankie_s132_dynamic_curve as s132
import frankie_s132_runtime as s132rt

base = s132rt.base
ForecastStop = s132rt.ForecastStop

_DATE8 = re.compile(r"(?<!\d)(20\d{6})(?!\d)")
_ISO = re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)")

S133_REASONING_ADDENDUM = r"""
S133 REASONING-AUTHORITY CONTRACT:

Before choosing a day sign, separate evidence by SCOPE:
- DIRECTION OWNER: evidence that is explicitly allowed to choose next-session sign.
- REGIME/BACKDROP: slow balance, storage level, demand/supply context, calendar state.
- MAGNITUDE/RANGE: volatility/catalyst/range information.
- TIMING/SHAPE/TAIL: information that changes path form or uncertainty but not sign by itself.

A CALL must name at least one evaluable DIRECTION OWNER in the reasoning.  Do not silently promote a
regime/backdrop input into sign authority because a faster direction discriminator is missing.

RAW PRIOR-SESSION FLOW WITHOUT PAIRED PRICE/SHAPE IS NOT NEXT-SESSION DIRECTIONAL CORROBORATION.
Signed flow, B-share, big-print share and phase flow without the paired realized price/shape cannot
distinguish delivered pressure from absorption, exhaustion, covering, or a failed move.  Those fields
may describe pressure/liquidity and widen/narrow uncertainty, but they must NOT increase confidence in
a next-session continuation sign.  If a canonical play requires price/shape to distinguish delivery
from absorption, and that input is unavailable, stand that play down rather than recreating its sign
through a prose proxy.

SLOW BALANCE IS A BACKDROP UNLESS A CANONICAL PLAY EXPLICITLY GRANTS IT DAY-SIGN AUTHORITY.  Storage
surplus/deficit, grid burn, NGWU balance and similar slow state may condition regime, magnitude and
risk.  They do not automatically own a one-session sign when continuation/turn state is unresolved.

When the sign-owning evidence is unavailable or genuinely conflicts, ABSTAIN means WITHHOLD TRADING
DIRECTIONAL AUTHORITY.  Under S132 you must still emit your best event-driven full P50 curve and
P25/P75 envelope; ABSTAIN never means "forecast a flat market".

If the packet contains `completed_prior_session_context`, it is realized information from a session
strictly earlier than the target day and is decision-time legal for SEQUENTIAL/LIVE/REFINE operation.
Use it for canonical day-boundary / continuation / exhaustion / delivery-vs-absorption plays exactly
as the brain specifies.  Do not treat its presence as hydration, and never infer any target-day tape
from it.
""".strip()


def _norm_day(day: str) -> str:
    d = str(day).replace("-", "")
    if len(d) != 8 or not d.isdigit():
        raise ForecastStop(f"S133 invalid decision day {day!r}")
    return d


def _dates_in(obj: Any) -> set[str]:
    """Collect explicit YYYYMMDD / YYYY-MM-DD dates from a nested evidence object."""
    out: set[str] = set()
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            out.update(_dates_in(k))
            out.update(_dates_in(v))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out.update(_dates_in(v))
    elif isinstance(obj, str):
        out.update(_DATE8.findall(obj))
        for y, m, d in _ISO.findall(obj):
            out.add(y + m + d)
    return out


def _validated_prior_session(prior_session: Mapping[str, Any], day: str) -> dict[str, Any]:
    target = _norm_day(day)
    if not isinstance(prior_session, Mapping):
        raise ForecastStop("S133 completed prior-session context must be an object")
    row = copy.deepcopy(dict(prior_session))
    session_day = _norm_day(str(row.get("date", "")))
    if session_day >= target:
        raise ForecastStop(
            f"S133 prior-session reveal must be strictly earlier than target day: {session_day} >= {target}"
        )
    future = sorted(d for d in _dates_in(row) if d >= target)
    if future:
        raise ForecastStop(
            f"S133 completed prior-session context contains own/future date(s) {future} for target {target}"
        )
    return row


def packet(template: str, gid: str, day: str, spec: str, namespace: str,
           *, bridge_deviation: bool = False) -> tuple[str, dict[str, Any]]:
    """Default S133 path: S132 packet + reasoning authority, still one-shot/no realized prior price."""
    prompt, payload = s132rt.packet(
        template, gid, day, spec, namespace, bridge_deviation=bridge_deviation
    )
    payload["s133_reasoning_authority"] = {
        "direction_owner_required_for_call": True,
        "raw_d1_flow_without_price_can_confirm_next_day_sign": False,
        "slow_balance_default_scope": "regime/backdrop/magnitude/risk, not automatic day sign",
        "missing_sign_owner_action": "find another canonical sign owner or downgrade/ABSTAIN",
        "one_shot_prior_session_realized_price_injected": False,
    }
    payload["redo_guards"] = list(payload.get("redo_guards") or []) + [
        "S133-direction-owner-required",
        "S133-no-raw-flow-corroboration-without-price",
        "S133-no-backdrop-promotion",
    ]
    s120.assert_no_outcome_leak(json.dumps(payload, sort_keys=True), gid, _norm_day(day))
    return prompt, payload


def packet_sequential(template: str, gid: str, day: str, spec: str, namespace: str,
                      *, prior_session: Mapping[str, Any],
                      bridge_deviation: bool = False,
                      provenance: str = "completed prior-session MBO evidence") -> tuple[str, dict[str, Any]]:
    """Sequential/live/refine packet with a strictly-prior completed session reveal.

    The caller supplies an already-completed prior-session evidence object (for example one row from
    group_mbo_engine).  S133 never reads actual files itself; that keeps actual access explicit at the
    operating boundary and preserves the one-shot default path.
    """
    prompt, payload = packet(
        template, gid, day, spec, namespace, bridge_deviation=bridge_deviation
    )
    prior = _validated_prior_session(prior_session, day)
    payload["completed_prior_session_context"] = {
        "mode": "SEQUENTIAL_LIVE_OR_REFINE",
        "decision_time_legal": True,
        "strictly_prior_to_target": True,
        "provenance": provenance,
        "session": prior,
    }
    payload["s133_reasoning_authority"]["one_shot_prior_session_realized_price_injected"] = False
    payload["s133_reasoning_authority"]["sequential_prior_session_context_present"] = True
    payload["redo_guards"].append("S133-prior-session-date-wall")
    # Existing S120 wall still checks forbidden actual artifact tokens / own-future explicit fields.
    s120.assert_no_outcome_leak(json.dumps(payload, sort_keys=True), gid, _norm_day(day))
    return prompt, payload


def install() -> None:
    """Install S133 over the clean S132 runtime without changing brain/schema/roles/spawn."""
    s132rt.install()
    if S133_REASONING_ADDENDUM not in base.MODEL_INSTRUCTIONS:
        base.MODEL_INSTRUCTIONS = base.MODEL_INSTRUCTIONS.rstrip() + "\n\n" + S133_REASONING_ADDENDUM
    base._packet = packet
    base._validate_day = s132.validate_day


def _selftest() -> None:
    # Preserve real function so this unit proof does not need a staged group/state tree.
    real_packet = s132rt.packet
    try:
        def fake_packet(*args, **kwargs):
            return "PROMPT", {
                "group": "gx",
                "day": "20250102",
                "specialist": "C",
                "realized_outcome_in_packet": False,
                "redo_guards": ["S132-event-driven-curve"],
            }
        s132rt.packet = fake_packet

        _, p = packet("BLD-1", "gx", "20250102", "C", "ns")
        a = p["s133_reasoning_authority"]
        assert a["direction_owner_required_for_call"] is True
        assert a["raw_d1_flow_without_price_can_confirm_next_day_sign"] is False
        assert "completed_prior_session_context" not in p

        prior = {
            "date": "20250101",
            "open": 3.0,
            "close": 3.1,
            "net_usd": 1000,
            "turn_kind": "turn_up",
            "phases": [{"sflow": -900, "pxchg": 400}],
        }
        _, q = packet_sequential(
            "BLD-1", "gx", "20250102", "C", "ns", prior_session=prior
        )
        assert q["completed_prior_session_context"]["session"]["date"] == "20250101"
        assert q["completed_prior_session_context"]["decision_time_legal"] is True

        for bad in ("20250102", "20250103"):
            try:
                packet_sequential(
                    "BLD-1", "gx", "20250102", "C", "ns",
                    prior_session={"date": bad, "net_usd": 1},
                )
            except ForecastStop:
                pass
            else:
                raise AssertionError("own/future prior-session reveal was not rejected")

        try:
            packet_sequential(
                "BLD-1", "gx", "20250102", "C", "ns",
                prior_session={"date": "20250101", "note": "future marker 2025-01-02"},
            )
        except ForecastStop:
            pass
        else:
            raise AssertionError("nested own-day date was not rejected")
    finally:
        s132rt.packet = real_packet

    install()
    assert S133_REASONING_ADDENDUM in base.MODEL_INSTRUCTIONS
    assert base._packet is packet
    assert base._validate_day is s132.validate_day


if __name__ == "__main__":
    _selftest()
    print(json.dumps({
        "status": "READY",
        "runtime": "S133_REASONING_AUTHORITY",
        "inherits": "S132_EVENT_DRIVEN_CURVE",
        "brain_modified": False,
        "specialist_roles_modified": False,
        "spawn_modified": False,
        "one_shot_default_preserved": True,
        "raw_d1_flow_without_price_directional_corroboration": False,
        "explicit_prior_session_sequential_path": True,
        "own_future_reveal_rejected": True,
    }, indent=2, sort_keys=True))
