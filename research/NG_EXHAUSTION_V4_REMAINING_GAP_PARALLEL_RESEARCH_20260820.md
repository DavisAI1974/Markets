# NG Exhaustion V4 remaining-gap parallel research — 2026-08-20

Status: **DOCUMENTATION / SOURCE RESEARCH ONLY. NO V4 LAUNCH. NO PERMANENT FRANKIE MUTATION. NO DATA PURCHASE. NO EXTERNAL MODEL CALL.**

Source checkpoint audited before this record: `97cd9570fa684aafb887fed6c8a26bc60def7ded` on `chatgpt/ng-exhaustion-entry-timing-revival-20260818`.

## Authority boundary

This record follows the clean-source V4 authority wall. V3 model/trade outputs are not used as empirical truth about exhaustion. All chain/case populations remain preserved; weak, negative, sparse, censored, unresolved and model-disagreement cases remain evidence and are not dropped.

The remaining gaps were split into five independent research lanes so one interpretation could not silently close another lane:

1. causal detector clock / exhaustion-state source;
2. book and MBO provenance;
3. history / support expansion;
4. continuous-series and roll provenance;
5. P0/V4 ledger, lock and empirical-readiness boundary.

The purpose was to determine which open items still need genuinely new empirical research, which are source/acquisition questions, and which are now mechanical implementation work.

---

## Executive result

The open V4 work is now narrower than the prelaunch matrix implied.

### Genuinely empirical / new-evidence work still remains in three places

- **Causal exhaustion discovery time (`event_known_by`)**: the current live-clock adapter is explicitly not the event detector. It accepts an upstream `t0` and does not persist a sourceful live discovery timestamp. Retrospective canonical `t0` cannot be substituted. This requires prospective instrumentation or a separately named causal replay/discovery candidate.
- **D3 fine-stratum and especially D4/D5 support**: current clean counts remain D3=124, D4=8, D5=1. Population calibration at D4/D5 is not supportable from the current frozen chronology. Additional independent history is the lawful way to seek more cases; no present case may be dropped or promoted into a universal law.
- **The six P0 empirical-readiness receipts**: held-out performance, calibration/selective risk, planted-null contamination, protected retention, evaluator independence, and live byte-exact rollback still require real executed evidence. Their validators/contracts exist; the missing object is evidence, not another paper design.

### Several items are now source/acquisition or engineering, not broad unknown research

- Exact causal roll-20/aggressor-flow state already exists in `research/ng_exhaustion_live_clock.py`; it can be used as a clearly named V4 causal proxy surface. A separate *detector-native* continuous intensity remains unproven and should simply be omitted unless its source is later proven.
- The current live NG collector **does ingest MBO** and archives a mixed raw DBN stream. Earlier assumptions that the collector lacked MBO are superseded by current-branch source inspection.
- Databento `GLBX.MDP3` supports historical MBO from the CME MBO era (2017-05-21 onward) and MBP-10 farther back. Therefore literal queue survival is not blocked by vendor impossibility; the unresolved question is whether the required historical NG MBO bytes are already present in our archive and, if not, what bounded acquisition is worth buying.
- The current historical backfill utility does **not** safely preserve MBO if `schema=mbo` is requested: its schema-specific writers handle MBP-10 and MBP-1, while the fallback writer is trade-shaped. Historical MBO acquisition therefore needs a raw-DBN-preserving or dedicated MBO writer before any paid pull.
- Roll/series ambiguity is mechanically closeable through immutable symbology maps and row/source provenance. It is not a reason to choose one series silently.
- Probability movie / first-lock ledger, missingness-safe causal movie, unresolved predecessor lifecycle, multi-clock field availability, unified lane registry, reconciler recomputation and sealed execution handoff remain implementation gates already specified by the V4 audits.

---

# Lane 1 — causal detector clock and exhaustion-state source

## What current source proves

`research/ng_exhaustion_live_clock.py` states that it is **NOT an event detector**. An upstream causal detector supplies `t0`.

The adapter does reconstruct the exact causal 20-second rolling aggressor-volume imbalance used by the frozen exhaustion research:

- trade classification is price versus concurrent top-of-book mid;
- buy/sell volume is accumulated by second;
- `raw_value_at(second)` computes `(buy - sell) / (buy + sell)` over the trailing 20 seconds;
- the event polarity and pre-family geometry are derived from the causal roll-20 state around an already supplied `t0`.

The current `LiveExhaustionRunwayEngine.mark_event(...)` accepts `t0_second`, verifies that the live tape has reached it, and creates the event. It does **not** persist `detector_marked_at`, `event_known_by`, or an upstream detector provenance object.

