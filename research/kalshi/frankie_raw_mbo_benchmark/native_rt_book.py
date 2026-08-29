"""A FIFO order book advanced one action at a time, so every read is the REAL-TIME view.

Greg, 2026-08-29: *"We should see it like it would be seen in rt."*

**The problem this exists for.** `InstrumentBook`
(`research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`) mutates on EVERY record, while the
group frame carrying `raw_actions` is only returned at F_LAST. So by the time a closed group
reaches an adapter, that book already reflects the group's OWN later actions. Reading a level
there reports it as it stood AFTER the add the level is meant to describe - an intra-group
lookahead that is present, typed, in range and wrong. Section 4.6 needs `orders_ahead` at the
instant an order rested, not at the instant its group closed, and the difference is the whole
measurement.

**The rule that governs every line below: MIRROR `InstrumentBook` ON EVERY BOOK MUTATION.**
This is a second book over the same tape, and two books that disagree about one fact do not
fail - the numbers simply differ. That is the `_family_id` defect of 2026-08-29 and the
S108/S109 shape, and re-introducing it here while claiming to prevent it would be the worst
possible trade. So each mutating branch is a transcription of the `InstrumentBook` method
named above it, including the parts that look surprising:

* **`F`, `T` and `N` mutate NOTHING.** In this feed a fill is not a book event; the venue's
  subsequent `C` or `M` is what removes the liquidity (`_book_effect`).
* **`C` decrements by the ROW's size** and removes only at zero. A partial cancel never
  re-queues, because `_cancel` does not call `_remove_from_level` on a survivor.
* **`M`** loses priority when `old_price != price_raw or size > old_size`, and then goes to the
  BACK of the (possibly new) level; otherwise the size updates in place and the queue position
  is kept. Size reaching zero removes it. A modify for an order that is not resting is treated
  as an ADD - Databento's reference LOB does this and `_modify` counts it as
  `modify_missing_treated_as_add` - which matters because a replay window opening mid-stream
  sees these constantly.
* **`R` clears both sides.**

**The one deliberate divergence, and it is about INPUT, never about a mutation.**
`InstrumentBook` writes `max(0, msg.size)`, which turns a malformed row into a silent zero.
This refuses instead, following `native_group_adapters._size`. So this book is stricter than
`InstrumentBook` about what it will accept, and identical to it about what it does with
anything both accept - which is the only shape of divergence that cannot put the two books
into disagreement about a real row.

**No averaging, no derived statistics.** This answers questions about the book's exact state;
counts and sizes are integers throughout. Nothing here is a rate, a mean or a ratio.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from research.kalshi.frankie_raw_mbo_benchmark.native_group_adapters import PRICE_SENTINEL_ABS

__all__ = ["ReplayBook", "RtBookError", "PRICE_SENTINEL_ABS"]

ADD = "A"
CANCEL = "C"
MODIFY = "M"
RESET = "R"
FILL = "F"
TRADE = "T"
NONE = "N"

VALID_ACTIONS = frozenset("ACMRTFN")
"""The feed's own vocabulary, from `InstrumentBook.VALID_ACTIONS`."""

NON_MUTATING_ACTIONS = frozenset({FILL, TRADE, NONE})
"""Actions that carry information but leave the book untouched. See the module docstring."""

BID, ASK = "B", "A"
BOOK_SIDES = (BID, ASK)


class RtBookError(ValueError):
    """A raw action row could not be applied to the replay book."""


@dataclass
class _Resting:
    """One resting order. Mutable, because a modify updates it in place when priority holds."""

    side: str
    price_raw: int
    size: int


