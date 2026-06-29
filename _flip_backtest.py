"""_flip_backtest.py — validate the causal flip detector: leakage gate -> net-of-cost swing sweep.

Mandatory order (S36b): assert_no_leakage FIRST, then the backtest. Swing model = flip at each detected
turn, ride to the next opposite turn (Greg's oscillation model). Net of a per-swing round-trip fee at
TAKER (10 bps) and MAKER (4 bps, resting the limit at the predicted turn). Sweeps W (trend window) x
reversal (the 'defense failed' threshold). Runs on whatever bins are local (BTC/ETH bybit, multi-day).
"""
from __future__ import annotations
import numpy as np
from pathlib import Path
from odcore.io import load_bins
from odcore.flip_detector import lean_series, detect_flips, backtest_swings, make_signal_at
from odcore.leakage import assert_no_leakage

CELLS = ["btc_bybit_perp", "eth_bybit_perp"]
WS = [30, 60, 120]
REVS = [0.05, 0.10, 0.20]
TAKER, MAKER = 10.0, 4.0


def main():
    # ---- leakage gate (mandatory, before any backtest) ----
    cv0 = CELLS[0]
    bs = load_bins(f"realbins/{cv0}_bins.json")
    rng = np.random.default_rng(0)
    idxs = rng.integers(2000, 40000, size=30)
    ok, fails = assert_no_leakage(make_signal_at(60, 0.10), bs.ts, bs.mid, bs.buy, bs.sell, idxs)
    print(f"[leakage] flip detector causal? {'PASS' if ok else 'FAIL'} ({len(fails)} leaks)")
    if not ok:
        print("  refusing to backtest a leaking signal"); return 1

    # ---- net-of-cost swing sweep, per cell ----
    for cv in CELLS:
        if not Path(f"realbins/{cv}_bins.json").exists():
            continue
        bs = load_bins(f"realbins/{cv}_bins.json")
        span_d = (bs.ts[-1] - bs.ts[0]) / 86400
        print(f"\n=== {cv}  ({span_d:.1f} days, {len(bs.ts)} sec) ===")
        print(f"{'W':>4} {'rev':>5} {'flips':>6} {'lag_bps':>8} {'gross/sw':>9} "
              f"{'net@taker':>10} {'net@maker':>10} {'pos%@mk':>8}")
        for W in WS:
            lean = lean_series(bs.buy, bs.sell, W)
            for rev in REVS:
                flips, _ = detect_flips(lean, rev)
                t = backtest_swings(bs.mid, flips, TAKER)
                m = backtest_swings(bs.mid, flips, MAKER)
                print(f"{W:>4} {rev:>5.2f} {t['n']:>6} {t['lag_bps']:>8.1f} {t['gross']:>9.2f} "
                      f"{t['mean']:>10.2f} {m['mean']:>10.2f} {m['pos_frac']:>8.1%}")
    print("\n(gross/sw = mean swing bps before fees; net = after round-trip fee; maker assumes resting the "
          "limit at the predicted turn. >0 net = the swing clears costs.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
