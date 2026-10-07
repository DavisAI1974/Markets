# Frankie 30 Day AWS Runbook 20261006

## Source continuation — steps 5 and 6, 2026-10-07 UTC

Step 5's governing decision below is unchanged. The built correction-delivery interfaces and
remaining scientific-owner/successor gaps are in `STEP5_CORRECTION_DELIVERY_20261007.md`.
CCode's step-6 return is integrated through `276d6073`; concrete remaining recovery and
historical corrections are in the newest `CCODE_NEXT_SOURCE_TASKS_20261006.md` section.
Codex has connected the new bound runtime-failure receipt to non-blocking runner/queue handling.
No independent Granite weight learning exists. The V2 exact-price adapter is source-built;
raw market prices and their time associations remain. Steps 2–6 are not declared complete.
Verification is source review/AST/whitespace only; every runtime/AWS hold remains.

## Step #5 clarified — 2026-10-06 21:53 ET

Greg settled workflow #5 as market-only checking, correction and immediate teaching of corrected
knowledge. Read the new opening section of `SPEC-experiment-orchestrator.md` for the governing
contract. Maker/taker costs and profit objectives cannot influence research selection, calculations
or verdicts. Dates/weekdays/IDs remain searchable grouping context for actual market conditions.
Fix errors through affected results and lessons; saved records must never keep known errors active.
Keep original market evidence and truthful causal identities, without adding an archival project.
The 30 days continue learning; the former year split/one-time knowledge freeze stays retired.
The discussion is complete for this scope; implementation and affected-consumer propagation remain
open. Source work only; no tests, calculations, reproduction calls or AWS execution are authorized.
The old draft stays unapplied. This workflow #5 is distinct from item 5 in the short build list below.

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

**Native recovery source slice, 2026-10-06:** bedrock information is required. An explicit default-off ROOT option now
connects complete manifest/opening state, full native checkpoints and completed-stage reuse while omitting giant rendered
bedrock tables. The queue does not activate it yet; exact lifecycle availability and actual shared consumers remain open.
Read `BEDROCK_SHARED_STREAM_ROUTE_20261006.md`. The original native model-learning/representation path also needs its
retained checkpoint, governed BOSS objective and cross-lane update lineage settled; current code discovery is not proof
of learned live recognition. CCode may own smaller-model facilitator integration separately. No AWS go or E2E.


**Latest full-depth continuation (from `166507b6`):** Greg explicitly requires all applicable full-depth MBO/FIFO
and joint accumulated-knowledge computation. New experiment ROOTs retain every level/FIFO queue, the complete resting
book observation and every original INPUT field in each successful closed group, including bytes. These enter the
existing positional group-close search; Dipole state/reason categories also reach cells. `FRANKIE_ROOT_FULL_DEPTH_GROUPS_V2`
binds resume to this projection. This does not supply identity-linked lifecycle/disabled derived planes, every APPLIED
envelope, or all BOSS/knowledge consumers. Read `ROOT_PLANE_COVERAGE_20261006.md` and
`KNOWLEDGE_CONSUMER_COVERAGE_20261006.md`. #2/#3 remain open; source/syntax only, no E2E or AWS activity.


**ROOT frame sections, source-only continuation:** the experiment now retains existing book/activity/integrity values
through the original frame spool/export/search, with a versioned resume binding. No extra producer pass or bedrock
activation. This does not establish all-plane coverage. `ROOT_PLANE_COVERAGE_20261006.md` reconciles the 99-layer roster
with the 49-layer calculation subset and lists remaining full-FIFO, event, derived-producer and knowledge-consumer gaps.
CCode's next separate task is `HANDOFF_20261006_CCODE_STEP4.md`. #2/#3 stay open; no AWS go or E2E result.

**External findings continuation:** existing external classroom discoveries now enter immediate brain publication,
actual external-pair recognition and the existing scientific reader's explicitly labelled directional projection.
Full source/scope is retained; old Dipole-only lessons cannot silently satisfy the expanded claim set. Source/syntax
only, no E2E. See the step-2 handoff for the exact scientific limits and remaining gaps.

