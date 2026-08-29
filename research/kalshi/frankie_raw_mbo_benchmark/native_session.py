"""Section 2 session segmentation and trading-day assignment (decision D6a, 2026-08-29).

Section 2 says a session boundary starts a new continuity segment, and segments decide
where lifecycles are censored, where runs restart and where replenishment horizons are cut.
Nothing in the tree defined a boundary, so `continuity_segment` was whatever a caller
passed. This module defines it.

**Two boundaries, not one.** They are separate fields in `StratumKey` and they fall at
different instants:

* `continuity_segment` - THE BOOK RESET. CME Globex energy closes for an hour, 16:00-17:00
  America/Chicago, and that hour-long close is the reset: the resting book is withdrawn and
  the next session starts a new one. Confirmed on our own tape, per day rather than pooled -
  20211001 ends on a group at `21:00:00.253Z`, 20211004 carries 430 `C` components closing
  on `N` at `21:00:00.078Z`, and 20211005 carries 581 at `21:00:00.078Z`. 21:00 UTC is what
  16:00 CT resolves to under CDT. 20211003 shows no such group because it is a Sunday and
  has no close, only the reopen - the one roster day that omits the boundary is the one that
  should.

* `trade_day` - the CME trade date, which begins at 17:00 CT on the previous calendar day
  and runs to 16:00 CT. Taken from the exchange rather than from the power-market HE1..HE24
  operating day, because the object here is an exchange order book.

**The boundary is written in exchange local time on purpose.** Pinning the literal 21:00 UTC
would reproduce this roster and then be silently one hour wrong from 2021-11-07, inside the
source window `20211001_20211101`'s own neighbourhood.

**The Sunday fold is not an exception, it is the definition.** Sunday 17:00 CT is the start
of Monday's trade date by CME's own rule, so 20211003's evening session carries the
20211004 trade date without a hand-coded special case. The S104 Sunday fold and the CME
convention are the same rule.

**Segment and trade date coincide.** Each CME trade date is exactly one continuous book -
opened at 17:00 CT, liquidated at the 16:00 CT close - so `continuity_segment` is the trade
date's ordinal rather than a second, competing anchor. The 16:00-17:00 CT halt window
belongs to the OUTGOING trade date: the withdrawal group is the terminal event of the
session it liquidates, not the first event of the next one.

**Exchange holidays are consulted** (closed 2026-08-29; Greg: "we follow cme trading day
schedule"). `is_trading_day` reads the CME energy holiday class from `plant_calendar`, which
generates it from rules rather than a date table - necessary here, because the roster year
is 2021 and the committed table starts in 2025. A `full_closure` is not a trade date and is
skipped by the same loop that skips a Saturday. A `partial_session` or `early_close` IS a
trade date, because the book opens; but its CLOSE TIME is recorded nowhere in this
repository and a partial session runs no settlement cycle at all, so `phase_within` refuses
on those dates instead of answering from the ordinary hours. The roster contains no holiday,
so nothing in the launch window raises.

**Phase (D6b)** is derived from the same authority. Every boundary below is stated by the
exchange, none is fitted to our tape:

* the daily close at 16:00 CT and reopen at 17:00 CT (CME Globex energy hours), and
* the settlement window, which the NYMEX Energy Futures Daily Settlement Procedure fixes for
  NG as **14:28:00 to 14:30:00 Eastern Time** - "settled by CME Group staff based solely
  upon trading activity on CME Globex" in that window.

Those two carve the trade date into `PRE_OPEN`, `PRE_SETTLEMENT`, `SETTLEMENT`,
`POST_SETTLEMENT` and `POST_CLOSE`. Note the settlement window is defined in **Eastern**
time while the session is defined in **Central**; each is resolved in the zone the exchange
states it in rather than converted, so neither drifts on its own.

`CARRIED_PHASES` is a **starting vocabulary, not a validator**. Per the open-world rule,
`session_phase` is not checked against a closed set anywhere in this tree, and it must stay
that way: a novel phase rounded into the nearest carried label looks like a confirmation of
the label rather than a discovery.

**Not handled, declared rather than latent:** the shortened close time on a
`partial_session` / `early_close` (refused rather than guessed, above), and the special
settlement procedure the same document applies on the last two trading days of the front
month.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from typing import Any, Iterable, Iterator, Mapping
from zoneinfo import ZoneInfo

EXCHANGE_TZ = ZoneInfo("America/Chicago")
EXCHANGE_TZ_NAME = "America/Chicago"

CLOSE_LOCAL_TIME = time(16, 0)
"""Daily close. The book reset."""

REOPEN_LOCAL_TIME = time(17, 0)
"""Daily reopen, one hour after the close. A continuity segment begins here."""

SETTLEMENT_TZ = ZoneInfo("America/New_York")
SETTLEMENT_TZ_NAME = "America/New_York"

SETTLEMENT_START_ET = time(14, 28)
SETTLEMENT_END_ET = time(14, 30)
"""NG daily settlement window, per the NYMEX Energy Futures Daily Settlement Procedure."""

PRE_OPEN = "PRE_OPEN"
PRE_SETTLEMENT = "PRE_SETTLEMENT"
SETTLEMENT = "SETTLEMENT"
POST_SETTLEMENT = "POST_SETTLEMENT"
POST_CLOSE = "POST_CLOSE"

CARRIED_PHASES = (PRE_OPEN, PRE_SETTLEMENT, SETTLEMENT, POST_SETTLEMENT, POST_CLOSE)
"""Where phase discovery STARTS. Not a closed set - see the open-world note above."""

SATURDAY = 5
NS_PER_SECOND = 1_000_000_000
EPOCH = date(1970, 1, 1)


FULL_CLOSURE = "full_closure"
PARTIAL_SESSION = "partial_session"
EARLY_CLOSE = "early_close"

SHORTENED_CLASSES = frozenset({PARTIAL_SESSION, EARLY_CLOSE})
"""Classes on which the exchange closes before 16:00 CT. The trade date still exists."""


class SessionError(ValueError):
    """A group could not be assigned to a continuity segment or trading day."""


def _local_instant_ns(day: date, local_time: time, tz: ZoneInfo = EXCHANGE_TZ) -> int:
    local = datetime.combine(day, local_time, tzinfo=tz)
    return int(local.astimezone(timezone.utc).timestamp()) * NS_PER_SECOND


def close_instant_ns(day: date) -> int:
    """The 16:00 CT close on `day`, as UTC epoch nanoseconds."""
    return _local_instant_ns(day, CLOSE_LOCAL_TIME)


def reopen_instant_ns(day: date) -> int:
    """The 17:00 CT reopen on `day`, as UTC epoch nanoseconds."""
    return _local_instant_ns(day, REOPEN_LOCAL_TIME)


def settlement_window_ns(day: date) -> tuple[int, int]:
    """The 14:28:00-14:30:00 ET settlement window on `day`, half-open, in UTC epoch ns.

    Resolved in Eastern time because that is the zone the settlement procedure states, not
    converted from the Central-time session hours.
    """
    return (
        _local_instant_ns(day, SETTLEMENT_START_ET, SETTLEMENT_TZ),
        _local_instant_ns(day, SETTLEMENT_END_ET, SETTLEMENT_TZ),
    )


def session_open_ns(trading_day: date) -> int:
    """The reopen that starts `trading_day`: 17:00 CT on the preceding calendar day.

    For a Monday that is the Sunday 17:00 CT reopen, which is why the Sunday fold needs no
    special case.
    """
    return reopen_instant_ns(trading_day - timedelta(days=1))


def _local_datetime(ts_ns: int) -> datetime:
    seconds, _ = divmod(int(ts_ns), NS_PER_SECOND)
    return datetime.fromtimestamp(seconds, tz=timezone.utc).astimezone(EXCHANGE_TZ)


def local_date(ts_ns: int) -> date:
    """The America/Chicago calendar date of an epoch-nanosecond instant."""
    return _local_datetime(ts_ns).date()


def trade_day(ts_ns: int) -> date:
    """The CME trade date: 17:00 CT on the previous calendar day through 16:00 CT.

    The weekend roll is the same rule continued rather than a second one - no trade date
    falls on a Saturday or Sunday, so a candidate landing there advances to the Monday. That
    is what makes the Sunday 17:00 CT reopen carry Monday's date.

    A CME `full_closure` advances by that identical rule: it is not a trade date either, so
    it is skipped rather than special-cased. This is what makes the Christmas-evening reopen
    fall out instead of needing a clause - an instant at 18:00 CT on a closed Christmas is
    already past that day's reopen, so the candidate has advanced to the 26th before the
    skip loop is reached, and those trades carry the 26th, which is the trade date they
    settle into.
    """
    ts_ns = int(ts_ns)
    day = local_date(ts_ns)
    candidate = day + timedelta(days=1) if ts_ns >= reopen_instant_ns(day) else day
    while not is_trading_day(candidate):
        candidate += timedelta(days=1)
    return candidate


def session_phase(ts_ns: int) -> str:
    """The exchange-defined phase of the trade date this instant belongs to."""
    ts_ns = int(ts_ns)
    return phase_within(ts_ns, trade_day(ts_ns))


def phase_within(ts_ns: int, day: date) -> str:
    """`session_phase` for a caller that already knows the trade date.

    Split out because resolving the trade date costs several timezone conversions and the
    traversal is 4.26M groups: the streaming path resolves it once and passes it here.
    Ordered from the outside in - before the session opened, after it closed, then the
    settlement window and the two legs around it.

    REFUSES on a shortened trade date, rather than answering from the ordinary hours. Two
    independent facts are missing, and each alone would make the answer wrong:

    * The close is earlier than 16:00 CT and no source in this repository records by how
      much. Reusing 16:00 would put `POST_CLOSE` hours late - present, typed, plausible and
      wrong, which is the S108 off-instrument and S109 `session_b_share` shape exactly.
    * On a `partial_session` the exchange runs NO settlement cycle at all. The three
      settlement-derived phases do not merely shift, they do not exist, so there is no
      correct carried label to return. Rounding into the nearest one would be the failure
      the open-world rule names: a novel state reported as a confirmation of a carried one.

    The roster (2021-10-01 to 10-05) contains no such date, so this raises nowhere in the
    launch window. It converts a latent wrong answer into a loud one for any wider window.
    """
    klass = holiday_class(day)
    if klass in SHORTENED_CLASSES:
        raise SessionError(
            f"{day.isoformat()} is a CME {klass}; its close time is not recorded in this "
            "repository and a partial_session has no settlement cycle, so no phase can be "
            "resolved from the ordinary 16:00 CT / 14:28 ET boundaries"
        )
    if ts_ns < session_open_ns(day):
        return PRE_OPEN
    if ts_ns >= close_instant_ns(day):
        return POST_CLOSE
    settle_start, settle_end = settlement_window_ns(day)
    if ts_ns >= settle_end:
        return POST_SETTLEMENT
    if ts_ns >= settle_start:
        return SETTLEMENT
    return PRE_SETTLEMENT


def continuity_segment(ts_ns: int) -> int:
    """Absolute segment ordinal: days since epoch of the trade date.

    Each CME trade date is exactly one continuous book, so the segment IS the trade date.
    Absolute rather than run-relative, so two runs over overlapping windows agree on what
    segment a group is in and a segment id means the same thing across source days.
    """
    return segment_of(trade_day(ts_ns))


def segment_of(day: date) -> int:
    """`continuity_segment` for a caller that already knows the trade date."""
    return (day - EPOCH).days


@lru_cache(maxsize=None)
def _holiday_classes(year: int) -> Mapping[str, str]:
    """CME energy holiday classes for `year`, keyed by ISO date.

    Sourced from `plant_calendar.holidays`, which generates them from RULES - the nth
    weekday, the observation rule, and the computus for Good Friday - rather than from a
    date table. That matters here for two reasons. The roster year is 2021 and
    `flow_calendar.CME_HOLIDAYS` only begins at 2025-09-01, so a table lookup would report
    "not a holiday" for every date in the source window: present, boolean and wrong, which
    is the S112 finding about a table that runs out. And the rules are verified - they
    reproduce all 16 committed entries with zero mismatches, and additionally generate four
    real early closes the hand-kept table omits.

    Imported lazily because `plant_calendar` mutates `sys.path` at import time; the cache
    means that happens once per year of the window rather than per group.
    """
    from research.kalshi.plant_calendar import holidays as _rule_holidays

    return {iso: cls for iso, (_name, cls) in _rule_holidays(year).items()}


def holiday_class(day: date) -> str | None:
    """The CME energy holiday class of `day`, or None on an ordinary day."""
    return _holiday_classes(day.year).get(day.isoformat())


def is_trading_day(day: date) -> bool:
    """Whether the exchange opens a book bearing `day` as its trade date.

    A `full_closure` has no Globex session at all, so it is not a trade date and carries no
    continuity segment - the same status as a Saturday, reached by the same rule.

    A `partial_session` or `early_close` IS a trading day: the book opens and trades. Note
    `flow_calendar` calls a partial session "NOT a business day", which is the
    SETTLEMENT-counting sense used for expiry arithmetic. This module segments an order
    book, so the question is whether the book is open, and it is. Business day and trading
    day are different predicates and conflating them would move every expiry-adjacent
    segment by a day.
    """
    return day.weekday() < SATURDAY and holiday_class(day) != FULL_CLOSURE


def group_event_ns(group: Mapping[str, Any]) -> int:
    """A group's first component event time.

    Session membership is an exchange fact about when something happened, so it reads
    `ts_event_ns`. Section 4.5 requires economic interpretation to stay separate from a
    serialization/feed explanation; `ts_recv_ns` remains the causal clock for availability.
    """
    actions = group.get("raw_actions")
    if not isinstance(actions, list) or not actions:
        raise SessionError("group carries no raw_actions")
    return int(actions[0]["ts_event_ns"])


@dataclass
class SessionSegmenter:
    """Forward-only segment and trading-day assignment over an ordered group stream.

    Holds no forward window, matching the traversal discipline in `native_clocks`: refusing
    non-monotonic input is what makes the assignment a property of the traversal rather than
    a rule applied to the output afterwards.
    """

    _last_event_ns: int | None = None
    _last_segment: int | None = None
    _boundaries_crossed: int = 0

    def assign(self, ts_event_ns: int) -> dict[str, Any]:
        ts_event_ns = int(ts_event_ns)
        if self._last_event_ns is not None and ts_event_ns < self._last_event_ns:
            raise SessionError(
                "group event times are not monotonic; segmentation is a forward-only pass"
            )
        day = trade_day(ts_event_ns)
        segment = segment_of(day)
        if self._last_segment is not None and segment != self._last_segment:
            self._boundaries_crossed += 1
        self._last_event_ns = ts_event_ns
        self._last_segment = segment
        return {
            "continuity_segment": segment,
            "trade_day": day.strftime("%Y%m%d"),
            "session_phase": phase_within(ts_event_ns, day),
        }

    def assign_group(self, group: Mapping[str, Any]) -> dict[str, Any]:
        return self.assign(group_event_ns(group))

    @property
    def boundaries_crossed(self) -> int:
        """Segment transitions seen so far. Zero on a single-segment run."""
        return self._boundaries_crossed


def segment_stream(groups: Iterable[Mapping[str, Any]]) -> Iterator[dict[str, Any]]:
    """Segment assignments for an ordered group stream.

    A generator, not a list: the roster is 4.26M groups and this module holds no forward
    window anywhere else either.
    """
    segmenter = SessionSegmenter()
    for group in groups:
        yield segmenter.assign_group(group)


@dataclass
class AssignmentLedger:
    """Reconciles the segment and phase a traversal USED against the exchange rule.

    This exists because a field-level check cannot catch the failure it guards. A driver
    that passes one constant `session_phase` for every group emits a value that is present,
    non-empty, correctly typed and entirely plausible, and every stratum silently collapses
    into one - the parallel-view rule broken without a single test going red. S108 and S109
    both ended at the same conclusion: only comparison against an INDEPENDENT source settles
    a wrong-but-well-formed input.

    So the traversal reports what it actually put in the stratum key, and this recomputes it
    from the group's own event time. Degeneracy needs no separate check: a constant phase
    across a span that crosses an exchange boundary shows up here as a mismatch.
    """

    observed: int = 0
    segment_mismatches: list[dict[str, Any]] = field(default_factory=list)
    phase_mismatches: list[dict[str, Any]] = field(default_factory=list)
    segment_mismatch_count: int = 0
    phase_mismatch_count: int = 0
    segment_histogram: Counter = field(default_factory=Counter)
    phase_histogram: Counter = field(default_factory=Counter)
    _sample_cap: int = 20

    def observe(
        self, *, ts_event_ns: int, continuity_segment: int, session_phase: str
    ) -> None:
        ts_event_ns = int(ts_event_ns)
        self.observed += 1
        day = trade_day(ts_event_ns)
        expected_segment = segment_of(day)
        expected_phase = phase_within(ts_event_ns, day)
        # D60: `expected_phase` and `expected_segment` were computed for every group and
        # discarded unless they mismatched, so the stratum denominators the parallel-view rule
        # depends on were never counted anywhere.
        self.phase_histogram[expected_phase] += 1
        self.segment_histogram[expected_segment] += 1
        if continuity_segment != expected_segment:
            # D60: the count and the sample list used to be the SAME capped list, so twenty
            # mismatches and twenty million both reported 20 - and the denominators gate
            # printed that number for a wholly broken run.
            self.segment_mismatch_count += 1
            self._note(self.segment_mismatches, ts_event_ns, continuity_segment, expected_segment)
        if session_phase != expected_phase:
            self.phase_mismatch_count += 1
            self._note(self.phase_mismatches, ts_event_ns, session_phase, expected_phase)

    def _note(self, bucket: list[dict[str, Any]], ts_ns: int, used: Any, expected: Any) -> None:
        if len(bucket) < self._sample_cap:
            bucket.append({"ts_event_ns": ts_ns, "used": used, "expected": expected})

    @property
    def mismatches(self) -> int:
        return len(self.segment_mismatches) + len(self.phase_mismatches)

    @property
    def distinct_phases_expected(self) -> int:
        """How many phases the exchange rule says this span should contain.

        Reported, never gated on: a legitimately short slice sits inside one phase, and a
        threshold here would label a correct run as broken.
        """
        return len({row["expected"] for row in self.phase_mismatches}) or 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "assignments_observed": self.observed,
            "segment_mismatches": self.segment_mismatch_count,
            "segment_mismatch_samples": list(self.segment_mismatches),
            "segment_histogram": dict(self.segment_histogram),
            "phase_histogram": dict(self.phase_histogram),
            "phase_mismatches": self.phase_mismatch_count,
            "phase_mismatch_samples": list(self.phase_mismatches),
            "segment_mismatch_samples": list(self.segment_mismatches),
            "phase_mismatch_samples": list(self.phase_mismatches),
            "basis": "recomputed from ts_event_ns via the CME session rule (D6)",
        }
