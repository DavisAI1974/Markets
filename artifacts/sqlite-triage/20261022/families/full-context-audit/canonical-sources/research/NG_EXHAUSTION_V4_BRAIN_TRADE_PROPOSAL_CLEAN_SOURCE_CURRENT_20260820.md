# NG Exhaustion V4 Brain + Trade Proposal — Clean-Source Current — 2026-08-20

Status: **CURRENT V4 PROPOSAL. PROPOSAL ONLY. NO V4 EMPIRICAL LAUNCH. NO PERMANENT FRANKIE MUTATION. NO PLAY PROMOTION.**

This file is the current proposal interpretation for the next V4 session. It supersedes the active proposal interpretation in `NG_EXHAUSTION_V3_V4_BRAIN_TRADE_PROPOSAL_FINAL_ADDENDUM_20260820.md` while preserving that older file as provenance.

## Authority boundary

The proposal is grounded in:

- frozen/protected detector and canonical evidence;
- finalized Phase-2 and frozen runway records;
- preserved chain lineage and chronological support counts;
- raw causal price/trade/flow/dipole/book interfaces and archive schemas;
- the five clean-source V4 deep dives: Gap Source, Trajectory, Geometry, History, and Ledger;
- `NG_EXHAUSTION_V4_CLEAN_SOURCE_DEEP_DIVE_COMPLETE_FINDINGS_20260820.md`;
- `NG_EXHAUSTION_V4_CLEAN_SOURCE_DEEP_DIVE_GAP_MATRIX_20260820.json`;
- `NG_EXHAUSTION_V4_CLEAN_SOURCE_PRELAUNCH_GATES_20260820.md`;
- `NG_EXHAUSTION_V4_REMAINING_GAP_PARALLEL_RESEARCH_20260820.md`;
- `research/kalshi/FRANKIE_V4_UNIFIED_FRAMEWORK_AUDIT_20260820.md`;
- the current live Databento entitlement receipts and source inspection.

**V3 model/trade outputs are not empirical truth about exhaustion.** Do not use V3 AUCs, exact PRIOR/T0/H calls, continuation/depth/P/O/S/X predictions, model disagreements, fixed-horizon economics, or null lanes as scientific limits on the phenomenon. V3 remains provenance/debugging material only.

Every chain/case remains preserved. Sparse, negative, unresolved, missing-channel, censored, losing, late, and model-disagreement cases are evidence, not failed/dropped chains.

---

## 1. Primary object Frankie should learn

Exhaustion is a dynamic structural process, not a direction classifier.

The proposed primary V4 heads/state are:

1. exhaustion persistence versus collapse;
2. runway / maturity / remaining-lifespan distribution;
3. P/O/S/X structural-state distribution;
4. structural continuation / termination probability;
5. eventual chain-depth distribution;
6. ordered chain-transition geometry and ancestry context;
7. unresolved predecessor lifecycle and resolution state;
8. continuous causal recognition / first-lock state and confidence;
9. support/calibration state by stage, geometry, regime, session, ancestry and channel availability.

Direction/polarity is causal context and a possible downstream execution variable. It is not the primary definition of whether exhaustion was measured correctly.

---

## 2. Timing: causal knowledge clocks, not target-relative buckets

Do not operationalize V4 as `PRIOR -> T0 -> H+N` scanning.

The clean-source work establishes that retrospective canonical `t0` is not proof of when Frankie could know the event existed. V4 must preserve distinct clocks, including at minimum:

- `ts_event`;
- `ts_recv` / `observed_at`;
- `detector_marked_at` / `event_known_by`;
- `structural_onset_at`;
- `structural_confirmation_at`;
- `feature_available_at`;
- `model_evaluated_at`;
- `lock_decided_at` / `decision_available_at`.

No derived feature can become available before the latest lawful availability of all contributing inputs. Persistence-confirmed state may not be backdated.

The remaining hard timing measurement is `event_known_by`. The present live-clock adapter is explicitly not the detector and accepts an upstream event time. V4 therefore needs either:

1. prospective detector-mark instrumentation; or
2. a separately named causal replay discovery rule that emits the first lawful mark time.

Retrospective canonical `t0` remains scoring/provenance metadata only and cannot substitute for live discovery time.

---

## 3. Causal state movie and missingness

At every causal second, V4 should build an immutable state movie from all information lawfully known by that cutoff.

Per channel, missingness must distinguish at minimum:

- `OBSERVED`;
- `PAST_CARRY`;
- `STALE`;
- `MISSING`;
- `STRUCTURALLY_NOT_YET_KNOWN`;
- `NOT_APPLICABLE`;
- true numerical zero.

