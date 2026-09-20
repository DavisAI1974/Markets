# Master weave: the Frankie/BOSS day chain as one `day_pipeline` state machine

Architect-persona notes, 2026-09-20, read-only, produced at Greg's request for Claude chat (the architect).
Companions: `NOTES_FOR_CLAUDE_CHAT_20260920.md` (causes and cleanup) and `SIMPLIFICATION_NOTES_20260920.md`
(code-level simplification). Every file named below was read in full; run ids and timestamps come from
`CLAUDE_HANDOFF_20260920.md`. Nothing here is for the run in flight (Greg, 20:15Z: no changes until both
cycles are done); it is the design for the next run.

Two facts found in code that shape the whole design and that the earlier notes do not state:

1. **The HOLD is not an exit today on a fresh cycle.** `FrankiePrincipalAdapter.execute` writes
   `session-request.json` and then calls `session_executor`, which is `await_recorded_principal`
   (`run_actual_sunday_classroom.py`): it prints `actual_frankie_session_pending`, releases `actual-host.lock`
   and blocks in a 1-second poll until `session-response.json` exists. Exit 3 (`PrincipalPending`) happens only
   on re-entry (`execute` finds the request, `recover` raises), which is why cycle 0 reached it today only
   because the request had been written by an earlier process. On cycle 1 the cycles SSM command would sit
   inside `day_cycles.ps1` for up to `cycles_timeout` = 43,200 s waiting for Root, and `day_cycles.ps1`
   treats any status other than the two completions as a throw. The same shape exists one stage earlier:
   `read_execution_trigger` polls forever for the readiness trigger. The weave has to make both waits exits
   with a receipt, or "the pipeline never polls" is not achievable.
2. **The observer's request bytes have no writer in the repository.** `granite_retained_host.prepare` reads
   the admitted request from `runs/request-archives/<sha>/envelope.json` + `request.enc`
   (`git_request_archive.read_request_archive`) or from S3 `.../frankie/boss_requests/<sha>.json`; only the
   reader exists. The two archives on the branch (`6cd46f98`, `a7b72cf9`) were written out of band. For
   cycle 1 (a new request sha) someone has to publish the request before any observer can run; that is a
   hand-off nobody has named.

Also load-bearing: commits pushed with the default `GITHUB_TOKEN` never fire `on: push` workflows (GitHub
rule). "A push trigger on the recorder's receipt" therefore has to be "receipt committed, then an explicit
`workflow_dispatch` by the event workflow". `workflow_dispatch` created with `GITHUB_TOKEN` does run (that is
how `publish_completion` reaches `frankie_retained_completion.yml` today).

## 1. Inventory: the pieces as they exist today

### 1A. The day pipeline core

