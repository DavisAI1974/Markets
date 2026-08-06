"""
cash_basis.py - FEED G (family DEL): Henry Hub CASH vs front-futures-settle basis (S98 data gate).

WHY THIS EXISTS
---------------
Cash leads futures in delivery stress, and the walk had zero physical-market visibility. In G11 the
expiring February contract ran 3.0 -> 5.4 into delivery (NGG26 final settle 7.460) while the
forecaster watched March. The physical market called it FIRST and LOUDER: EIA's Henry Hub daily spot
went 3.06 (Jan 16) -> 4.00 -> 4.96 -> 8.42 (Jan 22) -> 30.72 (Jan 23) -> 25.01 -> 17.19 -> 9.34 ->
7.18 (Jan 30). The cash-minus-front basis blew from -0.05 to +25.37 and collapsed into expiry. This
feed puts that series - at its HONEST publication lag - in front of the agent. It does not gate,
score or recommend; the agent decides what it means.

THE MEASURED PUBLICATION MECHANICS (the load-bearing finding, investigated 2026-07-20)
--------------------------------------------------------------------------------------
The naive assumption "EIA publishes daily HH spot with a short (D-1) lag" is WRONG. The series is
published in WEEKLY BATCHES, and the vehicle CHANGED mid-walk:

ERA 1 (gas days through 2026-01-21): the Natural Gas Weekly Update (NGWU) released weekly, normally
  Thursday, carrying daily spot through the prior Wednesday (release-1). The release-date list is
  MEASURED from EIA's own archive index (eia.gov/naturalgas/weekly/includes/archive.php):
  Sep 4/11/18/25, Oct 2/9/16/23/30, Nov 6/13/20, Dec 4/11/18 (2025), Jan 8/15/22 (2026).
  HOLIDAY SKIPS ARE REAL AND LARGE: no issue existed for Thanksgiving week (would-be Nov 27), nor
  for the two year-end weeks (would-be Dec 25 and Jan 1). Each issue carries ONE Thu->Wed week
  (verified on the archived Dec 4 issue), so skipped weeks' gas days never appeared in any issue;
  their first measured publication event is the NEXT release. Consequence: gas days Dec 18-24 and
  Dec 25-31 were not knowable until Jan 8+1 - a 15-21 day blind stretch across the New Year that a
  naive T+1 rule would have leaked.
  The Jan 22, 2026 issue was the FINAL NGWU ("replaced by the WNGSR Supplement launching Jan 29").

ERA 2 (gas days from 2026-01-22): the WNGSR Supplement launched Thursday 2026-01-29, "published
  every Thursday afternoon". The DNAV history page today stamps its own weekly release (observed
  2026-07-20: "Release Date: 7/15/2026, Next Release Date: 7/22/2026" - a Wednesday - with data
  through Monday 7/13, i.e. release-2). Wayback snapshots are unreachable from this environment, so
  per-issue winter release days for Era 2 cannot be directly measured; the model takes the
  CONSERVATIVE (later-knowable) weekly grid consistent with both measured anchors: release = first
  THURSDAY R with R >= gas_day + 2 (and R >= 2026-01-29), data-through R-2. The July-measured
  Wednesday stamp implies live-forward values may become knowable ~1-2 days EARLIER than this model
  claims - conservative, never leaky.

KNOWABILITY RULE (the blind wall): a spot for gas day T joins decision state from
  knowable_from = release_date + 1 calendar day
(release hour vs decision hour is unmeasured for the walk - NGWU/supplement released in the
afternoon, mid-session - so the day-after rule is airtight). Minimum lag anywhere in the store is
gas_day + 2; the maximum in the walked winter is gas_day + 22 (2025-12-18, published 2026-01-08).

VINTAGE / REVISION (measured, not assumed)
------------------------------------------
The as-first-printed values differ from today's DNAV vintage at cent level. All 7 days checked
against archived NGWU issues (independent EIA display of the same series) mismatch by $0.01-0.07:
  2025-12-01 first-print 5.05 vs vintage 5.08 | 12-02 4.81/4.83 | 12-03 4.87/4.86
  2026-01-15 2.95/2.92 | 01-16 3.13/3.06 | 01-20 3.98/4.00 | 01-21 4.98/4.96
The store carries the CURRENT DNAV VINTAGE (retrieved 2026-07-20) and says so per row; the
first-print deltas above are recorded in the store meta. Whether this is true revision or two
snapshot conventions of the Refinitiv assessment is not resolvable from the public displays; the
magnitude (cents, on a series that moved $27 in the squeeze) is recorded and named.

UNITS: $/MMBtu on both legs (EIA HH spot and NYMEX NG settle) - the basis is a plain difference.

THE FUTURES LEG (read-only)
---------------------------
calendar_front settle per session from data/contract_structure/NG_structure.json (field
`calendar_front_settle`, keyed here by its `curve_asof` session). Per contract_structure.py /
forward_curve.py that price is the Databento GLBX ohlcv-1d daily-bar CLOSE (~ settle, not the
official CME settlement print; e.g. NGG26's last session close 7.200 vs official final settle
7.460). The approximation is named in `front_settle_source`. Settlement of session S is publicly
knowable S+1 (CME next-morning rule) - always earlier than the spot's own knowable_from, so the
joint blind wall is the spot's.

MISSING IS EXPLICIT, NEVER ZERO
-------------------------------
Weekends have no cash print (Friday's trade covers the weekend package). Holidays print nothing.
Every missing weekday in the store span is NAMED in meta.missing_weekdays_named (Labor Day,
Veterans Day, Thanksgiving +1, Christmas +1, New Year +1, MLK, Presidents Day, ...). Nothing is
interpolated, bridged, or carried across a gap: basis changes are None whenever any business day in
their window lacks a value or the front symbol rolled. Zero synthetic data.

PUBLIC API
----------
  cash_basis_asof(date: str) -> dict | None
      date "YYYY-MM-DD" (or "YYYYMMDD"). Returns the decision-time cash-basis state using ONLY
      publications knowable strictly before/at start of `date` (knowable_from <= date), or None if
      no spot is publishable yet (dates before 2025-09-05). Fields:
        hh_spot                      latest publishable EIA HH daily spot ($/MMBtu, current vintage)
        hh_spot_gas_day              the gas day that price belongs to
        hh_spot_publication_date     the release event that made it knowable (measured or modeled)
        hh_spot_publication_basis    measured_ngwu_release | next_measured_release_holiday_skip |
                                     modeled_thursday_release
        age_days                     (date - gas_day) in calendar days: the honest staleness
        front_settle                 calendar-front close~settle for the SAME session as the spot's
                                     gas day (exact match required for the basis; nearest prior
                                     session reported informationally when exact is absent)
        front_settle_session         the session the settle came from (named)
        front_settle_symbol          e.g. NGG26
        front_settle_source          provenance + the close~settle caveat
        hh_cash_minus_front_settle   spot - settle, matched-day only, else None
        basis_chg_1d/3d/5d           change vs 1/3/5 BUSINESS days earlier; None unless every
                                     business day in the window has a matched-day basis AND the
                                     front symbol is constant across the window (never bridge a
                                     None, never difference across a roll)
        note                         staleness / gap / roll blockers, human-readable
  spot_for_gas_day(gas_day: str) -> float | None       (store lookup, no wall - build/audit use)

CLI
---
  python research/kalshi/cash_basis.py --build [--raw PATH]   # parse raw DNAV HTML -> store
  python research/kalshi/cash_basis.py --selftest
  python research/kalshi/cash_basis.py --show 2026-01-30
  python research/kalshi/cash_basis.py --table 2026-01-16 2026-01-30
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from datetime import date as _date, datetime, timedelta, timezone

# Repo-root anchored paths (module-relative, not CWD - the S98 Tier 0 fix pattern).
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORE_DIR = os.path.join(_ROOT, "data", "cash_basis")
STORE_PATH = os.path.join(STORE_DIR, "hh_cash.json")
RAW_DIR = os.path.join(STORE_DIR, "raw")
STRUCTURE_PATH = os.path.join(_ROOT, "data", "contract_structure", "NG_structure.json")

SOURCE_URL = "https://www.eia.gov/dnav/ng/hist/rngwhhdD.htm"
SERIES_NAME = "EIA Henry Hub Natural Gas Spot Price, daily (Dollars per Million Btu), Refinitiv-sourced"
RANGE_START = "2025-09-01"

# ---------------------------------------------------------------------------------------------
# Measured publication mechanics (see module docstring; investigated 2026-07-20).
# ---------------------------------------------------------------------------------------------
# Era 1: NGWU release dates measured from EIA's archive index. Each release carries daily spot
# through release-1 (verified: Jan 22 issue -> through Jan 21; Dec 4 issue -> through Dec 3).
ERA1_RELEASES = [
    "2025-09-04", "2025-09-11", "2025-09-18", "2025-09-25",
    "2025-10-02", "2025-10-09", "2025-10-16", "2025-10-23", "2025-10-30",
    "2025-11-06", "2025-11-13", "2025-11-20",            # no Nov 27 issue (Thanksgiving)
    "2025-12-04", "2025-12-11", "2025-12-18",            # no Dec 25 / Jan 1 issues (year-end)
    "2026-01-08", "2026-01-15", "2026-01-22",            # Jan 22 = FINAL NGWU
]
ERA1_LAST_COVERED = "2026-01-21"       # the final NGWU carried spot through this gas day
ERA2_FIRST_RELEASE = "2026-01-29"      # WNGSR Supplement launch (Thursday), measured
# Era 2 model (conservative): release = first Thursday R with R >= gas_day+2 and R >= launch;
# data-through R-2 (consistent with the DNAV stamp observed 2026-07-20: release Wed 7/15, data
# through Mon 7/13). knowable_from = R+1 in both eras.

# First-print (NGWU archived issues, fetched 2026-07-20) vs current DNAV vintage - MEASURED.
FIRST_PRINT_VS_VINTAGE = {
    "2025-12-01": {"first_print": 5.05, "ngwu_issue": "2025-12-04"},
    "2025-12-02": {"first_print": 4.81, "ngwu_issue": "2025-12-04"},
    "2025-12-03": {"first_print": 4.87, "ngwu_issue": "2025-12-04"},
    "2026-01-15": {"first_print": 2.95, "ngwu_issue": "2026-01-22"},
    "2026-01-16": {"first_print": 3.13, "ngwu_issue": "2026-01-22"},
    "2026-01-20": {"first_print": 3.98, "ngwu_issue": "2026-01-22"},
    "2026-01-21": {"first_print": 4.98, "ngwu_issue": "2026-01-22"},
}

# Named no-print weekdays (cash market holidays / source-blank days) in the store span.
HOLIDAY_NAMES = {
    "2025-09-01": "Labor Day",
    "2025-11-11": "Veterans Day",
    "2025-11-27": "Thanksgiving Day",
    "2025-11-28": "Day after Thanksgiving (NGWU prints 'Holiday')",
    "2025-12-25": "Christmas Day",
    "2025-12-26": "Day after Christmas (no print in source)",
    "2026-01-01": "New Year's Day",
    "2026-01-02": "Day after New Year's (no print in source)",
    "2026-01-19": "Martin Luther King Jr. Day",
    "2026-02-16": "Presidents Day",
    "2026-04-03": "Good Friday",
    "2026-05-25": "Memorial Day",
    "2026-06-19": "Juneteenth",
    "2026-07-03": "Independence Day (observed)",
}

_MON = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
_ROW_RE = re.compile(
    r"<td class='B6'>(?:&nbsp;)*\s*(\d{4})\s+([A-Za-z]{3})-\s?(\d{1,2})\s+to\s+([A-Za-z]{3})-\s?(\d{1,2})</td>"
    r"\s*<td class='B3'>([^<]*)</td>\s*<td class='B3'>([^<]*)</td>\s*<td class='B3'>([^<]*)</td>"
    r"\s*<td class='B3'>([^<]*)</td>\s*<td class='B3'>([^<]*)</td>")
_REL_RE = re.compile(r"Release Date:\s*(\d{1,2})/(\d{1,2})/(\d{4})")


def _require(cond: bool, msg: str) -> None:
    """Assertion immune to python -O; every blind-wall invariant goes through here."""
    if not cond:
        raise AssertionError("cash_basis invariant violated: " + msg)


def _d(s: str) -> _date:
    s = s.strip()
    if re.fullmatch(r"\d{8}", s):
        s = f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return _date.fromisoformat(s)


def _biz_back(d: _date, k: int) -> _date:
    """k business (Mon-Fri) days before d. Pure calendar grid - holidays are NOT skipped, so a
    holiday inside the window shows up as a missing value and correctly voids the change."""
    while k > 0:
        d = d - timedelta(days=1)
        if d.weekday() < 5:
            k -= 1
    return d


def _first_thursday_on_or_after(d: _date) -> _date:
    return d + timedelta(days=(3 - d.weekday()) % 7)


def publication_for_gas_day(gas_day: str) -> tuple[str, str]:
    """(publication_date, basis_tag) for a gas day, per the measured/modeled era mechanics."""
    t = _d(gas_day)
    if gas_day <= ERA1_LAST_COVERED:
        later = [r for r in ERA1_RELEASES if _d(r) > t]
        _require(bool(later), f"no measured NGWU release after {gas_day}")
        rel = later[0]
        tag = ("measured_ngwu_release" if (_d(rel) - t).days <= 8
               else "next_measured_release_holiday_skip")
        return rel, tag
    lo = max(t + timedelta(days=2), _d(ERA2_FIRST_RELEASE))
    return _first_thursday_on_or_after(lo).isoformat(), "modeled_thursday_release"


def knowable_from(publication_date: str) -> str:
    """Release hour vs decision hour is unmeasured -> usable the day AFTER the release."""
    return (_d(publication_date) + timedelta(days=1)).isoformat()


# ---------------------------------------------------------------------------------------------
# Build: parse the raw DNAV HTML -> store
# ---------------------------------------------------------------------------------------------
def parse_dnav_html(path: str) -> tuple[dict[str, float], dict]:
    html = open(path, encoding="utf-8", errors="replace").read()
    series: dict[str, float] = {}
    for (yr, m1, d1, _m2, _d2, *vals) in _ROW_RE.findall(html):
        start = _date(int(yr), _MON[m1], int(d1))
        _require(start.weekday() == 0, f"DNAV week row not Monday-anchored: {start}")
        for k, v in enumerate(vals):
            v = v.replace("&nbsp;", "").strip()
            if v in ("", "-", "--", "NA", "W"):
                continue                       # blank/flagged cell = no print, never zero
            series[(start + timedelta(days=k)).isoformat()] = float(v)
    rels = _REL_RE.findall(html)
    stamps = [f"{y}-{int(m):02d}-{int(dd):02d}" for (m, dd, y) in rels]
    return series, {"release_stamps_on_page": sorted(set(stamps))}


def build_store(raw_path: str | None = None) -> dict:
    if raw_path is None:
        cands = sorted(glob.glob(os.path.join(RAW_DIR, "rngwhhdD_*.htm")))
        if not cands:
            raise FileNotFoundError(
                f"no raw DNAV HTML under {RAW_DIR}; download {SOURCE_URL} first (zero synthetic data)")
        raw_path = cands[-1]
    series, page_meta = parse_dnav_html(raw_path)
    keep = {k: v for k, v in sorted(series.items()) if k >= RANGE_START}
    _require(bool(keep), f"no rows on/after {RANGE_START} - source coverage changed, STOP")

    retrieved_at = datetime.fromtimestamp(os.path.getmtime(raw_path), tz=timezone.utc).isoformat()
    src_tag = f"eia_dnav_html:{os.path.basename(raw_path)}"
    rows, missing = [], {}
    end = max(keep)
    d = _d(RANGE_START)
    while d.isoformat() <= end:
        iso = d.isoformat()
        if d.weekday() < 5:
            if iso in keep:
                pub, tag = publication_for_gas_day(iso)
                _require((_d(knowable_from(pub)) - d).days >= 2,
                         f"knowable_from < gas_day+2 for {iso}")
                rows.append({
                    "gas_day": iso,
                    "spot": keep[iso],
                    "source": src_tag,
                    "retrieved_at": retrieved_at,
                    "publication_date_assumed_or_measured": pub,
                    "publication_basis": tag,
                    "knowable_from": knowable_from(pub),
                })
            else:
                missing[iso] = HOLIDAY_NAMES.get(iso, "no publication (reason not stated by source)")
        d += timedelta(days=1)

    vintage = {}
    for gd, fp in FIRST_PRINT_VS_VINTAGE.items():
        cur = keep.get(gd)
        vintage[gd] = {**fp, "current_vintage": cur,
                       "delta": None if cur is None else round(cur - fp["first_print"], 4)}

    store = {
        "meta": {
            "series": SERIES_NAME,
            "source_url": SOURCE_URL,
            "source_route": "public DNAV history page (no API key; EIA_API_KEY route not used)",
            "raw_file": os.path.relpath(raw_path, _ROOT),
            "retrieved_at": retrieved_at,
            "range_start": RANGE_START,
            "range_end": end,
            "n_rows": len(rows),
            "dnav_release_observed_2026_07_20": {
                "release_date": "2026-07-15", "next_release_date": "2026-07-22",
                "data_through": "2026-07-13",
                "note": "weekly batch publication measured on the page itself; see publication_model",
            },
            "page_release_stamps_parsed": page_meta["release_stamps_on_page"],
            "publication_model": {
                "era1": "gas days <= 2026-01-21: NGWU weekly issues (measured release list), each "
                        "carrying spot through release-1; holiday-skipped weeks first appear at the "
                        "NEXT measured release (no issue existed for Nov 27, Dec 25, Jan 1)",
                "era1_releases_measured": ERA1_RELEASES,
                "era2": "gas days >= 2026-01-22: WNGSR Supplement era (launched Thu 2026-01-29, "
                        "'every Thursday afternoon'); CONSERVATIVE model release = first Thursday "
                        ">= gas_day+2, data-through release-2 (July DNAV stamp measured release-2); "
                        "per-issue winter dates not directly measurable (Wayback unreachable)",
                "knowable_rule": "knowable_from = release_date + 1 day (release hour unmeasured; "
                                 "day-after is airtight)",
                "min_lag_days": 2,
            },
            "vintage_crosscheck_first_print_vs_current": vintage,
            "vintage_note": "all 7 checked days differ at $0.01-0.07; store carries the CURRENT "
                            "DNAV vintage retrieved 2026-07-20; as-first-printed values are the "
                            "NGWU columns above (feed K discipline: revised values stay, labeled)",
            "missing_weekdays_named": missing,
        },
        "rows": rows,
    }
    os.makedirs(STORE_DIR, exist_ok=True)
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=1)
    return store


# ---------------------------------------------------------------------------------------------
# Load + joins
# ---------------------------------------------------------------------------------------------
_CACHE: dict = {}


def _load_store() -> dict | None:
    if "store" not in _CACHE:
        if not os.path.exists(STORE_PATH):
            return None
        _CACHE["store"] = json.load(open(STORE_PATH, encoding="utf-8"))
    return _CACHE["store"]


def _load_settles() -> dict[str, dict]:
    """curve_asof session -> {settle, symbol} from the read-only structure store."""
    if "settles" not in _CACHE:
        out: dict[str, dict] = {}
        if os.path.exists(STRUCTURE_PATH):
            j = json.load(open(STRUCTURE_PATH, encoding="utf-8"))
            for rec in j.values():
                sess, px = rec.get("curve_asof"), rec.get("calendar_front_settle")
                if not sess or px is None:
                    continue
                prev = out.get(sess)
                _require(prev is None or prev["settle"] == px,
                         f"conflicting settles for session {sess}")
                out[sess] = {"settle": px, "symbol": rec.get("calendar_front_symbol")}
        _CACHE["settles"] = out
    return _CACHE["settles"]


def spot_for_gas_day(gas_day: str) -> float | None:
    """Raw store lookup by gas day - NO blind wall; build/audit/selftest use only."""
    store = _load_store()
    if not store:
        return None
    if "by_day" not in _CACHE:
        _CACHE["by_day"] = {r["gas_day"]: r for r in store["rows"]}
    row = _CACHE["by_day"].get(_d(gas_day).isoformat())
    return None if row is None else row["spot"]


def _matched_basis(gas_day: str) -> tuple[float | None, str | None]:
    """(basis, symbol) for one gas day, EXACT same-session settle only; (None, None) if either
    leg is missing. Used by the change ladder - fallback sessions never enter changes."""
    spot = spot_for_gas_day(gas_day)
    st = _load_settles().get(gas_day)
    if spot is None or st is None:
        return None, None
    return round(spot - st["settle"], 4), st["symbol"]


def cash_basis_asof(date: str) -> dict | None:
    store = _load_store()
    if not store:
        return None
    day = _d(date)
    iso = day.isoformat()

    # latest spot whose PUBLICATION makes it knowable by `date` (the blind wall)
    usable = [r for r in store["rows"] if r["knowable_from"] <= iso]
    if not usable:
        return None
    row = usable[-1]
    g = row["gas_day"]
    _require(row["knowable_from"] <= iso, f"blind wall: {g} not knowable at {iso}")
    _require(g < iso, f"blind wall: gas_day {g} not strictly before {iso}")

    notes = [f"spot is gas day {g} published {row['publication_date_assumed_or_measured']} "
             f"({row['publication_basis']})"]
    age = (day - _d(g)).days
    if age > 5:
        notes.append(f"STALE {age}d")

    # front settle, matched session first; nearest prior session reported when exact is absent
    settles = _load_settles()
    st, sess, fallback = settles.get(g), g, False
    if st is None:
        prior = sorted(s for s in settles if s < g)
        if prior:
            sess, st, fallback = prior[-1], settles[prior[-1]], True

    basis = None
    if st is None:
        settle = symbol = None
        sess = None
        notes.append("front_settle None: structure store has no session on/before the spot's "
                     "gas day (store starts 2025-11-02)")
    else:
        _require(sess <= g, f"settle session {sess} after spot gas day {g}")
        _require(sess < iso, f"settle session {sess} not strictly before asof {iso}")
        settle, symbol = st["settle"], st["symbol"]
        if fallback:
            notes.append(f"no settle session ON {g}; nearest prior {sess} reported "
                         "informationally; basis None (matched-day only)")
        else:
            basis = round(row["spot"] - settle, 4)

    # 1/3/5 business-day basis changes: every day in the window must have a matched-day basis and
    # the SAME front symbol - never bridge a None, never difference across a roll.
    chg: dict[str, float | None] = {}
    for k in (1, 3, 5):
        val = None
        if basis is not None:
            gd = _d(g)
            window = [_biz_back(gd, i).isoformat() for i in range(k + 1)]  # [G, G-1, ..., G-k]
            legs = [_matched_basis(w) for w in window]
            bad = next((w for w, (b, _s) in zip(window, legs) if b is None), None)
            if bad is not None:
                notes.append(f"chg_{k}d None: {bad} has no matched basis"
                             + (f" ({HOLIDAY_NAMES[bad]})" if bad in HOLIDAY_NAMES else ""))
            elif len({s for (_b, s) in legs}) != 1:
                notes.append(f"chg_{k}d None: front symbol rolled inside window")
            else:
                val = round(legs[0][0] - legs[-1][0], 4)
        chg[f"basis_chg_{k}d"] = val

    return {
        "hh_spot": row["spot"],
        "hh_spot_gas_day": g,
        "hh_spot_publication_date": row["publication_date_assumed_or_measured"],
        "hh_spot_publication_basis": row["publication_basis"],
        "hh_spot_vintage": "current DNAV vintage (retrieved 2026-07-20); first prints differed "
                           "by $0.01-0.07 on all 7 measured days",
        "age_days": age,
        "front_settle": settle,
        "front_settle_session": sess,
        "front_settle_symbol": symbol,
        "front_settle_source": "contract_structure calendar_front_settle (GLBX ohlcv-1d close "
                               "~ settle, not the official CME settlement print)",
        "hh_cash_minus_front_settle": basis,
        **chg,
        "note": "; ".join(notes),
    }


# ---------------------------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------------------------
def _selftest() -> int:
    print("=== cash_basis --selftest ===")
    store = _load_store()
    _require(store is not None, f"store missing at {STORE_PATH}; run --build")
    rows = store["rows"]
    fails = 0

    # S1 store integrity
    days = [r["gas_day"] for r in rows]
    _require(days == sorted(days) and len(days) == len(set(days)), "rows not sorted-unique")
    _require(all(_d(x).weekday() < 5 for x in days), "weekend gas_day in store")
    _require(all(isinstance(r["spot"], float) and r["spot"] > 0 for r in rows), "bad spot value")
    lags = [(_d(r["knowable_from"]) - _d(r["gas_day"])).days for r in rows]
    _require(min(lags) >= 2, "publication lag floor broken (< gas_day+2)")
    tags: dict[str, int] = {}
    for r in rows:
        tags[r["publication_basis"]] = tags.get(r["publication_basis"], 0) + 1
    print(f"S1 store: {len(rows)} rows {days[0]}..{days[-1]}; lag min/max {min(lags)}/{max(lags)} "
          f"days; basis tags {tags}")
    worst = sorted(rows, key=lambda r: -(_d(r["knowable_from"]) - _d(r["gas_day"])).days)[:3]
    print("   naive-T+1 rule would have leaked EVERY row (lag floor is 2d); worst stretches: "
          + ", ".join(f"{r['gas_day']} not knowable until {r['knowable_from']} "
                      f"({(_d(r['knowable_from']) - _d(r['gas_day'])).days}d)" for r in worst))

    # S2 known values: exact vs the DNAV display (parse-integrity), tolerance vs the NGWU
    # archived issues (independent EIA display of the same series; vintage differs at cent level)
    dnav_known = {"2025-12-01": 5.08, "2026-01-16": 3.06, "2026-01-22": 8.42,
                  "2026-01-23": 30.72, "2026-07-13": 2.83}
    for gd, exp in dnav_known.items():
        got = spot_for_gas_day(gd)
        ok = got == exp
        fails += 0 if ok else 1
        print(f"S2 dnav-display  {gd}  expect {exp}  got {got}  {'OK' if ok else 'FAIL'}")
    for gd, fp in FIRST_PRINT_VS_VINTAGE.items():
        got = spot_for_gas_day(gd)
        delta = None if got is None else round(got - fp["first_print"], 4)
        ok = got is not None and abs(delta) <= 0.07
        fails += 0 if ok else 1
        print(f"S2 ngwu-independent {gd}  first-print {fp['first_print']}  vintage {got}  "
              f"delta {delta}  {'OK(<=0.07 vintage)' if ok else 'FAIL'}")

    # S3 blind-wall audit: every asof evaluation over the whole span must only surface rows
    # already publishable; count violations (must be 0)
    viol = 0
    n_eval = 0
    d = _d(RANGE_START)
    stop = _d(store["meta"]["range_end"]) + timedelta(days=5)
    while d <= stop:
        r = cash_basis_asof(d.isoformat())   # internal _require calls also guard every field
        if r is not None:
            n_eval += 1
            k = next(x["knowable_from"] for x in rows if x["gas_day"] == r["hh_spot_gas_day"])
            if k > d.isoformat() or r["hh_spot_gas_day"] >= d.isoformat():
                viol += 1
            if r["front_settle_session"] is not None and r["front_settle_session"] >= d.isoformat():
                viol += 1
        d += timedelta(days=1)
    print(f"S3 blind-wall audit: {viol} violations over {n_eval} asof evaluations "
          f"({RANGE_START}..{stop.isoformat()})  {'OK' if viol == 0 else 'FAIL'}")
    fails += viol

    # S4 missing-is-None: weekend + holiday days are absent/named, never zeroed or bridged
    _require(spot_for_gas_day("2026-01-17") is None, "Saturday has a spot")   # weekend
    _require(spot_for_gas_day("2026-01-18") is None, "Sunday has a spot")     # weekend
    _require(spot_for_gas_day("2026-01-19") is None, "MLK holiday has a spot")
    named = store["meta"]["missing_weekdays_named"]
    _require("2026-01-19" in named, "MLK gap not named")
    sat = cash_basis_asof("2026-01-17")
    _require(sat is not None and sat["hh_spot_gas_day"] == "2026-01-14" and sat["age_days"] == 3,
             f"weekend asof wrong: {sat}")
    # asof 2026-01-24: latest knowable spot is gas day Jan 21 (final NGWU, knowable Jan 23); its
    # 3d/5d windows reach back across MLK (Jan 19, no print) -> those changes MUST be None while
    # chg_1d (Jan 20->21, both printed) stays real. Never bridge a None.
    mlk = cash_basis_asof("2026-01-24")
    _require(mlk is not None and mlk["hh_spot_gas_day"] == "2026-01-21", f"asof Jan 24 wrong: {mlk}")
    _require(mlk["basis_chg_3d"] is None and mlk["basis_chg_5d"] is None,
             "chg_3d/5d bridged the MLK gap")
    _require(mlk["basis_chg_1d"] is not None, "chg_1d wrongly None on two printed days")
    print("S4 missing-is-None: no Sat/Sun/MLK rows; MLK named "
          f"('{named['2026-01-19']}'); asof(Sat 2026-01-17) -> gas day {sat['hh_spot_gas_day']} "
          f"age {sat['age_days']}d spot {sat['hh_spot']}; asof(2026-01-24) -> gas day "
          f"{mlk['hh_spot_gas_day']}, chg_1d {mlk['basis_chg_1d']}, chg_3d/5d "
          f"{mlk['basis_chg_3d']}/{mlk['basis_chg_5d']} (window crosses MLK -> None, never bridged)")

    # S5 the G11 window, factual
    print("S5 G11 window (gas day | spot | knowable_from | settle sym | matched basis):")
    d = _d("2026-01-16")
    while d <= _d("2026-01-30"):
        iso = d.isoformat()
        if d.weekday() < 5:
            sp = spot_for_gas_day(iso)
            b, sym = _matched_basis(iso)
            kf = next((x["knowable_from"] for x in rows if x["gas_day"] == iso), None)
            st = _load_settles().get(iso)
            print(f"   {iso}  spot {sp if sp is not None else 'None':>6}  knowable {kf or '-':>10}  "
                  f"settle {(st or {}).get('settle', 'None'):>6} {sym or '-':6}  "
                  f"basis {b if b is not None else 'None'}")
        d += timedelta(days=1)

    print(f"=== selftest {'PASS' if fails == 0 else f'FAIL ({fails})'} ===")
    return 0 if fails == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--raw", default=None, help="path to a saved DNAV rngwhhdD HTML")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--show", metavar="DATE")
    ap.add_argument("--table", nargs=2, metavar=("START", "END"))
    a = ap.parse_args()
    if a.build:
        s = build_store(a.raw)
        m = s["meta"]
        print(f"built {STORE_PATH}: {m['n_rows']} rows {m['range_start']}..{m['range_end']}; "
              f"{len(m['missing_weekdays_named'])} missing weekdays named")
        return 0
    if a.selftest:
        return _selftest()
    if a.show:
        print(json.dumps(cash_basis_asof(a.show), indent=2))
        return 0
    if a.table:
        d, end = _d(a.table[0]), _d(a.table[1])
        while d <= end:
            r = cash_basis_asof(d.isoformat())
            if r:
                print(f"{d.isoformat()}  spot {r['hh_spot']:>6} ({r['hh_spot_gas_day']}, "
                      f"age {r['age_days']}d)  settle {r['front_settle']} "
                      f"{r['front_settle_symbol'] or '-'}  basis {r['hh_cash_minus_front_settle']}"
                      f"  chg1/3/5 {r['basis_chg_1d']}/{r['basis_chg_3d']}/{r['basis_chg_5d']}")
            d += timedelta(days=1)
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
