from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from research.kalshi.frankie_full_stack_runtime_adapter_20260824 import (
    AdapterRuntimeError,
    DurableJsonlLedger,
    FullStackRuntimeAdapter,
    MAX_PROVIDER_REPLAY_INPUT_BYTES,
    OpenAIResponsesClient,
    RecordingEventSink,
)
from research.kalshi.frankie_provider_knowledge_tools_20260824 import (
    KNOWLEDGE_TOOL_DEFINITIONS,
    MAX_TOOL_RESULT_JSON_BYTES,
    ProviderToolExecution,
)
from research.kalshi.frankie_causal_operational_context_20260824 import (
    CausalDecisionStateSnapshotAdapter,
    RegistryCoverageOracle,
)
from research.kalshi.frankie_causal_runtime_tools_20260824 import (
    CausalEvidenceJournal,
    CausalRuntimeToolBackend,
    validate_causal_evidence_journal,
)
from research.kalshi.frankie_full_stack_runtime_contracts_20260824 import (
    EXPECTED_MODEL,
    CausalPrefixBinding,
    HelperRole,
    KnowledgeSourceExcerpt,
    LedgerKind,
    RetrievalReceipt,
    RuntimeContractError,
    ToolCallReceipt,
    validate_helper_cpu_affinity_timing_receipts,
)


H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
H4 = "4" * 64
DUMMY_PROVIDER_SECRET = "sk-" + "abcdefghijklmnopqrstuvwxyz"
KNOWLEDGE_TEXT = "lawful base knowledge excerpt"
KNOWLEDGE_SHA = hashlib.sha256(KNOWLEDGE_TEXT.encode()).hexdigest()


def binding(cutoff: float = 1633075201.0) -> CausalPrefixBinding:
    return CausalPrefixBinding(
        run_id="october-full-stack",
        causal_cutoff=cutoff,
        event_known_by=cutoff - 0.5,
        causal_prefix_hash=H1,
        state_prefix_hash=H2,
        knowledge_manifest_hash=H3,
    ).validate()


def tools_and_retrievals():
    return (
        ToolCallReceipt("tool-1", "read_state_prefix", H1, H2).validate(),
    ), (
        RetrievalReceipt(
            "ret-1", "phase2", H4, 0, len(KNOWLEDGE_TEXT.encode()), KNOWLEDGE_SHA
        ).validate(),
    )


def knowledge_sources():
    return (
        KnowledgeSourceExcerpt.create(
            source_id="phase2",
            source_sha256=H4,
            byte_start=0,
            excerpt=KNOWLEDGE_TEXT,
        ),
    )


