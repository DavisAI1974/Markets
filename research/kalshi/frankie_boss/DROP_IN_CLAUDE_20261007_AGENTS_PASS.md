# Drop-in for the next session: the agents' pass of 2026-10-07 (Greg)

## Drop-in box (paste into the new session)

```
NEW SESSION -- Frankie (Greg, 2026-10-07 evening: THE AGENTS ARE THE ONLY WAY WORK RUNS)
1. Start ON branch ccr-d2f8f826-iefeah-frankie (tip c838c7b3 or newer):
   git fetch origin ccr-d2f8f826-iefeah-frankie && git checkout -B ccr-d2f8f826-iefeah-frankie origin/ccr-d2f8f826-iefeah-frankie
   Also fetch ccode/teacher-tasks-20261006b-step8-corrections (5f111885 over CCode's 8f242402).
2. Verify tools: the Agent tool lists the 7 frankie-* and 3 aws-* agents; the Aws connector
   (Greg's, read AND write, binds at session start) answers sts GetCallerIdentity; the project
   aws-mcp resolves retrieve_skill('aws-compute').
3. Read research/kalshi/frankie_boss/DROP_IN_CLAUDE_20261007_AGENTS_PASS.md (this file), then
   WORKFLOW_COVERAGE_PLAN_20261007.md (the plan and Greg's decisions).
4. The session is the parent only: it relays Greg's go, assigns roles, commits returns, never
   does a role's work. Every role starts with api-and-interface-design and uses the AWS skills.
5. Run the open list below in order, on Greg's go. No E2E, dispatch, model/data run or install
   without his explicit go. Greg is low on weekly usage: no re-passes, no duplicate agents.
```

## Where everything is
| Branch | Tip | Holds |
|---|---|---|
| `ccr-d2f8f826-iefeah-frankie` (work) | `c838c7b3` | integration `d6af990` + codex checkpoint `fd42dfd` + today's returns + WIP checkpoints |
| `ccode/teacher-tasks-20261006b-step8-corrections` | `5f111885` | CCode's `8f242402` + both reviewers' Step 8 corrections (`9cd1e2aa`) + the Step 8 restart pass |
| `ccr-5fce7de3-xa4hfg` (integration) | `d6af990` | published reviewed source; nothing from today is integrated |
| `ccode/teacher-tasks-20261006b` | `8f242402` | CCode's return, history untouched |

Everything from today is SOURCE-BUILT / RUNTIME-UNVERIFIED and UNREVIEWED. Nothing ran. No account
call succeeded (the connector bound before Greg reconnected it; the container has no credentials).

## What landed today (returned by its agent, committed by the parent)
- Agents: `.claude/agents/` ten roles with one shared block (API skill first, AWS read and write,
  efficiency and data-processing skills, one-day inspection reports, missing-coverage rule).
- Step 8 (corrections branch): the two reviewers found CCode's return BLOCKED and fixed it (Jev
  status collision, lease release without ownership, retained jobs with expired URLs, save ack not
  binding CPUs/source, missing day-file witness refused; hot close_day loop, integrity relabelled
  waiting, numbering SystemExit). The restart pass: finish states finished/waiting/failed, the
  one-day reporter after a day's last step, close_day drains once, one meeting child per decision,
  remote admission both sides (voice_route local|github), REBOOK'd Jev chain, stages 0-3 verified.
- Work branch: core missing-coverage correction (iter_applied refuses nothing; complete = exhaustion;
  coverage per picture and per day; absent layers list; the ROOT spool pin KeyError fixed); classroom
  correction (identity refuses, coverage lists; received/outputs pins; phase timings; two hot-path
  fixes); adviser bridge (AdviserMarketContext rewritten for the rule, Jev/sit_in/exchange/Granite
  transport, workflow_report fields); lane_state kick scoped (needs the Step 8 queue's scope kwarg);
  Codex's reporter extended with --write (one md per piece + index.md) and projections.

## UNFINISHED on the work branch (agents stopped before returning; reconcile first)
WIP checkpoints `ec1b6420`..`85173aee` hold partial, unreturned edits from the stage pass:
`frankie_box_experiment_teacher.py` (+169), `frankie_box_experiment_data.py` (+93) and `.sh`,
`frankie_box_experiment_day_reports.sh`, `frankie_principal_adapter.py` (+44),
`frankie_box_market_timeline.py` (+35), `frankie_box_workflow_inspection.py`. Their owners
(workflow-reports for teacher/data/timeline, correction-consumer for day_reports/principal_adapter)
must read `git diff 6c10e6e4..c838c7b3 -- <file>`, finish or revert each hunk, and return. The
stage 8/9/10 agent wrote nothing. AST and diff check pass on every checkpoint.

## Open list, in order (the next session's agents)
1. Reconcile the unfinished hunks above (their owners), then merge
   `ccode/teacher-tasks-20261006b-step8-corrections` into the work branch (the lane_state kick needs it).
2. Independent review of everything on both branches: frankie-ccode-review and frankie-school-recovery
   cross-review what they did not author; APPROVED/BLOCKED with file:line; fix; then integrate to
   `ccr-5fce7de3-xa4hfg`.
3. Stage 10 survivor/candidate update: NOT built (frankie-school-recovery; design in the plan's prompt
   history: cross-day batch boundary, consumption only by later classrooms, no averaging).
4. frankie-remaining-consumers: the token stacks on the adviser picture text (reading_render,
   stacked_text, digest_render; byte-exact parse-back; canary measurement); the whole picture into
   Granite's meeting input (Greg: unless the per-call cap refuses); Granite local route as the default
   with the runtime gate naming what the box needs installed.
5. Stages 4/6/7 and 12 passes (review, plan, implement) finished by their owners.
6. Account work with the live connector (frankie-ccode-step8, on Greg's go): the 8A items (inline
   least-privilege policy on the main box's `Ssm` role; worker box `i-0d17573dbce871520` setup via
   SSM; systemd-run/venv check on the main box; SSM status of both boxes), and installing the pinned
   Granite 4.2 3B Q4_K_M + llama.cpp b11440 on the box for the local meeting route.
7. Greg supplies the Jev runtime pins (JEV_CPU_RUNTIME_V1). Then, on his go: the authorized E2E,
   ONE day configured exactly as the THREE days (per-piece inspection md under
   `<run-dir>/days/<day>/inspection/`), review with Greg and Frankie, THREE days.

Standing requests to Codex-owned code that nobody fixed: `pod_agent.run_full_day` should read
`facts['finish']=='waiting'`; `frankie_box_jev_cpu.execute` should accept the rebook successor chain.
