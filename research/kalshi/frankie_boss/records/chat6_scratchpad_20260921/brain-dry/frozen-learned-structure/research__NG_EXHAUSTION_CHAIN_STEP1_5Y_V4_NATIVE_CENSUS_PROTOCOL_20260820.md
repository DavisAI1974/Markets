# NG Exhaustion Step-1 — Five-Year V4-Native Structural Census Protocol — 2026-08-20

Status: **BINDING ADDITIVE STRUCTURAL-CENSUS PROTOCOL. BUILD/PREPARATION AUTHORIZED. NO RESULT-BEARING FIVE-YEAR CENSUS OR V4 PREDICTIVE RUN IS AUTHORIZED BY THIS FILE.**

Repository: `DavisAI1974/Markets`

Branch: `chatgpt/ng-exhaustion-entry-timing-revival-20260818`

## 1. Purpose

The next large historical-data pass has a distinct Step-1 purpose:

**first establish what exhaustion chains actually exist in the expanded chronology; only afterward test whether Frankie can predict their evolution before it happens.**

This Step-1 pass is a structural census/population-construction exercise. It is not the later per-D prediction experiment, not a trade-edge test, not a calibration test and not a promotion run.

It must produce a complete immutable population registry containing every eligible root/event, ordered ancestry, chain membership, realized/reset structure, terminal depth/support status and provenance. Negative, weak, losing, censored, unresolved, sparse, contradictory and unusual cases remain in the population.

## 2. Why this is not a date-only rerun

The frozen three-week scripts contained pilot-only exact week/event-count assertions. The prior 54/55-week expansion correctly replaced those assumptions through wrappers while preserving the underlying frozen doctrine.

The five-year corpus also changes the source surface materially: the new canonical historical archive is true Databento `GLBX.MDP3` MBO for `NG.v.0`, whereas the original canonical Step-1 builder consumed a trade/MBP-10-shaped stream.

Therefore five-year Step 1 requires a new adapter and new wrappers. Frozen 2026-08-17 artifacts are not edited in place.

## 3. Dual structural census is mandatory

The five-year Step-1 work has two explicit views. Neither may silently replace the other.

### 3.1 `LEGACY_CONTROL`

Goal: preserve continuity with the frozen historical Step-1 experiment.

The MBO adapter reconstructs the book and emits a compatibility projection containing the trade and top-10 book fields needed by the frozen detector/canonical machinery. Before any five-year control result is trusted, overlap samples must demonstrate that this projection reproduces the old detector/event-table behavior within predeclared equivalence tolerances. Exact mismatches are retained and decomposed; they are not hidden.

The control view retains the old rule that Phase-1 chain boundaries are established from inherited behavioral information before family/time/shape/book characteristics are used to name or characterize them.

### 3.2 `V4_NATIVE_FULL`

Goal: discover the structural organization available to Frankie from the information he will actually receive.

This is a **new V4-native structural census**, not a rewrite of frozen Phase 1.

It may consume every lawful causal V4 channel whose own availability time has passed, including:

- raw MBO action semantics;
- venue `order_id`;
- FIFO priority reconstructed from MBO message/snapshot order where supported;
- event `sequence`, `channel_id`, `publisher_id` and instrument identity;
- `ts_event`, `ts_recv`, `ts_in_delta` and derived source-availability time;
- add/cancel/modify/trade/fill/clear activity;
- order size, side and price;
- reconstructed full-depth book and top-N aggregates;
- queue depth/order count and volume-ahead/priority distributions;
- queue age/survival summaries;
- depletion/cancellation and top-level add/replenishment-like activity, explicitly named as derived when it is not a native field;
- spread, micro/book imbalance and depth concentration;
- direct trade aggressor side where disseminated;
- price path;
- signed flow;
- dipole / roll-20 trajectories and lawful exhaustion proxies;
- causal `event_known_by` and multi-clock availability;
- missing/stale/not-yet-known/not-applicable semantics;
- unresolved predecessor lifecycle;
- exact requested continuous symbol, resolved raw contract/instrument and roll provenance;
- time/session context that would lawfully be available to Frankie.

No future descendant, retrospective endpoint truth, revealed terminal depth, later family truth or other not-yet-known information may leak into a causal state.

## 4. MBO is a first-class language Frankie must learn

The native DBN remains the canonical source of truth. Derived state is an auditable representation, not a replacement for native bytes.

The adapter must expose both:

1. normalized raw event semantics so Frankie/research can distinguish what occurred; and
2. causal reconstructed state/features that describe what those actions mean for the book and queue.

Databento CME MBO does not expose CME tag `37707-MDOrderPriority` as a standalone field. The adapter must not invent a `PriorityID`. FIFO priority is reconstructed from message order/snapshots where supported and labeled as reconstructed priority.