**Next step-2 slice:** non-classroom days now call the existing accumulated-claim scientific reader on their own
completed search before following batch work. It reuses the lesson launcher/held lane and publishes results through
the existing brain writer. Source/syntax checked only; no runtime verification. Cross-owner batch coordination,
broader typed consumers and BOSS integration remain open. CCode's Step #3 source-coverage assignment is separate.

**Latest continuation:** The step-2 handoff now records the authorized learner-owned journal read and wired external
reader for SOCRATIC/VERIFY (source only), plus Greg's all-plane discovery mission and the R4 build-document BOSS role.
The BOSS retains mathematics, representation supervision, targets, masks, controls and training responsibilities;
research collaboration is additive. Its broader knowledge integration, remaining typed consumers and #3/#4 still need
completion. #2 is open. Historical pending-walk/uncalled-adapter statements below are superseded; no real E2E ran.

**08:02 ET handoff:** Greg asked to stop before completing #2. Accumulated native claims now feed owner-local
scientific calculations before classroom-arm exchanges; counts outside a claim's applied scope cannot confirm it.
CCode `c547c01a` adds an uncalled external day-file adapter. SOCRATIC/VERIFY still need Greg's ruling on a second
Dipole teacher walk and independence semantics. See the step-2 handoff for exact remaining gaps. Source-built only.

**Step #2 source checkpoint:** reused teachers, cumulative lesson exchange, cross-lane legal claim inputs and GUIDED readers are wired. SOCRATIC/VERIFY and remaining typed scientific consumers are still open. Follow `HANDOFF_20261006_STEP2_KNOWLEDGE.md`; no E2E has passed. Greg delegated the Granite discussion/report to another chat.

**Knowledge stacking applies throughout:** the classroom, Frankie, both teachers and their exchanges must use applicable completed knowledge in their actual inputs/computations, regardless of trading date. Receipt-only availability is not consumption. Greg may consider repeated refinement passes over the same data after the initial 30 days; that remains undecided and outside the current build.

**Greg, 2026-10-06 — all-30-day continuous learning:** remove both the chronological trading-date gate and the old
2021-2023 discovery / 2024-2025 confirmation knowledge separation. Stage/school knowledge becomes available when
published at the next workflow boundary, including October 2024 teaching a later-running October 2022 day. Every
assigned year uses the existing learning (`discovery`) route. ROOT lanes run in parallel. Per-day raw-source timestamps
and host-answer/Jev walls remain. Same-day checked findings feed subsequent work immediately; do not withhold
them for the rest of the day or count their reuse as an independent check.

Generate the revised plan before authorized execution; do not overwrite/reinterpret a saved plan or its receipts.
The year-role mapping and explicit knowledge-order policy change its identity. No plan was dispatched. Older references
below to untouched 2024-2025 confirmation are superseded for these 30 learning days; #5 follows the correction decision above.

**Step #2 source update:** `HANDOFF_20261006_STEP2_KNOWLEDGE.md` records actual structured knowledge reaching learner
answers, pinned versions and complete previous-class carry. Reused-teacher reconciliation is integrated; #2 remains open
for remaining evidence readers and non-arm delivery. The SOCRATIC/VERIFY refusal is a launch limitation. Availability receipts
are not consumption proof. No runtime/E2E verification or AWS compute occurred.

**Current implementation checkpoint:** `HANDOFF_20261006_STEP1_RECOVERY.md` is the next-chat handoff. Step #1
(Linux ownership and retained-day save/recovery) is source-built; runtime verification remains pending the one E2E.
The complete ten-step checkbox list and exact current low-level status/stop/resume commands are in that handoff.
Continue with #2, actual legal knowledge delivery. **Apply the later #5 checking/correction decision above**; discuss before
settling the pending Jev CPU route/completion dependency. Discuss Granite before wiring its final role.

