from __future__ import annotations

import copy
import hashlib
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_hipporag_p0_retrieval import (  # noqa: E402
    HippoCallbackResult,
    run_hipporag_shadow_pipeline,
)


H = "a" * 64
READER_HASH = "b" * 64


def chunk(
    chunk_id: str,
    text: str,
    *,
    created_at: str = "2026-08-20T09:00:00Z",
    knowable_at: str = "2026-08-20T09:00:00Z",
    parents=(),
    tokens: int = 5,
):
    return {
        "chunk_id": chunk_id,
        "text": text,
        "source_path": f"research/source/{chunk_id}.txt",
        "source_hash": hashlib.sha256(("source:" + chunk_id).encode()).hexdigest(),
        "content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "created_at": created_at,
        "knowable_at": knowable_at,
        "token_count": tokens,
        "parent_chunk_ids": list(parents),
        "immutable": True,
    }


def base_chunks():
    return [
        chunk("c1", "Alpha operates the venue."),
        chunk("c2", "The venue lists Beta.", parents=("c1",)),
        chunk("c3", "Beta is connected to Gamma.", parents=("c2",)),
    ]


def open_ie(request):
    ids = {item["chunk_id"] for item in request["source_chunks"]}
    entities = []
    triples = []
    if "c1" in ids:
        entities += [
            {"label": "Alpha", "source_chunk_ids": ["c1"]},
            {"label": "Venue", "source_chunk_ids": ["c1"]},
        ]
        triples.append(
            {
                "subject": "Alpha",
                "predicate": "operates",
                "object": "Venue",
                "source_chunk_ids": ["c1"],
            }
        )
    if "c2" in ids:
        entities += [
            {"label": "Venue", "source_chunk_ids": ["c2"]},
            {"label": "Beta", "source_chunk_ids": ["c2"]},
        ]
        triples.append(
            {
                "subject": "Venue",
                "predicate": "lists",
                "object": "Beta",
                "source_chunk_ids": ["c2"],
            }
        )
    if "c3" in ids:
        entities += [
            {"label": "Beta", "source_chunk_ids": ["c3"]},
            {"label": "Gamma", "source_chunk_ids": ["c3"]},
        ]
        triples.append(
            {
                "subject": "Beta",
                "predicate": "connected to",
                "object": "Gamma",
                "source_chunk_ids": ["c3"],
            }
        )
    return HippoCallbackResult(
        {"entities": entities, "triples": triples}, read_only=True, side_effect_free=True
    )


def query_entities(_request):
    return HippoCallbackResult(
        {"entities": ["Alpha"]}, read_only=True, side_effect_free=True
    )


def reader(request):
    first = request["retrieved_chunks"][0]
    return HippoCallbackResult(
        {
            "answer": "The retrieved evidence supports the answer.",
            "citations": [
                {
                    "chunk_id": first["chunk_id"],
                    "source_path": first["source_path"],
                    "source_hash": first["source_hash"],
                    "content_hash": first["content_hash"],
                }
            ],
        },
        read_only=True,
        side_effect_free=True,
    )


def kwargs(**overrides):
    values = {
        "source_chunks": base_chunks(),
        "invalidations": [],
        "query": "What does Alpha connect to?",
        "decision_cutoff_at": "2026-08-20T10:00:00Z",
        "target_birth_at": "2026-08-20T11:00:00Z",
        "open_ie_fn": open_ie,
        "query_entity_fn": query_entities,
        "reader_fn": reader,
        "open_ie_version_hash": H,
        "query_entity_version_hash": H,
        "reader_version_hash": READER_HASH,
        "matched_control": {
            "method": "FLAT_VECTOR_LIKE",
            "storage_budget_bytes": 100_000,
            "top_k": 3,
            "token_budget": 20,
            "reader_call_budget": 1,
            "reader_version_hash": READER_HASH,
        },
        "storage_budget_bytes": 100_000,
        "top_k": 3,
        "token_budget": 20,
    }
    values.update(overrides)
    return values


def test_complete_pipeline_binds_paper_mechanisms_and_frankie_gates():
    receipt = run_hipporag_shadow_pipeline(**kwargs())
    assert receipt["status"] == "COMPLETED"
    assert receipt["paper_faithful"] is False
    assert receipt["performance_evidence"] is False
    assert receipt["association_is_causality"] is False
    assert receipt["promotion_authority"] == "NONE"
    assert receipt["matched_control"]["control_executed"] is False
    assert receipt["matched_control"]["same_reader_version"] is True
    assert receipt["result"]["reader_output"]["exact_citation_paths_validated"] is True
    assert receipt["removal_receipt"]["canonical_state_changed"] is False


