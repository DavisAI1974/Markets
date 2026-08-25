from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from research.kalshi.frankie_full_stack_runtime_adapter_20260824 import (
    AdapterRuntimeError,
    DurableJsonlLedger,
    FullStackRuntimeAdapter,
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
DUMMY_PROVIDER_SECRET = "sk-" + "abcdefghijklmnopqrstuvwxyz"


def binding(cutoff: float = 1633075201.0) -> CausalPrefixBinding:
    return CausalPrefixBinding(
        run_id="october-full-stack",
        causal_cutoff=cutoff,
        event_known_by=cutoff - 0.5,
        causal_prefix_hash=H1,
        state_prefix_hash=H2,
        knowledge_manifest_hash=H3,
    ).validate()


def tools_and_retrievals():
    return (
        ToolCallReceipt("tool-1", "read_state_prefix", H1, H2).validate(),
    ), (
        RetrievalReceipt("ret-1", "phase2", H4, 0, 128, H1).validate(),
    )


class FakeResponsesAPI:
    def __init__(self, *, mode: str = "ok") -> None:
        self.mode = mode
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.mode == "raise_secret":
            raise RuntimeError(f"provider failed with {DUMMY_PROVIDER_SECRET}")

        payload = json.loads(kwargs["input"])
        response_id = f"resp-{len(self.calls)}"
        model = EXPECTED_MODEL
        if self.mode == "wrong_model":
            model = "gpt-5.6"
        if self.mode == "blank_id":
            response_id = ""

        if payload["request_type"] == "HELPER_EVIDENCE":
            role = payload["role"]
            output = {
                "role": role,
                "citations": [
                    {
                        "reference_id": f"state:{role}",
                        "content_sha256": H2,
                        "observation": f"{role} lawful-prefix observation",
                    }
                ],
                "supporting_observations": [f"{role} support"],
                "contradictory_observations": [f"{role} contradiction"],
                "uncertainty": {
                    "level": "HIGH",
                    "drivers": ["bounded prefix"],
                    "calibrated_probability": None,
                },
                "abstention": {
                    "is_abstaining": True,
                    "reason": "insufficient causal evidence",
                },
            }
        else:
            output = {
                "reasoning": "Frankie weighs support and contradiction without helper voting.",
                "probabilities": [0.7, 0.3],
                "candidate_ids": ["candidate-1"],
                "primary_lock_id": "primary-lock-1",
                "synthesis_method": "FRANKIE_SOLE_SYNTHESIS",
            }
        if self.mode == "schema_drift":
            output["unexpected"] = "field"
        return SimpleNamespace(id=response_id, model=model, output_text=json.dumps(output))


class FakeOpenAIClient:
    def __init__(self, *, mode: str = "ok") -> None:
        self.responses = FakeResponsesAPI(mode=mode)


def run_adapter(tmp_path, *, mode: str = "ok"):
    raw_client = FakeOpenAIClient(mode=mode)
    provider = OpenAIResponsesClient(api_client=raw_client)
    ledger = DurableJsonlLedger.create(tmp_path / "runtime.jsonl", run_id="october-full-stack")
    events = RecordingEventSink()
    adapter = FullStackRuntimeAdapter(client=provider, ledger=ledger, event_sink=events)
    tool_calls, retrievals = tools_and_retrievals()
    result = adapter.run_prefix(
        binding=binding(),
        causal_state={"queue": {"bid_depth": 7, "ask_depth": 5}},
        tool_calls=tool_calls,
        retrievals=retrievals,
    )
    return raw_client, ledger, events, result


def test_five_exact_sol_requests_keep_roles_separate_and_frankie_owns_lock(tmp_path):
    raw_client, ledger, events, result = run_adapter(tmp_path)

    calls = raw_client.responses.calls
    assert len(calls) == 5
    assert all(call["model"] == EXPECTED_MODEL and call["store"] is False for call in calls)
    assert tuple(
        receipt.accepted_response.provider_response_id for receipt in result.invocation_receipts
    ) == ("resp-1", "resp-2", "resp-3", "resp-4", "resp-5")

    helper_payloads = [json.loads(call["input"]) for call in calls[:4]]
    assert [payload["role"] for payload in helper_payloads] == [role.value for role in HelperRole]
    assert len({call["instructions"] for call in calls[:4]}) == 4
    assert all(payload["binding"] == binding().identity_payload() for payload in helper_payloads)
    assert all("probabilities" not in payload["required_output_schema"] for payload in helper_payloads)

    synthesis_payload = json.loads(calls[4]["input"])
    assert synthesis_payload["request_type"] == "FRANKIE_SYNTHESIS"
    assert synthesis_payload["binding"] == binding().identity_payload()
    assert len(synthesis_payload["helper_evidence_packets"]) == 4
    assert result.synthesis.synthesis_owner == "FRANKIE"
    assert result.synthesis.probability_owner == "FRANKIE"
    assert result.synthesis.primary_lock_owner == "FRANKIE"
    assert result.synthesis.primary_lock_id == "primary-lock-1"

    assert len(ledger.snapshot()) >= 12
    assert sum(event.name == "FRANKIE_PROVIDER_RESPONSE_ACCEPTED" for event in events.events) == 5
    assert any(event.name == "FRANKIE_OCTOBER_PROGRESS" for event in events.events)


def test_durable_jsonl_uses_exclusive_creation_validates_resume_and_rejects_backfill(tmp_path):
    path = tmp_path / "append-only.jsonl"
    ledger = DurableJsonlLedger.create(path, run_id="october-full-stack")
    first = ledger.append(
        kind=LedgerKind.STATE,
        binding=binding(10.0),
        content={"state": "first"},
    )
    with pytest.raises(AdapterRuntimeError, match="already exists"):
        DurableJsonlLedger.create(path, run_id="october-full-stack")

    resumed = DurableJsonlLedger.resume(path, run_id="october-full-stack")
    assert resumed.snapshot() == (first,)
    second = resumed.append(
        kind=LedgerKind.STATE_DELTA,
        binding=binding(11.0),
        content={"delta": "second"},
    )
    assert second.prior_record_hash == first.record_hash
    with pytest.raises(AdapterRuntimeError, match="backfill"):
        resumed.append(
            kind=LedgerKind.STATE,
            binding=binding(9.0),
            content={"state": "older"},
        )

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row["sequence"] for row in rows] == [0, 1]
    assert rows[1]["prior_record_hash"] == rows[0]["record_hash"]
    assert DurableJsonlLedger.resume(path, run_id="october-full-stack").snapshot() == (first, second)


