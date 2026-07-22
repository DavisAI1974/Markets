#!/usr/bin/env python3
"""Chronological G15 discovery -> G16 forward-holdout validation.

The module is deliberately downstream of both outcome scorers. It verifies that
G15-supported lessons were pre-registered before G16 outcomes, associates only
actually-used G16 SHADOW candidate handlers with G16 score improvements, and
emits a conservative post-G16 registry for a new untouched holdout or forward-
live SHADOW test.

G15 and G16 are fixed chronological blocks. Random shuffling is forbidden. G16
becomes scored evidence after this pass and therefore cannot be reused as an
untouched final holdout. Nothing here can change a blind prior, update
``knowledge/ng_brain.json``, or grant execution authority.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

from ng_historical_manifest import G15_DATES
from ng_g16_blind_wall import G16_DATES

SCHEMA = "ng_chronological_validation.v1"
AUTHORITY = "CHRONOLOGICAL_OUTCOME_VALIDATION_ONLY"
POST_G16_REGISTRY_SCHEMA = "ng_post_g16_shadow_candidate_registry.v1"
POST_G16_AUTHORITY = "POST_G16_UNTOUCHED_SHADOW_TEST_ONLY"
EPS = 1e-9


class ChronologicalValidationError(ValueError):
    """Raised when chronological provenance or outcome evidence is invalid."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _require_false(artifact: Mapping[str, Any], fields: tuple[str, ...], *, label: str) -> None:
    for field in fields:
        if artifact.get(field) is not False:
            raise ChronologicalValidationError(f"{label}: {field} must remain false")


def _validate_fingerprint(artifact: Mapping[str, Any], field: str, *, label: str) -> str:
    payload = copy.deepcopy(dict(artifact))
    observed = payload.pop(field, None)
    expected = _fingerprint(payload)
    if not isinstance(observed, str) or observed != expected:
        raise ChronologicalValidationError(f"{label}: {field} mismatch")
    return observed


def _candidate_ids_from_adjudication(adjudication: Mapping[str, Any]) -> list[str]:
    registry = dict(adjudication.get("g16_shadow_registry") or {})
    return sorted(str(row.get("proposal_id") or "") for row in registry.get("candidates") or [])


def validate_g15_adjudication(adjudication: Mapping[str, Any]) -> None:
    if adjudication.get("schema") != "ng_g15_lesson_adjudication.v1":
        raise ChronologicalValidationError("adjudication: schema mismatch")
    if adjudication.get("authority") != "LESSON_ADJUDICATION_ONLY":
        raise ChronologicalValidationError("adjudication: authority mismatch")
    if int(adjudication.get("group") or 0) != 15:
        raise ChronologicalValidationError("adjudication: group must be 15")
    if adjudication.get("actual_outcomes_used") is not True:
        raise ChronologicalValidationError("adjudication: G15 outcome use must be disclosed")
    _require_false(adjudication, ("execution_authority", "may_update_ng_brain"), label="adjudication")

    adjudication_ids: set[str] = set()
    eligible_ids: set[str] = set()
    for row in adjudication.get("adjudications") or []:
        if not isinstance(row, Mapping):
            raise ChronologicalValidationError("adjudication: row must be an object")
        identifier = str(row.get("id") or "")
        if not identifier or identifier in adjudication_ids:
            raise ChronologicalValidationError("adjudication: ids must be unique and non-empty")
        adjudication_ids.add(identifier)
        if row.get("actual_outcomes_used") is not True:
            raise ChronologicalValidationError(f"adjudication:{identifier}: outcome use must be disclosed")
        _require_false(row, ("execution_authority", "may_update_ng_brain"), label=f"adjudication:{identifier}")
        _validate_fingerprint(row, "evidence_fingerprint", label=f"adjudication:{identifier}")
        if bool((row.get("g16_shadow_test") or {}).get("eligible")):
            eligible_ids.add(identifier)

    registry = dict(adjudication.get("g16_shadow_registry") or {})
    if registry.get("schema") != "ng_g16_shadow_lesson_registry.v1":
        raise ChronologicalValidationError("registry: schema mismatch")
    if registry.get("authority") != "G16_PRE_CUTOFF_SHADOW_TEST_ONLY":
        raise ChronologicalValidationError("registry: authority mismatch")
    if int(registry.get("source_group") or 0) != 15 or int(registry.get("target_group") or 0) != 16:
        raise ChronologicalValidationError("registry: must map G15 to G16")
    _require_false(
        registry,
        ("execution_authority", "actual_g16_outcomes_used", "may_update_ng_brain", "may_change_g16_blind_prior"),
        label="registry",
    )
    candidates = list(registry.get("candidates") or [])
    if int(registry.get("candidate_count") or 0) != len(candidates):
        raise ChronologicalValidationError("registry: candidate_count mismatch")
    candidate_ids: set[str] = set()
    for row in candidates:
        if not isinstance(row, Mapping):
            raise ChronologicalValidationError("registry: candidate must be an object")
        identifier = str(row.get("proposal_id") or "")
        if not identifier or identifier in candidate_ids:
            raise ChronologicalValidationError("registry: candidate ids must be unique and non-empty")
        candidate_ids.add(identifier)
        if row.get("pre_registered_before_g16_outcomes") is not True:
            raise ChronologicalValidationError(f"registry:{identifier}: candidate was not pre-registered")
        if not row.get("g15_evidence_fingerprint"):
            raise ChronologicalValidationError(f"registry:{identifier}: G15 evidence fingerprint required")
        _require_false(row, ("may_update_ng_brain", "may_change_g16_blind_prior"), label=f"registry:{identifier}")
    if candidate_ids != eligible_ids:
        raise ChronologicalValidationError("registry: candidates differ from eligible G15 adjudications")
    if bool((registry.get("gate") or {}).get("g16_refinement_authorized")) != bool(candidate_ids):
        raise ChronologicalValidationError("registry: refinement authorization disagrees with candidate set")
    if (registry.get("gate") or {}).get("g16_outcome_access_authorized") is not False:
        raise ChronologicalValidationError("registry: G16 outcome access must remain disabled")
    _validate_fingerprint(registry, "registry_fingerprint", label="registry")
    _validate_fingerprint(adjudication, "artifact_fingerprint", label="adjudication")


