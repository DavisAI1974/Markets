# Frankie AWS handoff — step 1 recovery, 2026-10-06

**Later step-5 decision, 2026-10-06 21:53 ET:** Greg settled its purpose as market-only
checking/correction and prompt delivery of corrected knowledge. Read the opening section of
`SPEC-experiment-orchestrator.md`; it supersedes the older discussion/freeze instructions here.
No maker/taker costs, profit-based selection or freezing errors into active knowledge.
Implementation remains incomplete and every runtime execution hold remains.

## Latest CPU entry-point source update — 2026-10-06

The stale A1 controller argument defect is corrected in source. `.github/workflows/frankie_box_run.yml` now routes
its legacy `deploy/aws/box/frankie_box_pod_root_loop.sh` marker to the existing AWS CPU Linux controller with
`ACTION=plan|status|loop|resume|stop`. Pod inputs are explicitly rejected, including when empty; the active controller
step no longer passes Pod arguments or a Runpod credential. Unknown and duplicate controller inputs also refuse.
`loop` and `resume` share the existing serialized controller concurrency group; status and cooperative save requests
can reach the running controller independently. No new hosting/service choice was made.

The accepted controller fields are `ACTION`, `RUN`, `CODE_ROOT`, `BOXES`, `SLOTS`, `DATA_WORKERS`, `BUDGET_MINUTES`
and `JOB`. Use the exact Linux owner `BOXES=i-0d17573dbce871520@us-east-1` and `SLOTS=1`, including for plan/status.
`JOB=<RUN>-YYYYMMDD-aN` is mandatory for resume/stop and refused for other actions. `DATA_WORKERS` defaults to 15;
`BUDGET_MINUTES` remains 330. `CODE_ROOT` is the staged main checkout under `/opt/frankie-box/code/<dir>/markets`.
This exposes already-built controller behavior; a successful command or E2E has not been observed.

The main launcher `frankie_box_experiment.sh` and Python `--parallel-days` parser now both default to two main days.
The existing CPU ledger still owns the actual 16-CPU reservations and 15-worker allocation. Main actions remain
`plan|start|status`; no main `stop` or `resume` alias was added.

### Main save/resume remains a real ownership gap

A main-side stop cannot safely be wired by creating a Linux-style marker alone:

- `Run.save_requested` reads a process-global environment marker, while main ROOT days run in concurrent threads and
  the class worker is a separate process. Main has no day-bound marker delivery across those owners.
- `_root_job` and `_finish_job` treat `SystemExit(75)` as failure and unconditionally release the held slot.
  Queue failure/retry handling can clear ownership and start another attempt; it does not retain a saved main lane.
- `_book_slot` can accept a retained CPU list, but the main queue does not persist that list in its day entry.
  `Run.root` selects the existing interrupted attempt only on the Linux mailbox path; main ordinarily selects a new one.
- The class worker does not acknowledge an orderly saved-child transition, and `await_roots` can re-kick a worker
  without a run save check. Signal-based class shutdown must not be equated with completed child saving.

The next main recovery implementation must propagate a day-bound stop marker, retain original owner/CPU/attempt
identity, recognize the existing saved exit without release/requeue, and wait for class-child acknowledgement before
its owner exits. Reuse existing continuation/checkpoint code. Do not implement only a parser alias or process kill.
Existing ROOT-worker SIGTERM drains its running whole days; `handover` also starts a successor. Neither is a complete
main cooperative save/resume interface, and Jev's unresolved completion dependency can prevent a drain finishing.

Step #8 remains open: coordinated three-lane launch and main recovery, sustained controller lifetime beyond the
bounded runner, saved-plan/claim-store prerequisites, and dependency completion still need work. The saved main
`plan.json` must exist before the Linux controller's queue/claim route. No detached controller, new AWS service,
Jev bypass, Granite decision, or workflow #5 implementation was introduced.

Verification is shell/Python syntax and source/interface inspection only. No tests, AWS actions, installation,
dispatch, training, model call, data/scientific run, or E2E occurred. AWS compute and the later thirty-day run still
require their respective explicit authorization. Older A1-pending/interface descriptions below are historical and
are superseded only by this narrow source update; their other open items remain open.

