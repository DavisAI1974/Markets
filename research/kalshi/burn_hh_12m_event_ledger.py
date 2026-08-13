#!/usr/bin/env python3
"""Build an event-level US48 gas-generation vs Henry Hub spot ledger.

No regression, correlation, fitted coefficient, threshold, or seasonal average is
computed here.  The raw daily physical series is retained and each Henry Hub
trading-day move is paired with the physical change over the same trading-date
endpoints.  Wind, solar, hydro, nuclear, and coal are retained as context.

Sources:
- EIA-930 daily generation by energy source, US48, Eastern time.
- EIA Henry Hub daily spot-price history XLS (RNGWHHDd.xls).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
import xlrd

EIA_DAILY_FUEL_URL = (
    "https://api.eia.gov/v2/electricity/rto/daily-fuel-type-data/data/"
)
HH_DAILY_XLS_URL = "https://www.eia.gov/dnav/ng/hist_xls/RNGWHHDd.xls"
FUEL_TYPES = ("NG", "WND", "SUN", "WAT", "NUC", "COL")
FUEL_COLUMNS = {
    "NG": "ng_mwh",
    "WND": "wind_mwh",
    "SUN": "solar_mwh",
    "WAT": "hydro_mwh",
    "NUC": "nuclear_mwh",
    "COL": "coal_mwh",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2025-08-01")
    p.add_argument("--end", default="2026-07-31")
    p.add_argument("--out", default="research/kalshi/s125_burn_hh_12m")
    return p.parse_args()


def as_float(value):
    if value in (None, "", "NA", "N/A"):
        return None
    return float(value)


def direction(value):
    if value is None:
        return "missing"
    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return "zero"


def relation(a, b):
    da, db = direction(a), direction(b)
    if "missing" in (da, db):
        return "missing"
    if "zero" in (da, db):
        return "zero_involved"
    return "same" if da == db else "opposite"


def season_for(d: date) -> str:
    if d.month in (12, 1, 2):
        return "winter"
    if d.month in (3, 4, 5):
        return "spring"
    if d.month in (6, 7, 8):
        return "summer"
    return "fall"


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def get_eia_daily_fuels(api_key: str, start: str, end: str):
    by_date = defaultdict(dict)
    raw = {}
    for fuel in FUEL_TYPES:
        params = [
            ("api_key", api_key),
            ("frequency", "daily"),
            ("data[0]", "value"),
            ("facets[respondent][]", "US48"),
            ("facets[timezone][]", "Eastern"),
            ("facets[fueltype][]", fuel),
            ("start", start),
            ("end", end),
            ("sort[0][column]", "period"),
            ("sort[0][direction]", "asc"),
            ("offset", "0"),
            ("length", "5000"),
        ]
        r = requests.get(EIA_DAILY_FUEL_URL, params=params, timeout=90)
        r.raise_for_status()
        payload = r.json()
        raw[fuel] = payload
        rows = payload.get("response", {}).get("data", [])
        if not rows:
            raise RuntimeError(f"EIA returned no rows for fuel={fuel}: {payload}")
        for row in rows:
            period = row.get("period")
            if not period:
                continue
            d = datetime.strptime(period[:10], "%Y-%m-%d").date()
            by_date[d][fuel] = as_float(row.get("value"))
    return by_date, raw


def get_henry_hub_daily():
    r = requests.get(HH_DAILY_XLS_URL, timeout=90)
    r.raise_for_status()
    book = xlrd.open_workbook(file_contents=r.content)
    sheet = book.sheet_by_index(1)
    out = {}
    for row_idx in range(3, sheet.nrows):
        serial = sheet.cell_value(row_idx, 0)
        price = sheet.cell_value(row_idx, 1)
        if serial in (None, "") or price in (None, ""):
            continue
        d = xlrd.xldate_as_datetime(serial, book.datemode).date()
        out[d] = float(price)
    return out, r.content


def write_csv(path: Path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main():
    args = parse_args()
    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    if (end - start).days != 364:
        raise SystemExit(
            f"Window must be exactly 365 calendar days; got {(end-start).days + 1}."
        )

    api_key = os.environ.get("EIA_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("EIA_API_KEY is required")

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    fuels, raw_eia = get_eia_daily_fuels(api_key, args.start, args.end)
    hh, hh_xls = get_henry_hub_daily()

    physical_rows = []
    missing_ng = []
    for d in daterange(start, end):
        vals = fuels.get(d, {})
        if vals.get("NG") is None:
            missing_ng.append(d.isoformat())
        row = {
            "date": d.isoformat(),
            "month": d.strftime("%Y-%m"),
            "season": season_for(d),
            "hh_spot_usd_mmbtu": hh.get(d),
        }
        for fuel, col in FUEL_COLUMNS.items():
            row[col] = vals.get(fuel)
        physical_rows.append(row)

    if missing_ng:
        raise RuntimeError(
            "Missing US48 natural-gas generation on calendar dates: "
            + ", ".join(missing_ng[:20])
            + (" ..." if len(missing_ng) > 20 else "")
        )

    trading_dates = sorted(d for d in hh if start <= d <= end and d in fuels)
    if len(trading_dates) < 200:
        raise RuntimeError(f"Too few Henry Hub trading dates: {len(trading_dates)}")

    ledger_rows = []
    for i in range(1, len(trading_dates)):
        d = trading_dates[i]
        prev = trading_dates[i - 1]
        cur = fuels[d]
        prior = fuels[prev]

        hh_delta = hh[d] - hh[prev]
        ng_delta_trade = cur["NG"] - prior["NG"]
        prev_calendar = d - timedelta(days=1)
        ng_delta_1d = None
        if prev_calendar in fuels and fuels[prev_calendar].get("NG") is not None:
            ng_delta_1d = cur["NG"] - fuels[prev_calendar]["NG"]

        interval_dates = [
            x for x in daterange(prev, d) if x in fuels and fuels[x].get("NG") is not None
        ]
        interval_ng = [fuels[x]["NG"] for x in interval_dates]

        row = {
            "date": d.isoformat(),
            "month": d.strftime("%Y-%m"),
            "season": season_for(d),
            "prev_hh_date": prev.isoformat(),
            "calendar_gap_days": (d - prev).days,
            "intervening_calendar_days": max(0, (d - prev).days - 1),
            "hh_spot_usd_mmbtu": hh[d],
            "hh_prev_usd_mmbtu": hh[prev],
            "hh_delta_usd_mmbtu": hh_delta,
            "hh_direction": direction(hh_delta),
            "ng_mwh": cur["NG"],
            "ng_prev_trade_mwh": prior["NG"],
            "ng_delta_prev_trade_mwh": ng_delta_trade,
            "ng_direction_prev_trade": direction(ng_delta_trade),
            "ng_delta_1d_mwh": ng_delta_1d,
            "ng_direction_1d": direction(ng_delta_1d),
            "burn_price_relation_trade_endpoints": relation(ng_delta_trade, hh_delta),
            "interval_ng_min_mwh": min(interval_ng),
            "interval_ng_max_mwh": max(interval_ng),
        }
        for fuel, prefix in (
            ("WND", "wind"),
            ("SUN", "solar"),
            ("WAT", "hydro"),
            ("NUC", "nuclear"),
            ("COL", "coal"),
        ):
            row[f"{prefix}_mwh"] = cur.get(fuel)
            row[f"{prefix}_delta_prev_trade_mwh"] = (
                cur.get(fuel) - prior.get(fuel)
                if cur.get(fuel) is not None and prior.get(fuel) is not None
                else None
            )
        ledger_rows.append(row)

    physical_fields = [
        "date", "month", "season", "hh_spot_usd_mmbtu",
        "ng_mwh", "wind_mwh", "solar_mwh", "hydro_mwh", "nuclear_mwh", "coal_mwh",
    ]
    ledger_fields = list(ledger_rows[0].keys())
    write_csv(outdir / "physical_daily_365d.csv", physical_rows, physical_fields)
    write_csv(outdir / "hh_trading_day_event_ledger.csv", ledger_rows, ledger_fields)

    with (outdir / "eia_raw_responses.json").open("w", encoding="utf-8") as f:
        json.dump(raw_eia, f)
    (outdir / "henry_hub_source.xls").write_bytes(hh_xls)

    notes = [
        "# S125 independent 12-month gas-generation vs Henry Hub ledger",
        "",
        f"Window: {start.isoformat()} through {end.isoformat()} (365 calendar days).",
        "",
        "This artifact intentionally computes no R-squared, correlation, regression, fitted coefficient, seasonal mean, or annual mean.",
        "",
        "`physical_daily_365d.csv` preserves every calendar day of US48 EIA-930 generation by fuel. `hh_trading_day_event_ledger.csv` preserves each Henry Hub trading-day move and compares it with the change in US48 natural-gas generation over the same trading-date endpoints. Weekend and holiday physical paths remain visible via the calendar gap and interval NG min/max columns.",
        "",
        "Natural-gas generation is retained in raw MWh. No heat-rate conversion is applied here, so a Bcf/d conversion cannot create or reverse the sign relationship. Wind and solar are retained on every date because the requested study is intentionally limited to one recent renewable regime.",
        "",
        f"Physical calendar rows: {len(physical_rows)}",
        f"Henry Hub event rows: {len(ledger_rows)}",
        f"First Henry Hub event row: {ledger_rows[0]['date']}",
        f"Last Henry Hub event row: {ledger_rows[-1]['date']}",
        "",
        "Sources:",
        f"- EIA-930 daily fuel-type API: {EIA_DAILY_FUEL_URL}",
        f"- EIA Henry Hub daily history: {HH_DAILY_XLS_URL}",
    ]
    (outdir / "README.md").write_text("\n".join(notes) + "\n", encoding="utf-8")

    print(json.dumps({
        "window": [start.isoformat(), end.isoformat()],
        "physical_rows": len(physical_rows),
        "event_rows": len(ledger_rows),
        "first_event": ledger_rows[0]["date"],
        "last_event": ledger_rows[-1]["date"],
        "outdir": str(outdir),
    }, indent=2))


if __name__ == "__main__":
    main()
