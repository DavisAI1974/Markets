from __future__ import annotations

from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from research.kalshi.frankie_full_stack_paired_lane_orchestrator_20260824 import (
    COMBINED_COMPONENTS,
    ComponentLifecycleStage,
    ComponentStatus,
    LaneId,
    LaneRuntime,
    PairedLaneError,
    PairedLaneEventSink,
    PairedLaneOrchestrator,
    ProvisionalComponentReceipt,
)
from research.kalshi.frankie_full_stack_runtime_adapter_20260824 import (
    DurableJsonlLedger,
    OpenAIResponsesClient,
    RecordingEventSink,
)
from research.kalshi.frankie_full_stack_runtime_contracts_20260824 import (
    EXPECTED_MODEL,
    CausalPrefixBinding,
    HelperRole,
    LedgerKind,
    RetrievalReceipt,
    ToolCallReceipt,
)


H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
H4 = "4" * 64
H5 = "5" * 64


def binding(prefix_hash: str = H1, cutoff: float = 1633075201.0) -> CausalPrefixBinding:
    return CausalPrefixBinding(
        run_id="october-paired-lane",
        causal_cutoff=cutoff,
        event_known_by=cutoff - 0.5,
        causal_prefix_hash=prefix_hash,
        state_prefix_hash=H2,
        knowledge_manifest_hash=H3,
    ).validate()


def tools_and_retrievals(label: str):
    return (
        ToolCallReceipt(f"tool-{label}", "read_state_prefix", H1, H2).validate(),
    ), (
        RetrievalReceipt(f"ret-{label}", f"source-{label}", H4, 0, 128, H5).validate(),
    )


class FakeResponsesAPI:
    def __init__(self, lane: str, *, shared_ids: bool = False) -> None:
        self.lane = lane
        self.shared_ids = shared_ids
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = json.loads(kwargs["input"])
        prefix = "shared" if self.shared_ids else self.lane.lower()
        response_id = f"{prefix}-resp-{len(self.calls)}"
        if payload["request_type"] == "HELPER_EVIDENCE":
            role = payload["role"]
            output = {
                "role": role,
                "citations": [
                    {
                        "reference_id": f"{self.lane}:{role}",
                        "content_sha256": H2,
                        "observation": f"{role} evidence in {self.lane}",
                    }
                ],
                "supporting_observations": [f"{role} support"],
                "contradictory_observations": [f"{role} contradiction"],
                "uncertainty": {
                    "level": "HIGH",
                    "drivers": ["bounded prefix"],
                    "calibrated_probability": None,
                },
                "abstention": {"is_abstaining": False, "reason": None},
            }
        else:
            output = {
                "reasoning": f"Frankie synthesizes {self.lane} without voting.",
                "probabilities": [0.7, 0.3],
                "candidate_ids": [f"candidate-{self.lane.lower()}"],
                "primary_lock_id": f"lock-{self.lane.lower()}",
                "synthesis_method": "FRANKIE_SOLE_SYNTHESIS",
            }
        return SimpleNamespace(id=response_id, model=EXPECTED_MODEL, output_text=json.dumps(output))


class FakeOpenAIClient:
    def __init__(self, lane: str, *, shared_ids: bool = False) -> None:
        self.responses = FakeResponsesAPI(lane, shared_ids=shared_ids)


def lane_runtime(tmp_path, lane: LaneId, *, shared_ids: bool = False) -> tuple[LaneRuntime, FakeOpenAIClient]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    raw = FakeOpenAIClient(lane.value, shared_ids=shared_ids)
    client = OpenAIResponsesClient(api_client=raw)
    ledger = DurableJsonlLedger.create(
        tmp_path / f"{lane.value.lower()}.jsonl", run_id="october-paired-lane"
    )
    tools, retrievals = tools_and_retrievals(lane.value)
    return (
        LaneRuntime(
            lane_id=lane,
            client=client,
            ledger=ledger,
            event_sink=RecordingEventSink(),
            tool_calls=tools,
            retrievals=retrievals,
        ),
        raw,
    )


def component_receipts(bound: CausalPrefixBinding):
    return tuple(
        ProvisionalComponentReceipt.create(
            component_id=component,
            binding=bound,
            lifecycle_stage=(
                ComponentLifecycleStage.POST_EVIDENCE_DIAGNOSTIC
                if component == "META_LOOP"
                else ComponentLifecycleStage.PRE_REVEAL_PREFIX
            ),
            executed_stage=ComponentLifecycleStage.PRE_REVEAL_PREFIX,
            status=(
                ComponentStatus.DEFERRED_NOT_YET_LAWFUL
                if component == "META_LOOP"
                else ComponentStatus.ACTIVE
            ),
            context={
                "component": component,
                "evidence": f"lawful-{component.lower()}",
                "post_evidence_deferred": component == "META_LOOP",
            },
        )
        for component in COMBINED_COMPONENTS
    )


