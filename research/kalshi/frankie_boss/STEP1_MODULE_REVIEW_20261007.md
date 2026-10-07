# Step 1 module/interface review — 2026-10-07

Source reviewed at `439cb0b` (`ccr-5fce7de3-xa4hfg`), with other agents' in-progress changes left untouched. After Greg requested implementation, ownership was assigned for two narrow fixes: `Run.root` exact attempt selection and `lane_state._coordinate` request binding. Both are now source-built; other findings below remain proposals. Applied `using-agent-skills`, `context-engineering`, `api-and-interface-design`, and AWS `aws-compute` plus `references/systems-manager.md`, discovered through AWS `search_documentation` before `retrieve_skill`.

## Current result and precedence

The retained Linux path has substantial source-built recovery. General main/class recovery remains incomplete. No runtime recovery, transfer speed or E2E result is established. The latest top section of `CODEX_HANDOFF_20261006_NIGHT.md` supersedes old STOP-before-5 and successor-not-wired notes. The older Step 1 handoff's completed checkbox applies to Linux only. Its newer main-save gap remains visible in current code. Step 8A controller/workflow/launcher changes belong to CCode; this review does not modify them.

## Actual module contracts

| Module / entry | Input and retained output | Recovery boundary |
| --- | --- | --- |
| `pod_root/controller.py`: `start_day`, `renew`, `coordinate` | Central claim, pinned job/input manifest, transport-only URL renewal; SSM commands and RPC slots | Original run/day/attempt/owner/commit must survive retries; existing Linux worker only. Controller lifetime belongs to Step 8A. |
| `pod_root/pod_agent.py`: `accept`, `renew_job`, `run_job`, `run_full_day` | `FRANKIE_POD_ROOT_JOB_V1`, exactly 15 workers, named Linux owner, 16 saved CPUs; atomic accepted directory, per-job save marker, state and launch lock | Retained unfinished jobs block another day. Exit 75 becomes `saved`; failed setup/input/finish keeps artifacts. Resume replays pending RPC before advancing. |
| `pod_root/pod_transfer.py`: `get_to_file`, `get_parts_to_file` | Pinned length/whole-file hash and signed URLs; retained `.part` / `.assembling` bytes and multipart source binding | Range restart preserves the prefix; changed multipart identity refuses. Cooperative stop flushes/fsyncs written bytes. Caller checks the complete hash. |
| `frankie_box_experiment.py`: `Run.child`, `root`, `guarded` | Saved plan and stage receipts; child environment and optional held booking | Shared stop marker is checked before and after children. Linux now selects its exact claimed attempt for first dispatch/recovery; main does not yet preserve its exact attempt. |
| `frankie_box_frankie_queue.py`: `_root_job`, `_finish_day`, `class_day`, workers | FIFO day/class entries, whole-day slot, prior classroom and report number | Main ROOT runs in threads; classroom runs in a separate process. Their save acknowledgments and retained ownership are not joined. |
| `frankie_box_cores.py`: `book`, `held_booking`, `run --inside` | Exact 16-CPU reservation and process identities | Supports an explicitly retained CPU list; rejects unavailable/different CPUs. Main queue does not retain that list. Dead-process bookings are reaped. |
| `frankie_box_lane_state.py`: `request`, `recover_request`, `coordinate` | Durable complete request + stable ID; central owner/attempt check; class and day receipts | One request at a time, per-ID lock, full request witness before side effects and payload-bound response cache. Legacy unbound cached results refuse. |
| ROOT/teacher/classroom/search implementations | Existing pinned continuation state, operation outputs and final receipts | Reuse existing continuation/checkpoint writers. Do not replace these with a new validator or rebuild completed science. |

## Current defects and smallest proposed corrections

### S1-1 — Main/class save is still failure/requeue, not retained recovery (high)

`Run.save_requested` (`frankie_box_experiment.py:532`) reads one process-global environment variable. `_root_job` and `_finish_job` (`frankie_box_frankie_queue.py:1049–1103`) catch `SystemExit(75)` with ordinary failures and unconditionally release the slot. Worker reconciliation clears ownership on failure and permits retry. `_book_slot` accepts `x['cpus']`, but the main take paths persist only the booking ID. `Run.root` normally allocates `len(attempts)+1`; `claim_root` can release and retake its own inactive claim. A saved main attempt can therefore become a new attempt/CPU allocation.

The class worker catches exit 75 as failure (`:776`), while its SIGTERM handler raises `Bound` directly (`:423`). The resulting queued/saved status does not acknowledge a child save. `_finish_day` checks the parent's marker while the separately launched class may still own work. `class_day` silently omits `slot_booking` when it is no longer live, permitting the child's regular booking path instead of refusing lost ownership. `await_roots` and the final worker-kick loop have no save guard.

Minimal coherent patch, owned by Codex: persist run/day/owner/attempt/CPUs/marker in the existing queue entry before launching its thread; derive each `Run`'s marker from that entry without changing the parent process environment; inject it only into that day's child environment. Carry that same binding into the class entry. Treat exit 75 as a distinct saved result in both workers and reconciliation; keep the claim and exact CPU reservation identity, excluding saved entries from ordinary admission/retry. Require class-child saved acknowledgment before the owner completes saving or releases any live booking. A missing held booking must wait/refuse rather than rebook. Resume the named retained attempt. Guard both wait/kick paths. These are one ownership contract: an exit-code-only or parser-only patch is insufficient.

