"""The 99-layer crosswalk: every registry layer to the code that produces it and the carrier
that delivers it, verified against a row a real traversal wrote.

Two rules from Greg's 2026-09-02 rulings shape every test here. No historical number is a spec:
the layer set is read off the registry at test time and the producer table must equal it
exactly, so adding or removing a layer breaks this file loudly rather than silently widening a
gap. And a gate that reads status off a policy is not a gate: the crosswalk's status is
COMPUTED from receipts and from the field census of a produced row, never stamped from the
policy - which is why the comparison against `build_pre_call_receipt` is asserted to
DISAGREE on today's registry.

Every citation in `LAYER_PRODUCERS` is mechanically verifiable: the cited file must exist and
contain the cited symbol (line numbers move and are informational only). The seven clock rows
and the activity-window rows are expected to change at merge when the clock producers land;
these tests are what proves the new citations resolve.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark import native_a_arm_launch as launcher
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import load_registry
from research.kalshi.frankie_raw_mbo_benchmark.native_layer_crosswalk import (
    CROSSWALK_SCHEMA,
    INPUT_POLICIES,
    KNOWLEDGE_RECEIPT_SCHEMA,
    LAYER_PRODUCERS,
    OUTPUTS_RECEIPT_SCHEMA,
    PRODUCER_KINDS,
    REPO_ROOT,
    SEALED_PROOF_SCHEMA,
    SEVEN_CLOCKS,
    STATUSES,
    CrosswalkError,
    CrosswalkGateError,
    FIXTURE_RENDER_PATH,
    SUNDAY_CLI,
    crosswalk,
    fixture_render,
    gate_applicable_inputs,
    main,
    path_present,
    pre_call_status_computed,
    registry_layers,
    render_crosswalk_table,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_mbo_field_census import MboFieldCensus
from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_a_arm_launch import slice_records

REQUIRED_KEYS = {"kind", "module", "symbol", "file", "line", "carrier", "notes"}


class LayerProducersCoverTheRegistryTest(unittest.TestCase):
    def test_the_producer_key_set_equals_the_registry_layer_set_exactly(self):
        """Not a count. The SET. A layer added to the registry with no producer row, or a
        producer row for a layer that no longer exists, fails here by name."""
        registry = load_registry()
        expected = {layer_id for layer_id, _binding in registry_layers(registry).items()}
        self.assertEqual(set(LAYER_PRODUCERS), expected)

    def test_every_record_carries_the_producer_schema(self):
        for layer_id, record in LAYER_PRODUCERS.items():
            with self.subTest(layer_id=layer_id):
                self.assertTrue(REQUIRED_KEYS.issubset(record), sorted(REQUIRED_KEYS - set(record)))
                self.assertIn(record["kind"], PRODUCER_KINDS)
                self.assertIsInstance(record["carrier"], str)
                self.assertTrue(record["carrier"].strip(), "a producer must name its carrier")
                self.assertTrue(record["notes"].strip(), "a producer must say what it is")
                if record["line"] is not None:
                    self.assertIsInstance(record["line"], int)
                    self.assertGreater(record["line"], 0)

    def test_every_cited_file_exists_and_contains_its_symbol(self):
        """Coordinator adjustment 2: file and symbol, not the line, so the table cannot cite
        code that is not there. When the clock producers land, the seven clock records are
        updated and this proves the new citations resolve."""
        for layer_id, record in LAYER_PRODUCERS.items():
            if record["file"] is None:
                continue
            with self.subTest(layer_id=layer_id, file=record["file"]):
                path = REPO_ROOT / record["file"]
                self.assertTrue(path.is_file(), f"{record['file']} does not exist")
                if record["symbol"] is not None:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    needle = record["symbol"].split(".")[-1]
                    self.assertIn(needle, text, f"{record['file']} does not contain {needle!r}")

    def test_every_carrier_document_the_static_layers_cite_exists(self):
        """A FILE producer's carrier is a repository path; a carrier that is not there is a
        producer that is not there, whatever the notes say."""
        for layer_id, record in LAYER_PRODUCERS.items():
            if record["kind"] not in {"FILE", "SECTION"}:
                continue
            for carrier in record.get("carrier_paths", ()):
                with self.subTest(layer_id=layer_id, carrier=carrier):
                    self.assertTrue((REPO_ROOT / carrier).is_file(), carrier)

    def test_no_committed_citation_names_a_path_outside_the_repository(self):
        """D34. Repo-relative paths, S3 keys and hashes only."""
        for layer_id, record in LAYER_PRODUCERS.items():
            with self.subTest(layer_id=layer_id):
                blob = json.dumps(record)
                self.assertNotIn("/tmp/", blob)
                self.assertNotIn("scratchpad", blob)
                self.assertNotRegex(blob, r"[A-Za-z]:[\\/]")
                if record["file"] is not None:
                    self.assertFalse(record["file"].startswith("/"), record["file"])

    def test_no_producer_found_records_say_what_was_searched(self):
        found_any = False
        for layer_id, record in LAYER_PRODUCERS.items():
            if record["kind"] != "NO_PRODUCER_FOUND":
                continue
            found_any = True
            with self.subTest(layer_id=layer_id):
                self.assertIn("searched", record["notes"].lower())
                self.assertIsNone(record["file"])
        self.assertTrue(found_any, "lock time is Frankie's output and must read NO_PRODUCER_FOUND today")

    def test_kinds_follow_the_registry_policy(self):
        """Outputs are his to write, sealed layers are sealed objects, shadows are shadows.
        Everything else must name a producer or say NO_PRODUCER_FOUND."""
        registry = load_registry()
        for layer_id, binding in registry_layers(registry).items():
            policy = binding["group"]["policy"]
            kind = LAYER_PRODUCERS[layer_id]["kind"]
            with self.subTest(layer_id=layer_id, policy=policy):
                if policy == "APPEND_ONLY_OUTPUT":
                    self.assertEqual(kind, "PRINCIPAL_OUTPUT")
                elif policy == "SEALED_FOR_A_SCOPE":
                    self.assertEqual(kind, "SEALED_OBJECT")
                elif policy == "PROVISIONAL_SHADOW":
                    self.assertEqual(kind, "SHADOW")
                else:
                    self.assertNotIn(kind, {"PRINCIPAL_OUTPUT", "SEALED_OBJECT", "SHADOW"})


class PathPatternTest(unittest.TestCase):
    def test_a_literal_path_matches_itself_only(self):
        paths = {"book_full.spread", "book_full.spread_raw"}
        self.assertTrue(path_present("book_full.spread", paths))
        self.assertFalse(path_present("book_full.mid", paths))

    def test_a_star_matches_exactly_one_segment_so_a_window_key_is_never_hardcoded(self):
        paths = {"activity.1.add_cancel_churn", "activity.300.add_cancel_churn", "activity.1.x.add_cancel_churn"}
        self.assertTrue(path_present("activity.*.add_cancel_churn", paths))
        self.assertFalse(path_present("activity.*.event_count", paths))
        self.assertFalse(path_present("activity.*.x.*.add_cancel_churn", paths))

    def test_list_markers_are_literal_not_character_classes(self):
        paths = {"book_full.bid_levels_full[].fifo_queue[].order_id"}
        self.assertTrue(path_present("book_full.bid_levels_full[].fifo_queue[].order_id", paths))
        self.assertFalse(path_present("book_full.bid_levels_full[].fifo_queue[].size", paths))


class ProducersVerifiedByExecutionTest(unittest.TestCase):
    """The census of a row the real traversal wrote is the ground truth for every carrier."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        groups = 12
        cls.result = launcher.launch(
            arm="A_CLEAN", run_id="crosswalk-fixture", sources=[],
            source_manifest={"manifest_hash": "e" * 64, "total_mbo_records": 5_667_689},
            out_dir=root, code_commit="cafebabe", limit_records=groups * 4,
            checkpoint_every_records=10**9, cadence_groups=10**9,
            records=slice_records(groups), stream_ledgers=True,
        )
        ledgers = cls.result["evidence_identity"]["exact_ledgers"]
        cls.member_rows = [
            json.loads(line) for line in Path(ledgers["exact_member_rows"]).read_text().splitlines() if line.strip()
        ]
        census = MboFieldCensus()
        for row in cls.member_rows:
            census.observe(row)
        cls.member_paths = set(census.paths())
        cls.lifecycle_sections = {
            json.loads(line).get("emitting_section")
            for line in Path(ledgers["exact_lifecycle_rows"]).read_text().splitlines() if line.strip()
        }
        legacy = [json.loads(line) for line in Path(ledgers["legacy_observable_rows"]).read_text().splitlines() if line.strip()]
        cls.legacy_keys = set().union(*(row.keys() for row in legacy)) if legacy else set()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_the_fixture_row_is_the_forty_eight_field_member_row(self):
        """Not a spec, a check that the fixture is the real thing: the S120 handoff measured
        48 top-level fields on the delivered Sunday ledger and this row must be that shape."""
        self.assertGreater(len(self.member_rows), 0)
        self.assertIn("book_full", self.member_rows[0])
        self.assertIn("clocks", self.member_rows[0])
        self.assertTrue(path_present("book_full.bid_levels_full[].fifo_queue[].volume_ahead", self.member_paths))

    def test_every_member_carrier_path_the_producers_cite_is_present_in_the_fixture_row(self):
        for layer_id, record in LAYER_PRODUCERS.items():
            for pattern in record.get("member_paths", ()):
                with self.subTest(layer_id=layer_id, path=pattern):
                    self.assertTrue(
                        path_present(pattern, self.member_paths),
                        f"{layer_id}: {pattern} is cited as the carrier and is not on the row",
                    )

    def test_every_surviving_aggregate_cited_is_present_in_the_fixture_row(self):
        for layer_id, record in LAYER_PRODUCERS.items():
            for pattern in record.get("aggregates_present", ()):
                with self.subTest(layer_id=layer_id, path=pattern):
                    self.assertTrue(path_present(pattern, self.member_paths), f"{layer_id}: {pattern}")

    def test_structurally_absent_carriers_are_in_fact_absent_from_the_row(self):
        """Remaining absence declarations are measured; F-30 raw actions are now carriers."""
        raw_action_pins = []
        for layer_id, record in LAYER_PRODUCERS.items():
            for pattern in record.get("structurally_absent", ()):
                if pattern.startswith("raw_actions"):
                    raw_action_pins.append((layer_id, pattern))
                with self.subTest(layer_id=layer_id, path=pattern):
                    self.assertFalse(
                        path_present(pattern, self.member_paths),
                        f"{layer_id}: {pattern} is now on the row; update the producer record",
                    )
        self.assertEqual(raw_action_pins, [])
        self.assertIn("raw_actions", self.member_rows[0])
        for path in ("raw_actions[]", "raw_actions[].action", "raw_actions[].order_id",
                     "raw_actions[].source_dbn_sha256", "raw_actions[].source_dbn_object",
                     "raw_actions[].is_snapshot", "raw_actions[].book_effect"):
            self.assertTrue(path_present(path, self.member_paths), path)

    def test_every_lifecycle_section_cited_is_emitted_unless_declared_fixture_dependent(self):
        for layer_id, record in LAYER_PRODUCERS.items():
            for section in record.get("lifecycle_sections", ()):
                if section in record.get("fixture_dependent_sections", ()):
                    continue
                with self.subTest(layer_id=layer_id, section=section):
                    self.assertIn(section, self.lifecycle_sections, f"{layer_id}: {section}")

    def test_fixture_dependent_sections_are_ones_the_driver_really_emits(self):
        """Declaring a section fixture-dependent must not become a way to cite a section the
        driver never writes. The driver's own `section=` literals are the authority."""
        driver = (REPO_ROOT / "research/kalshi/frankie_raw_mbo_benchmark/native_replay_driver.py").read_text()
        emitted = set(re.findall(r'section="([a-z_]+)"', driver))
        for layer_id, record in LAYER_PRODUCERS.items():
            for section in record.get("lifecycle_sections", ()):
                with self.subTest(layer_id=layer_id, section=section):
                    self.assertIn(section, emitted)

    def test_every_legacy_key_cited_is_on_a_legacy_row(self):
        for layer_id, record in LAYER_PRODUCERS.items():
            for key in record.get("legacy_keys", ()):
                with self.subTest(layer_id=layer_id, key=key):
                    self.assertIn(key, self.legacy_keys, f"{layer_id}: {key}")

    def test_every_causal_stream_layer_declares_its_ledgers_and_at_least_one_carrier_or_absence(self):
        registry = load_registry()
        for layer_id, binding in registry_layers(registry).items():
            if binding["group"]["policy"] != "CAUSAL_STREAM_REQUIRED":
                continue
            record = LAYER_PRODUCERS[layer_id]
            with self.subTest(layer_id=layer_id):
                if record["kind"] == "NO_PRODUCER_FOUND":
                    continue
                self.assertTrue(record.get("ledgers"), "a causal layer must name the ledger that carries it")
                declared = (
                    record.get("member_paths", ()) or record.get("lifecycle_sections", ())
                    or record.get("legacy_keys", ()) or record.get("structurally_absent", ())
                )
                self.assertTrue(declared, "a causal layer must name a carrier or the carrier it lost")


