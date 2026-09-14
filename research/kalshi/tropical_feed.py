#!/usr/bin/env python3
"""tropical_feed.py - the TROPICAL / HURRICANE feed (S110; the named summer gap, memo 1.4).

WHY (Greg, S109, verbatim in the ledger): "Tanker flows will matter when hurricanes blow through
the gulf." A Gulf storm hits EXPORT CAPACITY (liquefaction: demand destruction, bearish) and GULF
PRODUCTION (supply loss, bullish) SIMULTANEOUSLY - the two pull price in OPPOSITE directions, and
departures (the vessel line) only CONFIRM afterward. This feed is the EARLY side: the track and
formation outlook, free, structured, from the NHC. `freeze_risk` is the winter twin; this is the
summer counterpart that did not exist. Season Aug-Oct is live NOW.

SOURCE (verified live at build time): https://www.nhc.noaa.gov/CurrentStorms.json - the NHC's
machine-readable active-cyclone index (id, name, classification, intensity, position, movement,
lastUpdate). Retrieval-dated snapshots, append-only store; each storm's own advisory time is the
knowable_from (an advisory is public the moment it posts).

THE GULF GEOMETRY (the trade-relevant flags, computed per storm):
- in_gulf_box: position inside lat 18..31, lon -98..-80 (GoM + approaches).
- min_terminal_dist_km + nearest terminal, against the four liquefaction sites the S109 ledger
  names: Sabine Pass, Corpus Christi, Freeport, Cameron. A storm bearing on one is the
  demand-destruction limb; a storm over the producing shelf is the supply limb. This feed serves
  the OBSERVABLE (position/track); the interpretation stays with the forecaster.

STORE: data/tropical/tropical.jsonl (append-only snapshots; S3 push is the orchestrator's step,
prefix tropical/). CONSUMER (feed-consumer rule D12): the paper/live daily loop context and the
supply.lng_export_throughput_vessel_line play's forward drivers - named here so this feed is born
with a reader, not served-but-unread.

USAGE
  python tropical_feed.py pull        (fetch + append a snapshot; prints the summary)
  python tropical_feed.py latest      (print the last stored snapshot's summary)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
STORE_DIR = os.path.join(HERE, "..", "..", "data", "tropical")
STORE = os.path.join(STORE_DIR, "tropical.jsonl")
URL = "https://www.nhc.noaa.gov/CurrentStorms.json"

TERMINALS = {"SabinePass": (29.73, -93.87), "CorpusChristi": (27.89, -97.28),
             "Freeport": (28.94, -95.31), "Cameron": (29.80, -93.33)}
GULF_BOX = (18.0, 31.0, -98.0, -80.0)   # lat_lo, lat_hi, lon_lo, lon_hi


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def enrich(storm: dict) -> dict:
    lat, lon = storm.get("latitudeNumeric"), storm.get("longitudeNumeric")
    out = {"id": storm.get("id"), "name": storm.get("name"),
           "classification": storm.get("classification"),
           "intensity_kt": storm.get("intensity"), "pressure_mb": storm.get("pressure"),
           "lat": lat, "lon": lon, "movement": storm.get("movementDir"),
           "movement_kt": storm.get("movementSpeed"),
           "advisory_utc": storm.get("lastUpdate"), "basin": storm.get("binNumber")}
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        out["in_gulf_box"] = (GULF_BOX[0] <= lat <= GULF_BOX[1]
                              and GULF_BOX[2] <= lon <= GULF_BOX[3])
        dists = {n: round(_km((lat, lon), p), 0) for n, p in TERMINALS.items()}
        near = min(dists, key=dists.get)
        out["nearest_terminal"] = near
        out["min_terminal_dist_km"] = dists[near]
    else:
        out["in_gulf_box"] = None
    return out


def pull() -> dict:
    with urllib.request.urlopen(URL, timeout=30) as r:
        raw = json.loads(r.read().decode())
    storms = [enrich(s) for s in raw.get("activeStorms", [])]
    snap = {"retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": URL, "n_active": len(storms),
            "n_gulf": sum(1 for s in storms if s.get("in_gulf_box")),
            "storms": storms,
            "note": ("knowable_from = each storm's advisory_utc (public at post time). "
                     "Empty activeStorms is a REAL reading (quiet basin), not a feed failure.")}
    os.makedirs(STORE_DIR, exist_ok=True)
    with open(STORE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(snap) + "\n")
    return snap


def latest() -> dict | None:
    if not os.path.exists(STORE):
        return None
    last = None
    with open(STORE, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                last = line
    return json.loads(last) if last else None


def summary(snap: dict) -> str:
    if not snap:
        return "[tropical] no snapshot stored"
    lines = [f"[tropical] {snap['retrieved_utc']} - {snap['n_active']} active, "
             f"{snap['n_gulf']} in the Gulf box"]
    for s in snap["storms"]:
        gulf = "GULF" if s.get("in_gulf_box") else ("?" if s.get("in_gulf_box") is None else "not-gulf")
        lines.append(f"  {s.get('classification','?'):>3} {s.get('name','?'):<12} {gulf:<8} "
                     f"{s.get('intensity_kt','?')}kt  nearest {s.get('nearest_terminal','-')} "
                     f"{s.get('min_terminal_dist_km','-')}km  adv {s.get('advisory_utc')}")
    if snap["n_active"] == 0:
        lines.append("  (quiet basin - a real reading)")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["pull", "latest"])
    a = ap.parse_args()
    if a.cmd == "pull":
        print(summary(pull()))
    else:
        print(summary(latest()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
