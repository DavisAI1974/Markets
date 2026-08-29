"""Differential tests: `ReplayBook` must MIRROR `InstrumentBook` on every book mutation.

`native_rt_book.ReplayBook` states that rule in its module docstring and then transcribes
`InstrumentBook` (`research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`) branch for
branch. Until this file existed the rule was ASSERTED and never MEASURED: not one test drove
`InstrumentBook` at all, so the two books could only be compared by reading them side by side,
and the next edit to the admission gate would re-open the hole with a green suite. That is
exactly the defect shape this tree keeps finding - S108 off-instrument, S109 `session_b_share`,
the 2026-08-29 `_family_id` split - where nothing raises and the numbers are simply not the
quantity they claim to be. Two books over one tape that disagree about one fact do not fail;
they just differ.

So these tests drive BOTH books with the same logical actions and compare FULL STATE after
EVERY record, not at the end. Comparing at the end would let a divergence open and close
again inside the run, which is precisely the intra-group lookahead `ReplayBook` exists to
prevent. Three things are compared:

* the resting-order map `{order_id: (side, price_raw, size)}`,
* both level maps `{side: {price_raw: [order_id, ...]}}` in FIFO order, and
* the touch on both sides (`best_price_raw` against `touch_price`).

The two streams that drive them - a hand-built one reaching every branch, and a seeded fuzz -
are WELL-FORMED by construction: a side in `{B, A}` on every mutating row, a non-negative
size, a price far below the sentinel, and a non-zero order id. Those two tests are the core
and never skip.

The anomalous rows get their own class, because `ReplayBook` is deliberately stricter than
`InstrumentBook` about what it will ACCEPT while identical about what it DOES with anything
both accept. What holds either way is the invariant `AnomalousRowTests` asserts: an anomalous
row is either REFUSED loudly (`RtBookError`) or MIRRORED exactly - never silently dropped.
A silent drop is the failure mode wearing a safety check's costume: the row changes the other
book, this one shrugs, and a `view` number moves with nothing raising. Written this way the
class measures the contract that is actually in force rather than the one that was planned,
so it survives the module deciding a given row belongs on the other side of that line.
"""
from __future__ import annotations

import random
import unittest
from collections import Counter
from dataclasses import dataclass, field

from research.kalshi.frankie_raw_mbo_benchmark import native_rt_book as rt
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import (
    F_TOB,
    UNDEF_PRICE,
    InstrumentBook,
    V4MboAdapter,
)

INSTRUMENT_ID = 4242
BOOK_SIDES = ("B", "A")

# Sane raw prices, both sides, well clear of the sentinel. Bids sit below asks so the touch
# comparison is reading a book shaped like a real one rather than a crossed accident.
BID_PRICES = (2_990_000_000, 2_995_000_000, 3_000_000_000)
ASK_PRICES = (3_005_000_000, 3_010_000_000, 3_015_000_000)
ALL_PRICES = BID_PRICES + ASK_PRICES

# Order ids for adds are drawn from this range and never reused: a duplicate add is an
# anomaly both books COUNT, so it belongs in the anomalous table below where the counter is
# part of the record, not scattered through a stream that is meant to be ordinary. Ids from
# NEVER_ISSUED_BASE drive the missing-reference paths - a cancel for an order that never
# rested, and a modify for one, which Databento's reference LOB treats as an add.
FIRST_ADD_ORDER_ID = 1_000
NEVER_ISSUED_BASE = 9_000_000


