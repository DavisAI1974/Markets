#!/usr/bin/env python3
"""Matched-budget SHADOW experiment registry for Frankie's cognitive top ten."""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from frankie_cognition import CognitiveContractError, sha256_json

EXPERIMENT_SCHEMA_VERSION = "1.3"
BUDGET_DIMENSIONS = (
    "model_calls",
    "input_tokens",
    "output_tokens",
    "tool_queries",
    "storage_bytes",
    "wall_clock_ms",
)
REQUIRED_STRATA = ("task", "regime", "safety", "provenance")
MIN_EVALUATION_CASES = 30
MIN_FAIL_TO_PASS_CASES = 5
MIN_OBSERVED_STRATUM_CASES = 5


@dataclass(frozen=True)
class MetricRule:
    name: str
    direction: str
    role: str
    min_improvement: float = 0.0
    max_regression: float = 0.0


@dataclass(frozen=True)
class CognitiveExperiment:
    rank: int
    candidate_id: str
    paper: str
    venue: str
    component: str
    hypothesis: str
    control: str
    intervention: str
    falsifiers: tuple[str, ...]
    metric_rules: tuple[MetricRule, ...]
    implementation_targets: tuple[str, ...]
    authority: str = "SHADOW_ONLY"
    execution_enabled: bool = False
    automatic_apply: bool = False

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _metric(name: str, direction: str, role: str, *, improve: float = 0.0, regress: float = 0.0) -> MetricRule:
    return MetricRule(name, direction, role, improve, regress)


