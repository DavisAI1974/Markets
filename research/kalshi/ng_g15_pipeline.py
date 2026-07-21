#!/usr/bin/env python3
"""Causal G15 prepared-corpus replay and SHADOW refinement pipeline.

The pipeline never invents corpus availability or skill. It requires a verified
prepared index and READY manifest, builds the locked Friday anchor from explicit
normalized inputs, replays through NGLiveOperator/ng_rt_feature_state, applies the
SHADOW refiner, emits per-day telemetry and unscored lesson proposals, and proves
the committed blind forecast stayed byte-identical. Outcome scoring, refined
curves, continuous_rt renders, and G16 remain explicit downstream gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ng_g15_anchor import EVENT_ORDER, build_anchor, validate_anchor
from ng_historical_manifest import G15_DATES
from ng_historical_replay import merge_sorted_sources, read_jsonl
from ng_historical_replay_prepared import replay_prepared_index
from ng_rt_refiner import refine_stream, validate_refine_output

SCHEMA = "ng_g15_pipeline.v1"
AUDIT_SCHEMA = "ng_g15_daily_refine_audit.v1"
LESSON_SCHEMA = "ng_g15_lesson_proposals.v1"


class PipelineError(ValueError):
    """Raised when orchestration cannot remain causal and reproducible."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _anchor_rows(paths: Sequence[Path]) -> list[dict[str, Any]]:
    if not paths:
        raise PipelineError("at least one normalized Friday anchor source is required")
    rows = list(merge_sorted_sources([read_jsonl(path) for path in paths]))
    rows.sort(
        key=lambda row: (
            float(row["ts_event_s"]),
            EVENT_ORDER.get(str(row.get("event_type") or ""), 99),
            int(row.get("source_sequence") or 0),
            int(row.get("ingest_sequence") or 0),
        )
    )
    return rows


def _flatten_states(replay: Mapping[str, Any]) -> list[dict[str, Any]]:
    states = [
        dict(state)
        for stream in replay.get("streams") or []
        for state in stream.get("states") or []
    ]
    states.sort(
        key=lambda row: (
            float(row["as_of_event_s"]),
            int(row.get("sequence") or 0),
            str((row.get("instrument") or {}).get("raw_symbol") or ""),
        )
    )
    return states


def _posterior_delta(output: Mapping[str, Any]) -> float:
    prior = dict(output.get("blind_prior") or {})
    posterior = dict(output.get("posterior") or {})
    prior_direction = float(prior.get("up") or 0.0) - float(prior.get("down") or 0.0)
    post_direction = float(posterior.get("up") or 0.0) - float(posterior.get("down") or 0.0)
    return post_direction - prior_direction


