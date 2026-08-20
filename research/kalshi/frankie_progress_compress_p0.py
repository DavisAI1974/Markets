#!/usr/bin/env python3
"""Bounded Progress & Compress SHADOW lifecycle for Frankie.

Paper-derived plumbing represented here:

* a disposable active column progresses on one sequentially revealed task;
* the active column can read frozen knowledge-base features laterally;
* a teacher-target artifact drives a compression proposal; and
* compression binds an EWC-style parameter anchor and Fisher importance map.

Frankie-added controls represented here include causal reveal/release firewalls,
matched budgets, independent evaluation, planted-null contamination bindings,
cellwise zero-regression retention, immutable artifact lineage, removal, and
byte-exact rollback.  Callback attestations cannot prove an underlying model
actually optimized the paper losses.  Consequently every receipt declares
``paper_faithful=false`` and ``performance_evidence=false``.

The module has no model, filesystem, workflow, V4, apply, or promotion authority.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence


VERSION = "FRANKIE_PROGRESS_COMPRESS_P0_V1_PROVISIONAL"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RESOURCE_DIMENSIONS = (
    "model_calls",
    "input_tokens",
    "output_tokens",
    "tool_queries",
    "storage_bytes",
    "wall_clock_ms",
)
REQUIRED_BUDGET_ARMS = ("FROZEN_BASELINE", "PROGRESS_COMPRESS_CANDIDATE")
MAX_JSON_BYTES = 1_000_000
MAX_CALLBACK_ARTIFACT_BYTES = 20_000_000
ALLOWED_FAULTS = frozenset(
    {
        "AFTER_PRE_RETENTION",
        "AFTER_PROGRESS",
        "AFTER_TEACHER",
        "AFTER_COMPRESS",
        "AFTER_POST_RETENTION",
        "AFTER_NEW_TASK_EVALUATION",
        "BEFORE_ROLLBACK",
    }
)

PAPER_DERIVED_MECHANISMS = (
    "separate active column for current-task progress",
    "lateral access from the active column to protected knowledge-base features",
    "teacher/distillation targets for compressing active competence into a knowledge base",
    "EWC-style Fisher-weighted anchoring of protected parameters during compression",
    "sequential progress then compress lifecycle across tasks",
)
FRANKIE_ADDED_CONTROLS = (
    "immutable byte-hashed permanent knowledge-base snapshot",
    "delayed-label and release-holdout chronology firewall",
    "exact six-dimensional matched budget ceiling",
    "locked independent evaluator and planted-null contamination receipt binding",
    "complete pre/post protected-cohort matrix with zero allowed regression",
    "new-task minimum-improvement gate",
    "hash-chained artifact lineage, disposable removal, and byte-exact rollback",
    "no automatic consolidation and explicit user authorization after evidence",
)
PAPER_MECHANISMS_NOT_IMPLEMENTED = (
    "paper neural architectures and lateral adapter parameterization",
    "paper classification or reinforcement-learning environments",
    "verified gradient optimization of distillation and EWC losses",
    "online Fisher estimation from real trajectories",
    "paper hyperparameters, task curricula, and reported performance",
)


class ProgressCompressP0Error(ValueError):
    """Malformed P0 lifecycle input or violated SHADOW contract."""


class _Abort(RuntimeError):
    def __init__(self, reason: str, *, phase: str, task_id: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.phase = phase
        self.task_id = task_id


def _canonical_json(value: Any) -> bytes:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProgressCompressP0Error(f"value is not canonical JSON: {exc}") from exc
    if len(payload) > MAX_JSON_BYTES:
        raise ProgressCompressP0Error("JSON artifact exceeds the P0 byte limit")
    return payload


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _identifier(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not result or len(result) > 256:
        raise ProgressCompressP0Error(f"{label} must be a non-empty bounded identifier")
    return result


def _sha256(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not SHA256_RE.fullmatch(result):
        raise ProgressCompressP0Error(f"{label} must be a lowercase SHA-256 value")
    return result


def _number(value: Any, label: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProgressCompressP0Error(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or (nonnegative and result < 0.0):
        raise ProgressCompressP0Error(f"{label} must be finite" + (" and nonnegative" if nonnegative else ""))
    return result


def _parse_time(value: Any, label: str) -> dt.datetime:
    text = str(value or "").strip()
    try:
        result = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProgressCompressP0Error(f"{label} must be an ISO-8601 timestamp") from exc
    if result.tzinfo is None:
        raise ProgressCompressP0Error(f"{label} must include a timezone")
    return result.astimezone(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _clone_json(value: Any, label: str) -> Any:
    try:
        return json.loads(_canonical_json(value).decode("utf-8"))
    except ProgressCompressP0Error:
        raise
    except Exception as exc:  # pragma: no cover - defensive JSON boundary
        raise ProgressCompressP0Error(f"{label} cannot be detached") from exc


def _hash_artifact_map(artifacts: Mapping[str, bytes]) -> str:
    return _sha256_json(
        [
            {"artifact_id": artifact_id, "content_sha256": _sha256_bytes(artifacts[artifact_id])}
            for artifact_id in sorted(artifacts)
        ]
    )


def _validate_artifact_map(value: Any, label: str) -> dict[str, bytes]:
    if not isinstance(value, Mapping) or not value:
        raise ProgressCompressP0Error(f"{label} must be a non-empty artifact mapping")
    result: dict[str, bytes] = {}
    total = 0
    for raw_id, raw_bytes in value.items():
        artifact_id = _identifier(raw_id, f"{label} artifact id")
        if artifact_id in result or not isinstance(raw_bytes, bytes) or not raw_bytes:
            raise ProgressCompressP0Error(f"{label} artifacts require unique ids and non-empty bytes")
        total += len(raw_bytes)
        if total > MAX_CALLBACK_ARTIFACT_BYTES:
            raise ProgressCompressP0Error(f"{label} exceeds the callback artifact byte limit")
        result[artifact_id] = bytes(raw_bytes)
    return result


@dataclass(frozen=True)
class ResourceUsage:
    model_calls: float = 0.0
    input_tokens: float = 0.0
    output_tokens: float = 0.0
    tool_queries: float = 0.0
    storage_bytes: float = 0.0
    wall_clock_ms: float = 0.0

    def __post_init__(self) -> None:
        for name in RESOURCE_DIMENSIONS:
            _number(getattr(self, name), f"usage.{name}", nonnegative=True)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ResourceUsage":
        if not isinstance(value, Mapping) or set(value) != set(RESOURCE_DIMENSIONS):
            raise ProgressCompressP0Error("budget must contain exactly the six resource dimensions")
        return cls(**{name: _number(value[name], f"budget.{name}", nonnegative=True) for name in RESOURCE_DIMENSIONS})

    def as_dict(self) -> dict[str, float]:
        return {name: float(getattr(self, name)) for name in RESOURCE_DIMENSIONS}

    def add(self, other: "ResourceUsage") -> "ResourceUsage":
        return ResourceUsage(**{name: getattr(self, name) + getattr(other, name) for name in RESOURCE_DIMENSIONS})


@dataclass(frozen=True)
class ShadowCallbackResult:
    """Detached callback output with mandatory isolation and usage attestations."""

    payload: Mapping[str, Any]
    artifacts: Mapping[str, bytes]
    usage: ResourceUsage = field(default_factory=ResourceUsage)
    isolated: bool = False
    side_effect_free: bool = False
    permanent_state_mutated: bool = True
    release_data_accessed: bool = True

    def __post_init__(self) -> None:
        _clone_json(dict(self.payload), "callback payload")
        _validate_artifact_map(self.artifacts, "callback")
        if not isinstance(self.usage, ResourceUsage):
            raise ProgressCompressP0Error("callback usage must be ResourceUsage")
        if (
            self.isolated is not True
            or self.side_effect_free is not True
            or self.permanent_state_mutated is not False
            or self.release_data_accessed is not False
        ):
            raise ProgressCompressP0Error(
                "callback must attest isolation, side-effect freedom, no permanent mutation, and no release access"
            )


Callback = Callable[[Mapping[str, Any]], ShadowCallbackResult]


def _receipt_self_hash(receipt: Mapping[str, Any], hash_field: str) -> bool:
    supplied = str(receipt.get(hash_field, ""))
    core = {str(key): value for key, value in receipt.items() if key != hash_field}
    try:
        return bool(SHA256_RE.fullmatch(supplied)) and supplied == _sha256_json(core)
    except ProgressCompressP0Error:
        return False


def _validate_external_controls(
    evaluator_receipt: Mapping[str, Any],
    contamination_receipt: Mapping[str, Any],
    release_firewall_receipt: Mapping[str, Any],
    task_release_hashes: Mapping[str, str],
) -> dict[str, str]:
    if not isinstance(evaluator_receipt, Mapping) or not _receipt_self_hash(evaluator_receipt, "canary_hash"):
        raise ProgressCompressP0Error("evaluator-independence receipt is absent or hash-invalid")
    evaluator_hash = _sha256(evaluator_receipt.get("judge_version_hash"), "judge version hash")
    _sha256(evaluator_receipt.get("canary_manifest_hash"), "judge canary manifest hash")
    _sha256(evaluator_receipt.get("case_set_hash"), "judge canary case-set hash")
    judge_id = str(evaluator_receipt.get("judge_id") or "").strip()
    cases = evaluator_receipt.get("cases")
    rates = evaluator_receipt.get("rates")
    tolerances = evaluator_receipt.get("tolerances")
    judge_metrics = (
        "order_flip_rate",
        "length_control_flip_rate",
        "truth_disagreement_rate",
    )
    if (
        not judge_id
        or judge_id == "UNBOUND"
        or type(cases) is not int
        or cases < 100
        or not isinstance(rates, Mapping)
        or not isinstance(tolerances, Mapping)
        or set(rates) != set(judge_metrics)
        or set(tolerances) != set(judge_metrics)
        or any(
            not 0.0 <= _number(rates[name], f"judge {name}") <= _number(
                tolerances[name], f"judge {name} tolerance"
            ) <= 1.0
            for name in judge_metrics
        )
        or evaluator_receipt.get("verdict") != "JUDGE_AUTHORITY_RETAINED"
        or evaluator_receipt.get("promotion_authority") != "NONE"
        or evaluator_receipt.get("blockers") != []
    ):
        raise ProgressCompressP0Error("independent evaluator canary did not retain grading authority")

    if not isinstance(contamination_receipt, Mapping) or not _receipt_self_hash(contamination_receipt, "receipt_hash"):
        raise ProgressCompressP0Error("contamination receipt is absent or hash-invalid")
    bindings = contamination_receipt.get("bindings")
    policy = contamination_receipt.get("policy")
    trial_count = contamination_receipt.get("trial_count")
    false_count = contamination_receipt.get("false_selection_count")
    false_rate = contamination_receipt.get("false_selection_rate")
    false_upper = contamination_receipt.get("false_selection_wilson_upper")
    if (
        contamination_receipt.get("verdict") != "PASS"
        or contamination_receipt.get("declared_parent_hash_separation") is not True
        or contamination_receipt.get("blockers") != []
        or not isinstance(bindings, Mapping)
        or bindings.get("locked_evaluator_hash") != evaluator_hash
        or set(bindings) != {
            "precommit_hash",
            "adaptive_search_manifest_hash",
            "planted_null_manifest_hash",
            "locked_evaluator_hash",
        }
        or any(not SHA256_RE.fullmatch(str(value)) for value in bindings.values())
        or len(set(bindings.values())) != len(bindings)
        or not isinstance(policy, Mapping)
        or contamination_receipt.get("policy_hash") != _sha256_json(dict(policy))
        or type(trial_count) is not int
        or trial_count < 2
        or type(false_count) is not int
        or not 0 <= false_count <= trial_count
        or not math.isclose(
            _number(false_rate, "contamination false-selection rate"),
            false_count / trial_count,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        or _number(false_upper, "contamination Wilson upper bound")
        > _number(policy.get("max_false_selection_rate"), "contamination policy rate")
    ):
        raise ProgressCompressP0Error("planted-null contamination gate is unbound or failed")
    _sha256(contamination_receipt.get("row_hash"), "contamination row hash")

    if not isinstance(release_firewall_receipt, Mapping) or not _receipt_self_hash(
        release_firewall_receipt, "firewall_hash"
    ):
        raise ProgressCompressP0Error("release-firewall receipt is absent or hash-invalid")
    declared_release = release_firewall_receipt.get("task_release_manifest_sha256")
    if not isinstance(declared_release, Mapping):
        raise ProgressCompressP0Error("release firewall must bind every task release manifest")
    normalized_release = {
        _identifier(key, "release firewall task id"): _sha256(value, "release manifest hash")
        for key, value in declared_release.items()
    }
    if (
        normalized_release != dict(task_release_hashes)
        or release_firewall_receipt.get("adaptation_exposure_count") != 0
        or release_firewall_receipt.get("row_level_disclosed") is not False
        or release_firewall_receipt.get("release_data_available_to_candidate") is not False
        or release_firewall_receipt.get("locked_evaluator_hash") != evaluator_hash
    ):
        raise ProgressCompressP0Error("release firewall is incomplete, exposed, or evaluator-unbound")
    return {
        "evaluator_artifact_sha256": evaluator_hash,
        "evaluator_receipt_hash": str(evaluator_receipt["canary_hash"]),
        "contamination_receipt_hash": str(contamination_receipt["receipt_hash"]),
        "release_firewall_receipt_hash": str(release_firewall_receipt["firewall_hash"]),
    }


def _normalize_budgets(value: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, ResourceUsage], str]:
    if not isinstance(value, Mapping) or set(value) != set(REQUIRED_BUDGET_ARMS):
        raise ProgressCompressP0Error(
            "matched_budgets must contain exactly frozen baseline and Progress & Compress candidate"
        )
    result = {arm: ResourceUsage.from_mapping(value[arm]) for arm in REQUIRED_BUDGET_ARMS}
    frozen = result["FROZEN_BASELINE"].as_dict()
    if result["PROGRESS_COMPRESS_CANDIDATE"].as_dict() != frozen:
        raise ProgressCompressP0Error("frozen baseline and candidate budgets are not exactly matched")
    return result, _sha256_json({arm: result[arm].as_dict() for arm in REQUIRED_BUDGET_ARMS})


def _normalize_cohorts(value: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise ProgressCompressP0Error("protected_cohorts must be a non-empty sequence")
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in value:
        if not isinstance(raw, Mapping):
            raise ProgressCompressP0Error("protected cohort entries must be objects")
        cohort_id = _identifier(raw.get("cohort_id"), "protected cohort id")
        stratum = _identifier(raw.get("stratum"), "protected cohort stratum")
        key = (cohort_id, stratum)
        min_rows = raw.get("min_rows")
        if key in seen or type(min_rows) is not int or min_rows < 1 or type(raw.get("higher_is_better")) is not bool:
            raise ProgressCompressP0Error("protected cohorts require unique cells, positive rows, and direction")
        seen.add(key)
        result.append(
            {
                "cohort_id": cohort_id,
                "stratum": stratum,
                "case_manifest_sha256": _sha256(raw.get("case_manifest_sha256"), "cohort case manifest"),
                "min_rows": min_rows,
                "higher_is_better": raw["higher_is_better"],
            }
        )
    result.sort(key=lambda item: (item["cohort_id"], item["stratum"]))
    return result, _sha256_json(result)


def _normalize_tasks(value: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise ProgressCompressP0Error("tasks must be a non-empty sequential task list")
    result: list[dict[str, Any]] = []
    release_hashes: dict[str, str] = {}
    seen: set[str] = set()
    prior_evaluation: dt.datetime | None = None
    for raw in value:
        if not isinstance(raw, Mapping):
            raise ProgressCompressP0Error("task entries must be objects")
        task_id = _identifier(raw.get("task_id"), "task id")
        if task_id in seen:
            raise ProgressCompressP0Error(f"duplicate task id: {task_id}")
        seen.add(task_id)
        opened = _parse_time(raw.get("opened_at"), f"{task_id}.opened_at")
        revealed = _parse_time(raw.get("label_revealed_at"), f"{task_id}.label_revealed_at")
        progress = _parse_time(raw.get("progress_at"), f"{task_id}.progress_at")
        compress = _parse_time(raw.get("compress_at"), f"{task_id}.compress_at")
        evaluation = _parse_time(raw.get("evaluation_at"), f"{task_id}.evaluation_at")
        release = _parse_time(raw.get("release_at"), f"{task_id}.release_at")
        if not opened < revealed <= progress <= compress <= evaluation < release:
            raise ProgressCompressP0Error(
                f"task {task_id} violates opened < reveal <= progress <= compress <= evaluation < release"
            )
        if prior_evaluation is not None and opened < prior_evaluation:
            raise ProgressCompressP0Error("tasks overlap or are not sequential in declared order")
        prior_evaluation = evaluation
        required_ids_raw = raw.get("required_parameter_ids")
        if not isinstance(required_ids_raw, Sequence) or isinstance(required_ids_raw, (str, bytes)):
            raise ProgressCompressP0Error(f"task {task_id} required_parameter_ids must be a sequence")
        required_ids = tuple(_identifier(item, f"{task_id} parameter id") for item in required_ids_raw)
        if not required_ids or len(set(required_ids)) != len(required_ids):
            raise ProgressCompressP0Error(f"task {task_id} requires unique protected parameters")
        parameters = raw.get("ewc_parameters")
        if not isinstance(parameters, Mapping) or set(parameters) != set(required_ids):
            raise ProgressCompressP0Error(f"task {task_id} Fisher/anchor coverage is incomplete or extra")
        normalized_parameters: dict[str, dict[str, Any]] = {}
        positive_fisher = 0
        for parameter_id in sorted(required_ids):
            item = parameters[parameter_id]
            if not isinstance(item, Mapping):
                raise ProgressCompressP0Error(f"task {task_id} EWC parameter entries must be objects")
            fisher = _number(item.get("fisher"), f"{task_id}.{parameter_id}.fisher", nonnegative=True)
            positive_fisher += int(fisher > 0.0)
            normalized_parameters[parameter_id] = {
                "anchor": _number(item.get("anchor"), f"{task_id}.{parameter_id}.anchor"),
                "fisher": fisher,
                "source_artifact_id": _identifier(
                    item.get("source_artifact_id"), f"{task_id}.{parameter_id}.source_artifact_id"
                ),
            }
        if positive_fisher == 0:
            raise ProgressCompressP0Error(f"task {task_id} Fisher map is vacuous")
        min_rows = raw.get("new_task_min_rows")
        if type(min_rows) is not int or min_rows < 1 or type(raw.get("new_task_higher_is_better")) is not bool:
            raise ProgressCompressP0Error(f"task {task_id} new-task evaluation contract is invalid")
        release_hash = _sha256(raw.get("release_manifest_sha256"), f"{task_id} release manifest")
        release_hashes[task_id] = release_hash
        normalized = {
            "task_id": task_id,
            "opened_at": _iso(opened),
            "label_revealed_at": _iso(revealed),
            "progress_at": _iso(progress),
            "compress_at": _iso(compress),
            "evaluation_at": _iso(evaluation),
            "release_at": _iso(release),
            "training_manifest_sha256": _sha256(raw.get("training_manifest_sha256"), f"{task_id} training manifest"),
            "new_task_evaluation_manifest_sha256": _sha256(
                raw.get("new_task_evaluation_manifest_sha256"), f"{task_id} new-task manifest"
            ),
            "release_manifest_sha256": release_hash,
            "required_parameter_ids": sorted(required_ids),
            "ewc_parameters": normalized_parameters,
            "new_task_min_rows": min_rows,
            "new_task_higher_is_better": raw["new_task_higher_is_better"],
            "minimum_new_task_improvement": _number(
                raw.get("minimum_new_task_improvement"),
                f"{task_id} minimum improvement",
                nonnegative=True,
            ),
        }
        result.append(normalized)
    return result, release_hashes


def build_release_firewall_receipt(
    *,
    task_release_manifest_sha256: Mapping[str, str],
    locked_evaluator_hash: str,
) -> dict[str, Any]:
    """Build a pre-execution zero-exposure release-firewall receipt."""
    if not isinstance(task_release_manifest_sha256, Mapping) or not task_release_manifest_sha256:
        raise ProgressCompressP0Error("release firewall requires task manifests")
    core = {
        "version": VERSION,
        "task_release_manifest_sha256": {
            _identifier(key, "release task id"): _sha256(value, "release manifest hash")
            for key, value in sorted(task_release_manifest_sha256.items())
        },
        "locked_evaluator_hash": _sha256(locked_evaluator_hash, "locked evaluator hash"),
        "adaptation_exposure_count": 0,
        "row_level_disclosed": False,
        "release_data_available_to_candidate": False,
        "performance_evidence": False,
    }
    return {**core, "firewall_hash": _sha256_json(core)}


class _Session:
    def __init__(
        self,
        protected_reference: Mapping[str, bytes],
        protected_snapshot: Mapping[str, bytes],
        expected_hashes: Mapping[str, str],
        budget: ResourceUsage,
        faults: set[str],
    ) -> None:
        self.protected_reference = protected_reference
        self.protected_snapshot = dict(protected_snapshot)
        self.expected_hashes = dict(expected_hashes)
        self.budget = budget
        self.used = ResourceUsage()
        self.faults = faults
        self.events: list[dict[str, Any]] = []
        self.artifacts: list[dict[str, Any]] = []
        self.disposable_hashes: set[str] = set()

    def protected_intact(self) -> bool:
        try:
            current = _validate_artifact_map(self.protected_reference, "protected knowledge base")
        except ProgressCompressP0Error:
            return False
        return set(current) == set(self.expected_hashes) and all(
            _sha256_bytes(current[key]) == self.expected_hashes[key] for key in current
        )

    def _digestable_context(self, value: Any) -> Any:
        if isinstance(value, bytes):
            return {"byte_count": len(value), "content_sha256": _sha256_bytes(value)}
        if isinstance(value, Mapping):
            return {str(key): self._digestable_context(item) for key, item in value.items()}
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return [self._digestable_context(item) for item in value]
        return value

    def call(
        self,
        operation: str,
        callback: Callback,
        context: Mapping[str, Any],
        *,
        task_id: str | None,
        allowed_access_hashes: set[str],
        release_hash: str | None,
        parent_hashes: Sequence[str],
    ) -> tuple[dict[str, Any], dict[str, bytes], str]:
        if not self.protected_intact():
            raise _Abort("protected knowledge base mutated before callback", phase=operation, task_id=task_id)
        detached_context = copy.deepcopy(dict(context))
        try:
            raw = callback(detached_context)
        except Exception as exc:
            raise _Abort(f"{operation} callback failed: {type(exc).__name__}", phase=operation, task_id=task_id) from exc
        if not isinstance(raw, ShadowCallbackResult):
            raise _Abort(f"{operation} callback did not return ShadowCallbackResult", phase=operation, task_id=task_id)
        if not self.protected_intact():
            raise _Abort("protected knowledge base mutated by callback", phase=operation, task_id=task_id)
        try:
            payload = _clone_json(dict(raw.payload), f"{operation} callback payload")
            artifacts = _validate_artifact_map(raw.artifacts, f"{operation} callback")
        except ProgressCompressP0Error as exc:
            raise _Abort(str(exc), phase=operation, task_id=task_id) from exc
        if raw.isolated is not True or raw.side_effect_free is not True or raw.permanent_state_mutated is not False:
            raise _Abort(f"{operation} callback isolation attestation failed", phase=operation, task_id=task_id)
        if raw.release_data_accessed is not False:
            raise _Abort(f"{operation} callback accessed release data", phase=operation, task_id=task_id)
        accesses = payload.get("accessed_artifact_hashes")
        if not isinstance(accesses, list) or any(not SHA256_RE.fullmatch(str(value)) for value in accesses):
            raise _Abort(f"{operation} callback must serialize accessed artifact hashes", phase=operation, task_id=task_id)
        if len(set(accesses)) != len(accesses) or not set(accesses).issubset(allowed_access_hashes):
            raise _Abort(f"{operation} callback accessed an undeclared artifact", phase=operation, task_id=task_id)
        if release_hash and (
            release_hash in set(accesses)
            or release_hash in json.dumps(payload, sort_keys=True, separators=(",", ":"))
            or any(release_hash.encode("ascii") in value for value in artifacts.values())
        ):
            raise _Abort(f"{operation} callback leaked release data", phase=operation, task_id=task_id)
        self.used = self.used.add(raw.usage)
        exceeded = [
            name
            for name in RESOURCE_DIMENSIONS
            if getattr(self.used, name) > getattr(self.budget, name)
        ]
        if exceeded:
            raise _Abort(
                f"matched candidate budget exceeded: {', '.join(exceeded)}",
                phase=operation,
                task_id=task_id,
            )
        artifact_rows = []
        for artifact_id in sorted(artifacts):
            content_hash = _sha256_bytes(artifacts[artifact_id])
            artifact_row = {
                "artifact_id": f"{len(self.events) + 1}:{operation}:{task_id or 'GLOBAL'}:{artifact_id}",
                "logical_artifact_id": artifact_id,
                "artifact_class": operation,
                "content_sha256": content_hash,
                "byte_count": len(artifacts[artifact_id]),
                "parent_hashes": sorted(set(parent_hashes)),
                "disposable": True,
            }
            artifact_rows.append(artifact_row)
            self.artifacts.append(artifact_row)
            self.disposable_hashes.add(content_hash)
        prior = self.events[-1]["event_hash"] if self.events else _hash_artifact_map(self.protected_snapshot)
        core = {
            "sequence": len(self.events) + 1,
            "operation": operation,
            "task_id": task_id,
            "context_hash": _sha256_json(self._digestable_context(context)),
            "payload_hash": _sha256_json(payload),
            "artifact_hashes": [row["content_sha256"] for row in artifact_rows],
            "usage": raw.usage.as_dict(),
            "cumulative_usage": self.used.as_dict(),
            "parent_hashes": sorted(set(parent_hashes)),
            "prior_event_hash": prior,
        }
        event = {**core, "event_hash": _sha256_json(core)}
        self.events.append(event)
        return payload, artifacts, event["event_hash"]


def _validate_operation(payload: Mapping[str, Any], operation: str, task: Mapping[str, Any], at_field: str) -> None:
    if (
        payload.get("operation") != operation
        or payload.get("task_id") != task["task_id"]
        or _iso(_parse_time(payload.get("observed_at"), f"{operation}.observed_at")) != task[at_field]
    ):
        raise _Abort("callback operation/task/time binding mismatch", phase=operation, task_id=task["task_id"])


def _cohort_cells(
    payload: Mapping[str, Any],
    cohorts: Sequence[Mapping[str, Any]],
    role: str,
    task: Mapping[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    _validate_operation(payload, "EVALUATE_PROTECTED", task, "evaluation_at")
    if payload.get("evaluation_role") != role:
        raise _Abort("protected evaluation role mismatch", phase=f"EVALUATE_{role}", task_id=task["task_id"])
    raw_cells = payload.get("cells")
    if not isinstance(raw_cells, list):
        raise _Abort("protected evaluation cells are missing", phase=f"EVALUATE_{role}", task_id=task["task_id"])
    expected = {(item["cohort_id"], item["stratum"]): item for item in cohorts}
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in raw_cells:
        if not isinstance(raw, Mapping):
            raise _Abort("protected evaluation cell is malformed", phase=f"EVALUATE_{role}", task_id=task["task_id"])
        key = (
            _identifier(raw.get("cohort_id"), "evaluation cohort id"),
            _identifier(raw.get("stratum"), "evaluation stratum"),
        )
        row_count = raw.get("row_count")
        if key not in expected or key in result or type(row_count) is not int or row_count < expected.get(key, {}).get("min_rows", 1):
            raise _Abort("protected retention matrix is missing, extra, duplicate, or sparse", phase=f"EVALUATE_{role}", task_id=task["task_id"])
        contract = expected[key]
        if (
            raw.get("case_manifest_sha256") != contract["case_manifest_sha256"]
            or raw.get("higher_is_better") is not contract["higher_is_better"]
        ):
            raise _Abort("protected evaluation cell contract mismatch", phase=f"EVALUATE_{role}", task_id=task["task_id"])
        result[key] = {
            "cohort_id": key[0],
            "stratum": key[1],
            "case_manifest_sha256": contract["case_manifest_sha256"],
            "row_count": row_count,
            "higher_is_better": contract["higher_is_better"],
            "metric": _number(raw.get("metric"), "protected cell metric"),
        }
    if set(result) != set(expected):
        raise _Abort("protected retention matrix is incomplete", phase=f"EVALUATE_{role}", task_id=task["task_id"])
    return result


def _new_task_metric(payload: Mapping[str, Any], arm: str, task: Mapping[str, Any]) -> dict[str, Any]:
    _validate_operation(payload, "EVALUATE_NEW_TASK", task, "evaluation_at")
    row_count = payload.get("row_count")
    if (
        payload.get("arm") != arm
        or payload.get("case_manifest_sha256") != task["new_task_evaluation_manifest_sha256"]
        or payload.get("higher_is_better") is not task["new_task_higher_is_better"]
        or type(row_count) is not int
        or row_count < task["new_task_min_rows"]
    ):
        raise _Abort("new-task evaluation is unbound or sparse", phase=f"EVALUATE_NEW_{arm}", task_id=task["task_id"])
    return {
        "arm": arm,
        "row_count": row_count,
        "metric": _number(payload.get("metric"), "new-task metric"),
        "higher_is_better": task["new_task_higher_is_better"],
        "case_manifest_sha256": task["new_task_evaluation_manifest_sha256"],
    }


def _make_rollback_receipt(
    original: Mapping[str, bytes],
    candidate: Mapping[str, bytes] | None,
    restored: Mapping[str, bytes] | None,
    protected_intact: bool,
) -> dict[str, Any]:
    original_hashes = {key: _sha256_bytes(value) for key, value in sorted(original.items())}
    candidate_hashes = (
        {key: _sha256_bytes(value) for key, value in sorted(candidate.items())} if candidate else {}
    )
    restored_hashes = (
        {key: _sha256_bytes(value) for key, value in sorted(restored.items())} if restored else {}
    )
    nonvacuous = bool(candidate) and set(candidate) == set(original) and any(
        candidate[key] != original[key] for key in original
    )
    byte_exact = bool(restored) and set(restored) == set(original) and all(
        restored[key] == original[key] for key in original
    )
    core = {
        "version": VERSION,
        "original_hashes": original_hashes,
        "candidate_hashes": candidate_hashes,
        "restored_hashes": restored_hashes,
        "nonvacuous_candidate": nonvacuous,
        "byte_exact_restoration": byte_exact,
        "permanent_protected_snapshot_intact": protected_intact,
        "passed": nonvacuous and byte_exact and protected_intact,
        "live_external_rollback_evidence": False,
        "scope": "DISPOSABLE_IN_PROCESS_SHADOW_ARTIFACTS_ONLY",
    }
    return {**core, "rollback_hash": _sha256_json(core)}


def _make_removal_receipt(session: _Session) -> dict[str, Any]:
    protected_intact = session.protected_intact()
    core = {
        "version": VERSION,
        "removed_artifact_hashes": sorted(session.disposable_hashes),
        "removed_artifact_count": len(session.disposable_hashes),
        "raw_artifacts_returned": False,
        "shadow_candidate_available_after_return": False,
        "permanent_state_changed": False if protected_intact else None,
        "permanent_state_integrity_verified": protected_intact,
        "removal_scope": "ALL_DISPOSABLE_CALLBACK_ARTIFACTS",
    }
    return {**core, "removal_hash": _sha256_json(core)}


def run_progress_compress_shadow(
    protected_kb: Mapping[str, bytes],
    expected_protected_hashes: Mapping[str, str],
    tasks: Sequence[Mapping[str, Any]],
    protected_cohorts: Sequence[Mapping[str, Any]],
    matched_budgets: Mapping[str, Mapping[str, Any]],
    *,
    progress_fn: Callback,
    teacher_fn: Callback,
    compress_fn: Callback,
    evaluate_fn: Callback,
    rollback_fn: Callback,
    evaluator_independence_receipt: Mapping[str, Any],
    contamination_receipt: Mapping[str, Any],
    release_firewall_receipt: Mapping[str, Any],
    faults: Sequence[str] = (),
) -> dict[str, Any]:
    """Execute and remove a bounded sequential Progress & Compress proposal.

    Successful contract execution does not retain or apply the candidate.  It
    returns hashes, metrics, lineage, rollback, and removal receipts only.
    """
    protected = _validate_artifact_map(protected_kb, "protected knowledge base")
    if not isinstance(expected_protected_hashes, Mapping) or set(expected_protected_hashes) != set(protected):
        raise ProgressCompressP0Error("expected protected hashes must exactly cover the knowledge base")
    expected_hashes = {
        key: _sha256(expected_protected_hashes[key], f"expected protected hash {key}")
        for key in protected
    }
    if any(_sha256_bytes(protected[key]) != expected_hashes[key] for key in protected):
        raise ProgressCompressP0Error("protected knowledge base does not match frozen expected bytes")
    normalized_tasks, task_release_hashes = _normalize_tasks(tasks)
    cohorts, cohort_manifest_hash = _normalize_cohorts(protected_cohorts)
    budgets, budget_manifest_hash = _normalize_budgets(matched_budgets)
    fault_set = {_identifier(value, "fault") for value in faults}
    if not fault_set.issubset(ALLOWED_FAULTS):
        raise ProgressCompressP0Error("unknown Progress & Compress fault injection point")
    callbacks = (progress_fn, teacher_fn, compress_fn, evaluate_fn, rollback_fn)
    if any(not callable(item) for item in callbacks) or len({id(item) for item in callbacks}) != len(callbacks):
        raise ProgressCompressP0Error("all callbacks must be callable and independently bound")
    external = _validate_external_controls(
        evaluator_independence_receipt,
        contamination_receipt,
        release_firewall_receipt,
        task_release_hashes,
    )
    protected_hash_set = set(expected_hashes.values())
    if external["evaluator_artifact_sha256"] in protected_hash_set:
        raise ProgressCompressP0Error("evaluator artifact is not independent from protected model artifacts")

    session = _Session(
        protected_kb,
        protected,
        expected_hashes,
        budgets["PROGRESS_COMPRESS_CANDIDATE"],
        fault_set,
    )
    current_kb = dict(protected)
    last_candidate: dict[str, bytes] | None = None
    task_receipts: list[dict[str, Any]] = []
    phase = "PREFLIGHT"
    task_id: str | None = None
    abort: _Abort | None = None
    rollback_result: dict[str, bytes] | None = None
    try:
        for task in normalized_tasks:
            task_id = task["task_id"]
            release_hash = task["release_manifest_sha256"]
            current_hashes = {_sha256_bytes(value) for value in current_kb.values()}
            current_snapshot_hash = _hash_artifact_map(current_kb)
            ewc_manifest = {
                "anchor_kb_snapshot_sha256": current_snapshot_hash,
                "parameters": task["ewc_parameters"],
            }
            invalid_sources = sorted(
                {
                    item["source_artifact_id"]
                    for item in task["ewc_parameters"].values()
                    if item["source_artifact_id"] not in current_kb
                }
            )
            if invalid_sources:
                raise _Abort("EWC anchors cite unknown protected artifacts", phase="EWC_PREFLIGHT", task_id=task_id)
            ewc_manifest_hash = _sha256_json(ewc_manifest)

            phase = "EVALUATE_PRE_PROTECTED"
            pre_allowed = current_hashes | {item["case_manifest_sha256"] for item in cohorts}
            pre_payload, _, pre_event = session.call(
                "EVALUATE_PROTECTED",
                evaluate_fn,
                {
                    "operation": "EVALUATE_PROTECTED",
                    "evaluation_role": "PRE",
                    "task_id": task_id,
                    "observed_at": task["evaluation_at"],
                    "knowledge_base": dict(current_kb),
                    "protected_cohorts": cohorts,
                    "evaluator_artifact_sha256": external["evaluator_artifact_sha256"],
                },
                task_id=task_id,
                allowed_access_hashes=pre_allowed,
                release_hash=release_hash,
                parent_hashes=(current_snapshot_hash, cohort_manifest_hash, external["evaluator_receipt_hash"]),
            )
            pre_cells = _cohort_cells(pre_payload, cohorts, "PRE", task)
            if "AFTER_PRE_RETENTION" in fault_set:
                raise _Abort("fault injected after pre-retention", phase=phase, task_id=task_id)

            phase = "PROGRESS"
            progress_allowed = current_hashes | {task["training_manifest_sha256"]}
            progress_payload, active_artifacts, progress_event = session.call(
                "PROGRESS",
                progress_fn,
                {
                    "operation": "PROGRESS",
                    "task_id": task_id,
                    "observed_at": task["progress_at"],
                    "label_revealed_at": task["label_revealed_at"],
                    "training_manifest_sha256": task["training_manifest_sha256"],
                    "protected_feature_artifacts": dict(current_kb),
                },
                task_id=task_id,
                allowed_access_hashes=progress_allowed,
                release_hash=release_hash,
                parent_hashes=(current_snapshot_hash, task["training_manifest_sha256"]),
            )
            _validate_operation(progress_payload, "PROGRESS", task, "progress_at")
            lateral = progress_payload.get("lateral_accesses")
            if not isinstance(lateral, list) or not lateral:
                raise _Abort("active column has no declared protected lateral access", phase=phase, task_id=task_id)
            seen_lateral: set[str] = set()
            for item in lateral:
                if not isinstance(item, Mapping):
                    raise _Abort("lateral access receipt is malformed", phase=phase, task_id=task_id)
                artifact_id = _identifier(item.get("artifact_id"), "lateral artifact id")
                if (
                    artifact_id in seen_lateral
                    or artifact_id not in current_kb
                    or item.get("content_sha256") != _sha256_bytes(current_kb[artifact_id])
                ):
                    raise _Abort("lateral access does not bind a protected feature artifact", phase=phase, task_id=task_id)
                seen_lateral.add(artifact_id)
            if sorted(progress_payload.get("active_column_artifact_ids", [])) != sorted(active_artifacts):
                raise _Abort("active-column artifact ids are not bound", phase=phase, task_id=task_id)
            active_hashes = {_sha256_bytes(value) for value in active_artifacts.values()}
            if "AFTER_PROGRESS" in fault_set:
                raise _Abort("fault injected after progress", phase=phase, task_id=task_id)

            phase = "TEACHER_TARGETS"
            teacher_allowed = progress_allowed | active_hashes
            teacher_payload, teacher_artifacts, teacher_event = session.call(
                "TEACHER_TARGETS",
                teacher_fn,
                {
                    "operation": "TEACHER_TARGETS",
                    "task_id": task_id,
                    "observed_at": task["compress_at"],
                    "active_column": dict(active_artifacts),
                    "protected_knowledge_base": dict(current_kb),
                    "training_manifest_sha256": task["training_manifest_sha256"],
                },
                task_id=task_id,
                allowed_access_hashes=teacher_allowed,
                release_hash=release_hash,
                parent_hashes=(progress_event, current_snapshot_hash),
            )
            _validate_operation(teacher_payload, "TEACHER_TARGETS", task, "compress_at")
            target_id = _identifier(teacher_payload.get("teacher_target_artifact_id"), "teacher target artifact id")
            if target_id not in teacher_artifacts:
                raise _Abort("teacher target artifact is absent", phase=phase, task_id=task_id)
            teacher_target_hash = _sha256_bytes(teacher_artifacts[target_id])
            if teacher_payload.get("teacher_target_sha256") != teacher_target_hash:
                raise _Abort("teacher target hash is unbound", phase=phase, task_id=task_id)
            if "AFTER_TEACHER" in fault_set:
                raise _Abort("fault injected after teacher targets", phase=phase, task_id=task_id)

            phase = "COMPRESS_PROPOSAL"
            compress_allowed = teacher_allowed | {_sha256_bytes(value) for value in teacher_artifacts.values()} | {ewc_manifest_hash}
            compress_payload, candidate_kb, compress_event = session.call(
                "COMPRESS_PROPOSAL",
                compress_fn,
                {
                    "operation": "COMPRESS_PROPOSAL",
                    "task_id": task_id,
                    "observed_at": task["compress_at"],
                    "active_column": dict(active_artifacts),
                    "teacher_targets": dict(teacher_artifacts),
                    "teacher_target_sha256": teacher_target_hash,
                    "current_shadow_knowledge_base": dict(current_kb),
                    "ewc_manifest": ewc_manifest,
                    "ewc_manifest_sha256": ewc_manifest_hash,
                },
                task_id=task_id,
                allowed_access_hashes=compress_allowed,
                release_hash=release_hash,
                parent_hashes=(teacher_event, progress_event, ewc_manifest_hash),
            )
            _validate_operation(compress_payload, "COMPRESS_PROPOSAL", task, "compress_at")
            if set(candidate_kb) != set(current_kb) or not any(
                candidate_kb[key] != current_kb[key] for key in current_kb
            ):
                raise _Abort("compression proposal must be non-vacuous and exactly cover KB artifacts", phase=phase, task_id=task_id)
            if (
                compress_payload.get("teacher_target_sha256") != teacher_target_hash
                or compress_payload.get("ewc_manifest_sha256") != ewc_manifest_hash
                or sorted(compress_payload.get("protected_parameter_ids", [])) != task["required_parameter_ids"]
                or compress_payload.get("distillation_applied") is not True
                or compress_payload.get("ewc_anchor_applied") is not True
                or sorted(compress_payload.get("candidate_kb_artifact_ids", [])) != sorted(candidate_kb)
            ):
                raise _Abort("compression proposal lacks teacher, Fisher/anchor, or artifact bindings", phase=phase, task_id=task_id)
            last_candidate = dict(candidate_kb)
            candidate_hashes = {_sha256_bytes(value) for value in candidate_kb.values()}
            candidate_snapshot_hash = _hash_artifact_map(candidate_kb)
            if external["evaluator_artifact_sha256"] in candidate_hashes:
                raise _Abort("candidate aliases the independent evaluator artifact", phase=phase, task_id=task_id)
            if "AFTER_COMPRESS" in fault_set:
                raise _Abort("fault injected after compression", phase=phase, task_id=task_id)

            phase = "EVALUATE_POST_PROTECTED"
            post_allowed = candidate_hashes | {item["case_manifest_sha256"] for item in cohorts}
            post_payload, _, post_event = session.call(
                "EVALUATE_PROTECTED",
                evaluate_fn,
                {
                    "operation": "EVALUATE_PROTECTED",
                    "evaluation_role": "POST",
                    "task_id": task_id,
                    "observed_at": task["evaluation_at"],
                    "knowledge_base": dict(candidate_kb),
                    "protected_cohorts": cohorts,
                    "evaluator_artifact_sha256": external["evaluator_artifact_sha256"],
                },
                task_id=task_id,
                allowed_access_hashes=post_allowed,
                release_hash=release_hash,
                parent_hashes=(candidate_snapshot_hash, cohort_manifest_hash, external["evaluator_receipt_hash"]),
            )
            post_cells = _cohort_cells(post_payload, cohorts, "POST", task)
            retention_rows = []
            regressions = []
            for key in sorted(pre_cells):
                pre = pre_cells[key]
                post = post_cells[key]
                delta = post["metric"] - pre["metric"]
                oriented = delta if pre["higher_is_better"] else -delta
                row = {
                    "cohort_id": key[0],
                    "stratum": key[1],
                    "pre_metric": pre["metric"],
                    "post_metric": post["metric"],
                    "oriented_delta": oriented,
                    "pre_row_count": pre["row_count"],
                    "post_row_count": post["row_count"],
                    "zero_regression_passed": oriented >= 0.0,
                }
                retention_rows.append(row)
                if oriented < 0.0:
                    regressions.append(f"{key[0]}/{key[1]}")
            if regressions:
                raise _Abort(
                    "catastrophic protected-cohort regression: " + ", ".join(regressions),
                    phase=phase,
                    task_id=task_id,
                )
            if "AFTER_POST_RETENTION" in fault_set:
                raise _Abort("fault injected after post-retention", phase=phase, task_id=task_id)

            new_results = {}
            new_events = []
            for arm, kb in (("FROZEN_BASELINE", protected), ("CANDIDATE", candidate_kb)):
                arm_hashes = {_sha256_bytes(value) for value in kb.values()}
                payload, _, event_hash = session.call(
                    "EVALUATE_NEW_TASK",
                    evaluate_fn,
                    {
                        "operation": "EVALUATE_NEW_TASK",
                        "arm": arm,
                        "task_id": task_id,
                        "observed_at": task["evaluation_at"],
                        "knowledge_base": dict(kb),
                        "case_manifest_sha256": task["new_task_evaluation_manifest_sha256"],
                        "evaluator_artifact_sha256": external["evaluator_artifact_sha256"],
                    },
                    task_id=task_id,
                    allowed_access_hashes=arm_hashes | {task["new_task_evaluation_manifest_sha256"]},
                    release_hash=release_hash,
                    parent_hashes=(_hash_artifact_map(kb), external["evaluator_receipt_hash"]),
                )
                new_results[arm] = _new_task_metric(payload, arm, task)
                new_events.append(event_hash)
            baseline_metric = new_results["FROZEN_BASELINE"]["metric"]
            candidate_metric = new_results["CANDIDATE"]["metric"]
            raw_improvement = candidate_metric - baseline_metric
            oriented_improvement = raw_improvement if task["new_task_higher_is_better"] else -raw_improvement
            if oriented_improvement < task["minimum_new_task_improvement"]:
                raise _Abort("new-task improvement is below the declared minimum", phase="EVALUATE_NEW_TASK", task_id=task_id)
            if "AFTER_NEW_TASK_EVALUATION" in fault_set:
                raise _Abort("fault injected after new-task evaluation", phase="EVALUATE_NEW_TASK", task_id=task_id)

            task_core = {
                "task_id": task_id,
                "chronology": {key: task[key] for key in ("opened_at", "label_revealed_at", "progress_at", "compress_at", "evaluation_at", "release_at")},
                "training_manifest_sha256": task["training_manifest_sha256"],
                "new_task_evaluation_manifest_sha256": task["new_task_evaluation_manifest_sha256"],
                "release_manifest_sha256": release_hash,
                "input_shadow_kb_snapshot_sha256": current_snapshot_hash,
                "candidate_shadow_kb_snapshot_sha256": candidate_snapshot_hash,
                "ewc_manifest_sha256": ewc_manifest_hash,
                "teacher_target_sha256": teacher_target_hash,
                "retention_rows": retention_rows,
                "retention_matrix_hash": _sha256_json(retention_rows),
                "protected_zero_regression": True,
                "new_task": {
                    "baseline": new_results["FROZEN_BASELINE"],
                    "candidate": new_results["CANDIDATE"],
                    "oriented_improvement": oriented_improvement,
                    "minimum_improvement": task["minimum_new_task_improvement"],
                    "passed": True,
                },
                "lineage_parent_events": [pre_event, progress_event, teacher_event, compress_event, post_event, *new_events],
                "accepted_for_next_disposable_shadow_task": True,
                "consolidated_into_permanent_kb": False,
            }
            task_receipts.append({**task_core, "task_receipt_hash": _sha256_json(task_core)})
            current_kb = dict(candidate_kb)

        phase = "ROLLBACK"
        if "BEFORE_ROLLBACK" in fault_set:
            raise _Abort("fault injected before rollback", phase=phase, task_id=task_id)
        rollback_payload, rollback_artifacts, _ = session.call(
            "ROLLBACK",
            rollback_fn,
            {
                "operation": "ROLLBACK",
                "task_id": task_id,
                "observed_at": normalized_tasks[-1]["evaluation_at"],
                "candidate_shadow_knowledge_base": dict(current_kb),
                "expected_protected_hashes": expected_hashes,
            },
            task_id=task_id,
            allowed_access_hashes={_sha256_bytes(value) for value in current_kb.values()} | set(expected_hashes.values()),
            release_hash=None,
            parent_hashes=(_hash_artifact_map(current_kb), _hash_artifact_map(protected)),
        )
        if rollback_payload.get("operation") != "ROLLBACK" or rollback_payload.get("byte_exact_requested") is not True:
            raise _Abort("rollback callback contract is malformed", phase=phase, task_id=task_id)
        rollback_result = dict(rollback_artifacts)
        rollback_receipt = _make_rollback_receipt(protected, current_kb, rollback_result, session.protected_intact())
        if not rollback_receipt["passed"]:
            raise _Abort("byte-exact shadow rollback failed", phase=phase, task_id=task_id)
    except _Abort as exc:
        abort = exc
    except ProgressCompressP0Error as exc:
        abort = _Abort(str(exc), phase=phase, task_id=task_id)

    if abort is not None:
        if rollback_result is None and last_candidate is not None and session.protected_intact():
            try:
                payload, artifacts, _ = session.call(
                    "ROLLBACK",
                    rollback_fn,
                    {
                        "operation": "ROLLBACK",
                        "task_id": abort.task_id,
                        "observed_at": normalized_tasks[-1]["evaluation_at"],
                        "candidate_shadow_knowledge_base": dict(last_candidate),
                        "expected_protected_hashes": expected_hashes,
                    },
                    task_id=abort.task_id,
                    allowed_access_hashes={_sha256_bytes(value) for value in last_candidate.values()} | set(expected_hashes.values()),
                    release_hash=None,
                    parent_hashes=(_hash_artifact_map(last_candidate), _hash_artifact_map(protected)),
                )
                if payload.get("operation") == "ROLLBACK" and payload.get("byte_exact_requested") is True:
                    rollback_result = dict(artifacts)
            except _Abort:
                rollback_result = None
        rollback_receipt = _make_rollback_receipt(
            protected,
            last_candidate,
            rollback_result,
            session.protected_intact(),
        )
        abort_core = {
            "version": VERSION,
            "phase": abort.phase,
            "task_id": abort.task_id,
            "reason": abort.reason,
            "fault_injected": abort.reason.startswith("fault injected"),
            "rollback_passed": rollback_receipt["passed"],
            "permanent_state_changed": False if session.protected_intact() else None,
        }
        abort_receipt = {**abort_core, "abort_hash": _sha256_json(abort_core)}
    else:
        abort_receipt = None

    removal_receipt = _make_removal_receipt(session)
    success = abort is None and rollback_receipt["passed"] and session.protected_intact()
    common = {
        "version": VERSION,
        "status": "COMPLETED_SHADOW_EVIDENCE_ONLY" if success else (
            "ABORTED_ROLLBACK_FAILED"
            if not session.protected_intact() or (last_candidate is not None and not rollback_receipt["passed"])
            else "ABORTED_REMOVED"
        ),
        "paper_faithful": False,
        "performance_evidence": False,
        "paper_derived_mechanisms": list(PAPER_DERIVED_MECHANISMS),
        "frankie_added_controls": list(FRANKIE_ADDED_CONTROLS),
        "paper_mechanisms_not_implemented": list(PAPER_MECHANISMS_NOT_IMPLEMENTED),
        "component_contract_passed": success,
        "protected_kb_snapshot_sha256": _hash_artifact_map(protected),
        "protected_kb_hashes": expected_hashes,
        "protected_cohort_manifest_sha256": cohort_manifest_hash,
        "matched_budget_manifest_sha256": budget_manifest_hash,
        "matched_controls": ["FROZEN_BASELINE"],
        "resource_usage": session.used.as_dict(),
        "external_control_bindings": external,
        "task_receipts": task_receipts,
        "artifact_lineage": session.artifacts,
        "lineage_events": session.events,
        "lineage_tip_hash": session.events[-1]["event_hash"] if session.events else _hash_artifact_map(protected),
        "rollback_receipt": rollback_receipt,
        "removal_receipt": removal_receipt,
        "abort_receipt": abort_receipt,
        "candidate_retained": False,
        "automatic_consolidation": False,
        "execution": False,
        "apply": False,
        "promotion": False,
        "explicit_user_authorization_required": True,
        "limitations": (
            "callback attestations do not prove actual gradient training, distillation, or Fisher estimation",
            "rollback covers disposable in-process byte artifacts, not a live deployed system",
            "component-contract success is not held-out performance or promotion evidence",
        ),
    }
    return {**common, "result_hash": _sha256_json(common)}


__all__ = [
    "FRANKIE_ADDED_CONTROLS",
    "PAPER_DERIVED_MECHANISMS",
    "PAPER_MECHANISMS_NOT_IMPLEMENTED",
    "ProgressCompressP0Error",
    "ResourceUsage",
    "ShadowCallbackResult",
    "VERSION",
    "build_release_firewall_receipt",
    "run_progress_compress_shadow",
]