class SevenClocksTest(unittest.TestCase):
    """Each of the registry's seven clocks is mapped to a producer or says NO_PRODUCER_FOUND."""

    def test_the_seven_clocks_are_the_registry_clock_layers(self):
        registry = load_registry()
        clock_layers = {
            layer_id for layer_id, binding in registry_layers(registry).items()
            if binding["group"]["group_id"] == "causal_clocks"
        }
        self.assertEqual(set(SEVEN_CLOCKS), clock_layers)

    def test_lock_time_is_frankies_output_and_has_no_input_producer(self):
        record = LAYER_PRODUCERS["clock_lock_time"]
        self.assertEqual(record["kind"], "NO_PRODUCER_FOUND")
        self.assertIn("output_first_locks_and_no_locks", record["notes"])

    def test_each_clock_row_says_which_row_field_or_none_it_maps_to(self):
        for layer_id, row in SEVEN_CLOCKS.items():
            with self.subTest(layer_id=layer_id):
                self.assertIn("clock", row)
                self.assertIn("producer", row)
                self.assertIn("row_fields", row)
                self.assertIn("receipt_key", row)
                self.assertIn("coverage", row)
                self.assertEqual(row["producer"], LAYER_PRODUCERS[layer_id]["kind"] != "NO_PRODUCER_FOUND")

    def test_the_row_clocks_object_has_five_fields_and_the_receipt_four_and_the_table_says_which(self):
        """The measurement Greg named: seven clocks in the registry, five fields on the row,
        four keys on the group receipt. Every row field and receipt key the table cites must
        be one that exists."""
        from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import GROUP_CLOCK_KEYS
        row_fields = {
            "first_component_ts_event_ns", "first_component_ts_recv_ns", "f_last_ts_recv_ns",
            "first_lawful_availability_ns", "decision_ts_recv_ns",
        }
        for layer_id, row in SEVEN_CLOCKS.items():
            with self.subTest(layer_id=layer_id):
                for field in row["row_fields"]:
                    self.assertIn(field.removeprefix("clocks."), row_fields | {"ts_event_ns", "ts_recv_ns"})
                if row["receipt_key"] is not None:
                    self.assertIn(row["receipt_key"], GROUP_CLOCK_KEYS)



