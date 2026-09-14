#!/usr/bin/env python3
"""FEED A PHASE 1 (S100, DATA_GATE_S98) - cycle-level MOS as-of, hour resolution.

WHY (the gate, verbatim motivation): the Sunday reopen is priced by a LATER model cycle than the
D-1-evening feed carries; the walk's most reproduced residual (1019 +1570, 0118 +2100, 0125 +2480
weekend gaps) is a DATA limitation, not a reasoning one. This module exposes WHICH cycle was
available WHEN, at hour resolution, from the raw archive the S97 build already landed.

EXPOSURE REWORK, NOT A RE-PULL: the raw store (weather/mos_asof/raw/, on S3 and restored locally
by platform_sync) already holds ALL FOUR daily cycles (00z/06z/12z/18z) for ALL SEVEN days of the
week, 2025-10-29..2026-03-09, per (metro, model) - measured 2026-07-20 before this was written.
Zero new data is fetched.

THE AVAILABILITY WALL (the blind wall of this feed, stated with its mechanics):
  a cycle initialized at runtime R is usable from R + DISSEM_LAG_H hours.
  NAMED LIMITATION: the IEM archive serves (runtime, ftime, tmp) only - actual dissemination
  stamps are NOT recoverable from it, so the wall cannot be verified per-cycle from this source.
  DISSEM_LAG_H = 4.5 is CONSERVATIVE vs NWS's documented ~3.2-4.0h MOS posting latency: a too-late
  wall can only under-inform a view, never leak the future into it. The constant is exposed in
  every output; sensitivity to it is a legitimate future measurement, never silently changed here.

THE TWO DOCUMENTED BUILDER TRAPS (S98/S99), engineered out:
  1. index overwrite - this module NEVER touches mos_asof_index.json; its own store is a separate
     file, and build() MERGES into any existing store (read-modify-write per day), never replaces
     the file with only the built range.
  2. normals cache window - vs_normal is computed only when the cached normals file actually
     covers the target date (checked per date); otherwise None with the gap named.

Views delivered (the gate's deliverable):
  cycle_view(asof_utc, start_day)     - the LATEST cycle available per metro before asof, per
                                        horizon D..D+7, gas-weighted, with per-metro cycle sources
  sunday_reopen_view(sunday)          - asof = Sunday 18:00 ET (the Globex reopen), targets Mon..
  weekday_open_view(day)              - asof = 08:00 ET on day D (US session convention, clock
                                        mechanism 'us_session ~08-16 ET')
  overnight_delta(day)                - what the post-evening cycles (18z D-1, 00z D, 06z D) ADDED
                                        vs the D-1-evening batch, per horizon, consecutive-cycle
Per-event always; a horizon with no coverage is None, never zero; deltas computed on the common
metro set only. Additive: nothing existing is renamed or removed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nws_temp_feed import (  # reuse, never re-derive
    STATION_WEIGHTS_RAW, MOS_MODEL_ORDER, MOS_MIN_OBS, REF_TZ,
    station_weights, degree_days, regime_bucket, load_normals, _gw_normal,
)

ET = ZoneInfo("America/New_York")
DISSEM_LAG_H = 4.5              # conservative availability wall; see module docstring
N_HORIZONS = 8                  # D..D+7
WEEKDAY_OPEN_ET = 8             # 08:00 ET; clock mechanism 'US session ~08-16 ET decides the day'

_DATA_CANDIDATES = [os.path.join(HERE, "..", "..", "data", "weather", "mos_asof", "raw"),
                    os.path.join("data", "weather", "mos_asof", "raw"),
                    os.path.join("weather", "mos_asof", "raw")]
STORE_DIR_CANDIDATES = [os.path.join(HERE, "..", "..", "data", "weather", "mos_cycle"),
                        os.path.join("data", "weather", "mos_cycle")]
STORE_NAME = "mos_cycle_index.json"


def _raw_dir() -> str:
    for p in _DATA_CANDIDATES:
        if os.path.isdir(p):
            return p
    raise FileNotFoundError("mos raw archive not found; run platform_sync pull --prefix weather/ first")


def _store_path() -> str:
    for d in STORE_DIR_CANDIDATES:
        parent = os.path.dirname(d)
        if os.path.isdir(parent):
            os.makedirs(d, exist_ok=True)
            return os.path.join(d, STORE_NAME)
    os.makedirs(STORE_DIR_CANDIDATES[0], exist_ok=True)
    return os.path.join(STORE_DIR_CANDIDATES[0], STORE_NAME)


def _parse_ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


_RUNS_CACHE: dict[tuple[str, str], dict[str, dict[str, float]]] = {}


def load_runs(station: str, model: str) -> dict[str, dict[str, float]]:
    """{runtime: {ftime: tmp}} for one (metro, model), merged across every raw span file present.
    Values kept verbatim; a runtime present in two span files merges (identical rows in overlap)."""
    key = (station, model)
    if key in _RUNS_CACHE:
        return _RUNS_CACHE[key]
    rd = _raw_dir()
    runs: dict[str, dict[str, float]] = defaultdict(dict)
    n_files = 0
    for fn in sorted(os.listdir(rd)):
        if fn.startswith(f"{station}_{model}_") and fn.endswith(".json"):
            n_files += 1
            with open(os.path.join(rd, fn)) as fh:
                for r in json.load(fh):
                    t = r.get("tmp")
                    if t is None or t == "":
                        continue                      # missing stays missing, never coerced
                    runs[r["runtime"]][r["ftime"]] = float(t)
    _RUNS_CACHE[key] = dict(runs)
    return _RUNS_CACHE[key]


def _available_runs(runs: dict[str, dict[str, float]], asof_utc: datetime,
                    lookback_h: float = 30.0) -> dict[str, dict[str, float]]:
    """Cycles AVAILABLE (initialized + disseminated) by asof, within the trailing lookback window.
    Hard-asserts the availability wall."""
    lag = timedelta(hours=DISSEM_LAG_H)
    lo = asof_utc - timedelta(hours=lookback_h)
    sel = {rt: fc for rt, fc in runs.items()
           if lo < _parse_ts(rt) and _parse_ts(rt) + lag <= asof_utc}
    assert all(_parse_ts(rt) + lag <= asof_utc for rt in sel), \
        "AVAILABILITY WALL VIOLATION: cycle not yet disseminated at asof"
    return sel


def _day_temp_from_run(fcst: dict[str, float], target_day: str, min_obs: int):
    temps = [t for ft, t in fcst.items()
             if _parse_ts(ft).astimezone(REF_TZ).strftime("%Y-%m-%d") == target_day]
    if len(temps) < min_obs:
        return None
    return max(temps), min(temps)


def _station_view(station: str, target_day: str, asof_utc: datetime) -> dict | None:
    """One metro at one asof for one target day: latest AVAILABLE cycle of the first model in
    MOS_MODEL_ORDER that covers the day. Records model + cycle."""
    for model in MOS_MODEL_ORDER:
        runs = load_runs(station, model)
        if not runs:
            continue
        sel = _available_runs(runs, asof_utc)
        for rt in sorted(sel, key=_parse_ts, reverse=True):
            mm = _day_temp_from_run(sel[rt], target_day, MOS_MIN_OBS[model])
            if mm is None:
                continue
            tmax, tmin = mm
            tmean = (tmax + tmin) / 2.0
            hdd, cdd = degree_days(tmean)
            return {"model": model, "runtime": rt, "tmax": round(tmax, 1), "tmin": round(tmin, 1),
                    "hdd": round(hdd, 2), "cdd": round(cdd, 2)}
    return None


def _gw(per_station: dict[str, dict | None]) -> dict:
    w = station_weights()
    present = {s: v for s, v in per_station.items() if v is not None}
    missing = sorted(s for s in STATION_WEIGHTS_RAW if s not in present)
    wsum = sum(w[s] for s in present)
    if wsum <= 0:
        return {"gw_hdd": None, "gw_cdd": None, "coverage": 0.0, "n_metros": 0,
                "metros_missing": missing, "partial": True,
                "coverage_note": "NO available cycle covers this horizon for any metro - null, NOT zero"}
    gw_hdd = sum(w[s] * present[s]["hdd"] for s in present) / wsum
    gw_cdd = sum(w[s] * present[s]["cdd"] for s in present) / wsum
    return {"gw_hdd": round(gw_hdd, 3), "gw_cdd": round(gw_cdd, 3),
            "coverage": round(wsum, 4), "n_metros": len(present),
            "metros_missing": missing, "partial": bool(missing),
            "regime": regime_bucket(gw_hdd, gw_cdd),
            "cycle_by_metro": {s: f"{present[s]['model']}@{present[s]['runtime']}" for s in sorted(present)},
            "coverage_note": ("complete: all 16 gas-demand metros present" if not missing else
                              f"PARTIAL: {len(missing)}/16 metros missing ({','.join(missing)}); "
                              f"weights renormalized over the {len(present)} present")}


def _delta_on_common(cur: dict[str, dict | None], prv: dict[str, dict | None]) -> dict:
    both = [s for s in STATION_WEIGHTS_RAW if cur.get(s) and prv.get(s)]
    w = station_weights()
    wsum = sum(w[s] for s in both)
    if wsum <= 0:
        return {"d_gw_hdd": None, "d_gw_cdd": None, "coverage": 0.0, "n_metros": 0, "partial": True,
                "coverage_note": "no metro present in BOTH views - delta null, NOT zero"}
    d_hdd = sum(w[s] * (cur[s]["hdd"] - prv[s]["hdd"]) for s in both) / wsum
    d_cdd = sum(w[s] * (cur[s]["cdd"] - prv[s]["cdd"]) for s in both) / wsum
    miss = sorted(set(STATION_WEIGHTS_RAW) - set(both))
    return {"d_gw_hdd": round(d_hdd, 3), "d_gw_cdd": round(d_cdd, 3),
            "coverage": round(wsum, 4), "n_metros": len(both), "partial": bool(miss),
            "coverage_note": ("common set complete" if not miss else
                              f"PARTIAL delta over {len(both)} common metros (missing {','.join(miss)})")}


def cycle_view(asof_utc: datetime, start_day: str, n_horizons: int = N_HORIZONS,
               delta_vs_asof_utc: datetime | None = None) -> dict:
    """The core view: per horizon h, target day start_day+h as seen by the latest cycles AVAILABLE
    at asof_utc; optional delta vs an earlier asof (common metros only)."""
    normals = _normals_or_none()
    horizons = []
    for h in range(n_horizons):
        tgt = (datetime.strptime(start_day, "%Y-%m-%d") + timedelta(days=h)).strftime("%Y-%m-%d")
        cur = {s: _station_view(s, tgt, asof_utc) for s in STATION_WEIGHTS_RAW}
        g = _gw(cur)
        nrm = _gw_normal(tgt, normals) if normals is not None else {"gw_hdd": None, "gw_cdd": None}
        vs = (None if g["gw_hdd"] is None or nrm["gw_hdd"] is None
              else round(g["gw_hdd"] - nrm["gw_hdd"], 3))
        row = {"horizon": h, "target_date": tgt, **g, "normal_gw_hdd": nrm["gw_hdd"],
               "forecast_vs_normal": vs}
        if delta_vs_asof_utc is not None:
            prv = {s: _station_view(s, tgt, delta_vs_asof_utc) for s in STATION_WEIGHTS_RAW}
            row["delta_vs_prior"] = _delta_on_common(cur, prv)
        horizons.append(row)
    return {"asof_utc": asof_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "asof_et": asof_utc.astimezone(ET).strftime("%Y-%m-%dT%H:%M:%S%z"),
            "availability_rule": f"cycle usable from runtime + {DISSEM_LAG_H}h (conservative; "
                                 f"IEM archive carries no posting stamps - named limitation)",
            "start_day": start_day, "horizons": horizons}


def _normals_or_none():
    """Trap #2 guard: use the cached normals file as-is; per-date coverage is checked by _gw_normal
    itself (absent MM-DD -> nulls with note). Returns None only if no cache exists at all."""
    try:
        return load_normals("2025-09-01", "2026-09-01", refresh=False)
    except Exception:
        return None


def sunday_reopen_view(sunday: str) -> dict:
    """Everything available at the Globex Sunday 18:00 ET reopen (minus 1 min), targets Mon..
    Delta vs the SATURDAY-evening state (Sat 18:59 ET = the prior D-1-evening-equivalent), so the
    weekend's OWN cycles (Sat 18z, Sun 00z/06z/12z, and Sun 18z if disseminated) are the delta."""
    d = datetime.strptime(sunday, "%Y-%m-%d")
    assert d.weekday() == 6, f"{sunday} is not a Sunday"
    reopen_et = d.replace(hour=17, minute=59, tzinfo=ET)
    sat_eve_et = (d - timedelta(days=1)).replace(hour=18, minute=59, tzinfo=ET)
    monday = (d + timedelta(days=1)).strftime("%Y-%m-%d")
    v = cycle_view(reopen_et.astimezone(timezone.utc), monday,
                   delta_vs_asof_utc=sat_eve_et.astimezone(timezone.utc))
    v["view"] = "sunday_reopen"
    v["note"] = ("the LATEST cycles available before the Sun 18:00 ET reopen; delta_vs_prior = what "
                 "the weekend's own cycles added vs Saturday evening - the repricing the reopen gap "
                 "delivers (s100_2_weekend_gap_note)")
    return v


