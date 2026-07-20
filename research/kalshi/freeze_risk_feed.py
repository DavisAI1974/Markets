#!/usr/bin/env python3
"""FEED E (S100, DATA_GATE_S98) - freeze-off risk: producing-basin forecast MIN temps, cycle as-of.

WHY (gate, verbatim): deep cold CUTS SUPPLY (wellhead/gathering freeze-offs) at the same time it
raises demand - extreme-cold days are convex; the brain's weather logic is demand-only and cannot
see this mechanism. The walk's dominant residual (extreme days overshooting bands 2-17x) has this
as a mechanism-level candidate.

TEMPERATURES ONLY - no synthesized production impact, no Bcf estimate; the agent decides what the
numbers mean. Thresholds are EXPOSED AS DATA (20F/15F/10F), never tuned.

Stations (availability VERIFIED in the IEM archive 2026-07-20, 4 cycles/day each; NO
substitutions needed): MAF Midland (Permian), OKC (Anadarko), PIT (Appalachia), SHV (Haynesville).

Cycle discipline is feed A's, verbatim reuse from mos_cycle_feed: availability wall
runtime + 4.5h (conservative; IEM posting stamps unrecoverable - same named limitation), same
weekday_open (08:00 ET) and sunday_reopen (Sun 17:59 ET) views, merge-not-overwrite store.
CAVEAT NAMED: MOS serves 3-hourly temps - the gas-day min of those samples can sit slightly ABOVE
the true overnight low; consistent across days, never corrected synthetically.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nws_temp_feed import fetch_mos, MOS_MODEL_ORDER, MOS_MIN_OBS, REF_TZ
from mos_cycle_feed import _available_runs, _parse_ts, DISSEM_LAG_H, ET

BASINS = {"MAF": "Permian", "OKC": "Anadarko", "PIT": "Appalachia", "SHV": "Haynesville"}
THRESHOLDS_F = [20.0, 15.0, 10.0]         # exposed as data, never tuned
N_HORIZONS = 8
PULL_STS, PULL_ETS = "2025-10-29", "2026-03-09"    # matches feed A's raw archive span

_RAW_CANDIDATES = [os.path.join(HERE, "..", "..", "data", "weather", "mos_freeze", "raw"),
                   os.path.join("data", "weather", "mos_freeze", "raw")]
STORE_CANDIDATES = [os.path.join(HERE, "..", "..", "data", "weather", "mos_freeze"),
                    os.path.join("data", "weather", "mos_freeze")]
STORE_NAME = "freeze_risk_index.json"


def _raw_dir(create: bool = False) -> str:
    for p in _RAW_CANDIDATES:
        if os.path.isdir(p):
            return p
    if create:
        os.makedirs(_RAW_CANDIDATES[0], exist_ok=True)
        return _RAW_CANDIDATES[0]
    raise FileNotFoundError("mos_freeze raw archive absent - run: freeze_risk_feed.py pull")


def _store_path() -> str:
    d = os.path.dirname(_raw_dir(create=True))
    return os.path.join(d, STORE_NAME)


def pull(sts: str = PULL_STS, ets: str = PULL_ETS) -> None:
    """One IEM request per (station, model) over the whole window, cached to the raw dir."""
    import time
    rd = _raw_dir(create=True)
    for st in BASINS:
        for model in MOS_MODEL_ORDER:
            path = os.path.join(rd, f"{st}_{model}_{sts}_{ets}.json")
            if os.path.exists(path):
                print(f"[freeze pull] {st} {model}: cached")
                continue
            rows = fetch_mos("K" + st, model, sts, ets)
            with open(path, "w") as fh:
                json.dump(rows, fh)
            print(f"[freeze pull] {st} {model}: {len(rows)} rows", flush=True)
            time.sleep(0.4)                                    # politeness to IEM


_RUNS_CACHE: dict[tuple[str, str], dict] = {}


def load_runs(station: str, model: str) -> dict[str, dict[str, float]]:
    key = (station, model)
    if key in _RUNS_CACHE:
        return _RUNS_CACHE[key]
    rd = _raw_dir()
    runs: dict[str, dict[str, float]] = defaultdict(dict)
    for fn in sorted(os.listdir(rd)):
        if fn.startswith(f"{station}_{model}_") and fn.endswith(".json"):
            with open(os.path.join(rd, fn)) as fh:
                for r in json.load(fh):
                    t = r.get("tmp")
                    if t is None or t == "":
                        continue
                    runs[r["runtime"]][r["ftime"]] = float(t)
    _RUNS_CACHE[key] = dict(runs)
    return _RUNS_CACHE[key]


def _basin_min(station: str, target_day: str, asof_utc: datetime):
    """Latest AVAILABLE cycle's forecast MIN temp for the gas day, first covering model in order."""
    for model in MOS_MODEL_ORDER:
        runs = load_runs(station, model)
        if not runs:
            continue
        sel = _available_runs(runs, asof_utc)
        for rt in sorted(sel, key=_parse_ts, reverse=True):
            temps = [t for ft, t in sel[rt].items()
                     if _parse_ts(ft).astimezone(REF_TZ).strftime("%Y-%m-%d") == target_day]
            if len(temps) < MOS_MIN_OBS[model]:
                continue
            return {"tmin_f": round(min(temps), 1), "model": model, "runtime": rt}
    return None                                                # explicit miss, never zero