@dataclass(frozen=True)
class Action:
    """One logical tape action, emitted into BOTH book dialects from one set of fields.

    The point of a single source is that the two books provably receive the SAME event: if
    the test built the two shapes independently, a divergence could be the harness's own
    disagreement rather than the books'. Note the field-name split - `V4MboAdapter.normalize`
    reads "price", "ts_event" and "ts_recv", while the raw action rows `ReplayBook` consumes
    carry "price_raw", "ts_event_ns" and "ts_recv_ns".
    """

    action: str
    side: str
    order_id: int
    price_raw: int
    size: int
    flags: int = 0
    sequence: int = 0
    recv_ns: int = 0

    def rt_row(self) -> dict:
        return {
            "action": self.action,
            "side": self.side,
            "order_id": self.order_id,
            "price_raw": self.price_raw,
            "size": self.size,
            "flags": self.flags,
            "ts_recv_ns": self.recv_ns,
            "ts_event_ns": self.recv_ns - 10,
        }

    def v4_record(self) -> dict:
        # The two streams leave flags at 0: F_LAST would close an event group and pull the
        # whole frame projection in, which is not a book mutation. F_TOB is set only by the
        # anomalous cases, where the side wipe is the point.
        return {
            "instrument_id": INSTRUMENT_ID,
            "publisher_id": 1,
            "channel_id": 0,
            "action": self.action,
            "side": self.side,
            "order_id": self.order_id,
            "price": self.price_raw,
            "size": self.size,
            "flags": self.flags,
            "sequence": self.sequence,
            "ts_event": self.recv_ns - 10,
            "ts_recv": self.recv_ns,
            "ts_in_delta": 0,
        }

    def label(self) -> str:
        return (
            f"{self.action} side={self.side} id={self.order_id} "
            f"px={self.price_raw} sz={self.size} flags={self.flags}"
        )


def _v4_state(book: InstrumentBook) -> dict:
    """Full comparable state of the V4 book.

    `InstrumentBook.levels` is a defaultdict of lists and can in principle hold a level whose
    queue has emptied, so empty levels are dropped on BOTH sides before comparing - the
    question here is which orders rest where and in what order, not how each book spells
    "nothing". The touch is deliberately NOT filtered that way: `best_price_raw` reads the
    level dict without checking for empty queues while `touch_price` filters them, so this is
    the comparison that would catch a lingering empty level as the divergence it would be.
    """
    return {
        "orders": {
            int(oid): (order.side, int(order.price_raw), int(order.size))
            for oid, order in book.orders.items()
        },
        "levels": {
            side: {int(px): list(ids) for px, ids in book.levels[side].items() if ids}
            for side in BOOK_SIDES
        },
        "touch": {side: book.best_price_raw(side) for side in BOOK_SIDES},
    }


def _rt_state(book: rt.ReplayBook) -> dict:
    """Full comparable state of the replay book.

    `_orders` and `_levels` are read directly. The public accessors are used where they
    exist (`resting_at`, `touch_price`), but there is no public enumeration of the resting
    set or of level membership, and the property under test is STATE EQUALITY, not API
    surface: iterating the private maps is what makes "the two books hold the same thing"
    checkable at all. It is the comparison that is the deliverable, not the access path.
    """
    return {
        "orders": {int(oid): book.resting_at(oid) for oid in book._orders},
        "levels": {
            side: {int(px): list(ids) for px, ids in book._levels[side].items() if ids}
            for side in BOOK_SIDES
        },
        "touch": {side: book.touch_price(side) for side in BOOK_SIDES},
    }


@dataclass
class RunReport:
    """What one differential run measured. Counters exist so a no-op harness cannot pass."""

    records: int = 0
    divergences: list[str] = field(default_factory=list)
    divergence_count: int = 0
    max_resting_orders: int = 0
    level_map_changes: int = 0
    action_counts: Counter = field(default_factory=Counter)
    modifies_on_a_resting_order: int = 0
    modifies_on_a_missing_order: int = 0
    cancels_on_a_resting_order: int = 0
    cancels_on_a_missing_order: int = 0
    full_removals: int = 0


MAX_REPORTED_DIVERGENCES = 5


