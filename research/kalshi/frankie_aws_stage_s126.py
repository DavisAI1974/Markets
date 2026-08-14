#!/usr/bin/env python3
"""Fail-closed AWS staging preflight for the current Frankie build (S126).

This does NOT create or change a wind/solar model. It restores the existing data plane from S3,
stages the requested group through the canonical stage_group path, rebuilds the per-day causal slices,
and proves the already-built S114 weather_forcing_forecast is populated in both the group state and
every specialist slice before Frankie may run.

Canonical AWS recovery for the currently stale g24 artifacts:

    env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY \
      python research/kalshi/frankie_aws_stage_s126.py g24

Why this wrapper exists: restore_substrate.py --group already restores nymex/gefs_forcing/ and calls
stage_group.py, and stage_group already fail-closes through state_health. But stage_group does not
rebuild g<N>_causal_slices after replacing grp<N>_state.json. A fresh good state could therefore sit
next to stale specialist slices. This wrapper closes that final staging seam without touching Frankie's
schema/settings/inputs, specialist roles, spawn.py, or the blind artifacts.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RENDERS = HERE / "renders" / "ng_refine_s95"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import group_config as gc  # noqa: E402


class StageInvariantError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StageInvariantError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise StageInvariantError(f"expected JSON object: {path}")
    return obj


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _require_forcing(day: str, block: Any, where: str) -> dict[str, Any]:
    if not isinstance(block, dict) or not block:
        raise StageInvariantError(f"STALE_STATE: {where} {day} has no weather_forcing_forecast")
    if block.get("wind_cf_proxy") is None:
        raise StageInvariantError(f"STALE_STATE: {where} {day} has no wind_cf_proxy")
    if block.get("solar_irradiance_proxy") is None:
        raise StageInvariantError(f"STALE_STATE: {where} {day} has no solar_irradiance_proxy")
    if block.get("served_separately") is not True:
        raise StageInvariantError(f"S114_CONTRACT: {where} {day} does not keep wind/solar separate")
    if block.get("is_forecast_not_realized") is not True:
        raise StageInvariantError(f"CAUSAL_WALL: {where} {day} is not marked forecast-not-realized")
    if not block.get("cycle_utc") or not block.get("knowable_from"):
        raise StageInvariantError(f"CAUSAL_WALL: {where} {day} lacks forcing timestamps")
    iso_day = f"{day[:4]}-{day[4:6]}-{day[6:]}"
    if str(block["knowable_from"])[:10] >= iso_day:
        raise StageInvariantError(
            f"CAUSAL_WALL: {where} {day} forcing knowable_from={block['knowable_from']} is not pre-day"
        )
    return block


def validate_served_forcing(gid: str, renders: Path = RENDERS) -> dict[str, Any]:
    """Prove S114 wind+solar is present and identical in state and every causal specialist slice."""
    if gid not in gc.GROUPS:
        raise StageInvariantError(f"unknown group {gid!r}")
    days = list(gc.GROUPS[gid]["days"])
    state_path = renders / f"grp{gid[1:]}_state.json"
    slices_dir = renders / f"{gid}_causal_slices"
    state = _read_json(state_path)
    checked: dict[str, Any] = {}
    for day in days:
        state_block = _require_forcing(
            day,
            (state.get(day) or {}).get("weather_forcing_forecast"),
            state_path.name,
        )
        slice_path = slices_dir / f"state_{day}.json"
        slice_obj = _read_json(slice_path)
        slice_block = _require_forcing(
            day,
            (slice_obj.get(day) or {}).get("weather_forcing_forecast"),
            slice_path.name,
        )
        if slice_block != state_block:
            raise StageInvariantError(
                f"STALE_SLICE: {slice_path.name} weather_forcing_forecast differs from canonical state"
            )
        # Physical causal wall: no future day blocks may be present in the specialist slice.
        future = sorted(k for k in slice_obj if k[:1].isdigit() and k > day)
        if future:
            raise StageInvariantError(
                f"CAUSAL_WALL: {slice_path.name} contains future day blocks: {future[:5]}"
            )
        checked[day] = state_block
    return {
        "group": gid,
        "days": len(days),
        "state": str(state_path),
        "slices": str(slices_dir),
        "weather_forcing_forecast": "PASS",
        "wind_solar_separate": True,
        "causal_slices": "PASS",
    }


def stage_for_aws(gid: str) -> dict[str, Any]:
    """Restore canonical S3 substrate, stage group, rebuild causal slices, then fail-closed verify."""
    if gid not in gc.GROUPS:
        raise StageInvariantError(f"unknown group {gid!r}")

    # Blind artifacts are historical evidence. They must remain byte-for-byte untouched by recovery.
    blind = RENDERS / f"grp{gid[1:]}_state_blind_s114.json"
    blind_before = _sha256(blind)

    # restore_substrate --group pulls nymex/gefs_forcing/ -> data/gefs_forcing and invokes the
    # canonical stage_group path, which runs state_health.assert_healthy before completing.
    subprocess.run(
        [sys.executable, str(HERE / "restore_substrate.py"), "--group", gid],
        cwd=str(ROOT),
        check=True,
    )

    # Rebuild specialist-facing physical causal walls from the newly staged canonical state.
    slices_dir = RENDERS / f"{gid}_causal_slices"
    subprocess.run(
        [
            sys.executable,
            str(HERE / "build_causal_slices.py"),
            gid,
            "--write",
            "--outdir",
            str(slices_dir),
        ],
        cwd=str(ROOT),
        check=True,
    )

    result = validate_served_forcing(gid)
    blind_after = _sha256(blind)
    if blind_before != blind_after:
        raise StageInvariantError(
            f"BLIND_ARTIFACT_MUTATED: {blind} changed during AWS recovery; refusing to run Frankie"
        )
    result["blind_artifact_unchanged"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: frankie_aws_stage_s126.py <group>  (current recovery target: g24)", file=sys.stderr)
        return 2
    try:
        result = stage_for_aws(args[0])
    except (StageInvariantError, subprocess.CalledProcessError) as exc:
        print(f"[frankie-aws-stage] FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    print("[frankie-aws-stage] PASS: AWS substrate -> canonical state -> causal specialist slices")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
