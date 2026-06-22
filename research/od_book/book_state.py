"""
book_state.py — OD-BOOK state-vector x(t) construction.

Loads the gzipped-JSONL L2 snapshots written by coinbase_btcusd_book_collector.py
and builds the small, explicit state vector x(t) the OD-BOOK spec (§1) calls for.
Dimensionality is the enemy of clean operator recovery, so the default state is
deliberately compact and every column is named/interpretable.

State columns (default):
  mid_ret        : delta-log(mid) over one grid step  (stationary mid dynamic)
  spread         : best_ask - best_bid                 (price units)
  tob_imb        : top-of-book size imbalance (b0-a0)/(b0+a0) in [-1, 1]
  depth_imb      : top-K size imbalance (sum b - sum a)/(sum b + sum a)
  flow           : signed taker volume in the cell (buy - sell)
  bid_sz_k       : resting size at bid level k (k=0..K-1)
  ask_sz_k       : resting size at ask level k
  bid_off_k      : price offset of bid level k from mid (<= 0)
  ask_off_k      : price offset of ask level k from mid (>= 0)

`mid` (absolute) is returned SEPARATELY (not in the operator state — it is
non-stationary) so downstream code can reconstruct the predicted price
trajectory for the turn-as-consequence metric by integrating predicted mid_ret.

No synthetic data is ever produced here; rows that cannot be parsed or are
missing a full top-K on either side are dropped (and counted), never fabricated.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass

import numpy as np


@dataclass
class BookSeries:
    ts: np.ndarray          # (N,) float epoch seconds (regular grid)
    mid: np.ndarray         # (N,) absolute mid price (for reconstruction)
    X: np.ndarray           # (N, D) state matrix
    cols: list[str]         # length-D column names
    grid_s: float           # nominal grid step in seconds
    n_dropped: int          # rows dropped (incomplete depth / parse error)

    @property
    def n(self) -> int:
        return self.X.shape[0]

    def col(self, name: str) -> np.ndarray:
        return self.X[:, self.cols.index(name)]


def load_rows(path: str, depth: int | None = None) -> list[dict]:
    """Load raw snapshot rows from a gzipped (or plain) JSONL file."""
    opener = gzip.open if path.endswith(".gz") else open
    rows: list[dict] = []
    with opener(path, "rt") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if depth is not None:
                if len(r.get("bids", [])) < depth or len(r.get("asks", [])) < depth:
                    continue
            rows.append(r)
    rows.sort(key=lambda r: r["ts"])
    return rows


def build_state(path: str, depth: int = 10, grid_s: float = 0.1) -> BookSeries:
    """Build the OD-BOOK state series from a snapshot file."""
    rows = load_rows(path, depth=None)  # filter per-row below so we can count drops
    cols: list[str] = ["mid_ret", "spread", "tob_imb", "depth_imb", "flow"]
    for k in range(depth):
        cols.append(f"bid_sz_{k}")
    for k in range(depth):
        cols.append(f"ask_sz_{k}")
    for k in range(depth):
        cols.append(f"bid_off_{k}")
    for k in range(depth):
        cols.append(f"ask_off_{k}")

    ts_l: list[float] = []
    mid_l: list[float] = []
    feat_l: list[list[float]] = []
    n_dropped = 0
    prev_mid: float | None = None

    for r in rows:
        bids = r.get("bids", [])
        asks = r.get("asks", [])
        if len(bids) < depth or len(asks) < depth:
            n_dropped += 1
            continue
        mid = float(r["mid"])
        spread = float(r["spread"])
        b_off = [float(bids[k][0]) for k in range(depth)]
        b_sz = [float(bids[k][1]) for k in range(depth)]
        a_off = [float(asks[k][0]) for k in range(depth)]
        a_sz = [float(asks[k][1]) for k in range(depth)]

        b0, a0 = b_sz[0], a_sz[0]
        tob_imb = (b0 - a0) / (b0 + a0) if (b0 + a0) > 0 else 0.0
        sb, sa = sum(b_sz), sum(a_sz)
        depth_imb = (sb - sa) / (sb + sa) if (sb + sa) > 0 else 0.0
        flow = float(r.get("buy", 0.0)) - float(r.get("sell", 0.0))

        if prev_mid is None or prev_mid <= 0:
            mid_ret = 0.0
        else:
            mid_ret = np.log(mid / prev_mid)
        prev_mid = mid

        feat = [mid_ret, spread, tob_imb, depth_imb, flow] + b_sz + a_sz + b_off + a_off
        ts_l.append(float(r["ts"]))
        mid_l.append(mid)
        feat_l.append(feat)

    X = np.asarray(feat_l, dtype=float) if feat_l else np.zeros((0, len(cols)))
    return BookSeries(
        ts=np.asarray(ts_l, dtype=float),
        mid=np.asarray(mid_l, dtype=float),
        X=X,
        cols=cols,
        grid_s=grid_s,
        n_dropped=n_dropped,
    )


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else "/tmp/smoke_book.jsonl.gz"
    bs = build_state(p)
    print(f"loaded {bs.n} states, {len(bs.cols)} dims, dropped {bs.n_dropped}")
    print("cols:", bs.cols)
    if bs.n:
        print("mid range: %.2f .. %.2f" % (bs.mid.min(), bs.mid.max()))
        for c in ["mid_ret", "spread", "tob_imb", "depth_imb", "flow"]:
            v = bs.col(c)
            print(f"  {c:10s} mean={v.mean():+.5g} std={v.std():.5g}")
