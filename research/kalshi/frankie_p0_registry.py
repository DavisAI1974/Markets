#!/usr/bin/env python3
"""Fail-closed inventory and readiness receipts for provisional Frankie P0 work.

This module is an honesty boundary, not an integration or launch mechanism.  It
binds the public call surfaces of the provisional P0 packs to exact source bytes and
states what each surface does and does not implement.  Nothing here authorizes
execution, application to Frankie state, candidate promotion, or V4 activity.

The empirical-readiness evaluator validates hash-bound evidence receipts.  It
cannot establish that a caller disclosed every external channel, so a passing
receipt set remains subject to independent artifact review and explicit user
authorization.
"""
from __future__ import annotations

import ast
import copy
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


REGISTRY_SCHEMA_VERSION = "FRANKIE_P0_REGISTRY_V2"
EVIDENCE_SCHEMA_VERSION = "FRANKIE_P0_EVIDENCE_RECEIPT_V1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

CLASSIFICATIONS = frozenset({"RUNTIME_LOOP", "VALIDATOR", "HELPER", "BENCHMARK"})
RUNTIME_EXPOSURES = frozenset(
    {
        "EXPLICIT_OPT_IN_COGNITIVE_RUNTIME_HOOK",
        "STANDALONE_ONLY",
    }
)
CALLER_ATTESTATION_ROLES = frozenset(
    {
        "NONE",
        "DECLARES_CALLER_ATTESTATION_ENVELOPE",
        "CONSUMES_CALLER_ATTESTATION",
    }
)
INTEGRATION_STATUSES = frozenset(
    {
        "EXPLICIT_OPT_IN_RUNTIME_HOOK_NOT_GROUP_RUNNER_WIRED",
        "STANDALONE_SHADOW_LOOP_NOT_RUNTIME_WIRED",
        "STANDALONE_VALIDATOR_NOT_RUNTIME_OR_V4_WIRED",
        "STANDALONE_HELPER_NOT_RUNTIME_WIRED",
        "STANDALONE_BENCHMARK_NOT_RUNTIME_WIRED",
    }
)

RUNTIME_BINDING_FILES = {
    "cognitive_runtime": {
        "filename": "frankie_s137_cognitive_runtime.py",
        "content_sha256": "97b82cd9821130b1117dd3207a8f4dabe748f49a464ea8dfb34ee9787fa87020",
    },
    "standard_group_runner": {
        "filename": "frankie_s135_group_runner.py",
        "content_sha256": "9bdeea4957ca8edf2aa9164368a694954a6f7ba21b26de884c299f3b85ae9e22",
    },
}

RUNTIME_HOOK_BINDINGS: tuple[dict[str, str], ...] = (
    {
        "candidate_id": "COG02_REACT_EVIDENCE_LOOP",
        "module": "frankie_cognitive_p0_loops.py",
        "entry_point": "run_bounded_react",
    },
    {
        "candidate_id": "COG03_LATS_BOUNDED_PLAN_SEARCH",
        "module": "frankie_lats_p0_search.py",
        "entry_point": "run_bounded_lats_search",
    },
    {
        "candidate_id": "COG04_STRUCTGPT_TYPED_READS",
        "module": "frankie_cognitive_p0_loops.py",
        "entry_point": "run_iterative_structured_reads",
    },
    {
        "candidate_id": "COG05_FAITHFUL_EXECUTABLE_REASONING",
        "module": "frankie_cognitive_p0_loops.py",
        "entry_point": "execute_faithful_ir",
    },
    {
        "candidate_id": "COG06_CRITIC_TOOL_VERIFICATION",
        "module": "frankie_cognitive_p0_loops.py",
        "entry_point": "run_critic_revision",
    },
    {
        "candidate_id": "COG07_MEMORY_AGENT_BENCH",
        "module": "frankie_cognitive_p0_loops.py",
        "entry_point": "run_chronological_memory_benchmark",
    },
    {
        "candidate_id": "COG08_HIPPORAG_ASSOCIATIVE_RETRIEVAL",
        "module": "frankie_hipporag_p0_retrieval.py",
        "entry_point": "run_hipporag_shadow_pipeline",
    },
    {
        "candidate_id": "COG09_HIAGENT_WORKING_MEMORY",
        "module": "frankie_cognitive_p0_loops.py",
        "entry_point": "run_state_aware_working_memory",
    },
    {
        "candidate_id": "COG10_PROGRESS_COMPRESS_SHADOW_LEARNING",
        "module": "frankie_progress_compress_p0.py",
        "entry_point": "run_progress_compress_shadow",
    },
)

COMMON_COGNITIVE_CONTROLS = (
    "S135_FROZEN_BASELINE",
    "IDENTICAL_INFORMATION_AND_REVEAL_SET",
    "MATCHED_MODEL_AND_RESOURCE_BUDGET",
    "FIXED_NO_LOOP_OR_IDENTITY_CONTROL",
)
COMMON_COGNITIVE_GATES = (
    "CONTRACT_AND_FAULT_INJECTION",
    "HELD_OUT_PAIRED_PERFORMANCE",
    "CALIBRATION_AND_SELECTIVE_RISK",
    "PLANTED_NULL_CONTAMINATION",
    "PROTECTED_RETENTION_MATRIX",
    "EVALUATOR_INDEPENDENCE",
    "BYTE_EXACT_LIVE_ROLLBACK",
)
COMMON_MARKET_GATES = (
    "HASH_BOUND_INPUTS",
    "HELD_OUT_PAIRED_PERFORMANCE",
    "CALIBRATION_AND_SELECTIVE_RISK",
    "PLANTED_NULL_CONTAMINATION",
    "PROTECTED_RETENTION_MATRIX",
    "EVALUATOR_INDEPENDENCE",
    "BYTE_EXACT_LIVE_ROLLBACK",
)
COMMON_GDL_GATES = (
    "HASH_BOUND_INPUT_GRAPH_AND_SPLIT",
    "LAWFUL_INVARIANCE_AND_HARMFUL_TRANSFORM_SENSITIVITY",
    "HELD_OUT_PAIRED_PERFORMANCE",
    "CALIBRATION_AND_SELECTIVE_RISK",
    "PLANTED_NULL_CONTAMINATION",
    "PROTECTED_RETENTION_MATRIX",
    "EVALUATOR_INDEPENDENCE",
    "BYTE_EXACT_LIVE_ROLLBACK",
)


MODULE_SPECS: dict[str, dict[str, Any]] = {
    "frankie_cognitive_p0_loops.py": {
        "implementation_version": "FRANKIE_COGNITIVE_P0_LOOPS_V1_PROVISIONAL",
        "version_symbol": "VERSION",
        "content_sha256": "cc8d9830d52350801be985768d2d9df6a60c7bf96d1a66a3bf9aec9eb23bc148",
    },
    "frankie_market_p0_controls.py": {
        "implementation_version": "FRANKIE_MARKET_P0_CONTROLS_V1",
        "version_symbol": None,
        "content_sha256": "0f35ef404a07074e4d9802fc71837b489178f6cf463db1252c2784c3c5833cb6",
    },
    "frankie_gdl_p0_controls.py": {
        "implementation_version": "FRANKIE_GDL_P0_CONTROLS_V1",
        "version_symbol": "SCHEMA_VERSION",
        "content_sha256": "837f7ab713c56a951aaf6ad847246b35ae0dedf62eb8341be6c4fe38c0dd5f86",
    },
    "frankie_microstructure_p0_baselines.py": {
        "implementation_version": "PROVISIONAL_BASELINE_NO_FORWARD_EVIDENCE",
        "version_symbol": "IMPLEMENTATION_STATUS",
        "content_sha256": "32968935dc81b8b399d067913b054bee1e9bea42685ec29bee2e1f094eb86389",
    },
    "frankie_temporal_p0_controls.py": {
        "implementation_version": "FRANKIE_TEMPORAL_P0_CONTROLS_V1",
        "version_symbol": "SCHEMA_VERSION",
        "content_sha256": "1e99be6700cbc5f4071faff6e9e0abd2bd0e663972ca1e67363afee2557edec8",
    },
    "frankie_lats_p0_search.py": {
        "implementation_version": "FRANKIE_LATS_P0_SEARCH_V1_PROVISIONAL",
        "version_symbol": "VERSION",
        "content_sha256": "c727aabf4720e8de355a5c4c54b26b16d88341f7b9ced4438c2bba2029d8bc19",
    },
    "frankie_hipporag_p0_retrieval.py": {
        "implementation_version": "FRANKIE_HIPPORAG_P0_RETRIEVAL_V1_PROVISIONAL",
        "version_symbol": "VERSION",
        "content_sha256": "2922eda270bca543c54e5c987d93c8b268f16d2a72edc0230f6d72adf5291bc5",
    },
    "frankie_progress_compress_p0.py": {
        "implementation_version": "FRANKIE_PROGRESS_COMPRESS_P0_V1_PROVISIONAL",
        "version_symbol": "VERSION",
        "content_sha256": "9ab4036f61f2cfeda1639e694d1f7ef182cb3bf24843a56f8f0b9cd3d879550f",
    },
    "frankie_temporal_graph_p0_adapter.py": {
        "implementation_version": "FRANKIE_TEMPORAL_GRAPH_P0_ADAPTER_V1_PROVISIONAL",
        "version_symbol": "VERSION",
        "content_sha256": "b3d11e79bad148148f21970f3c3801313b1fffd5413103a82fc77255ecdb4e53",
    },
}


