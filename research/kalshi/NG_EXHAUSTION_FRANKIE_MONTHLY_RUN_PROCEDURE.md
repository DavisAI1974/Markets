# Canonical Frankie month-at-a-time procedure

Version: 1
Adopted: 2026-08-24

This is the permanent first-read procedure for every Frankie monthly-run handoff. A handoff may supply
month-specific identities and explicitly approved exceptions, but it must not copy, weaken, or silently
fork this procedure.

## Required handoff header

Every new monthly handoff must place this block immediately after its title and before dates, branches,
scope, or implementation instructions:

> **Required first read:** Read and obey
> `research/kalshi/NG_EXHAUSTION_FRANKIE_MONTHLY_RUN_PROCEDURE.md` in full before this handoff.
> This handoff supplies month-specific identities and exceptions only. If it conflicts with the canonical
> procedure, stop and resolve the conflict explicitly rather than silently choosing one.

## Normal rollover rule

After the one-time generic framework is complete, a normal month changes only:

1. One content-addressed month descriptor.
2. One frozen prior-knowledge source declaration.
3. Generated frozen-knowledge and exact-SHA launch receipts.

Runtime, scientific logic, helper concurrency, CPU mapping, lane order, ledger/journal behavior, workflow,
and generic tests remain byte-identical. A raw-manifest, schema, dependency, model, CPU-topology, authority,
or scientific change is a separate reviewed release, not a monthly rollover.

## Provider-cost architecture changes

Replacing the four paid helper calls with local Nucleus processing is a separate architecture release, not
a monthly rollover. Until a blinded shadow comparison accepts that release, the existing four-helper CPU
mapping and Frankie-after-join contract remain authoritative.

A candidate Nucleus release must keep both lanes isolated on the identical immutable prefix, keep the target
month and Step-1 answer wall sealed, and emit content-addressed source/omission receipts that Frankie can
audit. The preferred cost target is one Frankie synthesis per lane after Nucleus produces structured
recurrence, extension, timing, and context sections. Validate it on only 1-2 frozen prefixes before any live
month is authorized. Do not relaunch October merely to evaluate this architecture.

## File policy

### Change each month

- `research/kalshi/config/ng_exhaustion_frankie_fullstack_YYYYMM.json`
  - Exact UTC half-open interval and month ID.
  - Manifest-selected predecessor identity.
  - Exact target roster/hash/count and raw-manifest identity.
  - Prior-learning declaration identity.
  - Artifact namespace and first-evidence canary size of 1 or 2.
- `research/kalshi/config/ng_exhaustion_frankie_frozen_knowledge_sources_YYYYMM.json`
  - Immutable provider-visible prior-learning sources, byte ranges/lengths, hashes, authority classes,
    freeze identity, and proof that target-month answers are excluded.

### Generate; never hand edit

- `research/kalshi/receipts/NG_EXHAUSTION_FRANKIE_FROZEN_KNOWLEDGE_YYYYMM.json`
- `research/kalshi/launch/NG_EXHAUSTION_FRANKIE_FULLSTACK_YYYYMM_LAUNCH.json`
- Per-run `PREFLIGHT.json`, lane ledgers, causal journals, event/progress log, and `FINAL_RECEIPT.json`.

### Do not change during a normal rollover

- Runtime contracts and adapter.
- Causal journal tools and paired-lane orchestrator.
- Generic monthly runner and workflow.
- CPU/concurrency, monthly-contract, and workflow/receipt tests.
- Helper mapping, lane authority/order, receipt schemas, progress arithmetic, and exact-SHA gates.

## Required sequence

1. **Freeze the prior month.** Require final progress 100/0, valid causal/evidence chains, and a frozen
   learned-knowledge pack/receipt. An incomplete run cannot become knowledge authority.
2. **Author the next-month descriptor.** Bind exact dates, lawful predecessor, complete target roster,
   object count, raw-manifest hash, prior-learning declaration hash, and artifact namespace.
3. **Declare prior learning.** List and hash every provider-visible frozen source. Keep target-month answer
   artifacts mechanically sealed.
4. **Generate the knowledge receipt.** Canonicalize sources and actual bytes; independently recompute the
   aggregate knowledge and receipt hashes.
5. **Validate immutable replay inputs.** Require deterministic source ordering, monotone causal cutoffs,
   and one prefix/snapshot hash shared by both lanes.
6. **Run the narrow prelaunch gate.** Run at most two focused nodes. Do not rerun broad settled suites or
   unchanged science/integration tests.
7. **Publish month inputs.** Commit only allowlisted month declarations and the generated knowledge receipt;
   refetch and stop on genuine remote drift.
8. **Generate the launch marker.** Bind the exact fetched implementation SHA, branch, descriptor, knowledge,
   framework, manifest/roster, model, CPU map, scope, and authorization.
9. **Publish marker as the next fast-forward.** Its parent must be the exact remote implementation commit.
10. **Prepare the isolated unit.** Verify package/wheel hashes; extract; restore provider-readable repository
    traversal; perform the unprivileged offline install; reapply restrictive permissions; require CPUs 0-3;
    start systemd with `CPUAffinity=0 1 2 3`; verify the unit and MainPID effective set exactly.
11. **Run each paired prefix.** Control lane first, combined lane second. Within one lane run recurrence on
    CPU 0, extension on CPU 1, timing on CPU 2, and context on CPU 3 concurrently on the identical immutable
    prefix. Frankie is call five and starts only after all four helpers finish. Never run eight helpers across
    both lanes.
12. **Gate first live evidence.** The first `PAIRED_PREFIX_ACCEPTED` event must durably bind both lanes' full
    affinity/timing receipts, four distinct native thread IDs, singleton affinities, helper overlap, no lane
    overlap, identical prefix proof, progress, knowledge/descriptor hashes, and sealed wall.
13. **Observe the canary while the run continues.** Report the first 1-2 accepted prefixes and completed/
    remaining percentage. Do not create a stop/resume identity boundary merely for the canary.
14. **Close the month.** Continue monotonically to 100/0, validate every chain, write `FINAL_RECEIPT.json`,
    and freeze the learned pack used by the following month.

## Permanent execution invariants

- `S135_CONTROL` is primary and completes before `FULL_PROVISIONAL_COMBINED`, which remains shadow-only.
- Both lanes use the identical immutable causal prefix and decision-state snapshot.
- The role-to-CPU mapping is recurrence=0, extension=1, timing=2, context=3.
- Only directly shared append surfaces are thread-safe; immutable inputs remain shared read-only.
- Every receipt is canonical/content-addressed and independently recomputable.
- Progress is monotone, done plus left equals total, and completed plus remaining equals 100%.
- Provider calls are forbidden until config, knowledge, CPU, package, and unit-affinity gates pass.
- Failures receive the smallest observed-path correction plus 1-2 focused tests; do not reopen settled work.

## Handoff completion checklist

A monthly handoff is incomplete unless it names the descriptor path/hash, prior-learning declaration and
receipt hashes, raw-manifest/roster identity, target branch, expected implementation/marker ancestry, focused
test nodes, artifact namespace, canary size, progress source, isolated stop command, and any explicit exception
to this procedure.
