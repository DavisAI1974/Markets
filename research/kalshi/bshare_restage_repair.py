#!/usr/bin/env python3
"""S109: repair session_b_share in states staged on the S108 leg path, WITHOUT a data plane.

THE DEFECT. forecast_harness._tape_day_stats tests `side == "B"`, but the S108 leg reader
(tape_reconcile.load_leg_trades) spells side as flow_read's signed int (1/-1/0) rather than the raw
tape string the continuous reader returns. Nothing matched, so `buys` summed to 0 and session_b_share
served a hard 0.0 on every scored-leg session. It hid because _tape_enrich copies the OTHER b_share
fields through from flow_read - session_b_share was the one field missing from that copy list.
Blast radius: G22 and G23 only (8 leg days each + both prior_full_session limbs); every earlier group
was staged on the continuous string path and is untouched.

WHY RECONSTRUCT INSTEAD OF RE-STAGE. A re-stage is the authoritative fix and needs the databento leg
files. A group staged at S108+ is meant to run BOTH rounds with no data plane, and the keys do not
survive a session - so demanding a re-stage to clear a defect the state can settle by itself would
strand two staged groups. The three fields are algebraically locked:

    b_share  = buys / tot                       (total-volume basis, the ORIGINAL series)
    b_share2 = buys / sides                      (two-sided basis, S108)
    sides    = tot * (1 - unsided_volume_frac)
  =>  b_share = b_share2 * (1 - unsided_volume_frac)

That is an IDENTITY, not a fit. It reproduces every continuous-store day in G22/G23 to the third
decimal - the days where the harness computed b_share correctly and independently.

PRECISION, STATED. b_share2 and unsided_volume_frac are each already rounded to 3 dp, so the product
carries up to ~0.002 of compounding error against the value a re-stage would compute from raw lots.
Each repaired reading declares itself via session_b_share_basis, so no specialist can mistake a
reconstruction for a direct measurement, and a later re-stage overwrites it with the exact figure.

Idempotent: a reading that already reconciles is left byte-identical.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATES = HERE / "renders" / "ng_refine_s95"
TOL = 0.002
BASIS = ("RECONSTRUCTED S109 from session_b_share_two_sided x (1 - unsided_volume_frac), an exact "
         "identity, because the S108 leg reader's side encoding zeroed the direct computation. "
         "Carries up to ~0.002 of rounding error vs a re-stage off raw lots; a re-stage overwrites it.")


def _repair_scope(scope: dict) -> str | None:
    """Repair one tape_conditions-shaped dict in place. Returns a description if it changed."""
    if not isinstance(scope, dict):
        return None
    b, b2 = scope.get("session_b_share"), scope.get("session_b_share_two_sided")
    u = scope.get("unsided_volume_frac")
    if not all(isinstance(x, (int, float)) for x in (b, b2, u)):
        return None
    pred = round(b2 * (1.0 - u), 3)
    if abs(pred - b) <= TOL:
        return None                      # already reconciles - leave it exactly as it is
    scope["session_b_share"] = pred
    scope["session_b_share_basis"] = BASIS
    return f"{scope.get('session')} [{scope.get('source_store')}] {b} -> {pred}"


def repair(gid: str, write: bool) -> int:
    path = STATES / f"{gid.replace('g', 'grp')}_state.json"
    if not path.exists():
        print(f"[bshare_repair] {gid}: no state at {path}", file=sys.stderr)
        return 1
    state = json.loads(path.read_text(encoding="utf-8"))
    changed = []
    for day in [k for k in state if k[:1].isdigit()]:
        tc = (state[day] or {}).get("tape_conditions")
        if not isinstance(tc, dict):
            continue
        for scope in (tc, tc.get("prior_full_session")):
            msg = _repair_scope(scope)
            if msg:
                changed.append(f"  {day}: {msg}")
    print(f"[bshare_repair] {gid}: {len(changed)} reading(s) reconstructed")
    for c in changed:
        print(c)
    if changed and write:
        # The staged states are compact single-line JSON. json.dumps' defaults round-trip them
        # byte-identically (verified), so the diff is confined to the repaired readings and does not
        # reformat 600KB of untouched state.
        path.write_text(json.dumps(state), encoding="utf-8")
        print(f"[bshare_repair] {gid}: WROTE {path}")
    elif changed:
        print(f"[bshare_repair] {gid}: dry run - pass --write to apply")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gids", nargs="+", help="group ids, e.g. g22 g23")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    return max(repair(g, args.write) for g in args.gids)


if __name__ == "__main__":
    raise SystemExit(main())