def validate_g16_plan(plan: Mapping[str, Any], *, adjudication: Mapping[str, Any]) -> None:
    if plan.get("schema") != "ng_g16_shadow_refinement_plan.v1":
        raise ChronologicalValidationError("plan: schema mismatch")
    if plan.get("authority") != "G16_PRE_CUTOFF_SHADOW_REFINEMENT_PLAN_ONLY":
        raise ChronologicalValidationError("plan: authority mismatch")
    if int(plan.get("group") or 0) != 16:
        raise ChronologicalValidationError("plan: group must be 16")
    _require_false(
        plan,
        ("execution_authority", "actual_g16_outcomes_used", "target_session_tape_used", "may_update_ng_brain", "may_change_g16_blind_prior"),
        label="plan",
    )
    registry = dict(adjudication["g16_shadow_registry"])
    if plan.get("lesson_adjudication_fingerprint") != adjudication.get("artifact_fingerprint"):
        raise ChronologicalValidationError("plan: G15 adjudication fingerprint mismatch")
    if plan.get("lesson_registry_fingerprint") != registry.get("registry_fingerprint"):
        raise ChronologicalValidationError("plan: G15 registry fingerprint mismatch")
    candidate_ids = [str(value) for value in plan.get("candidate_ids") or []]
    if candidate_ids != sorted(set(candidate_ids)):
        raise ChronologicalValidationError("plan: candidate ids must be sorted and unique")
    if candidate_ids != _candidate_ids_from_adjudication(adjudication):
        raise ChronologicalValidationError("plan: candidate set differs from G15 registry")
    if int(plan.get("candidate_count") or 0) != len(candidate_ids):
        raise ChronologicalValidationError("plan: candidate_count mismatch")
    if bool((plan.get("gate") or {}).get("g16_shadow_refinement_authorized")) != bool(candidate_ids):
        raise ChronologicalValidationError("plan: authorization disagrees with candidate set")
    if (plan.get("gate") or {}).get("g16_outcome_access_authorized") is not False:
        raise ChronologicalValidationError("plan: cannot authorize G16 outcome access")

    day_map = plan.get("days") or {}
    if list(day_map) != list(G16_DATES) or int(plan.get("n_days") or 0) != len(G16_DATES):
        raise ChronologicalValidationError("plan: canonical G16 day order required")
    for day in G16_DATES:
        row = dict(day_map[day])
        observed = row.pop("day_plan_fingerprint", None)
        if observed != _fingerprint(row):
            raise ChronologicalValidationError(f"plan:{day}: day fingerprint mismatch")
        if str(row.get("date") or "") != day:
            raise ChronologicalValidationError(f"plan:{day}: date mismatch")
        if list(row.get("allowed_candidate_ids") or []) != candidate_ids:
            raise ChronologicalValidationError(f"plan:{day}: candidate set mismatch")
        _require_false(
            row,
            ("target_session_tape_used", "actual_g16_outcomes_used", "execution_authority", "may_update_ng_brain", "may_change_g16_blind_prior"),
            label=f"plan:{day}",
        )
        if not row.get("decision_cutoff_utc"):
            raise ChronologicalValidationError(f"plan:{day}: decision cutoff required")
    _validate_fingerprint(plan, "plan_fingerprint", label="plan")


