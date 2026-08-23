from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from ng_exhaustion_mbo_5y_step1_census_20260822 import (
    CensusError,
    DeterministicGzipJsonlWriter,
    OVERLAP_WEEKS,
    REVISION,
    RULESET,
    SecondAggregator,
    _object_dates_for_weeks,
    _iter_seconds_weeks,
    _segment_objects,
    _match_events,
    _resumable_segment_receipt,
    _verified_child_outputs,
    build_crosswalk,
    compare_lineage,
    expanding_folds,
    legacy_overlap_receipt,
    lineage_population,
    ruleset_sha256,
    sha256_json,
)


def event(week: str, idx: int, polarity: int = 1, family: str = "A"):
    return {
        "event_id": f"{week}-{idx:06d}-{polarity:+d}",
        "week_sunday": week,
        "t0_idx": idx,
        "polarity": polarity,
        "family": family,
        "dynamic_endpoint": {"causal_confirmation_idx": idx + 10},
    }


class SecondAggregatorTests(unittest.TestCase):
    def test_preserves_legacy_projection_and_native_trade_semantics(self):
        aggregator = SecondAggregator()
        frame = {
            "ts_event_ns": 2_000_000_000,
            "ts_recv_ns": 2_000_000_100,
            "raw_symbol": "NGX6",
            "instrument_id": 10,
            "raw_actions": [{
                "action": "T", "side": "B", "size": 3,
                "source_dbn_object": "x.dbn.zst", "source_dbn_sha256": "a" * 64,
            }],
            "book": {
                "spread": 0.001, "depth_imbalance_full": 0.2,
                "bid_depth_full": 10, "ask_depth_full": 5,
                "bid_order_count_full": 2, "ask_order_count_full": 1,
                "bid_price_level_count_full": 1, "ask_price_level_count_full": 1,
            },
            "activity": {"20": {"event_count": 1}},
            "integrity": {},
        }
        envelope = {
            "compact_event_frame": frame,
            "full_depth_exposed": True,
        }
        legacy = [{
            "action": "T", "price": 3.1, "size": 3,
            "bid_px_00": 3.0, "ask_px_00": 3.05,
            **{f"bid_sz_{i:02d}": 1 for i in range(10)},
            **{f"ask_sz_{i:02d}": 2 for i in range(10)},
        }]
        aggregator.consume(envelope, legacy)
        row = aggregator.seconds[2]
        self.assertEqual(row["legacy_buy_qty"], 3)
        self.assertEqual(row["native_buy_qty"], 3)
        self.assertEqual(row["source_dbn_sha256"], "a" * 64)
        self.assertTrue(row["native_state"]["full_depth_exposed_in_process"])

    def test_streaming_flush_is_ordered_and_memory_bounded(self):
        emitted = []
        aggregator = SecondAggregator(emit=emitted.append, reorder_tolerance_s=1)
        for second in (10, 11, 12):
            envelope = {
                "compact_event_frame": {
                    "ts_event_ns": second * 1_000_000_000,
                    "ts_recv_ns": second * 1_000_000_000,
                    "raw_symbol": "NGX6", "instrument_id": 1,
                    "raw_actions": [],
                    "book": {
                        "spread": None, "depth_imbalance_full": None,
                        "bid_depth_full": 0, "ask_depth_full": 0,
                        "bid_order_count_full": 0, "ask_order_count_full": 0,
                        "bid_price_level_count_full": 0, "ask_price_level_count_full": 0,
                    },
                    "activity": {}, "integrity": {},
                },
                "full_depth_exposed": True,
            }
            aggregator.consume(envelope, [])
        aggregator.finish()
        self.assertEqual([x["epoch_second"] for x in emitted], [10, 11, 12])
        self.assertEqual(aggregator.seconds, {})


