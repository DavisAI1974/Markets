# Detailed continuation handoff: BOTH teachers' Dipole coverage — 2026-10-06

## Start here: current checkpoint

Repository: DavisAI1974/Markets
Working branch: `ccr-5fce7de3-xa4hfg`
Last verified remote base before this final source/handoff batch:
`e75792b47244ce9f699bde2cb6bc9950a509e5c8` (latest CCode fix merge; preserves `54c75fb`).

This handoff is committed with the final raw-retention/BOSS-input-count changes described below.
Fetch the CURRENT branch first; its commit containing this handoff is newer than the base above.
Preserve every newer commit, including CCode's. Do not reset to any older SHA in this document.
Greg asked to finish the work underway, finish the stopped agent's work too, and leave a detailed
handoff before usage ran out. The bounded source work is finished; full coverage is NOT complete.
No agent task or partial implementation needs to be resumed from memory.

**SOURCE-BUILT / RUNTIME-UNVERIFIED. STOP BEFORE WORKFLOW #5.**

## Latest reserved search fix after `6cf36b3`: exact event-group membership

Source review found that `events.*` action/side counts and size sums used one global open-group
accumulator, then timestamp as-of placement. Interleaved instruments could share the wrong bucket;
distinct closes with the same full nanosecond timestamp could select a later group's counts. The
timestamp includes its date; it is simply not a unique group identity. `events.last.*` also relied
on a global raw F_LAST sequence matching every successful ROOT frame.

`experiment_search.build_series` now reuses `experiment_journal._frame_index` and ROOT's original
`input_record_indices`/`input_cursor`. Only a frame's recorded members contribute to its counts and
numeric-size sums, and its exact closing record supplies `events.last.*`. INPUT and frame spool
bytes/hashes must match the selected export. Instrument, closing stamp/flag and complete membership
are checked; there is no timestamp selection, second ingest, adapter replay or new trajectory definition.
Integer counts and integer-size sums stay exact Python integers rather than passing through float.

The existing numerical sum still includes only numeric sizes; per-group unknown-size counts now
make incomplete sums explicit alongside the whole-source count. Original records remain retained.
Source `group_binding` reports grouped records, exact inclusive unplaced INPUT-index ranges,
frame hash and membership helper identity. Older exports without group membership are listed as
unsupported for these aliases instead of guessed. Other existing projections remain as supplied.
Raw F_LAST counts and tail diagnostics are distinct from successful ROOT group counts.

Existing transforms, lag units, coupling/chance formulas, targets and masks are unchanged. Search
continuation already binds this module and the journal helper, so incompatible pending arrays refuse;
completed old results remain unchanged and are not rerun or claimed corrected. Verification was direct
producer/consumer/recovery source review, AST syntax without imports, and whitespace only. No tests,
synthetic exercises, model/data/scientific runs, installs or AWS actions occurred. Runtime remains open.
CCode ownership is unchanged; this touches the reserved search module and shared documentation only.

## Latest continuation after `7d10fa5`: raw availability repaired; expanded CCode ownership

Current source fix: `frankie_box_experiment_dipole.py` V3 creates a numerical projection of each
placed source row without mutating the original snapshot. Only raw component numeric `.value`
leaves whose producer state is not an integer PRESENT become None. Both positional rows and
entity closing aliases use that view. PRESENT zero, incomplete-but-PRESENT values, all other
numeric metadata, original state/reason fields and DState remain available under existing semantics.
There is no 19-component input whitelist and no target/mask/formula change.

The source report's `raw_value_projection.unavailable` groups affected observations by component,
producer state and reason, with paired inclusive source ordinal/cursor ranges. It counts each original
observation once across aliases. Original values remain in the hash-bound snapshot. Unplaced rows
retain the existing separate dispositions. The manifest notes point to that exact accounting.

Recovery now binds V3/helper bytes and the producer State module in the existing search identity.
Old pending prepared arrays are refused on identity mismatch; completed searches remain unchanged
and are not rerun or declared repaired. Checks: direct source/interface review, AST parse without
project imports, and git diff --check only. No behavioral or performance validation was performed.

