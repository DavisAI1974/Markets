"""
scripts/od_trade_dipole_run.py — S23 runner: fit + validate the chem-dipole trade
predictor on REAL labeled trades (zero synthetic data).

Pipeline
--------
1. LABELED TRADES. For each source in realbins/, regenerate labeled trades by replaying
   the adaptive_backtester generators on the source's MINUTE bars (ALL generators incl.
   the dipole generator, pooled -- Greg's S23 call, to confirm the data/numbers are
   current). Each fired equilibrium-chunk entry is a trade:
       entry_ts = chunks[t].bars[-1].ts            (minute-aligned epoch sec)
       gross    = direction * log(p_exit / p_entry)   (chunk last closes)
       net      = gross - fee_bps/1e4               (matches GeneratorTracker.record)
       label    = +1 if net > 0 else -1             (win/lose by NET P&L)
   Deduped by (source, entry_ts, direction) so N generators agreeing is one trade.

2. PRE-ENTRY DIPOLE VECTOR. For each trade, slice the orderflow window
   [entry_ts - pre_entry, entry_ts] from the SAME source's 1-second BinSeries
   (buy vs sell) and build the 15-feature coupling vector c_i via
   dipole_trade.trade_coupling_vector.  (This is the expensive step -> built ONCE.)

3. POSITIVE CONTROL (in-sample). Build in-sample win/lose centroids, fit
   H_a^2 = a + b*(H_a*H_b) + c*(H_a*H_b)^2. Reference: a=0.007 b=-0.093 c=1.309 R^2=0.943
   (original 128-dim, RAW, no standardization).

   *** STANDARDIZATION CAVEAT (surfaced by running this) ***
   The S22 port standardizes c_i per feature (subtract pool mean / divide pool std) because
   our 15 features are heterogeneous. But subtracting the POOL MEAN zero-centers the pool,
   which forces  n_win*c_win + n_lose*c_lose = 0  -> the two centroids are EXACTLY antiparallel
   -> H_a == -H_b for every trade -> H_a^2 == -(H_a*H_b) with r2=1.0, c=0 by construction.
   That is a tautology, NOT the reference. So this runner evaluates three modes and prints all:
       none  = raw c_i            (closest to the original; heterogeneous scales)
       scale = c_i / std          (THE FIX: comparable scales, centroids NOT forced antiparallel)
       pool  = (c_i - mean)/std   (the S22 Standardizer; degenerate -- shown for contrast)
   Standardization stats are always fit on TRAIN only (no leakage) in the walk-forward pass.

4. HONEST PREDICTOR (walk-forward, embargoed). Per fold: fit standardization + centroids on
   the TRAIN fold only, project the TEST fold -> dipole_direction signal. Backtest the
   concatenated OOS signal net of fees+slippage and gate via odcore/validation.py:
       - net > 0 after costs, and BEAT take-all baseline (trade every generator signal)
       - tautology circular-shift null z >> 2-3
       - small random-vs-walkforward sharpe gap (stationarity signature)
   In this per-trade framing buy-hold == take-all (gross sum of every signed trade).

Usage
-----
    python scripts/od_trade_dipole_run.py                          # all 6 sources, all trades
    python scripts/od_trade_dipole_run.py --sources btc_coinbase --max-trades 300
    python scripts/od_trade_dipole_run.py --standardize scale --leadlag-nnull 20
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from dataclasses import dataclass

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from odcore.io import load_bins
from odcore.dipole_trade import trade_coupling_vector, FEATURE_NAMES
from odcore.dipole_predictor import (
    algebraic_dipole_over_trades, build_centroids, project, dipole_direction,
)
from odcore.validation import (
    backtest_signal, walk_forward_splits, random_vs_walkforward_gap, tautology_signal_null,
)

# Platform shell (trade generation only; odcore stays portable per S21).
from markets_adapter import load_minute_bars, MarketChunker, MarketChunkEncoder
from regime_classifier import Regime, classify_regime, baselines_from_corpus
from adaptive_backtester import build_generators

REALBINS = os.path.join(os.path.dirname(__file__), "..", "realbins")
REF = "reference (orig 128-dim, raw): a=0.007 b=-0.093 c=1.309 R^2=0.943"
ALL_SOURCES = ["btc_coinbase", "btc_kraken", "btc_bybit_perp",
               "eth_coinbase", "eth_kraken", "eth_bybit_perp"]


@dataclass
class LabeledTrade:
    source: str
    entry_ts: int       # epoch sec (minute-aligned); slices the 1s BinSeries
    direction: int      # +1 / -1
    gross: float        # direction * log(p_exit/p_entry)  (fee applied later)
    net: float          # gross - fee_bps/1e4
    generators: int     # how many generators agreed on this (entry_ts, direction)


# --------------------------------------------------------------------------- #
# 1. labeled trades (replay the adaptive_backtester generators on minute bars)
# --------------------------------------------------------------------------- #
def generate_trades(source: str, bars, fee_bps: float,
                    chunk_max: int = 30, chunk_min: int = 10) -> list[LabeledTrade]:
    """Mirror adaptive_backtester.simulate()'s trade loop, but EMIT per-trade records for
    every generator that fires on an equilibrium chunk. Deduped by (entry_ts, direction)."""
    chunker = MarketChunker(max_window_size=chunk_max, stride=chunk_max // 2,
                            min_segment=chunk_min, mode="hybrid")
    encoder = MarketChunkEncoder(d_enc=64)
    chunks = chunker.chunk(source, bars)
    feats = [encoder._extract(c) for c in chunks]
    base = baselines_from_corpus(feats)
    regimes = [classify_regime(f, base).regime for f in feats]
    generators = build_generators()

    by_key: dict[tuple[int, int], LabeledTrade] = {}
    for t in range(len(chunks) - 1):
        if regimes[t] != Regime.EQUILIBRIUM_TWO_SIDED:
            continue
        if not chunks[t].bars or not chunks[t + 1].bars:
            continue
        p0 = chunks[t].bars[-1].close
        p1 = chunks[t + 1].bars[-1].close
        if p0 <= 0 or p1 <= 0:
            continue
        actual_return = math.log(p1 / p0)
        entry_ts = int(chunks[t].bars[-1].ts)
        f = feats[t]
        for g in generators:
            direction, _mag = g.signal(f)
            if direction == 0:
                continue
            gross = direction * actual_return
            net = gross - fee_bps / 10000.0
            key = (entry_ts, direction)
            if key in by_key:
                by_key[key].generators += 1
            else:
                by_key[key] = LabeledTrade(source, entry_ts, direction, gross, net, 1)
    return list(by_key.values())


# --------------------------------------------------------------------------- #
# 2. pre-entry dipole vectors (the expensive step)
# --------------------------------------------------------------------------- #
def build_vectors(trades, series, pre_entry, window, stride, max_lag, leadlag_nnull):
    """For each trade, slice [entry_ts - pre_entry, entry_ts] from the 1s BinSeries
    (buy vs sell orderflow) and build c_i. Returns (C, labels, gross, kept, skipped)."""
    t0 = int(series.ts[0])
    n_sec = len(series)
    C, labels, gross, kept = [], [], [], []
    skipped_bounds = skipped_short = 0
    for tr in trades:
        i1 = tr.entry_ts - t0
        i0 = i1 - pre_entry
        if i0 < 0 or i1 > n_sec:
            skipped_bounds += 1
            continue
        c = trade_coupling_vector(series.buy[i0:i1], series.sell[i0:i1],
                                  window=window, stride=stride, max_lag=max_lag,
                                  leadlag_nnull=leadlag_nnull)
        if c is None:
            skipped_short += 1
            continue
        C.append(c)
        labels.append(1 if tr.net > 0 else -1)   # win/lose by NET P&L
        gross.append(tr.gross)
        kept.append(tr)
    return C, labels, gross, kept, (skipped_bounds, skipped_short)


# --------------------------------------------------------------------------- #
# standardization (3 modes) -- fit stats on C_fit, apply to C_apply
# --------------------------------------------------------------------------- #
def standardize(C_fit, C_apply, mode):
    C_fit = np.asarray(C_fit, dtype=float)
    C_apply = np.asarray(C_apply, dtype=float)
    if mode == "none":
        return C_apply
    sd = C_fit.std(axis=0)
    sd = np.where(sd < 1e-12, 1.0, sd)
    if mode == "scale":
        return C_apply / sd
    mu = C_fit.mean(axis=0)               # mode == "pool"
    return (C_apply - mu) / sd


# --------------------------------------------------------------------------- #
# 3 + 4. evaluate one standardization mode (control + walk-forward + gate)
# --------------------------------------------------------------------------- #
def evaluate(C, labels, gross, mode, n_folds, embargo, fee_bps, slippage_bps):
    n = C.shape[0]
    print(f"\n{'='*72}\nMODE = {mode}\n{'='*72}")

    # -- positive control (in-sample) -------------------------------------- #
    Cz = standardize(C, C, mode)
    fit = algebraic_dipole_over_trades(Cz, labels)
    degenerate = fit.r2_lin > 0.999 and abs(fit.c) < 1e-3
    print("-- POSITIVE CONTROL (in-sample, structural; NOT an edge) --")
    print(f"   H_a^2 = {fit.a:+.4f} {fit.b:+.4f}*(H_a*H_b) {fit.c:+.4f}*(H_a*H_b)^2")
    print(f"   r2_quad={fit.r2_quad:.3f}  r2_lin={fit.r2_lin:.3f}  "
          f"(n_win={fit.n_win} n_lose={fit.n_lose})")
    print(f"   {REF}")
    if degenerate:
        print("   -> DEGENERATE: H_a == -H_b (antiparallel centroids); r2=1 is a tautology, "
              "NOT a reproduction.")
    else:
        print(f"   -> {'convex c>0' if fit.c > 0 else 'NON-convex c<=0'}; "
              f"r2_quad {'>' if fit.r2_quad > fit.r2_lin + 1e-3 else '~='} r2_lin "
              f"({'quadratic term adds structure' if fit.r2_quad > fit.r2_lin + 1e-3 else 'no extra curvature'})")

    # -- honest predictor (walk-forward) ----------------------------------- #
    folds = list(walk_forward_splits(n, n_folds, embargo))
    if not folds:
        print(f"-- WALK-FORWARD: SKIPPED (no folds; n={n}, embargo={embargo} too large "
              f"vs fold={n//(n_folds+1)}). Lower --embargo or add trades.)")
        return
    pred = np.zeros(n)
    covered = np.zeros(n, dtype=bool)
    single_class = 0
    for (tr0, tr1), (te0, te1) in folds:
        ytr = labels[tr0:tr1]
        if (ytr > 0).sum() == 0 or (ytr <= 0).sum() == 0:
            single_class += 1
        cw, cl = build_centroids(standardize(C[tr0:tr1], C[tr0:tr1], mode), ytr)
        Cte = standardize(C[tr0:tr1], C[te0:te1], mode)   # fit on TRAIN, apply to TEST
        for j in range(Cte.shape[0]):
            Ha, Hb = project(Cte[j], cw, cl)
            pred[te0 + j] = dipole_direction(Ha, Hb)
        covered[te0:te1] = True

    m = covered
    n_oos = int(m.sum())
    if n_oos < 30:
        print(f"-- WALK-FORWARD: only {n_oos} OOS trades (<30); skipping validation.")
        return
    ret_bt = np.concatenate([[0.0], gross[m]])   # pair pred_i with gross_i (signal[t]->ret[t+1])
    sig = pred[m]
    oos = backtest_signal(ret_bt, sig, fee_bps, slippage_bps)
    take_all = backtest_signal(ret_bt, np.ones(n_oos), fee_bps, slippage_bps)
    taut = tautology_signal_null(ret_bt, sig, fee_bps, slippage_bps)
    pred_is = np.array([dipole_direction(*project(Cz[i], *build_centroids(Cz, labels)))
                        for i in range(n)])
    gap = random_vs_walkforward_gap(np.concatenate([[0.0], gross]), pred_is,
                                    fee_bps, slippage_bps, n_folds)

    n_long = int((sig > 0).sum())
    print(f"-- HONEST PREDICTOR (walk-forward OOS; {n_oos} test trades, "
          f"{single_class} single-class folds, pred_win={n_long}) --")
    print(f"   dipole   net={oos.net_return:+.4f}  gross={oos.gross_return:+.4f}  "
          f"hit={oos.hit_rate:.1%}  sharpe={oos.sharpe:+.3f}  mdd={oos.max_drawdown:.4f}")
    print(f"   take-all net={take_all.net_return:+.4f}  gross={take_all.gross_return:+.4f}  "
          f"sharpe={take_all.sharpe:+.3f}   (== buy-hold here)")
    print(f"   tautology null: real_net={taut['real_net']:+.4f}  null_mean={taut['null_mean']:+.4f}  "
          f"null_std={taut['null_std']:.4f}  z={taut['z']:+.2f}")
    print(f"   random-vs-WF:   wf_sharpe={gap['walkforward_sharpe']:+.3f}  "
          f"random_sharpe={gap['random_sharpe']:+.3f}  gap={gap['gap']:+.3f}")

    g_net = oos.net_return > 0
    g_beat = oos.net_return > take_all.net_return
    g_taut = taut['z'] > 3.0
    g_gap = abs(gap['gap']) < 0.5
    passed = g_net and g_beat and g_taut and g_gap
    print("   GATE: "
          f"[{'PASS' if g_net else 'FAIL'}] net>0  "
          f"[{'PASS' if g_beat else 'FAIL'}] beat take-all  "
          f"[{'PASS' if g_taut else 'FAIL'}] z>>3  "
          f"[{'PASS' if g_gap else 'FAIL'}] gap<0.5  "
          f"=> {'PASS' if passed else 'FAIL'}")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", nargs="+", default=ALL_SOURCES)
    ap.add_argument("--pre-entry", type=int, default=600, help="pre-entry window (seconds)")
    ap.add_argument("--window", type=int, default=40)
    ap.add_argument("--stride", type=int, default=10)
    ap.add_argument("--max-lag", type=int, default=15)
    ap.add_argument("--leadlag-nnull", type=int, default=20, help="leadlag null shuffles (speed knob)")
    ap.add_argument("--fee-bps", type=float, default=25.0)
    ap.add_argument("--slippage-bps", type=float, default=2.0)
    ap.add_argument("--n-folds", type=int, default=5)
    ap.add_argument("--embargo", type=int, default=50)
    ap.add_argument("--max-trades", type=int, default=0, help="cap per source (0=all); even subsample")
    ap.add_argument("--standardize", default="all", choices=["all", "none", "scale", "pool"])
    args = ap.parse_args()

    print(f"== S23 chem-dipole trade runner ==  pre_entry={args.pre_entry}s "
          f"fee={args.fee_bps}bps slip={args.slippage_bps}bps folds={args.n_folds} "
          f"embargo={args.embargo} leadlag_nnull={args.leadlag_nnull}")

    all_C, all_lab, all_gross, all_ts = [], [], [], []
    for src in args.sources:
        path = os.path.join(REALBINS, f"{src}_bins.json")
        if not os.path.exists(path):
            print(f"  [skip] {src}: no bins at {path}")
            continue
        t = time.time()
        bars = load_minute_bars(path)
        series = load_bins(path)
        trades = generate_trades(src, bars, args.fee_bps)
        if args.max_trades and len(trades) > args.max_trades:
            step = max(1, len(trades) // args.max_trades)
            trades = trades[::step][:args.max_trades]       # even subsample across time
        C, lab, gross, kept, (sb, ss) = build_vectors(
            trades, series, args.pre_entry, args.window, args.stride,
            args.max_lag, args.leadlag_nnull)
        n_win = sum(1 for x in lab if x > 0)
        print(f"  {src:<16} bars={len(bars):>6}min  trades={len(trades):>4}  "
              f"usable={len(C):>4} (win={n_win} lose={len(C)-n_win})  "
              f"skip[bounds={sb} short={ss}]  {time.time()-t:.1f}s", flush=True)
        all_C.extend(C); all_lab.extend(lab); all_gross.extend(gross)
        all_ts.extend(tr.entry_ts for tr in kept)

    if len(all_C) < max(20, args.n_folds * 10):
        print(f"\n[STOP] only {len(all_C)} usable trades; need >= {max(20, args.n_folds*10)}. "
              f"Widen --sources, raise --max-trades, or lower --pre-entry.")
        return

    order = np.argsort(np.asarray(all_ts))          # chronological pooled order
    C = np.asarray(all_C, dtype=float)[order]
    labels = np.asarray(all_lab)[order]
    gross = np.asarray(all_gross, dtype=float)[order]
    n = C.shape[0]
    n_win = int((labels > 0).sum())
    print(f"\nPOOLED: {n} trades  (win={n_win}  lose={n - n_win}  base_rate={n_win/n:.1%})  "
          f"features={len(FEATURE_NAMES)}")

    modes = ["none", "scale", "pool"] if args.standardize == "all" else [args.standardize]
    for mode in modes:
        evaluate(C, labels, gross, mode, args.n_folds, args.embargo,
                 args.fee_bps, args.slippage_bps)

    print("\nNOTE: Option-2 trade set includes the dipole generator's own entries, so any OOS")
    print("edge is mildly self-referential; a clean read excludes it (re-run later).")


if __name__ == "__main__":
    main()
