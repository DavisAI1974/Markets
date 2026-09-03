from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark.raw_mbo_source_manifest import manifest_hash
from research.kalshi.frankie_raw_mbo_benchmark.chat_packet_seam import (
    SEED_MEMORY_SCHEMA,
    SEED_SURFACE_LABEL,
    seed_memory_package,
    ChatPacketSeamError,
    build_chat_packet_contract,
    native_group_envelope,
)
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import F_LAST, V4MboAdapter
from research.kalshi.frankie_raw_mbo_benchmark.tests.manifest_fixture import manifest_fixture


class ChatPacketSeamTests(unittest.TestCase):
    def _manifest(self) -> dict:
        return manifest_fixture((10, 20, 30, 40))

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


class SeedMemoryPackageTest(unittest.TestCase):
    """D86/D88: A-memory's memory is the SEED - committed past-run outputs bound by the
    registry's a_memory_overlay group - never the wrong-data package. The package the packet
    contract carries is built FROM the registry's bindings and hashed over the files' bytes,
    so it cannot be asserted; and a layer still bound to an `external:` identity (no
    repository bytes) is a refusal, not a fallback."""

    def _registry(self, tmp, *, external=False):
        root = Path(tmp)
        (root / "seed").mkdir()
        seed = root / "seed" / "A_MEMORY_SEED.json"
        seed.write_text('{"schema": "SEED", "entries": []}\n', encoding="utf-8")
        capsule = root / "seed" / "CAPSULE.md"
        capsule.write_text("capsule\n", encoding="utf-8")
        entries = [
            {"layer_id": "a_memory_promoted_positive_capsule", "source_paths": ["seed/CAPSULE.md"]},
            {"layer_id": "a_memory_prior_lessons_package",
             "source_paths": ["external:a_memory_prior_lessons_package" if external else "seed/A_MEMORY_SEED.json"]},
        ]
        return root, {"groups": [
            {"group_id": "mission", "policy": "STATIC_REQUIRED_INPUT", "arms": ["A_MEMORY"], "entries": []},
            {"group_id": "a_memory_overlay", "policy": "ARM_REQUIRED_INPUT", "arms": ["A_MEMORY"], "entries": entries},
        ]}

    def test_the_seed_package_is_built_from_the_overlay_bindings_and_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, registry = self._registry(tmp)
            package = seed_memory_package(registry, repo_root=root)
            self.assertEqual(package["schema"], SEED_MEMORY_SCHEMA)
            self.assertEqual(package["source_surface_label"], SEED_SURFACE_LABEL)
            self.assertEqual([f["path"] for f in package["files"]],
                             ["seed/A_MEMORY_SEED.json", "seed/CAPSULE.md"])
            for row in package["files"]:
                self.assertEqual(row["sha256"], hashlib.sha256((root / row["path"]).read_bytes()).hexdigest())
                self.assertEqual(row["bytes"], (root / row["path"]).stat().st_size)
            contract = build_chat_packet_contract(
                arm="A-memory", source_manifest=self._manifest(), memory_package=package
            )
            self.assertEqual(contract["memory_mode"], "MEMORY_ASSISTED")
            self.assertEqual(contract["memory_package"]["package_sha256"], package["package_sha256"])
            self.assertEqual(len(contract["memory_package"]["files"]), 2)

    def test_an_external_binding_is_refused_as_not_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, registry = self._registry(tmp, external=True)
            with self.assertRaises(ChatPacketSeamError) as caught:
                seed_memory_package(registry, repo_root=root)
            self.assertIn("external:a_memory_prior_lessons_package", str(caught.exception))
            self.assertIn("D86", str(caught.exception))

    def test_a_seed_package_whose_hash_does_not_match_its_files_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, registry = self._registry(tmp)
            package = seed_memory_package(registry, repo_root=root)
            package["files"][0]["sha256"] = "0" * 64
            with self.assertRaises(ChatPacketSeamError):
                build_chat_packet_contract(
                    arm="A-memory", source_manifest=self._manifest(), memory_package=package
                )

    def test_a_missing_overlay_group_or_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, registry = self._registry(tmp)
            (root / "seed" / "CAPSULE.md").unlink()
            with self.assertRaises(ChatPacketSeamError):
                seed_memory_package(registry, repo_root=root)
            with self.assertRaises(ChatPacketSeamError):
                seed_memory_package({"groups": []}, repo_root=root)

    def _manifest(self) -> dict:
        return manifest_fixture((10, 20, 30, 40))
