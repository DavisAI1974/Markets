"""Causal Level-I OFI and resiliency baselines for provisional Frankie research.

This module is evidence plumbing, not a V4 runner and not a promoted model.  It
does not authorize a run, choose a lock, update a live model, or establish
forward performance.

Paper/implementation boundary
-----------------------------
``compute_level1_ofi_events`` implements the best-bid/best-ask order-flow
imbalance equation associated with Cont, Kukanov, and Stoikov (2014).  Using
observable depletion followed by replenishment as a measurement target is
inspired by Large (2007).  The exact shock threshold, non-overlapping episode
state machine, refill threshold/horizon, censoring convention, data-quality
guards, lag-feature contract, deterministic logistic fitter, and matched
price/volume/static-imbalance controls are Frankie-added operational rules.
They are not claimed to reproduce either paper's estimator or empirical
results.

All forecast covariates produced here have source timestamps strictly before
the observable shock onset.  Refill observations at or after onset occur only
in label fields.  Model scaling and weights are fit from rows explicitly marked
``TRAIN`` and the exact fit inputs are fingerprinted.
"""
from __future__ import annotations

import dataclasses
import math
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from frankie_cognition import CognitiveContractError, sha256_json


IMPLEMENTATION_STATUS = "PROVISIONAL_BASELINE_NO_FORWARD_EVIDENCE"
MODEL_IDS = (
    "OFI",
    "PRICE_ONLY_CONTROL",
    "VOLUME_ONLY_CONTROL",
    "STATIC_IMBALANCE_CONTROL",
)
MODEL_FEATURES = {
    "OFI": "lag_side_aligned_ofi",
    "PRICE_ONLY_CONTROL": "lag_side_aligned_mid_change",
    "VOLUME_ONLY_CONTROL": "lag_trade_volume",
    "STATIC_IMBALANCE_CONTROL": "lag_side_aligned_static_imbalance",
}
FEATURE_NAMES = tuple(MODEL_FEATURES[model_id] for model_id in MODEL_IDS)
SHA256_RE = re.compile(r"[0-9a-f]{64}")

LINEAGE = {
    "level1_ofi": {
        "paper_inspiration": (
            "Cont, Kukanov, and Stoikov (2014): signed best-bid/best-ask "
            "queue-change OFI equation"
        ),
        "frankie_added": (
            "snapshot schema, timestamp/sequence/tick guards, deterministic "
            "receipts, and fixed-window lag aggregation"
        ),
    },
    "resiliency": {
        "paper_inspiration": (
            "Large (2007): measure order-book resiliency following liquidity depletion"
        ),
        "frankie_added": (
            "observable shock rule, non-overlapping side episodes, reference-queue "
            "refill fraction, horizon, censoring/non-replenishment labels, and scoring"
        ),
    },
    "matched_controls": {
        "paper_inspiration": "none; these are falsification and comparison controls",
        "frankie_added": (
            "same cases, labels, feature dimension, optimizer budget, train-only "
            "standardization, and price/volume/static-imbalance arms"
        ),
    },
}


@dataclass(frozen=True)
class BookGuardPolicy:
    """Fail-closed quality limits for observed Level-I snapshots."""

    max_book_age_seconds: float
    max_interarrival_seconds: float
    tick_size: float
    require_consecutive_sequence: bool = True

    def __post_init__(self) -> None:
        _positive(self.max_book_age_seconds, "max_book_age_seconds")
        _positive(self.max_interarrival_seconds, "max_interarrival_seconds")
        _positive(self.tick_size, "tick_size")
        if type(self.require_consecutive_sequence) is not bool:
            raise CognitiveContractError("require_consecutive_sequence must be boolean")


@dataclass(frozen=True)
class ResiliencyPolicy:
    """Frankie-added deterministic episode rules; not parameters from Large."""

    minimum_depletion_fraction: float
    refill_fraction_of_reference_depth: float
    refill_horizon_seconds: float

    def __post_init__(self) -> None:
        depletion = _probability(
            self.minimum_depletion_fraction, "minimum_depletion_fraction"
        )
        refill = _probability(
            self.refill_fraction_of_reference_depth,
            "refill_fraction_of_reference_depth",
        )
        if depletion <= 0.0:
            raise CognitiveContractError("minimum_depletion_fraction must be positive")
        if refill <= 0.0:
            raise CognitiveContractError(
                "refill_fraction_of_reference_depth must be positive"
            )
        _positive(self.refill_horizon_seconds, "refill_horizon_seconds")


@dataclass(frozen=True)
class FitPolicy:
    """One-feature logistic budget shared exactly by all four arms."""

    iterations: int = 400
    learning_rate: float = 0.05
    l2: float = 0.0

    def __post_init__(self) -> None:
        if type(self.iterations) is not int or self.iterations <= 0:
            raise CognitiveContractError("iterations must be a positive integer")
        _positive(self.learning_rate, "learning_rate")
        _nonnegative(self.l2, "l2")