| Piece | Owns | Inputs | Receipt it writes | Dispatched by | Depends on |
|---|---|---|---|---|---|
| `.github/workflows/frankie_journal_stack.yml` | The day run: jobs `sources` (host online, stages 00-01, detects an existing ingest receipt), `journal` (the gold-standard stack on the 32-vCPU runner, receipt 02 via `--record ingest`), `checks` (16 hand-named test files + YAML validation + receiver proof), `host` (downloads 02, `day_pipeline.py` resume with `--go/--until/--cycles`, commits receipts `if: always()`), `cleanup` (`--stop-compute`, only when `keep_compute=false`). Concurrency `frankie-day-<day>`, no cancel. | typed `workflow_dispatch`: `day`, `go`, `until`, `ingest_on`, `runner`, `cycles`, `keep_compute`, `checks_only` | git commits of `runs/<DAY>/*.json`, artifacts | Human, every time (12 dispatches today) | AWS secrets; `sources` hard-pins `day == 20211003`; `checks` runs only when `checks_only` or `go` set |
| `operations/day_pipeline.py` | 7 stages `stage-sources, host-start, ingest, schedule-prefixes, cycles, package-upload, snapshot-stop`; `GATES` per stage; receipt `NN-<stage>.json` written once, chained by `previous_receipt_sha256`; `run_stage` returns `present/hold/partial/done`; `resume()` = first missing receipt, stops at `hold`/`partial`/`until`; HOLD file when `go != manifest_hash`; partial receipt for a batch; `record_external`; `host_stop`, `ensure_host_online`, `stop_compute`; `_ssm` builds the `--set` list | CLI + `day_pipeline.configuration.json` | the receipts; exit 2 on `StageRefused` | the workflow | `ec2_host.py`, `ssm_run_ps1.py`, the host scripts' last `PIPELINE_RECEIPT` line |
| `deploy/aws/host/day_schedule_prefixes.ps1` | Stage 03: runs the prefix builder, reads back its manifest | `--set Day, ToolsRoot, Python, RunRoot, CycleLimit` | `PIPELINE_RECEIPT {prefix_count, prefixes_sha256, ...}` | pipeline | the day configuration |
| `deploy/aws/host/day_cycles.ps1` | Stage 04: runs `run_actual_sunday_ec2.py ... --cycles N [--ec2-resume]`; takes the runner's last JSON line; throws unless status is one of the two completions (**exit 3 / `actual_frankie_session_pending` is a throw today**) | same + `CycleLimit` | `PIPELINE_RECEIPT {status, requested_cycles, cycles_completed, ...}` | pipeline | the runner |
| `deploy/aws/ssm_run_ps1.py` | Send a `.ps1` verbatim over SSM with `--set NAME=VALUE` prepended as single-quoted literals; refuses values with `'` or newline; prints the last 6,000 chars | `--instance --region --script --timeout --set ... --comment` | none | every host workflow | boto3 SSM |
| `deploy/aws/ec2_host.py` | `status/start/stop/snapshot/snapshots/resize`; `start` waits for SSM Online; reports the `KeepRunning` tag but cannot set it | `--instance --region action` | none | pipeline | boto3 |

### 1B. The host runner and the science boundary

| Piece | Owns | Durable records | Dispatched by |
|---|---|---|---|
| `operations/run_actual_sunday_ec2.py` | `EC2ActualHost`: numeric policy, `native-host-runtime.json` identity, composes the compact-source host over the classroom host | `native-host-runtime.json` | `day_cycles.ps1` |
| `operations/run_actual_sunday.py` | `ActualHost.__init__`: `boss_commit == HEAD`, clean tree, `self.code` = sha of every `.py` under frankie_boss + refrag (except tests) + host script, `host-identity.c15.json`. `runtime()`: source, prefix, `_training()` (identities incl. `code_hash`), tokenizer admission, `prime_cache` (re-prepare path when `host-service` absent), preparation, `actual-critic-request.json`, `host-preparation`, `host-ready-<instance>`; `--prepare-only` exits 0 here; `read_execution_trigger` polls forever for the readiness trigger; `host-service`; `critic()` on the Pod; `publish_completion` runs `gh workflow run frankie_retained_completion.yml --ref completion_workflow_ref` FROM THE HOST and raises `JobAttention` if not confirmed. Exit 0 complete, 1 stopped, 3 principal pending, 4 job attention, 5 incomplete output | the `.c15.json` records, `critic-spool/`, `completion-publication/`, `host-progress/` | `run_actual_sunday_ec2` |
| `operations/run_actual_sunday_classroom.py` | classroom package per cycle in `prime_cache`; `await_recorded_principal` (initial request and correction turn); `main(host_class)` with `--cycles` | same | same |
| `sunday_execution.py` | `execution-identity.c15.json` (pins `boss_commit`, `agent_commit`); `run_cycle(index)`: `request-plan.c15.json` saved once, journals with witnesses, `_LazyPrincipal`, `coordinator.run(...)`, `completion.c15.json`; `run_remaining(cycles=N)` | the files above | host |
| `feedback_cycle.py` | `CycleCoordinator.run` stages in `cycles.sqlite`: binding (with the declared supersede), controller, export (`_export_verified` with the declared old pins), attachment, principal_intent, principal_output (`recover` -> `PrincipalPending`), feedback, training, lessons, complete; `_save` refuses differing bytes | `cycles.sqlite`, `lessons.sqlite`, `handoff-<sha>/` | `run_cycle` |
| `frankie_principal_adapter.py` | `prepare`, `execute` (writes `session-request.json` then `session_executor(request)`; **`session_executor is None` -> `PrincipalPending` immediately after the durable write**), `recover`, `record_session_response` (host-only immutable write), `verify`; `json_form` | `principal/*.json`, `receiver/` | coordinator |
| `operations/record_actual_frankie_response.py` | The human HOLD recorder: takes `actual-host.lock`, rebuilds the classroom adapter with `session_executor=None`, validates the candidate in `response-check-<uuid>/`, then `record_session_response` -> immutable `session-response.json`; prints `actual_principal_response_recorded` | `session-response.json` only; **no receipt in the day directory, nothing on git** | Root's session, by hand |

