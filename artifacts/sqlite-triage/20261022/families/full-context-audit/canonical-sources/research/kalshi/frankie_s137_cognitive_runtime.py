#!/usr/bin/env python3
"""S137 SHADOW-only cognitive-candidate wrapper for CURRENT FRANKIE S135.

Pass an instance from ``runtime_for(candidate_id)`` to the canonical S135 group
runner.  The frozen S135 runtime remains the control.  This wrapper attaches one
candidate contract, requires an evidence-bound cognitive trace, and delegates
all existing forecast/owner validation back to S135.
"""
from __future__ import annotations

import dataclasses
import json
from typing import Any, Mapping

import frankie_s135_current_runtime as s135
from frankie_cognition import (
    COGNITIVE_CONTRACT_VERSION,
    CognitiveContractError,
    sha256_json,
    validate_reasoning_contract,
)
from frankie_cognitive_candidates import (
    TypedEvidenceStore,
    run_deterministic_check,
    validate_react_trace,
)
from frankie_cognitive_p0_loops import (
    execute_faithful_ir,
    run_bounded_react,
    run_chronological_memory_benchmark,
    run_critic_revision,
    run_iterative_structured_reads,
    run_state_aware_working_memory,
)
from frankie_hipporag_p0_retrieval import (
    HippoRAGContractError,
    run_hipporag_shadow_pipeline,
)
from frankie_lats_p0_search import run_bounded_lats_search
from frankie_progress_compress_p0 import (
    ProgressCompressP0Error,
    run_progress_compress_shadow,
)
from frankie_cognitive_experiments import (
    EXPERIMENT_BY_ID,
    IMPLEMENTATION_AUDIT,
    experiment_manifest,
)

VERSION = "S137_COGNITIVE_SHADOW_RUNTIME_V3_PROVISIONAL"

P0_COMPONENT_RUNNERS = {
    "COG02_REACT_EVIDENCE_LOOP": run_bounded_react,
    "COG03_LATS_BOUNDED_PLAN_SEARCH": run_bounded_lats_search,
    "COG04_STRUCTGPT_TYPED_READS": run_iterative_structured_reads,
    "COG05_FAITHFUL_EXECUTABLE_REASONING": execute_faithful_ir,
    "COG06_CRITIC_TOOL_VERIFICATION": run_critic_revision,
    "COG07_MEMORY_AGENT_BENCH": run_chronological_memory_benchmark,
    "COG08_HIPPORAG_ASSOCIATIVE_RETRIEVAL": run_hipporag_shadow_pipeline,
    "COG09_HIAGENT_WORKING_MEMORY": run_state_aware_working_memory,
    "COG10_PROGRESS_COMPRESS_SHADOW_LEARNING": run_progress_compress_shadow,
}


class CognitiveRuntimeError(RuntimeError):
    """Fail-closed candidate-runtime contract error."""


