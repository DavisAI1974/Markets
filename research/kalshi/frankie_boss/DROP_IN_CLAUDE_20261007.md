# DROP-IN (Claude): the CCode pre-#5 queue after Codex's correction queue was returned (2026-10-07, end of the third session)

Current box (2026-10-07, after the eighth session: the Step 8 remainder returned). The earlier boxes below are kept for their reading order and boundaries.

```
CCode queue, CLAUDE session, 2026-10-07. The Step 8 REMAINDER is RETURNED on Codex's 7f08d76e: 456a006a 8A findings |
23e3afae owner contract | 4272f949 scope | 8af0a0b8 previous_of + producer identity | d8ec096b 2634e5ee 157c84ff 83081b64
review passes | bfae4460 school consumer + waiting_school recovery + Jev CPU caller | b4c60a4d ack identity + kick scope |
df51afb0 review pass | the docs commit = tip. HOLD stands.
FIRST, in this order:
1. /run using-agent-skills (the Skill tool). Greg's rules and the boundaries below win where they differ from a skill.
2. Branch (the harness branch is never the work). Exactly:
     git fetch origin ccode/teacher-tasks-20261006b ccr-5fce7de3-xa4hfg
     git checkout -B ccode/teacher-tasks-20261006b origin/ccode/teacher-tasks-20261006b
     git rebase origin/ccr-5fce7de3-xa4hfg && git log --oneline -20
   If Codex edited an owned file (frankie_box_experiment.py/.sh, frankie_box_frankie_queue.py/.sh, frankie_box_cores.py,
   pod_root/controller.py, frankie_box_cpu_controller.sh, frankie_box_run.yml, the drain branch of
   frankie_box_successor_dispatch.py), read its diff before touching that file.
3. #run memory mcp BEFORE any code change (Greg): CLI, after the rebase, tree quiescent (it aborts if files change):
     echo '{"repo_path":"/home/user/Markets","mode":"full"}' | codebase-memory-mcp cli --quiet --json index_repository
READ, in order (research/kalshi/frankie_boss/):
   CCODE_STEP8_REMAINDER_RETURN_20261007.md              the record: protocol (2), scope (3), callers (4), NOT wired (5), review (7)
   CLAUDE_HANDOFF_20261007_CCODE_SLICES_A_D.md (top)     the Claude-side state, design choices not to re-litigate
   CCODE_NEXT_SOURCE_TASKS_20261006.md (top section)     Codex's independent review of the return lands HERE
BOUNDARIES: source/interface review, ast.parse without project imports, sh -n, yaml.safe_load, git diff --check ONLY. No
tests, runs, installs, model calls, AWS, dispatch, canaries, E2E; boxes stopped. Owned: frankie_box_experiment.py/.sh,
frankie_box_frankie_queue.py/.sh, frankie_box_cores.py, pod_root/controller.py, frankie_box_cpu_controller.sh, the
controller routing and Pod gates of frankie_box_run.yml, frankie_box_pod_root_loop.sh, and ONLY the waiting_school branch
of successor_dispatch.drain. Never edit Codex's files (school owner, experiment review, the rest of the successor
dispatcher, principal adapter, BOSS session, scientific teacher, teacher knowledge, search/native/journal readers,
lane_state, Jev's helper, shared assignment/handoff docs) or the unowned box side (frankie_box_pod_root.sh/.py,
pod_agent.py): return exact interface requests. Never call frankie_box_historical_reproduction.run(); never rebuild the
claims file. Granite pins/threads null settled. STOP before #5; never apply 9c19cc2. H06-H08 historical, bind nothing.
NO cost references, ever.
NEXT: (1) fix what Codex's review names, one [skip ci] commit per finding group; (2) wire the shared-market ROOT policy
(Run.root/plan) and the remote voice admission (Run.voice) ONLY once their producer contracts are on Codex's tip (return
section 5 names what to look for); (3) run the code-review skill over origin/ccr-5fce7de3-xa4hfg..HEAD at high effort
BEFORE every push and fix what it finds. Update the return record, both handoffs (Claude + CCODE) and both drop-ins; push
--force-with-lease -u; report exact tips. Nothing on the scratchpad.
```


Current box (2026-10-07, after the seventh session: Step 8A returned). The earlier boxes below are kept for their reading order and boundaries.

