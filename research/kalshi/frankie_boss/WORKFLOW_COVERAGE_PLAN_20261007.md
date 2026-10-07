# Workflow coverage plan: the agents go over every stage (Greg, 2026-10-07)

Greg: "we are going to have to have these agents go over the entire workflow steps just like they did
earlier in codex. get a plan together and then implement." This is the plan. It follows the Codex
instruction in `CODEX_HANDOFF_20261007_WORKFLOW_CONTINUATION.md`: map the actual producers, consumers
and substeps of `SPEC-experiment-orchestrator.md` section 0, reconcile the map against the current code
and completed reports, then work the remaining pieces with separate agents, explicit file ownership and
integration review. Source-only until Greg's E2E go. Nothing here is runtime evidence.

## Branches
- Work branch: `ccr-d2f8f826-iefeah-frankie` (integration `d6af990` + codex checkpoint `fd42dfd` + the
  2026-10-07 returns: core, classroom, adviser, lane_state kick, agents).
- Step 8 corrections: `ccode/teacher-tasks-20261006b-step8-corrections` over CCode's `8f242402`
  (worktree `scratchpad/step8-wt`). Merged into the work branch after its Phase 2 returns.
- Integration target after review: `ccr-5fce7de3-xa4hfg`.

## Phase A: the map (read-only, fast)
`frankie-ccode-review` builds `WORKFLOW_COVERAGE_MAP_20261007.md`: for each stage 0-15 of section 0
(and the conditional/cross-day substeps) the producer modules and entry points, the receipts and
pins, the consumers, what is built, wired, waiting or absent, with file:line on the current code,
and the gaps against the spec row and the standing rules. No edits.

## Phase B: every stage worked, disjoint ownership
Each owner: review the stage's code against its spec row and the standing rules (missing-coverage;
no same-day circular teaching; Jev blind; the lane rule; single-occurrence equal treatment; new
discovery central; immediate brain commits; no Pods), fix defects in owned files, build what the row
says is not built, carry the one-day inspection report fields, name cross-owner requests precisely.

| Stages | Owner | Files (owned) | When |
|---|---|---|---|
| 0 preflight, 1 ingest, 2 day file, 3 ROOT lane, lane/traffic-controller rule, remote worker ROOT-to-finish | frankie-ccode-step8 | experiment.py (Run), frankie_queue, cores, cpu_controller, pod_root controller/worker agent, run.yml | after Phase 2 and the Step 8 merge |
| 4 BOSS teacher read, 6 data export, 7 causal series + search (incl. symbolic discovery) | frankie-workflow-reports | experiment_teacher, experiment_data, experiment_search, market_timeline, journal/native bridges | now |
| 5 Frankie classroom | frankie-main-recovery | classroom_reader, classroom_code, experiment_classroom_v2, classroom_staged | now |
| 8 carried claims, 9 today's findings, 10 survivor/candidate update (NOT fully built), 14 corrections (successor side) | frankie-school-recovery | scientific_teacher, experiment_review, survivor/candidate code, school_knowledge; successor_dispatch after the Step 8 merge | now (10 first) |
| 12 end of day: school consolidation and numbered reports | frankie-correction-consumer | experiment_day_reports, the school file writer, correction consumption | now |
| 11 three-way meeting (Granite coordinator, voice transport), 13 Jev blind comparison, Jev sit-in | frankie-remaining-consumers | adviser_market, jev_cpu, sit_in, experiment_exchange, granite_meeting | after its stacks pass |
| 15 separate confirmation | nobody: not selected, map only | | |

## Phase C: review and integration
`frankie-ccode-review` and `frankie-school-recovery` review each slice they did not author
(APPROVED/BLOCKED with file:line). The parent commits approved slices to the work branch, then merges
to integration. Then, on Greg's go in a session with the live AWS connector: the 8A account steps,
the authorized E2E, ONE day with the per-piece inspection reports, review with Greg and Frankie,
THREE days. Thirty days is a separate decision. Jev runtime pins and the Granite picture-body call
wait on Greg.

## Decisions from Greg during this pass (2026-10-07)
- The ONE-day run is configured exactly as the THREE-day run will be: same lanes, same routes, no
  local shortcuts. The Jev runtime pins and the Granite hosting are settled before day 1.
- Optimize as much as the science allows before the one-day run; it is a check that the workflow
  runs the way Greg wants, not a benchmark. Keep the instrumentation so it shows where time went.
- Day 1 must surface every problem: nothing in any piece goes wrong quietly; every skip, wait,
  refusal, fallback, cap, retry, missing or stale input, swallowed exception and default taken
  lands on the receipt and in the piece's inspection markdown with its reason.
- Granite sees the whole shared market picture unless there is a good reason; the only accepted
  reason is the per-call token cap, which refuses visibly.
- Granite hosting: AWS, uniform with the lanes (the spec's "local if practical"): the meeting runs
  as a child on the owning box, CPU only, pinned Granite 4.2 3B Q4_K_M under llama.cpp b11440;
  plan `voice_route=local`. The GitHub route stays in the code as the listed fallback, unused.
  Installing the pinned binary and model on the box is a day-1 setup step for the next session
  with the live connector, on Greg's go.
