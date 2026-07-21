#!/usr/bin/env python3
"""Deterministic daylight/load-shape enrichment for the existing NG forecaster.

This is NOT a standalone trading signal. It supplies calendar-known features to the
existing decision state and day-characterization paths:

- sunrise/sunset and civil dawn/dusk (lighting transitions);
- effective solar ramp start/end at +5 degrees solar elevation;
- weighted daylight/dark hours across major U.S. gas-power load centers;
- 24-hour clear-sky solar and artificial-lighting geometry envelopes;
- calendar curve regime (summer long-day, winter long-dark, shoulder);
- current daylight phase for the live public-data snapshot.

The approximation follows the compact NOAA/Meeus solar-position equations. It uses
UTC and longitude directly, so DST/time-zone rules are not required. Geometry is
leakage-safe for historical work because it is a pure function of date and location.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

# Same first-cut national gas/power demand weights used by nws_temp_feed and the
# free public-data collector. These are load centers, not solar farms.
LOAD_CENTERS: dict[str, tuple[float, float, float]] = {
    "NYC": (40.71, -74.01, 0.12), "BOS": (42.36, -71.01, 0.05),
    "PHL": (39.87, -75.23, 0.05), "DCA": (38.85, -77.03, 0.05),
    "ORD": (41.98, -87.90, 0.10), "DTW": (42.21, -83.35, 0.05),
    "MSP": (44.88, -93.22, 0.045), "STL": (38.75, -90.37, 0.035),
    "IAH": (29.98, -95.34, 0.07), "DFW": (32.90, -97.04, 0.065),
    "ATL": (33.63, -84.44, 0.055), "DEN": (39.86, -104.67, 0.035),
    "PHX": (33.43, -112.01, 0.045), "LAX": (33.94, -118.41, 0.055),
    "SFO": (37.62, -122.38, 0.03), "SEA": (47.44, -122.31, 0.035),
}

APPARENT_SUN_ELEVATION_DEG = -0.833
CIVIL_TWILIGHT_ELEVATION_DEG = -6.0
EFFECTIVE_SOLAR_ELEVATION_DEG = 5.0


def _as_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _fractional_year(day: date, hour_utc: float = 12.0) -> float:
    days = 366 if _is_leap(day.year) else 365
    return 2.0 * math.pi / days * (day.timetuple().tm_yday - 1 + (hour_utc - 12.0) / 24.0)


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def solar_terms(day: date, hour_utc: float = 12.0) -> tuple[float, float]:
    """Return (equation_of_time_minutes, solar_declination_radians)."""
    g = _fractional_year(day, hour_utc)
    eqtime = 229.18 * (
        0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
        - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g)
    )
    decl = (
        0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
        - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
        - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g)
    )
    return eqtime, decl


def solar_event_minutes_utc(day: date, lat_deg: float, lon_deg: float,
                            elevation_deg: float, morning: bool) -> float | None:
    """UTC minute of a solar-elevation crossing; east-positive longitude."""
    eqtime, decl = solar_terms(day)
    lat = math.radians(lat_deg)
    zenith = math.radians(90.0 - elevation_deg)
    denom = math.cos(lat) * math.cos(decl)
    if abs(denom) < 1e-12:
        return None
    cos_ha = (math.cos(zenith) / denom) - math.tan(lat) * math.tan(decl)
    if cos_ha < -1.0 or cos_ha > 1.0:
        return None
    ha_deg = math.degrees(math.acos(max(-1.0, min(1.0, cos_ha))))
    solar_noon = 720.0 - 4.0 * lon_deg - eqtime
    value = solar_noon - 4.0 * ha_deg if morning else solar_noon + 4.0 * ha_deg
    return value % 1440.0


def solar_elevation_deg(day: date, minute_utc: float, lat_deg: float, lon_deg: float) -> float:
    hour = minute_utc / 60.0
    eqtime, decl = solar_terms(day, hour)
    true_solar_min = (minute_utc + eqtime + 4.0 * lon_deg) % 1440.0
    hour_angle_deg = true_solar_min / 4.0 - 180.0
    lat = math.radians(lat_deg)
    ha = math.radians(hour_angle_deg)
    cos_zenith = (
        math.sin(lat) * math.sin(decl)
        + math.cos(lat) * math.cos(decl) * math.cos(ha)
    )
    zenith = math.acos(max(-1.0, min(1.0, cos_zenith)))
    return 90.0 - math.degrees(zenith)


def solar_geometry_factor(elevation_deg: float) -> float:
    """0..1 clear-sky production envelope from sun elevation only."""
    if elevation_deg <= 0.0:
        return 0.0
    return round(max(0.0, math.sin(math.radians(elevation_deg))) ** 1.25, 6)


def lighting_need_factor(elevation_deg: float) -> float:
    """0..1 artificial-lighting geometry proxy around civil twilight."""
    if elevation_deg >= 0.0:
        return 0.0
    if elevation_deg <= CIVIL_TWILIGHT_ELEVATION_DEG:
        return 1.0
    return round((-elevation_deg) / abs(CIVIL_TWILIGHT_ELEVATION_DEG), 6)


def _weights() -> dict[str, float]:
    total = sum(v[2] for v in LOAD_CENTERS.values())
    return {name: values[2] / total for name, values in LOAD_CENTERS.items()}


def _weighted_event(day: date, elevation_deg: float, morning: bool) -> float | None:
    values: list[tuple[float, float]] = []
    for name, (lat, lon, _) in LOAD_CENTERS.items():
        minute = solar_event_minutes_utc(day, lat, lon, elevation_deg, morning)
        if minute is None:
            continue
        if not morning and minute < 720.0:
            minute += 1440.0
        values.append((minute, _weights()[name]))
    if not values:
        return None
    weight = sum(w for _, w in values)
    return sum(value * w for value, w in values) / weight


def _minute_to_iso(day: date, minute: float | None) -> str | None:
    if minute is None:
        return None
    base = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return (base + timedelta(minutes=minute)).isoformat()


def _hourly_curves(day: date) -> tuple[list[float], list[float]]:
    solar: list[float] = []
    lighting: list[float] = []
    weights = _weights()
    for hour in range(24):
        minute = hour * 60.0 + 30.0
        sf = 0.0
        lf = 0.0
        for name, (lat, lon, _) in LOAD_CENTERS.items():
            elevation = solar_elevation_deg(day, minute, lat, lon)
            sf += weights[name] * solar_geometry_factor(elevation)
            lf += weights[name] * lighting_need_factor(elevation)
        solar.append(round(sf, 5))
        lighting.append(round(lf, 5))
    return solar, lighting


def calendar_regime(daylight_hours: float) -> str:
    if daylight_hours >= 13.5:
        return "summer_long_day"
    if daylight_hours <= 10.5:
        return "winter_long_dark"
    return "shoulder_transition"


def combine_with_temp(profile: dict[str, Any], temp_regime: str | None) -> str:
    temp = str(temp_regime or "unknown")
    if temp in {"hard_heat", "mod_heat"}:
        return "winter_heating_lighting"
    if temp in {"hard_cool", "mod_cool"}:
        return "summer_cooling_solar"
    return str(profile.get("calendar_curve_regime", "unknown"))


def weighted_day_profile(value: str | date | datetime, include_curves: bool = True) -> dict[str, Any]:
    day = _as_date(value)
    civil_dawn = _weighted_event(day, CIVIL_TWILIGHT_ELEVATION_DEG, True)
    sunrise = _weighted_event(day, APPARENT_SUN_ELEVATION_DEG, True)
    solar_start = _weighted_event(day, EFFECTIVE_SOLAR_ELEVATION_DEG, True)
    solar_end = _weighted_event(day, EFFECTIVE_SOLAR_ELEVATION_DEG, False)
    sunset = _weighted_event(day, APPARENT_SUN_ELEVATION_DEG, False)
    civil_dusk = _weighted_event(day, CIVIL_TWILIGHT_ELEVATION_DEG, False)

    daylight_minutes = None if sunrise is None or sunset is None else sunset - sunrise
    daylight_hours = None if daylight_minutes is None else daylight_minutes / 60.0
    dark_hours = None if daylight_hours is None else 24.0 - daylight_hours

    previous = day - timedelta(days=1)
    prev_rise = _weighted_event(previous, APPARENT_SUN_ELEVATION_DEG, True)
    prev_set = _weighted_event(previous, APPARENT_SUN_ELEVATION_DEG, False)
    previous_daylight = None if prev_rise is None or prev_set is None else prev_set - prev_rise
    delta = None if daylight_minutes is None or previous_daylight is None else daylight_minutes - previous_daylight

    profile: dict[str, Any] = {
        "date": day.isoformat(),
        "source": "deterministic NOAA/Meeus-style solar geometry",
        "data_class": "calendar-known",
        "execution_authority": "existing-forecast-feature-only",
        "civil_dawn_utc": _minute_to_iso(day, civil_dawn),
        "sunrise_utc": _minute_to_iso(day, sunrise),
        "effective_solar_start_utc": _minute_to_iso(day, solar_start),
        "effective_solar_end_utc": _minute_to_iso(day, solar_end),
        "sunset_utc": _minute_to_iso(day, sunset),
        "civil_dusk_utc": _minute_to_iso(day, civil_dusk),
        "daylight_hours": round(daylight_hours, 3) if daylight_hours is not None else None,
        "dark_hours": round(dark_hours, 3) if dark_hours is not None else None,
        "daylight_change_minutes_vs_prior_day": round(delta, 3) if delta is not None else None,
        "daylight_trend": (
            "lengthening" if delta is not None and delta > 0.25
            else "shortening" if delta is not None and delta < -0.25
            else "flat"
        ),
        "calendar_curve_regime": calendar_regime(daylight_hours) if daylight_hours is not None else "unknown",
        "sunrise_native_load_window_utc": {
            "start": _minute_to_iso(day, civil_dawn),
            "end": _minute_to_iso(day, None if solar_start is None else solar_start + 120.0),
        },
        "evening_net_load_ramp_window_utc": {
            "start": _minute_to_iso(day, None if solar_end is None else solar_end - 120.0),
            "end": _minute_to_iso(day, civil_dusk),
        },
        "methodology": {
            "lighting_transition": "civil twilight (-6 degree solar elevation)",
            "apparent_sunrise_sunset": "-0.833 degree solar elevation",
            "effective_solar_threshold": "+5 degree solar elevation",
            "weights": "same 16 gas/power load-center weights as the weather stack",
        },
    }
    if include_curves:
        solar, lighting = _hourly_curves(day)
        profile["hourly_utc"] = list(range(24))
        profile["clear_sky_solar_geometry"] = solar
        profile["artificial_lighting_geometry"] = lighting
    return profile


def live_profile(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    profile = weighted_day_profile(now.date(), include_curves=True)
    minute = now.hour * 60.0 + now.minute + now.second / 60.0
    weights = _weights()
    solar = 0.0
    lighting = 0.0
    for name, (lat, lon, _) in LOAD_CENTERS.items():
        elevation = solar_elevation_deg(now.date(), minute, lat, lon)
        solar += weights[name] * solar_geometry_factor(elevation)
        lighting += weights[name] * lighting_need_factor(elevation)

    def minute_of(key: str) -> float | None:
        raw = profile.get(key)
        if not raw:
            return None
        dt = datetime.fromisoformat(str(raw)).astimezone(timezone.utc)
        return (dt - datetime.combine(now.date(), time.min, tzinfo=timezone.utc)).total_seconds() / 60.0

    dawn = minute_of("civil_dawn_utc")
    rise = minute_of("sunrise_utc")
    start = minute_of("effective_solar_start_utc")
    end = minute_of("effective_solar_end_utc")
    set_ = minute_of("sunset_utc")
    dusk = minute_of("civil_dusk_utc")
    if dawn is not None and minute < dawn:
        phase = "overnight_dark"
    elif rise is not None and minute < rise:
        phase = "civil_dawn_lighting_release"
    elif start is not None and minute < start + 120.0:
        phase = "sunrise_solar_ramp"
    elif end is not None and minute < end - 120.0:
        phase = "daylight_plateau"
    elif set_ is not None and minute < set_:
        phase = "evening_solar_fade"
    elif dusk is not None and minute < dusk:
        phase = "civil_dusk_lighting_pickup"
    else:
        phase = "overnight_dark"
    profile["as_of_utc"] = now.isoformat()
    profile["current_phase"] = phase
    profile["current_clear_sky_solar_geometry"] = round(solar, 5)
    profile["current_artificial_lighting_geometry"] = round(lighting, 5)
    return profile


def selftest() -> int:
    summer = weighted_day_profile("2026-06-21")
    winter = weighted_day_profile("2026-12-21")
    assert summer["daylight_hours"] > winter["daylight_hours"] + 3.0
    assert summer["calendar_curve_regime"] == "summer_long_day"
    assert winter["calendar_curve_regime"] == "winter_long_dark"
    for profile in (summer, winter):
        dawn = datetime.fromisoformat(profile["civil_dawn_utc"])
        rise = datetime.fromisoformat(profile["sunrise_utc"])
        start = datetime.fromisoformat(profile["effective_solar_start_utc"])
        end = datetime.fromisoformat(profile["effective_solar_end_utc"])
        set_ = datetime.fromisoformat(profile["sunset_utc"])
        dusk = datetime.fromisoformat(profile["civil_dusk_utc"])
        assert dawn < rise < start < end < set_ < dusk
        assert max(profile["clear_sky_solar_geometry"]) > 0.5
        assert max(profile["artificial_lighting_geometry"]) == 1.0
    assert combine_with_temp(summer, "hard_cool") == "summer_cooling_solar"
    assert combine_with_temp(winter, "hard_heat") == "winter_heating_lighting"
    print("[daylight-load-shape] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    payload = live_profile() if args.live else weighted_day_profile(args.date)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