### S1-2 — Exact Linux ROOT attempt selection (medium; source-fixed)

`pod_agent.run_full_day` supplies `FRANKIE_LANE_ATTEMPT=job_id`, but `Run.root` (`experiment.py:796–807`) ignores it and chooses `max(candidates, attempt-number)`. It also chooses a count-based name for a remote job with no interrupted directory. A retained extra directory can redirect the operation away from the immutable claim; a claimed attempt other than `a1` can start under a different output name.

Implemented in `Run.root`: validate `FRANKIE_LANE_ATTEMPT` against the exact run/day/attempt pattern; set `owned_output = ROOTS / attempt`; use that path for first dispatch and resume, with `resume` only when it is already a directory. Refuse conflicting interrupted directories, a differently named completed local ROOT, symbolic-link output and non-directory output. Existing source/projection continuation guards remain. This deliberately refuses a remote plan naming a different completed ROOT rather than silently substituting it for the claim; any intended cross-attempt reuse needs an explicit consistent owner binding.

### S1-3 — Bind RPC intent and cached success to the complete payload (medium; source-fixed)

`lane_state._coordinate` (`:507–519`) checks owner/attempt, then returns `STATE/rpc/<id>.json` without comparing the incoming operation/body. A same-owner reused ID with a different payload receives the first operation's success. The client preserves its request correctly; the external coordination boundary does not enforce that contract.

Implemented in `_coordinate`: canonical complete-body SHA-256 plus full body are written to `<id>.request.json` under the existing per-ID lock before effects. Every retry must match both; cached response ID and request hash must match as well. Legacy cached results without a request witness refuse and remain untouched for explicit recovery. The response adds `request_sha256`; existing clients continue to read `id`/`result`. Same-ID replay, locks and owner check remain; the existing `write` function persists the witness. This does not reconstruct historical side effects for which neither intent nor result was recorded.

### S1-4 — Main recovery accepts the new worker's source instead of its retained source (medium)

`_run_for` (`queue.py:400–417`) verifies `plan_sha256`, but constructs `Run(..., code_root, commit)` from the current worker arguments. `handover` intentionally launches a worker at another commit. The queue already retains enqueuer and attempt provenance, but does not check it on resumed work. Some individual continuations refuse changed producers, but the owner contract itself does not prevent mixing already-complete old stages and new source for missing stages.

Minimal patch: bind the code root/commit when the day first takes its slot, preserve that binding on save, and require `_run_for` to use that retained checkout or explicitly refuse its absence/mismatch. Do not silently reinterpret a newly queued, never-started day as a resumed day. Any intentional source transition needs an explicit owner-bound decision; it is not ordinary resume.

## AWS performance options evaluated

AWS documentation was read through documentation tools only. No account/instance inspection, SSM command, installation, new service or spend occurred.

| Option | Current source and decision |
| --- | --- |
| Preserve completed work and download prefixes | Already the most concrete recovery-speed feature: `fetch_inputs` verifies retained files, ROOT/teacher/search reuse continuations, and transfers resume ranges. Keep full hashes and exact evidence. S1-1/S1-2 prevent losing these benefits through a replacement attempt. |
| Concurrent S3 byte-range downloads | AWS documents higher aggregate throughput and shorter retry ranges. Current `get_to_file` uses Range only on restart; multipart pieces are serial. Deferred: concurrent output commits need a bounded, durable part-order contract and may add requests/cost. No measured bottleneck or authorized extra cost supports changing it in this source-only slice. |
| Reuse existing S3 ingest objects | `Controller.s3_source` already avoids exporting a whole input when an existing object has matching size; the worker still verifies its complete SHA-256. Preserve this route and its final hash check. Do not replace content identity with size-only acceptance. |
| Avoid redundant disk reads | `get_parts_to_file` hashes downloaded pieces then rereads the assembled file for its whole-file hash. Streaming a digest during assembly could remove that final sequential read, but would change final on-disk readback semantics; no such validation reduction is made. Retain the existing proof until an equivalent full readback path is specified. |
| EBS read-ahead / provisioned throughput | AWS's 1 MiB read-ahead guidance is specifically for large sequential reads on `st1/sc1`; it can hurt random workloads. Actual volumes were not inspected. No device setting, volume migration, throughput purchase or CPU/instance change is proposed as an immediate fix. |

Sources: [AWS Systems Manager fleet operations](https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command.html), [S3 performance guidelines](https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance-guidelines.html), [S3 byte-range guidance](https://docs.aws.amazon.com/whitepapers/latest/s3-optimizing-performance-best-practices/use-byte-range-fetches.html), [EBS volume performance](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-performance.html). Systems Manager is the existing command transport, not a save-memory mechanism. Durable state must remain on persistent storage; instance-store loss on stop is explicitly documented in the AWS compute skill. Current mount durability is unverified.

## Verification and remaining holds

Source/interface review and AST parsing without project imports only: seven reviewed modules parsed, then both changed modules parsed after edits. Changed source/report whitespace checked with `git diff --check`; RPC-file consumers inspected for the additive request-witness filename. No tests, synthetic exercises, installs, data/reproduction/model runs, AWS account actions or execution. No new validator/test framework. Existing three held lanes only: two main and one Linux, each 16 CPUs with 15 workers plus coordinator. Main/class recovery, Step 8A integration, Jev completion and owner-local durability require further source work; runtime verification waits for explicit AWS authorization. Thirty-day authorization remains separate.
