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

Phase (`session_phase`) is deliberately NOT assigned here - see D6b, still open.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

EXCHANGE_TZ = ZoneInfo("America/Chicago")
EXCHANGE_TZ_NAME = "America/Chicago"

CLOSE_LOCAL_TIME = time(16, 0)
"""Daily close. The book reset."""

REOPEN_LOCAL_TIME = time(17, 0)
"""Daily reopen, one hour after the close. A continuity segment begins here."""

SATURDAY = 5
NS_PER_SECOND = 1_000_000_000


class SessionError(ValueError):
    """A group could not be assigned to a continuity segment or trading day."""


def _local_instant_ns(day: date, local_time: time) -> int:
    local = datetime.combine(day, local_time, tzinfo=EXCHANGE_TZ)
    return int(local.astimezone(timezone.utc).timestamp()) * NS_PER_SECOND


def close_instant_ns(day: date) -> int:
    """The 16:00 CT close on `day`, as UTC epoch nanoseconds."""
    return _local_instant_ns(day, CLOSE_LOCAL_TIME)


def reopen_instant_ns(day: date) -> int:
    """The 17:00 CT reopen on `day`, as UTC epoch nanoseconds."""
    return _local_instant_ns(day, REOPEN_LOCAL_TIME)


def _local_datetime(ts_ns: int) -> datetime:
    seconds, _ = divmod(int(ts_ns), NS_PER_SECOND)
    return datetime.fromtimestamp(seconds, tz=timezone.utc).astimezone(EXCHANGE_TZ)


def local_date(ts_ns: int) -> date:
    """The America/Chicago calendar date of an epoch-nanosecond instant."""
    return _local_datetime(ts_ns).date()


def in_halt_window(ts_ns: int) -> bool:
    """True inside the 16:00-17:00 CT close, when the book is down.

    Labelled rather than refused: a group landing here is informative - it means either the
    halt assumption needs revisiting or the tape carries post-close administrative traffic -
    and silently absorbing it into a session would hide that.
    """
    local = _local_datetime(ts_ns)
    return CLOSE_LOCAL_TIME <= local.time() < REOPEN_LOCAL_TIME


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


def continuity_segment(ts_ns: int) -> int:
    """Absolute segment ordinal: days since epoch of the trade date.

    Each CME trade date is exactly one continuous book, so the segment IS the trade date.
    Absolute rather than run-relative, so two runs over overlapping windows agree on what
    segment a group is in and a segment id means the same thing across source days.
    """
    return (trade_day(ts_ns) - date(1970, 1, 1)).days


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
        segment = continuity_segment(ts_event_ns)
        if self._last_segment is not None and segment != self._last_segment:
            self._boundaries_crossed += 1
        self._last_event_ns = ts_event_ns
        self._last_segment = segment
        return {
            "continuity_segment": segment,
            "trade_day": trade_day(ts_event_ns).strftime("%Y%m%d"),
            "in_halt_window": in_halt_window(ts_event_ns),
        }

    def assign_group(self, group: Mapping[str, Any]) -> dict[str, Any]:
        return self.assign(group_event_ns(group))

    @property
    def boundaries_crossed(self) -> int:
        """Segment transitions seen so far. Zero on a single-segment run."""
        return self._boundaries_crossed


def segment_stream(groups: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Convenience: segment assignments for an ordered group stream."""
    segmenter = SessionSegmenter()
    return [segmenter.assign_group(group) for group in groups]