EXPERIMENTS = (
    CognitiveExperiment(
        1,
        "COG01_COALA_ARCHITECTURE_MAP",
        "Cognitive Architectures for Language Agents",
        "TMLR 2024",
        "cognitive ownership and typed state",
        "Explicit memory/action ownership reduces cross-lane state faults without changing good decisions.",
        "current Frankie packet and lane boundaries",
        "typed CoALA map and read-only cognitive context",
        ("any new authority", "any decision change", "incomplete instrumentation coverage"),
        (
            _metric("instrumentation_coverage", "HIGHER", "PRIMARY", improve=0.01),
            _metric("task_success", "HIGHER", "GUARDRAIL"),
            _metric("provenance_coverage", "HIGHER", "GUARDRAIL"),
            _metric("cross_lane_fault_rate", "LOWER", "GUARDRAIL"),
        ),
        ("frankie_cognition.build_cognitive_context", "frankie_cognitive_candidates.coala_architecture_map"),
    ),
    CognitiveExperiment(
        2,
        "COG02_REACT_EVIDENCE_LOOP",
        "ReAct: Synergizing Reasoning and Acting in Language Models",
        "ICLR 2023",
        "reason-action-observation loop",
        "Bounded typed evidence loops recover missing facts without increasing unsupported claims.",
        "current one-pass lane reasoning",
        "bounded OBSERVE/RETRIEVE/REASON/VERIFY trace",
        ("unused retrieval", "unauthorized action", "more pass-to-fail cases"),
        (
            _metric("task_success", "HIGHER", "PRIMARY", improve=0.01),
            _metric("unsupported_claim_rate", "LOWER", "GUARDRAIL"),
            _metric("invalid_action_rate", "LOWER", "GUARDRAIL"),
        ),
        ("frankie_cognition.validate_reasoning_contract", "frankie_cognitive_candidates.validate_react_trace"),
    ),
    CognitiveExperiment(
        3,
        "COG03_LATS_BOUNDED_PLAN_SEARCH",
        "Language Agent Tree Search",
        "ICML 2024",
        "bounded multi-path planning",
        "A shallow externally scored hypothesis tree recovers early wrong paths at matched budget.",
        "current independent linear candidate drafts",
        "fixed-width/fixed-depth plan branches with external feedback",
        ("self-owned value score", "budget excess", "hallucinated evidence increases"),
        (
            _metric("executable_grader_success", "HIGHER", "PRIMARY", improve=0.01),
            _metric("hallucinated_evidence_rate", "LOWER", "GUARDRAIL"),
            _metric("abstention_quality", "HIGHER", "GUARDRAIL"),
        ),
        ("frankie_cognitive_candidates.select_bounded_plan_branches",),
    ),
    CognitiveExperiment(
        4,
        "COG04_STRUCTGPT_TYPED_READS",
        "StructGPT",
        "EMNLP 2023",
        "typed structured evidence access",
        "Narrow typed reads improve evidence recall and citation correctness without forbidden access.",
        "current serialized evidence packet",
        "read-only evidence catalog queried by exact ref id",
        ("future or forbidden field access", "unknown ref", "provenance loss"),
        (
            _metric("evidence_recall", "HIGHER", "PRIMARY", improve=0.01),
            _metric("citation_correctness", "HIGHER", "GUARDRAIL"),
            _metric("forbidden_access_rate", "LOWER", "GUARDRAIL"),
        ),
        ("frankie_cognitive_candidates.TypedEvidenceStore",),
    ),
    CognitiveExperiment(
        5,
        "COG05_FAITHFUL_EXECUTABLE_REASONING",
        "Faithful Chain-of-Thought Reasoning",
        "IJCNLP-AACL 2023",
        "executable mechanical reasoning",
        "Allowlisted deterministic checks reduce silent arithmetic/clock/contract errors.",
        "free-form reasoning for checkable steps",
        "typed check specification and deterministic execution",
        ("false premise treated as proof", "non-allowlisted check", "task regression"),
        (
            _metric("executable_validity", "HIGHER", "PRIMARY", improve=0.01),
            _metric("silent_error_rate", "LOWER", "GUARDRAIL"),
            _metric("task_success", "HIGHER", "GUARDRAIL"),
        ),
        ("frankie_cognitive_candidates.run_deterministic_check",),
    ),
    CognitiveExperiment(
        6,
        "COG06_CRITIC_TOOL_VERIFICATION",
        "CRITIC",
        "ICLR 2024",
        "tool-grounded verification",
        "External deterministic checks correct more failures than they introduce.",
        "one-pass output and feedback-free self-critique",
        "bounded verify-then-revise disposable candidate",
        ("unsupported revision", "immutable evidence mutation", "introduced failure"),
        (
            _metric("corrected_failure_rate", "HIGHER", "PRIMARY", improve=0.01),
            _metric("introduced_failure_rate", "LOWER", "GUARDRAIL"),
            _metric("unsupported_revision_rate", "LOWER", "GUARDRAIL"),
        ),
        ("frankie_cognitive_candidates.run_deterministic_check", "frankie_cognition.ReasoningStep"),
    ),
    CognitiveExperiment(
        7,
        "COG07_MEMORY_AGENT_BENCH",
        "Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions",
        "ICLR 2026",
        "four-competency memory evaluation",
        "Memory changes can improve all competencies without stale or untraceable recall.",
        "current memory serving",
        "sealed retrieval/learning/long-range/forgetting scorecard",
        ("obsolete memory use", "provenance failure", "any omitted competency"),
        (
            _metric("memory_macro_accuracy", "HIGHER", "PRIMARY", improve=0.01),
            _metric("obsolete_memory_rate", "LOWER", "GUARDRAIL"),
            _metric("provenance_failure_rate", "LOWER", "GUARDRAIL"),
        ),
        ("frankie_cognition.select_active_memories", "frankie_cognitive_candidates.score_memory_competencies"),
    ),
    CognitiveExperiment(
        8,
        "COG08_HIPPORAG_ASSOCIATIVE_RETRIEVAL",
        "HippoRAG",
        "NeurIPS 2024",
        "associative graph retrieval",
        "Active-only graph retrieval improves attributed multi-hop recall at the same serving budget.",
        "current lexical/vector retrieval",
        "provenance graph plus deterministic Personalized PageRank",
        ("graph proximity asserted as causality", "invalidated node served", "citation regression"),
        (
            _metric("multihop_accuracy", "HIGHER", "PRIMARY", improve=0.01),
            _metric("stale_node_rate", "LOWER", "GUARDRAIL"),
            _metric("citation_correctness", "HIGHER", "GUARDRAIL"),
        ),
        ("frankie_cognitive_candidates.rank_associative_memory",),
    ),
    CognitiveExperiment(
        9,
        "COG09_HIAGENT_WORKING_MEMORY",
        "HiAgent",
        "ACL 2025",
        "hierarchical working memory",
        "Subgoal chunks preserve evidence while improving long-run completion and recovery.",
        "full undifferentiated action-observation history",
        "one-active-subgoal working-memory chunks",
        ("lost evidence ref", "decision changed by compaction", "multiple active subgoals"),
        (
            _metric("task_success", "HIGHER", "PRIMARY", improve=0.01),
            _metric("omitted_evidence_rate", "LOWER", "GUARDRAIL"),
            _metric("interruption_recovery", "HIGHER", "GUARDRAIL"),
        ),
        ("frankie_cognition.validate_working_memory",),
    ),
    CognitiveExperiment(
        10,
        "COG10_PROGRESS_COMPRESS_SHADOW_LEARNING",
        "Progress & Compress",
        "ICML 2018",
        "protected continual learning",
        "A disposable active candidate can improve a new regime without old-cohort regression.",
        "frozen permanent Frankie",
        "shadow learner followed by separately controlled consolidation evaluation",
        ("any protected regression", "holdout reuse", "candidate controls evaluator or promotion"),
        (
            _metric("new_regime_success", "HIGHER", "PRIMARY", improve=0.01),
            _metric("old_cohort_success", "HIGHER", "GUARDRAIL"),
            _metric("forgetting_rate", "LOWER", "GUARDRAIL"),
            _metric("rollback_fidelity", "HIGHER", "GUARDRAIL"),
        ),
        ("frankie_evolution.evaluate_release",),
    ),
)

