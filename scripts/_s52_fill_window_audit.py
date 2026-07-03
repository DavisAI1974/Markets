"""_s52_fill_window_audit.py — S52 re-audit (Greg: "the low $/hr numbers don't look right").

THE INCONSISTENCY UNDER TEST: the validated executor has NO fill window — the quote RESTS at the fixed
limit (the turn price) until the next turn (Greg S46: "the time windows are irrelevant"; `_next_positive`
fills the first unit at the first opposing trade). But `_capacity_model._leg_caps` bounds the SIZE-S fill
to FILL_W=10 cells (10s) of opposing flow after the fill cell. For finite S the honest window is neither
10s nor the whole hold — it is PRICE-CONDITIONAL: a resting bid at `open_px` keeps getting hit exactly in
the cells where it is still at-or-better-than the venue's best bid (mid[t] <= mid at the post for a long;
mid[t] >= it for a short), bounded by the leg close. On a lingering turn that is >>10s; once price leaves,
the fill window closes by itself. This probe measures, per cell (Coinbase books):

  1. the FIRST-fill lag distribution (open_idx − flip_idx) — how long the executor actually rests;
  2. the TIME the leg spends price-eligible (mid at-or-through the limit) — the real fill window;
  3. cap10 (current FILL_W=10) vs capP (price-conditional, [open, close]) — ratio distribution,
     winners vs losers separately (the adverse-selection check: losers SHOULD show fatter capP);
  4. the $/hr consequence: _dollars() at REP_S and across SIZES, mk0 and −1bp, flat and SIZED,
     cap10 vs capP — i.e. does the 10s window materially understate deploy-size $/hr?

Honesty notes: capP at S→inf re-admits the whole-hold fiction ON LOSERS (you eat the entire adverse
slide) — so the ceiling under capP is reported as max over the SIZES grid (the optimal finite deploy),
never S=inf. At finite S, min(S·size, capP) is honest: winners' fills stop when price leaves; losers'
fills truncate at S (you cannot lose more than the size you posted). No new signal — pure accounting
re-measurement of the SAME legs; leakage gate not applicable (no feature enters a trading decision).
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _liquidity_dive import build_channels, median_spread_bps
from _birth_probe import load_book
from odcore.flip_detector import lean_series, detect_flips
from odcore.swing_maker import simulate_swing_maker, size_legs
from _capacity_model import (_leg_features, _leg_caps, _dollars, CELLS, GRACE,
                             FLOW_W, WFLIP, REV, REP_S, SIZES, FILL_W)


def _price_conditional_caps(legs, mid, buy, sell):
    """capP per leg: opposing $ flow in cells t in [open_idx, close_idx] where the fixed limit at the post
    cell is still at-or-better than the venue best on our side — long: mid[t] <= mid[flip_ci] (our bid at
    mid(ci)·(1−hs) is >= the current best bid level); short: mid[t] >= mid[flip_ci]. Also returns the
    eligible-cell count (the real fill-window length in seconds)."""
    capP, elig_s = [], []
    for l in legs:
        o, c, ci = int(l.open_idx), int(l.close_idx), int(l.flip_idx)
        if c <= o:
            capP.append(0.0); elig_s.append(0); continue
        seg = slice(o, c + 1)
        m = mid[seg]
        if l.side > 0:
            ok = m <= mid[ci]
            opp = sell[seg]
        else:
            ok = m >= mid[ci]
            opp = buy[seg]
        px = float(mid[o])
        capP.append(float(np.sum(opp[ok])) * px)
        elig_s.append(int(ok.sum()))
    return np.asarray(capP), np.asarray(elig_s)


def audit_cell(coin, K, grace):
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"
    if not os.path.exists(path):
        return None
    raw = load_book(path)
    ch, g = build_channels(path, K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    sret = ch["signed_ret"]
    hs = median_spread_bps(path, raw=raw) / 2.0
    hrs = (raw["ts"][-1] - raw["ts"][0]) / 3600.0
    lean = lean_series(buy, sell, WFLIP)
    allf = detect_flips(lean, REV)[0]
    piv = {int(c): int(p) for (c, p, s) in allf}

    out_scen = []
    caps10 = capP = None
    for label, mk in [("mk0", 0.0), ("mk-1", -1.0)]:
        res = simulate_swing_maker(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                                   maker_fee_bps=mk, taker_fee_bps=5.0, cover_grace=grace)
        legs = res.legs
        if caps10 is None:
            caps10, _ = _leg_caps(legs, mid, buy, sell, bb, ba)
            capP, elig_s = _price_conditional_caps(legs, mid, buy, sell)
            fill_lag = np.asarray([int(l.open_idx) - int(l.flip_idx) for l in legs])
            hold_s = np.asarray([int(l.close_idx) - int(l.open_idx) for l in legs])
            q, sa = _leg_features(legs, mid, sret, buy, sell, lean, piv)
        nets = np.asarray([float(l.net_bps) for l in legs])
        size_legs(legs, q, sa, alpha=1.0, roll=200)
        sizes = np.asarray([float(l.size) for l in legs])
        ones = np.ones_like(sizes)
        row = dict(label=label,
                   flat_rep_10=_dollars(nets, ones, caps10, hrs, REP_S),
                   flat_rep_P=_dollars(nets, ones, capP, hrs, REP_S),
                   sized_rep_10=_dollars(nets, sizes, caps10, hrs, REP_S),
                   sized_rep_P=_dollars(nets, sizes, capP, hrs, REP_S))
        # $/hr across the SIZES grid under capP (report the max = optimal finite deploy, never S=inf)
        grid = {}
        for S in SIZES[:-1]:
            grid[S] = dict(flat_10=_dollars(nets, ones, caps10, hrs, S),
                           flat_P=_dollars(nets, ones, capP, hrs, S),
                           sized_P=_dollars(nets, sizes, capP, hrs, S))
        row["grid"] = grid
        row["best_S_P"] = max(grid, key=lambda S: grid[S]["sized_P"])
        row["best_sized_P"] = grid[row["best_S_P"]]["sized_P"]
        row["ceil_10"] = _dollars(nets, ones, caps10, hrs, 1e12)
        out_scen.append(row)

    w = nets > 0  # winner mask from the mk0 pass (same legs; nets from last loop is mk-1 — recompute)
    res0 = simulate_swing_maker(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                                maker_fee_bps=0.0, taker_fee_bps=5.0, cover_grace=grace)
    nets0 = np.asarray([float(l.net_bps) for l in res0.legs])
    w = nets0 > 0
    r = dict(coin=coin, hrs=hrs, n=len(nets0), turns_hr=len(nets0) / hrs,
             fill_lag_med_s=float(np.median(fill_lag)), fill_lag_p90_s=float(np.percentile(fill_lag, 90)),
             hold_med_s=float(np.median(hold_s)),
             elig_med_s=float(np.median(elig_s)), elig_p90_s=float(np.percentile(elig_s, 90)),
             cap10_med=float(np.median(caps10)), capP_med=float(np.median(capP)),
             ratio_med=float(np.median(capP / (caps10 + 1e-9))),
             frac_capP_gt_1k=float(np.mean(capP >= REP_S)), frac_cap10_gt_1k=float(np.mean(caps10 >= REP_S)),
             capP_win_med=float(np.median(capP[w])), capP_los_med=float(np.median(capP[~w])),
             cap10_win_med=float(np.median(caps10[w])), cap10_los_med=float(np.median(caps10[~w])),
             scen=out_scen)
    return r


def main():
    print(f"=== S52 fill-window audit — FILL_W={FILL_W}s window vs PRICE-CONDITIONAL fill (the executor rests"
          f" with no window) ===\n")
    out = []
    for coin, K in CELLS:
        r = audit_cell(coin, K, GRACE[coin])
        if r is None:
            print(f"[{coin}] no book\n"); continue
        out.append(r)
        print(f"[{r['coin'].upper()}]  {r['hrs']:.1f}h  n={r['n']}  turns/hr={r['turns_hr']:.1f}")
        print(f"    first-fill lag: med {r['fill_lag_med_s']:.0f}s  p90 {r['fill_lag_p90_s']:.0f}s   "
              f"hold med {r['hold_med_s']:.0f}s   price-eligible window: med {r['elig_med_s']:.0f}s "
              f"p90 {r['elig_p90_s']:.0f}s  (vs FILL_W={FILL_W}s)")
        print(f"    cap med: 10s ${r['cap10_med']:,.0f} -> priceCond ${r['capP_med']:,.0f}  "
              f"(med ratio {r['ratio_med']:.1f}x)   legs with cap>=${REP_S:,.0f}: "
              f"{r['frac_cap10_gt_1k']*100:.0f}% -> {r['frac_capP_gt_1k']*100:.0f}%")
        print(f"    winners vs losers capP med: ${r['capP_win_med']:,.0f} vs ${r['capP_los_med']:,.0f} "
              f"(10s: ${r['cap10_win_med']:,.0f} vs ${r['cap10_los_med']:,.0f})")
        for s in r["scen"]:
            print(f"    [{s['label']:4s}] $/hr @$1k: flat {s['flat_rep_10']:+.1f} -> {s['flat_rep_P']:+.1f}"
                  f"   sized {s['sized_rep_10']:+.1f} -> {s['sized_rep_P']:+.1f}"
                  f"   | best-S sized(P) {s['best_sized_P']:+.1f} @${s['best_S_P']:,.0f}/leg"
                  f"   (old v1 ceil {s['ceil_10']:+.1f})")
        print()
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "_s52_fill_window_audit_results.json"), "w") as f:
        json.dump(out, f, indent=2, default=float)
    print("READING: if the price-eligible window >> 10s and capP >> cap10, the deploy-size $/hr in every prior")
    print("matrix cell is UNDERSTATED by the 10s truncation — rebuild the matrix on capP (finite S only).")


if __name__ == "__main__":
    main()
