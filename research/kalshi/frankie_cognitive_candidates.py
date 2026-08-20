"""Pure SHADOW candidate components derived from Frankie's cognitive top ten.

These helpers are deliberately non-agentic: they validate, select, score, or
rank already supplied objects.  They cannot call models or tools, mutate source
evidence, write canonical memory, promote a candidate, or execute a trade.
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from frankie_cognition import (
    COGNITIVE_CONTRACT_VERSION,
    CognitiveContractError,
    ReasoningStep,
    sha256_json,
)


def coala_architecture_map() -> dict[str, Any]:
    """Return Frankie's explicit cognitive ownership map without changing behavior."""
    mapping = {
        "contract_version": COGNITIVE_CONTRACT_VERSION,
        "memory": {
            "WORKING": "current event, qualification, and bounded task chunks",
            "EPISODIC": "immutable decisions, resolved outcomes, and attributed cases",
            "SEMANTIC": "reviewed paper claims, typed brain knowledge, and definitions",
            "PROCEDURAL": "candidate contracts, deterministic gates, and reviewed plays",
        },
        "actions": {
            "internal_read_only": ["OBSERVE", "RETRIEVE", "REASON", "VERIFY", "ABSTAIN"],
            "external_read_only": ["typed evidence read", "deterministic check"],
            "forbidden": ["EXECUTE", "TRADE", "WRITE_CANONICAL", "PROMOTE", "CHANGE_PERMISSION"],
        },
        "owners": {
            "causal_scientist": "mechanism, alternatives, knowability, falsification",
            "trading_mechanics": "contract, settlement, cost, liquidity, balance convention",
            "deterministic_adjudicator": "qualification, lane agreement, authority cap",
            "outcome_resolver": "append-only resolved sidecar",
            "improvement_proposer": "one disposable bounded proposal",
            "independent_critic": "proposal criticism without apply authority",
            "human_release_owner": "sandbox review and any permanent promotion",
        },
        "execution_enabled": False,
        "automatic_apply": False,
    }
    return {**mapping, "architecture_hash": sha256_json(mapping)}


class TypedEvidenceStore:
    """Read exact catalog records by id; there is intentionally no write method."""

    def __init__(self, cognitive_context: Mapping[str, Any]):
        if cognitive_context.get("contract_version") != COGNITIVE_CONTRACT_VERSION:
            raise CognitiveContractError("typed evidence store requires the current cognitive contract")
        catalog = cognitive_context.get("evidence_catalog")
        if not isinstance(catalog, list) or not catalog:
            raise CognitiveContractError("typed evidence store requires a non-empty catalog")
        observed_hash = sha256_json(catalog)
        if observed_hash != cognitive_context.get("evidence_catalog_hash"):
            raise CognitiveContractError("typed evidence catalog hash mismatch")
        self._records: dict[str, dict[str, Any]] = {}
        for record in catalog:
            if not isinstance(record, Mapping) or not record.get("ref_id"):
                raise CognitiveContractError("invalid typed evidence record")
            ref_id = str(record["ref_id"])
            if ref_id in self._records:
                raise CognitiveContractError(f"duplicate typed evidence record: {ref_id}")
            if record.get("immutable") is not True or record.get("status") != "ACTIVE":
                raise CognitiveContractError(f"typed evidence record is not active and immutable: {ref_id}")
            self._records[ref_id] = dict(record)
        self.catalog_hash = observed_hash

    def read(self, ref_ids: Sequence[str], *, max_records: int = 8) -> dict[str, Any]:
        if not 1 <= max_records <= 32:
            raise CognitiveContractError("typed read max_records must be within [1, 32]")
        requested = tuple(dict.fromkeys(str(ref_id) for ref_id in ref_ids))
        if not requested or len(requested) > max_records:
            raise CognitiveContractError("typed read is empty or exceeds its record budget")
        missing = sorted(set(requested) - self._records.keys())
        if missing:
            raise CognitiveContractError(f"typed read requested unknown refs: {', '.join(missing)}")
        records = [self._records[ref_id] for ref_id in requested]
        payload = {
            "catalog_hash": self.catalog_hash,
            "requested_refs": requested,
            "records": records,
            "write_authority": "NONE",
        }
        return {**payload, "read_hash": sha256_json(payload)}


