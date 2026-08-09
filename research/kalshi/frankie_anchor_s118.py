#!/usr/bin/env python3
"""Materialize ephemeral G17/G18 anchor artifacts from declared group_config values.

Fresh checkouts do not carry the historical anchor JSONs that spawn.py requires. For the S118
walked validation only, recreate those lookup artifacts from the already-declared config. This
never reads actual tape and refuses groups whose anchor is unresolved.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import group_config as gc  # noqa: E402

RENDERS = HERE / "renders" / "ng_refine_s95"
ALLOWED = ("g17", "g18")


def materialize(gid: str) -> Path:
    if gid not in ALLOWED:
        raise RuntimeError(f"S118 anchor materializer allows only {ALLOWED}; got {gid}")
    g = gc.GROUPS[gid]
    anchor = g.get("anchor")
    anchor_date = str(g.get("anchor_date") or "").replace("-", "")
    last = g.get("anchor_lasthr_dir")
    if anchor is None or len(anchor_date) != 8 or last not in (-1, 1):
        raise RuntimeError(
            f"{gid}: declared anchor is incomplete: anchor={anchor!r} date={anchor_date!r} last_hour={last!r}"
        )
    path = RENDERS / f"{gid}_anchor.json"
    payload = {
        "schema_version": "s118_ephemeral_anchor_v1",
        "group": gid,
        "date": anchor_date,
        "price": float(anchor),
        "last_hour_dir": "up" if last > 0 else "down",
        "last_hour_dir_numeric": int(last),
        "source": "group_config.GROUPS declared values",
        "actual_tape_read": False,
        "ephemeral_validation_artifact": True,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    groups = sys.argv[1:] or list(ALLOWED)
    out = [str(materialize(g)) for g in groups]
    print(json.dumps({"anchors": out, "actual_tape_read": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
