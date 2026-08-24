# Frankie Full-Stack October Launch — Self-Contained Next-Chat Handoff

Date: 2026-08-24
Target branch: `chatgpt/ng-exhaustion-october-sharded-20260824`

## Governing instruction

Take over the NG Exhaustion / Frankie project. This is an implementation-and-launch session, not another planning or science-review session.

Treat this document as the corrected operational scope. It supersedes incompatible instructions in older handoffs, bridges, workflows, status packets, and chat messages.

## Dual mandate — both deliverables are required

This session has two inseparable deliverables:

1. Complete the exhaustive Frankie inventory, rebuild the corrected full-stack bridge, and launch the full October 2021 run.
2. Implement every recommendation in the complete GPT-5.6 Sol Frankie design-review paper embedded below.

Neither deliverable substitutes for the other.

Do not launch a reduced runner that omits Frankie's recommendations. Do not stop after implementing the recommendations without launching October. Both must be completed in the same workstream.

## Invoke these skills immediately

The Addy Osmani `agent-skills` release 0.6.7 versions, including the Codex compatibility fix and `using-agent-skills`, were already installed. Do not reinstall them.

Invoke:

- `context-engineering`
- `planning-and-task-breakdown`
- `git-workflow-and-versioning`
- `api-and-interface-design`
- `incremental-implementation`
- `observability-and-instrumentation`
- `shipping-and-launch`
- focused `test-driven-development` only for new bridge behavior
- `debugging-and-error-recovery` only if the real launch encounters an error
- one bounded `code-review-and-quality` pass before launch

Use four GPT-5.6 Sol implementation helpers only where parallel inspection or implementation will reduce launch time. One agent owns integration and dispatch. Do not reopen settled science or start an extended review cycle.

The four live D-finding helpers described later are part of Frankie's runtime design and are distinct from temporary implementation agents.

## Mission and date scope

Build a fresh, minimal, additive bridge connecting:

1. The complete authority-gated Frankie knowledge stack.
2. Continuously replayed canonical raw DBN MBO data.
3. The unchanged V4 causal/state/mechanics/probability/lock runtime.
4. Four active real-time D-finding specialist helpers.
5. GPT-5.6 Sol as Frankie's actual reasoning authority.
6. Immutable state, helper-evidence, reasoning, probability, first-lock, no-lock, and receipt ledgers.

Then launch the complete October 2021 run:

```text
[2021-10-01, 2021-11-01)
```

Use only the canonical predecessor input required to bootstrap continuous order-book and predecessor-lifecycle state.

October is the first staged full-month run. It does not use different science from September or November. The final homogeneous scope is September through November 2021, using the same data, knowledge, helper design, runtime, schema, clocks, causal restrictions, and withholding rules:

```text
[2021-09-01, 2021-12-01)
```

Run October first. After October's discoveries, movies, reasoning, and first locks are immutable, reveal the existing October Step-1 answer key and let Frankie diagnose remaining gaps. If the runner is validated, apply the same frozen construction to September and November.

Do not rerun October Step-1.

## Scientific separation and answer wall

October Step-1 is the sealed target answer key.

Before Frankie and the four helpers freeze their discoveries and first locks, they must not receive:

- Step-1 target seconds or target-relative clocks.
- Step-1 populations.
- October answer crosswalks.
- Receipts that reveal target membership.
- Labels or classifications.
- Result prefixes.
- Reconciliation outputs.
- Answer-derived `PRIOR`, `T0`, or `H`.
- Any other target-relative leakage.

After primary outputs freeze, Step-1 may be revealed for reconciliation and gap diagnosis.

DBN snapshot messages are order-book bootstrap/reset information. They are not Frankie's state movie.

## Reuse the established V4 science unchanged

Reuse, do not replace:

- `research/ng_exhaustion_mbo_v4_full_state_replay_20260820.py::replay_dbn_files`
- `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`
- V4 causal-clock modules
- V4 state assembler
- V4 mechanics
- V4 probability movie
- V4 first-lock logic
- V4 adapter integration
- V4 unified runtime
- V4 reconciliation

The missing component is the executable bridge and complete ingestion/wiring layer.

Do not invent alternative science. Do not rerun broad settled test suites. Fix an established scientific module only if the real launch encounters a concrete error, and record the error and smallest necessary fix.

## Complete Frankie knowledge stack

