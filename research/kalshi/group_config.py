"""group_config.py - per-group turnkey config for the NG forecaster walk (S105).
One place: window days (Sunday fold), anchor, two-leg basis + per-day contract, owner map,
EIA/holiday/expiry specials, and the DST transition register. The actual/state/coordinate
builders read this so a new group is a config entry, not new code.

DST (Greg S105): both US clock changes in the data year are marked SPECIAL - they change the
session length and shift the ET curve clock. tz_convert already maps UTC->ET correctly (DST-aware),
so the ACTUAL curve plots at the right wall time; the mark additionally (a) flags the day-class and
(b) tells the 2-hourly reopen grid the day is 23h (spring) or 25h (fall), so the path grid is not
misaligned across the transition.
"""
import os

MULT = 10000.0

# US DST transitions (Sundays). session_hours = the Globex trade-day length across the change.
DST_SPECIAL = {
    "20251102": {"type": "fall_back", "session_hours": 25,
                 "note": "clocks 02:00->01:00 ET; the 01:00 hour repeats; trade-day GAINS an hour; "
                         "ET grid after 02:00 shifts +1h vs a normal day"},
    "20260308": {"type": "spring_forward", "session_hours": 23,
                 "note": "clocks 02:00->03:00 ET; the 02:00 hour does not exist; trade-day LOSES an "
                         "hour; ET grid after 02:00 shifts -1h vs a normal day"},
}

def dst_flag(ymd: str):
    """Return the DST-special record if this day (or its Sunday reopen) crosses a transition, else None."""
    return DST_SPECIAL.get(ymd)


# US federal market holidays / CME NG closures in-window (extend as the walk advances).
HOLIDAYS = {
    # S107 CORRECTION: this entry previously carried eia_shift "20260529" and a note claiming the print
    # shifted Thu->Fri. It does not - the EIA calendar feed has is_eia_print_day TRUE on 20260528 with
    # shifted=false / shift_reason=null. A MONDAY holiday does not move the Thursday gas storage report.
    # This mattered beyond documentation: group_actual.py:63 stamps this record onto the holiday day of
    # the ACTUAL file, so the wrong claim was propagating into a scored artifact. It was a SECOND copy
    # of the same error already fixed in GROUPS["g20"]["eia_thursdays"] - the duplicate is why it
    # survived that fix, and why it is corrected here rather than left as prose.
    "20260525": {"name": "Memorial Day", "cme": "early_close/holiday", "eia_shift": None,
                 "note": "Mon holiday, thin session that DOES trade; the EIA print stays on Thu 05-28 "
                         "(a Monday holiday does not shift it); A owns the reopen and the day"},
    "20260619": {"name": "Juneteenth", "cme": "early_close/holiday", "eia_shift": None,
                 "note": "Fri holiday inside G21; A owns it per the holiday day-class. Verify the CME "
                         "energy session class when G21 is run - Juneteenth is not a full CME closure "
                         "in every year"},
    "20260703": {"name": "Independence Day (observed)", "cme": "early_close/holiday", "eia_shift": None,
                 "note": "July 4 falls Sat in 2026 so the observed holiday is Fri 07-03, the last day "
                         "of G22; A owns it. Verify the early-close vs full-closure class when run"},
}

# Kalshi-underlying roll map (roll = 5 business days before LTD; from FLOW_CALENDAR_NOTES_S98).
LTD = {"NGK26": "20260428", "NGM26": "20260527", "NGN26": "20260626", "NGQ26": "20260729"}
ROLL = {"NGM26->NGN26": "20260520", "NGK26->NGM26": "20260421", "NGN26->NGQ26": "20260722"}


def _dow(ymd):
    import datetime
    return ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[
        datetime.date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8])).weekday()]


def _default_owner(ymd, seam, eia_thursdays, holidays):
    """day-class owner: holiday->A, EIA-print-day->D (from the list, print may shift off Thursday),
    seam->E, Fri->E, Mon->B, else C. EIA ownership follows the explicit list ONLY (a hollow Thursday
    whose print shifted to Friday is core-C; the EIA-Friday is D)."""
    if ymd in holidays:
        return "A"
    if ymd in eia_thursdays:            # the actual print day (Thu normally, Fri after a Mon holiday)
        return "D"
    if ymd == seam:
        return "E"
    dw = _dow(ymd)
    if dw == "Fri":
        return "E"
    if dw == "Mon":
        return "B"
    return "C"


