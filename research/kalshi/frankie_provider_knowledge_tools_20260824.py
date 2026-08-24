#!/usr/bin/env python3
"""Bounded provider-callable access to the lawful Frankie knowledge plane.

The Responses API schemas follow the official function-calling contract:
https://developers.openai.com/api/docs/guides/function-calling#strict-mode

Every object schema is strict, all arguments are required, and each provider
invocation receives a fresh twelve-call session.  The executor never opens a
repository path itself; all bytes and complete plays pass through the existing
identity-bound lane router and authority plane.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Mapping, Protocol, Sequence

from research.kalshi.frankie_authority_knowledge_plane_20260824 import (
    KnowledgeAccessDenied,
)
from research.kalshi.frankie_full_stack_runtime_contracts_20260824 import (
    CausalPrefixBinding,
    RetrievalReceipt,
    ToolCallReceipt,
)
from research.kalshi.frankie_lane_aware_context_router_20260824 import (
    ContextVariant,
    FrankieLaneAwareContextRouter,
    RouteBundle,
)


TOOL_SESSION_CALL_LIMIT = 12
LIST_RESULT_LIMIT = 50
SEARCH_RESULT_LIMIT = 20
SEARCH_CURSOR_LIMIT = 480
READ_CHUNK_BYTES = 16 * 1024
MAX_QUERY_CHARS = 256
MAX_PLAY_ID_CHARS = 128
MAX_PLAY_JSON_BYTES = 256 * 1024
MAX_TOOL_RESULT_JSON_BYTES = 384 * 1024
MAX_TOOL_OUTPUT_JSON_BYTES = 400 * 1024
MAX_TOOL_SESSION_OUTPUT_BYTES = 2 * 1024 * 1024
_TOOL_BUDGET_DENIAL_RESERVE_BYTES = 4 * 1024
TOOL_OUTPUT_SCHEMA = "FRANKIE_PROVIDER_TOOL_OUTPUT_V1"


class ProviderToolError(ValueError):
    """A provider tool name, schema, bound, or execution contract failed closed."""


def _canonical(value: Any, field: str) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError) as exc:
        raise ProviderToolError(f"{field} must be deterministic JSON") from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value, "hash payload").encode()).hexdigest()


def _strict_args(value: Mapping[str, Any], keys: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ProviderToolError(f"{name} arguments violate the strict schema")
    return dict(value)


def _integer(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ProviderToolError(f"{field} must be an integer in [{minimum}, {maximum}]")
    return value


def _text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ProviderToolError(f"{field} must be non-empty and at most {maximum} characters")
    return value


def _object_schema(properties: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(properties),
        "additionalProperties": False,
    }


# Responses function tools are top-level {type,name,description,parameters,strict}.
# Source: https://developers.openai.com/api/docs/guides/function-calling#defining-functions
KNOWLEDGE_TOOL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "type": "function",
        "name": "list",
        "description": "List the currently lawful sources for this exact experiment lane, page by page.",
        "parameters": _object_schema(
            {
                "cursor": {"type": "integer", "minimum": 0, "maximum": 10000},
                "limit": {"type": "integer", "minimum": 1, "maximum": LIST_RESULT_LIMIT},
            }
        ),
        "strict": True,
    },
    {
        "type": "function",
        "name": "search",
        "description": "Case-insensitive search across every currently lawful lane source; results are bounded and paginated.",
        "parameters": _object_schema(
            {
                "query": {"type": "string", "minLength": 1, "maxLength": MAX_QUERY_CHARS},
                "cursor": {"type": "integer", "minimum": 0, "maximum": SEARCH_CURSOR_LIMIT},
                "limit": {"type": "integer", "minimum": 1, "maximum": SEARCH_RESULT_LIMIT},
            }
        ),
        "strict": True,
    },
    {
        "type": "function",
        "name": "read",
        "description": "Read a byte-addressed UTF-8 chunk from one lawful lane source; continue at next_byte_start for full content.",
        "parameters": _object_schema(
            {
                "path": {"type": "string", "minLength": 1, "maxLength": 1024},
                "byte_start": {"type": "integer", "minimum": 0},
                "byte_count": {"type": "integer", "minimum": 1, "maximum": READ_CHUNK_BYTES},
            }
        ),
        "strict": True,
    },
    {
        "type": "function",
        "name": "read_play",
        "description": "Read one complete lawful s105.9 brain play by exact play ID, including all fields.",
        "parameters": _object_schema(
            {"play_id": {"type": "string", "minLength": 1, "maxLength": MAX_PLAY_ID_CHARS}}
        ),
        "strict": True,
    },
)


@dataclass(frozen=True)
class ProviderToolExecution:
    call_id: str
    tool_name: str
    status: str
    request_json: str
    request_sha256: str
    result: Mapping[str, Any]
    response_sha256: str
    output_json: str
    output_json_sha256: str
    tool_receipt: ToolCallReceipt
    retrievals: tuple[RetrievalReceipt, ...]
    # Knowledge backends supply RouterReceipt values; causal-state backends may
    # supply their own deterministic receipt dataclasses through the same seam.
    router_receipts: tuple[Any, ...]
    execution_receipt_hash: str


class ProviderToolSession(Protocol):
    @property
    def definitions(self) -> Sequence[Mapping[str, Any]]: ...

    def execute(
        self, call_id: str, name: str, arguments: Mapping[str, Any]
    ) -> ProviderToolExecution: ...


class ProviderToolBackend(Protocol):
    @property
    def definitions(self) -> Sequence[Mapping[str, Any]]: ...

    def open_session(
        self,
        binding: CausalPrefixBinding | None = None,
        lane_id: str | None = None,
    ) -> ProviderToolSession: ...


def _budget_denial(
    execution: ProviderToolExecution,
    *,
    reason: str,
    rejected_output_bytes: int,
    rejected_output_sha256: str,
) -> ProviderToolExecution:
    """Replace an oversized child result with a small content-addressed denial."""
    result = {
        "reason": reason,
        "rejected_output_bytes": rejected_output_bytes,
        "rejected_output_sha256": rejected_output_sha256,
    }
    response_hash = _hash({"status": "DENIED", "result": result})
    wrapper = {
        "schema": TOOL_OUTPUT_SCHEMA,
        "status": "DENIED",
        "tool_call_id": execution.call_id,
        "tool_name": execution.tool_name,
        "request_sha256": execution.request_sha256,
        "response_sha256": response_hash,
        "reference_id": f"tool:{execution.call_id}",
        "result": result,
    }
    output_json = _canonical(wrapper, "bounded tool denial")
    output_hash = hashlib.sha256(output_json.encode()).hexdigest()
    receipt = ToolCallReceipt(
        execution.call_id,
        execution.tool_name,
        execution.request_sha256,
        response_hash,
    ).validate()
    retrievals = tuple(item.validate() for item in execution.retrievals)
    router_receipts = tuple(execution.router_receipts)
    router_receipt_hashes = []
    for item in router_receipts:
        receipt_hash = str(getattr(item, "receipt_hash", ""))
        if len(receipt_hash) != 64 or any(
            char not in "0123456789abcdef" for char in receipt_hash
        ):
            raise ProviderToolError("provider authority receipt hash is invalid")
        router_receipt_hashes.append(receipt_hash)
    core = {
        "request_sha256": execution.request_sha256,
        "response_sha256": response_hash,
        "output_json_sha256": output_hash,
        "tool_receipt": asdict(receipt),
        "retrievals": [asdict(item) for item in retrievals],
        "router_receipt_hashes": router_receipt_hashes,
    }
    return ProviderToolExecution(
        call_id=execution.call_id,
        tool_name=execution.tool_name,
        status="DENIED",
        request_json=execution.request_json,
        request_sha256=execution.request_sha256,
        result=result,
        response_sha256=response_hash,
        output_json=output_json,
        output_json_sha256=output_hash,
        tool_receipt=receipt,
        retrievals=retrievals,
        router_receipts=router_receipts,
        execution_receipt_hash=_hash(core),
    )


class BoundedProviderToolSession:
    """Enforce per-result and cumulative byte limits around any child backend."""

    def __init__(self, child: ProviderToolSession) -> None:
        self._child = child
        self._output_bytes = 0
        self._budget_exhausted = False

    @property
    def definitions(self) -> Sequence[Mapping[str, Any]]:
        return self._child.definitions

    def execute(
        self, call_id: str, name: str, arguments: Mapping[str, Any]
    ) -> ProviderToolExecution:
        if self._budget_exhausted:
            raise ProviderToolError("provider tool cumulative output budget exceeded")
        execution = self._child.execute(call_id, name, arguments)
        result_json = _canonical(dict(execution.result), "provider tool result")
        result_bytes = len(result_json.encode())
        output_bytes = len(execution.output_json.encode())
        rejected_reason: str | None = None
        if (
            result_bytes > MAX_TOOL_RESULT_JSON_BYTES
            or output_bytes > MAX_TOOL_OUTPUT_JSON_BYTES
        ):
            rejected_reason = "TOOL_RESULT_BYTE_BUDGET_EXCEEDED"
        elif (
            self._output_bytes + output_bytes
            > MAX_TOOL_SESSION_OUTPUT_BYTES - _TOOL_BUDGET_DENIAL_RESERVE_BYTES
        ):
            rejected_reason = "TOOL_SESSION_CUMULATIVE_BYTE_BUDGET_EXCEEDED"
            self._budget_exhausted = True
        if rejected_reason is not None:
            execution = _budget_denial(
                execution,
                reason=rejected_reason,
                rejected_output_bytes=output_bytes,
                rejected_output_sha256=hashlib.sha256(
                    execution.output_json.encode()
                ).hexdigest(),
            )
            output_bytes = len(execution.output_json.encode())
            if (
                self._output_bytes + output_bytes
                > MAX_TOOL_SESSION_OUTPUT_BYTES
            ):
                raise ProviderToolError("provider tool denial exceeds cumulative output budget")
        self._output_bytes += output_bytes
        return execution


def bounded_provider_tool_session(session: ProviderToolSession) -> BoundedProviderToolSession:
    if isinstance(session, BoundedProviderToolSession):
        return session
    return BoundedProviderToolSession(session)


class CompositeProviderToolBackend:
    """Merge independent knowledge/state backends behind one bounded tool surface."""

    def __init__(self, *backends: ProviderToolBackend) -> None:
        self._backends = tuple(backends)
        if not self._backends:
            raise ProviderToolError("composite provider tools require at least one backend")
        definitions = [dict(item) for backend in self._backends for item in backend.definitions]
        names = [str(item.get("name") or "") for item in definitions]
        if any(not name for name in names) or len(set(names)) != len(names):
            raise ProviderToolError("composite provider tool names must be non-empty and unique")
        self._definitions = tuple(definitions)

    @property
    def definitions(self) -> Sequence[Mapping[str, Any]]:
        return self._definitions

    def open_session(
        self,
        binding: CausalPrefixBinding | None = None,
        lane_id: str | None = None,
    ) -> BoundedProviderToolSession:
        return bounded_provider_tool_session(
            CompositeProviderToolSession(
                tuple(backend.open_session(binding, lane_id) for backend in self._backends)
            )
        )


class CompositeProviderToolSession:
    def __init__(self, sessions: tuple[ProviderToolSession, ...]) -> None:
        self._sessions = sessions
        self._call_ids: set[str] = set()
        definitions = [dict(item) for session in sessions for item in session.definitions]
        self._definitions = tuple(definitions)
        self._by_name = {
            str(definition["name"]): session
            for session in sessions
            for definition in session.definitions
        }

    @property
    def definitions(self) -> Sequence[Mapping[str, Any]]:
        return self._definitions

    def execute(
        self, call_id: str, name: str, arguments: Mapping[str, Any]
    ) -> ProviderToolExecution:
        identity = _text(call_id, "tool call_id", 256)
        if identity in self._call_ids:
            raise ProviderToolError("duplicate provider tool call_id")
        if len(self._call_ids) >= TOOL_SESSION_CALL_LIMIT:
            raise ProviderToolError("provider tool call budget exceeded")
        try:
            session = self._by_name[name]
        except KeyError as exc:
            raise ProviderToolError(f"unknown provider tool: {name}") from exc
        self._call_ids.add(identity)
        return session.execute(identity, name, arguments)


class LaneKnowledgeToolBackend:
    def __init__(
        self,
        *,
        router: FrankieLaneAwareContextRouter,
        bundle: RouteBundle,
        variant: ContextVariant,
    ) -> None:
        if not isinstance(variant, ContextVariant):
            raise ProviderToolError("knowledge tool variant is invalid")
        self.router = router
        self.bundle = bundle
        self.variant = variant

    @property
    def definitions(self) -> Sequence[Mapping[str, Any]]:
        return KNOWLEDGE_TOOL_DEFINITIONS

    @property
    def knowledge_manifest_hash(self) -> str:
        return self.bundle.knowledge_manifest_hash

    def open_session(
        self,
        binding: CausalPrefixBinding | None = None,
        lane_id: str | None = None,
    ) -> BoundedProviderToolSession:
        if binding is not None:
            bound = binding.validate()
            if (
                bound.run_id != self.bundle.run_id
                or bound.state_prefix_hash != self.bundle.state_prefix_hash
                or bound.knowledge_manifest_hash != self.bundle.knowledge_manifest_hash
            ):
                raise ProviderToolError("knowledge tool session binding differs from route bundle")
        if lane_id is not None and lane_id != self.variant.value:
            raise ProviderToolError("knowledge tool session lane differs from route variant")
        return bounded_provider_tool_session(LaneKnowledgeToolSession(self))


class LaneKnowledgeToolSession:
    def __init__(self, backend: LaneKnowledgeToolBackend) -> None:
        self._backend = backend
        self._call_ids: set[str] = set()

    @property
    def definitions(self) -> Sequence[Mapping[str, Any]]:
        return self._backend.definitions

    def execute(
        self, call_id: str, name: str, arguments: Mapping[str, Any]
    ) -> ProviderToolExecution:
        identity = _text(call_id, "tool call_id", 256)
        tool_name = _text(name, "tool name", 64)
        if identity in self._call_ids:
            raise ProviderToolError("duplicate provider tool call_id")
        if len(self._call_ids) >= TOOL_SESSION_CALL_LIMIT:
            raise ProviderToolError("provider tool call budget exceeded")
        if tool_name not in {row["name"] for row in KNOWLEDGE_TOOL_DEFINITIONS}:
            raise ProviderToolError(f"unknown provider tool: {tool_name}")
        self._call_ids.add(identity)
        request = {"call_id": identity, "tool_name": tool_name, "arguments": dict(arguments)}
        request_json = _canonical(request, "tool request")
        request_hash = hashlib.sha256(request_json.encode()).hexdigest()
        before = len(self._backend.router.receipts)
        retrievals: tuple[RetrievalReceipt, ...] = ()
        try:
            if tool_name == "list":
                result, retrievals = self._list(arguments)
            elif tool_name == "search":
                result, retrievals = self._search(identity, arguments)
            elif tool_name == "read":
                result, retrievals = self._read(identity, arguments)
            else:
                result, retrievals = self._read_play(arguments)
            status = "OK"
        except (KnowledgeAccessDenied, KeyError) as exc:
            status = "DENIED"
            result = {"reason": str(exc)[:500] or type(exc).__name__}
        router_receipts = self._backend.router.receipts[before:]
        result_payload = {"status": status, "result": result}
        response_hash = _hash(result_payload)
        wrapper = {
            "schema": TOOL_OUTPUT_SCHEMA,
            "status": status,
            "tool_call_id": identity,
            "tool_name": tool_name,
            "request_sha256": request_hash,
            "response_sha256": response_hash,
            "reference_id": f"tool:{identity}",
            "result": result,
        }
        output_json = _canonical(wrapper, "tool output")
        output_json_hash = hashlib.sha256(output_json.encode()).hexdigest()
        receipt = ToolCallReceipt(identity, tool_name, request_hash, response_hash).validate()
        core = {
            "request_sha256": request_hash,
            "response_sha256": response_hash,
            "output_json_sha256": output_json_hash,
            "tool_receipt": asdict(receipt),
            "retrievals": [asdict(item) for item in retrievals],
            "router_receipt_hashes": [item.receipt_hash for item in router_receipts],
        }
        return ProviderToolExecution(
            call_id=identity,
            tool_name=tool_name,
            status=status,
            request_json=request_json,
            request_sha256=request_hash,
            result=result,
            response_sha256=response_hash,
            output_json=output_json,
            output_json_sha256=output_json_hash,
            tool_receipt=receipt,
            retrievals=retrievals,
            router_receipts=router_receipts,
            execution_receipt_hash=_hash(core),
        )

    def _list(
        self, arguments: Mapping[str, Any]
    ) -> tuple[dict[str, Any], tuple[RetrievalReceipt, ...]]:
        row = _strict_args(arguments, {"cursor", "limit"}, "list")
        cursor = _integer(row["cursor"], "list cursor", 0, 10000)
        limit = _integer(row["limit"], "list limit", 1, LIST_RESULT_LIMIT)
        sources = self._backend.router.list_route_sources(
            self._backend.bundle, self._backend.variant
        )
        page = sources[cursor : cursor + limit]
        next_cursor = cursor + len(page) if cursor + len(page) < len(sources) else None
        return (
            {
                "knowledge_manifest_hash": self._backend.bundle.knowledge_manifest_hash,
                "route_hash": self._backend.bundle.routes[self._backend.variant].route_hash,
                "cursor": cursor,
                "next_cursor": next_cursor,
                "total_sources": len(sources),
                "sources": [
                    {
                        "source_id": source.source_id,
                        "path": source.path,
                        "source_sha256": source.sha256,
                        "byte_length": source.byte_length,
                        "authority": source.authority.value,
                        "component_label": source.component_label,
                    }
                    for source in page
                ],
            },
            (),
        )

    def _search(
        self, call_id: str, arguments: Mapping[str, Any]
    ) -> tuple[dict[str, Any], tuple[RetrievalReceipt, ...]]:
        row = _strict_args(arguments, {"query", "cursor", "limit"}, "search")
        query = _text(row["query"], "search query", MAX_QUERY_CHARS)
        cursor = _integer(row["cursor"], "search cursor", 0, SEARCH_CURSOR_LIMIT)
        limit = _integer(row["limit"], "search limit", 1, SEARCH_RESULT_LIMIT)
        needle = query.encode("utf-8")
        lowered = needle.lower()
        all_hits: list[dict[str, Any]] = []
        reads: list[RetrievalReceipt] = []
        sources = self._backend.router.list_route_sources(
            self._backend.bundle, self._backend.variant
        )
        wanted = cursor + limit + 1
        for source in sources:
            result = self._backend.router.read_source(
                self._backend.bundle, self._backend.variant, source.path
            )
            lower_data = result.data.lower()
            offset = 0
            while len(all_hits) < wanted:
                start = lower_data.find(lowered, offset)
                if start < 0:
                    break
                end = start + len(needle)
                match = result.data[start:end]
                content_hash = hashlib.sha256(match).hexdigest()
                retrieval_id = f"{call_id}:search:{len(all_hits)}"
                reads.append(
                    RetrievalReceipt(
                        retrieval_id,
                        source.source_id,
                        source.sha256,
                        start,
                        end,
                        content_hash,
                    ).validate()
                )
                context_start = max(0, start - 160)
                context_end = min(len(result.data), end + 160)
                context = result.data[context_start:context_end].decode("utf-8", errors="replace")
                all_hits.append(
                    {
                        "retrieval_id": retrieval_id,
                        "source_id": source.source_id,
                        "path": source.path,
                        "source_sha256": source.sha256,
                        "byte_start": start,
                        "byte_end": end,
                        "content_sha256": content_hash,
                        "match_utf8": match.decode("utf-8", errors="replace"),
                        "context_utf8": context,
                    }
                )
                offset = end
            if len(all_hits) >= wanted:
                break
        page = all_hits[cursor : cursor + limit]
        page_ids = {item["retrieval_id"] for item in page}
        page_reads = tuple(item for item in reads if item.retrieval_id in page_ids)
        next_cursor = cursor + len(page) if len(all_hits) > cursor + len(page) else None
        return (
            {
                "query": query,
                "cursor": cursor,
                "next_cursor": next_cursor,
                "hits": page,
                "result_limit": limit,
            },
            page_reads,
        )

    def _read(
        self, call_id: str, arguments: Mapping[str, Any]
    ) -> tuple[dict[str, Any], tuple[RetrievalReceipt, ...]]:
        row = _strict_args(arguments, {"path", "byte_start", "byte_count"}, "read")
        path = _text(row["path"], "read path", 1024)
        start = _integer(row["byte_start"], "read byte_start", 0, 2**63 - 1)
        count = _integer(row["byte_count"], "read byte_count", 1, READ_CHUNK_BYTES)
        route_sources = {
            source.path: source
            for source in self._backend.router.list_route_sources(
                self._backend.bundle, self._backend.variant
            )
        }
        # Unknown/sealed/archive paths still go to the router so it can emit the
        # authoritative denial receipt; only known lawful lengths are used here.
        source = route_sources.get(path)
        requested_end = start + count
        end = min(requested_end, source.byte_length) if source is not None else requested_end
        result = self._backend.router.read_source(
            self._backend.bundle,
            self._backend.variant,
            path,
            start=start,
            end_exclusive=end,
        )
        if start >= result.entry.byte_length:
            raise ProviderToolError("read byte_start must be smaller than source byte length")
        data = result.data
        while data:
            try:
                text = data.decode("utf-8")
                break
            except UnicodeDecodeError as exc:
                if exc.reason != "unexpected end of data" or exc.start <= 0:
                    raise ProviderToolError("read range does not begin at a UTF-8 boundary") from exc
                end = start + exc.start
                result = self._backend.router.read_source(
                    self._backend.bundle,
                    self._backend.variant,
                    path,
                    start=start,
                    end_exclusive=end,
                )
                data = result.data
        else:
            raise ProviderToolError("read returned an empty byte range")
        retrieval_id = f"{call_id}:read"
        retrieval = RetrievalReceipt(
            retrieval_id,
            result.entry.source_id,
            result.entry.sha256,
            start,
            end,
            hashlib.sha256(data).hexdigest(),
        ).validate()
        return (
            {
                "retrieval_id": retrieval_id,
                "source_id": result.entry.source_id,
                "path": result.entry.path,
                "source_sha256": result.entry.sha256,
                "byte_start": start,
                "byte_end": end,
                "byte_length": result.entry.byte_length,
                "content_sha256": retrieval.content_sha256,
                "content_utf8": text,
                "next_byte_start": end,
                "eof": end == result.entry.byte_length,
            },
            (retrieval,),
        )

    def _read_play(
        self, arguments: Mapping[str, Any]
    ) -> tuple[dict[str, Any], tuple[RetrievalReceipt, ...]]:
        row = _strict_args(arguments, {"play_id"}, "read_play")
        play_id = _text(row["play_id"], "play_id", MAX_PLAY_ID_CHARS)
        play = self._backend.router.read_play(
            self._backend.bundle, self._backend.variant, play_id
        )
        body_json = _canonical(play.body, "play body")
        if len(body_json.encode()) > MAX_PLAY_JSON_BYTES:
            raise ProviderToolError("complete play exceeds the bounded read_play output")
        return (
            {
                "play_id": play.play_id,
                "source_id": play.source_id,
                "content_sha256": play.content_sha256,
                "body": dict(play.body),
            },
            (),
        )


__all__ = [
    "BoundedProviderToolSession",
    "CompositeProviderToolBackend",
    "CompositeProviderToolSession",
    "KNOWLEDGE_TOOL_DEFINITIONS",
    "LaneKnowledgeToolBackend",
    "LaneKnowledgeToolSession",
    "ProviderToolBackend",
    "ProviderToolError",
    "ProviderToolExecution",
    "ProviderToolSession",
    "MAX_TOOL_OUTPUT_JSON_BYTES",
    "MAX_TOOL_RESULT_JSON_BYTES",
    "MAX_TOOL_SESSION_OUTPUT_BYTES",
    "bounded_provider_tool_session",
]
