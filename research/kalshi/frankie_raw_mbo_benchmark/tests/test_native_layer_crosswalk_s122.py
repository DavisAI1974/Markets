"""S122 slice 4 on the crosswalk: F-27, F-29, F-feed-4, F-feed-8, F-feed-10, the withheld sealed
rows, and the A_MEMORY default.

- F-27: bound-ness is read off the registry's actual source_paths
  (`native_knowledge_delivery.layers_bound_only_to`), never off a static producer flag.
- F-29: `clock_lock_time` computes PRINCIPAL_STAMPED - its producer is his own
  `output_first_locks_and_no_locks` ledger - and the gate accepts it while the pre-call stamp
  (READY_CAUSAL_STREAM) still reads as a disagreement.
- F-feed-4: "carrier absent" and "census absent" are different facts and different statuses;
  with a ledger dir the crosswalk censuses the delivered member ledger's first rows (bounded).
- F-feed-8: one authority for carriers - the per-group set the stream must claim is DERIVED
  from the per-layer producer records.
- F-feed-10: the arm is read off the result's identity receipt; a mismatch is refused.
"""
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
from research.kalshi.frankie_raw_mbo_benchmark.native_layer_crosswalk import (
    INPUT_POLICIES,
    LAYER_PRODUCERS,
    SEVEN_CLOCKS,
    STATUS_MEANING,
    SUNDAY_CLI,
    CrosswalkError,
    CrosswalkGateError,
    crosswalk,
    gate_applicable_inputs,
    group_carriers_from_producers,
    main,
    observed_carriers,
    pre_call_status_computed,
    render_crosswalk_table,
)
from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_layer_crosswalk import (
    delivery_receipt,
    fixture,
    rows_by_id,
    sealed_proof,
)

DOC_ONLY_LAYERS = [b.layer_id for b in KNOWLEDGE_LAYER_SOURCES]


def bound_to_doc(registry: dict, layer_id: str) -> dict:
    stale = json.loads(json.dumps(registry))
    for group in stale["groups"]:
        for entry in group["entries"]:
            if entry["layer_id"] == layer_id:
                entry["source_paths"] = [FEED_INVENTORY_PATH]
    return stale


class BoundnessIsReadOffTheRegistryTest(unittest.TestCase):
    """F-27."""

    def test_no_producer_record_carries_the_static_flag_any_more(self) -> None:
        for layer_id, record in LAYER_PRODUCERS.items():
            with self.subTest(layer=layer_id):
                self.assertNotIn("bound_to_inventory_document", record)

    def test_on_the_rebound_registry_with_no_receipt_the_knowledge_layers_are_produced_not_delivered(self) -> None:
        registry = load_registry()
        self.assertEqual(layers_bound_only_to(registry, FEED_INVENTORY_PATH, policies=KNOWLEDGE_INPUT_POLICIES), [])
        rows = rows_by_id(crosswalk(registry, arm="A_MEMORY"))
        for layer_id in DOC_ONLY_LAYERS:
            with self.subTest(layer=layer_id):
                self.assertEqual(rows[layer_id]["status"], "PRODUCED_NOT_DELIVERED")
                self.assertNotEqual(rows[layer_id]["evidence"]["kind"], "INVENTORY_DOCUMENT")
        self.assertEqual(crosswalk(registry, arm="A_MEMORY")["totals"]["bound_to_inventory_document"], 0)

    def test_a_layer_the_registry_binds_only_to_the_document_reads_bound_even_with_a_receipt_row(self) -> None:
        stale = bound_to_doc(load_registry(), "complete_s105_9_brain")
        receipt = {
            "schema": "FRANKIE_KNOWLEDGE_DELIVERY_RECEIPT_V1", "receipt_sha256": "1" * 64,
            "layers": [{"layer_id": "complete_s105_9_brain", "status": "DELIVERED",
                        "files": [{"path": FEED_INVENTORY_PATH, "sha256": "a" * 64, "bytes": 1}]}],
        }
        rows = rows_by_id(crosswalk(stale, arm="A_MEMORY", knowledge_receipt=receipt))
        self.assertEqual(rows["complete_s105_9_brain"]["status"], "BOUND_TO_INVENTORY_DOCUMENT")
        self.assertEqual(rows["complete_s105_9_brain"]["evidence"]["kind"], "INVENTORY_DOCUMENT")
        self.assertEqual(rows["doctrine_reasoning_play_index_evidence"]["status"], "PRODUCED_NOT_DELIVERED")

    def test_the_knowledge_producer_records_cite_the_registrys_keep_files_as_carriers(self) -> None:
        by_id = {b.layer_id: b for b in KNOWLEDGE_LAYER_SOURCES}
        for layer_id, binding in by_id.items():
            with self.subTest(layer=layer_id):
                record = LAYER_PRODUCERS[layer_id]
                self.assertEqual(record["kind"], "FILE")
                self.assertEqual(tuple(record["carrier_paths"]), tuple(binding.paths))


