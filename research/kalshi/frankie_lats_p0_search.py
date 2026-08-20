#!/usr/bin/env python3
"""Bounded, callback-injected SHADOW LATS/MCTS plumbing for Frankie.

This module implements the *shape* of the defining Language Agent Tree Search
loop: deterministic tree selection, candidate expansion, read-only environment
feedback, heuristic value evaluation, reflection, and backpropagation.  It does
not reproduce the paper's prompts, language-model policy, benchmark
environments, learned value function, or published evaluation.  All callbacks
are caller-isolated and caller-attested side-effect-free; every result is
disposable and has no apply, promotion, execution, or trading authority.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import math
import re
from typing import Any, Callable, Mapping, Sequence

from frankie_cognition import CognitiveContractError, sha256_json
from frankie_cognitive_p0_loops import BudgetVector, CallbackResult, RESOURCE_DIMENSIONS


VERSION = "FRANKIE_LATS_P0_SEARCH_V1_PROVISIONAL"
MODES = {"TREE", "ONE_PATH_CONTROL"}
SIMULATION_STATUSES = {"SUPPORTED", "CONTRADICTED", "INCONCLUSIVE"}
MAX_ARTIFACT_BYTES = 1_000_000
SHA256_RE = re.compile(r"[0-9a-f]{64}")
FORBIDDEN_UNREVEALED_KEYS = {
    "future_outcome",
    "ground_truth",
    "protected_label",
    "unrevealed_label",
    "unrevealed_outcome",
}
CALLBACK_STAGES = {"lats.expand", "lats.simulate", "lats.value", "lats.reflect"}
ALL_STAGES = CALLBACK_STAGES | {"lats.select", "lats.prune", "lats.backprop"}

IMPLEMENTATION_AUDIT = {
    "classification": "BOUNDED_DEFINING_SEARCH_LOOP_PLUMBING",
    "paper_mechanisms_represented": [
        "tree selection",
        "candidate expansion",
        "environment simulation and feedback",
        "heuristic value evaluation",
        "reflection",
        "backpropagation",
        "multiple live hypotheses",
    ],
    "frankie_added_gates": [
        "fixed depth, width, and iteration bounds",
        "six-dimensional matched-budget receipts",
        "deterministic seed and tie ordering",
        "hash-bound immutable disposable artifacts",
        "ancestry-closure and pruned-node exclusion",
        "cutoff-bound exact feedback refs",
        "callback input-mutation detection and side-effect-free attestation",
        "fault-injection and removal receipts",
        "one-path matched-budget control contract",
    ],
    "not_implemented": [
        "paper prompts or benchmark environment replication",
        "paper language-model generation policy",
        "learned or paper-identical value function",
        "paper hyperparameters and published performance reproduction",
        "automatic standard group-runner integration",
    ],
}


class LATSContractError(CognitiveContractError):
    """Invalid bounded LATS input or evidence contract."""


class _Stop(RuntimeError):
    pass


Callback = Callable[[Mapping[str, Any]], CallbackResult]


def _clone(value: Any, label: str) -> Any:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        if len(encoded.encode("utf-8")) > MAX_ARTIFACT_BYTES:
            raise LATSContractError(f"{label} exceeds the artifact byte limit")
        return json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise LATSContractError(f"{label} must be finite JSON data") from exc


def _text(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise _Stop(f"{label} must be non-empty")
    return result


def _strings(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, (list, tuple)) or isinstance(value, (str, bytes)):
        raise _Stop(f"{label} must be a string sequence")
    result = list(dict.fromkeys(str(item).strip() for item in value))
    if any(not item for item in result) or (not result and not allow_empty):
        raise _Stop(f"{label} must contain non-empty strings")
    return result


def _parse_time(value: Any, label: str) -> dt.datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise LATSContractError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise LATSContractError(f"{label} must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _reject_unknown_keys(raw: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise _Stop(f"{label} contains forbidden or unknown keys: {', '.join(unknown)}")


def _reject_unrevealed_keys(value: Any, label: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).strip().lower() in FORBIDDEN_UNREVEALED_KEYS:
                raise LATSContractError(f"{label} contains forbidden unrevealed outcome material")
            _reject_unrevealed_keys(child, label)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_unrevealed_keys(child, label)


def _normalize_feedback_catalog(
    feedback_catalog: Sequence[Mapping[str, Any]],
    cutoff_at: dt.datetime,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], set[str]]:
    if not isinstance(feedback_catalog, (list, tuple)) or isinstance(feedback_catalog, (str, bytes)):
        raise LATSContractError("feedback_catalog must be a sequence")
    normalized: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    permitted: set[str] = set()
    allowed_keys = {
        "ref_id", "payload", "source_hash", "observed_at", "reveal_at", "immutable", "status"
    }
    for index, raw in enumerate(feedback_catalog):
        if not isinstance(raw, Mapping):
            raise LATSContractError(f"feedback_catalog row {index} must be an object")
        unknown = sorted(set(raw) - allowed_keys)
        if unknown:
            raise LATSContractError(
                f"feedback_catalog row {index} contains forbidden or unknown keys: {', '.join(unknown)}"
            )
        ref_id = str(raw.get("ref_id") or "").strip()
        if not ref_id or ref_id in by_id:
            raise LATSContractError(f"feedback_catalog row {index} has an invalid or duplicate ref_id")
        payload = _clone(raw.get("payload"), f"feedback {ref_id} payload")
        source_hash = str(raw.get("source_hash") or "").strip()
        if not SHA256_RE.fullmatch(source_hash) or source_hash != sha256_json(payload):
            raise LATSContractError(f"feedback {ref_id} source hash mismatch")
        observed = _parse_time(raw.get("observed_at"), f"feedback {ref_id} observed_at")
        revealed = _parse_time(raw.get("reveal_at", raw.get("observed_at")), f"feedback {ref_id} reveal_at")
        if observed > revealed:
            raise LATSContractError(f"feedback {ref_id} is revealed before it is observed")
        if raw.get("immutable") is not True or str(raw.get("status") or "").upper() != "ACTIVE":
            raise LATSContractError(f"feedback {ref_id} must be active and immutable")
        row = {
            "ref_id": ref_id,
            "payload": payload,
            "source_hash": source_hash,
            "observed_at": _iso(observed),
            "reveal_at": _iso(revealed),
            "immutable": True,
            "status": "ACTIVE",
        }
        normalized.append(row)
        by_id[ref_id] = row
        if observed <= cutoff_at and revealed <= cutoff_at:
            permitted.add(ref_id)
    normalized.sort(key=lambda row: row["ref_id"])
    return normalized, by_id, permitted


class _Session:
    def __init__(
        self,
        baseline_budget: Mapping[str, Any],
        *,
        budget_tolerance: float,
        faults: Sequence[str],
    ) -> None:
        self.baseline = BudgetVector.from_mapping(baseline_budget, "baseline_budget")
        if isinstance(budget_tolerance, bool) or not isinstance(budget_tolerance, (int, float)):
            raise LATSContractError("budget_tolerance must be numeric")
        self.tolerance = float(budget_tolerance)
        if not 0.0 <= self.tolerance <= 0.10:
            raise LATSContractError("budget_tolerance must be within [0, 0.10]")
        if not isinstance(faults, (list, tuple)) or isinstance(faults, (str, bytes)):
            raise LATSContractError("faults must be a sequence")
        parsed_faults: set[str] = set()
        for fault in faults:
            text = str(fault or "").strip()
            match = re.fullmatch(r"(lats\.[a-z]+)(?::([1-9][0-9]*))?", text)
            if not match or match.group(1) not in ALL_STAGES:
                raise LATSContractError(f"unknown fault stage: {text}")
            parsed_faults.add(text)
        self.faults = frozenset(parsed_faults)
        self.usage = BudgetVector()
        self.stage_counts: dict[str, int] = {}
        self.events: list[dict[str, Any]] = []
        self.artifacts: list[dict[str, Any]] = []

    def _before(self, stage: str) -> int:
        ordinal = self.stage_counts.get(stage, 0) + 1
        self.stage_counts[stage] = ordinal
        if stage in self.faults or f"{stage}:{ordinal}" in self.faults:
            self.events.append({"stage": stage, "ordinal": ordinal, "event": "FAULT_INJECTED"})
            raise _Stop(f"fault injected at {stage}:{ordinal}")
        return ordinal

    def _freeze(self, stage: str, ordinal: int, payload: Mapping[str, Any]) -> dict[str, Any]:
        frozen = _clone(dict(payload), f"{stage} payload")
        core = {"stage": stage, "ordinal": ordinal, "payload": frozen}
        artifact = {**core, "artifact_hash": sha256_json(core), "immutable": True}
        self.artifacts.append(artifact)
        return artifact

    def _add_usage(self, usage: BudgetVector) -> None:
        self.usage = self.usage.plus(usage)
        exceeded = [
            name
            for name in RESOURCE_DIMENSIONS
            if getattr(self.usage, name)
            > getattr(self.baseline, name) * (1.0 + self.tolerance) + 1e-9
        ]
        if exceeded:
            raise _Stop("matched budget exceeded: " + ", ".join(exceeded))

    def local(self, stage: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        ordinal = self._before(stage)
        artifact = self._freeze(stage, ordinal, payload)
        self.events.append({
            "stage": stage,
            "ordinal": ordinal,
            "event": "LOCAL_ARTIFACT",
            "artifact_hash": artifact["artifact_hash"],
        })
        return artifact

    def call(
        self,
        stage: str,
        callback: Callback,
        request: Mapping[str, Any],
        normalizer: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        *,
        minimum_usage: Mapping[str, float],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        ordinal = self._before(stage)
        callback_input = _clone(dict(request), f"{stage} request")
        before_hash = sha256_json(callback_input)
        try:
            result = callback(callback_input)
        except Exception as exc:
            self.events.append({
                "stage": stage,
                "ordinal": ordinal,
                "event": "CALLBACK_ERROR",
                "error_type": type(exc).__name__,
            })
            raise _Stop(f"callback failed at {stage}:{ordinal}") from exc
        if sha256_json(callback_input) != before_hash:
            self.events.append({"stage": stage, "ordinal": ordinal, "event": "CALLBACK_INPUT_MUTATED"})
            raise _Stop(f"callback mutated its input at {stage}:{ordinal}")
        if not isinstance(result, CallbackResult):
            raise _Stop(f"callback at {stage}:{ordinal} returned the wrong type")
        if result.side_effect_free is not True:
            raise _Stop(f"callback at {stage}:{ordinal} did not attest side_effect_free=True")
        if not isinstance(result.usage, BudgetVector):
            raise _Stop(f"callback at {stage}:{ordinal} returned invalid usage metering")
        short = [
            name
            for name, floor in minimum_usage.items()
            if getattr(result.usage, name) + 1e-9 < float(floor)
        ]
        if short:
            raise _Stop(
                f"callback under-reported required usage at {stage}:{ordinal}: {', '.join(short)}"
            )
        try:
            normalized = dict(normalizer(result.payload))
        except _Stop:
            raise
        except Exception as exc:
            raise _Stop(f"invalid callback payload at {stage}:{ordinal}: {exc}") from exc
        artifact = self._freeze(stage, ordinal, normalized)
        self._add_usage(result.usage)
        self.events.append({
            "stage": stage,
            "ordinal": ordinal,
            "event": "CALLBACK_ACCEPTED",
            "artifact_hash": artifact["artifact_hash"],
            "request_hash": before_hash,
            "usage_hash": sha256_json(result.usage.as_dict()),
            "side_effect_free_attested": True,
        })
        return copy.deepcopy(normalized), artifact

    def finish(
        self,
        status: str,
        reason: str,
        *,
        result: Mapping[str, Any],
        live_node_ids: Sequence[str],
        pruned_hashes: Sequence[str],
    ) -> dict[str, Any]:
        limits = {
            name: getattr(self.baseline, name) * (1.0 + self.tolerance)
            for name in RESOURCE_DIMENSIONS
        }
        within = all(getattr(self.usage, name) <= limits[name] + 1e-9 for name in limits)
        budget_core = {
            "baseline": self.baseline.as_dict(),
            "candidate": self.usage.as_dict(),
            "tolerance": self.tolerance,
            "limits": limits,
            "within_matched_budget": within,
        }
        artifact_hashes = [artifact["artifact_hash"] for artifact in self.artifacts]
        removal_core = {
            "method": "DROP_DISPOSABLE_TREE_AND_CALLBACK_ARTIFACTS",
            "artifact_hashes": artifact_hashes,
            "live_node_ids": sorted(live_node_ids),
            "pruned_candidate_hashes": sorted(pruned_hashes),
            "canonical_state_changed": False,
            "external_callback_side_effects": "NOT_VERIFIABLE; CALLER MUST ISOLATE CALLBACKS",
        }
        core = {
            "version": VERSION,
            "status": status if within else "REJECTED",
            "reason": reason if within else "matched budget exceeded",
            "implementation_audit": IMPLEMENTATION_AUDIT,
            "paper_faithful": False,
            "performance_evidence": False,
            "execution_enabled": False,
            "automatic_apply": False,
            "promotion_authority": "NONE",
            "trading_authority": "NONE",
            "canonical_mutation": False,
            "callback_contract": "INJECTED_CALLER_ISOLATED_AND_ATTESTED_SIDE_EFFECT_FREE",
            "fault_plan": sorted(self.faults),
            "events": self.events,
            "artifacts": self.artifacts,
            "artifact_chain_hash": sha256_json(artifact_hashes),
            "matched_budget": {**budget_core, "budget_hash": sha256_json(budget_core)},
            "removal": {**removal_core, "removal_receipt_hash": sha256_json(removal_core)},
            "result": _clone(dict(result), "LATS result"),
        }
        return {**core, "result_hash": sha256_json(core)}


def _candidate_normalizer(
    raw: Mapping[str, Any],
    *,
    parent_id: str,
    permitted_refs: set[str],
    reflection_lineage: list[str],
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise _Stop("expansion payload must be an object")
    _reject_unknown_keys(raw, {"source_parent_id", "candidates"}, "expansion payload")
    if str(raw.get("source_parent_id") or "") != parent_id:
        raise _Stop("expansion payload has an orphan or wrong source_parent_id")
    candidates = raw.get("candidates")
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 32:
        raise _Stop("expansion requires between 1 and 32 candidates")
    normalized: list[dict[str, Any]] = []
    ids: set[str] = set()
    allowed = {
        "candidate_id", "hypothesis", "action", "planned_feedback_refs", "used_reflection_hashes"
    }
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            raise _Stop(f"candidate {index} must be an object")
        _reject_unknown_keys(candidate, allowed, f"candidate {index}")
        candidate_id = _text(candidate.get("candidate_id"), f"candidate {index} candidate_id")
        if candidate_id in ids:
            raise _Stop(f"duplicate candidate_id in expansion: {candidate_id}")
        ids.add(candidate_id)
        hypothesis = _text(candidate.get("hypothesis"), f"candidate {candidate_id} hypothesis")
        action = candidate.get("action")
        if not isinstance(action, Mapping) or not action:
            raise _Stop(f"candidate {candidate_id} action must be a non-empty object")
        _reject_unrevealed_keys(action, f"candidate {candidate_id} action")
        planned_refs = _strings(
            candidate.get("planned_feedback_refs"),
            f"candidate {candidate_id} planned_feedback_refs",
        )
        if set(planned_refs) - permitted_refs:
            raise _Stop(f"candidate {candidate_id} planned unavailable or unrevealed feedback")
        used_reflections = _strings(
            candidate.get("used_reflection_hashes", []),
            f"candidate {candidate_id} used_reflection_hashes",
            allow_empty=True,
        )
        if used_reflections != reflection_lineage:
            raise _Stop(f"candidate {candidate_id} reflection lineage mismatch")
        normalized.append({
            "candidate_id": candidate_id,
            "hypothesis": hypothesis,
            "action": _clone(dict(action), f"candidate {candidate_id} action"),
            "planned_feedback_refs": sorted(planned_refs),
            "used_reflection_hashes": list(used_reflections),
        })
    normalized.sort(key=lambda row: row["candidate_id"])
    return {"source_parent_id": parent_id, "candidates": normalized}


def _simulation_normalizer(
    raw: Mapping[str, Any],
    *,
    planned_refs: set[str],
    feedback_by_id: Mapping[str, Mapping[str, Any]],
    permitted_refs: set[str],
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise _Stop("simulation payload must be an object")
    allowed = {"read_only", "feedback_refs", "simulation_status", "terminal", "uses_unrevealed_outcome"}
    _reject_unknown_keys(raw, allowed, "simulation payload")
    if raw.get("read_only") is not True:
        raise _Stop("environment simulation must attest read_only=True")
    if raw.get("uses_unrevealed_outcome") is not False:
        raise _Stop("environment simulation must attest uses_unrevealed_outcome=False")
    refs = _strings(raw.get("feedback_refs"), "simulation feedback_refs")
    if set(refs) - permitted_refs:
        raise _Stop("simulation cited forbidden or unrevealed feedback")
    if set(refs) - planned_refs:
        raise _Stop("simulation cited feedback outside the candidate evidence plan")
    status = str(raw.get("simulation_status") or "").strip().upper()
    if status not in SIMULATION_STATUSES:
        raise _Stop("simulation_status is invalid")
    if not isinstance(raw.get("terminal"), bool):
        raise _Stop("simulation terminal must be boolean")
    materialized = [_clone(feedback_by_id[ref_id], f"feedback {ref_id}") for ref_id in sorted(refs)]
    return {
        "read_only": True,
        "feedback_refs": sorted(refs),
        "feedback": materialized,
        "simulation_status": status,
        "terminal": raw["terminal"],
        "uses_unrevealed_outcome": False,
    }


def _value_normalizer(raw: Mapping[str, Any], *, feedback_refs: set[str]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise _Stop("value payload must be an object")
    _reject_unknown_keys(raw, {"value", "reason", "feedback_refs"}, "value payload")
    value = raw.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _Stop("value must be numeric")
    value = float(value)
    if not math.isfinite(value) or not -1.0 <= value <= 1.0:
        raise _Stop("value must be finite and within [-1, 1]")
    refs = _strings(raw.get("feedback_refs"), "value feedback_refs")
    if set(refs) - feedback_refs:
        raise _Stop("value cited feedback outside its simulation")
    return {
        "value": value,
        "reason": _text(raw.get("reason"), "value reason"),
        "feedback_refs": sorted(refs),
        "value_semantics": "SEARCH_HEURISTIC_NOT_PROBABILITY_OR_PROMOTION_VOTE",
    }


def _reflection_normalizer(
    raw: Mapping[str, Any],
    *,
    node_id: str,
    feedback_refs: set[str],
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise _Stop("reflection payload must be an object")
    allowed = {"source_node_id", "reflection", "feedback_refs", "next_constraints"}
    _reject_unknown_keys(raw, allowed, "reflection payload")
    if str(raw.get("source_node_id") or "") != node_id:
        raise _Stop("reflection source_node_id does not match its lineage")
    refs = _strings(raw.get("feedback_refs"), "reflection feedback_refs")
    if set(refs) - feedback_refs:
        raise _Stop("reflection cited feedback outside its simulation")
    constraints = _strings(raw.get("next_constraints", []), "reflection next_constraints", allow_empty=True)
    return {
        "source_node_id": node_id,
        "reflection": _text(raw.get("reflection"), "reflection text"),
        "feedback_refs": sorted(refs),
        "next_constraints": constraints,
    }


def _path(nodes: Mapping[str, Mapping[str, Any]], node_id: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    current: str | None = node_id
    while current is not None:
        if current in seen or current not in nodes:
            raise _Stop("tree ancestry is cyclic or orphaned")
        seen.add(current)
        result.append(current)
        parent = nodes[current]["parent_id"]
        current = str(parent) if parent is not None else None
    return list(reversed(result))


def _snapshot_nodes(nodes: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for node_id in sorted(nodes):
        node = nodes[node_id]
        core = {
            "node_id": node_id,
            "parent_id": node["parent_id"],
            "depth": node["depth"],
            "candidate_id": node["candidate_id"],
            "hypothesis": node["hypothesis"],
            "action": node["action"],
            "planned_feedback_refs": node["planned_feedback_refs"],
            "feedback_refs": node["feedback_refs"],
            "simulation_status": node["simulation_status"],
            "terminal": node["terminal"],
            "own_value": node["own_value"],
            "visits": node["visits"],
            "value_sum": node["value_sum"],
            "mean_value": node["value_sum"] / node["visits"] if node["visits"] else 0.0,
            "expanded": node["expanded"],
            "children": sorted(node["children"]),
            "reflection_artifact_hash": node["reflection_artifact_hash"],
            "reflection_lineage": node["reflection_lineage"],
            "creation_artifact_hash": node["creation_artifact_hash"],
        }
        snapshots.append({**_clone(core, f"node {node_id}"), "node_hash": sha256_json(core)})
    return snapshots


def _ancestry_audit(nodes: Mapping[str, Mapping[str, Any]], pruned_node_ids: set[str]) -> dict[str, Any]:
    errors: list[str] = []
    for node_id, node in nodes.items():
        if node_id in pruned_node_ids:
            errors.append(f"pruned node survived: {node_id}")
        parent_id = node["parent_id"]
        if parent_id is None:
            if node["depth"] != 0:
                errors.append(f"root-depth mismatch: {node_id}")
        elif parent_id not in nodes:
            errors.append(f"orphan: {node_id}")
        elif node["depth"] != nodes[parent_id]["depth"] + 1:
            errors.append(f"depth mismatch: {node_id}")
        try:
            _path(nodes, node_id)
        except _Stop as exc:
            errors.append(f"{node_id}: {exc}")
    return {
        "ancestry_closed": not errors,
        "errors": errors,
        "live_node_count": len(nodes),
        "pruned_node_count": len(pruned_node_ids),
    }


def run_bounded_lats_search(
    initial_state: Mapping[str, Any],
    feedback_catalog: Sequence[Mapping[str, Any]],
    *,
    cutoff_at: str,
    expand_fn: Callback,
    simulate_fn: Callback,
    value_fn: Callback,
    reflect_fn: Callback,
    baseline_budget: Mapping[str, Any],
    max_depth: int = 3,
    max_width: int = 3,
    iterations: int = 3,
    seed: int = 0,
    exploration_constant: float = 1.0,
    mode: str = "TREE",
    budget_tolerance: float = 0.02,
    faults: Sequence[str] = (),
) -> dict[str, Any]:
    """Execute a bounded SHADOW LATS skeleton or its one-path control.

    ``mode="TREE"`` keeps up to ``max_width`` children per expansion and
    requires at least two live root hypotheses.  ``mode="ONE_PATH_CONTROL"``
    uses the same declared width/depth/iteration contract but deterministically
    retains only one child at every expansion.  Use
    :func:`compare_tree_to_one_path_control` to enforce matched control budgets.
    """
    if not isinstance(initial_state, Mapping):
        raise LATSContractError("initial_state must be an object")
    state = _clone(dict(initial_state), "initial_state")
    _reject_unrevealed_keys(state, "initial_state")
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or not 1 <= max_depth <= 8:
        raise LATSContractError("max_depth must be within [1, 8]")
    if isinstance(max_width, bool) or not isinstance(max_width, int) or not 2 <= max_width <= 8:
        raise LATSContractError("max_width must be within [2, 8]")
    if isinstance(iterations, bool) or not isinstance(iterations, int) or not 1 <= iterations <= 32:
        raise LATSContractError("iterations must be within [1, 32]")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1:
        raise LATSContractError("seed must be an unsigned 32-bit integer")
    if isinstance(exploration_constant, bool) or not isinstance(exploration_constant, (int, float)):
        raise LATSContractError("exploration_constant must be numeric")
    exploration_constant = float(exploration_constant)
    if not math.isfinite(exploration_constant) or not 0.0 <= exploration_constant <= 4.0:
        raise LATSContractError("exploration_constant must be finite and within [0, 4]")
    mode = str(mode or "").strip().upper()
    if mode not in MODES:
        raise LATSContractError(f"mode must be one of {sorted(MODES)}")
    if not all(callable(callback) for callback in (expand_fn, simulate_fn, value_fn, reflect_fn)):
        raise LATSContractError("all LATS callbacks must be callable")

    cutoff = _parse_time(cutoff_at, "cutoff_at")
    catalog, feedback_by_id, permitted_refs = _normalize_feedback_catalog(feedback_catalog, cutoff)
    session = _Session(baseline_budget, budget_tolerance=budget_tolerance, faults=faults)
    problem_hash = sha256_json(state)
    catalog_hash = sha256_json(catalog)
    root_core = {"problem_hash": problem_hash, "catalog_hash": catalog_hash, "seed": seed}
    root_id = "root-" + sha256_json(root_core)[:24]
    root_hypothesis = str(
        state.get("question") or state.get("problem") or state.get("objective") or "ROOT"
    ).strip() or "ROOT"
    nodes: dict[str, dict[str, Any]] = {
        root_id: {
            "node_id": root_id,
            "parent_id": None,
            "depth": 0,
            "candidate_id": "ROOT",
            "hypothesis": root_hypothesis,
            "action": {"kind": "ROOT"},
            "planned_feedback_refs": [],
            "feedback_refs": [],
            "simulation_status": "INCONCLUSIVE",
            "terminal": False,
            "own_value": 0.0,
            "visits": 0,
            "value_sum": 0.0,
            "expanded": False,
            "children": [],
            "reflection_artifact_hash": None,
            "reflection_lineage": [],
            "creation_artifact_hash": None,
        }
    }
    all_candidate_ids: set[str] = set()
    pruned_hashes: list[str] = []
    pruned_node_ids: set[str] = set()
    completed_iterations = 0

    settings = {
        "max_depth": max_depth,
        "max_width": max_width,
        "iterations": iterations,
        "seed": seed,
        "exploration_constant": exploration_constant,
        "cutoff_at": _iso(cutoff),
        "problem_hash": problem_hash,
        "feedback_catalog_hash": catalog_hash,
    }
    replay_key = {**settings, "mode": mode}

    def finish(status: str, reason: str, best_node_id: str | None = None) -> dict[str, Any]:
        snapshots = _snapshot_nodes(nodes)
        ancestry = _ancestry_audit(nodes, pruned_node_ids)
        if status == "COMPLETED" and not ancestry["ancestry_closed"]:
            status = "REJECTED"
            reason = "final tree failed ancestry closure"
        best_path = _path(nodes, best_node_id) if best_node_id is not None and best_node_id in nodes else []
        projection_core = {
            "replay_key": replay_key,
            "completed_iterations": completed_iterations,
            "nodes": snapshots,
            "best_node_id": best_node_id,
            "best_path": best_path,
            "pruned_candidate_hashes": sorted(pruned_hashes),
            "ancestry_audit": ancestry,
        }
        result = {
            "mode": mode,
            "settings": settings,
            "effective_width": max_width if mode == "TREE" else 1,
            "completed_iterations": completed_iterations,
            "nodes": snapshots,
            "best_node_id": best_node_id,
            "best_path": best_path,
            "live_hypotheses": sorted(
                node["hypothesis"] for node in nodes.values() if node["parent_id"] is not None
            ),
            "pruned_candidate_hashes": sorted(pruned_hashes),
            "ancestry_audit": ancestry,
            "feedback_cutoff_receipt": {
                "cutoff_at": _iso(cutoff),
                "catalog_hash": catalog_hash,
                "permitted_ref_ids": sorted(permitted_refs),
                "withheld_ref_ids": sorted(set(feedback_by_id) - permitted_refs),
                "unrevealed_payloads_exposed": False,
            },
            "replay_key_hash": sha256_json(replay_key),
            "comparison_key_hash": sha256_json(settings),
            "determinism_projection_hash": sha256_json(projection_core),
            "value_semantics": "SEARCH_HEURISTIC_NOT_PROBABILITY_OR_PROMOTION_VOTE",
        }
        return session.finish(
            status,
            reason,
            result=result,
            live_node_ids=nodes,
            pruned_hashes=pruned_hashes,
        )

    try:
        for iteration in range(1, iterations + 1):
            frontier = [
                node
                for node in nodes.values()
                if not node["expanded"] and not node["terminal"] and node["depth"] < max_depth
            ]
            if not frontier:
                raise _Stop("fixed iteration contract exhausted the expandable frontier")

            ranked: list[tuple[float, str, str]] = []
            for node in frontier:
                if node["parent_id"] is None:
                    score = 0.0
                else:
                    parent = nodes[node["parent_id"]]
                    mean = node["value_sum"] / node["visits"] if node["visits"] else 0.0
                    score = mean + exploration_constant * math.sqrt(
                        math.log(max(1, parent["visits"]) + 1.0) / max(1, node["visits"])
                    )
                tie_key = sha256_json({"seed": seed, "node_id": node["node_id"]})
                ranked.append((score, tie_key, node["node_id"]))
            ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
            selected_id = ranked[0][2]
            selected = nodes[selected_id]
            selection_artifact = session.local("lats.select", {
                "iteration": iteration,
                "frontier": [
                    {"node_id": node_id, "selection_score": score, "tie_key": tie_key}
                    for score, tie_key, node_id in ranked
                ],
                "selected_node_id": selected_id,
                "selected_path": _path(nodes, selected_id),
                "seed": seed,
            })

            path_ids = _path(nodes, selected_id)
            expansion_request = {
                "iteration": iteration,
                "mode": mode,
                "seed": seed,
                "parent": _snapshot_nodes({selected_id: selected})[0],
                "path_node_ids": path_ids,
                "path_hypotheses": [nodes[node_id]["hypothesis"] for node_id in path_ids],
                "reflection_lineage": list(selected["reflection_lineage"]),
                "allowed_feedback_ref_ids": sorted(permitted_refs),
                "max_children": max_width if mode == "TREE" else 1,
            }
            expansion, expansion_artifact = session.call(
                "lats.expand",
                expand_fn,
                expansion_request,
                lambda raw: _candidate_normalizer(
                    raw,
                    parent_id=selected_id,
                    permitted_refs=permitted_refs,
                    reflection_lineage=list(selected["reflection_lineage"]),
                ),
                minimum_usage={"model_calls": 1.0},
            )
            generated = expansion["candidates"]
            duplicate_global = sorted(
                candidate["candidate_id"]
                for candidate in generated
                if candidate["candidate_id"] in all_candidate_ids
            )
            if duplicate_global:
                raise _Stop("candidate ids were reused across expansions: " + ", ".join(duplicate_global))
            all_candidate_ids.update(candidate["candidate_id"] for candidate in generated)

            ranked_candidates = sorted(
                generated,
                key=lambda candidate: (
                    sha256_json({
                        "seed": seed,
                        "parent_id": selected_id,
                        "candidate_id": candidate["candidate_id"],
                    }),
                    candidate["candidate_id"],
                ),
            )
            keep_count = max_width if mode == "TREE" else 1
            kept = ranked_candidates[:keep_count]
            pruned = ranked_candidates[keep_count:]
            if mode == "TREE" and selected["parent_id"] is None and len(kept) < 2:
                raise _Stop("TREE mode must preserve at least two distinct root hypotheses")
            if pruned:
                prune_payload = {
                    "iteration": iteration,
                    "parent_id": selected_id,
                    "reason": "FIXED_WIDTH_OR_ONE_PATH_CONTROL",
                    "candidates": pruned,
                }
                prune_artifact = session.local("lats.prune", prune_payload)
                for candidate in pruned:
                    candidate_hash = sha256_json({
                        "parent_id": selected_id,
                        "candidate": candidate,
                        "prune_artifact_hash": prune_artifact["artifact_hash"],
                    })
                    pruned_hashes.append(candidate_hash)
                    pruned_node_ids.add("pruned-" + candidate_hash[:24])

            selected["expanded"] = True
            for candidate in kept:
                node_core = {
                    "parent_id": selected_id,
                    "candidate": candidate,
                    "problem_hash": problem_hash,
                    "catalog_hash": catalog_hash,
                    "seed": seed,
                }
                node_id = "node-" + sha256_json(node_core)[:24]
                if node_id in nodes:
                    raise _Stop("deterministic node id collision")
                node = {
                    "node_id": node_id,
                    "parent_id": selected_id,
                    "depth": selected["depth"] + 1,
                    "candidate_id": candidate["candidate_id"],
                    "hypothesis": candidate["hypothesis"],
                    "action": candidate["action"],
                    "planned_feedback_refs": candidate["planned_feedback_refs"],
                    "feedback_refs": [],
                    "simulation_status": "INCONCLUSIVE",
                    "terminal": False,
                    "own_value": 0.0,
                    "visits": 0,
                    "value_sum": 0.0,
                    "expanded": False,
                    "children": [],
                    "reflection_artifact_hash": None,
                    "reflection_lineage": list(selected["reflection_lineage"]),
                    "creation_artifact_hash": expansion_artifact["artifact_hash"],
                }
                nodes[node_id] = node
                selected["children"].append(node_id)

                available_feedback = [
                    feedback_by_id[ref_id] for ref_id in candidate["planned_feedback_refs"]
                ]
                simulation_request = {
                    "iteration": iteration,
                    "node_id": node_id,
                    "parent_id": selected_id,
                    "path_node_ids": _path(nodes, node_id),
                    "hypothesis": candidate["hypothesis"],
                    "action": candidate["action"],
                    "available_feedback": available_feedback,
                    "cutoff_at": _iso(cutoff),
                    "read_only_required": True,
                    "unrevealed_outcome_access": "FORBIDDEN",
                }
                simulation, simulation_artifact = session.call(
                    "lats.simulate",
                    simulate_fn,
                    simulation_request,
                    lambda raw, planned=set(candidate["planned_feedback_refs"]): _simulation_normalizer(
                        raw,
                        planned_refs=planned,
                        feedback_by_id=feedback_by_id,
                        permitted_refs=permitted_refs,
                    ),
                    minimum_usage={"tool_queries": 1.0},
                )
                node["feedback_refs"] = simulation["feedback_refs"]
                node["simulation_status"] = simulation["simulation_status"]
                node["terminal"] = simulation["terminal"] or node["depth"] >= max_depth

                value_request = {
                    "iteration": iteration,
                    "node_id": node_id,
                    "path_node_ids": _path(nodes, node_id),
                    "hypothesis": node["hypothesis"],
                    "simulation_artifact_hash": simulation_artifact["artifact_hash"],
                    "simulation": simulation,
                    "value_semantics": "SEARCH_HEURISTIC_NOT_PROBABILITY_OR_PROMOTION_VOTE",
                }
                value_result, value_artifact = session.call(
                    "lats.value",
                    value_fn,
                    value_request,
                    lambda raw, refs=set(simulation["feedback_refs"]): _value_normalizer(
                        raw, feedback_refs=refs
                    ),
                    minimum_usage={"model_calls": 1.0},
                )
                node["own_value"] = value_result["value"]

                reflection_request = {
                    "iteration": iteration,
                    "node_id": node_id,
                    "path_node_ids": _path(nodes, node_id),
                    "hypothesis": node["hypothesis"],
                    "simulation_artifact_hash": simulation_artifact["artifact_hash"],
                    "value_artifact_hash": value_artifact["artifact_hash"],
                    "simulation": simulation,
                    "value": value_result,
                    "prior_reflection_lineage": list(node["reflection_lineage"]),
                }
                reflection, reflection_artifact = session.call(
                    "lats.reflect",
                    reflect_fn,
                    reflection_request,
                    lambda raw, current=node_id, refs=set(simulation["feedback_refs"]): _reflection_normalizer(
                        raw, node_id=current, feedback_refs=refs
                    ),
                    minimum_usage={"model_calls": 1.0},
                )
                node["reflection_artifact_hash"] = reflection_artifact["artifact_hash"]
                node["reflection_lineage"].append(reflection_artifact["artifact_hash"])

                backprop_path = _path(nodes, node_id)
                before = {
                    path_id: {"visits": nodes[path_id]["visits"], "value_sum": nodes[path_id]["value_sum"]}
                    for path_id in backprop_path
                }
                for path_id in backprop_path:
                    nodes[path_id]["visits"] += 1
                    nodes[path_id]["value_sum"] += value_result["value"]
                after = {
                    path_id: {"visits": nodes[path_id]["visits"], "value_sum": nodes[path_id]["value_sum"]}
                    for path_id in backprop_path
                }
                session.local("lats.backprop", {
                    "iteration": iteration,
                    "source_node_id": node_id,
                    "path_node_ids": backprop_path,
                    "heuristic_value": value_result["value"],
                    "before": before,
                    "after": after,
                    "reflection_artifact_hash": reflection_artifact["artifact_hash"],
                    "selection_artifact_hash": selection_artifact["artifact_hash"],
                })
            completed_iterations = iteration

        candidates = [node for node in nodes.values() if node["parent_id"] is not None]
        candidates.sort(key=lambda node: (
            -(node["value_sum"] / node["visits"] if node["visits"] else -1.0),
            sha256_json({"seed": seed, "node_id": node["node_id"]}),
            node["node_id"],
        ))
        best_node_id = candidates[0]["node_id"] if candidates else None
        return finish("COMPLETED", "bounded SHADOW LATS loop completed", best_node_id)
    except _Stop as exc:
        return finish("REJECTED", str(exc), None)


def verify_lats_replay(first: Mapping[str, Any], second: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed when two same-key runs have nondeterministic normalized trees."""
    try:
        first_result = first["result"]
        second_result = second["result"]
        same_key = first_result["replay_key_hash"] == second_result["replay_key_hash"]
        same_projection = (
            first_result["determinism_projection_hash"]
            == second_result["determinism_projection_hash"]
        )
    except (KeyError, TypeError) as exc:
        raise LATSContractError("replay inputs are not LATS receipts") from exc
    if not same_key:
        raise LATSContractError("replay keys differ; determinism cannot be adjudicated")
    if not same_projection:
        raise LATSContractError("nondeterministic LATS replay detected")
    core = {
        "version": VERSION,
        "replay_key_hash": first_result["replay_key_hash"],
        "determinism_projection_hash": first_result["determinism_projection_hash"],
        "deterministic": True,
        "performance_evidence": False,
        "promotion_authority": "NONE",
    }
    return {**core, "replay_receipt_hash": sha256_json(core)}


