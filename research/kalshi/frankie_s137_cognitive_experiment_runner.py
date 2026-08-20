#!/usr/bin/env python3
"""Paired freeze-before-reveal runner for Frankie's ten S137 SHADOW arms.

The runner owns experiment order and auditability, not grading policy.  Callers
provide a causal CURRENT-FRANKIE packet, metered model invocations, target reveal,
and an external grader.  Both forecasts are durably represented by hashes before
the target may be revealed.  The resulting rows feed the locked cognitive gate.
"""
from __future__ import annotations

import dataclasses
import json
import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

import frankie_s135_current_runtime as s135
from frankie_cognition import CognitiveContractError, sha256_json
from frankie_cognitive_experiments import (
    BUDGET_DIMENSIONS,
    EXPERIMENT_BY_ID,
    MIN_EVALUATION_CASES,
    MIN_FAIL_TO_PASS_CASES,
    MIN_OBSERVED_STRATUM_CASES,
    REQUIRED_STRATA,
    evaluate_shadow_candidate,
)
from frankie_s137_cognitive_runtime import CognitiveCandidateRuntime, runtime_for

VERSION = "S137_COGNITIVE_PAIRED_RUNNER_V1"
ARMS = ("baseline", "candidate")


class PairedRunError(RuntimeError):
    """Fail-closed paired experiment error."""


@dataclass(frozen=True)
class BudgetUsage:
    model_calls: float
    input_tokens: float
    output_tokens: float
    tool_queries: float
    storage_bytes: float
    wall_clock_ms: float

    def __post_init__(self) -> None:
        for name in BUDGET_DIMENSIONS:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise PairedRunError(f"budget {name} must be numeric")
            if not math.isfinite(float(value)) or float(value) < 0:
                raise PairedRunError(f"budget {name} must be finite and non-negative")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "BudgetUsage":
        if not isinstance(raw, Mapping):
            raise PairedRunError("metered invocation budget must be an object")
        missing = sorted(set(BUDGET_DIMENSIONS) - set(raw))
        extra = sorted(set(raw) - set(BUDGET_DIMENSIONS))
        if missing or extra:
            raise PairedRunError(f"budget dimensions mismatch; missing={missing}, extra={extra}")
        return cls(**{name: raw[name] for name in BUDGET_DIMENSIONS})

    def as_dict(self) -> dict[str, float]:
        return {name: float(getattr(self, name)) for name in BUDGET_DIMENSIONS}


@dataclass(frozen=True)
class InvocationResult:
    output: Mapping[str, Any]
    budget: BudgetUsage

    def __post_init__(self) -> None:
        if not isinstance(self.output, Mapping):
            raise PairedRunError("model invocation output must be an object")


@dataclass(frozen=True)
class ArmGrade:
    passed: bool
    metrics: Mapping[str, float]
    catastrophic: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.passed, bool) or not isinstance(self.catastrophic, bool):
            raise PairedRunError("grader pass/catastrophic states must be boolean")
        if not isinstance(self.metrics, Mapping):
            raise PairedRunError("grader metrics must be an object")
        for name, value in self.metrics.items():
            if not str(name).strip() or isinstance(value, bool) or not isinstance(value, (int, float)):
                raise PairedRunError("grader metrics require non-empty names and numeric values")
            if not math.isfinite(float(value)):
                raise PairedRunError(f"grader metric {name} must be finite")


@dataclass(frozen=True)
class PairedCaseSpec:
    case_id: str
    specialist: str
    strata: Mapping[str, str]
    task: str = "day_forecast"
    protected: bool = False
    arm_order: tuple[str, str] = ARMS

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise PairedRunError("paired case_id must be non-empty")
        if self.specialist.upper() not in set("ABCDE"):
            raise PairedRunError("paired case specialist must be A-E")
        if self.task not in {"day_forecast", "weekend_bridge"}:
            raise PairedRunError("paired case task must be day_forecast or weekend_bridge")
        if set(self.arm_order) != set(ARMS) or len(self.arm_order) != 2:
            raise PairedRunError("arm_order must contain baseline and candidate exactly once")
        if not isinstance(self.protected, bool):
            raise PairedRunError("protected must be boolean")
        if not isinstance(self.strata, Mapping):
            raise PairedRunError("paired case strata must be an object")
        missing = [name for name in REQUIRED_STRATA if not str(self.strata.get(name) or "").strip()]
        if missing:
            raise PairedRunError(f"paired case missing strata: {missing}")


