from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.raw_mbo_source_manifest import manifest_hash
from research.kalshi.frankie_raw_mbo_benchmark.chat_packet_seam import native_group_envelope
from research.kalshi.frankie_raw_mbo_benchmark.native_evidence_bundle import (
    NativeEvidenceBundleError,
    NativeEvidenceLedger,
)
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import F_LAST, V4MboAdapter


class NativeEvidenceBundleTests(unittest.TestCase):
    @staticmethod
    def _manifest() -> dict:
        roster = (
            ("20211001", "WARMUP_DEVELOPMENT", 2),
            ("20211003", "WARMUP_DEVELOPMENT", 1),
            ("20211004", "HELD_OUT_BLIND", 1),
            ("20211005", "HELD_OUT_BLIND", 1),
        )
        sources = [
            {
                "name": f"glbx-mdp3-{date}.mbo.dbn.zst",
                "date": date,
                "role": role,
                "bytes": 1000 + index,
                "sha256": str(index) * 64,
                "mbo_records": records,
            }
            for index, (date, role, records) in enumerate(roster, start=1)
        ]
        value = {
            "schema": "FRANKIE_RAW_MBO_SOURCE_MANIFEST_V1",
            "source_kind": "NATIVE_DBN_MBO",
            "causal_clock": "ts_recv_ns",
            "canonical_source_rewritten": False,
            "sources": sources,
            "warmup_mbo_records": 3,
            "held_out_mbo_records": 2,
            "total_mbo_records": 5,
            "manifest_hash": "",
        }
        value["manifest_hash"] = manifest_hash(value)
        return value

    @staticmethod
    def _record(order_id: int, sequence: int, ts_recv: int, *, side: str = "B", flags: int = F_LAST) -> dict:
        return {
            "instrument_id": 1,
            "publisher_id": 1,
            "channel_id": 1,
            "order_id": order_id,
            "action": "A",
            "side": side,
            "price": 3_000_000_000 + order_id,
            "size": 1,
            "flags": flags,
            "sequence": sequence,
            "ts_event": ts_recv - 1,
            "ts_recv": ts_recv,
            "ts_in_delta": 1,
        }

    def test_groups_store_every_raw_action_once_and_bind_exact_cursors(self) -> None:
        manifest = self._manifest()
        ledger = NativeEvidenceLedger(manifest)
        adapter = V4MboAdapter()
        source = manifest["sources"][0]["name"]

        first = self._record(101, 1, 100, flags=0)
        second = self._record(102, 2, 101, side="A")
        frame, _ = adapter.apply(first, raw_symbol="NGX1")
        self.assertIsNone(frame)
        frame, _ = adapter.apply(second, raw_symbol="NGX1")
        envelope = native_group_envelope(adapter, frame)

        group = ledger.add_group(source, envelope)
        self.assertEqual(group["source_record_start"], 0)
        self.assertEqual(group["source_record_end_exclusive"], 2)
        self.assertEqual(group["completed_mbo_records_before"], 0)
        self.assertEqual(group["completed_mbo_records_after"], 2)
        self.assertEqual([row["order_id"] for row in group["raw_actions"]], [101, 102])
        self.assertNotIn("raw_actions", group["compact_event_frame"])
        self.assertNotIn("full_state", group)
        self.assertTrue(group["full_depth_reconstructable_from_checkpoint_and_raw_actions"])
        self.assertTrue(group["fifo_reconstructable_from_checkpoint_and_raw_actions"])
        self.assertEqual(group["causal_availability_clock"], "ts_recv_ns")

    def test_file_boundary_checkpoint_preserves_exact_adapter_state(self) -> None:
        manifest = self._manifest()
        ledger = NativeEvidenceLedger(manifest)
        adapter = V4MboAdapter()
        source = manifest["sources"][0]["name"]
        for record in (
            self._record(101, 1, 100, flags=0),
            self._record(102, 2, 101, side="A"),
        ):
            frame, _ = adapter.apply(record, raw_symbol="NGX1")
            if frame is not None:
                ledger.add_group(source, native_group_envelope(adapter, frame))

        checkpoint = ledger.checkpoint(adapter, source_name=source, reason="RAW_FILE_BOUNDARY")
        self.assertEqual(checkpoint["source_record_cursor"], 2)
        self.assertEqual(checkpoint["completed_mbo_records"], 2)
        self.assertEqual(checkpoint["adapter_state_hash"], checkpoint["adapter_state"]["state_hash"])
        self.assertFalse(checkpoint["event_group_open"])
        self.assertEqual(checkpoint["reason"], "RAW_FILE_BOUNDARY")
        self.assertTrue(checkpoint["full_depth_fifo_continuation_preserved"])

    def test_checkpoint_rejects_open_event_group(self) -> None:
        manifest = self._manifest()
        ledger = NativeEvidenceLedger(manifest)
        adapter = V4MboAdapter()
        source = manifest["sources"][0]["name"]
        adapter.apply(self._record(101, 1, 100, flags=0), raw_symbol="NGX1")
        with self.assertRaises(NativeEvidenceBundleError):
            ledger.checkpoint(adapter, source_name=source, reason="INTERVAL")

    def test_source_must_finish_at_hash_bound_raw_record_count(self) -> None:
        manifest = self._manifest()
        ledger = NativeEvidenceLedger(manifest)
        adapter = V4MboAdapter()
        source = manifest["sources"][0]["name"]
        frame, _ = adapter.apply(self._record(101, 1, 100), raw_symbol="NGX1")
        ledger.add_group(source, native_group_envelope(adapter, frame))
        with self.assertRaises(NativeEvidenceBundleError):
            ledger.finish_source(source)

    def test_final_bundle_reconciles_all_four_native_sources_without_seconds_surface(self) -> None:
        manifest = self._manifest()
        ledger = NativeEvidenceLedger(manifest)
        adapter = V4MboAdapter()
        sequence = 1
        ts_recv = 100
        for source_row in manifest["sources"]:
            source = source_row["name"]
            count = source_row["mbo_records"]
            for offset in range(count):
                flags = F_LAST if offset == count - 1 else 0
                frame, _ = adapter.apply(
                    self._record(1000 + sequence, sequence, ts_recv, flags=flags),
                    raw_symbol="NGX1",
                )
                sequence += 1
                ts_recv += 1
                if frame is not None:
                    ledger.add_group(source, native_group_envelope(adapter, frame))
            ledger.checkpoint(adapter, source_name=source, reason="RAW_FILE_BOUNDARY")
            ledger.finish_source(source)

        bundle = ledger.finalize()
        self.assertEqual(bundle["source_manifest_hash"], manifest["manifest_hash"])
        self.assertEqual(bundle["completed_mbo_records"], 5)
        self.assertEqual(bundle["total_mbo_records"], 5)
        self.assertEqual(bundle["percent_complete"], 100.0)
        self.assertEqual(bundle["scientific_input"], "NATIVE_DBN_MBO")
        self.assertFalse(bundle["seconds_surface_present"])
        self.assertFalse(bundle["step1_derived_input_present"])
        self.assertTrue(bundle["raw_actions_preserved_exactly_once"])
        self.assertTrue(bundle["full_depth_fifo_reconstructable"])
        self.assertEqual(len(bundle["sources"]), 4)
        self.assertEqual(len(bundle["bundle_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
