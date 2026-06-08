# QUOTE_SERVICE_PLAN.md

> Canonical build guide for the markets-watch **Quote Service**. Produced S26 (2026-06-08) by the architecture agent after reading BOTH the phase-2 trading platform (`claude/continue-phase-2-pipeline-UFiGY`) and the OD/dipole branch. **Follow this document before touching quote-service code.** Every path/decision/constraint is binding until Greg supersedes it in writing.

## Preamble
This fuses the **T3.1 `mm_passive` skeleton** (phase-2 branch) with the **OD/coupling/dipole layer** (OD branch). Core thesis: a quote service IS a maker/market-making capability — post resting bid/ask, capture spread minus fees, gated by regime. The platform already has the `mm_passive` skeleton + regime classifier + monitors; the OD layer adds coupling/lead-lag/decoupling/dipole. **OD signals do NOT decide whether to quote — they adjust WHERE/HOW-WIDE to quote and WHEN to pull.** This reconciles the OD findings (signals lose net-of-cost; cheaper execution is the edge lever) with the established forward-paper cells without overstating anything.

---

## 1. REUSABLE-ASSET INVENTORY (don't go in circles)

### 1A. Phase-2 trading platform (`backend/` + root, phase-2 branch)
- **`backend/forward_paper.py`** — the `mm_passive` skeleton is ALREADY complete. `CellSpec(kind="mm_passive")` exists; the 4 cells `eth_kr_eq_mm_passive`, `eth_cb_eq_mm_passive`, `btc_kr_eq_mm_passive`, `btc_cb_eq_mm_passive` are registered. `entry_price_for_cell()` distinguishes passive fill (bid for buys, ask for sells) vs aggressive; `close_paper_trade()` (~L595) has the mm_passive exit (rest on opposite side to earn spread); `vol_target_multiplier()` clips to [0.5x, 2.0x]. Cells use `notional_usd=1000`, `hold_minutes=5`. **EXTEND, do not rewrite.**
- **`backend/api_server.py`** — `SignalStore.poll_all()` already calls `_sweep_close_forward_paper_trades()` each 30s. SSE event queue (`self.event_queue`) is the channel to surface quote state. Wire: OI/CB gate checks before mm cells fire + OD decoupling as a quote-pull trigger.
- **`backend/oi_monitor.py`** — polls BN+BB perp APIs → `OI_BUILDING_LONG/SHORT`, `OI_UNWIND_*`, `OI_CLEARED`; already in `poll_all()`. Read current state to gate/widen.
- **`backend/cb_premium_monitor.py`** — peg-corrected CB vs BN-USDT premium → `CB_PREMIUM_HOT/COLD/CLEARED`; wired. Directional bias from US-institutional flow.
- **`backend/carry_analyzer.py`** — funding carry, `MIN_NET_APR=0.03`; T3.3 carry cells are ORTHOGONAL to quoting (share JSONL, not the regime gate).
- **`backend/basis_monitor.py`** — spot-perp basis → `BASIS_DIVERGENT_HOT/COLD/CLEARED`; use as a pull-quotes trigger (dislocation = inventory risk).
- **`regime_classifier.py`** — `ClassificationResult` carries `vpin`, `vpin_multiplier`, `hawkes_multiplier`, `hurst`, `hurst_label`, `cross_venue_multiplier`, `cross_asset_multiplier`, `event_multiplier`. `Regime.EQUILIBRIUM_TWO_SIDED` (61-78% of chunks at scale) is the mm_passive trigger.
- **`hawkes.py`** — univariate Hawkes η=α/β per chunk → `hawkes_multiplier` via `hawkes_eta_calibration.json`. High η on EQUILIBRIUM = the quiet regime is about to break → widen.
- **`edge_tracker.py` (`MultiHorizonEdgeTracker`)** — per (asset,venue,regime) intraday/daily/weekly/longterm STRONG/MODERATE/WEAK/NEW + STRENGTHENING/DECAYING/FLIPPING/STABLE. This IS the Adaptive-Markets "cell strength" applied to MM cells (DECAYING/FLIPPING → reduce size; STRENGTHENING → hold/increase).
- **`executor/executor.py` + `executor/risk.py`** — `LayeredRiskConfig` per (asset,venue); `RiskConfig` has regime_whitelist/min_confidence/size/stops/max_hold. Extend with `mm_max_spread_bps`, `mm_pull_on_regimes`. SSE path handles `signal` + `manual_trade_intent`; add `quote_state_change`.
- **`frontend/src/pages/PracticeFeed.jsx`** — renders open+closed practice trades, P&L by `cell_id`. Add a `source=mm`/`kind=mm_passive` filter tab. No new page.
- **`deploy/` (LAUNCH_PLAYBOOK.md §1.5)** — AWS Lightsail `market_watch`, Ubuntu 22.04, static IP `3.142.250.137`, `markets.davisai.ai`, Caddy+LE done through §1.4. Backend systemd (§1.5) is next. Quote service runs IN the same backend process.