EXPERIMENT_BY_ID = {experiment.candidate_id: experiment for experiment in EXPERIMENTS}

# Honest implementation-depth audit.  A pure helper, validator, prompt contract,
# or release gate is not the paper's behavioral method.  This map is part of the
# hashed manifest so experiment consumers cannot silently equate scaffolding with
# a paper-faithful implementation.
IMPLEMENTATION_AUDIT: dict[str, dict[str, Any]] = {
    "COG01_COALA_ARCHITECTURE_MAP": {
        "depth": "GENERIC_CONTRACT_INTEGRATED",
        "runtime_invoked": ["build_cognitive_context", "validate_reasoning_contract"],
        "implemented_plumbing": [
            "instrumentation coverage is evaluated separately from task behavior",
            "paired rows require identical behavior projections",
        ],
        "paper_method_not_implemented": ["decision-cycle policy", "memory learning actions"],
    },
    "COG02_REACT_EVIDENCE_LOOP": {
        "depth": "BOUNDED_LOOP_RUNTIME_HOOK_NOT_GROUP_RUNNER_WIRED",
        "runtime_invoked": ["validate_react_trace", "run_p0_component.run_bounded_react"],
        "implemented_plumbing": [
            "every REASON step requires a transitive OBSERVE/RETRIEVE dependency path",
            "every retrieval must feed later reasoning or verification",
        ],
        "paper_method_not_implemented": [
            "paper prompts/environment",
            "learned action policy",
            "automatic standard group-runner integration",
        ],
    },
    "COG03_LATS_BOUNDED_PLAN_SEARCH": {
        "depth": "BOUNDED_SEARCH_RUNTIME_HOOK_NOT_GROUP_RUNNER_WIRED",
        "runtime_invoked": ["run_p0_component.run_bounded_lats_search"],
        "implemented_plumbing": [
            "selection, expansion, simulation, value, reflection, and backpropagation are distinct bounded stages",
            "tree and one-path controls bind exact six-dimensional matched budgets",
            "selection is ancestry-closed and pruned parents cannot leave selected orphan descendants",
        ],
        "paper_method_not_implemented": [
            "paper prompts and learned policy/value model",
            "paper benchmark replication",
            "automatic standard group-runner integration",
        ],
    },
    "COG04_STRUCTGPT_TYPED_READS": {
        "depth": "BOUNDED_LOOP_RUNTIME_HOOK_NOT_GROUP_RUNNER_WIRED",
        "runtime_invoked": [
            "TypedEvidenceStore",
            "TypedEvidenceStore.read",
            "run_p0_component.run_iterative_structured_reads",
        ],
        "implemented_plumbing": [
            "runtime packet catalog is hash-bound, active, immutable, exact-ref, and read-only",
            "candidate citations are re-read through the typed store during output validation",
        ],
        "paper_method_not_implemented": [
            "paper KG/table/database interfaces",
            "trained model-directed retrieval policy",
            "automatic standard group-runner integration",
        ],
    },
    "COG05_FAITHFUL_EXECUTABLE_REASONING": {
        "depth": "BOUNDED_IR_RUNTIME_HOOK_NOT_GROUP_RUNNER_WIRED",
        "runtime_invoked": [
            "run_deterministic_check",
            "run_p0_component.execute_faithful_ir",
        ],
        "implemented_plumbing": ["check receipts hash exact inputs, evidence refs, and result"],
        "paper_method_not_implemented": [
            "language-to-symbolic translation",
            "general Python/Datalog/PDDL solver execution",
        ],
    },
    "COG06_CRITIC_TOOL_VERIFICATION": {
        "depth": "BOUNDED_LOOP_RUNTIME_HOOK_NOT_GROUP_RUNNER_WIRED",
        "runtime_invoked": [
            "run_deterministic_check",
            "run_p0_component.run_critic_revision",
        ],
        "implemented_plumbing": ["check receipts hash exact inputs, evidence refs, and result"],
        "paper_method_not_implemented": [
            "paper prompts and external tools",
            "trained critique/revision policy",
            "automatic standard group-runner integration",
        ],
    },
    "COG07_MEMORY_AGENT_BENCH": {
        "depth": "BENCHMARK_RUNTIME_HOOK_NOT_GROUP_RUNNER_WIRED",
        "runtime_invoked": ["run_p0_component.run_chronological_memory_benchmark"],
        "implemented_plumbing": [
            "each competency has an explicit minimum-rate gate",
            "withdrawal receipts bind records, invalidations, reasons, and descendant paths",
        ],
        "paper_method_not_implemented": [
            "MemoryAgentBench corpus replication",
            "four-competency runtime memory architecture",
            "LLM judge",
        ],
    },
    "COG08_HIPPORAG_ASSOCIATIVE_RETRIEVAL": {
        "depth": "BOUNDED_RETRIEVAL_RUNTIME_HOOK_NOT_GROUP_RUNNER_WIRED",
        "runtime_invoked": ["run_p0_component.run_hipporag_shadow_pipeline"],
        "implemented_plumbing": [
            "source-bound extraction proposals, associative graph construction, PPR, top-k selection, and cited reader output",
            "point-in-time, target-birth, invalidation-closure, provenance-path, and matched flat-control receipts",
            "graph associations explicitly carry no causal authority",
        ],
        "paper_method_not_implemented": [
            "paper-exact extraction/entity-linking stack and trained reader",
            "paper benchmark replication",
            "automatic standard group-runner integration",
        ],
    },
    "COG09_HIAGENT_WORKING_MEMORY": {
        "depth": "BOUNDED_STATE_MACHINE_RUNTIME_HOOK_NOT_GROUP_RUNNER_WIRED",
        "runtime_invoked": ["run_p0_component.run_state_aware_working_memory"],
        "paper_method_not_implemented": [
            "model-generated subgoals/summaries",
            "learned retrieval policy",
            "automatic standard group-runner integration",
        ],
    },
    "COG10_PROGRESS_COMPRESS_SHADOW_LEARNING": {
        "depth": "BOUNDED_LIFECYCLE_RUNTIME_HOOK_NOT_GROUP_RUNNER_WIRED",
        "runtime_invoked": ["run_p0_component.run_progress_compress_shadow"],
        "implemented_plumbing": [
            "immutable protected knowledge base, disposable active phase, teacher targets, distillation/EWC proposal, protected retention, and rollback",
            "sequential reveal/release firewall plus evaluator and contamination bindings",
        ],
        "paper_method_not_implemented": [
            "externally proven gradients, distillation, and Fisher estimation",
            "live model consolidation or weight update",
            "automatic standard group-runner integration",
        ],
    },
}