def run_differential(actions, replay_factory=rt.ReplayBook) -> RunReport:
    """Drive both books with the same actions, comparing full state after EVERY record.

    Divergences are collected rather than raised so the first one is reported with its record
    index and the run still completes; the caller asserts the list is empty. A divergence
    that opens and closes again would be invisible to an end-of-run comparison, and that
    transient is the whole reason this book exists.

    `replay_factory` exists only so `ComparatorTests` can drive a deliberately perturbed book
    through this same code path and prove the comparison is live.
    """
    replay = replay_factory()
    v4 = InstrumentBook(INSTRUMENT_ID)
    report = RunReport()
    previous_levels = None

    for index, act in enumerate(actions):
        if act.action in ("C", "M"):
            hit = replay.is_resting(act.order_id)
            if act.action == "M":
                report.modifies_on_a_resting_order += int(hit)
                report.modifies_on_a_missing_order += int(not hit)
            else:
                report.cancels_on_a_resting_order += int(hit)
                report.cancels_on_a_missing_order += int(not hit)
        resting_before = len(replay._orders)

        replay.apply(act.rt_row())
        v4.apply(V4MboAdapter.normalize(act.v4_record()))

        report.records += 1
        report.action_counts[act.action] += 1

        rt_state = _rt_state(replay)
        v4_state = _v4_state(v4)
        if rt_state != v4_state:
            report.divergence_count += 1
            if len(report.divergences) < MAX_REPORTED_DIVERGENCES:
                report.divergences.append(
                    f"record {index} [{act.label()}]\n"
                    f"  replay: {rt_state}\n"
                    f"  v4    : {v4_state}"
                )

        report.max_resting_orders = max(report.max_resting_orders, len(rt_state["orders"]))
        if len(rt_state["orders"]) < resting_before:
            report.full_removals += 1
        if previous_levels is not None and rt_state["levels"] != previous_levels:
            report.level_map_changes += 1
        previous_levels = rt_state["levels"]

    return report


# --- the hand-built stream ------------------------------------------------
#
# Every action in the feed's vocabulary, on both sides, with each documented modify branch
# reached at least once. Ids 1..9 are adds; 7 is only ever modified, so it enters the book
# through the missing-modify-treated-as-add path; 99 is only ever cancelled, so it never
# rests at all.
_B0, _B1, _B2 = BID_PRICES
_A0, _A1, _A2 = ASK_PRICES

HAND_BUILT_STREAM = [
    Action("A", "B", 1, _B0, 5),                 # first order at the bid touch
    Action("A", "B", 2, _B0, 7),                 # FIFO behind 1 at the same level
    Action("A", "B", 6, _B0, 2),                 # FIFO behind 2
    Action("A", "B", 3, _B1, 4),                 # a second bid level
    Action("A", "A", 4, _A0, 6),                 # the ask touch
    Action("A", "A", 5, _A1, 3),                 # a second ask level
    Action("F", "B", 1, _B0, 2),                 # a fill is not a book event in this feed
    Action("T", "N", 0, _B0, 2),                 # nor is a trade
    Action("N", "N", 0, _B0, 0),                 # nor is the tape declining to say
    Action("C", "B", 2, _B0, 3),                 # partial cancel: 7 -> 4, keeps FIFO position
    Action("C", "B", 2, _B0, 4),                 # the rest of it: order 2 leaves the level
    Action("M", "B", 1, _B0, 9),                 # size increase: priority lost, same level
    Action("M", "B", 1, _B0, 4),                 # size decrease: priority kept
    Action("M", "B", 1, _B1, 4),                 # price change: to the back of the new level
    Action("M", "A", 5, _A1, 0),                 # modify to zero removes the order
    Action("M", "B", 7, _B2, 8),                 # unknown order: treated as an add
    Action("M", "A", 7, _A2, 8),                 # side change: off the bid, onto the ask
    Action("C", "A", 4, _A0, 6),                 # the whole ask touch leaves; touch moves
    Action("A", "A", 8, _A0, 5),                 # and comes back
    Action("M", "A", 8, _A0, 5),                 # same price, same size: nothing moves
    Action("C", "B", 99, _B0, 1),                # cancel of an order that never rested
    Action("R", "N", 0, 0, 0),                   # reset clears both sides
    Action("A", "B", 9, _B0, 3),                 # the book is rebuildable after a reset
    Action("A", "A", 10, _A2, 6),
]


def _sequenced(actions):
    """Stamp monotone sequence numbers and receive times onto a list of actions."""
    return [
        Action(
            action=act.action,
            side=act.side,
            order_id=act.order_id,
            price_raw=act.price_raw,
            size=act.size,
            flags=act.flags,
            sequence=index + 1,
            recv_ns=1_700_000_000_000_000_000 + index * 1_000_000,
        )
        for index, act in enumerate(actions)
    ]


# --- the fuzz -------------------------------------------------------------

FUZZ_SEED = 20260829
FUZZ_RECORDS = 12_000

# Weighted so removals roughly keep pace with adds: an unbounded book would make each
# per-record state comparison quadratic in the run length without testing anything new.
_ACTION_WEIGHTS = (("A", 34), ("C", 24), ("M", 24), ("T", 8), ("F", 6), ("N", 3), ("R", 1))


