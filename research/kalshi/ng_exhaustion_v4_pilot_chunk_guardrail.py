#!/usr/bin/env python3
"""Fail-closed V4 pilot manifest and D/year chunk guardrail.

This module is engineering-only. It does not launch a result-bearing V4 pilot,
consume the release holdout, or establish model/trade claims. Its only positive
pilot claim is PIPELINE_VERIFIED_FOR_THIS_EXACT_CANDIDATE.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import datetime as dt
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

SCHEMA = "NG_EXHAUSTION_V4_PILOT_CHUNK_GUARDRAIL_V1"
ALLOWED_D = {f"D{i}" for i in range(6)}
ALLOWED_CLAIM = "PIPELINE_VERIFIED_FOR_THIS_EXACT_CANDIDATE"
FORBIDDEN_CLAIMS = {
    "MODEL_SUPERIORITY",
    "CALIBRATION_ADEQUACY",
    "UNIVERSAL_D_LAW",
    "TRADE_EDGE",
    "PERMANENT_FRANKIE_READINESS",
    "D4_D5_POPULATION_VALIDATION",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")


class PilotGuardrailError(ValueError):
    pass


def _stable_hash(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _id(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PilotGuardrailError(f"{field} must be non-empty")
    return text


def _sha64(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not HEX64.fullmatch(text):
        raise PilotGuardrailError(f"{field} must be lowercase SHA-256")
    return text


def _commit(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not HEX40.fullmatch(text):
        raise PilotGuardrailError("candidate_commit must be an exact 40-character git SHA")
    return text


@dataclass(frozen=True)
class ExactCandidateBinding:
    candidate_commit: str
    workflow_sha256: str
    ruleset_sha256: str
    engine_sha256: str
    adapter_sha256: str
    reconciler_sha256: str
    model_sha256: str
    source_manifest_sha256: str

    def validate(self) -> "ExactCandidateBinding":
        _commit(self.candidate_commit)
        for field in (
            "workflow_sha256",
            "ruleset_sha256",
            "engine_sha256",
            "adapter_sha256",
            "reconciler_sha256",
            "model_sha256",
            "source_manifest_sha256",
        ):
            _sha64(getattr(self, field), field)
        return self


@dataclass(frozen=True)
class PilotChunkManifest:
    pilot_id: str
    d_stage: str
    calendar_year: int
    start_date: str
    end_date: str
    selection_manifest_sha256: str
    membership_manifest_sha256: str
    parent_manifest_sha256: str
    binding: ExactCandidateBinding
    selection_frozen: bool
    membership_frozen: bool
    release_holdout_consumed: bool
    manifest_hash: str = ""

    def core(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "pilot_id": self.pilot_id,
            "d_stage": self.d_stage,
            "calendar_year": self.calendar_year,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "selection_manifest_sha256": self.selection_manifest_sha256,
            "membership_manifest_sha256": self.membership_manifest_sha256,
            "parent_manifest_sha256": self.parent_manifest_sha256,
            "binding": asdict(self.binding),
            "selection_frozen": self.selection_frozen,
            "membership_frozen": self.membership_frozen,
            "release_holdout_consumed": self.release_holdout_consumed,
            "allowed_claim": ALLOWED_CLAIM,
            "forbidden_claims": sorted(FORBIDDEN_CLAIMS),
        }

    def validate(self) -> "PilotChunkManifest":
        _id(self.pilot_id, "pilot_id")
        if self.d_stage not in ALLOWED_D:
            raise PilotGuardrailError("pilot manifest must contain exactly one D stage")
        try:
            start = dt.date.fromisoformat(self.start_date)
            end = dt.date.fromisoformat(self.end_date)
        except ValueError as exc:
            raise PilotGuardrailError("pilot dates must be ISO YYYY-MM-DD") from exc
        if not start < end:
            raise PilotGuardrailError("pilot date span must satisfy start_date < end_date")
        if start.year != self.calendar_year or end.year != self.calendar_year:
            raise PilotGuardrailError("pilot chunk must stay inside one explicit calendar year")
        for field in (
            "selection_manifest_sha256",
            "membership_manifest_sha256",
            "parent_manifest_sha256",
        ):
            _sha64(getattr(self, field), field)
        self.binding.validate()
        if self.selection_frozen is not True or self.membership_frozen is not True:
            raise PilotGuardrailError("pilot selection and chunk membership must be frozen")
        if self.release_holdout_consumed:
            raise PilotGuardrailError("virgin/release holdout cannot be consumed by a development pilot")
        expected = _stable_hash(self.core())
        if self.manifest_hash and self.manifest_hash != expected:
            raise PilotGuardrailError("pilot manifest hash mismatch")
        return self


def make_manifest(**kwargs: Any) -> PilotChunkManifest:
    manifest = PilotChunkManifest(**kwargs)
    manifest.validate()
    return PilotChunkManifest(**{**asdict(manifest), "binding": manifest.binding, "manifest_hash": _stable_hash(manifest.core())}).validate()


@dataclass(frozen=True)
class ResultLaunchAuthorization:
    authorization_id: str
    candidate_commit: str
    workflow_sha256: str
    ruleset_sha256: str
    pilot_manifest_hash: str
    result_bearing_authorized: bool

    def validate_for(self, manifest: PilotChunkManifest) -> "ResultLaunchAuthorization":
        manifest.validate()
        _id(self.authorization_id, "authorization_id")
        _commit(self.candidate_commit)
        _sha64(self.workflow_sha256, "workflow_sha256")
        _sha64(self.ruleset_sha256, "ruleset_sha256")
        _sha64(self.pilot_manifest_hash, "pilot_manifest_hash")
        expected = manifest.binding
        if self.candidate_commit != expected.candidate_commit:
            raise PilotGuardrailError("launch authorization candidate mismatch")
        if self.workflow_sha256 != expected.workflow_sha256:
            raise PilotGuardrailError("launch authorization workflow mismatch")
        if self.ruleset_sha256 != expected.ruleset_sha256:
            raise PilotGuardrailError("launch authorization ruleset mismatch")
        if self.pilot_manifest_hash != manifest.manifest_hash:
            raise PilotGuardrailError("launch authorization pilot-manifest mismatch")
        if self.result_bearing_authorized is not True:
            raise PilotGuardrailError("result-bearing launch is not explicitly authorized")
        return self


@dataclass(frozen=True)
class ChunkResult:
    chunk_id: str
    parent_manifest_hash: str
    d_stage: str
    calendar_year: int
    start_date: str
    end_date: str
    result_artifact_sha256: str
    status: str
    claims: tuple[str, ...]

    def validate_against(self, manifest: PilotChunkManifest) -> "ChunkResult":
        manifest.validate()
        _id(self.chunk_id, "chunk_id")
        _sha64(self.parent_manifest_hash, "parent_manifest_hash")
        _sha64(self.result_artifact_sha256, "result_artifact_sha256")
        if self.parent_manifest_hash != manifest.manifest_hash:
            raise PilotGuardrailError("child result does not reconcile to exact parent manifest")
        expected = (manifest.d_stage, manifest.calendar_year, manifest.start_date, manifest.end_date)
        actual = (self.d_stage, self.calendar_year, self.start_date, self.end_date)
        if actual != expected:
            raise PilotGuardrailError("child result D/year/date membership drift")
        if self.status not in {"COMPLETE", "BLOCKED", "FAILED", "TIMED_OUT"}:
            raise PilotGuardrailError("invalid chunk result status")
        claims = tuple(str(x).strip() for x in self.claims)
        forbidden = sorted(set(claims) & FORBIDDEN_CLAIMS)
        if forbidden:
            raise PilotGuardrailError(f"forbidden pilot claims requested: {forbidden}")
        if any(x != ALLOWED_CLAIM for x in claims):
            raise PilotGuardrailError("pilot may claim only pipeline verification for this exact candidate")
        return self


def downstream_handoff(manifest: PilotChunkManifest, child: ChunkResult) -> dict[str, Any]:
    """Permit one completed D/year chunk to advance without waiting for siblings."""
    child.validate_against(manifest)
    if child.status != "COMPLETE":
        return {
            "status": "NOT_READY_FOR_DOWNSTREAM",
            "chunk_id": child.chunk_id,
            "reason": child.status,
            "wait_for_other_chunks": False,
        }
    return {
        "status": "READY_FOR_DOWNSTREAM",
        "chunk_id": child.chunk_id,
        "parent_manifest_hash": manifest.manifest_hash,
        "result_artifact_sha256": child.result_artifact_sha256,
        "d_stage": child.d_stage,
        "calendar_year": child.calendar_year,
        "wait_for_other_chunks": False,
        "claim": ALLOWED_CLAIM,
        "release_holdout_consumed": False,
    }


def reconcile_children(parent: PilotChunkManifest, children: Sequence[ChunkResult]) -> dict[str, Any]:
    """Recompute child->parent identity; aggregate completion is never required for streaming."""
    parent.validate()
    seen: set[str] = set()
    ready: list[str] = []
    blocked: list[str] = []
    for child in children:
        child.validate_against(parent)
        if child.chunk_id in seen:
            raise PilotGuardrailError("duplicate child chunk_id")
        seen.add(child.chunk_id)
        (ready if child.status == "COMPLETE" else blocked).append(child.chunk_id)
    return {
        "status": "CHILD_PARENT_RECONCILED",
        "parent_manifest_hash": parent.manifest_hash,
        "ready_children": sorted(ready),
        "nonready_children": sorted(blocked),
        "streaming_downstream_allowed": True,
        "aggregate_barrier_required": False,
        "release_holdout_consumed": False,
    }


if __name__ == "__main__":
    print("V4 PILOT CHUNK GUARDRAIL MODULE READY; NO EMPIRICAL LAUNCH")
