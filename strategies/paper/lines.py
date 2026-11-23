"""The two lines at each sided print (Part A), made by CALLING crypto_ng.tick.reads and tick.line as they are.

Only those two functions and the constants LINE_NS, LEAN_NS, NONE are used (Greg, 2026-11-23, point G2). The time is
the feed's own (milliseconds made into ns), ordered by time then sequence (S1); the lines are made from the prints
that carry a side (S4); `until` is the latest sided print's time plus one. Recomputed over the kept arrays at every
print: correctness first.

EMPTY (nothing traded in the span) is kept apart from zero. MISSING (G3): until a span of feed time has passed since
the first print seen, that line reads MISSING; so does a hump whose start falls there.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from crypto_ng import tick
from strategies.paper.events import PRINT

EMPTY, MISSING = 'EMPTY', 'MISSING'
ON_TRADE, AT_MOMENT, CUT = 'on a trade', 'at a moment trades only left', 'MISSING: cut at the start'


def sign_of(v) -> Optional[int]:
    """+1 / -1 / 0 (zero or EMPTY); None for MISSING."""
    if v == MISSING:
        return None
    if v == EMPTY:
        return 0
    return int(np.sign(v))


@dataclass(frozen=True)
class LineState:
    idx: int                      # index of this print among all prints seen
    exh: object                   # 20-second line at this print: float, EMPTY or MISSING
    dip: object                   # 60-second line at this print
    dip_before: object            # 60-second line at the read just before this print's read
    hump: Optional[dict]          # the hump of the 20-second line in being: side, began_read, began_kind, began_idx, began_here
    hump_ends: tuple              # humps that ended since the previous sided print: dict(..., at_print, known_late)
    late: tuple                   # S5 moments since the previous sided print: dict(moment_ns, exh, dip)
    unsided_since: int            # prints with no side seen since the previous sided print


class LiveLines:
    def __init__(self):
        self.t, self.buy, self.size, self.keys = [], [], [], []
        self.first_time = None
        self.n_prints = self.n_unsided = self.n_sided = self.n_no_size = 0
        self.n20 = self.n60 = 0                      # reads already handed on
        self.cur = None                              # the hump in being
        self.last_side = 'start'                     # sign of the previous 20-second read; None = MISSING
        self.unsided_since = 0
        self.log = []                                # (sided index, exh, dip) at each sided print, for the checks

    def _value(self, r, quiet, flow, k, span):
        if int(r['moment'][k]) - self.first_time < span:
            return MISSING
        return EMPTY if quiet[k] else float(flow[k])

    def on_print(self, p: PRINT, idx: int) -> Optional[LineState]:
        self.n_prints += 1
        if self.first_time is None:
            self.first_time = p.time_ns
        if p.side is None:
            self.n_unsided += 1
            self.unsided_since += 1
            return None
        if p.size is None:
            self.n_no_size += 1                      # a missing input: not in the lines, counted
            self.unsided_since += 1
            return None
        key = (p.time_ns, p.sequence)
        if self.keys and key < self.keys[-1]:
            raise ValueError(f'print {p.place} is earlier in feed time than one already read: the lines cannot be '
                             f'kept causal (STOP)')
        self.keys.append(key)
        self.t.append(p.time_ns); self.buy.append(p.side == 'B'); self.size.append(int(p.size))
        self.n_sided += 1
        t, buy, size = np.array(self.t, np.int64), np.array(self.buy, bool), np.array(self.size, np.int64)
        until = p.time_ns + 1
        r20 = tick.reads(t, buy, size, tick.LINE_NS, until)
        r60 = tick.reads(t, buy, size, tick.LEAN_NS, until)
        f20, q20 = tick.line(r20['bought'], r20['sold'])
        f60, q60 = tick.line(r60['bought'], r60['sold'])
        mine = self.n_sided - 1
        assert r20['trade'][-1] == mine and r60['trade'][-1] == mine
        v20 = lambda k: self._value(r20, q20, f20, k, tick.LINE_NS)
        v60 = lambda k: self._value(r60, q60, f60, k, tick.LEAN_NS)
        # S5: moments since the previous print at which trades only left a span, with both lines at each
        moments = sorted({int(r20['moment'][k]) for k in range(self.n20, len(r20['moment'])) if r20['trade'][k] == tick.NONE}
                         | {int(r60['moment'][k]) for k in range(self.n60, len(r60['moment'])) if r60['trade'][k] == tick.NONE})
        late = []
        for m in moments:
            a, b = int(np.searchsorted(r20['moment'], m, 'right')) - 1, int(np.searchsorted(r60['moment'], m, 'right')) - 1
            late.append(dict(moment_ns=m, exh=v20(a), dip=v60(b)))
        # humps over the new reads of the 20-second line
        begins, ends = [], []
        for k in range(self.n20, len(r20['moment'])):
            val = v20(k)
            s, at_trade = sign_of(val), r20['trade'][k] != tick.NONE
            if s is None:
                self.last_side = None
                continue
            if self.cur is not None and self.cur['side'] == s and s != 0:
                self.last_side = s
                continue
            if self.cur is not None:
                ends.append(dict(self.cur, ended_read=k, ended_ns=int(r20['moment'][k]), at_print=bool(at_trade),
                                 known_late=not at_trade))
                self.cur = None
            if s != 0:
                kind = CUT if self.last_side is None else (ON_TRADE if at_trade else AT_MOMENT)
                self.cur = dict(side=s, began_read=k, began_kind=kind, began_ns=int(r20['moment'][k]),
                                began_idx=idx if at_trade else None)
                begins.append(self.cur)
            self.last_side = s
        self.n20, self.n60 = len(r20['moment']), len(r60['moment'])
        k20, k60 = len(r20['moment']) - 1, len(r60['moment']) - 1
        dip_before = v60(k60 - 1) if k60 >= 1 else MISSING
        exh, dip = v20(k20), v60(k60)
        hump = None
        if self.cur is not None:
            hump = dict(self.cur, began_here=any(b is self.cur for b in begins))
        state = LineState(idx, exh, dip, dip_before, hump, tuple(ends), tuple(late), self.unsided_since)
        self.unsided_since = 0
        self.log.append((mine, exh, dip, int(r20['trade'][-1]), r20['moment'][-1], r60['moment'][-1]))
        return state
