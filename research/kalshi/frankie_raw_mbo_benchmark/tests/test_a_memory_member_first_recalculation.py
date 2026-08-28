from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark import (
    a_memory_member_first_recalculation_20260828 as recalc,
)
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import F_LAST, V4MboAdapter


class AMemoryMemberFirstPureLogicTests(unittest.TestCase):
    @staticmethod
    def _raw_action(
        *, action: str, side: str, order_id: int, price_raw: int, size: int, flags: int
    ) -> dict:
        return {
            "action": action,
            "channel_id": 1,
            "flags": flags,
            "instrument_id": 1,
            "is_last": bool(flags & F_LAST),
            "is_snapshot": False,
            "order_id": order_id,
            "price": price_raw / 1_000_000_000,
            "price_raw": price_raw,
            "publisher_id": 1,
            "raw_symbol": "NGX1",
            "sequence": 10 + order_id,
            "side": side,
            "size": size,
            "source_dbn_object": "glbx-mdp3-20211004.mbo.dbn.zst",
            "source_dbn_sha256": "a" * 64,
            "ts_event_ns": 100 + order_id,
            "ts_in_delta_ns": 10,
            "ts_recv_ns": 200 + order_id,
        }

    def test_unknown_native_path_receives_open_world_candidate_identity(self) -> None:
        actions = [
            {"action": "T", "side": "B", "order_id": 0, "price_raw": 6000, "size": 3},
            {"action": "F", "side": "A", "order_id": 11, "price_raw": 6000, "size": 1},
            {"action": "F", "side": "A", "order_id": 12, "price_raw": 5999, "size": 2},
            {"action": "A", "side": "B", "order_id": 13, "price_raw": 5998, "size": 2},
            {"action": "C", "side": "A", "order_id": 11, "price_raw": 6000, "size": 1},
            {"action": "M", "side": "A", "order_id": 12, "price_raw": 5999, "size": 1},
            {"action": "N", "side": "N", "order_id": 0, "price_raw": None, "size": 0},
        ]

        observed = recalc.describe_structure(actions)

        self.assertEqual(observed["action_string"], "TFFACMN")
        self.assertEqual(observed["side_string"], "BAABAAN")
        self.assertFalse(observed["matches_carried_native_family"])
        self.assertEqual(observed["discovery_status"], "OPEN_WORLD_CANDIDATE")
        self.assertRegex(observed["candidate_family_id"], r"^ow-[0-9a-f]{20}$")

    def test_candidate_identity_is_content_derived_not_family_count_derived(self) -> None:
        actions = [
            {"action": "A", "side": "B", "order_id": 1, "price_raw": 10, "size": 2},
            {"action": "N", "side": "N", "order_id": 0, "price_raw": None, "size": 0},
        ]

        first = recalc.describe_structure(actions)
        second = recalc.describe_structure(list(actions))

        self.assertEqual(first["candidate_family_id"], second["candidate_family_id"])
        self.assertNotIn("family_count", first)
        self.assertNotIn("maximum_family_count", first)

    def test_structural_seed_vocabulary_is_not_an_allowlist(self) -> None:
        contract = recalc.discovery_contract()

        self.assertEqual(
            contract["structural_state_seeds"],
            {
                "P": "persistent_exhaustion",
                "O": "collapsed_opposite_flow_reversal",
                "S": "collapsed_same_flow_reload",
                "X": "collapsed_sparse_indeterminate",
            },
        )
        self.assertEqual(contract["transition_orientation_seeds"], ["SAME", "FLIP"])
        self.assertTrue(contract["open_world"])
        self.assertIsNone(contract["maximum_family_count"])
        self.assertEqual(contract["unmatched_policy"], "PRESERVE_AND_CHARACTERIZE")

    def test_mirrored_sides_share_pair_key_but_retain_orientation(self) -> None:
        bid_resting = recalc.mirror_identity("ABBN")
        ask_resting = recalc.mirror_identity("BAAN")

        self.assertEqual(bid_resting["mirror_side_string"], "BAAN")
        self.assertEqual(ask_resting["mirror_side_string"], "ABBN")
        self.assertEqual(bid_resting["mirror_pair_key"], ask_resting["mirror_pair_key"])
        self.assertNotEqual(bid_resting["orientation"], ask_resting["orientation"])

    def test_exact_book_values_and_deltas_are_preserved(self) -> None:
        before = {
            "spread": 0.003,
            "depth_imbalance_full": -0.2,
            "bid_depth_full": 80,
            "ask_depth_full": 120,
            "bid_order_count_full": 40,
            "ask_order_count_full": 60,
            "bid_price_level_count_full": 8,
            "ask_price_level_count_full": 10,
        }
        after = {
            "spread": 0.002,
            "depth_imbalance_full": 0.2,
            "bid_depth_full": 120,
            "ask_depth_full": 80,
            "bid_order_count_full": 55,
            "ask_order_count_full": 45,
            "bid_price_level_count_full": 9,
            "ask_price_level_count_full": 9,
        }

        observed = recalc.book_transition(before, after)

        self.assertEqual(observed["before"], before)
        self.assertEqual(observed["after"], after)
        self.assertEqual(observed["delta"]["bid_depth_full"], 40)
        self.assertEqual(observed["delta"]["ask_depth_full"], -40)
        self.assertEqual(
            observed["sign_signature"],
            "spread:-|depth_imbalance_full:+|bid_depth_full:+|ask_depth_full:-|"
            "bid_order_count_full:+|ask_order_count_full:-|"
            "bid_price_level_count_full:+|ask_price_level_count_full:-",
        )

    def test_fill_disposition_preserves_split_and_unresolved_ids(self) -> None:
        actions = [
            {"action": "F", "side": "A", "order_id": 1, "price_raw": 1, "size": 1},
            {"action": "F", "side": "A", "order_id": 2, "price_raw": 1, "size": 1},
            {"action": "F", "side": "A", "order_id": 3, "price_raw": 1, "size": 1},
            {"action": "C", "side": "A", "order_id": 1, "price_raw": 1, "size": 1},
            {"action": "M", "side": "A", "order_id": 2, "price_raw": 1, "size": 1},
        ]

        observed = recalc.fill_disposition(actions)

        self.assertEqual(observed["cancelled_fill_order_ids"], [1])
        self.assertEqual(observed["modified_fill_order_ids"], [2])
        self.assertEqual(observed["unresolved_fill_order_ids"], [3])
        self.assertEqual(observed["class"], "SPLIT_CANCEL_MODIFY_WITH_UNRESOLVED")

    def test_averages_never_pool_distinct_structural_strata(self) -> None:
        accumulator = recalc.StratifiedAverages()
        book = {key: 1 for key in recalc.BOOK_FIELDS}

        accumulator.add(
            source_day="2021-10-04",
            family_id="family-a",
            side_string="ABBN",
            continuity_segment="segment-1",
            causal_phase="phase-1",
            clock_basis="F_LAST_TS_RECV_NS",
            group_index=1,
            values=book,
        )
        accumulator.add(
            source_day="2021-10-04",
            family_id="family-a",
            side_string="BAAN",
            continuity_segment="segment-1",
            causal_phase="phase-1",
            clock_basis="F_LAST_TS_RECV_NS",
            group_index=2,
            values=book,
        )

        rows = accumulator.rows()

        self.assertEqual(len(rows), 2)
        self.assertEqual({row["side_string"] for row in rows}, {"ABBN", "BAAN"})
        self.assertTrue(all(row["denominator_n"] == 1 for row in rows))
        self.assertTrue(all(row["member_group_indices"] for row in rows))

    def test_reconstruct_group_restores_exact_book_and_f_last_clock(self) -> None:
        actions = [
            self._raw_action(
                action="A", side="B", order_id=1, price_raw=3_000_000_000, size=4, flags=0
            ),
            self._raw_action(
                action="A",
                side="A",
                order_id=2,
                price_raw=3_010_000_000,
                size=7,
                flags=F_LAST,
            ),
        ]
        group = {
            "group_index": 0,
            "group_hash": "b" * 64,
            "completed_mbo_records_before": 0,
            "completed_mbo_records_after": 2,
            "causal_availability_clock": "ts_recv_ns",
            "full_depth_reconstructable_from_checkpoint_and_raw_actions": True,
            "fifo_reconstructable_from_checkpoint_and_raw_actions": True,
            "mbp_substitute_used": False,
            "seconds_collapse_used": False,
            "step1_derived_input_used": False,
            "compact_event_frame": {
                "event_group_complete_f_last": True,
                "ts_event_ns": 102,
                "ts_recv_ns": 202,
            },
            "raw_actions": actions,
        }

        frame = recalc.reconstruct_group(V4MboAdapter(), group, expected_cursor=0)

        self.assertEqual(frame["ts_recv_ns"], 202)
        self.assertEqual(frame["book"]["bid_depth_full"], 4)
        self.assertEqual(frame["book"]["ask_depth_full"], 7)
        self.assertAlmostEqual(frame["book"]["spread"], 0.01)

    def test_reconstruct_group_fails_closed_on_non_f_last_group(self) -> None:
        action = self._raw_action(
            action="A", side="B", order_id=1, price_raw=3_000_000_000, size=4, flags=0
        )
        group = {
            "group_index": 0,
            "group_hash": "b" * 64,
            "completed_mbo_records_before": 0,
            "completed_mbo_records_after": 1,
            "causal_availability_clock": "ts_recv_ns",
            "full_depth_reconstructable_from_checkpoint_and_raw_actions": True,
            "fifo_reconstructable_from_checkpoint_and_raw_actions": True,
            "mbp_substitute_used": False,
            "seconds_collapse_used": False,
            "step1_derived_input_used": False,
            "compact_event_frame": {
                "event_group_complete_f_last": False,
                "ts_event_ns": 101,
                "ts_recv_ns": 201,
            },
            "raw_actions": [action],
        }

        with self.assertRaisesRegex(RuntimeError, "F_LAST"):
            recalc.reconstruct_group(V4MboAdapter(), group, expected_cursor=0)

    def test_small_recalculation_writes_every_member_and_open_world_receipt(self) -> None:
        first = self._raw_action(
            action="A", side="B", order_id=1, price_raw=3_000_000_000, size=4, flags=F_LAST
        )
        second = self._raw_action(
            action="A", side="A", order_id=2, price_raw=3_010_000_000, size=7, flags=F_LAST
        )
        second["ts_event_ns"] = 102
        second["ts_recv_ns"] = 202
        groups = []
        for index, action in enumerate((first, second)):
            groups.append(
                {
                    "group_index": index,
                    "group_hash": str(index + 1) * 64,
                    "completed_mbo_records_before": index,
                    "completed_mbo_records_after": index + 1,
                    "causal_availability_clock": "ts_recv_ns",
                    "full_depth_reconstructable_from_checkpoint_and_raw_actions": True,
                    "fifo_reconstructable_from_checkpoint_and_raw_actions": True,
                    "mbp_substitute_used": False,
                    "seconds_collapse_used": False,
                    "step1_derived_input_used": False,
                    "compact_event_frame": {
                        "event_group_complete_f_last": True,
                        "ts_event_ns": action["ts_event_ns"],
                        "ts_recv_ns": action["ts_recv_ns"],
                    },
                    "raw_actions": [action],
                }
            )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = root / "ledger.jsonl.gz"
            with ledger.open("wb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as handle:
                    for group in groups:
                        handle.write(
                            (json.dumps(group, sort_keys=True, separators=(",", ":")) + "\n").encode()
                        )
            expected_sha = hashlib.sha256(ledger.read_bytes()).hexdigest()
            output = root / "output"

            receipt = recalc.run_recalculation(
                ledger_path=ledger,
                out_dir=output,
                expected_ledger_sha256=expected_sha,
                expected_group_count=2,
                expected_record_count=2,
            )

            self.assertEqual(receipt["completed_event_groups"], 2)
            self.assertEqual(receipt["completed_native_mbo_records"], 2)
            self.assertEqual(receipt["discovery_contract"]["maximum_family_count"], None)
            with gzip.open(output / "exact-members.jsonl.gz", "rt", encoding="utf-8") as handle:
                members = [json.loads(line) for line in handle]
            self.assertEqual([row["group_index"] for row in members], [0, 1])
            self.assertTrue(all(row["structural_state"] == "OPEN_WORLD_UNASSIGNED" for row in members))
            self.assertEqual(members[0]["book"]["after"]["bid_depth_full"], 4)
            self.assertEqual(members[1]["book"]["after"]["ask_depth_full"], 7)
            self.assertEqual(len(json.loads((output / "family-index.json").read_text())["families"]), 2)


if __name__ == "__main__":
    unittest.main()