class FakeResponsesAPI:
    def __init__(self, *, mode: str = "ok") -> None:
        self.mode = mode
        self.calls = []
        self.pending = {}
        self.last_tool_output = ()
        self._thread_state = threading.local()

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.mode == "raise_secret":
            raise RuntimeError(f"provider failed with {DUMMY_PROVIDER_SECRET}")

        tool_modes = {
            "tool_read",
            "tool_manifest",
            "tool_manifest_only",
            "tool_replay_oversize",
        }
        if self.mode in tool_modes and isinstance(kwargs["input"], str):
            if "previous_response_id" in kwargs:
                raise AssertionError("store=False tool loops must not use previous_response_id")
            payload = json.loads(kwargs["input"])
            response_id = f"tool-round-{len(self.calls)}"
            name = (
                "read"
                if self.mode in {"tool_read", "tool_replay_oversize"}
                else "decision_state_manifest"
            )
            arguments = (
                {"path": "phase2", "byte_start": 0, "byte_count": 16}
                if self.mode in {"tool_read", "tool_replay_oversize"}
                else {}
            )
            reasoning = SimpleNamespace(
                type="reasoning",
                id=f"reasoning-{len(self.calls)}",
                summary=[],
                encrypted_content=(
                    "x" * (MAX_PROVIDER_REPLAY_INPUT_BYTES + 1)
                    if self.mode == "tool_replay_oversize"
                    else f"encrypted-{len(self.calls)}"
                ),
            )
            function_call = SimpleNamespace(
                type="function_call",
                call_id=f"knowledge-call-{len(self.pending)}",
                name=name,
                arguments=json.dumps(arguments),
            )
            self.last_tool_output = (reasoning, function_call)
            self._thread_state.last_tool_output = self.last_tool_output
            return SimpleNamespace(
                id=response_id,
                model=EXPECTED_MODEL,
                output_text="",
                output=list(self.last_tool_output),
            )
        if self.mode in tool_modes:
            if "previous_response_id" in kwargs:
                raise AssertionError("store=False continuation supplied previous_response_id")
            replay = kwargs["input"]
            if not isinstance(replay, list):
                raise AssertionError("stateless continuation must replay an input list")
            last_tool_output = getattr(self._thread_state, "last_tool_output", ())
            if not all(any(item is expected for item in replay) for expected in last_tool_output):
                raise AssertionError("stateless continuation did not replay every raw output item")
            if not any(getattr(item, "type", None) == "reasoning" for item in replay):
                raise AssertionError("stateless continuation dropped provider reasoning output")
            calls = [item for item in replay if getattr(item, "type", None) == "function_call"]
            outputs = [
                item
                for item in replay
                if isinstance(item, dict) and item.get("type") == "function_call_output"
            ]
            if not calls or not outputs or calls[-1].call_id != outputs[-1]["call_id"]:
                raise AssertionError("stateless continuation did not replay the tool call and output")
            original = next(
                (
                    item
                    for item in replay
                    if isinstance(item, dict)
                    and item.get("role") == "user"
                    and isinstance(item.get("content"), str)
                ),
                None,
            )
            if original is None:
                raise AssertionError("stateless continuation dropped the original provider request")
            payload = json.loads(original["content"])
            call_names = [item.name for item in calls]
            if self.mode == "tool_manifest" and "decision_state_search" not in call_names:
                reasoning = SimpleNamespace(
                    type="reasoning",
                    id=f"reasoning-{len(self.calls)}",
                    summary=[],
                    encrypted_content=f"encrypted-{len(self.calls)}",
                )
                function_call = SimpleNamespace(
                    type="function_call",
                    call_id=f"state-value-call-{len(self.calls)}",
                    name="decision_state_search",
                    arguments=json.dumps(
                        {"query": "block_00.field_00", "cursor": 0, "limit": 50}
                    ),
                )
                self.last_tool_output = (reasoning, function_call)
                self._thread_state.last_tool_output = self.last_tool_output
                return SimpleNamespace(
                    id=f"tool-round-{len(self.calls)}",
                    model=EXPECTED_MODEL,
                    output_text="",
                    output=list(self.last_tool_output),
                )
        else:
            payload = json.loads(kwargs["input"])
        response_id = f"resp-{len(self.calls)}"
        model = EXPECTED_MODEL
        if self.mode == "wrong_model":
            model = "gpt-5.6"
        if self.mode == "blank_id":
            response_id = ""
        if self.mode == "duplicate_id":
            response_id = "resp-duplicate"

        if payload["request_type"] == "HELPER_EVIDENCE":
            role = payload["role"]
            output = {
                "role": role,
                "citations": [
                    {
                        "reference_id": (
                            "retrieval:fabricated"
                            if self.mode == "fabricated_reference"
                            else "retrieval:ret-1"
                        ),
                        "content_sha256": H2 if self.mode == "fabricated_hash" else KNOWLEDGE_SHA,
                        "observation": f"{role} lawful-prefix observation",
                    }
                ],
                "supporting_observations": [f"{role} support"],
                "contradictory_observations": [f"{role} contradiction"],
                "uncertainty": {
                    "level": "HIGH",
                    "drivers": ["bounded prefix"],
                    "calibrated_probability": None,
                },
                "abstention": {
                    "is_abstaining": True,
                    "reason": "insufficient causal evidence",
                },
            }
        else:
            output = {
                "reasoning": "Frankie weighs support and contradiction without helper voting.",
                "probabilities": [0.7, 0.3],
                "candidate_ids": ["candidate-1"],
                "primary_lock_id": "primary-lock-1",
                "synthesis_method": "FRANKIE_SOLE_SYNTHESIS",
            }
        if self.mode == "schema_drift":
            output["unexpected"] = "field"
        return SimpleNamespace(id=response_id, model=model, output_text=json.dumps(output))


class ThreadSafeFakeResponsesAPI(FakeResponsesAPI):
    def __init__(self, *, mode: str = "ok") -> None:
        super().__init__(mode=mode)
        self._serialize_lock = threading.Lock()

    def create(self, **kwargs):
        with self._serialize_lock:
            return super().create(**kwargs)


class FakeOpenAIClient:
    def __init__(self, *, mode: str = "ok") -> None:
        self.responses = ThreadSafeFakeResponsesAPI(mode=mode)


class DelayedConcurrentResponsesAPI(FakeResponsesAPI):
    def __init__(self, *, helper_delay: float = 0.2) -> None:
        super().__init__()
        self.helper_delay = helper_delay
        self._lock = threading.Lock()
        self._response_lock = threading.Lock()
        self.active_helpers = 0
        self.max_active_helpers = 0
        self.helper_threads = {}
        self.helper_affinities = {}
        self.helper_ended = {}
        self.synthesis_started = None

    def create(self, **kwargs):
        payload = json.loads(kwargs["input"])
        if payload["request_type"] != "HELPER_EVIDENCE":
            self.synthesis_started = time.monotonic_ns()
            with self._response_lock:
                return super().create(**kwargs)

        role = payload["role"]
        native_thread_id = threading.get_native_id()
        with self._lock:
            self.active_helpers += 1
            self.max_active_helpers = max(self.max_active_helpers, self.active_helpers)
            self.helper_threads[role] = native_thread_id
            self.helper_affinities[role] = set(os.sched_getaffinity(native_thread_id))
        try:
            time.sleep(self.helper_delay)
            with self._response_lock:
                return super().create(**kwargs)
        finally:
            ended = time.monotonic_ns()
            with self._lock:
                self.helper_ended[role] = ended
                self.active_helpers -= 1


