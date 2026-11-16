"""
odcore/validation.py: walk-forward splits with an embargo.

Random k-fold overstates out-of-sample results on correlated time series, so splits are expanding-window
walk-forward with an embargo gap. The cost-charging backtest, the random-vs-walk-forward gap and the
net-return null that used to live here were removed on 2026-11-16 (Greg): trade cost is not a market
condition, and no bitcoin-era trade rule is carried forward.
"""

from __future__ import annotations


def walk_forward_splits(n: int, n_folds: int = 5, embargo: int = 50):
    """Expanding-window walk-forward splits with an embargo gap (prevents leakage from
    overlapping windows in correlated series)."""
    fold = n // (n_folds + 1)
    for i in range(1, n_folds + 1):
        train_end = fold * i
        test_start = min(n, train_end + embargo)
        test_end = min(n, train_end + fold)
        if test_end - test_start < 10:
            continue
        yield (0, train_end), (test_start, test_end)