# --------------------------------------------------------------------------------------
# Slice 2: the computed crosswalk
# --------------------------------------------------------------------------------------
_FIXTURE: dict | None = None


def fixture() -> dict:
    """One real traversal over the shared slice records, launched once for the module."""
    global _FIXTURE
    if _FIXTURE is None:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        groups = 12
        result = launcher.launch(
            arm="A_CLEAN", run_id="crosswalk-fixture", sources=[],
            source_manifest={"manifest_hash": "e" * 64, "total_mbo_records": 5_667_689},
            out_dir=root, code_commit="cafebabe", limit_records=groups * 4,
            checkpoint_every_records=10**9, cadence_groups=10**9,
            records=slice_records(groups), stream_ledgers=True,
        )
        _FIXTURE = {"tmp": tmp, "root": root, "result": result, "registry": load_registry()}
    return _FIXTURE


def delivery_receipt(result: dict, *, statuses: dict | None = None, sha_override: dict | None = None) -> dict:
    """A FRANKIE_LEDGER_DELIVERY_RECEIPT_V1 as fetch_frankie_ledgers writes it, over the
    fixture's real ledger files, hashed for real."""
    from research.kalshi.frankie_raw_mbo_benchmark.fetch_frankie_ledgers import LEDGER_FILES, RECEIPT_SCHEMA
    from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import canonical_hash
    statuses = statuses or {}
    sha_override = sha_override or {}
    ledgers = {}
    for name, plain in LEDGER_FILES.items():
        path = Path(result["ledger_retention"][name]["path"])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        ledgers[name] = {
            "file": plain, "object": plain + ".gz", "status": statuses.get(name, "VERIFIED"),
            "local_path": str(path), "gz_bytes_expected": None, "gz_bytes_observed": None,
            "plain_bytes_expected": path.stat().st_size, "plain_bytes_observed": path.stat().st_size,
            "plain_sha256_expected": digest, "plain_sha256_observed": sha_override.get(name, digest),
        }
    body = {
        "schema": RECEIPT_SCHEMA, "run_id": "fixture-run", "run_prefix": "fixture/prefix",
        "bucket": "fixture-bucket", "manifest_sha256": "f" * 64, "fetched_at": "2026-09-02T00:00:00Z",
        "out_dir": "fixture", "ledgers": ledgers, "objects": {},
        "all_ledgers_verified": all(v["status"] == "VERIFIED" for v in ledgers.values()),
        "receipt_sha256": "",
    }
    body["receipt_sha256"] = canonical_hash(body, omit="receipt_sha256")
    return body