class DelayedConcurrentOpenAIClient:
    def __init__(self, *, helper_delay: float = 0.2) -> None:
        self.responses = DelayedConcurrentResponsesAPI(helper_delay=helper_delay)


def run_adapter(tmp_path, *, mode: str = "ok"):
    raw_client = FakeOpenAIClient(mode=mode)
    provider = OpenAIResponsesClient(api_client=raw_client)
    ledger = DurableJsonlLedger.create(tmp_path / "runtime.jsonl", run_id="october-full-stack")
    events = RecordingEventSink()
    adapter = FullStackRuntimeAdapter(client=provider, ledger=ledger, event_sink=events)
    tool_calls, retrievals = tools_and_retrievals()
    result = adapter.run_prefix(
        binding=binding(),
        lane_id="S135_CONTROL",
        causal_state={"queue": {"bid_depth": 7, "ask_depth": 5}},
        provisional_context=None,
        knowledge_sources=knowledge_sources(),
        tool_calls=tool_calls,
        retrievals=retrievals,
    )
    return raw_client, ledger, events, result


class StubToolBackend:
    @property
    def definitions(self):
        return KNOWLEDGE_TOOL_DEFINITIONS

    def open_session(self, binding, lane_id):
        assert binding.run_id == "october-full-stack"
        assert lane_id == "S135_CONTROL"
        return StubToolSession()


