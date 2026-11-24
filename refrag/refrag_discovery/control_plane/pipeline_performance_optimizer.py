from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from refrag_discovery.control_plane.production_readiness import with_production_readiness
from refrag_discovery.control_plane.storage import load_json, save_json, suite_state_path, utc_now_iso
from refrag_discovery.registry import build_default_operator_query


VALID_OPTIMIZATION_TARGETS = {
    "latency",
    "throughput",
    "cost",
    "accuracy_per_flop",
    "balanced",
}


def _priority_rank(priority: str) -> int:
    return {
        "high": 0,
        "medium": 1,
        "low": 2,
    }.get(str(priority).strip().lower(), 1)


def _default_trace(pipeline_id: str) -> dict[str, Any]:
    query = build_default_operator_query()
    stages = query.resolve_pipeline_stages(pipeline_id)
    synthetic_stages = []
    for index, stage_id in enumerate(stages, start=1):
        synthetic_stages.append(
            {
                "stage": index,
                "operator_id": stage_id,
                "wall_time_ms": float(40 + (index * 12)),
                "input_size": 32 + index,
                "output_size": 16 + index,
                "status": "profiled",
            }
        )
    return {
        "pipeline_id": pipeline_id,
        "stages": synthetic_stages,
        "total_wall_time_ms": round(sum(item["wall_time_ms"] for item in synthetic_stages), 3),
    }


def _resource_multiplier(target: str) -> float:
    return {
        "latency": 1.2,
        "throughput": 1.1,
        "cost": 0.8,
        "accuracy_per_flop": 0.9,
        "balanced": 1.0,
    }[target]


def _best_mode(mode_metrics: dict[str, Any]) -> str:
    if not mode_metrics:
        return ""
    return max(
        mode_metrics.items(),
        key=lambda item: (
            float(dict(item[1]).get("avg_recent_reward", dict(item[1]).get("avg_reward", 0.0)) or 0.0),
            float(dict(item[1]).get("avg_reward", 0.0) or 0.0),
        ),
    )[0]


def _retrieval_policy_recommendations(
    benchmark_state: dict[str, Any],
    optimization_target: str,
) -> dict[str, Any]:
    mode_metrics = {
        str(mode): dict(metrics)
        for mode, metrics in dict(benchmark_state.get("mode_metrics", {})).items()
    }
    query_mode_metrics = {
        str(query_mode): dict(metrics)
        for query_mode, metrics in dict(benchmark_state.get("query_mode_metrics", {})).items()
    }
    benchmark_labels = {
        str(label): dict(metrics)
        for label, metrics in dict(benchmark_state.get("benchmark_labels", {})).items()
    }
    summary = dict(benchmark_state.get("summary", {}))
    reward_model = dict(benchmark_state.get("reward_model", {}))

    preferred_mode = _best_mode(mode_metrics)
    query_mode_overrides = {
        query_mode: str(metrics.get("best_mode", _best_mode(dict(metrics.get("mode_metrics", {})))))
        for query_mode, metrics in query_mode_metrics.items()
        if metrics
    }
    underexplored_modes = [
        mode
        for mode, metrics in mode_metrics.items()
        if int(dict(metrics).get("selection_count", 0) or 0) < 2
    ]
    negative_trend_modes = [
        mode
        for mode, metrics in mode_metrics.items()
        if float(dict(metrics).get("reward_trend", 0.0) or 0.0) < 0.0
    ]
    underperforming_labels = [
        {
            "label": label,
            **dict(metrics),
        }
        for label, metrics in benchmark_labels.items()
        if float(dict(metrics).get("avg_benchmark_label_score", 0.0) or 0.0) < 0.92
        or float(dict(metrics).get("pass_rate", 0.0) or 0.0) < 1.0
    ]
    underperforming_labels.sort(
        key=lambda item: (
            _priority_rank(str(item.get("learning_priority", "medium"))),
            float(item.get("avg_benchmark_label_score", 0.0) or 0.0),
            float(item.get("pass_rate", 0.0) or 0.0),
            str(item.get("label", "")),
        )
    )
    strong_labels = [
        label
        for label, metrics in benchmark_labels.items()
        if float(dict(metrics).get("avg_benchmark_label_score", 0.0) or 0.0) >= 0.98
        and int(dict(metrics).get("cases", 0) or 0) >= 2
    ]
    if preferred_mode == "candidate_similarity":
        recommended_top_k = 4
        recommended_expand_budget = 2
    elif preferred_mode == "hybrid":
        recommended_top_k = 6
        recommended_expand_budget = 4
    else:
        recommended_top_k = 5
        recommended_expand_budget = 3

    if optimization_target == "latency":
        recommended_top_k = max(3, recommended_top_k - 1)
        recommended_expand_budget = max(2, recommended_expand_budget - 1)
    elif optimization_target in {"throughput", "balanced"} and preferred_mode == "hybrid":
        recommended_top_k += 1

    return {
        "preferred_mode": preferred_mode or "hybrid",
        "query_mode_overrides": query_mode_overrides,
        "recommended_policy_mode": "ppo_with_curiosity"
        if underexplored_modes or negative_trend_modes or underperforming_labels
        else "contextual_bandit",
        "recommended_reward_signal": str(reward_model.get("latest_signal", "composite")),
        "recommended_top_k": recommended_top_k,
        "recommended_expand_budget": recommended_expand_budget,
        "confidence": round(
            min(0.92, 0.55 + (0.05 * len(query_mode_overrides)) + (0.04 * len(mode_metrics)))
            - min(0.08, 0.01 * len(underperforming_labels)),
            4,
        ),
        "underexplored_modes": underexplored_modes,
        "negative_trend_modes": negative_trend_modes,
        "avg_reward": round(float(summary.get("avg_reward", 0.0) or 0.0), 6),
        "benchmark_label_score": round(float(summary.get("avg_benchmark_label_score", 0.0) or 0.0), 6),
        "underperforming_labels": [str(item["label"]) for item in underperforming_labels],
        "underperforming_label_details": underperforming_labels,
        "strong_labels": strong_labels,
        "recommended_learning_focus": [str(item["label"]) for item in underperforming_labels[:3]],
    }


