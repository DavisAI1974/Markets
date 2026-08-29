"""Tests for the full-capture adapter (D60).

Each test is a DIFFERENTIAL against the hash-locked `V4MboAdapter`: it drives both with the
same records and asserts the base adapter drops something the wrapper keeps. Written that way
on purpose - asserting only that the wrapper HAS a field would still pass if the base adapter
had it all along, and the claim being made is specifically that this data was being lost.
"""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_full_capture_adapter import (
    FullCaptureAdapter,
)
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import (
    F_LAST,
    F_TOB,
    UNDEF_PRICE,
    V4MboAdapter,
)


def rec(*, seq, order_id, action="A", side="B", size=5, price=3_500_000_000,
        last=True, flags=None, ts=1_000_000_000):
    return {
        "instrument_id": 42,
        "publisher_id": 1,
        "channel_id": 0,
        "order_id": order_id,
        "action": action,
        "side": side,
        "price": price,
        "size": size,
        "flags": (F_LAST if last else 0) if flags is None else flags,
        "sequence": seq,
        "ts_event": ts,
        "ts_recv": ts + 150_000,
        "ts_in_delta": 0,
        "source_dbn_object": "20211004.dbn",
        "source_dbn_sha256": "0" * 64,
    }


def drive(adapter, records):
    frames = []
    for r in records:
        frame, _legacy = adapter.apply(
            r, raw_symbol="NGX1", source_dbn_object=r["source_dbn_object"],
            source_dbn_sha256=r["source_dbn_sha256"],
        )
        if frame is not None:
            frames.append(frame)
    return frames


class PerRecordEffectTests(unittest.TestCase):
    def test_the_base_adapter_drops_the_book_effect_and_the_wrapper_keeps_it(self):
        # `V4MboAdapter.apply` binds the ApplyEffect to `_`. It is the only place the book
        # says what a record DID rather than what it said.
        records = [rec(seq=1, order_id=11, ts=1_000)]
        base = drive(V4MboAdapter(), records)[0]
        kept = drive(FullCaptureAdapter(), records)[0]
        self.assertNotIn("book_effect", base["raw_actions"][0])
        self.assertIn("book_effect", kept["raw_actions"][0])

    def test_the_effect_carries_the_touch_as_it_stood_before_the_record(self):
        # `top_before_price_raw` and `removed` had zero readers anywhere in the repo, and the
        # pre-record touch cannot be recovered from a post-group frame.
        records = [rec(seq=1, order_id=11, ts=1_000), rec(seq=2, order_id=12, ts=2_000)]
        kept = drive(FullCaptureAdapter(), records)
        effect = kept[1]["raw_actions"][0]["book_effect"]
        self.assertIn("top_before_price_raw", effect)
        self.assertIn("removed", effect)
        self.assertEqual(effect["top_before_price_raw"], 3_500_000_000)


class BookDepthTests(unittest.TestCase):
    def test_the_base_frame_asserts_a_fifo_reconstruction_it_does_not_carry(self):
        records = [rec(seq=1, order_id=11, ts=1_000)]
        base = drive(V4MboAdapter(), records)[0]
        kept = drive(FullCaptureAdapter(), records)[0]
        self.assertTrue(base["fifo_priority_reconstructed"], "the claim the frame makes")
        self.assertNotIn("fifo_queue", base["book"]["bid_levels"][0], "and does not carry")
        self.assertIn("fifo_queue", kept["book_full"]["bid_levels"][0])
        queue = kept["book_full"]["bid_levels"][0]["fifo_queue"][0]
        for field in ("order_id", "size", "volume_ahead", "priority_recv_ns"):
            self.assertIn(field, queue)

    def test_the_wrapper_carries_the_book_below_the_top_ten_levels(self):
        records = [rec(seq=1, order_id=11, ts=1_000)]
        base = drive(V4MboAdapter(), records)[0]
        kept = drive(FullCaptureAdapter(), records)[0]
        self.assertNotIn("bid_levels_full", base["book"])
        self.assertIn("bid_levels_full", kept["book_full"])


class ActivityWindowTests(unittest.TestCase):
    def test_per_side_counts_and_full_touch_quantities_are_published(self):
        # All three are maintained on every record in five windows and published by none.
        # Quantity is not count: one 500-lot pull and five hundred one-lots are opposite.
        records = [rec(seq=1, order_id=11, ts=1_000)]
        base = drive(V4MboAdapter(), records)[0]
        kept = drive(FullCaptureAdapter(), records)[0]
        one_window = next(iter(base["activity"].values()))
        self.assertNotIn("action_side_count", one_window)
        self.assertNotIn("top_level_qty_by_action", one_window)
        self.assertNotIn("receive_order_clean", one_window)
        extras = next(iter(kept["activity_full"].values()))
        self.assertIn("action_side_count", extras)
        self.assertIn("top_level_qty_by_action", extras)
        self.assertIn("receive_order_clean", extras)


