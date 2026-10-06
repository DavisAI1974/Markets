# HANDOFF 2026-10-06 — 30-day AWS workflow reconstruction

Branch: `chatgpt/frankie-30day-aws-workflow-20261006`
Tip at handoff creation: `1f63f76cf70c6e405e3eaebe958647a66526f74b`

## Mission

Finish the retained 30-day Frankie experiment as economically as possible on AWS without risking existing data/progress.
Do not redesign working machinery. Do not build a validator/canary/test framework. Wire the actual workflow, run ONE
real ROOT-to-finish end-to-end discovery day, fix actual failures, then feed the retained 30-day pipeline.

## Greg's settled operating rules

- Existing 30-day ingests/progress are evidence. Never casually re-ingest, delete, overwrite, detach or move them.
- Paid AWS boxes are execution engines, not development boxes. Settle/wire before starting compute.
- A day owns the SAME box + SAME 16-CPU lane + SAME worker allocation from ROOT to its last applicable stage.
- Existing CPU ledger is authoritative: 16 CPUs, normally 15 worker CPUs + 1 coordinator/ordered-consumer; no double booking.
- Frankie gets new legally available knowledge IMMEDIATELY after each knowledge-producing stage. End-of-day retention is
  consolidation, not the first learning event.
- No silent dropping, truncation, averaging, smoothing or normalization of retained evidence.
- One real E2E test only after wiring. Fix real failures; no validation project.

## Canonical day workflow

Source of truth: `research/kalshi/frankie_boss/SPEC-experiment-orchestrator.md`.

1. existing sealed ingest/receipt (fetch+ingest only if genuinely missing)
2. causal day file
3. ROOT -> immediate ROOT brain entry
4. BOSS teacher whole-journal read -> immediate teacher brain entry
5. classroom-arm days: Frankie classroom immediately after teacher -> immediate classroom brain entry
6. data export
7. causal series/search -> immediate search brain entry
8. scientific teacher tests carried/prior claims
9. scientific teacher tests today's Frankie findings -> immediate lessons brain entry
10. survivor/candidate update at cross-day/batch boundaries (not a per-day lane blocker)
11. three-way meeting
12. Frankie end-of-day school/report consolidation
13. Jev blind comparison; after Jev's own claims are sealed/tested, tested Jev knowledge may enter Frankie immediately
14. freeze discovery survivors once
15. untouched confirmation days only after freeze; confirmation findings enter brain but never change frozen list

Non-classroom discovery days: ROOT -> BOSS teacher -> data/search -> carried-claim scientific teacher; skip class/meeting/school/Jev.

## Granite — FINAL experiment role

Greg 2026-10-06 chose the ACTIVE facilitator plan.

- Granite 4.2 is the bounded coordinator/facilitator of the post-class three-seat discussion.
- It may ask clarification/follow-up questions, surface scope disagreements, keep open items/next tests organized, and
  request that a code seat run/name a test.
- It is NOT a fourth scientific seat and never calculates, grades, selects survivors, confirms claims, changes
  confirmation, forecasts or trades.
- Any requested calculation runs in the proper code stage and must return source-bound evidence before discussion continues.
- Useful discussion knowledge enters Frankie's brain immediately.
- Old B2 critic/self-assessment code remains historical/full-system code and is NOT part of this 30-day experiment.

Files:
- `research/kalshi/frankie_boss/knowledge/GRANITE_DISCUSSION_COORDINATOR_ROLE_V2.md`
- `research/kalshi/frankie_boss/knowledge/CLASSROOM_RULES_V3.json`

Hosting preference:
1. local if practical;
2. FREE standard GitHub public-repo CPU runner with IBM Granite 4.2 8B GGUF + llama.cpp if meeting latency is acceptable;
3. existing small AWS CPU box only while a meeting runs;
4. paid GPU fallback only.
No standing Granite GPU/Pod.

Official IBM Granite 4.2 8B GGUF exists and supports llama.cpp; Q4_K_M is suitable for a small coordinator runtime.
Do NOT restore the old 131k-context retained-vLLM/L40S machinery merely for this role.

## Important GitHub compute correction

The exact September-30 four-day ROOT setup did use GitHub Actions as the CONTROLLER, but not as the ROOT compute.
Workflow run `36656174396` shows the GitHub job dispatching:

`PODS=0o3wfhj6vxvqis,kj93q89dnpuhdp,tthwp8ztjxhqcw,s8u7611dxa5i24`

Those were four A100 RunPod ROOT workers. So the four simultaneous ROOT days came from four Pods; GitHub orchestrated them.

Current GitHub facts (checked 2026-10-06):
- standard public-repo GitHub-hosted Linux runner: 4 vCPU / 16 GB / 14 GB SSD, free and unlimited;
- GPU larger runner: Tesla T4 16 GB VRAM, 4 CPU / 28 GB RAM / 176 GB SSD;
- GPU larger runners are PAID even for public repos: Linux $0.052/min = $3.12/hour;
- larger runners require GitHub Team/Enterprise organization access.
Thus free GitHub CPU remains useful for orchestration/light independent work and possibly quantized Granite coordinator,
but it is NOT a free 16-core ROOT lane and GitHub GPU is not an economic ROOT/Granite default.