def test_generated_link_requires_exact_active_source_provenance():
    def bad_open_ie(_request):
        return HippoCallbackResult(
            {
                "entities": [
                    {"label": "Alpha", "source_chunk_ids": ["c1"]},
                    {"label": "Venue", "source_chunk_ids": ["c1"]},
                ],
                "triples": [
                    {
                        "subject": "Alpha",
                        "predicate": "operates",
                        "object": "Venue",
                        "source_chunk_ids": [],
                    }
                ],
            },
            read_only=True,
            side_effect_free=True,
        )

    receipt = run_hipporag_shadow_pipeline(**kwargs(open_ie_fn=bad_open_ie))
    assert receipt["status"] == "REJECTED"
    assert receipt["failed_stage"] == "graph"
    assert "sources" in receipt["reason"]
    assert receipt["failure_receipt"]["failed"] is True


def test_invalidation_withdraws_exact_descendant_closure_before_extraction():
    seen = {}

    def recording_open_ie(request):
        seen["ids"] = [item["chunk_id"] for item in request["source_chunks"]]
        return open_ie(request)

    invalidation = {
        "invalidation_id": "inv1",
        "invalidates_chunk_id": "c2",
        "invalidated_at": "2026-08-20T09:30:00Z",
        "source_hash": "c" * 64,
        "reason": "source corrected",
    }
    receipt = run_hipporag_shadow_pipeline(
        **kwargs(invalidations=[invalidation], open_ie_fn=recording_open_ie)
    )
    assert receipt["status"] == "COMPLETED"
    assert seen["ids"] == ["c1"]
    availability = receipt["result"]["availability_receipt"]
    assert availability["withdrawn_chunk_ids"] == ["c2", "c3"]
    assert availability["withdrawal_paths"]["c3"] == ["c2", "c3"]


def test_future_and_target_birth_chunks_never_reach_callbacks_or_graph():
    chunks = base_chunks() + [
        chunk(
            "future",
            "Future evidence.",
            created_at="2026-08-20T10:30:00Z",
            knowable_at="2026-08-20T10:30:00Z",
        ),
        chunk(
            "birth",
            "Target-derived evidence.",
            created_at="2026-08-20T11:00:00Z",
            knowable_at="2026-08-20T11:00:00Z",
        ),
    ]
    seen = {}

    def recording_open_ie(request):
        seen["ids"] = [item["chunk_id"] for item in request["source_chunks"]]
        return open_ie(request)

    receipt = run_hipporag_shadow_pipeline(
        **kwargs(source_chunks=chunks, open_ie_fn=recording_open_ie)
    )
    assert receipt["status"] == "COMPLETED"
    assert seen["ids"] == ["c1", "c2", "c3"]
    unavailable = receipt["result"]["availability_receipt"]["unavailable_chunks"]
    assert unavailable["future"] == "AFTER_DECISION_CUTOFF"
    assert unavailable["birth"] == "AT_OR_AFTER_TARGET_BIRTH"
    assert "chunk:future" not in {node["node_id"] for node in receipt["result"]["graph"]["nodes"]}
    assert receipt["result"]["availability_receipt"]["future_nodes_served"] == []


def test_chunk_after_cutoff_but_before_birth_and_chunk_at_birth_are_both_filtered():
    chunks = [
        chunk("c1", "Alpha operates the venue."),
        chunk(
            "after-cutoff",
            "Not available yet.",
            created_at="2026-08-20T10:30:00Z",
            knowable_at="2026-08-20T10:30:00Z",
        ),
        chunk(
            "at-birth",
            "Born with target.",
            created_at="2026-08-20T11:00:00Z",
            knowable_at="2026-08-20T11:00:00Z",
        ),
    ]
    receipt = run_hipporag_shadow_pipeline(**kwargs(source_chunks=chunks))
    assert receipt["status"] == "COMPLETED"
    assert receipt["result"]["availability_receipt"]["active_chunk_ids"] == ["c1"]
    assert receipt["result"]["availability_receipt"]["unavailable_chunks"] == {
        "after-cutoff": "AFTER_DECISION_CUTOFF",
        "at-birth": "AT_OR_AFTER_TARGET_BIRTH",
    }