Greg asked to give CCode as much work as possible to conserve Codex usage. The NEW top section of
`CCODE_NEXT_SOURCE_TASKS_20261006.md` transfers the remaining pre-#5 queue to CCode, including
teacher_knowledge/exchange caller edits and historical binding support previously reserved for Codex.
It also covers existing native semantic consumers, model/trajectory plumbing and late-delivery gaps
only where current contracts define the semantics. CCode must preserve all held decisions and execution
restrictions. Codex retains the two current search modules and shared handoffs, then reviews/integrates
CCode returns. Older ownership statements below are historical where this assignment supersedes them.
The task document is ready for Greg to pass along; this is not evidence CCode has started it.

Step #1 remains source-built. Steps #2–#4 remain incomplete: the assigned work aims to close major
delivery/computation gaps, but missing definitions, full original-calculation reproduction/repair
capabilities, native model consumers and identity trajectories still require concrete resolution.
No reliable completion percentage or runtime readiness is established. Require CCode's return to
name each remaining blocker against the existing contracts, not infer completion from file counts.

## Non-negotiable instructions from Greg

- Fix actual computational input coverage for BOTH BOSS and scientific teachers. Storage, catalog
  counts, references and status summaries are not proof of computation.
- The 19 output/target columns must never become a ceiling on applicable input evidence.
- Claude's old dead/no-good/rejected/discarded labels are claims, not scientific truth. Both teachers
  must reproduce applicable original calculations, investigate failure causes, and attempt repairs
  or reformulations. Nothing closes merely because Claude rejected it or a stored-count reassessment
  produced a disposition. Preserve original evidence, rationale, scope and pending work.
- CCode builds the teachers' capabilities; he does NOT personally rerun, rework or judge the research.
  The same separation applies to this source-only Codex work. Teachers perform scientific work only
  when execution is separately authorized.
- No tests, project imports/execution, installs, model/runtime downloads, model calls, data/scientific
  runs, canaries, E2E, AWS actions, box starts or workflow dispatch. Keep the boxes stopped.
- Syntax parsing and source/interface/whitespace review only. No source-built/runtime-verified conflation.
- Preserve formulas, targets, validity semantics, source identities, private trading-logic walls,
  teacher/student answer walls and Jev's blind wall. No new labels, weights, objectives, optimization
  order, acceptance/survivor rules, arbitrary minima or enabled producers.
- Preserve the planned three held 16-CPU lanes, 15 workers plus coordinator, and owner-local giant
  evidence. Do not reopen Granite model pins or parameters, including `threads: null`.
- STOP before #5; freeze/evaluation draft remains unapplied. Jev CPU discussion remains pending.
  E2E and the thirty-day launch need separate authorization.
- Use `[skip ci]` on commits. No Codex attribution.

## Read next, in order

Paths are under `research/kalshi/frankie_boss/` unless prefixed otherwise.

1. Repository `AGENTS.md`, then this file.
2. `DIPOLE_TEACHER_COVERAGE_CONTINUATION_20261006.md`: exact source changes and limitations.
3. `CCODE_NEXT_SOURCE_TASKS_20261006.md`: current ownership and concrete follow-up defects.
4. `CCODE_HANDOFF_CODEX_DIPOLE_TEACHERS_20261006.md`.
5. `CCODE_DIPOLE_COMBINED_COLLECTION_20261006.md`.
6. `CCODE_STEP4_SOURCE_ROUTE_20261006.md`, section 7.
7. `HANDOFF_20261006_SUCCESSOR_AND_FULL_EVIDENCE.md`,
   `ROOT_PLANE_COVERAGE_20261006.md`, `KNOWLEDGE_CONSUMER_COVERAGE_20261006.md`.
8. `GRANITE_INTEGRATION_RECOVERY_20261006.md` for the authoritative ten-step workflow.
9. Current experiment directive/rules, native-learning decisions and relevant original specifications
   before changing calculation semantics. Older reports saying a caller is absent may predate these commits.

## Commit history and what is actually integrated

