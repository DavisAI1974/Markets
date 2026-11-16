"""No original evidence, counterexample, link or source conflict may be dropped."""
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from adaptive_locality.core import LocalityError
from adaptive_locality.coupling import discover_coupling,dipole_window_probe
from adaptive_locality.level2_coupling import discover_level2_balance_links
from adaptive_locality.research_holds import (
    ResearchHoldRegistry,preserve_full_raw_five_step_holds,
    preserve_full_raw_level2_holds)
from test_adaptive_locality_geometry_validation import original_series


class FullRawLevelOneAndTwoTests(unittest.TestCase):
    def test_five_step_full_raw_all_directions_and_conflicts_are_research_holds(self):
        raw,bins,info=original_series(90)
        report=discover_coupling(info)
        self.assertTrue(report["evidence_identity"])
        self.assertEqual(report["result_count"],2)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"five-step.sqlite"
            with ResearchHoldRegistry(path,source_identity="geometry-raw",
                                      contract_identity=bins.identity()) as registry:
                receipt=preserve_full_raw_five_step_holds(
                    report,info,raw,bins,registry,archive_name="all-directions-and-raw")
                self.assertEqual(receipt["retained_full_raw_frames"],len(raw))
                self.assertEqual(receipt["retained_five_step_results"],2)
                self.assertEqual(receipt["unverified_lineage_conflict_count"],0)
                self.assertEqual(receipt["cases"],2)
                self.assertEqual(receipt["scientific_jobs_eliminated"],0)
                self.assertEqual(receipt,preserve_full_raw_five_step_holds(
                    report,info,raw,bins,registry,archive_name="all-directions-and-raw"))
                originals=registry.read_archive("all-directions-and-raw")["records"]
                self.assertEqual(originals[0]["raw_frame"]["samples"][0]["value"],
                                 raw[0].samples[0].value)
                self.assertEqual(originals[-1]["kind"],"COMPLETE_FIVE_STEP_REPORT")
                self.assertEqual(len(originals[-1]["report"]["results"]),2)
                self.assertTrue(registry.verify())
                for case in receipt["research_case_ids"]:
                    self.assertIn("UNVERIFIED_RESULT",registry.get(case)["reason"])
            with ResearchHoldRegistry(path,source_identity="geometry-raw",
                                      contract_identity=bins.identity()) as registry:
                self.assertEqual(registry.read_archive("all-directions-and-raw")["records"],
                                 originals)
                self.assertTrue(registry.verify())

        changed_result=replace(report["results"][0],source_frames=("fake-observation",))
        altered={**report,"results":(changed_result,report["results"][1])}
        with tempfile.TemporaryDirectory() as folder:
            with ResearchHoldRegistry(Path(folder)/"conflict.sqlite",
                                      source_identity="geometry-raw",
                                      contract_identity=bins.identity()) as registry:
                receipt=preserve_full_raw_five_step_holds(
                    altered,info,raw,bins,registry,archive_name="lineage-conflict-retained")
                self.assertEqual(receipt["unverified_lineage_conflict_count"],1)
                self.assertEqual(registry.counts()["cases"],2)
                self.assertIn("LINEAGE_CONFLICT",
                              registry.get(receipt["research_case_ids"][0])["reason"])
                self.assertEqual(registry.read_archive("lineage-conflict-retained")
                                 ["records"][-1]["report"]["results"][0]["source_frames"],
                                 ["fake-observation"])
                self.assertTrue(registry.verify())

    def test_source_change_refused_without_fabricating_raw_evidence(self):
        raw,bins,info=original_series(90)
        report=discover_coupling(info)
        new_sample=replace(raw[5].samples[0],value=3.5)
        changed=(raw[:5]+(replace(raw[5],samples=(new_sample,)+raw[5].samples[1:]),)
                 +raw[6:])
        with tempfile.TemporaryDirectory() as folder:
            with ResearchHoldRegistry(Path(folder)/"review.sqlite",
                                      source_identity="geometry-raw",
                                      contract_identity=bins.identity()) as registry:
                with self.assertRaises(LocalityError):
                    preserve_full_raw_five_step_holds(
                        report,info,changed,bins,registry,archive_name="should-not-claim-valid")
                self.assertEqual(registry.counts()["archives"],0)

    def test_level_two_preserves_each_direction_window_issue_and_complete_raw(self):
        raw,bins,info=original_series(160)
        windows=dipole_window_probe(info,window=40,stride=2)
        report=discover_level2_balance_links(
            windows,source_identity="geometry-raw",
            calibration_identity=bins.identity())
        self.assertEqual(report["original_window_count"],len(windows))
        self.assertEqual(report["input_windows_dropped"],0)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"level2.sqlite"
            with ResearchHoldRegistry(path,source_identity="geometry-raw",
                                      contract_identity=bins.identity()) as registry:
                receipt=preserve_full_raw_level2_holds(
                    report,info,raw,bins,registry,archive_name="level2-with-raw")
                self.assertEqual(receipt["retained_full_raw_frames"],160)
                self.assertEqual(receipt["retained_original_windows"],len(windows))
                self.assertEqual(receipt["retained_level2_links"],report["tested_link_count"])
                self.assertEqual(receipt["retained_unresolved_items"],
                                 report["unresolved_count"])
                self.assertEqual(receipt["unverified_window_lineage_count"],0)
                self.assertEqual(receipt["scientific_jobs_eliminated"],0)
                archive=registry.read_archive("level2-with-raw")
                self.assertEqual(archive["records"][-1]["kind"],"COMPLETE_LEVEL2_REPORT")
                self.assertEqual(len(archive["records"][-1]["report"]
                                     ["retained_original_windows"]),len(windows))
                self.assertTrue(registry.verify())
            with ResearchHoldRegistry(path,source_identity="geometry-raw",
                                      contract_identity=bins.identity()) as registry:
                self.assertEqual(registry.read_archive("level2-with-raw"),archive)
                self.assertEqual(registry.counts()["cases"],receipt["cases"])
                self.assertTrue(registry.verify())

    def test_conflicting_level2_window_lineage_archived_instead_of_dropped(self):
        raw,bins,info=original_series(160)
        windows=list(dipole_window_probe(info,window=40,stride=2))
        windows[0]=replace(windows[0],source_frames=("unmatched-original-id",)+
                            windows[0].source_frames[1:])
        report=discover_level2_balance_links(
            windows,source_identity="geometry-raw",
            calibration_identity=bins.identity())
        with tempfile.TemporaryDirectory() as folder:
            with ResearchHoldRegistry(Path(folder)/"level2-conflict.sqlite",
                                      source_identity="geometry-raw",
                                      contract_identity=bins.identity()) as registry:
                receipt=preserve_full_raw_level2_holds(
                    report,info,raw,bins,registry,archive_name="source-conflicts")
                self.assertEqual(receipt["unverified_window_lineage_count"],1)
                self.assertGreater(receipt["cases"],report["unresolved_count"])
                archive=registry.read_archive("source-conflicts")
                self.assertEqual(archive["records"][-1]["report"]
                                 ["retained_original_windows"][0]["source_frames"][0],
                                 "unmatched-original-id")
                self.assertTrue(any("SOURCE_LINEAGE_CONFLICT" in
                                    registry.get(case)["reason"]
                                    for case in receipt["research_case_ids"]))
                self.assertTrue(registry.verify())


if __name__=="__main__":
    unittest.main()
