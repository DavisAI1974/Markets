from __future__ import annotations

from typing import Any


_BASE_GUARDRAILS = [
    "Treat scores and confidence fields as deterministic heuristics, not calibrated probabilities.",
    "Keep outputs behind human review or a stricter policy gate before irreversible external actions.",
    "Record benchmark or trace evidence for any production workflow that consumes this operator.",
]


_HEURISTIC_OPERATOR_SPECS: dict[str, dict[str, Any]] = {
    "cross_domain_transfer_detector": {
        "autonomy_level": "advisory_only",
        "side_effect_scope": "none",
        "release_criteria": [
            "Validate transfer ranking against held-out cross-domain matches.",
            "Replace publication-readiness heuristics with measured replication evidence.",
        ],
        "blocking_gaps": [
            "Transfer confidence is based on capability overlap rather than calibrated outcome data.",
            "Publication readiness remains a proxy derived from candidate counts.",
        ],
    },
    "exploration_policy_controller": {
        "autonomy_level": "advisory_only",
        "side_effect_scope": "artifact_state_only",
        "release_criteria": [
            "Validate prioritization against realized benchmark lift on replayed histories.",
            "Keep exploration plans bounded by explicit compute and risk budgets.",
        ],
        "blocking_gaps": [
            "Priority allocation is heuristic and not optimized from realized outcomes.",
            "Portfolio selection is not yet calibrated against long-run opportunity cost.",
        ],
    },
    "manifest_synthesizer": {
        "autonomy_level": "advisory_only",
        "side_effect_scope": "none",
        "release_criteria": [
            "Validate inferred contracts against successful execution traces before registry admission.",
            "Require manual manifest review before any synthesized operator is published.",
        ],
        "blocking_gaps": [
            "Manifest confidence is based on repeated sequence counts rather than semantic validation.",
            "Generated compositions do not yet verify governance or runtime safety requirements.",
        ],
    },
    "operator_benchmark_suite": {
        "autonomy_level": "measurement_only",
        "side_effect_scope": "artifact_state_only",
        "release_criteria": [
            "Calibrate heuristic proxy scores against real benchmark outcomes.",
            "Validate regression thresholds on historical benchmark incidents.",
        ],
        "blocking_gaps": [
            "Predicted unseen-task performance is a heuristic proxy rather than a learned model.",
            "Benchmark confidence values are not yet calibrated against observed variance.",
        ],
    },
    "operator_chain_builder": {
        "autonomy_level": "advisory_only",
        "side_effect_scope": "none",
        "release_criteria": [
            "Replay suggested chains against held-out task objectives and measure success.",
            "Validate chain ranking quality against observed downstream pipeline outcomes.",
        ],
        "blocking_gaps": [
            "Chain search remains query- and composability-heuristic rather than outcome-trained.",
            "Missing-capability suggestions are inferred from sparse gap recommendations.",
        ],
    },
    "operator_composability_scorer": {
        "autonomy_level": "advisory_only",
        "side_effect_scope": "none",
        "release_criteria": [
            "Measure score calibration against real chain failures and successful compositions.",
            "Validate adapter suggestions against known bridge operators.",
        ],
        "blocking_gaps": [
            "Compatibility scores are inferred from manifest overlap rather than empirical executions.",
            "Predicted failure modes are rule-based and not calibrated from incident data.",
        ],
    },
    "operator_gap_finder": {
        "autonomy_level": "advisory_only",
        "side_effect_scope": "none",
        "release_criteria": [
            "Benchmark missing-gap precision and recall against curated registry snapshots.",
            "Require reviewed draft manifests before any suggested gap-closure operator is created.",
        ],
        "blocking_gaps": [
            "Gap severity is derived from manifest-count heuristics instead of demand data.",
            "Draft recommendations do not yet validate runtime feasibility or governance fit.",
        ],
    },
    "operator_graph_rewriter": {
        "autonomy_level": "approved_execute_only",
        "side_effect_scope": "approved_graph_mutation",
        "release_criteria": [
            "Keep execute mode gated by explicit approval and rollback handling.",
            "Validate simulated rewrite gains on replayed graphs before broad rollout.",
        ],
        "blocking_gaps": [
            "Rewrite proposals and risks are heuristic rather than learned from historical graph edits.",
            "Execution safety depends on caller approval discipline rather than a policy service.",
        ],
        "guardrails": [
            "Do not use execute mode without an explicit approval token.",
        ],
    },
    "operator_promotion_recommender": {
        "autonomy_level": "advisory_only",
        "side_effect_scope": "none",
        "release_criteria": [
            "Validate promotion scores against historical lifecycle and exposure outcomes.",
            "Require governance review before any public promotion decision is enacted.",
        ],
        "blocking_gaps": [
            "Promotion score weights are heuristic and not tuned from realized promotion outcomes.",
            "Counterfactual analysis is synthetic and not backed by observed interventions.",
        ],
    },
    "pipeline_performance_optimizer": {
        "autonomy_level": "advisory_only",
        "side_effect_scope": "artifact_state_only",
        "release_criteria": [
            "Replay optimization recommendations against historical traces and regression gates.",
            "Roll out suggested config changes only behind a controlled approval path.",
        ],
        "blocking_gaps": [
            "Optimization and speedup estimates are heuristic rather than measured via search trials.",
            "Recommended policy-mode transitions are not yet validated online.",
        ],
    },
    "task_meta_learner": {
        "autonomy_level": "advisory_only",
        "side_effect_scope": "artifact_state_only",
        "release_criteria": [
            "Validate recommended configurations against held-out task histories.",
            "Keep autonomous reconfiguration in shadow mode until prediction error is measured.",
        ],
        "blocking_gaps": [
            "Configuration confidence is heuristic and based on taxonomy history counts.",
            "Task classification and performance prediction are not yet trained from richer telemetry.",
        ],
    },
}


def is_heuristic_control_plane_operator(operator_id: str) -> bool:
    return operator_id in _HEURISTIC_OPERATOR_SPECS


def heuristic_production_readiness(operator_id: str) -> dict[str, Any]:
    spec = _HEURISTIC_OPERATOR_SPECS[operator_id]
    guardrails = list(_BASE_GUARDRAILS) + list(spec.get("guardrails", []))
    return {
        "criteria_version": "heuristic_guardrails_v1",
        "operator_id": operator_id,
        "implementation_type": "deterministic_heuristic_proxy",
        "production_ready": False,
        "confidence_calibration": "uncalibrated_heuristic",
        "requires_human_review": True,
        "bounded_outputs": True,
        "autonomy_level": str(spec["autonomy_level"]),
        "side_effect_scope": str(spec["side_effect_scope"]),
        "guardrails": guardrails,
        "release_criteria": list(spec["release_criteria"]),
        "blocking_gaps": list(spec["blocking_gaps"]),
    }


def with_production_readiness(operator_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(payload)
    enriched["production_readiness"] = heuristic_production_readiness(operator_id)
    return enriched