**Latest full-depth continuation (from `166507b6`):** Greg explicitly requires all applicable full-depth MBO/FIFO
and joint accumulated-knowledge computation. New experiment ROOTs retain every level/FIFO queue, the complete resting
book observation and every original INPUT field in each successful closed group, including bytes. These enter the
existing positional group-close search; Dipole state/reason categories also reach cells. `FRANKIE_ROOT_FULL_DEPTH_GROUPS_V2`
binds resume to this projection. This does not supply identity-linked lifecycle/disabled derived planes, every APPLIED
envelope, or all BOSS/knowledge consumers. Read `ROOT_PLANE_COVERAGE_20261006.md` and
`KNOWLEDGE_CONSUMER_COVERAGE_20261006.md`. #2/#3 remain open; source/syntax only, no E2E or AWS activity.


Repository: `DavisAI1974/Markets`  
Branch: `chatgpt/frankie-30day-aws-workflow-20261006`

**Step #2 progress:** After this handoff's reading order, read `HANDOFF_20261006_STEP2_KNOWLEDGE.md`.
The learner-answer and previous-class carry slice is source-built; #2 remains open. It records the separate CCode
teacher integration, cumulative teacher-exchange lesson inputs, remaining unsupported readers and the integrated GUIDED extension (source only). No real E2E has passed.
Greg then removed chronological AND former discovery/confirmation knowledge gates: all 30 random-order days learn
from completed stages at their next boundary, including 2024 teaching a later-running 2022 day. Preserve raw per-day
timing and host-answer/Jev walls. R15 and new plan roles are amended; all years use the existing learning route.
Same-day checked knowledge is immediately available to subsequent work. Old year-split instructions below are superseded;
remaining #5 evaluation/freeze design still needs discussion, and no #5 implementation or compute has been authorized.

Fetch the latest branch and preserve newer commits. This is a **partial workflow implementation**.
Step #1 is complete in source for the retained Linux ROOT-to-finish day path. It has **not passed a real E2E**.
The prior published recovery checkpoint is `7913b478d7d16d41a1086e535fe7dbfee8df447d`; the final publication includes
this handoff and subsequent integration. Use the branch tip, not that earlier commit, to continue.

## Read first and stay focused

1. This handoff, then `HANDOFF_20261006_CHAT_RESET.md` for settled scientific and role directives.
2. `SPEC-experiment-orchestrator.md`, `Frankie_30Day_AWS_Runbook_20261006.md`, and the original
   `HANDOFF_20261006_AWS_WORKFLOW.md` / `CODEX_HANDOFF_FRANKIE_30DAY_AWS_20261006.md`.
3. `.claude/skills/experiment-orchestrator/SKILL.md`, full-run-orchestrator sections 0, 3, 5 and 7,
   `knowledge/CLASSROOM_RULES_V3.json`, and `knowledge/GRANITE_DISCUSSION_COORDINATOR_ROLE_V2.md`.
4. Apply local `using-agent-skills` and `context-engineering`. Greg authorized parallel coding agents; split file
   ownership and integrate their work. Do not create a test farm or substitute source wiring for runtime evidence.

**Next is #2, actual legal knowledge delivery. Stop and discuss with Greg BEFORE #5, freeze and confirmation.**
Greg also requires discussion before deciding/wiring Jev's pending CPU route or changing his completion dependency.
Granite needs its own discussion before final workflow wiring/E2E. Do not reopen settled scientific mathematics.

## Ordered checklist

- [x] 1. Linux ownership and retained-day save/resume implementation — source-built, runtime unverified.
- [ ] 2. Finish actual legal knowledge delivery to learner inputs, including reused teachers and previous-class state.
- [ ] 3. Complete existing native-field search surfaces, cross-transform pairs, conditions/cells, targets, Dipole,
  scoped claims and the unchanged symbolic discovery engine.
- [ ] 4. Candidate/survivor batches and scientific double-checks, with equal checked single-occurrence treatment.
- [ ] 5. Wire market-only checking/correction through affected calculations, findings and lessons; deliver checked corrections to Frankie before dependent work. Purpose settled with Greg at 21:53 ET; implementation remains open. No trading costs/profit objectives or knowledge freeze.
- [ ] 6. Discuss Granite, then wire its bounded CPU post-class facilitator role.
- [ ] 7. Discuss/finish Jev CPU blind comparison, claim sealing/testing and immediate tested-knowledge publication.
- [ ] 8. Finish the three-lane launch/status/resume/stop interface, dependencies, controller lifetime and Pod audit.
- [ ] 9. After wiring, Granite discussion and Greg's explicit AWS go: ONE real ROOT-to-finish E2E; fix actual failures.
- [ ] 10. Launch all 30 days only when separately authorized.

