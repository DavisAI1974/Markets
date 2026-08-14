#!/usr/bin/env python3
"""S127 blind-only Frankie launcher for the sanctioned g24 state.

This is a thin execution seam over the existing S121/S126 Frankie stack. It does not change
Frankie's brain, schema, settings, causal inputs, specialist roles, or protected spawn.py. Its jobs
are deliberately narrow:
- pin the current g24 state/slices and protected role/spawn files to the sanctioned S126 commit;
- scope the legacy S118 orchestrator to g24 in-process without widening the old validation CLI;
- preserve the S120 full-brain/A-82 guards, S121 curve contract, and S126 specialist parity;
- run blind preflight or blind forecast only through the existing OpenAI backend.

There is intentionally no score or refine phase here. Outcome access remains a separate later step
after the complete blind g24 group is frozen.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_group_forecast_s118 as base  # noqa: E402
import frankie_s121_curve_restore as s121  # noqa: E402
import frankie_specialist_parity_s126 as s126  # noqa: E402
import group_config as gc  # noqa: E402
from frankie_core import verify_original_spawn  # noqa: E402

GID = "g24"
PHASES = ("preflight", "forecast")
DEFAULT_NAMESPACE = "frankie_g24_s127_openai"
OPENAI_MODEL = "gpt-5.6-sol"
SANCTIONED_ARTIFACT_COMMIT = "5d0354b5230c5fe746c639608075e0a3f2a54735"

_STATE_REL = Path("research/kalshi/renders/ng_refine_s95/grp24_state.json")
_SLICE_ROOT_REL = Path("research/kalshi/renders/ng_refine_s95/g24_causal_slices")
_PROTECTED_REL = (
    Path("research/kalshi/spawn.py"),
    Path("research/kalshi/agents/mbo_refine_shared.md"),
    Path("research/kalshi/agents/mbo_specialist_A.md"),
    Path("research/kalshi/agents/mbo_specialist_B.md"),
    Path("research/kalshi/agents/mbo_specialist_C.md"),
    Path("research/kalshi/agents/mbo_specialist_D.md"),
    Path("research/kalshi/agents/mbo_specialist_E.md"),
)


class S127Stop(base.ForecastStop):
    pass


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args], cwd=str(ROOT), text=True, capture_output=True, check=False
        )
    except FileNotFoundError as exc:
        raise S127Stop("git is required to verify the sanctioned g24 artifact state") from exc


def verify_sanctioned_state() -> dict[str, Any]:
    """Fail closed unless the exact g24 artifacts/protected files still match 5d0354b."""
    days = list(gc.GROUPS[GID]["days"])
    artifact_paths = [_STATE_REL] + [_SLICE_ROOT_REL / f"state_{day}.json" for day in days]
    checked_paths = artifact_paths + list(_PROTECTED_REL)

    missing = [str(p) for p in checked_paths if not (ROOT / p).is_file()]
    if missing:
        raise S127Stop("sanctioned g24 preflight missing required file(s): " + ", ".join(missing))

    commit_probe = _git(["cat-file", "-e", f"{SANCTIONED_ARTIFACT_COMMIT}^{{commit}}"])
    if commit_probe.returncode != 0:
        detail = (commit_probe.stderr or commit_probe.stdout or "").strip()[-1000:]
        raise S127Stop(
            f"cannot resolve sanctioned artifact commit {SANCTIONED_ARTIFACT_COMMIT}: {detail}"
        )

    diff = _git(
        ["diff", "--quiet", SANCTIONED_ARTIFACT_COMMIT, "--", *[str(p) for p in checked_paths]]
    )
    if diff.returncode == 1:
        names = _git(
            ["diff", "--name-only", SANCTIONED_ARTIFACT_COMMIT, "--", *[str(p) for p in checked_paths]]
        )
        detail = (names.stdout or names.stderr or "unknown protected/artifact path").strip()
        raise S127Stop(
            "current g24 artifacts/protected files differ from sanctioned 5d0354b state: " + detail
        )
    if diff.returncode != 0:
        detail = (diff.stderr or diff.stdout or "").strip()[-1000:]
        raise S127Stop(f"git diff failed during sanctioned-state preflight: {detail}")

    return {
        "group": GID,
        "artifact_commit": SANCTIONED_ARTIFACT_COMMIT,
        "state": str(_STATE_REL),
        "causal_slices": len(days),
        "protected_files": len(_PROTECTED_REL),
        "verdict": "SANCTIONED_G24_STATE",
    }


def _g24_packet(
    template: str,
    gid: str,
    day: str,
    spec: str,
    namespace: str,
    *,
    bridge_deviation: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Use the current S126 packet unchanged except for correcting obsolete validation metadata."""
    if gid != GID:
        raise S127Stop(f"S127 launcher is g24-only; got {gid!r}")
    prompt, payload = s126.packet(
        template,
        gid,
        day,
        spec,
        namespace,
        bridge_deviation=bridge_deviation,
    )
    out = dict(payload)
    # This field came from the walked g17/g18 S118 harness. It is harness provenance, not a Frankie
    # data input or schema field. g24 is the sanctioned blind target, so leaving True would be false.
    out["walked_validation_only"] = False
    return prompt, out


def install() -> None:
    """Install the existing current stack, then scope only this process to sanctioned g24."""
    s121.install()
    base.ALLOWED_GROUPS = (GID,)
    base._packet = _g24_packet


def _assert_preflight(report: dict[str, Any]) -> None:
    days = report.get("days")
    if report.get("group") != GID or report.get("verdict") != "PACKETS_CAUSAL":
        raise S127Stop(f"unexpected g24 preflight report: {report}")
    if not isinstance(days, list) or len(days) != len(gc.GROUPS[GID]["days"]):
        raise S127Stop("g24 preflight did not build every configured day")
    bad_brain = [row for row in days if int(row.get("served_plays", -1)) != 90]
    if bad_brain:
        raise S127Stop(f"g24 preflight did not serve all 90 play bodies: {bad_brain}")
    if report.get("actuals_read") is not False:
        raise S127Stop("g24 preflight reported outcome access")


def preflight(namespace: str) -> dict[str, Any]:
    origin = verify_original_spawn()
    sanctioned = verify_sanctioned_state()
    install()
    report = base.preflight_group(GID, namespace)
    _assert_preflight(report)
    return {
        "origin": origin,
        "sanctioned": sanctioned,
        "packet_preflight": report,
        "backend_invoked": False,
        "actuals_read": False,
    }


def require_openai_runtime() -> dict[str, str]:
    """Require the already-sanctioned OpenAI model choice; never silently fall back to gpt-5."""
    model = os.environ.get("FRANKIE_OPENAI_MODEL", "").strip()
    if model != OPENAI_MODEL:
        raise S127Stop(
            f"FRANKIE_OPENAI_MODEL must be exactly {OPENAI_MODEL!r} for the S127 g24 run; "
            f"got {model or '<unset>'!r}"
        )
    return {"backend": "openai", "model": model}


def forecast(namespace: str, *, resume: bool = True) -> dict[str, Any]:
    structural = preflight(namespace)
    runtime = require_openai_runtime()
    run = base.run_group(GID, namespace, "openai", resume=resume)
    return {
        "preflight": structural,
        "runtime": runtime,
        "blind_run": run,
        "score_or_reveal_invoked": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=PHASES)
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    try:
        if args.phase == "preflight":
            result = preflight(args.namespace)
        else:
            result = forecast(args.namespace, resume=not args.no_resume)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"STOP - {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
