# ARCHITECT READ — S66 (2026-07-06): the multi-sleeve capital model + Kraken execution system, given the 116-cell THIN-OK small-cap universe

**Mandate:** an opinionated architect read of the whole system as it stands, aimed at ONE decision — how to
architect the multi-sleeve capital allocator AND the Kraken execution system now that a ~116-pair rebate-eligible
small-cap universe is in play. Wanted BEFORE building the capital model, because it changes the design.

**Method/discipline:** every claim is grounded in code (`file:line`) or a doc; measured-fact is separated from
hypothesis. Honors: per-cell law, net-of-cost, shuffle/reversed/per-week nulls, **sim = live code** (no
re-implementing executor/fill/sizing/fees), venue-in-filenames, **no aggregate-as-sum**. No heavy compute run —
this is a reasoning read over the repo.

---

## 0. THE ONE-LINE CONCLUSION (read this first)

The small-cap universe **inverts the binding constraint**. The majors-only frame is a *capital-rationing* problem
— one scarce $5k pool, cells 57% idle (`STRATEGY_INVENTORY.md` §2.A S65 block; basket_sim reports `idle%`). The
116-cell THIN-OK frame is a **capacity-and-correlation-bounded diversification** problem — the $5k pool is *surplus*
relative to what any thin book can absorb, so the allocator's job is not "route scarce capital to the best live
cell" but "spread a surplus pool across many capacity-capped, decorrelated cells while bounding correlated-flush
exposure." **The thin sleeve IS the anti-resting mechanism** the majors sleeve was missing. But every thin $/hr
number is currently **fiction**, because the executor models no per-order capacity limit (§3), and the whole thin
economics is contingent on a fee tier we do not yet hold (§4). So: **build the capacity model in `odcore/` and prove
one small thin slice honest-fill + capacity-capped + per-week BEFORE writing the capital model** — otherwise we
parameterize the wrong frame.

---

## 1. THE CENTRAL QUESTION — what the ~116 THIN-OK cells change vs a majors-only allocator

### 1.1 Position sizing on thin books — the constraint flips from POOL to BOOK CAPACITY (measured-adjacent fact)
- The executor sizes a leg's dollars as `net_bps/1e4 * CAP` with `CAP=5000` flat (`basket_sim_kraken.py:45,133`),
  optionally scaled by `size_legs` which clips the multiplier to **[0.25, 4.0]** (`swing_maker.py:477,513`) — so a
  single leg can demand **up to $20k** of fill. On a THIN-OK book that is absurd: THIN-OK = $10k–1M/24h
  (`KRAKEN_ELIGIBLE_LIQUIDITY_S66.md:7`); the *median* THIN-OK pair is ~$50k/24h ≈ **$2,000/hr of two-sided
  notional**. A $5k slice is ~2.5 hours of the entire book's volume. Even a $200 slice is material.
- **The fill models do NOT cap by our order size.** `front` = `_next_positive` fills us on "the next REAL opposing
  trade" *of any size* (`swing_maker.py:84-94`); `queue` = `_queue_fill_index` waits until cumulative opposing
  volume clears the best-level queue ahead (`swing_maker.py:97-110`) but then **still books a full fill** — neither
  model limits our realized fill to the available/opposing size, and neither models market impact. So on thin books
  the executor reports a full $5k(×size) fill that could never happen. S56 already measured this on Bybit majors —
  *"binding constraint = FILL SIZE (median fillable $137–169/leg), not the edge"* (`STRATEGY_INVENTORY.md` §8.7 line
  368; CLAUDE.md S56 line 76). On Kraken thin alts the fillable/leg will be far smaller.
- **Consequence:** per-cell size must be capped at a measured *book capacity* (a rolling function of opposing-trade
  size / best-level depth), and the $5k pool is **over-provisioned** for any single thin cell. This is the single
  biggest architectural change and the single biggest missing live mechanic (§3, §4).

### 1.2 Fill realism — the front-of-line premise is weaker on thin, grade QUEUE-HONEST by default
- The deployed premise is `fill_model="front"` = "have the best bid/offer" (`platform.py:141`,
  `STRATEGY_INVENTORY.md` S65 rule lines 19-22). On majors, front-of-line is *earned* by the enticing close
  (`swing_maker.py:430-447`, ~0.5bp concession). On a THIN-OK book the spread is wide and intermittent; you may
  genuinely be alone at the top of book (front-of-line easy) OR you may sit behind a thin spoofy wall and only fill
  when informed flow runs you over — the S45 adverse-selection lesson, re-confirmed honest-fill in
  `PIECES_TEST_dipole.md` §2c ("opposing-flow legs are exactly the adverse-selected worst-filling ones"). The two
  cases are opposite and unknown per-pair. **Architecture decision: grade thin cells on the queue-honest fill
  (`fill_model="queue"`, `swing_maker.py:97-110,234-239`), not front** — front is optimistic and must be *earned*,
  and on a wide thin spread the enticing concession is a larger fraction of the capture. Front stays the majors
  premise; thin defaults pessimistic.

