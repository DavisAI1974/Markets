# Step 5 — scoped corrections and actual knowledge delivery

Greg authorized this source work on 2026-10-06 ET. SOURCE-BUILT / RUNTIME-UNVERIFIED.
No tests, project imports, scientific/data/model runs, reproduction calls or AWS actions.

## Owner-bound claim-input transition — 2026-10-07 source continuation

The accumulated-teacher transition is now source-built in `record_correction(...,
owner_transition={original_inputs: witness, replacement_inputs: witness})`. Each witness is
the actual frozen `inputs.json` path/bytes/SHA256. This is an explicit owner argument, never
inferred from a newer lesson. The function reads both selected operations before publication,
checks their selection hashes, exact source lessons and ordered consumed claim projections,
then binds their owner day/brain, search manifest, scientific reader, historical binding tables
and reproduction selection to each complete result's `knowledge_retest` and claim/result hashes.
The successor needs a distinct input file/hash on the same owner day and publishing brain.

`FRANKIE_CORRECTION_OWNER_TRANSITION_V1` is retained inside the correction record. Transported
readers recheck those operation bindings against both full lesson objects without opening or
copying the private frozen selections. This is owner-declared operation evidence, not independent
proof that the research ran or that its conclusion is scientifically correct.

The original schema, author, lesson day, claims-file hash and ordered claim IDs still must match.
Changed `claim_inputs` or their hash refuse without this transition. Partial replacement still
requires explicit addresses for EVERY changed field, including operation metadata and changed
input/hash fields; there is no metadata exemption from unaffected-value equality. Unchanged-input
corrections retain their existing interface. Standalone scientific CLI results without accumulated
operation bindings remain unsupported for changed-input corrections, explicitly refused.

## Explicit successor retest and checked publication — 2026-10-07 continuation

`frankie_box_teacher_knowledge.teach_successor(day, search, brain, out_dir, request=...)`
now provides the explicit owner-local operation. The request has exactly `original_inputs`,
`original_result`, `reason`, and `evidence`; the first two and every evidence item are actual
path/bytes/SHA256 witnesses. It verifies the original completed result against its frozen
operation and published brain identity before scientific work. It requires the same exact
owner day, brain and unchanged search manifest, plus a distinct output directory.

The operation selects exactly the original result's complete ordered claim set from the
original frozen source, retaining the full source lesson. It schedules that explicit set
through the existing teacher even on the same search; ordinary `teach_accumulated` deduplication
is unchanged. No unrelated brain claims are reopened. Original reproduction records remain
selected at their original pins; additional records in the new owner's reproduction directory
join the frozen selection. Missing/changed originals refuse. Older bindings can be listed as
inadmissible by the current scientific reader but are never silently erased. Later arrivals
remain listed and require another explicit operation, not mutation of frozen inputs.

The existing teacher writes complete results durably and reuses exact completed files on
restart. A same-directory successor lock serializes calls; changed requests/readers refuse.
The result's original and replacement operation bindings are checked before the durable
`FRANKIE_TEACHER_SUCCESSOR_RECEIPT_V1` is returned. The receipt includes the actual new/reused
file counts and both input witnesses needed by the correction publisher. Same-search retesting
is explicitly not an independent observation.

This candidate is NOT published as an ordinary newer lesson and does not replace the original.
`publish_successor(brain, receipt=..., scopes=..., decision=..., reason=..., evidence=...)`
now calls the existing `record_correction` after verifying the exact receipt and frozen request.
The owner must supply the actual checked decision, evidence and all changed JSON addresses;
none is inferred from result disposition, age or disagreement. The existing same-subject and
unaffected-value guard still applies, including metadata. Publication/retry uses the existing
correction lock/objects/record and reaches the existing learner delivery path immediately.
After publication, retry the publication with its retained receipt; do not retest the replaced
original. The retest entrypoint explicitly refuses an already-replaced original.

Scope is deliberately precise: this supports operation-reader/binding/reproduction changes for
one accumulated result's unchanged claims and search. Changed claim content, changed search
inputs, a smaller affected subset within a multi-claim result, dependent exchange/request
successors and main/worker dispatch/acknowledgment are not wired by this slice. No CLI or run
loop invokes it automatically, no scientific decision is manufactured, and no actual retest or
publication was performed. SOURCE-BUILT / RUNTIME-UNVERIFIED.

## Governing knowledge rule

