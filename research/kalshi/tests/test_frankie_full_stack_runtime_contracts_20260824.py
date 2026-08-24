from __future__ import annotations

import hashlib
import json

import pytest

from research.kalshi.frankie_full_stack_runtime_contracts_20260824 import (
    EXPECTED_MODEL,
    OCTOBER_END,
    OCTOBER_START,
    AbstentionPacket,
    AcceptedProviderResponseReceipt,
    CausalPrefixBinding,
    EvidenceCitation,
    FrankieSynthesisRecord,
    HelperEvidencePacket,
    HelperRole,
    ImmutableAppendOnlyLedger,
    LedgerKind,
    KnowledgeSourceExcerpt,
    PairedShadowAblation,
    ProviderInvocationReceipt,
    ProviderRequestReceipt,
    RetrievalReceipt,
    RuntimeContractError,
    RuntimeEvent,
    ToolCallReceipt,
    UncertaintyPacket,
    helper_contracts,
    validate_helper_batch,
)


H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
H4 = "4" * 64


def binding(*, causal_cutoff: float = 1633075201.0) -> CausalPrefixBinding:
    return CausalPrefixBinding(
        run_id="october-full-stack",
        causal_cutoff=causal_cutoff,
        event_known_by=causal_cutoff - 0.5,
        causal_prefix_hash=H1,
        state_prefix_hash=H2,
        knowledge_manifest_hash=H3,
    ).validate()


def invocation(bind: CausalPrefixBinding | None = None) -> ProviderInvocationReceipt:
    active_binding = bind or binding()
    request = ProviderRequestReceipt.create(
        model=EXPECTED_MODEL,
        request_payload={"causal_prefix_hash": H1, "task": "recurrence"},
        instructions="Use only the lawful causal prefix.",
        binding=active_binding,
    )
    tool = ToolCallReceipt(
        tool_call_id="call-1",
        tool_name="read_state_prefix",
        request_hash=H1,
        response_hash=H2,
    ).validate()
    retrieval = RetrievalReceipt(
        retrieval_id="ret-1",
        source_id="phase2-findings",
        source_sha256=H4,
        byte_start=0,
        byte_end=128,
        content_sha256=H1,
    ).validate()
    accepted = AcceptedProviderResponseReceipt.create(
        provider_response_id="resp_123",
        resolved_model=EXPECTED_MODEL,
        accepted_response={"status": "INCONCLUSIVE", "evidence": ["state:1"]},
        request_hash=request.request_hash,
    )
    return ProviderInvocationReceipt.create(
        request=request,
        accepted_response=accepted,
        tool_calls=(tool,),
        retrievals=(retrieval,),
    )


def packet(role: HelperRole, *, bind: CausalPrefixBinding | None = None) -> HelperEvidencePacket:
    active_binding = bind or binding()
    return HelperEvidencePacket.create(
        role=role,
        binding=active_binding,
        invocation=invocation(active_binding),
        citations=(EvidenceCitation("tool:call-1", H2, "lawful state row"),),
        supporting_observations=("queue depletion persists",),
        contradictory_observations=("ask replenishment remains active",),
        uncertainty=UncertaintyPacket("HIGH", ("short prefix",), None),
        abstention=AbstentionPacket(True, "insufficient causal evidence"),
    )


def test_four_active_helper_contracts_are_evidence_only_and_share_one_prefix():
    contracts = helper_contracts()
    assert tuple(contracts) == tuple(HelperRole)
    assert all(item.model == EXPECTED_MODEL for item in contracts.values())
    assert all(not item.can_synthesize_probability and not item.can_own_primary_lock for item in contracts.values())

    packets = tuple(packet(role) for role in HelperRole)
    assert validate_helper_batch(packets) == binding()

    divergent = CausalPrefixBinding(**{**binding().__dict__, "state_prefix_hash": H4}).validate()
    with pytest.raises(RuntimeContractError, match="identical causal-prefix/state/knowledge"):
        validate_helper_batch((*packets[:-1], packet(HelperRole.CONTEXT, bind=divergent)))


