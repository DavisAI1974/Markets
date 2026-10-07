# Original-session checked correction consumer — 2026-10-07

Source-built / runtime-unverified. This implements a bounded analytical reader after
the retained correction scope ledger. It does not complete native learner training
or prove that every kind of retained knowledge reaches a supported predicate.

## Implemented boundary

`frankie_principal_adapter.prepare_knowledge_correction` adds an optional
`learner_consumer` to new requests. It pins this adapter and the existing
`frankie_box_classroom_code.py` reader by their exact source hashes. The additional
field changes the content-addressed request identity only for a genuinely new
correction intent. Preparation first finds an existing identical intent, comparing
all request fields except this additive consumer pin. It verifies each retained
request against its content-addressed directory and reuses the unique original
body/hash; ambiguous matches refuse. An old pending dispatch cannot become a new
request merely because the reader was added or its source changed. An earlier
immutable request or response is not overwritten or silently upgraded. A pinned
old reader can require explicit recovery rather than replacement. Earlier V1 follow-ups remain
recoverable with their exact original receipt shape; `learner_consumption` is
omitted for those earlier responses, preserving retained proof comparisons.

`Session.knowledge_correction` still binds the original request, initial response,
session, reported model and host authority. For new requests it now:

1. Retains the existing checked scope ledger as `scope-comparison.json` in the
   correction's existing content-addressed outbox.
2. Reads that file back and compares it to the complete checked ledger.
3. Calls `consume_knowledge_correction` with this readback and the unchanged
   original request.
4. Returns the analytical output as `learner_consumption` in the response. The
   existing response hash and independent host attestation bind that output.

The reader replaces only whole selected documents with their checked successors,
following the carried correction chain. It preserves unaffected selected documents.
The existing `REVIEW.require_current` rejects selected derived containers still
depending on superseded source hashes; it also checks the original visible evidence
for known replaced dependencies. This code does not edit old source pointers to
make an uncorrected derived result appear current.

The actual analytical consumer is the existing
`classroom_code.stage_knowledge_reproduction`. It receives complete effective
knowledge documents and only `classroom.visible_of(original_request)`. Existing
pair/component predicates perform the computation; no new predicate, numerical
method, target, label, lag or validation criterion is selected. The output carries
the complete effective selection, original request/response digests, checked-overlay
digest, original visible-evidence digest and the existing reader's full result.

Host recording/recovery computes the expected analytical response from the same
original request and checked ledger before accepting the response attestation.
The original pending-feedback object is checked against the initial response;
the original request ID and complete feedback contract are checked unchanged.

## Meaning and limits

- This is same-session **code-level analytical consumption/reproduction**. It
  is not a new forecast, a classroom answer rerun, a replacement model session,
  a native checkpoint update or independent scientific confirmation.
- Existing `checks`, `listed`, `not_measurable`, `full_claim_tested: false` and
  other unsupported-predicate dispositions stay unchanged. The consumption object
  explicitly says `all_knowledge_consumed: false`,
  `native_learning_performed: false` and
  `independent_scientific_verification: false`.
- No original model-visible classroom means refusal. SOCRATIC/VERIFY require the
  learner-owned evidence already present in that original visible package; this
  path never fetches a new snapshot, reads the host answer key or initiates a walk.
- A corrected embedded source still needs an explicit checked containing-document
  successor before that container can be used. School/meeting owner recovery is a
  separate workstream. A retained original classroom evidence dependency that is
  known to be superseded similarly refuses; no replacement observation is guessed.
- Full BOSS/native representation, targets, masks, controls, training lineage and
  unsupported scientific claim predicates remain outside this consumer. Their
  unsettled choices are not resolved by the analytical receipt.
- Transport uses the existing response/host-attestation files. The checked overlay
  remains in the owning Session outbox. Dispatch integration must distinguish an
  older ledger-only receipt (no `learner_consumption`) from this bounded consumer,
  and must not interpret either as full native learning completion.

## Review and efficiency

Applied using-agent-skills, context-engineering, API and Interface Design, and
code-review-and-quality. Reused the documented AWS/source-only constraints, the
existing whole-file witness cache, existing correction/currentness rules and the
existing evidence/predicate reader. No new service, cache, worker pool, validator
framework or claimed measured speedup. Repeated GUIDED evidence access uses the
reader's existing process-local evidence cache; host verification still recomputes
the analytical result rather than trusting a completion flag.

