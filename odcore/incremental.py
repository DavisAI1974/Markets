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

EPS = 1e-12


class IncrementalQuietGate:
    """Causal, O(1)/tick port of `odcore.quiet_floor.QuietFloor` for the live hot path (S43 NEXT #4).

    The batch `QuietFloor.gate()` needs the whole imbalance array (floor_hat reads imb[t-1] over a
    vector). In production the turn-detector sees one imbalance value at a time, so this holds the
    FITTED (phi, c, sigma) and just the PREVIOUS imbalance, reproducing the gate one tick at a time:

        floor_hat(t) = phi*imb(t-1) + c          (the quiet relaxation expectation)
        innov(t)     = imb(t) - floor_hat(t)      (~0 between trades, spikes on a shock)
        gate open    <=>  |innov(t)| > k*sigma

    Greg (S42/S43): the imbalance LEVEL carries DIRECTION (sign), the gate decides WHEN to fire so the
    live dipole stops churning through a trend (the level stays elevated and slowly relaxes → the floor
    absorbs it → small innovation → gate stays shut). Fit OFFLINE per cell on training quiet cells
    (`odcore.quiet_floor.fit`), then feed the learned coefficients here. No look-ahead: the gate at t
    uses only imb(t) and the prior imb(t-1).
    """

    def __init__(self, phi: float, c: float, sigma: float, k: float = 1.5):
        self.phi = float(phi)
        self.c = float(c)
        self.sigma = float(sigma)
        self.k = float(k)
        self._prev: float | None = None   # imb(t-1); None until the first tick

    @classmethod
    def from_floor(cls, floor, k: float = 1.5) -> "IncrementalQuietGate":
        """Build from a fitted `odcore.quiet_floor.QuietFloor`."""
        return cls(phi=floor.phi, c=floor.c, sigma=floor.sigma, k=k)

    def innovation(self, imb: float) -> float:
        """imb(t) minus the quiet floor; for the first tick the floor is imb itself (innov 0)."""
        if self._prev is None:
            return 0.0
        return float(imb) - (self.phi * self._prev + self.c)

    def update(self, imb: float) -> bool:
        """Advance one tick. Returns whether the gate is OPEN (a shock broke the quiet floor)."""
        innov = self.innovation(imb)
        self._prev = float(imb)
        return abs(innov) > self.k * (self.sigma + EPS)

    def gated_signal(self, imb: float) -> float:
        """The deploy form: sign(level) for DIRECTION, but 0 (stand aside) unless the gate is open.

        Call ONCE per tick (it advances the rolling previous-imbalance state)."""
        imb = float(imb)
        open_ = self.update(imb)
        if not open_:
            return 0.0
        return 1.0 if imb > 0 else (-1.0 if imb < 0 else 0.0)


class RollingFlow:
    """Feed (ts, buy_vol, sell_vol) per tick; read imbalance() and exhausting() in O(1).

    Optionally pass a fitted `IncrementalQuietGate` to gate the live dipole: `gated_signal()` then
    returns sign(imbalance) only on a shock that breaks the quiet relaxation floor, else 0 — the
    production turn-detector with the QuietFloor wired in (S43 NEXT #4)."""

    def __init__(self, window_s: float, gate: "IncrementalQuietGate | None" = None):
        self.W = float(window_s)
        self.h = self.W / 2.0
        self.early: deque = deque()   # older half  [now-W, now-W/2)
        self.late: deque = deque()    # newer half  [now-W/2, now]
        self.eB = self.eS = self.lB = self.lS = 0.0
        self.gate = gate

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

    def gated_signal(self) -> float:
        """The live dipole with the QuietFloor wired in: sign(imbalance) only when the attached gate
        is open (a shock broke the quiet relaxation floor), else 0. Requires a gate; advances its
        per-tick state, so call ONCE per tick after update()."""
        if self.gate is None:
            raise ValueError("RollingFlow has no gate; pass IncrementalQuietGate to enable gated_signal()")
        return self.gate.gated_signal(self.imbalance())

    def n(self) -> int:
        return len(self.early) + len(self.late)
