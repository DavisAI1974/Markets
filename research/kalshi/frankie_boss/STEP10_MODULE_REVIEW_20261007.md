# Step 10 — 30-day launch readiness source review, 2026-10-07

**SOURCE REVIEW ONLY. Step 10 is not authorized and is not complete.** No AWS account
inspection/action, dispatch, installation, test, synthetic exercise, project import,
data/scientific/model call or E2E was performed. The canonical Step 9 still requires
finished wiring, the outstanding decisions and Greg's explicit AWS go for ONE real
ROOT-to-finish E2E. A successful Step 9 would not itself authorize the 30 days.

Reviewed checkout: integration tip `439cb0b` plus concurrent, uncommitted source edits.
Those other agents' edits were preserved. Applied using-agent-skills, context-engineering,
API and Interface Design, Git Workflow and Versioning, and the AWS `aws-compute` skill
(discovered with AWS documentation search, then retrieved with its Systems Manager reference).
Read AGENTS, the current night handoff, canonical Step-1 ten-step list, current spec/runbook,
and CCode's ACTIVE Step-8A ownership. Historical freeze/Pod instructions do not override them.

## Launch interfaces actually present

| Boundary | Actual source contract | Remaining prerequisite |
| --- | --- | --- |
| Submitted day list → immutable plan | `frankie_box_experiment.load_plan` validates selected class/month/year, records left-out days, preserves per-day overrides and assigns all 2021–2025 days to discovery. `main` refuses a different saved plan under the same run name. | The exact intended 30 distinct days and their supplied random order must be represented in the eventual plan. This review creates no plan and chooses no dates. |
| Preview → saved plan | `ACTION=plan` prints preview only; `main` saves `plan.json` on the start path. | Linux claim/controller use needs the actual saved main plan and claim store. A preview is not that prerequisite. CCode owns the Step-8A interface. |
| Main start → held day | `frankie_box_experiment.sh` stages against `MARKETS_SHA`; main defaults to two parallel days; queue `_book_slot` books `day-run` through the existing CPU ledger. | Main day-bound save/resume and class-child acknowledgments are Step-8 work in progress. No source-only report establishes runtime ownership/recovery. |
| CPU ledger → stage children | `frankie_box_cores.size_of('day-run')` is exactly 16; booked affinity passes to the stage; 15 workers plus coordinator. | Existing two main lanes and one Linux lane remain the entire allocation. No instance resize, additional reservation or worker-count change is proposed. |
| Linux controller → retained owner | Existing controller routes plan/status/loop/resume/stop; resume requires the retained run-day-attempt claim. | Controller lifetime, prerequisite binding, Pod refusal and exact final action routing remain CCode's Step 8A. This review does not supply a dispatch command for an unfinished interface. |
| Completed stage → next dependent work | New plans declare `completed_workflow_stages_all_30_days_no_trading_date_or_year_holdout`; existing brain/reader/successor routes own actual delivery. | Steps 2–5 and their module reviews own complete applicable consumption/corrections. A published receipt alone is insufficient. Preserve raw causal timing and host-answer/Jev walls. |
| Arm day → final completion | `Run.jev` still returns waiting after classroom/material readiness because the CPU claim seal/test/publication path is unfinished. | Resolve Jev runtime/artifact/token/core choices and owner-local completion. Do not skip Jev or accept remote PUT as consumer seal verification. |
| Source-built workflow → 30-day execution | Runbook requires successful real E2E followed by separately explicit 30-day permission. | Neither execution permission nor a successful E2E exists in this review. |

## Narrow source correction implemented

**S10-ORDER — preserve the submitted day sequence.** `load_plan` previously constructed
the day list in caller order and then unconditionally re-sorted it using date-ordered
`pair_units` (formerly lines 304–306). That silently changed an explicitly randomized input
sequence into chronological pair order, conflicting with the spec's random-order learning
clarification. After parent ownership approval, this review removed only that final sort.

The accepted list now stays in supplied order: plan entries, followed by `--days` entries,
with ordinary refusal/left-out rules unchanged. `pair_units`, its pair membership, the
classroom-arm membership calculation, `BATCH`, stage ownership and all-year discovery
policy are unchanged. No random shuffle or seed is invented. The existing plan digest
includes the ordered list; an existing saved run with a different order still refuses,
so this cannot reinterpret historical receipts. FIFO admission remains governed by the
existing readiness/queue path, and parallel day completion is not promised to occur in
the supplied order.

This is an interface correction, not evidence that the eventual 30-day plan contains the
right days or that all source prerequisites are closed. The source-only change is within
`deploy/aws/box/frankie_box_experiment.py::load_plan` only.

## Precise remaining source findings for the shared owner

**S10-SUMMARY — progress completion and CLI completion disagree.** In `Run.summary`,
`unfinished` covers requested per-day stages and pending successors. It does not include
nonfinished batch receipts; the probe chooses `complete` solely when `unfinished` is empty.
The CLI subsequently checks both unfinished days AND batch statuses and can exit 3 despite
the probe saying complete. The minimal existing-owner patch is to use the same batch-status
predicate for the probe's terminal state and the CLI decision; retain every batch receipt.
No reporting framework or new scientific verdict is needed. Not modified here because the
shared runner is under concurrent ownership.

**S10-NOT-WIRED — historical unwired flags cannot establish experiment completion.** The
same `unfinished` comprehension excludes any receipt carrying `not_wired`, even when the
receipt is unfinished; those records appear separately in `not_wired`. Source inspection
found no current writer in this runner, so this is a retained/legacy-record hazard, not a
claim that the present run already emitted such a receipt. The minimal owner correction is
to keep unfinished required stages unfinished regardless of historical `not_wired` flags.
Preserve the explicitly defined bounded Granite `non_blocking` handling separately; do not
use that exception to skip scientific or Jev work. Not modified in this review.

The queue's unused `slots_now` helper was investigated rather than treated as proof of an
allocation bug. Actual `_book_slot` calls the exact-size ledger, which refuses without 16
free CPUs. On the specified 32-CPU main box this bounds held day slots to two. No unsupported
claim of a fourth lane or scheduling patch is made here.

## AWS performance aids evaluated within the existing allocation

AWS's EC2 guidance states that EBS throughput is bounded by the lower of the instance limit
and attached volumes' aggregate performance. Therefore adding Python workers is not evidence
of an I/O speedup. The applicable future observation is to compare existing owner-local CPU,
I/O and stage-progress evidence during the one authorized E2E before changing anything.
The existing ledger, owner-local giant evidence, completed-stage reuse and small knowledge
transfer remain appropriate; no volume provisioning or concurrency increase was introduced.

AWS's Systems Manager reference describes Run Command as one-shot fleet execution. The
source already has a main-box systemd pattern, and CCode owns applying existing host/process
mechanisms to the Linux controller's lifetime. This keeps a bounded GitHub/SSM invocation
from being mistaken for durable workflow ownership. It is an application inference from
the documentation and source, not an AWS guarantee of this application's correctness.

Documentation consulted through the AWS documentation-only tools:

- `aws-compute` → `references/systems-manager.md` (retrieved exact advertised skill/file IDs).
- [Get the maximum Amazon EBS optimized performance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-optimization-performance.html).
- [Selecting IOPS and throughput when migrating to gp3](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-storage-gp3-migration-selection.html): documents independently provisioned performance and additional throughput cost; no migration or tuning is proposed under the hold.

Verification: direct source/interface inspection and `git diff --check`; no executable
project path was invoked. No runtime performance improvement or launch readiness is claimed.
