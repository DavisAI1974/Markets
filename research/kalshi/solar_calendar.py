"""
solar_calendar.py - FEED P (S98, Greg 2026-07-20: "do we have sun up/sun down time in our feed").

Sunrise / sunset / day-length state for the 16 gas-weighted demand metros. PURE ASTRONOMY - the
standard NOAA solar-position equations, no external data source, fully forward-known (like the flow
calendar), so there is no blind wall to audit. Deterministic to the minute-scale accuracy the use
cases need.

WHY (desk channels, recorded not scored - the agent decides):
1. THE SUNSET POWER-BURN RAMP: solar generation collapses at sunset and gas peakers pick up the
   evening load (the duck-curve neck). WHERE the sunset lands on the session clock moves the
   evening gas-burn ramp; strongest in high-solar grids (ERCOT/CAISO) and growing every year.
2. DAY LENGTH + its rate of change: the seasonal demand-shape descriptor (lighting/heating timing,
   the march toward/away from solstice).

Fields are per-metro (station -> local + ET clock times) plus a summary block: gas-weighted day
length, its 7d change, and the sunset span across metros in ET. Missing is never fabricated: polar
edge cases do not arise at these latitudes; if the iteration failed it would raise, not default.

  python solar_calendar.py --build              # precompute the span store
  python solar_calendar.py --selftest
  python solar_calendar.py --asof 2026-01-20
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import math
import os
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
STORE_DIR = os.path.join(REPO, "data", "solar_calendar")
STORE = os.path.join(STORE_DIR, "solar_calendar.json")
SPAN = ("2025-09-01", "2026-08-31")               # matches the flow-calendar span
ET = ZoneInfo("America/New_York")

# The 16 demand metros of nws_temp_feed.STATION_WEIGHTS_RAW (weights normalized at read) with the
# station coordinates (fixed public facts - airport/city reference points) and IANA timezones,
# tagged by grid region for the solar-ramp channel.
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


def _solar_events(lat: float, lon: float, day: dt.date) -> tuple[float, float]:
    """(sunrise_utc_hours, sunset_utc_hours) via the NOAA general solar position equations
    (fractional-year form). Accuracy ~1-2 minutes at mid-latitudes - ample for the use case."""
    doy = day.timetuple().tm_yday
    out = []
    for is_rise in (True, False):
        # first pass with solar noon guess, one refinement pass on the hour fraction
        hour = 12.0
        for _ in range(2):
            gamma = 2.0 * math.pi / 365.0 * (doy - 1 + (hour - 12.0) / 24.0)
            eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma)
                               - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma))
            decl = (0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma)
                    - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma)
                    - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma))
            lat_r = math.radians(lat)
            cos_ha = (math.cos(math.radians(90.833)) / (math.cos(lat_r) * math.cos(decl))
                      - math.tan(lat_r) * math.tan(decl))
            cos_ha = max(-1.0, min(1.0, cos_ha))          # clamp; no polar day/night at these latitudes
            ha = math.degrees(math.acos(cos_ha))          # degrees
            if not is_rise:
                ha = -ha
            minutes = 720.0 - 4.0 * (lon + ha) - eqtime   # minutes UTC
            hour = minutes / 60.0
        out.append(hour % 24.0)
    return out[0], out[1]


def _fmt_local(day: dt.date, utc_hours: float, tz: ZoneInfo) -> str:
    t = dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc) + dt.timedelta(hours=utc_hours)
    return t.astimezone(tz).strftime("%H:%M")


def _day_row(iso: str) -> dict:
    day = dt.date.fromisoformat(iso)
    metros = {}
    gw_len = 0.0
    sunsets_et = []
    for st, (lat, lon, tzname, grid, w) in METROS.items():
        rise_u, set_u = _solar_events(lat, lon, day)
        if set_u < rise_u:
            set_u += 24.0
        length = set_u - rise_u
        tz = ZoneInfo(tzname)
        set_et = _fmt_local(day, set_u % 24.0, ET)
        metros[st] = {"sunrise_local": _fmt_local(day, rise_u, tz),
                      "sunset_local": _fmt_local(day, set_u % 24.0, tz),
                      "sunset_et": set_et, "day_length_h": round(length, 2), "grid": grid}
        gw_len += (w / _WSUM) * length
        sunsets_et.append(set_et)
    return {"date": iso, "metros": metros,
            "gw_day_length_h": round(gw_len, 3),
            "sunset_et_earliest": min(sunsets_et), "sunset_et_latest": max(sunsets_et)}


def build() -> dict:
    os.makedirs(STORE_DIR, exist_ok=True)
    out = {}
    day = dt.date.fromisoformat(SPAN[0])
    end = dt.date.fromisoformat(SPAN[1])
    while day <= end:
        out[day.isoformat()] = _day_row(day.isoformat())
        day += dt.timedelta(days=1)
    # 7d day-length change (within-store, deterministic)
    keys = sorted(out)
    for i, k in enumerate(keys):
        prev = out[keys[i - 7]]["gw_day_length_h"] if i >= 7 else None
        out[k]["gw_day_length_chg_7d"] = round(out[k]["gw_day_length_h"] - prev, 3) if prev is not None else None
    json.dump(out, open(STORE, "w"), indent=1, sort_keys=True)
    return out


def solar_asof(date: str) -> dict | None:
    """Per-date solar state. Deterministic and forward-known - no blind wall. None outside the span."""
    iso = f"{date[:4]}-{date[4:6]}-{date[6:]}" if len(date) == 8 and date.isdigit() else date
    if not os.path.exists(STORE):
        return None
    row = json.load(open(STORE)).get(iso)
    return dict(row) if row else None


def _selftest() -> int:
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")
        ok = ok and cond

    if not os.path.exists(STORE):
        build()
    s = json.load(open(STORE))
    # solstice anchors, NYC (well-established values; tolerance covers the 1-2 min algorithm accuracy)
    dec = s["2025-12-21"]["metros"]["NYC"]; jun = s["2026-06-21"]["metros"]["NYC"]
    check("NYC winter-solstice day length ~9.25h", abs(dec["day_length_h"] - 9.25) < 0.17, dec["day_length_h"])
    check("NYC summer-solstice day length ~15.1h", abs(jun["day_length_h"] - 15.10) < 0.17, jun["day_length_h"])
    check("solstice ordering: every metro shortest day in Dec",
          all(s["2025-12-21"]["metros"][m]["day_length_h"] < s["2026-06-21"]["metros"][m]["day_length_h"]
              for m in METROS))
    # west-coast sunset lands later on the ET clock than the east coast
    j20 = s["2026-01-20"]
    check("LAX sunset_et later than NYC sunset_et", j20["metros"]["LAX"]["sunset_et"] > j20["metros"]["NYC"]["sunset_et"],
          f"{j20['metros']['NYC']['sunset_et']} vs {j20['metros']['LAX']['sunset_et']}")
    # day length monotonically increasing through late January (post-solstice)
    check("gw day length rising post-solstice", s["2026-01-30"]["gw_day_length_h"] > s["2026-01-02"]["gw_day_length_h"])
    check("7d change populated and positive late Jan", (s["2026-01-30"]["gw_day_length_chg_7d"] or 0) > 0,
          s["2026-01-30"]["gw_day_length_chg_7d"])
    # DST discontinuity visible in ET clock times (Mar 8 2026 spring-forward)
    check("DST jump in NYC sunset_local across Mar 7->9",
          s["2026-03-09"]["metros"]["NYC"]["sunset_local"] > "18:30" > s["2026-03-07"]["metros"]["NYC"]["sunset_local"])
    check("span bounds: outside -> None", solar_asof("2025-08-31") is None and solar_asof("2026-09-01") is None)
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--asof")
    a = ap.parse_args()
    if a.build:
        out = build(); print(f"[solar_calendar] wrote {STORE}: {len(out)} days {SPAN[0]}..{SPAN[1]}"); return 0
    if a.selftest:
        return _selftest()
    if a.asof:
        print(json.dumps(solar_asof(a.asof), indent=1, sort_keys=True)); return 0
    ap.print_help(); return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