### Reclassification

- `dipole_roll20`: **ANSWERED AS CAUSAL BASIS**.
- `detector_native_continuous_exhaustion_intensity`: **NARROWED / OPTIONAL SOURCE**. No separate frozen detector-native scalar is proven. V4 may proceed without it by using a clearly named `roll20_aggressor_imbalance` or other proxy namespace; do not rename that proxy “detector-native intensity.”
- `detector_marked_at_event_known_by`: **STILL A HARD CAUSAL SOURCE GAP**.

## Lawful research options for `event_known_by`

Two paths remain valid without rewriting the frozen detector:

1. **Prospective live instrumentation**: a separately named research detector/wrapper emits an immutable mark receipt containing source clocks, observed/receive clocks, detector revision, event candidate identity and actual mark time. V4 may not begin prediction for that event before this mark.
2. **Causal replay candidate**: replay raw observations in receive/availability order and run a separately versioned causal discovery rule. The mark is the first time the rule can lawfully declare the event. Retrospective canonical `t0` remains scoring/provenance metadata and is never substituted for the discovered mark.

If reproducing the retrospective canonical detector causally requires future neighborhood information or a later day-level statistic, the replay must delay the declaration until those inputs are actually available. It may not backdate the event-known clock.

This lane therefore does **not** call for broad literature research. It calls for source-semantic verification plus prospective/replay instrumentation and measurement.

---

# Lane 2 — book and MBO provenance

## Correction from current branch source

`research/kalshi/ng_live_collector.py` currently subscribes to:

- `mbo` with `snapshot=True`;
- `mbp-10`;
- `trades`;
- `tbbo`;
- `definition`;
- `statistics`;
- `status`.

It writes the native stream to a mixed DBN archive and uploads completed archives to the configured S3 live prefix. The code explicitly treats MBO as stateful and does not skip MBO records. Its health state also exposes the latest MBO action/side/price/size, while the raw DBN is the durable source.

`BUILD_STATUS_NG_LIVE.md` independently documents the intended mixed raw DBN archive as MBO + MBP-10 + trades + TBBO + definition + statistics + status.

### Reclassification of literal queue source

`literal_queue_survival` is no longer correctly described as “vendor/source capability unknown.” It is better classified as:

**SOURCE AVAILABLE; EXISTING HISTORICAL CORPUS COVERAGE NOT YET CERTIFIED.**

Databento documents full order-event MBO for CME `GLBX.MDP3` from the MBO era beginning 2017-05-21. That is sufficient in principle to reconstruct order IDs, adds/cancels/modifies and queue survival for NG windows.

## Historical acquisition trap found by this lane

`research/kalshi/databento_backfill.py` is safe and rich for MBP-10/MBP-1, but its current dispatch only has dedicated full writers for those schemas. A `schema=mbo` historical pull would fall through to the generic trade-shaped writer, which would not preserve the complete order-event payload.

Therefore **do not buy historical MBO with the current writer path**.

Before any MBO purchase, add an isolated preservation path that either:

- stores the returned native DBN unchanged and hashes it; or
- writes every MBO field without reduction, including event/receive clocks, order ID, action, side, price, size, flags, sequence/channel/instrument identity and snapshot markers.

Then build a per-session/channel coverage manifest before claiming literal queue features are available for a case.

## Cost-safe acquisition option

Databento exposes `metadata.get_cost`, and the existing backfill utility already cost-gates requests. A future authorized acquisition should first run cost-only probes for the exact NG intervals and never exceed a predeclared ceiling. No cost probe or purchase was executed here.

---

# Lane 3 — history and support expansion

## Current support facts

The clean V4 matrix preserves the current depth counts:

- D0: 135,860
- D1: 18,837
- D2: 1,592
- D3: 124
- D4: 8
- D5: 1

The frozen full-history coverage record contains 55 usable complete trading weeks and 329 unique raw dates spanning roughly late June 2025 through mid-July 2026. That is a complete frozen corpus for its defined scope, but it is not enough to make fine D3 or population-level D4/D5 claims.

## External history option exists

Databento documents CME `GLBX.MDP3` history from 2010-06-06. For V4's strongest multi-clock and literal-order-book work, the cleaner boundary is 2017-05-21 onward because that is the MBO era and capture-time semantics are richer. This creates multiple years of potential independent NG history beyond the frozen 55-week corpus.