A newly arriving observation may not rewrite an earlier frozen movie row. Carried values retain source timestamp and age.

---

## 4. Unresolved predecessor lifecycle

The clean-source trajectory work says this is primarily a state-construction problem, not a missing-data problem.

For each causally known predecessor, maintain prospectively:

- identity and chain order;
- lawful known-by time;
- structural onset and confirmation when available;
- `UNRESOLVED`, `RESOLVED`, or `CENSORED` state;
- elapsed unresolved age;
- current causal price/path, signed-flow, roll-20/dipole, and book state where available;
- ancestry and relative timing/scale context;
- explicit channel missingness/staleness masks.

Do not expose future chain membership, future target existence, future target time, eventual depth, future family/polarity, or posthoc overlap labels as live state.

A survival/hazard output remains a V4 model hypothesis to test, not a currently established law.

---

## 5. Geometric representation

The ancestry skeleton and most required market measurements already exist or are causally derivable. V4 should add the representation, not invent new raw facts.

Key proposed geometry:

- ordered predecessor-to-predecessor and predecessor-to-live temporal gaps;
- live age relative to already-known anchors;
- tick-normalized price displacement/range and relative scales;
- path-so-far shape descriptors and path distances;
- signed-flow persistence/reversal geometry;
- roll-20/dipole sign-runs, area, slope, change-of-slope, curvature and lawful crossings;
- aggregate MBP depth depletion/recovery/resilience where coverage is certified;
- cross-link time/price/flow/dipole/book ratios and distances;
- session/contract context;
- source/provenance/missingness state.

Preserve causal chain order; do not impose permutation invariance on ancestry or book-level rank.

Do not claim a trained TGN/TGAT, spectral mechanism, ReLIC, graphon invariance, or learned topology unless that exact mechanism is independently implemented and validated. Simpler ordered-message/Deep-Sets/1-WL/static controls remain required.

---

## 6. Flow, dipole, book and MBO semantics

### Flow and dipole

The causal roll-20/aggressor-flow basis is already available. It should be exposed under an explicit V4 proxy/source namespace with transform revision and lawful clocks.

A separate frozen detector-native continuous exhaustion-intensity stream is still unproven. It is non-blocking if omitted. Do not rename roll-20 or another proxy as detector-native intensity.

### Aggregate book

MBP-10 can support aggregate depth, imbalance, depletion, recovery and resilience where exact coverage is certified. A per-session/channel coverage manifest is required before claiming population-wide availability.

### Literal queue survival / MBO

Literal order survival, add/cancel/modify lineage and queue replenishment require provenance-complete MBO/order-event data. Aggregate MBP recovery must not be mislabeled as literal queue survival.

Current live-source fact as of 2026-08-20:

- GitHub secret `MARKETS_NG_LIVE_MBO` is present and valid for the Databento live client;
- `GLBX.MDP3` trades are authorized and produced live records;
- the same credential receives explicit `Not authorized for mbp-10 schema` and `Not authorized for mbo schema` responses;
- therefore current Databento Standard live access does **not** provide the L2/L3 depth required here;
- do not degrade the research contract by silently substituting trades-only live data for MBP-10/MBO.

Historical MBO remains a separate acquisition path. Before any paid historical MBO pull, preserve native DBN bytes or implement a lossless MBO writer; the existing historical fallback writer is not sufficient for full order-event preservation. Use Databento cost estimation first and a hard predeclared spend ceiling.

The next chat must perform an **exhaustive public vendor search for a cheaper live CME/NYMEX NG depth source than Databento Plus**, specifically live MBP-10/L2 and MBO/L3/order-level data for Henry Hub NG on CME Globex. It must verify actual entitlement and price directly from current vendor sources, not infer from marketing labels. Compare at minimum:

- monthly/annual price and exchange/licensing fees;
- whether CME/NYMEX NG is included;
- L2 depth versus true L3/MBO/order IDs;
- add/cancel/modify and queue-position/survival capability;
- event and receive timestamps;
- API/protocol and Python usability;
- raw-message archival/replay rights and historical backfill availability;
- retention, rate limits and session reliability;
- professional/non-professional classification requirements;
- redistribution/display restrictions;
- whether the feed can legally and technically support our V4 research and eventual live system.

Do not recommend an alternative unless its live depth semantics are explicitly verified.

---

## 7. Contract, roll and source provenance

V4 must never treat continuous NG as an identity-free series.

The repository has used multiple roll conventions, including `NG.v.0` and `NG.n.0`, and the frozen history contains explicitly documented `NG.v.0` material. Every source interval/instance should pin at minimum:

- dataset/publisher;
- schema/message type;
- requested symbol and symbology type;
- roll rule;
- resolved instrument ID;
- raw symbol;
- effective mapping/definition interval;
- definition/source revision;
- raw object/message range and content hash;
- builder/transform revision and hash.

A `v`/`n`/`c` mismatch is a provenance distinction, not something to normalize away silently.

---

## 8. Channel fusion and extraction

Do not assume flat concatenation is optimal and do not require cross-model voting.

Keep identifiable structural, price/path, flow/dipole, aggregate-book, optional MBO, and context channels or equivalent ablations. Test flat, gated, late-fusion, stage-aware, and context-aware alternatives only under causal/matched-budget controls.

Model disagreement is evidence about extraction/representation, not a reason to discard a case.

---

## 9. Unified V4 architecture

One unified V4 remains the only safe design.

Use:

- one immutable `V4LaneSpec` registry;
- one orchestrator;
- one shared engine;
- target-specific adapters only for population, labels, reveal logic, causal start/end, feature provider, coordinate formatting and case-study restrictions;
- one registry-driven reconciler.

The shared engine owns chronology, immutable snapshots, every-second replay, probability movies, lock selection, reveal-before-update, frozen/adaptive twins, update ancestry, rollback lineage and normalized outputs.

D4/D5 must use the same engine/movie contract in `CASE_STUDY_NO_ADAPTATION`, not a second execution path.

The fixed POX branch remains explicitly oracle-conditioned/posthoc and permanently non-promotable.

All 21 defects and all 12 pre-launch gates in `FRANKIE_V4_UNIFIED_FRAMEWORK_AUDIT_20260820.md` remain binding unless a later clean-source record explicitly closes one with evidence.

---

## 10. Immutable probability / first-lock ledger

Each every-second prediction must be append-only and hash-bound to:

- instance and snapshot identity;
- source/feature/graph semantics;
- model/head/view identity;
- probabilities/margins;
- lawful evaluation timestamp;
- lock-rule revision;
- first-lock, no-reliable-lock, no-lock, wrong-lock, late and censored states.

First lock must be independently recomputable. A later cleaner call cannot replace an earlier exact signal.

---

## 11. Sealed prediction-to-execution handoff

Execution is downstream from measured exhaustion state.

The execution layer must consume a sealed `signal_id` / `execution_handoff_id` that binds the original model/head/view, probabilities, lock time, state snapshot, provenance and ruleset.

Execution may not:

- re-predict;
- re-time;
- re-fuse;
- substitute a cleaner view/head;
- backdate entry;
- reinterpret future information as if it were known at lock.

Execution research may later ask direction, entry, size, hold, exit, continuation, reversal, abstention and multi-stage management questions, but those are consequences of the measured structural state, not the primary exhaustion labels.

---

## 12. Support and new chronology

Current clean support remains:

- D0: 135,860
- D1: 18,837
- D2: 1,592
- D3: 124
- D4: 8
- D5: 1

D3 becomes thin under fine stratification and D4/D5 remain case-ledger evidence. Additional independent provenance-certified chronology under unchanged frozen detector/canonical rules is the lawful way to seek more deep cases.

Do not relabel previously inspected discovery chronology as fresh OOT. Preserve genuinely untouched future chronology for forward evidence.

Historical MBP-10/trade expansion should precede expensive MBO expansion when the immediate goal is simply to discover whether deeper D chains exist. MBO can then be added as a distinct optional channel/ablation around certified windows.

---

## 13. P0 empirical readiness

Frankie component contracts remain ready but empirical readiness remains blocked until real executed receipts exist for all six required evidence types:

1. untouched held-out paired performance;
2. calibration/selective risk;
3. planted-null contamination;
4. complete protected retention matrix;
5. evaluator-independence canary;
6. non-vacuous byte-exact live rollback.

Synthetic tests, source hashes, caller attestations and unit canaries are not substitutes for these receipts.

---

## 14. Preservation and promotion boundary

No chain/case is removed because it is negative, sparse, losing, late, model-specific, unresolved or inconclusive. Technical failure remains reserved for execution/integrity failure.

This proposal authorizes no permanent Frankie merge, detector/canonical mutation, Phase-1/Phase-2/runway rewrite, `spawn.py` change, play freeze, live trading deployment, or V4 empirical dispatch.

A trusted V4 empirical launch still requires one exact tested candidate commit, engine/adapter/ruleset identities, all pre-launch gates green, and a separate explicit user authorization naming the exact commit/workflow/ruleset.
