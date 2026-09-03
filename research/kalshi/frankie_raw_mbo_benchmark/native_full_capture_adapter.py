"""Keep everything the V4 adapter computes and then throws away, without editing it.

**Why a wrapper and not a patch.** `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`
is HASH-LOCKED: `test_checked_in_finalizer_lock_pins_every_executable_byte` and the October
full-stack workflow's supply-chain tests pin its bytes, and other pipelines' provenance rests
on that hash. Editing it to restore the drops broke six of those locks in one commit. So the
locked file stays byte-identical and this subclass keeps what it discards. That is not a
compromise on D60 - nothing is left out - it is the only form of the fix that does not
invalidate a prior run's provenance to improve this one.

**What was being dropped, all of it computed on every record and then discarded.**

* **The per-record `ApplyEffect`.** `V4MboAdapter.apply` binds it to `_`, so no per-record book
  effect reached the traversal at all. It is the only place the book says what a record
  actually DID rather than what it said: `top_before_price_raw` is the prevailing touch
  IMMEDIATELY BEFORE the record - the reference every "did this lift the offer" question needs
  - and `removed` says whether the record killed a resting order outright. Both had zero
  readers anywhere in the repo. For a cancel or a modify the effect's `side` and `price_raw`
  are the RESTING order's as the book knows them, not the message's, so a cancel whose message
  disagrees with the book is visible only here.
* **The reconstructed FIFO queue.** Every frame asserted `fifo_priority_reconstructed: True`
  while asking `book_snapshot` for `include_order_ids=False`, so it carried none of the
  reconstruction - and the FIFO queue is surface #1 in the adapter's own docstring. With ids
  on, each level carries every resting order's id, size, `volume_ahead` and priority age.
* **Everything below the top ten levels**, via `include_full_depth=False`. Total depth and
  level count survived as aggregates; the shape of the far book did not.
* **Per-side event COUNTS** (`action_side_count`), maintained in all five rolling windows with
  full add/remove bookkeeping and published by none. Quantity is not count: a `C_B` of 500 is
  one 500-lot pull or five hundred one-lots, which are opposite microstructure.
* **Top-of-book touch quantity for `T`, `F` and `M`.** `top_qty` accumulates for every action
  and `snapshot()` published only `A` and `C`, so aggressive trade quantity transacting at the
  prevailing touch was computed and dropped.
* **`ordered`**, the flag saying a rolling window saw out-of-order receive times and silently
  repaired itself.
* **Anomaly MAGNITUDES the book knows at the instant and does not keep**: the quantity an
  over-cancel swallows past the clamp, the depth and order count destroyed by an `R` clear or
  an `F_TOB` side wipe, and forward SEQUENCE GAPS - only backwards regressions were counted,
  while a forward jump is the standard signature of dropped packets on a CME channel and so
  the standard reason to distrust a reconstructed book.
* **Which group an integrity increment belongs to.** The cumulative counter says "this has now
  happened 47 times" and never says where; the per-group delta attributes it.

Nothing here recomputes anything the book already knows - every value is read off the book at
the instant it is true, which is the only point at which most of these exist.

**S122 slice (b), D83: activity is measured from EVENT ANCHORS, and the fixed-seconds blocks
leave the published frame.** Greg, verbatim: *"hardcoded windows we do not want these! ...
There should be zero hard coded time intervals for anything."* The locked adapter's
`ACTIVITY_WINDOWS_S = (1, 5, 20, 60, 300)` reached every member row as `activity` (twelve
quantities per fixed window) and, through this wrapper, as `activity_full` (three more per
fixed window). Both are RETIRED from the published frame (`RETIRED_FIXED_INTERVAL_FRAME_KEYS`)
on Greg's own instruction, which is the discussion D60 requires; the locked file keeps
computing its windows internally, unedited (D61), and `mbo_resume_state` keeps snapshotting
its `activity` deque because that state belongs to the locked file.

What replaces them is `activity_since`: the SAME fifteen quantities (the locked snapshot's
twelve plus the three this wrapper restored) accumulated over the causal prefix since a
named EVENT, published at the group's F_LAST cutoff, one window per anchor
(`ACTIVITY_ANCHORS`):

* `last_trade` - since the last `T` record, any side; resets when a `T` is applied;
  EXCLUSIVE of the anchor record, whose identity is recorded.
* `last_touch_change` - since the last record after which the best bid or best ask price
  differed from before it (`InstrumentBook.best_price_raw`, the same fact the locked
  `_book_effect` reads as `top_before_price_raw`); exclusive.
* `last_book_reset` - since the last `R` clear, `F_SNAPSHOT`-flagged record, or `F_TOB`
  side wipe; exclusive - after a clear the window starts from what the book was rebuilt from.
* `session_open` - since the 17:00 CT reopen that starts the record's CME trade date
  (`native_session.session_open_ns(trade_day(ts_event_ns))`, the rule `ExchangeSessionRule`
  keys segments on); INCLUSIVE of everything at or after the reopen; basis EXCHANGE_CALENDAR
  and exact after a resume, because it is a calendar fact.
* `last_f_last_same_side` - since the previous F_LAST-closed group whose side orientation
  (`B`, `A`, `N` or `MIXED`, the driver's `_side` rule) equals this group's; one accumulator
  per side key, published for THIS group's side at its close, then reset; exclusive of the
  anchor group.

Every window carries its anchor (`anchor_recv_ns`, `anchor_event_ns`, `anchor_sequence`),
the elapsed time on BOTH clocks (`elapsed_recv_ns`, `elapsed_event_ns` - reported as measured
and never clamped: event time is not monotone in receive order on real MBO, so a negative
value is a fact about the feed), `groups_since_anchor` and `records_since_anchor` (so "over
the last N groups" needs no chosen N - the tape supplies it), and `anchor_basis`. Snapshot
records are excluded from the counts exactly as the locked windows exclude them (they are
book state, not activity) while still resetting `last_book_reset`. On resume the four record
anchors are declared UNKNOWN_SINCE_RESUME with accumulation from the resume instant rather
than a fabricated anchor appearing only on the resume path.

Design note for the clocks: the Step-1 two-day module measures every event on the receive
clock of the record that made it knowable (`event_known_by_ts_recv_ns`); an anchor here is
such a record, and the window's cutoff is the group's F_LAST receive. Design reused; no
Step-1 value copied.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import timedelta
from typing import Any

from research.kalshi.frankie_raw_mbo_benchmark import native_session
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import (
    F_TOB,
    UNDEF_PRICE,
    InstrumentBook,
    V4MboAdapter,
    _ratio,
)

__all__ = [
    "ACTIVITY_ANCHORS",
    "ACTIVITY_SINCE_DECLARATION",
    "ANCHOR_BASIS_EXCHANGE_CALENDAR",
    "ANCHOR_BASIS_NOT_YET_OBSERVED",
    "ANCHOR_BASIS_OBSERVED",
    "ANCHOR_BASIS_UNKNOWN_SINCE_RESUME",
    "RETIRED_FIXED_INTERVAL_FRAME_KEYS",
    "AnchoredActivity",
    "FullCaptureAdapter",
]

RETIRED_FIXED_INTERVAL_FRAME_KEYS: tuple[str, ...] = ("activity", "activity_full")
"""The two fixed-seconds blocks that no longer reach the published frame (D83). `activity`
is popped from the locked adapter's frame in `_enrich`; `activity_full` is no longer built."""

