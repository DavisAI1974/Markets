#!/usr/bin/env python3
"""Isolated, fail-closed mechanics for NG Exhaustion V4.

This module is infrastructure only. It does not launch V4, mutate the frozen detector,
canonical evidence, runway clock, permanent Frankie, Frankie 1, or spawn.py.

It closes mechanical contracts for:
- multi-clock availability and explicit missingness;
- immutable causal state-movie rows;
- prospective predecessor lifecycle;
- append-only probability movie and independently recomputable first lock;
- immutable lane registry identity;
- sealed prediction-to-execution handoff.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Iterable, Mapping, Sequence

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SCHEMA_VERSION = "NG_EXHAUSTION_V4_MECHANICS_V1"
GENESIS = "0" * 64


class V4ContractError(ValueError):
    pass


def _id(v: Any, field: str) -> str:
    x = str(v or "").strip()
    if not x:
        raise V4ContractError(f"{field} must be non-empty")
    return x


def _sha(v: Any, field: str) -> str:
    x = str(v or "").strip().lower()
    if not SHA256_RE.fullmatch(x):
        raise V4ContractError(f"{field} must be lowercase SHA-256")
    return x


def _finite(v: Any, field: str) -> float:
    if isinstance(v, bool):
        raise V4ContractError(f"{field} must be finite")
    try:
        x = float(v)
    except (TypeError, ValueError, OverflowError) as exc:
        raise V4ContractError(f"{field} must be finite") from exc
    if not math.isfinite(x):
        raise V4ContractError(f"{field} must be finite")
    return x


def _prob(v: Any, field: str) -> float:
    x = _finite(v, field)
    if not 0.0 <= x <= 1.0:
        raise V4ContractError(f"{field} must be within [0,1]")
    return x


def stable_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


class Missingness(str, Enum):
    OBSERVED = "OBSERVED"
    PAST_CARRY = "PAST_CARRY"
    STALE = "STALE"
    MISSING = "MISSING"
    STRUCTURALLY_NOT_YET_KNOWN = "STRUCTURALLY_NOT_YET_KNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class CausalField:
    name: str
    status: Missingness
    value: Any
    source_ts_event: float | None
    source_ts_recv: float | None
    feature_available_at: float
    source_identity_sha256: str
    age_seconds: float | None = None

    def validate(self, *, cutoff: float) -> "CausalField":
        _id(self.name, "name")
        _sha(self.source_identity_sha256, "source_identity_sha256")
        cut = _finite(cutoff, "cutoff")
        avail = _finite(self.feature_available_at, "feature_available_at")
        if avail > cut:
            raise V4ContractError(f"field {self.name} is not yet lawfully available")
        for field_name, value in (("source_ts_event", self.source_ts_event), ("source_ts_recv", self.source_ts_recv)):
            if value is not None:
                ts = _finite(value, field_name)
                if ts > avail:
                    raise V4ContractError(f"{field_name} cannot exceed feature_available_at")
        if self.age_seconds is not None and _finite(self.age_seconds, "age_seconds") < 0:
            raise V4ContractError("age_seconds cannot be negative")
        absent = {Missingness.MISSING, Missingness.STRUCTURALLY_NOT_YET_KNOWN, Missingness.NOT_APPLICABLE}
        if self.status in absent and self.value is not None:
            raise V4ContractError(f"{self.status.value} field must carry value=None")
        if self.status == Missingness.OBSERVED and self.source_ts_recv is None:
            raise V4ContractError("OBSERVED requires source_ts_recv")
        if self.status in {Missingness.PAST_CARRY, Missingness.STALE}:
            if self.source_ts_recv is None or self.age_seconds is None:
                raise V4ContractError(f"{self.status.value} requires source_ts_recv and age_seconds")
        return self


@dataclass(frozen=True)
class StateMovieRow:
    instance_id: str
    causal_second: float
    event_known_by: float
    fields: tuple[CausalField, ...]
    source_manifest_sha256: str
    transform_sha256: str
    prior_row_hash: str = GENESIS
    row_hash: str = ""

    def core(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "instance_id": self.instance_id,
            "causal_second": self.causal_second,
            "event_known_by": self.event_known_by,
            "fields": [
                {**asdict(f), "status": f.status.value}
                for f in self.fields
            ],
            "source_manifest_sha256": self.source_manifest_sha256,
            "transform_sha256": self.transform_sha256,
            "prior_row_hash": self.prior_row_hash,
        }

    def validate(self) -> "StateMovieRow":
        _id(self.instance_id, "instance_id")
        second = _finite(self.causal_second, "causal_second")
        known = _finite(self.event_known_by, "event_known_by")
        if second < known:
            raise V4ContractError("state row cannot precede event_known_by")
        _sha(self.source_manifest_sha256, "source_manifest_sha256")
        _sha(self.transform_sha256, "transform_sha256")
        _sha(self.prior_row_hash, "prior_row_hash")
        names = [f.name for f in self.fields]
        if len(names) != len(set(names)):
            raise V4ContractError("duplicate field names in state row")
        for f in self.fields:
            f.validate(cutoff=second)
        expected = stable_hash(self.core())
        if self.row_hash and self.row_hash != expected:
            raise V4ContractError("state row hash mismatch")
        return self


def make_state_row(**kwargs: Any) -> StateMovieRow:
    row = StateMovieRow(**kwargs)
    row.validate()
    return StateMovieRow(**{**asdict(row), "fields": row.fields, "row_hash": stable_hash(row.core())}).validate()


def validate_state_movie(rows: Sequence[StateMovieRow]) -> str:
    if not rows:
        raise V4ContractError("state movie cannot be empty")
    instance = rows[0].instance_id
    last_second = -math.inf
    prior = GENESIS
    for row in rows:
        row.validate()
        if row.instance_id != instance:
            raise V4ContractError("state movie mixed instance ids")
        if row.causal_second <= last_second:
            raise V4ContractError("state movie seconds must be strictly increasing")
        if row.prior_row_hash != prior:
            raise V4ContractError("state movie hash chain broken")
        last_second = row.causal_second
        prior = row.row_hash
    return prior


class LifecycleState(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    RESOLVED = "RESOLVED"
    CENSORED = "CENSORED"


@dataclass(frozen=True)
class PredecessorLifecycle:
    instance_id: str
    predecessor_id: str
    predecessor_known_by: float
    evaluated_at: float
    state: LifecycleState
    unresolved_age_seconds: float
    resolved_at: float | None = None
    censor_reason: str | None = None

    def validate(self) -> "PredecessorLifecycle":
        _id(self.instance_id, "instance_id"); _id(self.predecessor_id, "predecessor_id")
        known = _finite(self.predecessor_known_by, "predecessor_known_by")
        now = _finite(self.evaluated_at, "evaluated_at")
        age = _finite(self.unresolved_age_seconds, "unresolved_age_seconds")
        if now < known or age < 0 or abs(age - (now - known)) > 1e-6:
            raise V4ContractError("unresolved age must equal evaluated_at - predecessor_known_by")
        if self.state == LifecycleState.RESOLVED:
            if self.resolved_at is None:
                raise V4ContractError("RESOLVED requires resolved_at")
            resolved = _finite(self.resolved_at, "resolved_at")
            if resolved > now or resolved < known:
                raise V4ContractError("resolved_at outside lawful lifecycle interval")
        elif self.resolved_at is not None:
            raise V4ContractError("only RESOLVED may carry resolved_at")
        if self.state == LifecycleState.CENSORED and not str(self.censor_reason or "").strip():
            raise V4ContractError("CENSORED requires censor_reason")
        return self


@dataclass(frozen=True)
class V4LaneSpec:
    lane_id: str
    mode: str
    population_manifest_sha256: str
    feature_schema_sha256: str
    adapter_sha256: str
    reveal_policy_sha256: str
    lock_policy_sha256: str

    def validate(self) -> "V4LaneSpec":
        _id(self.lane_id, "lane_id")
        if self.mode not in {"WALK_FORWARD", "CASE_STUDY_NO_ADAPTATION", "WALK_FORWARD_POSTHOC_ORACLE_CONDITIONED"}:
            raise V4ContractError("unsupported lane mode")
        for field in ("population_manifest_sha256", "feature_schema_sha256", "adapter_sha256", "reveal_policy_sha256", "lock_policy_sha256"):
            _sha(getattr(self, field), field)
        return self


def registry_hash(specs: Sequence[V4LaneSpec]) -> str:
    if not specs:
        raise V4ContractError("lane registry cannot be empty")
    ids = []
    payload = []
    for spec in specs:
        spec.validate(); ids.append(spec.lane_id); payload.append(asdict(spec))
    if len(ids) != len(set(ids)):
        raise V4ContractError("duplicate lane ids")
    return stable_hash({"schema": SCHEMA_VERSION, "lanes": sorted(payload, key=lambda x: x["lane_id"])})


@dataclass(frozen=True)
class ProbabilityEntry:
    signal_lane_id: str
    instance_id: str
    head_id: str
    causal_evaluation_at: float
    decision_available_at: float
    probabilities: tuple[float, ...]
    state_movie_hash: str
    model_sha256: str
    snapshot_sha256: str
    source_manifest_sha256: str
    missingness_manifest_sha256: str
    prior_entry_hash: str = GENESIS
    entry_hash: str = ""

    def core(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "signal_lane_id": self.signal_lane_id,
            "instance_id": self.instance_id,
            "head_id": self.head_id,
            "causal_evaluation_at": self.causal_evaluation_at,
            "decision_available_at": self.decision_available_at,
            "probabilities": list(self.probabilities),
            "state_movie_hash": self.state_movie_hash,
            "model_sha256": self.model_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            "source_manifest_sha256": self.source_manifest_sha256,
            "missingness_manifest_sha256": self.missingness_manifest_sha256,
            "prior_entry_hash": self.prior_entry_hash,
        }

    def validate(self) -> "ProbabilityEntry":
        _id(self.signal_lane_id, "signal_lane_id"); _id(self.instance_id, "instance_id"); _id(self.head_id, "head_id")
        evaluated = _finite(self.causal_evaluation_at, "causal_evaluation_at")
        decision = _finite(self.decision_available_at, "decision_available_at")
        if decision < evaluated:
            raise V4ContractError("decision_available_at cannot precede causal_evaluation_at")
        if len(self.probabilities) < 2:
            raise V4ContractError("probability vector needs at least two states")
        probs = tuple(_prob(x, "probability") for x in self.probabilities)
        if abs(sum(probs) - 1.0) > 1e-9:
            raise V4ContractError("probabilities must sum to 1")
        for field in ("state_movie_hash", "model_sha256", "snapshot_sha256", "source_manifest_sha256", "missingness_manifest_sha256", "prior_entry_hash"):
            _sha(getattr(self, field), field)
        expected = stable_hash(self.core())
        if self.entry_hash and self.entry_hash != expected:
            raise V4ContractError("probability entry hash mismatch")
        return self


def make_probability_entry(**kwargs: Any) -> ProbabilityEntry:
    e = ProbabilityEntry(**kwargs)
    e.validate()
    return ProbabilityEntry(**{**asdict(e), "probabilities": e.probabilities, "entry_hash": stable_hash(e.core())}).validate()


def validate_probability_movie(entries: Sequence[ProbabilityEntry]) -> str:
    if not entries:
        raise V4ContractError("probability movie cannot be empty")
    prior = GENESIS
    last = -math.inf
    identity = (entries[0].signal_lane_id, entries[0].instance_id, entries[0].head_id)
    for e in entries:
        e.validate()
        if (e.signal_lane_id, e.instance_id, e.head_id) != identity:
            raise V4ContractError("probability movie identity drift")
        if e.causal_evaluation_at <= last:
            raise V4ContractError("probability evaluations must be strictly increasing")
        if e.prior_entry_hash != prior:
            raise V4ContractError("probability movie hash chain broken")
        prior = e.entry_hash; last = e.causal_evaluation_at
    return prior


@dataclass(frozen=True)
class FirstLock:
    status: str
    entry_hash: str | None
    lock_decided_at: float | None
    decision_available_at: float | None
    class_index: int | None
    evidence_entry_hashes: tuple[str, ...]
    lock_policy_sha256: str
    lock_hash: str


def recompute_first_lock(entries: Sequence[ProbabilityEntry], *, threshold: float, persistence: int,
                         lock_policy_sha256: str) -> FirstLock:
    validate_probability_movie(entries)
    t = _prob(threshold, "threshold")
    if persistence < 1:
        raise V4ContractError("persistence must be >=1")
    policy = _sha(lock_policy_sha256, "lock_policy_sha256")
    streak_class = None
    streak: list[ProbabilityEntry] = []
    for e in entries:
        best = max(range(len(e.probabilities)), key=lambda i: e.probabilities[i])
        qualifies = e.probabilities[best] >= t
        if not qualifies:
            streak_class = None; streak = []; continue
        if streak_class == best:
            streak.append(e)
        else:
            streak_class = best; streak = [e]
        if len(streak) >= persistence:
            evidence = tuple(x.entry_hash for x in streak[-persistence:])
            core = {
                "status": "LOCKED",
                "entry_hash": e.entry_hash,
                "lock_decided_at": e.causal_evaluation_at,
                "decision_available_at": e.decision_available_at,
                "class_index": best,
                "evidence_entry_hashes": list(evidence),
                "lock_policy_sha256": policy,
            }
            return FirstLock(**core, lock_hash=stable_hash(core))
    core = {
        "status": "NO_RELIABLE_LOCK",
        "entry_hash": None,
        "lock_decided_at": None,
        "decision_available_at": None,
        "class_index": None,
        "evidence_entry_hashes": [],
        "lock_policy_sha256": policy,
    }
    return FirstLock(**{**core, "evidence_entry_hashes": tuple()}, lock_hash=stable_hash(core))


@dataclass(frozen=True)
class ExecutionHandoff:
    signal_id: str
    execution_handoff_id: str
    lane_id: str
    instance_id: str
    probability_entry_hash: str
    first_lock_hash: str
    state_movie_hash: str
    model_sha256: str
    snapshot_sha256: str
    source_manifest_sha256: str
    eligibility_state: str
    decision_available_at: float
    handoff_hash: str = ""

    def core(self) -> dict[str, Any]:
        d = asdict(self); d.pop("handoff_hash", None); return d

    def validate(self) -> "ExecutionHandoff":
        for field in ("signal_id", "execution_handoff_id", "lane_id", "instance_id", "eligibility_state"):
            _id(getattr(self, field), field)
        for field in ("probability_entry_hash", "first_lock_hash", "state_movie_hash", "model_sha256", "snapshot_sha256", "source_manifest_sha256"):
            _sha(getattr(self, field), field)
        _finite(self.decision_available_at, "decision_available_at")
        expected = stable_hash(self.core())
        if self.handoff_hash and self.handoff_hash != expected:
            raise V4ContractError("execution handoff hash mismatch")
        return self


def seal_execution_handoff(**kwargs: Any) -> ExecutionHandoff:
    h = ExecutionHandoff(**kwargs); h.validate()
    return ExecutionHandoff(**{**asdict(h), "handoff_hash": stable_hash(h.core())}).validate()


def validate_execution_binding(handoff: ExecutionHandoff, *, probability_entry: ProbabilityEntry,
                               first_lock: FirstLock, state_movie_hash: str) -> None:
    handoff.validate(); probability_entry.validate(); _sha(state_movie_hash, "state_movie_hash")
    if handoff.probability_entry_hash != probability_entry.entry_hash:
        raise V4ContractError("execution attempted probability substitution")
    if handoff.first_lock_hash != first_lock.lock_hash:
        raise V4ContractError("execution attempted lock substitution")
    if handoff.state_movie_hash != state_movie_hash or probability_entry.state_movie_hash != state_movie_hash:
        raise V4ContractError("execution attempted view/state substitution")
    if handoff.model_sha256 != probability_entry.model_sha256 or handoff.snapshot_sha256 != probability_entry.snapshot_sha256:
        raise V4ContractError("execution attempted model/snapshot substitution")
    if handoff.source_manifest_sha256 != probability_entry.source_manifest_sha256:
        raise V4ContractError("execution attempted source substitution")
    if handoff.decision_available_at != first_lock.decision_available_at:
        raise V4ContractError("execution attempted retiming")
