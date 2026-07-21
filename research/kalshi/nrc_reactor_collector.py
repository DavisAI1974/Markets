#!/usr/bin/env python3
"""Collect NRC daily commercial reactor power status for NG power-burn research.

The NRC publishes a free pipe-delimited file containing daily unit-level power
percentages for the trailing 365 days. This collector normalizes the feed and
emits a compact snapshot with:

- latest unit-level power status;
- outages and derates;
- day-over-day unit changes;
- equal-weight fleet availability and shortfall;
- trailing daily fleet aggregates.

EIA-930 remains the source for actual capacity-weighted nuclear generation.
NRC adds plant-level foresight and outage/return attribution. The derived
substitution signal is research-only and cannot grant execution authority.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

NRC_URL = (
    "https://www.nrc.gov/reading-rm/doc-collections/event-status/"
    "reactor-status/PowerReactorStatusForLast365Days.txt"
)
USER_AGENT = os.getenv(
    "NRC_USER_AGENT",
    "DavisAI-Markets/1.0 (public-data research; contact: operations@davisai.ai)",
)


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


def fetch_text(url: str = NRC_URL, retries: int = 4) -> str:
    last: Exception | None = None
    headers = {"User-Agent": USER_AGENT, "Accept": "text/plain"}
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            if "ReportDt|Unit|Power" not in response.text:
                raise ValueError("NRC response did not contain the expected header")
            return response.text
        except (requests.RequestException, ValueError) as error:
            last = error
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"NRC fetch failed: {last}")


def parse_report_date(raw: str) -> str:
    value = raw.strip()
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"unrecognized NRC report date: {raw!r}")


def parse_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(text.replace("\ufeff", "").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("ReportDt|"):
            continue
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        try:
            report_date = parse_report_date(parts[0])
            power = int(float(parts[2].strip()))
        except ValueError:
            continue
        if power < 0 or power > 100:
            continue
        unit = parts[1].strip()
        if not unit:
            continue
        rows.append({"date": report_date, "unit": unit, "power_pct": power, "source_line": number})
    if not rows:
        raise ValueError("NRC feed parsed zero reactor records")
    return rows


def aggregate_day(units: dict[str, int]) -> dict[str, Any]:
    powers = list(units.values())
    shortfall = sum(100 - power for power in powers)
    return {
        "unit_count": len(powers),
        "online_units": sum(power > 0 for power in powers),
        "zero_power_units": sum(power == 0 for power in powers),
        "derated_units": sum(0 < power < 100 for power in powers),
        "full_power_units": sum(power == 100 for power in powers),
        "fleet_average_power_pct_unweighted": round(sum(powers) / len(powers), 3),
        "fleet_shortfall_pct_points_unweighted": shortfall,
    }


def build_snapshot(rows: list[dict[str, Any]], recent_days: int = 30) -> dict[str, Any]:
    by_date: dict[str, dict[str, int]] = defaultdict(dict)
    for row in rows:
        by_date[row["date"]][row["unit"]] = row["power_pct"]
    dates = sorted(by_date, reverse=True)
    if not dates:
        raise ValueError("NRC feed contained no report dates")

    latest_date = dates[0]
    previous_date = dates[1] if len(dates) > 1 else None
    latest_units = by_date[latest_date]
    previous_units = by_date.get(previous_date, {}) if previous_date else {}
    latest_aggregate = aggregate_day(latest_units)
    previous_aggregate = aggregate_day(previous_units) if previous_units else None

    changes: list[dict[str, Any]] = []
    for unit in sorted(set(latest_units) | set(previous_units)):
        current = latest_units.get(unit)
        previous = previous_units.get(unit)
        if current is None or previous is None or current == previous:
            continue
        changes.append({
            "unit": unit,
            "previous_power_pct": previous,
            "current_power_pct": current,
            "change_pct_points": current - previous,
        })
    changes.sort(key=lambda row: (-abs(row["change_pct_points"]), row["unit"]))

    outages = [
        {"unit": unit, "power_pct": power}
        for unit, power in sorted(latest_units.items()) if power == 0
    ]
    derates = [
        {"unit": unit, "power_pct": power, "shortfall_pct_points": 100 - power}
        for unit, power in sorted(latest_units.items(), key=lambda item: (item[1], item[0]))
        if 0 < power < 100
    ]

    previous_shortfall = (
        previous_aggregate["fleet_shortfall_pct_points_unweighted"]
        if previous_aggregate else None
    )
    shortfall_change = (
        latest_aggregate["fleet_shortfall_pct_points_unweighted"] - previous_shortfall
        if previous_shortfall is not None else None
    )
    if shortfall_change is None or shortfall_change == 0:
        substitution = "neutral"
    elif shortfall_change > 0:
        substitution = "higher_gas_substitution_pressure"
    else:
        substitution = "lower_gas_substitution_pressure"

    daily = []
    for date in dates[:max(2, recent_days)]:
        daily.append({"date": date, **aggregate_day(by_date[date])})

    return {
        "source": "NRC Power Reactor Status",
        "source_url": NRC_URL,
        "source_frequency": "daily; NRC states status is collected between 4am and 8am ET",
        "data_class": "public/free",
        "execution_authority": "research-input",
        "collected_at": utc_now(),
        "latest_report_date": latest_date,
        "previous_report_date": previous_date,
        "latest": latest_aggregate,
        "previous": previous_aggregate,
        "day_over_day": {
            "fleet_shortfall_change_pct_points_unweighted": shortfall_change,
            "gas_substitution_direction": substitution,
            "changed_units": changes,
        },
        "outages": outages,
        "derates": derates,
        "latest_units": [
            {"unit": unit, "power_pct": power}
            for unit, power in sorted(latest_units.items())
        ],
        "daily_history": daily,
        "methodology_notes": [
            "NRC power percentages are unit-level and the fleet aggregate is equal-weighted, not MW-capacity-weighted.",
            "Use EIA-930 nuclear generation for actual capacity-weighted output and NRC for plant-level outage attribution.",
            "Gas substitution depends on regional load, available gas capacity, transmission and fuel constraints; this feed is not a standalone trade signal.",
        ],
    }


def upload_s3(path: Path, bucket: str, key: str) -> None:
    import boto3

    boto3.client("s3", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-2")).upload_file(
        str(path), bucket, key
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.getenv("NRC_OUT", "/var/lib/markets/free_ng/nrc_latest.json"))
    parser.add_argument("--recent-days", type=int, default=30)
    parser.add_argument("--s3-bucket", default=os.getenv("FREE_NG_S3_BUCKET", ""))
    parser.add_argument("--s3-key", default=os.getenv("NRC_S3_KEY", "drivers/free_ng/nrc_latest.json"))
    parser.add_argument("--s3-archive-prefix", default=os.getenv("NRC_S3_ARCHIVE_PREFIX", "drivers/nrc/reactor_status"))
    args = parser.parse_args()

    text = fetch_text()
    snapshot = build_snapshot(parse_rows(text), recent_days=args.recent_days)
    out = Path(args.out)
    atomic_json(out, snapshot)

    if args.s3_bucket:
        upload_s3(out, args.s3_bucket, args.s3_key)
        report_date = snapshot["latest_report_date"].replace("-", "/")
        upload_s3(out, args.s3_bucket, f"{args.s3_archive_prefix.strip('/')}/{report_date}.json")

    print(json.dumps({
        "status": "ok",
        "report_date": snapshot["latest_report_date"],
        "units": snapshot["latest"]["unit_count"],
        "outages": snapshot["latest"]["zero_power_units"],
        "derates": snapshot["latest"]["derated_units"],
        "shortfall_change": snapshot["day_over_day"]["fleet_shortfall_change_pct_points_unweighted"],
        "out": str(out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
