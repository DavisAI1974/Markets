#!/usr/bin/env python3
"""Provider-callable causal state and append-only evidence receipts.

The tool backend is deliberately structural-compatible with ProviderToolBackend:
``definitions`` plus ``open_session()``, whose session exposes ``execute``.  It
keeps the complete decision-state snapshot pageable without turning a prompt
budget into an implicit field allowlist.  Historical reads validate the causal
JSONL hash chain and refuse records beyond the exact bound prefix.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
from threading import RLock
from typing import Any, Mapping, Sequence

from research.kalshi.frankie_causal_operational_context_20260824 import (
    DecisionStateSnapshot,
)
from research.kalshi.frankie_full_stack_runtime_contracts_20260824 import (
    CausalPrefixBinding,
    RetrievalReceipt,
    ToolCallReceipt,
)
from research.kalshi.frankie_provider_knowledge_tools_20260824 import (
    BoundedProviderToolSession,
    ProviderToolExecution,
    bounded_provider_tool_session,
)


TOOL_SCHEMA = "FRANKIE_CAUSAL_RUNTIME_TOOL_OUTPUT_V1_20260824"
EVIDENCE_SCHEMA = "FRANKIE_CAUSAL_EVIDENCE_JOURNAL_V1_20260824"
CAUSAL_SECOND_SCHEMA = "FRANKIE_CAUSAL_SECOND_CHAIN_V1_20260824"
GENESIS = "0" * 64
MAX_PAGE = 500
MAX_CALLS = 24
MAX_HISTORY_RECORD_SCAN = 4_096
MAX_RAW_EVENT_RECORD_SPAN = 120
MAX_RAW_EVENTS = 500
MAX_HISTORY_LINE_BYTES = 1_048_576
MAX_TOOL_RESULT_BYTES = 393_216
MAX_TOOL_OUTPUT_BYTES = 409_600


class CausalRuntimeToolError(ValueError):
    """A causal bound, receipt, provider-call, or evidence invariant failed."""


def _canonical(value: Any) -> str:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise CausalRuntimeToolError("value must be deterministic JSON") from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CausalRuntimeToolError(f"{field} must be non-empty")
    return value.strip()


def _integer(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise CausalRuntimeToolError(f"{field} must be an integer in [{minimum}, {maximum}]")
    return value


def _strict(arguments: Mapping[str, Any], keys: set[str], tool: str) -> dict[str, Any]:
    if not isinstance(arguments, Mapping) or set(arguments) != keys:
        raise CausalRuntimeToolError(f"{tool} arguments violate strict schema")
    return dict(arguments)


def _object(properties: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(properties),
        "additionalProperties": False,
    }


CAUSAL_TOOL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "type": "function",
        "name": "decision_state_manifest",
        "description": "Read identity, coverage, provenance, and missingness counts for the complete causal decision-state snapshot.",
        "parameters": _object({}),
        "strict": True,
    },
    {
        "type": "function",
        "name": "decision_state_list",
        "description": "List every decision-state path and status page by page, without an allowlist.",
        "parameters": _object(
            {
                "cursor": {"type": "integer", "minimum": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_PAGE},
            }
        ),
        "strict": True,
    },
    {
        "type": "function",
        "name": "decision_state_search",
        "description": "Search every complete decision-state path and family, retaining null and unavailable results.",
        "parameters": _object(
            {
                "query": {"type": "string", "minLength": 1, "maxLength": 256},
                "cursor": {"type": "integer", "minimum": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_PAGE},
            }
        ),
        "strict": True,
    },
    {
        "type": "function",
        "name": "decision_state_read",
        "description": "Page through every decision-state leaf, including explicit null and unavailable leaves; no field allowlist is applied.",
        "parameters": _object(
            {
                "cursor": {"type": "integer", "minimum": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_PAGE},
            }
        ),
        "strict": True,
    },
    {
        "type": "function",
        "name": "prior_causal_state",
        "description": "Read the full persisted causal state at an exact sequence not later than this prefix.",
        "parameters": _object({"sequence": {"type": "integer", "minimum": 0}}),
        "strict": True,
    },
    {
        "type": "function",
        "name": "prior_causal_delta",
        "description": "Read the full persisted causal delta at an exact sequence not later than this prefix.",
        "parameters": _object({"sequence": {"type": "integer", "minimum": 0}}),
        "strict": True,
    },
    {
        "type": "function",
        "name": "raw_event_range",
        "description": "Read raw event receipts from an inclusive causal sequence range, excluding all future-known events.",
        "parameters": _object(
            {
                "start_sequence": {"type": "integer", "minimum": 0},
                "end_sequence": {"type": "integer", "minimum": 0},
            }
        ),
        "strict": True,
    },
)


class CausalEvidenceJournal:
    """Exclusive-create, append-only, fsynced hash chain for access evidence."""

    def __init__(self, path: Path, run_id: str, fd: int) -> None:
        self.path = path
        self.run_id = _text(run_id, "run_id")
        self._fd: int | None = fd
        self._sequence = 0
        self._head = GENESIS
        self._lock = RLock()

    @classmethod
    def create(cls, path: str | Path, *, run_id: str) -> "CausalEvidenceJournal":
        target = Path(path)
        if not target.parent.is_dir():
            raise CausalRuntimeToolError("evidence journal parent does not exist")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND | os.O_CLOEXEC
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(target, flags, 0o600)
        except OSError as exc:
            raise CausalRuntimeToolError("evidence journal exclusive creation failed") from exc
        return cls(target, run_id, fd)

    def append(self, event_type: str, payload: Mapping[str, Any]) -> str:
        with self._lock:
            if self._fd is None:
                raise CausalRuntimeToolError("evidence journal is closed")
            if not isinstance(payload, Mapping):
                raise CausalRuntimeToolError("evidence payload must be an object")
            core = {
                "schema": EVIDENCE_SCHEMA,
                "run_id": self.run_id,
                "sequence": self._sequence,
                "event_type": _text(event_type, "event_type"),
                "payload": dict(payload),
                "prior_record_hash": self._head,
            }
            record_hash = _hash(core)
            raw = (_canonical({**core, "record_hash": record_hash}) + "\n").encode()
            offset = 0
            while offset < len(raw):
                try:
                    written = os.write(self._fd, raw[offset:])
                except InterruptedError:
                    continue
                if written <= 0:
                    raise CausalRuntimeToolError("evidence journal append made no progress")
                offset += written
            os.fsync(self._fd)
            self._sequence += 1
            self._head = record_hash
            return record_hash

    def record_answer_access(self, *, allowed: bool, reason: str) -> str:
        return self.append("ANSWER_ACCESS", {"allowed": bool(allowed), "reason": _text(reason, "reason")})

    @property
    def head_hash(self) -> str:
        """Return the current durable chain head for launch evidence."""
        with self._lock:
            return self._head

    @property
    def record_count(self) -> int:
        """Return the number of content-addressed records appended so far."""
        with self._lock:
            return self._sequence

    def close(self) -> None:
        with self._lock:
            if self._fd is not None:
                os.fsync(self._fd)
                os.close(self._fd)
                self._fd = None


def validate_causal_evidence_journal(path: str | Path, *, run_id: str) -> dict[str, Any]:
    """Recompute every evidence record and prior link before artifacts are accepted."""
    target = Path(path)
    expected_sequence = 0
    expected_prior = GENESIS
    try:
        handle = target.open("r", encoding="utf-8")
    except OSError as exc:
        raise CausalRuntimeToolError("evidence journal cannot be validated") from exc
    with handle:
        for line in handle:
            try:
                record = json.loads(line)
            except (TypeError, ValueError) as exc:
                raise CausalRuntimeToolError("evidence journal contains invalid JSON") from exc
            if not isinstance(record, Mapping):
                raise CausalRuntimeToolError("evidence journal record must be an object")
            if (
                record.get("schema") != EVIDENCE_SCHEMA
                or record.get("run_id") != run_id
                or record.get("sequence") != expected_sequence
                or record.get("prior_record_hash") != expected_prior
            ):
                raise CausalRuntimeToolError("evidence journal identity or chain mismatch")
            core = dict(record)
            record_hash = str(core.pop("record_hash", ""))
            if record_hash != _hash(core):
                raise CausalRuntimeToolError("evidence journal record hash mismatch")
            expected_sequence += 1
            expected_prior = record_hash
    return {"record_count": expected_sequence, "head_hash": expected_prior}


class CausalRuntimeToolBackend:
    """One immutable snapshot plus an optional, causally bounded history store."""

    def __init__(
        self,
        *,
        snapshot: DecisionStateSnapshot,
        binding: CausalPrefixBinding,
        causal_state_path: str | Path | None,
        evidence_journal: CausalEvidenceJournal | None,
        commit_sha: str,
    ) -> None:
        self.snapshot = snapshot.validate()
        self.binding = binding.validate()
        if self.snapshot.run_id != self.binding.run_id:
            raise CausalRuntimeToolError("snapshot/binding run identity mismatch")
        if self.snapshot.evaluated_at > self.binding.causal_cutoff:
            raise CausalRuntimeToolError("snapshot was evaluated after provider causal cutoff")
        self.causal_state_path = None if causal_state_path is None else Path(causal_state_path)
        self.evidence_journal = evidence_journal
        commit = _text(commit_sha, "commit_sha").lower()
        if len(commit) not in {40, 64} or any(ch not in "0123456789abcdef" for ch in commit):
            raise CausalRuntimeToolError("commit_sha must be a 40- or 64-character lowercase hex identity")
        self.commit_sha = commit
        if self.evidence_journal is not None:
            if self.evidence_journal.run_id != self.binding.run_id:
                raise CausalRuntimeToolError("evidence journal run identity mismatch")
            self.evidence_journal.append(
                "CODE_IDENTITY",
                {
                    "commit_sha": commit,
                    "snapshot_hash": self.snapshot.snapshot_hash,
                    "registry_receipt_hash": self.snapshot.registry_receipt_hash,
                },
            )

    @property
    def definitions(self) -> Sequence[Mapping[str, Any]]:
        if self.causal_state_path is None:
            return CAUSAL_TOOL_DEFINITIONS[:4]
        return CAUSAL_TOOL_DEFINITIONS

    def open_session(
        self,
        binding: CausalPrefixBinding | None = None,
        lane_id: str | None = None,
    ) -> BoundedProviderToolSession:
        """Open a lane-bound session; no-arg form preserves composite compatibility."""
        bound = (binding or self.binding).validate()
        if bound.run_id != self.snapshot.run_id or bound.causal_cutoff < self.snapshot.evaluated_at:
            raise CausalRuntimeToolError("session binding is incompatible with snapshot identity or cutoff")
        lane = _text(lane_id or "BOUND_BACKEND_DEFAULT", "lane_id")
        if self.evidence_journal is not None:
            self.evidence_journal.append(
                "SESSION_BINDING",
                {
                    "lane_id": lane,
                    "causal_cutoff": bound.causal_cutoff,
                    "causal_prefix_hash": bound.causal_prefix_hash,
                    "snapshot_hash": self.snapshot.snapshot_hash,
                },
            )
        return bounded_provider_tool_session(CausalRuntimeToolSession(self, bound, lane))


class CausalRuntimeToolSession:
    def __init__(
        self, backend: CausalRuntimeToolBackend, binding: CausalPrefixBinding, lane_id: str
    ) -> None:
        self._backend = backend
        self._binding = binding.validate()
        self._lane_id = lane_id
        self._call_ids: set[str] = set()

    @property
    def definitions(self) -> Sequence[Mapping[str, Any]]:
        return self._backend.definitions

    def execute(
        self, call_id: str, name: str, arguments: Mapping[str, Any]
    ) -> ProviderToolExecution:
        identity = _text(call_id, "call_id")
        tool_name = _text(name, "tool name")
        if identity in self._call_ids:
            raise CausalRuntimeToolError("duplicate provider tool call_id")
        if len(self._call_ids) >= MAX_CALLS:
            raise CausalRuntimeToolError("provider causal tool call budget exceeded")
        if tool_name not in {str(row["name"]) for row in self.definitions}:
            raise CausalRuntimeToolError(f"unknown causal tool: {tool_name}")
        self._call_ids.add(identity)
        request = {"call_id": identity, "tool_name": tool_name, "arguments": dict(arguments)}
        request_json = _canonical(request)
        request_hash = hashlib.sha256(request_json.encode()).hexdigest()
        retrievals: tuple[RetrievalReceipt, ...] = ()
        event_type = "TOOL_READ"
        try:
            result, retrievals, event_type = self._dispatch(identity, tool_name, arguments)
            if len(_canonical(result).encode("utf-8")) > MAX_TOOL_RESULT_BYTES:
                raise CausalRuntimeToolError("provider tool result exceeds serialized byte cap")
            status = "OK"
        except CausalRuntimeToolError as exc:
            status = "DENIED"
            event_type = "TOOL_DENY"
            result = {"reason": str(exc)[:500]}
        response_hash = _hash({"status": status, "result": result})
        wrapper = {
            "schema": TOOL_SCHEMA,
            "status": status,
            "tool_call_id": identity,
            "tool_name": tool_name,
            "request_sha256": request_hash,
            "response_sha256": response_hash,
            "reference_id": f"causal-tool:{identity}",
            "result": result,
        }
        output_json = _canonical(wrapper)
        if len(output_json.encode("utf-8")) > MAX_TOOL_OUTPUT_BYTES:
            # This should only be reachable if wrapper metadata, rather than the
            # already-bounded result, grows unexpectedly.
            raise CausalRuntimeToolError("provider tool wrapper exceeds serialized byte cap")
        output_hash = hashlib.sha256(output_json.encode()).hexdigest()
        receipt = ToolCallReceipt(identity, tool_name, request_hash, response_hash).validate()
        core = {
            "request_sha256": request_hash,
            "response_sha256": response_hash,
            "output_json_sha256": output_hash,
            "tool_receipt": asdict(receipt),
            "retrievals": [asdict(item) for item in retrievals],
            "router_receipt_hashes": [],
        }
        execution_hash = _hash(core)
        if self._backend.evidence_journal is not None:
            self._backend.evidence_journal.append(
                event_type,
                {
                    "call_id": identity,
                    "tool_name": tool_name,
                    "status": status,
                    "causal_cutoff": self._binding.causal_cutoff,
                    "lane_id": self._lane_id,
                    "request_sha256": request_hash,
                    "response_sha256": response_hash,
                    "execution_receipt_hash": execution_hash,
                    "retrieval_receipt_hashes": [_hash(asdict(item)) for item in retrievals],
                },
            )
        return ProviderToolExecution(
            call_id=identity,
            tool_name=tool_name,
            status=status,
            request_json=request_json,
            request_sha256=request_hash,
            result=result,
            response_sha256=response_hash,
            output_json=output_json,
            output_json_sha256=output_hash,
            tool_receipt=receipt,
            retrievals=retrievals,
            router_receipts=(),
            execution_receipt_hash=execution_hash,
        )

    def _dispatch(
        self, call_id: str, name: str, arguments: Mapping[str, Any]
    ) -> tuple[dict[str, Any], tuple[RetrievalReceipt, ...], str]:
        if name == "decision_state_manifest":
            _strict(arguments, set(), name)
            snapshot = self._backend.snapshot
            return (
                {
                    "snapshot_hash": snapshot.snapshot_hash,
                    "registry_receipt_hash": snapshot.registry_receipt_hash,
                    "path_count": snapshot.path_count,
                    "block_count": snapshot.block_count,
                    "registry_path_count": snapshot.registry_path_count,
                    "registry_block_count": snapshot.registry_block_count,
                    "additive_path_count": snapshot.additive_path_count,
                    "coverage_fraction": snapshot.coverage_fraction,
                    "schema_registered_count": snapshot.schema_registered_count,
                    "emitted_leaf_count": snapshot.emitted_leaf_count,
                    "emitted_registered_count": snapshot.emitted_registered_count,
                    "emitted_additive_count": snapshot.emitted_additive_count,
                    "present_count": snapshot.present_count,
                    "explicit_null_count": snapshot.explicit_null_count,
                    "unavailable_count": snapshot.unavailable_count,
                    "emitted_coverage_fraction": snapshot.emitted_coverage_fraction,
                    "value_coverage_fraction": snapshot.value_coverage_fraction,
                    "source_snapshot_leaf_count": snapshot.source_snapshot_leaf_count,
                    "source_snapshot_leaf_hash": snapshot.source_snapshot_leaf_hash,
                    "build_status": snapshot.build_status,
                    "build_error_hash": snapshot.build_error_hash,
                    "family_manifest": {key: dict(value) for key, value in snapshot.family_manifest.items()},
                },
                (),
                "TOOL_READ",
            )
        if name in {"decision_state_list", "decision_state_read"}:
            row = _strict(arguments, {"cursor", "limit"}, name)
            cursor = _integer(row["cursor"], "cursor", 0, self._backend.snapshot.path_count)
            limit = _integer(row["limit"], "limit", 1, MAX_PAGE)
            page = self._backend.snapshot.fields[cursor : cursor + limit]
            fields = [
                asdict(item) if name == "decision_state_read" else {
                    "path": item.path,
                    "block": item.block,
                    "status": item.status.value,
                    "field_hash": item.field_hash,
                }
                for item in page
            ]
            next_cursor = cursor + len(fields)
            if next_cursor >= self._backend.snapshot.path_count:
                next_cursor = None
            result = {
                "snapshot_hash": self._backend.snapshot.snapshot_hash,
                "cursor": cursor,
                "next_cursor": next_cursor,
                "total_fields": self._backend.snapshot.path_count,
                "fields": fields,
            }
            return result, self._retrieval(call_id, "decision-state-page", self._backend.snapshot.snapshot_hash, result), "TOOL_READ"
        if name == "decision_state_search":
            row = _strict(arguments, {"query", "cursor", "limit"}, name)
            query = _text(row["query"], "query").casefold()
            if len(query) > 256:
                raise CausalRuntimeToolError("query exceeds 256 characters")
            matches = [
                item for item in self._backend.snapshot.fields
                if query in item.path.casefold() or query in item.block.casefold()
            ]
            cursor = _integer(row["cursor"], "cursor", 0, len(matches))
            limit = _integer(row["limit"], "limit", 1, MAX_PAGE)
            page = matches[cursor : cursor + limit]
            next_cursor = cursor + len(page)
            if next_cursor >= len(matches):
                next_cursor = None
            result = {
                "snapshot_hash": self._backend.snapshot.snapshot_hash,
                "query": row["query"],
                "cursor": cursor,
                "next_cursor": next_cursor,
                "total_matches": len(matches),
                "fields": [asdict(item) for item in page],
            }
            return result, self._retrieval(call_id, "decision-state-search", self._backend.snapshot.snapshot_hash, result), "TOOL_READ"
        row = _strict(arguments, {"sequence"}, name) if name != "raw_event_range" else None
        if name in {"prior_causal_state", "prior_causal_delta"}:
            assert row is not None
            sequence = _integer(
                row["sequence"], "sequence", 0, MAX_HISTORY_RECORD_SCAN - 1
            )
            record = next(
                (item for item in self._iter_causal_records(stop_sequence=sequence)
                 if item["sequence"] == sequence),
                None,
            )
            if record is None:
                raise CausalRuntimeToolError("sequence is absent or later than the bound causal prefix")
            key = "state" if name.endswith("state") else "delta"
            result = {
                "sequence": sequence,
                "causal_cutoff": record["causal_cutoff"],
                "record_hash": record["record_hash"],
                key: record["content"][key],
            }
            return result, self._retrieval(call_id, f"causal-{key}", record["record_hash"], result), "TOOL_READ"
        if name != "raw_event_range":
            raise CausalRuntimeToolError(f"unsupported causal tool: {name}")
        span = _strict(arguments, {"start_sequence", "end_sequence"}, name)
        start = _integer(span["start_sequence"], "start_sequence", 0, 2**63 - 1)
        end = _integer(span["end_sequence"], "end_sequence", 0, 2**63 - 1)
        if end < start or end - start + 1 > MAX_RAW_EVENT_RECORD_SPAN:
            raise CausalRuntimeToolError("raw event sequence range is invalid or too large")
        events: list[Mapping[str, Any]] = []
        receipt_hashes: list[str] = []
        for record in self._iter_causal_records(stop_sequence=end):
            if not start <= record["sequence"] <= end:
                continue
            state = record["content"]["state"]
            candidates = state.get("raw_events", state.get("actions", [])) if isinstance(state, Mapping) else []
            if not isinstance(candidates, list):
                raise CausalRuntimeToolError("raw events in causal state are not a list")
            for event in candidates:
                if not isinstance(event, Mapping):
                    raise CausalRuntimeToolError("raw event is not an object")
                known_by = event.get("known_by")
                if known_by is not None:
                    try:
                        known = float(known_by)
                    except (TypeError, ValueError, OverflowError) as exc:
                        raise CausalRuntimeToolError("raw event known_by is invalid") from exc
                    if not math.isfinite(known) or known > self._binding.causal_cutoff:
                        raise CausalRuntimeToolError("raw event violates the causal availability bound")
                events.append(dict(event))
                if len(events) > MAX_RAW_EVENTS:
                    raise CausalRuntimeToolError("raw event result exceeds event cap")
            receipt_hashes.append(record["record_hash"])
        result = {
            "start_sequence": start,
            "end_sequence": end,
            "causal_cutoff": self._binding.causal_cutoff,
            "source_record_hashes": receipt_hashes,
            "events": events,
        }
        source_hash = _hash(receipt_hashes)
        return result, self._retrieval(call_id, "raw-event-range", source_hash, result), "RAW_EVENT_RANGE"

    @staticmethod
    def _retrieval(
        call_id: str, source_id: str, source_sha: str, result: Mapping[str, Any]
    ) -> tuple[RetrievalReceipt, ...]:
        raw = _canonical(result).encode()
        return (
            RetrievalReceipt(
                retrieval_id=f"{call_id}:0",
                source_id=source_id,
                source_sha256=source_sha,
                byte_start=0,
                byte_end=len(raw),
                content_sha256=hashlib.sha256(raw).hexdigest(),
            ).validate(),
        )

    def _iter_causal_records(self, *, stop_sequence: int):
        """Stream and validate only the causal prefix needed by this call."""
        path = self._backend.causal_state_path
        if path is None:
            raise CausalRuntimeToolError("causal history was not configured")
        expected_sequence = 0
        expected_prior = GENESIS
        last_cutoff: float | None = None
        try:
            handle = path.open("r", encoding="utf-8")
        except OSError as exc:
            raise CausalRuntimeToolError("causal history cannot be read") from exc
        with handle:
            for line in handle:
                if expected_sequence >= MAX_HISTORY_RECORD_SCAN:
                    raise CausalRuntimeToolError("causal history scan exceeds record cap")
                if len(line.encode("utf-8")) > MAX_HISTORY_LINE_BYTES:
                    raise CausalRuntimeToolError("causal history record exceeds byte cap")
                try:
                    record = json.loads(line)
                except (TypeError, ValueError) as exc:
                    raise CausalRuntimeToolError("causal history contains invalid JSON") from exc
                if not isinstance(record, dict) or record.get("schema") != CAUSAL_SECOND_SCHEMA:
                    raise CausalRuntimeToolError("causal history schema mismatch")
                if record.get("run_id") != self._binding.run_id or record.get("sequence") != expected_sequence:
                    raise CausalRuntimeToolError("causal history identity or sequence mismatch")
                if record.get("prior_record_hash") != expected_prior:
                    raise CausalRuntimeToolError("causal history prior hash mismatch")
                content = record.get("content")
                if not isinstance(content, Mapping) or set(content) != {"state", "delta", "integrity", "decision"}:
                    raise CausalRuntimeToolError("causal history content is incomplete")
                binding_payload = record.get("binding")
                if not isinstance(binding_payload, Mapping):
                    raise CausalRuntimeToolError("causal history binding is absent")
                try:
                    serialized_binding = CausalPrefixBinding(**binding_payload).validate()
                except (TypeError, ValueError, RuntimeError) as exc:
                    raise CausalRuntimeToolError("causal history binding is invalid") from exc
                if (
                    serialized_binding.run_id != self._binding.run_id
                    or serialized_binding.causal_cutoff != record.get("causal_cutoff")
                    or serialized_binding.knowledge_manifest_hash
                    != self._binding.knowledge_manifest_hash
                ):
                    raise CausalRuntimeToolError(
                        "causal history binding identity, cutoff, or knowledge manifest mismatch"
                    )
                content_hash = _hash(content)
                core = {
                    "schema": record["schema"],
                    "run_id": record["run_id"],
                    "sequence": record["sequence"],
                    "causal_cutoff": record["causal_cutoff"],
                    "binding": binding_payload,
                    "content_hash": content_hash,
                    "prior_record_hash": record["prior_record_hash"],
                }
                if record.get("content_hash") != content_hash or record.get("record_hash") != _hash(core):
                    raise CausalRuntimeToolError("causal history hash mismatch")
                cutoff = record.get("causal_cutoff")
                if isinstance(cutoff, bool):
                    raise CausalRuntimeToolError("causal history cutoff is invalid")
                try:
                    cutoff_float = float(cutoff)
                except (TypeError, ValueError, OverflowError) as exc:
                    raise CausalRuntimeToolError("causal history cutoff is invalid") from exc
                if not math.isfinite(cutoff_float) or (last_cutoff is not None and cutoff_float < last_cutoff):
                    raise CausalRuntimeToolError("causal history cutoff regressed")
                if cutoff_float <= self._binding.causal_cutoff:
                    yield record
                expected_sequence += 1
                expected_prior = record["record_hash"]
                last_cutoff = cutoff_float
                if record["sequence"] >= stop_sequence:
                    break


__all__ = [
    "CAUSAL_TOOL_DEFINITIONS",
    "CausalEvidenceJournal",
    "CausalRuntimeToolBackend",
    "CausalRuntimeToolError",
    "CausalRuntimeToolSession",
    "MAX_HISTORY_RECORD_SCAN",
    "MAX_RAW_EVENT_RECORD_SPAN",
    "MAX_RAW_EVENTS",
    "MAX_TOOL_RESULT_BYTES",
    "MAX_TOOL_OUTPUT_BYTES",
    "validate_causal_evidence_journal",
]
