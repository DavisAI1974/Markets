"""_s57_staged_sizing.py — Greg's staged-commit sizing on the deployed model's legs,
priced at the REAL Coinbase fee tiers.

THE DESIGN (Greg, S52 accumulate spec + S57 restatements): every leg opens with a STARTER;
on CONFIRMATION (+c bp favorable from entry before the flip exits) go ALL-IN — top up to the
full $5k ($5k IS the all-in; no $10k). Losers mostly never confirm -> they die at starter
size. Entry = the zigzag's own barely-late fine-flip entry (the executor's legs). Adds are
MAKER-POSTED (taker adds measured fatal at tight confirms — S57 first pass).

FEE MODELS (Greg: "build a few different fee models — tiers we can realistically get to"):
every result prints at each Coinbase Exchange tier (verified schedule, 2026-06 snapshot):
entry <$10k 40/60 | early $100k-1M 10/20 | realistic $1-15M 8/18 | scale $75-250M 3/10 |
top $250M+ 0/6 (labeled ceiling — NOT a tier we hold; the old mk0/tk5 basis was aspirational).
Executor mechanics (fills, cover-grace, close-maker flags) are fee-independent; P&L is
re-priced per tier arithmetically. Exits use the leg's actual maker/taker flag at tier rates.

Controls per tier: random-add (same count, 20 seeds) + reversed (add on -c adverse).
Full-fill reference basis; queue-honest capacity remains the deploy bracket.
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

MID = 5000.0                    # $5k = THE ALL-IN (Greg S57: no 10k)
S0S = (0.2, 0.4)
CONF = 2.0                      # the measured trigger (S57: 69%->93% win separation)
VENUE = "coinbase"
GRACE = 300
# (label, maker bp, taker bp) — Coinbase Exchange schedule, verified 2026-06 snapshot
FEE_TIERS = (("cb_entry <10k", 40.0, 60.0), ("cb_early 100k-1M", 10.0, 20.0),
             ("cb_real 1-15M", 8.0, 18.0), ("cb_scale 75-250M", 3.0, 10.0),
             ("cb_top 250M+ ceil", 0.0, 6.0))


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
                               maker_fee_bps=0.0, taker_fee_bps=5.0, cover_grace=GRACE)
    return res.legs, mid, hrs


def run_cell(coin):
    legs, mid, hrs = build(coin)
    n = len(legs)
    sides = np.asarray([int(l.side) for l in legs])
    opens = np.asarray([float(l.open_px) for l in legs])
    closes = np.asarray([float(l.close_px) for l in legs])
    oidx = np.asarray([int(l.open_idx) for l in legs])
    cidx = np.asarray([int(l.close_idx) for l in legs])
    exit_maker = np.asarray([bool(l.close_maker) for l in legs])
    gross = sides * (closes - opens) / opens * 1e4
    win = gross > 0

    # confirmation / adverse cells at c=CONF (leg-path causal)
    addi = np.full(n, -1); advi = np.full(n, -1)
    addpx = np.zeros(n)
    for i in range(n):
        seg = mid[oidx[i]:cidx[i] + 1]
        if len(seg) < 2:
            continue
        fav = sides[i] * (seg - opens[i]) / opens[i] * 1e4
        hit = np.nonzero(fav >= CONF)[0]
        if len(hit):
            addi[i] = oidx[i] + hit[0]; addpx[i] = mid[addi[i]]
        ah = np.nonzero(fav <= -CONF)[0]
        if len(ah):
            advi[i] = oidx[i] + ah[0]
    g_add = np.where(addi >= 0,
                     sides * (closes - addpx) / np.where(addpx > 0, addpx, 1.0) * 1e4, 0.0)
    g_adv = np.zeros(n)
    m = advi >= 0
    advpx = np.where(m, mid[np.clip(advi, 0, len(mid) - 1)], 1.0)
    g_adv[m] = (sides * (closes - advpx) / advpx * 1e4)[m]

    print(f"\n[{coin}_{VENUE}] {n} legs {hrs:.2f}h  win {100 * np.mean(win):.0f}%  "
          f"(all-in = $5k; adds maker-posted at first +{CONF:.0f}bp; add fires on "
          f"{100 * np.mean(addi >= 0):.0f}% of legs)")
    print(f"  {'fee tier':>20} | {'ALL-IN@entry $/hr':>17} | "
          + " | ".join(f"staged s0={s:.1f} (rand±sd / rev)" for s in S0S))
    rng = np.random.default_rng(57)
    for label, mk, tk in FEE_TIERS:
        xfee = np.where(exit_maker, mk, tk)
        flat = float(np.sum(MID * (gross - mk - xfee) / 1e4)) / hrs
        cells = []
        for s0 in S0S:
            st = s0 * MID * (gross - mk - xfee) / 1e4
            ad = np.where(addi >= 0, (1 - s0) * MID * (g_add - mk - xfee) / 1e4, 0.0)
            t = float(np.sum(st + ad)) / hrs
            withc = int(np.sum(addi >= 0))
            r = []
            for _ in range(20):
                pick = np.zeros(n, bool)
                pick[rng.choice(n, size=withc, replace=False)] = True
                ga = np.where(addi >= 0, g_add, gross)      # no-confirm pick adds at open
                rr = st + np.where(pick, (1 - s0) * MID * (ga - mk - xfee) / 1e4, 0.0)
                r.append(float(np.sum(rr)) / hrs)
            rv = st + np.where(advi >= 0, (1 - s0) * MID * (g_adv - mk - xfee) / 1e4, 0.0)
            rev = float(np.sum(rv)) / hrs
            cells.append(f"{t:>+9.2f} ({np.mean(r):+.2f}±{np.std(r):.2f} / {rev:+.2f})")
        print(f"  {label:>20} | {flat:>+17.2f} | " + " | ".join(cells))


def main():
    global VENUE
    av = sys.argv
    if "--venue" in av:
        VENUE = av[av.index("--venue") + 1]
    for coin in ("sol", "eth"):
        run_cell(coin)


if __name__ == "__main__":
    main()