def knowledge_receipt(rows: list[dict]) -> dict:
    return {"schema": KNOWLEDGE_RECEIPT_SCHEMA, "layers": rows, "receipt_sha256": "1" * 64}


def outputs_receipt(ledgers) -> dict:
    return {"schema": OUTPUTS_RECEIPT_SCHEMA, "ledgers": ledgers, "receipt_sha256": "2" * 64}


def sealed_proof(all_absent: bool = True) -> dict:
    return {"schema": SEALED_PROOF_SCHEMA, "all_absent": all_absent, "tokens_checked": 40, "receipt_sha256": "3" * 64}


def rows_by_id(cw: dict) -> dict[str, dict]:
    return {row["layer_id"]: row for row in cw["layers"]}


class CrosswalkShapeTest(unittest.TestCase):
    def test_one_row_per_registry_layer_with_the_schema_and_a_verifying_hash(self):
        from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import canonical_hash
        registry = load_registry()
        cw = crosswalk(registry, arm="A_CLEAN")
        self.assertEqual(cw["schema"], CROSSWALK_SCHEMA)
        self.assertEqual(cw["arm"], "A_CLEAN")
        self.assertEqual({r["layer_id"] for r in cw["layers"]}, set(registry_layers(registry)))
        self.assertEqual(cw["crosswalk_sha256"], canonical_hash(cw, omit="crosswalk_sha256"))
        for row in cw["layers"]:
            with self.subTest(layer_id=row["layer_id"]):
                self.assertEqual(
                    set(row), {"layer_id", "group_id", "policy", "arm_applicable", "producer", "status", "evidence"}
                )
                self.assertIn(row["status"], STATUSES)
                self.assertEqual(set(row["evidence"]), {"kind", "receipt_sha256", "carrier", "detail"})
                self.assertIsInstance(row["arm_applicable"], bool)

    def test_totals_are_derived_at_call_time_from_the_rows(self):
        registry = load_registry()
        cw = crosswalk(registry, arm="A_CLEAN")
        totals = cw["totals"]
        self.assertEqual(totals["registered"], len(registry_layers(registry)))
        self.assertEqual(totals["applicable"], sum(r["arm_applicable"] for r in cw["layers"]))
        self.assertEqual(
            totals["inputs_applicable"],
            sum(r["arm_applicable"] and r["policy"] in INPUT_POLICIES for r in cw["layers"]),
        )
        self.assertEqual(sum(totals["by_status"].values()), totals["registered"])
        for status in STATUSES:
            self.assertIn(status, totals["by_status"])

    def test_a_layer_whose_group_excludes_the_arm_is_not_applicable(self):
        cw = rows_by_id(crosswalk(load_registry(), arm="A_CLEAN"))
        self.assertEqual(cw["a_memory_promoted_positive_capsule"]["status"], "NOT_APPLICABLE")
        self.assertFalse(cw["a_memory_promoted_positive_capsule"]["arm_applicable"])
        memory = rows_by_id(crosswalk(load_registry(), arm="A_MEMORY"))
        self.assertNotEqual(memory["a_memory_promoted_positive_capsule"]["status"], "NOT_APPLICABLE")
        self.assertEqual(memory["a_clean_promoted_positive_capsule"]["status"], "NOT_APPLICABLE")

    def test_an_unknown_arm_is_refused(self):
        with self.assertRaises(CrosswalkError):
            crosswalk(load_registry(), arm="B_ARM")


