# DROP-IN (Claude): the CCode pre-#5 queue after Codex's correction queue was returned (2026-10-07, end of the third session)

Paste this box into the new Claude Code session. It is separate from the Codex-facing `CCODE_DROP_IN_20261006_NEXT_CHAT.md`.

```
CCode queue, CLAUDE session, 2026-10-07. Codex's review round on step 6 (6R1-6R3) and the follow-ups (B2-R, B4-R, BIND-R)
is RETURNED (588c9c7f 1d9a1cbf d52237d3 6837875a bf8f87a5 0cb6868b + docs); this session picks up Codex's next review.
HOLD stands. Read CCODE_STEP6_RETURN_20261007.md section 8. The step-5 reader hooks are CODEX's (Greg 22:46 ET): never build them.
FIRST, in this order:
1. /run using-agent-skills (the Skill tool). Greg's rules and the boundaries below win where they differ from a skill.
2. #run memory mcp BEFORE any code change (Greg): the MCP call times out at 60 s; run the CLI (minutes; background it; it
   ABORTS if files change while it runs, so fetch/rebase first, then index, then verify with index_status/check_index_coverage):
     echo '{"repo_path":"/home/user/Markets","mode":"full"}' | codebase-memory-mcp cli --quiet --json index_repository
     echo '{"project":"home-user-Markets","query":"<symbol>","limit":5}' | codebase-memory-mcp cli --quiet --json search_graph
   The session-start warning that the NG data plane is not restored is expected: nothing here needs data/ or S3.
3. Branch: ccode/teacher-tasks-20261006b (the harness branch is never the work). Exactly:
     git fetch origin ccode/teacher-tasks-20261006b ccr-5fce7de3-xa4hfg
     git checkout -B ccode/teacher-tasks-20261006b origin/ccode/teacher-tasks-20261006b
     git rebase origin/ccr-5fce7de3-xa4hfg && git log --oneline -10
   The tip must be the docs commit above 0cb6868b (BIND-R) on Codex's 3bc72da8 or later. Expect a clean rebase; if Codex edited
   frankie_box_boss_session.py / frankie_box_experiment_exchange.py / frankie_box_scientific_teacher.py /
   frankie_box_teacher_knowledge.py / frankie_box_historical_*.py, read its diff before touching that module.
READ, in order (research/kalshi/frankie_boss/):
   CLAUDE_HANDOFF_20261007_CCODE_SLICES_A_D.md          top section: the Claude-side state, the design choices not to re-litigate
   CCODE_STEP6_RETURN_20261007.md                       step 6: what was built, the weight-learning answer, interface requests
   CCODE_NEXT_SOURCE_TASKS_20261006.md (top section)    Codex's review of the correction commits lands HERE
   NEW_CHAT_HANDOFF_20261006_TEACHER_COVERAGE.md        newest sections only (Codex's reserved search continuation)
   CCODE_STEP4_SOURCE_ROUTE_20261006.md section 8 "Corrections after Codex's integration review" + section 9 table
DONE (source-built, runtime-unverified; nothing ran): A-D (c31cad06 7cb2ce52 11082ff8 2a05c147); the correction queue
D1 18b6edcd (prices: FRANKIE_ROOT_PRICE_ROW_PROVENANCE_V2, originating INPUT from the producer's retained open-group state;
structures stay V1), B7/C2 8930b4f0, B2-B5 5fdc14f5, B1/B6/A4/C1 45f52d28, docs 6002a926, 602e29f6 = B7 BY DELETION.
73288615 = Greg's step-5 direction applied (current tables decide; frozen bindings superseded in both seats + Frankie;
propagation gaps listed in step-4 report section 8). STEP 6: e922a6e2 (deadline through every request; durable per-item
progress, interrupted calls explicit; whole evidence, process release), b3fb5a26 (workflow inputs as env vars; return.json;
owner import named, never dispatched), 2f1d6630 (B2-B5 follow-ups), 11a433a7 (CCODE_STEP6_RETURN_20261007.md: the
weight-learning answer = inference-only, decisions listed for Greg; interface requests to Codex's runner/queue/reports).
GREG (2026-10-07, twice): NO reference to transaction costs in market-conditions work, period. The crypto_harness binding
is deleted from REPRODUCTIONS (H01/H02 stay bound by crypto_trend_flip); no admission table, field, status word or
sentence about costs exists in any owned module. Never reintroduce one; never "frame" a cost-based result as context.
NEXT: (1) Codex's review of the step-6 and B2-B5 follow-up commits lands in the task doc's top section: fix every source
defect it names in the owned files, one [skip ci] commit per finding group, no reapplying what Codex integrated; (2) the
exact price adapter on the V2 price contract is Codex's: answer questions on it only; (3) weight learning: Greg's decisions
(feedback, objective, pin policy, host) are open; implement no training, touch no hash gate; (4) nothing else is assigned:
do not open or invent a slice; if the task doc assigns more, trace first, build within settled contracts only; update the
step-6 return + step-4 report sections 8/9 + the Claude handoff + this drop-in; push with [skip ci].
OWNED (step 6): frankie_box_granite_meeting.py, frankie_box_granite_meeting.sh, frankie_box_granite_meeting_setup.sh,
.github/workflows/frankie_granite_meeting.yml, CCODE_STEP6_RETURN_20261007.md; plus the historical/teacher modules.
Boundaries: source/interface review, ast.parse without project imports, git diff --check ONLY. No tests, runs, installs,
model calls, AWS actions, dispatch, canaries or E2E. Never edit frankie_box_experiment_dipole.py,
frankie_box_experiment_search.py, frankie_box_brain.py, frankie_box_lane_state.py, frankie_box_experiment.py or the shared
assignment/handoff documents (Codex's while step 5 is in flight): return exact interface requests instead. Never call frankie_box_historical_reproduction.run(); never rebuild the claims file.
Granite pins/parameters settled (threads null). STOP before #5; preserved draft unapplied; never apply 9c19cc2.
Memory A retired: H06-H08 stay historical, bind nothing. Greg's decisions stay open (listed in the Claude handoff).
Commits end with the attribution lines the harness gives; no model identifiers in anything pushed. Nothing on the scratchpad.
```
