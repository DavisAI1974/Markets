import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g16_blind_wall import (  # noqa: E402
    BlindWallError,
    G16_DATES,
    build_blind_safe_state,
    session_decision_cutoff_utc,
    validate_blind_safe_state,
)


def source_fixture():
    source = {"_information_clock": {"globex_reopen_et": "Sun 18:00"}}
    for day in G16_DATES:
        source[day] = {
            "dow": datetime.strptime(day, "%Y%m%d").strftime("%a"),
            "known_block": {"as_of": "2026-03-01", "value": 1},
            "future_block": {"knowable_from": "2027-01-01", "value": 2},
            "storage_consensus": {
                "next_print": {
                    "for_report_date": "2026-04-01",
                    "print_datetime_utc": "2026-12-31T15:30:00Z",
                    "consensus_chg_bcf": 34,
                    "source": "tradingeconomics_final_frozen",
                    "consensus_pre_print_bcf": 38,
                    "consensus_pre_print_snapshot_utc": "2026-03-20T06:00:00Z",
                    "final_capture_is_post_print": True,
                    "actual_as_printed_bcf": 25,
                    "surprise_vs_consensus_bcf": -9,
                    "estimates": [
                        {
                            "source": "pre",
                            "pre_print": True,
                            "value_bcf": 38,
                            "snapshot_utc": "2026-03-20T06:00:00Z",
                        },
                        {
                            "source": "post",
                            "pre_print": False,
                            "value_bcf": 34,
                            "snapshot_utc": "2026-04-20T06:00:00Z",
                        },
                    ],
                },
                "last_print": {
                    "print_datetime_utc": "2026-03-01T15:30:00Z",
                    "consensus_chg_bcf": -44,
                    "actual_as_printed_bcf": -54,
                    "surprise_vs_consensus_bcf": -10,
                    "estimates": [
                        {
                            "source": "known_after_release",
                            "pre_print": False,
                            "value_bcf": -44,
                            "snapshot_utc": "2026-03-02T06:00:00Z",
                        }
                    ],
                },
            },
        }
    return source


class CutoffTests(unittest.TestCase):
    def test_sunday_cutoff_is_same_day_before_reopen(self):
        cutoff = session_decision_cutoff_utc("20260329")
        self.assertEqual(cutoff, datetime(2026, 3, 29, 21, 59, 59, tzinfo=timezone.utc))

    def test_weekday_cutoff_is_prior_calendar_day(self):
        cutoff = session_decision_cutoff_utc("20260330")
        self.assertEqual(cutoff, datetime(2026, 3, 29, 21, 59, 59, tzinfo=timezone.utc))


class BlindWallTests(unittest.TestCase):
    def test_future_release_outcomes_are_removed(self):
        result = build_blind_safe_state(source_fixture())
        release = result["days"]["20260329"]["state"]["storage_consensus"]["next_print"]
        self.assertNotIn("actual_as_printed_bcf", release)
        self.assertNotIn("surprise_vs_consensus_bcf", release)
        self.assertNotIn("final_capture_is_post_print", release)
        self.assertNotIn("consensus_chg_bcf", release)
        self.assertEqual(release["blind_wall_release_status"], "UPCOMING_AT_DECISION_CUTOFF")

    def test_preprint_consensus_is_retained(self):
        result = build_blind_safe_state(source_fixture())
        release = result["days"]["20260329"]["state"]["storage_consensus"]["next_print"]
        self.assertEqual(release["consensus_pre_print_bcf"], 38)
        self.assertEqual(len(release["estimates"]), 1)
        self.assertTrue(release["estimates"][0]["pre_print"])

    def test_already_public_release_outcomes_are_retained(self):
        result = build_blind_safe_state(source_fixture())
        release = result["days"]["20260329"]["state"]["storage_consensus"]["last_print"]
        self.assertEqual(release["actual_as_printed_bcf"], -54)
        self.assertEqual(release["surprise_vs_consensus_bcf"], -10)
        self.assertEqual(release["blind_wall_release_status"], "ALREADY_PUBLIC_AT_DECISION_CUTOFF")

    def test_future_knowable_block_is_removed(self):
        result = build_blind_safe_state(source_fixture())
        state = result["days"]["20260329"]["state"]
        self.assertNotIn("future_block", state)
        self.assertIn("known_block", state)

    def test_source_is_immutable(self):
        source = source_fixture()
        original = copy.deepcopy(source)
        build_blind_safe_state(source)
        self.assertEqual(source, original)

    def test_incomplete_g16_dates_are_rejected(self):
        source = source_fixture()
        del source[G16_DATES[-1]]
        with self.assertRaises(BlindWallError):
            build_blind_safe_state(source)

    def test_output_is_non_executable_and_cannot_mutate_brain_or_prior(self):
        result = build_blind_safe_state(source_fixture())
        self.assertFalse(result["execution_authority"])
        self.assertFalse(result["actual_g16_outcomes_used"])
        self.assertFalse(result["target_session_tape_used"])
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(result["may_change_g16_blind_prior"])
        self.assertFalse(result["gate"]["g16_outcome_access_authorized"])

    def test_fingerprints_are_deterministic(self):
        first = build_blind_safe_state(source_fixture())
        second = build_blind_safe_state(source_fixture())
        self.assertEqual(first["artifact_fingerprint"], second["artifact_fingerprint"])
        self.assertEqual(first["source_state_fingerprint"], second["source_state_fingerprint"])

    def test_tampered_artifact_is_rejected(self):
        result = build_blind_safe_state(source_fixture())
        result["days"]["20260329"]["state"]["known_block"]["value"] = 99
        with self.assertRaises(BlindWallError):
            validate_blind_safe_state(result)

    def test_post_cutoff_preprint_snapshot_is_not_retained(self):
        source = source_fixture()
        upcoming = source["20260329"]["storage_consensus"]["next_print"]
        upcoming["consensus_pre_print_snapshot_utc"] = "2026-04-01T06:00:00Z"
        upcoming["estimates"][0]["snapshot_utc"] = "2026-04-01T06:00:00Z"
        result = build_blind_safe_state(source)
        release = result["days"]["20260329"]["state"]["storage_consensus"]["next_print"]
        self.assertNotIn("consensus_pre_print_bcf", release)
        self.assertNotIn("consensus_pre_print_snapshot_utc", release)
        self.assertEqual(release["estimates"], [])

    def test_removal_audit_is_visible(self):
        result = build_blind_safe_state(source_fixture())
        row = result["days"]["20260329"]
        reasons = {item["reason"] for item in row["removals"]}
        self.assertGreater(row["removal_count"], 0)
        self.assertIn("knowable_from_after_decision_cutoff", reasons)
        self.assertIn("future_release_outcome_field", reasons)


if __name__ == "__main__":
    unittest.main()
