#!/usr/bin/env python3
"""Thin S131 entrypoint for a corrected G3 mechanical re-blind.

This runner restores only the BLIND input side of the canonical stage_group path after the shared S3
substrate has been restored by the workflow: scored-contract leg files plus prior n0/n1/L1 tape. It
never calls stage_group.stage(), group_actual, the scoring path, or any reveal/refine routine.

It then exposes the already-corrected in-memory S131 state to the standard canonical spawn slots:
  renders/ng_refine_s95/grp3_state.json
  renders/ng_refine_s95/g3_causal_slices/state_<DAY>.json
Those files exist only in the disposable GitHub Actions checkout; no canonical repo artifact is changed.

S131 is a CURRENT-FRANKIE improvement test, not a historical-brain reconstruction. The generalized
current brain/rules remain available, but DIRECT realized-outcome evidence dated on or after each
historical decision cutoff is visibly withheld before the packet reaches the unchanged S120 A-82 leak
guard. The guard itself is never weakened or replaced.

The runner also declares the Sep-2025 archive gaps proven by the read-only S3 inventory run
31911949696 (commit 89c21ce7): zero Sep-2025 objects exist in the relevant durable prefixes. Missing
families therefore remain unavailable/null; no hydration, synthesis, or realized-data substitution is
performed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import frankie_g3_reblind_s131 as s131

_ORIGINAL_PACKET = s131._packet
_ORIGINAL_BUILD_STATE = s131.build_state
_ORIGINAL_FULL_BRAIN = s131.s128.full_brain
_ACTIVE_CUTOFF: str | None = None
_OUT_DIR: Path | None = None

_DATE8 = re.compile(r"20\d{6}")
_DATE_SEP = re.compile(r"(20\d{2})[-/.](\d{2})[-/.](\d{2})")
_DATE_KEYS = frozenset(("date", "day", "target_date", "session_date", "evidence_date", "ymd"))
_DIRECT_LEAK_FIELDS = ("actual_day_move_usd", "actual_close", "actual_net_usd", "actual_gap_usd")
_POST_CUTOFF_MARKER = "[WITHHELD: post-cutoff direct outcome evidence]"

# Read-only S3 inventory: workflow run 31911949696, commit 89c21ce7ad4a1e0c8c423e9e9be26a68710f3ede.
# Every listed durable prefix had zero Sep-2025 date-keyed objects. This is declaration only; it does
# not change the state values produced by the current harness.
_ARCHIVE_ABSENT = {
    "weather_forecast": ["weather/mos_cycle/"],
    "weather_forecast_cycle": ["weather/mos_cycle/"],
    "freeze_risk": ["weather/mos_freeze/", "weather/mos_cycle/"],
    "weather_forcing_forecast": ["nymex/gefs_forcing/"],
    "model_disagreement": ["model_disagreement/"],
    "contract_structure": ["nymex/contract_structure/"],
    "options_surface": ["options_ng/", "options_ng_bridge/"],
    "squeeze_watch": ["nymex/contract_structure/", "options_ng/"],
    "curve_regime": ["nymex/nymex_curve/"],
}


def _extract_dates(value) -> set[str]:
    text = str(value)
    out = set(_DATE8.findall(text))
    out.update("".join(m.groups()) for m in _DATE_SEP.finditer(text))
    return out


def _is_direct_outcome_leaf(key: str, value) -> bool:
    k = str(key).lower()
    if k == "what_the_day_did" or k.startswith("actual_") or k.startswith("realized_"):
        return True
    if isinstance(value, str) and any(token in value for token in _DIRECT_LEAK_FIELDS):
        return True
    return False


def _redact_post_cutoff_outcomes(obj, cutoff: str, counter: list[int], in_future_record: bool = False):
    """Withhold direct outcome leaves inside records explicitly dated >= cutoff.

    This preserves the current brain's generalized rules, claims, health/falsifier logic and learned
    parameters. It removes only the realized-answer leaf of a later dated example. The replacement is
    explicit rather than a silent drop. A direct outcome string that carries its own future date is
    also withheld even when no sibling date field exists.
    """
    if isinstance(obj, dict):
        local_dates: set[str] = set()
        for key, value in obj.items():
            if str(key).lower() in _DATE_KEYS:
                local_dates.update(_extract_dates(value))
        future = in_future_record or any(day >= cutoff for day in local_dates)
        out = {}
        for key, value in obj.items():
            if future and _is_direct_outcome_leaf(str(key), value):
                out[key] = _POST_CUTOFF_MARKER
                counter[0] += 1
            else:
                out[key] = _redact_post_cutoff_outcomes(value, cutoff, counter, future)
        return out
    if isinstance(obj, list):
        return [_redact_post_cutoff_outcomes(value, cutoff, counter, in_future_record) for value in obj]
    if isinstance(obj, str):
        dates = _extract_dates(obj)
        if any(day >= cutoff for day in dates) and any(token in obj for token in _DIRECT_LEAK_FIELDS):
            counter[0] += 1
            return _POST_CUTOFF_MARKER
    return obj


def _full_brain_with_cutoff(view):
    if not _ACTIVE_CUTOFF:
        raise s131.S131Stop("S131 brain cutoff was not set before current-brain serving")
    full = _ORIGINAL_FULL_BRAIN(view)
    counter = [0]
    redacted = _redact_post_cutoff_outcomes(full, _ACTIVE_CUTOFF, counter)
    serving = redacted.get("_frankie_serving")
    if isinstance(serving, dict):
        serving["s131_historical_cutoff"] = _ACTIVE_CUTOFF
        serving["s131_post_cutoff_direct_outcomes_redacted"] = counter[0]
        serving["s131_redaction_rule"] = (
            "generalized current brain retained; direct realized-outcome leaves in records dated "
            "on/after this historical cutoff are visibly withheld; canonical S120 A-82 remains unchanged"
        )
    return redacted


def _coverage_report(state: dict) -> dict:
    days = list(s131.DAYS)

    def empty(value) -> bool:
        if value is None or value == {} or value == []:
            return True
        if isinstance(value, dict) and value.get("masked_one_shot") is True and value.get("value", "__absent__") is None:
            return True
        return False

    rows = {}
    for day in days:
        block = state.get(day) or {}
        rows[day] = {
            "top_level_blocks": len(block),
            "nonempty_top_level_blocks": sum(not empty(v) for v in block.values()),
            "archive_absent_blocks": [name for name in _ARCHIVE_ABSENT if empty(block.get(name)) or block.get(name) == "unknown"],
            "firehose_present": block.get("firehose_present"),
            "scored_leg": block.get("scored_leg"),
        }
    return {
        "group": s131.GID,
        "window": "2025-09-08..2025-09-19",
        "inventory_run_id": 31911949696,
        "inventory_commit": "89c21ce7ad4a1e0c8c423e9e9be26a68710f3ede",
        "inventory_result": "zero Sep-2025 date-keyed objects in every listed durable prefix",
        "archive_absent": _ARCHIVE_ABSENT,
        "rule": "missing archive families remain unavailable/null; no hydration, synthesis, or realized-data substitution",
        "days": rows,
    }


def _build_state_with_archive_contract() -> dict:
    state = _ORIGINAL_BUILD_STATE()
    state["_s131_archive_availability"] = {
        "verified_by": "read-only S3 inventory",
        "inventory_run_id": 31911949696,
        "inventory_commit": "89c21ce7ad4a1e0c8c423e9e9be26a68710f3ede",
        "sep2025_archive_absent": _ARCHIVE_ABSENT,
        "policy": "remain unavailable/null; never synthesize or hydrate",
    }
    if _OUT_DIR is not None:
        (_OUT_DIR / "g3_s131_state_coverage.json").write_text(
            json.dumps(_coverage_report(state), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return state


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
    global _ACTIVE_CUTOFF
    _materialize_standard_slots(state)
    cutoff = str(kwargs.get("decision_day") or kwargs.get("day") or "")
    if not re.fullmatch(r"20\d{6}", cutoff):
        raise s131.S131Stop(f"cannot establish historical cutoff for packet: {kwargs}")
    _ACTIVE_CUTOFF = cutoff
    try:
        return _ORIGINAL_PACKET(state, **kwargs)
    finally:
        _ACTIVE_CUTOFF = None


def main() -> int:
    global _OUT_DIR
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--namespace", default=s131.DEFAULT_NAMESPACE)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    _OUT_DIR = args.out

    try:
        staging = _stage_existing_blind_inputs()
        (args.out / "g3_s131_input_stage_report.json").write_text(
            json.dumps(staging, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        # Preserve canonical S120 A-82 unchanged. Only the model-facing current brain view is filtered
        # for direct post-cutoff outcome leaves, and the filter is applied per packet cutoff.
        s131.build_state = _build_state_with_archive_contract
        s131.s128.full_brain = _full_brain_with_cutoff
        s131._packet = _packet_with_standard_state_slot
        result = s131.export(args.out, args.namespace)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"STOP - {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
