"""Section 4.7's OBSERVATION half: what tells `ReplenishmentCalculator` a level moved.

`ReplenishmentCalculator` is the horizon half and it was already wired - `native_replay_driver`
calls `run.replenishment.advance(recv_ns)` at every group close and retains what matures. But
nothing ever called `open_episode`, `add_refill` or `restore_touch`, so the section matured an
empty pending set forever: every gate passed, every stratum was well formed, and the ingest
count was zero. That is the same shape as the 4.8/4.9/4.13/4.14 finding of 2026-08-29
(`native_group_adapters` imported by its own test alone), and the only cure is a call site.

**The unit is the level, not the group.** 4.6-4.16 take the F_LAST group as the candidate unit
(D53), and this module is fed one group at a time, but 4.7's own unit is an EPISODE: "following
an identified removal/contact", measured at one price on one side. A group can open several
episodes, or none, and a refill in a later group answers an episode opened in an earlier one.
So the group is the unit of DELIVERY here while the level is the unit of MEASUREMENT - the same
split `native_group_adapters` records for 4.13, where the group is observed and the depth
accumulates in the graph.

**Every reading is taken around ONE action, from `ReplayBook`.** A level's depth is read
immediately before a row is applied and immediately after, and the difference IS the removal or
the refill. Reading the group's book at F_LAST instead would report each level as it stood after
the group's own later actions - the intra-group lookahead `native_rt_book` exists to prevent -
and a removal measured that way is present, typed, in range and not the quantity it claims.

**THE ONE DECLARED CHOICE: the tick neighbourhood is ONE TICK, and it travels on the value.**
4.7 asks for "refills at the same price" and "refills at neighboring prices" and never says how
wide a neighbourhood is. Nothing was invented for it:

* `research/ng_dipole_runway_audit.py` already commits `TICK = 0.001`, the NG exchange minimum
  price increment in decimal dollars.
* `research/ng_exhaustion_mbo_v4_state_adapter_20260820.PRICE_SCALE = 1_000_000_000` is the
  scale `price_raw` is expressed in (`decimal_price(raw) = raw / PRICE_SCALE`).
* So one tick in `price_raw` units is `int(TICK * PRICE_SCALE)` = 1_000_000, which is
  `TICK_RAW_NG` below and is asserted against both sources rather than typed as a literal.

The WIDTH is one tick - the single adjacent level - for a reason this tree keeps rediscovering:
any wider number (two, three, five ticks) is a bar sited at a value, chosen by taste, and S111
measured that the healthiest bars are the ones that cannot be moved without changing what is
being asked. One tick is the smallest price distinction the venue permits, so it is the only
neighbourhood definable without a fitted width. A refill further away is NOT counted as a
neighbouring refill and is NOT silently ignored either: it is counted, with its quantity
retained, under `refill_with_no_pending_episode` - an add ten ticks away is a true fact about a
DIFFERENT level, so calling it replenishment of this one would be an invention, and calling it
"beyond the neighbourhood" would claim an episode exists further away, which `pending_at`'s
exact-price key cannot establish. `tick_raw`, `neighbourhood_ticks` and the composed `price_relation_basis` string are
emitted on EVERY observation, on the `ladder_scope` / `cancels_ahead_basis` / `view_with_basis`
precedent: a caveat that lives only in a docstring is a caveat that expires (S114).

**NEW-ID versus SAME-ID is decided on OBSERVED RESIDENCY, and never merged.** 4.7 requires new
liquidity and reshaped residual orders be distinguished, and the calculator holds them in two
separate pairs of fields that its own summary refuses to sum. The test here is whether the row's
`order_id` was RESTING IN THE BOOK immediately before the row: resting means the residual was
reshaped (`SAME_ID_MODIFY`), not resting means liquidity arrived (`NEW_ID_ADD`). That is not
merely the cheap test, it is the right one - an order that fully left the book and came back is
new liquidity, not a reshaped residual, and an ever-seen order-id set would say otherwise while
costing tens of millions of integers a day. Three residency bases are named rather than assumed,
and each travels on the value: an ordinary resident, an ordinary non-resident, and a `M` for an
order this book never had, which `InstrumentBook` treats as an add and which a window opening
mid-stream sees constantly.

**A row may NEVER restore its own removal.** A modify that walks an order from 3000 to 2999
depletes 3000 and populates 2999, one tick apart. Attributing that add to the episode the same
row just opened would report the level instantly restored when the liquidity in fact retreated -
a manufactured restoration, and the most plausible-looking wrong number this module could
produce. So within one row refills are attributed FIRST, against the episodes pending BEFORE the
row, and removals open their episodes AFTER. A refill in the NEXT row of the same group does
answer it, which is genuine.

**A refill is attributed to EVERY pending episode in its neighbourhood, and that is declared.**
Two removals at one level can both be pending when one add arrives; the alternative is a FIFO
allocation that fills the oldest episode first. FIFO was rejected on two grounds. It makes an
episode's answer depend on other episodes it has nothing to do with, when the calculator is
built per episode throughout (per-episode survival, per-episode ratio, per-episode overshoot);
and capping each episode at its own removed quantity would make OVERSHOOT - a measurand 4.7
names explicitly - unobservable. The cost is stated instead of hidden: episodes whose windows
overlap at one level SHARE a refill, so `neighborhood_arrival_quantity` SUMMED across overlapping episodes
exceeds the quantity that actually arrived. The episode is the unit 4.7 measures, not the sum,
and `shared_with_episode_count` is emitted on the observation so the overlap is countable rather
than inferred.

**NO LOOKAHEAD, and never-restored stays distinct from not-yet-observed.** Rows are consumed in
tape order and every timestamp handed to the calculator is the row's own `ts_recv_ns`. Nothing
here decides an outcome - the calculator's `advance` does that when stream time reaches the
horizon - so this module cannot know a restoration before it happens. A refill whose `recv_ns`
precedes its candidate episode's open (an out-of-order feed) is not attributed and not clamped
into range: it is counted as `refill_precedes_episode_open` with its quantity retained.

**Three row classes open no episode, each refused for a stated reason and counted, not dropped.**
D60 forbids a silent drop and allows only a row that is truly blank. (1) A removal at Databento's
undefined-price sentinel: the sentinel is the feed declining to state a price, and an episode
keyed on it could never be matched by any refill at a real price, so every one of them would
report NEVER_RESTORED - a manufactured result, not a measurement. (2) The normalized
top-of-book side wipe, which drops a whole side at once. (3) `R`, which clears the book. The last
two are book-state events rather than participant removals, and opening an episode per cleared
level would flood 4.7 with never-restored artifacts created at a single instant. All three keep
their counts and their quantities.

**What a wipe cleared is DERIVED, and says so.** `ReplayBook` exposes no level enumeration, so
the quantity a side wipe or a reset removes cannot be read out of it. Rather than reach into its
privates or stand up a second book, `InstrumentReplay` carries a per-side running total of the
depth deltas THIS MODULE OBSERVED - one integer per side, not a per-level structure - and reports
that at a wipe under `DERIVED_FROM_OBSERVED_LEVEL_DELTAS`. It is exact while the book starts
empty and every mutation passes through the diff, which is the case within a continuity segment,
and its basis is on the value so it can never be read as a book measurement.

**The row volume is stated, because it is large.** An episode opens on EVERY observed depletion
of displayed depth - the honest reading of "following an identified removal/contact" - so on real
tape this is one episode per cancel and per shrinking modify, and `observe_group` hands back one
exact row per level change. That is the same order as `legacy_rows`, which the traversal already
streams through `native_row_sink` rather than holding inline. The pending set itself stays
horizon-bounded, but only because the traversal keeps calling `advance`; nothing in the
observation half can bound it, since nothing here resolves an episode.

**No averaging anywhere.** Every quantity here is an integer count or an integer size. Nothing in
this module is a mean, a ratio, a rate or a share; the calculator owns the stratified measures
and this module hands it exact per-level facts.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_group_adapters import (
    PRICE_SENTINEL_ABS,
    GroupContext,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_replenishment import (
    NEIGHBORING_PRICE,
    NEW_LIQUIDITY,
    RESHAPED_RESIDUAL,
    SAME_PRICE,
    ReplenishmentCalculator,
    ReplenishmentEpisode,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_rt_book import ReplayBook
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import F_TOB, PRICE_SCALE

__all__ = [
    # the two entry points and the objects they exchange
    "GroupObservations",
    "InstrumentReplay",
    "LevelObservation",
    "ReplenishmentAdapterError",
    "ReplenishmentObserver",
    "level_observations",
    # the declared choices, exported because a consumer must be able to read them back
    "CLEARED_QUANTITY_BASIS",
    "NEIGHBOURHOOD_TICKS",
    "REFILL_ATTRIBUTION",
    "SELF_RESTORATION_POLICY",
    "TICK_DECIMAL_NG",
    "TICK_RAW_NG",
    # the vocabulary every emitted value is written in
    "AHEAD_OF_TOUCH",
    "AT_TOUCH",
    "BEHIND_TOUCH",
    "MODIFY_MISSING",
    "NOT_RESIDENT",
    "NO_PENDING_EPISODE_IN_NEIGHBOURHOOD",
    "PRICE_UNDEFINED",
    "REFILL",
    "REFUSED_RESET",
    "REFUSED_SENTINEL_PRICE",
    "REFUSED_TOB_WIPE",
    "REMOVAL",
    "RESIDENT",
    "TOUCH_ABSENT",
    "TOUCH_DISPLACED",
    "TOUCH_NEVER_DISPLACED",
    "TOUCH_REFERENCE_ABSENT",
    "UNIDENTIFIED",
]

ADD = "A"
CANCEL = "C"
MODIFY = "M"
RESET = "R"
BID, ASK = "B", "A"
BOOK_SIDES = (BID, ASK)

TICK_DECIMAL_NG = 0.001
"""NG's exchange minimum price increment, in decimal dollars.

