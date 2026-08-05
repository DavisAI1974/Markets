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
import datetime as dt
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



import plant_calendar as pcal  # noqa: E402


def day_calendar(gid, day):
    """PER-DAY calendar context for the specialist forecasting THIS day.

    GREG, S112: "The agents are going to have to get the holiday schedule when those days are
    getting forecasts made because it will change the trading days."

    THE MEASURED GAP HE IS NAMING. The served flow_calendar carries holiday fields for THAT DAY
    ONLY (cme_holiday, cme_early_close, cme_session_class) and has NO prior-session field of any
    kind - checked across the served state, `prior`/`since`/`prev` return nothing. So a specialist
    on a Monday after a Friday holiday cannot tell that its prior session was THURSDAY. It inherits
    a handoff from a session it cannot locate, and the weekend seam it thinks it is crossing is
    actually a four-day gap.

    NOT A LEAK, and this is why it can be served to a BLIND specialist. The state ALREADY serves
    forward-looking calendar: days_to_next_eia_release, days_to_futures_expiry, days_to_opex and
    next_eia_release_datetime_et are all dated ahead by construction. Calendar is deterministic and
    public; D2's one deliberate mask is the PRICE CURVE. So forward holiday facts are the same
    class as what the blind already reads, and my earlier A-13 note - that a per-day CAL_FACTS
    would have to be truncated at the decision point - was over-cautious for calendar specifically.

    Computed from plant_calendar's RULES, not from flow_calendar.CME_HOLIDAYS, because that table
    ends 2027-02-15 and a specialist forecasting past it would be told every day is a normal one."""
    d = dt.datetime.strptime(day, "%Y%m%d").date()
    # a generous window either side so the block's own shape is visible
    ss = pcal.sessions(d - dt.timedelta(days=21), d + dt.timedelta(days=21))
    dates = [x["date"] for x in ss]
    if day not in dates:
        raise SlotError("DAY_CALENDAR: %s is not a trading session under the calendar rules "
                        "(full closure or weekend)" % day)
    i = dates.index(day)
    prior = ss[i - 1] if i > 0 else None
    nxt = ss[i + 1] if i + 1 < len(ss) else None
    me = ss[i]
    out = []
    out.append("THIS SESSION: %s %s, class %s%s"
               % (me["date"], me["dow"], me["session_class"],
                  " (%s)" % me["holiday"] if me["holiday"] else ""))
    if prior:
        gap = (d - dt.datetime.strptime(prior["date"], "%Y%m%d").date()).days
        note = ""
        if gap > 1:
            skipped = []
            probe = d - dt.timedelta(days=1)
            while probe.strftime("%Y%m%d") != prior["date"]:
                h = pcal.holidays(probe.year).get(probe.isoformat())
                skipped.append("%s %s%s" % (probe.strftime("%Y%m%d"), probe.strftime("%a"),
                                            " %s" % h[0] if h else ""))
                probe -= dt.timedelta(days=1)
            note = "  <- NOT the previous calendar day. Skipped: %s" % "; ".join(reversed(skipped))
        out.append("PRIOR TRADING SESSION: %s %s, class %s, %d calendar day(s) back%s"
                   % (prior["date"], prior["dow"], prior["session_class"], gap, note))
    if nxt:
        out.append("NEXT TRADING SESSION: %s %s, class %s"
                   % (nxt["date"], nxt["dow"], nxt["session_class"]))
    ahead = [x for x in ss[i + 1:] if x["session_class"] != "normal"]
    out.append("NON-NORMAL SESSIONS IN THE NEXT THREE WEEKS: %s"
               % ("; ".join("%s %s %s" % (x["date"], x["holiday"], x["session_class"])
                            for x in ahead[:4]) if ahead else "none"))
    return "\n".join(out)


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
        s["DAY_CALENDAR"] = (day_calendar(gid, day),
                             "GENERATED from plant_calendar RULES - prior/next trading session, "
                             "holiday gaps, upcoming non-normal sessions")
        s["SLICE"] = (os.path.relpath(os.path.join(RN, "%s_causal_slices" % gid,
                                                   "state_%s.json" % day), ROOT),
                      "per-day causal slice (D3)")
    if spec:
        s["X"] = (spec, "argument")
        s["DAYS_OWNED"] = (", ".join(d for d, o in sorted(owners.items()) if o == spec),
                           "group_config.owner_map")
    if day:
        fc = _served_days(gid)[day].get("flow_calendar") or {}
        # day_class is NOT served, so it is DERIVED - and the derivation quotes the served fields
        # it rests on, so a reader can check it rather than trust it.
        parts = [s["dow"][0]]
        if fc.get("days_to_next_eia_release") == 0:
            parts.append("eia_print_thursday")
        if fc.get("cme_holiday"):
            parts.append("cme_holiday:%s" % (fc.get("cme_holiday_name") or "unnamed"))
        elif fc.get("cme_early_close"):
            parts.append("cme_early_close")
        if fc.get("days_to_futures_expiry") == 0:
            parts.append("futures_expiry")
        if fc.get("in_bcom_roll") or fc.get("in_gsci_roll"):
            parts.append("index_roll")
        s["day_class"] = (" | ".join(parts),
                          "DERIVED from state.dow + flow_calendar "
                          "(days_to_next_eia_release, cme_holiday, days_to_futures_expiry, "
                          "in_*_roll) - not a served field")
        # the weekend bridge pair: a Monday and the Friday whose exit feeds it
        served = sorted(_served_days(gid))
        if s["dow"][0] == "Mon":
            i = served.index(day)
            fri = served[i - 1] if i > 0 else str(g.get("anchor_date") or "").replace("-", "")
            if not fri:
                raise SlotError("DAY_FRI: no preceding session and no anchor_date for %s" % day)
            s["DAY_MON"] = (day, "argument")
            s["DAY_FRI"] = (fri, "preceding served session"
                            if i > 0 else "group_config anchor_date (block's first Monday)")
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


