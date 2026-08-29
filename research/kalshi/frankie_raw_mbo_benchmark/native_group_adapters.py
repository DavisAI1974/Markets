"""Construct section-4 domain objects from one F_LAST group (decision D53, 2026-08-29).

Sections 4.6 to 4.16 were built, tested and closed at their boundaries, and then fed by
nothing. The reason was not an oversight: the calculation contract specifies the
CALCULATION and never the input event. Section 4.10 says "construct a complete causal
runway for each candidate" without anywhere defining a candidate, and every ingest point in
the tree - `LadderCalculator.observe`, `RecurrenceCalculator.observe_sequence`,
`LineageCalculator.observe_node`, `AbsorptionCalculator.score`,
`ExhaustionCalculator.enter_phase` - takes a CONSTRUCTED DOMAIN OBJECT. Nothing built those
from raw MBO. This module is that missing layer.

**The unit is the F_LAST group (D53, Greg).** A candidate IS one F_LAST group: the same unit
`describe_structure` already hashes into `candidate_family_id`, and the unit the member-first
run cut its 4,758 candidate families from over 4.26M groups. Chosen so reconciliation against
that roster holds by construction rather than by agreement between two vocabularies - which
is precisely the `_family_id` defect caught on 2026-08-29, where the driver keyed strata on a
bare action string while the roster keyed on the structural hash. Nothing failed there; the
strata were simply cut differently. One unit, one vocabulary, no second opinion.

**Every construction here is STRUCTURAL and group-local.** It reads only the group's own
actions - no book state, no external vocabulary, no fitted threshold, no bar sited at a
value. That is the `describe_structure` precedent and it is what keeps these open-world: a
label this module cannot justify from the group's contents is not emitted.

**The declared cost of the one-unit choice, recorded rather than smoothed over.** Greg took
this trade knowingly and it is written into D53: sections 4.6 (order survival) and 4.9
(ladder topology) are not naturally group-shaped.

* **4.9 is a group-local ladder DELTA, not a book snapshot.** A single F_LAST group cannot
  see resting liquidity it did not touch. `before` is therefore the depth the group CONSUMED
  (the liquidity it found) and `after` is the depth it LEFT (the liquidity it added). This
  is a true statement about the group and a false one about the book, so the scope travels
  ON the value as `ladder_scope`, not only in this docstring - a caveat that lives only in
  prose is a caveat that expires (S114). Read as a book snapshot it would overstate
  `depth_concentration` and invent level deaths.
* **Lineage depth accumulates ACROSS groups, not within one.** Within a single fill cascade
  the observable causal structure is one level deep - an aggressor against the resting
  orders it consumed - so a within-group lineage would report `max_depth` 1 forever and look
  like a measurement rather than an artifact of the unit. `LineageCalculator` holds its graph
  across the traversal, so the group is the unit of OBSERVATION while depth is a property of
  the accumulating graph, keyed on `order_id`.

**No averaging anywhere.** Nothing here returns a mean, a ratio-of-sums or a rate; the
calculators own the stratified measures and this module only hands them exact per-group
quantities. Sizes and counts are integers throughout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_ladder import LadderSide, LadderTransition
from research.kalshi.frankie_raw_mbo_benchmark.native_recurrence import Occurrence

ADD = "A"
CANCEL = "C"
MODIFY = "M"
FILL = "F"
TRADE = "T"

CONSUMING_ACTIONS = frozenset({CANCEL, FILL, TRADE})
"""Actions that act on liquidity which was ALREADY RESTING when the group opened."""

ADDING_ACTIONS = frozenset({ADD})
"""Actions that leave liquidity resting after the group closes."""

PRICE_SENTINEL_ABS = 9_000_000_000_000_000_000
"""Databento's undefined-price sentinel. `describe_structure` excludes on the same bound."""

BID, ASK = "B", "A"

LADDER_SCOPE = "GROUP_LOCAL_DELTA"
"""What a `ladder_transitions` value IS. Travels with the value; see the module docstring."""


class GroupAdapterError(ValueError):
    """A group could not be turned into a section-4 domain object."""