@dataclass(frozen=True)
class FrozenArmArtifact:
    arm: str
    canonical_json: str
    sha256: str

    @classmethod
    def create(cls, arm: str, output: Mapping[str, Any]) -> "FrozenArmArtifact":
        if arm not in ARMS:
            raise PairedRunError(f"unknown paired arm: {arm}")
        text = json.dumps(dict(output), sort_keys=True, separators=(",", ":"), allow_nan=False)
        return cls(arm=arm, canonical_json=text, sha256=sha256_json(dict(output)))

    def thaw_verified(self) -> dict[str, Any]:
        value = json.loads(self.canonical_json)
        if not isinstance(value, dict) or sha256_json(value) != self.sha256:
            raise PairedRunError(f"frozen {self.arm} artifact hash mismatch")
        return value


@dataclass(frozen=True)
class PairedCaseResult:
    row: Mapping[str, Any]
    audit: Mapping[str, Any]


PacketFn = Callable[[PairedCaseSpec], tuple[str, Mapping[str, Any]]]
InvokeFn = Callable[[PairedCaseSpec, str, str, Mapping[str, Any]], InvocationResult]
RevealFn = Callable[[PairedCaseSpec], Mapping[str, Any]]
GradeFn = Callable[[PairedCaseSpec, str, Mapping[str, Any], Mapping[str, Any]], ArmGrade]
BaselineValidateFn = Callable[[Mapping[str, Any], str, str], None]


def _default_baseline_validate(output: Mapping[str, Any], specialist: str, task: str) -> None:
    s135.validate_owner_output(output, specialist, task=task)


def _validate_grade_metrics(candidate_id: str, grade: ArmGrade, arm: str) -> None:
    required = {rule.name for rule in EXPERIMENT_BY_ID[candidate_id].metric_rules}
    observed = set(grade.metrics)
    if observed != required:
        raise PairedRunError(
            f"{arm} grader metrics mismatch for {candidate_id}; "
            f"missing={sorted(required - observed)}, extra={sorted(observed - required)}"
        )


def run_paired_case(
    candidate_id: str,
    case: PairedCaseSpec,
    *,
    packet_fn: PacketFn,
    invoke_fn: InvokeFn,
    reveal_fn: RevealFn,
    grade_fn: GradeFn,
    baseline_validate_fn: BaselineValidateFn = _default_baseline_validate,
    candidate_runtime: CognitiveCandidateRuntime | None = None,
) -> PairedCaseResult:
    """Run one pair.  No reveal callback occurs unless both arms validate and freeze."""
    if candidate_id not in EXPERIMENT_BY_ID:
        raise PairedRunError(f"unknown cognitive candidate: {candidate_id}")
    runtime = candidate_runtime or runtime_for(candidate_id)
    if runtime.candidate_id != candidate_id:
        raise PairedRunError("candidate runtime does not match requested arm")
    runtime.install()

    control_prompt, control_packet_raw = packet_fn(case)
    if not isinstance(control_prompt, str) or not control_prompt.strip():
        raise PairedRunError("packet callback returned an empty control prompt")
    if not isinstance(control_packet_raw, Mapping) or not control_packet_raw:
        raise PairedRunError("packet callback returned an empty control packet")
    control_packet = dict(control_packet_raw)
    control_packet_hash = sha256_json(control_packet)
    candidate_prompt, candidate_packet = runtime.attach_to_frozen_control(
        control_prompt,
        control_packet,
        specialist=case.specialist,
        task=case.task,
    )
    stripped = dict(candidate_packet)
    candidate_contract = stripped.pop("s137_cognitive_candidate", None)
    if not isinstance(candidate_contract, Mapping):
        raise PairedRunError("candidate packet is missing its S137 contract")
    if stripped != control_packet or sha256_json(stripped) != control_packet_hash:
        raise PairedRunError("candidate changed the frozen S135 information set")

    prompts = {"baseline": control_prompt, "candidate": candidate_prompt}
    packets = {"baseline": control_packet, "candidate": candidate_packet}
    frozen: dict[str, FrozenArmArtifact] = {}
    budgets: dict[str, BudgetUsage] = {}
    events: list[dict[str, Any]] = []
    for arm in case.arm_order:
        invocation = invoke_fn(case, arm, prompts[arm], packets[arm])
        if not isinstance(invocation, InvocationResult):
            raise PairedRunError("invoke callback must return InvocationResult")
        output = dict(invocation.output)
        if arm == "baseline":
            baseline_validate_fn(output, case.specialist, case.task)
        else:
            runtime.validate_owner_output(output, case.specialist, task=case.task)
        frozen[arm] = FrozenArmArtifact.create(arm, output)
        budgets[arm] = invocation.budget
        events.append({"event": "ARM_FROZEN", "arm": arm, "sha256": frozen[arm].sha256})

    if set(frozen) != set(ARMS):
        raise PairedRunError("target reveal requires both paired arms frozen")
    actual = reveal_fn(case)
    if not isinstance(actual, Mapping):
        raise PairedRunError("reveal callback must return an object")
    actual_hash = sha256_json(dict(actual))
    events.append({
        "event": "TARGET_REVEALED_AFTER_BOTH_ARMS",
        "actual_sha256": actual_hash,
        "frozen_arm_hashes": {arm: frozen[arm].sha256 for arm in ARMS},
    })

    grades: dict[str, ArmGrade] = {}
    for arm in ARMS:
        grades[arm] = grade_fn(case, arm, frozen[arm].thaw_verified(), dict(actual))
        if not isinstance(grades[arm], ArmGrade):
            raise PairedRunError("grade callback must return ArmGrade")
        _validate_grade_metrics(candidate_id, grades[arm], arm)

    row = {
        "case_id": case.case_id,
        "baseline_pass": grades["baseline"].passed,
        "candidate_pass": grades["candidate"].passed,
        "candidate_catastrophic": grades["candidate"].catastrophic,
        "protected": case.protected,
        "strata": {name: str(case.strata[name]) for name in REQUIRED_STRATA},
        "baseline_budget": budgets["baseline"].as_dict(),
        "candidate_budget": budgets["candidate"].as_dict(),
        "baseline_metrics": {name: float(value) for name, value in grades["baseline"].metrics.items()},
        "candidate_metrics": {name: float(value) for name, value in grades["candidate"].metrics.items()},
    }
    audit_core = {
        "version": VERSION,
        "case_id": case.case_id,
        "candidate_id": candidate_id,
        "arm_order": list(case.arm_order),
        "control_packet_hash": control_packet_hash,
        "candidate_underlay_hash": sha256_json(stripped),
        "same_information_set": True,
        "candidate_contract_hash": sha256_json(candidate_contract),
        "freeze_before_reveal": True,
        "events": events,
        "execution_enabled": False,
        "automatic_apply": False,
    }
    return PairedCaseResult(row=row, audit={**audit_core, "audit_hash": sha256_json(audit_core)})


