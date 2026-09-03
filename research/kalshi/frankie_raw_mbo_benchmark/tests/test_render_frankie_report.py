"""The principal's report is a RENDER of his findings, never a separately authored document.

WHY THIS EXISTS. Run 33605852433 produced 44 findings in
`frankie_principal_findings.json` - chain depths, family crosswalks, exhaustion runways,
prebirth recognition, dipole decoupling - and a hand-authored
`frankie_calculation_assessment.md` beside it. The report was written separately from the
findings, so the 44 were never surfaced to Greg at all; what he saw was a verdict on whether
each section was worth keeping. A report authored apart from its evidence can omit the
evidence and still look complete.

So the findings artifact is the STORE and the report is a RENDER, exactly as DECISIONS.md,
OPEN_ITEMS.md and RUN_SOP.md already are in this tree. Edit the store, re-render, never the
render. The single load-bearing property is that EVERY finding reaches the page.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark.render_frankie_report import (
    REPORT_FILENAME,
    ReportError,
    render_report,
    write_report,
)


def finding(fid, section, **over):
    base = {
        "id": fid,
        "section": section,
        "category": "duration_recurrence_extension_chain_completion",
        "claim": f"claim text for {fid}",
        "evidence": {"n": 91, "nested": {"depth": 1}},
        "falsifier": f"falsifier for {fid}",
        "confidence_basis": "single day, one instrument",
    }
    base.update(over)
    return base


def artifact(findings=None, **over):
    body = {
        "schema": "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_FINDINGS_V1",
        "principal": "claude-opus-5",
        "arm": "A_MEMORY",
        "role": "REAL_TIME_FRANKIE",
        "run_id": "frankie-a-memory-rt-1-1",
        "source_day": "20211003",
        "evidence_result_hash": "cb685e0e",
        "causal_clock": "ts_recv_ns",
        "continuity_segment": 18904,
        "findings": findings if findings is not None else [
            finding("F-01", "4.10"), finding("F-02", "4.13"), finding("F-03", "4.10"),
        ],
    }
    body.update(over)
    return body


class EveryFindingReachesThePageTest(unittest.TestCase):
    """The one property that matters. A render that drops a finding is the defect itself."""

    def test_every_finding_id_appears(self):
        body = artifact([finding(f"F-{i:02d}", "4.10") for i in range(1, 45)])
        text = render_report(body)
        for i in range(1, 45):
            self.assertIn(f"F-{i:02d}", text, f"F-{i:02d} did not reach the report")

    def test_the_count_is_stated_so_a_dropped_finding_is_visible(self):
        """A reader cannot notice an absent finding without a denominator to check against."""
        body = artifact([finding(f"F-{i:02d}", "4.10") for i in range(1, 45)])
        self.assertIn("44", render_report(body))

    def test_the_rendered_count_matches_the_artifact(self):
        for n in (1, 3, 17):
            with self.subTest(n=n):
                body = artifact([finding(f"F-{i:02d}", "4.6") for i in range(n)])
                text = render_report(body)
                self.assertEqual(text.count("#### F-"), n)

    def test_claim_evidence_falsifier_and_basis_all_survive(self):
        """Frankie's falsifiers were the most valued content of the prior run. A report that
        carried claims without them would spend exactly the credibility they earned."""
        text = render_report(artifact([finding("F-01", "4.7")]))
        self.assertIn("claim text for F-01", text)
        self.assertIn("falsifier for F-01", text)
        self.assertIn("single day, one instrument", text)
        self.assertIn("91", text)

    def test_nested_evidence_is_not_flattened_away(self):
        text = render_report(artifact([finding("F-01", "4.7")]))
        self.assertIn("depth", text)


class GroupingTest(unittest.TestCase):
    def test_findings_are_grouped_by_section(self):
        text = render_report(artifact())
        self.assertIn("4.10", text)
        self.assertIn("4.13", text)

    def test_a_multi_section_finding_is_not_dropped_by_grouping(self):
        """Real findings carry sections like '4.3 / 4.14'. Grouping must not lose one that
        does not match a single tidy key."""
        body = artifact([finding("F-07", "4.3 / 4.5 / 4.9 / 4.14")])
        self.assertIn("F-07", render_report(body))

    def test_output_is_deterministic(self):
        body = artifact()
        self.assertEqual(render_report(body), render_report(body))


class IdentityTest(unittest.TestCase):
    def test_the_run_identity_is_on_the_page(self):
        """A report that cannot say which run it describes is how a verdict came to be read
        against the wrong run once already in this tree."""
        text = render_report(artifact())
        for needle in ("frankie-a-memory-rt-1-1", "20211003", "cb685e0e", "A_MEMORY",
                       "claude-opus-5", "ts_recv_ns"):
            self.assertIn(needle, text)

    def test_it_declares_itself_a_render(self):
        self.assertIn("render", render_report(artifact()).lower())


class RefusalTest(unittest.TestCase):
    def test_an_artifact_with_no_findings_is_refused(self):
        """An empty artifact is a failed spawn, not an empty success - the staging layer
        already says so, and the renderer must not paper over it with a tidy empty page."""
        with self.assertRaises(ReportError):
            render_report(artifact([]))

    def test_a_finding_missing_its_claim_is_refused_by_name(self):
        with self.assertRaises(ReportError) as caught:
            render_report(artifact([{"id": "F-01", "section": "4.6"}]))
        self.assertIn("F-01", str(caught.exception))


class WriteReportTest(unittest.TestCase):
    def test_it_writes_beside_the_artifact_under_a_distinct_name(self):
        """It must NEVER overwrite the hand-authored assessment: that document is a record,
        and D60 does not permit destroying one to make room for a generated file."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frankie_principal_findings.json"
            path.write_text(json.dumps(artifact()), encoding="utf-8")
            assessment = Path(tmp) / "frankie_calculation_assessment.md"
            assessment.write_text("hand authored, keep me", encoding="utf-8")

            written = write_report(path)

            self.assertEqual(written.name, REPORT_FILENAME)
            self.assertNotEqual(written.name, assessment.name)
            self.assertEqual(assessment.read_text(), "hand authored, keep me")
            self.assertIn("F-01", written.read_text())

    def test_rewriting_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frankie_principal_findings.json"
            path.write_text(json.dumps(artifact()), encoding="utf-8")
            first = write_report(path).read_text()
            second = write_report(path).read_text()
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()


