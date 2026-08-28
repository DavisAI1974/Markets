# Frankie BOSS two-day blind benchmark handoff — 2026-08-28

Repository: `DavisAI1974/Markets`

BOSS branch: `codex/frankie-boss-sol-replacement-20260824`

Pre-handoff BOSS HEAD: `45ce276483ba945880ea370c42b81f75bde99f4d`

Separate Step-1 / Frankie branch observed when this handoff was written:

- branch: `chatgpt/frankie-october-aws-readonly-20260824`
- observed HEAD: `eb369e255e9a38f278beb4462651a0b13ee0dede`

Governing Agent Skills release: `addyosmani/agent-skills` `0.6.7`.

## Controlling reveal rule — user clarification

This rule supersedes any broader wording in the initial handoff commit.

For the first October 4–5 paired benchmark, the reveal sequence is exactly:

1. Run and freeze the Chat-driven Frankie/model lane on the still-blind October 4–5 evidence.
2. **Do not reveal anything after the Chat-driven run.**
3. Keep all October 4–5 outcomes, answers, scored Step-1 findings, and answer-derived discussion sealed.
4. Run and freeze the Granite 4.2 8B lane on the same still-blind October 4–5 evidence under the separately approved interface/runtime contract.
5. Only after both model outputs are frozen may the reveal occur.
6. Reveal once, then score and compare both frozen outputs against the same realized market.

There is no intermediate reveal between the Chat run and the Granite run.

The two model outputs may be compared pre-reveal only after both are frozen, and that comparison must not be fed back into either model for an October 4–5 rerun.

## Purpose

Use the already-expensive corrected two-day full-MBO Step-1 corpus as the first real BOSS semantic/blind benchmark without spending another large Step-1 run and without contaminating the model comparison.

The scientific goal is to maximize information from the same high-fidelity causal evidence while keeping all answer/reveal information sealed through both required model runs.

This handoff is a test protocol and data-handling contract. It does not authorize a new large Step-1 replay, a Granite download/invocation, a Frankie/provider launch, BOSS training, recurrent-depth implementation, or reveal by itself.

## Core decision: preserve October 4–5 as the shared blind benchmark

The authorized two-day diagnostic target window is:

- start: `2021-10-04T00:00:00Z`
- end: `2021-10-06T00:00:00Z` (half-open)

Therefore the primary blind benchmark days are:

- 2021-10-04
- 2021-10-05

The same two calendar days are intentionally reused for the paired model comparison. Calendar-date reuse is not leakage; answer exposure is.

For the first reveal gate, the required pair is:

1. Chat-driven Frankie/model run.
2. Granite 4.2 8B run using the same lawful causal benchmark evidence after the Granite interface/runtime tranche is separately approved.

The exact runtime/model identity for each lane must be recorded from receipts. Do not guess or normalize model names in provenance.

Native BOSS/adaptive-depth/control arms may later be added under their own specs. They do not create permission for an intermediate reveal between Chat and Granite.

## Reveal wall

Keep the reveal sealed through both model runs.

The current Step-1 recovery contract already requires Step-1 findings to remain sealed from the Frankies until the existing reveal boundary. Preserve that wall and extend it to the Granite lane.

Before both required model outputs are locked, neither lane may receive:

- realized post-`as_of` outcomes,
- later price path used as an answer,
- event outcome labels,
- final chain success/failure labels,
- the other model's prediction/reasoning,
- scored Step-1 answer summaries,
- holdout score results,
- human summaries derived from those answers.

Lawful point-in-time Step-1/MBO state may be reused. Answer/reveal material may not.

## Lock-before-reveal rule