Both changed Python modules passed AST parsing without imports and scoped
`git diff --check`. Source/interface review traced preparation, retained readback,
predicate invocation, host recording and recovery. No tests, data/model runs,
project imports, AWS calls, installations or runtime verification occurred.

Owned changes: `deploy/aws/box/frankie_box_boss_session.py`,
`research/kalshi/frankie_boss/frankie_principal_adapter.py`, and this document.

## 2026-10-07 evening: stage 12 (end of day) pass, WIP hunks finished (source-built, runtime-unverified)

Greg requested resumption of this role (relayed by the parent). One source-only pass under the
stopped-agents handoff, the api-and-interface-design skill first, the AWS skills loaded through the
live connector for guidance; no account call, no run, no install, nothing executed.

### The two unfinished hunks from the stage pass (933529a and neighbours)
- `research/kalshi/frankie_boss/frankie_principal_adapter.py` (+44): FINISHED. `consume_knowledge_correction`
  now carries a `FRANKIE_PIECE_WORKFLOW_REPORT_V1` (`PIECE_WORKFLOW_REPORT`, piece
  `knowledge_correction_consumer`) inside the `learner_consumption` object: inputs (original request/response
  digests, the checked overlay and visible-evidence digests, every correction's record/original/replacement
  sha256, the selected knowledge pins), use (which selected documents were replaced along the chain and which
  were unaffected, the currentness check, the existing reader, what was NOT done: no forecast rerun, no
  classroom rerun, no native training, no new predicate or criterion, no answer key, no walk; pending feedback
  preserved; zero model calls), outputs (effective and replaced document counts, the reproduction's field
  names, the three `False` flags, empty waits/refusals/integrity_failures) and explicit dispositions: missing
  coverage never refuses here (the original visible picture is consumed as retained, absent operands stay
  listed by the existing predicates); a changed pin, overlay, chain or stale container refuses visibly as an
  integrity failure. Built from values already computed, no clock, so the host's byte-for-byte recompute of the
  consumption still holds. The consumption body and digests are unchanged otherwise (additive field only).
- `deploy/aws/box/frankie_box_experiment_day_reports.sh` (+9): KEPT as checkpointed (already on the branch). Its
  `SCHOOL` / `SCHOOL_LISTED` environment now reaches real arguments: `--school` and `--school-listed` exist in
  `frankie_box_experiment_day_reports.py` (below). The path check admits `<brain>/school/<day>.json` and
  `<brain>/school/successors/<day>/<op>/school.json`, no `..`.

### Stage 12 built in owned files
`deploy/aws/box/frankie_box_experiment_day_reports.py`:
- `Day.__init__(..., school=None, school_listed=None)`; `Day._read(kind, path)` reads every input ONCE and
  witnesses it (kind, path, bytes, sha256) in `Day.inputs`; the exchange, the sibling Frankie view, the classroom
  receipt, the sixteen classroom JSON files, classroom.md and the brain MANIFEST all go through it (the brain
  MANIFEST was read twice before: once for JSON, once for its hash).