@pytest.mark.parametrize("mode,match", [("wrong_model", "model drift"), ("blank_id", "response ID"), ("schema_drift", "schema")])
def test_provider_model_id_and_response_schema_drift_fail_closed(tmp_path, mode, match):
    with pytest.raises(AdapterRuntimeError, match=match):
        run_adapter(tmp_path, mode=mode)


def test_provider_errors_emit_redacted_structured_event(tmp_path):
    raw_client = FakeOpenAIClient(mode="raise_secret")
    provider = OpenAIResponsesClient(api_client=raw_client)
    ledger = DurableJsonlLedger.create(tmp_path / "errors.jsonl", run_id="october-full-stack")
    events = RecordingEventSink()
    adapter = FullStackRuntimeAdapter(client=provider, ledger=ledger, event_sink=events)
    tool_calls, retrievals = tools_and_retrievals()

    with pytest.raises(AdapterRuntimeError, match="provider invocation failed"):
        adapter.run_prefix(
            binding=binding(),
            causal_state={"queue": "lawful"},
            tool_calls=tool_calls,
            retrievals=retrievals,
        )
    error = events.events[-1]
    assert error.name == "FRANKIE_RUNTIME_ERROR"
    assert DUMMY_PROVIDER_SECRET not in error.details_json
    assert "REDACTED_OPENAI_KEY" in error.details_json
