# CCode step-6 return: the bounded Granite meeting source/recovery path, 2026-10-07

Assignment: `CCODE_NEXT_SOURCE_TASKS_20261006.md`, "ACTIVE assignment, Greg 2026-10-06 22:11 ET", section 6 (findings 1-5)
plus the pre-#5 follow-ups B2-B5 (recorded in `CCODE_STEP4_SOURCE_ROUTE_20261006.md` sections 8/9). Branch
`ccode/teacher-tasks-20261006b` rebased onto Codex's `6c033cd5`. Commits: `e922a6e2` findings 1-3 | `b3fb5a26` finding 4 |
`2f1d6630` B2-B5 follow-ups | then this documentation. SOURCE-BUILT / RUNTIME-UNVERIFIED: `ast.parse` without project imports,
YAML parse of the workflow, `git diff --check`. No test, setup, download, install, model or data run, reproduction call, AWS
action, start, dispatch, canary or E2E. Pins unchanged; `threads: null` unchanged; `9c19cc2` never applied; the deleted
historical binding stays deleted; H06-H08 historical/not_bound. Owned files changed: `deploy/aws/box/frankie_box_granite_meeting.py`,
`.github/workflows/frankie_granite_meeting.yml`, `deploy/aws/box/frankie_box_historical_reproduction.py`. The launcher and the
setup script needed no change for these findings (traced; see section 4).

## 1. Finding 1, the meeting deadline through every request