def test_provider_receipt_binds_exact_request_response_id_tools_and_retrievals():
    receipt = invocation()
    assert receipt.request.model == EXPECTED_MODEL
    assert json.loads(receipt.request.request_json)["task"] == "recurrence"
    assert receipt.accepted_response.provider_response_id == "resp_123"
    assert json.loads(receipt.accepted_response.accepted_response_json)["status"] == "INCONCLUSIVE"
    assert receipt.tool_calls[0].tool_name == "read_state_prefix"
    assert receipt.retrievals[0].byte_end == 128
    assert len(receipt.receipt_hash) == 64

    value_bound = ProviderInvocationReceipt.create(
        request=receipt.request,
        accepted_response=receipt.accepted_response,
        tool_calls=receipt.tool_calls,
        retrievals=receipt.retrievals,
        value_state_read_receipt_hashes=(H3,),
    )
    assert value_bound.value_state_read_receipt_hashes == (H3,)
    assert value_bound.receipt_hash != receipt.receipt_hash
    with pytest.raises(RuntimeContractError, match="must be unique"):
        ProviderInvocationReceipt.create(
            request=receipt.request,
            accepted_response=receipt.accepted_response,
            tool_calls=receipt.tool_calls,
            retrievals=receipt.retrievals,
            value_state_read_receipt_hashes=(H3, H3),
        )

    with pytest.raises(RuntimeContractError, match="exactly gpt-5.6-sol"):
        ProviderRequestReceipt.create(
            model="gpt-5.6",
            request_payload={"task": "timing"},
            instructions="bounded",
            binding=binding(),
        )


def test_helper_packet_retains_support_contradiction_uncertainty_and_abstention():
    item = packet(HelperRole.TIMING)
    assert item.supporting_observations
    assert item.contradictory_observations
    assert item.uncertainty.level == "HIGH"
    assert item.abstention.is_abstaining
    assert item.packet_hash


def test_helper_citations_must_bind_supplied_tool_or_retrieval_receipts():
    active = invocation()
    common = {
        "role": HelperRole.RECURRENCE,
        "binding": binding(),
        "invocation": active,
        "supporting_observations": ("support",),
        "contradictory_observations": ("contradiction",),
        "uncertainty": UncertaintyPacket("HIGH", ("bounded",), None),
        "abstention": AbstentionPacket(False, None),
    }
    with pytest.raises(RuntimeContractError, match="supplied tool or retrieval receipt"):
        HelperEvidencePacket.create(
            **common,
            citations=(EvidenceCitation("retrieval:fabricated", H1, "invented"),),
        )
    with pytest.raises(RuntimeContractError, match="citation content hash"):
        HelperEvidencePacket.create(
            **common,
            citations=(EvidenceCitation("retrieval:ret-1", H2, "wrong hash"),),
        )


def test_knowledge_excerpt_is_actual_content_bound_to_its_source_range():
    excerpt = KnowledgeSourceExcerpt.create(
        source_id="phase2-findings",
        source_sha256=H4,
        byte_start=7,
        excerpt=" lawful base knowledge\n",
    )
    assert excerpt.excerpt == " lawful base knowledge\n"
    assert excerpt.byte_end - excerpt.byte_start == len(excerpt.excerpt.encode("utf-8"))
    assert excerpt.content_sha256 == hashlib.sha256(excerpt.excerpt.encode("utf-8")).hexdigest()
    assert excerpt.validate() == excerpt


def test_frankie_is_mechanically_the_only_synthesizer_probability_and_lock_owner():
    helpers = tuple(packet(role) for role in HelperRole)
    synthesis = FrankieSynthesisRecord.create(
        binding=binding(),
        helper_packets=helpers,
        reasoning="Support and contradiction remain unresolved.",
        probabilities=(0.4, 0.6),
        candidate_ids=("candidate-1",),
        primary_lock_id=None,
        synthesis_method="FRANKIE_SOLE_SYNTHESIS",
    )
    assert synthesis.synthesis_owner == "FRANKIE"
    assert synthesis.probability_owner == "FRANKIE"
    assert synthesis.primary_lock_owner == "FRANKIE"

    for forbidden in ("MAJORITY_VOTE", "AVERAGE_HELPERS", "AUTOMATIC_CONSENSUS"):
        with pytest.raises(RuntimeContractError, match="voting, averaging, or consensus"):
            FrankieSynthesisRecord.create(
                binding=binding(),
                helper_packets=helpers,
                reasoning="invalid",
                probabilities=(0.5, 0.5),
                candidate_ids=(),
                primary_lock_id="lock-1",
                synthesis_method=forbidden,
            )

    with pytest.raises(RuntimeContractError, match="helper-owned primary locks"):
        FrankieSynthesisRecord.create(
            binding=binding(),
            helper_packets=helpers,
            reasoning="invalid",
            probabilities=(0.5, 0.5),
            candidate_ids=(),
            primary_lock_id="lock-1",
            synthesis_method="FRANKIE_SOLE_SYNTHESIS",
            helper_owned_lock_ids=("timing-lock",),
        )