def _probability_dict(value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise ChronologicalValidationError("posterior: probability object required")
    result: dict[str, float] = {}
    for label in ("up", "flat", "down"):
        number = _finite(value.get(label))
        if number is None or number < 0:
            raise ChronologicalValidationError("posterior: invalid probability")
        result[label] = float(number)
    total = sum(result.values())
    if total <= 0:
        raise ChronologicalValidationError("posterior: probability mass required")
    return {key: result[key] / total for key in result}


def validate_g16_posterior_stream(stream: Mapping[str, Any], *, plan: Mapping[str, Any]) -> None:
    if stream.get("schema") != "ng_g16_shadow_posterior_stream.v1":
        raise ChronologicalValidationError("posterior stream: schema mismatch")
    if stream.get("authority") != "G16_CAUSAL_SHADOW_POSTERIOR_STREAM_ONLY":
        raise ChronologicalValidationError("posterior stream: authority mismatch")
    if int(stream.get("group") or 0) != 16:
        raise ChronologicalValidationError("posterior stream: group must be 16")
    _require_false(
        stream,
        ("execution_authority", "actual_g16_outcomes_used", "may_update_ng_brain", "may_change_g16_blind_prior"),
        label="posterior stream",
    )
    if stream.get("plan_fingerprint") != plan.get("plan_fingerprint"):
        raise ChronologicalValidationError("posterior stream: plan fingerprint mismatch")
    outputs = list(stream.get("outputs") or [])
    if int(stream.get("n_outputs") or 0) != len(outputs):
        raise ChronologicalValidationError("posterior stream: n_outputs mismatch")
    allowed = set(str(value) for value in plan.get("candidate_ids") or [])
    last_day_index = -1
    last_by_day: dict[str, tuple[float, int]] = {}
    for output in outputs:
        if not isinstance(output, Mapping):
            raise ChronologicalValidationError("posterior stream: output must be an object")
        if output.get("schema") != "ng_g16_shadow_posterior.v1":
            raise ChronologicalValidationError("posterior output: schema mismatch")
        if output.get("authority") != "G16_CAUSAL_SHADOW_POSTERIOR_ONLY":
            raise ChronologicalValidationError("posterior output: authority mismatch")
        _require_false(
            output,
            ("execution_authority", "actual_g16_outcomes_used", "may_update_ng_brain", "may_change_g16_blind_prior"),
            label="posterior output",
        )
        day = str(output.get("session_day") or "")
        if day not in G16_DATES:
            raise ChronologicalValidationError("posterior output: invalid G16 day")
        event_s = _finite(output.get("as_of_event_s"))
        sequence = int(output.get("sequence") or 0)
        if event_s is None or sequence <= 0:
            raise ChronologicalValidationError(f"posterior output:{day}: event time and sequence required")
        day_index = G16_DATES.index(day)
        current = (float(event_s), sequence)
        if day_index < last_day_index or (day in last_by_day and current <= last_by_day[day]):
            raise ChronologicalValidationError("posterior stream: outputs are not chronological")
        last_day_index = day_index
        last_by_day[day] = current
        if (output.get("provenance") or {}).get("plan_fingerprint") != plan.get("plan_fingerprint"):
            raise ChronologicalValidationError(f"posterior output:{day}: plan provenance mismatch")
        requested = set(str(value) for value in output.get("authorized_candidate_ids") or [])
        implemented = set(str(value) for value in output.get("implemented_candidate_ids") or [])
        unhandled = set(str(value) for value in output.get("unhandled_candidate_ids") or [])
        if not requested.issubset(allowed):
            raise ChronologicalValidationError(f"posterior output:{day}: unregistered candidate")
        if implemented | unhandled != requested or implemented & unhandled:
            raise ChronologicalValidationError(f"posterior output:{day}: candidate accounting mismatch")
        for attribution in output.get("attribution") or []:
            identifier = str(attribution.get("candidate_id") or "")
            if identifier not in requested:
                raise ChronologicalValidationError(f"posterior output:{day}: attribution candidate not authorized")
            if not isinstance(attribution.get("used"), bool):
                raise ChronologicalValidationError(f"posterior output:{day}: attribution used flag required")
            if _finite(attribution.get("directional_contribution")) is None:
                raise ChronologicalValidationError(f"posterior output:{day}: contribution must be finite")
        if output.get("status") == "STAND_DOWN":
            if _probability_dict(output.get("posterior")) != _probability_dict(output.get("blind_prior")):
                raise ChronologicalValidationError(f"posterior output:{day}: stand-down changed blind prior")
        _validate_fingerprint(output, "output_fingerprint", label=f"posterior output:{day}:{sequence}")
    _validate_fingerprint(stream, "stream_fingerprint", label="posterior stream")


def validate_g16_comparison(comparison: Mapping[str, Any]) -> None:
    if comparison.get("schema") != "ng_g16_path_comparison.v1":
        raise ChronologicalValidationError("comparison: schema mismatch")
    if comparison.get("authority") != "G16_OUTCOME_SCORING_ONLY":
        raise ChronologicalValidationError("comparison: authority mismatch")
    if int(comparison.get("group") or 0) != 16:
        raise ChronologicalValidationError("comparison: group must be 16")
    if comparison.get("actual_g16_outcomes_used") is not True:
        raise ChronologicalValidationError("comparison: G16 outcome use must be disclosed")
    _require_false(
        comparison,
        ("execution_authority", "may_update_ng_brain", "may_change_g16_blind_prior"),
        label="comparison",
    )
    days = list(comparison.get("days") or [])
    if [str(row.get("date") or "") for row in days] != list(G16_DATES):
        raise ChronologicalValidationError("comparison: canonical G16 day order required")
    for row in days:
        day = str(row.get("date") or "")
        for field in ("path_mae_improvement_usd", "endpoint_abs_error_improvement_usd"):
            if _finite(row.get(field)) is None:
                raise ChronologicalValidationError(f"comparison:{day}: {field} must be finite")
        _validate_fingerprint(row, "comparison_day_fingerprint", label=f"comparison:{day}")
    aggregate = dict(comparison.get("aggregate") or {})
    if int(aggregate.get("n_days") or 0) != len(G16_DATES):
        raise ChronologicalValidationError("comparison: aggregate n_days mismatch")
    for field in (
        "mean_path_mae_improvement_usd",
        "mean_net_abs_error_improvement_usd",
        "net_direction_gain",
        "regime_gain",
    ):
        if _finite(aggregate.get(field)) is None:
            raise ChronologicalValidationError(f"comparison: aggregate {field} must be finite")
    _validate_fingerprint(comparison, "comparison_fingerprint", label="comparison")


def _classification(value: float) -> str:
    if value > EPS:
        return "SUPPORT"
    if value < -EPS:
        return "COUNTEREXAMPLE"
    return "NEUTRAL"


def _candidate_status(
    *,
    sample_size: int,
    support_count: int,
    counterexample_count: int,
    mean_path_improvement: float,
    direction_gain_count: int,
    direction_harm_count: int,
) -> tuple[str, bool]:
    if sample_size == 0:
        return "NOT_EXERCISED_G16", False
    if sample_size < 2:
        return "INSUFFICIENT_G16", False
    if (
        support_count >= 2
        and counterexample_count == 0
        and mean_path_improvement > EPS
        and direction_harm_count == 0
    ):
        return "G16_FORWARD_HOLDOUT_SUPPORTED", True
    if (
        counterexample_count > support_count
        or mean_path_improvement < -EPS
        or direction_harm_count > direction_gain_count
    ):
        return "G16_FORWARD_HOLDOUT_CONTRADICTED", False
    return "G16_FORWARD_HOLDOUT_MIXED", False


def _block_status(aggregate: Mapping[str, Any]) -> str:
    improved = int(aggregate.get("days_path_mae_improved") or 0)
    worsened = int(aggregate.get("days_path_mae_worsened") or 0)
    mean_path = float(aggregate["mean_path_mae_improvement_usd"])
    direction_gain = int(aggregate.get("net_direction_gain") or 0)
    regime_gain = int(aggregate.get("regime_gain") or 0)
    if mean_path > EPS and improved > worsened and direction_gain >= 0 and regime_gain >= 0:
        return "G16_FORWARD_HOLDOUT_SUPPORTED"
    if mean_path < -EPS or worsened > improved or direction_gain < 0:
        return "G16_FORWARD_HOLDOUT_CONTRADICTED"
    return "G16_FORWARD_HOLDOUT_MIXED"


def build_chronological_validation(
    adjudication: Mapping[str, Any],
    plan: Mapping[str, Any],
    posterior_stream: Mapping[str, Any],
    g16_comparison: Mapping[str, Any],
) -> dict[str, Any]:
    originals = [copy.deepcopy(dict(value)) for value in (adjudication, plan, posterior_stream, g16_comparison)]
    validate_g15_adjudication(adjudication)
    validate_g16_plan(plan, adjudication=adjudication)
    validate_g16_posterior_stream(posterior_stream, plan=plan)
    validate_g16_comparison(g16_comparison)
    if max(G15_DATES) >= min(G16_DATES):
        raise ChronologicalValidationError("fixed discovery and holdout blocks overlap or move backward")

    comparison_by_day = {str(row["date"]): dict(row) for row in g16_comparison["days"]}
    outputs = list(posterior_stream.get("outputs") or [])
    registry_rows = {
        str(row["proposal_id"]): dict(row)
        for row in adjudication["g16_shadow_registry"].get("candidates") or []
    }
    candidate_results: list[dict[str, Any]] = []
    survivors: list[dict[str, Any]] = []

    for identifier in sorted(registry_rows):
        used_by_day: dict[str, dict[str, float | int]] = {}
        attempted_days: set[str] = set()
        for output in outputs:
            day = str(output["session_day"])
            if identifier in set(output.get("authorized_candidate_ids") or []):
                attempted_days.add(day)
            for attribution in output.get("attribution") or []:
                if str(attribution.get("candidate_id") or "") != identifier or attribution.get("used") is not True:
                    continue
                bucket = used_by_day.setdefault(day, {"used_outputs": 0, "signed_contribution_sum": 0.0, "absolute_contribution_sum": 0.0})
                contribution = float(attribution["directional_contribution"])
                bucket["used_outputs"] = int(bucket["used_outputs"]) + 1
                bucket["signed_contribution_sum"] = float(bucket["signed_contribution_sum"]) + contribution
                bucket["absolute_contribution_sum"] = float(bucket["absolute_contribution_sum"]) + abs(contribution)

        day_rows: list[dict[str, Any]] = []
        for day in G16_DATES:
            if day not in used_by_day:
                continue
            comparison = comparison_by_day[day]
            path = float(comparison["path_mae_improvement_usd"])
            endpoint = float(comparison["endpoint_abs_error_improvement_usd"])
            direction_gain = int(comparison.get("direction_gain") or 0)
            regime_gain = int(comparison.get("regime_gain") or 0)
            usage = used_by_day[day]
            day_rows.append(
                {
                    "date": day,
                    "classification": _classification(path),
                    "path_mae_improvement_usd": round(path, 8),
                    "endpoint_abs_error_improvement_usd": round(endpoint, 8),
                    "direction_gain": direction_gain > 0,
                    "direction_harm": direction_gain < 0,
                    "regime_gain": regime_gain > 0,
                    "regime_harm": regime_gain < 0,
                    "used_outputs": int(usage["used_outputs"]),
                    "signed_contribution_sum": round(float(usage["signed_contribution_sum"]), 8),
                    "absolute_contribution_sum": round(float(usage["absolute_contribution_sum"]), 8),
                    "association_caveat": (
                        "The candidate was used on this day, but score improvement belongs to the full "
                        "authorized refined path and does not isolate this candidate's independent effect."
                    ),
                }
            )

        sample_size = len(day_rows)
        support = sum(int(row["classification"] == "SUPPORT") for row in day_rows)
        counterexamples = sum(int(row["classification"] == "COUNTEREXAMPLE") for row in day_rows)
        neutral = sample_size - support - counterexamples
        path_sum = sum(float(row["path_mae_improvement_usd"]) for row in day_rows)
        endpoint_sum = sum(float(row["endpoint_abs_error_improvement_usd"]) for row in day_rows)
        mean_path = path_sum / sample_size if sample_size else 0.0
        mean_endpoint = endpoint_sum / sample_size if sample_size else 0.0
        direction_gain_count = sum(int(row["direction_gain"]) for row in day_rows)
        direction_harm_count = sum(int(row["direction_harm"]) for row in day_rows)
        regime_gain_count = sum(int(row["regime_gain"]) for row in day_rows)
        regime_harm_count = sum(int(row["regime_harm"]) for row in day_rows)
        status, eligible = _candidate_status(
            sample_size=sample_size,
            support_count=support,
            counterexample_count=counterexamples,
            mean_path_improvement=mean_path,
            direction_gain_count=direction_gain_count,
            direction_harm_count=direction_harm_count,
        )
        row = {
            "candidate_id": identifier,
            "status": status,
            "authority": AUTHORITY,
            "actual_g16_outcomes_used": True,
            "execution_authority": False,
            "may_update_ng_brain": False,
            "may_change_any_blind_prior": False,
            "g15_evidence_fingerprint": registry_rows[identifier].get("g15_evidence_fingerprint"),
            "attempted_g16_days": sorted(attempted_days),
            "used_g16_days": [day["date"] for day in day_rows],
            "sample_size_days": sample_size,
            "metrics": {
                "support_count": support,
                "counterexample_count": counterexamples,
                "neutral_count": neutral,
                "path_mae_improvement_sum_usd": round(path_sum, 8),
                "path_mae_improvement_mean_usd": round(mean_path, 8),
                "endpoint_improvement_sum_usd": round(endpoint_sum, 8),
                "endpoint_improvement_mean_usd": round(mean_endpoint, 8),
                "direction_gain_count": direction_gain_count,
                "direction_harm_count": direction_harm_count,
                "regime_gain_count": regime_gain_count,
                "regime_harm_count": regime_harm_count,
            },
            "days": day_rows,
            "next_untouched_shadow_test": {
                "eligible": eligible,
                "authority": POST_G16_AUTHORITY,
                "may_update_ng_brain": False,
                "may_change_any_blind_prior": False,
            },
        }
        row["validation_fingerprint"] = _fingerprint(row)
        candidate_results.append(row)
        if eligible:
            survivors.append(
                {
                    "candidate_id": identifier,
                    "g15_evidence_fingerprint": row["g15_evidence_fingerprint"],
                    "g16_validation_fingerprint": row["validation_fingerprint"],
                    "g16_status": status,
                    "authority": POST_G16_AUTHORITY,
                    "pre_registered_before_future_outcomes": True,
                    "may_update_ng_brain": False,
                    "may_change_any_blind_prior": False,
                }
            )

    aggregate = copy.deepcopy(dict(g16_comparison.get("aggregate") or {}))
    block = {
        "status": _block_status(aggregate),
        "validation_role": "FORWARD_HOLDOUT_1",
        "n_days": len(G16_DATES),
        "days_path_mae_improved": int(aggregate.get("days_path_mae_improved") or 0),
        "days_path_mae_worsened": int(aggregate.get("days_path_mae_worsened") or 0),
        "mean_path_mae_improvement_usd": float(aggregate["mean_path_mae_improvement_usd"]),
        "mean_net_abs_error_improvement_usd": float(aggregate["mean_net_abs_error_improvement_usd"]),
        "net_direction_gain": int(aggregate.get("net_direction_gain") or 0),
        "regime_gain": int(aggregate.get("regime_gain") or 0),
        "g16_reusable_as_untouched_holdout": False,
        "reason": "G16 outcomes are now consumed for chronological validation and cannot remain untouched.",
    }

    post_g16_registry = {
        "schema": POST_G16_REGISTRY_SCHEMA,
        "market": "NG",
        "source_group": 16,
        "target_partition": "POST_G16_UNTOUCHED_OR_FORWARD_LIVE",
        "authority": POST_G16_AUTHORITY,
        "execution_authority": False,
        "actual_future_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_any_blind_prior": False,
        "candidate_count": len(survivors),
        "candidates": survivors,
        "gate": {
            "next_untouched_shadow_test_authorized": bool(survivors),
            "brain_adoption_authorized": False,
            "reason": (
                "Only candidates supported in both G15 discovery and G16 forward holdout may proceed; "
                "an untouched post-G16 or forward-live SHADOW test is still required."
            ),
        },
    }
    post_g16_registry["registry_fingerprint"] = _fingerprint(post_g16_registry)

    result = {
        "schema": SCHEMA,
        "market": "NG",
        "authority": AUTHORITY,
        "execution_authority": False,
        "actual_g15_outcomes_used": True,
        "actual_g16_outcomes_used": True,
        "may_update_ng_brain": False,
        "may_change_any_blind_prior": False,
        "random_shuffle_used": False,
        "random_shuffle_allowed": False,
        "partition": {
            "policy": "FIXED_CHRONOLOGICAL_BLOCKS_NO_SHUFFLE",
            "discovery": {"group": 15, "role": "DISCOVERY_AND_PRE_REGISTRATION", "dates": list(G15_DATES)},
            "forward_holdout": {"group": 16, "role": "FORWARD_HOLDOUT_1", "dates": list(G16_DATES)},
            "chronological_separation_verified": max(G15_DATES) < min(G16_DATES),
            "next_untouched_partition_required": True,
        },
        "source": {
            "g15_adjudication_fingerprint": adjudication.get("artifact_fingerprint"),
            "g15_registry_fingerprint": adjudication["g16_shadow_registry"].get("registry_fingerprint"),
            "g16_plan_fingerprint": plan.get("plan_fingerprint"),
            "g16_posterior_stream_fingerprint": posterior_stream.get("stream_fingerprint"),
            "g16_comparison_fingerprint": g16_comparison.get("comparison_fingerprint"),
        },
        "candidate_results": candidate_results,
        "block": block,
        "post_g16_shadow_registry": post_g16_registry,
        "adoption_gate": {
            "brain_adoption_authorized": False,
            "execution_authorized": False,
            "requirements_before_any_brain_change": [
                "untouched chronological holdout after G16 or forward-live SHADOW validation",
                "retain G16 counterexamples and stand-downs",
                "explicit human review",
            ],
        },
        "note": (
            "Outcome validation only. Candidate-day association is not isolated causal proof. "
            "G16 is now scored evidence and cannot be recycled as an untouched holdout."
        ),
    }
    result["artifact_fingerprint"] = _fingerprint(result)
    validate_chronological_validation(result)

    if [dict(value) for value in (adjudication, plan, posterior_stream, g16_comparison)] != originals:
        raise ChronologicalValidationError("chronological validation mutated a source artifact")
    return result


def validate_chronological_validation(result: Mapping[str, Any]) -> None:
    if result.get("schema") != SCHEMA or result.get("authority") != AUTHORITY:
        raise ChronologicalValidationError("validation result: schema/authority mismatch")
    if result.get("actual_g15_outcomes_used") is not True or result.get("actual_g16_outcomes_used") is not True:
        raise ChronologicalValidationError("validation result: outcome use must be disclosed")
    _require_false(
        result,
        ("execution_authority", "may_update_ng_brain", "may_change_any_blind_prior", "random_shuffle_used", "random_shuffle_allowed"),
        label="validation result",
    )
    partition = dict(result.get("partition") or {})
    if partition.get("policy") != "FIXED_CHRONOLOGICAL_BLOCKS_NO_SHUFFLE":
        raise ChronologicalValidationError("validation result: partition policy mismatch")
    if (partition.get("discovery") or {}).get("dates") != list(G15_DATES):
        raise ChronologicalValidationError("validation result: G15 discovery dates mismatch")
    if (partition.get("forward_holdout") or {}).get("dates") != list(G16_DATES):
        raise ChronologicalValidationError("validation result: G16 holdout dates mismatch")
    if partition.get("chronological_separation_verified") is not True:
        raise ChronologicalValidationError("validation result: chronological separation not verified")
    if partition.get("next_untouched_partition_required") is not True:
        raise ChronologicalValidationError("validation result: next untouched partition must remain required")

    candidate_ids: set[str] = set()
    survivor_ids: set[str] = set()
    for row in result.get("candidate_results") or []:
        identifier = str(row.get("candidate_id") or "")
        if not identifier or identifier in candidate_ids:
            raise ChronologicalValidationError("validation result: candidate ids must be unique and non-empty")
        candidate_ids.add(identifier)
        if row.get("actual_g16_outcomes_used") is not True:
            raise ChronologicalValidationError(f"validation result:{identifier}: G16 outcome use must be disclosed")
        _require_false(
            row,
            ("execution_authority", "may_update_ng_brain", "may_change_any_blind_prior"),
            label=f"validation result:{identifier}",
        )
        _validate_fingerprint(row, "validation_fingerprint", label=f"validation result:{identifier}")
        if bool((row.get("next_untouched_shadow_test") or {}).get("eligible")):
            survivor_ids.add(identifier)

    registry = dict(result.get("post_g16_shadow_registry") or {})
    if registry.get("schema") != POST_G16_REGISTRY_SCHEMA or registry.get("authority") != POST_G16_AUTHORITY:
        raise ChronologicalValidationError("post-G16 registry: schema/authority mismatch")
    _require_false(
        registry,
        ("execution_authority", "actual_future_outcomes_used", "may_update_ng_brain", "may_change_any_blind_prior"),
        label="post-G16 registry",
    )
    registry_ids = {str(row.get("candidate_id") or "") for row in registry.get("candidates") or []}
    if registry_ids != survivor_ids:
        raise ChronologicalValidationError("post-G16 registry: candidates differ from supported results")
    if int(registry.get("candidate_count") or 0) != len(registry_ids):
        raise ChronologicalValidationError("post-G16 registry: candidate_count mismatch")
    if bool((registry.get("gate") or {}).get("next_untouched_shadow_test_authorized")) != bool(registry_ids):
        raise ChronologicalValidationError("post-G16 registry: gate disagrees with candidate set")
    if (registry.get("gate") or {}).get("brain_adoption_authorized") is not False:
        raise ChronologicalValidationError("post-G16 registry: brain adoption must remain disabled")
    _validate_fingerprint(registry, "registry_fingerprint", label="post-G16 registry")
    if (result.get("adoption_gate") or {}).get("brain_adoption_authorized") is not False:
        raise ChronologicalValidationError("validation result: brain adoption must remain disabled")
    if (result.get("adoption_gate") or {}).get("execution_authorized") is not False:
        raise ChronologicalValidationError("validation result: execution must remain disabled")
    _validate_fingerprint(result, "artifact_fingerprint", label="validation result")


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _fixture() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    candidate_id = "g15_mbo.signed_flow"
    evidence = {
        "id": candidate_id,
        "authority": "LESSON_ADJUDICATION_ONLY",
        "status": "G15_SUPPORTED_SHADOW_CANDIDATE",
        "confidence": "MODERATE_G15_ONLY",
        "actual_outcomes_used": True,
        "execution_authority": False,
        "may_update_ng_brain": False,
        "g16_shadow_test": {"eligible": True, "authority": "G16_PRE_CUTOFF_SHADOW_TEST_ONLY"},
    }
    evidence["evidence_fingerprint"] = _fingerprint(evidence)
    registry = {
        "schema": "ng_g16_shadow_lesson_registry.v1",
        "market": "NG",
        "source_group": 15,
        "target_group": 16,
        "authority": "G16_PRE_CUTOFF_SHADOW_TEST_ONLY",
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "candidate_count": 1,
        "candidates": [
            {
                "proposal_id": candidate_id,
                "g15_evidence_fingerprint": evidence["evidence_fingerprint"],
                "authority": "G16_PRE_CUTOFF_SHADOW_TEST_ONLY",
                "pre_registered_before_g16_outcomes": True,
                "may_update_ng_brain": False,
                "may_change_g16_blind_prior": False,
            }
        ],
        "gate": {"g16_refinement_authorized": True, "g16_outcome_access_authorized": False},
    }
    registry["registry_fingerprint"] = _fingerprint(registry)
    adjudication = {
        "schema": "ng_g15_lesson_adjudication.v1",
        "market": "NG",
        "group": 15,
        "authority": "LESSON_ADJUDICATION_ONLY",
        "execution_authority": False,
        "actual_outcomes_used": True,
        "may_update_ng_brain": False,
        "adjudications": [evidence],
        "g16_shadow_registry": registry,
    }
    adjudication["artifact_fingerprint"] = _fingerprint(adjudication)

    day_map: dict[str, Any] = {}
    for day in G16_DATES:
        row = {
            "date": day,
            "decision_cutoff_utc": f"{day}T21:59:59+00:00",
            "blind_forecast_day_fingerprint": f"blind-{day}",
            "blind_state_day_fingerprint": f"state-{day}",
            "allowed_candidate_ids": [candidate_id],
            "candidate_evidence_fingerprints": {candidate_id: evidence["evidence_fingerprint"]},
            "target_session_tape_used": False,
            "actual_g16_outcomes_used": False,
            "execution_authority": False,
            "may_update_ng_brain": False,
            "may_change_g16_blind_prior": False,
        }
        row["day_plan_fingerprint"] = _fingerprint(row)
        day_map[day] = row
    plan = {
        "schema": "ng_g16_shadow_refinement_plan.v1",
        "market": "NG",
        "group": 16,
        "authority": "G16_PRE_CUTOFF_SHADOW_REFINEMENT_PLAN_ONLY",
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "target_session_tape_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "blind_forecast_fingerprint": "blind",
        "blind_safe_state_fingerprint": "state",
        "lesson_registry_fingerprint": registry["registry_fingerprint"],
        "lesson_adjudication_fingerprint": adjudication["artifact_fingerprint"],
        "candidate_count": 1,
        "candidate_ids": [candidate_id],
        "n_days": len(G16_DATES),
        "days": day_map,
        "gate": {"g16_shadow_refinement_authorized": True, "g16_outcome_access_authorized": False},
    }
    plan["plan_fingerprint"] = _fingerprint(plan)

    outputs = []
    for index, day in enumerate(G16_DATES[:3], 1):
        output = {
            "schema": "ng_g16_shadow_posterior.v1",
            "market": "NG",
            "group": 16,
            "session_day": day,
            "sequence": index,
            "horizon": "close",
            "as_of_event_s": float(index),
            "authority": "G16_CAUSAL_SHADOW_POSTERIOR_ONLY",
            "execution_authority": False,
            "actual_g16_outcomes_used": False,
            "may_update_ng_brain": False,
            "may_change_g16_blind_prior": False,
            "status": "UPDATED",
            "blind_prior": {"up": 0.3, "flat": 0.2, "down": 0.5},
            "posterior": {"up": 0.2, "flat": 0.2, "down": 0.6},
            "scores": {"directional_log_weight": -0.2, "flat_log_weight": 0.0, "update_strength": 1.0},
            "attribution": [
                {
                    "candidate_id": candidate_id,
                    "implemented_handler": True,
                    "used": True,
                    "value": {"imb_level": -0.4},
                    "directional_contribution": -0.4,
                }
            ],
            "authorized_candidate_ids": [candidate_id],
            "implemented_candidate_ids": [candidate_id],
            "unhandled_candidate_ids": [],
            "stand_down_reasons": [],
            "provenance": {"plan_fingerprint": plan["plan_fingerprint"]},
        }
        output["output_fingerprint"] = _fingerprint(output)
        outputs.append(output)
    stream = {
        "schema": "ng_g16_shadow_posterior_stream.v1",
        "market": "NG",
        "group": 16,
        "authority": "G16_CAUSAL_SHADOW_POSTERIOR_STREAM_ONLY",
        "execution_authority": False,
        "actual_g16_outcomes_used": False,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "plan_fingerprint": plan["plan_fingerprint"],
        "authorization_stream_fingerprint": "auth",
        "n_outputs": len(outputs),
        "outputs": outputs,
    }
    stream["stream_fingerprint"] = _fingerprint(stream)

    days = []
    for day in G16_DATES:
        row = {
            "date": day,
            "path_mae_improvement_usd": 20.0,
            "path_rmse_improvement_usd": 20.0,
            "net_abs_error_improvement_usd": 20.0,
            "endpoint_abs_error_improvement_usd": 20.0,
            "blind_net_direction_ok": False,
            "refined_net_direction_ok": True,
            "direction_gain": 1,
            "blind_regime_ok": False,
            "refined_regime_ok": True,
            "regime_gain": 1,
            "blind_cumulative_drift_usd": 100.0,
            "refined_cumulative_drift_usd": 50.0,
        }
        row["comparison_day_fingerprint"] = _fingerprint(row)
        days.append(row)
    comparison = {
        "schema": "ng_g16_path_comparison.v1",
        "market": "NG",
        "group": 16,
        "authority": "G16_OUTCOME_SCORING_ONLY",
        "execution_authority": False,
        "actual_g16_outcomes_used": True,
        "may_update_ng_brain": False,
        "may_change_g16_blind_prior": False,
        "actual_sha256": "actual",
        "blind_score_fingerprint": "blind-score",
        "refined_score_fingerprint": "refined-score",
        "days": days,
        "aggregate": {
            "n_days": len(G16_DATES),
            "days_path_mae_improved": len(G16_DATES),
            "days_path_mae_worsened": 0,
            "mean_path_mae_improvement_usd": 20.0,
            "mean_path_rmse_improvement_usd": 20.0,
            "mean_net_abs_error_improvement_usd": 20.0,
            "net_direction_gain": len(G16_DATES),
            "regime_gain": len(G16_DATES),
            "blind_final_cumulative_drift_usd": 100.0,
            "refined_final_cumulative_drift_usd": 50.0,
            "absolute_final_drift_improvement_usd": 50.0,
        },
    }
    comparison["comparison_fingerprint"] = _fingerprint(comparison)
    return adjudication, plan, stream, comparison


def selftest() -> int:
    adjudication, plan, stream, comparison = _fixture()
    originals = copy.deepcopy((adjudication, plan, stream, comparison))
    result = build_chronological_validation(adjudication, plan, stream, comparison)
    assert result["block"]["status"] == "G16_FORWARD_HOLDOUT_SUPPORTED"
    assert result["candidate_results"][0]["status"] == "G16_FORWARD_HOLDOUT_SUPPORTED"
    assert result["post_g16_shadow_registry"]["candidate_count"] == 1
    assert (adjudication, plan, stream, comparison) == originals
    validate_chronological_validation(result)
    print("[ng_chronological_validation] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate G15 lessons chronologically on the G16 forward holdout")
    parser.add_argument("--adjudication", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--posterior-stream", type=Path)
    parser.add_argument("--g16-comparison", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    required = ("adjudication", "plan", "posterior_stream", "g16_comparison", "out")
    if any(getattr(args, name) is None for name in required):
        parser.error("--adjudication --plan --posterior-stream --g16-comparison --out are required")
    result = build_chronological_validation(
        json.loads(args.adjudication.read_text(encoding="utf-8")),
        json.loads(args.plan.read_text(encoding="utf-8")),
        json.loads(args.posterior_stream.read_text(encoding="utf-8")),
        json.loads(args.g16_comparison.read_text(encoding="utf-8")),
    )
    _atomic_json(args.out, result)
    print(json.dumps({
        "status": result["block"]["status"],
        "survivors": result["post_g16_shadow_registry"]["candidate_count"],
        "out": str(args.out),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