def _entry(
    module: str,
    name: str,
    classification: str,
    paper_derived: Sequence[str],
    frankie_added: Sequence[str],
    controls: Sequence[str],
    gates: Sequence[str],
    integration_status: str,
) -> dict[str, Any]:
    return {
        "module": module,
        "entry_point": name,
        "classification": classification,
        "paper_derived_mechanisms": tuple(paper_derived),
        "frankie_added_mechanisms": tuple(frankie_added),
        "required_matched_controls": tuple(controls),
        "required_gates": tuple(gates),
        "integration_status": integration_status,
        "performance_evidence": False,
        "execution": False,
        "apply": False,
        "promotion": False,
    }


_COG = "frankie_cognitive_p0_loops.py"
_MARKET = "frankie_market_p0_controls.py"
_GDL = "frankie_gdl_p0_controls.py"

ENTRY_SPECS: tuple[dict[str, Any], ...] = (
    _entry(
        _COG,
        "P0LoopError",
        "HELPER",
        ("none; public exception type only",),
        ("shared fail-closed error boundary for malformed P0 loop contracts",),
        ("NOT_APPLICABLE_PUBLIC_ERROR_TYPE",),
        ("REGISTRY_INVENTORY_INTEGRITY",),
        "STANDALONE_HELPER_NOT_RUNTIME_WIRED",
    ),
    _entry(
        _COG,
        "BudgetVector",
        "HELPER",
        ("none; resource accounting is experimental-governance plumbing",),
        ("six-dimensional nonnegative finite budget vector",),
        ("IDENTICAL_RESOURCE_METERING_SCHEMA",),
        ("MATCHED_RESOURCE_BUDGET", "REGISTRY_INVENTORY_INTEGRITY"),
        "STANDALONE_HELPER_NOT_RUNTIME_WIRED",
    ),
    _entry(
        _COG,
        "CallbackResult",
        "HELPER",
        ("none; callback envelope is Frankie control plumbing",),
        ("detached payload, explicit usage, and mandatory side-effect-free attestation",),
        ("IDENTICAL_CALLBACK_CONTRACT",),
        ("CONTRACT_AND_FAULT_INJECTION", "REGISTRY_INVENTORY_INTEGRITY"),
        "STANDALONE_HELPER_NOT_RUNTIME_WIRED",
    ),
    _entry(
        _COG,
        "run_bounded_react",
        "RUNTIME_LOOP",
        ("ReAct decide, read-only action, observation, replan, and stop loop",),
        (
            "hard step and resource bounds",
            "allow-listed injected tools",
            "hash-chained disposable SHADOW trace",
            "fault-injection hooks",
        ),
        COMMON_COGNITIVE_CONTROLS,
        COMMON_COGNITIVE_GATES,
        "STANDALONE_SHADOW_LOOP_NOT_RUNTIME_WIRED",
    ),
    _entry(
        _COG,
        "run_iterative_structured_reads",
        "RUNTIME_LOOP",
        ("StructGPT-style iterative model-directed structured reads and answer-or-read stopping",),
        (
            "typed exact-reference store",
            "round and record ceilings",
            "hash-chained disposable SHADOW trace",
        ),
        COMMON_COGNITIVE_CONTROLS,
        COMMON_COGNITIVE_GATES,
        "STANDALONE_SHADOW_LOOP_NOT_RUNTIME_WIRED",
    ),
    _entry(
        _COG,
        "run_critic_revision",
        "RUNTIME_LOOP",
        ("CRITIC initial answer, external check, critique, revision, and recheck loop",),
        (
            "immutable initial artifact",
            "allowed-evidence references",
            "revision ceiling and matched metering",
        ),
        COMMON_COGNITIVE_CONTROLS,
        COMMON_COGNITIVE_GATES,
        "STANDALONE_SHADOW_LOOP_NOT_RUNTIME_WIRED",
    ),
    _entry(
        _COG,
        "run_state_aware_working_memory",
        "RUNTIME_LOOP",
        ("HiAgent-style one-active-subgoal state, summary compaction, and detail retrieval",),
        (
            "bounded chunks and events",
            "hidden-history lifecycle",
            "source-reference validation and SHADOW-only state",
        ),
        COMMON_COGNITIVE_CONTROLS,
        COMMON_COGNITIVE_GATES,
        "STANDALONE_SHADOW_LOOP_NOT_RUNTIME_WIRED",
    ),
    _entry(
        _COG,
        "execute_faithful_ir",
        "RUNTIME_LOOP",
        ("Faithful-CoT-style explicit executable intermediate reasoning",),
        (
            "source-hashed premises",
            "bounded linear non-Turing typed IR",
            "deterministic final-register derivation",
        ),
        (*COMMON_COGNITIVE_CONTROLS, "DIRECT_ANSWER_WITHOUT_IR"),
        COMMON_COGNITIVE_GATES,
        "STANDALONE_SHADOW_LOOP_NOT_RUNTIME_WIRED",
    ),
    _entry(
        _COG,
        "run_chronological_memory_benchmark",
        "BENCHMARK",
        ("MemoryAgentBench-style long-term memory competency axes",),
        (
            "chronological incremental histories",
            "fresh isolated adapter per case",
            "exact four-axis answer and provenance scoring",
        ),
        ("MEMORY_DISABLED", "CURRENT_FRANKIE_MEMORY", "MATCHED_MODEL_AND_RESOURCE_BUDGET"),
        COMMON_COGNITIVE_GATES,
        "STANDALONE_BENCHMARK_NOT_RUNTIME_WIRED",
    ),
    _entry(
        _MARKET,
        "score_open_stream_events",
        "BENCHMARK",
        ("early-classification joint evaluation of prediction error and decision delay",),
        ("stream-local one-to-one matching, explicit windows, misses, and false alarms per observed hour",),
        ("NO_ALARM", "FIXED_THRESHOLD", "RANDOM_MATCHED_ALARM_RATE"),
        ("CHRONOLOGICAL_HELD_OUT_STREAM", *COMMON_MARKET_GATES),
        "STANDALONE_BENCHMARK_NOT_RUNTIME_WIRED",
    ),
    _entry(
        _MARKET,
        "validate_reveal_time_purged_splits",
        "VALIDATOR",
        ("chronological current-risk assessment under temporal shift",),
        ("exact reveal-time embargo, case/group disjointness, and end-before-reveal enforcement",),
        ("DECLARED_SPLIT_MANIFEST", "UNPURGED_SPLIT_DIAGNOSTIC_ONLY"),
        ("ZERO_SPLIT_AND_REVEAL_VIOLATIONS", "HASH_BOUND_INPUTS"),
        "STANDALONE_VALIDATOR_NOT_RUNTIME_OR_V4_WIRED",
    ),
    _entry(
        _MARKET,
        "validate_first_lock_movie",
        "VALIDATOR",
        ("none; first-lock reconciliation is Frankie-specific",),
        ("current-second persistence recomputation with no backdating",),
        ("RECORDED_LOCK", "RECOMPUTED_FIRST_LOCK"),
        ("EXACT_LOCK_AND_PROBABILITY_PATH_MATCH", "HASH_BOUND_INPUTS"),
        "STANDALONE_VALIDATOR_NOT_RUNTIME_OR_V4_WIRED",
    ),
    _entry(
        _MARKET,
        "CalibrationPolicy",
        "HELPER",
        ("none; policy envelope only",),
        ("declared calibration, selective-risk, wrong-lock, and coverage thresholds",),
        ("PRECOMMITTED_POLICY",),
        ("POLICY_RANGE_VALIDATION", "HASH_BOUND_INPUTS"),
        "STANDALONE_HELPER_NOT_RUNTIME_WIRED",
    ),
    _entry(
        _MARKET,
        "evaluate_calibration_selective_gate",
        "VALIDATOR",
        ("calibration assessment under changing distributions, motivated by adaptive conformal work",),
        ("Brier, clipped log loss, equal-width ECE, complete declared strata, selective risk, wrong-lock, and coverage gates",),
        ("UNCALIBRATED_FROZEN_BASELINE", "FIXED_CALIBRATOR", "IDENTICAL_HELD_OUT_ROWS"),
        COMMON_MARKET_GATES,
        "STANDALONE_VALIDATOR_NOT_RUNTIME_OR_V4_WIRED",
    ),
    _entry(
        _MARKET,
        "PairedEvidencePolicy",
        "HELPER",
        ("none; paired policy is experimental-governance plumbing",),
        ("minimum cases/seeds/effect/win-rate and maximum loss-rate thresholds",),
        ("PRECOMMITTED_POLICY",),
        ("POLICY_RANGE_VALIDATION", "HASH_BOUND_INPUTS"),
        "STANDALONE_HELPER_NOT_RUNTIME_WIRED",
    ),
    _entry(
        _MARKET,
        "evaluate_paired_repeated_seed_gate",
        "VALIDATOR",
        ("none; paired repeated-seed gate is Frankie experimental governance",),
        ("exact case-seed pairing and case-clustered normal lower confidence bound",),
        ("FROZEN_BASELINE", "FIXED_REWRITE", "RANDOM_SEARCH", "MATCHED_BUDGET_AND_SEEDS"),
        COMMON_MARKET_GATES,
        "STANDALONE_VALIDATOR_NOT_RUNTIME_OR_V4_WIRED",
    ),
    _entry(
        _MARKET,
        "RetentionPolicy",
        "HELPER",
        ("none; policy envelope only",),
        ("minimum protected-cell count and maximum regression",),
        ("PRECOMMITTED_POLICY",),
        ("POLICY_RANGE_VALIDATION", "HASH_BOUND_INPUTS"),
        "STANDALONE_HELPER_NOT_RUNTIME_WIRED",
    ),
    _entry(
        _MARKET,
        "evaluate_retention_matrix",
        "VALIDATOR",
        ("none; this is Frankie retention governance",),
        ("complete declared protected-suite by stratum matrix and per-cell regression gate",),
        ("FROZEN_BASELINE", "IDENTICAL_PROTECTED_CASES", "ALL_DECLARED_STRATA"),
        COMMON_MARKET_GATES,
        "STANDALONE_VALIDATOR_NOT_RUNTIME_OR_V4_WIRED",
    ),
    _entry(
        _MARKET,
        "validate_byte_exact_rollback",
        "VALIDATOR",
        ("none; this is Frankie rollback governance",),
        ("non-vacuous candidate mutation and exact restoration of every declared artifact byte",),
        ("PRE_CANDIDATE_ARTIFACT_SET", "MUTATED_CANDIDATE", "RESTORED_ARTIFACT_SET"),
        ("BYTE_EXACT_LIVE_ROLLBACK", "HASH_BOUND_INPUTS"),
        "STANDALONE_VALIDATOR_NOT_RUNTIME_OR_V4_WIRED",
    ),
    _entry(
        _MARKET,
        "AdaptiveNullPolicy",
        "HELPER",
        ("none; policy envelope only",),
        ("minimum planted-null trials and false-selection confidence ceiling",),
        ("PRECOMMITTED_POLICY",),
        ("POLICY_RANGE_VALIDATION", "HASH_BOUND_INPUTS"),
        "STANDALONE_HELPER_NOT_RUNTIME_WIRED",
    ),
    _entry(
        _MARKET,
        "evaluate_planted_null_contamination_gate",
        "VALIDATOR",
        ("none; planted-null governance is Frankie-specific",),
        ("precommitted false-selection gate and declared hash-parent separation",),
        ("PLANTED_NULLS", "NEGATIVE_CONTROLS", "LOCKED_EVALUATOR"),
        COMMON_MARKET_GATES,
        "STANDALONE_VALIDATOR_NOT_RUNTIME_OR_V4_WIRED",
    ),
    _entry(
        _GDL,
        "GDLControlError",
        "HELPER",
        ("none; public exception type only",),
        ("shared fail-closed error boundary for malformed GDL control contracts",),
        ("NOT_APPLICABLE_PUBLIC_ERROR_TYPE",),
        ("REGISTRY_INVENTORY_INTEGRITY",),
        "STANDALONE_HELPER_NOT_RUNTIME_WIRED",
    ),
    _entry(
        _GDL,
        "audit_causal_prefix",
        "VALIDATOR",
        ("causal temporal-graph/message-passing inputs use information available at the evaluation time",),
        ("complete point-in-time prefix, effective-cutoff binding, and target-prebirth field blacklist",),
        ("FULL_AVAILABLE_EVENT_UNIVERSE", "DECLARED_PREFIX", "FUTURE_LEAKAGE_CANARY"),
        COMMON_GDL_GATES,
        "STANDALONE_VALIDATOR_NOT_RUNTIME_OR_V4_WIRED",
    ),
    _entry(
        _GDL,
        "validate_graph_stability_pair",
        "VALIDATOR",
        ("graph model permutation invariance and sensitivity to semantic graph changes",),
        ("paired lawful-transform invariance and intentionally harmful-transform sensitivity thresholds",),
        ("INPUT_REORDER", "NODE_RELABEL", "DIRECTION_TIMESTAMP_POLARITY_AND_EDGE_DAMAGE"),
        COMMON_GDL_GATES,
        "STANDALONE_VALIDATOR_NOT_RUNTIME_OR_V4_WIRED",
    ),
    _entry(
        _GDL,
        "build_one_wl_control_receipt",
        "BENCHMARK",
        ("1-WL color-refinement expressivity limitation for message-passing graph models",),
        ("hash-bound non-isomorphic undirected pair with matching 1-WL colors and simple-structure checks",),
        ("ONE_WL_INDISTINGUISHABLE_PAIR", "STRUCTURALLY_DISTINCT_PAIR"),
        COMMON_GDL_GATES,
        "STANDALONE_BENCHMARK_NOT_RUNTIME_WIRED",
    ),
    _entry(
        _GDL,
        "validate_edgeless_deep_sets_control",
        "VALIDATOR",
        ("Deep Sets permutation-invariant set aggregation as a graph-free control",),
        ("exact feature/split/case/budget binding against a graph candidate with no edges",),
        ("EDGELESS_DEEP_SETS", "GRAPH_CANDIDATE", "IDENTICAL_INPUTS_AND_BUDGET"),
        COMMON_GDL_GATES,
        "STANDALONE_VALIDATOR_NOT_RUNTIME_OR_V4_WIRED",
    ),
    _entry(
        _GDL,
        "validate_artifact_dag_withdrawal_coverage",
        "VALIDATOR",
        ("none; this is provenance and withdrawal governance, not a paper learning mechanism",),
        ("exact descendant closure over a declared hash-bound artifact DAG and serving-leak rejection",),
        ("DIRECT_ONLY_WITHDRAWAL", "FULL_DESCENDANT_WITHDRAWAL", "SERVING_LEAK_CANARY"),
        ("ALL_DECLARED_ARTIFACT_CLASSES", "EXACT_DESCENDANT_CLOSURE", "ZERO_SERVING_LEAKS", *COMMON_GDL_GATES),
        "STANDALONE_VALIDATOR_NOT_RUNTIME_OR_V4_WIRED",
    ),
)


