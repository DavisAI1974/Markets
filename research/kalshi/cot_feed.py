"""CFTC Commitments of Traders (COT) positioning feed for the NG intraday forecaster.

WHAT THIS IS
------------
An INPUT, not a thesis. It supplies the forecast agent with a view of NYMEX Henry
Hub natural gas trader positioning (who is long, who is short, how stretched) so
the agent can decide for itself whether positioning matters for a given day. This
module does not gate, score, rank or recommend anything.

SOURCE
------
CFTC Disaggregated Commitments of Traders, FUTURES-ONLY report.
Annual compressed archives, comma-delimited text:

    https://www.cftc.gov/files/dea/history/fut_disagg_txt_<YEAR>.zip

Each zip contains a single `f_year.txt`: quoted CSV, header row present,
one row per (market, report date). Disaggregated history begins 2006-06-13.

CONTRACT
--------
CFTC contract market code `023651` -- "NAT GAS NYME - NEW YORK MERCANTILE EXCHANGE".
This is the main NYMEX Henry Hub Natural Gas futures contract (NG, 10,000 MMBtu).

Deliberately NOT used (they are separate, smaller contracts and would give a
different positioning picture):
  03565C  HENRY HUB PENULTIMATE NAT GAS - NYMEX   (penultimate-settled variant)
  023391  NAT GAS ICE LD1 - ICE FUTURES ENERGY    (ICE, last-day)
  023392  NAT GAS ICE PEN - ICE FUTURES ENERGY    (ICE, penultimate)
  0233AT  NAT GAS LD1 for GDD -TEXOK - ICE        (regional basis)
  06665R / 06641A                                 (natural GASOLINE, unrelated)

THE BLIND WALL
--------------
COT reports positions as of TUESDAY but is not PUBLISHED until the following
FRIDAY at 15:30 ET. Joining on the report date leaks three days of future
positioning into every Wednesday and Thursday decision. Every record therefore
carries `publication_ts` (tz-aware, America/New_York) and ALL lookups key on it
with a STRICT inequality: a report is visible to decision time T only if
publication_ts < T.

Publication rule (derived, then validated):
  publication = first Friday strictly after report_date, at 15:30 ET,
                delayed one business day for each US federal holiday falling in
                (report_date, nominal_friday].
This reproduces the CFTC's published 2026 release schedule EXACTLY -- all 52
release dates including all six holiday-delayed ones (Jan 05, Jun 22, Jul 06,
Nov 16, Nov 30, Dec 28). See `_selftest_publication_rule`.

The normal rule is NOT sufficient on its own. The 2025 federal appropriations
lapse suspended COT publication from 2025-10-01 to 2025-11-12; the backlog was
then cleared on a published catch-up schedule running to 2025-12-29. Applying
the Friday rule across that window would have made the 2025-09-30 report look
public on 2025-10-03 when it did not exist until 2025-11-19 -- a 47-day leak
straight through the autumn. `PUBLICATION_OVERRIDES` carries the CFTC's actual
catch-up table for those 13 reports. During the lapse the feed correctly goes
STALE rather than silently fresh: on 2025-11-14 the newest visible report is
2025-09-23, `age_days` 48.8. The agent is told how old its information is.

MISSING IS EXPLICIT
-------------------
Absent values are None, never 0. A zeroed net position reads as "flat/neutral",
which is a false signal. `cot_asof` returns None when nothing is visible yet.
Percentile fields are None when the trailing window lacks enough real history;
they are never computed off a truncated window.

PUBLIC API
----------
    cot_asof(date, contract_code="023651", data_dir=None) -> dict | None

        date : datetime.date | datetime.datetime | str ("YYYY-MM-DD" or
               "YYYY-MM-DD HH:MM" / ISO8601)
               A naive datetime or a plain date is interpreted in America/New_York.
               A plain DATE is treated as 00:00 ET that day -- the conservative
               reading (a report published Friday 15:30 is NOT visible on the
               Friday date key, only from the following Monday's date key).
               Pass an explicit datetime for intraday precision.

        returns dict | None. None means "no COT report was published before this
        decision time" -- treat as unknown, NOT as flat.

        dict keys:
          report_date              str  YYYY-MM-DD  (Tuesday the positions are as of)
          publication_ts           str  ISO8601 tz-aware ET (when it became public)
          publication_delayed      bool (shifted off the nominal Friday)
          publication_confidence   str  "published_schedule" (CFTC catch-up table)
                                        | "derived" (validated normal rule)
                                        | "derived_unreliable" (known-disrupted
                                          window with no CFTC per-date table)
          age_days                 float days between publication and decision time.
                                        Large values are real: during the 2025
                                        lapse this reaches ~49 days. Stale
                                        positioning is still information, but the
                                        agent should weight it by this field.
          contract_code            str
          market_name              str
          open_interest            int
          managed_money_long       int
          managed_money_short      int
          managed_money_net        int
          managed_money_net_chg_wow        int | None
          producer_merchant_net    int
          swap_dealer_net          int
          other_reportable_net     int
          managed_money_net_pctile_1y      float | None  0-100
          managed_money_net_pctile_3y      float | None  0-100
          pctile_1y_n_obs          int   observations backing the 1y percentile
          pctile_3y_n_obs          int   observations backing the 3y percentile

CLI
---
    python cot_feed.py --build            # download archives + build the store
    python cot_feed.py --audit            # blind-wall + coverage audit
    python cot_feed.py --selftest         # self-tests (no network needed post-build)
    python cot_feed.py --asof 2026-01-15  # inspect one decision date
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import sys
import urllib.request
import zipfile
from typing import Any, Dict, List, Optional, Sequence

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    raise SystemExit("cot_feed requires Python 3.9+ (zoneinfo)")

ET = ZoneInfo("America/New_York")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NG_CONTRACT_CODE = "023651"
NG_MARKET_NAME_EXPECTED = "NAT GAS NYME - NEW YORK MERCANTILE EXCHANGE"

# S114: every contract code the forecaster actually SERVES. `--build` built exactly one
# of these (the default), so four of the five stores went stale in place while the build
# reported success - and staleness in a positioning book is invisible downstream, because
# a frozen COT reads as a real reading with an older report_date. Measured on g24: the
# NYMEX book was current while all four ICE books sat one publication behind, and three
# specialists reasoned off the spent-vs-fresh question those books decide. `--build` with
# no --contract now builds the whole served set. Order = the harness's own read order.
SERVED_CONTRACT_CODES = ("023651", "023391", "023392", "0233AG", "0233AH")

ARCHIVE_URL = "https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
DEFAULT_DATA_DIR = os.path.join(_REPO, "data", "cot")
RAW_SUBDIR = "raw"
STORE_NAME = "ng_cot_{code}.json"

# Coverage the forecaster needs, plus the prior history the percentile windows
# need in order to be real rather than truncated. 3y percentile at 2025-01-01
# requires genuine data back to 2022-01-01; we pull from 2019 for headroom.
BUILD_YEARS = tuple(range(2019, dt.date.today().year + 1))

REQUIRED_COVERAGE_START = dt.date(2025, 1, 1)
REQUIRED_COVERAGE_END = dt.date(2026, 3, 1)

# A trailing window must carry at least this many real observations before a
# percentile is emitted. Below it the field is None (explicitly missing).
MIN_OBS_1Y = 45   # of ~52 weekly reports
MIN_OBS_3Y = 140  # of ~156

PUBLICATION_HOUR_ET = 15
PUBLICATION_MINUTE_ET = 30

# ---------------------------------------------------------------------------
# Publication overrides -- events where the normal Friday rule DOES NOT hold.
# Without these the feed would make reports visible weeks before they existed,
# which is the exact leak this module is built to prevent.
# ---------------------------------------------------------------------------

# 2025 federal appropriations lapse: COT processing and publication were
# interrupted 2025-10-01 to 2025-11-12, then cleared on an accelerated catch-up.
# Source: CFTC press release 9147-25 "CFTC to Accelerate Publication of
# Backlogged COT Data" (2025-12-09), which superseded the 2025-11-18 plan
# (press release 9138-25). The accelerated table is the one that actually ran:
# it returns to normal cadence with report 2025-12-30 published 2026-01-05,
# which is exactly what the CFTC's published 2026 release schedule shows. The
# superseded plan had 2025-12-30 publishing 2026-01-13, contradicting it.
PUBLICATION_OVERRIDES = {
    "2025-09-30": "2025-11-19",
    "2025-10-07": "2025-11-21",
    "2025-10-14": "2025-11-25",
    "2025-10-21": "2025-12-02",
    "2025-10-28": "2025-12-05",
    "2025-11-04": "2025-12-09",
    "2025-11-10": "2025-12-10",
    "2025-11-18": "2025-12-12",
    "2025-11-25": "2025-12-15",
    "2025-12-02": "2025-12-17",
    "2025-12-09": "2025-12-19",
    "2025-12-16": "2025-12-23",
    "2025-12-23": "2025-12-29",
}

# Windows where publication timing is known to be disrupted but the CFTC did
# not publish a per-report-date table we can transcribe. Records here keep a
# derived timestamp but are flagged `publication_confidence="derived_unreliable"`
# so a consumer can refuse them. The 2018-12/2019-01 lapse suspended COT and was
# cleared by a narrative Tue+Fri catch-up from 2019-02-01 with no per-date table
# (CFTC press release 7864-19). This is OUTSIDE the required coverage window and
# affects only percentile history, which keys on report dates, not publication.
PUBLICATION_UNVERIFIED_WINDOWS = (
    (dt.date(2018, 12, 18), dt.date(2019, 3, 29)),
)


# ---------------------------------------------------------------------------
# US federal holidays (needed for the publication rule)
# ---------------------------------------------------------------------------

def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    """n-th `weekday` (Mon=0) of month; n=-1 means last."""
    if n > 0:
        d = dt.date(year, month, 1)
        offset = (weekday - d.weekday()) % 7
        return d + dt.timedelta(days=offset + 7 * (n - 1))
    d = dt.date(year, month, 28)
    while (d + dt.timedelta(days=7)).month == month:
        d += dt.timedelta(days=7)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d: dt.date) -> dt.date:
    """Federal observance: Saturday -> preceding Friday, Sunday -> following Monday."""
    if d.weekday() == 5:
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + dt.timedelta(days=1)
    return d


def us_federal_holidays(year: int) -> set:
    """Observed US federal holidays for `year`.

    Juneteenth is a federal holiday from 2021 onward only.
    """
    h = {
        _observed(dt.date(year, 1, 1)),                 # New Year's Day
        _nth_weekday(year, 1, 0, 3),                    # MLK Jr Day
        _nth_weekday(year, 2, 0, 3),                    # Washington's Birthday
        _nth_weekday(year, 5, 0, -1),                   # Memorial Day
        _observed(dt.date(year, 7, 4)),                 # Independence Day
        _nth_weekday(year, 9, 0, 1),                    # Labor Day
        _nth_weekday(year, 10, 0, 2),                   # Columbus Day
        _observed(dt.date(year, 11, 11)),               # Veterans Day
        _nth_weekday(year, 11, 3, 4),                   # Thanksgiving
        _observed(dt.date(year, 12, 25)),               # Christmas
    }
    if year >= 2021:
        h.add(_observed(dt.date(year, 6, 19)))          # Juneteenth
    return h


_HOLIDAY_CACHE: Dict[int, set] = {}


def _is_holiday(d: dt.date) -> bool:
    if d.year not in _HOLIDAY_CACHE:
        _HOLIDAY_CACHE[d.year] = us_federal_holidays(d.year)
    return d in _HOLIDAY_CACHE[d.year]


def _is_business_day(d: dt.date) -> bool:
    return d.weekday() < 5 and not _is_holiday(d)


def _next_business_day(d: dt.date) -> dt.date:
    d += dt.timedelta(days=1)
    while not _is_business_day(d):
        d += dt.timedelta(days=1)
    return d


# ---------------------------------------------------------------------------
# The publication rule -- the blind wall
# ---------------------------------------------------------------------------

def _derived_publication(report_date: dt.date) -> "tuple[dt.datetime, bool]":
    """The normal-cadence rule, before overrides."""
    days_ahead = (4 - report_date.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    nominal = report_date + dt.timedelta(days=days_ahead)

    n_holidays = 0
    d = report_date + dt.timedelta(days=1)
    while d <= nominal:
        if _is_holiday(d):
            n_holidays += 1
        d += dt.timedelta(days=1)

    pub = nominal
    for _ in range(n_holidays):
        pub = _next_business_day(pub)
    while not _is_business_day(pub):
        pub = _next_business_day(pub)

    ts = dt.datetime(
        pub.year, pub.month, pub.day,
        PUBLICATION_HOUR_ET, PUBLICATION_MINUTE_ET, tzinfo=ET,
    )
    return ts, pub != nominal


def publication_datetime(report_date: dt.date) -> "tuple[dt.datetime, bool, str]":
    """Return (publication_ts_ET, was_delayed, confidence) for a COT report date.

    Normal cadence: first Friday strictly after `report_date` at 15:30 ET, pushed
    forward one business day for each US federal holiday in
    (report_date, nominal_friday]. Validated against the CFTC's published 2026
    release schedule -- reproduces all 52 dates and all 6 delays.

    Overrides (PUBLICATION_OVERRIDES) replace that rule for report dates caught
    in the 2025 appropriations lapse. An override may only ever DELAY visibility:
    the result is max(derived, override), so a transcription slip cannot open a
    leak, only close one.

    confidence is one of:
      "published_schedule"   taken from a CFTC-published catch-up table
      "derived"              normal-cadence rule, validated against 2026
      "derived_unreliable"   inside a known-disrupted window with no CFTC table
    """
    derived_ts, derived_delayed = _derived_publication(report_date)

    key = report_date.isoformat()
    if key in PUBLICATION_OVERRIDES:
        od = dt.date.fromisoformat(PUBLICATION_OVERRIDES[key])
        ov_ts = dt.datetime(od.year, od.month, od.day,
                            PUBLICATION_HOUR_ET, PUBLICATION_MINUTE_ET, tzinfo=ET)
        ts = max(ov_ts, derived_ts)
        nominal_friday = report_date + dt.timedelta(
            days=((4 - report_date.weekday()) % 7) or 7)
        return ts, ts.date() != nominal_friday, "published_schedule"

    for lo, hi in PUBLICATION_UNVERIFIED_WINDOWS:
        if lo <= report_date <= hi:
            return derived_ts, derived_delayed, "derived_unreliable"

    return derived_ts, derived_delayed, "derived"


# ---------------------------------------------------------------------------
# Fetch + parse
# ---------------------------------------------------------------------------

def _raw_dir(data_dir: str) -> str:
    return os.path.join(data_dir, RAW_SUBDIR)


def download_archives(data_dir: str, years: Sequence[int], force: bool = False) -> List[str]:
    raw = _raw_dir(data_dir)
    os.makedirs(raw, exist_ok=True)
    paths = []
    for year in years:
        dest = os.path.join(raw, "fut_disagg_txt_%d.zip" % year)
        if os.path.exists(dest) and not force and os.path.getsize(dest) > 1000:
            paths.append(dest)
            continue
        url = ARCHIVE_URL.format(year=year)
        # S114: cftc.gov sits behind Cloudflare, which 403s urllib's default
        # "Python-urllib/3.x" User-Agent while serving the identical file to any
        # browser UA. This is why the store silently froze at the 2026-07-20 build:
        # the current year's archive stopped downloading, every cached year was
        # already on disk and satisfied the not-force branch above, and the build
        # therefore "succeeded" one publication short. A 403 on ONE year is not a
        # layout change - send a real UA and say so if it still fails.
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; DavisAI-Markets/1.0; research data pull)",
            "Accept": "application/zip,*/*",
        })
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                blob = r.read()
        except Exception as exc:
            raise SystemExit(
                "FATAL: could not fetch %s (%s). The archive layout may have "
                "changed. Stopping rather than substituting data." % (url, exc)
            )
        if len(blob) < 1000 or not blob.startswith(b"PK"):
            raise SystemExit(
                "FATAL: %s did not return a zip archive (%d bytes). Format may "
                "have changed. Stopping rather than substituting data."
                % (url, len(blob))
            )
        with open(dest, "wb") as f:
            f.write(blob)
        paths.append(dest)
    return paths


def _to_int(raw: str) -> Optional[int]:
    """Parse a COT integer cell. Blank / '.' / unparseable -> None, NEVER 0."""
    if raw is None:
        return None
    s = raw.strip().replace(",", "")
    if s == "" or s == "." or s.lower() in ("na", "n/a"):
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


REQUIRED_COLUMNS = (
    "Market_and_Exchange_Names",
    "Report_Date_as_YYYY-MM-DD",
    "CFTC_Contract_Market_Code",
    "Open_Interest_All",
    "Prod_Merc_Positions_Long_All",
    "Prod_Merc_Positions_Short_All",
    "Swap_Positions_Long_All",
    "Swap__Positions_Short_All",
    "M_Money_Positions_Long_All",
    "M_Money_Positions_Short_All",
    "Other_Rept_Positions_Long_All",
    "Other_Rept_Positions_Short_All",
)


def parse_archives(paths: Sequence[str], contract_code: str) -> List[Dict[str, Any]]:
    """Extract every row for `contract_code` from the annual archives."""
    rows: List[Dict[str, Any]] = []
    seen_report_dates = set()

    for path in sorted(paths):
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".txt")]
            if not names:
                raise SystemExit("FATAL: no .txt member in %s" % path)
            for name in names:
                with z.open(name) as fh:
                    text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace",
                                            newline="")
                    reader = csv.DictReader(text)
                    missing = [c for c in REQUIRED_COLUMNS
                               if c not in (reader.fieldnames or [])]
                    if missing:
                        raise SystemExit(
                            "FATAL: %s is missing expected columns %s. The CFTC "
                            "file format has changed; stopping rather than "
                            "guessing a mapping." % (path, missing)
                        )
                    for row in reader:
                        if row.get("CFTC_Contract_Market_Code", "").strip() != contract_code:
                            continue
                        rd_raw = row["Report_Date_as_YYYY-MM-DD"].strip()
                        try:
                            report_date = dt.datetime.strptime(rd_raw, "%Y-%m-%d").date()
                        except ValueError:
                            raise SystemExit(
                                "FATAL: unparseable report date %r in %s"
                                % (rd_raw, path)
                            )
                        if report_date in seen_report_dates:
                            continue
                        seen_report_dates.add(report_date)

                        mm_long = _to_int(row["M_Money_Positions_Long_All"])
                        mm_short = _to_int(row["M_Money_Positions_Short_All"])
                        pm_long = _to_int(row["Prod_Merc_Positions_Long_All"])
                        pm_short = _to_int(row["Prod_Merc_Positions_Short_All"])
                        sd_long = _to_int(row["Swap_Positions_Long_All"])
                        sd_short = _to_int(row["Swap__Positions_Short_All"])
                        or_long = _to_int(row["Other_Rept_Positions_Long_All"])
                        or_short = _to_int(row["Other_Rept_Positions_Short_All"])

                        def net(a, b):
                            return None if (a is None or b is None) else a - b

                        pub_ts, delayed, conf = publication_datetime(report_date)

                        rows.append({
                            "report_date": report_date.isoformat(),
                            "publication_ts": pub_ts.isoformat(),
                            "publication_delayed": delayed,
                            "publication_confidence": conf,
                            "contract_code": contract_code,
                            "market_name": row["Market_and_Exchange_Names"].strip(),
                            "open_interest": _to_int(row["Open_Interest_All"]),
                            "managed_money_long": mm_long,
                            "managed_money_short": mm_short,
                            "managed_money_net": net(mm_long, mm_short),
                            "producer_merchant_net": net(pm_long, pm_short),
                            "swap_dealer_net": net(sd_long, sd_short),
                            "other_reportable_net": net(or_long, or_short),
                        })

    rows.sort(key=lambda r: r["report_date"])
    return rows


# ---------------------------------------------------------------------------
# Derived fields
# ---------------------------------------------------------------------------

def _percentile_of(value: float, window: Sequence[float]) -> float:
    """Percentile rank of `value` within `window` (inclusive), 0-100.

    Midpoint convention: ties contribute half weight, so an unchanged series
    sits at 50 rather than 0 or 100.
    """
    below = sum(1 for w in window if w < value)
    equal = sum(1 for w in window if w == value)
    return 100.0 * (below + 0.5 * equal) / len(window)


def enrich(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add week-over-week change and trailing 1y / 3y percentile fields.

    Percentiles are computed on the trailing calendar window ENDING at each
    row's own report date -- no forward information. When the window holds
    fewer than the minimum number of real observations the field is None.
    """
    out = []
    for i, row in enumerate(rows):
        r = dict(row)
        rd = dt.date.fromisoformat(r["report_date"])
        mm_net = r["managed_money_net"]

        # Week-over-week change. Only meaningful against the immediately prior
        # report; if it is missing or the gap is not a normal weekly step, None.
        chg = None
        if i > 0 and mm_net is not None:
            prev = rows[i - 1]
            prev_net = prev["managed_money_net"]
            gap = (rd - dt.date.fromisoformat(prev["report_date"])).days
            if prev_net is not None and 5 <= gap <= 10:
                chg = mm_net - prev_net
        r["managed_money_net_chg_wow"] = chg

        for label, days, min_obs in (("1y", 365, MIN_OBS_1Y), ("3y", 1095, MIN_OBS_3Y)):
            key = "managed_money_net_pctile_%s" % label
            nkey = "pctile_%s_n_obs" % label
            if mm_net is None:
                r[key] = None
                r[nkey] = 0
                continue
            start = rd - dt.timedelta(days=days)
            window = [
                rows[j]["managed_money_net"]
                for j in range(0, i + 1)
                if rows[j]["managed_money_net"] is not None
                and start <= dt.date.fromisoformat(rows[j]["report_date"]) <= rd
            ]
            r[nkey] = len(window)
            r[key] = round(_percentile_of(mm_net, window), 2) if len(window) >= min_obs else None
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

