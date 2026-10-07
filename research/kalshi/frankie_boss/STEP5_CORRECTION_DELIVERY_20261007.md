# Step 5 — scoped corrections and actual knowledge delivery

Greg authorized this source work on 2026-10-06 ET. SOURCE-BUILT / RUNTIME-UNVERIFIED.
No tests, project imports, scientific/data/model runs, reproduction calls or AWS actions.

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
author/schema/claim identity and identical values outside the declared scopes. Partial replacement
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
   correction. No producer currently calls `record_correction` automatically; an ordinary newer
   or contradictory lesson must NEVER trigger it. There is no newly invented adjudication rule.
2. The fifth-session owner trace identifies a concrete contract gap: a recomputed successor
   can change `claim_inputs`/`claim_inputs_sha256`, but the current correction guard requires
   them equal. Codex must bind that explicit identity transition without relaxing scientific
   ownership or unaffected-scope checks; publication is not ready to wire around the guard.
   Scheduling corrected successor operations for already-frozen/completed work is not complete.
   The current runner refuses stale dependencies; it does not yet build every replacement
   operation. Existing immutable request identities and pending feedback must be carried forward
   by their owner, without an implicit scientific rerun or reopening unrelated completed days.
3. Historical reproduction/rework, native learner decisions, the remaining step-2–4 gaps and
   CCode's remaining B2-R/B4-R/BIND-R corrections remain open. Real computation requires Greg's separate authorization.

Verification: direct source/interface review, `ast.parse` on changed Python text without project
imports and `git diff --check`. No synthetic exercises, tests or runtime claims.
