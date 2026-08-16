#!/usr/bin/env python3
"""Fail-closed S135 preflight for every new Frankie group run.

Run this twice:
1. code-stack preflight before staging;
2. state preflight after the group's decision-state has been built/staged.

A run is not CURRENT FRANKIE unless the S135 canonical runtime is installed and the state was built
with explicit group context. Normal groups must pass state_health + tape_reconcile. Historical archive
exceptions must be separately proven and documented by the runner; this preflight never invents data.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import frankie_s135_current_runtime as s135

_DAY = re.compile(r"^20\d{6}$")


def check_state(path: Path, gid: str, expected_mask_after: str | None, strict_health: bool) -> dict:
    state = json.loads(path.read_text(encoding="utf-8"))
    build = state.get("_state_build") or {}
    if build.get("group") != gid:
        raise SystemExit(f"S135 PRECHECK FAIL: state group {build.get('group')!r} != {gid!r}")
    if build.get("mask_after") != expected_mask_after:
        raise SystemExit(
            f"S135 PRECHECK FAIL: state mask_after {build.get('mask_after')!r} != explicit expected {expected_mask_after!r}"
        )
    days = sorted(k for k in state if _DAY.fullmatch(str(k)))
    if not days:
        raise SystemExit("S135 PRECHECK FAIL: no decision-day blocks in state")
    for day in days:
        row = state[day]
        scored = row.get("scored_leg") if isinstance(row, dict) else None
        if not isinstance(scored, dict) or scored.get("group") != gid or not scored.get("leg"):
            raise SystemExit(f"S135 PRECHECK FAIL: {day} scored_leg/group context missing: {scored!r}")

    health = "NOT_RUN"
    reconcile = "NOT_RUN"
    if strict_health:
        import state_health
        import tape_reconcile
        state_health.assert_healthy(state, gid)
        health = "PASS"
        tape_reconcile.assert_reconciled(gid, state)
        reconcile = "PASS"

    return {
        "state": str(path),
        "group": gid,
        "mask_after": expected_mask_after,
        "days": days,
        "state_health": health,
        "tape_reconcile": reconcile,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", type=Path)
    ap.add_argument("--group")
    ap.add_argument("--mask-after", default="NONE", help="YYYYMMDD or NONE; must be explicit")
    ap.add_argument("--skip-strict-health", action="store_true",
                    help="Historical archive-gap runner only; runner must carry separate proven gap inventory")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    stack = s135.stack_manifest()
    result = {
        "status": "PASS",
        "current_frankie": stack,
        "state_check": None,
        "hard_requirements": [
            "restore canonical S3 substrate before state build",
            "stage scored per-contract leg + prior tape/L1 for group",
            "build state through s135.decision_state with explicit group and explicit mask policy",
            "normal group: state_health PASS and tape_reconcile PASS before any specialist sees packet",
            "all A-E packets through s135.packet or s135.packet_sequential; no direct S126/S132/S133 install",
            "HE24->HE1 chain through frankie_s135_handoff, not stale canonical carry prose",
            "Frankie coordinator selects configured day owner verbatim; never average/smooth specialists",
            "S132 event-driven curve: no fixed clock/point count; ABSTAIN still emits full curve/range",
            "S133 direction owner required; raw D-1 flow without price/shape cannot corroborate next-day sign",
            "historical current-brain tests keep later learned brain evidence; only target-window outcomes are walled",
            "no hydration; no new datapoint family",
        ],
    }

    if args.state is not None:
        if not args.group:
            raise SystemExit("--group is required with --state")
        mask = None if args.mask_after.upper() == "NONE" else args.mask_after
        if mask is not None and not re.fullmatch(r"20\d{6}", mask):
            raise SystemExit(f"invalid --mask-after {args.mask_after!r}")
        result["state_check"] = check_state(
            args.state, args.group, mask, strict_health=not args.skip_strict_health
        )
        if args.skip_strict_health:
            result["state_check"]["exception_rule"] = (
                "strict health skipped only for a historical runner carrying separate durable archive-gap proof; "
                "missing families must remain unavailable/null and may not be hydrated/synthesized"
            )

    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