```
CCode queue, CLAUDE session, 2026-10-07. Step 8A (the CPU controller's lifetime and launch routing) is RETURNED on Codex's
439cb0bf (assigned in 3a1416b7): bc178ff3 lifetime/prerequisites/controls | bd28796e Pod routes closed | bdf7122b cdeb61ce two code-review passes |
the docs commit = tip. HOLD stands. Greg: do not mess with old work; Step 8A only.
FIRST, in this order:
1. /run using-agent-skills (the Skill tool). Greg's rules and the boundaries below win where they differ from a skill.
2. Branch (the harness branch is never the work). Exactly:
     git fetch origin ccode/teacher-tasks-20261006b ccr-5fce7de3-xa4hfg
     git checkout -B ccode/teacher-tasks-20261006b origin/ccode/teacher-tasks-20261006b
     git rebase origin/ccr-5fce7de3-xa4hfg && git log --oneline -10
   If Codex edited pod_root/controller.py, frankie_box_run.yml, frankie_box_cpu_controller.sh or frankie_box_pod_root_loop.sh,
   read its diff before touching that file.
3. #run memory mcp BEFORE any code change (Greg): CLI, after the rebase, tree quiescent (it aborts if files change):
     echo '{"repo_path":"/home/user/Markets","mode":"full"}' | codebase-memory-mcp cli --quiet --json index_repository
READ, in order (research/kalshi/frankie_boss/):
   CCODE_STEP8_CPU_CONTROLLER_20261007.md                the 8A record: action map, ownership, dependencies, requests, review
   CLAUDE_HANDOFF_20261007_CCODE_SLICES_A_D.md (top)     the Claude-side state, design choices not to re-litigate
   CCODE_NEXT_SOURCE_TASKS_20261006.md (top section)     Codex's review of the five commits lands HERE
BOUNDARIES: source/interface review, ast.parse without project imports, the static import check, sh -n, git diff --check
ONLY. No tests, runs, installs, model calls, AWS, dispatch, canaries, E2E; boxes stopped. Owned: pod_root/controller.py, the
controller routing and Pod gates of frankie_box_run.yml, frankie_box_pod_root_loop.sh, frankie_box_cpu_controller.sh. Never
edit Codex's files (experiment runner, frankie_queue, lane_state, brain, review, search, dipole, clm_sidecar, Jev, the step-5
reader hooks, shared assignment/handoff docs) or the unowned box side (frankie_box_pod_root.sh/.py, pod_agent.py): return
exact interface requests. Never call frankie_box_historical_reproduction.run(); never rebuild the claims file. Granite
pins/threads null settled. STOP before #5; never apply 9c19cc2. H06-H08 historical, bind nothing. NO cost references, ever.
NEXT: (1) fix what Codex's review names, one [skip ci] commit per finding group; (2) run the code-review skill over
origin/ccr-5fce7de3-xa4hfg..HEAD at high effort BEFORE every push and fix what it finds; (3) nothing else is assigned: the
main lanes' save/resume, Jev, the reader hooks and scheduling are Codex's; the instance profile is Greg's decision. Update
the step-8 record, the step-6 return section 10, both handoffs (Claude + CCODE) and both drop-ins; push --force-with-lease -u;
report exact tips. Nothing on the scratchpad.
```

Paste this box into the new Claude Code session. It is separate from the Codex-facing `CCODE_DROP_IN_20261006_NEXT_CHAT.md`.

```
CCode queue, CLAUDE session, 2026-10-07. Codex's fifth-return review (BIND-F 12258b3b, B4-F 7dd8b9a4, 6R3-F 34dab141,
6R2-F 4b5a8eba) plus two adversarial code-review passes (62eb55e3, 6c804bd2) are RETURNED on Codex's 5e216265; docs 889120af.
Codex's integration tip has since moved to c816bc56 (step seven): rebase onto it first. HOLD stands.
FIRST, in this order:
1. /run using-agent-skills (the Skill tool). Greg's rules and the boundaries below win where they differ from a skill.
2. Branch (the harness branch is never the work). Exactly:
     git fetch origin ccode/teacher-tasks-20261006b ccr-5fce7de3-xa4hfg
     git checkout -B ccode/teacher-tasks-20261006b origin/ccode/teacher-tasks-20261006b
     git rebase origin/ccr-5fce7de3-xa4hfg && git log --oneline -10
   The tip must be the handoff commit above 889120af or later. If Codex edited frankie_box_granite_meeting.py /
   frankie_box_scientific_teacher.py / frankie_box_historical_reproduction.py / frankie_box_experiment_exchange.py, read
   its diff before touching that module.
3. #run memory mcp BEFORE any code change (Greg): CLI, after the rebase, tree quiescent (it aborts if files change):
     echo '{"repo_path":"/home/user/Markets","mode":"full"}' | codebase-memory-mcp cli --quiet --json index_repository
     echo '{"project":"home-user-Markets","query":"<symbol>","limit":5}' | codebase-memory-mcp cli --quiet --json search_graph
   The session-start warning that the NG data plane is not restored is expected: nothing here needs data/ or S3.
READ, in order (research/kalshi/frankie_boss/):
   CCODE_STEP6_RETURN_20261007.md section 9 then 8       what was returned this round and the two review passes
   CLAUDE_HANDOFF_20261007_CCODE_SLICES_A_D.md (top)     the Claude-side state, design choices not to re-litigate
   CCODE_NEXT_SOURCE_TASKS_20261006.md (top section)     Codex's next review lands HERE
   CCODE_STEP4_SOURCE_ROUTE_20261006.md sections 8-9     historical-side detail and the closure table
GREG (2026-10-07, twice): NO reference to transaction costs in market-conditions work, period; never reintroduce one.
BOUNDARIES: source/interface review, ast.parse without project imports, the static import check, git diff --check ONLY.
No tests, runs, installs, model calls, AWS, dispatch, canaries, E2E. Never edit Codex's files (dipole, search, brain,
lane_state, experiment runner, frankie_queue, experiment_review, the step-5 reader hooks, shared assignment/handoff docs):
return exact interface requests. Never call frankie_box_historical_reproduction.run(); never rebuild the claims file.
Granite pins/threads null settled. STOP before #5; never apply 9c19cc2. H06-H08 historical, bind nothing.
NEXT: (1) fix what Codex's review names, one [skip ci] commit per finding group; (2) run the code-review skill over
origin/ccr-5fce7de3-xa4hfg..HEAD at high effort BEFORE every push and fix what it finds; (3) nothing else is assigned:
do not open or invent a slice; weight learning stays Greg's decision. Update the step-6 return, step-4 report 8/9, both
handoffs (Claude + CCODE) and both drop-ins; push --force-with-lease -u; report exact tips. Nothing on the scratchpad.
```
