"""Turning a finished run into the table the drop decision needs.

The run that filled a volume produced one usable number: the total. Greg's question - which
of the sixteen calculations is the size, and does any of it carry no value - cannot be
answered from a total, and the session that has to answer it cannot read S3, because the
credentials are workflow scoped. So the rendering lives here, in tested repo code that a
workflow calls, rather than in a shell block nobody can run twice.

What these tests pin is honesty about provenance, not formatting. The section figures are
EXACT and must reconcile to the ledger totals; the field figures are SAMPLED and must never
appear without saying so. Those are the two ways a size table can lie while looking right.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark.report_ledger_size import (
    ReportError,
    render_report,
)


def _receipt(ledger, *, sections, fields, sample_every=97, sampled=10):
    total = sum(sections.values())
    return {
        "ledger": ledger,
        "path": f"/opt/run/ledgers/{ledger}.jsonl",
        "row_count": sum(20 for _ in sections),
        "bytes": total,
        "sha256": "a" * 64,
        "bytes_by_section": dict(sections),
        "rows_by_section": {name: 20 for name in sections},
        "field_bytes_estimated": {
            "sample_every_nth_row": sample_every,
            "rows_sampled": sampled,
            "basis": "sum of len(json({key: value})) over sampled rows, scaled by the rate",
            "bytes_by_field": dict(fields),
        },
    }


def _result(**overrides):
    body = {
        "verdict": "ACCEPTED",
        "failed_gates": [],
        "completion_status": "COMPLETE",
        "traversal": {
            "groups_seen": 45_000,
            "records_seen": 56_819,
            "save_points": 10,
            "sections_fed": {"4.6": 1, "4.13": 1},
        },
        "slice": {"records_requested": 56_819, "is_bounded_slice": True,
                  "sources": ["/opt/run/sources/glbx-mdp3-20211003.mbo.dbn.zst"]},
        "ledger_retention": {
            "exact_member_ledger": _receipt(
                "exact_member_ledger",
                sections={"4.13": 8_000_000, "4.6": 2_000_000},
                fields={"book_full": 7_000_000, "order_id": 400_000},
            ),
            "exact_lifecycle_and_runway_ledger": _receipt(
                "exact_lifecycle_and_runway_ledger",
                sections={"4.6": 3_000_000, "queue": 1_000_000},
                fields={"book_full": 2_000_000, "ts_recv": 300_000},
            ),
        },
    }
    body.update(overrides)
    return body


class RenderReportTest(unittest.TestCase):
    def _render(self, body):
        directory = Path(tempfile.mkdtemp())
        path = directory / "calculation_result.json"
        path.write_text(json.dumps(body), encoding="utf-8")
        return render_report(path)

    def test_sections_are_merged_across_ledgers_and_ranked_by_bytes(self):
        """4.6 is split across two ledgers and must be ONE row, or it ranks too low.

        This is the failure that would quietly protect whichever section is spread widest:
        reported per ledger, 4.6's 5 MB shows up as 2 MB and 3 MB and sorts below 4.13's
        single 8 MB block twice over, when in truth it is the second largest thing here.
        """
        text = self._render(_result())
        rows = [line for line in text.splitlines() if line.startswith("| 4.")]
        self.assertTrue(rows[0].startswith("| 4.13"), rows[:3])
        self.assertIn("5,000,000", " ".join(rows), "4.6 must be summed across both ledgers")

    def test_the_totals_reconcile_to_the_ledger_bytes(self):
        """A table that does not add up to what was written is a plausible table."""
        text = self._render(_result())
        self.assertIn("14,000,000", text)  # 10,000,000 + 4,000,000 across both ledgers

    def test_field_figures_are_labelled_sampled_wherever_they_appear(self):
        """The one number here that is not exact must say so where it is read.

        A sampled figure printed beside exact ones, in the same units, with no marking is
        the failure this package keeps finding - and a drop decision taken off an unmarked
        estimate is exactly the kind of decision D60 exists to prevent.
        """
        text = self._render(_result())
        field_heading = next(
            line for line in text.splitlines() if line.startswith("#") and "field" in line.lower()
        )
        self.assertIn("SAMPLED", field_heading.upper())
        self.assertIn("1 row in 97", text)

    def test_it_reports_bytes_per_record_because_that_is_what_sizes_a_volume(self):
        """The per-record figure is the one that was wrong by 9x and cost the run."""
        text = self._render(_result())
        # 14,000,000 bytes over 56,819 records is about 246 bytes per record.
        self.assertRegex(text, r"per record[^\n]*24[0-9]")

    def test_it_refuses_a_result_with_no_retention_block_instead_of_printing_zeroes(self):
        """An empty table is indistinguishable from a run that retained nothing.

        `stream_ledgers=False` keeps the ledgers in RAM and writes no receipts, so this is
        reachable by configuration rather than by corruption - which is exactly when a
        silent zero would be believed.
        """
        body = _result()
        del body["ledger_retention"]
        with self.assertRaises(ReportError):
            self._render(body)

    def test_the_verdict_and_the_slice_travel_with_the_table(self):
        """A size table detached from what produced it cannot be checked against anything."""
        text = self._render(_result(verdict="REFUSED", failed_gates=["exact_once_coverage"]))
        self.assertIn("REFUSED", text)
        self.assertIn("exact_once_coverage", text)
        self.assertIn("glbx-mdp3-20211003.mbo.dbn.zst", text)


if __name__ == "__main__":
    unittest.main()
