# Detailed continuation handoff: BOTH teachers' Dipole coverage — 2026-10-06

## Latest integration review — CCode A–D and the provenance handshake (2026-10-06 late)

CCode return `fea2e165a3cf721760db0ac2932cf2c4ab0be859` is retained atop integration
`80a0e2793e3cfb9cb8a2a06e03c08bed22d041fa`: A `c31cad06`, B `7cb2ce52`,
C `11082ff8`, D `2a05c147`, plus CCode's handoffs. This is source integration with
explicit unresolved defects, not completed coverage or reproduction acceptance.
Read the NEW TOP SECTION of `CCODE_NEXT_SOURCE_TASKS_20261006.md` before CCode resumes.
It supersedes the older A-only follow-ups and the returned slice-closure claims.

Codex traced the D producer through `InstrumentBook.apply`: legacy trade rows accumulate
until the instrument's F_LAST close. The returned price provenance stamps ALL of those rows
with that closing INPUT's index, not their actual originating INPUT. Thus the promised price
identity is wrong. CCode owns the narrowly necessary producer correction, including retained
group state and receipt/recovery versioning. Never repair this by a timestamp or spool-position
join. Search explicitly lists all price ordinals as `price_original_input_identity_pending`;
the original price timestamp aliases and their exact unselected-row ranges remain.

The structure contract is usable: reserved search now adds `structures.group.*` by original
closing INPUT cursor, instrument and the complete exact ROOT group member list, reusing the
journal's existing membership reader. Its receipt is selected and hash/size checked against the
export manifest; old/missing producer/membership information gets exact source-ordinal
dispositions. Conflicting identities refuse. No clock join, forward fill, interpolation, pooling
or replacement of the original `structures.*` aliases. Missing group values remain missing.
Provenance metadata on BOTH prices and structures is excluded from numerical channels and
text cells and retained in pinned evidence/reports. Alias collisions refuse. Duplicate
representations are not independent observations or new lag/trajectory semantics.