@dataclass(frozen=True)
class GroupContext:
    """Everything a calculator needs about a group that is not in its actions.

    Frozen because a stratum key assembled from mutable context is a key that can be
    changed after the row it labelled was written.
    """

    group_index: int
    source_day: str
    source_role: str
    continuity_segment: int
    session_phase: str
    family_id: str
    side_orientation: str
    event_ns: int
    recv_ns: int
    instrument_id: int = 0

    @property
    def candidate_id(self) -> str:
        """Stable per-group identity. Absolute, so two runs over overlapping windows agree."""
        return f"grp-{self.source_day}-{self.group_index}"


def _int(row: Mapping[str, Any], key: str, default: int = 0) -> int:
    value = row.get(key)
    if value is None:
        return default
    return int(value)


def _size(row: Mapping[str, Any]) -> int:
    """A size is a quantity, so a negative one is refused rather than clamped.

    `max(0, ...)` would turn a malformed row into a silent zero, which is present, typed,
    in range and wrong - the failure shape this tree keeps guarding against.
    """
    size = _int(row, "size")
    if size < 0:
        raise GroupAdapterError(f"negative size {size} in a raw action row")
    return size


def _price(row: Mapping[str, Any]) -> int | None:
    """The row's price, or None when it carries the undefined-price sentinel."""
    value = row.get("price_raw")
    if value is None:
        return None
    price = int(value)
    if abs(price) >= PRICE_SENTINEL_ABS:
        return None
    return price


def _action(row: Mapping[str, Any]) -> str:
    return str(row.get("action", "?"))


def _side(row: Mapping[str, Any]) -> str:
    return str(row.get("side", "N"))


def _require_actions(actions: Sequence[Mapping[str, Any]]) -> None:
    if not actions:
        raise GroupAdapterError("an F_LAST group must contain at least one native action")


# --------------------------------------------------------------------------------------
# 4.14 Recurrence
# --------------------------------------------------------------------------------------
def occurrences(actions: Sequence[Mapping[str, Any]], ctx: GroupContext) -> list[Occurrence]:
    """One occurrence per action, in tape order.

    The node label is `action|side` rather than the bare action, so a cancel on the bid and
    a cancel on the ask are different nodes in the transition graph. Collapsing them would
    pool two sides into one - the parallel-view rule broken at construction time, where no
    later check could see it.
    """
    _require_actions(actions)
    return [
        Occurrence(
            node=f"{_action(row)}|{_side(row)}",
            recv_ns=_int(row, "ts_recv_ns", ctx.recv_ns),
            continuity_segment=ctx.continuity_segment,
            order_id=_int(row, "order_id") or None,
        )
        for row in actions
    ]


# --------------------------------------------------------------------------------------
# 4.9 Price-ladder topology
# --------------------------------------------------------------------------------------
def ladder_transitions(
    actions: Sequence[Mapping[str, Any]], ctx: GroupContext
) -> dict[str, LadderTransition]:
    """One transition per side: depth CONSUMED before, depth LEFT after.

    See the module docstring - this is a group-local delta, not a book snapshot, because a
    group cannot see liquidity it never touched. Sides are kept apart; a row whose side is
    neither bid nor ask (Databento's `N`) contributes to neither, because assigning it to one
    would fabricate a side the tape declined to state.
    """
    _require_actions(actions)
    before: dict[str, dict[int, int]] = {BID: {}, ASK: {}}
    after: dict[str, dict[int, int]] = {BID: {}, ASK: {}}
    causing: dict[str, list[int]] = {BID: [], ASK: []}

    for row in actions:
        side = _side(row)
        if side not in (BID, ASK):
            continue
        price = _price(row)
        if price is None:
            continue
        action = _action(row)
        size = _size(row)
        if action in CONSUMING_ACTIONS:
            before[side][price] = before[side].get(price, 0) + size
        elif action in ADDING_ACTIONS:
            after[side][price] = after[side].get(price, 0) + size
        order_id = _int(row, "order_id")
        if order_id:
            causing[side].append(order_id)

    return {
        side: LadderTransition(
            before=LadderSide(side=side, depth_by_price=dict(before[side])),
            after=LadderSide(side=side, depth_by_price=dict(after[side])),
            recv_ns=ctx.recv_ns,
            causing_order_ids=tuple(dict.fromkeys(causing[side])),
            ladder_scope=LADDER_SCOPE,
        )
        for side in (BID, ASK)
        if before[side] or after[side]
    }