def build_fuzz_actions(seed: int = FUZZ_SEED, count: int = FUZZ_RECORDS):
    """A deterministic stream of WELL-FORMED rows that frequently hits resting orders.

    Order ids for cancels and modifies are drawn mostly from the RECENTLY issued tail, which
    is what makes them land on orders that are still resting - a uniform draw over a growing
    id space degenerates into a stream of missing-reference no-ops that would compare equal
    for the wrong reason. The generator keeps its own issued-id ledger rather than reading
    either book, so it never has to agree with the thing under test to produce a valid row.
    """
    rng = random.Random(seed)
    actions = []
    kinds = [kind for kind, weight in _ACTION_WEIGHTS for _ in range(weight)]
    issued: list[int] = []
    next_add_id = FIRST_ADD_ORDER_ID
    next_unissued_id = NEVER_ISSUED_BASE

    for _ in range(count):
        kind = rng.choice(kinds)
        if kind == "A":
            order_id = next_add_id
            next_add_id += 1
            issued.append(order_id)
            side = rng.choice(BOOK_SIDES)
            price = rng.choice(BID_PRICES if side == "B" else ASK_PRICES)
            actions.append(Action("A", side, order_id, price, rng.randint(1, 40)))
        elif kind in ("C", "M"):
            draw = rng.random()
            if draw < 0.05 or not issued:
                # An id that has never been issued: a cancel of it is a structural no-op and a
                # modify of it is the reference LOB's treat-as-add. Reserved range, so a later
                # add can never collide with one of these and become a duplicate add.
                order_id = next_unissued_id
                next_unissued_id += 1
                issued.append(order_id)
            elif draw < 0.15:
                order_id = rng.choice(issued)
            else:
                order_id = rng.choice(issued[-60:])
            side = rng.choice(BOOK_SIDES)
            price = rng.choice(ALL_PRICES)
            if kind == "C":
                # Sizes span the add range so partial and full cancels both occur often.
                actions.append(Action("C", side, order_id, price, rng.randint(1, 55)))
            else:
                # Zero is reachable and well-formed: it is the documented modify-to-zero
                # removal, and both books are supposed to treat it identically.
                size = 0 if rng.random() < 0.06 else rng.randint(1, 40)
                actions.append(Action("M", side, order_id, price, size))
        elif kind == "R":
            actions.append(Action("R", "N", 0, 0, 0))
        else:
            order_id = rng.choice(issued) if issued else 0
            side = rng.choice(BOOK_SIDES + ("N",))
            actions.append(Action(kind, side, order_id, rng.choice(ALL_PRICES), rng.randint(0, 20)))

    return _sequenced(actions)


def _assert_agreement(case: unittest.TestCase, report: RunReport, what: str) -> None:
    if not report.divergences:
        return
    case.fail(
        f"{report.divergence_count} of {report.records} records diverged on {what}; "
        f"first {len(report.divergences)}:\n" + "\n".join(report.divergences)
    )


class HandBuiltStreamDifferentialTests(unittest.TestCase):
    def test_the_two_books_agree_on_full_state_after_every_hand_built_record(self) -> None:
        report = run_differential(_sequenced(HAND_BUILT_STREAM))
        self.assertEqual(report.records, len(HAND_BUILT_STREAM))
        _assert_agreement(self, report, "the hand-built stream")

    def test_the_hand_built_stream_reaches_every_action_in_the_feeds_vocabulary(self) -> None:
        # A differential over a stream that never reaches a branch proves nothing about it.
        reached = {act.action for act in HAND_BUILT_STREAM}
        self.assertEqual(reached, set(rt.VALID_ACTIONS))

    def test_the_hand_built_stream_mutates_the_book_rather_than_only_reading_it(self) -> None:
        report = run_differential(_sequenced(HAND_BUILT_STREAM))
        self.assertGreaterEqual(report.max_resting_orders, 5)
        self.assertGreaterEqual(report.level_map_changes, 10)
        self.assertGreaterEqual(report.full_removals, 4)


