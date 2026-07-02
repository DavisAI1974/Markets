# S51 FINDINGS — the rebate lever QUANTIFIED (it's super-linear) + venue shortlist + 4x pipeline speedup

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

## NEXT
1. **Job 3 (decisive): collect Bybit (and/or Backpack) SOL book** — extend the venue-parameterized collector,
   re-measure spread + fill + the swing edge on THAT book before believing the rebate math prints there.
2. Job 4: v2 walk-the-book mark-to-fill model (`odcore/maker_book.py` queue) — honest $/hr at larger size.
3. Job 5: per-leg size cap wired alongside `size_legs` (bounds loaded-up wrong-tail legs; sizing stays ON).
4. Greg action: fire the Bybit MM application / Backpack VIP-desk email (the qualification is an application,
   not a wall — nothing blocks starting it now).
