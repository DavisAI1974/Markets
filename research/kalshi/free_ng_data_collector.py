#!/usr/bin/env python3
"""Collect free public drivers for Henry Hub NG and CME event-contract research.

Sources:
- EIA API v2: weekly working gas and hourly grid operating data.
- NOAA/NWS API: hourly point forecasts and active alerts for gas-demand regions.

The collector writes one atomic JSON snapshot and optionally mirrors it to S3.
It is intentionally independent of Databento historical and live jobs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

EIA_BASE = "https://api.eia.gov/v2"
NWS_BASE = "https://api.weather.gov"
USER_AGENT = os.getenv("NWS_USER_AGENT", "DavisAI-Markets/1.0 (research; contact: operations@davisai.ai)")

STATIONS: dict[str, tuple[float, float, float]] = {
    "NYC": (40.71, -74.01, 0.12), "BOS": (42.36, -71.01, 0.05),
    "PHL": (39.87, -75.23, 0.05), "DCA": (38.85, -77.03, 0.05),
    "ORD": (41.98, -87.90, 0.10), "DTW": (42.21, -83.35, 0.05),
    "MSP": (44.88, -93.22, 0.045), "STL": (38.75, -90.37, 0.035),
    "IAH": (29.98, -95.34, 0.07), "DFW": (32.90, -97.04, 0.065),
    "ATL": (33.63, -84.44, 0.055), "DEN": (39.86, -104.67, 0.035),
    "PHX": (33.43, -112.01, 0.045), "LAX": (33.94, -118.41, 0.055),
    "SFO": (37.62, -122.38, 0.03), "SEA": (47.44, -122.31, 0.035),
}
DEMAND_BAS = ["ERCO", "MISO", "PJM", "SWPP", "CISO", "ISNE", "NYIS", "TVA", "SOCO"]
ALERT_AREAS = ["TX", "LA", "OK", "PA", "NY", "MA", "IL", "MI", "MN", "GA", "CA", "WA"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def get_json(url: str, *, params: dict[str, Any] | list[tuple[str, Any]] | None = None,
             headers: dict[str, str] | None = None, timeout: int = 60,
             retries: int = 3) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            last = error
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"GET failed {url}: {last}")


def eia_data(route: str, key: str, *, frequency: str, length: int,
             facets: dict[str, list[str]] | None = None,
             start: str | None = None) -> list[dict[str, Any]]:
    params: list[tuple[str, Any]] = [
        ("api_key", key), ("frequency", frequency), ("data[0]", "value"),
        ("sort[0][column]", "period"), ("sort[0][direction]", "desc"),
        ("offset", 0), ("length", length),
    ]
    if start:
        params.append(("start", start))
    for facet, values in (facets or {}).items():
        params.extend((f"facets[{facet}][]", value) for value in values)
    payload = get_json(f"{EIA_BASE}/{route}/data/", params=params)
    response = payload.get("response") or {}
    warning = response.get("warning")
    if warning:
        print(f"[free-ng] EIA warning {route}: {warning}", file=sys.stderr)
    return response.get("data") or []


def collect_eia(key: str) -> dict[str, Any]:
    storage_rows = eia_data(
        "natural-gas/stor/wkly", key, frequency="weekly", length=8,
        facets={"series": ["NW2_EPG0_SWO_R48_BCF"]},
    )
    storage = []
    for row in storage_rows:
        try:
            storage.append({"period": row["period"], "working_gas_bcf": float(row["value"])})
        except (KeyError, TypeError, ValueError):
            continue
    storage.sort(key=lambda row: row["period"], reverse=True)
    latest_storage = storage[0] if storage else None
    if len(storage) >= 2:
        latest_storage = dict(latest_storage or {})
        latest_storage["weekly_change_bcf"] = round(storage[0]["working_gas_bcf"] - storage[1]["working_gas_bcf"], 3)

    start = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H")
    region_rows = eia_data(
        "electricity/rto/region-data", key, frequency="hourly", length=5000,
        facets={"respondent": DEMAND_BAS, "type": ["D", "DF", "NG", "TI"]}, start=start,
    )
    fuel_rows = eia_data(
        "electricity/rto/fuel-type-data", key, frequency="hourly", length=5000,
        facets={"respondent": DEMAND_BAS}, start=start,
    )

    latest_period = max((str(row.get("period")) for row in region_rows if row.get("period")), default=None)
    latest_region = [row for row in region_rows if str(row.get("period")) == latest_period]
    latest_fuel_period = max((str(row.get("period")) for row in fuel_rows if row.get("period")), default=None)
    latest_fuel = [row for row in fuel_rows if str(row.get("period")) == latest_fuel_period]

    def sum_fuel(code: str) -> float | None:
        values = []
        for row in latest_fuel:
            if str(row.get("type-name") or row.get("fueltype") or row.get("type")) == code:
                try:
                    values.append(float(row["value"]))
                except (KeyError, TypeError, ValueError):
                    pass
        return round(sum(values), 3) if values else None

    return {
        "storage": {"latest": latest_storage, "recent": storage},
        "grid": {
            "region_period": latest_period,
            "region_rows": latest_region,
            "fuel_period": latest_fuel_period,
            "fuel_rows": latest_fuel,
            "derived": {
                "gas_generation_mwh": sum_fuel("Natural gas"),
                "wind_generation_mwh": sum_fuel("Wind"),
                "solar_generation_mwh": sum_fuel("Solar"),
                "coal_generation_mwh": sum_fuel("Coal"),
                "nuclear_generation_mwh": sum_fuel("Nuclear"),
            },
        },
    }


def forecast_periods(lat: float, lon: float, session: requests.Session) -> list[dict[str, Any]]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
    points = session.get(f"{NWS_BASE}/points/{lat},{lon}", headers=headers, timeout=30)
    points.raise_for_status()
    hourly_url = points.json()["properties"]["forecastHourly"]
    forecast = session.get(hourly_url, headers=headers, timeout=30)
    forecast.raise_for_status()
    periods = forecast.json()["properties"]["periods"]
    keep = []
    for period in periods[:168]:
        keep.append({
            "startTime": period.get("startTime"),
            "temperature": period.get("temperature"),
            "temperatureUnit": period.get("temperatureUnit"),
            "windSpeed": period.get("windSpeed"),
            "windDirection": period.get("windDirection"),
            "shortForecast": period.get("shortForecast"),
            "probabilityOfPrecipitation": (period.get("probabilityOfPrecipitation") or {}).get("value"),
            "dewpoint_c": (period.get("dewpoint") or {}).get("value"),
            "relativeHumidity": (period.get("relativeHumidity") or {}).get("value"),
        })
    return keep


def collect_nws() -> dict[str, Any]:
    session = requests.Session()
    station_data: dict[str, Any] = {}
    errors: dict[str, str] = {}
    total_weight = sum(v[2] for v in STATIONS.values())
    weights = {station: weight / total_weight for station, (_, _, weight) in STATIONS.items()}
    first_day_hdd = 0.0
    first_day_cdd = 0.0
    coverage = 0.0
    for station, (lat, lon, _) in STATIONS.items():
        try:
            periods = forecast_periods(lat, lon, session)
            station_data[station] = {"lat": lat, "lon": lon, "hourly": periods}
            temps = [float(p["temperature"]) for p in periods[:24]
                     if p.get("temperature") is not None and p.get("temperatureUnit") == "F"]
            if temps:
                mean = sum(temps) / len(temps)
                w = weights[station]
                first_day_hdd += w * max(0.0, 65.0 - mean)
                first_day_cdd += w * max(0.0, mean - 65.0)
                coverage += w
        except Exception as error:
            errors[station] = repr(error)
        time.sleep(0.15)

    alerts: list[dict[str, Any]] = []
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
    for area in ALERT_AREAS:
        try:
            response = session.get(f"{NWS_BASE}/alerts/active", params={"area": area}, headers=headers, timeout=30)
            response.raise_for_status()
            for feature in response.json().get("features", []):
                props = feature.get("properties") or {}
                alerts.append({
                    "area": area, "id": props.get("id"), "event": props.get("event"),
                    "severity": props.get("severity"), "urgency": props.get("urgency"),
                    "certainty": props.get("certainty"), "onset": props.get("onset"),
                    "expires": props.get("expires"), "headline": props.get("headline"),
                    "areaDesc": props.get("areaDesc"),
                })
        except Exception as error:
            errors[f"alerts:{area}"] = repr(error)
        time.sleep(0.1)

    if coverage:
        first_day_hdd /= coverage
        first_day_cdd /= coverage
    return {
        "gas_weighted_next_24h": {
            "hdd65": round(first_day_hdd, 3) if coverage else None,
            "cdd65": round(first_day_cdd, 3) if coverage else None,
            "weight_coverage": round(coverage, 4),
            "station_count": len(station_data),
        },
        "stations": station_data,
        "alerts": alerts,
        "errors": errors,
    }


def upload_s3(path: Path, bucket: str, key: str) -> None:
    import boto3
    boto3.client("s3", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-2")).upload_file(str(path), bucket, key)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.getenv("FREE_NG_OUT", "/var/lib/markets/free_ng/latest.json"))
    parser.add_argument("--eia-key", default=(os.getenv("EIA_API_KEY") or "DEMO_KEY"))
    parser.add_argument("--s3-bucket", default=os.getenv("FREE_NG_S3_BUCKET", ""))
    parser.add_argument("--s3-key", default=os.getenv("FREE_NG_S3_KEY", "drivers/free_ng/latest.json"))
    parser.add_argument("--no-eia", action="store_true")
    parser.add_argument("--no-nws", action="store_true")
    args = parser.parse_args()

    started = time.time()
    result: dict[str, Any] = {
        "collector": "free-ng-drivers", "started_at": utc_now(), "sources": {}, "errors": {},
        "data_class": "public/free", "execution_authority": "research-input",
    }
    if not args.no_eia:
        try:
            result["sources"]["eia"] = collect_eia(args.eia_key)
            result["sources"]["eia"]["status"] = "ok"
        except Exception as error:
            result["errors"]["eia"] = repr(error)
    if not args.no_nws:
        try:
            result["sources"]["nws"] = collect_nws()
            result["sources"]["nws"]["status"] = "ok"
        except Exception as error:
            result["errors"]["nws"] = repr(error)
    result["completed_at"] = utc_now()
    result["duration_s"] = round(time.time() - started, 3)
    result["status"] = "ok" if result["sources"] and not result["errors"] else ("partial" if result["sources"] else "error")

    out = Path(args.out)
    atomic_json(out, result)
    if args.s3_bucket:
        upload_s3(out, args.s3_bucket, args.s3_key)
    print(json.dumps({"status": result["status"], "out": str(out), "sources": list(result["sources"]), "errors": result["errors"]}, indent=2))
    return 0 if result["sources"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