## Step 1 built

- Linux acceptance and resume are serialized; a retained day keeps its owner, attempt, 16-CPU set, work and cache.
  Atomic acceptance and process locks cover interrupted launcher bookkeeping. Runtime acceptance refuses legacy
  Pod/shipping jobs. Failed/setup/input days retain their files and claim rather than freeing the lane for another day.
- A durable `save-request.json` requests cooperative saving. Parent SIGTERM/SIGINT/SIGHUP creates the request;
  it does not kill the process group. Children with continuation hooks save the active operation and then stop.
  The common runner starts no next stage. Exit 75 means saved. In-flight work is drained and retained.
- ROOT saves extracted INPUT rows/cursor; live adapter and canonical state, unfinished event groups, caches and
  dict/counter order; binner; previous book; next calculation input; every output spool. Finished ROOT calculation
  receipts are reused locally. Source verification may reread a sealed prefix; completed calculations are not replayed.
- Teacher raw state retains both streams, pending groups, whole-day totals/cohorts, rows and hashes in one pickle,
  preserving shared references. Attachment preparation/base normalizer state and completed worker chunks are saved
  separately. Only missing chunks run on resume. Publication of rows, attachment, external key/receipt and final
  teacher receipt is recoverable; an early rows file alone no longer marks the teacher complete.
- Classroom phase state retains the complete package/external key, legally selected learner inputs, each component
  answer, grades, corrections and finish outputs. Histories and the complete brain entry publish before the final
  receipt. `completion.json` alone no longer proves classroom completion.
- Search recovery saves prepared arrays, transforms, cells/jobs, per-predictor state and the next partner position,
  emitted rows and counts. Completed parts are reused; submitted workers drain before saving. Search mathematics,
  cell/lag selection and confirmation parsing in the active file remain at the prior published behavior.
- Input transport retains HTTP-range and multipart progress and refreshes signed URLs without changing source
  identity. Preparation can resume the original central claim before a job reaches the worker. Old claims lacking
  the new preparation pins refuse reconstruction explicitly; no new attempt is guessed.
- RPC requests retain the full payload and ID. Restart replays pending coordination before advancing. Resume keeps
  the controller serving that job and cannot launch another day. An explicitly released remote claim can requeue;
  a retained failed/saved claim stays with its lane.
- Main receives actual owned-day stage receipts and a `remote_calculations` ROOT marker, avoiding attempts to read
  Linux-local giant artifacts. Per-day teacher completion is transported. Shared batch receipts stay scoped to the
  contributing owner/day; a lane result does not falsely mark a global batch complete.

These changes are ordinary source implementation, **not runtime verification**. An orderly save finishes the active
indivisible operation and preserves all its results/state before stopping. Source preparation, transforms and other
unhooked packaging operations may finish their current operation before honoring stop. This is not a promise to
recover arbitrary unsaved RAM after SIGKILL, power loss or a machine crash. Mismatched unsaved spool bytes are retained
and refused rather than silently rewound. The pre-ROOT ingest code's unfinished pass/segment recovery has separate
limits; the Linux path starts from validated sealed inputs. Preserve those ingests and address any genuinely missing
day's preparation in #8. Do not describe every historical process in the repository as fully crash-resumable.

## Actual commands built, not executed

The controller CLI now supports `plan`, `status`, `loop`, `resume`, and `stop`; the historical `create`/Pod options
are rejected. On an authorized controller host with the existing AWS credentials and a staged main-box checkout:

```sh
python research/kalshi/frankie_boss/pod_root/controller.py --action status --run RUN --code-root /opt/frankie-box/code/STAGED/markets --boxes i-0d17573dbce871520@us-east-1 --slots 1
python research/kalshi/frankie_boss/pod_root/controller.py --action stop --run RUN --code-root /opt/frankie-box/code/STAGED/markets --boxes i-0d17573dbce871520@us-east-1 --slots 1 --job RUN-YYYYMMDD-aN
python research/kalshi/frankie_boss/pod_root/controller.py --action resume --run RUN --code-root /opt/frankie-box/code/STAGED/markets --boxes i-0d17573dbce871520@us-east-1 --slots 1 --job RUN-YYYYMMDD-aN
```

