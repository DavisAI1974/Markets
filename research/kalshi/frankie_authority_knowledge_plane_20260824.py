#!/usr/bin/env python3
"""Lossless authority-gated knowledge plane for the blind October Frankie run.

This module is deliberately additive.  It does not import the obsolete October
bridge and it never parses sealed Step-1 sources before the primary-output
freeze.  Source bytes are hashed into an immutable catalog; retrieval is routed
through typed methods that always emit identity-bound receipts.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence


# This file is intentionally runnable from ``research/kalshi`` as well as
# importable through ``research.kalshi``.  Register the first import under both
# names before defining enums; otherwise Python can create two incompatible
# RetrievalLane/AuthorityClass identities in one process.
_MODULE_ALIASES = {
    "frankie_authority_knowledge_plane_20260824",
    "research.kalshi.frankie_authority_knowledge_plane_20260824",
}
for _module_alias in _MODULE_ALIASES:
    sys.modules.setdefault(_module_alias, sys.modules[__name__])


class AuthorityClass(str, Enum):
    BINDING_CURRENT = "BINDING_CURRENT"
    CURRENT_BRAIN = "CURRENT_BRAIN"
    FROZEN_LEARNED_KNOWLEDGE = "FROZEN_LEARNED_KNOWLEDGE"
    EXTRA_AGENT_CARRYFORWARD = "EXTRA_AGENT_CARRYFORWARD"
    PROVISIONAL_SHADOW = "PROVISIONAL_SHADOW"
    ARCHIVE_NOT_SERVABLE = "ARCHIVE_NOT_SERVABLE"
    SEALED_TARGET_ANSWER = "SEALED_TARGET_ANSWER"


class AccessPolicy(str, Enum):
    SERVE = "SERVE"
    SHADOW_ONLY = "SHADOW_ONLY"
    DENY = "DENY"
    SEALED_UNTIL_PRIMARY_FREEZE = "SEALED_UNTIL_PRIMARY_FREEZE"


class TargetRelationship(str, Enum):
    GENERAL = "GENERAL"
    OCTOBER_TARGET_PERIOD = "OCTOBER_TARGET_PERIOD"
    OCTOBER_STEP1_ANSWER = "OCTOBER_STEP1_ANSWER"


class RetrievalLane(str, Enum):
    PRIMARY = "PRIMARY"
    SHADOW = "SHADOW"
    POST_FREEZE_RECONCILIATION = "POST_FREEZE_RECONCILIATION"


class EvidencePolarity(str, Enum):
    SUPPORTING = "SUPPORTING"
    CONTRADICTORY = "CONTRADICTORY"


class KnowledgeCatalogError(ValueError):
    """The source manifest or completeness contract is not safe to use."""


class KnowledgeAccessDenied(PermissionError):
    """A typed retrieval was denied and receipted by the authority gate."""


@dataclass(frozen=True)
class SourceSpec:
    path: str
    authority: AuthorityClass
    supersedes: tuple[str, ...] = ()
    target_relationship: TargetRelationship = TargetRelationship.GENERAL
    access_policy: AccessPolicy = AccessPolicy.SERVE


@dataclass(frozen=True)
class CoverageChunk:
    start: int
    end_exclusive: int
    sha256: str


@dataclass(frozen=True)
class SourceEntry:
    source_id: str
    path: str
    sha256: str
    byte_length: int
    authority: AuthorityClass
    supersedes: tuple[str, ...]
    superseded_by: tuple[str, ...]
    target_relationship: TargetRelationship
    access_policy: AccessPolicy
    knowledge_manifest_version: str
    coverage: tuple[CoverageChunk, ...]


@dataclass(frozen=True)
class CompletenessContract:
    brain_path: str
    brain_version: str = "s105.9"
    expected_play_count: int = 90
    s135_paths: frozenset[str] = frozenset()
    frozen_paths: frozenset[str] = frozenset()
    carryforward_paths: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RetrievalContext:
    run_id: str
    state_hash: str
    knowledge_manifest_hash: str
    lane: RetrievalLane = RetrievalLane.PRIMARY


@dataclass(frozen=True)
class RetrievalReceipt:
    sequence: int
    event: str
    operation: str
    decision: str
    reason: str
    run_id: str
    state_hash: str
    knowledge_manifest_hash: str
    lane: str
    source_id: str | None
    source_path: str | None
    byte_range: tuple[int, int] | None
    content_sha256: str | None
    shadow_only: bool
    primary_lock_eligible: bool
    primary_freeze_receipt_hash: str | None


@dataclass(frozen=True)
class ReadResult:
    entry: SourceEntry
    data: bytes
    receipt: RetrievalReceipt


@dataclass(frozen=True)
class SearchHit:
    source_id: str
    path: str
    start: int
    end_exclusive: int
    match: bytes
    content_sha256: str


@dataclass(frozen=True)
class PlayRecord:
    play_id: str
    body: Mapping[str, Any]
    content_sha256: str
    source_id: str
    receipt: RetrievalReceipt


@dataclass(frozen=True)
class EvidenceRecord:
    play_id: str
    polarity: EvidencePolarity
    body: Mapping[str, Any]
    content_sha256: str


@dataclass(frozen=True)
class PrimaryFreezeReceipt:
    run_id: str
    state_hash: str
    knowledge_manifest_hash: str
    artifact_hashes: Mapping[str, str]
    receipt_hash: str


ReceiptSink = Callable[[RetrievalReceipt], None]


_ALLOWED_V3_CARRYFORWARD = frozenset(
    {
        "NG_EXHAUSTION_V3_NONAUTHORITATIVE_RESULTS_EXTRA_AGENT_V4_CARRYFORWARD_20260820.md",
        "NG_EXHAUSTION_V3_EXTRA_AGENT_INFORMATION_FINDINGS_20260820.md",
        "NG_EXHAUSTION_V3_EXTRA_AGENT_INFORMATION_FINDINGS_20260820.json",
    }
)
_REQUIRED_FREEZE_ARTIFACTS = frozenset(
    {
        "candidate_discovery",
        "helper_evidence",
        "frankie_reasoning",
        "probability_movie",
        "first_lock",
        "no_lock",
    }
)

_S135_STACK_PATHS = frozenset(
    {
        "research/kalshi/frankie_packet_compact_s120.py",
        "research/kalshi/frankie_causal_capture_gate_s126.py",
        "research/kalshi/frankie_specialist_parity_s126.py",
        "research/kalshi/frankie_s114_separation_metadata_s126.py",
        "research/kalshi/frankie_m13_recover_s126.py",
        "research/kalshi/frankie_aws_stage_s126.py",
        "research/kalshi/frankie_s128_contract_repairs.py",
        "research/kalshi/frankie_s128_decision_state.py",
        "research/kalshi/frankie_s128_handoff.py",
        "research/kalshi/frankie_s132_dynamic_curve.py",
        "research/kalshi/frankie_s132_runtime.py",
        "research/kalshi/frankie_s133_reasoning_runtime.py",
        "research/kalshi/frankie_s135_current_runtime.py",
        "research/kalshi/frankie_s135_date_driver.py",
        "research/kalshi/frankie_s135_date_render.py",
        "research/kalshi/frankie_s135_date_session.py",
        "research/kalshi/frankie_s135_group_runner.py",
        "research/kalshi/frankie_s135_handoff.py",
        "research/kalshi/frankie_s135_preflight.py",
        "research/kalshi/frankie_s135_specialist_authority.py",
    }
)

_FROZEN_EXHAUSTION_CORPUS_PATHS = frozenset(
    {
        "research/NG_EXHAUSTION_CHAIN_PHASE1_54W_BASE_FREEZE_20260817.json",
        "research/NG_EXHAUSTION_CHAIN_PHASE1_54W_EXECUTION_PROTOCOL_20260817.json",
        "research/NG_EXHAUSTION_CHAIN_PHASE1_CAUSAL_PROTOCOL_20260817.json",
        "research/NG_EXHAUSTION_CHAIN_PHASE1_DISCOVERY_PROTOCOL_20260817.json",
        "research/NG_EXHAUSTION_CHAIN_PHASE1_MECHANISM_ADDENDUM_20260817.json",
        "research/NG_EXHAUSTION_CHAIN_PHASE1_55W_RECONCILE_LAUNCH_20260817.json",
        "research/NG_EXHAUSTION_CHAIN_PHASE2_FINAL_FREEZE_20260818.md",
        "research/NG_EXHAUSTION_CHAIN_PHASE2_ALL_AGENT_FINDINGS_20260818.md",
        "research/NG_EXHAUSTION_CHAIN_PHASE2_FINDINGS_20260817.md",
        "research/NG_EXHAUSTION_CHAIN_PHASE2_TIMING_CONTEXT_FINDINGS_20260818.md",
        "research/NG_EXHAUSTION_CHAIN_PHASE2_MODULE_NOVELTY_FINDINGS_20260818.md",
        "research/NG_EXHAUSTION_CHAIN_PHASE2_POSTEXIT_RECURRENCE_FINDINGS_20260818.md",
        "research/NG_EXHAUSTION_CHAIN_PHASE2_PARALLEL_RECURRENCE_RECONCILIATION_20260818.md",
        "research/NG_EXHAUSTION_CHAIN_PHASE2_FINDINGS_ADDENDUM_POX_20260818.md",
        "research/NG_EXHAUSTION_CHAIN_PHASE2_POX_BRANCH_RECONCILIATION_V2_20260818.md",
        "research/NG_EXHAUSTION_CHAIN_PHASE2_POX_SAME_POSTEXIT_REEXPRESSION_20260818.md",
        "research/NG_EXHAUSTION_CHAIN_PHASE2_REAPPEARANCE_WATCH_MAP_20260818.json",
        "research/NG_EXHAUSTION_CHAIN_PHASE2_FINALIZATION_CHECKLIST_20260818.json",
        "research/NG_EXHAUSTION_BRAIN_PROPOSAL_INDEX_20260818.md",
        "research/NG_EXHAUSTION_BRAIN_PROPOSAL_INDEX_ADDENDUM_20260820.md",
        "research/NG_EXHAUSTION_V4_BRAIN_TRADE_PROPOSAL_CLEAN_SOURCE_CURRENT_20260820.md",
        "research/kalshi/knowledge/ng_brain_exhaustion_chain_phase2_proposal_20260818.json",
        "research/kalshi/knowledge/ng_brain_exhaustion_chain_birth_v2_proposal_20260819.json",
        "research/kalshi/knowledge/ng_brain_exhaustion_entry_timing_extension_20260818.json",
        "research/kalshi/knowledge/ng_brain_exhaustion_pox_focused_proposal_20260819.json",
    }
)

_CARRYFORWARD_PATHS = frozenset(
    {
        "research/NG_EXHAUSTION_V3_NONAUTHORITATIVE_RESULTS_EXTRA_AGENT_V4_CARRYFORWARD_20260820.md",
        "research/NG_EXHAUSTION_V3_EXTRA_AGENT_INFORMATION_FINDINGS_20260820.md",
        "research/NG_EXHAUSTION_V3_EXTRA_AGENT_INFORMATION_FINDINGS_20260820.json",
    }
)


def october_full_stack_completeness_contract() -> CompletenessContract:
    """Return the binding production completeness contract for October integration."""
    return CompletenessContract(
        brain_path="research/kalshi/knowledge/ng_brain.json",
        brain_version="s105.9",
        expected_play_count=90,
        s135_paths=_S135_STACK_PATHS,
        frozen_paths=_FROZEN_EXHAUSTION_CORPUS_PATHS,
        carryforward_paths=_CARRYFORWARD_PATHS,
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())


def _normal_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise KnowledgeCatalogError(f"unsafe source path: {value!r}")
    return path.as_posix()


def _coverage(data: bytes, chunk_bytes: int) -> tuple[CoverageChunk, ...]:
    if chunk_bytes < 1:
        raise KnowledgeCatalogError("coverage_chunk_bytes must be positive")
    if not data:
        return (CoverageChunk(0, 0, _sha256(b"")),)
    return tuple(
        CoverageChunk(start, min(start + chunk_bytes, len(data)), _sha256(data[start : start + chunk_bytes]))
        for start in range(0, len(data), chunk_bytes)
    )


def _validate_coverage(entry: SourceEntry) -> None:
    cursor = 0
    for chunk in entry.coverage:
        if chunk.start != cursor or chunk.end_exclusive < chunk.start:
            raise KnowledgeCatalogError(f"non-contiguous coverage for {entry.path}")
        cursor = chunk.end_exclusive
    if cursor != entry.byte_length:
        raise KnowledgeCatalogError(f"incomplete byte coverage for {entry.path}")


class KnowledgePlane:
    """Immutable catalog plus fail-closed retrieval and answer-wall contracts."""

    def __init__(
        self,
        *,
        root: Path,
        entries: Mapping[str, SourceEntry],
        manifest_hash: str,
        brain_path: str,
        plays: Mapping[str, Mapping[str, Any]],
        receipt_sink: ReceiptSink | None,
    ) -> None:
        self._root = root
        self._entries = dict(entries)
        self.manifest_hash = manifest_hash
        self._brain_path = brain_path
        self._plays = copy.deepcopy(dict(plays))
        self._receipts: list[RetrievalReceipt] = []
        self._receipt_sink = receipt_sink
        self._primary_freeze: PrimaryFreezeReceipt | None = None

    @classmethod
    def build(
        cls,
        root: str | Path,
        specs: Sequence[SourceSpec],
        *,
        contract: CompletenessContract,
        manifest_version: str,
        coverage_chunk_bytes: int = 64 * 1024,
        receipt_sink: ReceiptSink | None = None,
    ) -> "KnowledgePlane":
        root_path = Path(root).resolve()
        if not manifest_version:
            raise KnowledgeCatalogError("knowledge manifest version is required")

        normalized: dict[str, SourceSpec] = {}
        raw_by_path: dict[str, bytes] = {}
        for supplied in specs:
            path = _normal_path(supplied.path)
            supersedes = tuple(_normal_path(item) for item in supplied.supersedes)
            spec = SourceSpec(
                path=path,
                authority=supplied.authority,
                supersedes=supersedes,
                target_relationship=supplied.target_relationship,
                access_policy=supplied.access_policy,
            )
            if path in normalized:
                raise KnowledgeCatalogError(f"duplicate catalog path: {path}")
            cls._validate_spec(spec)
            absolute = (root_path / path).resolve()
            try:
                absolute.relative_to(root_path)
            except ValueError as exc:
                raise KnowledgeCatalogError(f"source escapes catalog root: {path}") from exc
            if not absolute.is_file():
                raise KnowledgeCatalogError(f"source does not exist: {path}")
            normalized[path] = spec
            # Sealed bytes are hashed for the lossless manifest but never decoded or semantically inspected here.
            raw_by_path[path] = absolute.read_bytes()

        superseded_by: dict[str, list[str]] = {path: [] for path in normalized}
        for path, spec in normalized.items():
            for old_path in spec.supersedes:
                if old_path not in normalized:
                    raise KnowledgeCatalogError(f"{path} supersedes uncatalogued source {old_path}")
                superseded_by[old_path].append(path)

        entries: dict[str, SourceEntry] = {}
        for path in sorted(normalized):
            spec = normalized[path]
            data = raw_by_path[path]
            digest = _sha256(data)
            path_digest = _sha256(path.encode("utf-8"))[:16]
            entry = SourceEntry(
                source_id=f"sha256:{digest}:{path_digest}",
                path=path,
                sha256=digest,
                byte_length=len(data),
                authority=spec.authority,
                supersedes=spec.supersedes,
                superseded_by=tuple(sorted(superseded_by[path])),
                target_relationship=spec.target_relationship,
                access_policy=spec.access_policy,
                knowledge_manifest_version=manifest_version,
                coverage=_coverage(data, coverage_chunk_bytes),
            )
            _validate_coverage(entry)
            entries[path] = entry

        brain_path = _normal_path(contract.brain_path)
        if brain_path not in entries or entries[brain_path].authority is not AuthorityClass.CURRENT_BRAIN:
            raise KnowledgeCatalogError("completeness contract brain must be catalogued as CURRENT_BRAIN")
        try:
            brain = json.loads(raw_by_path[brain_path].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise KnowledgeCatalogError("current brain is not valid UTF-8 JSON") from exc
        version = str((brain.get("meta") or {}).get("version") or brain.get("version") or "")
        plays_list = brain.get("plays")
        if version != contract.brain_version:
            raise KnowledgeCatalogError(
                f"current brain version mismatch: expected {contract.brain_version}, got {version or 'missing'}"
            )
        if not isinstance(plays_list, list) or len(plays_list) != contract.expected_play_count:
            raise KnowledgeCatalogError(
                f"current brain must expose {contract.expected_play_count} complete plays"
            )
        plays: dict[str, Mapping[str, Any]] = {}
        for play in plays_list:
            if not isinstance(play, dict) or not str(play.get("id") or ""):
                raise KnowledgeCatalogError("every complete play body requires a unique id")
            play_id = str(play["id"])
            if play_id in plays:
                raise KnowledgeCatalogError(f"duplicate play id: {play_id}")
            plays[play_id] = play

        frozen_paths = {_normal_path(path) for path in contract.frozen_paths}
        cls._require_paths(
            "frozen corpus", frozen_paths, entries, {AuthorityClass.FROZEN_LEARNED_KNOWLEDGE}
        )
        cls._require_paths(
            "S135 stack",
            {_normal_path(path) for path in contract.s135_paths},
            entries,
            {AuthorityClass.BINDING_CURRENT, AuthorityClass.CURRENT_BRAIN},
        )
        cls._require_paths(
            "extra-agent carryforward",
            {_normal_path(path) for path in contract.carryforward_paths},
            entries,
            {AuthorityClass.EXTRA_AGENT_CARRYFORWARD},
        )

        manifest_rows = [cls._manifest_row(entries[path]) for path in sorted(entries)]
        manifest_hash = _sha256(
            _canonical_bytes({"version": manifest_version, "sources": manifest_rows})
        )
        return cls(
            root=root_path,
            entries=entries,
            manifest_hash=manifest_hash,
            brain_path=brain_path,
            plays=plays,
            receipt_sink=receipt_sink,
        )

    @staticmethod
    def _require_paths(
        label: str,
        required: set[str],
        entries: Mapping[str, SourceEntry],
        authorities: set[AuthorityClass],
    ) -> None:
        missing = sorted(required - entries.keys())
        wrong_authority = sorted(
            path for path in required & entries.keys() if entries[path].authority not in authorities
        )
        if missing or wrong_authority:
            raise KnowledgeCatalogError(
                f"{label} incomplete: missing={missing}, wrong_authority={wrong_authority}"
            )

    @staticmethod
    def _validate_spec(spec: SourceSpec) -> None:
        if spec.authority is AuthorityClass.PROVISIONAL_SHADOW and spec.access_policy is not AccessPolicy.SHADOW_ONLY:
            raise KnowledgeCatalogError(f"provisional source must be SHADOW_ONLY: {spec.path}")
        if spec.authority is AuthorityClass.SEALED_TARGET_ANSWER:
            if spec.access_policy is not AccessPolicy.SEALED_UNTIL_PRIMARY_FREEZE:
                raise KnowledgeCatalogError(f"sealed answer requires answer-wall policy: {spec.path}")
            if spec.target_relationship is not TargetRelationship.OCTOBER_STEP1_ANSWER:
                raise KnowledgeCatalogError(f"sealed answer requires explicit target relationship: {spec.path}")
        if spec.access_policy is AccessPolicy.SEALED_UNTIL_PRIMARY_FREEZE and (
            spec.authority is not AuthorityClass.SEALED_TARGET_ANSWER
            or spec.target_relationship is not TargetRelationship.OCTOBER_STEP1_ANSWER
        ):
            raise KnowledgeCatalogError(f"answer-wall policy requires SEALED_TARGET_ANSWER: {spec.path}")

    @staticmethod
    def _manifest_row(entry: SourceEntry) -> dict[str, Any]:
        return {
            "source_id": entry.source_id,
            "path": entry.path,
            "sha256": entry.sha256,
            "bytes": entry.byte_length,
            "authority": entry.authority.value,
            "supersedes": list(entry.supersedes),
            "superseded_by": list(entry.superseded_by),
            "target_relationship": entry.target_relationship.value,
            "access_policy": entry.access_policy.value,
            "knowledge_manifest_version": entry.knowledge_manifest_version,
            "coverage": [asdict(chunk) for chunk in entry.coverage],
        }

    @property
    def receipts(self) -> tuple[RetrievalReceipt, ...]:
        return tuple(self._receipts)

    def entry(self, path: str) -> SourceEntry:
        normalized = _normal_path(path)
        try:
            return self._entries[normalized]
        except KeyError as exc:
            raise KeyError(f"unknown catalog source: {normalized}") from exc

    def context(
        self,
        *,
        run_id: str,
        state_hash: str,
        lane: RetrievalLane = RetrievalLane.PRIMARY,
    ) -> RetrievalContext:
        if not run_id or not _is_sha256(state_hash):
            raise KnowledgeCatalogError("retrieval context requires run id and SHA-256 state hash")
        return RetrievalContext(run_id, state_hash.lower(), self.manifest_hash, lane)

    def freeze_primary_outputs(
        self, context: RetrievalContext, artifact_hashes: Mapping[str, str]
    ) -> PrimaryFreezeReceipt:
        if context.knowledge_manifest_hash != self.manifest_hash:
            raise KnowledgeAccessDenied("MANIFEST_IDENTITY_MISMATCH")
        if context.lane is not RetrievalLane.PRIMARY:
            raise KnowledgeAccessDenied("PRIMARY_FREEZE_REQUIRES_PRIMARY_LANE")
        missing = sorted(_REQUIRED_FREEZE_ARTIFACTS - artifact_hashes.keys())
        invalid = sorted(name for name, digest in artifact_hashes.items() if not _is_sha256(str(digest)))
        if missing or invalid:
            raise KnowledgeCatalogError(f"incomplete primary freeze: missing={missing}, invalid={invalid}")
        payload = {
            "run_id": context.run_id,
            "state_hash": context.state_hash,
            "knowledge_manifest_hash": context.knowledge_manifest_hash,
            "artifact_hashes": dict(sorted(artifact_hashes.items())),
        }
        receipt = PrimaryFreezeReceipt(
            run_id=context.run_id,
            state_hash=context.state_hash,
            knowledge_manifest_hash=context.knowledge_manifest_hash,
            artifact_hashes=dict(sorted(artifact_hashes.items())),
            receipt_hash=_sha256(_canonical_bytes(payload)),
        )
        if self._primary_freeze is not None and self._primary_freeze != receipt:
            raise KnowledgeAccessDenied("PRIMARY_FREEZE_ALREADY_IMMUTABLE")
        self._primary_freeze = receipt
        return receipt

    def list_sources(self, context: RetrievalContext) -> tuple[SourceEntry, ...]:
        self._require_context(context, "LIST")
        visible = []
        for entry in sorted(self._entries.values(), key=lambda item: item.path):
            reason = self._access_reason(context, entry)
            if reason is None:
                visible.append(entry)
            else:
                self._record(context, entry, "LIST", "DENIED", reason)
        self._record(context, None, "LIST", "ALLOWED", "AUTHORIZED_SOURCES_ONLY")
        return tuple(visible)

    def search(
        self, context: RetrievalContext, query: str | bytes, *, max_results: int = 100
    ) -> tuple[SearchHit, ...]:
        self._require_context(context, "SEARCH")
        needle = query.encode("utf-8") if isinstance(query, str) else bytes(query)
        if not needle or max_results < 1:
            raise ValueError("search query and positive max_results are required")
        lowered = needle.lower()
        hits: list[SearchHit] = []
        for entry in sorted(self._entries.values(), key=lambda item: item.path):
            reason = self._access_reason(context, entry)
            if reason is not None:
                self._record(context, entry, "SEARCH", "DENIED", reason)
                continue
            data = self._verified_bytes(context, entry, "SEARCH")
            cursor = 0
            lower_data = data.lower()
            while len(hits) < max_results:
                start = lower_data.find(lowered, cursor)
                if start < 0:
                    break
                end = start + len(needle)
                match = data[start:end]
                hits.append(
                    SearchHit(entry.source_id, entry.path, start, end, match, _sha256(match))
                )
                cursor = end
            self._record(context, entry, "SEARCH", "ALLOWED", "AUTHORIZED", content_sha256=entry.sha256)
            if len(hits) >= max_results:
                break
        return tuple(hits)

    def read(
        self,
        context: RetrievalContext,
        path: str,
        *,
        start: int = 0,
        end_exclusive: int | None = None,
    ) -> ReadResult:
        entry = self.entry(path)
        self._require_access(context, entry, "READ")
        data = self._verified_bytes(context, entry, "READ")
        end = len(data) if end_exclusive is None else end_exclusive
        if start < 0 or end < start or end > len(data):
            raise ValueError(f"invalid byte range [{start}, {end}) for {entry.path}")
        selected = data[start:end]
        receipt = self._record(
            context,
            entry,
            "READ",
            "ALLOWED",
            "AUTHORIZED",
            byte_range=(start, end),
            content_sha256=_sha256(selected),
        )
        return ReadResult(entry, selected, receipt)

    def read_play(self, context: RetrievalContext, play_id: str) -> PlayRecord:
        entry = self._entries[self._brain_path]
        self._require_access(context, entry, "READ_PLAY")
        self._verified_bytes(context, entry, "READ_PLAY")
        try:
            body = copy.deepcopy(self._plays[play_id])
        except KeyError as exc:
            raise KeyError(f"unknown complete brain play: {play_id}") from exc
        digest = _sha256(_canonical_bytes(body))
        receipt = self._record(
            context, entry, "READ_PLAY", "ALLOWED", "COMPLETE_PLAY_BODY", content_sha256=digest
        )
        return PlayRecord(play_id, body, digest, entry.source_id, receipt)

    def retrieve_play_evidence(
        self, context: RetrievalContext, play_id: str, polarity: EvidencePolarity
    ) -> tuple[EvidenceRecord, ...]:
        entry = self._entries[self._brain_path]
        self._require_access(context, entry, f"RETRIEVE_{polarity.value}_EVIDENCE")
        self._verified_bytes(context, entry, f"RETRIEVE_{polarity.value}_EVIDENCE")
        try:
            play = self._plays[play_id]
        except KeyError as exc:
            raise KeyError(f"unknown complete brain play: {play_id}") from exc
        records: list[EvidenceRecord] = []
        if polarity is EvidencePolarity.SUPPORTING and play.get("support"):
            records.append(self._evidence(play_id, polarity, {"support": play["support"]}))
        if polarity is EvidencePolarity.CONTRADICTORY and play.get("falsifier"):
            records.append(self._evidence(play_id, polarity, {"falsifier": play["falsifier"]}))
        expected = "supports" if polarity is EvidencePolarity.SUPPORTING else "contradicts"
        for instance in play.get("instances") or []:
            if str(instance.get("supports_or_contradicts") or "").lower() == expected:
                records.append(self._evidence(play_id, polarity, copy.deepcopy(instance)))
        collection_hash = _sha256(_canonical_bytes([asdict(record) for record in records]))
        self._record(
            context,
            entry,
            f"RETRIEVE_{polarity.value}_EVIDENCE",
            "ALLOWED",
            "EXPLICIT_PLAY_EVIDENCE",
            content_sha256=collection_hash,
        )
        return tuple(records)

    @staticmethod
    def _evidence(
        play_id: str, polarity: EvidencePolarity, body: Mapping[str, Any]
    ) -> EvidenceRecord:
        return EvidenceRecord(play_id, polarity, body, _sha256(_canonical_bytes(body)))

    def _verified_bytes(
        self, context: RetrievalContext, entry: SourceEntry, operation: str
    ) -> bytes:
        data = (self._root / entry.path).read_bytes()
        if len(data) != entry.byte_length or _sha256(data) != entry.sha256:
            self._deny(context, entry, operation, "SOURCE_INTEGRITY_MISMATCH")
        return data

    def _require_access(
        self, context: RetrievalContext, entry: SourceEntry, operation: str
    ) -> None:
        reason = self._access_reason(context, entry)
        if reason is not None:
            self._deny(context, entry, operation, reason)

    def _access_reason(self, context: RetrievalContext, entry: SourceEntry) -> str | None:
        if context.knowledge_manifest_hash != self.manifest_hash:
            return "MANIFEST_IDENTITY_MISMATCH"
        if not context.run_id or not _is_sha256(context.state_hash):
            return "INVALID_RUN_STATE_IDENTITY"
        if self._forbidden_v3_or_extratrees(entry):
            return "FORBIDDEN_V3_D1_EXTRATREES"
        if entry.authority is AuthorityClass.ARCHIVE_NOT_SERVABLE or entry.access_policy is AccessPolicy.DENY:
            return "ARCHIVE_NOT_SERVABLE"
        sealed = (
            entry.authority is AuthorityClass.SEALED_TARGET_ANSWER
            or entry.target_relationship is TargetRelationship.OCTOBER_STEP1_ANSWER
            or self._looks_like_october_answer(entry.path)
        )
        if sealed:
            if self._primary_freeze is None:
                return "ANSWER_WALL_PRE_FREEZE"
            if context.lane is not RetrievalLane.POST_FREEZE_RECONCILIATION:
                return "RECONCILIATION_LANE_REQUIRED"
            freeze = self._primary_freeze
            if (
                context.run_id != freeze.run_id
                or context.state_hash != freeze.state_hash
                or context.knowledge_manifest_hash != freeze.knowledge_manifest_hash
            ):
                return "FREEZE_IDENTITY_MISMATCH"
        if (
            entry.authority is AuthorityClass.PROVISIONAL_SHADOW
            or entry.access_policy is AccessPolicy.SHADOW_ONLY
        ) and context.lane is not RetrievalLane.SHADOW:
            return "PROVISIONAL_SHADOW_ONLY"
        return None

    def _require_context(self, context: RetrievalContext, operation: str) -> None:
        if context.knowledge_manifest_hash != self.manifest_hash:
            reason = "MANIFEST_IDENTITY_MISMATCH"
        elif not context.run_id or not _is_sha256(context.state_hash):
            reason = "INVALID_RUN_STATE_IDENTITY"
        elif not isinstance(context.lane, RetrievalLane):
            reason = "INVALID_RETRIEVAL_LANE"
        else:
            return
        self._record(context, None, operation, "DENIED", reason)
        raise KnowledgeAccessDenied(reason)

    @staticmethod
    def _forbidden_v3_or_extratrees(entry: SourceEntry) -> bool:
        name = PurePosixPath(entry.path).name
        lowered = entry.path.lower().replace("-", "_")
        if "d1" in lowered and "extratrees" in lowered:
            return True
        if "d1_d5_predictability" in lowered:
            return True
        return "v3" in lowered and name not in _ALLOWED_V3_CARRYFORWARD

    @staticmethod
    def _looks_like_october_answer(path: str) -> bool:
        lowered = path.lower().replace("-", "_")
        if "step1" in lowered or "step_1" in lowered:
            return True
        return "october" in lowered and any(
            token in lowered for token in ("crosswalk", "reconciliation", "result")
        )

    def _deny(
        self, context: RetrievalContext, entry: SourceEntry, operation: str, reason: str
    ) -> None:
        self._record(context, entry, operation, "DENIED", reason)
        raise KnowledgeAccessDenied(reason)

    def _record(
        self,
        context: RetrievalContext,
        entry: SourceEntry | None,
        operation: str,
        decision: str,
        reason: str,
        *,
        byte_range: tuple[int, int] | None = None,
        content_sha256: str | None = None,
    ) -> RetrievalReceipt:
        shadow_only = bool(entry and entry.authority is AuthorityClass.PROVISIONAL_SHADOW)
        freeze_hash = self._primary_freeze.receipt_hash if self._primary_freeze else None
        receipt = RetrievalReceipt(
            sequence=len(self._receipts) + 1,
            event="knowledge_retrieval",
            operation=operation,
            decision=decision,
            reason=reason,
            run_id=context.run_id,
            state_hash=context.state_hash,
            knowledge_manifest_hash=context.knowledge_manifest_hash,
            lane=context.lane.value,
            source_id=entry.source_id if entry else None,
            source_path=entry.path if entry else None,
            byte_range=byte_range,
            content_sha256=content_sha256,
            shadow_only=shadow_only,
            primary_lock_eligible=decision == "ALLOWED" and not shadow_only and context.lane is RetrievalLane.PRIMARY,
            primary_freeze_receipt_hash=freeze_hash,
        )
        self._receipts.append(receipt)
        if self._receipt_sink is not None:
            self._receipt_sink(receipt)
        return receipt


__all__ = [
    "AccessPolicy",
    "AuthorityClass",
    "CompletenessContract",
    "CoverageChunk",
    "EvidencePolarity",
    "EvidenceRecord",
    "KnowledgeAccessDenied",
    "KnowledgeCatalogError",
    "KnowledgePlane",
    "PlayRecord",
    "PrimaryFreezeReceipt",
    "ReadResult",
    "RetrievalContext",
    "RetrievalLane",
    "RetrievalReceipt",
    "SearchHit",
    "SourceEntry",
    "SourceSpec",
    "TargetRelationship",
    "october_full_stack_completeness_contract",
]