### 1C. Operator workflows and the environment (all `workflow_dispatch`, all dispatched by a human today)

| Piece | Owns | Receipt | Notes |
|---|---|---|---|
| `frankie_host_advance.yml` + `.ps1` | fetch target, ancestry check, detached checkout, textual rewrite of `boss_commit`, dated backup; refuses dirty tree; carries a launch-day literal check for `cycle-{index:02d}` | `FRANKIE_HOST_ADVANCE_RECEIPT_V1` | `target` must be 40 hex |
| `frankie_host_supersede_code_bound_state.yml` + `.ps1` | move (never delete) the code-bound set into `superseded/<run>-<stamp>-code-<old>/`; keeps `host-instance`, `native-host-runtime` | `FRANKIE_CODE_BOUND_STATE_SUPERSEDED_V1` | tools HEAD == `boss_commit` |
| `frankie_host_declare_identity_supersede.yml` + `.ps1` + `operations/declare_identity_supersede.py` | append `{request_id, old_code_hash, new_code_hash, old_arm_hash, old_boss_commit, old_agent_commit, reason}` to `cycles.sqlite.identity-supersede.json`; refuses while a runner is alive | `FRANKIE_CYCLE_IDENTITY_SUPERSEDE_DECLARED_V1` | reason via `--set`, refused on an apostrophe (run 35533704067) |
| `frankie_host_binding_diff.yml` / `frankie_host_cycle_status.yml` | read-only probes | none | fit the SSM output cap |
| `frankie_host_restore_mapping_index.yml` + `.ps1` | fetch the ledger-mapping artifact, verify against the committed pin, stage on S3, start the host and tag `KeepRunning=true` inline, presigned URL by `--set` from a file, host re-verifies and renames | `FRANKIE_MAPPING_INDEX_RESTORED_V1` | the artifact run id typed by hand |
| `frankie_retained_granite.yml` (the observer) | `prepare` reads the request bytes (git archive or S3), tokenizer admission, `ActiveRunStore.claim`, start intent or `observe_migrated_start` (needs boot frames stamped after its own startup record -> a container restart by another actor), publishes `retained-granite-ready-<run_id>`, then `hold` (observes until the Pod exits or the 6-hour job deadline) | artifacts; S3 journal | `request_sha256`, `local_ready_json` (typed), runtime configuration |
| `frankie_deliver_readiness.yml` + `deploy/aws/host/build_readiness_delivery.py` | download the ready artifact by run id, refuse if the pins' `request_sha256` differs, build `delivery.ps1` with the six files embedded, write the immutable trigger; `READINESS_ROOT` and `HOST_CONFIGURATION` are path literals inside the generated script | `FRANKIE_READINESS_DELIVERY_RECEIPT_V1` printed | the observer run id typed by hand |
| `frankie_retained_completion.yml` + `granite_retained_completion.py` | publish the outcome into the request's S3 journal; `journal_generation` is a choice pinned in the workflow file | S3 records | dispatched by the host's `gh` with `--ref completion_workflow_ref` (stranded today on the old generation; re-published by hand) |
| `frankie_pod_control.yml` / `frankie_pod_prepare.yml` / `frankie_refresh_bootstrap_urls.yml` / `frankie_active_run_supersede.yml` | Pod inspect/start/restart/terminate; replacement prepare (the re-mint is a commit by hand); URL re-sign; close a stale S3 claim (`granite_active_run.py` has no release without a Pod STOP) | printed receipts / artifacts | Runpod key, S3 |
| Trunk only: `aws_idle_instance_guard.yml` + `deploy/aws/idle_instance_guard.py` | cron `17 */6 * * *`; stops any running instance whose hourly average CPU sat under 5 percent for six hours; exempts `KeepRunning=true` | log only | stopped the host at 16:07:50Z today while cycle 0 was preparing |

