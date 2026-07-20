"""
nuclear_outages.py - FEED R arm 1 (family D+S): U.S. nuclear capacity offline, daily (S99).

WHY THIS EXISTS
---------------
Shoulder seasons are maintenance seasons, and NUCLEAR refueling outages ADD gas burn GW-for-GW
(a reactor offline is replaced at the margin mostly by gas). Deep cold can also force units offline
exactly when gas demand peaks - the walked winter's freeze window shows U.S. nuclear capacity out
jumping 1.8 -> 3.2 GW across Jan 17-18 2026, a measured 1.4 GW of extra implied gas burn arriving
DURING the squeeze build-up. None of this was visible to the agent. The feed does not gate, score
or recommend; the agent decides what it means.

SOURCE (the S98 sweep side-find, EIA_BALANCE_OPTIONS_S98.md section 7): EIA Open Data v2 route
`nuclear-outages/us-nuclear-outages` - DAILY U.S. aggregate operable capacity, capacity out, and
percent out, 2007-01-01 -> present, straight from the API. No NRC page scraping needed. Facility
and generator level exist on sibling routes (facets verified) - deliberately NOT pulled in arm 1;
named phase-2 scope. ISO aggregate outage reports (coal/gas plant maintenance) are arm 4, a
separate build.

PUBLICATION MECHANICS (measured 2026-07-20)
-------------------------------------------
The underlying NRC Power Reactor Status Report posts each morning for that day's 00:00 status, and
EIA re-serves it SAME DAY: on 2026-07-20 the route already carried a 2026-07-20 row. Earlier the
same day the S98 sweep saw the series end at 2026-07-17 - i.e. weekend rows (Jul 19-20) landed in a
Monday batch, and 2026-07-18 (Sat) is ABSENT ENTIRELY. Measured properties:
  1. Same-day-morning publication on normal weekdays; weekend/holiday rows can arrive late or
     never (NRC skips some weekend/holiday reports; EIA leaves the day missing, no interpolation).
  2. Missing calendar days are REAL gaps and stay gaps in this store (missing == absent, never
     bridged; day-over-day changes across a gap are None).
BLIND WALL (conservative): a day-D value posted the morning of D is certainly public by D+1, and
the exact posting hour is unmeasured historically, so
    knowable_from = period + 1 calendar day;  asof(iso) = latest period STRICTLY BEFORE iso.
Age is typically 1 day, stretching to 2-3 across missing weekend days - exposed per read.

REVISION RISK (named, unmeasured): NRC daily statuses are point-in-time and unlikely to revise,
but EIA-side corrections are not ruled out; the store is a retrieval-dated snapshot (feed-K-class
question only if it ever matters - values here are ~100 MW-scale state, not print-surprise data).

UNITS: the API serves MEGAWATTS; the store keeps raw MW, the asof exposes GW alongside.

STORE: data/nuclear_outages/us_daily.json.gz. No commits by this module; S3 push is the
orchestrator's step (prefix nuclear_outages/).

USAGE
-----
  python research/kalshi/nuclear_outages.py --build
  python research/kalshi/nuclear_outages.py --selftest
  python research/kalshi/nuclear_outages.py --show 2026-01-21
"""

from __future__ import annotations

import argparse
import datetime
import gzip
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORE_DIR = os.path.join(_ROOT, "data", "nuclear_outages")
STORE_PATH = os.path.join(STORE_DIR, "us_daily.json.gz")
ENV_PATH = os.path.join(_ROOT, "scratchpad", "aws.env")
API = "https://api.eia.gov/v2/nuclear-outages/us-nuclear-outages/data"