### 1.3 Rebate economics — the −2bp changes per-leg net, but the whole edge is tier-contingent (precondition, not a fact)
- Thin eligible pairs earn maker **−2bp REBATE** (both legs maker ⇒ +4bp/round-trip), on top of the wide-spread
  mean-reversion capture — vs majors at kr_mk0 **0bp** (`STRATEGY_INVENTORY.md` §5 lines 240-243; CellConfig
  `maker_fee` default 0, `swing_maker.py` treats negative fee as rebate `:129`). The rebate is *per-leg regardless of
  $ size*, so on small thin legs it is a fixed floor — this is exactly why the S64 efficiency gradient says the edge
  should live in the thin band (liquid=weak, HYPE $8.8M=null; `KRAKEN_ELIGIBLE_LIQUIDITY_S66.md:2-5`).
- **HARD PRECONDITION (load-bearing):** BOTH the 0bp tier AND the −2bp rebate require **$10M/30d aggregate volume**,
  which we do **not** hold today, and the eligible list is Kraken-re-curated ~monthly (`STRATEGY_INVENTORY.md` §5
  lines 240-243, §2.A fee note line 122: *"1bp maker is FATAL — kr_mk2 nets −13..−20"*). If the tier is not held,
  thin caps pay up to 25bp maker = instantly dead. The good news is the tier is a **turnover** condition, not a
  capital one: high-cadence small-size churn hits $10M/30d easily (400 legs/hr × $200 × 24 × 30 ≈ $57M), so the
  thin sleeve's own churn *helps* unlock the tier — **but only realized fills count** (§1.1), so this is
  circular until capacity is modeled. **This is a Greg/ops precondition to confirm before sizing anything.**

### 1.4 Correlation structure — √N BREAKS across 116 alts; measure PnL-bucket corr + tail co-movement
- The majors basket found near-zero *PnL* correlation (`basket_sim_kraken.py:192-202`; portfolio Sharpe +0.810→
  +0.946 > best single, `STRATEGY_INVENTORY.md` S65 lines 163-176) *despite* BTC/ETH return corr being high —
  because a market-making mean-reversion PnL stream is not the coin's return stream. That is encouraging but it will
  **NOT extrapolate to √116**: the alts share a common crypto-beta factor plus meme/narrative clusters, and the real
  risk is **correlated fill-failure / correlated bail in a market-wide flush** (every thin cell adverse-selected at
  once, every deep-bail firing together). So: (a) diversification benefit is far below √N; (b) the allocator must
  **measure PnL-bucket correlation on realized legs** (reuse `np.corrcoef` over hourly buckets, `basket_sim:192`)
  AND a **tail/crisis co-movement** estimate, then **cluster-cap** exposure — never assume independence.

### 1.5 Anti-resting rotation across many intermittent cells — the logic INVERTS
- Majors sit ~57% idle (`STRATEGY_INVENTORY.md` §2.A line 185). Many THIN-OK cells are *intermittent* — a THIN-OK
  pair with ~300 trades/24h (`KRAKEN_ELIGIBLE_LIQUIDITY_S66.md`, dozens of rows in that range) is ~12 opposing
  prints/hr = one fill opportunity every ~5 min. You cannot "rotate the $5k to the one live cell"; you must **quote
  on the whole eligible-and-live roster simultaneously, each capped small**, and the pool self-absorbs because at
  any instant only a fraction have an open leg. With per-cell cap ~$100–500 you need **~10–50 simultaneously-active
  thin cells to soak a $5k pool** — which is precisely how the thin universe fills the majors' idle. The pool binds
  only in a *correlated burst* (many cells fire at once), which is the §1.4 tail risk. So the pool should be sized to
  the expected *simultaneous-open* notional, not the sum of caps.

---

## 2. THE RIGHT ARCHITECTURE for the multi-sleeve allocator

