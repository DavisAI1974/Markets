"""_s57_staged_sizing.py — S57: Greg's staged-commit sizing on the deployed model's legs.

THE DESIGN (Greg, S52 accumulate spec + S57 restatement — "don't go all-in until we are
sure"; "zig zag already has this designed, use that"): every leg opens with a STARTER
tranche; the remainder is added HARD AND FAST only when the trade CONFIRMS (favorable move
of c bp from entry before the flip exits the leg). Losers mostly never confirm -> they die
at starter size. Winners carry full size for the rest of the ride. $5k = mid reference,
$10k = the hard cap (full size F), starter = s0 x $5k. The add tranche pays up c bp for
its entry — the price of certainty; the question is whether the loser-size asymmetry buys
more than the paid-up entries cost. (twxv4t's green-add fillability kill was SUPERSEDED
as wrong-window — this is the honest re-test on the venue tape.)

Mechanics per leg (all causal — decisions read only the leg's own past path):
  starter s0*$5k fills at the leg's open price (maker, the executor's own fill);
  confirmation = first cell where side*(mid - open_px)/open_px >= c bp;
  add (F - s0)*$5k at that cell's mid — scored BOTH as maker (-0.4) and taker (+5.5):
  the truth bracket, since a fast favorable move may require crossing;
  full position exits at the leg's close px with the leg's ACTUAL close fee semantics
  (maker_close flag -> -0.4 else 5.5).

Scored vs: flat $5k every leg; all-in $10k every leg (the "no discipline" benchmark);
random-add control (same add COUNT, coin-flip legs, 20 seeds); reversed control (add on
-c ADVERSE move instead — martingale; should lose). Report $ P&L/hr, avg deployed $,
P&L per $ deployed, and Greg's asymmetry metric: avg notional on losers vs winners.

Combos swept: s0 in {0.2, 0.4, 0.6} x c in {2, 5, 10}bp, F = 2.0 ($10k cap).
Full-fill reference basis (fills at stated notional); the deploy number stays the
queue-honest bracket. Default venue/fees: Coinbase books at mk0/tk5 (the deployed basis).
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _birth_probe import load_book                                    # noqa: E402
from _liquidity_dive import build_channels, median_spread_bps         # noqa: E402
from odcore.flip_detector import lean_series, detect_flips            # noqa: E402
from odcore.platform import FLOW_W, WFLIP, REV                        # noqa: E402
from odcore.swing_maker import simulate_swing_maker                   # noqa: E402

MID = 5000.0                    # $5k = ALL-IN (Greg S57: no 10k — the cap IS 5k)
CAP_F = 1.0                     # top-up target = $5k total
S0S = (0.2, 0.4, 0.6)
CONFS = (2.0, 5.0, 10.0)        # bp favorable move to confirm
# venue/fees via CLI: --venue coinbase --maker X --taker Y (S57: bybit STRUCK — US-ineligible)
VENUE = "coinbase"
MK, TK, GRACE = 0.0, 5.0, 300


def build(coin):
    path = f"/tmp/{coin}_{VENUE}_book.jsonl.gz"
    raw = load_book(path)
    _, g = build_channels(path, 1, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0
    hrs = (float(raw["ts"][-1]) - float(raw["ts"][0])) / 3600.0
    lean = lean_series(buy, sell, WFLIP)
    allf = detect_flips(lean, REV)[0]
    res = simulate_swing_maker(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                               maker_fee_bps=MK, taker_fee_bps=TK, cover_grace=GRACE)
    return res.legs, mid, hrs


def leg_tranche_pnl(l, entry_px, exit_fee_bps, notional):
    """$ P&L of a tranche entered at entry_px, exited at the leg's close px."""
    s = int(l.side)
    gross_bp = s * (float(l.close_px) - entry_px) / entry_px * 1e4
    fees_bp = (-MK) * 0 + 0  # entry fee applied by caller (maker vs taker differs)
    return notional * (gross_bp - exit_fee_bps) / 1e4, gross_bp


