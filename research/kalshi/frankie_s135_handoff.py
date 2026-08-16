#!/usr/bin/env python3
"""S135 current HE24->HE1 handoff wrapper.

The canonical S105 handoff artifact is still valuable and remains the data builder, but its embedded
carry prose predates S133 and says D-1 trade tilt owns direction. That is stale relative to the current
brain/runtime: completed prior-session price/shape may activate canonical exhaustion/turn/absorption
plays, while raw flow without paired price/shape cannot own next-session sign.

This wrapper calls the unchanged canonical builder, then replaces ONLY the carry instruction strings.
No state values, price/tape measurements, chain fields, source walls, or owner reads are modified.
Every new S135 group run must use this wrapper rather than calling group_he24_he1_handoff.main directly.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import group_he24_he1_handoff as base

HERE = Path(__file__).resolve().parent


def current_carry_rules(boundary_kind: str) -> list[str]:
    rules = [
        "Use the completed prior-session exit/chain STATE through the current brain's canonical plays; a qualified turn/exhaustion/absorption play may override inherited continuation.",
        "Raw D-1 signed flow/B-share without paired price/shape is pressure/liquidity context, NOT next-session directional corroboration (S133 reasoning-authority contract).",
        "Direction must have an evaluable canonical owner. If continuation-vs-turn cannot be adjudicated, reduce authority or ABSTAIN rather than smuggling the missing decision back through slow backdrop + raw flow.",
    ]
    if boundary_kind == "weekend_reopen":
        rules.append(
            "Weekend: keep Sunday gap and Monday session separate. Monday inherits Friday close/chain state, then re-test against legally available weekend information; never inherit Friday day-net mechanically."
        )
    elif boundary_kind == "post_seam":
        rules.append(
            "Contract seam: the leg change itself is never a traded move. Anchor to the new leg correctly and treat any scoring offset as scoring-only."
        )
    else:
        rules.append(
            "Overnight: read the open relative to the completed prior close's exit condition (close-off-extreme, high/low timing, last-hour direction/flow, chain state)."
        )
    return rules


def rewrite(gid: str) -> Path:
    path = HERE / "forecasts" / f"{gid}_he24_he1_handoffs.json"
    if not path.is_file():
        raise SystemExit(f"S135 handoff artifact missing after canonical build: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    days = obj.get("days")
    if not isinstance(days, dict):
        raise SystemExit(f"S135 malformed handoff days: {path}")
    changed = 0
    for _day, row in days.items():
        if not isinstance(row, dict) or "prior_date" not in row:
            continue
        kind = str(row.get("boundary_kind") or "overnight")
        row["carry_rules"] = current_carry_rules(kind)
        row["s135_reasoning_authority"] = {
            "prior_exit_state_can_override_continuation_through_canonical_play": True,
            "raw_d1_flow_without_price_direction_owner": False,
            "direction_owner_required": True,
        }
        changed += 1
    obj["spec"] = "he24->he1 boundary handoff (STATE not day-net); S135 current reasoning authority"
    obj["s135_wrapper"] = {
        "canonical_builder_unchanged": True,
        "only_carry_instruction_text_replaced": True,
        "days_rewritten": changed,
    }
    path.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path


def run(gid: str, source: str = "actual") -> Path:
    if source not in ("actual", "blind"):
        raise SystemExit(f"source must be actual|blind, got {source!r}")
    base.main(gid, source)
    return rewrite(gid)


def _selftest() -> None:
    normal = current_carry_rules("overnight")
    text = " ".join(normal)
    assert "Direction stays with the D-1 trade tilt" not in text
    assert "NOT next-session directional corroboration" in text
    assert "turn/exhaustion/absorption" in text
    weekend = " ".join(current_carry_rules("weekend_reopen"))
    assert "Sunday gap and Monday session separate" in weekend


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("gid", nargs="?")
    ap.add_argument("--source", choices=("actual", "blind"), default="actual")
    args = ap.parse_args()
    if args.gid is None:
        _selftest()
        print("S135 HANDOFF READY")
    else:
        print(run(args.gid, args.source))