CCode corrections queued with source trace and disjoint ownership:
- D1: original trade INPUT provenance (first, to unblock Codex's exact price adapter).
- A4: aggregate discovery identity must survive unavailable arithmetic without becoming a test.
- B1–B6: full stderr/comparison evidence; immutable reference vs fresh output separation;
  pre-dispatch operation/retry identity; full source/input/entry record binding and accurate
  performed statuses; frozen owner-local record selection; exact external-input supply gap.
- C1: identical completed-native content at different materialization paths must not conflict;
  preserve owner-manifest provenance and report the actual scope of emitted results.

A's earlier three follow-ups are source-present. Late knowledge remains receipt-only at frozen
boundaries. B does not yet establish safe runnable reproduction; no historical calculation or
repair has been performed. H06–H08 remain historical/not_bound: Greg retired Memory A.
Other historical rejection/no-good labels remain open for BOTH teachers' reproduction/rework.
Steps 2–4 remain incomplete; the 19 outputs do not cap evidence.

Checks here: source/interface review, AST syntax without project imports, whitespace only.
No tests, examples, installs, project/data/model runs, historical reproduction calls, AWS
actions, starts, dispatch, canaries or E2E. Codebase-memory MCP/CLI unavailable in this workspace;
direct source review used. SOURCE-BUILT / RUNTIME-UNVERIFIED. Keep boxes stopped.
STOP before #5; preserve its unapplied draft and Granite pins (threads null); never `9c19cc2`.
Fetch current HEAD and preserve newer commits; the hashes above are reviewed checkpoints.

## Latest reserved continuation — timestamp selection dispositions, after `1f8d64e1`

Fetched integration `1f8d64e18c2389ced9f570a02a95da994bd7f085`; CCode still at `a9625ae2`,
with no new source beyond the already integrated partial Slice A. His handoff-only commit remains
unmerged; its overbroad closure claims still do not supersede the three assigned corrections.

Following Greg's no-silent-optional-omission question, Codex traced the existing timestamp-asof
selection in its reserved search module. Valid-clock rows can receive no frame position: an earlier
tie loses to a later source row, or another source row arrives between that row and the next frame.
Previously only unusable clocks were explicitly counted. `asof_source_rows` now supplies the same
original source ordinal selection to `asof_values` (including leakage-gate calls) and the accounting.
Manifest notes give exact inclusive unselected-clocked-row ranges, counts, source identity and reason;
the existing disposition log surfaces the gap. Missing-clock ranges remain separate. These are
alignment counts before per-field gates, not measured/valid observations or extra evidence.
Price/structure source entries now explicitly identify their timestamp aliases and unresolved exact
INPUT/group/entity joins. Their formulas, tie rule, axis and values are unchanged. Original evidence
remains retained; this exposes an omission and does NOT supply the pending exact join or claim full
computation. CCode's source-bound original INPUT-index/instrument producer is still required.

Source/interface review, AST syntax and whitespace only; SOURCE-BUILT / RUNTIME-UNVERIFIED.
Existing search code identity refuses incompatible pending arrays; completed results remain unchanged.
No tests, synthetic examples, installs, project/model/data runs or AWS actions. Stop before #5.

## Latest Codex source continuation — selected export binding and optional-source visibility

Started from fetched current `8bb4c0d33245972817e68e23c5e0218d986de08f`, preserving the newer
documentation checkpoint above Greg's supplied `cb7acc40`. Only the reserved search module and
shared handoffs change. CCode's latest observed branch remains `a9625ae2`; no new implementation
from that branch is claimed integrated. Fetch current refs again before continuing.

The previously reserved manifest-binding gap is now SOURCE-BUILT / RUNTIME-UNVERIFIED:
- `build_series` selects unique stage/path pins from the existing export manifest. Frames are
  checked unconditionally; structures, prices and INPUT spools are checked against byte count and
  SHA256 while their original UTF-8 lines are decoded with the existing codec. Full exhaustion is
  required before preparation can return/save. No extra giant-spool hashing pass is introduced.
- Signed-flow and roll20 JSON are decoded from exactly the bytes checked against their export pins.
  The external day file and optional companion receipt are independently export-bound; their mutual
  hash check and the existing AsOfReader validation/publication-clock policy remain in force.
- The preparation call receives the continuation's selected manifest hash and verifies it before
  and after preparation. Publication checks and records that same hash instead of pinning a later
  manifest. Existing code/manifest recovery identities refuse old incompatible prepared state.
  New compatible prepared arrays are reused without rereading/recalculating raw evidence: their
  original source reads were already checked. This is not a fresh proof of current disk bytes.

Greg then asked whether optional sources could silently be passed over. Concrete fixes in this slice:
- Selected-but-missing INPUT/Dipole paths remain discoverable from the manifest and refuse clearly;
  they cannot become an optional absence because filesystem globbing no longer finds them.
- External file discovery follows the selected ingest path, including nested catalogued paths.
  Multiple day files refuse instead of picking or merging one. Existing physical files absent from
  the selected export are not silently consumed. No export is expanded or rewritten.
- A genuinely absent optional source is listed in manifest notes AND the source-disposition log;
  other available evidence continues. Missing does not mean zero, fulfilled coverage or permission
  to waive the source. Selected files with missing bytes, changed hashes or ambiguous pins refuse
  preparation; all retained work stays intact. No new completeness/survivor policy is invented.
- Empty signed-flow/roll20 inputs are explicit. A retained roll20 series without an integer
  `first_second` lists every unplaced original ordinal, including boolean-clock rejection, rather
  than silently bypassing the values. No clock, observation or numerical result is invented.

Source/interface review, AST syntax without project imports, and whitespace checks only; no tests,
installs, synthetic exercises, model/data/project runs, AWS actions, starts, dispatch, canaries or E2E.
No current infrastructure status check is claimed. No codebase-memory tool was exposed; direct source
inspection was used. STOP BEFORE #5; its draft and Granite pins remain untouched; discard `9c19cc2`.

Next Codex work: review/integrate CCode returns and wire exact price/structure joins only after his
original INPUT-index/instrument producer contract returns. CCode retains the full A/B/C/D queue,
including all three Slice A corrections. Do not duplicate his work. Steps #2–#4 are still incomplete.
The sections below describe earlier checkpoints; the manifest-binding investigation is no longer open.

## Earlier documentation checkpoint — preserved history

Repository: DavisAI1974/Markets
Working branch: `ccr-5fce7de3-xa4hfg`
Last verified remote base before this documentation-only checkpoint:
`cb7acc402380ec9a54a238355127fe14bab55c95` (CCode Slice A integration; preserves all search fixes).

This handoff checkpoint adds no source changes; the completed source changes are already pushed.
Fetch the CURRENT branch first; its commit containing this handoff is newer than the base above.
Preserve every newer commit, including CCode's. Do not reset to any older SHA in this document.
Greg asked to finish the work underway, finish the stopped agent's work too, and leave a detailed
handoff before usage ran out. The bounded source work is finished; full coverage is NOT complete.
No agent task or partial implementation needs to be resumed from memory.

**SOURCE-BUILT / RUNTIME-UNVERIFIED. STOP BEFORE WORKFLOW #5.**

## New-chat checkpoint at Greg's request, 2026-10-06 16:13 ET

Run using-agent-skills and context-engineering. Fetch current HEAD and preserve newer commits.
Read this document, `CCODE_NEXT_SOURCE_TASKS_20261006.md`,
`DIPOLE_TEACHER_COVERAGE_CONTINUATION_20261006.md`, then
`CCODE_STEP4_SOURCE_ROUTE_20261006.md` (including section 7 and later addenda).

Completed source commits: `57c2cb27` raw-placeholder projection; `bbe2d560` exact ROOT event
membership; `59cca0d4` empty-spool/unknown-clock dispositions; `cb7acc40` CCode integration.
No uncommitted source patch was left at this handoff. No tests or execution were performed.

Latest observed CCode tip is `a9625ae2a2e145ea85540f47e542f7bf20e8a1ba` on
`ccode/teacher-tasks-20261006b`. Its only change beyond the integrated source is
`CCODE_HANDOFF_20261006_TEACHER_TASKS_NEXT_CHAT.md`; that document has not been merged.
It says historical slice B is traced but unwritten and slices C/D are not started. Its "Slice A
DONE" and closure-table wording do not close the three concrete source defects recorded below
and in the assignment. Read its historical trace as a reference, not proof of implemented bindings
or scientific reproduction. It reports a Memory A retirement decision in CCode's separate chat;
this checkpoint neither implements that reported decision nor restores any retired runtime route.

Codex's next reserved investigation (source finding, NOT PATCHED): `build_series` hashes
structures/prices, signed_flow, roll20 and external artifacts without consistently comparing them
to the selected export manifest's bytes/hash pins. The export hard-links files; recording a current
hash alone does not establish that it matches the selected export. Frame pin checks are conditional
on the journal/event routes. Trace this narrow inconsistency and reuse existing binding contracts
in the reserved search module; do not add a validator framework or run source/data examples.
Check the existing source/recovery identity when fixing it. No changes to numerical formulas,
evidence, availability policy or historical knowledge admission are authorized by this finding.

The price/structure exact-identity adapter remains pending CCode's producer contract for original
INPUT index and instrument. Do not guess timestamp or positional joins. Full timestamps already
include the date; they do not uniquely identify records or groups. Codex reserves search/dipole
and shared handoffs; CCode owns the expanded A/B/C/D and producer queue. Give him as much of the
remaining implementation as possible rather than duplicating his work.

Steps 2–4 remain incomplete: actual native learner/knowledge computation, identity-linked and
completed-native semantic coverage, and historical reproduction/repair capabilities still have
implementation or definition gaps. Runtime verification remains wholly open. Do not reduce their
remaining work to verification alone or equate assigned work with completed work.

Only source/interface review, AST syntax without project imports and whitespace checks are allowed.
No tests, synthetic exercises, installs, project/model/data/scientific runs, AWS actions, starts,
dispatch, canaries or E2E. Keep boxes stopped. Preserve the unapplied #5 draft and settled Granite
pins, including `threads: null`. Use `[skip ci]`; never apply discarded `9c19cc2`.

## Latest CCode Slice A integration after `59cca0d4`

Incoming branch `ccode/teacher-tasks-20261006b`, exact return
`6e5fb403ac8a1f6ce4c82a2173c7c08b7c9c7054`, based on `bbe2d560`. The two-parent integration
preserves its four exact file blobs and all newer search/clock changes from `59cca0d4`.
Incoming files: teacher_knowledge.py, experiment_exchange.py, scientific_teacher.py and CCode's
Step #4 report. No incoming source was rewritten or research executed during this integration.

The blanket discovery-day candidate skip is removed. The existing reader retains exact origin
part/ordinal/raw-line identities without counting origin rows as tests. The exchange now computes
the existing movement-count complements for current-day origin rows and teaches those in the BOSS
turn and lawful Frankie reply. Both seat sidecars retain the result. Test counts, findings, acceptance,
historical reproduction and the Jev blind boundary remain separate. Mirror equivalence now names
null_exclusion and beyond_chance. The existing changed-module digests refuse incompatible recovery.

**Slice A remains partial:** the scientific teacher's actual record/voice only states origin row counts
and whether the discovery row was found; full arithmetic is in its sidecar, outside `record=science`.
CCode must connect the already-computed origin result to that turn before validation/hashing, without
creating another measurement. Origin teaching also needs the shared route's transformed-zero/missing/
unclassified limitation, and listed arithmetic failures must reach both actual turns. These exact
follow-ups head `CCODE_NEXT_SOURCE_TASKS_20261006.md`. Do not cross off BOTH-seat coverage yet.

Verification: direct caller/reader/arithmetic/recovery/answer-wall source review, AST parse of the
three incoming Python modules without project imports, incoming and local whitespace checks, and
disjoint-path/blob/parent verification. No tests, synthetic exercises, installs, runs or AWS actions.
Steps #2–#4 remain open; stop before #5. CCode retains source ownership for these follow-ups and B/C/D.

## Latest reserved search review after `bbe2d560`: empty/unknown-clock source handling

An empty prices/structures spool previously failed at `num.pop(time_key)`, despite the producer
explicitly permitting no trade rows. Search now lists an empty spool and continues the other sources.
Missing or nonnumeric clock columns use an unavailable alignment view; original rows/clock text remain
in the retained spool. `known_time_rows` gives alignment and its existing leakage gate the same integer
clock selection, excluding booleans. Every source passed through the as-of wrapper with unusable clocks
gets exact inclusive original ordinal ranges in manifest notes. No timestamp is synthesized, and the
remaining properly clocked rows still use the existing as-of policy. No statistic or gate was added.

This does NOT fix price/structure timestamp ties or entity mixing. Source review found their producer
spools lack original INPUT index and instrument identity. CCode's assignment now names the exact
`Session.derive` append sites and the required source/recovery-bound provenance addition. Codex keeps
the search-side adapter pending that returned contract; do not guess a join by row number or timestamp.
This is another concrete #3 gap, so neither step completion nor full computation is claimed.

Verification: direct producer/reader/alignment source review, AST syntax without project imports and
whitespace checks only. No tests, synthetic exercises, project/data/model/scientific runs or AWS actions.

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
