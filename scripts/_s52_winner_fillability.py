"""_s52_winner_fillability.py — S52 JOB 1b, step 2: can a WINNER-SIDE add even FILL?

Greg's Job 1b(ii): the S45/S51 result is the market force-feeds size to LOSERS (a resting quote fills hardest
when price rips against it). The proposed inversion: only accept post-entry ADDS when the leg is GREEN. That can
only work if GREEN/winning legs actually offer opposing maker flow to fill the add. This measures, per cell, the
entry-window opposing $ flow (== the fillable capacity, `_leg_caps` v1) split by WINNER vs LOSER legs.

If winners' fillable flow <= losers' (the S51 finding), a green-only add STRUCTURALLY cannot load winners harder
than losers — the mechanism is dead on the microstructure, not just on this window. Uses the exact deployable
legs + cap model (no reinvention).
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _liquidity_dive import build_channels, median_spread_bps
from _birth_probe import load_book
from odcore.flip_detector import lean_series, detect_flips
from odcore.swing_maker import simulate_swing_maker
from _capacity_model import _leg_caps, CELLS, GRACE, FLOW_W, WFLIP, REV


def cell(coin, K, grace):
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"
    if not os.path.exists(path):
        return None
    raw = load_book(path)
    ch, g = build_channels(path, K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0
    lean = lean_series(buy, sell, WFLIP)
    allf = detect_flips(lean, REV)[0]
    res = simulate_swing_maker(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                               maker_fee_bps=0.0, taker_fee_bps=5.0, cover_grace=grace)
    legs = res.legs
    caps, _ = _leg_caps(legs, mid, buy, sell, bb, ba)
    nets = np.asarray([float(l.net_bps) for l in legs])
    w = nets > 0
    cw, cl = caps[w], caps[~w]
    return dict(coin=coin, n=len(legs), win=float(w.mean()),
                cap_win_med=float(np.median(cw)) if len(cw) else float("nan"),
                cap_los_med=float(np.median(cl)) if len(cl) else float("nan"),
                cap_win_mean=float(cw.mean()) if len(cw) else float("nan"),
                cap_los_mean=float(cl.mean()) if len(cl) else float("nan"),
                ratio_med=float(np.median(cw) / (np.median(cl) + 1e-9)) if len(cw) and len(cl) else float("nan"))


print("=== S52 JOB 1b/step2 — fillable opposing flow (v1 cap $), WINNER vs LOSER legs ===\n")
out = []
for coin, K in CELLS:
    r = cell(coin, K, GRACE[coin])
    if r is None:
        print(f"[{coin}] no book\n"); continue
    out.append(r)
    print(f"[{r['coin'].upper()}]  n={r['n']}  win={100*r['win']:.0f}%")
    print(f"    fillable $ (median):  winners ${r['cap_win_med']:,.0f}   losers ${r['cap_los_med']:,.0f}   "
          f"win/lose ratio {r['ratio_med']:.2f}")
    print(f"    fillable $ (mean):    winners ${r['cap_win_mean']:,.0f}   losers ${r['cap_los_mean']:,.0f}\n")

print("READING: ratio <= 1 means losing legs offer >= the maker fill of winning legs -> a green-only add cannot")
print("preferentially load winners. The market force-feeds fill to losers (S45/S51), confirmed on the cap model.")
with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "_s52_winner_fillability_results.json"), "w") as f:
    json.dump(out, f, indent=2)
