from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from research.kalshi.frankie_authority_knowledge_plane_20260824 import (
    AccessPolicy,
    AuthorityClass,
    CompletenessContract,
    KnowledgePlane,
    SourceSpec,
    TargetRelationship,
)
from research.kalshi.frankie_lane_aware_context_router_20260824 import (
    ComponentAvailability,
    ContextVariant,
    FrankieLaneAwareContextRouter,
    ProvisionalComponent,
)
from research.kalshi.frankie_provider_knowledge_tools_20260824 import (
    CompositeProviderToolBackend,
    KNOWLEDGE_TOOL_DEFINITIONS,
    LaneKnowledgeToolBackend,
    MAX_TOOL_OUTPUT_JSON_BYTES,
    MAX_TOOL_RESULT_JSON_BYTES,
    MAX_TOOL_SESSION_OUTPUT_BYTES,
    ProviderToolError,
    ProviderToolExecution,
)
from research.kalshi.frankie_causal_operational_context_20260824 import (
    CausalDecisionStateSnapshotAdapter,
    RegistryCoverageOracle,
)
from research.kalshi.frankie_causal_runtime_tools_20260824 import (
    CausalEvidenceJournal,
    CausalRuntimeToolBackend,
)
from research.kalshi.frankie_full_stack_runtime_contracts_20260824 import (
    CausalPrefixBinding,
    ToolCallReceipt,
)


def _write(root: Path, relative: str, content: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _backend(tmp_path: Path, variant: ContextVariant) -> tuple[LaneKnowledgeToolBackend, object]:
    brain = {
        "meta": {"version": "s105.9"},
        "plays": [
            {
                "id": "play-00",
                "call": "complete source fallback",
                "support": "supporting structure",
                "falsifier": "contradictory structure",
            }
        ],
    }
    _write(tmp_path, "knowledge/ng_brain.json", json.dumps(brain))
    _write(tmp_path, "s135/runtime.py", "S135_BINDING = 'full-access-marker'\n")
    _write(tmp_path, "frozen/findings.md", "frozen lawful recurrence evidence")
    _write(tmp_path, "carry/findings.md", "authorized carryforward evidence")
    _write(tmp_path, "shadow/s137.json", '{"provisional":"combined-only marker"}')
    _write(tmp_path, "shadow/meta_loop_s138.json", '{"sealed_later":"meta marker"}')
    _write(tmp_path, "archive/old.md", "archive secret marker")
    _write(tmp_path, "sealed/october_step1_results.json", '{"target":"sealed answer marker"}')
    specs = (
        SourceSpec("knowledge/ng_brain.json", AuthorityClass.CURRENT_BRAIN),
        SourceSpec("s135/runtime.py", AuthorityClass.BINDING_CURRENT),
        SourceSpec("frozen/findings.md", AuthorityClass.FROZEN_LEARNED_KNOWLEDGE),
        SourceSpec("carry/findings.md", AuthorityClass.EXTRA_AGENT_CARRYFORWARD),
        SourceSpec(
            "shadow/s137.json",
            AuthorityClass.PROVISIONAL_SHADOW,
            access_policy=AccessPolicy.SHADOW_ONLY,
        ),
        SourceSpec(
            "shadow/meta_loop_s138.json",
            AuthorityClass.PROVISIONAL_SHADOW,
            access_policy=AccessPolicy.SHADOW_ONLY,
        ),
        SourceSpec(
            "archive/old.md",
            AuthorityClass.ARCHIVE_NOT_SERVABLE,
            access_policy=AccessPolicy.DENY,
        ),
        SourceSpec(
            "sealed/october_step1_results.json",
            AuthorityClass.SEALED_TARGET_ANSWER,
            target_relationship=TargetRelationship.OCTOBER_STEP1_ANSWER,
            access_policy=AccessPolicy.SEALED_UNTIL_PRIMARY_FREEZE,
        ),
    )
    plane = KnowledgePlane.build(
        tmp_path,
        specs,
        contract=CompletenessContract(
            brain_path="knowledge/ng_brain.json",
            expected_play_count=1,
            s135_paths=frozenset({"s135/runtime.py"}),
            frozen_paths=frozenset({"frozen/findings.md"}),
            carryforward_paths=frozenset({"carry/findings.md"}),
        ),
        manifest_version="provider-tools-test-v1",
    )
    router = FrankieLaneAwareContextRouter(
        plane,
        (
            ProvisionalComponent(
                "shadow/s137.json",
                "S137_COGNITIVE",
                ComponentAvailability.PRE_FREEZE_AUGMENTATION,
            ),
            ProvisionalComponent(
                "shadow/meta_loop_s138.json",
                "META_LOOP",
                ComponentAvailability.POST_GLOBAL_FREEZE_ONLY,
            ),
        ),
    )
    bundle = router.build_routes(run_id="october-provider-tools", state_prefix_hash="a" * 64)
    return LaneKnowledgeToolBackend(router=router, bundle=bundle, variant=variant), plane


def test_function_definitions_are_strict_bounded_responses_api_schemas():
    assert [row["name"] for row in KNOWLEDGE_TOOL_DEFINITIONS] == [
        "list",
        "search",
        "read",
        "read_play",
    ]
    for tool in KNOWLEDGE_TOOL_DEFINITIONS:
        assert tool["type"] == "function"
        assert tool["strict"] is True
        schema = tool["parameters"]
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])