class LockTimeIsPrincipalStampedTest(unittest.TestCase):
    """F-29."""

    def test_clock_lock_time_computes_principal_stamped_naming_his_ledger(self) -> None:
        rows = rows_by_id(crosswalk(load_registry(), arm="A_MEMORY"))
        row = rows["clock_lock_time"]
        self.assertEqual(row["status"], "PRINCIPAL_STAMPED")
        self.assertIn("output_first_locks_and_no_locks", row["evidence"]["carrier"])
        self.assertEqual(row["evidence"]["kind"], "PRINCIPAL_OUTPUT_LEDGER")
        self.assertIn("PRINCIPAL_STAMPED", STATUS_MEANING)
        self.assertEqual(SEVEN_CLOCKS["clock_lock_time"]["principal_ledger"], "output_first_locks_and_no_locks")
        self.assertEqual(LAYER_PRODUCERS["clock_lock_time"]["kind"], "NO_PRODUCER_FOUND", "no INPUT producer, still")

    def test_the_gate_accepts_principal_stamped_and_refuses_everything_else(self) -> None:
        cw = crosswalk(load_registry(), arm="A_MEMORY")
        for row in cw["layers"]:
            if row["arm_applicable"] and row["policy"] in INPUT_POLICIES and row["layer_id"] != "clock_lock_time":
                row["status"] = "DELIVERED"
        self.assertIsNone(gate_applicable_inputs(cw))
        cw = crosswalk(load_registry(), arm="A_MEMORY")
        with self.assertRaises(CrosswalkGateError) as caught:
            gate_applicable_inputs(cw)
        self.assertNotIn("clock_lock_time", str(caught.exception))
        self.assertIn("fifo_queues", str(caught.exception))

    def test_the_pre_call_stamp_still_reads_as_a_disagreement(self) -> None:
        registry = load_registry()
        comparison = {r["layer_id"]: r for r in pre_call_status_computed(crosswalk(registry, arm="A_MEMORY"), registry=registry)}
        self.assertEqual(comparison["clock_lock_time"]["policy_stamp"], "READY_CAUSAL_STREAM")
        self.assertEqual(comparison["clock_lock_time"]["computed_status"], "PRINCIPAL_STAMPED")
        self.assertFalse(comparison["clock_lock_time"]["agree"])

    def test_totals_count_principal_stamped_and_the_input_gate_counts_it_as_accounted(self) -> None:
        totals = crosswalk(load_registry(), arm="A_MEMORY")["totals"]
        self.assertEqual(totals["principal_stamped"], 1)
        self.assertEqual(totals["inputs_accounted"], totals["inputs_delivered"] + totals["principal_stamped"])

    def test_an_outputs_receipt_naming_his_lock_ledger_is_reflected_in_the_detail(self) -> None:
        receipt = {"schema": "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_OUTPUTS_RECEIPT_V1",
                   "ledgers": ["output_first_locks_and_no_locks"], "receipt_sha256": "2" * 64}
        rows = rows_by_id(crosswalk(load_registry(), arm="A_MEMORY", outputs_receipt=receipt))
        self.assertEqual(rows["clock_lock_time"]["status"], "PRINCIPAL_STAMPED")
        self.assertIn("filed", rows["clock_lock_time"]["evidence"]["detail"])
        self.assertEqual(rows["clock_lock_time"]["evidence"]["receipt_sha256"], "2" * 64)