Not invented here: `research/ng_dipole_runway_audit.py` commits the same `TICK = 0.001` and
builds its ZigZag reversal thresholds (3t/5t/8t/13t) on it. One source, one value.
"""

TICK_RAW_NG = 1_000_000
"""One tick in `price_raw` units: `TICK_DECIMAL_NG * PRICE_SCALE`.

Written as a literal AND checked against its two sources on import (below), because a literal
that silently disagrees with the scale it was derived from is exactly the class of defect this
tree keeps finding - present, typed, in range and wrong.
"""

if TICK_RAW_NG != round(TICK_DECIMAL_NG * PRICE_SCALE):
    raise AssertionError(
        "TICK_RAW_NG disagrees with TICK_DECIMAL_NG * PRICE_SCALE; one of the two sources moved"
    )

NEIGHBOURHOOD_TICKS = 1
"""How far from a removal's price a refill may sit and still be a NEIGHBORING refill.

ONE - the single adjacent level. See the module docstring: any wider number is a bar sited at a
value, and one tick is the smallest price distinction the venue permits.
"""

REMOVAL = "REMOVAL"
REFILL = "REFILL"
"""What a `LevelObservation` IS. A level's depth fell, or a level's depth rose."""

AT_TOUCH = "AT_TOUCH"
BEHIND_TOUCH = "BEHIND_TOUCH"
AHEAD_OF_TOUCH = "AHEAD_OF_TOUCH"
TOUCH_ABSENT = "TOUCH_ABSENT"
"""Where a level sat relative to its own side's touch, read BEFORE the row was applied.

