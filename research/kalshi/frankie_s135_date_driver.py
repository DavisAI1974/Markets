#!/usr/bin/env python3
"""Permanent thin driver for S135 date-window ChatGPT sessions.

The public run intent is only an inclusive start/end date pair. S136 resolves that pair against one
exact window already declared in group_config.py and fails before staging if the contract plan cannot
be proven there. No contract-month arithmetic or roll inference is allowed.

Historical learning runs receive current full Frankie.  The date layer withholds only evidence
attributable to the target session itself; it does not roll the brain back to the historical date.
The proven Friday E -> A handoff remains: E's frozen handoff_out is attached to the Monday A bridge
packet while A also receives completed Friday reality and may override E's forecast read.

Frankie, spawn.py, brain/schema, specialist roles, datapoint universe and the S135 state machine remain
unchanged.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import forecast_harness as fh
import frankie_s135_date_session as session
import frankie_s135_current_runtime as runtime
import frankie_s135_group_runner as runner
import frankie_s136_date_plan as date_plan
import frankie_s136_state_stage as state_stage
import frankie_s136_target_brain_wall as target_brain_wall
import group_config as gc

_OUTPUTS: Path | None = None
_DRIVER_OUT: Path | None = None
_RESOLVED_PLAN: dict | None = None
_ORIG_PACKET_SEQUENTIAL = runtime.packet_sequential
_ORIG_INSTALL_DATE_CONFIG = session._install_date_config
_ORIG_STAGE_BLIND_INPUTS = session._stage_blind_inputs
_ORIG_BUILD_STATE = session._build_state


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _attach_prior_session_plan(cfg: dict) -> dict:
    """Derive target -> previous actual session from the resolved declared session sequence."""
    out = dict(cfg)
    days = [str(x) for x in out.get("days", [])]
    anchor = str(out.get("anchor_date") or "")
    sequence = [anchor] + days
    if not anchor or not days:
        raise SystemExit("S136 prior-session proof requires an anchor and resolved session days")
    if sequence != sorted(sequence) or len(sequence) != len(set(sequence)):
        raise SystemExit(
            "S136 prior-session proof failed: anchor + resolved session sequence is not unique/chronological"
        )
    prior = {day: sequence[index] for index, day in enumerate(days)}
    for target, previous in prior.items():
        if previous >= target:
            raise SystemExit(
                f"S136 prior-session proof failed: {target} previous session {previous} is not prior"
            )
    out["prior_session_by_day"] = prior
    out["prior_session_proof"] = {
        "status": "RESOLVED_SEQUENCE_PENDING_ARCHIVE_PROOF",
        "source": "exact declared group_config session sequence + declared completed-session anchor",
        "rule": "target session -> immediately previous resolved trading session; never calendar D-1",
        "archive_requirement": "n0+n1+L1 prior tape and declared leg archive must stage or fail closed",
    }
    return out


def _install_resolved_date_config(args) -> str:
    """Preserve declared holiday ownership without changing the frozen S135 session implementation."""
    gid = _ORIG_INSTALL_DATE_CONFIG(args)
    if _RESOLVED_PLAN is None:
        raise RuntimeError("resolved date plan missing")
    gc.GROUPS[gid]["holidays"] = list(_RESOLVED_PLAN.get("holidays", []))
    return gid


def _stage_only_proven_contract_inputs(gid: str) -> dict:
    """Stage real canonical state, exact contract legs and required prior tape; fail closed."""
    if _RESOLVED_PLAN is None or _DRIVER_OUT is None:
        raise RuntimeError("S136 resolved plan/output missing before staging")

    manifest_path = _DRIVER_OUT / "state_stage_manifest.json"
    canonical = state_stage.stage_compact_state(
        str(_RESOLVED_PLAN["start_ymd"]), manifest_path
    )
    report = _ORIG_STAGE_BLIND_INPUTS(gid)

    missing_legs = [
        row for row in report.get("legs", [])
        if str(row.get("status")) not in {"ok", "skip"}
    ]
    if missing_legs:
        details = ", ".join(
            f"{row.get('store')}:{row.get('day')}={row.get('status')}" for row in missing_legs
        )
        raise SystemExit(
            "S136 contract archive proof failed; declared leg file(s) are unavailable: "
            f"{details}. Refusing to continue or infer a replacement contract."
        )

    missing_prior = [
        row for row in report.get("prior_tape", [])
        if str(row.get("status")) not in {"ok", "skip"}
    ]
    if missing_prior:
        details = ", ".join(
            f"{row.get('store')}:{row.get('day')}={row.get('status')}" for row in missing_prior
        )
        raise SystemExit(
            "S136 required prior n0/n1/L1 context is unavailable: "
            f"{details}. Refusing to continue or synthesize it."
        )

    prior_map = dict(_RESOLVED_PLAN.get("prior_session_by_day") or {})
    expected_prior_days = list(prior_map.values())
    if len(expected_prior_days) != len(set(expected_prior_days)):
        raise SystemExit("S136 prior-session archive proof failed: duplicate resolved prior sessions")
    for store in ("nymex_cont_n0", "nymex_cont_n1", "ng_l1"):
        staged_days = [
            str(row.get("day")) for row in report.get("prior_tape", [])
            if row.get("store") == store
        ]
        if staged_days != expected_prior_days:
            raise SystemExit(
                f"S136 prior-session archive proof failed for {store}: staged={staged_days} "
                f"expected={expected_prior_days}"
            )

    report["contract_archive_proof"] = "PASS_ALL_DECLARED_LEG_FILES_PRESENT"
    report["prior_context_proof"] = "PASS_ALL_REQUIRED_N0_N1_L1_PRESENT"
    report["prior_session_identity_proof"] = {
        "status": "PASS_EXACT_RESOLVED_PRIOR_SESSIONS_STAGED",
        "rule": "target session -> immediately previous resolved trading session; never calendar D-1",
        "by_target": prior_map,
        "required_stores": ["nymex_cont_n0", "nymex_cont_n1", "ng_l1"],
    }
    report["canonical_state_stage"] = {
        "manifest": str(manifest_path),
        "object_count": canonical["object_count"],
        "bucket": canonical["bucket"],
        "full_n0_restore": canonical["full_n0_restore"],
        "bounded_prior_n0": canonical["bounded_prior_n0"],
        "ngwu_policy": "RESTORE_REAL_CANONICAL_STORE_FROM_S3; missing fields remain None",
    }
    report["vol_regime"] = state_stage.rebuild_vol_regime()
    return report


def _build_state_with_proven_prior(gid: str):
    """Build state with exact resolved prior sessions; calendar D-1 fallback is forbidden here."""
    if _RESOLVED_PLAN is None:
        raise RuntimeError("S136 resolved plan missing before state build")
    prior_map = dict(_RESOLVED_PLAN.get("prior_session_by_day") or {})
    if set(prior_map) != set(gc.GROUPS[gid]["days"]):
        raise SystemExit("S136 prior-session map does not cover the resolved target session set exactly")

    original_tape_conditions = fh._tape_conditions_block

    def exact_prior_tape(iso: str):
        target = iso.replace("-", "")
        prior = prior_map.get(target)
        if prior is None:
            raise RuntimeError(
                f"S136 no proven prior-session identity for target {target}; refusing calendar fallback"
            )
        stats = fh._tape_day_stats(prior)
        if stats is None:
            raise RuntimeError(
                f"S136 proven prior session {prior} for target {target} has no readable tape; fail closed"
            )
        prior_date = dt.datetime.strptime(prior, "%Y%m%d").date()
        out = fh._tape_enrich(prior_date, prior, stats)
        out["prior_session_resolution"] = {
            "status": "PROVEN_RESOLVED_SESSION",
            "target_session": target,
            "prior_session": prior,
            "rule": "immediately previous resolved trading session; calendar D-1 lookup disabled",
        }
        return out

    fh._tape_conditions_block = exact_prior_tape
    try:
        state, state_path = _ORIG_BUILD_STATE(gid)
    finally:
        fh._tape_conditions_block = original_tape_conditions

    for target, prior in prior_map.items():
        tape = (state.get(target) or {}).get("tape_conditions") or {}
        expected_iso = dt.datetime.strptime(prior, "%Y%m%d").date().isoformat()
        if tape.get("asof_prior_session") != expected_iso or tape.get("session") != prior:
            raise SystemExit(
                f"S136 prior-session state proof failed for {target}: "
                f"served asof={tape.get('asof_prior_session')} session={tape.get('session')} "
                f"expected={expected_iso}/{prior}"
            )
    return state, state_path


def _install_target_only_role_view(gid: str, state: dict) -> None:
    """Serve current full brain with only the target session structurally walled."""
    if _RESOLVED_PLAN is None:
        raise RuntimeError("S136 resolved plan missing before role-view install")
    source_group = str(_RESOLVED_PLAN.get("resolved_group") or "")

    def builder(request_gid: str, day: str, namespace: str) -> Path:
        if request_gid != gid:
            raise RuntimeError(f"date-session role builder got unexpected gid {request_gid}")
        raw_brain = session.brain_view.load()
        view = target_brain_wall.build_role_view(
            raw_brain,
            target_day=day,
            source_group=source_group,
            state_day=state[day],
        )
        path = runtime.base.PACKET_ROOT / namespace / gid / f"brain_view_{day}.json"
        _write_json(path, view)
        return path

    runtime.base._build_role_view = builder


def _packet_sequential_with_friday_handoff(template, gid, day, spec, namespace, **kwargs):
    prompt, packet = _ORIG_PACKET_SEQUENTIAL(template, gid, day, spec, namespace, **kwargs)
    if template != "BLD-2" or spec != "A" or _OUTPUTS is None:
        return prompt, packet

    days = list(gc.GROUPS[gid]["days"])
    if day not in days:
        return prompt, packet
    index = days.index(day)
    if index <= 0:  # starter Friday anchor -> first Monday has no in-window E forecast.
        return prompt, packet

    friday = days[index - 1]
    owner = gc.owner_map(gid)[friday]
    if owner != "E":
        return prompt, packet
    path = _OUTPUTS / f"forecast_{owner}_{friday}.json"
    if not path.is_file():
        raise SystemExit(f"Friday owner forecast missing before A bridge: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    handoff = obj.get("handoff_out")
    if not isinstance(handoff, dict):
        raise SystemExit(f"Friday owner handoff_out missing before A bridge: {path}")

    packet = dict(packet)
    packet["s135_friday_owner_handoff"] = {
        "from_day": friday,
        "from_specialist": owner,
        "forecast_disposition": obj.get("disposition"),
        "handoff_out": handoff,
    }
    runner._assert_packet_outcome_wall(runtime, packet, gid, plan.day)
    return prompt, packet


def main() -> int:
    global _OUTPUTS, _DRIVER_OUT, _RESOLVED_PLAN

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--start-date")
    ap.add_argument("--end-date")
    args = ap.parse_args()

    raw = json.loads(args.config.read_text(encoding="utf-8"))
    start_date = args.start_date or raw.get("start_date")
    end_date = args.end_date or raw.get("end_date")
    if not start_date or not end_date:
        raise SystemExit(
            "date intent incomplete: provide both start_date and end_date in the config or CLI"
        )

    try:
        cfg = _attach_prior_session_plan(date_plan.resolve_date_plan(start_date, end_date))
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    args.out.mkdir(parents=True, exist_ok=True)
    _write_json(args.out / "resolved_date_plan.json", cfg)

    _RESOLVED_PLAN = cfg
    _DRIVER_OUT = args.out
    _OUTPUTS = Path(cfg["outputs"])
    session._install_date_config = _install_resolved_date_config
    session._stage_blind_inputs = _stage_only_proven_contract_inputs
    session._build_state = _build_state_with_proven_prior
    session._install_inprocess_role_view = _install_target_only_role_view
    target_brain_wall.install_date_run_leak_guard()
    runtime.packet_sequential = _packet_sequential_with_friday_handoff

    days = ",".join(str(x) for x in cfg["days"])
    eia = ",".join(str(x) for x in cfg.get("eia", []))
    argv = [
        "frankie_s135_date_session.py",
        "--days", days,
        "--anchor-date", str(cfg["anchor_date"]),
        "--anchor", str(cfg["anchor"]),
        "--anchor-lasthr-dir", str(cfg.get("anchor_lasthr_dir", 0)),
        "--pre-leg", str(cfg["pre_leg"]),
        "--eia", eia,
        "--basis", str(cfg.get("basis", "date-driven S135 historical run")),
        "--namespace", str(cfg["namespace"]),
        "--outputs", str(_OUTPUTS),
        "--out", str(args.out),
    ]
    if cfg.get("seam"):
        argv += ["--seam", str(cfg["seam"]), "--post-leg", str(cfg["post_leg"])]
    sys.argv = argv
    return session.main()


if __name__ == "__main__":
    raise SystemExit(main())
