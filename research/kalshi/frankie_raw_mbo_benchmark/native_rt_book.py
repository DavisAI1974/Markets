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
S108/S109 shape. Each mutating branch is a transcription of the `InstrumentBook` method named
above it, including the parts that look surprising:

* **`F`, `T` and `N` mutate NOTHING.** In this feed a fill is not a book event; the venue's
  subsequent `C` or `M` is what removes the liquidity (`_book_effect`).
* **`C` decrements by the ROW's size** and removes only at zero. A partial cancel never
  re-queues, because `_cancel` does not call `_remove_from_level` on a survivor.
* **`M`** loses priority when `old_price != price_raw or size > old_size`, and then goes to the
  BACK of the (possibly new) level; otherwise the size updates in place and the queue position
  is kept. Size reaching zero removes it. A modify for an order that is not resting is treated
  as an ADD - `_modify` counts it as `modify_missing_treated_as_add` - which matters because a
  replay window opening mid-stream sees these constantly.
* **`R` clears both sides.**

**RETAIN EVERYTHING, AND MIRROR EVEN WHERE THE OTHER BOOK LOOKS WRONG.** Greg, 2026-08-29:
*"do not leave any of the book data out. it may not seem relevant to you but it may to
frankie."* An earlier draft of this module DROPPED rows it thought were nonsense - a sentinel
price, an order id of zero, an add with no side. A differential harness against
`InstrumentBook` (163,481 well-formed records, zero divergence; a malformed-row fuzz, three
root causes) showed every divergence it had came from exactly that, and each one moved a `view`
number with nothing failing. Dropping a row the other book ACTS on is the defect this module
exists to prevent, wearing the costume of a safety check. Two things follow, and they are the
same rule:

* **The state mirrors `InstrumentBook` even where mirroring looks wrong.** A sentinel-priced
  add RESTS at the sentinel level and is then reported as the touch, exactly as
  `best_price_raw` reports it. The `F_TOB` sentinel add WIPES its whole side. An `order_id` of
  zero - which `normalize` produces from a missing or unparseable field - rests as a real
  order, because `_add_order` rests it and a level one order short is a wrong `orders_ahead`.
  A duplicate add REPLACES, as `_add_order` does. None of these are this module's call to
  overrule: it is a second book over one tape, and the moment it decides it knows better, the
  two disagree with nothing failing.
* **Nothing observed is discarded - it is COUNTED.** `integrity` carries `InstrumentBook`'s own
  counter names where they correspond, plus the events it does not count, so a row that changes
  no state still leaves a trace: an unsided add, a cancel for an order that never rested, the
  quantity lost when a cancel exceeds the resting size, a modify that became an add, a
  sentinel rest, an order id of zero, a top-of-book side wipe, and every non-mutating `F`/`T`/
  `N`. Counters rather than a per-row log deliberately: the log is already the input
  (`raw_actions`), and an unbounded list over 4.26M groups is a memory failure, not a record.

**The ONLY divergence, and it is about malformed INPUT rather than about a mutation.**
`InstrumentBook` writes `max(0, msg.size)`, which turns a malformed row into a silent zero.
This refuses, following `native_group_adapters._size`. Size is validated only on the actions
that USE it, so a stray value on a row this book ignores cannot abort a replay that
`InstrumentBook` would have survived. A modify whose side is neither `B` nor `A` also stops,
because `_modify` calls `_add_order` with no side check and dies on `levels["N"]` - the two
books abort together rather than one carrying on with a different book.

**The caveat travels on the value.** `view` returns the bare pair `native_queue.BookView`
requires, but `(0, 0)` means both "at the front of the queue" and "not found here", and a
caller cannot tell a genuine touch-front order from a lookup that failed. `view_with_basis`
returns the same pair plus the basis that produced it, on the `cancels_ahead_basis` and
`ladder_scope` precedent: a caveat that lives only in prose expires.

