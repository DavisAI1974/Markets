#!/usr/bin/env python3
"""Assemble the S132 G3 event-driven curve rehearsal without reading target outcomes.

This is NOT a new blind score.  The operator/model had already seen the S131 reveal before these
curve nodes were authored.  The purpose is narrower: prove and inspect the corrected curve-emission
contract while holding every original S131 forecast judgment fixed.

Allowed change: curve_nodes + the compatibility path_p50_curve projection.
Forbidden change: owner, day net, gap, disposition, confidence, reasoning, plays, or state-gap report.
No actual, scored tape, scorecard, reveal artifact, brain edit, hydration or model API is read here.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import frankie_s132_dynamic_curve as s132

HERE = Path(__file__).resolve().parent
FORECASTS = HERE / "forecasts"
SRC = FORECASTS / "frankie_g3_s131_corrected_reblind"
DST = FORECASTS / "frankie_g3_s132_dynamic_curve_rehearsal"
NODE_FILE = DST / "g3_s132_curve_nodes.json"
ET = ZoneInfo("America/New_York")
ANCHOR_CLOSE = 3.026
MULT = 10000.0
DAYS = [
    "20250908", "20250909", "20250910", "20250911", "20250912",
    "20250915", "20250916", "20250917", "20250918", "20250919",
]
OWNERS = {
    "20250908": "B", "20250909": "C", "20250910": "C", "20250911": "D",
    "20250912": "E", "20250915": "B", "20250916": "C", "20250917": "C",
    "20250918": "D", "20250919": "E",
}
SOURCE_FILE = {
    day: SRC / f"grp3_{OWNERS[day]}_{day}.json"
    for day in DAYS
}
IMMUTABLE_FIELDS = (
    "specialist", "group", "date", "guessed_net_usd", "overnight_gap_usd",
    "reasoning", "plays_fired", "plays_stood_down", "confidence",
    "state_defects_and_gaps_reported", "disposition",
)
FORBIDDEN_KEYS = {
    "actual_day_move_usd", "actual_close", "actual_net_usd", "actual_gap_usd",
    "actual_price", "direction_hit", "endpoint_error_usd", "score", "scorecard",
}


class RehearsalStop(RuntimeError):
    pass


def _read(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RehearsalStop(f"cannot read {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise RehearsalStop(f"expected object: {path}")
    return obj


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _scan_forbidden(obj: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k) in FORBIDDEN_KEYS:
                hits.append(f"{path}.{k}")
            hits.extend(_scan_forbidden(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(_scan_forbidden(v, f"{path}[{i}]"))
    return hits


def _timestamps(day: str, nodes: list[dict[str, Any]]) -> list[str]:
    base = dt.datetime(int(day[:4]), int(day[4:6]), int(day[6:]), tzinfo=ET)
    hs = [float(n["et_hour"]) for n in nodes]
    # Chronology has already been validated by S132.  Convert the same one-wrap session axis to dates.
    off = -1 if hs and hs[0] >= 18.0 else 0
    wrapped = off == 0
    prev: float | None = None
    out: list[str] = []
    for h in hs:
        if prev is not None and h < prev:
            if wrapped:
                raise RehearsalStop(f"{day}: second/backward midnight wrap")
            off += 1
            wrapped = True
        out.append((base + dt.timedelta(days=off, hours=h)).isoformat())
        prev = h
    return out


def _same(a: Any, b: Any) -> bool:
    return json.dumps(a, sort_keys=True, separators=(",", ":")) == json.dumps(
        b, sort_keys=True, separators=(",", ":")
    )


def assemble(out_dir: Path) -> dict[str, Any]:
    spec = _read(NODE_FILE)
    if spec.get("classification") != "POST_REVEAL_CURVE_CONTRACT_REHEARSAL_NOT_BLIND_SCORE":
        raise RehearsalStop("curve-node artifact lost its post-reveal classification")
    if spec.get("operator_had_prior_target_reveal_context") is not True:
        raise RehearsalStop("rehearsal must acknowledge prior reveal context")
    if spec.get("assembler_actuals_read") is not False:
        raise RehearsalStop("node artifact does not certify actual-free assembly")

    s132_days = spec.get("days")
    if not isinstance(s132_days, dict) or sorted(s132_days) != sorted(DAYS):
        raise RehearsalStop("curve-node day coverage mismatch")

    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    full_curve: list[dict[str, Any]] = []
    running_usd = 0.0

    for day in DAYS:
        owner = OWNERS[day]
        source_path = SOURCE_FILE[day]
        src = _read(source_path)
        if _scan_forbidden(src):
            raise RehearsalStop(f"{day}: source S131 forecast unexpectedly contains reveal fields")

        node_rec = s132_days[day]
        if str(node_rec.get("owner")) != owner:
            raise RehearsalStop(f"{day}: S132 node owner mismatch")
        nodes = node_rec.get("curve_nodes")
        if not isinstance(nodes, list):
            raise RehearsalStop(f"{day}: curve_nodes missing")

        out = copy.deepcopy(src)
        out["curve_nodes"] = copy.deepcopy(nodes)
        out["path_p50_curve"] = [
            [n["et_hour"], n["p50_cum_usd"]]
            for n in nodes
        ]
        out["_s132_curve_rehearsal"] = {
            "classification": "POST_REVEAL_CURVE_CONTRACT_REHEARSAL_NOT_BLIND_SCORE",
            "operator_had_prior_target_reveal_context": True,
            "actuals_read_by_assembler": False,
            "source_s131_path": str(source_path.relative_to(HERE)),
            "source_s131_sha256": _sha(source_path),
            "only_curve_layer_changed": True,
            "fixed_clock": False,
            "fixed_point_count": False,
            "abstain_means_no_direction_authority_not_flat_market": True,
        }

        for key in IMMUTABLE_FIELDS:
            if not _same(src.get(key), out.get(key)):
                raise RehearsalStop(f"{day}: forbidden mutation of S131 field {key}")
        if _scan_forbidden(out):
            raise RehearsalStop(f"{day}: reveal field entered S132 output")

        try:
            s132.validate_day(out, "g3", day, owner)
        except Exception as exc:
            raise RehearsalStop(f"{day}: S132 dynamic curve validation failed: {exc}") from exc

        day_file = out_dir / f"grp3_{owner}_{day}.json"
        day_file.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        prior_close_cum = running_usd
        gap = float(out["overnight_gap_usd"])
        open_cum = prior_close_cum + gap
        stamps = _timestamps(day, nodes)
        for ts, node in zip(stamps, nodes):
            p25 = open_cum + float(node["p25_cum_usd"])
            p50 = open_cum + float(node["p50_cum_usd"])
            p75 = open_cum + float(node["p75_cum_usd"])
            full_curve.append({
                "date": day,
                "owner": owner,
                "timestamp_et": ts,
                "et_hour": node["et_hour"],
                "market_condition": node["market_condition"],
                "p25_cum_from_anchor_usd": p25,
                "p50_cum_from_anchor_usd": p50,
                "p75_cum_from_anchor_usd": p75,
                "price_p25": round(ANCHOR_CLOSE + p25 / MULT, 6),
                "price_p50": round(ANCHOR_CLOSE + p50 / MULT, 6),
                "price_p75": round(ANCHOR_CLOSE + p75 / MULT, 6),
            })

        running_usd += float(out["guessed_net_usd"])
        rows.append({
            "date": day,
            "owner": owner,
            "source_s131_sha256": _sha(source_path),
            "s132_output_sha256": _sha(day_file),
            "node_count": len(nodes),
            "guessed_net_usd": out["guessed_net_usd"],
            "overnight_gap_usd": out["overnight_gap_usd"],
            "disposition": out["disposition"],
            "confidence": out["confidence"],
            "immutable_forecast_judgment_verified": True,
        })

    if len(full_curve) == 120:
        raise RehearsalStop("S132 accidentally reproduced the old fixed 120-point cardinality")
    node_counts = [r["node_count"] for r in rows]
    if len(set(node_counts)) < 2:
        raise RehearsalStop("S132 node counts are suspiciously uniform; expected event-driven variation")

    result = {
        "artifact_version": "s132.g3.event-driven-curve-rehearsal.1",
        "group": "g3",
        "classification": "POST_REVEAL_CURVE_CONTRACT_REHEARSAL_NOT_BLIND_SCORE",
        "operator_had_prior_target_reveal_context": True,
        "actuals_read": False,
        "score_or_reveal_phase_present": False,
        "hydration": "REJECTED_NOT_USED",
        "brain_changed": False,
        "specialist_roles_changed": False,
        "direction_magnitude_reasoning_changed": False,
        "curve_contract_changed": True,
        "curve_rule": "Frankie-selected event nodes; no fixed clock/cadence/count; decimal ET allowed; each node carries market-condition rationale and P25/P50/P75 envelope",
        "abstain_rule": "no directional trading authority; full curve/range forecast still required",
        "source_curve_nodes": {
            "path": str(NODE_FILE.relative_to(HERE)),
            "sha256": _sha(NODE_FILE),
        },
        "days": rows,
        "node_counts": node_counts,
        "total_curve_nodes": len(full_curve),
        "terminal_cum_usd": running_usd,
        "terminal_price_p50": round(ANCHOR_CLOSE + running_usd / MULT, 6),
        "full_curve": full_curve,
        "use_rule": "Inspect contract behavior only. Do not compare this post-reveal re-emission as if it were a fresh blind forecast.",
    }
    (out_dir / "g3_s132_curve_rehearsal.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    try:
        d = assemble(args.out)
    except Exception as exc:
        print(f"STOP - {type(exc).__name__}: {exc}")
        return 2
    print(json.dumps({
        "status": "S132_CURVE_REHEARSAL_READY",
        "classification": d["classification"],
        "total_curve_nodes": d["total_curve_nodes"],
        "node_counts": d["node_counts"],
        "actuals_read": d["actuals_read"],
        "direction_magnitude_reasoning_changed": d["direction_magnitude_reasoning_changed"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
