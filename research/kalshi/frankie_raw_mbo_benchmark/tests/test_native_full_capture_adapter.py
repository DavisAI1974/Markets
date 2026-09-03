"""Tests for the full-capture adapter (D60).

Each test is a DIFFERENTIAL against the hash-locked `V4MboAdapter`: it drives both with the
same records and asserts the base adapter drops something the wrapper keeps. Written that way
on purpose - asserting only that the wrapper HAS a field would still pass if the base adapter
had it all along, and the claim being made is specifically that this data was being lost.
"""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark import native_full_capture_adapter
from research.kalshi.frankie_raw_mbo_benchmark import native_session
from research.kalshi.frankie_raw_mbo_benchmark.native_full_capture_adapter import (
    ACTIVITY_ANCHORS,
    ANCHOR_BASIS_EXCHANGE_CALENDAR,
    ANCHOR_BASIS_NOT_YET_OBSERVED,
    ANCHOR_BASIS_OBSERVED,
    ANCHOR_BASIS_UNKNOWN_SINCE_RESUME,
    RETIRED_FIXED_INTERVAL_FRAME_KEYS,
    FullCaptureAdapter,
)
from research.kalshi.frankie_raw_mbo_benchmark.mbo_resume_state import (
    export_adapter_state,
    restore_adapter_state,
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
        # S122 (b): the three extras ride on every EVENT-ANCHORED window (`activity_since`)
        # where they rode on every fixed window (`activity_full`) before D83.
        records = [rec(seq=1, order_id=11, ts=1_000)]
        base = drive(V4MboAdapter(), records)[0]
        kept = drive(FullCaptureAdapter(), records)[0]
        one_window = next(iter(base["activity"].values()))
        self.assertNotIn("action_side_count", one_window)
        self.assertNotIn("top_level_qty_by_action", one_window)
        self.assertNotIn("receive_order_clean", one_window)
        for anchor, window in kept["activity_since"].items():
            with self.subTest(anchor=anchor):
                self.assertIn("action_side_count", window)
                self.assertIn("top_level_qty_by_action", window)
                self.assertIn("receive_order_clean", window)


NS = 1_000_000_000
MONDAY_OPEN = native_session.session_open_ns(__import__("datetime").date(2021, 10, 4))
"""The Sunday 17:00 CT reopen that starts the Monday 2021-10-04 trade date."""


def trec(*, seq, ts, side="B", size=1, order_id=None, last=True, price=3_500_000_000):
    """A trade record. Its own order id so the book never resolves it to a resting order."""
    return rec(seq=seq, order_id=order_id if order_id is not None else 90_000 + seq,
               action="T", side=side, size=size, price=price, ts=ts, last=last)


class ActivitySinceEventAnchorsTests(unittest.TestCase):
    """S122 slice (b), D83: activity is measured from EVENT anchors on named clocks, and the
    fixed-seconds `activity` / `activity_full` blocks leave the published frame. The removal
    is Greg's own instruction (the discussion D60 requires); nothing raw leaves, and the
    locked adapter keeps computing its windows internally, unedited (D61)."""

    TWELVE = (
        "event_count", "action_count", "action_qty", "action_side_qty",
        "trade_buy_aggressor_qty", "trade_sell_aggressor_qty", "trade_aggressor_imbalance",
        "add_cancel_churn", "top_level_add_qty_derived", "top_level_cancel_qty_derived",
        "priority_lost_modify_count", "missing_reference_count",
    )
    THREE = ("action_side_count", "top_level_qty_by_action", "receive_order_clean")
    ANCHOR_FIELDS = (
        "anchor_recv_ns", "anchor_event_ns", "anchor_sequence", "elapsed_recv_ns",
        "elapsed_event_ns", "groups_since_anchor", "records_since_anchor", "anchor_basis",
    )

    def test_the_base_frame_carries_the_fixed_windows_and_the_wrapper_frame_does_not(self):
        """The differential the whole file is written as: the LOCKED adapter still emits
        `activity` (its windows are its own), the wrapper's published frame does not."""
        records = [rec(seq=1, order_id=11, ts=MONDAY_OPEN + NS)]
        base = drive(V4MboAdapter(), records)[0]
        kept = drive(FullCaptureAdapter(), records)[0]
        self.assertIn("activity", base)
        for retired in RETIRED_FIXED_INTERVAL_FRAME_KEYS:
            with self.subTest(retired=retired):
                self.assertNotIn(retired, kept)
        self.assertEqual(RETIRED_FIXED_INTERVAL_FRAME_KEYS, ("activity", "activity_full"))
        self.assertEqual(tuple(kept["activity_since"]), ACTIVITY_ANCHORS)
        self.assertEqual(
            ACTIVITY_ANCHORS,
            ("last_trade", "last_touch_change", "last_book_reset", "session_open",
             "last_f_last_same_side"),
        )

    def test_every_anchored_window_carries_the_twelve_the_three_and_its_anchor(self):
        """Nothing in the VOCABULARY is lost - only the fixed spans. The twelve are read off
        the locked adapter's own snapshot so a rename there fails here."""
        records = [rec(seq=1, order_id=11, ts=MONDAY_OPEN + NS)]
        base = drive(V4MboAdapter(), records)[0]
        kept = drive(FullCaptureAdapter(), records)[0]
        base_keys = set(next(iter(base["activity"].values())))
        self.assertEqual(base_keys, set(self.TWELVE))
        for anchor, window in kept["activity_since"].items():
            with self.subTest(anchor=anchor):
                self.assertTrue(base_keys <= set(window), base_keys - set(window))
                self.assertTrue(set(self.THREE) <= set(window))
                self.assertTrue(set(self.ANCHOR_FIELDS) <= set(window))
                self.assertNotIn("seconds", window)
                self.assertNotIn("window_s", window)

    def test_last_trade_resets_on_a_trade_and_measures_from_it_on_both_clocks(self):
        t0 = MONDAY_OPEN + 10 * NS
        adapter = FullCaptureAdapter()
        frames = drive(adapter, [
            rec(seq=1, order_id=11, ts=t0),                       # group 0: an add, no trade yet
            trec(seq=2, ts=t0 + 5 * NS, side="A", size=7),        # group 1: the anchor trade
            rec(seq=3, order_id=12, ts=t0 + 8 * NS),              # group 2: an add after it
            rec(seq=4, order_id=13, ts=t0 + 9 * NS),              # group 3
        ])
        before = frames[0]["activity_since"]["last_trade"]
        self.assertEqual(before["anchor_basis"], ANCHOR_BASIS_NOT_YET_OBSERVED)
        self.assertIsNone(before["anchor_recv_ns"])
        self.assertEqual(before["records_since_anchor"], 1)
        at_trade = frames[1]["activity_since"]["last_trade"]
        # EXCLUSIVE of the anchor record: the trade itself is the anchor, not activity since.
        self.assertEqual(at_trade["anchor_basis"], ANCHOR_BASIS_OBSERVED)
        self.assertEqual(at_trade["anchor_recv_ns"], t0 + 5 * NS + 150_000)
        self.assertEqual(at_trade["anchor_event_ns"], t0 + 5 * NS)
        self.assertEqual(at_trade["anchor_sequence"], 2)
        self.assertEqual(at_trade["event_count"], 0)
        self.assertEqual(at_trade["records_since_anchor"], 0)
        self.assertEqual(at_trade["elapsed_recv_ns"], 0)
        after = frames[3]["activity_since"]["last_trade"]
        self.assertEqual(after["anchor_sequence"], 2)
        self.assertEqual(after["event_count"], 2)
        self.assertEqual(after["records_since_anchor"], 2)
        self.assertEqual(after["groups_since_anchor"], 2)
        self.assertEqual(after["elapsed_recv_ns"], 4 * NS)
        self.assertEqual(after["elapsed_event_ns"], 4 * NS)
        self.assertEqual(after["action_count"], {"A": 2})

    def test_last_touch_change_resets_when_the_best_price_moves_not_when_depth_joins_behind(self):
        t0 = MONDAY_OPEN + 10 * NS
        frames = drive(FullCaptureAdapter(), [
            rec(seq=1, order_id=11, ts=t0, price=3_499_000_000),            # first bid: touch born
            rec(seq=2, order_id=12, ts=t0 + NS, price=3_498_000_000),       # behind it: no change
            rec(seq=3, order_id=13, ts=t0 + 2 * NS, price=3_499_000_000),   # joins the touch: no change
            rec(seq=4, order_id=14, ts=t0 + 3 * NS, price=3_500_000_000),   # improves: change
            rec(seq=5, order_id=15, ts=t0 + 4 * NS, price=3_497_000_000),   # behind: no change
        ])
        touch = [f["activity_since"]["last_touch_change"] for f in frames]
        self.assertEqual(touch[0]["anchor_sequence"], 1)
        self.assertEqual(touch[1]["anchor_sequence"], 1)
        self.assertEqual(touch[2]["anchor_sequence"], 1)
        self.assertEqual(touch[2]["records_since_anchor"], 2)
        self.assertEqual(touch[3]["anchor_sequence"], 4)
        self.assertEqual(touch[3]["records_since_anchor"], 0)
        self.assertEqual(touch[4]["anchor_sequence"], 4)
        self.assertEqual(touch[4]["records_since_anchor"], 1)
        self.assertEqual(touch[4]["elapsed_recv_ns"], NS)

    def test_last_book_reset_resets_on_a_clear_and_a_snapshot_flagged_record(self):
        from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import F_SNAPSHOT
        t0 = MONDAY_OPEN + 10 * NS
        frames = drive(FullCaptureAdapter(), [
            rec(seq=1, order_id=11, ts=t0),
            rec(seq=2, order_id=0, action="R", side="N", size=0, price=0, ts=t0 + NS),
            rec(seq=3, order_id=12, ts=t0 + 2 * NS),
            rec(seq=4, order_id=13, ts=t0 + 3 * NS, flags=F_LAST | F_SNAPSHOT),
            rec(seq=5, order_id=14, ts=t0 + 4 * NS),
        ])
        reset = [f["activity_since"]["last_book_reset"] for f in frames]
        self.assertEqual(reset[0]["anchor_basis"], ANCHOR_BASIS_NOT_YET_OBSERVED)
        self.assertEqual(reset[1]["anchor_sequence"], 2)
        self.assertEqual(reset[1]["anchor_basis"], ANCHOR_BASIS_OBSERVED)
        self.assertEqual(reset[2]["anchor_sequence"], 2)
        self.assertEqual(reset[2]["records_since_anchor"], 1)
        self.assertEqual(reset[3]["anchor_sequence"], 4)
        self.assertEqual(reset[4]["anchor_sequence"], 4)
        self.assertEqual(reset[4]["records_since_anchor"], 1)

    def test_session_open_anchors_at_the_exchange_reopen_inclusively(self):
        t0 = MONDAY_OPEN + 60 * NS
        frames = drive(FullCaptureAdapter(), [
            rec(seq=1, order_id=11, ts=t0),
            rec(seq=2, order_id=12, ts=t0 + NS),
        ])
        first = frames[0]["activity_since"]["session_open"]
        self.assertEqual(first["anchor_basis"], ANCHOR_BASIS_EXCHANGE_CALENDAR)
        self.assertEqual(first["anchor_event_ns"], MONDAY_OPEN)
        self.assertIsNone(first["anchor_recv_ns"])
        self.assertIsNone(first["elapsed_recv_ns"])
        self.assertEqual(first["elapsed_event_ns"], 60 * NS)
        # INCLUSIVE of everything at or after the reopen: the first record counts.
        self.assertEqual(first["records_since_anchor"], 1)
        self.assertEqual(first["event_count"], 1)
        second = frames[1]["activity_since"]["session_open"]
        self.assertEqual(second["records_since_anchor"], 2)
        self.assertEqual(second["groups_since_anchor"], 2)

    def test_session_open_rolls_when_a_record_crosses_the_next_reopen(self):
        import datetime
        tuesday_open = native_session.session_open_ns(datetime.date(2021, 10, 5))
        frames = drive(FullCaptureAdapter(), [
            rec(seq=1, order_id=11, ts=MONDAY_OPEN + 60 * NS),
            rec(seq=2, order_id=12, ts=tuesday_open + 5 * NS),
        ])
        rolled = frames[1]["activity_since"]["session_open"]
        self.assertEqual(rolled["anchor_event_ns"], tuesday_open)
        self.assertEqual(rolled["records_since_anchor"], 1)
        self.assertEqual(rolled["elapsed_event_ns"], 5 * NS)

    def test_last_f_last_same_side_is_measured_per_side_and_excludes_the_anchor_group(self):
        t0 = MONDAY_OPEN + 10 * NS
        frames = drive(FullCaptureAdapter(), [
            rec(seq=1, order_id=11, side="B", ts=t0),                 # B group 0 (no B before)
            rec(seq=2, order_id=12, side="A", ts=t0 + NS),            # A group 1 (no A before)
            rec(seq=3, order_id=13, side="B", ts=t0 + 2 * NS, last=False),
            rec(seq=4, order_id=14, side="B", ts=t0 + 3 * NS),        # B group 2: since group 0
            rec(seq=5, order_id=15, side="A", ts=t0 + 4 * NS),        # A group 3: since group 1
        ])
        same = [f["activity_since"]["last_f_last_same_side"] for f in frames]
        self.assertEqual(same[0]["anchor_basis"], ANCHOR_BASIS_NOT_YET_OBSERVED)
        self.assertEqual(same[0]["side_orientation"], "B")
        self.assertEqual(same[1]["anchor_basis"], ANCHOR_BASIS_NOT_YET_OBSERVED)
        self.assertEqual(same[1]["side_orientation"], "A")
        b2 = same[2]
        self.assertEqual(b2["side_orientation"], "B")
        self.assertEqual(b2["anchor_basis"], ANCHOR_BASIS_OBSERVED)
        self.assertEqual(b2["anchor_sequence"], 1)       # the previous B group's F_LAST
        self.assertEqual(b2["records_since_anchor"], 3)  # seq 2 (the A group), 3, 4
        self.assertEqual(b2["groups_since_anchor"], 2)   # group 1 (A) and this group
        self.assertEqual(b2["action_side_count"], {"A_A": 1, "A_B": 2})
        a3 = same[3]
        self.assertEqual(a3["side_orientation"], "A")
        self.assertEqual(a3["anchor_sequence"], 2)
        self.assertEqual(a3["records_since_anchor"], 3)
        self.assertEqual(a3["groups_since_anchor"], 2)

    def test_a_resumed_adapter_declares_what_it_does_not_know_and_keeps_the_calendar_exact(self):
        """The honest resume form: the four record anchors are UNKNOWN_SINCE_RESUME with
        accumulation from the resume instant; `session_open` is a calendar fact and exact."""
        t0 = MONDAY_OPEN + 10 * NS
        first = FullCaptureAdapter()
        drive(first, [trec(seq=1, ts=t0), rec(seq=2, order_id=11, ts=t0 + NS)])
        restored = restore_adapter_state(export_adapter_state(first))
        resumed = FullCaptureAdapter.from_restored(restored)
        frame = drive(resumed, [rec(seq=3, order_id=12, ts=t0 + 2 * NS)])[0]
        since = frame["activity_since"]
        for anchor in ("last_trade", "last_touch_change", "last_book_reset", "last_f_last_same_side"):
            with self.subTest(anchor=anchor):
                self.assertEqual(since[anchor]["anchor_basis"], ANCHOR_BASIS_UNKNOWN_SINCE_RESUME)
                self.assertIsNone(since[anchor]["anchor_recv_ns"])
                self.assertEqual(since[anchor]["records_since_anchor"], 1)
        self.assertEqual(since["session_open"]["anchor_basis"], ANCHOR_BASIS_EXCHANGE_CALENDAR)
        self.assertEqual(since["session_open"]["anchor_event_ns"], MONDAY_OPEN)

    def test_the_wrapper_code_references_no_fixed_window_constant(self):
        """The prose may NAME the retired constant (it records why); the code may not
        reference it - no import, no attribute, no expression."""
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(native_full_capture_adapter))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        imported = {
            alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        self.assertNotIn("ACTIVITY_WINDOWS_S", names)
        self.assertNotIn("ACTIVITY_WINDOWS_S", imported)
        self.assertFalse(hasattr(native_full_capture_adapter, "ACTIVITY_WINDOWS_S"))


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

    def test_nothing_the_base_frame_carried_was_removed_except_the_named_retired_keys(self):
        """Re-baselined honestly at S122 (b): every base key is carried EXCEPT the fixed-
        interval `activity` block, which is named in RETIRED_FIXED_INTERVAL_FRAME_KEYS and
        removed on Greg's instruction (D83); its vocabulary rides on `activity_since`."""
        records = [rec(seq=1, order_id=11, ts=1_000)]
        base = drive(V4MboAdapter(), records)[0]
        kept = drive(FullCaptureAdapter(), records)[0]
        for key in base:
            if key in RETIRED_FIXED_INTERVAL_FRAME_KEYS:
                self.assertNotIn(key, kept, f"{key} is retired and must not be published")
                continue
            self.assertIn(key, kept, f"the wrapper dropped {key} while restoring others")


if __name__ == "__main__":
    unittest.main()
