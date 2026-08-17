"""Immutable replay-proof gates for the isolated NG exhaustion runway clock V0.

This validator does not regenerate blind predictions. It checks the committed
pre-reveal freeze manifest against the frozen classifier/count/shard contract.
Post-reveal ordering remains validated by ng_exhaustion_runway_clock.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ng_exhaustion_runway_clock import (
    A_FAST_COLLAPSE,
    A_PERSISTENT,
    EXPECTED_CLASSIFIER_SHA256,
    EXPECTED_HELDOUT_A_COUNTS,
    EXPECTED_HELDOUT_DAYS,
    ReplayValidationError,
)

EXPECTED_BLIND_PREDICTION_N = 1711
EXPECTED_FREEZE_SHARD_SHA256 = {
    "20250717": "580198ef63cbec1ca6b7935cba5f57c8473b6c20bbc105ed0e861c7a04668806",
    "20250923": "43dee4e629627c50e14fefb72c560f5e5ecdd3ad0df03973acc9d9d8f6ee64a1",
    "20250930": "9b14348fd9519eac73f018ce48f7dd30f55fba4a013c327f8b53c71ee60bc855",
    "20251001": "e6aaf55e826cf47bbfb898425c29772c55caad06476a04c5d161c0cc4ebd6ac7",
}


def validate_blind_freeze_manifest(
    manifest_or_path: Mapping[str, Any] | str | Path,
) -> dict[str, Any]:
    """Fail closed if the committed pre-reveal freeze contract has drifted."""
    if isinstance(manifest_or_path, Mapping):
        manifest = dict(manifest_or_path)
    else:
        manifest = json.loads(Path(manifest_or_path).read_text(encoding="utf-8"))

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise ReplayValidationError(message)

    require(
        manifest.get("frozen_a_classifier_sha256") == EXPECTED_CLASSIFIER_SHA256,
        "blind-freeze classifier SHA drift",
    )
    require(
        manifest.get("a_post_state_counts")
        == {A_FAST_COLLAPSE: 831, A_PERSISTENT: 785}
        == EXPECTED_HELDOUT_A_COUNTS,
        "blind-freeze A state-count drift",
    )
    require(
        manifest.get("family_counts", {}).get("A") == 1616,
        "blind-freeze Family A count drift",
    )
    require(
        manifest.get("prediction_n") == EXPECTED_BLIND_PREDICTION_N,
        "blind-freeze prediction_n drift",
    )
    require(
        manifest.get("causal_t0_anchor_served") is True,
        "blind-freeze causal t0 anchor missing",
    )
    require(
        manifest.get("future_price_served_to_model") is False,
        "blind freeze exposed future price",
    )
    require(
        manifest.get("outcome_accessed_before_freeze") is False,
        "outcome was accessed before freeze",
    )
    require(
        manifest.get("single_best_curve_only") is True,
        "blind-freeze curve contract drift",
    )
    require(
        manifest.get("status") == "FROZEN_BLIND_PREDICTIONS_PENDING_REVEAL",
        "blind-freeze status drift",
    )

    shards = manifest.get("shards", {})
    require(isinstance(shards, Mapping) and len(shards) == 4, "blind-freeze shard count drift")

    seen_days: set[str] = set()
    shard_records = 0
    for shard_name, row in shards.items():
        require(isinstance(row, Mapping), f"invalid blind-freeze shard metadata for {shard_name}")
        day = str(row.get("day"))
        seen_days.add(day)
        require(day in EXPECTED_FREEZE_SHARD_SHA256, f"unexpected blind-freeze day {day}")
        require(
            row.get("sha256") == EXPECTED_FREEZE_SHARD_SHA256[day],
            f"blind-freeze shard SHA drift for {day}",
        )
        records = row.get("records")
        require(
            isinstance(records, int) and records > 0,
            f"invalid blind-freeze record count for {day}",
        )
        shard_records += records

    require(
        seen_days == set(EXPECTED_HELDOUT_DAYS),
        "blind-freeze held-out day set drift",
    )
    require(
        shard_records == EXPECTED_BLIND_PREDICTION_N,
        "blind-freeze shard-record total drift",
    )

    return {
        "status": "PASS",
        "classifier_sha256": EXPECTED_CLASSIFIER_SHA256,
        "heldout_a_counts": dict(EXPECTED_HELDOUT_A_COUNTS),
        "heldout_a_total": sum(EXPECTED_HELDOUT_A_COUNTS.values()),
        "prediction_n": EXPECTED_BLIND_PREDICTION_N,
        "shard_records": shard_records,
        "days": list(EXPECTED_HELDOUT_DAYS),
        "freeze_pre_reveal": True,
        "future_price_served_to_model": False,
        "outcome_accessed_before_freeze": False,
        "blind_experiment_rerun": False,
    }
