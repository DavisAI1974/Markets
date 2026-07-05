"""_s63_kraken_flipzz.py — the REAL deployed zigzag (flow-lean flip detector) on the KRAKEN tape.

Greg: "the final zigzag we used on bybit for sol that was nailing the trades." That is NOT the
price-zigzag in _s63_kraken_zigzag.py — it is the S40/S56 CAUSAL FLOW-LEAN flip detector
(`odcore/flip_detector.py`), deployed params `odcore/platform.py` WFLIP=600, REV=0.1 (ARM0 natural
cadence). Its thesis: price near a turn is ~99.6% symmetric, so the turn lives in the trailing
taker-flow LEAN, not price. Promoted S56 on Bybit @ MM3 (full S54 gate: z 6.8-14.4, 20/20 coin-weeks,
reversed below floor).

This drops the KRAKEN tape into that exact detector and runs the S54 gate:
  lean = lean_series(buy, sell, 600);  flips = detect_flips(lean, 0.1);  backtest_swings(mid, flips, 0)
  SHUFFLE null: permute the per-second flow pairs (break flow<->turn alignment), rerun on real price.
  REVERSED control: negate every side (a real edge => reversed loses, below the shuffle floor).

⚠ Bybit @ MM3 was a maker-REBATE tier: there the big $/hr was largely a VOLUME PAYCHECK (a shuffled
tape earned ~$90-106/hr/coin too). Kraken kr_mk0 = 0bp (NO rebate), so this tests PURE STRUCTURE —
expect small $/hr; the gate (forward > shuffle, reversed < floor) is the verdict, not the raw number.

Usage:  python scripts/_s63_kraken_flipzz.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from odcore.flip_detector import lean_series, detect_flips, backtest_swings  # noqa: E402

CAP = 5000.0
WFLIP, REV = 600, 0.1          # deployed params (odcore/platform.py)
KTAPE = "/tmp/kraken_backfill"
REALBINS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "realbins")
CELLS = [("sol", f"{KTAPE}/SOLUSD_30d_bins.json"), ("eth", f"{KTAPE}/ETHUSD_30d_bins.json"),
         ("xrp", f"{KTAPE}/XRPUSD_30d_bins.json"), ("btc", f"{KTAPE}/XBTUSD_30d_bins.json"),
         ("doge", f"{KTAPE}/XDGUSD_30d_bins.json")]
N_SHUF = 100
SEED = 5
FEES = [("kr_mk0", 0.0), ("kr_mk2", 2.0)]


def load_flow(path):
    mid, buy, sell, cover, hrs = load_bins(path)
    return (np.asarray(mid, float), np.asarray(buy, float), np.asarray(sell, float), cover, hrs)


def run_detector(mid, buy, sell, fee):
    lean = lean_series(buy, sell, WFLIP)
    flips, _ = detect_flips(lean, REV)
    st = backtest_swings(mid, flips, fee)
    return st, flips


def main():
    rng = np.random.default_rng(SEED)
    print("=== REAL flow-lean flip detector (WFLIP=600, REV=0.1) on the KRAKEN tape ===")
    print("    net $/hr @ $5k; forward>shuffle AND reversed<floor = the S54 gate PASS\n")
    for coin, path in CELLS:
        if not os.path.exists(path):
            print(f"[{coin}] not present"); continue
        mid, buy, sell, cover, hrs = load_flow(path)
        st, flips = run_detector(mid, buy, sell, 0.0)
        if st["n"] < 20:
            print(f"[{coin}] too few swings ({st['n']}) — flow too sparse"); continue
        def dph(net_bps):
            return net_bps / 1e4 * CAP / hrs
        fwd0 = dph(st["net"])
        legs_h = st["n"] / hrs
        # reversed control: negate sides -> net = -gross_sum (same legs)
        rev_flips = [(ci, pv, -s) for (ci, pv, s) in flips]
        rev_net = backtest_swings(mid, rev_flips, 0.0)["net"]
        # shuffle null: permute per-second flow pairs, rerun detector on REAL price
        null = np.empty(N_SHUF)
        idx = np.arange(len(buy))
        for j in range(N_SHUF):
            perm = rng.permutation(idx)
            stn, _ = run_detector(mid, buy[perm], sell[perm], 0.0)
            null[j] = dph(stn["net"])
        mu = float(null.mean()); sd = float(null.std() + 1e-12)
        z = (fwd0 - mu) / sd; p = (np.sum(null >= fwd0) + 1) / (N_SHUF + 1)
        gate = "PASS" if (fwd0 > 0 and z > 2 and dph(rev_net) < mu) else "fail"
        print(f"[{coin}]  span={len(mid)/86400:.1f}d cov={cover*100:.0f}%  swings={st['n']} "
              f"({legs_h:.2f}/h)  win%={st['pos_frac']*100:.0f}  mean={st['mean']:+.1f}bp  lag={st['lag_bps']:.1f}bp")
        row = "   net $/hr:"
        for lbl, fee in FEES:
            row += f"  {lbl}={dph(run_detector(mid,buy,sell,fee)[0]['net']):+.2f}"
        print(row)
        print(f"   fwd={fwd0:+.2f}  shuffle mu={mu:+.2f} sd={sd:.2f}  z={z:+.1f} p={p:.3f}  "
              f"reversed={dph(rev_net):+.2f}   GATE: {gate}\n")


if __name__ == "__main__":
    main()
