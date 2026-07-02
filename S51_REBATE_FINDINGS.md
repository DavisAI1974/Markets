# S51 FINDINGS — the rebate lever QUANTIFIED (it's super-linear) + venue shortlist + 4x pipeline speedup

> ⚠ **NO SINGLE NUMBER IN THIS DOC IS "THE CEILING" (Greg, S51 close).** Every $/hr below is one cell of the
> matrix {venue, maker fee, FLAT|SIZED, v1|v2 fill, window}: the SAME SOL legs read +$18/hr (mk0·flat·v1)
> to +$142/hr (−2bp·wider book·v1) to −$7/+$20 (v2 worst-case mk0/−1bp) — and everything here is measured on
> Coinbase's ~$4.7M/hr tape, i.e. PRE-Bybit (~10x tape). Cite the cell, not "the ceiling." The sizing-on-
> winners contribution is NOT finalized in these numbers — that accounting is S52 JOB 1; treat the sized
> columns as a floor on what sizing adds, per the forward ledger (+16% SOL … +47% doge OOS).

Jobs 1+2 of `KICKOFF_2026-07-02_S51.md`, plus a verified-bit-identical performance pass on the shared pipeline.
Tools changed IN PLACE per the standing rule: `scripts/_capacity_model.py` (rebate/spread scenario sweep),
`_birth_probe.load_book` + `_liquidity_dive.{build_channels,median_spread_bps}` (single-parse reuse).

## Job 1 — the rebate scenario sweep (SOL focus; all cells run)

`scripts/_capacity_model.py` now sweeps scenarios = (maker fee, spread multiplier) over the SAME real legs
(leg open/close indices are volume-determined — fee/spread-independent — so channels build once per cell and
only net_bps changes per scenario). Flat vs SIZED reported at each scenario. Results
`_capacity_model_results.json`; books = the same windows as S50 (SOL 35h ... BTC 196h control).

### SOL (the focus cell) — sized ceiling $/hr (all-turn-flow, 1s entry window, tk5)
| scenario | net/leg | ceiling $/hr | vs mk0 | sizing lift @$1k |
|----------|---------|--------------|--------|------------------|
| mk0 (Coinbase today) | +1.73 bps | +$18 | 1.00x | +21% |
| **maker −1 bp** | **+3.72 bps** | **+$71** | **3.9x** | +11% |
| maker −2 bp | +5.72 bps | +$124 | 6.8x | +8% |
| −1 bp + 1.5x wider book | +4.40 bps | +$89 | 4.9x | +10% |
| −2 bp + 1.5x wider book | +6.40 bps | +$142 | 7.7x | +8% |

**The lever is SUPER-linear, not linear.** S50 estimated "−1 bp ≈ doubles $/hr"; measured it's ~4x, because the
rebate does not just scale winners — it FLIPS currently-negative legs positive, so the profitable fraction of
flow grows with the rebate. Same shape on every cell (ETH +$2 → +$68 ceiling at −1 bp; BTC's negative mk0
ceiling −$5 → +$31; XRP +$6 → +$47; DOGE capacity-starved as always, +$6 → +$11).

