from __future__ import annotations

from pathlib import Path
from typing import Any

from refrag_discovery.control_plane.production_readiness import with_production_readiness
from refrag_discovery.control_plane.operator_lifecycle_tracker import track_operator_lifecycle
from refrag_discovery.control_plane.operator_lineage_tracker import track_operator_lineage
from refrag_discovery.control_plane.storage import load_json, save_json, suite_state_path, utc_now_iso
from refrag_discovery.registry import build_default_operator_query


MODE_ADJUSTMENT = {
    "standard": 0.0,
    "stress": -0.08,
    "adversarial": -0.11,
    "full": -0.04,
}

STATE_BASE_SCORE = {
    "experimental": 0.48,
    "candidate": 0.63,
    "stable": 0.82,
    "promoted": 0.91,
    "deprecated": 0.2,
}


def _resource_modifier(resource_budget: dict[str, Any]) -> float:
    max_cost = resource_budget.get("max_cost_usd")
    max_latency_ms = resource_budget.get("max_latency_ms")
    modifier = 0.0
    if isinstance(max_cost, (int, float)) and max_cost < 0.01:
        modifier -= 0.03
    if isinstance(max_latency_ms, (int, float)) and max_latency_ms < 1000:
        modifier -= 0.02
    return modifier


def _clamp_score(value: float) -> float:
    return round(min(1.0, max(0.0, value)), 6)


def _runtime_feedback_scores(runtime_feedback: dict[str, Any] | None) -> dict[str, float]:
    runtime_feedback = dict(runtime_feedback or {})
    return {
        "overall_score": _clamp_score(float(runtime_feedback.get("overall_score", 0.0) or 0.0)),
        "robustness_score": _clamp_score(float(runtime_feedback.get("robustness_score", 0.0) or 0.0)),
        "efficiency_score": _clamp_score(float(runtime_feedback.get("efficiency_score", 0.0) or 0.0)),
        "benchmark_label_score": _clamp_score(float(runtime_feedback.get("benchmark_label_score", 0.0) or 0.0)),
    }


