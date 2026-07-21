# DavisAI Markets — New Session Handoff

**Date:** 2026-07-21  
**Primary review target:** Blind NG forecaster build logic  
**Repository:** `DavisAI1974/Markets`  
**Canonical branch:** `claude/kalshi-s79-kickoff-ij8t9o`

---

## 1. Purpose of this handoff

Use this document to start a fresh review of the natural-gas blind forecaster without losing the broader platform context.

The new session should:

1. Understand what DavisAI Markets is and how the live, fundamental, signal, UI, and execution layers fit together.
2. Audit the blind forecaster for leakage, reproducibility, calibration, and seasonal logic.
3. Preserve the existing signal authority instead of creating parallel or competing forecasts.
4. Keep all event-contract execution in SHADOW until venue data, settlement logic, fees, fills, and forward-live gates are complete.

---

## 2. Platform identity

DavisAI Markets is an event-driven energy trading platform centered on:

- Henry Hub natural-gas futures microstructure.
- Fundamental power-burn and physical-balance drivers.
- Kalshi and CME event-contract mispricing.
- A self-growing blind forecaster and live trading coach.

The platform is not intended to be a generic chart dashboard. Its operating sequence is:

1. Observe the underlying NYMEX Henry Hub futures market at message-level speed.
2. Detect movement onset, direction, magnitude, continuation, exhaustion, and turning points.
3. Combine live microstructure with decision-time fundamental and seasonal state.
4. Convert the expected underlying distribution into contract-specific settlement probabilities.
5. Compare fair probability with the event-contract bid/ask.
6. Trade only when the edge survives fees, fill probability, latency, executable size, exact-definition matching, and risk gates.

### Venue and brokerage context

- Kalshi is used directly.
- CME hourly and daily Henry Hub event contracts are currently SHADOW only.
- Tastytrade is the brokerage relationship for the broader trading build.
- Do not substitute IBKR assumptions.
- NYMEX NG options are a future direct trading vehicle.

No research signal grants live execution authority by itself.

---

## 3. Core architecture

### 3.1 Underlying market lane

Databento `GLBX.MDP3` for Henry Hub NG futures.

Historical state:

- Historical MBP-10 corpus already collected.
- One-year L1 historical collection is currently running separately.
- Historical jobs must not be restarted or duplicated without checking AWS/S3 first.

New live collector supports:

- MBO.
- MBP-10.
- Trades.
- TBBO.
- Definitions.
- Statistics.
- Status.

### 3.2 Fundamental lane

Merged public/free collectors now cover:

- EIA Lower-48 working gas and weekly change.
- EIA-930 hourly demand.
- EIA-930 forecast demand.
- EIA-930 net generation.
- EIA-930 interchange.
- EIA-930 generation by fuel, including natural gas, wind, solar, coal, and nuclear.
- NOAA/NWS hourly forecasts for 16 gas-demand metros.
- NOAA/NWS active alerts for major demand and Gulf-supply states.
- NRC daily unit-level reactor status, outages, derates, and returns.

### 3.3 Forecast and coach lane

Key files:

- `research/kalshi/month_characterize.py`
- `research/kalshi/forecast_harness.py`
- `research/kalshi/coach_replay.py`
- `research/kalshi/knowledge/ng_brain.json`
- `research/kalshi/NG_BEHAVIOR_KNOWLEDGE.md`
- `research/kalshi/FORECASTER_RUNBOOK_S93.md`

### 3.4 Event-contract lane

Still missing or SHADOW:

- Active CME `ECNG` and `ECH*` definitions and books.
- CME hourly settlement-window VWAP engine.
- Strike-by-strike probability model.
- Underlying-to-event repricing-lag measurement.
- CME fee, fill, executable-size, and slippage model.
- CME order routing.

---

## 4. UI work completed

A new HTMX operations desk was built around a truthful top-stack design.

### Live NG top stack

The panel shows:

- Prompt Henry Hub contract.
- Last trade.
- Bid/ask and spread.
- 10-level depth imbalance.
- MBP-10 bid and ask depth.
- Latest MBO action, side, price, and size.
- Feed latency p50/p95.
- Record age and health age.
- Session record count.
- Local archive growth.
- Reconnect count.

### Truthful authority labels

The panel explicitly displays:

- `CME EVENTS · SHADOW`
- `Dipole look-ahead · WIRING NEXT`
- `CME order routing unavailable`

The interface must never display unavailable data as live.

### Intended full top stack

Longer-term cards should include:

- NYMEX leader price and direction.
- Event-contract follower bid/ask.
- Edge clock.
- Gross edge.
- Maker, taker, and likely net edge.
- Residual edge after observed repricing.
- Pipeline latency.
- Signed flow.
- Executable size.
- Fill probability.
- Exact settlement-definition match.
- Risk gate.
- Active, armed, and shadow plays.

### AWS UI service

- HTMX desk binds to `127.0.0.1:8091`.
- Intended access is AWS SSM port forwarding.
- The service is designed to persist across logout and reboot.

---

## 5. Infrastructure work completed

Merged work includes:

- Durable live NG collector.
- systemd boot persistence.
- Automatic reconnect.
- Daily DBN rotation.
- S3 archival.
- Crash/orphan archive recovery.
- One-minute watchdog.
- Atomic health snapshot.
- One-command installer.
- HTMX desk service.
- GitHub validation workflow.
- EIA/NOAA public-data workflow.
- NRC reactor-status collector.

Important distinction:

- Code is built and merged.
- Actual AWS live runtime activation has not been independently verified from this chat.
- Historical L1 and previous MBP collections were deliberately left untouched.

---

## 6. Current data state

### Confirmed available

- Historical raw MBP-10 for NG and CL.
- One-year L1 backfill currently running.
- EIA weekly storage history.
- EIA hourly grid/load/fuel data.
- NWS hourly forecasts and alerts.
- NWS/ASOS historical observations.
- NRC trailing 365-day reactor status.
- Forward-curve regime data.
- Existing Kalshi public order-book capture.

### Built but not AWS-runtime-confirmed

- Live Databento NG MBO/MBP-10/trades/TBBO collector.
- Live HTMX NG desk.
- AWS public EIA/NOAA/NRC timer and S3 snapshot path.

### Missing or incomplete

- ECMWF IFS/AIFS open model ingest.
- NOAA GFS/GEFS model-run deltas and ensemble spread.
- Real-time behind-the-meter solar estimate.
- EIA-861M distributed-solar calibration.
- PJM/AEP behind-the-meter solar shape and capacity integration.
- Timely LNG-terminal feedgas nominations.
- Trading-day dry-gas production estimates.
- Normalized interstate-pipeline nominations.
- Public pipeline EBB maintenance normalization.
- LNG-terminal and Coast Guard status normalization.
- Institutional storage-consensus history and revisions.
- CME event-contract depth and trade history.

---

## 7. Nuclear signal state

Two nuclear sources are intentionally combined.

### EIA-930

Use for actual, capacity-weighted hourly nuclear generation.

### NRC

Use for unit-level attribution:

- Which reactor is offline.
- Which reactor is derated.
- Which unit ramped down.
- Which unit is returning.
- Day-over-day fleet shortfall direction.

Do not replace EIA with NRC or NRC with EIA.

Current NRC aggregate caveat:

- Fleet aggregate is equal-weighted by unit, not MW-weighted.
- Next enrichment should map each unit to nameplate capacity, balancing authority, and region.
- Then test whether regional nuclear shortfall is actually being replaced by gas in EIA-930.

---

## 8. Solar, daylight, and native-load logic

Key operator insight from Greg:

> Native load often drops sharply as the sun rises because behind-the-meter residential and commercial solar subtracts from what the utility can see.

The platform should distinguish:

`reported native load = gross customer demand - behind-the-meter solar ± battery activity`

EIA-930 solar mostly captures grid-visible utility solar. It does not fully capture residential and small-commercial PV.

### Desired solar stack

- Utility-scale solar actual.
- Distributed-PV installed capacity.
- Clear-sky solar geometry.
- Cloud and irradiance forecast.
- Native-load residual.
- BTM solar estimate.
- Day-ahead solar expectation.
- Solar surprise.
- Sunrise ramp.
- Evening replacement ramp.
- Gas-generation displacement.

### Daylight enrichment work

Open PR:

- PR 3: `Enrich existing NG projection with daylight load shape`
- Branch: `chatgpt/daylight-load-shape`

Design rule:

- Enrich the existing forecast authority.
- Do not create a parallel signal.

The PR adds one shared daylight module for:

- Civil dawn and civil dusk.
- Sunrise and sunset.
- Effective solar-ramp start and end.
- Weighted daylight and dark hours.
- Clear-sky solar geometry.
- Artificial-lighting geometry.
- Sunrise native-load window.
- Evening net-load ramp window.
- Summer long-day, winter long-dark, and shoulder regimes.

It feeds:

- Existing `forecast_harness.decision_state()`.
- Existing EIA/NOAA public-data snapshot.

**Current status:** PR 3 is open. Its first CI run failed during the daylight self-test. Diagnose and correct before merge.

