"""Section 4.6 from one F_LAST group: queue position, priority, order survival (D53).

`QueueSurvivalCalculator` was built, tested, closed at its boundaries and fed by nothing.
`native_group_adapters` is that missing layer for 4.8, 4.9, 4.13 and 4.14; this is it for
4.6. It is a separate module because 4.6 is a different KIND of ingest: the other four take
a domain object built from a group's actions alone, while 4.6 takes an ordered stream of
CALLS whose meaning depends on the state of a live FIFO book between them. There is no
`queue_events(actions, ctx)` that could return a value, because the value of the second call
depends on what the first one did to the book.

**The unit is still the F_LAST group, and the input is still only the group's own actions.**
The adapter advances a `ReplayBook` one raw action at a time and, after each one, reports to
the calculator what the book DID. It never re-derives a book rule and then tells the
calculator its own answer; the book is the fact, the row is the instruction. That split is
the whole reason `native_rt_book` exists (see its docstring) and it is the `_family_id`
defect of 2026-08-29 in another costume: two vocabularies over one quantity do not fail, the
numbers simply differ.

**NO LOOKAHEAD, structurally rather than by policy.** `InstrumentBook` mutates on every
record while the group frame is only returned at F_LAST, so reading a level off that book at
group close reports it AFTER the very add it describes - present, typed, in range and wrong.
This adapter never reads that book. It reads `ReplayBook`, which it advances itself, action
by action, so `orders_ahead` is the number that stood when the order rested. Every call the
calculator receives is made from a book that has seen this row and nothing later.

**Where the book is the arbiter, and the one place it is not.** After each row the adapter
asks the book three questions - is this order resting, where, and how far back - and derives
every call from the answers. Departures, level moves and queue movement are therefore
OBSERVED. The single exception is priority retention on a modify: `ReplayBook._modify`
decides it from `old_price != price_raw or size > old_size` and does not expose the decision,
and an observed position cannot substitute, because an order re-appended to the back of a
level where it was already last shows an unchanged `orders_ahead`. So that one condition is
recomputed here from the BOOK's own pre-state plus the row - `PRIORITY_RULE_BASIS` - and it
is cross-checked: a position that increased while the rule says priority held is a real
disagreement between two books over one tape and is counted as `priority_rule_disagreement`,
never smoothed away.

**Terminal attribution, which the contract does not specify.** In this feed `F` mutates
nothing; the venue's later `C` or `M` is what removes the liquidity, so the row that ends a
lifecycle looks identical whether the order traded or was pulled. The adapter keeps a pending
fill quantity per order id - `F` rows add to it, book size reductions consume it - and a
removal that consumed pending fill is `FILLED`, a removal that consumed none is `CANCELLED`.
The basis travels ON the row as `terminal_basis`, never only in this docstring (S114). A
partial fill followed by a genuine cancel of the remainder therefore resolves as CANCELLED,
which is the honest reading: the pending quantity was already booked by the earlier
reduction.

**`fills_ahead` is credited at the DEPARTURE, not at the `F` row, and that is load-bearing.**
The calculator's self-check is the FIFO identity
`initial_orders_ahead - current_orders_ahead == fills_ahead + cancels_ahead`. Crediting a
fill when the `F` arrives would raise `fills_ahead` while `current_orders_ahead` is still
unchanged - `F` does not mutate the book - driving the residual negative and recording a
violation of an identity that exists to detect NON-FIFO events. Booking the fill at the
instant the book removes the order keeps every departure classified exactly once, at the
instant it happens, so a recorded violation still means what it says.

**No averaging anywhere.** Nothing here returns a mean, a ratio-of-sums or a rate. The
calculator owns the stratified measures and the survival estimator; this module hands it
exact per-order quantities and exact counts. Sizes and counts are integers throughout.

**The declared cost of the one-unit choice, recorded rather than smoothed over (D53).**
Greg took this trade knowingly and it is written into D53: 4.6 is NOT naturally group-shaped.
An order lifecycle is a property of the ORDER and can outlive the group that gave birth to
it by an arbitrary number of groups, while a 4.6 stratum key wants a family, a phase and a
side. This adapter resolves that by stamping the stratum at BIRTH and never restamping it -
`QUEUE_SCOPE = "BIRTH_GROUP_STRATUM"` - because restamping mid-life would move an order
between strata on the strength of a group it merely coexisted with, and averaging across the
move is exactly what section 3 forbids. That choice distorts, so the distortions are
COUNTED and emitted by `report()` rather than described here and forgotten:

* `lifecycles_outliving_birth_group` - how often the birth-group family label describes an
  order that was still resting many groups later. A large count does not invalidate the
  stratum; it states how much of the population the label is a convention for.
* `lifecycles_observed_in_another_phase` - orders whose queue was still being observed in a
  session phase other than the one their stratum names.
* `orphaned_by_reset` / `orphaned_by_tob_wipe` - a reset or a top-of-book side wipe removes
  resting orders WITHOUT naming them. Their exit is real but it is neither a fill nor a
  cancel, and `on_terminal` accepts only those two, so the lifecycle is left OPEN and is
  censored at the next continuity boundary. Censoring is the right treatment for an
  observation lost administratively, but the censored age is then measured to the boundary
  rather than to the wipe, which OVERSTATES it. Declared, counted, not repaired here.
* `reprice_departures_ahead` - an order ahead of ours that leaves the level by re-pricing is
  a departure that is neither fill nor cancel, and `cancels_ahead` is a residual, so it is
  booked as a cancel-ahead. That is the calculator's declared basis and this adapter does not
  fight it; it counts how often the residual is carrying a re-price.
* `snapshot_adds_not_born` - a snapshot `A` restates a book rather than creating an order, so
  its birth time would be false. The book still applies it (it must mirror), but no lifecycle
  opens, because a value the adapter cannot justify from the group's contents is not emitted.
* `anonymous_adds_not_tracked` - `normalize` writes `order_id` 0 for a missing or unparseable
  id and the book rests it as a real order, which is correct for depth. It is not an
  identity, so a lifecycle keyed on it would fuse unrelated orders into one; the book keeps
  it, the survival ledger does not, and the count says how many.
* `cancel_for_untracked_order` / `fill_for_unlocated_order` - a group is a SLICE of the day,
  so orders that rested before the window opened are cancelled and filled inside it. Those
  are structural absences, not defects, and they are counted so a reader can see what share
  of the tape's exits the ledger could not attach to a birth it observed.

**Nothing is dropped (D60).** Every row is applied to the book exactly once, including the
ones that mutate nothing, and every row that produces no calculator call still produces a
counter. Sizes are refused rather than clamped, on the `native_group_adapters._size`
precedent: `max(0, size)` turns a malformed row into a silent zero.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_group_adapters import (
    PRICE_SENTINEL_ABS,
    GroupContext,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_queue import (
    CANCELLED,
    FILLED,
    QueueSurvivalCalculator,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_rt_book import ReplayBook

__all__ = [
    "QueueAdapterError",
    "QueueGroupAdapter",
    "QUEUE_SCOPE",
    "PRIORITY_RULE_BASIS",
    "TERMINAL_BASIS_FILL",
    "TERMINAL_BASIS_CANCEL",
    "DECLARED_DISTORTIONS",
]

ADD = "A"
CANCEL = "C"
MODIFY = "M"
RESET = "R"
FILL = "F"
TRADE = "T"
NONE_ACTION = "N"

BID, ASK = "B", "A"
BOOK_SIDES = (BID, ASK)

QUEUE_SCOPE = "BIRTH_GROUP_STRATUM"
"""What a 4.6 stratum label IS under D53. Travels with the value; see the module docstring.

