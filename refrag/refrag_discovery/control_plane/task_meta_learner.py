from __future__ import annotations

from pathlib import Path
from typing import Any

from refrag_discovery.control_plane.production_readiness import with_production_readiness
from refrag_discovery.control_plane.storage import load_json, save_json, suite_state_path, utc_now_iso


VALID_QUERY_MODES = {
    "recommend_config",
    "classify_task",
    "predict_performance",
    "update_from_outcome",
    "explore_task_space",
}


def _classify_task(task_description: str, task_features: dict[str, Any]) -> dict[str, Any]:
    domain = str(task_features.get("domain", "unknown")).strip().lower() or "unknown"
    data_type = str(task_features.get("data_type", "unknown")).strip().lower() or "unknown"
    size = float(task_features.get("size", 0.0) or 0.0)
    noise = float(task_features.get("noise", 0.0) or 0.0)

    scale = "small"
    if size >= 1000:
        scale = "large"
    elif size >= 100:
        scale = "medium"

    noise_band = "low" if noise < 0.1 else "moderate" if noise < 0.35 else "high"
    taxonomy_id = f"{domain}:{data_type}:{scale}:{noise_band}"
    return {
        "taxonomy_id": taxonomy_id,
        "domain": domain,
        "data_type": data_type,
        "scale": scale,
        "noise_band": noise_band,
        "label": f"{domain} {data_type} {scale} {noise_band}",
        "matched_on": {
            "task_description": task_description,
            "task_features": dict(task_features),
        },
    }


def _recommended_configuration(classification: dict[str, Any], task_features: dict[str, Any], history_size: int) -> dict[str, Any]:
    scale = classification["scale"]
    noise_band = classification["noise_band"]
    recommended_top_k = 4 if scale == "small" else 6 if scale == "medium" else 8
    expand_budget = 2 if noise_band == "high" else 3 if scale == "medium" else 4
    window_size = 96 if scale == "small" else 128 if scale == "medium" else 192
    confidence = 0.58 + min(0.25, history_size * 0.03)

    return {
        "spectral_chunker": {
            "window_size": window_size,
            "stride": max(32, window_size // 2),
        },
        "operator_query": {
            "top_k": recommended_top_k,
        },
        "pipeline": {
            "expand_budget": expand_budget,
        },
        "confidence": round(min(0.9, confidence), 4),
        "adaptation_source": "observed_history" if history_size else "heuristic_bootstrap",
        "task_features": dict(task_features),
    }


def _performance_prediction(configuration: dict[str, Any], classification: dict[str, Any]) -> dict[str, Any]:
    base_accuracy = 0.72
    if classification["noise_band"] == "high":
        base_accuracy -= 0.08
    if classification["scale"] == "large":
        base_accuracy += 0.04
    confidence = float(configuration["confidence"])
    return {
        "expected_accuracy": round(base_accuracy, 4),
        "confidence_interval": [round(max(0.0, base_accuracy - 0.08), 4), round(min(1.0, base_accuracy + 0.08), 4)],
        "confidence": round(confidence, 4),
    }


def _task_space_analysis(state: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    label_stats: dict[str, dict[str, Any]] = {}
    for item in state.get("observations", []):
        taxonomy_id = str(item.get("taxonomy_id", "unknown"))
        counts[taxonomy_id] = counts.get(taxonomy_id, 0) + 1
        task_outcome = dict(item.get("task_outcome", {}))
        benchmark_labels = {
            str(label): dict(metrics)
            for label, metrics in dict(task_outcome.get("benchmark_labels", {})).items()
        }
        for label, metrics in benchmark_labels.items():
            stats = label_stats.setdefault(
                label,
                {
                    "observations": 0,
                    "scores": [],
                    "pass_rates": [],
                },
            )
            stats["observations"] += 1
            stats["scores"].append(float(metrics.get("avg_benchmark_label_score", task_outcome.get("benchmark_label_score", 0.0)) or 0.0))
            stats["pass_rates"].append(float(metrics.get("pass_rate", 1.0) or 1.0))

    underexplored = [
        {"taxonomy_id": taxonomy_id, "count": count}
        for taxonomy_id, count in sorted(counts.items())
        if count < 2
    ]
    benchmark_label_priors = {
        label: {
            "observations": int(stats["observations"]),
            "avg_benchmark_label_score": round(
                sum(stats["scores"]) / max(1, len(stats["scores"])),
                6,
            ),
            "avg_pass_rate": round(
                sum(stats["pass_rates"]) / max(1, len(stats["pass_rates"])),
                6,
            ),
        }
        for label, stats in sorted(label_stats.items())
    }
    underexplored_labels = [
        {"label": label, "count": int(stats["observations"])}
        for label, stats in sorted(benchmark_label_priors.items())
        if int(stats["observations"]) < 2
    ]
    return {
        "taxonomy_counts": counts,
        "underexplored_regions": underexplored,
        "observation_count": len(state.get("observations", [])),
        "benchmark_label_priors": benchmark_label_priors,
        "underexplored_labels": underexplored_labels,
    }


def run_task_meta_learner(
    *,
    task_description: str,
    task_features: dict[str, Any],
    query_mode: str = "recommend_config",
    task_outcome: dict[str, Any] | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    if query_mode not in VALID_QUERY_MODES:
        raise ValueError(f"Unsupported query_mode: {query_mode}")

    state_path = suite_state_path("meta_learner", "task_meta_learner", artifacts_dir)
    state = load_json(state_path, {"observations": []})

    classification = _classify_task(task_description, task_features)
    history = [item for item in state["observations"] if item.get("taxonomy_id") == classification["taxonomy_id"]]
    configuration = _recommended_configuration(classification, task_features, len(history))
    prediction = _performance_prediction(configuration, classification)
    analysis = _task_space_analysis(state)

    if query_mode == "update_from_outcome":
        state["observations"].append(
            {
                "recorded_at": utc_now_iso(),
                "task_description": task_description,
                "task_features": dict(task_features),
                "taxonomy_id": classification["taxonomy_id"],
                "task_outcome": dict(task_outcome or {}),
            }
        )
        save_json(state_path, state)
        analysis = _task_space_analysis(state)
        configuration["adaptation_source"] = "updated_from_outcome"
        configuration["confidence"] = round(min(0.92, float(configuration["confidence"]) + 0.05), 4)
        prediction = _performance_prediction(configuration, classification)
    elif not state_path.exists():
        save_json(state_path, state)

    return with_production_readiness(
        "task_meta_learner",
        {
            "recommended_configuration": configuration,
            "task_classification": classification,
            "performance_prediction": prediction,
            "task_space_analysis": analysis,
        },
    )