### 1B. OD/dipole branch (`backend/odcore_store.py` + `odcore/`)
- **`backend/odcore_store.py` (`CouplingStore`)** — caches coupling matrix (pairwise lag-0 |cc| + structured-coupling verdict), lead-lag per asset (leader/lag/z vs time-slide null), `DipoleSignal` per source (a,b,c,R2,direction), `StrengthPoint` (mi_slope, chem_frac), `DecouplingEventOut` (pair,ts,cc,baseline,severity). Refresh 600s. Read `snapshot.decoupling` (quote-pull) + `snapshot.leadlag` (bias).
- **OD API endpoints** (merge into phase-2 `api_server.py`, additive): `/api/coupling_matrix`, `/api/leadlag/{asset}`, `/api/dipole_signals`, `/api/strength/{asset}/{venue}`, `/api/decoupling`.
- **`odcore/leadlag.py`** — `detect_leadlag()`/`cross_correlation()` → `LeadLagResult(lag,cc,z,leader)`. Crypto fact: CB↔Bybit-perp lag-0 cc=0.656 z=580 — **synchronous at 1s**. Use only as directional bias on multi-min holds, NOT sub-second timing.
- **`odcore/coupling_scanner.py`** — `tautology_structure_null()`/`score_pair()` (`PairScore.structure_z` = honest coupling), `detect_decoupling()`/`rolling_coupling()`. Pull quotes when structural coupling collapses.
- **`odcore/dipole_predictor.py`** — `build_centroids()` + `algebraic_dipole_over_trades()` = the validated 128-dim per-pair predictor (z=+9.6). **NOT a live quote signal yet** (no net-of-cost PnL). Classifier input only (direction → which side to widen), not whether to quote.
- **`odcore/validation.py`** — `backtest_signal()`, `walk_forward_splits()`, `random_vs_walkforward_gap()`. Every OD signal wired into a quote decision must first clear `walk_forward_splits()` with `net_return>0` after fees.
- **`odcore/sizing.py`** — `od_size_fraction()`. NOT for primary sizing (vol-target is proven/settled); reserved for a future phase after net-of-cost edge is demonstrated.

---

## 2. RECOMMENDED ARCHITECTURE

**Design decision — OD signals as gates & spread adjusters, not entry signals.** S26 establishes: (a) venues synchronous at 1s (no sub-bar lead-lag without tick data), (b) cross-venue reversion real but sub-cost, (c) the 128-dim dipole separates win/lose at z=+9.6 but net-of-cost PnL unproven. The quote service's edge is **spread capture on EQUILIBRIUM at maker-tier fees**. OD signals adjust where/how-wide to quote and when to pull — they do not gate the decision to quote.

### Component map
```
DATA (unchanged): GHA collectors -> *.json 1s bins -> api_server._bars_from_bins() -> 1-min MarketBar
REGIME/FEATURES (extended): MarketChunker(PELT) -> MarketChunkEncoder -> classify_regime() -> ClassificationResult; MultiHorizonEdgeTracker
OD LAYER (merge in): CouplingStore.refresh()@600s -> snapshot.{coupling_matrix, leadlag, dipole_signals, decoupling}
MONITORS (wired): OIMonitor / CoinbasePremiumMonitor / FundingMonitor / BasisMonitor / LiqMonitor
QUOTE GATE (NEW: backend/quote_gate.py): (ClassificationResult, ODSnapshot, monitor states) -> QuoteDecision{should_quote, spread_bps, size_mult, pull_reason, notes}
FORWARD PAPER (extended): forward_paper.CELLS mm_passive; close on time OR regime-flip OR gate pull
EXECUTOR (later): RiskConfig + mm_max_spread_bps/mm_pull_on_regimes; quote_state_change SSE
FRONTEND (minimal): PracticeFeed "MM" tab + QuoteStatus.jsx (htmx fragment, FastAPI returns HTML)
```

