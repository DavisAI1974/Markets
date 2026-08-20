# NG Exhaustion V4 — Research Thread / Data-Gap Handoff — 2026-08-20

Status: **ACTIVE V4 RESEARCH THREAD; EVIDENCE-SEEDED DESIGN/HANDOFF ONLY; V4 IS NOT LAUNCHED BY THIS DOCUMENT.**

Branch:

`chatgpt/ng-exhaustion-entry-timing-revival-20260818`

V3 evidence pin:

`3dc22b341dd4136b1be16c014e48feb70ee544d6`

Primary live evidence runs:

- V3-T0 pinned core: `32359639305`
- D0-D3 model-specific fixed-horizon trade: `32359639396`

This thread starts from the current V3 evidence and asks a different question from pass/fail adjudication:

> **What is the data telling us is visible, missing, too coarsely represented, too weakly supported, model-specific, or not yet translated into a trade?**

No negative, weak or inconclusive research result is a failed chain. No chain is dropped because it did not produce the desired answer. Only execution/integrity problems may be called technical failures.

---

## 1. Frozen research universe remains intact

Do not renumber, merge, delete, prune or reinterpret the frozen depth groups:

- D0 = 135,860
- D1 = 18,837
- D2 = 1,592
- D3 = 124
- D4 = 8
- D5 = 1

Standing policy:

`FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`

D4/D5 remain preserved low-support case studies. Their rarity is itself evidence; it is not permission to discard them or generalize from them as if they were population-sized lanes.

---

## 2. Interpretation doctrine for V4

Every V3/V4 outcome belongs to one or more of these evidence classes:

1. **positive predictive information** — a causal relation independently survives the required validation blocks;
2. **negative observation** — the tested representation/model/checkpoint does not independently support the target;
3. **inconclusive / support-limited observation** — the available sample or chronology is insufficient for a population claim;
4. **information-boundary observation** — the answer becomes visible only later, only through a narrower causal channel, or only to some model class;
5. **trade-translation observation** — predictive information exists but the current execution translator cannot or should not act on it;
6. **technical failure** — reserved for job/runtime/invariant/artifact/pin/leakage problems.

The first five are research evidence. None removes a chain from the research universe.

---

## 3. Current V3 evidence snapshot

Snapshot date: 2026-08-20. Both live workflows remain pinned to the exact evidence commit above.

### D0

Core Logistic / ExtraTrees / KNN remain in progress at this snapshot.

Completed trade observations:

- KNN: `BLOCKED_NO_INDEPENDENTLY_VALIDATED_CONTINUATION_SIGNAL`.
- ExtraTrees: `BLOCKED_NO_INDEPENDENTLY_VALIDATED_CONTINUATION_SIGNAL`.
- Logistic trade remains in progress.

These are not D0 verdicts because the matching KNN/ExtraTrees core lanes have not yet completed. They say only that the current model-specific trade translator did not receive an independently validated continuation signal from its own historical scan.

### D1

All three core lanes remain in progress.

Completed trade observations:

- KNN: causal trade signal at `H+1`; tested fixed-horizon candidate did not independently validate historically.
- ExtraTrees: causal trade signal at `H+1`; tested fixed-horizon candidate did not independently validate historically.
- Logistic trade remains in progress.

These observations preserve the H+1 timing information even though the tested execution translation did not validate.

### D2 — strongest landed V3 structure so far

#### KNN core

- continuation: `BIRTH_T0`, FULL_CAUSAL;
- eventual depth: no independently validated earliest timing;
- P/O/S/X structural family: `PRIOR age 0`, FULL_CAUSAL;
- P/O/S/X also independently validates in the NO_PRICE_CAUSAL slice at that PRIOR checkpoint;
- PRICE_POLARITY_ONLY does not independently establish the structural-family result.

Critical clock meaning: `PRIOR age 0` is the instant all required predecessor events are causally confirmed while still strictly before target birth. It is **not** “zero seconds before birth.” Actual lead to birth varies by case.

KNN trade remains in progress.

#### ExtraTrees core

- continuation: `BIRTH_T0`, FULL_CAUSAL;
- eventual depth: `BIRTH_T0`, FULL_CAUSAL;
- P/O/S/X structural family: `PRIOR age 0`, FULL_CAUSAL.

ExtraTrees trade remains in progress.

#### Logistic core + trade

- continuation: no independently validated earliest timing;
- eventual depth: no independently validated earliest timing;
- P/O/S/X structural family: `BIRTH_T0`, FULL_CAUSAL;
- matching trade: `BLOCKED_NO_INDEPENDENTLY_VALIDATED_CONTINUATION_SIGNAL`.

This is the first clean like-for-like example of a **trade-translation boundary**: structural-family information exists for the model, but the current trade translator is continuation-gated and therefore has no authorized path to test whether that structural information should condition an execution candidate.

### D3 — model extraction / representation divergence

#### Logistic core

