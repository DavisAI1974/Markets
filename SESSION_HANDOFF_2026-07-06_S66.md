# SESSION HANDOFF — S66 (2026-07-06) — capacity built + the fill-model saga + Greg's reframe → the CAPITAL MODEL is next

Read `STRATEGY_INVENTORY.md` (S66 block) first. This session: reconciled the branch, pulled the data, ran the
agent reads, built `odcore/capacity.py`, went down (and corrected) a fill-modeling rabbit hole, and landed on
Greg's clean reframe → next session = **the capital model**.

## THE LANDING (Greg, load-bearing — start here next session)
- **Don't re-derive the fill economics. Keep last night's (S65) per-coin EDGE; make capacity a VARIABLE SIZE cap**
  (not $5k every trade); PIVOT to the CAPITAL MODEL (now the priority). Per-coin $/hr = edge-per-$ × capacity.
- **The pool is SHARED**: you won't have $5k for each coin — you spread ONE pool ($2k on one, $2k on another,
  $1k on a third), each capped at its capacity, correlation-aware. That's the allocator's job.
- Variable-capacity rescales AND REORDERS last night's numbers (conservative tape read; pin on the book):
  | coin | ~capacity | last-night @$5k | rescaled ≈ edge×cap |
  |---|---|---|---|
  | BTC | ~$3.9k | +6.66 | ~+5.2 |
  | XRP | ~$2.3k | +16.05 | ~+7.4 |
  | SOL | ~$2.3k | +6.01 | ~+2.8 |
  | ETH | ~$1.3k | +6.77 | ~+1.8 |
  | DOGE | ~$0.2k | +9.13 | ~+0.4 |
  (XRP/DOGE had huge $5k numbers but thin books → shrink hard; BTC deep book → barely moves.)
- **OPEN decisions for the capital model (Greg to steer):** (1) capacity granularity — per-LEG cap vs per-COIN
  position cap; (2) the total POOL size ($5k or other).

## WHAT WAS BUILT / FOUND
- **Branch reconciled** to canonical S65 tip `5a2b537` (was cut from a stale S59 parent; "5c5vg9" is a session
  label, not a SHA). Force-pushed; origin matches.
- **`odcore/capacity.py`** (the architect's #1) — per-leg $ fill-capacity, promotes S50/S51 `_leg_caps`; canary
  `scripts/_s66_canary_capacity.py` PASS bit-for-bit. `realized = min(desired, cap)`; flow-bound (tape) +
  queue-honest (book) + price-eligibility (S52). Deployable capital = Σ per-cell caps, not the $5k slice.
- **⚠ The fill-model saga (3 attempts — READ so it's not re-run):**
  1. STATIC limit (open-anchored, `_leg_caps`): capacity-capped majors ALL negative (ETH −13, BTC −7…) because
     it modeled a maker frozen at one price → winners "unfillable" ($15). **TOO PESSIMISTIC.**
  2. PIVOT patch (`anchor="pivot"` ±W): flipped BTC/ETH positive — but it counted PRE-flip climax the one-sided
     maker can't fill (posts only after confirm). **LEAKAGE — retracted.** (The adversarial Kraken agent caught it.)
  3. DYNAMIC following-maker (`scripts/_s66_dynamic_fill_kraken.py`, Greg's mechanic — re-quote to follow, VWAP
     entry, causal adverse-pull): fills **100%** (not $15), but VWAP dilution → **ETH +0.45 / BTC +1.35** positive,
     SOL/XRP/DOGE ~0/neg. **The honest middle**, bracketed static-cap < dynamic < uncapped. Magnitude needs the book.
  Greg's call: this fill-quality nuance is NOT worth chasing now — treat capacity as a variable SIZE cap and build
  the allocator. (`capacity.anchor="pivot"` is now CAUSAL forward-from-flip; the ±W leakage window removed.)
- **E300 death-selector on Kraken tape** (`_s66_e300_run.py`, DOGE/XRP + 5 majors): AUC 0.64–0.72 all 5, venue-
  robust (Binance transferred within 0.05). ⚠ RUNS ON THE DEPRECATED `_s62_3piece` harness (armed-midband base,
  not the deployed stack) — numbers are NOT the deployed-stack numbers; per-coin BTC/XRP are the robust E300 cells.
  `S66_E300_KRAKEN_RESULTS.md`. (We've moved away from the 3-piece — don't use it as the vehicle.)
- **Agent reads (all committed):** `DIPOLE_EXPERT_READ_S66.md` + `ARCHITECT_READ_S66.md` (converged: capital
  model LAST, gated on capacity + fee tier + correlation/tail; risk-axis changes; capacity.py first) +
  `KRAKEN_LONGLEG_AUDIT_S66.md` (long-leg/eligible-alt audit — but it used the STATIC/too-pessimistic model, so its
  "all cells negative" verdict is SUPERSEDED by the dynamic model; re-grade needed).

## DATA STATE
- **Majors 30d Kraken tape ON BOX** (`/tmp/ktape/{XBTUSD,ETHUSD,SOLUSD,XRPUSD,XDGUSD}_30d_bins.json`; BTC/ETH also
  27.7d in `realbins/`). Binance-vision 30d for BTC/ETH/DOGE/XRP in `/tmp/backfill` (E300 substrate).
- **Eligible-alt 120d Kraken tape COLLECTING** → branch `data/kraken-smallcap-tape` (fat-first, commits every 15
  pairs, resumable). `KRAKEN_ELIGIBLE_LIQUIDITY_S66.md` = 352 rebate-eligible (−2bp) USD alts banded: 5 LARGE
  (>$1M/24h), ~116 THIN-OK ($10k–1M, the edge band), 231 too-thin, ~30 dead. `/tmp/eligible_liquidity.json`,
  `/tmp/thinok_pairs.txt`.
- ⚠ **In-container background collection DIES on session idle** (the S37 durability limit) — it only advances while
  a session is active. NEXT SESSION: restart `scripts/_s66_overnight_collect.sh` (resumes from committed pairs).

## NEXT SESSION (Greg)
1. **Restart the eligible-alt collection** (`bash scripts/_s66_overnight_collect.sh &` — resumes; fat-first).
2. **⭐ BUILD THE CAPITAL MODEL** — variable per-coin capacity + shared-pool allocator on top of the LIVE path
   (`basket_sim_kraken.py` / `run_kraken_cell` — sim=live). Architect spec: `odcore/allocator.py` +
   `platform.run_portfolio` + capacity caps + cluster/correlation caps + pool cap; anti-resting rotation. Settle
   the 2 open decisions (capacity granularity, pool size) first.
3. **Kraken agent for overlooked MAJORS** (Greg's ask): sweep Kraken for LIQUID majors beyond our 5 (LINK/ADA/
   AVAX/LTC/etc.) that deserve a cell — NOT the thin eligibles (that was this session's agent).
4. Re-grade the eligible alts + BTC/ETH with the DYNAMIC fill model (the static-model kill is superseded); pin
   capacity on the ~30h Kraken book when ready.

## Files (S66): odcore/capacity.py; scripts/_s66_{canary_capacity,capacity_demo_kraken,dynamic_fill_kraken,e300_run,overnight_collect}.py;
S66_CAPACITY_FINDINGS.md, S66_E300_KRAKEN_RESULTS.md, KRAKEN_ELIGIBLE_LIQUIDITY_S66.md, KRAKEN_LONGLEG_AUDIT_S66.md,
DIPOLE_EXPERT_READ_S66.md, ARCHITECT_READ_S66.md; branch data/kraken-smallcap-tape.
