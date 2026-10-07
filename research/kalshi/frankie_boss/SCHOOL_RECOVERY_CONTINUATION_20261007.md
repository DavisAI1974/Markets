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
  and multiplicity remain unchanged. Existing whole lesson/exchange pointers keep their pointer
  status and update only to the exact checked source pin; giant sources are not copied into
  the corpus. Unsupported affected projections refuse; they do not silently disappear.
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

## 2026-10-07 evening: stage 10 built, all-99 coverage in the scientific stages, day-quantity agnostic (SOURCE-BUILT / RUNTIME-UNVERIFIED / UNREVIEWED)

Greg resumed the school_recovery role (relayed by the parent) with the redirect "the 99 layers are combined for Frankie
FIRST" and "day-quantity agnostic". Nothing ran; no account call was made; AWS skills were retrieved as documentation
only. A fresh independent review is required before integration. Skills used through the Skill tool:
api-and-interface-design (first), context-engineering, experiment-orchestrator, performance-optimization,
observability-and-instrumentation, incremental-implementation, doubt-driven-development (degraded self-questioning: a
subagent cannot spawn a fresh reviewer; cross-model skipped, non-interactive). Through the live `Aws` connector:
`search_documentation` (topics agent_skills, the stage's own words) and `retrieve_skill` for querying-aws-s3,
aws-storage, querying-data-lake, aws-billing-and-cost-management, aws-compute.

### Files (all under deploy/aws/box/)

| File | Lines | What |
|---|---:|---|
| `frankie_box_all99_coverage.py` (NEW) | 449 | the 99 identities of the retained crosswalk (`research/kalshi/frankie_boss/audits/CROSSWALK_SUNDAY_CYCLE0_FEED_33746436209_20260916.json`, sha256 `ece9c624...`, registry sha256 `239a1480...`) embedded and checked against the file; `day_coverage` (per day, per entry: arrived / thin / absent / disabled / withheld_by_role / produced / pending, with the reason and `via`), `registry`, `series_sources`, `tests_by_source`, `summary`, `retain` (content-addressed file), `boundary` (cross-day: days per disposition per entry), `markdown` |
| `frankie_box_survivor_update.py` (NEW) | 495 | stage 10: `select` (frozen selection over every brain root, per-entry integrity capture), `lessons_in`, `candidate_key`, `build` (one candidate per tested claim, every test with exact provenance, days per mark, own-day/origin/duplicate rows listed never counted, `works_on`/`not_on`, `previously_known`/`new_tests`, `same_pair_candidates`), `coverage` (all-99 per batch day), `update` (inputs.json frozen, survivors.json reproducible, immediate brain commit `<boundary day>-survivors`, receipt with FRANKIE_PIECE_WORKFLOW_REPORT_V1, late knowledge listed), `main` |
| `frankie_box_survivor_update.sh` (NEW) | 27 | the box wrapper: RUN, BOUNDARY_DAY, BATCH_DAYS (one or more), BRAIN, OUT, SEARCHES |
| `frankie_box_scientific_teacher.py` | 1696 (+294) | `load_searches` retains the manifest's plane/source/shared-market receipts; `test(..., report=)` with the needle row filter (every byte still hashed; selected rows invariant); `all99_for_operation`; `write(..., all99=, read_report=)` carries `all99_coverage` and `evidence_read` in every lessons file; `teach_standalone_successor` refreshes its coverage; `upload_jev_lessons` records intent before the PUT and success / failure / unknown after it (HTTPError = failure, transport = unknown; a retry PUTs the same bytes to the same key); `main`: `--search-findings` with no other searched day is LISTED, not refused (N = 1 days lawful); `_accumulated_report` (coverage + workflow_report on the accumulated receipt); `_write_teacher_receipt` (FRANKIE_SCIENTIFIC_TEACHER_RECEIPT_V1, content-addressed under `<out>/receipts/`, printed as the last line) |
| `frankie_box_experiment_review.py` | 1064 (+41) | `current_document`: a FRANKIE_SURVIVOR_UPDATE_V1 whose cited lesson has a checked correction is delivered whole with each affected candidate marked (`stale_sources`, `status_disposition=awaiting_next_boundary_update`, doc-level `corrections_pending`) instead of raising; its checked successor is the next boundary update |
| `frankie_box_school_knowledge.py` | 559 (+53) | `main` receipt carries `missing_listed` and `withheld_listed` (correction_consumer's request) and `workflow_report` (new `workflow_report()`: inputs by path/pin, per-section inline/subset/pointer dispositions, the currentness check, the day's lessons' all-99 summary, outputs file pin/row/reused/successor/corrections); the school file's bytes, index row and consumption path are unchanged |

### Stage 10 design as built

Cross-day batch boundary keyed by the batch's last day in plan order (a batch of one day is a boundary); cumulative over
every lessons / jev-tested / search / survivors brain entry at the boundary; selection frozen in inputs.json (a restart
reproduces the same bytes; later arrivals listed as late_knowledge and consumed at the next boundary; nothing waits).
One candidate per tested claim (author, claim id, day made, statement), every test row with lessons sha256, result
index, part sha256, row ordinal and raw-line sha256; the mark the scientific teacher gave it; days named per mark;
counts never pooled. Status words are orientation only: survivor_scoped (held beyond chance the claimed way on at
least one day other than the day the claim was made: one checked occurrence counts, R06), contradicted_scoped (no held
day, a shown_otherwise day: kept, D52), open. Days shown otherwise stay beside days held (both accounts, R13). No
threshold, rarity gate, minimum occurrence, averaging or freeze (step 13 freezes once, separately; not built). Filed
immediately as `<brain>/<boundary day>-survivors` (write_stage_entry, stage `survivors`): `learner_knowledge` delivers
it to every LATER classroom and excludes the boundary day's own classroom (DAY_KINDS survivors 50 > classroom 0): no
same-day circular promotion. Each candidate carries claim_id, x, y, scope.pair and evidence_refs so the classroom's
existing learner check binds it as a prior hypothesis, never as today's observation. Integrity failures (altered pinned
bytes, unreadable manifests, lessons needing a checked successor) are listed apart and block only what they carry.

### All-99 coverage (Greg's item 1)

For every searched day the stage emits one list of the 99 entries. Raw (6) and calculation/clock (49) entries are
read through the search MANIFEST's own plane receipt (`frankie_box_experiment_search.plane_summary`) and source
receipts: an entry is `arrived` only when a test row of this operation read a series the search placed from that
entry's source; `thin` when placed partially or placed and no claim named it; `absent` with the search's reason
(listed missing, not in this export, not produced with bedrock off, built not called, produced not carried). The 23
control/knowledge/arm entries are classified by role: the historical catalog entries reach the test through the
historical crosswalk only (`thin`, with the mapped/not_testable counts) or are absent when no historical claims file
was given; Memory A entries `disabled` (retired); arm/control policies `absent` by role; `lawful_prior_session_carry`
`arrived` when the operation selected brain documents. The 9 sealed answers are `withheld_by_role` (R09/R10), the 2
shadows `disabled`, the 10 outputs `produced` with the pin when this operation wrote them (candidate discoveries,
negative/inconclusive ledger, knowledge retrieval receipts, source/code hashes), `pending` or `absent` (other owners)
otherwise. The list is retained per day under `<out>/coverage/` (content-addressed), summarised inline in every lessons
file (`all99_coverage.by_day`), on the accumulated receipt, the standalone teacher receipt, the survivor receipt and
the school receipt's workflow_report, all under FRANKIE_PIECE_WORKFLOW_REPORT_V1 so the one-day reporter projects it.
The registry file named by the pins (`frankie_native_raw_mbo_ingestion_layer_registry_20260828.json`) is not in this
checkout; the crosswalk is, and the embedded identities are bound to its sha256; a difference is an integrity finding.

### Day-quantity agnostic (Greg's item 2)

Removed: the `--search-findings` refusal when the candidates' own day is the only searched day (now listed; the claims
come back INSUFFICIENT_EVIDENCE with the reason; the next day's search tests them). The survivor boundary accepts one
or more days. No other day-count literal exists in the owned files: `len(a.search) != 1` (accumulated mode) and the
`len(...) != 1` checks in experiment_review/school_knowledge are identity checks (one owning search, one index row,
one meeting), not run-length assumptions. `BATCH = 5` is in CCode's experiment.py (a teacher batch size, not a run
length) and is named below.