The likely review point is the solar-event ordering or event-minute handling in `research/kalshi/daylight_load_shape.py`.

---

## 9. Natural-gas seasonal weighting

Practical EIA-based power-sector shares of total U.S. gas demand:

- Peak summer: roughly 45% to 53%.
- Cold winter: roughly 28% to 35%.
- Annual average: roughly 39% to 41%.

### Summer authority should lean more heavily on

- Grid-load surprise.
- Behind-the-meter solar ramp and surprise.
- Utility solar.
- Wind surprise.
- Nuclear outages and returns.
- Gas-fired generation.
- Heat and humidity.

### Winter authority should lean more heavily on

- Population-weighted HDD changes.
- Residential and commercial heating demand.
- Freeze-offs.
- Production.
- Pipeline constraints.
- Storage.
- Nuclear and wind shortfalls.
- Electric-heating load.
- Short-day lighting shape.

Winter and summer intraday curves should not be pooled.

---

## 10. Trade-signal inventory

Machine-readable source:

- `research/kalshi/knowledge/ng_brain.json`

### 10.1 `direction.flow_nowcast`

**Target:** direction  
**Read:** `dip_imb_level`  
**Mechanism:** signed taker buy-minus-sell flow imbalance from the pre/nascent-leg window.  
**Current call:** when `|dip_imb_level| >= 0.15`, follow its sign.  
**Evidence:** 34/34 in a limited unseen warm-season strong-flow sample.  
**Status:** PROVISIONAL.  
**Limitation:** nowcast as the leg is being born, not a from-flat prediction.

### 10.2 `direction.book_contrarian`

**Target:** direction tie-breaker  
**Read:** entry resting-book imbalance `imb_R`  
**Call:** when flow is flat, fade the heavy resting side; a wall may be fuel rather than support.  
**Status:** PROVISIONAL, lower confidence.  
**Rule:** flow dominates the book when they disagree.

### 10.3 `ride.magnitude_staircase`

**Target:** continuation and sustain  
**Read:** favorable move reached so far.

Observed continuation staircase:

- $50: 43%.
- $150: 57%.
- $250: 75%.
- $350: 92%.
- $500: 100% in the limited sample.

**Status:** STABLE within the warm-season sample.  
**Important:** use the real-time crossing event, not the final realized peak.

### 10.4 `exit.recruitment_reversal`

**Target:** turning point and exit  
**Reads:**

- `turn_far_thinning`
- `turn_aligned_push`
- `turn_exhaustion`

**Call:**

- Stay while the far-side ladder recruits liquidity ahead of price.
- Exit when recruitment stops or flips to consumed/stalled while support collapses.

**Status:** PROVISIONAL.  
**Major limitation:** currently measured entry-to-realized-peak; the running live version is not yet validated.

### 10.5 `shape.grind_vs_spike`

**Target:** sustain  
**Reads:** `fast_capture`, `peaked_fast`

**Call:**

- Slow grind tends to hold.
- Front-loaded spike tends to round-trip.

**Status:** STABLE in limited warm-season data.  
**Availability:** usable after approximately the first 60 seconds of the leg.

### 10.6 `daytype.surprise_magnitude`

**Target:** day type  
**Read:** absolute EIA storage surprise versus seasonal proxy or consensus.

**Call:**

- Larger surprise may imply a larger or trend day.
- Near-consensus may imply range or chop.

**Status:** PROVISIONAL_WEAKENED.  
**Important:** surprise sign did not reliably sort price direction.

### 10.7 `daytype.weekday_archetype`

**Target:** day type  
**Read:** weekday.

Current warm-season observations:

- Tuesday: strongest-trend weekday.
- Wednesday: US-session up lean in the small sample.
- Thursday: storage catalyst at 10:30 ET.
- Friday: range tendency; can override surprise.
- Monday: open problem due weekend-gap behavior.

**Status:** PROVISIONAL.

---

## 11. Supporting mechanisms

- Thursday EIA storage release is the main scheduled weekly catalyst.
- The US session tends to decide the daily range; overnight is often thinner drift.
- Monday can have a distinct weekend-information repricing shape.
- Summer is cooling and power-burn led.
- Winter is heating, withdrawal, freeze-off, and constraint led.
- LNG feedgas, production, and pipeline constraints are real but incompletely measured.

---

## 12. Signals currently ruled out or weak

In the limited warm-season multi-target pass, these did not provide reliable standalone lift across direction, sustain, turn, or peak:

- `aligned_imb`
- `aligned_imb_R`
- `exhaustion` by itself
- `spread_ratio`
- `pre_vol`
- coiled-volume split
- `dip_aligned_flow`
- `dip_mi_flow`
- entry bid/ask depth alone
- daily temperature regime alone
- `gw_hdd`
- `gw_cdd`
- precipitation alone
- contango-flat curve regime alone