LAST_TRADE = "last_trade"
LAST_TOUCH_CHANGE = "last_touch_change"
LAST_BOOK_RESET = "last_book_reset"
SESSION_OPEN = "session_open"
LAST_F_LAST_SAME_SIDE = "last_f_last_same_side"
ACTIVITY_ANCHORS: tuple[str, ...] = (
    LAST_TRADE, LAST_TOUCH_CHANGE, LAST_BOOK_RESET, SESSION_OPEN, LAST_F_LAST_SAME_SIDE,
)
RECORD_ANCHORS: tuple[str, ...] = (LAST_TRADE, LAST_TOUCH_CHANGE, LAST_BOOK_RESET)
"""The anchors that are a RECORD (exclusive of it). `session_open` is a calendar instant
(inclusive) and `last_f_last_same_side` a GROUP (exclusive of it)."""

ANCHOR_BASIS_OBSERVED = "OBSERVED"
ANCHOR_BASIS_NOT_YET_OBSERVED = "NOT_YET_OBSERVED_IN_THIS_RUN"
ANCHOR_BASIS_UNKNOWN_SINCE_RESUME = "UNKNOWN_SINCE_RESUME"
ANCHOR_BASIS_EXCHANGE_CALENDAR = "EXCHANGE_CALENDAR"

