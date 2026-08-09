#!/usr/bin/env python3
"""Reproducible S118 two-group Frankie validation entrypoint.

G18/G19 are the first current-format walked groups whose committed masked STATE artifacts are
present on the Frankie branch. This wrapper reconstructs only disposable causal slices and declared
anchor lookup files, then delegates to frankie_group_forecast_s118. Realized actuals remain unread
until scoring after all forecasts are written.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import group_config as gc  # noqa: E402
import frankie_group_forecast_s118 as runner  # noqa: E402

GROUPS = ("g18", "g19")
RENDERS = HERE / "renders" / "ng_refine_s95"


def _materialize_anchor(gid: str) -> Path:
    g = gc.GROUPS[gid]
    anchor = g.get("anchor")
    date = str(g.get("anchor_date") or "").replace("-", "")
    last = g.get("anchor_lasthr_dir")
    if anchor is None or len(date) != 8 or last not in (-1, 1):
        raise RuntimeError(f"{gid}: unresolved declared anchor")
    p = RENDERS / f"{gid}_anchor.json"
    p.write_text(json.dumps({
        "schema_version": "s118_ephemeral_anchor_v1",
        "group": gid,
        "date": date,
        "price": float(anchor),
        "last_hour_dir": "up" if last > 0 else "down",
        "last_hour_dir_numeric": int(last),
        "source": "group_config.GROUPS declared values",
        "actual_tape_read": False,
        "ephemeral_validation_artifact": True,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def _build_slices(gid: str) -> Path:
    state = RENDERS / f"grp{gid[1:]}_state.json"
    if not state.is_file():
        raise RuntimeError(f"{gid}: committed state missing: {state}")
    out = RENDERS / f"{gid}_causal_slices"
    done = subprocess.run(
        [sys.executable, str(HERE / "build_causal_slices.py"), gid, "--write", "--outdir", str(out)],
        cwd=str(HERE), text=True, capture_output=True, check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(f"{gid}: causal-slice build failed:\n{(done.stdout + done.stderr)[-5000:]}")
    expected = [out / f"state_{d}.json" for d in gc.GROUPS[gid]["days"]]
    missing = [str(p) for p in expected if not p.is_file()]
    if missing:
        raise RuntimeError(f"{gid}: causal-slice build left missing files: {missing[:3]}")
    return out


def prepare() -> dict:
    runner.ALLOWED_GROUPS = GROUPS
    result = []
    for gid in GROUPS:
        anchor = _materialize_anchor(gid)
        slices = _build_slices(gid)
        result.append({
            "group": gid,
            "anchor": str(anchor),
            "causal_slices": str(slices),
            "state": str(RENDERS / f"grp{gid[1:]}_state.json"),
            "actual_tape_read": False,
        })
    return {"groups": result, "actual_tape_read": False}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--namespace", default="frankie_s118_b")
    ap.add_argument("--backend", choices=("openai", "bedrock"), default="openai")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--score-only", action="store_true")
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args()
    try:
        prep = prepare()
        if args.preflight:
            result = {
                "prepare": prep,
                "packets": [runner.preflight_group(g, args.namespace) for g in GROUPS],
            }
        elif args.score_only:
            result = {
                "prepare": prep,
                "scores": [runner.score_group(g, args.namespace) for g in GROUPS],
            }
        else:
            runs = []
            for gid in GROUPS:
                run = runner.run_group(
                    gid, args.namespace, args.backend, resume=not args.no_resume
                )
                score = runner.score_group(gid, args.namespace)
                runs.append({"run": run, "score": score})
            result = {"prepare": prep, "runs": runs}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"STOP - {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