`LlamaServer` now carries the meeting deadline (`time.monotonic() + max_meeting_seconds`, the settled 3000 s, untouched).
`_bounded(ceiling)` gives every request `min(ceiling, remaining)` and raises `MeetingBudgetExpired` when nothing remains: the
health wait at `start()`, `/apply-template`, `/tokenize` and `/v1/chat/completions` are all bounded; the 600 s ceiling is now a
ceiling, never the bound. In `discuss_item` an expiry closes the CURRENT item `LEFT_OPEN_BY_CODE` with an open item
`time_budget` naming `rounds_completed`; its completed coordinator turns, answers, notes, requests and refusals are kept in the
record. `_meeting` checks the remaining budget before each item and lists every unreached item in `not_discussed` with its
code-seeded open items (unchanged shape, so Codex's `read_meeting_record` coverage check holds). The record's `runtime` carries
`budget_seconds` and `budget_left_seconds`.

## 2. Finding 2, interrupted-call recovery

- `meeting-binding.json` (`FRANKIE_GRANITE_MEETING_BINDING_V1`), written once before the server starts: the exchange (path,
  sha256, exchange_hash), the meeting input witness, the charter, rules and runtime-config witnesses, the pins' sha256, the
  parameters, the binary and model witnesses. A retained binding with other bytes REFUSES the meeting directory (nothing is
  reused across inputs); every progress file names its sha256 and refuses on a mismatch.
- `ItemProgress` (`FRANKIE_GRANITE_MEETING_ITEM_PROGRESS_V1`, `<out>/progress/<item>.json`) through the existing durable writer
  (`frankie_box_durable.write_json`: complete bytes, fsync, previous bytes retained beside as `.retained-<sha>`): the item's
  transcript, completed rounds and all four categories after EVERY completed round. The one non-idempotent request (chat) is
  marked `pending_call` (round, transcript sha256, started_at) BEFORE it is sent and cleared only after its reply was recorded.
  `/apply-template` and `/tokenize` are side-effect free and are not marked.
- On a restart: a retained complete item is reused without a call (`reused_from_progress`, counted in `counts.reused_items`);
  an in-progress item resumes from its completed rounds; an item with a pending call is closed `LEFT_OPEN_BY_CODE` with an
  open item `interrupted_call` naming the round and transcript hash: the call is never repeated and no answer is invented.
  A completed `meeting.json` is reused as before (publication repair unchanged).
- Partial state after a budget expiry or a failed request keeps the pending fact in the progress file (`status: interrupted`).

## 3. Finding 3, whole evidence and cleanup

- The server's stderr goes to `<out>/evidence/llama-server-stderr.log`, whole, as a file (no undrained pipe, no slice);
  `stderr_witness()` pins it into the record and every failure message.
- `retain(label, bytes)` writes every HTTP error body, transport error, non-JSON or malformed reply and every refused raw
  coordinator turn as a durable file under `evidence/` (`NNN-<label>.bin`), listed in `runtime.evidence`; `refused[].raw` keeps
  the whole text too (the `[:2000]` slice is gone).
- A startup failure (`MeetingCallFailed` from `start()`, or the budget spent while starting) releases the process inside
  `start()`, writes a receipt `status: runtime_failed` with `refused_to_run` (the reason) and the stderr witness, keeps the
  inputs and the binding, and re-raises (loud). A request failure closes the item open by code (`call_failed` with its
  evidence) and, if the server died, lists the remaining items; `stop()` always releases the process and closes the stderr
  file. No new logging or validator framework.

## 4. Finding 4, the runner return contract (traced; nothing dispatched)

The workflow returns BYTES only: the `granite-meeting-record` artifact (now uploaded on every outcome, so partial state
returns too) and the optional presigned PUT of `meeting.json`. Publication is the explicit owner-side import that already
exists: `frankie_box_lane_state.import_meeting_record` (CLI `--import-meeting RECORD --record-sha256 SHA --exchange
/opt/frankie-box/work/experiment/<run>/exchange/<day>/exchange-frankie.json`), which re-pins the plan, the completed ROOT, the
exchange step and both exchange receipts, verifies the record hash, writes the record under `<owner>/meeting/<day>/` and
publishes through `publish_meeting_record`. The hash it needs is now written by the runner: `return.json`
(`FRANKIE_GRANITE_MEETING_RETURN_V1`: record path/bytes/sha256, receipt, progress and evidence file names, the exact import
command). Workflow inputs reach the shell only as environment variables (`EXCHANGE_GET_URL`, `RECORD_PUT_URL`, checked
to be https); no interpolation into shell source remains. Missing orchestration, stated, not built: nothing downloads the
artifact onto a lane, nothing runs the import, the PUT target is whatever presigned URL the dispatcher chose, and the first
E2E host is Greg's choice. Permissions stay `contents: read`; dispatch-only and inputs-only defaults unchanged.
The launcher `frankie_box_granite_meeting.sh` needed no change (its path discipline and env inputs already hold); the setup
script needed none (its every-run verification is in place).

## 5. Greg's question: does Granite's weight set improve on its own?

Plainly: no. The meeting runtime is inference-only. `LlamaServer` starts a pinned `llama-server` on a pinned GGUF; `gate`
refuses a model file whose sha256 differs from `pins.model_sha256`; there is no optimizer, no loss, no training feedback, no
learned checkpoint and no path that writes weights anywhere in `frankie_box_granite_meeting.py`, its scripts or the workflow.
Every meeting runs the same bytes. What does change between meetings is CONTEXT: the exchange view, the charter, the rules
and the accumulated-knowledge index (labels and hashes, by `lane_state.learner_knowledge(day, 'voice')`), plus the retained
lessons the brain `meeting` entries carry forward. That is lessons, not learning in the weights.

Existing machinery traced (none of it trains Granite):
- `research/kalshi/frankie_boss/native_forecast_learning.NativeForecastLearner`: Frankie's native BOSS learner (torch;
  optimizer identity, checkpoints, attested feedback through `PENDING_FEEDBACK_COMPLETION_20261006.md`). Its own docstring
  says "Granite is not optimized". Out of this assignment by Greg's instruction.
- `research/kalshi/frankie_boss/granite_shadow.GraniteIdentity` (retired vLLM-era boundary): an identity slot with
  `base_checkpoint_sha`, `weights_sha` and `tune_receipt_hash`, i.e. the SHAPE a tuned-weights pin would take (base +
  learned delta + the receipt of how it was made). No tuning code exists behind it.