def daily_audit(
    outputs: Iterable[Mapping[str, Any]],
    *,
    blind_forecast_sha256: str,
    anchor_fingerprint: str,
) -> dict[str, Any]:
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in outputs:
        output = dict(raw)
        validate_refine_output(output)
        day = str(output.get("session_day") or "")
        if day not in G15_DATES:
            raise PipelineError(f"non-G15 or missing session_day: {day!r}")
        by_day[day].append(output)

    missing = [day for day in G15_DATES if not by_day.get(day)]
    if missing:
        raise PipelineError("no completed state for: " + ", ".join(missing))

    rows: list[dict[str, Any]] = []
    for day in G15_DATES:
        day_outputs = sorted(
            by_day[day],
            key=lambda row: (float(row["as_of_event_s"]), int(row.get("sequence") or 0)),
        )
        statuses = Counter(str(row.get("status") or "UNKNOWN") for row in day_outputs)
        attribution_counts: Counter[str] = Counter()
        attribution_abs: dict[str, float] = defaultdict(float)
        stand_down: Counter[str] = Counter()
        flow_allowed = queue_allowed = 0
        max_shift = 0.0
        max_shift_time = None

        for output in day_outputs:
            availability = dict(output.get("availability") or {})
            flow_allowed += int(bool(availability.get("flow_update_allowed")))
            queue_allowed += int(bool(availability.get("queue_update_allowed")))
            for reason in availability.get("stand_down_reasons") or []:
                stand_down[str(reason)] += 1
            shift = abs(_posterior_delta(output))
            if shift >= max_shift:
                max_shift = shift
                max_shift_time = output.get("as_of_event_s")
            for item in output.get("attribution") or []:
                if not item.get("used"):
                    continue
                name = str(item.get("name") or "unknown")
                attribution_counts[name] += 1
                attribution_abs[name] += abs(float(item.get("contribution") or 0.0))

        strongest = sorted(
            [
                {
                    "name": name,
                    "used_count": attribution_counts[name],
                    "absolute_contribution_sum": round(attribution_abs[name], 8),
                }
                for name in attribution_counts
            ],
            key=lambda row: (
                -row["absolute_contribution_sum"],
                -row["used_count"],
                row["name"],
            ),
        )
        latest = day_outputs[-1]
        rows.append(
            {
                "date": day,
                "n_completed_states": len(day_outputs),
                "first_event_s": day_outputs[0]["as_of_event_s"],
                "last_event_s": latest["as_of_event_s"],
                "status_counts": dict(sorted(statuses.items())),
                "flow_allowed_states": flow_allowed,
                "queue_allowed_states": queue_allowed,
                "stand_down_reasons": dict(sorted(stand_down.items())),
                "max_abs_direction_posterior_shift": round(max_shift, 8),
                "max_shift_event_s": max_shift_time,
                "latest_posterior": latest.get("posterior"),
                "latest_output_fingerprint": latest.get("output_fingerprint"),
                "strongest_attribution": strongest[:3],
                "outcome_scored": False,
            }
        )

    audit = {
        "schema": AUDIT_SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": "REFINE_AUDIT_ONLY",
        "execution_authority": False,
        "blind_forecast_sha256": blind_forecast_sha256,
        "anchor_fingerprint": anchor_fingerprint,
        "n_days": len(rows),
        "days": rows,
        "note": (
            "Per-day causal telemetry only. No actual outcomes were used and no "
            "pooled accuracy claim is made."
        ),
    }
    audit["audit_fingerprint"] = _fingerprint(audit)
    return audit


def lesson_proposals(audit: Mapping[str, Any]) -> dict[str, Any]:
    support: dict[str, list[str]] = defaultdict(list)
    for day in audit.get("days") or []:
        for item in day.get("strongest_attribution") or []:
            name = str(item.get("name") or "")
            if name:
                support[name].append(str(day.get("date") or ""))

    mechanisms = {
        "signed_flow": (
            "Nascent signed flow may update direction after onset, subject to "
            "chronological outcome and held-out scoring."
        ),
        "far_side_recruitment": (
            "Far-side replenishment versus depletion may distinguish continuation "
            "from exhaustion when the MBO book is complete."
        ),
        "divergence_exhaustion": (
            "Flow/price divergence may identify continuation failure or reversal "
            "risk without changing the immutable blind prior."
        ),
    }
    proposals = []
    for name in sorted(support):
        days = sorted(set(support[name]))
        proposals.append(
            {
                "id": f"g15_mbo.{name}",
                "status": "UNSCORED_CANDIDATE",
                "authority": "LESSON_PROPOSAL_ONLY",
                "may_update_ng_brain": False,
                "mechanism": mechanisms.get(
                    name,
                    f"{name} showed material causal attribution in replay.",
                ),
                "supporting_g15_days": days,
                "counterexamples": [],
                "sample_size_days": len(days),
                "confidence": "UNSCORED",
                "scope": "G15 historical replay telemetry; no outcome claim",
                "required_validation": [
                    "score against G15 actual path without changing the proposal",
                    "chronological forward test on G16",
                    "untouched holdout beyond G16",
                    "forward-live SHADOW validation",
                ],
            }
        )

    result = {
        "schema": LESSON_SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": "LESSON_PROPOSAL_ONLY",
        "execution_authority": False,
        "may_update_ng_brain": False,
        "source_audit_fingerprint": audit.get("audit_fingerprint"),
        "proposals": proposals,
        "note": (
            "Unscored candidates only. Separate adjudication is required; this "
            "artifact cannot rewrite knowledge/ng_brain.json."
        ),
    }
    result["proposal_fingerprint"] = _fingerprint(result)
    return result