SIDE_KEYS: tuple[str, ...] = ("B", "A", "N", "MIXED")
"""The driver's `_side` rule: one side across the group's records, else MIXED."""

ACTIVITY_SINCE_DECLARATION: dict[str, Any] = {
    "rule": (
        "activity is accumulated over the causal prefix since a named EVENT and published at "
        "the group's F_LAST cutoff on ts_recv_ns; there is no fixed-seconds window (D83)"
    ),
    "anchors": {
        LAST_TRADE: "the last T record, any side; exclusive of the anchor record",
        LAST_TOUCH_CHANGE: (
            "the last record after which the best bid or best ask price differed from before "
            "it (InstrumentBook.best_price_raw); exclusive"
        ),
        LAST_BOOK_RESET: "the last R clear, F_SNAPSHOT-flagged record or F_TOB side wipe; exclusive",
        SESSION_OPEN: (
            "the 17:00 CT reopen that starts the record's CME trade date "
            "(native_session.session_open_ns); inclusive; exact after a resume"
        ),
        LAST_F_LAST_SAME_SIDE: (
            "the previous F_LAST-closed group with this group's side orientation (B, A, N or "
            "MIXED); one accumulator per side key; exclusive of the anchor group"
        ),
    },
    "no_fixed_n": (
        "every window carries groups_since_anchor and records_since_anchor, so 'over the "
        "last N groups' is read off the tape rather than chosen"
    ),
    "snapshot_records_excluded": (
        "F_SNAPSHOT records are book state, not activity, and are excluded from every count "
        "exactly as the locked adapter's windows exclude them; they still reset last_book_reset"
    ),
    "elapsed_event_ns": "reported as measured, never clamped; event time is not monotone in receive order",
    "resume": (
        "the four record/group anchors are declared UNKNOWN_SINCE_RESUME with accumulation "
        "from the resume instant; session_open is recovered exactly from the calendar"
    ),
    "retired_fixed_interval_frame_keys": list(RETIRED_FIXED_INTERVAL_FRAME_KEYS),
}
"""Static prose, declared ONCE and rendered into the traversal summary, never per row."""


