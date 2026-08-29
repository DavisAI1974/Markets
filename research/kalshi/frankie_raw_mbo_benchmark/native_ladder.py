"""Section 4.9: price-ladder topology.

Section 4.9 ends with a separation that is easy to state and easy to lose: "Separate
absolute liquidity from relative imbalance." Depth and imbalance move independently - a
book can double in size with imbalance unchanged, or flip from bid-heavy to ask-heavy with
no change in total depth - so a single "liquidity" number silently mixes two different
facts. Here they are separate measures and neither is derived from the other.

Topology is compared between two consecutive full-book states. Level births and deaths are
computed as exact set differences over occupied prices rather than inferred from depth
changes, because a level whose size merely fell is not a level that died, and treating it
as one would invent discontinuities that never happened.

Gaps are reported as the exact occupied-price geometry, since section 4.9 says rare
discontinuities cannot be represented by an average and remain coequal with it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_stratum import (
    RESOLVED,
    Declaration,
    StratifiedMeasure,
    StratumKey,
)

CAUSAL_CLOCK = "ts_recv_ns"

COMPRESSION = "COMPRESSION"
EXPANSION = "EXPANSION"
UNCHANGED = "UNCHANGED"


class LadderError(ValueError):
    """A ladder transition could not be measured."""


@dataclass(frozen=True)
class LadderSide:
    """One side's occupied price ladder at one instant.

    `depth_by_price` is the full ladder, not a top-N view: section 6.2 of the ingestion
    paper rejects a top-of-book or MBP-10 substitute for this state.
    """

    side: str
    depth_by_price: Mapping[int, int]

    def __post_init__(self) -> None:
        if self.side not in ("B", "A"):
            raise LadderError("side must be B or A")
        for price, depth in self.depth_by_price.items():
            if depth < 0:
                raise LadderError(f"depth at {price} is negative")

    @property
    def occupied_prices(self) -> frozenset[int]:
        return frozenset(price for price, depth in self.depth_by_price.items() if depth > 0)

    @property
    def occupied_level_count(self) -> int:
        return len(self.occupied_prices)

    @property
    def total_depth(self) -> int:
        return sum(depth for depth in self.depth_by_price.values() if depth > 0)

    @property
    def best_price(self) -> int | None:
        prices = self.occupied_prices
        if not prices:
            return None
        return max(prices) if self.side == "B" else min(prices)

    @property
    def price_gaps(self) -> list[int]:
        """Exact spacing between consecutive occupied prices, best-first."""
        prices = sorted(self.occupied_prices, reverse=(self.side == "B"))
        return [abs(b - a) for a, b in zip(prices, prices[1:])]

    @property
    def depth_concentration(self) -> float | None:
        """Share of total depth resting at the best price. None on an empty side."""
        best = self.best_price
        if best is None or self.total_depth == 0:
            return None
        return self.depth_by_price[best] / self.total_depth


@dataclass(frozen=True)
class LadderTransition:
    """The exact topology change between two consecutive states of one side."""

    before: LadderSide
    after: LadderSide
    recv_ns: int
    causing_order_ids: tuple[int, ...] = ()
    ladder_scope: str = ""
    """WHAT this transition is a transition OF. Travels on the value, never only in prose.

    D60/S114. `native_group_adapters` builds these as a GROUP-LOCAL DELTA - `before` is the
    depth the group CONSUMED and `after` the depth it LEFT - which is a true statement about
    the group and a false one about the book. Its module docstring said the caveat "travels ON
    the value as `ladder_scope`", a constant was defined for it, and it was attached to
    nothing and emitted nowhere. Read as a book snapshot, `depth_concentration_after` means
    something other than what it says and `level_deaths` are invented.
    """

    def __post_init__(self) -> None:
        if self.before.side != self.after.side:
            raise LadderError("a transition compares one side with itself")

    @property
    def side(self) -> str:
        return self.before.side

    @property
    def level_births(self) -> frozenset[int]:
        """Prices occupied after but not before - a set difference, not a depth inference."""
        return self.after.occupied_prices - self.before.occupied_prices

    @property
    def level_deaths(self) -> frozenset[int]:
        return self.before.occupied_prices - self.after.occupied_prices

    @property
    def best_price_moved(self) -> bool:
        return self.before.best_price != self.after.best_price

    @property
    def touch_migration_raw(self) -> int | None:
        """Signed toward the side's own aggression. None if either side was empty."""
        if self.before.best_price is None or self.after.best_price is None:
            return None
        delta = self.after.best_price - self.before.best_price
        return delta if self.side == "B" else -delta

    @property
    def touch_state(self) -> str:
        migration = self.touch_migration_raw
        if migration is None or migration == 0:
            return UNCHANGED
        return EXPANSION if migration > 0 else COMPRESSION

    @property
    def depth_migration(self) -> int:
        """Absolute depth change. Deliberately not combined with imbalance."""
        return self.after.total_depth - self.before.total_depth

    def as_dict(self) -> dict[str, Any]:
        return {
            "side": self.side,
            "recv_ns": self.recv_ns,
            "occupied_levels_before": self.before.occupied_level_count,
            "occupied_levels_after": self.after.occupied_level_count,
            "level_births": sorted(self.level_births),
            "level_deaths": sorted(self.level_deaths),
            "level_birth_count": len(self.level_births),
            "level_death_count": len(self.level_deaths),
            "best_price_before": self.before.best_price,
            "best_price_after": self.after.best_price,
            "best_price_moved": self.best_price_moved,
            "touch_migration_raw": self.touch_migration_raw,
            "touch_state": self.touch_state,
            "total_depth_before": self.before.total_depth,
            "total_depth_after": self.after.total_depth,
            "depth_migration": self.depth_migration,
            "depth_concentration_after": self.after.depth_concentration,
            "price_gaps_after": self.after.price_gaps,
            "max_price_gap_after": max(self.after.price_gaps) if self.after.price_gaps else 0,
            "causing_order_ids": list(self.causing_order_ids),
            "ladder_scope": self.ladder_scope,
            "clock": CAUSAL_CLOCK,
        }


