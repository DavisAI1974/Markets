#!/usr/bin/env python3
"""Executable provider and durable-ledger adapter for one lawful Frankie prefix.

The adapter performs four role-separated evidence calls followed by one Frankie
synthesis call.  Network access remains behind an injectable Responses client; tests
use a fake.  The durable JSONL implementation exclusively creates its file, validates
the complete hash chain before every append/resume, and never overwrites or backfills.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Protocol, Sequence

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
    HelperEvidencePacket,
    HelperRole,
    LedgerKind,
    LedgerRecord,
    ProviderInvocationReceipt,
    ProviderRequestReceipt,
    RetrievalReceipt,
    RuntimeEvent,
    RuntimeEventSink,
    ToolCallReceipt,
    UncertaintyPacket,
    helper_contracts,
    validate_helper_batch,
)


LEDGER_SCHEMA = "FRANKIE_FULL_STACK_DURABLE_JSONL_V1"
HELPER_REQUEST_SCHEMA = "FRANKIE_HELPER_EVIDENCE_REQUEST_V1"
SYNTHESIS_REQUEST_SCHEMA = "FRANKIE_SYNTHESIS_REQUEST_V1"
_OPEN_FLAGS = os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
_KEY_RE = re.compile(r"AKIA[0-9A-Z]{12,}")
_OPENAI_RE = re.compile(r"sk-[A-Za-z0-9_-]{12,}")


class AdapterRuntimeError(ValueError):
    """Provider, schema, persistence, or resume validation failed closed."""


def _canonical(value: Any, field: str) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError) as exc:
        raise AdapterRuntimeError(f"{field} must be deterministic JSON") from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value, "hash payload").encode()).hexdigest()


def _redact_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    text = _KEY_RE.sub("[REDACTED_AWS_KEY]", text)
    text = _OPENAI_RE.sub("[REDACTED_OPENAI_KEY]", text)
    return text[:2000]


class ResponsesClient(Protocol):
    def create(self, *, model: str, instructions: str, input: str, store: bool) -> Any: ...


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

    def create(self, *, model: str, instructions: str, input: str, store: bool) -> Any:
        if model != EXPECTED_MODEL:
            raise AdapterRuntimeError(f"provider model must be exactly {EXPECTED_MODEL}")
        if store is not False:
            raise AdapterRuntimeError("provider requests must set store=False")
        return self._api_client.responses.create(
            model=model,
            instructions=instructions,
            input=input,
            store=False,
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
        return tuple(self._records)

    def append(
        self,
        *,
        kind: LedgerKind,
        binding: CausalPrefixBinding,
        content: Mapping[str, Any],
    ) -> LedgerRecord:
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

    def emit(self, event: RuntimeEvent) -> None:
        self.events.append(event)


_HELPER_INSTRUCTIONS = {
    HelperRole.RECURRENCE: (
        "You are the pair/triplet recurrence scout. Identify known or novel local modules using only "
        "the supplied lawful prefix. Emit evidence, contradiction, uncertainty, or abstention only."
    ),
    HelperRole.EXTENSION: (
        "You are the extension-propensity scout. Evaluate whether the lawful prefix is growing into a "
        "larger chain. Emit evidence only; never emit a probability path or primary lock."
    ),
    HelperRole.TIMING: (
        "You are the timing/lifespan-family scout. Track unresolved age and trajectory without target-relative "
        "or hard-coded clocks. Emit evidence only and abstain when the prefix is insufficient."
    ),
    HelperRole.CONTEXT: (
        "You are the true/false-context investigator. Recover ancestry, regimes, contradictions, stopped chains, "
        "and negative evidence. Preserve false contexts; never synthesize or lock."
    ),
}

_SYNTHESIS_INSTRUCTIONS = (
    "You are Frankie, the sole synthesizer and sole owner of the primary probability path and first lock. "
    "Use all four evidence packets on the identical causal prefix. Do not vote, average, use automatic "
    "consensus, or accept helper-owned locks. Return exactly the required JSON object."
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


@dataclass(frozen=True)
class PrefixRuntimeResult:
    binding: CausalPrefixBinding
    helper_packets: tuple[HelperEvidencePacket, ...]
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
    ) -> None:
        self.client = client
        self.ledger = ledger
        self.event_sink = event_sink

    def _event(self, name: str, binding: CausalPrefixBinding, details: Mapping[str, Any]) -> None:
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

    def _invoke(
        self,
        *,
        binding: CausalPrefixBinding,
        task: str,
        instructions: str,
        payload: Mapping[str, Any],
        tool_calls: Sequence[ToolCallReceipt],
        retrievals: Sequence[RetrievalReceipt],
    ) -> tuple[dict[str, Any], ProviderInvocationReceipt]:
        request = ProviderRequestReceipt.create(
            model=EXPECTED_MODEL,
            request_payload=payload,
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
            {"task": task, "model": EXPECTED_MODEL, "request_hash": request.request_hash},
        )
        try:
            raw = self.client.create(
                model=EXPECTED_MODEL,
                instructions=instructions,
                input=request.request_json,
                store=False,
            )
        except Exception as exc:
            raise AdapterRuntimeError(f"provider invocation failed: {_redact_error(exc)}") from exc
        provider_id = str(getattr(raw, "id", "") or "").strip()
        if not provider_id:
            raise AdapterRuntimeError("provider response ID must be non-empty")
        resolved_model = str(getattr(raw, "model", "") or "").strip()
        if resolved_model != EXPECTED_MODEL:
            raise AdapterRuntimeError(
                f"provider model drift: expected {EXPECTED_MODEL}, received {resolved_model or 'EMPTY'}"
            )
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
            tool_calls=tool_calls,
            retrievals=retrievals,
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
                "response_hash": accepted.response_hash,
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
        causal_state: Mapping[str, Any],
        tool_calls: Sequence[ToolCallReceipt],
        retrievals: Sequence[RetrievalReceipt],
    ) -> PrefixRuntimeResult:
        bound = binding.validate()
        if self.ledger.run_id != bound.run_id:
            raise AdapterRuntimeError("adapter ledger run_id differs from causal prefix")
        if not isinstance(causal_state, Mapping):
            raise AdapterRuntimeError("causal_state must be an object")
        tools = tuple(item.validate() for item in tool_calls)
        reads = tuple(item.validate() for item in retrievals)
        if not tools or not reads:
            raise AdapterRuntimeError("runtime prefix requires tool and retrieval receipts")
        try:
            self._event(
                "FRANKIE_REPLAY_PROGRESS",
                bound,
                {"phase": "PREFIX_READY", "state_prefix_hash": bound.state_prefix_hash},
            )
            self._persist(
                LedgerKind.STATE,
                bound,
                {"binding": bound.identity_payload(), "causal_state": dict(causal_state)},
            )
            self._persist(
                LedgerKind.RETRIEVAL,
                bound,
                {"retrievals": [asdict(item) for item in reads]},
            )

            packets: list[HelperEvidencePacket] = []
            invocations: list[ProviderInvocationReceipt] = []
            for role in HelperRole:
                contract = helper_contracts()[role]
                payload = {
                    "schema": HELPER_REQUEST_SCHEMA,
                    "request_type": "HELPER_EVIDENCE",
                    "role": role.value,
                    "role_title": contract.title,
                    "role_objective": contract.objective,
                    "binding": bound.identity_payload(),
                    "causal_state": dict(causal_state),
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
                    tool_calls=tools,
                    retrievals=reads,
                )
                packet = self._parse_helper(
                    role=role, binding=bound, output=output, invocation=invocation
                )
                packets.append(packet)
                invocations.append(invocation)
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
                            "owner": f"HELPER:{role.value}",
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
                tool_calls=tools,
                retrievals=reads,
            )
            synthesis = self._parse_synthesis(
                binding=bound, helper_packets=packets, output=synthesis_output
            )
            invocations.append(synthesis_invocation)
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