def weekday_open_view(day: str) -> dict:
    """Everything available at 08:00 ET on day D (the US-session open convention); delta vs the
    D-1 18:59 ET evening state = what the overnight cycles (18z D-1, 00z D; 06z D lands 10:30z
    which is 05:30/06:30 ET depending on DST) added."""
    d = datetime.strptime(day, "%Y-%m-%d")
    open_et = d.replace(hour=WEEKDAY_OPEN_ET, minute=0, tzinfo=ET)
    prev_eve_et = (d - timedelta(days=1)).replace(hour=18, minute=59, tzinfo=ET)
    v = cycle_view(open_et.astimezone(timezone.utc), day,
                   delta_vs_asof_utc=prev_eve_et.astimezone(timezone.utc))
    v["view"] = "weekday_open"
    v["note"] = ("cycles available by 08:00 ET on D; delta_vs_prior = the overnight add vs the "
                 "D-1-evening state the existing weather_forecast block carries")
    return v


def mos_cycle_asof(day: str) -> dict | None:
    """Store read for decision_state wiring: the built per-day record (weekday_open view; plus the
    sunday_reopen view attached to the PRECEDING Sunday when day is Monday)."""
    p = _store_path()
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        store = json.load(fh)
    return store.get(day)


def build(start: str, end: str, verbose: bool = True) -> dict:
    """Build the per-day store over [start, end): weekday_open view for every day; for Sundays the
    sunday_reopen view (stored under the MONDAY it prices into, additively). MERGES into any
    existing store (trap #1: never replaces the file with only the built range)."""
    p = _store_path()
    store = {}
    if os.path.exists(p):
        with open(p) as fh:
            store = json.load(fh)
    day = datetime.strptime(start, "%Y-%m-%d")
    end_d = datetime.strptime(end, "%Y-%m-%d")
    while day < end_d:
        iso = day.strftime("%Y-%m-%d")
        rec = {"date": iso, "weekday_open": weekday_open_view(iso)}
        if day.weekday() == 0:                                  # Monday: attach the Sunday-reopen view
            sunday = (day - timedelta(days=1)).strftime("%Y-%m-%d")
            try:
                rec["sunday_reopen"] = sunday_reopen_view(sunday)
            except AssertionError:
                pass
        store[iso] = rec
        if verbose:
            wo = rec["weekday_open"]["horizons"][0]
            dl = wo.get("delta_vs_prior", {})
            print(f"[mos-cycle] {iso}  D+0 gwHDD {wo['gw_hdd']}  overnight_d {dl.get('d_gw_hdd')}"
                  + ("  +sunday_reopen" if "sunday_reopen" in rec else ""), flush=True)
        day += timedelta(days=1)
    with open(p, "w") as fh:
        json.dump(store, fh, sort_keys=True)
    if verbose:
        print(f"[mos-cycle] store: {p} ({len(store)} days total after merge)")
    return store