class CensusAbsentIsNotCarrierAbsentTest(unittest.TestCase):
    """F-feed-4."""

    @classmethod
    def setUpClass(cls) -> None:
        fx = fixture()
        cls.result = fx["result"]
        cls.registry = fx["registry"]
        cls.receipt = delivery_receipt(cls.result)
        cls.ledger_dir = Path(cls.result["ledger_retention"]["exact_member_ledger"]["path"]).parent

    def _without_census(self) -> dict:
        stripped = json.loads(json.dumps(self.result))
        stripped["layers"]["exact_member_ledger"].pop("field_census", None)
        return stripped

    def test_a_result_without_a_census_and_no_ledger_reads_carrier_unmeasured_not_absent(self) -> None:
        rows = rows_by_id(crosswalk(self.registry, arm="A_CLEAN", result=self._without_census(), delivery_receipt=self.receipt))
        self.assertEqual(rows["fifo_queues"]["status"], "CARRIER_UNMEASURED")
        self.assertIn("census", rows["fifo_queues"]["evidence"]["detail"])
        self.assertIn("CARRIER_UNMEASURED", STATUS_MEANING)
        with self.assertRaisesRegex(CrosswalkGateError, "fifo_queues=CARRIER_UNMEASURED"):
            gate_applicable_inputs(crosswalk(self.registry, arm="A_CLEAN", result=self._without_census(), delivery_receipt=self.receipt))

    def test_with_a_ledger_dir_the_delivered_member_ledger_is_censused_and_the_carrier_is_found(self) -> None:
        observed = observed_carriers(self._without_census(), delivery_receipt=self.receipt, ledger_dir=self.ledger_dir)
        self.assertEqual(observed["member_paths_source"], "DELIVERED_LEDGER_FIRST_ROWS")
        self.assertIn("book_full.bid_levels_full[].fifo_queue[].volume_ahead", observed["member_paths"])
        self.assertGreater(observed["member_rows"], 0)
        self.assertIn("rows", observed["member_scan_bound"])
        self.assertIn("bytes", observed["member_scan_bound"])
        rows = rows_by_id(crosswalk(self.registry, arm="A_CLEAN", result=self._without_census(),
                                    delivery_receipt=self.receipt, ledger_dir=self.ledger_dir))
        self.assertEqual(rows["fifo_queues"]["status"], "DELIVERED")
        self.assertEqual(rows["order_lifecycle_adds"]["status"], "RECEIPTED_CARRIER_ABSENT")

    def test_the_results_own_census_is_preferred_over_the_ledger_scan_when_present(self) -> None:
        observed = observed_carriers(self.result, delivery_receipt=self.receipt, ledger_dir=self.ledger_dir)
        self.assertEqual(observed["member_paths_source"], "RESULT_FIELD_CENSUS")

    def test_a_carrier_genuinely_absent_from_a_censused_run_still_reads_absent(self) -> None:
        rows = rows_by_id(crosswalk(self.registry, arm="A_CLEAN", result=self.result, delivery_receipt=self.receipt))
        self.assertEqual(rows["order_lifecycle_adds"]["status"], "RECEIPTED_CARRIER_ABSENT")
        self.assertEqual(rows["fifo_queues"]["status"], "DELIVERED")


