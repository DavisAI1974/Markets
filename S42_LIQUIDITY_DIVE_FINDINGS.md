# S42 — LIQUIDITY DIVE FINDINGS (2026-06-23)

Branch `claude/crypto-liquidity-signals-5c5vg9` (fast-forwarded to the S41 tip, then this work on
top). Data: `data/btc-book` -> `/tmp/book.jsonl.gz` (btc_coinbase, 100ms, **11.67h / 420,215 cells**,
3 gaps >1s; gitignored, same pattern as `realbins/`). Tool: `_liquidity_dive.py`.

Rules honored: crypto only; zero synthetic; never tune off one window (cross-segment + held-out OOS +
shuffle null throughout); falsification-first; agnostic 5-step coupler reads what couples (no imposed
direction — the lead/lag SIGN is discovered). **Single cell, single window of one venue/coin — these
are CHARACTERIZATION results, not deploy-grade. Multi-day / multi-venue / per-cell is still required.**

## Why this dive
S41's only surviving structure was on the **liquidity** side; every flow<->price pair was NULL. But
S41 used `abs_return` (price *magnitude*) and never tested liquidity **dynamics**. This dive added the
**signed** return (directional target) + the liquidity-dynamics channels Greg named (book-depth
withdrawal, one-sided depth changes, depth-imbalance velocity).

## HEADLINE — book-depth IMBALANCE LEVEL is a real, OOS, causally-leading next-move predictor
`depth_imb = (bid_depth - ask_depth)/(bid_depth + ask_depth)` at top-K=5.

**PART B — exploitability (40% held-out test, circular-shift null, strictly-forward target):**
| signal | horizon | OOS_r | null_z | hit% | \|fwd move\| |
|--------|--------:|------:|-------:|-----:|------:|
| **depth_imb** | next cell (0.1s) | **+0.164** | **+60** | **63.1%** | 0.06 bps |
| depth_imb | 0.5s | +0.193 | +36 | 62.2% | 0.25 bps |
| depth_imb | 1.0s | +0.184 | +31 | 60.5% | 0.44 bps |
| depth_imb | 5.0s | +0.118 | +11 | 55.5% | 1.32 bps |
| d_depth_imb (velocity) | 0.1s | +0.091 | +40 | 57.1% | — |
| d_bid_depth (one-sided) | 0.1s | +0.048 | +21 | 56.2% | — |
| d_ask_depth (one-sided) | 0.1s | −0.035 | −17 | 56.2%* | — |
| flow (taker lean) | 0.1s | +0.069 | +23 | 57.1% | — |
| **d_total_depth (withdrawal)** | any | **~0.00** | **~0** | **~50%** | — |

\* d_ask_depth predicts the *opposite* sign (asks refilling -> price down), a symmetric echo of imbalance.

**PART A — agnostic 5-step coupler (`score_pair`, all 5 steps + circular-shift tautology null),
10 time-slices for anti-fluke consistency:**
<!-- FILLED FROM _liquidity_dive_partA.out -->
(see `_liquidity_dive_results.json` / table below)

**Causality (two-sided cross-correlation, the non-tradeability check):** `depth_imb` vs signed return
peaks at **lag +1 (+0.1s) = imbalance LEADS price** (cc +0.134), and the lead side is stronger than the
lag side (−0.1s: +0.103). So it is genuinely (weakly) predictive, not merely a lagging reflection of a
move that already happened. This is the canonical top-of-book-imbalance -> next-tick predictor,
recovered cleanly and OOS from our own data.

## What it means (honest reading)
1. **The directional content is in the IMBALANCE, not total depth.** Symmetric book withdrawal
   (`d_total_depth`) is NULL for direction. One-sided withdrawal/refill (`d_bid_depth` +, `d_ask_depth` −)
   carries the same signed information as the imbalance level, just decomposed.
