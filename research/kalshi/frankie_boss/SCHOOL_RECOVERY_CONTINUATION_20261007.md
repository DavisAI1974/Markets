# School recovery continuation — 2026-10-07

SOURCE-BUILT / RUNTIME-UNVERIFIED. The owner rebuild and consumer protection are implemented;
coordinator scheduling integration remains assigned to CCode's Step 8 owner. Do not mark
school-dependent dispatch complete until that integration is returned and reviewed.

## Implemented boundaries

- `frankie_box_school_knowledge.retained_school(brain, day)` reads the immutable indexed
  original and follows only explicit checked school successors. It returns `None`, or
  `{row, original, content, corrections, status}`. `row` remains the original index row;
  `original` is the latest checked complete school path/bytes/SHA256 witness. `status` is
  `complete` or `requires_successor`. Errors in the index, original or correction chain refuse.
- `rebuild_successor(day, run, brain, *, original_school, exchange_view=None)` requires that
  exact original owner's indexed day/run and current school. It retains a distinct operation,
  complete replacement and receipt under `school/successors/<day>/<operation SHA>/`. Identical
  retries read back the same receipt. The original school JSON and index row are never changed.
- Only checked copied scientific/exchange sources change. The existing BOSS exchange-measurement
  subset and scientific `untested` subset are recomputed from their checked replacements.
  Unaffected sections, classroom answers, author labels, rules, missing/withheld lists, order
  and multiplicity remain unchanged. Unsupported affected projections or pointers refuse;
  they do not silently disappear.
- A school containing a discussion of a replaced exchange requires the actual completed,
  receipt-verified successor meeting. The old discussion remains in the immutable original;
  the new school carries the entire new discussion with its existing zero evidentiary authority.
  An inputs-only, refused or runtime-failed replacement meeting cannot masquerade as that
  completed discussion. This owner operation itself performs no model or scientific calls.
- `record_correction(..., school_transition={receipt: <pin>})` extends the existing checked
  correction mechanism. It binds the exact complete operation, owner/index lineage, copied
  sources and meeting receipt, and checks preservation of all unaffected content. Public source
  corrections and objects travel with the school correction; private scientific selections and
  model runtime evidence stay on their owner.
- Existing brain/corpus and lane-school readers already call `current_document`. They now
  consume the checked complete school successor and refuse implicit nested repair of a stale
  school. Reader currentness still applies to its copied sources and full discussion.
  Retained forecasts, request/session/source identities, pending feedback and native weights
  remain untouched.
- The ordinary school CLI handles an indexed school through the same owner operation; new
  school publication resolves checked scientific sources and checks currentness before writing.
- The successor dispatcher freezes an affected school in its existing dependent intent,
  records precise invalidation, and withholds dependency acknowledgment/native delivery until
  the checked school successor exists. On completion it verifies the exact school chain and
  adds that correction to the original-session consumer's available corrections.

## Required CCode integration (experiment.py / Step 8 ownership)

These exact caller changes are intentionally not made by the school agent because CCode now
owns `frankie_box_experiment.py`, queue and cores.

1. `Run.school`: remove unconditional reuse merely because an index row exists. Call
   `SK.retained_school(brain, day)`. For a `complete` result, reuse its `original['path']`,
   retain `row` as `dict(result['row'], **result['original'])`, and record its `corrections`.
   For `requires_successor`, continue through the existing school child and let its CLI run
   the owner operation. Do not catch binding errors as ordinary absence. Require the result's
   `content['run']` to equal the current run; do not reuse another run's same-day school.
   Copy the child receipt's optional `successor`, `correction` and `corrections` fields into
   the run's school receipt. Do not overwrite the original index row.
2. `successor_dispatch.rebuild_dependents` can now return:

   ```python
   dict(status='waiting_school', recovery_intent=<exact school-invalidation pin>,
        stages=['voice', 'school'], reason=...)
   ```

   `drain` must arrange the existing `Run.voice` then `Run.school` on the same owner/day/held
   16-CPU lane, without recursively entering this same successor drain. Existing `Run.voice`
   calls `self.successors(day)` and `Run.child` drains before ordinary children, so calling
   those methods unchanged inside `drain` deadlocks on the drain lock. Bind a narrowly scoped
   recovery call to the actual operation/recovery-intent and allow it to skip only that nested
   inbox drain. Preserve save checks, source/currentness checks, original CPU allocation and
   child completion acknowledgment. Do not add a parallel Granite scheduler or model runtime.
3. After those stages produce the real checked school successor, call `rebuild_dependents`
   again. It verifies the owner chain, resumes original-session corrections and only then
   permits the usual dependency/knowledge-sync acknowledgment. An incomplete/refused meeting
   must remain explicit waiting recovery, not a completed school, failure/requeue substitute,
   invented discussion or native training claim. A cooperative save preserves this exact
   intent and original allocation. The current dispatcher deliberately remains waiting until
   this caller integration or an explicit owner recovery completes; no fake completion path.
4. Completed stage reuse (`Run.finished` and downstream report reuse) must resolve school
   currentness as well as teacher/exchange currentness, and reports based on the old school
   need their existing owner refresh. Source publication is not proof that an already-produced
   report or learner consumed the new school. Do not rewrite old report artifacts in place.

## Limits and verification

AST parsing without project imports and `git diff --check` passed for the three changed Python
files. Source/interface inspection covered publication/retry, transport, original index ancestry,
reader delivery, explicit waiting and native correction selection. No tests, validator framework,
model/data/scientific runs, AWS installations or dispatch were performed. AWS reauthorization
was unavailable; this slice reuses the existing owner-local I/O, held-lane execution and durable
receipts, and makes no new AWS efficiency claim. API/module principles applied: one additive
owner transition, exact input/output witnesses, checked boundary publication and original-intent
retry behavior; no independent replacement pipeline.