class StubToolSession:
    @property
    def definitions(self):
        return KNOWLEDGE_TOOL_DEFINITIONS

    def execute(self, call_id, name, arguments):
        request_json = json.dumps(
            {"call_id": call_id, "tool_name": name, "arguments": arguments},
            sort_keys=True,
            separators=(",", ":"),
        )
        request_hash = hashlib.sha256(request_json.encode()).hexdigest()
        result = {"content_utf8": KNOWLEDGE_TEXT, "content_sha256": KNOWLEDGE_SHA}
        response_hash = hashlib.sha256(
            json.dumps(
                {"status": "OK", "result": result},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        output_json = json.dumps(
            {
                "schema": "FRANKIE_PROVIDER_TOOL_OUTPUT_V1",
                "status": "OK",
                "tool_call_id": call_id,
                "tool_name": name,
                "request_sha256": request_hash,
                "response_sha256": response_hash,
                "reference_id": f"tool:{call_id}",
                "result": result,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        receipt = ToolCallReceipt(call_id, name, request_hash, response_hash).validate()
        return ProviderToolExecution(
            call_id=call_id,
            tool_name=name,
            status="OK",
            request_json=request_json,
            request_sha256=request_hash,
            result=result,
            response_sha256=response_hash,
            output_json=output_json,
            output_json_sha256=hashlib.sha256(output_json.encode()).hexdigest(),
            tool_receipt=receipt,
            retrievals=(),
            router_receipts=(),
            execution_receipt_hash="9" * 64,
        )


class OversizedStubToolBackend(StubToolBackend):
    def open_session(self, binding, lane_id):
        assert binding.run_id == "october-full-stack"
        assert lane_id == "S135_CONTROL"
        return OversizedStubToolSession()


class OversizedStubToolSession(StubToolSession):
    def execute(self, call_id, name, arguments):
        execution = super().execute(call_id, name, arguments)
        result = {"payload": "x" * (MAX_TOOL_RESULT_JSON_BYTES + 1)}
        response_hash = hashlib.sha256(
            json.dumps(
                {"status": "OK", "result": result},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        output = {
            "schema": "SYNTHETIC_OVERSIZED",
            "status": "OK",
            "tool_call_id": call_id,
            "tool_name": name,
            "request_sha256": execution.request_sha256,
            "response_sha256": response_hash,
            "result": result,
        }
        output_json = json.dumps(output, sort_keys=True, separators=(",", ":"))
        receipt = ToolCallReceipt(
            call_id, name, execution.request_sha256, response_hash
        ).validate()
        return ProviderToolExecution(
            call_id=call_id,
            tool_name=name,
            status="OK",
            request_json=execution.request_json,
            request_sha256=execution.request_sha256,
            result=result,
            response_sha256=response_hash,
            output_json=output_json,
            output_json_sha256=hashlib.sha256(output_json.encode()).hexdigest(),
            tool_receipt=receipt,
            retrievals=(),
            router_receipts=(),
            execution_receipt_hash="8" * 64,
        )


def test_responses_tool_loop_is_strict_sequential_bounded_and_persisted(tmp_path):
    raw_client = FakeOpenAIClient(mode="tool_read")
    provider = OpenAIResponsesClient(api_client=raw_client)
    ledger = DurableJsonlLedger.create(tmp_path / "tool-runtime.jsonl", run_id="october-full-stack")
    adapter = FullStackRuntimeAdapter(
        client=provider,
        ledger=ledger,
        event_sink=RecordingEventSink(),
        provider_tools=StubToolBackend(),
    )
    tool_calls, retrievals = tools_and_retrievals()
    result = adapter.run_prefix(
        binding=binding(),
        lane_id="S135_CONTROL",
        causal_state={"queue": {"bid_depth": 7, "ask_depth": 5}},
        provisional_context=None,
        knowledge_sources=knowledge_sources(),
        tool_calls=tool_calls,
        retrievals=retrievals,
    )

    calls = raw_client.responses.calls
    assert len(calls) == 10
    initial = [call for call in calls if isinstance(call["input"], str)]
    continuations = [call for call in calls if isinstance(call["input"], list)]
    assert len(initial) == len(continuations) == 5
    assert all(call["tools"] == list(KNOWLEDGE_TOOL_DEFINITIONS) for call in calls)
    assert all(call["parallel_tool_calls"] is False for call in calls)
    assert all("previous_response_id" not in call for call in calls)
    assert all(
        any(getattr(item, "type", None) == "reasoning" for item in call["input"])
        for call in continuations
    )
    assert all(
        any(
            isinstance(item, dict) and item.get("type") == "function_call_output"
            for item in call["input"]
        )
        for call in continuations
    )
    assert all(len(item.tool_calls) == 2 for item in result.invocation_receipts)
    persisted = [
        json.loads(row.content_json)
        for row in ledger.snapshot()
        if row.kind is LedgerKind.RETRIEVAL
        and json.loads(row.content_json).get("record_type") == "PROVIDER_TOOL_EXECUTION"
    ]
    assert len(persisted) == 5
    assert all(len(row["request_sha256"]) == len(row["response_sha256"]) == 64 for row in persisted)


def test_adapter_persists_denial_without_replaying_oversized_child_content(tmp_path):
    raw_client = FakeOpenAIClient(mode="tool_read")
    ledger = DurableJsonlLedger.create(
        tmp_path / "oversized-tool-runtime.jsonl", run_id="october-full-stack"
    )
    tool_calls, retrievals = tools_and_retrievals()
    FullStackRuntimeAdapter(
        client=OpenAIResponsesClient(api_client=raw_client),
        ledger=ledger,
        event_sink=RecordingEventSink(),
        provider_tools=OversizedStubToolBackend(),
    ).run_prefix(
        binding=binding(),
        lane_id="S135_CONTROL",
        causal_state={"queue": {"bid_depth": 7}},
        provisional_context=None,
        knowledge_sources=knowledge_sources(),
        tool_calls=tool_calls,
        retrievals=retrievals,
    )
    persisted = [
        json.loads(row.content_json)
        for row in ledger.snapshot()
        if row.kind is LedgerKind.RETRIEVAL
        and json.loads(row.content_json).get("record_type") == "PROVIDER_TOOL_EXECUTION"
    ]
    assert len(persisted) == 5
    assert all(row["status"] == "DENIED" for row in persisted)
    assert all(
        json.loads(row["response_json"])["result"]["reason"]
        == "TOOL_RESULT_BYTE_BUDGET_EXCEEDED"
        for row in persisted
    )
    assert all("x" * 1024 not in row["response_json"] for row in persisted)
    continuations = raw_client.responses.calls[1::2]
    assert len(continuations) == 5
    assert all(
        "x" * 1024 not in item["output"]
        for call in continuations
        for item in call["input"]
        if isinstance(item, dict) and item.get("type") == "function_call_output"
    )


def test_adapter_caps_replayed_reasoning_before_a_continuation_is_sent(tmp_path):
    raw_client = FakeOpenAIClient(mode="tool_replay_oversize")
    ledger = DurableJsonlLedger.create(
        tmp_path / "oversized-replay-runtime.jsonl", run_id="october-full-stack"
    )
    tool_calls, retrievals = tools_and_retrievals()
    with pytest.raises(AdapterRuntimeError, match="replay input byte budget"):
        FullStackRuntimeAdapter(
            client=OpenAIResponsesClient(api_client=raw_client),
            ledger=ledger,
            event_sink=RecordingEventSink(),
            provider_tools=StubToolBackend(),
        ).run_prefix(
            binding=binding(),
            lane_id="S135_CONTROL",
            causal_state={"queue": {"bid_depth": 7}},
            provisional_context=None,
            knowledge_sources=knowledge_sources(),
            tool_calls=tool_calls,
            retrievals=retrievals,
        )
    # The retired adapter starts its fixed worker batch concurrently. Several initial
    # calls can therefore be in flight before one worker reports the oversized replay,
    # but no worker may send a continuation containing that replay.
    assert raw_client.responses.calls
    assert all(isinstance(call["input"], str) for call in raw_client.responses.calls)
    persisted = [
        json.loads(row.content_json)
        for row in ledger.snapshot()
        if row.kind is LedgerKind.RETRIEVAL
        and json.loads(row.content_json).get("record_type") == "PROVIDER_TOOL_EXECUTION"
    ]
    assert len(persisted) == len(raw_client.responses.calls)


def test_all_five_roles_in_both_lanes_can_call_identical_1940_by_46_causal_snapshot(tmp_path):
    paths = tuple(
        f"block_{block:02d}.field_{field:02d}"
        for block in range(44)
        for field in range(44)
    )
    oracle = RegistryCoverageOracle.create(
        paths=paths,
        source_ids=("fixture-registry",),
        source_hashes=("4" * 64,),
    )
    snapshot = CausalDecisionStateSnapshotAdapter(oracle).snapshot(
        run_id="october-full-stack",
        decision_day="20211001",
        evaluated_at=binding().causal_cutoff,
        canonical_state={
            "block_00": {"field_00": 1.0},
            "live_weather": {"temperature": 18.0, "staleness": 0.0},
            "live_storage": {"inventory": 3000.0, "revision": 1},
        },
        canonical_source_id="fixture-causal-state",
        canonical_source_sha256="5" * 64,
    )
    assert (snapshot.path_count, snapshot.block_count) == (1940, 46)
    tool_calls, retrievals = tools_and_retrievals()

    lane_results = {}
    for lane, provisional in (
        ("S135_CONTROL", None),
        ("FULL_PROVISIONAL_COMBINED", {"all_together": True}),
    ):
        lane_root = tmp_path / lane.lower()
        lane_root.mkdir()
        journal = CausalEvidenceJournal.create(
            lane_root / "causal-evidence.jsonl", run_id="october-full-stack"
        )
        backend = CausalRuntimeToolBackend(
            snapshot=snapshot,
            binding=binding(),
            causal_state_path=None,
            evidence_journal=journal,
            commit_sha="6" * 40,
        )
        raw = FakeOpenAIClient(mode="tool_manifest")
        ledger = DurableJsonlLedger.create(
            lane_root / "runtime.jsonl", run_id="october-full-stack"
        )
        result = FullStackRuntimeAdapter(
            client=OpenAIResponsesClient(api_client=raw),
            ledger=ledger,
            event_sink=RecordingEventSink(),
            provider_tools=backend,
        ).run_prefix(
            binding=binding(),
            lane_id=lane,
            causal_state={"queue": {"bid_depth": 7, "ask_depth": 5}},
            provisional_context=provisional,
            knowledge_sources=knowledge_sources(),
            tool_calls=tool_calls,
            retrievals=retrievals,
        )
        journal.close()
        persisted = [
            json.loads(row.content_json)
            for row in ledger.snapshot()
            if row.kind is LedgerKind.RETRIEVAL
            and json.loads(row.content_json).get("record_type") == "PROVIDER_TOOL_EXECUTION"
        ]
        assert len(persisted) == 10
        manifests = [
            json.loads(row["response_json"])["result"]
            for row in persisted
            if row["tool_name"] == "decision_state_manifest"
        ]
        assert {(item["path_count"], item["block_count"]) for item in manifests} == {(1940, 46)}
        value_reads = [row for row in persisted if row["tool_name"] == "decision_state_search"]
        assert len(value_reads) == 5
        assert all(
            any(call.tool_name == "decision_state_manifest" for call in invocation.tool_calls)
            for invocation in result.invocation_receipts
        )
        assert all(
            len(invocation.value_state_read_receipt_hashes) == 1
            for invocation in result.invocation_receipts
        )
        accepted_rows = [
            json.loads(row.content_json)
            for row in ledger.snapshot()
            if row.kind is LedgerKind.PROVIDER
            and json.loads(row.content_json).get("status") == "ACCEPTED"
        ]
        assert len(accepted_rows) == 5
        assert all(row["value_state_read_count"] == 1 for row in accepted_rows)
        assert all(
            len(row["value_state_read_receipt_hashes"]) == 1 for row in accepted_rows
        )
        assert all(
            "consult relevant causal state" in call["instructions"]
            and "manifest/list access alone is insufficient" in call["instructions"]
            for call in raw.responses.calls
        )
        evidence = [json.loads(line) for line in (lane_root / "causal-evidence.jsonl").read_text().splitlines()]
        assert sum(row["event_type"] == "TOOL_READ" for row in evidence) == 10
        assert any(
            row["event_type"] == "SESSION_BINDING"
            and row["payload"]["lane_id"] == lane
            for row in evidence
        )
        lane_results[lane] = (snapshot.snapshot_hash, result)

    assert lane_results["S135_CONTROL"][0] == lane_results["FULL_PROVISIONAL_COMBINED"][0]


def test_manifest_only_causal_tool_use_fails_before_provider_output_is_accepted(tmp_path):
    paths = tuple(
        f"block_{block:02d}.field_{field:02d}"
        for block in range(44)
        for field in range(44)
    )
    snapshot = CausalDecisionStateSnapshotAdapter(
        RegistryCoverageOracle.create(
            paths=paths,
            source_ids=("fixture-registry",),
            source_hashes=("4" * 64,),
        )
    ).snapshot(
        run_id="october-full-stack",
        decision_day="20211001",
        evaluated_at=binding().causal_cutoff,
        canonical_state={"live_state": {"value": 7}},
        canonical_source_id="fixture-causal-state",
        canonical_source_sha256="5" * 64,
    )
    journal = CausalEvidenceJournal.create(
        tmp_path / "manifest-only-evidence.jsonl", run_id="october-full-stack"
    )
    backend = CausalRuntimeToolBackend(
        snapshot=snapshot,
        binding=binding(),
        causal_state_path=None,
        evidence_journal=journal,
        commit_sha="6" * 40,
    )
    tool_calls, retrievals = tools_and_retrievals()
    adapter = FullStackRuntimeAdapter(
        client=OpenAIResponsesClient(api_client=FakeOpenAIClient(mode="tool_manifest_only")),
        ledger=DurableJsonlLedger.create(
            tmp_path / "manifest-only-runtime.jsonl", run_id="october-full-stack"
        ),
        event_sink=RecordingEventSink(),
        provider_tools=backend,
    )
    with pytest.raises(AdapterRuntimeError, match="value-bearing decision-state read"):
        adapter.run_prefix(
            binding=binding(),
            lane_id="S135_CONTROL",
            causal_state={"queue": {"bid_depth": 7}},
            provisional_context=None,
            knowledge_sources=knowledge_sources(),
            tool_calls=tool_calls,
            retrievals=retrievals,
        )
    journal.close()


def test_five_exact_sol_requests_keep_roles_separate_and_frankie_owns_lock(tmp_path):
    raw_client, ledger, events, result = run_adapter(tmp_path)

    calls = raw_client.responses.calls
    assert len(calls) == 5
    assert all(call["model"] == EXPECTED_MODEL and call["store"] is False for call in calls)
    response_ids = tuple(
        receipt.accepted_response.provider_response_id for receipt in result.invocation_receipts
    )
    assert set(response_ids[:4]) == {"resp-1", "resp-2", "resp-3", "resp-4"}
    assert response_ids[4] == "resp-5"

    helper_payloads = [json.loads(call["input"]) for call in calls[:4]]
    assert {payload["role"] for payload in helper_payloads} == {role.value for role in HelperRole}
    assert len({call["instructions"] for call in calls[:4]}) == 4
    assert all(payload["binding"] == binding().identity_payload() for payload in helper_payloads)
    assert all("probabilities" not in payload["required_output_schema"] for payload in helper_payloads)
    assert all(payload["model"] == EXPECTED_MODEL for payload in helper_payloads)
    assert all(payload["request_context"]["lane_id"] == "S135_CONTROL" for payload in helper_payloads)
    assert all(payload["request_context"]["causal_prefix_hash"] == H1 for payload in helper_payloads)
    assert all(payload["request_context"]["state_prefix_hash"] == H2 for payload in helper_payloads)
    assert all(payload["knowledge_source_excerpts"][0]["excerpt"] == KNOWLEDGE_TEXT for payload in helper_payloads)
    assert all(payload["tool_references"][0]["tool_call_id"] == "tool-1" for payload in helper_payloads)
    assert all(payload["retrieval_references"][0]["retrieval_id"] == "ret-1" for payload in helper_payloads)
    assert all(len(payload["request_context"][key]) == 64 for payload in helper_payloads for key in ("base_state_content_hash", "full_state_content_hash", "knowledge_content_hash"))

    synthesis_payload = json.loads(calls[4]["input"])
    assert synthesis_payload["request_type"] == "FRANKIE_SYNTHESIS"
    assert synthesis_payload["binding"] == binding().identity_payload()
    assert synthesis_payload["request_context"]["lane_id"] == "S135_CONTROL"
    assert synthesis_payload["knowledge_source_excerpts"][0]["content_sha256"] == KNOWLEDGE_SHA
    assert len(synthesis_payload["helper_evidence_packets"]) == 4
    assert result.synthesis.synthesis_owner == "FRANKIE"
    assert result.synthesis.probability_owner == "FRANKIE"
    assert result.synthesis.primary_lock_owner == "FRANKIE"
    assert result.synthesis.primary_lock_id == "primary-lock-1"

    assert len(ledger.snapshot()) >= 12
    assert sum(event.name == "FRANKIE_PROVIDER_RESPONSE_ACCEPTED" for event in events.events) == 5
    assert any(event.name == "FRANKIE_OCTOBER_PROGRESS" for event in events.events)
    started = [event for event in events.events if event.name == "FRANKIE_PROVIDER_CALL_STARTED"]
    assert len(started) == 5
    assert all(json.loads(event.details_json)["lane_id"] == "S135_CONTROL" for event in started)
    assert all(KNOWLEDGE_TEXT not in event.details_json for event in started)


def test_four_helpers_overlap_on_distinct_singleton_cpu_threads_before_frankie(tmp_path):
    helper_delay = 0.2
    baseline_started = time.perf_counter()
    for _ in HelperRole:
        time.sleep(helper_delay)
    sequential_baseline = time.perf_counter() - baseline_started
    raw_client = DelayedConcurrentOpenAIClient(helper_delay=helper_delay)
    ledger_path = tmp_path / "concurrent-runtime.jsonl"
    ledger = DurableJsonlLedger.create(ledger_path, run_id="october-full-stack")
    events = RecordingEventSink()
    adapter = FullStackRuntimeAdapter(
        client=OpenAIResponsesClient(api_client=raw_client),
        ledger=ledger,
        event_sink=events,
    )
    tool_calls, retrievals = tools_and_retrievals()

    started = time.perf_counter()
    result = adapter.run_prefix(
        binding=binding(),
        lane_id="S135_CONTROL",
        causal_state={"queue": {"bid_depth": 7, "ask_depth": 5}},
        provisional_context=None,
        knowledge_sources=knowledge_sources(),
        tool_calls=tool_calls,
        retrievals=retrievals,
    )
    elapsed = time.perf_counter() - started

    expected_map = {
        HelperRole.RECURRENCE.value: {0},
        HelperRole.EXTENSION.value: {1},
        HelperRole.TIMING.value: {2},
        HelperRole.CONTEXT.value: {3},
    }
    responses = raw_client.responses
    assert responses.max_active_helpers == 4
    assert len(set(responses.helper_threads.values())) == 4
    assert responses.helper_affinities == expected_map
    assert responses.synthesis_started >= max(responses.helper_ended.values())
    assert elapsed < sequential_baseline

    receipts = result.helper_cpu_affinity_receipts
    assert [receipt.role for receipt in receipts] == list(HelperRole)
    assert [receipt.requested_cpu for receipt in receipts] == [0, 1, 2, 3]
    assert [receipt.observed_affinity for receipt in receipts] == [(0,), (1,), (2,), (3,)]
    assert len({receipt.native_thread_id for receipt in receipts}) == 4
    assert all(receipt.validate() is receipt for receipt in receipts)
    helper_batch_seconds = (
        max(receipt.ended_monotonic_ns for receipt in receipts)
        - min(receipt.started_monotonic_ns for receipt in receipts)
    ) / 1_000_000_000
    assert helper_batch_seconds < sequential_baseline * 0.6
    with pytest.raises(RuntimeContractError, match="receipt hash mismatch"):
        replace(receipts[0], duration_ns=receipts[0].duration_ns + 1).validate()

    resumed = DurableJsonlLedger.resume(ledger_path, run_id="october-full-stack").snapshot()
    affinity_rows = [
        json.loads(record.content_json)
        for record in resumed
        if record.kind is LedgerKind.INTEGRITY
        and json.loads(record.content_json).get("record_type")
        == "HELPER_CPU_AFFINITY_TIMING"
    ]
    assert [row["receipt_hash"] for row in affinity_rows] == [
        receipt.receipt_hash for receipt in receipts
    ]

    tampered_receipts = (
        replace(receipts[0], requested_cpu=1),
        replace(receipts[0], observed_affinity=(1,)),
        replace(receipts[0], ended_monotonic_ns=receipts[0].started_monotonic_ns - 1),
        replace(receipts[0], receipt_hash="0" * 64),
    )
    for tampered in tampered_receipts:
        with pytest.raises(RuntimeContractError):
            tampered.validate()
    duplicate_thread_receipt = type(receipts[1]).create(
        role=receipts[1].role,
        lane_id=receipts[1].lane_id,
        binding=receipts[1].binding,
        requested_cpu=receipts[1].requested_cpu,
        observed_affinity=receipts[1].observed_affinity,
        native_thread_id=receipts[0].native_thread_id,
        mapping_version=receipts[1].mapping_version,
        started_monotonic_ns=receipts[1].started_monotonic_ns,
        ended_monotonic_ns=receipts[1].ended_monotonic_ns,
        provider_receipt_hash=receipts[1].provider_receipt_hash,
        helper_packet_hash=receipts[1].helper_packet_hash,
    )
    with pytest.raises(RuntimeContractError, match="four distinct native threads"):
        validate_helper_cpu_affinity_timing_receipts(
            (receipts[0], duplicate_thread_receipt, *receipts[2:])
        )

    journal_path = tmp_path / "concurrent-causal-evidence.jsonl"
    journal = CausalEvidenceJournal.create(journal_path, run_id="october-full-stack")
    with ThreadPoolExecutor(max_workers=4) as executor:
        journal_hashes = tuple(
            executor.map(
                lambda index: journal.append("CONCURRENT_TEST", {"worker": index}),
                range(4),
            )
        )
    journal.close()
    journal_validation = validate_causal_evidence_journal(
        journal_path, run_id="october-full-stack"
    )
    assert journal_validation["record_count"] == 4
    assert journal_validation["head_hash"] in journal_hashes

    missing_cpu_client = FakeOpenAIClient()
    missing_cpu_ledger = DurableJsonlLedger.create(
        tmp_path / "missing-cpu-runtime.jsonl", run_id="october-full-stack"
    )
    missing_cpu_adapter = FullStackRuntimeAdapter(
        client=OpenAIResponsesClient(api_client=missing_cpu_client),
        ledger=missing_cpu_ledger,
        event_sink=RecordingEventSink(),
    )
    with patch.object(os, "sched_getaffinity", return_value={0, 1, 2}):
        with pytest.raises(AdapterRuntimeError, match="available CPUs 0, 1, 2, and 3"):
            missing_cpu_adapter.run_prefix(
                binding=binding(),
                lane_id="S135_CONTROL",
                causal_state={"queue": {"bid_depth": 7}},
                provisional_context=None,
                knowledge_sources=knowledge_sources(),
                tool_calls=tool_calls,
                retrievals=retrievals,
            )
    assert missing_cpu_client.responses.calls == []
    assert missing_cpu_ledger.snapshot() == ()


def test_durable_jsonl_uses_exclusive_creation_validates_resume_and_rejects_backfill(tmp_path):
    path = tmp_path / "append-only.jsonl"
    ledger = DurableJsonlLedger.create(path, run_id="october-full-stack")
    first = ledger.append(
        kind=LedgerKind.STATE,
        binding=binding(10.0),
        content={"state": "first"},
    )
    with pytest.raises(AdapterRuntimeError, match="already exists"):
        DurableJsonlLedger.create(path, run_id="october-full-stack")

    resumed = DurableJsonlLedger.resume(path, run_id="october-full-stack")
    assert resumed.snapshot() == (first,)
    second = resumed.append(
        kind=LedgerKind.STATE_DELTA,
        binding=binding(11.0),
        content={"delta": "second"},
    )
    assert second.prior_record_hash == first.record_hash
    with pytest.raises(AdapterRuntimeError, match="backfill"):
        resumed.append(
            kind=LedgerKind.STATE,
            binding=binding(9.0),
            content={"state": "older"},
        )

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row["sequence"] for row in rows] == [0, 1]
    assert rows[1]["prior_record_hash"] == rows[0]["record_hash"]
    assert DurableJsonlLedger.resume(path, run_id="october-full-stack").snapshot() == (first, second)


@pytest.mark.parametrize("mode,match", [("wrong_model", "model drift"), ("blank_id", "response ID"), ("schema_drift", "schema")])
def test_provider_model_id_and_response_schema_drift_fail_closed(tmp_path, mode, match):
    with pytest.raises(AdapterRuntimeError, match=match):
        run_adapter(tmp_path, mode=mode)


@pytest.mark.parametrize(
    "mode,match",
    [
        ("fabricated_reference", "supplied tool or retrieval receipt"),
        ("fabricated_hash", "citation content hash"),
        ("duplicate_id", "five distinct provider response IDs"),
    ],
)
def test_fabricated_citations_and_duplicate_provider_ids_fail_closed(tmp_path, mode, match):
    with pytest.raises(AdapterRuntimeError, match=match):
        run_adapter(tmp_path, mode=mode)


def test_knowledge_excerpt_must_match_the_supplied_retrieval_receipt(tmp_path):
    raw_client = FakeOpenAIClient()
    ledger = DurableJsonlLedger.create(tmp_path / "knowledge-drift.jsonl", run_id="october-full-stack")
    adapter = FullStackRuntimeAdapter(
        client=OpenAIResponsesClient(api_client=raw_client),
        ledger=ledger,
        event_sink=RecordingEventSink(),
    )
    tool_calls, retrievals = tools_and_retrievals()
    drifted = KnowledgeSourceExcerpt.create(
        source_id="another-source",
        source_sha256=H4,
        byte_start=0,
        excerpt=KNOWLEDGE_TEXT,
    )
    with pytest.raises(AdapterRuntimeError, match="knowledge excerpts must exactly match"):
        adapter.run_prefix(
            binding=binding(),
            lane_id="S135_CONTROL",
            causal_state={"queue": "lawful"},
            provisional_context=None,
            knowledge_sources=(drifted,),
            tool_calls=tool_calls,
            retrievals=retrievals,
        )
    assert raw_client.responses.calls == []


def test_provider_errors_emit_redacted_structured_event(tmp_path):
    raw_client = FakeOpenAIClient(mode="raise_secret")
    provider = OpenAIResponsesClient(api_client=raw_client)
    ledger = DurableJsonlLedger.create(tmp_path / "errors.jsonl", run_id="october-full-stack")
    events = RecordingEventSink()
    adapter = FullStackRuntimeAdapter(client=provider, ledger=ledger, event_sink=events)
    tool_calls, retrievals = tools_and_retrievals()

    with pytest.raises(AdapterRuntimeError, match="provider invocation failed"):
        adapter.run_prefix(
            binding=binding(),
            lane_id="S135_CONTROL",
            causal_state={"queue": "lawful"},
            provisional_context=None,
            knowledge_sources=knowledge_sources(),
            tool_calls=tool_calls,
            retrievals=retrievals,
        )
    error = events.events[-1]
    assert error.name == "FRANKIE_RUNTIME_ERROR"
    assert DUMMY_PROVIDER_SECRET not in error.details_json
    assert "REDACTED_OPENAI_KEY" in error.details_json