def run_pipeline(
    *,
    prepared_index: dict[str, Any],
    manifest: dict[str, Any],
    blind_prior: dict[str, Any],
    blind_forecast_path: Path,
    anchor_inputs: Sequence[Path],
) -> dict[str, Any]:
    if not blind_forecast_path.is_file():
        raise PipelineError(f"blind forecast does not exist: {blind_forecast_path}")
    blind_before = blind_forecast_path.read_bytes()
    blind_hash_before = _file_sha256(blind_forecast_path)

    anchor = build_anchor(_anchor_rows(anchor_inputs))
    validate_anchor(anchor)
    replay = replay_prepared_index(
        prepared_index,
        manifest=manifest,
        blind_prior=blind_prior,
        horizon="close",
    )
    states = _flatten_states(replay)
    if not states:
        raise PipelineError("prepared replay emitted no completed MBO states")
    stream = refine_stream(states, anchor)
    audit = daily_audit(
        stream.get("outputs") or [],
        blind_forecast_sha256=blind_hash_before,
        anchor_fingerprint=str(anchor["anchor_fingerprint"]),
    )
    lessons = lesson_proposals(audit)

    blind_after = blind_forecast_path.read_bytes()
    blind_hash_after = _file_sha256(blind_forecast_path)
    if blind_after != blind_before or blind_hash_after != blind_hash_before:
        raise PipelineError("blind forecast changed during pipeline execution")

    bundle = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 15,
        "authority": "HISTORICAL_REFINE_PIPELINE_ONLY",
        "execution_authority": False,
        "blind_forecast": {
            "path": str(blind_forecast_path),
            "sha256_before": blind_hash_before,
            "sha256_after": blind_hash_after,
            "byte_identical": True,
        },
        "anchor": anchor,
        "replay": replay,
        "refine_stream": stream,
        "daily_audit": audit,
        "lesson_proposals": lessons,
        "gates": {
            "actual_outcome_scoring_complete": False,
            "refined_curve_complete": False,
            "continuous_rt_renders_complete": False,
            "g16_authorized": False,
        },
        "next_required_artifacts": [
            "g15_mbo_refined forecast curve derived without actual outcomes",
            "g15_mbo_blind_score.json",
            "g15_mbo_refined_score.json",
            "g15_mbo_comparison.json",
            "g15_mbo_blind_continuous.png",
            "g15_mbo_refined_continuous.png",
        ],
        "note": (
            "Replay and posterior telemetry are causal and SHADOW. This pipeline "
            "does not claim data availability, skill, or render completion."
        ),
    }
    bundle["pipeline_fingerprint"] = _fingerprint(bundle)
    return bundle


def write_outputs(
    bundle: Mapping[str, Any],
    out_dir: Path,
    prefix: str = "g15_mbo",
) -> dict[str, str]:
    outputs = {
        "anchor": out_dir / f"{prefix}_anchor.json",
        "replay": out_dir / f"{prefix}_replay.json",
        "refine_stream": out_dir / f"{prefix}_refine_stream.json",
        "daily_audit": out_dir / f"{prefix}_daily_audit.json",
        "lesson_proposals": out_dir / f"{prefix}_lesson_proposals.json",
        "pipeline": out_dir / f"{prefix}_pipeline.json",
    }
    _atomic_json(outputs["anchor"], dict(bundle["anchor"]))
    _atomic_json(outputs["replay"], dict(bundle["replay"]))
    _atomic_json(outputs["refine_stream"], dict(bundle["refine_stream"]))
    _atomic_json(outputs["daily_audit"], dict(bundle["daily_audit"]))
    _atomic_json(outputs["lesson_proposals"], dict(bundle["lesson_proposals"]))
    _atomic_json(outputs["pipeline"], dict(bundle))
    return {name: str(path) for name, path in outputs.items()}


