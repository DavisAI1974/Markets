#!/usr/bin/env python3
"""Thin S131 entrypoint that exposes the corrected state to canonical spawn slot lookup.

The corrected state is already built and validated by frankie_g3_reblind_s131.  Canonical spawn
expects that same state at renders/ng_refine_s95/grp3_state.json.  This shim writes the exact in-memory
state there immediately before prompt emission.  The file exists only in the disposable workflow
checkout; no canonical repo artifact is changed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import frankie_g3_reblind_s131 as s131

_ORIGINAL_PACKET = s131._packet


def _packet_with_standard_state_slot(state, **kwargs):
    slot = s131.HERE / "renders" / "ng_refine_s95" / "grp3_state.json"
    slot.parent.mkdir(parents=True, exist_ok=True)
    slot.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    check = json.loads(slot.read_text(encoding="utf-8"))
    build = check.get("_state_build") or {}
    if build.get("group") != s131.GID or build.get("mask_after") != s131.ANCHOR_DATE:
        raise s131.S131Stop(f"standard state slot lost corrected G3 boundary: {build}")
    return _ORIGINAL_PACKET(state, **kwargs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--namespace", default=s131.DEFAULT_NAMESPACE)
    args = ap.parse_args()
    s131._packet = _packet_with_standard_state_slot
    try:
        result = s131.export(args.out, args.namespace)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"STOP - {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
