# New-chat handoff — complete the remaining workflow pieces

Greg requested this checkpoint at **2026-10-07 00:54 ET** because the chat was getting buggy.
Read this first. It supersedes older next-action and rollout wording where they conflict.

## What the new chat must do

**Agents still need to work through the remaining pieces of the entire workflow.** The prior
agents completed their assigned bounded source slices; that does not mean the whole workflow
is finished or fully reviewed. Continue with separate agents, explicit file ownership and
integration review so the main agent does not become the implementation bottleneck.

Greg already directed agents to apply API/module skills, research AWS/data-processing tools
that could help each piece, and **implement suitable findings**. He initially requested plans
for Frankie/BOSS, then explicitly approved improvements that preserve the science. Carry that
approval forward; do not repeat the plan-confirmation round for that same source scope.
Use the existing AWS skill/documentation research and existing implementation before adding
anything. Do not presume a new AWS service or a measured speedup. Preserve formulas, targets,
masks, controls, numerical methods, scientific meaning, training objectives and model lineage.

**The ten-item list is an implementation/recovery/rollout checklist, not the entire workflow.**
Do not assign reporting or coverage only to those ten items. Map the actual producers,
consumers and substeps in `SPEC-experiment-orchestrator.md`, section 0, then reconcile that
map against the current code and completed reports. Its stage table includes preflight,
ingest, day data, ROOT/Frankie calculations, BOSS teaching, classroom, export, causal search,
carried and new-claim scientific checking, cross-day candidate updates, meeting, end-of-day
school/reports, Jev and corrections. Applicable substeps also need coverage. Some entries
are conditional or cross-day; do not activate an inapplicable route just to fill the map.
Separate confirmation is not automatically selected by this experiment.

## Greg's agreed AWS rollout and reporting proposal

1. Finish the necessary wiring and discussions, then pass the authorized E2E.
2. **After the E2E passes, send ONE day all the way through the applicable workflow.** This
   is a review of whether inputs are being ingested/consumed and outputs produced as Greg
   wants, not another bug-hunting test suite.
3. Give **every separate workflow piece** a reviewable report for that one-day pass. Reuse
   reports already generated. Add temporary inspection reporting only for pieces missing it.
   Show what went in, what was actually used, what came out, notable exclusions/dispositions,
   and unexpected behavior/results. References to retained real outputs can support review;
   a receipt alone must not be claimed as actual computation.
4. The extra reports are needed only this one time. **They do not need permanent storage,
   and they are not Frankie knowledge.** Do not add them to brain/lesson inputs, training,
   scientific evidence or a permanent reporting/validator framework. Preserve the workflow's
   normal scientific artifacts and existing reports; this temporary reporting requirement
   does not authorize deleting those.
5. Review with Greg and Frankie, surface surprises and requested tweaks, make the agreed
   adjustments, **then run the THREE days**. Do not jump from E2E to thirty days. A later
   thirty-day launch remains a separate decision.

This is the agreed sequence for when AWS execution occurs, not a record that it occurred.
No AWS workload, E2E, historical rework or three-day run was launched here. Preserve the
existing execution boundary and do not confuse source implementation with runtime evidence.
No additional test suite or validator framework is wanted.

## Exact source checkpoint

- Repository: `DavisAI1974/Markets`; integration branch: `ccr-5fce7de3-xa4hfg`.
- Reviewed source is committed and pushed at **`fe7cc188f49708bc825aa10a252eb028e7120dca`**.
  Its predecessors are `439cb0bf71968f30f94b696b85acfaa00dccc3c1` and the user's starting
  `4e416e1826156f59be562d78ed22e9ca886b6758`.
- The source checkpoint's 28 changed Python files passed AST parsing without project imports;
  whitespace and source/interface review passed. No tests, runtime or AWS account actions.
- Current workspace: `/workspace/scratch/e116b4e8f692/Markets`. This path may change next chat.
- The worktree was clean before this documentation-only handoff. Nothing from the new
  main-recovery assignment was edited: it was interrupted when Greg clarified the proposal.
