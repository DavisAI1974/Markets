"""CFTC COT FUTURES-AND-OPTIONS COMBINED positioning feed (DATA_GATE_S98 feed H).

WHAT THIS IS
------------
An INPUT, not a thesis (family P). The S97 `cot_feed.py` build is FUTURES-ONLY;
options positioning is a separate picture, and expiry-week mechanics (G13, the
squeeze test carrying the Feb 25 2026 opex/expiry pair) are exactly where the
two diverge: a crowd that looks moderate in futures can be violently short via
options. The G11 squeeze (NGG26 3.0 -> 7.460 settle) is the standing motivating
instance. This module supplies the combined view PLUS the derived options-only
read (combined minus futures-only); the agent decides what it means. Nothing
here gates, scores, or recommends.

SOURCE
------
CFTC Disaggregated Commitments of Traders, FUTURES-AND-OPTIONS COMBINED report.
Annual compressed archives, comma-delimited text:

    https://www.cftc.gov/files/dea/history/com_disagg_txt_<YEAR>.zip

Each zip contains a single `c_year.txt` (the futures-only variant that
`cot_feed.py` pulls is `fut_disagg_txt_<YEAR>.zip` / `f_year.txt`). Verified
2026-07-20: identical 191-column layout, all twelve columns this feed needs
present under the same names as the futures-only file. Contract identity
verified: `023651` = "NAT GAS NYME - NEW YORK MERCANTILE EXCHANGE".

DOWNLOAD NOTE (2026-07-20): cftc.gov returns HTTP 403 for python's default
User-Agent on BOTH variants. This downloader sends a browser User-Agent.
(`cot_feed.py`'s downloader predates the block; its raw zips are already on
disk. That module is deliberately NOT edited by this build.)

WHAT "COMBINED" MEANS
---------------------
Options positions are converted by the CFTC into futures-equivalents using each
option's risk factor (delta) and added to the futures positions. So for every
field: combined = futures + delta-adjusted options. All `*_combined` fields in
this store are in futures-equivalent contracts, directly comparable to the
futures-only fields.

THE DERIVED OPTIONS-IMPLIED READ (the point of this feed)
---------------------------------------------------------
    <field>_options_implied = <field>_combined - <field>   (futures-only)

computed AT READ TIME inside `cot_combined_asof` against the futures-only store
`data/cot/ng_cot_023651.json` (READ-ONLY; this module never writes it), always
on the SAME report_date on both sides -- never across vintages. Where either
side is missing (date absent from the futures store, or either field None) the
derived value is None, never 0.

Percentile discipline for the derived read: the 1y/3y percentiles are computed
OF the options-implied series itself (trailing window ending at the report
date, same minimum-observation bars as cot_feed). Differencing the two sides'
percentiles would NOT be an options-implied percentile -- the two rank spaces
are different -- so that is deliberately not done.

THE BLIND WALL
--------------
Identical to `cot_feed.py`, and deliberately IMPORTED from it rather than
re-derived: all COT variants (futures-only and combined) are released together
Friday 15:30 ET for Tuesday positions. Publication rule = first Friday strictly
after report_date at 15:30 ET, pushed one business day per US federal holiday,
validated against the CFTC published 2026 schedule; PLUS the 2025
appropriations-lapse catch-up table (`cot_feed.PUBLICATION_OVERRIDES`) -- the
naive Friday rule across the Oct 1 - Nov 12 2025 suspension would have leaked
47 days of future positioning. Every lookup keys on publication_ts with a
STRICT inequality.

MISSING IS EXPLICIT
-------------------
Absent values are None, never 0. `cot_combined_asof` returns None when no
combined report was public yet -- unknown, NOT flat.

PUBLIC API
----------
    cot_combined_asof(date, contract_code="023651",
                      data_dir=None, futures_data_dir=None) -> dict | None

        date : datetime.date | datetime.datetime | str -- same contract as
               cot_feed.cot_asof (naive = ET; plain date = 00:00 ET that day,
               the conservative reading).

        Returned keys (ALL suffixed so the orchestrator can merge additively
        into cot_asof output with zero collisions):

        record metadata (suffixed at return time):
          report_date_combined           str  YYYY-MM-DD (Tuesday as-of date)
          publication_ts_combined        str  ISO8601 tz-aware ET
          publication_delayed_combined   bool
          publication_confidence_combined str ("published_schedule" |
                                              "derived" | "derived_unreliable")
          age_days_combined              float
          contract_code_combined         str
          market_name_combined           str

        combined positioning (futures + delta-adjusted options):
          open_interest_combined                 int | None
          managed_money_long_combined            int | None
          managed_money_short_combined           int | None
          managed_money_net_combined             int | None
          managed_money_net_chg_wow_combined     int | None
          producer_merchant_net_combined         int | None
          swap_dealer_net_combined               int | None
          other_reportable_net_combined          int | None
          managed_money_net_pctile_1y_combined   float | None  0-100
          managed_money_net_pctile_3y_combined   float | None  0-100
          pctile_1y_n_obs_combined               int
          pctile_3y_n_obs_combined               int

        derived options-implied (combined minus futures-only, same report_date;
        None where either side is missing):
          open_interest_options_implied          int | None
          managed_money_long_options_implied     int | None
          managed_money_short_options_implied    int | None
          managed_money_net_options_implied      int | None
          managed_money_net_chg_wow_options_implied  int | None
          producer_merchant_net_options_implied  int | None
          swap_dealer_net_options_implied        int | None
          other_reportable_net_options_implied   int | None
          managed_money_net_options_implied_pctile_1y  float | None
          managed_money_net_options_implied_pctile_3y  float | None
          options_implied_pctile_1y_n_obs        int
          options_implied_pctile_3y_n_obs        int

KNOWN LIMIT (carried forward from S97, still open)
--------------------------------------------------
ICE Henry Hub positioning remains OUT: the ICE LD1/penultimate contracts
(023391/023392) are a separate positioning picture on a different exchange and
there is no free historical source for ICE commitments data. This feed closes
the OPTIONS half of COT limit #9 only.

CLI
---
    python cot_combined_feed.py --build            # download + build the store
    python cot_combined_feed.py --audit            # blind wall + coverage + OI cross-check
    python cot_combined_feed.py --selftest         # self-tests (0 violations required)
    python cot_combined_feed.py --asof 2026-01-19  # inspect one decision date
    python cot_combined_feed.py --divergence 2025-11-01 2026-02-28
                                                   # factual per-week fut-vs-combined table
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
import zipfile
from typing import Any, Dict, List, Optional, Sequence

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# The single source of truth for the publication machinery. Imported, never
# copied: the Friday-15:30-ET rule, the US-federal-holiday delays, the 2025
# shutdown catch-up overrides, and the decision-time coercion all live in
# cot_feed and are reused verbatim. This module NEVER writes cot_feed's store.
import cot_feed
from cot_feed import (
    ET,
    MIN_OBS_1Y,
    MIN_OBS_3Y,
    NG_CONTRACT_CODE,
    NG_MARKET_NAME_EXPECTED,
    REQUIRED_COVERAGE_END,
    REQUIRED_COVERAGE_START,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COMBINED_ARCHIVE_URL = "https://www.cftc.gov/files/dea/history/com_disagg_txt_{year}.zip"

# cftc.gov 403s python's default User-Agent (observed 2026-07-20, both report
# variants). A plain browser UA is accepted.
DOWNLOAD_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

_REPO = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
DEFAULT_DATA_DIR = os.path.join(_REPO, "data", "cot_combined")
RAW_SUBDIR = "raw"
STORE_NAME = "ng_cot_combined_{code}.json"

# Same year span as the futures-only store (data/cot: 2019..current year).
BUILD_YEARS = cot_feed.BUILD_YEARS

# Store-row metadata keys that stay natural inside the store and are suffixed
# only in the asof return.
_META_KEYS = (
    "report_date",
    "publication_ts",
    "publication_delayed",
    "publication_confidence",
    "contract_code",
    "market_name",
)

# The positioning level fields the derived options-implied read differences.
_DIFF_BASE_FIELDS = (
    "open_interest",
    "managed_money_long",
    "managed_money_short",
    "managed_money_net",
    "producer_merchant_net",
    "swap_dealer_net",
    "other_reportable_net",
)

_DERIVED_KEYS = tuple(f + "_options_implied" for f in _DIFF_BASE_FIELDS) + (
    "managed_money_net_chg_wow_options_implied",
    "managed_money_net_options_implied_pctile_1y",
    "managed_money_net_options_implied_pctile_3y",
    "options_implied_pctile_1y_n_obs",
    "options_implied_pctile_3y_n_obs",
)


# ---------------------------------------------------------------------------
# Fetch (combined variant; UA-carrying)
# ---------------------------------------------------------------------------

def _raw_dir(data_dir: str) -> str:
    return os.path.join(data_dir, RAW_SUBDIR)


def download_archives(data_dir: str, years: Sequence[int], force: bool = False) -> List[str]:
    raw = _raw_dir(data_dir)
    os.makedirs(raw, exist_ok=True)
    paths = []
    for year in years:
        dest = os.path.join(raw, "com_disagg_txt_%d.zip" % year)
        if os.path.exists(dest) and not force and os.path.getsize(dest) > 1000:
            paths.append(dest)
            continue
        url = COMBINED_ARCHIVE_URL.format(year=year)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": DOWNLOAD_USER_AGENT})
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


# ---------------------------------------------------------------------------
# Store build. Parsing + enrichment REUSE cot_feed's machinery verbatim
# (identical column names verified 2026-07-20); field names are then suffixed
# `_combined` so the two stores can never be confused for one another.
# ---------------------------------------------------------------------------

def _suffix_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Suffix every non-metadata key with `_combined`."""
    return {
        (k if k in _META_KEYS else k + "_combined"): v
        for k, v in row.items()
    }


