#!/usr/bin/env python3
"""S126 hard gate for causal-slice capture timestamps.

`build_causal_slices.py` historically printed future capture stamps as notes.  The M-13 recovery proved
that a postdated `storage_consensus` capture can carry a real value backward into an earlier decision
slice, so Frankie must fail closed on this class before any regenerated state is sanctioned.

Scheduled future event timestamps are already excluded by `forward_stamps`; this gate only rejects
value-capture/as-of/retrieval stamps that postdate the decision day, plus the existing block/session
causality violations from `build_causal_slices.audit`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
RENDER_DIR = HERE / "renders" / "ng_refine_s95"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_causal_slices as bcs  # noqa: E402
import group_config as gc  # noqa: E402


class CausalCaptureError(RuntimeError):
    pass


def validate(gid: str, render_dir: Path = RENDER_DIR) -> dict:
    if gid not in gc.GROUPS:
        raise CausalCaptureError(f"unknown group {gid}")
    days = list(gc.GROUPS[gid]["days"])
    slice_dir = render_dir / f"{gid}_causal_slices"
    for day in days:
        path = slice_dir / f"state_{day}.json"
        if not path.exists():
            raise CausalCaptureError(f"missing causal slice {path}")
        sl = json.loads(path.read_text(encoding="utf-8"))
        structural = bcs.audit(sl, day)
        if structural:
            raise CausalCaptureError(f"{day}: causal structure violation: {structural}")
        stamps = bcs.forward_stamps(sl, day)
        if stamps:
            raise CausalCaptureError(f"{day}: future value-capture stamp(s): {stamps}")
    return {"gid": gid, "days": len(days), "future_capture_stamps": 0, "causal_structure": "PASS"}


def main() -> int:
    ap = argparse.ArgumentParser(description="S126 hard gate for future value-capture stamps")
    ap.add_argument("gid", nargs="?", default="g24")
    args = ap.parse_args()
    try:
        result = validate(args.gid)
    except CausalCaptureError as exc:
        print(f"FAIL: S126_CAUSAL_CAPTURE: {exc}", file=sys.stderr, flush=True)
        return 1
    print(
        f"PASS: {args.gid} causal slices have zero future value-capture stamps and no structural leakage",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
