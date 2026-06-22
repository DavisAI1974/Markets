"""odcore/incremental.py — O(1)-amortized rolling order-flow operator for the live hot path.

The Architect's cheapest latency win (S36b): the live turn-detector's order-flow imbalance + exhaustion do
NOT need a from-scratch window recompute each tick. Maintain a rolling state — each bin is added once,
crosses the half-window boundary once, and is evicted once → O(1) AMORTIZED per tick. Same math as the
batch operator (proven by `_canary_incremental.py`), but the work leaves the hot path.

Splits the window into equal-TIME halves (late = the newer half) for the exhaustion read
(|imb_late| < |imb_early| = the dipole collapsing toward 0.5, the leader weakening). Equal-time halves are
the natural incremental split and match `odcore.info_dipole.divergence`'s intent.
"""
from __future__ import annotations

from collections import deque


class RollingFlow:
    """Feed (ts, buy_vol, sell_vol) per tick; read imbalance() and exhausting() in O(1)."""

    def __init__(self, window_s: float):
        self.W = float(window_s)
        self.h = self.W / 2.0
        self.early: deque = deque()   # older half  [now-W, now-W/2)
        self.late: deque = deque()    # newer half  [now-W/2, now]
        self.eB = self.eS = self.lB = self.lS = 0.0

    def update(self, ts: float, buy: float, sell: float) -> "RollingFlow":
        self.late.append((ts, buy, sell)); self.lB += buy; self.lS += sell
        h0 = ts - self.h
        while self.late and self.late[0][0] < h0:            # age newer→older half
            t, b, s = self.late.popleft(); self.lB -= b; self.lS -= s
            self.early.append((t, b, s)); self.eB += b; self.eS += s
        w0 = ts - self.W
        while self.early and self.early[0][0] < w0:           # evict past the window
            t, b, s = self.early.popleft(); self.eB -= b; self.eS -= s
        while self.late and self.late[0][0] < w0:             # edge case: tiny window
            t, b, s = self.late.popleft(); self.lB -= b; self.lS -= s
        return self

    @staticmethod
    def _imb(B: float, S: float) -> float:
        t = B + S
        return (B - S) / t if t > 0 else 0.0

    def imbalance(self) -> float:
        return self._imb(self.eB + self.lB, self.eS + self.lS)

    def imb_early(self) -> float:
        return self._imb(self.eB, self.eS)

    def imb_late(self) -> float:
        return self._imb(self.lB, self.lS)

    def exhausting(self) -> bool:
        return abs(self.imb_late()) < abs(self.imb_early())

    def n(self) -> int:
        return len(self.early) + len(self.late)
