#!/usr/bin/env python3
"""S130 historical hydration utility for current Frankie decision states.

This does NOT add datapoint families or alter Frankie brain/schema. It materializes existing
historical inputs that are causally recoverable, records explicit availability, and refuses to
launder hindsight from legacy realized proxies into a blind packet.

For G3 Sep 8-19 2025 the legacy archive is used ONLY to recover weekly EIA storage report payloads.
Visibility is recomputed here with report_date STRICTLY BEFORE decision day, fixing the historical
same-Thursday bug. Current modules are expected to have rebuilt any public stores (COT, regional
storage, solar calendar, STEO, grid/nuclear when available) before this adapter is run.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SEED = HERE / "historical" / "g3_s130_storage_seed.json"


def _decision_days(state: dict) -> list[str]:
    return sorted(k for k in state if len(k) == 8 and k.isdigit())


def _latest_prior_report(day_ymd: str, reports: dict) -> tuple[str, dict] | None:
    day = dt.date(int(day_ymd[:4]), int(day_ymd[4:6]), int(day_ymd[6:8]))
    eligible = []
    for report_iso, payload in reports.items():
        rd = dt.date.fromisoformat(report_iso)
        if rd < day:  # STRICT blind wall: own Thursday print is not visible at the open.
            eligible.append((rd, report_iso, payload))
    if not eligible:
        return None
    _, report_iso, payload = max(eligible)
    return report_iso, payload


def hydrate(state: dict, seed: dict) -> dict:
    out = json.loads(json.dumps(state))
    reports = seed.get("reports", {})
    days = _decision_days(out)

    for day in days:
        row = out[day]
        visible = _latest_prior_report(day, reports)
        if visible is not None:
            report_iso, payload = visible
            # Existing current-schema fields only. No schema expansion.
            row["storage"] = payload.get("storage")
            row["stor_surprise"] = payload.get("stor_surprise")
            row["stor_surprise_sign"] = payload.get("stor_surprise_sign")
            row["stor_surprise_basis"] = payload.get("stor_surprise_basis")
            assert row["storage"]["as_of"] == report_iso
            assert dt.date.fromisoformat(report_iso) < dt.date(
                int(day[:4]), int(day[4:6]), int(day[6:8])
            )

        # Never recover the legacy realized weather proxy. Current forecast-vintage modules own
        # these fields; if their vintage store is absent they remain unavailable.
        if row.get("weather") and isinstance(row["weather"], dict):
            note = str(row["weather"].get("note", ""))
            if "realized_as_proxy" in note:
                raise AssertionError(f"{day}: realized weather proxy reached S130 current state")

    # Availability is descriptive, not a new input. Count top-level current-schema channels.
    ignored = {"dow", "holiday"}
    channel_names = sorted({k for d in days for k in out[d] if k not in ignored})
    counts = {k: sum(out[d].get(k) is not None for d in days) for k in channel_names}
    out["_historical_hydration"] = {
        "schema": "frankie_historical_hydration_manifest_v1",
        "group": seed.get("group"),
        "window": seed.get("window"),
        "source": seed.get("provenance"),
        "strict_storage_wall": True,
        "legacy_realized_weather_rejected": True,
        "channel_non_null_day_counts": counts,
        "fully_populated_channels": [k for k, n in counts.items() if n == len(days)],
        "partially_populated_channels": [k for k, n in counts.items() if 0 < n < len(days)],
        "unavailable_channels": [k for k, n in counts.items() if n == 0],
        "decision_days": days,
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--seed", default=str(DEFAULT_SEED))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    state = json.loads(Path(a.state).read_text(encoding="utf-8"))
    seed = json.loads(Path(a.seed).read_text(encoding="utf-8"))
    out = hydrate(state, seed)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    m = out["_historical_hydration"]
    print(json.dumps(m, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
