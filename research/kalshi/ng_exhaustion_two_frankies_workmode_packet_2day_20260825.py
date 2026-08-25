#!/usr/bin/env python3
"""Build blind-safe Work-mode packets for the exact Oct-4/5 two-Frankie run.

This program is deterministic preparation only.  It never invokes a model, never
reads an OpenAI credential, and never uses Step-1 answers.  It filters the frozen
prior reduced/non-full-MBO seconds source to the exact half-open two-day window,
preserves every selected source field for Real-Time Frankie's optional local scout,
and emits the direct packets used by the sequential blind -> freeze -> refine run.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.kalshi import (  # noqa: E402
    ng_exhaustion_two_frankies_prior_surface_blind_2day_20260825 as prior,
)
from research.kalshi.frankie_role_context_profiles_20260824 import (  # noqa: E402
    FrankieRole,
    build_role_context_payload,
)
from research.kalshi.frankie_authority_knowledge_plane_20260824 import (  # noqa: E402
    AccessPolicy,
    TargetRelationship,
)
from research.kalshi.frankie_october_knowledge_inventory_20260824 import (  # noqa: E402
    production_source_specs,
)


SCHEMA = "NG_EXHAUSTION_TWO_FRANKIES_WORKMODE_PACKET_V1_20260825"
INFO_DIPOLE_PATH = prior.REPO_ROOT / "odcore/info_dipole.py"
LATS_LOOKAHEAD_PATH = prior.REPO_ROOT / "research/kalshi/frankie_lats_p0_search.py"
KNOWLEDGE_INVENTORY_BUILDER_PATH = (
    prior.REPO_ROOT / "research/kalshi/frankie_october_knowledge_inventory_20260824.py"
)
KNOWLEDGE_INVENTORY_MAP_PATH = (
    prior.REPO_ROOT / "research/kalshi/NG_EXHAUSTION_FRANKIE_SOURCE_FILE_INVENTORY_20260824.md"
)
EXPECTED_KNOWLEDGE_INVENTORY_BUILDER_SHA256 = (
    "e6b01aea9064ef1369eb36a872d5b43a70540c0c7720679ec0eed671482da7f1"
)
EXPECTED_KNOWLEDGE_INVENTORY_MAP_SHA256 = (
    "1603a4bc329c6aabd9f62ee76c755651c1059a609c7cf8a52d21217a78cce24e"
)
TOKEN_ESTIMATE_PER_BYTE = 0.285
RT_DIRECT_INPUT_TOKEN_CAP = 48_000
RT_CUMULATIVE_INPUT_TOKEN_CAP = 96_000
FORECASTER_INPUT_TOKEN_CAP = 150_000
FORECASTER_FROZEN_RT_RESERVE_TOKENS = 12_000
FORECASTER_BASE_PACKET_TOKEN_CAP = (
    FORECASTER_INPUT_TOKEN_CAP - FORECASTER_FROZEN_RT_RESERVE_TOKENS
)
MAX_OUTPUT_TOKENS = 12_000
FORECASTER_HELPER_INPUT_TOKEN_CAP = 48_000
FORECASTER_HELPER_OUTPUT_TOKEN_CAP = 6_000
REQUIRED_OUTPUTS = (
    "PREFLIGHT.json",
    "SOURCE_VERIFY.json",
    "SLICE_MANIFEST.json",
    "ANSWER_WALL.json",
    "CAPABILITY_RECONCILIATION.json",
    "RT_WORK_PACKET.json",
    "RT_CAPABILITIES.json",
    "RT_SCOUT_ROWS.jsonl.gz",
    "FORECASTER_LAWFUL_KNOWLEDGE.jsonl.gz",
    "FORECASTER_LAWFUL_KNOWLEDGE_MANIFEST.json",
    "FORECASTER_BASE_WORK_PACKET.json",
    "WORK_PACKET_MANIFEST.json",
    "PACKET_COMPLETE.json",
)


def work_instructions(role: FrankieRole, mission_path: Path) -> str:
    role_mission = mission_path.read_text(encoding="utf-8")
    if role is FrankieRole.REAL_TIME:
        authority = (
            "You are Real-Time Frankie. You detect, characterize, and first-lock exhaustion from "
            "causally observed evidence. You are not the forecasting role. Do not turn missing or "
            "future evidence into a forecast."
        )
        missingness = (
            "The complete capability vocabulary is preserved with Real-Time Frankie's established "
            "role-specific dormant routes unchanged. UNAVAILABLE, UNKNOWN, or DORMANT never means "
            "false or zero."
        )
    else:
        authority = (
            "You are Forecaster Frankie. Forecast from the exact frozen Real-Time Frankie exhaustion "
            "state; never reconstruct or modify that current-state lock."
        )
        missingness = (
            "Your complete 1,940-leaf/46-block/24-surface capability vocabulary is supplied directly "
            "with no dormant entries. UNAVAILABLE or UNKNOWN never means false or zero."
        )
    return "\n\n".join(
        [
            authority,
            role_mission,
            (
                "STRICT BLIND FIREWALL: Step-1 event/family/depth structures, populations, crosswalks, "
                "self-fit results, realized runway/outcomes, 54-week answers, and post-reveal analysis "
                "are absent and forbidden."
            ),
            missingness,
            (
                "Outputs are open-world. Do not force an event, family, category, mechanism, depth, "
                "correlation, clock, or match. Preserve materially distinct clocks and regimes; never "
                "average dispersed or multimodal clocks."
            ),
            "Return exactly one JSON object matching the supplied role-specific output contract.",
        ]
    )


def rt_output_contract() -> dict[str, Any]:
    return {
        "schema": "FRANKIE_PRIOR_SURFACE_RT_EXHAUSTION_FINDINGS_V2_20260825",
        "role": FrankieRole.REAL_TIME.value,
        "as_of": {
            "event_time_cutoff_ns": "integer",
            "receive_time_cutoff_ns": "integer",
            "clock_policy": "string",
        },
        "state_summary": "open object",
        "study_design": {
            "answer_key_blind": True,
            "retrospective_complete_two_day_surface": True,
            "prospective_or_out_of_sample_validation": False,
            "early_warning_claim_status": "RETROSPECTIVE_DISCOVERY_NOT_BLIND_OOS_VALIDATION",
        },
        "material_omissions": [
            {"capability_or_field": "string", "availability": "string", "confidence_impact": "string"}
        ],
        "exhaustion_events": [
            {
                "event_id": "canonical content-derived string",
                "status": "observed open-world string",
                "family": "open-world string; new names allowed",
                "category": "open-world string; new names allowed",
                "depth": "observed value or null",
                "severity": "observed value or null",
                "novel_structure": "boolean",
                "mechanism": "string",
                "searched_interval": "open clock object",
                "earliest_lawful_precursor": "event/receive clocks or null with reason",
                "pre_birth_conditions": "open object",
                "first_observed_deviation": "event/receive clocks or null with reason",
                "observed_onset": "event/receive clocks or null with reason",
                "observed_transitions": "array",
                "observed_peak_or_inflection": "open object or null with reason",
                "clock_ledger": (
                    "required precursor/onset/detection/confirmation stage objects; each keeps "
                    "event_time_ns, receive_time_ns, evidence_availability_time_ns, "
                    "decision_as_of_time_ns, and status separate"
                ),
                "prebirth_detectability": (
                    "required object with alert possibility, earliest alert clocks, lead-time range, "
                    "features, false-positive risk, contradictions, missingness, and "
                    "validation_status=RETROSPECTIVE_DISCOVERY_NOT_BLIND_OOS_VALIDATION"
                ),
                "detection_latency_s": "distribution/range or null with reason",
                "observed_dipole_runway": "required open object with stage states, clocks, contradictions, and missingness",
                "observed_elapsed_age_s": "number or null",
                "observed_duration_so_far_s": "number or null",
                "estimated_total_exhaustion_duration_s": "distribution/range or null with reason",
                "estimated_remaining_exhaustion_duration_s": "distribution/range or null with reason",
                "observed_end_or_open_status": "string",
                "contradictions": "array",
                "confidence": "number in [0,1]",
                "censoring_status": "string",
                "unknown_status": "string",
                "clock_reasoning": "string",
                "evidence_refs": ["exact row/scout/source references"],
                "assumptions": ["string"],
            }
        ],
        "observed_correlations": [
            {
                "relationship_id": "string",
                "fields": ["string"],
                "lags_seconds": ["number"],
                "clock_basis": "string",
                "mechanism": "string",
                "evidence_refs": ["string"],
                "uncertainty": "string",
            }
        ],
        "direction_and_direction_change": {
            "current_direction": "BUY_PRESSURE, SELL_PRESSURE, BALANCED, or UNKNOWN",
            "signed_imbalance_and_clock": (
                "required method_path=odcore/info_dipole.py, exact normalized buy-minus-sell "
                "formula, sign convention, window, value or null, and separate clocks"
            ),
            "dipole_flow_and_clock": (
                "required mi_flow/imb_flow definitions, values or null, window, and separate clocks"
            ),
            "continuation_weakening_reversal_or_flip_risk": "open object",
            "opposing_flow": "open object",
            "collapse_toward_balance": "open object",
            "price_flow_coupling": "open object",
            "contradictions": ["string"],
            "evidence_refs": ["string"],
            "cell_signal_promoted_to_fact": False
        },
        "bounded_lookahead": {
            "status": "SHADOW_ONLY",
            "causal_cutoff": "open clock object",
            "fixed_budget": "positive integer depth/width/iterations/resource_limit object",
            "hypothesis_tree": "open object with multiple live hypotheses",
            "feedback_statuses": ["SUPPORTED, CONTRADICTED, or INCONCLUSIVE"],
            "reflections_and_backpropagation": "open object",
            "pruned_alternatives_and_falsifiers": ["open objects"],
            "reasoning_pattern_applied": True,
            "runtime_module_executed": False,
            "unrevealed_outcomes_accessed": False,
            "first_lock_mutated": False
        },
        "scout_usage": {
            "available": True,
            "invoked": "boolean",
            "invocation_count": "integer 0 or 1",
            "request_sha256": "SHA-256 when invoked; null otherwise",
            "response_sha256": "SHA-256 when invoked; null otherwise",
            "response_bytes": "integer",
            "cumulative_estimated_input_tokens": "integer no greater than 96000",
        },
        "strategy_hypotheses": [
            {
                "strategy_id": "deterministic content-derived string",
                "status": (
                    "DISCOVERY_ONLY or PROMISING_RETROSPECTIVE_TWO_DAY_HYPOTHESIS; "
                    "never VALIDATED_EDGE"
                ),
                "exhaustion_detection_quality_gate": {
                    "event_support": "integer",
                    "misses": "integer",
                    "false_alerts": "integer",
                    "prebirth_or_early_detection": "open object",
                    "lead_time_distribution_s": "open object",
                    "detection_latency_distribution_s": "open object",
                    "duration_error_or_range_coverage": "open object",
                    "readiness_verdict": (
                        "DISCOVERY_ONLY or PROMISING_RETROSPECTIVE_TWO_DAY_HYPOTHESIS"
                    ),
                    "promotion_or_rejection_reason": "string",
                },
                "causal_trigger": "open object with separate clocks",
                "side_or_position_logic": "string",
                "entry_condition": "open object",
                "hold_or_continuation_condition": "open object",
                "exit_or_reversal_condition": "open object",
                "invalidation_or_stop": "open object",
                "expected_horizon": "open object",
                "sizing_and_risk": "open object",
                "fees_slippage_and_fill_assumptions": "open object",
                "required_unavailable_data": ["string"],
                "contradictions": ["string"],
                "evidence_refs": ["string"],
                "execution_authority": False,
                "validated_profitability_claim": False,
            }
        ],
        "uncertainty": "open object",
        "first_lock": "required open object",
        "frozen_rt_state": "required open object",
        "general_market_projection_authority": (
            "DENIED; only exhaustion-specific pre-birth detectability, detection latency, and "
            "duration estimation are authorized"
        ),
        "additional_properties": "allowed; no fixed event/family/category/count possibilities",
    }


def forecaster_output_contract() -> dict[str, Any]:
    contract = prior._required_output_contract(FrankieRole.FORECASTER.value)
    contract["rt_state_sha256"] = "exact frozen Real-Time Frankie state SHA-256"
    contract["forecast_curve"] = {
        "curve_id": "canonical content-derived string",
        "as_of_event_clock_ns": "integer",
        "as_of_receive_clock_ns": "integer",
        "path_regime": "open-world string",
        "points": [
            {
                "horizon_or_timestamp": "future horizon or exact timestamp",
                "target_event_time_ns": "strictly increasing future integer event timestamp",
                "scenario_id": "stable path identifier",
                "rt_state_sha256": "exact frozen RT state SHA-256",
                "rt_candidate_ids": "array of exact frozen RT candidate IDs used at this point",
                "clock_ledger": (
                    "required separate source/event, receive, evidence-availability, decision/as-of, "
                    "and target clocks"
                ),
                "central_path_value": "number or null when no honest centre is supported",
                "distribution_or_range": "required open object",
                "conditions": ["string"],
                "catalysts": ["string"],
                "disconfirmers": ["string"],
                "confidence": "number in [0,1]",
                "missingness": ["string"],
                "rt_feed_effect": "how frozen RT evidence changed or did not change this point",
                "dipole_path": "required conditional dipole/pressure path object or explicit UNKNOWN/UNAVAILABLE",
            }
        ],
        "continuity_reasoning": "how the plotted points form one time-evolving curve",
        "multimodal_paths": "separate path objects; never averaged together",
        "abstention": "open object",
    }
    contract["dipole_scenarios"] = (
        "separate conditional dipole paths bound to the frozen observed RT dipole state; "
        "never average materially distinct regimes"
    )
    contract["helper_usage"] = {
        "available": True,
        "invoked": "boolean",
        "invocation_count": "integer 0 or 1",
        "reason": "string",
        "helper_model": "gpt-5.6-sol when invoked; null otherwise",
        "helper_request_hash": "SHA-256 when invoked; null otherwise",
        "helper_response_hash": "SHA-256 when invoked; null otherwise",
        "advisory_findings_used": "boolean",
        "helper_evidence_refs": ["helper finding/source references when used"],
        "rejection_reason": "string when invoked but not used; null otherwise",
    }
    contract["knowledge_usage"] = {
        "complete_bundle_available": True,
        "inventory_receipt_hash": "exact lawful-knowledge inventory receipt SHA-256",
        "sources_consulted": ["exact inventory paths"],
        "sources_uninspected": ["exact complementary inventory paths"],
        "bytes_loaded_into_principal_context": "nonnegative integer",
        "estimated_total_principal_input_tokens": "integer no greater than 150000",
        "every_bundle_byte_claimed_loaded": "boolean; must be false unless byte accounting proves it",
        "uninspected_source_treated_as_absent": False,
    }
    contract["forward_exhaustion_correlations"] = [
        {
            "relationship_id": "string",
            "forecast_horizon": "open object",
            "fields": ["string"],
            "lags_seconds": ["number"],
            "as_of_event_clock_ns": "integer",
            "as_of_receive_clock_ns": "integer",
            "mechanism": "string",
            "evidence_refs": ["string"],
            "uncertainty": "string",
            "falsifier": "string",
        }
    ]
    contract["novel_correlation_search_coverage"] = {
        "fields_depths_mechanisms_interactions_searched": ["string"],
        "lags_and_clock_relationships_searched": ["string"],
        "sequence_motifs_searched": ["string"],
        "none_found_records": ["string"],
    }
    contract["secondary_forward_exhaustion_search_is_not_a_success_gate"] = True
    return contract


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bind_direct_packet_token_cap(packet: dict[str, Any], cap: int) -> dict[str, Any]:
    estimate = math.ceil(len(canonical(packet)) * TOKEN_ESTIMATE_PER_BYTE)
    bound = {
        **packet,
        "direct_packet_token_budget": {
            "estimated_input_tokens": estimate,
            "estimator_tokens_per_byte": TOKEN_ESTIMATE_PER_BYTE,
            "maximum_estimated_input_tokens": cap,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        },
    }
    final_estimate = math.ceil(len(canonical(bound)) * TOKEN_ESTIMATE_PER_BYTE)
    bound["direct_packet_token_budget"]["estimated_input_tokens"] = final_estimate
    if final_estimate > cap:
        raise prior.TwoFrankieBlindError(
            f"{packet.get('role')} direct Work packet estimated at {final_estimate} tokens; cap is {cap}"
        )
    return bound


def write_json(path: Path, value: Any) -> None:
    raw = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(raw)


def assert_keyless_environment() -> None:
    forbidden = [name for name in ("OPENAI_API_KEY", "MARKETS_OPENAI_API_KEY") if os.environ.get(name)]
    if forbidden:
        raise prior.TwoFrankieBlindError(
            "Work-mode packet preparation refuses provider credentials: " + ", ".join(forbidden)
        )


def assert_forecaster_direct(receipt: dict[str, Any]) -> None:
    leaves = receipt.get("leaf_items")
    blocks = receipt.get("block_items")
    surfaces = receipt.get("surface_items")
    if not isinstance(leaves, list) or len(leaves) != prior.EXPECTED_BIGSUITE_LEAVES:
        raise prior.TwoFrankieBlindError("Forecaster direct leaf roster is not exactly 1,940")
    if not isinstance(blocks, list) or len(blocks) != prior.EXPECTED_BIGSUITE_BLOCKS:
        raise prior.TwoFrankieBlindError("Forecaster direct block roster is not exactly 46")
    if not isinstance(surfaces, list) or len(surfaces) != 24:
        raise prior.TwoFrankieBlindError("Forecaster direct surface roster is not exactly 24")
    if len({row.get("item_id") for row in leaves}) != prior.EXPECTED_BIGSUITE_LEAVES:
        raise prior.TwoFrankieBlindError("Forecaster leaf identities are not unique")
    if sum(int(row.get("leaf_count") or 0) for row in blocks) != prior.EXPECTED_BIGSUITE_LEAVES:
        raise prior.TwoFrankieBlindError("Forecaster blocks do not reconcile to 1,940 leaves")
    if len({row.get("block_id") for row in blocks}) != prior.EXPECTED_BIGSUITE_BLOCKS:
        raise prior.TwoFrankieBlindError("Forecaster block identities are not unique")
    if len({row.get("surface_id") for row in surfaces}) != 24:
        raise prior.TwoFrankieBlindError("Forecaster surface identities are not unique")
    dormant = [
        str(row.get("item_id") or row.get("block_id") or row.get("surface_id"))
        for row in [*leaves, *blocks, *surfaces]
        if row.get("state") == "DORMANT" or row.get("availability") == "DORMANT"
    ]
    if dormant:
        raise prior.TwoFrankieBlindError(
            "Forecaster has dormant capability entries: " + ", ".join(dormant[:10])
        )
    invalid_availability = [
        row for row in [*leaves, *blocks, *surfaces]
        if row.get("availability") not in {"AVAILABLE", "PARTIAL", "UNAVAILABLE", "UNKNOWN"}
    ]
    if invalid_availability:
        raise prior.TwoFrankieBlindError("Forecaster availability contains an invalid state")
    non_direct = [
        str(row.get("item_id") or row.get("block_id") or row.get("surface_id"))
        for row in [*leaves, *blocks, *surfaces]
        if row.get("state") != "DIRECT"
    ]
    if non_direct:
        raise prior.TwoFrankieBlindError(
            "Forecaster capability route is not DIRECT: " + ", ".join(non_direct[:10])
        )


def assert_rt_role_policy(overlay: dict[str, Any], receipt: dict[str, Any]) -> None:
    expected = {
        "full_raw_mbo_events": ("DORMANT", "UNAVAILABLE"),
        "top20_book_and_fifo": ("DORMANT", "UNAVAILABLE"),
        "historical_analogs_and_calibration": ("DORMANT", "UNKNOWN"),
        "step1_revealed_retrospective_evidence": ("DORMANT", "DORMANT"),
        "rt_on_demand_evidence_scout": ("TOOL_ACCESSIBLE", "AVAILABLE"),
        "frozen_rt_state": ("DORMANT", "DORMANT"),
    }
    configured = overlay.get("role_surface_overrides", {}).get("REAL_TIME_FRANKIE", {})
    for surface_id, (state, availability) in expected.items():
        row = configured.get(surface_id)
        if not isinstance(row, dict) or (row.get("state"), row.get("availability")) != (
            state,
            availability,
        ):
            raise prior.TwoFrankieBlindError(
                f"Real-Time Frankie role-specific routing drift: {surface_id}"
            )
    received = {row["surface_id"]: row for row in receipt["surface_items"]}
    for surface_id, (state, availability) in expected.items():
        row = received.get(surface_id, {})
        if (row.get("state"), row.get("availability")) != (state, availability):
            raise prior.TwoFrankieBlindError(
                f"Real-Time Frankie materialized routing drift: {surface_id}"
            )


def forecaster_direct_role_context(role_context: dict[str, Any]) -> dict[str, Any]:
    """Restore canonical DIRECT static bytes while avoiding a second leaf-roster copy."""
    compact = prior._compact_role_context(role_context)
    direct_static = role_context.get("direct_static_surfaces")
    if not isinstance(direct_static, dict) or not direct_static:
        raise prior.TwoFrankieBlindError("Forecaster canonical direct-static context is absent")
    for surface_id, surface in direct_static.items():
        if not isinstance(surface, dict):
            raise prior.TwoFrankieBlindError(
                f"Forecaster direct-static surface is malformed: {surface_id}"
            )
        sources = surface.get("direct_sources")
        if not isinstance(sources, list) or any(
            not isinstance(row, dict) or not isinstance(row.get("content"), str)
            for row in sources
        ):
            raise prior.TwoFrankieBlindError(
                f"Forecaster direct-static bytes are absent: {surface_id}"
            )
    compact["direct_static_surfaces"] = direct_static
    compact["bigsuite_registry_route"] = (
        "COMPLETE_DIRECT_REGISTRY_IN_complete_direct_capability_registry_NO_DUPLICATE_COPY"
    )
    return compact


def forecaster_direct_registry(receipt: dict[str, Any]) -> dict[str, Any]:
    """Columnar full registry: every identity once, no repeated false value claims."""
    leaves = receipt["leaf_items"]
    if any(
        row.get("state") != "DIRECT"
        or row.get("availability") != "UNKNOWN"
        or row.get("coverage") is not None
        for row in leaves
    ):
        raise prior.TwoFrankieBlindError(
            "Forecaster leaf roster cannot use the exact compact UNKNOWN-value encoding"
        )
    paths = [str(row["path"]) for row in leaves]
    if len(paths) != prior.EXPECTED_BIGSUITE_LEAVES or len(set(paths)) != len(paths):
        raise prior.TwoFrankieBlindError("Forecaster compact leaf-path roster drift")
    core = {
        "schema": "FRANKIE_FORECASTER_COMPLETE_DIRECT_REGISTRY_COLUMNAR_V1_20260825",
        "leaf_count": len(paths),
        "block_count": len(receipt["block_items"]),
        "surface_count": len(receipt["surface_items"]),
        "leaf_paths": paths,
        "leaf_item_id_rule": "item_id = 'bigsuite:' + leaf_path",
        "all_leaf_routes": "DIRECT",
        "all_leaf_value_availability": "UNKNOWN",
        "all_leaf_values": None,
        "all_leaf_coverage": None,
        "all_leaf_provenance": leaves[0]["provenance"],
        "all_leaf_omission_reason": leaves[0]["omission_reason"],
        "semantic_rule": "UNKNOWN never means false or zero; registry identity is not a value receipt.",
        "block_items": receipt["block_items"],
        "surface_items": receipt["surface_items"],
        "source_full_receipt_hash": receipt["receipt_hash"],
        "source_full_receipt_file": "CAPABILITY_RECONCILIATION.json",
    }
    return {**core, "registry_hash": sha256_json(core)}


def write_scout_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            for row in rows:
                zipped.write(canonical(row) + b"\n")


def write_forecaster_knowledge_bundle(
    bundle_path: Path, manifest_path: Path
) -> dict[str, Any]:
    """Publish every lawful knowledge source without reading denied/sealed bytes."""
    for path, expected in (
        (KNOWLEDGE_INVENTORY_BUILDER_PATH, EXPECTED_KNOWLEDGE_INVENTORY_BUILDER_SHA256),
        (KNOWLEDGE_INVENTORY_MAP_PATH, EXPECTED_KNOWLEDGE_INVENTORY_MAP_SHA256),
    ):
        if sha256_file(path) != expected:
            raise prior.TwoFrankieBlindError(f"bound lawful knowledge inventory drift: {path}")
    specs = production_source_specs(prior.REPO_ROOT)
    if not specs or len({spec.path for spec in specs}) != len(specs):
        raise prior.TwoFrankieBlindError("lawful knowledge inventory paths are absent or duplicated")
    inventory_rows = [
        {
            "path": spec.path,
            "authority": spec.authority.value,
            "access_policy": spec.access_policy.value,
            "target_relationship": spec.target_relationship.value,
            "supersedes": list(spec.supersedes),
        }
        for spec in sorted(specs, key=lambda item: item.path)
    ]
    inventory_receipt_hash = sha256_json(inventory_rows)
    counts = {policy.value: 0 for policy in AccessPolicy}
    served_bytes = 0
    served_rows: list[dict[str, Any]] = []
    descriptor_rows: list[dict[str, Any]] = []
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(bundle_path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            for spec in sorted(specs, key=lambda item: item.path):
                is_step1_answer = (
                    spec.target_relationship is TargetRelationship.OCTOBER_STEP1_ANSWER
                )
                is_servable = spec.access_policy in {
                    AccessPolicy.SERVE,
                    AccessPolicy.SHADOW_ONLY,
                }
                if is_step1_answer and is_servable:
                    raise prior.TwoFrankieBlindError(
                        f"Step-1 answer source is incorrectly servable: {spec.path}"
                    )
                counts[spec.access_policy.value] += 1
                identity = {
                    "path": spec.path,
                    "authority": spec.authority.value,
                    "access_policy": spec.access_policy.value,
                    "target_relationship": spec.target_relationship.value,
                    "supersedes": list(spec.supersedes),
                }
                if spec.access_policy in {AccessPolicy.SERVE, AccessPolicy.SHADOW_ONLY}:
                    source = prior.REPO_ROOT / spec.path
                    source_bytes = source.read_bytes()
                    try:
                        content = source_bytes.decode("utf-8")
                    except UnicodeDecodeError as exc:
                        raise prior.TwoFrankieBlindError(
                            f"lawful Forecaster knowledge source is not UTF-8: {spec.path}"
                        ) from exc
                    row = {
                        **identity,
                        "byte_length": len(source_bytes),
                        "sha256": hashlib.sha256(source_bytes).hexdigest(),
                        "content": content,
                        "content_present": True,
                        "shadow_claims_are_nonbinding": (
                            spec.access_policy is AccessPolicy.SHADOW_ONLY
                        ),
                    }
                    served_bytes += len(source_bytes)
                    served_rows.append(
                        {
                            key: row[key]
                            for key in (
                                "path", "authority", "access_policy", "target_relationship",
                                "byte_length", "sha256", "shadow_claims_are_nonbinding",
                            )
                        }
                    )
                    served_rows[-1]["retrieval_payload_bytes"] = len(canonical(row)) + 1
                    zipped.write(canonical(row) + b"\n")
                else:
                    descriptor_rows.append(
                        {
                            **identity,
                            "content_present": False,
                            "content_accessed": False,
                        }
                    )
    manifest = {
        "schema": "FRANKIE_FORECASTER_LAWFUL_KNOWLEDGE_MANIFEST_V1_20260825",
        "surface_id": "current_brain_and_learned_knowledge",
        "bundle_file": bundle_path.name,
        "bundle_sha256": sha256_file(bundle_path),
        "bundle_bytes": bundle_path.stat().st_size,
        "uncompressed_lawful_source_bytes": served_bytes,
        "inventory_source_count": len(specs),
        "inventory_receipt_hash": inventory_receipt_hash,
        "governing_inventory_builder_sha256": EXPECTED_KNOWLEDGE_INVENTORY_BUILDER_SHA256,
        "governing_inventory_map_sha256": EXPECTED_KNOWLEDGE_INVENTORY_MAP_SHA256,
        "source_count_by_access_policy": counts,
        "lawful_content_source_count": len(served_rows),
        "lawful_content_sources": served_rows,
        "nonservable_descriptors": descriptor_rows,
        "all_serve_and_shadow_sources_present_byte_for_byte": (
            len(served_rows)
            == counts[AccessPolicy.SERVE.value] + counts[AccessPolicy.SHADOW_ONLY.value]
        ),
        "sealed_or_denied_content_read_by_this_code_path": any(
            row.get("content_accessed") is not False for row in descriptor_rows
        ),
        "step1_answer_content_present": any(
            row["target_relationship"] == TargetRelationship.OCTOBER_STEP1_ANSWER.value
            and row.get("content_present") is True
            for row in [*served_rows, *descriptor_rows]
        ),
        "shadow_claims_are_nonbinding": True,
        "zero_lawful_source_omissions": (
            len(served_rows) + len(descriptor_rows) == len(specs)
        ),
    }
    if (
        not manifest["all_serve_and_shadow_sources_present_byte_for_byte"]
        or manifest["sealed_or_denied_content_read_by_this_code_path"]
        or manifest["step1_answer_content_present"]
        or not manifest["zero_lawful_source_omissions"]
    ):
        raise prior.TwoFrankieBlindError("lawful knowledge inventory reconciliation failed")
    manifest["receipt_hash"] = sha256_json(manifest)
    write_json(manifest_path, manifest)
    return manifest


def build(source: Path, output_root: Path, run_id: str) -> None:
    assert_keyless_environment()
    prior._blind_path_check(source)
    if not run_id.strip():
        raise prior.TwoFrankieBlindError("run-id is required")
    if output_root.exists():
        raise prior.TwoFrankieBlindError("output root already exists")

    source_receipt = prior._validate_october_child(source)
    rows, source_manifest = prior.load_prior_surface(source)
    day_context = prior.build_day_context(rows, source_manifest)
    prior._blind_object_check(day_context)

    overlay = prior.read_json(prior.CAPABILITY_OVERLAY)
    rt_context = build_role_context_payload(prior.REPO_ROOT, FrankieRole.REAL_TIME)
    fc_context = build_role_context_payload(prior.REPO_ROOT, FrankieRole.FORECASTER)
    rt_availability = prior._capability_availability(rt_context, overlay)
    fc_availability = prior._capability_availability(fc_context, overlay)
    assert_rt_role_policy(overlay, rt_availability)
    assert_forecaster_direct(fc_availability)

    output_root.mkdir(parents=True, exist_ok=False)
    preflight = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_KEYLESS_PREFLIGHT_V1_20260825",
        "evidence_surface_label": "PRIOR_REDUCED_NON_FULL_MBO_SURFACE",
        "window": {
            "start": prior.TARGET_START_ISO,
            "end_exclusive": prior.TARGET_END_EXCLUSIVE_ISO,
        },
        "source_bytes": prior.EXPECTED_SECONDS_BYTES,
        "source_sha256": prior.EXPECTED_SECONDS_SHA256,
        "principal_role_order": [
            FrankieRole.REAL_TIME.value,
            FrankieRole.FORECASTER.value,
        ],
        "principal_role_calls": 2,
        "optional_forecaster_helper_maximum_calls": 1,
        "model_requested": prior.MODEL,
        "provider_api_called": False,
        "openai_key_used": False,
        "cli_model_called": False,
        "canary": False,
        "tests": False,
        "study_design": "ANSWER_KEY_BLIND_RETROSPECTIVE_DISCOVERY",
    }
    preflight["receipt_hash"] = sha256_json(preflight)
    write_json(output_root / "PREFLIGHT.json", preflight)
    source_verify = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_SOURCE_VERIFY_V2_WORKMODE_20260825",
        "evidence_surface_label": "PRIOR_REDUCED_NON_FULL_MBO_SURFACE",
        "bytes": prior.EXPECTED_SECONDS_BYTES,
        "sha256": prior.EXPECTED_SECONDS_SHA256,
        "window_start": prior.TARGET_START_ISO,
        "window_end_exclusive": prior.TARGET_END_EXCLUSIVE_ISO,
        "receipt_file_sha256": source_receipt["receipt_file_sha256"],
        "receipt_canonical_sha256": source_receipt["receipt_canonical_sha256"],
        "verified": True,
        "openai_key_used": False,
        "provider_api_called": False,
        "cli_model_called": False,
    }
    source_verify["receipt_hash"] = sha256_json(source_verify)
    write_json(output_root / "SOURCE_VERIFY.json", source_verify)
    write_json(output_root / "SLICE_MANIFEST.json", source_manifest)

    answer_wall = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_ANSWER_WALL_V2_WORKMODE_20260825",
        "answer_key_or_step1_results_exposed": False,
        "step1_answer_key_exposed": False,
        "comparison_accessed": False,
        "answer_key_release_authorized": False,
        "allowed_surface": "PRIOR_REDUCED_NON_FULL_MBO_SURFACE",
        "54_week_answer_population_exposed": False,
        "step1_answer_clocks_exposed": False,
    }
    answer_wall["receipt_hash"] = sha256_json(answer_wall)
    write_json(output_root / "ANSWER_WALL.json", answer_wall)

    capability = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_DUAL_ROLE_CAPABILITY_RECONCILIATION_V2_WORKMODE_20260825",
        "evidence_surface_label": "PRIOR_REDUCED_NON_FULL_MBO_SURFACE",
        "REAL_TIME_FRANKIE": rt_availability,
        "FORECASTER_FRANKIE": fc_availability,
        "leaf_count": prior.EXPECTED_BIGSUITE_LEAVES,
        "block_count": prior.EXPECTED_BIGSUITE_BLOCKS,
        "surface_count": 24,
        "forecaster_direct_no_dormant": True,
        "realtime_role_specific_dormant_preserved": True,
        "zero_silent_omissions": True,
    }
    capability["receipt_hash"] = sha256_json(capability)
    write_json(output_root / "CAPABILITY_RECONCILIATION.json", capability)
    write_json(output_root / "RT_CAPABILITIES.json", rt_availability)
    write_scout_rows(output_root / "RT_SCOUT_ROWS.jsonl.gz", rows)
    knowledge_manifest = write_forecaster_knowledge_bundle(
        output_root / "FORECASTER_LAWFUL_KNOWLEDGE.jsonl.gz",
        output_root / "FORECASTER_LAWFUL_KNOWLEDGE_MANIFEST.json",
    )

    common = {
        "schema": SCHEMA,
        "run_id": run_id,
        "model": prior.MODEL,
        "evidence_surface_label": "PRIOR_REDUCED_NON_FULL_MBO_SURFACE",
        "source_manifest": source_manifest,
        "direct_day_specific_context": day_context,
        "sealed_step1_results_exposed": False,
        "execution_surface": "CHATGPT_WORK_SEQUENTIAL_AGENTS",
        "external_provider_api": False,
        "token_caps": {
            "estimator_tokens_per_byte": TOKEN_ESTIMATE_PER_BYTE,
            "rt_direct_input_tokens": RT_DIRECT_INPUT_TOKEN_CAP,
            "rt_cumulative_input_tokens": RT_CUMULATIVE_INPUT_TOKEN_CAP,
            "forecaster_input_tokens": FORECASTER_INPUT_TOKEN_CAP,
            "max_output_tokens_per_principal_role": MAX_OUTPUT_TOKENS,
        },
    }
    rt_method_sources = {}
    for method_id, path in (
        ("SIGNED_INFORMATION_DIPOLE_DIRECTION_AND_CHANGE", INFO_DIPOLE_PATH),
        ("BOUNDED_LATS_LOOKAHEAD_SHADOW", LATS_LOOKAHEAD_PATH),
    ):
        raw = path.read_bytes()
        rt_method_sources[method_id] = {
            "path": str(path.relative_to(prior.REPO_ROOT)),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "byte_length": len(raw),
            "content": raw.decode("utf-8"),
            "authority": "BINDING_CURRENT" if method_id.startswith("SIGNED") else "PROVISIONAL_SHADOW",
            "access_policy": "SERVE" if method_id.startswith("SIGNED") else "SHADOW_ONLY",
        }
    rt_packet = {
        **common,
        "role": FrankieRole.REAL_TIME.value,
        "mission": prior.RT_MISSION_PATH.read_text(encoding="utf-8"),
        "instructions": work_instructions(FrankieRole.REAL_TIME, prior.RT_MISSION_PATH),
        "role_is_forecasting": False,
        "role_objective": "DETECT_AND_CHARACTERIZE_EXHAUSTION",
        "direct_direction_and_lookahead_methods": rt_method_sources,
        "role_context": prior._compact_role_context(rt_context),
        "capability_availability_summary": {
            "receipt_hash": rt_availability["receipt_hash"],
            "leaf_count": prior.EXPECTED_BIGSUITE_LEAVES,
            "block_count": prior.EXPECTED_BIGSUITE_BLOCKS,
            "full_receipt_file": "RT_CAPABILITIES.json",
        },
        "optional_local_scout": {
            "auto_call": False,
            "model_or_provider_subcall": False,
            "maximum_invocations": 1,
            "maximum_response_input_tokens": (
                RT_CUMULATIVE_INPUT_TOKEN_CAP - RT_DIRECT_INPUT_TOKEN_CAP
            ),
            "rows_file": "RT_SCOUT_ROWS.jsonl.gz",
            "capabilities_file": "RT_CAPABILITIES.json",
            "request_contract": {
                "schema": "FRANKIE_RT_LOCAL_SCOUT_REQUEST_V1_20260825",
                "operation": "ROW_RANGE or FIELD_SERIES",
                "candidate_event_id": "exact provisional or final content-derived candidate ID",
                "decision_cutoff_ns": "maximum lawful event-time retrieval cutoff",
                "event_time_start_ns": "integer inside supplied window",
                "event_time_end_exclusive_ns": "integer inside supplied window",
                "field_paths": "bounded array of exact source fields",
                "maximum_rows": "positive integer",
                "allowed_input_hashes": (
                    "exact hashes for RT_SCOUT_ROWS.jsonl.gz and RT_CAPABILITIES.json"
                ),
            },
            "response_contract": {
                "schema": "FRANKIE_RT_LOCAL_SCOUT_RESPONSE_V1_20260825",
                "request_sha256": "exact request SHA-256",
                "operation": "must equal request operation",
                "rows": (
                    "array of {source_row_index,event_time_ns,fields}; exact bound-source values, "
                    "requested fields only, ordered, and no longer than maximum_rows"
                ),
                "row_count": "must equal rows length",
                "truncated": "boolean",
            },
            "receipt_required_when_invoked": True,
        },
        "helper_agents": None,
        "required_output_contract": rt_output_contract(),
    }
    rt_packet = bind_direct_packet_token_cap(rt_packet, RT_DIRECT_INPUT_TOKEN_CAP)
    prior._blind_object_check(rt_packet)
    rt_packet["packet_hash"] = sha256_json(rt_packet)
    write_json(output_root / "RT_WORK_PACKET.json", rt_packet)

    fc_packet = {
        **common,
        "role": FrankieRole.FORECASTER.value,
        "mission": prior.FORECASTER_MISSION_PATH.read_text(encoding="utf-8"),
        "instructions": work_instructions(FrankieRole.FORECASTER, prior.FORECASTER_MISSION_PATH),
        "role_is_forecasting": True,
        "secondary_forward_exhaustion_correlation_search": True,
        "secondary_search_is_success_gate": False,
        "role_context": forecaster_direct_role_context(fc_context),
        "complete_direct_capability_registry": forecaster_direct_registry(fc_availability),
        "complete_direct_capability_registry_hash": fc_availability["receipt_hash"],
        "forecaster_has_dormant_entries": False,
        "complete_lawful_knowledge_plane": {
            "bundle_file": "FORECASTER_LAWFUL_KNOWLEDGE.jsonl.gz",
            "manifest_file": "FORECASTER_LAWFUL_KNOWLEDGE_MANIFEST.json",
            "manifest_receipt_hash": knowledge_manifest["receipt_hash"],
            "bundle_sha256": knowledge_manifest["bundle_sha256"],
            "all_serve_and_shadow_sources_present_byte_for_byte": True,
            "sealed_or_denied_content_read": False,
            "complete_bundle_preserved_and_addressable": True,
            "required_inventory_and_authority_review_before_final_answer": True,
            "model_visible_bytes_must_be_hash_receipted": True,
            "all_bundle_bytes_claimed_inside_principal_context": False,
            "retrieval_rule": (
                "Use deterministic hash-bound local retrieval from the complete bundle as needed; "
                "record inspected and uninspected sources and never treat an uninspected source as absent."
            ),
        },
        "forecaster_tools": {
            "optional_knowledge_helper_agent": {
                "available": True,
                "auto_call": False,
                "maximum_invocations": 1,
                "model": prior.MODEL,
                "input_token_cap": FORECASTER_HELPER_INPUT_TOKEN_CAP,
                "output_token_cap": FORECASTER_HELPER_OUTPUT_TOKEN_CAP,
                "allowed_inputs": [
                    "FORECASTER_LAWFUL_KNOWLEDGE.jsonl.gz",
                    "FORECASTER_LAWFUL_KNOWLEDGE_MANIFEST.json",
                    "RT_FROZEN_STATE.json",
                    "ONEWAY_HANDOFF.json",
                ],
                "request_contract": {
                    "selected_source_paths": "unique lawful inventory subset",
                    "selected_source_bytes": "exact serialized retrieval-payload byte sum",
                    "estimated_input_tokens": "integer no greater than 48000",
                    "allowed_input_hashes": "exact filename-to-SHA-256 map",
                    "model_visible_input_files": (
                        "manifest, frozen RT state, and one-way handoff; full bundle is addressable"
                    ),
                    "causal_cutoff": "exact frozen RT as-of object",
                },
                "authority": "ADVISORY_RETRIEVAL_AND_CROSS_SOURCE_RECONCILIATION_ONLY",
                "may_own_forecast_or_lock": False,
                "may_access_step1_answers": False,
            },
            "specialists": None,
            "evidence_scout": None,
            "repair_or_fallback": None,
        },
        "authoritative_frozen_rt_state": "INJECT_AFTER_RT_FREEZE",
        "required_output_contract": forecaster_output_contract(),
        "current_reconstruction_authority": "DENIED_USE_FROZEN_RT_STATE",
    }
    fc_packet = bind_direct_packet_token_cap(fc_packet, FORECASTER_BASE_PACKET_TOKEN_CAP)
    prior._blind_object_check(fc_packet)
    fc_packet["packet_hash"] = sha256_json(fc_packet)
    write_json(output_root / "FORECASTER_BASE_WORK_PACKET.json", fc_packet)

    artifact_rows = []
    for path in sorted(output_root.iterdir()):
        if path.is_file():
            artifact_rows.append(
                {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            )
    manifest = {
        "schema": "FRANKIE_PRIOR_SURFACE_OCT45_WORK_PACKET_MANIFEST_V1_20260825",
        "artifacts": artifact_rows,
        "external_provider_api_called": False,
        "openai_key_used": False,
        "logical_role_calls_completed": 0,
        "next_role": FrankieRole.REAL_TIME.value,
    }
    manifest["receipt_hash"] = sha256_json(manifest)
    write_json(output_root / "WORK_PACKET_MANIFEST.json", manifest)
    complete = {
        "schema": SCHEMA,
        "status": "WORK_PACKETS_READY_MODEL_NOT_CALLED",
        "published_last": True,
        "manifest_receipt_hash": manifest["receipt_hash"],
        "window": source_manifest["window"],
        "source_sha256": prior.EXPECTED_SECONDS_SHA256,
        "logical_role_calls_completed": 0,
        "next_role": FrankieRole.REAL_TIME.value,
    }
    complete["receipt_hash"] = sha256_json(complete)
    write_json(output_root / "PACKET_COMPLETE.json", complete)

    missing = [name for name in REQUIRED_OUTPUTS if not (output_root / name).is_file()]
    if missing:
        raise prior.TwoFrankieBlindError("packet output roster incomplete: " + ", ".join(missing))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        build(args.source, args.output_root, args.run_id)
    except prior.TwoFrankieBlindError as exc:
        print(f"WORK_PACKET_BUILD=FAIL: {exc}", file=sys.stderr)
        return 2
    print("WORK_PACKET_BUILD=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
