"""
odcore/io.py — load real collector bins into aligned channel arrays.

The durable collectors persist one-second bins to the data/* branches as
    {"<ts>.0": {"buy":.., "sell":.., "mid":.., "high":.., "low":.., "n_trades":..,
                "bid":.., "ask":.., ...}, ...}
(materialized locally under realbins/). This module is the single bins loader
(consolidating the 5 duplicate load_bars copies the plan calls out) and produces
numpy channel arrays on a regular integer-second grid so two sources can be aligned
for cross-venue / cross-asset operator pairs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np


@dataclass
class BinSeries:
    """Per-second channels for one (asset, venue) source, sorted + gap-filled."""
    ts: np.ndarray         # int seconds (regular grid)
    buy: np.ndarray        # taker-buy volume  (the OD H_a channel)
    sell: np.ndarray       # taker-sell volume (the OD H_b channel)
    mid: np.ndarray        # mid price (forward-filled across gaps)
    volume: np.ndarray     # buy + sell
    spread: np.ndarray     # ask - bid (0 where unavailable)
    n_trades: np.ndarray

    def __len__(self) -> int:
        return self.ts.size

    def log_return(self) -> np.ndarray:
        """Per-second log returns of mid (len matches ts; first element 0)."""
        m = np.where(self.mid > 0, self.mid, np.nan)
        lr = np.zeros_like(m)
        lr[1:] = np.log(m[1:] / m[:-1])
        return np.nan_to_num(lr, nan=0.0, posinf=0.0, neginf=0.0)

    def abs_return(self) -> np.ndarray:
        return np.abs(self.log_return())

    def resample(self, sec: int) -> "BinSeries":
        """Aggregate to `sec`-second bars: sum volumes, last mid, mean spread."""
        if sec <= 1:
            return self
        n = len(self) // sec
        if n < 2:
            return self
        def block(x, how):
            x = x[:n * sec].reshape(n, sec)
            return x.sum(axis=1) if how == "sum" else (
                x[:, -1] if how == "last" else x.mean(axis=1))
        return BinSeries(
            ts=self.ts[:n * sec:sec],
            buy=block(self.buy, "sum"), sell=block(self.sell, "sum"),
            mid=block(self.mid, "last"), volume=block(self.volume, "sum"),
            spread=block(self.spread, "mean"), n_trades=block(self.n_trades, "sum"))


def load_bins(path: str, mask_spikes: bool = False,
              spike_k: float = 20.0, spike_floor: float = 50.0) -> BinSeries:
    """Load a bins JSON file into a gap-filled BinSeries on a 1-second grid.

    Spike handling (the Kraken snapshot-replay residue): a reconnect dumped a
    whole replayed batch of already-counted trades into one wall-clock second,
    so a few seconds carry duplicated volume. Two guards, both keeping `mid`
    intact (only the inflated volume is removed):
      - any second carrying ``"_suspect": True`` (set by scripts/bins_integrity.py
        --normalize) has its buy/sell/n_trades zeroed, always; and
      - with ``mask_spikes=True`` (opt-in, for raw un-normalized files) seconds
        whose n_trades exceeds ``max(spike_k * median_nonzero, spike_floor)`` are
        zeroed too. Off by default so liquid-venue news bursts aren't masked.
    """
    with open(path) as fh:
        raw = json.load(fh)
    items = sorted((int(float(k)), v) for k, v in raw.items())
    if not items:
        raise ValueError(f"no bins in {path}")
    t0, t1 = items[0][0], items[-1][0]
    n = t1 - t0 + 1
    ts = np.arange(t0, t1 + 1, dtype=np.int64)
    buy = np.zeros(n); sell = np.zeros(n); mid = np.zeros(n)
    spread = np.zeros(n); ntr = np.zeros(n)
    for t, v in items:
        i = t - t0
        buy[i] = float(v.get("buy", 0.0) or 0.0)
        sell[i] = float(v.get("sell", 0.0) or 0.0)
        mid[i] = float(v.get("mid", 0.0) or 0.0)
        bid = v.get("bid"); ask = v.get("ask")
        if bid and ask:
            spread[i] = float(ask) - float(bid)
        ntr[i] = float(v.get("n_trades", 0.0) or 0.0)
        if v.get("_suspect"):              # repair tool already flagged this second
            buy[i] = sell[i] = ntr[i] = 0.0
    if mask_spikes:
        nz = ntr[ntr > 0]
        if nz.size:
            thr = max(spike_k * float(np.median(nz)), spike_floor)
            spike = ntr > thr
            buy[spike] = 0.0; sell[spike] = 0.0; ntr[spike] = 0.0
    # forward-fill mid across empty seconds (price persists; volume does not)
    last = 0.0
    for i in range(n):
        if mid[i] > 0:
            last = mid[i]
        elif last > 0:
            mid[i] = last
    return BinSeries(ts=ts, buy=buy, sell=sell, mid=mid, volume=buy + sell,
                     spread=spread, n_trades=ntr)


def align(a: BinSeries, b: BinSeries) -> tuple[BinSeries, BinSeries]:
    """Restrict two sources to their overlapping, common time grid (step-aware).

    Works whether the series are at 1-second or resampled (e.g. minute) cadence. Best
    practice is to align at 1s FIRST and resample afterwards so both grids share a phase;
    this function infers each series' step and clips by timestamp value rather than assuming
    a 1-second grid.
    """
    da = int(a.ts[1] - a.ts[0]) if len(a) > 1 else 1
    db = int(b.ts[1] - b.ts[0]) if len(b) > 1 else 1
    if da != db:
        raise ValueError(f"align requires equal cadence (got {da}s vs {db}s); "
                         "align at 1s before resampling")
    step = da
    lo = max(int(a.ts[0]), int(b.ts[0]))
    hi = min(int(a.ts[-1]), int(b.ts[-1]))
    if hi <= lo:
        raise ValueError("sources do not overlap in time")

    def clip(s: BinSeries) -> BinSeries:
        i0 = (lo - int(s.ts[0])) // step
        i1 = (hi - int(s.ts[0])) // step + 1
        return BinSeries(s.ts[i0:i1], s.buy[i0:i1], s.sell[i0:i1], s.mid[i0:i1],
                         s.volume[i0:i1], s.spread[i0:i1], s.n_trades[i0:i1])
    ca, cb = clip(a), clip(b)
    n = min(len(ca), len(cb))  # guard off-by-one from differing phases
    def trunc(s):
        return BinSeries(s.ts[:n], s.buy[:n], s.sell[:n], s.mid[:n], s.volume[:n],
                         s.spread[:n], s.n_trades[:n])
    return trunc(ca), trunc(cb)