def view(asof_utc: datetime, start_day: str, n_horizons: int = N_HORIZONS) -> dict:
    basins = {}
    for st, name in BASINS.items():
        horizons = []
        for h in range(n_horizons):
            tgt = (datetime.strptime(start_day, "%Y-%m-%d") + timedelta(days=h)).strftime("%Y-%m-%d")
            r = _basin_min(st, tgt, asof_utc)
            horizons.append({"horizon": h, "target_date": tgt,
                             "tmin_f": (r or {}).get("tmin_f"),
                             "cycle": (f"{r['model']}@{r['runtime']}" if r else None)})
        thr_read = {}
        for thr in THRESHOLDS_F:
            subs = [x["target_date"] for x in horizons if x["tmin_f"] is not None and x["tmin_f"] < thr]
            run_max = cur = 0
            prev_ok = False
            for x in horizons:
                is_sub = x["tmin_f"] is not None and x["tmin_f"] < thr
                cur = cur + 1 if (is_sub and prev_ok) else (1 if is_sub else 0)
                run_max = max(run_max, cur)
                prev_ok = is_sub
            thr_read[str(thr)] = {"days_below": len(subs), "max_consecutive": run_max,
                                  "first_below": (subs[0] if subs else None),
                                  "last_below": (subs[-1] if subs else None)}
        stamps = [x["cycle"].split("@")[-1] for x in horizons if x["cycle"]]
        basins[st] = {"basin": name, "horizons": horizons, "thresholds_f": thr_read,
                      "max_cycle_runtime_utc": (max(stamps) if stamps else None)}
    return {"asof_utc": asof_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "asof_et": asof_utc.astimezone(ET).strftime("%Y-%m-%dT%H:%M:%S%z"),
            "availability_rule": f"cycle usable from runtime + {DISSEM_LAG_H}h (feed A rule, reused)",
            "start_day": start_day, "basins": basins,
            "note": ("producing-basin forecast MIN temps only; thresholds are data (20/15/10F), "
                     "never tuned; 3-hourly MOS sampling can sit slightly above the true low - "
                     "consistent across days, uncorrected")}


def weekday_open_view(day: str) -> dict:
    d = datetime.strptime(day, "%Y-%m-%d")
    v = view(d.replace(hour=8, minute=0, tzinfo=ET).astimezone(timezone.utc), day)
    v["view"] = "weekday_open"
    return v


def sunday_reopen_view(sunday: str) -> dict:
    d = datetime.strptime(sunday, "%Y-%m-%d")
    assert d.weekday() == 6, f"{sunday} is not a Sunday"
    monday = (d + timedelta(days=1)).strftime("%Y-%m-%d")
    v = view(d.replace(hour=17, minute=59, tzinfo=ET).astimezone(timezone.utc), monday)
    v["view"] = "sunday_reopen"
    return v


def freeze_risk_asof(day: str) -> dict | None:
    p = _store_path()
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        return json.load(fh).get(day)


def build(start: str, end: str, verbose: bool = True) -> dict:
    """MERGES into any existing store (feed A trap #1 discipline)."""
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
        if day.weekday() == 0:
            rec["sunday_reopen"] = sunday_reopen_view((day - timedelta(days=1)).strftime("%Y-%m-%d"))
        store[iso] = rec
        if verbose:
            mins = {st: b["horizons"][0]["tmin_f"] for st, b in rec["weekday_open"]["basins"].items()}
            print(f"[freeze] {iso}  D+0 mins {mins}", flush=True)
        day += timedelta(days=1)
    with open(p, "w") as fh:
        json.dump(store, fh, sort_keys=True)
    if verbose:
        print(f"[freeze] store: {p} ({len(store)} days total after merge)")
    return store