def store_path(data_dir: str, contract_code: str) -> str:
    return os.path.join(data_dir, STORE_NAME.format(code=contract_code))


def build(data_dir: str = DEFAULT_DATA_DIR,
          contract_code: str = NG_CONTRACT_CODE,
          years: Sequence[int] = BUILD_YEARS,
          force: bool = False) -> Dict[str, Any]:
    os.makedirs(data_dir, exist_ok=True)
    paths = download_archives(data_dir, years, force=force)
    rows = parse_archives(paths, contract_code)
    if not rows:
        raise SystemExit(
            "FATAL: contract code %s produced no rows. Verify the code against "
            "the archive; stopping rather than substituting another contract."
            % contract_code
        )
    names = sorted({r["market_name"] for r in rows})
    if contract_code == NG_CONTRACT_CODE and NG_MARKET_NAME_EXPECTED not in names:
        raise SystemExit(
            "FATAL: code %s no longer maps to %r (found %s). Stopping."
            % (contract_code, NG_MARKET_NAME_EXPECTED, names)
        )
    rows = enrich(rows)
    store = {
        "source": "CFTC Disaggregated Commitments of Traders, futures-only",
        "source_url_pattern": ARCHIVE_URL,
        "contract_code": contract_code,
        "market_names": names,
        "built_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "years": list(years),
        "publication_rule": (
            "first Friday strictly after report_date at 15:30 ET, delayed one "
            "business day per US federal holiday in (report_date, nominal_friday]; "
            "validated against the CFTC published 2026 release schedule"
        ),
        "n_reports": len(rows),
        "reports": rows,
    }
    dest = store_path(data_dir, contract_code)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=1)
    return store


