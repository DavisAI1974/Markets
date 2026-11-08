"""Compare public EIA Henry Hub futures and spot with explicit delivery months."""

import argparse
from bisect import bisect_right
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import date, timedelta
import gzip
import hashlib
import io
import json
from math import log, sqrt
from pathlib import Path
from statistics import mean

import requests
import xlrd

SERIES = ("RNGWHHD", "RNGC1", "RNGC2", "RNGC3", "RNGC4")


def fetch(series):
    url = f"https://www.eia.gov/dnav/ng/hist_xls/{series}d.xls"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    workbook = xlrd.open_workbook(file_contents=response.content)
    sheet = workbook.sheet_by_name("Data 1")
    if sheet.cell_value(1, 1) != series:
        raise ValueError(f"unexpected EIA series in {url}")
    values = {}
    for n in range(3, sheet.nrows):
        raw_day, value = sheet.row_values(n)[:2]
        if isinstance(value, (float, int)):
            day = xlrd.xldate_as_datetime(raw_day, workbook.datemode).date()
            if value <= 0 or day in values:
                raise ValueError(f"unexpected NG price or duplicate date in {series}: {day}")
            values[day] = value
    return values, dict(
        url=url, sha256=hashlib.sha256(response.content).hexdigest(),
        first=str(min(values)), last=str(max(values)), observations=len(values),
    )


def month_key(day, shift=0):
    return day.year * 12 + day.month - 1 + shift


def month_text(key):
    year, month0 = divmod(key, 12)
    return f"{year}-{month0+1:02d}"


def forecast_cases(spot, front):
    daily = sorted(spot)
    targets, origins = defaultdict(list), {}
    for day in daily:
        targets[month_key(day)].append(spot[day])
    for day in sorted(front):
        if 8 <= day.day <= 15:
            origins[month_key(day)] = day
    result = []
    for origin_month, origin in sorted(origins.items()):
        delivery = origin_month + 1
        if len(targets.get(delivery, ())) < 15:
            continue
        prior = bisect_right(daily, origin - timedelta(days=3))
        if prior < 20:
            continue
        prices = [spot[day] for day in daily[prior - 20:prior]]
        result.append(dict(
            origin=str(origin), delivery_month=month_text(delivery), futures=front[origin],
            prior_spot_date=str(daily[prior-1]), prior_spot=prices[-1], trailing20_spot=mean(prices),
            realized_spot=mean(targets[delivery]), delivery_spot_observations=len(targets[delivery]),
            basis_percent=100*(front[origin]/prices[-1]-1),
        ))
    return result


def errors(cases):
    results = {}
    for name, selected in (
        ("all", cases),
        ("abs_basis_under_5pct", [row for row in cases if abs(row["basis_percent"]) < 5]),
        ("abs_basis_5pct_or_more", [row for row in cases if abs(row["basis_percent"]) >= 5]),
        ("2010_onward", [row for row in cases if row["origin"][:4] >= "2010"]),
    ):
        measures = {"n": len(selected)}
        for key in ("futures", "prior_spot", "trailing20_spot"):
            delta = [row[key]-row["realized_spot"] for row in selected]
            measures[key] = dict(bias=mean(delta), mae=mean(map(abs, delta)), rmse=sqrt(mean(x*x for x in delta)))
        results[name] = measures
    return results


def maturity_panel(strip):
    # Within the 2nd to 20th of a month each slot refers to one fixed delivery month.
    common_days = sorted(set.intersection(*(set(leg) for leg in strip)))
    matches = defaultdict(lambda: defaultdict(list))
    same_date = []
    for before, after in zip(common_days, common_days[1:]):
        if before.month != after.month or not 2 <= before.day < after.day <= 20 or (after-before).days > 4:
            continue
        moves = [log(leg[after]/leg[before]) for leg in strip]
        same_date.append(moves)
        for lead, move in enumerate(moves, 1):
            matches[month_key(after, lead)][lead].append(move)
    paired_delivery = []
    for key, legs in sorted(matches.items()):
        if len(legs) == 4 and min(map(len, legs.values())) >= 5:
            paired_delivery.append(dict(
                delivery_month=month_text(key),
                **{f"slot{i}_rms": sqrt(mean(x*x for x in legs[i])) for i in range(1,5)},
                **{f"slot{i}_n": len(legs[i]) for i in range(1,5)},
            ))
    results = dict(
        paired_same_date_n=len(same_date),
        paired_same_date_rms=[sqrt(mean(day[i]**2 for day in same_date)) for i in range(4)],
        paired_same_delivery_n=len(paired_delivery),
        paired_same_delivery_front_gt_fourth=sum(row["slot1_rms"]>row["slot4_rms"] for row in paired_delivery),
    )
    return paired_delivery, results


def save_csv(path, records):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=records[0], lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    path.write_bytes(gzip.compress(stream.getvalue().encode(), mtime=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    output = parser.parse_args().output_directory
    with ThreadPoolExecutor(max_workers=len(SERIES)) as pool:
        data = list(pool.map(fetch, SERIES))
    spot, front, *later = [values for values, _ in data]
    forecasts = forecast_cases(spot, front)
    maturities, maturity_stats = maturity_panel([front, *later])
    summary = dict(
        sources={series: metadata for series, (_, metadata) in zip(SERIES, data)},
        forecast_first_origin=forecasts[0]["origin"], forecast_last_origin=forecasts[-1]["origin"],
        forecast_errors=errors(forecasts), maturity=maturity_stats,
    )
    available_days = sorted(set.union(*(set(values) for values, _ in data)))
    last_delivery = month_key(date.fromisoformat(forecasts[-1]["origin"]), 1)
    save_csv(output / "primer-eia-ng-source-daily.csv.gz", [
        {"date": str(day), **{name: values.get(day) for name, (values, _) in zip(SERIES, data)}}
        for day in available_days if month_key(day) <= last_delivery
    ])
    save_csv(output / "primer-eia-ng-forecasts.csv.gz", forecasts)
    save_csv(output / "primer-eia-ng-maturity.csv.gz", maturities)
    (output / "primer-eia-ng-summary.json").write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
