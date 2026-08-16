#!/usr/bin/env python3
"""Prepare a post-reveal REFINE packet for a completed S135 date session.

This is deliberately NOT a blind rerun.  Frozen blind forecasts are read verbatim and hashed.  The
realized target-session tape is now legal learning evidence.  Frankie is served the CURRENT brain at
full capacity: the raw current brain is exported unchanged and the convenience specialist view is
built WITHOUT window_days, so no historical-date/window redaction is applied.

The model-facing refine contract is intentionally simple:
  * ONE refined forecast per session.
  * ONE event-driven P50 path for that forecast.
  * Frankie chooses every event point and every timestamp.
  * No fixed clock, no cadence, no required point count, no filler points.
  * No P25/P75 side forecasts.
  * The immutable blind remains the baseline; refine may use the revealed tape to learn mechanism.
  * Missing historical source families remain genuinely missing; no hydration/synthesis.

This module prepares evidence only.  It does not edit the brain, specialist roles, schema, spawn.py,
group_config.py, blind outputs, or datapoint universe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

import brain_view
import frankie_s135_date_render as date_render
import frankie_s135_date_session as date_session
import group_actual
import group_config as gc
import group_mbo_engine

GID = "gdate"
MULT = 10000.0
ET = "America/New_York"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _forecast_file(outputs: Path, day: str) -> Path:
    hits = sorted(outputs.glob(f"forecast_*_{day}.json"))
    if len(hits) != 1:
        raise SystemExit(f"{day}: expected exactly one frozen blind forecast, got {hits}")
    return hits[0]


def _minute_actual_path(day: str) -> list[dict[str, Any]]:
    """A readable representation of the revealed tape; this is evidence, never a forecast clock."""
    store = gc.leg_for(GID, day)
    ts, px = group_actual.load_trades(store, day)
    if len(px) == 0:
        raise SystemExit(f"{day}: no realized trades for {store}")
    et = pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET)
    open_px = float(px[0])
    s = pd.Series(px, index=et).resample("1min").last().dropna()
    return [
        {"timestamp_et": t.isoformat(), "cum_usd_from_session_open": round((float(v) - open_px) * MULT, 1)}
        for t, v in s.items()
    ]


def build(config: Path, out: Path) -> dict[str, Any]:
    cfg = _read(config)
    date_render.install_config(cfg)
    outputs = ROOT / str(cfg["outputs"])
    days = [str(x).replace("-", "") for x in cfg["days"]]

    # Ensure the exact historical MBO legs/prior stores exist locally.  This is staging only; no
    # blind forecast is run and no target outcome is hidden in this post-reveal phase.
    stage = date_session._stage_blind_inputs(GID)
    state, _state_path = date_session._build_state(GID)

    out.mkdir(parents=True, exist_ok=True)
    brain = brain_view.load()
    raw_brain_path = out / "current_brain_full.json"
    _write(raw_brain_path, brain)
    brain_meta = brain.get("meta") or {}
    plays = brain.get("plays") or []

    actual_block = group_actual.build(GID)
    actual_by_day = {str(x["date"]): x for x in actual_block["days"]}

    blind_manifest = []
    packets = []
    for day in days:
        fpath = _forecast_file(outputs, day)
        blind = _read(fpath)
        blind_manifest.append({"date": day, "file": str(fpath.relative_to(ROOT)), "sha256": _sha(fpath)})

        # CURRENT brain; intentionally NO window_days.  This is the key difference from a blind
        # historical run: later-learned evidence is not removed merely because the tape date is old.
        view, served, withheld = brain_view.build(brain, "specialist", phase="working", window_days=None)
        if "window_redaction" in (view.get("meta") or {}):
            raise SystemExit(f"{day}: REFINE brain view unexpectedly contains window_redaction")
        view = brain_view.annotate_evaluability(view, state[day])
        view_path = out / f"brain_view_current_{day}.json"
        _write(view_path, view)

        actual_evidence = group_mbo_engine.per_day_evidence(GID, day)
        packet = {
            "phase": "POST_REVEAL_REFINE_REQUEST",
            "group_runtime_id": GID,
            "date": day,
            "specialist": blind.get("specialist"),
            "brain_rule": {
                "current_brain_full_capacity": True,
                "current_brain_file": raw_brain_path.name,
                "current_specialist_view_file": view_path.name,
                "historical_date_window_redaction": False,
                "later_learned_current_brain_evidence_available": True,
                "working_sections_served": served,
                "role_scoped_sections_withheld_only_by_normal_current_role_contract": withheld,
            },
            "blind_rule": {
                "blind_is_immutable": True,
                "blind_file": str(fpath.relative_to(ROOT)),
                "blind_sha256": _sha(fpath),
                "blind_forecast": blind,
            },
            "revealed_learning_evidence": {
                "actual_day": actual_by_day[day],
                "mbo_mechanism": actual_evidence,
                "actual_path_1min": _minute_actual_path(day),
                "actual_path_note": "1-minute tape representation is evidence only. It does not prescribe forecast timestamps or cadence.",
            },
            "refine_output_contract": {
                "one_forecast_only": True,
                "forecast_path": "one P50 event-driven path",
                "p25_p75_outputs": "FORBIDDEN_IN_THIS_REFINE",
                "fixed_clock": False,
                "fixed_point_count": False,
                "minimum_point_count": None,
                "maximum_point_count": None,
                "filler_points": "FORBIDDEN",
                "timestamp_rule": "Frankie chooses a timestamp only when he expects a meaningful market-state transition; scheduled events may naturally have exact event times.",
                "blind_baseline_must_remain_unchanged": True,
                "refine_may_see_target_tape": True,
                "purpose": "learn the mechanism and produce the posterior single forecast; do not fit a memorized day-specific answer",
                "hydration": "REJECTED_NOT_USED",
                "new_datapoint_family": False,
            },
        }
        packet_path = out / f"refine_packet_{blind.get('specialist')}_{day}.json"
        _write(packet_path, packet)
        packets.append(packet_path.name)

    manifest = {
        "status": "READY_FOR_CURRENT_FRANKIE_REFINE",
        "phase": "POST_REVEAL_REFINE",
        "window": f"{days[0]}..{days[-1]}",
        "days": days,
        "packet_count": len(packets),
        "packets": packets,
        "current_brain": {
            "file": raw_brain_path.name,
            "sha256": _sha(raw_brain_path),
            "version": brain_meta.get("version"),
            "canonical_plays": len(plays),
            "window_redaction": False,
        },
        "blind_manifest": blind_manifest,
        "blind_rerun": False,
        "actuals_visible": True,
        "hydration": "REJECTED_NOT_USED",
        "stage": stage,
        "next_step": "Current ChatGPT/Frankie reads each packet + current brain, writes one event-driven P50 refine per day, then performs a separate blind-vs-refine learning analysis.",
    }
    _write(out / "manifest.json", manifest)
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    m = build(a.config, a.out)
    print(json.dumps({
        "status": m["status"],
        "window": m["window"],
        "packets": m["packet_count"],
        "brain_version": m["current_brain"]["version"],
        "plays": m["current_brain"]["canonical_plays"],
        "blind_rerun": m["blind_rerun"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