class AnomalyMagnitudeTests(unittest.TestCase):
    """Magnitudes the book knows at the instant and does not keep."""

    def test_a_forward_sequence_gap_is_counted_where_only_regressions_were(self):
        # A forward jump is the standard signature of dropped packets on a CME channel, and
        # so the standard reason to distrust a reconstructed book. It was never computed.
        adapter = FullCaptureAdapter()
        drive(adapter, [rec(seq=1, order_id=11, ts=1_000), rec(seq=9, order_id=12, ts=2_000)])
        self.assertEqual(adapter.capture["sequence_gap"], 1)
        self.assertEqual(adapter.capture["sequence_gap_messages"], 7)

    def test_the_quantity_an_over_cancel_swallows_is_kept(self):
        adapter = FullCaptureAdapter()
        drive(adapter, [
            rec(seq=1, order_id=11, size=5, ts=1_000),
            rec(seq=2, order_id=11, action="C", size=8, ts=2_000),
        ])
        self.assertEqual(adapter.capture["over_cancel"], 1)
        self.assertEqual(adapter.capture["over_cancel_qty"], 3)

    def test_a_clear_records_what_it_destroyed(self):
        adapter = FullCaptureAdapter()
        drive(adapter, [
            rec(seq=1, order_id=11, size=5, ts=1_000),
            rec(seq=2, order_id=12, size=7, ts=2_000),
            rec(seq=3, order_id=0, action="R", side="N", size=0, ts=3_000),
        ])
        self.assertEqual(adapter.capture["book_clear"], 1)
        self.assertEqual(adapter.capture["book_clear_orders_removed"], 2)
        self.assertEqual(adapter.capture["book_clear_qty_removed"], 12)

    def test_a_top_of_book_side_wipe_records_what_it_destroyed(self):
        adapter = FullCaptureAdapter()
        drive(adapter, [
            rec(seq=1, order_id=11, size=5, ts=1_000),
            rec(seq=2, order_id=12, size=7, ts=2_000),
            rec(seq=3, order_id=99, price=UNDEF_PRICE, size=0,
                flags=F_LAST | F_TOB, ts=3_000),
        ])
        self.assertEqual(adapter.capture["tob_side_wipe"], 1)
        self.assertEqual(adapter.capture["tob_side_wipe_orders_removed"], 2)
        self.assertEqual(adapter.capture["tob_side_wipe_qty_removed"], 12)


class IntegrityAttributionTests(unittest.TestCase):
    def test_the_group_that_caused_an_integrity_increment_is_identifiable(self):
        # The cumulative counter says "this has now happened 47 times" and never says where.
        adapter = FullCaptureAdapter()
        frames = drive(adapter, [
            rec(seq=1, order_id=11, ts=1_000),
            rec(seq=2, order_id=404, action="C", ts=2_000),
        ])
        self.assertEqual(frames[0]["integrity_delta"], {})
        self.assertEqual(frames[1]["integrity_delta"], {"cancel_missing_order": 1})
        self.assertEqual(frames[1]["integrity"]["cancel_missing_order"], 1,
                         "the cumulative counter is unchanged, not replaced")


class SubstitutabilityTests(unittest.TestCase):
    def test_it_is_a_drop_in_for_the_locked_adapter(self):
        # `mbo_resume_state` snapshots these by name, so the wrapper must keep them exact.
        records = [rec(seq=1, order_id=11, ts=1_000), rec(seq=2, order_id=12, ts=2_000)]
        base, kept = V4MboAdapter(), FullCaptureAdapter()
        base_frames, kept_frames = drive(base, records), drive(kept, records)
        self.assertEqual(len(base_frames), len(kept_frames))
        self.assertEqual(base.record_count, kept.record_count)
        self.assertEqual(base.completed_event_group_count, kept.completed_event_group_count)
        self.assertEqual(sorted(base.books), sorted(kept.books))
        kept.assert_groups_closed()

    def test_nothing_the_base_frame_carried_was_removed(self):
        records = [rec(seq=1, order_id=11, ts=1_000)]
        base = drive(V4MboAdapter(), records)[0]
        kept = drive(FullCaptureAdapter(), records)[0]
        for key in base:
            self.assertIn(key, kept, f"the wrapper dropped {key} while restoring others")


if __name__ == "__main__":
    unittest.main()