_EXPANDED_SURFACES: dict[str, dict[str, Any]] = {
    "frankie_microstructure_p0_baselines.py": {
        "paper": "Cont-style Level-I OFI and Large-inspired depletion/resiliency measurement",
        "frankie": "causal book guards, censoring, lag-only rows, train-only fits, and matched controls",
        "controls": ("OFI", "PRICE_ONLY", "VOLUME_ONLY", "STATIC_IMBALANCE"),
        "gates": COMMON_MARKET_GATES,
        "surfaces": {
            "BookGuardPolicy": "HELPER",
            "ResiliencyPolicy": "HELPER",
            "FitPolicy": "HELPER",
            "compute_level1_ofi_events": "HELPER",
            "aggregate_causal_ofi_windows": "HELPER",
            "label_depletion_resiliency_episodes": "HELPER",
            "build_lag_only_forecast_rows": "HELPER",
            "validate_lag_only_forecast_rows": "VALIDATOR",
            "fit_matched_resiliency_baselines": "HELPER",
            "predict_matched_resiliency_baselines": "HELPER",
            "score_resiliency_forecasts": "BENCHMARK",
        },
    },
    "frankie_temporal_p0_controls.py": {
        "paper": "sequential-error, accumulated-gap, delayed-label ACI, and adaptive current-risk assessment",
        "frankie": "precommitted alpha spending, frozen-pool controls, receipts, and explicit theorem limits",
        "controls": ("FINITE_BONFERRONI", "NAIVE_POINTWISE", "FIXED", "EXPANDING", "RECENT"),
        "gates": COMMON_MARKET_GATES,
        "surfaces": {
            "TemporalP0ControlError": "HELPER",
            "audit_planted_null_first_locks": "VALIDATOR",
            "calibrate_accumulated_accuracy_gap": "BENCHMARK",
            "run_delayed_label_aci": "RUNTIME_LOOP",
            "assess_frozen_pool_current_risk": "BENCHMARK",
        },
    },
    "frankie_lats_p0_search.py": {
        "paper": "LATS selection, expansion, simulation, value, reflection, and backpropagation loop",
        "frankie": "bounded deterministic shadow search, causal feedback catalog, matched budget, and removal receipts",
        "controls": ("TREE", "ONE_PATH_CONTROL"),
        "gates": COMMON_COGNITIVE_GATES,
        "surfaces": {
            "LATSContractError": "HELPER",
            "run_bounded_lats_search": "RUNTIME_LOOP",
            "verify_lats_replay": "VALIDATOR",
            "compare_tree_to_one_path_control": "VALIDATOR",
        },
    },
    "frankie_hipporag_p0_retrieval.py": {
        "paper": "HippoRAG extraction, associative graph, PPR retrieval, and reader pipeline",
        "frankie": "point-in-time provenance, target-birth and withdrawal filters, cited paths, and matched flat control",
        "controls": ("PPR_GRAPH", "MATCHED_FLAT_RETRIEVAL"),
        "gates": COMMON_COGNITIVE_GATES,
        "surfaces": {
            "HippoRAGContractError": "HELPER",
            "HippoCallbackResult": "HELPER",
            "run_hipporag_shadow_pipeline": "RUNTIME_LOOP",
        },
    },
    "frankie_progress_compress_p0.py": {
        "paper": "Progress-and-Compress active column, lateral transfer, distillation, and EWC consolidation shape",
        "frankie": "immutable protected bytes, release firewall, zero-regression retention, isolation, and rollback",
        "controls": ("FROZEN_BASELINE", "MATCHED_ACTIVE_CANDIDATE"),
        "gates": COMMON_COGNITIVE_GATES,
        "surfaces": {
            "ProgressCompressP0Error": "HELPER",
            "ResourceUsage": "HELPER",
            "ShadowCallbackResult": "HELPER",
            "build_release_firewall_receipt": "HELPER",
            "run_progress_compress_shadow": "RUNTIME_LOOP",
        },
    },
    "frankie_temporal_graph_p0_adapter.py": {
        "paper": "TGN/TGAT-inspired temporal message, memory, time encoding, and attention replay",
        "frankie": "batch-size-1 predict-before-update causality, lane isolation, invalidation replay, and exact reset identity",
        "controls": ("FROZEN_STATIC_SIGNED_HASH", "EDGELESS_DEEP_SETS", "ONE_WL"),
        "gates": COMMON_GDL_GATES,
        "surfaces": {
            "TemporalGraphContractError": "HELPER",
            "temporal_event_content_hash": "HELPER",
            "TemporalCallbackResult": "HELPER",
            "frozen_static_signed_hash_payload": "HELPER",
            "run_temporal_graph_shadow_adapter": "RUNTIME_LOOP",
        },
    },
}


