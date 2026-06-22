"""
odcore/validation.py — the honesty layer: walk-forward CV, real costs, baselines.

RECONSTRUCTED-FROM-CLAUDE.md. Cites:
  - Random k-fold OVERSTATES OOS on correlated time series; chemistry (stationary) is the
    only domain with positive block-CV (INFO-026 l.617). So we use WALK-FORWARD/block CV with
    an embargo, and report the random-vs-walkforward GAP as a stationarity signature.
  - Result Discipline (l.104-143): every result is one data point; catalog misses as carefully
    as hits; a signal is promoted only if it beats baselines net of cost.
  - Tautology-killing null (INFO-066): an edge must survive shuffling the signal/return pairing.

No synthetic data: all inputs are real per-bar returns + signals from the engine.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class BacktestMetrics:
    n: int
    n_trades: int
    hit_rate: float
    gross_return: float
    net_return: float
    sharpe: float          # annualized-ish (per-bar sharpe * sqrt(bars))
    max_drawdown: float
    avg_win: float
    avg_loss: float


def backtest_signal(returns: np.ndarray, signal: np.ndarray, fee_bps: float = 1.0,
                    slippage_bps: float = 1.0) -> BacktestMetrics:
    """Apply a per-bar signal in {-1,0,+1} to the NEXT bar's return, net of costs.

    Cost (fee + slippage, in bps) is charged on every change in position size. Returns and
    signal are aligned so signal[t] earns returns[t+1].
    """
    returns = np.asarray(returns, dtype=float)
    signal = np.asarray(signal, dtype=float)
    n = min(returns.size - 1, signal.size)
    sig = signal[:n]
    fwd = returns[1:n + 1]
    gross = sig * fwd
    turns = np.abs(np.diff(np.concatenate([[0.0], sig])))
    cost = turns * ((fee_bps + slippage_bps) * 1e-4)
    net = gross - cost

    traded = sig != 0
    n_trades = int(np.sum(turns > 0))
    wins = net[traded & (net > 0)]
    losses = net[traded & (net < 0)]
    hit = float(len(wins) / max(1, np.sum(traded)))
    equity = np.cumsum(net)
    peak = np.maximum.accumulate(equity) if equity.size else np.array([0.0])
    mdd = float(np.max(peak - equity)) if equity.size else 0.0
    sd = net.std()
    sharpe = float(net.mean() / sd * np.sqrt(n)) if sd > 1e-12 else 0.0
    return BacktestMetrics(
        n=n, n_trades=n_trades, hit_rate=hit,
        gross_return=float(gross.sum()), net_return=float(net.sum()),
        sharpe=sharpe, max_drawdown=mdd,
        avg_win=float(wins.mean()) if wins.size else 0.0,
        avg_loss=float(losses.mean()) if losses.size else 0.0)


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


def random_vs_walkforward_gap(returns: np.ndarray, signal: np.ndarray, fee_bps: float = 1.0,
                              slippage_bps: float = 1.0, n_folds: int = 5,
                              seed: int = 0) -> dict:
    """Report walk-forward OOS sharpe vs random-k-fold sharpe; the GAP is a stationarity
    signature (INFO-026: large gap => non-stationary, random-CV is optimistic)."""
    n = min(returns.size - 1, signal.size)
    # walk-forward (out-of-sample test folds only)
    wf = []
    for _, (ts, te) in walk_forward_splits(n, n_folds):
        m = backtest_signal(returns[ts:te + 1], signal[ts:te], fee_bps, slippage_bps)
        wf.append(m.sharpe)
    # random k-fold
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    rk = []
    fold = n // n_folds
    for i in range(n_folds):
        sel = np.sort(idx[i * fold:(i + 1) * fold])
        m = backtest_signal(returns, _masked(signal, sel, n), fee_bps, slippage_bps)
        rk.append(m.sharpe)
    wf_m, rk_m = float(np.mean(wf)) if wf else 0.0, float(np.mean(rk)) if rk else 0.0
    return {"walkforward_sharpe": wf_m, "random_sharpe": rk_m, "gap": rk_m - wf_m}


def _masked(signal: np.ndarray, sel: np.ndarray, n: int) -> np.ndarray:
    out = np.zeros(n)
    out[sel] = signal[sel]
    return out


def tautology_signal_null(returns: np.ndarray, signal: np.ndarray, fee_bps: float = 1.0,
                          slippage_bps: float = 1.0, n_null: int = 200, seed: int = 0) -> dict:
    """Circular-shift the signal vs returns n_null times; z of the real net return vs null.
    A real edge survives; a tautology/overfit collapses to the null."""
    real = backtest_signal(returns, signal, fee_bps, slippage_bps).net_return
    rng = np.random.default_rng(seed)
    n = signal.size
    nulls = np.empty(n_null)
    for i in range(n_null):
        shift = int(rng.integers(1, n - 1))
        nulls[i] = backtest_signal(returns, np.roll(signal, shift), fee_bps, slippage_bps).net_return
    mu, sd = float(nulls.mean()), float(nulls.std())
    z = (real - mu) / sd if sd > 1e-12 else 0.0
    return {"real_net": real, "null_mean": mu, "null_std": sd, "z": z}
