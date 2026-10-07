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
