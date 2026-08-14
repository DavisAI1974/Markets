#!/usr/bin/env python3
"""S128 staging wrapper: original stage_group with repaired decision-state construction.

All S3/download/actual/MBO/exit-state behavior remains owned by stage_group.py. The only
intercept replaces its forecast_harness.py decision-state subprocess with the S128 contract-
repair entrypoint. This avoids copying or rewriting the canonical staging machinery.
"""
from __future__ import annotations

import sys
from pathlib import Path

import stage_group as base

HERE = Path(__file__).resolve().parent
_ORIG_RUN = base.subprocess.run


def _run(cmd, *args, **kwargs):
    patched = list(cmd) if isinstance(cmd, (list, tuple)) else cmd
    if isinstance(patched, list):
        for i, token in enumerate(patched):
            if str(token).endswith("forecast_harness.py") and "decision-state" in patched:
                patched[i] = str(HERE / "frankie_s128_decision_state.py")
                break
    return _ORIG_RUN(patched, *args, **kwargs)


def main() -> int:
    base.subprocess.run = _run
    args = sys.argv[1:]
    suffix = ""
    if "--suffix" in args:
        i = args.index("--suffix")
        suffix = args[i + 1]
        args = args[:i] + args[i + 2:]
    if not args:
        raise SystemExit("usage: frankie_stage_group_s128.py [--suffix SUFFIX] <gid> [gid ...]")
    for gid in args:
        base.stage(gid, suffix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