def _identifier(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise CognitiveContractError(f"{field} must be a non-empty identifier")
    return result


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CognitiveContractError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise CognitiveContractError(f"{field} must be a finite number")
    return result


def _nonnegative(value: Any, field: str) -> float:
    result = _number(value, field)
    if result < 0.0:
        raise CognitiveContractError(f"{field} must be non-negative")
    return result


def _positive(value: Any, field: str) -> float:
    result = _number(value, field)
    if result <= 0.0:
        raise CognitiveContractError(f"{field} must be positive")
    return result


def _probability(value: Any, field: str) -> float:
    result = _number(value, field)
    if not 0.0 <= result <= 1.0:
        raise CognitiveContractError(f"{field} must be within [0, 1]")
    return result


def _timestamp(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise CognitiveContractError(
            f"{field} must be a finite epoch or timezone-aware ISO timestamp"
        )
    if isinstance(value, (int, float)):
        return _number(value, field)
    if not isinstance(value, str) or not value.strip():
        raise CognitiveContractError(
            f"{field} must be a finite epoch or timezone-aware ISO timestamp"
        )
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise CognitiveContractError(f"{field} is not a valid ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CognitiveContractError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc).timestamp()


def _on_tick(price: float, tick_size: float) -> bool:
    ticks = price / tick_size
    return math.isclose(ticks, round(ticks), rel_tol=0.0, abs_tol=1e-8)


def _receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    core = dict(payload)
    return {**core, "receipt_hash": sha256_json(core)}


def _validate_receipt(receipt: Mapping[str, Any]) -> None:
    claimed = str(receipt.get("receipt_hash", ""))
    if not SHA256_RE.fullmatch(claimed):
        raise CognitiveContractError("receipt_hash must be a lowercase SHA-256 value")
    core = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    if sha256_json(core) != claimed:
        raise CognitiveContractError("receipt_hash does not match receipt contents")


def _normalize_books(
    snapshots: Sequence[Mapping[str, Any]], guard: BookGuardPolicy
) -> list[dict[str, Any]]:
    if not snapshots:
        raise CognitiveContractError("Level-I processing requires snapshots")
    normalized: list[dict[str, Any]] = []
    prior_by_stream: dict[str, dict[str, Any]] = {}
    seen_ids: set[str] = set()
    for raw in snapshots:
        stream_id = _identifier(raw.get("stream_id"), "stream_id")
        sequence = raw.get("sequence")
        if type(sequence) is not int or sequence < 0:
            raise CognitiveContractError("sequence must be a non-negative integer")
        snapshot_id = _identifier(
            raw.get("snapshot_id", f"{stream_id}:{sequence}"), "snapshot_id"
        )
        if snapshot_id in seen_ids:
            raise CognitiveContractError(f"duplicate snapshot_id: {snapshot_id}")
        seen_ids.add(snapshot_id)
        observed = _timestamp(raw.get("observed_timestamp"), "observed_timestamp")
        book_timestamp = _timestamp(
            raw.get("book_timestamp", raw.get("observed_timestamp")), "book_timestamp"
        )
        if book_timestamp > observed:
            raise CognitiveContractError(f"snapshot {snapshot_id} has a future book timestamp")
        if observed - book_timestamp > guard.max_book_age_seconds:
            raise CognitiveContractError(f"snapshot {snapshot_id} is stale")
        bid_price = _positive(raw.get("bid_price"), "bid_price")
        ask_price = _positive(raw.get("ask_price"), "ask_price")
        bid_size = _positive(raw.get("bid_size"), "bid_size")
        ask_size = _positive(raw.get("ask_size"), "ask_size")
        trade_volume = _nonnegative(
            raw.get("trade_volume_since_previous", 0.0),
            "trade_volume_since_previous",
        )
        if bid_price >= ask_price:
            raise CognitiveContractError(f"snapshot {snapshot_id} is crossed or locked")
        if not _on_tick(bid_price, guard.tick_size) or not _on_tick(
            ask_price, guard.tick_size
        ):
            raise CognitiveContractError(f"snapshot {snapshot_id} contains an off-tick price")
        row = {
            "snapshot_id": snapshot_id,
            "stream_id": stream_id,
            "sequence": sequence,
            "observed_timestamp": observed,
            "book_timestamp": book_timestamp,
            "bid_price": bid_price,
            "bid_size": bid_size,
            "ask_price": ask_price,
            "ask_size": ask_size,
            "trade_volume_since_previous": trade_volume,
        }
        prior = prior_by_stream.get(stream_id)
        if prior is not None:
            if observed <= prior["observed_timestamp"]:
                raise CognitiveContractError(
                    f"stream {stream_id} timestamps must be strictly increasing"
                )
            if observed - prior["observed_timestamp"] > guard.max_interarrival_seconds:
                raise CognitiveContractError(
                    f"stream {stream_id} contains an unbridged feed gap"
                )
            if sequence <= prior["sequence"]:
                raise CognitiveContractError(
                    f"stream {stream_id} sequences must be strictly increasing"
                )
            if guard.require_consecutive_sequence and sequence != prior["sequence"] + 1:
                raise CognitiveContractError(
                    f"stream {stream_id} contains a sequence gap"
                )
        prior_by_stream[stream_id] = row
        normalized.append(row)
    counts: dict[str, int] = defaultdict(int)
    for row in normalized:
        counts[row["stream_id"]] += 1
    short = sorted(stream for stream, count in counts.items() if count < 2)
    if short:
        raise CognitiveContractError(
            "each Level-I stream requires at least two snapshots: " + ", ".join(short)
        )
    return normalized


def compute_level1_ofi_events(
    snapshots: Sequence[Mapping[str, Any]], guard: BookGuardPolicy
) -> dict[str, Any]:
    """Compute causal signed OFI from consecutive visible Level-I states.

    The returned event at time ``n`` uses only state ``n`` and state ``n-1``.
    No crossed/stale/gapped state is repaired or carried across a gap.
    """
    books = _normalize_books(snapshots, guard)
    prior_by_stream: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    for row in books:
        prior = prior_by_stream.get(row["stream_id"])
        prior_by_stream[row["stream_id"]] = row
        if prior is None:
            continue
        bid_contribution = (
            (row["bid_size"] if row["bid_price"] >= prior["bid_price"] else 0.0)
            - (prior["bid_size"] if row["bid_price"] <= prior["bid_price"] else 0.0)
        )
        ask_contribution = (
            -(row["ask_size"] if row["ask_price"] <= prior["ask_price"] else 0.0)
            + (prior["ask_size"] if row["ask_price"] >= prior["ask_price"] else 0.0)
        )
        ofi = bid_contribution + ask_contribution
        mid = (row["bid_price"] + row["ask_price"]) / 2.0
        prior_mid = (prior["bid_price"] + prior["ask_price"]) / 2.0
        event = {
            "event_id": f"OFI:{row['snapshot_id']}",
            "stream_id": row["stream_id"],
            "sequence": row["sequence"],
            "event_timestamp": row["observed_timestamp"],
            "source_snapshot_ids": [prior["snapshot_id"], row["snapshot_id"]],
            "source_max_timestamp": row["observed_timestamp"],
            "bid_contribution": bid_contribution,
            "ask_contribution": ask_contribution,
            "ofi": ofi,
            "ofi_sign": 1 if ofi > 0.0 else (-1 if ofi < 0.0 else 0),
            "mid_price": mid,
            "previous_mid_price": prior_mid,
            "mid_change": mid - prior_mid,
            "trade_volume": row["trade_volume_since_previous"],
            "static_imbalance": (
                (row["bid_size"] - row["ask_size"])
                / (row["bid_size"] + row["ask_size"])
            ),
        }
        event["event_hash"] = sha256_json(event)
        events.append(event)
    payload = {
        "implementation_status": IMPLEMENTATION_STATUS,
        "lineage": LINEAGE["level1_ofi"],
        "guard_policy": dataclasses.asdict(guard),
        "source_snapshot_count": len(books),
        "event_count": len(events),
        "source_snapshot_hash": sha256_json(books),
        "events": events,
    }
    return _receipt(payload)


def aggregate_causal_ofi_windows(
    ofi_receipt: Mapping[str, Any], *, trailing_window_seconds: float
) -> dict[str, Any]:
    """Aggregate each stream's events over a causal trailing time window.

    The row at event time ``t`` includes only same-stream events whose timestamps
    are in ``(t - window, t]``.  Counts by sign are kept alongside OFI magnitude
    so downstream code cannot silently substitute a trade-sign count for the
    Cont-style queue-change measure.
    """
    _validate_receipt(ofi_receipt)
    window = _positive(trailing_window_seconds, "trailing_window_seconds")
    events_by_stream: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for event in ofi_receipt.get("events", []):
        events_by_stream[_identifier(event.get("stream_id"), "stream_id")].append(event)
    aggregates: list[dict[str, Any]] = []
    for stream in sorted(events_by_stream):
        events = sorted(
            events_by_stream[stream],
            key=lambda row: (float(row["event_timestamp"]), int(row["sequence"])),
        )
        left = 0
        for right, event in enumerate(events):
            timestamp = _timestamp(event.get("event_timestamp"), "event_timestamp")
            while (
                left <= right
                and _timestamp(events[left].get("event_timestamp"), "event_timestamp")
                <= timestamp - window
            ):
                left += 1
            history = events[left : right + 1]
            values = [_number(row.get("ofi"), "ofi") for row in history]
            signs = [row.get("ofi_sign") for row in history]
            if any(type(sign) is not int or sign not in (-1, 0, 1) for sign in signs):
                raise CognitiveContractError("OFI event signs must be integers in {-1, 0, 1}")
            if any(
                (value > 0.0 and sign != 1)
                or (value < 0.0 and sign != -1)
                or (value == 0.0 and sign != 0)
                for value, sign in zip(values, signs)
            ):
                raise CognitiveContractError("OFI event sign contradicts OFI magnitude")
            row = {
                "aggregate_id": f"OFIWIN:{event['event_id']}:{window:g}",
                "stream_id": stream,
                "as_of_timestamp": timestamp,
                "source_max_timestamp": max(
                    _timestamp(item.get("source_max_timestamp"), "source_max_timestamp")
                    for item in history
                ),
                "source_event_ids": [str(item["event_id"]) for item in history],
                "event_count": len(history),
                "ofi_sum": sum(values),
                "ofi_mean": statistics.fmean(values),
                "sign_sum": sum(signs),
                "positive_event_count": sum(sign == 1 for sign in signs),
                "negative_event_count": sum(sign == -1 for sign in signs),
                "zero_event_count": sum(sign == 0 for sign in signs),
            }
            if row["source_max_timestamp"] > timestamp:
                raise CognitiveContractError("causal OFI window contains a future source")
            row["aggregate_hash"] = sha256_json(row)
            aggregates.append(row)
    payload = {
        "implementation_status": IMPLEMENTATION_STATUS,
        "lineage": LINEAGE["level1_ofi"],
        "trailing_window_seconds": window,
        "ofi_receipt_hash": ofi_receipt["receipt_hash"],
        "aggregate_count": len(aggregates),
        "aggregates": aggregates,
    }
    return _receipt(payload)


def _depletion_fraction(
    side: str, prior: Mapping[str, Any], current: Mapping[str, Any]
) -> float:
    price_key = f"{side.lower()}_price"
    size_key = f"{side.lower()}_size"
    old_price = float(prior[price_key])
    new_price = float(current[price_key])
    worsened = new_price < old_price if side == "BID" else new_price > old_price
    improved = new_price > old_price if side == "BID" else new_price < old_price
    if worsened:
        return 1.0
    if improved:
        return 0.0
    return max(0.0, (float(prior[size_key]) - float(current[size_key])) / float(prior[size_key]))


def _recovery_fraction(
    episode: Mapping[str, Any], current: Mapping[str, Any]
) -> float:
    side = str(episode["side"])
    price_key = f"{side.lower()}_price"
    size_key = f"{side.lower()}_size"
    reference_price = float(episode["reference_price"])
    current_price = float(current[price_key])
    price_recovered = (
        current_price >= reference_price if side == "BID" else current_price <= reference_price
    )
    if not price_recovered:
        return 0.0
    return float(current[size_key]) / float(episode["reference_depth"])


def label_depletion_resiliency_episodes(
    snapshots: Sequence[Mapping[str, Any]],
    guard: BookGuardPolicy,
    policy: ResiliencyPolicy,
) -> dict[str, Any]:
    """Create observable depletion episodes and future-only refill labels.

    A side cannot open another episode while its prior episode is unresolved.
    A resolved positive uses the first later observed book meeting the refill
    rule.  A negative is revealed only after an observed book reaches the fixed
    horizon without refill.  If observation ends earlier, the episode remains
    censored and has no binary label.
    """
    books = _normalize_books(snapshots, guard)
    prior_by_stream: dict[str, dict[str, Any]] = {}
    active: dict[tuple[str, str], dict[str, Any]] = {}
    episodes: list[dict[str, Any]] = []
    last_by_stream: dict[str, dict[str, Any]] = {}

    def close_episode(
        episode: dict[str, Any], *, status: str, reveal: float | None, current: Mapping[str, Any]
    ) -> None:
        result = dict(episode)
        result["status"] = status
        result["outcome_label"] = 1 if status == "REFILLED" else (0 if status == "NON_REPLENISHED" else None)
        result["label_reveal_timestamp"] = reveal
        result["refill_timestamp"] = reveal if status == "REFILLED" else None
        result["time_to_refill_seconds"] = (
            reveal - result["onset_timestamp"] if status == "REFILLED" and reveal is not None else None
        )
        result["observation_end_timestamp"] = current["observed_timestamp"]
        result["label_fields_hash"] = sha256_json(
            {
                "episode_id": result["episode_id"],
                "status": status,
                "outcome_label": result["outcome_label"],
                "label_reveal_timestamp": reveal,
                "refill_timestamp": result["refill_timestamp"],
                "time_to_refill_seconds": result["time_to_refill_seconds"],
                "half_recovery_seconds": result["half_recovery_seconds"],
            }
        )
        episodes.append(result)

    for current in books:
        stream = current["stream_id"]
        last_by_stream[stream] = current
        prior = prior_by_stream.get(stream)
        if prior is None:
            prior_by_stream[stream] = current
            continue

        for side in ("BID", "ASK"):
            key = (stream, side)
            episode = active.get(key)
            if episode is None:
                continue
            deadline = float(episode["deadline_timestamp"])
            if current["observed_timestamp"] > deadline:
                close_episode(
                    episode,
                    status="NON_REPLENISHED",
                    reveal=deadline,
                    current=current,
                )
                del active[key]
                continue
            recovery = _recovery_fraction(episode, current)
            if recovery >= 0.5 and episode["half_recovery_seconds"] is None:
                episode["half_recovery_seconds"] = (
                    current["observed_timestamp"] - episode["onset_timestamp"]
                )
            if recovery >= policy.refill_fraction_of_reference_depth:
                close_episode(
                    episode,
                    status="REFILLED",
                    reveal=current["observed_timestamp"],
                    current=current,
                )
                del active[key]
            elif current["observed_timestamp"] == deadline:
                close_episode(
                    episode,
                    status="NON_REPLENISHED",
                    reveal=deadline,
                    current=current,
                )
                del active[key]

        for side in ("BID", "ASK"):
            key = (stream, side)
            if key in active:
                continue
            depletion = _depletion_fraction(side, prior, current)
            if depletion < policy.minimum_depletion_fraction:
                continue
            price_key = f"{side.lower()}_price"
            size_key = f"{side.lower()}_size"
            onset = {
                "episode_id": f"DEP:{stream}:{side}:{current['sequence']}",
                "stream_id": stream,
                "side": side,
                "onset_sequence": current["sequence"],
                "onset_timestamp": current["observed_timestamp"],
                "deadline_timestamp": (
                    current["observed_timestamp"] + policy.refill_horizon_seconds
                ),
                "reference_price": prior[price_key],
                "reference_depth": prior[size_key],
                "onset_price": current[price_key],
                "onset_depth": current[size_key],
                "depletion_fraction": depletion,
                "half_recovery_seconds": None,
                "onset_source_snapshot_ids": [
                    prior["snapshot_id"],
                    current["snapshot_id"],
                ],
            }
            onset["onset_observation_hash"] = sha256_json(onset)
            active[key] = onset
        prior_by_stream[stream] = current

    for key in sorted(active):
        episode = active[key]
        last = last_by_stream[episode["stream_id"]]
        if last["observed_timestamp"] >= episode["deadline_timestamp"]:
            close_episode(
                episode,
                status="NON_REPLENISHED",
                reveal=episode["deadline_timestamp"],
                current=last,
            )
        else:
            close_episode(episode, status="CENSORED", reveal=None, current=last)

    episodes.sort(key=lambda row: (row["stream_id"], row["onset_timestamp"], row["side"]))
    payload = {
        "implementation_status": IMPLEMENTATION_STATUS,
        "lineage": LINEAGE["resiliency"],
        "guard_policy": dataclasses.asdict(guard),
        "resiliency_policy": dataclasses.asdict(policy),
        "source_snapshot_hash": sha256_json(books),
        "episode_count": len(episodes),
        "status_counts": {
            status: sum(row["status"] == status for row in episodes)
            for status in ("REFILLED", "NON_REPLENISHED", "CENSORED")
        },
        "episodes": episodes,
    }
    return _receipt(payload)


def build_lag_only_forecast_rows(
    ofi_receipt: Mapping[str, Any],
    episode_receipt: Mapping[str, Any],
    split_by_episode: Mapping[str, str],
    *,
    lookback_seconds: float,
) -> dict[str, Any]:
    """Aggregate strictly pre-onset features for each depletion episode."""
    _validate_receipt(ofi_receipt)
    _validate_receipt(episode_receipt)
    lookback = _positive(lookback_seconds, "lookback_seconds")
    events_by_stream: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for event in ofi_receipt.get("events", []):
        events_by_stream[str(event["stream_id"])].append(event)
    for stream in events_by_stream:
        events_by_stream[stream].sort(key=lambda row: (row["event_timestamp"], row["sequence"]))

    episodes = list(episode_receipt.get("episodes", []))
    episode_ids = {str(row["episode_id"]) for row in episodes}
    if set(split_by_episode) != episode_ids:
        missing = sorted(episode_ids - set(split_by_episode))
        extra = sorted(set(split_by_episode) - episode_ids)
        raise CognitiveContractError(
            f"split mapping must cover episodes exactly; missing={missing}, extra={extra}"
        )
    rows: list[dict[str, Any]] = []
    omitted: list[dict[str, str]] = []
    for episode in episodes:
        episode_id = str(episode["episode_id"])
        onset = float(episode["onset_timestamp"])
        history = [
            event
            for event in events_by_stream.get(str(episode["stream_id"]), [])
            if onset - lookback <= float(event["event_timestamp"]) < onset
        ]
        if not history:
            omitted.append({"episode_id": episode_id, "reason": "NO_STRICTLY_LAGGED_EVENTS"})
            continue
        source_max = max(float(event["source_max_timestamp"]) for event in history)
        if source_max >= onset:
            raise CognitiveContractError("lag aggregation included an onset/future event")
        side_sign = 1.0 if episode["side"] == "BID" else -1.0
        first = history[0]
        last = history[-1]
        values = {
            "lag_side_aligned_ofi": side_sign * sum(float(event["ofi"]) for event in history),
            "lag_side_aligned_mid_change": side_sign
            * (float(last["mid_price"]) - float(first["previous_mid_price"])),
            "lag_trade_volume": sum(float(event["trade_volume"]) for event in history),
            "lag_side_aligned_static_imbalance": side_sign
            * float(last["static_imbalance"]),
        }
        source_timestamps = {name: source_max for name in FEATURE_NAMES}
        status = str(episode["status"])
        row = {
            "case_id": episode_id,
            "stream_id": episode["stream_id"],
            "instrument_day": datetime.fromtimestamp(onset, timezone.utc).date().isoformat(),
            "side": episode["side"],
            "split": _identifier(split_by_episode[episode_id], "split"),
            "forecast_timestamp": onset,
            "feature_cutoff_timestamp": source_max,
            "feature_values": values,
            "feature_source_timestamps": source_timestamps,
            "label_status": status,
            "label": episode["outcome_label"],
            "label_reveal_timestamp": episode["label_reveal_timestamp"],
            "onset_observation_hash": episode["onset_observation_hash"],
            "lag_event_ids": [str(event["event_id"]) for event in history],
        }
        rows.append(row)
    normalized = validate_lag_only_forecast_rows(rows, require_resolved_labels=False)
    payload = {
        "implementation_status": IMPLEMENTATION_STATUS,
        "lookback_seconds": lookback,
        "ofi_receipt_hash": ofi_receipt["receipt_hash"],
        "episode_receipt_hash": episode_receipt["receipt_hash"],
        "row_count": len(normalized),
        "omitted_episode_count": len(omitted),
        "omitted": omitted,
        "rows": normalized,
    }
    return _receipt(payload)


def validate_lag_only_forecast_rows(
    rows: Sequence[Mapping[str, Any]], *, require_resolved_labels: bool
) -> list[dict[str, Any]]:
    """Validate the no-future feature and label boundary."""
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        case_id = _identifier(raw.get("case_id"), "case_id")
        if case_id in seen:
            raise CognitiveContractError(f"duplicate forecast case_id: {case_id}")
        seen.add(case_id)
        forecast = _timestamp(raw.get("forecast_timestamp"), "forecast_timestamp")
        cutoff = _timestamp(raw.get("feature_cutoff_timestamp"), "feature_cutoff_timestamp")
        if cutoff >= forecast:
            raise CognitiveContractError(
                f"case {case_id} feature cutoff must be strictly before forecast"
            )
        values_raw = raw.get("feature_values")
        timestamps_raw = raw.get("feature_source_timestamps")
        if not isinstance(values_raw, Mapping) or set(values_raw) != set(FEATURE_NAMES):
            raise CognitiveContractError(
                f"case {case_id} must provide exactly the declared feature values"
            )
        if not isinstance(timestamps_raw, Mapping) or set(timestamps_raw) != set(FEATURE_NAMES):
            raise CognitiveContractError(
                f"case {case_id} must timestamp every declared feature"
            )
        values = {name: _number(values_raw[name], name) for name in FEATURE_NAMES}
        source_timestamps = {
            name: _timestamp(timestamps_raw[name], f"{name}_source_timestamp")
            for name in FEATURE_NAMES
        }
        if any(timestamp >= forecast for timestamp in source_timestamps.values()):
            raise CognitiveContractError(f"case {case_id} contains an onset/future feature")
        if not math.isclose(cutoff, max(source_timestamps.values()), abs_tol=1e-9):
            raise CognitiveContractError(
                f"case {case_id} cutoff is not the maximum feature source timestamp"
            )
        label_status = _identifier(raw.get("label_status"), "label_status")
        if label_status not in {"REFILLED", "NON_REPLENISHED", "CENSORED"}:
            raise CognitiveContractError(f"case {case_id} has an unknown label_status")
        label = raw.get("label")
        reveal_raw = raw.get("label_reveal_timestamp")
        if label_status == "CENSORED":
            if label is not None or reveal_raw is not None:
                raise CognitiveContractError(f"censored case {case_id} must not have a label")
            if require_resolved_labels:
                raise CognitiveContractError(f"fit/scoring row {case_id} is censored")
            reveal = None
        else:
            expected = 1 if label_status == "REFILLED" else 0
            if type(label) is not int or label != expected:
                raise CognitiveContractError(f"case {case_id} label contradicts its status")
            reveal = _timestamp(reveal_raw, "label_reveal_timestamp")
            if reveal <= forecast:
                raise CognitiveContractError(
                    f"case {case_id} label must be revealed after forecast"
                )
        normalized.append(
            {
                **dict(raw),
                "case_id": case_id,
                "stream_id": _identifier(raw.get("stream_id"), "stream_id"),
                "instrument_day": _identifier(raw.get("instrument_day"), "instrument_day"),
                "side": _identifier(raw.get("side"), "side"),
                "split": _identifier(raw.get("split"), "split"),
                "forecast_timestamp": forecast,
                "feature_cutoff_timestamp": cutoff,
                "feature_values": values,
                "feature_source_timestamps": source_timestamps,
                "label_status": label_status,
                "label": label,
                "label_reveal_timestamp": reveal,
            }
        )
    return sorted(normalized, key=lambda row: row["case_id"])


def fit_matched_resiliency_baselines(
    train_rows: Sequence[Mapping[str, Any]], policy: FitPolicy = FitPolicy()
) -> dict[str, Any]:
    """Fit OFI and three one-feature controls on exactly the same TRAIN rows."""
    rows = validate_lag_only_forecast_rows(train_rows, require_resolved_labels=True)
    if not rows:
        raise CognitiveContractError("baseline fitting requires TRAIN rows")
    wrong_split = sorted(row["case_id"] for row in rows if row["split"] != "TRAIN")
    if wrong_split:
        raise CognitiveContractError(
            "fit accepts only rows marked TRAIN; rejected=" + ", ".join(wrong_split)
        )
    labels = [float(row["label"]) for row in rows]
    train_projection = [
        {
            "case_id": row["case_id"],
            "forecast_timestamp": row["forecast_timestamp"],
            "label_reveal_timestamp": row["label_reveal_timestamp"],
            "label": row["label"],
            "feature_values": row["feature_values"],
        }
        for row in rows
    ]
    train_rows_hash = sha256_json(train_projection)
    case_ids = [row["case_id"] for row in rows]
    fit_config = dataclasses.asdict(policy)
    models: dict[str, dict[str, Any]] = {}
    for model_id in MODEL_IDS:
        feature_name = MODEL_FEATURES[model_id]
        raw_values = [float(row["feature_values"][feature_name]) for row in rows]
        mean = statistics.fmean(raw_values)
        scale = math.sqrt(statistics.fmean([(value - mean) ** 2 for value in raw_values]))
        if scale <= 1e-12:
            scale = 1.0
        values = [(value - mean) / scale for value in raw_values]
        intercept = 0.0
        weight = 0.0
        for _ in range(policy.iterations):
            probabilities = [
                _sigmoid(intercept + weight * value) for value in values
            ]
            grad_intercept = statistics.fmean(
                probability - label
                for probability, label in zip(probabilities, labels)
            )
            grad_weight = (
                statistics.fmean(
                    (probability - label) * value
                    for probability, label, value in zip(probabilities, labels, values)
                )
                + policy.l2 * weight
            )
            intercept -= policy.learning_rate * grad_intercept
            weight -= policy.learning_rate * grad_weight
        model = {
            "model_id": model_id,
            "feature_name": feature_name,
            "feature_dimension": 1,
            "train_row_count": len(rows),
            "train_rows_hash": train_rows_hash,
            "standardization_mean": mean,
            "standardization_scale": scale,
            "intercept": intercept,
            "weight": weight,
            "fit_config": fit_config,
        }
        model["model_artifact_hash"] = sha256_json(model)
        models[model_id] = model
    payload = {
        "implementation_status": IMPLEMENTATION_STATUS,
        "lineage": LINEAGE["matched_controls"],
        "train_split": "TRAIN",
        "train_case_ids": case_ids,
        "train_case_ids_hash": sha256_json(case_ids),
        "train_rows_hash": train_rows_hash,
        "fit_config": fit_config,
        "matching_contract": {
            "same_case_ids": True,
            "same_labels": True,
            "same_feature_dimension": 1,
            "same_optimizer_and_budget": True,
            "standardization_fit_on_train_only": True,
        },
        "models": models,
    }
    return _receipt(payload)


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        exp_neg = math.exp(-value)
        return 1.0 / (1.0 + exp_neg)
    exp_pos = math.exp(value)
    return exp_pos / (1.0 + exp_pos)


def predict_matched_resiliency_baselines(
    fit_receipt: Mapping[str, Any], eval_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Predict with frozen train-only fits on disjoint non-TRAIN rows."""
    _validate_receipt(fit_receipt)
    rows = validate_lag_only_forecast_rows(eval_rows, require_resolved_labels=False)
    train_ids = set(str(case_id) for case_id in fit_receipt.get("train_case_ids", []))
    overlap = sorted(train_ids & {row["case_id"] for row in rows})
    if overlap:
        raise CognitiveContractError(
            "evaluation cases overlap fit cases: " + ", ".join(overlap)
        )
    if any(row["split"] == "TRAIN" for row in rows):
        raise CognitiveContractError("prediction evaluation rows must not be marked TRAIN")
    models = fit_receipt.get("models")
    if not isinstance(models, Mapping) or set(models) != set(MODEL_IDS):
        raise CognitiveContractError("fit receipt does not contain the four matched arms")
    predictions: list[dict[str, Any]] = []
    for row in rows:
        for model_id in MODEL_IDS:
            model = models[model_id]
            feature_name = MODEL_FEATURES[model_id]
            value = float(row["feature_values"][feature_name])
            standardized = (
                value - float(model["standardization_mean"])
            ) / float(model["standardization_scale"])
            probability = _sigmoid(
                float(model["intercept"]) + float(model["weight"]) * standardized
            )
            predictions.append(
                {
                    "case_id": row["case_id"],
                    "model_id": model_id,
                    "probability_refilled": probability,
                    "forecast_timestamp": row["forecast_timestamp"],
                    "feature_cutoff_timestamp": row["feature_cutoff_timestamp"],
                    "fit_receipt_hash": fit_receipt["receipt_hash"],
                    "model_artifact_hash": model["model_artifact_hash"],
                    "split": row["split"],
                }
            )
    payload = {
        "implementation_status": IMPLEMENTATION_STATUS,
        "fit_receipt_hash": fit_receipt["receipt_hash"],
        "eval_case_ids_hash": sha256_json([row["case_id"] for row in rows]),
        "prediction_count": len(predictions),
        "predictions": predictions,
    }
    return _receipt(payload)


def score_resiliency_forecasts(
    prediction_receipt: Mapping[str, Any],
    eval_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Score resolved held-out episodes; report censoring without imputing it."""
    _validate_receipt(prediction_receipt)
    rows = validate_lag_only_forecast_rows(eval_rows, require_resolved_labels=False)
    row_by_id = {row["case_id"]: row for row in rows}
    resolved = {case_id: row for case_id, row in row_by_id.items() if row["label"] is not None}
    if not resolved:
        raise CognitiveContractError("scoring requires at least one resolved episode")
    prediction_map: dict[tuple[str, str], float] = {}
    for prediction in prediction_receipt.get("predictions", []):
        case_id = _identifier(prediction.get("case_id"), "case_id")
        model_id = _identifier(prediction.get("model_id"), "model_id")
        if case_id not in row_by_id:
            raise CognitiveContractError(f"prediction references unknown case {case_id}")
        if model_id not in MODEL_IDS:
            raise CognitiveContractError(f"prediction references unknown model {model_id}")
        if prediction.get("fit_receipt_hash") != prediction_receipt.get("fit_receipt_hash"):
            raise CognitiveContractError(
                f"prediction {case_id}/{model_id} has the wrong frozen-fit binding"
            )
        key = (case_id, model_id)
        if key in prediction_map:
            raise CognitiveContractError(f"duplicate prediction for {case_id}/{model_id}")
        probability = _probability(
            prediction.get("probability_refilled"), "probability_refilled"
        )
        if _timestamp(prediction.get("feature_cutoff_timestamp"), "feature_cutoff_timestamp") >= _timestamp(
            prediction.get("forecast_timestamp"), "forecast_timestamp"
        ):
            raise CognitiveContractError(f"prediction {case_id}/{model_id} violates lag-only timing")
        prediction_map[key] = probability
    expected = {(case_id, model_id) for case_id in row_by_id for model_id in MODEL_IDS}
    if set(prediction_map) != expected:
        missing = sorted(expected - set(prediction_map))
        extra = sorted(set(prediction_map) - expected)
        raise CognitiveContractError(
            f"prediction matrix must be complete; missing={missing}, extra={extra}"
        )

    metrics: dict[str, dict[str, Any]] = {}
    for model_id in MODEL_IDS:
        scored = [
            (float(row["label"]), prediction_map[(case_id, model_id)], row["instrument_day"])
            for case_id, row in resolved.items()
        ]
        brier = statistics.fmean((probability - label) ** 2 for label, probability, _ in scored)
        log_loss = statistics.fmean(
            -(
                label * math.log(min(max(probability, 1e-15), 1.0 - 1e-15))
                + (1.0 - label)
                * math.log(min(max(1.0 - probability, 1e-15), 1.0 - 1e-15))
            )
            for label, probability, _ in scored
        )
        day_brier = {
            day: statistics.fmean(
                (probability - label) ** 2
                for label, probability, row_day in scored
                if row_day == day
            )
            for day in sorted({day for _, _, day in scored})
        }
        metrics[model_id] = {
            "resolved_row_count": len(scored),
            "brier": brier,
            "log_loss": log_loss,
            "brier_by_instrument_day": day_brier,
        }
    ofi_brier = float(metrics["OFI"]["brier"])
    comparisons = {}
    for control in MODEL_IDS[1:]:
        control_brier = float(metrics[control]["brier"])
        comparisons[control] = {
            "relative_brier_improvement_ofi_vs_control": (
                (control_brier - ofi_brier) / control_brier if control_brier > 0.0 else None
            )
        }
    payload = {
        "implementation_status": IMPLEMENTATION_STATUS,
        "claim": "METRICS_ONLY_NO_PASS_OR_FORWARD_GAIN_CLAIM",
        "evaluation_row_count": len(rows),
        "resolved_row_count": len(resolved),
        "censored_row_count": len(rows) - len(resolved),
        "censoring_fraction": (len(rows) - len(resolved)) / len(rows),
        "refill_rate_resolved": statistics.fmean(float(row["label"]) for row in resolved.values()),
        "metrics": metrics,
        "comparisons": comparisons,
        "prediction_receipt_hash": prediction_receipt["receipt_hash"],
    }
    return _receipt(payload)