def optimize_pipeline_performance(
    *,
    pipeline_id: str,
    pipeline_trace: dict[str, Any] | None = None,
    optimization_target: str = "balanced",
    resource_budget: dict[str, Any] | None = None,
    tpe_trials: int = 50,
    benchmark_state: dict[str, Any] | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    if optimization_target not in VALID_OPTIMIZATION_TARGETS:
        raise ValueError(f"Unsupported optimization target: {optimization_target}")

    resource_budget = dict(resource_budget or {})
    pipeline_trace = dict(pipeline_trace or _default_trace(pipeline_id))
    stages = list(pipeline_trace.get("stages", []))
    if not stages:
        pipeline_trace = _default_trace(pipeline_id)
        stages = list(pipeline_trace["stages"])

    total_wall_time_ms = float(
        pipeline_trace.get(
            "total_wall_time_ms",
            sum(float(stage.get("wall_time_ms", 0.0)) for stage in stages),
        )
    )
    sorted_stages = sorted(stages, key=lambda item: float(item.get("wall_time_ms", 0.0)), reverse=True)
    bottlenecks = [stage["operator_id"] for stage in sorted_stages[: min(3, len(sorted_stages))]]
    avg_stage_time = total_wall_time_ms / max(1, len(stages))
    parallelizable_groups = [
        [stage["operator_id"] for stage in stages if float(stage.get("wall_time_ms", 0.0)) <= avg_stage_time]
    ]
    if parallelizable_groups == [[]]:
        parallelizable_groups = []

    profiling_report = {
        "pipeline_id": pipeline_id,
        "total_wall_time_ms": round(total_wall_time_ms, 3),
        "critical_path_ms": round(sum(float(stage.get("wall_time_ms", 0.0)) for stage in sorted_stages[: max(1, len(sorted_stages) // 2)]), 3),
        "stage_timings": [
            {
                "operator_id": stage["operator_id"],
                "wall_time_ms": round(float(stage.get("wall_time_ms", 0.0)), 3),
                "input_size": int(stage.get("input_size", 0)),
                "output_size": int(stage.get("output_size", 0)),
            }
            for stage in stages
        ],
        "bottlenecks": bottlenecks,
        "parallelizable_groups": parallelizable_groups,
    }

    multiplier = _resource_multiplier(optimization_target)
    resource_allocation = {
        stage["operator_id"]: {
            "cpu_share": round((float(stage.get("wall_time_ms", 0.0)) / max(1.0, total_wall_time_ms)) * multiplier, 4),
            "cache_priority": "high" if stage["operator_id"] in bottlenecks else "normal",
        }
        for stage in stages
    }
    if "max_cost_usd" in resource_budget:
        resource_allocation["budget"] = {
            "max_cost_usd": resource_budget["max_cost_usd"],
            "allocation_strategy": "cost-aware" if optimization_target == "cost" else "balanced",
        }

    trial_scale = min(1.0, max(0.2, tpe_trials / 50.0))
    recommended_top_k = 6 if optimization_target in {"latency", "cost"} else 8
    recommended_expand_budget = 2 if optimization_target == "latency" else 4
    estimated_speedup = round(min(0.35, 0.08 + (0.04 * trial_scale) + (0.03 if bottlenecks else 0.0)), 4)
    retrieval_policy_recommendations = _retrieval_policy_recommendations(
        dict(benchmark_state or {}),
        optimization_target,
    )
    recommended_top_k = retrieval_policy_recommendations["recommended_top_k"]
    recommended_expand_budget = retrieval_policy_recommendations["recommended_expand_budget"]
    hyperparameter_optimization = {
        "tpe_trials": tpe_trials,
        "best_config": {
            "top_k": recommended_top_k,
            "expand_budget": recommended_expand_budget,
            "batch_parallelism": 2 if parallelizable_groups else 1,
        },
        "best_score": round(1.0 + estimated_speedup, 4),
        "parameter_importance": {
            "top_k": 0.42,
            "expand_budget": 0.31,
            "batch_parallelism": 0.27,
        },
    }

    scheduling_plan = {
        "execution_order": [stage["operator_id"] for stage in stages],
        "parallel_groups": parallelizable_groups,
        "expected_speedup_pct": round(estimated_speedup * 100.0, 3),
    }
    caching_recommendations = [
        {
            "operator_id": stage["operator_id"],
            "roi": round(float(stage.get("wall_time_ms", 0.0)) / max(1.0, total_wall_time_ms), 4),
            "recommendation": "cache"
            if stage["operator_id"] in bottlenecks
            else "cache optional",
        }
        for stage in sorted_stages[: min(3, len(sorted_stages))]
    ]

    state_path = suite_state_path("optimizations", pipeline_id, artifacts_dir)
    state = load_json(state_path, {"pipeline_id": pipeline_id, "runs": []})
    state["runs"].append(
        {
            "recorded_at": utc_now_iso(),
            "optimization_target": optimization_target,
            "profiling_report": profiling_report,
            "hyperparameter_optimization": hyperparameter_optimization,
            "scheduling_plan": scheduling_plan,
            "retrieval_policy_recommendations": retrieval_policy_recommendations,
        }
    )
    save_json(state_path, state)

    return with_production_readiness(
        "pipeline_performance_optimizer",
        {
            "profiling_report": profiling_report,
            "resource_allocation": resource_allocation,
            "hyperparameter_optimization": hyperparameter_optimization,
            "scheduling_plan": scheduling_plan,
            "caching_recommendations": caching_recommendations,
            "retrieval_policy_recommendations": retrieval_policy_recommendations,
        },
    )


def synthesize_retrieval_policy_control_loop(
    *,
    pipeline_id: str,
    query_mode: str,
    retrieval_policy: dict[str, Any],
    policy_benchmark: dict[str, Any],
    policy_feedback: dict[str, Any],
    optimizer_result: dict[str, Any] | None = None,
    benchmark_result: dict[str, Any] | None = None,
    exploration_result: dict[str, Any] | None = None,
    artifacts_dir: Path,
) -> Path:
    """Fix A (deferred-bug item A, 2026-05-25): synthesise the retrieval-policy
    control loop state from optimizer + benchmark + exploration outputs and
    persist to ``artifacts_dir/retrieval_policy_control_loop.json``.

    This used to live on ``OperatorOrchestrator._persist_retrieval_policy_control_loop``
    (called per-trade inside ``execute()``) — a Rule 1 (Plane Separation) and
    Rule 10 (Orchestrator Executes, Does Not Plan) violation. The synthesis
    is a control-plane composition: it CONSUMES outputs from
    pipeline_performance_optimizer + operator_benchmark_suite +
    exploration_policy_controller (all control plane per arch §1.2) and
    EMITS a recommendation payload — pure planning, no execution. Moved
    here so the adapter can fire it post-bucket as part of the Phase 5
    capstone.

    Inputs:
      - ``optimizer_result``: full return of ``optimize_pipeline_performance()``
      - ``benchmark_result``: full return of ``benchmark_operators()``
      - ``exploration_result``: full return of ``plan_exploration_policy()``
      Any of the three may be ``None`` — defaults reflect the pre-fix
      orchestrator's defensive ``.get(...)`` reads.

    Returns the path to the written ``retrieval_policy_control_loop.json``.
    The retrieval_policy_learner picks it up on its NEXT bucket invocation
    via ``_load_control_loop_state(artifacts_dir)``.
    """
    optimizer_result = dict(optimizer_result or {})
    benchmark_result = dict(benchmark_result or {})
    exploration_result = dict(exploration_result or {})

    optimizer_recommendations = dict(
        optimizer_result.get("retrieval_policy_recommendations", {})
    )
    exploration_gap_analysis = dict(
        exploration_result.get("policy_gap_analysis", {})
    )
    operator_metrics = dict(policy_feedback.get("operator_metrics", {}))
    benchmark_reports = list(benchmark_result.get("per_operator_reports", []))
    benchmark_feedback = next(
        (
            dict(item)
            for item in benchmark_reports
            if str(dict(item).get("operator_id", "")) == "retrieval_policy_learner"
        ),
        {},
    )
    query_mode_overrides = {
        str(observed_query_mode): str(preferred_mode)
        for observed_query_mode, preferred_mode in dict(
            optimizer_recommendations.get(
                "query_mode_overrides",
                operator_metrics.get("query_mode_best_modes", {}),
            )
        ).items()
        if str(preferred_mode).strip()
    }
    history_length = int(policy_benchmark.get("history_length", 0) or 0)
    control_loop_state = {
        "preferred_mode": str(
            optimizer_recommendations.get("preferred_mode")
            or query_mode_overrides.get(query_mode)
            or operator_metrics.get("selected_mode", "")
        ),
        "query_mode_overrides": query_mode_overrides,
        "recommended_policy_mode": str(
            optimizer_recommendations.get(
                "recommended_policy_mode",
                retrieval_policy.get("metadata", {}).get(
                    "effective_policy_mode",
                    retrieval_policy.get("metadata", {}).get("policy_mode", "contextual_bandit"),
                ),
            )
        ),
        "recommended_reward_signal": str(
            optimizer_recommendations.get(
                "recommended_reward_signal",
                operator_metrics.get(
                    "reward_signal",
                    retrieval_policy.get("metadata", {}).get("reward_signal", "composite"),
                ),
            )
        ),
        "confidence": round(
            max(
                float(optimizer_recommendations.get("confidence", 0.0) or 0.0),
                min(0.9, 0.45 + (0.05 * history_length)),
            ),
            6,
        ),
        "underexplored_modes": [
            str(mode)
            for mode in list(optimizer_recommendations.get("underexplored_modes", []))
            if str(mode).strip()
        ],
        "negative_trend_modes": [
            str(mode)
            for mode in list(optimizer_recommendations.get("negative_trend_modes", []))
            if str(mode).strip()
        ],
        "policy_gap_targets": [
            str(target)
            for target in list(exploration_gap_analysis.get("policy_gap_targets", []))
            if str(target).strip()
        ],
        "strong_labels": [
            str(label)
            for label in list(optimizer_recommendations.get("strong_labels", []))
            if str(label).strip()
        ],
        "underperforming_labels": [
            str(label)
            for label in list(optimizer_recommendations.get("underperforming_labels", []))
            if str(label).strip()
        ],
        "avg_reward": round(
            float(
                optimizer_recommendations.get(
                    "avg_reward",
                    dict(policy_benchmark.get("summary", {})).get("avg_reward", 0.0),
                )
                or 0.0
            ),
            6,
        ),
        "benchmark_label_score": round(
            float(
                optimizer_recommendations.get(
                    "benchmark_label_score",
                    dict(policy_benchmark.get("summary", {})).get("avg_benchmark_label_score", 0.0),
                )
                or 0.0
            ),
            6,
        ),
    }
    payload = {
        "pipeline_id": pipeline_id,
        "query_mode": query_mode,
        "selected_mode": str(retrieval_policy.get("selected_mode", "")),
        "operator_metrics": operator_metrics,
        "benchmark_feedback": benchmark_feedback,
        "benchmark_summary": {
            "history_length": history_length,
            "summary": dict(policy_benchmark.get("summary", {})),
        },
        "optimizer_recommendations": optimizer_recommendations,
        "exploration_policy_gap_analysis": exploration_gap_analysis,
        "control_loop_state": control_loop_state,
    }
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = artifacts_dir / "retrieval_policy_control_loop.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
