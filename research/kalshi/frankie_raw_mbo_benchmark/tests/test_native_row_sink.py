"""Byte attribution on the exact ledgers: which calculation is the size.

A run that fills a volume tells you it is too big and nothing about what to do next. The
sink already knew its total; it did not know where the total came from, so the question
"which of the sixteen sections is expensive, and does any of it carry no value" could only
be answered with an opinion. These tests pin the table that replaces the opinion.

Two properties matter more than the numbers themselves. The section totals must be EXACT and
must sum to the ledger total, or the table is plausible rather than true. And the per-field
figures must be labelled as the sampled estimates they are - a sampled number reported as
exact is the failure this package keeps finding, in the one place where it would be most
tempting to round off.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark.native_row_sink import (
    KEY_SAMPLE_EVERY,
    RowSink,
)


class ByteAttributionTest(unittest.TestCase):
    """The size question needs a table, and a table that does not add up is not one."""

    def _sink(self, rows):
        directory = Path(tempfile.mkdtemp())
        sink = RowSink(directory / "lifecycle.jsonl", ledger="lifecycle")
        for row in rows:
            sink.write(row)
        return sink.close()

    def test_section_bytes_sum_exactly_to_the_ledger_total(self):
        """EXACT, not approximate. Every byte written is attributed to something.

        This is the assertion that would catch a row whose section cannot be determined
        being counted in the total and nowhere else - which is how an attribution table
        comes to look complete while quietly under-reporting whichever section is hardest
        to name.
        """
        rows = [{"emitting_section": "4.6", "v": "x" * 40} for _ in range(30)]
        rows += [{"emitting_section": "4.13", "v": "y" * 400} for _ in range(30)]
        rows += [{"no_section_here": 1}]
        receipt = self._sink(rows)
        by_section = receipt["bytes_by_section"]
        self.assertEqual(sum(by_section.values()), receipt["bytes"])
        self.assertEqual(sum(receipt["rows_by_section"].values()), receipt["row_count"])
        # A row with no section is attributed to the LEDGER rather than dropped, so the sum
        # above cannot be made to balance by discarding what is hard to classify.
        self.assertIn("lifecycle", by_section)

    def test_it_separates_a_big_section_from_a_busy_one(self):
        """Row count and byte count answer different questions, so both are reported.

        4.13 here emits the same number of rows as 4.6 and ten times the bytes. A decision
        made on counts alone would rank them equal, which is exactly the wrong answer for a
        volume problem.
        """
        rows = [{"emitting_section": "4.6", "v": "x" * 40} for _ in range(30)]
        rows += [{"emitting_section": "4.13", "v": "y" * 400} for _ in range(30)]
        receipt = self._sink(rows)
        self.assertEqual(receipt["rows_by_section"]["4.6"], receipt["rows_by_section"]["4.13"])
        self.assertGreater(
            receipt["bytes_by_section"]["4.13"], 5 * receipt["bytes_by_section"]["4.6"]
        )

    def test_field_estimate_is_labelled_an_estimate_and_names_the_heavy_field(self):
        """A sampled number reported as exact is the failure this package keeps finding.

        The per-field table exists because the expensive thing is usually one field rather
        than one section - a nested book snapshot inside an otherwise ordinary row. Naming
        it is what turns "4.9 is large" into a decision someone can actually take.
        """
        rows = [
            {"emitting_section": "4.9", "tiny": index, "book_full": {"levels": ["z" * 200] * 5}}
            for index in range(400)
        ]
        receipt = self._sink(rows)
        estimate = receipt["field_bytes_estimated"]
        self.assertEqual(estimate["sample_every_nth_row"], KEY_SAMPLE_EVERY)
        self.assertGreater(estimate["rows_sampled"], 0)
        by_field = estimate["bytes_by_field"]
        # The heavy field is named FIRST, which is the point of the table.
        self.assertEqual(next(iter(by_field)), "book_full")
        self.assertGreater(by_field["book_full"], by_field["tiny"])

    def test_the_sample_rate_is_prime_so_it_cannot_lock_onto_one_row_of_a_group(self):
        """A round rate would measure the same position in every group's emission cycle.

        The traversal emits rows in a repeating per-group pattern. With a sample rate that
        shares a factor with that cycle length, every sampled row is the same KIND of row,
        and the estimate describes one slice of the data while looking like all of it. This
        pins the property rather than the number, so the rate can change and the reason
        cannot be lost.
        """
        self.assertGreater(KEY_SAMPLE_EVERY, 1)
        for factor in range(2, int(KEY_SAMPLE_EVERY ** 0.5) + 1):
            self.assertNotEqual(KEY_SAMPLE_EVERY % factor, 0, f"divisible by {factor}")

    def test_attribution_survives_the_read_back_that_proves_retention(self):
        """The sink's own tally is not evidence; the file is. Both must agree.

        `reconcile` exists because a counter agreeing with itself proves only that the code
        is self-consistent, which is what a silently failed write leaves intact. The same
        applies to the new table, so it is checked against a receipt taken after the rows
        were read back off disk.
        """
        directory = Path(tempfile.mkdtemp())
        sink = RowSink(directory / "lifecycle.jsonl", ledger="lifecycle")
        rows = [{"emitting_section": "4.14", "v": index} for index in range(25)]
        for row in rows:
            sink.write(row)
        receipt = sink.reconcile(expected_rows=len(rows))
        self.assertEqual(receipt["rows_read_back_from_disk"], len(rows))
        self.assertEqual(receipt["bytes_by_section"]["4.14"], receipt["bytes"])
        on_disk = list(sink.read_back())
        self.assertEqual(len(on_disk), len(rows))

class SinkEncodesOnceTest(unittest.TestCase):
    """The bytes on disk, the digest and the byte count are ONE encoding, not two agreeing.

    `write` encoded every line to UTF-8 twice: once explicitly for the digest, and again
    inside the text handle. Over a member ledger measured at 9.2 GB that is a second full
    encoding pass bought for nothing.

    This is a guard rather than a red test - the change removes work and must not move a
    byte. So it pins the property that makes it safe, independently of how the sink is
    implemented: the receipt's digest and length must describe THE FILE. Non-ASCII is in
    the data on purpose, because a careless binary conversion is exactly where a multi-byte
    character stops agreeing with its own length.
    """

    def test_digest_and_length_describe_the_file_on_disk(self):
        import hashlib

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "member.jsonl"
            sink = RowSink(path, ledger="exact_member_rows")
            rows = [
                {"emitting_section": "4.6", "symbol": "NGX1", "note": "plain ascii"},
                {"emitting_section": "4.6", "symbol": "NG\u00d81", "note": "caf\u00e9 \u00b5s \u20ac"},
                {"emitting_section": "4.9", "symbol": "\u65e5\u672c", "note": "\U0001f600 astral"},
            ]
            for row in rows:
                sink.write(row)
            receipt = sink.close()

            raw = path.read_bytes()
            self.assertEqual(receipt["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(receipt["bytes"], len(raw))
            self.assertEqual(receipt["row_count"], len(rows))

    def test_the_ledger_is_pure_ascii_because_ensure_ascii_is_on(self):
        """Written down because I assumed the opposite and the test caught it.

        `json.dumps` defaults to ensure_ascii=True, so every non-ASCII character is escaped
        to \\uXXXX and the ledger is pure ASCII - bytes and characters are always equal. That
        is what makes the file hash portable across locales, and it is the reason
        `ensure_ascii` must not be turned off to save space: it would change every byte of
        every ledger and with them every hash the run is verified by.
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "member.jsonl"
            sink = RowSink(path, ledger="exact_member_rows")
            sink.write({"emitting_section": "4.6", "v": "caf\u00e9 \u65e5\u672c \U0001f600"})
            receipt = sink.close()
            raw = path.read_bytes()
            raw.decode("ascii")  # raises if anything non-ASCII reached the file
            self.assertEqual(receipt["bytes"], len(raw))
            self.assertEqual(len(raw), len(path.read_text(encoding="utf-8")))



if __name__ == "__main__":
    unittest.main()
