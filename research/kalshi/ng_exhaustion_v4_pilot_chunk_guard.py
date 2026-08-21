#!/usr/bin/env python3
"""Fail-closed pilot-manifest / D-year-chunk guard for NG Exhaustion V4.

This is preparation infrastructure only.  It cannot launch a result-bearing V4
pilot, consume the release holdout, establish model quality, or promote Frankie.
A completed D/year chunk may emit its own downstream handoff without waiting for
unrelated sibling chunks, but only after exact child->parent reconciliation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import datetime as dt
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SCHEMA = "NG_EXHAUSTION_V4_PILOT_D_YEAR_CHUNK_V1"
ALLOWED_D = frozenset({"D0", "D1", "D2", "D3", "D4", "D5"})
PIPELINE_CLAIM = "PIPELINE_VERIFIED_FOR_THIS_EXACT_CANDIDATE"
FORBIDDEN_CLAIMS = frozenset(
    {
        "MODEL_SUPERIORITY",
        "CALIBRATION_ADEQUACY",
        "UNIVERSAL_D_LAW",
        "TRADE_EDGE",
        "PERMANENT_FRANKIE_READINESS",
        "D4_D5_POPULATION_VALIDATION",
    }
)


class PilotGuardError(ValueError):
    pass


def _sha(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not SHA256_RE.fullmatch(text):
        raise PilotGuardError(f"{field} must be lowercase SHA-256")
    return text


def _id(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PilotGuardError(f"{field} must be non-empty")
    return text


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


@dataclass(frozen=True)
class ExactCandidateIdentity:
    candidate_sha256: str
    workflow_sha256: str
    ruleset_sha256: str
    engine_sha256: str
    adapter_sha256: str
    reconciler_sha256: str
    model_sha256: str
    source_sha256: str

    def validate(self) -> "ExactCandidateIdentity":
        for field in asdict(self):
            _sha(getattr(self, field), field)
        return self

    @property
    def identity_hash(self) -> str:
        self.validate()
        return _hash({"schema": SCHEMA, "identity": asdict(self)})


@dataclass(frozen=True)
class PilotChunkManifest:
    pilot_id: str
    d_lane: str
    year: int
    start_date: str
    end_date_exclusive: str
    identity: ExactCandidateIdentity
    selection_manifest_sha256: str
    membership_manifest_sha256: str
    child_ids: tuple[str, ...]
    release_holdout_included: bool = False
    frozen_selection: bool = True
    frozen_membership: bool = True
    purpose: str = "MECHANICS_CAUSALITY_PROVENANCE_ARTIFACT_RESTART_RECONCILIATION_ONLY"

    def validate(self) -> "PilotChunkManifest":
        _id(self.pilot_id, "pilot_id")
        if self.d_lane not in ALLOWED_D:
            raise PilotGuardError("pilot must bind exactly one D0-D5 lane")
        if not isinstance(self.year, int) or self.year < 2000:
            raise PilotGuardError("year must be explicit")
        try:
            start = dt.date.fromisoformat(self.start_date)
            end = dt.date.fromisoformat(self.end_date_exclusive)
        except ValueError as exc:
            raise PilotGuardError("pilot dates must be ISO dates") from exc
        if not start < end:
            raise PilotGuardError("pilot date span must be non-empty")
        if start.year != self.year or end > dt.date(self.year + 1, 1, 1):
            raise PilotGuardError("D/year chunk may not cross its declared year")
        self.identity.validate()
        _sha(self.selection_manifest_sha256, "selection_manifest_sha256")
        _sha(self.membership_manifest_sha256, "membership_manifest_sha256")
        if not self.frozen_selection or not self.frozen_membership:
            raise PilotGuardError("pilot selection and chunk membership must be frozen")
        if self.release_holdout_included:
            raise PilotGuardError("virgin/release holdout is forbidden in development pilots")
        children = tuple(_id(x, "child_id") for x in self.child_ids)
        if not children or len(children) != len(set(children)):
            raise PilotGuardError("chunk child_ids must be non-empty and unique")
        return self

    def core(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema": SCHEMA,
            "pilot_id": self.pilot_id,
            "d_lane": self.d_lane,
            "year": self.year,
            "start_date": self.start_date,
            "end_date_exclusive": self.end_date_exclusive,
            "identity": asdict(self.identity),
            "identity_hash": self.identity.identity_hash,
            "selection_manifest_sha256": self.selection_manifest_sha256,
            "membership_manifest_sha256": self.membership_manifest_sha256,
            "child_ids": list(self.child_ids),
            "release_holdout_included": False,
            "frozen_selection": True,
            "frozen_membership": True,
            "purpose": self.purpose,
        }

    @property
    def manifest_hash(self) -> str:
        return _hash(self.core())


@dataclass(frozen=True)
class ResultBearingLaunchAuthorization:
    authorization_id: str
    manifest_hash: str
    identity_hash: str
    candidate_sha256: str
    workflow_sha256: str
    ruleset_sha256: str
    explicitly_result_bearing: bool

    def validate_for(self, manifest: PilotChunkManifest) -> "ResultBearingLaunchAuthorization":
        manifest.validate()
        _id(self.authorization_id, "authorization_id")
        if self.explicitly_result_bearing is not True:
            raise PilotGuardError("generic Proceed is not result-bearing V4 authorization")
        if self.manifest_hash != manifest.manifest_hash:
            raise PilotGuardError("launch authorization manifest mismatch")
        if self.identity_hash != manifest.identity.identity_hash:
            raise PilotGuardError("launch authorization identity mismatch")
        expected = manifest.identity
        if (
            self.candidate_sha256 != expected.candidate_sha256
            or self.workflow_sha256 != expected.workflow_sha256
            or self.ruleset_sha256 != expected.ruleset_sha256
        ):
            raise PilotGuardError("authorization does not name exact candidate/workflow/ruleset")
        return self


def authorize_dispatch(
    manifest: PilotChunkManifest,
    *,
    result_bearing: bool,
    authorization: ResultBearingLaunchAuthorization | None = None,
) -> dict[str, Any]:
    manifest.validate()
    if result_bearing:
        if authorization is None:
            raise PilotGuardError("result-bearing launch requires exact explicit authorization")
        authorization.validate_for(manifest)
    return {
        "status": "SYNTHETIC_GUARDRAIL_DISPATCH_ALLOWED" if not result_bearing else "EXACT_RESULT_BEARING_DISPATCH_AUTHORIZED",
        "manifest_hash": manifest.manifest_hash,
        "identity_hash": manifest.identity.identity_hash,
        "result_bearing": bool(result_bearing),
        "release_holdout_consumed": False,
        "claims_authorized": [] if result_bearing else [PIPELINE_CLAIM],
    }


@dataclass(frozen=True)
class ChildResult:
    child_id: str
    parent_manifest_hash: str
    result_sha256: str
    claim: str = PIPELINE_CLAIM

    def validate(self, manifest: PilotChunkManifest) -> "ChildResult":
        if self.child_id not in set(manifest.child_ids):
            raise PilotGuardError("child result is not in frozen chunk membership")
        if self.parent_manifest_hash != manifest.manifest_hash:
            raise PilotGuardError("child->parent manifest mismatch")
        _sha(self.result_sha256, "result_sha256")
        if self.claim != PIPELINE_CLAIM or self.claim in FORBIDDEN_CLAIMS:
            raise PilotGuardError("pilot result attempted an unauthorized scientific claim")
        return self


def reconcile_chunk(manifest: PilotChunkManifest, results: Sequence[ChildResult]) -> dict[str, Any]:
    manifest.validate()
    if len(results) != len(manifest.child_ids):
        raise PilotGuardError("chunk reconciliation requires every frozen child exactly once")
    seen: set[str] = set()
    rows = []
    for result in results:
        result.validate(manifest)
        if result.child_id in seen:
            raise PilotGuardError("duplicate child result")
        seen.add(result.child_id)
        rows.append(asdict(result))
    if seen != set(manifest.child_ids):
        raise PilotGuardError("child set does not exactly match frozen membership")
    core = {
        "schema": SCHEMA,
        "status": "D_YEAR_CHUNK_RECONCILED",
        "manifest_hash": manifest.manifest_hash,
        "identity_hash": manifest.identity.identity_hash,
        "d_lane": manifest.d_lane,
        "year": manifest.year,
        "children": sorted(rows, key=lambda x: x["child_id"]),
        "claim": PIPELINE_CLAIM,
        "forbidden_claims_established": [],
        "release_holdout_consumed": False,
        "sibling_barrier_required": False,
    }
    return {**core, "reconciliation_hash": _hash(core)}


def emit_downstream_handoff(manifest: PilotChunkManifest, reconciliation: Mapping[str, Any]) -> dict[str, Any]:
    """Permit one completed D/year slice to advance without waiting for sibling slices."""
    manifest.validate()
    if reconciliation.get("status") != "D_YEAR_CHUNK_RECONCILED":
        raise PilotGuardError("downstream handoff requires a reconciled D/year chunk")
    if reconciliation.get("manifest_hash") != manifest.manifest_hash:
        raise PilotGuardError("downstream handoff parent mismatch")
    core = {
        "schema": SCHEMA,
        "status": "D_YEAR_CHUNK_DOWNSTREAM_READY",
        "manifest_hash": manifest.manifest_hash,
        "reconciliation_hash": reconciliation.get("reconciliation_hash"),
        "d_lane": manifest.d_lane,
        "year": manifest.year,
        "sibling_barrier_required": False,
        "result_bearing_launch_authorized": False,
        "claim": PIPELINE_CLAIM,
    }
    return {**core, "handoff_hash": _hash(core)}