def _api_key() -> str:
    for line in open(ENV_PATH):
        if line.startswith("EIA_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("EIA_API_KEY not found in scratchpad/aws.env")


def build() -> dict:
    import requests
    key = _api_key()
    rows, offset = [], 0
    while True:
        r = requests.get(API, params={
            "api_key": key, "data[]": ["capacity", "outage", "percentOutage"],
            "sort[0][column]": "period", "sort[0][direction]": "asc",
            "length": 5000, "offset": offset}, timeout=120)
        r.raise_for_status()
        resp = r.json()["response"]
        batch = resp["data"]
        rows.extend(batch)
        offset += len(batch)
        if offset >= int(resp["total"]) or not batch:
            break
    def _f(v):  # EIA v2 serializes numerics as strings in data pulls
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    days = {}
    for row in rows:
        p = row["period"]
        days[p] = {"capacity_mw": _f(row.get("capacity")), "outage_mw": _f(row.get("outage")),
                   "pct_out": _f(row.get("percentOutage"))}
    os.makedirs(STORE_DIR, exist_ok=True)
    store = {
        "meta": {
            "retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "source": API,
            "units": "megawatts (raw as served)",
            "publication": "same-day-morning weekdays; weekend/holiday rows late or absent "
                           "(measured 2026-07-20); wall = knowable_from period+1, strictly-prior join",
            "n_days": len(days),
            "first": min(days), "last": max(days),
        },
        "days": days,
    }
    with gzip.open(STORE_PATH, "wt", encoding="utf-8") as f:
        json.dump(store, f)
    print(f"[nuclear_outages] store written: {len(days)} days {store['meta']['first']}.."
          f"{store['meta']['last']} -> {os.path.relpath(STORE_PATH, _ROOT)}")
    return store


_CACHE: dict | None = None


def load_store() -> dict | None:
    global _CACHE
    if _CACHE is None and os.path.exists(STORE_PATH):
        with gzip.open(STORE_PATH, "rt", encoding="utf-8") as f:
            _CACHE = json.load(f)
    return _CACHE


def _season(iso: str) -> str | None:
    m = int(iso[5:7])
    if m in (3, 4, 5):
        return "spring_outage_season"
    if m in (9, 10, 11):
        return "fall_outage_season"
    return None


def nuclear_outages_asof(iso: str) -> dict | None:
    """Latest U.S. nuclear capacity-out state STRICTLY BEFORE iso (wall: knowable_from = period+1).
    Day-over-day / week-over-week changes are None when the exact comparison day is a real gap in
    the series - never bridged. None before coverage (2007-01-01)."""
    store = load_store()
    if not store:
        return None
    days = store["days"]
    prior = [p for p in days if p < iso]
    if not prior:
        return None
    p = max(prior)
    d = days[p]
    out = d["outage_mw"]

    def delta(k: int):
        ref = (datetime.date.fromisoformat(p) - datetime.timedelta(days=k)).isoformat()
        r = days.get(ref)
        if r is None or r["outage_mw"] is None or out is None:
            return None
        return round(out - r["outage_mw"], 1)

    return {
        "period": p,
        "age_days": (datetime.date.fromisoformat(iso) - datetime.date.fromisoformat(p)).days,
        "capacity_out_mw": out,
        "capacity_out_gw": round(out / 1000.0, 3) if out is not None else None,
        "pct_of_fleet_out": d["pct_out"],
        "fleet_capacity_mw": d["capacity_mw"],
        "chg_1d_mw": delta(1),
        "chg_7d_mw": delta(7),
        "outage_season": _season(iso),
        "note": "nuclear GW offline adds gas burn roughly GW-for-GW at the margin; season tag is "
                "calendar-descriptive; changes across missing days are None, never bridged",
    }


def _t(cond, msg, fails):
    print(("  PASS " if cond else "  FAIL ") + msg)
    return fails + (0 if cond else 1)


def _selftest() -> int:
    print("=== nuclear_outages --selftest ===")
    fails = 0
    store = load_store()
    fails = _t(store is not None, "store present", fails)
    if store is None:
        return 1
    days = store["days"]
    fails = _t(len(days) >= 7100 and min(days) == "2007-01-01", f"coverage {min(days)}..{max(days)} ({len(days)} days)", fails)
    # measured pins (2026-07-20 pull): the freeze-window outage rise 1.8 -> 3.2 GW
    v15, v20 = days.get("2026-01-15", {}).get("outage_mw"), days.get("2026-01-20", {}).get("outage_mw")
    fails = _t(v15 is not None and abs(v15 - 1839.396) < 0.5, f"2026-01-15 outage {v15} MW (~1839)", fails)
    fails = _t(v20 is not None and abs(v20 - 3184.344) < 0.5, f"2026-01-20 outage {v20} MW (~3184)", fails)
    # blind wall: strictly-prior join, day-D never sees its own morning row
    a21 = nuclear_outages_asof("2026-01-21")
    fails = _t(a21 is not None and a21["period"] == "2026-01-20" and a21["age_days"] == 1,
               f"asof 2026-01-21 -> period {a21 and a21['period']} age {a21 and a21['age_days']}", fails)
    a20 = nuclear_outages_asof("2026-01-20")
    fails = _t(a20 is not None and a20["period"] == "2026-01-19", "asof 2026-01-20 -> 2026-01-19 (own day walled)", fails)
    fails = _t(nuclear_outages_asof("2007-01-01") is None, "pre-coverage -> None", fails)
    # measured chg on a verified consecutive pair (Jan 15 -> 16: +268.3)
    a17 = nuclear_outages_asof("2026-01-17")
    fails = _t(a17 is not None and a17["chg_1d_mw"] is not None and abs(a17["chg_1d_mw"] - 268.3) < 0.5,
               f"chg_1d on the 01-16 row = {a17 and a17['chg_1d_mw']} (~+268.3)", fails)
    # gap honesty: changes across a REAL missing day are None (find any gap in the store)
    gap_checked = False
    ds = sorted(days)
    for i in range(1, len(ds)):
        d_prev, d_cur = datetime.date.fromisoformat(ds[i - 1]), datetime.date.fromisoformat(ds[i])
        if (d_cur - d_prev).days == 2:  # exactly one missing day between rows
            probe = nuclear_outages_asof((d_cur + datetime.timedelta(days=1)).isoformat())
            if probe and probe["period"] == ds[i]:
                fails = _t(probe["chg_1d_mw"] is None,
                           f"chg_1d across the {ds[i - 1]}->{ds[i]} gap is None (gap kept, not bridged)", fails)
                gap_checked = True
                break
    if not gap_checked:
        print("  NOTE no single-day gap found in store; gap-honesty check not exercised")
    # blind-wall walk over the walked window: every trade day resolves strictly-prior
    d = datetime.date(2025, 11, 3)
    bad = 0
    while d <= datetime.date(2026, 2, 27):
        if d.weekday() < 5 or d.weekday() == 6:
            r = nuclear_outages_asof(d.isoformat())
            if r is None or not (r["period"] < d.isoformat()):
                bad += 1
        d += datetime.timedelta(days=1)
    fails = _t(bad == 0, f"blind-wall walk Nov 3 - Feb 27: {bad} violations (expect 0)", fails)
    print(f"=== selftest {'PASS' if fails == 0 else f'FAIL ({fails})'} ===")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="U.S. daily nuclear capacity-out feed (feed R arm 1)")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--show", metavar="DATE")
    a = ap.parse_args()
    if a.build:
        build()
        return 0
    if a.selftest:
        return _selftest()
    if a.show:
        print(json.dumps(nuclear_outages_asof(a.show), indent=1))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
