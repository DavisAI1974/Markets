#!/usr/bin/env python3
"""Fail-closed tombstone for the superseded fixed-hold POX executor.

This file previously encoded fixed +5/+10/+20/+30/+60 hold horizons and
clock-relative management comparisons. Those assumptions violate the standing
event-driven/no-clock timing contract and must not execute. Git history
preserves the old implementation for audit only.
"""

from __future__ import annotations

POLICY = "EVENT_DRIVEN_NO_FIXED_INTERVALS"
CONTRACT = "research/NG_EXHAUSTION_POX_NO_CLOCK_CONTRACT_20260917.json"
REPLACEMENT = "research/ng_exhaustion_pox_event_driven_execution_20260917.py"


def main() -> None:
    raise SystemExit(
        "SUPERSEDED_FIXED_HOLD_RUNNER_DISABLED: "
        f"{POLICY}. Fixed hold horizons, timeout exits, and clock-relative "
        "management are forbidden. Historical +60 remains diagnostic/label "
        "evidence only and cannot trigger a trade action. See " + CONTRACT + ". "
        "Replacement: " + REPLACEMENT
    )


if __name__ == "__main__":
    main()