This does **not** guarantee more D4/D5 cases. The only lawful way to know is to run the unchanged frozen detector/canonical rules on a provenance-certified outside chronology and count every resulting chain/case.

## Recommended support expansion order

1. **Expand the same causal MBP-10/trade basis first** under unchanged detector/canonical rules. This directly addresses D3/D4/D5 support without changing the measurement system at the same time.
2. Keep the newly added chronology outside the old frozen discovery corpus and preserve every generated case.
3. Treat D4/D5 as case-ledger evidence until support actually grows enough for population calibration.
4. Add MBO as a distinct optional channel/ablation around certified windows; do not make expensive L3 acquisition a prerequisite for merely discovering whether deeper chains exist.
5. Preserve future genuinely untouched chronology for forward/held-out evidence. Backfilling older history can increase support, but it cannot turn already inspected chronology into a virgin release holdout.

### Reclassification

- `d3_fine_stratification`: **EMPIRICAL SUPPORT GAP; EXPANDABLE**.
- `d4_d5_population_calibration`: **EMPIRICAL SUPPORT GAP; CURRENTLY CASE-LEDGER ONLY**.
- No chain is a failure because support is sparse; the support count itself is evidence.

---

# Lane 4 — contract, continuous-series and roll provenance

## Concrete ambiguity found

The repo contains multiple continuous-series conventions that must not be silently conflated:

- current live collector default: `NG.v.0`;
- `databento_backfill.py` default: volume roll `v`;
- that same backfill code explicitly records a prior research finding that the G11+ walk basis moved to `NG.n.0` because `NG.v.0` could switch contracts through expiry-week behavior;
- the frozen full-history repair for the 2025-06-29 Sunday reopen explicitly records `NG.v.0`.

This does not prove that every frozen row is mixed-series. It proves that a V4 row cannot safely inherit a generic `NG` label and assume one roll rule.

## Mechanical closure path

Databento's symbology layer can resolve continuous symbols to actual instrument IDs over dated effective intervals. The definition stream can then bind raw symbol and contract metadata.

Every V4 source interval / instance should therefore pin at minimum:

- dataset;
- schema/channel;
- input symbology type;
- requested continuous symbol (`NG.v.0`, `NG.n.0`, `NG.c.0`, or raw symbol);
- roll rule;
- resolved instrument ID;
- raw symbol;
- effective mapping interval;
- definition/source revision;
- mapping acquisition time and content hash;
- raw object/message-range hash.

A v/n/c mismatch is a provenance distinction, not something to normalize away silently. Existing frozen evidence must remain frozen; V4 adds provenance around it rather than rewriting the old chain population.

### Reclassification

`contract_series_roll_identity`: **ENGINEERING-CLOSEABLE WITH SOURCE PROVENANCE**, with one empirical follow-up available later: a predeclared series-basis sensitivity/ablation if we need to know whether conclusions depend materially on roll convention.

---

# Lane 5 — P0/V4 ledger, model-lock and readiness boundary

## What is already solved as contract/engineering

`FRANKIE_P0_GAP_CLOSURE_PROVISIONAL_20260820.md` and `frankie_p0_registry.py` already define a fail-closed Registry V2 evidence boundary. Component contracts are ready but have no empirical performance authority.

`FRANKIE_V4_UNIFIED_FRAMEWORK_AUDIT_20260820.md` already specifies the required one-registry / one-engine / one-reconciler V4 architecture and its minimum artifact identity. The remaining V4 ledger/lock items are therefore not unanswered research questions:

- deterministic state/feature/graph identity;
- every-second probability movie;
- independent first-lock recomputation;
- explicit invalid/no-reliable-lock/no-lock/wrong-lock/late/censored states;
- immutable active-instance snapshots;
- reveal-before-update enforcement;
- byte-verifiable rollback lineage;
- unified `V4LaneSpec` registry and adapter conformance;
- reconciler recomputation and tamper tests;
- sealed signal-to-execution handoff that cannot re-predict/re-time/re-fuse.

These are implementation gates to close and test on one exact candidate commit once separately authorized.

## What remains genuinely empirical in P0

The six readiness receipts remain absent:

1. untouched held-out paired performance;
2. calibration and selective risk;
3. planted-null contamination;
4. complete protected retention matrix;
5. evaluator-independence canary;
6. non-vacuous byte-exact live rollback.

The registry already knows how to validate those receipts. The missing package is real data + real executions + independent evaluator + disposable rollback target + explicit cost/mutation authority where needed.

Additional broad paper reading is not the next bottleneck. The handoff correctly says to deep-audit only gap-critical references rather than treating the remaining screened GDL bibliography as work that must be completed before V4.