_STORE_CACHE: Dict[str, Dict[str, Any]] = {}


def load_store(data_dir: str = DEFAULT_DATA_DIR,
               contract_code: str = NG_CONTRACT_CODE) -> Dict[str, Any]:
    path = store_path(data_dir, contract_code)
    if path not in _STORE_CACHE:
        if not os.path.exists(path):
            raise FileNotFoundError(
                "COT store not built: %s. Run `python cot_feed.py --build`." % path
            )
        with open(path, encoding="utf-8") as f:
            _STORE_CACHE[path] = json.load(f)
    return _STORE_CACHE[path]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _coerce_decision_ts(date: Any) -> dt.datetime:
    """Normalise a decision moment to a tz-aware ET datetime.

    A plain date (or a 'YYYY-MM-DD' string) becomes 00:00 ET that day, which is
    the conservative reading: a report published Friday 15:30 ET is NOT visible
    under the Friday date key, only from the next date key onward.
    """
    if isinstance(date, dt.datetime):
        d = date
    elif isinstance(date, dt.date):
        d = dt.datetime(date.year, date.month, date.day)
    elif isinstance(date, str):
        s = date.strip().replace("Z", "+00:00")
        try:
            d = dt.datetime.fromisoformat(s)
        except ValueError:
            try:
                d = dt.datetime.strptime(s[:10], "%Y-%m-%d")
            except ValueError:
                raise ValueError("cot_asof: unparseable date %r" % date)
    else:
        raise TypeError("cot_asof: unsupported date type %r" % type(date))
    if d.tzinfo is None:
        d = d.replace(tzinfo=ET)
    return d.astimezone(ET)


