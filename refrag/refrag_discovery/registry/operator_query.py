from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from adapters.od_refrag_adapter import OperatorCandidate, OperatorQuery as AdapterOperatorQuery
from refrag_discovery.registry.bootstrap import ManifestRegistry, bootstrap_registry
from refrag_discovery.registry.manifest_validator import (
    DEFAULT_MANIFESTS_DIR,
    DEFAULT_OPERATOR_SCHEMA_PATH,
)
from refrag_discovery.registry.models import SearchResult


TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text)}


def _cosine(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left)) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right)) or 1.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


@dataclass
class OperatorQueryService:
    registry: ManifestRegistry
    default_d_enc: int = 128

    def get_manifest(self, operator_id: str) -> dict[str, Any]:
        return dict(self.registry.records_by_id[operator_id].manifest)

    def list_manifests(
        self,
        *,
        execution_class: str | None = None,
        operator_type: str | None = None,
    ) -> list[dict[str, Any]]:
        manifests = list(self.registry.records_by_id.values())
        if execution_class:
            manifests = [
                record for record in manifests if record.execution_class == execution_class
            ]
        if operator_type:
            manifests = [
                record for record in manifests if record.operator_type == operator_type
            ]
        return [dict(record.manifest) for record in sorted(manifests, key=lambda item: item.operator_id)]

    def search(
        self,
        text: str = "",
        *,
        capabilities: list[str] | None = None,
        execution_class: str | None = None,
        operator_type: str | None = None,
        top_k: int = 10,
    ) -> list[SearchResult]:
        candidates = list(self.registry.records_by_id.values())
        if execution_class:
            candidates = [
                record for record in candidates if record.execution_class == execution_class
            ]
        if operator_type:
            candidates = [
                record for record in candidates if record.operator_type == operator_type
            ]

        query_tokens = _tokens(text)
        requested_capabilities = {item.lower() for item in capabilities or []}
        results: list[SearchResult] = []

        for record in candidates:
            score = 0.0
            if query_tokens:
                overlap = len(query_tokens & _tokens(record.search_text))
                score += overlap / max(1, len(query_tokens))
            if requested_capabilities:
                available = {cap.lower() for cap in record.capabilities}
                cap_overlap = len(requested_capabilities & available)
                score += (2.0 * cap_overlap) / max(1, len(requested_capabilities))
            if text or requested_capabilities:
                if score <= 0:
                    continue
            manifest = record.manifest
            results.append(
                SearchResult(
                    operator_id=record.operator_id,
                    operator_name=str(manifest.get("operator_name", record.operator_id)),
                    description=str(manifest.get("description", "")),
                    score=round(score, 4),
                    execution_class=record.execution_class,
                    operator_type=record.operator_type,
                    path=record.path,
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]

    def resolve_dependencies(self, operator_id: str, *, transitive: bool = True) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []

        def visit(current_operator_id: str) -> None:
            for dependency_id in self.registry.dependency_graph.get(current_operator_id, ()):
                if dependency_id in seen:
                    continue
                seen.add(dependency_id)
                if transitive:
                    visit(dependency_id)
                ordered.append(dependency_id)

        visit(operator_id)
        return ordered

    def resolve_pipeline_stages(self, pipeline_id: str) -> list[str]:
        execution_waves = self.resolve_pipeline_dag(pipeline_id)
        return [stage_id for wave in execution_waves for stage_id in wave]

    def resolve_pipeline_dag(self, pipeline_id: str) -> list[list[str]]:
        manifest = self.get_manifest(pipeline_id)
        stage_entries = [
            dependency
            for dependency in manifest.get("dependencies", [])
            if dependency.get("operator_id") and dependency.get("operator_id") != "operator_orchestrator"
        ]
        stage_ids = [str(dependency.get("operator_id")) for dependency in stage_entries]
        stage_set = set(stage_ids)
        stage_position = {stage_id: index for index, stage_id in enumerate(stage_ids)}
        dependency_map: dict[str, list[str]] = {}
        uses_explicit_stage_edges = any("depends_on" in dependency for dependency in stage_entries)
        previous_stage: str | None = None
        for dependency in stage_entries:
            stage_id = str(dependency.get("operator_id"))
            if uses_explicit_stage_edges:
                declared_dependencies = []
                for dependency_id in dependency.get("depends_on", []):
                    normalized_dependency_id = str(dependency_id)
                    if normalized_dependency_id == stage_id:
                        raise ValueError(f"Pipeline stage {stage_id} cannot depend on itself")
                    if normalized_dependency_id not in stage_set:
                        raise ValueError(
                            f"Pipeline stage {stage_id} depends on unknown stage {normalized_dependency_id}"
                        )
                    declared_dependencies.append(normalized_dependency_id)
                dependency_map[stage_id] = list(dict.fromkeys(declared_dependencies))
                continue

            explicit_dependencies = [
                dependency_id
                for dependency_id in self.registry.dependency_graph.get(stage_id, ())
                if dependency_id in stage_set
                and dependency_id != stage_id
                and stage_position[dependency_id] < stage_position[stage_id]
            ]
            dependencies = list(explicit_dependencies)
            if previous_stage is not None and previous_stage not in dependencies:
                dependencies.append(previous_stage)
            dependency_map[stage_id] = dependencies
            previous_stage = stage_id

        remaining = set(stage_ids)
        resolved: set[str] = set()
        waves: list[list[str]] = []
        while remaining:
            ready = [
                stage_id
                for stage_id in stage_ids
                if stage_id in remaining and all(dependency in resolved for dependency in dependency_map[stage_id])
            ]
            if not ready:
                unresolved = ", ".join(sorted(remaining))
                raise ValueError(f"Pipeline dependency cycle or missing dependency among: {unresolved}")
            waves.append(ready)
            resolved.update(ready)
            remaining.difference_update(ready)
        return waves

    def build_query_vectors(
        self,
        *,
        mode: str,
        candidate: dict[str, Any] | None = None,
        target_frequencies: list[float] | None = None,
        target_energy: float = 1.0,
        evidence_state: dict[str, Any] | None = None,
        n_queries: int = 1,
        d_enc: int | None = None,
        sample_rate: float = 1.0,
    ) -> dict[str, Any]:
        dimension = d_enc or self.default_d_enc
        builder = AdapterOperatorQuery(d_enc=dimension)
        base_vector: list[float]

        if mode == "from_candidate":
            base_vector = builder.from_candidate(self._candidate_from_dict(candidate, dimension))
        elif mode == "from_spectral_target":
            base_vector = builder.from_spectral_target(
                target_frequencies=target_frequencies or [],
                target_energy=target_energy,
                sample_rate=sample_rate,
            )
        elif mode == "learned_synthesis":
            base_vector = self._synthesize_from_evidence(evidence_state or {}, dimension)
        elif mode == "multi_query_dpp":
            base_vector = builder.from_spectral_target(
                target_frequencies=target_frequencies or [],
                target_energy=target_energy,
                sample_rate=sample_rate,
            )
        else:
            raise ValueError(f"Unsupported operator_query mode: {mode}")

        query_vectors = [base_vector]
        if mode == "multi_query_dpp":
            query_vectors = self._diversify_queries(base_vector, n_queries)
        elif n_queries > 1:
            query_vectors = self._diversify_queries(base_vector, n_queries)

        diversity = 0.0
        if len(query_vectors) > 1:
            pairwise: list[float] = []
            for idx, left in enumerate(query_vectors):
                for right in query_vectors[idx + 1 :]:
                    pairwise.append(1.0 - _cosine(left, right))
            diversity = sum(pairwise) / max(1, len(pairwise))

        gains = [round(sum(abs(value) for value in vector[:8]) / 8.0, 4) for vector in query_vectors]
        return {
            "query_vectors": query_vectors,
            "query_diversity_score": round(diversity, 4),
            "expected_information_gain": gains,
        }

    def _candidate_from_dict(
        self,
        candidate: dict[str, Any] | None,
        d_enc: int,
    ) -> OperatorCandidate:
        spectral_signature = []
        coefficients: dict[str, float] = {}
        operator_id = "candidate_operator"
        if candidate:
            operator_id = str(candidate.get("operator_id", operator_id))
            coefficients = {
                str(key): float(value)
                for key, value in candidate.get("coefficients", {}).items()
            }
            signature = candidate.get("spectral_signature", [])
            spectral_signature = [float(value) for value in signature]
            if not spectral_signature and coefficients:
                spectral_signature = list(coefficients.values())

        if not spectral_signature:
            spectral_signature = [0.0] * d_enc

        return OperatorCandidate(
            operator_id=operator_id,
            spectral_signature=spectral_signature,
            coefficients=coefficients,
            source_domain=str(candidate.get("source_domain", "")) if candidate else "",
        )

    def _synthesize_from_evidence(self, evidence_state: dict[str, Any], d_enc: int) -> list[float]:
        embeddings = [
            [float(value) for value in embedding]
            for embedding in evidence_state.get("embeddings", [])
            if embedding
        ]
        if not embeddings:
            return [0.0] * d_enc
        base = [0.0] * len(embeddings[0])
        for embedding in embeddings:
            for idx, value in enumerate(embedding):
                base[idx] += value
        return [value / len(embeddings) for value in base[:d_enc]]

    def _diversify_queries(self, base_vector: list[float], n_queries: int) -> list[list[float]]:
        queries = []
        for offset in range(max(1, n_queries)):
            query = list(base_vector)
            if query:
                query[offset % len(query)] += 0.1 * (offset + 1)
            queries.append(query)
        return queries


@lru_cache(maxsize=1)
def build_default_operator_query(
    *,
    repair: bool = False,
    manifests_dir: Path = DEFAULT_MANIFESTS_DIR,
    schema_path: Path = DEFAULT_OPERATOR_SCHEMA_PATH,
) -> OperatorQueryService:
    registry = bootstrap_registry(manifests_dir, schema_path, repair=repair)
    return OperatorQueryService(registry=registry)