class ReplayBook:
    """One instrument's resting-order book, advanced by `apply` one row at a time.

    Every accessor answers for the state as of the rows applied SO FAR and nothing later,
    which is the property `test_no_reading_depends_on_a_row_later_in_the_sequence` asserts
    executably rather than by comment.
    """

    def __init__(self) -> None:
        # Per instance, never class attributes: a shared mutable default would pool two
        # instruments into one book, which reads downstream as depth rather than as an error.
        self._orders: dict[int, _Resting] = {}
        self._levels: dict[str, dict[int, list[int]]] = {BID: {}, ASK: {}}

    # --- reads ------------------------------------------------------------

    def is_resting(self, order_id: int) -> bool:
        return int(order_id) in self._orders

    def resting_at(self, order_id: int) -> tuple[str, int, int] | None:
        """`(side, price_raw, size)` for a resting order, or None if it is not resting."""
        order = self._orders.get(int(order_id))
        if order is None:
            return None
        return (order.side, order.price_raw, order.size)

    def level(self, side: str, price_raw: int) -> tuple[int, int]:
        """`(order_count, total_volume)` resting at one level."""
        ids = self._level_ids(side, price_raw)
        return (len(ids), sum(self._orders[oid].size for oid in ids))

    def view(self, side: str, price_raw: int, order_id: int) -> tuple[int, int]:
        """`(orders_ahead, volume_ahead)` strictly ahead of `order_id`, in FIFO order.

        This is `native_queue.BookView`. An order id absent from the level reports the WHOLE
        level as ahead, matching `test_native_queue.FakeBook.view`: the conservative answer
        for an order we cannot locate is that all of the level is ahead of it, never none.
        """
        target = int(order_id)
        orders_ahead = 0
        volume_ahead = 0
        for oid in self._level_ids(side, price_raw):
            if oid == target:
                break
            orders_ahead += 1
            volume_ahead += self._orders[oid].size
        return (orders_ahead, volume_ahead)

    def touch_price(self, side: str) -> int | None:
        """Best price on one side: the MAXIMUM on the bid, the MINIMUM on the ask.

        Taking the same extreme on both sides would read as a plausible price while being the
        FAR touch on one of them. `InstrumentBook.best_price_raw` splits them for this reason.
        """
        prices = [price for price, ids in self._levels.get(side, {}).items() if ids]
        if not prices:
            return None
        return max(prices) if side == BID else min(prices)

    # --- the one mutator --------------------------------------------------

    def apply(self, row: Mapping[str, Any]) -> None:
        """Advance the book by exactly one raw action row."""
        action = str(row.get("action", "?"))
        if action not in VALID_ACTIONS:
            raise RtBookError(
                f"unsupported action {action!r}; the feed's vocabulary is {sorted(VALID_ACTIONS)}"
            )
        size = self._size(row)

        if action in NON_MUTATING_ACTIONS:
            return
        if action == RESET:
            self._orders.clear()
            self._levels = {BID: {}, ASK: {}}
            return
        if action == ADD:
            self._add(row, size)
            return
        if action == CANCEL:
            self._cancel(row, size)
            return
        self._modify(row, size)

    # --- mutating branches, each a transcription of its InstrumentBook method ---

    def _add(self, row: Mapping[str, Any], size: int) -> None:
        """`InstrumentBook._add_order`, plus a refusal it does not make."""
        order_id = int(row.get("order_id") or 0)
        if order_id and order_id in self._orders:
            # InstrumentBook tolerates this: it counts `duplicate_add_order_id` and rests the
            # new order in place of the old. It can afford to, because its job is to survive a
            # whole day's tape. This book's job is to answer `view` for ONE NAMED order, and
            # after a silent replacement that answer is a different order's queue position
            # under the same id - present, typed and wrong. So it refuses and lets the caller
            # decide what a duplicate means.
            raise RtBookError(f"order {order_id} is already resting; a duplicate add would fork it")
        side, price = self._admit(row)
        if side is None or price is None or not order_id:
            return
        self._rest(order_id, side, price, size)

    def _cancel(self, row: Mapping[str, Any], size: int) -> None:
        """`InstrumentBook._cancel`: decrement by the ROW's size, remove only at zero.

        Side and price are taken from the RESTING order, never from the row: the row is the
        instruction, the book is the fact. An unknown order id mutates nothing - a group is a
        SLICE of the day, so a cancel of an order that rested before the window opened is
        structural, not malformed, and raising would make this book unusable anywhere but the
        session's first record.
        """
        order = self._orders.get(int(row.get("order_id") or 0))
        if order is None:
            return
        order.size = max(0, order.size - size)
        if order.size == 0:
            self._remove(int(row.get("order_id") or 0))

    def _modify(self, row: Mapping[str, Any], size: int) -> None:
        """`InstrumentBook._modify`, branch for branch."""
        order_id = int(row.get("order_id") or 0)
        if not order_id:
            return
        order = self._orders.get(order_id)
        side, price = self._admit(row)

        if order is None:
            # Databento's reference LOB treats a missing modify as an add, and `_modify`
            # records the anomaly as `modify_missing_treated_as_add` rather than dropping it.
            if side is None or price is None:
                return
            self._rest(order_id, side, price, size)
            return

        if side is not None and side != order.side:
            self._remove(order_id)
            if price is not None:
                self._rest(order_id, side, price, size)
            return

        if price is None:
            return
        priority_lost = order.price_raw != price or size > order.size
        if priority_lost:
            self._detach(order_id, order)
            order.price_raw = price
            order.size = size
            self._levels[order.side].setdefault(price, []).append(order_id)
        else:
            order.size = size
        if order.size == 0:
            self._remove(order_id)

    # --- helpers ----------------------------------------------------------

    def _size(self, row: Mapping[str, Any]) -> int:
        """A size is a quantity, so a negative one is refused rather than clamped.

        THE ONE DELIBERATE DIVERGENCE from `InstrumentBook`, which writes `max(0, size)`.
        Clamping turns a malformed row into a silent zero. Refusing keeps this book stricter
        on INPUT while identical on every mutation, so the two can never disagree about a row
        that both accepted. Follows `native_group_adapters._size`.
        """
        value = row.get("size")
        size = 0 if value is None else int(value)
        if size < 0:
            raise RtBookError(f"negative size {size} in a raw action row")
        return size

    @staticmethod
    def _admit(row: Mapping[str, Any]) -> tuple[str | None, int | None]:
        """The side and price a row may enter the book at, or None where it may not.

        An undefined price is not a level, and Databento's `N` is the tape DECLINING to state
        a side - assigning it to one would fabricate the very fact that is missing, which is
        the rule `ladder_transitions` already applies.
        """
        side = str(row.get("side", NONE))
        if side not in BOOK_SIDES:
            return (None, None)
        value = row.get("price_raw")
        if value is None:
            return (side, None)
        price = int(value)
        if abs(price) >= PRICE_SENTINEL_ABS:
            return (side, None)
        return (side, price)

    def _level_ids(self, side: str, price_raw: int) -> list[int]:
        return self._levels.get(side, {}).get(int(price_raw), [])

    def _rest(self, order_id: int, side: str, price: int, size: int) -> None:
        self._orders[order_id] = _Resting(side=side, price_raw=price, size=size)
        self._levels[side].setdefault(price, []).append(order_id)

    def _detach(self, order_id: int, order: _Resting) -> None:
        """Take an order off its level, dropping the level when it empties.

        An emptied level must not linger: `touch_price` reads the level map, and a price whose
        queue is empty would answer as a touch that no longer exists.
        """
        ids = self._levels.get(order.side, {}).get(order.price_raw)
        if not ids:
            return
        if order_id in ids:
            ids.remove(order_id)
        if not ids:
            self._levels[order.side].pop(order.price_raw, None)

    def _remove(self, order_id: int) -> None:
        order = self._orders.pop(order_id, None)
        if order is not None:
            self._detach(order_id, order)
