"""_inventory_sim.py — continuous-inventory maker simulator: the FAITHFUL version of Greg's S51 picture.

"Offers lifted on the way down the slide, flatten at the valley, flip to bids hit on the way up, flatten
at the peak." The scale-in probe (_scale_in_probe.py) marked every leg's fills to a single flatten at the
leg close — which is impossible at size (inventory 4-20x the exit-turn flow). But in Greg's picture the
flatten IS the next leg's entry: at the valley, the sellers hitting our new bid simultaneously COVER the
short and BUILD the long. Inventory nets across legs; there is no separate exit. This simulator implements
exactly that:

  - conviction side flips at each flip confirm (same detect_flips turns as the deployed executor);
  - the conviction quote rests pegged at the best price (bid = mid-hs / ask = mid+hs) the whole leg;
  - every opposing taker trade fills us (front-of-queue optimism, = the v1 model class, flagged) up to a
    $ inventory cap C: fills first UNWIND the carried opposite inventory, then build the new side to C;
  - cash/coins accounting; P&L = cash + coins*mid marked at the end; maker fee (or rebate) on every fill.

Honesty metrics reported per run:
  - tape_share = our filled $ / the venue's one-sided taker $ over the window. At small caps this must be
    a few % for the front-of-queue assumption to be even roughly plausible; at large caps it explodes and
    the number is an upper bound on a venue THIS size (Bybit runs ~10x Coinbase's tape).
  - max drawdown of the equity curve (inventory risk the per-leg models hide).

No leakage surface: same flips, no new signal, execution-layer only. Falsification-first: report per cell;
the random-side control (--control) re-runs with the conviction side REVERSED — if reversed sides also
print, the money is spread/rebate harvesting, not the turns.
"""
import sys, os, json, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _liquidity_dive import build_channels, median_spread_bps
from _birth_probe import load_book
from odcore.flip_detector import lean_series, detect_flips

FLOW_W, WFLIP, REV = 20, 600, 0.1
CELLS = [("sol", 1), ("eth", 1)]
CAPS = [1_000.0, 5_000.0, 25_000.0]


def run_cell(coin, K, maker_fee=0.0, reverse=False):
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"
    raw = load_book(path)
    ch, g = build_channels(path, K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    hs = (median_spread_bps(path, raw=raw) / 2.0) / 1e4
    hrs = (raw["ts"][-1] - raw["ts"][0]) / 3600.0
    flips = detect_flips(lean_series(buy, sell, WFLIP), REV)[0]
    n = len(mid)

    # conviction side per cell: side s from flip k's confirm to flip k+1's confirm
    side = np.zeros(n, dtype=int)
    for k, (ci, _p, s) in enumerate(flips):
        ci = int(ci)
        nxt = int(flips[k + 1][0]) if k + 1 < len(flips) else n
        side[ci:nxt] = -int(s) if reverse else int(s)

    out = []
    tape_one_sided = float(np.sum((buy + sell) / 2.0 * mid))   # one-sided taker $ over the window
    for C in CAPS:
        cash = 0.0; coins = 0.0
        filled_usd = 0.0; n_fills = 0
        eq_peak = 0.0; max_dd = 0.0
        # cell loop (1-2M cells): plain python, ~seconds — fine for a probe
        for t in range(n):
            s = side[t]
            if s == 0:
                continue
            opp = sell[t] if s > 0 else buy[t]                # bid <- SELL flow; ask <- BUY flow
            if opp <= 0.0:
                continue
            px = mid[t] * (1.0 - s * hs)                      # our pegged maker price this cell
            pos_usd = coins * mid[t]
            room = C - s * pos_usd                            # unwind opposite first, build to +/-C
            if room <= 0.0:
                continue
            q_usd = min(opp * px, room)
            q = q_usd / px
            coins += s * q
            cash -= s * q_usd
            cash -= q_usd * maker_fee / 1e4                   # maker fee per fill (negative = rebate paid)
            filled_usd += q_usd; n_fills += 1
            eq = cash + coins * mid[t]
            eq_peak = max(eq_peak, eq)
            max_dd = max(max_dd, eq_peak - eq)   # classic peak-to-trough drawdown of the equity curve
        pnl = cash + coins * mid[-1]
        out.append(dict(cap=C, pnl_hr=pnl / hrs, filled_hr=filled_usd / hrs,
                        tape_share=filled_usd / max(tape_one_sided, 1e-9),
                        n_fills=n_fills, end_inv_usd=float(coins * mid[-1]),
                        max_dd=float(max_dd)))
    return dict(coin=coin, hrs=hrs, n_flips=len(flips), rows=out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maker", type=float, default=0.0, help="maker fee bps (negative = rebate)")
    ap.add_argument("--control", action="store_true", help="REVERSED-side control (falsification)")
    a = ap.parse_args()
    tag = "REVERSED-SIDE CONTROL" if a.control else "conviction side"
    print(f"=== INVENTORY-NETTING maker sim ({tag}, maker {a.maker:+.1f} bps) ===")
    print("    fills unwind the carried inventory then build the new side (the flatten IS the next leg's")
    print("    entry — no separate exit). Front-of-queue optimism flagged via tape_share.\n")
    results = []
    for coin, K in CELLS:
        r = run_cell(coin, K, maker_fee=a.maker, reverse=a.control)
        results.append(r)
        print(f"[{coin.upper()}]  {r['hrs']:.1f}h  {r['n_flips']} flips")
        print(f"   {'cap':>9} {'P&L $/hr':>10} {'$fill/hr':>11} {'tape%':>7} {'fills':>8} {'end inv$':>10} {'maxDD$':>9}")
        for row in r["rows"]:
            print(f"   ${row['cap']:>8,.0f} {row['pnl_hr']:>+10,.1f} {row['filled_hr']:>11,.0f}"
                  f" {row['tape_share']*100:>6.1f}% {row['n_fills']:>8,} {row['end_inv_usd']:>+10,.0f}"
                  f" {row['max_dd']:>9,.0f}")
        print()
    suff = "_control" if a.control else ""
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           f"_inventory_sim_results{suff}.json"), "w") as f:
        json.dump(dict(maker=a.maker, control=a.control, cells=results), f, indent=2)


if __name__ == "__main__":
    main()
