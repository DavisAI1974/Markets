# NG Exhaustion Frankie Data-Feed Inventory

Date: 2026-08-24
Scope: the authoritative input surfaces required by the corrected October Frankie runner

This inventory defines what Frankie and the four live D-finding helpers must be able to consume. It separates admissible knowledge, continuous causal market data, provisional shadow inputs, and the sealed target answer.

## 1. Current Frankie brain and runtime feed

- Authoritative S135 construction, including the retained S120, S126, S128, S132, and S133 improvements.
- Complete `s105.9` NG brain with all 90 play bodies.
- Doctrine, reasoning instructions, play index, falsifiers, negative evidence, and contradictory evidence.
- Prior-session carry permitted by the current runtime contracts.
- Outcome-wall enforcement for the October target period.

Authority: `CURRENT_BRAIN` / `BINDING_CURRENT`.

## 2. Frozen 54/55-week learned-structure feed

- D structures and D families.
- Dipoles and their geometry.
- Pair/triplet recurrence structures.
- Chains, extensions, reappearances, and successor ancestry.
- Phase-1 discoveries and structural/falsifier results.
- Phase-2 findings, modules, timing/lifespan context, POX branches, and negative/stopped-chain cases.
- Predecessor, ancestry, and unresolved-chain state.
- Historical timing/lifespan knowledge as context only, never a hardcoded target clock.
- Full proposal/index material needed to interpret the learned structures.

Authority: `FROZEN_LEARNED_KNOWLEDGE`.

## 3. Post-correction extra-agent carryforward feed

- Only the information and gap diagnoses expressly preserved by the V4 correction/carryforward records.
- Four-helper architecture and valid specialist roles.

Authority: `EXTRA_AGENT_CARRYFORWARD`.

Explicitly excluded:

- Ordinary V3 run findings.
- D1 ExtraTrees values.
- V3 point estimates, AUCs, hit rates, and fixed-horizon trade findings.
- Exact old `PRIOR`/`T0`/`H` values.
- Pre-correction predictive claims not expressly carried into V4.

Excluded authority: `ARCHIVE_NOT_SERVABLE`.

## 4. Canonical raw DBN MBO feed

- Canonical September-November 2021 DBN MBO objects.
- October first: `[2021-10-01, 2021-11-01)`.
- Only the canonical predecessor object(s) required to bootstrap continuous order-book and predecessor-lifecycle state.
- All relevant A/C/M/R/T/F/N message types.
- Snapshot messages used only for book bootstrap/reset.
- Raw source-object identity, SHA/provenance, receive time, event time, and integrity state.

Authority: `BINDING_CURRENT`.

## 5. Full order-lifecycle feed

- Adds.
- Cancels.
- Modifies.
- Replaces.
- Trades.
- Fills.
- Clears.
- Order identity and lifecycle transitions.
- Contract/session/roll state.

Availability must be causal at each evaluation cutoff.

## 6. Full book, FIFO, and queue feed

- Full bid and ask depth, not only top-of-book summaries.
- Price-level counts and order counts.
- FIFO queues.
- Queue age and survival.
- Queue concentration.
- Orders and volume ahead.
- Spread and depth imbalance.
- Complete state reset/bootstrap receipts.

## 7. Microstructure mechanics feed

- Adds/cancels/modifies/replaces/trades/fills by side and level.
- Aggressor and native signed flow.
- Depletion and replenishment.
- Resilience and recovery.
- Churn and queue turnover.
- Price path and book path.
- Missingness and integrity flags.

## 8. Legacy-observable compatibility feed

The same causal replay must recreate the exact lawful surface on which the 54/55-week structures were learned:

- Legacy price.
- Native signed flow.
- Per-second `roll20`.
- Legacy book imbalance.
- D/dipole/family/chain/predecessor observables.

Every legacy field requires an explicit crosswalk to its V4-native source fields, calculation, availability time, and state hash. The crosswalk must not contain October target identities.

## 9. Per-second derived geometry feed

- `roll20` and dipole state.
- D-family geometry.
- P/O/S/X known predecessor state where supported by binding science.
- Ancestry gaps.
- Unresolved age and chain/extension trajectory.
- Price, signed-flow, and book paths.
- V4 mechanics and FIFO features.
- Feature-availability timestamps.

These become immutable state/state-delta movie fields.

## 10. Four live helper-evidence feeds

Four GPT-5.6 Sol specialists inspect identical immutable causal prefixes:

1. Pair/triplet recurrence scout.
2. Extension-propensity scout.
3. Timing/lifespan-family scout.
4. True/false-context investigator.

Each emits a typed evidence packet containing state-prefix hash, lawful cutoff, model/provider identity, provider response ID, knowledge-manifest hash, evidence citations, contradiction, uncertainty, and abstention status.

Frankie is the sole synthesizer and primary lock owner.

## 11. Pre-birth opportunity feed

Prediction before D onset requires opportunities that exist before the target is known:

- Predecessor-defined at-risk state.
- Unresolved chain/extension state.
- Ancestry and successor opportunity.
- Stopped-chain and false-context controls.
- Negative opportunity cases.
- Later outcome reveal after predictions and locks freeze.

An instance created only after D discovery is a recognition instance, not a prior-prediction instance.

## 12. Distinct causal clocks

- Event time.
- Receive time.
- `event_known_by` time.
- Feature availability time.
- Prospective discovery/confirmation time.
- Model evaluation time.
- Lock time.
- Onset time, withheld until allowed.

No fixed hourly windows or answer-derived `PRIOR`/`T0`/`H`.

## 13. Provisional shadow feed

- S137/HippoRAG retrieval and cognitive components.
- Other provisional V4 engineering candidates expressly identified by readiness records.

Authority: `PROVISIONAL_SHADOW`.

They may expand retrieval or produce shadow reasoning/diagnostics on the same causal prefix. They cannot replace S135, become the sole source path, mutate the brain, or own/alter the primary lock.

## 14. Sealed October answer feed

- Existing October Step-1 seconds.
- Populations.
- Crosswalks.
- Receipts revealing target membership.
- Labels and classifications.
- Result prefixes.
- Reconciliation outputs.

Authority: `SEALED_TARGET_ANSWER`.

This feed is mechanically inaccessible until all primary discoveries, helper evidence, probability movies, and first-lock/no-lock ledgers are immutable. It is used only for post-freeze reconciliation and gap diagnosis.

## 15. Immutable output and receipt feed

- State movie and state-delta movie.
- Helper-evidence movie.
- Frankie reasoning movie.
- Probability movie.
- Candidate discoveries.
- First locks and no-locks.
- Abstentions, weak findings, negatives, sparse cases, and inconclusive cases.
- Knowledge retrieval receipts.
- Provider invocation/response receipts.
- Answer-wall access receipts.
- Source, state, manifest, code, model, and run hashes.

These outputs are part of the experimental data and must remain append-only.