---

# Reconciled remaining-gap matrix

| Gap | New status after parallel research | Next lawful action |
|---|---|---|
| `event_known_by` | **GENUINE CAUSAL MEASUREMENT / PROVENANCE GAP** | prospective detector mark instrumentation or separately named causal replay discovery rule; never infer from retrospective `t0` |
| exact causal roll-20 state | **ANSWERED** | expose sourceful raw roll-20 under explicit V4 proxy namespace with clocks/revision |
| detector-native continuous intensity | **UNPROVEN BUT NON-BLOCKING IF OMITTED** | prove native stream later or omit; do not rename proxy |
| aggregate MBP geometry | **SOURCE EXISTS; COVERAGE MANIFEST STILL REQUIRED** | build exact per-session/channel manifest and masks |
| literal MBO queue survival | **SOURCE AVAILABLE; CORPUS COVERAGE/WRITER GAP** | inventory live MBO archives; implement lossless historical MBO preservation before any paid pull |
| historical MBP-10 corpus | **FROZEN 55-WEEK SCOPE COMPLETE** | add V4-compatible per-session provenance/coverage rather than reacquire the same scope |
| D3 fine strata | **EMPIRICAL SUPPORT LIMITED** | add provenance-certified outside chronology under unchanged rules |
| D4/D5 calibration | **EMPIRICAL SUPPORT LIMITED / CASE-LEDGER ONLY** | expand independent history; retain all 8 D4 and 1 D5 cases regardless of outcome |
| roll/series identity | **ENGINEERING-CLOSEABLE** | immutable continuous→instrument/raw-contract map; fail closed on v/n/c ambiguity |
| missingness/multi-clock causal movie | **ENGINEERING-CLOSEABLE** | implement required state/mask/clock schema and conformance tests |
| unresolved predecessor lifecycle | **ENGINEERING-CLOSEABLE** | implement prospective UNRESOLVED/RESOLVED/CENSORED state |
| probability/first-lock ledger | **ENGINEERING-CLOSEABLE** | one shared engine + append-only/recomputable ledger and tamper tests |
| prediction→execution handoff | **ENGINEERING-CLOSEABLE** | sealed signal identity; execution may not alter predictive call |
| P0 six receipts | **GENUINE EMPIRICAL EVIDENCE GAP** | real untouched chronology, matched real executions, independent evaluator, protected retention and live rollback evidence |

---

# What should happen next

The research phase should not expand into another generic design cycle. The evidence now supports three parallel continuations, each kept separate:

**A. Mechanical V4 prelaunch closure** — implement the already-specified clock/provenance/state/ledger/hand-off contracts on one clean unified candidate, without launching it.

**B. Data/support plan** — inventory existing live MBO archives, produce exact MBP/MBO/L1 coverage manifests, and prepare cost-only historical expansion estimates. Do not purchase data until cost authority is explicit.

**C. Prospective evidence plan** — define the separate causal `event_known_by` capture and preserve future untouched chronology for V4/P0 forward evidence.

Only after those are closed should a separate authorization name one exact candidate commit and ruleset for any V4 empirical dispatch.

## Source anchors used by the lanes

Repository source:

- `research/NG_EXHAUSTION_V4_CLEAN_SOURCE_DEEP_DIVE_GAP_MATRIX_20260820.json`
- `research/NG_EXHAUSTION_V4_CLEAN_SOURCE_DEEP_DIVE_COMPLETE_FINDINGS_20260820.md`
- `research/NG_EXHAUSTION_FULL_HISTORY_COVERAGE_FREEZE_20260817.json`
- `research/ng_exhaustion_live_clock.py`
- `research/kalshi/ng_live_collector.py`
- `research/kalshi/ng_live_recover.py`
- `research/kalshi/databento_backfill.py`
- `BUILD_STATUS_NG_LIVE.md`
- `research/kalshi/FRANKIE_P0_GAP_CLOSURE_PROVISIONAL_20260820.md`
- `research/kalshi/FRANKIE_V4_UNIFIED_FRAMEWORK_AUDIT_20260820.md`
- `research/kalshi/frankie_p0_registry.py`

External primary source:

- Databento CME Globex MDP 3.0 dataset documentation (historical availability and schema coverage)
- Databento MBO schema/snapshot documentation
- Databento symbology documentation (continuous `c`/`n`/`v` mapping and `symbology.resolve`)
- Databento Historical API `metadata.get_cost` documentation

No V3 predictive/trade result was used to close any V4 D question in this record.