| Commit | Status and change |
|---|---|
| `03f29be` | Earlier base: CCode cached archive/GGUF verification fix; preserves Granite integration. |
| `7bef0c5` | Full DState and raw-detail snapshot/exact-cursor search retention. |
| `b129dc6` | Owner-local candidate scientific testing and publication connected to teacher exchange seats. |
| `3e0a6f0` | Historical research explicitly open for reproduction/rework by both teachers. |
| `21df8f1` | User's starting checkpoint/handoff; preserved. |
| `4c5b5ad2d83dcd1934107ac0ef1994260619727a` | Deferred raw-worker replacement preserves parent incomplete/book-integrity and unknown-side annotations; recovery binds resolver source digest. |
| `2135bc1e40574709ed2c264981283d7516d940d3` | Stable entity-scoped closing-row input projection; classroom scope descriptions corrected. |
| `42239c098090763d1688b2b37e0fe1a2634c22a7` | Real two-parent merge: first parent `2135bc1`, second parent CCode `b264f7946b78200c9d47f7810ea6d325640b37ad`. All seven incoming CCode blobs preserved. |
| `54c75fb341cbc342494d472edef6436b823b1489` | Combined collection default for new plans; reconsideration/native keys retained and delivered to both seats; CCode follow-up doc pushed. |
| `e61a382b4cd1c60454013092ee0ef8a9009e782e` | CCode return based on `42239c0`: exact part/ordinal/raw-line origin binding and reversed origin-row retention. |
| `e75792b47244ce9f699bde2cb6bc9950a509e5c8` | Two-parent merge of `e61a382` onto `54c75fb`, preserving our newer shared-caller work. |
| Commit containing this handoff | Raw retention independent of DState; separate BOSS descriptive calculations over exact retained numeric input leaves; both seats and lawful Frankie reply receive them. |

**Do not integrate discarded draft `9c19cc2e7b1232f81b984b074ffb9690991b2d08`.** That overlapping
candidate-origin draft was never attached to the branch. Greg said CCode was already doing that work;
it was set aside. Its commit object is not accepted integration. Reconcile fresh requirements instead.

### CCode merge contents

CCode branch `ccode/dipole-collection-20261006` was cut from `21df8f1` and contains:
- `7c555fe`: combined catalog/builder/claims.
- `046361e`: reconsideration statuses, reversed-orientation deduplication, initial origin-part binding.
- `728f1f7`: completed-native evidence packaging.
- `b264f79`: handoff.

His seven changed files were scientific_teacher.py; three CCode documents; combined catalog;
combined claims; and operations/build_dipole_combined_catalog.py. His candidate adapter and launcher
were reviewed but unchanged. The 52,948,574-byte claims blob was preserved directly, not rebuilt.

CCode reports: **1,538 sources across 199 branch tips; 82,372 candidate statements; 10 mapped
crosswalk claims; 82,365 not_testable entries**, including 81,655 awaiting_teacher_binding and
710 code_source_constructions. These are source categories, not asserted disjoint percentages.
The collection is much larger; computational mapping remains tiny. Codex did not run its builder.

## Completed source paths and their limits

### 1. Capture and deferred-worker annotations

`parallel_teacher.row_pass(retain_dstate=True)` snapshots the existing per-entity DState after its
original F_LAST update. It preserves exact rational numerator/denominator fields and row identity.
NOT_F_LAST rows do not invent a state transition. Host and lawful learner use separate machines.
The resolver retains parent incomplete/book-integrity counts and unknown-side count/volume when
worker results replace deferred placeholders; numeric values/state/reason and R3 mask handling remain.

Raw-pass and attachment recovery bind the parallel_teacher source SHA256. Incompatible partial state
is refused/preserved. No old completed artifact was rerun, migrated or silently replaced.

### 2. Snapshot retention independent of optional DState — final batch

`dipole_classroom.snapshot_teacher_attachment` previously copied raw_components only inside its
optional dstate_rows branch. The ordinary parallel_attach route can omit DState, despite possessing
raw evidence. The raw-components loop now always runs for valid raw rows.