The GitHub dispatch entry, main-lane stop interface, dependencies and long-lived controller service remain #8.
Claude's `CLAUDE_AWS_WORKFLOW_AUDIT_20261006.md` is preserved unchanged; its post-fix disposition is in the new handoff.
A save request preserves all completed results and active continuation state at the next operation boundary; it is
not an assertion of arbitrary unsaved-RAM recovery after machine loss. Do not kill a worker process group to save it.

Finish the existing AWS workflow, run one real ROOT-to-finish end-to-end day, fix actual failures, then run the 30-day experiment. Use three CPU lanes and deliver new legal knowledge to Frankie as soon as each stage produces it.

This dated runbook carries the agreed three-lane plan forward. It is the build and operating sequence for Codex; implementation comes next. AWS launch requires Greg’s explicit go.

**Latest operating clarification (Greg, 2026-10-06): Pods are retired.** Run on the three AWS CPU lanes only. Legacy `pod_root` filenames are reused controller/worker code, not Pod launch instructions. Jev's old Pod dispatch is disabled; his blind comparison needs a CPU transport before an arm day can finish. Settle Granite with Greg after core wiring and before the final workflow and real E2E.

## Starting point

- Repository: `DavisAI1974/Markets`
- Branch: `chatgpt/frankie-30day-aws-workflow-20261006`
- Original planning tip: `9d355fac22131a84646a9583c5ea18c1a2ee9589`; fetch the latest branch for implementation.

Read these existing instructions before implementing:

1. `research/kalshi/frankie_boss/HANDOFF_20261006_AWS_WORKFLOW.md`
2. `research/kalshi/frankie_boss/SPEC-experiment-orchestrator.md`
3. `.claude/skills/experiment-orchestrator/SKILL.md`
4. `knowledge/GRANITE_DISCUSSION_COORDINATOR_ROLE_V2.md` and the repository’s `CLASSROOM_RULES_V3.json`; locate the latter by filename if its directory differs.

Reuse the repository’s stage order, inventories, contracts and existing runner. Preserve Frankie’s inputs, calculations, planes, adapters, replay and Memory A. Retained native MBO records and fields must reach computation. No silent dropping, arbitrary truncation, averaging, smoothing or normalization of raw evidence.

## Three lane layout

| Lane | AWS box | Day allocation |
| --- | --- | --- |
| Main 1 | Main `r7i.8xlarge` | One held 16-core lane |
| Main 2 | Main `r7i.8xlarge` | One held 16-core lane |
| Worker 1 | Linux worker `r7i.4xlarge` | One held 16-core lane |

Reuse the existing 16-core/15-worker CPU ledger, held day slots, FIFO queues, claims and receipts. A claimed day stays on the same box and lane from ROOT through completion; hold its slot between stages. Release the slot only when the day completes or the existing recovery procedure explicitly releases it.

Three lanes is the launch architecture. A fourth lane is outside this build. GitHub can control dispatch and potentially host the small Granite process; the day computations use AWS.

## Build sequence

1. **Finish the Linux worker.** Inventory its ROOT-only path, then patch it to use the common ROOT-to-finish day runner. Carry the existing day claim, lane identity, checkpoints and receipts through every stage. Keep large ROOT artifacts on the day’s assigned box.

2. **Connect stage knowledge across boxes.** Add a small publish/pull path using the existing brain and receipt contracts. Publish new legal knowledge immediately after each knowledge-producing stage. Make it available to Frankie before the next dependent calculation or discussion step, and to other active lanes at their next legal boundary. Record which knowledge version each stage consumed. Preserve causal and answer-wall restrictions; later or forbidden information must not enter an earlier decision. Transfer the small knowledge updates and coordination state without moving the large ROOT artifacts or introducing a shared journal filesystem.