def _expanded_entry_specs() -> tuple[dict[str, Any], ...]:
    result: list[dict[str, Any]] = []
    integration_by_class = {
        "RUNTIME_LOOP": "STANDALONE_SHADOW_LOOP_NOT_RUNTIME_WIRED",
        "VALIDATOR": "STANDALONE_VALIDATOR_NOT_RUNTIME_OR_V4_WIRED",
        "HELPER": "STANDALONE_HELPER_NOT_RUNTIME_WIRED",
        "BENCHMARK": "STANDALONE_BENCHMARK_NOT_RUNTIME_WIRED",
    }
    for module, spec in _EXPANDED_SURFACES.items():
        for name, classification in spec["surfaces"].items():
            support_surface = (
                name.endswith("Error")
                or name.endswith("Policy")
                or name.endswith("Result")
                or name in {"ResourceUsage", "temporal_event_content_hash"}
            )
            paper = (
                ("none; public contract/support surface",)
                if support_surface
                else (f"{name}: {spec['paper']}",)
            )
            result.append(
                _entry(
                    module,
                    name,
                    classification,
                    paper,
                    (f"{name}: {spec['frankie']}",),
                    spec["controls"],
                    spec["gates"],
                    integration_by_class[classification],
                )
            )
    return tuple(result)


_CALLER_ATTESTATION_BY_ENTRY = {
    ("frankie_cognitive_p0_loops.py", "CallbackResult"):
        "DECLARES_CALLER_ATTESTATION_ENVELOPE",
    ("frankie_cognitive_p0_loops.py", "run_bounded_react"):
        "CONSUMES_CALLER_ATTESTATION",
    ("frankie_cognitive_p0_loops.py", "run_iterative_structured_reads"):
        "CONSUMES_CALLER_ATTESTATION",
    ("frankie_cognitive_p0_loops.py", "run_critic_revision"):
        "CONSUMES_CALLER_ATTESTATION",
    ("frankie_cognitive_p0_loops.py", "run_state_aware_working_memory"):
        "CONSUMES_CALLER_ATTESTATION",
    ("frankie_cognitive_p0_loops.py", "run_chronological_memory_benchmark"):
        "CONSUMES_CALLER_ATTESTATION",
    ("frankie_lats_p0_search.py", "run_bounded_lats_search"):
        "CONSUMES_CALLER_ATTESTATION",
    ("frankie_hipporag_p0_retrieval.py", "HippoCallbackResult"):
        "DECLARES_CALLER_ATTESTATION_ENVELOPE",
    ("frankie_hipporag_p0_retrieval.py", "run_hipporag_shadow_pipeline"):
        "CONSUMES_CALLER_ATTESTATION",
    ("frankie_progress_compress_p0.py", "ShadowCallbackResult"):
        "DECLARES_CALLER_ATTESTATION_ENVELOPE",
    ("frankie_progress_compress_p0.py", "run_progress_compress_shadow"):
        "CONSUMES_CALLER_ATTESTATION",
    ("frankie_temporal_graph_p0_adapter.py", "TemporalCallbackResult"):
        "DECLARES_CALLER_ATTESTATION_ENVELOPE",
    ("frankie_temporal_graph_p0_adapter.py", "run_temporal_graph_shadow_adapter"):
        "CONSUMES_CALLER_ATTESTATION",
}

