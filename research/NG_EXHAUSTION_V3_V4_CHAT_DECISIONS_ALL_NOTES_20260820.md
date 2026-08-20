# NG Exhaustion V3/V4 — All Chat Decisions and Corrections — 2026-08-20

Status: **DURABLE CONVERSATION DECISION RECORD. CURRENT BRANCH STATE + THIS FILE ARE THE HANDOFF TRUTH.**

Branch:

`chatgpt/ng-exhaustion-entry-timing-revival-20260818`

This file preserves the substantive decisions made during the chain-birth/depth/type recovery conversation so future work does not have to infer them from intermediate runners, stale proposal files, or partially superseded workflows.

Nothing in this record authorizes a permanent Frankie merge or live-play promotion.

---

## 1. Frozen/protected boundaries remain unchanged

Do not modify, retune, reopen, or rewrite:

- frozen exhaustion detector;
- frozen canonical base/held evidence and rows;
- frozen Phase-1 lineage/scores;
- finalized Phase-2 findings;
- frozen exhaustion runway clock;
- permanent Frankie;
- Frankie 1;
- `research/kalshi/spawn.py`;
- frozen SSOS play.

Preserve every valid positive, false, losing, censored, low-support and model-disagreement case.

Standing policy:

`FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`

The mandatory historical all-agent Phase-2 record remains:

`research/NG_EXHAUSTION_CHAIN_PHASE2_ALL_AGENT_FINDINGS_20260818.md`

Do not re-litigate settled Phase-2 findings merely because later predictive research uses a richer causal information surface.

---

## 2. Frozen exact chain-depth groups

Do not renumber, merge, delete or reinterpret these groups:

- D0 = 135,860
- D1 = 18,837
- D2 = 1,592
- D3 = 124
- D4 = 8
- D5 = 1

D0 versus D1+ is chain/no-chain at the root boundary.

D4/D5 remain low-support case-study territory. Do not force a universal law from current support.

---

## 3. Primary prediction questions

The recovery questions are separate and must remain separately scored:

1. Will this exhaustion become/continue as a chain?
2. What final depth will the chain reach?
3. What P/O/S/X structural family/state is the next chain link becoming?
4. At what earliest causal time can each answer be trusted?

P/O/S/X definitions remain the frozen grammar:

- P = `persistent_exhaustion`
- O = `collapsed_opposite_flow_reversal`
- S = `collapsed_same_flow_reload`
- X = `collapsed_sparse_indeterminate`

Target polarity is **not** one of these primary prediction questions.

SAME/FLIP remains secondary annotation/context. It may be useful later for structural interpretation or trade research, but a model does not fail the primary chain-family question merely because it did not predict target polarity.

---

## 4. Full-causal information doctrine

The recovery must use all represented information once that information is genuinely causally available.

The correct rule is:

> **Use every represented fact when it becomes causally known; block only hindsight/future information.**

This supersedes the old narrow characteristics wall for this recovery line.

The market itself is observable continuously. At every causal second the model may see the then-known:

- raw price direction;
- recent price velocity/range/path;
- signed aggressor flow;
- rolling flow imbalance / dipole direction and shape;
- live book imbalance and change/path;
- causal clock/session context;
- all predecessor/root information already genuinely known.

Unknown future target polarity must never suppress these live observations or make a PRIOR ineligible.

---

## 5. Continuous live market correction

An important correction in this conversation was that the recovery should not wait for an event label before observing direction.

The V3 live checkpoint surface therefore includes:

- dense causal one-second price history;
- dense 61-second roll-20/dipole history;
- multiple signed-flow windows;
- recent book-imbalance history;
- price velocity/range;
- causal time/session state;
- remembered predecessor/root structural information.

Current live-state module:

`research/ng_exhaustion_live_checkpoint_state_20260819.py`

The market movie is always causal. A frozen future target label is not.

---

## 6. Event-specific label availability remains a separate open clock

Three timestamps must never be conflated:

1. retrospective frozen event birth/onset `t0`;
2. the upstream protected detector's actual live mark/discovery time;
3. later structural endpoint / `dynamic_endpoint.causal_confirmation_idx`.

The live runway adapter explicitly says it is not the event detector. It can derive event polarity and pre-family from the causal tape once an upstream event has been marked, but the exact live mark-time contract has not yet been proven in this recovery.

