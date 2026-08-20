"""Fail-closed temporal P0 controls for provisional Frankie research.

The helpers in this module are deliberately outside every V4 runner.  They
produce immutable assessment receipts; they do not update a prediction model,
choose a V4 lock, authorize a launch, promote a candidate, or mutate Frankie.

Paper boundaries
----------------
* The planted-null audit uses a precommitted alpha-spending union bound.  It is
  an anytime-valid sequential *audit* under explicitly listed super-uniform
  null-p-value assumptions, not an implementation of Howard et al.'s
  confidence-sequence constructions.
* The accumulated-accuracy-gap receipt uses the one-sided loss from Ringel et
  al. (full classifier correct and early classifier wrong), separate
  calibration/test partitions, and accumulated halt-time slices.  Its simple
  global-threshold/Hoeffding calibration is an operational LTT-style control,
  not the paper's full two-stage conditional algorithm.
* The delayed-label wrapper implements the scalar Gibbs--Candes ACI update,
  ``alpha <- alpha + gamma * (target_alpha - error)``, with an operational
  [0, 1] projection.  Prediction-set construction remains external.
* The adaptive-window assessment follows the empirical-Bernstein/
  Goldenshluger--Lepski shape of Han, Huang, and Wang for a frozen finite model
  pool.  It is limited to current-risk assessment/model-selection evidence.
  It provides no cumulative-loss, best-fixed-expert, switching-regret, or live
  deployment theorem.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "FRANKIE_TEMPORAL_P0_CONTROLS_V1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class TemporalP0ControlError(ValueError):
    """Raised when temporal evidence is malformed, contaminated, or sparse."""


def _sha256_json(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TemporalP0ControlError(f"value is not canonical JSON: {exc}") from exc
    return hashlib.sha256(encoded).hexdigest()


def _identifier(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 256:
        raise TemporalP0ControlError(f"{label} must be a non-empty bounded identifier")
    return text


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TemporalP0ControlError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise TemporalP0ControlError(f"{label} must be a finite number")
    return result


def _probability(value: Any, label: str, *, open_interval: bool = False) -> float:
    result = _number(value, label)
    valid = 0.0 < result < 1.0 if open_interval else 0.0 <= result <= 1.0
    if not valid:
        interval = "(0, 1)" if open_interval else "[0, 1]"
        raise TemporalP0ControlError(f"{label} must be within {interval}")
    return result


def _timestamp(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise TemporalP0ControlError(f"{label} must be an epoch or timezone-aware ISO timestamp")
    if isinstance(value, (int, float)):
        return _number(value, label)
    if not isinstance(value, str) or not value.strip():
        raise TemporalP0ControlError(f"{label} must be an epoch or timezone-aware ISO timestamp")
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TemporalP0ControlError(f"{label} is not a valid ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TemporalP0ControlError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc).timestamp()


def _rows(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TemporalP0ControlError(f"{label} must be a sequence")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise TemporalP0ControlError(f"{label}[{index}] must be an object")
        result.append(dict(item))
    return result


def _authority() -> dict[str, bool]:
    return {
        "v4_launch_authority": False,
        "model_promotion_authority": False,
        "runtime_mutation_authority": False,
        "trading_authority": False,
    }


def _receipt(core: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(core)
    payload["authority"] = _authority()
    return {**payload, "receipt_hash": _sha256_json(payload)}


def _first_crossing(p_values: Sequence[float], thresholds: Sequence[float]) -> int | None:
    for index, (p_value, threshold) in enumerate(zip(p_values, thresholds), start=1):
        if p_value <= threshold:
            return index
    return None


def audit_planted_null_first_locks(
    trials: Sequence[Mapping[str, Any]],
    *,
    alpha: float,
    spending_policy: str = "TELESCOPING",
    planned_horizon: int | None = None,
    empirical_confidence_delta: float = 0.05,
    max_empirical_upper_false_lock_rate: float | None = None,
) -> dict[str, Any]:
    """Audit first locks on planted-null paths under precommitted spending.

    ``TELESCOPING`` spends ``alpha / (t * (t + 1))`` at look ``t`` and
    therefore spends at most ``alpha`` over an unbounded horizon.  The finite
    Bonferroni and naive pointwise-alpha paths are reported as controls.  The
    time-uniform implication requires each null p-value to be super-uniform,
    the spending rule and statistic to be fixed before looking, and the input
    paths truly to be null.  This function validates none of those scientific
    premises merely by observing p-values; it records them as assumptions.
    """

    family_alpha = _probability(alpha, "alpha", open_interval=True)
    empirical_delta = _probability(
        empirical_confidence_delta,
        "empirical_confidence_delta",
        open_interval=True,
    )
    policy = str(spending_policy or "").strip().upper()
    if policy not in {"TELESCOPING", "FINITE_UNIFORM"}:
        raise TemporalP0ControlError("spending_policy must be TELESCOPING or FINITE_UNIFORM")
    if planned_horizon is not None and (
        type(planned_horizon) is not int or planned_horizon <= 0
    ):
        raise TemporalP0ControlError("planned_horizon must be a positive integer")
    if policy == "FINITE_UNIFORM" and planned_horizon is None:
        raise TemporalP0ControlError("FINITE_UNIFORM requires planned_horizon")
    empirical_cap = (
        _probability(
            max_empirical_upper_false_lock_rate,
            "max_empirical_upper_false_lock_rate",
        )
        if max_empirical_upper_false_lock_rate is not None
        else None
    )

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    max_looks = 0
    for trial_index, trial in enumerate(_rows(trials, "trials")):
        trial_id = _identifier(trial.get("trial_id"), f"trials[{trial_index}].trial_id")
        if trial_id in seen:
            raise TemporalP0ControlError(f"duplicate trial_id: {trial_id}")
        seen.add(trial_id)
        if trial.get("planted_null") is not True:
            raise TemporalP0ControlError(f"trial {trial_id} is not explicitly planted_null=true")
        looks = _rows(trial.get("looks"), f"trial {trial_id}.looks")
        if not looks:
            raise TemporalP0ControlError(f"trial {trial_id} has no sequential looks")
        if planned_horizon is not None and len(looks) > planned_horizon:
            raise TemporalP0ControlError(f"trial {trial_id} exceeds the planned horizon")
        previous_time = -math.inf
        p_values: list[float] = []
        for look_index, look in enumerate(looks, start=1):
            if look.get("look_index") != look_index:
                raise TemporalP0ControlError(
                    f"trial {trial_id} look_index must be contiguous and one-based"
                )
            observed_at = _timestamp(
                look.get("observed_at"), f"trial {trial_id} look {look_index}.observed_at"
            )
            if observed_at <= previous_time:
                raise TemporalP0ControlError(
                    f"trial {trial_id} observed_at values must be strictly increasing"
                )
            previous_time = observed_at
            p_values.append(
                _probability(look.get("p_value"), f"trial {trial_id} look {look_index}.p_value")
            )
        spend = [
            family_alpha / (index * (index + 1))
            if policy == "TELESCOPING"
            else family_alpha / int(planned_horizon)
            for index in range(1, len(p_values) + 1)
        ]
        bonferroni_horizon = planned_horizon or len(p_values)
        bonferroni = [family_alpha / bonferroni_horizon] * len(p_values)
        spending_lock = _first_crossing(p_values, spend)
        recorded = trial.get("recorded_spending_first_lock_look")
        if recorded is not None and (type(recorded) is not int or recorded <= 0):
            raise TemporalP0ControlError(
                f"trial {trial_id}.recorded_spending_first_lock_look must be positive or null"
            )
        if recorded != spending_lock:
            raise TemporalP0ControlError(
                f"trial {trial_id} recorded first lock disagrees with recomputation"
            )
        normalized.append(
            {
                "trial_id": trial_id,
                "look_count": len(p_values),
                "p_values_hash": _sha256_json(p_values),
                "spending_first_lock_look": spending_lock,
                "bonferroni_first_lock_look": _first_crossing(p_values, bonferroni),
                "naive_pointwise_first_lock_look": _first_crossing(
                    p_values, [family_alpha] * len(p_values)
                ),
            }
        )
        max_looks = max(max_looks, len(p_values))

    if not normalized:
        raise TemporalP0ControlError("planted-null audit requires at least one trial")

    def summarize(key: str) -> dict[str, Any]:
        locked = sum(row[key] is not None for row in normalized)
        rate = locked / len(normalized)
        # A distribution-free concentration diagnostic for the empirical null
        # trial rate.  It is not the sequential validity argument itself.
        upper = min(1.0, rate + math.sqrt(math.log(1.0 / empirical_delta) / (2 * len(normalized))))
        return {"false_locks": locked, "trial_count": len(normalized), "rate": rate, "hoeffding_upper": upper}

    spending_summary = summarize("spending_first_lock_look")
    empirical_passed = (
        None
        if empirical_cap is None
        else spending_summary["hoeffding_upper"] <= empirical_cap
    )
    if policy == "TELESCOPING":
        total_planned_spend = family_alpha
        spend_description = "alpha/(t*(t+1)); infinite sum equals alpha"
    else:
        total_planned_spend = family_alpha
        spend_description = "alpha/planned_horizon for each precommitted look"

    return _receipt(
        {
            "schema_version": SCHEMA_VERSION,
            "control": "PLANTED_NULL_SEQUENTIAL_FIRST_LOCK",
            "method": "PRECOMMITTED_ALPHA_SPENDING_UNION_BOUND",
            "spending_policy": policy,
            "alpha": family_alpha,
            "planned_horizon": planned_horizon,
            "maximum_observed_looks": max_looks,
            "total_planned_spend_upper_bound": total_planned_spend,
            "spend_description": spend_description,
            "assumptions": [
                "each planted-null p-value is marginally super-uniform",
                "the monitored statistic and spending rule were fixed before observing a path",
                "every submitted trial is genuinely generated under the declared null",
                "a lock is the first p-value at or below that look's allocated alpha",
                "dependence across looks is allowed by the union-bound argument",
            ],
            "assumptions_empirically_proved_by_this_receipt": False,
            "time_uniform_type_i_statement": (
                "Under the listed assumptions, probability of any spending-rule false lock "
                "is at most alpha."
            ),
            "confidence_sequence_implementation": False,
            "paper_faithful_howard_boundary": False,
            "trial_receipts": normalized,
            "spending_result": spending_summary,
            "finite_bonferroni_control": summarize("bonferroni_first_lock_look"),
            "naive_pointwise_control": summarize("naive_pointwise_first_lock_look"),
            "empirical_gate_cap": empirical_cap,
            "empirical_gate_passed": empirical_passed,
            "input_hash": _sha256_json(_rows(trials, "trials")),
        }
    )


def _normalize_early_cases(
    cases: Sequence[Mapping[str, Any]], *, partition: str
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    expected_look_count: int | None = None
    for case_index, case in enumerate(_rows(cases, f"{partition.lower()}_cases")):
        case_id = _identifier(case.get("case_id"), f"{partition} case_id")
        if case_id in seen:
            raise TemporalP0ControlError(f"duplicate {partition} case_id: {case_id}")
        seen.add(case_id)
        truth = _identifier(case.get("truth_label"), f"case {case_id}.truth_label")
        full_prediction = _identifier(
            case.get("full_prediction"), f"case {case_id}.full_prediction"
        )
        start_at = _timestamp(case.get("case_start_at"), f"case {case_id}.case_start_at")
        reveal_at = _timestamp(case.get("label_reveal_at"), f"case {case_id}.label_reveal_at")
        if reveal_at <= start_at:
            raise TemporalP0ControlError(f"case {case_id} label must reveal after case start")
        looks = _rows(case.get("prefixes"), f"case {case_id}.prefixes")
        if not looks:
            raise TemporalP0ControlError(f"case {case_id} has no prefixes")
        if expected_look_count is None:
            expected_look_count = len(looks)
        elif len(looks) != expected_look_count:
            raise TemporalP0ControlError(
                "AAG receipt requires a common precommitted look grid across cases"
            )
        normalized_looks: list[dict[str, Any]] = []
        previous_time = -math.inf
        for look_index, look in enumerate(looks, start=1):
            if look.get("look_index") != look_index:
                raise TemporalP0ControlError(f"case {case_id} look indices must be contiguous")
            observed_at = _timestamp(
                look.get("observed_at"), f"case {case_id} look {look_index}.observed_at"
            )
            if observed_at <= previous_time or observed_at < start_at or observed_at >= reveal_at:
                raise TemporalP0ControlError(
                    f"case {case_id} prefix times must increase within [start, reveal)"
                )
            previous_time = observed_at
            normalized_looks.append(
                {
                    "look_index": look_index,
                    "observed_at": observed_at,
                    "prediction": _identifier(
                        look.get("prediction"), f"case {case_id} prefix prediction"
                    ),
                    "confidence": _probability(
                        look.get("confidence"), f"case {case_id} prefix confidence"
                    ),
                }
            )
        result.append(
            {
                "case_id": case_id,
                "partition": partition,
                "truth_label": truth,
                "full_prediction": full_prediction,
                "case_start_at": start_at,
                "label_reveal_at": reveal_at,
                "prefixes": normalized_looks,
            }
        )
    if not result:
        raise TemporalP0ControlError(f"{partition} partition must not be empty")
    return result


def _evaluate_aag_policy(cases: Sequence[Mapping[str, Any]], threshold: float) -> dict[str, Any]:
    per_case: list[dict[str, Any]] = []
    look_count = len(cases[0]["prefixes"])
    for case in cases:
        chosen = next(
            (look for look in case["prefixes"] if look["confidence"] >= threshold),
            None,
        )
        if chosen is None:
            halt_index = look_count
            early_prediction = case["full_prediction"]
            fell_back_to_full = True
        else:
            halt_index = chosen["look_index"]
            early_prediction = chosen["prediction"]
            fell_back_to_full = False
        gap_loss = int(
            case["full_prediction"] == case["truth_label"]
            and early_prediction != case["truth_label"]
        )
        per_case.append(
            {
                "case_id": case["case_id"],
                "halt_index": halt_index,
                "normalized_halt_time": halt_index / look_count,
                "early_prediction": early_prediction,
                "full_prediction_correct": case["full_prediction"] == case["truth_label"],
                "gap_loss": gap_loss,
                "fell_back_to_full": fell_back_to_full,
            }
        )
    accumulated: list[dict[str, Any]] = []
    for look_index in range(1, look_count + 1):
        halted = [row for row in per_case if row["halt_index"] <= look_index]
        accumulated.append(
            {
                "through_look_index": look_index,
                "halted_count": len(halted),
                "empirical_accuracy_gap": (
                    sum(row["gap_loss"] for row in halted) / len(halted) if halted else None
                ),
            }
        )
    return {
        "threshold": threshold,
        "case_count": len(per_case),
        "mean_normalized_halt_time": sum(row["normalized_halt_time"] for row in per_case)
        / len(per_case),
        "full_fallback_count": sum(row["fell_back_to_full"] for row in per_case),
        "marginal_accuracy_gap": sum(row["gap_loss"] for row in per_case) / len(per_case),
        "accumulated_halt_time_gaps": accumulated,
        "case_receipts_hash": _sha256_json(per_case),
    }


def calibrate_accumulated_accuracy_gap(
    calibration_cases: Sequence[Mapping[str, Any]],
    test_cases: Sequence[Mapping[str, Any]],
    *,
    candidate_thresholds: Sequence[float],
    max_accuracy_gap: float,
    confidence_delta: float,
    min_calibration_halts_per_slice: int = 5,
    calibration_iid_assumption_declared: bool = False,
) -> dict[str, Any]:
    """Calibrate one global prefix-confidence lock without using test truth.

    Candidate policies are tested on the calibration partition only.  For a
    fixed candidate, the lock time depends solely on prefix confidences and the
    precommitted threshold.  Truth and the full-stream prediction are opened
    only to score the one-sided accuracy-gap loss after the halt.  Candidate
    choice minimizes calibration earliness among policies whose simultaneous
    Hoeffding upper bounds pass every sufficiently populated accumulated-halt
    slice.  Test truth is used only after the selected threshold is frozen.
    """

    calibration = _normalize_early_cases(calibration_cases, partition="CALIBRATION")
    test = _normalize_early_cases(test_cases, partition="TEST")
    calibration_ids = {case["case_id"] for case in calibration}
    test_ids = {case["case_id"] for case in test}
    overlap = calibration_ids.intersection(test_ids)
    if overlap:
        raise TemporalP0ControlError(f"calibration/test case IDs overlap: {sorted(overlap)}")
    if max(case["label_reveal_at"] for case in calibration) > min(
        case["case_start_at"] for case in test
    ):
        raise TemporalP0ControlError(
            "calibration labels must all mature before the first test case starts"
        )
    if len(calibration[0]["prefixes"]) != len(test[0]["prefixes"]):
        raise TemporalP0ControlError("calibration and test must share one look grid")
    if type(min_calibration_halts_per_slice) is not int or min_calibration_halts_per_slice <= 0:
        raise TemporalP0ControlError("min_calibration_halts_per_slice must be positive")
    gap_cap = _probability(max_accuracy_gap, "max_accuracy_gap")
    delta = _probability(confidence_delta, "confidence_delta", open_interval=True)
    thresholds = sorted(
        {_probability(value, "candidate threshold") for value in candidate_thresholds}
    )
    if not thresholds:
        raise TemporalP0ControlError("candidate_thresholds must not be empty")

    look_count = len(calibration[0]["prefixes"])
    comparison_count = len(thresholds) * look_count
    per_comparison_delta = delta / comparison_count
    candidates: list[dict[str, Any]] = []
    for threshold in thresholds:
        summary = _evaluate_aag_policy(calibration, threshold)
        slices: list[dict[str, Any]] = []
        passed = True
        populated = 0
        for item in summary["accumulated_halt_time_gaps"]:
            count = item["halted_count"]
            if count < min_calibration_halts_per_slice:
                slices.append({**item, "upper_bound": None, "eligible": False})
                continue
            populated += 1
            empirical = float(item["empirical_accuracy_gap"])
            upper = min(
                1.0,
                empirical + math.sqrt(math.log(1.0 / per_comparison_delta) / (2 * count)),
            )
            slice_passed = upper <= gap_cap
            passed = passed and slice_passed
            slices.append(
                {**item, "upper_bound": upper, "eligible": True, "passed": slice_passed}
            )
        # At least the terminal cumulative slice must be assessable.
        if populated == 0:
            passed = False
        candidates.append(
            {
                **summary,
                "simultaneous_slices": slices,
                "eligible_slice_count": populated,
                "calibration_passed": passed,
            }
        )
    passing = [candidate for candidate in candidates if candidate["calibration_passed"]]
    selected = (
        min(
            passing,
            key=lambda candidate: (
                candidate["mean_normalized_halt_time"],
                -candidate["threshold"],
            ),
        )
        if passing
        else None
    )
    test_summary = (
        _evaluate_aag_policy(test, float(selected["threshold"])) if selected is not None else None
    )

    return _receipt(
        {
            "schema_version": SCHEMA_VERSION,
            "control": "ACCUMULATED_ACCURACY_GAP_LOCK_CALIBRATION",
            "method": "GLOBAL_THRESHOLD_LTT_STYLE_HOEFFDING",
            "paper_faithful_ringel_two_stage_conditional_algorithm": False,
            "gap_loss_definition": "FULL_CORRECT_AND_EARLY_WRONG",
            "timing_rule_inputs": ["prefix confidence", "candidate threshold", "look order"],
            "truth_relative_timing_optimization": False,
            "test_partition_used_for_selection": False,
            "max_accuracy_gap": gap_cap,
            "confidence_delta": delta,
            "simultaneous_comparison_count": comparison_count,
            "min_calibration_halts_per_slice": min_calibration_halts_per_slice,
            "calibration_iid_assumption_declared": calibration_iid_assumption_declared is True,
            "finite_sample_distribution_free_claim_active": calibration_iid_assumption_declared is True,
            "assumptions": [
                "the sequential classifier and threshold grid are frozen before calibration",
                "calibration cases are independent and identically distributed for formal bounds",
                "calibration and test identities are disjoint",
                "all calibration labels mature before test begins",
                "the full-stream prediction is a comparator and never a prefix feature",
            ],
            "calibration_partition_hash": _sha256_json(calibration),
            "test_partition_hash": _sha256_json(test),
            "candidate_summaries": candidates,
            "selected_threshold": selected["threshold"] if selected is not None else None,
            "selected_calibration_summary_hash": _sha256_json(selected) if selected else None,
            "test_summary": test_summary,
            "calibration_passed": selected is not None,
        }
    )


def run_delayed_label_aci(
    events: Sequence[Mapping[str, Any]],
    *,
    target_miscoverage: float,
    gamma: float,
    initial_alpha: float | None = None,
    audit_until: Any | None = None,
) -> dict[str, Any]:
    """Replay the scalar ACI update while enforcing causal label maturity.

    Each event supplies the eventual miscoverage indicator for the ACI set that
    was emitted and a matched static-alpha set.  Both outcomes remain queued
    until ``reveal_at``.  All predictions sharing a timestamp receive the same
    pre-update alpha, preventing case-ID order from leaking same-time labels.
    """

    target = _probability(target_miscoverage, "target_miscoverage", open_interval=True)
    step = _number(gamma, "gamma")
    if step <= 0.0:
        raise TemporalP0ControlError("gamma must be positive")
    alpha_state = (
        target if initial_alpha is None else _probability(initial_alpha, "initial_alpha")
    )
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, event in enumerate(_rows(events, "events")):
        case_id = _identifier(event.get("case_id"), f"events[{index}].case_id")
        if case_id in seen:
            raise TemporalP0ControlError(f"duplicate ACI case_id: {case_id}")
        seen.add(case_id)
        prediction_at = _timestamp(event.get("prediction_at"), f"case {case_id}.prediction_at")
        reveal_at = _timestamp(event.get("reveal_at"), f"case {case_id}.reveal_at")
        if reveal_at <= prediction_at:
            raise TemporalP0ControlError(f"case {case_id} reveal_at must follow prediction_at")
        aci_miscovered = event.get("aci_miscovered")
        static_miscovered = event.get("static_miscovered")
        if type(aci_miscovered) is not bool or type(static_miscovered) is not bool:
            raise TemporalP0ControlError(
                f"case {case_id} miscoverage indicators must be boolean"
            )
        normalized.append(
            {
                "case_id": case_id,
                "prediction_at": prediction_at,
                "reveal_at": reveal_at,
                "aci_miscovered": aci_miscovered,
                "static_miscovered": static_miscovered,
            }
        )
    if not normalized:
        raise TemporalP0ControlError("ACI replay requires at least one event")
    normalized.sort(key=lambda row: (row["prediction_at"], row["case_id"]))

    pending: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []

    def mature(cutoff: float) -> None:
        nonlocal alpha_state, pending
        ready = sorted(
            (row for row in pending if row["reveal_at"] <= cutoff),
            key=lambda row: (row["reveal_at"], row["prediction_at"], row["case_id"]),
        )
        ready_ids = {row["case_id"] for row in ready}
        pending = [row for row in pending if row["case_id"] not in ready_ids]
        for row in ready:
            before = alpha_state
            raw_after = before + step * (target - int(row["aci_miscovered"]))
            alpha_state = min(1.0, max(0.0, raw_after))
            updates.append(
                {
                    "case_id": row["case_id"],
                    "reveal_at": row["reveal_at"],
                    "alpha_before": before,
                    "raw_alpha_after": raw_after,
                    "alpha_after": alpha_state,
                    "aci_miscovered": row["aci_miscovered"],
                    "processed_at_cutoff": cutoff,
                }
            )

    prediction_times = sorted({row["prediction_at"] for row in normalized})
    for prediction_time in prediction_times:
        mature(prediction_time)
        same_time = [row for row in normalized if row["prediction_at"] == prediction_time]
        update_count = len(updates)
        for row in same_time:
            decisions.append(
                {
                    "case_id": row["case_id"],
                    "prediction_at": prediction_time,
                    "alpha_used": alpha_state,
                    "matured_update_count_before_prediction": update_count,
                }
            )
        pending.extend(same_time)

    final_cutoff = (
        _timestamp(audit_until, "audit_until")
        if audit_until is not None
        else prediction_times[-1]
    )
    if final_cutoff < prediction_times[-1]:
        raise TemporalP0ControlError("audit_until cannot predate the final prediction")
    mature(final_cutoff)
    matured_ids = {row["case_id"] for row in updates}
    matured_rows = [row for row in normalized if row["case_id"] in matured_ids]

    def rate(key: str) -> float | None:
        return (
            sum(int(row[key]) for row in matured_rows) / len(matured_rows)
            if matured_rows
            else None
        )

    return _receipt(
        {
            "schema_version": SCHEMA_VERSION,
            "control": "DELAYED_LABEL_ACI_REPLAY",
            "method": "PROJECTED_SCALAR_ACI_UPDATE",
            "target_miscoverage": target,
            "gamma": step,
            "initial_alpha": target if initial_alpha is None else initial_alpha,
            "final_alpha": alpha_state,
            "prediction_set_construction_external": True,
            "paper_scalar_update_implemented": True,
            "paper_faithful_end_to_end_conformal_system": False,
            "long_run_coverage_or_instance_conditional_claim": False,
            "matured_labels_only": True,
            "same_timestamp_batching": True,
            "decision_ledger": decisions,
            "update_ledger": updates,
            "pending_case_ids": sorted(row["case_id"] for row in pending),
            "matured_case_count": len(matured_rows),
            "aci_miscoverage_rate_on_matured": rate("aci_miscovered"),
            "static_alpha_control_miscoverage_rate_on_matured": rate("static_miscovered"),
            "input_hash": _sha256_json(normalized),
        }
    )


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _sample_std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    center = _mean(values)
    return math.sqrt(sum((value - center) ** 2 for value in values) / (len(values) - 1))


def _period_window_values(
    rows: Sequence[Mapping[str, Any]], model_id: str, period_count: int
) -> list[float]:
    periods = sorted({int(row["period_index"]) for row in rows})
    chosen = set(periods[-period_count:])
    return [float(row["losses"][model_id]) for row in rows if row["period_index"] in chosen]


def _hhw_window_table(
    rows: Sequence[Mapping[str, Any]],
    model_id: str,
    candidate_periods: Sequence[int],
    *,
    loss_range: float,
    delta_prime: float,
    min_samples: int,
) -> list[dict[str, Any]]:
    table: list[dict[str, Any]] = []
    for period_count in sorted(candidate_periods):
        values = _period_window_values(rows, model_id, period_count)
        if len(values) < min_samples:
            raise TemporalP0ControlError(
                f"sparse adaptive window: model={model_id}, periods={period_count}, "
                f"samples={len(values)}, required={min_samples}"
            )
        mean = _mean(values)
        if len(values) == 1:
            psi = loss_range
        else:
            log_term = math.log(2.0 / delta_prime)
            psi = _sample_std(values) * math.sqrt(2.0 * log_term / len(values))
            psi += 8.0 * loss_range * log_term / (3.0 * (len(values) - 1))
        table.append(
            {
                "window_periods": period_count,
                "sample_count": len(values),
                "mean_loss": mean,
                "sample_std": _sample_std(values),
                "psi": psi,
            }
        )
    for row in table:
        smaller = [item for item in table if item["window_periods"] <= row["window_periods"]]
        phi = max(
            0.0,
            max(
                abs(row["mean_loss"] - item["mean_loss"]) - row["psi"] - item["psi"]
                for item in smaller
            ),
        )
        row["phi"] = phi
        row["selection_objective"] = phi + row["psi"]
    return table


def assess_frozen_pool_current_risk(
    loss_rows: Sequence[Mapping[str, Any]],
    frozen_model_hashes: Mapping[str, str],
    assessments: Sequence[Mapping[str, Any]],
    *,
    loss_upper_bound: float,
    delta: float,
    adaptive_window_periods: Sequence[int],
    fixed_window_periods: int,
    recent_window_periods: int,
    min_samples_per_window: int = 2,
) -> dict[str, Any]:
    """Assess a frozen model pool with causal current-risk windows and controls.

    Only rows whose labels have matured by an assessment timestamp participate.
    The adaptive estimator minimizes ``phi_hat + psi_hat`` over precommitted
    windows, following Han--Huang--Wang's assessment shape.  Model parameters
    are represented only by immutable hashes.  Fixed-window, expanding-window,
    and recent-window selectors use the exact same matured rows and model pool.
    Switch counts are operational diagnostics, not a switching guarantee.
    """

    if not isinstance(frozen_model_hashes, Mapping) or len(frozen_model_hashes) < 2:
        raise TemporalP0ControlError("frozen_model_hashes must declare at least two models")
    model_hashes: dict[str, str] = {}
    for raw_id, raw_hash in frozen_model_hashes.items():
        model_id = _identifier(raw_id, "model_id")
        model_hash = str(raw_hash or "").strip()
        if not SHA256_RE.fullmatch(model_hash):
            raise TemporalP0ControlError(f"model {model_id} must have a lowercase SHA-256 hash")
        model_hashes[model_id] = model_hash
    if len(model_hashes) != len(frozen_model_hashes):
        raise TemporalP0ControlError("model identifiers must be unique after normalization")
    loss_bound = _number(loss_upper_bound, "loss_upper_bound")
    if loss_bound <= 0.0:
        raise TemporalP0ControlError("loss_upper_bound must be positive")
    confidence_delta = _probability(delta, "delta", open_interval=True)
    for label, value in (
        ("fixed_window_periods", fixed_window_periods),
        ("recent_window_periods", recent_window_periods),
        ("min_samples_per_window", min_samples_per_window),
    ):
        if type(value) is not int or value <= 0:
            raise TemporalP0ControlError(f"{label} must be a positive integer")
    adaptive_periods = sorted(set(adaptive_window_periods))
    if not adaptive_periods or any(type(value) is not int or value <= 0 for value in adaptive_periods):
        raise TemporalP0ControlError("adaptive_window_periods must contain positive integers")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    expected_models = set(model_hashes)
    for index, row in enumerate(_rows(loss_rows, "loss_rows")):
        case_id = _identifier(row.get("case_id"), f"loss_rows[{index}].case_id")
        if case_id in seen:
            raise TemporalP0ControlError(f"duplicate loss case_id: {case_id}")
        seen.add(case_id)
        period_index = row.get("period_index")
        if type(period_index) is not int or period_index <= 0:
            raise TemporalP0ControlError(f"case {case_id}.period_index must be positive integer")
        observed_at = _timestamp(row.get("observed_at"), f"case {case_id}.observed_at")
        reveal_at = _timestamp(row.get("reveal_at"), f"case {case_id}.reveal_at")
        if reveal_at < observed_at:
            raise TemporalP0ControlError(f"case {case_id} reveal_at cannot precede observed_at")
        losses = row.get("losses")
        if not isinstance(losses, Mapping) or set(losses) != expected_models:
            raise TemporalP0ControlError(f"case {case_id} must provide the exact frozen model pool")
        normalized_losses: dict[str, float] = {}
        for model_id in sorted(expected_models):
            value = _number(losses[model_id], f"case {case_id} loss {model_id}")
            if not 0.0 <= value <= loss_bound:
                raise TemporalP0ControlError(
                    f"case {case_id} loss {model_id} must be within [0, loss_upper_bound]"
                )
            normalized_losses[model_id] = value
        normalized.append(
            {
                "case_id": case_id,
                "period_index": period_index,
                "observed_at": observed_at,
                "reveal_at": reveal_at,
                "losses": normalized_losses,
            }
        )
    if not normalized:
        raise TemporalP0ControlError("current-risk assessment requires loss rows")

    assessment_rows: list[dict[str, Any]] = []
    assessment_seen: set[str] = set()
    previous_time = -math.inf
    for index, raw in enumerate(_rows(assessments, "assessments")):
        assessment_id = _identifier(raw.get("assessment_id"), f"assessments[{index}].assessment_id")
        if assessment_id in assessment_seen:
            raise TemporalP0ControlError(f"duplicate assessment_id: {assessment_id}")
        assessment_seen.add(assessment_id)
        assessment_at = _timestamp(raw.get("assessment_at"), f"assessment {assessment_id}.assessment_at")
        if assessment_at <= previous_time:
            raise TemporalP0ControlError("assessment timestamps must be strictly increasing")
        previous_time = assessment_at
        assessment_rows.append({"assessment_id": assessment_id, "assessment_at": assessment_at})
    if not assessment_rows:
        raise TemporalP0ControlError("at least one assessment is required")

    results: list[dict[str, Any]] = []
    required_periods = max(max(adaptive_periods), fixed_window_periods, recent_window_periods)
    for assessment in assessment_rows:
        matured = [row for row in normalized if row["reveal_at"] <= assessment["assessment_at"]]
        periods = sorted({row["period_index"] for row in matured})
        if len(periods) < required_periods:
            raise TemporalP0ControlError(
                f"assessment {assessment['assessment_id']} has {len(periods)} matured periods; "
                f"{required_periods} required"
            )
        delta_prime = confidence_delta / (3.0 * len(periods) * len(model_hashes))
        adaptive_models: dict[str, Any] = {}
        for model_id in sorted(model_hashes):
            table = _hhw_window_table(
                matured,
                model_id,
                adaptive_periods,
                loss_range=loss_bound,
                delta_prime=delta_prime,
                min_samples=min_samples_per_window,
            )
            selected_window = min(
                table,
                key=lambda row: (row["selection_objective"], row["window_periods"]),
            )
            adaptive_models[model_id] = {
                "selected_window_periods": selected_window["window_periods"],
                "estimated_current_risk": selected_window["mean_loss"],
                "window_table": table,
            }

        def control(period_count: int | None) -> dict[str, Any]:
            estimates: dict[str, float] = {}
            for model_id in sorted(model_hashes):
                values = (
                    [float(row["losses"][model_id]) for row in matured]
                    if period_count is None
                    else _period_window_values(matured, model_id, period_count)
                )
                if len(values) < min_samples_per_window:
                    raise TemporalP0ControlError(
                        f"sparse control window for model={model_id}, samples={len(values)}"
                    )
                estimates[model_id] = _mean(values)
            selected_model = min(estimates, key=lambda model_id: (estimates[model_id], model_id))
            return {"selected_model_id": selected_model, "estimated_risks": estimates}

        adaptive_selected = min(
            adaptive_models,
            key=lambda model_id: (
                adaptive_models[model_id]["estimated_current_risk"], model_id
            ),
        )
        results.append(
            {
                **assessment,
                "matured_case_count": len(matured),
                "matured_period_count": len(periods),
                "matured_case_ids_hash": _sha256_json(sorted(row["case_id"] for row in matured)),
                "adaptive": {
                    "selected_model_id": adaptive_selected,
                    "model_assessments": adaptive_models,
                },
                "fixed_window_control": control(fixed_window_periods),
                "expanding_window_control": control(None),
                "recent_window_control": control(recent_window_periods),
            }
        )

    strategy_paths = {
        "adaptive": [row["adaptive"]["selected_model_id"] for row in results],
        "fixed_window_control": [
            row["fixed_window_control"]["selected_model_id"] for row in results
        ],
        "expanding_window_control": [
            row["expanding_window_control"]["selected_model_id"] for row in results
        ],
        "recent_window_control": [
            row["recent_window_control"]["selected_model_id"] for row in results
        ],
    }
    switch_report = {
        name: {
            "selection_path": path,
            "switch_count": sum(left != right for left, right in zip(path, path[1:])),
        }
        for name, path in strategy_paths.items()
    }

    return _receipt(
        {
            "schema_version": SCHEMA_VERSION,
            "control": "FROZEN_POOL_ADAPTIVE_CURRENT_RISK",
            "method": "HHW_INSPIRED_EMPIRICAL_BERNSTEIN_GL_WINDOW",
            "paper_faithful_hhw_algorithm_and_theorem": False,
            "scope": "CURRENT_RISK_ASSESSMENT_AND_FINITE_FROZEN_POOL_SELECTION_ONLY",
            "cumulative_loss_guarantee": False,
            "best_fixed_candidate_guarantee": False,
            "switching_or_dynamic_regret_guarantee": False,
            "switch_counts_operational_only": True,
            "models_frozen": True,
            "matured_labels_only": True,
            "loss_upper_bound": loss_bound,
            "delta": confidence_delta,
            "adaptive_window_periods": adaptive_periods,
            "fixed_window_periods": fixed_window_periods,
            "recent_window_periods": recent_window_periods,
            "min_samples_per_window": min_samples_per_window,
            "model_hashes": dict(sorted(model_hashes.items())),
            "model_pool_hash": _sha256_json(dict(sorted(model_hashes.items()))),
            "loss_rows_hash": _sha256_json(normalized),
            "assessment_plan_hash": _sha256_json(assessment_rows),
            "assessment_results": results,
            "switch_report": switch_report,
        }
    )


__all__ = [
    "SCHEMA_VERSION",
    "TemporalP0ControlError",
    "assess_frozen_pool_current_risk",
    "audit_planted_null_first_locks",
    "calibrate_accumulated_accuracy_gap",
    "run_delayed_label_aci",
]