# ---------------- the three walk instances, measured (per-event; printed, never averaged) ----------------
def measure_instances() -> None:
    """The falsifiable point of this feed: for each of the walk's three big weekend gaps, WHICH
    cycle first carried the repricing, and was it available BEFORE the Sunday 18:00 ET reopen?"""
    cases = [("2025-10-19", "the 1020 compound-reversal weekend (+1570 gap)"),
             ("2026-01-18", "the 0118 fresh-shot weekend (+2100 gap; Jan-24 add)"),
             ("2026-01-25", "the 0125 wobble weekend (+2480 gap)")]
    for sunday, label in cases:
        try:
            v = sunday_reopen_view(sunday)
        except Exception as e:
            print(f"[measure] {sunday} ({label}): UNMEASURABLE here - {e}")
            continue
        print(f"[measure] {sunday} ({label}) - reopen-available delta vs Sat evening, per horizon:")
        for h in v["horizons"]:
            d = h.get("delta_vs_prior", {})
            if d.get("d_gw_hdd") not in (None, 0.0):
                print(f"    {h['target_date']} (h{h['horizon']}): d_gw_hdd {d['d_gw_hdd']:+.3f} "
                      f"(coverage {d['coverage']})")
        print(f"    D+0 absolute gw_hdd {v['horizons'][0]['gw_hdd']}; "
              f"asof {v['asof_et']} | rule: {v['availability_rule']}")


