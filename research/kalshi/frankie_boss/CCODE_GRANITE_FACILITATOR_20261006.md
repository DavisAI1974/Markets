# CCode: smaller-model facilitator integration (Granite post-class coordinator), 2026-10-06

Branch `ccr-5fce7de3-xa4hfg`, rebased onto the `chatgpt/frankie-30day-aws-workflow-20261006` tip `eb81aead` (the four
Codex commits after `c75a805a` touch ROOT/search/docs only; CCode's step 4 files were untouched and carry over). This is
the assignment Codex's step 2 handoff labels **smaller-model facilitator integration**; it is NOT workflow Step #5.
Input: Greg's Granite discussion report, filed verbatim as `GRANITE_DISCUSSION_REPORT_20261006.md`.

SOURCE-BUILT / RUNTIME-UNVERIFIED. Checks: `py_compile`, `bash -n` on both scripts, JSON and YAML parsing, module
import, and a structural exercise of the gate and the turn validator on invented text (no market data, nothing run
against a real exchange). No model was downloaded, installed or called; no workflow was dispatched; no AWS action.

## 1. Existing implementation, inspected before building

- `knowledge/GRANITE_DISCUSSION_COORDINATOR_ROLE_V2.md` (CONFIRMED by Greg 2026-10-06) and `CLASSROOM_RULES_V3.json`
  R17: the role is settled. `GRANITE_DISCUSSION_VOICE_ROLE_V1.md` is the superseded "voice" charter.
- `deploy/aws/box/frankie_box_exchange_voice.py`: the code-only validator built for the voice charter (`voice_input`,
  `parse_output`, `validate`, `_allowed`, `NUMBER`, `POOLED`, `FORWARD`). It calls no model and its `NOT_WIRED` text is
  what `Run.voice` (`frankie_box_experiment.py` 1386), the queue (`frankie_box_frankie_queue.py` 511, 652, 1025), the
  school (`frankie_box_school_knowledge.py` 209) and the reports (`frankie_box_experiment_day_reports.py` 904) read.
  Its number/wording checks are exactly the evidence discipline role V2 needs, so the new module REUSES them.
- `frankie_box_experiment_exchange.py`: produces `exchange-frankie.json` (Frankie's view, Jev raw items withheld) with
  per-item `turns` (records: position, evidence_checks, next_tests, uncertainty; science side: proposed_tests, untested,
  cannot_test_yet, counts_per_day; Frankie side: resolution, remaining_disagreements, learned, next_steps) and
  `voice_turns` (text, lines, cites with source sha256). That file is the complete governed input of the meeting.
- The retired model routes (`frankie_box_scientific_dialogue.py`, `frankie_box_teacher_discussion.py`,
  `dipole_teacher_discussion.py` prompts, the `boss_granite_*` workflows, `frankie_box_host_config.py` disabling the
  dialogue) are the B2 critic / 131k / vLLM era. None was restored or called.
- No llama.cpp or GGUF tooling existed anywhere in the repository (grep over deploy, workflows and the frankie_boss docs
  finds only the handoff prose). Model identity pins (repository, file, sha256, llama.cpp release) are NOT in any source.
- Brain: `frankie_box_brain.py` has writers for stage knowledge (allowed kinds `ingest, day-file, root, teacher, search,
  jev-tested, survivors, confirmation`), lessons and exchange; `DAY_KINDS`, `ENTRY_GLOBS` and `parse_entry_name` register
  the readable kinds. There is no `meeting` kind, so a meeting record cannot be filed into the brain by existing code.

## 2. Built (new files only; nothing existing changed)

| file | what |
|---|---|
| `research/kalshi/frankie_boss/knowledge/GRANITE_MEETING_RUNTIME_V1.json` | the runtime contract from the report: settled (3B Q4_K_M, llama.cpp llama-server, hosts in order, ephemeral, 8B only on a demonstrated failure, forbidden routes); `pins` = six EXPLICIT BLANKS (model repository, file, sha256; llama.cpp release, asset, sha256) the gates refuse to run past; `proposed_runtime_parameters` (temperature 0.2, top_p 0.9, 400 output tokens per turn, 8192 input cap, 16384 context, 6 coordinator turns per item, 1800 s per meeting, 8 threads) with `confirmed: false`, `confirmed_by: null` |
| `deploy/aws/box/frankie_box_granite_meeting.py` | the meeting: `meeting_input` (per item the three voiced turns, the seats' retained record fields, code-seeded open items from positions/proposals/untested/cannot_test_yet/remaining disagreements; accumulated knowledge listed by label and sha only); `validate_action` (every number must be in a seat's turn and cited to its file; pooled/forward/trade/deciding wording refused; ASK needs a seat with a turn; REQUEST_TEST routes to the scientific seat and must bind to an existing proposal_id/claim_id/untested text; RESOLVED accepted only when the seats' own records already resolve it); `seat_answer` (a seat's own retained record restated by code, no calculation); `LlamaServer` (ephemeral llama-server, OpenAI-compatible chat with a JSON-schema response format; started and stopped per meeting); `discuss_item` loop with turn budget; `meeting` with the time budget, `--inputs-only`, the `FRANKIE_GRANITE_MEETING_V1` record keeping the four categories apart, and a receipt saying publication is pending |
| `deploy/aws/box/frankie_box_granite_meeting.sh` | launcher under the staged-checkout/MARKETS_SHA discipline; paths constrained to the owning experiment; without a pinned binary and model it runs inputs-only |
| `deploy/aws/box/frankie_box_granite_meeting_setup.sh` | fetches the PINNED llama.cpp release asset and the PINNED official GGUF with sha256 verification; refuses while any pin is blank; never run |
| `.github/workflows/frankie_granite_meeting.yml` | the free standard CPU runner hosting: `workflow_dispatch` only, never on push or schedule; takes a presigned GET of one day's `exchange-frankie.json` and an optional presigned PUT for the record; defaults to inputs-only; the model path refuses while pins are blank; the record is a run artifact |
| `GRANITE_DISCUSSION_REPORT_20261006.md` | Greg's report, verbatim, with a filing note |

Status of the route: **built, uncalled, unverified at runtime, unpublished.** The gate refuses the model today on seven
counts (six blank pins, unconfirmed parameters), by design.

## 3. How the role's rules are enforced in code, not prose

- Zero evidentiary weight: a coordinator turn may contain only numbers already in the item's turns, each cited to the
  file sha256 the seat cited; anything else is refused and listed (`refused`), never kept.
- Never calculate/pool/forecast/trade/grade/confirm/select: the voice validator's `POOLED` and `FORWARD` lists plus a
  `DECIDING` list (confirm, proves, survivor, promote, is valid, grade, score, tradable, ...).
- A requested calculation is executed by the proper code stage: `REQUEST_TEST` is recorded as
  `FRANKIE_MEETING_TEST_REQUEST_V1` with `status='requested_not_run'`, bound to an existing proposal/claim/untested text.
  Granite cannot name a test of its own, and nothing in the meeting runs a test.
- Private process and grades: a code answer restates only the seat's exchange record fields (R09/R10 are already applied
  upstream by the exchange); Jev raw items never enter because the input is Frankie's view.
- Nothing dropped: items not reached by the time budget are listed with their open items; an item that spends its turn
  budget is closed OPEN by code; every refused turn is kept in the record.
- Agreement is never confirmation: `RESOLVED` is refused unless Frankie's own resolution is `RESOLVED_*` with no remaining
  disagreement; otherwise only `LEAVE_OPEN` ends an item.

## 4. Exact edits outside CCode ownership, for Codex (named, not made)

1. `frankie_box_brain.py`: register kind `meeting` (`DAY_KINDS['meeting'] = 45`, between exchange 40 and survivors 50;
   `ENTRY_GLOBS` and `parse_entry_name` admit `<day>-meeting`) and add `write_meeting_entry(brain, day, record_path)`
   accepting only `FRANKIE_GRANITE_MEETING_V1` with `status == 'complete'` and the same day; same bytes reuse, other bytes
   decline, like `write_exchange_entry`. Then `frankie_box_granite_meeting.meeting` publishes immediately (CCode edit,
   one call) and `lane_state.learner_knowledge` needs `'meeting': 45` in its `before` map so later stages read it.
2. `frankie_box_experiment.Run.voice`: replace the `not_wired` record with a child call of
   `frankie_box_granite_meeting.sh` (`EXCHANGE_VIEW` = the exchange receipt's `frankie_view`, `OUT_DIR` =
   `<run>/meeting/<day>`, `BRAIN` = the plan brain, `LLAMA_SERVER`/`GGUF_MODEL` from the staged setup) when the exchange is
   done; record `done` on a `complete` receipt, `waiting` with the gate's `refused_to_run` reasons otherwise. Keep the
   stage non-blocking for school and reports as today.
3. `frankie_box_exchange_voice.NOT_WIRED` consumers (`frankie_box_school_knowledge.py` 209,
   `frankie_box_experiment_day_reports.py` 904, the queue's `passed('voice')`): read the meeting receipt/record when
   present; the school's `exchange` section gets a `discussion (meeting)` item carrying the record (four categories), the
   reports render it, and `Run.summary` stops listing the stage as not wired.
4. `frankie_box_frankie_queue.py`: `CLASS_STAGES` keeps `voice`; `_finish_day`/`class_day` pass the stage on a complete
   or gate-refused receipt (never block the day on a missing model), as the current stub does.
5. Return transport for the GitHub-runner host: the workflow uploads the record as an artifact and optionally PUTs it to
   a presigned URL; moving it into the owning lane's brain is the lane transport's job (`frankie_box_lane_state`), a Codex
   edit. On the AWS CPU box host no transport is needed (the launcher writes under the owning experiment).

## 5. Decisions still Greg's (documented, not chosen)

1. The model pins: exact official GGUF repository/file/sha256 for Granite 4.2 3B Q4_K_M. The report names the identity,
   not the artifact; nothing was guessed. huggingface.co is denied by this session's network policy (egress 403), so
   the values could not be read from the source here: either allow that host for the environment (then the Hugging Face
   tree API gives each file's sha256 without downloading weights) or paste the three values. The llama.cpp pins ARE
   filled: release b11440, asset llama-b11440-bin-ubuntu-x64.tar.gz, sha256 5e6dcc91...1fb2b, fetched through the
   session proxy and hashed in the scratchpad (contains llama-server, llama-cli, llama-completion); newer tags b11443
   to b11445 had no Ubuntu x64 asset at the time. The 8B files already staged (ibm-granite/granite-4.2-8b at f8de16cd,
   safetensors) are not a GGUF and are the escalation model, not this one.
2. The proposed runtime parameters (temperature, top_p, output tokens per turn, input cap, context, turns per item,
   meeting seconds, threads): confirm or change, then set `confirmed: true` and `confirmed_by`.
3. Which host first for the E2E: the GitHub runner path needs the small exchange view presigned out and the record back;
   the small AWS CPU box path needs the box started for the meeting and the setup script run there (an install, so a go).
4. The `json_schema` response format and `/v1/chat/completions` are llama.cpp server features; whether the pinned release
   supports them is verified only when the pinned binary exists. The parser tolerates refusal (a non-JSON reply is refused
   and re-asked within the turn budget).
5. Whether accumulated knowledge should be more than a label/sha index to the coordinator (role V2 says "applicable
   accumulated knowledge"; the 3B context argues for names only, with a code answer on request as a later addition).

## 6. Boundaries kept

No Pod, GPU, standing service, critic or self-assessment; no vLLM/131k machinery; no install, download, dispatch, model
call, AWS action, test framework or E2E. No existing file changed. Step #5 untouched; the preserved draft unapplied.
