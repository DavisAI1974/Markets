"""Section 4.2: the daily book regime companion, which did not run.

**Why this exists.** D-4. A full-text walk of run 33605852433's result for `4.2`,
`book_regime`, `daily_book`, `first_book`, `last_book` and `spread` returned four hits and
none of them was a 4.2 output: one gate surface id, two byte-accounting entries and one
`frame_keys_carried` entry. No first/last snapshot pair, no per-day min, max or mean for
spread, depth, order count or level count, no group count, no max-actions-per-group. The
verdict on it was `NO_VALUE_AS_COMPUTED (it did not run)`, and the parenthetical is the whole
content: the section was not wrong, it was absent.

**That absence is why the run's largest artifact had no reader.** `book_full` is 10.13 GB,
93.47% of the exact member ledger, stored on all 43,569 member rows - and 4.2 is the section
whose entire job is to summarise it. With 4.2 dark, ten gigabytes of reconstructed book were
retained and consumed by nothing, which is the D60 shape in its most expensive form. Nothing
new is captured here and no new pass is made: this reads the book that is already on the row.

**On the stratum.** Every other section keys by family. This one is a PER-DAY companion by
contract, so it deliberately aggregates families, and it says so in the family slot itself
rather than leaving a reader to infer it from a suspiciously coarse row. Segment, phase, day
and role still key normally, because a continuity break and a session phase change the object
being described.

**`relative_imbalance` here is a third computation of an estimand two other sections already
compute** - 4.9 and 4.12 both do `(bid - ask)/(bid + ask)`. That is not duplication to be
removed; it is exactly what the cross-section gate reads, and a third independent measurement
of the same quantity from a third substrate is what makes a one-sided book detectable rather
than merely present.
"""
from __future__ import annotations

from typing import Any, Mapping

from research.kalshi.frankie_raw_mbo_benchmark.native_stratum import (
    RESOLVED,
    Declaration,
    StratifiedMeasure,
    StratumError,
    StratumKey,
)

CAUSAL_CLOCK = "ts_recv_ns"

DAY_COMPANION_FAMILY = "ALL_FAMILIES_DAY_COMPANION"
"""The family slot for a row that is a per-day aggregate across families, by contract.

Named rather than left blank so the row states its own coarseness. A blank family on a row
that legitimately spans families is indistinguishable from a blank family on a row that lost
one, and this codebase has already paid for that distinction once, in D-14.
"""


class BookRegimeError(ValueError):
    """A book snapshot could not be summarised."""


