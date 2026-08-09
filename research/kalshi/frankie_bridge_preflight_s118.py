#!/usr/bin/env python3
"""Preflight the namespace-local E->A->B weekend bridge path for S118 G18/G19 validation.

No model is invoked and no realized outcome is read. This exists because the historical Monday
failure was specifically a missing live A bridge; BLD-1-only packet checks do not exercise BLD-2.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_two_group_run_s118 as two  # noqa: E402
import frankie_group_forecast_s118 as runner  # noqa: E402
import group_config as gc  # noqa: E402


def main() -> int:
    namespace = "ci_s118_bridge"
    prep = two.prepare()
    rows = []
    for gid in two.GROUPS:
        days = list(gc.GROUPS[gid]["days"])
        for day in days:
            fri = runner._prior_inblock_friday(days, day)
            if fri is None:
                continue
            prompt, packet = runner._packet(
                "BLD-2", gid, day, "A", namespace, bridge_deviation=True
            )
            out = runner._output_path_from_prompt(
                prompt, namespace, gid, "A", day, "BLD-2"
            )
            text = json.dumps(packet, sort_keys=True)
            if "actual_day_move_usd" in text or "actual_close" in text:
                raise RuntimeError(f"{gid} {day}: realized outcome field entered bridge packet")
            if namespace not in str(out):
                raise RuntimeError(f"{gid} {day}: bridge output escaped namespace: {out}")
            rows.append({
                "group": gid,
                "monday": day,
                "prior_friday": fri,
                "bridge_output": str(out.relative_to(HERE)),
                "actual_tape_read": False,
            })
    if not rows:
        raise RuntimeError("no in-block Monday bridge cases were exercised")
    print(json.dumps({
        "verdict": "PASS",
        "prepare": prep,
        "bridges": rows,
        "actual_tape_read": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
