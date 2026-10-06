# Frankie 30 Day AWS Runbook 20261006

Finish the existing AWS workflow, run one real ROOT-to-finish end-to-end day, fix actual failures, then run the 30-day experiment. Use three CPU lanes and deliver new legal knowledge to Frankie as soon as each stage produces it.

This dated runbook carries the agreed three-lane plan forward. It is the build and operating sequence for Codex; implementation comes next. AWS launch requires Greg’s explicit go.

## Starting point

- Repository: `DavisAI1974/Markets`
- Branch: `chatgpt/frankie-30day-aws-workflow-20261006`
- Handoff tip: `9d355fac22131a84646a9583c5ea18c1a2ee9589`

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

4. **Wire Granite into the post-class loop.** Use Granite as an active, bounded coordinator/facilitator under the role document and classroom rules. Its work is turn selection, clarification, bookkeeping and asking the code seats for the next test. Keep scientific calculations and judgments with their existing owners. Granite has no critic or self-assessment role in this experiment.

   Start with the agreed Granite 3B `Q4_K_M` candidate. Prefer local/free standard GitHub CPU if adequate, then small AWS CPU. Use 8B only if the real end-to-end run exposes facilitator-quality problems with 3B. Paid GPU remains a fallback; there is no standing GPU and no separate model-evaluation project.

5. **Connect the launch entry point.** Route all three lanes through the common workflow and existing queue/claim machinery. Preserve the held-slot behavior and stage knowledge refresh. Write the exact launch, status, resume and stop commands into the repository runbook once their implementation is complete; derive them from the actual entry points.

## One real end to end day

After wiring is complete and Greg gives an explicit AWS go, run one real day from ROOT through the existing completion stage.

Use that run to confirm the actual path: the day keeps its box and lane, all required search surfaces execute, survivor/freeze/confirmation finish, Frankie receives stage knowledge at the next legal step, cross-box knowledge delivery works, and Granite facilitates the post-class loop. Preserve the existing claims, receipts and completion evidence.

Fix failures where they occur and resume using the existing checkpoint rules. Do not create a validator framework, test farm, broad A/B program or additional discovery project. Use the end-to-end run’s real evidence to decide whether the wiring is ready.

## Run the 30 days

Once the end-to-end day succeeds and Greg’s explicit authorization covers the 30-day launch, enqueue the planned days through the existing FIFO and dependency rules. Run up to three eligible days concurrently. Each lane takes its next eligible day only after completing and releasing its current day.

Continue publishing and consuming legal knowledge after every knowledge-producing stage throughout the experiment. Do not wait for day-end to update Frankie’s brain. Keep learned findings available through the existing memory mechanism; do not fill memory with empty no-findings artifacts.

Monitor the existing ledger, queues, claims, stage receipts and completion records. If a day fails, preserve its state and use the existing recovery path. At completion, report the completed days, actual failures and fixes, findings carried into memory, Granite’s operating placement, and the final run/output locations.