TEMPLATE_STORE = os.path.join(HERE, "store", "sop_templates.json")


def templates():
    """The CANONICAL templates, loaded from the store - not a copy written here.

    An earlier version of this file carried its own abridged BLD-1 and AUD-1 and had no BLD-2,
    RFN-1 or RFN-2 at all. Letting those become the source would have quietly replaced the
    canonical templates with simpler ones: the exact A-7 divergence this store exists to end,
    committed by the tool built to end it. The store is extracted VERBATIM from RUN_SOP.md's
    appendix and round-trip proven against it before it is trusted."""
    if not os.path.exists(TEMPLATE_STORE):
        raise SlotError("template store missing: %s" % os.path.relpath(TEMPLATE_STORE, ROOT))
    with open(TEMPLATE_STORE, encoding="utf-8") as f:
        return {t["name"]: t for t in json.load(f)["templates"]}


def _redirect(text, gid, ns):
    """Rewrite canonical per-day OUTPUT paths in an emitted prompt into a rehearsal namespace.

    WHY THIS IS NEEDED AND WHY IT IS NOT AN SOP CHANGE. The BLD-1/RFN-1 bodies hardcode
    `forecasts/g{N}_perday/...` as the write target. For a group that has already run, that
    directory HOLDS THE COMMITTED POSTERIORS - so an agent following its prompt verbatim would
    overwrite the record (NC-4's shape, one layer up, inside the template rather than a
    coordinator). The stored template is left byte-identical; only the EMITTED text is redirected,
    which is why this needs no change-control diff (D10). Anything not matched is left alone, so a
    path this does not recognise stays canonical and is caught by the byte-identity check rather
    than silently half-redirected."""
    n = gid[1:]
    subs = [(f"forecasts/g{n}_perday/", f"forecasts/{ns}/"),
            (f"forecasts/g{n}_refine_perday/", f"forecasts/{ns}/")]
    for a_, b_ in subs:
        text = text.replace(a_, b_)
    banner = (f"*** REHEARSAL RUN - NAMESPACE {ns} ***\n"
              f"This is a MECHANICS SHAKEDOWN, not a scored forecast. The block has already been run\n"
              f"and its actual is committed, so your output is NOT evidence of forecasting skill and\n"
              f"must never be cited as such. Write ONLY into forecasts/{ns}/. Do not write to any\n"
              f"canonical grp*/g{n}_perday path, and do not open {gid}_actual.json, {gid}_exit_states.json\n"
              f"or {gid}_mbo_evidence.json - the point is to exercise the pipeline as the blind sees it.\n"
              f"Report explicitly on any brain play you evaluated, including ones you stood down.\n\n")
    return banner + text