Keep older lessons available. Age alone never makes knowledge obsolete. Only conflicting
knowledge about the same thing calls for research of that conflict. Keep both accounts and
their circumstances available while it is unresolved. Research can establish a circumstance-
specific or partial replacement; preserve every unaffected part. Full replacement requires an
explicit researched decision. A demonstrated source/calculation error can also be corrected.
This implementation introduces no recency winner, rarity criterion or new scientific formula.

## Built source path

`frankie_box_experiment_review.record_correction` publishes a completed scientific-owner
decision, not a judgment inferred from a date or a contradictory result. It takes the brain,
original/replacement path/bytes/SHA256 witnesses, exact JSON-address scopes, decision, reason,
evidence witnesses and `publication_day` (the owning workflow day whose lessons stage completed
the correction). Both complete lesson objects are retained. It requires the same original
author/schema/claim identity (with the explicit operation transition above for changed input pins)
and identical values outside the declared scopes. Partial replacement
cannot use the whole-document address. The original must already be published learner knowledge.

`FRANKIE_KNOWLEDGE_CORRECTION_V1` records live at `brain/corrections/<content-hash>.json`;
original and successor objects live under `corrections/objects/`. Existing durable writes and an
owner publication lock handle publication/retry. Readers verify the records and object pins,
reject cycles/competing replacement links, and do not resolve competing decisions by recency.
Evidence witnesses retain their owner paths; private research/answer material is not copied into
learner knowledge through the correction transport. A record is the owner's declared checked
decision, not independent proof that its scientific conclusion is correct.

| Actual consumer | Source behavior |
|---|---|
| Lane snapshot/import | Transports each correction record and both complete lesson objects in the existing hash-bound owner version. |
| `lane_state.learner_knowledge` | Delivers the complete corrected lesson with its actual file hash/path; unrelated and unresolved conflicting lessons remain. Deduplicates identical delivered bytes only. |
| `lane_state.learner_school` | Rebuilds copied-source views with corrected inline lessons and true container hashes; the immutable school source is unchanged. Stage argument preserves own-day answer walls. |
| `brain.identity` / `brain.load` | Use corrected JSON source identities/content before corpus deduplication. Captured request bases pin correction-record identities; a later relevant correction requires an explicit successor request. |
| Experiment exchange arguments | Resolve directly supplied lesson paths to their checked successors before passing them to the exchange. |
| Standalone teacher/exchange | Guard retained scientific/exchange selections, resolve directly supplied lessons to their actual corrected file/hash, use the exchange school boundary, and bind the correction reader implementation in frozen input identities. |
| Experiment teacher reuse/child boundaries | Check both accumulated-teacher and exchange frozen selections; a known replaced input cannot silently continue as current. |

Copied-source containers can be rebuilt by substitution. Computed results cannot: a derived
document still citing a replaced source refuses until its owner supplies a checked successor.
`require_current` follows recorded hash dependencies transitively within the supplied selection.
It does not claim to discover unrecorded dependencies or remove knowledge from learned weights.
Completed past predictions are never rewritten as if they originally consumed a correction.

Search publication now checks every stored row against the existing exact-integer count margins
and existing market-signal/context policy, with binary part/line hashes and selected part sizes.
Every failed row has its exact original location and reasons in a retained review; invalid evidence
refuses publication. Valid retained findings keep their established bytes/identity. A review adds
zero independent observations. Scientific judgments still belong to the existing teachers.

## Completion gaps — do not mark all of step 5 complete

The standalone reader hooks were completed by Codex after Greg's 22:46 ET ownership update.
The remaining gaps are:

1. Scientific owners must explicitly supply a checked decision and successor after research or
   correction. The explicit `publish_successor` interface now calls `record_correction`; no producer
   chooses a scientific decision automatically. An ordinary newer or contradictory lesson must NEVER trigger it. There is no newly invented adjudication rule.
2. The accumulated-teacher identity transition is source-built as described above; standalone
   CLI operation binding and full corrected-successor scheduling remain incomplete. The explicit
   accumulated-owner interface above overcomes same-search reuse only for its pinned original result;
   the normal run loop still needs owner request/decision delivery and completion acknowledgment.
   The current runner refuses stale dependencies; it does not yet build every replacement
   operation. Existing immutable request identities and pending feedback must be carried forward
   by their owner, without an implicit scientific rerun or reopening unrelated completed days.
3. Historical reproduction/rework, native learner decisions, the remaining step-2–4 gaps and
   runtime verification of the integrated historical-binding/comparison fixes remain open. Real computation requires Greg's separate authorization.

Verification: direct source/interface review, `ast.parse` on changed Python text without project
imports and `git diff --check`. No synthetic exercises, tests or runtime claims.
