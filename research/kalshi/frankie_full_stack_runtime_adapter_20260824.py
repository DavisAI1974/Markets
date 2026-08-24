#!/usr/bin/env python3
"""Executable provider and durable-ledger adapter for one lawful Frankie prefix.

The adapter performs four role-separated evidence calls followed by one Frankie
synthesis call.  Network access remains behind an injectable Responses client; tests
use a fake.  The durable JSONL implementation exclusively creates its file, validates
the complete hash chain before every append/resume, and never overwrites or backfills.
"""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, is_dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Mapping, Protocol, Sequence

from research.kalshi.frankie_provider_knowledge_tools_20260824 import (
    BoundedProviderToolSession,
    ProviderToolBackend,
    ProviderToolError,
    ProviderToolExecution,
    bounded_provider_tool_session,
)

from research.kalshi.frankie_full_stack_runtime_contracts_20260824 import (
    EXPECTED_MODEL,
    GENESIS,
    OCTOBER_END,
    OCTOBER_START,
    AbstentionPacket,
    AcceptedProviderResponseReceipt,
    CausalPrefixBinding,
    EvidenceCitation,
    FrankieSynthesisRecord,
    HELPER_CPU_MAPPING_VERSION,
    HelperEvidencePacket,
    HelperCpuAffinityTimingReceipt,
    HelperRole,
    KnowledgeSourceExcerpt,
    LedgerKind,
    LedgerRecord,
    ProviderInvocationReceipt,
    ProviderRequestReceipt,
    RetrievalReceipt,
    RuntimeEvent,
    RuntimeEventSink,
    RuntimeContractError,
    ToolCallReceipt,
    UncertaintyPacket,
    helper_contracts,
    helper_role_cpu_map,
    validate_helper_cpu_affinity_timing_receipts,
    validate_knowledge_excerpts,
    validate_helper_batch,
)


LEDGER_SCHEMA = "FRANKIE_FULL_STACK_DURABLE_JSONL_V1"
HELPER_REQUEST_SCHEMA = "FRANKIE_HELPER_EVIDENCE_REQUEST_V1"
SYNTHESIS_REQUEST_SCHEMA = "FRANKIE_SYNTHESIS_REQUEST_V1"
_OPEN_FLAGS = os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
_KEY_RE = re.compile(r"AKIA[0-9A-Z]{12,}")
_OPENAI_RE = re.compile(r"sk-[A-Za-z0-9_-]{12,}")
_RUNTIME_LANES = {"S135_CONTROL", "FULL_PROVISIONAL_COMBINED"}
_RESERVED_STATE_KEYS = {"experiment_lane", "provisional_combined_context"}
MAX_PROVIDER_FUNCTION_ARGUMENT_BYTES = 64 * 1024
MAX_PROVIDER_REPLAY_INPUT_BYTES = 8 * 1024 * 1024


class AdapterRuntimeError(ValueError):
    """Provider, schema, persistence, or resume validation failed closed."""


def _canonical(value: Any, field: str) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError) as exc:
        raise AdapterRuntimeError(f"{field} must be deterministic JSON") from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value, "hash payload").encode()).hexdigest()


def _receipt_payload(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    raise AdapterRuntimeError("provider authority receipt must be a dataclass or mapping")


def _replay_payload(value: Any) -> Any:
    """Convert SDK response Items to deterministic JSON solely for byte accounting."""
    if isinstance(value, Mapping):
        return {str(key): _replay_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_replay_payload(item) for item in value]
    if is_dataclass(value):
        return _replay_payload(asdict(value))
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _replay_payload(model_dump(mode="json"))
    if hasattr(value, "__dict__"):
        return _replay_payload(vars(value))
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise AdapterRuntimeError("provider response output item is not byte-accountable")


def _replay_input_bytes(items: Sequence[Any]) -> int:
    return len(_canonical(_replay_payload(items), "provider replay input").encode())


def _redact_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    text = _KEY_RE.sub("[REDACTED_AWS_KEY]", text)
    text = _OPENAI_RE.sub("[REDACTED_OPENAI_KEY]", text)
    return text[:2000]


class ResponsesClient(Protocol):
    def create(
        self,
        *,
        model: str,
        instructions: str,
        input: Any,
        store: bool,
        tools: Sequence[Mapping[str, Any]] | None = None,
        parallel_tool_calls: bool | None = None,
        previous_response_id: str | None = None,
    ) -> Any: ...


class OpenAIResponsesClient:
    """Production Responses API seam with optional injection for deterministic tests."""

    def __init__(self, *, api_client: Any | None = None) -> None:
        if api_client is None:
            try:
                import creds
                from openai import OpenAI

                api_client = OpenAI(api_key=creds.get("OPENAI_API_KEY"))
            except Exception as exc:
                raise AdapterRuntimeError(f"OpenAI client initialization failed: {_redact_error(exc)}") from exc
        if not hasattr(api_client, "responses") or not hasattr(api_client.responses, "create"):
            raise AdapterRuntimeError("OpenAI client must expose responses.create")
        self._api_client = api_client

    def create(
        self,
        *,
        model: str,
        instructions: str,
        input: Any,
        store: bool,
        tools: Sequence[Mapping[str, Any]] | None = None,
        parallel_tool_calls: bool | None = None,
        previous_response_id: str | None = None,
    ) -> Any:
        if model != EXPECTED_MODEL:
            raise AdapterRuntimeError(f"provider model must be exactly {EXPECTED_MODEL}")
        if store is not False:
            raise AdapterRuntimeError("provider requests must set store=False")
        kwargs: dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "input": input,
            "store": False,
        }
        if tools is not None:
            kwargs["tools"] = list(tools)
        if parallel_tool_calls is not None:
            kwargs["parallel_tool_calls"] = parallel_tool_calls
        if previous_response_id is not None:
            kwargs["previous_response_id"] = previous_response_id
        return self._api_client.responses.create(
            **kwargs,
        )


def _record_core(
    *,
    run_id: str,
    sequence: int,
    kind: LedgerKind,
    binding: CausalPrefixBinding,
    content_hash: str,
    prior_record_hash: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "sequence": sequence,
        "kind": kind.value,
        "causal_cutoff": binding.causal_cutoff,
        "binding": binding.identity_payload(),
        "content_hash": content_hash,
        "prior_record_hash": prior_record_hash,
    }