Existing DState-enabled snapshot content is unchanged. Newly materialized snapshots without DState
gain raw precision, reasons, incomplete and unknown-side metadata, with a new snapshot hash.
No DState is fabricated. Existing serialized snapshots remain readable without backfill.
The experiment teacher already requests DState, so its completed/retry shape is unchanged.
General classroom runtime recovery was not verified; do not re-pin old source hashes to force reuse.

### 3. Stable closing-row search inputs

`deploy/aws/box/frankie_box_experiment_dipole.py`, schema V2, now keeps both:
- All positional intermediate rows under `dipole.group.rows[slot].*`.
- Whole exact closing rows under `dipole.group_close.by_entity.<publisher>:<instrument>.*`.

This fixes field fragmentation when the closing row moves between list slots as group sizes change.
APPLIED cursor/prefix/time/entity and DState closure are checked. Source review of c15_builder proved
receipt/frame closure equivalence; the journal reader refuses earlier closes in a group.

All scalar leaves reach the existing numeric/categorical transforms; the 19 targets are unchanged.
No fill, interpolation, new axis, statistic or lag definition was added. Other entities/missing closes
remain absent. Aliases are explicitly the same evidence, not additional observations.
Interleaved entities still break adjacent search steps; full identity trajectories remain open.
Helper schema/source digest already bind search continuation identity.

### 4. Truthful classroom descriptions

Shared role strings no longer falsely assert top-three cohorts or a 1,024-group long horizon.
They use selected-cohort and short/long-horizon wording and state that actual scope belongs to the
bound producer. Active teacher_changes uses all levels/whole-day long history; historical pinned
snapshots can differ. Readable exact producer-scope metadata remains a future improvement.

### 5. Collection, lessons and both seats

New experiment plans default to:
`research/kalshi/frankie_boss/knowledge/HISTORICAL_CLAIMS_V1-9dc79ca359e9.json`.
Explicit overrides and existing frozen plans retain their selection.

`teacher_knowledge.teach_accumulated` preserves top-level `reconsideration` and
`completed_native_evidence` unchanged in emitted retest lessons. `lane_state.learner_knowledge`
already carries whole hash-checked documents; its contract now explicitly documents that behavior.

Exchange checks reconsideration against the lesson claims hash, states all collection statuses in
BOTH seats before turn validation/hashing, and preserves producer construction/prior labels in
research_rework. Native references remain scoped to their original day and include declared hash,
counts, receipt, matching rule and listed gaps. Context survives zero-result lessons and obeys
the Jev wall in the Frankie view. This is delivery/citation, not a new native semantic calculation.

### 6. BOSS input computations beyond the target ledgers — final batch

The stopped agent completed source review but hit credits before editing. Greg then instructed
Codex to finish his work; Codex implemented and source-reviewed this route.

In `frankie_box_experiment_exchange.py`:
- teacher_rows retains source snapshot rows beside the unchanged 19 target ledgers.
- retained_evidence_counts resolves exact closing-row entity paths only:
  `...raw_components.*` and `...dstate.state.*`.
- It validates ordered causal cursors, cutoff, DState schema, row cursor/time/prefix, publisher/
  instrument, and closing-state shape. No identity is guessed for sources lacking DState.
- Existing scalar projection and classroom _direction/_co_movement arithmetic compute descriptive
  directions and same/opposite/one-sided/neither movement counts. No new coefficient/average.
- A raw component.value requires its producer PRESENT state. Non-PRESENT placeholder zeros are
  unavailable, not observations. Numeric metadata such as incomplete counts has its own availability.
- Only same-entity fields pair. Temporary arithmetic presence is numeric availability, never target
  validity. Results use availability terminology and remain separate from target-mask proposals.
- Both seats receive the same source-bound counts in unresolved evidence checks. The scientific
  seat reading them is not a second measurement. Lawful Frankie's reply/sidecar/citations retain them.
- No raw result enters joint empirical findings, survivor promotion, a claim verdict or new targets.
  Ledger storage is per claim, not an ever-growing whole-day cache.
  Arithmetic helper source hashes travel with the counts, and accumulated-exchange input identity
  now binds both the classroom arithmetic and generic scalar-projection modules.

