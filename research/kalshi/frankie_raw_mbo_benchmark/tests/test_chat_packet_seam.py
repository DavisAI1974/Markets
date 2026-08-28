from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.raw_mbo_source_manifest import manifest_hash
from research.kalshi.frankie_raw_mbo_benchmark.chat_packet_seam import (
    ChatPacketSeamError,
    build_chat_packet_contract,
    native_group_envelope,
)
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import F_LAST, V4MboAdapter


class ChatPacketSeamTests(unittest.TestCase):
    def _manifest(self) -> dict:
        sources = []
        for index, (date, role) in enumerate(
            (
                ("20211001", "WARMUP_DEVELOPMENT"),
                ("20211003", "WARMUP_DEVELOPMENT"),
                ("20211004", "HELD_OUT_BLIND"),
                ("20211005", "HELD_OUT_BLIND"),
            ),
            start=1,
        ):
            sources.append(
                {
                    "name": f"glbx-mdp3-{date}.mbo.dbn.zst",
                    "date": date,
                    "role": role,
                    "bytes": 1000 + index,
                    "sha256": str(index) * 64,
                    "mbo_records": 10 * index,
                }
            )
        value = {
            "schema": "FRANKIE_RAW_MBO_SOURCE_MANIFEST_V1",
            "source_kind": "NATIVE_DBN_MBO",
            "causal_clock": "ts_recv_ns",
            "canonical_source_rewritten": False,
            "sources": sources,
            "warmup_mbo_records": 30,
            "held_out_mbo_records": 70,
            "total_mbo_records": 100,
            "manifest_hash": "",
        }
        value["manifest_hash"] = manifest_hash(value)
        return value

    @staticmethod
    def _memory() -> dict:
        return {
            "schema": "FRANKIE_PREEXISTING_UNREVEALED_OCT45_MEMORY_V1",
            "source_surface_label": "PRIOR_REDUCED_NON_FULL_MBO_SURFACE",
            "package_sha256": "a" * 64,
            "pre_existing_before_current_benchmark": True,
            "step1_or_post_reveal_content": False,
            "current_benchmark_arm_output_content": False,
        }

    def test_clean_contract_is_native_only_and_reuses_proven_orchestration(self) -> None:
        contract = build_chat_packet_contract(arm="A-clean", source_manifest=self._manifest())
        self.assertEqual(contract["controller"], "A_CHATGPT")
        self.assertEqual(contract["memory_mode"], "CLEAN")
        self.assertEqual(contract["scientific_input"]["source_kind"], "NATIVE_DBN_MBO")
        self.assertEqual(contract["scientific_input"]["causal_availability_clock"], "ts_recv_ns")
        self.assertFalse(contract["scientific_input"]["seconds_collapse_allowed"])
        self.assertFalse(contract["scientific_input"]["mbp_substitute_allowed"])
        self.assertFalse(contract["scientific_input"]["step1_derived_input_allowed"])
        self.assertTrue(contract["scientific_input"]["raw_actions_preserved"])
        self.assertTrue(contract["scientific_input"]["full_depth_required"])
        self.assertTrue(contract["scientific_input"]["fifo_order_state_required"])
        self.assertEqual(
            contract["orchestration_reuse"]["packet_builder_reference"],
            "research/kalshi/ng_exhaustion_two_frankies_workmode_packet_2day_20260825.py",
        )
        self.assertEqual(
            contract["orchestration_reuse"]["coordinator_reference"],
            "research/kalshi/ng_exhaustion_two_frankies_workmode_coordinate_2day_20260825.py",
        )
        self.assertEqual(contract["progress"]["percent_complete"], 0.0)
        self.assertEqual(contract["progress"]["total_mbo_records"], 100)
        self.assertEqual(len(contract["contract_hash"]), 64)

    def test_clean_rejects_memory_and_memory_requires_one_bound_package(self) -> None:
        with self.assertRaises(ChatPacketSeamError):
            build_chat_packet_contract(
                arm="A-clean", source_manifest=self._manifest(), memory_package=self._memory()
            )
        with self.assertRaises(ChatPacketSeamError):
            build_chat_packet_contract(arm="A-memory", source_manifest=self._manifest())

        memory_contract = build_chat_packet_contract(
            arm="A-memory", source_manifest=self._manifest(), memory_package=self._memory()
        )
        self.assertEqual(memory_contract["memory_mode"], "MEMORY_ASSISTED")
        self.assertEqual(memory_contract["memory_package"]["package_sha256"], "a" * 64)

    def test_memory_rejects_step1_or_current_arm_contamination(self) -> None:
        for field in ("step1_or_post_reveal_content", "current_benchmark_arm_output_content"):
            memory = self._memory()
            memory[field] = True
            with self.subTest(field=field), self.assertRaises(ChatPacketSeamError):
                build_chat_packet_contract(
                    arm="A-memory", source_manifest=self._manifest(), memory_package=memory
                )

    def test_non_chat_arm_is_rejected(self) -> None:
        with self.assertRaises(ChatPacketSeamError):
            build_chat_packet_contract(arm="B0-clean", source_manifest=self._manifest())

    def test_native_group_envelope_preserves_actions_full_depth_and_fifo(self) -> None:
        adapter = V4MboAdapter()
        first = {
            "instrument_id": 1,
            "publisher_id": 1,
            "channel_id": 1,
            "order_id": 101,
            "action": "A",
            "side": "B",
            "price": 3_000_000_000,
            "size": 4,
            "flags": 0,
            "sequence": 10,
            "ts_event": 100,
            "ts_recv": 110,
            "ts_in_delta": 10,
        }
        second = {
            "instrument_id": 1,
            "publisher_id": 1,
            "channel_id": 1,
            "order_id": 202,
            "action": "A",
            "side": "A",
            "price": 3_010_000_000,
            "size": 7,
            "flags": F_LAST,
            "sequence": 11,
            "ts_event": 101,
            "ts_recv": 111,
            "ts_in_delta": 10,
        }
        frame, _ = adapter.apply(first, raw_symbol="NGX1")
        self.assertIsNone(frame)
        frame, _ = adapter.apply(second, raw_symbol="NGX1")
        self.assertIsNotNone(frame)

        envelope = native_group_envelope(adapter, frame)
        self.assertEqual(envelope["causal_availability_clock"], "ts_recv_ns")
        self.assertEqual([row["order_id"] for row in envelope["raw_actions"]], [101, 202])
        self.assertTrue(envelope["full_depth_exposed"])
        self.assertTrue(envelope["fifo_order_state_exposed"])
        book = envelope["full_state"]["book"]
        self.assertEqual(book["bid_levels_full"][0]["fifo_queue"][0]["order_id"], 101)
        self.assertEqual(book["ask_levels_full"][0]["fifo_queue"][0]["order_id"], 202)
        self.assertNotIn("legacy_control", envelope)

    def test_native_group_envelope_rejects_non_closed_group(self) -> None:
        adapter = V4MboAdapter()
        with self.assertRaises(ChatPacketSeamError):
            native_group_envelope(
                adapter,
                {
                    "instrument_id": 1,
                    "ts_recv_ns": 111,
                    "event_group_complete_f_last": False,
                    "raw_actions": [],
                },
            )


if __name__ == "__main__":
    unittest.main()