The durable boundary record is:

`research/NG_EXHAUSTION_EVENT_MARK_CLOCK_OPEN_BOUNDARY_20260819.md`

Do not solve this by inventing a detector timestamp or retuning the protected detector.

Raw market direction/flow/book remains observable regardless.

---

## 7. V3 fixed-checkpoint baseline — current authoritative launch target

V3 remains useful as the fixed-checkpoint benchmark and is the immediate agent priority.

Current V3 revision:

`V3_CONTINUOUS_LIVE_MARKET_STATE_T0`

Current timing ladder for D1-D5:

`PRIOR -> T0 -> H+1 -> H+2 -> H+3 -> H+4 -> H+5`

`T0` was added explicitly during this conversation. It is the frozen target birth second and is deliberately not called H=0.

For D0, do not invent a descendant H clock. D0 remains rooted in its root/candidate-relative timing semantics.

Important V3 hierarchy note:

- a valid pre-birth PRIOR always outranks T0/H chronologically;
- T0/H first-band results are provisional if later pre-birth PRIOR has not been exhausted;
- V3 is now primarily a benchmark because V4 removes the hard-coded timing grid entirely.

Current V3 core files include:

- `research/ng_exhaustion_chain_recovery_features_v3_20260819.py`
- `research/ng_exhaustion_chain_recovery_models_v3_20260819.py`
- `research/ng_exhaustion_chain_birth_depth_type_recovery_v3_20260819.py`
- `research/ng_exhaustion_d0_full_causal_recovery_v3_20260819.py`

The old unified V3 workflow is not the preferred launch path because its contract predated the T0 revision.

A new exact-commit-pinned workflow was therefore created:

`.github/workflows/ng_exhaustion_v3_t0_pinned_core_20260820.yml`

It checks out `${{ github.sha }}` so the agent run cannot silently change underneath an in-flight workflow when later branch commits occur.

The pinned workflow runs 14 lanes:

- D0: Logistic / ExtraTrees / KNN;
- D1: Logistic / ExtraTrees / KNN;
- D2: Logistic / ExtraTrees / KNN;
- D3: Logistic / ExtraTrees / KNN;
- D4 case study;
- D5 case study.

No cross-model vote or probability aggregation is allowed.

The V3 pinned core launch marker is intentionally created **after** this documentation checkpoint so the pinned launch commit contains the full final chat notes/handoff state.

---

## 8. V3 model doctrine

Logistic, ExtraTrees and KNN are independent evidence lanes.

Do not:

- require 2-of-3 agreement;
- median their probabilities;
- erase disagreement;
- reject a valid independent OOT result merely because another model does not validate the same relation.

Preserve independent earliest timing, positive findings, negative findings, inconclusive findings and disagreements model by model and target by target.

---

## 9. V3 primary family target correction

Earlier recovery code used combined labels such as `P|S` or `O|F` as the primary chain-type target. That improperly bundled structural state with polarity transition.

Current primary type target is P/O/S/X only.

SAME/FLIP remains secondary annotation and cannot cause a PRIOR or type prediction to fail.

Known predecessor polarity may still be a causal input once known. Target polarity may become a causal input only when genuinely known. Neither changes the primary target definition.

---

## 10. V3 root/complement ablation doctrine

The following comparisons are useful but are not model votes:

- direct D0 versus matched `1 - D1` is a calibration/implementation cross-check only;
- D2/D3 root-retained versus root-ablated measures whether root memory still adds information at deeper stages;
- FULL_CAUSAL versus NO_PRICE_CAUSAL measures incremental price value;
- FULL_CAUSAL versus PRICE_POLARITY_ONLY measures incremental structural/microstructure value.

When root is ablated, the live market state must remain identical on both sides. Only root information is removed.

T0 belongs in matched D2/D3 root-ablation comparisons as well as PRIOR/H.

---

## 11. Trade-research correction

A serious hindsight issue was caught in an older D0 trade prototype: it capped the exit at the next canonical exhaustion. That future event is not known at entry and therefore cannot choose/cap a causal exit.

Authoritative trade doctrine for this line is now:

- each model reproduces its own independently validated causal signal;
- no probability aggregation;
- direction comes only from causal predecessor/live market information;
- realized target polarity is forbidden as a direction source;
- exits use fixed discovery-selected horizons;
- future target birth / next canonical exhaustion / future endpoint may never choose or cap the exit;
- preserve cost stresses, MFE, MAE, path efficiency and week stability;
- post-birth historical timing does not automatically mean live-executable timing until the upstream event-mark clock is proven.

Corrected trade research files include:

- `research/ng_exhaustion_d0_d3_model_specific_trade_v3_20260819.py`
- `research/ng_exhaustion_d0_d3_model_specific_trade_v3_hierarchy_20260820.py`

Older next-event-capped trade output, if it appears, is comparison/provenance only and must never be promoted as authoritative execution evidence.

---

## 12. Why V4 was introduced

The largest methodological correction in this conversation came after adding T0.

The fixed V3 timing ladder is useful as a benchmark, but the research question should not be constrained by timing values chosen in advance.

The user-directed V4 principle is:

> **Do not hard-code PRIOR or H values. Let the instance/model discover when information becomes sufficient, then report the timing afterward.**

Time therefore becomes an output rather than a predeclared research grid.

V4 should score the natural causal trajectory second by second without giving the primary model:

- target `t0`;
- seconds until birth;
- PRIOR/H identity;
- target polarity;
- target P/O/S/X answer;
- target-relative price anchor;
- censor countdown.

Only after a prediction/lock timestamp is frozen should the historical timestamp be aligned to the frozen target birth and reported as:

- `N seconds PRIOR`;
- `T0`;
- `H+N` for a true continuation;
- control-candidate-relative timing for stopped controls;
- candidate-relative timing for D0, which has no true descendant H clock.

Current V4 surface:

`research/ng_exhaustion_continuous_instance_features_20260820.py`

Current revision:

`V4_CONTINUOUS_PER_INSTANCE_TIMING`

V4 is **code/research-design only in this chat and must not be launched here**. A new chat will intentionally review/complete and launch it later.

---

## 13. Hindsight-proof lock rule

A historical instance cannot be declared to have locked at the first second where the eventual answer happens to be retrospectively correct.

Instead:

1. the model emits a causal probability vector each second;
2. discovery data selects a trustworthy lock rule;
3. the lock rule contains a confidence threshold, winning-class margin and persistence requirement;
4. that rule freezes before OOT;
5. OOT locks when the same predicted class satisfies the frozen rule for the required consecutive seconds;
6. the operational decision timestamp is the second when persistence has actually been observed; it is not backdated;
7. correctness is revealed/scored only afterward.

This allows timing to be discovered without outcome leakage.

---

## 14. Training from what each completed instance actually looked like

Another explicit user correction was that the system should improve from the actual realized instance after that instance has completed.

The intended adaptive sequence is:

`predict -> freeze call -> reveal completed instance -> diagnose/train -> improve next instance`

Past predictions are immutable.

Once an instance is causally complete/revealable, its actual trajectory may train future model state, including relationships involving:

- continuation;
- final depth;
- P/O/S/X state/family;
- price/flow/dipole/book evolution;
- root/ancestry relevance;
- recognition timing;
- short/long lifespan context;
- eventual downstream trade management research.

The system is allowed to learn from experience, but never to rewrite the call it already made on that experience.

---

## 15. Frozen benchmark versus adaptive walk-forward

V4 should preserve two separate views:

### Frozen benchmark

- train on discovery;
- freeze model and lock rule;
- never learn from OOT outcomes;
- answers whether the discovered relation generalizes without adaptation.

### Adaptive walk-forward

- starts as an exact discovery twin;
- uses the same frozen lock rule in the first adaptive study;
- creates each new-instance model snapshot from only earlier completed/revealable cases;
- freezes that instance's call/timing;
- learns from it only after it becomes causally revealable;
- uses the improved model only on later instance snapshots.

Overlapping instances are handled conservatively in the initial V4 design: an active instance keeps the model snapshot it had at start. A newly completed overlapping case does not update that active instance midstream. This intentionally understates adaptation rather than risking overlap hindsight.

Durable adaptive contract:

`research/NG_EXHAUSTION_V4_CONTINUOUS_ADAPTIVE_WALKFORWARD_CONTRACT_20260820.md`

The adaptive held result is an operational chronological walk-forward result, not a conventional untouched holdout. The frozen lane retains the conventional untouched benchmark.

---

## 16. Operational timing after research