class EquivalenceTests(unittest.TestCase):
    def test_exact_revealed_overlap_passes(self):
        rows = []
        for week in OVERLAP_WEEKS:
            rows.extend(event(week, i * 50) for i in range(20))
        receipt, mismatches = legacy_overlap_receipt(rows, [dict(x) for x in rows])
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["matched_event_count"], 60)
        self.assertEqual(mismatches, [])
        self.assertEqual(receipt["mismatch_policy"], RULESET)

    def test_every_mismatch_is_retained_and_gate_fails(self):
        expected = [event(OVERLAP_WEEKS[0], i * 50) for i in range(20)]
        actual = [dict(x) for x in expected[:-3]]
        actual.append(event(OVERLAP_WEEKS[0], 2000, polarity=-1))
        receipt, mismatches = legacy_overlap_receipt(expected, actual)
        self.assertEqual(receipt["status"], "FAIL_CLOSED")
        self.assertEqual(receipt["retained_mismatch_count"], len(mismatches))
        self.assertEqual(sum(x["kind"] == "FROZEN_ONLY" for x in mismatches), 3)
        self.assertEqual(sum(x["kind"] == "LEGACY_CONTROL_ONLY" for x in mismatches), 1)

    def test_matching_is_one_to_one(self):
        left = [event(OVERLAP_WEEKS[0], 100), event(OVERLAP_WEEKS[0], 101)]
        right = [event(OVERLAP_WEEKS[0], 100)]
        matches, missing, extras = _match_events(left, right)
        self.assertEqual(len(matches), 1)
        self.assertEqual(len(missing), 1)
        self.assertEqual(extras, [])

    def test_lineage_comparison_retains_depth_and_sign_disagreement(self):
        base = {
            "origin_event_id": "origin",
            "consecutive_all_models_positive_depth_candidate": 1,
            "incremental_gain": {
                "ridge": {"1": 0.1, "2": -0.1, "3": None},
                "knn": {"1": 0.1, "2": -0.1, "3": None},
                "extra_trees": {"1": 0.1, "2": -0.1, "3": None},
            },
        }
        changed = {
            **base,
            "consecutive_all_models_positive_depth_candidate": 0,
            "incremental_gain": {
                **base["incremental_gain"],
                "ridge": {"1": -0.1, "2": -0.1, "3": None},
            },
        }
        result, mismatches = compare_lineage([base], [changed])
        self.assertEqual(result["depth_agreement_on_common_origins"], 0.0)
        self.assertEqual(result["sign_agreement_on_comparable_cells"], 5 / 6)
        self.assertEqual(sum(x["kind"] == "LINEAGE_DEPTH_DISAGREEMENT" for x in mismatches), 1)
        self.assertEqual(sum(x["kind"] == "LINEAGE_GAIN_SIGN_DISAGREEMENT" for x in mismatches), 1)


class PartitionTests(unittest.TestCase):
    def test_expanding_folds_are_disjoint_and_cover_post_training_weeks(self):
        weeks = [f"W{i:03d}" for i in range(131)]
        folds = expanding_folds(weeks)
        tested = [w for _, test, _ in folds for w in test]
        self.assertEqual(tested, weeks[52:])
        self.assertEqual(len(tested), len(set(tested)))
        for train, test, _ in folds:
            self.assertFalse(set(train) & set(test))
            self.assertLess(max(weeks.index(x) for x in train), min(weeks.index(x) for x in test))


