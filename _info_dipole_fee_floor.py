"""_info_dipole_fee_floor.py — per-leg asymmetric (maker/taker) fee floor + how many 1-sec swings clear.

Architect's "free precision edge" (S36b): the 22 bps floor is round-trip TAKER. But the floor is per-leg
and asymmetric. Because the dipole PREDICTS the turn, you can REST a maker limit at the turn instead of
crossing the spread — which lowers BOTH the fee (maker ~ rebate) AND the slippage (you fill at your price,
not ~6 bps into the move). Modeling the floor per-leg, the min tradeable swing drops a lot, and many more
swings become tradeable.

floor = entry(fee + slippage) + exit(fee + slippage).  Slippage at 1-sec ~6 bps/side taker (the timing-test
entry_off) vs ~1 bps maker-rest (fill near your resting price). Fees are representative bybit-ish (tune per
venue live). Maker-rest carries FILL RISK (the limit only fills if price reaches it) — flagged, not modeled.

Run: python _info_dipole_fee_floor.py
"""
from __future__ import annotations

import numpy as np

from _info_dipole_swing_backtest import load_series, zigzag

# per-side (fee, slippage) in bps. maker-rest at the turn -> low fee + low slippage; taker -> higher both.
SCEN = {
    "taker / taker":        dict(entry=(5.0, 6.0), exit=(5.0, 6.0)),
    "maker-in / taker-out": dict(entry=(1.0, 1.0), exit=(5.0, 6.0)),
    "maker / maker":        dict(entry=(1.0, 1.0), exit=(1.0, 1.0)),
}


def floor_bps(s):
    return sum(s["entry"]) + sum(s["exit"])


def swings_at(p, theta):
    piv = zigzag(p, theta)
    return np.array([abs(p[i1] / p[i0] - 1.0) * 1e4 for (i0, _), (i1, _) in zip(piv[:-1], piv[1:])])


def main():
    series = load_series("realbins")
    thetas = [0.0005, 0.0010, 0.0015, 0.0020, 0.0030]
    print("Per-leg asymmetric fee floor — min tradeable swing = round-trip floor (fee+slippage both legs):")
    for name, s in SCEN.items():
        print(f"   {name:22s} floor = {floor_bps(s):>4.0f} bps   "
              f"(entry {sum(s['entry']):.0f} = fee {s['entry'][0]:.0f}+slip {s['entry'][1]:.0f}; "
              f"exit {sum(s['exit']):.0f})")
    print("\nORACLE swing net (bps total) under each fee scenario — pooled across 6 venues, by swing size:")
    print(f"{'theta':>7s} | " + " | ".join(f"{n:>20s}" for n in SCEN))
    allsw = {th: np.concatenate([swings_at(series[s][1], th) for s in series]) for th in thetas}
    for th in thetas:
        sw = allsw[th]
        cells = []
        for name, s in SCEN.items():
            F = floor_bps(s)
            trad = sw[sw > F]                                  # only swings that clear the floor are traded
            net = float((trad - F).sum())
            cells.append(f"{net:>9.0f}/{trad.size:>5d}")
        print(f"{th*1e4:>5.0f}bp | " + " | ".join(f"{c:>20s}" for c in cells))
    print("  (cell = oracle NET bps total / number of tradeable swings, i.e. swings that clear that floor.)")

    # headline: at the best theta per scenario, how much does maker execution add?
    print("\nBest-theta oracle net per scenario (pooled), and the maker uplift over taker/taker:")
    base = None
    for name, s in SCEN.items():
        F = floor_bps(s)
        best = max(float((allsw[th][allsw[th] > F] - F).sum()) for th in thetas)
        if base is None:
            base = best
        print(f"   {name:22s} floor {F:>4.0f}bps   best oracle net = {best:>9.0f} bps"
              f"{'' if name=='taker / taker' else f'   ({best/base:.1f}x taker/taker)'}")
    print("\nNOTE: oracle = perfect timing; this isolates the FEE-FLOOR effect (more swings clear a lower floor).")
    print("Maker-rest carries FILL RISK (limit only fills if price reaches it) — model per-venue before trusting.")


if __name__ == "__main__":
    main()
