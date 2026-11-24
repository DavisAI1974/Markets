from __future__ import annotations

from pathlib import Path
from typing import Any

from refrag_discovery.registry import DEFAULT_EVIDENCE_SCHEMA_PATH, validate_evidence_graph
from refrag_discovery.runtime.types import RetrievedChunk


def _clip_confidence(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _upsert_node(nodes_by_id: dict[str, dict[str, Any]], node: dict[str, Any]) -> None:
    existing = nodes_by_id.get(node["id"])
    if existing is None:
        nodes_by_id[node["id"]] = node
        return
    if node.get("text") and not existing.get("text"):
        existing["text"] = node["text"]
    if node.get("embedding") and not existing.get("embedding"):
        existing["embedding"] = node["embedding"]
    existing_metadata = dict(existing.get("metadata", {}))
    existing_metadata.update(node.get("metadata", {}))
    if existing_metadata:
        existing["metadata"] = existing_metadata


def _append_edge(
    edges: list[dict[str, Any]],
    seen_edges: set[tuple[str, str, str]],
    edge: dict[str, Any],
) -> None:
    key = (str(edge.get("source")), str(edge.get("target")), str(edge.get("relation")))
    if key in seen_edges:
        return
    edges.append(edge)
    seen_edges.add(key)


def _extract_claim_document_map(graph: dict[str, Any]) -> dict[str, set[str]]:
    node_map = {
        str(node.get("id")): node
        for node in graph.get("nodes", [])
        if node.get("id")
    }
    chunk_documents: dict[str, set[str]] = {}
    for edge in graph.get("edges", []):
        if edge.get("relation") != "derived_from":
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source not in node_map or target not in node_map:
            continue
        target_node = node_map[target]
        if target_node.get("type") != "document":
            continue
        source_id = str(target_node.get("metadata", {}).get("source_id") or target.removeprefix("document:"))
        chunk_documents.setdefault(source, set()).add(source_id)

    claim_documents: dict[str, set[str]] = {}
    for node in graph.get("nodes", []):
        if node.get("type") != "claim":
            continue
        claim_documents[str(node["id"])] = {
            str(document_id)
            for document_id in node.get("metadata", {}).get("supporting_documents", [])
            if document_id
        }

    for edge in graph.get("edges", []):
        if edge.get("relation") not in {"supports", "contradicts"}:
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if target not in claim_documents:
            continue
        claim_documents[target].update(chunk_documents.get(source, set()))
    return claim_documents


def _historical_claim_summary(graph: dict[str, Any]) -> tuple[int, float, float]:
    claim_ids = {
        str(node.get("id"))
        for node in graph.get("nodes", [])
        if node.get("type") == "claim" and node.get("id")
    }
    support_mass = 0.0
    contradiction_mass = 0.0
    for edge in graph.get("edges", []):
        target = str(edge.get("target", ""))
        if target not in claim_ids:
            continue
        confidence = float(edge.get("confidence", 0.0) or 0.0)
        if edge.get("relation") == "supports":
            support_mass += confidence
        elif edge.get("relation") == "contradicts":
            contradiction_mass += confidence
    return len(claim_ids), round(support_mass, 4), round(contradiction_mass, 4)


def validate_runtime_graph(graph: dict[str, Any], *, require_claim: bool = True) -> tuple[str, ...]:
    errors = list(validate_evidence_graph(graph, DEFAULT_EVIDENCE_SCHEMA_PATH))
    node_ids: set[str] = set()
    claim_ids: set[str] = set()
    for index, node in enumerate(graph.get("nodes", [])):
        node_id = str(node.get("id", "")).strip()
        if not node_id:
            errors.append(f"nodes.{index}.id: missing node id")
            continue
        if node_id in node_ids:
            errors.append(f"nodes.{index}.id: duplicate node id {node_id}")
            continue
        node_ids.add(node_id)
        if str(node.get("type", "")) == "claim":
            claim_ids.add(node_id)

    if require_claim and not claim_ids:
        errors.append("nodes: graph must contain at least one claim node")

    for index, edge in enumerate(graph.get("edges", [])):
        source = str(edge.get("source", "")).strip()
        target = str(edge.get("target", "")).strip()
        if source and source not in node_ids:
            errors.append(f"edges.{index}.source: missing node {source}")
        if target and target not in node_ids:
            errors.append(f"edges.{index}.target: missing node {target}")
    return tuple(errors)


def execute(
    *,
    evidence_items: list,
    graph_id: str,
    reasoning_mode: str = "static",
    n_message_passes: int = 4,
    merge_strategy: str = "append",
    existing_graph: dict | None = None,
) -> dict:
    nodes_by_id: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    document_ids: dict[str, str] = {}
    chunk_ids: list[str] = []
    contradictions: list[dict] = []
    inferred_edges: list[dict] = []
    claim_id = f"claim:{graph_id}"
    claim_text = "Recovered operator hypothesis from prioritized evidence."
    current_support_mass = 0.0
    current_contradiction_mass = 0.0
    current_supporting_documents: set[str] = set()

    if existing_graph:
        existing_graph_errors = validate_runtime_graph(existing_graph, require_claim=False)
        if existing_graph_errors:
            raise ValueError(f"existing_graph invalid: {'; '.join(existing_graph_errors)}")

    for item in evidence_items:
        if isinstance(item, RetrievedChunk):
            document_node_id = document_ids.setdefault(
                item.chunk.source_id,
                f"document:{item.chunk.source_id}",
            )
            current_supporting_documents.add(item.chunk.source_id)
            _upsert_node(
                nodes_by_id,
                {
                    "id": document_node_id,
                    "type": "document",
                    "text": item.chunk.source_id,
                    "metadata": {"source_id": item.chunk.source_id},
                },
            )
            chunk_node_id = f"chunk:{item.chunk.chunk_id}"
            chunk_ids.append(chunk_node_id)
            score = _clip_confidence(float(item.score))
            _upsert_node(
                nodes_by_id,
                {
                    "id": chunk_node_id,
                    "type": "chunk",
                    "text": f"{item.chunk.source_id}[{item.chunk.window_start}:{item.chunk.window_end}]",
                    "embedding": item.embedding,
                    "metadata": {
                        "score": score,
                        "information_gain": item.information_gain,
                    },
                },
            )
            _append_edge(
                edges,
                seen_edges,
                {
                    "source": chunk_node_id,
                    "target": document_node_id,
                    "relation": "derived_from",
                    "confidence": 1.0,
                },
            )
            current_support_mass += score
            if score < 0.45:
                contradiction_confidence = _clip_confidence(1.0 - score)
                contradiction = {
                    "chunk_id": item.chunk.chunk_id,
                    "reason": "Low support score indicates possible contradiction",
                    "score": score,
                }
                contradictions.append(contradiction)
                current_contradiction_mass += contradiction_confidence
                _append_edge(
                    edges,
                    seen_edges,
                    {
                        "source": chunk_node_id,
                        "target": claim_id,
                        "relation": "contradicts",
                        "confidence": contradiction_confidence,
                    },
                )
        elif isinstance(item, dict) and "operator_coefficients" in item:
            claim_text = (
                "Recovered operator coefficients: "
                + ", ".join(f"{value:.4f}" for value in item["operator_coefficients"][:8])
            )
            decoder_support = _clip_confidence(
                max(
                    0.0,
                    1.0 - max(item["coefficient_posterior"]["std"]),
                )
            )
            current_support_mass += decoder_support
            _upsert_node(
                nodes_by_id,
                {
                    "id": f"fact:{graph_id}:posterior",
                    "type": "fact",
                    "text": f"Posterior width {max(item['coefficient_posterior']['std']):.4f}",
                    "metadata": item["coefficient_posterior"],
                },
            )
            _append_edge(
                edges,
                seen_edges,
                {
                    "source": f"fact:{graph_id}:posterior",
                    "target": claim_id,
                    "relation": "references",
                    "confidence": 0.9,
                },
            )

    _upsert_node(
        nodes_by_id,
        {
            "id": claim_id,
            "type": "claim",
            "text": claim_text,
            "metadata": {
                "graph_id": graph_id,
                "supporting_documents": sorted(current_supporting_documents),
            },
        },
    )
    for chunk_node_id in chunk_ids:
        chunk_node = nodes_by_id[chunk_node_id]
        _append_edge(
            edges,
            seen_edges,
            {
                "source": chunk_node_id,
                "target": claim_id,
                "relation": "supports",
                "confidence": _clip_confidence(float(chunk_node["metadata"]["score"])),
            },
        )

    for left_index, left_chunk_id in enumerate(chunk_ids):
        left_node = nodes_by_id[left_chunk_id]
        for right_chunk_id in chunk_ids[left_index + 1 :]:
            right_node = nodes_by_id[right_chunk_id]
            if left_node["text"].split("[", 1)[0] == right_node["text"].split("[", 1)[0]:
                edge = {
                    "source": left_chunk_id,
                    "target": right_chunk_id,
                    "relation": "references",
                    "confidence": 0.55,
                }
                inferred_edges.append(edge)
                _append_edge(edges, seen_edges, edge)

    historical_claim_count = 0
    prior_support_mass = 0.0
    prior_contradiction_mass = 0.0

    if existing_graph:
        claim_documents = _extract_claim_document_map(existing_graph)
        historical_claim_count, prior_support_mass, prior_contradiction_mass = _historical_claim_summary(
            existing_graph
        )
        existing_nodes = existing_graph.get("nodes", [])
        existing_edges = existing_graph.get("edges", [])
        for node in existing_nodes:
            if node.get("id"):
                _upsert_node(nodes_by_id, dict(node))
        for edge in existing_edges:
            _append_edge(edges, seen_edges, dict(edge))
        for historical_claim_id, supporting_documents in claim_documents.items():
            if historical_claim_id == claim_id:
                continue
            overlap = current_supporting_documents & supporting_documents
            if not overlap:
                continue
            union = current_supporting_documents | supporting_documents
            _append_edge(
                edges,
                seen_edges,
                {
                    "source": claim_id,
                    "target": historical_claim_id,
                    "relation": "related_to",
                    "confidence": _clip_confidence(max(0.35, len(overlap) / max(1, len(union)))),
                },
            )

    graph = {"nodes": list(nodes_by_id.values()), "edges": edges}
    errors = validate_runtime_graph(graph)
    if errors:
        raise ValueError("; ".join(errors))

    alpha = 1.0 + prior_support_mass + current_support_mass
    beta = 1.0 + prior_contradiction_mass + current_contradiction_mass
    probability_valid = round(alpha / max(1.0, alpha + beta), 4)
    return {
        "graph": graph,
        "clusters": [
            {
                "cluster_id": f"cluster:{graph_id}:support",
                "members": chunk_ids,
            }
        ],
        "contradictions": contradictions,
        "operator_validity_posterior": {
            "probability_valid": probability_valid,
            "reasoning_mode": reasoning_mode,
            "n_message_passes": n_message_passes,
            "historical_claim_count": historical_claim_count,
            "prior_support_mass": round(prior_support_mass, 4),
            "prior_contradiction_mass": round(prior_contradiction_mass, 4),
            "current_support_mass": round(current_support_mass, 4),
            "current_contradiction_mass": round(current_contradiction_mass, 4),
        },
        "inferred_edges": inferred_edges,
        "metadata": {
            "merge_strategy": merge_strategy,
            "schema_path": str(Path(DEFAULT_EVIDENCE_SCHEMA_PATH)),
            "merged_existing_graph": bool(existing_graph),
            "supporting_documents": sorted(current_supporting_documents),
            "accumulated_claim_count": historical_claim_count + 1,
        },
    }
