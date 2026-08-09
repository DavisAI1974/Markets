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

SCHEMA_VERSION = "1.0"
EXECUTION_ENABLED = False
APPLY_ALLOWED = False

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
        if baseline and not candidate:
            cls = "PASS_TO_FAIL"
        elif not baseline and candidate:
            cls = "FAIL_TO_PASS"
        elif baseline and candidate:
            cls = "UNCHANGED_PASS"
        else:
            cls = "UNCHANGED_FAIL"
        flips.append(FlipRecord(case_id, baseline, candidate, cls))
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
    held_out_rows: Sequence[Mapping[str, Any]],
) -> ReleaseEvaluation:
    """Strict RSEA/AgentDevel gate: no pass->fail regression, and at least one fix."""
    flips = classify_flips(held_out_rows)
    counts = {name: sum(1 for flip in flips if flip.class_name == name) for name in (
        "PASS_TO_FAIL", "FAIL_TO_PASS", "UNCHANGED_PASS", "UNCHANGED_FAIL"
    )}
    reasons: list[str] = []
    verdict = "REJECT"

    if not split_precommitted:
        reasons.append("held-out split was not precommitted")
    if candidate.source_trial_required and not isolated_trial_worker:
        reasons.append("source-affecting candidate was not tested in an isolated trial worker")
    if not required_tests_passed:
        reasons.append("required deterministic tests failed")
    if counts["PASS_TO_FAIL"]:
        reasons.append(f"non-regression gate failed: {counts['PASS_TO_FAIL']} pass-to-fail flips")
    if counts["FAIL_TO_PASS"] == 0:
        reasons.append("candidate produced no held-out fail-to-pass improvement")

    if not reasons:
        verdict = "SANDBOX_RELEASE_ELIGIBLE"
        reasons.append("precommitted held-out keep-better gate passed with zero regressions")

    core = {
        "candidate_hash": candidate.candidate_hash,
        "parent_version": candidate.parent_version,
        "held_out_split_id": safe_id(held_out_split_id),
        "split_precommitted": bool(split_precommitted),
        "isolated_trial_worker": bool(isolated_trial_worker),
        "required_tests_passed": bool(required_tests_passed),
        "flips": flips,
        "pass_to_fail": counts["PASS_TO_FAIL"],
        "fail_to_pass": counts["FAIL_TO_PASS"],
        "unchanged_pass": counts["UNCHANGED_PASS"],
        "unchanged_fail": counts["UNCHANGED_FAIL"],
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