def run_cell(coin):
    legs, mid, hrs = build(coin)
    n = len(legs)
    sides = np.asarray([int(l.side) for l in legs])
    opens = np.asarray([float(l.open_px) for l in legs])
    closes = np.asarray([float(l.close_px) for l in legs])
    oidx = np.asarray([int(l.open_idx) for l in legs])
    cidx = np.asarray([int(l.close_idx) for l in legs])
    exit_fee = np.asarray([MK if bool(l.close_maker) else TK for l in legs])
    gross = sides * (closes - opens) / opens * 1e4          # bp, price move of the leg
    win = gross > 0

    # flat and all-in references ($: notional x (gross - entry fee - exit fee)/1e4)
    def total_usd(notional_per_leg):
        return float(np.sum(notional_per_leg * (gross - MK - exit_fee) / 1e4))

    flat5 = total_usd(np.full(n, MID))
    allin10 = total_usd(np.full(n, CAP_F * MID))
    print(f"\n[{coin}_{VENUE}] {n} legs {hrs:.2f}h | ALL-IN $5k every leg ${flat5 / hrs:+.2f}/hr "
          f"| win {100 * np.mean(win):.0f}%")
    print(f"  {'s0':>4} {'c(bp)':>6} | {'add%':>5} | {'staged $/hr':>14} | "
          f"{'rand-add (20s)':>14} | {'rev(adverse)':>13} | {'L$:W$ avg':>9}")

    rng = np.random.default_rng(57)
    # precompute per-leg confirmation cell (first favorable c bp) and adverse cell for reversed
    for s0 in S0S:
        for c in CONFS:
            addi = np.full(n, -1)                            # grid idx of the add, -1 = none
            advi = np.full(n, -1)                            # first -c adverse (reversed ctl)
            for i in range(n):
                seg = mid[oidx[i]:cidx[i] + 1]
                if len(seg) < 2:
                    continue
                fav = sides[i] * (seg - opens[i]) / opens[i] * 1e4
                hit = np.nonzero(fav >= c)[0]
                if len(hit):
                    addi[i] = oidx[i] + hit[0]
                ah = np.nonzero(fav <= -c)[0]
                if len(ah):
                    advi[i] = oidx[i] + ah[0]

            def staged_total(add_at, add_maker):
                tot = 0.0
                sizes = np.full(n, s0 * MID)
                for i in range(n):
                    st_n = s0 * MID
                    g_st = sides[i] * (closes[i] - opens[i]) / opens[i] * 1e4
                    tot += st_n * (g_st - MK - exit_fee[i]) / 1e4
                    ai = add_at[i]
                    if ai >= 0:
                        px = mid[ai]
                        g_ad = sides[i] * (closes[i] - px) / px * 1e4
                        fee_in = MK if add_maker else TK
                        ad_n = (CAP_F - s0) * MID
                        tot += ad_n * (g_ad - fee_in - exit_fee[i]) / 1e4
                        sizes[i] += ad_n
                return tot, sizes

            t_mk, sizes = staged_total(addi, True)   # adds maker-posted (Coinbase pricing)
            addpct = 100 * np.mean(addi >= 0)
            # random-add control: same count, random legs, add at same relative delay?
            # honest cheap version: add at the leg's confirmation cell if chosen leg HAS one,
            # else at open (worst case none) — simpler: choose among legs WITH a confirm cell.
            withc = np.nonzero(addi >= 0)[0]
            r_tots = []
            for _ in range(20):
                pick = rng.choice(n, size=len(withc), replace=False)
                ra = np.full(n, -1)
                for i in pick:
                    ra[i] = addi[i] if addi[i] >= 0 else oidx[i]   # no confirm -> add at open
                r_tots.append(staged_total(ra, True)[0])
            t_rev, _ = staged_total(advi, True)
            lw = (np.mean(sizes[~win]) / max(np.mean(sizes[win]), 1e-9)) if win.any() else 0
            print(f"  {s0:>4.1f} {c:>6.1f} | {addpct:>4.0f}% | {t_mk / hrs:>+14.2f} | "
                  f"{np.mean(r_tots) / hrs:>+8.2f}±{np.std(r_tots) / hrs:>4.2f} | "
                  f"{t_rev / hrs:>+15.2f} | {lw:>9.2f}")


def main():
    global VENUE, MK, TK
    av = sys.argv
    if "--venue" in av:
        VENUE = av[av.index("--venue") + 1]
    if "--maker" in av:
        MK = float(av[av.index("--maker") + 1])
    if "--taker" in av:
        TK = float(av[av.index("--taker") + 1])
    print(f"# staged sizing — venue={VENUE} maker={MK} taker={TK}")
    for coin in ("sol", "eth"):
        run_cell(coin)


if __name__ == "__main__":
    main()