def _int(book: Mapping[str, Any], key: str) -> int | None:
    value = book.get(key)
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class BookRegimeCalculator:
    """Streaming section 4.2 accumulator over full-book snapshots.

    One observation per snapshot, not per group: a group that changed nothing still leaves the
    book in a state, and a day's regime is the sequence of states the book was actually in.
    """

    def __init__(self, *, exact_cap: int | None = None, seed: int = 0) -> None:
        kwargs: dict[str, Any] = {"seed": seed}
        if exact_cap is not None:
            kwargs["exact_cap"] = exact_cap

        def measure(name: str, numerator: str, missingness: str):
            return StratifiedMeasure(
                name=name,
                declaration=Declaration(
                    numerator_formula=numerator,
                    population=(
                        "full-book snapshots within the day, role, continuity segment and "
                        "session phase; families are deliberately pooled, which is what a "
                        "per-day companion is"
                    ),
                    causal_cutoff="snapshot receive time (ts_recv_ns)",
                    status=RESOLVED,
                    missingness_rule=missingness,
                ),
                **kwargs,
            )

        self.spread = measure(
            "book_spread_raw",
            "best_ask - best_bid at the snapshot",
            "a snapshot with either side empty has no spread and is excluded and counted; a "
            "one-sided book has an undefined spread, never a zero one",
        )
        self.total_depth = measure(
            "book_total_depth",
            "bid_depth_full + ask_depth_full",
            "no exclusions; an empty book has depth zero, which is a measurement",
        )
        self.order_count = measure(
            "book_order_count",
            "bid_order_count_full + ask_order_count_full",
            "no exclusions; an empty book holds zero orders, which is a measurement",
        )
        self.level_count = measure(
            "book_level_count",
            "bid_price_level_count_full + ask_price_level_count_full",
            "no exclusions; an empty book occupies zero levels, which is a measurement",
        )
        self.relative_imbalance = measure(
            "relative_imbalance",
            "(bid_depth_full - ask_depth_full) / (bid_depth_full + ask_depth_full)",
            "a book with no depth on either side has no imbalance and is excluded and "
            "counted; zero would be a reading of balance and none was taken",
        )
        self.actions_per_group = measure(
            "actions_per_group",
            "count of raw actions in one F_LAST-closed group",
            "no exclusions; every closed group has at least one action",
        )

        self.snapshots = 0
        self.groups = 0
        self.max_actions_in_a_group = 0
        self.snapshots_without_a_spread = 0
        self.snapshots_without_depth = 0
        # The exact pair the contract asks for by name. Retained verbatim rather than
        # summarised: "first and last" is not a statistic and cannot be recovered from one.
        self._first: dict[str, dict[str, Any]] = {}
        self._last: dict[str, dict[str, Any]] = {}

    @property
    def measures(self) -> tuple[StratifiedMeasure, ...]:
        return (
            self.spread,
            self.total_depth,
            self.order_count,
            self.level_count,
            self.relative_imbalance,
            self.actions_per_group,
        )

    @staticmethod
    def _key(
        *,
        source_day: str,
        source_role: str,
        continuity_segment: int,
        session_phase: str,
        side_orientation: str = "BOTH",
    ) -> StratumKey:
        return StratumKey(
            source_day=source_day,
            source_role=source_role,
            continuity_segment=continuity_segment,
            family_id=DAY_COMPANION_FAMILY,
            side_orientation=side_orientation,
            session_phase=session_phase,
            clock=CAUSAL_CLOCK,
        )

    def observe_snapshot(
        self,
        book: Mapping[str, Any],
        *,
        source_day: str,
        source_role: str,
        continuity_segment: int,
        session_phase: str,
        recv_ns: int,
    ) -> dict[str, Any]:
        """Fold one full-book snapshot in and return what was read from it.

        Returns the extracted quantities rather than None so the caller can retain them on the
        exact member row: a summary with no member beneath it is not evidence, which is the
        rule the eighth gate already enforces for every other section.
        """
        if not isinstance(book, Mapping):
            raise BookRegimeError("a book snapshot must be a mapping")
        key = self._key(
            source_day=source_day,
            source_role=source_role,
            continuity_segment=continuity_segment,
            session_phase=session_phase,
        )
        self.snapshots += 1

        bid_depth = _int(book, "bid_depth_full") or 0
        ask_depth = _int(book, "ask_depth_full") or 0
        orders = (_int(book, "bid_order_count_full") or 0) + (_int(book, "ask_order_count_full") or 0)
        levels = (_int(book, "bid_price_level_count_full") or 0) + (
            _int(book, "ask_price_level_count_full") or 0
        )
        best_bid, best_ask = _int(book, "best_bid"), _int(book, "best_ask")

        self.total_depth.observe(key, float(bid_depth + ask_depth))
        self.order_count.observe(key, float(orders))
        self.level_count.observe(key, float(levels))

        # A one-sided book has an UNDEFINED spread. Recording zero would say the two sides
        # met, which is the opposite of what an absent side means - and it is the same error
        # shape that made 4.9 report an imbalance against a side that was not there.
        spread = None
        if best_bid is not None and best_ask is not None:
            spread = best_ask - best_bid
            self.spread.observe(key, float(spread))
        else:
            self.spread.exclude_missing(key)
            self.snapshots_without_a_spread += 1

        imbalance = None
        if bid_depth + ask_depth:
            imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth)
            self.relative_imbalance.observe(key, float(imbalance))
        else:
            self.relative_imbalance.exclude_missing(key)
            self.snapshots_without_depth += 1

        snapshot = {
            "recv_ns": int(recv_ns),
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread_raw": spread,
            "bid_depth": bid_depth,
            "ask_depth": ask_depth,
            "total_depth": bid_depth + ask_depth,
            "order_count": orders,
            "level_count": levels,
            "relative_imbalance": imbalance,
            "clock": CAUSAL_CLOCK,
        }
        day_key = f"{source_day}|{source_role}|{continuity_segment}|{session_phase}"
        self._first.setdefault(day_key, snapshot)
        # Last wins by arrival, not by comparison: the stream is forward-only on ts_recv_ns,
        # so the most recently seen snapshot IS the latest one, and re-deriving that by
        # comparing timestamps would invent a second ordering to disagree with the first.
        self._last[day_key] = snapshot
        return snapshot

    def observe_group_size(
        self,
        action_count: int,
        *,
        source_day: str,
        source_role: str,
        continuity_segment: int,
        session_phase: str,
    ) -> None:
        """One F_LAST-closed group's action count, for the companion the contract names."""
        if action_count <= 0:
            raise BookRegimeError("a closed group has at least one action")
        self.groups += 1
        self.max_actions_in_a_group = max(self.max_actions_in_a_group, int(action_count))
        self.actions_per_group.observe(
            self._key(
                source_day=source_day,
                source_role=source_role,
                continuity_segment=continuity_segment,
                session_phase=session_phase,
            ),
            float(action_count),
        )

    def first_last_pairs(self) -> list[dict[str, Any]]:
        """The exact first and last snapshot of each day-segment-phase, side by side."""
        rows = []
        for day_key in sorted(self._first):
            source_day, source_role, segment, session_phase = day_key.split("|")
            rows.append({
                "source_day": source_day,
                "source_role": source_role,
                "continuity_segment": int(segment),
                "session_phase": session_phase,
                "first_book": self._first[day_key],
                "last_book": self._last[day_key],
            })
        return rows

    def companion_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for measure in self.measures:
            rows.extend(measure.rows())
        return rows

    def summary(self) -> dict[str, Any]:
        return {
            "section": "4.2",
            "causal_clock": CAUSAL_CLOCK,
            "snapshots_observed": self.snapshots,
            "groups_observed": self.groups,
            "max_actions_in_a_group": self.max_actions_in_a_group,
            "snapshots_without_a_spread": self.snapshots_without_a_spread,
            "snapshots_without_depth": self.snapshots_without_depth,
            "first_last_pairs": self.first_last_pairs(),
            "family_pooling_note": (
                "this section pools families deliberately - it is a per-day companion by "
                "contract - and says so in the family slot rather than leaving a blank"
            ),
            "shared_estimand_note": (
                "relative_imbalance here is a THIRD computation of the estimand 4.9 and 4.12 "
                "also compute; that is what the cross-section gate reads, and three "
                "independent measurements from three substrates are what made a one-sided "
                "book detectable rather than merely present"
            ),
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
        }
