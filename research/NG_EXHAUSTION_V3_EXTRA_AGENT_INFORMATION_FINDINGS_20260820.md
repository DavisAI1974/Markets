# NG Exhaustion V3 Extra-Agent Information Findings — 2026-08-20

Status: **DURABLE INTERPRETIVE RESEARCH RECORD FOR V4 HANDOFF. EXTRA-AGENT FINDINGS ARE THE PRIMARY INFORMATIONAL PAYLOAD; V3 NUMERIC OUTPUTS ARE DIAGNOSTIC/PROVENANCE ONLY.**

Branch: `chatgpt/ng-exhaustion-entry-timing-revival-20260818`

## Governing interpretation

The V3 runs contained multiple methodological mistakes and mismatched research questions. Therefore the next session must **not treat V3 point estimates, hit rates, exact PRIOR/T0/H timings, fixed-horizon P&L, directional trade outcomes, or model-specific percentages as authoritative limits on exhaustion behavior**.

Keep those numbers intact for provenance, debugging, and comparison. Do not throw them away. But do not build V4 around them and do not infer that exhaustion lacks information because one of those V3 numbers was weak or negative.

The more important information for V4 came from the independent extra-agent reviews that asked **why the information boundary appeared where it did and what representation/measurement/support/translation was missing**.

A valid negative or inconclusive result is not a failed chain. No chain is dropped. Technical failure is reserved for execution/integrity problems.

## Critical correction: direction is not the primary exhaustion measurement

Exhaustion is fundamentally a **state/structure/lifespan/transition phenomenon**, not a directional label.

Primary exhaustion measurements for V4 should include, as separate heads or clearly separable outputs:

- persistence versus collapse;
- runway / remaining lifespan / exhaustion maturity;
- P/O/S/X structural family;
- continuation versus termination as a structural event;
- eventual chain depth;
- chain-transition geometry and ancestry context;
- recognition/lock timing discovered from the continuous causal movie;
- short-run versus long-run behavior and the path by which the state resolves.

Price direction, predecessor polarity, flow direction, or a with/against trade orientation may be useful **downstream causal context for execution**, but they are not the truth label for whether the exhaustion state was measured correctly.

Do not score V4 exhaustion quality from directional trade P&L.

## Critical correction: V4 does not inherit the V3 seconds grid

V3's PRIOR/T0/H ladder is benchmark provenance only. V4 must not search those buckets as the decision mechanism.

Frankie should consume the continuous causal state and determine when information becomes sufficient under a frozen hindsight-proof lock rule. The lock timestamp is an absolute causal timestamp. Only after the prediction ledger is frozen may it be aligned post hoc to historical birth/onset for reporting.

Therefore the V3 T0/H+1 discrepancy is not a V4 problem to patch. It is evidence that the bucket architecture was the wrong research framing.

## Extra-agent findings carried into V4

### 1. Timing / observability review

The timing reviewer found that apparent timing boundaries can be artifacts of what the V3 scanner chose to expose or test. The V3 trade scanner skipped T0 and moved from PRIOR buckets to H+1, while the core could see information at T0. More broadly, predecessor structural information was often withheld until causal confirmation, leaving overlap cases with raw market evolution but without a structured representation of unresolved predecessor state.

V4 obligation:

- continuous causal scoring rather than fixed PRIOR/T0/H search;
- explicit provenance/missingness masks;
- causal predecessor-resolution / overlap-state representation;
- never leak future predecessor family/polarity, but do represent what is causally knowable about unresolved overlap and the market path during it.

### 2. Feature / representation review

The feature reviewer found that the main issue is unlikely to be simply “missing price,” “missing dipole,” “missing flow,” or “missing book.” V3 already carries dense versions of those measurements. The more plausible gap is **how those measurements are expressed relative to the evolving chain**.

Evidence-seeded V4 hypotheses include:

- explicit predecessor-to-predecessor and predecessor-to-live-state distances;
- relative exhaustion slopes and change-of-slope;
- dipole turning geometry and curvature;
- timing-gap ratios and chain-spacing normalization;
- path-shape similarity;
- cross-link scale normalization;
- ordered ancestry geometry;
- explicit local nonlinear geometry that KNN may have been extracting implicitly;
- separate structural, price/path, flow/dipole, and book encoders or equivalent identifiable ablations.