_UNIMPLEMENTED_BY_ENTRY: dict[tuple[str, str], tuple[str, ...]] = {
    ("frankie_cognitive_p0_loops.py", "run_bounded_react"): (
        "paper prompts and paper tool environment",
        "learned action policy",
    ),
    ("frankie_cognitive_p0_loops.py", "run_iterative_structured_reads"): (
        "paper-exact table, knowledge-graph, and database interfaces",
        "entity linking, SQL generation, and trained retrieval policy",
    ),
    ("frankie_cognitive_p0_loops.py", "run_critic_revision"): (
        "paper prompts and external tool suite",
        "trained critique policy",
    ),
    ("frankie_cognitive_p0_loops.py", "run_state_aware_working_memory"): (
        "model-generated subgoals and summaries",
        "paper prompts and learned detail-retrieval policy",
    ),
    ("frankie_cognitive_p0_loops.py", "execute_faithful_ir"): (
        "language-to-IR translation model",
        "general solver stack",
    ),
    ("frankie_cognitive_p0_loops.py", "run_chronological_memory_benchmark"): (
        "MemoryAgentBench corpus and judge replication",
        "complete runtime memory architecture",
    ),
    ("frankie_market_p0_controls.py", "score_open_stream_events"): (
        "ECOTS classifier, training procedure, and paper benchmark replication",
        "real chronological open-stream performance evidence",
    ),
    ("frankie_market_p0_controls.py", "evaluate_calibration_selective_gate"): (
        "adaptive conformal prediction-set construction",
        "real chronological calibration and selective-risk evidence",
    ),
    ("frankie_gdl_p0_controls.py", "validate_graph_stability_pair"): (
        "trained graph model and paper stability-bound reproduction",
        "real lawful-perturbation performance evidence",
    ),
    ("frankie_gdl_p0_controls.py", "build_one_wl_control_receipt"): (
        "learned message-passing graph model",
        "held-out comparison against the control pair",
    ),
    ("frankie_gdl_p0_controls.py", "validate_edgeless_deep_sets_control"): (
        "trained Deep-Sets control model",
        "held-out matched-budget comparison",
    ),
    ("frankie_lats_p0_search.py", "run_bounded_lats_search"): (
        "paper prompts, benchmark environment, and language-model generation policy",
        "learned or paper-identical value function and published-result reproduction",
    ),
    ("frankie_lats_p0_search.py", "compare_tree_to_one_path_control"): (
        "paper prompts, learned policy/value model, and benchmark replication",
        "real matched-budget tree-versus-one-path evidence",
    ),
    ("frankie_hipporag_p0_retrieval.py", "run_hipporag_shadow_pipeline"): (
        "paper-exact extractor, entity linker, graph schema, reader, and retrieval stack",
        "paper corpus/benchmark replication and held-out answer-quality evidence",
    ),
    ("frankie_progress_compress_p0.py", "run_progress_compress_shadow"): (
        "paper neural architecture and verified gradient optimization",
        "online Fisher estimation, paper curriculum, and performance reproduction",
    ),
    ("frankie_temporal_graph_p0_adapter.py", "run_temporal_graph_shadow_adapter"): (
        "trained TGN/TGAT parameters, samplers, losses, embeddings, and paper batching",
        "paper-exact modules, datasets, benchmark replication, and held-out evidence",
    ),
    ("frankie_temporal_p0_controls.py", "audit_planted_null_first_locks"): (
        "Howard-et-al. confidence-sequence construction",
        "real chronological sequential-error evidence",
    ),
    ("frankie_temporal_p0_controls.py", "calibrate_accumulated_accuracy_gap"): (
        "paper's full two-stage conditional accumulated-gap algorithm",
        "real purged calibration and held-out evidence",
    ),
    ("frankie_temporal_p0_controls.py", "run_delayed_label_aci"): (
        "prediction-set construction and instance-conditional guarantee",
        "real delayed-label coverage evidence",
    ),
    ("frankie_temporal_p0_controls.py", "assess_frozen_pool_current_risk"): (
        "cumulative-loss, best-fixed, switching-regret, or live-selection theorem",
        "real prequential current-risk evidence",
    ),
}

_MODULE_PAPER_GAPS: dict[str, tuple[str, ...]] = {
    "frankie_microstructure_p0_baselines.py": (
        "paper model parameterization and dataset replication",
        "real chronological market-transfer evidence",
    ),
    "frankie_temporal_p0_controls.py": (
        "paper-faithful end-to-end temporal method",
        "real chronological calibration/performance evidence",
    ),
    "frankie_lats_p0_search.py": (
        "paper prompts, learned policy/value model, and benchmark replication",
        "real matched-budget performance evidence",
    ),
    "frankie_hipporag_p0_retrieval.py": (
        "paper-exact learned retrieval stack and benchmark replication",
        "real held-out answer-quality evidence",
    ),
    "frankie_progress_compress_p0.py": (
        "verified real gradient, distillation, Fisher, and consolidation behavior",
        "real sequential-regime retention/performance evidence",
    ),
    "frankie_temporal_graph_p0_adapter.py": (
        "trained paper-faithful temporal graph system",
        "real held-out temporal-graph performance evidence",
    ),
}


def _enrich_entry_boundaries(
    entries: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    hook_by_surface = {
        (item["module"], item["entry_point"]): item["candidate_id"]
        for item in RUNTIME_HOOK_BINDINGS
    }
    result: list[dict[str, Any]] = []
    for raw in entries:
        entry = copy.deepcopy(dict(raw))
        key = (entry["module"], entry["entry_point"])
        candidate_id = hook_by_surface.get(key)
        entry["runtime_exposure"] = (
            "EXPLICIT_OPT_IN_COGNITIVE_RUNTIME_HOOK"
            if candidate_id
            else "STANDALONE_ONLY"
        )
        entry["runtime_hook_candidate_id"] = candidate_id
        if candidate_id:
            entry["integration_status"] = (
                "EXPLICIT_OPT_IN_RUNTIME_HOOK_NOT_GROUP_RUNNER_WIRED"
            )
        entry["caller_attestation_role"] = _CALLER_ATTESTATION_BY_ENTRY.get(
            key, "NONE"
        )
        if key in _UNIMPLEMENTED_BY_ENTRY:
            unimplemented = _UNIMPLEMENTED_BY_ENTRY[key]
        elif all(
            str(item).lower().startswith("none;")
            for item in entry["paper_derived_mechanisms"]
        ):
            unimplemented = ("NOT_APPLICABLE_NO_PAPER_BEHAVIOR_CLAIMED",)
        else:
            unimplemented = _MODULE_PAPER_GAPS.get(
                entry["module"],
                (
                    "paper-faithful end-to-end mechanism",
                    "real held-out empirical evidence",
                ),
            )
        entry["paper_mechanisms_not_implemented"] = tuple(unimplemented)
        result.append(entry)
    return tuple(result)


ENTRY_SPECS = _enrich_entry_boundaries(
    (*ENTRY_SPECS, *_expanded_entry_specs())
)


REQUIRED_EVIDENCE_TYPES: tuple[str, ...] = (
    "HELD_OUT_PERFORMANCE",
    "CALIBRATION",
    "CONTAMINATION",
    "RETENTION",
    "EVALUATOR_INDEPENDENCE",
    "BYTE_EXACT_LIVE_ROLLBACK",
)

_COMMON_EVIDENCE_BINDINGS = (
    "candidate_artifact_sha256",
    "baseline_artifact_sha256",
    "runner_commit_sha256",
    "evaluator_artifact_sha256",
    "evaluation_plan_sha256",
)

_TYPE_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "HELD_OUT_PERFORMANCE": {
        "evidence_origin": "EXECUTED_HELD_OUT_ARTIFACTS",
        "held_out": True,
        "selection_blinded": True,
        "paired_control": True,
        "matched_budget": True,
        "forward_chronological": True,
    },
    "CALIBRATION": {
        "evidence_origin": "EXECUTED_HELD_OUT_ARTIFACTS",
        "declared_strata_complete": True,
        "calibration_gate_passed": True,
        "selective_risk_gate_passed": True,
    },
    "CONTAMINATION": {
        "evidence_origin": "EXECUTED_PLANTED_NULL_ARTIFACTS",
        "planted_null_gate_passed": True,
        "adaptive_search_blinded_to_planted_nulls": True,
        "declared_channel_audit_passed": True,
    },
    "RETENTION": {
        "evidence_origin": "EXECUTED_PROTECTED_SUITE_ARTIFACTS",
        "protected_matrix_complete": True,
        "retention_gate_passed": True,
    },
    "EVALUATOR_INDEPENDENCE": {
        "evidence_origin": "EXECUTED_LOCKED_EVALUATOR_ARTIFACTS",
        "evaluator_independent": True,
        "evaluator_locked_before_reveal": True,
        "objective_grading": True,
    },
    "BYTE_EXACT_LIVE_ROLLBACK": {
        "evidence_origin": "EXECUTED_LIVE_ROLLBACK_ARTIFACTS",
        "byte_exact": True,
        "nonvacuous_mutation": True,
        "live_rollback_executed": True,
    },
}

