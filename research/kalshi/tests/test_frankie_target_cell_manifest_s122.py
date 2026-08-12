from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_target_cell_manifest_s122 as m  # noqa: E402


def row(family, field, *, possessed=True, causal=True, contaminated=False,
        accessible=True, status="ACCESSIBLE"):
    return {
        "family": family,
        "field": field,
        "source": f"source/{family}/{field}",
        "possessed": possessed,
        "available_by_cutoff": causal,
        "future_answer_contaminated": contaminated,
        "accessible_to_frankie": accessible,
        "status": status,
        "evidence": "explicit test evidence",
    }


def full_rows():
    return [
        row("brain schema plays", "canonical brain"),
        row("Databento MBO tape", "mbo events"),
        row("EIA storage", "storage state"),
        row("NOAA weather", "weather state"),
        row("fundamentals production LNG feedgas power", "fundamental state"),
        row("COT positioning flows", "cot state"),
        row("vol options", "option state"),
        row("basis contract structure", "basis state"),
        row("calendar events releases", "calendar state"),
        row("prior price historical analogues", "prior history"),
        row("target actual curve", "realized target curve", contaminated=True,
            accessible=False, status="FUTURE_MASKED"),
    ]


class TargetCellManifestTests(unittest.TestCase):
    def test_complete_manifest_compiles_and_hashes(self):
        doc = {
            "target": {"group": "g18", "date": "20260427", "cutoff": "2026-04-27T09:29:59-04:00", "namespace": "test"},
            "rows": full_rows(),
        }
        out = m.compile_manifest(doc)
        self.assertEqual(out["readiness"], "READY_OFFLINE")
        self.assertEqual(len(out["sha256"]), 64)
        self.assertEqual(out["summary"]["future_masked_count"], 1)

    def test_one_possessed_causal_field_omission_stops_family(self):
        rows = full_rows()
        rows.append(row("NOAA weather", "wind speed", accessible=False))
        with self.assertRaisesRegex(m.TargetCellManifestStop, "silently omitted"):
            m.compile_manifest({
                "target": {"group": "g18", "date": "20260427", "cutoff": "T", "namespace": "test"},
                "rows": rows,
            })

    def test_unknown_status_cannot_be_guessed_away(self):
        rows = full_rows()
        rows[0]["status"] = "UNKNOWN"
        with self.assertRaisesRegex(m.TargetCellManifestStop, "invalid status"):
            m.compile_manifest({
                "target": {"group": "g18", "date": "20260427", "cutoff": "T", "namespace": "test"},
                "rows": rows,
            })

    def test_duplicate_field_fails(self):
        rows = full_rows()
        rows.append(dict(rows[0]))
        with self.assertRaisesRegex(m.TargetCellManifestStop, "duplicate target-cell field"):
            m.compile_manifest({
                "target": {"group": "g18", "date": "20260427", "cutoff": "T", "namespace": "test"},
                "rows": rows,
            })

    def test_missing_domain_bucket_fails(self):
        rows = [row("brain schema plays", "brain"), row("Databento MBO tape", "mbo")]
        with self.assertRaisesRegex(m.TargetCellManifestStop, "required domain bucket"):
            m.compile_manifest({
                "target": {"group": "g18", "date": "20260427", "cutoff": "T", "namespace": "test"},
                "rows": rows,
            })


if __name__ == "__main__":
    unittest.main()
