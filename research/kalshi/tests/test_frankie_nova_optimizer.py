from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.kalshi.frankie_nova_optimizer import (
    BPEState,
    FrankieNovaOptimizer,
    HarnessAccessEvent,
    HarnessAccessLedger,
    HarnessAction,
    HarnessStop,
    compact_json_lossless,
    next_access_event,
    plan_retrieval,
)


def test_lossless_payload_roundtrip_preserves_exact_json_value() -> None:
    payload = {
        "event_id": "g18:20260427:B",
        "nested": {"required": ["x"], "value": 1.25, "flag": False},
        "items": [1, "two", None],
    }
    result = FrankieNovaOptimizer().compact_payload(payload)
    assert json.loads(result.text) == payload
    assert result.decision_safe is True
    assert result.requires_a65_validation is False
    assert result.withheld == ()
    assert result.optimized_bytes <= result.original_bytes


def test_tool_compaction_never_renames_or_merges_markets_terminal_tools() -> None:
    tools = [
        {
            "name": "markets_repo_status",
            "description": "Return repository status.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
            "examples": [{"ok": True}],
        },
        {
            "name": "markets_read_file",
            "description": "Read one safe UTF-8 repository file.",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            "externalDocs": {"url": "https://example.invalid"},
        },
    ]
    compacted, stats = FrankieNovaOptimizer().compact_tool_view(tools)
    assert [t["name"] for t in compacted] == ["markets_repo_status", "markets_read_file"]
    assert compacted[1]["input_schema"] == tools[1]["input_schema"]
    assert "examples" not in compacted[0]
    assert "externalDocs" not in compacted[1]
    assert stats.requires_a65_validation is True
    assert stats.decision_safe is False
    assert stats.withheld


def test_access_ledger_is_append_only_and_causal(tmp_path: Path) -> None:
    ledger = HarnessAccessLedger(tmp_path / "access.jsonl")
    first = HarnessAccessEvent(
        seq=1,
        day="2026-04-27",
        action=HarnessAction.TRACK.value,
        state_class=BPEState.BELIEF.value,
        source="decision_state:g18",
        request="weather block",
        bytes_returned=100,
        estimated_tokens=25,
    )
    ledger.append(first)
    second = HarnessAccessEvent(
        seq=2,
        day="2026-04-28",
        action=HarnessAction.RECALL.value,
        state_class=BPEState.EXPERIENCE.value,
        source="play_index",
        request="freeze analogs",
        bytes_returned=80,
        estimated_tokens=20,
        withheld=("unmatched plays",),
    )
    ledger.append(second)
    assert [r["seq"] for r in ledger.causal_view("2026-04-28")] == [1]
    assert ledger.summary()["estimated_tokens"] == 45

    with pytest.raises(HarnessStop):
        ledger.append(second)


def test_next_access_event_hashes_returned_text(tmp_path: Path) -> None:
    ledger = HarnessAccessLedger(tmp_path / "access.jsonl")
    event = next_access_event(
        ledger=ledger,
        day="2026-04-27",
        action=HarnessAction.RECALL,
        state_class=BPEState.EXPERIENCE,
        source="specialist_track_records",
        request="specialist B prior failures",
        returned_text="abc",
        withheld=("other specialists",),
    )
    assert event.seq == 1
    assert event.bytes_returned == 3
    assert event.withheld == ("other specialists",)
    assert event.source_hash


def test_retrieval_plan_prefers_selective_access_and_refuses_oversize() -> None:
    assert plan_retrieval(file_bytes=500_000, has_query=True, has_range=False).step == "locate"
    assert plan_retrieval(file_bytes=500_000, has_query=False, has_range=True).step == "ranged_read"
    refused = plan_retrieval(file_bytes=500_000, has_query=False, has_range=False)
    assert refused.step == "refuse_full_read"
    assert refused.withheld
    assert plan_retrieval(file_bytes=1_000, has_query=False, has_range=False).step == "full_read"


def test_compact_json_is_deterministic() -> None:
    a = {"b": 2, "a": 1}
    b = {"a": 1, "b": 2}
    assert compact_json_lossless(a) == compact_json_lossless(b)
