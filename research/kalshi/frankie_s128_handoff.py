#!/usr/bin/env python3
"""S128 HE24->HE1 handoff entrypoint with typed forecast-vs-realized exit state."""
from __future__ import annotations

import argparse

import frankie_s128_contract_repairs as repairs
import group_he24_he1_handoff as base


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("gid")
    ap.add_argument("--source", choices=("actual", "blind"), default="actual")
    ap.add_argument("--precompute", action="store_true")
    a = ap.parse_args()
    repairs.install_handoff()
    if a.precompute:
        if a.source == "blind":
            raise SystemExit("--precompute is realized/refine-only and cannot run under --source blind")
        base.precompute_exit_states(a.gid)
    else:
        base.main(a.gid, a.source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