3. **Complete the existing search surface.** Wire the surfaces identified as unfinished: per-event INPUT fields, cross-transform pairs beyond the two existing combinations, other cells, conditions, additional targets, Dipole on search-only days, and claims. Use existing inventories to cover the full applicable surface. Carry results into the survivor selection, freeze and confirmation paths in the order required by the current spec. Feed any new legal knowledge from these stages into Frankie immediately.

   **New discovery remains central (Greg, 2026-10-06):** Keep symbolic equation discovery and its ability to discover new nonlinear/multivariable mathematical relationships, alongside causal search and Frankie's novel findings. Counts-based evidence and acceptance must preserve that capability. Greg's averaging restriction concerns collapsing outputs from multiple runs into an average; it does not authorize changing equation-fitting mathematics. Preserve existing discovery/fitting mathematics and objectives, and retain individual run findings. A fixed set of pairwise tests does not fulfill this requirement. Scientific discovery and judgment remain with code, never Granite.

   **Single-occurrence findings (Greg, 2026-10-06):** Double-check the mathematics, source evidence, causal timing and scientific work. A finding that still checks out after one occurrence receives the same validity, certainty, survivor, teaching and knowledge treatment as a checked multi-occurrence finding. No rarity-based uncertainty label, confidence discount or minimum-occurrence gate. Counts remain descriptive; actual errors, contradictions or incomplete checks are judged on their merits. A day with no relevant occurrence supplies no new test and does not downgrade a checked finding. This supersedes the older R06 one-appearance promotion prohibition.

4. **Wire Granite into the post-class loop.** Use Granite as an active, bounded coordinator/facilitator under the role document and classroom rules. Its work is turn selection, clarification, bookkeeping and asking the code seats for the next test. Keep scientific calculations and judgments with their existing owners. Granite has no critic or self-assessment role in this experiment.

   Start with the agreed Granite 3B `Q4_K_M` candidate. Prefer local/free standard GitHub CPU if adequate, then small AWS CPU. Use 8B only if the real end-to-end run exposes facilitator-quality problems with 3B. Paid GPU remains a fallback; there is no standing GPU and no separate model-evaluation project.

5. **Connect the launch entry point.** Route all three lanes through the common workflow and existing queue/claim machinery. Preserve the held-slot behavior and stage knowledge refresh. Write the exact launch, status, resume and stop commands into the repository runbook once their implementation is complete; derive them from the actual entry points.

## One real end to end day

After wiring is complete and Greg gives an explicit AWS go, run one real day from ROOT through the existing completion stage.

Use that run to confirm the actual path: the day keeps its box and lane, all required search surfaces execute, applicable scientific checks and corrections reach affected findings and lessons, Frankie receives corrected stage knowledge before dependent work, cross-box knowledge delivery works, and Granite facilitates the post-class loop. Preserve the existing claims, receipts and completion evidence. No fee/profit-based research verdict or knowledge freeze belongs in that path.

Fix failures where they occur and resume using the existing checkpoint rules. Do not create a validator framework, test farm, broad A/B program or additional discovery project. Use the end-to-end run’s real evidence to decide whether the wiring is ready.

## Run the 30 days

Once the end-to-end day succeeds and Greg’s explicit authorization covers the 30-day launch, enqueue the planned days through the existing FIFO and dependency rules. Run up to three eligible days concurrently. Each lane takes its next eligible day only after completing and releasing its current day.

Continue publishing and consuming legal knowledge after every knowledge-producing stage throughout the experiment. Do not wait for day-end to update Frankie’s brain. Keep learned findings available through the existing memory mechanism; do not fill memory with empty no-findings artifacts.

Monitor the existing ledger, queues, claims, stage receipts and completion records. If a day fails, preserve its state and use the existing recovery path. At completion, report the completed days, actual failures and fixes, findings carried into memory, Granite’s operating placement, and the final run/output locations.

## Source-built recovery and remaining launch order

Use the new handoff's ten-step list. The final launch must first retain the main saved plan and claim store, then
start two main lanes plus one Linux controller lane, with sustained controller service for every Linux boundary.
The historical runner marker is not yet a finished two-dispatch operating interface. Before launch, finish A1/A8/B1/B2
in Claude's audit and document exact authorized dispatches. No dependency installation, instance start or run occurred
in this checkpoint. Resume itself starts compute and requires Greg's explicit AWS go.