The family, session phase and side on an order's stratum key are the ones that held in the
group where the order was BORN, and they are never restamped. Read as "the family that was
trading while this order rested" it would be wrong for any order that outlived its group.
"""

PRIORITY_RULE_BASIS = "OLD_PRICE_CHANGED_OR_ROW_SIZE_EXCEEDS_RESTING_SIZE"
"""The one book rule this module recomputes, named so a later definition cannot replace it.

Transcribed from `ReplayBook._modify`, evaluated against the BOOK's pre-state and the row.
Cross-checked against the observed change in `orders_ahead`, which can falsify it but cannot
confirm it - an order re-appended to the back of a level where it was already last does not
move. Disagreements are counted, never resolved silently.
"""

TERMINAL_BASIS_FILL = "OWN_FILL_PENDING_AT_REMOVAL"
TERMINAL_BASIS_CANCEL = "NO_OWN_FILL_PENDING_AT_REMOVAL"
"""Why a removal was called FILLED or CANCELLED. Travels on the emitted lifecycle row."""

DECLARED_DISTORTIONS: tuple[dict[str, str], ...] = (
    {
        "name": "BIRTH_GROUP_STRATUM",
        "statement": (
            "family_id, session_phase and side_orientation are stamped in the group that gave "
            "birth to the order and are never restamped, so an order outliving its birth group "
            "carries a label describing a group it merely coexisted with"
        ),
        "counters": "lifecycles_outliving_birth_group, lifecycles_observed_in_another_phase",
    },
    {
        "name": "RESET_ORPHAN_CENSORED_AT_THE_BOUNDARY",
        "statement": (
            "a reset or top-of-book side wipe removes resting orders without naming them; the "
            "exit is neither a fill nor a cancel, so the lifecycle stays open and is censored at "
            "the next continuity boundary, which overstates the censored age"
        ),
        "counters": "orphaned_by_reset, orphaned_by_tob_wipe",
    },
    {
        "name": "REPRICE_DEPARTURE_BOOKED_AS_CANCEL_AHEAD",
        "statement": (
            "cancels_ahead is a residual, so an order ahead that leaves a level by re-pricing is "
            "counted as a cancel ahead rather than as a move"
        ),
        "counters": "reprice_departures_ahead",
    },
    {
        "name": "SNAPSHOT_ADD_IS_NOT_A_BIRTH",
        "statement": (
            "a snapshot add restates a book rather than creating an order, so its birth time "
            "would be false; the book applies it and no lifecycle opens"
        ),
        "counters": "snapshot_adds_not_born",
    },
    {
        "name": "ANONYMOUS_ORDER_ID_NOT_TRACKED",
        "statement": (
            "order_id 0 is a missing identity, not an identity; the book rests it so depth stays "
            "right and no lifecycle opens, because one key would fuse unrelated orders"
        ),
        "counters": "anonymous_adds_not_tracked",
    },
    {
        "name": "PRE_WINDOW_ORDERS_HAVE_NO_BIRTH",
        "statement": (
            "a group is a slice of the day, so exits of orders that rested before the window "
            "opened cannot be attached to an observed birth"
        ),
        "counters": "cancel_for_untracked_order, fill_for_unlocated_order",
    },
)
"""Where the F_LAST group unit distorts 4.6, stated on the value and counted (D53)."""


class QueueAdapterError(ValueError):
    """A group could not be turned into a lawful 4.6 ingest."""


def _int(row: Mapping[str, Any], key: str, default: int = 0) -> int:
    value = row.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise QueueAdapterError(f"{key} is not an integer: {value!r}") from exc


def _size(row: Mapping[str, Any]) -> int:
    """A size is a quantity, so a negative one is refused rather than clamped.

    `ReplayBook._size` refuses on the actions that mutate the book, but it returns before
    validating anything on `F`, `T` and `N`. A fill size is read HERE, so it is validated
    here too: `max(0, size)` would turn a malformed row into a silent zero, and a zero own
    fill is present, typed, in range and wrong.
    """
    size = _int(row, "size")
    if size < 0:
        raise QueueAdapterError(f"negative size {size} in a raw action row")
    return size


def _action(row: Mapping[str, Any]) -> str:
    return str(row.get("action", "?"))


def _side(row: Mapping[str, Any]) -> str:
    return str(row.get("side", NONE_ACTION))


def _recv_ns(row: Mapping[str, Any], default: int) -> int:
    """The row's own receive time, falling back to the group's.

    Per-row rather than per-group, matching `native_group_adapters.occurrences`. A lifetime
    measured on the group clock would be zero for every order born and killed inside one
    group, which is a large share of them. There is no lookahead in this: the adapter only
    ever runs at F_LAST, when the whole group is already lawful knowledge, and it is stamping
    exact observed times rather than claiming to have known them earlier.
    """
    return _int(row, "ts_recv_ns", default)


def _is_snapshot(row: Mapping[str, Any]) -> bool:
    """Snapshot flag, from the normalized field or from the raw flag bits.

    `NormalizedMbo.public_dict` writes `is_snapshot`, but a hand-built row may carry only
    `flags`, so both are read. Section 2 treats a snapshot as a boundary, not as history.
    """
    flagged = row.get("is_snapshot")
    if flagged is not None:
        return bool(flagged)
    return bool(_int(row, "flags") & 32)


@dataclass
class _Tracked:
    """One order this adapter opened a lifecycle for and has not yet closed.

    This is the adapter's log of the calls it MADE, not a mirror of calculator state and not
    a second opinion about the book. Nothing is decided from `side`/`price_raw`/`size`: they
    are an index into `_by_level` and are re-read from the book before any use.
    """

    order_id: int
    instrument_id: int
    continuity_segment: int
    birth_group_index: int
    birth_session_phase: str
    birth_family_id: str
    birth_recv_ns: int
    side: str
    price_raw: int
    size: int
    outlived_birth_group: bool = False
    observed_in_another_phase: bool = False
    book_absent: bool = False


@dataclass
class _Tally:
    """What one group produced. Exact counts plus the exact rows, never a rate."""

    births: int = 0
    terminals: list[dict[str, Any]] = field(default_factory=list)
    priority_losses: int = 0
    modifies_retaining_priority: int = 0
    level_observations: int = 0
    own_fills: int = 0
    level_fills: int = 0
    rows_applied: int = 0


class QueueGroupAdapter:
    """Feeds `QueueSurvivalCalculator` from F_LAST groups and one advancing `ReplayBook`.

    Stateful across groups by necessity: an order lifecycle is not group-shaped, so the
    tracked set, the pending fill ledger and the level index all outlive the group that
    created them. That is the same shape as the driver's `_lineage_node_of`.

    The caller owns the book and must advance the SAME book across every group of an
    instrument - a book rebuilt per group would report every order as front-of-queue, which
    is a number, in range, and wrong. A different book object for an instrument already seen
    is refused rather than used.
    """

    def __init__(self) -> None:
        self._tracked: dict[tuple[int, int], _Tracked] = {}
        self._by_level: dict[tuple[int, str, int], list[int]] = {}
        self._pending_fill: dict[tuple[int, int], int] = {}
        self._books: dict[int, ReplayBook] = {}
        self._segment: int | None = None
        self.counters: Counter[str] = Counter()
        """Everything observed that produced no calculator call, or an anomalous one.

        Nothing this adapter sees is discarded; what it does not measure, it counts.
        """

    # --- public surface ---------------------------------------------------

    @property
    def open_tracked_orders(self) -> int:
        return len(self._tracked)

    def feed_group(
        self,
        calculator: QueueSurvivalCalculator,
        actions: Sequence[Mapping[str, Any]],
        ctx: GroupContext,
        *,
        book: ReplayBook,
    ) -> dict[str, Any]:
        """Advance `book` over this group's actions and feed 4.6 from what the book did.

        Returns the exact rows and counts this group produced. The terminal rows are the ONLY
        emission point for a lifecycle that resolved inside a group - `close_continuity_
        segment` and `finalize` emit only the censored ones - so dropping this return keeps
        the stratified average and loses the member beneath it, which section 6 rejects and
        D60 forbids.
        """
        if not actions:
            raise QueueAdapterError("an F_LAST group must contain at least one native action")
        self._require_one_book(ctx.instrument_id, book)
        self._require_segment(ctx)
        tally = _Tally()
        for row in actions:
            self._row(calculator, book, row, ctx, tally)
        return {
            "section": "4.6",
            "candidate_id": ctx.candidate_id,
            "group_index": ctx.group_index,
            "instrument_id": ctx.instrument_id,
            "continuity_segment": ctx.continuity_segment,
            "queue_scope": QUEUE_SCOPE,
            "rows_applied": tally.rows_applied,
            "births": tally.births,
            "priority_losses": tally.priority_losses,
            "modifies_retaining_priority": tally.modifies_retaining_priority,
            "level_observations": tally.level_observations,
            "own_fills": tally.own_fills,
            "level_fills": tally.level_fills,
            "terminals": tally.terminals,
            "terminal_count": len(tally.terminals),
            "open_tracked_orders": len(self._tracked),
        }

    def close_continuity_segment(self, *, segment: int) -> dict[str, Any]:
        """Release the adapter's tracking for one segment. The CALCULATOR censors its own.

        Two owners for one censoring would double-count, so this deliberately does not call
        `QueueSurvivalCalculator.close_continuity_segment`; the traversal already does, and
        it is the only place that knows the boundary's receive time. What this releases is
        the adapter's own bookkeeping, which would otherwise go on addressing lifecycles the
        calculator has already closed - every such call would land in `unknown_order_events`
        and quietly turn a defect counter into noise.
        """
        released = [t for t in self._tracked.values() if t.continuity_segment == segment]
        for tracked in released:
            self._untrack(tracked)
        self.counters["tracking_released_at_segment_close"] += len(released)
        return {
            "section": "4.6",
            "continuity_segment": segment,
            "tracking_released": len(released),
            "open_tracked_orders": len(self._tracked),
        }

    def finalize(self) -> dict[str, Any]:
        """Release everything at stream end. The calculator censors its own open orders."""
        released = len(self._tracked)
        for tracked in list(self._tracked.values()):
            self._untrack(tracked)
        self._pending_fill.clear()
        self.counters["tracking_released_at_stream_end"] += released
        return {"section": "4.6", "tracking_released": released, "open_tracked_orders": 0}

    def report(self) -> dict[str, Any]:
        """Everything the adapter measured, plus where the F_LAST unit distorts 4.6."""
        return {
            "section": "4.6",
            "queue_scope": QUEUE_SCOPE,
            "priority_rule_basis": PRIORITY_RULE_BASIS,
            "terminal_attribution": {
                FILLED: TERMINAL_BASIS_FILL,
                CANCELLED: TERMINAL_BASIS_CANCEL,
                "note": (
                    "F mutates nothing in this feed, so a removal is attributed by whether it "
                    "consumed pending own-fill quantity, never by the removing row's action"
                ),
            },
            "fills_ahead_credit_point": "BOOK_REMOVAL_OF_THE_FILLED_ORDER",
            "counters": dict(self.counters),
            "open_tracked_orders": len(self._tracked),
            "orders_with_pending_fill": len(self._pending_fill),
            "instruments": sorted(self._books),
            "declared_distortions": [dict(d) for d in DECLARED_DISTORTIONS],
        }

    # --- guards -----------------------------------------------------------

    def _require_one_book(self, instrument_id: int, book: ReplayBook) -> None:
        if not isinstance(book, ReplayBook):
            raise QueueAdapterError("book must be a ReplayBook advanced action by action")
        known = self._books.get(instrument_id)
        if known is None:
            self._books[instrument_id] = book
            return
        if known is not book:
            raise QueueAdapterError(
                f"a second ReplayBook was supplied for instrument {instrument_id}; a book "
                "rebuilt between groups reports every resting order as front-of-queue, which "
                "is a number rather than a failure"
            )

    def _require_segment(self, ctx: GroupContext) -> None:
        """A segment change with tracking still held is a missing boundary call, not a state.

        Section 2 forbids a calculation crossing a continuity boundary and the calculator
        censors at one. If the traversal moved to a new segment without telling this adapter,
        its tracked orders now name lifecycles the calculator has already closed. Refusing is
        the only way that omission fails rather than reads as a queue with no movement.
        """
        if self._segment is not None and ctx.continuity_segment != self._segment:
            stale = [t for t in self._tracked.values() if t.continuity_segment == self._segment]
            if stale:
                raise QueueAdapterError(
                    f"segment {self._segment} still holds {len(stale)} tracked orders while "
                    f"group {ctx.group_index} opens segment {ctx.continuity_segment}; call "
                    "close_continuity_segment(segment=...) at the boundary"
                )
        self._segment = ctx.continuity_segment

    def _require_instrument(self, row: Mapping[str, Any], ctx: GroupContext) -> None:
        stated = row.get("instrument_id")
        if stated is not None and int(stated) != ctx.instrument_id:
            raise QueueAdapterError(
                f"row names instrument {int(stated)} inside a group on {ctx.instrument_id}; "
                "one book per instrument is the premise of every queue position here"
            )

    # --- the per-row pass -------------------------------------------------

    def _row(
        self,
        calc: QueueSurvivalCalculator,
        book: ReplayBook,
        row: Mapping[str, Any],
        ctx: GroupContext,
        tally: _Tally,
    ) -> None:
        """Apply one raw action to the book, then tell 4.6 what the book did.

        The book is advanced exactly once per row, including for the actions that mutate
        nothing, so its integrity counters account for every row this adapter saw.
        """
        self._require_instrument(row, ctx)
        action = _action(row)
        order_id = _int(row, "order_id")
        instrument_id = ctx.instrument_id
        recv_ns = _recv_ns(row, ctx.recv_ns)
        handle = (instrument_id, order_id)

        # Pre-state, read from the book BEFORE the row lands. `resting_at` is the fact; the
        # row is only the instruction, which is `ReplayBook._cancel`'s doctrine.
        pre = book.resting_at(order_id) if order_id else None
        ahead_before = -1
        behind: list[int] = []
        if pre is not None and pre[0] in BOOK_SIDES and action in (ADD, CANCEL, MODIFY):
            ahead_before = book.view(pre[0], pre[1], order_id)[0]
            behind = self._behind(book, instrument_id, pre[0], pre[1], order_id, ahead_before)

        watched = self._watch(book, action)
        book.apply(row)
        fired = self._fired(book, watched)
        tally.rows_applied += 1

        if action == RESET:
            self._orphan(list(self._tracked.values()), "orphaned_by_reset")
            return
        if action == FILL:
            self._on_fill(calc, row, ctx, tally, resting=pre, order_id=order_id)
            return
        if action in (TRADE, NONE_ACTION):
            # Counted rather than passed over: a trade summary is the event 4.8 measures, and
            # it changes no queue position, so 4.6 records that it saw one.
            self.counters[f"non_mutating_{action}"] += 1
            return

        if fired.get("tob_side_wipe"):
            side = _side(row)
            self._orphan(
                [t for t in self._tracked.values() if t.instrument_id == instrument_id and t.side == side],
                "orphaned_by_tob_wipe",
            )
            return
        if fired.get("add_invalid_side"):
            self.counters["unsided_row_rested_nothing"] += 1
            return

        post = book.resting_at(order_id) if order_id else None
        tracked = self._tracked.get(handle)

        if action == ADD:
            self._on_add(
                calc, book, row, ctx, tally,
                order_id=order_id, pre=pre, post=post, tracked=tracked, fired=fired,
                recv_ns=recv_ns, behind=behind,
            )
            return
        self._on_cancel_or_modify(
            calc, book, row, ctx, tally,
            action=action, order_id=order_id, pre=pre, post=post, tracked=tracked,
            fired=fired, recv_ns=recv_ns, ahead_before=ahead_before, behind=behind,
        )

    # --- action branches --------------------------------------------------

    def _on_add(
        self,
        calc: QueueSurvivalCalculator,
        book: ReplayBook,
        row: Mapping[str, Any],
        ctx: GroupContext,
        tally: _Tally,
        order_id: int,
        post: tuple[str, int, int] | None,
        tracked: _Tracked | None,
        fired: Mapping[str, int],
        recv_ns: int,
    ) -> None:
        """An add that RESTED is a birth. One that did not is counted, never invented."""
        if post is None:
            self.counters["add_rested_nothing"] += 1
            return
        if not order_id:
            self.counters["anonymous_adds_not_tracked"] += 1
            return
        if tracked is not None:
            # `_add_order` REPLACES on a duplicate id, so the order is off its old level and
            # back at the tail of a new one. That is priority loss by any reading, and using
            # the ingest point the calculator already has keeps one lifecycle for one id
            # rather than forking it - which `on_add` refuses outright.
            self.counters[
                "duplicate_add_requeued" if fired.get("duplicate_add_order_id") else "readd_of_absent_order_requeued"
            ] += 1
            self._priority_loss(calc, book, tracked, post, recv_ns, tally)
            return
        if _is_snapshot(row):
            self.counters["snapshot_adds_not_born"] += 1
            return
        if abs(post[1]) >= PRICE_SENTINEL_ABS:
            # The book rests it and reports it as the touch, so the level is real to every
            # other order there. Kept, and counted, because a queue position at a price that
            # does not exist is a fact about the feed rather than about the market.
            self.counters["sentinel_price_births"] += 1
        self._birth(calc, book, row, ctx, tally, order_id, post, recv_ns)

    def _on_cancel_or_modify(
        self,
        calc: QueueSurvivalCalculator,
        book: ReplayBook,
        row: Mapping[str, Any],
        ctx: GroupContext,
        tally: _Tally,
        *,
        action: str,
        order_id: int,
        pre: tuple[str, int, int] | None,
        post: tuple[str, int, int] | None,
        tracked: _Tracked | None,
        fired: Mapping[str, int],
        recv_ns: int,
        ahead_before: int,
        behind: Sequence[int],
    ) -> None:
        """Everything a cancel or a modify can do to a queue, decided from the book."""
        if fired.get("modify_missing_treated_as_add"):
            # Databento's reference LOB treats a missing modify as an add and the book mirrors
            # it. For 4.6 that is a birth when we have never seen the id, and a re-queue when
            # the id is one we lost to a reset or a wipe.
            self.counters["modify_missing_treated_as_add"] += 1
            if post is None:
                self.counters["add_rested_nothing"] += 1
            elif tracked is not None:
                self._priority_loss(calc, book, tracked, post, recv_ns, tally)
            elif order_id and not _is_snapshot(row):
                self._birth(calc, book, row, ctx, tally, order_id, post, recv_ns)
            elif order_id:
                self.counters["snapshot_adds_not_born"] += 1
            else:
                self.counters["anonymous_adds_not_tracked"] += 1
            return

        if pre is None:
            # A group is a slice of the day, so a cancel or modify of an order that rested
            # before the window opened is structural. The book counted it; so does this.
            self.counters[
                "cancel_for_untracked_order" if action == CANCEL else "modify_for_untracked_order"
            ] += 1
            if tracked is not None:
                # It is tracked but absent from the book, so a reset or a wipe already took
                # it. We never observed a lawful exit, so the lifecycle stays open and is
                # censored at the boundary rather than being resolved by a row.
                self.counters["terminal_row_for_orphaned_order"] += 1
            return

        side_before, price_before, size_before = pre
        size_after = post[2] if post is not None else 0
        reduction = max(0, size_before - size_after)
        consumed = self._consume_pending(ctx.instrument_id, order_id, reduction)
        departed = post is None
        moved = post is not None and (post[0], post[1]) != (side_before, price_before)

        if departed:
            status = FILLED if consumed > 0 else CANCELLED
            basis = TERMINAL_BASIS_FILL if consumed > 0 else TERMINAL_BASIS_CANCEL
            leftover = self._pending_fill.pop((ctx.instrument_id, order_id), 0)
            if leftover:
                # An F reported more quantity than the book ever held for the order.
                self.counters["pending_fill_unbooked_at_removal"] += leftover
            if tracked is not None:
                self._terminate(calc, ctx, tally, tracked, status, basis, recv_ns)
        elif tracked is not None:
            if action == MODIFY:
                self._modify_priority(
                    calc, book, row, tally, tracked, pre, post, recv_ns, ahead_before, moved
                )
            self._touch(tracked, ctx)

        if moved and behind:
            self.counters["reprice_departures_ahead"] += len(behind)

        credit = 1 if (departed and consumed > 0) else 0
        self._refresh_level(
            calc, book, ctx.instrument_id, side_before, price_before, tally,
            credited=set(behind) if credit else set(),
        )
        if moved and post is not None:
            self._refresh_level(calc, book, ctx.instrument_id, post[0], post[1], tally, credited=set())

    def _modify_priority(
        self,
        calc: QueueSurvivalCalculator,
        book: ReplayBook,
        row: Mapping[str, Any],
        tally: _Tally,
        tracked: _Tracked,
        pre: tuple[str, int, int],
        post: tuple[str, int, int],
        recv_ns: int,
        ahead_before: int,
        moved: bool,
    ) -> None:
        """Priority retained, or lost. See PRIORITY_RULE_BASIS for why this one is recomputed."""
        side_before, price_before, size_before = pre
        rule_says_lost = (
            price_before != _int(row, "price_raw", PRICE_SENTINEL_ABS)
            or _size(row) > size_before
        )
        ahead_after = book.view(post[0], post[1], tracked.order_id)[0]
        position_moved_back = (not moved) and ahead_before >= 0 and ahead_after > ahead_before
        if position_moved_back and not rule_says_lost:
            # The observation can falsify the rule even though it cannot confirm it. Two books
            # over one tape disagreeing is the defect this tree keeps finding, so it is
            # counted rather than resolved in favour of whichever is convenient.
            self.counters["priority_rule_disagreement"] += 1
        if moved:
            self.counters["modify_side_change_kept_birth_side" if post[0] != side_before else "modify_reprice"] += 1
        if moved or rule_says_lost or position_moved_back:
            self._priority_loss(calc, book, tracked, post, recv_ns, tally)
            if rule_says_lost and not position_moved_back and not moved:
                self.counters["priority_loss_not_visible_in_position"] += 1
            return
        calc.on_modify_retaining_priority(
            instrument_id=tracked.instrument_id, order_id=tracked.order_id
        )
        tally.modifies_retaining_priority += 1

    def _on_fill(
        self,
        calc: QueueSurvivalCalculator,
        row: Mapping[str, Any],
        ctx: GroupContext,
        tally: _Tally,
        *,
        resting: tuple[str, int, int] | None,
        order_id: int,
    ) -> None:
        """An `F` mutates nothing, so it books quantity and locates a level - never a queue.

        The fill is NOT credited to anyone's `fills_ahead` here. See the module docstring: the
        credit lands when the book removes the filled order, so the FIFO identity stays exact.
        """
        size = _size(row)
        if order_id:
            key = (ctx.instrument_id, order_id)
            self._pending_fill[key] = self._pending_fill.get(key, 0) + size
        tracked = self._tracked.get((ctx.instrument_id, order_id))
        if tracked is not None:
            calc.on_own_fill(instrument_id=ctx.instrument_id, order_id=order_id, size=size)
            tally.own_fills += 1
            self._touch(tracked, ctx)
        if resting is not None and resting[0] in BOOK_SIDES:
            calc.note_level_fill(
                instrument_id=ctx.instrument_id, side=resting[0], price_raw=resting[1]
            )
            tally.level_fills += 1
            return
        # The book cannot locate the filled order - an aggressor's own fill, or an order that
        # rested before the window opened. Its side is then the row's claim rather than a book
        # fact, and levelling a fill on an unconfirmed side would fabricate the one thing
        # missing, so it is counted instead.
        self.counters["fill_for_unlocated_order"] += 1

    # --- calculator calls -------------------------------------------------

    def _birth(
        self,
        calc: QueueSurvivalCalculator,
        book: ReplayBook,
        row: Mapping[str, Any],
        ctx: GroupContext,
        tally: _Tally,
        order_id: int,
        post: tuple[str, int, int],
        recv_ns: int,
    ) -> None:
        side, price, size = post
        calc.on_add(
            instrument_id=ctx.instrument_id,
            order_id=order_id,
            side=side,
            price_raw=price,
            recv_ns=recv_ns,
            sequence=_int(row, "sequence"),
            continuity_segment=ctx.continuity_segment,
            source_day=ctx.source_day,
            source_role=ctx.source_role,
            family_id=ctx.family_id,
            session_phase=ctx.session_phase,
            book_view=book.view,
        )
        tracked = _Tracked(
            order_id=order_id,
            instrument_id=ctx.instrument_id,
            continuity_segment=ctx.continuity_segment,
            birth_group_index=ctx.group_index,
            birth_session_phase=ctx.session_phase,
            birth_family_id=ctx.family_id,
            birth_recv_ns=recv_ns,
            side=side,
            price_raw=price,
            size=size,
        )
        self._tracked[(ctx.instrument_id, order_id)] = tracked
        self._by_level.setdefault((ctx.instrument_id, side, price), []).append(order_id)
        tally.births += 1

    def _priority_loss(
        self,
        calc: QueueSurvivalCalculator,
        book: ReplayBook,
        tracked: _Tracked,
        post: tuple[str, int, int],
        recv_ns: int,
        tally: _Tally,
    ) -> None:
        side, price, size = post
        calc.on_priority_loss(
            instrument_id=tracked.instrument_id,
            order_id=tracked.order_id,
            side=side,
            price_raw=price,
            recv_ns=recv_ns,
            book_view=book.view,
        )
        self._relocate(tracked, side, price)
        tracked.size = size
        tracked.book_absent = False
        tally.priority_losses += 1

    def _terminate(
        self,
        calc: QueueSurvivalCalculator,
        ctx: GroupContext,
        tally: _Tally,
        tracked: _Tracked,
        status: str,
        basis: str,
        recv_ns: int,
    ) -> None:
        if recv_ns < tracked.birth_recv_ns:
            # The V4 adapter counts a receive-time regression rather than raising, so this
            # does too - but the lifetime it produces is negative, and a negative lifetime in
            # a survival curve is not a small error.
            self.counters["terminals_with_negative_lifetime"] += 1
        row = calc.on_terminal(
            instrument_id=tracked.instrument_id,
            order_id=tracked.order_id,
            status=status,
            recv_ns=recv_ns,
        )
        self._untrack(tracked)
        if row is None:
            self.counters["terminal_for_order_unknown_to_the_calculator"] += 1
            return
        row["terminal_basis"] = basis
        row["queue_scope"] = QUEUE_SCOPE
        row["birth_group_index"] = tracked.birth_group_index
        row["terminal_group_index"] = ctx.group_index
        row["birth_session_phase"] = tracked.birth_session_phase
        tally.terminals.append(row)

    def _refresh_level(
        self,
        calc: QueueSurvivalCalculator,
        book: ReplayBook,
        instrument_id: int,
        side: str,
        price: int,
        tally: _Tally,
        *,
        credited: set[int],
    ) -> None:
        """Re-read every tracked order still resting at one level and hand 4.6 the truth.

        Orders that were ahead of the change see the same numbers again, which is harmless -
        `QueueEpisode.observe` records a violation only on an INCREASE - and re-reading the
        whole level is what keeps a partial cancel ahead visible in `volume_ahead`.
        """
        if side not in BOOK_SIDES:
            return
        for order_id in self._tracked_at_level(book, instrument_id, side, price):
            orders_ahead, volume_ahead = book.view(side, price, order_id)
            calc.observe_level(
                instrument_id=instrument_id,
                order_id=order_id,
                orders_ahead=orders_ahead,
                volume_ahead=volume_ahead,
                fills_ahead_delta=1 if order_id in credited else 0,
            )
            tally.level_observations += 1

    # --- state -------------------------------------------------------------

    def _behind(
        self,
        book: ReplayBook,
        instrument_id: int,
        side: str,
        price: int,
        order_id: int,
        ahead_of_target: int,
    ) -> list[int]:
        """Tracked orders standing BEHIND `order_id` at its level, before the row lands.

        Captured before the mutation because afterwards the departing order is gone and the
        question cannot be asked. Only these may be credited with a fill ahead; an order in
        front of a departure gained nothing.
        """
        out = []
        for tid in self._tracked_at_level(book, instrument_id, side, price):
            if tid == order_id:
                continue
            if book.view(side, price, tid)[0] > ahead_of_target:
                out.append(tid)
        return out

    def _tracked_at_level(
        self, book: ReplayBook, instrument_id: int, side: str, price: int
    ) -> list[int]:
        """The tracked orders the BOOK still places at this level, pruning the index in passing.

        `_by_level` is an index over this adapter's own tracked set, never an opinion about
        where an order rests: every id is re-checked against `resting_at` before it is used,
        so a reset, a wipe or any move the adapter did not see prunes itself here rather than
        producing a queue reading for an order that is no longer there.
        """
        key = (instrument_id, side, price)
        ids = self._by_level.get(key)
        if not ids:
            return []
        kept = [
            oid
            for oid in ids
            if (instrument_id, oid) in self._tracked
            and book.resting_at(oid) is not None
            and book.resting_at(oid)[:2] == (side, price)
        ]
        if kept:
            self._by_level[key] = kept
        else:
            self._by_level.pop(key, None)
        return kept

    def _relocate(self, tracked: _Tracked, side: str, price: int) -> None:
        old = (tracked.instrument_id, tracked.side, tracked.price_raw)
        ids = self._by_level.get(old)
        if ids and tracked.order_id in ids:
            ids.remove(tracked.order_id)
            if not ids:
                self._by_level.pop(old, None)
        tracked.side = side
        tracked.price_raw = price
        self._by_level.setdefault((tracked.instrument_id, side, price), []).append(
            tracked.order_id
        )

    def _untrack(self, tracked: _Tracked) -> None:
        self._tracked.pop((tracked.instrument_id, tracked.order_id), None)
        key = (tracked.instrument_id, tracked.side, tracked.price_raw)
        ids = self._by_level.get(key)
        if ids and tracked.order_id in ids:
            ids.remove(tracked.order_id)
            if not ids:
                self._by_level.pop(key, None)

    def _orphan(self, tracked: Sequence[_Tracked], counter: str) -> None:
        """A reset or a side wipe removed these without naming them, so they are NOT resolved.

        `on_terminal` accepts FILLED and CANCELLED only, and this is neither: the order left
        the book administratively. Recording it as an event would inject a false resolved exit
        into the survival curve, so the lifecycle stays OPEN and is censored at the boundary.
        The cost - a censored age measured to the boundary rather than to the wipe - is one of
        DECLARED_DISTORTIONS.
        """
        for entry in tracked:
            if entry.book_absent:
                continue
            entry.book_absent = True
            key = (entry.instrument_id, entry.side, entry.price_raw)
            ids = self._by_level.get(key)
            if ids and entry.order_id in ids:
                ids.remove(entry.order_id)
                if not ids:
                    self._by_level.pop(key, None)
            self._pending_fill.pop((entry.instrument_id, entry.order_id), None)
            self.counters[counter] += 1

    def _touch(self, tracked: _Tracked, ctx: GroupContext) -> None:
        """Notice, once per order, that its birth-group stratum has outlived its group.

        Done on contact rather than by sweeping the tracked set at every group close, which
        would be a pass over the whole resting book for each of 4.26M groups.
        """
        if not tracked.outlived_birth_group and ctx.group_index != tracked.birth_group_index:
            tracked.outlived_birth_group = True
            self.counters["lifecycles_outliving_birth_group"] += 1
        if (
            not tracked.observed_in_another_phase
            and ctx.session_phase != tracked.birth_session_phase
        ):
            tracked.observed_in_another_phase = True
            self.counters["lifecycles_observed_in_another_phase"] += 1

    def _consume_pending(self, instrument_id: int, order_id: int, reduction: int) -> int:
        """Book a size reduction against quantity the tape already reported filled."""
        if reduction <= 0 or not order_id:
            return 0
        key = (instrument_id, order_id)
        pending = self._pending_fill.get(key, 0)
        if pending <= 0:
            return 0
        consumed = min(pending, reduction)
        remaining = pending - consumed
        if remaining:
            self._pending_fill[key] = remaining
        else:
            self._pending_fill.pop(key, None)
        return consumed

    # --- reading the book's own record -------------------------------------

    _WATCHED: Mapping[str, tuple[str, ...]] = {
        ADD: ("add_invalid_side", "tob_side_wipe", "duplicate_add_order_id"),
        MODIFY: ("modify_missing_treated_as_add",),
    }
    """Which of `ReplayBook.integrity`'s counters name a branch this adapter must react to.

    Reading the book's OWN counters is how the adapter learns which branch fired without
    re-implementing the branch conditions. Per action rather than a whole-Counter snapshot,
    because a dict copy per row across 4.26M groups is a cost with no reader.
    """

    @staticmethod
    def _watch(book: ReplayBook, action: str) -> dict[str, int]:
        return {name: book.integrity[name] for name in QueueGroupAdapter._WATCHED.get(action, ())}

    @staticmethod
    def _fired(book: ReplayBook, watched: Mapping[str, int]) -> dict[str, int]:
        return {name: book.integrity[name] - before for name, before in watched.items()}