def cmd_emit(a):
    try:
        s = slots(a.gid, a.day, a.spec)
    except SlotError as e:
        print("STOP - slot lookup failed: %s" % e)
        return 1
    try:
        tmap = templates()
    except SlotError as e:
        print("STOP - %s" % e)
        return 1
    if a.template not in tmap:
        print("unknown template %r - have %s" % (a.template, ", ".join(sorted(tmap))))
        return 1
    t = tmap[a.template]["body"]
    ns = getattr(a, "namespace", None)
    if getattr(a, "directive", None):
        s["DIRECTIVE"] = (a.directive, "argument, quoted verbatim per SOP STEP 5.1")
    need = set(re.findall(r"\{([A-Za-z_0-9]+)\}", t))
    missing = sorted(need - set(s))
    if missing:
        # THE STOP RULE: an unresolved slot halts emission. Never blank, never guessed.
        print("STOP - template %s needs slots that did not resolve: %s"
              % (a.template, ", ".join(missing)))
        if "DIRECTIVE" in missing:
            print("       DIRECTIVE is an INPUT, not a lookup - the SOP requires the run directive "
                  "quoted VERBATIM (STEP 5.1). Supply --directive; it is never invented.")
        print("       (supply --day / --spec / --directive, or fix the missing artifact)")
        return 1
    # SUBSTITUTE ONLY KNOWN SLOTS, never str.format. The canonical templates use braces for TWO
    # different things: real slots like {DAY}, and conditional prose the SOP writes inline, e.g.
    # "{IF E, weekend-feeding Friday}: you MUST emit the 9-field handoff_out" and "{IF B}". format()
    # cannot tell them apart and raised KeyError on the first one it met. Targeted replacement also
    # has the better failure mode: an unrecognised brace expression is preserved VERBATIM rather
    # than crashing or being silently swallowed, so the SOP's own conditional instructions survive
    # into the emitted prompt exactly as written.
    out = t
    for k, (v, _src) in s.items():
        out = out.replace("{%s}" % k, str(v))
    if ns:
        out = _redirect(out, a.gid, ns)
    print(out)
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
    arg.directive = None
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
    # only SLOT-shaped braces must be gone; the SOP's inline conditionals ({IF E, ...}) are
    # deliberate prose and are expected to survive verbatim
    leftover = [m for m in re.findall(r"\{([A-Za-z_0-9]+)\}", out)]
    check("a fully-resolved template emits with no SLOT placeholder left",
          rc == 0 and not leftover)
    check("the SOP's inline conditional prose survives verbatim",
          "{IF E, weekend-feeding Friday}" in out or "{IF B}" in out)
    # CAL_FACTS stays AUD-1-only ON PURPOSE, and that is now a DIFFERENT statement than it was at
    # S112. It is the whole-group block quoting every served day's flow_calendar - correct for the
    # auditor, who reads the block, and wrong for a per-day forecaster, who would be handed nine
    # days he does not own. A-13 closed the gap with the RIGHT channel instead: BLD-1 and RFN-1
    # now carry {DAY_CALENDAR}, the per-day block. So this check no longer says "the forecasters
    # have no calendar channel" - they do - it says CAL_FACTS did not leak into them.
    arg2 = _A(); arg2.gid = "g23"; arg2.day = None; arg2.spec = None
    arg2.template = "AUD-1"; arg2.directive = None
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc2 = cmd_emit(arg2)
    check("the auditor prompt carries the roll fact NC-1 got wrong",
          rc2 == 0 and "bcom_roll_day_n 5" in buf.getvalue())
    check("CAL_FACTS stays AUD-1-only - the whole-group block does not leak into a per-day prompt",
          [t for t in templates().values() if "CAL_FACTS" in t["slots"]][0]["name"] == "AUD-1"
          and len([t for t in templates().values() if "CAL_FACTS" in t["slots"]]) == 1)

    # A-13 CLOSED. The structural cause of NC-1 was that a per-day forecaster had no calendar
    # channel of its own, so a false calendar premise typed into a directive met nothing that
    # could contradict it. These checks EXECUTE the emit and read the delivered text - a slot
    # that is generated but never rendered is exactly the failure this item was about.
    for tname in ("BLD-1", "RFN-1"):
        check("A-13: %s declares the DAY_CALENDAR slot" % tname,
              "DAY_CALENDAR" in templates()[tname]["slots"])
    arg3 = _A(); arg3.gid = "g23"; arg3.day = "20260706"; arg3.spec = None
    arg3.template = "BLD-1"; arg3.directive = None
    buf3 = io.StringIO()
    with contextlib.redirect_stdout(buf3):
        rc3 = cmd_emit(arg3)
    emitted = buf3.getvalue()
    check("A-13: the emitted BLIND prompt actually CONTAINS the prior trading session",
          rc3 == 0 and "PRIOR TRADING SESSION:" in emitted)
    check("A-13: and on the Monday after Independence Day observed it names the skipped session, "
          "so the specialist cannot mistake a 3-day gap for a weekend",
          "NOT the previous calendar day" in emitted and "20260703" in emitted)
    check("A-13: no DAY_CALENDAR placeholder survives into the emitted prompt",
          "{DAY_CALENDAR}" not in emitted)

    # PER-DAY CALENDAR (Greg, S112: the agents need the holiday schedule because it changes the
    # trading days). The Monday after the Independence Day observed session is the worked case.
    dc = day_calendar("g23", "20260706")
    check("per-day calendar names the PRIOR TRADING SESSION, not the previous calendar day",
          "PRIOR TRADING SESSION: 20260703" in dc and "NOT the previous calendar day" in dc)
    check("it says how many calendar days back, so a long gap is visible",
          "3 calendar day(s) back" in dc)
    check("it names what was skipped", "20260704 Sat" in dc and "20260705 Sun" in dc)
    dc2 = day_calendar("g23", "20260709")
    check("an ordinary day reports a 1-day gap and no skip note",
          "1 calendar day(s) back" in dc2 and "NOT the previous" not in dc2)
    # a session inheriting FROM a holiday session - reduced tape, previously invisible
    dc3 = day_calendar("g21", "20260526")
    check("a day inheriting from a partial (holiday) session says so",
          "class partial_session" in dc3)

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
    p.add_argument("--day"); p.add_argument("--spec"); p.add_argument("--directive")
    p.add_argument("--namespace", default=None, help="REHEARSAL redirect: rewrite canonical "
                   "forecasts/<gid>_perday/ output paths to forecasts/<namespace>/ in the EMITTED "
                   "text. The stored template is NOT modified, so this is not an SOP change.")
    sub.add_parser("selftest")
    a = ap.parse_args()
    return {"slots": cmd_slots, "calfacts": cmd_calfacts,
            "emit": cmd_emit, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