## 2. The two-cycle run as it actually ran today, with every human hand-off

`H` = a human dispatch or decision. The pipeline itself never dispatched anything except
`frankie_retained_completion.yml` (from the host).

```mermaid
sequenceDiagram
  autonumber
  participant G as Greg
  participant E as Engineer (chat session)
  participant W as Operator workflows
  participant P as frankie_journal_stack.yml
  participant X as Native host (EC2, Windows)
  participant O as Observer / Pod (Runpod)
  participant I as Idle guard (trunk cron)
  participant R as Root's Frankie session

  Note over G,E: H1 Greg: prepare the fresh pod in parallel
  E->>W: H2 pod_prepare (3 creates; a stop-retained Pod lost its GPU)
  G-->>E: H3 terminate it -> pod_control terminate
  E->>W: H4 pod_prepare watch -> 8vqdacl5t61rjx ready; RE-MINT COMMIT by hand
  E->>O: H5 observer (request 6cd46f98, ready witness typed) + pod_control restart
  E->>W: H6 deliver_readiness (ready_run_id typed)
  E->>W: H7 host_advance
  E->>P: H8 dispatch (day, go, cycles 2)
  P->>X: cycles -> REFUSED (host-identity guard, old boss_commit)
  E->>W: H9 three read-only probes
  G-->>E: H10 "Just override it!" (provenance, not science)
  loop Override chain (x2 until past __init__)
    E->>W: H11 supersede_code_bound_state
    E->>P: H12 re-dispatch
    P->>X: cycles -> REFUSED (execution-identity, then CRLF at line 843)
  end
  loop Fix chain: normalize_eol -> advance -> supersede -> re-dispatch (x4)
    E->>W: H13 normalize_eol / advance / supersede
    E->>P: H14 re-dispatch
    P->>X: cycles -> REFUSED (type-only stop, frames, classroom package, prefix batch, request sha moved)
  end
  E->>W: H15 supersede_classroom_package + rebuild_prefix_batch + supersede_readiness
  E->>O: H16 observer -> REFUSED (active-run claim) -> active_run_supersede close -> observer + restart
  E->>W: H17 deliver_readiness
  E->>P: H18 re-dispatch (15:36Z)
  P->>X: cycles: trigger read, critic request on the Pod
  X->>O: durable job; outcome.json 15:52:45Z
  X-->>W: publish_completion via gh --ref old branch -> REFUSED (old generation)
  E->>W: H19 re-publish completion by hand
  X-->>P: cycle 0 STOPPED 16:00Z (mapping/index.jsonl absent)
  I->>X: 16:07:50Z host STOPPED (CPU under 5 percent for 6 h)
  E->>W: H20 ledger_mapping rebuild + restore_mapping_index (3 attempts; starts host, tags KeepRunning)
  E->>P: H21 re-dispatch (16:28Z)
  X-->>P: bind_prefix passed; session-request.json written 16:39:23Z; STOPPED 2 s later (tuple compare)
  Note over E: fix 90e63722; checks_only family on GitHub
  loop Same coupling, four times (17:13Z, 18:16Z, 18:51Z, 19:55Z)
    E->>W: H22 host_advance (one short-sha refusal)
    E->>W: H23 supersede_code_bound_state
    E->>W: H24 declare_identity_supersede (one apostrophe refusal)
    E->>P: H25 re-dispatch
    P->>X: re-prime + re-prepare (4-13 min) -> REFUSED (binding code_hash; then arm_hash; then export boss_commit)
    E->>W: H26 binding_diff probe (read-only) when needed
  end
  G-->>E: H27 "You do the commits and then do 2 in order"
  E->>P: H28 re-dispatch (19:55Z) -> exit 3 actual_frankie_session_pending at 20:10:42Z
  Note over R: H29 (designed) Root consumes session-request.json, runs the recorder
  Note over E: H30 (designed) re-dispatch; cycle 0 finishes; cycle 1 admits
  Note over E: H31 (designed) publish cycle-1 request archive; observer; restart; deliver readiness; re-dispatch
  Note over R: H32 (designed) Root's second session; recorder; re-dispatch
  Note over E: H33 (designed) re-publish completion by hand (task 7); stop compute; revert KeepRunning (task 9)
```

