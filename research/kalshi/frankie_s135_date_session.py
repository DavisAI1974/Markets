#!/usr/bin/env python3
"""Date-driven ChatGPT transport for the existing S135 CURRENT-FRANKIE state machine.

The persistent interface is dates/anchor/seam/legs, not a numbered group.  A synthetic runtime id is
injected only in this Python process because the existing S3/state/spawn machinery is keyed by a group
identifier.  Frankie, spawn.py, the brain, schema, roles, datapoint universe, and S135 runner are not
modified.

Historical rule: use the already-proven S131 boundary.  Stage only the existing input stores, build
current S128 decision state with explicit group+mask, keep absent historical families unavailable/null,
and prove those gaps to S135 preflight.  Never hydrate or synthesize them.

Transport rule: each invocation replays already-frozen ChatGPT outputs in order and emits exactly ONE
next model-facing request.  The target MBO provider is called only after that day's output exists and
has been SHA-frozen/validated.  Therefore the exported packet never contains the target outcome.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import brain_view
import build_causal_slices as causal
import frankie_s128_contract_repairs as s128
import frankie_s135_current_runtime as runtime
import frankie_s135_group_runner as runner
import frankie_s135_preflight as preflight
import group_config as gc
import group_mbo_engine
import stage_group

RUNTIME_GID = "gdate"


def _csv(value: str) -> list[str]:
    return [x.strip().replace("-", "") for x in value.split(",") if x.strip()]


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _install_date_config(args) -> str:
    days = _csv(args.days)
    eia = _csv(args.eia)
    if not days:
        raise SystemExit("--days is empty")
    if days != sorted(days) or len(days) != len(set(days)):
        raise SystemExit("--days must be unique and chronological")
    seam = args.seam.replace("-", "") if args.seam else None
    gc.GROUPS[RUNTIME_GID] = {
        "window": f"{days[0]}..{days[-1]}",
        "days": days,
        "anchor": float(args.anchor),
        "anchor_date": args.anchor_date.replace("-", ""),
        "anchor_lasthr_dir": int(args.anchor_lasthr_dir),
        "mask_after": args.anchor_date.replace("-", ""),
        "seam": seam,
        "legs": ({"pre": args.pre_leg.lower(), "post": args.post_leg.lower()}
                 if seam else {"all": args.pre_leg.lower()}),
        "eia_thursdays": eia,
        "holidays": [],
        "basis": args.basis,
    }
    return RUNTIME_GID


def _anchor_context(gid: str) -> dict[str, Any]:
    g = gc.GROUPS[gid]
    d = g["anchor_date"]
    first_leg = gc.leg_for(gid, g["days"][0])
    last_dir = int(g.get("anchor_lasthr_dir") or 0)
    return {
        "date": d,
        "dow": gc._dow(d),
        "contract": first_leg.replace("ng_mbo_", "").upper(),
        "leg": first_leg,
        "close": float(g["anchor"]),
        "anchor_close": float(g["anchor"]),
        "last_hour_dir": last_dir,
        "last_hour_direction": "up" if last_dir > 0 else ("down" if last_dir < 0 else "flat"),
        "provenance": "declared completed-session starter anchor; strictly prior to target window",
    }


def _install_anchor_artifact(gid: str, anchor: dict[str, Any]) -> Path:
    p = HERE / "renders" / "ng_refine_s95" / f"{gid}_anchor.json"
    artifact = {
        "group": gid,
        "date": anchor["date"],
        "dow": anchor["dow"],
        "anchor_close": anchor["anchor_close"],
        "anchor_lasthr_dir": anchor["last_hour_dir"],
        "leg": anchor["leg"],
        "basis": gc.GROUPS[gid]["basis"],
        "is_holiday_session": False,
        "verification": {
            "status": "DECLARED_REPLAY_ANCHOR",
            "source": "completed session before date-driven blind window",
        },
        "last_hour": {
            "direction": anchor["last_hour_direction"],
            "derived_dir": anchor["last_hour_dir"],
        },
        "session_activity": None,
    }
    _write(p, artifact)
    return p


def _stage_blind_inputs(gid: str) -> dict[str, Any]:
    """S131-style staging: existing leg files + strictly-prior n0/n1/L1; no actual/score build."""
    g = gc.GROUPS[gid]
    days = list(g["days"])
    anchor_day = g["anchor_date"]
    os.makedirs(stage_group.LEG_DIR, exist_ok=True)
    leg_days = [(gc.leg_for(gid, d), d) for d in days]
    leg_days = [(leg_days[0][0], anchor_day)] + leg_days
    report: dict[str, Any] = {
        "group_runtime_id": gid,
        "hydration": "REJECTED_NOT_USED",
        "actuals_built": False,
        "legs": [],
        "prior_tape": [],
    }
    for store, day in leg_days:
        key = f"nymex/{store}/NG_{day}.dbn.zst"
        dest = os.path.join(stage_group.LEG_DIR, f"{store}_{day}.dbn.zst")
        report["legs"].append({"store": store, "day": day, "status": stage_group._dl(key, dest)})

    tape_days = [anchor_day] + days[:-1]
    for store in ("nymex_cont_n0", "nymex_cont_n1", "ng_l1"):
        dest_dir = ROOT / "data" / store
        dest_dir.mkdir(parents=True, exist_ok=True)
        for day in tape_days:
            key = f"nymex/{store}/NG_{day}.jsonl.gz"
            dest = str(dest_dir / f"NG_{day}.jsonl.gz")
            report["prior_tape"].append(
                {"store": store, "day": day, "status": stage_group._dl(key, dest)}
            )
    return report


def _build_state(gid: str) -> tuple[dict[str, Any], Path]:
    g = gc.GROUPS[gid]
    state = s128.decision_state(g["days"], mask_after=g["mask_after"], group=gid)
    build = state.get("_state_build") or {}
    if build.get("group") != gid or build.get("mask_after") != g["mask_after"]:
        raise SystemExit(f"historical state boundary lost explicit group/mask: {build}")
    for day in g["days"]:
        row = state.get(day)
        if not isinstance(row, dict):
            raise SystemExit(f"state missing day {day}")
        scored = row.get("scored_leg")
        expected = gc.leg_for(gid, day)
        if not isinstance(scored, dict) or scored.get("group") != gid or scored.get("leg") != expected:
            raise SystemExit(f"{day}: scored-leg context {scored!r} != {expected!r}")
    state["_s135_date_historical_contract"] = {
        "runtime_group_id": gid,
        "days": list(g["days"]),
        "anchor_date": g["anchor_date"],
        "mask_after": g["mask_after"],
        "seam": g.get("seam"),
        "hydration": "REJECTED_NOT_USED",
        "missing_historical_families": "remain unavailable/null; never synthesized",
        "target_actuals_read_before_freeze": False,
    }
    p = HERE / "renders" / "ng_refine_s95" / "grpdate_state.json"
    _write(p, state)
    return state, p


def _write_slices(gid: str, state: dict[str, Any]) -> Path:
    out = HERE / "renders" / "ng_refine_s95" / f"{gid}_causal_slices"
    out.mkdir(parents=True, exist_ok=True)
    for day in gc.GROUPS[gid]["days"]:
        sl = causal.slice_state(state, day)
        bad = causal.audit(sl, day)
        if bad:
            raise SystemExit(f"causal slice violation {day}: {bad}")
        _write(out / f"state_{day}.json", sl)
    return out


def _archive_gap_proof(out: Path, gid: str, state: dict[str, Any]) -> Path:
    g = gc.GROUPS[gid]
    rows = []
    for day in g["days"]:
        row = state[day]
        absent = []
        for key, value in row.items():
            if value is None or value == {} or value == [] or value == "unknown":
                absent.append(key)
            elif isinstance(value, dict) and value.get("masked_one_shot") is True and value.get("value") is None:
                absent.append(key + "(masked/no historical value)")
        rows.append(f"{day}: {', '.join(sorted(absent)) if absent else 'none'}")
    p = out / "archive_gap_proof.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "S135 historical archive-gap proof for gdate.\n"
        "Policy: missing historical families remain unavailable/null. Hydration and synthesis are rejected.\n"
        f"Window: {g['days'][0]}..{g['days'][-1]}; anchor={g['anchor_date']}.\n" +
        "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    return p


def _install_inprocess_role_view(gid: str, state: dict[str, Any]) -> None:
    """Keep ephemeral date config visible to the brain-view builder without editing group_config.py."""
    def builder(request_gid: str, day: str, namespace: str) -> Path:
        if request_gid != gid:
            raise RuntimeError(f"date-session role builder got unexpected gid {request_gid}")
        brain = brain_view.load()
        view, _served, _withheld = brain_view.build(
            brain, "specialist", phase="working", window_days=gc.GROUPS[gid]["days"]
        )
        view = brain_view.annotate_evaluability(view, state[day])
        p = runtime.base.PACKET_ROOT / namespace / gid / f"brain_view_{day}.json"
        _write(p, view)
        return p
    runtime.base._build_role_view = builder


def _score(plan, frozen, actual):
    forecast_ex_gap = float(frozen["guessed_net_usd"]) - float(frozen["overnight_gap_usd"])
    realized = float(actual.get("net_usd") or 0.0)
    def sign(x):
        return 0 if abs(x) < 1e-9 else (1 if x > 0 else -1)
    return {
        "day": plan.day,
        "owner": plan.owner,
        "leg": plan.leg,
        "forecast_session_net_usd": forecast_ex_gap,
        "actual_session_net_usd": realized,
        "abs_error_usd": abs(forecast_ex_gap - realized),
        "direction_hit": sign(forecast_ex_gap) == sign(realized),
    }


def _request(out: Path, kind: str, plan, prompt: str, packet: dict, ledger) -> int:
    is_bridge = kind in {"weekend_bridge", "starter_weekend_bridge"}
    req = {
        "status": "MODEL_INPUT_REQUIRED",
        "kind": kind,
        "day": plan.day,
        "owner": "A" if is_bridge else plan.owner,
        "group_runtime_id": ledger.spec.group,
        "output_filename": (f"bridge_A_{plan.day}.json" if is_bridge
                            else f"forecast_{plan.owner}_{plan.day}.json"),
        "rule": "Use only packet.json. Return only the JSON requested by its canonical prompt.",
    }
    _write(out / "request.json", req)
    _write(out / "packet.json", packet)
    (out / "prompt.txt").write_text(prompt, encoding="utf-8")
    _write(out / "ledger.json", ledger.summary())
    print(json.dumps(req, sort_keys=True))
    return 0


def _is_friday(day: str) -> bool:
    return dt.date(int(day[:4]), int(day[4:6]), int(day[6:8])).weekday() == 4


def _is_monday(day: str) -> bool:
    return dt.date(int(day[:4]), int(day[4:6]), int(day[6:8])).weekday() == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", required=True)
    ap.add_argument("--anchor-date", required=True)
    ap.add_argument("--anchor", required=True, type=float)
    ap.add_argument("--anchor-lasthr-dir", default=0, type=int)
    ap.add_argument("--seam", default="")
    ap.add_argument("--pre-leg", required=True)
    ap.add_argument("--post-leg", default="")
    ap.add_argument("--eia", default="")
    ap.add_argument("--basis", default="date-driven S135 historical run")
    ap.add_argument("--namespace", default="frankie_s135_date_session")
    ap.add_argument("--outputs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    gid = _install_date_config(args)
    args.out.mkdir(parents=True, exist_ok=True)
    args.outputs.mkdir(parents=True, exist_ok=True)
    anchor = _anchor_context(gid)
    _install_anchor_artifact(gid, anchor)

    staging = _stage_blind_inputs(gid)
    _write(args.out / "input_stage_report.json", staging)
    state, state_path = _build_state(gid)
    _write_slices(gid, state)
    proof = _archive_gap_proof(args.out, gid, state)

    pf = preflight.build_preflight(
        group=gid,
        state=state_path,
        mask_after=gc.GROUPS[gid]["mask_after"],
        strict_health=False,
        archive_gap_proof=proof,
    )
    _write(args.out / "preflight.json", pf)
    if pf.get("run_gate") != "PASS":
        raise SystemExit(f"S135 run gate blocked: {pf.get('failed_checks')}")

    spec = runner.GroupRunSpec.from_group(gid, "BLIND", config_module=gc)
    runner._require_preflight_gate(spec, pf)
    runtime.install()
    _install_inprocess_role_view(gid, state)
    ledger = runner.SequentialReplayLedger(spec, initial_prior_session=anchor)

    for index, plan in enumerate(spec.days):
        prior = ledger.carry_for(plan.day)
        bridge = None

        # Block-opening Monday: completed Friday anchor -> A weekend bridge -> Monday B.
        if index == 0 and _is_friday(anchor["date"]) and _is_monday(plan.day):
            bp, bpacket = runtime.packet_sequential(
                "BLD-2", gid, plan.day, "A", args.namespace,
                prior_session=anchor,
                bridge_deviation=True,
                provenance="S135 completed Friday starter anchor",
            )
            bpath = args.outputs / f"bridge_A_{plan.day}.json"
            if not bpath.is_file():
                return _request(args.out, "starter_weekend_bridge", plan, bp, bpacket, ledger)
            bridge = _read(bpath)
            runtime.validate_owner_output(bridge, "A", task="weekend_bridge")

        # Normal in-window Friday E -> A bridge -> Monday B.
        elif index > 0:
            prev = spec.days[index - 1]
            if runner._is_friday_to_monday(prev.day, plan.day):
                if prior is None:
                    raise SystemExit("Friday carry missing at weekend bridge")
                bp, bpacket = runtime.packet_sequential(
                    "BLD-2", gid, plan.day, "A", args.namespace,
                    prior_session=prior,
                    bridge_deviation=True,
                    provenance="S135 frozen-then-revealed Friday completed session",
                )
                bpath = args.outputs / f"bridge_A_{plan.day}.json"
                if not bpath.is_file():
                    return _request(args.out, "weekend_bridge", plan, bp, bpacket, ledger)
                bridge = _read(bpath)
                runtime.validate_owner_output(bridge, "A", task="weekend_bridge")
                bridge = ledger.record_weekend_bridge(plan.day, bridge)

        if prior is None:
            prompt, packet = runtime.packet("BLD-1", gid, plan.day, plan.owner, args.namespace)
        else:
            prompt, packet = runtime.packet_sequential(
                "BLD-1", gid, plan.day, plan.owner, args.namespace,
                prior_session=prior,
                bridge_deviation=(bridge is not None),
                provenance="S135 completed strictly-prior session evidence",
            )
        if bridge is not None:
            packet = dict(packet)
            packet["s135_weekend_bridge_context"] = {
                "via_specialist": "A",
                "owns_monday_forecast": False,
                "monday_owner": plan.owner,
                "bridge": bridge,
            }
            runner._assert_packet_outcome_wall(runtime, packet, gid, plan.day)

        fpath = args.outputs / f"forecast_{plan.owner}_{plan.day}.json"
        if not fpath.is_file():
            return _request(args.out, "day_forecast", plan, prompt, packet, ledger)

        output = _read(fpath)
        ledger.freeze(
            plan.day,
            output,
            validator=lambda out, _owner, current=plan: runner._default_validate(runtime, out, gid, current),
        )
        # This is the legal reveal boundary: no call to per_day_evidence occurs before the SHA freeze.
        actual = group_mbo_engine.per_day_evidence(gid, plan.day)
        ledger.reveal(plan.day, actual)
        ledger.score_frozen(plan.day, _score)
        ledger.advance(plan.day)

    summary = ledger.summary()
    summary["status"] = "COMPLETE"
    summary["scores"] = dict(ledger._scores)  # all target forecasts are frozen before final exposure
    _write(args.out / "complete.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
