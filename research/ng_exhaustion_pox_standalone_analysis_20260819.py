#!/usr/bin/env python3
"""Fail-closed tombstone for the superseded fixed-interval POX analyzer.

This file previously encoded wall-clock checkpoint grids and fixed temporal
windows. Those assumptions violate the standing event-driven/no-clock timing
contract and must not execute. Git history preserves the old research code for
audit only.
"""

from __future__ import annotations

import sys

POLICY = "EVENT_DRIVEN_NO_FIXED_INTERVALS"
CONTRACT = "research/NG_EXHAUSTION_POX_NO_CLOCK_CONTRACT_20260917.json"
REPLACEMENT = "research/ng_exhaustion_pox_event_driven_execution_20260917.py"


def main() -> None:
    raise SystemExit(
        "SUPERSEDED_FIXED_INTERVAL_RUNNER_DISABLED: "
        f"{POLICY}. Do not restore checkpoint grids, fixed lookback gates, or "
        "elapsed-time decision triggers. See " + CONTRACT + ". "
        "Use the event-driven path after the authoritative 3,429 / 1,444 / 1,985 "
        "case ledger has passed the fixed-ledger gate. Replacement: " + REPLACEMENT
    )


if __name__ == "__main__":
    main()
