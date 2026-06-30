# S47 FINDINGS — entry-timing & wrong-tail-gating are DEAD; two-factor conviction SIZING is the edge

Branch `claude/crypto-liquidity-signals-s47-3l25k5` (dev). ALL numbers PROVISIONAL on ONE ~11.7h window
(the rolling alt book ending 2026-06-29 23:29; reproduces S46 byte-identical -> SAME window, not yet a 2nd
window). Per-cell, vs a random-tilt falsification control. Do NOT size off these until a 2nd window + real fees.

## The levers map (what we learned)
1. **Entry timing (job #2) — DEAD.** Built a causal early-arm + price-reversal retimer (`odcore/flip_detector.
   retime_flips`, leakage PASS, off by default, eps->inf == baseline). Entries are already near-optimal:
   peak-BEFORE-entry lag ~2 bps (uniform across swing sizes), median off-top vs the true up-leg peak ~= the
   half-spread; price near a turn is flat (1-2 bps over 1-2s, the S40 symmetry). Best retime gain +1.5% net/leg,
   degrades at tight eps. The "6-10 bps off the top" in the walk was a ±300-cell-window artifact (neighbouring
   swings), not our own swing. NOT recoverable.
2. **Wrong-tail GATING (job #4) — DEAD, three ways.** The losing ~26% are NOT separable at entry: every causal
   feature ~0.53 AUC; the only thing unique about losers is look-ahead (adverse-after AUC 0.905 = the definition;
   they're bigger swings that happened to continue). Tested: dipole-exhaustion gate (anti-predictive), climax-
   volume gate (removes winners, win% drops, total net halved), adverse-excursion STOP (cuts winners that
   reverse). EVERY gate LOSES total net (baseline trades-all makes the most). The wrong-tail is IRREDUCIBLE.
   **Gating subtracts; sizing adds** (Greg) — this is why the edge is sizing, not filtering.
3. **TWO-FACTOR conviction SIZING (jobs #3+#4 reframed) — THE EDGE.** Keep every trade; SIZE up the high-
   conviction turns. Two independent axes (per-cell screen, corr vs target, all 5 cells):
   - **SIZE axis** (predicts |move|, sign-CONSISTENT on all 5 cells): vol_60 (+.13..+.26), volat_120
     (+.12..+.22), runup (+.10..+.17), **dive_depth = |lean@pivot| (+.07..+.165, Greg's S40 depth->size,
     reproduced STRONGER)**, clmx_60 (+.08..+.12).
   - **NET/QUALITY axis** (predicts win/lose): ONLY clmx_60 is sign-consistent; all else flips sign per cell.
   - The sign-"inconsistency" of the other levers is a TARGET artifact: they predict SIZE (consistent), not
     NET (inconsistent). climax is the one lever on BOTH axes -> the best single lever.
   - **E[net] = P(reversal) x E[|move|]** -> size by rank(climax) x rank(size-axis). matched-capital total-net
     lift vs random control: **SOL +3.6sig, DOGE +1.4->+3.2sig (the size axis ACTIVATES doge), BTC +2.2sig.**
     XRP/ETH stay null (+0.1sig) -> flat sizing or their own levers (per-cell deploy rule).
   - Why size matters: mean swing ~2-4 bps < the 20 bps fee floor; the money is only in big swings
     (swing>=20: n=5 @ +25.93/leg). The SIZE axis is highly predictable even though NET is not -> concentrate
     capital on predicted-big + predicted-quality turns.

## Deployable form (provisional)
Per cell, conviction = rank(clmx_60) x rank(z(vol_60)+z(volat_120)+z(runup)+z(dive_depth)); size multiplier
= clip(1+alpha*z(conviction)); KEEP all trades. Deploy on SOL/DOGE/BTC. clmx_60 = the universal lever; the
size levers are causal-at-the-flip. Sizing, NOT gating.

## Mandatory gates before sizing for real (NOT yet done)
- **2nd window**: every number here is one window (== S46's). The rolling book must advance (or off-git
  storage) for an independent test. The random-tilt control only proves in-window signal, not generalization.
- **Real fees (job #5)**: everything is GROSS-of-fee (half-spread is in the prices). Mean swing 2-4 bps ->
  taker fee on last-option exits + maker rebate could erase the base +2.19/leg. This is the survival gate.
- **Causal rolling normalization** of the conviction z-scores + re-run `assert_no_leakage` before wiring.
- Then wire conviction->size into `simulate_swing_maker` (the job #3 scale-in) and the emit path.

## JOB #5 NET-OF-COST — DONE (the survival gate). RAZOR-THIN + FEE-CRITICAL.
simulate_swing_maker(maker_fee_bps, taker_fee_bps); open always maker, close maker-at-turn or taker-on-last-option.
Per cell, net/leg by scenario (✓ survives / ✗ negative):
| cell (taker%) | gross | mk0/tk5 (realistic) | mk1/tk5 | mkRebate-0.5/tk5 |
| SOL (10%)  | +2.19 | +1.68 ✓ (sized 1791) | -0.22 ✗ | +2.63 ✓ |
| BTC (3%)   | +0.60 | +0.47 ✓ (sized 834)  | -1.51 ✗ | +1.45 ✓ |
| XRP (16%)  | +1.01 | +0.23 ~              | -1.61 ✗ | +1.16 ✓ |
| ETH (10%)  | +0.40 | -0.10 ✗             | -2.00 ✗ | +0.85 ✓ |
| DOGE (47%) | +1.09 | -1.28 ✗             | -2.80 ✗ | -0.51 ✗ |
VERDICT:
1. Mean swing 2-4 bps -> even a 1 bp maker fee (x2 legs) is FATAL (all cells negative at mk1/tk5, win% craters).
   The strategy REQUIRES maker fee <= 0 (zero or rebate). Load-bearing execution requirement.
2. At realistic mk0/tk5 it SURVIVES on SOL (+1.68) and BTC (+0.47); two-factor sizing IMPROVES net-of-fee there
   (sol 1337->1791, btc 591->834). DEPLOYABLE cells = SOL, BTC.
3. DOGE DIES despite its +3.2sig sizing signal -- 47% of exits are forced TAKER flattens. Signal real, EXECUTION
   kills it. Taker rate is as important as the signal. (Fix: better maker fill / front-of-queue, or skip doge.)
4. A maker REBATE rescues XRP/ETH (and fattens SOL/BTC); not DOGE.
5. Sizing helps net-of-fee everywhere and rescues marginal cells (eth flat -75 -> sized +15).
BOTTOM LINE: real but thin. Deploy net-of-fee on SOL/BTC with maker<=0; rebate extends to XRP/ETH; DOGE blocked
by taker rate. STILL one window -> 2nd window remains the outstanding gate before sizing for real.

## Files (scratchpad prototypes, not committed; logic to port if it survives the 2nd window)
proto_job2*/proto_walk_decomp (timing), proto_wrongtail*/proto_stop (gating), proto_spread/proto_sizing/
proto_levers_corr/proto_dive/proto_size_screen/proto_twoaxis (sizing). Committed: `retime_flips` in
`odcore/flip_detector.py` (leakage-clean, off).