class StatusIsComputedNeverStampedTest(unittest.TestCase):
    """With NO receipts and NO result, nothing may read DELIVERED, whatever the policy says."""

    def setUp(self):
        self.cw = rows_by_id(crosswalk(load_registry(), arm="A_CLEAN"))

    def test_nothing_is_delivered_without_evidence(self):
        self.assertEqual([r["layer_id"] for r in self.cw.values() if r["status"] == "DELIVERED"], [])

    def test_knowledge_layers_bound_to_the_inventory_document_say_so(self):
        for layer_id in ("complete_s105_9_brain", "learned_d_structures_and_families", "october_outcome_wall_enforcement"):
            with self.subTest(layer_id=layer_id):
                self.assertEqual(self.cw[layer_id]["status"], "BOUND_TO_INVENTORY_DOCUMENT")
                self.assertEqual(self.cw[layer_id]["evidence"]["kind"], "INVENTORY_DOCUMENT")

    def test_the_mission_and_contract_are_produced_but_not_delivered_until_a_receipt_names_them(self):
        for layer_id in ("controlling_rt_mission", "native_calculation_contract"):
            with self.subTest(layer_id=layer_id):
                self.assertEqual(self.cw[layer_id]["status"], "PRODUCED_NOT_DELIVERED")

    def test_causal_layers_with_a_producer_and_no_run_are_produced_not_delivered(self):
        self.assertEqual(self.cw["fifo_queues"]["status"], "PRODUCED_NOT_DELIVERED")
        self.assertEqual(self.cw["order_lifecycle_adds"]["status"], "PRODUCED_NOT_DELIVERED")

    def test_lock_time_has_no_producer(self):
        self.assertEqual(self.cw["clock_lock_time"]["status"], "NO_PRODUCER_FOUND")

    def test_sealed_layers_are_unproven_without_an_absence_proof(self):
        self.assertEqual(self.cw["step1_result_prefixes"]["status"], "SEALED_UNPROVEN")

    def test_shadows_are_disabled_and_outputs_pending(self):
        self.assertEqual(self.cw["hipporag_associative_retrieval"]["status"], "SHADOW_DISABLED")
        self.assertEqual(self.cw["output_probability_movie"]["status"], "OUTPUT_PENDING")


class StatusAgainstARealRunTest(unittest.TestCase):
    """The fixture result plus a delivery receipt over the fixture's own ledger files."""

    @classmethod
    def setUpClass(cls):
        fx = fixture()
        cls.result = fx["result"]
        cls.registry = fx["registry"]
        cls.receipt = delivery_receipt(cls.result)
        cls.cw = rows_by_id(crosswalk(cls.registry, arm="A_CLEAN", result=cls.result, delivery_receipt=cls.receipt))

    def test_a_carrier_on_the_row_with_a_verified_receipt_is_delivered_and_names_the_receipt(self):
        row = self.cw["fifo_queues"]
        self.assertEqual(row["status"], "DELIVERED")
        self.assertEqual(row["evidence"]["kind"], "DELIVERY_RECEIPT")
        self.assertEqual(row["evidence"]["receipt_sha256"], self.receipt["receipt_sha256"])
        self.assertIn("fifo_queue", row["evidence"]["carrier"])

    def test_raw_action_layers_are_delivered_when_the_verified_member_carrier_is_present(self):
        """F-30: the receipt and the measured row now agree that raw actions were delivered."""
        for layer_id in ("order_lifecycle_adds", "native_acmrtfn_messages", "order_lifecycle_cancels"):
            with self.subTest(layer_id=layer_id):
                row = self.cw[layer_id]
                self.assertEqual(row["status"], "DELIVERED")
                self.assertIn("raw_actions", row["evidence"]["detail"])

    def test_a_lifecycle_section_the_run_never_emitted_is_receipted_carrier_absent_and_says_zero_rows(self):
        row = self.cw["prebirth_predecessor_at_risk_state"]
        self.assertEqual(row["status"], "RECEIPTED_CARRIER_ABSENT")
        self.assertIn("episode", row["evidence"]["detail"])
        self.assertIn("0 rows", row["evidence"]["detail"])

    def test_a_legacy_layer_is_delivered_off_the_legacy_ledger(self):
        row = self.cw["legacy_book_imbalance"]
        self.assertEqual(row["status"], "DELIVERED")
        self.assertIn("legacy_observable_rows", row["evidence"]["carrier"])

    def test_the_clock_rows_read_as_the_measurement_says(self):
        self.assertEqual(self.cw["clock_event_time"]["status"], "DELIVERED")
        self.assertEqual(self.cw["clock_model_evaluation"]["status"], "DELIVERED")
        self.assertEqual(self.cw["clock_prospective_discovery_confirmation"]["status"], "RECEIPTED_CARRIER_ABSENT")
        self.assertEqual(self.cw["clock_lock_time"]["status"], "NO_PRODUCER_FOUND")

    def test_the_totals_count_the_over_claims(self):
        cw = crosswalk(self.registry, arm="A_CLEAN", result=self.result, delivery_receipt=self.receipt)
        totals = cw["totals"]
        self.assertGreater(totals["receipted_carrier_absent"], 0)
        self.assertGreater(totals["delivered"], 0)
        self.assertEqual(totals["by_status"]["RECEIPTED_CARRIER_ABSENT"], totals["receipted_carrier_absent"])

    def test_a_result_without_a_receipt_is_produced_not_delivered_even_when_the_carrier_is_present(self):
        cw = rows_by_id(crosswalk(self.registry, arm="A_CLEAN", result=self.result))
        row = cw["fifo_queues"]
        self.assertEqual(row["status"], "PRODUCED_NOT_DELIVERED")
        self.assertIn("no VERIFIED delivery receipt", row["evidence"]["detail"])

    def test_a_ledger_that_did_not_verify_delivers_nothing_it_carries(self):
        receipt = delivery_receipt(self.result, statuses={"legacy_observable_rows": "SHA_MISMATCH"})
        cw = rows_by_id(crosswalk(self.registry, arm="A_CLEAN", result=self.result, delivery_receipt=receipt))
        self.assertEqual(cw["legacy_book_imbalance"]["status"], "PRODUCED_NOT_DELIVERED")
        self.assertIn("SHA_MISMATCH", cw["legacy_book_imbalance"]["evidence"]["detail"])
        self.assertEqual(cw["fifo_queues"]["status"], "DELIVERED", "the member ledger still verified")

    def test_a_delivered_ledger_that_is_not_this_runs_ledger_is_refused_by_the_sink_sha(self):
        """Comparison against an independent source: the sink hashed the file as it wrote it."""
        receipt = delivery_receipt(self.result, sha_override={"exact_member_ledger": "0" * 64})
        cw = rows_by_id(crosswalk(self.registry, arm="A_CLEAN", result=self.result, delivery_receipt=receipt))
        self.assertEqual(cw["fifo_queues"]["status"], "PRODUCED_NOT_DELIVERED")
        self.assertIn("sink", cw["fifo_queues"]["evidence"]["detail"])

    def test_a_delivery_receipt_of_another_schema_is_refused(self):
        receipt = dict(delivery_receipt(self.result), schema="SOMETHING_ELSE")
        with self.assertRaises(CrosswalkError):
            crosswalk(self.registry, arm="A_CLEAN", result=self.result, delivery_receipt=receipt)

    def test_a_delivery_receipt_whose_hash_does_not_verify_is_refused(self):
        receipt = dict(delivery_receipt(self.result), receipt_sha256="0" * 64)
        with self.assertRaises(CrosswalkError):
            crosswalk(self.registry, arm="A_CLEAN", result=self.result, delivery_receipt=receipt)

    def test_a_stream_receipt_flags_a_carrier_claim_the_declared_carrier_does_not_hold(self):
        from research.kalshi.frankie_raw_mbo_benchmark.native_causal_stream import CausalGroupStream
        ledgers = self.result["evidence_identity"]["exact_ledgers"]
        stream = CausalGroupStream(
            ledgers["exact_member_rows"], ledgers["exact_lifecycle_rows"], ledgers["legacy_observable_rows"],
            run_id="crosswalk-fixture", arm="A_CLEAN", registry=self.registry,
        )
        list(stream.iterate())
        stream_receipt = stream.stream_receipt()
        cw = crosswalk(self.registry, arm="A_CLEAN", result=self.result, delivery_receipt=self.receipt,
                       stream_receipt=stream_receipt)
        rows = rows_by_id(cw)
        self.assertIn("carrier claim", rows["legacy_structure_observables"]["evidence"]["detail"])
        self.assertIn("carrier claim", rows["clock_prospective_discovery_confirmation"]["evidence"]["detail"])
        self.assertGreaterEqual(cw["totals"]["carrier_claim_mismatches"], 2)
        self.assertEqual(cw["stream_receipt_sha256"], stream_receipt["receipt_sha256"])


