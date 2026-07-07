# STRATEGY & TOOL INVENTORY — DavisAI Markets (living doc; started S64 2026-07-05)

> **WHY THIS EXISTS (Greg, S64):** we keep re-deriving from one tool and forgetting the rest of our
> own toolkit (S64: a whole benchmark got run on *bare* flow-lean, ignoring the deployed stack + the
> E300 family). This is the canonical list of EVERYTHING we have live/built so no session misses it.
> **Rule: read this at session start; update it whenever a strategy/tool/cell is added, tuned, or retired.**
> Keep it in sync with `odcore/platform.py::DEPLOYED` and the per-session handoff/kickoff.

---

## ⭐ STANDING RULE (Greg, S65) — SIM = LIVE CODE + NEW PIECES (things must MATCH)
Every simulation / backtest / probe MUST run its DECISION through the LIVE code
(`odcore/platform.py::run_cell`/`run_stream` → `odcore/swing_maker.py`), never a reimplementation. A sim
only ADDS pieces the live path doesn't own yet: a data loader for a venue with no live loader, new signal
COMPOSITION, portfolio/sleeve orchestration, parameter sweeps. It does NOT rewrite the executor, fill
model, sizing, or fees. **New mechanics go INTO `odcore/` (live) FIRST, then the sim uses them** — e.g. the
S65 enticing close is `swing_maker.close_improve_bps`, threaded through `run_stream`, then used by
`basket_sim_kraken.py`. This RESTATES the standing no-rewrite-of-existing-files rule (Greg: "please make a
note to not rewrite sim code in place of our actual code"). **MAKER NUMBERS ARE FRONT-OF-LINE** by default
(`fill_model="front"` — the deployed S46 premise "have the best bid/offer"); back-of-line/`queue` is a
pessimistic REFERENCE only. WHY THIS RULE: S65 caught the basket sim using `queue`/back-of-line while live
uses `front` — the numbers didn't match. That mismatch is exactly the failure this rule prevents.

---

## ⭐ S67 IN-PROGRESS (2026-07-06, live) — THE CAPITAL MODEL (v1 built, canary PASS) + overlooked-majors sweep
> Greg's S67 landing (S66): keep the per-coin EDGE; make capacity a VARIABLE SIZE cap (not $5k/trade);
> build the shared-POOL allocator on the LIVE path. Design LOCKED (Greg): MAJORS-FIRST (5 + agent's LARGE
> candidates as ungraded seats; thin sleeve stays a parallel data track); POOL=$5k shared; capacity
> granularity = PER-COIN position cap (an explicit JUMP-OFF scaffold — swappable `caps` dict migrates to
> per-LEG later w/o touching the allocator; the cap is a SIZE scale, NEVER an inclusion gate — a thin-cap
> coin gets small size, never dropped); fee = the $10M tier treated as REAL (majors 0bp, carried as the
> per-cell maker_fee param so a pre-$10M adjustment is a value change, not a rewrite).
- **Branch reconciled** (recurring wrong-parent bug): designated `claude/davisai-s67-capital-model-0mhh4j`
  was cut from a stale S59 parent; `reset --hard` to canonical S67 tip `0e688fb`. Dropped only a superseded
  `book_collector_btc.yml`; all Kraken collectors + paper cron intact on canonical.
- **⭐ CAPITAL MODEL BUILT (v1) — 3 additive pieces, existing live path byte-untouched:**
  - `odcore/allocator.py` (NEW): `allocate(demands,caps,pool,weights,clusters,cluster_caps)` = weighted
    WATER-FILL under 3 caps in priority (per-key capacity → cluster/correlation → pool). Proportional by
    return-on-capacity so best edge-per-$ funds first when the pool binds, but NOBODY is excluded (Greg's
    rule). + `pnl_correlation`/`cluster_by_corr` (union-find) promoted from basket_sim's ad-hoc corrcoef.
    6/6 sanity tests pass (unconstrained, cap-binds-thin-not-excluded, pool-binds-weighted-proportional,
    cluster-cap, corr-cluster, equal-weight fallback).
  - `odcore/platform.py::run_portfolio` (NEW, additive — run_cell/run_stream/run_kraken_cell untouched):
    event-driven shared-pool replay OVER per-cell legs (never re-decides a trade; sim=live). Closes free
    capital before opens at each cell; a batch opening competes for REMAINING pool via `allocate`; a held
    leg isn't resized mid-hold nor preempted (realistic; v1 simplification). Leg PnL realizes on the
    notional it held: `net_bps/1e4 * alloc`. Returns `PortfolioResult` (POOL RETURN, per-coin funded%/
    realized, pool Sharpe, utilization/idle).
  - `scripts/portfolio_sim_kraken.py` (NEW sim; only adds tape I/O + cap/weight/cluster construction):
    loads realbins Kraken tape, LIVE `run_kraken_cell` → legs, `capacity.py` per-coin caps (S66 whole-hold
    + price-eligible), return-on-capacity weights, corr clusters, `run_portfolio` over $5k. Reports POOL
    RETURN vs the acknowledged-WRONG sum-@-$5k-each framing.
- **⭐ CANARY PASS (load-bearing):** `--canary` proves `run_portfolio(pool=inf, cap=$5k/coin)` reproduces
  basket_sim's sum-of-cells **bit-for-bit** (|diff|=0.00e+00; eth +5744.24 / btc +5374.06 / total
  +11118.3043) → the capital model sits ON the proven per-cell path; "allocator off" == today's numbers.