_SOURCE_RECEIPT_CONTRACTS: dict[str, dict[str, Any]] = {
    "HELD_OUT_PERFORMANCE": {
        "validator": "frankie_market_p0_controls.evaluate_paired_repeated_seed_gate",
        "hash_field": "receipt_hash",
        "verdict_field": "verdict",
        "verdict": "PASS",
        "row_hash_field": "row_hash",
    },
    "CALIBRATION": {
        "validator": "frankie_market_p0_controls.evaluate_calibration_selective_gate",
        "hash_field": "receipt_hash",
        "verdict_field": "verdict",
        "verdict": "PASS",
        "row_hash_field": "row_hash",
    },
    "CONTAMINATION": {
        "validator": "frankie_market_p0_controls.evaluate_planted_null_contamination_gate",
        "hash_field": "receipt_hash",
        "verdict_field": "verdict",
        "verdict": "PASS",
        "row_hash_field": "row_hash",
    },
    "RETENTION": {
        "validator": "frankie_market_p0_controls.evaluate_retention_matrix",
        "hash_field": "receipt_hash",
        "verdict_field": "verdict",
        "verdict": "PASS",
        "row_hash_field": "matrix_hash",
    },
    "EVALUATOR_INDEPENDENCE": {
        "validator": "frankie_evaluation_controls.evaluate_judge_independence_canary",
        "hash_field": "canary_hash",
        "verdict_field": "verdict",
        "verdict": "JUDGE_AUTHORITY_RETAINED",
        "row_hash_field": "case_set_hash",
    },
    "BYTE_EXACT_LIVE_ROLLBACK": {
        "validator": "frankie_market_p0_controls.validate_byte_exact_rollback",
        "hash_field": "receipt_hash",
        "verdict_field": "verdict",
        "verdict": "PASS",
        "row_hash_field": None,
    },
}


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _discover_runtime_hook_bindings(source: str) -> tuple[dict[str, str], bool]:
    tree = ast.parse(source)
    imports: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        for alias in node.names:
            imports[alias.asname or alias.name] = (f"{node.module}.py", alias.name)

    bindings: dict[str, str] = {}
    hook_method_present = False
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "CognitiveCandidateRuntime":
            hook_method_present = any(
                isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name == "run_p0_component"
                for item in node.body
            )
        value: ast.AST | None = None
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "P0_COMPONENT_RUNNERS"
                for target in node.targets
            )
        ):
            value = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "P0_COMPONENT_RUNNERS"
        ):
            value = node.value
        if not isinstance(value, ast.Dict):
            continue
        for raw_key, raw_value in zip(value.keys, value.values):
            if not isinstance(raw_key, ast.Constant) or not isinstance(raw_key.value, str):
                continue
            if not isinstance(raw_value, ast.Name) or raw_value.id not in imports:
                bindings[raw_key.value] = "<UNRESOLVED>"
                continue
            module, imported_name = imports[raw_value.id]
            bindings[raw_key.value] = f"{module}:{imported_name}"
    return bindings, hook_method_present


def _standard_group_runner_invokes_p0(source: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "run_p0_component":
            return True
        if isinstance(node, ast.Name) and node.id == "P0_COMPONENT_RUNNERS":
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "frankie_s137_cognitive_runtime":
            return True
        if isinstance(node, ast.Import):
            if any(alias.name == "frankie_s137_cognitive_runtime" for alias in node.names):
                return True
    return False


def _audit_runtime_boundaries(
    root: Path,
    discovered_runtime_hook_bindings: Mapping[str, str] | None,
) -> dict[str, Any]:
    expected = {
        item["candidate_id"]: f"{item['module']}:{item['entry_point']}"
        for item in RUNTIME_HOOK_BINDINGS
    }
    observed: dict[str, str] = {}
    hook_method_present = False
    runtime_unreadable = False
    automatic_invocation_detected = False
    group_runner_unreadable = False
    file_receipts: list[dict[str, Any]] = []
    for role in ("cognitive_runtime", "standard_group_runner"):
        spec = RUNTIME_BINDING_FILES[role]
        path = root / spec["filename"]
        try:
            raw = path.read_bytes()
            source = raw.decode("utf-8")
            observed_hash = hashlib.sha256(raw).hexdigest()
            if role == "cognitive_runtime":
                observed, hook_method_present = _discover_runtime_hook_bindings(source)
            else:
                automatic_invocation_detected = _standard_group_runner_invokes_p0(source)
        except (OSError, UnicodeDecodeError, SyntaxError):
            observed_hash = ""
            if role == "cognitive_runtime":
                runtime_unreadable = True
            else:
                group_runner_unreadable = True
        file_receipts.append(
            {
                "role": role,
                "filename": spec["filename"],
                "expected_content_sha256": spec["content_sha256"],
                "observed_content_sha256": observed_hash,
                "content_hash_matches": observed_hash == spec["content_sha256"],
            }
        )
    if discovered_runtime_hook_bindings is not None:
        observed = {
            str(candidate_id): str(surface)
            for candidate_id, surface in discovered_runtime_hook_bindings.items()
        }

    missing = sorted(set(expected) - set(observed))
    unexpected = sorted(set(observed) - set(expected))
    mismatched = sorted(
        candidate_id
        for candidate_id in set(expected).intersection(observed)
        if expected[candidate_id] != observed[candidate_id]
    )
    hash_mismatches = sorted(
        receipt["role"]
        for receipt in file_receipts
        if not receipt["content_hash_matches"]
    )
    integrity = not (
        runtime_unreadable
        or group_runner_unreadable
        or hash_mismatches
        or missing
        or unexpected
        or mismatched
        or not hook_method_present
        or automatic_invocation_detected
    )
    core = {
        "hook_entry_point": (
            "frankie_s137_cognitive_runtime.CognitiveCandidateRuntime.run_p0_component"
        ),
        "hook_method_present": hook_method_present,
        "automatic_standard_group_runner_invocation": automatic_invocation_detected,
        "expected_bindings": expected,
        "observed_bindings": observed,
        "missing_candidate_bindings": missing,
        "unexpected_candidate_bindings": unexpected,
        "mismatched_candidate_bindings": mismatched,
        "binding_file_receipts": file_receipts,
        "binding_file_hash_mismatches": hash_mismatches,
        "runtime_unreadable": runtime_unreadable,
        "standard_group_runner_unreadable": group_runner_unreadable,
        "runtime_binding_integrity": integrity,
        "execution": False,
        "apply": False,
        "promotion": False,
    }
    return {**core, "runtime_binding_receipt_hash": _sha256_json(core)}


def _public_call_surfaces(source: str) -> tuple[set[str], dict[str, Any]]:
    tree = ast.parse(source)
    names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
    }
    constants: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                try:
                    constants[target.id] = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    pass
    return names, constants


def _entry_key(module: str, name: str) -> str:
    return f"{module}:{name}"