def make_orchestrator(tmp_path, *, roster=(H1,), shared_ids: bool = False):
    control, control_raw = lane_runtime(tmp_path, LaneId.S135_CONTROL, shared_ids=shared_ids)
    combined, combined_raw = lane_runtime(
        tmp_path, LaneId.FULL_PROVISIONAL_COMBINED, shared_ids=shared_ids
    )
    telemetry = PairedLaneEventSink()
    orchestrator = PairedLaneOrchestrator(
        prefix_roster=roster,
        control=control,
        combined=combined,
        event_sink=telemetry,
    )
    return orchestrator, control_raw, combined_raw, telemetry


def test_exactly_two_complete_lanes_share_prefix_but_isolate_combined_context_and_ledgers(tmp_path):
    orchestrator, control_raw, combined_raw, telemetry = make_orchestrator(tmp_path)
    raw_state = {"queue": {"bid_depth": 7, "ask_depth": 5}}

    paired = orchestrator.run_prefix(
        binding=binding(),
        causal_state=raw_state,
        component_receipts=component_receipts(binding()),
        answer_revealed=False,
    )

    assert paired.lane_ids == (LaneId.S135_CONTROL, LaneId.FULL_PROVISIONAL_COMBINED)
    assert paired.control.binding == paired.combined.binding == binding()
    assert paired.identical_prefix_proof.prefix_hash == H1
    assert paired.identical_prefix_proof.state_prefix_hash == H2
    assert paired.identical_prefix_proof.knowledge_manifest_hash == H3
    assert paired.identical_prefix_proof.proved is True
    assert len(paired.control.helper_packets) == len(paired.combined.helper_packets) == 4
    assert tuple(packet.role for packet in paired.control.helper_packets) == tuple(HelperRole)
    assert len(paired.control.invocation_receipts) == len(paired.combined.invocation_receipts) == 5
    control_ids = {
        item.accepted_response.provider_response_id for item in paired.control.invocation_receipts
    }
    combined_ids = {
        item.accepted_response.provider_response_id for item in paired.combined.invocation_receipts
    }
    assert control_ids.isdisjoint(combined_ids)
    assert paired.control.synthesis.primary_lock_owner == "FRANKIE"
    assert paired.combined.synthesis.primary_lock_owner == "FRANKIE"
    assert paired.control_lock_authority == "S135_PRIMARY"
    assert paired.combined_lock_authority == "SHADOW_ONLY"
    assert paired.primary_lane == LaneId.S135_CONTROL
    assert raw_state == {"queue": {"bid_depth": 7, "ask_depth": 5}}

    control_payloads = [json.loads(call["input"]) for call in control_raw.responses.calls[:4]]
    combined_payloads = [json.loads(call["input"]) for call in combined_raw.responses.calls[:4]]
    assert all("provisional_combined_context" not in row["causal_state"] for row in control_payloads)
    combined_context = combined_payloads[0]["causal_state"]["provisional_combined_context"]
    assert set(combined_context["components"]) == set(COMBINED_COMPONENTS)
    assert all(row["causal_state"]["provisional_combined_context"] == combined_context for row in combined_payloads)
    assert all(row["binding"] == binding().identity_payload() for row in control_payloads + combined_payloads)

    for lane, runtime in (
        (LaneId.S135_CONTROL, orchestrator.control),
        (LaneId.FULL_PROVISIONAL_COMBINED, orchestrator.combined),
    ):
        rows = [json.loads(record.content_json) for record in runtime.ledger.snapshot()]
        assert rows and all(row["lane_id"] == lane.value for row in rows)
        lock_rows = [
            row
            for record, row in zip(runtime.ledger.snapshot(), rows)
            if record.kind in {LedgerKind.LOCK, LedgerKind.NO_LOCK}
        ]
        expected = "S135_PRIMARY" if lane == LaneId.S135_CONTROL else "SHADOW_ONLY"
        assert lock_rows[-1]["lock_authority"] == expected
        assert lock_rows[-1]["first_lock_immutable"] is True

    assert {event.name for event in telemetry.events} >= {
        "PAIRED_LANE_STARTED",
        "PROVISIONAL_COMPONENT_BOUND",
        "IDENTICAL_PREFIX_PROVED",
        "PAIRED_LANE_PREFIX_COMPLETE",
    }


