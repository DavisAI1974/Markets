#!/usr/bin/env python3
"""Insert daylight/load-shape features into the existing free-NG snapshot.

This mutates the same snapshot produced by free_ng_data_collector.py. It does not
emit a competing signal or standalone verdict. The enrichment lives at
sources.nws.load_shape and is consumed by the existing power-burn projection.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import daylight_load_shape as dls


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def enrich(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = payload.setdefault("sources", {})
    nws = sources.setdefault("nws", {})
    nws["load_shape"] = dls.live_profile()
    nws["load_shape_integration"] = {
        "role": "enrichment of existing load/power-burn projection",
        "standalone_signal": False,
        "notes": [
            "Civil twilight represents streetlight and residential/commercial lighting transitions.",
            "Solar geometry is an expected clear-sky envelope; weather and observed native load determine surprise.",
            "Summer and winter retain separate calendar curve regimes.",
        ],
    }
    atomic_json(path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default=os.getenv("FREE_NG_OUT", "/var/lib/markets/free_ng/latest.json"))
    args = parser.parse_args()
    path = Path(args.path)
    if not path.exists():
        parser.error(f"snapshot does not exist: {path}")
    payload = enrich(path)
    shape = payload["sources"]["nws"]["load_shape"]
    print(json.dumps({
        "status": "ok",
        "path": str(path),
        "phase": shape.get("current_phase"),
        "curve_regime": shape.get("calendar_curve_regime"),
        "daylight_hours": shape.get("daylight_hours"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