1. Chat-driven run receives the lawful October 4–5 causal evidence and runs blind.
2. Persist exact model identity, code SHA, prompt/config identity, causal-prefix hashes, and emitted artifacts.
3. Lock/hash the Chat-driven output.
4. **Do not reveal.**
5. Granite receives the same lawful October 4–5 benchmark evidence while outcomes and the Chat output remain unavailable to it.
6. Persist exact Granite model/checkpoint identity, code SHA, serializer/prompt/config identity, causal-prefix hashes, and emitted artifacts.
7. Lock/hash the Granite output.
8. Once both are locked, a pre-reveal comparison of the two frozen outputs is permitted.
9. Do not feed that comparison back into either lane and rerun October 4–5.
10. Perform one reveal only after both model runs are frozen.

Pre-reveal comparison may examine behavior without outcomes, including:

- exhaustion events noticed/not noticed,
- chain starts/continuations/stops,
- long/short chain structure,
- evidence selected,
- contradictions identified,
- plays fired/stood down,
- confidence/abstention/no-call behavior,
- reasoning differences,
- pairwise agreement/disagreement.

No pre-reveal disagreement is called a failure. Preserve all differences.

## Step-1 source identity already available

The corrected full-MBO wrapper declares raw bootstrap dates:

- `20211001`
- `20211003`
- `20211004`
- `20211005`

The preserved native-seconds stream from the recovery handoff is:

`/mnt/markets/ng_exhaustion_two_day_full_mbo_step1_20260825/32819740234-1/results/V4_NATIVE_FULL_MBO_SECONDS.jsonl.gz`

Recorded identity:

- SHA-256: `899cca3c03d0cd66ba97bbd798b6d000bc3cb12c34d165a6def50b9c6f091b77`
- expected rows: `90,763`

Recorded raw MBO source files:

- `glbx-mdp3-20211001.mbo.dbn.zst` — 25,628,861 bytes
- `glbx-mdp3-20211003.mbo.dbn.zst` — 973,355 bytes
- `glbx-mdp3-20211004.mbo.dbn.zst` — 34,300,424 bytes
- `glbx-mdp3-20211005.mbo.dbn.zst` — 36,192,430 bytes

Before using any Step-1 artifact on the BOSS branch, re-verify the exact source/receipt hashes available at that time. Do not silently substitute a later rebuilt artifact with the same filename.

## How to treat October 1 and October 3

October 1 and October 3 are bootstrap/warmup/development material for this first benchmark. They are not part of the primary October 4–5 blind score.

Use them to establish and validate state/interface behavior, including:

- full-book/bootstrap continuity,
- packet -> typed-state construction,
- serializer round-trip on real market state,
- graph/FIFO ancestry representation,
- QSV/OD field preservation,
- defects/masks/presence handling,
- objective Granite semantic probes after separate model-invocation authorization,
- market-field ablation mechanics.

They may be measured diagnostically. If they are used to choose or tune a serializer, prompt, threshold, teacher target, ablation list, or model setting, they must remain labeled:

`DEVELOPMENT / WARMUP DIAGNOSTIC — NOT HELD OUT`

Do not add October 1/3 to the headline blind score after using them for development.

## How to treat October 4 and October 5

October 4–5 are the first shared blind benchmark.

Do not use these two days to tune the BOSS/Granite interface, prompt wording, field selection, thresholds, halting policy, teacher target list, or model choice after observing their predictions or outcomes.

The prior Step-1 two-day reconciliation adapter contains a user-authorized `self-fit/self-score` diagnostic exception because the 52-week out-of-time split is unavailable for that diagnostic. That exception is historical Step-1 methodology only. It does **not** become the Chat-vs-Granite blind benchmark methodology.

October 4–5 remain evaluation/blind days until both required model runs are frozen and the single reveal occurs.

## Step-1 data handling contract for BOSS / Granite

### Read-only source principle

Treat Step-1 outputs as immutable scientific source artifacts. BOSS/Granite work should consume hash-bound copies or read-only references. Do not mutate Step-1 results in place.

Every derived benchmark artifact must record:

- exact Step-1 branch/commit used,
- exact source artifact path,
- source SHA-256 / receipt identity,
- target date/window,
- BOSS/interface code SHA,
- serializer schema/version,
- extraction/builder version,
- causal-prefix/as-of identity where applicable.