Do not permanently discard them. Retest in:

- Winter.
- Backwardation.
- Extreme weather.
- Pipeline and LNG constraints.
- Different volatility regimes.

---

## 13. Blind forecaster — current logic

### 13.1 Current loop

1. Select approximately 12 previously untouched NG days.
2. Build a blind-safe decision-state file.
3. Give the decision state and `ng_brain.json` to an agent.
4. The agent forecasts the day archetype and cumulative-move trajectory.
5. The agent must not read the target-day tape.
6. Score forecast versus actual.
7. Distill general mechanisms and merge them into the brain.
8. Repeat across the year.
9. Judge skill on true holdout days and forward-live results.

### 13.2 Current `decision_state()` before PR 3

It supplies:

- Weekday.
- Most recent EIA storage surprise.
- Forward-curve regime.

### 13.3 Proposed enrichment in PR 3

The same state object gains:

- Civil dawn and dusk.
- Sunrise and sunset.
- Solar-ramp windows.
- Lighting-transition windows.
- 24-hour clear-sky solar geometry.
- 24-hour artificial-lighting geometry.
- Seasonal load-curve regime.

This must remain one forecast authority.

---

## 14. Blind-forecaster review questions

### 14.1 Is the blind wall truly clean?

For every feature, ask:

- Was it available at the decision timestamp?
- Is it an archived forecast known then, or reconstructed later?
- Does any historical weather field use realized data where an archived forecast was required?
- Does any release value accidentally use a later revision?
- Does the target-day tape leak into feature construction?

### 14.2 Is the model forecasting or narrating?

Determine whether the build is:

- Reproducible.
- Numerically specified.
- Scored consistently.
- Able to produce calibrated uncertainty.
- Resistant to hindsight language.
- Resistant to memorizing individual days.

### 14.3 Are winter and summer separate enough?

At minimum condition by:

- Daylight length.
- HDD/CDD regime.
- Power-burn share.
- Forward-curve regime.
- Injection versus withdrawal season.
- Weekday.
- Sunrise and evening-ramp timing.
- Nuclear, wind, and solar availability.

### 14.4 Is the output contract useful?

Recommended output fields:

- Expected direction distribution by horizon.
- Expected move-size distribution.
- Expected timing windows.
- Expected continuation versus reversal.
- Expected intraday cumulative path.
- Uncertainty bands.
- Confidence and data-quality flags.
- Explicit unknowns.

### 14.5 How should the forecaster connect to dipole?

Treat:

- From-flat forecaster as the prior.
- Dipole as a live likelihood update when flow begins.
- MBO/MBP features as continuation, exhaustion, and execution-state evidence.
- Event-contract pricing as the vehicle-specific fair-value comparison.

Do not allow the live dipole nowcast to contaminate a from-flat blind forecast evaluation.

### 14.6 How should scoring work?

Do not score only on final direction.

Score separately:

- Direction by horizon.
- Path shape.
- Timing of major move.
- Maximum favorable and adverse movement.
- Volatility and range.
- Trend versus chop.
- Calibration of uncertainty.
- Net trading value under a realistic vehicle and cost model.

---

## 15. Immediate next tasks for the new session

1. Read this handoff.
2. Read `research/kalshi/FORECASTER_RUNBOOK_S93.md`.
3. Read `research/kalshi/forecast_harness.py`.
4. Read `research/kalshi/knowledge/ng_brain.json`.
5. Audit the blind wall feature-by-feature.
6. Diagnose PR 3 CI failure before merge.
7. Propose a deterministic, reproducible forecast output contract.
8. Add calibration and proper scoring rules.
9. Separate warm-season, winter, shoulder, contango, and backwardation regimes.
10. Preserve one forecast authority and one live coach authority.

---

## 16. Non-negotiable rules

- Historical ingestion stays raw.
- No filtering or gates on the data side.
- Gates live on the trade-signal and execution side.
- No target-day tape in blind feature construction.
- No memorized-day rules in the brain.
- Per-event analysis; do not use pooling as the final verdict.
- True holdout and forward-live are the actual skill tests.
- Maker and taker economics must both be modeled.
- Fees, slippage, fill probability, and executable size must be included.
- No event-contract execution until the exact settlement definition and venue book are connected.
- Missing data must remain visibly flagged.
- No parallel daylight, solar, nuclear, or power-burn signal when the existing projection can be enriched.
- Tastytrade, not IBKR.
- Rotate exposed credentials before live use; never commit credentials.
