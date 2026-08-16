#!/usr/bin/env python3
"""Thin date-driven launcher for the existing S135 CURRENT-FRANKIE sequence.

This file does not change Frankie. It only supplies an ephemeral group_config entry from CLI dates,
stages the existing data path, replays already-frozen ChatGPT outputs, and emits exactly one next
model-facing request. Target evidence is never emitted before that day's forecast is frozen.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_causal_slices as causal
import frankie_s135_current_runtime as runtime
import frankie_s135_group_runner as runner
import frankie_s135_preflight as preflight
import group_config as gc
import group_mbo_engine
import stage_group


def _csv(value: str) -> list[str]:
    return [x.strip().replace("-", "") for x in value.split(",") if x.strip()]


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _install_date_config(args) -> str:
    days = _csv(args.days)
    eia = _csv(args.eia)
    if not days:
        raise SystemExit("--days is empty")
    gid = "gdate"  # ephemeral runtime id only; no numbered group file/config is required.
    gc.GROUPS[gid] = {
        "window": f"{days[0]}..{days[-1]}",
        "days": days,
        "anchor": float(args.anchor),
        "anchor_date": args.anchor_date.replace("-", ""),
        "anchor_lasthr_dir": int(args.anchor_lasthr_dir),
        "mask_after": args.anchor_date.replace("-", ""),
        "seam": args.seam.replace("-", "") if args.seam else None,
        "legs": {"pre": args.pre_leg.lower(), "post": args.post_leg.lower()} if args.seam
                else {"all": args.pre_leg.lower()},
        "eia_thursdays": eia,
        "holidays": [],
        "basis": args.basis,
    }
    return gid


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
    req = {
        "status": "MODEL_INPUT_REQUIRED",
        "kind": kind,
        "day": plan.day,
        "owner": "A" if kind == "weekend_bridge" else plan.owner,
        "group_runtime_id": ledger.spec.group,
        "output_filename": (f"bridge_A_{plan.day}.json" if kind == "weekend_bridge"
                            else f"forecast_{plan.owner}_{plan.day}.json"),
        "rule": "Return only the JSON requested by the canonical prompt. Do not use target outcomes outside packet.",
    }
    _write(out / "request.json", req)
    _write(out / "packet.json", packet)
    (out / "prompt.txt").write_text(prompt, encoding="utf-8")
    _write(out / "ledger.json", ledger.summary())
    print(json.dumps(req, sort_keys=True))
    return 0


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

    # Existing staging path. Actual/MBO artifacts may exist inside this isolated Actions checkout,
    # but only packet.json is exported to ChatGPT before freeze; S120/S135 outcome walls remain active.
    stage_group.stage(gid)
    state = HERE / "renders" / "ng_refine_s95" / "grpdate_state.json"
    slice_dir = HERE / "renders" / "ng_refine_s95" / f"{gid}_causal_slices"
    rc = causal.build(gid, True, str(slice_dir))
    if rc:
        raise SystemExit("causal slice build failed")

    pf = preflight.build_preflight(
        group=gid,
        state=state,
        mask_after=args.anchor_date.replace("-", ""),
        strict_health=True,
    )
    _write(args.out / "preflight.json", pf)
    if pf.get("run_gate") != "PASS":
        raise SystemExit(f"S135 run gate blocked: {pf.get('failed_checks')}")

    spec = runner.GroupRunSpec.from_group(gid, "BLIND", config_module=gc)
    runner._require_preflight_gate(spec, pf)
    runtime.install()
    ledger = runner.SequentialReplayLedger(spec)

    for index, plan in enumerate(spec.days):
        prior = ledger.carry_for(plan.day)
        bridge = None
        if index > 0:
            prev = spec.days[index - 1]
            if runner._is_friday_to_monday(prev.day, plan.day):
                if prior is None:
                    raise SystemExit("Friday carry missing at weekend bridge")
                bp, bpacket = runtime.packet_sequential(
                    "BLD-2", gid, plan.day, "A", args.namespace,
                    prior_session=prior,
                    provenance="S135 frozen-then-revealed Friday completed session",
                )
                bpath = args.outputs / f"bridge_A_{plan.day}.json"
                if not bpath.is_file():
                    return _request(args.out, "weekend_bridge", plan, bp, bpacket, ledger)
                bridge = _json(bpath)
                runtime.validate_owner_output(bridge, "A", task="weekend_bridge")
                bridge = ledger.record_weekend_bridge(plan.day, bridge)

        if prior is None:
            prompt, packet = runtime.packet("BLD-1", gid, plan.day, plan.owner, args.namespace)
        else:
            prompt, packet = runtime.packet_sequential(
                "BLD-1", gid, plan.day, plan.owner, args.namespace,
                prior_session=prior,
                provenance="S135 frozen-then-revealed completed prior-session evidence",
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

        output = _json(fpath)
        ledger.freeze(
            plan.day,
            output,
            validator=lambda out, _owner, current=plan: runner._default_validate(runtime, out, gid, current),
        )
        actual = group_mbo_engine.per_day_evidence(gid, plan.day)
        ledger.reveal(plan.day, actual)
        ledger.score_frozen(plan.day, _score)
        ledger.advance(plan.day)

    summary = ledger.summary()
    summary["status"] = "COMPLETE"
    _write(args.out / "complete.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