`AHEAD_OF_TOUCH` is unreachable for a removal - a populated level cannot be better than the
touch - but a refill CAN land ahead of the touch that prevailed a moment earlier, and that is
the observation that improves the touch. `TOUCH_ABSENT` is a side with nothing resting on it,
which is a different fact from a level being far from the touch.
"""

RESIDENT = "ORDER_ID_RESTING_BEFORE_ROW"
NOT_RESIDENT = "ORDER_ID_NOT_RESTING_BEFORE_ROW"
MODIFY_MISSING = "MODIFY_WITH_NO_RESTING_ORDER_TREATED_AS_ADD"
UNIDENTIFIED = "ORDER_ID_ZERO_IDENTITY_UNAVAILABLE"
"""How a refill's NEW-ID / SAME-ID classification was reached. Travels on the value.

`UNIDENTIFIED` is `normalize`'s order id of 0, which `InstrumentBook` and `ReplayBook` both rest
as a real order. Every anonymous order therefore shares one key, so residency answers a question
about a slot rather than about an order. The quantity is still observed and still attributed -
dropping it would under-count replenishment - but the classification is flagged as not
load-bearing rather than presented as a finding.
"""

NO_PENDING_EPISODE_IN_NEIGHBOURHOOD = "NO_PENDING_EPISODE_IN_NEIGHBOURHOOD"
PRICE_UNDEFINED = "PRICE_UNDEFINED"
"""Why a refill was observed but attributed to no episode.

`NO_PENDING_EPISODE_IN_NEIGHBOURHOOD` is the ORDINARY case and is deliberately not called
"beyond the neighbourhood": most liquidity arriving in a tape answers no open episode at all,
and `pending_at` is keyed by exact price, so whether an episode exists FURTHER away than one
tick cannot be established through the calculator's public surface. Claiming it would be a
statement this module cannot support. Its quantity is counted under its own name, apart from
`refill_quantity_unattributed`, which is reserved for the two anomalies - an undefined price
and an out-of-order timestamp - so that counter stays a defect signal rather than a tally of
the whole tape's adds.
"""

TOUCH_NEVER_DISPLACED = "TOUCH_NEVER_DISPLACED"
TOUCH_DISPLACED = "TOUCH_DISPLACED"
TOUCH_REFERENCE_ABSENT = "TOUCH_REFERENCE_ABSENT"
"""What the removal did to its own side's touch, decided at the removal and never later.

The calculator reports `touch_restoration_ns = None` for a touch that was displaced and never
came back AND for a touch that never left, which are different facts. Neither can be fixed from
outside the calculator, so the disposition is emitted here on a row carrying the same
`episode_id` the calculator emits, and the two join on it.
"""

REFUSED_SENTINEL_PRICE = "REMOVAL_AT_UNDEFINED_PRICE"
REFUSED_TOB_WIPE = "NORMALIZED_TOP_OF_BOOK_SIDE_WIPE"
REFUSED_RESET = "BOOK_RESET"
"""Why a row that removed real depth opened no episode. Counted, with its quantity retained."""

REFILL_ATTRIBUTION = "EVERY_PENDING_EPISODE_IN_NEIGHBOURHOOD"
SELF_RESTORATION_POLICY = "REFUSED_WITHIN_THE_SAME_ROW"
CLEARED_QUANTITY_BASIS = "DERIVED_FROM_OBSERVED_LEVEL_DELTAS"
"""The three policies a consumer would otherwise have to infer. See the module docstring."""


class ReplenishmentAdapterError(ValueError):
    """A group could not be turned into section-4.7 level observations.

    `native_rt_book.RtBookError` is deliberately NOT wrapped in this. A malformed row is the
    book's diagnosis and re-labelling it here would hide which layer refused; both subclass
    `ValueError`, so a caller catching that catches either.
    """


def _int(row: Mapping[str, Any], key: str, default: int = 0) -> int:
    """Coerce one row field, and fail as `ReplenishmentAdapterError` rather than bare.

    `ReplayBook._as_int` does the same for its own reads and for the same reason: this module's
    error contract is one exception type, and a caller writing `except ReplenishmentAdapterError`
    would not catch a raw `int()` failure. The default mirrors `normalize`, which coerces an
    absent id to zero and an absent price to the sentinel.
    """
    value = row.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ReplenishmentAdapterError(f"{key} is not an integer: {value!r}") from exc


def _is_sentinel(price: int | None) -> bool:
    return price is not None and abs(price) >= PRICE_SENTINEL_ABS


def _require_actions(actions: Sequence[Mapping[str, Any]]) -> None:
    if not actions:
        raise ReplenishmentAdapterError("an F_LAST group must contain at least one native action")


def _tally(out: "GroupObservations", replay: "InstrumentReplay", side: str) -> int:
    """The side's derived displayed volume, reported as it stands and never clamped.

    A negative tally would mean this module missed a mutation the book applied, which is a
    defect signal worth surfacing. `max(0, ...)` would hide it behind a plausible zero - the
    exact shape `_size` refuses everywhere else in this tree.
    """
    volume = replay.displayed_volume[side]
    if volume < 0:
        out.integrity["displayed_volume_negative"] += 1
    return volume


def _touch_state(price: int, touch: int | None, side: str) -> str:
    """Where `price` sits relative to its own side's touch. Never averaged, never scored."""
    if touch is None or _is_sentinel(touch):
        return TOUCH_ABSENT
    if price == touch:
        return AT_TOUCH
    better = price > touch if side == BID else price < touch
    return AHEAD_OF_TOUCH if better else BEHIND_TOUCH


