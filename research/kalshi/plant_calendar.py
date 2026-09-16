#!/usr/bin/env python3
"""
plant_calendar.py - the plant's clock and work cycle. RULES, not a loaded table.

GREG, S112: "attach the day and time to what aws uses as a clock and we have a 4 year loop program.
I believe the holidays will still track since most of them are based off [rules]" - e.g. "the 4th
Sunday in June" as a shape. And separately: "we'll have to load a 4 year calendar in and it will
follow that. After the last day on the 4th year it will go to day 1 of year 1."

HE IS RIGHT, AND THE MEASUREMENT SAYS IT IS URGENT. flow_calendar.py computes expiry, bidweek and
both roll legs as RULES already - but CME_HOLIDAYS is a HARDCODED DATE TABLE of 16 entries spanning
2025-09-01 to 2027-02-15. That is 194 days of runway from S112. An unattended plant walking forward
hits a calendar cliff in about six months, and the failure mode is the worst kind: every date past
the table simply reads "not a holiday", which is present, boolean, in range and wrong.

THE RULE INVENTORY, and the one exception worth naming up front:
  nth-weekday (6)  MLK 3rd Mon Jan | Presidents 3rd Mon Feb | Memorial LAST Mon May |
                   Labor 1st Mon Sep | Thanksgiving 4th Thu Nov | (+ day-after-Thanksgiving)
  fixed + observed (4)  New Year Jan 1 | Juneteenth Jun 19 | Independence Jul 4 | Christmas Dec 25
                   - each shifting to Fri/Mon when it lands on a weekend
  EASTER-BASED (1) GOOD FRIDAY. This is the exception to "most of them are based off weekday rules"
                   - it is Easter Sunday minus two days, and Easter is a LUNAR computus, not an
                   nth-weekday. A generator that assumes weekday rules alone silently loses one
                   full_closure per year, which is exactly the kind of hole this desk keeps finding.

THE PROOF THAT THE RULES ARE RIGHT: they must reproduce all 16 committed CME_HOLIDAYS entries
exactly - same dates, same names, same classes - before anything downstream trusts them. Same
discipline the decisions store used to earn the right to become the source of truth: generate,
prove it reproduces the committed artifact, then rely on it.

THE 4-YEAR WORK CYCLE. The plant walks trading sessions in order; when it passes the last session
of year 4 it wraps to day 1 of year 1 and increments the CYCLE. The wrap is the valuable part and
not merely a way to avoid running out: re-walking a session on a later cycle with a better brain is
a REPEAT MEASUREMENT of the same day, which is the only way "the point of these runs was to get
better" (Greg, S112) becomes measurable. Every pass records the brain version that walked it, so
cycle 2 against cycle 1 on the same session is a controlled comparison rather than an impression.

USAGE
    python plant_calendar.py holidays 2028          # rule-generated, any year
    python plant_calendar.py verify                 # rules vs the committed table - the proof
    python plant_calendar.py build --years 4        # -> store/plant_calendar.json
    python plant_calendar.py cursor                 # where the plant is, and what is next
    python plant_calendar.py advance --write        # step the cursor, wrapping the cycle
    python plant_calendar.py selftest
"""

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
STORE = os.path.join(HERE, "store")
CAL = os.path.join(STORE, "plant_calendar.json")

sys.path.insert(0, HERE)
import flow_calendar as fc  # noqa: E402

FULL, PARTIAL, EARLY = "full_closure", "partial_session", "early_close"


def _nth_weekday(year, month, weekday, n):
    """n-th `weekday` of month; n = -1 means the LAST one. weekday: Mon=0 .. Sun=6."""
    d = dt.date(year, month, 1)
    if n > 0:
        shift = (weekday - d.weekday()) % 7
        return d + dt.timedelta(days=shift + 7 * (n - 1))
    d = dt.date(year, month + 1, 1) - dt.timedelta(days=1) if month < 12 else dt.date(year, 12, 31)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