def cot_asof(date: Any,
             contract_code: str = NG_CONTRACT_CODE,
             data_dir: str = DEFAULT_DATA_DIR) -> Optional[Dict[str, Any]]:
    """Latest COT report PUBLISHED strictly before the given decision moment.

    See the module docstring for the argument and return contract. Returns None
    when no report was public yet -- that means UNKNOWN, not flat.
    """
    decision = _coerce_decision_ts(date)
    store = load_store(data_dir, contract_code)

    # Full scan, no early break: publication order is NOT guaranteed to follow
    # report-date order once catch-up overrides are in play. Pick the report
    # with the LATEST report_date among those already public -- that is the
    # freshest positioning the agent could actually have known.
    latest = None
    for r in store["reports"]:
        pub = dt.datetime.fromisoformat(r["publication_ts"])
        if pub < decision:            # STRICT: the blind wall
            if latest is None or r["report_date"] > latest[0]["report_date"]:
                latest = (r, pub)

    if latest is None:
        return None

    row, pub = latest
    out = dict(row)
    out["age_days"] = round((decision - pub).total_seconds() / 86400.0, 4)
    return out


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def audit(data_dir: str = DEFAULT_DATA_DIR,
          contract_code: str = NG_CONTRACT_CODE,
          verbose: bool = True) -> Dict[str, Any]:
    store = load_store(data_dir, contract_code)
    rows = store["reports"]
    report = {}

    # -- blind wall: publication must strictly follow the report date, and
    #    cot_asof must never return a report published at or after the decision.
    violations = []
    for r in rows:
        rd = dt.date.fromisoformat(r["report_date"])
        pub = dt.datetime.fromisoformat(r["publication_ts"])
        if pub.date() <= rd:
            violations.append(("publication_not_after_report", r["report_date"]))
        if (pub.date() - rd).days < 3:
            violations.append(("publication_lag_under_3_days", r["report_date"]))

    # exhaustive walk of every calendar day in the coverage window at several
    # decision times: assert the returned report was public before that moment
    probe_violations = []
    day = REQUIRED_COVERAGE_START
    while day <= REQUIRED_COVERAGE_END:
        for hh, mm in ((0, 0), (9, 30), (14, 0), (15, 29), (15, 31), (23, 59)):
            ts = dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=ET)
            rec = cot_asof(ts, contract_code, data_dir)
            if rec is None:
                continue
            pub = dt.datetime.fromisoformat(rec["publication_ts"])
            if not (pub < ts):
                probe_violations.append((ts.isoformat(), rec["report_date"]))
            if dt.date.fromisoformat(rec["report_date"]) >= day and hh < 23:
                probe_violations.append(("report_date_not_past", ts.isoformat()))
        day += dt.timedelta(days=1)

    report["blind_wall_violations"] = len(violations) + len(probe_violations)
    report["blind_wall_detail"] = (violations + probe_violations)[:20]

    # -- coverage: every expected weekly report date present, gaps named
    in_window = [r for r in rows
                 if REQUIRED_COVERAGE_START <= dt.date.fromisoformat(r["report_date"])
                 <= REQUIRED_COVERAGE_END]
    dates = [dt.date.fromisoformat(r["report_date"]) for r in in_window]
    gaps = []
    for a, b in zip(dates, dates[1:]):
        step = (b - a).days
        if step != 7:
            gaps.append({"after": a.isoformat(), "next": b.isoformat(), "gap_days": step})
    report["coverage_start"] = dates[0].isoformat() if dates else None
    report["coverage_end"] = dates[-1].isoformat() if dates else None
    report["n_reports_in_window"] = len(dates)
    report["gaps"] = gaps

    # -- missing / zero discipline: name every field that is None, per date
    missing = []
    for r in in_window:
        for k in ("open_interest", "managed_money_long", "managed_money_short",
                  "managed_money_net", "producer_merchant_net", "swap_dealer_net",
                  "other_reportable_net", "managed_money_net_chg_wow",
                  "managed_money_net_pctile_1y", "managed_money_net_pctile_3y"):
            if r.get(k) is None:
                missing.append({"report_date": r["report_date"], "field": k})
    report["missing_fields"] = missing

    report["delayed_publications"] = [
        {"report_date": r["report_date"], "publication_ts": r["publication_ts"],
         "lag_days": (dt.datetime.fromisoformat(r["publication_ts"]).date()
                      - dt.date.fromisoformat(r["report_date"])).days,
         "confidence": r["publication_confidence"]}
        for r in in_window if r["publication_delayed"]
    ]
    report["publication_confidence_counts"] = {
        c: sum(1 for r in in_window if r["publication_confidence"] == c)
        for c in sorted({r["publication_confidence"] for r in in_window})
    }
    report["unreliable_publication_dates_all_history"] = [
        r["report_date"] for r in rows
        if r["publication_confidence"] == "derived_unreliable"
    ]
    report["full_history_start"] = rows[0]["report_date"]
    report["full_history_end"] = rows[-1]["report_date"]
    report["n_reports_total"] = len(rows)

    if verbose:
        print(json.dumps(report, indent=1))
    return report


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