### Efficiency and data processing

| Change | Mechanism | Estimated effect (from the data shape) | Canary |
|---|---|---|---|
| `test()` needle row filter | the parts' JSON encoding (`json.dumps(row, sort_keys=True)`); both encodings of every claimed name; every byte still hashed | a part carries every ordered pair x cell x transform pair; a claim names 2-3 series, so nearly every line skips `json.loads` (roughly 10-20 us) for a substring scan (under 1 us); parse time of the read falls by about the share of unrelated rows; hashing (about 1 GB/s) unchanged; rows, ordinals and raw-line hashes invariant | `evidence_read` on the receipt: rows_hashed vs rows_parsed vs rows_selected, and the operation's `seconds`, with and without `NEEDLE_LIMIT` |
| Jev upload intent/result | the existing presigned PUT | no speed change; an interrupted upload is UNKNOWN, retried idempotently, never a silent second scientific test | the two files beside the lesson |

AWS mechanisms (retrieved, judged against these stages): S3 byte-range/conditional reads, parallel transfer, S3 Select
and Athena over the tape or receipts, S3 Metadata/Storage Lens, Glue/Iceberg tables for claims or day files: none
applies. These stages read owner-local files on the box (search parts under /opt/frankie-box/work, brain entries,
lessons) whose identity is a byte-exact hash of the whole file; a query engine cannot return the raw-line hashes and
ordinals the provenance requires, and a second copy of pinned bytes would be a second identity. The only S3 touch is
Jev's presigned PUT; an S3 conditional write (If-None-Match) would need the dispatcher's presign map to sign that
header (not this role's file) and is named as a possible later request, not built. Cost side: nothing added; no
account call made.

### Review of stages 8, 9, 14 (successor side) in the owned files

Fixed: no receipt for the standalone lessons call (now FRANKIE_SCIENTIFIC_TEACHER_RECEIPT_V1); no all-99 trace; the
N = 1 refusal; the Jev upload's unknown outcome; a survivors document blocking later classrooms on a corrected lesson
(experiment_review); the school receipt's counts-only lists. Kept as designed: a corrupt search part (altered pinned
bytes) still refuses the whole operation with the part named (an integrity failure, visible); the Jev blind seal is
still required by `freeze_operation`; search candidates' origin rows are never tests.

