# ChatGPT Handoff — NG Exhaustion V3 Monitor / V4 Next — 2026-08-20

## Current status

Current branch:

`chatgpt/ng-exhaustion-entry-timing-revival-20260818`

Current repo state is truth. Do not redo settled Phase-1/Phase-2 work.

The immediate priority is **getting the pinned V3-T0 agents to run and reconciling their durable results**.

V4 continuous per-instance timing/adaptive learning has been designed and partially coded, but **V4 is not to be launched by this chat**. A new chat should intentionally review/complete V4 before launch.

A possible additional Frankie enhancement was mentioned by the user and deliberately deferred. Do not guess or implement it from this handoff.

---

## Mandatory read order for the next chat

Read in this order before changing anything:

1. `research/NG_EXHAUSTION_V3_V4_CHAT_DECISIONS_ALL_NOTES_20260820.md`
2. `research/NG_EXHAUSTION_V3_V4_BRAIN_TRADE_PROPOSAL_ADDENDUM_20260820.md`
3. `research/NG_EXHAUSTION_BRAIN_PROPOSAL_INDEX_ADDENDUM_20260820.md`
4. `research/NG_EXHAUSTION_CHAIN_PHASE2_ALL_AGENT_FINDINGS_20260818.md`
5. `research/NG_EXHAUSTION_EVENT_MARK_CLOCK_OPEN_BOUNDARY_20260819.md`
6. `research/NG_EXHAUSTION_V4_CONTINUOUS_ADAPTIVE_WALKFORWARD_CONTRACT_20260820.md`
7. this handoff again for the exact operational next step.

Read older proposal/synthesis files only for provenance after the files above.

---

## Protected/frozen — DO NOT MODIFY

Do not modify, retune, reopen or relitigate:

- frozen exhaustion detector;
- frozen canonical base/held rows/evidence;
- frozen Phase-1 lineage/scores;
- finalized Phase-2 findings;
- frozen exhaustion runway clock;
- permanent Frankie;
- Frankie 1;
- `research/kalshi/spawn.py`;
- frozen SSOS play.

No permanent brain merge or live-play promotion is authorized.

Preserve every positive, negative, false, losing, censored, low-support and model-disagreement case.

Standing policy:

`FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`

---

## Frozen exact depth counts

These counts are invariants:

- D0 = 135,860
- D1 = 18,837
- D2 = 1,592
- D3 = 124
- D4 = 8
- D5 = 1

Do not collapse or renumber them.

D4/D5 remain low-support case studies.

---

## Primary research questions

Keep these independent:

1. chain / continuation;
2. eventual final depth;
3. P/O/S/X structural state/family;
4. earliest causal recognition time.

Target polarity is not a primary target.

SAME/FLIP is secondary annotation/context only.

P/O/S/X:

- P = persistent exhaustion;
- O = collapsed opposite-flow reversal;
- S = collapsed same-flow reload;
- X = collapsed sparse/indeterminate.

---

# PART I — V3: IMMEDIATE PRIORITY

## V3 current revision

Current fixed-checkpoint benchmark revision:

`V3_CONTINUOUS_LIVE_MARKET_STATE_T0`

D1-D5 fixed benchmark ladder:

`PRIOR -> T0 -> H+1 -> H+2 -> H+3 -> H+4 -> H+5`

T0 is explicitly the frozen birth second, not H=0.

D0 does not get a fake descendant H clock.

The live market surface continuously includes price direction/path, rolling-flow/dipole shape, signed flow, book path and causal/session context.

Unknown future target polarity never blocks PRIOR/T0 or hides live direction.

## Current V3 core code

- `research/ng_exhaustion_live_checkpoint_state_20260819.py`
- `research/ng_exhaustion_chain_recovery_features_v3_20260819.py`
- `research/ng_exhaustion_chain_recovery_models_v3_20260819.py`
- `research/ng_exhaustion_chain_birth_depth_type_recovery_v3_20260819.py`
- `research/ng_exhaustion_d0_full_causal_recovery_v3_20260819.py`

Last verified important blob SHAs before this handoff:

- live checkpoint state: `8afb71ee6238a541897ea1302f395a2035b23061`
- V3 feature surface after T0: `679da1a9885daa5acda5b377fb5044cda84d9809`
- V3 D1-D5 runner after T0: `d1aecfbc12b97c4955cf44a7adc11996efc22407`
- V3 D0 wrapper: `e299af923bdb7972ba39556df37834f1eb39b076`

If current branch blobs differ later, inspect the diff before trusting the old hashes. Do not silently force old hashes onto a newer intentional fix.

## Why the old unified V3 workflow is not the launch authority

The older workflow:

`.github/workflows/ng_exhaustion_d0_d5_full_causal_v3_20260819.yml`

was created before the explicit T0 revision and still carried an old revision assertion. It is retained as audit/provenance but is not the preferred current launch path.

## New pinned V3 launch workflow

Use:

`.github/workflows/ng_exhaustion_v3_t0_pinned_core_20260820.yml`

Workflow creation commit:

`7b8501b876288658b4c6ec050798c08e3836b8d2`

Critical design:

- trigger path is the dedicated launch marker;
- every job checks out `${{ github.sha }}`;
- therefore each run executes the exact launch commit, not a moving branch head;
- 14 lanes total;
- max parallel 10;
- no cross-model vote;
- frozen input artifacts are hash-verified;
- reconciliation commits durable outputs back to the agents branch.

### 14 core lanes

D0:

- Logistic
- ExtraTrees
- KNN

D1:

- Logistic
- ExtraTrees
- KNN

D2:

- Logistic
- ExtraTrees
- KNN

D3:

- Logistic
- ExtraTrees
- KNN

Sparse:

- D4 case study
- D5 case study

## Frozen workflow artifact inputs

- BASE_ID `9281733364`
- BASE_SHA `f50eaf74a57654334691cbf5cce3b038443f6944a9c00eb5da6ca35b557802b1`
- HELD_ID `9281272840`
- HELD_SHA `21577d01d45241264df714ab6ee5b95f6a774e1475e0d74a9454221fdfdde12e`
- LINEAGE_ID `9289929292`
- LINEAGE_SHA `a67caab9de6b183e8c102ebd73a7e542aa909e23f66575290563e40b056efd95`
- RECONCILE_ID `9306082330`
- RECONCILE_SHA `f17c130df029429bfbc35067d1cc9d16128ca4fb227dd37f3fb4fbb8bbaf8875`

## Pinned V3 expected durable outputs

After a successful run/reconciliation:

`research/generated/ng_exhaustion_v3_t0_pinned_core_20260820/NG_EXHAUSTION_V3_T0_PINNED_CORE_ALL_RESULTS_20260820.json`

and

`research/generated/ng_exhaustion_v3_t0_pinned_core_20260820/NG_EXHAUSTION_V3_T0_PINNED_CORE_ALL_FINDINGS_20260820.md`

As of this handoff's construction, these durable pinned outputs had **not yet landed**.

Do not claim completion until those files or a verified workflow result exist.

---

## V3 monitoring/recovery procedure

After the launch marker is committed:

1. Check the branch for the two generated pinned output files above.
2. If present, fetch/read both.
3. Report every D0-D3 model/target independently:
   - earliest fixed-checkpoint finding;
   - unresolved pairs;
   - FULL_CAUSAL / price-ablation evidence;
   - model disagreement;
   - D4/D5 case-study observations.
4. Do not vote the models.
5. Preserve all failures and unresolved cases.
6. If output is absent and workflow/job status is discoverable, inspect the failed step/log.
7. Patch only active V3 runner/workflow infrastructure necessary to make the intended contract execute.
8. Retrigger with a new marker update after the patch.
9. Never alter protected/frozen research artifacts to rescue a run.

If connector visibility for push-triggered Actions remains incomplete, absence of a visible run is **not** evidence of failure. Use durable generated outputs or explicit job/run evidence.

---

## V3 later-PRIOR refinement

A historical later-PRIOR refinement runner/workflow exists:

- `research/ng_exhaustion_v3_later_prior_refinement_20260819.py`
- `.github/workflows/ng_exhaustion_v3_later_prior_refinement_20260819.yml`