- `granite_positive_priming.py`: model-visible priming with retained provenance, i.e. context, not weights.
- `frankie_box_brain` `meeting` entries + `learner_knowledge('voice')`: the only feedback loop today, and it is a context loop.

The smallest concrete path to a coordinator that improves from checked feedback, in two separable layers:
1. Context/lessons layer (no weights; mostly existing): file the code's own verdicts on coordinator turns as retained
   lessons for the coordinator: each meeting record already holds accepted turns, refused turns with the code's reason,
   requested tests and open items. A "coordinator lessons" document built from completed records (what was refused and
   why; which questions produced code-seat answers; which requests were bound) would enter the knowledge index the
   meeting already lists. Decision needed: the content scope of accumulated knowledge beyond the label/hash index (Greg,
   already open). No weights change; identical model bytes.
2. Weight-update layer (new, separate operation): a LoRA adapter trained on checked coordination transcripts, loaded by
   `llama-server --lora <adapter.gguf>` beside the UNCHANGED pinned base model. Requirements before any code: FEEDBACK =
   which turns count as good (code-accepted turns as positives and code-refused turns as negatives is the only feedback the
   code can attest today; whether a human grade or an E2E facilitator-quality outcome joins it is Greg's); OBJECTIVE =
   supervised next-token on accepted turns, or preference between accepted and refused replies (a mathematical choice, not
   taken); ADMISSION = only complete, receipt-verified meeting records of the owning lane; CHECKPOINT = a new pin pair in
   `GRANITE_MEETING_RUNTIME_V1.json` (`adapter_sha256`, `adapter_receipt_sha256`) beside the untouched `model_sha256`, the
   gate verifying both, the record carrying both, the `GraniteIdentity` shape (`weights_sha`, `tune_receipt_hash`) reused for
   the receipt; RECOVERY = training is a separate authorized operation with its own durable receipt (inputs' hashes,
   objective, seed, steps, the resulting adapter hash); a meeting never trains; an adapter whose receipt or hash fails
   the gate refuses the meeting, never falls back silently; EVALUATION = the runtime config's `upgrade_trigger` criteria
   (stay in role, keep attribution, keep open items intact, route requests) on the one authorized E2E, before and after.
   Host: training needs a GPU hour the current policy does not permit as a standing service; it would be a bounded,
   authorized job, not a meeting-time activity.
Decisions still needed and not taken here: the feedback definition and its authorship; the objective; whether the pin policy
admits an adapter at all; the training host and authorization; the evaluation bar. Nothing was implemented, the hash gate is
unchanged, nothing ran. Conversation context (the transcript of one item), retained lessons (brain entries and the knowledge
index) and weight updates (none exist) are three different things; only the first two exist today.

## 6. Exact interface requests to Codex-owned files (not made)

1. `frankie_box_experiment.Run.voice` (experiment runner): pass the same `OUT_DIR` for a day on every retry so retained
   progress is reused; treat a receipt `status: runtime_failed` (new; carries `refused_to_run` and `evidence`) as the
   non-blocking `waiting` disposition, like a gate refusal; a child exit after such a receipt is not a wiring failure.
2. `frankie_box_frankie_queue.py` (`passed('voice')`): `runtime_failed` passes the stage non-blocking like a gate refusal
   (the receipt names why; the model is not blocking the day).
3. `frankie_box_brain.read_meeting_record`: no change required; the record gained additive keys only (`binding`, `progress`,
   `runtime.budget_*`, `runtime.server_stderr`, `runtime.evidence`, `counts.reused_items`, per item `rounds_completed` and
   `reused_from_progress`). If Codex wants them checked, `binding.sha256` is the hash of `meeting-binding.json`.
4. `frankie_box_lane_state.import_meeting_record`: no change required; `return.json`'s `record.sha256` is the value for
   `--record-sha256`. Optional: accept `--return return.json` and read the hash from it (same verification).
5. School and day reports: the new open-item kinds `time_budget`, `interrupted_call`, `call_failed` (beside `input_cap`,
   `turn_budget`) should render like the existing kinds; nothing else changes shape.

## 7. Knowledge rule noted

Older lessons stay available; age retires nothing; conflicting knowledge about the same thing is researched, both accounts
kept while unresolved; partial replacement keeps unaffected knowledge. Nothing in this return deletes or ranks lessons by
recency; the step-5 supersession of a historical BINDING (`b5d0fe74`, now `73288615`) is a demonstrated source correction of
a declared table, not a lesson replacement.

## 8. Codex's review round (task doc "ACTIVE review of fourth-session return", 2026-10-07): 6R1-6R3, B2-R, B4-R, BIND-R

**Codex review after return `3667b289`:** integrated, source-only. 6R1 is addressed;
6R2-F interrupted-attempt discovery and 6R3-F read-deadline/partial-failure handling remain
open. Historical B2-R is addressed; B4-F command/inventory and BIND-F JSON/per-entry identity
remain open. Exact findings and ownership are in the current task-doc top section. The
publication trace is received, with changed claim-input identity still a Codex interface gap.
No runtime or training result is established.

Rebased onto Codex's `3bc72da8` (which lands the shared correction reader, `STEP5_CORRECTION_DELIVERY_20261007.md`, and
Greg's 22:46 ET ownership update: the step-5 reader hooks in `teach_accumulated`, `accumulated_lessons`, direct lesson
loading and the two `learner_school(stage='exchange')` call sites are Codex's; none was built here). Six commits, one
per finding: `588c9c7f` 6R1 | `1d9a1cbf` 6R2 | `d52237d3` 6R3 | `6837875a` B2-R | `bf8f87a5` B4-R | `0cb6868b` BIND-R.
The codebase-memory index was rebuilt on this tree first (generation 02:41:28Z; the first retry aborted when the rebase
changed files under it) and used for the callers of every function changed: all inside the owned modules.
SOURCE-BUILT / RUNTIME-UNVERIFIED: `ast.parse` without project imports, `git diff --check`; nothing run.

- **6R1** (`discuss_item`): a terminal LEAVE_OPEN/RESOLVED is saved in ONE durable write with its completed round and
  the item's result, and the function returns from it; on recovery a retained terminal outcome or a retained over-cap
  count is consumed before any request; the over-cap fact is saved before anything else.
- **6R2** (`LlamaServer`, `_meeting`): evidence files are content-addressed (`<sha256>-<label>.bin`, equal bytes = the same
  file; a later attempt can never renumber or overwrite); stderr is one exclusively-opened file per attempt
  (`llama-server-stderr-<attempt>.log`); each attempt writes an immutable `evidence/attempts/<attempt>.json` (stderr
  witness, evidence list, calls and tokens of that attempt) and the complete record lists every retained attempt oldest
  first. `_meeting` computes the input bytes with the durable writer's own encoding and validates the retained binding
  against them BEFORE `meeting-input.json` is touched: a changed-input retry refuses without mutating any retained file.
- **6R3** (`LlamaServer._post`, `_read_bounded`, `chat`, `count_tokens`, `start`; the record's counts): `_post` returns
  (parsed, raw) and validates each endpoint's required shape (`_expect_template` / `_expect_tokens` / `_expect_chat`)
  with the original bytes retained whole on any unusable shape, so no KeyError/TypeError escapes the meeting's own failure
  path; every chat reply's raw bytes are retained per round; bodies (success and HTTP-error) are read in chunks under the
  ABSOLUTE remaining deadline and the partial bytes are retained on expiry; the health wait parses defensively and releases
  the process on expiry; `model_calls` is derived from the retained rounds of all attempts, with `calls.this_attempt`,
  `calls_sent_without_recorded_reply` and the tokens' scope stated apart.
- **B2-R** (`aggregate_status`, `compare`): the whole-output status follows the coverage of EVERY declared comparable
  output: a declared printed/json output that could not be compared at all is a gap and the status is
  `performed_incomplete` (differs still wins; none compared is `performed_not_comparable`); `coverage` (declared,
  compared, uncovered with reasons, complete) is recorded beside the matched scope; prose stays outside comparison.
- **B4-R** (`read_dispatch`, `coherence`, `record`, `_admit`): the dispatch marker is PARSED and must name this entry,
  this plan hash, the run's argv/cwd/start, an explicit authorization and the run's capability; the plan must carry the
  CURRENT entry's command, recorded outputs, declared inventory, binding status/calculation, pins and tables; the run's
  command must be the plan's; run/plan/record name one capability revision; the comparison status is recomputed from
  its retained outputs. `record()` refuses an incoherent operation; `_admit()` re-checks on read.
- **BIND-R** (`binding_identity`, `binding_identities_differ`, `current_binding`, the lesson projection; the exchange's
  `binding_correction`, `context_checks`, the rework): identity schema `FRANKIE_BINDING_IDENTITY_V2` = status, entry ids,
  source pins, input pins (with status), each entry's command, recorded outputs and calculation; the teacher's
  `reproduction_binding` now carries it, so lessons freeze the complete identity. An older projection (flat sources)
  yields `complete=False` with the unestablished parts named; consumers record `superseded` on a real difference and
  `equivalence_not_established` otherwise, never inferring equality; a performed status is carried only when the retained
  identity is complete and equal; both seats and Frankie's rework say which case holds. No lesson is retired by age.

### The scientific-owner publication / successor interface (traced; nothing built, nothing labelled a correction)

Where a scientific owner COMPLETES a lesson today (the only points that could carry a checked decision into
`frankie_box_experiment_review.record_correction`):
1. `frankie_box_scientific_teacher.write()` -> `publish_lessons()` -> `frankie_box_brain.write_lessons_entry` (the CLI
   route: one lessons file per author/day, then the immutable brain entry).
2. `frankie_box_teacher_knowledge.teach_accumulated()` -> per result file `ST.publish_lessons` (authors
   frankie/historical/jev) or `BR.write_lessons_entry` (author search) -> the owner's `receipt.json`.
Neither computes a correction decision, and neither should: a newer or contradictory lesson is a new lesson, not a
correction (the knowledge rule). The decision exists only when an owner supplies it explicitly. The exact interface still
missing, returned as a request (the runner's scheduling is Codex's; the publication call site is mine once it exists):
- an explicit owner-supplied decision input to the publication step: `{original: {path, bytes, sha256}, scopes:
  [JSON addresses], decision: partial|full, reason, evidence: [witnesses]}` (a `--correction FILE` on `ST.main` /
  `teach_accumulated`), consumed ONLY when present; the successor lesson is the result just computed by the same owner
  against the corrected tables/inputs (not a copy with values edited);
- the successor OPERATION: a corrected retest of an already-frozen owner day needs a new accumulated out_dir
  (`require_current_selection` refuses the frozen one; `claim_inputs` binds the tables, so the result identity differs):
  `teach_accumulated(day, search, brain, out_dir_successor, successor_of=<frozen inputs.json witness>)` is the shape;
  WHO schedules it and WHEN (the next owner boundary; which lane) is the step-5 completion gap 3 and is Codex's;
- `record_correction(brain, original, replacement, scopes, decision, reason, evidence, publication_day)` is then called
  from the publication step with the owner's decision and the successor's witness, after `write_lessons_entry`
  succeeded (both complete objects retained by the reader).
Partial replacements keep every unaffected value (the reader enforces identical values outside the scopes); full
replacement is the explicit `decision`. No recency winner, no automatic labelling, no training.

## 9. Codex's review of the fifth-session return (task doc "ACTIVE review of fifth-session return", 2026-10-07): BIND-F, B4-F, 6R3-F, 6R2-F, then two adversarial review passes

Rebased onto Codex's `5e216265`. One commit per finding, then two review-correction commits from the code-review skill run
adversarially over the whole range (Greg: this has to be the last correction): `12258b3b` BIND-F | `7dd8b9a4` B4-F |
`34dab141` 6R3-F | `4b5a8eba` 6R2-F | `62eb55e3` review pass 1 | `6c804bd2` review pass 2. SOURCE-BUILT / RUNTIME-UNVERIFIED:
`ast.parse` without project imports, a static check that every dotted module used in the three modules is imported,
`git diff --check`; nothing run. The codebase-memory index was rebuilt on the rebased tree before any code change.

- **BIND-F** (`frankie_box_scientific_teacher.py`): `FRANKIE_BINDING_IDENTITY_V3`, one JSON-stable identity
  (`_json_stable`: sorted keys, no floats-by-repr drift) built PER ENTRY (status, sources, inputs, command,
  recorded_outputs, calculation; tables' shape per entry). `_validate_identity` names the parts present; a retained V2
  identity is converted (flat sources/inputs, `converted_from`, association unestablished) rather than dropped; an
  unmapped claim's empty entry set is a complete identity. `binding_identities_differ` compares the parts both sides
  establish and reports `equivalence_not_established` when neither side establishes a part; `current_binding` records
  `superseded` or `equivalence_not_established`, never equality by default. The exchange voices the unestablished case.
- **B4-F** (`frankie_box_historical_reproduction.py`): `command_argv(command)` is the producer's own contract
  (`['-B', script, *argv]`), checked against the run record's argv[1:]; `DECLARATION_FIELDS` has one definition;
  `inventory_of_outputs` requires the retained outputs to be the FULL declared comparison inventory by position, and
  an older comparison without declaration fields is reported as inventory-not-establishable, not as complete.
- **6R3-F** (`frankie_box_granite_meeting.py`): transport is `http.client.HTTPConnection` owned by the meeting; every
  blocking read (`_read_bounded`, `response.read1` under `sock.settimeout`) is bounded by the ABSOLUTE remaining
  deadline and additionally by a per-call `ceiling` (health polls 5 s, chat 600 s); partial bytes are retained on every
  failure; the socket reference is taken before `getresponse` so a Connection-close reply still releases it;
  `MeetingBudgetExpired`/`MeetingCallFailed` carry `sent` (False = the request never reached the socket) and
  `discuss_item` clears `pending_call` on a never-sent request instead of leaving a phantom interrupted call.
- **6R2-F** (`frankie_box_granite_meeting.py`): the attempt record `evidence/attempts/<attempt>-start.json` is written
  BEFORE Popen (a spawn failure is `MeetingCallFailed`, recorded as `failed_in_discussion`/`spawn_failed`); records
  carry no clock and are write-once, so a retry is idempotent; `retained_attempts` discovers attempts from records,
  orphaned stderr files and evidence directories, lists unreadable records, and marks `finished`; `_meeting` carries
  `runtime.attempts`, `unfinished_attempts` and `calls.pre_send_intents_unresolved` apart from `model_calls`
  (completed chat calls across attempts); `_record_quietly` never masks the original error.
- **Review pass 1** (`62eb55e3`, 10 findings; the gravest: the 6R3-F edit had built the `import http.client` line and
  never applied it, a NameError on every request) and **pass 2** (`6c804bd2`, 10 findings: per-call ceiling, health
  partial bodies not retained, `sent` flag, `return_witness` walks the evidence tree with rglob, spawn failure,
  clock-free attempt records, unreadable record stems, V2 conversion, duplicate-declaration check removed, coverage
  equality via `canonical()`). Both passes are recorded here so the next session does not re-find them.
- **Still Codex's**: the reader hooks, scheduling of successors, the claim-input identity mismatch at the step-5 reader.
