#!/usr/bin/env python3
"""Thin S131 entrypoint for a corrected G3 mechanical re-blind.

This runner restores only the BLIND input side of the canonical stage_group path after the shared S3
substrate has been restored by the workflow: scored-contract leg files plus prior n0/n1/L1 tape. It
never calls stage_group.stage(), group_actual, the scoring path, or any reveal/refine routine.

It then exposes the already-corrected in-memory S131 state to the standard canonical spawn slots:
  renders/ng_refine_s95/grp3_state.json
  renders/ng_refine_s95/g3_causal_slices/state_<DAY>.json
Those files exist only in the disposable GitHub Actions checkout; no canonical repo artifact is changed.

S131 is a CURRENT-FRANKIE improvement test, not a historical-brain reconstruction. The current brain
therefore keeps later learned evidence, including realized examples learned after Sep-2025. The blind
wall applies to the TARGET WINDOW only: Sep-08..Sep-19 2025 outcomes and G3 actual/reveal artifacts
remain forbidden. Canonical S120 is not changed; this narrower rule is installed only in this runner.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import frankie_g3_reblind_s131 as s131

_ORIGINAL_PACKET = s131._packet
_TARGET_DATES = frozenset(s131.DAYS)
_LEAK_FIELDS = ("actual_day_move_usd", "actual_close", "actual_net_usd", "actual_gap_usd")
_DATE8 = re.compile(r"20\d{6}")
_LEAK_CONTEXT = 500


def _assert_s131_target_window_only(text: str, gid: str, day: str) -> None:
    """Permit current-brain learned outcomes except the Sep-2025 target window itself.

    This deliberately differs from S120's pristine/walked-canary A-82 rule. S131 asks whether the
    CURRENT Frankie, with everything learned since, can reason better on an old market environment.
    Therefore a dated 2026 realized example is legitimate learned evidence. What remains illegal is
    the answer to the period being tested: G3 actual/reveal artifacts or an outcome field associated
    with any Sep-08..Sep-19 2025 target date.
    """
    scan = re.sub(r"do not open[^\n]+", "", text, flags=re.IGNORECASE)
    for artifact in (f"{gid}_actual.json", f"{gid}_rt.json"):
        if artifact in scan:
            raise s131.s120.ForecastStop(
                f"S131 target-window leak: forbidden artifact {artifact!r} entered {gid} {day} packet"
            )

    for field in _LEAK_FIELDS:
        start = 0
        while True:
            i = text.find(field, start)
            if i < 0:
                break
            start = i + len(field)
            ctx = text[max(0, i - _LEAK_CONTEXT): i + _LEAK_CONTEXT]
            bad = sorted(set(_DATE8.findall(ctx)) & _TARGET_DATES)
            if bad:
                raise s131.s120.ForecastStop(
                    f"S131 target-window leak: {field!r} in {gid} {day} packet is associated with "
                    f"tested target date(s) {bad}"
                )


def _stage_existing_blind_inputs() -> dict:
    """Reuse stage_group's existing S3 key/path contract without running its outcome-building half."""
    s131.install_g3_context()
    import stage_group as sg

    g = s131.gc.GROUPS[s131.GID]
    days = list(g["days"])
    anchor_day = g["anchor_date"]
    leg_days = [(s131.gc.leg_for(s131.GID, d), d) for d in days]
    first_leg = leg_days[0][0]
    leg_days = [(first_leg, anchor_day)] + leg_days

    report = {"leg": [], "prior_tape": [], "actuals_read": False}
    os.makedirs(sg.LEG_DIR, exist_ok=True)
    for store, day in leg_days:
        key = f"nymex/{store}/NG_{day}.dbn.zst"
        dest = os.path.join(sg.LEG_DIR, f"{store}_{day}.dbn.zst")
        status = sg._dl(key, dest)
        report["leg"].append({"store": store, "day": day, "status": status})

    tape_days = [anchor_day] + days[:-1]
    for store in ("nymex_cont_n0", "nymex_cont_n1", "ng_l1"):
        dest_dir = os.path.join(sg.REPO, "data", store)
        os.makedirs(dest_dir, exist_ok=True)
        for day in tape_days:
            key = f"nymex/{store}/NG_{day}.jsonl.gz"
            dest = os.path.join(dest_dir, f"NG_{day}.jsonl.gz")
            status = sg._dl(key, dest)
            report["prior_tape"].append({"store": store, "day": day, "status": status})

    return report


def _materialize_standard_slots(state) -> None:
    render = s131.HERE / "renders" / "ng_refine_s95"

    state_slot = render / "grp3_state.json"
    state_slot.parent.mkdir(parents=True, exist_ok=True)
    state_slot.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    check = json.loads(state_slot.read_text(encoding="utf-8"))
    build = check.get("_state_build") or {}
    if build.get("group") != s131.GID or build.get("mask_after") != s131.ANCHOR_DATE:
        raise s131.S131Stop(f"standard state slot lost corrected G3 boundary: {build}")

    slice_dir = render / "g3_causal_slices"
    slice_dir.mkdir(parents=True, exist_ok=True)
    for day in s131.DAYS:
        sl = s131.causal.slice_state(state, day)
        bad = s131.causal.audit(sl, day)
        if bad:
            raise s131.S131Stop(f"refuse to materialize noncausal standard slice {day}: {bad}")
        future = sorted(k for k in sl if k[:1].isdigit() and k > day)
        if future:
            raise s131.S131Stop(f"standard slice {day} contains future day blocks: {future}")
        p = slice_dir / f"state_{day}.json"
        p.write_text(json.dumps(sl, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        reread = json.loads(p.read_text(encoding="utf-8"))
        build2 = reread.get("_state_build") or {}
        if build2.get("group") != s131.GID or build2.get("mask_after") != s131.ANCHOR_DATE:
            raise s131.S131Stop(f"standard slice {day} lost corrected G3 boundary: {build2}")
        bad2 = s131.causal.audit(reread, day)
        if bad2:
            raise s131.S131Stop(f"standard slice {day} failed reread causal audit: {bad2}")


def _packet_with_standard_state_slot(state, **kwargs):
    _materialize_standard_slots(state)
    return _ORIGINAL_PACKET(state, **kwargs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--namespace", default=s131.DEFAULT_NAMESPACE)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    try:
        staging = _stage_existing_blind_inputs()
        (args.out / "g3_s131_input_stage_report.json").write_text(
            json.dumps(staging, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        s131.s120.assert_no_outcome_leak = _assert_s131_target_window_only
        s131._packet = _packet_with_standard_state_slot
        result = s131.export(args.out, args.namespace)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"STOP - {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