- `Day._school(school, school_listed)`: reads the school file once, hashes once, checks an indexed original
  against its `index.json` row and a successor against its `receipt.json`. Status `read`; `not given` (a thinner
  picture, the orchestrator's reason carried); `unreadable` or `integrity_mismatch` (visible failures: stated in
  the report, on the receipt's `problems`, exit code 1; the content is not consolidated). Missing coverage and
  integrity are never conflated.
- `school_lines(d, number)`: the FRANKIE report's new section "The school file (what the day consolidated)",
  fixed templates only: kind, the recorded run / report number / classroom status / writer, per section the
  recorded author and item count, per item how it was carried (whole inline, a stated subset with what it
  holds, or a pointer with its recorded reason) and bytes, then every item the school listed missing or withheld
  with its recorded reason. Present on refused days too. Paths and hashes stay in Evidence (`evidence()` now
  names the school file, its index row and the count of files read).
- `run(..., school=None, school_listed=None)`: the school file's sha256 and status join the reuse rule beside
  the exchange and meeting (a report built before the school file is superseded by a revision with the same N;
  old index entries without the fields still reuse); the index entry carries `school`, `school_sha256`,
  `school_status`; `reuse_why` names exactly which of source / exchange / meeting / school changed.
- The receipt (last stdout line, unchanged schema, additive fields) now carries: `exchange_sha256`,
  `meeting.reason`, `meeting_status`, `meeting_sha256`, `school`, `school_sha256`, `school_status`,
  `school_listed`, `school_kind`, `school_row`, `school_successor_receipt_status`, `absent` (every file not
  found or unreadable with its reason), `inputs` (every file read with bytes and sha256), `reused`, `reuse_why`,
  `problems`, `timings_seconds` (read_inputs, build_and_write, total; receipt only, so report bytes stay
  deterministic), `workflow_report` and `receipt_path`.
- `workflow_report(d, receipt)`: `FRANKIE_PIECE_WORKFLOW_REPORT_V1`, piece `day_reports`: inputs (the files,
  the source, the three hashes, the school row), use (which inputs fed which report sections, which expected
  inputs were not read, every disposition: absent/unreadable files, exchange not given, meeting not complete,
  school not given / unreadable / integrity mismatch, classroom outputs not read on a refused day; the reuse
  decision; what the templates withhold; the no-interpretation rule), outputs (the reports with pins, N, the
  index, problems, empty refusals/waits, model_calls 0, the exit code).
- The same receipt is written to `<reports-dir>/receipts/<run>/<day>.json` (pending file + `os.replace`;
  `previous_receipt_sha256` recorded when one existed), the path `frankie_box_workflow_inspection.artifact_paths`
  already reads for the `school` piece; the reporter's `FIELDS`/`USED` already project `school`,
  `school_sha256`, `school_status`, `school_listed`, `problems`, `number_assigned_now`, `meeting_status`, so no
  reporter change is requested. The reports and the receipt are diagnostic, never knowledge.

`deploy/aws/box/frankie_box_boss_session.py`:
- `Session.knowledge_correction` is now a recording wrapper around `Session._knowledge_correction` (the body,
  unchanged in its bindings, retained files and attestation). Any `ValueError`/`KeyError`/`TypeError` (a
  different original request, response or host; a changed overlay; a stale container; a chain cycle; a
  malformed request) is written as `knowledge-corrections/<request_sha256>/refusal-<reason digest>.json`
  (`FRANKIE_PIECE_WORKFLOW_REPORT_V1`, piece `knowledge_correction_consumer`, `outputs.refusals=[reason]`,
  disposition `integrity_or_binding_refusal`, "not missing coverage") before the error propagates. Idempotent
  for the same reason; the retained request/scope/response/host bodies are untouched (no clock in them).
- Timings (read, consume, retain, total) go to the session log only.

### Cross-owner requests (precise)
1. `deploy/aws/box/frankie_box_experiment.py` (CCode, `Run.reports`): after `EXCHANGE`/`EXCHANGE_LISTED`, pass
   `env['SCHOOL'] = s['file']` when `s = self.receipt('school', day)` has status `done` or `reused`, else
   `env['SCHOOL_LISTED'] = "the day's school stage is <status>: <reason>"`; and in `Run.reports_stale`, treat a
   school receipt whose `row['sha256']` differs from the reports receipt's `school_sha256` as a reason to
   rebuild (a revision under the same N), exactly as a newly returned meeting or exchange is. Why: stage 12's
   row says the reports consolidate the school knowledge; without the env the FRANKIE report can only say "no
   school file was given".
2. `deploy/aws/box/frankie_box_school_knowledge.py` (`main`, receipt; shared history with school_recovery):
   carry the `missing` and `withheld` LISTS (section, item, path, reason; small) on the receipt beside the
   counts, and a `workflow_report` (inputs: classroom receipt, exchange view, lessons, teacher rows, rules
   witness with pins; use: per section what was inlined, subset or pointed and why, every missing/withheld
   disposition, the currentness check; outputs: the file pin, the index row, reused, successor/corrections).
   Why: the inspection reporter never opens the school file (it inlines the meeting), so today it can show only
   counts for the school half of the piece. Not edited here by instruction.
3. CCode's `waiting_school` drain callback (Step 8 branch): stage 12 needs, when it fires, the school receipt
   (file, row sha256, status) to reach `Run.reports`/`reports_stale` on the held lane so the revision is built
   with the school file rather than before it; nothing built here.

### Efficiency and data processing (Greg, 2026-10-07): what was used and what was rejected
Data shape of stage 12: one day, one child process on the held lane, kilobytes to a few megabytes of JSON on the
box's EBS, no S3 read or write (the day file reaches the school file by reference only), no model call.
- Used, in code: single read + single hash per input (`Day._read`), the receipt file so the inspection never
  re-derives, phase timings on the receipt and in the session log (observability-and-instrumentation).
  Estimated effect: the brain MANIFEST read drops from two reads to one and the exchange/meeting are no longer
  hashed separately; on this data shape the step stays sub-second after interpreter start, so the measurable
  gain is in the inspection (no second pass over the classroom directory). Measurement later: the
  `timings_seconds` of one real day (a one-to-two-minute canary: run the step twice, the second run reuses).
- Considered through the connector's skills and rejected for this stage, each with the reason: S3 byte-range /
  conditional reads, multipart and parallel transfer (no S3 object is read or written by stage 12);
  S3 Select / Athena over receipts and day files (the receipts are read from local disk by the inspection on
  the box; moving them to S3 would add a transfer and a service to a sub-second step); S3 Metadata and Storage
  Lens tables (no list/head at any scale: one file per day by exact path); Glue / Iceberg tables for the
  numbered reports and the school file (the school file is a hash-pinned, index-row-bound knowledge document
  read by the brain loader by exact path and sha256; a table changes its pinned identity and consumption path;
  the reports are markdown for Greg); SSM for the box steps (already the orchestrator's transport, not this
  stage's code; the reports print in full to the SSM log as before); billing (stage 12 adds no account call,
  its cost is seconds of the held lane). Skills loaded (verbatim names): `aws-compute`, `aws-storage`,
  `querying-aws-s3`, `querying-data-lake`, `aws-billing-and-cost-management`; `ingesting-into-data-lake` and
  `creating-data-lake-table` were resolved by search and not retrieved (not applicable, above); Skill tool:
  `api-and-interface-design`, `performance-optimization`, `observability-and-instrumentation`. Account calls:
  none.

### Still open in stage 12
- The orchestrator does not yet pass `SCHOOL`; until request 1 lands the school section reads "not given".
- The school receipt carries counts only (request 2); the inspection's school half shows counts.
- `waiting_school` drain (CCode) and genuine returned-school/report currentness remain CCode's.
- Nothing has run: SOURCE-BUILT / RUNTIME-UNVERIFIED; AST parse without project imports and `git diff --check`
  only. A fresh independent review is required before integration.

## 2026-10-07 (later): the 99 layers in the FRANKIE report, per-layer native records, the native-only 18

Greg resumed the role ("respawn and finish"; relayed by the parent). Source only; nothing ran. Skills used:
`api-and-interface-design` (first), `context-engineering`, `experiment-orchestrator`. No AWS account call (the
stage-12 survey stands). SOURCE-BUILT / RUNTIME-UNVERIFIED / UNREVIEWED.

### The 99 layers (what reached Frankie today): `frankie_box_experiment_day_reports.py`
- `collect_all99` reads each piece's own recorded all-99 list ONCE (pinned lists checked against their pin;
  a lessons file the school already inlined whole is taken from the school copy, not re-read): ROOT
  (`days/<day>/root.json` field `all99`, FRANKIE_ALL99_ADMISSION_V1), classroom (`receipt.json`
  `all99_coverage`), scientific teacher per lessons file the exchange consumed (`all99_coverage.by_day[<day>]`
  -> the pinned FRANKIE_ALL99_COVERAGE_V1 file), carried claims (accumulated-lessons receipt
  `workflow_report.outputs.all99_coverage_files[<day>]`), candidates (survivor update receipt at a boundary day
  or given), exchange / meeting / Jev / Jev sit-in (`workflow_report.use.all_99_coverage`). The shared field is
  preferred wherever a piece carries it (the list itself, or its nested `shared_field`) and is validated at
  this boundary by `frankie_box_all99_coverage.validate`.
