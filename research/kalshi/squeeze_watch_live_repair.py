#!/usr/bin/env python3
"""S109 fix phase, findings f1 and f3 (state auditor, G22): squeeze_watch's "live" limbs are frozen.

f1 - THE _live FIELDS ARE THE FROZEN VALUE UNDER A LIVE NAME. S108 set out to derive the calendar limb
live and shipped fields that copy the anchor vintage: days_to_calendar_front_expiry_live is a constant 5
and calendar_front_symbol_live a constant NGN26 on all ten G22 days, while flow_calendar correctly walks
4,3,2,1,0 then 21,20,19,18,18 and rolls the symbol to NGQ26 on 0629. The block's own calendar_limb_basis
asserts the opposite in prose - "DETERMINISTIC CALENDAR from flow_calendar and is never masked" - and
active_false_negative states "the LIVE calendar says 5", which is false on nine of ten days. S108 fixed a
false NEGATIVE here and shipped its mirror image: calendar_limb_satisfied_live reads true on 0629-0703,
whose live dte is 18-21, against a play window of <=7. The same object carries frozen_front_expired:true
beside calendar_front_symbol_live:"NGN26", the contract that expired - self-contradictory in one block.

f3 - THE DEAD-SPONSOR ARM IS FROZEN ON THE MAY PROMPT. last_prompt_symbol NGM26 / 2026-05-27 /
sessions_since_prompt_expiry 16 / unwind_watch false, on all ten days. But NGN26 expired 2026-06-26
inside this block, so on 0629 the true last prompt expiry is one session back, not sixteen. The arm is
defined as "a prompt expiry within ~3 sessions with premium stranded in the front" and it reads false on
the seam one session after exactly that. frozen_structure_stale does not cover it: that block scopes to
calendar-front fields and points the reader at flow_calendar, which carries no prompt-expiry field at
all. magnitude.block_gap_ownership evaluates ANCHOR_STRUCTURAL first and a dead squeeze sponsor is one
of its three structural triggers, so a false unwind_watch on the 0626->0629 weekend seam routes the gap
owner past branch (1) without ever testing it - the G19 non-falsifiable shape again.

THE BOOLEAN IS NOT REPAIRED TO true. The gate is (dte <= 7) AND (spread_chg_3d > 0), and the spread limb
is genuinely price-derived and legitimately masked. A derived boolean whose input is unavailable must not
be emitted as false - that is a confident answer to a question the block cannot evaluate. It is set to
null with the reason stated, and the dte limb is served separately so the reader can see which half is
known. That is the auditor's recommendation and it is right.

Idempotent, dry-run by default. Repairs only what it can DERIVE from the same file (flow_calendar and
the block's own expiry calendar); invents nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER_DIR = os.path.join(HERE, "renders", "ng_refine_s95")

BASIS_FIXED = ("days_to_calendar_front_expiry_live and calendar_front_symbol_live are re-derived per day "
               "from flow_calendar (deterministic calendar, never masked). The frozen "
               "days_to_calendar_front_expiry / calendar_front_symbol are the anchor vintage and are kept "
               "only for provenance. The SPREAD limb is genuinely price-derived and stays masked.")
LIMB_NULL = ("UNKNOWN, not false. The gate is (days_to_calendar_front_expiry_live <= 7) AND "
             "(calendar_front_next_spread_chg_3d > 0); the spread limb is masked, so the conjunction "
             "cannot be evaluated. calendar_dte_limb_satisfied_live carries the half that IS knowable. "
             "Do not read a squeeze into the p50 on a limb you cannot see, and do not read its ABSENCE "
             "as a negative either.")


def repair_day(day: str, blk: dict, fc: dict, last_exp: tuple | None, sess_since: int | None) -> list[str]:
    ch = []
    live_dte = fc.get("days_to_futures_expiry")
    live_sym = fc.get("front_symbol_calendar")

    if live_dte is not None and blk.get("days_to_calendar_front_expiry_live") != live_dte:
        ch.append(f"dte_live {blk.get('days_to_calendar_front_expiry_live')} -> {live_dte}")
        blk["days_to_calendar_front_expiry_live"] = live_dte
    if live_sym and blk.get("calendar_front_symbol_live") != live_sym:
        ch.append(f"symbol_live {blk.get('calendar_front_symbol_live')} -> {live_sym}")
        blk["calendar_front_symbol_live"] = live_sym

    # the conjunction is not evaluable; serve the knowable half and null the boolean
    if blk.get("calendar_limb_satisfied_live") is not None:
        ch.append(f"limb_satisfied_live {blk.get('calendar_limb_satisfied_live')} -> null (unevaluable)")
        blk["calendar_limb_satisfied_live"] = None
    if live_dte is not None:
        blk["calendar_dte_limb_satisfied_live"] = bool(live_dte <= 7)
    blk["calendar_limb_note"] = LIMB_NULL
    blk["calendar_limb_basis"] = BASIS_FIXED
    # the prose assertion was false on every day where the two clocks disagree
    if "active_false_negative" in blk:
        blk.pop("active_false_negative")
        blk["active_status_note"] = (
            f"active={blk.get('active')} is the FROZEN vintage's answer and is not decision-legit. Live "
            f"calendar dte for this session is {live_dte} on {live_sym}. Treat active as UNKNOWN. "
            f"(S109: the previous note here asserted the live and frozen clocks agreed at 5, which was "
            f"false on nine of ten days in this block.)")
        ch.append("replaced false active_false_negative prose")

    # f3 - the dead-sponsor arm
    if last_exp and sess_since is not None:
        sym, exp = last_exp
        if blk.get("last_prompt_symbol") != sym or blk.get("sessions_since_prompt_expiry") != sess_since:
            ch.append(f"prompt {blk.get('last_prompt_symbol')}/{blk.get('sessions_since_prompt_expiry')}"
                      f" -> {sym}/{sess_since}")
            blk["last_prompt_symbol"] = sym
            blk["last_prompt_expiry"] = exp
            blk["sessions_since_prompt_expiry"] = sess_since
            blk["unwind_watch"] = bool(sess_since <= 3)
            blk["unwind_basis"] = ("re-derived S109 from the block's own expiry calendar (flow_calendar "
                                   "is_expiry_day); was frozen on the anchor vintage's prompt.")
    return ch


def run(gid: str, write: bool) -> int:
    p = os.path.join(RENDER_DIR, f"{gid.replace('g', 'grp')}_state.json")
    st = json.loads(open(p, encoding="utf-8").read())
    days = sorted(k for k in st if k[:1].isdigit())

    # locate prompt expiries inside the block from the deterministic calendar
    expiries = []
    for d in days:
        fc = st[d].get("flow_calendar") or {}
        if fc.get("is_expiry_day"):
            expiries.append((d, fc.get("front_symbol_calendar"), fc.get("futures_expiry_date")))

    total = []
    for i, d in enumerate(days):
        blk = st[d].get("squeeze_watch")
        fc = st[d].get("flow_calendar") or {}
        if not isinstance(blk, dict):
            continue
        prior = [e for e in expiries if e[0] < d]
        last_exp, sess_since = None, None
        if prior:
            ed, esym, eexp = prior[-1]
            last_exp = (esym, eexp)
            sess_since = days.index(d) - days.index(ed)
        ch = repair_day(d, blk, fc, last_exp, sess_since)
        if ch:
            total.append((d, ch))

    print(f"[squeeze_repair] {gid}: {len(total)} day(s) repaired")
    for d, ch in total:
        print(f"  {d}: " + "; ".join(ch))
    if total and write:
        open(p, "w", encoding="utf-8").write(json.dumps(st))
        print(f"[squeeze_repair] {gid}: WROTE {p}")
    elif total:
        print(f"[squeeze_repair] {gid}: dry run - pass --write")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gids", nargs="+")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    return max(run(g, a.write) for g in a.gids)


if __name__ == "__main__":
    raise SystemExit(main())
