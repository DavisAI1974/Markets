#!/usr/bin/env python3
"""Fresh full-stack October Frankie runner.

This module is the additive integration owner for the corrected October construction.  It does not
import or reveal Step-1 outputs.  The initial slice freezes the exact canonical raw-object roster and
full-month operating boundary; knowledge, causal-plane, helper-runtime, and launch wiring are added
through the focused contracts tested beside this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import re
import os
import sys
from types import MappingProxyType
from typing import Any, Mapping, Sequence

_KALSHI_DIR = Path(__file__).resolve().parent
_RESEARCH_DIR = _KALSHI_DIR.parent
for _path in (_KALSHI_DIR, _RESEARCH_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from research.kalshi.frankie_authority_knowledge_plane_20260824 import (
    AuthorityClass,
    KnowledgeAccessDenied,
    KnowledgePlane,
    RetrievalLane,
    october_full_stack_completeness_contract,
)
# The router remains executable both as a package module and as a standalone
# research script.  Pin its legacy top-level import name to this exact module
# object so RetrievalLane/AuthorityClass identities cannot split at runtime.
sys.modules.setdefault(
    "frankie_authority_knowledge_plane_20260824",
    sys.modules["research.kalshi.frankie_authority_knowledge_plane_20260824"],
)
from research.kalshi.frankie_full_stack_paired_lane_orchestrator_20260824 import (
    COMBINED_COMPONENTS,
    ComponentLifecycleStage,
    ComponentStatus,
    LaneId,
    LaneRuntime,
    PairedLaneEvent,
    PairedLaneEventSink,
    PairedLaneOrchestrator,
    ProvisionalComponentReceipt,
)
from research.kalshi.frankie_full_stack_runtime_adapter_20260824 import (
    DurableJsonlLedger,
    OpenAIResponsesClient,
)
from research.kalshi.frankie_full_stack_runtime_contracts_20260824 import (
    CausalPrefixBinding,
    KnowledgeSourceExcerpt,
    LedgerKind,
    RetrievalReceipt,
    RuntimeEvent,
    ToolCallReceipt,
)
from research.kalshi.frankie_lane_aware_context_router_20260824 import (
    ComponentAvailability,
    ContextVariant,
    FrankieLaneAwareContextRouter,
    ProvisionalComponent,
    RouteBundle,
)
from research.kalshi.frankie_october_knowledge_inventory_20260824 import production_source_specs
from research.kalshi.ng_exhaustion_frankie_causal_data_plane_20260824 import (
    ChainExtensionState,
    OpportunityKind,
    default_legacy_v4_mappings,
    seal_semantic_crosswalk,
)
from research.kalshi.ng_exhaustion_frankie_continuous_stream_20260824 import (
    ContinuousCausalSecond,
    ContinuousV4CausalStreamBuilder,
    OpportunityTransition,
    ProtectedProspectiveWeakeningMarker,
    replay_dbn_files_to_causal_seconds,
)


SCHEMA = "NG_EXHAUSTION_FRANKIE_FULLSTACK_OCTOBER_V1_20260824"
EXPECTED_MODEL = "gpt-5.6-sol"
EXPECTED_MANIFEST_SHA256 = "5739bce85d9bfbbe6c59d000bc411b424d7752b98a309725161d44e6d1d3dc2e"
PREDECESSOR_SEGMENT = "20210901_20211001"
OCTOBER_SEGMENT = "20211001_20211101"
PREDECESSOR_NAME = "glbx-mdp3-20210930.mbo.dbn.zst"
TARGET_START = int(datetime(2021, 10, 1, tzinfo=timezone.utc).timestamp())
TARGET_END = int(datetime(2021, 11, 1, tzinfo=timezone.utc).timestamp())
ANSWER_WALL_MODE = "SEALED_UNTIL_PRIMARY_FREEZE"
_OBJECT_DATE = re.compile(r"glbx-mdp3-(20\d{6})\.mbo\.dbn\.zst$")
PAIRED_COMPONENTS = tuple(COMBINED_COMPONENTS)
ACTIVE_PAIRED_COMPONENTS = tuple(item for item in PAIRED_COMPONENTS if item != "META_LOOP")
_BASE_CONTEXT_PATHS = (
    "research/NG_EXHAUSTION_CHAIN_PHASE2_ALL_AGENT_FINDINGS_20260818.md",
    "research/NG_EXHAUSTION_V4_BRAIN_TRADE_PROPOSAL_CLEAN_SOURCE_CURRENT_20260820.md",
    "research/NG_EXHAUSTION_V4_INTERPRETATION_CORRECTION_20260820.md",
    "research/NG_EXHAUSTION_V3_NONAUTHORITATIVE_RESULTS_EXTRA_AGENT_V4_CARRYFORWARD_20260820.md",
)


class FullStackOctoberError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class LaunchJsonEventSink:
    """Secret-free newline-JSON launch telemetry consumed by the workflow gate."""

    def emit_launch(self, event: str, **details: Any) -> None:
        if not str(event or "").strip():
            raise FullStackOctoberError("launch event name is required")
        for key in details:
            if any(term in str(key).lower() for term in ("secret", "token", "api_key", "password")):
                raise FullStackOctoberError("secret-bearing launch telemetry is forbidden")
        print(json.dumps({"event": event, **details}, sort_keys=True, separators=(",", ":")), flush=True)


class LaunchRuntimeEventSink:
    def emit(self, event: RuntimeEvent) -> None:
        LaunchJsonEventSink().emit_launch(
            event.name,
            level=event.level,
            run_id=event.run_id,
            correlation_id=event.correlation_id,
            causal_cutoff=event.causal_cutoff,
            receipt_hash=event.event_hash,
            **json.loads(event.details_json),
        )


class LaunchPairedEventSink(PairedLaneEventSink):
    def emit(self, event: PairedLaneEvent) -> None:
        super().emit(event)
        LaunchJsonEventSink().emit_launch(
            event.name,
            run_id=event.run_id,
            causal_prefix_hash=event.causal_prefix_hash,
            receipt_hash=event.event_hash,
            **json.loads(event.details_json),
        )


@dataclass(frozen=True)
class SourceObject:
    date: str
    segment: str
    key: str
    sha256: str
    bytes: int
    bucket: str
    purpose: str


def _source_object(row: Mapping[str, Any], *, purpose: str) -> SourceObject:
    key = str(row.get("key") or "")
    match = _OBJECT_DATE.search(key)
    if match is None:
        raise FullStackOctoberError(f"canonical DBN key has no source date: {key!r}")
    sha = str(row.get("sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise FullStackOctoberError(f"canonical DBN object has invalid SHA-256: {key}")
    size = row.get("bytes")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise FullStackOctoberError(f"canonical DBN object has invalid byte length: {key}")
    return SourceObject(
        date=match.group(1),
        segment=str(row.get("segment") or ""),
        key=key,
        sha256=sha,
        bytes=size,
        bucket=str(row.get("bucket") or ""),
        purpose=purpose,
    )


def select_october_source_roster(manifest: Mapping[str, Any]) -> tuple[SourceObject, ...]:
    """Return one lawful predecessor object followed by all 26 canonical October objects."""
    if manifest.get("manifest_sha256") != EXPECTED_MANIFEST_SHA256:
        raise FullStackOctoberError("canonical raw-object manifest identity mismatch")
    rows = manifest.get("canonical_dbn_objects")
    if not isinstance(rows, list):
        raise FullStackOctoberError("canonical_dbn_objects must be a list")

    predecessor_rows = [
        row for row in rows
        if isinstance(row, Mapping)
        and row.get("segment") == PREDECESSOR_SEGMENT
        and str(row.get("key") or "").endswith(PREDECESSOR_NAME)
    ]
    if len(predecessor_rows) != 1:
        raise FullStackOctoberError("exact canonical predecessor bootstrap object is required")
    target_rows = [
        row for row in rows
        if isinstance(row, Mapping) and row.get("segment") == OCTOBER_SEGMENT
    ]
    targets = sorted(
        (_source_object(row, purpose="OCTOBER_CAUSAL_STREAM") for row in target_rows),
        key=lambda item: (item.date, item.key),
    )
    if len(targets) != 26 or len({item.key for item in targets}) != 26:
        raise FullStackOctoberError("October canonical roster must contain exactly 26 unique objects")
    if targets[0].date != "20211001" or targets[-1].date != "20211031":
        raise FullStackOctoberError("October canonical roster date coverage drift")
    predecessor = _source_object(predecessor_rows[0], purpose="PREDECESSOR_BOOTSTRAP")
    return (predecessor, *targets)


def verify_staged_source_roster(
    roster: tuple[SourceObject, ...], source_root: str | Path
) -> tuple[Path, ...]:
    """Resolve the manifest-selected objects by basename and reverify bytes and SHA."""
    root = Path(source_root)
    if not root.is_dir() or not roster:
        raise FullStackOctoberError("staged source root and non-empty roster are required")
    paths: list[Path] = []
    names: set[str] = set()
    for item in roster:
        name = Path(item.key).name
        if not name or name in names:
            raise FullStackOctoberError("staged roster basenames must be unique")
        names.add(name)
        path = root / name
        if not path.is_file():
            raise FullStackOctoberError(f"staged canonical source is missing: {name}")
        if path.stat().st_size != item.bytes:
            raise FullStackOctoberError(f"staged canonical source byte mismatch: {name}")
        if _sha256_file(path) != item.sha256:
            raise FullStackOctoberError(f"staged canonical source SHA-256 mismatch: {name}")
        paths.append(path)
    return tuple(paths)


@dataclass(frozen=True)
class FullStackOctoberConfig:
    run_id: str
    manifest_path: Path
    source_root: Path
    output_root: Path
    model: str = EXPECTED_MODEL
    target_start: int = TARGET_START
    target_end: int = TARGET_END
    answer_wall_mode: str = ANSWER_WALL_MODE

    def validate(self) -> "FullStackOctoberConfig":
        if not str(self.run_id or "").strip():
            raise FullStackOctoberError("run_id is required")
        if self.model != EXPECTED_MODEL:
            raise FullStackOctoberError(f"model must be exactly {EXPECTED_MODEL}")
        if (self.target_start, self.target_end) != (TARGET_START, TARGET_END):
            raise FullStackOctoberError("runner must cover the exact full October half-open interval")
        if self.answer_wall_mode != ANSWER_WALL_MODE:
            raise FullStackOctoberError("October Step-1 answer wall must remain sealed until primary freeze")
        if self.output_root.exists() and any(self.output_root.iterdir()):
            raise FullStackOctoberError("output_root must be new or empty")
        return self


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        # ``dataclasses.asdict`` deep-copies every leaf.  The causal stream
        # intentionally seals nested state with MappingProxyType, which cannot
        # be pickled/deep-copied.  Walk declared fields directly so immutability
        # remains intact while producing the provider/ledger JSON projection.
        return {field.name: _jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, (Mapping, MappingProxyType)):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value") and isinstance(getattr(value, "value"), str):
        return value.value
    return value


def _write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(dict(value), handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def paired_component_id(path: str) -> str:
    name = Path(path).name.lower()
    if "meta_loop" in name:
        return "META_LOOP"
    if "hipporag" in name:
        return "HIPPORAG_RETRIEVAL"
    if "lats" in name:
        return "LATS_BOUNDED_SEARCH"
    if "progress_compress" in name:
        return "PROGRESS_COMPRESSION"
    if "temporal" in name:
        return "TEMPORAL_GRAPH"
    if "cognitive_p0_loops" in name:
        return "WORKING_MEMORY"
    if any(term in name for term in ("v4_provisional", "gap_closure", "p0_registry")):
        return "PROVISIONAL_V4_ENGINEERING_CANDIDATE"
    return "S137_COGNITIVE_RUNTIME"


def production_provisional_components(plane: KnowledgePlane) -> tuple[ProvisionalComponent, ...]:
    context = plane.context(
        run_id="fullstack-component-catalog", state_hash=_stable_hash("component-catalog"), lane=RetrievalLane.SHADOW
    )
    entries = [
        item for item in plane.list_sources(context)
        if item.authority is AuthorityClass.PROVISIONAL_SHADOW
    ]
    return tuple(
        ProvisionalComponent(
            path=item.path,
            label=f"{paired_component_id(item.path)}:{Path(item.path).name}",
            availability=(
                ComponentAvailability.POST_GLOBAL_FREEZE_ONLY
                if paired_component_id(item.path) == "META_LOOP"
                else ComponentAvailability.PRE_FREEZE_AUGMENTATION
            ),
        )
        for item in sorted(entries, key=lambda row: row.path)
    )


def _binding(row: ContinuousCausalSecond, knowledge_manifest_hash: str) -> CausalPrefixBinding:
    clocks = row.data_plane_row.clocks
    return CausalPrefixBinding(
        run_id=row.data_plane_row.run_id,
        causal_cutoff=clocks.evaluated_at,
        event_known_by=clocks.event_known_by,
        causal_prefix_hash=row.prefix.prefix_hash,
        state_prefix_hash=row.data_plane_row.row_hash,
        knowledge_manifest_hash=knowledge_manifest_hash,
    ).validate()


def _base_knowledge(
    router: FrankieLaneAwareContextRouter,
    bundle: RouteBundle,
) -> tuple[KnowledgeSourceExcerpt, ...]:
    excerpts: list[KnowledgeSourceExcerpt] = []
    for path in _BASE_CONTEXT_PATHS:
        result = router.read_source(bundle, ContextVariant.S135_CONTROL, path)
        try:
            text = result.data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FullStackOctoberError(f"base knowledge is not UTF-8: {path}") from exc
        excerpts.append(
            KnowledgeSourceExcerpt.create(
                source_id=result.entry.source_id,
                source_sha256=result.entry.sha256,
                byte_start=0,
                excerpt=text,
            )
        )
    return tuple(excerpts)


def _lane_receipts(
    *,
    lane: LaneId,
    binding: CausalPrefixBinding,
    sources: Sequence[KnowledgeSourceExcerpt],
) -> tuple[tuple[ToolCallReceipt, ...], tuple[RetrievalReceipt, ...]]:
    prefix = binding.causal_prefix_hash[:16]
    retrievals = tuple(
        RetrievalReceipt(
            retrieval_id=f"{lane.value}:{prefix}:{index}",
            source_id=item.source_id,
            source_sha256=item.source_sha256,
            byte_start=item.byte_start,
            byte_end=item.byte_end,
            content_sha256=item.content_sha256,
        ).validate()
        for index, item in enumerate(sources)
    )
    response_hash = _stable_hash([item.content_sha256 for item in sources])
    tool = ToolCallReceipt(
        tool_call_id=f"{lane.value}:{prefix}:list-read",
        tool_name="authority_knowledge.list_and_read",
        request_hash=_stable_hash(
            {"lane": lane.value, "prefix": binding.causal_prefix_hash, "sources": [item.source_id for item in sources]}
        ),
        response_hash=response_hash,
    ).validate()
    return (tool,), retrievals


def _component_receipts(
    *,
    router: FrankieLaneAwareContextRouter,
    bundle: RouteBundle,
    binding: CausalPrefixBinding,
) -> tuple[ProvisionalComponentReceipt, ...]:
    route = bundle.routes[ContextVariant.FULL_PROVISIONAL_COMBINED]
    grouped: dict[str, list[dict[str, Any]]] = {item: [] for item in ACTIVE_PAIRED_COMPONENTS}
    for source in route.augmentation_sources:
        component = paired_component_id(source.path)
        if component == "META_LOOP":
            continue
        result = router.read_source(bundle, ContextVariant.FULL_PROVISIONAL_COMBINED, source.path)
        text = result.data.decode("utf-8", errors="strict")
        grouped[component].append(
            {
                "path": source.path,
                "source_sha256": source.sha256,
                "source_bytes": source.byte_length,
                "content_excerpt": text[:12000],
                "excerpt_truncated": len(text) > 12000,
            }
        )
    missing = sorted(component for component, rows in grouped.items() if not rows)
    if missing:
        raise FullStackOctoberError(f"combined provisional context incomplete: {missing}")
    receipts = [
        ProvisionalComponentReceipt.create(
            component_id=component,
            binding=binding,
            lifecycle_stage=ComponentLifecycleStage.PRE_REVEAL_PREFIX,
            executed_stage=ComponentLifecycleStage.PRE_REVEAL_PREFIX,
            status=ComponentStatus.ACTIVE,
            context={"component_id": component, "sources": grouped[component]},
        )
        for component in ACTIVE_PAIRED_COMPONENTS
    ]
    receipts.append(
        ProvisionalComponentReceipt.create(
            component_id="META_LOOP",
            binding=binding,
            lifecycle_stage=ComponentLifecycleStage.POST_EVIDENCE_DIAGNOSTIC,
            executed_stage=ComponentLifecycleStage.PRE_REVEAL_PREFIX,
            status=ComponentStatus.DEFERRED_NOT_YET_LAWFUL,
            context={
                "component_id": "META_LOOP",
                "withheld_sources": [
                    {"path": item.path, "source_sha256": item.sha256}
                    for item in route.withheld_sources
                ],
                "reason": "OUTCOME_DEPENDENT_POST_EVIDENCE_ONLY",
            },
        )
    )
    return tuple(receipts)


def _first_receipts(ledger: DurableJsonlLedger, prefix_hash: str) -> dict[str, str]:
    required = {
        LedgerKind.HELPER_EVIDENCE: "helper_evidence",
        LedgerKind.REASONING: "frankie_reasoning",
        LedgerKind.PROBABILITY: "probability_movie",
    }
    found: dict[str, str] = {}
    for record in ledger.snapshot():
        if record.binding.causal_prefix_hash == prefix_hash and record.kind in required:
            found.setdefault(required[record.kind], record.record_hash)
    if set(found) != set(required.values()):
        raise FullStackOctoberError("paired lane first receipt set is incomplete")
    return found


def make_paired_launch_event(
    *,
    binding: CausalPrefixBinding,
    paired: Any,
    control_ledger: DurableJsonlLedger,
    combined_ledger: DurableJsonlLedger,
) -> dict[str, Any]:
    active_hashes = {
        key: value for key, value in paired.component_receipt_hashes.items() if key != "META_LOOP"
    }
    meta_hash = paired.component_receipt_hashes["META_LOOP"]
    event = {
        "lanes": [LaneId.S135_CONTROL.value, LaneId.FULL_PROVISIONAL_COMBINED.value],
        "primary_lane": LaneId.S135_CONTROL.value,
        "combined_lane": LaneId.FULL_PROVISIONAL_COMBINED.value,
        "model": EXPECTED_MODEL,
        "step1_sealed": True,
        "answer_revealed": False,
        "identical_prefix_proof_hash": paired.identical_prefix_proof.proof_hash,
        "control_causal_prefix_hash": binding.causal_prefix_hash,
        "combined_causal_prefix_hash": binding.causal_prefix_hash,
        "knowledge_manifest_hash": binding.knowledge_manifest_hash,
        "control_provider_response_ids": [
            item.accepted_response.provider_response_id for item in paired.control.invocation_receipts
        ],
        "combined_provider_response_ids": [
            item.accepted_response.provider_response_id for item in paired.combined.invocation_receipts
        ],
        "active_provisional_components": list(ACTIVE_PAIRED_COMPONENTS),
        "active_provisional_component_receipt_hashes": active_hashes,
        "deferred_meta_loop": {
            "component_id": "META_LOOP",
            "status": ComponentStatus.DEFERRED_NOT_YET_LAWFUL.value,
            "lifecycle_stage": ComponentLifecycleStage.POST_EVIDENCE_DIAGNOSTIC.value,
            "executed_stage": ComponentLifecycleStage.PRE_REVEAL_PREFIX.value,
            "receipt_hash": meta_hash,
        },
        "control_lock_authority": paired.control_lock_authority,
        "combined_lock_authority": paired.combined_lock_authority,
        "control_ledger": {
            "lane_id": LaneId.S135_CONTROL.value,
            "path": str(control_ledger.path),
            "control_final_ledger_hash": paired.control.final_ledger_hash,
            "first_receipt_hashes": _first_receipts(control_ledger, binding.causal_prefix_hash),
        },
        "combined_ledger": {
            "lane_id": LaneId.FULL_PROVISIONAL_COMBINED.value,
            "path": str(combined_ledger.path),
            "combined_final_ledger_hash": paired.combined.final_ledger_hash,
            "first_receipt_hashes": _first_receipts(combined_ledger, binding.causal_prefix_hash),
        },
    }
    event["receipt_hash"] = _stable_hash(event)
    return event


def _artifact_hashes(ledger: DurableJsonlLedger) -> dict[str, str]:
    records = ledger.snapshot()
    groups = {
        "candidate_discovery": {LedgerKind.CANDIDATE},
        "helper_evidence": {LedgerKind.HELPER_EVIDENCE},
        "frankie_reasoning": {LedgerKind.REASONING},
        "probability_movie": {LedgerKind.PROBABILITY},
        "first_lock": {LedgerKind.LOCK},
        "no_lock": {LedgerKind.NO_LOCK},
    }
    return {
        name: _stable_hash([row.record_hash for row in records if row.kind in kinds])
        for name, kinds in groups.items()
    }


def _provider_state(row: ContinuousCausalSecond) -> dict[str, Any]:
    return {
        "schema": row.schema_version,
        "source_second": row.source_second,
        "source_object_id": row.source_object_id,
        "source_object_sha256": row.source_object_sha256,
        "legacy": _jsonable(row.legacy),
        "actions": _jsonable(row.actions),
        "v4_native": _jsonable(row.v4_native),
        "quality": _jsonable(row.quality),
        "data_plane_row": row.data_plane_row.core(),
        "protected_prefix_hash": row.prefix.prefix_hash,
        "prospective_mark": None if row.mark is None else _jsonable(row.mark),
        "stream_hash": row.stream_hash,
    }


def _persist_causal_second(
    ledger: DurableJsonlLedger,
    row: ContinuousCausalSecond,
    binding: CausalPrefixBinding,
    prior_stream_hash: str,
) -> None:
    state = _provider_state(row)
    ledger.append(kind=LedgerKind.STATE, binding=binding, content=state)
    ledger.append(
        kind=LedgerKind.STATE_DELTA,
        binding=binding,
        content={
            "prior_stream_hash": prior_stream_hash,
            "stream_hash": row.stream_hash,
            "data_plane_row_hash": row.data_plane_row.row_hash,
            "geometry_hash": row.data_plane_row.geometry.geometry_hash,
        },
    )
    ledger.append(kind=LedgerKind.INTEGRITY, binding=binding, content=_jsonable(row.quality))
    if row.mark is None:
        ledger.append(
            kind=LedgerKind.NO_LOCK,
            binding=binding,
            content={
                "owner": "CAUSAL_OBSERVATION_ONLY",
                "primary_lock": False,
                "reason": "NO_PROSPECTIVE_MARK",
                "weak_negative_sparse_retained": True,
            },
        )


def run_full_october(config: FullStackOctoberConfig) -> dict[str, Any]:
    cfg = config.validate()
    launch = LaunchJsonEventSink()
    manifest = json.loads(cfg.manifest_path.read_text(encoding="utf-8"))
    roster = select_october_source_roster(manifest)
    source_paths = verify_staged_source_roster(roster, cfg.source_root)
    cfg.output_root.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parents[2]

    plane = KnowledgePlane.build(
        repo_root,
        production_source_specs(repo_root),
        contract=october_full_stack_completeness_contract(),
        manifest_version=f"frankie-october-paired:{os.environ.get('SOURCE_COMMIT', 'UNSET')}",
    )
    router = FrankieLaneAwareContextRouter(plane, production_provisional_components(plane))
    launch.emit_launch(
        "KNOWLEDGE_MANIFEST_READY",
        knowledge_manifest_hash=plane.manifest_hash,
        source_count=len(production_source_specs(repo_root)),
        brain_version="s105.9",
        complete_plays=90,
    )

    probe = router.build_routes(run_id=cfg.run_id, state_prefix_hash="0" * 64)
    sealed_paths = [
        item.path for item in production_source_specs(repo_root)
        if item.authority is AuthorityClass.SEALED_TARGET_ANSWER
    ]
    wall_denied = 0
    for path in sealed_paths:
        try:
            router.read_source(probe, ContextVariant.S135_CONTROL, path)
        except KnowledgeAccessDenied:
            wall_denied += 1
    if wall_denied != len(sealed_paths) or not sealed_paths:
        raise FullStackOctoberError("October Step-1 wall failed closed pre-freeze")
    launch.emit_launch("ANSWER_WALL_PREFREEZE_VERIFIED", step1_sealed=True, answer_revealed=False)

    primary_context = plane.context(run_id=cfg.run_id, state_hash="0" * 64)
    denied = 0
    for path in (
        "research/kalshi/ng_exhaustion_october_frankie_v4_bridge_20260824.py",
        "research/kalshi/frankie_bounded_3mo_parallel.py",
    ):
        try:
            plane.read(primary_context, path)
        except KnowledgeAccessDenied:
            denied += 1
    if denied != 2:
        raise FullStackOctoberError("forbidden V3/transport surfaces were not denied")
    launch.emit_launch("FORBIDDEN_V3_DENIED", ordinary_v3_denied=True, d1_extratrees_denied=True)

    causal_ledger = DurableJsonlLedger.create(cfg.output_root / "causal-state.jsonl", run_id=cfg.run_id)
    control_ledger = DurableJsonlLedger.create(cfg.output_root / "s135-control.jsonl", run_id=cfg.run_id)
    combined_ledger = DurableJsonlLedger.create(cfg.output_root / "full-provisional-combined.jsonl", run_id=cfg.run_id)

    stream_source = repo_root / "research/kalshi/ng_exhaustion_frankie_continuous_stream_20260824.py"
    crosswalk = seal_semantic_crosswalk(
        mappings=default_legacy_v4_mappings(),
        source_manifest_sha256=EXPECTED_MANIFEST_SHA256,
        adapter_revision="V4_MBO_FULL_STATE_REPLAY_20260820",
        transform_sha256=_sha256_file(stream_source),
    )
    predecessor = roster[0]
    transition = OpportunityTransition(
        effective_second=TARGET_START,
        opportunity_id=f"predecessor:{predecessor.sha256[:20]}",
        predecessor_ids=(Path(predecessor.key).name,),
        ancestry_ids=(predecessor.key,),
        predecessor_states=("P",),
        ancestry_gap_seconds=(0.0,),
        predecessor_known_by=float(TARGET_START),
        reveal_not_before=float(TARGET_END + 1),
        kind=OpportunityKind.AT_RISK,
        chain_state=ChainExtensionState.UNRESOLVED,
    )
    builder = ContinuousV4CausalStreamBuilder(
        run_id=cfg.run_id,
        target_start_second=TARGET_START,
        target_end_second=TARGET_END,
        source_manifest_sha256=EXPECTED_MANIFEST_SHA256,
        crosswalk=crosswalk,
        opportunity_transitions=(transition,),
        marker=ProtectedProspectiveWeakeningMarker(detector_source_sha256=_sha256_file(stream_source)),
    )
    control_client = OpenAIResponsesClient()
    combined_client = OpenAIResponsesClient()
    marked_prefixes: list[str] = []
    last_runtime: tuple[LaneRuntime, LaneRuntime, tuple[KnowledgeSourceExcerpt, ...], RouteBundle] | None = None
    prior_stream_hash = "0" * 64

    def on_second(row: ContinuousCausalSecond) -> None:
        nonlocal prior_stream_hash, last_runtime
        binding = _binding(row, plane.manifest_hash)
        _persist_causal_second(causal_ledger, row, binding, prior_stream_hash)
        prior_stream_hash = row.stream_hash
        if row.mark is None:
            return
        bundle = router.build_routes(run_id=cfg.run_id, state_prefix_hash=binding.state_prefix_hash)
        knowledge = _base_knowledge(router, bundle)
        control_tools, control_reads = _lane_receipts(
            lane=LaneId.S135_CONTROL, binding=binding, sources=knowledge
        )
        combined_tools, combined_reads = _lane_receipts(
            lane=LaneId.FULL_PROVISIONAL_COMBINED, binding=binding, sources=knowledge
        )
        control_runtime = LaneRuntime(
            LaneId.S135_CONTROL,
            control_client,
            control_ledger,
            LaunchRuntimeEventSink(),
            control_tools,
            control_reads,
        )
        combined_runtime = LaneRuntime(
            LaneId.FULL_PROVISIONAL_COMBINED,
            combined_client,
            combined_ledger,
            LaunchRuntimeEventSink(),
            combined_tools,
            combined_reads,
        )
        orchestrator = PairedLaneOrchestrator(
            prefix_roster=(binding.causal_prefix_hash,),
            control=control_runtime,
            combined=combined_runtime,
            base_knowledge_sources=knowledge,
            event_sink=LaunchPairedEventSink(),
        )
        paired = orchestrator.run_prefix(
            binding=binding,
            causal_state=_provider_state(row),
            component_receipts=_component_receipts(router=router, bundle=bundle, binding=binding),
            answer_revealed=False,
        )
        marked_prefixes.append(binding.causal_prefix_hash)
        last_runtime = (control_runtime, combined_runtime, knowledge, bundle)
        launch.emit_launch(
            "PAIRED_PREFIX_ACCEPTED",
            **make_paired_launch_event(
                binding=binding,
                paired=paired,
                control_ledger=control_ledger,
                combined_ledger=combined_ledger,
            ),
        )

    replay_receipt = replay_dbn_files_to_causal_seconds(
        [str(path) for path in source_paths], builder=builder, on_second=on_second
    )
    if not marked_prefixes or last_runtime is None:
        raise FullStackOctoberError("full October completed without a lawful prospective mark")
    control_runtime, combined_runtime, knowledge, final_bundle = last_runtime
    freeze_orchestrator = PairedLaneOrchestrator(
        prefix_roster=tuple(marked_prefixes),
        control=control_runtime,
        combined=combined_runtime,
        base_knowledge_sources=knowledge,
        event_sink=LaunchPairedEventSink(),
    )
    freeze = freeze_orchestrator.freeze_global_experiment(answer_revealed=False)
    router_freeze = router.freeze_global_experiment(
        final_bundle,
        {
            ContextVariant.S135_CONTROL: _artifact_hashes(control_ledger),
            ContextVariant.FULL_PROVISIONAL_COMBINED: _artifact_hashes(combined_ledger),
        },
    )
    final = {
        "schema": SCHEMA,
        "run_id": cfg.run_id,
        "status": "FULL_OCTOBER_COMPLETE_GLOBAL_EXPERIMENT_FROZEN",
        "source_manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "knowledge_manifest_hash": plane.manifest_hash,
        "crosswalk_receipt_hash": crosswalk.receipt_hash,
        "marked_prefix_count": len(marked_prefixes),
        "global_freeze_receipt_hash": freeze.receipt_hash,
        "knowledge_global_freeze_receipt_hash": router_freeze.receipt_hash,
        "answer_revealed": False,
        "replay": replay_receipt,
    }
    _write_json_exclusive(cfg.output_root / "FINAL_RECEIPT.json", final)
    launch.emit_launch("GLOBAL_EXPERIMENT_FROZEN", **final)
    return final


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the paired full-stack October Frankie experiment")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = FullStackOctoberConfig(
        run_id=args.run_id,
        manifest_path=args.manifest,
        source_root=args.source_root,
        output_root=args.output_root,
    )
    try:
        run_full_october(config)
    except Exception as exc:
        LaunchJsonEventSink().emit_launch(
            "RUN_FAILED", error_type=type(exc).__name__, error=str(exc)[:2000]
        )
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