def _operator_report(
    manifest: dict[str, Any],
    *,
    lifecycle_state: str,
    task_suite_id: str,
    benchmark_mode: str,
    resource_budget: dict[str, Any],
    generate_adversarial_tasks: bool,
    runtime_feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    complexity = (
        len(manifest.get("inputs", []))
        + len(manifest.get("outputs", []))
        + len(manifest.get("dependencies", []))
        + len(manifest.get("capabilities", []))
    )
    determinism_bonus = 0.03 if manifest.get("constraints", {}).get("deterministic") else -0.01
    execution_bonus = 0.02 if manifest.get("execution_class") == "runtime" else 0.0
    template_penalty = -0.02 if manifest.get("operator_type") == "template" else 0.0
    complexity_penalty = 0.008 * max(0, complexity - 8)
    base_score = STATE_BASE_SCORE[lifecycle_state]
    overall_score = _clamp_score(
        base_score
        + determinism_bonus
        + execution_bonus
        + template_penalty
        + MODE_ADJUSTMENT.get(benchmark_mode, MODE_ADJUSTMENT["full"])
        + _resource_modifier(resource_budget)
        - complexity_penalty
    )
    robustness_score = _clamp_score(overall_score - (0.04 if benchmark_mode in {"stress", "adversarial"} else 0.01))
    efficiency_score = _clamp_score(
        overall_score
        + (0.02 if manifest.get("constraints", {}).get("max_latency_ms", 0) <= 5000 else -0.01)
    )
    runtime_scores = _runtime_feedback_scores(runtime_feedback)
    if any(runtime_scores.values()):
        overall_score = _clamp_score((overall_score * 0.25) + (runtime_scores["overall_score"] * 0.75))
        robustness_score = _clamp_score(
            (robustness_score * 0.45) + (runtime_scores["robustness_score"] * 0.55)
        )
        efficiency_score = _clamp_score(
            (efficiency_score * 0.45) + (runtime_scores["efficiency_score"] * 0.55)
        )
        if runtime_scores["benchmark_label_score"] > 0.0:
            overall_score = _clamp_score((overall_score * 0.75) + (runtime_scores["benchmark_label_score"] * 0.25))
            robustness_score = _clamp_score(
                (robustness_score * 0.8) + (runtime_scores["benchmark_label_score"] * 0.2)
            )

    report = {
        "operator_id": str(manifest["operator_id"]),
        "version": str(manifest.get("lineage", {}).get("version", "unknown")),
        "task_suite_id": task_suite_id,
        "benchmark_mode": benchmark_mode,
        "lifecycle_state": lifecycle_state,
        "metrics": {
            "overall_score": overall_score,
            "robustness_score": robustness_score,
            "efficiency_score": efficiency_score,
            "complexity_score": round(complexity, 4),
        },
        "constraints_observed": {
            "deterministic": bool(manifest.get("constraints", {}).get("deterministic", False)),
            "max_latency_ms": manifest.get("constraints", {}).get("max_latency_ms"),
            "max_cost_usd": manifest.get("constraints", {}).get("max_cost_usd"),
        },
    }
    if runtime_feedback:
        report["runtime_feedback"] = {
            "selected_mode": runtime_feedback.get("selected_mode"),
            "reward_signal": runtime_feedback.get("reward_signal"),
            "selection_count": int(runtime_feedback.get("selection_count", 0) or 0),
            "reward_trend": round(float(runtime_feedback.get("reward_trend", 0.0) or 0.0), 6),
            "query_mode_best_modes": dict(runtime_feedback.get("query_mode_best_modes", {})),
            "mode_metrics": dict(runtime_feedback.get("mode_metrics", {})),
            "benchmark_label_score": round(float(runtime_feedback.get("benchmark_label_score", 0.0) or 0.0), 6),
            "benchmark_labels": dict(runtime_feedback.get("benchmark_labels", {})),
            "underperforming_labels": list(runtime_feedback.get("underperforming_labels", [])),
            "underperforming_label_details": list(runtime_feedback.get("underperforming_label_details", [])),
        }
    if generate_adversarial_tasks:
        report["weakness_profile"] = {
            "surface_area": "high" if complexity >= 12 else "moderate" if complexity >= 8 else "low",
            "highest_risk": "maturity" if lifecycle_state in {"experimental", "candidate"} else "complexity",
        }
    return report


def benchmark_operators(
    *,
    operator_ids: list[str] | None = None,
    task_suite_id: str = "standard_v1",
    benchmark_mode: str = "full",
    resource_budget: dict[str, Any] | None = None,
    generate_adversarial_tasks: bool = True,
    external_metrics_by_operator: dict[str, dict[str, Any]] | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    query = build_default_operator_query()
    resource_budget = dict(resource_budget or {})
    external_metrics_by_operator = {
        str(operator_id): dict(metrics)
        for operator_id, metrics in dict(external_metrics_by_operator or {}).items()
    }

    manifests = (
        [query.get_manifest(operator_id) for operator_id in operator_ids]
        if operator_ids
        else query.list_manifests()
    )
    suite_path = suite_state_path("benchmarks", task_suite_id, artifacts_dir)
    state = load_json(
        suite_path,
        {
            "task_suite_id": task_suite_id,
            "runs": [],
        },
    )
    previous_reports = {}
    if state.get("runs"):
        previous_reports = {
            item["operator_id"]: item
            for item in state["runs"][-1].get("per_operator_reports", [])
        }

    per_operator_reports: list[dict[str, Any]] = []
    regressions_detected: list[dict[str, Any]] = []
    adversarial_findings: list[dict[str, Any]] = []
    predictions: dict[str, dict[str, Any]] = {}

    for manifest in manifests:
        operator_id = str(manifest["operator_id"])
        lifecycle = track_operator_lifecycle(operator_id=operator_id, artifacts_dir=artifacts_dir)
        report = _operator_report(
            manifest,
            lifecycle_state=lifecycle["current_state"],
            task_suite_id=task_suite_id,
            benchmark_mode=benchmark_mode,
            resource_budget=resource_budget,
            generate_adversarial_tasks=generate_adversarial_tasks,
            runtime_feedback=external_metrics_by_operator.get(operator_id),
        )
        per_operator_reports.append(report)

        previous = previous_reports.get(operator_id)
        if previous is not None:
            previous_score = float(previous["metrics"]["overall_score"])
            current_score = float(report["metrics"]["overall_score"])
            if current_score < previous_score:
                regressions_detected.append(
                    {
                        "operator_id": operator_id,
                        "previous_score": round(previous_score, 6),
                        "current_score": round(current_score, 6),
                        "delta": round(current_score - previous_score, 6),
                    }
                )

        if generate_adversarial_tasks:
            adversarial_findings.append(
                {
                    "operator_id": operator_id,
                    "weakness_profile": report.get("weakness_profile", {}),
                    "recommended_focus": "stabilize interfaces"
                    if report.get("weakness_profile", {}).get("surface_area") == "high"
                    else "increase maturity coverage",
                }
            )

        predictions[operator_id] = {
            "predicted_unseen_task_score": _clamp_score(
                report["metrics"]["overall_score"] - (0.02 if manifest.get("operator_type") == "template" else 0.01)
            ),
            "prediction_confidence": 0.62,
        }

        track_operator_lineage(
            operator_id=operator_id,
            version=str(manifest.get("lineage", {}).get("version", "0.0.0")),
            schema_snapshot=manifest,
            performance_benchmark={
                "summary": report["metrics"],
                "task_suite_id": task_suite_id,
                "benchmark_mode": benchmark_mode,
            },
            artifacts_dir=artifacts_dir,
        )

    per_operator_reports.sort(
        key=lambda item: (float(item["metrics"]["overall_score"]), item["operator_id"]),
        reverse=True,
    )
    leaderboard = {
        "task_suite_id": task_suite_id,
        "benchmark_mode": benchmark_mode,
        "rankings": [
            {
                "rank": index + 1,
                "operator_id": report["operator_id"],
                "overall_score": report["metrics"]["overall_score"],
                "lifecycle_state": report["lifecycle_state"],
            }
            for index, report in enumerate(per_operator_reports)
        ],
        "pareto_frontier": [
            report["operator_id"]
            for report in per_operator_reports
            if report["metrics"]["overall_score"] >= per_operator_reports[0]["metrics"]["overall_score"] - 0.03
        ]
        if per_operator_reports
        else [],
    }

    state["runs"].append(
        {
            "recorded_at": utc_now_iso(),
            "task_suite_id": task_suite_id,
            "benchmark_mode": benchmark_mode,
            "external_metrics_by_operator": external_metrics_by_operator,
            "per_operator_reports": per_operator_reports,
        }
    )
    save_json(suite_path, state)

    return with_production_readiness(
        "operator_benchmark_suite",
        {
            "leaderboard": leaderboard,
            "per_operator_reports": per_operator_reports,
            "regressions_detected": regressions_detected,
            "adversarial_findings": adversarial_findings,
            "gp_performance_predictions": {
                "model": "heuristic_proxy",
                "predictions": predictions,
            },
        },
    )
