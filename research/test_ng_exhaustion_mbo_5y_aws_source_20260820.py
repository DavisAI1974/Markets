from __future__ import annotations

import unittest

from ng_exhaustion_mbo_5y_aws_source_20260820 import (
    SourceSelectionError,
    normalize_dbn_key,
    resolve_canonical_keys,
)
from ng_exhaustion_mbo_v4_full_state_replay_20260820 import full_state_envelope
from ng_exhaustion_mbo_v4_state_adapter_20260820 import F_LAST, V4MboAdapter


BUCKET = "bento-568968024170-us-east-2-an"
PREFIX = "nymex/ng_mbo_5y_v0/"


class CanonicalSelectionTests(unittest.TestCase):
    def test_normalizes_key_and_s3_uri(self):
        key = PREFIX + "2026/example.dbn.zst"
        self.assertEqual(normalize_dbn_key(key, BUCKET, PREFIX), key)
        self.assertEqual(normalize_dbn_key(f"s3://{BUCKET}/{key}", BUCKET, PREFIX), key)

    def test_prefers_explicit_canonical_field(self):
        manifest = {
            "status": "COMPLETE",
            "canonical_dbn_keys": [
                f"s3://{BUCKET}/{PREFIX}a.dbn.zst",
                PREFIX + "b.dbn",
            ],
            "other_objects": [PREFIX + "duplicate.dbn.zst"],
        }
        keys, field = resolve_canonical_keys(manifest, BUCKET, PREFIX)
        self.assertEqual(field, "canonical_dbn_keys")
        self.assertEqual(keys, [PREFIX + "a.dbn.zst", PREFIX + "b.dbn"])

    def test_fails_closed_without_explicit_selection(self):
        manifest = {
            "status": "COMPLETE",
            "objects": [PREFIX + "maybe.dbn.zst"],
        }
        with self.assertRaises(SourceSelectionError):
            resolve_canonical_keys(manifest, BUCKET, PREFIX)

    def test_conflicting_same_tier_selection_fails(self):
        manifest = {
            "canonical_dbn_keys": [PREFIX + "a.dbn.zst"],
            "canonical_objects": [PREFIX + "b.dbn.zst"],
        }
        with self.assertRaises(SourceSelectionError):
            resolve_canonical_keys(manifest, BUCKET, PREFIX)


class FullStateReplayTests(unittest.TestCase):
    def test_full_state_exposes_depth_and_fifo(self):
        adapter = V4MboAdapter()
        frame, legacy = adapter.apply(
            {
                "instrument_id": 1,
                "publisher_id": 1,
                "channel_id": 1,
                "order_id": 101,
                "action": "A",
                "side": "B",
                "price": 3_000_000_000,
                "size": 7,
                "flags": F_LAST,
                "sequence": 1,
                "ts_event": 1_000_000_000,
                "ts_recv": 1_000_000_100,
                "ts_in_delta": 100,
            },
            raw_symbol="NGX6",
        )
        self.assertIsNotNone(frame)
        self.assertTrue(legacy)
        envelope = full_state_envelope(adapter, frame)
        self.assertTrue(envelope["full_depth_exposed"])
        self.assertTrue(envelope["fifo_order_state_exposed"])
        bid = envelope["full_state"]["book"]["bid_levels_full"][0]
        self.assertEqual(bid["fifo_queue"][0]["order_id"], 101)
        self.assertEqual(bid["fifo_queue"][0]["size"], 7)


if __name__ == "__main__":
    unittest.main()