def validate_react_trace(steps: Sequence[ReasoningStep]) -> dict[str, Any]:
    """Require evidence acquisition to feed later reasoning rather than float beside it."""
    if not steps:
        raise CognitiveContractError("ReAct trace cannot be empty")
    positions = {step.step_id: index for index, step in enumerate(steps)}
    evidence_step_ids = {
        step.step_id for step in steps if step.action in {"OBSERVE", "RETRIEVE"}
    }
    retrieve_ids = {step.step_id for step in steps if step.action == "RETRIEVE"}
    used_retrievals: set[str] = set()
    grounded_reasoning: set[str] = set()
    for step in steps:
        for dependency in step.depends_on:
            if dependency not in positions or positions[dependency] >= positions[step.step_id]:
                raise CognitiveContractError(f"ReAct step {step.step_id} has a non-prior dependency")
        if step.action in {"REASON", "VERIFY"}:
            used_retrievals.update(set(step.depends_on).intersection(retrieve_ids))
            pending = list(step.depends_on)
            ancestors: set[str] = set()
            while pending:
                dependency = pending.pop()
                if dependency in ancestors:
                    continue
                ancestors.add(dependency)
                pending.extend(steps[positions[dependency]].depends_on)
            used_retrievals.update(ancestors.intersection(retrieve_ids))
            if ancestors.intersection(evidence_step_ids):
                grounded_reasoning.add(step.step_id)
    unused = sorted(retrieve_ids - used_retrievals)
    if unused:
        raise CognitiveContractError(f"retrieved evidence was never used by later reasoning: {', '.join(unused)}")
    reasoning_ids = {step.step_id for step in steps if step.action == "REASON"}
    if not reasoning_ids:
        raise CognitiveContractError("ReAct trace requires at least one REASON step")
    ungrounded = sorted(reasoning_ids - grounded_reasoning)
    if ungrounded:
        raise CognitiveContractError(
            "reasoning lacks an OBSERVE/RETRIEVE dependency path: " + ", ".join(ungrounded)
        )
    payload = [dataclasses.asdict(step) for step in steps]
    return {
        "valid": True,
        "steps": len(steps),
        "retrievals": len(retrieve_ids),
        "trace_hash": sha256_json(payload),
        "execution_authority": "NONE",
    }


@dataclass(frozen=True)
class PlanBranch:
    branch_id: str
    parent_id: str | None
    depth: int
    external_score: float
    feedback_refs: tuple[str, ...]
    status: str


def select_bounded_plan_branches(
    rows: Sequence[Mapping[str, Any]],
    *,
    max_width: int = 3,
    max_depth: int = 3,
) -> dict[str, Any]:
    """Select bounded LATS-style branches using external feedback only."""
    if not 1 <= max_width <= 8 or not 1 <= max_depth <= 8:
        raise CognitiveContractError("plan width/depth exceeds the bounded search contract")
    branches: list[PlanBranch] = []
    by_id: dict[str, PlanBranch] = {}
    for index, row in enumerate(rows):
        if "self_score" in row or "model_score" in row:
            raise CognitiveContractError("plan branches may not own their value function")
        branch_id = str(row.get("branch_id") or "").strip()
        if not branch_id or branch_id in by_id:
            raise CognitiveContractError(f"invalid or duplicate plan branch at row {index}")
        parent_raw = row.get("parent_id")
        parent_id = str(parent_raw) if parent_raw is not None else None
        depth = int(row.get("depth", -1))
        if depth < 0 or depth > max_depth:
            raise CognitiveContractError(f"plan branch {branch_id} exceeds depth contract")
        if parent_id is None and depth != 0:
            raise CognitiveContractError(f"root plan branch {branch_id} must have depth zero")
        if parent_id is not None:
            parent = by_id.get(parent_id)
            if parent is None or depth != parent.depth + 1:
                raise CognitiveContractError(f"plan branch {branch_id} has an invalid parent/depth")
        score_raw = row.get("external_score")
        if isinstance(score_raw, bool) or not isinstance(score_raw, (int, float)):
            raise CognitiveContractError(f"plan branch {branch_id} requires an external score")
        score = float(score_raw)
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise CognitiveContractError(f"plan branch {branch_id} score must be within [0, 1]")
        refs_raw = row.get("feedback_refs")
        if not isinstance(refs_raw, list) or not refs_raw or not all(isinstance(v, str) and v for v in refs_raw):
            raise CognitiveContractError(f"plan branch {branch_id} requires external feedback refs")
        status = str(row.get("status") or "INCONCLUSIVE").upper()
        if status not in {"SUPPORTED", "CONTRADICTED", "INCONCLUSIVE"}:
            raise CognitiveContractError(f"plan branch {branch_id} has invalid status")
        branch = PlanBranch(branch_id, parent_id, depth, score, tuple(dict.fromkeys(refs_raw)), status)
        branches.append(branch)
        by_id[branch_id] = branch
    if not branches:
        raise CognitiveContractError("bounded plan search requires branches")
    selected: list[PlanBranch] = []
    selected_ids: set[str] = set()
    for depth in range(max_depth + 1):
        at_depth = [
            branch
            for branch in branches
            if branch.depth == depth
            and branch.status != "CONTRADICTED"
            and (branch.parent_id is None or branch.parent_id in selected_ids)
        ]
        chosen = sorted(
            at_depth,
            key=lambda branch: (-branch.external_score, branch.branch_id),
        )[:max_width]
        selected.extend(chosen)
        selected_ids.update(branch.branch_id for branch in chosen)
    payload = [dataclasses.asdict(branch) for branch in selected]
    return {
        "selected": payload,
        "search_hash": sha256_json(payload),
        "value_owner": "EXTERNAL_FEEDBACK_ONLY",
        "promotion_authority": "NONE",
    }


