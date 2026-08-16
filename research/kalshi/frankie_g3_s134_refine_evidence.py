#!/usr/bin/env python3
"""S134 full-window G3 refine evidence extractor.

Post-score refine only.  This script is intentionally UNBLINDED to the already-scored Sep 8-19,
2025 NGV25 tape so the refine pass can learn WHY each of the ten sessions moved.  It does not alter
S131/S132 artifacts, the brain, specialist roles, spawn.py, or group_config.py.

The extractor reuses the canonical generic MBO evidence engine after installing S131's in-process
G3 contract.  Output is per-event/per-day evidence only: price excursion, onset, turn, signed flow,
phase price/flow and absorption.  Nothing is pooled into a fitted rule here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import frankie_g3_reblind_s131 as g3


def build() -> dict:
    g3.install_g3_context()
    import group_mbo_engine as mbo

    days = {}
    for day in g3.DAYS:
        days[day] = mbo.per_day_evidence(g3.GID, day)
    return {
        "phase": "POST_SCORE_UNBLINDED_REFINE_EVIDENCE",
        "group": g3.GID,
        "window": "2025-09-08..2025-09-19",
        "scored_leg": "NGV25",
        "actuals_read": True,
        "hydration": "REJECTED_NOT_USED",
        "new_datapoint_family_added": False,
        "rule": "per-day causal fingerprint for refine; do not pool/average into a fitted answer",
        "days": days,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    obj = build()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "READY", "days": len(obj["days"]), "out": str(a.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
