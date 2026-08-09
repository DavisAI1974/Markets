#!/usr/bin/env python3
"""Report readiness against FRANKIE_BUILD_BRIEF_S115.md without pretending missing data is ready."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import group_config as gc  # noqa: E402
from frankie_s115 import OWNERSHIP, assert_ownership_clean  # noqa: E402

RENDERS = HERE / "renders" / "ng_refine_s95"
ROOT_DATA = HERE.parents[1] / "data"


def _actual_days(gid: str) -> tuple[bool, int, str | None]:
    path = RENDERS / f"{gid}_actual.json"
    if not path.is_file():
        return False, 0, None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False, 0, "INVALID_JSON"
    days = raw.get("days") if isinstance(raw, dict) else None
    return True, len(days or []), str(raw.get("basis")) if isinstance(raw, dict) else None


def status() -> dict:
    assert_ownership_clean()
    corpus = {}
    total = 0
    for n in range(6, 25):
        gid = f"g{n}"
        if gid not in gc.GROUPS:
            continue
        state = RENDERS / f"grp{n}_state.json"
        actual, ndays, basis = _actual_days(gid)
        usable = state.is_file() and actual and ndays > 0
        corpus[gid] = {
            "state": state.is_file(),
            "actual": actual,
            "actual_days": ndays,
            "usable_for_a69": usable,
            "basis": basis or gc.GROUPS[gid].get("basis"),
        }
        if usable:
            total += ndays
    head_trade_dir = ROOT_DATA / "nymex_cont_n0"
    l1_dir = ROOT_DATA / "nymex_mbp10"
    return {
        "schema_version": "1.0",
        "sequence": [
            "M-16/A-61/A-50",
            "A-66",
            "A-59/A-68/A-62",
            "A-65",
            "A-67-arm1/A-69",
            "A-67-arm2/A-42",
            "LATER:A-5+A-63+A-60",
        ],
        "implemented_contracts": {
            "M-16_guarded_entry": str(HERE / "databento_backfill_s115.py"),
            "A-61_snapshot": True,
            "A-50_narrative_leak_guard": True,
            "A-66_ownership_clean": True,
            "A-59_render_and_typed_write": True,
            "A-68_causal_lens_book": True,
            "A-62_generated_track_records": True,
            "A-65_same_cell_posterior_diff": True,
            "A-67_per_event_ab_contract": True,
            "A-69_disjoint_heldout_and_fj1_gate": True,
            "A-42_fj1_adapter": True,
            "A-63_A-60": "DEFERRED_BY_S115_UNTIL_A-5_LIBRARY_INDEX",
        },
        "ownership": OWNERSHIP,
        "data_plane": {
            "nymex_cont_n0_exists": head_trade_dir.is_dir(),
            "nymex_cont_n0_files": len(list(head_trade_dir.glob("*"))) if head_trade_dir.is_dir() else 0,
            "nymex_mbp10_exists": l1_dir.is_dir(),
            "nymex_mbp10_files": len(list(l1_dir.glob("*"))) if l1_dir.is_dir() else 0,
            "note": "file existence is only a preflight; A-67 still requires a pinned staged head seal",
        },
        "a69_corpus": {"measured_usable_days_in_tree": total, "groups": corpus},
        "execution_enabled": False,
    }


def main() -> int:
    print(json.dumps(status(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
