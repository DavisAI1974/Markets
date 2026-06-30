# SESSION HANDOFF — S47 (2026-06-30) — timing & wrong-tail-gating are DEAD; the edge is two-factor conviction SIZING (climax × size-axis); net-of-fee survives on SOL/BTC only with maker fee ≤ 0

Branch: `claude/crypto-liquidity-signals-s47-3l25k5` (dev; ff-merged from canonical S46 tip `caae666`, then
S47 work committed+pushed: `221f389`+ this doc). ALL numbers PROVISIONAL on ONE ~11.7h window (the rolling alt
book ending 2026-06-29 23:29 — reproduces S46 BYTE-IDENTICAL, so it is the SAME window, NOT a 2nd window).
Per-cell, vs a random-tilt falsification control. DO NOT size off these until a 2nd window + the fee work below.
Full detail: `S47_SIZING_FINDINGS.md`. Read that + this.

## What S47 set out to do vs what happened
The kickoff named two "remaining edges": entry timing (job #2, "biggest remaining edge") and wrong-tail
gating (job #4). **Both turned out to be dead ends.** The real edge came from Greg's two live interventions
(size-don't-gate; spread/depth as levers) and is **two-factor conviction SIZING.**

## The levers map (the durable result — start S48 from here, don't re-chase)
1. **Entry timing (job #2) — DEAD.** Built `odcore/flip_detector.retime_flips` (causal early-arm + price-
   reversal; leakage PASS; off by default; `eps→inf` == `detect_flips`). Entries already near-optimal: peak-
   before lag ~2 bps (uniform across swing sizes), median off-top vs the true up-leg peak ≈ the half-spread,
   price flat at the turn (1–2 bps over 1–2s = the S40 symmetry). Best retime +1.5% net/leg, worse at tight
   eps. The "6–10 bps off the top" in the walk was a ±300-cell-window artifact (neighbouring swings). The
   lagging tail is an irreducible causal limit (can't sell a sharp top without look-ahead).
2. **Wrong-tail GATING (job #4) — DEAD three ways.** The losing ~26% are NOT separable at entry (every causal
   feature ~0.53 AUC; the only "unique" thing is look-ahead — adverse-after AUC 0.905 = the definition; losers
   are bigger swings that happened to continue). Tested + all net-negative: dipole-exhaustion gate (anti-
   predictive), climax-volume gate (removes winners, win% drops, total halved), adverse-excursion STOP (cuts
   winners that reverse). EVERY gate LOSES total net. The wrong-tail is IRREDUCIBLE. **Gating subtracts;
   sizing adds** (Greg). This is WHY the edge is sizing.
3. **TWO-FACTOR conviction SIZING — THE EDGE.** Keep every trade; SIZE up the high-conviction turns. Two
   independent axes (per-cell corr screen, all 5 cells):
   - **SIZE axis** (predicts |move|, sign-CONSISTENT on all 5): vol_60, volat_120, runup, **dive_depth =
     |lean@pivot| (Greg's S40 depth→size, reproduced STRONGER, +0.07..+0.165)**, clmx_60.
   - **QUALITY axis** (predicts win/lose): ONLY clmx_60 is sign-consistent; all else flips sign per cell.
   - The other levers' sign-"inconsistency" is a TARGET artifact: consistent on SIZE, inconsistent on NET.
     climax is the one lever on BOTH axes → the best single lever.
   - **E[net] = P(reversal) × E[|move|]** → size by rank(clmx) × rank(size-axis). Matched-capital total-net
     lift vs random control: **SOL +3.6σ, DOGE +1.4→+3.2σ (the size axis ACTIVATES doge), BTC +2.2σ;
     XRP/ETH null (+0.1σ).** Simpler `sum` is a robust runner-up. clmx-ALONE already gives sol +2.6σ/btc +3.0σ;
     stacking the wrong (net-screened) levers DILUTES — only the SIZE axis adds.

## Job #5 net-of-cost (the survival gate) — RAZOR-THIN + FEE-CRITICAL
Per cell net/leg (✓ survives / ✗ negative):
| cell (taker%) | gross | mk0/tk5 (realistic) | mk1/tk5 | mkRebate-0.5/tk5 |
| SOL (10%)  | +2.19 | +1.68 ✓ (sized 1791) | -0.22 ✗ | +2.63 ✓ |
| BTC (3%)   | +0.60 | +0.47 ✓ (sized 834)  | -1.51 ✗ | +1.45 ✓ |
| XRP (16%)  | +1.01 | +0.23 ~              | -1.61 ✗ | +1.16 ✓ |
| ETH (10%)  | +0.40 | -0.10 ✗             | -2.00 ✗ | +0.85 ✓ |
| DOGE (47%) | +1.09 | -1.28 ✗             | -2.80 ✗ | -0.51 ✗ |
- Mean swing 2–4 bps → even a **1 bp maker fee is fatal** (mk1/tk5 all negative). REQUIRES **maker fee ≤ 0.**
- At realistic mk0/tk5: **SURVIVES on SOL/BTC** (sizing improves it); marginal XRP; ETH negative; **DOGE dies**
  (47% taker exits — execution, not signal). A maker rebate rescues XRP/ETH, not DOGE.
- **Deployable net-of-fee: SOL/BTC with maker ≤ 0; rebate extends to XRP/ETH; DOGE blocked by taker rate.**

## Committed this session
- `odcore/flip_detector.py`: `retime_flips` + `make_retimed_signal` (causal, leakage-clean, OFF; job-#2 record).
- `S47_SIZING_FINDINGS.md` (the full findings incl. the fee table).
- This handoff + the CLAUDE.md S47 delta + `KICKOFF_2026-07-01_S48.md`.
- Scratchpad prototypes (NOT committed; port if they survive the 2nd window): proto_job2*/proto_walk_decomp
  (timing); proto_wrongtail*/proto_stop (gating); proto_spread/proto_sizing/proto_levers_corr/proto_dive/
  proto_size_screen/proto_twoaxis/proto_fees (sizing + fees).

## Data / env notes
- Books load GZIPPED (`load_book` uses `gzip.open`) — keep the blob gzipped in /tmp; the kickoff's
  `| gunzip` is a bins-workflow copy-paste, WRONG for books. Re-fetch: `git show origin/data/<c>-book:<c>_coinbase_book.jsonl.gz > /tmp/<c>_coinbase_book.jsonl.gz` (NO gunzip).
- `matplotlib` not in the session-start hook — `pip install matplotlib`; run renders with `MPLBACKEND=Agg`.
- The alt rolling book hadn't advanced past S46 (same window). A 2nd window needs the cron to roll forward (or
  off-git storage). btc book is stale (06-22→06-24).

## NEXT (S48) — the two outstanding gates, then wire
1. **2nd window** (THE gate): re-fetch once the rolling book has advanced; re-run proto_twoaxis + proto_fees on
   the fresh window. Does the SOL/BTC two-factor sizing lift + net-of-fee survival REPRODUCE? Don't size until yes.
2. **Lower the taker rate** (the doge lesson + thins the fee drag everywhere): the forced taker flattens are the
   cost sink. Better maker fills / true front-of-queue / a smarter last-option, esp. for high-taker cells.
3. **Causal rolling normalization** of the conviction z-scores + re-run `assert_no_leakage`, THEN wire
   conviction→size into `simulate_swing_maker` (the job-#3 scale-in) and the per-cell emit path
   (`odcore/quiet_registry.py`).
4. Confirm the maker-fee≤0 / rebate venue assumption is real for these cells before any sizing.
