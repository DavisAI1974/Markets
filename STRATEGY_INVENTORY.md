# STRATEGY & TOOL INVENTORY — DavisAI Markets (living doc; started S64 2026-07-05)

> **WHY THIS EXISTS (Greg, S64):** we keep re-deriving from one tool and forgetting the rest of our
> own toolkit (S64: a whole benchmark got run on *bare* flow-lean, ignoring the deployed stack + the
> E300 family). This is the canonical list of EVERYTHING we have live/built so no session misses it.
> **Rule: read this at session start; update it whenever a strategy/tool/cell is added, tuned, or retired.**
> Keep it in sync with `odcore/platform.py::DEPLOYED` and the per-session handoff/kickoff.

---

## 1. DEPLOYED CELLS (`odcore/platform.py::DEPLOYED`) — the production registry
Per-cell law: each cell = asset × venue × side, validated + deployed independently.
- `DEPLOYED = [sol, doge(grace=600), xrp, eth, btc(K=10)]` — the paper/sandbox forward ledger cells.
- **Fee frame (S63 pivot): KRAKEN kr_mk0 = 0 bp maker** (needs $10M/30d volume tier; Coinbase parked).
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
### S64 open threads (see handoff/kickoff)
1. Full-stack + E300-on-lean measurement through the deployed executor (not bare lean).
2. Rebate-eligible-pair BASKET (per-coin tuned gate; ~6 confirmed: APE/RE fwd, XDC/SHX/AIOZ/ARPA rev).
3. Multi-sleeve basket simulator (majors unlock tier + eligible earn rebate + E300 sleeve; ~0-corr idle-fill).
4. Kraken live adapter (WS v2 add/amend/cancel, executions, post_only; no spot testnet → tiny-size first).