def _is_at_least_as_good(touch: int | None, reference: int, side: str) -> bool:
    """Has the touch come back to `reference` or better? Bid climbs, ask falls."""
    if touch is None or _is_sentinel(touch):
        return False
    return touch >= reference if side == BID else touch <= reference


@dataclass(frozen=True)
class LevelObservation:
    """One level's depth change, caused by exactly one raw action row.

    Frozen for the same reason `GroupContext` is: this is the fact a stratum key and an episode
    are built from, and a fact that can be edited after the row it labelled was written is not a
    fact. Every field is an integer, a string or None - nothing here is derived by division.
    """

    row_index: int
    kind: str
    action: str
    order_id: int
    instrument_id: int
    side: str
    price_raw: int
    quantity: int
    order_count_delta: int
    depth_before: int
    depth_after: int
    touch_price_before: int | None
    touch_price_after: int | None
    touch_state: str
    recv_ns: int
    price_is_sentinel: bool
    liquidity_kind: str | None
    liquidity_kind_basis: str | None
    group_index: int
    source_day: str
    source_role: str
    continuity_segment: int
    family_id: str
    session_phase: str
    tick_raw: int
    neighbourhood_ticks: int

    @property
    def price_relation_basis(self) -> str:
        """The declared neighbourhood, composed from the values actually used.

        Composed rather than stored so it cannot drift from `tick_raw` and
        `neighbourhood_ticks`: two names for one choice is how the `_family_id` split of
        2026-08-29 happened, where nothing failed and the strata were simply cut differently.
        """
        return (
            f"ADJACENT_LEVEL|tick_raw={self.tick_raw}"
            f"|neighbourhood_ticks={self.neighbourhood_ticks}"
        )

    def price_relation_to(self, episode_price_raw: int) -> tuple[str, int] | None:
        """`(SAME_PRICE|NEIGHBORING_PRICE, offset_in_ticks)`, or None when out of neighbourhood.

        The offset is SIGNED, measured as THIS REFILL relative to the episode's level, and kept
        even though the calculator holds one NEIGHBORING bucket: a refill one tick INSIDE the
        removed level and one tick BEHIND it are opposite facts about where liquidity went, and
        the sign is the only thing that separates them. Oriented refill-minus-episode rather
        than the reverse because the question 4.7 asks is where the liquidity CAME BACK, not
        where it left from.
        """
        if self.price_is_sentinel or _is_sentinel(episode_price_raw):
            return None
        delta = self.price_raw - episode_price_raw
        if delta % self.tick_raw:
            return None
        offset = delta // self.tick_raw
        if abs(offset) > self.neighbourhood_ticks:
            return None
        return (SAME_PRICE if offset == 0 else NEIGHBORING_PRICE, offset)

    def as_dict(self) -> dict[str, Any]:
        return {
            "section": "4.7",
            "observation": self.kind,
            "row_index": self.row_index,
            "action": self.action,
            "order_id": self.order_id,
            "instrument_id": self.instrument_id,
            "side": self.side,
            "price_raw": self.price_raw,
            "quantity": self.quantity,
            "order_count_delta": self.order_count_delta,
            "depth_before": self.depth_before,
            "depth_after": self.depth_after,
            "touch_price_before": self.touch_price_before,
            "touch_price_after": self.touch_price_after,
            "touch_state": self.touch_state,
            "recv_ns": self.recv_ns,
            "price_is_sentinel": self.price_is_sentinel,
            "liquidity_kind": self.liquidity_kind,
            "liquidity_kind_basis": self.liquidity_kind_basis,
            "group_index": self.group_index,
            "source_day": self.source_day,
            "source_role": self.source_role,
            "continuity_segment": self.continuity_segment,
            "family_id": self.family_id,
            "session_phase": self.session_phase,
            "tick_raw": self.tick_raw,
            "neighbourhood_ticks": self.neighbourhood_ticks,
            "price_relation_basis": self.price_relation_basis,
            "refill_attribution": REFILL_ATTRIBUTION,
            "self_restoration_policy": SELF_RESTORATION_POLICY,
        }


@dataclass
class GroupObservations:
    """What one group's actions did to the levels, plus everything they did instead.

    `integrity` is not a debug aid. Every row that changed depth without opening an episode, and
    every quantity that could not be attributed, is counted here - D60's "retained and counted"
    for the cases where "used" is not available.
    """

    observations: list[LevelObservation] = field(default_factory=list)
    integrity: Counter[str] = field(default_factory=Counter)

    def by_row(self) -> Iterable[tuple[int, list[LevelObservation]]]:
        """Observations grouped by their originating row, in tape order.

        `itertools.groupby` is deliberately not used: it would silently split a row whose
        observations are not adjacent, and the whole self-restoration rule depends on every
        observation of one row being handled together.
        """
        rows: dict[int, list[LevelObservation]] = {}
        for observation in self.observations:
            rows.setdefault(observation.row_index, []).append(observation)
        for index in sorted(rows):
            yield index, rows[index]