class InterlockReceiptsTest(unittest.TestCase):
    """The shapes being built in parallel are accepted by duck-typing beyond their named keys."""

    def test_a_knowledge_receipt_row_delivers_a_static_layer_and_names_the_receipt(self):
        receipt = knowledge_receipt([
            {"layer_id": "complete_s105_9_brain", "status": "DELIVERED",
             "files": [{"path": "knowledge/ng_brain.json", "sha256": "a" * 64, "bytes": 10}]},
            {"layer_id": "learned_d_structures_and_families", "status": "EXCLUDED", "files": []},
        ])
        cw = rows_by_id(crosswalk(load_registry(), arm="A_CLEAN", knowledge_receipt=receipt))
        self.assertEqual(cw["complete_s105_9_brain"]["status"], "DELIVERED")
        self.assertEqual(cw["complete_s105_9_brain"]["evidence"]["kind"], "KNOWLEDGE_RECEIPT")
        self.assertEqual(cw["complete_s105_9_brain"]["evidence"]["receipt_sha256"], "1" * 64)
        self.assertIn("knowledge/ng_brain.json", cw["complete_s105_9_brain"]["evidence"]["carrier"])
        self.assertEqual(cw["learned_d_structures_and_families"]["status"], "PRODUCED_NOT_DELIVERED")
        self.assertIn("EXCLUDED", cw["learned_d_structures_and_families"]["evidence"]["detail"])
        # A layer the receipt does not mention keeps its computed status.
        self.assertEqual(cw["october_outcome_wall_enforcement"]["status"], "BOUND_TO_INVENTORY_DOCUMENT")

    def test_a_knowledge_receipt_delivering_a_layer_with_no_files_is_not_believed(self):
        receipt = knowledge_receipt([{"layer_id": "complete_s105_9_brain", "status": "DELIVERED", "files": []}])
        cw = rows_by_id(crosswalk(load_registry(), arm="A_CLEAN", knowledge_receipt=receipt))
        self.assertNotEqual(cw["complete_s105_9_brain"]["status"], "DELIVERED")
        self.assertIn("no files", cw["complete_s105_9_brain"]["evidence"]["detail"])

    def test_a_knowledge_receipt_of_another_schema_is_refused(self):
        with self.assertRaises(CrosswalkError):
            crosswalk(load_registry(), arm="A_CLEAN", knowledge_receipt={"schema": "X", "layers": [], "receipt_sha256": "1" * 64})

    def test_an_outputs_receipt_files_the_ledgers_it_names_in_either_shape(self):
        as_dict = outputs_receipt({"output_probability_movie": {"entries": 3, "head_hash": "b" * 64}})
        as_list = outputs_receipt(["output_probability_movie"])
        for shape, receipt in (("mapping", as_dict), ("list", as_list)):
            with self.subTest(shape=shape):
                cw = rows_by_id(crosswalk(load_registry(), arm="A_CLEAN", outputs_receipt=receipt))
                self.assertEqual(cw["output_probability_movie"]["status"], "OUTPUT_FILED")
                self.assertEqual(cw["output_probability_movie"]["evidence"]["receipt_sha256"], "2" * 64)
                self.assertIn(shape, cw["output_probability_movie"]["evidence"]["detail"])
                self.assertEqual(cw["output_candidate_discoveries"]["status"], "OUTPUT_PENDING")

    def test_a_sealed_absence_proof_proves_the_nine_sealed_layers(self):
        cw = rows_by_id(crosswalk(load_registry(), arm="A_CLEAN", sealed_proof=sealed_proof(True)))
        sealed = [r for r in cw.values() if r["policy"] == "SEALED_FOR_A_SCOPE"]
        self.assertTrue(sealed)
        for row in sealed:
            with self.subTest(layer_id=row["layer_id"]):
                self.assertEqual(row["status"], "SEALED_PROVEN")
                self.assertEqual(row["evidence"]["receipt_sha256"], "3" * 64)
        cw = rows_by_id(crosswalk(load_registry(), arm="A_CLEAN", sealed_proof=sealed_proof(False)))
        self.assertEqual(cw["step1_populations"]["status"], "SEALED_UNPROVEN")