# The CFTC published 2026 release schedule, transcribed from
# https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm
# Asterisked entries are the CFTC's own holiday-delay markers.
_CFTC_2026_SCHEDULE = {
    1: [5, 9, 16, 23, 30], 2: [6, 13, 20, 27], 3: [6, 13, 20, 27],
    4: [3, 10, 17, 24], 5: [1, 8, 15, 22, 29], 6: [5, 12, 22, 26],
    7: [6, 10, 17, 24, 31], 8: [7, 14, 21, 28], 9: [4, 11, 18, 25],
    10: [2, 9, 16, 23, 30], 11: [6, 16, 20, 30], 12: [4, 11, 18, 28],
}
_CFTC_2026_DELAYED = {
    dt.date(2026, 1, 5), dt.date(2026, 6, 22), dt.date(2026, 7, 6),
    dt.date(2026, 11, 16), dt.date(2026, 11, 30), dt.date(2026, 12, 28),
}


def _selftest_publication_rule() -> None:
    """Derived publication dates must reproduce the CFTC's published schedule."""
    published = sorted(dt.date(2026, m, d) for m, days in _CFTC_2026_SCHEDULE.items()
                       for d in days)
    # Walk the Tuesdays whose nominal release lands in 2026.
    derived = {}
    d = dt.date(2025, 12, 1)
    while d <= dt.date(2026, 12, 31):
        if d.weekday() == 1:  # Tuesday
            ts, delayed, _ = publication_datetime(d)
            if ts.year == 2026:
                derived[ts.date()] = delayed
        d += dt.timedelta(days=1)

    derived_dates = sorted(derived)
    assert derived_dates == published, (
        "publication rule diverged from the CFTC 2026 schedule.\n"
        "  only derived:   %s\n  only published: %s"
        % (sorted(set(derived_dates) - set(published)),
           sorted(set(published) - set(derived_dates)))
    )
    got_delayed = {k for k, v in derived.items() if v}
    assert got_delayed == _CFTC_2026_DELAYED, (
        "delay flags diverged: derived %s vs published %s"
        % (sorted(got_delayed), sorted(_CFTC_2026_DELAYED))
    )
    assert ts.hour == 15 and ts.minute == 30
    print("PASS publication rule reproduces the CFTC 2026 schedule "
          "(%d dates, %d delays)" % (len(published), len(_CFTC_2026_DELAYED)))