class InstrumentReplay:
    """One instrument's `ReplayBook`, plus the displayed-volume total derived from its deltas.

    Per instance and never a class attribute, for `ReplayBook`'s own reason: a shared book pools
    two instruments into one, which reads downstream as depth rather than as an error.

    `displayed_volume` is ONE integer per side, updated from the level deltas this module
    already measured. It is not a second book - it holds no per-level state and answers no
    question about a level - and it exists only so that a side wipe or a reset can report the
    quantity it cleared, which `ReplayBook` has no public surface to enumerate.
    """

    def __init__(self) -> None:
        self.book = ReplayBook()
        self.displayed_volume: dict[str, int] = {BID: 0, ASK: 0}

    def note_delta(self, side: str, delta: int) -> None:
        if side in self.displayed_volume:
            self.displayed_volume[side] += delta


def level_observations(
    actions: Sequence[Mapping[str, Any]],
    ctx: GroupContext,
    *,
    replay: InstrumentReplay,
    tick_raw: int = TICK_RAW_NG,
    neighbourhood_ticks: int = NEIGHBOURHOOD_TICKS,
) -> GroupObservations:
    """Advance `replay` by every action in the group and report what each did to the levels.

    This is the whole measurement, and it holds no calculator: a level's depth is read
    immediately before a row is applied and immediately after, and the signed difference is a
    REMOVAL or a REFILL. Doing it this way rather than branching per action is not tidiness -
    it is the only version that stays correct for the cases the feed actually produces, because
    `InstrumentBook` (and so `ReplayBook`) makes a duplicate add REPLACE, a modify that moves
    price re-queue at the back of a different level, and a modify with a side change leave one
    side for the other. A per-action branch has to enumerate those; a before/after read gets
    every one of them from the book itself, and cannot disagree with it.

    At most two levels can change per row - the level the order was resting on, and the level
    the row names - so the cost is a constant two reads either side of the apply, never a scan.

    Rows that open no episode are counted rather than passed over: see the module docstring for
    the three refused classes and why each is refused.
    """
    _require_actions(actions)
    if tick_raw <= 0:
        raise ReplenishmentAdapterError(f"tick_raw must be positive; got {tick_raw}")
    if neighbourhood_ticks < 0:
        raise ReplenishmentAdapterError(
            f"neighbourhood_ticks cannot be negative; got {neighbourhood_ticks}"
        )

    out = GroupObservations()
    book = replay.book

    for row_index, row in enumerate(actions):
        action = str(row.get("action", "?"))
        order_id = _int(row, "order_id")
        recv_ns = _int(row, "ts_recv_ns", ctx.recv_ns)
        if "ts_recv_ns" not in row or row.get("ts_recv_ns") is None:
            # The group's own close, never a later group's - `native_group_adapters` defaults
            # the same way. Counted because a defaulted causal timestamp is not a measured one.
            out.integrity["row_recv_ns_defaulted_to_group_close"] += 1

        if action == RESET:
            out.integrity["reset_rows"] += 1
            for side in BOOK_SIDES:
                out.integrity["reset_quantity_cleared"] += _tally(out, replay, side)
                replay.displayed_volume[side] = 0
            book.apply(row)
            continue

        price_field = _int(row, "price_raw", PRICE_SENTINEL_ABS)
        side_field = str(row.get("side", "N"))
        if action == ADD and _is_sentinel(price_field) and _int(row, "flags") & F_TOB:
            out.integrity["tob_wipe_rows"] += 1
            if side_field in BOOK_SIDES:
                out.integrity["tob_wipe_quantity_cleared"] += _tally(out, replay, side_field)
                replay.displayed_volume[side_field] = 0
            book.apply(row)
            continue

        # Everything the row can reach, named BEFORE it is applied. `resting_at` is the fact
        # (a cancel's own side and price are the instruction, and `ReplayBook` ignores them);
        # the row's own level is where an add or a modify can put liquidity.
        levels: list[tuple[str, int]] = []
        resting = book.resting_at(order_id) if action in (ADD, CANCEL, MODIFY) else None
        if resting is not None:
            levels.append((resting[0], resting[1]))
        if action in (ADD, MODIFY) and side_field in BOOK_SIDES:
            candidate = (side_field, price_field)
            if candidate not in levels:
                levels.append(candidate)
        was_resting = resting is not None

        if not levels and action in (ADD, CANCEL, MODIFY):
            # A cancel for an order that never rested (a group is a SLICE of the day, so this is
            # structural), or an add whose side the tape declined to state. `ReplayBook` counts
            # each under its own name; counted here too so no row leaves this module untraced.
            out.integrity["mutating_row_touched_no_level"] += 1

        before_depth = {level: book.level(*level) for level in levels}
        before_touch = {side: book.touch_price(side) for side in {s for s, _ in levels}}

        book.apply(row)

        after_depth = {level: book.level(*level) for level in levels}
        after_touch = {side: book.touch_price(side) for side in before_touch}

        for side, price in levels:
            count_before, volume_before = before_depth[(side, price)]
            count_after, volume_after = after_depth[(side, price)]
            delta = volume_after - volume_before
            replay.note_delta(side, delta)
            if delta == 0:
                if count_after != count_before:
                    # No quantity moved but the level's order count did. Nothing 4.7 can open
                    # an episode on (a zero removal is not a contact), so it is counted.
                    out.integrity["level_order_count_changed_without_quantity"] += 1
                else:
                    out.integrity["level_unchanged_by_mutation"] += 1
                continue

            kind = REFILL if delta > 0 else REMOVAL
            liquidity_kind: str | None = None
            basis: str | None = None
            if kind == REFILL:
                if not order_id:
                    basis = UNIDENTIFIED
                elif was_resting:
                    basis = RESIDENT
                elif action == MODIFY:
                    basis = MODIFY_MISSING
                else:
                    basis = NOT_RESIDENT
                liquidity_kind = RESHAPED_RESIDUAL if was_resting else NEW_LIQUIDITY
                out.integrity[f"refill_basis_{basis}"] += 1

            out.observations.append(
                LevelObservation(
                    row_index=row_index,
                    kind=kind,
                    action=action,
                    order_id=order_id,
                    instrument_id=ctx.instrument_id,
                    side=side,
                    price_raw=price,
                    quantity=abs(delta),
                    order_count_delta=count_after - count_before,
                    depth_before=volume_before,
                    depth_after=volume_after,
                    touch_price_before=before_touch[side],
                    touch_price_after=after_touch[side],
                    touch_state=_touch_state(price, before_touch[side], side),
                    recv_ns=recv_ns,
                    price_is_sentinel=_is_sentinel(price),
                    liquidity_kind=liquidity_kind,
                    liquidity_kind_basis=basis,
                    group_index=ctx.group_index,
                    source_day=ctx.source_day,
                    source_role=ctx.source_role,
                    continuity_segment=ctx.continuity_segment,
                    family_id=ctx.family_id,
                    session_phase=ctx.session_phase,
                    tick_raw=tick_raw,
                    neighbourhood_ticks=neighbourhood_ticks,
                )
            )
    return out