# ---- per-group configs (Sunday fold: the ~2h Sunday reopen folds into the following Monday) ----
GROUPS = {
    "g17": {
        "window": "Sun 2026-04-12 -> Fri 2026-04-24",
        "days": ["20260413","20260414","20260415","20260416","20260417","20260420","20260421","20260422","20260423","20260424"],
        "anchor": 2.653, "anchor_date": "20260410", "anchor_lasthr_dir": -1,
        "mask_after": "20260410",
        "seam": "20260421", "legs": {"pre": "ngk26", "post": "ngm26"},  # May->June
        "eia_thursdays": ["20260416","20260423"],
        "basis": "May/NGK26(996) through 04-20; June/NGM26 from 04-21; seam 04-21 never-traded",
    },
    "g18": {
        "window": "Sun 2026-04-26 -> Fri 2026-05-08",
        "days": ["20260427","20260428","20260429","20260430","20260501","20260504","20260505","20260506","20260507","20260508"],
        "anchor": 2.689, "anchor_date": "20260424", "anchor_lasthr_dir": -1,
        "mask_after": "20260424",
        "seam": None, "legs": {"all": "ngm26"},                        # clean June
        "eia_thursdays": ["20260430","20260507"],
        "basis": "June/NGM26 clean (June roll 05-20 outside); NGK26 expiry 04-28 is off-basis (damped)",
    },
    "g19": {
        "window": "Sun 2026-05-10 -> Fri 2026-05-22",
        "days": ["20260511","20260512","20260513","20260514","20260515","20260518","20260519","20260520","20260521","20260522"],
        "anchor": 2.750, "anchor_date": "20260508", "anchor_lasthr_dir": -1,   # from G18 actual 05-08 close
        "mask_after": "20260508",
        "seam": "20260520", "legs": {"pre": "ngm26", "post": "ngn26"},  # June->July roll 05-20
        "eia_thursdays": ["20260514","20260521"],
        "basis": "June/NGM26 through 05-19; July/NGN26 from 05-20; seam 05-20 never-traded",
    },
    "g20": {
        "window": "Sun 2026-05-24 -> Fri 2026-06-05 (Memorial Day 05-25)",
        "days": ["20260525","20260526","20260527","20260528","20260529","20260601","20260602","20260603","20260604","20260605"],
        "anchor": None, "anchor_date": "20260522", "anchor_lasthr_dir": 1,   # anchor from G19 actual;
        # lasthr_dir derived S107 from the 20260522 NGN26 tape (close 3.034, last hour +1) - the same
        # field and same derivation G17/G18/G19 carry. It was left None here, which silently gave G20's
        # blind one bit less anchor context than G19's had.
        "mask_after": "20260522",
        "seam": None, "legs": {"all": "ngn26"},                        # clean July (roll 06-19 outside)
        # S107 CORRECTION. This was ["20260529","20260604"] on the assumption that Memorial Day shifts
        # the print off Thursday. The EIA calendar feed says otherwise and is authoritative: grp20_state
        # flow_calendar carries is_eia_print_day TRUE on 20260528 with shifted=false, shift_reason=null,
        # and a single release that week at 2026-05-28T10:30 ET. A MONDAY holiday does not move the
        # Thursday gas storage report (only a Thursday holiday does). owner_map derives D's ownership
        # from this list, so the error had D applying the EIA lens to a non-print Friday while the real
        # print day was handled as an ordinary core day. G21/G22/G23 were checked and all MATCH the feed.
        "eia_thursdays": ["20260528","20260604"],
        "holidays": ["20260525"],
        "basis": "July/NGN26 clean; Memorial Day 05-25 holiday (Mon, does NOT shift the print); "
                 "EIA prints Thu 05-28 and Thu 06-04, both on schedule",
    },
    # ---- past G20 (stretch; VERIFY holiday/roll specifics when reached) ----
    "g21": {
        "window": "Sun 2026-06-07 -> Fri 2026-06-19 (Juneteenth 06-19 + July->Aug roll)",
        "days": ["20260608","20260609","20260610","20260611","20260612","20260615","20260616","20260617","20260618","20260619"],
        "anchor": None, "anchor_date": "20260605", "anchor_lasthr_dir": 1,   # from G20 actual; lasthr_dir
        # derived S107 from the 20260605 NGN26 anchor session (close 3.220, last hour +1)
        "mask_after": "20260605",
        # NGN26 LTD 06-26 -> roll 06-19, BUT 06-19 = Juneteenth (holiday); the Aug/NGQ26 underlying
        # effectively begins 06-22 (G22). Treat G21 as clean July/NGN26 with 06-19 a holiday day.
        "seam": None, "legs": {"all": "ngn26"},
        "eia_thursdays": ["20260611","20260618"],
        "holidays": ["20260619"],
        "basis": "July/NGN26; 06-19 Juneteenth holiday; NGN26->NGQ26 roll lands at the 06-19/06-22 boundary (verify)",
    },
    "g22": {
        "window": "Sun 2026-06-21 -> Fri 2026-07-03 (Independence Day observed 07-03)",
        "days": ["20260622","20260623","20260624","20260625","20260626","20260629","20260630","20260701","20260702","20260703"],
        "anchor": None, "anchor_date": "20260619", "anchor_lasthr_dir": -1,   # from G21 actual (leg change
        # NGN26->NGQ26 at this boundary). lasthr_dir derived S107 on the PRIOR leg NGN26 (close 3.198,
        # last hour -1) - the anchor CLOSE comes from G21, so its last hour must be read on G21's leg,
        # not on this group's NGQ26. Reading it on the own-leg would describe a different contract.
        "mask_after": "20260619",
        "seam": None, "legs": {"all": "ngq26"},   # Aug/NGQ26 (Aug roll 07-22 outside)
        "eia_thursdays": ["20260625","20260702"],
        "holidays": ["20260703"],   # July 4 is Sat 2026 -> observed Fri 07-03
        "basis": "Aug/NGQ26; boundary leg change NGN26->NGQ26 at 06-19/06-22 (anchor on the Aug leg); 07-03 Independence Day observed",
    },
    "g23": {
        "window": "Sun 2026-07-05 -> Fri 2026-07-17",
        "days": ["20260706","20260707","20260708","20260709","20260710","20260713","20260714","20260715","20260716","20260717"],
        "anchor": None, "anchor_date": "20260703", "anchor_lasthr_dir": -1,   # from G22 actual; lasthr_dir
        # derived S107 from the 20260703 NGQ26 anchor session (close 3.245, last hour -1)
        "mask_after": "20260703",
        "seam": None, "legs": {"all": "ngq26"},   # Aug/NGQ26 clean (Aug roll 07-22 outside; data ends ~07-20)
        "eia_thursdays": ["20260709","20260716"],
        "basis": "Aug/NGQ26 clean; data year ends ~07-20 so this is the last fully-staged block",
    },
    "g24": {
        "window": "Sun 2026-07-19 -> Fri 2026-07-31",
        "days": ["20260720","20260721","20260722","20260723","20260724",
                 "20260727","20260728","20260729","20260730","20260731"],
        "anchor": 2.916, "anchor_date": "20260717", "anchor_lasthr_dir": None,
        # anchor = G23 actual's last-day CLOSE on 20260717 (2.916), per the build_anchor_block rule
        # that each group's anchor must equal the prior group's realized close - an independent
        # measurement, different file. anchor_lasthr_dir is left None to be DERIVED at stage time
        # from the actual price path rather than asserted here.
        "mask_after": "20260717",
        # ---- THE ROLL, RESEARCHED S114 RATHER THAN ASSUMED --------------------------------
        # Kalshi's KXNATGASD underlying rolls forward 5 BUSINESS DAYS BEFORE LTD (spec verified
        # S99), and the roll day IS the first day on the new leg. NGQ26 LTD is 2026-07-29, so the
        # seam is 2026-07-22.
        # FIVE INDEPENDENT CONFIRMATIONS, because a wrong leg is hole #8 - the block populates,
        # reconciles internally and recomputes coherently off the WRONG contract:
        #  1. The rule reproduces BOTH prior two-leg seams exactly: NGK26 LTD 04-28 -> 04-21 = g17's
        #     recorded seam; NGM26 LTD 05-27 -> 05-20 = g19's.
        #  2. The NG LTD rule (3 business days before the delivery month) reproduces NGU26's
        #     front_expiry of 2026-08-27 as served in our own contract_structure block.
        #  3. NGQ26 tape on S3 ends exactly 20260729.
        #  4. g22 begins 06-22, after the NGN26->NGQ26 roll on 06-19, and is correctly all-NGQ26.
        #  5. g23's own comment above already recorded "Aug roll 07-22", written by an earlier
        #     session with no knowledge of this one.
        # VOLUME IS THE WRONG INSTRUMENT AND WOULD HAVE GIVEN 07-24. Measured, volume LAGS the
        # underlying roll every time - g17 flipped 2 days late (04-23), g19 1 day late (05-21), and
        # G24's volume flips 07-24, exactly the g17 lag off a 07-22 seam. Volume says when traders
        # migrated; the walk forecasts what Kalshi SETTLES against.
        "seam": "20260722", "legs": {"pre": "ngq26", "post": "ngu26"},
        "eia_thursdays": ["20260723","20260730"],
        "basis": "Aug/NGQ26 through 07-21; Sep/NGU26 from 07-22 (Kalshi underlying roll, 5 business "
                 "days before NGQ26's 07-29 LTD). First two-leg block since g19. LAST BLOCK THE "
                 "WALK CAN DO - G25 would be 08-02..08-14 and only 3 of its 10 sessions have "
                 "happened.",
    },
}