def store_path(data_dir: str, contract_code: str) -> str:
    return os.path.join(data_dir, STORE_NAME.format(code=contract_code))


def build(data_dir: str = DEFAULT_DATA_DIR,
          contract_code: str = NG_CONTRACT_CODE,
          years: Sequence[int] = BUILD_YEARS,
          force: bool = False) -> Dict[str, Any]:
    os.makedirs(data_dir, exist_ok=True)
    paths = download_archives(data_dir, years, force=force)
    # cot_feed.parse_archives: same 12 required columns, same contract filter,
    # same FATAL-on-format-drift, same publication_datetime (overrides incl.).
    rows = cot_feed.parse_archives(paths, contract_code)
    if not rows:
        raise SystemExit(
            "FATAL: contract code %s produced no rows in the COMBINED archives. "
            "Verify the code; stopping rather than substituting another contract."
            % contract_code
        )
    names = sorted({r["market_name"] for r in rows})
    if contract_code == NG_CONTRACT_CODE and NG_MARKET_NAME_EXPECTED not in names:
        raise SystemExit(
            "FATAL: code %s no longer maps to %r in the combined archive "
            "(found %s). Stopping." % (contract_code, NG_MARKET_NAME_EXPECTED, names)
        )
    rows = cot_feed.enrich(rows)          # wow change + 1y/3y percentiles
    rows = [_suffix_row(r) for r in rows]
    store = {
        "source": "CFTC Disaggregated Commitments of Traders, futures-and-options combined",
        "source_url_pattern": COMBINED_ARCHIVE_URL,
        "field_semantics": (
            "*_combined = futures positions PLUS delta-adjusted options "
            "positions (futures-equivalent contracts). Directly comparable to "
            "the futures-only fields in data/cot; combined minus futures-only "
            "= the options-implied read, computed at read time by "
            "cot_combined_asof, never stored."
        ),
        "contract_code": contract_code,
        "market_names": names,
        "built_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "years": list(years),
        "publication_rule": (
            "identical to cot_feed (imported, not re-derived): first Friday "
            "strictly after report_date at 15:30 ET, delayed one business day "
            "per US federal holiday in (report_date, nominal_friday]; 2025 "
            "appropriations-lapse catch-up overrides applied; validated "
            "against the CFTC published 2026 release schedule"
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
                "combined COT store not built: %s. Run "
                "`python cot_combined_feed.py --build`." % path
            )
        with open(path, encoding="utf-8") as f:
            _STORE_CACHE[path] = json.load(f)
    return _STORE_CACHE[path]


# ---------------------------------------------------------------------------
# The derived options-implied series (combined minus futures-only)
# ---------------------------------------------------------------------------

def options_implied_series(combined_rows: List[Dict[str, Any]],
                           futures_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per combined report date: combined minus futures-only, same report_date.

    Pure function of the two stores' report lists (combined rows carry
    `_combined`-suffixed fields, futures rows carry the natural names). For
    each level field the diff is None unless BOTH sides are present. On top of
    the diffs: week-over-week change of the managed-money net diff (adjacent
    combined report dates, 5-10 day gap, both diffs present) and trailing
    1y/3y percentiles OF the diff series (window ending at the report date,
    cot_feed's minimum-observation bars; never a difference of percentiles).
    """
    fut_by_date = {r["report_date"]: r for r in futures_rows}
    out: List[Dict[str, Any]] = []
    for c in combined_rows:
        f = fut_by_date.get(c["report_date"])
        d: Dict[str, Any] = {"report_date": c["report_date"]}
        for k in _DIFF_BASE_FIELDS:
            cv = c.get(k + "_combined")
            fv = None if f is None else f.get(k)
            d[k + "_options_implied"] = None if (cv is None or fv is None) else cv - fv
        out.append(d)

    for i, d in enumerate(out):
        rd = dt.date.fromisoformat(d["report_date"])
        v = d["managed_money_net_options_implied"]

        chg = None
        if i > 0 and v is not None:
            prev = out[i - 1]
            pv = prev["managed_money_net_options_implied"]
            gap = (rd - dt.date.fromisoformat(prev["report_date"])).days
            if pv is not None and 5 <= gap <= 10:
                chg = v - pv
        d["managed_money_net_chg_wow_options_implied"] = chg

        for label, days, min_obs in (("1y", 365, MIN_OBS_1Y), ("3y", 1095, MIN_OBS_3Y)):
            key = "managed_money_net_options_implied_pctile_%s" % label
            nkey = "options_implied_pctile_%s_n_obs" % label
            if v is None:
                d[key] = None
                d[nkey] = 0
                continue
            start = rd - dt.timedelta(days=days)
            window = [
                out[j]["managed_money_net_options_implied"]
                for j in range(0, i + 1)
                if out[j]["managed_money_net_options_implied"] is not None
                and start <= dt.date.fromisoformat(out[j]["report_date"]) <= rd
            ]
            d[nkey] = len(window)
            d[key] = (round(cot_feed._percentile_of(v, window), 2)
                      if len(window) >= min_obs else None)
    return out


_JOINED_CACHE: Dict[tuple, Dict[str, Dict[str, Any]]] = {}


def _joined(data_dir: str, futures_data_dir: str,
            contract_code: str) -> Dict[str, Dict[str, Any]]:
    key = (os.path.abspath(data_dir), os.path.abspath(futures_data_dir), contract_code)
    if key not in _JOINED_CACHE:
        combined = load_store(data_dir, contract_code)["reports"]
        try:
            # READ-ONLY view of the futures-only store; never written here.
            futures = cot_feed.load_store(futures_data_dir, contract_code)["reports"]
        except FileNotFoundError:
            # The futures side is entirely missing: every derived value is
            # None (explicitly missing), the combined fields still serve.
            futures = []
        series = options_implied_series(combined, futures)
        _JOINED_CACHE[key] = {r["report_date"]: r for r in series}
    return _JOINED_CACHE[key]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def cot_combined_asof(date: Any,
                      contract_code: str = NG_CONTRACT_CODE,
                      data_dir: str = DEFAULT_DATA_DIR,
                      futures_data_dir: str = cot_feed.DEFAULT_DATA_DIR
                      ) -> Optional[Dict[str, Any]]:
    """Latest COMBINED COT report PUBLISHED strictly before the decision moment.

    Returns None when no combined report was public yet -- UNKNOWN, not flat.
    See the module docstring for the full key contract. All keys are suffixed
    (`*_combined` / `*_options_implied`) so the dict merges additively into
    cot_feed.cot_asof output with zero collisions.
    """
    decision = cot_feed._coerce_decision_ts(date)
    store = load_store(data_dir, contract_code)

    # Full scan, no early break: publication order is NOT guaranteed to follow
    # report-date order once catch-up overrides are in play (same reasoning as
    # cot_feed.cot_asof).
    latest = None
    for r in store["reports"]:
        pub = dt.datetime.fromisoformat(r["publication_ts"])
        if pub < decision:            # STRICT: the blind wall
            if latest is None or r["report_date"] > latest[0]["report_date"]:
                latest = (r, pub)

    if latest is None:
        return None

    row, pub = latest
    out: Dict[str, Any] = {}
    for k, v in row.items():
        out[(k + "_combined") if k in _META_KEYS else k] = v
    out["age_days_combined"] = round((decision - pub).total_seconds() / 86400.0, 4)

    derived = _joined(data_dir, futures_data_dir, contract_code).get(row["report_date"])
    if derived is None:  # cannot happen for a store-resident date; belt+braces
        for k in _DERIVED_KEYS:
            out[k] = None if not k.endswith("_n_obs") else 0
    else:
        for k, v in derived.items():
            if k != "report_date":
                out[k] = v
    return out


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def audit(data_dir: str = DEFAULT_DATA_DIR,
          contract_code: str = NG_CONTRACT_CODE,
          futures_data_dir: str = cot_feed.DEFAULT_DATA_DIR,
          verbose: bool = True) -> Dict[str, Any]:
    store = load_store(data_dir, contract_code)
    rows = store["reports"]
    report: Dict[str, Any] = {}

    # -- blind wall: publication strictly after report date, sane lag
    violations = []
    for r in rows:
        rd = dt.date.fromisoformat(r["report_date"])
        pub = dt.datetime.fromisoformat(r["publication_ts"])
        if pub.date() <= rd:
            violations.append(("publication_not_after_report", r["report_date"]))
        if (pub.date() - rd).days < 3:
            violations.append(("publication_lag_under_3_days", r["report_date"]))

    # exhaustive probe walk over the coverage window at several decision times
    probe_violations = []
    day = REQUIRED_COVERAGE_START
    while day <= REQUIRED_COVERAGE_END:
        for hh, mm in ((0, 0), (9, 30), (14, 0), (15, 29), (15, 31), (23, 59)):
            ts = dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=ET)
            rec = cot_combined_asof(ts, contract_code, data_dir, futures_data_dir)
            if rec is None:
                continue
            pub = dt.datetime.fromisoformat(rec["publication_ts_combined"])
            if not (pub < ts):
                probe_violations.append((ts.isoformat(), rec["report_date_combined"]))
            if dt.date.fromisoformat(rec["report_date_combined"]) >= day and hh < 23:
                probe_violations.append(("report_date_not_past", ts.isoformat()))
        day += dt.timedelta(days=1)

    report["blind_wall_violations"] = len(violations) + len(probe_violations)
    report["blind_wall_detail"] = (violations + probe_violations)[:20]

    # -- coverage in the required window, cadence anomalies named
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

    # -- missing / zero discipline, per date per field
    missing = []
    for r in in_window:
        for k in ("open_interest_combined", "managed_money_long_combined",
                  "managed_money_short_combined", "managed_money_net_combined",
                  "producer_merchant_net_combined", "swap_dealer_net_combined",
                  "other_reportable_net_combined", "managed_money_net_chg_wow_combined",
                  "managed_money_net_pctile_1y_combined",
                  "managed_money_net_pctile_3y_combined"):
            if r.get(k) is None:
                missing.append({"report_date": r["report_date"], "field": k})
    report["missing_fields"] = missing

    # -- cross-store checks against the futures-only store (READ-ONLY)
    try:
        fut_rows = cot_feed.load_store(futures_data_dir, contract_code)["reports"]
    except FileNotFoundError as exc:
        fut_rows = None
        report["futures_store"] = "MISSING (%s) - derived read all-None" % exc

    if fut_rows is not None:
        fut_by_date = {r["report_date"]: r for r in fut_rows}
        comb_dates = {r["report_date"] for r in rows}

        # OI cross-check: combined must be >= futures-only on every overlapping
        # report date (options add non-negative delta-adjusted OI). A violation
        # would indicate a file/contract mismatch and is NAMED, never dropped.
        oi_violations = []
        n_overlap = 0
        for r in rows:
            f = fut_by_date.get(r["report_date"])
            if f is None:
                continue
            co, fo = r.get("open_interest_combined"), f.get("open_interest")
            if co is None or fo is None:
                continue
            n_overlap += 1
            if co < fo:
                oi_violations.append({"report_date": r["report_date"],
                                      "combined_oi": co, "futures_oi": fo})
        report["oi_crosscheck_n_overlapping"] = n_overlap
        report["oi_crosscheck_violations"] = oi_violations

        # publication timestamps must be identical on shared report dates
        # (all COT variants are released together)
        pub_mismatch = [
            {"report_date": r["report_date"],
             "combined": r["publication_ts"],
             "futures": fut_by_date[r["report_date"]]["publication_ts"]}
            for r in rows
            if r["report_date"] in fut_by_date
            and r["publication_ts"] != fut_by_date[r["report_date"]]["publication_ts"]
        ]
        report["publication_ts_mismatches"] = pub_mismatch

        # overlap gaps, named per date, both directions
        report["combined_dates_missing_from_futures_store"] = sorted(
            d for d in comb_dates if d not in fut_by_date)
        report["futures_dates_missing_from_combined_store"] = sorted(
            d for d in fut_by_date if d not in comb_dates)

        joined = _joined(data_dir, futures_data_dir, contract_code)
        report["derived_read_computable_dates"] = sum(
            1 for v in joined.values()
            if v["managed_money_net_options_implied"] is not None)

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
    report["full_history_start"] = rows[0]["report_date"]
    report["full_history_end"] = rows[-1]["report_date"]
    report["n_reports_total"] = len(rows)

    if verbose:
        print(json.dumps(report, indent=1))
    return report


# ---------------------------------------------------------------------------
# Divergence table (factual; used for COT_COMBINED_NOTES_S98.md)
# ---------------------------------------------------------------------------

def divergence_table(start: str, end: str,
                     data_dir: str = DEFAULT_DATA_DIR,
                     contract_code: str = NG_CONTRACT_CODE,
                     futures_data_dir: str = cot_feed.DEFAULT_DATA_DIR
                     ) -> List[Dict[str, Any]]:
    """Per report week in [start, end]: futures vs combined, plus the diff.

    Facts only -- no interpretation. Percentiles shown are each side's own
    trailing-1y rank of its own managed-money net.
    """
    lo, hi = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    comb = load_store(data_dir, contract_code)["reports"]
    fut_by_date = {r["report_date"]: r
                   for r in cot_feed.load_store(futures_data_dir, contract_code)["reports"]}
    joined = _joined(data_dir, futures_data_dir, contract_code)
    out = []
    for r in comb:
        rd = dt.date.fromisoformat(r["report_date"])
        if not (lo <= rd <= hi):
            continue
        f = fut_by_date.get(r["report_date"])
        j = joined[r["report_date"]]
        out.append({
            "report_date": r["report_date"],
            "published": dt.datetime.fromisoformat(r["publication_ts"]).date().isoformat(),
            "mm_net_futures": None if f is None else f.get("managed_money_net"),
            "mm_net_combined": r.get("managed_money_net_combined"),
            "mm_net_options_implied": j["managed_money_net_options_implied"],
            "mm_net_pctile_1y_futures": None if f is None else f.get("managed_money_net_pctile_1y"),
            "mm_net_pctile_1y_combined": r.get("managed_money_net_pctile_1y_combined"),
            "oi_futures": None if f is None else f.get("open_interest"),
            "oi_combined": r.get("open_interest_combined"),
            "oi_options_implied": j["open_interest_options_implied"],
        })
    return out


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest_imported_machinery() -> None:
    """The blind wall is cot_feed's; prove the imported machinery is intact."""
    cot_feed._selftest_publication_rule()
    cot_feed._selftest_missing_never_zero()
    cot_feed._selftest_shutdown_overrides()
    cot_feed._selftest_blind_wall_synthetic()
    print("PASS imported cot_feed machinery intact (rule, overrides, wall)")


def _selftest_suffix_integrity() -> None:
    row = {"report_date": "2026-01-13", "publication_ts": "x",
           "publication_delayed": False, "publication_confidence": "derived",
           "contract_code": "023651", "market_name": "m",
           "open_interest": 10, "managed_money_net": -5,
           "managed_money_net_pctile_1y": None, "pctile_1y_n_obs": 3}
    s = _suffix_row(row)
    assert s["report_date"] == "2026-01-13"          # metadata untouched
    assert s["open_interest_combined"] == 10
    assert s["managed_money_net_combined"] == -5
    assert s["managed_money_net_pctile_1y_combined"] is None
    assert s["pctile_1y_n_obs_combined"] == 3
    for k in ("open_interest", "managed_money_net", "pctile_1y_n_obs"):
        assert k not in s, "unsuffixed positioning key leaked into store row: %s" % k
    print("PASS suffix integrity: positioning fields _combined, metadata natural")


def _selftest_derived_diff() -> None:
    """combined minus futures per field; None where either side missing."""
    def crow(d, oi, mm):
        return {"report_date": d, "open_interest_combined": oi,
                "managed_money_long_combined": None, "managed_money_short_combined": None,
                "managed_money_net_combined": mm, "producer_merchant_net_combined": 1,
                "swap_dealer_net_combined": 2, "other_reportable_net_combined": 3}

    def frow(d, oi, mm):
        return {"report_date": d, "open_interest": oi,
                "managed_money_long": None, "managed_money_short": 4,
                "managed_money_net": mm, "producer_merchant_net": 1,
                "swap_dealer_net": None, "other_reportable_net": 1}

    comb = [crow("2026-01-06", 1600, -100), crow("2026-01-13", 1610, -120),
            crow("2026-01-20", 1620, -90)]
    fut = [frow("2026-01-06", 1400, -80), frow("2026-01-20", 1420, -70)]
    s = options_implied_series(comb, fut)

    assert s[0]["open_interest_options_implied"] == 200
    assert s[0]["managed_money_net_options_implied"] == -20
    assert s[0]["managed_money_long_options_implied"] is None      # both sides None
    assert s[0]["producer_merchant_net_options_implied"] == 0      # 0 is a real value
    assert s[0]["swap_dealer_net_options_implied"] is None         # futures side None
    assert s[0]["managed_money_short_options_implied"] is None     # combined side None
    # 2026-01-13 absent from the futures store: every diff None, n_obs 0
    assert all(s[1][k + "_options_implied"] is None for k in _DIFF_BASE_FIELDS)
    assert s[1]["options_implied_pctile_1y_n_obs"] == 0
    # wow change needs BOTH adjacent diffs: 01-13 diff is None so 01-20 chg is None
    assert s[1]["managed_money_net_chg_wow_options_implied"] is None
    assert s[2]["managed_money_net_chg_wow_options_implied"] is None
    # percentiles gated by MIN_OBS: 2-3 obs is far under 45 -> None, n_obs real
    assert s[2]["managed_money_net_options_implied_pctile_1y"] is None
    assert s[2]["options_implied_pctile_1y_n_obs"] == 2
    # adjacent-week wow when both sides present
    comb2 = [crow("2026-01-06", 1600, -100), crow("2026-01-13", 1610, -120)]
    fut2 = [frow("2026-01-06", 1400, -80), frow("2026-01-13", 1400, -80)]
    s2 = options_implied_series(comb2, fut2)
    assert s2[1]["managed_money_net_chg_wow_options_implied"] == (-40) - (-20)
    print("PASS derived options-implied diff: per-field, None-propagating, "
          "wow gap rule, percentile min-obs gate")


def _selftest_live_store(data_dir: str, contract_code: str,
                         futures_data_dir: str) -> None:
    try:
        store = load_store(data_dir, contract_code)
    except FileNotFoundError as exc:
        print("SKIP live-store tests: %s" % exc)
        return
    rows = store["reports"]
    assert all(r["contract_code"] == contract_code for r in rows)

    # suffix integrity across the whole live store
    for r in rows:
        for k in r:
            assert k in _META_KEYS or k.endswith("_combined"), (
                "unsuffixed field %r in live store" % k)

    # blind wall: exhaustive daily probe at 09:30 ET across the coverage window
    bad = 0
    d = REQUIRED_COVERAGE_START
    while d <= REQUIRED_COVERAGE_END:
        ts = dt.datetime(d.year, d.month, d.day, 9, 30, tzinfo=ET)
        rec = cot_combined_asof(ts, contract_code, data_dir, futures_data_dir)
        if rec is not None:
            if not (dt.datetime.fromisoformat(rec["publication_ts_combined"]) < ts):
                bad += 1
        d += dt.timedelta(days=1)
    assert bad == 0, "%d blind-wall violations in live combined store" % bad

    # a Wednesday must NOT see that week's Tuesday report
    wed = dt.datetime(2026, 1, 14, 9, 30, tzinfo=ET)
    rec = cot_combined_asof(wed, contract_code, data_dir, futures_data_dir)
    if rec is not None:
        assert dt.date.fromisoformat(rec["report_date_combined"]) < dt.date(2026, 1, 13), (
            "Wednesday leaked the same-week Tuesday combined report: %s"
            % rec["report_date_combined"])

    # shutdown era: no report caught in the 2025 lapse may be visible at the
    # minute the NAIVE Friday rule would have published it
    for rd_s in cot_feed.PUBLICATION_OVERRIDES:
        naive, _ = cot_feed._derived_publication(dt.date.fromisoformat(rd_s))
        actual, _, _ = cot_feed.publication_datetime(dt.date.fromisoformat(rd_s))
        if actual <= naive:
            continue
        probe = naive + dt.timedelta(minutes=1)
        rec = cot_combined_asof(probe, contract_code, data_dir, futures_data_dir)
        if rec is not None:
            assert dt.date.fromisoformat(rec["report_date_combined"]) < dt.date.fromisoformat(rd_s), (
                "shutdown-era combined report %s leaked at %s" % (rd_s, probe))

    # cross-store: OI cross-check + identical publication stamps + derived
    # read recomputed independently on EVERY overlapping date
    try:
        fut_rows = cot_feed.load_store(futures_data_dir, contract_code)["reports"]
    except FileNotFoundError:
        print("PASS live combined store (futures store absent: derived checks skipped)")
        return
    fut_by_date = {r["report_date"]: r for r in fut_rows}
    joined = _joined(data_dir, futures_data_dir, contract_code)

    oi_viol = []
    n_overlap = 0
    for r in rows:
        f = fut_by_date.get(r["report_date"])
        if f is None:
            continue
        assert r["publication_ts"] == f["publication_ts"], (
            "publication stamp mismatch on %s (variants are released together)"
            % r["report_date"])
        co, fo = r.get("open_interest_combined"), f.get("open_interest")
        if co is not None and fo is not None:
            n_overlap += 1
            if co < fo:
                oi_viol.append((r["report_date"], co, fo))
        for k in _DIFF_BASE_FIELDS:
            cv, fv = r.get(k + "_combined"), f.get(k)
            expect = None if (cv is None or fv is None) else cv - fv
            got = joined[r["report_date"]][k + "_options_implied"]
            assert got == expect, (
                "derived mismatch %s %s: got %r expect %r"
                % (r["report_date"], k, got, expect))
    assert not oi_viol, (
        "OI cross-check FAILED (combined < futures-only -- file/contract "
        "mismatch?): %s" % oi_viol)

    # asof-level spot check: the returned derived value equals a by-hand diff
    probe_ts = dt.datetime(2026, 1, 19, 9, 30, tzinfo=ET)
    rec = cot_combined_asof(probe_ts, contract_code, data_dir, futures_data_dir)
    if rec is not None and rec["report_date_combined"] in fut_by_date:
        f = fut_by_date[rec["report_date_combined"]]
        if rec["managed_money_net_combined"] is not None and f["managed_money_net"] is not None:
            assert rec["managed_money_net_options_implied"] == (
                rec["managed_money_net_combined"] - f["managed_money_net"])

    print("PASS live combined store: %d reports %s..%s, 0 blind-wall "
          "violations, OI cross-check %d/%d overlapping dates OK, derived "
          "read verified on every overlap"
          % (len(rows), rows[0]["report_date"], rows[-1]["report_date"],
             n_overlap, n_overlap))


def selftest(data_dir: str = DEFAULT_DATA_DIR,
             contract_code: str = NG_CONTRACT_CODE,
             futures_data_dir: str = cot_feed.DEFAULT_DATA_DIR) -> None:
    _selftest_imported_machinery()
    _selftest_suffix_integrity()
    _selftest_derived_diff()
    _selftest_live_store(data_dir, contract_code, futures_data_dir)
    print("ALL SELFTESTS PASSED")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--build", action="store_true", help="download archives + build store")
    p.add_argument("--force", action="store_true", help="re-download archives")
    p.add_argument("--audit", action="store_true",
                   help="blind-wall + coverage + OI cross-check audit")
    p.add_argument("--selftest", action="store_true", help="run self-tests")
    p.add_argument("--asof", metavar="TS", help="inspect one decision date/datetime")
    p.add_argument("--divergence", nargs=2, metavar=("START", "END"),
                   help="factual per-report-week futures-vs-combined table")
    p.add_argument("--contract", default=NG_CONTRACT_CODE)
    p.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    p.add_argument("--futures-data-dir", default=cot_feed.DEFAULT_DATA_DIR,
                   help="READ-ONLY futures-only store dir (data/cot)")
    a = p.parse_args(argv)

    if a.build:
        store = build(a.data_dir, a.contract, force=a.force)
        print("built %d combined reports for %s (%s) -> %s"
              % (store["n_reports"], a.contract, ", ".join(store["market_names"]),
                 store_path(a.data_dir, a.contract)))
    if a.audit:
        audit(a.data_dir, a.contract, a.futures_data_dir)
    if a.selftest:
        selftest(a.data_dir, a.contract, a.futures_data_dir)
    if a.asof:
        rec = cot_combined_asof(a.asof, a.contract, a.data_dir, a.futures_data_dir)
        print(json.dumps(rec, indent=1) if rec else
              "None  (no combined COT report published before %s -- UNKNOWN, "
              "not flat)" % a.asof)
    if a.divergence:
        rows = divergence_table(a.divergence[0], a.divergence[1],
                                a.data_dir, a.contract, a.futures_data_dir)
        print(json.dumps(rows, indent=1))
    if not any([a.build, a.audit, a.selftest, a.asof, a.divergence]):
        p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
