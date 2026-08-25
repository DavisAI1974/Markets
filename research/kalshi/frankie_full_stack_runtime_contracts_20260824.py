#!/usr/bin/env python3
"""Additive runtime-plane contracts for the Frankie October full-stack bridge.

This module does not call a provider, replay data, persist files, select a lock policy,
or launch October.  It defines fail-closed interfaces that the executable bridge can
implement while preserving S135 authority and the immutable V4 runtime.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Mapping, Protocol, Sequence


EXPECTED_MODEL = "gpt-5.6-sol"
OCTOBER_START = "2021-10-01T00:00:00Z"
OCTOBER_END = "2021-11-01T00:00:00Z"
GENESIS = "0" * 64
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_SYNTHESIS_TERMS = ("VOTE", "AVERAG", "CONSENSUS")
SECRET_FIELD_TERMS = ("api_key", "authorization", "password", "secret", "token")


class RuntimeContractError(ValueError):
    """A runtime-plane input violated a causal, authority, or receipt boundary."""


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise RuntimeContractError(f"{field} must be non-empty")
    return text


def _sha256(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not SHA256_RE.fullmatch(text):
        raise RuntimeContractError(f"{field} must be lowercase SHA-256")
    return text


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise RuntimeContractError(f"{field} must be finite")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuntimeContractError(f"{field} must be finite") from exc
    if not math.isfinite(number):
        raise RuntimeContractError(f"{field} must be finite")
    return number


def _canonical_json(value: Any, field: str) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError) as exc:
        raise RuntimeContractError(f"{field} must be deterministic JSON") from exc


def _hash_payload(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value, "hash payload").encode()).hexdigest()


@dataclass(frozen=True)
class CausalPrefixBinding:
    run_id: str
    causal_cutoff: float
    event_known_by: float
    causal_prefix_hash: str
    state_prefix_hash: str
    knowledge_manifest_hash: str

    def validate(self) -> "CausalPrefixBinding":
        _required_text(self.run_id, "run_id")
        cutoff = _finite(self.causal_cutoff, "causal_cutoff")
        known = _finite(self.event_known_by, "event_known_by")
        if known > cutoff:
            raise RuntimeContractError("event_known_by cannot exceed the causal cutoff")
        for field in ("causal_prefix_hash", "state_prefix_hash", "knowledge_manifest_hash"):
            _sha256(getattr(self, field), field)
        return self

    def identity_payload(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


class HelperRole(str, Enum):
    RECURRENCE = "recurrence"
    EXTENSION = "extension"
    TIMING = "timing"
    CONTEXT = "context"


@dataclass(frozen=True)
class HelperRoleContract:
    role: HelperRole
    title: str
    objective: str
    model: str = EXPECTED_MODEL
    evidence_only: bool = True
    can_synthesize_probability: bool = False
    can_own_primary_lock: bool = False

    def validate(self) -> "HelperRoleContract":
        if self.model != EXPECTED_MODEL:
            raise RuntimeContractError(f"helper model must be exactly {EXPECTED_MODEL}")
        if not self.evidence_only or self.can_synthesize_probability or self.can_own_primary_lock:
            raise RuntimeContractError("helpers must remain evidence-only without probability or lock authority")
        _required_text(self.title, "helper title")
        _required_text(self.objective, "helper objective")
        return self


_HELPER_CONTRACTS = {
    HelperRole.RECURRENCE: HelperRoleContract(
        HelperRole.RECURRENCE,
        "Pair/triplet recurrence scout",
        "Identify known or novel pair, triplet, and local structural modules.",
    ),
    HelperRole.EXTENSION: HelperRoleContract(
        HelperRole.EXTENSION,
        "Extension-propensity scout",
        "Evaluate whether the lawful prefix is developing into a larger chain or extension.",
    ),
    HelperRole.TIMING: HelperRoleContract(
        HelperRole.TIMING,
        "Timing/lifespan-family scout",
        "Track unresolved age and trajectory without answer-relative or hard-coded event clocks.",
    ),
    HelperRole.CONTEXT: HelperRoleContract(
        HelperRole.CONTEXT,
        "True/false-context investigator",
        "Recover ancestry, regimes, contradiction, stopped chains, and negative evidence.",
    ),
}


def helper_contracts() -> dict[HelperRole, HelperRoleContract]:
    return {role: contract.validate() for role, contract in _HELPER_CONTRACTS.items()}


@dataclass(frozen=True)
class ToolCallReceipt:
    tool_call_id: str
    tool_name: str
    request_hash: str
    response_hash: str

    def validate(self) -> "ToolCallReceipt":
        _required_text(self.tool_call_id, "tool_call_id")
        _required_text(self.tool_name, "tool_name")
        _sha256(self.request_hash, "tool request_hash")
        _sha256(self.response_hash, "tool response_hash")
        return self


@dataclass(frozen=True)
class RetrievalReceipt:
    retrieval_id: str
    source_id: str
    source_sha256: str
    byte_start: int
    byte_end: int
    content_sha256: str

    def validate(self) -> "RetrievalReceipt":
        _required_text(self.retrieval_id, "retrieval_id")
        _required_text(self.source_id, "source_id")
        _sha256(self.source_sha256, "retrieval source_sha256")
        _sha256(self.content_sha256, "retrieval content_sha256")
        if isinstance(self.byte_start, bool) or isinstance(self.byte_end, bool):
            raise RuntimeContractError("retrieval byte range must be integer offsets")
        if not isinstance(self.byte_start, int) or not isinstance(self.byte_end, int):
            raise RuntimeContractError("retrieval byte range must be integer offsets")
        if self.byte_start < 0 or self.byte_end <= self.byte_start:
            raise RuntimeContractError("retrieval byte range must satisfy 0 <= start < end")
        return self


@dataclass(frozen=True)
class KnowledgeSourceExcerpt:
    """Actual provider-visible knowledge bytes bound to one catalog source range."""

    source_id: str
    source_sha256: str
    byte_start: int
    byte_end: int
    content_sha256: str
    excerpt: str

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        source_sha256: str,
        byte_start: int,
        excerpt: str,
    ) -> "KnowledgeSourceExcerpt":
        source = _required_text(source_id, "knowledge source_id")
        source_hash = _sha256(source_sha256, "knowledge source_sha256")
        if isinstance(byte_start, bool) or not isinstance(byte_start, int) or byte_start < 0:
            raise RuntimeContractError("knowledge byte_start must be a non-negative integer")
        if not isinstance(excerpt, str) or not excerpt.strip():
            raise RuntimeContractError("knowledge excerpt must be non-empty UTF-8 text")
        text = excerpt
        encoded = text.encode("utf-8")
        return cls(
            source_id=source,
            source_sha256=source_hash,
            byte_start=byte_start,
            byte_end=byte_start + len(encoded),
            content_sha256=hashlib.sha256(encoded).hexdigest(),
            excerpt=text,
        )

    def validate(self) -> "KnowledgeSourceExcerpt":
        rebuilt = self.create(
            source_id=self.source_id,
            source_sha256=self.source_sha256,
            byte_start=self.byte_start,
            excerpt=self.excerpt,
        )
        if rebuilt != self:
            raise RuntimeContractError("knowledge excerpt byte range or content hash mismatch")
        return self

    def retrieval_identity(self) -> tuple[str, str, int, int, str]:
        self.validate()
        return (
            self.source_id,
            self.source_sha256,
            self.byte_start,
            self.byte_end,
            self.content_sha256,
        )


def validate_knowledge_excerpts(
    excerpts: Sequence[KnowledgeSourceExcerpt],
    retrievals: Sequence[RetrievalReceipt],
) -> tuple[KnowledgeSourceExcerpt, ...]:
    """Require exact content coverage for all provider-visible retrieval receipts."""

    sources = tuple(item.validate() for item in excerpts)
    reads = tuple(item.validate() for item in retrievals)
    if not sources or not reads:
        raise RuntimeContractError("knowledge excerpts and retrieval receipts must be non-empty")
    source_identities = [item.retrieval_identity() for item in sources]
    if len(set(source_identities)) != len(source_identities):
        raise RuntimeContractError("knowledge excerpts must be unique")
    retrieval_identities = {
        (
            item.source_id,
            item.source_sha256,
            item.byte_start,
            item.byte_end,
            item.content_sha256,
        )
        for item in reads
    }
    if set(source_identities) != retrieval_identities:
        raise RuntimeContractError("knowledge excerpts must exactly match supplied retrieval receipts")
    return sources


@dataclass(frozen=True)
class ProviderRequestReceipt:
    model: str
    instructions: str
    request_json: str
    binding: CausalPrefixBinding
    request_hash: str

    @classmethod
    def create(
        cls,
        *,
        model: str,
        request_payload: Mapping[str, Any],
        instructions: str,
        binding: CausalPrefixBinding,
    ) -> "ProviderRequestReceipt":
        if model != EXPECTED_MODEL:
            raise RuntimeContractError(f"provider request model must be exactly {EXPECTED_MODEL}")
        prompt = _required_text(instructions, "provider instructions")
        if not isinstance(request_payload, Mapping):
            raise RuntimeContractError("provider request payload must be an object")
        bound = binding.validate()
        request_json = _canonical_json(dict(request_payload), "provider request payload")
        core = {
            "model": model,
            "instructions": prompt,
            "request_json": request_json,
            "binding": bound.identity_payload(),
        }
        return cls(model, prompt, request_json, bound, _hash_payload(core))

    def validate(self) -> "ProviderRequestReceipt":
        rebuilt = self.create(
            model=self.model,
            request_payload=json.loads(self.request_json),
            instructions=self.instructions,
            binding=self.binding,
        )
        if rebuilt.request_hash != self.request_hash or rebuilt.request_json != self.request_json:
            raise RuntimeContractError("provider request receipt hash mismatch")
        return self


@dataclass(frozen=True)
class AcceptedProviderResponseReceipt:
    provider_response_id: str
    resolved_model: str
    accepted_response_json: str
    request_hash: str
    response_hash: str

    @classmethod
    def create(
        cls,
        *,
        provider_response_id: str,
        resolved_model: str,
        accepted_response: Mapping[str, Any],
        request_hash: str,
    ) -> "AcceptedProviderResponseReceipt":
        response_id = _required_text(provider_response_id, "provider_response_id")
        if resolved_model != EXPECTED_MODEL:
            raise RuntimeContractError(f"accepted response model must be exactly {EXPECTED_MODEL}")
        _sha256(request_hash, "accepted response request_hash")
        if not isinstance(accepted_response, Mapping):
            raise RuntimeContractError("accepted provider response must be a parsed object")
        response_json = _canonical_json(dict(accepted_response), "accepted provider response")
        core = {
            "provider_response_id": response_id,
            "resolved_model": resolved_model,
            "accepted_response_json": response_json,
            "request_hash": request_hash,
        }
        return cls(response_id, resolved_model, response_json, request_hash, _hash_payload(core))

    def validate(self) -> "AcceptedProviderResponseReceipt":
        rebuilt = self.create(
            provider_response_id=self.provider_response_id,
            resolved_model=self.resolved_model,
            accepted_response=json.loads(self.accepted_response_json),
            request_hash=self.request_hash,
        )
        if rebuilt.response_hash != self.response_hash or rebuilt.accepted_response_json != self.accepted_response_json:
            raise RuntimeContractError("accepted provider response receipt hash mismatch")
        return self


@dataclass(frozen=True)
class ProviderInvocationReceipt:
    request: ProviderRequestReceipt
    accepted_response: AcceptedProviderResponseReceipt
    tool_calls: tuple[ToolCallReceipt, ...]
    retrievals: tuple[RetrievalReceipt, ...]
    receipt_hash: str

    @classmethod
    def create(
        cls,
        *,
        request: ProviderRequestReceipt,
        accepted_response: AcceptedProviderResponseReceipt,
        tool_calls: Sequence[ToolCallReceipt],
        retrievals: Sequence[RetrievalReceipt],
    ) -> "ProviderInvocationReceipt":
        req = request.validate()
        response = accepted_response.validate()
        if response.request_hash != req.request_hash:
            raise RuntimeContractError("accepted response is not bound to the exact provider request")
        tools = tuple(item.validate() for item in tool_calls)
        reads = tuple(item.validate() for item in retrievals)
        if not tools or not reads:
            raise RuntimeContractError("provider invocation requires tool-call and retrieval receipts")
        if len({item.tool_call_id for item in tools}) != len(tools):
            raise RuntimeContractError("provider invocation tool-call IDs must be unique")
        if len({item.retrieval_id for item in reads}) != len(reads):
            raise RuntimeContractError("provider invocation retrieval IDs must be unique")
        core = {
            "request_hash": req.request_hash,
            "response_hash": response.response_hash,
            "provider_response_id": response.provider_response_id,
            "tool_calls": [asdict(item) for item in tools],
            "retrievals": [asdict(item) for item in reads],
        }
        return cls(req, response, tools, reads, _hash_payload(core))

    def validate(self) -> "ProviderInvocationReceipt":
        rebuilt = self.create(
            request=self.request,
            accepted_response=self.accepted_response,
            tool_calls=self.tool_calls,
            retrievals=self.retrievals,
        )
        if rebuilt.receipt_hash != self.receipt_hash:
            raise RuntimeContractError("provider invocation receipt hash mismatch")
        return self


@dataclass(frozen=True)
class EvidenceCitation:
    reference_id: str
    content_sha256: str
    observation: str

    def validate(self) -> "EvidenceCitation":
        _required_text(self.reference_id, "evidence reference_id")
        _sha256(self.content_sha256, "evidence content_sha256")
        _required_text(self.observation, "evidence observation")
        return self


@dataclass(frozen=True)
class UncertaintyPacket:
    level: str
    drivers: tuple[str, ...]
    calibrated_probability: float | None

    def validate(self) -> "UncertaintyPacket":
        level = str(self.level).upper()
        if level not in {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}:
            raise RuntimeContractError("uncertainty level is invalid")
        if not self.drivers or any(not str(item).strip() for item in self.drivers):
            raise RuntimeContractError("uncertainty requires specific drivers")
        if self.calibrated_probability is not None:
            probability = _finite(self.calibrated_probability, "calibrated_probability")
            if not 0.0 <= probability <= 1.0:
                raise RuntimeContractError("calibrated_probability must be within [0,1]")
        return self


@dataclass(frozen=True)
class AbstentionPacket:
    is_abstaining: bool
    reason: str | None

    def validate(self) -> "AbstentionPacket":
        if not isinstance(self.is_abstaining, bool):
            raise RuntimeContractError("is_abstaining must be boolean")
        if self.is_abstaining:
            _required_text(self.reason, "abstention reason")
        elif self.reason not in (None, ""):
            raise RuntimeContractError("a non-abstaining packet cannot carry an abstention reason")
        return self


@dataclass(frozen=True)
class HelperEvidencePacket:
    role: HelperRole
    binding: CausalPrefixBinding
    invocation: ProviderInvocationReceipt
    citations: tuple[EvidenceCitation, ...]
    supporting_observations: tuple[str, ...]
    contradictory_observations: tuple[str, ...]
    uncertainty: UncertaintyPacket
    abstention: AbstentionPacket
    packet_hash: str

    @classmethod
    def create(
        cls,
        *,
        role: HelperRole,
        binding: CausalPrefixBinding,
        invocation: ProviderInvocationReceipt,
        citations: Sequence[EvidenceCitation],
        supporting_observations: Sequence[str],
        contradictory_observations: Sequence[str],
        uncertainty: UncertaintyPacket,
        abstention: AbstentionPacket,
    ) -> "HelperEvidencePacket":
        if not isinstance(role, HelperRole):
            raise RuntimeContractError("helper role must be one of the four active contracts")
        helper_contracts()[role]
        bound = binding.validate()
        invoked = invocation.validate()
        if invoked.request.binding != bound:
            raise RuntimeContractError("helper provider invocation must bind the helper causal prefix")
        evidence = tuple(item.validate() for item in citations)
        if not evidence:
            raise RuntimeContractError("helper packet requires evidence citations")
        supplied_references = {
            **{
                f"tool:{item.tool_call_id}": item.response_hash
                for item in invoked.tool_calls
            },
            **{
                f"retrieval:{item.retrieval_id}": item.content_sha256
                for item in invoked.retrievals
            },
        }
        for citation in evidence:
            expected_hash = supplied_references.get(citation.reference_id)
            if expected_hash is None:
                raise RuntimeContractError(
                    "helper citation must reference a supplied tool or retrieval receipt"
                )
            if citation.content_sha256 != expected_hash:
                raise RuntimeContractError("helper citation content hash differs from its receipt")
        support = tuple(_required_text(item, "supporting observation") for item in supporting_observations)
        contradiction = tuple(
            _required_text(item, "contradictory observation") for item in contradictory_observations
        )
        uncertain = uncertainty.validate()
        abstain = abstention.validate()
        core = {
            "role": role.value,
            "binding": bound.identity_payload(),
            "provider_receipt_hash": invoked.receipt_hash,
            "citations": [asdict(item) for item in evidence],
            "supporting_observations": support,
            "contradictory_observations": contradiction,
            "uncertainty": asdict(uncertain),
            "abstention": asdict(abstain),
        }
        return cls(role, bound, invoked, evidence, support, contradiction, uncertain, abstain, _hash_payload(core))

    def validate(self) -> "HelperEvidencePacket":
        rebuilt = self.create(
            role=self.role,
            binding=self.binding,
            invocation=self.invocation,
            citations=self.citations,
            supporting_observations=self.supporting_observations,
            contradictory_observations=self.contradictory_observations,
            uncertainty=self.uncertainty,
            abstention=self.abstention,
        )
        if rebuilt.packet_hash != self.packet_hash:
            raise RuntimeContractError("helper evidence packet hash mismatch")
        return self


def validate_helper_batch(packets: Sequence[HelperEvidencePacket]) -> CausalPrefixBinding:
    items = tuple(item.validate() for item in packets)
    roles = tuple(item.role for item in items)
    if len(items) != len(HelperRole) or set(roles) != set(HelperRole) or len(set(roles)) != len(roles):
        raise RuntimeContractError("helper batch requires exactly one packet from each of the four roles")
    binding = items[0].binding
    if any(item.binding != binding for item in items[1:]):
        raise RuntimeContractError("helpers must receive identical causal-prefix/state/knowledge hashes")
    return binding


@dataclass(frozen=True)
class FrankieSynthesisRecord:
    binding: CausalPrefixBinding
    helper_packet_hashes: tuple[str, ...]
    reasoning: str
    probabilities: tuple[float, ...]
    candidate_ids: tuple[str, ...]
    primary_lock_id: str | None
    synthesis_method: str
    synthesis_owner: str
    probability_owner: str
    primary_lock_owner: str
    helper_owned_lock_ids: tuple[str, ...]
    record_hash: str

    @classmethod
    def create(
        cls,
        *,
        binding: CausalPrefixBinding,
        helper_packets: Sequence[HelperEvidencePacket],
        reasoning: str,
        probabilities: Sequence[float],
        candidate_ids: Sequence[str],
        primary_lock_id: str | None,
        synthesis_method: str,
        helper_owned_lock_ids: Sequence[str] = (),
    ) -> "FrankieSynthesisRecord":
        bound = validate_helper_batch(helper_packets)
        if bound != binding.validate():
            raise RuntimeContractError("Frankie synthesis must use the helpers' identical causal prefix")
        method = _required_text(synthesis_method, "synthesis_method").upper()
        if any(term in method for term in FORBIDDEN_SYNTHESIS_TERMS):
            raise RuntimeContractError("helper voting, averaging, or consensus is mechanically forbidden")
        helper_locks = tuple(helper_owned_lock_ids)
        if helper_locks:
            raise RuntimeContractError("helper-owned primary locks are mechanically forbidden")
        probs = tuple(_finite(item, "probability") for item in probabilities)
        if len(probs) < 2 or any(item < 0.0 or item > 1.0 for item in probs):
            raise RuntimeContractError("probability path requires at least two probabilities within [0,1]")
        if abs(sum(probs) - 1.0) > 1e-9:
            raise RuntimeContractError("Frankie probabilities must sum to one")
        reason = _required_text(reasoning, "Frankie reasoning")
        candidates = tuple(_required_text(item, "candidate_id") for item in candidate_ids)
        lock_id = None if primary_lock_id is None else _required_text(primary_lock_id, "primary_lock_id")
        helper_hashes = tuple(item.packet_hash for item in helper_packets)
        core = {
            "binding": bound.identity_payload(),
            "helper_packet_hashes": helper_hashes,
            "reasoning": reason,
            "probabilities": probs,
            "candidate_ids": candidates,
            "primary_lock_id": lock_id,
            "synthesis_method": method,
            "synthesis_owner": "FRANKIE",
            "probability_owner": "FRANKIE",
            "primary_lock_owner": "FRANKIE",
            "helper_owned_lock_ids": [],
        }
        return cls(
            bound,
            helper_hashes,
            reason,
            probs,
            candidates,
            lock_id,
            method,
            "FRANKIE",
            "FRANKIE",
            "FRANKIE",
            (),
            _hash_payload(core),
        )


class LedgerKind(str, Enum):
    STATE = "STATE"
    STATE_DELTA = "STATE_DELTA"
    HELPER_EVIDENCE = "HELPER_EVIDENCE"
    REASONING = "REASONING"
    PROBABILITY = "PROBABILITY"
    CANDIDATE = "CANDIDATE"
    LOCK = "LOCK"
    NO_LOCK = "NO_LOCK"
    ABSTENTION = "ABSTENTION"
    INTEGRITY = "INTEGRITY"
    RETRIEVAL = "RETRIEVAL"
    PROVIDER = "PROVIDER"
    ANSWER_ACCESS = "ANSWER_ACCESS"


@dataclass(frozen=True)
class LedgerRecord:
    run_id: str
    sequence: int
    kind: LedgerKind
    causal_cutoff: float
    binding: CausalPrefixBinding
    content_json: str
    content_hash: str
    prior_record_hash: str
    record_hash: str


class AppendOnlyLedger(Protocol):
    def append(
        self,
        *,
        kind: LedgerKind,
        causal_cutoff: float,
        binding: CausalPrefixBinding,
        content: Mapping[str, Any],
    ) -> LedgerRecord: ...

    def snapshot(self) -> tuple[LedgerRecord, ...]: ...


class ImmutableAppendOnlyLedger:
    """In-memory reference implementation of the append-only hash-chain interface."""

    def __init__(self, *, run_id: str) -> None:
        self.run_id = _required_text(run_id, "ledger run_id")
        self._records: list[LedgerRecord] = []

    def append(
        self,
        *,
        kind: LedgerKind,
        causal_cutoff: float,
        binding: CausalPrefixBinding,
        content: Mapping[str, Any],
    ) -> LedgerRecord:
        if not isinstance(kind, LedgerKind):
            raise RuntimeContractError("ledger kind is invalid")
        cutoff = _finite(causal_cutoff, "ledger causal_cutoff")
        bound = binding.validate()
        if bound.run_id != self.run_id:
            raise RuntimeContractError("ledger and binding run identities differ")
        if bound.causal_cutoff != cutoff:
            raise RuntimeContractError("ledger record must bind its exact causal cutoff")
        if self._records and cutoff < self._records[-1].causal_cutoff:
            raise RuntimeContractError("append-only ledger cannot append an earlier causal cutoff")
        if not isinstance(content, Mapping):
            raise RuntimeContractError("ledger content must be an object")
        content_json = _canonical_json(dict(content), "ledger content")
        content_hash = hashlib.sha256(content_json.encode()).hexdigest()
        prior_hash = self._records[-1].record_hash if self._records else GENESIS
        core = {
            "run_id": self.run_id,
            "sequence": len(self._records),
            "kind": kind.value,
            "causal_cutoff": cutoff,
            "binding": bound.identity_payload(),
            "content_hash": content_hash,
            "prior_record_hash": prior_hash,
        }
        record = LedgerRecord(
            self.run_id,
            len(self._records),
            kind,
            cutoff,
            bound,
            content_json,
            content_hash,
            prior_hash,
            _hash_payload(core),
        )
        self._records.append(record)
        return record

    def snapshot(self) -> tuple[LedgerRecord, ...]:
        return tuple(self._records)


@dataclass(frozen=True)
class PairedShadowAblation:
    binding: CausalPrefixBinding
    control_runtime: str
    shadow_runtime: str
    control_artifact_hash: str
    shadow_artifact_hash: str
    authority: str
    can_mutate_brain: bool
    can_change_primary_probability: bool
    can_own_primary_lock: bool
    comparison_allowed: bool
    receipt_hash: str

    @classmethod
    def create(
        cls,
        *,
        binding: CausalPrefixBinding,
        control_runtime: str,
        shadow_runtime: str,
        control_artifact_hash: str,
        shadow_artifact_hash: str,
        primary_lock_frozen: bool,
    ) -> "PairedShadowAblation":
        bound = binding.validate()
        control = _required_text(control_runtime, "control_runtime")
        if not control.lower().startswith("s135"):
            raise RuntimeContractError("paired ablation control must remain S135")
        shadow = _required_text(shadow_runtime, "shadow_runtime")
        _sha256(control_artifact_hash, "control_artifact_hash")
        _sha256(shadow_artifact_hash, "shadow_artifact_hash")
        if not primary_lock_frozen:
            raise RuntimeContractError("shadow comparison is allowed only after the S135 primary lock freezes")
        core = {
            "binding": bound.identity_payload(),
            "control_runtime": control,
            "shadow_runtime": shadow,
            "control_artifact_hash": control_artifact_hash,
            "shadow_artifact_hash": shadow_artifact_hash,
            "authority": "SHADOW_ONLY",
            "can_mutate_brain": False,
            "can_change_primary_probability": False,
            "can_own_primary_lock": False,
            "comparison_allowed": True,
        }
        return cls(
            bound,
            control,
            shadow,
            control_artifact_hash,
            shadow_artifact_hash,
            "SHADOW_ONLY",
            False,
            False,
            False,
            True,
            _hash_payload(core),
        )


RUNTIME_EVENT_NAMES = {
    "FRANKIE_REPLAY_PROGRESS",
    "FRANKIE_PROVIDER_CALL_STARTED",
    "FRANKIE_PROVIDER_RESPONSE_ACCEPTED",
    "FRANKIE_PERSISTENCE_APPENDED",
    "FRANKIE_OCTOBER_PROGRESS",
    "FRANKIE_RUNTIME_ERROR",
}


def _reject_secret_fields(value: Any, path: str = "details") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower()
            if any(term in normalized for term in SECRET_FIELD_TERMS):
                raise RuntimeContractError(f"secret-bearing telemetry field is forbidden: {path}.{key}")
            _reject_secret_fields(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_secret_fields(item, f"{path}[{index}]")


@dataclass(frozen=True)
class RuntimeEvent:
    name: str
    level: str
    run_id: str
    correlation_id: str
    causal_cutoff: float
    details_json: str
    event_hash: str

    @classmethod
    def create(
        cls,
        *,
        name: str,
        run_id: str,
        correlation_id: str,
        causal_cutoff: float,
        details: Mapping[str, Any],
    ) -> "RuntimeEvent":
        if name not in RUNTIME_EVENT_NAMES:
            raise RuntimeContractError("unknown structured runtime event")
        if not isinstance(details, Mapping):
            raise RuntimeContractError("runtime event details must be an object")
        _reject_secret_fields(details)
        details_json = _canonical_json(dict(details), "runtime event details")
        level = "ERROR" if name == "FRANKIE_RUNTIME_ERROR" else "INFO"
        core = {
            "name": name,
            "level": level,
            "run_id": _required_text(run_id, "event run_id"),
            "correlation_id": _required_text(correlation_id, "event correlation_id"),
            "causal_cutoff": _finite(causal_cutoff, "event causal_cutoff"),
            "details_json": details_json,
        }
        return cls(
            name,
            level,
            core["run_id"],
            core["correlation_id"],
            core["causal_cutoff"],
            details_json,
            _hash_payload(core),
        )


class RuntimeEventSink(Protocol):
    def emit(self, event: RuntimeEvent) -> None: ...
