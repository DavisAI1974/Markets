"""The raw MBO reaches the principal the way it arrives in real time, and nothing else.

Greg, 2026-09-02: *"he gets every record of every field for Sunday, the date and time we are
running. and Monday will get the same thing for Monday and so on."* and *"this has to exactly
mimic how it's going to come in rt."* So the stream hands over one F_LAST-closed group at a
time, in `ts_recv_ns` order, byte-identical to the ledger, visible only once its F_LAST record
has been received - never ahead, never re-read, never peeked.

Every refusal below is PRODUCED, not asserted: a guard whose firing branch never executed was
never tested (S113, NC-3).
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark import native_a_arm_launch as launcher
from research.kalshi.frankie_raw_mbo_benchmark.native_causal_stream import (
    CAUSAL_CLOCKS_DERIVED_FROM_LEGACY,
    CAUSAL_CLOCKS_ROW_OWN,
    GENESIS_PREVIOUS_RECEIPT_SHA256,
    NOT_ON_THIS_ROW,
    STREAM_RECEIPT_SCHEMA,
    CausalGroupStream,
    CausalStreamError,
    EndOfStream,
    lifecycle_availability,
    main,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_clocks import (
    CAUSAL_CLOCK_LAYER_IDS,
    CLOCK_EVENT_KNOWN_BY,
    CLOCK_EVENT_TIME,
    CLOCK_LOCK_TIME,
    CLOCK_MODEL_EVALUATION,
    CLOCK_RECEIVE_TIME,
    EVENT_CLOCK,
    causal_clock_layers,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    GROUP_DELIVERY_SCHEMA,
    canonical_hash,
    load_registry,
)
from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_a_arm_launch import slice_records

NS = 1_000_000_000
BASE = 1_633_352_400_000_150_000


def sink_line(row: dict) -> bytes:
    """Exactly what `RowSink.write` puts on disk. The byte-identity oracle."""
    return (json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def member_row(index: int, recv_ns: int, *, f_last: bool = True, clock: str = "ts_recv_ns") -> dict:
    """The fields a real member row carries that the stream reads. Names are the ledger's own:
    `group_index`, `ts_recv_ns`, `ts_event_ns`, `causal_availability_clock`,
    `event_group_complete_f_last`, and `clocks.first_lawful_availability_ns` /
    `clocks.f_last_ts_recv_ns` / `clocks.decision_ts_recv_ns` (native_clocks.member_clock_row)."""
    return {
        "group_index": index,
        "ts_recv_ns": recv_ns,
        "ts_event_ns": recv_ns - 150_000,
        "causal_availability_clock": clock,
        "event_group_complete_f_last": f_last,
        "clocks": {
            "first_component_ts_event_ns": recv_ns - 3 * NS - 150_000,
            "first_component_ts_recv_ns": recv_ns - 3 * NS,
            "f_last_ts_recv_ns": recv_ns,
            "first_lawful_availability_ns": recv_ns,
            "decision_ts_recv_ns": recv_ns,
        },
        "raw_actions": [{"action": "A", "side": "B", "ts_recv_ns": recv_ns}],
        "book_full": {"bid_levels": [], "ask_levels": []},
        "source_day": "20211003",
    }


def write_ledger(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        for row in rows:
            handle.write(sink_line(row))
    return path


def three_groups(root: Path) -> Path:
    return write_ledger(
        root / "exact_member_rows.jsonl",
        [member_row(0, BASE), member_row(1, BASE + 4 * NS), member_row(2, BASE + 8 * NS)],
    )


class DeliversByteIdenticalRowsInOrderTest(unittest.TestCase):
    def test_each_delivered_group_is_the_ledger_line_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = three_groups(Path(tmp))
            lines = path.read_bytes().splitlines(keepends=True)
            stream = CausalGroupStream(path, run_id="t", arm="A_CLEAN")
            for expected in lines:
                delivery = stream.next_group()
                self.assertEqual(delivery.group, json.loads(expected))
                self.assertEqual(sink_line(delivery.group), expected)
                self.assertEqual(delivery.group_line, expected)
            with self.assertRaises(EndOfStream):
                stream.next_group()

    def test_the_availability_stamp_is_the_rows_own_f_last_receive_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = CausalGroupStream(three_groups(Path(tmp)), run_id="t", arm="A_CLEAN")
            first = stream.next_group()
            self.assertEqual(first.first_lawful_availability_ns, BASE)
            self.assertEqual(
                first.first_lawful_availability_ns,
                first.group["clocks"]["first_lawful_availability_ns"],
            )
            self.assertEqual(first.group_index, 0)

    def test_iterate_yields_every_group_once_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = CausalGroupStream(three_groups(Path(tmp)), run_id="t", arm="A_CLEAN")
            self.assertEqual([d.group_index for d in stream.iterate()], [0, 1, 2])


class RefusesDisorderTest(unittest.TestCase):
    def test_a_ledger_whose_receive_clock_moves_backwards_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_ledger(
                Path(tmp) / "m.jsonl",
                [member_row(0, BASE), member_row(1, BASE + 4 * NS), member_row(2, BASE + 2 * NS)],
            )
            stream = CausalGroupStream(path, run_id="t", arm="A_CLEAN")
            stream.next_group()
            stream.next_group()
            with self.assertRaisesRegex(CausalStreamError, "backwards"):
                stream.next_group()

    def test_a_group_not_closed_by_f_last_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_ledger(Path(tmp) / "m.jsonl", [member_row(0, BASE, f_last=False)])
            with self.assertRaisesRegex(CausalStreamError, "F_LAST"):
                CausalGroupStream(path, run_id="t", arm="A_CLEAN").next_group()

    def test_a_row_declaring_another_availability_clock_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_ledger(Path(tmp) / "m.jsonl", [member_row(0, BASE, clock="ts_event_ns")])
            with self.assertRaisesRegex(CausalStreamError, "causal_availability_clock"):
                CausalGroupStream(path, run_id="t", arm="A_CLEAN").next_group()


class NoRandomAccessTest(unittest.TestCase):
    def test_every_way_of_looking_ahead_or_back_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = CausalGroupStream(three_groups(Path(tmp)), run_id="t", arm="A_CLEAN")
            stream.next_group()
            for attempt in (
                lambda: stream.peek(),
                lambda: stream.seek(0),
                lambda: stream.rewind(),
                lambda: stream[2],
                lambda: len(stream),
                lambda: list(reversed(stream)),
            ):
                with self.assertRaises(CausalStreamError):
                    attempt()
            # And it kept its place: the refusals did not move the cursor.
            self.assertEqual(stream.next_group().group_index, 1)

    def test_withheld_rows_cannot_be_read_before_the_stream_is_exhausted(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = CausalGroupStream(three_groups(Path(tmp)), run_id="t", arm="A_CLEAN")
            stream.next_group()
            with self.assertRaisesRegex(CausalStreamError, "exhausted"):
                stream.drain_withheld()


class SidecarAttachmentTest(unittest.TestCase):
    """Lifecycle and legacy rows ride with a group ONLY when their own clock allows it."""

    def _stream(self, tmp: Path, lifecycle: list[dict] | None = None, legacy: list[dict] | None = None):
        member = three_groups(tmp)
        life = write_ledger(tmp / "exact_lifecycle_rows.jsonl", lifecycle) if lifecycle is not None else None
        leg = write_ledger(tmp / "legacy_observable_rows.jsonl", legacy) if legacy is not None else None
        return CausalGroupStream(member, life, leg, run_id="t", arm="A_CLEAN")

    def test_a_lifecycle_row_later_than_the_cutoff_is_withheld_then_delivered_later(self):
        rows = [
            {"emitting_section": "ladder", "emitted_on": "GROUP_CLOSE", "recv_ns": BASE, "clock": "ts_recv_ns"},
            {"emitting_section": "ladder", "emitted_on": "GROUP_CLOSE", "recv_ns": BASE + 4 * NS, "clock": "ts_recv_ns"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            stream = self._stream(Path(tmp), lifecycle=rows)
            first = stream.next_group()
            self.assertEqual([r["recv_ns"] for r in first.lifecycle_rows], [BASE])
            second = stream.next_group()
            self.assertEqual([r["recv_ns"] for r in second.lifecycle_rows], [BASE + 4 * NS])
            third = stream.next_group()
            self.assertEqual(third.lifecycle_rows, ())

    def test_a_row_with_no_clock_of_its_own_is_withheld_and_counted_not_dropped(self):
        rows = [
            {"emitting_section": "mirror", "emitted_on": "GROUP_CLOSE", "member_id": "grp-20211003-0"},
            {"emitting_section": "ladder", "emitted_on": "GROUP_CLOSE", "recv_ns": BASE, "clock": "ts_recv_ns"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            stream = self._stream(Path(tmp), lifecycle=rows)
            deliveries = list(stream.iterate())
            self.assertEqual(sum(len(d.lifecycle_rows) for d in deliveries), 1)
            receipt = stream.stream_receipt()
            life = receipt["lifecycle_ledger"]
            self.assertEqual(life["rows_read"], 2)
            self.assertEqual(life["rows_attached"], 1)
            self.assertEqual(life["withheld_no_own_clock"], {"mirror": 1})
            self.assertTrue(life["retention_identity_holds"])
            withheld = stream.drain_withheld()
            self.assertEqual([r["row"]["member_id"] for r in withheld["lifecycle"]], ["grp-20211003-0"])
            self.assertEqual(withheld["lifecycle"][0]["reason"], "NO_OWN_CLOCK")

    def test_close_occasion_rows_never_ride_inside_a_group(self):
        """A STREAM_END or SEGMENT_CLOSE row's content was fixed at a close instant the row
        does not carry, so delivering it at its latest named clock would say, at that clock,
        that nothing followed - which is the future."""
        rows = [
            {"emitting_section": "lineage", "emitted_on": "STREAM_END", "entered_recv_ns": BASE,
             "exited_recv_ns": None, "status": "CENSORED_STREAM_END", "clock": "ts_recv_ns"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            stream = self._stream(Path(tmp), lifecycle=rows)
            deliveries = list(stream.iterate())
            self.assertEqual(sum(len(d.lifecycle_rows) for d in deliveries), 0)
            receipt = stream.stream_receipt()
            self.assertEqual(receipt["lifecycle_ledger"]["withheld_close_occasion"], {"lineage|STREAM_END": 1})
            self.assertEqual(stream.drain_withheld()["lifecycle"][0]["reason"], "CLOSE_OCCASION")

    def test_a_lifecycle_row_beyond_the_last_cutoff_is_withheld_and_counted(self):
        rows = [{"emitting_section": "ladder", "emitted_on": "GROUP_CLOSE", "recv_ns": BASE + 40 * NS, "clock": "ts_recv_ns"}]
        with tempfile.TemporaryDirectory() as tmp:
            stream = self._stream(Path(tmp), lifecycle=rows)
            list(stream.iterate())
            receipt = stream.stream_receipt()
            self.assertEqual(receipt["lifecycle_ledger"]["withheld_beyond_last_cutoff"], 1)
            self.assertEqual(receipt["lifecycle_ledger"]["rows_attached"], 0)

    def test_a_completed_second_is_lawful_once_that_second_has_ended(self):
        second = BASE // NS
        rows = [
            {"emitting_section": "flow_substrate", "emitted_on": "SECOND_COMPLETE", "second": second, "clock": "ts_recv_ns"},
            {"emitting_section": "flow_substrate", "emitted_on": "SECOND_COMPLETE", "second": second + 7, "clock": "ts_recv_ns"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            stream = self._stream(Path(tmp), lifecycle=rows)
            first = stream.next_group()      # cutoff BASE, inside `second`: not yet ended
            self.assertEqual(first.lifecycle_rows, ())
            second_delivery = stream.next_group()   # cutoff BASE + 4s: `second` ended, second+7 has not
            self.assertEqual([r["second"] for r in second_delivery.lifecycle_rows], [second])
            third = stream.next_group()      # cutoff BASE + 8s >= (second+8)s: second+7 ended
            self.assertEqual([r["second"] for r in third.lifecycle_rows], [second + 7])

    def test_a_candidate_is_lawful_at_its_own_available_second(self):
        rows = [{"emitting_section": "candidate", "emitted_on": "CANDIDATE_LAWFUL",
                 "event_second": BASE // NS, "available_second": BASE // NS + 4}]
        with tempfile.TemporaryDirectory() as tmp:
            stream = self._stream(Path(tmp), lifecycle=rows)
            first = stream.next_group()
            self.assertEqual(first.lifecycle_rows, ())
            second = stream.next_group()
            self.assertEqual(len(second.lifecycle_rows), 1)

    def test_a_legacy_row_is_attached_by_its_own_ts_recv_in_seconds(self):
        legacy = [
            {"ts_recv": BASE / 1e9, "action": "A", "census_view": "LEGACY_CONTROL"},
            {"ts_recv": (BASE + 4 * NS) / 1e9, "action": "T", "census_view": "LEGACY_CONTROL"},
            {"ts_recv": (BASE + 9 * NS) / 1e9, "action": "C", "census_view": "LEGACY_CONTROL"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            stream = self._stream(Path(tmp), legacy=legacy)
            deliveries = list(stream.iterate())
            self.assertEqual([[r["action"] for r in d.legacy_rows] for d in deliveries], [["A"], ["T"], []])
            receipt = stream.stream_receipt()
            self.assertEqual(receipt["legacy_ledger"]["rows_read"], 3)
            self.assertEqual(receipt["legacy_ledger"]["rows_attached"], 2)
            self.assertEqual(receipt["legacy_ledger"]["withheld_beyond_last_cutoff"], 1)
            self.assertTrue(receipt["legacy_ledger"]["retention_identity_holds"])


class LifecycleAvailabilityRuleTest(unittest.TestCase):
    def test_the_latest_named_receive_clock_is_the_availability_including_nested(self):
        row = {"emitting_section": "recurrence", "emitted_on": "GROUP_CLOSE",
               "runs": [{"end_recv_ns": 5, "start_recv_ns": 1}], "gaps": [{"recv_ns": 7}]}
        self.assertEqual(lifecycle_availability(row), ("OWN_CLOCK", 7))

    def test_nulls_and_non_integers_are_not_clocks(self):
        row = {"emitting_section": "lineage", "emitted_on": "GROUP_CLOSE",
               "entered_recv_ns": 3, "exited_recv_ns": None, "clock": "ts_recv_ns"}
        self.assertEqual(lifecycle_availability(row), ("OWN_CLOCK", 3))

    def test_no_clock_at_all_is_said_not_guessed(self):
        self.assertEqual(lifecycle_availability({"emitting_section": "mirror", "emitted_on": "GROUP_CLOSE"}), ("NO_OWN_CLOCK", None))


class DeliveryReceiptTest(unittest.TestCase):
    """The registry's uncalled validator is now called on every delivered group."""

    def test_every_delivery_carries_a_validated_registry_receipt_chained_to_the_previous(self):
        registry = load_registry()
        with tempfile.TemporaryDirectory() as tmp:
            stream = CausalGroupStream(three_groups(Path(tmp)), run_id="run-1", arm="A_CLEAN", registry=registry)
            previous = GENESIS_PREVIOUS_RECEIPT_SHA256
            for delivery in stream.iterate():
                receipt = delivery.receipt
                self.assertEqual(receipt["schema"], GROUP_DELIVERY_SCHEMA)
                self.assertEqual(receipt["previous_delivery_receipt_sha256"], previous)
                self.assertEqual(receipt["receipt_sha256"], canonical_hash(receipt, omit="receipt_sha256"))
                self.assertEqual(receipt["group_id"], delivery.group_index)
                self.assertEqual(receipt["clocks"]["availability_time_ns"], delivery.first_lawful_availability_ns)
                self.assertEqual(receipt["group_sha256"], delivery.group_sha256)
                self.assertTrue(delivery.gate["all_causal_layers_delivered"])
                self.assertEqual(delivery.gate["delivered_layer_count"], 55)
                previous = receipt["receipt_sha256"]
            self.assertEqual(stream.stream_receipt()["last_delivery_receipt_sha256"], previous)

    def test_the_group_hash_is_over_the_bytes_actually_delivered(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = three_groups(Path(tmp))
            first_line = path.read_bytes().splitlines(keepends=True)[0]
            delivery = CausalGroupStream(path, run_id="r", arm="A_CLEAN").next_group()
            self.assertEqual(delivery.group_sha256, hashlib.sha256(first_line).hexdigest())
            self.assertEqual(delivery.bytes_delivered, len(first_line))


class StreamReceiptTest(unittest.TestCase):
    def test_the_receipt_counts_groups_bytes_hash_and_ordered_cutoffs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = three_groups(Path(tmp))
            stream = CausalGroupStream(path, run_id="r", arm="A_CLEAN")
            list(stream.iterate())
            receipt = stream.stream_receipt()
            self.assertEqual(receipt["schema"], STREAM_RECEIPT_SCHEMA)
            self.assertEqual(receipt["groups_delivered"], 3)
            self.assertEqual(receipt["bytes_delivered"], path.stat().st_size)
            self.assertEqual(receipt["sha256_delivered"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(receipt["member_ledger"]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(receipt["cutoffs"], [BASE, BASE + 4 * NS, BASE + 8 * NS])
            self.assertTrue(receipt["complete"])
            self.assertEqual(receipt["receipt_sha256"], canonical_hash(receipt, omit="receipt_sha256"))

    def test_a_receipt_taken_before_exhaustion_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = CausalGroupStream(three_groups(Path(tmp)), run_id="r", arm="A_CLEAN")
            stream.next_group()
            receipt = stream.stream_receipt()
            self.assertFalse(receipt["complete"])
            self.assertEqual(receipt["groups_delivered"], 1)
            with self.assertRaisesRegex(CausalStreamError, "closed"):
                stream.next_group()


class RealLedgersStreamTest(unittest.TestCase):
    """The rows the actual traversal writes, not a hand-made shape of them."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        groups = 12
        cls.result = launcher.launch(
            arm="A_CLEAN", run_id="stream-fixture", sources=[],
            source_manifest={"manifest_hash": "e" * 64, "total_mbo_records": 5_667_689},
            out_dir=root, code_commit="cafebabe", limit_records=groups * 4,
            checkpoint_every_records=10**9, cadence_groups=10**9,
            records=slice_records(groups), stream_ledgers=True,
        )
        cls.ledgers = cls.result["evidence_identity"]["exact_ledgers"]

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_the_whole_real_member_ledger_streams_in_order_and_hashes_to_the_sink_receipt(self):
        stream = CausalGroupStream(
            self.ledgers["exact_member_rows"], self.ledgers["exact_lifecycle_rows"],
            self.ledgers["legacy_observable_rows"], run_id="stream-fixture", arm="A_CLEAN",
        )
        deliveries = list(stream.iterate())
        receipt = stream.stream_receipt()
        sink = self.result["ledger_retention"]["exact_member_ledger"]
        self.assertEqual(receipt["groups_delivered"], sink["row_count"])
        self.assertEqual(receipt["member_ledger"]["sha256"], sink["sha256"])
        self.assertEqual(receipt["member_ledger"]["bytes"], sink["bytes"])
        self.assertEqual(receipt["cutoffs"], sorted(receipt["cutoffs"]))
        self.assertEqual([d.group_index for d in deliveries], list(range(sink["row_count"])))

    def test_every_real_sidecar_row_is_attached_or_withheld_and_counted(self):
        stream = CausalGroupStream(
            self.ledgers["exact_member_rows"], self.ledgers["exact_lifecycle_rows"],
            self.ledgers["legacy_observable_rows"], run_id="stream-fixture", arm="A_CLEAN",
        )
        deliveries = list(stream.iterate())
        receipt = stream.stream_receipt()
        retention = self.result["ledger_retention"]
        for ledger, key in (("lifecycle_ledger", "exact_lifecycle_and_runway_ledger"),
                            ("legacy_ledger", "legacy_observable_rows")):
            with self.subTest(ledger=ledger):
                block = receipt[ledger]
                self.assertEqual(block["rows_read"], retention[key]["row_count"])
                self.assertTrue(block["retention_identity_holds"])
                self.assertGreater(block["rows_attached"], 0)
        attached = sum(len(d.legacy_rows) for d in deliveries)
        self.assertEqual(attached, receipt["legacy_ledger"]["rows_attached"])
        # Every legacy row the adapter emitted before a group's F_LAST rides with that group.
        self.assertEqual(receipt["legacy_ledger"]["rows_attached"], retention["legacy_observable_rows"]["row_count"])

    def test_no_delivered_sidecar_row_postdates_its_groups_cutoff(self):
        stream = CausalGroupStream(
            self.ledgers["exact_member_rows"], self.ledgers["exact_lifecycle_rows"],
            self.ledgers["legacy_observable_rows"], run_id="stream-fixture", arm="A_CLEAN",
        )
        for delivery in stream.iterate():
            cutoff = delivery.first_lawful_availability_ns
            for row in delivery.lifecycle_rows:
                kind, when = lifecycle_availability(row)
                self.assertLessEqual(when, cutoff, (kind, row.get("emitting_section")))
            for row in delivery.legacy_rows:
                self.assertLessEqual(float(row["ts_recv"]), cutoff / 1e9)


class CommandLineTest(unittest.TestCase):
    def test_the_module_prints_the_stream_receipt_over_a_whole_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = three_groups(Path(tmp))
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["--member-ledger", str(path), "--run-id", "r", "--arm", "A_CLEAN"])
            self.assertEqual(code, 0)
            receipt = json.loads(out.getvalue())
            self.assertEqual(receipt["groups_delivered"], 3)
            self.assertTrue(receipt["complete"])

    def test_a_gzipped_member_ledger_is_refused_rather_than_read_as_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.jsonl.gz"
            with gzip.open(path, "wb") as handle:
                handle.write(sink_line(member_row(0, BASE)))
            with self.assertRaisesRegex(CausalStreamError, "gunzip"):
                CausalGroupStream(path, run_id="r", arm="A_CLEAN").next_group()


class CausalClocksOnDeliveryTest(unittest.TestCase):
    """S121 item one: the seven clocks ride on `GroupDelivery` by registry id, beside a receipt
    whose four-key `clocks` object the registry validator still checks exactly."""

    def _row_with_causal_clocks(self, index: int, recv_ns: int) -> dict:
        row = member_row(index, recv_ns)
        row["causal_clocks"] = causal_clock_layers(
            event_ns=[recv_ns - 3 * NS - 150_000, recv_ns - 150_000],
            recv_ns=[recv_ns - 3 * NS, recv_ns],
        )
        return row

    def test_a_row_carrying_its_own_causal_clocks_is_delivered_as_row_own(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_ledger(Path(tmp) / "m.jsonl", [self._row_with_causal_clocks(0, BASE)])
            delivery = CausalGroupStream(path, run_id="t", arm="A_CLEAN").next_group()
            self.assertEqual(delivery.causal_clocks_basis, CAUSAL_CLOCKS_ROW_OWN)
            self.assertEqual(delivery.causal_clocks, delivery.group["causal_clocks"])
            self.assertEqual(set(delivery.causal_clocks), set(CAUSAL_CLOCK_LAYER_IDS))

    def test_a_pre_s121_ledger_row_gets_the_three_derivable_clocks_and_says_so(self):
        """The delivered Sunday ledger predates the field. The stream derives what the legacy
        five-field object can support and declares the rest absent, so the ledger stays
        deliverable and the crosswalk can still find the clocks by name."""
        with tempfile.TemporaryDirectory() as tmp:
            delivery = CausalGroupStream(three_groups(Path(tmp)), run_id="t", arm="A_CLEAN").next_group()
            self.assertEqual(delivery.causal_clocks_basis, CAUSAL_CLOCKS_DERIVED_FROM_LEGACY)
            clocks = delivery.causal_clocks
            self.assertEqual(set(clocks), set(CAUSAL_CLOCK_LAYER_IDS))
            self.assertEqual(clocks[CLOCK_EVENT_KNOWN_BY]["value_ns"], BASE)
            self.assertEqual(clocks[CLOCK_RECEIVE_TIME]["f_last_ns"], BASE)
            self.assertEqual(clocks[CLOCK_RECEIVE_TIME]["first_component_ns"], BASE - 3 * NS)
            self.assertEqual(clocks[CLOCK_EVENT_TIME]["f_last_ns"], BASE - 150_000)
            self.assertEqual(clocks[CLOCK_EVENT_TIME]["first_component_ns"], BASE - 3 * NS - 150_000)
            self.assertEqual(clocks[CLOCK_LOCK_TIME]["basis"], NOT_ON_THIS_ROW)
            self.assertEqual(clocks[CLOCK_MODEL_EVALUATION]["basis"], NOT_ON_THIS_ROW)

    def test_a_row_with_a_partial_causal_clocks_object_is_refused_not_patched(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = member_row(0, BASE)
            row["causal_clocks"] = {CLOCK_EVENT_TIME: {"clock": EVENT_CLOCK}}
            path = write_ledger(Path(tmp) / "m.jsonl", [row])
            with self.assertRaisesRegex(CausalStreamError, "causal_clocks"):
                CausalGroupStream(path, run_id="t", arm="A_CLEAN").next_group()

    def test_a_disordered_row_own_object_is_refused_not_delivered(self):
        """A row whose feature clock precedes its event_known_by is not a row the stream
        can hand over as causal, whatever its five-field `clocks` object says."""
        with tempfile.TemporaryDirectory() as tmp:
            row = self._row_with_causal_clocks(0, BASE)
            row["causal_clocks"]["clock_feature_availability"]["value_ns"] = BASE - 1
            path = write_ledger(Path(tmp) / "m.jsonl", [row])
            with self.assertRaisesRegex(CausalStreamError, "clock_event_known_by"):
                CausalGroupStream(path, run_id="t", arm="A_CLEAN").next_group()

    def test_the_delivered_chain_is_checked_and_reported_on_every_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_ledger(Path(tmp) / "m.jsonl", [self._row_with_causal_clocks(0, BASE)])
            delivery = CausalGroupStream(path, run_id="t", arm="A_CLEAN").next_group()
            self.assertEqual(delivery.causal_clock_chain["event_known_by_ns"], BASE)
            self.assertEqual(delivery.causal_clock_chain["feature_availability_ns"], BASE)
            self.assertIsNone(delivery.causal_clock_chain["model_evaluation_ns"])

    def test_the_registry_receipt_still_carries_exactly_four_clock_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_ledger(Path(tmp) / "m.jsonl", [self._row_with_causal_clocks(0, BASE)])
            delivery = CausalGroupStream(path, run_id="t", arm="A_CLEAN").next_group()
            self.assertEqual(
                set(delivery.receipt["clocks"]),
                {"event_time_ns", "receive_time_ns", "availability_time_ns", "decision_time_ns"},
            )
            self.assertTrue(delivery.gate["all_causal_layers_delivered"])

    def test_the_stream_receipt_declares_the_carrier_and_counts_both_bases(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [self._row_with_causal_clocks(0, BASE), member_row(1, BASE + 4 * NS)]
            stream = CausalGroupStream(write_ledger(Path(tmp) / "m.jsonl", rows), run_id="t", arm="A_CLEAN")
            list(stream.iterate())
            declared = stream.stream_receipt()["causal_clock_layers"]
            self.assertEqual(declared["carrier"], "member.causal_clocks")
            self.assertEqual(declared["layer_ids"], list(CAUSAL_CLOCK_LAYER_IDS))
            self.assertEqual(declared["groups_with_row_own"], 1)
            self.assertEqual(declared["groups_with_derived_from_legacy_clocks"], 1)


if __name__ == "__main__":
    unittest.main()