class RecoveryAndReconciliationTests(unittest.TestCase):
    def test_overlap_object_selection_is_exactly_revealed_calendar_weeks(self):
        objects = []
        for day in ("20250712", "20250713", "20250718", "20250720"):
            objects.append({
                "segment": "20250701_20250801",
                "key": f"prefix/glbx-mdp3-{day}.mbo.dbn.zst",
                "bytes": 1,
            })
        manifest = {"canonical_dbn_objects": objects}
        selected = _segment_objects(
            manifest,
            "20250701_20250801",
            _object_dates_for_weeks({"20250713"}),
        )
        self.assertEqual([row["key"] for row in selected], [
            "prefix/glbx-mdp3-20250713.mbo.dbn.zst",
            "prefix/glbx-mdp3-20250718.mbo.dbn.zst",
        ])

    def test_deterministic_writer_is_atomic_and_byte_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            left = Path(tmp) / "left.jsonl.gz"
            right = Path(tmp) / "right.jsonl.gz"
            rows = [{"b": 2, "a": 1}, {"x": "y"}]
            receipts = []
            for path in (left, right):
                writer = DeterministicGzipJsonlWriter(path)
                for row in rows:
                    writer.write(row)
                receipts.append(writer.close())
            self.assertEqual(receipts[0]["gzip_sha256"], receipts[1]["gzip_sha256"])
            self.assertFalse(left.with_suffix(left.suffix + ".partial").exists())

    def test_restart_resume_requires_exact_engine_source_and_output_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            segment = "20250101_20250201"
            seconds = out / f"{segment}.seconds.jsonl.gz"
            writer = DeterministicGzipJsonlWriter(seconds)
            writer.write({"epoch_second": 1})
            output = writer.close()
            manifest = {"manifest_sha256": "m" * 64}
            engine = {"runner": "e" * 64}
            source_scope = {"mode": "FULL_CANONICAL_SEGMENT"}
            receipt = {
                "schema": "NG_EXHAUSTION_MBO_5Y_STEP1_SEGMENT_RECEIPT_V1",
                "revision": REVISION,
                "segment": segment,
                "source_manifest_sha256": manifest["manifest_sha256"],
                "source_scope": source_scope,
                "engine_hashes": engine,
                "ruleset_sha256": ruleset_sha256(),
                "status": "SEGMENT_COMPLETE",
                "seconds_output": output,
            }
            receipt["receipt_sha256"] = sha256_json(receipt)
            (out / f"{segment}.receipt.json").write_text(json.dumps(receipt))
            self.assertIsNotNone(_resumable_segment_receipt(manifest, segment, out, engine, source_scope))
            seconds.write_bytes(b"drift")
            self.assertIsNone(_resumable_segment_receipt(manifest, segment, out, engine, source_scope))

    def test_parent_verifies_exact_child_receipt_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            segment = "20250101_20250201"
            seconds = out / f"{segment}.seconds.jsonl.gz"
            writer = DeterministicGzipJsonlWriter(seconds)
            writer.write({"epoch_second": 1})
            output = writer.close()
            manifest = {"manifest_sha256": "m" * 64}
            receipt = {
                "status": "SEGMENT_COMPLETE",
                "segment": segment,
                "source_manifest_sha256": manifest["manifest_sha256"],
                "ruleset_sha256": ruleset_sha256(),
                "seconds_output": output,
            }
            receipt["receipt_sha256"] = sha256_json(receipt)
            receipt["receipt_sha256"] = "0" * 64
            (out / f"{segment}.receipt.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(CensusError, "child receipt hash drift"):
                _verified_child_outputs(manifest, out, [segment])

    def test_reconciliation_clips_cross_job_warmup_to_half_open_segment_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            left_segment = "20250901_20251001"
            right_segment = "20251001_20251101"
            boundary = 1759276800
            paths = []
            for segment, seconds in (
                (left_segment, (boundary - 2, boundary - 1)),
                (right_segment, (boundary - 20, boundary - 1, boundary, boundary + 1)),
            ):
                path = tmp / f"{segment}.seconds.jsonl.gz"
                writer = DeterministicGzipJsonlWriter(path)
                for second in seconds:
                    writer.write({"epoch_second": second})
                writer.close()
                paths.append(path)
            audit = {}
            weeks = list(_iter_seconds_weeks(paths, None, [left_segment, right_segment], audit))
            emitted = [row["epoch_second"] for _, rows in weeks for row in rows]
            self.assertEqual(emitted, [boundary - 2, boundary - 1, boundary, boundary + 1])
            self.assertEqual(audit["excluded_out_of_interval_seconds"], 2)
            self.assertEqual(audit["segments"][right_segment]["excluded_before_start"], 2)
            self.assertEqual(
                audit["retention"],
                "RAW_CHILD_OUTPUTS_AND_RECEIPTS_RETAIN_EXCLUDED_WARMUP_ROWS",
            )

    def test_reconciliation_still_fails_on_in_segment_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            segment = "20251001_20251101"
            path = Path(tmp) / f"{segment}.seconds.jsonl.gz"
            writer = DeterministicGzipJsonlWriter(path)
            writer.write({"epoch_second": 1759276800})
            writer.write({"epoch_second": 1759276800})
            writer.close()
            with self.assertRaisesRegex(CensusError, "child segment non-increasing/duplicate"):
                list(_iter_seconds_weeks([path], None, [segment], {}))

    def test_parent_recovery_requires_pinned_engine_scope_receipt_and_seconds(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            segment = "20251001_20251101"
            seconds = out / f"{segment}.seconds.jsonl.gz"
            writer = DeterministicGzipJsonlWriter(seconds)
            writer.write({"epoch_second": 1759276800})
            output = writer.close()
            manifest = {"manifest_sha256": "m" * 64}
            engine = {"runner": "e" * 64}
            scope = {"mode": "REVEALED_OVERLAP_DAILY_OBJECTS"}
            receipt = {
                "status": "SEGMENT_COMPLETE",
                "segment": segment,
                "source_manifest_sha256": manifest["manifest_sha256"],
                "ruleset_sha256": ruleset_sha256(),
                "engine_hashes": engine,
                "source_scope": scope,
                "seconds_output": output,
            }
            receipt["receipt_sha256"] = sha256_json(receipt)
            (out / f"{segment}.receipt.json").write_text(json.dumps(receipt))
            pins = {
                segment: {
                    "receipt_sha256": receipt["receipt_sha256"],
                    "seconds_gzip_sha256": output["gzip_sha256"],
                    "seconds_rows": output["rows"],
                }
            }
            paths, hashes = _verified_child_outputs(
                manifest,
                out,
                [segment],
                expected_engine_hashes=engine,
                expected_source_scopes={segment: scope},
                pinned_children=pins,
            )
            self.assertEqual(paths, [seconds])
            self.assertEqual(hashes, [receipt["receipt_sha256"]])
            pins[segment]["seconds_gzip_sha256"] = "0" * 64
            with self.assertRaisesRegex(CensusError, "recovery seconds pin drift"):
                _verified_child_outputs(
                    manifest,
                    out,
                    [segment],
                    expected_engine_hashes=engine,
                    expected_source_scopes={segment: scope},
                    pinned_children=pins,
                )

    def test_crosswalk_retains_split_edges_without_false_orphan(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            legacy_path = tmp / "legacy.gz"
            native_path = tmp / "native.gz"
            output_path = tmp / "crosswalk.gz"
            base = {
                "week_sunday": "20250105", "polarity": 1, "family": "A",
                "realized_structural_depth": 1, "reset_event_id": None, "unresolved": False,
            }
            legacy = [{**base, "event_id": "L", "t0_idx": 100, "chain_id": "LC"}]
            native = [
                {**base, "event_id": "V1", "t0_idx": 99, "chain_id": "VC1"},
                {**base, "event_id": "V2", "t0_idx": 101, "chain_id": "VC2"},
            ]
            for path, rows in ((legacy_path, legacy), (native_path, native)):
                writer = DeterministicGzipJsonlWriter(path)
                for row in rows:
                    writer.write(row)
                writer.close()
            _, summary = build_crosswalk(legacy_path, native_path, output_path)
            with gzip.open(output_path, "rt") as handle:
                rows = [json.loads(line) for line in handle]
            self.assertEqual([row["status"] for row in rows], ["SPLIT", "SPLIT"])
            self.assertEqual(summary["v4_native_full_only"], 0)
            self.assertEqual(summary["primary_matches"], 1)

    def test_lineage_population_streams_and_retains_unscored_training_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            inputs = tmp / "inputs.gz"
            population = tmp / "population.gz"
            index = tmp / "index.gz"
            writer = DeterministicGzipJsonlWriter(inputs)
            for i in range(2):
                writer.write({
                    "event_id": f"E{i}", "week_sunday": "20250105",
                    "sequence_index": i, "t0_idx": 100 + i * 10,
                    "polarity": 1, "family": "A",
                    "previous_event_id": None if i == 0 else "E0",
                    "next_event_id": "E1" if i == 0 else None,
                    "causal_confirmation_idx": 105 + i * 10,
                    "behavior_vector_full": [1.0] * 22,
                    "source_boundary_censored": False,
                    "source_provenance": {
                        "source_dbn_key": "exact.dbn.zst",
                        "source_dbn_sha256": "a" * 64,
                        "contract_resolution_status": "RESOLVED_FROM_DBN_METADATA",
                    },
                    "native_structure": None,
                })
            writer.close()
            output, summary, _ = lineage_population(
                inputs, "LEGACY_CONTROL", {"runner": "b" * 64}, population, index
            )
            self.assertEqual(output["rows"], 2)
            self.assertEqual(summary["population_count"], 2)
            self.assertEqual(summary["depth_histogram"], {0: 2})
            with gzip.open(population, "rt") as handle:
                rows = [json.loads(line) for line in handle]
            self.assertTrue(all(row["unresolved"] for row in rows))
            self.assertTrue(all(row["retention_policy"] == RULESET for row in rows))


if __name__ == "__main__":
    unittest.main()
