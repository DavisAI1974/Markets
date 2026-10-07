# Step 9 module review — E2E readiness, 2026-10-07

SOURCE-BUILT / RUNTIME-UNVERIFIED. Step 9 remains held. One real ROOT-to-finish
E2E needs completed wiring/discussion and Greg's explicit AWS go; the 30-day
launch needs its own later authorization. This review grants neither.

Reviewed the working tree based on `439cb0bf71968f30f94b696b85acfaa00dccc3c1`.
Other agents were editing disjoint functions during review. Applied
using-agent-skills, context-engineering, API and Interface Design, and
git-workflow-and-versioning. Retrieved AWS `aws-compute` and its
`references/systems-manager.md` through documentation-only calls. The current
night handoff and opening spec supersede older freeze/confirmation/Pod wording
inside historical skill sections.

## Actual entry and completion contract

| Boundary | Existing source contract | E2E implication |
| --- | --- | --- |
| Dispatch | `.github/workflows/frankie_box_run.yml` runs the committed box script; `frankie_box_experiment.sh:25–30` binds staged HEAD to `MARKETS_SHA`. | A staged checkout and successful dispatch do not establish completed calculation. CCode owns workflow/controller routing. |
| Main start | `frankie_box_experiment.py:2186–2249` parses selected stages, retains one immutable plan per run, then calls `Run.start`. `ACTION=plan` previews and does not persist the plan. | A preview is insufficient for Linux saved-plan/claim prerequisites. Same start interface accepts both one-day and multiday plans. |
| Default queued path | `Run.start:1950–1975` queues ROOT-ready days and kicks the worker; `frankie_box_frankie_queue.py:_finish_day` owns subsequent stages. | `STAGES` is a dispatch-stage selection, not a reliable cap on the worker's entire day execution. |
| Held day | `_finish_day:954–1057` reuses the held lane for teacher, class/search/lessons and completion. Linux calls the same finish path with its mailbox-backed class lease. | Day, owner, attempt, booking and input identities must remain the same through resume. |
| Jev | `Run.jev:1550–1568` still returns waiting on classroom-arm days until the authorized CPU blind comparison/seal/test/publication path exists. `_finish_day:1050–1057` will not close an arm day while Jev waits. | A genuine full arm-day E2E is blocked. Keep this waiting dependency; a search-only day skips it and cannot establish the full classroom/Granite/Jev path. |
| Detached start | `frankie_box_experiment.sh:69–91` returns after a systemd unit remains active for ten seconds. | Its zero exit proves launch acknowledgment, not day completion. |

## Implemented: truthful operational summary

Ownership was explicitly granted for `Run.summary` and its CLI exit accounting
only. No workflow/controller/queue behavior was changed by this slice.

- The summary adds `completion_scope: requested_stages`, `omitted_stages`,
  `status`, and `unfinished_batches`. These are additive to the existing schema.
- A requested but `not_wired` stage now prevents operational completion and
  produces CLI exit 3. Previously it was listed separately yet could leave the
  probe complete and the CLI successful.
- Failed/waiting batch receipts now prevent the probe from saying complete,
  matching the CLI's existing batch completion rule.
- The probe phase is `summary:requested_stages`. A successful subset remains
  a successful operational subset, with omitted stages explicit. It makes no
  E2E claim.
- Existing `skipped` stage and explicitly non-blocking Granite semantics remain.
  In particular, an operationally complete day with `meeting_waiting` does not
  establish that Granite facilitated the full path.

This is accounting, not a new validator, test harness or authorization system.
The `status` read action still returns the persisted summary plus current stage
receipt listings; persisted summaries can lag asynchronous workers and must
not supersede newer owner/queue/completion evidence.

## Remaining concrete gates and minimal next fixes