def run_deterministic_check(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Execute one allowlisted Faithful-CoT/CRITIC check over supplied values."""
    check_id = str(spec.get("check_id") or "").strip()
    check_type = str(spec.get("check_type") or "").strip().upper()
    refs = spec.get("evidence_refs")
    if not check_id or not isinstance(refs, list) or not refs or not all(isinstance(v, str) and v for v in refs):
        raise CognitiveContractError("deterministic check requires id and evidence refs")
    inputs = spec.get("inputs")
    if not isinstance(inputs, Mapping):
        raise CognitiveContractError(f"deterministic check {check_id} inputs must be an object")
    if check_type == "EXACT_EQUAL":
        supported = inputs.get("left") == inputs.get("right")
    elif check_type == "TIMESTAMP_NOT_AFTER":
        from frankie_cognition import _parse_iso  # local import keeps the public surface small

        supported = _parse_iso(inputs.get("left"), f"{check_id}.left") <= _parse_iso(
            inputs.get("right"), f"{check_id}.right"
        )
    elif check_type == "NUMERIC_BETWEEN":
        value = inputs.get("value")
        lower = inputs.get("lower")
        upper = inputs.get("upper")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (value, lower, upper)):
            raise CognitiveContractError(f"deterministic check {check_id} requires numeric inputs")
        supported = float(lower) <= float(value) <= float(upper)
    elif check_type == "SET_CONTAINS":
        values = inputs.get("values")
        if not isinstance(values, list):
            raise CognitiveContractError(f"deterministic check {check_id} values must be a list")
        supported = inputs.get("item") in values
    else:
        raise CognitiveContractError(f"deterministic check type is not allowlisted: {check_type}")
    core = {
        "check_id": check_id,
        "check_type": check_type,
        "evidence_refs": tuple(dict.fromkeys(refs)),
        "inputs": dict(inputs),
        "status": "SUPPORTED" if supported else "CONTRADICTED",
        "execution_authority": "NONE",
        "revision_authority": "DISPOSABLE_CANDIDATE_ONLY",
    }
    return {**core, "check_hash": sha256_json(core)}


MEMORY_COMPETENCIES = {
    "ACCURATE_RETRIEVAL",
    "TEST_TIME_LEARNING",
    "LONG_RANGE_UNDERSTANDING",
    "SELECTIVE_FORGETTING",
}


def score_memory_competencies(
    rows: Sequence[Mapping[str, Any]],
    *,
    minimum_rate: float = 1.0,
) -> dict[str, Any]:
    """Score all four memory competencies separately and fail closed on provenance/staleness."""
    if isinstance(minimum_rate, bool) or not isinstance(minimum_rate, (int, float)):
        raise CognitiveContractError("memory minimum_rate must be numeric")
    minimum_rate = float(minimum_rate)
    if not math.isfinite(minimum_rate) or not 0.0 <= minimum_rate <= 1.0:
        raise CognitiveContractError("memory minimum_rate must be within [0, 1]")
    totals = {name: 0 for name in MEMORY_COMPETENCIES}
    passed = {name: 0 for name in MEMORY_COMPETENCIES}
    provenance_failures = 0
    obsolete_uses = 0
    seen: set[str] = set()
    for row in rows:
        case_id = str(row.get("case_id") or "").strip()
        if not case_id or case_id in seen:
            raise CognitiveContractError("memory cases require unique non-empty ids")
        seen.add(case_id)
        competency = str(row.get("competency") or "").strip().upper()
        if competency not in MEMORY_COMPETENCIES:
            raise CognitiveContractError(f"memory case {case_id} has invalid competency")
        if not isinstance(row.get("passed"), bool) or not isinstance(row.get("provenance_ok"), bool):
            raise CognitiveContractError(f"memory case {case_id} requires boolean results")
        totals[competency] += 1
        passed[competency] += int(row["passed"])
        provenance_failures += int(not row["provenance_ok"])
        obsolete_uses += int(bool(row.get("obsolete_memory_used", False)))
    missing = sorted(name for name, total in totals.items() if total == 0)
    if missing:
        raise CognitiveContractError(f"memory evaluation omitted competencies: {', '.join(missing)}")
    rates = {name: passed[name] / totals[name] for name in sorted(MEMORY_COMPETENCIES)}
    blockers = []
    if provenance_failures:
        blockers.append(f"{provenance_failures} provenance failures")
    if obsolete_uses:
        blockers.append(f"{obsolete_uses} obsolete-memory uses")
    below_minimum = sorted(name for name, rate in rates.items() if rate < minimum_rate)
    if below_minimum:
        blockers.append(
            "competencies below minimum rate: " + ", ".join(below_minimum)
        )
    core = {
        "rates": rates,
        "counts": {name: totals[name] for name in sorted(MEMORY_COMPETENCIES)},
        "minimum_rate": minimum_rate,
        "provenance_failures": provenance_failures,
        "obsolete_memory_uses": obsolete_uses,
        "verdict": "COMPONENT_GATE_PASSED" if not blockers else "REJECT",
        "blockers": blockers,
        "promotion_authority": "NONE",
    }
    return {**core, "scorecard_hash": sha256_json(core)}


def rank_associative_memory(
    *,
    node_ids: Sequence[str],
    edges: Sequence[Mapping[str, Any]],
    seed_ids: Sequence[str],
    active_ids: set[str],
    top_k: int = 8,
    damping: float = 0.85,
    iterations: int = 30,
) -> dict[str, Any]:
    """Deterministic Personalized-PageRank retrieval over active memory nodes."""
    nodes = tuple(dict.fromkeys(str(node) for node in node_ids))
    if not nodes or len(nodes) != len(node_ids):
        raise CognitiveContractError("associative memory graph requires unique nodes")
    if not 1 <= top_k <= len(nodes) or not 0.0 < damping < 1.0 or not 1 <= iterations <= 200:
        raise CognitiveContractError("invalid associative retrieval bounds")
    unknown_active = active_ids - set(nodes)
    seeds = tuple(dict.fromkeys(str(seed) for seed in seed_ids))
    if unknown_active or not seeds or set(seeds) - active_ids:
        raise CognitiveContractError("associative retrieval seeds and active ids must be known and active")
    outgoing: dict[str, list[tuple[str, float]]] = {node: [] for node in active_ids}
    inactive_edges: list[dict[str, Any]] = []
    known_nodes = set(nodes)
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        weight_raw = edge.get("weight", 1.0)
        if source not in known_nodes or target not in known_nodes:
            raise CognitiveContractError(
                f"associative edge cites unknown endpoint: {source}->{target}"
            )
        if source not in active_ids or target not in active_ids:
            inactive_edges.append({"source": source, "target": target})
            continue
        if isinstance(weight_raw, bool) or not isinstance(weight_raw, (int, float)):
            raise CognitiveContractError("associative edge weight must be numeric")
        weight = float(weight_raw)
        if not math.isfinite(weight) or weight <= 0:
            raise CognitiveContractError("associative edge weight must be finite and positive")
        outgoing[source].append((target, weight))
    teleport = {node: (1.0 / len(seeds) if node in seeds else 0.0) for node in active_ids}
    scores = dict(teleport)
    for _ in range(iterations):
        next_scores = {node: (1.0 - damping) * teleport[node] for node in active_ids}
        dangling = sum(scores[node] for node, links in outgoing.items() if not links)
        for node in active_ids:
            next_scores[node] += damping * dangling * teleport[node]
        for source, links in outgoing.items():
            total_weight = sum(weight for _, weight in links)
            for target, weight in links:
                next_scores[target] += damping * scores[source] * weight / total_weight
        scores = next_scores
    ranked = sorted(active_ids, key=lambda node: (-scores[node], node))[:top_k]
    core = {
        "ranked_ids": ranked,
        "scores": {node: scores[node] for node in ranked},
        "active_only": True,
        "inactive_edges_excluded": inactive_edges,
        "graph_hash": sha256_json({
            "node_ids": nodes,
            "edges": [dict(edge) for edge in edges],
            "active_ids": sorted(active_ids),
            "seed_ids": seeds,
        }),
        "causal_claim": False,
        "iterations": iterations,
    }
    return {**core, "retrieval_hash": sha256_json(core)}