Precise limits:
- Existing teacher co-movement bridges unavailable rows via successive available observations.
  Search transforms require adjacent available F_LAST cells. No axis equivalence is claimed.
- This is descriptive accounting of the retained snapshot, not a test of a claim's cell, transform,
  lag, causality, predictive/economic result or original research reproduction.
- Numerator/denominator leaves remain separate quantities. Target normalized units are not inherited.
- Categorical flags/state/masks, group identities, text, nonfinite/absent fields, positional aliases,
  cross-entity pairs and mixed target/raw pairings are explicitly listed as unsupported here.
- No producer activation, new scientific meaning for numeric flags, native model training or
  full-input semantic coverage is claimed.

## Remaining work, prioritized and owned

### Raw placeholder projection: source-fixed by the latest continuation above

Confirmed source path:
`c15_teacher_r3._value` emits value=0 for non-PRESENT states ->
snapshot raw_components retains it ->
experiment_dipole passes whole rows to search.columns ->
experiment_search.build_series inserts every returned numeric channel ->
transforms._steps treats finite zero as a known value.

The governed `dipole.<target>` channels DO check component PRESENT, but the new raw nested .value
channels do not consult raw producer state. The final BOSS route fixes this for its own calculations,
not for the generic search. Do NOT carry this mistake forward.

Implemented repair: preserve original raw bytes/state/reasons, but make numerical projection of a
raw component.value honor the producer's declared absence; list affected source cursors/reasons.
Do not mask independent numeric metadata just because its associated component has no value.
Do not discard meaningful present values with incomplete annotations, invent zero fills or change
formulas. Review both positional and closing-row projections and recovery identities. No tests/runs
under the standing hold. The latest V3 continuation implements this repair; runtime verification remains open.

### CCode-owned follow-ups already recorded in his Git document

Read the top section of CCODE_NEXT_SOURCE_TASKS_20261006.md:
1. SOURCE-FIXED in CCode `e61a382`, merged as `e75792b`: actual origin rows now bind their part
   SHA256, zero-based ordinal and raw-line SHA256. Every read result names its exact where record;
   missing discovery-row identity is listed. The producer convention is raw-line, not reconstructed
   canonical-JSON hashing. Codex source-reviewed the exact reader diff; no test/data run occurred.
2. SOURCE-FIXED in the same return: origin handling runs before mirror skipping. Reversed
   discovery-day rows remain in origin_evidence with mark origin_evidence_mirror and mirror_of.
   They remain outside tests. The separate review of mirror chance-identity fields remains open.
3. STILL OPEN: discovery-day skip in teach_accumulated and origin_evidence arithmetic in both seats.
   Codex owns those caller changes; coordinate against the now-fixed exact reader contract.
4. STILL OPEN: distinguish completed-native packaging/citation from semantic computation and identify exact
   supported consumers/missing definitions. Accumulated candidate-only lessons do not automatically
   generate the current day's native evidence.

User has the GitHub task-doc link and said he will pass it along. No private message or external
notification was sent to CCode. Do not overlap his scientific_teacher/candidate_claims/launcher work.

### Broader coverage still incomplete

- CROSSWALK has only 10 mapped historical claims. Faithful binding of existing source calculations,
  original reproduction and repair/reformulation capabilities remain major work. Status reporting
  does not implement those computations; unmapped claims remain open.
- Original BOSS TeacherHead/native-model representation and training consumers remain incomplete.
- Full identity-linked order/book trajectories and categorical semantics remain incomplete.
- Completed result/4.2/4.4/FINALIZE products need real lawful semantic consumers. They cannot be
  projected backward onto live frames. Averages stay labelled supplements.
- Late knowledge does not automatically reopen completed days. Preserve existing boundaries/recovery.
- Old completed sources retain old coverage. No rerun, migration or fresh-state supersede authorized.
- New source-built routes have no runtime verification and no performance measurement.

### Decisions still held for Greg

