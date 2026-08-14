#!/usr/bin/env python3
"""Build the legacy national-storage compatibility store from EIA's public WNGSR workbook.

Frankie's existing decision-state contract reads `data/eia_surprise.json` for the top-level
`storage` block. That generated file is not guaranteed to exist in a fresh checkout. The regional
storage feed already has an official no-key EIA workbook fallback containing the same Lower-48
series plus the regional/salt detail. This builder derives the existing KXNATGASD record shape from
that source without changing Frankie's schema or adding a new signal.

Only KXNATGASD is replaced. Any other series already present in the output file are preserved.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import storage_regional as sr


def build_kxnatgasd() -> dict:
    raw, prov = sr.fetch_all_xls()
    records = sr.build_records(raw, prov=prov, source="EIA_WNGSR_ngshistory_xls")
    out = {}
    for release_date, rec in sorted(records.items()):
        l48 = (rec.get("regions") or {}).get("l48") or {}
        level = l48.get("level")
        actual = l48.get("weekly_chg")
        if level is None or actual is None:
            continue
        surprise = l48.get("chg_vs_5yr_chg")
        seasonal_exp = None if surprise is None else actual - surprise
        out[release_date] = {
            "period": rec.get("period"),
            "actual": round(float(actual), 3),
            "seasonal_exp": None if seasonal_exp is None else round(float(seasonal_exp), 3),
            "surprise": None if surprise is None else round(float(surprise), 3),
            "prev_level": round(float(level) - float(actual), 3),
            "unit": "Bcf",
            "source": "EIA_WNGSR_ngshistory_xls_via_storage_regional",
        }
    if not out:
        raise RuntimeError("no Lower-48 storage records built from EIA workbook")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/eia_surprise.json")
    args = ap.parse_args()
    path = Path(args.out)
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    existing["KXNATGASD"] = build_kxnatgasd()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    rows = existing["KXNATGASD"]
    print(json.dumps({"records": len(rows), "first_release": min(rows), "last_release": max(rows), "out": str(path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