def test_immutable_ledger_supports_every_required_movie_and_receipt_kind():
    ledger = ImmutableAppendOnlyLedger(run_id="october-full-stack")
    required = {
        LedgerKind.STATE,
        LedgerKind.STATE_DELTA,
        LedgerKind.HELPER_EVIDENCE,
        LedgerKind.REASONING,
        LedgerKind.PROBABILITY,
        LedgerKind.CANDIDATE,
        LedgerKind.LOCK,
        LedgerKind.NO_LOCK,
        LedgerKind.ABSTENTION,
        LedgerKind.INTEGRITY,
        LedgerKind.RETRIEVAL,
        LedgerKind.PROVIDER,
        LedgerKind.ANSWER_ACCESS,
    }
    for index, kind in enumerate(required):
        causal_cutoff = 1633075200.0 + index
        ledger.append(
            kind=kind,
            causal_cutoff=causal_cutoff,
            binding=binding(causal_cutoff=causal_cutoff),
            content={"kind": kind.value, "index": index},
        )
    frozen = ledger.snapshot()
    assert {row.kind for row in frozen} == required
    assert all(frozen[index].prior_record_hash == frozen[index - 1].record_hash for index in range(1, len(frozen)))
    assert isinstance(frozen, tuple)

    with pytest.raises(RuntimeContractError, match="cannot append an earlier causal cutoff"):
        ledger.append(
            kind=LedgerKind.STATE,
            causal_cutoff=1.0,
            binding=binding(causal_cutoff=1.0),
            content={"late": False},
        )


def test_s137_and_other_provisional_builds_are_paired_shadow_only_on_identical_prefixes():
    paired = PairedShadowAblation.create(
        binding=binding(),
        control_runtime="s135.current-frankie.2",
        shadow_runtime="s137.cognitive.shadow.1",
        control_artifact_hash=H1,
        shadow_artifact_hash=H2,
        primary_lock_frozen=True,
    )
    assert paired.authority == "SHADOW_ONLY"
    assert not paired.can_mutate_brain
    assert not paired.can_change_primary_probability
    assert not paired.can_own_primary_lock
    assert paired.comparison_allowed

    with pytest.raises(RuntimeContractError, match="after the S135 primary lock freezes"):
        PairedShadowAblation.create(
            binding=binding(),
            control_runtime="s135.current-frankie.2",
            shadow_runtime="hipporag.provisional",
            control_artifact_hash=H1,
            shadow_artifact_hash=H2,
            primary_lock_frozen=False,
        )


def test_structured_runtime_events_observe_progress_and_errors_without_secret_fields():
    names = (
        "FRANKIE_REPLAY_PROGRESS",
        "FRANKIE_PROVIDER_CALL_STARTED",
        "FRANKIE_PROVIDER_RESPONSE_ACCEPTED",
        "FRANKIE_PERSISTENCE_APPENDED",
        "FRANKIE_OCTOBER_PROGRESS",
        "FRANKIE_RUNTIME_ERROR",
    )
    events = tuple(
        RuntimeEvent.create(
            name=name,
            run_id="october-full-stack",
            correlation_id="prefix-1",
            causal_cutoff=1633075201.0,
            details={
                "phase": "runtime",
                "processed_seconds": 1,
                "target_start": OCTOBER_START,
                "target_end": OCTOBER_END,
                "error_code": "PROVIDER_TIMEOUT" if name.endswith("ERROR") else None,
            },
        )
        for name in names
    )
    assert [event.name for event in events] == list(names)
    assert all(event.run_id == "october-full-stack" for event in events)

    with pytest.raises(RuntimeContractError, match="secret-bearing telemetry field"):
        RuntimeEvent.create(
            name="FRANKIE_RUNTIME_ERROR",
            run_id="october-full-stack",
            correlation_id="prefix-1",
            causal_cutoff=1633075201.0,
            details={"api_key": "do-not-log"},
        )
