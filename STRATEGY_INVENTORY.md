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