It was designed before the final V4 no-grid decision and its planner originally treated H/unresolved cases as refinement candidates.

Because V3 is now a fixed benchmark and V4 is the eventual timing-discovery architecture, do not automatically launch this workflow merely to consume context.

If a later V3 benchmark refinement is still desired, audit it first so T0 provisional results are handled consistently.

---

# PART II — V3 FOLLOW-UPS AFTER CORE

## Root/complement research

Useful comparisons:

- direct D0 vs matched `1 - D1` is calibration/implementation evidence only;
- D2/D3 root-retained vs root-ablated tests root-memory increment;
- FULL_CAUSAL vs NO_PRICE_CAUSAL tests price increment;
- FULL_CAUSAL vs PRICE_POLARITY_ONLY tests structural/microstructure increment.

Current T0-aware root-ablation wrapper:

`research/ng_exhaustion_root_retained_ablation_v3_20260819.py`

Last known blob after T0 addition:

`def3c0de1e99bc516846c1da225420094c6a240b`

Do not treat the older foundation workflow's D0 trade prototype as authoritative execution evidence.

## Corrected V3 trade doctrine

The older D0 trade prototype used a future next-exhaustion exit cap. That is hindsight and is superseded.

Corrected trade research files:

- `research/ng_exhaustion_d0_d3_model_specific_trade_v3_20260819.py`
- `research/ng_exhaustion_d0_d3_model_specific_trade_v3_hierarchy_20260820.py`

Corrected principles:

- model-specific signal;
- no probability aggregation;
- causal direction only;
- no realized target polarity as direction source;
- fixed horizon;
- no future next-event cap;
- preserve all candidate failures.

The earlier 12-lane trade workflow/trigger is comparison/provenance if it predates the hierarchy/T0 corrections. Do not promote those outputs as the final trade result without auditing which runner revision actually executed.

---

# PART III — V4: CODE/DESIGN ONLY, DO NOT LAUNCH FROM THIS HANDOFF AUTOMATICALLY

## V4 core correction

The user explicitly rejected hard-coded PRIOR/H research timing as the primary method.

V4 principle:

> score the causal trajectory continuously, let each instance/model discover when it becomes trustworthy, then report the discovered timestamp relative to frozen t0 afterward.

Timing becomes an output rather than an input grid.

## V4 current files

- `research/NG_EXHAUSTION_CONTINUOUS_INSTANCE_TIMING_CORRECTION_20260820.md`
- `research/ng_exhaustion_continuous_instance_features_20260820.py`
- `research/NG_EXHAUSTION_V4_CONTINUOUS_ADAPTIVE_WALKFORWARD_CONTRACT_20260820.md`

Current feature revision:

`V4_CONTINUOUS_PER_INSTANCE_TIMING`

The V4 feature surface withholds target t0 / PRIOR-H identity / target label from the primary model and uses t0 only for posthoc reporting.

Negative stop controls never receive a synthetic H label.

D0 remains candidate-relative rather than being assigned a descendant H clock.

## V4 hindsight-proof lock rule

Do not identify the first retrospectively correct second.

Instead discovery learns and freezes a lock rule based on:

- winning-class probability threshold;
- winning-class margin;
- persistence of the same winner for consecutive seconds.

OOT then fires the frozen rule causally. Correctness is scored after firing.

## V4 adaptive architecture

Compare:

### Frozen benchmark

Discovery-trained model + lock rule remain frozen through OOT.

### Adaptive walk-forward

Each instance:

1. starts from a snapshot containing only earlier causally completed/revealable cases;
2. is predicted causally;
3. has its call/timing frozen;
4. reveals its completed truth later;
5. may train only future instances.

Past calls are immutable.

Initial overlap policy is conservative: an already-active instance does not receive a mid-instance model update merely because another overlapping case completed.

## V4 implementation status

The V4 feature surface and adaptive contract are committed.

A full V4 frozen/adaptive walk-forward runner and launch workflow were **not completed/launched in this conversation checkpoint**.

The next chat may finish that code, review it, and deliberately launch V4 after the V3 priority is under control.

