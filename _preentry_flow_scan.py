"""_preentry_flow_scan.py — mine the pre-entry window SECOND-BY-SECOND for the trend-vs-reversal split.

Greg: the 33% is pos/neg — winners that are "still flowing but in a different direction" (reversals/flips)
vs trend-continuation. The right instrument is the ACTUAL per-second taker flow + price in the pre-entry
window (bins carry buy/sell volume per second), not the summary imb_level. This:
  1. classifies each winner TREND (entered with the prior move) vs REVERSAL (entered against it = caught
     the turn), from the real per-second window.
  2. shows WHERE in the window the side signal lives, across lookbacks 1/5/15/30 min (answers: can we cut
     the 30-min window to 15-20?).
  3. dumps a per-second feature table for OD/PySR to discover the operator (the next step).

Runs on whatever bins are local (covers ~30% of the box's 21-day winners); same tool runs full on the box.
Usage: python _preentry_flow_scan.py --cells btc_bybit_perp,eth_bybit_perp
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
from odcore.io import load_bins

LOOKBACKS = [60, 300, 900, 1800]   # 1, 5, 15, 30 min
LAB = Path("_alt_labels")


def scan_cell(coin_venue: str):
    bs = load_bins(f"realbins/{coin_venue}_bins.json")
    ts, mid, buy, sell = bs.ts, bs.mid, bs.buy, bs.sell
    t0, t1 = ts[0], ts[-1]
    rows = []
    for side in ("buy", "sell"):
        fp = LAB / f"{coin_venue}_{side}_winner_onsets.json"
        if not fp.exists():
            continue
        sgn = +1.0 if side == "buy" else -1.0
        for r in json.load(open(fp)):
            dts = float(r["decision_ts_utc"])
            if not (t0 + 1800 <= dts <= t1):       # need a full 30-min lookback covered
                continue
            i = int(np.searchsorted(ts, dts, side="right")) - 1
            if i < 1800 or mid[i] <= 0:
                continue
            feat = {"side": side, "sgn": sgn, "net_bps": float(r.get("net_bps") or 0.0)}
            ok = True
            for L in LOOKBACKS:
                b = buy[i - L:i].sum(); s = sell[i - L:i].sum(); tot = b + s
                m0 = mid[i - L]
                if tot <= 0 or m0 <= 0:
                    ok = False; break
                feat[f"flow_{L}"] = (b - s) / tot                      # +buying / -selling
                feat[f"drift_{L}"] = np.log(mid[i] / m0) * 1e4          # bps, pre-entry price move
            if ok:
                rows.append(feat)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="btc_bybit_perp,eth_bybit_perp")
    args = ap.parse_args()
    rows = []
    for cv in args.cells.split(","):
        cv = cv.strip()
        if Path(f"realbins/{cv}_bins.json").exists():
            r = scan_cell(cv); print(f"[{cv}] usable winners (full 30-min lookback): {len(r)}")
            rows += r
    if not rows:
        print("no covered winners"); return
    sgn = np.array([r["sgn"] for r in rows]); net = np.array([r["net_bps"] for r in rows])

    # 1) TREND vs REVERSAL by the pre-entry price move RELATIVE TO the winning side
    print("\n=== TREND vs REVERSAL (price_toward_side = pre-entry drift * side sign) ===")
    print("    >0 = price already moved the winner's way before entry (TREND/continuation)")
    print("    <0 = entered AGAINST the prior move = caught the turn (REVERSAL/flip)")
    for L in LOOKBACKS:
        drift = np.array([r[f"drift_{L}"] for r in rows])
        toward = drift * sgn
        rev = toward < 0
        print(f"  lookback {L//60:>2d}min: REVERSAL {rev.mean():5.1%}  "
              f"net_bps trend={net[~rev].mean():7.1f} reversal={net[rev].mean():7.1f}")

    # 2) WHERE does the side signal live? does flow/price direction separate buy vs sell, per lookback?
    print("\n=== side separation by lookback (|mean flow/drift toward side|; bigger=more signal there) ===")
    for L in LOOKBACKS:
        flow = np.array([r[f"flow_{L}"] for r in rows]) * sgn      # flow toward side
        drift = np.array([r[f"drift_{L}"] for r in rows]) * sgn
        # how often does flow direction agree with the winning side?
        agree = (flow > 0).mean()
        print(f"  {L//60:>2d}min: flow-toward-side mean={flow.mean():+.4f}  agree={agree:5.1%}   "
              f"drift-toward-side mean={drift.mean():+7.2f} bps")

    # 3) dump features for OD/PySR (next step: let OD discover the operator)
    out = LAB / "preentry_flow_features.json"
    json.dump(rows, open(out, "w"))
    print(f"\nwrote {len(rows)} per-winner pre-entry feature rows -> {out} (for OD/PySR)")


if __name__ == "__main__":
    main()
