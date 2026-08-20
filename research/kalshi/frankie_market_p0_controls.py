"""Fail-closed market/temporal evidence controls for Frankie.

This module is deliberately outside the V4 runners.  It scores or validates
evidence; it does not choose a V4 lock, update a model, authorize a run, or
promote a candidate.

Evidence-lineage boundary
-------------------------
The papers motivating this work support evaluating error together with
decision time/delay, assessing calibration under temporal change, and using
chronological current-risk evidence.  The exact one-to-one event matcher,
false-alarms-per-observed-hour measure, reveal-time embargo, declared-stratum
thresholds, repeated-seed paired gate, retention matrix, byte-exact rollback,
and planted-null contamination receipt are Frankie-added operational controls.
They are not claimed as paper-faithful implementations of ECOTS, accumulated
accuracy gap, adaptive conformal inference, or temporal model selection.
"""
from __future__ import annotations

import dataclasses
import hashlib
import itertools
import math
import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from frankie_cognition import CognitiveContractError, sha256_json


SHA256_RE = re.compile(r"[0-9a-f]{64}")
VALIDATOR_STATUS = "VALIDATOR_OR_EVALUATION_HELPER_NOT_RUNTIME_MODEL"

LINEAGE = {
    "open_stream": {
        "paper_derived": (
            "joint evaluation of prediction error and decision time/delay is "
            "motivated by early-classification work (ECOTS and accumulated accuracy gap)"
        ),
        "frankie_added": (
            "stream-local one-to-one matching, explicit early/late windows, misses, "
            "and false alarms per observed hour"
        ),
    },
    "reveal_split": {
        "paper_derived": (
            "chronological/current-risk assessment is motivated by temporal model-selection work"
        ),
        "frankie_added": (
            "the exact reveal-time embargo, case/group disjointness, and end-before-reveal rules"
        ),
    },
    "calibration": {
        "paper_derived": (
            "calibration under changing distributions is motivated by adaptive conformal inference"
        ),
        "frankie_added": (
            "Brier, clipped log loss, equal-width ECE, declared-stratum completeness, "
            "selective-risk, wrong-lock, and coverage thresholds"
        ),
    },
    "paired": {
        "paper_derived": "none; this is experimental-governance plumbing",
        "frankie_added": (
            "exact repeated-seed pairing and a case-clustered normal lower confidence bound"
        ),
    },
    "first_lock": {
        "paper_derived": "none; this is a reconciliation validator",
        "frankie_added": (
            "recompute the immutable first lock at the current second after consecutive "
            "qualifying observations, never backdated"
        ),
    },
    "retention_rollback": {
        "paper_derived": "none; this is Frankie retention and rollback governance",
        "frankie_added": (
            "complete protected-suite/stratum matrix and byte-exact restoration checks"
        ),
    },
    "adaptive_null": {
        "paper_derived": "none; this is adaptive-evaluation contamination governance",
        "frankie_added": (
            "precommitted planted-null false-selection gate and hash-parent separation receipt"
        ),
    },
}


