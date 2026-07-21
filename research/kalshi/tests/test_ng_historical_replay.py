import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_historical_manifest import (  # noqa: E402
    G15_DATES,
    expected_g15_manifest,
    validate_manifest,
)
from ng_historical_replay import (  # noqa: E402
    NORMALIZED_SCHEMA,
    ReplayError,
    merge_sorted_sources,
    replay_events,
)
from ng_live_operator import F_LAST  # noqa: E402


def ready_manifest():
    manifest = expected_g15_manifest(publisher_id=1)
    for entry in manifest["entries"]:
        entry.update(
            status="PRESENT",
            location=f"s3://fixture/{entry['source_kind']}/{entry['day']}",
            publisher_id=1,
            definition_date="2026-03-01" if entry["raw_symbol"] == "NGJ26" else "2026-03-20",
            definition_start_s=0.0,
            definition_end_s=2000.0,
            event_start_s=1.0,
            event_end_s=1000.0,
            record_count=100,
            size_bytes=1000,
            inventory_observed_at="2026-07-21T00:00:00Z",
        )
    return manifest


def base_identity(day="20260316"):
    april = day <= "20260319"
    return {
        "dataset": "GLBX.MDP3",
        "publisher_id": 1,
        "instrument_id": 1008 if april else 996,
        "raw_symbol": "NGJ26" if april else "NGK26",
        "definition_date": "2026-03-01" if april else "2026-03-20",
        "session_day": day,
    }


def event(identity, event_type, ts, seq, **kwargs):
    return {
        **identity,
        "schema": NORMALIZED_SCHEMA,
        "event_type": event_type,
        "ts_event_s": float(ts),
        "source_sequence": int(seq),
        **kwargs,
    }


def basic_events(*, final_flags=F_LAST, trade_sequence=(1, 2, 3, 4, 5, 6)):
    identity = base_identity()
    rows = [event(identity, "definition", 1, 1)]
    for index, seq in enumerate(trade_sequence, 2):
        rows.append(
            event(
                identity,
                "trade",
                index,
                seq,
                price=3.0 + index * 0.001,
                size=4,
                side="B",
            )
        )
    rows.append(
        event(
            identity,
            "mbo",
            20,
            1,
            action="A",
            side="B",
            size=10,
            order_id=1,
            price=3.005,
            flags=final_flags,
        )
    )
    return rows


class HistoricalManifestTests(unittest.TestCase):
    def test_template_is_unknown_not_fake_present(self):
        manifest = expected_g15_manifest(publisher_id=1)
        report = validate_manifest(manifest)
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(len(report["unknown_entries"]), len(G15_DATES) * 2)
        self.assertFalse(manifest["remote_inventory_verified"])

    def test_ready_manifest_requires_paired_overlap(self):
        manifest = ready_manifest()
        report = validate_manifest(manifest)
        self.assertEqual(report["status"], "READY")
        self.assertTrue(report["can_replay_all_g15"])
        self.assertEqual(report["ready_days"], list(G15_DATES))

    def test_contract_mismatch_blocks(self):
        manifest = ready_manifest()
        manifest["entries"][0]["raw_symbol"] = "NGK26"
        report = validate_manifest(manifest)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertTrue(any("raw_symbol" in message for message in report["errors"]))


class HistoricalReplayTests(unittest.TestCase):
    def setUp(self):
        self.manifest = ready_manifest()
        self.prior = {"up": 0.4, "flat": 0.2, "down": 0.4}

    def test_emits_only_on_completed_mbo_boundary(self):
        no_last = replay_events(
            basic_events(final_flags=0),
            manifest=self.manifest,
            blind_prior=self.prior,
        )
        self.assertEqual(no_last["completed_mbo_event_boundaries"], 0)
        self.assertEqual(no_last["streams"][0]["n_states"], 0)

        completed = replay_events(
            basic_events(final_flags=F_LAST),
            manifest=self.manifest,
            blind_prior=self.prior,
        )
        self.assertEqual(completed["completed_mbo_event_boundaries"], 1)
        state = completed["streams"][0]["states"][0]
        self.assertTrue(state["completed_mbo_event_boundary"])
        self.assertEqual(state["authority"], "REFINE_INPUT_ONLY")
        self.assertFalse(state["execution_authority"])

    def test_blind_prior_is_immutable(self):
        original = copy.deepcopy(self.prior)
        replay_events(basic_events(), manifest=self.manifest, blind_prior=self.prior)
        self.assertEqual(self.prior, original)

    def test_sequence_gap_is_visible_and_stands_down(self):
        result = replay_events(
            basic_events(trade_sequence=(1, 2, 4, 5, 6, 7)),
            manifest=self.manifest,
            blind_prior=self.prior,
        )
        self.assertEqual(len(result["sequence_gaps"]), 1)
        state = result["streams"][0]["states"][0]
        self.assertIn("collector_skipped_records", state["availability"]["stand_down_reasons"])
        self.assertFalse(state["availability"]["flow_update_allowed"])
        self.assertFalse(state["availability"]["queue_update_allowed"])

    def test_unknown_manifest_is_refused_by_default(self):
        with self.assertRaises(ReplayError):
            replay_events(
                basic_events(),
                manifest=expected_g15_manifest(publisher_id=1),
                blind_prior=self.prior,
            )

    def test_wrong_g15_contract_is_rejected(self):
        rows = basic_events()
        rows[-1]["raw_symbol"] = "NGK26"
        rows[-1]["instrument_id"] = 996
        rows[-1]["definition_date"] = "2026-03-20"
        with self.assertRaises(ReplayError):
            replay_events(rows, manifest=self.manifest, blind_prior=self.prior)

    def test_merge_rejects_backwards_source(self):
        identity = base_identity()
        source = [
            event(identity, "trade", 2, 2, price=3.0, size=1, side="B"),
            event(identity, "trade", 1, 1, price=3.0, size=1, side="B"),
        ]
        with self.assertRaises(ReplayError):
            list(merge_sorted_sources([source]))


if __name__ == "__main__":
    unittest.main()
