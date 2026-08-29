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

**Not handled: exchange holidays.** A CME holiday shifts trade dates, and no holiday
calendar is consulted here. The roster (2021-10-01 to 10-05) contains none - Columbus Day
was 10-11 - so this is a declared gap rather than a latent bug, and it must be closed before
this module is used on any window that spans one.

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

**Not handled, declared rather than latent:** exchange holidays (no calendar is consulted;
the roster contains none), and the special settlement procedure the same document applies on
the last two trading days of the front month.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
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
    """
    ts_ns = int(ts_ns)
    day = local_date(ts_ns)
    candidate = day + timedelta(days=1) if ts_ns >= reopen_instant_ns(day) else day
    while candidate.weekday() >= SATURDAY:
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
    """
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
