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
    HELPER_CPU_MAPPING_VERSION,
    KnowledgeSourceExcerpt,
    LedgerKind,
    RetrievalReceipt,
    RuntimeEvent,
    ToolCallReceipt,
    helper_role_cpu_map,
    validate_helper_cpu_affinity_timing_receipts,
)
from research.kalshi.frankie_causal_operational_context_20260824 import (
    ACCEPTED_MINIMUM_PATHS,
    DecisionStateSnapshot,
    RegistryCoverageOracle,
    build_canonical_s135_snapshot,
    snapshot_availability_audit,
)
from research.kalshi.frankie_causal_runtime_tools_20260824 import (
    CausalEvidenceJournal,
    CausalRuntimeToolBackend,
    validate_causal_evidence_journal,
)
from research.kalshi.frankie_v4_authority_runtime_validation_20260824 import (
    H_RUNTIME_MODULES,
    validate_v4_authority_runtime,
)
from research.kalshi.frankie_v4_governing_runtime_execution_20260824 import (
    build_v4_governing_input_context,
    execute_v4_governing_prefix,
    validate_v4_governing_runtime_receipt,
)
from research.kalshi.frankie_s135_substrate_descriptor_20260824 import (
    validate_substrate_descriptor,
)
from research.kalshi.frankie_full_stack_provisional_combined_pipeline_20260824 import (
    execute_combined_provisional_pipeline,
)
from research.kalshi.frankie_lane_aware_context_router_20260824 import (
    ComponentAvailability,
    ContextVariant,
    FrankieLaneAwareContextRouter,
    ProvisionalComponent,
    RouteBundle,
)
from research.kalshi.frankie_october_knowledge_inventory_20260824 import (
    PROVISIONAL_SOURCE_DISPOSITIONS,
    production_source_specs,
    sealed_step1_external_descriptors,
)
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
from research.kalshi.frankie_provider_knowledge_tools_20260824 import (
    CompositeProviderToolBackend,
    LaneKnowledgeToolBackend,
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
CAUSAL_SECOND_CHAIN_SCHEMA = "FRANKIE_CAUSAL_SECOND_CHAIN_V1_20260824"
OCTOBER_REPLAY_PROGRESS_SCHEMA = "FRANKIE_OCTOBER_REPLAY_PROGRESS_V1_20260824"
CAUSAL_SECOND_CHAIN_GENESIS = "0" * 64
CAUSAL_SECOND_FLUSH_INTERVAL = 512
_OBJECT_DATE = re.compile(r"glbx-mdp3-(20\d{6})\.mbo\.dbn\.zst$")
PAIRED_COMPONENTS = tuple(COMBINED_COMPONENTS)
ACTIVE_PAIRED_COMPONENTS = tuple(item for item in PAIRED_COMPONENTS if item != "META_LOOP")
BASE_SOURCE_EXCERPT_BYTES = 2048
_D1_EXTRATREES_PATH = (
    "research/generated/ng_exhaustion_entry_timing_revival_20260819/"
    "d1_d5_predictability_agents/NG_EXHAUSTION_D1_D5_PREDICTABILITY_ALL_AGENT_RESULTS_20260819.json"
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


def make_october_replay_progress(
    *, processed_source_second: int, accepted_prefix_count: int
) -> dict[str, Any]:
    """Return a fixed-October, content-addressed replay done/left receipt."""
    if isinstance(processed_source_second, bool) or not isinstance(
        processed_source_second, int
    ):
        raise FullStackOctoberError("processed_source_second must be an integer")
    if (
        isinstance(accepted_prefix_count, bool)
        or not isinstance(accepted_prefix_count, int)
        or accepted_prefix_count < 0
    ):
        raise FullStackOctoberError("accepted_prefix_count must be a non-negative integer")
    total_seconds = TARGET_END - TARGET_START
    done_seconds = min(
        total_seconds,
        max(0, processed_source_second - TARGET_START + 1),
    )
    completed_percent = (done_seconds * 100) // total_seconds
    core = {
        "schema": OCTOBER_REPLAY_PROGRESS_SCHEMA,
        "target_start": TARGET_START,
        "target_end": TARGET_END,
        "processed_source_second": processed_source_second,
        "total_seconds": total_seconds,
        "done_seconds": done_seconds,
        "left_seconds": total_seconds - done_seconds,
        "completed_percent": completed_percent,
        "remaining_percent": 100 - completed_percent,
        "accepted_prefix_count": accepted_prefix_count,
    }
    return {**core, "receipt_hash": _stable_hash(core)}


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


def _canonical_chain_json(value: Any, field_name: str) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise FullStackOctoberError(
            f"causal-second {field_name} must be deterministic JSON"
        ) from exc


def _causal_chain_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_chain_json(value, "hash payload").encode()).hexdigest()


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(path, flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


class CausalSecondJsonlWriter:
    """Linear append-only causal-second chain with bounded durability epochs.

    Unlike the strict helper/Frankie lane ledgers, this single-owner high-volume
    stream never rereads its growing file during append.  Each second is one
    self-contained hash-chained record.  The open descriptor is periodically
    fsynced and is always fsynced once more before final close.
    """

    def __init__(
        self,
        *,
        path: Path,
        run_id: str,
        fd: int,
        flush_interval_records: int,
    ) -> None:
        self.path = path
        self.run_id = run_id
        self._fd: int | None = fd
        self._flush_interval_records = flush_interval_records
        self._record_count = 0
        self._head_hash = CAUSAL_SECOND_CHAIN_GENESIS
        self._last_causal_cutoff: float | None = None
        self._periodic_fsync_count = 0
        self._close_receipt: dict[str, Any] | None = None

    @classmethod
    def create(
        cls,
        path: str | Path,
        *,
        run_id: str,
        flush_interval_records: int = CAUSAL_SECOND_FLUSH_INTERVAL,
    ) -> "CausalSecondJsonlWriter":
        target = Path(path)
        if not str(run_id or "").strip():
            raise FullStackOctoberError("causal-second run_id is required")
        if (
            isinstance(flush_interval_records, bool)
            or not isinstance(flush_interval_records, int)
            or flush_interval_records <= 0
        ):
            raise FullStackOctoberError("causal-second flush interval must be a positive integer")
        if not target.parent.is_dir():
            raise FullStackOctoberError("causal-second parent directory does not exist")
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_APPEND
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            fd = os.open(target, flags, 0o600)
        except OSError as exc:
            raise FullStackOctoberError("causal-second exclusive creation failed") from exc
        try:
            os.fsync(fd)
            _fsync_directory(target.parent)
        except BaseException:
            os.close(fd)
            raise
        return cls(
            path=target,
            run_id=run_id,
            fd=fd,
            flush_interval_records=flush_interval_records,
        )

    def append_second(
        self,
        *,
        binding: CausalPrefixBinding,
        state: Mapping[str, Any],
        delta: Mapping[str, Any],
        integrity: Mapping[str, Any],
        decision: Mapping[str, Any],
    ) -> str:
        if self._fd is None:
            raise FullStackOctoberError("causal-second writer is closed")
        bound = binding.validate()
        if bound.run_id != self.run_id:
            raise FullStackOctoberError("causal-second binding run_id mismatch")
        if self._last_causal_cutoff is not None and bound.causal_cutoff < self._last_causal_cutoff:
            raise FullStackOctoberError("causal-second writer refuses causal backfill")
        for name, value in (
            ("state", state),
            ("delta", delta),
            ("integrity", integrity),
            ("decision", decision),
        ):
            if not isinstance(value, Mapping):
                raise FullStackOctoberError(f"causal-second {name} must be an object")
        decision_type = decision.get("type")
        if decision_type not in {"NO_LOCK", "PROSPECTIVE_MARK"}:
            raise FullStackOctoberError("causal-second decision must be explicit")
        if decision.get("owner") != "CAUSAL_OBSERVATION_ONLY" or decision.get("primary_lock") is not False:
            raise FullStackOctoberError("causal-second decision cannot claim primary lock authority")

        content = {
            "state": dict(state),
            "delta": dict(delta),
            "integrity": dict(integrity),
            "decision": dict(decision),
        }
        content_hash = _causal_chain_hash(content)
        core = {
            "schema": CAUSAL_SECOND_CHAIN_SCHEMA,
            "run_id": self.run_id,
            "sequence": self._record_count,
            "causal_cutoff": bound.causal_cutoff,
            "binding": bound.identity_payload(),
            "content_hash": content_hash,
            "prior_record_hash": self._head_hash,
        }
        record_hash = _causal_chain_hash(core)
        payload = _canonical_chain_json(
            {**core, "content": content, "record_hash": record_hash}, "record"
        ).encode() + b"\n"
        offset = 0
        while offset < len(payload):
            try:
                written = os.write(self._fd, payload[offset:])
            except InterruptedError:
                continue
            if written <= 0:
                raise FullStackOctoberError("causal-second append made no progress")
            offset += written

        self._record_count += 1
        self._head_hash = record_hash
        self._last_causal_cutoff = bound.causal_cutoff
        if self._record_count % self._flush_interval_records == 0:
            os.fsync(self._fd)
            self._periodic_fsync_count += 1
        return record_hash

    def close(self) -> dict[str, Any]:
        if self._close_receipt is not None:
            return dict(self._close_receipt)
        if self._fd is None:
            raise FullStackOctoberError("causal-second writer has no open descriptor")
        fd = self._fd
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
            self._fd = None
        self._close_receipt = {
            "schema": CAUSAL_SECOND_CHAIN_SCHEMA,
            "run_id": self.run_id,
            "path": str(self.path),
            "record_count": self._record_count,
            "head_hash": self._head_hash,
            "flush_interval_records": self._flush_interval_records,
            "periodic_fsync_count": self._periodic_fsync_count,
            "final_fsync_completed": True,
        }
        return dict(self._close_receipt)


def validate_causal_second_jsonl(path: str | Path, *, run_id: str) -> dict[str, Any]:
    """Stream-validate the causal-second chain without retaining its records."""
    target = Path(path)
    expected_sequence = 0
    expected_prior = CAUSAL_SECOND_CHAIN_GENESIS
    last_cutoff: float | None = None
    try:
        handle = target.open("r", encoding="utf-8")
    except OSError as exc:
        raise FullStackOctoberError("causal-second validation open failed") from exc
    with handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                record = json.loads(line)
            except (TypeError, ValueError) as exc:
                raise FullStackOctoberError(
                    f"causal-second record {line_number} is not valid JSON"
                ) from exc
            if not isinstance(record, Mapping):
                raise FullStackOctoberError("causal-second record must be an object")
            if record.get("schema") != CAUSAL_SECOND_CHAIN_SCHEMA:
                raise FullStackOctoberError("causal-second schema mismatch")
            if record.get("run_id") != run_id or record.get("sequence") != expected_sequence:
                raise FullStackOctoberError("causal-second identity or sequence mismatch")
            if record.get("prior_record_hash") != expected_prior:
                raise FullStackOctoberError("causal-second prior hash mismatch")
            binding_payload = record.get("binding")
            try:
                bound = CausalPrefixBinding(**binding_payload).validate()
            except (TypeError, ValueError, RuntimeError) as exc:
                raise FullStackOctoberError("causal-second binding is invalid") from exc
            if bound.run_id != run_id or bound.causal_cutoff != record.get("causal_cutoff"):
                raise FullStackOctoberError("causal-second binding identity mismatch")
            if last_cutoff is not None and bound.causal_cutoff < last_cutoff:
                raise FullStackOctoberError("causal-second causal cutoff regressed")
            content = record.get("content")
            if not isinstance(content, Mapping) or set(content) != {
                "state",
                "delta",
                "integrity",
                "decision",
            }:
                raise FullStackOctoberError("causal-second content is incomplete")
            decision = content.get("decision")
            if (
                not isinstance(decision, Mapping)
                or decision.get("type") not in {"NO_LOCK", "PROSPECTIVE_MARK"}
                or decision.get("owner") != "CAUSAL_OBSERVATION_ONLY"
                or decision.get("primary_lock") is not False
            ):
                raise FullStackOctoberError("causal-second decision is invalid")
            content_hash = _causal_chain_hash(content)
            if record.get("content_hash") != content_hash:
                raise FullStackOctoberError("causal-second content hash mismatch")
            core = {
                "schema": record["schema"],
                "run_id": record["run_id"],
                "sequence": record["sequence"],
                "causal_cutoff": record["causal_cutoff"],
                "binding": binding_payload,
                "content_hash": content_hash,
                "prior_record_hash": record["prior_record_hash"],
            }
            record_hash = _causal_chain_hash(core)
            if record.get("record_hash") != record_hash:
                raise FullStackOctoberError("causal-second record hash mismatch")
            expected_sequence += 1
            expected_prior = record_hash
            last_cutoff = bound.causal_cutoff
    return {
        "schema": CAUSAL_SECOND_CHAIN_SCHEMA,
        "run_id": run_id,
        "path": str(target),
        "record_count": expected_sequence,
        "head_hash": expected_prior,
        "chain_validated": True,
    }


def paired_component_id(path: str) -> str:
    try:
        return PROVISIONAL_SOURCE_DISPOSITIONS[path].component_id
    except KeyError as exc:
        raise FullStackOctoberError(
            f"provisional source has no reviewed disposition: {path}"
        ) from exc


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


def _verify_denied(plane: KnowledgePlane, context: Any, path: str, reason: str) -> bool:
    try:
        plane.read(context, path)
    except KnowledgeAccessDenied as exc:
        return reason in str(exc)
    except KeyError:
        # A repository artifact outside the servable catalog is denied by
        # construction; the existence check for the known D1 artifact is
        # performed separately below.
        return True
    return False


def _knowledge_preflight(
    *,
    plane: KnowledgePlane,
    specs: Sequence[Any],
    repo_root: Path,
    output_root: Path,
    run_id: str,
    sink: LaunchJsonEventSink,
) -> dict[str, Any]:
    state_hash = _stable_hash({"run_id": run_id, "phase": "PREFLIGHT"})
    primary = plane.context(run_id=run_id, state_hash=state_hash, lane=RetrievalLane.PRIMARY)
    sealed_paths = tuple(
        spec.path for spec in specs if spec.authority is AuthorityClass.SEALED_TARGET_ANSWER
    )
    if not sealed_paths or not all(
        _verify_denied(plane, primary, path, "ANSWER_WALL_PRE_FREEZE")
        for path in sealed_paths
    ):
        raise FullStackOctoberError("October Step-1 answer wall preflight failed")
    external_descriptors = plane.external_descriptors
    if not external_descriptors or any(
        item.authority is not AuthorityClass.SEALED_TARGET_ANSWER
        or item.content_accessed is not False
        or not item.descriptor_sha256
        for item in external_descriptors
    ):
        raise FullStackOctoberError("sealed Step-1 external descriptor preflight failed")

    ordinary_v3 = tuple(
        spec.path
        for spec in specs
        if "v3" in spec.path.lower() and "extra_agent" not in Path(spec.path).name.lower()
    )
    if not ordinary_v3 or not all(
        _verify_denied(plane, primary, path, "FORBIDDEN_V3_D1_EXTRATREES")
        for path in ordinary_v3
    ):
        raise FullStackOctoberError("ordinary V3 denial preflight failed")

    d1_path = repo_root / _D1_EXTRATREES_PATH
    if not d1_path.is_file():
        raise FullStackOctoberError("known D1 ExtraTrees artifact is absent from repository preflight")
    if not _verify_denied(
        plane, primary, _D1_EXTRATREES_PATH, "FORBIDDEN_V3_D1_EXTRATREES"
    ):
        raise FullStackOctoberError("D1 ExtraTrees denial preflight failed")

    core = {
        "schema": "FRANKIE_FULLSTACK_OCTOBER_PREFLIGHT_V1",
        "run_id": run_id,
        "knowledge_manifest_hash": plane.manifest_hash,
        "step1_sealed": True,
        "answer_revealed": False,
        "sealed_source_count": len(sealed_paths),
        "sealed_external_descriptor_count": len(external_descriptors),
        "ordinary_v3_denied": True,
        "ordinary_v3_source_count": len(ordinary_v3),
        "d1_extratrees_denied": True,
    }
    receipt = {**core, "receipt_hash": _stable_hash(core)}
    _write_json_exclusive(output_root / "PREFLIGHT.json", receipt)
    sink.emit_launch(
        "KNOWLEDGE_MANIFEST_READY",
        knowledge_manifest_hash=plane.manifest_hash,
        source_count=len(specs) + len(external_descriptors),
        brain_version="s105.9",
        complete_plays=90,
        receipt_hash=receipt["receipt_hash"],
    )
    sink.emit_launch(
        "ANSWER_WALL_PREFREEZE_VERIFIED",
        step1_sealed=True,
        answer_revealed=False,
        sealed_source_count=len(sealed_paths),
        sealed_external_descriptor_count=len(external_descriptors),
        receipt_hash=receipt["receipt_hash"],
    )
    sink.emit_launch(
        "FORBIDDEN_V3_DENIED",
        ordinary_v3_denied=True,
        d1_extratrees_denied=True,
        receipt_hash=receipt["receipt_hash"],
    )
    return receipt


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
    route = bundle.routes[ContextVariant.S135_CONTROL]
    for source in route.base_sources:
        end = min(source.byte_length, BASE_SOURCE_EXCERPT_BYTES)
        if end <= 0:
            raise FullStackOctoberError(f"routed base source is empty: {source.path}")
        while True:
            result = router.read_source(
                bundle,
                ContextVariant.S135_CONTROL,
                source.path,
                start=0,
                end_exclusive=end,
            )
            try:
                text = result.data.decode("utf-8")
                break
            except UnicodeDecodeError as exc:
                if exc.start <= 0:
                    raise FullStackOctoberError(
                        f"routed base source is not UTF-8 text: {source.path}"
                    ) from exc
                end = exc.start
        if not text.strip():
            raise FullStackOctoberError(f"routed base source excerpt is blank: {source.path}")
        excerpts.append(
            KnowledgeSourceExcerpt.create(
                source_id=result.entry.source_id,
                source_sha256=result.entry.sha256,
                byte_start=0,
                excerpt=text,
            )
        )
    if len(excerpts) != len(route.base_sources):
        raise FullStackOctoberError("provider-visible base source coverage is incomplete")
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
    causal_state: Mapping[str, Any],
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
    return execute_combined_provisional_pipeline(
        binding=binding,
        causal_state=causal_state,
        source_contexts=grouped,
    )


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


def _provider_tool_evidence(invocations: Sequence[Any], journal: Any) -> dict[str, Any]:
    """Prove every provider role read values, not merely the snapshot manifest."""
    causal_tool_names = {
        "decision_state_manifest",
        "decision_state_list",
        "decision_state_search",
        "decision_state_read",
        "prior_causal_state",
        "prior_causal_delta",
        "raw_event_range",
    }
    provider_tools: list[Any] = []
    per_invocation: list[dict[str, Any]] = []
    for invocation in invocations:
        causal_tools = tuple(
            tool for tool in invocation.tool_calls if tool.tool_name in causal_tool_names
        )
        provider_tools.extend(causal_tools)
        value_read_receipt_hashes = tuple(
            str(item)
            for item in getattr(invocation, "value_state_read_receipt_hashes", ())
        )
        response_id = str(invocation.accepted_response.provider_response_id)
        if any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in value_read_receipt_hashes):
            raise FullStackOctoberError(
                f"provider invocation {response_id} has an invalid value-state read receipt hash"
            )
        row = {
            "provider_response_id": response_id,
            "causal_call_count": len(causal_tools),
            "value_state_read_count": len(value_read_receipt_hashes),
            "value_state_read_receipt_hashes": list(value_read_receipt_hashes),
        }
        per_invocation.append(row)
        if not value_read_receipt_hashes:
            raise FullStackOctoberError(
                f"provider invocation {response_id} has no successful value-bearing decision-state read"
            )
    receipt_hashes = [
        _stable_hash(
            {
                "tool_call_id": tool.tool_call_id,
                "tool_name": tool.tool_name,
                "request_hash": tool.request_hash,
                "response_hash": tool.response_hash,
            }
        )
        for tool in provider_tools
    ]
    return {
        "call_count": len(provider_tools),
        "tool_receipt_hashes": receipt_hashes,
        "invocation_count": len(per_invocation),
        "value_state_read_count": sum(
            int(row["value_state_read_count"]) for row in per_invocation
        ),
        "value_state_read_invocation_count": sum(
            int(row["value_state_read_count"] > 0) for row in per_invocation
        ),
        "per_invocation": per_invocation,
        "evidence_journal_record_count": journal.record_count,
        "evidence_journal_head_hash": journal.head_hash,
    }


def _helper_cpu_execution(paired: Any) -> dict[str, Any]:
    lanes: dict[str, Any] = {}
    for lane_id, result in (
        (LaneId.S135_CONTROL.value, paired.control),
        (LaneId.FULL_PROVISIONAL_COMBINED.value, paired.combined),
    ):
        receipts = validate_helper_cpu_affinity_timing_receipts(
            result.helper_cpu_affinity_receipts,
            binding=result.binding,
            lane_id=lane_id,
        )
        batch_started = min(item.started_monotonic_ns for item in receipts)
        batch_ended = max(item.ended_monotonic_ns for item in receipts)
        lanes[lane_id] = {
            "receipts": [asdict(item) for item in receipts],
            "receipt_hashes": [item.receipt_hash for item in receipts],
            "batch_started_monotonic_ns": batch_started,
            "batch_ended_monotonic_ns": batch_ended,
            "batch_duration_ns": batch_ended - batch_started,
        }
    return {
        "mapping_version": HELPER_CPU_MAPPING_VERSION,
        "role_cpu_map": {
            role.value: cpu for role, cpu in helper_role_cpu_map().items()
        },
        "process_effective_affinity": sorted(os.sched_getaffinity(0)),
        "lanes": lanes,
    }


def make_paired_launch_event(
    *,
    binding: CausalPrefixBinding,
    paired: Any,
    control_ledger: DurableJsonlLedger,
    combined_ledger: DurableJsonlLedger,
    decision_snapshot: DecisionStateSnapshot,
    control_evidence: CausalEvidenceJournal,
    combined_evidence: CausalEvidenceJournal,
    governing_receipt: Mapping[str, Any],
    october_replay_progress: Mapping[str, Any],
) -> dict[str, Any]:
    active_hashes = {
        key: value for key, value in paired.component_receipt_hashes.items() if key != "META_LOOP"
    }
    meta_hash = paired.component_receipt_hashes["META_LOOP"]
    causal_quarantine_count = sum(
        str(field.missing_reason or "").startswith("UNAVAILABLE_CAUSAL_QUARANTINE_")
        for field in decision_snapshot.fields
    )
    same_day_weather_quarantine_count = sum(
        field.missing_reason == "UNAVAILABLE_CAUSAL_QUARANTINE_SAME_DAY_REALIZED_WEATHER"
        for field in decision_snapshot.fields
    )
    same_day_weather_present_count = sum(
        field.path.startswith("weather.")
        and str(getattr(field.status, "value", field.status)) == "PRESENT"
        for field in decision_snapshot.fields
    )
    if (
        decision_snapshot.schema_registered_count < ACCEPTED_MINIMUM_PATHS
        or decision_snapshot.schema_registered_count != decision_snapshot.registry_path_count
        or decision_snapshot.present_count
        + decision_snapshot.explicit_null_count
        + decision_snapshot.unavailable_count
        != decision_snapshot.schema_registered_count
        or decision_snapshot.present_count <= 0
        or same_day_weather_present_count != 0
        or decision_snapshot.build_status != "CANONICAL_S135_ACCEPTED"
    ):
        raise FullStackOctoberError("decision-state launch evidence is incomplete or non-causal")
    try:
        governing = validate_v4_governing_runtime_receipt(governing_receipt)
    except ValueError as exc:
        raise FullStackOctoberError(f"governing H runtime evidence is invalid: {exc}") from exc
    direct_count = governing["disposition_counts"].get("DIRECT_OPERATIONAL_EXECUTION", 0)
    superseded_count = governing["disposition_counts"].get(
        "SUPERSEDED_BY_CORRECTED_RUNTIME_EQUIVALENCE", 0
    )
    replay_progress = dict(october_replay_progress)
    replay_progress_hash = replay_progress.pop("receipt_hash", None)
    if (
        replay_progress.get("schema") != OCTOBER_REPLAY_PROGRESS_SCHEMA
        or replay_progress.get("target_start") != TARGET_START
        or replay_progress.get("target_end") != TARGET_END
        or replay_progress_hash != _stable_hash(replay_progress)
    ):
        raise FullStackOctoberError("October replay progress receipt is invalid")
    replay_progress["receipt_hash"] = replay_progress_hash
    event = {
        "lanes": [LaneId.S135_CONTROL.value, LaneId.FULL_PROVISIONAL_COMBINED.value],
        "primary_lane": LaneId.S135_CONTROL.value,
        "combined_lane": LaneId.FULL_PROVISIONAL_COMBINED.value,
        "model": EXPECTED_MODEL,
        "step1_sealed": True,
        "answer_revealed": False,
        "helper_cpu_execution": _helper_cpu_execution(paired),
        "october_replay_progress": replay_progress,
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
        "decision_state": {
            "registered_path_count": decision_snapshot.schema_registered_count,
            "schema_registered_count": decision_snapshot.schema_registered_count,
            "provider_path_count": decision_snapshot.path_count,
            "registered_block_count": decision_snapshot.registry_block_count,
            "provider_block_count": decision_snapshot.block_count,
            "registry_baseline_path_count": decision_snapshot.registry_path_count,
            "emitted_leaf_count": decision_snapshot.emitted_leaf_count,
            "emitted_registered_count": decision_snapshot.emitted_registered_count,
            "emitted_additive_count": decision_snapshot.emitted_additive_count,
            "present_count": decision_snapshot.present_count,
            "explicit_null_count": decision_snapshot.explicit_null_count,
            "unavailable_count": decision_snapshot.unavailable_count,
            "emitted_coverage_fraction": decision_snapshot.emitted_coverage_fraction,
            "value_coverage_fraction": decision_snapshot.value_coverage_fraction,
            "source_snapshot_leaf_count": decision_snapshot.source_snapshot_leaf_count,
            "source_snapshot_leaf_hash": decision_snapshot.source_snapshot_leaf_hash,
            "availability_matrix_hash": decision_snapshot.availability_matrix["matrix_hash"],
            "availability_matrix_block_count": decision_snapshot.availability_matrix["block_count"],
            "availability_matrix": _jsonable(decision_snapshot.availability_matrix["blocks"]),
            "availability_audit": _jsonable(
                getattr(decision_snapshot, "availability_audit", None)
                or snapshot_availability_audit(decision_snapshot)
            ),
            "causal_quarantine_count": causal_quarantine_count,
            "same_day_realized_weather_quarantine_count": same_day_weather_quarantine_count,
            "same_day_realized_weather_present_count": same_day_weather_present_count,
            "coverage_status": decision_snapshot.build_status,
            "registry_receipt_hash": decision_snapshot.registry_receipt_hash,
            "control_snapshot_hash": decision_snapshot.snapshot_hash,
            "combined_snapshot_hash": decision_snapshot.snapshot_hash,
        },
        "provider_tool_evidence": {
            LaneId.S135_CONTROL.value: _provider_tool_evidence(
                paired.control.invocation_receipts, control_evidence
            ),
            LaneId.FULL_PROVISIONAL_COMBINED.value: _provider_tool_evidence(
                paired.combined.invocation_receipts, combined_evidence
            ),
        },
        "v4_governing_runtime": {
            "governing_runtime_receipt_hash": governing["receipt_hash"],
            "module_count": governing["module_count"],
            "module_identities": governing["module_identities"],
            "module_identity_hash": governing["module_identity_hash"],
            "disposition_counts": governing["disposition_counts"],
            "direct_operational_execution_count": direct_count,
            "superseded_equivalence_count": superseded_count,
            "module_evidence": governing["modules"],
            # Backward-compatible alias while workflow gates migrate to module_evidence.
            "modules": governing["modules"],
        },
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
    writer: CausalSecondJsonlWriter,
    row: ContinuousCausalSecond,
    binding: CausalPrefixBinding,
    prior_stream_hash: str,
) -> str:
    state = _provider_state(row)
    mark = None if row.mark is None else _jsonable(row.mark)
    return writer.append_second(
        binding=binding,
        state=state,
        delta={
            "prior_stream_hash": prior_stream_hash,
            "stream_hash": row.stream_hash,
            "data_plane_row_hash": row.data_plane_row.row_hash,
            "geometry_hash": row.data_plane_row.geometry.geometry_hash,
        },
        integrity=_jsonable(row.quality),
        decision={
            "type": "NO_LOCK" if mark is None else "PROSPECTIVE_MARK",
            "owner": "CAUSAL_OBSERVATION_ONLY",
            "primary_lock": False,
            "reason": "NO_PROSPECTIVE_MARK" if mark is None else "PROSPECTIVE_MARK_OBSERVED",
            "weak_negative_sparse_retained": True,
            "mark": mark,
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
    authority_validation = validate_v4_authority_runtime(repo_root)
    _write_json_exclusive(
        cfg.output_root / "v4-authority-runtime-validation.json", authority_validation
    )
    launch.emit_launch(
        "V4_AUTHORITY_RUNTIME_VALIDATED",
        h_module_count=authority_validation["h_module_count"],
        i_record_count=authority_validation["i_record_count"],
        receipt_hash=authority_validation["receipt_hash"],
    )

    specs = production_source_specs(repo_root)
    external_descriptors = sealed_step1_external_descriptors(repo_root)
    plane = KnowledgePlane.build(
        repo_root,
        specs,
        contract=october_full_stack_completeness_contract(),
        manifest_version=f"frankie-october-paired:{os.environ.get('SOURCE_COMMIT', 'UNSET')}",
        external_descriptors=external_descriptors,
    )
    router = FrankieLaneAwareContextRouter(plane, production_provisional_components(plane))
    _knowledge_preflight(
        plane=plane,
        specs=specs,
        repo_root=repo_root,
        output_root=cfg.output_root,
        run_id=cfg.run_id,
        sink=launch,
    )

    source_commit = str(os.environ.get("SOURCE_COMMIT") or "").strip().lower()
    if len(source_commit) != 40 or any(ch not in "0123456789abcdef" for ch in source_commit):
        raise FullStackOctoberError("SOURCE_COMMIT must bind the run to an exact 40-character commit")
    registry_oracle = RegistryCoverageOracle.from_repo(repo_root)
    substrate_descriptor_path = cfg.source_root / "S135_SUBSTRATE_DESCRIPTOR.json"
    try:
        substrate_descriptor = validate_substrate_descriptor(
            json.loads(substrate_descriptor_path.read_text(encoding="utf-8")),
            oracle=registry_oracle,
        )
    except (OSError, TypeError, ValueError) as exc:
        raise FullStackOctoberError("canonical S135 substrate descriptor preflight failed") from exc
    causal_writer = CausalSecondJsonlWriter.create(
        cfg.output_root / "causal-state.jsonl", run_id=cfg.run_id
    )
    control_ledger = DurableJsonlLedger.create(cfg.output_root / "s135-control.jsonl", run_id=cfg.run_id)
    combined_ledger = DurableJsonlLedger.create(cfg.output_root / "full-provisional-combined.jsonl", run_id=cfg.run_id)
    control_causal_evidence = CausalEvidenceJournal.create(
        cfg.output_root / "s135-control-causal-evidence.jsonl", run_id=cfg.run_id
    )
    combined_causal_evidence = CausalEvidenceJournal.create(
        cfg.output_root / "full-provisional-combined-causal-evidence.jsonl", run_id=cfg.run_id
    )
    for journal in (control_causal_evidence, combined_causal_evidence):
        journal.record_answer_access(
            allowed=False, reason="SEALED_UNTIL_PRIMARY_FREEZE"
        )
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
    governing_runtime_receipt_hashes: list[str] = []
    last_runtime: tuple[LaneRuntime, LaneRuntime, tuple[KnowledgeSourceExcerpt, ...], RouteBundle] | None = None
    last_decision_snapshot: DecisionStateSnapshot | None = None
    prior_stream_hash = "0" * 64
    last_progress_percent = 0
    last_replay_progress = make_october_replay_progress(
        processed_source_second=TARGET_START - 1,
        accepted_prefix_count=0,
    )

    def update_replay_progress(processed_source_second: int) -> dict[str, Any]:
        nonlocal last_progress_percent, last_replay_progress
        progress = make_october_replay_progress(
            processed_source_second=processed_source_second,
            accepted_prefix_count=len(marked_prefixes),
        )
        last_replay_progress = progress
        percent = int(progress["completed_percent"])
        if percent > last_progress_percent:
            launch.emit_launch("OCTOBER_REPLAY_PROGRESS", **progress)
            last_progress_percent = percent
        return progress

    def on_second(row: ContinuousCausalSecond) -> None:
        nonlocal prior_stream_hash, last_runtime, last_decision_snapshot
        binding = _binding(row, plane.manifest_hash)
        causal_record_hash = _persist_causal_second(
            causal_writer, row, binding, prior_stream_hash
        )
        prior_stream_hash = row.stream_hash
        if row.mark is None:
            update_replay_progress(row.source_second)
            return
        raw_event_receipt = {
            "start_source_second": row.source_second,
            "end_source_second": row.source_second,
            "causal_cutoff": binding.causal_cutoff,
            "causal_record_hash": causal_record_hash,
            "raw_event_count": len(row.actions),
            "causal_prefix_hash": binding.causal_prefix_hash,
        }
        for journal in (control_causal_evidence, combined_causal_evidence):
            journal.append("RAW_EVENT_RANGE", raw_event_receipt)
        decision_snapshot = build_canonical_s135_snapshot(
            repo_root=repo_root,
            run_id=cfg.run_id,
            decision_day=datetime.fromtimestamp(row.source_second, tz=timezone.utc).strftime("%Y%m%d"),
            evaluated_at=binding.causal_cutoff,
            group=os.environ.get("FRANKIE_S135_GROUP", "3"),
            oracle=registry_oracle,
        )
        present_fields = sum(
            int(family["present"]) for family in decision_snapshot.family_manifest.values()
        )
        if (
            decision_snapshot.build_status != "CANONICAL_S135_ACCEPTED"
            or present_fields <= 0
        ):
            raise FullStackOctoberError(
                "canonical S135 operational substrate was not accepted with present causal values"
            )
        causal_state = _provider_state(row)
        causal_state["operational_decision_state"] = decision_snapshot.provider_payload()
        governing_input_context = build_v4_governing_input_context(
            binding=binding,
            snapshot=decision_snapshot,
            source_object_id=row.source_object_id,
            source_object_sha256=row.source_object_sha256,
        )
        causal_state["v4_governing_runtime_context"] = governing_input_context
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
            CompositeProviderToolBackend(
                LaneKnowledgeToolBackend(
                    router=router,
                    bundle=bundle,
                    variant=ContextVariant.S135_CONTROL,
                ),
                CausalRuntimeToolBackend(
                    snapshot=decision_snapshot,
                    binding=binding,
                    causal_state_path=causal_writer.path,
                    evidence_journal=control_causal_evidence,
                    commit_sha=source_commit,
                ),
            ),
        )
        combined_runtime = LaneRuntime(
            LaneId.FULL_PROVISIONAL_COMBINED,
            combined_client,
            combined_ledger,
            LaunchRuntimeEventSink(),
            combined_tools,
            combined_reads,
            CompositeProviderToolBackend(
                LaneKnowledgeToolBackend(
                    router=router,
                    bundle=bundle,
                    variant=ContextVariant.FULL_PROVISIONAL_COMBINED,
                ),
                CausalRuntimeToolBackend(
                    snapshot=decision_snapshot,
                    binding=binding,
                    causal_state_path=causal_writer.path,
                    evidence_journal=combined_causal_evidence,
                    commit_sha=source_commit,
                ),
            ),
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
            causal_state=causal_state,
            component_receipts=_component_receipts(
                router=router,
                bundle=bundle,
                binding=binding,
                causal_state=causal_state,
            ),
            answer_revealed=False,
        )
        governing_receipt = execute_v4_governing_prefix(
            binding=binding,
            snapshot=decision_snapshot,
            paired=paired,
            source_object_id=row.source_object_id,
            source_object_sha256=row.source_object_sha256,
            source_commit=source_commit,
            governing_input_context=governing_input_context,
        )
        for journal in (control_causal_evidence, combined_causal_evidence):
            journal.append("V4_GOVERNING_RUNTIME_EXECUTION", governing_receipt)
        governing_runtime_receipt_hashes.append(governing_receipt["receipt_hash"])
        marked_prefixes.append(binding.causal_prefix_hash)
        last_decision_snapshot = decision_snapshot
        last_runtime = (control_runtime, combined_runtime, knowledge, bundle)
        replay_progress = update_replay_progress(row.source_second)
        launch.emit_launch(
            "PAIRED_PREFIX_ACCEPTED",
            **make_paired_launch_event(
                binding=binding,
                paired=paired,
                control_ledger=control_ledger,
                combined_ledger=combined_ledger,
                decision_snapshot=decision_snapshot,
                control_evidence=control_causal_evidence,
                combined_evidence=combined_causal_evidence,
                governing_receipt=governing_receipt,
                october_replay_progress=replay_progress,
            ),
        )

    try:
        replay_receipt = replay_dbn_files_to_causal_seconds(
            [str(path) for path in source_paths], builder=builder, on_second=on_second
        )
        update_replay_progress(TARGET_END - 1)
    finally:
        causal_chain_receipt = causal_writer.close()
        control_causal_evidence.close()
        combined_causal_evidence.close()
    causal_chain_validation = validate_causal_second_jsonl(
        causal_writer.path, run_id=cfg.run_id
    )
    control_causal_evidence_validation = validate_causal_evidence_journal(
        control_causal_evidence.path, run_id=cfg.run_id
    )
    combined_causal_evidence_validation = validate_causal_evidence_journal(
        combined_causal_evidence.path, run_id=cfg.run_id
    )
    if (
        causal_chain_validation["record_count"] != causal_chain_receipt["record_count"]
        or causal_chain_validation["head_hash"] != causal_chain_receipt["head_hash"]
    ):
        raise FullStackOctoberError("causal-second final chain receipt mismatch")
    if not marked_prefixes or last_runtime is None or last_decision_snapshot is None:
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
        "v4_authority_runtime_receipt_hash": authority_validation["receipt_hash"],
        "s135_substrate_descriptor_hash": substrate_descriptor["descriptor_hash"],
        "marked_prefix_count": len(marked_prefixes),
        "october_replay_progress": last_replay_progress,
        "v4_governing_prefix_receipt_hashes": governing_runtime_receipt_hashes,
        "global_freeze_receipt_hash": freeze.receipt_hash,
        "knowledge_global_freeze_receipt_hash": router_freeze.receipt_hash,
        "answer_revealed": False,
        "causal_second_chain": causal_chain_receipt,
        "control_causal_evidence_chain": control_causal_evidence_validation,
        "combined_causal_evidence_chain": combined_causal_evidence_validation,
        "causal_decision_state": {
            "snapshot_hash": last_decision_snapshot.snapshot_hash,
            "registry_receipt_hash": last_decision_snapshot.registry_receipt_hash,
            "path_count": last_decision_snapshot.path_count,
            "block_count": last_decision_snapshot.block_count,
            "registry_path_count": last_decision_snapshot.registry_path_count,
            "coverage_fraction": last_decision_snapshot.coverage_fraction,
            "control_evidence_path": str(control_causal_evidence.path),
            "combined_evidence_path": str(combined_causal_evidence.path),
        },
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
