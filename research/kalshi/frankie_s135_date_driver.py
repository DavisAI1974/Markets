#!/usr/bin/env python3
"""Permanent thin driver for S135 date-window ChatGPT sessions.

Future runs edit only date_run_session.json.  This driver keeps the two historical transport seams
that were proven during the Sep-22..Oct-03 run out of the workflow YAML:

1. S131 historical wall: retain current later-learned rules/plays while visibly withholding direct
   realized-outcome leaves dated on/after each historical decision cutoff.
2. Friday E -> A transport: attach the frozen Friday owner's handoff_out to the Monday A bridge packet;
   A still receives the legally completed Friday session separately and may override E's forecast read.

Frankie, spawn.py, brain/schema, specialist roles, datapoint universe and the S135 state machine remain
unchanged.  Hydration/synthesis remains rejected.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import brain_view
import frankie_g3_reblind_s131_runner as historical_wall
import frankie_s135_date_session as session
import frankie_s135_current_runtime as runtime
import frankie_s135_group_runner as runner
import group_config as gc

_OUTPUTS: Path | None = None
_ORIG_PACKET_SEQUENTIAL = runtime.packet_sequential


def _install_historical_role_view(gid: str, state: dict) -> None:
    def builder(request_gid: str, day: str, namespace: str) -> Path:
        if request_gid != gid:
            raise RuntimeError(f"date-session role builder got unexpected gid {request_gid}")
        brain = brain_view.load()
        view, _served, _withheld = brain_view.build(
            brain, "specialist", phase="working", window_days=gc.GROUPS[gid]["days"]
        )
        redacted = [0]
        view = historical_wall._redact_post_cutoff_outcomes(view, day, redacted)
        if isinstance(view.get("meta"), dict):
            view["meta"]["s135_historical_cutoff"] = day
            view["meta"]["s135_post_cutoff_direct_outcomes_redacted"] = redacted[0]
        view = brain_view.annotate_evaluability(view, state[day])
        path = runtime.base.PACKET_ROOT / namespace / gid / f"brain_view_{day}.json"
        session._write(path, view)
        return path

    runtime.base._build_role_view = builder


def _packet_sequential_with_friday_handoff(template, gid, day, spec, namespace, **kwargs):
    prompt, packet = _ORIG_PACKET_SEQUENTIAL(template, gid, day, spec, namespace, **kwargs)
    if template != "BLD-2" or spec != "A" or _OUTPUTS is None:
        return prompt, packet

    days = list(gc.GROUPS[gid]["days"])
    if day not in days:
        return prompt, packet
    index = days.index(day)
    if index <= 0:  # starter Friday anchor -> first Monday has no in-window E forecast.
        return prompt, packet

    friday = days[index - 1]
    owner = gc.owner_map(gid)[friday]
    if owner != "E":
        return prompt, packet
    path = _OUTPUTS / f"forecast_{owner}_{friday}.json"
    if not path.is_file():
        raise SystemExit(f"Friday owner forecast missing before A bridge: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    handoff = obj.get("handoff_out")
    if not isinstance(handoff, dict):
        raise SystemExit(f"Friday owner handoff_out missing before A bridge: {path}")

    packet = dict(packet)
    packet["s135_friday_owner_handoff"] = {
        "from_day": friday,
        "from_specialist": owner,
        "forecast_disposition": obj.get("disposition"),
        "handoff_out": handoff,
    }
    runner._assert_packet_outcome_wall(runtime, packet, gid, day)
    return prompt, packet


def main() -> int:
    global _OUTPUTS
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))

    days = cfg["days"]
    if isinstance(days, list):
        days = ",".join(str(x) for x in days)
    eia = cfg.get("eia", [])
    if isinstance(eia, list):
        eia = ",".join(str(x) for x in eia)

    _OUTPUTS = Path(cfg["outputs"])
    session._install_inprocess_role_view = _install_historical_role_view
    runtime.packet_sequential = _packet_sequential_with_friday_handoff

    argv = [
        "frankie_s135_date_session.py",
        "--days", str(days),
        "--anchor-date", str(cfg["anchor_date"]),
        "--anchor", str(cfg["anchor"]),
        "--anchor-lasthr-dir", str(cfg.get("anchor_lasthr_dir", 0)),
        "--pre-leg", str(cfg["pre_leg"]),
        "--eia", str(eia),
        "--basis", str(cfg.get("basis", "date-driven S135 historical run")),
        "--namespace", str(cfg.get("namespace", "frankie_s135_date_session")),
        "--outputs", str(_OUTPUTS),
        "--out", str(args.out),
    ]
    if cfg.get("seam"):
        argv += ["--seam", str(cfg["seam"]), "--post-leg", str(cfg["post_leg"])]
    sys.argv = argv
    return session.main()


if __name__ == "__main__":
    raise SystemExit(main())