@dataclass
class _TouchWatch:
    """One episode's touch, and whether the removal that opened it pushed the touch away.

    Held here rather than on the episode because the calculator is hash-locked against its own
    tests and D61 says restore by wrapping, never by editing. Pruned every group against the
    episode's own `outcome`, so the watch set is bounded by the pending set, which is bounded by
    the horizon.
    """

    episode: ReplenishmentEpisode
    side: str
    reference_touch: int
    displaced: bool


class ReplenishmentObserver:
    """Feeds section 4.7's observation half: removals, refills and touch restorations.

    One instance per traversal. It owns a `ReplayBook` per instrument and a touch watch per
    pending episode, and it holds NO reference to the calculator - the calculator is passed in
    at each call, so this object cannot outlive or contradict the run that owns it.

    Nothing here decides an outcome. `advance`, `close_continuity_segment` and `finalize` on the
    calculator remain the only places an episode resolves, which is what keeps the no-lookahead
    property: this module can observe a restoration but can never report one before stream time
    reaches it.
    """

    def __init__(
        self,
        *,
        tick_raw: int = TICK_RAW_NG,
        neighbourhood_ticks: int = NEIGHBOURHOOD_TICKS,
    ) -> None:
        if tick_raw <= 0:
            raise ReplenishmentAdapterError(f"tick_raw must be positive; got {tick_raw}")
        if neighbourhood_ticks < 0:
            raise ReplenishmentAdapterError(
                f"neighbourhood_ticks cannot be negative; got {neighbourhood_ticks}"
            )
        self.tick_raw = tick_raw
        self.neighbourhood_ticks = neighbourhood_ticks
        self._replays: dict[int, InstrumentReplay] = {}
        self._watches: list[_TouchWatch] = []
        self.integrity: Counter[str] = Counter()
        # A book discarded at a boundary takes its integrity counters with it, so they are
        # folded in here BEFORE it goes. Dropping them at a segment close would be the same
        # silent loss D60 was written for, only spread across every boundary in the run.
        self._retired_book_integrity: Counter[str] = Counter()
        self.groups_observed = 0
        self.episodes_opened = 0
        self.refills_attributed = 0
        self.touch_restorations = 0

    def replay_for(self, instrument_id: int) -> InstrumentReplay:
        """The book for one instrument, created empty on first sight."""
        replay = self._replays.get(instrument_id)
        if replay is None:
            replay = InstrumentReplay()
            self._replays[instrument_id] = replay
        return replay

    def observe_group(
        self,
        actions: Sequence[Mapping[str, Any]],
        ctx: GroupContext,
        *,
        calculator: ReplenishmentCalculator,
    ) -> list[dict[str, Any]]:
        """Tell `calculator` what this group's actions did, and hand back every fact stated.

        The return is the point, not a courtesy. `native_replay_driver._feed_sections` retains
        the exact row every fed section hands back, because keeping the stratified measure while
        losing the member beneath it is what section 6 rejects and D60 forbids. These rows carry
        the same `episode_id` the calculator emits at maturity, so an observation and its
        outcome join without either side having to be re-derived.

        Within one row: refills are attributed FIRST against the episodes pending before the
        row, then removals open theirs. That ordering is the whole self-restoration rule - see
        the module docstring.
        """
        self._prune_watches()
        replay = self.replay_for(ctx.instrument_id)
        group = level_observations(
            actions,
            ctx,
            replay=replay,
            tick_raw=self.tick_raw,
            neighbourhood_ticks=self.neighbourhood_ticks,
        )
        self.integrity.update(group.integrity)
        self.groups_observed += 1

        rows: list[dict[str, Any]] = []
        for _row_index, observations in group.by_row():
            refills = [o for o in observations if o.kind == REFILL]
            removals = [o for o in observations if o.kind == REMOVAL]
            for observation in refills:
                rows.append(self._attribute_refill(observation, calculator))
            for observation in refills:
                self._check_touch_restoration(observation)
            for observation in removals:
                rows.append(self._open_episode(observation, calculator))
        return rows

    def close_continuity_segment(self, *, segment: int, recv_ns: int) -> list[dict[str, Any]]:
        """Drop the books at a boundary, and state what was standing when they went.

        Section 2 forbids a calculation crossing a reset, snapshot, gap or session boundary, and
        a book built before a gap describes liquidity nobody can vouch for after it. The
        calculator censors its own pending episodes through its own `close_continuity_segment`;
        this drops only what this module holds, and reports the depth it was carrying rather
        than discarding it silently.
        """
        rows = [
            {
                "section": "4.7",
                "observation": "SEGMENT_BOOK_DISCARDED",
                "continuity_segment": segment,
                "recv_ns": recv_ns,
                "instrument_id": instrument_id,
                "displayed_volume_discarded": dict(replay.displayed_volume),
                "displayed_volume_basis": CLEARED_QUANTITY_BASIS,
                "touch_watches_abandoned": sum(
                    1 for w in self._watches if w.episode.instrument_id == instrument_id
                ),
                "replay_book_integrity": dict(replay.book.integrity),
            }
            for instrument_id, replay in sorted(self._replays.items())
        ]
        for replay in self._replays.values():
            self._retired_book_integrity.update(replay.book.integrity)
        self.integrity["segment_books_discarded"] += len(rows)
        self._replays = {}
        self._watches = []
        return rows

    def summary(self) -> dict[str, Any]:
        """Counts only. No mean, no rate, no share - the calculator owns every measure."""
        return {
            "section": "4.7",
            "half": "OBSERVATION",
            "groups_observed": self.groups_observed,
            "episodes_opened": self.episodes_opened,
            "refills_attributed": self.refills_attributed,
            "touch_restorations_observed": self.touch_restorations,
            "open_touch_watches": len(self._watches),
            "instruments": len(self._replays),
            "tick_raw": self.tick_raw,
            "tick_decimal": self.tick_raw / PRICE_SCALE,
            "neighbourhood_ticks": self.neighbourhood_ticks,
            "price_relation_basis": (
                f"ADJACENT_LEVEL|tick_raw={self.tick_raw}"
                f"|neighbourhood_ticks={self.neighbourhood_ticks}"
            ),
            "refill_attribution": REFILL_ATTRIBUTION,
            "self_restoration_policy": SELF_RESTORATION_POLICY,
            "cleared_quantity_basis": CLEARED_QUANTITY_BASIS,
            # The three classes that open no episode, named by the reason each is refused
            # rather than left to be read off three unrelated counter names. A consumer
            # asking "what did 4.7 decline to measure, and why" gets one answer here.
            "refused_row_classes": {
                REFUSED_SENTINEL_PRICE: self.integrity["removal_at_undefined_price_not_opened"],
                REFUSED_TOB_WIPE: self.integrity["tob_wipe_rows"],
                REFUSED_RESET: self.integrity["reset_rows"],
            },
            "separation_note": (
                "new-ID adds and same-ID modifies are classified on observed residency and "
                "handed to the calculator as separate kinds; a refill beyond one tick is "
                "counted, never folded into the neighbouring bucket"
            ),
            "integrity": dict(self.integrity),
            # `ReplayBook` counts every row that changed no state or changed it anomalously -
            # an unsided add, a cancel for an order that never rested, the quantity an
            # over-cancel swallowed, a sentinel rest, a side wipe. Those books are held here,
            # so their counters are reported here or they are reported nowhere.
            "replay_book_integrity": dict(self._book_integrity()),
        }

    def _book_integrity(self) -> Counter[str]:
        """Live books plus every book already retired at a continuity boundary."""
        total: Counter[str] = Counter(self._retired_book_integrity)
        for replay in self._replays.values():
            total.update(replay.book.integrity)
        return total

    # --- the two ingest paths ---------------------------------------------

    def _attribute_refill(
        self, observation: LevelObservation, calculator: ReplenishmentCalculator
    ) -> dict[str, Any]:
        """Add this refill to every pending episode whose level is within the neighbourhood."""
        row = observation.as_dict()
        if observation.price_is_sentinel:
            self.integrity["refill_at_undefined_price_unattributed"] += 1
            self.integrity["refill_quantity_unattributed"] += observation.quantity
            row["attributed_to_episode_ids"] = []
            row["unattributed_reason"] = PRICE_UNDEFINED
            row["shared_with_episode_count"] = 0
            return row

        attributed: list[int] = []
        relations: list[str] = []
        offsets: list[int] = []
        anomalous = False
        for step in range(-self.neighbourhood_ticks, self.neighbourhood_ticks + 1):
            price = observation.price_raw + step * self.tick_raw
            for episode in calculator.pending_at(
                observation.instrument_id, observation.side, price
            ):
                # `price_relation_to` is the ONE owner of the relation. Deriving it here from
                # `step` as well would be a second opinion about a single fact, which is the
                # `_family_id` shape: nothing fails and the two vocabularies simply disagree.
                relation = observation.price_relation_to(episode.price_raw)
                if relation is None:
                    self.integrity["refill_relation_undefined"] += 1
                    anomalous = True
                    continue
                if observation.recv_ns < episode.opened_recv_ns:
                    # An out-of-order feed, not a refill for this episode. Never clamped into
                    # range: the quantity is kept in the counters and the episode is untouched.
                    self.integrity["refill_precedes_episode_open"] += 1
                    self.integrity["refill_quantity_unattributed"] += observation.quantity
                    anomalous = True
                    continue
                price_relation, offset = relation
                episode.add_refill(
                    quantity=observation.quantity,
                    liquidity_kind=observation.liquidity_kind or NEW_LIQUIDITY,
                    price_relation=price_relation,
                    recv_ns=observation.recv_ns,
                )
                attributed.append(episode.episode_id)
                relations.append(price_relation)
                offsets.append(offset)
                self.refills_attributed += 1

        if not attributed and not anomalous:
            self.integrity["refill_with_no_pending_episode"] += 1
            self.integrity["refill_quantity_no_pending_episode"] += observation.quantity
            row["unattributed_reason"] = NO_PENDING_EPISODE_IN_NEIGHBOURHOOD
        row["attributed_to_episode_ids"] = attributed
        row["price_relations"] = relations
        row["neighbour_offset_ticks"] = offsets
        # Declared, not inferred: overlapping episodes SHARE this quantity, so a sum of
        # `neighborhood_arrival_quantity` across them exceeds what arrived. The episode is the unit.
        row["shared_with_episode_count"] = max(len(attributed) - 1, 0)
        return row

    def _open_episode(
        self, observation: LevelObservation, calculator: ReplenishmentCalculator
    ) -> dict[str, Any]:
        """Open one episode for one removal, or state why none was opened."""
        row = observation.as_dict()
        if observation.price_is_sentinel:
            self.integrity["removal_at_undefined_price_not_opened"] += 1
            self.integrity["removal_quantity_not_opened"] += observation.quantity
            row["episode_id"] = None
            row["refused_reason"] = REFUSED_SENTINEL_PRICE
            row["touch_disposition"] = TOUCH_REFERENCE_ABSENT
            return row

        if calculator.pending_at(
            observation.instrument_id, observation.side, observation.price_raw
        ):
            # 4.7 names persistence, and a level depleted AGAIN while an episode on it is still
            # pending is exactly that. The calculator has no ingest for a second removal inside
            # an open episode, so the fact is counted and carried on this row rather than lost.
            self.integrity["removal_during_pending_episode"] += 1
            row["removal_during_pending_episode"] = True

        episode = calculator.open_episode(
            instrument_id=observation.instrument_id,
            side=observation.side,
            price_raw=observation.price_raw,
            recv_ns=observation.recv_ns,
            continuity_segment=observation.continuity_segment,
            source_day=observation.source_day,
            source_role=observation.source_role,
            family_id=observation.family_id,
            session_phase=observation.session_phase,
            touch_state_at_open=observation.touch_state,
            removed_quantity=observation.quantity,
            removed_order_count=max(-observation.order_count_delta, 0),
            depth_at_open=observation.depth_before,
            touch_price_at_open=observation.touch_price_before,
        )
        self.episodes_opened += 1
        row["episode_id"] = episode.episode_id
        row["touch_disposition"] = self._arm_touch_watch(observation, episode)
        return row

    # --- touch restoration ------------------------------------------------

    def _arm_touch_watch(
        self, observation: LevelObservation, episode: ReplenishmentEpisode
    ) -> str:
        """Decide, at the removal, whether this episode's touch was pushed away at all.

        A removal deep in the book leaves the touch where it was, so there is nothing to
        restore, and calling `restore_touch` on the next add would report a restoration that
        never had a displacement. That reads as a fast, healthy book and is fabricated. The
        watch is armed only when the touch actually moved, and the disposition is returned so
        the never-displaced case is on the row rather than hiding inside a `None`.
        """
        reference = observation.touch_price_before
        if reference is None or _is_sentinel(reference):
            self.integrity["episode_opened_without_touch_reference"] += 1
            return TOUCH_REFERENCE_ABSENT
        if _is_at_least_as_good(observation.touch_price_after, reference, observation.side):
            self.integrity["touch_never_displaced"] += 1
            return TOUCH_NEVER_DISPLACED
        self.integrity["touch_displaced"] += 1
        self._watches.append(
            _TouchWatch(
                episode=episode,
                side=observation.side,
                reference_touch=reference,
                displaced=True,
            )
        )
        return TOUCH_DISPLACED

    def _check_touch_restoration(self, observation: LevelObservation) -> None:
        """A refill that brings its side's touch back to the reference restores it.

        Every touch improvement coincides with a positive depth delta on that side - the touch
        can only improve if some level on it became populated - so checking on refills sees
        every restoration without reading the book on rows that could not have caused one.
        """
        if observation.price_is_sentinel:
            # `ReplayBook` mirrors `InstrumentBook` and lets a sentinel-priced bid rest as the
            # touch. Treating that as a restoration would credit the book for a price the feed
            # declined to state.
            self.integrity["touch_restoration_skipped_sentinel"] += 1
            return
        touch = observation.touch_price_after
        for watch in self._watches:
            if watch.episode.instrument_id != observation.instrument_id:
                continue
            if watch.side != observation.side:
                continue
            if watch.episode.outcome is not None:
                # Already emitted. Mutating a resolved episode would edit a fact after the row
                # that stated it was written, which is the reason `LevelObservation` is frozen.
                continue
            if watch.episode.touch_restored_recv_ns is not None:
                continue
            if _is_at_least_as_good(touch, watch.reference_touch, watch.side):
                watch.episode.restore_touch(observation.recv_ns)
                self.touch_restorations += 1

    def _prune_watches(self) -> None:
        """Drop watches whose episode has already resolved or been censored.

        The calculator emits an episode by setting its `outcome` and removing it from the
        pending set, so `outcome is not None` is the episode's own statement that it is done -
        not a second opinion formed here. Bounded by the pending set, which the horizon bounds.
        """
        if not self._watches:
            return
        before = len(self._watches)
        self._watches = [w for w in self._watches if w.episode.outcome is None]
        self.integrity["touch_watches_pruned"] += before - len(self._watches)