2. **The edge is real but lives BELOW the active-trading fee floor.** Predicted moves are sub-bp at the
   fast horizons where the hit-rate is high (0.06 bps next-cell @ 63%; ~1.3 bps @ 5s but only 55%).
   Median top-of-book spread on this book is sub-bp; Coinbase round-trip is ~80 bps taker / ~50 bps
   maker / ~0 with maker rebate. **No taker strategy clears.** This is a **MAKER / quoting signal** —
   which side to post, when to pull a resting order, queue-position timing — exactly the market-making
   use, consistent with the architecture (`DIPOLE=filter, price=timing, MAKER=lever`).
3. **Reconciles S41.** S41's flow<->price NULL stands for *magnitude*; the *directional* coupling that
   S41 couldn't see lives in book imbalance vs **signed** return, and it is contemporaneous-plus-1-cell,
   not a multi-second lead. Flow (taker lean) also has mild signed-predictive content (+0.069) but is
   dominated by `depth_imb`.

## NOT done / NEXT (the data bottleneck is unchanged)
- **One cell only** (btc_coinbase). Per-cell deploy rule requires the book collector on more
  venues/coins + multi-day depth before any of this is deploy-grade. The collector exists only for
  btc_coinbase; GHA `book_collector_btc.yml` needs Greg's manual "Run workflow" click to accrue.
- A maker-fill model (queue position, adverse selection) is required to turn the 63% next-cell signal
  into a net-of-rebate quoting edge — the realistic path to monetizing a sub-bp predictor.
- Re-run `_liquidity_dive.py` per cell once multi-cell book data exists; confirm the imbalance edge and
  its sign/lead are stable across venues (cross-segment consistency here is the stand-in).

## QUIET FLOOR — stop the dipole firing through a trend (Greg, S42; `_quiet_floor.py`, `odcore/quiet_floor.py`)
Chat's OD run found the book imbalance obeys a clean AR(1) RELAXATION that is quiet/still between
trades: `imb(t+1)=phi*imb(t)+c`. Reproduced on our 11.67h: **phi_quiet=0.944** (Chat 0.947), quiet
OOS-R2 0.76 > trade 0.62 — quiet is the stiller operator. Greg's idea: use it as a FLOOR so the
directional dipole stops re-firing while the imbalance LEVEL just sits elevated and relaxes through a
trend.

- **The floor absorbs the between-trade bumps.** `innov(t)=imb(t)-(phi_q*imb(t-1)+c_q)` has std **0.15
  on quiet cells vs 0.22 on trade cells**, while raw imbalance is 0.38 in both — the smooth relaxation
  is removed, energy concentrates on shocks.
- **Direction lives in the LEVEL, not the innovation.** Replacing level with innovation dilutes the
  edge (next-cell hit 61.6% -> 57.4%). So do NOT replace it.
- **Use the floor as a GATE (the deploy form).** Fire only when `|innov| > k*sigma` (imbalance breaks
  the quiet floor = a real shock). At k=1.5sigma the gate opens **7% on quiet cells vs 16% on trade
  cells (2.3x)** — silent between trades, fires on shocks — and the gated direction (sign of the level)
  keeps the **62% hit** (k=2 sharpens to 62.7%). Raw level would hold "on" ~15% of ALL cells
  continuously (the churn). **Direction kept, between-trade firing cut.**
- `odcore/quiet_floor.py`: portable `fit(imb, quiet, train_frac)` -> `QuietFloor` with causal
  `floor_hat / innovation / gate / gated_signal`. Leakage-safe (fits phi_q + gate sigma on TRAIN quiet
  cells only). Fit one per cell. This is the wiring Greg asked for: the quiet operator is the floor; the
  dipole fires on shocks, not through the trend.

## Files
`_quiet_floor.py`, `odcore/quiet_floor.py` (quiet-floor gate),
`_liquidity_dive.py` (PART A agnostic coupler x10 slices; PART B OOS exploitability + null + fee floor),
`_liquidity_dive_results.json`. PNGs none. Builds on `_birth_probe.py`, `odcore.coupling_scanner`,
`odcore.leadlag`.
