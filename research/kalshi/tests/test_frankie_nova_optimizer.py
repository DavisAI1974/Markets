from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

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


class FrankieNovaOptimizerTests(unittest.TestCase):
    def test_lossless_payload_roundtrip_preserves_exact_json_value(self) -> None:
        payload = {
            "event_id": "g18:20260427:B",
            "nested": {"required": ["x"], "value": 1.25, "flag": False},
            "items": [1, "two", None],
        }
        result = FrankieNovaOptimizer().compact_payload(payload)
        self.assertEqual(json.loads(result.text), payload)
        self.assertTrue(result.decision_safe)
        self.assertFalse(result.requires_a65_validation)
        self.assertEqual(result.withheld, ())
        self.assertLessEqual(result.optimized_bytes, result.original_bytes)

    def test_tool_compaction_never_renames_or_merges_markets_terminal_tools(self) -> None:
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
        self.assertEqual(
            [t["name"] for t in compacted],
            ["markets_repo_status", "markets_read_file"],
        )
        self.assertEqual(compacted[1]["input_schema"], tools[1]["input_schema"])
        self.assertNotIn("examples", compacted[0])
        self.assertNotIn("externalDocs", compacted[1])
        self.assertTrue(stats.requires_a65_validation)
        self.assertFalse(stats.decision_safe)
        self.assertTrue(stats.withheld)

    def test_access_ledger_is_append_only_and_causal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ledger = HarnessAccessLedger(Path(td) / "access.jsonl")
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
            self.assertEqual([r["seq"] for r in ledger.causal_view("2026-04-28")], [1])
            self.assertEqual(ledger.summary()["estimated_tokens"], 45)
            with self.assertRaises(HarnessStop):
                ledger.append(second)

    def test_next_access_event_hashes_returned_text(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ledger = HarnessAccessLedger(Path(td) / "access.jsonl")
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
            self.assertEqual(event.seq, 1)
            self.assertEqual(event.bytes_returned, 3)
            self.assertEqual(event.withheld, ("other specialists",))
            self.assertTrue(event.source_hash)

    def test_retrieval_plan_prefers_selective_access_and_refuses_oversize(self) -> None:
        self.assertEqual(
            plan_retrieval(file_bytes=500_000, has_query=True, has_range=False).step,
            "locate",
        )
        self.assertEqual(
            plan_retrieval(file_bytes=500_000, has_query=False, has_range=True).step,
            "ranged_read",
        )
        refused = plan_retrieval(file_bytes=500_000, has_query=False, has_range=False)
        self.assertEqual(refused.step, "refuse_full_read")
        self.assertTrue(refused.withheld)
        self.assertEqual(
            plan_retrieval(file_bytes=1_000, has_query=False, has_range=False).step,
            "full_read",
        )

    def test_compact_json_is_deterministic(self) -> None:
        a = {"b": 2, "a": 1}
        b = {"a": 1, "b": 2}
        self.assertEqual(compact_json_lossless(a), compact_json_lossless(b))


if __name__ == "__main__":
    unittest.main()