def _selftest_anchor_sources(root: Path) -> list[Path]:
    identity = {
        "schema": "ng_normalized_event.v1",
        "dataset": "GLBX.MDP3",
        "publisher_id": 1,
        "instrument_id": 1008,
        "raw_symbol": "NGJ26",
        "definition_date": "2026-03-01",
        "session_day": "20260313",
    }
    definition_path = root / "anchor_definition.jsonl"
    trades_path = root / "anchor_trades.jsonl"
    mbo_path = root / "anchor_mbo.jsonl"
    definition_path.write_text(
        json.dumps(
            {
                **identity,
                "event_type": "definition",
                "ts_event_s": 1.0,
                "source_sequence": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    trades = [
        {
            **identity,
            "event_type": "trade",
            "ts_event_s": float(sequence + 1),
            "source_sequence": sequence,
            "price": 3.0 + sequence * 0.001,
            "size": 2,
            "side": "B" if sequence >= 4 else "A",
        }
        for sequence in range(1, 7)
    ]
    trades_path.write_text(
        "".join(json.dumps(row) + "\n" for row in trades),
        encoding="utf-8",
    )
    mbo_path.write_text(
        json.dumps(
            {
                **identity,
                "event_type": "mbo",
                "ts_event_s": 7.0,
                "source_sequence": 1,
                "action": "A",
                "side": "B",
                "size": 10,
                "order_id": 1,
                "price": 3.005,
                "flags": 128,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return [definition_path, trades_path, mbo_path]


def selftest() -> int:
    from ng_historical_replay_prepared import _fixture

    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        manifest, index = _fixture(root)
        blind = root / "grp15.json"
        blind.write_text(
            json.dumps({"group": 15, "days": []}) + "\n",
            encoding="utf-8",
        )
        before = blind.read_bytes()
        bundle = run_pipeline(
            prepared_index=index,
            manifest=manifest,
            blind_prior={"up": 0.4, "flat": 0.2, "down": 0.4},
            blind_forecast_path=blind,
            anchor_inputs=_selftest_anchor_sources(root),
        )
        assert bundle["daily_audit"]["n_days"] == 12
        assert bundle["refine_stream"]["n_outputs"] == 12
        assert bundle["blind_forecast"]["byte_identical"] is True
        assert blind.read_bytes() == before
        assert bundle["lesson_proposals"]["may_update_ng_brain"] is False
    print("[ng_g15_pipeline] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run causal G15 prepared replay and SHADOW refinement"
    )
    parser.add_argument("--prepared-index", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--blind-prior", type=Path)
    parser.add_argument("--blind-forecast", type=Path)
    parser.add_argument("--anchor-input", type=Path, action="append")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--prefix", default="g15_mbo")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()

    required = {
        "--prepared-index": args.prepared_index,
        "--manifest": args.manifest,
        "--blind-prior": args.blind_prior,
        "--blind-forecast": args.blind_forecast,
        "--anchor-input": args.anchor_input,
        "--out-dir": args.out_dir,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        parser.error("required arguments missing: " + ", ".join(missing))

    bundle = run_pipeline(
        prepared_index=json.loads(
            args.prepared_index.read_text(encoding="utf-8")
        ),
        manifest=json.loads(args.manifest.read_text(encoding="utf-8")),
        blind_prior=json.loads(args.blind_prior.read_text(encoding="utf-8")),
        blind_forecast_path=args.blind_forecast,
        anchor_inputs=args.anchor_input,
    )
    paths = write_outputs(bundle, args.out_dir, args.prefix)
    print(
        json.dumps(
            {
                "pipeline_fingerprint": bundle["pipeline_fingerprint"],
                "blind_immutable": bundle["blind_forecast"]["byte_identical"],
                "completed_boundaries": bundle["replay"][
                    "completed_mbo_event_boundaries"
                ],
                "refine_outputs": bundle["refine_stream"]["n_outputs"],
                "days": bundle["daily_audit"]["n_days"],
                "outputs": paths,
                "gates": bundle["gates"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
