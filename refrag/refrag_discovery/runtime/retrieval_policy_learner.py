from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from refrag_discovery.paths import ARTIFACTS_DIR


def _softmax(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    peak = max(scores.values())
    weights = {key: math.exp(value - peak) for key, value in scores.items()}
    total = sum(weights.values()) or 1.0
    return {key: round(value / total, 4) for key, value in weights.items()}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def reward_component_weights(reward_signal: str = "composite") -> dict[str, float]:
    presets = {
        "composite": {
            "quality": 0.38,
            "evidence": 0.18,
            "consistency": 0.16,
            "coverage": 0.12,
            "efficiency": 0.10,
            "calibration": 0.06,
        },
        "quality_first": {
            "quality": 0.50,
            "evidence": 0.16,
            "consistency": 0.14,
            "coverage": 0.08,
            "efficiency": 0.06,
            "calibration": 0.06,
        },
        "latency_first": {
            "quality": 0.26,
            "evidence": 0.16,
            "consistency": 0.14,
            "coverage": 0.08,
            "efficiency": 0.28,
            "calibration": 0.08,
        },
    }
    return dict(presets.get(reward_signal, presets["composite"]))


def _load_artifact_policy_state(
    artifact_root: Path,
    available_modes: list[str],
) -> tuple[dict[str, float], dict[str, int], dict[str, float], int, dict[str, Any]]:
    history_path = artifact_root / "policy_history.jsonl"
    benchmark_path = artifact_root / "retrieval_policy_benchmark.json"
    history_records = _load_jsonl(history_path)
    mode_rewards: dict[str, list[float]] = {mode: [] for mode in available_modes}
    mode_history: dict[str, int] = {mode: 0 for mode in available_modes}
    benchmark_signals: dict[str, float] = {}

    for record in history_records:
        selected_mode = str(record.get("selected_mode", ""))
        if selected_mode not in mode_history:
            continue
        mode_history[selected_mode] += 1
        reward = float(record.get("reward", 0.0) or 0.0)
        mode_rewards[selected_mode].append(reward)

    historical_mode_rewards = {
        mode: round(_average(rewards), 6)
        for mode, rewards in mode_rewards.items()
        if rewards
    }

    benchmark_report = _load_json(benchmark_path)
    for mode, metrics in dict(benchmark_report.get("mode_metrics", {})).items():
        if mode not in mode_history or not isinstance(metrics, dict):
            continue
        benchmark_signals[mode] = round(float(metrics.get("avg_reward", 0.0) or 0.0), 6)
        if not mode_history[mode]:
            mode_history[mode] = int(metrics.get("selection_count", 0) or 0)

    return historical_mode_rewards, mode_history, benchmark_signals, len(history_records), benchmark_report


def _merge_float_maps(base: dict[str, float], overlay: dict[str, float]) -> dict[str, float]:
    merged = {str(key): float(value) for key, value in base.items()}
    for key, value in overlay.items():
        name = str(key)
        candidate = float(value)
        if name in merged:
            merged[name] = round((merged[name] + candidate) / 2.0, 6)
        else:
            merged[name] = candidate
    return merged


def _merge_int_maps(base: dict[str, int], overlay: dict[str, int]) -> dict[str, int]:
    merged = {str(key): int(value) for key, value in base.items()}
    for key, value in overlay.items():
        name = str(key)
        merged[name] = merged.get(name, 0) + int(value)
    return merged


def _load_control_loop_state(artifact_root: Path) -> dict[str, Any]:
    return _load_json(artifact_root / "retrieval_policy_control_loop.json")


def _control_loop_context(control_loop_report: dict[str, Any], query_mode: str) -> dict[str, Any]:
    state = dict(control_loop_report.get("control_loop_state", control_loop_report))
    query_mode_overrides = {
        str(observed_query_mode): str(preferred_mode)
        for observed_query_mode, preferred_mode in dict(state.get("query_mode_overrides", {})).items()
        if str(preferred_mode).strip()
    }
    preferred_mode = str(query_mode_overrides.get(query_mode) or state.get("preferred_mode", "")).strip()
    return {
        "preferred_mode": preferred_mode,
        "global_preferred_mode": str(state.get("preferred_mode", "")).strip(),
        "query_mode_overrides": query_mode_overrides,
        "recommended_policy_mode": str(state.get("recommended_policy_mode", "")).strip(),
        "recommended_reward_signal": str(state.get("recommended_reward_signal", "")).strip(),
        "confidence": round(_clamp(float(state.get("confidence", 0.0) or 0.0)), 6),
        "underexplored_modes": [
            str(mode)
            for mode in list(state.get("underexplored_modes", []))
            if str(mode).strip()
        ],
        "negative_trend_modes": [
            str(mode)
            for mode in list(state.get("negative_trend_modes", []))
            if str(mode).strip()
        ],
        "policy_gap_targets": [
            str(target)
            for target in list(state.get("policy_gap_targets", []))
            if str(target).strip()
        ],
        "strong_labels": [
            str(label)
            for label in list(state.get("strong_labels", []))
            if str(label).strip()
        ],
        "underperforming_labels": [
            str(label)
            for label in list(state.get("underperforming_labels", []))
            if str(label).strip()
        ],
    }


def _mode_feature_vector(
    mode: str,
    *,
    query_mode: str,
    chunk_count: int,
    avg_uncertainty: float,
) -> list[float]:
    chunk_scale = min(1.0, chunk_count / 128.0)
    if mode == "candidate_similarity":
        return [
            1.0 if query_mode == "from_candidate" else 0.2,
            max(0.0, 1.0 - avg_uncertainty),
            max(0.2, 1.0 - chunk_scale),
        ]
    if mode == "spectral_target":
        return [
            1.0 if query_mode == "from_spectral_target" else 0.2,
            min(1.0, avg_uncertainty + 0.2),
            0.4 + (chunk_scale / 3.0),
        ]
    if mode == "hybrid":
        return [
            0.8,
            0.5 + min(0.4, avg_uncertainty),
            0.6 + (chunk_scale / 2.0),
        ]
    return [0.3, 0.3, 0.3]


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _metric_component_scores(metrics: dict[str, Any]) -> dict[str, float]:
    raw_components = dict(metrics.get("avg_component_scores", {}))
    if raw_components:
        return {
            "quality": float(raw_components.get("quality", metrics.get("avg_probability_valid", 0.0)) or 0.0),
            "evidence": float(raw_components.get("evidence", metrics.get("avg_evidence_density", 0.0)) or 0.0),
            "consistency": float(raw_components.get("consistency", metrics.get("avg_support_ratio", 0.0)) or 0.0),
            "coverage": float(raw_components.get("coverage", metrics.get("avg_graph_coverage", 0.0)) or 0.0),
            "efficiency": float(
                raw_components.get(
                    "efficiency",
                    max(0.0, 1.0 - float(metrics.get("avg_pipeline_latency_s", 0.0) or 0.0)),
                )
                or 0.0
            ),
            "calibration": float(
                raw_components.get("calibration", metrics.get("avg_confidence_alignment", 0.0)) or 0.0
            ),
        }
    return {
        "quality": float(metrics.get("avg_probability_valid", 0.0) or 0.0),
        "evidence": float(metrics.get("avg_evidence_density", 0.0) or 0.0),
        "consistency": float(metrics.get("avg_support_ratio", 0.0) or 0.0),
        "coverage": float(metrics.get("avg_graph_coverage", 0.0) or 0.0),
        "efficiency": max(0.0, 1.0 - float(metrics.get("avg_pipeline_latency_s", 0.0) or 0.0)),
        "calibration": float(metrics.get("avg_confidence_alignment", 0.0) or 0.0),
    }


def _profile_from_metrics(metrics: dict[str, Any], component_weights: dict[str, float]) -> dict[str, Any]:
    if not metrics:
        return {
            "selection_count": 0,
            "avg_reward": 0.0,
            "avg_recent_reward": 0.0,
            "reward_trend": 0.0,
            "reliability": 0.0,
            "component_alignment": 0.0,
            "score": 0.0,
            "components": _metric_component_scores({}),
        }

    selection_count = int(metrics.get("selection_count", 0) or 0)
    avg_reward = float(metrics.get("avg_reward", 0.0) or 0.0)
    avg_recent_reward = float(metrics.get("avg_recent_reward", avg_reward) or avg_reward)
    reward_trend = float(metrics.get("reward_trend", 0.0) or 0.0)
    reliability = _clamp(selection_count / 5.0)
    components = _metric_component_scores(metrics)
    component_alignment = sum(
        float(component_weights.get(name, 0.0) or 0.0) * float(components.get(name, 0.0) or 0.0)
        for name in component_weights
    )
    score = (
        (avg_reward * 0.45)
        + (avg_recent_reward * 0.25)
        + (component_alignment * 0.20)
        + (_clamp(reward_trend, -0.25, 0.25) * 0.40)
    )
    score *= 0.35 + (0.65 * reliability)
    return {
        "selection_count": selection_count,
        "avg_reward": round(avg_reward, 6),
        "avg_recent_reward": round(avg_recent_reward, 6),
        "reward_trend": round(reward_trend, 6),
        "reliability": round(reliability, 6),
        "component_alignment": round(component_alignment, 6),
        "score": round(score, 6),
        "components": {name: round(float(value), 6) for name, value in components.items()},
    }


def _benchmark_profile(
    *,
    mode: str,
    query_mode: str,
    benchmark_report: dict[str, Any],
    component_weights: dict[str, float],
) -> dict[str, Any]:
    mode_metrics = dict(benchmark_report.get("mode_metrics", {})).get(mode, {})
    query_mode_metrics = dict(benchmark_report.get("query_mode_metrics", {})).get(query_mode, {})
    contextual_metrics = dict(query_mode_metrics.get("mode_metrics", {})).get(mode, {})
    global_profile = _profile_from_metrics(mode_metrics, component_weights)
    contextual_profile = _profile_from_metrics(contextual_metrics, component_weights)
    return {
        "selection_count": global_profile["selection_count"],
        "global_score": global_profile["score"],
        "contextual_score": contextual_profile["score"],
        "global_reliability": global_profile["reliability"],
        "contextual_reliability": contextual_profile["reliability"],
        "component_alignment": global_profile["component_alignment"],
        "contextual_component_alignment": contextual_profile["component_alignment"],
        "avg_reward": global_profile["avg_reward"],
        "avg_recent_reward": global_profile["avg_recent_reward"],
        "reward_trend": global_profile["reward_trend"],
        "query_mode_avg_reward": contextual_profile["avg_reward"],
        "query_mode_recent_reward": contextual_profile["avg_recent_reward"],
        "components": global_profile["components"],
        "query_mode_components": contextual_profile["components"],
    }


def execute(
    *,
    task_features: dict,
    available_modes: list[str],
    reward_signal: str = "composite",
    policy_mode: str = "ppo",
    artifacts_dir: Path | None = None,
) -> dict:
    if not available_modes:
        raise ValueError("available_modes must contain at least one retrieval mode")

    query_mode = str(task_features.get("query_mode", "from_spectral_target"))
    chunk_count = int(task_features.get("chunk_count", 0))
    avg_uncertainty = float(task_features.get("avg_uncertainty", 0.0))
    historical_mode_rewards = {
        str(key): float(value)
        for key, value in dict(task_features.get("historical_mode_rewards", {})).items()
    }
    mode_history = {
        str(key): int(value)
        for key, value in dict(task_features.get("mode_history", {})).items()
    }
    benchmark_signals = {
        str(key): float(value)
        for key, value in dict(task_features.get("benchmark_signals", {})).items()
    }

    artifact_root = Path(artifacts_dir or task_features.get("artifacts_dir") or ARTIFACTS_DIR)
    (
        artifact_mode_rewards,
        artifact_mode_history,
        artifact_benchmark_signals,
        artifact_history_count,
        benchmark_report,
    ) = _load_artifact_policy_state(artifact_root, available_modes)
    historical_mode_rewards = _merge_float_maps(artifact_mode_rewards, historical_mode_rewards)
    mode_history = _merge_int_maps(artifact_mode_history, mode_history)
    benchmark_signals = _merge_float_maps(artifact_benchmark_signals, benchmark_signals)
    control_loop_report = _load_control_loop_state(artifact_root)
    control_loop_state = _control_loop_context(control_loop_report, query_mode)

    policy_report = _load_json(artifact_root / "policy_ppo_report.json")
    training_report = _load_json(artifact_root / "training_report.json")
    training_summary = dict(training_report.get("summary", {}))
    health_score = float(training_summary.get("health_score", 0.0) or 0.0)
    policy_weights = [float(value) for value in policy_report.get("weights", [])]
    ppo_gain = float(policy_report.get("final_relevant_prob", 0.0) or 0.0) - float(
        policy_report.get("initial_relevant_prob", 0.0) or 0.0
    )
    policy_avg_reward = float(policy_report.get("avg_reward", 0.0) or 0.0)
    benchmark_summary = dict(benchmark_report.get("summary", {}))
    benchmark_selection_count = max(
        artifact_history_count,
        int(benchmark_summary.get("selection_count", 0) or 0),
    )
    benchmark_ready = bool(benchmark_report) and benchmark_selection_count >= 2
    control_loop_confidence = float(control_loop_state["confidence"])
    ppo_evidence = _clamp((max(0.0, policy_avg_reward) * 0.7) + (max(0.0, ppo_gain) * 2.0))
    benchmark_support = _clamp(
        (float(benchmark_summary.get("avg_reward", 0.0) or 0.0) * 0.6)
        + min(0.4, benchmark_selection_count / 5.0)
    )
    ppo_support = round(
        (health_score * 0.45)
        + (ppo_evidence * 0.35)
        + (benchmark_support * 0.15)
        + (control_loop_confidence * 0.05),
        6,
    )
    ppo_ready = (
        len(policy_weights) >= 3
        and health_score >= 0.55
        and ppo_support >= 0.62
        and (policy_avg_reward > 0.0 or ppo_gain > 0.0)
    )
    requested_policy_mode = policy_mode
    effective_policy_mode = requested_policy_mode
    fallback_reason = ""
    if requested_policy_mode in {"ppo", "ppo_with_curiosity"} and not ppo_ready:
        effective_policy_mode = "contextual_bandit"
        fallback_reason = "ppo_support_insufficient"
    use_ppo_scores = ppo_ready and effective_policy_mode in {"ppo", "ppo_with_curiosity"}
    component_weights = reward_component_weights(reward_signal)

    raw_scores: dict[str, float] = {}
    learned_scores: dict[str, float] = {}
    curiosity_bonus: dict[str, float] = {}
    control_loop_bonus: dict[str, float] = {}
    benchmark_mode_profiles: dict[str, dict[str, Any]] = {}
    contextual_benchmark_signals: dict[str, float] = {}
    preferred_mode = control_loop_state["preferred_mode"]
    global_preferred_mode = control_loop_state["global_preferred_mode"]
    underexplored_modes = set(control_loop_state["underexplored_modes"])
    negative_trend_modes = set(control_loop_state["negative_trend_modes"])
    for mode in available_modes:
        score = 0.2
        if mode == "candidate_similarity":
            score += 0.5 if query_mode == "from_candidate" else 0.1
        elif mode == "spectral_target":
            score += 0.5 if query_mode == "from_spectral_target" else 0.1
        elif mode == "hybrid":
            score += 0.25 + min(0.25, chunk_count / 100.0) + (avg_uncertainty * 0.2)
        else:
            score += 0.1

        history_bonus = historical_mode_rewards.get(mode, 0.0) * 0.18
        profile = _benchmark_profile(
            mode=mode,
            query_mode=query_mode,
            benchmark_report=benchmark_report,
            component_weights=component_weights,
        )
        benchmark_mode_profiles[mode] = profile
        contextual_benchmark_signals[mode] = round(float(profile["contextual_score"]), 6)

        benchmark_bonus = (
            (benchmark_signals.get(mode, 0.0) * 0.10)
            + (float(profile["global_score"]) * 0.24)
            + (float(profile["contextual_score"]) * 0.28)
            + (float(profile["component_alignment"]) * 0.08)
        )
        benchmark_bonus += max(-0.03, min(0.06, float(profile["reward_trend"]) * 0.25))
        if not benchmark_signals and not benchmark_report:
            if mode == "hybrid":
                benchmark_bonus = health_score * 0.10
            elif mode == "spectral_target":
                benchmark_bonus = health_score * 0.06
            else:
                benchmark_bonus = health_score * 0.04

        learned_score = 0.0
        if use_ppo_scores and policy_weights:
            learned_score = _dot(
                _mode_feature_vector(
                    mode,
                    query_mode=query_mode,
                    chunk_count=chunk_count,
                    avg_uncertainty=avg_uncertainty,
                ),
                policy_weights[:3],
            )
            learned_score *= max(0.0, policy_avg_reward + ppo_gain)
        learned_scores[mode] = round(learned_score, 6)

        mode_count = mode_history.get(mode, 0)
        bonus = 0.0
        if effective_policy_mode in {"contextual_bandit", "ppo_with_curiosity"}:
            bonus = max(0.0, 0.12 - min(0.1, mode_count * 0.02))
            if effective_policy_mode == "ppo_with_curiosity":
                bonus += max(0.0, avg_uncertainty * 0.08)
            if not int(profile["selection_count"]):
                bonus += 0.015
        curiosity_bonus[mode] = round(bonus, 6)
        mode_control_loop_bonus = 0.0
        if control_loop_confidence:
            if preferred_mode and mode == preferred_mode:
                mode_control_loop_bonus += 0.24 * control_loop_confidence
            elif global_preferred_mode and mode == global_preferred_mode:
                mode_control_loop_bonus += 0.12 * control_loop_confidence
            if mode in underexplored_modes and effective_policy_mode in {
                "contextual_bandit",
                "ppo_with_curiosity",
            }:
                mode_control_loop_bonus += 0.05 + (0.06 * control_loop_confidence)
            if mode in negative_trend_modes:
                mode_control_loop_bonus -= 0.10 + (0.08 * control_loop_confidence)
        control_loop_bonus[mode] = round(mode_control_loop_bonus, 6)
        raw_scores[mode] = (
            score
            + history_bonus
            + benchmark_bonus
            + learned_score
            + bonus
            + mode_control_loop_bonus
        )

    action_probabilities = _softmax(raw_scores)
    selected_mode = max(action_probabilities, key=action_probabilities.get)
    policy_confidence = action_probabilities[selected_mode]
    selected_score = raw_scores[selected_mode]
    value_estimate = round(
        max(0.0, selected_score)
        * (1.0 - avg_uncertainty / 2.0)
        * (0.7 + (float(benchmark_mode_profiles[selected_mode]["global_reliability"]) * 0.3)),
        4,
    )
    policy_source = "heuristic"
    if control_loop_report:
        policy_source = "control_loop_backed"
    elif use_ppo_scores and (benchmark_report or artifact_history_count or health_score):
        policy_source = "artifact_backed"
    elif use_ppo_scores:
        policy_source = "ppo_artifact"
    elif historical_mode_rewards or benchmark_signals or artifact_history_count or benchmark_report:
        policy_source = "history_backed"

    return {
        "selected_mode": selected_mode,
        "policy_confidence": policy_confidence,
        "action_probabilities": action_probabilities,
        "value_estimate": value_estimate,
        "metadata": {
            "reward_signal": reward_signal,
            "reward_component_weights": component_weights,
            "policy_mode": requested_policy_mode,
            "effective_policy_mode": effective_policy_mode,
            "policy_source": policy_source,
            "learned_scores": learned_scores,
            "curiosity_bonus": curiosity_bonus,
            "control_loop_bonus": control_loop_bonus,
            "health_score": round(health_score, 6),
            "artifact_root": str(artifact_root),
            "artifact_history_count": artifact_history_count,
            "effective_historical_mode_rewards": historical_mode_rewards,
            "effective_benchmark_signals": benchmark_signals,
            "effective_mode_history": mode_history,
            "benchmark_mode_profiles": benchmark_mode_profiles,
            "contextual_benchmark_signals": contextual_benchmark_signals,
            "policy_readiness": {
                "requested_policy_mode": requested_policy_mode,
                "effective_policy_mode": effective_policy_mode,
                "ppo_ready": ppo_ready,
                "benchmark_ready": benchmark_ready,
                "control_loop_state_loaded": bool(control_loop_report),
                "control_loop_confidence": round(control_loop_confidence, 6),
                "fallback_reason": fallback_reason,
                "ppo_support": ppo_support,
            },
            "control_loop_state": control_loop_state,
        },
    }
