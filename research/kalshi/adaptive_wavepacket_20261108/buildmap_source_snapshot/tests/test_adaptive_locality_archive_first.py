"""Archive-first admission holds every unresolved observation without fitting it away."""
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from adaptive_locality.core import LocalityError
from adaptive_locality.information import derive_information
from adaptive_locality.standalone_review import archive_first_geometric_review
from adaptive_locality.research_holds import ResearchHoldRegistry
from test_adaptive_locality_geometry_validation import original_series


class ArchiveFirstGeometricReviewTests(unittest.TestCase):
    def test_bounded_success_is_raw_archived_and_still_unverified(self):
        raw,bins,info=original_series(96)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"admission.sqlite"
            with ResearchHoldRegistry(path,source_identity="geometry-raw",
                                      contract_identity=bins.identity()) as registry:
                receipt=archive_first_geometric_review(
                    raw,bins,registry,"a","b",archive_prefix="case-good")
                self.assertEqual(receipt["original_raw_frames"],96)
                self.assertEqual(receipt["retained_information_frames"],96)
                self.assertEqual(receipt["status"],"RETAINED_FOR_FURTHER_INSPECTION")
                self.assertEqual(receipt["scientific_jobs_eliminated"],0)
                self.assertEqual(receipt["original_frames_dropped"],0)
                self.assertFalse(receipt["averaged_or_smoothed_original_values"])
                self.assertIsNotNone(receipt["static_report"])
                self.assertIsNotNone(receipt["predictive_report"])
                self.assertIsNotNone(receipt["static_archive_receipt"])
                self.assertIsNotNone(receipt["predictive_archive_receipt"])
                self.assertEqual(receipt, archive_first_geometric_review(
                    raw,bins,registry,"a","b",archive_prefix="case-good"))
                self.assertTrue(registry.verify())
                rawcopy=registry.read_archive("case-good-unmodified-raw")["records"]
                self.assertEqual(rawcopy[0]["samples"][0]["order_id"],
                                 raw[0].samples[0].order_id)
                self.assertEqual(rawcopy[0]["samples"][0]["value"],
                                 raw[0].samples[0].value)
                self.assertEqual(len(registry.read_archive("case-good-derived-information")
                                     ["records"]),len(info))
                self.assertGreater(len(receipt["research_case_ids"]),0)
            with ResearchHoldRegistry(path,source_identity="geometry-raw",
                                      contract_identity=bins.identity()) as registry:
                self.assertTrue(registry.verify())
                self.assertEqual(registry.read_archive("case-good-unmodified-raw")
                                 ["records"],rawcopy)

    def test_out_of_calibration_raw_is_archived_before_fit_and_inspectable(self):
        raw,bins,info=original_series(96)
        unusual=replace(raw[0].samples[0],value=50.)
        changed=(replace(raw[0],samples=(unusual,)+raw[0].samples[1:]),)+raw[1:]
        self.assertEqual(derive_information(changed[0],bins).status,"REVIEW_REQUIRED")
        with tempfile.TemporaryDirectory() as folder:
            with ResearchHoldRegistry(Path(folder)/"review.sqlite",
                                      source_identity="geometry-raw",
                                      contract_identity=bins.identity()) as registry:
                receipt=archive_first_geometric_review(
                    changed,bins,registry,"a","b",archive_prefix="out-of-bins")
                self.assertIsNone(receipt["static_report"])
                self.assertIsNone(receipt["predictive_report"])
                self.assertEqual(len(receipt["research_case_ids"]),1)
                self.assertEqual(registry.read_archive("out-of-bins-unmodified-raw")
                                 ["records"][0]["samples"][0]["value"],50.)
                case=registry.get(receipt["research_case_ids"][0])
                self.assertEqual(case["reason"],"INFORMATION_UNVERIFIED_INPUT_NO_FIT")
                self.assertIn("OUT_OF_FROZEN_RANGE",
                              str(case["details"]["review_clock_reasons"]))
                self.assertTrue(registry.verify())

    def test_short_and_budget_limited_series_are_archived_not_truncated(self):
        for n,limit in ((8,12000),(160,90)):
            with self.subTest(n=n):
                raw,bins,_=original_series(n)
                with tempfile.TemporaryDirectory() as folder:
                    with ResearchHoldRegistry(Path(folder)/"r.sqlite",
                                              source_identity="geometry-raw",
                                              contract_identity=bins.identity()) as registry:
                        receipt=archive_first_geometric_review(
                            raw,bins,registry,"a","b",archive_prefix="bounded",
                            max_frames=limit)
                        self.assertIsNone(receipt["predictive_report"])
                        self.assertEqual(receipt["original_raw_frames"],n)
                        self.assertEqual(len(registry.read_archive("bounded-unmodified-raw")
                                             ["records"]),n)
                        reasons=[registry.get(case)["reason"] for case in receipt["research_case_ids"]]
                        self.assertTrue(any("PREDICTIVE_GEOMETRY_" in reason for reason in reasons))
                        self.assertTrue(registry.verify())

    def test_same_archive_name_cannot_replace_different_raw_observations(self):
        raw,bins,info=original_series(48)
        with tempfile.TemporaryDirectory() as folder:
            with ResearchHoldRegistry(Path(folder)/"r.sqlite",
                                      source_identity="geometry-raw",
                                      contract_identity=bins.identity()) as registry:
                receipt=archive_first_geometric_review(raw,bins,registry,"a","b",
                                                       archive_prefix="no-clobber")
                altered=replace(raw[0].samples[0],value=2.5)
                changed=(replace(raw[0],samples=(altered,)+raw[0].samples[1:]),)+raw[1:]
                with self.assertRaises(LocalityError):
                    archive_first_geometric_review(changed,bins,registry,"a","b",
                                                   archive_prefix="no-clobber")
                self.assertEqual(registry.read_archive("no-clobber-unmodified-raw")
                                 ["records"][0]["samples"][0]["value"],
                                 raw[0].samples[0].value)
                self.assertTrue(registry.verify())


if __name__=="__main__":
    unittest.main()