### 3. Channel-fusion review

The extra agents found cases where a narrower causal channel became informative earlier than FULL_CAUSAL. That means “more causal inputs” is not automatically better if they are fused poorly.

V4 obligation:

- preserve identifiable channel ablations;
- test stage/context-aware fusion or gating against flat concatenation;
- do not allow a combined model to hide that a narrower causal channel carried the earlier usable information;
- preserve independent model extraction lanes rather than forcing cross-model consensus.

### 4. Support / calibration review

The support reviewer found meaningful chronological base-rate and composition shifts, especially at deeper stages. D4 and D5 are particularly sparse. D4's held block contained no positive D4 continuation examples, and D5 remains case-study territory.

V4 obligation:

- separate “not enough independent support” from “no information exists”;
- report stage/class/regime support explicitly;
- test geometry/regime-conditioned calibration rather than pooled global calibration only;
- preserve D4/D5 as case studies and retain every rare continuation;
- more history may help support, but simple pooling is not assumed to solve regime mismatch.

### 5. Trade-translation review

The trade reviewer found that the V3 execution layer can strand useful structural information because it is continuation-gated. A model can have P/O/S/X information while the trade layer refuses to test anything because continuation did not independently validate.

The V3 trade grid also forced a small menu of **direction choices and fixed hold durations**. That architecture should not be mistaken for the measurement of exhaustion itself.

V4/later obligation:

- predictive exhaustion state comes first;
- structural state, lifespan/runway, depth, geometry, and lock timing should be available to downstream execution research;
- trade direction is a downstream consequence/decision, not an exhaustion label;
- do not require continuation as the only gateway to all execution research;
- learn or test entry/exit/hold behavior conditional on the causal structural state rather than forcing all cases into with/against direction plus a fixed seconds grid;
- future target polarity, future endpoint, and future canonical event identity remain forbidden.

### 6. Model-extraction review

Different models extracted different relationships from the same causal observations. This is useful evidence about representation, not a voting contest.

V4 obligation:

- preserve Logistic / ExtraTrees / KNN and any graph/sequence variants as independent evidence lanes;
- use disagreement to locate representation/extraction boundaries;
- do not average probabilities or require 2-of-3 agreement;
- do not treat a model's null result as a chain failure.

### 7. Prediction-to-execution routing seam

A later post-correction trade-gap review isolated a narrower architectural defect than the generic continuation gate. At the pinned V3 implementation, the execution `signal_scan` re-searches only `FULL_CAUSAL`, scans PRIOR checkpoints, and then jumps to POST_BIRTH H checkpoints; it does not consume an immutable predictive-layer ledger carrying the exact source view and validated lock timestamp. This means execution can silently lose information by narrowing or shifting the predictive question before trade research begins.

This is a **research-system diagnosis**, not validation of the underlying V3 signal.

V4/later obligation:

- prediction emits an immutable per-model signal ledger;
- at minimum preserve `{head, causal_view, lock_timestamp, probability/calibration, support, provenance}`;
- execution consumes each validated signal lane independently rather than re-discovering it under a narrower contract;
- source view and lock timestamp are first-class provenance and may not be silently replaced by `FULL_CAUSAL` or another checkpoint;
- only after that seam is tested should orientation, entry, causal exit geometry, or state-conditioned management be evaluated separately;
- favorable MFE/MAE patterns in V3 remain hypothesis seeds only, not proof of an exit edge.

### 8. Inter-event exhaustion survival / resolution-trajectory hypothesis

A later post-correction timing/feature review identified a more specific question than “use continuous timing.” The V3 D0 research architecture samples only a very short fixed set of early root ages even though the unresolved interval after predecessor confirmation can be materially longer. Sparse deeper-stage case material also contains long unresolved intervals. These V3 intervals are diagnostic provenance only, but they expose a mismatch between the observation design and the duration of the process being studied.

