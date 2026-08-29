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
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Any

from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import (
    ACTIVITY_WINDOWS_S,
    F_TOB,
    UNDEF_PRICE,
    InstrumentBook,
    V4MboAdapter,
)

__all__ = ["FullCaptureAdapter"]


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
        effect, frame, legacy_rows = book.apply(msg)
        self.record_count += 1
        self._effects[iid].append({**asdict(effect), **observed})
        if frame is None:
            return None, []
        self.completed_event_group_count += 1
        return self._enrich(book, frame, iid, msg.ts_recv_ns), legacy_rows

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
        self, book: InstrumentBook, frame: dict[str, Any], iid: int, now_ns: int
    ) -> dict[str, Any]:
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
        frame["activity_full"] = {
            str(seconds): self._window_extras(book, seconds) for seconds in ACTIVITY_WINDOWS_S
        }
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
    def _window_extras(book: InstrumentBook, seconds: int) -> dict[str, Any]:
        """The three quantities `_RollingActivityWindow.snapshot` maintains and withholds."""
        window = book._activity_windows[seconds]  # noqa: SLF001 - see the module docstring
        return {
            "action_side_count": dict(window.action_side_count),
            "top_level_qty_by_action": dict(window.top_qty),
            "receive_order_clean": bool(window.ordered),
        }