def compare_tree_to_one_path_control(
    tree: Mapping[str, Any],
    control: Mapping[str, Any],
    *,
    actual_usage_tolerance: float = 0.02,
) -> dict[str, Any]:
    """Require identical search contract and matched six-dimensional resources."""
    if isinstance(actual_usage_tolerance, bool) or not isinstance(actual_usage_tolerance, (int, float)):
        raise LATSContractError("actual_usage_tolerance must be numeric")
    tolerance = float(actual_usage_tolerance)
    if not 0.0 <= tolerance <= 0.10:
        raise LATSContractError("actual_usage_tolerance must be within [0, 0.10]")
    try:
        if tree["status"] != "COMPLETED" or control["status"] != "COMPLETED":
            raise LATSContractError("tree and one-path control must both complete")
        if tree["result"]["mode"] != "TREE" or control["result"]["mode"] != "ONE_PATH_CONTROL":
            raise LATSContractError("comparison requires TREE and ONE_PATH_CONTROL arms")
        if tree["result"]["comparison_key_hash"] != control["result"]["comparison_key_hash"]:
            raise LATSContractError("tree and control search contracts differ")
        tree_budget = tree["matched_budget"]
        control_budget = control["matched_budget"]
    except (KeyError, TypeError) as exc:
        raise LATSContractError("comparison inputs are not LATS receipts") from exc
    for key in ("baseline", "tolerance", "limits"):
        if tree_budget[key] != control_budget[key]:
            raise LATSContractError("tree and control budget caps differ")
    deltas: dict[str, float] = {}
    violations: list[str] = []
    for name in RESOURCE_DIMENSIONS:
        left = float(tree_budget["candidate"][name])
        right = float(control_budget["candidate"][name])
        delta = abs(left - right)
        deltas[name] = delta
        allowed = float(tree_budget["baseline"][name]) * tolerance + 1e-9
        if delta > allowed:
            violations.append(name)
    if violations:
        raise LATSContractError(
            "tree and one-path actual usage is not matched: " + ", ".join(violations)
        )
    core = {
        "version": VERSION,
        "comparison_key_hash": tree["result"]["comparison_key_hash"],
        "tree_result_hash": tree["result_hash"],
        "control_result_hash": control["result_hash"],
        "budget_cap_hash": tree_budget["budget_hash"],
        "actual_usage_tolerance": tolerance,
        "actual_usage_deltas": deltas,
        "six_dimensions_matched": True,
        "performance_evidence": False,
        "promotion_authority": "NONE",
    }
    return {**core, "comparison_receipt_hash": sha256_json(core)}