class AnchoredActivity:
    """The locked `_RollingActivityWindow` vocabulary accumulated since one anchor EVENT.

    Same twelve published quantities as `_RollingActivityWindow.snapshot` (the formulas are
    the locked file's, reused by import of `_ratio`), plus the three that file maintained and
    withheld (`action_side_count`, `top_level_qty_by_action`, `receive_order_clean`), plus
    the anchor's identity and the elapsed time on both clocks. Nothing expires: the window
    is reset by its anchor event and by nothing else.
    """

    __slots__ = (
        "anchor_recv_ns", "anchor_event_ns", "anchor_sequence", "anchor_basis",
        "event_count", "records", "groups", "action_count", "action_side_count",
        "action_qty", "action_side_qty", "top_qty", "priority_lost", "missing_refs",
        "ordered", "last_recv_ns", "anchor_closes_its_group",
    )

    def __init__(self, *, basis: str = ANCHOR_BASIS_NOT_YET_OBSERVED) -> None:
        self.anchor_recv_ns: int | None = None
        self.anchor_event_ns: int | None = None
        self.anchor_sequence: int | None = None
        self.anchor_basis = basis
        self.event_count = 0
        self.records = 0
        self.groups = 0
        self.action_count: dict[str, int] = {}
        self.action_side_count: dict[str, int] = {}
        self.action_qty: dict[str, int] = {}
        self.action_side_qty: dict[str, int] = {}
        self.top_qty: dict[str, int] = {}
        self.priority_lost = 0
        self.missing_refs = 0
        self.ordered = True
        self.last_recv_ns: int | None = None
        self.anchor_closes_its_group = False

    def reset(
        self,
        *,
        recv_ns: int | None,
        event_ns: int | None,
        sequence: int | None,
        basis: str,
        anchor_closes_its_group: bool = False,
    ) -> None:
        """A new anchor. The window starts EMPTY - exclusive of the anchor record.

        `anchor_closes_its_group`: the anchor record is itself its group's F_LAST, so the
        group close that follows is the SAME instant as the anchor and is not a close since
        it - the window reads 0 groups, 0 records, 0 elapsed at that publication.
        """
        self.__init__(basis=basis)
        self.anchor_recv_ns = recv_ns
        self.anchor_event_ns = event_ns
        self.anchor_sequence = sequence
        self.anchor_closes_its_group = anchor_closes_its_group

    def note_record(self) -> None:
        self.records += 1

    def note_group_close(self) -> None:
        if self.anchor_closes_its_group:
            self.anchor_closes_its_group = False
            return
        self.groups += 1

    def append(self, row: dict[str, Any]) -> None:
        """One non-snapshot record, in the locked file's own row vocabulary."""
        recv_ns = int(row["ts_recv_ns"])
        if self.last_recv_ns is not None and recv_ns < self.last_recv_ns:
            self.ordered = False
        self.last_recv_ns = recv_ns
        action = str(row["action"])
        action_side = f"{action}_{row['side']}"
        size = max(0, int(row["size"]))
        self.event_count += 1
        self.action_count[action] = self.action_count.get(action, 0) + 1
        self.action_side_count[action_side] = self.action_side_count.get(action_side, 0) + 1
        self.action_qty[action] = self.action_qty.get(action, 0) + size
        self.action_side_qty[action_side] = self.action_side_qty.get(action_side, 0) + size
        if row["top_touch"]:
            self.top_qty[action] = self.top_qty.get(action, 0) + size
        self.priority_lost += int(bool(row["priority_lost"]))
        self.missing_refs += int(bool(row["missing_reference"]))

    def snapshot(self, *, now_recv_ns: int, now_event_ns: int) -> dict[str, Any]:
        trade_buy = self.action_side_qty.get("T_B", 0)
        trade_sell = self.action_side_qty.get("T_A", 0)
        add_qty = self.action_qty.get("A", 0)
        cancel_qty = self.action_qty.get("C", 0)
        return {
            "anchor_basis": self.anchor_basis,
            "anchor_recv_ns": self.anchor_recv_ns,
            "anchor_event_ns": self.anchor_event_ns,
            "anchor_sequence": self.anchor_sequence,
            "elapsed_recv_ns": (
                None if self.anchor_recv_ns is None else now_recv_ns - self.anchor_recv_ns
            ),
            "elapsed_event_ns": (
                None if self.anchor_event_ns is None else now_event_ns - self.anchor_event_ns
            ),
            "groups_since_anchor": self.groups,
            "records_since_anchor": self.records,
            # The locked snapshot's twelve, by the locked file's formulas.
            "event_count": self.event_count,
            "action_count": dict(self.action_count),
            "action_qty": dict(self.action_qty),
            "action_side_qty": dict(self.action_side_qty),
            "trade_buy_aggressor_qty": trade_buy,
            "trade_sell_aggressor_qty": trade_sell,
            "trade_aggressor_imbalance": _ratio(trade_buy - trade_sell, trade_buy + trade_sell),
            "add_cancel_churn": _ratio(cancel_qty, add_qty + cancel_qty),
            "top_level_add_qty_derived": self.top_qty.get("A", 0),
            "top_level_cancel_qty_derived": self.top_qty.get("C", 0),
            "priority_lost_modify_count": self.priority_lost,
            "missing_reference_count": self.missing_refs,
            # The three the locked file maintained and withheld (D61).
            **FullCaptureAdapter._window_extras(self),
        }