@pytest.mark.parametrize(
    "variant,visible,hidden",
    [
        (ContextVariant.S135_CONTROL, "s135/runtime.py", "shadow/s137.json"),
        (
            ContextVariant.FULL_PROVISIONAL_COMBINED,
            "shadow/s137.json",
            "shadow/meta_loop_s138.json",
        ),
    ],
)
def test_list_is_paginated_and_exactly_lane_scoped(tmp_path, variant, visible, hidden):
    backend, _ = _backend(tmp_path, variant)
    session = backend.open_session()
    first = session.execute("call-list-1", "list", {"cursor": 0, "limit": 2})
    second = session.execute(
        "call-list-2", "list", {"cursor": first.result["next_cursor"], "limit": 50}
    )
    paths = [row["path"] for row in first.result["sources"] + second.result["sources"]]

    assert visible in paths
    assert hidden not in paths
    assert "sealed/october_step1_results.json" not in paths
    assert "archive/old.md" not in paths
    assert first.tool_receipt.response_hash == first.response_sha256
    assert len(first.execution_receipt_hash) == 64


def test_read_chunks_reassemble_every_byte_and_search_returns_bounded_content_addresses(tmp_path):
    backend, plane = _backend(tmp_path, ContextVariant.S135_CONTROL)
    session = backend.open_session()
    raw = (tmp_path / "frozen/findings.md").read_bytes()
    chunks = []
    cursor = 0
    while cursor < len(raw):
        executed = session.execute(
            f"call-read-{cursor}",
            "read",
            {"path": "frozen/findings.md", "byte_start": cursor, "byte_count": 7},
        )
        chunks.append(executed.result["content_utf8"].encode())
        cursor = executed.result["next_byte_start"]
        assert executed.retrievals[0].content_sha256 == executed.result["content_sha256"]
    assert b"".join(chunks) == raw
    assert cursor == len(raw)

    found = session.execute(
        "call-search", "search", {"query": "recurrence", "cursor": 0, "limit": 3}
    )
    assert found.result["hits"][0]["path"] == "frozen/findings.md"
    assert found.result["hits"][0]["content_sha256"] == hashlib.sha256(b"recurrence").hexdigest()
    assert len(found.result["hits"]) <= 3
    assert found.retrievals
    assert plane.manifest_hash == backend.knowledge_manifest_hash


