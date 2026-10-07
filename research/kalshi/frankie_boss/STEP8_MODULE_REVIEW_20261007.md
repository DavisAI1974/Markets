# Step 8 module and AWS workflow review — 2026-10-07

SOURCE-BUILT / RUNTIME-UNVERIFIED. Step 8 remains open. Exactly two main lanes and one Linux lane, each 16 CPUs with 15 workers plus its coordinator. No tests, project imports, synthetic executions, installs, model/data/scientific runs, AWS account inspections/actions, starts, dispatch or provider calls occurred. No commit or push was made by this review.

Applied `using-agent-skills`, `context-engineering`, `api-and-interface-design`, and `git-workflow-and-versioning`. AWS `aws-compute` was discovered through `search_documentation`, then loaded with its `references/systems-manager.md` workflow. AWS calls retrieved documentation only. The current handoff, Step 1 review, runbook/spec and top ACTIVE CCode assignment govern; earlier run/Pod descriptions are historical.

## Actual action and ownership contracts

| Action / entrypoint | Owner and retained contract | Current limitation |
| --- | --- | --- |
| Main `frankie_box_experiment.sh ACTION=plan` | Main plan/readiness preview, pinned `MARKETS_SHA` and staged `CODE_ROOT`; Python `load_plan` supplies plan | A preview is not the saved run plan required by Linux queue/claim admission. |
| Main `ACTION=start`, optionally `DETACH=on` | Existing main systemd launch pattern; run plan and stage receipts under `work/experiment/<RUN>`; ROOT/class queues own day work | Main still has no general day-bound stop/resume action. Process-global save markers do not supply the missing ownership protocol. |
| Main `ACTION=status` and queue `ACTION=show` | Main summary and retained ROOT/class entries, attempts, worker state and stage evidence | No status observation was performed. Queue status now adds `source_owner`; worker `waiting_owner` means refused admission, not saved completion. |
| Linux legacy `frankie_box_pod_root_loop.sh` workflow marker, `plan/status` | CPU controller uses main queue/claim route and existing worker status | Workflow requires exact Linux owner and one slot; direct CLI prerequisite/legacy-input checks remain CCode's work. |
| Linux `loop` | `pod_root/controller.py` coordinates the existing Linux worker and its held run/day/attempt | Still runner-bound in reviewed source, default 330 minutes. Sustained lifetime belongs to CCode Step 8A. |
| Linux `resume`, original `JOB=RUN-YYYYMMDD-aN` | Same held Linux claim, renewal and worker coordination | Same owner/attempt recovery is required; no replacement day, host or slot. Controller lifetime/prerequisite integration is pending. |
| Linux `stop`, original `JOB` | Worker durable cooperative save request; worker owns save acknowledgment | A request is not proof the child is saved. Controller and worker states must be reported separately. |
| Main queue `kick/handover` | Existing serialized worker locks, whole-day bookings and source-pinned entries | Handover does not migrate a retained day to new code. Global queues can contain other runs; a one-day run does not isolate dispatch scope. |

CCode exclusively owns the controller, workflow controller/retired-Pod gates, legacy marker and dedicated controller launcher. None was edited. Main shell launcher was inspected as an existing lifetime pattern, not modified.

## Source changes made

### Retained source admission

`frankie_box_frankie_queue.py` adds the optional `source_owner` object containing the exact commit and resolved staged checkout path. A never-started day binds these at its first take. ROOT and finish take paths save the owner and attempt/finish intent before starting their thread. Class take saves source intent before report/attempt effects. `_run_for` carries the source owner into `Run`; `_after_root` copies it to the class entry with the held booking.

`_source_wait` runs at worker admission before a booking, attempt mutation or scientific dispatch. A different commit/path, unavailable retained checkout, or older started entry without source-owner evidence waits for explicit owner recovery. It does not infer the original source from the new worker or silently initialize a replacement identity. Already completed days remain completed. The source check also precedes ROOT reconciliation and receipt-after-found recovery, so a different-source worker cannot first relabel the retained attempt as gone and queue a replacement.

Workers report `waiting_owner` with exit 5; probes report `waiting`, not failed. Entries keep their existing attempt and state. A ROOT owner wait prevents new ROOT admission; the class FIFO remains blocked at its original entry. The owner source is exposed additively by `line_view`. No new queue state, attempt ID, model/data input, math rule or scientific acceptance threshold was introduced.

The source binding relies on the existing staged-checkout/commit verification. It does not claim a new filesystem immutability mechanism or retroactively prove historical source. Old started entries lacking the binding require explicit recovery; this review adds no migration command. This source admission protection is separate from general main save/resume, which is still incomplete.

### Classroom held-slot refusal

`class_worker` checks the held day booking before taking the entry or reserving another school/report attempt. `class_day` repeats the guard at its actual dispatch boundary and returns waiting if the binding or live booking is absent. It no longer silently omits `run.slot_booking` and lets child code book a new slot. The Linux in-process classroom route already supplies its live booking and continues through the same guard; its retained worker owns source validation.

`_after_root` refuses to replace an existing different class-source binding and leaves that entry/booking intact. Its additive `owner_waiting` result makes `_finish_day` hold the current thread and slot before reading any old class failure. It polls for explicit source recovery without returning a failed/saved terminal result or starting another attempt. A save request during this unresolved source conflict remains pending; this is not a save acknowledgment. A source disagreement requires owner recovery, never copied replacement provenance.

### Stop-before-kick protection

`Run.await_roots` checks the existing save request before polling and before re-kicking a missing worker. `Run.kick` checks before its broad error handler, so every caller, including the final `Run.start` kick loop, honors the existing save exit. These guards do not deliver a per-day save request to independent class processes or acknowledge a child save.

