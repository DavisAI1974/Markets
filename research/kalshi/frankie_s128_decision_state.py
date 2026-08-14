#!/usr/bin/env python3
"""S128 decision-state entrypoint with contract-only serving repairs installed."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import frankie_s128_contract_repairs as repairs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("decision-state", nargs="?")
    ap.add_argument("--days", required=True)
    ap.add_argument("--out")
    ap.add_argument("--group")
    ap.add_argument("--mask-after", default=None)
    a = ap.parse_args()
    ds = repairs.decision_state(a.days.split(","), mask_after=a.mask_after, group=a.group)
    print(json.dumps(ds, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(ds), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