class OneCarrierAuthorityTest(unittest.TestCase):
    """F-feed-8."""

    def test_group_carriers_are_derived_from_the_producer_records_in_the_streams_vocabulary(self) -> None:
        registry = load_registry()
        derived = group_carriers_from_producers(registry)
        self.assertEqual(set(derived), set(LAYER_CARRIERS), "the stream's groups and the derived groups are the same set")
        for group_id, carriers in derived.items():
            with self.subTest(group=group_id):
                self.assertTrue(set(carriers) <= {"member", "lifecycle", "legacy"})
                self.assertEqual(list(carriers), sorted(set(carriers)))
        self.assertIn("lifecycle", derived["microstructure_mechanics"])
        self.assertIn("legacy", derived["order_lifecycle"])

    @unittest.expectedFailure
    def test_the_streams_layer_carriers_equal_the_derived_set_f_feed_8_pins_the_disagreement(self) -> None:
        """EXPECTED TO FAIL until native_causal_stream derives LAYER_CARRIERS from
        group_carriers_from_producers (the clocks persona's file). When it does, this test
        passes unexpectedly and the decorator comes off - the disagreement cannot go quiet."""
        derived = group_carriers_from_producers(load_registry())
        self.assertEqual({g: tuple(c) for g, c in derived.items()}, {g: tuple(sorted(c)) for g, c in LAYER_CARRIERS.items()})


class ArmIsReadOffTheResultTest(unittest.TestCase):
    """F-feed-10."""

    def test_an_arm_that_is_not_the_results_identity_arm_is_refused_by_name(self) -> None:
        fx = fixture()
        with self.assertRaisesRegex(CrosswalkError, "A_MEMORY.*A_CLEAN|A_CLEAN.*A_MEMORY"):
            crosswalk(fx["registry"], arm="A_MEMORY", result=fx["result"])

    def test_the_cli_defaults_to_a_memory_without_a_result_and_to_the_results_arm_with_one(self) -> None:
        fx = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_json = root / "cw.json"
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                self.assertEqual(main(["--json", str(out_json)]), 0)
            self.assertEqual(json.loads(out_json.read_text())["arm"], "A_MEMORY")
            result_path = root / "calculation_result.json"
            result_path.write_text(json.dumps(fx["result"]), encoding="utf-8")
            with redirect_stdout(buffer):
                self.assertEqual(main(["--result", str(result_path), "--json", str(out_json)]), 0)
            self.assertEqual(json.loads(out_json.read_text())["arm"], "A_CLEAN")
            err = io.StringIO()
            with redirect_stdout(buffer), redirect_stderr(err):
                self.assertEqual(main(["--result", str(result_path), "--arm", "A_MEMORY", "--json", str(out_json)]), 2)
            self.assertIn("A_CLEAN", err.getvalue())

    def test_the_sunday_cli_example_names_the_memory_arm(self) -> None:
        self.assertIn("--arm A_MEMORY", SUNDAY_CLI)
        self.assertNotIn("A_CLEAN", SUNDAY_CLI)


class SealedRowsWithheldTest(unittest.TestCase):
    def test_the_prompt_render_withholds_the_sealed_rows_and_states_the_count_and_proof(self) -> None:
        registry = load_registry()
        proof = sealed_proof(True)
        cw = crosswalk(registry, arm="A_MEMORY", sealed_proof=proof)
        sealed_ids = [e["layer_id"] for g in registry["groups"] if g["policy"] == "SEALED_FOR_A_SCOPE" for e in g["entries"]]
        withheld = render_crosswalk_table(cw, registry=registry, withhold_sealed=True)
        full = render_crosswalk_table(cw, registry=registry)
        for layer_id in sealed_ids:
            with self.subTest(layer=layer_id):
                self.assertNotIn(layer_id, withheld)
                self.assertIn(layer_id, full)
        self.assertIn(f"{len(sealed_ids)} sealed", withheld)
        self.assertIn("3" * 12, withheld)
        self.assertIn("SEALED_PROVEN", withheld)
        table_rows = [line for line in withheld.splitlines() if line.startswith("| ") and "`" in line.split("|")[2]]
        self.assertEqual(len(table_rows), cw["totals"]["registered"] - len(sealed_ids))


if __name__ == "__main__":
    unittest.main()