- **FIRST NUMBER (BTC+ETH Kraken tape, 677h/27.7d, front-of-line, $10M-tier 0bp — PROVISIONAL 2-coin):**
  one **$5k shared pool** capacity-capped (ETH cap ~$1.3k, BTC ~$4.0k) earns **+8.11 $/hr = +0.162%/hr**,
  pool util mean 89%/peak 100%/idle 1%, Sharpe/bucket +0.48, BTC/ETH PnL-corr just 0.10. Contrast the
  WRONG framing (sum @ $5k each = +16.4 $/hr but on $10k of capital, crediting $5k fills BTC's ~$4k book
  can't absorb). Per-$ rate nearly identical (0.162 vs 0.164 %/hr) because near-zero corr + idle capacity
  → $5k shared ≈ as efficient as $10k split (the anti-resting/diversification benefit, architect §1.5).
- **⭐ OVERLOOKED-MAJORS SWEEP DONE** (`KRAKEN_MAJORS_SWEEP_S67.md`, agent): fee gate is a NON-ISSUE (all
  liquid majors share the majors' 0bp-at-$10M schedule; HYPE/XPL better at −2bp). Real gate = LIQUIDITY,
  and name≠Kraken depth (DOT/ATOM/ARB/OP thin; MATIC/MKR no USD pair). LARGE-band candidate cells:
  HYPE·SUI·ADA·ZEC·XMR·AVAX·XLM·AAVE·LTC·NEAR·TAO·LINK·BCH·BNB·TON(+XPL). ⚠ liquidity ≠ edge (HYPE was the
  S64 NULL) — each needs a per-cell grade before it's a cell. ⚠ 0bp assumes we HOLD the $10M/30d tier.
- **⭐ FULL ROSTER RUN + CANDIDATE GRADES (S67, 14d Kraken tape):** pulled sol/xrp/doge/ada/sui/ltc/avax
  Kraken tape (`backfill_kraken_trades.py --days 14`; majors 28d already on box). New grading harness
  `scripts/grade_coin_kraken.py` = per-cell S54 gate for a NEW coin (forward-vs-reversed + circular-shift
  NULL floor + per-window sign consistency + REV sweep; LIVE run_stream, front-of-line, kr_mk0). Grades
  of the agent's 4 candidate majors (deep book ≠ edge — the per-cell law):
  **LTC=SEAT** (rev-side, REV0.30, +3.33 $/hr, 86% windows, clears floor) · **AVAX=MARGINAL** (+3.37 but
  57% windows, barely over floor) · **ADA=MARGINAL** (+1.88, BELOW its own null floor +2.41) · **SUI=REJECT**
  (−2.30, 43% windows — 2nd-deepest book, no mean-reversion edge). Registries added (additive):
  `platform.KRAKEN_CANDIDATES` (LTC) + `KRAKEN_CANDIDATES_MARGINAL` (AVAX/ADA); `portfolio_sim_kraken
  --seats {majors,graded,all}`. CANARY still PASS on the 6-cell roster.
- **⭐⭐ THE POOL-BOUND FINDING (load-bearing — reframes "backup capacity"):** at a FIXED $5k pool the 5
  majors ALREADY SATURATE it (98% util, 0% idle) → adding coins DILUTES the strong ones, LOWERING pool
  return: majors +5.98 → +LTC +5.40 → +LTC/AVAX/ADA +5.11 $/hr (backups cannibalize BTC/ETH allocation +
  XRP is a drag −0.68/hr, negative-edge on 14d tape, echoing S63 "XRP aside on tape"). Backup capacity
  pays ONLY when the POOL GROWS to match: at $10k, +LTC ADDS (+11.04 vs +10.86 majors). Per-$ return is
  ~flat 0.11%/hr until over-provisioned (all@$15k → 0.079%/hr, 73% util). **⇒ backup coins buy POOL
  HEADROOM (capacity to deploy MORE), not per-$ edge; best per-$ config is majors-only; XRP tape-grade is
  a review flag.** (⚠ 14d window, tape-proxy capacity, front-of-line — structure not sizing-grade.)
- **⭐ GREG'S REFRAME (load-bearing, end of S67):** the **$5k is the ENTIRE stack**, not per-sleeve — the
  per-coin $5k slice was always the temp tuning artifact. The job = **best deployment of ONE $5k for max
  profit/hr**. Rules: (a) **fill the best edge-per-$ coin FIRST** (greedy, not spread); (b) **never DROP a
  coin — idle costs nothing**, every coin stays seated & available, the allocator just doesn't fund it when
  its edge is negative or better coins fill the pool; (c) don't fund negative-edge (idle > a losing trade).
- **⭐ XRP REFIGURED (Greg was right):** −0.68 was a **book-overfit CONFIG**, not a bad coin. `grade_coin_kraken`
  on 14d tape: XRP wants **REVERSED, REV0.20 → +2.61 $/hr** (registry had FORWARD; that's the S63 "XRP aside/
  reversed on tape" signal; last night's +16 was the 30h book). Applied as a sim-only `GRADED_OVERRIDE`
  (live registry untouched). Re-grade of all 5 majors on 14d tape: BTC FWD0.10 +5.10 SEAT · ETH FWD0.13
  +5.89 SEAT · SOL/XRP/DOGE MARGINAL (positive with right config, below null floor on this window).
- **⭐ GREEDY ALLOCATOR built** (`allocator.allocate(mode="greedy")`, now DEFAULT; `run_portfolio(mode=)`):
  ranks seated coins by edge-per-$, fills the best to its cap first, then next, until $5k spent; **skips
  non-positive edge (idle beats a loser); never drops a coin**. `portfolio_sim_kraken --seats all --mode
  greedy` = 9 coins seated (5 majors + LTC + AVAX/ADA/SUI backups), XRP fixed. CANARY still PASS bit-for-bit.
  ⚠ **OPEN (the real "best deployment" work, next session):** per-batch greedy funds THINNER coins during
  BTC/ETH's idle windows and some lose on this 14d window (no preemption; idle-vs-deploy threshold unset) →
  pool +5.37/hr @ $5k, ~flat vs proportional. Tuning the idle-vs-deploy / preemption / per-coin exposure cap
  is the next lever. Numbers PROVISIONAL (14d tape-proxy capacity, front-of-line; not sizing-grade).
- **✅ $10M-TIER VOLUME (Greg's Q, answered):** based on the 5 majors' tape, our capacity-capped $5k pool
  trades **~$49M notional over 13.8d** (12,295 funded legs, open+close) = ~$3.5M/day → **~$106M/30d, crosses
  $10M in ~2.8 days**. The 0bp/−2bp tier is SELF-SUSTAINING once running (churn ≈ 10× the threshold even at
  $5k); the only cost is the pre-$10M RAMP (~first 3d at higher maker fee) = Greg's deferred "pre-10M" adjust.
- **⭐ NEXT (S68):** (0) **TUNE ALL 4 CANDIDATE MAJORS** (Greg — ADA/SUI/AVAX/LTC: don't accept the base grade;
  finer REV grid + eps/bail + side re-confirm via grade_coin_kraken before final seating); (1) **TUNE THE BEST
  $5k DEPLOYMENT** — idle-vs-deploy threshold (don't fund thin coins
  just because majors are between legs unless edge clears a bar), optional preemption / per-coin exposure cap,
  edge-weight source (tape vs book); confirm LTC + the marginal configs on a longer window; (2) **SMALL-CAP
  STRATEGY** (Greg's 3rd ask — the ~116 THIN-OK −2bp sleeve: rebate economics, queue-honest fill, per-cell
  grade via `grade_coin_kraken`; architect S1–S3 thin proof); (3) later: per-LEG cap swap; pin capacity on the
  Kraken BOOK; wire run_portfolio to the paper cron. Restart eligible-alt collection (thin track).

---

## ⭐ S66 IN-PROGRESS (2026-07-06, live) — the pre-capital-model gating work + the BIG small-cap data pull
> Greg's S66 reorder (load-bearing): the capital model is BLOCKED — we CANNOT build it until (a) all the
> proposed improvement tests are run per-cell on **majors AND small caps** (E300, bigline, S42 direction,
> divergence-filter, etc.), and (b) the **small-cap coins are actually figured out** (we've only ever worked
> the majors sleeve). So S66 = complete the per-cell test matrix + build out the small-cap sleeve FIRST.
- **Branch reconciled:** `claude/davisai-s66-kickoff-4kjp87` was cut from a stale S59-infra parent; reset --hard
  to canonical S65 tip `5a2b537` (the recurring wrong-parent bug). Origin matches. Dropped only a stale
  `book_collector_btc.yml` infra variant (superseded on canonical).
- **⚠ MISSING agent reads (S65):** only TWO coverage audits landed (`PIECES_TEST_execution_kraken.md`,
  `PIECES_TEST_dipole.md`). The **dipole-EXPERT deep read** and the **ARCHITECT read** never landed — TODO.
- **E300 death-selector on DOGE/XRP (Greg's directive):** RUN. Runs on Binance-vision 30d bins (`/tmp/backfill`,
  the S62 substrate) — **Binance preview:** DOGE AUC **0.685**, base +0.63 → 3piece +1.32 (**Δ+0.69**, 4/5 wk+);
  XRP AUC **0.768**, base +1.10 → 3piece +3.08 (**Δ+1.98**, 4/5 wk+). Matches S62's 0.69–0.77. Driver:
  `scripts/_s66_e300_run.py {binance|kraken}` (drives `_s62_e300_3piece` unmodified — sim=live rule). **Kraken
  re-run in progress** (waits on the XDG/XRP tape) — that is the deploy-grade number.
- **⭐ BINANCE ≠ KRAKEN for deploy (the answer to Greg's Q):** Binance is a fast SIGNAL-EXISTENCE proxy for
  MAJORS only (prices arb'd, lag-0 synchrony) — good for "does depth@300 predict death (AUC)". It is NOT the
  deploy $/hr (fee kr_mk0=0bp, fill, spread, liquidity are Kraken-specific → grade on Kraken tape). For SMALL
  CAPS Binance is useless: most eligibles (XDC/SHX/AIOZ/GWEI/NIGHT/HYPE) are **404 on Binance** and the edge is
  Kraken low-liq microstructure. **⇒ all deploy-grade tests must run on Kraken tape.**
- **⭐ DATA REALITY fixed (no 30d wait):** Kraken REST `Trades` gives HISTORICAL 30–120d NOW.
  - Majors: BTC+ETH already have **27.7d** Kraken tape on box (`realbins/{btc,eth}_kraken_bins.json`,
    2026-06-08→07-06). SOL/XRP/DOGE 30d pulling (`/tmp/ktape`, higher volume ~20–40min).
  - **Small caps are SECONDS each** (XDCUSD 30d = 34k trades = 4s) → deep history is cheap.
  - **⭐ THE ELIGIBLE UNIVERSE IS 352, NOT 6:** Kraken has **352 rebate-eligible (maker_deep = −2bp) USD alt
    pairs** (`/tmp/eligible_pairs.txt`), not the S64 shortlist of ~6. Greg: "bigger sample of them."
  - **⭐ LIQUIDITY-BANDED (Greg: "some of the small caps are actually large"; `KRAKEN_ELIGIBLE_LIQUIDITY_S66.md`,
    24h Ticker):** eligible ≠ small — the 352 span the whole range. Bands: **LARGE >$1M/24h = 5** (HYPE $8.8M
    = S64 NULL, SYN, CAP, SLX, AI → expect WEAK per S64 efficiency gradient) · **THIN-OK $10k–1M = 116** (the
    edge sweet-spot; `/tmp/thinok_pairs.txt`) · TOO-THIN <$10k = 231 (median $3,856/24h) · **DEAD $0 = ~30
    (untradeable)**. So the real target sleeve = the ~116 THIN-OK, and liquidity is a first-class gating axis
    (edge strong on thin, weak on liquid). Collect all 352 (cheap) but GATE/BUILD on THIN-OK.
  - **"RE"** = probably a TYPO in the S64 notes (Greg), not a real intended pair — drop it (REUSD exists but ignore).
- **⭐ OVERNIGHT DURABLE COLLECTION (running while Greg away):** `scripts/_s66_overnight_collect.sh` pulls all
  352 eligible alts @ **120d** Kraken tape (par=4, self-throttling), gzips + commits every 20 pairs to the orphan
  branch **`data/kraken-smallcap-tape`** (survives container recycle; resumable — skips committed pairs). Absorbs
  the SOL/XRP/DOGE majors at the end. 120d = ~17 weeks for the per-week+reversed gate (vs 5 on 30d).
- **⚠ Ambiguity to resolve (Greg):** S64 "**RE**" isn't a bare Kraken pair — candidates `RED/REKT/RENDER/REN USD`.
- **⭐ ORDER (Greg S66):** dipole-EXPERT + ARCHITECT reads DONE (`DIPOLE_EXPERT_READ_S66.md`,
  `ARCHITECT_READ_S66.md` — converged: capacity FIRST, capital model LAST, risk-axis changes). Kraken E300 DOGE/XRP
  + 5 majors DONE (AUC 0.64–0.72 venue-robust; ⚠ on the DEPRECATED 3-piece harness — not deployed-stack numbers).
- **⭐ CAPACITY BUILT + the reframe (S66 landing):** `odcore/capacity.py` (per-leg $ fill-cap, canary PASS). The
  fill-model saga (see handoff): STATIC cap = too pessimistic (−13, winners "unfillable"); PIVOT patch = LEAKAGE
  (retracted, agent caught it); **DYNAMIC following-maker** (`_s66_dynamic_fill_kraken.py`, Greg's re-quote-to-
  follow mechanic) = the honest middle (fills 100%, ETH +0.45/BTC +1.35). **GREG'S CALL: don't chase fill-quality —
  keep last night's per-coin EDGE, make capacity a VARIABLE SIZE cap, PIVOT to the capital model.** Per-coin $/hr =
  edge × capacity; the pool is SHARED ($2k/$2k/$1k across coins), capacity-capped, correlation-aware. Variable
  capacity REORDERS last night (BTC ~+5.2, XRP ~+7.4, SOL ~+2.8, ETH ~+1.8, DOGE ~+0.4 — thin books shrink hard).
- **⭐ NEXT SESSION:** (1) restart the eligible-alt collection (`_s66_overnight_collect.sh`, resumes; ⚠ in-container
  bg dies on idle); (2) **BUILD THE CAPITAL MODEL** — variable capacity + shared-pool allocator on the LIVE path
  (`odcore/allocator.py` + `platform.run_portfolio`, architect spec; sim=live); settle capacity-granularity
  (per-leg vs per-coin position) + pool size; (3) Kraken agent for **overlooked MAJORS** (LINK/ADA/AVAX/LTC — liquid
  majors beyond our 5, NOT thin eligibles); (4) re-grade eligibles + BTC/ETH with the DYNAMIC fill (static kill
  superseded) + pin on the ~30h book.

---

## 1. DEPLOYED CELLS (`odcore/platform.py::DEPLOYED`) — the production registry
Per-cell law: each cell = asset × venue × side, validated + deployed independently.
- **⭐ WE ARE ON KRAKEN (Greg). `KRAKEN` registry (S65) = the ACTIVE live stack** (`odcore/platform.py::KRAKEN`
  + `run_kraken_cell`): per-coin STACK (direction / early-arm eps / deep-bail / cover-grace / **enticing close** /
  REV), FRONT-OF-LINE fill, kr_mk0. `scripts/basket_sim_kraken.py` DECIDES through `run_kraken_cell` (sim = live
  code — S65 rule). CellConfig gained `side/rev/eps/bail/improve`. ⚠ BOOK-PROVISIONAL (one 30h window): direction
  re-adjudication (SOL/XRP/DOGE fwd) + the REV pick are NOT a live-capital decision until a 30d-tape confirm.
- `DEPLOYED = [sol, doge(grace=600), xrp, eth, btc(K=10)]` — **LEGACY Coinbase cells (venue PARKED, S63).** The
  paper_trade cron still runs these (a parked-venue ledger). **S66 open: replace the paper/live path with the
  KRAKEN registry** (needs a live Kraken book loader wired into a `run_cell`-style path + the paper cron repointed).
- **Fee frame (S63 pivot): KRAKEN kr_mk0 = 0 bp maker** (needs $10M/30d volume tier; Coinbase parked/legacy).
- `SANDBOX = []` (emptied S57 when Bybit was struck).

## 2. STRATEGY FAMILIES (we have MORE THAN ONE — do not treat lean as the only tool)

### A. Kraken flow-lean ZIGZAG — the mean-reversion RIDE  ⭐ primary
- **Signal:** `odcore/flip_detector.py` — causal taker-FLOW-lean flip detector (WFLIP=600, REV=0.1, ARM0).
  Zigzags on the taker-flow LEAN, not price (price at a turn is ~99.6% symmetric).
- **The STACK (this is a stack, not bare lean):**
  - `+ early-arm entry` (`retime_flips`, S47) — fire at first price reversal near the extreme. **~doubles it**
    (ETH bare +4.86 → +9.50; BTC +4.22 → +8.64 @ $5k, kr_mk0 paper). eps per-coin (ETH 10, BTC 5).
  - `+ deep bail` (BTC −80 / ETH −100) — FREE tail-cap (at big depth WIN%~0 = dead loss). Taker flatten.
  - `+ cover_grace` (rest cover past the turn, S48) — recovers the maker fill (ETH taker 55%→12%).
  - `+ swing floor` (coarser REV) — fill-vs-edge knob (fewer/bigger swings for real-fill deployment).
- **Per-coin verdict (`KRAKEN_DEPLOY_MAP_S63.md`):** ETH/BTC **forward** · SOL **reversed** · DOGE = fade-8h
  (different tool) · XRP = stand aside. **Per-coin window TUNING matters** (S64: SHX/AIOZ only pass at W2400).
- **Tools:** all `scripts/_s63_kraken_*.py` (20): retime, deepstop, covergrace, swingfloor, flipzz, winloss,
  makerfill, zigzag(+null), bail/widebail/flipbail/bailshort, winners/smallwinners, dipole_agent, etc.
- **DEAD levers (don't re-chase):** any entry/direction signal; flip/re-short at depth; shallow stop;
  take-profit trail; taker-entry (fee > captured edge — S64).

#### ⭐ FINAL PER-COIN CONFIG — the authoritative deployed set (reconciled S65 from CODE + docs; cite this)
> **Provenance (Greg's S65 concern — "best zigzag was the final Bybit, then per-coin fixes on Kraken; I don't
> trust we documented it right"):** the PEAK model is the deployed fine flow-lean zigzag at **NATURAL CADENCE
> (ARM0 — NO arming gates**; the S55/S56 *armed* fine-confirm variants were all killed by their own gate,
> `SESSION_HANDOFF_2026-07-03_S56.md`). On Bybit it PASSED the full S54 gate on all 5 coins (z 6.8–14.4 @ MM3
> rebate) — but Bybit's big $/hr was the **MM3 rebate volume paycheck**, not extra structure; the STRUCTURE is
> what ports. S63 carried that structure to **Kraken spot @ kr_mk0 (0bp)** with per-coin fixes below. Bybit is
> permanently banned (§6) so the config lives on Kraken now.
>
> Reconciled against BOTH the actual code constants (`scripts/_s63_kraken_*.py`: `WFLIP,REV=600,0.1`;
> `EPS`/`REVERSED`/`DEPTHS`) AND the prose (`KRAKEN_DEPLOY_MAP_S63.md`, `S63_TREND_FLIP_FINDINGS.md`,
> `SESSION_HANDOFF_2026-07-05_S64.md`). Core detector: `flip_detector.py` **WFLIP=600, REV=0.1, ARM0**, all coins.

| coin | signal | direction | early-arm eps | deep-bail | cover_grace | E300-on-ride | paper $/hr | gate |
|---|---|---|---|---|---|---|---|---|
| **ETH** | flow-lean zigzag | **forward** | **eps10** | **−100** | 300 | **DROP** (−0.41, redundant w/ deep-bail) | +9.50 | z=4.0 PASS |
| **BTC** | flow-lean zigzag (**K=10**) | **forward** | **eps5** | **−80** | 300 | **KEEP** (+0.20) | +8.64 | z=3.0 PASS |
| **SOL** | flow-lean zigzag | **REVERSED** | **none** (early-arm HURTS SOL, −0.68) | none | 300 | — | +2.33 | fwd z=−1.6 → reversed (fragile) |
| **DOGE** | **fade-8h TREND** (different tool, `_s63_kraken_fade.py`) | fade | — | — | 600 | — | +2.73 | fade p=0.016 (data-limited, 3% cov) |
| **XRP** | — nothing clears — | — | — | — | — | — | ~0 | z=0.7 → **STAND ASIDE** |

- **Fees:** kr_mk0 = 0bp maker; taker fallback ~5bp (deep-bail taker cross 11bp, flip 22bp). A 1bp maker fee is
  FATAL (kr_mk2 nets −13..−20) — the 0bp tier is the existence condition, razor-thin ~0.5bp/swing headroom.
- **Fill-mode knob (deployment vs paper):** detection **REV=0.1** = the paper edge; **swing-floor REV≈0.2 +
  cover_grace≈300** = the real-fill config (raises fill% 31%→60%; a fill-vs-edge knob). The honest-fill re-grade
  (Job 1) runs the swing-floor config, NOT bare REV=0.1.
- **⚠ S64 window-fragility flag (do NOT size off one window):** early-arm is the lift on the 30d TAPE but it
  **HURT BTC on the realbins book window** (opposite sign) — point estimates are window-fragile; confirm on a
  2nd window before sizing. Same for the E300-per-coin split (one realbins window).
- **⚠ Code-vs-deploy nuance (flagged S65):** `_s63_kraken_deepstop/bail/*.py` list `("sol", "SOLUSD", 10.0)` —
  the `10.0` is an eps used only to generate SOL's *analysis* legs; **SOL's DEPLOYED config takes NO early-arm.**
  Don't read that constant as "SOL uses eps10."
- **⭐ S65 PROVISIONAL LEAD (3 independent confirmations — basket sim + execution agent + dipole agent; ONE ~30h
  book window, NOT the tape — do NOT overturn the deploy map yet):**
  - **XRP is a clean-POSITIVE honest-fill cell** as the PLAIN base flow-lean ride (forward, NO early-arm, NO bail,
    cover_grace): +12.5 $/hr honest, fill 49%, forced-taker only 11%, win 53%, W/L 1.44. Its book fills well where
    the majors don't. The S63 "stand aside" was a 30d-TAPE direction call (z=0.7); the book-FILL picture is
    materially positive. A dipole gate does NOT help XRP — leave it un-gated. **NEXT: confirm on a 30d tape / Tardis.**
  - **The bleed on ETH/BTC/SOL is the FILL, not the signal** (`analyze_basket_kraken.py`): maker-closed legs are
    net positive/breakeven; 54–79% of ALL loss is FORCED-TAKER closes (win% 11–32% vs 49–54% maker). Fill fix
    (coarser swing-floor REV + bigger cover_grace, `_kraken_filllever.py`) mechanically lifts fill% 24→59% and
    claws ETH→~breakeven / SOL→+1.2 / BTC still −1.9 — but this LOW-EDGE window can't show the payoff (need Tardis).
  - **Dipole `divergence` as a leg-FILTER (never tried — only as a direction classifier)** lifts on 0bp-IDEAL
    (ETH 0.34→1.60/leg, SOL-rev sign-flip +1.98, opp+exh stack > opp alone) BUT on the HONEST fill it WRECKS fill%
    (the opposing-flow legs are exactly the adverse-selected worst-filling ones, S45) → net negative. Fill-idealization
    artifact; re-grade on a real-tape honest-fill window before any wire-in.
  - **Cheap coverage gaps found:** add xrp/doge to the `makerfill`/`covergrace`/`deepstop` CELLS (eth/btc/sol only);
    run S42 book-depth DIRECTION + E300 death-selector on the Kraken TAPE for XRP/DOGE (never run on Kraken).
  - **⭐ FRONT-OF-LINE vs the pessimistic bound (Greg S65 #2, `_kraken_enticing.py`):** the basket-sim "honest"
    number used `fill_model="queue" queue_frac=1.0` = BACK-of-the-best-level-queue (pessimistic). The DEPLOYED
    `run_cell` uses `fill_model="front"` = FRONT-of-line (the S46 "have the best bid/offer" premise). At front-of-line
    (queue_frac→0) EVERY cell flips positive on this window (eth +3.4 / btc +1.8 / sol +2.2 / xrp +14.0, forced-taker→0).
    So most of the ETH/BTC/SOL "bleed" was the back-of-line worst-case, not the signal.
  - **⭐ ENTICING MAKER CLOSE (Greg S65 #1 — new opt-in `swing_maker.simulate_swing_maker(close_improve_bps=)`,
    default 0 = bit-identical):** to EARN front-of-line, post a price-IMPROVED cover that CONCEDES a little half-spread
    to jump the queue → maker close instead of a taker cross. Even from the pessimistic back-of-line base, a **0.5bp
    concession converts forced-taker closes 26–47%→2–7%** and recovers ~half the bleed (eth −7.8→−3.1, sol −8.0→−3.1,
    xrp +12.5→+14.7). **Sweet spot is MINIMAL (~0.5bp)** — more concession costs more than it saves. The enticing quote
    is the mechanism that turns the back-of-line bound into the front-of-line ceiling. Re-grade on a normal-edge window.
  - **⭐ BASKET AT FRONT-OF-LINE (the corrected live-code run, `basket_sim_kraken.py` via `run_stream`):** all 4 active
    cells POSITIVE — eth +6.77 / btc +6.66 / sol +4.79 / xrp +14.02 $/hr; aggregate **+32.24/hr @ $5k each**; correlations
    near-zero (eth-btc 0.42, rest <0.22) so **portfolio Sharpe +0.674 > best single +0.629** (diversification real). The
    enticing lever adds **+0.00 at front-of-line** (nothing to convert — front-of-line already fills maker); its value is
    the back→front recovery it SECURES (+10/+17/+10/+1.5 per coin). Keep it on (free safety net; positive where needed).
  - **⭐ THE NEW BLEED = SIGNAL-LOSS, not fill** (`analyze_basket_kraken.py` at front-of-line): forced-taker collapses to
    0–1% of loss (1–2 legs); **100% of loss is now maker-close losers = wrong-direction swings** (win 52–57%, W/L 1.05–1.40).
    Deep-bail never fired (no −80/−100 leg on this calm window). So the CHEAP bleed (fill) is FIXED; the residual is the
    irreducible direction cost (direction is DEAD, closed 4 ways). Only SOL has a fatter tail (worst-10 = 33% of loss,
    W/L 1.05) — the one maybe-cheap probe left (a SOL bail was killed on tape; re-check on book), low priority.
  - **⭐ THE 2.5× LEG EXPLOSION AT FRONT-OF-LINE IS CHURN, NOT EDGE** (Greg S65; `_kraken_newlegs.py`/`_kraken_legbleed.py`):
    front-of-line fires ~2.5× more legs (eth 194→453) but ~same $/hr — the money is ONLY in the big swings (eth ≥20bp = 23
    legs = 97% of $/hr, net/leg +17bp; btc ≥10bp ~73%; xrp ≥20bp 109%); the mid legs [2,20)bp have winners ≈ losers (pure
    churn, ±25/hr gross → +6.77 net on eth). Bleed = QUICK-REVERSAL whipsaws (87–96% of loss).
    **PER-COIN REV (`_kraken_revsweep.py`, Greg's rule — cut churn ONLY where NEGATIVE):** eth/btc/sol keep 0.10 (their
    fine churn is net-POSITIVE — coarsening LOSES money, causally); **DOGE→0.30 and XRP→0.13 ADOPTED** (negative churn cut:
    doge +6.59→+9.13 win 54→63%, xrp +14.02→+16.05, portfolio Sharpe +0.810→**+0.946**). In the KRAKEN registry.
    Fewer/bigger/spaced legs also serve the capital/anti-resting rotation. front-of-line is optimistic on sub-bp legs.
  - **⭐ DIRECTION RE-ADJUDICATION employed (agent finding; `_kraken_readjudicate.py`) — FWD wins ALL 5 on the book:**
    eth +3.42 / btc +1.80 / **sol +6.51 > rev +2.17 (CONTRADICTS deployed reversed)** / **xrp +14.02 (was stand-aside)** /
    **doge +5.46 fwd flow-lean** (deployed = fade-8h). Employed in `basket_sim_kraken.py` (SOL→fwd, DOGE activated fwd, XRP
    fwd), portfolio Sharpe → +0.810 with 5 uncorrelated cells. ⚠ ONE 30h BOOK window vs the 30d-TAPE deploy map — a
    RE-ADJUDICATION, NOT an overturn; the live deploy map (SOL reversed / XRP aside) stands until a 30d-tape/Tardis confirm.
  - **⚠ CAPITAL FRAMING (Greg S65): NO aggregate-as-sum.** $5k is the TOTAL, not per-cell; the sim's "aggregate @ $Nk"
    line is the OLD wrong framing. Real portfolio = ONE $5k pool ALLOCATED across cells with an ANTI-RESTING strategy
    (route capital to whichever uncorrelated cells are live so it's never idle — majors sit ~57% idle, small caps take
    small size → need MANY cells). The $5k-shared-pool + anti-resting rebuild is the next build (not yet done).

### B. Coinbase midband entry + E300 DEATH-SELECTOR — the mid-leg rig  ⭐ SEPARATE family
- **Entry:** `odcore/entry_coinbase.py::armed_midband_flips` (S59 promoted; `COINBASE_MIDBAND` registry).
- **The edge:** at 300 s into each leg a depth classifier (`scripts/_s62_e300_3piece.py`) predicts DEATH
  (final gross ≤ −40) at **AUC 0.69–0.77 all 5 coins** → HOLD / FLATTEN / FLIP. Independently earns
  (BTC +1.29/hr). `_s63_e300_trend.py` folds the 1h-trend as flip-direction confirm.
- **NOT yet combined with family A** (S64 open): stack E300 death-cut onto the Kraken lean ride, and/or
  run E300 as a SECOND uncorrelated sleeve (edges ~uncorrelated → √N Sharpe + fills the majors' idle).

### C. Fade-the-N-hour-TREND — direction tool for trending coins
- `scripts/_s63_kraken_fade.py` / `_s63_fade.py` — pred_side = −sign(mom over W hours). DOGE-8h clears
  (p=0.016); the market mean-reverts at multi-hour horizon. Decide side at ENTRY (no flip fee).

### D. OD dipole / divergence-exhaustion (the S36 flow read)
- `odcore/info_dipole.py` — `divergence()` (aligned_flow = imb·sign(drift)), exhaustion (dipole→0.5).
  Per-cell trend-continuation-vs-FLIP detector. Feeds gates; the S36 "biggest edge" candidate.

### E. 128-dim OD FINGERPRINT tier (the S35 distinctive-winner signature)  ⚠ heavy, mostly off-container
- `odcore/fingerprint.py`, `fingerprint_predictor.py`, `dipole_predictor.py`, `od_refrag_adapter.py` —
  deterministic OD coeff decoder + centroid dual-print (match-winner MINUS match-loser). The winner-side
  path when causal flow reads are null. **Needs the E-drive discovery archives + encoder** (not in container).

### F. QuietFloor gate — book-depth relaxation
- `odcore/quiet_floor.py` — AR(1) relaxation floor on book-depth imbalance; fires only on a shock that
  breaks the floor (gate = WHEN, level sign = DIRECTION). Cuts between-trade churn.

### G. Other executors / research strategies
- `odcore/swing_accum.py` — Greg's ACCUMULATE strategy (starter + all-in-on-confirm, layered unload).
- `odcore/swing_bigline.py` — Greg's BIG-LINE (trendline ride/break, coarse-theta swing capture).

## 3. EXECUTOR & INFRA (shared)
- `odcore/swing_maker.py` — **THE one executor** (S55 "one version: live=paper=research"). Maker-at-the-turn,
  one-sided; params: `cover_grace`, `lean_exit`, `exit_spec` (price_stop/armed_dive/casc_flip), `exit_gate`,
  `fill_mode` (maker/taker), `fill_model` (front/queue-honest), `maker_fee`(neg=rebate)/`taker_fee`. Deep-bail
  = an exit_spec/taker flatten. Defaults bit-identical when arms off.
- `odcore/platform.py` — `run_cell` (deployed cells) / `run_stream` (any flip stream, same executor);
  `DEPLOYED`/`SANDBOX`/`COINBASE_MIDBAND` registries; venue is a first-class CellConfig dim.
- `odcore/incremental.py` — `RollingFlow` O(1)/tick incremental signal (the LIVE hot-path form).
- `odcore/maker_book.py` — honest queue-ahead fill model (feeds swing_maker fill_model="queue").
- `odcore/leakage.py` (`assert_no_leakage` — MANDATORY before wiring any signal), `validation.py`
  (walk-forward + real costs + circular-shift tautology null), `sizing.py` (OD-native, `size_legs`),
  `generators.py`, `stacking.py`, `quiet_registry.py`.
- **Paper/live:** `scripts/paper_trade.py` (forward ledger cron), `paper_ledger*.jsonl`.

## 4. DATA COLLECTORS
- `backfill_kraken_trades.py` (REST tape → 1s bins; pairs XBTUSD/XDGUSD; ~1req/s, hours).
- `kraken_book_collectors_durable.yml` (all 5 coins, 6h cron → `data/<coin>-kraken-book`, L2 depth).
- Coinbase: `coinbase_book_collector.py`, `coinbase_collector.py`; alt/book durable workflows.
- Materialize book: `git show origin/data/<coin>-kraken-book:<f>.jsonl.gz | gunzip`.

## 5. FEE / VENUE REALITY (S64)
- **Kraken spot maker:** starts 0.25% (25 bp) → **0.00% at $10M/30d** → negative only at $500M+ (majors).
  30d volume is **aggregate across ALL pairs** (majors count toward the tier).
- **Maker REBATE (−2 bp):** ONLY on select LOW-LIQUIDITY pairs (majors BTC/ETH/SOL/XRP/DOGE excluded),
  and only at $10M+/30d. Eligible set = detect live via AssetPairs negative-maker-tier signature; Kraken
  re-curates it ~monthly (liquidity-driven).
- **US-legal rebate venues:** effectively only Kraken's alt-pair program. Bybit/OKX out (US-ineligible).

## 6. STANDING BANS / DEAD
- ⛔ **BYBIT** — permanently banned (US-ineligible, S57). **MEXC** dead. Coinbase parked (fee frame = Kraken).
- Dead levers: entry/direction prediction (closed 4 ways); taker-entry as blanket rule; mk0 as a default basis.

---
## 7. TRIED & DEAD — do NOT re-run these (per-coin caveats noted; kept where they work)
- **Entry/direction prediction** — closed 4 ways (S62 coeff, S62 momentum, S63 fade-flip, S63 dipole agent);
  direction ~0.50 at entry AND every mid-leg time. Depth predicts DEATH (magnitude), never direction.
- **Taker-entry as a blanket rule** (S64) — taker fee (11bp/leg) > captured edge (1-7bp/leg avg). ORACLE
  (perfect winner-pick) works (+11 ETH) but no entry-time swing-SIZE predictor exists (vol AUC 0.567≈chance).
- **E300 death-cut ON the lean ride — PER-COIN, NOT global** (S64, Greg): KEEP on **BTC** (+0.20, helps even if
  marginal), DROP on **ETH** (−0.41, redundant with deep-bail there). Do NOT pool to "neutral" — per-coin law.
  ⚠ one window (realbins); confirm 2nd window before sizing. E300 ALSO runs as its own SLEEVE (family B, +1.29/hr).
- **Flip / re-short at depth** (S63) — slide spent (confirmed-short wins ~19%); bail-flat > confirmed-short > blind.
- **Shallow stop (−15), take-profit trail** (S63) — clip recoveries / fight mean-reversion + pay taker. Deep-bail only.
- **mk0 as a default fee basis** (S57) — 0bp is the $10M/30d tier, not a given. **Bybit / MEXC** — banned/dead.
- **Grading a pair on ONE lean config** (S64) — under-calls per-coin; tune the WINDOW (SHX/AIOZ need W2400).

### S64 open threads (see handoff/kickoff)
1. ✅ Full-stack + E300-on-lean measured (early-arm = the lift; E300-on-ride neutral → E300 = separate sleeve).
2. Rebate-eligible-pair BASKET (per-coin tuned gate; ~6 confirmed: APE/RE fwd, XDC/SHX/AIOZ/ARPA rev). Needs
   the full per-week+reversed re-gate on the shortlist + longer pulls on the 7-day pairs (SYN/GWEI/NIGHT/HYPE).
3. **Multi-sleeve basket simulator** (majors unlock tier + eligible earn rebate + E300 sleeve; ~0-corr idle-fill)
   — THE next build. Name it `*_kraken_*` (deployable). Run through the real executor, not bare lean.
4. Kraken live adapter (WS v2 add/amend/cancel, executions, post_only; no spot testnet → tiny-size first).

---
## 8. PIECES — exhaustive catalog (S65, Greg's anti-amnesia audit)
> Greg (S65): "go through all the handoff versions and list all the different inventory pieces. it doesn't
> matter if they say dead or killed or whatever... I'm just not 100% we haven't missed something." Every
> distinct strategy/signal/detector/gate/executor/sizing/fill-model/dipole-read/fingerprint/cross-venue
> tool/feature/research-idea ever BUILT or seriously PROPOSED (S19→S65), regardless of dead/killed/parked
> status. Sourced from all SESSION_HANDOFF_*, KICKOFF_*, *_FINDINGS/*_NOTES, CLAUDE.md deltas, code, and
> docs/DIPOLE_PAPER_S60.md. The richest "buried but reusable" reservoirs are flagged at the bottom.

### 8.1 Signals & detectors
- **Flow-lean zigzag flip detector** (`odcore/flip_detector.py`, S36→S56) — causal taker-FLOW-lean zigzag (W600/REV0.1/ARM0); zigzags on flow lean not price. **live** — core deployed; ETH/BTC fwd, SOL rev.
- **ARM0 natural-cadence fine zigzag** (`flip_detector.py`, S56) — the PEAK model; full S54 gate all 5 (z 6.8–14.4). **live**.
- **Price-reversal zigzag (1-sec)** (S36b) — enter ~5–6bp of the true turn; the TIMING half. **live** (paired w/ dipole filter).
- **Big-line / trendline ride-break** (`odcore/swing_bigline.py`, S54) — coarse-theta swing capture. **parked** — Coinbase-1-window +$1–4/hr didn't reproduce on 30d Bybit bins (per-window, not dead).
- **Two-scale zigzag (fine executes, coarse selects)** (S54→S55) — **DEAD** — v0/v1 re-entry churn (global).
- **Fade-the-N-hour-trend** (`_s63_kraken_fade.py`/`_s63_fade.py`, S62/S63) — pred_side=−sign(mom over W hrs). **live-per-coin** — DOGE-8h clears (p=0.016), SOL-4h; XRP/ETH fragile.
- **1h-trend-fade flip** (`_s63_trend_flip.py`, S62/S63) — among big losers 1h trend predicts fwd dir 0.58–0.67; flip strongest. **research**.
- **Multi-hour big-trend oracle** (S53→S54) — 100–300bp waves, fee 2–5% of swing. **research** — proved opportunity, capture open.
- **OFI momentum / fade generators** (`odcore/generators.py`) — ofi_momentum/ofi_fade/momentum5/dipole_direction. **DEAD** — all lose net-of-cost (WF −11.8%..−188%, taut z~1); kept as diagnostics.
- **Depth-imbalance next-move predictor** (`_liquidity_dive.py`, S42) — top-K depth_imb predicts SIGNED next move (OOS +0.164, 63% hit, leads +0.1s). **research** — sub-bp, a MAKER/quoting signal.
- **buy/sell mirror leave-one-out** (`_diag_flip_states.py`, S41) — 63.5% flip-state classifier. **research/diagnostic**.
- **Freight-train anatomy** (S56/S57) — worst-10 = counter-entries into violent moves; dipole `continue` rc=0.00 flags them. **DEAD as gate** — no subgroup sums negative; content in size axis.

### 8.2 Entry timing
- **Early-arm retime (`retime_flips`)** (`flip_detector.py`, S47) — fires at first price reversal near extreme; ~doubles $/hr. **live-per-coin** — eps10 ETH/eps5 BTC; HURTS SOL (−0.68) & hurt BTC on realbins (window-fragile S64).
- **Arming rule v1 (two-stage confirm)** (`_s55_armed_zigzag_probe.py`, S55) — **DEAD** — idles 98% of month, unbounded loss (global, S56).
- **v2 extreme-anchored + trailing fallback** (`_s56_armed_gate.py`, S56) — **DEAD** — 25bp first-dip = coin flip (47% win, global).
- **ARM chop-filter family (v3-ARM)** (S56) — **DEAD** — fails as a family (global).
- **Armed mid-band entry machine** (`odcore/entry_coinbase.py::armed_midband_flips`, S58→S59) — **deployed** — `COINBASE_MIDBAND` (sol mb100/xrp mb80/doge mb100; btc gated; eth absent).
- **Theta-confirm baseline entry** (S55/S57) — **DEAD as edge** — theta-late (SOL −31bp/leg gross); the baseline to beat.
- **Fine 25bp reversal confirm (the LAG cut)** (S55 R5) — theta-confirm 151bp/54min → 26bp/1min. **research** — ~250bp/leg recoverable.
- **Bounce-back / trough-sell fallback** (S53/S56) — **DEAD** — rejected S58 R5; trough-sell fine-scale-local.
- **Confirm threshold scaling with band** (S57) — **DEAD** — "+2bp as coarse confirm" listed dead.

### 8.3 Exit & loss management
- **Deep bail (BTC −80 / ETH −100)** (`_s63_kraken_deepstop/bail/widebail.py`, S63) — at big depth WIN%~0, taker-flatten caps the −150/−200 tail FREE. **live-per-coin** — ETH/BTC (SOL none).
- **Shallow bail / stop (−15)** (S63) — **DEAD global** — BLED (clips recoveries + fights mean-reversion + taker).
- **Flip / re-short at depth** (`_s63_kraken_flipbail/bailshort/flipzz.py`, S63) — **DEAD global** — slide spent, confirmed-short wins ~19%.
- **Take-profit trail / peak harvester** (S60/S63) — **DEAD global** — winners already 68–83% of peak; toll law (giveback=c·θ) → no harvester exists.
- **cover-grace** (`swing_maker.py::cover_grace`, S48) — rest cover past turn, first opposing=maker. **live** — taker→~0% all 5; flipped DOGE losing→profitable; grace map (doge 600).
- **lean_exit / lean-collapse exit (R8)** (`swing_maker.py::lean_exit`, S55) — **parked** — INERT at fine scale (flip detector IS that exit); value at coarse, never aimed.
- **exit_gate (structure-says-out / FLAT third state)** (`swing_maker.py::exit_gate`, S55) — **research** — fixes S46 non-actionable-flip-HELD mismatch.
- **Wrong-side corrector (per-cell DIAGONAL)** (S60 Piece-2) — **research-per-coin** — SOL none / BTC plain-stop / DOGE casc-flip / XRP none.
- **Plain price-stop rider (BTC)** (`btc_coinbase_mb80_plainstop`, S60/S61) — **parked/ops-blocked** — cell stays negative; ZERO gap protection → ops bar (needs exchange-side stop + staleness kill).
- **Armed dive / armed-before uw-stop** (`exit_spec=armed_dive`, S60/S61) — **DEAD-per-coin** — fails BTC th80; SOL-only until re-shown.
- **Cascade-join flip (casc_flip)** (`exit_spec=casc_flip`, S60) — **research DOGE-only** — BUY-only +1.10/hr; fails Kraken shuffle floor (venue law).
- **Harvest-into-strength rungs (B1)** (`_s53_accum_sandbox.py`, S53) — **DEAD global** — LOSES (−$0.26), caps fat winners.
- **c_x·theta retrace exit** (S61) — **DEAD** — wealth transfer (winners −65..−73 SOL).
- **3-part exit oracle (hold/flatten/flip)** (`_s62_3piece_harness.py`, S61/S62) — **research (oracle)** — +26/hr (15×), 508/508 winners kept; NO causal mid-leg signal reaches it (winners-invisible law).
- **Big-loser flip / flip pre600<−80** (`_s62_loser_flip.py`, S61) — **research** — +2.38–6.79/hr; WEEK-FRAGILE (wk4).
- **Flip-then-manage** (S61 R13f) — flatten reversed leg on adverse / ride on favorable. **proposed** — the wk4 mitigation, unbuilt.
- **Winner flip** (`_s62_winner_flip.py`, S62) — **DEAD** — winners fade DEEPER (min −429), outnumber losers 2.5:1.

### 8.4 Gates & filters
- **Dipole divergence (aligned_flow)** (`info_dipole.py::divergence`, S36) — imb·sign(drift); strong div → ~65% reversal. **research/gate** — the S36 "biggest edge" candidate.
- **Dipole exhaustion (dipole→0.5)** (`info_dipole.py`, S36) — oppose+exhaust=64% reversal. **research** — stacks w/ divergence.
- **QuietFloor gate** (`odcore/quiet_floor.py`+`IncrementalQuietGate`, S42/S44) — AR(1) book-depth relaxation; fire only on a shock breaking the floor. **research/wired** — fires 6.9% vs 100%; on the depth channel.
- **Regime master-gate (per-cell)** (`_info_dipole_regime_gate.py`, S36b) — stand-aside; rescues bleeders. **research** — PER-CELL.
- **E300 death-selector** (`_s62_e300_3piece.py`, S62) — at 300s realized DEPTH predicts DEATH (gross≤−40) AUC 0.69–0.77 all 5. **research/Family-B** — magnitude/death not direction.
- **E300-on-the-ride death-cut** (S64) — **research-per-coin** — KEEP BTC (+0.20), DROP ETH (−0.41); one window.
- **Deep-arm variant (arm −20/−30)** (`_s62_armed_trend.py`, S62) — ETH/BTC/DOGE +1.1..+1.6. **research** — one window.
- **Climax-volume gate** (S40/S47) — **DEAD as wrong-tail gate** — removes winners, halves total; real as a fillability marker (S60).
- **Adverse-excursion STOP gate** (S47) — **DEAD** — cuts winners that reverse.
- **Dipole-exhaustion wrong-tail gate (entry_gate)** (S46) — **DEAD/marginal** — anti-predictive; off by default.
- **Confirm-budget / D-class gates** (S53) — **DEAD** — confirm-budget dud (corr −0.10).
- **Death-combo anti-print (opposing+climax w/o exhausting)** (S58) — 4×-replicated worst-entry (−31..−53bp/leg). **research (anti-print)** — avoid, not a positive gate.
- **Coeff gate / loser-coeff tier** (S62) — **DEAD in-container** — ~chance at mid-band (date/regime confound).
- **"No gates" scoring rule** (Greg S53) — judge net $/hr AND legs/hr. **standing rule**.

### 8.5 Executors & platform
- **swing_maker (THE one executor)** (`odcore/swing_maker.py`, S46→S55) — one-sided maker-at-the-turn; cover_grace/lean_exit/exit_spec/exit_gate/fill_mode/fill_model/fees. **live**.
- **platform run_cell / run_stream** (`odcore/platform.py`, S55) — deployed cells / any flip stream; venue = 1st-class dim. **live**.
- **DEPLOYED/SANDBOX/COINBASE_MIDBAND registries** (S55/S56/S59) — **live** (SANDBOX emptied S57).
- **entry_coinbase** (`odcore/entry_coinbase.py`, S59) — armed mid-band + truncation-invariance leakage gate. **deployed**.
- **swing_accum** (`odcore/swing_accum.py`, S52) — accumulate (starter + all-in-on-confirm + layered unload). **research** — +$1.3–1.6/hr SOL miniature; R&D not deploy.
- **swing_bigline** (`odcore/swing_bigline.py`, S54) — **parked** (see 8.1).
- **exit_spec socket** (`swing_maker.py`, S61) — price_stop/armed_dive/casc_flip, flat/flip, wall-clock lean_w. **research**.
- **RollingFlow incremental** (`odcore/incremental.py`, S36b) — O(1)/tick, bit-faithful, 1.70µs/tick. **live** (hot-path form).
- **paper_trade forward ledger** (`scripts/paper_trade.py`, S47) — causal executor + sizing all 5 cells, deduped accruing. **live**.
- **3-piece harness** (`_s62_3piece_harness.py`, S62) — reproduces R11 (SOL +1.77/+13.93/+26.02). **research rig**.

### 8.6 Sizing
- **Two-factor conviction sizing** (`odcore/sizing.py::size_legs`, S47/S49) — QUALITY (clmx_60) × SIZE (vol_60/volat_120/runup/dive_depth). **live** — SOL +3.6σ/DOGE +3.2σ/BTC +2.2σ; XRP/ETH null. Leakage PASS.
- **Staged-commit / accumulate sizing** (`swing_accum.py`, S52/S57) — starter → all-in on confirm (maker adds). **research/validated** — confirm adds beat random 10–14σ; NO across-trade signal.
- **Dive-depth→size (|lean@pivot|)** (S40) — predicts big moves all 4 cells. **research/live** — the first swing-SIZE signal (a SIZE axis).
- **Size cap / hi_clip tightening** (S51) — **DEAD** — FALSIFIED on forward ledger; net rises to hi_clip=4.0.
- **Scale-in / netting variants** (`_scale_in_probe.py`, S51) — **DEAD** — losers soak ~2× flow (adverse selection); REVERSED control beats it.
- **Anti-martingale / probe-across-trades** (S52/S57) — **DEAD** — P(w|prev w)==P(w|prev L) all 5.
- **Taker-entry as blanket rule** (S64) — **DEAD global** — fee 11bp > edge 1–7bp/leg; no entry-time swing-size predictor (vol AUC 0.567≈chance).

### 8.7 Fill models
- **Front-of-queue (v1)** (`_capacity_model.py`, S45/S51) — best-price priority, full half-spread. **research (optimistic bound)**.
- **Queue-honest (v2)** (`_capacity_model.py`, S51) — minus best-level size ahead. **research** — mk0 4/5 ceilings NEG; −1bp flips positive.
- **maker_book honest queue-ahead** (`odcore/maker_book.py`, S43) — fill when opposing taker vol clears the queue + adverse selection. **research** — feeds `fill_model="queue"`; binding = PRICE ELIGIBILITY.
- **Price-eligibility fill fix** (`_leg_caps` price_eligible, S52) — **live (bug fix)** — all pre-S52 mk0 $/hr were artifacts.
- **1s entry-window fill bound (FILL_W)** (S50) — **live** — Greg-caught (SOL −$204→+$19/hr).
- **Honest fill (queue + repeg-to-best)** (S61 #1) — queue clears median ~8s; repeg makes grace=0 fine. **research**.
- **Fill-size binding constraint** (S56) — median fillable $137–169/leg is the cap, not the edge. **measured**.
- **Taker-share acceptance / fill-asymmetry dollars** (S60) — **proposed (ranked archive levers)**.

### 8.8 Dipole / OD reads (D1–D8 + turn anatomy)
- **D1 flow dipole (dMI/dt)** (`info_dipole.py`, S60) — **DEAD standalone** — blind (R²<0.02, opposition is construction-generated).
- **D2 algebraic ("chem") dipole** (`dipole_predictor.py`, S60) — H_a²=a+b(H_a·H_b)+c(·)². **DEAD on order-flow entropies** — no convex c>0; convexity is a D3 (coeff-space) property.
- **D3 centroid dual-projection (markets H_a/H_b)** (`dipole_predictor.py`, S25) — coeff on win/lose centroids. **research** — real per-pair (z=+9.6) but confounded; needs same-period losers.
- **D4 trading lean dipole (the deployed one)** (`flip_detector.py`, S36+) — trailing flow lean + causal zigzag. **live** — deepest record (z 6.8–14.4).
- **D5 divergence/exhaustion** (`info_dipole.py`, S36) — see 8.4. **research/gate**.
- **D6 raw-covariance dipole (solved for time)** (`odcore/leadlag.py`/`coupling_scanner.py`, S41/S60) — raw cross-cov over lag; recovers the lag. **research (rank-A)** — the lead-lag tool; entropy transforms destroy it.
- **D7 entropy-asymmetry + C ratio** (S60) — **DEAD as signal** — units bookkeeping / MI-degeneracy.
- **D8 fingerprint-space difference (dual-print / buy-sell mirror)** (S60) — see 8.9. **research** — population-relative.
- **M1 mutual-info-in-null discriminator** (`odcore/null_extract.py`, S60) — state-dependent regime coupling. **research tool**.
- **Turn anatomy — CLIMAX / coeff-flip / QUADRATIC+accel-leads-3s** (`_turn_*`, S40) — 94–99.6% symmetric; edge = ODD remainder in FLOW (5.7%) not price (0.4%). **research findings** — climax = fillability marker.
- **Absorption / spoof wall** (`_s60_absorption_wall.py`, S60) — **DEAD (decided against)** — latency killed, wall falsified; residual SOL-only maker-frame price-discovery lead.
- **Three-offices dipole framing** (S60) — one lean, three offices (entry-confirm/wrong-side/fill-moment). **standing note**.
- **Fill-office INVERSION (dive marks THIN tape)** (S60) — dive marks ~70%-one-sided tape; with-ride climax = true fillability. **finding**.
- **coupling_scanner tautology null** (`coupling_scanner.py`, S20/S41) — 5-step coupler + circular-shift (145 decoupling events). **research tool** — load-bearing null.
- **dipole_trade 15-dim coupling vector** (`dipole_trade.py`, S22) — **DEAD as basis** — collinear (eff-rank 7.82); superseded by 128-dim.
- **3 dipole flow agents (paper/dive/s61alt)** (S62) — **DEAD as death-vs-recovery** — ~chance (0.47–0.56); orthogonal but null.
- **8 dipole-paper features F1–F8** (`dipole_paper_s62.md`, S62) — F1_lean..F8_entdipole. **research** — AUC ~0.5; F5 weak ETH, F2/F7 weak BTC.

### 8.9 Fingerprint / 128-dim OD tier
- **OD coeff deterministic decoder** (`odcore/od_refrag_adapter.py`/`fingerprint.py`, S39) — prefill+refine → 128-dim unit-L2, in-container (35s). **research**.
- **Per-cell distinctive fingerprint predictor** (`fingerprint_predictor.py`, S40) — ~91% shared shape, distinctiveness = ~9% residual; buy/sell perfect mirror (−1.0). **research**.
- **Centroid dual-print (match-winner MINUS match-loser)** (S59) — **DEAD at micros tier** — clean null; narrows to the S35 ENCODER tier.
- **Onset re-anchor (per-episode)** (`_build_episode_onsets.py`, S35b) — reconstruct true onset. **research** — entry-fingerprint canary gate.
- **6 micros feature set** (S34/S35) — mean_dipole/dipole_acl1/volume_zscore/trade_present/recent_2chunk/from_onset. **research** — stored micros were LOOK-AHEAD; coeffs CLEAN.
- **cand_sp / win_onset coeff signatures** (`markets_<cell>_win_cand_sp/`, S35) — ~1,919 per-cell signatures, hist AUC 0.72–0.84. **research (archived LOCAL on E:)** — the heavy winner-side prize; not in container.
- **HEAVY OD-coeff + centroid gate** (`_markets_gate_v2.py`, S35) — memoized, AWS-scalable. **research (validated tier)**.
- **Fingerprint encoder + canary** (`_canary_fingerprint.py`, S35) — must reproduce ONSET micros from pre-entry bars. **research (gate)** — must pass before wiring.

### 8.10 Cross-venue / coupling / lead-lag
- **Cross-venue reversion** (`od_xvenue_backtest.py`, S20/S51) — Coinbase↔Bybit lag-0 cc=0.656 z=580. **DEAD as taker edge** — real (z 3.0–3.6 @10s) but per-trade edge < cost.
- **leadlag raw cross-cov-over-lag** (`odcore/leadlag.py`, S19/S41) — a leads b 75.5%, mean +0.07s. **research tool**.
- **Cross-venue lead-lag map (D6, rank A)** (S60 menu) — Binance-spot flow leads Kraken price 1–30s. **proposed** — kill if lag-0 dominates.
- **Cross-coin dive propagation (D4+D6, rank A)** (S60) — BTC/ETH dive precedes alt dives → portfolio flatten overlay. **proposed**.
- **Implied stablecoin-basis monitor (D6+D7, rank A)** (S60) — implied USDT/USD depeg early-warning. **proposed** (novel data object).
- **Cross-coin rolling correlation regime descriptor** (F2/F3, S51/S62) — rolling 400s corr vs other major. **research feature**.
- **Book-toxicity score (VPIN analogue) / lean-conditioned inventory skew** (D4+D6, rank A, S60) — **proposed**.
- **Coupling-collapse vol overlay / dipole-class throttle / algebraic convexity cell-selector / centroid drift alarm** (D-menu rank B, S60) — **proposed (lower)**.

### 8.11 Data & infra
- **backfill_kraken_trades** (`.py`, S59) — REST tape → 1s bins, paced/resumable; 30d×5 pulled. **live**.
- **kraken_book_collectors_durable** (`.yml`, all 5, S59) — 6h cron → `data/<coin>-kraken-book` L2. **live** (the FILLS truth).
- **Coinbase book/bin collectors** (S37/S44) — **live (parked venue)**.
- **Bybit book/perp collectors** (S37/S51) — **DEAD/STRUCK** (S57 ban; 2 branches await UI delete).
- **Binance-vision / bybit backfill** (`backfill_binance_spot.py`, S39/S54) — bulk dumps → 30d×5 1-sec bins ~40min. **live** (the S54 unlock).
- **build_realbins** (`scripts/build_realbins.py`, S23) — merge daily JSONL → realbins. **live**.
- **Gzip data-branch storage + rotation guardrail** (S37/S58) — fixes 100MiB cap. **live** — off-git (S3/Render) is the durable answer.
- **OD-BOOK L2 collector + dynamics-recoverer** (`research/od_book/`, S37/S43) — **DEAD (KILL S43)** — fee-floor not signal (leg-2 FAIL); DMD operator salvaged as a feature.
- **CouplingStore + 5 OD endpoints** (`backend/odcore_store.py`, S21) — **research/diagnostic** — OD is shadow, not live source.

### 8.12 Fee / venue reality (context)
- **Real fee models** (S57) — cb_entry 40/60 .. cb_top 0/6 ceiling. **standing** — mk0 = unreached tier.
- **Kraken kr_mk0 (0bp @ $10M/30d)** (S58/S59) — verified, no application, the existence condition. **live frame** — 1bp maker FATAL.
- **Kraken alt-pair maker rebate (−2bp)** (S64) — select low-liq pairs, $10M+/30d, majors excluded. **research** — only US-legal rebate path.
- **Bybit MM (−0.1..−1.25bp)** (S51/S52) — **DEAD/BANNED** (S57 US-ineligible).
- **Fee-tier > all exit code** (S60/S61) — Greg's "2 clicks". **standing note**.

### 8.13 Multi-sleeve / basket (open builds)
- **Multi-sleeve basket simulator** (`scripts/basket_sim_kraken.py`, S65) — majors book-honest + eligible/E300 sleeves flagged; correlation + portfolio Sharpe. **BUILT v1 (S65)** — full per-coin stack via real executor; provisional on the 30h low-edge book.
- **Rebate-eligible-pair basket** (S64 #2) — ~6 confirmed (APE/RE fwd; XDC/SHX/AIOZ/ARPA rev; SHX/AIOZ @W2400). **research** — needs full per-week+reversed re-gate.
- **E300 as separate uncorrelated sleeve (Family B)** (S64) — +1.29/hr BTC, fills majors' idle. **research**.
- **Kraken live adapter (WS v2)** (S64 #4) — add/amend/cancel, post_only; no spot testnet → tiny-size. **proposed**.

### 8.14 Validation / discipline infra (gate everything)
- **assert_no_leakage** (`odcore/leakage.py`, S36b) — mandatory pre-entry; catches look-ahead 40/40. **live (mandatory)**.
- **validation (walk-forward + real costs + circular-shift null)** (`odcore/validation.py`, S20) — **live** (promotion gate).
- **S54 full gate (shuffle + reversed + per-week ×5)** (S54/S56) — **live** (deep-history gate).
- **Shuffle floor** (S56) — structure-free tape earns ~$90–106/hr/coin; premium = +$7–17 above. **standing** — never cite floor as edge.
- **quiet_registry / size_legs per-cell emit** (S44/S49) — per-cell alpha/roll + deploy flag. **live**.
- **Agent-fleet playbook** (`AGENT_PLAYBOOK_PIECES.md`, S58) — leg-dump-not-tape, falsification duty, convergence=evidence. **standing method**.
- **Leg dump (entry/exit)** (`_s58_piece1_legdump.py`, S58) — causal descriptor row at the decision cell, leakage-gated. **live method**.

### ⭐ Richest "may have missed something" reservoirs (Greg's concern → the audit agents' targets)
1. **Per-coin-DEAD exit correctors kept for another coin** (§8.3) — casc_flip DOGE-only, plain-stop BTC-only, wrong-side corrector diagonal — never swept across ALL Kraken coins per-cell.
2. **Gates alive as size/fill markers but DEAD as gates** (§8.4/8.8) — climax (fillability), death-combo (anti-print), dive (thin-tape marker) — reusable in a different office.
3. **The S60 dipole-paper rank-A/B menu** (§8.10, docs/DIPOLE_PAPER_S60.md) — ~15 fully-specified but UNBUILT cross-venue/coupling proposals (cross-coin dive propagation, book-toxicity/VPIN, lean-conditioned inventory skew, stablecoin-basis).
4. **The E-drive fingerprint archives** (§8.9) — cand_sp/win_onset coeffs (AUC 0.72–0.84), the heavy winner-side path never wired (needs E: + encoder).
