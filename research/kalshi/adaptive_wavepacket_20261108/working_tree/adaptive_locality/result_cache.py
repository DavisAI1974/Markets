"""Exact-key no-clobber offline cache for immutable research artifacts.

Only complete source/contract/policy/direction-bound artifacts are accepted.
Cache hits are NOT scientific equivalence authorization or job suppression.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from .core import LocalityError, _digest
from .checkpoints import seal_snapshot, load_snapshot


@dataclass(frozen=True)
class CacheKey:
    source_identity: str
    input_identity: str
    metric_identity: str
    policy_identity: str
    code_identity: str
    family: str
    direction: str
    artifact_type: str

    def __post_init__(self):
        if any(not isinstance(x, str) or not x for x in self.__dict__.values()):
            raise LocalityError("incomplete cache identity")

    def digest(self) -> str:
        return _digest(self.__dict__)


class OfflineCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, key: CacheKey) -> Path:
        digest = key.digest()
        return self.root / digest[:2] / (digest + ".json")

    def put(self, key: CacheKey, payload: dict) -> str:
        # E-15: the counter must be PRESENT and zero; absence is not assumed to be zero.
        if not isinstance(payload, dict) or "scientific_jobs_eliminated" not in payload:
            raise LocalityError("cache artifact must declare scientific_jobs_eliminated")
        if payload["scientific_jobs_eliminated"] != 0:
            raise LocalityError("cache cannot suppress jobs")
        target = self._path(key)
        artifact_identity = _digest(payload)
        if target.exists():
            existing = load_snapshot(target, source_identity=key.source_identity,
                                     contract_identity=key.digest())
            if existing.get("key") == key.__dict__ and existing.get("artifact_identity") == artifact_identity:
                return "ALREADY_PRESENT"
            raise LocalityError("cache entry exists with a different artifact")
        return seal_snapshot(target,
                             {"key": key.__dict__, "artifact": payload,
                              "artifact_identity": artifact_identity},
                             source_identity=key.source_identity,
                             contract_identity=key.digest())

    def get(self, key: CacheKey) -> dict:
        raw = load_snapshot(self._path(key), source_identity=key.source_identity,
                            contract_identity=key.digest())
        if raw.get("key") != key.__dict__:
            raise LocalityError("cache key mismatch")
        payload = raw.get("artifact")
        if not isinstance(payload, dict) or _digest(payload) != raw.get("artifact_identity"):
            raise LocalityError("cache artifact tampered")
        if payload.get("scientific_jobs_eliminated", 0) != 0:
            raise LocalityError("cache not non-destructive")
        return payload