def run_paired_suite(
    candidate_id: str,
    cases: Sequence[PairedCaseSpec],
    *,
    packet_fn: PacketFn,
    invoke_fn: InvokeFn,
    reveal_fn: RevealFn,
    grade_fn: GradeFn,
    baseline_validate_fn: BaselineValidateFn = _default_baseline_validate,
    budget_tolerance: float = 0.02,
) -> dict[str, Any]:
    """Run an isolated candidate cohort and apply the locked component gate."""
    if not cases:
        raise PairedRunError("paired candidate suite requires cases")
    if len({case.case_id for case in cases}) != len(cases):
        raise PairedRunError("paired candidate suite case ids must be unique")
    runtime = runtime_for(candidate_id)
    results = [
        run_paired_case(
            candidate_id,
            case,
            packet_fn=packet_fn,
            invoke_fn=invoke_fn,
            reveal_fn=reveal_fn,
            grade_fn=grade_fn,
            baseline_validate_fn=baseline_validate_fn,
            candidate_runtime=runtime,
        )
        for case in cases
    ]
    try:
        evaluation = evaluate_shadow_candidate(
            candidate_id,
            [result.row for result in results],
            budget_tolerance=budget_tolerance,
        )
    except CognitiveContractError as exc:
        raise PairedRunError(f"locked cognitive evaluator rejected paired rows: {exc}") from exc
    core = {
        "version": VERSION,
        "candidate_id": candidate_id,
        "cases": len(results),
        "case_audits": [result.audit for result in results],
        "rows": [result.row for result in results],
        "evaluation": evaluation,
        "performance_evidence": True,
        "promotion_authority": "NONE",
        "execution_enabled": False,
        "automatic_apply": False,
    }
    return {**core, "suite_hash": sha256_json(core)}


def runner_manifest() -> dict[str, Any]:
    core = {
        "version": VERSION,
        "candidate_ids": list(EXPERIMENT_BY_ID),
        "arms": list(ARMS),
        "required_ordering": "BOTH_ARMS_FROZEN_BEFORE_TARGET_REVEAL",
        "same_information_set_required": True,
        "exact_metering_required": list(BUDGET_DIMENSIONS),
        "minimum_evidence": {
            "cases": MIN_EVALUATION_CASES,
            "fail_to_pass": MIN_FAIL_TO_PASS_CASES,
            "observed_stratum_cases": MIN_OBSERVED_STRATUM_CASES,
        },
        "locked_evaluator": "frankie_cognitive_experiments.evaluate_shadow_candidate",
        "component_pass_next_gate": "UNTOUCHED_FORWARD_SHADOW",
        "promotion_authority": "NONE",
        "execution_enabled": False,
        "automatic_apply": False,
    }
    return {**core, "manifest_hash": sha256_json(core)}


if __name__ == "__main__":
    print(json.dumps(runner_manifest(), indent=2, sort_keys=True))
