from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


REPORTS_DIR = Path("reports")


def report_path_for(day: str | None = None, reports_dir: str | Path = REPORTS_DIR) -> Path:
    if day is None:
        compact = date.today().strftime("%Y%m%d")
    else:
        compact = str(day).replace("-", "")
    return Path(reports_dir) / f"daily_health_report_{compact}.json"


def load_daily_health_report(day: str | None = None, reports_dir: str | Path = REPORTS_DIR) -> dict[str, Any]:
    path = report_path_for(day, reports_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def family_report(report: dict[str, Any], family: str) -> dict[str, Any]:
    return dict(((report.get("summary") or {}).get("families") or {}).get(str(family).lower(), {}))


def bucket_report(report: dict[str, Any], bucket_id: str) -> dict[str, Any]:
    return dict((report.get("buckets") or {}).get(bucket_id, {}))


def venue_report(report: dict[str, Any], family: str, asset: str, venue: str) -> dict[str, Any]:
    key = "|".join([str(family).lower(), str(asset).upper(), str(venue).lower()])
    return dict((report.get("venues") or {}).get(key, {}))


def family_daily_limit_report(report: dict[str, Any], family: str) -> dict[str, Any]:
    return dict(((report.get("daily_limits_state") or {}).get("families") or {}).get(str(family).lower(), {}))


def bucket_daily_limit_report(report: dict[str, Any], bucket_id: str) -> dict[str, Any]:
    return dict(((report.get("daily_limits_state") or {}).get("buckets") or {}).get(bucket_id, {}))