- `all99_join` joins them over the ONE registry (`frankie_box_all99_coverage.REGISTRY`, imported) into one
  per-day table: per entry the word each piece recorded, its class (the row's own class, else the shared
  `CLASS_OF`; only `REACH_REFINE` splits consumer / rule / ROOT admission out of the shared 'arrived'), the
  final for Frankie (classroom / classroom_thin / other_computation / consumer / exposed_only / nothing /
  unknown), every entry no Frankie piece recorded in a computation with every piece's reason, and
  disagreements under fixed rules (group, lawful_role, picture_admitted_not_arrived,
  picture_arrived_not_admitted, summary_vs_list). A piece without a list is "not reported by <piece>" (unknown,
  never zero); integrity findings stay separate. ROOT and Jev are listed, never decide the final.
- The FRANKIE report carries the section (`all99_lines`), its receipt carries the full join (`all99`,
  FRANKIE_DAY_REPORTS_ALL99_JOIN_V1) and the workflow report its summary; the join's sha256 is part of the
  reports' reuse key (a changed list gives a revision with the same N). Diagnostic only, never knowledge.
- New optional inputs: `--run-dir`, `--piece-receipt candidates|carried_claims|jev=PATH`; the wrapper takes
  `RUN_DIR`, `CANDIDATES_RECEIPT`, `CARRIED_CLAIMS_RECEIPT`, `JEV_RECEIPT`.