Count: about 33 human hand-offs for a run whose designed shape has three (go, Root twice). Of the hand-offs
that were not fixes, every one is a typed id copied from one run into the inputs of another (`ready_run_id`,
`mapping_run_id`, `request_sha256`, `local_ready_json`, `target`), which is exactly what a state machine
carries in receipts.

## 3. The weave: one `day_pipeline` state machine

### 3.1 Principles (all already present in `day_pipeline.py`, extended)

1. **A receipt per state, written once, chained.** Keep `NN-<stage>.json` + `previous_receipt_sha256`. Add
   per-cycle sub-receipts under `runs/<DAY>/cycles/cycle-NN/` and event receipts under `runs/<DAY>/events/`.
2. **Inputs become receipts.** Greg's go, the cycle batch and `keep_compute` are recorded on the first
   dispatch as `runs/<DAY>/go.json` and `runs/<DAY>/run-intent.json`. Every later run reads them; a re-entry
   needs no typed input. (Today `go` must be retyped on every dispatch.)
3. **A WAIT is a state, not a failure.** `cycles` can end in `wait` (mirrors today's `hold`): the pipeline
   writes `06-cycles.WAIT.json {waiting_for, request_id, since}` and exits 0; the run ends green. A WAIT is
   ended only by its named event receipt; a dispatch that finds a WAIT without a newer matching event does not
   re-enter the host.
4. **The branch is the queue; the event workflow is the trigger.** Whoever ends a wait (the recorder, Greg)
   commits an event receipt through `frankie_day_event.yml`, which verifies it and then dispatches the pipeline
   for that day. Nobody types pipeline inputs; the pipeline never polls.
5. **The run owns its environment, and every id travels in a receipt, never in a typed input.** `KeepRunning`
   set at `host-start`, cleared at `compute-stop`; readiness bound to the request sha read from the admission
   receipt; completion published from the identity module at HEAD.

### 3.2 States

```
00 stage-sources        (unchanged)
01 host-start           + KeepRunning=true (receipt gains keep_running, tag_before)
02 ingest               (unchanged: journal job, --record ingest)
03 advance              host tools HEAD -> the dispatching commit (descendant only); science_hash compared
04 preflight            every pinned input on the host with its sha, LF checkout, HEAD == boss_commit,
                        Pod RUNNING and identity == checkout, URL freshness, SSM parameter type only,
                        trigger dir writable, no runner alive, KeepRunning=true
05 schedule-prefixes    (unchanged)
06 cycles               per cycle N, sub-states with receipts under cycles/cycle-NN/:
     a admitted         runner --prepare-only -> {request_id, request_sha256, host_instance_id, ready witness}
     b request-published request bytes archived (git_request_archive writer) -> {request_sha256, archive path}
     c readiness        observer (prepare+watchdog) + pod-adopt (restart on start intent) + delivery
                        -> {service_pins_sha256, six file shas, trigger path}
     d critic-complete  runner --until critic -> {job_id, outcome_sha256, startup_sha256}; completion published
                        by the pipeline -> {published: true}
     e principal-requested runner with the adapter in hold mode -> exit 3 -> {request_path, request_sha256}
                        => WAIT(principal_response, request_id)          <- Root
     e2 classroom-correction-requested (same shape, second WAIT)         <- Root
     f cycle-complete   runner resumes: recover -> verify -> learning -> readback -> completion
                        -> {completion hash, checkpoint hash, lessons hash}; active-run claim released with receipt
   06-cycles-batch-NN.json when cycle_limit < 19 (as today); 06-cycles.json when 19
07 package-upload       (unchanged)
08 snapshot-stop        (unchanged)
09 compute-stop         host stop + ingest runner stop + KeepRunning cleared -> {stopped, keep_running:false}
```

`HOLD` before 06 (no go) stays exactly as today.

### 3.3 Transitions

| From -> To | Receipt written | Trigger | Failure handling | Existing piece: stage or retired |
|---|---|---|---|---|
| dispatch -> 00 | `run-intent.json {day, cycles, keep_compute, dispatched_by, sha}` (once) and `go.json {manifest_hash, given_by, at}` when `go` is given | `workflow_dispatch` (first time) or `frankie_day_event.yml` (every later time) | intent differing from the retained one refuses | `frankie_journal_stack.yml` inputs -> receipts |
| 00 -> 01 | `01-host-start.json` + `keep_running: true` | 00 present | start or tag failure -> refuse (never run untagged) | `ec2_host.py` gains `keep-running on\|off`; inline tagging in the restore workflow retired |
| 01 -> 02 | `02-ingest.json` (unchanged) | journal job artifact | unchanged | journal job = stage |
| 02 -> 03 | `03-advance.json {before, after, science_hash_before/after, tooling_hash_before/after}`; history under `03-advance-history/` | host HEAD != dispatching sha, target is a descendant | not a descendant -> refuse; `science_hash` changed with an open cycle and no override receipt -> refuse naming the override file; with an override -> run declare + supersede, receipt each | `frankie_host_advance.yml` -> stage; supersede + declare absorbed as the override path |
| 03 -> 04 | `04-preflight.json {tools_head, lf_clean, pins: [...], pod_status, pod_identity_ok, urls_expire_at, ssm_parameter_type, runner_alive:false, keep_running:true}` | 03 present | any false -> refuse BEFORE any compute, naming the pin and the delivery workflow to run | new `day_preflight.ps1` + runner part; absorbs `pod_control inspect`, `refresh_bootstrap_urls` (conditional), the read-only checks of `frankie_host_diag`; `normalize_eol` becomes a repair tool |
| 04 -> 05 | `05-schedule-prefixes.json` | 04 present | unchanged | `day_schedule_prefixes.ps1` = stage |
| 05 -> 06a | `cycles/cycle-NN/a-admitted.json` | 05 present, `go.json` present, previous cycle `f` present | runner exit 1 -> refuse with frames | `day_cycles.ps1` with `Mode=prepare` (`--prepare-only` exists) |
| 06a -> 06b | `cycles/cycle-NN/b-request-published.json` | a present | archive write fails or sha mismatch -> refuse | **new** writer in `git_request_archive.py` |
| 06b -> 06c | `cycles/cycle-NN/c-readiness-delivered.json` | b present | observer refuses -> refuse; readiness bound to another sha -> refuse; a trigger already present with other pins -> move aside with receipt, then deliver | `frankie_retained_granite.yml` -> `workflow_call` (prepare+watchdog; `hold` dispatched separately); `pod_control restart` -> job `pod-adopt`; `frankie_deliver_readiness.yml` -> step without literals |
| 06c -> 06d | `cycles/cycle-NN/d-critic-complete.json` + `completion-published: true` | c present | exit 4 -> WAIT(`job_attention`) with the job id; exit 5 -> refuse, never resume inference | runner `Mode=execute --until critic` (**new stop point**); `frankie_retained_completion.yml` -> `workflow_call` run by the pipeline with the generation from `granite_retained_identity.py`; the host's `gh workflow run` in `publish_completion` retired |
| 06d -> 06e | `cycles/cycle-NN/e-principal-requested.json` then `06-cycles.WAIT.json` | d present | exit 3 is the success path | adapter constructed with `session_executor=None` when `host_runtime.principal_wait == 'event'`; `day_cycles.ps1` accepts the two pending statuses as lawful |
| WAIT -> 06f | `events/<request_id>-principal-response.json {response_sha256, principal_receipt_sha256, recorded_at, announced_by}` | Root runs the recorder (unchanged) then announces | event sha != the host's `session-response.json` sha (verified read-only over SSM) -> refused, not committed | `record_actual_frankie_response.py` unchanged; **new** `frankie_day_event.yml` + `operations/day_event.py` |
| 06f -> next 06a or batch/full | `cycles/cycle-NN/f-cycle-complete.json`; claim release `g-claim-closed.json` | event present | `_save` refusals -> refuse with frames (provenance-only differences vanish once the identity split lands) | runner `Mode=finish`; `frankie_active_run_supersede.yml close` -> step (or a lawful `release_on_completion` in `granite_active_run.py`) |
| 06 -> 07 -> 08 | unchanged | `06-cycles.json` present | unchanged | unchanged |
| 08 -> 09 | `09-compute-stop.json {host_stopped, ingest_stopped, keep_running:false}` | 08 present, or batch receipt present and `keep_compute:false` | a failed stop keeps the receipt absent and the tag set; the idle guard is the backstop | today's `cleanup` job + `--stop-compute` -> the last stage with a receipt |

### 3.4 One run's static job graph, and how the loop closes

GitHub cannot spawn jobs per cycle, and every cycle contains a human WAIT, so a run covers at most one cycle:

```
intent -> sources -> journal(ingest) -> checks -> advance+preflight+prefixes (runner, SSM)
   -> host-a  (SSM: finish previous cycle if an event receipt ended its WAIT; admit this cycle; exit 0)
   -> request-publish (runner: archive writer, commit)
   -> readiness: [observer prepare+watchdog (reusable workflow)] || [pod-adopt: restart on start intent]
   -> deliver (runner -> SSM)
   -> host-b  (SSM: trigger read, critic, completion intent, export, principal request -> exit 3)
   -> completion-publish (runner, reusable workflow)
   -> commit receipts + WAIT (always)
```

The next run (fired by the event) finds 00-05 present, `a`..`e` present for cycle N and the event for N, runs
`host-a` (finish N + admit N+1) and continues. When the runner reports a completion status inside `host-a`,
the run skips `readiness`/`host-b` and goes to 07-09. Runs that find nothing to do end after
`advance+preflight` in under three minutes and touch no host stage.

### 3.5 The event mechanism

- `frankie_day_event.yml` (`workflow_dispatch`: `day`, `kind` in {`principal_response`,
  `classroom_correction`, `science_supersede`, `go`}, `request_id`, `sha256`, `reason_b64`): verifies the claim
  read-only (for a response: a host script prints the sha of `session-response.json`; for go: the manifest
  hash equals the day's staged manifest), commits `runs/<DAY>/events/<request_id>-<kind>.json` with the actor,
  then `gh workflow run frankie_day_pipeline.yml -f day=<day>`. The receipt is the record; the dispatch is the
  trigger.
- Root's announce: the host already has `gh`; a small `operations/announce_principal_response.py` reads the
  immutable response, hashes it, calls the event workflow, writes `principal/announced.json`. Root's whole
  touch is: recorder, then announce.
- The observer's `hold` role (six-hour observation) is dispatched by the pipeline as a separate workflow
  outside the day run, so it cannot queue the event-fired next run behind it under `frankie-day-<day>`.

### 3.6 What exists afterwards

Workflows: `frankie_day_pipeline.yml` (successor of `frankie_journal_stack.yml`; the day is an input, the
`20211003` pins go; `checks` runs the tests directory whole and on push); `frankie_day_event.yml` (new; the
only dispatch a human or Root makes after the go); `frankie_retained_granite.yml` (gains `workflow_call`;
`hold` split out); `frankie_retained_completion.yml` (gains `workflow_call`; generation from the identity
module). Kept as operator tools: pod prepare/control, cycle status, binding diff, binding probe, diag, restore
mapping index (generalized to "deliver a pinned input"), the repair scripts. Absorbed (dispatch kept for
emergencies): host advance, code-bound supersede, declare, deliver readiness, refresh URLs, active-run
supersede, supersede readiness. Trunk: the idle guard unchanged in shape; `KeepRunning` gains an expiry form.

Python entry points: `day_pipeline.py` (stages advance/preflight/compute-stop, per-cycle sub-receipts, `wait`
outcome, intent/go/event readers, science/tooling hash helpers, `--mode`); `run_actual_sunday.py` (+ classroom,
ec2): `--until critic`, `principal_wait == 'event'`, `completion_publisher == 'pipeline'`, `self.code` split by
`SCIENCE_MODULES.json`, provenance recorded not compared; `git_request_archive.write_request_archive` (the
missing writer); `operations/day_event.py` and `operations/announce_principal_response.py`;
`record_actual_frankie_response.py` unchanged; `ec2_host.py keep-running on|off`; `day_preflight.ps1`,
`day_advance.ps1`, `day_cycles.ps1` (`Mode` + lawful pending statuses), `day_event_verify.ps1`;
`build_readiness_delivery.py` without literals.

The gold-standard reducer stack, the prefixes and the packing are not touched; every content hash check stays;
nothing is deleted on the host.

## 4. Human touchpoints that remain, and how each enters the machine

1. **Greg's go.** The first `workflow_dispatch` with `go=<manifest hash>` (recorded as `go.json` with the actor)
   or `frankie_day_event.yml kind=go` later. The HOLD persists until `go.json` exists with the right hash.
   Batch size and `keep_compute` live in `run-intent.json`; going from 2 to 19 cycles is a new intent commit,
   never a retyped dispatch.
2. **Root's Frankie session (per cycle, twice if the correction turn is pending).** Enters at
   `WAIT(principal_response, <request_id>)`: consume `session-request.json` with `prompt.md`; run the recorder
   exactly as documented; run the announce (or the event workflow by hand). The event workflow verifies the sha
   against the host read-only and dispatches the pipeline.
3. **Science-hash override.** When `03-advance` finds `science_hash` changed with a cycle open, it refuses and
   names the override file; Greg commits it (or the event workflow writes it, `kind=science_supersede`,
   `reason_b64`); the next run's advance stage runs the declaration and the code-bound supersede with the reason
   passed as base64. Tooling-only changes never reach this touchpoint once the split lands.
4. **Pod migration and Pod start/terminate** stay Greg's decisions; preflight refuses until the checkout's
   `POD_ID` matches a RUNNING Pod.
5. **Fixes.** A push does nothing by itself; the next event-fired run carries the commit to the host in
   `03-advance`. If a fix must reach the host before any event, `frankie_day_event.yml kind=advance` is the one
   manual dispatch that survives, and it carries no ids.

Idle guard contract: the pipeline sets `KeepRunning=until:<unix>` (now + 26 h) at `host-start`, refreshes it at
each host stage boundary, clears it at `compute-stop`; the guard honours `true` and `until:<t>`. A pipeline that
dies in a WAIT for more than 26 h is stopped by the guard, which is the right outcome.

## 5. Risks and open questions for Greg

1. The science/tooling split needs Greg's declared module list; until it exists every tooling fix mid-run
   still costs advance + supersede + declaration + a 4-13 minute re-preparation.
2. Making the principal wait an exit adds one runner re-entry per cycle (re-prime + re-prepare, 4-13 min
   measured today); over 19 cycles that is one to four hours of host time, unless the prepared context survives
   across processes.
3. The classroom adapter with `session_executor=None` must still refuse to fabricate the correction turn; the
   base adapter path is verified in code, the classroom path is not.
4. `observe_migrated_start` needs boot frames newer than its own startup record, so every cycle costs a
   container restart on the Pod; either the observer accepts the current boot when the Pod never stopped, or
   that cost is accepted.
5. `ActiveRunStore` releases a claim only through a Pod STOP; without a lawful `release_on_completion` the
   pipeline closes the claim per cycle by today's override path.
6. The request archive writer does not exist; until it does, cycle 1's readiness cannot start, and who may
   write the request-transport key is Greg's call.
7. The host checkout can never be where receipts are committed (clean-tree checks); all event receipts are
   committed from GitHub runners.
8. `GITHUB_TOKEN` commits never fire `on: push`, so the event workflow's explicit dispatch is mandatory; a PAT
   or App token would allow pure push triggers but adds a credential.
9. SSM output is capped near 24 KB and the sender prints the last 6,000 characters, so every host stage's
   receipt line must stay last and short; runner logs are read by the status tool, not by the pipeline.
10. `frankie_journal_stack.yml` pins `day == 20211003` in three places and lists the tests by hand; the
    successor derives both from the tree and the intent receipt.
11. Today's receipts are split across two branches (the launch branch holds the pipeline receipts, this branch
    the docs and the re-publication); the next run needs one declared branch that is both code and record.
12. Completion publication by the pipeline requires the host to stop raising `JobAttention` when it has only
    written the intent; a runner behaviour change to test against the durable job client's contract.
13. The Windows host is still PowerShell; a Linux image would replace every `.ps1` with `.sh` and remove the
    CRLF class of refusal for good.
14. `KeepRunning=until:<t>` changes the trunk guard's contract; if the guard stays as is, the pipeline refreshes
    a plain `true` and clears it at `compute-stop`, with no backstop for a pipeline that dies.
15. Whether a batch receipt should end the day with `compute-stop` (host stopped between batches) or leave the
    host running under the tag is a cost decision the intent receipt should carry explicitly.