- Definition of which group close owns a 4.4 pair completion.
- Definition, if any, of a search step for a 4.2 two-point session summary.
- Whether to split the 52.9 MB combined claims file. Currently kept intact.
- Whether principal_inputs should switch its separate Sept 22 retrieval catalog to the combined one.
  The teacher plan default changed; the principal retrieval catalog did NOT.
- Nonlinear/multivariable discovery, disabled producers, native objectives/optimizer ordering, late
  scheduling choices and workflow #5 remain separately governed; do not silently decide them.

## Ten-step workflow status

| # | Work | Current status |
|---|---|---|
| 1 | Linux ownership and retained-day save/resume | Source-built; runtime unverified. |
| 2 | Actual lawful knowledge delivery to learner computation | Partial; today's routes add coverage, not completion. |
| 3 | Native-field search, transforms, conditions, targets, Dipole, symbolic discovery | Partial; raw placeholder projection source-fixed; trajectories and semantic coverage remain open. |
| 4 | Candidate/survivor batches and scientific checks | CCode origin-reader fixes merged; discovery-day caller/consumer and actual rework gaps remain. |
| 5 | Discuss freeze/evaluation with Greg | STOP boundary; preserved draft unapplied. |
| 6 | Granite integration/decisions | Named source wiring built; host/transport execution, knowledge scope and runtime verification open. |
| 7 | Jev blind comparison and tested-knowledge publication | Discussion pending. |
| 8 | Three-lane launch/status/resume/stop and controller lifetime | Main save/resume work remains open. |
| 9 | One real ROOT-to-finish E2E | Not run; needs explicit authorization after wiring/discussion. |
| 10 | Thirty-day launch | Not launched; needs separate authorization. |

Do not cross off #2/#3/#4 or claim all 99-registry computation is complete.

## Verification actually performed

- Direct source/interface review of capture, producers, snapshots, search projection, teacher arithmetic,
  source binding, per-day scope, masks and Jev/answer walls.
- Agent reviews identified closing-row slot fragmentation, stale classroom scope, raw/DState capture
  coupling and the BOSS 19-ledger gate. Two agents later errored on workspace credits.
- Codex completed the final BOSS implementation and final review; do not claim independent review
  of its finished patch or behavioral validation.
- Python ast.parse on changed modules, without project imports. Whitespace diff checks.
- Git ref/merge parent/blob identity checks. Complete-base-tree commits, [skip ci], expected-head lease.
- No tests, synthetic exercises, model/data/scientific runs, installs, AWS actions, starts, dispatch or E2E.
  No infrastructure status recheck is claimed.

## Workspace and continuation mechanics

Current partial source snapshot:
`/workspace/scratch/930896a7f725/Markets`
Exact local comparison baselines:
`/workspace/scratch/930896a7f725/Markets-baseline`

This is NOT a Git checkout. Some producer/spec files were read directly at exact GitHub refs and are
not local. Do not infer that a missing local file is absent from the repository. Refresh current GitHub
source before edits. CCode's large catalog/claims blobs were merged by exact Git tree identity; they
were not downloaded into this partial snapshot or executed.

GitHub connector publication: create blobs, create a tree over the COMPLETE current base tree, create
a commit with the current parent, then update_ref(force=false, expected_sha=verified_head). Reconcile
newer commits on lease failure. CCode merge used additional_parent_shas to preserve both histories.
Verify the branch ref after publishing; unreferenced commit objects are not pushed changes.

Markets Terminal Read Only previously failed with a stale tunnel-client error. GitHub remained usable.
No AWS tools were invoked in this continuation. No codebase-memory MCP was available; source was read directly.

Greg requested using-agent-skills. Earlier in this conversation the skill was read from
addyosmani/agent-skills at exact tree `1401c8b8030e023baeebb31781a6653fe8e93026` after the requested
v0.6.7 ref was unavailable; context-engineering, incremental-implementation and git-workflow-and-versioning
were also read. User no-test/no-run instructions take precedence over skill test guidance.
Greg explicitly authorized agents; their credit errors are not evidence of a completed runtime check.

The discarded origin draft is in `/workspace/scratch/930896a7f725/unpublished-origin-patch/`.
Leave it unapplied. No repository files are duplicated into Library.
