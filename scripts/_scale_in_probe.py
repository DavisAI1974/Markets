"""_scale_in_probe.py — test Greg's S51 scale-in picture against the real books.

THE CLAIM (Greg, S51): "we should be getting our offers lifted on the way down the slide on winners and
flattening at the valley, then flipping to having our bids hit on the way up and flattening at the peak...
sizing up on winning trades and not on losing ones." I.e. instead of ONE maker fill at the turn (the current
executor), keep the conviction quote resting at the best price the WHOLE leg and let every opposing trade
scale us IN along the slide; flatten the accumulated inventory at the next turn.

This is a falsifiable flow question, decided per cell by the books:
  Q1  Does more opposing $ flow arrive during WINNING legs than LOSING legs? (Greg's picture says yes —
      the slide's counter-flow lifts our offers on winners. The S45 adverse-selection autopsy says the
      OPPOSITE — a resting offer fills hardest when price rips AGAINST it, i.e. on losers.)
  Q2  Scale-in P&L: each fill at cell t (maker, at mid[t] -/+ hs for bid/ask) is marked to the leg's actual
      close px (the executor's own close: maker at the next turn, or grace/taker fallback). Later fills
      capture only the REMAINING move. Does total $ beat the one-shot-at-the-turn model at matched
      per-leg capital?
  Q3  The wrong-tail: on losing legs scale-in averages the entry ALONG the adverse move (later fills lose
      less), but also loads MORE size into the loser. Which effect wins?

Uses the EXACT deployable legs (build_channels -> detect_flips -> simulate_swing_maker, cover-grace) — no
new signal, no leakage surface; this is an EXECUTION-layer variant on the same turns. Optimism flags shared
with the v1 capacity model: front-of-queue (we ARE the best price, every opposing trade fills us),
re-quote pegged at best each cell, and the flatten absorbs ALL inventory at close_px (exit capacity
un-modeled — the inventory/turn-flow ratio is reported as the honesty flag).
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _liquidity_dive import build_channels, median_spread_bps
from _birth_probe import load_book
from odcore.flip_detector import lean_series, detect_flips
from odcore.swing_maker import simulate_swing_maker

FLOW_W, WFLIP, REV = 20, 600, 0.1
CELLS = [("sol", 1), ("eth", 1)]
GRACE = {"sol": 300, "eth": 300}
CAPS = [1_000.0, 5_000.0, 25_000.0, 1e12]      # per-leg inventory cap $ (last = uncapped)
TURN_W = 10                                     # the one-shot entry window (S50 FILL_W)
TAKER = 5.0


def run_cell(coin, K, grace, maker_fee=0.0):
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"
    raw = load_book(path)
    ch, g = build_channels(path, K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    hs_bps = median_spread_bps(path, raw=raw) / 2.0
    hs = hs_bps / 1e4
    hrs = (raw["ts"][-1] - raw["ts"][0]) / 3600.0
    allf = detect_flips(lean_series(buy, sell, WFLIP), REV)[0]
    res = simulate_swing_maker(mid, bb, ba, buy, sell, allf, half_spread_bps=hs_bps,
                               maker_fee_bps=maker_fee, taker_fee_bps=TAKER, cover_grace=grace)

    legs = [l for l in res.legs if int(l.close_idx) > int(l.open_idx)]
    win = np.asarray([l.net_bps > 0 for l in legs])

    # ---- Q1: opposing $ flow available over the WHOLE leg, winners vs losers ----
    leg_flow = np.zeros(len(legs))
    for i, l in enumerate(legs):
        o, c = int(l.open_idx), int(l.close_idx)
        opp = sell[o:c] if l.side > 0 else buy[o:c]     # long bid <- SELL flow; short ask <- BUY flow
        leg_flow[i] = float(np.sum(opp)) * float(mid[o])

    # ---- Q2/Q3: scale-in P&L vs one-shot at matched per-leg capital ----
    out_rows = []
    for C in CAPS:
        tot_scale = 0.0; tot_onesh = 0.0
        filled_win = 0.0; filled_lose = 0.0
        pnl_win = 0.0; pnl_lose = 0.0
        inv_ratio = []                              # accumulated inventory / close-turn flow (honesty flag)
        for i, l in enumerate(legs):
            o, c = int(l.open_idx), int(l.close_idx)
            s = int(l.side)
            close_px = float(l.close_px)
            close_fee = maker_fee if l.close_maker else TAKER
            opp = sell[o:c] if s > 0 else buy[o:c]
            px = mid[o:c] * (1.0 - s * hs)          # our maker price each cell (bid below / ask above mid)
            fill_usd = opp * mid[o:c]               # opposing $ per cell at our quote
            cum = np.cumsum(fill_usd)
            take = np.minimum(fill_usd, np.maximum(0.0, C - (cum - fill_usd)))   # cap chronologically
            m = take > 0
            if m.any():
                per_bps = s * (close_px - px[m]) / px[m] * 1e4 - maker_fee - close_fee
                pnl = float(np.sum(per_bps / 1e4 * take[m]))
                filled = float(np.sum(take[m]))
            else:
                pnl = 0.0; filled = 0.0
            tot_scale += pnl
            if win[i]:
                filled_win += filled; pnl_win += pnl
            else:
                filled_lose += filled; pnl_lose += pnl
            # one-shot: fill bounded by the turn-window flow only, full leg net on it
            ow = float(np.sum((sell if s > 0 else buy)[o:min(c, o + TURN_W) + 1])) * float(mid[o])
            tot_onesh += float(l.net_bps) / 1e4 * min(C, ow)
            # exit honesty: inventory vs opposing flow in the close turn-window
            cw = float(np.sum((buy if s > 0 else sell)[c:c + TURN_W + 1])) * float(mid[c] if c < len(mid) else mid[-1])
            if filled > 0:
                inv_ratio.append(filled / max(cw, 1e-9))
        out_rows.append(dict(cap=C, scale_hr=tot_scale / hrs, oneshot_hr=tot_onesh / hrs,
                             filled_win=filled_win / hrs, filled_lose=filled_lose / hrs,
                             pnl_win_hr=pnl_win / hrs, pnl_lose_hr=pnl_lose / hrs,
                             med_inv_ratio=float(np.median(inv_ratio)) if inv_ratio else 0.0))
    return dict(coin=coin, hrs=hrs, n_legs=len(legs), win_frac=float(win.mean()),
                flow_win_med=float(np.median(leg_flow[win])) if win.any() else 0.0,
                flow_lose_med=float(np.median(leg_flow[~win])) if (~win).any() else 0.0,
                rows=out_rows)


def main():
    mk = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
    print(f"=== SCALE-IN probe (maker {mk:+.1f} bps, taker {TAKER} bps, cover-grace) ===")
    print("    scale-in = every opposing trade fills our re-quoted best-price maker quote along the leg,")
    print("    marked to the leg's actual close; one-shot = the current turn-window model. Same turns.\n")
    results = []
    for coin, K in CELLS:
        r = run_cell(coin, K, GRACE[coin], maker_fee=mk)
        results.append(r)
        print(f"[{coin.upper()}]  {r['hrs']:.1f}h  {r['n_legs']} legs  win {r['win_frac']*100:.0f}%")
        print(f"   Q1 opposing flow per leg (median $): WINNERS {r['flow_win_med']:>10,.0f}  vs  "
              f"LOSERS {r['flow_lose_med']:>10,.0f}   -> "
              + ("winners fill MORE (Greg's picture)" if r['flow_win_med'] > r['flow_lose_med']
                 else "LOSERS fill more (adverse selection)"))
        print(f"   {'cap/leg':>10} {'scale-in $/hr':>14} {'one-shot $/hr':>14} {'$fill/hr W':>12} {'$fill/hr L':>12}"
              f" {'pnlW/hr':>9} {'pnlL/hr':>9} {'inv/exit-flow':>13}")
        for row in r["rows"]:
            lab = "inf" if row["cap"] >= 1e11 else f"${row['cap']:,.0f}"
            print(f"   {lab:>10} {row['scale_hr']:>+14,.1f} {row['oneshot_hr']:>+14,.1f}"
                  f" {row['filled_win']:>12,.0f} {row['filled_lose']:>12,.0f}"
                  f" {row['pnl_win_hr']:>+9,.1f} {row['pnl_lose_hr']:>+9,.1f} {row['med_inv_ratio']:>12.1f}x")
        print()
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "_scale_in_probe_results.json"), "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
