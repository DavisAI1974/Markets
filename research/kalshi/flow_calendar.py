"""Flow calendar feed (family CAL) for the NG intraday forecaster -- DATA_GATE_S98 feed F.

WHAT THIS IS
------------
An INPUT, not a thesis. Mechanical, scheduled flows that desks trade around --
futures/options expiry clocks, bidweek, the GSCI/BCOM index-roll windows, EIA
release timing (incl. holiday shifts), CME holiday/early-close status -- exposed
per calendar date so the agent can see them. Fully deterministic; ZERO market
data; no blind wall except EIA holiday shifts, which come from EIA's PUBLISHED
schedule, never assumed.

Span: 2025-09-01 .. 2026-12-31. `flow_calendar_asof(date)` returns None outside
the span (missing is explicit, never a default). Extended from 2026-08-31 to
year-end 2026 on 2026-07-21 (STEP-C); the extension is additive -- the only
pre-existing rows that changed are 2026-08-28..2026-08-31, whose EIA
next-release / this-week fields were None-or-empty as a SPAN ARTIFACT (the
next release, Thu 2026-09-03, lay past the old span end; Mon 2026-08-31's
Mon-Sun week contains it) and now carry it.

VERIFIED RULES AND SOURCES (see FLOW_CALENDAR_NOTES_S98.md for the full audit)
------------------------------------------------------------------------------
1. NG FUTURES EXPIRY -- "trading terminates three business days prior to the
   first calendar day of the delivery month" (equivalently: the 3rd-last
   business day of the month before delivery). Sources: NYMEX contract text
   (tkfutures.com/natural_gas.htm mirror, quoted verbatim); EIA table
   definitions (eia.gov/dnav/ng/TblDefs/ng_pri_fut_tbldef2.asp: "Natural gas
   contracts expire three business days prior to the first calendar day of the
   delivery month"). cmegroup.com is unreachable from this environment
   (ECONNRESET on every path) -- named limitation. The rule is additionally
   validated against the repo's Databento `definition`-schema expirations
   (data/contract_structure/NG_instrument_map.json.gz): the derivation
   reproduces ALL 25 listed outright expiries NGZ25..NGZ27 exactly, across
   three separate Thanksgiving-class holiday Novembers.
2. NG OPTIONS EXPIRY -- "trading terminates at the close of business on the
   business day immediately preceding the expiration of the underlying natural
   gas futures contract" (same NYMEX text mirror). Applies to the monthly
   LN/ON options. No repo-internal cross-check exists (the definitions pull
   was futures-parent only) -- named.
3. BIDWEEK -- final 5 business days of each calendar month (per the feed spec).
   Cash-market bidweek follows the NGI/NAESB convention; this feed computes the
   window on the CME energy calendar -- identical over this span -- caveat in
   the notes doc.
4. S&P GSCI ROLL -- 5th through 9th S&P GSCI business days, 20%/day
   (80/20, 60/40, 40/60, 20/80, 0/100). Verified verbatim from the S&P GSCI
   methodology (June 2021 edition mirror; current spglobal.com PDF 403s from
   here -- named). NG is a component with ALL TWELVE contract months
   (G H J K M N Q U V X Z F -- rolls every month); RPDW 3.24% in the 2021
   edition (current 2026 RPDW not retrievable from this environment -- named).
   GSCI business days follow the NYSE calendar ("as determined by the NYSE
   Euronext Holiday & Hours schedule") -- identical to the CME-energy
   closed set over this span (checked date-by-date in the notes doc).
5. BCOM ROLL -- "'Roll Period' means the period of five Business Days,
   beginning with and including the sixth Business Day through and including
   the tenth Business Day of each month", 20%/day (RW array
   {1,1,1,1,1,.80,.60,.40,.20,0}); the "Hedge Roll Period" (where the hedge
   FLOW actually executes) is the FIFTH through NINTH business days --
   overlapping the GSCI window. Verified verbatim from the BCOM methodology
   PDF (assets.bbhub.io). NG is a component (~7.94% 2025 target weight);
   BCOM holds NG delivery months Jan/Mar/May/Jul/Sep/Nov, so NG contract
   ROLL FLOW months are Feb/Apr/Jun/Aug/Oct/Dec (+ the January rebalance).
6. EIA WEEKLY NATURAL GAS STORAGE RELEASE -- Thursdays 10:30 ET, EXCEPT as
   published on the schedule page (ir.eia.gov/ngs/schedule.html, fetched
   2026-07-20; re-fetched 2026-07-21 for the H2-2026 extension). In-span
   exceptions (all six verified from the page):
     Fri 2025-11-14 10:30 ET  (Veterans Day week -- a TUESDAY holiday slips
                               the release a day; the naive Thursday rule
                               would be wrong here)
     Wed 2025-11-26 12:00 ET  (Thanksgiving)
     Mon 2025-12-29 12:00 ET  (Christmas -- slips LATE to Monday, not early)
     Wed 2025-12-31 12:00 ET  (New Year's Day -- pulled a day early)
     Fri 2026-11-13 10:30 ET  (Veterans Day 2026 is a WEDNESDAY -- slips the
                               Thursday release to Friday, same as 2025)
     Wed 2026-11-25 12:00 ET  (Thanksgiving 2026)
   Consequence: the Mon-Sun week of 2025-12-22 has NO release; the week of
   2025-12-29 has TWO. Monday federal holidays do NOT move the release (no
   exception listed for Labor/Columbus/MLK/Presidents/Memorial days; Juneteenth
   2026 falls on a Friday so Thu 2026-06-18 stands). MEASURED NON-SHIFTS for
   the H2-2026 extension: the published page (fetched 2026-07-21) lists NO
   exception for the Christmas-2026 or New-Year-2027 weeks -- Dec 25 2026 and
   Jan 1 2027 fall on FRIDAYS, so the nominal Thursday releases 2026-12-24 and
   2026-12-31 STAND at 10:30 ET (the 2025 shifts happened because those
   holidays fell ON Thursday). Never assumed: read off the schedule page.
7. CME HOLIDAYS / EARLY CLOSES (energy) -- three observed classes:
     full_closure       : no Globex session at all (Christmas, New Year's Day,
                          Good Friday)
     partial_session    : Globex trades a shortened session, NO settlements,
                          NOT a business day (Labor/Thanksgiving/MLK/
                          Presidents/Memorial/Juneteenth/July-4-observed)
     early_close        : full business day WITH settlements, shortened hours
                          (day after Thanksgiving, Christmas Eve)
   Verified against: the repo's own tape (NG_sessions.json trade counts:
   Thanksgiving 14.4k trades = partial; Christmas 174 = evening reopen only),
   the Databento definition expiries (Thanksgiving-class exclusion required to
   reproduce NGZ25/NGZ26/NGZ27), AMP Futures' repost of the CME Christmas 2025
   schedule, and broker mirrors of the CME 2026 MLK/Presidents advisories
   ("prices carried forward from the prior day", i.e. no settlement cycle).
   cmegroup.com itself unreachable -- named. forecast_harness._HOLIDAYS is a
   read-only REFERENCE with different (liquidity-tag) semantics; disagreements
   are REPORTED by --selftest, never edited.

CONVENTIONS
-----------
- front_symbol_calendar on date d = the nearest contract whose expiry >= d
  (on the expiry day itself the expiring contract IS the front; it rolls the
  next calendar day). NOTE: data/contract_structure/NG_structure.json uses
  as-of-prior-close semantics and therefore shows the OLD front for one extra
  session after expiry (its days_to goes to -1); --selftest reports these
  per-instance as a convention offset, not an expiry disagreement.
- days_to_* = business days from date (EXCLUSIVE) to target (INCLUSIVE),
  CME-holiday aware -- the exact convention of
  contract_structure.business_days_between. 0 on the target day; negative if
  the target has passed (days_to_opex = -1 on the futures expiry day).
- Missing/not-applicable is None, never zero. Dates outside the span -> None.

USAGE
-----
    python flow_calendar.py --build       # precompute the span -> the store
    python flow_calendar.py --selftest    # anchors + cross-checks (exit != 0 on failure)
    python flow_calendar.py --asof 2026-02-20

    from flow_calendar import flow_calendar_asof
    row = flow_calendar_asof("2026-02-20")   # dict, or None outside span
"""