The purpose of discovering per-instance timing is not to force permanent Frankie to rediscover timing forever.

Once V4 produces stable, validated timing/context distributions, a later deliberate proposal may convert them into fixed operational timing rules or context-specific timing maps for Frankie.

For example, different stage/family/context conditions may justify different expected recognition windows. Those values must be learned from the research rather than hard-coded before it.

No such timing map is promoted in this chat because the V4 experiment has not run yet.

---

## 17. Future Frankie enhancement explicitly deferred

During this conversation the user noted there may be an additional Frankie capability that would help this learning/timing architecture.

That enhancement is deliberately **out of scope here**.

Do not guess what it is, implement it, or let it delay V3.

The future enhancement can be evaluated after V3 is durable and V4 is ready to launch.

---

## 18. Proposal/synthesis supersession

Historical proposal/synthesis files remain provenance and are not deleted.

Important historical files include:

- `research/NG_EXHAUSTION_V3_FINAL_SYNTHESIS_CONTRACT_20260819.md`
- `research/ng_exhaustion_v3_final_synthesis_20260819.py`
- `research/kalshi/knowledge/ng_brain_exhaustion_chain_birth_v2_proposal_20260819.json`

They predate some of the final conversation corrections, especially:

- explicit T0;
- V4 no-fixed-grid timing;
- adaptive learn-after-reveal architecture.

Use the 2026-08-20 proposal addendum/handoff as the current interpretation. Do not rewrite historical proposal artifacts to pretend they always contained the later doctrine.

---

## 19. Immediate priority after this documentation checkpoint

1. Create the final pinned V3-T0 launch marker **last**.
2. Let `.github/workflows/ng_exhaustion_v3_t0_pinned_core_20260820.yml` execute the exact launch commit.
3. Monitor for its durable reconciliation.
4. If it has a technical failure, patch only active V3 runner/workflow infrastructure and retrigger; do not touch protected artifacts.
5. When results land, report every model/target independently, including positive, negative, inconclusive and unresolved cases.
6. Do not launch V4 in this chat.
7. Do not add the deferred Frankie enhancement in this chat.

After V3 core is durable, later work may run corrected/pinned V3 root/complement/trade follow-ups as needed, then a new chat may review/complete and intentionally launch V4.

---

## 20. Bottom line

V3 is the immediate fixed-checkpoint benchmark that must run now.

V4 is the next methodological step: causal second-by-second per-instance timing discovery plus a frozen benchmark and adaptive learn-after-reveal walk-forward.

Permanent Frankie remains untouched. Phase-2 history remains intact. Every true/false/losing/censored/low-support case remains evidence.

---

## 21. Later user decision — apply the Frankie enhancement to D-series V4

After the earlier deferral, the user supplied and approved the following research direction for D0-D5 V4:

- geometric/structured causal representation over the complete raw + V3 market state;
- post-reveal self-edit proposals inspired by self-adapting model research;
- sandboxed, reversible candidate updates;
- chronological parent-vs-candidate evaluation with retention, leakage, calibration, stage/class and latency gates;
- immutable active-instance snapshots and prediction ledgers;
- no permanent Frankie mutation or live promotion.

This later decision supersedes sections 17 and 19 only with respect to **D-series V4 design/implementation scope**. It did not by itself authorize a V4 launch, result inspection, permanent Frankie merge, play promotion, commit, push, or protected-artifact change.

Binding contract:

`research/NG_EXHAUSTION_D0_D5_V4_GEOMETRIC_SELF_ADAPTATION_CONTRACT_20260820.md`

---

## 22. Later interpretation correction — there are no research “failed chains”

The user explicitly clarified that a test which does not return the hoped-for answer is not a failed chain and must never be used to shrink the research universe.

Current binding interpretation:

- positive result = evidence;
- negative result = evidence;
- weak/inconclusive result = evidence;
- model disagreement = evidence;
- low-support case = evidence;
- technical failure = reserved only for execution/integrity problems such as job failure, timeout, invariant violation, corrupt/missing artifact, pin mismatch or leakage.

Every original chain/case remains in the research universe. The working assumption is that a negative/inconclusive lane may be one missing measurement, representation, timing boundary, support condition, model extraction issue or trade-translation step away from becoming informative.

Do not use “drop,” “failed chain,” or similar pruning language for valid research outcomes.

---