CME/Databento MBO event groups must not be sampled mid-update. State used for a completed event snapshot is emitted only at an `F_LAST` boundary. Snapshot/bootstrap messages initialize book state but must not masquerade as live add/cancel/trade activity.

## 5. State-management semantics

The adapter follows Databento MBO normalization semantics:

- `A`: add resting order;
- `C`: remove the disseminated cancelled quantity, deleting the order when exhausted;
- `M`: replace current order state; price change or size increase loses FIFO priority; size decrease/same-price update retains priority;
- `R`: clear resting book for the instrument;
- `T`: aggressing trade record; does not itself mutate resting-book state;
- `F`: resting fill detail; does not itself mutate resting-book state because the corresponding book reduction is represented separately;
- `N`: no book-state mutation.

Any normalization anomaly, missing referenced order, sequence discontinuity, unsupported action, source gap or snapshot ambiguity is retained in an integrity channel and never silently repaired with future information.

## 6. Source/contract/roll provenance

Every V4-native state and every census event must bind to exact source identity:

- dataset `GLBX.MDP3`;
- schema `mbo`;
- requested continuous symbol `NG.v.0` for the approved corpus;
- resolved raw symbol/contract when available;
- instrument ID;
- publisher/channel;
- source DBN object key + SHA-256;
- Databento job/segment identity;
- event/receive timestamp range;
- continuous mapping/roll interval and mapping source;
- adapter revision/hash.

`NG.v.0`, `NG.n.0`, `NG.c.0` or another continuation basis may never be silently substituted.

## 7. Census output contract

The structural census must freeze, at minimum:

- `census_view` = `LEGACY_CONTROL` or `V4_NATIVE_FULL`;
- `chain_id` / origin identity;
- ordered member event identities;
- predecessor/successor ancestry;
- realized/reset boundary under that census view;
- realized structural depth;
- elapsed-time length;
- per-link inherited-information evidence / uncertainty appropriate to the view;
- causal/executable availability status for each link;
- censored/unresolved state;
- exact source/contract/roll provenance hash;
- exact adapter/engine/ruleset hashes;
- every preserved case and exclusion/integrity reason.

For `V4_NATIVE_FULL`, any discovered structural taxonomy that differs from the old D0-D5 representation gets a new versioned label/identity. Do not force novel structure into an old label merely for convenience.

## 8. Crosswalk, not overwrite

After both views are frozen, build an immutable crosswalk:

- matches between legacy-control and V4-native roots/chains;
- splits where one legacy chain becomes multiple V4-native structures;
- merges where richer state supports a common structure;
- depth agreement/disagreement;
- reset-boundary agreement/disagreement;
- support changes;
- cases only visible/usable in one view;
- provenance or source-coverage reasons for disagreement.

The old frozen 55-week population remains frozen. New five-year findings are additive.

## 9. Validation hierarchy

Before any large census run:

1. unit/adversarial-test MBO state management synthetically;
2. verify native DBN parsing and source metadata on a tiny non-result-bearing sample;
3. on overlap dates, compare `LEGACY_CONTROL` projection against the old MBP/trade-shaped detector/event output;
4. freeze equivalence/mismatch policy;
5. run a very small structural-census pilot only when separately authorized;
6. save full five-year census for later, after archive and coverage verification.

The user explicitly wants large runs last. Year/week shards are execution partitions only and must reconcile exactly into one frozen census population.

## 10. Relationship to per-D prediction protocol

`research/NG_EXHAUSTION_V4_PER_D_CHUNKED_RUN_PROTOCOL_20260820.md` governs the **later result-bearing predictive stage after a structural population exists**.

The Step-1 census itself is not a `D0_TERMINALITY` or `D3_CONTINUATION` prediction run. It discovers/freezes the structural population from which those later D-specific targets are formed.

Correct sequence:

`verified expanded chronology`
`-> Step-1 LEGACY_CONTROL census`
`-> Step-1 V4_NATIVE_FULL census`
`-> frozen crosswalk/population registry`
`-> support + characterization`
`-> tiny blind V4 prediction pilots`
`-> D-specific/year-specific predictive runs`
`-> full empirical/P0 validation last`

## 11. Protected boundaries

This protocol does not authorize mutation of:

- frozen exhaustion detector;
- frozen canonical 55-week rows;
- frozen Phase-1/Phase-2 findings;
- frozen runway clock;
- permanent Frankie / Frankie 1;
- `research/kalshi/spawn.py`;
- frozen V3 artifacts.

The adapter and new V4-native structural engine are additive/versioned new work.

## 12. Immediate build authority

Current authorization permits:

- build/test the MBO state adapter;
- build the compatibility projection;
- build source/coverage and census manifests;
- build synthetic/adversarial tests;
- update documentation/contracts;
- perform non-result-bearing parser/equivalence preflight on tiny samples as source files become available.

It does **not** authorize a full five-year structural census or later V4 predictive experiment without the separately required run authorization boundary.
