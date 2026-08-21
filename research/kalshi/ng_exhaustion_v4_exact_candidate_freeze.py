#!/usr/bin/env python3
"""Exact-candidate engineering regression/freeze contract for NG Exhaustion V4.

A passing freeze means only that one exact candidate/workflow/ruleset and its
mechanical dependencies passed the declared engineering checks. It grants no
result-bearing pilot authority, consumes no release holdout, executes none of
the six P0 real evidence receipts, and makes no empirical performance claim.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SCHEMA = "NG_EXHAUSTION_V4_EXACT_CANDIDATE_FREEZE_V1"
REQUIRED_CHECKS = frozenset(
    {
        "FOCUSED_V4_TESTS",
        "UNIFIED_RUNTIME",
        "STATE_ASSEMBLER",
        "PILOT_GUARD_RECONCILER",
        "FRANKIE_APPLICABLE_FULL_SUITE",
        "FRANKIE_SELFTEST",
        "REGISTRY_INVARIANTS",
        "PROTECTED_ARTIFACT_HASHES",
    }
)


class CandidateFreezeError(ValueError):
    pass


def _sha(v: Any, field: str) -> str:
    text = str(v or "").strip().lower()
    if not SHA256_RE.fullmatch(text):
        raise CandidateFreezeError(f"{field} must be lowercase SHA-256")
    return text


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class ExactFreezeIdentity:
    candidate_commit_sha: str
    workflow_sha256: str
    ruleset_sha256: str
    engine_sha256: str
    adapter_sha256: str
    reconciler_sha256: str
    model_sha256: str
    source_manifest_sha256: str

    def validate(self) -> "ExactFreezeIdentity":
        commit = str(self.candidate_commit_sha or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise CandidateFreezeError("candidate_commit_sha must be exact 40-character git SHA")
        for field in (
            "workflow_sha256",
            "ruleset_sha256",
            "engine_sha256",
            "adapter_sha256",
            "reconciler_sha256",
            "model_sha256",
            "source_manifest_sha256",
        ):
            _sha(getattr(self, field), field)
        return self

    @property
    def identity_hash(self) -> str:
        self.validate()
        return _hash({"schema": SCHEMA, "identity": asdict(self)})


@dataclass(frozen=True)
class EngineeringCheck:
    check_id: str
    passed: bool
    receipt_sha256: str
    detail: str

    def validate(self) -> "EngineeringCheck":
        if self.check_id not in REQUIRED_CHECKS:
            raise CandidateFreezeError(f"unknown engineering check: {self.check_id}")
        if self.passed is not True:
            raise CandidateFreezeError(f"engineering check failed: {self.check_id}")
        _sha(self.receipt_sha256, "receipt_sha256")
        if not str(self.detail or "").strip():
            raise CandidateFreezeError("engineering check detail required")
        return self


def freeze_exact_candidate(
    *,
    identity: ExactFreezeIdentity,
    checks: Sequence[EngineeringCheck],
    protected_artifact_hashes: Mapping[str, str],
    release_holdout_consumed: bool,
    v4_empirical_launch_performed: bool,
    p0_real_evidence_executed: bool,
) -> dict[str, Any]:
    identity.validate()
    seen = set()
    rows = []
    for check in checks:
        check.validate()
        if check.check_id in seen:
            raise CandidateFreezeError("duplicate engineering check")
        seen.add(check.check_id)
        rows.append(asdict(check))
    if seen != REQUIRED_CHECKS:
        raise CandidateFreezeError("exact freeze requires every declared engineering check")
    if not protected_artifact_hashes:
        raise CandidateFreezeError("protected artifact hashes required")
    protected = {}
    for path, digest in sorted(protected_artifact_hashes.items()):
        if not str(path or "").strip():
            raise CandidateFreezeError("protected artifact path required")
        protected[path] = _sha(digest, f"protected:{path}")
    if release_holdout_consumed or v4_empirical_launch_performed or p0_real_evidence_executed:
        raise CandidateFreezeError("engineering freeze cannot consume empirical authority")
    core = {
        "schema": SCHEMA,
        "status": "EXACT_CANDIDATE_ENGINEERING_FROZEN_NOT_EMPIRICALLY_AUTHORIZED",
        "identity": asdict(identity),
        "identity_hash": identity.identity_hash,
        "checks": sorted(rows, key=lambda x: x["check_id"]),
        "protected_artifact_hashes": protected,
        "release_holdout_consumed": False,
        "v4_empirical_launch_performed": False,
        "p0_real_evidence_executed": False,
        "result_bearing_pilot_authorized": False,
        "claims_established": [],
    }
    return {**core, "freeze_receipt_hash": _hash(core)}