## Open main lifecycle interfaces

These are implementation work, not hidden launch assumptions:

1. Persist a main run/day/host/attempt/exact CPU set and per-day marker before dispatch. Each concurrent `Run` needs its own marker and child environment; do not mutate a process-global environment variable across day threads. The current source owner is one field of this contract, not the complete contract.
2. `_root_job` / `_finish_job` still group exit 75 with failures and release the booking. A real saved result must retain its original claim and CPU identity, prevent ordinary reconciliation/retry, and distinguish saved from failed, running, done and unknown.
3. The class worker's SIGTERM `Bound` path is not a child-save acknowledgment. The main day must wait for an acknowledgment bound to the same marker, booking, child and attempt before ending its owner process. The CPU ledger currently reaps dead-process bookings; changing that requires a complete retained-owner protocol, not suppressing release in one `finally` block.
4. Main `Run.root` still needs an owner-bound attempt supplied by the main queue. The Step 1 fix now honors the existing Linux `FRANKIE_LANE_ATTEMPT`; it is not a main attempt allocator.
5. Queue workers are global across runs. `Run.start`/`Run.kick` does not constrain the worker to that run's days. Before the separately authorized ONE E2E, source needs an exact dispatch gate that cannot admit unrelated pending entries, or the authorized scope must be explicitly reconciled against all queue entries. Merely requesting one day is insufficient. No global queue redesign was made here.

No additional lane, parallel day, CPU model allocation or automatic scientific retry is implied. Jev's completion dependency stays intact; a relay/PUT acknowledgment is not scientific day completion. The Step 7 runtime/model/core decisions remain open.

## Exact outstanding CCode Step 8A boundaries

- Place the existing controller process on the existing authorized main host using the established staged source/systemd pattern, with run-bound single-controller ownership and durable status beyond a GitHub runner's lifetime. Preserve both controller lifetime and the worker's independent retained job.
- Require saved main `plan.json`, its run/code identity, active existing claim-store route and the authorized worker owner before claiming/starting. Retained unknown handoffs must preserve their original receipt and claim.
- Validate `plan/status` as well as mutations at the direct CLI boundary. Reviewed direct CLI still has old Pod option declarations, a `data-workers` default of 48, and only rejects `--pods` when nonempty; empty retired flags and non-mutating owner constraints therefore require explicit refusal. The workflow supplies 15, but direct invocation cannot rely on that wrapper.
- The workflow still has Jev/CLM Pod launch and `always()` cleanup paths. Refuse retired inputs before any provider call, including cleanup. Keep historical source/artifacts. These are CCode-owned changes, not authorization to call a provider.
- Bind SSM/credential prerequisites from existing source and explicitly name any missing host dependency. Do not silently install, provision or embed new credentials. Controller success must not be inferred from a finite budget exit.

## AWS processing-speed aids researched

No measured bottleneck or speedup is claimed. Source-only findings favor avoiding repeated work and preserving owner-local evidence before changing infrastructure.

| Tool or mechanism | AWS evidence and applicability | Decision within this task |
| --- | --- | --- |
| Existing EC2 Linux `vmstat` / `sar`, existing progress probe | AWS documents CPU user/system/I/O-wait/steal and paging observations to distinguish compute, I/O and host contention. | Use only already-present tools during a separately authorized run. No installation, sample, alarm, paid monitoring enablement or instance change now. |
| EBS detailed performance statistics on supported Nitro instances | Counters expose I/O completions, latency distributions and time exceeding volume/instance IOPS or throughput limits. | Useful future evidence for the owning lane's bottleneck; host/Nitro/device support is unverified. No `ebsnvme` installation, device change or extra provisioned IOPS. |
| S3 Range GET / aligned parts | AWS documents higher aggregate throughput with bounded concurrent ranges and shorter retry transfers, aligned to original multipart boundaries when possible. | Existing transfer prefix/range recovery remains useful. No new concurrency/request cost or output-commit protocol without a measured need; preserve full hashes and evidence. |
| Existing SSM Run Command + detached systemd process | SSM is the existing one-shot control transport; node prerequisites include agent, permissions and network reachability. | CCode should reuse the existing persistent host process pattern. SSM success is not scientific success or a save acknowledgment. No new AWS orchestration service. |
| Correct retained source/slot admission | Inference from the existing continuation implementation: preserving its original owner prevents an invalid attempt from replacing reusable results. | Implemented source guard. This prevents an incorrect retry path; no numerical performance gain is asserted. |

Sources retrieved through AWS documentation search/skill tools:

- [AWS EC2 CPU troubleshooting](https://repost.aws/knowledge-center/ec2-troubleshoot-cpu-utilization)
- [Amazon EBS I/O characteristics and monitoring](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-io-characteristics.html)
- [Amazon EBS detailed performance statistics examples](https://aws.amazon.com/blogs/storage/uncover-new-performance-insights-using-amazon-ebs-detailed-performance-statistics/)
- [Amazon S3 performance guidelines](https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance-guidelines.html)
- [Systems Manager Run Command](https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command.html)

## Verification and remaining holds

Both edited Python files parse with `ast.parse` without importing project modules. `git diff --check` passes. Source review traced both admission-before-booking and lost-class-booking paths, source handover, the pre-thread save order, remote class entry shape, wait status, and save-before-kick. Other agents' edits in the shared files were preserved. No tests, synthetic exercise, run, installation, AWS inspection/action or new validation framework was used. CCode's protected files remain untouched. One real E2E requires completed wiring/discussion and explicit AWS go; the thirty-day launch requires separate authorization.