`stop` requests a save; inspect status for `saved` before any separate machine stop. `resume` is compute dispatch and
requires Greg's explicit AWS go. The final GitHub workflow route and main-lane stop interface remain #8; do not assume
that the marker shell or an old workflow automatically exposes these controller arguments.

## Claude audit and remaining launch defects

`CLAUDE_AWS_WORKFLOW_AUDIT_20261006.md` was read from Claude's branch `ccr-e9f0f4af-lqxmss`, commit `a0a295d0`,
and copied unchanged into this branch. It audited `4ca39002`; its findings are historical observations, not a claim
that later fixes ran. Disposition:

- A2 Linux stop, A3 resume/continued coordination, A4 input renewal and A5 released-claim reconciliation: source fixed.
  Main-lane drain/stop interface remains #8. Cooperative save replaces the proposed process-group kill.
- A6 main completion reconciliation: source fixed for day receipts and ROOT ownership. Cross-owner scientific batch
  aggregation/testing remains #4/#8. Main explicitly waits when a batch would need worker-local evidence.
- A1 stale workflow dispatch arguments and final launch entry: pending #8. Retired Pod creation remains forbidden.
- A8 controller lifetime across long Linux days: still pending. Choose sustained existing-runner service or a detached
  main-box controller before launch; do not silently create a new AWS service.
- A7 Jev: still pending discussion/wiring. Do not turn its waiting result into a fake completed day or bypass blindness.
- B1 duckdb/pyarrow Linux installation: pending dependency work and AWS go; nothing was installed on a box.
- B2 main saved plan/claim-store launch prerequisite: document and wire in #8.

## Step 2 and 3 work preserved for continuation

Legal-knowledge implementation now includes immutable imported versions, actual learner-visible JSON/school inputs,
source-bound teacher findings and individual search findings, plus classroom reproduction/knowledge receipts.
This groundwork was preserved with the recovery integration; **#2 is not checked off**. Follow actual reader inputs,
finish previous-class small-state carry and causal/answer-wall handling, and ensure reused rows publish knowledge.
Large-source pointers whose bytes are unavailable remain unread; a version receipt is not consumption.

The prepared surface helper is retained, but full native search integration is not active yet. All earlier local
search-surface/conditional-lag/frozen-lag draft changes are preserved in:
`drafts/SEARCH_SURFACE_AND_CONFIRMATION_NOT_APPLIED_20261006.patch`.
It applies against this checkpoint's recovery-enabled search file. **Do not apply it wholesale**: extract/review #3
surface changes separately; the frozen-confirmation changes stay pending Greg's #5 discussion. Its mathematical
checks and not-measurable cases still need ordinary wiring review; no runtime results exist. `odcore/symbolic.py`
was not modified. Do not mistake the patch or surface helper for completed discovery/freeze/confirmation.

## Settled constraints and verification

AWS CPU only; exactly two main 16-CPU lanes on `i-035994afa8bdf66a5` (`r7i.8xlarge`) and one Linux 16-CPU lane on
`i-0d17573dbce871520` (`r7i.4xlarge`), both us-east-1, 15 workers plus coordinator per lane. No fourth lane, Pods,
Jev Pod revival, instance start or dispatch. The latest read-only MCP inspection found both stopped and not configured
for hibernation. AWS Step Functions redrive and ElastiCache do not automatically preserve process memory.

Keep Frankie inputs/calculations/planes/adapters/replay/Memory A and nonlinear/multivariable discovery/fitting math.
Greg's averaging concern is averaging outputs across runs, not fitting objectives. A scientifically double-checked
single occurrence has equal validity/certainty/survivor/teaching treatment; no occurrence minima or rarity penalties.
Each day needs its causal 13-point external file; consecutive values may agree. Publish legal knowledge after each
producing stage; peers refresh at legal boundaries. Preserve causal and answer walls. Discovery October 2021–2023;
confirmation October 2024–2025, with #5 discussion first. Granite candidate is 3B Q4_K_M, local/free GitHub CPU first,
then small AWS CPU; facilitator only, never critic, self-assessor or scientific judge.

Verification performed: Python syntax compilation, shell syntax, source/interface inspection, whitespace and exact
Git tree comparison for publication. No new tests, validation framework, model run, scientific experiment, E2E,
AWS instance start or compute dispatch. Pushes carry `[skip ci]`. Greg requested a new chat after this checkpoint;
continue at #2 and keep the checklist visible.