### The rebate x sizing interaction — S50's hypothesis CORRECTED
S50 predicted the sizing lift should GROW under a rebate (rebate cushions the wrong-tail you load into).
Measured: the OPPOSITE, in % terms — SOL +21% (mk0) → +11% (−1bp) → +8% (−2bp); same monotone shrink on every
cell. Mechanism: the rebate is a UNIFORM per-leg add, so it lifts the flat baseline proportionally more than
the sized overlay (sizing's absolute $ add stays ~flat while the base grows). ALSO: at the flow-capped ceiling
the lift → ~0 — when every leg's fill is bounded by the same real flow, up-sizing conviction legs cannot buy
more fill. **Sizing remains a capital-constrained-regime lever (KEEP it — it still adds ~+10-20% at deploy
sizes); it is NOT amplified by the rebate.** Per falsification-first, the hypothesis is dead; the sizing stays.

## Job 2 — rebate venue shortlist (primary-source verified)

Agent-verified from official exchange docs (NOT memory). Full detail in the session transcript; headline:

| venue | reachable maker rebate | bar | MM path |
|-------|------------------------|-----|---------|
| **Bybit** (MM Incentive Program) | −0.1 to −1.25 bps on perps | **maker SHARE ≥0.03% weighted (MM1)** — NOT a volume wall; 1-month trial | **YES** — email application (institutional_services@bybit.com) |
| **Backpack** (SOL-native) | MM5 top-tier maker rate for first month + share of $300k/mo pool ($200k perps); VIP2 0% maker ongoing | apply; then ≥1% allocation, avg order ≥$2k, liquidity score | **YES** — vip@backpack.exchange. ⚠ exact rebate bps image-locked in docs — confirm with their desk |
| Gate (GMMC) | to −1.2 bps | $50M/30d futures TO APPLY | Y (moderate wall) |
| KuCoin | to −1.5 bps (USDC pairs) | $30M/30d or VIP proof | Y (moderate wall) |
| Hyperliquid / dYdX / Deribit / Binance / OKX / Kraken | rebates exist but gated on >0.5% share / $100M-$1B walls / VIP8+ | — | not reachable small |
| Bitfinex | 0 fee, NO rebate (zero-fee move Dec 2025) | — | n/a |

**Recommendation: Bybit first (the only major venue whose rebate qualifies on maker share, not volume — exactly
our shape: high turn-count passive quoting), Backpack second (SOL-native, needs a desk conversation to pin the
bps).** Both are email-application MM programs, no $250M wall. NOTE the S51 sweep says even the minimum Bybit
MM1 rebate (−0.1 bp) helps, but the real money is at ≥−1 bp (MM2/MM3 tiers or Backpack's pool economics).
Caveat per the per-cell rule: a rebate on a TIGHTER SOL book than Coinbase's may not print — Job 3 (collect the
venue's SOL book, re-measure spread+fill there) is the decisive test and stays NEXT.

## Pipeline speedup — 4x per cell, verified BIT-IDENTICAL (money-neutral by construction)

Profiled the deploy path: each cell decompressed+parsed the ~20-50MB gzip book **three times**
(`build_channels` → `load_book`, an explicit `load_book` for timestamps, and `median_spread_bps` re-reading the
file), and `load_book` spent most of its time in 8 tiny `np.sum` calls per row (67s on the smallest book).
Fixes, all backward-compatible:
- `_birth_probe.load_book`: sequential-prefix depth sums for K=1/3/5 (bit-identical to np.sum below numpy's
  8-element pairwise threshold) + np.sum kept at K=10 (preserves its exact reduction order); also captures
  `spread` per row. **1.9x faster, verified bit-identical on all arrays** (a pure-prefix variant was 3.5x but
  differed at the last ULP on K=10 — rejected; we don't ship non-bit-identical changes to shared primitives).
- `build_channels(path, K, W, raw=None)` / `median_spread_bps(path, raw=None)`: optional preloaded-book reuse;
  `paper_trade.cell_trades` + `_capacity_model.cell_scenarios` now parse each book ONCE.
- **Verification (sandboxed old-vs-new at efd646b in a worktree): doge 1865 trades, sol 5376 trades — 0
  differing fields. The forward ledger is unaffected; this buys iteration speed, not P&L.**

## Job 4 — v2 QUEUE-HONEST fill model (the lower bound; wired into `_capacity_model.py`)

v1 assumed every opposing $ in the entry window fills US (front-of-queue / we set the new best price). v2
applies the `odcore/maker_book.py` queue discipline: we join the BACK of the existing best level, so the size
already resting there must trade through before our first unit fills → fillable$ = max(0, window_flow −
best_level_size). The two are a truth BRACKET: the executor posts at the turn, so when our quote IMPROVES the
book we are front-of-queue (v1); when we join an existing level we are back-of-queue (v2). Reality is between.

Key v2 numbers (flat, $1k/leg rep | ceiling):
| cell | legs fillable (v2) | mk0 v2 | −1bp v2 | −2bp v2 ceiling |
|------|--------------------|--------|---------|-----------------|
| SOL  | 20% (med cap $0)   | +$1 \| **−$7** | +$4 \| +$20 | +$46 |
| ETH  | 44%                | +$0 \| −$6 | +$7 \| +$43 | **+$92** |
| XRP  | 22%                | −$0 \| −$2 | +$3 \| +$22 | +$46 |
| BTC  | 22%                | +$0 \| −$7 | +$2 \| +$19 | +$46 |
| DOGE | 32%                | +$0 \| +$3 | +$1 \| +$7  | +$10 |

Three honest reads:
1. **At mk0, worst-case queue position, the strategy does NOT print** (v2 ceilings NEGATIVE on 4/5 cells) —
   the sharpest statement yet of why Coinbase-without-a-rebate is not deployable at size.
2. **The rebate flips even the worst case positive** (−1 bp: every cell's v2 ceiling > 0). The rebate is not
   just a magnitude lever, it is the VIABILITY guarantee under pessimistic queue assumptions.
3. **Queue-honesty favors DEEP books: ETH overtakes SOL in the v2 world** (44% of legs fillable vs 20%;
   −2 bp v2 ceiling +$92 vs +$46). If the rebate venue's SOL book is thin at the turns, ETH may be the better
   first cell THERE — Job 3's venue-book measurement decides, per the per-cell rule.

## Job 5 — per-leg size cap: tested on the forward ledger, answer = DON'T tighten (falsified)

The cap mechanism already exists (`size_legs` `hi_clip=4.0`). Tested cap ∈ {1,1.5,2,2.5,3,4} on the FORWARD
LEDGER (25,845 trades, multi-window — not one-window tuning), matched-capital normalized, at mk0 AND +1 bp
rebate: net rises MONOTONICALLY toward cap 4.0 on sol/eth/btc (sol +9,413 flat → +9,996 @cap4); doge peaks
at 3.0 and xrp at 1.5 by ~1% noise margins. The loaded-up legs are net-positive in aggregate — the wrong-tail
does not need bounding beyond the existing 4x clip. **No code change; hi_clip=4.0 IS the validated cap.**
(S50's "add a per-leg size cap" idea is hereby closed by falsification, like the rebate x sizing hypothesis.)

## Job 3 WIRED — Bybit venue-book collection is LIVE + the total-$/hr venue read (Greg's frame)

- `bybit_book_collector.py` (new, on 5c5vg9): Bybit v5 linear-perp L2 collector, SAME row schema as the
  Coinbase one so the whole pipeline consumes venue books unchanged. **Smoke-tested live** (584 rows/60s,
  0 reconnects; `load_book`/`median_spread_bps` read it). `bybit_book_collectors_durable.yml` pushed to the
  DEFAULT branch (cron 0 */6, SOL+ETH → `data/{sol,eth}-bybit-book`), same guardrail as the Coinbase crons.
- **Venue stats (primary sources = the venues' own APIs, this session):**
  | venue | SOL market | turnover | spread |
  |-------|-----------|----------|--------|
  | Bybit perp | SOLUSDT | **~$47M/hr** (24h WS ticker) | 1.24 bps |
  | Coinbase spot | SOL-USD | ~$4.7M/hr | 1.36 bps |
  | Backpack perp | SOL_USDC_PERP | ~$1.0M/hr | 1.24 bps |
  | Bitfinex perp (zero-fee) | SOLF0:USTF0 | ~$0.05M/hr | 6.6 bps |
  (ETH: Bybit ~$111M/hr vs Coinbase ~$10.7M/hr.)
- **Greg's frame (load-bearing): maximize OUR $/hr, not rebate size, not venue volume.** Venue volume converts
  to our $ through (a) fill fraction at our capital and (b) the saturation wall. So: Bitfinex's zero fee +
  fat 6.6 bps spread is the best PER-TRADE economics on paper and the WORST per-hour (flow-dead: our wall
  ~$2/hr). Bybit's 10x flow is the real lever — BUT Bybit's standard maker fee is +2 bps, which makes our
  ~1.7 bps edge NEGATIVE: the MM program (or 0-maker VIP) is the VIABILITY gate there, and any rebate beyond
  it is gravy. The projections (same turn structure assumed — the accruing venue book decides): Bybit at
  MM1 ~+$18-25/hr at $1k/leg (~full fills), ~+$100-150/hr at $10k/leg; at MM2/3 rebates roughly 2-3x that.

## Greg's scale-in picture — probed hard (falsification-first). Verdict: architecture right, mechanism
## backwards, NOT deployable off this model class; re-test on the venue book under a rebate.

Greg (S51): "offers lifted on the way down the slide on winners, flatten at the valley, flip, bids hit on
the way up" — i.e. scale IN along the leg instead of one fill at the turn, and size should ride winners.
Two probes built (execution-layer only, same flips, no new signal):

1. **`scripts/_scale_in_probe.py`** (per-leg, every opposing trade fills our pegged quote, all inventory
   marked to the leg's actual close):
   - **Q1 (the mechanism) FALSIFIED: LOSERS fill more, not winners** (SOL median opposing flow $6.7k on
     losing legs vs $3.6k on winning; ETH same direction). A resting quote fills hardest when price rips
     AGAINST it — the S45 adverse-selection autopsy, re-confirmed. "Sizing up on winners not losers" cannot
     be had for free from flow; the market hands more size to your losers.
   - **Q2 (total $) looked spectacular** (SOL mk0 +$15.6/hr @$1k/leg → +$169 @$25k vs one-shot +$7/+$24)
     — BUT the honesty flag maxed out: accumulated inventory = 4-20x the exit-turn flow. The single-point
     flatten is IMPOSSIBLE at size; these numbers are mark-to-close fiction at large caps.
2. **`scripts/_inventory_sim.py`** — the FAITHFUL version of Greg's picture (the flatten IS the next leg's
   entry: fills unwind carried inventory then build the new side; no separate exit; cash/coins accounting;
   maxDD + tape-share honesty metrics):
   - mk0 conviction: SOL +$3-6/hr at $1-5k caps, NEGATIVE at $25k; ETH negative — the naive scale-in $
     evaporate under honest exit accounting.
   - maker −1 bp: SOL +$18-43/hr, ETH +$11-87/hr — the rebate makes volume-multiplication profitable.
   - **REVERSED-SIDE CONTROL FIRES (the disqualifier): on SOL the control (quote AGAINST the conviction
     side) makes MORE at mk0 (+$9→+$60/hr) because it fills 50% more volume.** In this front-of-queue model
     class, fill VOLUME x half-spread dominates any signal content → the class cannot validate the strategy
     change (it would bless literally any always-on one-sided quote — which S45 measured as the adversely-
     selected victim, and the v2 queue model marks 80% of legs unfillable). Tape share at the bigger caps
     (16-72% of the venue's one-sided flow) is independently implausible on Coinbase.

**Where this lands (per-cell rule, honest):** the executor's one-shot-at-the-turn design SURVIVES — it was
built precisely to avoid the always-resting adverse-selection trap the probes just re-measured. The scale-in/
netting ARCHITECTURE (Greg's flatten=flip insight) is credible AND becomes genuinely interesting only under
(a) a rebate (marginal fills profitable) + (b) a 10x tape (our fill share plausible: the same $150k/hr of
fills is 0.3-1.5% of Bybit's tape vs 6.5% of Coinbase's) + (c) a QUEUE-AWARE fill model (the v2/maker_book
discipline, not front-of-queue). All three land together on the accruing Bybit book — that is the S52 test,
gated on real venue data, NOT deployable off this window.

## The "why are profits so low" question (Greg) — answered with measurements, not vibes
The code is not leaving money on the table within its model: (1) trades verified bit-identical through the
speedup; (2) sizing cap already optimal (forward-ledger falsification); (3) the one-shot executor beats the
scale-in alternatives once exits are honest; (4) the S50 capacity correction (entry-window fill) was RIGHT —
the whole-hold version's fatter numbers were the same mark-to-close fiction the scale-in probe just re-found.
The $/hr is structurally capped by **per-fill edge (thin, 1.7 bps at mk0) x honestly-fillable volume (queue-
limited)**. The levers that survive every falsification run this session: the REBATE (fee bps on every fill),
VENUE FLOW (10x tape → 10x the saturation wall AND plausible fill share), and capital-per-leg up to the wall.
All three = the Bybit MM path. The venue book now accruing decides it with measurements.

## NEXT
1. Let `data/{sol,eth}-bybit-book` accrue (cron live) → re-run the FULL stack on the venue book: spread,
   turn structure, v1/v2 capacity, and the netting sim under the reachable MM rebate. The decisive test.
2. Greg action: fire the Bybit MM application (institutional_services@bybit.com) / Backpack VIP desk
   (vip@backpack.exchange) — application-gated, not volume-gated; nothing blocks starting now.
3. Optional: queue_frac interpolation of the v1/v2 bracket once real queue position is observable on the
   venue (order-level data or our own resting orders).
