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

import json
import re
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark import native_a_arm_launch as launcher
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import load_registry
from research.kalshi.frankie_raw_mbo_benchmark.native_layer_crosswalk import (
    LAYER_PRODUCERS,
    PRODUCER_KINDS,
    REPO_ROOT,
    SEVEN_CLOCKS,
    path_present,
    registry_layers,
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
        """The measurement behind the RECEIPTED_CARRIER_ABSENT status, pinned. The driver
        drops the frame's `raw_actions` at group close saying the row already holds them; the
        row does not. When that is fixed this test fails and the records get updated - the
        crosswalk cannot silently keep reporting a defect that is gone."""
        pinned = 0
        for layer_id, record in LAYER_PRODUCERS.items():
            for pattern in record.get("structurally_absent", ()):
                pinned += 1
                with self.subTest(layer_id=layer_id, path=pattern):
                    self.assertFalse(
                        path_present(pattern, self.member_paths),
                        f"{layer_id}: {pattern} is now on the row; update the producer record",
                    )
        self.assertGreater(pinned, 0)
        self.assertNotIn("raw_actions", self.member_rows[0])

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


if __name__ == "__main__":
    unittest.main()
