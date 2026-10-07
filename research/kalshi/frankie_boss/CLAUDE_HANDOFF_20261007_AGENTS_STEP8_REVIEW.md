# Claude handoff: AWS MCP, agents, and the Step 8 agent review (2026-10-07)

Session `session_01RXFR8bwkmbcs3qnHquGbXz`. Configuration and agent definitions only. Nothing ran: no
agent, no test, no AWS account call, no dispatch, no data/model/scientific run. HOLD stands.

## Drop-in box (paste into the new session)

```
NEW SESSION -- Frankie Step 8 agent review (Greg, 2026-10-07: "We'll have the agents go over step 8")
1. Start ON branch ccr-d2f8f826-iefeah-frankie (tip 457a73f7 or newer, plus this handoff's
   commit). It carries the aws-mcp server, the agent-skills plugin and the 9 agents.
   git fetch origin ccr-d2f8f826-iefeah-frankie && git checkout -B ccr-d2f8f826-iefeah-frankie origin/ccr-d2f8f826-iefeah-frankie
2. Verify tools: /mcp shows aws-mcp (read-only: search/read docs, retrieve_skill, regions,
   tasks); the Agent tool lists frankie-ccode-review, frankie-school-recovery and the rest.
   If either is missing, stop and fix config first. Do NOT run agents on a broken toolset.
3. Read research/kalshi/frankie_boss/CLAUDE_HANDOFF_20261007_AGENTS_STEP8_REVIEW.md (this file).
4. Fetch ccode/teacher-tasks-20261006b. Its tip was 8f242402 (seventh review pass). If newer
   commits landed in the last hour, another CCode session may be live: coordinate, never collide.
5. Spawn IN PARALLEL, read-only: frankie-ccode-review (the whole Step 8 diff) and
   frankie-school-recovery (the school/waiting_school slice). The prompt states Greg's request.
6. Fix confirmed findings on ccode/teacher-tasks-20261006b (CCode-owned files only), source
   checks only, then a FRESH re-review. Push with [skip ci]. Never rewrite history.
Source-only. No tests, installs, AWS inspection/actions, dispatch or E2E. HOLD.
```

## Branches at close

| Branch | Tip | What it is |
|---|---|---|
| `ccr-d2f8f826-iefeah-frankie` | this handoff's commit, over `457a73f7` | WORK BRANCH: capture `fd42dfd3` + aws-mcp + 9 agents + agent-skills plugin + this handoff |
| `ccode/teacher-tasks-20261006b` | `8f242402` | CCode Step 8 remainder return, rebased on `d6af990`; awaiting independent review |
| `ccr-5fce7de3-xa4hfg` | `d6af990c` | Codex integration (published, reviewed source) |
| `codex/stopped-wip-20261007` | `fd42dfd3` | stopped adviser WIP + the missing-coverage rule docs |
| `claude/kalshi-s79-kickoff-ij8t9o` | `fe6dbf58` | repo default/trunk: aws-mcp + agent-skills plugin + the 3 AWS agents |
| `ccr-d2f8f826-iefeah` | `e4266dc5` | OBSOLETE. Delete was refused by the session git proxy; Greg deletes it in the GitHub UI. Everything on it lives on the two branches above. |

## What this session built

