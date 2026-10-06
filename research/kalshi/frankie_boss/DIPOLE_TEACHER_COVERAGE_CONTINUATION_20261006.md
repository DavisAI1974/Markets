# Dipole coverage and both-teacher continuation — 2026-10-06

Base: `ccr-5fce7de3-xa4hfg` at `03f29bef4a53c95296ca5c860712ba4a701bef0d`.
SOURCE-BUILT / RUNTIME-UNVERIFIED. No project imports, tests, scientific/data runs, models,
installs, runtime downloads, dispatch, AWS actions or E2E. Stop before workflow #5.

## Actual connections changed

### Parent annotation loss fixed after `21df8f1`

Source tracing found a concrete drop in `parallel_teacher._RawStreams._resolve`: replacing a deferred
calculation placeholder with its worker result discarded annotations the parent added after scheduling
that calculation. `teacher_changes.control_columns` adds current-book integrity/incomplete counters;
`teacher_changes.r3_iter_raw` adds those counters plus unknown-side trade count and volume. The worker
returns its own window calculation, so those parent annotations are not present in its result.

The resolver now preserves the worker's numeric value, state and reason, adds the parent's incomplete
counters using the same Counter addition as the original wrapper, and reapplies its other carried
metadata. R3 target-mask handling is unchanged. This repairs the existing calculation's output
assembly; it adds no measurement, formula, target, label or acceptance rule.

The actual existing path is: resolved raw mappings -> attachment `raw` -> snapshot `raw_components`
-> exact APPLIED cursor/prefix placement -> `dipole.group.rows[position].raw_components.*` -> existing
numeric/categorical transforms and coupling search. The host and separately owned lawful learner
walk both use this resolver. Both teachers' downstream search consumers can receive those fields
through their existing candidate/lesson routes; this is not a claim that every such consumer is complete.
The 19 output columns do not cap these nested input-evidence fields.

Raw-pass and attachment recovery identities now bind the parallel-teacher source SHA256. Previously
they bound teacher/source identities without this resolver implementation. Old partial state is
refused and preserved rather than silently reusing outputs that lost annotations. Old completed
artifacts remain unchanged and retain their actual previous coverage; no rerun or migration occurred.

Verification: direct source review of the deferred producer/wrapper/resolver and downstream consumer
interfaces, `ast.parse` of the changed module without imports, and no-index whitespace checks. No
tests, installs, model/data runs, AWS actions, dispatch or E2E. SOURCE-BUILT / RUNTIME-UNVERIFIED.

CCode's assignment was reread after Greg identified an overlapping candidate-origin investigation.
That four-file draft was set aside; commit object `9c19cc2e7b1232f81b984b074ffb9690991b2d08` was created
but never attached to the work branch. Do not cherry-pick it as completed integration. CCode retains
candidate/scientific-reader work, candidate-delivery review, historical reconsideration capabilities
and completed-native semantic review. Await his concrete caller requirements before overlapping them.

### Earlier source slice

1. `parallel_teacher.row_pass(retain_dstate=True)` captures all fields of the existing per-entity
   DState immediately after its original group update, from the existing continuation machine.
   Cursor/prefix, publisher/instrument, member/session, receive time, group ordinal and tick are retained.
   Fractions remain exact numerator/denominator fields; no reconstruction from logs or float conversion.
   A non-F_LAST row explicitly has no new state. Frozen/broken state semantics and all formulas remain.
2. The experiment teacher opts in for both its host walk and its separately owned lawful learner walk.
   It never imports the host machine into the learner. Raw and attachment recovery bind the additional
   coverage; incompatible old pending state refuses and remains intact rather than being replayed.
   Default non-opted callers retain their existing target/attachment content.
3. `snapshot_teacher_attachment` carries the optional state and every existing raw component mapping,
   including pre-tensor values, reasons and extra incomplete/unknown-side metadata. The original 19
   target columns and masks remain unchanged. The snapshot content hash includes the added fields.
4. Existing exact APPLIED cursor/prefix placement sends those complete row leaves to numeric/categorical
   search channels under `dipole.group.rows[position].dstate.*` and `.raw_components.*`.
   These reach the existing transforms/coupling/cell/chance computations. Rational numerators and
   denominators are separate exact channels, not a new scalar-ratio statistic. The report distinguishes
   retained from searched state counts; older snapshots explicitly lack coverage and are not backfilled.
5. `teacher_knowledge.teach_accumulated` now projects lawful transported search candidates through
   CCode's existing `candidate_claims_doc` and calls the existing `ST.test` on the owning day's complete,
   hash-checked search parts. It preserves exact scopes, frozen restart selection and claim deduplication.
   Origin-day evidence is listed, not counted as another test. No giant search parts move between owners.
6. Completed owner-local `SEARCH_CANDIDATE_LESSONS_V1` results enter the existing brain lesson writer.
   The accumulated caller handles exact-byte publication retry; CCode's standalone publisher remains
   guarded and is not used for this route. Both exchange seats admit these completed lessons.
   BOSS shared-count arithmetic/teaching and the scientific turn now receive the candidate results,
   and Frankie's existing reply receives the BOSS teaching. No new acceptance/survivor rule is chosen.

## Historical research belongs to the teachers

Greg clarified that both the BOSS and scientific teacher must challenge Claude's old dead/no-good/discarded
conclusions. R11, R13 and the experiment directive now explicitly require original-calculation reproduction
and repair/reformulation investigation before closure can be considered. CCode builds their capabilities;
CCode does not rerun, rework or judge Dipole research himself.

The historical catalog marks mapped claims and unmapped items open for teacher work. Both exchange seats
carry the reproduction/rework next task in their validated turn, before response hashes are computed.
Their per-item `research_rework` records explicitly say this exchange does not establish reproduction or
reformulation. Frankie's reply keeps that distinction. Original measured counts/dispositions are preserved;
an on-day disagreement resolution is not closure of the underlying research.

This is not a rerun engine or proof the historical corpus has been reworked. The existing historical
crosswalk is partial; unmapped `not_testable` items still need actual teacher computation bindings.
The corrected CCode assignment prioritizes those source/consumer gaps and forbids CCode research execution.

## Remaining coverage, not silently declared complete

- The 19 target columns are not a full-input limit. This slice adds retained state/raw details and an active
  research-results route; it does not complete every original BOSS representation/training consumer.
- No identity-linked full-book/order trajectory engine, full native model supervision, new mathematical
  objective, acceptance rule, nonlinear discovery route or disabled producer was selected.
- Post-stream result/section products need semantic consumers; they cannot be backfilled as earlier inputs.
- Old completed sources keep their actual old coverage. Resume refuses incompatible partial teacher/search
  state rather than replacing evidence. Rerun/migration choices are not made here.
- Candidate inputs reach a later existing applicable knowledge boundary; a finished day is not reopened
  automatically. Same-day origin comparisons are not independent evidence. Late scheduling remains separate.
- Teachers have not run. Coverage, cost, capacity and runtime behavior remain unmeasured. Steps #2/#3/#4
  remain open; one E2E and the 30-day launch still require their separate authorization.

Verification: changed Python parsed with `ast.parse`, edited JSON parsed, no-index whitespace diff,
and direct source tracing of producer, snapshot, exact placement, scientific call, publication, both
exchange seats and restart identities. An independent source review identified the capture/representation
and answer-wall requirements before implementation; final implementation review was performed by Codex.