def test_read_play_returns_complete_lawful_body_and_denials_never_leak_bytes(tmp_path):
    backend, _ = _backend(tmp_path, ContextVariant.S135_CONTROL)
    session = backend.open_session()
    play = session.execute("call-play", "read_play", {"play_id": "play-00"})
    assert play.result["body"] == {
        "id": "play-00",
        "call": "complete source fallback",
        "support": "supporting structure",
        "falsifier": "contradictory structure",
    }
    assert len(play.result["content_sha256"]) == 64
    assert len(play.output_json.encode()) <= MAX_TOOL_OUTPUT_JSON_BYTES
    assert play.router_receipts[-1].decision == "ALLOWED"

    sealed = session.execute(
        "call-sealed",
        "read",
        {
            "path": "sealed/october_step1_results.json",
            "byte_start": 0,
            "byte_count": 100,
        },
    )
    assert sealed.status == "DENIED"
    assert "sealed answer marker" not in sealed.output_json
    assert sealed.router_receipts[-1].decision == "DENIED"

    archive = session.execute(
        "call-archive",
        "read",
        {"path": "archive/old.md", "byte_start": 0, "byte_count": 100},
    )
    assert archive.status == "DENIED"
    assert "archive secret marker" not in archive.output_json


class _SyntheticToolSession:
    definitions = ({"name": "synthetic"},)

    def __init__(self, payload_bytes: int) -> None:
        self.payload_bytes = payload_bytes

    def execute(self, call_id, name, arguments):
        request_json = json.dumps(
            {"call_id": call_id, "tool_name": name, "arguments": arguments},
            sort_keys=True,
            separators=(",", ":"),
        )
        request_hash = hashlib.sha256(request_json.encode()).hexdigest()
        result = {"payload": "x" * self.payload_bytes}
        response_hash = hashlib.sha256(
            json.dumps(
                {"status": "OK", "result": result},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        output_json = json.dumps(
            {
                "schema": "SYNTHETIC",
                "status": "OK",
                "tool_call_id": call_id,
                "tool_name": name,
                "request_sha256": request_hash,
                "response_sha256": response_hash,
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


class _SyntheticToolBackend:
    definitions = _SyntheticToolSession.definitions

    def __init__(self, payload_bytes: int) -> None:
        self.payload_bytes = payload_bytes

    def open_session(self, binding=None, lane_id=None):
        return _SyntheticToolSession(self.payload_bytes)


def test_composite_denies_oversized_child_result_without_returning_its_content():
    session = CompositeProviderToolBackend(
        _SyntheticToolBackend(MAX_TOOL_RESULT_JSON_BYTES + 1)
    ).open_session()
    execution = session.execute("oversized", "synthetic", {})
    assert execution.status == "DENIED"
    assert execution.result["reason"] == "TOOL_RESULT_BYTE_BUDGET_EXCEEDED"
    assert execution.result["rejected_output_bytes"] > MAX_TOOL_RESULT_JSON_BYTES
    assert len(execution.result["rejected_output_sha256"]) == 64
    assert len(execution.output_json.encode()) <= MAX_TOOL_OUTPUT_JSON_BYTES
    assert "x" * 1024 not in execution.output_json
    assert execution.retrievals == () and execution.router_receipts == ()


def test_composite_twelve_call_session_enforces_cumulative_serialized_byte_budget():
    payload_bytes = MAX_TOOL_SESSION_OUTPUT_BYTES // 11
    session = CompositeProviderToolBackend(
        _SyntheticToolBackend(payload_bytes)
    ).open_session()
    executions = [session.execute(f"cumulative-{index}", "synthetic", {}) for index in range(11)]
    assert [item.status for item in executions[:10]] == ["OK"] * 10
    assert executions[10].status == "DENIED"
    assert (
        executions[10].result["reason"]
        == "TOOL_SESSION_CUMULATIVE_BYTE_BUDGET_EXCEEDED"
    )
    assert sum(len(item.output_json.encode()) for item in executions) <= MAX_TOOL_SESSION_OUTPUT_BYTES
    with pytest.raises(ProviderToolError, match="cumulative output budget"):
        session.execute("cumulative-11", "synthetic", {})


def test_session_rejects_duplicate_ids_unknown_tools_and_more_than_twelve_calls(tmp_path):
    backend, _ = _backend(tmp_path, ContextVariant.S135_CONTROL)
    session = backend.open_session()
    session.execute("call-0", "list", {"cursor": 0, "limit": 1})
    with pytest.raises(ProviderToolError, match="duplicate"):
        session.execute("call-0", "list", {"cursor": 0, "limit": 1})
    with pytest.raises(ProviderToolError, match="unknown"):
        session.execute("call-unknown", "delete", {})

    session = backend.open_session()
    for index in range(12):
        session.execute(f"call-{index}", "list", {"cursor": 0, "limit": 1})
    with pytest.raises(ProviderToolError, match="budget"):
        session.execute("call-12", "list", {"cursor": 0, "limit": 1})


def test_composite_exposes_identical_1940_field_46_block_state_to_both_lanes_and_persists(tmp_path):
    control_knowledge, plane = _backend(tmp_path / "knowledge", ContextVariant.S135_CONTROL)
    combined_knowledge = LaneKnowledgeToolBackend(
        router=control_knowledge.router,
        bundle=control_knowledge.bundle,
        variant=ContextVariant.FULL_PROVISIONAL_COMBINED,
    )
    registry_paths = tuple(
        f"block_{block:02d}.field_{field:02d}"
        for block in range(44)
        for field in range(44)
    )
    oracle = RegistryCoverageOracle.create(
        paths=registry_paths,
        source_ids=("fixture-registry",),
        source_hashes=("4" * 64,),
    )
    snapshot = CausalDecisionStateSnapshotAdapter(oracle).snapshot(
        run_id="october-provider-tools",
        decision_day="20211001",
        evaluated_at=10.5,
        canonical_state={
            "live_weather": {"temperature": 18.0, "staleness": 0.0},
            "live_storage": {"inventory": 3000.0, "revision": 1},
        },
        canonical_source_id="fixture-complete-causal-state",
        canonical_source_sha256="5" * 64,
    )
    assert snapshot.path_count == 1940
    assert snapshot.block_count == 46
    bound = CausalPrefixBinding(
        run_id="october-provider-tools",
        causal_cutoff=10.5,
        event_known_by=10.5,
        causal_prefix_hash="1" * 64,
        state_prefix_hash="a" * 64,
        knowledge_manifest_hash=plane.manifest_hash,
    ).validate()
    control_journal = CausalEvidenceJournal.create(
        tmp_path / "control-evidence.jsonl", run_id=bound.run_id
    )
    combined_journal = CausalEvidenceJournal.create(
        tmp_path / "combined-evidence.jsonl", run_id=bound.run_id
    )
    control_causal = CausalRuntimeToolBackend(
        snapshot=snapshot,
        binding=bound,
        causal_state_path=None,
        evidence_journal=control_journal,
        commit_sha="6" * 40,
    )
    combined_causal = CausalRuntimeToolBackend(
        snapshot=snapshot,
        binding=bound,
        causal_state_path=None,
        evidence_journal=combined_journal,
        commit_sha="6" * 40,
    )
    control = CompositeProviderToolBackend(control_knowledge, control_causal)
    combined = CompositeProviderToolBackend(combined_knowledge, combined_causal)

    # The no-argument form is a required compatibility path for pre-bound backends.
    assert control.open_session().definitions == control.definitions
    control_session = control.open_session(bound, "S135_CONTROL")
    combined_session = combined.open_session(bound, "FULL_PROVISIONAL_COMBINED")
    left = control_session.execute("control-manifest", "decision_state_manifest", {})
    right = combined_session.execute("combined-manifest", "decision_state_manifest", {})
    assert left.result["snapshot_hash"] == right.result["snapshot_hash"] == snapshot.snapshot_hash
    assert left.result["path_count"] == right.result["path_count"] == 1940
    assert left.result["block_count"] == right.result["block_count"] == 46
    page = combined_session.execute(
        "combined-page", "decision_state_read", {"cursor": 0, "limit": 500}
    )
    assert page.retrievals and page.result["total_fields"] == 1940
    assert len(page.output_json.encode()) <= MAX_TOOL_OUTPUT_JSON_BYTES
    control_journal.close()
    combined_journal.close()

    for path, lane in (
        (tmp_path / "control-evidence.jsonl", "S135_CONTROL"),
        (tmp_path / "combined-evidence.jsonl", "FULL_PROVISIONAL_COMBINED"),
    ):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert {row["event_type"] for row in rows} >= {
            "CODE_IDENTITY",
            "SESSION_BINDING",
            "TOOL_READ",
        }
        assert any(row["payload"].get("lane_id") == lane for row in rows)
        assert all(len(row["record_hash"]) == 64 for row in rows)