### Causal-prefix principle

Only evidence available by the requested `as_of` may enter a benchmark snapshot.

`ts_recv_ns` remains the causal availability clock. `ts_event_ns` is exchange event time, not availability. `ts_in_delta_ns` is provenance only.

Do not serialize a full-day file wholesale into a prefix if it exposes post-`as_of` information. Build each benchmark state from the lawful prefix.

### Packet-to-typed-state derivation must be proven

The completed serializer proves a closed deterministic representation but does not prove that separately supplied rows/graph/QSV values actually derive from the packet hash accompanying them.

Before result-bearing Granite testing, add a separately specified packet/Step-1 -> typed-state construction seam that proves:

- the typed state is reproducibly derived from the declared source identity,
- no future rows are accessible,
- row order and graph ancestry are preserved,
- QSV registry order/availability is preserved,
- defects/missing state are preserved rather than repaired silently,
- the same source prefix produces the same typed snapshot/hash.

Do not paper over this boundary with hand-built JSON.

### Answer-wall principle

Step-1 outputs may contain both lawful causal evidence and result-bearing/scored findings. The extraction layer must explicitly allowlist lawful state and reject answer-bearing fields.

Do not rely on human discipline alone. Add fail-closed tests that an outcome/answer field cannot cross the extraction boundary.

## Test program — run in this order

### Test 0 — repository-native preservation gate

The state-serializer tranche has focused local receipts but the combined repository-native BOSS preservation suite remains open.

Before a new semantic/result-bearing tranche, run the repository-native suite in an environment that actually contains the repo/dependencies:

- `test_causal_packet.py`
- `test_trunk.py`
- `test_seam.py`
- `test_state_serialization.py`

Record the actual command/environment/result. Do not infer it from historical `101/74/160` receipts.

### Test 1 — Step-1 artifact identity and date partition

Create focused fail-closed tests proving:

1. the source Step-1/native-seconds/raw-MBO identities match the frozen receipt/manifest used for the experiment;
2. the benchmark target is exactly `[2021-10-04T00:00:00Z, 2021-10-06T00:00:00Z)`;
3. October 1/3 are tagged warmup/development and cannot enter the primary score table;
4. October 4/5 are tagged blind benchmark and cannot be used by a development/tuning API;
5. no source file or row outside the declared roster/window is silently substituted.

### Test 2 — causal Step-1 -> typed-state derivation

TDD a small additive builder/extractor. Required tests:

- receive-time visibility only;
- future receive rows excluded even when event time is earlier;
- repeated same-prefix extraction is byte/hash identical;
- source packet/receipt identity bound into snapshot;
- row ordering preserved;
- graph parent/root references preserved;
- QSV names/order/states preserved;
- present zero vs missing vs ablated remain distinct;
- Step-1 defects remain defects;
- outcome/future/answer fields fail closed;
- unknown fields cannot silently pass through.

This builder must not modify Step-1 science or existing BOSS trunk files.

### Test 3 — real warmup serializer validation on October 1/3

Using only development/warmup state, prove the full real-data path:

`hash-bound Step-1 prefix -> typed snapshot -> canonical serializer -> parser -> equivalent snapshot`

Required checks:

- deterministic bytes/hash across repeated builds;
- graph/FIFO relations round-trip;
- QSV registry width/order/mask round-trip;
- real zero/missing/ablated distinctions survive;
- no answer-bearing field is present;
- market-field ablation preserves schema shape and changes only declared value-state markers.

A failure here is an interface/data-boundary finding, not evidence that Granite or BOSS reasoning failed.

### Test 4 — objective Granite probes on warmup only

Only after a separate Granite model-invocation authorization/spec, Granite 4.2 8B should first receive objective, mechanically checkable warmup probes rather than the held-out October 4–5 outcome.

Examples:

- recover a parent/ancestry relation;
- identify a named QSV feature/value/state;
- distinguish present-zero from missing/ablated;
- compare two explicitly named numeric fields;
- identify a declared defect;
- identify evidence conflict/contradiction that is directly encoded in the snapshot.

Do not reveal October 4–5 during or after these warmup probes.

Run the same probes against a market-field-ablated serialization. If performance does not degrade when the relevant market fields are removed, treat that as evidence Granite may be using generic structure/prompt priors rather than reading the market state.

### Test 5 — Chat-driven blind run on October 4/5

Run the Chat-driven Frankie/model lane on the exact lawful October 4–5 benchmark evidence.

Required controls:

- exact date/window;
- lawful causal evidence/prefix policy;
- existing Frankie brain/schema/settings appropriate to that run;
- answer wall still closed;
- exact Chat/provider/model/config identity receipted.

Then:

- freeze the output;
- hash/version it;
- do not reveal;
- do not expose its prediction/reasoning to Granite before Granite is locked.

### Test 6 — Granite blind run on October 4/5

After Granite's serializer/interface and warmup probes are proven and Granite invocation is separately authorized, run Granite 4.2 8B on the same still-blind October 4–5 benchmark evidence.

Required controls:

- no October 4–5 outcome/reveal access;
- no Chat-run output access;
- exact same lawful source/date partition;
- exact Step-1/serializer/prefix identities recorded;
- exact Granite checkpoint/config/prompt identity recorded;
- output frozen and hashed before any reveal.

If Granite is run as an assisted BOSS/Frankie component rather than a direct comparison model, that exact role must be frozen in the pre-run spec. Do not change the role after seeing October 4–5 behavior.

### Test 7 — paired pre-reveal comparison

Once **both** Chat and Granite outputs are locked, compare them without opening outcomes.

Compare:

- exhaustion discoveries,
- event/chain membership,
- chain continuation/stopping behavior,
- evidence selection,
- contradictions,
- confidence/abstention/no-call behavior,
- reasoning structure,
- pairwise agreement/disagreement.

Do not rerun either lane based on this comparison.

### Test 8 — single reveal and scoring

After both required model runs are frozen:

1. open the reveal/outcome material once;
2. score both frozen model outputs against the same realized market;
3. preserve null, negative, contradictory, abstention, and KILL results;
4. do not delete chains/events because they do not support a hypothesis;
5. do not retroactively tune and rescore October 4–5 as if still held out.

Post-reveal comparison includes both:

- Chat-vs-Granite agreement/disagreement;
- each model vs realized outcome.

Any later native-BOSS/adaptive-depth/teacher-distillation experiments using October 4–5 after this reveal must be labeled post-reveal/development, not blind. A future blind BOSS learning-curve claim therefore requires new held-out dates.

## Granite-specific later controls

If Granite later becomes a teacher/assistant rather than merely the second blind comparison model, preserve separate controlled arms:

A. native fixed-depth BOSS baseline;
B. native adaptive-depth/recurrent control if separately implemented;
C. Granite-assisted/teacher arm;
D. shuffled-Granite supervision control;
E. market-specific-field-ablated Granite input control.

Do not collapse mechanism benefit (`adaptive depth helps`) into teacher benefit (`Granite transfer helps`).

Validate Granite's process labels before distillation. Contradiction/evidence-conflict targets should be tested before halt/abstain targets. For any later uncertainty/abstain target, test whether higher Granite uncertainty associates with higher held-out error and whether selective removal of low-confidence cases reduces error.

## Scoring policy

### Primary blind score

Primary benchmark: October 4–5 only, scored only after both Chat and Granite outputs are frozen.

### Warmup score

October 1/3 may have diagnostic metrics, but they are never included in the primary held-out score after they are used for development.

### Two-day sample limitation

Two days are enough for:

- a real-data interface test,
- paired Chat-vs-Granite model-behavior comparison,
- a first blind semantic benchmark,
- discovering catastrophic serializer/reasoner mismatch.