Frankie must receive the current authoritative S135 runtime and complete brain, including:

- S120 full brain and outcome wall.
- S126 A-E parity.
- S128 decision-state repairs.
- S132 event-driven curve.
- S133 reasoning authority and prior-session carry.
- S135 authority.
- `research/kalshi/knowledge/ng_brain.json`
- Brain version `s105.9`.
- All 90 complete play bodies.
- Falsifiers.
- Contradictory and negative evidence.
- Doctrine, reasoning rules, and play index.
- Permitted historical source material.

Also provide the complete frozen knowledge learned from the original 54/55-week work:

- D structures and families.
- Dipoles.
- Chains and extensions.
- Pair/triplet recurrences.
- Phase-1 discoveries.
- Phase-2 structural knowledge.
- True/false-context findings.
- Predecessor and ancestry relationships.
- Stopped-chain and negative cases.
- Admissible timing/lifespan knowledge, without converting historical timing centers into hard clocks.
- The full proposal and proposal index.
- The clean V4 proposal.
- Post-correction extra-agent carryforward findings.

Controlling material includes, but is not necessarily limited to:

- `research/NG_EXHAUSTION_CHAIN_PHASE2_ALL_AGENT_FINDINGS_20260818.md`
- `research/NG_EXHAUSTION_BRAIN_PROPOSAL_INDEX_20260818.md`
- `research/NG_EXHAUSTION_V4_BRAIN_TRADE_PROPOSAL_CLEAN_SOURCE_CURRENT_20260820.md`
- `research/NG_EXHAUSTION_V4_CONTINUOUS_ADAPTIVE_WALKFORWARD_CONTRACT_20260820.md`
- `research/NG_EXHAUSTION_D0_D5_V4_GEOMETRIC_SELF_ADAPTATION_CONTRACT_20260820.md`
- `research/NG_EXHAUSTION_EVENT_MARK_CLOCK_OPEN_BOUNDARY_20260819.md`
- `research/NG_EXHAUSTION_V4_CLEAN_SOURCE_PRELAUNCH_GATES_20260820.md`
- `research/NG_EXHAUSTION_V4_INTERPRETATION_CORRECTION_20260820.md`
- `research/NG_EXHAUSTION_V3_NONAUTHORITATIVE_RESULTS_EXTRA_AGENT_V4_CARRYFORWARD_20260820.md`
- `research/NG_EXHAUSTION_V3_EXTRA_AGENT_INFORMATION_FINDINGS_20260820.md`
- `research/NG_EXHAUSTION_V3_EXTRA_AGENT_INFORMATION_FINDINGS_20260820.json`
- `research/kalshi/FRANKIE_P0_GAP_CLOSURE_PROVISIONAL_20260820.md`
- `research/kalshi/NG_EXHAUSTION_V4_PROVISIONAL_READINESS_20260821.json`
- `research/kalshi/NG_EXHAUSTION_OCTOBER_SHARDED_HANDOFF_20260824.md`, subject to this corrected scope

Search the repository for renamed, later, or superseding versions before treating this as the complete catalog.

## V3 authority boundary

V3 is not generally authoritative.

Preserve and use:

- The four-specialist helper architecture.
- Valid frozen Phase-1/Phase-2 structural knowledge.
- Post-correction extra-agent gap diagnoses expressly carried into V4.

Do not serve Frankie:

- Ordinary V3 run findings.
- V3 target point estimates.
- V3 AUCs or hit rates.
- Exact historical `PRIOR`/`T0`/`H` assignments.
- Fixed-horizon trade findings.
- D1 ExtraTrees numbers.
- Any pre-correction claim not expressly authorized by the V4 correction/carryforward documents.

The removed D1 ExtraTrees numbers came from the August 19 pre-correction predictability work. They are not the later, useful post-correction extra-agent gap findings.

Preserving the four helpers does not preserve their invalid historical outputs.

## Four active real-time D-finding helpers

The helpers are part of the live D-detection architecture, not merely coding assistants, curve reviewers, or after-the-fact analysts.

Use the roles described by:

- `research/ng_exhaustion_chain_phase2_parallel_agents_20260818.py`
- `research/NG_EXHAUSTION_CHAIN_PHASE2_ALL_AGENT_FINDINGS_20260818.md`

The four roles are:

1. Pair/triplet recurrence scout.
2. Extension-propensity scout.
3. Timing/lifespan-family scout.
4. True/false-context investigator.