### 2.1 The three sleeves are NOT three equal capital buckets
- **Majors sleeve (5 cells, lean stack):** high per-cell capacity, ~0 mutual PnL corr, proven structure, **anchors
  the fee-tier turnover**. The `KRAKEN` registry as-is (`platform.py:110-116`).
- **THIN-OK sleeve (~116 cells, rebate harvester):** low per-cell capacity, high count, **the anti-resting filler**
  and the rebate engine. Does not exist yet — must be built (§5).
- **E300 death-selector (family B):** architecturally **NOT a capital sleeve** — it is a per-cell *overlay*
  (death-cut exit / mid-band entry), an uncorrelated *signal* that composes onto a cell via the `exit_spec`/gate
  sockets (`swing_maker.py:146-164,302-345`) or as its own `COINBASE_MIDBAND`-style cells. In the pool it is an
  overlay on existing legs, not a separate allocation. Treat it as such — do not give it a capital bucket.

### 2.2 The allocation/rotation mechanism (decisive spec)
A per-step allocator over the set of *live* cells that respects THREE caps, in priority order:
1. **Per-cell capacity cap** `cap_i` (from the new capacity model, §3) — hard: realized notional ≤ `cap_i`.
2. **Cluster cap** — group cells by measured PnL-corr cluster; cap total open notional per cluster so a
   correlated flush cannot draw the whole pool.
3. **Pool cap** — Σ open notional ≤ $5k (the shared pool; this is the ONLY place the "$5k" enters — never as a
   per-cell slice, honoring no-aggregate-as-sum).
Within those caps, weight by **realized edge per $ of capacity** (walk-forward $/hr per deployed $, i.e. return on
capacity, from the per-cell forward ledger) — majors first (proven, high-capacity), thin caps as the diversifying
fillers. Anti-resting = at each step the pool flows to whichever live cells still have open capacity headroom.

### 2.3 Where the new mechanics live (sim = live code)
The **decisions** (capacity cap, allocation weights, cluster caps) are decisions → they go in `odcore/` and the sim
consumes them. Only data-I/O and the replay harness live in the sim.
- **`odcore/capacity.py` (NEW, build FIRST):** `fillable_notional(book_arrays, side, cell) -> usd_cap` from a
  rolling function of opposing-trade size / best-level depth; the executor books realized fill = `min(desired,
  cap)`. This is the missing live mechanic — without it every thin number is a phantom (§1.1, §3). Cleanest seam:
  compute per-leg realized-notional here, consumed by both `run_cell` (live) and the sim, so PnL scales by
  `realized/desired` uniformly.
- **`odcore/allocator.py` (NEW):** `allocate(live_cells, caps, corr, pool) -> {cell: notional}` implementing §2.2.
  Portfolio orchestration is explicitly an allowed "new piece," but per Greg's rule the *mechanic* goes into odcore,
  not the sim.
- **`odcore/platform.py` (EXTEND):** add `run_portfolio(cells, pool, ...)` composing the allocator + per-cell
  `run_stream`; extend `CellConfig` with `sleeve: str`, `capacity_usd` (or a capacity spec), and set thin cells'
  `maker_fee=-2.0`. Add a `THINOK` registry built programmatically from `/tmp/thinok_pairs.txt` (mirrors the
  `KRAKEN` list, `platform.py:110`). Correlation estimation = promote `basket_sim`'s `np.corrcoef` (`:192`) into an
  odcore helper the allocator calls.
- **`scripts/portfolio_sim_kraken.py` (NEW, or extend `basket_sim_kraken.py`):** the ONLY new sim responsibilities —
  the **multi-pair Kraken book/tape loader** (venue I/O the live path lacks, exactly as `basket_sim.load_book`
  already is, `:68-101`), roster/sleeve metadata, and the **replay of `run_portfolio` over the 120d tape**. It must
  report the **pool return** (Σ capacity-capped realized PnL / pool / hours), NOT the `aggregate $/hr (sum @ $5k
  each)` line — which the code itself already flags as wrong framing (`basket_sim_kraken.py:203-204`).

---

## 3. CAPACITY & ECONOMICS REALITY-CHECK

### 3.1 The binding constraint is per-cell BOOK CAPACITY, not the $5k pool (on thin)
- Deployable capital ≈ Σ (per-cell capacity) over *simultaneously-live* cells. With cap ~$100–500 and ~20–40 thin
  cells live at once, simultaneous open notional ≈ $2k–20k — so **$5k is roughly the right pool size** for 5 majors
  + a few dozen thin cells. To deploy materially more you add *cells*, not $/cell (you are capacity-bound, not
  capital-bound). **This is the answer to "is the $5k the binding constraint" — no, per-cell book capacity is**
  (on thin; the pool binds only in a correlated flush, §1.4).