- Day-quantity agnostic: numbering is 1 + the highest number held (N=1 for a one-day run), reuse is per
  (run, day); no one-day or three-day gate exists in the owned files.

### Per-layer native records and the native-only 18: `frankie_box_boss_session.py`
- `Session._write_native_layer_records` writes `work/native-layer-records.json`
  (FRANKIE_ROOT_NATIVE_LAYER_RECORDS_V1) AFTER derive.json, in `derive` and `_complete_native_derivation`: one
  record per native registry layer (44) with its crosswalk id, group, status and reason as derive.json
  recorded them (or `absent` with the reason), the projection pin, and the pinned crosswalk record; bound to
  derive.json's bytes. `Session.native_layer_records()` rebuilds it for a retained derivation. derive.json, the
  layer files and the digest are unchanged by it; the file moves aside with the derivation.
- The 18 native-only entries (`NATIVE_ONLY_ENTRIES`) are each named in `native_only` with status, producer and
  carrier. Each has a producer inside the pinned traversal `frankie_box_bedrock.run` already runs when the native
  pass is on (no new equation, no new invocation): fills `a_memory_member_first_recalculation_20260828.
  fill_disposition`; clears and reset/bootstrap receipts `native_full_capture_adapter._observe_before` /
  `_enrich`; roll state `native_replay_driver.ExchangeSessionRule`; depletion `replenishment` (4.7);
  resilience `absorption` (4.8); price/book path and price/flow/book paths `native_book_regime.
  observe_snapshot`; ancestry gaps and unresolved chain extension `LineageGraph`; chain trajectory
  `_retain_episode_rows`; V4 FIFO features `native_full_capture_adapter._window_extras`; predecessor at risk
  `_open_candidate`; successor opportunity `LINEAGE_SIGNATURE`; stopped-chain controls `native_recognition.
  note_failed_state`; negative cases `mark_missed`; discovery `record_call`; model evaluation `native_clocks.
  member_clock_row`. Limits named, never filled in: `clock_model_evaluation` is a declared null
  (NO_INVOCATION_AT_THIS_CUTOFF) under NeverInvoke (an observed evaluation time needs a model call inside the
  traversal); `clock_prospective_discovery_confirmation` is discovery only; the episode/candidate sections exist
  only when the candidate lane fires (900 s warmup, 600 observations), else `could_not` with the measured reason.
- The 2026-09-29 no-bedrock rule is retired in this file: the `derive` docstring states the native pass is ON
  by default and `bedrock=False` is only an explicit, recorded caller override (`override=True` on the skipped
  bedrock block; the not_derived reason says so). This changes derive.json text only for an override run.

### Still open
- The ROOT's admission list (`frankie_box_experiment.all99_admission`, ccode_step8) must read
  `native-layer-records.json` to name each native entry; the experiment ROOT's resume branch
  (`frankie_box_experiment_root.py`) should call `Session.native_layer_records()`.
- The orchestrator's `Run.reports` should pass `RUN_DIR` (the default already matches) and the candidate update
  receipt of the batch boundary covering the day.
- The data export lists `work/native-layer-records.json` as unclaimed until its catalog includes it.
- Nothing has run; AST parse without project imports, `bash -n` and `git diff --check` only. A fresh
  independent review is required before integration.