## 23. Pinned V3 evidence now seeding V4 research

Both active V3 workflows remain pinned to:

`3dc22b341dd4136b1be16c014e48feb70ee544d6`

The following completed results are now durable **model-specific V3 observations**, not cross-model votes and not permanent Frankie truth.

### D2

**KNN core**

- continuation: T0, FULL_CAUSAL;
- eventual depth: no independently validated earliest timing;
- P/O/S/X: PRIOR age 0, FULL_CAUSAL;
- P/O/S/X also independently validates at PRIOR age 0 in NO_PRICE_CAUSAL.

**ExtraTrees core**

- continuation: T0, FULL_CAUSAL;
- eventual depth: T0, FULL_CAUSAL;
- P/O/S/X: PRIOR age 0, FULL_CAUSAL.

**Logistic core/trade**

- continuation: no independently validated earliest timing;
- eventual depth: no independently validated earliest timing;
- P/O/S/X: T0, FULL_CAUSAL;
- matching trade blocks with `BLOCKED_NO_INDEPENDENTLY_VALIDATED_CONTINUATION_SIGNAL`.

The Logistic pair exposes a trade-translation boundary: the predictive layer can contain P/O/S/X information even when the current continuation-gated translator has no path to test it.

Critical timing meaning: PRIOR age 0 is the first instant after all required predecessor information is causally confirmed while still strictly before target birth. It is not “zero seconds before birth.”

### D3

**Logistic core**

- no primary FULL_CAUSAL earliest timing for continuation, eventual depth or P/O/S/X.

**ExtraTrees core**

- no primary FULL_CAUSAL earliest timing for continuation, eventual depth or P/O/S/X;
- PRICE_POLARITY_ONLY independently validates some tested continuation/depth checkpoints.

**KNN core**

- continuation: PRIOR age 0, FULL_CAUSAL;
- eventual depth: PRIOR age 1, FULL_CAUSAL;
- P/O/S/X: H+4, FULL_CAUSAL, provisional under the V3 hierarchy;
- NO_PRICE_CAUSAL independently sees P/O/S/X earlier at PRIOR age 3 and at T0/H+1/H+2/H+3/H+4.

The same D3 observations therefore expose different information boundaries by model/channel. This seeds V4 hypotheses around nonlinear relative geometry, model extraction and channel fusion; it does not authorize a model vote.

### D5

The completed D5 sparse case-study artifact contains:

- 9 total cases;
- 5 discovery, 2 validation, 2 confirmation, 0 held;
- 8 depth-4 stops and 1 depth-5 continuation;
- 8/9 eligible at PRIOR age 0;
- 9/9 eligible at T0.

D5 remains case-study evidence only. The single continuation is preserved as a rare informative case; it cannot support a universal D5 law by itself.

### Current V4 data-gap categories

V4 research must explicitly distinguish:

1. missing measurement;
2. coarse/wrong encoding;
3. timing/observability boundary;
4. support/calibration gap;
5. model extraction gap;
6. channel fusion gap;
7. trade translation gap.

Current evidence-seeded V4 research thread:

- `research/NG_EXHAUSTION_V4_RESEARCH_THREAD_20260820.md`
- `research/NG_EXHAUSTION_V4_RESEARCH_THREAD_20260820.json`

---

## 24. Later explicit documentation authorization — 2026-08-20

The user later explicitly instructed:

> Update docs and create V4 research thread docs, commit and push.

That instruction supersedes the earlier no-result-inspection/no-commit/no-push boundary **only for the documentation task necessary to capture the current evidence and create the V4 research-thread handoff**.

Authorized for this documentation update:

- inspect current pinned V3 Actions logs/artifacts needed to document the evidence boundary;
- update the current V3/V4 decision, brain/trade and geometric research records;
- create human- and machine-readable V4 research-thread records;
- commit/push those documentation-only changes to `chatgpt/ng-exhaustion-entry-timing-revival-20260818`.

Still unauthorized by this instruction:

- launch V4;
- rerun/cancel current V3 jobs;
- modify research code as part of this documentation commit;
- mutate frozen detector/canonical/Phase-1/Phase-2/runway/SSOS evidence;
- mutate permanent Frankie or Frankie 1;
- modify `research/kalshi/spawn.py`;
- promote a trade/play or deploy live.

V4 launch remains a separate explicit decision.