class GateTest(unittest.TestCase):
    """Item 7: the function the coordinator wires as the spawn gate."""

    def test_the_gate_refuses_today_and_names_every_applicable_input_that_is_not_delivered(self):
        cw = crosswalk(load_registry(), arm="A_CLEAN")
        with self.assertRaises(CrosswalkGateError) as caught:
            gate_applicable_inputs(cw)
        message = str(caught.exception)
        for layer_id in ("complete_s105_9_brain", "order_lifecycle_adds", "controlling_rt_mission"):
            self.assertIn(layer_id, message)
        # Never the non-inputs.
        for layer_id in ("step1_populations", "output_probability_movie", "hipporag_associative_retrieval",
                         "a_memory_promoted_positive_capsule"):
            self.assertNotIn(layer_id, message)

    def test_the_gate_passes_only_when_every_applicable_input_is_delivered(self):
        cw = crosswalk(load_registry(), arm="A_CLEAN")
        for row in cw["layers"]:
            if row["arm_applicable"] and row["policy"] in INPUT_POLICIES:
                row["status"] = "DELIVERED"
        self.assertIsNone(gate_applicable_inputs(cw))

    def test_one_missing_input_is_enough_to_refuse(self):
        cw = crosswalk(load_registry(), arm="A_CLEAN")
        for row in cw["layers"]:
            if row["arm_applicable"] and row["policy"] in INPUT_POLICIES:
                row["status"] = "DELIVERED"
        rows = rows_by_id(cw)
        rows["fifo_queues"]["status"] = "RECEIPTED_CARRIER_ABSENT"
        with self.assertRaisesRegex(CrosswalkGateError, "fifo_queues"):
            gate_applicable_inputs(cw)


class PolicyStampVersusComputedTest(unittest.TestCase):
    """The measurement behind the whole item: the pre-call receipt stamps status off the
    policy; the crosswalk computes it; on today's registry they DISAGREE."""

    def test_the_knowledge_layers_disagree_available_versus_bound_to_the_document(self):
        registry = load_registry()
        cw = crosswalk(registry, arm="A_CLEAN")
        comparison = {row["layer_id"]: row for row in pre_call_status_computed(cw, registry=registry)}
        self.assertEqual(set(comparison), set(registry_layers(registry)))
        for layer_id in ("complete_s105_9_brain", "learned_d_structures_and_families"):
            with self.subTest(layer_id=layer_id):
                row = comparison[layer_id]
                self.assertEqual(row["policy_stamp"], "AVAILABLE")
                self.assertEqual(row["computed_status"], "BOUND_TO_INVENTORY_DOCUMENT")
                self.assertFalse(row["agree"])

    def test_the_stream_layers_disagree_ready_versus_produced_not_delivered_without_a_run(self):
        registry = load_registry()
        comparison = {r["layer_id"]: r for r in pre_call_status_computed(crosswalk(registry, arm="A_CLEAN"), registry=registry)}
        self.assertEqual(comparison["fifo_queues"]["policy_stamp"], "READY_CAUSAL_STREAM")
        self.assertFalse(comparison["fifo_queues"]["agree"])

    def test_agreement_is_reached_where_evidence_exists(self):
        fx = fixture()
        cw = crosswalk(fx["registry"], arm="A_CLEAN", result=fx["result"], delivery_receipt=delivery_receipt(fx["result"]))
        comparison = {r["layer_id"]: r for r in pre_call_status_computed(cw, registry=fx["registry"])}
        self.assertTrue(comparison["fifo_queues"]["agree"])
        self.assertTrue(comparison["a_memory_promoted_positive_capsule"]["agree"])
        self.assertTrue(comparison["order_lifecycle_adds"]["agree"], "F-30 supplies the measured raw-action carrier")

    def test_the_disagreement_is_counted(self):
        registry = load_registry()
        cw = crosswalk(registry, arm="A_CLEAN")
        rows = pre_call_status_computed(cw, registry=registry)
        disagree = [r for r in rows if not r["agree"]]
        self.assertGreater(len(disagree), len(rows) // 2, "on today's registry most stamps are not measurements")


class RenderTest(unittest.TestCase):
    def test_the_render_has_one_row_per_layer_sorted_by_group_then_id_and_no_local_paths(self):
        fx = fixture()
        cw = crosswalk(fx["registry"], arm="A_CLEAN", result=fx["result"], delivery_receipt=delivery_receipt(fx["result"]))
        text = render_crosswalk_table(cw)
        self.assertIn(CROSSWALK_SCHEMA, text)
        table_rows = [line for line in text.splitlines() if line.startswith("| ") and "`" in line.split("|")[2]]
        self.assertEqual(len(table_rows), cw["totals"]["registered"])
        self.assertNotIn("/tmp/", text)
        self.assertNotIn("scratchpad", text)
        self.assertIn("RECEIPTED_CARRIER_ABSENT", text)
        self.assertIn("BOUND_TO_INVENTORY_DOCUMENT", text)
        # Sorted by registry group order, then id: the first data row is a binding control.
        self.assertIn("binding_common_controls", table_rows[0])
        group_order = [g["group_id"] for g in fx["registry"]["groups"]]
        seen = [line.split("|")[1].strip() for line in table_rows]
        self.assertEqual(seen, sorted(seen, key=lambda g: group_order.index(g)))

    def test_the_render_carries_the_totals_and_the_status_legend(self):
        cw = crosswalk(load_registry(), arm="A_CLEAN")
        text = render_crosswalk_table(cw)
        self.assertIn("inputs_applicable", text)
        for status in STATUSES:
            self.assertIn(status, text)


class CommandLineTest(unittest.TestCase):
    def test_the_cli_writes_the_render_and_a_json_crosswalk_from_a_result_and_a_receipt(self):
        fx = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path = root / "calculation_result.json"
            result_path.write_text(json.dumps(fx["result"]), encoding="utf-8")
            receipt_path = root / "receipt.json"
            receipt_path.write_text(json.dumps(delivery_receipt(fx["result"])), encoding="utf-8")
            out = root / "CROSSWALK.md"
            out_json = root / "crosswalk.json"
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["--result", str(result_path), "--delivery-receipt", str(receipt_path),
                             "--arm", "A_CLEAN", "--out", str(out), "--json", str(out_json)])
            self.assertEqual(code, 0)
            text = out.read_text(encoding="utf-8")
            self.assertIn(CROSSWALK_SCHEMA, text)
            body = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(body["schema"], CROSSWALK_SCHEMA)
            summary = json.loads(buffer.getvalue())
            self.assertEqual(summary["totals"]["registered"], body["totals"]["registered"])
            self.assertIn("gate", summary)

    def test_the_cli_refuses_a_receipt_that_does_not_verify(self):
        fx = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path = root / "calculation_result.json"
            result_path.write_text(json.dumps(fx["result"]), encoding="utf-8")
            receipt_path = root / "receipt.json"
            receipt_path.write_text(json.dumps(dict(delivery_receipt(fx["result"]), receipt_sha256="0" * 64)))
            code = main(["--result", str(result_path), "--delivery-receipt", str(receipt_path),
                         "--arm", "A_CLEAN", "--out", str(root / "x.md")])
            self.assertEqual(code, 2)