def relative_imbalance(bid_depth: int, ask_depth: int) -> float | None:
    """(bid - ask) / (bid + ask). None on an empty book rather than zero.

    Kept a free function and reported as its own measure so it is never folded into an
    absolute-liquidity figure; section 4.9 requires the two stay separate.
    """
    total = bid_depth + ask_depth
    if total == 0:
        return None
    return (bid_depth - ask_depth) / total


class LadderCalculator:
    """Streaming section 4.9 accumulator over consecutive full-book states."""

    def __init__(self, *, exact_cap: int | None = None, seed: int = 0) -> None:
        kwargs: dict[str, Any] = {"seed": seed}
        if exact_cap is not None:
            kwargs["exact_cap"] = exact_cap

        def measure(name: str, numerator: str, missingness: str):
            return StratifiedMeasure(
                name=name,
                declaration=Declaration(
                    numerator_formula=numerator,
                    population="ladder transitions within the stratum and continuity segment",
                    causal_cutoff="transition receive time on ts_recv_ns",
                    status=RESOLVED,
                    missingness_rule=missingness,
                ),
                **kwargs,
            )

        self.occupied_levels = measure(
            "occupied_level_count",
            "count of prices with positive depth after the transition",
            "no exclusions",
        )
        self.price_gap = measure(
            "price_gap_raw",
            "spacing between consecutive occupied prices, one observation per gap",
            "sides with fewer than two occupied levels contribute no gap and are counted",
        )
        self.level_births = measure(
            "level_birth_count",
            "prices occupied after but not before",
            "no exclusions",
        )
        self.level_deaths = measure(
            "level_death_count",
            "prices occupied before but not after",
            "no exclusions",
        )
        self.touch_migration = measure(
            "touch_migration_raw",
            "best-price change signed toward the side's own aggression",
            "transitions with an empty side are excluded and counted",
        )
        self.absolute_depth = measure(
            "absolute_total_depth",
            "sum of resting size across all occupied levels on the side",
            "no exclusions; this is absolute liquidity and is never combined with imbalance",
        )
        self.relative_imbalance = measure(
            "relative_imbalance",
            "(bid depth - ask depth) / (bid depth + ask depth), book-level",
            "empty books are excluded and counted; this is relative and never combined with depth",
        )
        self.depth_concentration = measure(
            "depth_concentration_at_touch",
            "depth at the best price over total side depth",
            "empty sides are excluded and counted",
        )

        self.transitions = 0
        self.touch_state_counts = {COMPRESSION: 0, EXPANSION: 0, UNCHANGED: 0}

    @property
    def measures(self) -> tuple[StratifiedMeasure, ...]:
        return (
            self.occupied_levels,
            self.price_gap,
            self.level_births,
            self.level_deaths,
            self.touch_migration,
            self.absolute_depth,
            self.relative_imbalance,
            self.depth_concentration,
        )

    @staticmethod
    def _key(
        *,
        source_day: str,
        source_role: str,
        continuity_segment: int,
        family_id: str,
        side: str,
        session_phase: str,
        touch_state: str,
    ) -> StratumKey:
        return StratumKey(
            source_day=source_day,
            source_role=source_role,
            continuity_segment=continuity_segment,
            family_id=family_id,
            side_orientation=side,
            session_phase=session_phase,
            clock=CAUSAL_CLOCK,
            subfamily_id=f"touch_state={touch_state}",
        )

    def observe(
        self,
        transition: LadderTransition,
        *,
        source_day: str,
        source_role: str,
        continuity_segment: int,
        family_id: str,
        session_phase: str,
        opposite_side_depth: int | None = None,
    ) -> dict[str, Any]:
        key = self._key(
            source_day=source_day,
            source_role=source_role,
            continuity_segment=continuity_segment,
            family_id=family_id,
            side=transition.side,
            session_phase=session_phase,
            touch_state=transition.touch_state,
        )
        after = transition.after
        self.transitions += 1
        self.touch_state_counts[transition.touch_state] += 1

        self.occupied_levels.observe(key, float(after.occupied_level_count))
        self.level_births.observe(key, float(len(transition.level_births)))
        self.level_deaths.observe(key, float(len(transition.level_deaths)))
        self.absolute_depth.observe(key, float(after.total_depth))

        gaps = after.price_gaps
        if gaps:
            for gap in gaps:
                self.price_gap.observe(key, float(gap))
        else:
            self.price_gap.exclude_missing(key)

        migration = transition.touch_migration_raw
        if migration is None:
            self.touch_migration.exclude_missing(key)
        else:
            self.touch_migration.observe(key, float(migration))

        concentration = after.depth_concentration
        if concentration is None:
            self.depth_concentration.exclude_missing(key)
        else:
            self.depth_concentration.observe(key, float(concentration))

        if opposite_side_depth is None:
            self.relative_imbalance.exclude_missing(key)
        else:
            bid, ask = (
                (after.total_depth, opposite_side_depth)
                if transition.side == "B"
                else (opposite_side_depth, after.total_depth)
            )
            imbalance = relative_imbalance(bid, ask)
            if imbalance is None:
                self.relative_imbalance.exclude_missing(key)
            else:
                self.relative_imbalance.observe(key, float(imbalance))

        return transition.as_dict()

    def companion_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for measure in self.measures:
            rows.extend(measure.rows())
        return rows

    def summary(self) -> dict[str, Any]:
        return {
            "section": "4.9",
            "causal_clock": CAUSAL_CLOCK,
            "transitions": self.transitions,
            "touch_state_counts": dict(self.touch_state_counts),
            "separation_note": (
                "absolute_total_depth and relative_imbalance are separate measures and "
                "neither is derived from the other; a book can double in size with imbalance "
                "unchanged, or flip imbalance with depth unchanged"
            ),
            "births_deaths_note": (
                "level births and deaths are exact set differences over occupied prices, not "
                "inferences from depth changes: a level whose size merely fell did not die"
            ),
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
        }