The resulting V4 hypothesis is that termination/depth information may be carried in the **evolution of the unresolved exhaustion aftermath itself**, rather than in a few isolated checkpoints immediately after predecessor confirmation.

Candidate causal state to test in V4 includes:

- elapsed time since predecessor confirmation, without any future-target-relative clock;
- unresolved-overlap age;
- continuous exhaustion intensity/decay when causally available from the frozen detector;
- exhaustion slope, change-of-slope and curvature;
- dipole sign-run length, area, slope/curvature, zero-crossing and reversal impulse;
- cumulative signed-flow persistence and reversal magnitude;
- book resilience/replenishment after flow shocks;
- chain-relative inter-link gap and scale ratios;
- a continuously updated transition/termination hazard or resolution probability learned from the evolving trajectory.

V3 nulls do not establish that such information exists or does not exist. V4 must independently test this survival/resolution representation.

### 9. Support / calibration / regime-composition hypothesis

A later post-correction support review found large chronological class-composition changes in some V3 blocks together with model-specific degradation and very sparse deeper-stage/trade samples. Those exact V3 rates and AUCs remain diagnostic provenance, not empirical exhaustion laws. Their legitimate implication is that the V3 evaluation design mixes **support quantity, class/regime composition, calibration and model extraction** in ways that can make a null or degradation ambiguous.

V4 obligation:

- report support and class composition by stage, chronological block and relevant regime;
- distinguish lack of support from calibration/regime mismatch and from representation/model limitation;
- test stage/regime-conditional calibration and conditional grouping;
- use geometric normalization where appropriate rather than assuming pooled calibration transfers;
- add historical weeks especially where they contribute rare minority/tail examples, not merely more abundant D0/D1 rows;
- keep D4/D5 as preserved sparse evidence until enough support exists for population calibration;
- treat thin held-trade counts as execution-sampling uncertainty, not evidence that exhaustion structure lacks information;
- do not infer cross-model truth from shared or divergent V3 outcomes.

## Post-correction review-agent status

The active `Timing Gap Review`, `Feature Gap Review`, `Support Gap Review`, `Trade Gap Review`, `D1 Secondary Review`, and `Markets Run Watch` were intentionally created **after the V3 non-authority problem was already known**. They are diagnostic gap-mining agents, not legacy V3 validators and not mock research runs.

Their purpose is to use the landed V3 artifacts to find research-system defects, omitted state, support/calibration problems, or translation seams that V4 should independently test. Their prompts were later hardened to make the already-intended rule explicit: V3 behavioral outputs remain non-authoritative, every chain/case is preserved, and any behavioral implication is only a V4 hypothesis.

## What to carry forward versus what not to over-weight

Carry forward strongly:

- the gap taxonomy;
- continuous causal lock-time discovery;
- ordered geometric representation;
- predecessor-overlap representation;
- inter-event survival/resolution trajectory as a V4 hypothesis;
- immutable model-specific signal-ledger routing into execution;
- channel-specific encoding/fusion tests;
- stage/regime-conditioned support and calibration;
- independent model extraction;
- structural-state-first trade translation;
- preservation of every chain/case;
- learn-after-reveal adaptive research with immutable past calls.

Carry forward only as low-weight benchmark provenance:

- exact V3 hit rates and point estimates;
- exact V3 PRIOR/T0/H earliest-timing numbers;
- exact V3 AUC/prevalence/calibration values;
- exact directional trade P&L;
- fixed-horizon trade selections;
- any implication that direction is the primary exhaustion target;
- any implication that a V3 null/negative result is a hard boundary on the phenomenon.

## V4 research priority

The next session should start by asking:

> What causal state is Frankie actually seeing, when does that state become trustworthy without target-relative buckets, how is the chain geometry evolving, what unresolved survival/resolution process is underway, what exhaustion state/lifespan transition is forming, and only then what execution consequences follow?

Do not start by trying to reproduce V3 numbers.

## Preservation / authority

This record does not launch V4, modify permanent Frankie, change the frozen detector, alter canonical evidence, or promote a trade/play.

It is an interpretive handoff record. V3 remains preserved as provenance. The extra-agent findings above are the primary informational guide for V4 design and adjudication.
