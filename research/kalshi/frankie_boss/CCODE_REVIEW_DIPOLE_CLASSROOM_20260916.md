# ccode review - Dipole classroom branch (2026-09-16)

Reviewed: `chatgpt/frankie-dipole-classroom-20260916` at `bcd278e1` (cut from the clean recovery
tip `d550c05e`; does not contain the direct-benchmark branch). Review commits are on
`ccode/frankie-dipole-classroom-review-20260916`. No Frankie, Granite, EC2, market-data or
result-bearing run was performed; only unit tests on temporary fixtures.

## Governing rule, verified

"Complete Dipole coverage is invariant; only who does the explaining changes" holds in the code:
`PAIR_COUNT` is derived from `c15_normalizer.COLUMNS` (19 -> 171), every builder and gate
checks 19/19 and 171/171, `select_mode` advances only after two consecutive mastered,
acknowledged, teacher-complete cycles at the current level, and `audit_teacher_complete`
refuses any cycle with a missing dimension, unaccounted state, silently omitted
MISSING/INVALID/ABLATED observation, missing prior-cycle change, incomplete teach-back, or
unresolved disagreement.

## What is untouched

Byte-identical to the lawful commit `050c5056`: `dipole_target.py`, both teachers, both
normalisers, `c15_dstate.py`, `context_session.py`, `prepared_context_cache.py`,
`b1_reasoner.py`, `boss_training_checkpoint.py`, `feedback_cycle.py`,
`frankie_principal_adapter.py`, `operations/run_actual_sunday.py`, `research/refrag`. The only
science-file diff is the already-reviewed learner telemetry. The classroom reuses the prepared
teacher attachment through `PreparedContextCache.prepare` (owned copies, no re-attach), checks
the classroom rows equal the prepared context cursors, and returns the ordinary feedback
envelope only after `finish()` succeeds, so training inputs are unchanged.

## Tests

| suite | result |
|---|---|
| test_dipole_classroom | 9 passed |
| test_dipole_classroom_session | 5 passed, 6 after the new test |
| test_sunday_execution | 1 failed -> 4 passed after binding a real package |
| test_frankie_principal_adapter / source_contract_runtime / integrated_principal_recovery / claude_cycle_review_fixes | 13 / 3 / 1 / 6 passed |

## The three open items, closed

1. **Transcript renderer** now prints every `correction_resolutions` entry as
   `correction_id: corrected_understanding` under its own heading, and says so explicitly when
   no correction was required. It tolerates a base acknowledgement without the field.
2. **Focused test** `test_corrected_understanding_is_required_per_correction_and_rendered`: an
   ID echo alone is refused, one record per correction ID is accepted, the statements appear in
   the Markdown transcript, and the cycle can be teacher-complete while not mastered.
3. **Constructor wrinkle**: `SundayRuntime.classroom_package` defaults to `None` so construction
   stays compatible with pre-classroom callers; `run_cycle` still refuses a runtime whose
   package is not bound to the request, so the mandate is at execution, where it belongs. The
   lawful composition test now binds a real package to its request id. Consequence stated
   plainly: on this branch the lawful `run_actual_sunday.py` cannot complete a cycle without the
   classroom wrapper, and the two benchmark harnesses on the direct-benchmark branch will need
   either the wrapper or an explicit benchmark exemption when the branches meet.

## Design findings (not applied; Greg's calls)

1. **The withheld key is handed over one turn later.** `correction_request` sends the full
   post-grade back to Frankie, and it contains the exhaustive audit: every retained
   observation's actual state and value and all 171 actual directional relations, not just the
   wrong ones. The next cycle's pre-message then embeds that entire prior post-grade
   (`prior_cycle_correction`) in every mode. Because consecutive context windows overlap
   almost completely, a GUIDED/SOCRATIC/VERIFY cycle sees nearly all of its answers in the
   prior grade before it answers. If "genuine discovery distinguishable from instruction" is
   the goal, the correction turn should carry only the correction items (ID, claimed, actual,
   explanation) and the prior-cycle field only the correction IDs and explanations; the full
   audit stays in the retained JSON.
2. **The taper never regresses.** `_NEXT_MODE` only advances; a non-mastered VERIFY cycle stays
   in VERIFY. Recommend dropping back to TEACH (or one step) on any non-mastered cycle.
3. **Pearson at three overlapping points** is reported; that is noise. Require a stated
   minimum (eight or more) or report only the overlap count below it.
4. **The audit key is retained in the principal directory** (`dipole-classroom-teacher-key.audit.json`)
   beside the model-visible artifacts, and the host already retains it in the cycle directory.
   A filesystem-capable session can read it there. Remove the principal-directory copy.
5. `audit_teacher_complete` returns `prior_cycle_change_reviewed: key["cycle_index"]==0 or True`,
   a tautology; the real check is the raise above it. Replace with `True` and a comment.
6. Three modified files lost their trailing newline; cosmetic, but on-disk bytes feed the host
   code hash.
7. `_recover_with_classroom` calls `super().recover()` first, so the base principal envelope is
   verified before the classroom runs; that order is right, but the envelope object is then held
   across a possibly long correction wait. Fine as is; noted for anyone reading the flow.