def test_global_freeze_requires_complete_roster_then_enables_only_control_vs_combined_comparison(tmp_path):
    orchestrator, _, _, _ = make_orchestrator(tmp_path, roster=(H1, H4))
    first = binding(H1, 1633075201.0)
    orchestrator.run_prefix(
        binding=first,
        causal_state={"prefix": 1},
        component_receipts=component_receipts(first),
        answer_revealed=False,
    )

    with pytest.raises(PairedLaneError, match="complete prefix roster"):
        orchestrator.freeze_global_experiment(answer_revealed=False)
    with pytest.raises(PairedLaneError, match="GLOBAL_EXPERIMENT_FREEZE"):
        orchestrator.build_comparison_manifest()

    second = binding(H4, 1633075202.0)
    orchestrator.run_prefix(
        binding=second,
        causal_state={"prefix": 2},
        component_receipts=component_receipts(second),
        answer_revealed=False,
    )
    freeze = orchestrator.freeze_global_experiment(answer_revealed=False)
    assert freeze.freeze_name == "GLOBAL_EXPERIMENT_FREEZE"
    assert freeze.completed_prefix_hashes == (H1, H4)
    assert freeze.step1_sealed is False
    assert freeze.comparison_allowed is True

    manifest = orchestrator.build_comparison_manifest()
    assert manifest.lanes == (LaneId.S135_CONTROL, LaneId.FULL_PROVISIONAL_COMBINED)
    assert manifest.control_lane == LaneId.S135_CONTROL
    assert manifest.combined_lane == LaneId.FULL_PROVISIONAL_COMBINED
    assert manifest.predictive_success_claimed is False
    assert manifest.scientific_comparison == "CONTROL_VS_ALL_TOGETHER_COMBINED"
    assert set(manifest.component_receipt_hashes) == set(COMBINED_COMPONENTS)

    for runtime in (orchestrator.control, orchestrator.combined):
        kinds_by_prefix: dict[str, set[LedgerKind]] = {H1: set(), H4: set()}
        for record in runtime.ledger.snapshot():
            if record.binding.causal_prefix_hash in kinds_by_prefix:
                kinds_by_prefix[record.binding.causal_prefix_hash].add(record.kind)
        for kinds in kinds_by_prefix.values():
            assert {LedgerKind.HELPER_EVIDENCE, LedgerKind.REASONING, LedgerKind.PROBABILITY, LedgerKind.CANDIDATE} <= kinds
            assert LedgerKind.LOCK in kinds or LedgerKind.NO_LOCK in kinds

    resumed_control_tools, resumed_control_retrievals = tools_and_retrievals("resumed-control")
    resumed_combined_tools, resumed_combined_retrievals = tools_and_retrievals("resumed-combined")
    resumed = PairedLaneOrchestrator(
        prefix_roster=(H1, H4),
        control=LaneRuntime(
            lane_id=LaneId.S135_CONTROL,
            client=OpenAIResponsesClient(api_client=FakeOpenAIClient("resumed-control")),
            ledger=DurableJsonlLedger.resume(
                tmp_path / "s135_control.jsonl", run_id="october-paired-lane"
            ),
            event_sink=RecordingEventSink(),
            tool_calls=resumed_control_tools,
            retrievals=resumed_control_retrievals,
        ),
        combined=LaneRuntime(
            lane_id=LaneId.FULL_PROVISIONAL_COMBINED,
            client=OpenAIResponsesClient(api_client=FakeOpenAIClient("resumed-combined")),
            ledger=DurableJsonlLedger.resume(
                tmp_path / "full_provisional_combined.jsonl", run_id="october-paired-lane"
            ),
            event_sink=RecordingEventSink(),
            tool_calls=resumed_combined_tools,
            retrievals=resumed_combined_retrievals,
        ),
        event_sink=PairedLaneEventSink(),
    )
    assert resumed.build_comparison_manifest().freeze_receipt_hash == freeze.receipt_hash
    with pytest.raises(PairedLaneError, match="append-once"):
        resumed.freeze_global_experiment(answer_revealed=False)


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda rows: rows[:-1], "all provisional components"),
        (lambda rows: (replace(rows[0], can_mutate_brain=True), *rows[1:]), "cannot mutate brain"),
        (lambda rows: (replace(rows[0], can_share_derived_state=True), *rows[1:]), "cannot share derived state"),
        (lambda rows: (replace(rows[0], can_change_primary=True), *rows[1:]), "cannot change primary"),
        (
            lambda rows: (
                replace(rows[0], binding=replace(rows[0].binding, state_prefix_hash=H5)),
                *rows[1:],
            ),
            "identical causal prefix",
        ),
    ],
)
def test_provisional_bundle_fails_closed_on_missing_authority_or_prefix_drift(tmp_path, mutation, match):
    orchestrator, _, _, _ = make_orchestrator(tmp_path)
    receipts = component_receipts(binding())
    with pytest.raises(PairedLaneError, match=match):
        orchestrator.run_prefix(
            binding=binding(),
            causal_state={"queue": "lawful"},
            component_receipts=mutation(receipts),
            answer_revealed=False,
        )


