#!/usr/bin/env python3
"""Apply the existing live dipole as a likelihood update to a locked blind prior.

This module does not create a parallel forecast. The blind ng.v2 direction probabilities
remain the scored prior. Once a nascent leg exists, the live coach may update that prior
with timestamped L1/MBO evidence. The posterior is stored separately and never written
back into the blind forecast artifact.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "ng_live_update.v1"
DIRECTIONS = ("up", "flat", "down")


def _normalize(probs: dict[str, Any]) -> dict[str, float]:
    values = {key: max(0.0, float(probs.get(key, 0.0) or 0.0)) for key in DIRECTIONS}
    total = sum(values.values())
    if total <= 0:
        return {key: 1.0 / 3.0 for key in DIRECTIONS}
    return {key: value / total for key, value in values.items()}


def _find_play(brain: dict[str, Any], play_id: str) -> dict[str, Any]:
    for play in brain.get("plays", []):
        if play.get("id") == play_id:
            return play
    raise KeyError(f"play not found: {play_id}")


def _smoothed_accuracy(play: dict[str, Any]) -> tuple[float, int, str]:
    evidence = play.get("evidence") or {}
    n = int(evidence.get("n_strong_oos") or evidence.get("n") or 0)
    raw_rate = evidence.get("rate_oos")
    if raw_rate is None:
        raw_rate = evidence.get("accuracy")
    if raw_rate is None or n <= 0:
        # No evidence means no update authority.
        return 0.5, 0, "no numeric OOS evidence; neutral likelihood"
    correct = max(0.0, min(float(n), float(raw_rate) * n))
    # Uniform Beta(1,1) shrinkage prevents a small perfect sample from becoming certainty.
    accuracy = (correct + 1.0) / (n + 2.0)
    return accuracy, n, "Beta(1,1)-smoothed from brain evidence"


def _likelihood_ratio(accuracy: float, cap: float) -> float:
    if not 0.5 < accuracy < 1.0:
        return 1.0
    return min(cap, accuracy / (1.0 - accuracy))


def apply_update(
    prior: dict[str, Any],
    dip_imb_level: float | None,
    brain: dict[str, Any],
    as_of_utc: str,
    source: str,
    horizon: str = "close",
    strong_threshold: float = 0.15,
    likelihood_cap: float = 10.0,
    data_quality_flags: list[str] | None = None,
) -> dict[str, Any]:
    prior_probs = _normalize(prior)
    play = _find_play(brain, "direction.flow_nowcast")
    accuracy, n, calibration_note = _smoothed_accuracy(play)
    lr = _likelihood_ratio(accuracy, likelihood_cap)
    flags = list(data_quality_flags or [])

    if dip_imb_level is None:
        posterior = prior_probs
        status = "NO_UPDATE_MISSING_DIPOLE"
        signal_side = None
        effective_lr = 1.0
        flags.append("dip_imb_level_missing")
    elif abs(float(dip_imb_level)) < strong_threshold:
        posterior = prior_probs
        status = "NO_UPDATE_WEAK_DIPOLE"
        signal_side = "up" if dip_imb_level > 0 else "down" if dip_imb_level < 0 else "flat"
        effective_lr = 1.0
    else:
        signal_side = "up" if dip_imb_level > 0 else "down"
        opposite = "down" if signal_side == "up" else "up"
        weights = dict(prior_probs)
        weights[signal_side] *= lr
        weights[opposite] /= lr
        # Flat remains possible but is softly reduced as strong directional evidence arrives.
        weights["flat"] /= math.sqrt(lr)
        posterior = _normalize(weights)
        status = "UPDATED"
        effective_lr = lr

    return {
        "schema": SCHEMA,
        "horizon": horizon,
        "as_of_utc": as_of_utc,
        "source": source,
        "authority": "live_likelihood_update_only",
        "execution_authority": False,
        "blind_prior": prior_probs,
        "evidence": {
            "play_id": play.get("id"),
            "play_status": play.get("status"),
            "play_scope": play.get("scope"),
            "dip_imb_level": dip_imb_level,
            "strong_threshold": strong_threshold,
            "signal_side": signal_side,
            "source_granularity": source,
            "oos_n": n,
            "smoothed_accuracy": round(accuracy, 8),
            "calibration_note": calibration_note,
            "likelihood_ratio": round(effective_lr, 8),
            "likelihood_cap": likelihood_cap,
        },
        "posterior": posterior,
        "status": status,
        "data_quality_flags": flags,
        "scoring_note": "blind scores use blind_prior only; posterior is scored separately as live-coach telemetry",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply live dipole evidence to a locked NG prior")
    parser.add_argument("--forecast", required=True, help="ng.v2 forecast JSON")
    parser.add_argument("--date", required=True, help="YYYYMMDD forecast day")
    parser.add_argument("--dip", type=float)
    parser.add_argument("--brain", default=str(Path(__file__).with_name("knowledge") / "ng_brain.json"))
    parser.add_argument("--source", choices=("L1", "MBO", "L1+MBO"), default="L1+MBO")
    parser.add_argument("--horizon", choices=("overnight", "us_open", "settle", "close"), default="close")
    parser.add_argument("--as-of-utc", default=dt.datetime.now(dt.timezone.utc).isoformat())
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    forecast = json.loads(Path(args.forecast).read_text(encoding="utf-8"))
    brain = json.loads(Path(args.brain).read_text(encoding="utf-8"))
    day = next((row for row in forecast.get("days", []) if row.get("date") == args.date), None)
    if day is None:
        raise SystemExit(f"date not found in forecast: {args.date}")
    prior = day["direction_probabilities"][args.horizon]
    result = apply_update(prior, args.dip, brain, args.as_of_utc, args.source, horizon=args.horizon)
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