Two days are **not** enough to establish the full sample-efficiency learning-curve claim for Granite-assisted BOSS. Do not claim that Granite reduces required MBO history by a percentage from this benchmark alone.

The later sample-efficiency experiment still requires nested training rungs across more frozen MBO periods, multiple seeds, a permanently time-disjoint holdout, and direct estimation of the horizontal data-efficiency shift with uncertainty intervals.

## Data never to discard

Preserve:

- all detected chains/events,
- positive findings,
- negative findings,
- null findings,
- contradictions,
- model disagreements,
- no-calls/abstentions,
- KILL outcomes,
- warmup diagnostics,
- blind outputs,
- reveal scores.

Do not call a non-confirming result a failed chain merely because it does not support the current hypothesis.

## Explicit no-go actions

Until the two-model reveal gate is satisfied, do not:

- reveal October 4/5 after the Chat-driven run;
- reveal October 4/5 before the Granite output is frozen;
- expose the Chat output to Granite before Granite is locked;
- expose Granite output to Chat before the Chat output is locked;
- use October 4/5 for prompt/interface/threshold tuning and then call them held out;
- inherit the Step-1 self-fit/self-score exception into this blind comparison;
- launch a new large Step-1 run merely for this benchmark;
- rebuild the preserved 90,763-row native-seconds stream unless identity verification fails and a separate recovery decision is made;
- modify Step-1 event definitions, causal clocks, proposal thresholds, retention, feature definitions, or outcome construction to make this easier;
- mutate Step-1 artifacts in place;
- hand-build an unproven packet -> typed-state bridge;
- integrate Granite directly into the BOSS trunk without a separate approved spec;
- change BLD-1, ReFRAG governance, the one shared graph branch, Frankie core/provider seam, or capability registry;
- claim predictive success before the single reveal/scoring step.

## Provenance required for each blind lane

Record at minimum:

- lane id,
- branch and exact code commit,
- exact model/checkpoint/provider identity,
- source Step-1 branch/commit,
- source artifact hashes/receipt ids,
- date/window,
- causal-prefix hash(es),
- serializer schema/hash where used,
- prompt/config identity where used,
- seed/sampling settings,
- start/end execution receipt,
- frozen output hash,
- explicit statement that reveal was sealed when the output was produced.

The reveal artifact must separately record the timestamp/commit at which the answer wall was opened and confirm both required output hashes existed beforehand.

## Immediate next-chat order

1. Read this handoff and the existing BOSS handoff/provenance/spec files.
2. Verify current BOSS remote HEAD and current Step-1 branch/artifact identities.
3. Run the open repository-native BOSS preservation suite if a proper repo environment is available.
4. Keep October 4/5 sealed.
5. Let the Chat-driven Frankie/model run complete and lock independently under its existing experiment contract.
6. **Do not reveal after the Chat run.**
7. Continue BOSS brownfield context/spec work for the Step-1 -> typed-state derivation boundary.
8. Use October 1/3 for real-data semantic/interface development and Granite warmup probes.
9. Once the Granite interface is proven and invocation is separately authorized, run Granite on the same still-sealed October 4/5 benchmark.
10. Lock/hash Granite output.
11. Optionally compare the two frozen outputs pre-reveal without feeding results back.
12. Reveal once after both model outputs are locked.
13. Score and preserve all results.

## Status at corrected handoff

- BOSS serializer mechanical tranche exists and is focused-GREEN (20/20 local serializer tests after hardening).
- Repository-native combined preservation suite remains explicitly open until actually rerun.
- Granite remains unadopted and uninvoked at this checkpoint.
- No BOSS result-bearing real-data run has occurred.
- No new Step-1 compute was launched by this handoff.
- October 4/5 reveal is explicitly sealed through the Chat run and the Granite run.
- The first reveal occurs only after both model outputs are frozen.
