from collections import Counter
from importlib.util import find_spec
from types import SimpleNamespace
import unittest

HAS_DBN = bool(find_spec("databento") and find_spec("databento_dbn"))
if HAS_DBN:
    from ..verify_absorption_ratio import Window, apply_record, ratio
    from ..verify_retained_root_inputs import RestingBook


def event(action, size, clock, *, order_id=5, price=3059000000, flags=0, side="B"):
    return SimpleNamespace(
        action=SimpleNamespace(value=action), side=SimpleNamespace(value=side),
        order_id=order_id, price=price, size=size, ts_recv=clock, flags=flags, sequence=clock,
    )


@unittest.skipUnless(HAS_DBN, "Databento replay dependencies are unavailable")
class RestingBookTests(unittest.TestCase):
    def test_priority_and_last_update_are_separate(self):
        book = RestingBook()
        book.apply(event("A", 10, 1, flags=32))
        book.apply(event("A", 3, 2, order_id=6))
        book.apply(event("F", 2, 3))
        book.apply(event("C", 2, 4))
        self.assertEqual(list(book.orders), [5, 6])
        self.assertEqual(book.orders[5].priority_recv, 1)
        self.assertEqual(book.orders[5].last_update, 4)
        self.assertTrue(book.orders[5].priority_from_snapshot)
        book.apply(event("M", 12, 5))
        self.assertEqual(list(book.orders), [6, 5])
        self.assertEqual(book.orders[5].priority_recv, 5)
        self.assertFalse(book.orders[5].priority_from_snapshot)

    def test_unreconciled_cancel_fails_closed(self):
        book = RestingBook()
        book.apply(event("A", 2, 1))
        with self.assertRaises(ValueError):
            book.apply(event("C", 3, 2))
        self.assertEqual(book.orders[5].size, 2)

    def test_refresh_fills_survive_zero_display_change(self):
        book = RestingBook()
        book.apply(event("A", 1, 1))
        counts, pending = Counter(), Counter()
        apply_record(book, event("F", 3, 2), pending, counts)
        apply_record(book, event("M", 1, 3), pending, counts)
        self.assertEqual(counts["linked_fill", "B"], 3)
        self.assertEqual(counts["reduction", "B"], 0)
        self.assertEqual(counts["linked_fill_unchanged_display", "B"], 3)
        self.assertIsNone(ratio(3, 0))
        self.assertEqual(ratio(53, 5), 10.6)

    def test_rolling_window_drops_only_expired_groups(self):
        window = Window(2)
        window.add(Counter(fills=7, reduction=2))
        window.add(Counter(fills=1, reduction=1))
        window.add(Counter(fills=4))
        self.assertEqual(window.totals, Counter(fills=5, reduction=1))

    def test_fill_side_requires_resting_id_and_price(self):
        book = RestingBook()
        book.apply(event("A", 1, 1))
        counts, pending = Counter(), Counter()
        apply_record(book, event("F", 2, 2, side="N"), pending, counts)
        apply_record(book, event("F", 4, 3, side="N", price=3058000000), pending, counts)
        apply_record(book, event("M", 1, 4), pending, counts)
        self.assertEqual(counts["wire_fill", "N"], 6)
        self.assertEqual(counts["unresolved_fill", "N"], 4)
        self.assertEqual(counts["fill_side_from_book", "B"], 2)
        self.assertEqual(counts["linked_fill", "B"], 2)
        self.assertEqual(counts["legacy_linked_fill", "B"], 6)
