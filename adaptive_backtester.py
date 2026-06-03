"""
adaptive_backtester.py — runs N candidate signal operators in parallel and
adaptively selects the best one based on rolling track record.

Each operator is a SignalGenerator: takes MarketFeatures, returns a signed
prediction (sign determines trade direction; magnitude can gate entry).

The simulation walks chunks chronologically. At each EQUILIBRIUM chunk:
  - All generators produce predictions.
  - Each generator's "what would have happened" is tracked.
  - The AdaptiveSelector picks whichever generator has the highest rolling
    Sharpe over the last N trades; sits out if all are negative.
  - The selected generator's prediction becomes the trade.

Final report compares: each generator standalone, adaptive ensemble, and
the per-generator switchover history.

This is the production pattern for multi-strategy operator deployment:
generators run in shadow on live data; live signal uses the rolling winner.

Usage:
    python adaptive_backtester.py --datasets CB-BTC:phase1_bins.json \\
                                  CB-ETH:eth_coinbase_bins.json \\
        --fee-bps 25
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from markets_adapter import (
    MarketBar, MarketChunker, MarketChunkEncoder, MarketFeatures, MarketChunk,
    load_minute_bars,
)
from regime_classifier import (
    Regime, classify_regime, baselines_from_corpus,
)
from operator_registry import OperatorRegistry, GeneratorStats


# ---------------------------------------------------------------------------
# Signal generators
# ---------------------------------------------------------------------------

@dataclass
class SignalGenerator:
    name: str
    predict_fn: Callable[[MarketFeatures], float]
    threshold: float = 0.1   # absolute prediction must exceed this to trade
    description: str = ""

    def signal(self, f: MarketFeatures) -> tuple[int, float]:
        """Return (direction, magnitude). direction in {-1, 0, +1}."""
        pred = self.predict_fn(f)
        if abs(pred) < self.threshold:
            return 0, abs(pred)
        return (-1 if pred < 0 else +1), abs(pred)


def build_generators() -> list[SignalGenerator]:
    """The candidate operator library.

    Includes the Operator-Discovery generators (odcore.generators.make_od_generators)
    so the entropy-dipole operators compete in the same rolling-Sharpe selection as the
    hand-specified ones. The OD generators degrade gracefully to [] if odcore is missing.
    """
    gens = [
        # Pure dipole (the hand-specified operator). Mean-reversion direction
        # because the empirical lag-1 r was negative on EQUILIBRIUM chunks.
        SignalGenerator(
            name="pure_dipole_fade",
            predict_fn=lambda f: -f.mean_dipole,
            threshold=0.15,
            description="Fade mean_dipole (mean-reversion of order flow imbalance)",
        ),
        # Hybrid: dipole gated by volume - the autoresearch winner
        SignalGenerator(
            name="dipole_x_volz",
            predict_fn=lambda f: -f.mean_dipole * f.volume_zscore,
            threshold=0.10,
            description="Fade dipole only when volume z is elevated",
        ),
        # Skew-based mean reversion (autoresearch second-best)
        SignalGenerator(
            name="ret_skew_fade",
            predict_fn=lambda f: -f.ret_skew,
            threshold=0.5,
            description="Fade returns skewness (kurtic days revert)",
        ),
        # Composite: dipole damped by autocorrelation persistence
        SignalGenerator(
            name="dipole_damp_acl1",
            predict_fn=lambda f: -f.mean_dipole * (1.0 - max(0, f.dipole_autocorr_lag1)),
            threshold=0.10,
            description="Fade dipole; reduce signal when one-side pressure is sustained (whale-like)",
        ),
    ]
    try:
        from odcore.generators import make_od_generators
        gens.extend(make_od_generators())
    except Exception:
        pass
    return gens


# ---------------------------------------------------------------------------
# Performance tracker: maintains rolling window of realized P&L per generator
# ---------------------------------------------------------------------------

@dataclass
class GeneratorTracker:
    name: str
    window: int = 20
    history: deque = field(default_factory=lambda: deque(maxlen=200))
    total_pnl_bps: float = 0.0
    n_trades: int = 0
    n_wins: int = 0

    def record(self, signed_return: float, fee_bps: float) -> None:
        net = signed_return - fee_bps / 10000.0
        self.history.append(net)
        self.total_pnl_bps += net * 10000.0
        self.n_trades += 1
        if net > 0:
            self.n_wins += 1

    def rolling_sharpe(self) -> float:
        if len(self.history) < 3:
            return 0.0
        recent = list(self.history)[-self.window:]
        m = float(np.mean(recent))
        s = float(np.std(recent))
        return m / s if s > 1e-12 else 0.0

    def rolling_mean_bps(self) -> float:
        if not self.history:
            return 0.0
        return float(np.mean(list(self.history)[-self.window:])) * 10000.0


class AdaptiveSelector:
    """Picks the highest-rolling-sharpe generator each chunk; sits out if all <= 0."""

    def __init__(self, generators: list[SignalGenerator], min_data_per_gen: int = 5):
        self.generators = {g.name: g for g in generators}
        self.trackers: dict[str, GeneratorTracker] = {
            g.name: GeneratorTracker(name=g.name) for g in generators
        }
        self.min_data = min_data_per_gen
        self.switch_log: list[tuple[int, str, str]] = []   # (chunk_idx, prev, new)
        self.last_selected: str | None = None

    def select(self, chunk_idx: int, default: str | None = None) -> str | None:
        # Cold start: not enough data; use default (first generator)
        all_have_data = all(t.n_trades >= self.min_data for t in self.trackers.values())
        if not all_have_data:
            picked = default or list(self.generators.keys())[0]
        else:
            scores = {n: t.rolling_sharpe() for n, t in self.trackers.items()}
            best_name, best_score = max(scores.items(), key=lambda x: x[1])
            if best_score <= 0:
                picked = None  # Sit out
            else:
                picked = best_name
        if picked != self.last_selected:
            self.switch_log.append((chunk_idx, self.last_selected or "(cold start)", picked or "(sit out)"))
            self.last_selected = picked
        return picked


# ---------------------------------------------------------------------------
# Simulation walker
# ---------------------------------------------------------------------------

# load_bars consolidated into markets_adapter.load_minute_bars (single source of the
# minute-bar loader that had been copy-pasted across the backtest/evaluator scripts).
load_bars = load_minute_bars


@dataclass
class SimResult:
    label: str
    generators: list[SignalGenerator]
    per_gen_track: dict[str, GeneratorTracker]
    adaptive_track: GeneratorTracker
    switch_log: list[tuple[int, str, str]]
    n_chunks: int
    n_equilibrium: int


def simulate(label: str, bars: list[MarketBar], fee_bps: float = 25.0,
             chunk_max: int = 30, chunk_min: int = 10,
             only_equilibrium: bool = True) -> SimResult:
    chunker = MarketChunker(max_window_size=chunk_max, stride=chunk_max // 2,
                             min_segment=chunk_min, mode="hybrid")
    encoder = MarketChunkEncoder(d_enc=64)
    chunks = chunker.chunk(label, bars)
    feats = [encoder._extract(c) for c in chunks]
    base = baselines_from_corpus(feats)
    regimes = [classify_regime(f, base).regime for f in feats]

    generators = build_generators()
    selector = AdaptiveSelector(generators)
    adaptive_tracker = GeneratorTracker(name="ADAPTIVE_ENSEMBLE")

    n_eq = sum(1 for r in regimes if r == Regime.EQUILIBRIUM_TWO_SIDED)

    for t in range(len(chunks) - 1):
        if only_equilibrium and regimes[t] != Regime.EQUILIBRIUM_TWO_SIDED:
            continue
        f = feats[t]
        if not chunks[t].bars or not chunks[t + 1].bars:
            continue
        p0 = chunks[t].bars[-1].close
        p1 = chunks[t + 1].bars[-1].close
        if p0 <= 0 or p1 <= 0:
            continue
        actual_return = math.log(p1 / p0)

        # Each generator records hypothetically what it would have earned
        signals: dict[str, tuple[int, float]] = {}
        for g in generators:
            direction, mag = g.signal(f)
            signals[g.name] = (direction, mag)
            if direction != 0:
                signed_return = direction * actual_return
                selector.trackers[g.name].record(signed_return, fee_bps)

        # Adaptive selector picks one generator (or sits out)
        picked = selector.select(t)
        if picked is None or signals[picked][0] == 0:
            continue
        direction = signals[picked][0]
        signed_return = direction * actual_return
        adaptive_tracker.record(signed_return, fee_bps)

    return SimResult(
        label=label,
        generators=generators,
        per_gen_track=dict(selector.trackers),
        adaptive_track=adaptive_tracker,
        switch_log=selector.switch_log,
        n_chunks=len(chunks),
        n_equilibrium=n_eq,
    )


def print_result(r: SimResult, fee_bps: float) -> None:
    print(f"\n=== {r.label} ===")
    print(f"  chunks={r.n_chunks}, equilibrium chunks={r.n_equilibrium}")
    print(f"  fee assumption: {fee_bps:.0f} bps round-trip\n")

    print(f"  Per-generator standalone (shadow track record):")
    print(f"    {'name':<26} {'n':>4} {'wins':>5} {'win%':>6} {'mean_bps':>9} {'sharpe':>8} {'total_bps':>10}")
    for name, t in r.per_gen_track.items():
        win_rate = t.n_wins / t.n_trades if t.n_trades else 0
        print(f"    {name:<26} {t.n_trades:>4} {t.n_wins:>5} {win_rate:>6.1%} "
              f"{t.rolling_mean_bps():>+9.2f} {t.rolling_sharpe():>+8.3f} {t.total_pnl_bps:>+10.2f}")
    print(f"\n  ADAPTIVE ensemble (live signal):")
    t = r.adaptive_track
    win_rate = t.n_wins / t.n_trades if t.n_trades else 0
    print(f"    {'ADAPTIVE_ENSEMBLE':<26} {t.n_trades:>4} {t.n_wins:>5} {win_rate:>6.1%} "
          f"{t.rolling_mean_bps():>+9.2f} {t.rolling_sharpe():>+8.3f} {t.total_pnl_bps:>+10.2f}")

    if r.switch_log:
        print(f"\n  Selector switch log (chunk_idx: prev -> new):")
        for ci, prev, new in r.switch_log[:20]:
            print(f"    chunk[{ci}]: {prev} -> {new}")
        if len(r.switch_log) > 20:
            print(f"    ... ({len(r.switch_log) - 20} more)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--datasets", nargs="+", required=True,
                   help="label:path pairs (label format ASSET-VENUE, e.g. CB-BTC:phase1_bins.json)")
    p.add_argument("--fee-bps", type=float, default=25.0)
    p.add_argument("--report-path", default=None)
    p.add_argument("--persist-registry", action="store_true",
                   help="Update operator_registry.json with per-source preferences")
    p.add_argument("--registry-path", default="operator_registry.json")
    args = p.parse_args()

    pairs = []
    for spec in args.datasets:
        if ":" not in spec:
            continue
        label, path = spec.split(":", 1)
        pairs.append((label, path))

    registry = OperatorRegistry(args.registry_path) if args.persist_registry else None

    all_results: list[SimResult] = []
    for label, path in pairs:
        bars = load_bars(path)
        r = simulate(label, bars, fee_bps=args.fee_bps)
        print_result(r, args.fee_bps)
        all_results.append(r)

        # Update per-source registry if requested. Label format ASSET-VENUE
        # or VENUE-ASSET; we accept either. (If label is "CB-BTC", we treat
        # CB as venue, BTC as asset.)
        if registry and "-" in label:
            parts = label.split("-")
            if len(parts) == 2:
                # Try to detect: if first is a known venue prefix, use that
                venue_prefixes = {"CB": "Coinbase", "KR": "Kraken", "BN": "Binance",
                                   "Coinbase": "Coinbase", "Kraken": "Kraken"}
                if parts[0] in venue_prefixes:
                    venue, asset = venue_prefixes[parts[0]], parts[1]
                elif parts[1] in venue_prefixes:
                    venue, asset = venue_prefixes[parts[1]], parts[0]
                else:
                    asset, venue = parts
                gen_stats = {
                    name: GeneratorStats(
                        sharpe=t.rolling_sharpe(),
                        n_trades=t.n_trades,
                        pnl_bps=t.total_pnl_bps,
                        last_updated_utc=__import__("time").time(),
                    )
                    for name, t in r.per_gen_track.items()
                }
                registry.update_source(asset, venue, gen_stats)

    if registry:
        registry.save()
        print(f"\n=== Operator registry updated: {args.registry_path} ===")
        print(registry.summary())

    # Summary table
    print(f"\n{'=' * 70}")
    print("SUMMARY: per-generator total PnL across all datasets")
    print(f"{'=' * 70}")
    aggregate: dict[str, float] = defaultdict(float)
    aggregate_trades: dict[str, int] = defaultdict(int)
    aggregate_wins: dict[str, int] = defaultdict(int)
    for r in all_results:
        for name, t in r.per_gen_track.items():
            aggregate[name] += t.total_pnl_bps
            aggregate_trades[name] += t.n_trades
            aggregate_wins[name] += t.n_wins
        aggregate["ADAPTIVE_ENSEMBLE"] += r.adaptive_track.total_pnl_bps
        aggregate_trades["ADAPTIVE_ENSEMBLE"] += r.adaptive_track.n_trades
        aggregate_wins["ADAPTIVE_ENSEMBLE"] += r.adaptive_track.n_wins

    print(f"  {'name':<26} {'n':>4} {'wins':>5} {'win%':>6} {'pnl_bps':>10}")
    for name in sorted(aggregate, key=lambda n: -aggregate[n]):
        n = aggregate_trades[name]
        w = aggregate_wins[name]
        wp = w / n if n else 0
        print(f"  {name:<26} {n:>4} {w:>5} {wp:>6.1%} {aggregate[name]:>+10.2f}")

    if args.report_path:
        report = {
            "fee_bps": args.fee_bps,
            "datasets": [{"label": r.label, "n_chunks": r.n_chunks,
                          "n_equilibrium": r.n_equilibrium,
                          "per_gen": {n: {"n_trades": t.n_trades, "n_wins": t.n_wins,
                                            "total_pnl_bps": t.total_pnl_bps,
                                            "rolling_sharpe": t.rolling_sharpe()}
                                       for n, t in r.per_gen_track.items()},
                          "adaptive": {"n_trades": r.adaptive_track.n_trades,
                                        "n_wins": r.adaptive_track.n_wins,
                                        "total_pnl_bps": r.adaptive_track.total_pnl_bps},
                          "switch_log_size": len(r.switch_log)}
                          for r in all_results],
            "aggregate": {n: {"trades": aggregate_trades[n], "wins": aggregate_wins[n],
                              "pnl_bps": aggregate[n]} for n in aggregate},
        }
        with open(args.report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved: {args.report_path}")


if __name__ == "__main__":
    main()