def experiment_manifest() -> dict[str, Any]:
    if len(EXPERIMENTS) != 10 or len(EXPERIMENT_BY_ID) != 10:
        raise CognitiveContractError("cognitive experiment registry must contain ten unique candidates")
    if sorted(experiment.rank for experiment in EXPERIMENTS) != list(range(1, 11)):
        raise CognitiveContractError("cognitive experiment ranks must be exactly 1 through 10")
    candidates = [
        {**experiment.as_dict(), "implementation_audit": IMPLEMENTATION_AUDIT[experiment.candidate_id]}
        for experiment in EXPERIMENTS
    ]
    core = {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "status": "SHADOW_ONLY",
        "baseline": "FROZEN_CURRENT_FRANKIE",
        "budget_dimensions": BUDGET_DIMENSIONS,
        "required_strata": REQUIRED_STRATA,
        "minimum_evidence": {
            "cases": MIN_EVALUATION_CASES,
            "fail_to_pass": MIN_FAIL_TO_PASS_CASES,
            "observed_stratum_cases": MIN_OBSERVED_STRATUM_CASES,
        },
        "current_frankie_runtime_adapter": "frankie_s137_cognitive_runtime.CognitiveCandidateRuntime",
        "row_schema": "research/kalshi/frankie_cognitive_experiment_row_schema.json",
        "candidates": candidates,
        "execution_enabled": False,
        "automatic_apply": False,
    }
    return {**core, "manifest_hash": sha256_json(core)}


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CognitiveContractError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise CognitiveContractError(f"{label} must be finite")
    return number


