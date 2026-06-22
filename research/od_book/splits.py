"""
splits.py — walk-forward, time-ordered split discipline for OD-BOOK.

NON-NEGOTIABLE (spec §1): time-ordered, no shuffling across the boundary. Random
shuffling is exactly the leakage mode that produced the unvalidated 0.993/FN=0
algebraic-dipole result. Every split here is contiguous in time; an assertion
refuses any split where a train index is >= a test index.

  T_train : recover the operator / fit the champion
  T_val   : tune hyperparameters (VAR order, DMD rank, ridge alpha, horizons)
  T_test  : touched EXACTLY ONCE, at the end, after the KILL gate is frozen.

The walk_forward() generator yields rolling (train, test) blocks for the
operator-stability diagnostic (does the recovered A keep getting recovered, or
does it wander?).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Split:
    train: np.ndarray   # contiguous int indices
    val: np.ndarray
    test: np.ndarray

    def assert_ordered(self) -> None:
        if len(self.train) and len(self.val):
            assert self.train.max() < self.val.min(), "train/val overlap or out of order"
        if len(self.val) and len(self.test):
            assert self.val.max() < self.test.min(), "val/test overlap or out of order"
        if len(self.train) and len(self.test):
            assert self.train.max() < self.test.min(), "train/test overlap or out of order"


def three_way(n: int, frac_train: float = 0.6, frac_val: float = 0.2) -> Split:
    """Contiguous train/val/test split by time order."""
    assert 0 < frac_train < 1 and 0 < frac_val < 1
    assert frac_train + frac_val < 1, "leave room for test"
    i_tr = int(n * frac_train)
    i_va = int(n * (frac_train + frac_val))
    s = Split(
        train=np.arange(0, i_tr),
        val=np.arange(i_tr, i_va),
        test=np.arange(i_va, n),
    )
    s.assert_ordered()
    return s


def walk_forward(n: int, n_windows: int = 8, train_frac: float = 0.5,
                 embargo: int = 0):
    """Yield (train_idx, test_idx) rolling blocks, time-ordered, non-overlapping
    test segments. `embargo` drops a gap between train and test to avoid
    autocorrelation leakage at the boundary."""
    assert n_windows >= 2
    seg = n // (n_windows + 1)
    if seg <= 1:
        return
    train_len = max(1, int(seg * (n_windows) * train_frac))
    for w in range(n_windows):
        test_start = (w + 1) * seg
        test_end = (w + 2) * seg if w < n_windows - 1 else n
        train_start = max(0, test_start - train_len - embargo)
        train_end = test_start - embargo
        if train_end - train_start < 2 or test_end - test_start < 1:
            continue
        train_idx = np.arange(train_start, train_end)
        test_idx = np.arange(test_start, test_end)
        assert train_idx.max() < test_idx.min(), "walk-forward leakage"
        yield train_idx, test_idx


def lagged_pairs(idx: np.ndarray, horizon: int):
    """Given a contiguous index block, return (src, dst) index arrays for the
    map x(t) -> x(t+horizon), staying WITHIN the block (no cross-boundary pairs)."""
    if len(idx) <= horizon:
        return np.array([], dtype=int), np.array([], dtype=int)
    src = idx[:-horizon]
    dst = idx[horizon:]
    return src, dst
