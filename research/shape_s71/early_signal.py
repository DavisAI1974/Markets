"""
early_signal.py — the forward-looking order-book "early signal" (entry filter + direction).

TIMES / PROVENANCE
------------------
  File written        : 2026-07-08 08:32 UTC
  Validated on venue  : Coinbase Exchange L2 books (public). Also intended for KRAKEN
                        (format-compatible; RE-FIT direction_sign per venue — see below).
  Forward-test data windows (Coinbase L2 book, 1s grid, out-of-sample tail):
    BTC  2026-06-22 06:11 -> 2026-06-30 10:27 UTC   (196h)
    ETH  2026-06-29 11:49 -> 2026-07-02 04:05 UTC   ( 64h)
    SOL  2026-06-29 11:49 -> 2026-07-03 15:08 UTC   ( 99h)
    XRP  2026-06-29 11:49 -> 2026-07-05 14:40 UTC   (147h)
    DOGE 2026-06-29 11:49 -> 2026-07-03 14:49 UTC   ( 99h)
  All results below are from these single windows -> provisional; re-validate on the
  accruing multi-window / multi-venue data before sizing.

WHAT THIS IS
------------
A portable, dependency-free reader that turns an L2 order-book snapshot into:
  * a MAGNITUDE / conviction  -> the FILTER  ("a real move is leaning in")
  * a SIGN / direction        -> the DIRECTION ("+1 = long, -1 = short")

It is designed to be used as the ENTRY signal. The magnitude decides *whether* to
arm a trade; the sign decides *which way*.

EMPIRICAL PROVENANCE (forward-tested on real Coinbase L2 books, 2026-07-08)
--------------------------------------------------------------------------
Signal = proximity-weighted net depth imbalance across the top-K book:
    imb = (Sum_bid w*size  -  Sum_ask w*size) / (Sum_bid w*size + Sum_ask w*size)
    with proximity weight  w = 1 / (1 + |price - mid|)   (near levels dominate)

Measured, out-of-sample, on the resting book (data/<coin>-book, ~40h/coin):
  * The book LEADS price: cross-correlation peaks at lag +1s (forward), not lag 0.
  * Full top-K depth beats top-of-book (the whole-book lean carries more than L1).
  * DIRECTION is real: sign(imb) predicts the next move.
        BTC 57% / ETH 55% OOS directional hit @15s   -> HIGH weight
        SOL flat (~37%, book uninformative)          -> ZERO the book here
        XRP / DOGE ~coin-flip accuracy, big gross     -> LOW weight, stack only
  * Net-of-cost: alive only at the 0% maker floor; the ride-to-reversal exit
    (wide ~30 bps trailing stop, ~10 min holds) was the first net-positive config
    (+7.4 bps/trade @ 0% maker, +5.4 @ 2 bps taker) on the BTC window.

IMPORTANT SCOPE
---------------
This is the SCALAR depth read — a validated *lower bound* on the edge. It is NOT
the two-piece whole-curve shape-match gate. Intended use: the entry FILTER/trigger,
to be STACKED with (or deferred to) the real shape gate where that code is available.
Per the platform rule, deploy PER CELL (asset x venue x side) and weight by the
per-coin accuracy above — do not trade the weak cells standalone.

USAGE
-----
    from early_signal import EarlySignalTracker

    trk = EarlySignalTracker(k=10, roll=120, enter_z=1.0, direction_sign=+1)
    # each new book snapshot (bids/asks as [[price, size], ...], best first):
    sig = trk.update(bids, asks)          # -> EarlySignal
    if sig.enter:                         # magnitude filter passed
        side = sig.direction              # +1 long / -1 short  <-- the direction signal
        # ... arm your entry / shape-gate confirmation here ...

Raw stateless read (no rolling baseline):
    from early_signal import early_signal
    sig = early_signal(bids, asks, k=10, direction_sign=+1)
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Sequence


# ---- tuned defaults (from the forward tests; re-fit per cell before sizing) ----
DEFAULT_K            = 10      # book levels per side to weigh
DEFAULT_ROLL         = 120     # rolling-baseline window (samples) for the z-score
DEFAULT_ENTER_Z      = 1.0     # |z| threshold to arm an entry (conviction gate)
DIRECTION_SIGN       = +1      # +1: bid-heavy book -> LONG (fit on Coinbase BTC/ETH).
                               # RE-FIT PER VENUE x CELL: the sign can differ on Kraken
                               # (different queue dynamics). To fit: on a train window,
                               # sgn = +1 if mean(sign(imb_t) * ret_{t->t+60s}) >= 0 else -1.
# exit-side reference constants (not used for entry; documented for the caller)
TRAIL_BPS_DEFAULT    = 30.0    # ride-to-reversal trailing stop that was net-positive
MAX_HOLD_S_DEFAULT   = 600     # hard cap on hold if no reversal
BEST_HORIZON_S       = 60      # the horizon where the signal was fattest


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _norm_levels(levels: Sequence) -> list[tuple[float, float]]:
    """Normalize a book side to [(price, size), ...] (best price first).

    Venue-agnostic — accepts every common shape:
      * Coinbase level2 REST : [[price, size, n_orders], ...]
      * Kraken public Depth  : [[price, volume, timestamp], ...]   (index 0/1 -> price/size)
      * Kraken WS v2 book    : [{"price": .., "qty": ..}, ...]      (dict form)
      * generic / our bins   : [[price, size], ...]
    Best price must be first in the list (Coinbase and Kraken both return it that way)."""
    out = []
    for lv in levels or []:
        if lv is None:
            continue
        if isinstance(lv, dict):                       # Kraken WS v2 dict entries
            price = _num(lv.get("price"))
            size = _num(lv.get("qty", lv.get("volume", lv.get("size", 0.0))))
        else:                                          # list/tuple: [price, size, ...]
            price = _num(lv[0])
            size = _num(lv[1]) if len(lv) > 1 else 0.0
        if size > 0:
            out.append((price, size))
    return out


def book_imbalance(bids: Sequence, asks: Sequence, k: int = DEFAULT_K,
                   mid: Optional[float] = None) -> dict:
    """Proximity-weighted net depth imbalance across the top-k book (the early signal core).

    Returns a dict with the signed imbalance in [-1, +1] plus the pieces, so a caller
    can also inspect the two sides separately (the 'two-piece' read is with_depth vs
    against_depth — this function reports both; the real shape gate matches their curves).
    """
    b = _norm_levels(bids)[:max(k, 1)]
    a = _norm_levels(asks)[:max(k, 1)]
    if not b or not a:
        return {"imb": 0.0, "bid_depth": 0.0, "ask_depth": 0.0, "mid": mid or 0.0, "ok": False}

    if mid is None:
        mid = (b[0][0] + a[0][0]) / 2.0

    def wsum(levels):
        s = 0.0
        for price, size in levels:
            off = abs(price - mid)          # distance from mid, in price units
            s += size / (1.0 + off)         # proximity weight: near levels dominate
        return s

    wb = wsum(b)   # with/bid-side weighted depth
    wa = wsum(a)   # against/ask-side weighted depth
    denom = wb + wa
    imb = (wb - wa) / denom if denom > 0 else 0.0
    return {"imb": imb, "bid_depth": wb, "ask_depth": wa, "mid": mid, "ok": True}


def early_signal(bids: Sequence, asks: Sequence, k: int = DEFAULT_K,
                 mid: Optional[float] = None, direction_sign: int = DIRECTION_SIGN) -> "EarlySignal":
    """Stateless one-shot read of a single book snapshot (no rolling baseline -> zscore=0,
    enter=False). Use EarlySignalTracker for a live stream where the entry gate arms."""
    bk = book_imbalance(bids, asks, k, mid)
    if not bk["ok"]:
        return EarlySignal(False, bk["mid"], 0.0, 0.0, 0.0, 0, False)
    ds = 1 if direction_sign >= 0 else -1
    value = bk["imb"] * ds
    direction = +1 if value > 0 else (-1 if value < 0 else 0)
    return EarlySignal(
        ok=True, mid=bk["mid"], value=value, conviction=abs(value),
        zscore=0.0, direction=direction, enter=False,
        bid_depth=bk["bid_depth"], ask_depth=bk["ask_depth"],
    )


@dataclass
class EarlySignal:
    ok: bool                 # book was well-formed
    mid: float               # mid used
    value: float             # signed early signal in [-1, +1] (already * direction_sign)
    conviction: float        # |value|  (raw magnitude filter)
    zscore: float            # value vs rolling baseline (relative conviction)
    direction: int           # +1 long / -1 short / 0 flat  <-- THE DIRECTION SIGNAL
    enter: bool              # magnitude/z gate passed -> arm an entry
    bid_depth: float = 0.0
    ask_depth: float = 0.0


class EarlySignalTracker:
    """Stateful early-signal reader. Feed it book snapshots in time order; it maintains a
    rolling baseline so 'strong lean' is relative to the recent regime (adapts across venues
    and volatility). `update()` returns an EarlySignal with both the entry gate and direction.
    """

    def __init__(self, k: int = DEFAULT_K, roll: int = DEFAULT_ROLL,
                 enter_z: float = DEFAULT_ENTER_Z, direction_sign: int = DIRECTION_SIGN,
                 min_conviction: float = 0.0):
        self.k = k
        self.enter_z = enter_z
        self.direction_sign = 1 if direction_sign >= 0 else -1
        self.min_conviction = min_conviction
        self._hist: deque[float] = deque(maxlen=roll)

    # absolute floor on the baseline std (in imbalance units, range [-1,1]); prevents a
    # dead/flat book (near-zero variance) from producing spurious huge-z entries -> in a
    # DEPLETED market the signal stays small and no entry arms, which is the correct behavior.
    SD_FLOOR = 0.02

    def _z(self, x: float) -> float:
        n = len(self._hist)
        if n < 5:
            return 0.0
        m = sum(self._hist) / n
        var = sum((v - m) ** 2 for v in self._hist) / n
        sd = max(math.sqrt(var), self.SD_FLOOR)
        return (x - m) / sd

    def update(self, bids: Sequence, asks: Sequence,
               mid: Optional[float] = None) -> EarlySignal:
        bk = book_imbalance(bids, asks, self.k, mid)
        if not bk["ok"]:
            return EarlySignal(False, bk["mid"], 0.0, 0.0, 0.0, 0, False)

        raw = bk["imb"]                       # signed book lean
        value = raw * self.direction_sign     # orient so +value -> long
        z = self._z(raw)                      # baseline computed on RAW (pre-orientation)
        self._hist.append(raw)

        conviction = abs(value)
        # direction: sign of the oriented value
        direction = 0
        if value > 0:
            direction = +1
        elif value < 0:
            direction = -1

        # entry gate: relative conviction (z) AND optional absolute floor
        enter = (abs(z) >= self.enter_z) and (conviction >= self.min_conviction) and direction != 0
        # z sign follows raw; orient the entry direction by direction_sign
        if enter:
            direction = (+1 if (z * self.direction_sign) > 0 else -1)

        return EarlySignal(
            ok=True, mid=bk["mid"], value=value, conviction=conviction,
            zscore=z * self.direction_sign, direction=direction, enter=enter,
            bid_depth=bk["bid_depth"], ask_depth=bk["ask_depth"],
        )


def fit_direction_sign(books: Optional[Sequence] = None,
                       mids: Optional[Sequence[float]] = None,
                       imbalances: Optional[Sequence[float]] = None,
                       horizon: int = BEST_HORIZON_S,
                       k: int = DEFAULT_K,
                       min_conviction: float = 0.0) -> dict:
    """Fit `direction_sign` for ONE venue x cell from a time-ordered series (e.g. Kraken BTC).

    Inputs (provide EITHER books, OR imbalances+mids):
      books      : list of (bids, asks) snapshots on a REGULAR grid (e.g. 1-sec), time-ordered.
      mids       : optional list of mid prices aligned with the series; if omitted and `books`
                   is given, mids are taken from best bid/ask.
      imbalances : optional precomputed signed imbalances (skip re-reading the books).
      horizon    : forward steps (in grid units) to score against. Default 60 (= 60s on a 1s
                   grid), the horizon where the signal was fattest.
      min_conviction : ignore samples with |imbalance| below this when fitting.

    Returns dict:
      sign            : +1 or -1  -> pass to EarlySignalTracker(direction_sign=...)
      hit_rate        : OOS-style directional accuracy of the fitted sign (0..1)
      mean_signed_bps : mean forward bps if you follow the fitted direction
      n               : samples scored
      recommend       : per-cell weight suggestion ('HIGH' / 'LOW' / 'ZERO-flat')

    Fit rule (matches the header): sign = +1 if mean(sign(imb_t)*ret_{t->t+h}) >= 0 else -1.
    Interpretation guide (from the Coinbase windows): hit >= 0.54 -> HIGH weight;
    0.50-0.54 -> LOW (stack only); < 0.50 or ~flat -> ZERO the book on this cell.
    """
    # build imbalance + mid arrays
    imb: list[float] = []
    mid_arr: list[float] = []
    if imbalances is not None:
        imb = [_num(x) for x in imbalances]
        if mids is None:
            raise ValueError("provide `mids` alongside `imbalances`")
        mid_arr = [_num(m) for m in mids]
    elif books is not None:
        for i, snap in enumerate(books):
            bids, asks = snap
            m = _num(mids[i]) if mids is not None else None
            bk = book_imbalance(bids, asks, k, m)
            imb.append(bk["imb"] if bk["ok"] else 0.0)
            mid_arr.append(bk["mid"])
    else:
        raise ValueError("provide either `books` or `imbalances`+`mids`")

    n = len(imb)
    if n <= horizon + 5:
        return {"sign": DIRECTION_SIGN, "hit_rate": float("nan"),
                "mean_signed_bps": float("nan"), "n": 0, "recommend": "INSUFFICIENT"}

    # forward log-return in bps over `horizon` grid steps
    def logret_bps(a, b):
        if a <= 0 or b <= 0:
            return 0.0
        return math.log(b / a) * 1e4

    score = 0.0
    used = 0
    for t in range(n - horizon):
        if abs(imb[t]) < min_conviction:
            continue
        si = 1.0 if imb[t] > 0 else (-1.0 if imb[t] < 0 else 0.0)
        if si == 0.0:
            continue
        fr = logret_bps(mid_arr[t], mid_arr[t + horizon])
        score += si * fr
        used += 1
    sign = 1 if score >= 0 else -1

    # diagnostics with the fitted sign applied
    hits = 0
    signed_bps = 0.0
    scored = 0
    for t in range(n - horizon):
        if abs(imb[t]) < min_conviction:
            continue
        si = 1.0 if imb[t] > 0 else (-1.0 if imb[t] < 0 else 0.0)
        if si == 0.0:
            continue
        pos = sign * si
        fr = logret_bps(mid_arr[t], mid_arr[t + horizon])
        if fr != 0.0:
            hits += 1 if (pos > 0) == (fr > 0) else 0
            signed_bps += pos * fr
            scored += 1
    hit_rate = hits / scored if scored else float("nan")
    mean_bps = signed_bps / scored if scored else float("nan")
    if hit_rate != hit_rate:            # NaN
        rec = "INSUFFICIENT"
    elif hit_rate >= 0.54:
        rec = "HIGH"
    elif hit_rate >= 0.50:
        rec = "LOW"
    else:
        rec = "ZERO-flat"
    return {"sign": sign, "hit_rate": hit_rate, "mean_signed_bps": mean_bps,
            "n": scored, "recommend": rec}


# ------------------------------- optional live demo -------------------------------
if __name__ == "__main__":
    # Sanity-check against a live Coinbase public book (no API key needed).
    # Prints the early signal + direction for BTC and ETH. Requires `requests` + network.
    import sys
    try:
        import requests
    except ImportError:
        print("demo needs `requests`; the module itself has no dependencies.")
        sys.exit(0)

    # Coinbase demo (Kraken works too: GET api.kraken.com/0/public/Depth?pair=XBTUSD ->
    # result[pair]["bids"/"asks"] = [[price, volume, timestamp], ...], handled as-is).
    trackers = {p: EarlySignalTracker() for p in ("BTC-USD", "ETH-USD")}
    for prod, trk in trackers.items():
        try:
            r = requests.get(
                f"https://api.exchange.coinbase.com/products/{prod}/book?level=2",
                timeout=10,
            )
            book = r.json()
            sig = trk.update(book["bids"], book["asks"])
            arrow = {1: "LONG", -1: "SHORT", 0: "flat"}[sig.direction]
            print(f"{prod}: value={sig.value:+.4f} conviction={sig.conviction:.4f} "
                  f"z={sig.zscore:+.2f} direction={arrow} (enter={sig.enter})  mid={sig.mid:.2f}")
            print("       NOTE: single snapshot -> z=0 (no baseline yet); feed a stream to arm entries.")
        except Exception as e:  # noqa: BLE001
            print(f"{prod}: demo fetch failed ({e})")