All four receive the same immutable causal prefix and state-prefix hash.

Their responsibilities are:

- Recurrence scout: identify known or novel pair/triplet/local structural modules.
- Extension scout: evaluate whether the lawful prefix is developing into a larger chain or extension.
- Timing scout: track unresolved age and trajectory without using answer-relative or hardcoded event clocks.
- Context investigator: recover ancestry, regimes, contradictory context, stopped chains, and negative evidence.

Each helper output must bind:

- Exact model identity: `gpt-5.6-sol`.
- Provider response ID.
- Causal evaluation timestamp.
- `event_known_by` cutoff.
- State-row or state-prefix hash.
- Knowledge-manifest hash.
- Evidence citations.
- Supporting observations.
- Contradictory observations.
- Uncertainty.
- Abstention or inconclusive status where applicable.

Helpers submit evidence packets to Frankie. Frankie is the sole synthesizer and sole owner of the primary probability path and first lock. Do not use majority voting, averaging, automatic consensus, or helper-owned primary locks.

### Binding four-CPU execution correction — 2026-08-24

Within each lane, run the four helpers concurrently and pin one role to each CPU: recurrence=CPU0, extension=CPU1, timing/lifespan=CPU2, and true/false-context=CPU3. Frankie synthesis begins only after all four complete. Preserve the existing sequential lane order—control first, combined second—so the four-CPU host never runs eight helper workers at once.

Persist and gate a hashed affinity receipt for every helper containing role, requested CPU, observed singleton affinity during the provider call, native thread identity, mapping version, timing, and receipt hash. Fail before provider activity if CPUs 0-3 are not available. Measure helper-batch wall time before and after; this requirement exists to reduce October wall-clock runtime, not only to label workers.

## Complete causal market-data plane

Feed the complete canonical raw DBN MBO/V4-native causal state, including:

- Relevant A/C/M/R/T/F/N messages.
- Adds, cancels, modifies, replaces, trades, fills, and clears.
- Complete order lifecycle.
- Full bid and ask depth.
- FIFO state.
- Queue age, survival, and concentration.
- Volume and orders ahead.
- Price-level counts.
- Spread, depth, and imbalance.
- Depletion and replenishment.
- Resilience and churn.
- Aggressor and signed flow.
- Price/path state.
- `roll20`.
- Dipole geometry.
- Book state.
- Predecessor lifecycle.
- Session state.
- Contract and roll state.
- Provenance.
- Missingness and integrity status.

Preserve continuous causal state across the complete month. Do not reset at artificial hourly windows or daily chunks except where the canonical source itself requires a bootstrap/reset.

## Exact legacy-to-V4 semantic crosswalk

The same MBO replay must expose both:

1. The exact legacy-observable surface on which the 54/55-week structures were learned.
2. The additive V4-native FIFO, depth, lifecycle, and mechanical surface.

Richer MBO data alone does not guarantee that Frankie can map an old D/dipole/chain fingerprint onto renamed native fields.

Explicitly map and receipt:

- Legacy price.
- Legacy native signed flow.
- Per-second `roll20`.
- Legacy book imbalance.
- Predecessor/family/chain observables.
- Their corresponding V4-native fields and causal availability.

Do not inject old target identities while creating this crosswalk.

## Lossless authority-gated ingestion

Use two planes:

1. A lossless, authority-gated knowledge plane.
2. A continuous causal market-data plane.

Create a content-addressed source catalog containing:

- Full source path.
- File SHA.
- Byte length.
- Authority class.
- Supersession relationship.
- Target relationship.
- Access policy.
- Knowledge-manifest version.

Use explicit authority classes:

- `BINDING_CURRENT`
- `CURRENT_BRAIN`
- `FROZEN_LEARNED_KNOWLEDGE`
- `EXTRA_AGENT_CARRYFORWARD`
- `PROVISIONAL_SHADOW`
- `ARCHIVE_NOT_SERVABLE`
- `SEALED_TARGET_ANSWER`

Semantic chunks may support retrieval, but every chunk requires byte ranges and hashes, with 100% source-coverage receipts.

Summaries and indexes are routing aids only. Full exact sources and complete play bodies must remain retrievable.

Provide typed tools for Frankie and the helpers to:

- List, search, and read knowledge sources.
- Read a complete brain play.
- Retrieve supporting and contradictory evidence.
- Read immutable state rows and deltas.
- Read raw causal events.
- Read order-book and queue state.
- Read prior lawful predictions.
- Record evidence packets and reasoning.

No summary, embedding system, or provisional retrieval layer may become the only route to source material.

## Clocks and pre-birth prediction opportunities

Do not use hourly windows or fixed `PRIOR`/`T0`/`H`.

Track distinct clocks:

- Event time.
- Receive time.
- `event_known_by` time.
- Onset time, revealed only when permitted.
- Confirmation/discovery time.
- Feature availability time.
- Model evaluation time.
- Lock time.

The causal clock can validate a supplied mark, but the bridge still needs the protected prospective mechanism that produces the discovery mark.

Prediction before D birth requires predecessor-defined, at-risk opportunity instances that exist before a possible next D event. Construct lawful opportunity processes using:

- Predecessor state.
- Unresolved chain/extension state.
- Ancestry.
- Stopped-chain controls.
- Negative opportunity cases.
- Later outcome reveal.

Do not create an opportunity only after its target D is already known. That measures recognition, not prior prediction.

Lock timing must be an empirical output. Do not reuse the old bridge's arbitrary threshold/two-hit lock, historical timing centers, or answer-derived timing buckets.

Find and authority-classify every purported predictive value before using it. D1 ExtraTrees values and other removed V3 numbers are forbidden. Any calibration and lock policy must come from an admissible discovery/calibration partition and remain frozen for October.

## Immutable output requirements

Emit append-only, content-addressed records for every lawful second, including weak, negative, sparse, ambiguous, contradictory, and inconclusive cases.

Required outputs include:

- State movie.
- State-delta movie.
- Helper-evidence movie.
- Frankie reasoning movie.
- Probability movie.
- Candidate-discovery ledger.
- First-lock ledger.
- No-lock ledger.
- Abstention ledger.
- Data-integrity and missingness ledger.
- Knowledge-retrieval receipts.
- Model/provider invocation receipts.
- Answer-wall access receipts.
- Post-freeze reconciliation.

Every record must bind:

- Run identity.
- Source-object identity.
- Causal cutoff.
- State hash.
- Knowledge-manifest hash.
- Code/commit identity.
- Model name.
- Provider response ID where applicable.

## Actual GPT-5.6 Sol requirement

GPT-5.6 Sol must perform structure discovery and synthesis reasoning.

It is not sufficient to write `gpt-5.6-sol` into an environment variable or service file.

Require runtime evidence of:

- Actual provider request.
- Exact model identity.
- Provider response ID.
- Tool-call and retrieval receipts.
- Evidence citations.
- Accepted, parsed response.
- Persisted reasoning/evidence associated with the relevant causal prefix.

## Provisional builds

S135 remains the control and authority.

Treat S137/HippoRAG and other provisional V4 engineering builds as paired `SHADOW_ONLY` ablations unless a newer binding authority document proves otherwise.

Provisional builds may assist with:

- Retrieval expansion.
- Structured reasoning.
- Diagnostics.
- Coverage comparison.
- Shadow probability or evidence generation.

They must not:

- Replace S135.
- Become the sole retrieval path.
- Mutate the brain.
- Own or alter the primary first lock.
- Inject unlabeled authority.
- Be counted as proof of prediction.

Run provisional variants on identical causal prefixes and compare them only after primary S135 locks freeze.

## Repository and worktree safety

Before changing anything, inspect all worktrees, branches, uncommitted changes, and untracked files read-only.

Main worktree previously observed:

```text
/workspace/scratch/a3eb045180ff/Markets
```

Detached HEAD previously observed:

```text
0d12b575751395f75c4f7d4333295b2911b3b404
```

Modified files previously observed:

```text
.github/workflows/ng_exhaustion_october_frankie_blind_canary_20260824.yml
research/kalshi/ng_exhaustion_october_frankie_v4_bridge_20260824.py
research/kalshi/tests/test_ng_exhaustion_october_frankie_v4_bridge_20260824.py
```

Untracked files previously observed:

```text
.github/workflows/ng_exhaustion_october_frankie_blind_canary_probe_20260824.yml
research/kalshi/NG_EXHAUSTION_OCTOBER_FRANKIE_BLIND_CANARY_PROBE_20260824.json
```

Remote target branch previously observed:

```text
origin/chatgpt/ng-exhaustion-october-sharded-20260824
dcf839e911c5d501396fa7af9d6692012fb6e0d9
```

Second worktree previously observed:

```text
/workspace/scratch/d684831c51bd/Markets
```

It was locally ahead by two commits and behind the remote by seventeen, with modified and untracked operational files.

These are historical observations, not permission to reset or overwrite anything. Reverify them.

Do not use:

- `git reset --hard`
- `git checkout --` on user changes
- `git clean`
- Force push
- Destructive worktree removal

Preserve every uncommitted and untracked artifact. Recover or reconcile worktrees non-destructively.

## Old bridge and failed canary evidence

The existing bridge does not satisfy the corrected construction:

```text
research/kalshi/ng_exhaustion_october_frankie_v4_bridge_20260824.py
```

Its shortcomings include:

- No complete S135/brain integration.
- No complete 54/55-week exhaustion corpus.
- Hourly compression.
- Buffered/replayed rather than continuously reasoned causal state.
- Narrow summaries instead of complete lawful state.
- Synthetic run-level discovery.
- No predecessor-defined pre-birth opportunity process.
- No four-helper live D-finding architecture.

Treat it as transport/forensic evidence, not the new scientific runner.

Old launch workflow:

```text
https://github.com/DavisAI1974/Markets/actions/runs/32712930114
```

It completed with failure.

Observer workflow:

```text
https://github.com/DavisAI1974/Markets/actions/runs/32715588278
```

Verified observer-log evidence included:

```text
UNIT_STATE=inactive
ActiveState=inactive
SubState=dead
LoadState=not-found
V4_GROUPS_PROCESSED target_groups=1118737
SOL_INVOCATION_STARTED model=gpt-5.6-sol
Traceback (body not captured)
BLIND_OCTOBER_FRANKIE_EXIT_CODE=1
Existing canary unit stopped before an accepted Sol response
```

No runtime `SOL_RESPONSE_ACCEPTED` event or provider response ID was emitted. The inactive status was the observer's final remote poll, not a new direct systemd check after the workflow. Verify current remote state read-only.

Build the corrected bridge fresh with a new identity. Preserve dirty and untracked old files until they have been inspected; deletion or replacement is a separate version-control decision.

Do not use `frankie_bounded_3mo_parallel.py`. It is an SQS consumer for prebuilt Frankie events, not the raw-MBO/V4 path. Do not create a `frankie-events` queue as a substitute.

## Preserve permanent services

Do not stop, replace, or modify permanent Frankie services or unrelated workers.

The corrected service must have a unique unit/run identity and bounded October scope.

## Minimum launch gates

Do not rerun broad settled suites. Validate only the new bridge behavior and launch-critical contracts:

1. Repository/worktree safety inventory completed.
2. Full knowledge-manifest hashes and authority classes recorded.
3. Full S135 brain and all 90 plays retrievable.
4. Frozen 54/55-week D corpus retrievable.
5. Forbidden V3 outputs mechanically denied.
6. October Step-1 answer wall mechanically denied before freeze.
7. Legacy/V4 semantic crosswalk has complete coverage receipts.
8. Continuous MBO replay and predecessor bootstrap verified.
9. Four live helpers receive identical causal-prefix hashes.
10. Frankie remains the sole primary lock owner.
11. A real GPT-5.6 Sol request returns an accepted response and provider ID.
12. Immutable state, evidence, reasoning, probability, lock, and no-lock records begin persisting.
13. Weak, negative, sparse, and inconclusive cases are retained.
14. Service isolation and rollback/stop command are documented.
15. Live logs and run URL make progress observable.

After these gates pass, launch full October in the same workstream. Do not stop after another transport canary, plan, documentation packet, or status-only update.

## Required report

Report:

- Branch and exact commit.
- Files added or changed.
- Knowledge-manifest hash.
- Enabled authority classes.
- Confirmation that forbidden V3 data is mechanically denied.
- Confirmation that Step-1 remains sealed.
- Four-helper identities and live roles.
- Live workflow/run URL.
- Remote service identity and state.
- Exact GPT-5.6 Sol provider-response evidence.
- First persisted causal-state, helper-evidence, reasoning, and probability receipts.
- Rollback/stop procedure.
- Any launch error and the smallest fix made.

Do not claim predictive success merely because the service runs.

---