Do not launch V4 merely because files exist.

---

# PART IV — EVENT-MARK CLOCK OPEN BOUNDARY

Read:

`research/NG_EXHAUSTION_EVENT_MARK_CLOCK_OPEN_BOUNDARY_20260819.md`

Do not equate:

- frozen t0;
- upstream live detector mark time;
- endpoint confirmation.

Raw market direction/flow/book can be observed continuously regardless.

Event-specific newborn labels require their true causal availability.

Post-birth historical timing should not be represented as proven live-executable detector timing until the existing protected detector's mark contract is located/proven.

Do not retune the detector to solve this documentation question.

---

# PART V — PROPOSAL STATUS

Current proposal interpretation:

- `research/NG_EXHAUSTION_V3_V4_BRAIN_TRADE_PROPOSAL_ADDENDUM_20260820.md`
- `research/NG_EXHAUSTION_BRAIN_PROPOSAL_INDEX_ADDENDUM_20260820.md`

Historical proposal/synthesis files remain provenance and are not deleted.

Any future permanent Frankie lesson should be evidence-gated and deliberately merged later.

The intended long-run architecture is:

- V3 fixed benchmark;
- V4 continuous per-instance timing;
- frozen vs adaptive walk-forward;
- after validated research, compress stable learned timing relationships into operational Frankie timing/context rules so live Frankie does not need to rediscover stable timing from scratch every occurrence.

No such permanent timing rule is merged yet.

---

# PART VI — DEFERRED FRANKIE ENHANCEMENT

The user said there may be an additional Frankie feature/capability that would help this line.

It was deliberately deferred because the current research already has enough moving parts.

Do not invent it. Ask/continue that separate discussion later when the user brings it back up.

---

# Exact next action

The documentation checkpoint should be completed first.

Then create/update the dedicated marker:

`research/NG_EXHAUSTION_V3_T0_PINNED_CORE_LAUNCH_20260820.json`

This marker must be the **last substantive launch commit** so the pinned workflow runs the exact documented V3 state.

After that, monitor only. Do not continue adding V4 machinery in the same launch sequence.

---

# Drop-in summary

> Take over the NG exhaustion program on `chatgpt/ng-exhaustion-entry-timing-revival-20260818`. Read `research/NG_EXHAUSTION_V3_V4_CHAT_DECISIONS_ALL_NOTES_20260820.md`, `research/NG_EXHAUSTION_V3_V4_BRAIN_TRADE_PROPOSAL_ADDENDUM_20260820.md`, `research/NG_EXHAUSTION_CHAIN_PHASE2_ALL_AGENT_FINDINGS_20260818.md`, and `CHATGPT_HANDOFF_NG_EXHAUSTION_V3_MONITOR_V4_NEXT_20260820.md` first. Current priority is the pinned V3-T0 core agents in `.github/workflows/ng_exhaustion_v3_t0_pinned_core_20260820.yml`; monitor/recover them and do not launch V4 until V3 is under control. V4 is the later continuous per-instance timing/adaptive-walk-forward architecture and is code/design only at this checkpoint. Do not modify protected detector/canonical/Phase1/Phase2/runway/Frankie/Frankie1/spawn.py/SSOS. Preserve all true/false/losing/censored/low-support/model-disagreement cases and use `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`.

---

# PART VII — LATER D-SERIES V4 ARCHITECTURE DECISION

The user later returned to the deferred Frankie enhancement and explicitly directed that it also apply to D0-D5 V4.

Current binding addendum:

`research/NG_EXHAUSTION_D0_D5_V4_GEOMETRIC_SELF_ADAPTATION_CONTRACT_20260820.md`

It adds a temporal attributed graph over the raw + V3 causal state and a post-reveal, sandboxed self-edit proposal/evaluation loop. Active-instance snapshots and calls remain immutable; accepted research updates affect only later instances. D4/D5 remain case studies, and no sparse outcome can promote a general update by itself.

This is design/implementation authority only. The prior no-automatic-launch rule, protected boundaries, permanent-Frankie wall, and promotion wall remain in force.
