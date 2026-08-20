#!/usr/bin/env python3
"""Bounded SHADOW-only cognitive mechanism plumbing.

The functions in this module execute small, auditable control-flow adapters for
selected cognitive-paper ideas.  They do not call a model or an external tool
on their own.  Any such behavior must be supplied through an injected callback,
whose read-only/side-effect-free status remains a caller attestation.  Results
are disposable, have no promotion authority, and are not performance evidence.
"""
from __future__ import annotations

import copy
import dataclasses
import datetime as dt
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from frankie_cognition import CognitiveContractError, sha256_json
from frankie_cognitive_candidates import TypedEvidenceStore, run_deterministic_check


VERSION = "FRANKIE_COGNITIVE_P0_LOOPS_V1_PROVISIONAL"
RESOURCE_DIMENSIONS = (
    "model_calls",
    "input_tokens",
    "output_tokens",
    "tool_queries",
    "storage_bytes",
    "wall_clock_ms",
)
SHA256_RE = re.compile(r"[0-9a-f]{64}")
MAX_ARTIFACT_BYTES = 1_000_000

IMPLEMENTATION_AUDIT = {
    "REACT": {
        "depth": "BOUNDED_DEFINING_LOOP_PLUMBING",
        "implemented": ["decide", "read-only tool action", "observation", "replan", "stop"],
        "not_implemented": ["paper prompts", "paper tool environment", "learned policy"],
    },
    "STRUCTGPT": {
        "depth": "BOUNDED_DEFINING_LOOP_PLUMBING",
        "implemented": ["iterative model-directed exact-ref reads", "answer-or-read stop policy"],
        "not_implemented": ["paper interfaces", "entity linking", "SQL generation", "trained reader"],
    },
    "CRITIC": {
        "depth": "BOUNDED_DEFINING_LOOP_PLUMBING",
        "implemented": ["immutable initial", "check", "critique", "revision", "recheck"],
        "not_implemented": ["paper prompts", "paper external tools", "trained critique policy"],
    },
    "HIAGENT": {
        "depth": "BOUNDED_STATE_MACHINE_PLUMBING",
        "implemented": ["one-active lifecycle", "summary compaction", "hidden history", "detail retrieval"],
        "not_implemented": ["model-generated subgoals", "paper prompts", "learned retrieval policy"],
    },
    "FAITHFUL_IR": {
        "depth": "BOUNDED_TYPED_EXECUTOR",
        "implemented": ["source-hashed premises", "linear typed IR", "deterministic final derivation"],
        "not_implemented": ["language-to-IR translation", "general Python/Datalog/PDDL solver"],
    },
    "MEMORY_BENCH": {
        "depth": "CHRONOLOGICAL_BENCHMARK_RUNNER",
        "implemented": ["incremental histories", "isolated cases", "four-axis exact scoring"],
        "not_implemented": ["memory architecture", "MemoryAgentBench corpus replication", "LLM judge"],
    },
}


class P0LoopError(CognitiveContractError):
    """Invalid P0 loop input or callback contract."""


class _ControlledStop(RuntimeError):
    pass


def _clone(value: Any, label: str = "value") -> Any:
    """Return a detached JSON value and reject non-finite/non-serializable data."""
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        if len(encoded.encode("utf-8")) > MAX_ARTIFACT_BYTES:
            raise P0LoopError(f"{label} exceeds the artifact byte limit")
        return json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise P0LoopError(f"{label} must be finite JSON data") from exc


def _nonempty(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise P0LoopError(f"{label} must be non-empty")
    return text


def _string_list(value: Any, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or isinstance(value, (str, bytes)):
        raise P0LoopError(f"{label} must be a string sequence")
    items = tuple(dict.fromkeys(str(item).strip() for item in value))
    if any(not item for item in items) or (not items and not allow_empty):
        raise P0LoopError(f"{label} must contain non-empty strings")
    return items


def _parse_time(value: Any, label: str) -> dt.datetime:
    text = _nonempty(value, label)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise P0LoopError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise P0LoopError(f"{label} must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


@dataclass(frozen=True)
class BudgetVector:
    model_calls: float = 0.0
    input_tokens: float = 0.0
    output_tokens: float = 0.0
    tool_queries: float = 0.0
    storage_bytes: float = 0.0
    wall_clock_ms: float = 0.0

    def __post_init__(self) -> None:
        for name in RESOURCE_DIMENSIONS:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise P0LoopError(f"budget {name} must be numeric")
            number = float(value)
            if not math.isfinite(number) or number < 0:
                raise P0LoopError(f"budget {name} must be finite and non-negative")
            object.__setattr__(self, name, number)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], label: str = "budget") -> "BudgetVector":
        if not isinstance(raw, Mapping):
            raise P0LoopError(f"{label} must be an object")
        missing = [name for name in RESOURCE_DIMENSIONS if name not in raw]
        unknown = sorted(set(raw) - set(RESOURCE_DIMENSIONS))
        if missing or unknown:
            raise P0LoopError(f"{label} dimensions mismatch; missing={missing}, unknown={unknown}")
        return cls(**{name: raw[name] for name in RESOURCE_DIMENSIONS})

    def as_dict(self) -> dict[str, float]:
        return {name: getattr(self, name) for name in RESOURCE_DIMENSIONS}

    def plus(self, other: "BudgetVector") -> "BudgetVector":
        return BudgetVector(**{
            name: getattr(self, name) + getattr(other, name)
            for name in RESOURCE_DIMENSIONS
        })


@dataclass(frozen=True)
class CallbackResult:
    """Result returned by an injected callback with caller-supplied metering."""

    payload: Mapping[str, Any]
    usage: BudgetVector = dataclasses.field(default_factory=BudgetVector)
    side_effect_free: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.payload, Mapping):
            raise P0LoopError("callback payload must be an object")
        if not isinstance(self.usage, BudgetVector):
            raise P0LoopError("callback usage must be a BudgetVector")
        if self.side_effect_free is not True:
            raise P0LoopError("callback must attest side_effect_free=True")


Callback = Callable[..., CallbackResult]


