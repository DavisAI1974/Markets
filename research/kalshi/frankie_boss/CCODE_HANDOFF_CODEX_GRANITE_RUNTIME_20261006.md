# CCode handoff to Codex: Granite meeting runtime is pinned and confirmed, 2026-10-06

Branch `ccr-5fce7de3-xa4hfg`, tip `eed57b3` (on top of `chatgpt/frankie-30day-aws-workflow-20261006` at `3fa9f592`, which
has not moved). CCode's files only; every existing non-CCode file is untouched. Source-built, runtime-unverified: no
model was fetched, installed or called; no workflow dispatched; no AWS action; no tests or E2E.

Read first: `CCODE_GRANITE_FACILITATOR_20261006.md` (what is built, how the role is enforced in code, the named Codex
edits), then `knowledge/GRANITE_MEETING_RUNTIME_V1.json` (the contract), then `GRANITE_DISCUSSION_REPORT_20261006.md`
(Greg's settled role and model choice).

## 1. State at this tip

| piece | state |
|---|---|
| model pins | FILLED: `ibm-granite/granite-4.2-3b-GGUF`, `granite-4.2-3b-Q4_K_M.gguf`, sha256 `e0406663...8e7d5`, 2,244,011,552 bytes (official IBM GGUF repository, not a community conversion); nothing downloaded |
| llama.cpp pins | FILLED: release `b11440`, asset `llama-b11440-bin-ubuntu-x64.tar.gz`, sha256 `5e6dcc91...1fb2b` (contains llama-server) |
| runtime parameters | CONFIRMED by Greg 2026-10-06 in chat (see below); `confirmed: true`, `confirmed_by` set |
| the gate | `gate(config)` returns `[]` on the committed configuration; it still refuses a missing binary/model at the given paths or a sha256 that differs from the pin |
| hosts | unchanged: free standard GitHub CPU runner first (`.github/workflows/frankie_granite_meeting.yml`, dispatch only, defaults to inputs-only), the small AWS CPU box second, started only for a meeting |

The confirmed eight, as committed (Greg: "Keep threads null"):

| parameter | value | note |
|---|---|---|
| temperature | 0.0 | greedy, so a turn and any facilitator failure in the one E2E reproduce |
| top_p | 0.9 | moot at temperature 0 |
| max_output_tokens_per_turn | 400 | a truncated reply is refused and re-asked within the turn budget |
| input_token_cap_per_call | 8192 | ENFORCED in code (section 2) |
| context_size | 16384 | the gate refuses a set where cap + output do not fit it |
| max_coordinator_turns_per_item | 6 | a refused reply also spends a turn |
| max_meeting_seconds | 3000 | under the workflow's 60-minute timeout with the pinned fetches; items not reached are listed open, never dropped |
| threads | null | = the host's online CPU count at launch (`resolve_threads`); an integer is clamped to it; the value used is written to the record's `runtime.effective` |

All eight are unmeasured until the one authorized E2E. The estimate behind 3000 s: on 2 cores a worst-case 6-turn
item is about 10 minutes, so about 5 such items are reached. Treat it as a canary figure, not a measurement.

## 2. What changed in `deploy/aws/box/frankie_box_granite_meeting.py` at eed57b3

- `gate`: a confirmed set must satisfy `input_token_cap_per_call + max_output_tokens_per_turn <= context_size`.
- `resolve_threads(params)`: null = `os.cpu_count()`; an integer is clamped to it. `LlamaServer` passes the resolved
  value to `--threads` and the record carries `runtime.effective = {threads, host_cpus}`.
- `LlamaServer.count_tokens(messages)`: the input's token count from llama-server's own `/tokenize` (message contents
  joined; the chat template adds a few dozen tokens, so it is a close lower bound).
- `discuss_item`: before EVERY call the transcript is counted; over the cap, no call is made, the item is closed
  `LEFT_OPEN_BY_CODE` with an `input_cap` open item carrying the round, the count and the cap. Nothing is truncated
  and nothing relies on the server's context shift (which would drop seat material silently).

Checks run: `py_compile`; JSON parse; `git diff --check`; a structural exercise with a stub server (over-cap at round 1
makes no call and lists the item open with the count; an under-cap LEAVE_OPEN runs as before; the gate still refuses an
unconfirmed set and now refuses a cap that does not fit). No server was started.

## 3. Codex's edits (named in the facilitator report section 4; not made by CCode)

1. `frankie_box_brain.py`: register kind `meeting` (`DAY_KINDS['meeting'] = 45`; `ENTRY_GLOBS` and `parse_entry_name`
   admit `<day>-meeting`) and `write_meeting_entry(brain, day, record_path)` accepting only
   `FRANKIE_GRANITE_MEETING_V1` with `status == 'complete'` and the same day; same bytes reuse, other bytes decline.
   Then `frankie_box_granite_meeting.meeting` publishes immediately (one CCode call) and
   `lane_state.learner_knowledge` needs `'meeting': 45` in its `before` map.
2. `frankie_box_experiment.Run.voice`: replace the `not_wired` record with a child call of
   `frankie_box_granite_meeting.sh` when the exchange is done; `done` on a `complete` receipt, `waiting` with the
   gate's `refused_to_run` reasons otherwise; non-blocking for school and reports as today.
3. `frankie_box_exchange_voice.NOT_WIRED` consumers (`frankie_box_school_knowledge.py`,
   `frankie_box_experiment_day_reports.py`, the queue's `passed('voice')`): read the meeting receipt/record when
   present; the school's `exchange` section gets a `discussion (meeting)` item (four categories), the reports render it,
   `Run.summary` stops listing the stage as not wired.
4. `frankie_box_frankie_queue.py`: `CLASS_STAGES` keeps `voice`; a complete or gate-refused receipt passes the stage;
   never block a day on a missing model.
5. Return transport for the GitHub-runner host (artifact / presigned PUT into the owning lane's brain) is the lane
   transport's job (`frankie_box_lane_state`). On the AWS box host no transport is needed.

Threads: Greg left the host-count rule in place ("we'll let codex figure that out"). If the staged setup on a host
wants a fixed count, set an integer in the JSON; it is clamped to the host's cores and the record shows the value used.

## 4. Still Greg's

- Which host runs the one E2E first (runner: the exchange view presigned out and the record back; box: the box started
  and `frankie_box_granite_meeting_setup.sh` run there, an install, so a go).
- Whether the pinned llama.cpp release supports `json_schema` response format on `/v1/chat/completions`: verified only
  when the pinned binary exists (the parser tolerates refusal; a non-JSON reply is refused and re-asked).
- Whether accumulated knowledge should be more than a label/sha index to the coordinator.

## 5. Boundaries kept

No Pod, GPU, standing service, critic or self-assessment; no vLLM/131k machinery; no install, download, dispatch,
model call, AWS action, test framework or E2E. Step #5 untouched; the preserved draft unapplied. Brain, experiment,
queue, exchange, classroom and lane files untouched.
