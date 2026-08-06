"""Bounded self-improvement for Frankie.

Frankie may learn from evidence and propose a versioned change. He may not apply it.
A separate reasoning lane critiques the proposal; deterministic code decides whether it is
eligible for a sandbox branch. Production promotion remains an ordinary reviewed Git PR.
"""
from __future__ import annotations

import dataclasses
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from frankie_backends import ReasoningBackend
from frankie_core import (
    BackendError,
    FrankieConfig,
    GateStop,
    atomic_write_json,
    load_json,
    parse_iso,
    safe_id,
    sha256_json,
    utc_now,
    verify_original_spawn,
)

ALLOWED_COMPONENTS = {
    "candidate_registry",
    "reasoning_prompt",
    "analog_retrieval",
    "research_tool",
    "test_harness",
    "data_contract",
    "calibration_report",
}
ALLOWED_REVIEW = {"SANDBOX_ELIGIBLE", "REVISE", "REJECT"}
FORBIDDEN_PATH_TOKENS = {
    "spawn.py",
    "creds.py",
    "kalshi_auth.py",
    "order_router",
    "execution_router",
    "live_executor",
    "risk_gate",
    "risk_service",
    "private_key",
    "markets.env",
}
MAX_EVIDENCE_FILES = 100
MAX_EVIDENCE_BYTES = 8_000_000


@dataclass(frozen=True)
class ImprovementProposal:
    proposal_id: str
    created_at_utc: str
    target_component: str
    hypothesis: str
    change_summary: str
    evidence_refs: tuple[str, ...]
    requested_files: tuple[str, ...]
    expected_benefit: str
    falsifiers: tuple[str, ...]
    test_plan: tuple[str, ...]
    untouched_forward_gate: str
    rollback_plan: str
    execution_enabled: bool
    apply_allowed: bool
    proposal_hash: str

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class ImprovementReview:
    backend: str
    verdict: str
    reasons: tuple[str, ...]
    required_tests: tuple[str, ...]
    leakage_risks: tuple[str, ...]
    execution_risks: tuple[str, ...]
    review_hash: str

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _strings(raw: Mapping[str, Any], name: str, *, required: bool = True) -> tuple[str, ...]:
    value = raw.get(name)
    if value is None and not required:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise BackendError(f"improvement field {name} must be a non-empty string list")
    return tuple(v.strip() for v in value)


def _forbidden_file(path: str) -> str | None:
    lower = path.replace("\\", "/").lower()
    for token in FORBIDDEN_PATH_TOKENS:
        if token in lower:
            return token
    return None


def validate_proposal(
    raw: Mapping[str, Any],
    *,
    evidence_hashes: set[str],
    resolved_hashes: set[str],
) -> ImprovementProposal:
    required = (
        "target_component",
        "hypothesis",
        "change_summary",
        "evidence_refs",
        "requested_files",
        "expected_benefit",
        "falsifiers",
        "test_plan",
        "untouched_forward_gate",
        "rollback_plan",
    )
    missing = [name for name in required if not raw.get(name)]
    if missing:
        raise BackendError(f"improvement proposal missing: {', '.join(missing)}")
    component = str(raw["target_component"])
    if component not in ALLOWED_COMPONENTS:
        raise BackendError(f"forbidden improvement component: {component}")
    evidence_refs = _strings(raw, "evidence_refs")
    unknown = sorted(set(evidence_refs) - evidence_hashes)
    if unknown:
        raise BackendError(f"proposal cites unknown evidence hashes: {', '.join(unknown)}")
    if not set(evidence_refs).intersection(resolved_hashes):
        raise GateStop(
            "self-improvement requires at least one cited evidence record with an immutable "
            "resolved-outcome sidecar"
        )
    requested_files = _strings(raw, "requested_files")
    forbidden = [(path, _forbidden_file(path)) for path in requested_files if _forbidden_file(path)]
    if forbidden:
        detail = ", ".join(f"{path} ({token})" for path, token in forbidden)
        raise GateStop(f"self-improvement requested forbidden files: {detail}")
    if raw.get("execution_enabled") is True or raw.get("apply_allowed") is True:
        raise GateStop("self-improvement attempted to grant itself execution or apply authority")
    core = {
        "proposal_id": safe_id(str(raw.get("proposal_id") or f"frankie-{uuid.uuid4()}")),
        "created_at_utc": utc_now().isoformat(timespec="seconds").replace("+00:00", "Z"),
        "target_component": component,
        "hypothesis": str(raw["hypothesis"]),
        "change_summary": str(raw["change_summary"]),
        "evidence_refs": evidence_refs,
        "requested_files": requested_files,
        "expected_benefit": str(raw["expected_benefit"]),
        "falsifiers": _strings(raw, "falsifiers"),
        "test_plan": _strings(raw, "test_plan"),
        "untouched_forward_gate": str(raw["untouched_forward_gate"]),
        "rollback_plan": str(raw["rollback_plan"]),
        "execution_enabled": False,
        "apply_allowed": False,
    }
    return ImprovementProposal(**core, proposal_hash=sha256_json(core))


