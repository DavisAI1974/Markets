#!/usr/bin/env python3
"""S109 HOLE #11: build per-day CAUSAL SLICES of a blind state, so a specialist physically cannot
read past its own decision point.

THE DEFECT IS THE FILE LAYOUT, NOT THE AGENT. A block's decision state serves, under each day's key,
the PRIOR session's realized tape. That is correct per-day. But every day of the block lives in ONE
file, so day X's OWN realized outcome sits one block later:

    [20260623].tape_conditions        = session 20260622 realized  (sflow -3717, phases [622,-3942,-397])
    [20260629].tape_conditions.prior_full_session = session 20260626 realized
    [20260703].stor_surprise          = 39.2, the 07-02 print's own surprise

So a specialist forecasting 0622 reads 0623's block and sees 0622's realized flow; one forecasting the
0702 EIA day reads 0703's block and sees that print's realized surprise. This is not a price leak - it
is a CAUSALITY leak, and the doctrine is explicit that causality is physics, not a mask: "neither sees
the FUTURE." Measured on the G22 wave-1 blind: all three specialists reached forward and ALL THREE
DECLARED IT unprompted. D forecast an EIA print day already knowing the print. E's entire phase read
(+688 / -2554 / +2737) and its whole handoff_out were built on its own day's realized close phase.

WHY A RULE IN THE PROMPT IS NOT THE FIX. The specialists were already under a hard read-only-here rule
and they still reached forward, because the data was in the file they were told to read and reaching
for it is indistinguishable from diligence. The only defence that works is to make the future ABSENT.
This is the same lesson as the filename collision and hole #8: a field-level check, or an instruction,
cannot catch a wrong-but-well-formed input - only removing it, or reconciling against an independent
source, can.

THE SLICE. For a forecast of day X, the legitimate state is every block for a day <= X. Day X's own
block is INCLUDED - it carries session X-1's tape, which is exactly what is known at X's open. Blocks
for days > X are dropped entirely. One slice per owned day, because the walk forecasts a ROLLING daily
curve: a specialist owning four days must forecast each from that day's own information set, not from
the union of all four.

WHAT THIS DELIBERATELY DOES NOT DO. It does not touch the price mask (already handled by mask_after),
does not drop any non-price channel, and does not reduce what the blind is entitled to at its decision
point. The blind still gets the whole kitchen sink - as of the open of the day it is forecasting.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER_DIR = os.path.join(HERE, "renders", "ng_refine_s95")
sys.path.insert(0, HERE)
import group_config as gc  # noqa: E402


def slice_state(state: dict, upto: str) -> dict:
    """Every meta key, plus every day block whose date is <= upto."""
    out = {}
    for k, v in state.items():
        if not k[:1].isdigit():
            out[k] = v                      # _information_clock and any other static meta
        elif k <= upto:
            out[k] = v
    return out


def audit(sl: dict, upto: str) -> list[str]:
    """Prove the slice cannot see past `upto`. Returns violations (empty = clean)."""
    bad = []
    for k in sl:
        if k[:1].isdigit() and k > upto:
            bad.append(f"day block {k} present in a slice cut at {upto}")
    # the specific channels that carried the leak
    for k, v in sl.items():
        if not k[:1].isdigit():
            continue
        tc = (v or {}).get("tape_conditions") or {}
        for scope, label in ((tc, "tape_conditions"),
                             (tc.get("prior_full_session") or {}, "tape_conditions.prior_full_session")):
            ses = scope.get("session")
            if ses and ses >= upto:
                bad.append(f"[{k}].{label} carries session {ses} - at or past the decision day {upto}")
    return bad


def forward_stamps(sl: dict, upto: str) -> list[str]:
    """S109, found by specialist C on 0630 mid-run: cutting by DAY BLOCK is necessary and NOT
    sufficient. A field INSIDE a legitimate block can carry a timestamp from past the decision point.
    Measured: storage_consensus.next_print.consensus_pre_print_snapshot_utc reads 2026-07-02 under the
    blocks for 0629, 0630 AND 0701 - a 'pre-print' field stamped after the days it is served to.

    This is a WEAKER leak than the block-level one (a capture stamp is not an outcome), which is why it
    is reported rather than hard-failed: several of these are declared, and stripping a field the
    specialists are successfully discounting would cost more than it saves. But it must be VISIBLE, and
    the day-slice audit alone would never show it.
    """
    import re
    out, pat = [], re.compile(r"(20\d{2})-(\d{2})-(\d{2})T")

    def walk(o, p=""):
        if isinstance(o, dict):
            for kk, vv in o.items():
                yield from walk(vv, p + "/" + kk)
        elif isinstance(o, list):
            for i, vv in enumerate(o):
                yield from walk(vv, p + f"[{i}]")
        else:
            yield p, o

    for k, v in sl.items():
        if not k[:1].isdigit() or k != upto:
            continue            # only the decision day's own block: earlier blocks legitimately differ
        for path, val in walk(v):
            if not isinstance(val, str):
                continue
            m = pat.match(val)
            if not m or f"{m.group(1)}{m.group(2)}{m.group(3)}" <= upto:
                continue
            # A SCHEDULED event time in the future is legitimate - a forecaster knows when the next EIA
            # print lands; that is deterministic calendar, the same class flow_calendar serves live.
            # A CAPTURE stamp in the future is not: it says the VALUE was observed after the decision
            # point. Only the second is a leak, and conflating them would cry wolf on every block that
            # correctly carries a forward schedule.
            leaf = path.rsplit("/", 1)[-1]
            if "snapshot" in leaf or leaf in ("captured_utc", "as_of_utc", "retrieved_utc"):
                out.append(f"[{upto}]{path} = {val} - VALUE CAPTURED after the decision day")
    return out


def build(gid: str, write: bool, outdir: str) -> int:
    path = os.path.join(RENDER_DIR, f"{gid.replace('g', 'grp')}_state.json")
    state = json.loads(open(path, encoding="utf-8").read())
    owner = gc.owner_map(gid)
    days = gc.GROUPS[gid]["days"]
    rc = 0
    for d in days:
        sl = slice_state(state, d)
        bad = audit(sl, d)
        nblocks = sum(1 for k in sl if k[:1].isdigit())
        status = "CLEAN" if not bad else "VIOLATION"
        print(f"  {d} (owner {owner[d]}): {nblocks} day blocks <= {d}  [{status}]")
        for b in bad:
            print(f"      {b}")
            rc = 1
        # Reported, never fatal - see forward_stamps(). A capture stamp past the decision point is a
        # weaker leak than a forward block, but it is invisible to the day-slice audit, so it has to be
        # printed or it does not exist. Dead code here would have silently un-found C's catch.
        for w in forward_stamps(sl, d):
            print(f"      note {w}")
        if write and not bad:
            os.makedirs(outdir, exist_ok=True)
            p = os.path.join(outdir, f"state_{d}.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(sl, fh)
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gid")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--outdir", required=False, default=None)
    a = ap.parse_args()
    out = a.outdir or os.path.join(RENDER_DIR, f"{a.gid}_causal_slices")
    print(f"[causal_slices] {a.gid} -> {out}")
    return build(a.gid, a.write, out)


if __name__ == "__main__":
    raise SystemExit(main())
