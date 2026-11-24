"""Exploration policy controller (arch §1.2 control-plane operator).

Per arch Rule 10 the controller owns its own policy knobs: the orchestrator
does not tune. When upstream callers omit ``exploration_budget``, the
controller falls back to ``COLD_START_EXPLORATION_BUDGET`` defined below
rather than inheriting any per-call hardcoded value. The historical
orchestrator override (max_runs=4, compute_fraction=0.35, risk_tolerance=0.55
— arch §1.2 violation) was removed in the Cluster A pass.

State persistence (arch §3): when ``artifacts_dir`` is provided, every plan is
appended to ``<artifacts_dir>/control_plane/exploration/<plan_id>.json`` so
downstream operators (pipeline_performance_optimizer, task_meta_learner) and
post-mortem tooling have a durable, queryable record.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from refrag_discovery.control_plane.production_readiness import with_production_readiness
from refrag_discovery.control_plane.storage import load_json, save_json, suite_state_path, utc_now_iso


# ---------------------------------------------------------------------------
# Cold-start defaults — Rule 10 places these here, NOT in the orchestrator.
# ---------------------------------------------------------------------------
COLD_START_EXPLORATION_BUDGET: dict[str, Any] = {
    "max_runs": 5,
    "compute_fraction": 0.4,
    "risk_tolerance": 0.5,
}

COLD_START_TIME_HORIZON: str = "sprint"

# Persisted-state schema — bump when the on-disk shape changes incompatibly.
STATE_SCHEMA_VERSION: int = 1

# Cap retained run history so the state file does not grow unbounded on
# long-running systems. Older entries are dropped first.
MAX_PERSISTED_RUNS: int = 200


def _priority_bonus(priority: str) -> float:
    return {
        "high": 0.12,
        "medium": 0.06,
        "low": 0.02,
    }.get(str(priority).strip().lower(), 0.06)


def _policy_benchmark_activities(policy_benchmark: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mode_metrics = {
        str(mode): dict(metrics)
        for mode, metrics in dict(policy_benchmark.get("mode_metrics", {})).items()
    }
    query_mode_metrics = {
        str(query_mode): dict(metrics)
        for query_mode, metrics in dict(policy_benchmark.get("query_mode_metrics", {})).items()
    }
    benchmark_labels = {
        str(label): dict(metrics)
        for label, metrics in dict(policy_benchmark.get("benchmark_labels", {})).items()
    }
    reward_model = dict(policy_benchmark.get("reward_model", {}))
    summary = dict(policy_benchmark.get("summary", {}))

    activities: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for mode, metrics in mode_metrics.items():
        selection_count = int(metrics.get("selection_count", 0) or 0)
        reward_trend = float(metrics.get("reward_trend", 0.0) or 0.0)
        if selection_count < 2:
            activities.append(
                {
                    "task": f"benchmark_mode:{mode}",
                    "priority": round(min(1.0, 0.78 + ((2 - selection_count) * 0.06)), 4),
                }
            )
            gaps.append({"target": mode, "severity": round(min(1.0, 0.72 + ((2 - selection_count) * 0.08)), 4)})
        elif reward_trend < 0.0:
            activities.append(
                {
                    "task": f"stabilize_mode:{mode}",
                    "priority": round(min(1.0, 0.7 + abs(reward_trend)), 4),
                }
            )

    for query_mode, metrics in query_mode_metrics.items():
        history_length = int(metrics.get("history_length", 0) or 0)
        if history_length < 2:
            activities.append(
                {
                    "task": f"expand_query_mode:{query_mode}",
                    "priority": round(min(1.0, 0.74 + ((2 - history_length) * 0.07)), 4),
                }
            )
            gaps.append({"target": query_mode, "severity": round(min(1.0, 0.7 + ((2 - history_length) * 0.06)), 4)})

    for label, metrics in benchmark_labels.items():
        label_score = float(metrics.get("avg_benchmark_label_score", 1.0) or 1.0)
        pass_rate = float(metrics.get("pass_rate", 1.0) or 1.0)
        case_count = int(metrics.get("cases", 0) or 0)
        priority = str(metrics.get("learning_priority", "medium"))
        priority_bonus = _priority_bonus(priority)
        action_hint = str(metrics.get("action_hint", ""))
        if case_count < 2:
            activities.append(
                {
                    "task": f"expand_label:{label}",
                    "priority": round(min(1.0, 0.74 + ((2 - case_count) * 0.08) + priority_bonus), 4),
                }
            )
            gap = {"target": label, "severity": round(min(1.0, 0.68 + ((2 - case_count) * 0.08) + priority_bonus), 4)}
            if action_hint:
                gap["action_hint"] = action_hint
            gaps.append(gap)
        if label_score < 0.92 or pass_rate < 1.0:
            severity = round(
                min(1.0, 0.72 + max(0.0, 0.92 - label_score) + max(0.0, 1.0 - pass_rate) + priority_bonus),
                4,
            )
            activities.append(
                {
                    "task": f"stabilize_label:{label}",
                    "priority": severity,
                }
            )
            gap = {"target": label, "severity": severity}
            if action_hint:
                gap["action_hint"] = action_hint
            gaps.append(gap)

    avg_reward = float(summary.get("avg_reward", 0.0) or 0.0)
    if avg_reward < 0.65:
        reward_signal = str(reward_model.get("latest_signal", "composite"))
        activities.insert(
            0,
            {
                "task": f"tune_reward_signal:{reward_signal}",
                "priority": round(min(1.0, 0.8 + max(0.0, 0.65 - avg_reward)), 4),
            },
        )
    return activities, gaps


def _resolve_exploration_budget(
    caller_budget: dict[str, Any] | None,
) -> tuple[dict[str, Any], str]:
    """Pick the budget the controller should plan against.

    Returns ``(resolved_budget, source)`` where ``source`` is one of:

    * ``"caller_supplied"`` — caller passed a non-empty budget. Missing keys
      are backfilled from ``COLD_START_EXPLORATION_BUDGET`` so a partial
      override (e.g. just ``{"max_runs": 3}``) still produces a complete
      budget without resurrecting the orchestrator's old hardcoded values.
    * ``"cold_start_default"`` — caller passed ``None`` or an empty dict.
      The full default budget is used.
    """
    if caller_budget:
        merged = {**COLD_START_EXPLORATION_BUDGET, **dict(caller_budget)}
        return merged, "caller_supplied"
    return dict(COLD_START_EXPLORATION_BUDGET), "cold_start_default"


def _initial_state(plan_id: str) -> dict[str, Any]:
    """Schema for a freshly created on-disk state file."""
    return {
        "state_schema_version": STATE_SCHEMA_VERSION,
        "plan_id": plan_id,
        "runs": [],
    }


def _ensure_state_envelope(state: dict[str, Any], plan_id: str) -> dict[str, Any]:
    """Migrate an existing state dict to the current envelope shape.

    Older state files (pre-schema-versioning) had only ``plan_id`` and
    ``runs``. We add the schema version + leave ``last_updated_at`` to be
    stamped by the writer. Idempotent on already-current state.
    """
    state.setdefault("state_schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("plan_id", plan_id)
    state.setdefault("runs", [])
    return state


def plan_exploration_policy(
    *,
    system_state: dict[str, Any],
    exploration_budget: dict[str, Any] | None = None,
    strategic_priorities: list[str] | None = None,
    time_horizon: str | None = None,
    plan_id: str = "default",
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    resolved_budget, budget_source = _resolve_exploration_budget(exploration_budget)
    resolved_time_horizon = time_horizon if time_horizon is not None else COLD_START_TIME_HORIZON
    strategic_priorities = [str(item).lower() for item in (strategic_priorities or [])]
    pending_tasks = list(system_state.get("pending_tasks", []))
    policy_benchmark = dict(system_state.get("policy_benchmark", {}))
    policy_activities, policy_gaps = _policy_benchmark_activities(policy_benchmark)
    pending_tasks = policy_activities + pending_tasks
    gap_report = dict(system_state.get("gap_report", {}))
    if policy_gaps:
        gap_report = {
            "gaps": policy_gaps + list(gap_report.get("gaps", [])),
        }
    resources = dict(system_state.get("resources", {}))

    max_runs = int(resolved_budget["max_runs"])
    compute_fraction = float(resolved_budget["compute_fraction"])
    risk_tolerance = float(resolved_budget["risk_tolerance"])

    activities = []
    for task in pending_tasks[:max_runs]:
        task_name = str(task.get("task", task))
        priority = float(task.get("priority", 0.5))
        if any(priority_term in task_name.lower() for priority_term in strategic_priorities):
            priority += 0.15
        activities.append(
            {
                "activity": task_name,
                "priority": round(min(1.0, priority), 4),
                "allocation": round(compute_fraction / max(1, min(max_runs, len(pending_tasks) or 1)), 4),
            }
        )

    if gap_report.get("gaps"):
        top_gap = gap_report["gaps"][0]
        activities.insert(
            0,
            {
                "activity": f"close_gap:{top_gap['target']}",
                "priority": round(min(1.0, float(top_gap.get("severity", 0.8)) + 0.1), 4),
                "allocation": round(min(1.0, compute_fraction * 0.35), 4),
            },
        )

    portfolio_allocation = {
        "time_horizon": resolved_time_horizon,
        "selected_portfolio": activities[:max_runs],
        "diversification_score": round(min(1.0, 0.45 + (0.1 * len({item['activity'].split(':')[0] for item in activities[:max_runs]})) - (0.15 * max(0.0, risk_tolerance - 0.7))), 4),
        "resources": resources,
    }
    opportunity_cost_analysis = {
        "unexplored_high_value_activities": [item["activity"] for item in activities[max_runs:]],
        "stagnation_risk": round(max(0.0, 0.6 - len(activities[:max_runs]) * 0.05 + (0.1 if not gap_report.get("gaps") else 0.0)), 4),
    }

    result = {
        "exploration_plan": {
            "activities": activities[:max_runs],
            "max_runs": max_runs,
            "compute_fraction": compute_fraction,
            "risk_tolerance": risk_tolerance,
            "budget_source": budget_source,
        },
        "portfolio_allocation": portfolio_allocation,
        "opportunity_cost_analysis": opportunity_cost_analysis,
        "policy_gap_analysis": {
            "generated_from_policy_benchmark": bool(policy_benchmark),
            "policy_gap_count": len(policy_gaps),
            "policy_gap_targets": [gap["target"] for gap in policy_gaps],
        },
    }
    if artifacts_dir is not None:
        state_path = suite_state_path("exploration", plan_id, artifacts_dir)
        state = _ensure_state_envelope(
            load_json(state_path, _initial_state(plan_id)),
            plan_id,
        )
        state["runs"].append(
            {
                "recorded_at": utc_now_iso(),
                "time_horizon": resolved_time_horizon,
                "resolved_budget": resolved_budget,
                "budget_source": budget_source,
                "exploration_plan": result["exploration_plan"],
                "portfolio_allocation": portfolio_allocation,
                "policy_gap_analysis": result["policy_gap_analysis"],
            }
        )
        # Cap retained history — drop oldest entries first.
        if len(state["runs"]) > MAX_PERSISTED_RUNS:
            state["runs"] = state["runs"][-MAX_PERSISTED_RUNS:]
        state["last_updated_at"] = utc_now_iso()
        save_json(state_path, state)
        result["state_path"] = str(state_path)
    return with_production_readiness("exploration_policy_controller", result)