### Step 8 scope (deprioritized by Greg behind item 1; read, not fully reviewed)

Read on `origin/ccode/teacher-tasks-20261006b-step8-corrections` (`5f11188`): `Run.school` (retained_school chain,
other-run refusal, requires_successor waits on the corrected meeting), `Run.recover_school` (dispatch at most once per
invalidation, failures the stage's own), `Run.school_current`, `Run.reports_school_stale`, and the `waiting_school`
branch of `successor_dispatch.drain`. No blocking defect found in that read against the 91f3766/2c332df contracts.
UNVERIFIED: the full Step 8 review was not performed in this pass; no edit was made on that branch.

### Checks

`python3 -I -c "import ast,sys; [ast.parse(open(p).read(), p) for p in sys.argv[1:]]"` on the five Python files: OK.
`git diff --check` on deploy/aws/box: clean; the three new files checked for trailing whitespace and tabs: clean;
`sh -n` on the wrapper: OK. No tests, no runs, no installs, no dispatch, no model or data call, no account write.

## 2026-10-07 (late): the confirmation clock from stage 10 (clock_prospective_discovery_confirmation)

Greg's bounded change, relayed by the parent: fill the registry entry `clock_prospective_discovery_confirmation` from
stage 10's confirmation event. The pinned native producer (`native_recognition.record_call`) records discovery only and
computes no confirmation time (SAME_SESSION_CORRECTION_CONSUMER_20261007.md, newest section); in the experiment the
confirmation is the batch boundary marking a candidate `survivor_scoped` because it held on a day other than its own.

### Contract (FRANKIE_DISCOVERY_CONFIRMATION_CLOCK_V1)

One record per (survivor_scoped candidate, held test row on a market day other than day_made), at
`survivors.json candidates[i].confirmations[j]`: `confirmation_id` (digest of candidate, day, part sha256, row,
raw-line sha256), `claim` (candidate, claim_id, author, day_made, statement sha256), `discovery` (day; an observed instant
only when the claim, its source claim or its origin carries one of `DISCOVERY_CLOCK_FIELDS`, else `absent` with the
author's reason; the origin row identity; the native record named as not linked), `confirming_test` (lessons sha256 and
path, result index, part, part sha256, row ordinal, raw-line sha256, mark held, pair, cell, lag, transforms, counts,
chance check), `confirming_day` (day, `market_order` later/earlier market date or unknown, the search the lessons file
names, the market read: search manifest verified against that pin, frames spool pin, axis note,
`through_group_close_ordinal`; the axis end clock listed absent with its reason), `boundary` (day, batch days,
sequence), `committed_in` (the `<boundary>-survivors` entry; the pin is on the receipt), `clock` (event
`stage10_batch_boundary`, `stamped_at_boundary`, `new_at_this_boundary`, `first_stamped`, `previously_stamped`).
Every candidate carries `confirmation_clock` (`stamped_at_boundary` or `discovery_only_no_confirmation` with its status).
The document's `confirmation_clock` index lists stamped and not-stamped candidates and every earlier stamp no longer
reproduced (`withdrawn_since_previous`, never relabelled). The receipt's `confirmation_clock` (also at
`workflow_report.outputs.confirmation_clock`) adds `committed`, the entry and the survivors pin; a declined publication
reads `stamped_not_committed`. Nothing pooled or averaged; one confirming day counts; own-day, origin and duplicate rows
never confirm; nothing backfilled. The search-manifest reads are frozen with the selection (`search_markets`); a
selection frozen earlier captures them after the freeze and says so.