class _Session:
    def __init__(
        self,
        component: str,
        baseline_budget: Mapping[str, Any],
        *,
        budget_tolerance: float,
        faults: Sequence[str],
    ) -> None:
        if component not in IMPLEMENTATION_AUDIT:
            raise P0LoopError(f"unknown P0 component: {component}")
        if isinstance(budget_tolerance, bool) or not isinstance(budget_tolerance, (int, float)):
            raise P0LoopError("budget tolerance must be numeric")
        self.tolerance = float(budget_tolerance)
        if not 0.0 <= self.tolerance <= 0.10:
            raise P0LoopError("budget tolerance must be within [0, 0.10]")
        self.component = component
        self.baseline = BudgetVector.from_mapping(baseline_budget, "baseline_budget")
        self.usage = BudgetVector()
        self.faults = frozenset(_string_list(faults, "faults", allow_empty=True))
        self.stage_counts: dict[str, int] = {}
        self.events: list[dict[str, Any]] = []
        self.artifacts: list[dict[str, Any]] = []

    def _ordinal(self, stage: str) -> int:
        self.stage_counts[stage] = self.stage_counts.get(stage, 0) + 1
        return self.stage_counts[stage]

    def _before(self, stage: str) -> int:
        ordinal = self._ordinal(stage)
        if stage in self.faults or f"{stage}:{ordinal}" in self.faults:
            self.events.append({"stage": stage, "ordinal": ordinal, "event": "FAULT_INJECTED"})
            raise _ControlledStop(f"fault injected at {stage}:{ordinal}")
        return ordinal

    def _add_usage(self, usage: BudgetVector) -> None:
        self.usage = self.usage.plus(usage)
        violations = [
            name
            for name in RESOURCE_DIMENSIONS
            if getattr(self.usage, name)
            > getattr(self.baseline, name) * (1.0 + self.tolerance) + 1e-9
        ]
        if violations:
            raise _ControlledStop("matched budget exceeded: " + ", ".join(violations))

    def _freeze(self, stage: str, ordinal: int, payload: Mapping[str, Any]) -> dict[str, Any]:
        frozen = _clone(dict(payload), f"{stage} payload")
        core = {"stage": stage, "ordinal": ordinal, "payload": frozen}
        artifact = {**core, "artifact_hash": sha256_json(core)}
        self.artifacts.append(artifact)
        return artifact

    def call(
        self,
        stage: str,
        callback: Callback,
        *args: Any,
        minimum_usage: Mapping[str, float] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        ordinal = self._before(stage)
        try:
            result = callback(*copy.deepcopy(args))
        except Exception as exc:  # callbacks are an isolation boundary
            self.events.append({
                "stage": stage,
                "ordinal": ordinal,
                "event": "CALLBACK_ERROR",
                "error_type": type(exc).__name__,
            })
            raise _ControlledStop(f"callback failed at {stage}:{ordinal}") from exc
        if not isinstance(result, CallbackResult):
            raise _ControlledStop(f"callback at {stage}:{ordinal} returned the wrong type")
        if minimum_usage:
            short = [
                name for name, floor in minimum_usage.items()
                if getattr(result.usage, name) + 1e-9 < float(floor)
            ]
            if short:
                raise _ControlledStop(
                    f"callback under-reported required usage at {stage}:{ordinal}: {', '.join(short)}"
                )
        artifact = self._freeze(stage, ordinal, result.payload)
        self._add_usage(result.usage)
        self.events.append({
            "stage": stage,
            "ordinal": ordinal,
            "event": "CALLBACK_ACCEPTED",
            "artifact_hash": artifact["artifact_hash"],
            "usage_hash": sha256_json(result.usage.as_dict()),
        })
        return copy.deepcopy(artifact["payload"]), artifact

    def local(
        self,
        stage: str,
        payload: Mapping[str, Any],
        *,
        usage: BudgetVector | None = None,
    ) -> dict[str, Any]:
        ordinal = self._before(stage)
        artifact = self._freeze(stage, ordinal, payload)
        self._add_usage(usage or BudgetVector())
        self.events.append({
            "stage": stage,
            "ordinal": ordinal,
            "event": "LOCAL_ARTIFACT",
            "artifact_hash": artifact["artifact_hash"],
        })
        return artifact

    def finish(
        self,
        status: str,
        *,
        reason: str,
        extra: Mapping[str, Any] | None = None,
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
            "method": "DROP_DISPOSABLE_RESULT_AND_LOCAL_ARTIFACTS",
            "component": self.component,
            "artifact_hashes": artifact_hashes,
            "canonical_state_changed": False,
            "external_callback_side_effects": "NOT_VERIFIABLE; CALLER MUST ISOLATE CALLBACKS",
        }
        core = {
            "version": VERSION,
            "component": self.component,
            "status": status if within else "REJECTED",
            "reason": reason if within else "matched budget exceeded",
            "implementation_audit": IMPLEMENTATION_AUDIT[self.component],
            "paper_faithful": False,
            "performance_evidence": False,
            "execution_enabled": False,
            "automatic_apply": False,
            "promotion_authority": "NONE",
            "canonical_mutation": False,
            "callback_contract": "INJECTED_AND_CALLER_ATTESTED_SIDE_EFFECT_FREE",
            "fault_plan": sorted(self.faults),
            "events": self.events,
            "artifacts": self.artifacts,
            "matched_budget": {**budget_core, "budget_hash": sha256_json(budget_core)},
            "removal": {**removal_core, "removal_receipt_hash": sha256_json(removal_core)},
            "result": _clone(dict(extra or {}), "loop result"),
        }
        return {**core, "result_hash": sha256_json(core)}


def _failed(session: _Session, exc: _ControlledStop, **extra: Any) -> dict[str, Any]:
    return session.finish("REJECTED", reason=str(exc), extra=extra)


def run_bounded_react(
    initial_state: Mapping[str, Any],
    *,
    decide_fn: Callback,
    tool_fn: Callback,
    allowed_tools: Sequence[str],
    baseline_budget: Mapping[str, Any],
    max_steps: int = 4,
    budget_tolerance: float = 0.02,
    faults: Sequence[str] = (),
) -> dict[str, Any]:
    """Run a bounded decide -> tool -> observe -> replan -> stop adapter."""
    if not 1 <= max_steps <= 16:
        raise P0LoopError("ReAct max_steps must be within [1, 16]")
    tools = frozenset(_string_list(allowed_tools, "allowed_tools"))
    state = _clone(dict(initial_state), "ReAct initial_state")
    session = _Session("REACT", baseline_budget, budget_tolerance=budget_tolerance, faults=faults)
    trace: list[dict[str, Any]] = []
    observations = 0
    observed_source_hashes: set[str] = set()
    try:
        for step in range(1, max_steps + 1):
            decision, decision_artifact = session.call(
                "react.decide",
                decide_fn,
                {"step": step, "state": state, "trace": trace},
            )
            kind = _nonempty(decision.get("kind"), "ReAct decision kind").upper()
            reason = _nonempty(decision.get("reason"), "ReAct decision reason")
            if kind in {"STOP", "ABSTAIN"}:
                if kind == "STOP" and observations == 0:
                    raise _ControlledStop("ReAct STOP requires at least one tool observation")
                final = decision.get("final")
                if kind == "STOP" and final is None:
                    raise _ControlledStop("ReAct STOP requires a final value")
                final_sources = _string_list(
                    decision.get("source_hashes", []),
                    "ReAct final source_hashes",
                    allow_empty=kind == "ABSTAIN",
                )
                if kind == "STOP" and (
                    any(not SHA256_RE.fullmatch(value) for value in final_sources)
                    or set(final_sources) - observed_source_hashes
                ):
                    raise _ControlledStop("ReAct final cites unknown or invalid observation hashes")
                trace.append({
                    "step": step,
                    "kind": kind,
                    "reason": reason,
                    "decision_artifact_hash": decision_artifact["artifact_hash"],
                    "source_hashes": final_sources,
                })
                return session.finish(
                    "COMPLETED" if kind == "STOP" else "ABSTAINED",
                    reason="bounded ReAct loop stopped explicitly",
                    extra={
                        "final": final,
                        "trace": trace,
                        "tool_observations": observations,
                        "replans": max(0, step - 1),
                    },
                )
            if kind != "TOOL":
                raise _ControlledStop(f"ReAct decision kind is not allowlisted: {kind}")
            tool_name = _nonempty(decision.get("tool_name"), "ReAct tool_name")
            if tool_name not in tools:
                raise _ControlledStop(f"ReAct tool is not allowlisted: {tool_name}")
            tool_input = decision.get("tool_input")
            if not isinstance(tool_input, Mapping):
                raise _ControlledStop("ReAct tool_input must be an object")
            observation, observation_artifact = session.call(
                "react.tool",
                tool_fn,
                {
                    "step": step,
                    "tool_name": tool_name,
                    "tool_input": _clone(dict(tool_input), "ReAct tool_input"),
                    "reason": reason,
                },
                minimum_usage={"tool_queries": 1.0},
            )
            if observation.get("read_only") is not True:
                raise _ControlledStop("ReAct tool callback did not attest read_only=True")
            if "observation" not in observation:
                raise _ControlledStop("ReAct tool callback omitted its observation")
            source_hashes = _string_list(observation.get("source_hashes"), "ReAct source_hashes")
            if any(not SHA256_RE.fullmatch(value) for value in source_hashes):
                raise _ControlledStop("ReAct observation source hashes must be SHA-256 values")
            trace.append({
                "step": step,
                "kind": "TOOL_OBSERVATION",
                "tool_name": tool_name,
                "reason": reason,
                "decision_artifact_hash": decision_artifact["artifact_hash"],
                "observation_artifact_hash": observation_artifact["artifact_hash"],
                "source_hashes": source_hashes,
            })
            observations += 1
            observed_source_hashes.update(source_hashes)
            state = {
                "initial": state.get("initial", state),
                "latest_observation": observation,
            }
        raise _ControlledStop("ReAct reached its step bound without STOP/ABSTAIN")
    except _ControlledStop as exc:
        return _failed(session, exc, trace=trace, tool_observations=observations)


def run_iterative_structured_reads(
    cognitive_context: Mapping[str, Any],
    initial_query: Mapping[str, Any],
    *,
    decide_fn: Callback,
    baseline_budget: Mapping[str, Any],
    max_rounds: int = 4,
    max_total_records: int = 16,
    budget_tolerance: float = 0.02,
    faults: Sequence[str] = (),
) -> dict[str, Any]:
    """Run bounded decide -> typed read -> reason cycles until answer/abstain."""
    if not 1 <= max_rounds <= 16 or not 1 <= max_total_records <= 32:
        raise P0LoopError("StructGPT round/record bounds are invalid")
    store = TypedEvidenceStore(cognitive_context)
    query = _clone(dict(initial_query), "structured-read query")
    session = _Session("STRUCTGPT", baseline_budget, budget_tolerance=budget_tolerance, faults=faults)
    history: list[dict[str, Any]] = []
    read_refs: set[str] = set()
    try:
        for round_index in range(1, max_rounds + 1):
            decision, decision_artifact = session.call(
                "struct.decide",
                decide_fn,
                {"round": round_index, "query": query, "read_history": history},
            )
            kind = _nonempty(decision.get("kind"), "structured-read decision kind").upper()
            if kind in {"ANSWER", "ABSTAIN"}:
                citations = _string_list(
                    decision.get("citations", []),
                    "structured-read citations",
                    allow_empty=kind == "ABSTAIN",
                )
                if kind == "ANSWER" and not history:
                    raise _ControlledStop("structured ANSWER requires at least one typed read")
                if set(citations) - read_refs:
                    raise _ControlledStop("structured answer cites refs that were not read")
                if kind == "ANSWER" and decision.get("answer") is None:
                    raise _ControlledStop("structured ANSWER requires an answer")
                return session.finish(
                    "COMPLETED" if kind == "ANSWER" else "ABSTAINED",
                    reason="structured read loop stopped explicitly",
                    extra={
                        "answer": decision.get("answer"),
                        "citations": citations,
                        "rounds": round_index,
                        "read_history": history,
                        "final_decision_hash": decision_artifact["artifact_hash"],
                    },
                )
            if kind != "READ":
                raise _ControlledStop(f"structured-read decision kind is not allowlisted: {kind}")
            refs = _string_list(decision.get("ref_ids"), "structured read refs")
            if len(read_refs | set(refs)) > max_total_records:
                raise _ControlledStop("structured read exceeded its total record bound")
            ordinal = session._before("struct.read")
            receipt = store.read(refs, max_records=min(32, len(refs)))
            retrieved_bytes = len(json.dumps(receipt["records"], sort_keys=True).encode("utf-8"))
            read_artifact = session._freeze("struct.read", ordinal, receipt)
            session._add_usage(BudgetVector(tool_queries=1, storage_bytes=retrieved_bytes))
            session.events.append({
                "stage": "struct.read",
                "ordinal": ordinal,
                "event": "READ_ONLY_TYPED_READ",
                "artifact_hash": read_artifact["artifact_hash"],
            })
            read_refs.update(refs)
            history.append({
                "round": round_index,
                "requested_refs": refs,
                "read_hash": receipt["read_hash"],
                "read_artifact_hash": read_artifact["artifact_hash"],
                "records": receipt["records"],
            })
        raise _ControlledStop("structured read loop reached its round bound")
    except (CognitiveContractError, _ControlledStop) as exc:
        controlled = exc if isinstance(exc, _ControlledStop) else _ControlledStop(str(exc))
        return _failed(session, controlled, read_history=history, read_refs=sorted(read_refs))


def run_critic_revision(
    context: Mapping[str, Any],
    *,
    initial_fn: Callback,
    check_fn: Callback,
    critique_fn: Callback,
    revise_fn: Callback,
    allowed_evidence_refs: set[str],
    baseline_budget: Mapping[str, Any],
    max_revisions: int = 2,
    budget_tolerance: float = 0.02,
    faults: Sequence[str] = (),
) -> dict[str, Any]:
    """Run immutable initial -> deterministic check -> critique -> revise cycles."""
    if not 0 <= max_revisions <= 4:
        raise P0LoopError("CRITIC max_revisions must be within [0, 4]")
    session = _Session("CRITIC", baseline_budget, budget_tolerance=budget_tolerance, faults=faults)
    answer_history: list[dict[str, Any]] = []
    check_history: list[dict[str, Any]] = []
    try:
        answer, answer_artifact = session.call("critic.initial", initial_fn, _clone(dict(context), "CRITIC context"))
        if "answer" not in answer:
            raise _ControlledStop("CRITIC initial callback omitted answer")
        answer_refs = _string_list(answer.get("evidence_refs"), "CRITIC initial evidence_refs")
        if set(answer_refs) - allowed_evidence_refs:
            raise _ControlledStop("CRITIC initial answer cites unknown evidence")
        answer_history.append({"round": 0, "answer_hash": answer_artifact["artifact_hash"]})
        initial_hash = answer_artifact["artifact_hash"]
        revisions = 0
        while True:
            check_payload, check_request_artifact = session.call(
                "critic.check",
                check_fn,
                {"round": revisions, "answer": answer, "answer_artifact_hash": answer_artifact["artifact_hash"]},
            )
            specs = check_payload.get("checks")
            if not isinstance(specs, list) or not 1 <= len(specs) <= 16:
                raise _ControlledStop("CRITIC check callback must return 1..16 checks")
            receipts = []
            for spec in specs:
                if not isinstance(spec, Mapping):
                    raise _ControlledStop("CRITIC check spec must be an object")
                refs = _string_list(spec.get("evidence_refs"), "CRITIC check evidence_refs")
                if set(refs) - allowed_evidence_refs:
                    raise _ControlledStop("CRITIC check cites unknown evidence")
                receipts.append(run_deterministic_check(spec))
            check_artifact = session.local("critic.check_receipts", {"receipts": receipts})
            supported = all(receipt["status"] == "SUPPORTED" for receipt in receipts)
            check_history.append({
                "round": revisions,
                "request_hash": check_request_artifact["artifact_hash"],
                "receipt_hash": check_artifact["artifact_hash"],
                "supported": supported,
            })
            if supported:
                return session.finish(
                    "COMPLETED",
                    reason="CRITIC checks support the frozen final answer",
                    extra={
                        "final_answer": answer.get("answer"),
                        "initial_answer_artifact_hash": initial_hash,
                        "final_answer_artifact_hash": answer_artifact["artifact_hash"],
                        "answer_history": answer_history,
                        "check_history": check_history,
                        "revisions": revisions,
                        "restore_target_hash": initial_hash,
                    },
                )
            if revisions >= max_revisions:
                raise _ControlledStop("CRITIC exhausted its revision bound with contradicted checks")
            critique, critique_artifact = session.call(
                "critic.critique",
                critique_fn,
                {
                    "round": revisions,
                    "answer": answer,
                    "answer_artifact_hash": answer_artifact["artifact_hash"],
                    "check_receipts": receipts,
                },
            )
            _nonempty(critique.get("critique"), "CRITIC critique")
            critique_refs = _string_list(critique.get("evidence_refs"), "CRITIC critique evidence_refs")
            if set(critique_refs) - allowed_evidence_refs:
                raise _ControlledStop("CRITIC critique cites unknown evidence")
            revised, revised_artifact = session.call(
                "critic.revise",
                revise_fn,
                {
                    "round": revisions + 1,
                    "prior_answer": answer,
                    "prior_answer_artifact_hash": answer_artifact["artifact_hash"],
                    "critique": critique,
                    "critique_artifact_hash": critique_artifact["artifact_hash"],
                },
            )
            if "answer" not in revised or sha256_json(revised.get("answer")) == sha256_json(answer.get("answer")):
                raise _ControlledStop("CRITIC revision did not change the answer")
            revised_refs = _string_list(revised.get("evidence_refs"), "CRITIC revision evidence_refs")
            if set(revised_refs) - allowed_evidence_refs:
                raise _ControlledStop("CRITIC revision cites unknown evidence")
            revisions += 1
            answer = revised
            answer_artifact = revised_artifact
            answer_history.append({
                "round": revisions,
                "answer_hash": revised_artifact["artifact_hash"],
                "parent_answer_hash": answer_history[-1]["answer_hash"],
                "critique_hash": critique_artifact["artifact_hash"],
            })
    except (CognitiveContractError, _ControlledStop) as exc:
        controlled = exc if isinstance(exc, _ControlledStop) else _ControlledStop(str(exc))
        return _failed(session, controlled, answer_history=answer_history, check_history=check_history)


def run_state_aware_working_memory(
    commands: Sequence[Mapping[str, Any]],
    *,
    summarize_fn: Callback,
    allowed_evidence_refs: set[str],
    baseline_budget: Mapping[str, Any],
    max_chunks: int = 16,
    max_events_per_chunk: int = 64,
    budget_tolerance: float = 0.02,
    faults: Sequence[str] = (),
) -> dict[str, Any]:
    """Execute a state-aware one-active-subgoal compaction/retrieval lifecycle."""
    if not commands or not 1 <= max_chunks <= 32 or not 1 <= max_events_per_chunk <= 256:
        raise P0LoopError("HiAgent command/chunk/event bounds are invalid")
    session = _Session("HIAGENT", baseline_budget, budget_tolerance=budget_tolerance, faults=faults)
    chunks: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    active_id: str | None = None
    snapshots: list[dict[str, Any]] = []

    def visible_context() -> dict[str, Any]:
        visible = []
        for chunk_id in order:
            chunk = chunks[chunk_id]
            if chunk["status"] == "ACTIVE":
                visible.append({
                    "subgoal_id": chunk_id,
                    "status": "ACTIVE",
                    "objective": chunk["objective"],
                    "trajectory": copy.deepcopy(chunk["trajectory"]),
                })
            else:
                visible.append({
                    "subgoal_id": chunk_id,
                    "status": "COMPLETE",
                    "objective": chunk["objective"],
                    "summary": chunk["summary"],
                    "trajectory_hash": chunk["trajectory_hash"],
                    "details_hidden": True,
                })
        return {"active_subgoal_id": active_id, "chunks": visible}

    try:
        for index, raw in enumerate(commands, start=1):
            if not isinstance(raw, Mapping):
                raise _ControlledStop(f"HiAgent command {index} must be an object")
            kind = _nonempty(raw.get("kind"), f"HiAgent command {index} kind").upper()
            if kind == "START":
                if active_id is not None:
                    raise _ControlledStop("HiAgent cannot START while another subgoal is active")
                chunk_id = _nonempty(raw.get("subgoal_id"), "HiAgent subgoal_id")
                if chunk_id in chunks or len(chunks) >= max_chunks:
                    raise _ControlledStop("HiAgent subgoal is duplicate or exceeds the chunk bound")
                chunks[chunk_id] = {
                    "objective": _nonempty(raw.get("objective"), "HiAgent objective"),
                    "status": "ACTIVE",
                    "trajectory": [],
                    "summary": None,
                    "trajectory_hash": None,
                }
                order.append(chunk_id)
                active_id = chunk_id
                session.local("hiagent.start", {"subgoal_id": chunk_id, "objective": chunks[chunk_id]["objective"]})
            elif kind == "EVENT":
                chunk_id = _nonempty(raw.get("subgoal_id"), "HiAgent event subgoal_id")
                if active_id != chunk_id:
                    raise _ControlledStop("HiAgent EVENT must target the active subgoal")
                event_kind = _nonempty(raw.get("event_kind"), "HiAgent event kind").upper()
                if event_kind not in {"ACTION", "OBSERVATION"}:
                    raise _ControlledStop("HiAgent event kind must be ACTION or OBSERVATION")
                refs = _string_list(raw.get("evidence_refs"), "HiAgent event evidence_refs")
                if set(refs) - allowed_evidence_refs:
                    raise _ControlledStop("HiAgent event cites unknown evidence")
                trajectory = chunks[chunk_id]["trajectory"]
                if len(trajectory) >= max_events_per_chunk:
                    raise _ControlledStop("HiAgent active trajectory exceeded its event bound")
                event_core = {
                    "index": len(trajectory) + 1,
                    "event_kind": event_kind,
                    "content": _clone(raw.get("content"), "HiAgent event content"),
                    "evidence_refs": refs,
                }
                event = {**event_core, "event_hash": sha256_json(event_core)}
                trajectory.append(event)
                session.local("hiagent.event", event)
            elif kind == "COMPLETE":
                chunk_id = _nonempty(raw.get("subgoal_id"), "HiAgent completion subgoal_id")
                if active_id != chunk_id or not chunks[chunk_id]["trajectory"]:
                    raise _ControlledStop("HiAgent COMPLETE requires the active subgoal and non-empty trajectory")
                trajectory = copy.deepcopy(chunks[chunk_id]["trajectory"])
                event_hashes = [event["event_hash"] for event in trajectory]
                summary, summary_artifact = session.call(
                    "hiagent.summarize",
                    summarize_fn,
                    {
                        "subgoal_id": chunk_id,
                        "objective": chunks[chunk_id]["objective"],
                        "trajectory": trajectory,
                    },
                )
                summary_text = _nonempty(summary.get("summary"), "HiAgent summary")
                covered = _string_list(summary.get("covered_event_hashes"), "HiAgent covered_event_hashes")
                if tuple(covered) != tuple(event_hashes):
                    raise _ControlledStop("HiAgent summary must cover every trajectory event in order")
                refs = _string_list(summary.get("evidence_refs"), "HiAgent summary evidence_refs")
                if set(refs) - allowed_evidence_refs:
                    raise _ControlledStop("HiAgent summary cites unknown evidence")
                trajectory_refs = {
                    ref for event in trajectory for ref in event["evidence_refs"]
                }
                if trajectory_refs - set(refs):
                    raise _ControlledStop("HiAgent summary omitted trajectory evidence refs")
                chunks[chunk_id].update({
                    "status": "COMPLETE",
                    "summary": summary_text,
                    "summary_artifact_hash": summary_artifact["artifact_hash"],
                    "trajectory_hash": sha256_json(trajectory),
                })
                active_id = None
            elif kind == "RETRIEVE":
                chunk_id = _nonempty(raw.get("subgoal_id"), "HiAgent retrieval subgoal_id")
                if chunk_id not in chunks or chunks[chunk_id]["status"] != "COMPLETE":
                    raise _ControlledStop("HiAgent may retrieve details only for a completed subgoal")
                reason = _nonempty(raw.get("reason"), "HiAgent retrieval reason")
                trajectory = copy.deepcopy(chunks[chunk_id]["trajectory"])
                retrieved_bytes = len(json.dumps(trajectory, sort_keys=True).encode("utf-8"))
                session.local(
                    "hiagent.retrieve",
                    {
                        "subgoal_id": chunk_id,
                        "reason": reason,
                        "trajectory": trajectory,
                        "trajectory_hash": chunks[chunk_id]["trajectory_hash"],
                        "read_only": True,
                    },
                    usage=BudgetVector(tool_queries=1, storage_bytes=retrieved_bytes),
                )
            elif kind == "STOP":
                if active_id is not None:
                    raise _ControlledStop("HiAgent STOP requires no active subgoal")
                if not chunks:
                    raise _ControlledStop("HiAgent STOP requires at least one completed subgoal")
                snapshots.append(visible_context())
                return session.finish(
                    "COMPLETED",
                    reason="HiAgent state machine stopped with no active subgoal",
                    extra={
                        "visible_context": visible_context(),
                        "snapshots": snapshots,
                        "completed_chunks": len(chunks),
                    },
                )
            else:
                raise _ControlledStop(f"HiAgent command kind is not allowlisted: {kind}")
            expected_active = sum(1 for chunk in chunks.values() if chunk["status"] == "ACTIVE")
            if expected_active != (1 if active_id is not None else 0):
                raise _ControlledStop("HiAgent active-subgoal state invariant failed")
            snapshots.append(visible_context())
        if active_id is not None:
            raise _ControlledStop("HiAgent command stream ended with an active subgoal")
        raise _ControlledStop("HiAgent command stream ended without STOP")
    except _ControlledStop as exc:
        return _failed(session, exc, visible_context=visible_context(), snapshots=snapshots)


def _source_value(payload: Any, path: Sequence[Any], label: str) -> Any:
    value = payload
    for part in path:
        if isinstance(value, Mapping) and isinstance(part, str) and part in value:
            value = value[part]
        elif isinstance(value, list) and isinstance(part, int) and not isinstance(part, bool) and 0 <= part < len(value):
            value = value[part]
        else:
            raise P0LoopError(f"{label} source path is invalid")
    return _clone(value, f"{label} resolved value")


def _numeric(value: Any, label: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise P0LoopError(f"{label} must be a finite number")
    if abs(float(value)) > 1e15:
        raise P0LoopError(f"{label} exceeds numeric bounds")
    return value


def execute_faithful_ir(
    *,
    sources: Mapping[str, Mapping[str, Any]],
    premises: Sequence[Mapping[str, Any]],
    program: Sequence[Mapping[str, Any]],
    final_register: str,
    baseline_budget: Mapping[str, Any],
    budget_tolerance: float = 0.02,
    faults: Sequence[str] = (),
) -> dict[str, Any]:
    """Execute a bounded, linear, non-Turing IR over source-hashed premises."""
    if not isinstance(sources, Mapping) or not sources or not 1 <= len(program) <= 64:
        raise P0LoopError("Faithful IR requires sources and 1..64 instructions")
    session = _Session("FAITHFUL_IR", baseline_budget, budget_tolerance=budget_tolerance, faults=faults)
    source_payloads: dict[str, Any] = {}
    source_hashes: dict[str, str] = {}
    for source_id_raw, raw in sources.items():
        source_id = _nonempty(source_id_raw, "Faithful source id")
        if not isinstance(raw, Mapping) or "payload" not in raw:
            raise P0LoopError(f"Faithful source {source_id} is invalid")
        payload = _clone(raw["payload"], f"Faithful source {source_id}")
        supplied_hash = str(raw.get("source_hash") or "")
        if not SHA256_RE.fullmatch(supplied_hash) or supplied_hash != sha256_json(payload):
            raise P0LoopError(f"Faithful source {source_id} hash mismatch")
        source_payloads[source_id] = payload
        source_hashes[source_id] = supplied_hash

    premise_values: dict[str, Any] = {}
    premise_receipts: list[dict[str, Any]] = []
    for raw in premises:
        premise_id = _nonempty(raw.get("premise_id"), "Faithful premise id")
        if premise_id in premise_values:
            raise P0LoopError(f"duplicate Faithful premise: {premise_id}")
        source_id = _nonempty(raw.get("source_id"), f"premise {premise_id} source_id")
        if source_id not in source_payloads:
            raise P0LoopError(f"premise {premise_id} cites an unknown source")
        path = raw.get("path", [])
        if not isinstance(path, list) or len(path) > 16:
            raise P0LoopError(f"premise {premise_id} path is invalid")
        value = _source_value(source_payloads[source_id], path, f"premise {premise_id}")
        premise_values[premise_id] = value
        core = {
            "premise_id": premise_id,
            "source_id": source_id,
            "source_hash": source_hashes[source_id],
            "path": path,
            "value_hash": sha256_json(value),
        }
        premise_receipts.append({**core, "premise_hash": sha256_json(core)})

    registers: dict[str, Any] = {}
    dependencies: dict[str, set[str]] = {}
    instruction_receipts: list[dict[str, Any]] = []

    def arg(name: str, instruction: Mapping[str, Any]) -> tuple[Any, set[str]]:
        register_id = _nonempty(instruction.get(name), f"Faithful {name}")
        if register_id not in registers:
            raise P0LoopError(f"Faithful instruction cites unknown/prior register: {register_id}")
        return registers[register_id], set(dependencies[register_id])

    try:
        for index, raw in enumerate(program, start=1):
            if not isinstance(raw, Mapping):
                raise P0LoopError(f"Faithful instruction {index} must be an object")
            session._before("faithful.step")
            out = _nonempty(raw.get("out"), f"Faithful instruction {index} out")
            if out in registers:
                raise P0LoopError(f"Faithful register is assigned twice: {out}")
            op = _nonempty(raw.get("op"), f"Faithful instruction {index} op").upper()
            deps: set[str]
            if op == "LOAD":
                premise_id = _nonempty(raw.get("premise_id"), "Faithful LOAD premise_id")
                if premise_id not in premise_values:
                    raise P0LoopError(f"Faithful LOAD cites unknown premise: {premise_id}")
                value, deps = premise_values[premise_id], {premise_id}
            elif op == "CONST":
                value, deps = _clone(raw.get("value"), "Faithful CONST value"), set()
            elif op == "NOT":
                left, deps = arg("left", raw)
                if not isinstance(left, bool):
                    raise P0LoopError("Faithful NOT requires a boolean")
                value = not left
            elif op in {"AND", "OR"}:
                left, left_deps = arg("left", raw)
                right, right_deps = arg("right", raw)
                if not isinstance(left, bool) or not isinstance(right, bool):
                    raise P0LoopError(f"Faithful {op} requires booleans")
                value = left and right if op == "AND" else left or right
                deps = left_deps | right_deps
            elif op in {"EQ", "NE", "LT", "LE", "GT", "GE"}:
                left, left_deps = arg("left", raw)
                right, right_deps = arg("right", raw)
                if op in {"LT", "LE", "GT", "GE"}:
                    _numeric(left, f"Faithful {op} left")
                    _numeric(right, f"Faithful {op} right")
                value = {
                    "EQ": lambda: left == right,
                    "NE": lambda: left != right,
                    "LT": lambda: left < right,
                    "LE": lambda: left <= right,
                    "GT": lambda: left > right,
                    "GE": lambda: left >= right,
                }[op]()
                deps = left_deps | right_deps
            elif op in {"ADD", "SUB", "MUL", "DIV"}:
                left, left_deps = arg("left", raw)
                right, right_deps = arg("right", raw)
                left = _numeric(left, f"Faithful {op} left")
                right = _numeric(right, f"Faithful {op} right")
                if op == "DIV" and float(right) == 0.0:
                    raise P0LoopError("Faithful DIV by zero")
                value = {
                    "ADD": lambda: left + right,
                    "SUB": lambda: left - right,
                    "MUL": lambda: left * right,
                    "DIV": lambda: left / right,
                }[op]()
                _numeric(value, f"Faithful {op} result")
                deps = left_deps | right_deps
            elif op == "CONTAINS":
                collection, left_deps = arg("collection", raw)
                item, right_deps = arg("item", raw)
                if not isinstance(collection, (list, str, Mapping)):
                    raise P0LoopError("Faithful CONTAINS requires list/string/object collection")
                value = item in collection
                deps = left_deps | right_deps
            elif op == "SELECT":
                condition, condition_deps = arg("condition", raw)
                true_value, true_deps = arg("when_true", raw)
                false_value, false_deps = arg("when_false", raw)
                if not isinstance(condition, bool):
                    raise P0LoopError("Faithful SELECT condition must be boolean")
                value = true_value if condition else false_value
                deps = condition_deps | (true_deps if condition else false_deps)
            else:
                raise P0LoopError(f"Faithful IR op is not allowlisted: {op}")
            value = _clone(value, f"Faithful {out} result")
            registers[out] = value
            dependencies[out] = deps
            receipt_core = {
                "index": index,
                "op": op,
                "out": out,
                "instruction_hash": sha256_json(dict(raw)),
                "result_hash": sha256_json(value),
                "premise_dependencies": sorted(deps),
            }
            receipt = {**receipt_core, "receipt_hash": sha256_json(receipt_core)}
            instruction_receipts.append(receipt)
            session._freeze("faithful.step", index, receipt)
        final = _nonempty(final_register, "Faithful final_register")
        if final not in registers or not dependencies[final]:
            raise P0LoopError("Faithful final answer must depend on at least one source premise")
        proof_core = {
            "source_hashes": source_hashes,
            "premises": premise_receipts,
            "instructions": instruction_receipts,
            "final_register": final,
            "final_answer_hash": sha256_json(registers[final]),
            "final_dependencies": sorted(dependencies[final]),
        }
        return session.finish(
            "COMPLETED",
            reason="typed IR deterministically derived the final answer",
            extra={
                "final_answer": registers[final],
                "final_register": final,
                "premise_dependencies": sorted(dependencies[final]),
                "proof": {**proof_core, "proof_hash": sha256_json(proof_core)},
            },
        )
    except (_ControlledStop, P0LoopError) as exc:
        controlled = exc if isinstance(exc, _ControlledStop) else _ControlledStop(str(exc))
        return _failed(session, controlled, instruction_receipts=instruction_receipts)


MEMORY_AXES = {
    "ACCURATE_RETRIEVAL",
    "TEST_TIME_LEARNING",
    "LONG_RANGE_UNDERSTANDING",
    "SELECTIVE_FORGETTING",
}


def run_chronological_memory_benchmark(
    cases: Sequence[Mapping[str, Any]],
    *,
    adapter_factory: Callable[[str], Callback],
    baseline_budget: Mapping[str, Any],
    minimum_rate: float = 1.0,
    budget_tolerance: float = 0.02,
    faults: Sequence[str] = (),
) -> dict[str, Any]:
    """Run four-axis incremental histories against isolated injected adapters."""
    if not cases:
        raise P0LoopError("memory benchmark requires cases")
    if isinstance(minimum_rate, bool) or not isinstance(minimum_rate, (int, float)):
        raise P0LoopError("memory benchmark minimum_rate must be numeric")
    minimum_rate = float(minimum_rate)
    if not 0.0 <= minimum_rate <= 1.0:
        raise P0LoopError("memory benchmark minimum_rate must be within [0, 1]")
    session = _Session("MEMORY_BENCH", baseline_budget, budget_tolerance=budget_tolerance, faults=faults)
    rows: list[dict[str, Any]] = []
    seen_cases: set[str] = set()
    totals = {axis: 0 for axis in MEMORY_AXES}
    passed = {axis: 0 for axis in MEMORY_AXES}
    manifest: list[dict[str, Any]] = []
    adapters: list[Callback] = []
    try:
        for raw_case in cases:
            if not isinstance(raw_case, Mapping):
                raise _ControlledStop("memory benchmark case must be an object")
            case_id = _nonempty(raw_case.get("case_id"), "memory benchmark case_id")
            if case_id in seen_cases:
                raise _ControlledStop(f"duplicate memory benchmark case: {case_id}")
            seen_cases.add(case_id)
            axis = _nonempty(raw_case.get("competency"), f"memory case {case_id} competency").upper()
            if axis not in MEMORY_AXES:
                raise _ControlledStop(f"memory case {case_id} has an invalid competency")
            chunks = raw_case.get("chunks")
            if not isinstance(chunks, list) or not chunks:
                raise _ControlledStop(f"memory case {case_id} requires chronological chunks")
            query_at = _parse_time(raw_case.get("query_at"), f"memory case {case_id} query_at")
            normalized_chunks: list[dict[str, Any]] = []
            prior_time: dt.datetime | None = None
            source_ids: set[str] = set()
            for chunk in chunks:
                if not isinstance(chunk, Mapping):
                    raise _ControlledStop(f"memory case {case_id} chunk must be an object")
                source_id = _nonempty(chunk.get("source_id"), f"memory case {case_id} source_id")
                if source_id in source_ids:
                    raise _ControlledStop(f"memory case {case_id} has duplicate source ids")
                source_ids.add(source_id)
                observed = _parse_time(chunk.get("observed_at"), f"memory case {case_id} observed_at")
                if (prior_time is not None and observed <= prior_time) or observed > query_at:
                    raise _ControlledStop(f"memory case {case_id} chronology is invalid")
                prior_time = observed
                payload = _clone(chunk.get("payload"), f"memory case {case_id} source payload")
                source_hash = str(chunk.get("source_hash") or "")
                if not SHA256_RE.fullmatch(source_hash) or source_hash != sha256_json(payload):
                    raise _ControlledStop(f"memory case {case_id} source hash mismatch")
                normalized_chunks.append({
                    "source_id": source_id,
                    "observed_at": observed.isoformat().replace("+00:00", "Z"),
                    "payload": payload,
                    "source_hash": source_hash,
                })
            expected_refs = set(_string_list(
                raw_case.get("expected_source_ids"),
                f"memory case {case_id} expected_source_ids",
            ))
            forbidden_refs = set(_string_list(
                raw_case.get("forbidden_source_ids", []),
                f"memory case {case_id} forbidden_source_ids",
                allow_empty=True,
            ))
            if expected_refs - source_ids or forbidden_refs - source_ids or expected_refs & forbidden_refs:
                raise _ControlledStop(f"memory case {case_id} source expectations are invalid")
            if axis == "SELECTIVE_FORGETTING" and not forbidden_refs:
                raise _ControlledStop("selective-forgetting case requires forbidden obsolete sources")
            query = raw_case.get("query")
            if not isinstance(query, Mapping):
                raise _ControlledStop(f"memory case {case_id} query must be an object")
            try:
                adapter = adapter_factory(case_id)
            except Exception as exc:
                raise _ControlledStop(f"memory adapter factory failed for {case_id}") from exc
            if not callable(adapter):
                raise _ControlledStop("memory adapter factory must return a fresh callback")
            if any(adapter is prior for prior in adapters):
                raise _ControlledStop("memory adapter factory reused state across cases")
            adapters.append(adapter)
            for chunk in normalized_chunks:
                ingest, _ = session.call(
                    "memory.ingest",
                    adapter,
                    {"operation": "INGEST", "case_id": case_id, "chunk": chunk},
                )
                if ingest.get("accepted") is not True:
                    raise _ControlledStop(f"memory adapter rejected an ingest for {case_id}")
            answer, answer_artifact = session.call(
                "memory.query",
                adapter,
                {
                    "operation": "QUERY",
                    "case_id": case_id,
                    "query_at": query_at.isoformat().replace("+00:00", "Z"),
                    "query": _clone(dict(query), f"memory case {case_id} query"),
                },
            )
            cited = set(_string_list(
                answer.get("source_ids", []),
                f"memory case {case_id} returned source_ids",
                allow_empty=True,
            ))
            provenance_ok = not (cited - source_ids) and expected_refs <= cited and not (cited & forbidden_refs)
            exact = answer.get("answer") == raw_case.get("expected_answer")
            case_passed = exact and provenance_ok and answer.get("abstained") is not True
            totals[axis] += 1
            passed[axis] += int(case_passed)
            row_core = {
                "case_id": case_id,
                "competency": axis,
                "passed": case_passed,
                "exact_answer": exact,
                "provenance_ok": provenance_ok,
                "obsolete_memory_used": bool(cited & forbidden_refs),
                "answer_artifact_hash": answer_artifact["artifact_hash"],
            }
            rows.append({**row_core, "row_hash": sha256_json(row_core)})
            manifest.append({
                "case_id": case_id,
                "competency": axis,
                "source_hashes": [chunk["source_hash"] for chunk in normalized_chunks],
                "query_hash": sha256_json(dict(query)),
                "expected_answer_hash": sha256_json(raw_case.get("expected_answer")),
                "expected_source_ids": sorted(expected_refs),
                "forbidden_source_ids": sorted(forbidden_refs),
            })
        missing_axes = sorted(axis for axis, count in totals.items() if count == 0)
        rates = {
            axis: (passed[axis] / totals[axis] if totals[axis] else 0.0)
            for axis in sorted(MEMORY_AXES)
        }
        blockers = []
        if missing_axes:
            blockers.append("missing competencies: " + ", ".join(missing_axes))
        below = sorted(axis for axis, rate in rates.items() if rate < minimum_rate)
        if below:
            blockers.append("competencies below minimum rate: " + ", ".join(below))
        if any(not row["provenance_ok"] for row in rows):
            blockers.append("provenance or obsolete-memory use failed")
        return session.finish(
            "COMPLETED" if not blockers else "REJECTED",
            reason="four-axis chronological benchmark passed" if not blockers else "; ".join(blockers),
            extra={
                "rows": rows,
                "rates": rates,
                "counts": {axis: totals[axis] for axis in sorted(MEMORY_AXES)},
                "minimum_rate": minimum_rate,
                "case_manifest_hash": sha256_json(manifest),
                "benchmark_only": True,
                "memory_architecture": "NONE",
            },
        )
    except _ControlledStop as exc:
        return _failed(session, exc, rows=rows, case_manifest_hash=sha256_json(manifest))
