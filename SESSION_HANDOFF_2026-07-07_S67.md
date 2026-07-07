# SESSION HANDOFF — S67 (2026-07-07) — THE CAPITAL MODEL is built (shared-pool allocator on the live path) + majors graded + Greg's deployment reframe

Read `STRATEGY_INVENTORY.md` (S67 block) first. This session built the capital model end-to-end, graded
the overlooked-majors sweep, and landed Greg's reframe of what the $5k is and how to deploy it.

## THE LANDING (Greg, load-bearing — start S68 here)
- **The $5k is the ENTIRE stack**, not $5k-per-sleeve. The per-coin $5k slice was always the temp tuning
  artifact. The job = **best deployment of ONE $5k pool for max profit-per-hour.**
- **Fill the best edge-per-$ coin FIRST** (greedy, not spread). **Never DROP a coin — idle costs nothing;**
  every coin stays seated & available, the allocator just doesn't fund it when its edge is negative or when
  better coins fill the pool. Don't fund negative-edge (idle > a losing trade).
- This is a **temp harness-tuning setup**: get the mechanics + the per-coin edge right, THEN tune the best
  deployment. Proceed cautiously; existing live path stays byte-untouched.

## WHAT WAS BUILT (all additive; run_cell/run_stream/run_kraken_cell byte-untouched; CANARY PASS bit-for-bit)
- **`odcore/allocator.py`** — `allocate(demands, caps, pool, weights, clusters, cluster_caps, mode)`:
  - `mode="greedy"` (DEFAULT, Greg): rank seated coins by edge-per-$, fill the best to its cap first, then
    the next, until the pool is spent; **skip non-positive edge; never drop a coin.**
  - `mode="proportional"`: weighted water-fill (spread for Sharpe) — reference.
  - 3 caps in priority: per-coin capacity → correlation-cluster → shared pool. + `pnl_correlation` /
    `cluster_by_corr` (union-find) promoted from basket_sim.
- **`odcore/platform.run_portfolio`** (NEW, additive) — event-driven shared-pool replay OVER per-cell legs
  (never re-decides a trade; sim=live). Returns `PortfolioResult` (POOL RETURN, funded%, pool Sharpe, util).
- **`scripts/portfolio_sim_kraken.py`** (NEW sim) — loads Kraken tape, LIVE `run_kraken_cell` → legs,
  per-coin capacity caps (`capacity.py`), edge weights, corr clusters, `run_portfolio` over $5k. Flags:
  `--seats {majors,graded,all}` (default all — never drop), `--mode {greedy,proportional}`, `--pool`,
  `--canary`. Reports POOL RETURN vs the acknowledged-WRONG sum-@-$5k line.
- **`scripts/grade_coin_kraken.py`** (NEW) — per-cell S54 gate for ANY new coin (forward-vs-reversed +
  circular-shift NULL floor + per-window sign consistency + REV sweep) via LIVE run_stream, front-of-line,
  kr_mk0. Emits a recommended CellConfig(side, rev). Reusable for candidate majors AND small-caps.
- **CANARY (load-bearing):** `--canary` proves `run_portfolio(pool=inf, cap=$5k/coin)` reproduces
  basket_sim's sum-of-cells **bit-for-bit** (|diff|=0) on the 9-coin roster → the capital model sits ON the
  proven path; "allocator off" == today's numbers.

## RESULTS (14d Kraken tape, front-of-line, $10M-tier — PROVISIONAL, structure not sizing-grade)
- **Overlooked-majors sweep** (`KRAKEN_MAJORS_SWEEP_S67.md`, agent): fee gate is a NON-ISSUE (all liquid
  majors on the 0bp-@-$10M schedule; HYPE/XPL better at −2bp). Real gate = LIQUIDITY; name ≠ Kraken depth.
- **Candidate grades (deep book ≠ edge):** **LTC = SEAT** (rev-side REV0.30, +3.33 $/hr, 86% windows) ·
  **AVAX/ADA = MARGINAL** (positive but thin/inconsistent) · **SUI = REJECT** (−2.30, 2nd-deepest book, no
  edge). Registries added: `platform.KRAKEN_CANDIDATES` (LTC) + `KRAKEN_CANDIDATES_MARGINAL` (AVAX/ADA/SUI).
- **XRP refigured (Greg was right):** −0.68 was a book-overfit CONFIG. 14d tape → **REVERSED REV0.20 =
  +2.61 $/hr** (registry was FORWARD). Applied as sim-only `GRADED_OVERRIDE` (live registry untouched).
  Re-grade of the 5 majors: BTC FWD0.10 +5.10 SEAT · ETH FWD0.13 +5.89 SEAT · SOL/XRP/DOGE MARGINAL.
- **POOL-BOUND finding:** at a FIXED $5k the 5 majors ALREADY saturate the pool (98% util) → adding coins
  DILUTES unless the pool GROWS. Backup coins buy POOL HEADROOM (capacity to deploy more), not per-$ edge.
- **Greedy full run (9 coins, $5k):** pool +5.37 $/hr (+0.107%/hr). ⚠ per-batch greedy funds THINNER coins
  during BTC/ETH idle windows and some lose on this window (no preemption; idle-vs-deploy threshold unset) —
  that's the next lever, not a finished number.

## DATA STATE
- Kraken tape on box (`realbins/<coin>_kraken_bins.json`): BTC/ETH 28d; sol/xrp/doge/ada/sui/ltc/avax 14d.
  ⚠ **Tapes are LOCAL (data-lives-local rule) and DIE on container recycle** — reproduce via
  `python backfill_kraken_trades.py --days 14 --pair {SOLUSD,XXRPZUSD,XDGUSD,ADAUSD,SUIUSD,LTCUSD,AVAXUSD}`
  (~10 min; resumable). Majors 28d also re-pullable at `--days 28`.
- `KRAKEN_MAJORS_SWEEP_S67.md` = the full agent sweep (LARGE-band candidate table + rejects).

## NEXT (S68)
1. **TUNE THE BEST $5k DEPLOYMENT** (the "best deployment" work): idle-vs-deploy threshold (don't fund thin
   coins just because majors are between legs unless their edge clears a bar), optional preemption /
   per-coin exposure cap; settle the edge-weight source (tape vs book); longer-window confirm of LTC + the
   marginal/XRP-reversed configs before any live-registry change.
2. **SMALL-CAP STRATEGY** (Greg's 3rd ask, still queued) — the ~116 THIN-OK −2bp sleeve: rebate economics,
   queue-honest fill, per-cell grade via `grade_coin_kraken`; architect S1–S3 thin-sleeve proof.
3. Later: swap per-COIN cap → per-LEG cap (`capacity.py`, the right granularity); pin capacity on the ~30h
   Kraken BOOK; wire `run_portfolio` to the paper cron; restart eligible-alt collection (thin data track).

## Files (S67)
odcore/allocator.py (NEW), odcore/platform.py (run_portfolio + KRAKEN_CANDIDATES[_MARGINAL], additive),
scripts/portfolio_sim_kraken.py (NEW), scripts/grade_coin_kraken.py (NEW), KRAKEN_MAJORS_SWEEP_S67.md,
STRATEGY_INVENTORY.md (S67 block), this handoff, KICKOFF_2026-07-07_S68.md.