def validate_review(raw: Mapping[str, Any], *, backend: str) -> ImprovementReview:
    verdict = str(raw.get("verdict") or "").upper()
    if verdict not in ALLOWED_REVIEW:
        raise BackendError(f"invalid improvement review verdict: {verdict}")
    core = {
        "backend": backend,
        "verdict": verdict,
        "reasons": _strings(raw, "reasons"),
        "required_tests": _strings(raw, "required_tests"),
        "leakage_risks": _strings(raw, "leakage_risks", required=False),
        "execution_risks": _strings(raw, "execution_risks", required=False),
    }
    return ImprovementReview(**core, review_hash=sha256_json(core))


def record_outcome(
    *,
    evidence_path: Path,
    outcome: Mapping[str, Any],
    config: FrankieConfig,
) -> dict[str, Any]:
    """Write an immutable outcome sidecar; never edit the original decision envelope."""
    evidence = load_json(evidence_path)
    if not isinstance(evidence, dict) or not isinstance(evidence.get("decision"), dict):
        raise GateStop("evidence envelope must contain a decision object")
    decision = evidence["decision"]
    decision_hash = str(decision.get("decision_hash") or "")
    if not decision_hash:
        raise GateStop("evidence decision is missing decision_hash")
    if outcome.get("execution_enabled") is True:
        raise GateStop("outcome attempted to enable execution")
    for key in ("resolved_at", "result", "source_provenance"):
        if not outcome.get(key):
            raise GateStop(f"outcome missing required field: {key}")
    resolved_at = parse_iso(str(outcome["resolved_at"]))
    provenance = outcome["source_provenance"]
    if not isinstance(provenance, list) or not provenance:
        raise GateStop("outcome source_provenance must be a non-empty list")
    for index, source in enumerate(provenance):
        if not isinstance(source, dict):
            raise GateStop(f"outcome source_provenance[{index}] must be an object")
        for key in ("source", "knowable_at", "content_hash"):
            if not source.get(key):
                raise GateStop(f"outcome source_provenance[{index}] missing {key}")
        parse_iso(str(source["knowable_at"]))
    core = {
        "schema_version": "1.0",
        "decision_hash": decision_hash,
        "evidence_envelope_hash": str(evidence.get("envelope_hash") or sha256_json(evidence)),
        "event_id": decision.get("event_id"),
        "candidate_id": decision.get("candidate_id"),
        "resolved_at": resolved_at.isoformat().replace("+00:00", "Z"),
        "result": str(outcome["result"]),
        "metrics": dict(outcome.get("metrics") or {}),
        "source_provenance": provenance,
        "notes": str(outcome.get("notes") or ""),
        "execution_enabled": False,
    }
    sidecar = {**core, "outcome_hash": sha256_json(core)}
    path = config.evidence_root.parent / "outcomes" / f"{decision_hash}.json"
    if path.exists():
        existing = load_json(path)
        if existing != sidecar:
            raise GateStop(
                f"outcome sidecar already exists with different content: {path}. "
                "Outcomes are append-only; write a correction record rather than overwriting."
            )
        return {"outcome_path": str(path), **existing}
    atomic_write_json(path, sidecar)
    return {"outcome_path": str(path), **sidecar}


def load_evidence(
    paths: Sequence[Path],
    *,
    config: FrankieConfig,
) -> tuple[list[dict[str, Any]], set[str]]:
    if not paths:
        raise GateStop("at least one evidence file is required")
    if len(paths) > MAX_EVIDENCE_FILES:
        raise GateStop(f"too many evidence files: {len(paths)} > {MAX_EVIDENCE_FILES}")
    total = sum(path.stat().st_size for path in paths if path.is_file())
    if total > MAX_EVIDENCE_BYTES:
        raise GateStop(f"evidence package too large: {total} > {MAX_EVIDENCE_BYTES}")
    records: list[dict[str, Any]] = []
    hashes: set[str] = set()
    for path in paths:
        raw = load_json(path)
        if not isinstance(raw, dict):
            raise GateStop(f"evidence file must contain an object: {path}")
        envelope_hash = str(raw.get("envelope_hash") or sha256_json(raw))
        decision = raw.get("decision") if isinstance(raw.get("decision"), dict) else {}
        decision_hash = str(decision.get("decision_hash") or "")
        sidecar_path = config.evidence_root.parent / "outcomes" / f"{decision_hash}.json"
        outcome = load_json(sidecar_path) if decision_hash and sidecar_path.exists() else None
        records.append(
            {
                "path": str(path),
                "envelope_hash": envelope_hash,
                "decision": decision or None,
                "event": raw.get("event"),
                "outcome": outcome,
                "outcome_status": "RESOLVED" if outcome else "AWAITING_OUTCOME",
            }
        )
        hashes.add(envelope_hash)
    return records, hashes