class FuzzDifferentialTests(unittest.TestCase):
    """One seeded run, driven once and asserted from two angles."""

    report: RunReport

    @classmethod
    def setUpClass(cls) -> None:
        cls.actions = build_fuzz_actions()
        cls.report = run_differential(cls.actions)

    def test_the_two_books_agree_on_full_state_after_every_fuzzed_record(self) -> None:
        self.assertEqual(self.report.records, FUZZ_RECORDS)
        _assert_agreement(self, self.report, f"the seeded fuzz (seed {FUZZ_SEED})")

    def test_the_fuzz_builds_a_real_book_rather_than_a_stream_of_no_ops(self) -> None:
        # Non-vacuity. A generator that emitted only misses, or only non-mutating actions,
        # would compare equal on every record while measuring nothing at all.
        self.assertGreaterEqual(self.report.max_resting_orders, 50)
        self.assertGreaterEqual(self.report.level_map_changes, 4_000)
        self.assertGreaterEqual(self.report.full_removals, 500)
        # Both halves of each reference-taking action: the ones that land on a resting order
        # (the interesting mutations) and the ones that do not (the missing-reference paths).
        self.assertGreaterEqual(self.report.modifies_on_a_resting_order, 600)
        self.assertGreaterEqual(self.report.modifies_on_a_missing_order, 600)
        self.assertGreaterEqual(self.report.cancels_on_a_resting_order, 600)
        self.assertGreaterEqual(self.report.cancels_on_a_missing_order, 600)
        for action in sorted(rt.VALID_ACTIONS):
            self.assertGreaterEqual(
                self.report.action_counts[action], 1, f"action {action} never generated"
            )
        self.assertGreaterEqual(self.report.action_counts["R"], 5)


# --- is the comparison live? ----------------------------------------------


class _PerturbedReplayBook:
    """A `ReplayBook` whose STATE READS are subtly wrong, in one named way at a time.

    A differential harness that compares nothing passes every run, quietly, forever - the
    same failure this whole file exists to close one level up. So the comparator is made to
    fail on demand. This wraps a real book and perturbs only what a read RETURNS, which keeps
    the perturbations independent of `ReplayBook`'s private method signatures: the point is to
    move one of the three compared quantities, not to model a plausible bug.
    """

    def __init__(self, perturbation: str) -> None:
        self._book = rt.ReplayBook()
        self._perturbation = perturbation

    def apply(self, row) -> None:
        self._book.apply(row)

    def is_resting(self, order_id) -> bool:
        return self._book.is_resting(order_id)

    @property
    def _orders(self):
        return self._book._orders

    @property
    def _levels(self):
        if self._perturbation == "reversed_fifo":
            return {
                side: {px: list(reversed(ids)) for px, ids in levels.items()}
                for side, levels in self._book._levels.items()
            }
        return self._book._levels

    def resting_at(self, order_id):
        found = self._book.resting_at(order_id)
        if found is not None and self._perturbation == "size_off_by_one":
            return (found[0], found[1], found[2] + 1)
        return found

    def touch_price(self, side):
        if self._perturbation == "same_extreme_on_both_sides":
            prices = [price for price, ids in self._book._levels[side].items() if ids]
            return max(prices) if prices else None
        return self._book.touch_price(side)


class ComparatorTests(unittest.TestCase):
    def test_each_compared_quantity_is_one_the_harness_can_actually_fail_on(self) -> None:
        # One perturbation per compared quantity: the resting-order map, FIFO order within a
        # level, and the touch. If any of these still reports zero divergences, that quantity
        # is not being compared and the corresponding half of the differential is decorative.
        for perturbation in ("size_off_by_one", "reversed_fifo", "same_extreme_on_both_sides"):
            with self.subTest(perturbation=perturbation):
                report = run_differential(
                    _sequenced(HAND_BUILT_STREAM),
                    replay_factory=lambda p=perturbation: _PerturbedReplayBook(p),
                )
                self.assertGreater(
                    report.divergence_count,
                    0,
                    f"perturbing {perturbation} changed nothing the harness looks at",
                )


# --- anomalous rows -------------------------------------------------------
#
# Rows the two books could plausibly treat differently. `ReplayBook` may REFUSE any of these
# (it is allowed to be stricter about what it ACCEPTS), but if it accepts one it must land in
# exactly the state `InstrumentBook` lands in. The third possibility - accept the row, mutate
# nothing, raise nothing - is the one that is never acceptable, and it is the only one this
# table can catch, because it is the one that leaves no trace anywhere else.