def _selftest_missing_never_zero() -> None:
    assert _to_int("") is None
    assert _to_int(".") is None
    assert _to_int("  ") is None
    assert _to_int(None) is None
    assert _to_int("junk") is None
    assert _to_int("0") == 0
    assert _to_int("1,234") == 1234
    assert _to_int("-5") == -5
    print("PASS missing parses to None, never 0")


def _selftest_percentile() -> None:
    assert _percentile_of(5, [1, 2, 3, 4, 5]) == 90.0
    assert _percentile_of(1, [1, 2, 3, 4, 5]) == 10.0
    assert _percentile_of(7, [7, 7, 7, 7]) == 50.0
    print("PASS percentile convention")


def _selftest_enrich_windows() -> None:
    """Percentiles must be None until the trailing window has real depth, and
    must never see a future observation."""
    base = dt.date(2020, 1, 7)
    rows = []
    for i in range(200):
        rows.append({
            "report_date": (base + dt.timedelta(days=7 * i)).isoformat(),
            "managed_money_net": i,
            "publication_ts": publication_datetime(
                base + dt.timedelta(days=7 * i))[0].isoformat(),
        })
    e = enrich(rows)
    assert e[0]["managed_money_net_pctile_1y"] is None
    assert e[0]["managed_money_net_chg_wow"] is None
    assert e[10]["managed_money_net_pctile_1y"] is None, "1y fired on a thin window"
    assert e[60]["managed_money_net_pctile_1y"] is not None
    assert e[60]["managed_money_net_pctile_3y"] is None, "3y fired on a thin window"
    assert e[160]["managed_money_net_pctile_3y"] is not None
    assert e[60]["managed_money_net_chg_wow"] == 1
    # strictly increasing series -> every value is the top of its trailing window
    assert e[60]["managed_money_net_pctile_1y"] > 99.0
    print("PASS trailing windows are real, not truncated, and carry no future data")


