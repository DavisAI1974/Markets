#!/usr/bin/env python3
"""batch_record.py - the TRAVELER on the pallet (S110 turnaround memo 2.3, lot traceability).

One JSON per group, forecasts/g<N>_batch_record.json, APPENDED at each station. Every entry
carries: station, session, spec versions (SOP + brain), what happened, artifacts touched. The
close-out diff and the andon board read these instead of re-mining prose handoffs.

API:  batch_record.append(gid, station, summary, **extra)   - from any pipeline script
CLI:  python batch_record.py append <gid> <station> "<summary>" [--session S110]
      python batch_record.py show <gid>

Stations (the plant map): staged | inspected | audited | audit-fixed | blind-r1 | coordinated |
scored | archived | refine-r1 | refine-r2 | merged | nonconformance | note
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FC = os.path.join(HERE, "forecasts")


def _sop_version() -> str:
    p = os.path.join(HERE, "agents", "RUN_SOP.md")
    if os.path.exists(p):
        m = re.search(r"^- (v[\d.]+) ", open(p, encoding="utf-8").read(), re.M)
        if m:
            return m.group(1)
    return "pre-SOP"


def _brain_version() -> str:
    p = os.path.join(HERE, "knowledge", "ng_brain.json")
    try:
        b = json.load(open(p, encoding="utf-8"))
        return str((b.get("meta") or {}).get("version") or (b.get("meta") or {}).get("brain_version") or "?")
    except Exception:
        return "?"


def _cur_session() -> str:
    root = os.path.abspath(os.path.join(HERE, "..", ".."))
    best = 0
    for h in glob.glob(os.path.join(root, "SESSION_HANDOFF_*_S*.md")):
        m = re.search(r"_S(\d+)\.md$", h)
        if m:
            best = max(best, int(m.group(1)))
    return f"S{best + 1}" if best else "S?"      # the handoff for the CURRENT session lands at close


def path_for(gid: str) -> str:
    return os.path.join(FC, f"g{gid.lstrip('g')}_batch_record.json")


def load(gid: str) -> dict:
    p = path_for(gid)
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    return {"group": f"g{gid.lstrip('g')}", "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "entries": []}


def append(gid: str, station: str, summary: str, session: str | None = None, **extra) -> dict:
    rec = load(gid)
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "session": session or _cur_session(), "station": station,
             "sop": _sop_version(), "brain": _brain_version(), "summary": summary}
    if extra:
        entry.update(extra)
    rec["entries"].append(entry)
    with open(path_for(gid), "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    return entry


def show(gid: str) -> None:
    rec = load(gid)
    print(f"BATCH RECORD {rec['group']} - {len(rec['entries'])} entries")
    for e in rec["entries"]:
        print(f"  {e['ts']} {e['session']:>5} [{e['station']:<13}] sop {e.get('sop','?'):>7} "
              f"brain {e.get('brain','?'):>8} | {e['summary']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("append")
    a1.add_argument("gid"); a1.add_argument("station"); a1.add_argument("summary")
    a1.add_argument("--session", default=None)
    a2 = sub.add_parser("show")
    a2.add_argument("gid")
    a = ap.parse_args()
    if a.cmd == "append":
        print(json.dumps(append(a.gid, a.station, a.summary, session=a.session)))
    else:
        show(a.gid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
