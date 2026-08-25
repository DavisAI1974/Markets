#!/usr/bin/env python3
"""Fail-closed two-lane orchestration for the October Frankie experiment.

Exactly one S135 control lane and one all-together provisional lane run before
answer reveal on an identical causal-prefix binding.  The provisional bundle is
available only to the combined lane.  Both lanes retain independent, lane-tagged,
append-only provider, retrieval, helper, reasoning, probability, candidate, and
lock/no-lock records.  Scientific comparison remains sealed until every declared
prefix has complete immutable artifacts in both ledgers.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from research.kalshi.frankie_full_stack_runtime_adapter_20260824 import (
    AdapterRuntimeError,
    DurableJsonlLedger,
    FullStackRuntimeAdapter,
    PrefixRuntimeResult,
    ResponsesClient,
)
from research.kalshi.frankie_full_stack_runtime_contracts_20260824 import (
    CausalPrefixBinding,
    LedgerKind,
    LedgerRecord,
    RetrievalReceipt,
    RuntimeEventSink,
    ToolCallReceipt,
)


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RESERVED_CONTEXT_KEY = "provisional_combined_context"
GLOBAL_FREEZE_NAME = "GLOBAL_EXPERIMENT_FREEZE"
COMBINED_COMPONENTS = (
    "S137_COGNITIVE_RUNTIME",
    "HIPPORAG_RETRIEVAL",
    "TEMPORAL_GRAPH",
    "LATS_BOUNDED_SEARCH",
    "WORKING_MEMORY",
    "PROGRESS_COMPRESSION",
    "META_LOOP",
    "PROVISIONAL_V4_ENGINEERING_CANDIDATE",
)


class PairedLaneError(ValueError):
    """A two-lane isolation, lifecycle, or freeze invariant failed closed."""


class LaneId(str, Enum):
    S135_CONTROL = "S135_CONTROL"
    FULL_PROVISIONAL_COMBINED = "FULL_PROVISIONAL_COMBINED"


class ComponentLifecycleStage(str, Enum):
    PRE_REVEAL_PREFIX = "PRE_REVEAL_PREFIX"
    POST_EVIDENCE_DIAGNOSTIC = "POST_EVIDENCE_DIAGNOSTIC"


class ComponentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEFERRED_NOT_YET_LAWFUL = "DEFERRED_NOT_YET_LAWFUL"


def _canonical(value: Any, field: str) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError) as exc:
        raise PairedLaneError(f"{field} must be deterministic JSON") from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value, "hash payload").encode()).hexdigest()


def _sha256(value: str, field: str) -> str:
    text = str(value or "").strip().lower()
    if not SHA256_RE.fullmatch(text):
        raise PairedLaneError(f"{field} must be lowercase SHA-256")
    return text


@dataclass(frozen=True)
class ProvisionalComponentReceipt:
    component_id: str
    binding: CausalPrefixBinding
    lifecycle_stage: ComponentLifecycleStage
    executed_stage: ComponentLifecycleStage
    status: ComponentStatus
    context_json: str
    context_hash: str
    authority: str
    can_mutate_brain: bool
    can_share_derived_state: bool
    can_change_primary: bool
    receipt_hash: str

    @classmethod
    def create(
        cls,
        *,
        component_id: str,
        binding: CausalPrefixBinding,
        lifecycle_stage: ComponentLifecycleStage,
        executed_stage: ComponentLifecycleStage,
        status: ComponentStatus,
        context: Mapping[str, Any],
    ) -> "ProvisionalComponentReceipt":
        if component_id not in COMBINED_COMPONENTS:
            raise PairedLaneError("unknown provisional combined component")
        bound = binding.validate()
        if not isinstance(lifecycle_stage, ComponentLifecycleStage) or not isinstance(
            executed_stage, ComponentLifecycleStage
        ):
            raise PairedLaneError("component lifecycle stage is invalid")
        if not isinstance(status, ComponentStatus):
            raise PairedLaneError("component status is invalid")
        if not isinstance(context, Mapping):
            raise PairedLaneError("component context must be an object")
        context_json = _canonical(dict(context), "component context")
        context_hash = hashlib.sha256(context_json.encode()).hexdigest()
        core = {
            "component_id": component_id,
            "binding": bound.identity_payload(),
            "lifecycle_stage": lifecycle_stage.value,
            "executed_stage": executed_stage.value,
            "status": status.value,
            "context_hash": context_hash,
            "authority": "SHADOW_DIAGNOSTIC_ONLY",
            "can_mutate_brain": False,
            "can_share_derived_state": False,
            "can_change_primary": False,
        }
        return cls(
            component_id=component_id,
            binding=bound,
            lifecycle_stage=lifecycle_stage,
            executed_stage=executed_stage,
            status=status,
            context_json=context_json,
            context_hash=context_hash,
            authority="SHADOW_DIAGNOSTIC_ONLY",
            can_mutate_brain=False,
            can_share_derived_state=False,
            can_change_primary=False,
            receipt_hash=_hash(core),
        )

    def validate(self, *, binding: CausalPrefixBinding) -> "ProvisionalComponentReceipt":
        bound = binding.validate()
        if self.component_id not in COMBINED_COMPONENTS:
            raise PairedLaneError("unknown provisional combined component")
        if self.binding != bound:
            raise PairedLaneError("component does not use the identical causal prefix")
        if self.authority != "SHADOW_DIAGNOSTIC_ONLY":
            raise PairedLaneError("provisional component authority must remain shadow diagnostic")
        if self.can_mutate_brain:
            raise PairedLaneError("provisional component cannot mutate brain")
        if self.can_share_derived_state:
            raise PairedLaneError("provisional component cannot share derived state")
        if self.can_change_primary:
            raise PairedLaneError("provisional component cannot change primary")
        if self.component_id == "META_LOOP":
            if (
                self.lifecycle_stage is not ComponentLifecycleStage.POST_EVIDENCE_DIAGNOSTIC
                or self.executed_stage is not ComponentLifecycleStage.PRE_REVEAL_PREFIX
                or self.status is not ComponentStatus.DEFERRED_NOT_YET_LAWFUL
            ):
                raise PairedLaneError("meta-loop must remain deferred until post-evidence")
        elif (
            self.lifecycle_stage is not ComponentLifecycleStage.PRE_REVEAL_PREFIX
            or self.executed_stage is not ComponentLifecycleStage.PRE_REVEAL_PREFIX
            or self.status is not ComponentStatus.ACTIVE
        ):
            raise PairedLaneError("pre-reveal provisional component is not lawfully active")
        try:
            context = json.loads(self.context_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise PairedLaneError("component context is invalid JSON") from exc
        if not isinstance(context, dict) or _canonical(context, "component context") != self.context_json:
            raise PairedLaneError("component context is not canonical")
        if hashlib.sha256(self.context_json.encode()).hexdigest() != self.context_hash:
            raise PairedLaneError("component context hash drift")
        core = {
            "component_id": self.component_id,
            "binding": self.binding.identity_payload(),
            "lifecycle_stage": self.lifecycle_stage.value,
            "executed_stage": self.executed_stage.value,
            "status": self.status.value,
            "context_hash": self.context_hash,
            "authority": self.authority,
            "can_mutate_brain": self.can_mutate_brain,
            "can_share_derived_state": self.can_share_derived_state,
            "can_change_primary": self.can_change_primary,
        }
        if _hash(core) != _sha256(self.receipt_hash, "component receipt_hash"):
            raise PairedLaneError("component receipt hash drift")
        return self


@dataclass(frozen=True)
class LaneRuntime:
    lane_id: LaneId
    client: ResponsesClient
    ledger: DurableJsonlLedger
    event_sink: RuntimeEventSink
    tool_calls: tuple[ToolCallReceipt, ...]
    retrievals: tuple[RetrievalReceipt, ...]


@dataclass(frozen=True)
class PairedLaneEvent:
    name: str
    run_id: str
    causal_prefix_hash: str
    details_json: str
    event_hash: str

    @classmethod
    def create(
        cls,
        *,
        name: str,
        binding: CausalPrefixBinding,
        details: Mapping[str, Any],
    ) -> "PairedLaneEvent":
        if name not in {
            "PAIRED_LANE_STARTED",
            "PROVISIONAL_COMPONENT_BOUND",
            "IDENTICAL_PREFIX_PROVED",
            "PAIRED_LANE_PREFIX_COMPLETE",
            "GLOBAL_EXPERIMENT_FROZEN",
            "POST_EVIDENCE_DIAGNOSTIC_APPENDED",
            "PAIRED_LANE_ERROR",
        }:
            raise PairedLaneError("unknown paired-lane event")
        for key in details:
            if any(term in str(key).lower() for term in ("secret", "token", "api_key", "password")):
                raise PairedLaneError("secret-bearing paired-lane event field is forbidden")
        payload = _canonical(dict(details), "paired-lane event details")
        core = {
            "name": name,
            "run_id": binding.run_id,
            "causal_prefix_hash": binding.causal_prefix_hash,
            "details_json": payload,
        }
        return cls(name, binding.run_id, binding.causal_prefix_hash, payload, _hash(core))


class PairedLaneEventSink:
    def __init__(self) -> None:
        self.events: list[PairedLaneEvent] = []

    def emit(self, event: PairedLaneEvent) -> None:
        self.events.append(event)


class _LaneTaggedLedger:
    """Duck-typed durable ledger view that tags every adapter append."""

    def __init__(self, runtime: LaneRuntime) -> None:
        self._ledger = runtime.ledger
        self.lane_id = runtime.lane_id
        self.run_id = runtime.ledger.run_id

    def snapshot(self) -> tuple[LedgerRecord, ...]:
        return self._ledger.snapshot()

    def append(
        self,
        *,
        kind: LedgerKind,
        binding: CausalPrefixBinding,
        content: Mapping[str, Any],
    ) -> LedgerRecord:
        tagged = dict(content)
        existing = tagged.get("lane_id")
        if existing is not None and existing != self.lane_id.value:
            raise PairedLaneError("ledger content contains a conflicting lane tag")
        tagged["lane_id"] = self.lane_id.value
        if kind in {LedgerKind.LOCK, LedgerKind.NO_LOCK}:
            tagged["lock_authority"] = (
                "S135_PRIMARY"
                if self.lane_id == LaneId.S135_CONTROL
                else "SHADOW_ONLY"
            )
            tagged["first_lock_immutable"] = True
        return self._ledger.append(kind=kind, binding=binding, content=tagged)


@dataclass(frozen=True)
class IdenticalPrefixProof:
    prefix_hash: str
    state_prefix_hash: str
    knowledge_manifest_hash: str
    causal_cutoff: float
    control_final_ledger_hash: str
    combined_final_ledger_hash: str
    proved: bool
    proof_hash: str


@dataclass(frozen=True)
class PairedPrefixRun:
    lane_ids: tuple[LaneId, LaneId]
    primary_lane: LaneId
    control: PrefixRuntimeResult
    combined: PrefixRuntimeResult
    control_lock_authority: str
    combined_lock_authority: str
    component_receipt_hashes: Mapping[str, str]
    identical_prefix_proof: IdenticalPrefixProof
    answer_revealed: bool


@dataclass(frozen=True)
class GlobalExperimentFreezeReceipt:
    freeze_name: str
    completed_prefix_hashes: tuple[str, ...]
    roster_hash: str
    control_ledger_hash: str
    combined_ledger_hash: str
    step1_sealed: bool
    comparison_allowed: bool
    answer_revealed: bool
    receipt_hash: str


@dataclass(frozen=True)
class ComparisonManifest:
    lanes: tuple[LaneId, LaneId]
    control_lane: LaneId
    combined_lane: LaneId
    scientific_comparison: str
    component_receipt_hashes: Mapping[str, tuple[str, ...]]
    freeze_receipt_hash: str
    predictive_success_claimed: bool
    manifest_hash: str


class PairedLaneOrchestrator:
    """Run and freeze the only lawful control-vs-combined experiment topology."""

    def __init__(
        self,
        *,
        prefix_roster: Sequence[str],
        control: LaneRuntime,
        combined: LaneRuntime,
        event_sink: PairedLaneEventSink,
    ) -> None:
        roster = tuple(_sha256(item, "prefix roster hash") for item in prefix_roster)
        if not roster or len(set(roster)) != len(roster):
            raise PairedLaneError("prefix roster must be non-empty and unique")
        if control.lane_id != LaneId.S135_CONTROL:
            raise PairedLaneError("control runtime must be S135_CONTROL")
        if combined.lane_id != LaneId.FULL_PROVISIONAL_COMBINED:
            raise PairedLaneError("combined runtime must be FULL_PROVISIONAL_COMBINED")
        if control.ledger is combined.ledger or Path(control.ledger.path) == Path(combined.ledger.path):
            raise PairedLaneError("paired lanes require independent ledgers")
        if control.ledger.run_id != combined.ledger.run_id:
            raise PairedLaneError("paired lane ledgers must share one run identity")
        if control.client is combined.client:
            raise PairedLaneError("paired lanes require independent provider clients")
        if {item.retrieval_id for item in control.retrievals} & {
            item.retrieval_id for item in combined.retrievals
        }:
            raise PairedLaneError("paired lanes require independent retrieval receipts")
        self.prefix_roster = roster
        self.control = control
        self.combined = combined
        self.event_sink = event_sink
        self._control_ledger = _LaneTaggedLedger(control)
        self._combined_ledger = _LaneTaggedLedger(combined)
        self._freeze_receipt = self._restore_freeze_receipt()

    def _emit(self, name: str, binding: CausalPrefixBinding, details: Mapping[str, Any]) -> None:
        self.event_sink.emit(PairedLaneEvent.create(name=name, binding=binding, details=details))

    @staticmethod
    def _content(record: LedgerRecord) -> dict[str, Any]:
        try:
            content = json.loads(record.content_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise PairedLaneError("lane ledger content is invalid JSON") from exc
        if not isinstance(content, dict):
            raise PairedLaneError("lane ledger content must be an object")
        return content

    def _restore_freeze_receipt(self) -> GlobalExperimentFreezeReceipt | None:
        def freeze_records(runtime: LaneRuntime) -> list[tuple[LedgerRecord, dict[str, Any]]]:
            rows = []
            for record in runtime.ledger.snapshot():
                content = self._content(record)
                if content.get("record_type") == GLOBAL_FREEZE_NAME:
                    rows.append((record, content))
            return rows

        control_rows = freeze_records(self.control)
        combined_rows = freeze_records(self.combined)
        if not control_rows and not combined_rows:
            return None
        if len(control_rows) != 1 or len(combined_rows) != 1:
            raise PairedLaneError("GLOBAL_EXPERIMENT_FREEZE must exist exactly once in both lanes")
        control_record, control = control_rows[0]
        combined_record, combined = combined_rows[0]
        compared_keys = {
            "record_type",
            "completed_prefix_hashes",
            "roster_hash",
            "control_ledger_hash",
            "combined_ledger_hash",
            "step1_sealed",
            "comparison_allowed",
            "answer_revealed",
            "freeze_receipt_hash",
        }
        if {key: control.get(key) for key in compared_keys} != {
            key: combined.get(key) for key in compared_keys
        }:
            raise PairedLaneError("GLOBAL_EXPERIMENT_FREEZE lane receipts disagree")
        completed = tuple(control.get("completed_prefix_hashes", ()))
        if completed != self.prefix_roster:
            raise PairedLaneError("GLOBAL_EXPERIMENT_FREEZE prefix roster drift")
        roster_hash = _sha256(control.get("roster_hash"), "freeze roster_hash")
        control_hash = _sha256(control.get("control_ledger_hash"), "freeze control_ledger_hash")
        combined_hash = _sha256(control.get("combined_ledger_hash"), "freeze combined_ledger_hash")
        if control_record.prior_record_hash != control_hash:
            raise PairedLaneError("control GLOBAL_EXPERIMENT_FREEZE does not bind its prior ledger hash")
        if combined_record.prior_record_hash != combined_hash:
            raise PairedLaneError("combined GLOBAL_EXPERIMENT_FREEZE does not bind its prior ledger hash")
        if (
            control.get("step1_sealed") is not False
            or control.get("comparison_allowed") is not True
            or control.get("answer_revealed") is not False
        ):
            raise PairedLaneError("GLOBAL_EXPERIMENT_FREEZE lifecycle flags drift")
        core = {
            "freeze_name": GLOBAL_FREEZE_NAME,
            "completed_prefix_hashes": list(completed),
            "roster_hash": roster_hash,
            "control_ledger_hash": control_hash,
            "combined_ledger_hash": combined_hash,
            "step1_sealed": False,
            "comparison_allowed": True,
            "answer_revealed": False,
        }
        receipt_hash = _sha256(control.get("freeze_receipt_hash"), "freeze receipt_hash")
        if _hash(core) != receipt_hash:
            raise PairedLaneError("GLOBAL_EXPERIMENT_FREEZE receipt hash drift")
        return GlobalExperimentFreezeReceipt(
            freeze_name=GLOBAL_FREEZE_NAME,
            completed_prefix_hashes=completed,
            roster_hash=roster_hash,
            control_ledger_hash=control_hash,
            combined_ledger_hash=combined_hash,
            step1_sealed=False,
            comparison_allowed=True,
            answer_revealed=False,
            receipt_hash=receipt_hash,
        )

    def _completed_prefixes(self) -> tuple[str, ...]:
        def marked(runtime: LaneRuntime) -> set[str]:
            found = set()
            for record in runtime.ledger.snapshot():
                content = self._content(record)
                if content.get("record_type") == "PAIRED_LANE_PREFIX_COMPLETE":
                    found.add(record.binding.causal_prefix_hash)
            return found

        complete = marked(self.control) & marked(self.combined)
        return tuple(prefix for prefix in self.prefix_roster if prefix in complete)

    def _validate_bundle(
        self,
        binding: CausalPrefixBinding,
        receipts: Sequence[ProvisionalComponentReceipt],
    ) -> tuple[ProvisionalComponentReceipt, ...]:
        rows = tuple(receipts)
        ids = tuple(item.component_id for item in rows)
        if len(rows) != len(COMBINED_COMPONENTS) or set(ids) != set(COMBINED_COMPONENTS):
            raise PairedLaneError("all provisional components must appear exactly once")
        validated = tuple(item.validate(binding=binding) for item in rows)
        for item in validated:
            if item.component_id != "META_LOOP" and (
                item.lifecycle_stage != ComponentLifecycleStage.PRE_REVEAL_PREFIX
            ):
                raise PairedLaneError("combined prefix components must execute at the lawful lifecycle stage")
        return tuple(sorted(validated, key=lambda item: COMBINED_COMPONENTS.index(item.component_id)))

    @staticmethod
    def _validate_result(
        result: PrefixRuntimeResult,
        *,
        binding: CausalPrefixBinding,
    ) -> None:
        if result.binding != binding:
            raise PairedLaneError("lane result lost the identical causal prefix binding")
        if len(result.helper_packets) != 4 or len(result.invocation_receipts) != 5:
            raise PairedLaneError("each lane must run four helpers plus Frankie")
        if tuple(packet.role.value for packet in result.helper_packets) != (
            "recurrence",
            "extension",
            "timing",
            "context",
        ):
            raise PairedLaneError("lane helper roles are incomplete or reordered")
        synthesis = result.synthesis
        if (
            synthesis.synthesis_owner,
            synthesis.probability_owner,
            synthesis.primary_lock_owner,
        ) != ("FRANKIE", "FRANKIE", "FRANKIE"):
            raise PairedLaneError("Frankie must be the sole synthesis, probability, and lock owner")

    def run_prefix(
        self,
        *,
        binding: CausalPrefixBinding,
        causal_state: Mapping[str, Any],
        component_receipts: Sequence[ProvisionalComponentReceipt],
        answer_revealed: bool,
    ) -> PairedPrefixRun:
        bound = binding.validate()
        if answer_revealed:
            raise PairedLaneError("paired lanes must run pre-answer-reveal")
        if self._freeze_receipt is not None:
            raise PairedLaneError("GLOBAL_EXPERIMENT_FREEZE forbids later prefix runs")
        if bound.run_id != self.control.ledger.run_id:
            raise PairedLaneError("prefix run identity differs from paired ledgers")
        if not isinstance(causal_state, Mapping):
            raise PairedLaneError("causal_state must be an object")
        if RESERVED_CONTEXT_KEY in causal_state:
            raise PairedLaneError("raw causal state contains reserved provisional context")
        complete = self._completed_prefixes()
        expected = self.prefix_roster[len(complete)] if len(complete) < len(self.prefix_roster) else None
        if bound.causal_prefix_hash != expected:
            raise PairedLaneError("prefix is not the next item in the immutable prefix roster")
        bundle = self._validate_bundle(bound, component_receipts)

        self._emit(
            "PAIRED_LANE_STARTED",
            bound,
            {
                "lanes": [item.value for item in (LaneId.S135_CONTROL, LaneId.FULL_PROVISIONAL_COMBINED)],
                "answer_revealed": False,
            },
        )
        components: dict[str, Any] = {}
        for item in bundle:
            components[item.component_id] = {
                "context": json.loads(item.context_json),
                "context_hash": item.context_hash,
                "receipt_hash": item.receipt_hash,
                "lifecycle_stage": item.lifecycle_stage.value,
                "status": item.status.value,
                "authority": item.authority,
            }
            self._combined_ledger.append(
                kind=LedgerKind.INTEGRITY,
                binding=bound,
                content={
                    "record_type": "PROVISIONAL_COMPONENT_BOUND",
                    "component_id": item.component_id,
                    "context_hash": item.context_hash,
                    "receipt_hash": item.receipt_hash,
                    "lifecycle_stage": item.lifecycle_stage.value,
                    "status": item.status.value,
                    "authority": item.authority,
                    "can_mutate_brain": False,
                    "can_share_derived_state": False,
                    "can_change_primary": False,
                },
            )
            self._emit(
                "PROVISIONAL_COMPONENT_BOUND",
                bound,
                {
                    "lane_id": LaneId.FULL_PROVISIONAL_COMBINED.value,
                    "component_id": item.component_id,
                    "receipt_hash": item.receipt_hash,
                },
            )

        base_state = json.loads(_canonical(dict(causal_state), "causal state"))
        control_state = dict(base_state)
        control_state["experiment_lane"] = LaneId.S135_CONTROL.value
        combined_state = dict(base_state)
        combined_state["experiment_lane"] = LaneId.FULL_PROVISIONAL_COMBINED.value
        combined_state[RESERVED_CONTEXT_KEY] = {
            "authority": "SHADOW_DIAGNOSTIC_ONLY",
            "scientific_variant": "ALL_TOGETHER_COMBINED",
            "components": components,
            "can_mutate_brain": False,
            "can_share_derived_state": False,
            "can_change_primary": False,
        }

        try:
            control_result = FullStackRuntimeAdapter(
                client=self.control.client,
                ledger=self._control_ledger,
                event_sink=self.control.event_sink,
            ).run_prefix(
                binding=bound,
                causal_state=control_state,
                tool_calls=self.control.tool_calls,
                retrievals=self.control.retrievals,
            )
            combined_result = FullStackRuntimeAdapter(
                client=self.combined.client,
                ledger=self._combined_ledger,
                event_sink=self.combined.event_sink,
            ).run_prefix(
                binding=bound,
                causal_state=combined_state,
                tool_calls=self.combined.tool_calls,
                retrievals=self.combined.retrievals,
            )
        except AdapterRuntimeError as exc:
            self._emit(
                "PAIRED_LANE_ERROR",
                bound,
                {"phase": "LANE_EXECUTION", "error_type": type(exc).__name__},
            )
            raise PairedLaneError("paired lane provider or persistence execution failed") from exc

        self._validate_result(control_result, binding=bound)
        self._validate_result(combined_result, binding=bound)
        control_ids = {
            item.accepted_response.provider_response_id for item in control_result.invocation_receipts
        }
        combined_ids = {
            item.accepted_response.provider_response_id for item in combined_result.invocation_receipts
        }
        if len(control_ids) != 5 or len(combined_ids) != 5 or control_ids & combined_ids:
            raise PairedLaneError("paired lanes require ten distinct provider response IDs")

        proof_core = {
            "binding": bound.identity_payload(),
            "lanes": [LaneId.S135_CONTROL.value, LaneId.FULL_PROVISIONAL_COMBINED.value],
            "control_final_ledger_hash": control_result.final_ledger_hash,
            "combined_final_ledger_hash": combined_result.final_ledger_hash,
            "proved": True,
        }
        proof = IdenticalPrefixProof(
            prefix_hash=bound.causal_prefix_hash,
            state_prefix_hash=bound.state_prefix_hash,
            knowledge_manifest_hash=bound.knowledge_manifest_hash,
            causal_cutoff=bound.causal_cutoff,
            control_final_ledger_hash=control_result.final_ledger_hash,
            combined_final_ledger_hash=combined_result.final_ledger_hash,
            proved=True,
            proof_hash=_hash(proof_core),
        )
        completion = {
            "record_type": "PAIRED_LANE_PREFIX_COMPLETE",
            "identical_prefix_proof_hash": proof.proof_hash,
            "control_final_ledger_hash": control_result.final_ledger_hash,
            "combined_final_ledger_hash": combined_result.final_ledger_hash,
            "provider_response_ids": {
                "control": sorted(control_ids),
                "combined": sorted(combined_ids),
            },
            "answer_revealed": False,
        }
        self._control_ledger.append(kind=LedgerKind.INTEGRITY, binding=bound, content=completion)
        self._combined_ledger.append(kind=LedgerKind.INTEGRITY, binding=bound, content=completion)
        self._emit("IDENTICAL_PREFIX_PROVED", bound, {"proof_hash": proof.proof_hash})
        self._emit(
            "PAIRED_LANE_PREFIX_COMPLETE",
            bound,
            {
                "completed_prefixes": len(self._completed_prefixes()),
                "total_prefixes": len(self.prefix_roster),
                "proof_hash": proof.proof_hash,
            },
        )
        return PairedPrefixRun(
            lane_ids=(LaneId.S135_CONTROL, LaneId.FULL_PROVISIONAL_COMBINED),
            primary_lane=LaneId.S135_CONTROL,
            control=control_result,
            combined=combined_result,
            control_lock_authority="S135_PRIMARY",
            combined_lock_authority="SHADOW_ONLY",
            component_receipt_hashes={item.component_id: item.receipt_hash for item in bundle},
            identical_prefix_proof=proof,
            answer_revealed=False,
        )

    def _validate_lane_roster_artifacts(self, runtime: LaneRuntime) -> None:
        by_prefix: dict[str, list[LedgerRecord]] = {item: [] for item in self.prefix_roster}
        for record in runtime.ledger.snapshot():
            prefix_hash = record.binding.causal_prefix_hash
            if prefix_hash in by_prefix:
                content = self._content(record)
                if content.get("lane_id") != runtime.lane_id.value:
                    raise PairedLaneError("lane ledger record is missing its immutable lane tag")
                by_prefix[prefix_hash].append(record)
        for prefix_hash, records in by_prefix.items():
            kinds = [record.kind for record in records]
            required = {LedgerKind.REASONING, LedgerKind.PROBABILITY, LedgerKind.CANDIDATE}
            if kinds.count(LedgerKind.HELPER_EVIDENCE) != 4 or not required.issubset(kinds):
                raise PairedLaneError(f"complete prefix roster artifacts missing for {prefix_hash}")
            if kinds.count(LedgerKind.LOCK) + kinds.count(LedgerKind.NO_LOCK) != 1:
                raise PairedLaneError(f"complete prefix roster first lock missing for {prefix_hash}")
            lock = next(
                record for record in records if record.kind in {LedgerKind.LOCK, LedgerKind.NO_LOCK}
            )
            lock_content = self._content(lock)
            expected = "S135_PRIMARY" if runtime.lane_id == LaneId.S135_CONTROL else "SHADOW_ONLY"
            if lock_content.get("lock_authority") != expected or lock_content.get("first_lock_immutable") is not True:
                raise PairedLaneError("lane first-lock authority or immutability drift")

    def freeze_global_experiment(self, *, answer_revealed: bool) -> GlobalExperimentFreezeReceipt:
        if answer_revealed:
            raise PairedLaneError("GLOBAL_EXPERIMENT_FREEZE must occur before answer reveal")
        if self._freeze_receipt is not None:
            raise PairedLaneError("GLOBAL_EXPERIMENT_FREEZE is append-once")
        completed = self._completed_prefixes()
        if completed != self.prefix_roster:
            raise PairedLaneError("GLOBAL_EXPERIMENT_FREEZE requires the complete prefix roster")
        self._validate_lane_roster_artifacts(self.control)
        self._validate_lane_roster_artifacts(self.combined)
        control_hash = self.control.ledger.snapshot()[-1].record_hash
        combined_hash = self.combined.ledger.snapshot()[-1].record_hash
        roster_hash = _hash(list(self.prefix_roster))
        core = {
            "freeze_name": GLOBAL_FREEZE_NAME,
            "completed_prefix_hashes": list(completed),
            "roster_hash": roster_hash,
            "control_ledger_hash": control_hash,
            "combined_ledger_hash": combined_hash,
            "step1_sealed": False,
            "comparison_allowed": True,
            "answer_revealed": False,
        }
        receipt = GlobalExperimentFreezeReceipt(
            freeze_name=GLOBAL_FREEZE_NAME,
            completed_prefix_hashes=completed,
            roster_hash=roster_hash,
            control_ledger_hash=control_hash,
            combined_ledger_hash=combined_hash,
            step1_sealed=False,
            comparison_allowed=True,
            answer_revealed=False,
            receipt_hash=_hash(core),
        )
        last_binding = self.control.ledger.snapshot()[-1].binding
        freeze_content = {
            "record_type": GLOBAL_FREEZE_NAME,
            "completed_prefix_hashes": list(completed),
            "roster_hash": roster_hash,
            "control_ledger_hash": control_hash,
            "combined_ledger_hash": combined_hash,
            "step1_sealed": False,
            "comparison_allowed": True,
            "answer_revealed": False,
            "freeze_receipt_hash": receipt.receipt_hash,
        }
        self._control_ledger.append(kind=LedgerKind.INTEGRITY, binding=last_binding, content=freeze_content)
        self._combined_ledger.append(kind=LedgerKind.INTEGRITY, binding=last_binding, content=freeze_content)
        self._freeze_receipt = receipt
        self._emit(
            "GLOBAL_EXPERIMENT_FROZEN",
            last_binding,
            {
                "freeze_receipt_hash": receipt.receipt_hash,
                "completed_prefixes": len(completed),
                "comparison_allowed": True,
            },
        )
        return receipt

    def build_comparison_manifest(self) -> ComparisonManifest:
        if self._freeze_receipt is None:
            raise PairedLaneError("comparison blocked until GLOBAL_EXPERIMENT_FREEZE")
        component_hashes: dict[str, list[str]] = {item: [] for item in COMBINED_COMPONENTS}
        for record in self.combined.ledger.snapshot():
            content = self._content(record)
            if content.get("record_type") == "PROVISIONAL_COMPONENT_BOUND":
                component = content.get("component_id")
                if component in component_hashes:
                    component_hashes[component].append(_sha256(content.get("receipt_hash"), "receipt hash"))
        frozen_hashes = {key: tuple(value) for key, value in component_hashes.items()}
        if any(len(value) != len(self.prefix_roster) for value in frozen_hashes.values()):
            raise PairedLaneError("comparison component receipt coverage is incomplete")
        core = {
            "lanes": [LaneId.S135_CONTROL.value, LaneId.FULL_PROVISIONAL_COMBINED.value],
            "scientific_comparison": "CONTROL_VS_ALL_TOGETHER_COMBINED",
            "component_receipt_hashes": frozen_hashes,
            "freeze_receipt_hash": self._freeze_receipt.receipt_hash,
            "predictive_success_claimed": False,
        }
        return ComparisonManifest(
            lanes=(LaneId.S135_CONTROL, LaneId.FULL_PROVISIONAL_COMBINED),
            control_lane=LaneId.S135_CONTROL,
            combined_lane=LaneId.FULL_PROVISIONAL_COMBINED,
            scientific_comparison="CONTROL_VS_ALL_TOGETHER_COMBINED",
            component_receipt_hashes=frozen_hashes,
            freeze_receipt_hash=self._freeze_receipt.receipt_hash,
            predictive_success_claimed=False,
            manifest_hash=_hash(core),
        )

    def append_post_evidence_diagnostic(
        self,
        *,
        receipt: ProvisionalComponentReceipt,
        expected_shadow_first_lock_hash: str,
        answer_revealed: bool,
    ) -> LedgerRecord:
        if self._freeze_receipt is None:
            raise PairedLaneError("post-evidence diagnostics require GLOBAL_EXPERIMENT_FREEZE")
        if not answer_revealed:
            raise PairedLaneError("post-evidence diagnostic requires the post-evidence lifecycle stage")
        item = receipt.validate(binding=receipt.binding)
        if item.lifecycle_stage != ComponentLifecycleStage.POST_EVIDENCE_DIAGNOSTIC:
            raise PairedLaneError("post-evidence component is outside its lawful lifecycle stage")
        expected = _sha256(expected_shadow_first_lock_hash, "shadow first lock hash")
        lock_records = [
            record
            for record in self.combined.ledger.snapshot()
            if record.binding.causal_prefix_hash == item.binding.causal_prefix_hash
            and record.kind in {LedgerKind.LOCK, LedgerKind.NO_LOCK}
        ]
        if len(lock_records) != 1:
            raise PairedLaneError("immutable pre-reveal shadow first lock is missing")
        lock_content = self._content(lock_records[0])
        actual = _sha256(lock_content.get("synthesis_record_hash"), "shadow first lock hash")
        if actual != expected:
            raise PairedLaneError("post-evidence receipt does not match the shadow first lock")
        record = self._combined_ledger.append(
            kind=LedgerKind.INTEGRITY,
            binding=item.binding,
            content={
                "record_type": "POST_EVIDENCE_COMPONENT_DIAGNOSTIC",
                "component_id": item.component_id,
                "component_receipt_hash": item.receipt_hash,
                "pre_reveal_shadow_first_lock_hash": actual,
                "can_rewrite_first_lock": False,
                "can_mutate_brain": False,
                "can_change_primary": False,
                "answer_revealed": True,
            },
        )
        self._emit(
            "POST_EVIDENCE_DIAGNOSTIC_APPENDED",
            item.binding,
            {
                "component_id": item.component_id,
                "receipt_hash": item.receipt_hash,
                "pre_reveal_shadow_first_lock_hash": actual,
                "can_rewrite_first_lock": False,
            },
        )
        return record
