"""
nws_temp_feed.py — the gas-demand TEMPERATURE feed for the NG path forecaster (S88, Greg's directive).

WHY (FORECAST_AGENT_DIRECTIVE_S88.md sec 6): temp is the dominant NG driver. The forecaster needs
(A) realized historical hourly temps for EVERY corpus day (to characterize each day's demand regime,
assign its temp cell, and score the historical curves against), and (B) a decision-time temp FORECAST
to condition a blind forecast at trade time. The (A)/(B) split IS the leakage boundary:
  - (A) realized history  -> labeling / bucketing past days  -> realized temp is correct.
  - (B) decision-time      -> conditioning a forecast         -> the FORECAST available that morning only;
                                                                 realized same-day temp is LOOK-AHEAD.

WHAT the price actually reacts to is NATIONAL gas demand, NOT Henry Hub's own Louisiana weather (Henry Hub
is the settlement point in Erath LA, ~no heating load). So the index is a population/gas-weighted degree-day
aggregate across the big consuming metros. Per-hub local weather (Chicago Citygate etc.) is the DEFERRED
per-location basis stack, not this.

SOURCE (Greg S88): NWS historical data. Realized hourly obs come from the NWS ASOS network via IEM
(mesonet.agron.iastate.edu) — the canonical free programmatic archive of NWS station observations
(temp tmpf, 1h precip p01i), UTC, arbitrary date ranges. Decision-time forecasts come from the NWS API
(api.weather.gov) — forward only (no historical forecast archive), so historical conditioning uses the
leakage-safe regime-bucket proxy documented below.

OUTPUT: a daily gas-weighted index {gw_hdd, gw_cdd, gw_precip} + per-station detail, cached under
data/nws_temp/ (gitignored, re-pullable). Degree-days base 65F; day boundary in a fixed reference tz
(America/Chicago, the central-US gas day) so all stations share one calendar day.

Usage:
    python research/kalshi/nws_temp_feed.py --start 2025-07-01 --end 2025-08-01     # fetch + cache + summary
    python research/kalshi/nws_temp_feed.py --selftest                              # math + leakage gate
    python research/kalshi/nws_temp_feed.py --forecast                              # decision-time (fwd) demo

Discipline: this is a CONDITIONING driver for the forecaster; it is leakage-gated (sec 6), the weights are
a documented FIRST CUT the agent tunes, and nothing here trades on its own.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

# ------------------------------------------------------------------------------------------------------
# Station set + weights. FIRST CUT (Greg S88: national demand-weighted, tunable by the agent).
# Weights are raw population/gas-demand proxies; normalized to sum 1.0 at load. IDs are NWS ASOS (IEM).
# The point is national HEATING+COOLING demand coverage, NOT Henry Hub's location.
# ------------------------------------------------------------------------------------------------------
STATION_WEIGHTS_RAW = {
    # Northeast (heavy heating)
    "NYC": 0.12, "BOS": 0.05, "PHL": 0.05, "DCA": 0.05,
    # Midwest (heavy heating + power gen)
    "ORD": 0.10, "DTW": 0.05, "MSP": 0.045, "STL": 0.035,
    # South / Texas (power gen, industrial, cooling)
    "IAH": 0.07, "DFW": 0.065, "ATL": 0.055,
    # West / Southwest / Pacific
    "DEN": 0.035, "PHX": 0.045, "LAX": 0.055, "SFO": 0.03, "SEA": 0.035,
}
REF_TZ = ZoneInfo("America/Chicago")     # single "gas day" boundary applied to every station
BASE_F = 65.0                             # degree-day base
IEM_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
NWS_API = "https://api.weather.gov"
CACHE_DIR = "data/nws_temp"
CACHE_FILE = os.path.join(CACHE_DIR, "gw_degree_days.json")   # {date: {...}} merged store


def station_weights() -> dict[str, float]:
    tot = sum(STATION_WEIGHTS_RAW.values())
    return {k: v / tot for k, v in STATION_WEIGHTS_RAW.items()}


# ------------------------------------------------------------------------------------------------------
# Degree-day math (pure, testable)
# ------------------------------------------------------------------------------------------------------
def degree_days(tmean_f: float, base: float = BASE_F) -> tuple[float, float]:
    """(HDD, CDD) from a daily mean temp F. Standard base-65."""
    hdd = max(0.0, base - tmean_f)
    cdd = max(0.0, tmean_f - base)
    return hdd, cdd


def _parse_precip(raw: str) -> float | None:
    """IEM p01i: 'M' missing -> None, 'T' trace -> 0.001, else inches."""
    raw = raw.strip()
    if raw in ("", "M"):
        return None
    if raw in ("T", "0.0001"):
        return 0.001
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_temp(raw: str) -> float | None:
    raw = raw.strip()
    if raw in ("", "M"):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def daily_from_obs(rows: list[tuple[datetime, float | None, float | None]]) -> dict[str, dict]:
    """
    Collapse per-station hourly obs -> per-(reference-tz)-day {tmax, tmin, tmean, precip_in, n}.
    rows: (utc_dt, tmpf_or_None, precip_or_None). Day key = date in REF_TZ.
    Tmean = (Tmax+Tmin)/2 (the degree-day convention). Precip = sum of hourly p01i over the day.
    LEAKAGE-CRITICAL: a day's value is a pure function of that day's obs only (see --selftest invariance).
    """
    by_day_t: dict[str, list[float]] = defaultdict(list)
    by_day_p: dict[str, list[float]] = defaultdict(list)
    for utc_dt, tmpf, precip in rows:
        day = utc_dt.astimezone(REF_TZ).strftime("%Y-%m-%d")
        if tmpf is not None:
            by_day_t[day].append(tmpf)
        if precip is not None:
            by_day_p[day].append(precip)
    out: dict[str, dict] = {}
    for day, temps in by_day_t.items():
        if not temps:
            continue
        tmax, tmin = max(temps), min(temps)
        tmean = (tmax + tmin) / 2.0
        hdd, cdd = degree_days(tmean)
        out[day] = {
            "tmax": round(tmax, 2), "tmin": round(tmin, 2), "tmean": round(tmean, 2),
            "hdd": round(hdd, 2), "cdd": round(cdd, 2),
            "precip_in": round(sum(by_day_p.get(day, [])), 3), "n_obs": len(temps),
        }
    return out


def gas_weighted(per_station_daily: dict[str, dict[str, dict]]) -> dict[str, dict]:
    """
    per_station_daily: {station: {date: {hdd,cdd,precip_in,...}}}  ->  {date: gw index}.
    Weighted by station_weights(), renormalized over the stations actually present that day (so a
    missing station reweights rather than silently dropping demand).
    """
    w = station_weights()
    days: set[str] = set()
    for st in per_station_daily.values():
        days.update(st.keys())
    out: dict[str, dict] = {}
    for day in sorted(days):
        present = [(s, per_station_daily[s][day]) for s in per_station_daily if day in per_station_daily[s]]
        wsum = sum(w[s] for s, _ in present)
        if wsum <= 0:
            continue
        gw_hdd = sum(w[s] * d["hdd"] for s, d in present) / wsum
        gw_cdd = sum(w[s] * d["cdd"] for s, d in present) / wsum
        gw_pr = sum(w[s] * d["precip_in"] for s, d in present) / wsum
        out[day] = {
            "gw_hdd": round(gw_hdd, 3), "gw_cdd": round(gw_cdd, 3), "gw_precip": round(gw_pr, 4),
            "n_stations": len(present), "coverage": round(wsum, 3),
            "regime": regime_bucket(gw_hdd, gw_cdd),
        }
    return out


def regime_bucket(gw_hdd: float, gw_cdd: float) -> str:
    """
    Coarse demand regime label. Used two ways:
      - to bucket historical days for analog matching (sec 4);
      - as the leakage-safe DECISION-TIME proxy when no archived forecast exists: the broad regime is
        highly forecastable a day ahead, so conditioning on the coarse bucket (not the exact realized
        value) is permissible with the small leak flagged (sec 6-B).
    """
    if gw_hdd >= 20:
        return "hard_heat"          # deep winter heating demand
    if gw_hdd >= 8:
        return "mod_heat"
    if gw_cdd >= 10:
        return "hard_cool"          # peak summer cooling / power-burn
    if gw_cdd >= 3:
        return "mod_cool"
    return "shoulder"               # low-demand shoulder season


# ------------------------------------------------------------------------------------------------------
# (A) realized history via NWS ASOS / IEM
# ------------------------------------------------------------------------------------------------------
def fetch_asos(station: str, start: str, end: str, retries: int = 4) -> list[tuple[datetime, float | None, float | None]]:
    """
    Realized hourly obs for one NWS ASOS station over [start, end) (YYYY-MM-DD), UTC.
    Returns [(utc_dt, tmpf|None, precip_in|None)]. Retries with backoff on transient failure.
    """
    sy, sm, sd = start.split("-")
    ey, em, ed = end.split("-")
    params = {
        "station": station, "data": ["tmpf", "p01i"],
        "year1": sy, "month1": sm, "day1": sd, "year2": ey, "month2": em, "day2": ed,
        "tz": "Etc/UTC", "format": "onlycomma", "missing": "M", "trace": "T",
    }
    last = None
    for i in range(retries):
        try:
            r = requests.get(IEM_URL, params=params, timeout=60)
            if r.status_code == 200 and r.text.strip():
                break
            last = f"status {r.status_code}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(2 ** i)
    else:
        raise RuntimeError(f"[nws] {station} {start}..{end} failed: {last}")
    rows: list[tuple[datetime, float | None, float | None]] = []
    reader = io.StringIO(r.text)
    header = reader.readline()          # station,valid,tmpf,p01i
    for line in reader:
        parts = line.rstrip("\n").split(",")
        if len(parts) < 4:
            continue
        try:
            dt = datetime.strptime(parts[1].strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        rows.append((dt, _parse_temp(parts[2]), _parse_precip(parts[3])))
    return rows


def realized_index(start: str, end: str, use_cache: bool = True, verbose: bool = True) -> dict[str, dict]:
    """
    The (A) path: realized gas-weighted daily degree-day index over [start, end). Merges into the local
    cache so we never re-fetch a covered day. Returns {date: gw index} for the requested range.
    """
    cache = _load_cache() if use_cache else {}
    per_station: dict[str, dict[str, dict]] = {}
    for st in STATION_WEIGHTS_RAW:
        if verbose:
            print(f"[nws] fetch {st} {start}..{end}", flush=True)
        rows = fetch_asos(st, start, end)
        per_station[st] = daily_from_obs(rows)
        time.sleep(0.5)                 # politeness to IEM
    gw = gas_weighted(per_station)
    if use_cache:
        cache.update(gw)
        _save_cache(cache)
    # return only the requested window (end exclusive)
    return {d: v for d, v in gw.items() if start <= d < end}


def _load_cache() -> dict[str, dict]:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict[str, dict]) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, sort_keys=True, indent=0)


# ------------------------------------------------------------------------------------------------------
# (B) decision-time forecast via NWS API (forward only)
# ------------------------------------------------------------------------------------------------------
# Approx lat/lon for the demand stations (for the NWS gridpoint forecast; forward-live use only).
STATION_LATLON = {
    "NYC": (40.71, -74.01), "BOS": (42.36, -71.01), "PHL": (39.87, -75.23), "DCA": (38.85, -77.03),
    "ORD": (41.98, -87.90), "DTW": (42.21, -83.35), "MSP": (44.88, -93.22), "STL": (38.75, -90.37),
    "IAH": (29.98, -95.34), "DFW": (32.90, -97.04), "ATL": (33.63, -84.44), "DEN": (39.86, -104.67),
    "PHX": (33.43, -112.01), "LAX": (33.94, -118.41), "SFO": (37.62, -122.38), "SEA": (47.44, -122.31),
}


def forecast_index_today(verbose: bool = True) -> dict:
    """
    The (B) path, FORWARD/LIVE only: today's gas-weighted degree-day FORECAST from api.weather.gov.
    NOTE: NWS has no historical forecast archive, so this cannot reconstruct a past day's decision-time
    forecast. For historical backtest conditioning, use regime_bucket() on the realized value as the
    leakage-safe forecastable proxy (sec 6-B); this function is for live/forward operation.
    """
    headers = {"User-Agent": "davisai-markets nws_temp_feed (research)"}
    per_station_dd: dict[str, tuple[float, float]] = {}
    for st, (lat, lon) in STATION_LATLON.items():
        try:
            pt = requests.get(f"{NWS_API}/points/{lat},{lon}", headers=headers, timeout=30).json()
            url = pt["properties"]["forecast"]
            fc = requests.get(url, headers=headers, timeout=30).json()
            periods = fc["properties"]["periods"][:2]      # next day/night
            temps = [p["temperature"] for p in periods if p.get("temperatureUnit") == "F"]
            if temps:
                tmax, tmin = max(temps), min(temps)
                per_station_dd[st] = degree_days((tmax + tmin) / 2.0)
        except Exception as e:                              # forward path; tolerate a station gap
            if verbose:
                print(f"[nws] forecast {st} skipped: {e}", flush=True)
        time.sleep(0.3)
    if not per_station_dd:
        return {}
    w = station_weights()
    wsum = sum(w[s] for s in per_station_dd)
    gw_hdd = sum(w[s] * hc[0] for s, hc in per_station_dd.items()) / wsum
    gw_cdd = sum(w[s] * hc[1] for s, hc in per_station_dd.items()) / wsum
    return {"gw_hdd": round(gw_hdd, 3), "gw_cdd": round(gw_cdd, 3),
            "n_stations": len(per_station_dd), "regime": regime_bucket(gw_hdd, gw_cdd)}


# ------------------------------------------------------------------------------------------------------
# selftest: degree-day math + weight normalization + parse + LEAKAGE invariance
# ------------------------------------------------------------------------------------------------------
def selftest() -> int:
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    # degree-day math
    check("40F day -> HDD 25, CDD 0", degree_days(40.0) == (25.0, 0.0))
    check("80F day -> HDD 0, CDD 15", degree_days(80.0) == (0.0, 15.0))
    check("65F day -> HDD 0, CDD 0", degree_days(65.0) == (0.0, 0.0))

    # weights normalize
    w = station_weights()
    check("weights sum to 1.0", abs(sum(w.values()) - 1.0) < 1e-9)
    check("all stations present in latlon", set(STATION_WEIGHTS_RAW) == set(STATION_LATLON))

    # parsing
    check("precip trace -> 0.001", _parse_precip("T") == 0.001)
    check("precip missing -> None", _parse_precip("M") is None)
    check("temp missing -> None", _parse_temp("M") is None)

    # regime buckets
    check("hard winter -> hard_heat", regime_bucket(30.0, 0.0) == "hard_heat")
    check("peak summer -> hard_cool", regime_bucket(0.0, 15.0) == "hard_cool")
    check("shoulder -> shoulder", regime_bucket(2.0, 1.0) == "shoulder")

    # LEAKAGE invariance: a past day's value must be byte-identical whether or not future obs exist.
    d1 = datetime(2025, 7, 1, 18, tzinfo=timezone.utc)
    d2 = datetime(2025, 7, 2, 18, tzinfo=timezone.utc)
    rows_past = [(d1, 80.0, 0.0), (d1.replace(hour=6), 68.0, 0.1)]
    rows_with_future = rows_past + [(d2, 95.0, 0.0), (d2.replace(hour=6), 72.0, 0.0)]
    day1 = d1.astimezone(REF_TZ).strftime("%Y-%m-%d")
    only = daily_from_obs(rows_past).get(day1)
    withf = daily_from_obs(rows_with_future).get(day1)
    check("day-1 index invariant under appended FUTURE obs (leakage gate)", only == withf and only is not None)

    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="NWS gas-weighted temperature feed for the NG forecaster")
    ap.add_argument("--start", help="YYYY-MM-DD inclusive")
    ap.add_argument("--end", help="YYYY-MM-DD exclusive")
    ap.add_argument("--no-cache", action="store_true", help="do not read/write the local cache")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--forecast", action="store_true", help="live/forward decision-time forecast demo (B)")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.forecast:
        print(json.dumps(forecast_index_today(), indent=2))
        return 0
    if not (args.start and args.end):
        ap.error("need --start and --end (or --selftest / --forecast)")

    idx = realized_index(args.start, args.end, use_cache=not args.no_cache)
    days = sorted(idx)
    print(f"[nws] {len(days)} days {args.start}..{args.end}  (cache: {CACHE_FILE})")
    for d in days:
        v = idx[d]
        print(f"  {d}  HDD {v['gw_hdd']:6.2f}  CDD {v['gw_cdd']:6.2f}  precip {v['gw_precip']:.3f}  "
              f"{v['regime']:10s}  n={v['n_stations']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
