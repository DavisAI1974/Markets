"""
storage_regional.py — REGIONAL NG working-gas storage as a decision-state INPUT (S97).

WHY. `decision_state` currently carries ONE national working-gas figure plus the EIA seasonal surprise.
The market does not trade the national number alone: the EIA Weekly Natural Gas Storage Report (WNGSR)
breaks working gas into five regions, and inside South Central it reports SALT and NON-SALT separately.
Salt-dome storage is the fast-cycling swing capacity — it can be injected/withdrawn in days rather than
weeks — so a salt draw/build moves short-dated NG far more than the same Bcf spread across the L48. This
module supplies that detail as an INPUT for the agent to use as it sees fit. It is NOT a thesis on trial:
nothing here gates, scores, or argues for/against using it.

ADDITIVE. This does not touch, replace, or alter the existing national `storage` fields sourced from
data/eia_surprise.json. It is a separate module writing a separate store.

SOURCE. EIA API v2, route `natural-gas/stor/wkly`, frequency=weekly, facet `series`. Eight series
(all Bcf, all covering 2010-01-01 forward):
    NW2_EPG0_SWO_R48_BCF   Lower 48 total       (national, for continuity)
    NW2_EPG0_SWO_R31_BCF   East
    NW2_EPG0_SWO_R32_BCF   Midwest
    NW2_EPG0_SWO_R33_BCF   South Central (total)
    NW2_EPG0_SSO_R33_BCF   South Central - SALT
    NW2_EPG0_SNO_R33_BCF   South Central - NON-SALT
    NW2_EPG0_SWO_R34_BCF   Mountain
    NW2_EPG0_SWO_R35_BCF   Pacific

Per report and per region/split we carry: level (Bcf), weekly change, level vs the 5-year average for the
same report week, level vs the year-ago same week, and the weekly change vs the 5-year average change.

DAYS OF SUPPLY: EIA does NOT publish a days-of-supply figure in the WNGSR (that normalization exists in the
petroleum WPSR, not the gas report), and it publishes no regional demand denominator here. Rather than
invent a substitute, `days_of_supply` is None on every record with a `days_of_supply_note` saying why.

BLIND WALL (critical). The WNGSR prints Thursday 10:30 ET. For a decision on day D, only reports whose
release is STRICTLY BEFORE D are visible — a storage Thursday's OWN print must never appear in that
Thursday's open-time state. This matches the S96 fix in forecast_harness._storage_asof (strict `<`, not
`<=`). We also shift the release to Friday when the nominal Thursday is a federal holiday, which is EIA's
published practice; a same-week shift can only make the wall MORE conservative, never less.

MISSING IS EXPLICIT, NEVER ZERO. A zeroed storage level reads as "empty inventory" — a catastrophic false
signal. Every absent value is None and the record names the gap. No interpolation across missing weeks.
Zero synthetic data anywhere in this module.

PUBLIC INTERFACE (the orchestrator wires this into decision_state serially, at the end):

    storage_regional_asof(date) -> dict | None

        date : str "YYYY-MM-DD" | datetime.date  -- the DECISION day D.
        returns: None if no report is visible strictly before D (or the store is absent/empty), else a dict:
            {
              "as_of":        "YYYY-MM-DD",   # release date of the most recent VISIBLE report
              "period":       "YYYY-MM-DD",   # the week-ending Friday that report covers
              "regions": {
                 "<name>": {"level": float|None, "weekly_chg": float|None,
                            "vs_5yr": float|None, "vs_year_ago": float|None,
                            "chg_vs_5yr_chg": float|None, "unit": "Bcf",
                            "missing": [str, ...]}          # names each unavailable field, never zeroed
                 ...  keys: l48, east, midwest, south_central, south_central_salt,
                            south_central_nonsalt, mountain, pacific
              },
              "salt_share":   float|None,     # salt level / south_central level
              "days_of_supply": None,
              "days_of_supply_note": str,
              "source": "EIA_WNGSR_v2"
            }
        The function reads the on-disk store (data/storage_regional/storage_regional.json), caching it.
        It performs no network I/O and asserts the blind wall on every call.

USAGE
    EIA_API_KEY=DEMO_KEY python research/kalshi/storage_regional.py --build
    python research/kalshi/storage_regional.py --audit --start 2024-01-01 --end 2026-03-01
    python research/kalshi/storage_regional.py --selftest
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict

EIA_BASE = "https://api.eia.gov/v2"
ROUTE = "natural-gas/stor/wkly"

# region key -> (EIA series id, human label)
REGIONS = {
    "l48":                   ("NW2_EPG0_SWO_R48_BCF", "Lower 48 total"),
    "east":                  ("NW2_EPG0_SWO_R31_BCF", "East"),
    "midwest":               ("NW2_EPG0_SWO_R32_BCF", "Midwest"),
    "south_central":         ("NW2_EPG0_SWO_R33_BCF", "South Central total"),
    "south_central_salt":    ("NW2_EPG0_SSO_R33_BCF", "South Central SALT"),
    "south_central_nonsalt": ("NW2_EPG0_SNO_R33_BCF", "South Central NON-SALT"),
    "mountain":              ("NW2_EPG0_SWO_R34_BCF", "Mountain"),
    "pacific":               ("NW2_EPG0_SWO_R35_BCF", "Pacific"),
}

UNIT = "Bcf"
DOS_NOTE = ("EIA publishes no days-of-supply (or any demand-normalized) figure in the Weekly Natural Gas "
            "Storage Report, and no regional demand denominator; no substitute is computed here.")

_HERE = os.path.dirname(os.path.abspath(__file__))
_STORE_DIRS = [os.path.join(_HERE, "..", "..", "data", "storage_regional"),
               os.path.join("data", "storage_regional")]
STORE_NAME = "storage_regional.json"
RAW_NAME = "levels_raw.json"


# ----------------------------------------------------------------------------- release-date mapping

def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(days=7 * (n - 1))


def _federal_holidays(year: int) -> set:
    """US federal holidays that can fall on a Thursday and push the WNGSR release to Friday."""
    obs = set()
    fixed = [(1, 1), (6, 19), (7, 4), (11, 11), (12, 25)]
    for m, day in fixed:
        obs.add(dt.date(year, m, day))
    obs.add(_nth_weekday(year, 1, 0, 3))    # MLK, 3rd Mon
    obs.add(_nth_weekday(year, 2, 0, 3))    # Presidents, 3rd Mon
    obs.add(_nth_weekday(year, 9, 0, 1))    # Labor, 1st Mon
    obs.add(_nth_weekday(year, 10, 0, 2))   # Columbus, 2nd Mon
    obs.add(_nth_weekday(year, 11, 3, 4))   # Thanksgiving, 4th Thu
    # Memorial Day, last Mon in May
    d = dt.date(year, 5, 31)
    obs.add(d - dt.timedelta(days=(d.weekday() - 0) % 7))
    return obs


def release_date(period: dt.date) -> dt.date:
    """Week-ending Friday `period` -> WNGSR release date (the following Thursday 10:30 ET; Friday when
    that Thursday is a federal holiday, per EIA practice)."""
    d = period + dt.timedelta(days=1)
    while d.weekday() != 3:
        d += dt.timedelta(days=1)
    if d in _federal_holidays(d.year):
        d += dt.timedelta(days=1)
    return d


# ----------------------------------------------------------------------------- fetch

def _get(url: str, tries: int = 8):
    """GET with exponential backoff. DEMO_KEY is aggressively rate-limited (429); a real EIA_API_KEY
    avoids nearly all of this."""
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503) or i == tries - 1:
                raise
            wait = min(120, 15 * (2 ** i))
            print(f"[storage_regional] HTTP {e.code}; backing off {wait}s")
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError):
            if i == tries - 1:
                raise
            time.sleep(min(120, 15 * (2 ** i)))
    raise RuntimeError("unreachable")


def fetch_all(key: str, page: int = 5000, pause: float = 3.0, tries: int = 8) -> dict:
    """{region_key: {period_iso: level}} for ALL eight series.

    Fetched as ONE multi-facet query, paginated by offset — 2 calls instead of 8, which matters because
    DEMO_KEY throttles hard. Non-numeric/absent values are DROPPED so they surface as explicit gaps
    downstream; they are never coerced to 0.
    """
    by_sid = {sid: rk for rk, (sid, _) in REGIONS.items()}
    facets = "".join(f"&facets[series][]={sid}" for sid in by_sid)
    raw = {rk: {} for rk in REGIONS}
    offset, total = 0, None
    while True:
        url = (f"{EIA_BASE}/{ROUTE}/data/?api_key={key}&frequency=weekly&data[0]=value{facets}"
               f"&sort[0][column]=period&sort[0][direction]=desc&length={page}&offset={offset}")
        d = _get(url, tries=tries)
        resp = d.get("response", {})
        rows = resp.get("data", [])
        if total is None:
            total = int(resp.get("total", 0))
            print(f"[storage_regional] EIA reports {total} rows across {len(by_sid)} series")
        for row in rows:
            rk = by_sid.get(row.get("series"))
            v = row.get("value")
            if rk is None or v is None or v == "":
                continue
            try:
                raw[rk][dt.date.fromisoformat(row["period"]).isoformat()] = float(v)
            except (ValueError, TypeError):
                continue
        offset += len(rows)
        if not rows or offset >= total:
            break
        time.sleep(pause)

    for rk, (sid, label) in REGIONS.items():
        per = sorted(raw[rk])
        print(f"[storage_regional] {rk:<22} {sid}  n={len(per):>4}  "
              f"{per[0] if per else '-'}..{per[-1] if per else '-'}  ({label})")
    return raw


# ---- fallback source: EIA's own weekly history workbook, NO API KEY REQUIRED ------------------
# https://ir.eia.gov/ngs/ngshistory.xls is the official file behind the WNGSR and carries the identical
# eight series (East, Midwest, Mountain, Pacific, South Central, Salt, NonSalt, Total Lower 48) from
# 2010-01-01 forward. Used when the API key is rate-limited (DEMO_KEY is 10 req/hr and globally shared).
NGSHISTORY_URL = "https://ir.eia.gov/ngs/ngshistory.xls"
# workbook column index -> region key (sheet `html_report_history`, header on row 6)
_XLS_COLS = {2: "east", 3: "midwest", 4: "mountain", 5: "pacific",
             6: "south_central", 7: "south_central_salt", 8: "south_central_nonsalt", 9: "l48"}


def fetch_all_xls(url: str = NGSHISTORY_URL) -> tuple:
    """({region_key: {period_iso: level}}, {period_iso: eia_source_label}) from ngshistory.xls.

    Blank/non-numeric cells are DROPPED so they surface as explicit gaps; never coerced to 0.
    """
    try:
        import xlrd
    except ImportError:
        raise SystemExit("the xls fallback needs xlrd: pip install xlrd")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        blob = r.read()
    book = xlrd.open_workbook(file_contents=blob)
    sh = book.sheet_by_name("html_report_history")
    hdr = [str(c).strip() for c in sh.row_values(6)]
    assert hdr[2].startswith("East") and hdr[7] == "Salt" and hdr[8] == "NonSalt", \
        f"ngshistory.xls layout changed: {hdr}"
    raw = {rk: {} for rk in REGIONS}
    prov = {}
    for r in range(7, sh.nrows):
        row = sh.row_values(r)
        try:
            per = dt.datetime(*xlrd.xldate_as_tuple(float(row[0]), book.datemode)).date().isoformat()
        except (ValueError, TypeError):
            continue
        prov[per] = str(row[1]).strip()
        for ci, rk in _XLS_COLS.items():
            v = row[ci]
            if v is None or v == "":
                continue
            try:
                raw[rk][per] = float(v)
            except (ValueError, TypeError):
                continue
    for rk, (sid, label) in REGIONS.items():
        per = sorted(raw[rk])
        print(f"[storage_regional] {rk:<22} n={len(per):>4}  "
              f"{per[0] if per else '-'}..{per[-1] if per else '-'}  ({label})")
    return raw, prov


# ----------------------------------------------------------------------------- derive

def _prior_same_week(byweek: dict, year: int, week: int, back: int):
    """Levels for the same ISO week in the `back` prior years, in year order. Absent years are simply
    absent (no fill, no interpolation)."""
    return [v for (y, v) in byweek.get(week, []) if year - back <= y < year]


def build_records(raw: dict, prov: dict | None = None, source: str = "EIA_WNGSR_v2") -> dict:
    """{release_iso: record}. One record per report; every region/split carried, missing named explicitly."""
    all_periods = sorted({p for s in raw.values() for p in s})
    # per region: ISO-week -> [(year, level)] for the 5-yr / year-ago comparisons
    byweek = {rk: defaultdict(list) for rk in REGIONS}
    for rk, s in raw.items():
        for p, v in s.items():
            d = dt.date.fromisoformat(p)
            byweek[rk][d.isocalendar()[1]].append((d.year, v))

    # per region: ISO-week -> [(year, weekly_change)]
    chg = {rk: {} for rk in REGIONS}
    for rk, s in raw.items():
        per = sorted(s)
        for i in range(1, len(per)):
            d0, d1 = dt.date.fromisoformat(per[i - 1]), dt.date.fromisoformat(per[i])
            if 5 <= (d1 - d0).days <= 10:          # never bridge a real gap
                chg[rk][per[i]] = s[per[i]] - s[per[i - 1]]
    chg_byweek = {rk: defaultdict(list) for rk in REGIONS}
    for rk, m in chg.items():
        for p, c in m.items():
            d = dt.date.fromisoformat(p)
            chg_byweek[rk][d.isocalendar()[1]].append((d.year, c))

    out = {}
    for p in all_periods:
        pd = dt.date.fromisoformat(p)
        yr, wk = pd.year, pd.isocalendar()[1]
        rel = release_date(pd).isoformat()
        regions = {}
        for rk in REGIONS:
            lvl = raw[rk].get(p)
            miss = []
            if lvl is None:
                miss.append("level")
            c = chg[rk].get(p)
            if c is None:
                miss.append("weekly_chg")

            prior = _prior_same_week(byweek[rk], yr, wk, 5)
            vs5 = None
            if lvl is not None and len(prior) >= 3:
                vs5 = lvl - sum(prior) / len(prior)
            else:
                miss.append("vs_5yr" if lvl is not None else "vs_5yr(no_level)")

            ya = [v for (y, v) in byweek[rk].get(wk, []) if y == yr - 1]
            vsya = (lvl - ya[0]) if (lvl is not None and ya) else None
            if vsya is None:
                miss.append("vs_year_ago")

            pc = [v for (y, v) in chg_byweek[rk].get(wk, []) if yr - 5 <= y < yr]
            cvs5 = (c - sum(pc) / len(pc)) if (c is not None and len(pc) >= 3) else None
            if cvs5 is None:
                miss.append("chg_vs_5yr_chg")

            regions[rk] = {
                "level": None if lvl is None else round(lvl, 1),
                "weekly_chg": None if c is None else round(c, 1),
                "vs_5yr": None if vs5 is None else round(vs5, 1),
                "vs_year_ago": None if vsya is None else round(vsya, 1),
                "chg_vs_5yr_chg": None if cvs5 is None else round(cvs5, 1),
                "unit": UNIT,
                "missing": miss,
            }

        salt = regions["south_central_salt"]["level"]
        sc = regions["south_central"]["level"]
        share = round(salt / sc, 4) if (salt is not None and sc) else None

        out[rel] = {
            "as_of": rel,
            "period": p,
            "regions": regions,
            "salt_share": share,
            "days_of_supply": None,
            "days_of_supply_note": DOS_NOTE,
            "source": source,
            "eia_estimate_basis": (prov or {}).get(p),
        }
    return out


def consistency(records: dict) -> list:
    """South Central total vs SALT + NON-SALT. Reported, not enforced (EIA rounds each series)."""
    bad = []
    for rel, r in records.items():
        g = r["regions"]
        sc, s, n = (g["south_central"]["level"], g["south_central_salt"]["level"],
                    g["south_central_nonsalt"]["level"])
        if None in (sc, s, n):
            continue
        if abs(sc - (s + n)) > 2.0:
            bad.append((rel, sc, s + n))
    return bad


# ----------------------------------------------------------------------------- store + public read

def store_path(write: bool = False) -> str:
    for d in _STORE_DIRS:
        if os.path.isdir(d):
            return os.path.join(d, STORE_NAME)
    d = _STORE_DIRS[0]
    if write:
        os.makedirs(d, exist_ok=True)
    return os.path.join(d, STORE_NAME)


_CACHE = {}


def load_store(path: str | None = None) -> dict:
    p = path or store_path()
    if p in _CACHE:
        return _CACHE[p]
    d = json.load(open(p)) if os.path.exists(p) else {}
    _CACHE[p] = d
    return d


def storage_regional_asof(date, store: dict | None = None) -> dict | None:
    """Regional NG storage visible at the DECISION time of `date`.

    BLIND WALL: returns the most recent report whose RELEASE date is STRICTLY BEFORE `date`. A storage
    Thursday's own 10:30 ET print is therefore never visible in that Thursday's state (S96 behavior).
    Returns None when nothing is visible or the store is absent. See module docstring for the full
    return shape. Never returns zeros for missing data — absent values are None and named in `missing`.
    """
    iso = date.isoformat() if isinstance(date, (dt.date, dt.datetime)) else str(date)[:10]
    s = load_store() if store is None else store
    if not s:
        return None
    past = [r for r in s if r < iso]
    if not past:
        return None
    rel = max(past)
    assert rel < iso, f"blind wall violated: report {rel} not strictly before decision day {iso}"
    return s[rel]


# ----------------------------------------------------------------------------- audit

def audit(store: dict, start: str, end: str) -> dict:
    """Walk every calendar day in [start, end] and check the blind wall + coverage. Violation = a returned
    report whose release date is >= the decision day (in particular a Thursday seeing its own print)."""
    d0, d1 = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    viol, days, covered, thursdays, own_print = 0, 0, 0, 0, 0
    d = d0
    while d <= d1:
        days += 1
        r = storage_regional_asof(d, store=store)
        if r is not None:
            covered += 1
            if r["as_of"] >= d.isoformat():
                viol += 1
        if d.weekday() == 3:
            thursdays += 1
            if r is not None and r["as_of"] == d.isoformat():
                own_print += 1
        d += dt.timedelta(days=1)
    return {"days": days, "covered": covered, "violations": viol,
            "thursdays": thursdays, "thursday_own_print": own_print}


def coverage_report(records: dict, start: str, end: str) -> None:
    reps = sorted(r for r in records if start <= r <= end)
    print(f"[audit] reports in window {start}..{end}: {len(reps)}  "
          f"({reps[0] if reps else '-'}..{reps[-1] if reps else '-'})")
    # weekly-continuity gaps, named individually
    gaps = []
    for i in range(1, len(reps)):
        n = (dt.date.fromisoformat(reps[i]) - dt.date.fromisoformat(reps[i - 1])).days
        if n > 10:
            gaps.append((reps[i - 1], reps[i], n))
    if gaps:
        for a, b, n in gaps:
            print(f"[audit] GAP {a} -> {b} ({n} days)")
    else:
        print("[audit] no report-to-report gap > 10 days")
    for rk, (sid, label) in REGIONS.items():
        miss = [r for r in reps if records[r]["regions"][rk]["level"] is None]
        n5 = [r for r in reps if records[r]["regions"][rk]["vs_5yr"] is None]
        nya = [r for r in reps if records[r]["regions"][rk]["vs_year_ago"] is None]
        print(f"[audit] {rk:<22} level_missing={len(miss)} vs_5yr_missing={len(n5)} "
              f"vs_year_ago_missing={len(nya)}")
        for lst, nm in ((miss, "level"), (n5, "vs_5yr"), (nya, "vs_year_ago")):
            for r in lst:
                print(f"           {nm} missing at report {r}")


# ----------------------------------------------------------------------------- selftest

def selftest() -> bool:
    """Unit-checks the derivation + the blind wall on CONSTRUCTED series (not market data)."""
    ok = True

    def chk(cond, good, bad):
        nonlocal ok
        print(("  ok  " + good) if cond else ("  FAIL " + bad))
        if not cond:
            ok = False

    # 1) release-date mapping: Fri week-ending -> following Thu
    chk(release_date(dt.date(2026, 1, 2)) == dt.date(2026, 1, 8),
        "release map: period 2026-01-02 (Fri) -> 2026-01-08 (Thu)",
        f"release map got {release_date(dt.date(2026, 1, 2))}")
    # Thanksgiving 2025-11-27 is a Thursday federal holiday -> shift to Friday
    chk(release_date(dt.date(2025, 11, 21)) == dt.date(2025, 11, 28),
        "release map: Thanksgiving Thursday shifts to 2025-11-28 (Fri)",
        f"holiday shift got {release_date(dt.date(2025, 11, 21))}")

    # 2) derivation on a constructed 7-year series, one region held out to prove MISSING stays None
    raw = {rk: {} for rk in REGIONS}
    periods = []
    for yr in range(2019, 2026):
        periods.append(dt.date.fromisocalendar(yr, 23, 5))   # ISO week 23, Friday — aligned across years
    for rk in REGIONS:
        for i, p in enumerate(periods):
            prev = p - dt.timedelta(days=7)
            if rk == "pacific":
                continue                                   # held out entirely -> explicit gap
            base = 1000.0 + 100.0 * i
            raw[rk][prev.isoformat()] = base
            raw[rk][p.isoformat()] = base + (10.0 if i < 6 else 60.0)
    # make south_central == salt + nonsalt exactly on the last period
    recs = build_records(raw)
    last_p = periods[-1]
    rel = release_date(last_p).isoformat()
    chk(rel in recs, f"record built for release {rel}", f"no record for {rel}")
    if rel in recs:
        e = recs[rel]["regions"]["east"]
        chk(e["weekly_chg"] == 60.0, f"weekly_chg = {e['weekly_chg']} (constructed +60)",
            f"weekly_chg = {e['weekly_chg']}, expected 60")
        # prior 5 same-week levels are 1610,1710,1810,1910,2010 -> mean 1810; level = 2010+... check vs_5yr present
        chk(e["vs_5yr"] is not None, f"vs_5yr computed = {e['vs_5yr']}", "vs_5yr None with 5 prior years")
        chk(e["vs_year_ago"] is not None, f"vs_year_ago computed = {e['vs_year_ago']}", "vs_year_ago None")
        chk(e["chg_vs_5yr_chg"] == 50.0,
            f"chg_vs_5yr_chg = {e['chg_vs_5yr_chg']} (+60 vs +10 avg)",
            f"chg_vs_5yr_chg = {e['chg_vs_5yr_chg']}, expected 50")
        pac = recs[rel]["regions"]["pacific"]
        chk(pac["level"] is None and "level" in pac["missing"],
            "held-out region: level is None and named in `missing` (NOT zero)",
            f"held-out region leaked {pac['level']}")
        chk(recs[rel]["days_of_supply"] is None and recs[rel]["days_of_supply_note"],
            "days_of_supply None with an explaining note (EIA publishes none)",
            "days_of_supply not handled")

    # 3) no interpolation across a gap: drop a middle period, the next change must be None
    gap_raw = {"east": {}}
    for i, off in enumerate([0, 7, 21]):                    # 14-day hole
        gap_raw["east"][(dt.date(2025, 3, 7) + dt.timedelta(days=off)).isoformat()] = 1000.0 + i
    gr = build_records({rk: (gap_raw["east"] if rk == "east" else {}) for rk in REGIONS})
    third = release_date(dt.date(2025, 3, 28)).isoformat()
    chk(third in gr and gr[third]["regions"]["east"]["weekly_chg"] is None,
        "no interpolation: weekly_chg across a 14-day hole is None",
        "a change was computed across a gap")

    # 4) BLIND WALL — the whole point
    store = {"2026-01-08": {"as_of": "2026-01-08"}, "2026-01-15": {"as_of": "2026-01-15"}}
    r = storage_regional_asof("2026-01-15", store=store)      # the report Thursday itself
    chk(r is not None and r["as_of"] == "2026-01-08",
        "blind wall: on report-Thursday 2026-01-15 the visible print is 2026-01-08 (own print hidden)",
        f"blind wall LEAK: got {r and r['as_of']} on 2026-01-15")
    r = storage_regional_asof("2026-01-16", store=store)
    chk(r is not None and r["as_of"] == "2026-01-15",
        "blind wall: Friday 2026-01-16 sees the 2026-01-15 print",
        f"got {r and r['as_of']} on 2026-01-16")
    chk(storage_regional_asof("2026-01-08", store=store)["as_of"] == "2026-01-08"
        if False else storage_regional_asof("2026-01-05", store=store) is None,
        "blind wall: before any report -> None (never a zeroed record)",
        "returned a record before any report existed")
    a = audit(store, "2026-01-01", "2026-01-31")
    chk(a["violations"] == 0 and a["thursday_own_print"] == 0,
        f"audit on constructed store: violations={a['violations']} thursday_own_print={a['thursday_own_print']}",
        f"audit found violations={a['violations']} own_print={a['thursday_own_print']}")

    print("SELFTEST", "PASS" if ok else "FAIL")
    return ok


# ----------------------------------------------------------------------------- cli

def main():
    ap = argparse.ArgumentParser(description="Regional NG working-gas storage (EIA WNGSR) decision input")
    ap.add_argument("--build", action="store_true", help="fetch from EIA and write the store")
    ap.add_argument("--audit", action="store_true", help="blind-wall + coverage audit of the on-disk store")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--start", default="2024-01-01")
    ap.add_argument("--end", default="2026-03-01")
    ap.add_argument("--key", default=os.environ.get("EIA_API_KEY", "DEMO_KEY"))
    ap.add_argument("--source", choices=["auto", "api", "xls"], default="auto",
                    help="auto = EIA API v2, falling back to ngshistory.xls on a 429")
    ap.add_argument("--asof", help="print storage_regional_asof(DATE) and exit")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)

    if args.build:
        prov, src = None, "EIA_WNGSR_v2"
        if args.source == "xls":
            raw, prov = fetch_all_xls()
            src = "EIA_WNGSR_ngshistory_xls"
        else:
            try:
                # in auto mode don't burn minutes on backoff — the xls fallback is equivalent data
                raw = fetch_all(args.key, tries=(8 if args.source == "api" else 2))
            except urllib.error.HTTPError as e:
                if e.code != 429 or args.source == "api":
                    raise
                print(f"[storage_regional] API rate-limited ({e.code}); falling back to {NGSHISTORY_URL}")
                raw, prov = fetch_all_xls()
                src = "EIA_WNGSR_ngshistory_xls"
        recs = build_records(raw, prov, src)
        p = store_path(write=True)
        d = os.path.dirname(p)
        json.dump(raw, open(os.path.join(d, RAW_NAME), "w"), indent=1)
        json.dump(recs, open(p, "w"), indent=1)
        rr = sorted(recs)
        print(f"[storage_regional] wrote {p}: {len(recs)} reports {rr[0]}..{rr[-1]}")
        bad = consistency(recs)
        print(f"[storage_regional] south_central vs salt+nonsalt mismatches >2 Bcf: {len(bad)}")
        for b in bad[:10]:
            print(f"   {b[0]}  total={b[1]}  salt+nonsalt={b[2]}")
        _CACHE.clear()

    if args.asof:
        print(json.dumps(storage_regional_asof(args.asof), indent=1))
        return

    if args.audit:
        s = load_store()
        if not s:
            print("[audit] no store on disk; run --build first")
            sys.exit(1)
        coverage_report(s, args.start, args.end)
        a = audit(s, args.start, args.end)
        print(f"[audit] blind wall over {args.start}..{args.end}: days={a['days']} "
              f"covered={a['covered']} VIOLATIONS={a['violations']} "
              f"thursdays={a['thursdays']} thursday_own_print={a['thursday_own_print']}")


if __name__ == "__main__":
    main()