1. **One-day plan alone does not limit global queue dispatch.**
   `Run.start:2031–2040` kicks any pending ROOT/class queue entries, including
   other runs. The ROOT worker iterates the global FIFO for unfinished days
   (`frankie_box_frankie_queue.py:1241–1279`), without a run/day eligibility
   constraint. `PARALLEL_DAYS=1` does not turn this into a one-day authorization
   boundary. Before Step 9, the existing queue owner must bind permitted work
   to the selected run/day or refuse dispatch when other retained work could
   be consumed. Preserve FIFO: do not silently skip, delete or reorder old
   entries. This source gap is separate from today's execution hold.
2. **Finish Step 7 before declaring Step 9 ready.** Wire the existing owner-local
   Jev CPU request/seal/teacher/publication/completion contract. Do not convert
   its waiting result to done, skipped, or non-blocking.
3. **Bind the concrete E2E to its actual path.** Use one explicitly selected
   classroom-arm day, the exact staged commit and saved plan, the original
   retained inputs, and one held owner attempt. Confirm the requested stage
   list covers the ROOT-to-finish path; include applicable preparation only
   where genuinely missing. Do not infer full coverage from a subset summary.
   No exact launch command is approved here because Step 8 routing and the
   remaining model/runtime choices are still open.
4. **Preserve the distinct runtime verdict.** After authorized execution,
   reconcile existing queue finish state, owner receipts and publication/
   consumption records. Include actual Granite facilitation and sealed/tested
   Jev publication, plus Steps 2–5's applicable checks and corrected downstream
   knowledge. A `complete` operational summary or `meeting_waiting` cannot
   substitute for those outcomes. Reuse the normal receipts; add no framework.
5. **Review the CCode Step 8 return before staging.** Sustained Linux controller
   service, main cooperative save/resume, dependency prerequisites and retired
   Pod refusal remain owned source work. Neither SSM timeout increases nor a
   detached launch independently closes these dependencies.
6. **Thirty days stay held after E2E.** A successful one-day run is evidence for
   the subsequent decision, not permission to enqueue the other days. The
   generic start CLI does not represent that human authorization distinction.

## AWS tools and performance observations

Documentation supports retaining the existing EC2 + Systems Manager path.
The current three 16-CPU lanes and 15-worker allocation remain fixed. No new
host, AWS service, installation, model call, account inspection or dispatch
was performed.

- **Existing SSM Run Command plus owner-local systemd continuation** is
  compatible with this design. It avoids holding a control session for an
  entire scientific day, but only after the existing lifetime/recovery work
  is complete. AWS distinguishes delivery from execution timeouts; increasing
  one does not preserve application state or complete the other contract.
  Source: [Understanding command statuses](https://docs.aws.amazon.com/systems-manager/latest/userguide/monitor-commands.html).
- **Use the existing probe and retained receipt readers for the authorized
  E2E**, including CPU affinity/utilization, queue owner and disk headroom.
  These identify whether compute, queue waiting or control polling dominates
  before any optimization. No speedup is measured in this source review.
- **Keep large evidence owner-local and reuse completed work.** Moving giant
  ROOT artifacts between hosts or re-running completed stages would add work
  and obscure recovery evidence. Small existing knowledge/RPC transport is
  the compatible cross-box path.
- **Do not increase polling or add Step Functions/another cache as a supposed
  speed fix.** `_finish_day` contains 15/30/60-second waits for leases, booking
  and class completion. They are bounded control delays, not evidence of the
  scientific bottleneck. Preserve the existing waits until the real run shows
  an avoidable delay.
- **SSM success is insufficient evidence.** AWS documents that a script's last
  command supplies its default exit code; this repository additionally has a
  deliberately detached launcher. The accounting fix above prevents known
  local false-completion cases but cannot turn transport success into E2E
  success. Source: [Troubleshooting Systems Manager Run Command](https://docs.aws.amazon.com/systems-manager/latest/userguide/troubleshooting-remote-commands.html).

## Verification boundary

Read source and reviewed the exact small patch. Python syntax was parsed using
`ast.parse` without importing project code; whitespace checked with
`git diff --check`. No tests, synthetic exercises, validator, imports of project
modules, dependency installs, data/scientific/model execution, reproduction,
AWS account calls, starts, dispatch, E2E, commit or push occurred in this slice.