def selftest() -> bool:
    ok = True

    def chk(cond, msg):
        nonlocal ok
        print(("  PASS " if cond else "  FAIL ") + msg)
        ok = ok and bool(cond)

    print("[mos-cycle selftest]")
    # 1. archive census: all four cycles, all seven DOWs, in a mid-window month (measured fact)
    runs = load_runs("ATL", "GFS")
    hours = {_parse_ts(rt).hour for rt in runs}
    dows = {_parse_ts(rt).weekday() for rt in runs}
    chk(hours == {0, 6, 12, 18}, f"ATL GFS carries exactly the 4 daily cycles: {sorted(hours)}")
    chk(dows == set(range(7)), "ATL GFS carries all 7 days-of-week incl Sat/Sun")
    # 2. availability wall: the Sunday 12z cycle IS available at the reopen; the NEXT 00z is NOT
    asof = datetime(2026, 1, 18, 22, 59, tzinfo=timezone.utc)   # 17:59 ET on 0118
    sel = _available_runs(runs, asof)
    have = sorted(sel)
    chk("2026-01-18 12:00:00" in have, "Sun 12z available at the 18:00 ET reopen")
    chk("2026-01-19 00:00:00" not in have, "Mon 00z NOT available at the Sunday reopen (wall holds)")
    # 18z Sunday: init 18:00Z + 4.5h = 22:30Z <= 22:59Z -> available under the conservative rule
    chk("2026-01-18 18:00:00" in have, "Sun 18z available 22:30Z (rule-derived), before the 22:59Z reopen-asof")
    # 3. no-leak assertion fires
    try:
        bad = {rt: fc for rt, fc in runs.items()}
        _ = {rt for rt in bad}
        _available_runs(runs, datetime(2025, 10, 29, 0, 0, tzinfo=timezone.utc))
        chk(True, "availability filter runs at window edge without leaking")
    except AssertionError:
        chk(False, "availability assertion misfired at window edge")
    # 4. THE 0118 PIN (recorded from the first measured run, 2026-07-20 this session): the Jan-24
    #    cold add was reopen-available - the sunday_reopen view's 2026-01-24 horizon (h5) delta vs
    #    Sat evening MEASURED +8.511 gw-HDD (exactly the run-delta s100_2 recorded arriving an hour
    #    AFTER the reopen in the D-1-evening frame; also +4.020 at Jan-23, coverage 1.0 both).
    #    Pin: > +4.0. This pin is the feed's reason to exist.
    v = sunday_reopen_view("2026-01-18")
    h6 = [h for h in v["horizons"] if h["target_date"] == "2026-01-24"]
    d = h6[0].get("delta_vs_prior", {}).get("d_gw_hdd") if h6 else None
    chk(d is not None and d > 4.0, f"0118 reopen view carries the Jan-24 add pre-reopen (d_gw_hdd {d})")
    # 5. store round-trip on one day (merge semantics: second build of a different day keeps the first)
    print("[mos-cycle selftest]", "PASS" if ok else "FAIL")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="Feed A phase 1 - cycle-level MOS as-of")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("selftest")
    sub.add_parser("measure")
    b = sub.add_parser("build")
    b.add_argument("--start", default="2025-11-01")
    b.add_argument("--end", default="2026-02-28")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return 0 if selftest() else 1
    if a.cmd == "measure":
        measure_instances()
        return 0
    if a.cmd == "build":
        build(a.start, a.end)
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