class CognitiveCandidateRuntime:
    """One isolated cognitive experiment arm around the frozen S135 control."""

    base = s135.base
    s133 = s135.s133
    ForecastStop = s135.ForecastStop

    def __init__(self, candidate_id: str):
        experiment = EXPERIMENT_BY_ID.get(candidate_id)
        if experiment is None:
            raise CognitiveRuntimeError(f"unknown S137 cognitive candidate: {candidate_id}")
        self.candidate_id = candidate_id
        self.experiment = experiment
        self._pending_refs: dict[tuple[str, str], set[str]] = {}
        self._pending_catalogs: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def install(self) -> None:
        s135.install()

    @staticmethod
    def _evidence_catalog(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        catalog = []
        for key in sorted(payload):
            if key == "s137_cognitive_candidate":
                continue
            value = payload[key]
            catalog.append(
                {
                    "ref_id": f"packet:{key}",
                    "source": f"CURRENT_FRANKIE_PACKET.{key}",
                    "content_hash": sha256_json(value),
                    "immutable": True,
                    "immutable_for_run": True,
                    "status": "ACTIVE",
                }
            )
        if not catalog:
            raise CognitiveRuntimeError("S137 refuses an empty CURRENT FRANKIE packet")
        return catalog

    def _attach(
        self,
        prompt: str,
        payload: Mapping[str, Any],
        *,
        specialist: str,
        task: str,
    ) -> tuple[str, dict[str, Any]]:
        out = dict(payload)
        catalog = self._evidence_catalog(out)
        refs = {str(record["ref_id"]) for record in catalog}
        key = (str(specialist).upper(), task)
        if key in self._pending_refs:
            raise CognitiveRuntimeError(
                f"S137 candidate packet for {key[0]}/{task} was not validated before replacement"
            )
        self._pending_refs[key] = refs
        self._pending_catalogs[key] = json.loads(
            json.dumps(catalog, sort_keys=True, separators=(",", ":"))
        )
        contract = {
            "version": VERSION,
            "contract_version": COGNITIVE_CONTRACT_VERSION,
            "candidate_id": self.candidate_id,
            "rank": self.experiment.rank,
            "paper": self.experiment.paper,
            "venue": self.experiment.venue,
            "component": self.experiment.component,
            "hypothesis": self.experiment.hypothesis,
            "intervention": self.experiment.intervention,
            "falsifiers": list(self.experiment.falsifiers),
            "metric_rules": [dataclasses.asdict(rule) for rule in self.experiment.metric_rules],
            "implementation_audit": IMPLEMENTATION_AUDIT[self.candidate_id],
            "evidence_catalog": catalog,
            "evidence_catalog_hash": sha256_json(catalog),
            "required_output": {
                "cognitive_evaluation": {
                    "candidate_id": self.candidate_id,
                    "reasoning_steps": [
                        {
                            "step_id": "S1",
                            "action": "OBSERVE | RETRIEVE | REASON | VERIFY | ABSTAIN",
                            "claim": "bounded claim",
                            "evidence_refs": ["exact packet ref ids only"],
                            "depends_on": ["earlier step ids only"],
                            "status": "SUPPORTED | CONTRADICTED | INCONCLUSIVE | NOT_APPLICABLE",
                        }
                    ],
                    "uncertainty": {
                        "level": "LOW | MEDIUM | HIGH | UNKNOWN",
                        "drivers": ["specific drivers"],
                        "calibrated_probability": "number in [0,1] or null",
                    },
                }
            },
            "authority": "SHADOW_ONLY",
            "execution_enabled": False,
            "automatic_apply": False,
        }
        out["s137_cognitive_candidate"] = contract
        addendum = (
            "\n\nS137 COGNITIVE SHADOW CANDIDATE\n"
            "Apply exactly one candidate contract below. Preserve every CURRENT FRANKIE owner, "
            "causal, outcome-wall, and output rule. Add cognitive_evaluation to the existing output. "
            "Cite only exact packet evidence ref ids. A trace is an auditable claim graph, not proof, "
            "authority, or permission. Do not trade, execute, promote, write memory, or modify gates.\n"
            + json.dumps(contract, indent=2, sort_keys=True)
        )
        return prompt.rstrip() + addendum, out

    def packet(self, template: str, gid: str, day: str, spec: str, namespace: str, **kwargs):
        prompt, payload = s135.packet(template, gid, day, spec, namespace, **kwargs)
        task = "weekend_bridge" if spec == "A" and template == "BLD-2" else "day_forecast"
        return self._attach(prompt, payload, specialist=spec, task=task)

    def packet_sequential(self, template: str, gid: str, day: str, spec: str, namespace: str, **kwargs):
        prompt, payload = s135.packet_sequential(template, gid, day, spec, namespace, **kwargs)
        task = "weekend_bridge" if spec == "A" and template == "BLD-2" else "day_forecast"
        return self._attach(prompt, payload, specialist=spec, task=task)

    def attach_to_frozen_control(
        self,
        prompt: str,
        payload: Mapping[str, Any],
        *,
        specialist: str,
        task: str = "day_forecast",
    ) -> tuple[str, dict[str, Any]]:
        """Derive the candidate arm from one already-built S135 control packet.

        Paired experiments must not rebuild the underlying packet independently for
        each arm: a clock, state, or serving change between those builds would be a
        confounder.  This entry attaches the one candidate intervention to the exact
        frozen control information set while leaving the control object untouched.
        """
        if not isinstance(prompt, str) or not prompt.strip():
            raise CognitiveRuntimeError("paired S137 control prompt must be non-empty")
        if not isinstance(payload, Mapping):
            raise CognitiveRuntimeError("paired S137 control packet must be an object")
        return self._attach(prompt, payload, specialist=specialist, task=task)

    def packet_live_rederive(self, open_packet: Mapping[str, Any], *, legal_event_evidence: Mapping[str, Any]):
        return s135.packet_live_rederive(open_packet, legal_event_evidence=legal_event_evidence)

    def validate_owner_output(
        self,
        output: Mapping[str, Any],
        specialist: str,
        *,
        task: str = "day_forecast",
    ) -> None:
        s135.validate_owner_output(output, specialist, task=task)
        key = (str(specialist).upper(), task)
        allowed_refs = self._pending_refs.get(key)
        if allowed_refs is None:
            raise CognitiveRuntimeError(f"S137 output has no pending packet contract for {key[0]}/{task}")
        raw = output.get("cognitive_evaluation")
        if not isinstance(raw, Mapping):
            raise CognitiveRuntimeError("S137 candidate output missing cognitive_evaluation")
        if raw.get("candidate_id") != self.candidate_id:
            raise CognitiveRuntimeError("S137 output candidate id does not match the active arm")
        try:
            steps, _uncertainty, _trace_hash = validate_reasoning_contract(
                raw,
                allowed_evidence_refs=allowed_refs,
            )
            if self.candidate_id == "COG02_REACT_EVIDENCE_LOOP":
                validate_react_trace(steps)
            if self.candidate_id == "COG04_STRUCTGPT_TYPED_READS":
                catalog = self._pending_catalogs.get(key)
                if catalog is None:
                    raise CognitiveContractError("typed-read catalog is missing")
                store = TypedEvidenceStore({
                    "contract_version": COGNITIVE_CONTRACT_VERSION,
                    "evidence_catalog": catalog,
                    "evidence_catalog_hash": sha256_json(catalog),
                })
                cited_refs = sorted({
                    ref for step in steps for ref in step.evidence_refs
                })
                store.read(cited_refs, max_records=min(32, len(cited_refs)))
            if self.candidate_id in {
                "COG05_FAITHFUL_EXECUTABLE_REASONING",
                "COG06_CRITIC_TOOL_VERIFICATION",
            }:
                checks = raw.get("deterministic_checks")
                if not isinstance(checks, list) or not checks:
                    raise CognitiveContractError("candidate requires deterministic_checks")
                for spec in checks:
                    if not isinstance(spec, Mapping):
                        raise CognitiveContractError("deterministic check must be an object")
                    refs = spec.get("evidence_refs")
                    if not isinstance(refs, list) or set(refs) - allowed_refs:
                        raise CognitiveContractError("deterministic check cites unknown packet evidence")
                    result = run_deterministic_check(spec)
                    if result["status"] != "SUPPORTED":
                        raise CognitiveContractError(
                            f"final candidate failed deterministic check {result['check_id']}"
                        )
        except CognitiveContractError as exc:
            raise CognitiveRuntimeError(f"S137 candidate cognitive contract failed: {exc}") from exc
        del self._pending_refs[key]
        del self._pending_catalogs[key]

    def contract_manifest(self) -> dict[str, Any]:
        registry = experiment_manifest()
        core = {
            "version": VERSION,
            "candidate_id": self.candidate_id,
            "experiment_manifest_hash": registry["manifest_hash"],
            "control_runtime": s135.STACK_VERSION,
            "authority": "SHADOW_ONLY",
            "execution_enabled": False,
            "automatic_apply": False,
        }
        return {**core, "runtime_hash": sha256_json(core)}

    def run_p0_component(self, **kwargs: Any) -> dict[str, Any]:
        """Run this arm's bounded P0 component through an explicit SHADOW hook.

        The injected callbacks and budgets remain caller-owned and must satisfy
        the component's fail-closed contract.  This hook is not invoked by the
        standard S135 group runner and grants no execution or apply authority.
        """
        runner = P0_COMPONENT_RUNNERS.get(self.candidate_id)
        if runner is None:
            raise CognitiveRuntimeError(
                f"{self.candidate_id} has no bounded P0 runtime component"
            )
        try:
            result = runner(**kwargs)
        except (CognitiveContractError, HippoRAGContractError, ProgressCompressP0Error) as exc:
            raise CognitiveRuntimeError(
                f"S137 P0 component failed: {exc}"
            ) from exc
        if not isinstance(result, dict):
            raise CognitiveRuntimeError("S137 P0 component returned a non-object")
        return result


def runtime_for(candidate_id: str) -> CognitiveCandidateRuntime:
    return CognitiveCandidateRuntime(candidate_id)


if __name__ == "__main__":
    print(json.dumps({candidate_id: runtime_for(candidate_id).contract_manifest() for candidate_id in EXPERIMENT_BY_ID}, indent=2, sort_keys=True))
