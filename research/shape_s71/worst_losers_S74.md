# 10 WORST LOSERS per coin (S74) — for the S75 bleed hunt

Pulled from the whole-leg caches (`/tmp/kbook/{coin}_whole.npz`, from `whole_legs.py` via the LIVE
`run_kraken_cell`). Columns: net_bps, dur_s, side, pre_ext (birth→onset seconds), **valley** (trade imbalance
signed-to-side at birth), **peak** (signed imbalance at onset = entry energy), **exh** (signed imbalance at
close), S/L (short/long by median dur). Regenerate: `python3` load `{coin}_whole.npz`, `argsort(net)[:10]`.

## SOL (737 legs, 73h, base-win 62%, median-dur 43s)
worst-10 mean: peak −0.03, exh −0.25, dur 64s, pre_ext 50s  |  ALL-losers: peak +0.20, exh −0.20, dur 51s
Worst: −21.5 / −20.2 / −20.2 / −19.4 / −16.6 ... (8/10 LONG). Several fired with onset flow MAXIMALLY AGAINST
(peak −1.00: #1 BUY, #3, #4).

## BTC (955 legs, 42h, base-win 68%, median-dur 36s)
worst-10 mean: **peak +0.51**, **exh −0.70**, dur 74s, pre_ext 51s  |  ALL-losers: peak +0.16, exh −0.40, dur 45s
Worst: −13.4 / −11.6 / −10.4 / −10.3 / −10.0 ... (9/10 LONG). BTC worst losers fire with STRONG onset energy
(+0.51, ABOVE the loser average) then reverse ALL the way (exh −0.70) — fakeouts/traps, not weak entries.

## ETH (659 legs, 67h, base-win 55%, median-dur 46s)
worst-10 mean: **peak −0.34**, **exh −0.84**, dur 66s, pre_ext 42s  |  ALL-losers: peak +0.09, exh −0.23, dur 53s
Worst: −30.2 / −20.2 / −19.6 / −15.4 / −14.9 ... (7/10 LONG, all SELL-heavy). Weak/NEGATIVE onset energy
(peak −0.34 — fired on nothing) then full reversal (exh −0.84). ETH is the worst single bleed (−30.2).

## XRP (672 legs, 73h, base-win 51%, median-dur 46s)
worst-10 mean: peak −0.06, exh −0.58, dur 62s, pre_ext 36s  |  ALL-losers: peak +0.27, exh −0.17, dur 52s
Worst: −34.7 / −25.3 / −25.1 / −25.0 / −22.7 ... (mixed S/L). Weak onset (peak −0.06 vs +0.27 avg) + hard reversal.

---

## ⭐ THE PATTERNS (rigorous — over the WORST-DECILE, 66–96 legs/coin, NOT the top-10 eyeball)
Split each coin's legs into WINNERS / TYPICAL-lose (net<0 above the 10th pct) / WORST-lose (bottom-10% net) and
compare (script inline in the S74 chat; `{coin}_whole.npz`). What actually holds:

1. **⭐ DURATION is the ONE clean, consistent pattern — the worst losers are LONG.** long% WINNERS→WORST:
   SOL 47→**73%**, BTC 46→**80%**, ETH 49→59%, XRP 52→57%; dur SOL 47→61s, BTC 40→56s, ETH 53→59s, XRP 55→61s.
   **The bleed is TIME** — a long leg that goes wrong runs long enough to pile up the big loss (strongest SOL/BTC).
2. **Flow REVERSES hard at close, grading with severity — but it's the LOSS, not a pre-fire tell.** exh
   WINNERS≈0 → TYPICAL≈−0.15 → WORST −0.3..−0.6; revExh% (exh<−0.5) 37→~45→~55–62%. Descriptive/co-incident
   (flow follows price down), NOT observable before firing.
3. **⛔ ONSET ENERGY does NOT separate the worst losers (corrects the top-10 eyeball).** Over the decile the
   WALL(peak<−0.3)/MUSHY/STRONG(peak>+0.5) buckets OVERLAP heavily between winners and worst-losers — ~a THIRD of
   WINNERS also fire "into the wall," ~half of both fire STRONG; peak barely differs (win +0.20..+0.35 vs worst
   −0.10..+0.28). The earlier "BTC strong-onset fakeouts / ETH weak-onset" split was a top-10 TAIL artifact, not
   the decile pattern. **The entry wall holds — you cannot pick the worst losers apart at entry by their shape.**

**Net (honest):** the bleed lever is **MANAGING LONG LEGS** (a price-based max-adverse / time cap, or tighter
deep-bail on long legs), NOT entry selection — entry can't separate them. ⚠ SOL runs NO deep-bail and its worst
legs reach −21 bps → a concrete candidate (Greg's call, exit/risk). The S74 energy-gate + BTC-book leads still
stand as ENTRY $/hr improvers, but they are NOT the worst-loser bleed fix — long-duration risk control is.