PRELOAD = [
    Action("A", "B", 501, _B0, 5),
    Action("A", "B", 502, _B0, 7),
    Action("A", "B", 503, _B1, 4),
    Action("A", "A", 504, _A0, 6),
    Action("A", "A", 505, _A1, 3),
]

ANOMALOUS_CASES = (
    (
        "an add with order id 0",
        Action("A", "B", 0, _B0, 5),
        "normalize coerces a missing id to 0 and _add_order rests it as a real order",
    ),
    (
        "a cancel with order id 0",
        Action("C", "B", 0, _B0, 5),
        "_cancel counts cancel_missing_order unless something rests under id 0",
    ),
    (
        "a modify with order id 0",
        Action("M", "B", 0, _B0, 5),
        "_modify treats it as an add under id 0",
    ),
    (
        "an add at the sentinel price",
        Action("A", "B", 601, UNDEF_PRICE, 5),
        "_add_order rests it and best_price_raw then reports the sentinel as the touch",
    ),
    (
        "a modify to the sentinel price",
        Action("M", "B", 501, UNDEF_PRICE, 5),
        "_modify moves the resting order to the sentinel price",
    ),
    (
        "a modify of an unknown order to the sentinel price",
        Action("M", "A", 602, UNDEF_PRICE, 5),
        "_modify treats the missing reference as an add, at the sentinel price",
    ),
    (
        "the F_TOB sentinel wipe",
        Action("A", "B", 603, UNDEF_PRICE, 5, flags=F_TOB),
        "_book_effect drops EVERY resting order on that side",
    ),
    (
        "a duplicate add of a resting order id",
        Action("A", "A", 501, _A2, 9),
        "_add_order counts duplicate_add_order_id and rests the new order in place of the old",
    ),
    (
        "an add with side N",
        Action("A", "N", 604, _B0, 5),
        "_book_effect counts add_invalid_side and mutates nothing",
    ),
    (
        "a modify with side N",
        Action("M", "N", 501, _B0, 5),
        "_modify calls _add_order with no side check and dies on levels['N']",
    ),
)


class AnomalousRowTests(unittest.TestCase):
    """One row at a time, onto a pre-loaded book, from the same start state each time."""

    def _loaded_pair(self):
        replay = rt.ReplayBook()
        v4 = InstrumentBook(INSTRUMENT_ID)
        for act in _sequenced(PRELOAD):
            replay.apply(act.rt_row())
            v4.apply(V4MboAdapter.normalize(act.v4_record()))
        self.assertEqual(_rt_state(replay), _v4_state(v4), "the pre-load itself diverged")
        return replay, v4

    def test_an_anomalous_row_is_refused_loudly_or_mirrored_exactly_never_dropped(self) -> None:
        for name, act, instrument_book_does in ANOMALOUS_CASES:
            with self.subTest(case=name):
                replay, v4 = self._loaded_pair()
                stamped = _sequenced(PRELOAD + [act])[-1]
                try:
                    replay.apply(stamped.rt_row())
                except rt.RtBookError:
                    # Refusing is allowed: this book may be stricter about what it ACCEPTS.
                    # What it may not do is accept and then quietly not act.
                    continue
                v4.apply(V4MboAdapter.normalize(stamped.v4_record()))
                self.assertEqual(
                    _rt_state(replay),
                    _v4_state(v4),
                    f"{name} was accepted but not mirrored; InstrumentBook {instrument_book_does}",
                )

    def test_a_row_that_stops_one_book_stops_the_other(self) -> None:
        # The complement of the test above. A row this book refuses while InstrumentBook
        # carries on is a divergence too - one replay aborts, the other produces numbers - so
        # a refusal has to be justified by the other book also being unable to proceed. The
        # exception is the DECLARED one: a negative size, which InstrumentBook silently
        # clamps to zero and this book refuses (pinned in tests/test_native_rt_book.py).
        for name, act, _does in ANOMALOUS_CASES:
            with self.subTest(case=name):
                replay, v4 = self._loaded_pair()
                stamped = _sequenced(PRELOAD + [act])[-1]
                try:
                    replay.apply(stamped.rt_row())
                except rt.RtBookError:
                    with self.assertRaises((KeyError, ValueError), msg=name):
                        v4.apply(V4MboAdapter.normalize(stamped.v4_record()))


if __name__ == "__main__":
    unittest.main()