def _selftest_shutdown_overrides() -> None:
    """The 2025 appropriations-lapse catch-up must beat the normal rule.

    Without the override table these reports would appear visible weeks early:
    e.g. report 2025-09-30 would look public on 2025-10-03 when it did not
    actually exist until 2025-11-19 -- a 47-day leak.
    """
    for rd_s, expect_s in PUBLICATION_OVERRIDES.items():
        rd = dt.date.fromisoformat(rd_s)
        ts, _, conf = publication_datetime(rd)
        assert conf == "published_schedule"
        assert ts.date() >= dt.date.fromisoformat(expect_s), (
            "override advanced visibility for %s" % rd_s)
        derived, _ = _derived_publication(rd)
        assert ts >= derived, "override must never precede the derived date"

    # the specific worst case
    ts, _, _ = publication_datetime(dt.date(2025, 9, 30))
    assert ts.date() == dt.date(2025, 11, 19)
    naive, _ = _derived_publication(dt.date(2025, 9, 30))
    assert (ts.date() - naive.date()).days == 47

    # normal cadence resumes at report 2025-12-30 -> 2026-01-05, matching the
    # CFTC published 2026 schedule
    ts, delayed, conf = publication_datetime(dt.date(2025, 12, 30))
    assert ts.date() == dt.date(2026, 1, 5) and delayed and conf == "derived"
    print("PASS 2025 shutdown overrides applied (%d reports, worst leak averted "
          "= 47 days)" % len(PUBLICATION_OVERRIDES))


def _selftest_blind_wall_synthetic() -> None:
    """A Tuesday report must be invisible Wed/Thu and until Friday 15:30 ET."""
    rd = dt.date(2026, 1, 13)          # a Tuesday
    pub, delayed, conf = publication_datetime(rd)
    assert not delayed and conf == "derived"
    assert pub.date() == dt.date(2026, 1, 16)  # Friday
    for probe, visible in (
        (dt.datetime(2026, 1, 13, 23, 59, tzinfo=ET), False),
        (dt.datetime(2026, 1, 14, 12, 0, tzinfo=ET), False),  # Wednesday
        (dt.datetime(2026, 1, 15, 23, 0, tzinfo=ET), False),  # Thursday
        (dt.datetime(2026, 1, 16, 15, 29, tzinfo=ET), False),
        (dt.datetime(2026, 1, 16, 15, 30, tzinfo=ET), False),  # strict inequality
        (dt.datetime(2026, 1, 16, 15, 31, tzinfo=ET), True),
    ):
        assert (pub < probe) == visible, ("blind wall broken at %s" % probe)
    print("PASS blind wall: Tuesday report invisible until Friday 15:30 ET")