def owner_map(gid):
    g = GROUPS[gid]
    hol = g.get("holidays", [])
    return {d: _default_owner(d, g.get("seam"), g.get("eia_thursdays", []), hol) for d in g["days"]}


def leg_for(gid, ymd):
    """which per-contract store this day sits on (two-leg seam aware)."""
    g = GROUPS[gid]
    legs = g["legs"]
    if "all" in legs:
        return f"ng_mbo_{legs['all']}"
    seam = g["seam"]
    return f"ng_mbo_{legs['post'] if ymd >= seam else legs['pre']}"


# Resolved chained anchors (each group's anchor = the prior group's actual last close) persist here so a
# static config entry can leave anchor=None and stage_group fills it. Loaded as an override at import.
_ANCHOR_OVERRIDE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "renders", "ng_refine_s95", "group_anchors.json")
try:
    import json as _json
    if os.path.exists(_ANCHOR_OVERRIDE):
        for _gid, _a in _json.load(open(_ANCHOR_OVERRIDE)).items():
            if _gid in GROUPS and _a is not None:
                GROUPS[_gid]["anchor"] = _a
except Exception:
    pass


def set_anchor(gid, anchor):
    """Persist a resolved anchor to the override file and patch the in-memory config."""
    import json as _json
    os.makedirs(os.path.dirname(_ANCHOR_OVERRIDE), exist_ok=True)
    cur = {}
    if os.path.exists(_ANCHOR_OVERRIDE):
        cur = _json.load(open(_ANCHOR_OVERRIDE))
    cur[gid] = anchor
    _json.dump(cur, open(_ANCHOR_OVERRIDE, "w"), indent=1)
    GROUPS[gid]["anchor"] = anchor


if __name__ == "__main__":
    for gid, g in GROUPS.items():
        om = owner_map(gid)
        print(f"\n{gid}: {g['window']}  anchor={g['anchor']}@{g['anchor_date']}  seam={g.get('seam')}")
        for d in g["days"]:
            marks = []
            if d == g.get("seam"): marks.append("SEAM")
            if d in g.get("eia_thursdays", []): marks.append("EIA")
            if d in g.get("holidays", []): marks.append("HOLIDAY")
            if dst_flag(d): marks.append("DST-" + dst_flag(d)["type"])
            print(f"  {d} {_dow(d)} owner={om[d]} leg={leg_for(gid,d)}  {' '.join(marks)}")