class WhatThePrincipalReadTest(unittest.TestCase):
    """F-10 / F-14: the report says in words which exact ledgers were read."""

    def test_the_read_status_per_ledger_is_rendered(self):
        body = artifact(evidence_read={
            "exact_member_ledger": "NOT_READ",
            "exact_lifecycle_and_runway_ledger": "PARTIAL",
            "legacy_observable_rows": "READ",
        })
        text = render_report(body)
        self.assertIn("## What the principal read", text)
        self.assertIn("| `exact_member_ledger` | **NOT_READ** |", text)
        self.assertIn("| `legacy_observable_rows` | **READ** |", text)
        self.assertIn("rests on the\nrunner's counters", text)

    def test_all_read_says_so(self):
        body = artifact(evidence_read={"exact_member_ledger": "READ"})
        self.assertIn("Every exact ledger was declared READ.", render_report(body))

    def test_an_undeclared_artifact_is_rendered_as_pre_gate_not_silently(self):
        body = artifact()
        body.pop("evidence_read", None)
        text = render_report(body)
        self.assertIn("`evidence_read` is not declared on this artifact", text)
        self.assertIn("resting on counters", text)


class CrosswalkSectionTest(unittest.TestCase):
    """S121 slice 3: the report is the choke point every artifact passes, so the 99-layer
    crosswalk - what reached him, computed from receipts - is appended there and nowhere a
    reader could miss it. Without a crosswalk the report is exactly what it was."""

    @classmethod
    def setUpClass(cls):
        from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
            load_registry,
        )
        from research.kalshi.frankie_raw_mbo_benchmark.native_layer_crosswalk import crosswalk

        cls.crosswalk = crosswalk(load_registry(), arm="A_MEMORY")

    def test_a_crosswalk_body_is_appended_with_its_totals_and_hash(self):
        text = render_report(artifact(arm="A_MEMORY"), crosswalk=self.crosswalk)
        self.assertIn("## Layer crosswalk", text)
        totals = self.crosswalk["totals"]
        self.assertIn(f"| registered | {totals['registered']} |", text)
        self.assertIn(f"| inputs_applicable | {totals['inputs_applicable']} |", text)
        self.assertIn(f"| outputs_pending | {totals['outputs_pending']} |", text)
        self.assertIn(self.crosswalk["crosswalk_sha256"], text)
        # The findings still come first and are all still there.
        self.assertLess(text.index("## Findings by section"), text.index("## Layer crosswalk"))
        self.assertEqual(text.count("#### F-"), 3)

    def test_without_a_crosswalk_the_report_is_unchanged(self):
        self.assertEqual(render_report(artifact()), render_report(artifact(), crosswalk=None))
        self.assertNotIn("## Layer crosswalk", render_report(artifact()))

    def test_a_crosswalk_that_could_not_be_computed_is_stated_in_the_report(self):
        """A failure recorded only on stderr expires with the terminal; the report says so."""
        text = render_report(
            artifact(), crosswalk_note="crosswalk could not be computed: fixture reason 4711"
        )
        self.assertIn("## Layer crosswalk", text)
        self.assertIn("fixture reason 4711", text)

    def test_write_report_carries_the_crosswalk_to_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frankie_principal_findings.json"
            path.write_text(json.dumps(artifact(arm="A_MEMORY")), encoding="utf-8")
            written = write_report(path, crosswalk=self.crosswalk)
            text = written.read_text()
        self.assertIn("## Layer crosswalk", text)
        self.assertIn(f"| registered | {self.crosswalk['totals']['registered']} |", text)