# Embedded paper: GPT-5.6 Sol Frankie Full-Stack Sufficiency Review

## Question reviewed

Considering the complete newly inventoried data/knowledge stack and Frankie's upgraded design—including the four active real-time D-finding helpers and provisional components—would the construction have been enough to detect the D structures from the original 54/55-week run? Would it be enough to predict them before onset or soon after onset?

## Verdict

The proposed stack contains enough information to run a scientifically meaningful October test and should be sufficient for recognizing the known 54/55-week D structures **if it is wired exactly as proposed**.

It is not yet sufficient to claim those structures can be predicted before onset or soon after onset. That remains the empirical question October must answer.

## Recognition versus prediction

### Recognition and detection

The construction is conceptually sufficient.

The combination of frozen 54/55-week D/dipole/family/chain/Phase-1/Phase-2 knowledge, the full S135 brain/runtime, and richer V4-native MBO state gives Frankie both:

1. The learned structural grammar.
2. A causal stream capable of reproducing the old observable surface while adding FIFO and order-level information.

Supporting repository material includes:

- `research/NG_EXHAUSTION_CHAIN_PHASE2_ALL_AGENT_FINDINGS_20260818.md`
- `research/NG_EXHAUSTION_BRAIN_PROPOSAL_INDEX_20260818.md`
- `research/ng_exhaustion_mbo_v4_full_state_replay_20260820.py`
- `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`

### Prediction before birth or soon into D

The construction contains enough lawful information to test prediction, but not enough evidence to assert predictive success beforehand.

The clean V4 contracts treat lock timing as an output and require each causal second to be scored without target-relative clocks:

- `research/NG_EXHAUSTION_V4_CONTINUOUS_ADAPTIVE_WALKFORWARD_CONTRACT_20260820.md`
- `research/NG_EXHAUSTION_D0_D5_V4_GEOMETRIC_SELF_ADAPTATION_CONTRACT_20260820.md`

The repository also states that the real `event_known_by` boundary remains unresolved and that prior availability alone did not establish predictive skill:

- `research/NG_EXHAUSTION_EVENT_MARK_CLOCK_OPEN_BOUNDARY_20260819.md`
- `research/NG_EXHAUSTION_V4_CLEAN_SOURCE_PRELAUNCH_GATES_20260820.md`

The honest conclusion is therefore:

> Frankie has enough lawful information to attempt prior recognition and early locking, but October must determine whether useful predictive information actually exists and when.

## Four real-time helper design

Preserve the four-helper architecture. Its valid roles are supported by:

- `research/ng_exhaustion_chain_phase2_parallel_agents_20260818.py`
- `research/NG_EXHAUSTION_CHAIN_PHASE2_ALL_AGENT_FINDINGS_20260818.md`

The four roles are:

1. Pair/triplet recurrence scout.
2. Extension-propensity scout.
3. Timing/lifespan-family scout.
4. True/false-context investigator.

For October, these should be four active causal-stream GPT-5.6 Sol specialists receiving the same immutable state-prefix hash and lawful cutoff:

- Recurrence identifies known or novel local modules.
- Extension evaluates whether the causal prefix appears to be growing.
- Timing tracks unresolved age and trajectory without converting historical timing centers into hard clocks.
- Context restores longer ancestry, regimes, contradictory evidence, false contexts, and stopped-chain evidence.

They feed evidence packets to Frankie. Frankie remains the sole synthesizer and lock owner. There is no voting, probability averaging, automatic consensus, or helper-owned primary lock.

Every helper output binds model/provider identity, provider response ID, state-row hash, knowledge-manifest hash, causal evaluation time, evidence citations, contradiction, uncertainty, and abstention status.

Preserving these helper roles does not authorize ordinary V3 findings or D1 ExtraTrees numbers. Those remain excluded. Valid frozen Phase-1/Phase-2 structural knowledge remains admissible.

## Minimum missing wiring identified by Frankie

The principal gap is wiring, not another dataset.

### 1. Legacy-to-native semantic crosswalk

From the same MBO replay, expose both the exact legacy-observable surface used to learn the 54/55-week structures and the additive V4-native FIFO/depth/order-lifecycle surface.

Richer MBO data alone does not guarantee that Frankie can map an old dipole/chain fingerprint to renamed native fields.

### 2. Complete knowledge manifest