def _record_json(record: LedgerRecord) -> str:
    return _canonical(
        {
            "schema": LEDGER_SCHEMA,
            "run_id": record.run_id,
            "sequence": record.sequence,
            "kind": record.kind.value,
            "causal_cutoff": record.causal_cutoff,
            "binding": record.binding.identity_payload(),
            "content_json": record.content_json,
            "content_hash": record.content_hash,
            "prior_record_hash": record.prior_record_hash,
            "record_hash": record.record_hash,
        },
        "ledger record",
    )


_PERSISTED_KEYS = {
    "schema",
    "run_id",
    "sequence",
    "kind",
    "causal_cutoff",
    "binding",
    "content_json",
    "content_hash",
    "prior_record_hash",
    "record_hash",
}


def _decode_records(data: bytes, *, run_id: str) -> tuple[LedgerRecord, ...]:
    if data and not data.endswith(b"\n"):
        raise AdapterRuntimeError("durable ledger ends with a partial JSONL record")
    records: list[LedgerRecord] = []
    for line_number, raw in enumerate(data.splitlines(), start=1):
        try:
            row = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdapterRuntimeError(f"durable ledger line {line_number} is invalid JSON") from exc
        if not isinstance(row, dict) or set(row) != _PERSISTED_KEYS:
            raise AdapterRuntimeError(f"durable ledger line {line_number} has schema drift")
        if row["schema"] != LEDGER_SCHEMA or row["run_id"] != run_id:
            raise AdapterRuntimeError(f"durable ledger line {line_number} identity mismatch")
        if row["sequence"] != len(records):
            raise AdapterRuntimeError(f"durable ledger line {line_number} sequence mismatch")
        try:
            kind = LedgerKind(row["kind"])
            binding = CausalPrefixBinding(**row["binding"]).validate()
        except (TypeError, ValueError) as exc:
            raise AdapterRuntimeError(f"durable ledger line {line_number} contract mismatch") from exc
        if binding.run_id != run_id or binding.causal_cutoff != row["causal_cutoff"]:
            raise AdapterRuntimeError(f"durable ledger line {line_number} binding mismatch")
        if records and binding.causal_cutoff < records[-1].causal_cutoff:
            raise AdapterRuntimeError(f"durable ledger line {line_number} contains backfill")
        try:
            content = json.loads(row["content_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise AdapterRuntimeError(f"durable ledger line {line_number} content is invalid") from exc
        if _canonical(content, "ledger content") != row["content_json"]:
            raise AdapterRuntimeError(f"durable ledger line {line_number} content is not canonical")
        content_hash = hashlib.sha256(row["content_json"].encode()).hexdigest()
        if content_hash != row["content_hash"]:
            raise AdapterRuntimeError(f"durable ledger line {line_number} content hash mismatch")
        prior = records[-1].record_hash if records else GENESIS
        if row["prior_record_hash"] != prior:
            raise AdapterRuntimeError(f"durable ledger line {line_number} hash chain is broken")
        core = _record_core(
            run_id=run_id,
            sequence=len(records),
            kind=kind,
            binding=binding,
            content_hash=content_hash,
            prior_record_hash=prior,
        )
        if row["record_hash"] != _hash(core):
            raise AdapterRuntimeError(f"durable ledger line {line_number} record hash mismatch")
        records.append(
            LedgerRecord(
                run_id=run_id,
                sequence=len(records),
                kind=kind,
                causal_cutoff=binding.causal_cutoff,
                binding=binding,
                content_json=row["content_json"],
                content_hash=content_hash,
                prior_record_hash=prior,
                record_hash=row["record_hash"],
            )
        )
    return tuple(records)


def _read_fd(fd: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _fsync_parent(path: Path) -> None:
    flags = os.O_RDONLY | _OPEN_FLAGS | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(path.parent, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class DurableJsonlLedger:
    """Durable append-only implementation of the runtime ledger interface."""

    def __init__(self, *, path: Path, run_id: str, records: Sequence[LedgerRecord]) -> None:
        self.path = path
        self.run_id = run_id
        self._records = list(records)
        self._lock = threading.RLock()

    @classmethod
    def create(cls, path: str | Path, *, run_id: str) -> "DurableJsonlLedger":
        target = Path(path)
        if not run_id.strip():
            raise AdapterRuntimeError("durable ledger run_id must be non-empty")
        if not target.parent.is_dir():
            raise AdapterRuntimeError("durable ledger parent directory does not exist")
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _OPEN_FLAGS, 0o600)
        except FileExistsError as exc:
            raise AdapterRuntimeError(f"durable ledger already exists: {target}") from exc
        except OSError as exc:
            raise AdapterRuntimeError(f"durable ledger exclusive creation failed: {_redact_error(exc)}") from exc
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        _fsync_parent(target)
        return cls(path=target, run_id=run_id, records=())

    @classmethod
    def resume(cls, path: str | Path, *, run_id: str) -> "DurableJsonlLedger":
        target = Path(path)
        try:
            fd = os.open(target, os.O_RDONLY | _OPEN_FLAGS)
        except OSError as exc:
            raise AdapterRuntimeError(f"durable ledger resume open failed: {_redact_error(exc)}") from exc
        try:
            data = _read_fd(fd)
        finally:
            os.close(fd)
        return cls(path=target, run_id=run_id, records=_decode_records(data, run_id=run_id))

    def snapshot(self) -> tuple[LedgerRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def append(
        self,
        *,
        kind: LedgerKind,
        binding: CausalPrefixBinding,
        content: Mapping[str, Any],
    ) -> LedgerRecord:
        with self._lock:
            if not isinstance(kind, LedgerKind):
                raise AdapterRuntimeError("durable ledger kind is invalid")
            bound = binding.validate()
            if bound.run_id != self.run_id:
                raise AdapterRuntimeError("durable ledger binding run_id mismatch")
            if self._records and bound.causal_cutoff < self._records[-1].causal_cutoff:
                raise AdapterRuntimeError("durable ledger refuses causal backfill")
            if not isinstance(content, Mapping):
                raise AdapterRuntimeError("durable ledger content must be an object")
            try:
                fd = os.open(self.path, os.O_RDWR | os.O_APPEND | _OPEN_FLAGS)
            except OSError as exc:
                raise AdapterRuntimeError(f"durable ledger append open failed: {_redact_error(exc)}") from exc
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                disk_records = _decode_records(_read_fd(fd), run_id=self.run_id)
                if disk_records != tuple(self._records):
                    raise AdapterRuntimeError("durable ledger changed concurrently; refusing fork or overwrite")
                content_json = _canonical(dict(content), "ledger content")
                content_hash = hashlib.sha256(content_json.encode()).hexdigest()
                prior = disk_records[-1].record_hash if disk_records else GENESIS
                core = _record_core(
                    run_id=self.run_id,
                    sequence=len(disk_records),
                    kind=kind,
                    binding=bound,
                    content_hash=content_hash,
                    prior_record_hash=prior,
                )
                record = LedgerRecord(
                    run_id=self.run_id,
                    sequence=len(disk_records),
                    kind=kind,
                    causal_cutoff=bound.causal_cutoff,
                    binding=bound,
                    content_json=content_json,
                    content_hash=content_hash,
                    prior_record_hash=prior,
                    record_hash=_hash(core),
                )
                payload = (_record_json(record) + "\n").encode()
                offset = 0
                while offset < len(payload):
                    written = os.write(fd, payload[offset:])
                    if written <= 0:
                        raise AdapterRuntimeError("durable ledger append made no progress")
                    offset += written
                os.fsync(fd)
                self._records.append(record)
                return record
            finally:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)


class RecordingEventSink:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []
        self._lock = threading.RLock()

    def emit(self, event: RuntimeEvent) -> None:
        with self._lock:
            self.events.append(event)


_HELPER_INSTRUCTIONS = {
    HelperRole.RECURRENCE: (
        "You are the pair/triplet recurrence scout. Identify known or novel local modules using only "
        "the supplied lawful prefix. Before answering you must consult relevant causal state with "
        "decision_state_search or decision_state_read and inspect at least one returned PRESENT or "
        "EXPLICIT_NULL field; manifest/list access alone is insufficient. The bounded lane-scoped "
        "knowledge tools can retrieve complete lawful source content chunkwise. "
        "Cite a returned tool:<call_id> with its response_sha256. Emit evidence, contradiction, "
        "uncertainty, or abstention only."
    ),
    HelperRole.EXTENSION: (
        "You are the extension-propensity scout. Evaluate whether the lawful prefix is growing into a "
        "larger chain. Before answering you must consult relevant causal state with decision_state_search "
        "or decision_state_read and inspect at least one returned PRESENT or EXPLICIT_NULL field; "
        "manifest/list access alone is insufficient. Use bounded lane-scoped knowledge tools as needed and "
        "cite their content addresses. Emit evidence only; never emit a probability path or primary lock."
    ),
    HelperRole.TIMING: (
        "You are the timing/lifespan-family scout. Track unresolved age and trajectory without target-relative "
        "or hard-coded clocks. Before answering you must consult relevant causal state with "
        "decision_state_search or decision_state_read and inspect at least one returned PRESENT or "
        "EXPLICIT_NULL field; manifest/list access alone is insufficient. Consult complete lawful knowledge "
        "through the bounded tools; "
        "emit evidence only and abstain when the prefix is insufficient."
    ),
    HelperRole.CONTEXT: (
        "You are the true/false-context investigator. Recover ancestry, regimes, contradictions, stopped chains, "
        "and negative evidence. Before answering you must consult relevant causal state with "
        "decision_state_search or decision_state_read and inspect at least one returned PRESENT or "
        "EXPLICIT_NULL field; manifest/list access alone is insufficient. Search/read complete lawful lane "
        "sources as needed. Preserve "
        "false contexts; never synthesize or lock."
    ),
}

_SYNTHESIS_INSTRUCTIONS = (
    "You are Frankie, the sole synthesizer and sole owner of the primary probability path and first lock. "
    "Use all four evidence packets on the identical causal prefix. Do not vote, average, use automatic "
    "consensus, or accept helper-owned locks. You may independently use the same bounded lane-scoped "
    "knowledge and causal-state tools to verify evidence. Before answering you must independently consult "
    "relevant causal state with decision_state_search or decision_state_read and inspect at least one returned "
    "PRESENT or EXPLICIT_NULL field; manifest/list access alone is insufficient. Return exactly the required "
    "JSON object."
)

_HELPER_OUTPUT_SCHEMA = {
    "role": "exact helper role",
    "citations": [{"reference_id": "string", "content_sha256": "sha256", "observation": "string"}],
    "supporting_observations": ["string"],
    "contradictory_observations": ["string"],
    "uncertainty": {
        "level": "LOW | MEDIUM | HIGH | UNKNOWN",
        "drivers": ["string"],
        "calibrated_probability": "number in [0,1] or null",
    },
    "abstention": {"is_abstaining": "boolean", "reason": "string or null"},
}

_SYNTHESIS_OUTPUT_SCHEMA = {
    "reasoning": "string",
    "probabilities": ["numbers in [0,1] summing to one"],
    "candidate_ids": ["string"],
    "primary_lock_id": "string or null",
    "synthesis_method": "FRANKIE_SOLE_SYNTHESIS",
}

_PROVIDER_TOOL_ROUND_LIMIT = 12
_VALUE_STATE_TOOL_NAMES = frozenset({"decision_state_search", "decision_state_read"})
_VALUE_STATE_STATUSES = frozenset({"PRESENT", "EXPLICIT_NULL"})


def _is_value_bearing_state_execution(execution: ProviderToolExecution) -> bool:
    """Accept only successful state rows that expose a lawful value/null status."""
    if execution.status != "OK" or execution.tool_name not in _VALUE_STATE_TOOL_NAMES:
        return False
    if not isinstance(execution.result, Mapping):
        return False
    fields = execution.result.get("fields")
    return isinstance(fields, list) and any(
        isinstance(field, Mapping)
        and str(getattr(field.get("status"), "value", field.get("status")))
        in _VALUE_STATE_STATUSES
        for field in fields
    )


@dataclass(frozen=True)
class PrefixRuntimeResult:
    binding: CausalPrefixBinding
    helper_packets: tuple[HelperEvidencePacket, ...]
    helper_cpu_affinity_receipts: tuple[HelperCpuAffinityTimingReceipt, ...]
    synthesis: FrankieSynthesisRecord
    invocation_receipts: tuple[ProviderInvocationReceipt, ...]
    final_ledger_hash: str


def _strict_object(value: Any, expected_keys: set[str], field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise AdapterRuntimeError(f"{field} schema drift")
    return value


def _string_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise AdapterRuntimeError(f"{field} must be a list of non-empty strings")
    return tuple(value)


def _helper_payload(packet: HelperEvidencePacket) -> dict[str, Any]:
    return {
        "role": packet.role.value,
        "binding": packet.binding.identity_payload(),
        "provider_response_id": packet.invocation.accepted_response.provider_response_id,
        "provider_receipt_hash": packet.invocation.receipt_hash,
        "packet_hash": packet.packet_hash,
        "citations": [asdict(item) for item in packet.citations],
        "supporting_observations": list(packet.supporting_observations),
        "contradictory_observations": list(packet.contradictory_observations),
        "uncertainty": asdict(packet.uncertainty),
        "abstention": asdict(packet.abstention),
    }


class FullStackRuntimeAdapter:
    def __init__(
        self,
        *,
        client: ResponsesClient,
        ledger: DurableJsonlLedger,
        event_sink: RuntimeEventSink,
        provider_tools: ProviderToolBackend | None = None,
    ) -> None:
        self.client = client
        self.ledger = ledger
        self.event_sink = event_sink
        self.provider_tools = provider_tools
        self._event_lock = threading.RLock()

    def _event(self, name: str, binding: CausalPrefixBinding, details: Mapping[str, Any]) -> None:
        with self._event_lock:
            self.event_sink.emit(
                RuntimeEvent.create(
                    name=name,
                    run_id=binding.run_id,
                    correlation_id=binding.causal_prefix_hash,
                    causal_cutoff=binding.causal_cutoff,
                    details=details,
                )
            )

    def _persist(self, kind: LedgerKind, binding: CausalPrefixBinding, content: Mapping[str, Any]) -> LedgerRecord:
        record = self.ledger.append(kind=kind, binding=binding, content=content)
        self._event(
            "FRANKIE_PERSISTENCE_APPENDED",
            binding,
            {"kind": kind.value, "sequence": record.sequence, "record_hash": record.record_hash},
        )
        return record

    @staticmethod
    def _tool_definitions(backend: ProviderToolBackend) -> tuple[dict[str, Any], ...]:
        definitions = tuple(dict(item) for item in backend.definitions)
        if not definitions:
            raise AdapterRuntimeError("provider tool backend exposes no definitions")
        names: list[str] = []
        for definition in definitions:
            name = str(definition.get("name") or "").strip()
            parameters = definition.get("parameters")
            if (
                definition.get("type") != "function"
                or not name
                or definition.get("strict") is not True
                or not isinstance(parameters, dict)
                or parameters.get("type") != "object"
                or parameters.get("additionalProperties") is not False
                or set(parameters.get("required") or ()) != set(
                    (parameters.get("properties") or {}).keys()
                )
            ):
                raise AdapterRuntimeError("provider function tool must use a strict object schema")
            names.append(name)
        if len(set(names)) != len(names):
            raise AdapterRuntimeError("provider function tool names must be unique")
        return definitions

    @staticmethod
    def _response_identity(raw: Any) -> tuple[str, str]:
        provider_id = str(getattr(raw, "id", "") or "").strip()
        if not provider_id:
            raise AdapterRuntimeError("provider response ID must be non-empty")
        resolved_model = str(getattr(raw, "model", "") or "").strip()
        if resolved_model != EXPECTED_MODEL:
            raise AdapterRuntimeError(
                f"provider model drift: expected {EXPECTED_MODEL}, received {resolved_model or 'EMPTY'}"
            )
        return provider_id, resolved_model

    @staticmethod
    def _function_calls(raw: Any) -> tuple[tuple[str, str, dict[str, Any]], ...]:
        calls: list[tuple[str, str, dict[str, Any]]] = []
        output = getattr(raw, "output", ()) or ()
        for item in output:
            item_type = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)
            if item_type != "function_call":
                continue
            call_id = item.get("call_id") if isinstance(item, dict) else getattr(item, "call_id", None)
            name = item.get("name") if isinstance(item, dict) else getattr(item, "name", None)
            raw_arguments = (
                item.get("arguments") if isinstance(item, dict) else getattr(item, "arguments", None)
            )
            if not isinstance(call_id, str) or not call_id.strip():
                raise AdapterRuntimeError("provider function call_id must be non-empty")
            if not isinstance(name, str) or not name.strip():
                raise AdapterRuntimeError("provider function name must be non-empty")
            if not isinstance(raw_arguments, str):
                raise AdapterRuntimeError("provider function arguments must be JSON text")
            if len(raw_arguments.encode()) > MAX_PROVIDER_FUNCTION_ARGUMENT_BYTES:
                raise AdapterRuntimeError("provider function arguments exceed the byte budget")
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError as exc:
                raise AdapterRuntimeError("provider function arguments are invalid JSON") from exc
            if not isinstance(arguments, dict):
                raise AdapterRuntimeError("provider function arguments must decode to an object")
            calls.append((call_id.strip(), name.strip(), arguments))
        if len(calls) > 1:
            raise AdapterRuntimeError("parallel provider function calls are forbidden")
        return tuple(calls)

    def _persist_tool_execution(
        self,
        *,
        binding: CausalPrefixBinding,
        lane_id: str,
        task: str,
        provider_response_id: str,
        execution: ProviderToolExecution,
    ) -> None:
        self._persist(
            LedgerKind.RETRIEVAL,
            binding,
            {
                "record_type": "PROVIDER_TOOL_EXECUTION",
                "lane_id": lane_id,
                "task": task,
                "provider_response_id": provider_response_id,
                "tool_call_id": execution.call_id,
                "tool_name": execution.tool_name,
                "status": execution.status,
                "request_json": execution.request_json,
                "request_sha256": execution.request_sha256,
                "response_json": execution.output_json,
                "response_sha256": execution.response_sha256,
                "output_json_sha256": execution.output_json_sha256,
                "tool_receipt": asdict(execution.tool_receipt),
                "retrievals": [asdict(item) for item in execution.retrievals],
                "authority_receipts": [
                    _receipt_payload(item) for item in execution.router_receipts
                ],
                "execution_receipt_hash": execution.execution_receipt_hash,
            },
        )
        self._event(
            "FRANKIE_PROVIDER_TOOL_EXECUTED",
            binding,
            {
                "lane_id": lane_id,
                "task": task,
                "tool_call_id": execution.call_id,
                "tool_name": execution.tool_name,
                "status": execution.status,
                "request_sha256": execution.request_sha256,
                "response_sha256": execution.response_sha256,
                "execution_receipt_hash": execution.execution_receipt_hash,
            },
        )

    def _provider_with_tools(
        self,
        *,
        binding: CausalPrefixBinding,
        task: str,
        instructions: str,
        request_json: str,
        lane_id: str,
        definitions: Sequence[Mapping[str, Any]],
    ) -> tuple[
        Any,
        tuple[ToolCallReceipt, ...],
        tuple[RetrievalReceipt, ...],
        tuple[str, ...],
    ]:
        # Official Responses tool loop and sequential-call controls:
        # https://developers.openai.com/api/docs/guides/function-calling#handling-function-calls
        # https://developers.openai.com/api/docs/guides/function-calling#parallel-function-calling
        if self.provider_tools is None:
            raise AdapterRuntimeError("provider tool backend is missing")
        session: BoundedProviderToolSession = bounded_provider_tool_session(
            self.provider_tools.open_session(binding, lane_id)
        )
        if tuple(dict(item) for item in session.definitions) != tuple(
            dict(item) for item in definitions
        ):
            raise AdapterRuntimeError("provider tool session definition drift")
        conversation_input: list[Any] = [
            {"role": "user", "content": request_json}
        ]
        if _replay_input_bytes(conversation_input) > MAX_PROVIDER_REPLAY_INPUT_BYTES:
            raise AdapterRuntimeError("initial provider replay input exceeds the byte budget")
        raw = self.client.create(
            model=EXPECTED_MODEL,
            instructions=instructions,
            input=request_json,
            store=False,
            tools=definitions,
            parallel_tool_calls=False,
        )
        # `store=False` is a stateless Responses exchange.  The official loop
        # therefore replays the original input and every response output item
        # (including reasoning items) before appending function_call_output:
        # https://developers.openai.com/api/docs/guides/function-calling#handling-function-calls
        # https://developers.openai.com/api/docs/guides/migrate-to-responses#4-decide-when-to-use-statefulness
        tool_receipts: list[ToolCallReceipt] = []
        retrievals: list[RetrievalReceipt] = []
        value_state_read_receipt_hashes: list[str] = []
        requires_value_state_read = any(
            str(definition.get("name", "")) in _VALUE_STATE_TOOL_NAMES
            for definition in definitions
        )
        response_ids: set[str] = set()
        for _ in range(_PROVIDER_TOOL_ROUND_LIMIT + 1):
            provider_id, _ = self._response_identity(raw)
            if provider_id in response_ids:
                raise AdapterRuntimeError("provider tool loop reused a response ID")
            response_ids.add(provider_id)
            function_calls = self._function_calls(raw)
            if not function_calls:
                if requires_value_state_read and not value_state_read_receipt_hashes:
                    raise AdapterRuntimeError(
                        "provider invocation requires a value-bearing decision-state read"
                    )
                return (
                    raw,
                    tuple(tool_receipts),
                    tuple(retrievals),
                    tuple(value_state_read_receipt_hashes),
                )
            if len(tool_receipts) >= _PROVIDER_TOOL_ROUND_LIMIT:
                raise AdapterRuntimeError("provider tool call budget exceeded")
            call_id, name, arguments = function_calls[0]
            try:
                execution = session.execute(call_id, name, arguments)
            except ProviderToolError as exc:
                raise AdapterRuntimeError(f"provider tool execution failed: {exc}") from exc
            if execution.call_id != call_id or execution.tool_name != name:
                raise AdapterRuntimeError("provider tool execution identity drift")
            self._persist_tool_execution(
                binding=binding,
                lane_id=lane_id,
                task=task,
                provider_response_id=provider_id,
                execution=execution,
            )
            tool_receipts.append(execution.tool_receipt.validate())
            retrievals.extend(item.validate() for item in execution.retrievals)
            if _is_value_bearing_state_execution(execution):
                value_state_read_receipt_hashes.append(execution.execution_receipt_hash)
            output_items = getattr(raw, "output", None)
            if not isinstance(output_items, (list, tuple)):
                raise AdapterRuntimeError("provider response output is not replayable")
            function_output = {
                "type": "function_call_output",
                "call_id": call_id,
                "output": execution.output_json,
            }
            candidate_input = [*conversation_input, *output_items, function_output]
            if _replay_input_bytes(candidate_input) > MAX_PROVIDER_REPLAY_INPUT_BYTES:
                raise AdapterRuntimeError("provider replay input byte budget exceeded")
            conversation_input = candidate_input
            raw = self.client.create(
                model=EXPECTED_MODEL,
                instructions=instructions,
                input=list(conversation_input),
                store=False,
                tools=definitions,
                parallel_tool_calls=False,
            )
        raise AdapterRuntimeError("provider tool loop did not terminate")

    def _invoke(
        self,
        *,
        binding: CausalPrefixBinding,
        task: str,
        instructions: str,
        payload: Mapping[str, Any],
        request_context: Mapping[str, Any],
        knowledge_sources: Sequence[KnowledgeSourceExcerpt],
        tool_calls: Sequence[ToolCallReceipt],
        retrievals: Sequence[RetrievalReceipt],
    ) -> tuple[dict[str, Any], ProviderInvocationReceipt]:
        provider_payload = {
            **dict(payload),
            "model": EXPECTED_MODEL,
            "request_context": dict(request_context),
            "knowledge_source_excerpts": [asdict(item) for item in knowledge_sources],
            "tool_references": [asdict(item) for item in tool_calls],
            "retrieval_references": [asdict(item) for item in retrievals],
        }
        definitions: tuple[dict[str, Any], ...] = ()
        if self.provider_tools is not None:
            definitions = self._tool_definitions(self.provider_tools)
            provider_payload["provider_tool_surface"] = {
                "definitions": list(definitions),
                "definitions_sha256": _hash(list(definitions)),
                "parallel_tool_calls": False,
                "call_limit": _PROVIDER_TOOL_ROUND_LIMIT,
            }
        request = ProviderRequestReceipt.create(
            model=EXPECTED_MODEL,
            request_payload=provider_payload,
            instructions=instructions,
            binding=binding,
        )
        self._persist(
            LedgerKind.PROVIDER,
            binding,
            {
                "status": "REQUESTED",
                "task": task,
                "model": EXPECTED_MODEL,
                "request_hash": request.request_hash,
                "request_json": request.request_json,
            },
        )
        self._event(
            "FRANKIE_PROVIDER_CALL_STARTED",
            binding,
            {
                "task": task,
                "model": EXPECTED_MODEL,
                "lane_id": request_context["lane_id"],
                "base_state_content_hash": request_context["base_state_content_hash"],
                "full_state_content_hash": request_context["full_state_content_hash"],
                "knowledge_content_hash": request_context["knowledge_content_hash"],
                "request_hash": request.request_hash,
            },
        )
        try:
            dynamic_tools: tuple[ToolCallReceipt, ...] = ()
            dynamic_retrievals: tuple[RetrievalReceipt, ...] = ()
            value_state_read_receipt_hashes: tuple[str, ...] = ()
            if definitions:
                (
                    raw,
                    dynamic_tools,
                    dynamic_retrievals,
                    value_state_read_receipt_hashes,
                ) = self._provider_with_tools(
                    binding=binding,
                    task=task,
                    instructions=instructions,
                    request_json=request.request_json,
                    lane_id=str(request_context["lane_id"]),
                    definitions=definitions,
                )
            else:
                raw = self.client.create(
                    model=EXPECTED_MODEL,
                    instructions=instructions,
                    input=request.request_json,
                    store=False,
                )
        except Exception as exc:
            raise AdapterRuntimeError(f"provider invocation failed: {_redact_error(exc)}") from exc
        provider_id, resolved_model = self._response_identity(raw)
        output_text = getattr(raw, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise AdapterRuntimeError("provider accepted response text must be non-empty")
        try:
            output = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise AdapterRuntimeError("provider accepted response is not strict JSON") from exc
        if not isinstance(output, dict):
            raise AdapterRuntimeError("provider accepted response JSON must be an object")
        accepted = AcceptedProviderResponseReceipt.create(
            provider_response_id=provider_id,
            resolved_model=resolved_model,
            accepted_response=output,
            request_hash=request.request_hash,
        )
        invocation = ProviderInvocationReceipt.create(
            request=request,
            accepted_response=accepted,
            tool_calls=tuple(tool_calls) + dynamic_tools,
            retrievals=tuple(retrievals) + dynamic_retrievals,
            value_state_read_receipt_hashes=value_state_read_receipt_hashes,
        )
        self._persist(
            LedgerKind.PROVIDER,
            binding,
            {
                "status": "ACCEPTED",
                "task": task,
                "model": resolved_model,
                "provider_response_id": provider_id,
                "request_hash": request.request_hash,
                "response_hash": accepted.response_hash,
                "accepted_response_json": accepted.accepted_response_json,
                "tool_calls": [asdict(item) for item in invocation.tool_calls],
                "retrievals": [asdict(item) for item in invocation.retrievals],
                "value_state_read_count": len(invocation.value_state_read_receipt_hashes),
                "value_state_read_receipt_hashes": list(
                    invocation.value_state_read_receipt_hashes
                ),
                "receipt_hash": invocation.receipt_hash,
            },
        )
        self._event(
            "FRANKIE_PROVIDER_RESPONSE_ACCEPTED",
            binding,
            {
                "task": task,
                "model": resolved_model,
                "provider_response_id": provider_id,
                "lane_id": request_context["lane_id"],
                "response_hash": accepted.response_hash,
                "value_state_read_count": len(invocation.value_state_read_receipt_hashes),
                "value_state_read_receipt_hashes": list(
                    invocation.value_state_read_receipt_hashes
                ),
            },
        )
        return output, invocation

    @staticmethod
    def _parse_helper(
        *,
        role: HelperRole,
        binding: CausalPrefixBinding,
        output: Mapping[str, Any],
        invocation: ProviderInvocationReceipt,
    ) -> HelperEvidencePacket:
        row = _strict_object(
            dict(output),
            {
                "role",
                "citations",
                "supporting_observations",
                "contradictory_observations",
                "uncertainty",
                "abstention",
            },
            f"helper {role.value} response",
        )
        if row["role"] != role.value:
            raise AdapterRuntimeError(f"helper role drift: expected {role.value}")
        if not isinstance(row["citations"], list) or not row["citations"]:
            raise AdapterRuntimeError("helper citations must be a non-empty list")
        citations = []
        for raw in row["citations"]:
            item = _strict_object(raw, {"reference_id", "content_sha256", "observation"}, "citation")
            citations.append(EvidenceCitation(**item).validate())
        uncertainty = _strict_object(
            row["uncertainty"],
            {"level", "drivers", "calibrated_probability"},
            "helper uncertainty",
        )
        abstention = _strict_object(
            row["abstention"], {"is_abstaining", "reason"}, "helper abstention"
        )
        return HelperEvidencePacket.create(
            role=role,
            binding=binding,
            invocation=invocation,
            citations=tuple(citations),
            supporting_observations=_string_tuple(
                row["supporting_observations"], "supporting_observations"
            ),
            contradictory_observations=_string_tuple(
                row["contradictory_observations"], "contradictory_observations"
            ),
            uncertainty=UncertaintyPacket(
                level=uncertainty["level"],
                drivers=_string_tuple(uncertainty["drivers"], "uncertainty drivers"),
                calibrated_probability=uncertainty["calibrated_probability"],
            ),
            abstention=AbstentionPacket(
                is_abstaining=abstention["is_abstaining"], reason=abstention["reason"]
            ),
        )

    @staticmethod
    def _parse_synthesis(
        *,
        binding: CausalPrefixBinding,
        helper_packets: Sequence[HelperEvidencePacket],
        output: Mapping[str, Any],
    ) -> FrankieSynthesisRecord:
        row = _strict_object(
            dict(output),
            {"reasoning", "probabilities", "candidate_ids", "primary_lock_id", "synthesis_method"},
            "Frankie synthesis response",
        )
        if not isinstance(row["probabilities"], list):
            raise AdapterRuntimeError("Frankie probabilities must be a list")
        if not isinstance(row["candidate_ids"], list):
            raise AdapterRuntimeError("Frankie candidate_ids must be a list")
        return FrankieSynthesisRecord.create(
            binding=binding,
            helper_packets=helper_packets,
            reasoning=row["reasoning"],
            probabilities=row["probabilities"],
            candidate_ids=row["candidate_ids"],
            primary_lock_id=row["primary_lock_id"],
            synthesis_method=row["synthesis_method"],
        )

    def run_prefix(
        self,
        *,
        binding: CausalPrefixBinding,
        lane_id: str,
        causal_state: Mapping[str, Any],
        provisional_context: Mapping[str, Any] | None,
        knowledge_sources: Sequence[KnowledgeSourceExcerpt],
        tool_calls: Sequence[ToolCallReceipt],
        retrievals: Sequence[RetrievalReceipt],
    ) -> PrefixRuntimeResult:
        bound = binding.validate()
        if self.ledger.run_id != bound.run_id:
            raise AdapterRuntimeError("adapter ledger run_id differs from causal prefix")
        if not isinstance(causal_state, Mapping):
            raise AdapterRuntimeError("causal_state must be an object")
        lane = str(lane_id or "").strip()
        if lane not in _RUNTIME_LANES:
            raise AdapterRuntimeError("runtime lane identity is invalid")
        if any(key in causal_state for key in _RESERVED_STATE_KEYS):
            raise AdapterRuntimeError("base causal_state contains a reserved lane context key")
        if lane == "S135_CONTROL" and provisional_context is not None:
            raise AdapterRuntimeError("S135_CONTROL cannot receive provisional context")
        if lane == "FULL_PROVISIONAL_COMBINED" and (
            not isinstance(provisional_context, Mapping) or not provisional_context
        ):
            raise AdapterRuntimeError("FULL_PROVISIONAL_COMBINED requires provisional context")
        cpu_map = helper_role_cpu_map()
        if tuple(cpu_map.items()) != tuple(zip(HelperRole, (0, 1, 2, 3))):
            raise AdapterRuntimeError("helper CPU mapping differs from the fixed role order")
        try:
            available_cpus = frozenset(os.sched_getaffinity(0))
        except (AttributeError, OSError) as exc:
            raise AdapterRuntimeError("helper CPU affinity preflight is unavailable") from exc
        required_cpus = frozenset(cpu_map.values())
        if not required_cpus.issubset(available_cpus):
            raise AdapterRuntimeError(
                "helper CPU affinity preflight requires available CPUs 0, 1, 2, and 3"
            )
        tools = tuple(item.validate() for item in tool_calls)
        reads = tuple(item.validate() for item in retrievals)
        if not tools or not reads:
            raise AdapterRuntimeError("runtime prefix requires tool and retrieval receipts")
        try:
            sources = validate_knowledge_excerpts(knowledge_sources, reads)
        except RuntimeContractError as exc:
            raise AdapterRuntimeError(str(exc)) from exc
        base_state = json.loads(_canonical(dict(causal_state), "base causal_state"))
        full_state = dict(base_state)
        full_state["experiment_lane"] = lane
        if provisional_context is not None:
            full_state["provisional_combined_context"] = json.loads(
                _canonical(dict(provisional_context), "provisional context")
            )
        request_context = {
            "lane_id": lane,
            "causal_prefix_hash": bound.causal_prefix_hash,
            "state_prefix_hash": bound.state_prefix_hash,
            "knowledge_manifest_hash": bound.knowledge_manifest_hash,
            "base_state_content_hash": _hash(base_state),
            "full_state_content_hash": _hash(full_state),
            "knowledge_content_hash": _hash([asdict(item) for item in sources]),
        }
        try:
            self._event(
                "FRANKIE_REPLAY_PROGRESS",
                bound,
                {
                    "phase": "PREFIX_READY",
                    "lane_id": lane,
                    "state_prefix_hash": bound.state_prefix_hash,
                    "base_state_content_hash": request_context["base_state_content_hash"],
                    "full_state_content_hash": request_context["full_state_content_hash"],
                    "knowledge_content_hash": request_context["knowledge_content_hash"],
                },
            )
            self._persist(
                LedgerKind.STATE,
                bound,
                {
                    "binding": bound.identity_payload(),
                    "lane_id": lane,
                    "base_state_content_hash": request_context["base_state_content_hash"],
                    "full_state_content_hash": request_context["full_state_content_hash"],
                    "causal_state": full_state,
                },
            )
            self._persist(
                LedgerKind.RETRIEVAL,
                bound,
                {
                    "lane_id": lane,
                    "knowledge_content_hash": request_context["knowledge_content_hash"],
                    "knowledge_sources": [asdict(item) for item in sources],
                    "retrievals": [asdict(item) for item in reads],
                },
            )

            readiness = threading.Condition()
            ready_roles: set[HelperRole] = set()
            pin_failures: list[BaseException] = []
            start_provider_calls = threading.Event()

            def run_helper(
                role: HelperRole,
            ) -> tuple[
                HelperEvidencePacket,
                ProviderInvocationReceipt,
                HelperCpuAffinityTimingReceipt,
            ]:
                requested_cpu = cpu_map[role]
                native_thread_id = threading.get_native_id()
                original_affinity: frozenset[int] | None = None
                pinned = False
                try:
                    original_affinity = frozenset(os.sched_getaffinity(native_thread_id))
                    os.sched_setaffinity(native_thread_id, {requested_cpu})
                    observed_affinity = tuple(sorted(os.sched_getaffinity(native_thread_id)))
                    if observed_affinity != (requested_cpu,):
                        raise AdapterRuntimeError(
                            f"helper {role.value} did not observe singleton CPU {requested_cpu}"
                        )
                    pinned = True
                    with readiness:
                        ready_roles.add(role)
                        readiness.notify_all()
                    start_provider_calls.wait()
                    with readiness:
                        if pin_failures:
                            raise AdapterRuntimeError(
                                "helper provider batch aborted before provider calls"
                            )

                    started_monotonic_ns = time.monotonic_ns()
                    contract = helper_contracts()[role]
                    payload = {
                        "schema": HELPER_REQUEST_SCHEMA,
                        "request_type": "HELPER_EVIDENCE",
                        "role": role.value,
                        "role_title": contract.title,
                        "role_objective": contract.objective,
                        "binding": bound.identity_payload(),
                        "causal_state": full_state,
                        "required_output_schema": _HELPER_OUTPUT_SCHEMA,
                        "authority": {
                            "evidence_only": True,
                            "can_synthesize_probability": False,
                            "can_own_primary_lock": False,
                        },
                    }
                    output, invocation = self._invoke(
                        binding=bound,
                        task=f"helper:{role.value}",
                        instructions=_HELPER_INSTRUCTIONS[role],
                        payload=payload,
                        request_context=request_context,
                        knowledge_sources=sources,
                        tool_calls=tools,
                        retrievals=reads,
                    )
                    packet = self._parse_helper(
                        role=role, binding=bound, output=output, invocation=invocation
                    )
                    ended_monotonic_ns = time.monotonic_ns()
                    receipt = HelperCpuAffinityTimingReceipt.create(
                        role=role,
                        lane_id=lane,
                        binding=bound,
                        requested_cpu=requested_cpu,
                        observed_affinity=observed_affinity,
                        native_thread_id=native_thread_id,
                        mapping_version=HELPER_CPU_MAPPING_VERSION,
                        started_monotonic_ns=started_monotonic_ns,
                        ended_monotonic_ns=ended_monotonic_ns,
                        provider_receipt_hash=invocation.receipt_hash,
                        helper_packet_hash=packet.packet_hash,
                    )
                    return packet, invocation, receipt
                except BaseException as exc:
                    with readiness:
                        if role not in ready_roles:
                            pin_failures.append(exc)
                            readiness.notify_all()
                    raise
                finally:
                    if pinned and original_affinity is not None:
                        try:
                            os.sched_setaffinity(native_thread_id, original_affinity)
                        except OSError as exc:
                            raise AdapterRuntimeError(
                                f"helper {role.value} failed to restore native thread affinity"
                            ) from exc

            futures: dict[
                HelperRole,
                Future[
                    tuple[
                        HelperEvidencePacket,
                        ProviderInvocationReceipt,
                        HelperCpuAffinityTimingReceipt,
                    ]
                ],
            ] = {}
            with ThreadPoolExecutor(
                max_workers=len(HelperRole), thread_name_prefix=f"frankie-{lane.lower()}"
            ) as executor:
                for role in HelperRole:
                    futures[role] = executor.submit(run_helper, role)
                with readiness:
                    all_workers_ready = readiness.wait_for(
                        lambda: len(ready_roles) + len(pin_failures) == len(HelperRole),
                        timeout=30.0,
                    )
                    if not all_workers_ready:
                        pin_failures.append(
                            AdapterRuntimeError("helper CPU pinning readiness timed out")
                        )
                    start_provider_calls.set()
                if pin_failures:
                    for future in futures.values():
                        try:
                            future.result()
                        except BaseException:
                            pass
                    raise AdapterRuntimeError(
                        f"helper CPU pinning failed before provider calls: {_redact_error(pin_failures[0])}"
                    ) from pin_failures[0]
                ordered_results = tuple(futures[role].result() for role in HelperRole)

            packets = [item[0] for item in ordered_results]
            invocations = [item[1] for item in ordered_results]
            affinity_receipts = validate_helper_cpu_affinity_timing_receipts(
                [item[2] for item in ordered_results], binding=bound, lane_id=lane
            )
            for packet, receipt in zip(packets, affinity_receipts):
                self._persist(
                    LedgerKind.INTEGRITY,
                    bound,
                    {
                        "record_type": "HELPER_CPU_AFFINITY_TIMING",
                        "lane_id": lane,
                        "mapping_version": HELPER_CPU_MAPPING_VERSION,
                        "role_cpu_map": {
                            mapped_role.value: cpu for mapped_role, cpu in cpu_map.items()
                        },
                        "receipt": asdict(receipt),
                        "receipt_hash": receipt.receipt_hash,
                    },
                )
                self._persist(
                    LedgerKind.HELPER_EVIDENCE,
                    bound,
                    _helper_payload(packet),
                )
                if packet.abstention.is_abstaining:
                    self._persist(
                        LedgerKind.ABSTENTION,
                        bound,
                        {
                            "owner": f"HELPER:{packet.role.value}",
                            "packet_hash": packet.packet_hash,
                            "reason": packet.abstention.reason,
                        },
                    )

            validate_helper_batch(packets)
            synthesis_payload = {
                "schema": SYNTHESIS_REQUEST_SCHEMA,
                "request_type": "FRANKIE_SYNTHESIS",
                "binding": bound.identity_payload(),
                "helper_evidence_packets": [_helper_payload(packet) for packet in packets],
                "required_output_schema": _SYNTHESIS_OUTPUT_SCHEMA,
                "authority": {
                    "synthesis_owner": "FRANKIE",
                    "probability_owner": "FRANKIE",
                    "primary_lock_owner": "FRANKIE",
                    "voting": False,
                    "averaging": False,
                    "automatic_consensus": False,
                    "helper_locks": False,
                },
            }
            synthesis_output, synthesis_invocation = self._invoke(
                binding=bound,
                task="frankie:synthesis",
                instructions=_SYNTHESIS_INSTRUCTIONS,
                payload=synthesis_payload,
                request_context=request_context,
                knowledge_sources=sources,
                tool_calls=tools,
                retrievals=reads,
            )
            synthesis = self._parse_synthesis(
                binding=bound, helper_packets=packets, output=synthesis_output
            )
            invocations.append(synthesis_invocation)
            provider_ids = tuple(
                item.accepted_response.provider_response_id for item in invocations
            )
            if len(provider_ids) != 5 or len(set(provider_ids)) != 5:
                raise AdapterRuntimeError("runtime prefix requires five distinct provider response IDs")
            self._persist(
                LedgerKind.REASONING,
                bound,
                {
                    "owner": "FRANKIE",
                    "reasoning": synthesis.reasoning,
                    "record_hash": synthesis.record_hash,
                },
            )
            self._persist(
                LedgerKind.PROBABILITY,
                bound,
                {
                    "owner": "FRANKIE",
                    "probabilities": list(synthesis.probabilities),
                    "record_hash": synthesis.record_hash,
                },
            )
            self._persist(
                LedgerKind.CANDIDATE,
                bound,
                {"owner": "FRANKIE", "candidate_ids": list(synthesis.candidate_ids)},
            )
            lock_kind = LedgerKind.LOCK if synthesis.primary_lock_id else LedgerKind.NO_LOCK
            final = self._persist(
                lock_kind,
                bound,
                {
                    "owner": "FRANKIE",
                    "primary_lock_id": synthesis.primary_lock_id,
                    "synthesis_record_hash": synthesis.record_hash,
                },
            )
            self._event(
                "FRANKIE_OCTOBER_PROGRESS",
                bound,
                {
                    "phase": "PREFIX_COMPLETE",
                    "processed_prefixes": 1,
                    "target_start": OCTOBER_START,
                    "target_end": OCTOBER_END,
                    "final_record_hash": final.record_hash,
                },
            )
            return PrefixRuntimeResult(
                binding=bound,
                helper_packets=tuple(packets),
                helper_cpu_affinity_receipts=affinity_receipts,
                synthesis=synthesis,
                invocation_receipts=tuple(invocations),
                final_ledger_hash=final.record_hash,
            )
        except Exception as exc:
            self._event(
                "FRANKIE_RUNTIME_ERROR",
                bound,
                {
                    "phase": "PREFIX_FAILED",
                    "error_type": type(exc).__name__,
                    "error": _redact_error(exc),
                },
            )
            if isinstance(exc, AdapterRuntimeError):
                raise
            raise AdapterRuntimeError(f"runtime prefix failed: {_redact_error(exc)}") from exc
