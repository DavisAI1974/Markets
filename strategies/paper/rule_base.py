"""The rule interface (Part A). No I/O, no clock, no tastytrade knowledge.

A rule is given, at each SIDED print, a read-only Snapshot and returns a list of signals: OPEN or CLOSE. A print with
no side is never given to a rule (rule 5). Facts of the runs and legs that became known at earlier prints with no side
come with the next snapshot marked here=False: they may close a trade (late) but never open one. S5 moments come in
`lines.late` and hump ends known late in `lines.hump_ends` (known_late=True); a rule opens nothing on them (rule 6).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Optional

from strategies.paper.events import PRINT
from strategies.paper.lines import EMPTY, MISSING, LineState

BUY, SELL = 'BUY', 'SELL'
RIGHT, WRONG, NEITHER = 'right', 'wrong', 'neither'
UNDECIDED = 'undecided: both happened at one print'


@dataclass(frozen=True)
class Snapshot:
    print: PRINT
    idx: int
    lines: LineState
    run_facts: tuple               # dicts; here=True for those made at this print
    leg_facts: tuple
    quote_missing: bool            # this print had no bid or no offer
    quote_at_print: Callable       # idx -> (bid, offer) of an earlier print
    own_open: MappingProxyType = MappingProxyType({})


@dataclass(frozen=True)
class OPEN:
    rule: str
    trade_id: str
    side: str
    trigger: dict


@dataclass(frozen=True)
class CLOSE:
    rule: str
    trade_id: str
    reason: str
    verdict: Optional[str] = None  # right / wrong / neither, only where the rule says so
    known_late: bool = False
    detail: Optional[dict] = None


class Rule:
    code = '??'
    title = ''
    runs = True

    def __init__(self):
        self.counts = dict(armed=0, opened=0, closed=0, same_key_skipped=0)
        self.missing_counts = {}
        self.trades = {}           # trade id -> its state
        self.keys = set()          # rule 2: what a trade was opened on
        self._n = 0

    # counting
    def arm(self):
        self.counts['armed'] += 1

    def missing(self, name):
        self.missing_counts[name] = self.missing_counts.get(name, 0) + 1

    def open(self, side, key, trigger, **state):
        if key in self.keys:
            self.counts['same_key_skipped'] += 1
            return []
        self.keys.add(key)
        self._n += 1
        tid = f'{self.code}-{self._n:04d}'
        self.trades[tid] = dict(state, side=side, key=key)
        self.counts['opened'] += 1
        return [OPEN(self.code, tid, side, dict(trigger))]

    def close(self, tid, reason, verdict=None, known_late=False, detail=None):
        self.trades.pop(tid)
        self.counts['closed'] += 1
        return [CLOSE(self.code, tid, reason, verdict, known_late, detail)]

    def step(self, snap: Snapshot) -> list:
        return self.decide(snap)

    def decide(self, snap: Snapshot) -> list:
        raise NotImplementedError


def side_of_run(direction: str) -> str:
    return BUY if direction == 'up' else SELL


def when(f: dict) -> tuple:
    """Order of two moments: feed time, then print index (a late moment has idx -1)."""
    return (f['time_ns'], f['idx'])
