"""B, proved rather than claimed: streaming the exact ledgers changes no science.

The claim is that moving the exact member, lifecycle and legacy ledgers out of RAM and onto
disk changes WHERE a copy lands and nothing that was measured. That is exactly the kind of
claim this tree has learned not to accept on reasoning: the b_share encoding, the off-instrument
tape and the frozen countdowns were all present, well formed and wrong, and only comparison
against an independent source settled any of them.

So this runs ONE slice both ways and compares the whole result field for field. Anything that
differs outside the declared retention keys fails, whether or not anyone thought of it - which
is the property a list of specific assertions would not have.

It also mutation-tests its own comparator, because a differential that compares nothing passes
forever (S113, NC-3: a test that never produced the guard's output did not test the guard).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark import native_a_arm_launch as launcher
from research.kalshi.frankie_raw_mbo_benchmark.native_calculation_runner import ACCEPTED
from research.kalshi.frankie_raw_mbo_benchmark.native_row_sink import RowSink, RowSinkError
from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_a_arm_launch import slice_records

GROUPS = 60
MANIFEST = {"manifest_hash": "e" * 64, "total_mbo_records": 5_667_689}

# The only keys allowed to differ. Everything else must be identical, and the point of
# naming them is that the comparison below removes exactly these and then demands equality
# on the whole remaining object.
MEMBER_KEYS = {"rows", "rows_retention", "rows_receipt"}
TRAVERSAL_KEYS = {"legacy_rows", "legacy_rows_retention", "legacy_rows_receipt"}
TOP_KEYS = {"ledger_retention", "result_hash"}
# `result_hash` is `canonical_hash(result)` over the WHOLE artifact, and the artifact's
# retention representation is precisely what changed - inline arrays versus a receipt. So it
# MUST differ, and excluding it here is not an exemption: the test below asserts that it
# differs, which is the stronger statement. A hash that stayed equal across this change would
# mean it was not covering the ledgers at all.


def run_slice(out_dir: Path, *, stream: bool) -> dict:
    return launcher.launch(
        arm="A_CLEAN",
        run_id="differential",          # identical, so identity hashes cannot differ
        sources=[],
        source_manifest=MANIFEST,
        out_dir=out_dir,
        code_commit="cafebabe",
        limit_records=GROUPS * 4,
        checkpoint_every_records=10**9,
        cadence_groups=10**9,
        records=slice_records(GROUPS),
        stream_ledgers=stream,
    )


def strip_retention(result: dict) -> dict:
    body = {k: v for k, v in result.items() if k not in TOP_KEYS}
    body["traversal"] = {
        k: v for k, v in body["traversal"].items() if k not in TRAVERSAL_KEYS
    }
    layers = dict(body["layers"])
    for layer in ("exact_member_ledger", "exact_lifecycle_and_runway_ledger"):
        layers[layer] = {k: v for k, v in layers[layer].items() if k not in MEMBER_KEYS}
    body["layers"] = layers
    return body


class RowSinkDifferentialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.streamed = run_slice(root / "streamed", stream=True)
        cls.inline = run_slice(root / "inline", stream=False)
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_both_runs_are_accepted(self):
        for name, result in (("streamed", self.streamed), ("inline", self.inline)):
            with self.subTest(run=name):
                self.assertEqual(result["verdict"], ACCEPTED, result["failed_gates"])

    def test_everything_except_where_the_rows_live_is_identical(self):
        """The whole object, not a list of fields someone remembered to check."""
        self.assertEqual(strip_retention(self.streamed), strip_retention(self.inline))

    def test_the_artifact_hash_tracks_the_retention_change(self):
        """Asserted, not excused. A hash unchanged by this would not be covering the ledgers."""
        self.assertNotEqual(self.streamed["result_hash"], self.inline["result_hash"])
        for name, result in (("streamed", self.streamed), ("inline", self.inline)):
            with self.subTest(run=name):
                self.assertRegex(result["result_hash"], r"^[0-9a-f]{64}$")

    def test_the_comparator_would_notice_a_difference(self):
        """Mutation test. Without this the assertion above could be comparing nothing."""
        mutated = json.loads(json.dumps(strip_retention(self.streamed)))
        mutated["traversal"]["groups_seen"] += 1
        self.assertNotEqual(mutated, strip_retention(self.inline))

    def test_the_streamed_file_holds_exactly_the_rows_the_inline_run_held(self):
        """Same rows, same order. This is the claim that nothing was lost, read off disk."""
        receipt = self.streamed["layers"]["exact_member_ledger"]["rows_receipt"]
        on_disk = [
            json.loads(line)
            for line in Path(receipt["path"]).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        inline_rows = self.inline["layers"]["exact_member_ledger"]["rows"]
        self.assertEqual(len(on_disk), len(inline_rows))
        self.assertGreater(len(on_disk), 0, "the fixture stopped producing member rows")
        self.assertEqual(
            json.loads(json.dumps(on_disk, sort_keys=True)),
            json.loads(json.dumps(inline_rows, sort_keys=True)),
        )

    def test_all_three_ledgers_stream_and_reconcile_against_their_counters(self):
        retention = self.streamed["ledger_retention"]
        self.assertEqual(len(retention), 3)
        for ledger, receipt in retention.items():
            with self.subTest(ledger=ledger):
                self.assertEqual(receipt["retention"], "STREAMED")
                self.assertEqual(receipt["row_count"], receipt["rows_read_back_from_disk"])
                self.assertEqual(receipt["row_count"], receipt["reconciled_against_counter"])
                self.assertRegex(receipt["sha256"], r"^[0-9a-f]{64}$")

    def test_the_retained_counts_match_across_both_paths(self):
        """Retention counts are the D60 claim, and they cannot move when the home does."""
        for key in ("member_rows_retained", "lifecycle_rows_retained", "legacy_rows_retained"):
            with self.subTest(key=key):
                self.assertEqual(
                    self.streamed["traversal"][key], self.inline["traversal"][key]
                )
                self.assertGreater(self.streamed["traversal"][key], 0)

    def test_the_legacy_rows_survive_the_move_verbatim(self):
        """D60's hardest case: legacy_book_imbalance has no other source in the traversal."""
        receipt = self.streamed["traversal"]["legacy_rows_receipt"]
        on_disk = [
            json.loads(line)
            for line in Path(receipt["path"]).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(
            json.loads(json.dumps(on_disk, sort_keys=True)),
            json.loads(json.dumps(self.inline["traversal"]["legacy_rows"], sort_keys=True)),
        )

    def test_roll20_is_unaffected_by_where_the_legacy_rows_are_retained(self):
        """The trap this nearly walked into.

        `roll20` used to be fed by SLICING the fully retained legacy list from a cursor, so
        streaming the ledger would have handed it an empty tail and the per-second binning
        would have gone quietly wrong - a required CAUSAL_STREAM_REQUIRED layer, silently
        different, with nothing failing. It is now fed from a pending buffer that says what
        it is, and these two must agree.
        """
        self.assertEqual(
            self.streamed["traversal"]["legacy_per_second_roll20"],
            self.inline["traversal"]["legacy_per_second_roll20"],
        )


class RowSinkReconciliationTest(unittest.TestCase):
    """The check the in-RAM ledgers never had: a counter that agrees with nothing."""

    def test_a_short_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            sink = RowSink(Path(tmp) / "x.jsonl", ledger="test")
            sink.write({"a": 1})
            with self.assertRaises(RowSinkError):
                sink.reconcile(2)

    def test_a_matching_file_reconciles_and_reports_what_it_read_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            sink = RowSink(Path(tmp) / "x.jsonl", ledger="test")
            for i in range(5):
                sink.write({"i": i})
            receipt = sink.reconcile(5)
            self.assertEqual(receipt["rows_read_back_from_disk"], 5)
            self.assertEqual([r["i"] for r in sink.read_back()], [0, 1, 2, 3, 4])

    def test_a_row_arriving_after_close_is_refused_not_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            sink = RowSink(Path(tmp) / "x.jsonl", ledger="test")
            sink.write({"a": 1})
            sink.close()
            with self.assertRaises(RowSinkError):
                sink.write({"a": 2})

    def test_the_hash_depends_on_content_not_on_key_order(self):
        """Two runs retaining the same rows must produce the same hash, or it proves nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            first = RowSink(Path(tmp) / "a.jsonl", ledger="t")
            first.write({"a": 1, "b": 2})
            second = RowSink(Path(tmp) / "b.jsonl", ledger="t")
            second.write({"b": 2, "a": 1})
            self.assertEqual(first.close()["sha256"], second.close()["sha256"])


if __name__ == "__main__":
    unittest.main()
