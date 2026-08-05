#!/usr/bin/env python3
"""
spawn.py - fill every SOP slot BY LOOKUP and emit the exact prompt. (Registry A-7.)

WHY. RUN_SOP.md carries 13 slot placeholders across 36 occurrences and EVERY ONE IS FILLED BY HAND.
The SOP's own rule says slot values "are LOOKUPS (from group_config.py, committed artifacts, or the
calendar feeds), never judgment calls" - and the rule did not hold, because nothing enforced it.

NC-1 IS THE INSTANCE, AND IT IS WHAT THIS FILE EXISTS TO MAKE UNREACHABLE. The G23 refine spawn for
0715 asserted "first post-roll session". C-0715 checked `flow_calendar` and found `in_bcom_roll`
TRUE and `bcom_roll_day_n` 5 - the legs are offset (GSCI 0708-0714, BCOM 0709-0715), so 0715 is BCOM
roll day 5 of 5 and the first clean session is 0716. The same false premise sat in that day's BLIND
posterior. DECISIONS.md records the diagnosis exactly: "operator error, not a data gap - and I
propagated it into the directive... calendar premises in a directive must be QUOTED from
flow_calendar, never paraphrased."

So CAL_FACTS is GENERATED here, quoting the served fields with their values. A premise that cannot
be typed cannot be wrong. Greg's A-7 framing: running off-SOP becomes IMPOSSIBLE rather than
forbidden.

THE STOP RULE. A slot that cannot be resolved from a committed artifact HALTS the emission and says
which lookup failed. It is never left blank, never guessed, and never quietly dropped - that is the
SOP's own jidoka rule (a failing gate stops the line) applied to prompt construction.

USAGE
    python spawn.py slots g23                    # every slot, with the artifact each came from
    python spawn.py calfacts g23                 # the generated CAL_FACTS block alone
    python spawn.py emit BLD-1 g23 --day 20260715
    python spawn.py emit AUD-1 g23
    python spawn.py selftest                     # includes the NC-1 regression test
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RN = os.path.join(HERE, "renders", "ng_refine_s95")
BRAIN = os.path.join(HERE, "knowledge", "ng_brain.json")

sys.path.insert(0, HERE)
import group_config as gc  # noqa: E402


class SlotError(Exception):
    """A lookup failed. The line stops here rather than emitting a prompt with a guessed value."""


def _state_path(gid):
    n = gid.lstrip("g")
    p = os.path.join(RN, "grp%s_state.json" % n)
    if not os.path.exists(p):
        raise SlotError("STATE: %s does not exist" % os.path.relpath(p, ROOT))
    return p


def _served_days(gid):
    with open(_state_path(gid), encoding="utf-8") as f:
        d = json.load(f)
    return {k: v for k, v in d.items() if re.fullmatch(r"\d{8}", k)}


def cal_facts(gid):
    """THE NC-1 FIX. Every calendar premise is QUOTED from the served flow_calendar with its field
    name and value beside it, so a directive cannot assert a calendar fact the data contradicts.
    Mechanical lookups only - no interpretation, no leads, no hints (the SOP's own CAL_FACTS rule).
    """
    days = _served_days(gid)
    if not days:
        raise SlotError("CAL_FACTS: no served days in the state for %s" % gid)
    out = []
    eia, holidays, rolls, expiries = [], [], [], []
    for d in sorted(days):
        fc = days[d].get("flow_calendar") or {}
        if not fc:
            raise SlotError("CAL_FACTS: %s has no flow_calendar block - cannot quote a premise "
                            "that is not served" % d)
        if fc.get("days_to_next_eia_release") == 0:
            eia.append(d)
        if fc.get("cme_holiday"):
            holidays.append("%s (%s)" % (d, fc.get("cme_holiday_name") or "unnamed"))
        elif fc.get("cme_early_close"):
            holidays.append("%s (early close)" % d)
        # the roll legs are OFFSET and that offset is exactly what NC-1 got wrong, so both are
        # quoted per day rather than summarised into one window
        bits = []
        if fc.get("in_bcom_roll"):
            bits.append("in_bcom_roll TRUE, bcom_roll_day_n %s" % fc.get("bcom_roll_day_n"))
        if fc.get("in_gsci_roll"):
            bits.append("in_gsci_roll TRUE, gsci_roll_day_n %s" % fc.get("gsci_roll_day_n"))
        if bits:
            rolls.append("%s: %s" % (d, "; ".join(bits)))
        if fc.get("days_to_futures_expiry") == 0:
            expiries.append("%s: futures expiry (front %s)" % (d, fc.get("front_symbol_calendar")))
    out.append("EIA print days in the block (days_to_next_eia_release == 0): %s"
               % (", ".join(eia) if eia else "none"))
    out.append("Holidays / shortened sessions (cme_holiday / cme_early_close): %s"
               % (", ".join(holidays) if holidays else "none"))
    out.append("Index-roll days, quoted per leg - THE LEGS ARE OFFSET, do not merge them:")
    out.extend("   %s" % r for r in rolls) if rolls else out.append("   none in this block")
    out.append("Futures expiry inside the block: %s"
               % (", ".join(expiries) if expiries else "none"))
    out.append("Front contract by day (front_symbol_calendar): %s"
               % ", ".join(sorted({(days[d].get('flow_calendar') or {}).get('front_symbol_calendar')
                                   or "?" for d in days})))
    return "\n".join(out)


def slots(gid, day=None, spec=None):
    """Resolve every slot, each with the artifact it came from. Raises SlotError on any failure."""
    if gid not in gc.GROUPS:
        raise SlotError("GID: %r is not in group_config.GROUPS" % gid)
    g = gc.GROUPS[gid]
    n = gid.lstrip("g")
    anchor = os.path.join(RN, "%s_anchor.json" % gid)
    if not os.path.exists(anchor):
        raise SlotError("ANCHOR: %s does not exist - the anchor artifact is required, and a "
                        "hand-carried anchor is what S108 lost with a scratchpad"
                        % os.path.relpath(anchor, ROOT))
    with open(BRAIN, encoding="utf-8") as f:
        brain_v = json.load(f)["meta"]["version"]
    owners = gc.owner_map(gid)
    s = {
        "GID": (gid, "argument"),
        "N": (n, "derived from GID"),
        "STATE": (os.path.relpath(_state_path(gid), ROOT), "committed artifact"),
        "ANCHOR": (os.path.relpath(anchor, ROOT), "committed artifact"),
        "BRAIN_V": (brain_v, "knowledge/ng_brain.json meta.version"),
        "DAYS": (", ".join(g["days"]), "group_config.GROUPS[%s].days" % gid),
        "WINDOW": (str(g.get("window")), "group_config"),
        "SEAM": (str(g.get("seam")), "group_config"),
        "CAL_FACTS": (cal_facts(gid), "GENERATED from the served flow_calendar - never typed"),
    }
    if day:
        if day not in owners:
            raise SlotError("DAY: %s is not an owned day of %s (owner_map has %s)"
                            % (day, gid, ", ".join(sorted(owners))))
        served = _served_days(gid)
        if day not in served:
            raise SlotError("DAY: %s is not served in the state file" % day)
        s["DAY"] = (day, "argument, checked against owner_map and the state")
        s["X"] = (owners[day], "group_config.owner_map(%s)[%s]" % (gid, day))
        s["dow"] = (served[day].get("dow") or "?", "state.%s.dow" % day)
        s["DAYS_OWNED"] = (", ".join(d for d, o in sorted(owners.items()) if o == owners[day]),
                           "group_config.owner_map")
        s["SLICE"] = (os.path.relpath(os.path.join(RN, "%s_causal_slices" % gid,
                                                   "state_%s.json" % day), ROOT),
                      "per-day causal slice (D3)")
    if spec:
        s["X"] = (spec, "argument")
        s["DAYS_OWNED"] = (", ".join(d for d, o in sorted(owners.items()) if o == spec),
                           "group_config.owner_map")
    return s


def cmd_slots(a):
    try:
        s = slots(a.gid, a.day, a.spec)
    except SlotError as e:
        print("STOP - slot lookup failed: %s" % e)
        return 1
    print("slots for %s%s\n" % (a.gid, (" day %s" % a.day) if a.day else ""))
    for k, (v, src) in s.items():
        val = v if "\n" not in str(v) else "<%d lines>" % len(str(v).split("\n"))
        print("  {%-10s} = %-58s  <- %s" % (k, str(val)[:58], src))
    return 0


def cmd_calfacts(a):
    try:
        print(cal_facts(a.gid))
    except SlotError as e:
        print("STOP - %s" % e)
        return 1
    return 0


TEMPLATES = {
    "BLD-1": """You are specialist {X} of the NG 5-specialist forecaster, BLIND mode, group {GID}, round 1.
Your reasoning files are canonical and shared with the refine - read BOTH, in full, FIRST:
  research/kalshi/agents/mbo_refine_shared.md
  research/kalshi/agents/mbo_specialist_{X}.md
Follow them exactly. Blind mode is a DATA fact, not a rule change: your state has the price curve
masked. Causality is physics: your state is a per-day causal slice and contains nothing past your
decision point. Do not attempt to obtain masked or future data.

SPAWN PARAMETERS
- GROUP {GID} (N={N}), SPECIALIST {X}, ROUND 1, BLIND. Brain: knowledge/ng_brain.json ({BRAIN_V}).
- YOUR DAY: {DAY} ({dow}). You own this one day in this run.
- YOUR STATE (the only state you read): {SLICE}
- ANCHOR (group reference level): {ANCHOR}

CONTEXT - CALENDAR FACTS, QUOTED FROM THE SERVED flow_calendar. These are lookups, not hints, and
they are generated rather than typed. If your own read of the state disagrees with any line here,
STOP and report the discrepancy - do not reason past it:
{CAL_FACTS}

OUTPUT - write forecasts/g{N}_perday/grp{N}_{X}_{DAY}.json per the output contract in
mbo_refine_shared.md. Declare any input you found defective rather than silently working around it.
""",
    "AUD-1": """You are the STATE AUDITOR for group {GID} of the NG forecaster walk. Your canonical role file is
research/kalshi/agents/state_auditor.md - read it FIRST, in full, and follow it exactly.

THE GROUP UNDER AUDIT
- Group: {GID}. Days: {DAYS}. Window: {WINDOW}. Seam: {SEAM}.
- Decision state (your primary object): {STATE}
- Anchor artifact (also served to the run, in scope): {ANCHOR}
- Brain (for plays_affected greps): knowledge/ng_brain.json ({BRAIN_V})

CONTEXT - CALENDAR FACTS, QUOTED FROM THE SERVED flow_calendar, generated rather than typed:
{CAL_FACTS}

You produce NO forecasts, no direction calls, no price reasoning. Output per the role file.
""",
}


def cmd_emit(a):
    try:
        s = slots(a.gid, a.day, a.spec)
    except SlotError as e:
        print("STOP - slot lookup failed: %s" % e)
        return 1
    t = TEMPLATES.get(a.template)
    if t is None:
        print("unknown template %r - have %s" % (a.template, ", ".join(TEMPLATES)))
        return 1
    need = set(re.findall(r"\{([A-Za-z_]+)\}", t))
    missing = sorted(need - set(s))
    if missing:
        # THE STOP RULE: an unresolved slot halts emission. Never blank, never guessed.
        print("STOP - template %s needs slots that did not resolve: %s"
              % (a.template, ", ".join(missing)))
        print("       (supply --day / --spec, or fix the missing artifact)")
        return 1
    print(t.format(**{k: v for k, (v, _) in s.items()}))
    return 0


def cmd_selftest(a):
    res = []

    def check(name, ok):
        res.append(ok)
        print("  %-4s | %s" % ("PASS" if ok else "FAIL", name))

    # THE NC-1 REGRESSION TEST. The G23 refine directive for 0715 asserted "first post-roll
    # session"; flow_calendar says in_bcom_roll TRUE, bcom_roll_day_n 5. Generated CAL_FACTS must
    # state the roll fact, so the false premise cannot be typed in the first place.
    cf = cal_facts("g23")
    check("NC-1: generated CAL_FACTS reports 0715 as inside the BCOM roll",
          "20260715" in cf and "bcom_roll_day_n 5" in cf)
    check("NC-1: the roll legs are quoted separately, not merged",
          "THE LEGS ARE OFFSET" in cf)
    check("CAL_FACTS names the EIA print days from the served field",
          "days_to_next_eia_release == 0" in cf)

    try:
        slots("g99")
        check("an unknown group STOPS", False)
    except SlotError:
        check("an unknown group STOPS", True)

    try:
        slots("g23", day="20260704")
        check("a day outside owner_map STOPS", False)
    except SlotError:
        check("a day outside owner_map STOPS", True)

    s = slots("g23", day="20260715")
    check("the owner is looked up, not typed (0715 -> C)", s["X"][0] == "C")
    check("every slot declares its source", all(src for _, src in s.values()))

    import io, contextlib
    class _A: pass
    arg = _A(); arg.gid = "g23"; arg.day = None; arg.spec = None; arg.template = "BLD-1"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cmd_emit(arg)
    check("emitting a per-day template with no day STOPS rather than blanking",
          rc == 1 and "did not resolve" in buf.getvalue())

    arg.day = "20260715"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cmd_emit(arg)
    out = buf.getvalue()
    check("a fully-resolved template emits with no placeholder left",
          rc == 0 and not re.search(r"\{[A-Z_]{2,}\}", out))
    check("the emitted prompt carries the roll fact NC-1 got wrong",
          "bcom_roll_day_n 5" in out)

    print("\n  %d/%d passed" % (sum(res), len(res)))
    return 0 if all(res) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("slots"); p.add_argument("gid"); p.add_argument("--day")
    p.add_argument("--spec")
    p = sub.add_parser("calfacts"); p.add_argument("gid")
    p = sub.add_parser("emit"); p.add_argument("template"); p.add_argument("gid")
    p.add_argument("--day"); p.add_argument("--spec")
    sub.add_parser("selftest")
    a = ap.parse_args()
    return {"slots": cmd_slots, "calfacts": cmd_calfacts,
            "emit": cmd_emit, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
