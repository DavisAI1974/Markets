from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_kitchen_sink_audit_s121 as ks  # noqa: E402


def row(family, *, possessed=True, causal=True, contaminated=False, accessible=True, status="ACCESSIBLE"):
    return {
        "family": family,
        "source": f"source/{family}",
        "possessed": possessed,
        "available_by_cutoff": causal,
        "future_answer_contaminated": contaminated,
        "accessible_to_frankie": accessible,
        "status": status,
        "evidence": "synthetic audit evidence",
    }


class KitchenSinkTests(unittest.TestCase):
    def test_possessed_causal_but_unserved_hard_fails(self):
        rows = [row("weather", accessible=False, status="ACCESSIBLE")]
        with self.assertRaisesRegex(ks.KitchenSinkStop, "silently omitted"):
            ks.validate_inventory(rows)

    def test_future_answer_curve_may_be_masked(self):
        rows = [row("target actual curve", contaminated=True, accessible=False, status="FUTURE_MASKED")]
        out = ks.validate_inventory(rows)
        self.assertEqual(out["future_masked_count"], 1)

    def test_unavailable_historical_family_is_accounted_not_silently_dropped(self):
        rows = [row("ECMWF historical forecast", causal=False, accessible=False, status="UNAVAILABLE_AT_CUTOFF")]
        out = ks.validate_inventory(rows)
        self.assertEqual(out["unavailable_at_cutoff_count"], 1)

    def test_major_domain_inventory_scope_must_be_accounted_for(self):
        rows = [
            row("brain schema plays"), row("Databento MBO tape"), row("EIA storage"), row("NOAA weather"),
            row("fundamentals production LNG feedgas power"), row("COT positioning flows"),
            row("vol options"), row("basis contract structure"), row("calendar events releases"),
            row("prior price historical analogues"),
            row("target actual curve", contaminated=True, accessible=False, status="FUTURE_MASKED"),
        ]
        ks.assert_required_domains_present(rows)
        out = ks.validate_inventory(rows)
        self.assertEqual(out["status"], "KITCHEN_SINK_COMPLETE")

    def test_missing_major_domain_bucket_fails_scope_gate(self):
        rows = [row("brain schema plays"), row("Databento MBO tape")]
        with self.assertRaisesRegex(ks.KitchenSinkStop, "required domain bucket"):
            ks.assert_required_domains_present(rows)


if __name__ == "__main__":
    unittest.main()
