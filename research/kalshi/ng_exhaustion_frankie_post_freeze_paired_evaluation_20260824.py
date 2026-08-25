#!/usr/bin/env python3
"""Post-freeze paired evaluation for the October Frankie full-stack experiment.

This additive module is deliberately downstream of the blind run.  It opens the
Step-1 answer wall only after complete, immutable movies exist for exactly the
S135 control and the all-provisional-combined shadow lane on the same causal
prefix roster.  The resulting report is descriptive: it cannot promote a lane,
rewrite a first lock, test statistical significance, or claim predictive success.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
import statistics
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "NG_EXHAUSTION_FRANKIE_POST_FREEZE_PAIRED_EVALUATION_V1"
PRIMARY_TEST = "S135_CONTROL_VS_FULL_PROVISIONAL_COMBINED"


class ReconciliationError(ValueError):
    """A freeze, answer-wall, roster, or evaluation invariant failed closed."""


class LaneId(str, Enum):
    S135_CONTROL = "S135_CONTROL"
    FULL_PROVISIONAL_COMBINED = "FULL_PROVISIONAL_COMBINED"


class AnswerKind(str, Enum):
    D_TARGET = "D_TARGET"
    FALSE_CONTEXT = "FALSE_CONTEXT"
    STOPPED_CHAIN_CONTROL = "STOPPED_CHAIN_CONTROL"
    NEGATIVE_CONTROL = "NEGATIVE_CONTROL"


def _text(value: Any, field: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise ReconciliationError(f"{field} must be non-empty")
    return out


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ReconciliationError(f"{field} must be finite")
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ReconciliationError(f"{field} must be finite") from exc
    if not math.isfinite(out):
        raise ReconciliationError(f"{field} must be finite")
    return out


def _sha(value: Any, field: str) -> str:
    out = str(value or "").strip().lower()
    if len(out) != 64 or any(ch not in "0123456789abcdef" for ch in out):
        raise ReconciliationError(f"{field} must be lowercase SHA-256")
    return out


def _hash(value: Any) -> str:
    try:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode()
    except (TypeError, ValueError) as exc:
        raise ReconciliationError("receipt payload must be deterministic JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _candidate_ids(values: Sequence[Any]) -> tuple[str, ...]:
    items = tuple(_text(value, "candidate_id") for value in values)
    if len(items) != len(set(items)):
        raise ReconciliationError("candidate ids must be unique")
    return tuple(sorted(items))


@dataclass(frozen=True)
class ResourceUsage:
    provider_calls: float = 0.0
    input_tokens: float = 0.0
    output_tokens: float = 0.0
    provider_cost_usd: float = 0.0
    retrieval_queries: float = 0.0
    retrieval_bytes: float = 0.0
    retrieval_cost_usd: float = 0.0

    def validate(self) -> "ResourceUsage":
        for field in self.__dataclass_fields__:
            if _finite(getattr(self, field), field) < 0:
                raise ReconciliationError(f"{field} must be non-negative")
        return self

    def as_dict(self) -> dict[str, float]:
        self.validate()
        return {field: float(getattr(self, field)) for field in self.__dataclass_fields__}


def _sum_usage(items: Sequence[ResourceUsage]) -> ResourceUsage:
    return ResourceUsage(
        **{
            field: sum(float(getattr(item.validate(), field)) for item in items)
            for field in ResourceUsage.__dataclass_fields__
        }
    ).validate()


@dataclass(frozen=True)
class ComponentUsage:
    component_id: str
    usage: ResourceUsage

    def validate(self) -> "ComponentUsage":
        _text(self.component_id, "component_id")
        self.usage.validate()
        return self

    def payload(self) -> dict[str, Any]:
        self.validate()
        return {"component_id": self.component_id, "usage": self.usage.as_dict()}


@dataclass(frozen=True)
class FrozenLaneObservation:
    opportunity_id: str
    causal_cutoff: float
    causal_prefix_hash: str
    state_prefix_hash: str
    candidate_ids: tuple[str, ...]
    target_probability: float | None
    abstained: bool
    first_lock_id: str | None
    usage: ResourceUsage
    component_usage: tuple[ComponentUsage, ...]
    observation_hash: str

    @classmethod
    def create(
        cls,
        *,
        opportunity_id: str,
        causal_cutoff: Any,
        causal_prefix_hash: str,
        state_prefix_hash: str,
        candidate_ids: Sequence[str],
        target_probability: Any,
        abstained: bool,
        first_lock_id: str | None,
        usage: ResourceUsage,
        component_usage: Mapping[str, ResourceUsage],
    ) -> "FrozenLaneObservation":
        if not isinstance(abstained, bool):
            raise ReconciliationError("abstained must be boolean")
        candidates = _candidate_ids(candidate_ids)
        probability = (
            None
            if target_probability is None
            else _finite(target_probability, "target_probability")
        )
        if probability is not None and not 0 <= probability <= 1:
            raise ReconciliationError("target_probability must be within [0,1]")
        lock_id = None if first_lock_id is None else _text(first_lock_id, "first_lock_id")
        if abstained and (candidates or probability is not None or lock_id is not None):
            raise ReconciliationError("abstention cannot carry candidates, probability, or lock")
        if lock_id is not None and not candidates:
            raise ReconciliationError("a first lock requires at least one frozen candidate")
        if not isinstance(component_usage, Mapping):
            raise ReconciliationError("component_usage must be a mapping")
        components = tuple(
            ComponentUsage(_text(name, "component_id"), item.validate()).validate()
            for name, item in sorted(component_usage.items())
        )
        if len({item.component_id for item in components}) != len(components):
            raise ReconciliationError("component attribution ids must be unique")
        total = usage.validate()
        attributed = _sum_usage([item.usage for item in components])
        for field in ResourceUsage.__dataclass_fields__:
            if getattr(attributed, field) > getattr(total, field) + 1e-9:
                raise ReconciliationError("component attribution cannot exceed row usage")
        core = {
            "opportunity_id": _text(opportunity_id, "opportunity_id"),
            "causal_cutoff": _finite(causal_cutoff, "causal_cutoff"),
            "causal_prefix_hash": _sha(causal_prefix_hash, "causal_prefix_hash"),
            "state_prefix_hash": _sha(state_prefix_hash, "state_prefix_hash"),
            "candidate_ids": list(candidates),
            "target_probability": probability,
            "abstained": abstained,
            "first_lock_id": lock_id,
            "usage": total.as_dict(),
            "component_usage": [item.payload() for item in components],
        }
        return cls(
            core["opportunity_id"],
            core["causal_cutoff"],
            core["causal_prefix_hash"],
            core["state_prefix_hash"],
            candidates,
            probability,
            abstained,
            lock_id,
            total,
            components,
            _hash(core),
        )

    def identity(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "causal_cutoff": self.causal_cutoff,
            "causal_prefix_hash": self.causal_prefix_hash,
            "state_prefix_hash": self.state_prefix_hash,
        }

    def core(self) -> dict[str, Any]:
        return {
            **self.identity(),
            "candidate_ids": list(self.candidate_ids),
            "target_probability": self.target_probability,
            "abstained": self.abstained,
            "first_lock_id": self.first_lock_id,
            "usage": self.usage.as_dict(),
            "component_usage": [item.payload() for item in self.component_usage],
        }

    def validate(self) -> "FrozenLaneObservation":
        rebuilt = self.create(
            opportunity_id=self.opportunity_id,
            causal_cutoff=self.causal_cutoff,
            causal_prefix_hash=self.causal_prefix_hash,
            state_prefix_hash=self.state_prefix_hash,
            candidate_ids=self.candidate_ids,
            target_probability=self.target_probability,
            abstained=self.abstained,
            first_lock_id=self.first_lock_id,
            usage=self.usage,
            component_usage={item.component_id: item.usage for item in self.component_usage},
        )
        if rebuilt.observation_hash != self.observation_hash:
            raise ReconciliationError("lane observation hash mismatch")
        return self


@dataclass(frozen=True)
class FrozenLaneMovie:
    schema_version: str
    run_id: str
    lane: LaneId
    rows: tuple[FrozenLaneObservation, ...]
    expected_prefix_count: int
    complete: bool
    frozen_at: float
    authority: str
    can_promote: bool
    prefix_roster_hash: str
    first_lock_roster_hash: str
    movie_hash: str

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        lane: LaneId,
        rows: Sequence[FrozenLaneObservation],
        expected_prefix_count: int,
        complete: bool,
        frozen_at: Any,
    ) -> "FrozenLaneMovie":
        if not isinstance(lane, LaneId):
            raise ReconciliationError("lane must be an exact declared lane id")
        if type(expected_prefix_count) is not int or expected_prefix_count < 1:
            raise ReconciliationError("expected_prefix_count must be a positive integer")
        if not isinstance(complete, bool):
            raise ReconciliationError("complete must be boolean")
        frozen_rows = tuple(row.validate() for row in rows)
        if len(frozen_rows) > expected_prefix_count:
            raise ReconciliationError("movie contains more rows than its prefix contract")
        if complete and len(frozen_rows) != expected_prefix_count:
            raise ReconciliationError("complete movie does not contain its full prefix roster")
        identities = [row.identity() for row in frozen_rows]
        identity_keys = [
            (row.opportunity_id, row.causal_cutoff, row.causal_prefix_hash, row.state_prefix_hash)
            for row in frozen_rows
        ]
        if len(identity_keys) != len(set(identity_keys)):
            raise ReconciliationError("movie prefix identities must be unique")
        if any(
            frozen_rows[index].causal_cutoff > frozen_rows[index + 1].causal_cutoff
            for index in range(len(frozen_rows) - 1)
        ):
            raise ReconciliationError("movie rows must be in causal-cutoff order")
        locks: dict[str, tuple[float, str] | None] = {
            opportunity_id: None
            for opportunity_id in sorted({row.opportunity_id for row in frozen_rows})
        }
        for row in frozen_rows:
            if row.first_lock_id is None:
                continue
            if locks[row.opportunity_id] is not None:
                raise ReconciliationError("movie may freeze only one first lock per opportunity")
            locks[row.opportunity_id] = (row.causal_cutoff, row.first_lock_id)
        authority = (
            "S135_PRIMARY_AUTHORITY"
            if lane is LaneId.S135_CONTROL
            else "SHADOW_ONLY"
        )
        prefix_roster_hash = _hash(identities)
        first_lock_roster_hash = _hash(
            [
                {
                    "opportunity_id": opportunity_id,
                    "first_lock": locks[opportunity_id],
                }
                for opportunity_id in sorted(locks)
            ]
        )
        core = {
            "schema_version": SCHEMA_VERSION,
            "run_id": _text(run_id, "run_id"),
            "lane": lane.value,
            "row_hashes": [row.observation_hash for row in frozen_rows],
            "expected_prefix_count": expected_prefix_count,
            "complete": complete,
            "frozen_at": _finite(frozen_at, "frozen_at"),
            "authority": authority,
            "can_promote": False,
            "prefix_roster_hash": prefix_roster_hash,
            "first_lock_roster_hash": first_lock_roster_hash,
        }
        return cls(
            SCHEMA_VERSION,
            core["run_id"],
            lane,
            frozen_rows,
            expected_prefix_count,
            complete,
            core["frozen_at"],
            authority,
            False,
            prefix_roster_hash,
            first_lock_roster_hash,
            _hash(core),
        )

    def validate(self) -> "FrozenLaneMovie":
        rebuilt = self.create(
            run_id=self.run_id,
            lane=self.lane,
            rows=self.rows,
            expected_prefix_count=self.expected_prefix_count,
            complete=self.complete,
            frozen_at=self.frozen_at,
        )
        if self.schema_version != SCHEMA_VERSION:
            raise ReconciliationError("movie schema mismatch")
        if rebuilt != self:
            raise ReconciliationError("movie hash mismatch")
        return self


@dataclass(frozen=True)
class GlobalPairedFreezeReceipt:
    schema_version: str
    run_id: str
    control_movie_hash: str
    combined_movie_hash: str
    prefix_roster_hash: str
    opportunity_roster: tuple[str, ...]
    expected_prefix_count: int
    completed_at: float
    both_lanes_complete: bool
    step1_answer_access_allowed: bool
    comparison_allowed: bool
    primary_test: str
    promotion_authority: str
    receipt_hash: str

    def core(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "control_movie_hash": self.control_movie_hash,
            "combined_movie_hash": self.combined_movie_hash,
            "prefix_roster_hash": self.prefix_roster_hash,
            "opportunity_roster": list(self.opportunity_roster),
            "expected_prefix_count": self.expected_prefix_count,
            "completed_at": self.completed_at,
            "both_lanes_complete": self.both_lanes_complete,
            "step1_answer_access_allowed": self.step1_answer_access_allowed,
            "comparison_allowed": self.comparison_allowed,
            "primary_test": self.primary_test,
            "promotion_authority": self.promotion_authority,
        }

    def validate(self) -> "GlobalPairedFreezeReceipt":
        if self.schema_version != SCHEMA_VERSION:
            raise ReconciliationError("global freeze receipt schema mismatch")
        _text(self.run_id, "run_id")
        for field in ("control_movie_hash", "combined_movie_hash", "prefix_roster_hash"):
            _sha(getattr(self, field), field)
        if not self.opportunity_roster or len(set(self.opportunity_roster)) != len(self.opportunity_roster):
            raise ReconciliationError("global freeze opportunity roster must be unique and non-empty")
        if not (
            self.both_lanes_complete
            and self.step1_answer_access_allowed
            and self.comparison_allowed
        ):
            raise ReconciliationError("global freeze receipt is not complete")
        if self.primary_test != PRIMARY_TEST or self.promotion_authority != "NONE":
            raise ReconciliationError("global freeze authority contract drift")
        _finite(self.completed_at, "completed_at")
        if self.receipt_hash != _hash(self.core()):
            raise ReconciliationError("global freeze receipt hash mismatch")
        return self


def freeze_complete_pair(
    control: FrozenLaneMovie,
    combined: FrozenLaneMovie,
    *,
    completed_at: Any,
) -> GlobalPairedFreezeReceipt:
    control.validate()
    combined.validate()
    if control.lane is not LaneId.S135_CONTROL:
        raise ReconciliationError("control lane must be exactly S135_CONTROL")
    if combined.lane is not LaneId.FULL_PROVISIONAL_COMBINED:
        raise ReconciliationError("shadow lane must be exactly FULL_PROVISIONAL_COMBINED")
    if not control.complete or not combined.complete:
        raise ReconciliationError("both lane movies must be complete before global freeze")
    if control.run_id != combined.run_id:
        raise ReconciliationError("paired movies must share one run identity")
    if (
        control.expected_prefix_count != combined.expected_prefix_count
        or control.prefix_roster_hash != combined.prefix_roster_hash
    ):
        raise ReconciliationError("paired movies require an identical prefix roster")
    if [row.identity() for row in control.rows] != [row.identity() for row in combined.rows]:
        raise ReconciliationError("paired movies require identical prefix roster identities")
    completed = _finite(completed_at, "completed_at")
    if completed < max(control.frozen_at, combined.frozen_at):
        raise ReconciliationError("global freeze cannot complete before either movie freezes")
    opportunities = tuple(sorted({row.opportunity_id for row in control.rows}))
    core = {
        "schema_version": SCHEMA_VERSION,
        "run_id": control.run_id,
        "control_movie_hash": control.movie_hash,
        "combined_movie_hash": combined.movie_hash,
        "prefix_roster_hash": control.prefix_roster_hash,
        "opportunity_roster": list(opportunities),
        "expected_prefix_count": control.expected_prefix_count,
        "completed_at": completed,
        "both_lanes_complete": True,
        "step1_answer_access_allowed": True,
        "comparison_allowed": True,
        "primary_test": PRIMARY_TEST,
        "promotion_authority": "NONE",
    }
    return GlobalPairedFreezeReceipt(
        SCHEMA_VERSION,
        control.run_id,
        control.movie_hash,
        combined.movie_hash,
        control.prefix_roster_hash,
        opportunities,
        control.expected_prefix_count,
        completed,
        True,
        True,
        True,
        PRIMARY_TEST,
        "NONE",
        _hash(core),
    ).validate()


@dataclass(frozen=True)
class Step1Answer:
    opportunity_id: str
    kind: AnswerKind
    onset_at: float | None
    candidate_ids: tuple[str, ...]

    def validate(self) -> "Step1Answer":
        _text(self.opportunity_id, "answer opportunity_id")
        if not isinstance(self.kind, AnswerKind):
            raise ReconciliationError("answer kind is invalid")
        candidates = _candidate_ids(self.candidate_ids)
        if candidates != self.candidate_ids:
            raise ReconciliationError("answer candidate ids must be canonical")
        if self.kind is AnswerKind.D_TARGET:
            if self.onset_at is None or not candidates:
                raise ReconciliationError("D target answer requires onset and candidate ids")
            _finite(self.onset_at, "answer onset_at")
        elif self.onset_at is not None or candidates:
            raise ReconciliationError("control answers cannot carry target onset or candidate ids")
        return self

    def payload(self) -> dict[str, Any]:
        self.validate()
        return {
            "opportunity_id": self.opportunity_id,
            "kind": self.kind.value,
            "onset_at": self.onset_at,
            "candidate_ids": list(self.candidate_ids),
        }


@dataclass(frozen=True)
class RevealedStep1Answers:
    schema_version: str
    run_id: str
    global_freeze_receipt_hash: str
    answers: tuple[Step1Answer, ...]
    revealed_at: float
    answer_key_hash: str
    access_receipt_hash: str

    def validate(self) -> "RevealedStep1Answers":
        if self.schema_version != SCHEMA_VERSION:
            raise ReconciliationError("revealed answer schema mismatch")
        _text(self.run_id, "run_id")
        _sha(self.global_freeze_receipt_hash, "global_freeze_receipt_hash")
        items = tuple(answer.validate() for answer in self.answers)
        if not items or len({item.opportunity_id for item in items}) != len(items):
            raise ReconciliationError("revealed answers require unique opportunities")
        payload = [answer.payload() for answer in items]
        if self.answer_key_hash != _hash(payload):
            raise ReconciliationError("Step-1 answer key hash mismatch")
        core = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "global_freeze_receipt_hash": self.global_freeze_receipt_hash,
            "answer_key_hash": self.answer_key_hash,
            "revealed_at": _finite(self.revealed_at, "revealed_at"),
            "access_mode": "POST_GLOBAL_FREEZE_ONLY",
        }
        if self.access_receipt_hash != _hash(core):
            raise ReconciliationError("Step-1 answer access receipt hash mismatch")
        return self


def reveal_step1_answers(
    freeze_receipt: GlobalPairedFreezeReceipt | None,
    answers: Sequence[Step1Answer],
    *,
    revealed_at: Any,
) -> RevealedStep1Answers:
    if not isinstance(freeze_receipt, GlobalPairedFreezeReceipt):
        raise ReconciliationError("global paired freeze receipt is required before Step-1 access")
    receipt = freeze_receipt.validate()
    reveal_time = _finite(revealed_at, "revealed_at")
    if reveal_time < receipt.completed_at:
        raise ReconciliationError("Step-1 access must occur after global freeze")
    items = tuple(answer.validate() for answer in answers)
    roster = tuple(sorted(answer.opportunity_id for answer in items))
    if roster != receipt.opportunity_roster:
        raise ReconciliationError("Step-1 answer roster must equal the frozen opportunity roster")
    answer_hash = _hash([answer.payload() for answer in items])
    core = {
        "schema_version": SCHEMA_VERSION,
        "run_id": receipt.run_id,
        "global_freeze_receipt_hash": receipt.receipt_hash,
        "answer_key_hash": answer_hash,
        "revealed_at": reveal_time,
        "access_mode": "POST_GLOBAL_FREEZE_ONLY",
    }
    return RevealedStep1Answers(
        SCHEMA_VERSION,
        receipt.run_id,
        receipt.receipt_hash,
        items,
        reveal_time,
        answer_hash,
        _hash(core),
    ).validate()


@dataclass(frozen=True)
class EvaluationPolicy:
    early_onset_window_seconds: float
    confidence_z: float = 1.96
    calibration_bins: int = 10
    log_loss_epsilon: float = 1e-15

    def validate(self) -> "EvaluationPolicy":
        if _finite(self.early_onset_window_seconds, "early_onset_window_seconds") < 0:
            raise ReconciliationError("early onset window must be non-negative")
        if _finite(self.confidence_z, "confidence_z") <= 0:
            raise ReconciliationError("confidence_z must be positive")
        if type(self.calibration_bins) is not int or self.calibration_bins < 2:
            raise ReconciliationError("calibration_bins must be an integer >= 2")
        epsilon = _finite(self.log_loss_epsilon, "log_loss_epsilon")
        if not 0 < epsilon < 0.5:
            raise ReconciliationError("log_loss_epsilon must lie within (0,0.5)")
        return self

    def payload(self) -> dict[str, Any]:
        self.validate()
        return {
            "early_onset_window_seconds": self.early_onset_window_seconds,
            "confidence_z": self.confidence_z,
            "calibration_bins": self.calibration_bins,
            "log_loss_epsilon": self.log_loss_epsilon,
        }


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _probability_metrics(
    probabilities: Sequence[tuple[float, int]], policy: EvaluationPolicy
) -> dict[str, Any]:
    if not probabilities:
        return {
            "status": "NO_LAWFUL_PROBABILITIES",
            "brier_score": None,
            "log_loss": None,
            "calibration": {"status": "UNAVAILABLE", "bins": [], "ece": None},
        }
    brier = statistics.fmean((probability - label) ** 2 for probability, label in probabilities)
    clipped = [
        (min(1 - policy.log_loss_epsilon, max(policy.log_loss_epsilon, probability)), label)
        for probability, label in probabilities
    ]
    log_loss = statistics.fmean(
        -(label * math.log(probability) + (1 - label) * math.log(1 - probability))
        for probability, label in clipped
    )
    bins: list[dict[str, Any]] = []
    ece = 0.0
    for index in range(policy.calibration_bins):
        members = [
            (probability, label)
            for probability, label in probabilities
            if min(policy.calibration_bins - 1, int(probability * policy.calibration_bins)) == index
        ]
        if not members:
            continue
        forecast = statistics.fmean(item[0] for item in members)
        observed = statistics.fmean(item[1] for item in members)
        ece += len(members) / len(probabilities) * abs(forecast - observed)
        bins.append(
            {
                "lower": index / policy.calibration_bins,
                "upper": (index + 1) / policy.calibration_bins,
                "n": len(members),
                "mean_forecast": forecast,
                "observed_rate": observed,
            }
        )
    return {
        "status": "DESCRIPTIVE_ONLY",
        "brier_score": brier,
        "log_loss": log_loss,
        "calibration": {"status": "DESCRIPTIVE_ONLY", "bins": bins, "ece": ece},
    }


def _group_rows(movie: FrozenLaneMovie) -> dict[str, list[FrozenLaneObservation]]:
    grouped: dict[str, list[FrozenLaneObservation]] = {}
    for row in movie.rows:
        grouped.setdefault(row.opportunity_id, []).append(row)
    return grouped


def _lane_metrics(
    movie: FrozenLaneMovie,
    answers: Mapping[str, Step1Answer],
    policy: EvaluationPolicy,
) -> tuple[dict[str, Any], dict[str, dict[str, float]]]:
    grouped = _group_rows(movie)
    tp = fp = fn = 0
    target_count = 0
    timing: list[float] = []
    pre = early = late = missed = 0
    controls: dict[str, dict[str, int]] = {
        kind.value: {"cases": 0, "detections": 0}
        for kind in (
            AnswerKind.FALSE_CONTEXT,
            AnswerKind.STOPPED_CHAIN_CONTROL,
            AnswerKind.NEGATIVE_CONTROL,
        )
    }
    probability_rows: list[tuple[float, int]] = []
    case_values: dict[str, dict[str, float]] = {
        name: {}
        for name in (
            "target_detection_rate",
            "target_candidate_recall",
            "target_candidate_precision",
            "first_detection_seconds_vs_onset",
            "pre_onset_detection_rate",
            "early_onset_detection_rate",
            "brier_loss",
            "log_loss",
            "probability_coverage",
            "anchor_abstention",
            "false_context_detection_rate",
            "stopped_chain_detection_rate",
            "negative_control_detection_rate",
            "provider_cost_usd",
            "retrieval_cost_usd",
        )
    }
    anchor_abstentions = 0
    for opportunity_id, answer in answers.items():
        rows = grouped[opportunity_id]
        predicted = set().union(*(set(row.candidate_ids) for row in rows))
        actual = set(answer.candidate_ids)
        matched = predicted & actual
        tp += len(matched)
        fp += len(predicted - actual)
        fn += len(actual - predicted)
        total_usage = _sum_usage([row.usage for row in rows])
        case_values["provider_cost_usd"][opportunity_id] = total_usage.provider_cost_usd
        case_values["retrieval_cost_usd"][opportunity_id] = total_usage.retrieval_cost_usd

        if answer.kind is AnswerKind.D_TARGET:
            target_count += 1
            detected = bool(matched)
            case_values["target_detection_rate"][opportunity_id] = float(detected)
            case_values["target_candidate_recall"][opportunity_id] = len(matched) / len(actual)
            if predicted:
                case_values["target_candidate_precision"][opportunity_id] = len(matched) / len(predicted)
            matching_rows = [row for row in rows if set(row.candidate_ids) & actual]
            if matching_rows:
                first = min(row.causal_cutoff for row in matching_rows)
                delta = first - float(answer.onset_at)
                timing.append(delta)
                case_values["first_detection_seconds_vs_onset"][opportunity_id] = delta
                is_pre = delta < 0
                is_early = 0 <= delta <= policy.early_onset_window_seconds
                pre += int(is_pre)
                early += int(is_early)
                late += int(delta > policy.early_onset_window_seconds)
                case_values["pre_onset_detection_rate"][opportunity_id] = float(is_pre)
                case_values["early_onset_detection_rate"][opportunity_id] = float(is_early)
            else:
                missed += 1
                case_values["pre_onset_detection_rate"][opportunity_id] = 0.0
                case_values["early_onset_detection_rate"][opportunity_id] = 0.0
            eligible = [row for row in rows if row.causal_cutoff < float(answer.onset_at)]
        else:
            control = controls[answer.kind.value]
            control["cases"] += 1
            control["detections"] += int(bool(predicted))
            metric_name = {
                AnswerKind.FALSE_CONTEXT: "false_context_detection_rate",
                AnswerKind.STOPPED_CHAIN_CONTROL: "stopped_chain_detection_rate",
                AnswerKind.NEGATIVE_CONTROL: "negative_control_detection_rate",
            }[answer.kind]
            case_values[metric_name][opportunity_id] = float(bool(predicted))
            eligible = rows

        anchor = eligible[-1] if eligible else None
        label = 1 if answer.kind is AnswerKind.D_TARGET else 0
        has_probability = bool(
            anchor is not None
            and not anchor.abstained
            and anchor.target_probability is not None
        )
        case_values["probability_coverage"][opportunity_id] = float(has_probability)
        case_values["anchor_abstention"][opportunity_id] = float(not has_probability)
        anchor_abstentions += int(not has_probability)
        if has_probability and anchor is not None and anchor.target_probability is not None:
            probability = anchor.target_probability
            brier = (probability - label) ** 2
            clipped = min(1 - policy.log_loss_epsilon, max(policy.log_loss_epsilon, probability))
            loss = -(label * math.log(clipped) + (1 - label) * math.log(1 - clipped))
            probability_rows.append((probability, label))
            case_values["brier_loss"][opportunity_id] = brier
            case_values["log_loss"][opportunity_id] = loss

    probability_metrics = _probability_metrics(probability_rows, policy)
    total_usage = _sum_usage([row.usage for row in movie.rows])
    prefix_abstentions = sum(int(row.abstained) for row in movie.rows)
    opportunity_abstentions = sum(
        int(all(row.abstained for row in rows)) for rows in grouped.values()
    )
    for control in controls.values():
        control["detection_rate"] = _safe_ratio(control["detections"], control["cases"])
    metrics = {
        "recognition": {
            "candidate_matches": tp,
            "predicted_candidates": tp + fp,
            "answer_candidates": tp + fn,
            "false_positive_candidates": fp,
            "missed_candidates": fn,
            "recall": _safe_ratio(tp, tp + fn),
            "precision": _safe_ratio(tp, tp + fp),
        },
        "timing": {
            "target_cases": target_count,
            "detected_targets": len(timing),
            "missed_targets": missed,
            "first_detection_seconds_vs_onset": timing,
            "mean_seconds_vs_onset": None if not timing else statistics.fmean(timing),
            "median_seconds_vs_onset": None if not timing else statistics.median(timing),
            "pre_onset_detections": pre,
            "early_onset_detections": early,
            "late_onset_detections": late,
            "early_onset_window_seconds": policy.early_onset_window_seconds,
            "sign_convention": "NEGATIVE_IS_LEAD_POSITIVE_IS_LAG",
        },
        "prediction": {
            **probability_metrics,
            "lawful_probability_opportunities": len(probability_rows),
            "eligible_opportunities": len(answers),
            "coverage": len(probability_rows) / len(answers),
            "abstentions_or_missing": anchor_abstentions,
            "anchor_rule": "LAST_FROZEN_PRE_ONSET_PREFIX_FOR_TARGET_ELSE_LAST_FROZEN_PREFIX",
        },
        "coverage": {
            "prefix_rows": len(movie.rows),
            "prefix_abstentions": prefix_abstentions,
            "prefix_coverage": 1 - prefix_abstentions / len(movie.rows),
            "opportunities": len(grouped),
            "opportunity_abstentions": opportunity_abstentions,
            "opportunity_coverage": 1 - opportunity_abstentions / len(grouped),
        },
        "controls": controls,
        "cost": total_usage.as_dict(),
    }
    return metrics, case_values


def _paired_delta(
    control: Mapping[str, float],
    combined: Mapping[str, float],
    *,
    confidence_z: float,
) -> dict[str, Any]:
    keys = sorted(set(control) & set(combined))
    differences = [combined[key] - control[key] for key in keys]
    if not differences:
        return {
            "estimate_combined_minus_control": None,
            "standard_error": None,
            "interval_low": None,
            "interval_high": None,
            "n_pairs": 0,
            "uncertainty_method": "UNAVAILABLE_NO_LAWFUL_PAIRS",
        }
    estimate = statistics.fmean(differences)
    standard_error = (
        None
        if len(differences) < 2
        else statistics.stdev(differences) / math.sqrt(len(differences))
    )
    return {
        "estimate_combined_minus_control": estimate,
        "standard_error": standard_error,
        "interval_low": None if standard_error is None else estimate - confidence_z * standard_error,
        "interval_high": None if standard_error is None else estimate + confidence_z * standard_error,
        "n_pairs": len(differences),
        "uncertainty_method": (
            "SINGLE_PAIR_NO_INTERVAL"
            if standard_error is None
            else "CASE_CLUSTERED_NORMAL_INTERVAL_DESCRIPTIVE_ONLY"
        ),
    }


def _component_telemetry(movie: FrozenLaneMovie) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[ResourceUsage]] = {}
    for row in movie.rows:
        for item in row.component_usage:
            grouped.setdefault(item.component_id, []).append(item.usage)
    return {name: _sum_usage(items).as_dict() for name, items in sorted(grouped.items())}


@dataclass(frozen=True)
class PostRevealMetaLoopObservation:
    opportunity_id: str
    executed_at: float
    candidate_ids: tuple[str, ...]
    target_probability: float | None
    abstained: bool
    observed_frozen_first_lock_id: str | None
    rewrites_frozen_first_lock: bool
    usage: ResourceUsage
    observation_hash: str

    @classmethod
    def create(
        cls,
        *,
        opportunity_id: str,
        executed_at: Any,
        candidate_ids: Sequence[str],
        target_probability: Any,
        abstained: bool,
        observed_frozen_first_lock_id: str | None,
        rewrites_frozen_first_lock: bool,
        usage: ResourceUsage,
    ) -> "PostRevealMetaLoopObservation":
        if not isinstance(abstained, bool) or not isinstance(rewrites_frozen_first_lock, bool):
            raise ReconciliationError("meta-loop state flags must be boolean")
        candidates = _candidate_ids(candidate_ids)
        probability = None if target_probability is None else _finite(target_probability, "target_probability")
        if probability is not None and not 0 <= probability <= 1:
            raise ReconciliationError("target_probability must be within [0,1]")
        lock_id = (
            None
            if observed_frozen_first_lock_id is None
            else _text(observed_frozen_first_lock_id, "observed_frozen_first_lock_id")
        )
        if abstained and (candidates or probability is not None):
            raise ReconciliationError("meta-loop abstention cannot carry predictions")
        if rewrites_frozen_first_lock:
            raise ReconciliationError("post-reveal meta-loop cannot rewrite frozen shadow first lock")
        total = usage.validate()
        core = {
            "opportunity_id": _text(opportunity_id, "opportunity_id"),
            "executed_at": _finite(executed_at, "executed_at"),
            "candidate_ids": list(candidates),
            "target_probability": probability,
            "abstained": abstained,
            "observed_frozen_first_lock_id": lock_id,
            "rewrites_frozen_first_lock": False,
            "usage": total.as_dict(),
        }
        return cls(
            core["opportunity_id"],
            core["executed_at"],
            candidates,
            probability,
            abstained,
            lock_id,
            False,
            total,
            _hash(core),
        )

    def validate(self) -> "PostRevealMetaLoopObservation":
        rebuilt = self.create(
            opportunity_id=self.opportunity_id,
            executed_at=self.executed_at,
            candidate_ids=self.candidate_ids,
            target_probability=self.target_probability,
            abstained=self.abstained,
            observed_frozen_first_lock_id=self.observed_frozen_first_lock_id,
            rewrites_frozen_first_lock=self.rewrites_frozen_first_lock,
            usage=self.usage,
        )
        if rebuilt.observation_hash != self.observation_hash:
            raise ReconciliationError("meta-loop observation hash mismatch")
        return self


@dataclass(frozen=True)
class PostRevealMetaLoopMovie:
    schema_version: str
    run_id: str
    source_shadow_movie_hash: str
    frozen_shadow_first_lock_roster_hash: str
    observations: tuple[PostRevealMetaLoopObservation, ...]
    expected_opportunity_count: int
    complete: bool
    authority: str
    movie_hash: str

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        source_shadow_movie_hash: str,
        frozen_shadow_first_lock_roster_hash: str,
        observations: Sequence[PostRevealMetaLoopObservation],
        expected_opportunity_count: int,
        complete: bool,
    ) -> "PostRevealMetaLoopMovie":
        if type(expected_opportunity_count) is not int or expected_opportunity_count < 1:
            raise ReconciliationError("expected_opportunity_count must be positive")
        if not isinstance(complete, bool):
            raise ReconciliationError("meta-loop complete must be boolean")
        items = tuple(item.validate() for item in observations)
        if len({item.opportunity_id for item in items}) != len(items):
            raise ReconciliationError("meta-loop opportunity ids must be unique")
        if complete and len(items) != expected_opportunity_count:
            raise ReconciliationError("complete meta-loop movie has an incomplete roster")
        core = {
            "schema_version": SCHEMA_VERSION,
            "run_id": _text(run_id, "run_id"),
            "source_shadow_movie_hash": _sha(source_shadow_movie_hash, "source_shadow_movie_hash"),
            "frozen_shadow_first_lock_roster_hash": _sha(
                frozen_shadow_first_lock_roster_hash,
                "frozen_shadow_first_lock_roster_hash",
            ),
            "observation_hashes": [item.observation_hash for item in items],
            "expected_opportunity_count": expected_opportunity_count,
            "complete": complete,
            "authority": "POST_REVEAL_DIAGNOSTIC_ONLY",
        }
        return cls(
            SCHEMA_VERSION,
            core["run_id"],
            core["source_shadow_movie_hash"],
            core["frozen_shadow_first_lock_roster_hash"],
            items,
            expected_opportunity_count,
            complete,
            "POST_REVEAL_DIAGNOSTIC_ONLY",
            _hash(core),
        )

    def validate(self) -> "PostRevealMetaLoopMovie":
        rebuilt = self.create(
            run_id=self.run_id,
            source_shadow_movie_hash=self.source_shadow_movie_hash,
            frozen_shadow_first_lock_roster_hash=self.frozen_shadow_first_lock_roster_hash,
            observations=self.observations,
            expected_opportunity_count=self.expected_opportunity_count,
            complete=self.complete,
        )
        if self.schema_version != SCHEMA_VERSION or rebuilt != self:
            raise ReconciliationError("meta-loop movie hash mismatch")
        return self


def _first_lock_map(movie: FrozenLaneMovie) -> dict[str, str | None]:
    out = {row.opportunity_id: None for row in movie.rows}
    for row in movie.rows:
        if row.first_lock_id is not None:
            out[row.opportunity_id] = row.first_lock_id
    return out


def _score_meta_loop(
    meta: PostRevealMetaLoopMovie,
    combined: FrozenLaneMovie,
    answers: RevealedStep1Answers,
    policy: EvaluationPolicy,
) -> dict[str, Any]:
    meta.validate()
    if not meta.complete:
        raise ReconciliationError("post-reveal meta-loop movie must be complete")
    if meta.run_id != combined.run_id or meta.source_shadow_movie_hash != combined.movie_hash:
        raise ReconciliationError("meta-loop must bind the frozen combined shadow movie")
    if meta.frozen_shadow_first_lock_roster_hash != combined.first_lock_roster_hash:
        raise ReconciliationError("meta-loop first-lock roster hash mismatch")
    for row in meta.observations:
        if row.executed_at < answers.revealed_at:
            raise ReconciliationError("meta-loop execution is allowed only after Step-1 reveal")
    roster = tuple(sorted(row.opportunity_id for row in meta.observations))
    answer_by_id = {answer.opportunity_id: answer for answer in answers.answers}
    if roster != tuple(sorted(answer_by_id)):
        raise ReconciliationError("meta-loop must cover the frozen opportunity roster")
    locks = _first_lock_map(combined)
    for row in meta.observations:
        if row.observed_frozen_first_lock_id != locks[row.opportunity_id]:
            raise ReconciliationError("meta-loop attempted frozen first-lock substitution")

    tp = fp = fn = 0
    probabilities: list[tuple[float, int]] = []
    abstentions = 0
    for row in meta.observations:
        answer = answer_by_id[row.opportunity_id]
        actual = set(answer.candidate_ids)
        predicted = set(row.candidate_ids)
        tp += len(actual & predicted)
        fp += len(predicted - actual)
        fn += len(actual - predicted)
        abstentions += int(row.abstained)
        if not row.abstained and row.target_probability is not None:
            probabilities.append(
                (row.target_probability, int(answer.kind is AnswerKind.D_TARGET))
            )
    return {
        "authority": "POST_REVEAL_DIAGNOSTIC_ONLY",
        "predictive_evidence": False,
        "source_shadow_movie_hash": combined.movie_hash,
        "frozen_shadow_first_lock_roster_hash": combined.first_lock_roster_hash,
        "recognition": {
            "candidate_matches": tp,
            "recall": _safe_ratio(tp, tp + fn),
            "precision": _safe_ratio(tp, tp + fp),
        },
        "post_reveal_probability_diagnostics": _probability_metrics(probabilities, policy),
        "coverage": {
            "opportunities": len(meta.observations),
            "abstentions": abstentions,
            "coverage": 1 - abstentions / len(meta.observations),
        },
        "cost": _sum_usage([row.usage for row in meta.observations]).as_dict(),
        "included_in_primary_paired_deltas": False,
        "movie_hash": meta.movie_hash,
    }


def evaluate_frozen_pair(
    control: FrozenLaneMovie,
    combined: FrozenLaneMovie,
    freeze_receipt: GlobalPairedFreezeReceipt,
    revealed_answers: RevealedStep1Answers,
    *,
    policy: EvaluationPolicy,
    meta_loop: PostRevealMetaLoopMovie | None = None,
) -> dict[str, Any]:
    """Reconcile one immutable paired roster after the answer wall opens."""
    policy.validate()
    control.validate()
    combined.validate()
    receipt = freeze_receipt.validate()
    revealed = revealed_answers.validate()
    if control.lane is not LaneId.S135_CONTROL or combined.lane is not LaneId.FULL_PROVISIONAL_COMBINED:
        raise ReconciliationError("primary evaluation accepts only the corrected paired lanes")
    if (
        receipt.control_movie_hash != control.movie_hash
        or receipt.combined_movie_hash != combined.movie_hash
        or receipt.prefix_roster_hash != control.prefix_roster_hash
    ):
        raise ReconciliationError("paired movies do not match the global freeze receipt")
    if combined.prefix_roster_hash != control.prefix_roster_hash:
        raise ReconciliationError("evaluation requires identical prefix roster hashes")
    if revealed.global_freeze_receipt_hash != receipt.receipt_hash:
        raise ReconciliationError("Step-1 answers are not bound to this global freeze")
    if revealed.run_id != receipt.run_id or control.run_id != receipt.run_id or combined.run_id != receipt.run_id:
        raise ReconciliationError("paired evaluation run identity mismatch")
    if revealed.revealed_at < receipt.completed_at:
        raise ReconciliationError("comparison and Step-1 use are prohibited before global freeze")
    answer_by_id = {answer.opportunity_id: answer for answer in revealed.answers}
    if tuple(sorted(answer_by_id)) != receipt.opportunity_roster:
        raise ReconciliationError("revealed answer roster differs from frozen opportunities")

    control_metrics, control_cases = _lane_metrics(control, answer_by_id, policy)
    combined_metrics, combined_cases = _lane_metrics(combined, answer_by_id, policy)
    delta_names = (
        "target_detection_rate",
        "target_candidate_recall",
        "target_candidate_precision",
        "first_detection_seconds_vs_onset",
        "pre_onset_detection_rate",
        "early_onset_detection_rate",
        "brier_loss",
        "log_loss",
        "probability_coverage",
        "anchor_abstention",
        "false_context_detection_rate",
        "stopped_chain_detection_rate",
        "negative_control_detection_rate",
        "provider_cost_usd",
        "retrieval_cost_usd",
    )
    deltas = {
        name: _paired_delta(
            control_cases[name], combined_cases[name], confidence_z=policy.confidence_z
        )
        for name in delta_names
    }
    events = [
        {
            "event": "PAIRED_GLOBAL_FREEZE_VERIFIED",
            "run_id": receipt.run_id,
            "freeze_receipt_hash": receipt.receipt_hash,
            "prefix_count": receipt.expected_prefix_count,
        },
        {
            "event": "STEP1_ANSWERS_ACCESSED_POST_FREEZE",
            "run_id": receipt.run_id,
            "answer_access_receipt_hash": revealed.access_receipt_hash,
            "opportunity_count": len(answer_by_id),
        },
        {
            "event": "PAIRED_LANE_EVALUATION_COMPLETED",
            "run_id": receipt.run_id,
            "primary_test": PRIMARY_TEST,
            "paired_metric_count": len(deltas),
        },
    ]
    meta_result = None
    if meta_loop is not None:
        meta_result = _score_meta_loop(meta_loop, combined, revealed, policy)
        events.append(
            {
                "event": "POST_REVEAL_META_LOOP_SCORED_SEPARATELY",
                "run_id": receipt.run_id,
                "meta_loop_movie_hash": meta_loop.movie_hash,
                "included_in_primary_paired_deltas": False,
            }
        )
    core = {
        "schema_version": SCHEMA_VERSION,
        "run_id": receipt.run_id,
        "comparison": {
            "control_lane": LaneId.S135_CONTROL.value,
            "combined_lane": LaneId.FULL_PROVISIONAL_COMBINED.value,
            "primary_test": PRIMARY_TEST,
        },
        "freeze_receipt_hash": receipt.receipt_hash,
        "answer_access_receipt_hash": revealed.access_receipt_hash,
        "policy": policy.payload(),
        "lanes": {
            LaneId.S135_CONTROL.value: control_metrics,
            LaneId.FULL_PROVISIONAL_COMBINED.value: combined_metrics,
        },
        "paired_deltas": deltas,
        "component_telemetry": {
            LaneId.S135_CONTROL.value: _component_telemetry(control),
            LaneId.FULL_PROVISIONAL_COMBINED.value: _component_telemetry(combined),
            "interpretation": "COST_ATTRIBUTION_ONLY_NOT_COMPONENT_ABLATIONS",
        },
        "meta_loop": meta_result,
        "events": events,
        "promotion_authority": "NONE",
        "automatic_promotion": False,
        "significance_claim": "NOT_TESTED",
        "predictive_success_claim": "NOT_MADE",
        "interpretation": "DESCRIPTIVE_PAIRED_RECONCILIATION_ONLY",
    }
    return {**core, "report_hash": _hash(core)}


__all__ = [
    "AnswerKind",
    "EvaluationPolicy",
    "FrozenLaneMovie",
    "FrozenLaneObservation",
    "GlobalPairedFreezeReceipt",
    "LaneId",
    "PostRevealMetaLoopMovie",
    "PostRevealMetaLoopObservation",
    "ReconciliationError",
    "ResourceUsage",
    "RevealedStep1Answers",
    "Step1Answer",
    "evaluate_frozen_pair",
    "freeze_complete_pair",
    "reveal_step1_answers",
]