- continuation: no independently validated earliest timing;
- eventual depth: no independently validated earliest timing;
- P/O/S/X: no independently validated earliest timing in the primary FULL_CAUSAL ladder.

#### ExtraTrees core

- primary FULL_CAUSAL earliest timings are null for continuation, eventual depth and P/O/S/X;
- however, `PRICE_POLARITY_ONLY` independently validates some continuation/depth checkpoints inside the tested ladder.

#### KNN core

- continuation: `PRIOR age 0`, FULL_CAUSAL;
- eventual depth: `PRIOR age 1`, FULL_CAUSAL;
- P/O/S/X structural family: `H+4`, FULL_CAUSAL, provisional under the V3 hierarchy;
- NO_PRICE_CAUSAL sees P/O/S/X earlier, including `PRIOR age 3`, T0 and H+1 through H+4;
- NO_PRICE_CAUSAL also independently validates KNN continuation at PRIOR age 0 and eventual depth at PRIOR ages 0 and 1.

The same D3 observations therefore yield very different information boundaries by model and channel. That is evidence to investigate representation/fusion and nonlinear geometric extraction, not a reason to vote models against one another.

D3 model-specific trade lanes remain in progress at this snapshot.

### D4 / D5

D4 remains in progress and case-study only.

D5 completed as a sparse case study with no population earliest-timing declaration. The artifact contains 9 total cases: 5 discovery, 2 validation, 2 confirmation, no held cases; 8 terminate at depth 4 and 1 continues to depth 5. Eight of nine have an eligible PRIOR-age-0 observation and all nine have an eligible T0 observation. Preserve all nine; the current support is insufficient for a generalized D5 timing or predictive law.

---

## 4. What the landed data is currently saying

### A. Structural family can be visible before continuation certainty

D2 KNN and ExtraTrees both expose P/O/S/X before target birth while continuation itself is not trusted until T0. D2 Logistic sees P/O/S/X at T0 even though it never independently validates continuation/depth in the V3 ladder.

Research implication: P/O/S/X is an independent information channel/head. V4 must not subordinate structural-state learning to a continuation gate.

### B. Richer input is not automatically better if fusion is wrong

D3 KNN sees structural-family information earlier in NO_PRICE_CAUSAL than in FULL_CAUSAL. D3 ExtraTrees shows the complementary warning that narrower price/polarity information can validate some continuation/depth checkpoints while the primary combined FULL_CAUSAL representation does not.

Research implication: V4 should test **channel-specific normalization and stage/checkpoint-aware fusion/gating** rather than assuming flat concatenation of more causal features always improves extraction.

### C. Nonlinear local geometry may already be present but implicit

KNN extracts D3 continuation and depth before birth while Logistic and ExtraTrees do not under their primary FULL_CAUSAL results. Because the underlying observations are shared, at least part of the information may already exist in the V3 surface but be expressed in a geometry that some models cannot extract efficiently.

Research implication: explicitly represent predecessor-to-predecessor and predecessor-to-live-market geometry: relative gaps, normalized exhaustion trajectories, local slopes/curvature, dipole turning geometry, path-shape similarity, cross-link scale ratios and ordered ancestry.

### D. Support/regime shift must be separated from absence of information

D3 has far fewer continuation examples than D2. Sparse deeper stages and block-to-block base-rate/composition changes can damage global calibration even where discrimination exists in some blocks/models.

Research implication: V4 must report stage/class/regime support and calibration separately, and test geometry/regime-conditioned normalization rather than relying only on pooled probabilities. More history may improve support, but simply pooling more observations is not assumed to solve regime mismatch.

### E. Prediction and trade translation are different layers

The D2 Logistic pair shows that the current V3 trade translator can strand useful P/O/S/X information because it first requires a validated continuation signal.

Research implication: later trade research should preserve the existing continuation-driven path while testing a **separate structural-state-conditioned translation path**. That research must remain causal and model-specific; it must not use realized target polarity or future canonical events.

---

## 5. V4 data-gap taxonomy

Every proposed V4 improvement must identify which gap it is trying to test:

- `MISSING_MEASUREMENT` — information is not represented at all;
- `COARSE_OR_WRONG_ENCODING` — measurement exists but representation loses useful geometry/scale/context;
- `TIMING_OR_OBSERVABILITY_BOUNDARY` — information exists, but not yet at the tested causal time;
- `SUPPORT_OR_CALIBRATION_GAP` — examples/regime balance are insufficient or nonstationary;
- `MODEL_EXTRACTION_GAP` — information exists in the same observations but a particular model cannot recover it;
- `CHANNEL_FUSION_GAP` — combining causal channels degrades extraction relative to one or more narrower views;
- `TRADE_TRANSLATION_GAP` — predictive state exists but execution architecture cannot yet use it causally.

Do not label a gap merely because a desired result did not appear. Each gap hypothesis must be tied to observed model/channel/timing/support evidence and then tested independently.

---

## 6. V4 research threads

### Thread 1 — continuous per-instance timing