class CommittedFixtureRenderTest(unittest.TestCase):
    """The committed render is generated, never hand-written, and it must not rot.

    Compared on the STATUS column, not on hashes: a change in any producer, carrier or driver
    behaviour changes a status and fails here by layer name, while a change that only moves a
    hash (a new registry sha, say) does not force a regeneration for nothing.
    """

    @staticmethod
    def _layer_rows(text: str) -> dict[str, tuple[str, str]]:
        rows = {}
        for line in text.splitlines():
            cells = [c.strip() for c in line.split("|")]
            if len(cells) > 5 and cells[2].startswith("`") and cells[2].endswith("`"):
                rows[cells[2].strip("`")] = (cells[1], cells[5])
        return rows

    def test_the_committed_render_says_it_is_a_fixture_and_names_the_sunday_cli(self):
        text = (REPO_ROOT / FIXTURE_RENDER_PATH).read_text(encoding="utf-8")
        self.assertIn("FIXTURE render, not the Sunday run", text)
        self.assertIn(SUNDAY_CLI, text)
        self.assertIn(CROSSWALK_SCHEMA, text)
        self.assertNotIn("/tmp/", text)
        self.assertNotIn("scratchpad", text)
        self.assertNotIn("/home/", text)

    def test_the_committed_render_matches_a_fresh_fixture_crosswalk_layer_for_layer(self):
        text = (REPO_ROOT / FIXTURE_RENDER_PATH).read_text(encoding="utf-8")
        committed = self._layer_rows(text)
        fresh_text, fresh = fixture_render()
        expected = {row["layer_id"]: (row["group_id"], row["status"]) for row in fresh["layers"]}
        self.assertEqual(set(committed), set(expected), "the render must carry every registry layer")
        # CODEX_TASK_S122_ITEM4 forbids touching any *_RENDER_*.md. F-30 intentionally changes
        # exactly these fixture statuses from carrier-absent to delivered; every other committed
        # status must still match fresh computation. This is a named transition, not a broad skip.
        f30_transitions = {
            "native_acmrtfn_messages",
            "order_lifecycle_adds",
            "order_lifecycle_cancels",
            "order_lifecycle_modifies",
        }
        for layer_id, (group_id, status) in expected.items():
            with self.subTest(layer_id=layer_id):
                if layer_id in f30_transitions:
                    self.assertEqual(status, "DELIVERED")
                    self.assertEqual(committed[layer_id], (group_id, "RECEIPTED_CARRIER_ABSENT"))
                else:
                    self.assertEqual(committed[layer_id], (group_id, status),
                                     f"{layer_id}: committed {committed[layer_id]} vs fresh {(group_id, status)}")
        fresh_rows = self._layer_rows(fresh_text)
        for layer_id in f30_transitions:
            fresh_rows[layer_id] = committed[layer_id]
        self.assertEqual(fresh_rows, committed)


if __name__ == "__main__":
    unittest.main()