def evaluate_shadow_candidate(
    candidate_id: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    budget_tolerance: float = 0.02,
    required_stratum_values: Mapping[str, Sequence[str]] | None = None,
    required_joint_strata: Sequence[Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Evaluate one cognitive candidate; passing never authorizes promotion."""
    experiment = EXPERIMENT_BY_ID.get(candidate_id)
    if experiment is None:
        raise CognitiveContractError(f"unknown cognitive candidate: {candidate_id}")
    if not 0.0 <= budget_tolerance <= 0.10:
        raise CognitiveContractError("budget tolerance must be within [0, 0.10]")
    if not rows:
        raise CognitiveContractError("shadow evaluation requires cases")

    metric_pairs = {rule.name: [[], []] for rule in experiment.metric_rules}
    seen: set[str] = set()
    pass_to_fail = 0
    fail_to_pass = 0
    budget_violations: list[str] = []
    catastrophic: list[str] = []
    protected_failures: list[str] = []
    behavior_changes: list[str] = []
    stratum_counts: dict[str, dict[str, int]] = {name: {} for name in REQUIRED_STRATA}
    evaluated_rows: list[dict[str, Any]] = []

    expected_strata: dict[str, tuple[str, ...]] = {}
    expected_joint_strata: tuple[tuple[str, ...], ...] = ()
    if required_stratum_values is not None:
        if not isinstance(required_stratum_values, Mapping):
            raise CognitiveContractError("required_stratum_values must be an object")
        unknown_dimensions = sorted(set(required_stratum_values) - set(REQUIRED_STRATA))
        if unknown_dimensions:
            raise CognitiveContractError(
                "unknown required stratum dimensions: " + ", ".join(unknown_dimensions)
            )
        for name in REQUIRED_STRATA:
            raw_values = required_stratum_values.get(name)
            if not isinstance(raw_values, Sequence) or isinstance(raw_values, (str, bytes)):
                raise CognitiveContractError(f"required stratum {name} must be a sequence")
            values = tuple(dict.fromkeys(str(value).strip() for value in raw_values))
            if not values or any(not value for value in values):
                raise CognitiveContractError(f"required stratum {name} cannot be empty")
            expected_strata[name] = values
    if required_joint_strata is not None:
        if not isinstance(required_joint_strata, Sequence) or isinstance(
            required_joint_strata, (str, bytes)
        ):
            raise CognitiveContractError("required_joint_strata must be a sequence")
        normalized_joint: list[tuple[str, ...]] = []
        for index, raw in enumerate(required_joint_strata):
            if not isinstance(raw, Mapping) or set(raw) != set(REQUIRED_STRATA):
                raise CognitiveContractError(
                    f"required joint stratum {index} must contain exactly {REQUIRED_STRATA}"
                )
            cell = tuple(str(raw[name]).strip() for name in REQUIRED_STRATA)
            if any(not value for value in cell):
                raise CognitiveContractError(f"required joint stratum {index} is empty")
            normalized_joint.append(cell)
        expected_joint_strata = tuple(dict.fromkeys(normalized_joint))
        if not expected_joint_strata:
            raise CognitiveContractError("required_joint_strata cannot be empty")

    for row in rows:
        case_id = str(row.get("case_id") or "").strip()
        if not case_id or case_id in seen:
            raise CognitiveContractError("shadow rows require unique non-empty case_id")
        seen.add(case_id)
        baseline_pass = row.get("baseline_pass")
        candidate_pass = row.get("candidate_pass")
        if not isinstance(baseline_pass, bool) or not isinstance(candidate_pass, bool):
            raise CognitiveContractError(f"shadow case {case_id} requires boolean pass states")
        pass_to_fail += int(baseline_pass and not candidate_pass)
        fail_to_pass += int(not baseline_pass and candidate_pass)
        if bool(row.get("candidate_catastrophic", False)):
            catastrophic.append(case_id)
        if bool(row.get("protected", False)):
            if not baseline_pass:
                raise CognitiveContractError(f"protected case {case_id} must pass on the frozen baseline")
            if not candidate_pass:
                protected_failures.append(case_id)
        if candidate_id == "COG01_COALA_ARCHITECTURE_MAP":
            baseline_behavior_hash = str(row.get("baseline_behavior_hash") or "")
            candidate_behavior_hash = str(row.get("candidate_behavior_hash") or "")
            if not all(
                len(value) == 64 and all(character in "0123456789abcdef" for character in value)
                for value in (baseline_behavior_hash, candidate_behavior_hash)
            ):
                raise CognitiveContractError(
                    f"COG01 case {case_id} requires behavior SHA-256 hashes"
                )
            if baseline_behavior_hash != candidate_behavior_hash:
                behavior_changes.append(case_id)

        strata = row.get("strata")
        if not isinstance(strata, Mapping):
            raise CognitiveContractError(f"shadow case {case_id} requires strata")
        for name in REQUIRED_STRATA:
            value = str(strata.get(name) or "").strip()
            if not value:
                raise CognitiveContractError(f"shadow case {case_id} missing stratum {name}")
            stratum_counts[name][value] = stratum_counts[name].get(value, 0) + 1

        baseline_budget = row.get("baseline_budget")
        candidate_budget = row.get("candidate_budget")
        if not isinstance(baseline_budget, Mapping) or not isinstance(candidate_budget, Mapping):
            raise CognitiveContractError(f"shadow case {case_id} requires matched budgets")
        for dimension in BUDGET_DIMENSIONS:
            baseline_value = _number(baseline_budget.get(dimension), f"{case_id} baseline {dimension}")
            candidate_value = _number(candidate_budget.get(dimension), f"{case_id} candidate {dimension}")
            if baseline_value < 0 or candidate_value < 0:
                raise CognitiveContractError(f"shadow case {case_id} budgets cannot be negative")
            ceiling = baseline_value * (1.0 + budget_tolerance)
            if candidate_value > ceiling + 1e-9:
                budget_violations.append(f"{case_id}:{dimension}")

        baseline_metrics = row.get("baseline_metrics")
        candidate_metrics = row.get("candidate_metrics")
        if not isinstance(baseline_metrics, Mapping) or not isinstance(candidate_metrics, Mapping):
            raise CognitiveContractError(f"shadow case {case_id} requires metric maps")
        row_baseline_metrics: dict[str, float] = {}
        row_candidate_metrics: dict[str, float] = {}
        for rule in experiment.metric_rules:
            baseline_value = _number(
                baseline_metrics.get(rule.name),
                f"{case_id} baseline metric {rule.name}",
            )
            candidate_value = _number(
                candidate_metrics.get(rule.name),
                f"{case_id} candidate metric {rule.name}",
            )
            metric_pairs[rule.name][0].append(baseline_value)
            metric_pairs[rule.name][1].append(candidate_value)
            row_baseline_metrics[rule.name] = baseline_value
            row_candidate_metrics[rule.name] = candidate_value
        evaluated_rows.append({
            "case_id": case_id,
            "strata": {name: str(strata[name]).strip() for name in REQUIRED_STRATA},
            "baseline_metrics": row_baseline_metrics,
            "candidate_metrics": row_candidate_metrics,
        })

    metric_results: dict[str, Any] = {}
    blockers: list[str] = []
    if len(rows) < MIN_EVALUATION_CASES:
        blockers.append(
            f"insufficient cases: {len(rows)} < {MIN_EVALUATION_CASES}"
        )
    sparse_strata = [
        f"{name}={value}:{count}"
        for name, values in stratum_counts.items()
        for value, count in values.items()
        if count < MIN_OBSERVED_STRATUM_CASES
    ]
    if sparse_strata:
        blockers.append(
            "under-supported observed strata: " + ", ".join(sorted(sparse_strata))
        )
    missing_predeclared = [
        f"{name}={value}"
        for name, values in expected_strata.items()
        for value in values
        if value not in stratum_counts[name]
    ]
    if missing_predeclared:
        blockers.append(
            "missing predeclared strata: " + ", ".join(sorted(missing_predeclared))
        )
    observed_joint_cells = {
        tuple(row["strata"][name] for name in REQUIRED_STRATA)
        for row in evaluated_rows
    }
    missing_joint = sorted(set(expected_joint_strata) - observed_joint_cells)
    if missing_joint:
        blockers.append(
            "missing predeclared joint strata: "
            + ", ".join("|".join(cell) for cell in missing_joint)
        )
    for rule in experiment.metric_rules:
        baseline_mean = sum(metric_pairs[rule.name][0]) / len(rows)
        candidate_mean = sum(metric_pairs[rule.name][1]) / len(rows)
        improvement = (
            candidate_mean - baseline_mean if rule.direction == "HIGHER" else baseline_mean - candidate_mean
        )
        passed = (
            improvement >= rule.min_improvement
            if rule.role == "PRIMARY"
            else improvement >= -rule.max_regression
        )
        metric_results[rule.name] = {
            "baseline_mean": baseline_mean,
            "candidate_mean": candidate_mean,
            "direction": rule.direction,
            "role": rule.role,
            "improvement": improvement,
            "passed": passed,
        }
        if not passed:
            blockers.append(f"metric gate failed: {rule.name}")

    stratum_metric_results: dict[str, dict[str, dict[str, Any]]] = {
        name: {} for name in REQUIRED_STRATA
    }
    for dimension in REQUIRED_STRATA:
        for value in sorted(stratum_counts[dimension]):
            cohort = [
                row for row in evaluated_rows if row["strata"][dimension] == value
            ]
            cohort_results: dict[str, Any] = {}
            for rule in experiment.metric_rules:
                baseline_mean = sum(
                    row["baseline_metrics"][rule.name] for row in cohort
                ) / len(cohort)
                candidate_mean = sum(
                    row["candidate_metrics"][rule.name] for row in cohort
                ) / len(cohort)
                improvement = (
                    candidate_mean - baseline_mean
                    if rule.direction == "HIGHER"
                    else baseline_mean - candidate_mean
                )
                passed = improvement >= -rule.max_regression
                cohort_results[rule.name] = {
                    "cases": len(cohort),
                    "baseline_mean": baseline_mean,
                    "candidate_mean": candidate_mean,
                    "improvement": improvement,
                    "max_regression": rule.max_regression,
                    "passed": passed,
                }
                if not passed:
                    blockers.append(
                        f"stratum metric regression: {dimension}={value}:{rule.name}"
                    )
            stratum_metric_results[dimension][value] = cohort_results

    joint_stratum_metric_results: dict[str, dict[str, Any]] = {}
    for cell in sorted(observed_joint_cells):
        cohort = [
            row
            for row in evaluated_rows
            if tuple(row["strata"][name] for name in REQUIRED_STRATA) == cell
        ]
        cell_label = "|".join(cell)
        cell_results: dict[str, Any] = {}
        for rule in experiment.metric_rules:
            baseline_mean = sum(
                row["baseline_metrics"][rule.name] for row in cohort
            ) / len(cohort)
            candidate_mean = sum(
                row["candidate_metrics"][rule.name] for row in cohort
            ) / len(cohort)
            improvement = (
                candidate_mean - baseline_mean
                if rule.direction == "HIGHER"
                else baseline_mean - candidate_mean
            )
            passed = improvement >= -rule.max_regression
            cell_results[rule.name] = {
                "cases": len(cohort),
                "baseline_mean": baseline_mean,
                "candidate_mean": candidate_mean,
                "improvement": improvement,
                "max_regression": rule.max_regression,
                "passed": passed,
            }
            if not passed:
                blockers.append(
                    f"joint-stratum metric regression: {cell_label}:{rule.name}"
                )
        joint_stratum_metric_results[cell_label] = cell_results

    if pass_to_fail:
        blockers.append(f"{pass_to_fail} pass-to-fail regressions")
    if fail_to_pass < MIN_FAIL_TO_PASS_CASES:
        blockers.append(
            f"insufficient fail-to-pass evidence: {fail_to_pass} < {MIN_FAIL_TO_PASS_CASES}"
        )
    if budget_violations:
        blockers.append(f"{len(budget_violations)} matched-budget violations")
    if catastrophic:
        blockers.append(f"{len(catastrophic)} catastrophic candidate failures")
    if protected_failures:
        blockers.append(f"{len(protected_failures)} protected-case failures")
    if behavior_changes:
        blockers.append(f"{len(behavior_changes)} COG01 behavior changes")

    core = {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "experiment_rank": experiment.rank,
        "evaluation_policy_hash": sha256_json({
            "experiment": experiment.as_dict(),
            "budget_tolerance": budget_tolerance,
            "minimum_cases": MIN_EVALUATION_CASES,
            "minimum_fail_to_pass": MIN_FAIL_TO_PASS_CASES,
            "minimum_observed_stratum_cases": MIN_OBSERVED_STRATUM_CASES,
            "required_stratum_values": expected_strata,
            "required_joint_strata": expected_joint_strata,
            "stratum_non_regression": True,
            "joint_stratum_non_regression": True,
        }),
        "row_hashes": [sha256_json(dict(row)) for row in rows],
        "row_set_hash": sha256_json([dict(row) for row in rows]),
        "cases": len(rows),
        "pass_to_fail": pass_to_fail,
        "fail_to_pass": fail_to_pass,
        "budget_violations": budget_violations,
        "catastrophic_cases": catastrophic,
        "protected_failures": protected_failures,
        "behavior_changes": behavior_changes,
        "stratum_counts": stratum_counts,
        "required_stratum_values": expected_strata,
        "required_joint_strata": expected_joint_strata,
        "stratum_metric_results": stratum_metric_results,
        "joint_stratum_metric_results": joint_stratum_metric_results,
        "minimum_cases_required": MIN_EVALUATION_CASES,
        "minimum_fail_to_pass_required": MIN_FAIL_TO_PASS_CASES,
        "minimum_observed_stratum_cases": MIN_OBSERVED_STRATUM_CASES,
        "metric_results": metric_results,
        "verdict": "COMPONENT_GATE_PASSED" if not blockers else "REJECT",
        "blockers": blockers,
        "next_gate": "UNTOUCHED_FORWARD_SHADOW" if not blockers else "REVISE_OR_DROP",
        "execution_enabled": False,
        "automatic_apply": False,
        "promotion_authority": "NONE",
    }
    return {**core, "evaluation_hash": sha256_json(core)}


def component_contract_canary() -> dict[str, Any]:
    """Exercise all ten evaluators with synthetic legal rows; this is not performance evidence."""
    budget = {dimension: 100.0 for dimension in BUDGET_DIMENSIONS}
    results = []
    for experiment in EXPERIMENTS:
        baseline_metrics = {rule.name: 0.5 for rule in experiment.metric_rules}
        candidate_metrics = {
            rule.name: (0.6 if rule.direction == "HIGHER" else 0.4)
            for rule in experiment.metric_rules
        }
        common = {
            "candidate_catastrophic": False,
            "baseline_behavior_hash": "a" * 64,
            "candidate_behavior_hash": "a" * 64,
            "strata": {
                "task": "contract-canary",
                "regime": "synthetic",
                "safety": "standard",
                "provenance": "complete",
            },
            "baseline_budget": budget,
            "candidate_budget": budget,
            "baseline_metrics": baseline_metrics,
            "candidate_metrics": candidate_metrics,
        }
        rows = []
        for index in range(MIN_EVALUATION_CASES):
            correction = index < MIN_FAIL_TO_PASS_CASES
            protected = MIN_FAIL_TO_PASS_CASES <= index < (2 * MIN_FAIL_TO_PASS_CASES)
            rows.append(
                {
                    **common,
                    "case_id": f"{experiment.candidate_id}-canary-{index:02d}",
                    "baseline_pass": not correction,
                    "candidate_pass": True,
                    "protected": protected,
                    "strata": {
                        **common["strata"],
                        "safety": "protected" if protected else "standard",
                    },
                }
            )
        evaluation = evaluate_shadow_candidate(experiment.candidate_id, rows)
        contract_passed = evaluation["verdict"] == "COMPONENT_GATE_PASSED"
        results.append(
            {
                "candidate_id": experiment.candidate_id,
                "verdict": "CONTRACT_CANARY_PASSED" if contract_passed else "REJECT",
                "next_gate": "HELD_OUT_COMPONENT_EVALUATION" if contract_passed else "REVISE_CONTRACT",
                "evaluation_hash": evaluation["evaluation_hash"],
            }
        )
    core = {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "status": "SYNTHETIC_COMPONENT_CONTRACT_CANARY_ONLY",
        "performance_evidence": False,
        "candidates_exercised": len(results),
        "all_component_contracts_passed": all(
            result["verdict"] == "CONTRACT_CANARY_PASSED" for result in results
        ),
        "results": results,
        "execution_enabled": False,
        "automatic_apply": False,
    }
    return {**core, "canary_hash": sha256_json(core)}


def _read_rows(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not all(isinstance(row, dict) for row in raw):
        raise CognitiveContractError("experiment input must be a JSON list of objects")
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("manifest")
    sub.add_parser("canary")
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("candidate_id", choices=tuple(EXPERIMENT_BY_ID))
    evaluate.add_argument("rows_json", type=Path)
    evaluate.add_argument("--budget-tolerance", type=float, default=0.02)
    args = parser.parse_args()
    try:
        if args.command == "manifest":
            result = experiment_manifest()
        elif args.command == "canary":
            result = component_contract_canary()
        else:
            result = evaluate_shadow_candidate(
                args.candidate_id,
                _read_rows(args.rows_json),
                budget_tolerance=args.budget_tolerance,
            )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, CognitiveContractError) as exc:
        print(json.dumps({"status": "STOP", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
