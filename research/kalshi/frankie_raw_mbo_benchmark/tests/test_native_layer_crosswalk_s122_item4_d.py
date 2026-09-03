"""S122 Item 4 Task D: five measured crosswalk defects, tests first."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark.native_causal_stream import LAYER_CARRIERS
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import load_registry
from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
    FEED_INVENTORY_PATH,
    KNOWLEDGE_INPUT_POLICIES,
    KNOWLEDGE_LAYER_SOURCES,
    layers_bound_only_to,
)
from research.kalshi.frankie_raw_mbo_benchmark import native_layer_crosswalk as xw
from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_layer_crosswalk import (
    delivery_receipt,
    fixture,
    rows_by_id,
)

DOC_ONLY_LAYERS = [binding.layer_id for binding in KNOWLEDGE_LAYER_SOURCES]


def bind_only_to_feed_doc(registry: dict, layer_id: str) -> dict:
    stale = json.loads(json.dumps(registry))
    for group in stale["groups"]:
        for entry in group["entries"]:
            if entry["layer_id"] == layer_id:
                entry["source_paths"] = [FEED_INVENTORY_PATH]
    return stale


class D1CensusAbsentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fx = fixture()
        cls.result = fx["result"]
        cls.registry = fx["registry"]
        cls.receipt = delivery_receipt(cls.result)
        cls.ledger_dir = Path(cls.result["ledger_retention"]["exact_member_ledger"]["path"]).parent

    def without_census(self) -> dict:
        stripped = json.loads(json.dumps(self.result))
        stripped["layers"]["exact_member_ledger"].pop("field_census", None)
        return stripped

    def test_missing_census_is_not_carrier_absent(self) -> None:
        rows = rows_by_id(xw.crosswalk(self.registry, arm="A_CLEAN", result=self.without_census(),
                                       delivery_receipt=self.receipt))
        self.assertEqual(rows["fifo_queues"]["status"], "CENSUS_ABSENT")
        self.assertIn("CENSUS_ABSENT", xw.STATUS_MEANING)
        with self.assertRaisesRegex(xw.CrosswalkGateError, "fifo_queues=CENSUS_ABSENT"):
            xw.gate_applicable_inputs(xw.crosswalk(self.registry, arm="A_CLEAN", result=self.without_census(),
                                                   delivery_receipt=self.receipt))

    def test_ledger_dir_recovers_member_fields_and_reports_a_complete_scan(self) -> None:
        observed = xw.observed_carriers(self.without_census(), delivery_receipt=self.receipt,
                                        ledger_dir=self.ledger_dir)
        self.assertEqual(observed["member_paths_source"], "DELIVERED_LEDGER_FIRST_ROWS")
        self.assertIn("book_full.bid_levels_full[].fifo_queue[].volume_ahead", observed["member_paths"])
        self.assertGreater(observed["member_rows"], 0)
        self.assertIn("rows", observed["member_scan_bound"])
        self.assertIn("bytes", observed["member_scan_bound"])
        self.assertTrue(observed["member_scan_bound"]["reached_end"])
        self.assertFalse(observed["member_scan_bound"]["truncated"])
        self.assertEqual(
            observed["member_rows"], observed["member_scan_bound"]["rows_read"]
        )
        rows = rows_by_id(xw.crosswalk(self.registry, arm="A_CLEAN", result=self.without_census(),
                                       delivery_receipt=self.receipt, ledger_dir=self.ledger_dir))
        self.assertEqual(rows["fifo_queues"]["status"], "DELIVERED")
        self.assertIn(
            "reached end after "
            f"{observed['member_scan_bound']['rows_read']} rows / "
            f"{observed['member_scan_bound']['bytes_read']} bytes",
            rows["fifo_queues"]["evidence"]["detail"],
        )
        # Task A landed first: raw actions are now a real member carrier.
        self.assertEqual(rows["order_lifecycle_adds"]["status"], "DELIVERED")

    def test_result_census_is_preferred_and_a_genuinely_empty_section_stays_absent(self) -> None:
        observed = xw.observed_carriers(self.result, delivery_receipt=self.receipt, ledger_dir=self.ledger_dir)
        self.assertEqual(observed["member_paths_source"], "RESULT_FIELD_CENSUS")
        rows = rows_by_id(xw.crosswalk(self.registry, arm="A_CLEAN", result=self.result,
                                       delivery_receipt=self.receipt))
        self.assertEqual(rows["prebirth_predecessor_at_risk_state"]["status"], "RECEIPTED_CARRIER_ABSENT")


class D2OneCarrierAuthorityTest(unittest.TestCase):
    def test_group_carriers_are_derived_from_layer_producers(self) -> None:
        from research.kalshi.frankie_raw_mbo_benchmark.native_layer_crosswalk import group_carriers_from_producers
        derived = group_carriers_from_producers(load_registry())
        self.assertEqual(set(derived), set(LAYER_CARRIERS))
        for group_id, carriers in derived.items():
            with self.subTest(group=group_id):
                self.assertEqual(list(carriers), sorted(set(carriers)))
                self.assertTrue(set(carriers) <= {"member", "lifecycle", "legacy"})
        self.assertIn("lifecycle", derived["microstructure_mechanics"])
        self.assertIn("legacy", derived["order_lifecycle"])

    def test_stream_authority_equals_derived_authority(self) -> None:
        from research.kalshi.frankie_raw_mbo_benchmark.native_layer_crosswalk import group_carriers_from_producers
        derived = group_carriers_from_producers(load_registry())
        self.assertEqual({g: tuple(v) for g, v in derived.items()}, LAYER_CARRIERS)


class D3ResultArmTest(unittest.TestCase):
    def test_conflicting_explicit_arm_is_refused(self) -> None:
        fx = fixture()
        with self.assertRaisesRegex(xw.CrosswalkError, "A_MEMORY.*A_CLEAN|A_CLEAN.*A_MEMORY"):
            xw.crosswalk(fx["registry"], arm="A_MEMORY", result=fx["result"])

    def test_cli_uses_memory_without_result_and_result_arm_when_present(self) -> None:
        fx = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_json = root / "cw.json"
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(xw.main(["--json", str(out_json)]), 0)
            self.assertEqual(json.loads(out_json.read_text())["arm"], "A_MEMORY")
            result_path = root / "result.json"
            result_path.write_text(json.dumps(fx["result"]), encoding="utf-8")
            with redirect_stdout(output):
                self.assertEqual(xw.main(["--result", str(result_path), "--json", str(out_json)]), 0)
            self.assertEqual(json.loads(out_json.read_text())["arm"], "A_CLEAN")
            err = io.StringIO()
            with redirect_stdout(output), redirect_stderr(err):
                self.assertEqual(xw.main(["--result", str(result_path), "--arm", "A_MEMORY",
                                          "--json", str(out_json)]), 2)
            self.assertIn("A_CLEAN", err.getvalue())


class D4ComputedStatusesTest(unittest.TestCase):
    def test_boundness_is_computed_from_registry_not_producer_flag(self) -> None:
        registry = load_registry()
        self.assertEqual(layers_bound_only_to(registry, FEED_INVENTORY_PATH,
                                              policies=KNOWLEDGE_INPUT_POLICIES), [])
        rows = rows_by_id(xw.crosswalk(registry, arm="A_MEMORY"))
        for layer_id in DOC_ONLY_LAYERS:
            with self.subTest(layer=layer_id):
                self.assertNotIn("bound_to_inventory_document", xw.LAYER_PRODUCERS[layer_id])
                self.assertEqual(rows[layer_id]["status"], "PRODUCED_NOT_DELIVERED")
        self.assertEqual(xw.crosswalk(registry, arm="A_MEMORY")["totals"]["bound_to_inventory_document"], 0)

    def test_true_doc_only_binding_overrides_a_receipt_claim(self) -> None:
        stale = bind_only_to_feed_doc(load_registry(), "complete_s105_9_brain")
        receipt = {"schema": xw.KNOWLEDGE_RECEIPT_SCHEMA, "receipt_sha256": "1" * 64,
                   "layers": [{"layer_id": "complete_s105_9_brain", "status": "DELIVERED",
                               "files": [{"path": FEED_INVENTORY_PATH, "sha256": "a" * 64, "bytes": 1}]}]}
        rows = rows_by_id(xw.crosswalk(stale, arm="A_MEMORY", knowledge_receipt=receipt))
        self.assertEqual(rows["complete_s105_9_brain"]["status"], "BOUND_TO_INVENTORY_DOCUMENT")

    def test_knowledge_producers_cite_the_keep_files(self) -> None:
        for binding in KNOWLEDGE_LAYER_SOURCES:
            with self.subTest(layer=binding.layer_id):
                record = xw.LAYER_PRODUCERS[binding.layer_id]
                self.assertEqual(record["kind"], "FILE")
                self.assertEqual(tuple(record["carrier_paths"]), tuple(binding.paths))

    def test_lock_time_is_principal_stamped_and_gate_accounted(self) -> None:
        cw = xw.crosswalk(load_registry(), arm="A_MEMORY")
        rows = rows_by_id(cw)
        row = rows["clock_lock_time"]
        self.assertEqual(row["status"], "PRINCIPAL_STAMPED")
        self.assertEqual(row["evidence"]["kind"], "PRINCIPAL_OUTPUT_LEDGER")
        self.assertIn("output_first_locks_and_no_locks", row["evidence"]["carrier"])
        self.assertEqual(xw.SEVEN_CLOCKS["clock_lock_time"]["principal_ledger"],
                         "output_first_locks_and_no_locks")
        self.assertEqual(xw.LAYER_PRODUCERS["clock_lock_time"]["kind"], "NO_PRODUCER_FOUND")
        for candidate in cw["layers"]:
            if candidate["arm_applicable"] and candidate["policy"] in xw.INPUT_POLICIES and candidate["layer_id"] != "clock_lock_time":
                candidate["status"] = "DELIVERED"
        self.assertIsNone(xw.gate_applicable_inputs(cw))
        self.assertEqual(cw["totals"]["inputs_accounted"],
                         cw["totals"]["inputs_delivered"] + cw["totals"]["principal_stamped"])

    def test_principal_stamp_still_disagrees_with_pre_call_policy_stamp(self) -> None:
        registry = load_registry()
        comparison = {r["layer_id"]: r for r in xw.pre_call_status_computed(
            xw.crosswalk(registry, arm="A_MEMORY"), registry=registry)}
        self.assertEqual(comparison["clock_lock_time"]["computed_status"], "PRINCIPAL_STAMPED")
        self.assertFalse(comparison["clock_lock_time"]["agree"])


class D5CliDefaultTest(unittest.TestCase):
    def test_sunday_example_and_cli_default_are_memory(self) -> None:
        self.assertIn("--arm A_MEMORY", xw.SUNDAY_CLI)
        self.assertNotIn("--arm A_CLEAN", xw.SUNDAY_CLI)


if __name__ == "__main__":
    unittest.main()