class _ActivitySince:
    """One instrument's anchored windows. Owned by the wrapper, never by the locked book."""

    __slots__ = (
        "record_anchors", "session", "session_open_ns", "session_next_open_ns",
        "by_side", "sides_in_group",
    )

    def __init__(self, *, basis: str) -> None:
        self.record_anchors: dict[str, AnchoredActivity] = {
            name: AnchoredActivity(basis=basis) for name in RECORD_ANCHORS
        }
        self.session = AnchoredActivity(basis=ANCHOR_BASIS_EXCHANGE_CALENDAR)
        self.session_open_ns: int | None = None
        self.session_next_open_ns: int | None = None
        self.by_side: dict[str, AnchoredActivity] = {
            side: AnchoredActivity(basis=basis) for side in SIDE_KEYS
        }
        self.sides_in_group: set[str] = set()

    def all_windows(self) -> list[AnchoredActivity]:
        return [*self.record_anchors.values(), self.session, *self.by_side.values()]

    def roll_session(self, ts_event_ns: int) -> None:
        """Re-anchor `session_open` when a record's event time crosses the next reopen."""
        if self.session_next_open_ns is not None and ts_event_ns < self.session_next_open_ns:
            if self.session_open_ns is None or ts_event_ns >= self.session_open_ns:
                return
        day = native_session.trade_day(ts_event_ns)
        open_ns = native_session.session_open_ns(day)
        following = day + timedelta(days=1)
        while not native_session.is_trading_day(following):
            following += timedelta(days=1)
        self.session_next_open_ns = native_session.session_open_ns(following)
        if open_ns != self.session_open_ns:
            self.session_open_ns = open_ns
            self.session.reset(
                recv_ns=None, event_ns=open_ns, sequence=None,
                basis=ANCHOR_BASIS_EXCHANGE_CALENDAR,
            )