Score every causal second in the natural opportunity window. Timing is an output, not a hard-coded PRIOR/H grid. Preserve the hindsight-proof frozen lock rule and only align to retrospective target T0 after the decision ledger is frozen.

### Thread 2 — ordered geometric chain state

Build the additive `V4_GEOMETRIC_CAUSAL_STATE` over the complete raw + V3 causal state. Preserve chain order. Test relative time, scale/translation normalization, polarity transformation, cross-link distances, trajectory curvature and lawful microstructure perturbations without moving information earlier in time.

### Thread 3 — channel-specific encoding and fusion

Encode structural ancestry, price/path, signed flow/dipole and book state as identifiable causal channels. Test late/gated/attention-style or similarly explicit fusion against flat concatenation. Preserve ablations so a combined model cannot hide the fact that a narrower causal channel carried the earlier signal.

### Thread 4 — geometry/regime-conditioned calibration

Measure continuation/depth/family calibration by stage, chain geometry, lifespan/spacing family, ancestry context, session/contract context and other causally available regimes. Keep class/stage metrics visible so D0/D1 volume cannot hide D2/D3 degradation.

### Thread 5 — model-extraction ablations

Keep Logistic, ExtraTrees, KNN and any V4 graph/sequence models as independent evidence lanes. No majority vote. Use disagreements to locate which geometric/channel representation each model can or cannot extract.

### Thread 6 — adaptive learn-after-reveal

Maintain frozen and adaptive twins. The adaptive lane may learn only after conservative truth reveal, may never rewrite an active/past call, and must pass chronological parent-vs-candidate retention/leakage/calibration/latency gates before an update can enter the later research lineage.

### Thread 7 — structural-state trade translation

After predictive timing is independently established, test whether P/O/S/X, continuation, depth and live causal market state should feed separate or jointly conditioned execution translators. Do not force P/O/S/X through a continuation prerequisite by construction. Keep all trade paths causal and fixed-horizon or otherwise predeclared; future target identity/endpoint remains forbidden.

### Thread 8 — sparse-stage preservation

D4/D5 remain diagnostic/case-study lanes. Use them to generate questions and candidate self-edit packets, not universal laws. Any D4/D5-motivated shared update must first survive the full D0-D3 retention and chronological evaluation suite.

---

## 7. Required V4 evidence outputs

For every stage/model/head, preserve:

- full causal probability movie;
- frozen lock/no-lock ledger;
- posthoc decision timing coordinate;
- FULL_CAUSAL and predeclared channel ablations;
- support/class/regime counts;
- Brier/log-loss/calibration/discrimination/coverage/wrong-lock/no-lock metrics;
- model/channel disagreements;
- geometric ablation results;
- every negative, inconclusive, censored, losing and low-support case;
- self-edit proposals and rejected updates with reasons;
- exact parent/candidate provenance and rollback pointer;
- model-specific trade translation results when authorized downstream.

---

## 8. Pending V3 evidence before the baseline is complete

At this snapshot, still pending include:

- D0 core: Logistic / ExtraTrees / KNN;
- D1 core: Logistic / ExtraTrees / KNN;
- D4 case study;
- D0 Logistic trade;
- D1 Logistic trade;
- D2 KNN trade;
- D2 ExtraTrees trade;
- D3 Logistic / KNN / ExtraTrees trade.

Any newly landed result is appended to the evidence story. It does not erase or drop an earlier chain/model observation.

---

## 9. Protected boundaries / authorization

This research thread **does authorize** documentation work requested on 2026-08-20: inspect the current V3 evidence needed for the handoff, update/create research documentation, and commit/push those documentation changes to the current branch.

It does **not** authorize:

- launching V4;
- rerunning/canceling the current V3 jobs;
- changing V3/V4 research code as part of this documentation commit;
- modifying frozen detector/canonical/Phase-1/Phase-2/runway evidence;
- modifying permanent Frankie or Frankie 1;
- modifying `research/kalshi/spawn.py`;
- promoting a trade/play;
- converting a V3 observation into permanent brain truth.

V4 launch remains a separate explicit decision.

---

## 10. Durable handoff rule

Read this thread together with:

1. `research/NG_EXHAUSTION_V3_V4_CHAT_DECISIONS_ALL_NOTES_20260820.md`
2. `research/NG_EXHAUSTION_V3_V4_BRAIN_TRADE_PROPOSAL_ADDENDUM_20260820.md`
3. `research/NG_EXHAUSTION_D0_D5_V4_GEOMETRIC_SELF_ADAPTATION_CONTRACT_20260820.md`
4. `research/NG_EXHAUSTION_D0_D5_V4_GEOMETRIC_SELF_ADAPTATION_CONTRACT_20260820.json`
5. `research/NG_EXHAUSTION_V4_CONTINUOUS_ADAPTIVE_WALKFORWARD_CONTRACT_20260820.md`

Current branch state plus these records are the V4 research-thread truth. Preserve the complete research universe and let the data keep telling the story.