def test_reserved_context_answer_access_shared_provider_ids_and_shared_ledger_fail_closed(tmp_path):
    orchestrator, _, _, _ = make_orchestrator(tmp_path)
    with pytest.raises(PairedLaneError, match="reserved provisional context"):
        orchestrator.run_prefix(
            binding=binding(),
            causal_state={"provisional_combined_context": {"injected": True}},
            component_receipts=component_receipts(binding()),
            answer_revealed=False,
        )
    with pytest.raises(PairedLaneError, match="pre-answer-reveal"):
        orchestrator.run_prefix(
            binding=binding(),
            causal_state={"queue": "lawful"},
            component_receipts=component_receipts(binding()),
            answer_revealed=True,
        )

    shared, _, _, _ = make_orchestrator(tmp_path / "shared", shared_ids=True)
    with pytest.raises(PairedLaneError, match="provider response IDs"):
        shared.run_prefix(
            binding=binding(),
            causal_state={"queue": "lawful"},
            component_receipts=component_receipts(binding()),
            answer_revealed=False,
        )

    control, _ = lane_runtime(tmp_path / "same", LaneId.S135_CONTROL)
    combined_tools, combined_retrievals = tools_and_retrievals("combined")
    combined = LaneRuntime(
        lane_id=LaneId.FULL_PROVISIONAL_COMBINED,
        client=OpenAIResponsesClient(api_client=FakeOpenAIClient("combined")),
        ledger=control.ledger,
        event_sink=RecordingEventSink(),
        tool_calls=combined_tools,
        retrievals=combined_retrievals,
    )
    with pytest.raises(PairedLaneError, match="independent ledgers"):
        PairedLaneOrchestrator(
            prefix_roster=(H1,), control=control, combined=combined, event_sink=PairedLaneEventSink()
        )


def test_component_lifecycle_and_post_evidence_append_cannot_rewrite_shadow_first_lock(tmp_path):
    orchestrator, _, _, _ = make_orchestrator(tmp_path)
    wrong_stage = replace(
        component_receipts(binding())[0],
        executed_stage=ComponentLifecycleStage.POST_EVIDENCE_DIAGNOSTIC,
    )
    with pytest.raises(PairedLaneError, match="lawful lifecycle stage"):
        orchestrator.run_prefix(
            binding=binding(),
            causal_state={"queue": "lawful"},
            component_receipts=(wrong_stage, *component_receipts(binding())[1:]),
            answer_revealed=False,
        )

    paired = orchestrator.run_prefix(
        binding=binding(),
        causal_state={"queue": "lawful"},
        component_receipts=component_receipts(binding()),
        answer_revealed=False,
    )
    first_lock_hash = paired.combined.synthesis.record_hash
    orchestrator.freeze_global_experiment(answer_revealed=False)
    post_receipt = ProvisionalComponentReceipt.create(
        component_id="META_LOOP",
        binding=binding(),
        lifecycle_stage=ComponentLifecycleStage.POST_EVIDENCE_DIAGNOSTIC,
        executed_stage=ComponentLifecycleStage.POST_EVIDENCE_DIAGNOSTIC,
        status=ComponentStatus.ACTIVE,
        context={"diagnostic": "post-evidence only"},
    )
    appended = orchestrator.append_post_evidence_diagnostic(
        receipt=post_receipt,
        expected_shadow_first_lock_hash=first_lock_hash,
        answer_revealed=True,
    )
    assert appended.kind == LedgerKind.INTEGRITY
    content = json.loads(appended.content_json)
    assert content["pre_reveal_shadow_first_lock_hash"] == first_lock_hash
    assert content["can_rewrite_first_lock"] is False
    lock_rows = [
        row
        for row in orchestrator.combined.ledger.snapshot()
        if row.kind in {LedgerKind.LOCK, LedgerKind.NO_LOCK}
    ]
    assert len(lock_rows) == 1

    with pytest.raises(PairedLaneError, match="shadow first lock"):
        orchestrator.append_post_evidence_diagnostic(
            receipt=post_receipt,
            expected_shadow_first_lock_hash=H5,
            answer_revealed=True,
        )