- No implementation agent is running. Re-create or resume suitable agents in the new chat;
  completed agent status is not completion of all remaining workflow work.
- Fetch the actual latest tip; this documentation creates a later commit. Preserve newer work.
  Git CLI push lacks credentials in this environment; prior publication used GitHub app
  tree/commit/ref APIs with an expected-head lease, `[skip ci]`, and exact tree verification.

## Completed source slices and remaining work

Read `MODULE_REVIEW_INDEX_20261007.md`, `STEP5_CONTINUATION_20261007.md`, the individual
`STEP*_MODULE_REVIEW_20261007.md` reports, and both `*_MODULE_PERFORMANCE_PLAN_20261007.md`
files. Their implementation records distinguish built work from proposals and unresolved
science. Do not redo the completed cache/provider/queue/hoist or evidence-contract edits.

Concrete remaining work for the agents includes:

- Connect retained same-session corrected knowledge to the actual later learner consumer.
  The code follow-up compares scopes and retains corrected lessons; it does not yet complete
  that later consumption. Preserve original forecasts, request/input/source/session identities
  and pending outcome feedback. No replacement forecast, invented label or native training
  cycle follows from delivering a correction.
- Resolve downstream school containers that embed superseded meetings, preserving original
  artifacts and unaffected knowledge through explicit owner-bound recovery.
- Complete main/class cooperative save-resume ownership: original attempt, source, exact CPU
  allocation, day-bound marker, saved-child acknowledgment and no failure/requeue substitution.
- Bind global queue dispatch to the exact authorized run/day scope so a one-day request cannot
  silently admit unrelated pending days.
- Review/integrate the returned CCode Step 8A work described below and reconcile its interfaces.
- Finish remaining actual evidence/knowledge consumers and scientific-owner paths called out
  by the full workflow map; descriptors and stored documents are not proof of consumption.
  Scientific mappings/lag/target/native-lineage decisions still need their explicit resolution.
- Finish Jev's CPU route after its outstanding runtime/model/allocation decisions; preserve
  blind claim sealing, scientific testing and truthful completion. Do not bypass a waiting Jev.
- Prepare the missing one-time inspection reports across the actual workflow, then follow the
  agreed E2E → one-day review → adjustments → three-day sequence.
- Historical rework is still required for **both teachers**. No historical run was executed.

## Newly available CCode return — fetched, NOT reviewed or integrated

`origin/ccode/teacher-tasks-20261006b` was fetched at **`954f3f3`**. It is based on `439cb0b`
and includes six commits, beginning `bc178ff`, for the CPU controller/launcher and retired-Pod
workflow closure. Read its `CCODE_STEP8_CPU_CONTROLLER_20261007.md` and return/handoff notes
directly from that branch before integration. The return touches eleven files, including:

- `research/kalshi/frankie_boss/pod_root/controller.py`
- `deploy/aws/box/frankie_box_cpu_controller.sh`
- `deploy/aws/box/frankie_box_pod_root_loop.sh`
- `.github/workflows/frankie_box_run.yml`

CCode owns these source boundaries. Review the returned changes; do not overwrite or duplicate
them, or mistake the fetched return for already integrated work. No merge was performed.

## Standing invariants

Exactly three held 16-CPU lanes (two main, one Linux), each 15 workers plus coordinator; no Pods.
Keep giant evidence on its owner. Reuse existing recovery/checkpoint writers and retained state.
All applicable knowledge must reach actual computation. Preserve full evidence, older and
unaffected lessons, unresolved conflicting accounts, causal availability and answer walls.
Dates/weekdays/IDs group underlying market conditions; they are not numerical signals/targets.
No trading-cost/profit objective, output pooling across runs, arbitrary truncation or replacement
weights. Memory A remains retired; H06–H08 remain historical/not_bound. Temporary review reports
must not become knowledge. Source checks remain source review, AST without imports and
`git diff --check`; do not add tests or a validator framework. `[skip ci]` on pushes.