1. **AWS managed MCP** (`https://aws-mcp.us-east-1.api.aws/mcp` through `uvx mcp-proxy-for-aws-cli@1.7.0`,
   `--metadata AWS_REGION=us-east-2`, `--read-only`), registered in `.mcp.json` on the trunk (Greg's `e5c43a7`) and
   now on the Frankie work branch (`ef2f72fe`). Probed directly: read-only exposes `search_documentation`,
   `read_documentation`, `retrieve_skill`, `list_regions`, `get_regional_availability`, `get_tasks`. Without
   `--read-only` it adds `run_script` (destructive hint) and `get_presigned_url`. Read-only was kept because the
   Frankie line forbids AWS inspection/actions; switching is Greg's call and a one-line change.
2. **Agent-skills plugin** (addyosmani/agent-skills 0.6.8) enabled on the Frankie work branch (`457a73f7`), copied
   from the trunk's settings, so the agents' Skill tool finds `api-and-interface-design`, `incremental-implementation`,
   `code-review-and-quality`, `doubt-driven-development`, `debugging-and-error-recovery`, `context-engineering`.
3. **Agents** (`.claude/agents/`, `3a754ec4`), each with the Skill tool plus the aws-mcp tools:
   - Frankie roles from `CCODE_STOPPED_AGENTS_HANDOFF_20261007.md`: `frankie-remaining-consumers` (adviser bridge
     author), `frankie-workflow-reports` (timeline core author), `frankie-main-recovery` (classroom author),
     `frankie-correction-consumer` (944c354 follow-ups), `frankie-ccode-review` and `frankie-school-recovery`
     (read-only reviewers). The documentation role was dropped: Chat already did the doc refresh.
   - AWS: `aws-skills-guide`, `aws-infra-reviewer`, `aws-operator` (read-only inspection). Also on the trunk.
   - Every Frankie agent carries: a resumption gate (works only when the parent's prompt states Greg asked for that
     role), its disjoint file ownership, the missing-coverage rule, the source-only boundary, return-never-publish
     (no commit/push), one bounded AWS lookup per need.

## Step 8: what the agents review

CCode's Step 8 remainder return: `research/kalshi/frankie_boss/CCODE_STEP8_REMAINDER_RETURN_20261007.md` on
`ccode/teacher-tasks-20261006b`. Assignment: `CCODE_STEP8_REMAINDER_ASSIGNMENT_20261007.md` (section 4 and its
02:35 ET addendum) and `CCODE_HANDOFF_STEP8_REMAINDER_20261007.md`. The return asks for Codex's independent review
before integration; that review is this job.

Scope: `git diff d6af990..origin/ccode/teacher-tasks-20261006b` over 10 code files (+2,786/-591):
`pod_root/controller.py`, `frankie_box_frankie_queue.py`/`.sh`, `frankie_box_experiment.py`/`.sh`,
`frankie_box_cores.py`, `frankie_box_cpu_controller.sh`, `frankie_box_pod_root_loop.sh`,
`frankie_box_successor_dispatch.py` (the `waiting_school` branch only), `.github/workflows/frankie_box_run.yml`.

Commits (from the return): 8A `40cbc1d0` `57d619f2` `c134e0db` `a3603af9` `6bad3d22` `373f58ed`; 8A findings
`456a006a`; save/resume owner contract `23e3afae`; scoped dispatch `4272f949`; small integrations `8af0a0b8`; review
passes `d8ec096b` `2634e5ee` `157c84ff` `83081b64`; addendum callers `bfae4460`; class ack `b4c60a4d`; addendum review
`df51afb0`; shared-market policy `cf1f1f2c`; policy reviews `24df7810` `35718474`; docs `f1cbce25` `8f242402`.

Suggested split (both read-only, in parallel):
- **frankie-ccode-review**: the whole diff against its 8A checklist (lease freshness at every effect boundary;
  uncertain resume stays unknown; unsuccessful outcomes exit nonzero; saved ack binds owner/attempt/source/CPU/
  marker/generation; saved never requeued as failure; run/day/plan scope incl. the running fast path; exact
  predecessor/teacher/school/report pins; shared policy only on explicitly selected NEW requests, old saved
  requests never mutated) PLUS the missing-coverage rule in caller admission: incomplete layer coverage must not
  reject a timeline/day. Check the return's own choices against it: "a day whose ROOT or ingest is not complete
  waits instead of being refused", `Run.day_rows` refusals, `shared_teacher_compatible` three-way.
- **frankie-school-recovery**: the school consumer on the checked chain (`retained_school`), `waiting_school`
  recovery and its non-reentrance (`df51afb0` critical fixes), `successor_dispatch.drain`, reports currentness
  (`reports_school_stale`), against its own `91f3766`/`2c332df` contracts.

Spawn prompt must say: Greg requested on 2026-10-07 that the agents review Step 8; read-only; review the CCode tip
(verify it first); report findings ranked with file:line and a concrete failure path; end with APPROVED or BLOCKED.
Reviewers can read the CCode code with `git show origin/ccode/teacher-tasks-20261006b:<path>` or a scratchpad
worktree; they never edit.

Known open items the return already names (NOT review findings, do not "fix" by invention): the `Run.voice` remote
admission acknowledgment interface; Jev runtime configuration (`JEV_CPU_RUNTIME_V1`); REBOOK'd Jev requests; Codex's
`frankie_box_lane_state.py:619` unscoped kick (a request to Codex); the 8A dependencies (instance profile, signing
window, claim store, worker box, systemd-run/venv).

## Still open after Step 8 (do not start without Greg)

- The stopped adviser/core/classroom work and the missing-coverage correction across consumers
  (`frankie-workflow-reports` core first, then `frankie-main-recovery` and `frankie-remaining-consumers`, then the
  reviewers). Not implemented; the published core and the WIP draft are NOT compliant yet.
- Whether aws-mcp should drop `--read-only` (adds `run_script`, which can change the account).

## Notes for the next session

- The auto-mode safety classifier blocked three actions this session: writing a resumption claim into agent files
  together with settings changes (labelled "Instruction Poisoning" by the classifier itself, not by Greg), a force
  push over `ccr-d2f8f826-iefeah`, and the remote branch delete (refused by the git proxy). None was worked around.
- MCP servers and agents load only at session start; a config change needs a new session.
- The session start hook on this line reports no AWS credentials for the data plane; the aws-mcp proxy uses the
  container's own AWS identity and connected anyway. No credential was written anywhere.
