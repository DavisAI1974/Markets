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

## ⭐ WHAT'S OBVIOUS (my read — verify next session, do NOT treat as gospel)
1. **The bleed is in LONG legs that RUN LONG.** Worst-10 durations exceed the loser average on ALL 4 coins
   (SOL 64 vs 51, BTC 74 vs 45, ETH 66 vs 53, XRP 62 vs 52). A long leg that goes wrong has more time to
   accumulate the loss. → candidate: a max-adverse / time cap on long legs, or long-loser entry selection; check
   whether the deep-bail is even firing on these long ones (it may be too deep to catch them in time).
2. **The worst losers end with the flow FULLY REVERSED against** (exh strongly negative, many at −1.00), far more
   than typical losers (BTC −0.70 vs −0.40, ETH −0.84 vs −0.23). They rode into a complete flow flip.
3. **COIN SPLIT on onset energy — two different bleeds:**
   - **SOL / ETH / XRP worst losers fired with WEAK/NEGATIVE onset energy** (peak below the loser average, ETH
     even negative). Fired on nothing. → the ENERGY GATE (which doubles $/hr on ETH/XRP) directly targets THIS
     bleed — the energy-weak worst losers are exactly what it skips.
   - **BTC worst losers fired with STRONG onset energy (+0.51) and still lost big** — fakeouts/traps. Energy will
     NOT catch these. → this is where the ⭐ BTC BOOK pre-fire tell is the candidate: were these strong-onset BTC
     losers BORN BOOK-NEGATIVE at the valley? If so the book gate catches the exact bleed energy can't.
4. **Several worst losers fired with onset flow MAXIMALLY AGAINST the side (peak ≈ −1.00)** — the entry fired
   directly into opposing flow. Firing is LOCKED (Greg-only), so flag for a FIRING REVIEW, not a self-change.

**Net:** the two S74 leads map straight onto the two bleeds — the ENERGY gate kills the weak-onset losers
(SOL/ETH/XRP), the BTC BOOK tell is the candidate for the strong-onset BTC fakeouts. Long-duration is the
amplifier on both. Confirm these on the per-leg arcs (PNGs) next session before acting.
