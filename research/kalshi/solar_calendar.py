#!/usr/bin/env python3
"""
solar_calendar.py - deterministic daylight authority for the NG decision state.

This is the existing S103 solar authority, enriched in place. It is NOT a
standalone trading signal. The module provides calendar-known geometry used by
forecast_harness.decision_state()["solar"]:

- civil dawn/dusk and apparent sunrise/sunset;
- effective solar production start/end at +5 degrees elevation;
- gas-weighted daylight, darkness, and effective-solar hours;
- sunrise native-load and evening replacement-ramp windows;
- 24-hour clear-sky solar and artificial-lighting geometry;
- summer-long-day, winter-long-dark, and shoulder regimes.

All calculations use compact NOAA solar-position equations and fixed public
metro coordinates. No realized load, weather, price, or outcome data enters
this module, so the geometry is forward-known and blind-safe.

Commands:
  python solar_calendar.py --build
  python solar_calendar.py --selftest
  python solar_calendar.py --asof 2026-01-20
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
STORE_DIR = os.path.join(REPO, "data", "solar_calendar")
STORE = os.path.join(STORE_DIR, "solar_calendar.json")
SPAN = ("2025-09-01", "2026-12-31")
ET = ZoneInfo("America/New_York")

APPARENT_SUN_ELEVATION_DEG = -0.833
CIVIL_TWILIGHT_ELEVATION_DEG = -6.0
EFFECTIVE_SOLAR_ELEVATION_DEG = 5.0

# The 16 demand metros of nws_temp_feed.STATION_WEIGHTS_RAW. These are
# gas/power load centers, not solar farms. Existing weights and legacy fields
# remain unchanged.
METROS = {
    #        lat      lon        tz                     grid       weight
    "NYC": (40.78,  -73.97, "America/New_York",    "NYISO",   0.12),
    "BOS": (42.36,  -71.01, "America/New_York",    "ISO-NE",  0.05),
    "PHL": (39.87,  -75.24, "America/New_York",    "PJM",     0.05),
    "DCA": (38.85,  -77.04, "America/New_York",    "PJM",     0.05),
    "ORD": (41.98,  -87.90, "America/Chicago",     "PJM",     0.10),
    "DTW": (42.21,  -83.35, "America/Detroit",     "MISO",    0.05),
    "MSP": (44.88,  -93.22, "America/Chicago",     "MISO",    0.045),
    "STL": (38.75,  -90.37, "America/Chicago",     "MISO",    0.035),
    "IAH": (29.98,  -95.34, "America/Chicago",     "ERCOT",   0.07),
    "DFW": (32.90,  -97.04, "America/Chicago",     "ERCOT",   0.065),
    "ATL": (33.64,  -84.43, "America/New_York",    "SOCO",    0.055),
    "DEN": (39.86, -104.67, "America/Denver",      "WECC",    0.035),
    "PHX": (33.43, -112.01, "America/Phoenix",     "WECC",    0.045),
    "LAX": (33.94, -118.41, "America/Los_Angeles", "CAISO",   0.055),
    "SFO": (37.62, -122.38, "America/Los_Angeles", "CAISO",   0.03),
    "SEA": (47.45, -122.31, "America/Los_Angeles", "WECC",    0.035),
}
_WSUM = sum(v[4] for v in METROS.values())
_WEIGHTS = {name: values[4] / _WSUM for name, values in METROS.items()}


class SolarCalendarError(ValueError):
    """Raised when deterministic solar geometry is internally contradictory."""


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _solar_terms(day: dt.date, hour_utc: float = 12.0) -> tuple[float, float]:
    """Return equation-of-time minutes and solar declination radians."""
    days = 366 if _is_leap(day.year) else 365
    gamma = 2.0 * math.pi / days * (
        day.timetuple().tm_yday - 1 + (hour_utc - 12.0) / 24.0
    )
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )
    return eqtime, decl


def _solar_event_minutes_utc(
    day: dt.date,
    lat_deg: float,
    lon_deg: float,
    elevation_deg: float,
    morning: bool,
) -> float | None:
    """UTC minute of a requested solar-elevation crossing.

    Returned minutes are relative to 00:00 UTC on ``day`` and intentionally are
    not modulo-wrapped. West-coast evening events can therefore exceed 1440,
    preserving true chronology across the UTC date boundary.
    """
    eqtime, decl = _solar_terms(day)
    lat = math.radians(lat_deg)
    zenith = math.radians(90.0 - elevation_deg)
    denom = math.cos(lat) * math.cos(decl)
    if abs(denom) < 1e-12:
        return None
    cos_ha = (math.cos(zenith) / denom) - math.tan(lat) * math.tan(decl)
    if cos_ha < -1.0 or cos_ha > 1.0:
        return None
    hour_angle = math.degrees(math.acos(max(-1.0, min(1.0, cos_ha))))
    solar_noon = 720.0 - 4.0 * lon_deg - eqtime
    return solar_noon - 4.0 * hour_angle if morning else solar_noon + 4.0 * hour_angle


def _solar_events(lat: float, lon: float, day: dt.date) -> tuple[float, float]:
    """Legacy-compatible apparent sunrise/sunset UTC hours."""
    rise = _solar_event_minutes_utc(
        day, lat, lon, APPARENT_SUN_ELEVATION_DEG, True
    )
    set_ = _solar_event_minutes_utc(
        day, lat, lon, APPARENT_SUN_ELEVATION_DEG, False
    )
    if rise is None or set_ is None:
        raise SolarCalendarError("apparent sunrise/sunset unavailable")
    return rise / 60.0, set_ / 60.0


def _solar_elevation_deg(
    day: dt.date, minute_utc: float, lat_deg: float, lon_deg: float
) -> float:
    hour = minute_utc / 60.0
    eqtime, decl = _solar_terms(day, hour)
    true_solar_min = (minute_utc + eqtime + 4.0 * lon_deg) % 1440.0
    hour_angle = math.radians(true_solar_min / 4.0 - 180.0)
    lat = math.radians(lat_deg)
    cos_zenith = (
        math.sin(lat) * math.sin(decl)
        + math.cos(lat) * math.cos(decl) * math.cos(hour_angle)
    )
    zenith = math.acos(max(-1.0, min(1.0, cos_zenith)))
    return 90.0 - math.degrees(zenith)


def _solar_geometry_factor(elevation_deg: float) -> float:
    """0..1 clear-sky production envelope from solar elevation only."""
    if elevation_deg <= 0.0:
        return 0.0
    return max(0.0, math.sin(math.radians(elevation_deg))) ** 1.25


def _lighting_need_factor(elevation_deg: float) -> float:
    """0..1 artificial-lighting geometry proxy around civil twilight."""
    if elevation_deg >= 0.0:
        return 0.0
    if elevation_deg <= CIVIL_TWILIGHT_ELEVATION_DEG:
        return 1.0
    return (-elevation_deg) / abs(CIVIL_TWILIGHT_ELEVATION_DEG)


def _minute_to_datetime(day: dt.date, minute: float) -> dt.datetime:
    return dt.datetime.combine(day, dt.time.min, tzinfo=dt.timezone.utc) + dt.timedelta(
        minutes=minute
    )


def _fmt_event(day: dt.date, minute: float, tz: ZoneInfo) -> str:
    return _minute_to_datetime(day, minute).astimezone(tz).strftime("%H:%M")


def _event_iso(day: dt.date, minute: float | None) -> str | None:
    return None if minute is None else _minute_to_datetime(day, minute).isoformat()


def _weighted_event(
    day: dt.date, elevation_deg: float, morning: bool
) -> float | None:
    values: list[tuple[float, float]] = []
    for name, (lat, lon, _tzname, _grid, _weight) in METROS.items():
        minute = _solar_event_minutes_utc(day, lat, lon, elevation_deg, morning)
        if minute is not None:
            values.append((minute, _WEIGHTS[name]))
    if not values:
        return None
    weight = sum(w for _, w in values)
    return sum(value * w for value, w in values) / weight


def _hourly_curves(day: dt.date) -> tuple[list[float], list[float]]:
    solar: list[float] = []
    lighting: list[float] = []
    for hour in range(24):
        minute = hour * 60.0 + 30.0
        solar_value = 0.0
        lighting_value = 0.0
        for name, (lat, lon, _tzname, _grid, _weight) in METROS.items():
            elevation = _solar_elevation_deg(day, minute, lat, lon)
            solar_value += _WEIGHTS[name] * _solar_geometry_factor(elevation)
            lighting_value += _WEIGHTS[name] * _lighting_need_factor(elevation)
        solar.append(round(solar_value, 5))
        lighting.append(round(lighting_value, 5))
    return solar, lighting


def _calendar_regime(daylight_hours: float) -> str:
    if daylight_hours >= 13.5:
        return "summer_long_day"
    if daylight_hours <= 10.5:
        return "winter_long_dark"
    return "shoulder_transition"


def _ordered_events(events: dict[str, float | None], *, label: str) -> None:
    ordered = [
        events["civil_dawn"],
        events["sunrise"],
        events["effective_start"],
        events["effective_end"],
        events["sunset"],
        events["civil_dusk"],
    ]
    if any(value is None for value in ordered):
        raise SolarCalendarError(f"{label}: missing solar event")
    values = [float(value) for value in ordered if value is not None]
    if values != sorted(values) or len(set(values)) != len(values):
        raise SolarCalendarError(f"{label}: solar events are not strictly chronological")


def _day_row(iso: str) -> dict[str, Any]:
    day = dt.date.fromisoformat(iso)
    metros: dict[str, dict[str, Any]] = {}
    weighted_daylight = 0.0
    weighted_effective = 0.0
    sunsets_et: list[str] = []

    for station, (lat, lon, tzname, grid, _weight) in METROS.items():
        events = {
            "civil_dawn": _solar_event_minutes_utc(
                day, lat, lon, CIVIL_TWILIGHT_ELEVATION_DEG, True
            ),
            "sunrise": _solar_event_minutes_utc(
                day, lat, lon, APPARENT_SUN_ELEVATION_DEG, True
            ),
            "effective_start": _solar_event_minutes_utc(
                day, lat, lon, EFFECTIVE_SOLAR_ELEVATION_DEG, True
            ),
            "effective_end": _solar_event_minutes_utc(
                day, lat, lon, EFFECTIVE_SOLAR_ELEVATION_DEG, False
            ),
            "sunset": _solar_event_minutes_utc(
                day, lat, lon, APPARENT_SUN_ELEVATION_DEG, False
            ),
            "civil_dusk": _solar_event_minutes_utc(
                day, lat, lon, CIVIL_TWILIGHT_ELEVATION_DEG, False
            ),
        }
        _ordered_events(events, label=station)
        tz = ZoneInfo(tzname)
        sunrise = float(events["sunrise"])
        sunset = float(events["sunset"])
        effective_start = float(events["effective_start"])
        effective_end = float(events["effective_end"])
        daylight_hours = (sunset - sunrise) / 60.0
        effective_hours = (effective_end - effective_start) / 60.0
        sunset_et = _fmt_event(day, sunset, ET)
        sunsets_et.append(sunset_et)
        weighted_daylight += _WEIGHTS[station] * daylight_hours
        weighted_effective += _WEIGHTS[station] * effective_hours
        metros[station] = {
            "sunrise_local": _fmt_event(day, sunrise, tz),
            "sunset_local": _fmt_event(day, sunset, tz),
            "sunset_et": sunset_et,
            "day_length_h": round(daylight_hours, 2),
            "grid": grid,
            "civil_dawn_local": _fmt_event(day, float(events["civil_dawn"]), tz),
            "civil_dusk_local": _fmt_event(day, float(events["civil_dusk"]), tz),
            "effective_solar_start_local": _fmt_event(day, effective_start, tz),
            "effective_solar_end_local": _fmt_event(day, effective_end, tz),
            "sunrise_et": _fmt_event(day, sunrise, ET),
            "effective_solar_start_et": _fmt_event(day, effective_start, ET),
            "effective_solar_end_et": _fmt_event(day, effective_end, ET),
            "civil_dusk_et": _fmt_event(day, float(events["civil_dusk"]), ET),
            "effective_solar_hours": round(effective_hours, 2),
        }

    weighted = {
        "civil_dawn": _weighted_event(day, CIVIL_TWILIGHT_ELEVATION_DEG, True),
        "sunrise": _weighted_event(day, APPARENT_SUN_ELEVATION_DEG, True),
        "effective_start": _weighted_event(day, EFFECTIVE_SOLAR_ELEVATION_DEG, True),
        "effective_end": _weighted_event(day, EFFECTIVE_SOLAR_ELEVATION_DEG, False),
        "sunset": _weighted_event(day, APPARENT_SUN_ELEVATION_DEG, False),
        "civil_dusk": _weighted_event(day, CIVIL_TWILIGHT_ELEVATION_DEG, False),
    }
    _ordered_events(weighted, label="gas-weighted")
    solar_curve, lighting_curve = _hourly_curves(day)

    sunrise_window_end = float(weighted["effective_start"]) + 120.0
    evening_window_start = float(weighted["effective_end"]) - 120.0

    return {
        "date": iso,
        "authority": "EXISTING_SOLAR_DECISION_STATE_ENRICHMENT",
        "data_class": "calendar_known_deterministic",
        "execution_authority": False,
        "may_call_direction": False,
        "may_update_ng_brain": False,
        "metros": metros,
        "gw_day_length_h": round(weighted_daylight, 3),
        "sunset_et_earliest": min(sunsets_et),
        "sunset_et_latest": max(sunsets_et),
        "gw_dark_hours": round(24.0 - weighted_daylight, 3),
        "gw_effective_solar_hours": round(weighted_effective, 3),
        "calendar_curve_regime": _calendar_regime(weighted_daylight),
        "weighted_events_utc": {
            name: _event_iso(day, minute) for name, minute in weighted.items()
        },
        "weighted_events_et": {
            name: _fmt_event(day, float(minute), ET)
            for name, minute in weighted.items()
            if minute is not None
        },
        "sunrise_native_load_window_et": {
            "start": _fmt_event(day, float(weighted["civil_dawn"]), ET),
            "end": _fmt_event(day, sunrise_window_end, ET),
        },
        "evening_net_load_ramp_window_et": {
            "start": _fmt_event(day, evening_window_start, ET),
            "end": _fmt_event(day, float(weighted["civil_dusk"]), ET),
        },
        "hourly_utc": list(range(24)),
        "clear_sky_solar_geometry": solar_curve,
        "artificial_lighting_geometry": lighting_curve,
        "methodology": {
            "civil_twilight_elevation_deg": CIVIL_TWILIGHT_ELEVATION_DEG,
            "apparent_sun_elevation_deg": APPARENT_SUN_ELEVATION_DEG,
            "effective_solar_elevation_deg": EFFECTIVE_SOLAR_ELEVATION_DEG,
            "weights": "existing 16 gas-demand metro weights",
            "scope": (
                "geometry only; BTM capacity, clouds, irradiance, batteries, "
                "native-load residuals, and observed grid generation remain separate inputs"
            ),
        },
    }


def build() -> dict[str, dict[str, Any]]:
    os.makedirs(STORE_DIR, exist_ok=True)
    out: dict[str, dict[str, Any]] = {}
    day = dt.date.fromisoformat(SPAN[0])
    end = dt.date.fromisoformat(SPAN[1])
    while day <= end:
        out[day.isoformat()] = _day_row(day.isoformat())
        day += dt.timedelta(days=1)
    keys = sorted(out)
    for index, key in enumerate(keys):
        previous = out[keys[index - 7]]["gw_day_length_h"] if index >= 7 else None
        out[key]["gw_day_length_chg_7d"] = (
            round(out[key]["gw_day_length_h"] - previous, 3)
            if previous is not None
            else None
        )
    path = Path(STORE)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
        handle.write("\n")
    return out


def solar_asof(date: str) -> dict[str, Any] | None:
    """Return deterministic solar state for a date inside the configured span.

    The precomputed store remains the normal path. When it is not deployed yet,
    the same authority computes the row on demand rather than returning a fake
    zero or creating a second daylight signal.
    """
    iso = (
        f"{date[:4]}-{date[4:6]}-{date[6:]}"
        if len(date) == 8 and date.isdigit()
        else date
    )
    try:
        day = dt.date.fromisoformat(iso)
    except ValueError:
        return None
    start = dt.date.fromisoformat(SPAN[0])
    end = dt.date.fromisoformat(SPAN[1])
    if day < start or day > end:
        return None
    if os.path.exists(STORE):
        with open(STORE, encoding="utf-8") as handle:
            row = json.load(handle).get(iso)
        return dict(row) if row else None

    row = _day_row(iso)
    previous = day - dt.timedelta(days=7)
    row["gw_day_length_chg_7d"] = (
        round(row["gw_day_length_h"] - _day_row(previous.isoformat())["gw_day_length_h"], 3)
        if previous >= start
        else None
    )
    return row


def _selftest() -> int:
    winter = _day_row("2025-12-21")
    summer = _day_row("2026-06-21")
    assert abs(winter["metros"]["NYC"]["day_length_h"] - 9.25) < 0.17
    assert abs(summer["metros"]["NYC"]["day_length_h"] - 15.10) < 0.17
    assert summer["gw_day_length_h"] > winter["gw_day_length_h"] + 3.0
    assert summer["calendar_curve_regime"] == "summer_long_day"
    assert winter["calendar_curve_regime"] == "winter_long_dark"

    for profile in (summer, winter):
        events = [
            dt.datetime.fromisoformat(profile["weighted_events_utc"][name])
            for name in (
                "civil_dawn",
                "sunrise",
                "effective_start",
                "effective_end",
                "sunset",
                "civil_dusk",
            )
        ]
        assert events == sorted(events)
        assert len(profile["clear_sky_solar_geometry"]) == 24
        assert len(profile["artificial_lighting_geometry"]) == 24
        assert max(profile["clear_sky_solar_geometry"]) > 0.0
        assert max(profile["artificial_lighting_geometry"]) == 1.0

    assert max(summer["clear_sky_solar_geometry"]) > max(
        winter["clear_sky_solar_geometry"]
    )
    assert solar_asof("2025-08-31") is None
    assert solar_asof("2027-01-01") is None
    assert solar_asof("2026-09-01") is not None
    print("[solar-calendar] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--asof")
    args = parser.parse_args()
    if args.build:
        out = build()
        print(
            f"[solar_calendar] wrote {STORE}: {len(out)} days "
            f"{SPAN[0]}..{SPAN[1]}"
        )
        return 0
    if args.selftest:
        return _selftest()
    if args.asof:
        print(json.dumps(solar_asof(args.asof), indent=1, sort_keys=True))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