def _easter(year):
    """Anonymous Gregorian computus. Good Friday is the one holiday here that is NOT an
    nth-weekday rule, and omitting it loses a full_closure every year."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f, g = (b + 8) // 25, 0
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(year, month, day)


def _observed(d):
    """US observation rule: Saturday -> preceding Friday, Sunday -> following Monday."""
    if d.weekday() == 5:
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + dt.timedelta(days=1)
    return d


def holidays(year):
    """Every CME energy holiday / early close for a year, from rules alone."""
    out = {}

    def put(d, name, cls):
        out[d.isoformat()] = (name, cls)

    put(_observed(dt.date(year, 1, 1)), "New_Years_Day", FULL)
    put(_nth_weekday(year, 1, 0, 3), "MLK_Day", PARTIAL)
    put(_nth_weekday(year, 2, 0, 3), "Presidents_Day", PARTIAL)
    put(_easter(year) - dt.timedelta(days=2), "Good_Friday", FULL)
    put(_nth_weekday(year, 5, 0, -1), "Memorial_Day", PARTIAL)
    jun = dt.date(year, 6, 19)
    put(_observed(jun), "Juneteenth" + ("_observed" if _observed(jun) != jun else ""), PARTIAL)
    jul = dt.date(year, 7, 4)
    put(_observed(jul), "Independence_Day" + ("_observed" if _observed(jul) != jul else ""),
        PARTIAL)
    put(_nth_weekday(year, 9, 0, 1), "Labor_Day", PARTIAL)
    tg = _nth_weekday(year, 11, 3, 4)
    put(tg, "Thanksgiving", PARTIAL)
    put(tg + dt.timedelta(days=1), "Day_After_Thanksgiving", EARLY)
    put(dt.date(year, 12, 24), "Christmas_Eve", EARLY)
    put(_observed(dt.date(year, 12, 25)), "Christmas", FULL)
    return out


def cmd_holidays(a):
    for d, (n, c) in sorted(holidays(a.year).items()):
        print("  %s  %-26s %s" % (d, n, c))
    return 0


def cmd_verify(a):
    """THE PROOF. Every committed CME_HOLIDAYS entry must be reproduced by the rules - same date,
    same name, same class. Until that holds, nothing downstream may rely on the generator."""
    years = sorted({int(d[:4]) for d in fc.CME_HOLIDAYS})
    gen = {}
    for y in years:
        gen.update(holidays(y))
    bad = 0
    for d, (name, cls) in sorted(fc.CME_HOLIDAYS.items()):
        g = gen.get(d)
        if g is None:
            print("  MISSING   %s  committed=%s/%s - the rules do not generate this date"
                  % (d, name, cls))
            bad += 1
        elif g[1] != cls:
            print("  CLASS     %s  committed=%s/%s  generated=%s/%s" % (d, name, cls, g[0], g[1]))
            bad += 1
        elif g[0].split("_observed")[0] != name.split("_observed")[0]:
            print("  NAME      %s  committed=%s  generated=%s" % (d, name, g[0]))
            bad += 1
    # the generator legitimately produces MORE than the table (early closes the table omits),
    # so extras are reported as informational rather than as failures
    span = (min(fc.CME_HOLIDAYS), max(fc.CME_HOLIDAYS))
    extra = [d for d in gen if span[0] <= d <= span[1] and d not in fc.CME_HOLIDAYS]
    print("\n  committed entries: %d | reproduced: %d | mismatches: %d"
          % (len(fc.CME_HOLIDAYS), len(fc.CME_HOLIDAYS) - bad, bad))
    if extra:
        print("  generated but ABSENT from the committed table (%d) - these are real CME dates the "
              "hand-kept table omits, not errors:" % len(extra))
        for d in sorted(extra):
            print("     %s  %s/%s" % (d, gen[d][0], gen[d][1]))
    return 1 if bad else 0


def sessions(start, end):
    """Trading sessions between two dates: weekdays that are not a full closure. A partial session
    still trades and is still a session; a full closure is not."""
    out, d = [], start
    hol = {}
    for y in range(start.year, end.year + 1):
        hol.update(holidays(y))
    while d <= end:
        if d.weekday() < 5:
            h = hol.get(d.isoformat())
            if not h or h[1] != FULL:
                # CAL OFFSET (Greg, S112): "I'm designating whatever year is the first as cal + 0
                # and the numbers are the years after." Every session is addressable as
                # (cal+N, date), so the plant can reason in cycle-relative terms - cal+0 day 1 is
                # where a wrap returns to, whatever the absolute year happens to be.
                off = d.year - start.year
                out.append({"date": d.strftime("%Y%m%d"), "dow": d.strftime("%a"),
                            "cal_offset": off, "cal_label": "cal+%d" % off,
                            "holiday": h[0] if h else None,
                            "session_class": h[1] if h else "normal"})
        d += dt.timedelta(days=1)
    return out


def cmd_build(a):
    start = dt.date.fromisoformat(a.start) if a.start else dt.date(2026, 1, 1)
    end = dt.date(start.year + a.years, start.month, start.day) - dt.timedelta(days=1)
    ss = sessions(start, end)
    doc = {
        "note": ("THE PLANT'S WORK SCHEDULE. Sessions are GENERATED FROM RULES against the real "
                 "clock, never a loaded date table - flow_calendar.CME_HOLIDAYS runs out on "
                 "2027-02-15 and a date past a table reads as 'not a holiday', which is present, "
                 "boolean and wrong. The plant walks these in order; after the last session it "
                 "wraps to index 0 and increments `cycle`. The wrap is the point: re-walking a "
                 "session on a later cycle with a better brain is a REPEAT MEASUREMENT, which is "
                 "what makes 'get better over the runs' measurable rather than an impression."),
        "generated_by": "plant_calendar.py (rules; verified against flow_calendar.CME_HOLIDAYS)",
        "why_materialised_dates_are_safe_here": (
            "These are ALREADY-HAPPENED sessions and the plant RE-WALKS them, so writing the dates "
            "down is exact - the wrap returns to cal+0 day 1, it does not assert that those dates "
            "recur. THE ONE THING THIS TABLE MUST NEVER BE USED FOR is projecting past cal+3: the "
            "calendar does NOT repeat on four years. Memorial Day runs 05-25 / 05-27 / 05-29 / "
            "05-31 across 2026/2030/2034/2038 and Good Friday moves +16 or -12 days, so replaying "
            "cal+0's dates as year five would drift about two days per cycle and would eventually "
            "put a Monday holiday on a day that is not a Monday. To extend the window, RE-RUN the "
            "rules for the new years - never copy a cal offset forward."),
        "span": {"start": start.isoformat(), "end": end.isoformat(), "years": a.years},
        "n_sessions": len(ss),
        "cursor": {"index": 0, "cycle": 1, "brain_version_at_start": None},
        "sessions": ss,
    }
    print("%d sessions, %s .. %s (%d years)" % (len(ss), start, end, a.years))
    from collections import Counter
    c = Counter(s["session_class"] for s in ss)
    for k, v in c.most_common():
        print("   %-16s %d" % (k, v))
    if not a.write:
        print("\ndry run - nothing written. Re-run with --write.")
        return 0
    os.makedirs(STORE, exist_ok=True)
    with open(CAL, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
    print("wrote %s" % os.path.relpath(CAL, ROOT))
    return 0


def _load():
    if not os.path.exists(CAL):
        raise SystemExit("no calendar at %s - run build --write first" % os.path.relpath(CAL, ROOT))
    with open(CAL, encoding="utf-8") as f:
        return json.load(f)


def cmd_cursor(a):
    d = _load()
    cur = d["cursor"]
    ss = d["sessions"]
    i = cur["index"]
    print("cycle %d, index %d of %d" % (cur["cycle"], i, len(ss)))
    print("  current : %s %s  %s  (%s)" % (ss[i]["date"], ss[i]["dow"],
                                            ss[i].get("cal_label", "?"), ss[i]["session_class"]))
    for j in range(i + 1, min(i + 4, len(ss))):
        print("  next    : %s %s  %s  (%s)" % (ss[j]["date"], ss[j]["dow"],
                                                ss[j].get("cal_label", "?"), ss[j]["session_class"]))
    if i + 1 >= len(ss):
        print("  next    : WRAP -> index 0 = cal+0 day 1 (%s), cycle %d"
              % (ss[0]["date"], cur["cycle"] + 1))
    return 0


def cmd_advance(a):
    d = _load()
    cur, ss = d["cursor"], d["sessions"]
    nxt = cur["index"] + 1
    wrapped = nxt >= len(ss)
    if wrapped:
        nxt, cur["cycle"] = 0, cur["cycle"] + 1
    cur["index"] = nxt
    print("advanced to %s (index %d, cycle %d)%s"
          % (ss[nxt]["date"], nxt, cur["cycle"], "  [WRAPPED]" if wrapped else ""))
    if not a.write:
        print("dry run - nothing written. Re-run with --write.")
        return 0
    with open(CAL, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
    return 0


def cmd_selftest(a):
    res = []

    def check(n, ok):
        res.append(ok)
        print("  %-4s | %s" % ("PASS" if ok else "FAIL", n))

    h26 = holidays(2026)
    check("Good Friday 2026 is Easter-derived, not a weekday rule (2026-04-03)",
          h26.get("2026-04-03", ("", ""))[0] == "Good_Friday")
    check("Memorial Day is the LAST Monday in May, not the 4th (2026-05-25)",
          h26.get("2026-05-25", ("", ""))[0] == "Memorial_Day")
    check("Thanksgiving is the 4th Thursday (2026-11-26)",
          h26.get("2026-11-26", ("", ""))[0] == "Thanksgiving")
    check("Independence Day 2026 falls on a Saturday and observes to Friday 07-03",
          h26.get("2026-07-03", ("", ""))[0].startswith("Independence_Day"))
    # 2027: Jul 4 is a Sunday -> observed Monday 07-05. A fixed-date generator gets this wrong.
    h27 = holidays(2027)
    check("Independence Day 2027 falls on a Sunday and observes to Monday 07-05",
          h27.get("2027-07-05", ("", ""))[0].startswith("Independence_Day"))
    check("Easter moves year to year (2026 != 2027 Good Friday)",
          (_easter(2026) - dt.timedelta(days=2)) != (_easter(2027) - dt.timedelta(days=2)))
    check("a full closure is NOT a session; a partial one IS",
          all(s["session_class"] != FULL for s in sessions(dt.date(2026, 1, 1),
                                                           dt.date(2026, 12, 31)))
          and any(s["session_class"] == PARTIAL for s in sessions(dt.date(2026, 1, 1),
                                                                  dt.date(2026, 12, 31))))
    ss = sessions(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    check("no weekend is ever a session", all(s["dow"] not in ("Sat", "Sun") for s in ss))
    print("\n  %d/%d passed" % (sum(res), len(res)))
    return 0 if all(res) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("holidays"); p.add_argument("year", type=int)
    sub.add_parser("verify")
    p = sub.add_parser("build"); p.add_argument("--years", type=int, default=4)
    p.add_argument("--start"); p.add_argument("--write", action="store_true")
    sub.add_parser("cursor")
    p = sub.add_parser("advance"); p.add_argument("--write", action="store_true")
    sub.add_parser("selftest")
    a = ap.parse_args()
    return {"holidays": cmd_holidays, "verify": cmd_verify, "build": cmd_build,
            "cursor": cmd_cursor, "advance": cmd_advance, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