def audit_p0_registry(
    *,
    module_root: str | Path | None = None,
    discovered_entry_points: Mapping[str, Sequence[str]] | None = None,
    expected_module_hashes: Mapping[str, str] | None = None,
    discovered_runtime_hook_bindings: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Audit exact source/version/entry-point bindings for all P0 packs.

    The optional discovery/hash arguments exist for adversarial testing.  A
    receipt produced with either override is diagnostic and can never declare
    component readiness.
    """
    root = Path(module_root) if module_root is not None else Path(__file__).resolve().parent
    hash_expectations = {
        module: str(spec["content_sha256"])
        for module, spec in MODULE_SPECS.items()
    }
    override_used = any(
        value is not None
        for value in (
            expected_module_hashes,
            discovered_entry_points,
            discovered_runtime_hook_bindings,
        )
    )
    if expected_module_hashes is not None:
        hash_expectations.update({str(key): str(value) for key, value in expected_module_hashes.items()})

    expected_by_module: dict[str, set[str]] = {module: set() for module in MODULE_SPECS}
    for entry in ENTRY_SPECS:
        expected_by_module[entry["module"]].add(entry["entry_point"])

    module_receipts: list[dict[str, Any]] = []
    observed_by_module: dict[str, set[str]] = {}
    version_mismatches: list[str] = []
    module_hash_mismatches: list[str] = []
    invalid_module_hashes: list[str] = []
    unreadable_modules: list[str] = []
    for module, spec in MODULE_SPECS.items():
        path = root / module
        source = ""
        raw = b""
        constants: dict[str, Any] = {}
        try:
            raw = path.read_bytes()
            source = raw.decode("utf-8")
            observed_names, constants = _public_call_surfaces(source)
        except (OSError, UnicodeDecodeError, SyntaxError):
            observed_names = set()
            unreadable_modules.append(module)
        if discovered_entry_points is not None and module in discovered_entry_points:
            observed_names = {str(value) for value in discovered_entry_points[module]}
        observed_by_module[module] = observed_names
        observed_hash = hashlib.sha256(raw).hexdigest() if raw else ""
        expected_hash = hash_expectations.get(module, "")
        if not SHA256_RE.fullmatch(expected_hash):
            invalid_module_hashes.append(module)
        elif observed_hash != expected_hash:
            module_hash_mismatches.append(module)
        symbol = spec["version_symbol"]
        declared_version = constants.get(symbol) if symbol else None
        if symbol and declared_version != spec["implementation_version"]:
            version_mismatches.append(module)
        module_core = {
            "module": module,
            "implementation_version": spec["implementation_version"],
            "version_source": symbol or "REGISTRY_DECLARED_MODULE_ABI_VERSION",
            "declared_version": declared_version,
            "expected_content_sha256": expected_hash,
            "observed_content_sha256": observed_hash,
            "content_hash_matches": bool(SHA256_RE.fullmatch(expected_hash)) and observed_hash == expected_hash,
            "public_call_surface_count": len(observed_names),
        }
        module_receipts.append({**module_core, "module_receipt_hash": _sha256_json(module_core)})

    runtime_boundaries = _audit_runtime_boundaries(
        root,
        discovered_runtime_hook_bindings,
    )

    expected_keys = {
        _entry_key(entry["module"], entry["entry_point"])
        for entry in ENTRY_SPECS
    }
    observed_keys = {
        _entry_key(module, name)
        for module, names in observed_by_module.items()
        for name in names
    }
    missing = sorted(expected_keys - observed_keys)
    extra = sorted(observed_keys - expected_keys)

    entries: list[dict[str, Any]] = []
    unhashed: list[str] = []
    malformed_entries: list[str] = []
    for raw_entry in ENTRY_SPECS:
        entry = copy.deepcopy(raw_entry)
        module = entry["module"]
        name = entry["entry_point"]
        key = _entry_key(module, name)
        module_hash = hash_expectations.get(module, "")
        version = MODULE_SPECS.get(module, {}).get("implementation_version", "")
        entry["implementation_version"] = version
        entry["module_content_sha256"] = module_hash
        binding_core = {
            "module": module,
            "entry_point": name,
            "implementation_version": version,
            "module_content_sha256": module_hash,
        }
        if SHA256_RE.fullmatch(module_hash):
            entry["entry_point_binding_sha256"] = _sha256_json(binding_core)
        else:
            entry["entry_point_binding_sha256"] = ""
            unhashed.append(key)
        if (
            entry["classification"] not in CLASSIFICATIONS
            or entry["integration_status"] not in INTEGRATION_STATUSES
            or entry["runtime_exposure"] not in RUNTIME_EXPOSURES
            or entry["caller_attestation_role"] not in CALLER_ATTESTATION_ROLES
            or not entry["paper_derived_mechanisms"]
            or not entry["frankie_added_mechanisms"]
            or not entry["paper_mechanisms_not_implemented"]
            or not entry["required_matched_controls"]
            or not entry["required_gates"]
            or (
                entry["runtime_exposure"] == "EXPLICIT_OPT_IN_COGNITIVE_RUNTIME_HOOK"
                and not entry["runtime_hook_candidate_id"]
            )
            or (
                entry["runtime_exposure"] == "STANDALONE_ONLY"
                and entry["runtime_hook_candidate_id"] is not None
            )
            or any(entry[field] is not False for field in ("performance_evidence", "execution", "apply", "promotion"))
        ):
            malformed_entries.append(key)
        entries.append(entry)

    blockers = []
    if override_used:
        blockers.append("diagnostic inventory/hash override used")
    if unreadable_modules:
        blockers.append("unreadable modules")
    if module_hash_mismatches:
        blockers.append("module content hash mismatches")
    if invalid_module_hashes:
        blockers.append("invalid or absent module content hashes")
    if version_mismatches:
        blockers.append("implementation version mismatches")
    if missing:
        blockers.append("missing registered entry points")
    if extra:
        blockers.append("extra unregistered entry points")
    if unhashed:
        blockers.append("unhashed entry points")
    if malformed_entries:
        blockers.append("malformed or over-authorized registry entries")
    if not runtime_boundaries["runtime_binding_integrity"]:
        blockers.append("runtime hook boundary integrity is blocked")

    runtime_hook_entries = [
        {
            "candidate_id": entry["runtime_hook_candidate_id"],
            "module": entry["module"],
            "entry_point": entry["entry_point"],
            "classification": entry["classification"],
            "caller_attestation_role": entry["caller_attestation_role"],
        }
        for entry in entries
        if entry["runtime_exposure"] == "EXPLICIT_OPT_IN_COGNITIVE_RUNTIME_HOOK"
    ]
    runtime_hook_entries.sort(key=lambda item: str(item["candidate_id"]))
    standalone_loop_entry_points = sorted(
        _entry_key(entry["module"], entry["entry_point"])
        for entry in entries
        if entry["classification"] == "RUNTIME_LOOP"
        and entry["runtime_exposure"] == "STANDALONE_ONLY"
    )

    core = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "status": "COMPONENT_CONTRACT_READY" if not blockers else "BLOCKED_REGISTRY_INTEGRITY",
        "component_contract_ready": not blockers,
        "performance_evidence": False,
        "execution": False,
        "apply": False,
        "promotion": False,
        "module_receipts": module_receipts,
        "runtime_boundary_receipt": runtime_boundaries,
        "entries": entries,
        "entry_point_count": len(entries),
        "classification_counts": {
            value: sum(entry["classification"] == value for entry in entries)
            for value in sorted(CLASSIFICATIONS)
        },
        "runtime_hook_entries": runtime_hook_entries,
        "runtime_hook_count": len(runtime_hook_entries),
        "standalone_runtime_loop_entry_points": standalone_loop_entry_points,
        "standalone_runtime_loop_count": len(standalone_loop_entry_points),
        "caller_attestation_counts": {
            value: sum(entry["caller_attestation_role"] == value for entry in entries)
            for value in sorted(CALLER_ATTESTATION_ROLES)
        },
        "missing_entry_points": missing,
        "extra_entry_points": extra,
        "unhashed_entry_points": sorted(unhashed),
        "module_hash_mismatches": sorted(module_hash_mismatches),
        "invalid_module_hashes": sorted(invalid_module_hashes),
        "version_mismatches": sorted(version_mismatches),
        "unreadable_modules": sorted(unreadable_modules),
        "malformed_entries": sorted(malformed_entries),
        "blockers": blockers,
        "limitations": (
            "component readiness proves registry/source contract integrity only; it is not empirical evidence",
            "content hashes do not prove paper fidelity, external-channel absence, or evaluator independence",
            "caller callback attestations are declarations, not proof of external isolation or side-effect freedom",
            "explicit opt-in runtime hooks are not automatic standard-group-runner integration",
        ),
    }
    return {**core, "registry_receipt_hash": _sha256_json(core)}


def _validate_evidence_receipt(receipt: Any, expected_type: str) -> list[str]:
    prefix = expected_type
    if not isinstance(receipt, Mapping):
        return [f"{prefix}: receipt is absent or not an object"]
    issues: list[str] = []
    if receipt.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        issues.append(f"{prefix}: wrong schema_version")
    if receipt.get("evidence_type") != expected_type:
        issues.append(f"{prefix}: wrong evidence_type")
    if receipt.get("passed") is not True:
        issues.append(f"{prefix}: gate did not pass")
    if receipt.get("attestation_only") is not False:
        issues.append(f"{prefix}: attestation_only must be false")
    for field in _COMMON_EVIDENCE_BINDINGS:
        if not SHA256_RE.fullmatch(str(receipt.get(field, ""))):
            issues.append(f"{prefix}: {field} is not a SHA-256 binding")
    artifact_hash = str(receipt.get("evidence_artifact_sha256", ""))
    if not SHA256_RE.fullmatch(artifact_hash):
        issues.append(f"{prefix}: evidence_artifact_sha256 is not a SHA-256 binding")
    row_count = receipt.get("row_count")
    if type(row_count) is not int or row_count < 1:
        issues.append(f"{prefix}: row_count must be a positive integer")
    executed_at = receipt.get("executed_at")
    try:
        parsed = dt.datetime.fromisoformat(str(executed_at).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
    except (TypeError, ValueError):
        issues.append(f"{prefix}: executed_at must be a timezone-aware ISO timestamp")
    for field, expected in _TYPE_REQUIREMENTS[expected_type].items():
        if receipt.get(field) != expected:
            issues.append(f"{prefix}: {field} must equal {expected!r}")

    source_contract = _SOURCE_RECEIPT_CONTRACTS[expected_type]
    if receipt.get("source_validator_entry_point") != source_contract["validator"]:
        issues.append(f"{prefix}: wrong source_validator_entry_point")
    source_receipt = receipt.get("source_receipt")
    if not isinstance(source_receipt, Mapping):
        issues.append(f"{prefix}: verified source_receipt is required")
    else:
        hash_field = source_contract["hash_field"]
        source_hash = str(source_receipt.get(hash_field, ""))
        source_core = {
            str(key): value
            for key, value in source_receipt.items()
            if key != hash_field
        }
        try:
            computed_source_hash = _sha256_json(source_core)
            computed_artifact_hash = _sha256_json(dict(source_receipt))
        except (TypeError, ValueError):
            computed_source_hash = ""
            computed_artifact_hash = ""
        if not SHA256_RE.fullmatch(source_hash) or source_hash != computed_source_hash:
            issues.append(f"{prefix}: source receipt self-hash is absent or inconsistent")
        if artifact_hash != computed_artifact_hash:
            issues.append(f"{prefix}: evidence artifact hash does not bind the source receipt")
        verdict_field = source_contract["verdict_field"]
        if source_receipt.get(verdict_field) != source_contract["verdict"]:
            issues.append(f"{prefix}: source validator did not pass")
        row_hash_field = source_contract["row_hash_field"]
        if row_hash_field and not SHA256_RE.fullmatch(str(source_receipt.get(row_hash_field, ""))):
            issues.append(f"{prefix}: source receipt lacks a bound row/matrix hash")
        source_row_count: int | None = None
        if expected_type == "HELD_OUT_PERFORMANCE":
            case_count = source_receipt.get("case_count")
            seeds = source_receipt.get("declared_seeds")
            if type(case_count) is int and isinstance(seeds, Sequence) and not isinstance(seeds, (str, bytes)):
                source_row_count = case_count * len(seeds)
        elif expected_type == "CALIBRATION":
            metrics = source_receipt.get("metrics")
            if isinstance(metrics, Mapping) and isinstance(metrics.get("ALL"), Mapping):
                value = metrics["ALL"].get("rows")
                source_row_count = value if type(value) is int else None
        elif expected_type == "CONTAMINATION":
            value = source_receipt.get("trial_count")
            source_row_count = value if type(value) is int else None
        elif expected_type == "RETENTION":
            cells = source_receipt.get("cells")
            if isinstance(cells, Sequence) and not isinstance(cells, (str, bytes)):
                counts = [cell.get("row_count") for cell in cells if isinstance(cell, Mapping)]
                if len(counts) == len(cells) and all(type(value) is int for value in counts):
                    source_row_count = sum(counts)
        elif expected_type == "EVALUATOR_INDEPENDENCE":
            value = source_receipt.get("cases")
            source_row_count = value if type(value) is int else None
        elif expected_type == "BYTE_EXACT_LIVE_ROLLBACK":
            value = source_receipt.get("artifact_count")
            source_row_count = value if type(value) is int else None
        if source_row_count is None or source_row_count < 1 or source_row_count != row_count:
            issues.append(f"{prefix}: row_count is not verified by the source receipt")
    if expected_type == "BYTE_EXACT_LIVE_ROLLBACK":
        restored = receipt.get("restored_artifact_count")
        if type(restored) is not int or restored < 1:
            issues.append(f"{prefix}: restored_artifact_count must be positive")
        if isinstance(source_receipt, Mapping):
            changed = source_receipt.get("changed_artifact_count")
            artifacts = source_receipt.get("artifacts")
            if (
                type(changed) is not int
                or changed < 1
                or not isinstance(artifacts, Sequence)
                or isinstance(artifacts, (str, bytes))
                or not artifacts
                or any(
                    not isinstance(item, Mapping)
                    or item.get("before_hash") != item.get("restored_hash")
                    or not SHA256_RE.fullmatch(str(item.get("before_hash", "")))
                    for item in artifacts
                )
            ):
                issues.append(f"{prefix}: source rollback receipt does not prove non-vacuous byte restoration")
    evaluator_hash = str(receipt.get("evaluator_artifact_sha256", ""))
    if expected_type == "EVALUATOR_INDEPENDENCE" and evaluator_hash in {
        str(receipt.get("candidate_artifact_sha256", "")),
        str(receipt.get("baseline_artifact_sha256", "")),
    }:
        issues.append(f"{prefix}: evaluator artifact must differ from candidate and baseline")
    supplied_hash = str(receipt.get("receipt_hash", ""))
    core = {str(key): value for key, value in receipt.items() if key != "receipt_hash"}
    try:
        computed_hash = _sha256_json(core)
    except (TypeError, ValueError):
        computed_hash = ""
    if not SHA256_RE.fullmatch(supplied_hash) or supplied_hash != computed_hash:
        issues.append(f"{prefix}: receipt_hash is absent or inconsistent")
    return issues


def evaluate_p0_readiness(
    evidence_receipts: Sequence[Mapping[str, Any]] | None = None,
    *,
    module_root: str | Path | None = None,
) -> dict[str, Any]:
    """Evaluate contract and empirical readiness without granting authority.

    All six independently typed, executed, hash-bound receipts are mandatory.
    A complete set can make ``composite_readiness_passed`` true; execution,
    application, and promotion remain false until a separate user decision.
    """
    registry = audit_p0_registry(module_root=module_root)
    grouped: dict[str, list[Mapping[str, Any]]] = {name: [] for name in REQUIRED_EVIDENCE_TYPES}
    extra_types: list[str] = []
    for raw in evidence_receipts or ():
        if not isinstance(raw, Mapping):
            extra_types.append("<NON_OBJECT>")
            continue
        evidence_type = str(raw.get("evidence_type", ""))
        if evidence_type not in grouped:
            extra_types.append(evidence_type or "<MISSING>")
            continue
        grouped[evidence_type].append(raw)

    missing = [name for name in REQUIRED_EVIDENCE_TYPES if not grouped[name]]
    duplicate = [name for name in REQUIRED_EVIDENCE_TYPES if len(grouped[name]) > 1]
    issues: list[str] = []
    evidence_status: dict[str, dict[str, Any]] = {}
    accepted: list[Mapping[str, Any]] = []
    for evidence_type in REQUIRED_EVIDENCE_TYPES:
        receipts = grouped[evidence_type]
        type_issues: list[str] = []
        if len(receipts) == 1:
            type_issues = _validate_evidence_receipt(receipts[0], evidence_type)
            if not type_issues:
                accepted.append(receipts[0])
        elif not receipts:
            type_issues = [f"{evidence_type}: missing receipt"]
        else:
            type_issues = [f"{evidence_type}: duplicate receipts are forbidden"]
        issues.extend(type_issues)
        evidence_status[evidence_type] = {
            "ready": not type_issues,
            "issues": type_issues,
            "receipt_hash": receipts[0].get("receipt_hash") if len(receipts) == 1 else None,
        }

    cross_binding_mismatches: list[str] = []
    if len(accepted) == len(REQUIRED_EVIDENCE_TYPES):
        for field in _COMMON_EVIDENCE_BINDINGS:
            values = {str(receipt[field]) for receipt in accepted}
            if len(values) != 1:
                cross_binding_mismatches.append(field)
    if extra_types:
        issues.append("unexpected evidence receipt types")
    if cross_binding_mismatches:
        issues.append("cross-receipt binding mismatch")

    empirical_ready = (
        not issues
        and not extra_types
        and not cross_binding_mismatches
        and len(accepted) == len(REQUIRED_EVIDENCE_TYPES)
    )
    composite = registry["component_contract_ready"] and empirical_ready
    blockers: list[str] = []
    if not registry["component_contract_ready"]:
        blockers.append("P0 registry/component contract integrity is blocked")
    if not empirical_ready:
        blockers.append("real executed empirical evidence bundle is incomplete or invalid")
    if composite:
        blockers.append("explicit user authorization is still required")
    core = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "status": (
            "EMPIRICAL_GATES_READY_USER_AUTHORIZATION_REQUIRED"
            if composite
            else "BLOCKED_PENDING_EMPIRICAL_EVIDENCE"
        ),
        "component_contract_ready": registry["component_contract_ready"],
        "empirical_evidence_ready": empirical_ready,
        "composite_readiness_passed": composite,
        "performance_evidence": empirical_ready,
        "execution": False,
        "apply": False,
        "promotion": False,
        "user_authorization_required": True,
        "required_evidence_types": list(REQUIRED_EVIDENCE_TYPES),
        "missing_evidence_types": missing,
        "duplicate_evidence_types": duplicate,
        "unexpected_evidence_types": sorted(extra_types),
        "evidence_status": evidence_status,
        "evidence_issues": issues,
        "cross_binding_mismatches": cross_binding_mismatches,
        "registry_receipt_hash": registry["registry_receipt_hash"],
        "blockers": blockers,
        "limitations": (
            "receipt validation proves declared hash bindings and gate fields, not undisclosed external-channel absence",
            "independent artifact review and explicit user authorization remain mandatory",
        ),
    }
    return {**core, "readiness_receipt_hash": _sha256_json(core)}


__all__ = [
    "CALLER_ATTESTATION_ROLES",
    "CLASSIFICATIONS",
    "ENTRY_SPECS",
    "EVIDENCE_SCHEMA_VERSION",
    "MODULE_SPECS",
    "REGISTRY_SCHEMA_VERSION",
    "REQUIRED_EVIDENCE_TYPES",
    "RUNTIME_EXPOSURES",
    "RUNTIME_HOOK_BINDINGS",
    "audit_p0_registry",
    "evaluate_p0_readiness",
]