### Data flow (every 30s poll cycle)
1. `_bars_from_bins()` per (asset,venue). 2. chunk + encode features. 3. `classify_regime()`. 4. `MultiHorizonEdgeTracker.update()`. 5a. (600s bg) `CouplingStore.refresh()` → decoupling/leadlag/dipole. 5b. monitors update. 6. **`quote_gate.evaluate(...)` → QuoteDecision**. 7. if `should_quote` AND latest chunk EQUILIBRIUM → open mm_passive with `vol_mult = vol_target × QuoteDecision.size_mult`. 8. if `pull_reason` AND mm cell open → close + emit `quote_state_change`. 9. normal time-based sweep-close.

### Quote-gate logic (`backend/quote_gate.py`)
**Hard stops (should_quote=False):** regime≠EQUILIBRIUM_TWO_SIDED; `LIQ_BURST_*`; `BASIS_DIVERGENT_HOT/COLD`; recent (≤10min) decoupling event for this venue-pair; `event_multiplier<0.7` (FOMC/CPI); VPIN > calibrated p90.
**Spread wideners (+bps):** `OI_BUILDING_*` +2; `CB_PREMIUM_HOT/COLD` +1; low/`hawkes_multiplier<1.0` adjust; EQUILIBRIUM edge intraday DECAYING/FLIPPING +1; `cross_venue_multiplier<1.0` +2.
**Size reducers:** intraday edge WEAK/NEW ×0.75; self_trend DECAYING ×0.75; CB-BTC lead-lag z>3 ×0.5 on KR (passive on the lagging venue is info-disadvantaged).
**Size increasers:** intraday STRONG + STRENGTHENING ×1.25.
**Base spread (`VENUE_BASE_SPREAD_BPS`, policy until calibrated):** KR 12 bps (maker rebate ~-0.02%), CB 15 bps. Must cover round-trip fees.

---

## 3. BUILD SEQUENCE (each phase verified via forward paper)

**Phase 0 — Merge CouplingStore into phase-2 (1 session).** Copy `odcore_store.py` + the `odcore/` package into the phase-2 tree; import+instantiate `CouplingStore` in `SignalStore.__init__`; call `refresh()` in `poll_all()` (600s-throttled); register the 5 OD endpoints; ensure `odcore/` on `sys.path`. *Verify:* `/api/coupling_matrix` returns JSON, `/api/decoupling` returns `[]`/events, no refresh errors. *Degrades gracefully:* if `realbins/` absent on AWS, snapshot is empty (no pulls fire) — non-fatal.

**Phase 1 — `backend/quote_gate.py` (1 session).** Pure function `evaluate(...) -> QuoteDecision` (dataclass: should_quote, spread_bps, size_mult, pull_reason, notes). Inputs: regime, vpin, hawkes_multiplier, event_multiplier, cross_venue_multiplier, oi_state, cb_premium_state, basis_state, liq_state, recent_decoupling, edge_intraday_strength, edge_intraday_self_trend, leadlag_z_cb_leads_kr. Every path appends a note. *Verify:* `tests/test_quote_gate.py` — baseline→quote; LIQ_BURST→no-quote; OI_BUILDING→wider spread; DECAYING→size<1.

**Phase 2 — Wire gate into `poll_all()` (1 session).** In `_poll_one()` (≈L828) after classify+edge, if EQUILIBRIUM compute monitor states + `recent_decoupling` and call `quote_gate_evaluate(...)`, store in `self._last_quote_decision[(asset,venue)]`. Add `current_state_for()` accessors (3-5 LOC) to oi/cb_premium/basis/liq monitors. In open path, skip mm_passive cells when gate blocks; apply `vol_mult *= qd.size_mult`. In sweep-close, close open mm cells when `not qd.should_quote` with `close_reason=qd.pull_reason`. *Verify:* mm cells open at bid in EQUILIBRIUM; forced LIQ_BURST closes the open mm trade.

**Phase 3 — `quote_state_change` SSE (1 session).** Emit on decision change (should_quote flip or |Δspread|>0.5); add `GET /api/quote-status`. *Verify:* events appear on EQUILIBRIUM, vanish on regime flip.