def test_dangling_generated_triple_endpoint_fails_closed():
    def dangling(_request):
        return HippoCallbackResult(
            {
                "entities": [{"label": "Alpha", "source_chunk_ids": ["c1"]}],
                "triples": [
                    {
                        "subject": "Alpha",
                        "predicate": "mentions",
                        "object": "Unknown",
                        "source_chunk_ids": ["c1"],
                    }
                ],
            },
            read_only=True,
            side_effect_free=True,
        )

    receipt = run_hipporag_shadow_pipeline(**kwargs(open_ie_fn=dangling))
    assert receipt["status"] == "REJECTED"
    assert "dangling" in receipt["reason"]


def test_ppr_and_graph_hashes_are_deterministic_under_input_and_proposal_reordering():
    first = run_hipporag_shadow_pipeline(**kwargs())

    def reversed_open_ie(request):
        result = open_ie(request)
        payload = copy.deepcopy(dict(result.payload))
        payload["entities"].reverse()
        payload["triples"].reverse()
        return HippoCallbackResult(payload, read_only=True, side_effect_free=True)

    second = run_hipporag_shadow_pipeline(
        **kwargs(source_chunks=list(reversed(base_chunks())), open_ie_fn=reversed_open_ie)
    )
    assert first["status"] == second["status"] == "COMPLETED"
    assert first["result"]["graph"]["graph_hash"] == second["result"]["graph"]["graph_hash"]
    assert (
        first["result"]["retrieval"]["ppr"]["ppr_hash"]
        == second["result"]["retrieval"]["ppr"]["ppr_hash"]
    )
    assert first["result"]["retrieval"]["selected_chunk_ids"] == second["result"]["retrieval"]["selected_chunk_ids"]


def test_reader_citation_must_match_exact_retrieved_source_path_and_hashes():
    def lying_reader(request):
        first = request["retrieved_chunks"][0]
        return HippoCallbackResult(
            {
                "answer": "unsupported path",
                "citations": [
                    {
                        "chunk_id": first["chunk_id"],
                        "source_path": "different/path.txt",
                        "source_hash": first["source_hash"],
                        "content_hash": first["content_hash"],
                    }
                ],
            },
            read_only=True,
            side_effect_free=True,
        )

    receipt = run_hipporag_shadow_pipeline(**kwargs(reader_fn=lying_reader))
    assert receipt["status"] == "REJECTED"
    assert receipt["failed_stage"] == "reader"
    assert "path/hash mismatch" in receipt["reason"]


def test_reader_callback_failure_and_input_mutation_both_leave_removal_receipts():
    def failed_reader(_request):
        raise RuntimeError("reader unavailable")

    failed = run_hipporag_shadow_pipeline(**kwargs(reader_fn=failed_reader))
    assert failed["status"] == "REJECTED"
    assert failed["failed_stage"] == "reader"
    assert failed["removal_receipt"]["canonical_state_changed"] is False

    def mutating_reader(request):
        first = request["retrieved_chunks"].pop(0)
        return HippoCallbackResult(
            {
                "answer": "mutation attempted",
                "citations": [
                    {
                        "chunk_id": first["chunk_id"],
                        "source_path": first["source_path"],
                        "source_hash": first["source_hash"],
                        "content_hash": first["content_hash"],
                    }
                ],
            },
            read_only=True,
            side_effect_free=True,
        )

    mutated = run_hipporag_shadow_pipeline(**kwargs(reader_fn=mutating_reader))
    assert mutated["status"] == "REJECTED"
    assert "mutated its detached input" in mutated["reason"]
    assert mutated["canonical_mutation"] is False


def test_matched_control_and_fault_injection_fail_closed_without_claiming_evidence():
    unmatched = kwargs()
    unmatched["matched_control"] = dict(unmatched["matched_control"])
    unmatched["matched_control"]["reader_call_budget"] = 2
    rejected = run_hipporag_shadow_pipeline(**unmatched)
    assert rejected["status"] == "REJECTED"
    assert "reader_call_budget" in rejected["reason"]
    assert rejected["performance_evidence"] is False

    faulted = run_hipporag_shadow_pipeline(**kwargs(faults=["ppr"]))
    assert faulted["status"] == "REJECTED"
    assert faulted["failed_stage"] == "ppr"
    assert faulted["failure_receipt"]["fault_plan"] == ["ppr"]
    assert faulted["automatic_apply"] is False