def _selftest_live_store(data_dir: str, contract_code: str) -> None:
    try:
        store = load_store(data_dir, contract_code)
    except FileNotFoundError as exc:
        print("SKIP live-store tests: %s" % exc)
        return

    rows = store["reports"]
    assert all(r["contract_code"] == contract_code for r in rows)

    # asof never returns a report published at/after the decision moment
    bad = 0
    d = REQUIRED_COVERAGE_START
    while d <= REQUIRED_COVERAGE_END:
        ts = dt.datetime(d.year, d.month, d.day, 9, 30, tzinfo=ET)
        rec = cot_asof(ts, contract_code, data_dir)
        if rec is not None:
            if not (dt.datetime.fromisoformat(rec["publication_ts"]) < ts):
                bad += 1
        d += dt.timedelta(days=1)
    assert bad == 0, "%d blind-wall violations in live store" % bad

    # a Wednesday must NOT see that week's Tuesday report
    wed = dt.datetime(2026, 1, 14, 9, 30, tzinfo=ET)
    rec = cot_asof(wed, contract_code, data_dir)
    if rec is not None:
        assert dt.date.fromisoformat(rec["report_date"]) < dt.date(2026, 1, 13), (
            "Wednesday leaked the same-week Tuesday report: %s" % rec["report_date"]
        )

    # during the 2025 lapse, no shutdown-era report may be visible on the date
    # it would have been published under the normal rule
    for rd_s, actual_s in PUBLICATION_OVERRIDES.items():
        naive, _ = _derived_publication(dt.date.fromisoformat(rd_s))
        actual, _, _ = publication_datetime(dt.date.fromisoformat(rd_s))
        if actual <= naive:
            continue  # override matched the normal rule; nothing to leak
        probe = naive + dt.timedelta(minutes=1)
        rec = cot_asof(probe, contract_code, data_dir)
        if rec is not None:
            assert dt.date.fromisoformat(rec["report_date"]) < dt.date.fromisoformat(rd_s), (
                "shutdown-era report %s leaked at %s" % (rd_s, probe)
            )

    # nothing is silently zeroed
    for r in rows:
        for k in ("managed_money_long", "managed_money_short"):
            assert r[k] is None or isinstance(r[k], int)

    print("PASS live store: %d reports %s..%s, 0 blind-wall violations"
          % (len(rows), rows[0]["report_date"], rows[-1]["report_date"]))


def selftest(data_dir: str = DEFAULT_DATA_DIR,
             contract_code: str = NG_CONTRACT_CODE) -> None:
    _selftest_publication_rule()
    _selftest_missing_never_zero()
    _selftest_percentile()
    _selftest_enrich_windows()
    _selftest_shutdown_overrides()
    _selftest_blind_wall_synthetic()
    _selftest_live_store(data_dir, contract_code)
    print("ALL SELFTESTS PASSED")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--build", action="store_true", help="download archives + build store")
    p.add_argument("--force", action="store_true", help="re-download archives")
    p.add_argument("--audit", action="store_true", help="blind-wall + coverage audit")
    p.add_argument("--selftest", action="store_true", help="run self-tests")
    p.add_argument("--asof", metavar="TS", help="inspect one decision date/datetime")
    p.add_argument("--contract", default=NG_CONTRACT_CODE)
    p.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    p.add_argument("--list-ng-codes", action="store_true",
                   help="list every natural-gas market code found in the archives")
    a = p.parse_args(argv)

    if a.build:
        # S114: with no explicit --contract, build EVERY served code (see
        # SERVED_CONTRACT_CODES). An explicit --contract still builds exactly that one.
        codes = ([a.contract] if a.contract != NG_CONTRACT_CODE
                 else list(SERVED_CONTRACT_CODES))
        for i, code in enumerate(codes):
            # archives are downloaded once; only the first pass may re-download
            store = build(a.data_dir, code, force=(a.force and i == 0))
            print("built %d reports for %s (%s) -> %s"
                  % (store["n_reports"], code, ", ".join(store["market_names"]),
                     store_path(a.data_dir, code)))
    if a.list_ng_codes:
        paths = download_archives(a.data_dir, BUILD_YEARS)
        found = {}
        for path in sorted(paths):
            with zipfile.ZipFile(path) as z:
                for name in z.namelist():
                    if not name.lower().endswith(".txt"):
                        continue
                    with z.open(name) as fh:
                        rd = csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8",
                                                             errors="replace", newline=""))
                        for row in rd:
                            n = row.get("Market_and_Exchange_Names", "")
                            if "NAT GAS" in n.upper() or "NATURAL GAS" in n.upper():
                                found[row["CFTC_Contract_Market_Code"].strip()] = n.strip()
        for code in sorted(found):
            print(code, "|", found[code])
    if a.audit:
        audit(a.data_dir, a.contract)
    if a.selftest:
        selftest(a.data_dir, a.contract)
    if a.asof:
        rec = cot_asof(a.asof, a.contract, a.data_dir)
        print(json.dumps(rec, indent=1) if rec else
              "None  (no COT report published before %s -- UNKNOWN, not flat)" % a.asof)
    if not any([a.build, a.audit, a.selftest, a.asof, a.list_ng_codes]):
        p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
