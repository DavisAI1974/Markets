#!/usr/bin/env python3
"""S127 packet exporter for ChatGPT-operated Frankie on sanctioned g24.

This is a thin operational seam over the existing S121/S126 Frankie stack. It does not change
Frankie's brain, schema, settings, causal inputs, specialist roles, or protected spawn.py. It does
NOT invoke Claude, Bedrock, or the OpenAI API.

Its jobs are deliberately narrow:
- pin the current g24 state/slices and protected role/spawn files to the sanctioned S126 commit;
- scope the legacy S118 orchestration machinery to g24 in-process without widening the old CLI;
- preserve S120 full-brain/A-82 guards, S121 curve validation, and S126 specialist parity;
- export lossless, tool-less BLIND packets for ChatGPT to reason over one isolated call at a time.

There is intentionally no score, reveal, refine, or model-backend phase here. Outcome access stays
separate until the complete blind g24 group is frozen.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_group_forecast_s118 as base  # noqa: E402
import frankie_s118_redo as s120  # noqa: E402
import frankie_s121_curve_restore as s121  # noqa: E402
import frankie_specialist_parity_s126 as s126  # noqa: E402
import group_config as gc  # noqa: E402
from frankie_core import verify_original_spawn  # noqa: E402
from frankie_packet_compact_s120 import (  # noqa: E402
    assert_frankie_invariants,
    compact_packet_json,
)

GID = "g24"
PHASES = ("preflight", "export")
DEFAULT_NAMESPACE = "frankie_g24_s127_chatgpt"
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


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_sanctioned_state() -> dict[str, Any]:
    """Fail closed unless g24 artifacts/protected files still match sanctioned 5d0354b."""
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
    """Use the current S126 packet unchanged except obsolete walked-validation metadata."""
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
    # This field is S118 harness provenance, not a Frankie input/schema field. g24 is the sanctioned
    # blind target, so retaining True would incorrectly label the packet as walked validation data.
    out["walked_validation_only"] = False
    out["operator_transport"] = "chatgpt-session-manual; no model API invoked by runner"
    return prompt, out


def _g24_bridge_packet(day_mon: str, day_fri: str, namespace: str) -> tuple[str, dict[str, Any]]:
    """Build A's weekend bridge at its canonical FRIDAY decision point.

    The legacy S118 run_group asks its generic packet builder for BLD-2 using the Monday target day.
    That generic builder also selects the Monday causal slice, even though the canonical BLD-2
    prompt explicitly says the bridge decision point is the Friday exit. S127 corrects only that
    runner seam: Monday remains the bridge target/output name, while brain evaluability and served
    causal state are both pinned to Friday.
    """
    prompt = base._emit_prompt(
        "BLD-2",
        GID,
        day=day_mon,
        spec="A",
        namespace=namespace,
        allow_bridge_deviation=True,
    )
    view_path = base._build_role_view(GID, day_fri, namespace)
    view = s120.full_brain(base._read_json(view_path))
    causal_slice = base._read_json(base._slice_path(GID, day_fri))
    payload = {
        "packet_version": "s127.chatgpt-bridge.1",
        "phase": "BLIND",
        "group": GID,
        "day": day_mon,
        "decision_day": day_fri,
        "specialist": "A",
        "template": "BLD-2",
        "walked_validation_only": False,
        "realized_outcome_in_packet": False,
        "canonical_prompt": prompt,
        "canonical_role_files": {
            "shared": base.ROLE_SHARED.read_text(encoding="utf-8"),
            "specialist": base.ROLE_SPEC["A"].read_text(encoding="utf-8"),
        },
        "causal_slice": causal_slice,
        "brain_view_served": view,
        "redo_guards": ["A-80/S120-full-brain", "A-82", "S127-Friday-bridge-cutoff"],
        "operator_transport": "chatgpt-session-manual; no model API invoked by runner",
    }
    s120.assert_no_outcome_leak(json.dumps(payload, sort_keys=True), GID, day_fri)
    return prompt, s126.attach_specialist_access(payload, specialist="A", phase="BLIND")


def install() -> None:
    """Install current Frankie guards, then scope only this process to sanctioned g24."""
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
        "model_backend_invoked": False,
        "actuals_read": False,
    }


def export_packets(namespace: str, out_dir: Path) -> dict[str, Any]:
    """Export lossless packets only; ChatGPT reasons over them outside this runner."""
    structural = preflight(namespace)
    install()
    out_dir.mkdir(parents=True, exist_ok=True)
    days = list(gc.GROUPS[GID]["days"])
    owners = gc.owner_map(GID)
    exported: list[dict[str, Any]] = []

    for day in days:
        fri = base._prior_inblock_friday(days, day)
        if fri is not None:
            _, bridge = _g24_bridge_packet(day, fri, namespace)
            compact = compact_packet_json(bridge)
            inv = assert_frankie_invariants(bridge, compact)
            path = out_dir / f"{GID}_BLD-2_A_{fri}_to_{day}.json"
            path.write_text(compact + "\n", encoding="utf-8")
            exported.append({
                "template": "BLD-2",
                "specialist": "A",
                "target_day": day,
                "decision_day": fri,
                "path": path.name,
                "bytes": len(compact.encode("utf-8")),
                "sha256": _sha256(compact),
                "invariants": inv,
            })

        spec = owners[day]
        _, packet = _g24_packet(
            "BLD-1", GID, day, spec, namespace, bridge_deviation=(fri is not None)
        )
        compact = compact_packet_json(packet)
        inv = assert_frankie_invariants(packet, compact)
        path = out_dir / f"{GID}_BLD-1_{spec}_{day}.json"
        path.write_text(compact + "\n", encoding="utf-8")
        exported.append({
            "template": "BLD-1",
            "specialist": spec,
            "target_day": day,
            "decision_day": day,
            "path": path.name,
            "bytes": len(compact.encode("utf-8")),
            "sha256": _sha256(compact),
            "invariants": inv,
        })

    manifest = {
        "group": GID,
        "namespace": namespace,
        "operator": "ChatGPT session",
        "model_api_invoked": False,
        "actuals_read": False,
        "sanctioned_artifact_commit": SANCTIONED_ARTIFACT_COMMIT,
        "packet_count": len(exported),
        "packets": exported,
        "structural_preflight": structural,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=PHASES)
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--out", type=Path, default=Path("/tmp/frankie_g24_s127_packets"))
    args = parser.parse_args()

    try:
        if args.phase == "preflight":
            result = preflight(args.namespace)
        else:
            result = export_packets(args.namespace, args.out)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"STOP - {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
