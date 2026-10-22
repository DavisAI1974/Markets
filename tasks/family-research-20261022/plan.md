# Remaining family-research data plan

The user authorized the revised Julia run on October 22, 2026. Run it against the completed input caches without changing its cohort or definitions midway. Plan and source inventory work proceeds alongside that run; no subagents, monitors, new chats, or messages are involved.

## Current run

Run `run_descriptive.jl`, `summarize_descriptive.jl`, `compare_context_changes.jl`, and `report_descriptive.jl` on the existing persistent EC2 directory. Retain every family and original source row. Keep the 13 historical concepts, 99 registry identities/dispositions, second-set records, and timestamped instrument prices linked. Separate strictly pre-start, onset, and later observations. Save actual results, available-pair counts, ages, source clocks, session-edge censoring, chronological stability, overlapping-window diagnostics, and every computed exploratory comparison. No model, predictive target, or backtest is authorized by this descriptive run.

## Task 1: Distinguish recoverable input gaps from undefined measurements

**Acceptance:** Each reported gap has a source reason, family/series/cutoff key, available count, age, and one of: recoverable observation; source-defined undefined value; unavailable publication; censoring; unknown history. A current missing value is never replaced by a future observation or a differently defined metric.

**Verification:** Reconcile the input inventories with the expanded run's feature availability. Preserve original masks and provenance alongside any separately derived observation.

**Dependency:** Current input inventory; no dependency on favorable price results.

## Task 2: Add lifecycle observations identified by the earlier SQLite runs

Earlier SQLite catalog paths identify queue episodes, requeue opening bases, absorption, replenishment, priority semantics, continuity segments and source clocks. These are the most useful unconsumed source area. Retrieve original native.lifecycle rows only through the pinned index and the exact lifecycle ordinals referenced by selected source records' availability receipts.

**Acceptance:** Retain full original paths/indexes, observed family versus target family, source ordinal, instrument, event/receive/emission/known-by clocks, scope and censoring. Extract numeric queue progression, fill/cancel/refill/priority measurements only after checking their source definitions. Every pre-start measurement must have been emitted and known before its cutoff. Preserve terminal/exit information as later sequence evidence, never as an earlier predictor.

**Verification:** Source-reference and unit checks on the newly extracted observations; counts of available, missing, censored and rejected-as-future values. No recovery-directory enumeration and no ledger rescan.

**Dependency:** Task 1; small pilot across existing indexed contexts before a full context export.

## Task 3: Resolve genuinely omitted dictionary measurements

Some action/side dictionaries omit keys. A source-null value is not equivalent to an absent counter key. Inspect the exact counter-builder implementation before deciding whether an omitted action means measured zero.

**Acceptance:** If the implementation proves zero semantics, add a separate derived counter with an explicit rule and source-key-presence flag. Keep the original absence. Otherwise retain missingness. Unknown duration anchors remain unknown.

**Verification:** Reconcile derived action totals with independently recorded event/action totals for the same group and scope; report contradictions.

**Dependency:** Task 1. Do not change the running analysis inputs midway.

## Task 4: Preserve observable alternatives to undefined flow/step fields

Bid/ask queue ages and ongoing pullback geometry are already added. Continue to preserve both book sides when flow cannot select a far side. A last/previous completed-step pullback cannot exist before the required completion. NO_FLOW, SIDE_UNDEFINED, NO_COMPLETED_STEP and CHAIN_BROKEN are process states, not holes to impute.

**Acceptance:** Keep ongoing versus completed geometry separate, with exact rational values, original dispositions and observation age. Any further flow-independent measurement has its own name and definition; it cannot overwrite the original far-side or completed-step field.

**Verification:** Source-equation equivalence where both representations are defined, and explicit counts for the undefined cases.

**Dependency:** Task 1; existing stored geometry and book contexts.

## Task 5: Improve external context without future backfill

Actual same-station published temperature history is complete at the current pre-start cutoffs. Other weather measurements may still have no historical numeric observation. Forecast gaps are specific to model/horizon/target-day/vintage series; other horizons remain available. Calendar-count availability follows the recorded source clock even when its metadata describes a calendar rule.

**Acceptance:** Add earlier forecast vintages only as distinct model/horizon/vintage observations. Expand external alignment to any additional context cutoff used by a later analysis, keeping all 13 concepts attached. Derive a separate calendar count only if historical expiry, session calendar and prior availability can be demonstrated; never backdate the saved publication. Preserve publication-confidence and nominal-clock qualifications.

**Verification:** Exact publication-as-of tests, dimension isolation, observation ages and source-row receipts. No interpolation or global tick forward-fill.

**Dependency:** Task 1; use the already retained external tables and provenance first.

## Task 6: Audit price and session boundaries

Check only known indexed earlier/later source ranges if they contain actual same-instrument trades or quotes beyond a censored endpoint. Do not redownload or restore the verified database. If the retained source does not cover an endpoint, retain censoring.

**Acceptance:** Every added endpoint has an original event/receive/availability clock, cursor and instrument. Compare transaction-price changes with independently observed bid/ask/mid changes where available, to assess spread bounce. Stale prices and shorter observed intervals stay explicit.

**Verification:** Validate price and spread units against price_raw/1e9, with no invented post-session flat returns and no future information in input features.

**Dependency:** Task 1 and existing price/source indexes.

## Task 7: Broader evidence rather than manufactured completeness

Constant COT/storage or other slow historical inputs are real observations, not missing variation. The earlier SQLite runs concern the same retained market day; their report dates do not supply additional market days.

**Acceptance:** Do not promote a descriptive association without chronological and dependence checks. Any later multi-day extension must use actual retained days with matching provenance, instruments and clocks; it remains a separate dataset version. Keep the one-day results intact.

**Verification:** Source-day inventory and explicit out-of-sample separation before any future predictive or trading claim.

## Use of earlier SQLite results

The uncapped query export is the catalog reference. The old capped export is superseded. The earlier 1,594,763 task rows, 74,309 surviving tasks, 364,393 catalog selections and 210,412 field paths describe an inventory/search representation, not independent market events or predictive effects. Shared-selection labels are aliases; they are not established AND conditions. Paths such as level_event_key, IDs, hashes, absolute timestamps, outcome labels and future exits remain linkage/provenance, not numerical predictors. No earlier "surviving" filter defines the master cohort.

The field-path audit saved with this plan lists exact original paths and classifications. It is a roadmap to original rows, not a statistical candidate ranking.