Serve S135's complete 90-play brain plus the exhaustion proposal/index, frozen Phase-1/Phase-2 findings, negative and falsifier cases, and post-correction extra-agent gap findings.

`frankie_s135_current_runtime.py` demonstrates that the 90-play brain is served, but does not by itself integrate the separate exhaustion proposal corpus.

### 3. Pre-birth opportunity instances

The existing unified runtime requires a case to start no earlier than the current event's `event_known_by`. That supports post-discovery recognition but does not by itself create prediction opportunities before the target exists.

Prior prediction requires predecessor-defined, at-risk opportunity windows that remain active before a possible next D event, together with lawful stopped-chain controls and later outcome reveal.

### 4. Real discovery clock

The causal clock validates a supplied mark but does not itself implement the protected detector that produces the mark.

A prospective detector mark or separately versioned causal-replay discovery rule is still required.

### 5. Per-second derived geometry

Wire `roll20`/dipole state, P/O/S/X known predecessor state, ancestry gaps, unresolved age, price/flow/book paths, and full MBO mechanics into immutable V4 movie fields.

Generic state-assembler support exists, but the complete market-field mapping must be finished.

### 6. Frozen lock policy and calibration identity

Do not reuse the old bridge's arbitrary `0.8 x 2` lock or historical timing buckets.

The lock rule must be frozen from an admissible discovery/calibration partition and applied unchanged to October.

### 7. Answer wall and receipts

October Step-1 populations, seconds, classifications, crosswalks, and reconciliation remain sealed until every Frankie/helper discovery, probability movie, and first-lock/no-lock ledger is immutable. Reconcile only after that freeze.

## Existing bridge assessment

`research/kalshi/ng_exhaustion_october_frankie_v4_bridge_20260824.py` does not satisfy this construction because it:

- Does not load S135 or the complete 54/55-week exhaustion knowledge.
- Compresses the stream into hourly windows.
- Creates one synthetic month/run-level discovery at the target start rather than real per-D causal discovery.
- Has no predecessor-defined pre-birth opportunity process.
- Has no four-helper live architecture.

It may prove transport, but it cannot answer the scientific question.

## Provisional builds

Use S137/HippoRAG and the provisional V4 engineering candidate only as paired shadow ablations. Their controlling records state they are not empirically ready to replace the current authority:

- `research/kalshi/FRANKIE_P0_GAP_CLOSURE_PROVISIONAL_20260820.md`
- `research/kalshi/frankie_s137_cognitive_runtime.py`
- `research/kalshi/NG_EXHAUSTION_V4_PROVISIONAL_READINESS_20260821.json`

They may improve retrieval, structured reasoning, or diagnostics, but they must not:

- Replace S135.
- Become the sole route to complete source material.
- Own or alter Frankie's primary first lock.
- Mutate the brain.
- Contribute unlabeled authority.
- Be counted as proof of prediction.

Run them beside the S135 control on identical causal prefixes. Compare their outputs only after primary locks freeze.

## Paper conclusion

This is enough data and learned structure for a real October experiment.

It is probably enough for recognition if the legacy/native crosswalk and four real-time helpers are properly wired.

It is not evidence, by itself, of prior or early predictive capability. October is the experiment that can establish that capability.

## Mandatory implementation interpretation of this paper

Every recommendation above is required work, not optional commentary.

The corrected bridge is not complete merely because raw MBO replay reaches GPT-5.6 Sol. It is complete only when all recommendations are implemented, connected, receipted, causally verified, and included in the launched October construction.

Do not defer the recommendations to a cleanup pass. Do not stop after implementing them without launching October. Do not launch October without them.

## Final scientific expectation

The inventoried stack is conceptually sufficient to recognize the D structures found in the original 54/55-week work if:

- The complete frozen knowledge is actually served.
- The legacy/native semantic crosswalk is complete.
- The four helpers actively inspect the same causal stream.
- Frankie receives their evidence and retains synthesis authority.
- The target answer wall remains sealed.

Whether Frankie can predict D before onset or soon into onset is not established. October must determine:

- Whether lawful predictive signal exists.
- When it first becomes observable.
- Which helper or state family contributes it.
- Whether the lock is early enough to be actionable.
- Where recognition succeeds but prediction fails.
- Which data, knowledge, clock, or opportunity gaps remain.

Weak findings, failures, negatives, late locks, abstentions, and no-locks must be retained. They are part of the result.