PROPOSAL_INSTRUCTIONS = """You are Frankie's improvement-proposal lane. Diagnose repeated misses,
false positives, missing evidence, retrieval failures, or cost-gate failures from the supplied
immutable evidence and resolved outcome sidecars. Propose exactly one bounded change. You cannot edit
code, apply a patch, weaken a gate, modify spawn.py, touch credentials/risk/execution, choose a result
after seeing a holdout, or grant authority. Do not claim learning from records marked
AWAITING_OUTCOME. Return one JSON object only. Evidence references must be exact envelope hashes."""

REVIEW_INSTRUCTIONS = """You are the independent critic of a Frankie self-improvement proposal.
Try to falsify it. Check leakage, post-hoc fitting, threshold tuning, unresolved outcomes, duplicated
evidence, missing nulls, contract mismatch, execution-safety creep, and whether the test can fail.
You cannot apply or rewrite the proposal. Return one JSON object only."""


def propose_improvement(
    *,
    evidence_paths: Sequence[Path],
    proposer: ReasoningBackend,
    critic: ReasoningBackend,
    config: FrankieConfig,
) -> dict[str, Any]:
    origin = verify_original_spawn()
    records, hashes = load_evidence(evidence_paths, config=config)
    resolved_hashes = {
        record["envelope_hash"] for record in records if record["outcome_status"] == "RESOLVED"
    }
    proposal_schema = {
        "target_component": sorted(ALLOWED_COMPONENTS),
        "hypothesis": "specific causal diagnosis",
        "change_summary": "one bounded proposed change",
        "evidence_refs": ["exact envelope hash"],
        "requested_files": ["paths a human sandbox PR may change"],
        "expected_benefit": "measurable expected improvement",
        "falsifiers": ["conditions that kill the proposal"],
        "test_plan": ["replay, null, holdout, cost, and shadow steps"],
        "untouched_forward_gate": "precommitted forward requirement",
        "rollback_plan": "how a human reverts the version",
        "execution_enabled": False,
        "apply_allowed": False,
    }
    raw_proposal = proposer.generate(
        instructions=PROPOSAL_INSTRUCTIONS,
        prompt=json.dumps(
            {
                "agent": "Frankie",
                "origin": origin,
                "evidence": records,
                "required_schema": proposal_schema,
                "forbidden_path_tokens": sorted(FORBIDDEN_PATH_TOKENS),
            },
            indent=2,
            sort_keys=True,
        ),
    )
    proposal = validate_proposal(
        raw_proposal,
        evidence_hashes=hashes,
        resolved_hashes=resolved_hashes,
    )
    raw_review = critic.generate(
        instructions=REVIEW_INSTRUCTIONS,
        prompt=json.dumps(
            {
                "proposal": proposal.as_dict(),
                "evidence_outcome_status": {
                    record["envelope_hash"]: record["outcome_status"] for record in records
                },
                "required_schema": {
                    "verdict": sorted(ALLOWED_REVIEW),
                    "reasons": ["reason"],
                    "required_tests": ["test"],
                    "leakage_risks": ["risk"],
                    "execution_risks": ["risk"],
                },
            },
            indent=2,
            sort_keys=True,
        ),
    )
    review = validate_review(raw_review, backend=critic.name)
    state = "SANDBOX_ELIGIBLE" if review.verdict == "SANDBOX_ELIGIBLE" else review.verdict
    envelope = {
        "schema_version": "1.0",
        "agent": "Frankie",
        "state": state,
        "execution_enabled": False,
        "apply_allowed": False,
        "proposal": proposal.as_dict(),
        "review": review.as_dict(),
        "origin": origin,
    }
    envelope["envelope_hash"] = sha256_json(envelope)
    output = config.evidence_root.parent / "proposals" / "pending" / (
        f"{proposal.proposal_id}_{proposal.proposal_hash[:16]}.json"
    )
    atomic_write_json(output, envelope)
    return {"proposal_path": str(output), **envelope}
