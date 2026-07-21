# Databento platform research ledger

Status: ACTIVE research track
Branch: `chatgpt/ng-forecaster-s103-audit`
Purpose: extract high-value Databento mechanics that materially improve DavisAI Markets without creating a parallel signal architecture.

## Operating rule

Every finding must map to:

1. an existing DavisAI component;
2. a concrete implementation or test;
3. an authority level (`RAW`, `FEATURE`, `SHADOW`, `FORECAST`, `EXECUTION_GATE`);
4. a validation plan on historical and/or forward-live data.

Interesting retired signals may enter the retest registry, but never regain authority from documentation alone.

## Priority source set

- `databento/databento-python`
- `databento/dbn`
- official Databento docs and examples
- official venue/dataset supplements for `GLBX.MDP3`
- official queue-position, order-book, latency, markout, replay, symbology, and continuous-contract examples

## Findings already promoted to implementation work

### 1. MBO resting-book state

Databento actions:

- `A` Add inserts an order.
- `M` Modify changes price and/or size.
- `C` Cancel fully or partially removes resting size.
- `R` Clear removes all resting orders for an instrument.
- `T` Trade, `F` Fill, and `N` None do not update resting state.

DavisAI impact:

- `research/kalshi/ng_live_operator.py`
- queue recruitment/removal must exclude Trade and Fill to avoid double counting.
- exact order state and hypothetical new-order queue-ahead can be derived from MBO.

Authority: `SHADOW` until NG-specific fill/queue validation.

### 2. Event boundaries and book validity

`F_LAST` marks the last normalized record in one event for one instrument. Book-derived values should only be published after `F_LAST`. `F_MAYBE_BAD_BOOK` invalidates queue-derived telemetry until recovery.

DavisAI impact:

- live operator publishes completed-event state only;
- dashboard exposes `book_complete`, `maybe_bad_book`, and last completed event;
- queue/fill estimates stand down on incomplete or possibly bad books.

Authority: hard data-quality gate.

### 3. MBO snapshots

Snapshots begin with Clear and Add records, preserve FIFO priority order, and carry `F_SNAPSHOT` plus `F_BAD_TS_RECV`. Snapshot timestamps are not valid latency or onset observations. A snapshot may end before an exchange event completes; the book becomes valid only at the next `F_LAST`.

DavisAI impact:

- snapshots rebuild state but do not count as live adds/recruitment;
- snapshot records are excluded from latency, activity, onset, and queue-survival calibration;
- book readiness remains false until a completed event boundary.

Authority: raw normalization.

### 4. Timestamp decomposition

Keep separate:

- matching-engine processing: `ts_recv - ts_in_delta - ts_event`;
- publisher-to-Databento capture: `ts_in_delta`;
- Databento-to-DavisAI application: local wall clock minus `ts_recv`;
- optional Databento internal send latency: `ts_out - ts_recv` when available.

Never pool these into one latency number.

DavisAI impact:

- `research/kalshi/ng_live_collector.py`
- `desk/app.py`
- `dashboard/adapters/health.py`

Authority: operations telemetry and product-specific execution gate.

### 5. Slow-reader and backpressure behavior

Recent `databento-python` versions apply time-based backpressure when the internal live queue spans more than about one second by `ts_index`. Slow-reader behavior and skipped-record errors must be visible; connection-live status alone is insufficient.

DavisAI impact:

- surface slow-reader warnings/errors in health;
- distinguish feed freshness from callback backlog;
- raw archival remains primary even if feature callbacks fall behind;
- feature/operator authority stands down when backlog or skipped records are detected.

Authority: data-quality and execution gate.

### 6. Symbology and instrument identity

A symbol or instrument ID may be reused across dates/definition periods. Continuous symbology maps to actual instruments and uses original, unadjusted prices. Calendar (`c`), open-interest (`n`), and volume (`v`) roll rules are distinct.

DavisAI impact:

- all joins key on dataset/publisher/instrument/definition period, not instrument ID alone;
- every forecast and replay records the exact underlying raw symbol and roll rule;
- continuous-contract roll jumps remain marked seams, never market moves;
- Kalshi basis follows its settlement definition, not a generic continuous front.

Authority: hard blind/replay integrity gate.

### 7. Queue position and fill probability

MBO can exactly reconstruct FIFO queue state for venues/products using FIFO. Queue-ahead, cancels ahead, fills ahead, time at level, and priority resets can feed a passive-fill model.

DavisAI impact:

- queue position remains execution telemetry, not forecast direction;
- product/contract/price-level specific calibration;
- separate exact MBO queue model from L1-estimated fill model;
- maker/taker economics must use per-order fill probability and markouts.

Authority: `SHADOW` execution model until forward-live validation.

### 8. Product-specific follower lag

Underlying-to-follower delay is conditioned by venue, product, series, contract, strike/bracket, moneyness, liquidity, time of day, event class, and regime. No universal look-ahead duration is allowed.

DavisAI impact:

- extend lag-map key contract beyond Kalshi band/class/tod;
- onset timestamps from OD/dipole look up the exact follower cell;
- missing product history returns `NO_MEASURED_WINDOW`, never a borrowed delay.

Authority: execution timing gate.

## Research queue

### A. GLBX.MDP3 venue supplement

Extract:

- CME action/side edge cases;
- sequence/channel reset behavior;
- implied orders and publisher-specific flags;
- trade/fill/cancel normalization details;
- instrument-definition lifecycle and corrections;
- packet-gap/recovery semantics.

Deliverable: normalization tests for NG futures.

### B. Historical/live replay parity

Extract:

- `DBNStore.replay` timing semantics;
- `ts_index` selection;
- version upgrades and record conversion;
- snapshot differences between historical and live;
- mixed-schema ordering guarantees.

Deliverable: one deterministic historical replay path that feeds the same NG operator as live.

### C. Queue and fill model

Extract:

- exact FIFO queue-position example;
- modify priority rules;
- partial cancel behavior;
- hypothetical-order insertion rules;
- fill and adverse-selection markouts.

Deliverable: MBO exact queue/fill shadow model plus L1 fallback model.

### D. Latency and backlog

Extract:

- `ts_event`, `ts_recv`, `ts_in_delta`, `ts_out`, local wall semantics;
- slow-reader warnings and skipped-record errors;
- callback versus stream-writing behavior;
- compression and decoding costs;
- queue-span/backpressure instrumentation.

Deliverable: four-clock dashboard and authority stand-down gates.

### E. Symbology, definitions, and rolls

Extract:

- continuous symbol mappings;
- smart-symbol lifecycle;
- reused instrument IDs/symbols;
- definition corrections;
- calendar/OI/volume roll distinctions;
- unadjusted continuous price behavior.

Deliverable: exact instrument identity ledger for every blind/replay/live decision.

### F. Execution markouts and slippage

Extract:

- midprice markouts by horizon;
- passive adverse selection;
- aggressive slippage;
- spread/size/liquidity conditioning;
- product-specific transaction-cost examples.

Deliverable: proper execution scoring separate from forecast scoring.

### G. Retest candidates

Use improved L1/MBO data to retest, in shadow:

- far-side recruitment/thinning;
- resting-book contrarian effects;
- deep-ladder shakeout;
- OD onset pressure;
- recirculation/manipulation filters;
- subsecond reversal timing;
- queue depletion and replenishment signatures.

Deliverable: additions to `knowledge/signal_retest_registry.json`, never direct brain promotion.

## Completion standard

The research track is complete only when:

- all source-derived mechanics have tests;
- live and historical replay use the same normalization path;
- dashboard truth labels match authority;
- no signal is duplicated;
- no queue/latency value survives a bad-book, snapshot, gap, or backlog condition;
- every product-specific look-ahead window is keyed and measured separately;
- all unmeasured items are visibly `None`/`UNKNOWN`, never inferred from another product.