### Causality and consumers

Committed at the boundary in `<brain>/<boundary>-survivors`. Read through `frankie_box_lane_state.learner_knowledge` by
the classroom (`frankie_box_experiment_classroom_v2`, stage classroom), the exchange (`frankie_box_experiment_exchange`,
`frankie_box_teacher_knowledge`, stage exchange) and the meeting voice (`frankie_box_granite_meeting`, stage voice) of any
day other than the boundary day that runs after the entry is written; the boundary day's own stages never (DAY_KINDS
survivors 50 > classroom 0, exchange/voice 40). The next survivor update reads it as previously stamped.

Open (not this role's file): a NON-boundary day of the same batch whose exchange or voice runs after the boundary would
see the entry under the cross-day rule (`learner_knowledge` excludes by entry day only), including records whose
confirming row is that day's own. Request to the `frankie_box_lane_state.learner_knowledge` owner: exclude a
`FRANKIE_SURVIVOR_UPDATE_V1` entry for any day listed in its `boundary.batch_days`, listed with the reason.

### All-99 request (to workflow_reports, owner of frankie_box_all99_coverage.py)

For `clock_prospective_discovery_confirmation` on the survivor_update stage: `stamped_at_boundary` with the survivors
entry pin when the survivor update receipt's `confirmation_clock.status == 'stamped_at_boundary'` and `committed` is true
(pin: receipt `confirmation_clock.survivors` and `confirmation_clock.entry_manifest`; records at
`survivors.json candidates[i].confirmations[j]`, counts at `confirmation_clock.counts`); otherwise `discovery only, no
confirmation yet` with `confirmation_clock.reason` (or `stamped_not_committed` with its reason). Path: receipt
`<experiment-survivors>/<run>/<boundary>/receipt.json` key `confirmation_clock`.

### Checks

`python3 -I` ast.parse on frankie_box_survivor_update.py and frankie_box_scientific_teacher.py: OK; `sh -n` on
frankie_box_survivor_update.sh: OK; `git diff --check` on the two survivor files: clean. frankie_box_scientific_teacher.py
unchanged. SOURCE-BUILT / RUNTIME-UNVERIFIED; nothing ran. A fresh independent review is required before integration.
