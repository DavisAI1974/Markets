#!/usr/bin/env python3
"""Run Frankie through the current NG five-specialist forecast path on walked groups.

S118 purpose:
- exercise the *current* S105+ machinery on a tiny validation set (default g17,g18);
- inherit the existing brain and canonical specialist doctrine;
- package point-in-time inputs for a tool-less model backend;
- write only to an isolated forecast namespace;
- keep realized actuals completely outside every forecast packet;
- score only after every requested forecast has been durably written.

This is a validation/paper-transition runner, not A-67 evidence. Walked groups are knowingly
contaminated as experimental test data; their actuals are never placed in model context.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RENDERS = HERE / "renders" / "ng_refine_s95"
FORECASTS = HERE / "forecasts"
PACKET_ROOT = HERE / "data" / "frankie_s118_packets"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import group_config as gc  # noqa: E402
import spawn  # noqa: E402
from frankie_backends import backend_from_name  # noqa: E402
from frankie_core import FrankieConfig  # noqa: E402

ALLOWED_GROUPS = ("g17", "g18")
ROLE_SHARED = HERE / "agents" / "mbo_refine_shared.md"
ROLE_SPEC = {x: HERE / "agents" / f"mbo_specialist_{x}.md" for x in "ABCDE"}

MODEL_INSTRUCTIONS = """You are Agent Frankie running one causal NG forecast step. The attached packet
is the complete allowed information set for this call. Never use knowledge outside the packet to
recover a realized answer for the target day. Never infer or request the actual tape. Follow the
canonical specialist doctrine and brain view supplied in the packet. Return ONLY the JSON object
requested by the OUTPUT contract in the emitted canonical prompt. Do not wrap it in markdown. Do
not claim execution authority. If an input is absent or defective, report it in the requested gap
field rather than inventing it."""


class ForecastStop(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ForecastStop(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ForecastStop(f"expected JSON object: {path}")
    return raw


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _emit_prompt(template: str, gid: str, *, day: str | None, spec: str | None,
                 namespace: str, allow_bridge_deviation: bool = False) -> str:
    class A:
        pass
    a = A()
    a.template = template
    a.gid = gid
    a.day = day
    a.spec = spec
    a.directive = None
    a.namespace = namespace
    a.no_bridge = allow_bridge_deviation
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = spawn.cmd_emit(a)
    text = buf.getvalue()
    if rc != 0:
        raise ForecastStop(f"spawn {template} {gid} {day or ''} failed:\n{text[:4000]}")
    return text


def _build_role_view(gid: str, day: str, namespace: str) -> Path:
    out = PACKET_ROOT / namespace / gid / f"brain_view_{day}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    state = RENDERS / f"grp{gid[1:]}_state.json"
    cmd = [
        sys.executable, str(HERE / "brain_view.py"), "--role", "specialist", "--gid", gid,
        "--state", str(state), "--day", day, "--out", str(out),
    ]
    done = subprocess.run(cmd, cwd=str(HERE), text=True, capture_output=True, check=False)
    if done.returncode != 0 or not out.is_file():
        raise ForecastStop(f"brain_view failed for {gid} {day}: {(done.stdout + done.stderr)[-4000:]}")
    return out


def _index_status(row: Any) -> str:
    if isinstance(row, Mapping):
        return json.dumps(row, sort_keys=True)
    return str(row)


def _compact_brain(view: dict[str, Any]) -> dict[str, Any]:
    """Keep orientation/index whole; attach only plays the arithmetic index says may matter today.

    The canonical view remains on disk and is hashed by the run manifest. This compact packet is a
    serving choice, not a brain rewrite. It errs toward inclusion: ARMED, PARTIALLY_EVALUABLE and
    EVALUABLE rows are included when the play body can be resolved by name.
    """
    out = {k: v for k, v in view.items() if k != "plays"}
    plays = view.get("plays") if isinstance(view.get("plays"), Mapping) else {}
    index = view.get("play_index")
    chosen: set[str] = set()
    if isinstance(index, Mapping):
        items = index.items()
    elif isinstance(index, list):
        items = []
        for row in index:
            if isinstance(row, Mapping):
                name = str(row.get("name") or row.get("id") or row.get("play") or "")
                if name:
                    items.append((name, row))
    else:
        items = []
    for name, row in items:
        status = _index_status(row).upper()
        if any(token in status for token in ("ARMED", "PARTIALLY_EVALUABLE", "EVALUABLE")):
            chosen.add(str(name))
    selected = {name: plays[name] for name in chosen if name in plays}
    out["plays"] = selected
    out["_frankie_serving"] = {
        "canonical_plays_total": len(plays),
        "selected_plays": sorted(selected),
        "rule": "index-selected serving only; canonical brain/view is unchanged",
    }
    return out


def _slice_path(gid: str, day: str) -> Path:
    return RENDERS / f"{gid}_causal_slices" / f"state_{day}.json"


def _packet(template: str, gid: str, day: str, spec: str, namespace: str,
            *, bridge_deviation: bool = False) -> tuple[str, dict[str, Any]]:
    prompt = _emit_prompt(template, gid, day=day, spec=spec, namespace=namespace,
                          allow_bridge_deviation=bridge_deviation)
    view_path = _build_role_view(gid, day, namespace)
    view = _compact_brain(_read_json(view_path))
    slice_path = _slice_path(gid, day)
    causal_slice = _read_json(slice_path)
    role_files = {
        "shared": ROLE_SHARED.read_text(encoding="utf-8"),
        "specialist": ROLE_SPEC[spec].read_text(encoding="utf-8"),
    }
    packet = {
        "packet_version": "s118.1",
        "group": gid,
        "day": day,
        "specialist": spec,
        "template": template,
        "walked_validation_only": True,
        "realized_outcome_in_packet": False,
        "canonical_prompt": prompt,
        "canonical_role_files": role_files,
        "causal_slice": causal_slice,
        "brain_view_served": view,
    }
    text = json.dumps(packet, sort_keys=True)
    forbidden = (f"{gid}_actual.json", f"{gid}_rt.json", "actual_day_move_usd", "actual_close")
    for token in forbidden:
        if token in text:
            raise ForecastStop(f"outcome leak token {token!r} entered packet for {gid} {day}")
    return prompt, packet


def _output_path_from_prompt(prompt: str, namespace: str, gid: str, spec: str, day: str,
                             template: str) -> Path:
    matches = re.findall(r"(?:OUTPUT\s*[—-]\s*write|write)\s+([A-Za-z0-9_./-]+\.json)", prompt, flags=re.I)
    for raw in matches:
        p = Path(raw.rstrip(".:"))
        if p.parts and p.parts[0] == "forecasts" and namespace in p.parts:
            return HERE / p
    # Deterministic fallback for BLD-1 only. Bridge templates must name their own output.
    if template == "BLD-1":
        return FORECASTS / namespace / f"grp{gid[1:]}_{spec}_{day}.json"
    raise ForecastStop(f"could not resolve namespace output path from {template} prompt for {gid} {day}")


def _validate_day(payload: Mapping[str, Any], gid: str, day: str, spec: str) -> None:
    if str(payload.get("specialist")) != spec:
        raise ForecastStop(f"{gid} {day}: specialist mismatch: {payload.get('specialist')!r}")
    if str(payload.get("group")) != gid:
        raise ForecastStop(f"{gid} {day}: group mismatch: {payload.get('group')!r}")
    got_day = str(payload.get("date", "")).replace("-", "")
    if got_day != day:
        raise ForecastStop(f"{gid} {day}: date mismatch: {payload.get('date')!r}")
    guess = payload.get("guessed_net_usd")
    if isinstance(guess, bool) or not isinstance(guess, (int, float)):
        raise ForecastStop(f"{gid} {day}: guessed_net_usd must be numeric")
    gap = payload.get("overnight_gap_usd")
    if isinstance(gap, bool) or not isinstance(gap, (int, float)):
        raise ForecastStop(f"{gid} {day}: overnight_gap_usd must be numeric")
    curve = payload.get("path_p50_curve")
    if not isinstance(curve, list) or len(curve) < 2:
        raise ForecastStop(f"{gid} {day}: path_p50_curve missing/too short")
    if payload.get("execution_enabled") is True or payload.get("execution_authority") is True:
        raise ForecastStop(f"{gid} {day}: forecast attempted to enable execution")


def _invoke(packet: dict[str, Any], backend_name: str) -> Mapping[str, Any]:
    config = FrankieConfig.from_env()
    backend = backend_from_name(backend_name, config)
    return backend.generate(instructions=MODEL_INSTRUCTIONS, prompt=json.dumps(packet, indent=2, sort_keys=True))


def _weekday(day: str) -> int:
    import datetime as dt
    return dt.date(int(day[:4]), int(day[4:6]), int(day[6:])).weekday()


def _prior_inblock_friday(days: list[str], day: str) -> str | None:
    if _weekday(day) != 0:
        return None
    i = days.index(day)
    if i <= 0:
        return None
    prev = days[i - 1]
    return prev if _weekday(prev) == 4 else None


def preflight_group(gid: str, namespace: str) -> dict[str, Any]:
    if gid not in ALLOWED_GROUPS:
        raise ForecastStop(f"S118 validation runner allows only {ALLOWED_GROUPS}; got {gid}")
    days = list(gc.GROUPS[gid]["days"])
    owners = gc.owner_map(gid)
    built = []
    for day in days:
        spec = owners[day]
        _, packet = _packet("BLD-1", gid, day, spec, namespace, bridge_deviation=True)
        built.append({
            "day": day,
            "owner": spec,
            "packet_bytes": len(json.dumps(packet)),
            "served_plays": len((packet["brain_view_served"].get("plays") or {})),
        })
    return {"group": gid, "days": built, "actuals_read": False, "verdict": "PACKETS_CAUSAL"}


def run_group(gid: str, namespace: str, backend_name: str, resume: bool = True) -> dict[str, Any]:
    if gid not in ALLOWED_GROUPS:
        raise ForecastStop(f"S118 validation runner allows only {ALLOWED_GROUPS}; got {gid}")
    g = gc.GROUPS[gid]
    days = list(g["days"])
    owners = gc.owner_map(gid)
    written: list[str] = []
    bridges: list[str] = []
    for day in days:
        spec = owners[day]
        fri = _prior_inblock_friday(days, day)
        if fri is not None:
            # Build A's weekend bridge immediately before B's Monday call. The canonical spawn gate
            # points at the historical namespace, so we explicitly declare that deviation while the
            # emitted prompt itself is redirected to this isolated namespace.
            bridge_prompt, bridge_packet = _packet(
                "BLD-2", gid, day, "A", namespace, bridge_deviation=True
            )
            bridge_path = _output_path_from_prompt(bridge_prompt, namespace, gid, "A", day, "BLD-2")
            if not (resume and bridge_path.is_file()):
                bridge_payload = _invoke(bridge_packet, backend_name)
                _atomic_json(bridge_path, bridge_payload)
            bridges.append(str(bridge_path.relative_to(HERE)))

        prompt, packet = _packet("BLD-1", gid, day, spec, namespace,
                                 bridge_deviation=(fri is not None))
        out = _output_path_from_prompt(prompt, namespace, gid, spec, day, "BLD-1")
        if resume and out.is_file():
            payload = _read_json(out)
        else:
            payload = dict(_invoke(packet, backend_name))
            _validate_day(payload, gid, day, spec)
            _atomic_json(out, payload)
        _validate_day(payload, gid, day, spec)
        written.append(str(out.relative_to(HERE)))
    return {"group": gid, "namespace": namespace, "forecasts": written, "bridges": bridges}


def _old_by_day(gid: str) -> dict[str, dict[str, Any]]:
    raw = _read_json(FORECASTS / f"grp{gid[1:]}.json")
    rows = raw.get("days")
    if not isinstance(rows, list):
        raise ForecastStop(f"old forecast {gid} has no days list")
    return {str(x["date"]).replace("-", ""): x for x in rows if isinstance(x, Mapping) and x.get("date")}


def _actual_by_day(gid: str) -> dict[str, dict[str, Any]]:
    # OUTCOME ACCESS STARTS HERE, after forecast generation is complete.
    raw = _read_json(RENDERS / f"{gid}_actual.json")
    rows = raw.get("days")
    if not isinstance(rows, list):
        raise ForecastStop(f"actual {gid} has no days list")
    return {str(x["date"]).replace("-", ""): x for x in rows if isinstance(x, Mapping) and x.get("date")}


def score_group(gid: str, namespace: str) -> dict[str, Any]:
    days = list(gc.GROUPS[gid]["days"])
    owners = gc.owner_map(gid)
    actual = _actual_by_day(gid)
    old = _old_by_day(gid)
    rows = []
    prior_actual = 0.0
    same_dow: dict[int, float] = {}
    for day in days:
        spec = owners[day]
        p = _read_json(FORECASTS / namespace / f"grp{gid[1:]}_{spec}_{day}.json")
        arow = actual.get(day)
        if not arow:
            raise ForecastStop(f"{gid} {day}: actual missing")
        aval = arow.get("day_move_usd")
        if aval is None:
            aval = float(arow.get("net_usd", 0) or 0) + float(arow.get("gap_usd", 0) or 0)
        aval = float(aval)
        new_guess = float(p["guessed_net_usd"])
        oldrow = old.get(day) or {}
        old_guess = oldrow.get("guess_day_move_usd")
        if old_guess is None:
            old_guess = oldrow.get("guessed_net_usd", 0)
        old_guess = float(old_guess or 0)
        wd = _weekday(day)
        seasonal = same_dow.get(wd, 0.0)
        rows.append({
            "event_id": f"{gid}:{day}",
            "day": day,
            "owner": spec,
            "actual": aval,
            "old_blind": old_guess,
            "frankie": new_guess,
            "old_abs_error": abs(old_guess - aval),
            "frankie_abs_error": abs(new_guess - aval),
            "error_delta_frankie_minus_old": abs(new_guess - aval) - abs(old_guess - aval),
            "zero_change_abs_error": abs(aval),
            "persistence_abs_error": abs(prior_actual - aval),
            "seasonal_naive_abs_error": abs(seasonal - aval),
            "old_direction_ok": (old_guess > 0) == (aval > 0) if aval != 0 else old_guess == 0,
            "frankie_direction_ok": (new_guess > 0) == (aval > 0) if aval != 0 else new_guess == 0,
        })
        prior_actual = aval
        same_dow[wd] = aval
    report = {
        "schema_version": "1.0",
        "kind": "S118_WALKED_TWO_GROUP_VALIDATION",
        "group": gid,
        "namespace": namespace,
        "warning": "walked validation data; not A-67 evidence",
        "pooled_scalar": None,
        "events": rows,
        "counts": {
            "n": len(rows),
            "frankie_better_error": sum(r["frankie_abs_error"] < r["old_abs_error"] for r in rows),
            "frankie_worse_error": sum(r["frankie_abs_error"] > r["old_abs_error"] for r in rows),
            "frankie_dir_hits": sum(bool(r["frankie_direction_ok"]) for r in rows),
            "old_dir_hits": sum(bool(r["old_direction_ok"]) for r in rows),
        },
    }
    out = RENDERS / f"{gid}_{namespace}_comparison.json"
    _atomic_json(out, report)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("groups", nargs="*", default=list(ALLOWED_GROUPS))
    ap.add_argument("--namespace", default="frankie_s118_b")
    ap.add_argument("--backend", choices=("openai", "bedrock"), default="openai")
    ap.add_argument("--preflight", action="store_true", help="build/validate causal packets; no model and no actuals")
    ap.add_argument("--score-only", action="store_true")
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args()
    try:
        if args.preflight:
            result = [preflight_group(g, args.namespace) for g in args.groups]
        elif args.score_only:
            result = [score_group(g, args.namespace) for g in args.groups]
        else:
            result = []
            for g in args.groups:
                run = run_group(g, args.namespace, args.backend, resume=not args.no_resume)
                score = score_group(g, args.namespace)
                result.append({"run": run, "score": score})
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"STOP - {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