def measure() -> None:
    """The G11 freeze window, measured per-event (printed, never averaged): what did each basin's
    cycle-available forecast MIN show into the mid-January cold?"""
    for day in ["2026-01-12", "2026-01-15", "2026-01-17", "2026-01-19", "2026-01-22"]:
        try:
            v = weekday_open_view(day)
        except Exception as e:
            print(f"[measure] {day}: {e}")
            continue
        line = []
        for st, b in v["basins"].items():
            t = b["horizons"][0]["tmin_f"]
            t20 = b["thresholds_f"]["20.0"]
            line.append(f"{st} D+0 {t}F (sub-20F days={t20['days_below']} "
                        f"first={t20['first_below']})")
        print(f"[measure] {day}: " + " | ".join(line))


def selftest() -> bool:
    ok = True

    def chk(cond, msg):
        nonlocal ok
        print(("  PASS " if cond else "  FAIL ") + msg)
        ok = ok and bool(cond)

    print("[freeze selftest]")
    runs = load_runs("MAF", "GFS")
    hours = {_parse_ts(rt).hour for rt in runs}
    chk(hours == {0, 6, 12, 18}, f"MAF GFS carries all 4 cycles: {sorted(hours)}")
    v = weekday_open_view("2026-01-19")
    chk(set(v["basins"]) == set(BASINS), "all 4 basins present on 2026-01-19")
    for st, b in v["basins"].items():
        rtmax = b["max_cycle_runtime_utc"]
        chk(rtmax is not None and rtmax <= "2026-01-19 06:00:00",
            f"{st} newest cycle {rtmax} respects the 08:00 ET wall (06z+4.5h=10:30Z=05:30ET, eligible)")
    # PINS (recorded from the FIRST MEASURED run, 2026-07-20 this session - measured before pinned):
    # 2026-01-19 weekday-open D+0 mins: MAF 31.0F, OKC 26.0F, PIT 10.0F, SHV 28.0F. The 0119
    # freeze is APPALACHIAN (PIT 10F, 7 consecutive sub-20F days from Jan-19); the Permian/
    # Haynesville freeze arrives in the HORIZON: by 0122 both show sub-20F from Jan-24 - the
    # supply-side signal into the squeeze week (cash blowout Jan 23, the 0130 17x day).
    mins = {st: b["horizons"][0]["tmin_f"] for st, b in v["basins"].items()}
    chk(mins["PIT"] == 10.0, f"0119 Appalachia deep-freeze pin (PIT {mins['PIT']}F == 10.0)")
    chk(mins["MAF"] == 31.0 and mins["OKC"] == 26.0 and mins["SHV"] == 28.0,
        f"0119 basin mins pin (MAF/OKC/SHV {mins['MAF']}/{mins['OKC']}/{mins['SHV']})")
    t20 = v["basins"]["PIT"]["thresholds_f"]["20.0"]
    chk(t20["days_below"] == 7 and t20["first_below"] == "2026-01-19",
        f"0119 PIT 7 sub-20F days from Jan-19 pin ({t20})")
    v22 = weekday_open_view("2026-01-22")
    maf22 = v22["basins"]["MAF"]["thresholds_f"]["20.0"]
    shv22 = v22["basins"]["SHV"]["thresholds_f"]["20.0"]
    chk(maf22["days_below"] == 3 and maf22["first_below"] == "2026-01-24",
        f"0122 Permian sub-20F from Jan-24 pin ({maf22})")
    chk(shv22["days_below"] == 3 and shv22["first_below"] == "2026-01-24",
        f"0122 Haynesville sub-20F from Jan-24 pin ({shv22})")
    thr = v["basins"]["MAF"]["thresholds_f"]
    chk(set(thr) == {"20.0", "15.0", "10.0"}, "thresholds exposed as data (20/15/10F)")
    print("[freeze selftest]", "PASS" if ok else "FAIL")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="Feed E - freeze-off basin temps (cycle as-of)")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("pull")
    sub.add_parser("selftest")
    sub.add_parser("measure")
    b = sub.add_parser("build")
    b.add_argument("--start", default="2025-11-01")
    b.add_argument("--end", default="2026-02-28")
    a = ap.parse_args()
    if a.cmd == "pull":
        pull(); return 0
    if a.cmd == "selftest":
        return 0 if selftest() else 1
    if a.cmd == "measure":
        measure(); return 0
    if a.cmd == "build":
        build(a.start, a.end); return 0
    ap.print_help(); return 0


if __name__ == "__main__":
    sys.exit(main())