class FullCaptureAdapter(V4MboAdapter):
    """`V4MboAdapter`, minus the discarding. Same inputs, same outputs, more of them.

    Subclassed rather than reimplemented so `record_count`, `completed_event_group_count`,
    `books` and `assert_groups_closed` stay exactly what `mbo_resume_state` snapshots.
    """

    def __init__(self) -> None:
        super().__init__()
        self._effects: dict[int, list[dict[str, Any]]] = {}
        self._integrity_open: dict[int, dict[str, int]] = {}
        self._last_sequence: dict[int, int] = {}
        self._since: dict[int, _ActivitySince] = {}
        self._anchor_basis_at_start = ANCHOR_BASIS_NOT_YET_OBSERVED
        self.capture: Counter[str] = Counter()
        """Anomalies observed at the instant they were true. Never a substitute for the rows."""

    @classmethod
    def from_restored(cls, restored: V4MboAdapter) -> "FullCaptureAdapter":
        """Re-wrap an adapter rebuilt by `mbo_resume_state.restore_adapter_state`.

        That function returns a plain `V4MboAdapter`, so a resumed run would silently fall
        back to the dropping version and lose capture for the whole remainder - a drop that
        only appears on the resume path, which is exactly where nobody would look for it.
        The books are moved, not copied: they are the same objects the restore rebuilt.
        """
        adapter = cls()
        adapter.books = restored.books
        adapter.record_count = restored.record_count
        adapter.completed_event_group_count = restored.completed_event_group_count
        # Sequence continuity is per instrument and picks up from the restored books, so a
        # gap across the resume seam is not reported as if it were a feed gap.
        adapter._last_sequence = {
            iid: int(book.last_sequence)
            for iid, book in restored.books.items()
            if book.last_sequence is not None
        }
        # D83 / the honest resume form: the anchors are the wrapper's own state and are NOT
        # in the V1 resume schema, so a resumed run says it does not know where the last
        # trade, touch change, reset or same-side group was, and accumulates from here.
        # `session_open` is a calendar fact and is recovered exactly on the first record.
        adapter._anchor_basis_at_start = ANCHOR_BASIS_UNKNOWN_SINCE_RESUME
        return adapter

    # --- the one override --------------------------------------------------

    def apply(
        self,
        record: Any,
        raw_symbol: str | None = None,
        source_dbn_object: str | None = None,
        source_dbn_sha256: str | None = None,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        msg = self.normalize(record, raw_symbol, source_dbn_object, source_dbn_sha256)
        book = self.books.setdefault(msg.instrument_id, InstrumentBook(msg.instrument_id))
        iid = msg.instrument_id
        if not book.event_group:
            self._effects[iid] = []
            self._integrity_open[iid] = dict(book.integrity)

        observed = self._observe_before(book, msg, iid)
        since = self._since.get(iid)
        if since is None:
            since = self._since[iid] = _ActivitySince(basis=self._anchor_basis_at_start)
        touch_before = self._touch(book, msg)
        effect, frame, legacy_rows = book.apply(msg)
        self.record_count += 1
        self._effects[iid].append({**asdict(effect), **observed})
        self._observe_anchors(since, book, msg, effect, touch_before)
        if frame is None:
            return None, []
        self.completed_event_group_count += 1
        return self._enrich(book, frame, iid, msg, since), legacy_rows

    # --- the event anchors (D83) ---------------------------------------------

    @staticmethod
    def _touch(book: InstrumentBook, msg: Any) -> dict[str, int | None]:
        """The best price on every side this record can move, read off the book.

        Only A, C, M and R mutate resting orders in the locked book (T, F and N do not), so
        the read is confined to those, and to the record's own side except for a clear.
        """
        if msg.action == "R":
            return {"B": book.best_price_raw("B"), "A": book.best_price_raw("A")}
        if msg.action in ("A", "C", "M") and msg.side in ("B", "A"):
            return {msg.side: book.best_price_raw(msg.side)}
        return {}

    def _observe_anchors(
        self,
        since: _ActivitySince,
        book: InstrumentBook,
        msg: Any,
        effect: Any,
        touch_before: dict[str, int | None],
    ) -> None:
        since.roll_session(int(msg.ts_event_ns))
        since.sides_in_group.add(str(msg.side))
        # The record is activity SINCE every standing anchor (the calendar anchor inclusive),
        # and then, if it is itself an anchor event, that window restarts EXCLUSIVE of it.
        row = None
        if not msg.is_snapshot:
            row = {
                "ts_recv_ns": msg.ts_recv_ns,
                "action": msg.action,
                "side": msg.side,
                "size": msg.size,
                "priority_lost": effect.priority_lost,
                "missing_reference": effect.missing_reference,
                "top_touch": effect.touched_or_improved_top_before,
            }
        for window in since.all_windows():
            window.note_record()
            if row is not None:
                window.append(row)

        def anchor(name: str) -> None:
            since.record_anchors[name].reset(
                recv_ns=int(msg.ts_recv_ns), event_ns=int(msg.ts_event_ns),
                sequence=int(msg.sequence), basis=ANCHOR_BASIS_OBSERVED,
                anchor_closes_its_group=bool(msg.is_last),
            )

        if msg.action == "T":
            anchor(LAST_TRADE)
        if touch_before and any(
            touch_before[side] != book.best_price_raw(side) for side in touch_before
        ):
            anchor(LAST_TOUCH_CHANGE)
        if (
            msg.action == "R"
            or msg.is_snapshot
            or (msg.action == "A" and abs(msg.price_raw) >= UNDEF_PRICE and int(msg.flags) & F_TOB)
        ):
            anchor(LAST_BOOK_RESET)

    def _publish_activity_since(
        self, since: _ActivitySince, msg: Any
    ) -> dict[str, Any]:
        """At the group's F_LAST: every window at this cutoff, then the same-side reset."""
        now_recv = int(msg.ts_recv_ns)
        now_event = int(msg.ts_event_ns)
        sides = since.sides_in_group
        side = sides.pop() if len(sides) == 1 else "MIXED"
        since.sides_in_group = set()
        for window in since.all_windows():
            window.note_group_close()
        out: dict[str, Any] = {
            name: window.snapshot(now_recv_ns=now_recv, now_event_ns=now_event)
            for name, window in since.record_anchors.items()
        }
        out[SESSION_OPEN] = since.session.snapshot(now_recv_ns=now_recv, now_event_ns=now_event)
        same = since.by_side[side]
        out[LAST_F_LAST_SAME_SIDE] = {
            "side_orientation": side,
            **same.snapshot(now_recv_ns=now_recv, now_event_ns=now_event),
        }
        # This group is now the anchor for the next group of its side: exclusive of it.
        same.reset(
            recv_ns=now_recv, event_ns=now_event, sequence=int(msg.sequence),
            basis=ANCHOR_BASIS_OBSERVED,
        )
        return out

    # --- what only the pre-state knows -------------------------------------

    def _observe_before(self, book: InstrumentBook, msg: Any, iid: int) -> dict[str, Any]:
        """Read the anomalies that stop being true the moment the record is applied."""
        observed: dict[str, Any] = {}

        last = self._last_sequence.get(iid)
        if last is not None and not msg.is_snapshot:
            gap = int(msg.sequence) - last - 1
            if gap > 0:
                observed["sequence_gap_messages"] = gap
                self.capture["sequence_gap"] += 1
                self.capture["sequence_gap_messages"] += gap
        if not msg.is_snapshot:
            self._last_sequence[iid] = max(last or int(msg.sequence), int(msg.sequence))

        if msg.action == "C":
            resting = book.orders.get(msg.order_id)
            if resting is not None and max(0, msg.size) > resting.size:
                excess = max(0, msg.size) - resting.size
                observed["over_cancel_qty"] = excess
                self.capture["over_cancel"] += 1
                self.capture["over_cancel_qty"] += excess
        elif msg.action == "R":
            observed["cleared_orders"] = len(book.orders)
            observed["cleared_qty"] = sum(o.size for o in book.orders.values())
            self.capture["book_clear"] += 1
            self.capture["book_clear_orders_removed"] += observed["cleared_orders"]
            self.capture["book_clear_qty_removed"] += observed["cleared_qty"]
        elif (
            msg.action == "A"
            and abs(msg.price_raw) >= UNDEF_PRICE
            and int(msg.flags) & F_TOB
        ):
            wiped = [o for o in book.orders.values() if o.side == msg.side]
            observed["tob_wiped_orders"] = len(wiped)
            observed["tob_wiped_qty"] = sum(o.size for o in wiped)
            self.capture["tob_side_wipe"] += 1
            self.capture["tob_side_wipe_orders_removed"] += observed["tob_wiped_orders"]
            self.capture["tob_side_wipe_qty_removed"] += observed["tob_wiped_qty"]
        return observed

    # --- what the frame was not asking for ---------------------------------

    def _enrich(
        self,
        book: InstrumentBook,
        frame: dict[str, Any],
        iid: int,
        msg: Any,
        since: _ActivitySince,
    ) -> dict[str, Any]:
        now_ns = int(msg.ts_recv_ns)
        effects = self._effects.get(iid, [])
        actions = frame.get("raw_actions", [])
        # Parallel by construction - one effect appended per record, both reset together at
        # group open - so the zip is defensive, and a length mismatch is worth seeing.
        if len(effects) == len(actions):
            frame["raw_actions"] = [
                {**action, "book_effect": effect} for action, effect in zip(actions, effects)
            ]
        else:
            self.capture["effect_action_length_mismatch"] += 1
            frame["book_effects"] = list(effects)

        frame["book_full"] = book.book_snapshot(
            now_ns, depth_levels=10, include_full_depth=True, include_order_ids=True
        )
        # D83: the locked adapter's fixed-seconds `activity` block leaves the published frame,
        # and the fixed-window `activity_full` is no longer built. The same vocabulary rides
        # on event anchors instead.
        for retired in RETIRED_FIXED_INTERVAL_FRAME_KEYS:
            frame.pop(retired, None)
        frame["activity_since"] = self._publish_activity_since(since, msg)
        opened = self._integrity_open.get(iid, {})
        frame["integrity_delta"] = {
            key: value - opened.get(key, 0)
            for key, value in book.integrity.items()
            if value - opened.get(key, 0)
        }
        frame["capture_observations"] = dict(self.capture)
        self._effects[iid] = []
        return frame

    @staticmethod
    def _window_extras(window: AnchoredActivity) -> dict[str, Any]:
        """The three quantities `_RollingActivityWindow.snapshot` maintains and withholds,
        read off an event-anchored window (D83) where they were read off a fixed one."""
        return {
            "action_side_count": dict(window.action_side_count),
            "top_level_qty_by_action": dict(window.top_qty),
            "receive_order_clean": bool(window.ordered),
        }
