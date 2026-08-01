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
import csv
from datetime import datetime, timedelta, timezone
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
# S90: the store lives on AWS S3 (out of git). Bucket/prefix from env (defaults to the bento bucket); the
# feed syncs local <-> S3 so the container and the durable box share ONE store. Local-only if boto3/creds
# absent (graceful fallback).
S3_BUCKET = os.environ.get("NYMEX_S3_BUCKET", "bento-568968024170-us-east-2-an")
S3_KEY = os.environ.get("WEATHER_S3_KEY", "weather/nws_temp/gw_degree_days.json")


def _s3():
    try:
        import boto3
        return boto3.client("s3", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-2"))
    except Exception:
        return None


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


# ------------------------------------------------------------------------------------------------------
# RAW HOURLY ingestion (S90, Greg: "we want hourly ... don't roll temps up into one number - that doesn't
# help us trade daily settle for HH"). Same principle as the raw MBP-10 tape: keep EVERY hourly ob + EVERY
# quantitative field, store raw on S3, aggregate (daily HIGH for KXHIGH, gas-weighted HDD/CDD for HH) ONLY
# on the trade/scoring side. The daily gw_degree_days rollup is a DERIVED convenience, not the store.
# ------------------------------------------------------------------------------------------------------
# Every quantitative ASOS field IEM serves (excludes only the free-text METAR, which breaks CSV and is
# redundant with these parsed fields). Values kept VERBATIM (M=missing, T=trace) - zero reduction.
RAW_ASOS_FIELDS = [
    "tmpf", "dwpf", "relh", "drct", "sknt", "p01i", "alti", "mslp", "vsby", "gust",
    "skyc1", "skyc2", "skyc3", "skyc4", "skyl1", "skyl2", "skyl3", "skyl4", "feel",
    "ice_accretion_1hr", "ice_accretion_3hr", "ice_accretion_6hr",
    "peak_wind_gust", "peak_wind_drct", "peak_wind_time", "snowdepth",
]
# Stations to ingest: the 16 gas-demand metros (HH/NG) UNION the KXHIGH temp-market cities that aren't
# already covered (Austin, San Antonio). NOTE: confirm the exact KXHIGH settlement station per city with
# Greg before trading (e.g. KXHIGHNY settles on Central Park = NYC; KXHIGHCHI may be Midway = MDW).
KXHIGH_EXTRA = ["AUS", "SAT"]
RAW_STATIONS = list(STATION_WEIGHTS_RAW.keys()) + KXHIGH_EXTRA


def fetch_asos_raw(station: str, start: str, end: str, retries: int = 4) -> list[dict]:
    """RAW hourly obs for one station over [start, end) (YYYY-MM-DD, UTC): EVERY quantitative field, EVERY
    row, values verbatim. Returns [{column: value, ...}] with the station id + `valid` UTC timestamp. Zero
    reduction - the trade side parses/aggregates."""
    sy, sm, sd = start.split("-")
    ey, em, ed = end.split("-")
    params = {
        "station": station, "data": RAW_ASOS_FIELDS,
        "year1": sy, "month1": sm, "day1": sd, "year2": ey, "month2": em, "day2": ed,
        "tz": "Etc/UTC", "format": "onlycomma", "missing": "M", "trace": "T",
    }
    last = None
    for i in range(retries):
        try:
            r = requests.get(IEM_URL, params=params, timeout=120)
            if r.status_code == 200 and r.text.strip():
                break
            last = f"status {r.status_code}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(2 ** i)
    else:
        raise RuntimeError(f"[nws] raw {station} {start}..{end} failed: {last}")
    reader = io.StringIO(r.text)
    header = reader.readline().rstrip("\n").split(",")          # station,valid,<fields...>
    rows = []
    for line in reader:
        parts = line.rstrip("\n").split(",")
        if len(parts) < len(header):
            continue
        rows.append(dict(zip(header, parts)))                  # keep ALL columns, raw strings
    return rows


def _months_iter(start: str, end: str):
    sy, sm = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    y, m = sy, sm
    while (y, m) < (ey, em):
        nm = f"{y+1}-01" if m == 12 else f"{y}-{m+1:02d}"
        yield f"{y}-{m:02d}", f"{y}-{m:02d}-01", (f"{y+1}-01-01" if m == 12 else f"{y}-{m+1:02d}-01")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def ingest_hourly_raw(stations: list[str], start: str, end: str, dest: str,
                      scratch: str = "data/nws_hourly", overwrite: bool = False) -> int:
    """Pull RAW hourly obs per (station, month) and store gzipped jsonl to dest, resumable. dest is
    's3://BUCKET/PREFIX' (-> PREFIX/nws_hourly/{station}_{YYYYMM}.jsonl.gz) or a local dir. One line per
    hourly ob, ALL fields verbatim. Skips a (station, month) already present UNLESS overwrite=True (the
    forward-collector mode: re-fetch + overwrite the trailing month(s) so newly-arrived hours are appended
    -- IEM returns the whole month up to now, so overwriting tops it up). Returns rows written."""
    import gzip as _gz
    is_s3 = dest.startswith("s3://")
    if is_s3:
        bkt, _, pfx = dest[len("s3://"):].partition("/")
        pfx = pfx.strip("/")
        s3 = _s3()
    os.makedirs(scratch, exist_ok=True)
    total = 0
    for ym, ms, me in _months_iter(start, end):
        yyyymm = ym.replace("-", "")
        for st in stations:
            name = f"{st}_{yyyymm}.jsonl.gz"
            key = (f"{pfx}/" if is_s3 and pfx else "") + f"nws_hourly/{name}"
            if not overwrite:
                if is_s3:
                    if s3.list_objects_v2(Bucket=bkt, Prefix=key, MaxKeys=1).get("KeyCount", 0):
                        print(f"[nws-raw] skip {st} {ym} (in S3)", flush=True); continue
                else:
                    if os.path.exists(os.path.join(scratch, name)):
                        print(f"[nws-raw] skip {st} {ym} (local)", flush=True); continue
            try:
                rows = fetch_asos_raw(st, ms, me)
            except Exception as e:
                print(f"[nws-raw] ERROR {st} {ym}: {e}", flush=True); continue
            local = os.path.join(scratch, name)
            with _gz.open(local, "wt") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
            total += len(rows)
            if is_s3:
                s3.upload_file(local, bkt, key); os.remove(local)
            print(f"[nws-raw] {st} {ym}: {len(rows)} hourly obs -> {'s3://'+bkt+'/'+key if is_s3 else local}",
                  flush=True)
            time.sleep(0.5)                                    # politeness to IEM
    return total


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
    # S108 THE PARTIAL-TAIL DEFECT. The LAST day of any fetched range is computed on incomplete hours
    # and is WRONG - while still reporting coverage 1.0 and n_stations 16, so nothing downstream can
    # tell. Measured twice on this store:
    #   2026-07-13 was the tail of an earlier pull at gw_cdd 8.034 / regime mod_cool. Fetching
    #     2026-07-14..18 recomputed it to 13.548 / hard_cool - its neighbours are 14.2 and 15.5, so the
    #     8.034 was an anomalous dip and the correction is the real value.
    #   2026-07-17 was the tail of that pull at gw_cdd 15.42 / precip 0.2029. Fetching 2026-07-18..20
    #     recomputed it to 15.14 / precip 0.0002.
    #   2026-07-16, which had a successor day INSIDE its own pull, was byte-identical across both.
    # So a day is trustworthy only once a LATER day has been fetched. Flag the tail rather than dropping
    # it: a silently missing day is the failure mode this project keeps hitting, and a declared one lets
    # state_health refuse the group. cache.update() overwrites, so a later pull CLEARS the flag by
    # itself - the store self-heals as it extends.
    if gw:
        tail = max(gw)
        gw[tail] = {**gw[tail], "provisional_tail": True,
                    "provisional_note": ("LAST DAY OF A FETCH RANGE - computed on incomplete hours and "
                                         "NOT decision-legit. coverage/n_stations do NOT detect this. "
                                         "Re-fetch with at least one day of margin past it to settle it.")}
    if use_cache:
        cache.update(gw)
        _save_cache(cache)
    # return only the requested window (end exclusive)
    return {d: v for d, v in gw.items() if start <= d < end}


def _load_cache() -> dict[str, dict]:
    # local cache first; if absent, pull the store from S3 (out-of-git home) into the local cache.
    if not os.path.exists(CACHE_FILE):
        s3 = _s3()
        if s3 is not None:
            try:
                os.makedirs(CACHE_DIR, exist_ok=True)
                s3.download_file(S3_BUCKET, S3_KEY, CACHE_FILE)
                print(f"[nws] loaded store from s3://{S3_BUCKET}/{S3_KEY}")
            except Exception:
                pass                                    # not in S3 yet -> start empty
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict[str, dict]) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, sort_keys=True, indent=0)
    s3 = _s3()                                          # mirror to S3 (the durable store)
    if s3 is not None:
        try:
            s3.upload_file(CACHE_FILE, S3_BUCKET, S3_KEY)
        except Exception as e:
            print(f"[nws] warning: S3 upload failed ({e}); local cache still written")


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
# (C) HISTORICAL decision-time FORECAST via IEM MOS archive  (S97 JOB 2.2, Greg S96)
#
# WHY: the gas market reprices on what the FORECAST SAID and especially on the RUN-TO-RUN CHANGE in the
# forecast - not on the temperature that actually turned out. Every weather-conditioned brain rule is
# currently tested against realized temps used as a market-knowledge proxy (see _weather_asof /
# "realized_as_proxy_for_forecastable_regime"). That is backwards. This block reconstructs, for each target
# trading day D, what the NWS MOS point forecasts SAID as of the EVENING OF D-1.
#
# SOURCE (verified live, S97): IEM archives NWS MOS point forecasts back to ~2000 at
#   GET https://mesonet.agron.iastate.edu/cgi-bin/request/mos.py
#       ?station=K<4char>&model=<GFS|NAM|MEX|NBS|LAV>&sts=<ISO Z>&ets=<ISO Z>&format=csv
# CSV columns: runtime,ftime,model,n_x,tmp,dpt,cld,wdr,wsp,...,station
#   runtime = model INITIALIZATION time (UTC)  <- the blind-wall key
#   ftime   = valid/forecast time (UTC)
#   tmp     = forecast temperature (F)
# Model codes actually served (probed): GFS = GFS-MOS "MAV" short range (3-hourly, out to ~+72h),
#   NAM = NAM-MOS "MET" (3-hourly, out to ~+84h), MEX = GFS extended MOS (12-hourly, out to ~+192h).
# All 16 gas-demand metros return data for every one of the three models (probed 2026-01-20).
#
# MODEL PREFERENCE (per Greg's directive, extended only where the directive's models cannot reach):
#   GFS (MAV) preferred -> NAM (MET) fallback -> MEX only for horizons MAV/MET physically cannot cover
#   (beyond ~+72/84h, i.e. roughly D+3..D+7). The model actually used is RECORDED PER METRO PER TARGET DAY
#   in `source_by_metro`; nothing is silently substituted.
#
# NORMALS: forecast_vs_normal uses the NWS climatological normals that IEM serves alongside the daily ASOS
# summaries (climo_high_f / climo_low_f from /cgi-bin/request/daily.py). These are published NWS climate
# normals for the station+calendar-day - REAL data, not a synthesized or back-fit baseline.
#
# THE THREE OUTPUTS (all additive, all per-day, never pooled):
#   forecast_gw_hdd / forecast_gw_cdd  - gas-weighted, for target D and each horizon out to D+7
#   forecast_vs_normal                 - the forecast's departure from NWS climatological normal
#   forecast_run_delta                 - THE REPRICING DRIVER: today's run-set (as-of D-1 evening) MINUS
#                                        yesterday's run-set (as-of D-2 evening) for THE SAME TARGET DAYS
#
# THE BLIND WALL (the single most important correctness property here): a target day D may only ever see
# model runs whose `runtime` is <= MOS_CUTOFF(D) = D-1 T23:59Z. In the reference gas-day tz
# (America/Chicago) that instant is 17:59 CT on D-1 - unambiguously the evening of D-1, and it admits the
# 18Z D-1 cycle while EXCLUDING the 00Z-of-D cycle. Enforced by _mos_cutoff_utc + a hard assert in
# _runset_asof, and re-checked in --selftest.
#
# MISSING IS EXPLICIT, NEVER ZERO (non-negotiable): a metro/day/run with no usable MOS coverage yields
# None - never a defaulted 0. A silently-zeroed HDD in January reads to the forecast agent as "no heating
# demand", which is a catastrophic false signal. Weights are renormalized over the metros actually present,
# `coverage` reports the weight fraction retained, and any day below full coverage is flagged
# partial=True with the missing metros NAMED in `metros_missing`.
# ------------------------------------------------------------------------------------------------------
MOS_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/mos.py"
IEM_DAILY_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py"
MOS_DIR = "weather/mos_asof"
MOS_RAW_DIR = os.path.join(MOS_DIR, "raw")
MOS_INDEX = os.path.join(MOS_DIR, "mos_asof_index.json")
MOS_NORMALS = os.path.join(MOS_DIR, "climo_normals.json")
MOS_HORIZONS = 8                      # target D+0 .. D+7
MOS_MODEL_ORDER = ["GFS", "NAM", "MEX"]      # MAV preferred, MET fallback, MEX only where MAV/MET cannot reach
MOS_MIN_OBS = {"GFS": 5, "NAM": 5, "MEX": 2}  # min forecast temps inside the target gas-day to trust it
# IEM daily.py needs the state ASOS network for the climo normals.
STATION_NETWORK = {
    "NYC": "NY_ASOS", "BOS": "MA_ASOS", "PHL": "PA_ASOS", "DCA": "VA_ASOS",
    "ORD": "IL_ASOS", "DTW": "MI_ASOS", "MSP": "MN_ASOS", "STL": "MO_ASOS",
    "IAH": "TX_ASOS", "DFW": "TX_ASOS", "ATL": "GA_ASOS", "DEN": "CO_ASOS",
    "PHX": "AZ_ASOS", "LAX": "CA_ASOS", "SFO": "CA_ASOS", "SEA": "WA_ASOS",
}


