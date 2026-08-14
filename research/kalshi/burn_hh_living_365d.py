#!/usr/bin/env python3
"""Rebuild the active burn/Henry Hub dataset as the latest complete 365-day window.

This is a neutral data-maintenance wrapper around burn_hh_12m_event_ledger.py.
It detects the latest date shared by the EIA US48 generation workbook and the
Henry Hub daily history, then rebuilds exactly 365 calendar days ending there.
Large source workbooks stay temporary; the stable output keeps the two CSVs,
README, and a manifest with source hashes for provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from burn_hh_12m_event_ledger import get_eia_daily_fuels, get_henry_hub_daily


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--out",
        default="research/kalshi/burn_hh_living/current",
        help="Stable directory for the active 365-day snapshot.",
    )
    p.add_argument(
        "--probe-days",
        type=int,
        default=45,
        help="Recent calendar days to inspect when locating the latest common date.",
    )
    p.add_argument(
        "--max-lag-days",
        type=int,
        default=21,
        help="Fail if the latest common source date is older than this many days.",
    )
    return p.parse_args()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    args = parse_args()
    today_et = datetime.now(ZoneInfo("America/New_York")).date()
    probe_start = today_et - timedelta(days=args.probe_days)

    fuels, _, _ = get_eia_daily_fuels(probe_start, today_et)
    hh, _ = get_henry_hub_daily()
    common = sorted(
        d for d in hh if probe_start <= d <= today_et and fuels.get(d, {}).get("NG") is not None
    )
    if not common:
        raise SystemExit("No recent date is shared by EIA US48 generation and Henry Hub history.")

    end = common[-1]
    lag_days = (today_et - end).days
    if lag_days > args.max_lag_days:
        raise SystemExit(
            f"Latest common source date {end} is {lag_days} days old; "
            f"max allowed is {args.max_lag_days}."
        )
    start = end - timedelta(days=364)

    script = Path(__file__).with_name("burn_hh_12m_event_ledger.py")
    stable = Path(args.out)
    stable.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="burn_hh_living_") as tmp:
        tmpdir = Path(tmp)
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--start",
                start.isoformat(),
                "--end",
                end.isoformat(),
                "--out",
                str(tmpdir),
            ],
            check=True,
        )

        for name in ("README.md", "physical_daily_365d.csv", "hh_trading_day_event_ledger.csv"):
            shutil.copy2(tmpdir / name, stable / name)

        manifest = {
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "window_days": 365,
            "latest_common_source_date": end.isoformat(),
            "source_lag_days_at_build": lag_days,
            "built_at_et": datetime.now(ZoneInfo("America/New_York")).isoformat(),
            "source_sha256": {
                "eia_region_us48_source.xlsx": sha256(tmpdir / "eia_region_us48_source.xlsx"),
                "henry_hub_source.xls": sha256(tmpdir / "henry_hub_source.xls"),
            },
            "method": "event-level; active recent-year window",
        }
        (stable / "CURRENT_WINDOW.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
