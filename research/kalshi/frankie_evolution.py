"""Frankie's bounded harness-evolution and release-engineering layer.

Research grounding:
- Adaptive Auto-Harness: route heterogeneous/open-ended task streams through a harness tree.
- RSEA: evolve strategy/skills/playbook, but keep a candidate only after disjoint held-out selection.
- MOSS: source-level changes are more expressive, but must run in isolated trial workers before promotion.
- AgentDevel: maintain one canonical version line and treat pass->fail flips as first-class regressions.
- Self-Improvement Survey: make the mutable scaffold surface explicit and auditable.

This module NEVER edits source, opens a PR, changes credentials, or enables execution.
It produces versioned candidate/release artifacts for human-reviewed sandbox work.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from frankie_core import GateStop, atomic_write_json, safe_id, sha256_json
from frankie_evaluation_controls import SHA256_RE, validate_release_exposure_audit

SCHEMA_VERSION = "1.0"
EXECUTION_ENABLED = False
APPLY_ALLOWED = False
MIN_RELEASE_CASES = 30
MIN_RELEASE_FIXES = 5
MIN_RELEASE_OBSERVED_STRATUM_CASES = 5

MUTABLE_SCAFFOLD_SURFACES = {
    "strategy",
    "skills",
    "playbook",
    "reasoning_prompt",
    "analog_retrieval",
    "research_tool",
    "data_contract",
    "test_harness",
    "candidate_registry",
    "calibration_report",
}

SOURCE_TRIAL_SURFACES = {
    "research_tool",
    "test_harness",
    "analog_retrieval",
}

FORBIDDEN_RELEASE_TARGETS = {
    "spawn.py",
    "agent_frankie.py",
    "frankie_core.py",
    "frankie_backends.py",
    "frankie_engine.py",
    "frankie_cognition.py",
    "frankie_cognitive_candidates.py",
    "frankie_cognitive_experiments.py",
    "frankie_idempotency.py",
    "frankie_improve.py",
    "frankie_evolution.py",
    "creds.py",
    "kalshi_auth.py",
    "risk_gate",
    "risk_service",
    "order_router",
    "execution_router",
    "live_executor",
    ".github/",
    "deploy/",
}


@dataclass(frozen=True)
class HarnessState:
    strategy: str
    skills: tuple[str, ...]
    playbook: tuple[str, ...]


@dataclass(frozen=True)
class HarnessCandidate:
    candidate_id: str
    created_at_utc: str
    parent_version: str
    task_route: str
    mutable_surfaces: tuple[str, ...]
    harness_state: HarnessState
    evidence_refs: tuple[str, ...]
    hypothesis: str
    requested_files: tuple[str, ...]
    source_trial_required: bool
    human_steering_note: str | None
    execution_enabled: bool
    apply_allowed: bool
    candidate_hash: str

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class FlipRecord:
    case_id: str
    baseline_pass: bool
    candidate_pass: bool
    class_name: str
    protected: bool
    candidate_catastrophic: bool
    strata: dict[str, str]


@dataclass(frozen=True)
class ReleaseEvaluation:
    candidate_hash: str
    parent_version: str
    held_out_split_id: str
    split_precommitted: bool
    isolated_trial_worker: bool
    required_tests_passed: bool
    flips: tuple[FlipRecord, ...]
    pass_to_fail: int
    fail_to_pass: int
    unchanged_pass: int
    unchanged_fail: int
    protected_failures: int
    catastrophic_failures: int
    stratum_counts: dict[str, dict[str, int]]
    locked_evaluator_id: str
    locked_evaluator_hash: str
    evaluator_locked: bool
    permissions_locked: bool
    rollback_verified: bool
    rollback_artifact_hash: str
    untouched_forward: bool
    release_split_reuse_count: int
    holdout_firewall_passed: bool
    holdout_exposure_audit_hash: str | None
    verdict: str
    reasons: tuple[str, ...]
    execution_enabled: bool
    apply_allowed: bool
    evaluation_hash: str

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _str_list(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v.strip() for v in value):
        raise GateStop(f"{name} must be a non-empty string list")
    return tuple(v.strip() for v in value)


def _validate_target(path: str) -> None:
    normalized = path.replace("\\", "/").strip()
    if not normalized or normalized.startswith("/") or ".." in Path(normalized).parts:
        raise GateStop(f"invalid release target: {path}")
    lower = normalized.lower()
    if any(token in lower for token in FORBIDDEN_RELEASE_TARGETS):
        raise GateStop(f"forbidden release target: {path}")
    if not (normalized.startswith("research/kalshi/") or normalized == "dashboard/novel_candidates.json"):
        raise GateStop(f"release target outside Frankie research scope: {path}")


def build_candidate(raw: Mapping[str, Any], *, evidence_hashes: set[str]) -> HarnessCandidate:
    for key in (
        "parent_version",
        "task_route",
        "mutable_surfaces",
        "strategy",
        "skills",
        "playbook",
        "evidence_refs",
        "hypothesis",
        "requested_files",
    ):
        if not raw.get(key):
            raise GateStop(f"harness candidate missing {key}")

    surfaces = _str_list(raw["mutable_surfaces"], "mutable_surfaces")
    unknown = sorted(set(surfaces) - MUTABLE_SCAFFOLD_SURFACES)
    if unknown:
        raise GateStop(f"unknown mutable scaffold surfaces: {', '.join(unknown)}")

    refs = _str_list(raw["evidence_refs"], "evidence_refs")
    missing_refs = sorted(set(refs) - evidence_hashes)
    if missing_refs:
        raise GateStop(f"candidate cites unknown evidence: {', '.join(missing_refs)}")

    files = _str_list(raw["requested_files"], "requested_files")
    for path in files:
        _validate_target(path)

    source_trial_required = bool(set(surfaces).intersection(SOURCE_TRIAL_SURFACES))
    if raw.get("execution_enabled") is True or raw.get("apply_allowed") is True:
        raise GateStop("harness candidate attempted to grant itself authority")

    state = HarnessState(
        strategy=str(raw["strategy"]).strip(),
        skills=_str_list(raw["skills"], "skills"),
        playbook=_str_list(raw["playbook"], "playbook"),
    )
    core = {
        "candidate_id": safe_id(str(raw.get("candidate_id") or f"harness-{uuid.uuid4()}")),
        "created_at_utc": _now(),
        "parent_version": str(raw["parent_version"]),
        "task_route": safe_id(str(raw["task_route"])),
        "mutable_surfaces": surfaces,
        "harness_state": state,
        "evidence_refs": refs,
        "hypothesis": str(raw["hypothesis"]),
        "requested_files": files,
        "source_trial_required": source_trial_required,
        "human_steering_note": str(raw["human_steering_note"]) if raw.get("human_steering_note") else None,
        "execution_enabled": False,
        "apply_allowed": False,
    }
    hash_core = {**core, "harness_state": dataclasses.asdict(state)}
    return HarnessCandidate(**core, candidate_hash=sha256_json(hash_core))


def classify_flips(rows: Sequence[Mapping[str, Any]]) -> tuple[FlipRecord, ...]:
    flips: list[FlipRecord] = []
    seen: set[str] = set()
    for row in rows:
        case_id = safe_id(str(row.get("case_id") or ""))
        if not case_id or case_id in seen:
            raise GateStop("held-out cases require unique non-empty case_id")
        seen.add(case_id)
        if not isinstance(row.get("baseline_pass"), bool) or not isinstance(row.get("candidate_pass"), bool):
            raise GateStop(f"held-out case {case_id} requires boolean pass states")
        baseline = row["baseline_pass"]
        candidate = row["candidate_pass"]
        protected = bool(row.get("protected", False))
        catastrophic = bool(row.get("candidate_catastrophic", False))
        if protected and not baseline:
            raise GateStop(f"protected held-out case {case_id} must pass on the frozen baseline")
        strata_raw = row.get("strata")
        if not isinstance(strata_raw, Mapping):
            raise GateStop(f"held-out case {case_id} requires strata")
        strata: dict[str, str] = {}
        for name in ("task", "regime", "safety", "provenance"):
            value = str(strata_raw.get(name) or "").strip()
            if not value:
                raise GateStop(f"held-out case {case_id} missing stratum {name}")
            strata[name] = value
        if baseline and not candidate:
            cls = "PASS_TO_FAIL"
        elif not baseline and candidate:
            cls = "FAIL_TO_PASS"
        elif baseline and candidate:
            cls = "UNCHANGED_PASS"
        else:
            cls = "UNCHANGED_FAIL"
        flips.append(FlipRecord(case_id, baseline, candidate, cls, protected, catastrophic, strata))
    if not flips:
        raise GateStop("release evaluation requires held-out cases")
    return tuple(flips)


def evaluate_release(
    candidate: HarnessCandidate,
    *,
    held_out_split_id: str,
    split_precommitted: bool,
    isolated_trial_worker: bool,
    required_tests_passed: bool,
    locked_evaluator_id: str,
    locked_evaluator_hash: str,
    evaluator_locked: bool,
    permissions_locked: bool,
    rollback_verified: bool,
    rollback_artifact_hash: str,
    untouched_forward: bool,
    release_split_reuse_count: int,
    held_out_split_hash: str,
    release_exposure_audit: Mapping[str, Any] | None,
    held_out_rows: Sequence[Mapping[str, Any]],
) -> ReleaseEvaluation:
    """Strict RSEA/AgentDevel gate: no pass->fail regression, and at least one fix."""
    flips = classify_flips(held_out_rows)
    counts = {name: sum(1 for flip in flips if flip.class_name == name) for name in (
        "PASS_TO_FAIL", "FAIL_TO_PASS", "UNCHANGED_PASS", "UNCHANGED_FAIL"
    )}
    protected_failures = sum(1 for flip in flips if flip.protected and not flip.candidate_pass)
    catastrophic_failures = sum(1 for flip in flips if flip.candidate_catastrophic)
    stratum_counts: dict[str, dict[str, int]] = {
        name: {} for name in ("task", "regime", "safety", "provenance")
    }
    for flip in flips:
        for name, value in flip.strata.items():
            stratum_counts[name][value] = stratum_counts[name].get(value, 0) + 1
    if isinstance(release_split_reuse_count, bool) or release_split_reuse_count < 0:
        raise GateStop("release_split_reuse_count must be a non-negative integer")
    reasons: list[str] = []
    verdict = "REJECT"
    normalized_split_id = safe_id(held_out_split_id)
    normalized_evaluator_id = safe_id(locked_evaluator_id)
    holdout_firewall_passed = False
    holdout_exposure_audit_hash = None

    if not isinstance(release_exposure_audit, Mapping):
        reasons.append("release holdout exposure audit was not supplied")
    else:
        try:
            holdout_exposure_audit_hash = validate_release_exposure_audit(
                release_exposure_audit,
                split_id=normalized_split_id,
                split_hash=held_out_split_hash,
                expected_consumer=normalized_evaluator_id,
                required_parent_hashes=(
                    candidate.candidate_hash,
                    locked_evaluator_hash,
                    rollback_artifact_hash,
                ),
            )
            holdout_firewall_passed = True
        except ValueError as exc:
            reasons.append(f"release holdout exposure firewall failed: {exc}")

    if not split_precommitted:
        reasons.append("held-out split was not precommitted")
    if len(flips) < MIN_RELEASE_CASES:
        reasons.append(f"release cohort is underpowered: {len(flips)} < {MIN_RELEASE_CASES}")
    sparse_strata = [
        f"{name}={value}:{count}"
        for name, values in stratum_counts.items()
        for value, count in values.items()
        if count < MIN_RELEASE_OBSERVED_STRATUM_CASES
    ]
    if sparse_strata:
        reasons.append("under-supported observed strata: " + ", ".join(sorted(sparse_strata)))
    if release_split_reuse_count:
        reasons.append(f"release split was reused {release_split_reuse_count} time(s)")
    if candidate.source_trial_required and not isolated_trial_worker:
        reasons.append("source-affecting candidate was not tested in an isolated trial worker")
    if not required_tests_passed:
        reasons.append("required deterministic tests failed")
    if not evaluator_locked:
        reasons.append("candidate evaluator was not locked outside the mutable surface")
    if not SHA256_RE.fullmatch(str(locked_evaluator_hash or "")):
        reasons.append("locked evaluator artifact hash is missing or invalid")
    if not permissions_locked:
        reasons.append("candidate permissions were not locked outside the mutable surface")
    if not rollback_verified:
        reasons.append("rollback was not verified")
    if not SHA256_RE.fullmatch(str(rollback_artifact_hash or "")):
        reasons.append("rollback artifact hash is missing or invalid")
    if not untouched_forward:
        reasons.append("untouched-forward shadow gate was not completed")
    if counts["PASS_TO_FAIL"]:
        reasons.append(f"non-regression gate failed: {counts['PASS_TO_FAIL']} pass-to-fail flips")
    if protected_failures:
        reasons.append(f"protected-case gate failed: {protected_failures} failures")
    if catastrophic_failures:
        reasons.append(f"catastrophic-case gate failed: {catastrophic_failures} failures")
    if counts["FAIL_TO_PASS"] < MIN_RELEASE_FIXES:
        reasons.append(
            f"candidate produced insufficient held-out fixes: "
            f"{counts['FAIL_TO_PASS']} < {MIN_RELEASE_FIXES}"
        )

    if not reasons:
        verdict = "SANDBOX_RELEASE_ELIGIBLE"
        reasons.append("precommitted held-out keep-better gate passed with zero regressions")

    core = {
        "candidate_hash": candidate.candidate_hash,
        "parent_version": candidate.parent_version,
        "held_out_split_id": normalized_split_id,
        "split_precommitted": bool(split_precommitted),
        "isolated_trial_worker": bool(isolated_trial_worker),
        "required_tests_passed": bool(required_tests_passed),
        "flips": flips,
        "pass_to_fail": counts["PASS_TO_FAIL"],
        "fail_to_pass": counts["FAIL_TO_PASS"],
        "unchanged_pass": counts["UNCHANGED_PASS"],
        "unchanged_fail": counts["UNCHANGED_FAIL"],
        "protected_failures": protected_failures,
        "catastrophic_failures": catastrophic_failures,
        "stratum_counts": stratum_counts,
        "locked_evaluator_id": normalized_evaluator_id,
        "locked_evaluator_hash": locked_evaluator_hash,
        "evaluator_locked": bool(evaluator_locked),
        "permissions_locked": bool(permissions_locked),
        "rollback_verified": bool(rollback_verified),
        "rollback_artifact_hash": rollback_artifact_hash,
        "untouched_forward": bool(untouched_forward),
        "release_split_reuse_count": int(release_split_reuse_count),
        "holdout_firewall_passed": holdout_firewall_passed,
        "holdout_exposure_audit_hash": holdout_exposure_audit_hash,
        "verdict": verdict,
        "reasons": tuple(reasons),
        "execution_enabled": False,
        "apply_allowed": False,
    }
    hash_core = {**core, "flips": [dataclasses.asdict(flip) for flip in flips]}
    return ReleaseEvaluation(**core, evaluation_hash=sha256_json(hash_core))


def write_candidate(root: Path, candidate: HarnessCandidate) -> Path:
    path = root / "harness" / "candidates" / f"{candidate.candidate_id}_{candidate.candidate_hash[:16]}.json"
    atomic_write_json(path, candidate.as_dict())
    return path


def write_release_evaluation(root: Path, evaluation: ReleaseEvaluation) -> Path:
    path = root / "harness" / "release_evaluations" / f"{evaluation.evaluation_hash[:24]}.json"
    atomic_write_json(path, evaluation.as_dict())
    return path
