#!/usr/bin/env python3
"""Thin S131 entrypoint that exposes corrected G3 artifacts to canonical spawn slot lookup.

The corrected state is already built and validated by frankie_g3_reblind_s131. Canonical spawn
expects that same state at renders/ng_refine_s95/grp3_state.json and one physically causal slice per
forecast day at renders/ng_refine_s95/g3_causal_slices/state_<DAY>.json. This shim writes those exact
in-memory artifacts immediately before prompt emission. They exist only in the disposable workflow
checkout; no canonical repo artifact is changed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import frankie_g3_reblind_s131 as s131

_ORIGINAL_PACKET = s131._packet


def _materialize_standard_slots(state) -> None:
    render = s131.HERE / "renders" / "ng_refine_s95"

    state_slot = render / "grp3_state.json"
    state_slot.parent.mkdir(parents=True, exist_ok=True)
    state_slot.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    check = json.loads(state_slot.read_text(encoding="utf-8"))
    build = check.get("_state_build") or {}
    if build.get("group") != s131.GID or build.get("mask_after") != s131.ANCHOR_DATE:
        raise s131.S131Stop(f"standard state slot lost corrected G3 boundary: {build}")

    slice_dir = render / "g3_causal_slices"
    slice_dir.mkdir(parents=True, exist_ok=True)
    for day in s131.DAYS:
        sl = s131.causal.slice_state(state, day)
        bad = s131.causal.audit(sl, day)
        if bad:
            raise s131.S131Stop(f"refuse to materialize noncausal standard slice {day}: {bad}")
        future = sorted(k for k in sl if k[:1].isdigit() and k > day)
        if future:
            raise s131.S131Stop(f"standard slice {day} contains future day blocks: {future}")
        p = slice_dir / f"state_{day}.json"
        p.write_text(json.dumps(sl, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        reread = json.loads(p.read_text(encoding="utf-8"))
        build2 = reread.get("_state_build") or {}
        if build2.get("group") != s131.GID or build2.get("mask_after") != s131.ANCHOR_DATE:
            raise s131.S131Stop(f"standard slice {day} lost corrected G3 boundary: {build2}")
        bad2 = s131.causal.audit(reread, day)
        if bad2:
            raise s131.S131Stop(f"standard slice {day} failed reread causal audit: {bad2}")


def _packet_with_standard_state_slot(state, **kwargs):
    _materialize_standard_slots(state)
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
