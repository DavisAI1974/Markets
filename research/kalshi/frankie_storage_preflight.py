#!/usr/bin/env python3
"""Frankie storage preflight: build and verify the weekly EIA storage stores with no API key.

This is deterministic data plumbing, not model logic. It uses EIA's official WNGSR history workbook,
builds the existing regional store, then builds the legacy national KXNATGASD compatibility records
that forecast_harness already expects. It fails closed if either view is absent or disagrees on the
Lower-48 level/change for the latest completed report.
"""
from __future__ import annotations

import json
from pathlib import Path

import eia_storage_compat
import storage_regional as sr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
REGIONAL = ROOT / "data" / "storage_regional" / "storage_regional.json"
NATIONAL = ROOT / "data" / "eia_surprise.json"


def run() -> dict:
    raw, prov = sr.fetch_all_xls()
    records = sr.build_records(raw, prov=prov, source="EIA_WNGSR_ngshistory_xls")
    if not records:
        raise RuntimeError("regional storage store built zero records")
    REGIONAL.parent.mkdir(parents=True, exist_ok=True)
    REGIONAL.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")

    existing = {}
    if NATIONAL.exists():
        try:
            existing = json.loads(NATIONAL.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    existing["KXNATGASD"] = eia_storage_compat.build_kxnatgasd()
    NATIONAL.parent.mkdir(parents=True, exist_ok=True)
    NATIONAL.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")

    kx = existing["KXNATGASD"]
    latest = max(kx)
    reg = records.get(latest)
    if reg is None:
        raise RuntimeError(f"national latest release {latest} absent from regional store")
    l48 = reg["regions"]["l48"]
    nat = kx[latest]
    nat_level = float(nat["prev_level"]) + float(nat["actual"])
    if abs(nat_level - float(l48["level"])) > 0.11:
        raise RuntimeError("national/regional Lower-48 level disagreement")
    if abs(float(nat["actual"]) - float(l48["weekly_chg"])) > 0.11:
        raise RuntimeError("national/regional Lower-48 weekly-change disagreement")

    return {
        "status": "READY",
        "regional_reports": len(records),
        "national_reports": len(kx),
        "latest_release": latest,
        "latest_period": reg.get("period"),
        "latest_l48_level_bcf": l48.get("level"),
        "latest_l48_weekly_chg_bcf": l48.get("weekly_chg"),
        "source": "EIA_WNGSR_ngshistory_xls",
        "api_key_required": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