def _identifier(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise CognitiveContractError(f"{field} must be a non-empty identifier")
    return result


def _sha256(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not SHA256_RE.fullmatch(result):
        raise CognitiveContractError(f"{field} must be a lowercase SHA-256 value")
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


def _probability(value: Any, field: str) -> float:
    result = _number(value, field)
    if not 0.0 <= result <= 1.0:
        raise CognitiveContractError(f"{field} must be within [0, 1]")
    return result


def _binary(value: Any, field: str) -> int:
    if type(value) is not int or value not in (0, 1):
        raise CognitiveContractError(f"{field} must be integer 0 or 1")
    return int(value)


def _timestamp(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise CognitiveContractError(f"{field} must be a finite epoch or timezone-aware ISO timestamp")
    if isinstance(value, (int, float)):
        return _number(value, field)
    if not isinstance(value, str) or not value.strip():
        raise CognitiveContractError(f"{field} must be a finite epoch or timezone-aware ISO timestamp")
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


def _quantile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    core = dict(payload)
    return {**core, "receipt_hash": sha256_json(core)}


def score_open_stream_events(
    events: Sequence[Mapping[str, Any]],
    alarms: Sequence[Mapping[str, Any]],
    observation_windows: Sequence[Mapping[str, Any]],
    *,
    max_early_seconds: float = 0.0,
    max_late_seconds: float,
) -> dict[str, Any]:
    """Match alarms to events once, then score misses, false alarms, and delay.

    Matching is chronological and stream-local.  With fixed early/late windows,
    consuming the earliest compatible alarm for the earliest event is a
    deterministic maximum-cardinality ordered match.  An alarm cannot explain
    two events and events in one stream cannot borrow alarms from another.
    """
    early = _nonnegative(max_early_seconds, "max_early_seconds")
    late = _nonnegative(max_late_seconds, "max_late_seconds")
    if not observation_windows:
        raise CognitiveContractError("open-stream scoring requires observation windows")

    windows: dict[str, tuple[float, float]] = {}
    normalized_windows: list[dict[str, Any]] = []
    for row in observation_windows:
        stream = _identifier(row.get("stream_id"), "stream_id")
        if stream in windows:
            raise CognitiveContractError(f"duplicate observation window for {stream}")
        start = _timestamp(row.get("start_timestamp"), "start_timestamp")
        end = _timestamp(row.get("end_timestamp"), "end_timestamp")
        if end <= start:
            raise CognitiveContractError(f"observation window {stream} must have end > start")
        windows[stream] = (start, end)
        normalized_windows.append({"stream_id": stream, "start": start, "end": end})

    def normalize_rows(
        rows: Sequence[Mapping[str, Any]], *, kind: str
    ) -> dict[str, list[tuple[float, str]]]:
        result = {stream: [] for stream in windows}
        seen: set[str] = set()
        id_field = f"{kind}_id"
        for row in rows:
            item_id = _identifier(row.get(id_field), id_field)
            if item_id in seen:
                raise CognitiveContractError(f"duplicate {id_field}: {item_id}")
            seen.add(item_id)
            stream = _identifier(row.get("stream_id"), "stream_id")
            if stream not in windows:
                raise CognitiveContractError(f"{kind} {item_id} references an undeclared stream")
            timestamp = _timestamp(row.get("timestamp"), "timestamp")
            start, end = windows[stream]
            if not start <= timestamp <= end:
                raise CognitiveContractError(f"{kind} {item_id} falls outside its observation window")
            result[stream].append((timestamp, item_id))
        for stream in result:
            result[stream].sort(key=lambda item: (item[0], item[1]))
        return result

    events_by_stream = normalize_rows(events, kind="event")
    alarms_by_stream = normalize_rows(alarms, kind="alarm")
    matches: list[dict[str, Any]] = []
    missed: list[str] = []
    false_alarms: list[str] = []

    for stream in sorted(windows):
        stream_events = events_by_stream[stream]
        stream_alarms = alarms_by_stream[stream]
        event_index = alarm_index = 0
        while event_index < len(stream_events) and alarm_index < len(stream_alarms):
            event_time, event_id = stream_events[event_index]
            alarm_time, alarm_id = stream_alarms[alarm_index]
            if alarm_time < event_time - early:
                false_alarms.append(alarm_id)
                alarm_index += 1
            elif alarm_time > event_time + late:
                missed.append(event_id)
                event_index += 1
            else:
                delay = alarm_time - event_time
                matches.append(
                    {
                        "stream_id": stream,
                        "event_id": event_id,
                        "alarm_id": alarm_id,
                        "event_timestamp": event_time,
                        "alarm_timestamp": alarm_time,
                        "delay_seconds": delay,
                    }
                )
                event_index += 1
                alarm_index += 1
        missed.extend(event_id for _, event_id in stream_events[event_index:])
        false_alarms.extend(alarm_id for _, alarm_id in stream_alarms[alarm_index:])

    event_count = sum(len(rows) for rows in events_by_stream.values())
    alarm_count = sum(len(rows) for rows in alarms_by_stream.values())
    matched_count = len(matches)
    exposure_seconds = sum(end - start for start, end in windows.values())
    delays = [float(row["delay_seconds"]) for row in matches]
    metrics = {
        "event_count": event_count,
        "alarm_count": alarm_count,
        "matched_count": matched_count,
        "missed_event_count": len(missed),
        "false_alarm_count": len(false_alarms),
        "precision": matched_count / alarm_count if alarm_count else None,
        "recall": matched_count / event_count if event_count else None,
        "false_alarms_per_observed_hour": len(false_alarms) / (exposure_seconds / 3600.0),
        "mean_delay_seconds": statistics.fmean(delays) if delays else None,
        "median_delay_seconds": statistics.median(delays) if delays else None,
        "p90_delay_seconds": _quantile(delays, 0.90),
        "early_match_fraction": sum(delay < 0.0 for delay in delays) / len(delays) if delays else None,
        "observed_seconds": exposure_seconds,
    }
    normalized_inputs = {
        "events": [
            {"stream_id": stream, "timestamp": timestamp, "event_id": item_id}
            for stream in sorted(events_by_stream)
            for timestamp, item_id in events_by_stream[stream]
        ],
        "alarms": [
            {"stream_id": stream, "timestamp": timestamp, "alarm_id": item_id}
            for stream in sorted(alarms_by_stream)
            for timestamp, item_id in alarms_by_stream[stream]
        ],
        "observation_windows": sorted(normalized_windows, key=lambda row: row["stream_id"]),
    }
    return _receipt(
        {
            "status": VALIDATOR_STATUS,
            "lineage": LINEAGE["open_stream"],
            "input_hash": sha256_json(normalized_inputs),
            "policy": {"max_early_seconds": early, "max_late_seconds": late},
            "metrics": metrics,
            "matches": matches,
            "missed_event_ids": sorted(missed),
            "false_alarm_ids": sorted(false_alarms),
        }
    )


def validate_reveal_time_purged_splits(
    rows: Sequence[Mapping[str, Any]],
    split_order: Sequence[str],
    *,
    embargo_seconds: float = 0.0,
) -> dict[str, Any]:
    """Require causal cases and reveal-time isolation between ordered splits."""
    embargo = _nonnegative(embargo_seconds, "embargo_seconds")
    splits = tuple(_identifier(value, "split_order item") for value in split_order)
    if len(splits) < 2 or len(set(splits)) != len(splits):
        raise CognitiveContractError("split_order requires at least two unique split ids")
    if not rows:
        raise CognitiveContractError("purged split validation requires cases")

    normalized: list[dict[str, Any]] = []
    seen_cases: set[str] = set()
    group_splits: dict[str, set[str]] = {}
    by_split: dict[str, list[dict[str, Any]]] = {split: [] for split in splits}
    for row in rows:
        case_id = _identifier(row.get("case_id"), "case_id")
        group_id = _identifier(row.get("group_id"), "group_id")
        split = _identifier(row.get("split"), "split")
        if case_id in seen_cases:
            raise CognitiveContractError(f"duplicate case_id: {case_id}")
        if split not in by_split:
            raise CognitiveContractError(f"case {case_id} has undeclared split {split}")
        seen_cases.add(case_id)
        start = _timestamp(row.get("start_timestamp"), "start_timestamp")
        end = _timestamp(row.get("end_timestamp"), "end_timestamp")
        reveal = _timestamp(row.get("reveal_timestamp"), "reveal_timestamp")
        if not start <= end < reveal:
            raise CognitiveContractError(f"case {case_id} violates start <= end < reveal")
        item = {
            "case_id": case_id,
            "group_id": group_id,
            "split": split,
            "start": start,
            "end": end,
            "reveal": reveal,
        }
        normalized.append(item)
        by_split[split].append(item)
        group_splits.setdefault(group_id, set()).add(split)

    missing = [split for split, items in by_split.items() if not items]
    if missing:
        raise CognitiveContractError("declared splits have no cases: " + ", ".join(missing))
    reused = sorted(group for group, memberships in group_splits.items() if len(memberships) > 1)
    if reused:
        raise CognitiveContractError("groups cross split boundaries: " + ", ".join(reused))

    boundaries: list[dict[str, Any]] = []
    prior_rows: list[dict[str, Any]] = []
    for index, split in enumerate(splits):
        current = by_split[split]
        if index:
            prior_max_reveal = max(item["reveal"] for item in prior_rows)
            current_min_start = min(item["start"] for item in current)
            required_start = prior_max_reveal + embargo
            if current_min_start < required_start:
                raise CognitiveContractError(
                    f"split {split} starts before prior labels reveal plus embargo: "
                    f"{current_min_start} < {required_start}"
                )
            boundaries.append(
                {
                    "prior_splits": list(splits[:index]),
                    "next_split": split,
                    "prior_max_reveal": prior_max_reveal,
                    "next_min_start": current_min_start,
                    "embargo_seconds": embargo,
                    "clearance_seconds": current_min_start - prior_max_reveal,
                }
            )
        prior_rows.extend(current)

    normalized.sort(key=lambda item: (splits.index(item["split"]), item["start"], item["case_id"]))
    return _receipt(
        {
            "status": VALIDATOR_STATUS,
            "verdict": "PASS",
            "lineage": LINEAGE["reveal_split"],
            "split_order": list(splits),
            "embargo_seconds": embargo,
            "case_count": len(normalized),
            "case_manifest_hash": sha256_json(normalized),
            "boundaries": boundaries,
        }
    )


def validate_first_lock_movie(
    rows: Sequence[Mapping[str, Any]],
    labels: Sequence[str],
    rule: Mapping[str, Any],
    recorded_lock: Mapping[str, Any] | None,
    *,
    probability_tolerance: float = 1e-9,
) -> dict[str, Any]:
    """Recompute the provisional V4 first-lock rule from a probability movie.

    This mirrors the documented rule without selecting or changing it.  The
    decision is emitted at the current observation after persistence has been
    seen; it is never moved back to the beginning of the qualifying run.
    """
    label_list = tuple(_identifier(value, "label") for value in labels)
    if len(label_list) < 2 or len(set(label_list)) != len(label_list):
        raise CognitiveContractError("first-lock validation requires at least two unique labels")
    minimum_probability = _probability(
        rule.get("minimum_probability"), "minimum_probability"
    )
    minimum_margin = _probability(rule.get("minimum_margin"), "minimum_margin")
    persistence = rule.get("persistence_seconds")
    if type(persistence) is not int or persistence < 1:
        raise CognitiveContractError("persistence_seconds must be an integer >= 1")
    tolerance = _nonnegative(probability_tolerance, "probability_tolerance")
    if tolerance > 1e-6:
        raise CognitiveContractError("probability_tolerance may not exceed 1e-6")
    if not rows:
        raise CognitiveContractError("first-lock validation requires a probability movie")

    normalized: list[dict[str, Any]] = []
    last_timestamp: float | None = None
    run_label: str | None = None
    run_count = 0
    computed: dict[str, Any] | None = None
    for row in rows:
        timestamp = _timestamp(row.get("timestamp"), "timestamp")
        if last_timestamp is not None and timestamp <= last_timestamp:
            raise CognitiveContractError("probability movie timestamps must be strictly increasing")
        raw_probabilities = row.get("probabilities")
        if not isinstance(raw_probabilities, Mapping) or set(raw_probabilities) != set(label_list):
            raise CognitiveContractError("probability row must contain exactly the declared labels")
        probabilities = {
            label: _probability(raw_probabilities[label], f"probability[{label}]")
            for label in label_list
        }
        if abs(sum(probabilities.values()) - 1.0) > tolerance:
            raise CognitiveContractError("probability row does not sum to one within tolerance")
        order = sorted(range(len(label_list)), key=lambda index: (probabilities[label_list[index]], index))
        winner = label_list[order[-1]]
        runner_up = label_list[order[-2]]
        winning_probability = probabilities[winner]
        margin = winning_probability - probabilities[runner_up]
        qualifies = winning_probability >= minimum_probability and margin >= minimum_margin
        consecutive = last_timestamp is not None and timestamp == last_timestamp + 1.0
        if qualifies:
            if run_label == winner and consecutive:
                run_count += 1
            else:
                run_label = winner
                run_count = 1
        else:
            run_label = None
            run_count = 0
        item = {"timestamp": timestamp, "probabilities": probabilities}
        normalized.append(item)
        if computed is None and qualifies and run_count >= persistence:
            computed = {
                "decision_timestamp": timestamp,
                "predicted_label": winner,
                "winning_probability": winning_probability,
                "winning_margin": margin,
                "persistence_observed_seconds": run_count,
                "probabilities": probabilities,
            }
        last_timestamp = timestamp

    if recorded_lock is None:
        if computed is not None:
            raise CognitiveContractError("recorded no-lock disagrees with recomputed first lock")
    else:
        if not isinstance(recorded_lock, Mapping) or computed is None:
            raise CognitiveContractError("recorded lock disagrees with recomputed no-lock")
        required_keys = set(computed)
        if not required_keys.issubset(recorded_lock):
            raise CognitiveContractError("recorded lock is missing recomputed fields")
        recorded_probabilities = recorded_lock.get("probabilities")
        if not isinstance(recorded_probabilities, Mapping) or set(recorded_probabilities) != set(label_list):
            raise CognitiveContractError("recorded lock probabilities do not match labels")
        if (
            _timestamp(recorded_lock.get("decision_timestamp"), "recorded decision_timestamp")
            != computed["decision_timestamp"]
            or _identifier(recorded_lock.get("predicted_label"), "recorded predicted_label")
            != computed["predicted_label"]
            or recorded_lock.get("persistence_observed_seconds")
            != computed["persistence_observed_seconds"]
        ):
            raise CognitiveContractError("recorded lock is not the recomputed immutable first lock")
        for field in ("winning_probability", "winning_margin"):
            if abs(_number(recorded_lock.get(field), f"recorded {field}") - computed[field]) > tolerance:
                raise CognitiveContractError(f"recorded lock {field} mismatch")
        for label in label_list:
            if abs(
                _probability(recorded_probabilities[label], f"recorded probability[{label}]")
                - computed["probabilities"][label]
            ) > tolerance:
                raise CognitiveContractError("recorded lock probability vector mismatch")

    policy = {
        "minimum_probability": minimum_probability,
        "minimum_margin": minimum_margin,
        "persistence_seconds": persistence,
        "decision_time_policy": "CURRENT_SECOND_AFTER_PERSISTENCE_OBSERVED_NEVER_BACKDATED",
    }
    return _receipt(
        {
            "status": VALIDATOR_STATUS,
            "verdict": "PASS",
            "lineage": LINEAGE["first_lock"],
            "movie_hash": sha256_json(normalized),
            "policy": policy,
            "policy_hash": sha256_json(policy),
            "computed_first_lock": computed,
        }
    )


@dataclass(frozen=True)
class CalibrationPolicy:
    ece_bins: int
    min_rows_per_stratum: int
    min_selected_per_stratum: int
    max_brier: float
    max_log_loss: float
    max_ece: float
    max_selective_risk: float
    max_wrong_lock_rate: float
    min_coverage: float
    log_epsilon: float = 1e-15

    def __post_init__(self) -> None:
        if type(self.ece_bins) is not int or self.ece_bins < 2:
            raise CognitiveContractError("ece_bins must be an integer >= 2")
        if type(self.min_rows_per_stratum) is not int or self.min_rows_per_stratum < 1:
            raise CognitiveContractError("min_rows_per_stratum must be >= 1")
        if type(self.min_selected_per_stratum) is not int or self.min_selected_per_stratum < 1:
            raise CognitiveContractError("min_selected_per_stratum must be >= 1")
        for field in (
            "max_brier", "max_ece", "max_selective_risk",
            "max_wrong_lock_rate", "min_coverage",
        ):
            _probability(getattr(self, field), field)
        _nonnegative(self.max_log_loss, "max_log_loss")
        epsilon = _probability(self.log_epsilon, "log_epsilon")
        if epsilon <= 0.0 or epsilon >= 0.5:
            raise CognitiveContractError("log_epsilon must be within (0, 0.5)")


def _calibration_metrics(rows: Sequence[Mapping[str, Any]], policy: CalibrationPolicy) -> dict[str, Any]:
    count = len(rows)
    selected = [row for row in rows if row["selected"]]
    wrong = sum(row["lock_label"] != row["truth"] for row in selected)
    brier = statistics.fmean((row["probability"] - row["truth"]) ** 2 for row in rows)
    log_losses = []
    for row in rows:
        probability = min(1.0 - policy.log_epsilon, max(policy.log_epsilon, row["probability"]))
        log_losses.append(
            -(row["truth"] * math.log(probability) + (1 - row["truth"]) * math.log(1.0 - probability))
        )
    bins: list[list[Mapping[str, Any]]] = [[] for _ in range(policy.ece_bins)]
    for row in rows:
        index = min(policy.ece_bins - 1, int(row["probability"] * policy.ece_bins))
        bins[index].append(row)
    ece = sum(
        (len(items) / count)
        * abs(
            statistics.fmean(item["probability"] for item in items)
            - statistics.fmean(item["truth"] for item in items)
        )
        for items in bins
        if items
    )
    return {
        "rows": count,
        "selected_rows": len(selected),
        "brier": brier,
        "log_loss": statistics.fmean(log_losses),
        "ece": ece,
        "coverage": len(selected) / count,
        "selective_risk": wrong / len(selected) if selected else None,
        "wrong_lock_count": wrong,
        "wrong_lock_rate": wrong / count,
    }


def evaluate_calibration_selective_gate(
    rows: Sequence[Mapping[str, Any]],
    declared_strata: Sequence[str],
    policy: CalibrationPolicy,
) -> dict[str, Any]:
    """Score probabilistic locks overall and within every declared stratum."""
    strata = tuple(_identifier(value, "declared stratum") for value in declared_strata)
    if not strata or len(set(strata)) != len(strata):
        raise CognitiveContractError("declared_strata requires unique non-empty ids")
    if not rows:
        raise CognitiveContractError("calibration evaluation requires rows")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    by_stratum: dict[str, list[dict[str, Any]]] = {stratum: [] for stratum in strata}
    for row in rows:
        case_id = _identifier(row.get("case_id"), "case_id")
        if case_id in seen:
            raise CognitiveContractError(f"duplicate calibration case_id: {case_id}")
        seen.add(case_id)
        stratum = _identifier(row.get("stratum"), "stratum")
        if stratum not in by_stratum:
            raise CognitiveContractError(f"case {case_id} has undeclared stratum {stratum}")
        truth = _binary(row.get("truth"), "truth")
        probability = _probability(row.get("probability"), "probability")
        selected = row.get("selected")
        if type(selected) is not bool:
            raise CognitiveContractError(f"case {case_id} selected must be boolean")
        lock_raw = row.get("lock_label")
        if selected:
            lock_label: int | None = _binary(lock_raw, "lock_label")
        else:
            if lock_raw is not None:
                raise CognitiveContractError(f"unselected case {case_id} must not carry lock_label")
            lock_label = None
        item = {
            "case_id": case_id,
            "stratum": stratum,
            "truth": truth,
            "probability": probability,
            "selected": selected,
            "lock_label": lock_label,
        }
        normalized.append(item)
        by_stratum[stratum].append(item)
    empty = [stratum for stratum, items in by_stratum.items() if not items]
    if empty:
        raise CognitiveContractError("declared strata have no rows: " + ", ".join(empty))

    metrics = {"ALL": _calibration_metrics(normalized, policy)}
    metrics.update({stratum: _calibration_metrics(by_stratum[stratum], policy) for stratum in strata})
    blockers: list[str] = []
    for stratum, values in metrics.items():
        if values["rows"] < policy.min_rows_per_stratum:
            blockers.append(f"{stratum}: rows below minimum")
        if values["selected_rows"] < policy.min_selected_per_stratum:
            blockers.append(f"{stratum}: selected rows below minimum")
        checks = (
            ("brier", values["brier"], policy.max_brier, "max"),
            ("log_loss", values["log_loss"], policy.max_log_loss, "max"),
            ("ece", values["ece"], policy.max_ece, "max"),
            ("selective_risk", values["selective_risk"], policy.max_selective_risk, "max"),
            ("wrong_lock_rate", values["wrong_lock_rate"], policy.max_wrong_lock_rate, "max"),
            ("coverage", values["coverage"], policy.min_coverage, "min"),
        )
        for name, actual, limit, direction in checks:
            if actual is None or (direction == "max" and actual > limit) or (direction == "min" and actual < limit):
                blockers.append(f"{stratum}: {name} violates declared threshold")

    normalized.sort(key=lambda item: (item["stratum"], item["case_id"]))
    policy_data = dataclasses.asdict(policy)
    return _receipt(
        {
            "status": VALIDATOR_STATUS,
            "verdict": "PASS" if not blockers else "FAIL",
            "lineage": LINEAGE["calibration"],
            "declared_strata": list(strata),
            "row_hash": sha256_json(normalized),
            "policy": policy_data,
            "policy_hash": sha256_json(policy_data),
            "metrics": metrics,
            "blockers": blockers,
        }
    )


@dataclass(frozen=True)
class PairedEvidencePolicy:
    min_cases: int
    min_seeds_per_case: int
    min_effect: float
    confidence_z: float
    min_case_win_rate: float
    max_seed_loss_rate: float

    def __post_init__(self) -> None:
        if type(self.min_cases) is not int or self.min_cases < 2:
            raise CognitiveContractError("min_cases must be an integer >= 2")
        if type(self.min_seeds_per_case) is not int or self.min_seeds_per_case < 2:
            raise CognitiveContractError("min_seeds_per_case must be an integer >= 2")
        _number(self.min_effect, "min_effect")
        if _number(self.confidence_z, "confidence_z") <= 0.0:
            raise CognitiveContractError("confidence_z must be positive")
        _probability(self.min_case_win_rate, "min_case_win_rate")
        _probability(self.max_seed_loss_rate, "max_seed_loss_rate")


def evaluate_paired_repeated_seed_gate(
    rows: Sequence[Mapping[str, Any]],
    declared_seeds: Sequence[int],
    policy: PairedEvidencePolicy,
    *,
    higher_is_better: bool = True,
) -> dict[str, Any]:
    """Gate paired evidence after clustering repeated seeds within each case.

    The lower bound is a normal approximation over case-level mean paired
    differences.  It is an operational gate, not a distribution-free theorem.
    """
    if type(higher_is_better) is not bool:
        raise CognitiveContractError("higher_is_better must be boolean")
    seeds = tuple(declared_seeds)
    if (
        len(seeds) < policy.min_seeds_per_case
        or len(set(seeds)) != len(seeds)
        or any(type(seed) is not int for seed in seeds)
    ):
        raise CognitiveContractError("declared_seeds must be unique integers meeting the policy minimum")
    if not rows:
        raise CognitiveContractError("paired evidence requires rows")

    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    by_case: dict[str, dict[int, float]] = {}
    for row in rows:
        case_id = _identifier(row.get("case_id"), "case_id")
        seed = row.get("seed")
        if type(seed) is not int or seed not in seeds:
            raise CognitiveContractError(f"case {case_id} has undeclared seed")
        key = (case_id, seed)
        if key in seen:
            raise CognitiveContractError(f"duplicate paired row: {case_id}/{seed}")
        seen.add(key)
        candidate = _number(row.get("candidate_metric"), "candidate_metric")
        control = _number(row.get("control_metric"), "control_metric")
        difference = (candidate - control) * (1.0 if higher_is_better else -1.0)
        item = {
            "case_id": case_id,
            "seed": seed,
            "candidate_metric": candidate,
            "control_metric": control,
            "oriented_difference": difference,
        }
        normalized.append(item)
        by_case.setdefault(case_id, {})[seed] = difference
    if len(by_case) < policy.min_cases:
        raise CognitiveContractError("paired evidence has fewer cases than the policy minimum")
    expected = set(seeds)
    incomplete = sorted(case_id for case_id, values in by_case.items() if set(values) != expected)
    if incomplete:
        raise CognitiveContractError("cases do not have the exact declared seed set: " + ", ".join(incomplete))

    case_means = {case: statistics.fmean(values.values()) for case, values in by_case.items()}
    ordered_case_means = [case_means[case] for case in sorted(case_means)]
    mean_effect = statistics.fmean(ordered_case_means)
    standard_error = statistics.stdev(ordered_case_means) / math.sqrt(len(ordered_case_means))
    lower_bound = mean_effect - policy.confidence_z * standard_error
    case_win_rate = sum(value > policy.min_effect for value in ordered_case_means) / len(ordered_case_means)
    seed_means = {
        seed: statistics.fmean(by_case[case][seed] for case in by_case)
        for seed in seeds
    }
    seed_loss_rate = sum(value < policy.min_effect for value in seed_means.values()) / len(seed_means)
    blockers: list[str] = []
    if lower_bound <= policy.min_effect:
        blockers.append("case-clustered lower confidence bound does not exceed min_effect")
    if case_win_rate < policy.min_case_win_rate:
        blockers.append("case win rate is below threshold")
    if seed_loss_rate > policy.max_seed_loss_rate:
        blockers.append("seed loss rate exceeds threshold")

    normalized.sort(key=lambda item: (item["case_id"], item["seed"]))
    policy_data = dataclasses.asdict(policy)
    return _receipt(
        {
            "status": VALIDATOR_STATUS,
            "verdict": "PASS" if not blockers else "FAIL",
            "lineage": LINEAGE["paired"],
            "declared_seeds": list(seeds),
            "higher_is_better": higher_is_better,
            "row_hash": sha256_json(normalized),
            "policy": policy_data,
            "policy_hash": sha256_json(policy_data),
            "case_count": len(by_case),
            "mean_paired_effect": mean_effect,
            "case_clustered_standard_error": standard_error,
            "lower_confidence_bound": lower_bound,
            "case_win_rate": case_win_rate,
            "seed_mean_effects": seed_means,
            "seed_loss_rate": seed_loss_rate,
            "blockers": blockers,
        }
    )


@dataclass(frozen=True)
class RetentionPolicy:
    min_rows_per_cell: int
    max_regression: float

    def __post_init__(self) -> None:
        if type(self.min_rows_per_cell) is not int or self.min_rows_per_cell < 1:
            raise CognitiveContractError("min_rows_per_cell must be an integer >= 1")
        _nonnegative(self.max_regression, "max_regression")


def evaluate_retention_matrix(
    rows: Sequence[Mapping[str, Any]],
    declared_suites: Sequence[str],
    declared_strata: Sequence[str],
    policy: RetentionPolicy,
) -> dict[str, Any]:
    """Require and evaluate every declared protected-suite/stratum cell."""
    suites = tuple(_identifier(value, "declared suite") for value in declared_suites)
    strata = tuple(_identifier(value, "declared stratum") for value in declared_strata)
    if not suites or len(set(suites)) != len(suites):
        raise CognitiveContractError("declared_suites must contain unique ids")
    if not strata or len(set(strata)) != len(strata):
        raise CognitiveContractError("declared_strata must contain unique ids")
    expected = set(itertools.product(suites, strata))
    cells: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        suite = _identifier(row.get("suite_id"), "suite_id")
        stratum = _identifier(row.get("stratum"), "stratum")
        key = (suite, stratum)
        if key not in expected:
            raise CognitiveContractError(f"undeclared retention cell: {suite}/{stratum}")
        if key in cells:
            raise CognitiveContractError(f"duplicate retention cell: {suite}/{stratum}")
        baseline = _number(row.get("baseline_metric"), "baseline_metric")
        candidate = _number(row.get("candidate_metric"), "candidate_metric")
        higher = row.get("higher_is_better")
        if type(higher) is not bool:
            raise CognitiveContractError(f"retention cell {suite}/{stratum} needs higher_is_better boolean")
        count = row.get("row_count")
        if type(count) is not int or count < 0:
            raise CognitiveContractError(f"retention cell {suite}/{stratum} row_count must be non-negative int")
        oriented_delta = (candidate - baseline) * (1.0 if higher else -1.0)
        cells[key] = {
            "suite_id": suite,
            "stratum": stratum,
            "row_count": count,
            "baseline_metric": baseline,
            "candidate_metric": candidate,
            "higher_is_better": higher,
            "oriented_delta": oriented_delta,
        }
    missing = sorted(expected - set(cells))
    if missing:
        raise CognitiveContractError(
            "retention matrix is incomplete: " + ", ".join(f"{suite}/{stratum}" for suite, stratum in missing)
        )

    blockers: list[str] = []
    ordered = [cells[(suite, stratum)] for suite in suites for stratum in strata]
    for cell in ordered:
        label = f"{cell['suite_id']}/{cell['stratum']}"
        if cell["row_count"] < policy.min_rows_per_cell:
            blockers.append(f"{label}: row_count below minimum")
        if cell["oriented_delta"] < -policy.max_regression:
            blockers.append(f"{label}: regression exceeds tolerance")
    policy_data = dataclasses.asdict(policy)
    return _receipt(
        {
            "status": VALIDATOR_STATUS,
            "verdict": "PASS" if not blockers else "FAIL",
            "lineage": LINEAGE["retention_rollback"],
            "declared_suites": list(suites),
            "declared_strata": list(strata),
            "matrix_hash": sha256_json(ordered),
            "policy": policy_data,
            "policy_hash": sha256_json(policy_data),
            "cells": ordered,
            "blockers": blockers,
        }
    )


def validate_byte_exact_rollback(
    before: Mapping[str, bytes],
    candidate: Mapping[str, bytes],
    restored: Mapping[str, bytes],
    expected_before_hashes: Mapping[str, str],
) -> dict[str, Any]:
    """Verify a non-vacuous candidate mutation restores exact baseline bytes."""
    key_sets = [set(mapping) for mapping in (before, candidate, restored, expected_before_hashes)]
    if not key_sets[0] or any(keys != key_sets[0] for keys in key_sets[1:]):
        raise CognitiveContractError("rollback mappings must have the same non-empty artifact ids")
    artifacts: list[dict[str, Any]] = []
    changed_count = 0
    for artifact_id in sorted(key_sets[0]):
        _identifier(artifact_id, "artifact_id")
        values = (before[artifact_id], candidate[artifact_id], restored[artifact_id])
        if any(not isinstance(value, bytes) for value in values):
            raise CognitiveContractError(f"rollback artifact {artifact_id} must be bytes")
        expected = _sha256(expected_before_hashes[artifact_id], f"expected hash for {artifact_id}")
        hashes = tuple(hashlib.sha256(value).hexdigest() for value in values)
        if hashes[0] != expected:
            raise CognitiveContractError(f"baseline artifact {artifact_id} does not match expected hash")
        changed = values[1] != values[0]
        changed_count += int(changed)
        if values[2] != values[0] or hashes[2] != expected:
            raise CognitiveContractError(f"rollback artifact {artifact_id} was not restored byte-for-byte")
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "before_hash": hashes[0],
                "candidate_hash": hashes[1],
                "restored_hash": hashes[2],
                "candidate_changed": changed,
                "byte_count": len(values[0]),
            }
        )
    if changed_count == 0:
        raise CognitiveContractError("rollback exercise is vacuous: candidate changed no artifacts")
    return _receipt(
        {
            "status": VALIDATOR_STATUS,
            "verdict": "PASS",
            "lineage": LINEAGE["retention_rollback"],
            "artifact_count": len(artifacts),
            "changed_artifact_count": changed_count,
            "artifacts": artifacts,
        }
    )


@dataclass(frozen=True)
class AdaptiveNullPolicy:
    min_trials: int
    max_false_selection_rate: float
    confidence_z: float = 1.96

    def __post_init__(self) -> None:
        if type(self.min_trials) is not int or self.min_trials < 2:
            raise CognitiveContractError("min_trials must be an integer >= 2")
        _probability(self.max_false_selection_rate, "max_false_selection_rate")
        if _number(self.confidence_z, "confidence_z") <= 0.0:
            raise CognitiveContractError("confidence_z must be positive")


def _wilson_upper(successes: int, trials: int, z: float) -> float:
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    centre = proportion + z * z / (2.0 * trials)
    radius = z * math.sqrt(proportion * (1.0 - proportion) / trials + z * z / (4.0 * trials * trials))
    return min(1.0, (centre + radius) / denominator)


def evaluate_planted_null_contamination_gate(
    rows: Sequence[Mapping[str, Any]],
    policy: AdaptiveNullPolicy,
    *,
    precommit_hash: str,
    adaptive_search_manifest_hash: str,
    planted_null_manifest_hash: str,
    locked_evaluator_hash: str,
) -> dict[str, Any]:
    """Bind adaptive planted-null outcomes and reject direct hash-parent leakage.

    Hash separation detects declared artifact-parent contamination only.  It is
    not proof against semantic copying, undisclosed channels, or mislabeled
    artifacts; those remain external audit obligations.
    """
    bindings = {
        "precommit_hash": _sha256(precommit_hash, "precommit_hash"),
        "adaptive_search_manifest_hash": _sha256(
            adaptive_search_manifest_hash, "adaptive_search_manifest_hash"
        ),
        "planted_null_manifest_hash": _sha256(
            planted_null_manifest_hash, "planted_null_manifest_hash"
        ),
        "locked_evaluator_hash": _sha256(locked_evaluator_hash, "locked_evaluator_hash"),
    }
    if len(set(bindings.values())) != len(bindings):
        raise CognitiveContractError("adaptive-null binding artifacts must have distinct hashes")
    if len(rows) < policy.min_trials:
        raise CognitiveContractError("planted-null evidence has fewer trials than precommitted")

    normalized: list[dict[str, Any]] = []
    seen_trials: set[str] = set()
    seen_seeds: set[int] = set()
    seen_null_draws: set[str] = set()
    for row in rows:
        trial_id = _identifier(row.get("trial_id"), "trial_id")
        if trial_id in seen_trials:
            raise CognitiveContractError(f"duplicate planted-null trial: {trial_id}")
        seen_trials.add(trial_id)
        seed = row.get("seed")
        if type(seed) is not int or seed in seen_seeds:
            raise CognitiveContractError("planted-null trials require unique integer seeds")
        seen_seeds.add(seed)
        planted_effect = _number(row.get("planted_effect"), "planted_effect")
        if planted_effect != 0.0:
            raise CognitiveContractError(f"trial {trial_id} is not a planted null")
        selected = row.get("selected")
        if type(selected) is not bool:
            raise CognitiveContractError(f"trial {trial_id} selected must be boolean")
        observed_delta = _number(row.get("observed_delta"), "observed_delta")
        null_draw_hash = _sha256(row.get("null_draw_hash"), "null_draw_hash")
        if null_draw_hash in seen_null_draws:
            raise CognitiveContractError("planted-null trials require distinct null draws")
        seen_null_draws.add(null_draw_hash)
        candidate_hash = _sha256(row.get("candidate_hash"), "candidate_hash")
        if null_draw_hash in bindings.values() or candidate_hash in {*bindings.values(), null_draw_hash}:
            raise CognitiveContractError(f"trial {trial_id} artifact roles must have distinct hashes")
        adaptation_raw = row.get("adaptation_parent_hashes")
        evaluation_raw = row.get("evaluation_parent_hashes")
        if not isinstance(adaptation_raw, (list, tuple)) or not isinstance(evaluation_raw, (list, tuple)):
            raise CognitiveContractError(f"trial {trial_id} must serialize adaptation/evaluation parents")
        adaptation_parents = tuple(_sha256(value, "adaptation parent") for value in adaptation_raw)
        evaluation_parents = tuple(_sha256(value, "evaluation parent") for value in evaluation_raw)
        if len(set(adaptation_parents)) != len(adaptation_parents) or len(set(evaluation_parents)) != len(evaluation_parents):
            raise CognitiveContractError(f"trial {trial_id} parent lists may not contain duplicates")
        forbidden_adaptation = {
            null_draw_hash,
            bindings["planted_null_manifest_hash"],
            bindings["locked_evaluator_hash"],
        }
        leaked = sorted(forbidden_adaptation.intersection(adaptation_parents))
        if leaked:
            raise CognitiveContractError(f"trial {trial_id} adaptation parents contain holdout/null artifacts")
        required_adaptation = {
            bindings["precommit_hash"],
            bindings["adaptive_search_manifest_hash"],
        }
        if not required_adaptation.issubset(adaptation_parents):
            raise CognitiveContractError(f"trial {trial_id} adaptation parents are incomplete")
        required_evaluation = {
            candidate_hash,
            null_draw_hash,
            bindings["precommit_hash"],
            bindings["planted_null_manifest_hash"],
            bindings["locked_evaluator_hash"],
        }
        if not required_evaluation.issubset(evaluation_parents):
            raise CognitiveContractError(f"trial {trial_id} evaluation parents are incomplete")
        normalized.append(
            {
                "trial_id": trial_id,
                "seed": seed,
                "planted_effect": planted_effect,
                "selected": selected,
                "observed_delta": observed_delta,
                "null_draw_hash": null_draw_hash,
                "candidate_hash": candidate_hash,
                "adaptation_parent_hashes": list(adaptation_parents),
                "evaluation_parent_hashes": list(evaluation_parents),
            }
        )

    for item in normalized:
        leaked_null_draws = sorted(set(item["adaptation_parent_hashes"]).intersection(seen_null_draws))
        if leaked_null_draws:
            raise CognitiveContractError(
                f"trial {item['trial_id']} adaptation parents contain a planted-null draw"
            )

    false_selections = sum(row["selected"] for row in normalized)
    rate = false_selections / len(normalized)
    upper = _wilson_upper(false_selections, len(normalized), policy.confidence_z)
    blockers: list[str] = []
    if rate > policy.max_false_selection_rate:
        blockers.append("observed planted-null false-selection rate exceeds threshold")
    if upper > policy.max_false_selection_rate:
        blockers.append("Wilson upper bound for planted-null false-selection exceeds threshold")
    normalized.sort(key=lambda item: item["trial_id"])
    policy_data = dataclasses.asdict(policy)
    return _receipt(
        {
            "status": VALIDATOR_STATUS,
            "verdict": "PASS" if not blockers else "FAIL",
            "lineage": LINEAGE["adaptive_null"],
            "bindings": bindings,
            "row_hash": sha256_json(normalized),
            "policy": policy_data,
            "policy_hash": sha256_json(policy_data),
            "trial_count": len(normalized),
            "false_selection_count": false_selections,
            "false_selection_rate": rate,
            "false_selection_wilson_upper": upper,
            "declared_parent_hash_separation": True,
            "limitations": (
                "hash-parent separation does not prove absence of semantic or undisclosed contamination"
            ),
            "blockers": blockers,
        }
    )


__all__ = [
    "AdaptiveNullPolicy",
    "CalibrationPolicy",
    "LINEAGE",
    "PairedEvidencePolicy",
    "RetentionPolicy",
    "evaluate_calibration_selective_gate",
    "evaluate_paired_repeated_seed_gate",
    "evaluate_planted_null_contamination_gate",
    "evaluate_retention_matrix",
    "score_open_stream_events",
    "validate_byte_exact_rollback",
    "validate_first_lock_movie",
    "validate_reveal_time_purged_splits",
]