**Phase 4 — Frontend QuoteStatus (1 session).** `frontend/src/components/QuoteStatus.jsx` subscribes to `quote_state_change`; htmx initial load via `GET /api/quote-status-fragment/{asset}/{venue}` returning an **HTML fragment** (`HTMLResponse`, not JSON), `hx-trigger="load, sse:quote_state_change[...]"`. Add MM tab to PracticeFeed. *Verify:* phone renders per asset/venue, updates within 30s of regime change.

**Phase 5 — Calibrate + validate (ongoing).** After ≥50 closed mm trades/cell: recalibrate vol-target; per-cell net P&L (mean net bps > 3 = honest bar). When a cell clears that for ≥50 trades → promote to live limit orders via `executor/`. Add `calibrate_spread.py` (reads `backend_practice_trades.jsonl` mm cells → per-cell spread/fee/net JSON → feeds `VENUE_BASE_SPREAD_BPS`).

---

## 4. KEY CONSTRAINTS & RISKS
- **4A. 1s resolution (hard):** venues synchronous (cc=0.656 z=580). No sub-bar lead-lag edge. `snapshot.leadlag` (CB leads KR ~15min on BTC) = structural bias for multi-min holds only, NOT sub-second placement. Tick data would change this; until then claim no sub-bar edge.
- **4B. Net-of-cost = the edge lever:** every OD directional signal loses vs ~3bps. Maker-rebate capture is what flips it: e.g. Kraken maker ≈ -2bps → a 5bps spread earns ~9bps gross vs ~3bps net at taker. **The rebate is the edge, not the signal.** Forward-paper uses 25bps (taker) = a conservative lower bound; mm cells will show negative paper P&L — that is simulated taker fees on a maker strategy, NOT signal failure.
- **4C. htmx/CRO frontend:** new frontend endpoints return **HTML fragments** (`HTMLResponse` + string templates), trigger reloads via `hx-trigger="sse:quote_state_change"`; no new React page (extend PracticeFeed).
- **4D. AWS deploy (§1.5 blocking):** backend systemd not yet running → no forward-paper data accrues until §1.5 done (token, VAPID keys, requirements, systemd unit). Do §1.5 before code validation.
- **4E. UNKNOWN / needs validation (don't hardcode assumptions):** mm net-of-fee P&L (AWS not up); Hawkes-η EQUILIBRIUM thresholds (calibration is directional-only); the +2bps OI widen (no empirical backing yet); dipole-direction as spread signal (wire only in Phase 5 after evidence); "CB leads KR 15min" is a structural measurement, not a confirmed edge — bias input only, don't compose into a longer chain.
- **4F. SETTLED — do not relitigate:** VPIN 1.15/0.85/0.7; basis HOT_Z=2.0/CLEAR_Z=1.0; Gate I n≥30, BH q=0.10, r²>0.05; VOL_MULT [0.5,2.0] (the 0.005 bug is fixed); carry MIN_NET_APR=0.03, max_hold=480; notional $1000; practice-default-ON + two-confirmation to live; no math jargon in user strings; registry-driven playbooks; no synthetic data; "cell strength" framing.

---

## 5. OPEN QUESTIONS FOR GREG
1. **Maker-rebate access** on Kraken/Coinbase? Determines whether paper sim uses 25bps (taker) or maker-tier fees — and the minimum spread to quote.
2. **Min spread to quote / paper fee assumption:** keep 25bps taker (mm cells will paper-lose, "real" number only seen live) or switch paper to ~5bps/leg for a realistic picture?
3. **Quote on Bybit-perp** too (tighter spread/higher volume but more adverse selection), or CB+KR spot only?
4. **Decoupling pull threshold:** pull on any `severity`, or only "severe"? Affects false-positive pulled-quotes → cumulative P&L.
5. **Live execution location:** executor on your machine w/ personal keys (friend-group model, §4) vs central AWS?
6. **Dipole integration bar:** gate wiring on "net-of-cost demonstrated in `odcore/validation.py` walk-forward", or a different bar?

---

## File reference
**Extend, don't rewrite:** `backend/forward_paper.py`, `backend/api_server.py`, `regime_classifier.py` (do NOT touch thresholds), `backend/{oi,cb_premium,basis,liq}_monitor.py` (add `current_state_for()` only), `backend/odcore_store.py` + `odcore/` (copy as-is into phase-2).
**Create new:** `backend/quote_gate.py` (Phase 1), `tests/test_quote_gate.py` (Phase 1), `frontend/src/components/QuoteStatus.jsx` (Phase 4), `calibrate_spread.py` (Phase 5).