### 3.2 The $/hr ceiling — order-of-magnitude HYPOTHESIS, not a fact
- Rough thin-cell arithmetic (hypothesis): 200 legs/day × +2bp net (−2bp rebate + a small wide-spread capture, net
  of adverse-sel) × $200/leg ≈ $8/day ≈ **$0.33/hr per cell**; ×116 ≈ **~$38/hr** — the same order as the 5-major
  front-of-line **+32.24/hr** (`STRATEGY_INVENTORY.md` S65 line 163). So the thin sleeve could roughly *double* the
  ceiling AND fill the majors' idle. **But every bp of that is at risk** to adverse selection, fill-failure, and the
  tier precondition — it is a number to *earn*, not to bank.

### 3.3 Does the rebate clear the adverse-selection cost?
- The S64 problem statement — *"0.5–1bp gross < 0.8bp adverse-sel"* — was on the **liquid** band. On thin, gross
  capture per swing is *larger* (wide spread + real mean-reversion) and the −2bp rebate is a per-leg floor, so the
  arithmetic is structurally friendlier — **that is the whole efficiency-gradient thesis**
  (`KRAKEN_ELIGIBLE_LIQUIDITY_S66.md:2-5`). BUT: (a) thin books have *worse* fill rates and *worse* per-fill adverse
  selection (`PIECES_TEST_dipole.md` §2c); (b) the "thin=strong" evidence so far is **one window, per-coin**
  (SHX/AIOZ pass only at W2400 — `STRATEGY_INVENTORY.md` §2.A line 95, S64 open thread #2), not a validated
  cross-section. **Verdict: plausible, unproven. It must be graded honest-fill (queue) + capacity-capped + per-week
  + reversed + shuffle before it is a number.** The rebate improves the odds; it does not guarantee the clear.

---

## 4. LOAD-BEARING RISKS, GAPS & PRECONDITIONS (what must be TRUE before live capital)

**Gaps in the code as it stands:**
1. **No capacity model** (`swing_maker.py` fill models cap by nothing / by best-level queue, never by our order size
   or impact — `:84-110`). *The single most important gap.* A thin backtest through `run_stream` today reports
   full $5k×size fills = phantom edge. **Build `odcore/capacity.py` first.**
2. **No allocator / shared-pool orchestration** — `run_cell`/`run_stream` are per-cell; there is no `run_portfolio`
   and no pool constraint. The `aggregate @ $Nk` line is the acknowledged-wrong framing (`basket_sim:203`).
3. **No correlation-cluster machinery in odcore** — only an ad-hoc `corrcoef` in the sim (`:192`).
4. **Fee/rebate is a per-cell constant, tier held by assumption** — no check that $10M/30d is actually met, no
   handling of monthly eligibility churn.

**Preconditions (must be validated, per project discipline):**
- Fee tier + −2bp eligibility **actually held** (Greg/ops; §1.3). Without it thin = dead.
- Per-cell thin edge is **net-positive on the queue-honest fill, capacity-capped, per-week (S54 gate: shuffle +
  reversed + per-week ×N), leakage-gated** (`assert_no_leakage` mandatory, `STRATEGY_INVENTORY.md` §8.14). The 120d
  tape now collecting (`SESSION_HANDOFF_S66.md`; ~17 weeks) is exactly right for the per-week gate.
- Correlation structure **measured**, not assumed (§1.4); cluster caps set from data.
- **Direction stays DEAD** — the thin edge, like majors, is fill-capture + rebate mean-reversion, not direction
  (closed 4 ways, CLAUDE.md S63 line 22). Do not re-hunt direction on 116 new coins.
- Every book-window number (S65/S66) is **one ~30h low-edge window — never sizing-grade** (`PIECES_TEST_*` §DATA
  REALITY; `basket_sim` docstring lines 21-24).

**The smallest end-to-end slice that proves the thin sleeve is real:**
Pick **~5–10 THIN-OK pairs spanning the band** (e.g. XPL/NES/NIGHT $600k–800k, SHX/XDC/REUSD/GWEI ~$130–200k, plus a
couple near $10–50k), run the **LIVE `run_stream` flow-lean stack** on their 120d Kraken tape with: (a) the new
capacity cap, (b) `fill_model="queue"`, (c) `maker_fee=-2.0`, (d) the full S54 gate per-week/reversed/shuffle, (e)
leakage PASS. **Gate: a majority clear net-positive honest-fill, capacity-capped, per-week, with reversed below the
shuffle floor.** If they don't, the thin sleeve is not real and the capital model waits. That proof is the
prerequisite for the allocator — not the allocator.

---

## 5. BUILD SEQUENCE for S66+ (with the gate at each step)

**SETTLE-BEFORE-CAPITAL-MODEL (these change the frame; do them first):**
- **S0 — `odcore/capacity.py`** (the missing live mechanic). Per-cell fillable-notional from the book; executor
  books `min(desired, cap)`. *Gate: capacity-capped majors reproduce the S65 basket within the capped size; the
  pool-bound vs capacity-bound question is now answered with real fills.* **Without this, stop — every downstream
  thin number is fiction.**
- **S0b — grading defaults.** Thin cells grade `fill_model="queue"` + `maker_fee=-2.0`. *Gate: documented, canaried
  bit-identical when off (defaults preserve the Coinbase/majors path, per `platform.py:69,106`).*
- **S0c — confirm the fee-tier / −2bp precondition** (Greg/ops). *Gate: tier held (or a plan to hold it via majors
  turnover) — else the thin sleeve is on hold and the capital model is majors-only.*

**BUILD THE THIN SLEEVE (per-cell law):**
- **S1 — multi-pair loader** for `data/kraken-smallcap-tape` (sim I/O only). *Gate: loads, aligns, overlaps N pairs.*
- **S2 — the small-slice proof** (§4, 5–10 pairs, live stack + capacity + queue + rebate + full gate + leakage).
  *Gate: majority net-positive honest-fill per-week + reversed-below-shuffle. FAIL ⇒ thin sleeve not real; halt.*
- **S3 — full THIN-OK cross-section**, per-cell S54 gate; produce the per-cell deploy map (edge per $ of capacity,
  capacity cap, corr cluster). *Gate: the surviving subset (keep where it works; partial coverage ≠ failure).*

**BUILD THE ALLOCATOR (only after S2/S3 pass):**
- **S4 — `odcore/allocator.py` + `platform.run_portfolio`** (§2.2: capacity + cluster + pool caps, anti-resting),
  correlation estimator in odcore. Replay in `scripts/portfolio_sim_kraken.py` over the 120d tape, deciding through
  odcore. *Gate: pool never exceeded; portfolio net-positive on POOL RETURN (not sum); drawdown in correlated
  flushes acceptable.*
- **S5 — write the capital model precisely** — now just parameterizing the validated allocator (pool size, cluster
  budgets, edge-weighting). *This is where the original task lands — deliberately LAST.*
- **S6 — fold in majors + E300 + live wiring:** majors as the anchor sleeve, E300 as a per-cell overlay (not a
  bucket, §2.1); wire the live Kraken book loader into a `run_cell` path and repoint the paper cron off the parked
  Coinbase ledger (`SESSION_HANDOFF_S65.md` NEXT #3).

**What must be settled BEFORE the capital model is written (so we don't build on the wrong frame):**
1. Capacity model exists → the pool-bound-vs-capacity-bound question is answered (it is capacity-bound on thin).
2. The thin edge is real net of rebate + adverse-sel on the honest fill (S2 proof).
3. Correlation structure is measured (√N is dead; cluster caps come from data).
4. The fee tier / −2bp is held (precondition).
5. Direction stays dead; the edge is fill-capture + rebate only.

---

## Appendix — key code seams (for the implementers)
- `CellConfig` (`platform.py:52-87`): add `sleeve`, `capacity_usd`/spec; thin cells `maker_fee=-2.0`, grade
  `fill_model="queue"`. Defaults must stay bit-identical (the `DEPLOYED`/Coinbase path, `:90`).
- Fill models (`swing_maker.py:84-110,234-239`): capacity capping wraps the realized fill — do NOT rewrite these;
  apply `min(desired, cap)` at the leg-$ layer consumed by both `run_cell` and the sim.
- Sizing (`sizing.py`, `swing_maker.size_legs:476-517`): the [0.25,4.0] multiplier must be *bounded by* the capacity
  cap, or a high-conviction thin leg demands 4× a book it cannot fill.
- Portfolio math (`basket_sim_kraken.py:189-204`): replace the `aggregate (sum @ $5k each)` with the pool-return
  number; keep the `corrcoef`/Sharpe/`idle%` machinery (promote corr into odcore for the allocator).
