# DROP-IN (Claude): the CCode pre-#5 queue after Codex's correction queue was returned (2026-10-07, end of the third session)

Paste this box into the new Claude Code session. It is separate from the Codex-facing `CCODE_DROP_IN_20261006_NEXT_CHAT.md`.

```
CCode queue, CLAUDE session, 2026-10-07. STEP 6 (Granite meeting recovery path) + B2-B5 follow-ups are RETURNED (e922a6e2,
b3fb5a26, 2f1d6630 + docs); this session picks up Codex's review of them. HOLD stands. Read CCODE_STEP6_RETURN_20261007.md.
FIRST, in this order:
1. /run using-agent-skills (the Skill tool). Greg's rules and the boundaries below win where they differ from a skill.
2. #run memory mcp: the MCP index_repository call times out at 60 s; run the CLI (minutes; background it and verify):
     echo '{"repo_path":"/home/user/Markets","mode":"full"}' | codebase-memory-mcp cli --quiet --json index_repository
     echo '{"project":"home-user-Markets","query":"<symbol>","limit":5}' | codebase-memory-mcp cli --quiet --json search_graph
   The session-start warning that the NG data plane is not restored is expected: nothing here needs data/ or S3.
3. Branch: ccode/teacher-tasks-20261006b (the harness branch is never the work). Exactly:
     git fetch origin ccode/teacher-tasks-20261006b ccr-5fce7de3-xa4hfg
     git checkout -B ccode/teacher-tasks-20261006b origin/ccode/teacher-tasks-20261006b
     git rebase origin/ccr-5fce7de3-xa4hfg && git log --oneline -10
   The tip must be the docs commit above 2f1d6630 on Codex's 6c033cd5 or later. Expect a clean rebase; if Codex edited
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
b5d0fe74 = Greg's step-5 direction applied (current tables decide; frozen bindings superseded in both seats + Frankie;
propagation gaps listed in step-4 report section 8). The tip must be b5d0fe74 or later.
GREG (2026-10-07, twice): NO reference to transaction costs in market-conditions work, period. The crypto_harness binding
is deleted from REPRODUCTIONS (H01/H02 stay bound by crypto_trend_flip); no admission table, field, status word or
sentence about costs exists in any owned module. Never reintroduce one; never "frame" a cost-based result as context.
NEXT: (1) Codex's review of the correction commits lands in the task doc's top section: fix every source defect it names in
the owned files, one [skip ci] commit per finding group, no reapplying what Codex integrated; (2) the exact price adapter
on the V2 price contract (report section 8) is Codex's: answer questions on it only; (3) nothing else is assigned: do not
open or invent a slice; if the task doc assigns more, trace first, build within settled contracts only; update step-4
report sections 8/9 + the CCODE handoff + the Claude handoff + this drop-in; push with [skip ci].
Boundaries: source/interface review, ast.parse without project imports, git diff --check ONLY. No tests, runs, installs,
model calls, AWS actions, dispatch, canaries or E2E. Never edit frankie_box_experiment_dipole.py or
frankie_box_experiment_search.py. Never call frankie_box_historical_reproduction.run(); never rebuild the claims file.
Granite pins/parameters settled (threads null). STOP before #5; preserved draft unapplied; never apply 9c19cc2.
Memory A retired: H06-H08 stay historical, bind nothing. Greg's decisions stay open (listed in the Claude handoff).
Commits end with the attribution lines the harness gives; no model identifiers in anything pushed. Nothing on the scratchpad.
```