from __future__ import annotations

import argparse
import datetime as _dt
import gzip
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
DATA_DIR = os.path.join(_ROOT, "data", "flow_calendar")
STORE_PATH = os.path.join(DATA_DIR, "flow_calendar.json")
STRUCT_PATH = os.path.join(_ROOT, "data", "contract_structure", "NG_structure.json")
INSTMAP_PATH = os.path.join(_ROOT, "data", "contract_structure", "NG_instrument_map.json.gz")
HARNESS_PATH = os.path.join(_HERE, "forecast_harness.py")

SPAN_START = "2025-09-01"
SPAN_END = "2026-12-31"

MONTH_CODE = {1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
              7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z"}
CODE_MONTH = {v: k for k, v in MONTH_CODE.items()}

# ---------------------------------------------------------------------------
# CME energy calendar (business-day engine). Classes:
#   full_closure    -> NOT a business day (no Globex session)
#   partial_session -> NOT a business day (shortened Globex session, no
#                      settlements; validated by tape trade-counts + by the
#                      Databento expiry reproduction for the Thanksgiving class)
#   early_close     -> IS a business day (settlements happen, shortened hours)
# H2-2026 entries (Thanksgiving/Christmas 2026) added for the STEP-C year-end
# extension: same fixed annual CME-energy holiday classes as the verified 2025
# instances (CME site still unreachable from this environment -- named; classes
# carried by the recurring rule the 2025 tape + advisory mirrors verified).
# 2027-01-01 / 2027-01-18 / 2027-02-15 (outside the span) are carried -- the
# same precedent as 2026-09-07 -- so business-day counts from December rows to
# NGG27's expiry (2027-01-27, the front for late-Dec dates) and the expiry
# derivations checked against Databento definitions through Feb-2027 are
# holiday-correct.
# ---------------------------------------------------------------------------
CME_HOLIDAYS = {
    "2025-09-01": ("Labor_Day", "partial_session"),
    "2025-11-27": ("Thanksgiving", "partial_session"),
    "2025-12-25": ("Christmas", "full_closure"),
    "2026-01-01": ("New_Years_Day", "full_closure"),
    "2026-01-19": ("MLK_Day", "partial_session"),
    "2026-02-16": ("Presidents_Day", "partial_session"),
    "2026-04-03": ("Good_Friday", "full_closure"),
    "2026-05-25": ("Memorial_Day", "partial_session"),
    "2026-06-19": ("Juneteenth", "partial_session"),
    "2026-07-03": ("Independence_Day_observed", "partial_session"),
    "2026-09-07": ("Labor_Day", "partial_session"),
    "2026-11-26": ("Thanksgiving", "partial_session"),
    "2026-12-25": ("Christmas", "full_closure"),
    "2027-01-01": ("New_Years_Day", "full_closure"),
    "2027-01-18": ("MLK_Day", "partial_session"),
    "2027-02-15": ("Presidents_Day", "partial_session"),
}
CME_EARLY_CLOSES = {
    "2025-11-28": "day_after_Thanksgiving",
    "2025-12-24": "Christmas_Eve",
    "2026-11-27": "day_after_Thanksgiving",
    "2026-12-24": "Christmas_Eve",
}

# ---------------------------------------------------------------------------
# EIA Weekly Natural Gas Storage Report schedule (ir.eia.gov/ngs/schedule.html,
# fetched 2026-07-20; re-fetched 2026-07-21 -- the H2-2026 rows below are the
# only 2026-dated exceptions the page publishes). Standard: Thursday 10:30 ET.
# Exceptions map the NOMINAL (displaced) Thursday -> (actual release date,
# time ET, reason). ONLY the published exceptions are encoded; everything else
# is the standard rule, which the same page states. The Christmas-2026 /
# New-Year-2027 weeks have NO published exception (both holidays fall on
# Fridays): Thu 2026-12-24 and Thu 2026-12-31 stand.
# ---------------------------------------------------------------------------
EIA_SCHEDULE_EXCEPTIONS = {
    "2025-11-13": ("2025-11-14", "10:30", "Veterans_Day"),
    "2025-11-27": ("2025-11-26", "12:00", "Thanksgiving_Day"),
    "2025-12-25": ("2025-12-29", "12:00", "Christmas_Day"),
    "2026-01-01": ("2025-12-31", "12:00", "New_Years_Day"),
    "2026-11-12": ("2026-11-13", "10:30", "Veterans_Day"),
    "2026-11-26": ("2026-11-25", "12:00", "Thanksgiving_Day"),
}
EIA_STANDARD_TIME = "10:30"

# US Eastern DST boundaries covering the span (second Sunday of March / first
# Sunday of November), used only to stamp the correct UTC offset on release
# datetimes. 2025: DST ends Nov 2. 2026: DST starts Mar 8, ends Nov 1.
_DST_END_2025 = _dt.date(2025, 11, 2)
_DST_START_2026 = _dt.date(2026, 3, 8)
_DST_END_2026 = _dt.date(2026, 11, 1)

# BCOM Table 9 lead future by calendar month for Natural Gas (delivery months
# held: Jan/Mar/May/Jul/Sep/Nov). The lead CHANGES -- i.e. actual NG roll flow
# occurs -- in Feb/Apr/Jun/Aug/Oct/Dec. January's roll period carries the
# annual index REBALANCE instead (all commodities, including NG, re-weight).
BCOM_NG_ROLL_MONTHS = {2, 4, 6, 8, 10, 12}


def _norm(d) -> str:
    if isinstance(d, _dt.date):
        return d.isoformat()
    s = str(d).strip()
    if re.fullmatch(r"\d{8}", s):
        return "%s-%s-%s" % (s[:4], s[4:6], s[6:8])
    return s


def _d(iso) -> _dt.date:
    return _dt.date.fromisoformat(_norm(iso))


def _et_offset(d: _dt.date) -> str:
    """UTC offset string for America/New_York on date d (span-local rule)."""
    if d < _DST_END_2025 or (_DST_START_2026 <= d < _DST_END_2026):
        return "-04:00"
    return "-05:00"


def is_cme_business_day(d: _dt.date) -> bool:
    return d.weekday() < 5 and d.isoformat() not in CME_HOLIDAYS


def bd_between(a, b) -> int:
    """Business days from a (EXCLUSIVE) to b (INCLUSIVE); negative if b < a.
    Same convention as contract_structure.business_days_between."""
    da, db = _d(a), _d(b)
    sign = 1
    if db < da:
        da, db = db, da
        sign = -1
    n, cur = 0, da
    while cur < db:
        cur += _dt.timedelta(days=1)
        if is_cme_business_day(cur):
            n += 1
    return n * sign


def prev_business_day(d) -> _dt.date:
    cur = _d(d) - _dt.timedelta(days=1)
    while not is_cme_business_day(cur):
        cur -= _dt.timedelta(days=1)
    return cur


def ng_expiry(delivery_year: int, delivery_month: int) -> _dt.date:
    """NG futures termination: 3 business days prior to the first calendar day
    of the delivery month (= 3rd-last business day of the prior month)."""
    first = _dt.date(delivery_year, delivery_month, 1)
    cur, count = first, 0
    while True:
        cur -= _dt.timedelta(days=1)
        if is_cme_business_day(cur):
            count += 1
            if count == 3:
                return cur


def ng_symbol(delivery_year: int, delivery_month: int) -> str:
    return "NG%s%02d" % (MONTH_CODE[delivery_month], delivery_year % 100)


def calendar_front(d: _dt.date) -> tuple[str, _dt.date]:
    """Nearest contract whose expiry >= d (front THROUGH its expiry day)."""
    y, m = d.year, d.month
    for _ in range(4):
        exp = ng_expiry(y, m)
        if exp >= d:
            return ng_symbol(y, m), exp
        m += 1
        if m > 12:
            m, y = 1, y + 1
    raise RuntimeError("calendar_front walked off the rails for %s" % d)


def month_business_days(year: int, month: int) -> list[_dt.date]:
    out, cur = [], _dt.date(year, month, 1)
    while cur.month == month:
        if is_cme_business_day(cur):
            out.append(cur)
        cur += _dt.timedelta(days=1)
    return out


# ---------------------------------------------------------------------------
# EIA release table for the span
# ---------------------------------------------------------------------------

def build_eia_releases() -> list[dict]:
    """One row per release in the span: nominal Thursday -> actual date/time.
    for_week_ending = nominal Thursday - 6 days (the gas week ends Friday);
    the shifted releases keep their nominal week, so the Mon 2025-12-29
    release correctly covers week ending 2025-12-19."""
    rows = []
    cur = _d(SPAN_START)
    while cur.weekday() != 3:          # first Thursday in span
        cur += _dt.timedelta(days=1)
    end = _d(SPAN_END)
    while cur <= end:
        nominal = cur.isoformat()
        exc = EIA_SCHEDULE_EXCEPTIONS.get(nominal)
        if exc:
            date, time_et, reason = exc
        else:
            date, time_et, reason = nominal, EIA_STANDARD_TIME, None
        rows.append({
            "release_date": date,
            "release_time_et": time_et,
            "datetime_et": "%sT%s:00%s" % (date, time_et, _et_offset(_d(date))),
            "for_week_ending": (cur - _dt.timedelta(days=6)).isoformat(),
            "nominal_thursday": nominal,
            "shifted": exc is not None,
            "shift_reason": reason,
            "source": "eia_schedule_page" if exc else "eia_standard_rule",
        })
        cur += _dt.timedelta(days=7)
    rows.sort(key=lambda r: r["release_date"])
    return rows


# ---------------------------------------------------------------------------
# Per-date row
# ---------------------------------------------------------------------------

def _row_for(d: _dt.date, eia_rows: list[dict]) -> dict:
    iso = d.isoformat()
    hol = CME_HOLIDAYS.get(iso)
    early = CME_EARLY_CLOSES.get(iso)
    bd = is_cme_business_day(d)

    front_sym, fut_exp = calendar_front(d)
    opex = prev_business_day(fut_exp)

    mbds = month_business_days(d.year, d.month)
    bdom = (mbds.index(d) + 1) if d in mbds else None
    last5 = mbds[-5:]
    in_bw = d in last5
    nxt_m = d.month % 12 + 1
    nxt_y = d.year + (1 if d.month == 12 else 0)

    in_gsci = bdom is not None and 5 <= bdom <= 9
    in_bcom = bdom is not None and 6 <= bdom <= 10
    in_bcom_hedge = bdom is not None and 5 <= bdom <= 9

    # EIA: releases in this date's Mon-Sun week; next release on/after date
    monday = d - _dt.timedelta(days=d.weekday())
    sunday = monday + _dt.timedelta(days=6)
    week = [r for r in eia_rows if monday <= _d(r["release_date"]) <= sunday]
    future = [r for r in eia_rows if _d(r["release_date"]) >= d]
    nxt = future[0] if future else None

    return {
        "date": iso,
        "is_cme_business_day": bd,
        "cme_holiday": hol is not None,
        "cme_holiday_name": hol[0] if hol else (early if early else None),
        "cme_session_class": hol[1] if hol else ("early_close" if early else None),
        "cme_early_close": early is not None,

        "front_symbol_calendar": front_sym,
        "futures_expiry_date": fut_exp.isoformat(),
        "days_to_futures_expiry": bd_between(d, fut_exp),
        "is_expiry_day": d == fut_exp,
        "options_expiry_date": opex.isoformat(),
        "days_to_opex": bd_between(d, opex),
        "is_opex_day": d == opex,

        "in_bidweek": in_bw,
        "bidweek_day_n": (last5.index(d) + 1) if in_bw else None,
        "bidweek_delivery_month": "%04d-%02d" % (nxt_y, nxt_m) if in_bw else None,

        "business_day_of_month": bdom,
        "in_gsci_roll": in_gsci,
        "gsci_roll_day_n": (bdom - 4) if in_gsci else None,
        "gsci_ng_roll_this_month": True,   # GSCI NG holds all 12 delivery months
        "in_bcom_roll": in_bcom,
        "bcom_roll_day_n": (bdom - 5) if in_bcom else None,
        "in_bcom_hedge_roll": in_bcom_hedge,
        "bcom_ng_roll_this_month": d.month in BCOM_NG_ROLL_MONTHS,
        "bcom_january_rebalance": d.month == 1,

        "eia_storage_release_datetime_et": week[0]["datetime_et"] if week else None,
        "eia_releases_this_week": [
            {"datetime_et": r["datetime_et"], "for_week_ending": r["for_week_ending"],
             "shifted": r["shifted"], "shift_reason": r["shift_reason"]}
            for r in week],
        "is_eia_print_day": any(r["release_date"] == iso for r in eia_rows),
        "next_eia_release_datetime_et": nxt["datetime_et"] if nxt else None,
        "days_to_next_eia_release": (_d(nxt["release_date"]) - d).days if nxt else None,
    }


def build() -> dict:
    eia_rows = build_eia_releases()
    days, cur, end = {}, _d(SPAN_START), _d(SPAN_END)
    while cur <= end:
        days[cur.isoformat()] = _row_for(cur, eia_rows)
        cur += _dt.timedelta(days=1)
    store = {
        "meta": {
            "feed": "flow_calendar", "family": "CAL",
            "span": [SPAN_START, SPAN_END],
            "built_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_days": len(days),
            "n_eia_releases": len(eia_rows),
            "sources": {
                "ng_futures_expiry_rule": "NYMEX contract text (tkfutures.com mirror) + EIA "
                    "ng_pri_fut_tbldef2.asp; validated 25/25 vs Databento definition expirations "
                    "(NG_instrument_map.json.gz)",
                "ng_options_expiry_rule": "NYMEX contract text mirror: business day immediately "
                    "preceding the underlying futures termination",
                "gsci_roll": "S&P GSCI methodology (Jun-2021 edition mirror): 5th-9th S&P GSCI "
                    "business days, 20%/day; NG all 12 contract months",
                "bcom_roll": "BCOM methodology (assets.bbhub.io): Roll Period 6th-10th business "
                    "days 20%/day; Hedge Roll Period 5th-9th; NG lead months Table 9",
                "eia_schedule": "ir.eia.gov/ngs/schedule.html (fetched 2026-07-20, re-fetched "
                    "2026-07-21): Thursday 10:30 ET standard + 6 in-span published exceptions; "
                    "Christmas-2026/New-Year-2027 weeks publish NO exception (Friday holidays), "
                    "nominal Thursdays stand",
                "cme_calendar": "CME site unreachable (ECONNRESET); classes verified via repo "
                    "tape (NG_sessions.json), Databento expiry reproduction, AMP Futures / "
                    "broker reposts of CME advisories",
            },
        },
        "eia_releases": eia_rows,
        "days": days,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STORE_PATH, "w", encoding="utf-8") as fh:
        json.dump(store, fh, indent=1, sort_keys=True)
    return store


# ---------------------------------------------------------------------------
# asof
# ---------------------------------------------------------------------------

_CACHE: dict | None = None


def flow_calendar_asof(date) -> dict | None:
    """Flow-calendar state for a calendar date. None outside the span."""
    global _CACHE
    iso = _norm(date)
    if iso < SPAN_START or iso > SPAN_END:
        return None
    if _CACHE is None:
        if os.path.exists(STORE_PATH):
            with open(STORE_PATH, encoding="utf-8") as fh:
                _CACHE = json.load(fh)
        else:                       # deterministic feed: computing == reading
            _CACHE = build()
    return _CACHE["days"].get(iso)


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------

_HOLIDAY_ENTRY_RE = re.compile(
    r'"(\d{4}-\d{2}-\d{2})"\s*:\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)')


def _load_harness_holidays() -> dict:
    """Regex-parse forecast_harness._HOLIDAYS (read-only; no import, no exec)."""
    try:
        src = open(HARNESS_PATH, encoding="utf-8").read()
        m = re.search(r"_HOLIDAYS\s*=\s*\{", src)
        if not m:
            return {}
        i = m.end() - 1
        depth, j = 0, i
        while j < len(src):
            if src[j] == "{":
                depth += 1
            elif src[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        return {d: (name, effect)
                for d, name, effect in _HOLIDAY_ENTRY_RE.findall(src[i:j + 1])}
    except Exception as e:
        print("  (could not parse forecast_harness._HOLIDAYS: %s)" % e)
        return {}


def selftest() -> int:
    ok = True

    def check(name, cond):
        nonlocal ok
        print("  [%s] %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            ok = False

    print("flow_calendar selftest")
    store = build()
    days = store["days"]
    eia_rows = store["eia_releases"]

    # --- span / shape ---
    check("span has 487 rows (2025-09-01..2026-12-31)", len(days) == 487)
    check("asof outside span (2025-08-31) is None", flow_calendar_asof("2025-08-31") is None)
    check("asof outside span (2027-01-01) is None", flow_calendar_asof("2027-01-01") is None)
    check("2026-09-01 now IN span (year-end extension)",
          flow_calendar_asof("2026-09-01") is not None)

    # --- futures expiry anchors ---
    check("NGG26 expiry == 2026-01-28 (session anchor)",
          ng_expiry(2026, 2).isoformat() == "2026-01-28")
    ngh26 = ng_expiry(2026, 3).isoformat()
    print("  derived NGH26 (Mar-2026) expiry = %s  <- the G13 squeeze-test expiry; "
          "matches the S97 handoff's 'Feb 25 2026 expiry'" % ngh26)
    check("NGH26 expiry == 2026-02-25", ngh26 == "2026-02-25")
    # year-end extension expiries (holiday-aware; NGZ26 would be 2026-11-26 = Thanksgiving
    # under a naive 3rd-last-weekday rule -- the holiday table is load-bearing here)
    check("NGZ26 expiry == 2026-11-25 (Thanksgiving-aware)",
          ng_expiry(2026, 12).isoformat() == "2026-11-25")
    check("NGF27 expiry == 2026-12-29", ng_expiry(2027, 1).isoformat() == "2026-12-29")
    check("NGG27 expiry == 2027-01-27 (front for late-Dec rows)",
          ng_expiry(2027, 2).isoformat() == "2027-01-27")
    check("2026-11-25 is NGZ26 expiry day AND an EIA print day (Thanksgiving-eve pile-up)",
          days["2026-11-25"]["is_expiry_day"] and days["2026-11-25"]["is_eia_print_day"])

    # --- cross-check EVERY derived expiry vs Databento definitions ---
    # The engine's holiday table covers the span + carried dates through
    # Presidents Day 2027; contracts whose TERMINAL WINDOW falls beyond that
    # cannot be derived holiday-correctly here -- for those the comparison is REPORTED
    # per instance (definition authoritative), with the mechanical signature
    # check that a missing future holiday always pushes the derived date LATER.
    COVERAGE_END = "2027-02-28"   # holiday table now carried through Presidents Day 2027
    n_agree = n_in = 0
    in_cov_dis, beyond_dis, bad_signature = [], [], []
    if os.path.exists(INSTMAP_PATH):
        exp_map = json.load(gzip.open(INSTMAP_PATH, "rt"))["expiration"]
        pat = re.compile(r"^NG([FGHJKMNQUVXZ])(\d{2})$")
        for sym in sorted(k for k in exp_map if pat.match(k)):
            mth, yy = pat.match(sym).groups()
            dy, dm = 2000 + int(yy), CODE_MONTH[mth]
            derived = ng_expiry(dy, dm).isoformat()
            definition = exp_map[sym][:10]
            in_cov = definition <= COVERAGE_END
            n_in += in_cov
            if derived == definition:
                n_agree += 1
            elif in_cov:
                in_cov_dis.append((sym, derived, definition))
                print("  DISAGREEMENT (in-coverage) %s: derived %s vs definition %s "
                      "(definition wins)" % (sym, derived, definition))
            else:
                beyond_dis.append((sym, derived, definition))
                if not definition < derived:
                    bad_signature.append(sym)
                print("  beyond-coverage %s: derived %s vs definition %s -- the engine's "
                      "holiday table ends 2027-02; the missing future holiday (Thanksgiving/"
                      "Memorial/Good-Friday class) is the cause; definition is authoritative"
                      % (sym, derived, definition))
        print("  expiry cross-check vs Databento definitions: %d/%d agree overall; "
              "in-coverage (expiry <= %s): %d contracts, %d disagree; beyond-coverage "
              "disagreements: %d (all reported above)"
              % (n_agree, n_agree + len(in_cov_dis) + len(beyond_dis), COVERAGE_END,
                 n_in, len(in_cov_dis), len(beyond_dis)))
        check("all in-coverage definition expiries reproduced (span contracts)",
              not in_cov_dis)
        check("every beyond-coverage disagreement has the missing-holiday signature "
              "(definition EARLIER than derived)", not bad_signature)
        for sym in ("NGV25", "NGX25"):
            if sym not in exp_map:
                mth = sym[2]
                print("  NAMED GAP: %s expiry (%s) is derivation-only -- instrument map "
                      "starts NGZ25, no definition cross-check available"
                      % (sym, ng_expiry(2025, CODE_MONTH[mth]).isoformat()))
    else:
        print("  NAMED GAP: %s absent -- definition cross-check skipped" % INSTMAP_PATH)

    # --- per-date front vs the contract_structure store ---
    if os.path.exists(STRUCT_PATH):
        struct = json.load(open(STRUCT_PATH, encoding="utf-8"))
        n_same = 0
        offsets = []
        expiry_mismatch = []
        for k in sorted(struct):
            row = struct[k]
            s_sym, s_exp = row.get("calendar_front_symbol"), row.get("calendar_front_expiry")
            mine = days.get(k)
            if not (s_sym and mine):
                continue
            if mine["front_symbol_calendar"] == s_sym:
                n_same += 1
                if s_exp and mine["futures_expiry_date"] != s_exp:
                    expiry_mismatch.append((k, mine["futures_expiry_date"], s_exp))
            else:
                offsets.append((k, mine["front_symbol_calendar"], s_sym,
                                row.get("days_to_calendar_front_expiry")))
        print("  front-symbol vs NG_structure.json: %d/%d dates agree"
              % (n_same, n_same + len(offsets)))
        for k, m, s, dte in offsets:
            print("    convention offset %s: this feed %s vs store %s (store dte=%s; the store "
                  "keys state as-of the PRIOR close, so it shows the old front for one session "
                  "after expiry -- reported, not an expiry disagreement)" % (k, m, s, dte))
        check("expiry VALUES never disagree with the store where symbols agree",
              not expiry_mismatch)
        check("front offsets only on the store's post-expiry (dte<0) rows",
              all(dte is not None and dte < 0 for _, _, _, dte in offsets))
        # the exact late-Feb assertion asked for by the task:
        feb = [k for k in struct if k.startswith("2026-02-2")
               and struct[k].get("calendar_front_symbol") == "NGH26"]
        check("late-Feb store rows carry NGH26 expiry 2026-02-25 == derived",
              bool(feb) and all(struct[k]["calendar_front_expiry"] == ngh26 for k in feb))
    else:
        print("  NAMED GAP: %s absent -- store cross-check skipped" % STRUCT_PATH)

    # --- options expiry ---
    r = days["2026-01-27"]
    check("opex(NGG26) = 2026-01-27, business day before futures expiry",
          r["is_opex_day"] and r["options_expiry_date"] == "2026-01-27"
          and r["days_to_futures_expiry"] == 1)
    check("opex(NGH26) = 2026-02-24", days["2026-02-24"]["is_opex_day"])
    check("days_to_opex = -1 on the futures expiry day",
          days["2026-01-28"]["days_to_opex"] == -1 and days["2026-01-28"]["is_expiry_day"])

    # --- EIA releases ---
    dates_of = {r["release_date"]: r for r in eia_rows}
    check("70 releases in span", len(eia_rows) == 70)
    tg = dates_of.get("2025-11-26")
    check("Thanksgiving-week release = Wed 2025-11-26 12:00 ET (published schedule)",
          tg is not None and tg["release_time_et"] == "12:00"
          and tg["shift_reason"] == "Thanksgiving_Day")
    check("Veterans-week release = Fri 2025-11-14 10:30 ET",
          "2025-11-14" in dates_of and dates_of["2025-11-14"]["release_time_et"] == "10:30")
    check("Christmas-week release = Mon 2025-12-29 12:00 ET", "2025-12-29" in dates_of)
    check("New-Years-week release = Wed 2025-12-31 12:00 ET", "2025-12-31" in dates_of)
    check("no release on displaced Thursdays",
          all(x not in dates_of for x in ("2025-11-13", "2025-11-27", "2025-12-25", "2026-01-01")))
    check("week of 2025-12-22 has NO release",
          days["2025-12-23"]["eia_storage_release_datetime_et"] is None
          and days["2025-12-23"]["eia_releases_this_week"] == [])
    check("week of 2025-12-29 has TWO releases",
          len(days["2025-12-30"]["eia_releases_this_week"]) == 2)
    check("Dec-29 release covers week ending 2025-12-19 (nominal-week pairing)",
          dates_of["2025-12-29"]["for_week_ending"] == "2025-12-19")
    check("Juneteenth 2026 is a Friday -> Thu 2026-06-18 release stands",
          "2026-06-18" in dates_of and not dates_of["2026-06-18"]["shifted"])
    check("is_eia_print_day set on 2025-11-26", days["2025-11-26"]["is_eia_print_day"])
    # H2-2026 extension (published schedule, re-fetched 2026-07-21)
    check("Veterans-week 2026 release = Fri 2026-11-13 10:30 ET (Wednesday holiday slips it)",
          "2026-11-13" in dates_of and dates_of["2026-11-13"]["release_time_et"] == "10:30"
          and dates_of["2026-11-13"]["shift_reason"] == "Veterans_Day"
          and "2026-11-12" not in dates_of)
    check("Thanksgiving-week 2026 release = Wed 2026-11-25 12:00 ET",
          "2026-11-25" in dates_of and dates_of["2026-11-25"]["release_time_et"] == "12:00"
          and "2026-11-26" not in dates_of)
    check("Christmas-2026 week: Thu 2026-12-24 release STANDS unshifted at 10:30 "
          "(Friday holiday; no published exception)",
          "2026-12-24" in dates_of and not dates_of["2026-12-24"]["shifted"]
          and dates_of["2026-12-24"]["release_time_et"] == "10:30")
    check("New-Year-2027 week: Thu 2026-12-31 release STANDS unshifted",
          "2026-12-31" in dates_of and not dates_of["2026-12-31"]["shifted"])
    check("2026-08-31 span-artifact corrected: its Mon-Sun week now sees Thu 2026-09-03",
          days["2026-08-31"]["eia_storage_release_datetime_et"] is not None
          and days["2026-08-31"]["eia_storage_release_datetime_et"].startswith("2026-09-03"))

    # --- bidweek ---
    jan_bw = sorted(k for k, v in days.items() if v["in_bidweek"] and k.startswith("2026-01"))
    check("Jan-2026 bidweek = Jan 26..30",
          jan_bw == ["2026-01-26", "2026-01-27", "2026-01-28", "2026-01-29", "2026-01-30"])
    feb_bw = sorted(k for k, v in days.items() if v["in_bidweek"] and k.startswith("2026-02"))
    check("Feb-2026 bidweek = Feb 23..27 (G13 carries bidweek + opex + expiry)",
          feb_bw == ["2026-02-23", "2026-02-24", "2026-02-25", "2026-02-26", "2026-02-27"])
    nov_bw = sorted(k for k, v in days.items() if v["in_bidweek"] and k.startswith("2025-11"))
    check("Nov-2025 bidweek skips Thanksgiving (21,24,25,26,28)",
          nov_bw == ["2025-11-21", "2025-11-24", "2025-11-25", "2025-11-26", "2025-11-28"])
    check("bidweek delivery month tags the NEXT month",
          days["2026-02-25"]["bidweek_delivery_month"] == "2026-03")
    nov26_bw = sorted(k for k, v in days.items() if v["in_bidweek"] and k.startswith("2026-11"))
    check("Nov-2026 bidweek = 23,24,25,27,30 (skips Thanksgiving; 27th is an early-close "
          "BUSINESS day)",
          nov26_bw == ["2026-11-23", "2026-11-24", "2026-11-25", "2026-11-27", "2026-11-30"])
    dec26_bw = sorted(k for k, v in days.items() if v["in_bidweek"] and k.startswith("2026-12"))
    check("Dec-2026 bidweek = 24,28,29,30,31 (skips the Christmas closure)",
          dec26_bw == ["2026-12-24", "2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31"])

    # --- index roll windows ---
    gsci_feb = sorted(k for k, v in days.items() if v["in_gsci_roll"] and k.startswith("2026-02"))
    check("GSCI Feb-2026 window = Feb 6..12 (BD5-9)",
          gsci_feb == ["2026-02-06", "2026-02-09", "2026-02-10", "2026-02-11", "2026-02-12"])
    bcom_feb = sorted(k for k, v in days.items() if v["in_bcom_roll"] and k.startswith("2026-02"))
    check("BCOM Feb-2026 window = Feb 9..13 (BD6-10)",
          bcom_feb == ["2026-02-09", "2026-02-10", "2026-02-11", "2026-02-12", "2026-02-13"])
    gsci_jul = sorted(k for k, v in days.items() if v["in_gsci_roll"] and k.startswith("2026-07"))
    check("GSCI Jul-2026 window = Jul 8..14 (Jul 3 observed holiday excluded)",
          gsci_jul == ["2026-07-08", "2026-07-09", "2026-07-10", "2026-07-13", "2026-07-14"])
    check("BCOM NG roll-flow months are Feb/Apr/Jun/Aug/Oct/Dec",
          days["2026-02-10"]["bcom_ng_roll_this_month"]
          and not days["2026-03-10"]["bcom_ng_roll_this_month"]
          and days["2025-10-10"]["bcom_ng_roll_this_month"])
    check("January carries the BCOM rebalance flag", days["2026-01-12"]["bcom_january_rebalance"])
    gsci_dec26 = sorted(k for k, v in days.items() if v["in_gsci_roll"] and k.startswith("2026-12"))
    check("GSCI Dec-2026 window = Dec 7..11 (BD5-9)",
          gsci_dec26 == ["2026-12-07", "2026-12-08", "2026-12-09", "2026-12-10", "2026-12-11"])
    check("Dec-2026 is a BCOM NG roll-flow month", days["2026-12-09"]["bcom_ng_roll_this_month"])

    # --- CME calendar ---
    check("Christmas 2026 closed / Christmas Eve 2026 early close / Thanksgiving 2026 partial",
          days["2026-12-25"]["cme_session_class"] == "full_closure"
          and days["2026-12-24"]["cme_early_close"] and days["2026-12-24"]["is_cme_business_day"]
          and days["2026-11-26"]["cme_session_class"] == "partial_session"
          and not days["2026-11-26"]["is_cme_business_day"])
    check("Christmas closed / Christmas Eve early close",
          days["2025-12-25"]["cme_holiday"]
          and days["2025-12-25"]["cme_session_class"] == "full_closure"
          and days["2025-12-24"]["cme_early_close"]
          and days["2025-12-24"]["is_cme_business_day"])
    check("Thanksgiving partial session, NOT a business day",
          days["2025-11-27"]["cme_session_class"] == "partial_session"
          and not days["2025-11-27"]["is_cme_business_day"])
    check("Veterans Day 2025 is a NORMAL business day (CME open)",
          days["2025-11-11"]["is_cme_business_day"] and not days["2025-11-11"]["cme_holiday"])

    # --- forecast_harness._HOLIDAYS comparison (report-only, read-only) ---
    print("  forecast_harness._HOLIDAYS comparison (REFERENCE dict, different semantics -- "
          "its tags describe session LIQUIDITY; this feed's classes describe business-day/"
          "settlement status; reported, never edited):")
    hd = _load_harness_holidays()
    for iso in sorted(hd):
        if not (SPAN_START <= iso <= SPAN_END):
            continue
        name, effect = hd[iso]
        mine = days[iso]
        cls = mine["cme_session_class"] or ("business_day" if mine["is_cme_business_day"] else "?")
        agree = (
            (effect == "closed" and cls in ("full_closure", "partial_session"))
            or (effect == "early_close" and cls in ("early_close", "partial_session"))
            or (effect == "thin" and cls in ("partial_session", "business_day")))
        tag = "consistent" if agree else "DISAGREES"
        detail = ""
        if effect == "closed" and cls == "partial_session":
            detail = " (dict says closed; Globex energy trades a partial no-settlement " \
                     "session -- the S96 Thanksgiving correction generalizes to this date)"
        if effect == "early_close" and cls == "partial_session":
            detail = " (dict says early_close; CME treats it as a holiday: partial session, " \
                     "no settlements, NOT a business day for expiry/roll counting)"
        if effect == "thin" and cls == "partial_session":
            detail = " (liquidity tag vs holiday class: same day, two lenses)"
        print("    %s %s: dict=%s  feed=%s  -> %s%s" % (iso, name, effect, cls, tag, detail))
    if hd and not any(k < "2025-10-13" for k in hd):
        print("    NOTE: the dict carries nothing before 2025-10-13; this feed's span starts "
              "2025-09-01 (Labor Day 2025 is in-span here, absent there -- a coverage note, "
              "not a disagreement).")

    # --- store written ---
    check("store written with 487 rows + 70 releases",
          os.path.exists(STORE_PATH) and len(days) == 487 and len(eia_rows) == 70)

    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Flow calendar feed (DATA_GATE_S98 feed F)")
    p.add_argument("--build", action="store_true", help="precompute the span to the store")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--asof", metavar="DATE", help="print the row for a date")
    a = p.parse_args(argv)
    if a.build:
        store = build()
        print("built %d days, %d EIA releases -> %s"
              % (store["meta"]["n_days"], store["meta"]["n_eia_releases"], STORE_PATH))
    if a.selftest:
        return selftest()
    if a.asof:
        row = flow_calendar_asof(a.asof)
        print(json.dumps(row, indent=1, sort_keys=True) if row else
              "None  (outside span %s..%s)" % (SPAN_START, SPAN_END))
    if not any([a.build, a.selftest, a.asof]):
        p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