# --------------------------------------------------------------------------------------
# 4.8 Absorption
# --------------------------------------------------------------------------------------
def runway_pressure_fields(
    actions: Sequence[Mapping[str, Any]], ctx: GroupContext
) -> dict[str, Any]:
    """Exact per-group quantities for a `RunwayPressure`.

    Traded and withdrawn depletion stay separate quantities and are never summed into one
    "depletion", because 4.8 requires they never pool: an order that traded away and an
    order that was pulled are opposite evidence about pressure, and their sum is the one
    number that cannot tell them apart.
    """
    _require_actions(actions)
    traded = sum(_size(r) for r in actions if _action(r) in (FILL, TRADE))
    withdrawn = sum(_size(r) for r in actions if _action(r) == CANCEL)
    added = sum(_size(r) for r in actions if _action(r) in ADDING_ACTIONS)
    orientation = ctx.side_orientation

    same_side_added = sum(
        _size(r) for r in actions if _action(r) == ADD and _side(r) == orientation
    )
    opposite_retreat = sum(
        _size(r)
        for r in actions
        if _action(r) == CANCEL and _side(r) not in (orientation, "N")
    )

    consumed_ids = {_int(r, "order_id") for r in actions if _action(r) in CONSUMING_ACTIONS} - {0}
    added_ids = {_int(r, "order_id") for r in actions if _action(r) in ADDING_ACTIONS} - {0}

    prices = [p for p in (_price(r) for r in actions) if p is not None]

    return {
        "traded_quantity": traded,
        "withdrawn_quantity": withdrawn,
        "same_side_replacement_quantity": same_side_added,
        "opposite_side_retreat_quantity": opposite_retreat,
        "depth_at_open": traded + withdrawn,
        "surviving_depth": added,
        "price_at_open_raw": prices[0] if prices else 0,
        "price_at_close_raw": prices[-1] if prices else 0,
        "order_ids_at_open": len(consumed_ids),
        "order_ids_at_close": len(added_ids),
        "order_ids_persisting": len(consumed_ids & added_ids),
        "member_count": len(actions),
    }


# --------------------------------------------------------------------------------------
# 4.13 Lineage
# --------------------------------------------------------------------------------------
def lineage_additions(
    actions: Sequence[Mapping[str, Any]],
    ctx: GroupContext,
    *,
    seen_order_ids: Mapping[int, str],
) -> list[dict[str, Any]]:
    """`LineageGraph.add` keyword sets for the order ids this group touched FIRST.

    Returns argument sets rather than constructed `LineageNode`s deliberately. `LineageGraph`
    derives `depth` from the parent it already holds, so a node built here with its own depth
    would be a SECOND opinion about the same fact - and when two vocabularies describe one
    quantity, nothing fails, the values simply disagree. That is the `_family_id` defect of
    2026-08-29 exactly, and the fix there was the same: one owner, no second computation.
    Depth is therefore never set here.

    An order id that already carries a node keeps it; a new one is parented on the group's
    initiating order id, which is the first row's. An order id first seen as its own group's
    initiator, with no prior node, is a root and is added with `parent_id=None`.

    `seen_order_ids` maps an order id to the node id already issued for it, so this stays a
    forward-only pass with no lookahead: the caller owns the accumulated state, exactly as
    the traversal owns `SessionSegmenter`'s.
    """
    _require_actions(actions)
    initiator = _int(actions[0], "order_id")
    parent_node = seen_order_ids.get(initiator)
    additions: list[dict[str, Any]] = []
    issued: set[int] = set()

    for row in actions:
        order_id = _int(row, "order_id")
        if not order_id or order_id in seen_order_ids or order_id in issued:
            continue
        issued.add(order_id)
        is_root = order_id == initiator and parent_node is None
        additions.append(
            {
                "node_id": f"ord-{order_id}",
                "parent_id": None if is_root else (parent_node or f"ord-{initiator}"),
                "transition_type": _action(row),
                "side_orientation": _side(row),
                "entered_recv_ns": _int(row, "ts_recv_ns", ctx.recv_ns),
            }
        )
    return additions