## Current AWS compute facts

All currently stopped:
- main `i-035994afa8bdf66a5`, us-east-1d, r7i.8xlarge = 32 vCPU = TWO 16-core lanes; protected 2 TiB root EBS.
- replacement Linux worker `i-0d17573dbce871520`, us-east-1d, r7i.4xlarge = 16 vCPU = ONE 16-core lane.
  AWS tag: `frankie-linux-worker, replaces Windows i-0e90ee6110ef609aa (Greg 2026-09-29)`.
- `i-08cee7171c0a76a04`, us-east-2b, r6i.2xlarge = 8 vCPU / 64 GiB; existing small box.
  Current on-demand price checked: $0.504/hour.

Therefore preserved AWS boxes currently provide THREE full 16-core day lanes. A fourth lane is still unresolved.

Do not infer a fourth lane from GitHub standard runners. Options for next chat:
- temporarily add/resize a 16-core AWS worker after measuring exact data/disk placement cost;
- inspect whether the replacement worker can economically become 32 vCPU and hold two complete day lanes;
- Spot only if the remote full-day lane is truly restart-safe and state transfer is safe.

## AWS performance findings

Main 2 TiB gp3 volume is NOT overprovisioned for active crunch:
- observed ~1,007 MiB/s peak in 5-min windows;
- observed ~11,026 IOPS.
Do not lower EBS performance during the crunch.

Main r7i.8xlarge CPU:
- low overall average due idle phases, but active 5-min p95 ~81% of all 32 vCPUs; p99 ~98%.
Do not blindly downsize the active crunch box.

Potential Spot rate observed earlier in us-east-1d:
- r7i.8xlarge ~ $0.5664/h vs $2.1168/h on-demand.
Do NOT convert/move the protected stateful root volume to Spot mid-run. Spot remains future/restartable worker option.

## Code already reused / no rebuild

Existing:
- `frankie_box_cores.py` CPU booking ledger + taskset affinity
- 16-core day slots / 15-worker rule
- FIFO ROOT/class queues
- root claims
- receipt/resume state
- held day slot on main from ROOT through finish
- worker box setup/SSM path
- ROOT, BOSS teacher, classroom, data export, first-slice search, scientific teacher, exchange, school/reports, Jev relay

## Changes made on this branch

1. Canonical workflow rewritten in spec/runbook; stale September tables demoted to provenance.
2. Main traffic controller reordered classroom-arm days:
   ROOT -> BOSS teacher -> classroom -> data/search -> scientific teacher -> exchange/end.
3. Immediate brain rule added.
4. `frankie_box_brain.py` gained stage knowledge entries for ingest/day-file/ROOT/teacher/search/tested-Jev and future
   survivors/confirmation, using inline small sources or digest-bound pointers to retained large sources.
5. ROOT now always emits digest needed for immediate brain knowledge.
6. Experiment orchestrator now commits ingest/day-file/ROOT/teacher/search knowledge before advancing.
7. Tested Jev results can enter Frankie after Jev's own blind claims are fixed/tested.
8. Granite coordinator role V2 + classroom rules V3 created; classroom code now loads V3.

No AWS boxes were started and no result-bearing market-data run was launched during this work.

## Remaining build work — keep narrow

1. Remote Linux worker is still ROOT-only. Change it to use the SAME root-to-finish day runner and keep the day/16-core
   lane until completion. Do not create a parallel orchestration architecture.
2. Shared cross-box state: move/sync only small coordination/knowledge state; do not bounce giant day artifacts unless
   required. Central ownership/claims remain authoritative.
3. Full search surface is incomplete. Current search explicitly leaves retained per-event fields / more transforms /
   conditions / targets unsearched. Complete this because retained evidence must reach computation.
4. Survivors/freeze is not fully built.
5. Confirmation path is not fully built.
6. Granite active facilitator transport/follow-up loop is not wired yet. Build only the small role above, not old critic infrastructure.
7. Decide fourth 16-core lane economics/data placement.
8. When all wiring is complete: ONE real ROOT-to-finish E2E on an already-ingested discovery day. Fix failures as found.
9. Then run retained 30-day pipeline.

## Cost posture

No AWS Batch/EKS/SageMaker migration. No Savings Plan/RI commitment. No standing GPU.
Start expensive boxes only when the run is ready; stop promptly when useful crunching is over.

GitHub paid larger runners are not the cheap lane:
- 16-core Linux larger runner: $0.042/min = $2.52/h.
- 4-core T4 GPU runner: $0.052/min = $3.12/h.
Existing AWS/on-demand or eventual Spot is cheaper for 16-core day compute.

## Do NOT do next

- Do not run the 30-day experiment yet.
- Do not build validators/canaries/test frameworks.
- Do not re-ingest finished days.
- Do not prune snapshots/EBS/progress.
- Do not resurrect old Granite critic/131k/L40S machinery for the coordinator role.
- Do not assume GitHub standard runners supplied the old four ROOT compute lanes.