**No averaging, no derived statistics.** Counts and sizes are integers throughout. Nothing here
is a rate, a mean or a ratio.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping

from research.kalshi.frankie_raw_mbo_benchmark.native_group_adapters import PRICE_SENTINEL_ABS
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import F_TOB

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

MUTATING_ACTIONS = frozenset({ADD, CANCEL, MODIFY})
"""Actions that can change the book, and so must be able to name their order."""

BID, ASK = "B", "A"
BOOK_SIDES = (BID, ASK)

AT_POSITION = "AT_POSITION"
ABSENT_FROM_POPULATED_LEVEL = "ABSENT_FROM_POPULATED_LEVEL"
EMPTY_LEVEL = "EMPTY_LEVEL"
"""What produced a `view` reading. Travels with the value; see the module docstring."""


class RtBookError(ValueError):
    """A raw action row could not be applied to, or read from, the replay book."""


@dataclass
class _Resting:
    """One resting order. Mutable, because a modify updates it in place when priority holds."""

    side: str
    price_raw: int
    size: int


class ReplayBook:
    """One instrument's resting-order book, advanced by `apply` one row at a time.

    Every accessor answers for the rows applied SO FAR and nothing later.
    """

    def __init__(self) -> None:
        # Per instance, never class attributes: a shared mutable default would pool two
        # instruments into one book, which reads downstream as depth rather than as an error.
        self._orders: dict[int, _Resting] = {}
        self._levels: dict[str, dict[int, list[int]]] = {BID: {}, ASK: {}}
        self.integrity: Counter[str] = Counter()
        """Everything observed that changed no state, or changed it anomalously.

        Nothing this book sees is discarded. Names match `InstrumentBook.integrity` where the
        two count the same event, so the counters can be reconciled rather than compared.
        """

    # --- reads ------------------------------------------------------------

    def is_resting(self, order_id: int) -> bool:
        return self._as_int(order_id, "order_id") in self._orders

    def resting_at(self, order_id: int) -> tuple[str, int, int] | None:
        """`(side, price_raw, size)` for a resting order, or None if it is not resting."""
        order = self._orders.get(self._as_int(order_id, "order_id"))
        if order is None:
            return None
        return (order.side, order.price_raw, order.size)

    def level(self, side: str, price_raw: int) -> tuple[int, int]:
        """`(order_count, total_volume)` resting at one level."""
        ids = self._level_ids(side, price_raw)
        return (len(ids), sum(self._orders[oid].size for oid in ids))

    def view(self, side: str, price_raw: int, order_id: int) -> tuple[int, int]:
        """`(orders_ahead, volume_ahead)` strictly ahead of `order_id`, in FIFO order.

        This is the `native_queue.BookView` contract, which is why the return is the bare pair.
        Use `view_with_basis` when the caller needs to know WHICH of the three readings it got:
        `(0, 0)` is both "at the front" and "this level is empty".
        """
        orders_ahead, volume_ahead, _basis = self.view_with_basis(side, price_raw, order_id)
        return (orders_ahead, volume_ahead)

    def view_with_basis(self, side: str, price_raw: int, order_id: int) -> tuple[int, int, str]:
        """`view`, plus the basis that produced it.

        An order id absent from a POPULATED level reports the whole level as ahead, matching
        `test_native_queue.FakeBook.view`: the conservative answer for an order we cannot
        locate is that all of the level is ahead of it, never none of it.
        """
        target = self._as_int(order_id, "order_id")
        ids = self._level_ids(side, price_raw)
        if not ids:
            return (0, 0, EMPTY_LEVEL)
        orders_ahead = 0
        volume_ahead = 0
        for oid in ids:
            if oid == target:
                return (orders_ahead, volume_ahead, AT_POSITION)
            orders_ahead += 1
            volume_ahead += self._orders[oid].size
        return (orders_ahead, volume_ahead, ABSENT_FROM_POPULATED_LEVEL)

    def touch_price(self, side: str) -> int | None:
        """Best price on one side: the MAXIMUM on the bid, the MINIMUM on the ask.

        Taking the same extreme on both sides would read as a plausible price while being the
        FAR touch on one of them. `InstrumentBook.best_price_raw` splits them for this reason,
        and this mirrors it - including reporting a sentinel-priced rest as the touch.
        """
        self._require_side(side)
        prices = [price for price, ids in self._levels[side].items() if ids]
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
        if action in NON_MUTATING_ACTIONS:
            # These change no state in this feed, but they are not nothing: a fill is the
            # event 4.8 measures. Counted so the replay can account for every row it saw.
            self.integrity[f"non_mutating_{action}"] += 1
            return
        if action == RESET:
            self.integrity["reset_cleared_book"] += 1
            self._orders.clear()
            self._levels = {BID: {}, ASK: {}}
            return

        # Size is validated only where it is USED, so a stray value on a row this book ignores
        # cannot abort a replay that `InstrumentBook` would have survived.
        size = self._size(row)
        order_id = self._as_int(row.get("order_id"), "order_id")
        price = self._as_int(row.get("price_raw"), "price_raw", default=PRICE_SENTINEL_ABS)
        if not order_id:
            # `normalize` coerces a missing or unparseable order id to 0 and `_add_order` rests
            # it as a real order. Dropping it here would leave the level one order short, so it
            # is kept and counted instead.
            self.integrity["order_id_zero"] += 1

        if action == ADD:
            self._add(row, order_id, price, size)
        elif action == CANCEL:
            self._cancel(order_id, size)
        else:
            self._modify(row, order_id, price, size)

    # --- mutating branches, each a transcription of its InstrumentBook method ---

    def _add(self, row: Mapping[str, Any], order_id: int, price: int, size: int) -> None:
        """`InstrumentBook._add_order` and the `A` branch of `_book_effect`."""
        side = str(row.get("side", NONE))
        if side not in BOOK_SIDES:
            # `_book_effect` counts `add_invalid_side` and mutates nothing. Databento's "N" is
            # the tape DECLINING to state a side; assigning it to one would fabricate the very
            # fact that is missing (the `ladder_transitions` rule).
            self.integrity["add_invalid_side"] += 1
            return
        if abs(price) >= PRICE_SENTINEL_ABS and self._as_int(row.get("flags"), "flags") & F_TOB:
            # The normalized top-of-book wipe. `_book_effect` drops every resting order on this
            # side. Its blast radius is the whole side for the rest of the run, which is
            # exactly why this book must not quietly decline to do it.
            self.integrity["tob_side_wipe"] += 1
            for oid in [o for o, r in self._orders.items() if r.side == side]:
                self._remove(oid)
            return
        if abs(price) >= PRICE_SENTINEL_ABS:
            # `_add_order` rests this, and `best_price_raw` then reports the sentinel as the
            # touch. Mirrored rather than corrected: deciding we know better is how two books
            # over one tape end up disagreeing with nothing failing. Counted so it is visible.
            self.integrity["sentinel_price_rested"] += 1
        if order_id in self._orders:
            # `_add_order` counts this and rests the new order in place of the old.
            self.integrity["duplicate_add_order_id"] += 1
            self._remove(order_id)
        self._rest(order_id, side, price, size)

    def _cancel(self, order_id: int, size: int) -> None:
        """`InstrumentBook._cancel`: decrement by the ROW's size, remove only at zero.

        Side and price come from the RESTING order, never from the row: the row is the
        instruction, the book is the fact. An unknown order id mutates nothing - a group is a
        SLICE of the day, so a cancel of an order that rested before the window opened is
        structural, not malformed - and it is counted rather than passed over in silence.
        """
        order = self._orders.get(order_id)
        if order is None:
            self.integrity["cancel_missing_order"] += 1
            return
        if size > order.size:
            # `_cancel` clamps at zero and reports the truth only in its `size_delta`. The
            # quantity the clamp swallows is kept here rather than lost.
            self.integrity["over_cancel_quantity"] += size - order.size
        order.size = max(0, order.size - size)
        if order.size == 0:
            self._remove(order_id)

    def _modify(self, row: Mapping[str, Any], order_id: int, price: int, size: int) -> None:
        """`InstrumentBook._modify`, branch for branch."""
        side = str(row.get("side", NONE))
        if side not in BOOK_SIDES:
            # `_modify` calls `_add_order` with no side check and dies on `levels["N"]` with a
            # KeyError. One book aborting while the other carries on is a divergence too, so
            # they abort together - after the row is counted.
            self.integrity["modify_invalid_side"] += 1
            raise RtBookError(
                f"a modify on side {side!r} is not applicable to a book with sides "
                f"{list(BOOK_SIDES)}; `InstrumentBook` raises KeyError on the same row"
            )
        if abs(price) >= PRICE_SENTINEL_ABS:
            self.integrity["sentinel_price_rested"] += 1
        order = self._orders.get(order_id)

        if order is None:
            # Databento's reference LOB treats a missing modify as an add, and `_modify`
            # records the anomaly rather than dropping the row.
            self.integrity["modify_missing_treated_as_add"] += 1
            self._rest(order_id, side, price, size)
            return
        if side != order.side:
            self.integrity["modify_side_change"] += 1
            self._remove(order_id)
            self._rest(order_id, side, price, size)
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

    def _as_int(self, value: Any, field: str, *, default: int = 0) -> int:
        """Coerce, and fail as `RtBookError` rather than as a bare `ValueError`.

        `RtBookError` subclasses `ValueError`, so containment does not run the other way: a
        caller writing `except RtBookError` would not catch a raw `int()` failure, and this
        module's whole error contract is that one exception type. The default mirrors
        `normalize`, which coerces an absent price to the sentinel and an absent id to zero.
        """
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise RtBookError(f"{field} is not an integer: {value!r}") from exc

    def _size(self, row: Mapping[str, Any]) -> int:
        """A size is a quantity, so a negative one is refused rather than clamped.

        THE ONLY DIVERGENCE, and it is about malformed INPUT rather than about a mutation.
        `InstrumentBook` writes `max(0, size)`, turning a malformed row into a silent zero.
        Refusing keeps this book stricter on what it ACCEPTS and identical on what it DOES
        with anything both accept, which is the only shape of divergence that cannot put the
        two into disagreement about a real row. Follows `native_group_adapters._size`.
        """
        size = self._as_int(row.get("size"), "size")
        if size < 0:
            raise RtBookError(f"negative size {size} in a raw action row")
        return size

    @staticmethod
    def _require_side(side: str) -> None:
        """A READ for a side that does not exist is refused, never answered.

        `(0, 0)` and `None` are the LEAST conservative possible answers here: they say "front
        of the queue" and "no touch". `native_queue` feeds `book_view` straight into
        `initial_orders_ahead`, so a mistyped or `N` side would manufacture a front-of-queue
        survival input out of a lookup that never happened. This governs reads only; what the
        book DOES with an unsided row is mirrored above.
        """
        if side not in BOOK_SIDES:
            raise RtBookError(f"side {side!r} is not a book side; expected one of {list(BOOK_SIDES)}")

    def _level_ids(self, side: str, price_raw: int) -> list[int]:
        self._require_side(side)
        return self._levels[side].get(self._as_int(price_raw, "price_raw"), [])

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
            self.integrity["missing_level_on_remove"] += 1
            return
        if order_id in ids:
            ids.remove(order_id)
        else:
            self.integrity["missing_order_id_in_level_on_remove"] += 1
        if not ids:
            self._levels[order.side].pop(order.price_raw, None)

    def _remove(self, order_id: int) -> None:
        order = self._orders.pop(order_id, None)
        if order is not None:
            self._detach(order_id, order)