def _d(iso: str) -> datetime:
    return datetime.strptime(iso, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _shift(iso: str, days: int) -> str:
    return (_d(iso) + timedelta(days=days)).strftime("%Y-%m-%d")


def _mos_cutoff_utc(target_day: str) -> datetime:
    """THE BLIND WALL. Latest model INITIALIZATION time a forecast for `target_day` may see: D-1 T23:59Z
    (= 17:59 CT on D-1, the evening of D-1 in the gas-day reference tz). Admits the 18Z D-1 cycle,
    excludes the 00Z cycle of D itself."""
    return _d(target_day) - timedelta(minutes=1)


# ---------------- raw MOS fetch (cached to disk; one request per station+model over the whole window) ----
def fetch_mos(station4: str, model: str, sts: str, ets: str, retries: int = 4) -> list[dict]:
    """Raw MOS rows for one station+model over [sts, ets] (YYYY-MM-DD, interpreted UTC). Returns
    [{runtime, ftime, tmp}] with values kept verbatim (empty string = missing, never coerced to 0)."""
    params = {"station": station4, "model": model, "format": "csv",
              "sts": f"{sts}T00:00Z", "ets": f"{ets}T23:59Z"}
    last = None
    for i in range(retries):
        try:
            r = requests.get(MOS_URL, params=params, timeout=120)
            if r.status_code == 200 and r.text.strip():
                break
            last = f"status {r.status_code}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(2 ** i)
    else:
        raise RuntimeError(f"[mos] {station4} {model} {sts}..{ets} failed: {last}")
    rd = list(csv.DictReader(io.StringIO(r.text)))
    out = []
    for row in rd:
        rt, ft, tmp = row.get("runtime", ""), row.get("ftime", ""), (row.get("tmp") or "").strip()
        if not rt or not ft or tmp in ("", "M"):
            continue                                        # missing stays missing; NOT zero
        try:
            out.append({"runtime": rt, "ftime": ft, "tmp": float(tmp)})
        except ValueError:
            continue
    return out


def load_mos_cached(station: str, model: str, sts: str, ets: str, refresh: bool = False) -> list[dict]:
    os.makedirs(MOS_RAW_DIR, exist_ok=True)
    path = os.path.join(MOS_RAW_DIR, f"{station}_{model}_{sts}_{ets}.json")
    if os.path.exists(path) and not refresh:
        with open(path) as f:
            return json.load(f)
    rows = fetch_mos("K" + station, model, sts, ets)
    with open(path, "w") as f:
        json.dump(rows, f)
    time.sleep(0.4)                                          # politeness to IEM
    return rows


def _index_runs(rows: list[dict]) -> dict[str, dict[str, float]]:
    """[{runtime, ftime, tmp}] -> {runtime_iso: {ftime_iso: tmp}}."""
    runs: dict[str, dict[str, float]] = defaultdict(dict)
    for r in rows:
        runs[r["runtime"]][r["ftime"]] = r["tmp"]
    return dict(runs)


def _parse_ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _runset_asof(runs: dict[str, dict[str, float]], cutoff: datetime) -> dict[str, dict[str, float]]:
    """The model cycles a forecaster could have seen in the 24h ENDING at `cutoff` - i.e. the current
    evening's batch. Hard-asserts the blind wall: nothing initialized after `cutoff` may pass."""
    lo = cutoff - timedelta(hours=24)
    sel = {rt: fc for rt, fc in runs.items() if lo < _parse_ts(rt) <= cutoff}
    assert all(_parse_ts(rt) <= cutoff for rt in sel), "BLIND WALL VIOLATION: run initialized after cutoff"
    return sel


def _day_temp_from_run(fcst: dict[str, float], target_day: str, min_obs: int) -> tuple[float, float] | None:
    """(tmax, tmin) the run forecasts for `target_day` in REF_TZ (the gas day) - same max/min convention as
    daily_from_obs, so forecast and realized numbers are directly comparable. None if under-covered."""
    temps = [t for ft, t in fcst.items()
             if _parse_ts(ft).astimezone(REF_TZ).strftime("%Y-%m-%d") == target_day]
    if len(temps) < min_obs:
        return None
    return max(temps), min(temps)


def _station_forecast(runs_by_model: dict[str, dict], target_day: str, cutoff: datetime) -> dict | None:
    """One metro's decision-time forecast for one target day: walk MOS_MODEL_ORDER, take the LATEST
    eligible cycle of the first model that actually covers the day. Records which model won."""
    for model in MOS_MODEL_ORDER:
        runs = runs_by_model.get(model)
        if not runs:
            continue
        sel = _runset_asof(runs, cutoff)
        for rt in sorted(sel, key=_parse_ts, reverse=True):     # latest eligible cycle first
            mm = _day_temp_from_run(sel[rt], target_day, MOS_MIN_OBS[model])
            if mm is None:
                continue
            tmax, tmin = mm
            tmean = (tmax + tmin) / 2.0
            hdd, cdd = degree_days(tmean)
            return {"model": model, "runtime": rt, "tmax": round(tmax, 1), "tmin": round(tmin, 1),
                    "tmean": round(tmean, 2), "hdd": round(hdd, 2), "cdd": round(cdd, 2)}
    return None                                                 # explicit miss - NEVER a zero


def _gas_weight_forecast(per_station: dict[str, dict | None]) -> dict:
    """Gas-weight the per-metro forecast. Renormalizes over metros PRESENT; names the missing ones; flags
    partial. Returns nulls (not zeros) when nothing is available."""
    w = station_weights()
    present = {s: v for s, v in per_station.items() if v is not None}
    missing = sorted(s for s in STATION_WEIGHTS_RAW if s not in present)
    wsum = sum(w[s] for s in present)
    if wsum <= 0:
        return {"gw_hdd": None, "gw_cdd": None, "coverage": 0.0, "n_metros": 0,
                "metros_missing": missing, "partial": True,
                "coverage_note": "NO MOS coverage for any metro - value is null, NOT zero"}
    gw_hdd = sum(w[s] * present[s]["hdd"] for s in present) / wsum
    gw_cdd = sum(w[s] * present[s]["cdd"] for s in present) / wsum
    partial = len(missing) > 0
    return {
        "gw_hdd": round(gw_hdd, 3), "gw_cdd": round(gw_cdd, 3),
        "coverage": round(wsum, 4), "n_metros": len(present),
        "metros_missing": missing, "partial": partial,
        "regime": regime_bucket(gw_hdd, gw_cdd),
        "source_by_metro": {s: f"{present[s]['model']}@{present[s]['runtime']}" for s in sorted(present)},
        "coverage_note": (f"PARTIAL: {len(missing)}/{len(STATION_WEIGHTS_RAW)} metros missing "
                          f"({','.join(missing)}); weights renormalized over the {len(present)} present"
                          if partial else "complete: all 16 gas-demand metros present"),
    }


# ---------------- NWS climatological normals (real, from IEM daily.py climo_high_f/climo_low_f) ----------
def fetch_normals(station: str, sts: str, ets: str, retries: int = 4) -> dict[str, float]:
    """{MM-DD: climo_tmean_F} from the NWS normals IEM serves with the daily ASOS summary."""
    params = {"network": STATION_NETWORK[station], "stations": station, "sts": sts, "ets": ets,
              "format": "comma", "vars": "max_temp_f,min_temp_f"}
    last = None
    for i in range(retries):
        try:
            r = requests.get(IEM_DAILY_URL, params=params, timeout=180)
            if r.status_code == 200 and r.text.strip() and not r.text.startswith("ERROR"):
                break
            last = f"status {r.status_code} {r.text[:60]}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(2 ** i)
    else:
        raise RuntimeError(f"[mos] normals {station} failed: {last}")
    out: dict[str, float] = {}
    for row in csv.DictReader(io.StringIO(r.text)):
        hi, lo, day = (row.get("climo_high_f") or "").strip(), (row.get("climo_low_f") or "").strip(), row.get("day", "")
        if not day or hi in ("", "M", "None") or lo in ("", "M", "None"):
            continue                                        # missing normal stays missing
        try:
            out[day[5:]] = (float(hi) + float(lo)) / 2.0     # key MM-DD
        except ValueError:
            continue
    return out


def load_normals(sts: str, ets: str, refresh: bool = False) -> dict[str, dict[str, float]]:
    os.makedirs(MOS_DIR, exist_ok=True)
    if os.path.exists(MOS_NORMALS) and not refresh:
        with open(MOS_NORMALS) as f:
            return json.load(f)
    out = {}
    for st in STATION_WEIGHTS_RAW:
        try:
            out[st] = fetch_normals(st, sts, ets)
            print(f"[mos] normals {st}: {len(out[st])} calendar days", flush=True)
        except Exception as e:
            print(f"[mos] normals {st} MISSING: {e}", flush=True)   # explicit; not filled with zeros
        time.sleep(0.4)
    with open(MOS_NORMALS, "w") as f:
        json.dump(out, f, sort_keys=True)
    return out


def _gw_normal(target_day: str, normals: dict[str, dict[str, float]]) -> dict:
    """Gas-weighted NWS-normal HDD/CDD for the calendar day. Nulls, never zeros, where normals are absent."""
    w = station_weights()
    mmdd = target_day[5:]
    present = {s: normals[s][mmdd] for s in STATION_WEIGHTS_RAW
               if s in normals and mmdd in normals.get(s, {})}
    missing = sorted(s for s in STATION_WEIGHTS_RAW if s not in present)
    wsum = sum(w[s] for s in present)
    if wsum <= 0:
        return {"gw_hdd": None, "gw_cdd": None, "coverage": 0.0, "metros_missing": missing,
                "coverage_note": "NO NWS normals available - null, NOT zero"}
    hdd = sum(w[s] * degree_days(present[s])[0] for s in present) / wsum
    cdd = sum(w[s] * degree_days(present[s])[1] for s in present) / wsum
    return {"gw_hdd": round(hdd, 3), "gw_cdd": round(cdd, 3), "coverage": round(wsum, 4),
            "metros_missing": missing,
            "coverage_note": ("complete" if not missing else
                              f"PARTIAL normals: missing {','.join(missing)}")}


# ---------------- the assembled as-of state ------------------------------------------------------------
def mos_asof_day(target_day: str, mos: dict[str, dict[str, dict]], normals: dict) -> dict:
    """Everything a forecaster knew about temperature on the EVENING OF D-1, for target day D.

    horizons[h] describes target day D+h as seen by the D-1-evening run batch.
    run_delta[h]  = that same target day D+h, D-1-evening batch MINUS D-2-evening batch (the repricing
                    driver). Computed only over metros present in BOTH batches, with its own coverage.
    """
    cutoff_today = _mos_cutoff_utc(target_day)                  # D-1 T23:59Z
    cutoff_yday = cutoff_today - timedelta(days=1)              # D-2 T23:59Z
    horizons, run_delta = [], []
    for h in range(MOS_HORIZONS):
        tgt = _shift(target_day, h)
        cur = {s: _station_forecast(mos.get(s, {}), tgt, cutoff_today) for s in STATION_WEIGHTS_RAW}
        prv = {s: _station_forecast(mos.get(s, {}), tgt, cutoff_yday) for s in STATION_WEIGHTS_RAW}
        gw_cur = _gas_weight_forecast(cur)
        nrm = _gw_normal(tgt, normals)
        vs_norm = (None if gw_cur["gw_hdd"] is None or nrm["gw_hdd"] is None
                   else round(gw_cur["gw_hdd"] - nrm["gw_hdd"], 3))
        horizons.append({
            "horizon": h, "target_date": tgt,
            "forecast_gw_hdd": gw_cur["gw_hdd"], "forecast_gw_cdd": gw_cur["gw_cdd"],
            "regime": gw_cur.get("regime"),
            "normal_gw_hdd": nrm["gw_hdd"], "normal_gw_cdd": nrm["gw_cdd"],
            "forecast_vs_normal": vs_norm,
            "coverage": gw_cur["coverage"], "n_metros": gw_cur["n_metros"],
            "partial": gw_cur["partial"], "metros_missing": gw_cur["metros_missing"],
            "coverage_note": gw_cur["coverage_note"],
            "source_by_metro": gw_cur.get("source_by_metro", {}),
        })
        # run delta on the COMMON metro set only (so a coverage change cannot masquerade as a forecast change)
        both = [s for s in STATION_WEIGHTS_RAW if cur.get(s) and prv.get(s)]
        w = station_weights(); wsum = sum(w[s] for s in both)
        if wsum <= 0:
            run_delta.append({"horizon": h, "target_date": tgt, "d_gw_hdd": None, "d_gw_cdd": None,
                              "coverage": 0.0, "n_metros": 0, "partial": True,
                              "metros_missing": sorted(set(STATION_WEIGHTS_RAW) - set(both)),
                              "coverage_note": "no metro has BOTH a D-1-evening and a D-2-evening run - "
                                               "delta is null, NOT zero"})
        else:
            d_hdd = sum(w[s] * (cur[s]["hdd"] - prv[s]["hdd"]) for s in both) / wsum
            d_cdd = sum(w[s] * (cur[s]["cdd"] - prv[s]["cdd"]) for s in both) / wsum
            miss = sorted(set(STATION_WEIGHTS_RAW) - set(both))
            run_delta.append({"horizon": h, "target_date": tgt,
                              "d_gw_hdd": round(d_hdd, 3), "d_gw_cdd": round(d_cdd, 3),
                              "coverage": round(wsum, 4), "n_metros": len(both),
                              "partial": bool(miss), "metros_missing": miss,
                              "coverage_note": ("complete: all 16 metros in both batches" if not miss else
                                                f"PARTIAL delta: {len(miss)} metros lack one batch "
                                                f"({','.join(miss)}); common-set weights renormalized")})
    d0, r0 = horizons[0], run_delta[0]
    # the 1..7 day forward block-average is a SHAPE descriptor for the agent, never a final answer (Greg's
    # no-pooling rule): the per-horizon values above are canonical and always carried.
    fwd = [x["forecast_gw_hdd"] for x in horizons[1:] if x["forecast_gw_hdd"] is not None]
    return {
        "date": target_day,
        "asof_utc": cutoff_today.strftime("%Y-%m-%dT%H:%MZ"),
        "asof_note": ("all model runs strictly initialized at or before D-1 T23:59Z (= 17:59 CT on D-1, "
                      "the evening of D-1); the 00Z cycle of D itself is EXCLUDED"),
        "forecast_gw_hdd": d0["forecast_gw_hdd"], "forecast_gw_cdd": d0["forecast_gw_cdd"],
        "forecast_regime": d0["regime"],
        "forecast_vs_normal": d0["forecast_vs_normal"],
        "forecast_run_delta": r0["d_gw_hdd"],
        "forecast_run_delta_cdd": r0["d_gw_cdd"],
        "fwd7_gw_hdd_span": ([min(fwd), max(fwd)] if fwd else None),
        "complete": (not d0["partial"]) and (not r0["partial"]) and d0["forecast_gw_hdd"] is not None,
        "coverage_note": f"D+0 forecast: {d0['coverage_note']} | D+0 run-delta: {r0['coverage_note']}",
        "horizons": horizons,
        "run_delta": run_delta,
    }


def build_mos_asof(start: str, end: str, refresh: bool = False, verbose: bool = True) -> dict:
    """Back-fill the as-of-D-1-evening MOS forecast state for every target day in [start, end).
    Fetches the raw MOS window once per (metro, model), then assembles per-day. Writes MOS_INDEX."""
    fetch_sts = _shift(start, -3)                    # need the D-2 batch for the run delta
    fetch_ets = _shift(end, MOS_HORIZONS + 1)        # need runs valid out to D+7
    mos: dict[str, dict[str, dict]] = {}
    for st in STATION_WEIGHTS_RAW:
        mos[st] = {}
        for model in MOS_MODEL_ORDER:
            try:
                rows = load_mos_cached(st, model, fetch_sts, fetch_ets, refresh=refresh)
                mos[st][model] = _index_runs(rows)
                if verbose:
                    print(f"[mos] {st} {model}: {len(rows)} rows / {len(mos[st][model])} runs", flush=True)
            except Exception as e:
                print(f"[mos] {st} {model} MISSING: {e}", flush=True)     # explicit; no substitution
    normals = load_normals(_shift(start, -1), end, refresh=refresh)
    out = {}
    day = start
    while day < end:
        out[day] = mos_asof_day(day, mos, normals)
        if verbose:
            v = out[day]
            print(f"[mos] {day}  fHDD {v['forecast_gw_hdd']}  vsNorm {v['forecast_vs_normal']}  "
                  f"runDelta {v['forecast_run_delta']}  complete={v['complete']}", flush=True)
        day = _shift(day, 1)
    os.makedirs(MOS_DIR, exist_ok=True)
    with open(MOS_INDEX, "w") as f:
        json.dump(out, f, sort_keys=True, indent=1)
    return out


def mos_selftest() -> bool:
    """Blind wall + missing-is-never-zero + weighting, on synthetic STRUCTURE only (no synthetic market or
    weather values are ever persisted; these are unit fixtures for the join logic)."""
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    cut = _mos_cutoff_utc("2026-01-20")
    check("cutoff is D-1 T23:59Z", cut == datetime(2026, 1, 19, 23, 59, tzinfo=timezone.utc))
    check("cutoff is the evening of D-1 in the gas-day tz (17:59 CT)",
          cut.astimezone(REF_TZ).strftime("%Y-%m-%d %H:%M") == "2026-01-19 17:59")

    runs = {"2026-01-19 18:00:00": {"2026-01-20 12:00:00": 20.0},   # eligible (D-1 18Z)
            "2026-01-20 00:00:00": {"2026-01-20 12:00:00": 99.0},   # LEAK: 00Z of D itself
            "2026-01-18 12:00:00": {"2026-01-20 12:00:00": 10.0}}   # too old for this batch
    sel = _runset_asof(runs, cut)
    check("blind wall drops the 00Z-of-D run", "2026-01-20 00:00:00" not in sel)
    check("blind wall keeps the 18Z D-1 run", "2026-01-19 18:00:00" in sel)
    check("24h batch window drops the D-3 run", "2026-01-18 12:00:00" not in sel)

    # missing is null, never zero
    empty = _gas_weight_forecast({s: None for s in STATION_WEIGHTS_RAW})
    check("no coverage -> gw_hdd is None (NOT 0.0)", empty["gw_hdd"] is None and empty["partial"])
    check("no coverage names every missing metro", len(empty["metros_missing"]) == len(STATION_WEIGHTS_RAW))

    # partial coverage renormalizes and is flagged with named metros
    one = {s: None for s in STATION_WEIGHTS_RAW}
    one["ORD"] = {"model": "GFS", "runtime": "r", "tmax": 20.0, "tmin": 0.0, "tmean": 10.0,
                  "hdd": 55.0, "cdd": 0.0}
    p = _gas_weight_forecast(one)
    check("single-metro partial renormalizes to that metro's value", abs(p["gw_hdd"] - 55.0) < 1e-9)
    check("partial flagged with 15 named missing metros", p["partial"] and len(p["metros_missing"]) == 15)
    check("partial coverage < 1.0", p["coverage"] < 1.0)

    # full coverage
    full = {s: {"model": "GFS", "runtime": "r", "tmax": 40.0, "tmin": 20.0, "tmean": 30.0,
                "hdd": 35.0, "cdd": 0.0} for s in STATION_WEIGHTS_RAW}
    f = _gas_weight_forecast(full)
    check("full coverage -> coverage 1.0, not partial",
          abs(f["coverage"] - 1.0) < 1e-9 and not f["partial"] and abs(f["gw_hdd"] - 35.0) < 1e-9)

    # under-covered target day is a miss, not a fabricated value
    check("under-covered day -> None",
          _day_temp_from_run({"2026-01-20 12:00:00": 30.0}, "2026-01-20", 5) is None)
    return ok


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

    # (C) MOS as-of forecast feed: blind wall + missing-is-never-zero
    print("  -- mos-asof --")
    ok = mos_selftest() and ok

    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="NWS gas-weighted temperature feed for the NG forecaster")
    ap.add_argument("--start", help="YYYY-MM-DD inclusive")
    ap.add_argument("--end", help="YYYY-MM-DD exclusive")
    ap.add_argument("--no-cache", action="store_true", help="do not read/write the local cache")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--forecast", action="store_true", help="live/forward decision-time forecast demo (B)")
    ap.add_argument("--mos-asof", action="store_true",
                    help="(C) back-fill the HISTORICAL decision-time MOS forecast state (as of the EVENING "
                         "OF D-1) for [--start, --end): gas-weighted forecast HDD/CDD out to D+7, departure "
                         "from NWS normal, and the run-to-run delta vs the prior evening's batch. Writes "
                         "weather/mos_asof/.")
    ap.add_argument("--refresh", action="store_true", help="mos-asof: re-fetch instead of using the disk cache")
    ap.add_argument("--ingest-hourly", action="store_true",
                    help="RAW hourly ingestion: pull every quantitative ASOS field per (station,month) and "
                         "store gzipped jsonl (zero reduction) to --dest, resumable. Aggregate on the trade "
                         "side, NOT here.")
    ap.add_argument("--dest", default="s3://bento-568968024170-us-east-2-an/weather",
                    help="ingest-hourly destination: 's3://BUCKET/PREFIX' (-> PREFIX/nws_hourly/) or a local dir")
    ap.add_argument("--stations", default=None,
                    help="comma-separated station ids to ingest (default = the gas-demand metros + KXHIGH "
                         "cities: %s)" % ",".join(RAW_STATIONS))
    ap.add_argument("--overwrite", action="store_true",
                    help="ingest-hourly: re-fetch + overwrite months even if already present (forward-collector "
                         "mode -- tops up the trailing/current month with newly-arrived hours).")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.forecast:
        print(json.dumps(forecast_index_today(), indent=2))
        return 0
    if args.mos_asof:
        if not (args.start and args.end):
            ap.error("--mos-asof needs --start and --end (YYYY-MM-DD)")
        idx = build_mos_asof(args.start, args.end, refresh=args.refresh)
        comp = [d for d in sorted(idx) if idx[d]["complete"]]
        part = [d for d in sorted(idx) if not idx[d]["complete"] and idx[d]["forecast_gw_hdd"] is not None]
        miss = [d for d in sorted(idx) if idx[d]["forecast_gw_hdd"] is None]
        print(f"[mos] DONE {args.start}..{args.end} -> {MOS_INDEX}")
        print(f"[mos] complete={len(comp)} partial={len(part)} missing={len(miss)}")
        if part: print("[mos] PARTIAL days: " + ",".join(part))
        if miss: print("[mos] MISSING days: " + ",".join(miss))
        return 0
    if args.ingest_hourly:
        if not (args.start and args.end):
            ap.error("--ingest-hourly needs --start and --end (YYYY-MM-DD)")
        stations = args.stations.split(",") if args.stations else RAW_STATIONS
        n = ingest_hourly_raw(stations, args.start, args.end, args.dest, overwrite=args.overwrite)
        print(f"[nws-raw] DONE {args.start}..{args.end}: {n} hourly obs across {len(stations)} stations "
              f"-> {args.dest}/nws_hourly/", flush=True)
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
